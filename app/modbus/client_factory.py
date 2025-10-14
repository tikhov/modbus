from typing import Literal, Dict, Any
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
import serial
import re

ConnType = Literal["RTU", "TCP"]

def _normalize_serial_port(port: str) -> str:
    """
    Приводим строку к реальному имени порта.
    Примеры входа:
      "COM4 — USB-SERIAL CH340 (COM4)" -> "COM4"
      "USB-SERIAL CH340 (COM7)"        -> "COM7"
      "COM5"                            -> "COM5"
      "/dev/ttyUSB0"                    -> "/dev/ttyUSB0" (не трогаем *nix)
    """
    if not port:
        return port
    # если это *nix-путь — возвращаем как есть
    if port.startswith("/dev/"):
        return port
    # вытащим COMxxx из любой строки
    m = re.search(r"(COM\d+)", port, re.IGNORECASE)
    return m.group(1).upper() if m else port

def _normalize_stopbits(value) -> float:
    """
    Приводим stopbits к формату pyserial:
      1 -> serial.STOPBITS_ONE
      1.5 -> serial.STOPBITS_ONE_POINT_FIVE
      2 -> serial.STOPBITS_TWO
    """
    s = str(value).strip().replace(",", ".")
    try:
        f = float(s)
    except Exception:
        f = 1.0

    if abs(f - 2.0) < 1e-6:
        return serial.STOPBITS_TWO
    if abs(f - 1.5) < 1e-6:
        # не все драйверы поддерживают 1.5; если не поддерживается — pyserial бросит исключение
        return serial.STOPBITS_ONE_POINT_FIVE
    # по умолчанию
    return serial.STOPBITS_ONE


def create_client(conn_type: ConnType, settings: Dict[str, Any]):
    """
    settings RTU: {port, baudrate, parity, stopbits, unit_id, timeout?}
    settings TCP: {host, port, unit_id, timeout?}

    ВАЖНО: для pymodbus >= 3.x у ModbusSerialClient больше НЕТ параметра `method`.
    RTU-фреймер устанавливается по умолчанию.
    """
    timeout = float(settings.get("timeout", 1.0))

    if conn_type == "RTU":
        port = _normalize_serial_port(settings["port"])
        baudrate = int(settings.get("baudrate", 9600))
        parity = str(settings.get("parity", "N")).upper()[:1]  # 'N'/'E'/'O'
        stopbits = _normalize_stopbits(settings.get("stopbits", 1))

        # В 3.x: НЕ передавать method="rtu"
        client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,            # pyserial принимает один символ
            stopbits=stopbits,        # pyserial STOPBITS_*
            bytesize=8,
            timeout=timeout,
        )
        # уменьшить внутренние повторные попытки (если поддерживается библиотекой)
        try:
            setattr(client, 'retries', 0)
        except Exception:
            pass
        try:
            setattr(client, 'retry_on_empty', False)
        except Exception:
            pass
        return client

    # TCP
    host = settings["host"]
    port = int(settings.get("port", 502))
    client = ModbusTcpClient(host=host, port=port, timeout=timeout)
    try:
        setattr(client, 'retries', 0)
    except Exception:
        pass
    return client
