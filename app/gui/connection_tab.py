
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from dictionary import CONNECTION_SCREEN
from .widgets import AlertBox
from .settings_panel import SettingsPanel

class ConnectionTab(QWidget):
    """
    Единая вкладка «Подключение»:
    - сверху селектор типа подключения (в стиле из настроек — без карточек мастера)
    - ниже — сам SettingsPanel (RTU/TCP) со всеми профилями, «?» и подсказками (AlertBox).
    """
    connectRequested = Signal(str, dict)  # (conn_type, settings)

    def __init__(self, on_connect=None, parent=None):
        super().__init__(parent)
        self._on_connect_cb = on_connect
        self._current_type = "RTU"
        self._panel: SettingsPanel | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # --- Заголовок ---
        title = QLabel(CONNECTION_SCREEN.get("title", "Подключение"))
        title.setAlignment(Qt.AlignCenter)
        title.setProperty("role", "title")
        root.addWidget(title)

        # --- Ряд: селектор типа + «?» ---
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addStretch()

        self.type_box = QComboBox()
        self.type_box.addItems(CONNECTION_SCREEN.get("types", ["RTU (RS-485)", "TCP (Modbus/TCP)"]))
        self.type_box.setMinimumWidth(320)
        self.type_box.currentIndexChanged.connect(self._type_changed)
        row.addWidget(self.type_box)

        help_btn = QLabel("?")
        help_btn.setObjectName("HelpDot")  # используем тот же стиль, что и в SettingsPanel
        help_btn.setFixedSize(24, 24)
        help_btn.setAlignment(Qt.AlignCenter)
        help_btn.setStyleSheet("""
            QLabel#HelpDot {
                color: #383d41;
                background: #cce5ff;
                border: 1px solid #b8daff;
                border-radius: 12px;
                font-weight: 800;
            }
            QLabel#HelpDot:hover { background: #b8daff; }
        """)
        # Псевдо-кнопка: клик мыши показывает подсказку
        help_btn.mousePressEvent = lambda e: self.alert.show_message(CONNECTION_SCREEN.get("type_tooltip", ""))
        row.addWidget(help_btn)

        row.addStretch()
        root.addLayout(row)

        # --- Алерт-подсказок ---
        self.alert = AlertBox()
        root.addWidget(self.alert)

        # --- Встраиваем SettingsPanel по текущему типу ---
        self._mount_panel(self._current_type)

    # заменить панель при смене типа
    def _mount_panel(self, conn_type: str):
        if self._panel is not None:
            self.layout().removeWidget(self._panel)
            self._panel.setParent(None)
            self._panel.deleteLater()
            self._panel = None

        self._panel = SettingsPanel(conn_type=conn_type, on_back=lambda: None, on_connect=self._on_connect)
        self.layout().addWidget(self._panel, 1)

    def _type_changed(self, idx: int):
        # определяем тип по тексту (как в ConnectionTypeScreen)
        text = self.type_box.currentText()
        conn_type = "RTU" if "RTU" in text or "485" in text else "TCP"
        if conn_type != self._current_type:
            self._current_type = conn_type
            self._mount_panel(conn_type)

    # проксируем «Подключиться» наверх
    def _on_connect(self, conn_type: str, settings: dict):
        if callable(self._on_connect_cb):
            self._on_connect_cb(conn_type, settings)
        else:
            self.connectRequested.emit(conn_type, settings)

    # Показ ошибки подключения на вложенной панели
    def show_connect_error(self, text: str):
        if self._panel is not None:
            self._panel.show_connect_error(text or "Не удалось подключиться к источнику.")
