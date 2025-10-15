from __future__ import annotations

import time
from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread, QMetaObject, Qt
from app.modbus.driver import SourceDriver


class _PollerThread(QThread):
    """
    Внутренний поток опроса Modbus. Завершается после первой ошибки.
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
        print("[Poller] started")  # отладка: гарантирует, что run() запущен
        while self._running:
            try:
                meas = self.driver.read_measurements()
                if meas is not None:
                    if callable(self._measurements_cb):
                        try:
                            self._measurements_cb(meas)
                        except Exception:
                            pass
                else:
                    raise RuntimeError("No data received from device")

            except Exception as e:
                # ⚠️ первая ошибка — немедленно выходим
                print(f"[Poller] critical: {e}")
                if callable(self._error_cb):
                    try:
                        self._error_cb(str(e))
                    except Exception:
                        pass

                if callable(self._crit_cb):
                    try:
                        self._crit_cb(f"No response received: {e}")
                    except Exception:
                        pass

                # Закрываем клиент, чтобы Modbus не завис
                try:
                    if hasattr(self.driver, "client") and self.driver.client:
                        self.driver.client.close()
                except Exception:
                    pass

                self._running = False
                break

            time.sleep(self.interval_s)

        print("[Poller] stopped")  # отладка

    def stop(self):
        self._running = False
        self.wait(500)  # подождём завершения


class ConnectionService(QObject):
    measurements = Signal(object)
    error = Signal(str)

    def __init__(self, driver: SourceDriver, interval_ms: int = 500, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.driver = driver
        self.interval_ms = max(10, int(interval_ms))
        self._thread: Optional[_PollerThread] = None
        self._started = False  # ⚠️ предотвращает повторный запуск

    def start(self):
        """Запускает поток опроса (если он ещё не работает)."""
        if self._thread and self._thread.isRunning():
            print("[Service] Already running")
            return

        print("[Service] Starting polling thread...")
        self._thread = _PollerThread(self.driver, interval_s=self.interval_ms / 1000.0, max_failures=1)
        self._thread._measurements_cb = lambda m: self.measurements.emit(m)
        self._thread._error_cb = lambda e: self.error.emit(e)

        def _crit(e: str):
            try:
                self.error.emit(e)
            except Exception:
                pass
            try:
                if callable(self._crit_cb):
                    target = self._crit_cb
                    if hasattr(target, "__self__") and target.__self__ is not None:
                        QMetaObject.invokeMethod(target.__self__, "set_error", Qt.QueuedConnection, e)
                    else:
                        self._crit_cb(e)
            except Exception:
                pass

        self._thread._crit_cb = _crit

        # ⚠️ Делаем поток демоном — гарантированно не «умрёт» сразу
        self._thread.setTerminationEnabled(True)
        self._thread.start()
        self._started = True

    def stop(self):
        """Останавливает поток опроса."""
        if not self._thread:
            return
        print("[Service] Stopping polling thread...")
        try:
            self._thread.stop()
        except Exception:
            pass
        self._thread.wait(1500)
        self._thread = None
        self._started = False
        print("[Service] Polling stopped")
