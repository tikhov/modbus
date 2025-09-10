from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QSizePolicy, QWidgetItem, QSpacerItem
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, Signal, QSize
import os

from resources import ASSETS_DIR

NAV_BG = "#453D31"
PRIMARY_BORDER = "#EF7F1A"


class LeftNav(QWidget):
    """
    Левая вертикальная панель навигации (1/8 ширины).
    Ключи: home, program, source, settings, info
    Активная вкладка — иконка перекрашивается в белый.
    Иконки: 90% ширины панели, нижний отступ = 1/2 высоты иконки.
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
                padding-top: 20x;
                padding-bottom: 20x;
                padding-left: 5px;
                padding-right: 5px;
                margin-left: 0px;
                margin-right: 0px;
                margin-top: 10px;
                margin-bottom: 10px;
            }}
            QToolButton[leftnav="1"]:hover {{
                background: rgba(255,255,255,0.08);
                border-radius: 10px;
            }}
            QToolButton[leftnav="1"][active="true"] {{
                background: rgba(255,255,255,0.12);
                border-radius: 10px;
            }}
        """)

        self._defs = {
            "home":     "home.svg",
            "program":  "chip.svg",
            "source":   "source_arrows.svg",
            "settings": "set.svg",
            "info":     "info.svg",
        }
        self._active = "home"

        self._items = {}   # key -> {"btn":..., "wrap":..., "spacer":...}

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 12, 10, 12)
        v.setSpacing(0)  # управляем отступами сами через спейсер
        self._layout = v

        # верхние кнопки
        for key in ("home", "program", "source", "settings"):
            self._add_nav_item(key)

        v.addStretch()

        # нижняя кнопка (инфо)
        self._add_nav_item("info")

        # сигналы
        for key in self._defs.keys():
            self._items[key]["btn"].clicked.connect(lambda _, k=key: self._on_click(k))

        self._apply_active_styles()
        self._update_icon_metrics()

    # ---------- построение ----------

    def _icon_path(self, name: str) -> str:
        p = os.path.join(ASSETS_DIR, "icons", name)
        if not os.path.exists(p) and name == "gear.svg":
            # fallback на случай отсутствия шестерёнки
            return os.path.join(ASSETS_DIR, "icons", "info.svg")
        return p

    def _add_nav_item(self, key: str):
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

        self._layout.addWidget(wrap)
        self._items[key] = {"btn": btn, "wrap": wrap, "spacer": spacer}

    # ---------- логика ----------

    def connect_slot(self, key: str):
        self._items[key]["btn"].clicked.connect(lambda: self._on_click(key))

    def _on_click(self, key: str):
        self.set_active(key)
        self.navigate.emit(key)

    def set_active(self, key: str):
        if key not in self._defs:
            return
        self._active = key
        self._apply_active_styles()
        self._update_icon_metrics()  # чтобы перерисовать активную иконку белой

    def _apply_active_styles(self):
        for k, it in self._items.items():
            it["btn"].setProperty("active", "true" if k == self._active else "false")
            it["btn"].style().unpolish(it["btn"]); it["btn"].style().polish(it["btn"])

    # перекраска SVG-иконки в белый (для активного состояния)
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
        # доступная ширина с учётом внешних отступов слева/справа = margins 10 + 10
        content_w = max(1, self.width() - 20)
        icon_size = max(16, int(content_w * 0.90))   # 90% ширины панели
        bottom_gap = icon_size // 2                  # отступ снизу = половина высоты

        for key, it in self._items.items():
            path = self._icon_path(self._defs[key])

            # активная — белая, неактивная — исходная
            if key == self._active:
                icon = self._white_icon(path, icon_size)
            else:
                icon = QIcon(path)

            btn = it["btn"]
            btn.setIcon(icon)
            btn.setIconSize(QSize(icon_size, icon_size))

            # чтобы кнопка не «зажималась» по высоте, добавим минимальную высоту = иконка
            btn.setMinimumHeight(icon_size)

            # нижний отступ
            spacer: QSpacerItem = it["spacer"]
            spacer.changeSize(0, bottom_gap)

        # перелэйаутить
        self.layout().invalidate()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_icon_metrics()

    # массовое включение/отключение вкладок
    def set_enabled_tabs(self, *, home=True, program=True, source=True, settings=True, info=True):
        self._items["home"]["btn"].setEnabled(home)
        self._items["program"]["btn"].setEnabled(program)
        self._items["source"]["btn"].setEnabled(source)
        self._items["settings"]["btn"].setEnabled(settings)
        self._items["info"]["btn"].setEnabled(info)
