from __future__ import annotations

from typing import Optional
from PySide6.QtCore import QObject, Signal, QTimer

from app.modbus.driver import SourceDriver
from app.modbus.registry import Measurements


class ConnectionService(QObject):
    """
    Лёгкий сервис опроса Modbus-источника.
    НИЧЕГО не пишет в прибор — только периодически читает measurements.
    """
    measurements = Signal(object)   # Emits Measurements
    error = Signal(str)

    def __init__(self, driver: SourceDriver, interval_ms: int = 500, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.driver = driver
        self.interval_ms = int(interval_ms)
        self._timer: Optional[QTimer] = None
        self._started = False

    # ---- lifecycle ----
    def start(self):
        if self._started:
            return
        self._timer = QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self._on_poll)
        self._timer.start()
        self._started = True

    def stop(self):
        if self._timer:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer.deleteLater()
            self._timer = None
        self._started = False

    # ---- polling ----
    def _on_poll(self):
        try:
            meas: Optional[Measurements] = self.driver.read_measurements()
            if meas is not None:
                self.measurements.emit(meas)
        except Exception as e:
            # не валим сервис — просто сообщаем ошибку наверх
            self.error.emit(str(e))
