from __future__ import annotations

import re
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal, QThread, QMetaObject, Qt

from pymodbus.client import ModbusSerialClient, ModbusTcpClient

from app.state.store import AppStore
from app.modbus.connection_service import ConnectionService
from app.modbus.driver import SourceDriver
import inspect


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


def _parse_bool(val) -> Optional[bool]:
    """Возвращает True/False/None из разных представлений."""
    if isinstance(val, bool) or val is None:
        return val
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return None


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
                    retries=1
                )

                if not self.client.connect():
                    self.client.close()
                    raise RuntimeError(
                        f"Не удалось открыть порт {port} "
                        f"(baud={baudrate}, parity={parity}, stop={stopbits}, data=8)."
                    )

                self.driver = SourceDriver(self.client, unit_id=unit_id)


                # Быстрый ping (ничего не записывает в прибор)
                try:
                    if not self.driver.ping():
                        self.client.close()
                        raise RuntimeError(
                            f"Порт {port} открыт, но устройство (unit={unit_id}) не отвечает. Соединение остановлено."
                        )
                except Exception as e:
                    self.client.close()
                    raise RuntimeError(f"Ошибка при попытке связи: {e}")

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
            # ConnectionService теперь управляет собственным внутренним потоком,
            # поэтому просто создаём и стартуем сервис.
            self.svc = ConnectionService(self.driver, parent=None)
            self.svc.measurements.connect(self.store.set_measurements)
            # Подключаем ошибку и к локальному обработчику, и прямо в store —
            # это гарантирует, что GUI получит уведомление, даже если сигнал
            # проходит из рабочего потока.
            self.svc.error.connect(self._on_service_error)
            try:
                # напрямую подключаем сигнал ошибки сервиса к store.set_error
                # это использует queued connection между потоками и гарантирует
                # доставку сообщения в GUI-поток
                self.svc.error.connect(self.store.set_error)
            except Exception:
                # fallback к lambda, если прямое подключение не сработает
                try:
                    self.svc.error.connect(lambda m: self.store.set_error(m))
                except Exception:
                    pass
            self.svc.start()

            self.store.set_connected(True)
            self.connectionChanged.emit(True)
            return True

        except Exception as e:
            self._cleanup()
            # Сохраняем и эмитим ошибку через store
            try:
                self.store.last_error = str(e)
            except Exception:
                pass
            try:
                self.store.set_error(str(e))
            except Exception:
                pass
            return False

    def set_voltage(self, value: float):
        # отправить команду в драйвер на изменение напряжения
        if self.driver:
            self.driver.set_voltage(value)

    def set_current(self, value: float):
        # отправить команду в драйвер на изменение тока
        if self.driver:
            self.driver.set_current(value)

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

    def read_register(self, addr: int) -> bool:
        """
        Читает holding-регистры начиная с addr (0-based).
        Для pymodbus >= 3.6.
        """
        if not self.driver or not hasattr(self.driver, "client"):
            raise RuntimeError("Нет активного подключения к устройству")

        rr = self.driver.client.read_coils(addr)



        if rr.isError():
            raise RuntimeError(f"Ошибка чтения регистра {addr + 1}")
        return rr.bits[0]

    def write_register(self, addr: int, value: int) -> bool:
        if not self.driver or not hasattr(self.driver, "client"):
            raise RuntimeError("Нет активного подключения к устройству")

        rq = self.driver.client.write_coil(addr, value)
        if rq.isError():
            raise RuntimeError(f"Ошибка записи регистра {addr + 1}")
        return True

    # ------------------- Внутреннее -------------------
    def _on_service_error(self, msg: str):
        # При ошибке сервиса — останавливаем опрос и закрываем соединение,
        # чтобы прекратить повторные попытки чтения (и шум в консоли).
        # debug: логируем приход ошибки в контроллер
        try:
            print(f"[SourceController] service error: {msg}")
        except Exception:
            pass
        try:
            self.store.last_error = msg
        except Exception:
            pass
        try:
            self.store.set_error(msg)
        except Exception:
            pass
        # Остановить сервис/клиент немедленно
        try:
            # остановим сервис и закроем клиент
            self._cleanup()
        except Exception:
            pass
        try:
            self.store.set_connected(False)
        except Exception:
            pass
        try:
            self.connectionChanged.emit(False)
        except Exception:
            pass

    def _cleanup(self):
        # Останов сервиса
        if getattr(self, 'svc', None):
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
