from __future__ import annotations

import re
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal

from pymodbus.client import ModbusSerialClient, ModbusTcpClient

from app.state.store import AppStore
from app.modbus.connection_service import ConnectionService
from app.modbus.driver import SourceDriver


def _map_parity(p: str) -> str:
    """pymodbus ожидает 'N' / 'E' / 'O'."""
    p = (p or "N").upper()
    return p if p in ("N", "E", "O") else "N"


def _map_stopbits(val) -> float:
    """Приводим к 1 / 1.5 / 2 (float)."""
    try:
        s = float(val)
    except Exception:
        s = 1.0
    if str(val).strip() in ("1.5", "1,5"):
        return 1.5
    if s >= 2:
        return 2.0
    return 1.0


def _normalize_port_name(raw: str | None) -> str:
    """
    Из строки вроде 'COM4 — USB-SERIAL CH340 (COM4)' извлекает 'COM4'.
    Если шаблон не найден — возвращает trimmed исходник.
    """
    if not raw:
        return ""
    s = str(raw)
    m = re.search(r"(COM\d+)", s, flags=re.IGNORECASE)
    return m.group(1).upper() if m else s.strip()


class SourceController(QObject):
    """
    Управляет подключением/отключением и высокоуровневыми командами.
    ВАЖНО: connect() ничего не включает автоматически — питание только через set_power().
    """
    connectionChanged = Signal(bool)

    def __init__(self, store: AppStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.client = None
        self.driver: Optional[SourceDriver] = None
        self.svc: Optional[ConnectionService] = None
        self.conn_type: Optional[str] = None

    # ------------------- Публичный API -------------------
    def connect(self, conn_type: str, settings: Dict[str, Any]) -> bool:
        """
        Устанавливает соединение и запускает ТОЛЬКО опрос (без записи в coils).
        Возвращает True при успехе. Текст ошибки кладёт в store.last_error.
        """
        self.disconnect()
        self.conn_type = (conn_type or "").upper().strip()

        try:
            if self.conn_type == "RTU":
                # ---- Serial RTU (pymodbus 3.x: БЕЗ method="rtu") ----
                raw_port = settings.get("port") or settings.get("device") or ""
                port = _normalize_port_name(raw_port)
                if not port:
                    raise RuntimeError("Не выбран последовательный порт.")

                baudrate = int(settings.get("baudrate", 9600))
                parity = _map_parity(settings.get("parity", "N"))
                stopbits = _map_stopbits(settings.get("stopbits", 1))
                # Data bits — по умолчанию 8 (как в Modbus Poll)
                bytesize = 8
                unit_id = int(settings.get("unit_id", 1))

                self.client = ModbusSerialClient(
                    port=port,
                    baudrate=baudrate,
                    parity=parity,     # 'N'/'E'/'O'
                    stopbits=stopbits, # 1 / 1.5 / 2
                    bytesize=bytesize, # 8 data bits
                    timeout=2.0,
                )
                if not self.client.connect():
                    raise RuntimeError(
                        f"Не удалось открыть порт {port} "
                        f"(baud={baudrate}, parity={parity}, stop={stopbits}, data=8)."
                    )

                self.driver = SourceDriver(self.client, unit_id=unit_id)

                # Быстрый ping (ничего не записывает в прибор)
                if not self.driver.ping():
                    raise RuntimeError(
                        f"Порт {port} открыт, но устройство (unit={unit_id}) не отвечает. "
                        f"Проверьте линию/параметры (baud={baudrate}, parity={parity}, stop={stopbits}, data=8)."
                    )

            else:
                # ---- TCP ----
                host = settings.get("host", "192.168.1.100")
                port = int(settings.get("port", 502))
                unit_id = int(settings.get("unit_id", 1))

                self.client = ModbusTcpClient(host=host, port=port, timeout=2.0)
                if not self.client.connect():
                    raise RuntimeError(f"Не удалось подключиться к {host}:{port}.")

                self.driver = SourceDriver(self.client, unit_id=unit_id)

                if not self.driver.ping():
                    raise RuntimeError(
                        f"Связь с {host}:{port} установлена, но устройство (unit={unit_id}) не отвечает на опрос."
                    )

            # Только опрос — без записи в coils
            self.svc = ConnectionService(self.driver, parent=self)
            self.svc.measurements.connect(self.store.set_measurements)
            self.svc.error.connect(self._on_service_error)
            self.svc.start()

            self.store.set_connected(True)
            self.connectionChanged.emit(True)
            return True

        except Exception as e:
            self._cleanup()
            self.store.last_error = str(e)
            return False

    def disconnect(self):
        """Останавливает опрос и закрывает соединение."""
        self._cleanup()
        self.store.set_connected(False)
        self.connectionChanged.emit(False)

    def set_power(self, on: bool) -> bool:
        """
        Включение/выключение источника.
        Требуем успех обеих катушек и соблюдаем безопасный порядок:
          ON:  питание устройства -> инвертор
          OFF: инвертор -> питание устройства
        """
        if not self.driver:
            return False
        try:
            if on:
                ok1 = bool(self.driver.set_device_power(True))
                ok2 = bool(self.driver.set_inverter_enable(True))
                return ok1 and ok2
            else:
                ok1 = bool(self.driver.set_inverter_enable(False))
                ok2 = bool(self.driver.set_device_power(False))
                return ok1 and ok2
        except Exception:
            return False

    # ------------------- Внутреннее -------------------
    def _on_service_error(self, msg: str):
        # Просто сохраняем последний текст ошибки (для показа в UI)
        self.store.last_error = msg

    def _cleanup(self):
        # Останов сервиса
        if self.svc:
            try:
                self.svc.stop()
            except Exception:
                pass
            self.svc = None

        # Закрытие клиента
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None

        self.driver = None
        self.conn_type = None
