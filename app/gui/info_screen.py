from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from dictionary import INFO_TAB

class InfoScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(10)

        title = QLabel(INFO_TAB.get("title"))
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        desc = QLabel(INFO_TAB.get("text"))
        desc.setAlignment(Qt.AlignCenter)
        v.addWidget(desc, 1)
