from __future__ import annotations

from typing import Optional, List
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from .registry import (
    Coils, InputRegs, HoldingRegs, ErrorBits,
    coil, input_reg, holding_reg, u32_from_words, Measurements
)

ModbusClientT = ModbusSerialClient | ModbusTcpClient

# Твой прибор отдаёт десятые доли -> масштабирую к «человеческим» единицам
SCALE_I = 0.1
SCALE_V = 0.1

ADDR_MIN = 0
ADDR_MAX = 65535  # верхняя граница (исключая)


class SourceDriver:
    def __init__(self, client: ModbusClientT, unit_id: int = 1, swap_iv: Optional[bool] = None):
        self.client = client
        self.unit = unit_id
        self._swap_iv: Optional[bool] = swap_iv  # None — автоопределение
        # Критично: начинаем сдвиг с +1 (по твоему дампу это «правильное окно»)
        self._addr_shift = 1

        for attr in ("unit_id", "unit", "slave"):
            try:
                setattr(self.client, attr, self.unit)
            except Exception:
                pass

    # ---------- совместимые обёртки ----------
    def _read_input_registers(self, address: int, count: int = 1):
        try:
            return self.client.read_input_registers(address, count=count)
        except Exception:
            return None

    def _read_holding_registers(self, address: int, count: int = 1):
        try:
            return self.client.read_holding_registers(address, count=count)
        except Exception:
            return None

    def _read_coils(self, address: int, count: int = 1):
        try:
            return self.client.read_coils(address, count=count)
        except Exception:
            return None

    def _write_coil_raw(self, address: int, value: bool):
        try:
            return self.client.write_coil(address, bool(value))
        except Exception:
            return None

    def _write_register(self, address: int, value: int):
        try:
            return self.client.write_register(address, int(value))
        except Exception:
            return None

    # ---------- утилиты чтения ----------
    @staticmethod
    def _s16(x: int) -> int:
        return x - 0x10000 if x & 0x8000 else x

    @staticmethod
    def _pair_addrs_input(addr_1based: int) -> tuple[int, int]:
        """
        Две базы адресации:
          - offset (0-based внутри input-диапазона): input_reg(30001)=0, 30002=1, ...
          - absolute (1-based-1): 30001→30000, 30002→30001, ...
        """
        offset = input_reg(addr_1based)
        absolute = addr_1based - 1
        return offset, absolute

    @staticmethod
    def _ok_regs(rr, need: int) -> Optional[List[int]]:
        if getattr(rr, "isError", lambda: True)():
            return None
        regs = getattr(rr, "registers", None)
        return regs if regs and len(regs) >= need else None

    @staticmethod
    def _addr_is_ok(start: int, count: int) -> bool:
        return start >= ADDR_MIN and (start + count - 1) < ADDR_MAX

    def _read_inp_mode(self, base_addr: int, count: int) -> Optional[List[int]]:
        if not self._addr_is_ok(base_addr, count):
            return None
        return self._ok_regs(self._read_input_registers(base_addr, count=count), count)

    def _read_hold_mode(self, base_addr: int, count: int) -> Optional[List[int]]:
        if not self._addr_is_ok(base_addr, count):
            return None
        return self._ok_regs(self._read_holding_registers(base_addr, count=count), count)

    def _shifts_for(self) -> List[int]:
        """
        Порядок перебора сдвигов:
        - текущий (обычно +1)
        - 0
        - +1 (на случай сбоя внутреннего состояния)
        """
        out = [self._addr_shift, 0, 1]
        # убрать дубликаты, сохранить порядок
        seen = set(); res = []
        for x in out:
            if x not in seen:
                seen.add(x); res.append(x)
        return res

    def _read_block_smart(self, addr_1based_start: int, count: int) -> Optional[List[int]]:
        """
        Пробуем две схемы адресации (offset/absolute).
        В каждой — безопасные сдвиги: [self._addr_shift, 0, +1], без отрицательных адресов.
        """
        off_base, abs_base = self._pair_addrs_input(addr_1based_start)
        for reader in (self._read_inp_mode, self._read_hold_mode):
            for base in (off_base, abs_base):
                for sh in self._shifts_for():
                    start = base + sh
                    regs = reader(start, count)
                    if regs is not None:
                        if self._addr_shift != sh:
                            self._addr_shift = sh
                        return regs
        return None

    def _read_single_smart(self, addr_1based: int) -> Optional[int]:
        try:
            off_base, abs_base = self._pair_addrs_input(addr_1based)
            for reader in (self._read_inp_mode, self._read_hold_mode):
                for base in (off_base, abs_base):
                    for sh in self._shifts_for():
                        start = base + sh
                        regs = reader(start, 1)
                        if regs is not None:
                            if self._addr_shift != sh:
                                self._addr_shift = sh
                            return regs[0]
                        else:
                            return None
        except Exception:
            pass
        return None

    # ---------- запись катушек с верификацией ----------
    def _verify_coil(self, address: int, value: bool) -> bool:
        rr = self._read_coils(address, count=1)
        bits = getattr(rr, "bits", None)
        if hasattr(rr, "isError") and rr.isError():
            return False
        if bits is None:
            # некоторые реализации не возвращают bits — считаем успех по отсутствию ошибки записи
            return True
        return bool(bits[0]) == bool(value)

    def _write_coil_flex(self, address: int, value: bool) -> bool:
        """
        Пишем катушку и подтверждаем чтением.
        Если подтверждение не прошло — пробуем address-1 (на случай 1-based адресации на стороне устройства).
        """
        r = self._write_coil_raw(address, value)
        ok = hasattr(r, "isError") and not r.isError()
        if ok and self._verify_coil(address, value):
            return True

        # fallback: адрес-1
        r2 = self._write_coil_raw(address - 1, value)
        ok2 = hasattr(r2, "isError") and not r2.isError()
        return ok2 and self._verify_coil(address - 1, value)

    # ---------- Coils ----------
    def set_device_power(self, on: bool) -> bool:
        return self._write_coil_flex(coil(Coils.ENABLE_DEVICE), bool(on))

    def set_inverter_enable(self, on: bool) -> bool:
        return self._write_coil_flex(coil(Coils.INVERTER_ENABLE), bool(on))

    def reset_ah_counter(self) -> bool:
        ok1 = self._write_coil_flex(coil(Coils.AH_RESET), True)
        ok2 = self._write_coil_flex(coil(Coils.AH_RESET), False)
        return ok1 and ok2

    def set_control_mode_lock(self, locked: bool) -> bool:
        return self._write_coil_flex(coil(Coils.CONTROL_MODE_LOCK), bool(locked))

    def read_control_mode_info(self) -> Optional[int]:
        rr = self._read_coils(coil(Coils.CONTROL_MODE_INFO), count=1)
        bits = getattr(rr, "bits", None)
        if getattr(rr, "isError", lambda: True)() or not bits:
            return None
        return 1 if bits[0] else 0

    # ---------- Holding ----------
    def set_current_setpoint(self, value: int) -> bool:
        rr = self._write_register(holding_reg(HoldingRegs.CURRENT_SETPOINT), int(value))
        return hasattr(rr, "isError") and not rr.isError()

    def read_current_setpoint(self) -> Optional[int]:
        rr = self._read_holding_registers(holding_reg(HoldingRegs.CURRENT_SETPOINT), count=1)
        regs = getattr(rr, "registers", None)
        if getattr(rr, "isError", lambda: True)() or not regs:
            return None
        return int(regs[0])

    def set_voltage(self, value: float):
        # масштабировать и записать в регистр напряжения
        scaled = int(value / SCALE_V)
        self._write_register(HoldingRegs.VOLTAGE_SETPOINT, scaled)

    def set_current(self, value: float):
        # масштабировать и записать в регистр тока
        scaled = int(value / SCALE_I)
        self._write_register(HoldingRegs.CURRENT_SETPOINT, scaled)

    def read_40001_and_40002(self):
        from .registry import HoldingRegs  # Импортируем внутри метода или в начале файла

        rr1 = self._read_holding_registers(holding_reg(HoldingRegs.CURRENT_SETPOINT), count=1)
        rr2 = self._read_holding_registers(holding_reg(HoldingRegs.VOLTAGE_SETPOINT), count=1)

        i = None
        v = None

        if rr1 and not rr1.isError() and hasattr(rr1, 'registers') and len(rr1.registers) > 0:
            i = rr1.registers[0]

        if rr2 and not rr2.isError() and hasattr(rr2, 'registers') and len(rr2.registers) > 0:
            v = rr2.registers[0]

        return i, v

    def read_revers(self):
        from .registry import HoldingRegs  # Импортируем внутри метода или в начале файла

        rr1 = self._read_holding_registers(holding_reg(HoldingRegs.REVERS), count=1)

        i = None

        if rr1 and not rr1.isError() and hasattr(rr1, 'registers') and len(rr1.registers) > 0:
            i = rr1.registers[0]

        return i

    def write_revers(self, value: int) -> bool:
        rr = self._write_register(holding_reg(HoldingRegs.REVERS), int(value))
        success = hasattr(rr, "isError") and not rr.isError()
        if not success:
            print(f"Ошибка записи {value} в регистр {HoldingRegs.REVERS}")

        return success
        # --- Чтение/запись конкретных регистров ---

    def read_voltage_register(self) -> Optional[int]:
        from .registry import HoldingRegs
        try:
            rr = self._read_holding_registers(holding_reg(HoldingRegs.VOLTAGE_SETPOINT), count=1)
            if rr and not getattr(rr, 'isError', lambda: False)() and hasattr(rr, 'registers') and len(rr.registers) > 0:
                return int(rr.registers[0])
        except Exception:
            pass
        return None

    def write_voltage_register(self, value: int) -> bool:
        if value > 120:
            value = 120
        if value < 1:
            value = 1
        rr = self._write_register(holding_reg(HoldingRegs.VOLTAGE_SETPOINT), int(value))
        success = (rr is not None) and (not getattr(rr, 'isError', lambda: False)())
        if not success:
            print(f"Ошибка записи {value} в регистр напряжения {HoldingRegs.VOLTAGE_SETPOINT}")

        return success

    def read_current_register(self) -> Optional[int]:
        try:
            rr = self._read_holding_registers(holding_reg(HoldingRegs.CURRENT_SETPOINT), count=1)
            if rr and not getattr(rr, 'isError', lambda: False)() and hasattr(rr, 'registers') and len(rr.registers) > 0:
                return int(rr.registers[0])
        except Exception:
            pass
        return None

    def write_current_register(self, value: int) -> bool:
        if value > 5000:
            value = 5000
        if value < 1:
            value = 1
        rr = self._write_register(holding_reg(HoldingRegs.CURRENT_SETPOINT), int(value))
        success = (rr is not None) and (not getattr(rr, 'isError', lambda: False)())
        if not success:
            print(f"Ошибка записи {value} в регистр тока {HoldingRegs.CURRENT_SETPOINT}")
        return success

    # ---------- Inputs ----------
    def read_measurements(self) -> Optional[Measurements]:
        try:
            # I/U
            i_raw = self._read_single_smart(InputRegs.OUTPUT_CURRENT)
            u_raw = self._read_single_smart(InputRegs.OUTPUT_VOLTAGE)

            i, v = self.read_40001_and_40002()

            if i_raw is None or u_raw is None:
                return None

            curr = self._s16(int(i_raw)) * SCALE_I
            volt = self._s16(int(u_raw)) * SCALE_V

            # Остальные поля — блочно 30001.., при необходимости — поштучно
            regs1 = self._read_block_smart(InputRegs.ERROR_FLAGS, 6)
            err = pol = ah_lo = ah_hi = None
            if regs1 and len(regs1) >= 6:
                base_off = input_reg(InputRegs.ERROR_FLAGS)
                idx = lambda a1: input_reg(a1) - base_off
                try:
                    err   = regs1[idx(InputRegs.ERROR_FLAGS)]
                    pol   = regs1[idx(InputRegs.POLARITY)]
                    ah_lo = regs1[idx(InputRegs.AH_COUNTER_LO)]
                    ah_hi = regs1[idx(InputRegs.AH_COUNTER_HI)]
                except Exception:
                    pass

            if err   is None: err   = self._read_single_smart(InputRegs.ERROR_FLAGS)
            if pol   is None: pol   = self._read_single_smart(InputRegs.POLARITY)
            if ah_lo is None: ah_lo = self._read_single_smart(InputRegs.AH_COUNTER_LO)
            if ah_hi is None: ah_hi = self._read_single_smart(InputRegs.AH_COUNTER_HI)
            if None in (err, pol, ah_lo, ah_hi):
                return None

            ah32 = u32_from_words(int(ah_hi), int(ah_lo))

            # Температуры
            t_regs = self._read_block_smart(InputRegs.TEMP1, 2)
            if t_regs and len(t_regs) >= 2:
                t1, t2 = t_regs[0], t_regs[1]
            else:
                t1 = self._read_single_smart(InputRegs.TEMP1)
                t2 = self._read_single_smart(InputRegs.TEMP2)

            return Measurements(
                current=float(curr),
                voltage=float(volt),
                current_i=float(i),
                voltage_i=float(v),
                polarity=int(pol),
                ah_counter=int(ah32),
                temp1=(float(t1) if t1 is not None else None),
                temp2=(float(t2) if t2 is not None else None),
                errors_raw=int(err),
                error_overheat=bool((int(err) >> ErrorBits.OVERHEAT) & 1),
                error_mains=bool((int(err) >> ErrorBits.MAINS_MONITOR) & 1),
            )
        except Exception:
            return None

    # ---------- Пинг ----------
    def ping(self) -> bool:
        try:
        # Самый надёжный быстрый ping — одиночное чтение 30001
            return self._read_single_smart(InputRegs.ERROR_FLAGS) is not None
        except:
            return False
