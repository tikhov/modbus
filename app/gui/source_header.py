# app/gui/source_header.py
import os

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from resources import ASSETS_DIR


class SourceHeaderWidget(QWidget):
    def __init__(self, source_controller=None, parent=None):
        super().__init__(parent)
        self.source = source_controller  # ← принимаем контроллер
        self._setup_ui()
        self.set_source_name("ИПГ 12/4000-380 IP65 09-25-3007")

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 20, 0, 20)
        layout.setSpacing(100)

        self._btn = QPushButton()
        self._btn.setIcon(QIcon(os.path.join(ASSETS_DIR, "icons", "revers.svg")))
        self._btn.setIconSize(QSize(80, 80))
        self._btn.setFixedSize(80, 80)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: transparent;
            }
        """)
        self._btn.clicked.connect(self._on_button_clicked)

        self._label = QLabel()
        self._label.setStyleSheet("color: #FFFFFF; font-size: 50px; font-weight: 600;")
        self._label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._btn)
        layout.addWidget(self._label)

    def set_source_name(self, name: str):
        self._label.setText(name)

    def _on_button_clicked(self):
        """Читает Coil 1 (включение устройства) и выводит в консоль."""
        if self.source is None:
            print("⚠️ SourceController не передан в SourceHeaderWidget")
            return
        try:
            pass
        except Exception as e:
            print(f"❌ Ошибка при чтении регистра: {e}")
            return