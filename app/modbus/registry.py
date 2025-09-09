"""
Маппинг регистров Modbus и утилиты.
Важно: в документации адреса даны 1-based (00001, 30001, 40001).
В pymodbus используем 0-based, поэтому из кода ВСЕГДА вычитаем 1.
"""

from dataclasses import dataclass

# ---- Coils (FC 01 чтение, FC 05 запись) ----
class Coils:
    ENABLE_DEVICE          = 1      # 00001: 1–включен, 0–выключен
    INVERTER_ENABLE        = 2      # 00002: 1–включен, 0–выключен
    AH_RESET               = 3      # 00003: 1–сбросить, 0–считать
    CONTROL_MODE_LOCK      = 4      # 00004: 1–заблокировано, 0–разблокировано
    CONTROL_MODE_INFO      = 5      # 00005: 0–местное, 1–внешнее (read-only по смыслу)

# ---- Input Registers (FC 04) ----
class InputRegs:
    ERROR_FLAGS            = 30001  # биты ошибок (см. ниже)
    OUTPUT_CURRENT         = 30002  # измеряемый ток
    OUTPUT_VOLTAGE         = 30003  # измеряемое напряжение
    POLARITY               = 30004  # полярность
    AH_COUNTER_LO          = 30005  # младшее слово счётчика А·ч
    AH_COUNTER_HI          = 30006  # старшее слово счётчика А·ч
    TEMP1                  = 30010
    TEMP2                  = 30011

# ---- Holding Registers (FC 03 чтение, FC 06/16 запись) ----
class HoldingRegs:
    CURRENT_SETPOINT       = 40001  # уставка выходного тока

# ---- Биты регистра ошибок (30001) ----
class ErrorBits:
    OVERHEAT               = 0  # 1 — перегрев
    MAINS_MONITOR          = 1  # 1 — ошибка сети

# ---- Утилиты смещения (1-based -> 0-based) ----
def coil(addr_1based: int) -> int:
    return addr_1based - 1

def input_reg(addr_1based: int) -> int:
    return addr_1based - 30001  # смещение в диапазоне input-регистров

def holding_reg(addr_1based: int) -> int:
    return addr_1based - 40001  # смещение в диапазоне holding-регистров

# ---- Склейка 32-битного значения из двух 16-бит слов (HI+LO) ----
def u32_from_words(hi: int, lo: int) -> int:
    return ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)

@dataclass
class Measurements:
    current: float
    voltage: float
    polarity: int
    ah_counter: int
    temp1: float | None
    temp2: float | None
    errors_raw: int
    error_overheat: bool
    error_mains: bool
