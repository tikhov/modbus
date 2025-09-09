# app/state/store.py
from PySide6.QtCore import QObject, Signal

class AppStore(QObject):
    """
    Хранит текущее состояние: подключение, измерения, ошибки.
    Уведомляет GUI сигналами (можно привязывать к виджетам).
    """
    connectionChanged = Signal(bool)
    errorText = Signal(str)
    measurementsChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = False
        self.meas = None

    def set_connected(self, value: bool):
        if self.connected != value:
            self.connected = value
            self.connectionChanged.emit(value)

    def set_error(self, msg: str):
        self.errorText.emit(msg)

    def set_measurements(self, meas):
        self.meas = meas
        self.measurementsChanged.emit(meas)
