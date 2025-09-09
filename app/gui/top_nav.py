from PySide6.QtWidgets import QWidget, QHBoxLayout, QToolButton
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal, QSize
import os
from resources import ASSETS_DIR
from dictionary import HOME_SCREEN

PRIMARY = "#2563eb"     # цвет подчёркивания и текста активной вкладки
HOVER_BG = "rgba(0,0,0,0.06)"
CHECK_BG = "transparent"  # сохраняем «воздух» как в старом виде

class TopNav(QWidget):
    """
    Верхняя панель навигации в стиле СТАРОГО хедера:
    [иконка] [подпись] ---20px--- [иконка] [подпись] ...
    Активная вкладка помечается подчёркнутым текстом и акцентным цветом.
    """
    navigate = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(10)  # как в старом коде

        self.buttons = {
            "home":    self._make_btn("home.svg",           HOME_SCREEN["tabs"]["home"],   "home"),
            "program": self._make_btn("chip.svg",           HOME_SCREEN["tabs"]["chip"],   "program"),
            "source":  self._make_btn("source_arrows.svg",  HOME_SCREEN["tabs"]["source"], "source"),
            "info":    self._make_btn("info.svg",           HOME_SCREEN["tabs"]["info"],   "info"),
        }

        def add_with_gap(key):
            h.addWidget(self.buttons[key])
            h.addSpacing(20)

        add_with_gap("home")
        add_with_gap("program")
        add_with_gap("source")
        h.addWidget(self.buttons["info"])
        h.addStretch()

        self.set_active("home")

    def _make_btn(self, icon_name: str, text: str, key: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)  # иконка + текст сбоку (как раньше)
        btn.setCursor(Qt.PointingHandCursor)

        ico = QIcon(os.path.join(ASSETS_DIR, "icons", icon_name))
        btn.setIcon(ico)
        btn.setIconSize(QSize(28, 28))
        btn.setText(text)

        # Стиль «как лейблы с иконками», плюс активное подчёркивание
        btn.setProperty("topnav_inline", "1")
        btn.setStyleSheet(f"""
            QToolButton[topnav_inline="1"] {{
                background: transparent;
                border: none;
                padding: 0px 4px;       /* лёгкий внутренний отступ для hover */
                color: #111827;
                font-size: 14px;
                border-bottom: none;     /* по умолчанию без подчёркивания */
            }}
            QToolButton[topnav_inline="1"]:hover {{
                background: {HOVER_BG};
                border-radius: 6px;
            }}
            QToolButton[topnav_inline="1"]:checked {{
                background: {CHECK_BG};
                border-radius: 0px;      /* подчёркивание лучше без скругления */
                color: {PRIMARY};
                font-weight: 600;
                border-bottom: 2px solid {PRIMARY};  /* подчёркивание активной вкладки */
                padding-bottom: 1px;                  /* чтобы линия не «прыгала» */
            }}
        """)

        btn.clicked.connect(lambda: self._on_click(key))
        return btn

    def _on_click(self, key: str):
        self.set_active(key)
        self.navigate.emit(key)

    def set_active(self, key: str):
        for k, b in self.buttons.items():
            b.setChecked(k == key)
