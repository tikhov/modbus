from __future__ import annotations

from typing import Optional
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from .registry import (
    Coils, InputRegs, HoldingRegs, ErrorBits,
    coil, input_reg, holding_reg, u32_from_words, Measurements
)

ModbusClientT = ModbusSerialClient | ModbusTcpClient
SCALE_I = 1.0
SCALE_V = 1.0


class SourceDriver:
    """
    Совместимо с разными вариантами pymodbus (2.x / 3.x) и обёртками:
    - пробуем вызывать методы с unit=..., при TypeError повторяем без unit
    - ток/напряжение читаем как int16 (поддержка отрицательных значений)
    - авто-детект свопа I/U и 0/1-базового смещения адреса (+/-1)
    - А·ч читаем из блока 6 регистров, начиная с ERROR_FLAGS (индексы 4..5)
    """
    def __init__(self, client: ModbusClientT, unit_id: int = 1):
        self.client = client
        self.unit = unit_id
        self._iv_swapped = False
        self._addr_shift = 0
        # Попробуем задать идентификатор слейва в сам клиент — для реализаций без unit=...
        for attr in ("unit_id", "unit", "slave"):
            try:
                setattr(self.client, attr, self.unit)
            except Exception:
                pass

    # -------- вспомогательные совместимые вызовы --------
    def _read_input_registers(self, address: int, count: int = 1):
        try:
            return self.client.read_input_registers(address, count=count, unit=self.unit)
        except TypeError:
            return self.client.read_input_registers(address, count=count)

    def _read_holding_registers(self, address: int, count: int = 1):
        try:
            return self.client.read_holding_registers(address, count=count, unit=self.unit)
        except TypeError:
            return self.client.read_holding_registers(address, count=count)

    def _read_coils(self, address: int, count: int = 1):
        try:
            return self.client.read_coils(address, count=count, unit=self.unit)
        except TypeError:
            return self.client.read_coils(address, count=count)

    def _write_coil(self, address: int, value: bool):
        try:
            return self.client.write_coil(address, bool(value), unit=self.unit)
        except TypeError:
            return self.client.write_coil(address, bool(value))

    def _write_register(self, address: int, value: int):
        try:
            return self.client.write_register(address, int(value), unit=self.unit)
        except TypeError:
            return self.client.write_register(address, int(value))

    # -------- общие утилиты --------
    @staticmethod
    def _s16(x: int) -> int:
        return x - 0x10000 if x & 0x8000 else x

    def _read_inp(self, addr: int, count: int = 1):
        rr = self._read_input_registers(addr, count=count)
        if getattr(rr, "isError", lambda: True)():
            return None
        regs = getattr(rr, "registers", None)
        return regs if regs and len(regs) >= count else None

    def _read_block_flex(self, start_addr: int, count: int):
        """
        Читаем блок с автосмещением адреса. Пробуем последовательность смещений:
        текущий self._addr_shift, затем -1, +1, 0.
        """
        shifts = [self._addr_shift, -1, +1, 0]
        seen = set()
        for sh in shifts:
            if sh in seen:
                continue
            seen.add(sh)
            regs = self._read_inp(start_addr + sh, count=count)
            if regs is not None:
                if self._addr_shift != sh:
                    self._addr_shift = sh
                return regs
        return None

    # -------- Coils --------
    def set_device_power(self, on: bool) -> bool:
        rr = self._write_coil(coil(Coils.ENABLE_DEVICE), bool(on))
        return hasattr(rr, "isError") and not rr.isError()

    def set_inverter_enable(self, on: bool) -> bool:
        rr = self._write_coil(coil(Coils.INVERTER_ENABLE), bool(on))
        return hasattr(rr, "isError") and not rr.isError()

    def reset_ah_counter(self) -> bool:
        r1 = self._write_coil(coil(Coils.AH_RESET), True)
        r2 = self._write_coil(coil(Coils.AH_RESET), False)
        return all((hasattr(r1, "isError") and not r1.isError(),
                    hasattr(r2, "isError") and not r2.isError()))

    def set_control_mode_lock(self, locked: bool) -> bool:
        rr = self._write_coil(coil(Coils.CONTROL_MODE_LOCK), bool(locked))
        return hasattr(rr, "isError") and not rr.isError()

    def read_control_mode_info(self) -> Optional[int]:
        rr = self._read_coils(coil(Coils.CONTROL_MODE_INFO), count=1)
        bits = getattr(rr, "bits", None)
        if getattr(rr, "isError", lambda: True)() or not bits:
            return None
        return 1 if bits[0] else 0

    # -------- Holding --------
    def set_current_setpoint(self, value: int) -> bool:
        rr = self._write_register(holding_reg(HoldingRegs.CURRENT_SETPOINT), int(value))
        return hasattr(rr, "isError") and not rr.isError()

    def read_current_setpoint(self) -> Optional[int]:
        rr = self._read_holding_registers(holding_reg(HoldingRegs.CURRENT_SETPOINT), count=1)
        regs = getattr(rr, "registers", None)
        if getattr(rr, "isError", lambda: True)() or not regs:
            return None
        return int(regs[0])

    # -------- Inputs --------
    def read_measurements(self) -> Optional[Measurements]:
        """
        Читаем единым блоком 6 слов, начиная с ERROR_FLAGS:
          [0] ошибки, [1] I, [2] U, [3] полярность, [4] А·ч lo, [5] А·ч hi
        Затем — 2 слова температур от TEMP1.
        """
        base = input_reg(InputRegs.ERROR_FLAGS)
        regs1 = self._read_block_flex(base, 6)
        if regs1 is None or len(regs1) < 6:
            return None

        err   = regs1[0]
        i_raw = regs1[1]
        v_raw = regs1[2]
        pol   = regs1[3]
        ah_lo = regs1[4]
        ah_hi = regs1[5]
        ah32  = u32_from_words(ah_hi, ah_lo)

        # авто-своп I/U (если один ноль, другой нет) — запоминаем один раз
        if not self._iv_swapped:
            if (v_raw == 0 and i_raw != 0) or (i_raw == 0 and v_raw != 0):
                self._iv_swapped = True
        if self._iv_swapped:
            i_raw, v_raw = v_raw, i_raw

        curr = self._s16(i_raw) * SCALE_I
        volt = self._s16(v_raw) * SCALE_V

        # температуры
        tbase = input_reg(InputRegs.TEMP1)
        regs2 = self._read_block_flex(tbase, 2)
        if not regs2:
            t1 = t2 = None
        else:
            t1, t2 = regs2[0], regs2[1]

        return Measurements(
            current=float(curr),
            voltage=float(volt),
            polarity=int(pol),
            ah_counter=int(ah32),
            temp1=(float(t1) if t1 is not None else None),
            temp2=(float(t2) if t2 is not None else None),
            errors_raw=int(err),
            error_overheat=bool((int(err) >> ErrorBits.OVERHEAT) & 1),
            error_mains=bool((int(err) >> ErrorBits.MAINS_MONITOR) & 1),
        )

    # -------- Пинг --------
    def ping(self) -> bool:
        base = input_reg(InputRegs.ERROR_FLAGS)
        regs1 = self._read_block_flex(base, 2)  # [0]=err, [1]=I
        return regs1 is not None
