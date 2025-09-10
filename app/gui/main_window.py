from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton
)

from resources import ASSETS_DIR
from dictionary import HOME_SCREEN
from .left_nav import LeftNav
from .program_screen import ProgramScreen
from .connection_tab import ConnectionTab
from .settings_screen import SettingsScreen
from .info_screen import InfoScreen

from app.state.store import AppStore
from app.controllers.source_controller import SourceController


APP_BG = "#292116"
PRIMARY_BORDER = "#EF7F1A"
WHITE = "#FFFFFF"
ACCENT = "#EF7F1A"


def icon_label(name: str, size: int = 24) -> QLabel:
    lbl = QLabel()
    p = os.path.join(ASSETS_DIR, "icons", name)
    ico = QIcon(p)
    lbl.setPixmap(ico.pixmap(size, size))
    return lbl


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Power Source Controller")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 650)

        # Сервисы
        self.store = AppStore(self)
        self.source = SourceController(self.store, self)

        # Состояния экрана
        self._is_fullscreen = False
        self._display_swap_iv = False
        self.power_state = "ready"     # "ready" | "on" | "stop"

        # Таймер «времени работы»
        self._run_timer = QTimer(self)
        self._run_timer.setInterval(1000)
        self._run_timer.timeout.connect(self._tick_runtime)
        self._start_epoch: float | None = None
        self._elapsed = 0

        # Левая панель навигации
        self.left = LeftNav()
        self.left.navigate.connect(self._on_nav)

        # Правая часть — стек всех вкладок
        self.stack = QStackedWidget()
        self.stack.setObjectName("RightStack")

        # Вкладки
        self.home_widget = self._create_home_widget()     # 0 — Домик
        self.program_widget = ProgramScreen()             # 1 — Программный режим (заглушка)
        self.connection_tab = ConnectionTab(              # 2 — Подключение (селектор + SettingsPanel)
            on_connect=self.on_connect
        )
        self.settings_screen = SettingsScreen()           # 3 — Настройки (заглушка)
        self.info_widget = InfoScreen()                   # 4 — Инфо

        for w in (self.home_widget, self.program_widget, self.connection_tab, self.settings_screen, self.info_widget):
            self.stack.addWidget(w)

        # --- ВЕРТИКАЛЬНЫЙ РАЗДЕЛИТЕЛЬ (гарантированная линия) ---
        self.divider = QWidget()
        self.divider.setFixedWidth(3)
        self.divider.setStyleSheet(f"background: {PRIMARY_BORDER};")

        # Корневой лэйаут
        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.left, 1)   # ~1/8
        lay.addWidget(self.divider)   # линия между навигацией и контентом
        lay.addWidget(self.stack, 7)  # ~7/8
        self.setCentralWidget(root)

        self._apply_main_style()

        # Сигналы стора
        self.store.connectionChanged.connect(self._on_connection_changed)
        self.store.measurementsChanged.connect(self._on_meas)

        # Все вкладки активны сразу
        self._apply_nav_enabled(True)

        # Навигация на домашнюю
        self._on_nav("home")

        # Горячая клавиша F11
        self._init_actions()

    # ---------- хоткеи ----------
    def _init_actions(self):
        act = QAction("Полноэкранный режим", self)
        act.setShortcut(QKeySequence("F11"))
        act.triggered.connect(self.toggle_fullscreen)
        self.addAction(act)

    def toggle_fullscreen(self):
        if self._is_fullscreen:
            self.showNormal()
            self._is_fullscreen = False
        else:
            self.showFullScreen()
            self._is_fullscreen = True

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F11:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(e)

    # ---------- стили ----------
    def _apply_main_style(self):
        # Границу на правой области НЕ ставим, её роль берёт на себя self.divider.
        self.stack.setStyleSheet(f"QWidget#RightStack {{ background: {APP_BG}; }}")

    # ---------- построение Домика ----------
    def _create_home_widget(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(16)

        # Титульная надпись
        title = QLabel(HOME_SCREEN.get("title", ""))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; color: #fff;")
        v.addWidget(title)

        # Крупные показания
        self.lbl_voltage = QLabel("0,0 В")
        self.lbl_current = QLabel("0,0 А")
        for l in (self.lbl_voltage, self.lbl_current):
            l.setAlignment(Qt.AlignCenter)
        self.lbl_voltage.setStyleSheet(f"color:{WHITE}; font-size:180px; font-weight:800;")
        self.lbl_current.setStyleSheet(f"color:{ACCENT}; font-size:160px; font-weight:800;")

        v.addStretch()
        v.addWidget(self.lbl_voltage)
        v.addWidget(self.lbl_current)
        v.addStretch()

        # Большая кнопка «Подключиться» (видна только при отсутствии подключения)
        cbx = QVBoxLayout()
        self.btn_connect_big = QPushButton(HOME_SCREEN.get("connect_btn", "Подключиться"))
        self.btn_connect_big.setMinimumHeight(48)
        self.btn_connect_big.setStyleSheet(
            "font-size: 16px; padding: 10px 18px; font-weight: 700; "
            "background: #EF7F1A; color: #fff; border: none; border-radius: 8px;"
        )
        self.btn_connect_big.clicked.connect(lambda: self._on_nav("source"))
        cbx.addWidget(self.btn_connect_big, alignment=Qt.AlignHCenter)
        cbx.setContentsMargins(0, 0, 0, 0)
        v.addLayout(cbx)

        # Нижняя панель (видна только при подключении)
        self.bottom_container = QWidget()
        bottom = QHBoxLayout(self.bottom_container)
        bottom.setSpacing(40)
        bottom.setContentsMargins(20, 20, 20, 20)

        # Программа
        chip = icon_label("chip.svg", 72)
        lbl_prog = QLabel("Программа 1")
        lbl_prog.setStyleSheet("color:#fff; font-size:42px;")
        bottom.addWidget(chip)
        bottom.addWidget(lbl_prog)
        bottom.addSpacing(60)

        # Время работы
        sand = icon_label("hourglass.svg", 72)
        self.lbl_timer = QLabel("00:00:00")
        self.lbl_timer.setStyleSheet("color:#fff; font-size:42px;")
        bottom.addWidget(sand)
        bottom.addWidget(self.lbl_timer)
        bottom.addSpacing(60)

        # Ампер-часы
        ah = icon_label("ah.svg", 72)
        self.lbl_ah = QLabel("0 А·ч")
        self.lbl_ah.setStyleSheet("color:#fff; font-size:42px;")
        bottom.addWidget(ah)
        bottom.addWidget(self.lbl_ah)
        bottom.addSpacing(60)

        # Кнопка-индикатор питания (иконка)
        self.btn_power = QPushButton()
        self.btn_power.setCursor(Qt.PointingHandCursor)
        self.btn_power.setStyleSheet(
            "QPushButton { background: none; border: none; border-radius: 16px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.08); }"
            "QPushButton:disabled { background: none; }"
        )
        self.btn_power.setIconSize(QSize(96, 96))
        self.btn_power.clicked.connect(self._toggle_power)
        self._update_power_icon()

        bottom.addStretch()
        bottom.addWidget(self.btn_power)

        v.addWidget(self.bottom_container)

        # Стартовое состояние (нет подключения)
        self._apply_connected_ui(False)

        return w

    # ---------- навигация ----------
    def _on_nav(self, key: str):
        mapping = {"home": 0, "program": 1, "source": 2, "settings": 3, "info": 4}
        self.left.set_active(key)
        self.stack.setCurrentIndex(mapping.get(key, 0))

    def _apply_nav_enabled(self, connected: bool):
        # По ТЗ — все вкладки активны всегда
        self.left.set_enabled_tabs(home=True, program=True, source=True, settings=True, info=True)

    # ---------- подключение ----------
    def on_connect(self, conn_type: str, settings: dict):
        ok = self.source.connect(conn_type, settings)
        if ok:
            # Подключились — запускаем таймер, но источник НЕ включаем автоматически
            self._start_epoch = time.time()
            self._elapsed = 0
            self._run_timer.start()
            self.power_state = "ready"
            self._update_power_icon()
            self.btn_power.setEnabled(True)
            self._apply_connected_ui(True)
            self._on_nav("home")
        else:
            # Ошибка — показать алерт на вкладке «Подключение»
            err = getattr(self.store, "last_error", None) or "Не удалось подключиться. Проверьте параметры."
            self.stack.setCurrentWidget(self.connection_tab)
            self.connection_tab.show_connect_error(err)

    def _on_connection_changed(self, connected: bool):
        if not connected:
            # Сброс UI
            self._run_timer.stop()
            self._start_epoch = None
            self._elapsed = 0
            self.lbl_timer.setText("00:00:00")
            self.power_state = "ready"
            self._update_power_icon()
            self.lbl_voltage.setText("0,0 В")
            self.lbl_current.setText("0,0 А")
            self.lbl_ah.setText("0 А·ч")
            self.btn_power.setEnabled(False)
            self._apply_connected_ui(False)

    # ---------- синхронизация вида по подключению ----------
    def _apply_connected_ui(self, connected: bool):
        if hasattr(self, "btn_connect_big"):
            self.btn_connect_big.setVisible(not connected)
        if hasattr(self, "bottom_container"):
            self.bottom_container.setVisible(connected)
        # вкладки включены всегда
        self._apply_nav_enabled(connected)

    # ---------- показания ----------
    def _on_meas(self, meas):
        try:
            v = float(meas.voltage)
            i = float(meas.current)

            if self._display_swap_iv:
                v, i = i, v

            self.lbl_voltage.setText(f"{v:+.1f} В".replace("+", "").replace(".", ","))
            self.lbl_current.setText(f"{i:.1f} А".replace(".", ","))
            self.lbl_ah.setText(f"{int(meas.ah_counter)} А·ч")

            if getattr(meas, "error_overheat", False) or getattr(meas, "error_mains", False):
                self.power_state = "stop"
            else:
                if abs(i) > 0 or abs(v) > 0:
                    self.power_state = "on"
                else:
                    self.power_state = "ready"
            self._update_power_icon()
            self.btn_power.setEnabled(True)
        except Exception:
            self.lbl_voltage.setText("0,0 В")
            self.lbl_current.setText("0,0 А")
            self.lbl_ah.setText("0 А·ч")

    # ---------- таймер ----------
    def _tick_runtime(self):
        if self._start_epoch is None:
            return
        self._elapsed = int(time.time() - self._start_epoch)
        h = self._elapsed // 3600
        m = (self._elapsed % 3600) // 60
        s = self._elapsed % 60
        self.lbl_timer.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # ---------- индикатор питания и клик ----------
    def _update_power_icon(self):
        name = {
            "ready": "state_ready_yellow_triangle.svg",
            "on":    "state_on_green_power.svg",
            "stop":  "state_stop_red.svg",
        }.get(self.power_state, "state_ready_yellow_triangle.svg")
        self.btn_power.setIcon(QIcon(os.path.join(ASSETS_DIR, "icons", name)))

    def _toggle_power(self):
        want_on = True if self.power_state in ("ready", "stop") else False
        old_state = self.power_state
        self.power_state = "on" if want_on else "ready"
        self._update_power_icon()

        ok = False
        try:
            ok = bool(self.source.set_power(want_on))
        except Exception:
            ok = False

        if not ok and hasattr(self.source, "driver") and self.source.driver:
            try:
                ok1 = bool(self.source.driver.set_device_power(want_on))
                ok2 = bool(self.source.driver.set_inverter_enable(want_on))
                ok = ok1 and ok2
            except Exception:
                ok = False

        if not ok:
            self.power_state = old_state
            self._update_power_icon()
