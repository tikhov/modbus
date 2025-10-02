from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QToolButton, QSizePolicy, QSpacerItem
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, Signal, QSize, QTimer
import os
from resources import ASSETS_DIR

NAV_BG = "#453D31"
PRIMARY_BORDER = "#EF7F1A"
LOCK_BG = "#292116"
LOCK_BORDER = "#EF7F1A"


class LeftNav(QWidget):
    """
    Левая вертикальная панель навигации.
    Ключи: home, program, source, settings, info, lock
    """
    navigate = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LeftNav")
        self.setStyleSheet(f"""
            QWidget#LeftNav {{
                background: {NAV_BG};
                border-right: 3px solid {PRIMARY_BORDER};
            }}
            QToolButton[leftnav="1"] {{
                background: transparent;
                border: none;
                padding: 20px 5px;
                margin: 10px 0px;
            }}
            QToolButton[leftnav="1"]:hover {{
                background: rgba(255,255,255,0.08);
                border-radius: 10px;
            }}
            QToolButton[leftnav="1"][active="true"] {{
                background: rgba(255,255,255,0.12);
                border-radius: 10px;
            }}
            QWidget[lock_wrap="true"] {{
                background: {LOCK_BG};
                border-top: 3px solid {LOCK_BORDER};
                padding-top: 10px;
                margin-bottom: 0px;
                padding: 0px;
            }}
            QWidget[lock_wrap="true"] QToolButton {{
                background: transparent;
                border: none;
                padding: 0px;
                margin: 15px;
            }}
        """)

        self._defs = {
            "home":     "home.svg",
            "program":  "chip.svg",
            "source":   "source_arrows.svg",
            "settings": "list.svg",
            "info":     "info.svg",
            "lock":     "lock.svg",
        }

        self._active = "home"
        self._locked = False
        self._items = {}
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_timeout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 12, 0, 0)
        main_layout.setSpacing(0)

        # Верхние кнопки
        for key in ("home", "program", "source", "settings"):
            self._add_nav_item(key, main_layout)
        main_layout.addStretch()
        # Кнопка info
        self._add_nav_item("info", main_layout)
        # Кнопка lock
        self._lock_icon_locked = os.path.join(ASSETS_DIR, "icons", "lock.svg")
        self._lock_icon_unlocked = os.path.join(ASSETS_DIR, "icons", "unlock.svg")
        self._add_lock_item(main_layout)

        # Подключение сигналов
        for key in ("home", "program", "source", "settings", "info"):
            self._items[key]["btn"].clicked.connect(lambda _, k=key: self._on_click(k))

        self._lock_btn.pressed.connect(self._on_lock_pressed)
        self._lock_btn.released.connect(self._on_lock_released)

        self._apply_active_styles()
        self._update_icon_metrics()

    def _icon_path(self, name: str) -> str:
        return os.path.join(ASSETS_DIR, "icons", name)

    def _add_nav_item(self, key: str, layout):
        wrap = QWidget(self)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        btn.setProperty("leftnav", "1")
        btn.setProperty("active", "false")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setAutoRaise(True)
        btn.setIcon(QIcon(self._icon_path(self._defs[key])))
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Fixed)
        lay.addWidget(btn, alignment=Qt.AlignHCenter | Qt.AlignVCenter)
        lay.addItem(spacer)
        layout.addWidget(wrap)
        self._items[key] = {"btn": btn, "wrap": wrap, "spacer": spacer}

    def _add_lock_item(self, layout):
        wrap = QWidget(self)
        wrap.setProperty("lock_wrap", "true")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._lock_btn = QToolButton()
        self._lock_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._lock_btn.setCursor(Qt.PointingHandCursor)
        self._lock_btn.setAutoRaise(True)
        self._lock_btn.setIcon(QIcon(self._icon_path("lock.svg")))
        self._lock_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self._lock_btn, alignment=Qt.AlignCenter)

        layout.addWidget(wrap)
        self._items["lock"] = {"btn": self._lock_btn, "wrap": wrap}

    # ---------- блокировка ----------
    def _on_lock_pressed(self):
        lock_path = self._icon_path("lock.svg")
        if not self._locked:
            # короткое нажатие → блокировка
            self.lock_ui()
            self._lock_btn.setIcon(QIcon(lock_path))
        else:
            # если уже заблокировано — ждём удержания
            self._hold_timer.start(1000)


    def _on_lock_released(self):
        if self._hold_timer.isActive():
            self._hold_timer.stop()

    def _on_hold_timeout(self):
        if self._locked:
            self._locked = False
            # self._apply_active_styles()
            self._update_icon_metrics()
            # self.navigate.emit("unlock")

    def _on_click(self, key: str):
        if self._locked:
            return
        self.set_active(key)
        self.navigate.emit(key)

    def set_active(self, key: str):
        if key not in self._defs or self._locked or key == "lock" or key == "program":
            return
        self._active = key
        self._apply_active_styles()
        self._update_icon_metrics()

    def _apply_active_styles(self):
        for k in ("home", "program", "source", "settings", "info"):
            is_active = (k == self._active) and not self._locked
            btn = self._items[k]["btn"]
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _white_icon(self, path: str, size: int) -> QIcon:
        base = QIcon(path).pixmap(size, size)
        pm = QPixmap(base.size())
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.drawPixmap(0, 0, base)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(pm.rect(), QColor("#FFFFFF"))
        p.end()
        return QIcon(pm)

    def _update_icon_metrics(self):
        content_w = max(1, self.width() - 20)
        icon_size = max(16, int(content_w * 0.80))
        bottom_gap = icon_size // 2

        for key in ("home", "program", "source", "settings", "info"):
            path = self._icon_path(self._defs[key])
            btn = self._items[key]["btn"]
            icon = self._white_icon(path, icon_size) if (key == self._active and not self._locked) else QIcon(path)
            btn.setIcon(icon)
            btn.setIconSize(QSize(icon_size, icon_size))
            btn.setMinimumHeight(icon_size)
            spacer = self._items[key]["spacer"]
            spacer.changeSize(0, bottom_gap)

        # lock
        lock_icon_size = int(icon_size * 0.9)
        unlock_path = self._icon_path("unlock.svg")
        lock_path = self._icon_path("lock.svg")
        self._lock_btn.setIcon(QIcon(lock_path) if self._locked else QIcon(unlock_path))
        self._lock_btn.setIconSize(QSize(lock_icon_size, lock_icon_size))

        self.layout().invalidate()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_icon_metrics()

    def set_enabled_tabs(self, *, home=True, program=True, source=True, settings=True, info=True, lock=True):
        self._items["home"]["btn"].setEnabled(home and not self._locked)
        self._items["program"]["btn"].setEnabled(program and not self._locked)
        self._items["source"]["btn"].setEnabled(source and not self._locked)
        self._items["settings"]["btn"].setEnabled(settings and not self._locked)
        self._items["info"]["btn"].setEnabled(info and not self._locked)
        self._lock_btn.setEnabled(lock)

    def is_locked(self) -> bool:
        return self._locked

    def lock_ui(self):
        if not self._locked:
            self._locked = True
            # self._lock_btn.setIcon(QIcon(self._lock_icon_locked))  # меняем иконку
            # self._apply_active_styles()
            # self._update_icon_metrics()
            # self.navigate.emit("lock")

    def unlock_ui(self):
        if self._locked:
            self._locked = False
            # self._lock_btn.setIcon(QIcon(self._lock_icon_unlocked))
            # self._apply_active_styles()
            # self._update_icon_metrics()
            # self.navigate.emit("unlock")
