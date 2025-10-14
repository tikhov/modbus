from __future__ import annotations

from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtCore import QMetaObject, Qt
import time

from app.modbus.driver import SourceDriver
from app.modbus.registry import Measurements


class _PollerThread(QThread):
    """Внутренний поток, который опрашивает driver.read_measurements периодически.
    При N подряд ошибок — останавливается и эмитит ошибку через callback.
    """
    def __init__(self, driver: SourceDriver, interval_s: float = 0.5, max_failures: int = 1):
        super().__init__()
        self.driver = driver
        self.interval_s = float(interval_s)
        self.max_failures = int(max_failures)
        self._running = True
        self._measurements_cb = None
        self._error_cb = None
        self._crit_cb = None

    def run(self):
        failures = 0
        while self._running:
            try:
                meas = self.driver.read_measurements()
                if meas is not None:
                    failures = 0
                    if callable(self._measurements_cb):
                        try:
                            self._measurements_cb(meas)
                        except Exception:
                            pass
                else:
                    # считали None — считаем это неудачей
                    failures += 1
            except Exception as e:
                failures += 1
                # debug: сообщаем об ошибке чтения
                try:
                    print(f"[Poller] read error: {e}")
                except Exception:
                    pass
                if callable(self._error_cb):
                    try:
                        self._error_cb(str(e))
                    except Exception:
                        pass

            if failures >= self.max_failures:
                # критическая серия неудач — сообщаем ошибку и выходим
                try:
                    print(f"[Poller] critical: No response received after {self.max_failures} retries")
                except Exception:
                    pass
                if callable(self._error_cb):
                    try:
                        self._error_cb(f"No response received after {self.max_failures} retries")
                    except Exception:
                        pass
                if callable(self._crit_cb):
                    try:
                        self._crit_cb(f"No response received after {self.max_failures} retries")
                    except Exception:
                        pass
                break

            # пауза
            time.sleep(self.interval_s)

    def stop(self):
        self._running = False


class ConnectionService(QObject):
    measurements = Signal(object)   # Emits Measurements
    error = Signal(str)

    def __init__(self, driver: SourceDriver, interval_ms: int = 500, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.driver = driver
        self.interval_ms = max(10, int(interval_ms))
        self._thread: Optional[_PollerThread] = None

    def start(self):
        if self._thread and self._thread.isRunning():
            return
        # остановимся сразу при первой серьёзной неудаче (не будем ждать 3 ретраев)
        self._thread = _PollerThread(self.driver, interval_s=self.interval_ms / 1000.0, max_failures=1)
        # callbacks: чтобы сигналы эмитились в Qt-потоке вызывающего объекта
        self._thread._measurements_cb = lambda m: self.measurements.emit(m)
        self._thread._error_cb = lambda e: self.error.emit(e)
        # При критической ошибке — эмитим сигнал error и дополнительно
        # форсированно вызываем set_error через QMetaObject.invokeMethod если
        # у вызывающего объекта есть такая функция (это поможет при проблемах
        # с queued connections между потоками).
        def _crit(e: str):
            try:
                self.error.emit(e)
            except Exception:
                pass
            # если у драйвера/контроллера зарегистрирован метод для прямого
            # обновления хранилища — вызовем его в GUI-потоке (внешние
            # объекты могут передать callback через _crit_cb)
            try:
                # предполагаем, что кто-то мог установить _crit_cb как
                # callable(target_obj) — поддерживаем оба варианта
                if callable(self._crit_cb):
                    try:
                        target = self._crit_cb
                        # если _crit_cb — это привязанный метод к объекту,
                        # попытаемся вызвать его через invokeMethod
                        # (если это строка/имя — пропустим)
                        if hasattr(target, '__self__') and target.__self__ is not None:
                            QMetaObject.invokeMethod(target.__self__, 'set_error', Qt.QueuedConnection, e)
                    except Exception:
                        # последний резорт: попробовать просто вызвать
                        try:
                            self._crit_cb(e)
                        except Exception:
                            pass
            except Exception:
                pass

        self._thread._crit_cb = _crit
        self._thread.start()

    def stop(self):
        try:
            if self._thread:
                self._thread.stop()
                self._thread.wait(1500)
        except Exception:
            pass
        self._thread = None
