from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
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

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # --- Заголовок вкладки (сам заголовок полосы сверху теперь делает MainWindow) ---
        title = QLabel(CONNECTION_SCREEN.get("title", "Подключение к источнику"))
        title.setAlignment(Qt.AlignCenter)
        title.setProperty("role", "title")
        root.addWidget(title)

        # ---------------- ПЛАШКА ВЫБОРА ТИПА (такая же ширина, как у формы настроек) ----------------
        # Оборачиваем в горизонтальный контейнер со стретчами, чтобы центрировать.
        type_card_row = QHBoxLayout()
        type_card_row.setContentsMargins(0, 0, 0, 0)
        type_card_row.setSpacing(0)
        type_card_row.addStretch(1)

        self._type_card = QWidget(objectName="ConnTypeCard")
        self._type_card.setStyleSheet("""
            QWidget#ConnTypeCard {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
            }
        """)
        self._type_card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)

        card_l = QVBoxLayout(self._type_card)
        card_l.setContentsMargins(16, 14, 16, 14)
        card_l.setSpacing(12)

        # Заголовок секции
        sec_title = QLabel(CONNECTION_SCREEN.get("type_title", "Тип подключения"))
        sec_title.setStyleSheet("color:#fff; font-size:14px; font-weight:700;")
        card_l.addWidget(sec_title)

        # Ряд: селектор типа + «?»
        type_row = QHBoxLayout()
        type_row.setSpacing(8)

        # Селектор: используем те же маркеры, что у селектора профиля, чтобы подхватился ваш QSS
        self.type_box = QComboBox()
        self.type_box.addItems(CONNECTION_SCREEN.get("types", ["RTU (RS-485)", "TCP (Modbus/TCP)"]))
        self.type_box.setObjectName("ProfileCombo")  # как у селектора профиля
        self.type_box.setProperty("form", "1")       # как у полей формы
        self.type_box.setMinimumWidth(320)
        self.type_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.type_box.currentIndexChanged.connect(self._type_changed)
        type_row.addWidget(self.type_box, 1, Qt.AlignLeft)

        # «?» — подсказка внутри той же плашки
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
        type_row.addWidget(help_btn, 0, Qt.AlignLeft)
        type_row.addStretch(1)

        card_l.addLayout(type_row)

        # AlertBox ТЕПЕРЬ внутри плашки (как просил)
        self.alert = AlertBox()
        card_l.addWidget(self.alert)

        type_card_row.addWidget(self._type_card)
        type_card_row.addStretch(1)
        root.addLayout(type_card_row)

        # ---------------- SettingsPanel ----------------
        self._mount_panel(self._current_type)

        # Синхронизируем ширины плашек (после раскладки)
        QTimer.singleShot(0, self._sync_card_widths)

    # заменить панель при смене типа
    def _mount_panel(self, conn_type: str):
        if self._panel is not None:
            self.layout().removeWidget(self._panel)
            self._panel.setParent(None)
            self._panel.deleteLater()
            self._panel = None

        self._panel = SettingsPanel(
            conn_type=conn_type,
            on_back=lambda: None,
            on_connect=self._handle_connect_button
        )
        # В SettingsPanel его «карточка» обычно имеет objectName "FormCard" и центрируется самим классом.
        self.layout().addWidget(self._panel, 1)
        self._sync_connect_btn_text()

        # После замены панели — подогнать ширины
        QTimer.singleShot(0, self._sync_card_widths)

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
        # В твоём SettingsPanel кнопка называется self.connect_btn
        btn = getattr(self._panel, "connect_btn", None)
        if btn is not None:
            btn.setText("Отключить" if self._is_connected else "Подключиться")

    # Показ ошибки подключения на вложенной панели
    def show_connect_error(self, text: str):
        if self._panel is not None:
            self._panel.show_connect_error(text or "Не удалось подключиться к источнику.")

    # ---- сделать одинаковую ширину плашек (тип подключения == форма настроек) ----
    def _sync_card_widths(self):
        if self._panel is None:
            return
        # Пытаемся найти карточку формы внутри SettingsPanel
        form_card = self._panel.findChild(QWidget, "FormCard")
        if form_card is None:
            # если нет объекта по имени — используем ширину самой панели
            w = max(640, self._panel.width() or self._panel.sizeHint().width())
        else:
            # берём фактическую ширину карточки
            w = form_card.width() or form_card.sizeHint().width() or form_card.maximumWidth()
            if not w or w <= 0:
                w = 760  # запасной дефолт
        # Применяем ту же ширину и центрируем (контейнер уже центрирует)
        if w and w > 0:
            self._type_card.setFixedWidth(int(w))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._sync_card_widths()
