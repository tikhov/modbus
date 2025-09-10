
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

class SettingsScreen(QWidget):
    """Заглушка вкладки «Настройки» (шестерёнка)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(10)

        title = QLabel("Настройки")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        desc = QLabel("Раздел находится в разработке.")
        desc.setAlignment(Qt.AlignCenter)
        v.addWidget(desc, 1)
