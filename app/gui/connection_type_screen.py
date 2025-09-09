from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton,
    QHBoxLayout, QSizePolicy
)
from PySide6.QtCore import Qt
from dictionary import CONNECTION_SCREEN
from .widgets import AlertBox

class ConnectionTypeScreen(QWidget):
    def __init__(self, on_next, on_back):
        super().__init__()
        self.on_next = on_next
        self.on_back = on_back

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Центрируем «карточку»
        center_row = QHBoxLayout()
        center_row.addStretch()

        self.card = QWidget()
        self.card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        v = QVBoxLayout(self.card)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        title = QLabel(f"<b>{CONNECTION_SCREEN['title']}</b>")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        # Ряд: селектор + «?»
        row = QHBoxLayout()
        row.setSpacing(6)

        self.type_box = QComboBox()
        self.type_box.addItems(CONNECTION_SCREEN["types"])
        self.type_box.setMinimumWidth(320)
        row.addStretch()
        row.addWidget(self.type_box)
        help_btn = QPushButton("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setStyleSheet("""
            QPushButton {
                color: #383d41;
                border: 1px solid #b8daff;
                border-radius: 12px;
                background: #cce5ff;
                font-weight: bold;
            }
            QPushButton:hover { background: #b8daff; }
        """)
        row.addWidget(help_btn)
        row.addStretch()
        v.addLayout(row)

        self.alert = AlertBox()
        v.addWidget(self.alert)

        hint = QLabel(CONNECTION_SCREEN["hint"])
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#666;")
        v.addWidget(hint)

        buttons = QHBoxLayout()
        back_btn = QPushButton(CONNECTION_SCREEN["back_btn"])
        back_btn.clicked.connect(self.on_back)
        next_btn = QPushButton(CONNECTION_SCREEN["next_btn"])
        next_btn.clicked.connect(self._go_next)
        buttons.addStretch()
        buttons.addWidget(back_btn)
        buttons.addWidget(next_btn)
        v.addLayout(buttons)

        # клик по «?» — показать алерт
        help_btn.clicked.connect(lambda: self.alert.show_message(CONNECTION_SCREEN.get("type_tooltip", "")))

        center_row.addWidget(self.card)
        center_row.addStretch()

        root.addStretch()
        root.addLayout(center_row)
        root.addStretch()

    def resizeEvent(self, e):
        w = max(360, int(self.width() * 0.5))
        w = min(720, w)
        self.card.setFixedWidth(w)
        super().resizeEvent(e)

    def _go_next(self):
        selected = self.type_box.currentText()
        conn_type = "RTU" if "RTU" in selected else "TCP"
        self.on_next(conn_type)
