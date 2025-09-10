from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSizePolicy
)

from dictionary import CONNECTION_SCREEN
from .widgets import AlertBox
from .settings_panel import SettingsPanel


class ConnectionTab(QWidget):
    """
    Вкладка «Подключение»:
      ┌ Плашка выбора типа подключения (та же ширина и стили, что и у формы настроек)
      │   ├ селектор как у селектора профиля (тот же objectName/props → одинаковый QSS)
      │   └ AlertBox с подсказками (внутри этой плашки)
      └ SettingsPanel (RTU/TCP) со всеми профилями и кнопкой Подключиться/Отключить
    """
    connectRequested = Signal(str, dict)   # (conn_type, settings)
    disconnectRequested = Signal()         # () — запрос на отключение

    def __init__(self, on_connect=None, on_disconnect=None, parent=None):
        super().__init__(parent)
        self._on_connect_cb = on_connect
        self._on_disconnect_cb = on_disconnect
        self._current_type = "RTU"
        self._panel: SettingsPanel | None = None
        self._is_connected = False
        self._observed_card: QWidget | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # --- Заголовок вкладки (полоса сверху рисует MainWindow) ---
        title = QLabel(CONNECTION_SCREEN.get("title", "Подключение к источнику"))
        title.setAlignment(Qt.AlignCenter)
        title.setProperty("role", "title")
        root.addWidget(title)

        # ---------------- ПЛАШКА ВЫБОРА ТИПА ----------------
        type_card_row = QHBoxLayout()
        type_card_row.setContentsMargins(0, 0, 0, 0)
        type_card_row.setSpacing(0)
        type_card_row.addStretch(1)

        self._type_card = QWidget(objectName="ConnTypeCard")
        self._type_card.setStyleSheet("""
            QWidget {
                background: #3B2F22;
                border-radius: 8px;
            }
            QLabel { color: #ffffff; }
            QLineEdit, QComboBox {
                background: #453D31;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 28px;
            }
            QComboBox::drop-down { border: none; }
        """)
        self._type_card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)

        card_l = QVBoxLayout(self._type_card)
        card_l.setContentsMargins(16, 14, 16, 14)
        card_l.setSpacing(12)

        # Заголовок секции
        sec_title = QLabel(CONNECTION_SCREEN.get("type_title", "Тип подключения"))
        sec_title.setStyleSheet("color:#fff; font-size:14px; font-weight:700;")
        sec_title.setAlignment(Qt.AlignCenter)
        card_l.addWidget(sec_title)

        # Ряд: селектор типа + «?» (центр)
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_row.setAlignment(Qt.AlignCenter)

        self.type_box = QComboBox()
        self.type_box.addItems(CONNECTION_SCREEN.get("types", ["RTU (RS-485)", "TCP (Modbus/TCP)"]))
        self.type_box.setObjectName("ProfileCombo")
        self.type_box.setProperty("form", "1")
        self.type_box.setMinimumWidth(320)
        self.type_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.type_box.currentIndexChanged.connect(self._type_changed)

        help_btn = QLabel("?")
        help_btn.setObjectName("HelpDot")
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
        help_btn.mousePressEvent = lambda e: self.alert.show_message(
            CONNECTION_SCREEN.get("type_tooltip", "Выберите интерфейс связи с источником (RTU/TCP).")
        )

        type_row.addStretch(1)
        type_row.addWidget(self.type_box, 0, Qt.AlignVCenter)
        type_row.addWidget(help_btn, 0, Qt.AlignVCenter)
        type_row.addStretch(1)

        card_l.addLayout(type_row)

        # AlertBox — внутри плашки
        self.alert = AlertBox()
        card_l.addWidget(self.alert)

        type_card_row.addWidget(self._type_card)
        type_card_row.addStretch(1)
        root.addLayout(type_card_row)

        # ---------------- SettingsPanel ----------------
        self._mount_panel(self._current_type)

        # Стартовая синхронизация ширины после раскладки
        QTimer.singleShot(0, self._sync_card_widths)

    # заменить панель при смене типа
    def _mount_panel(self, conn_type: str):
        if self._panel is not None:
            # снять наблюдатель со старой карточки
            if self._observed_card is not None:
                try:
                    self._observed_card.removeEventFilter(self)
                except Exception:
                    pass
                self._observed_card = None
            self.layout().removeWidget(self._panel)
            self._panel.setParent(None)
            self._panel.deleteLater()
            self._panel = None

        self._panel = SettingsPanel(
            conn_type=conn_type,
            on_back=lambda: None,
            on_connect=self._handle_connect_button
        )
        self.layout().addWidget(self._panel, 1)
        self._sync_connect_btn_text()

        # Привязываем наблюдатель к фактической карточке настроек
        form_card = getattr(self._panel, "card", None)
        if form_card is not None:
            self._observed_card = form_card
            form_card.installEventFilter(self)

        QTimer.singleShot(0, self._sync_card_widths)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._sync_card_widths)

    def eventFilter(self, obj, ev):
        # как только карточка настроек получила размер/перелэйаутилась — выровняем ширину
        if obj is self._observed_card and ev.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest):
            self._sync_card_widths()
        return super().eventFilter(obj, ev)

    def _type_changed(self, idx: int):
        text = self.type_box.currentText()
        conn_type = "RTU" if "RTU" in text or "485" in text else "TCP"
        if conn_type != self._current_type:
            self._current_type = conn_type
            self._mount_panel(conn_type)

    # обработчик клика «Подключиться/Отключить»
    def _handle_connect_button(self, conn_type: str, settings: dict):
        if self._is_connected:
            if callable(self._on_disconnect_cb):
                self._on_disconnect_cb()
            else:
                self.disconnectRequested.emit()
        else:
            if callable(self._on_connect_cb):
                self._on_connect_cb(conn_type, settings)
            else:
                self.connectRequested.emit(conn_type, settings)

    # Публично из MainWindow: переключить подпись и режим
    def set_connected(self, connected: bool):
        self._is_connected = bool(connected)
        self._sync_connect_btn_text()

    def _sync_connect_btn_text(self):
        if self._panel is None:
            return
        btn = getattr(self._panel, "connect_btn", None)
        if btn is not None:
            btn.setText("Отключить" if self._is_connected else "Подключиться")

    # Показ ошибки подключения на вложенной панели
    def show_connect_error(self, text: str):
        if self._panel is not None:
            self._panel.show_connect_error(text or "Не удалось подключиться к источнику.")

    # ---- одинаковая ширина плашек (тип подключения == форма настроек) ----
    def _sync_card_widths(self):
        if self._panel is None:
            return
        form_card = getattr(self._panel, "card", None)
        if form_card:
            w = form_card.width() or form_card.sizeHint().width()
            # если ещё не измерен — считаем по такой же формуле, как в SettingsPanel
            if not w or w <= 0:
                w = int(max(420, min(900, self._panel.width() * 0.5)))
        else:
            w = int(max(420, min(900, self.width() * 0.5)))
        if w and w > 0:
            self._type_card.setFixedWidth(int(w))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._sync_card_widths()
