from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class ProgramScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(16)

        title = QLabel("Программный режим")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        center = QVBoxLayout()
        center.addStretch()

        row = QHBoxLayout()
        btnStart = QPushButton("ПУСК")
        btnStart.setObjectName("btnPrimary")
        btnStart.setMinimumHeight(44)
        row.addWidget(btnStart)

        btnStop = QPushButton("СТОП")
        btnStop.setObjectName("btnDanger")
        btnStop.setMinimumHeight(44)
        row.addWidget(btnStop)

        btnEnter = QPushButton("ВВОД")
        btnEnter.setObjectName("btnEnter")
        btnEnter.setMinimumHeight(44)
        row.addWidget(btnEnter)

        center.addLayout(row)
        center.addStretch()

        v.addLayout(center, 1)
