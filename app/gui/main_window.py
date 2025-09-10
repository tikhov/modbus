from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QApplication
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
TITLE_BAR_BG = "#1E1E1E"   # фон полосы заголовка (внизу)
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
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect
        )
        self.settings_screen = SettingsScreen()           # 3 — Настройки (заглушка)
        self.info_widget = InfoScreen()                   # 4 — Инфо

        for w in (self.home_widget, self.program_widget, self.connection_tab, self.settings_screen, self.info_widget):
            self.stack.addWidget(w)

        # --- ВЕРТИКАЛЬНЫЙ РАЗДЕЛИТЕЛЬ (оранжевая линия) ---
        self.divider = QWidget()
        self.divider.setFixedWidth(3)
        self.divider.setStyleSheet(f"background: {PRIMARY_BORDER};")

        # -------- Корневой контейнер: горизонтальный (лево: нав, середина: бордер, право: контент) --------
        root = QWidget()
        root_h = QHBoxLayout(root)
        root_h.setContentsMargins(0, 0, 0, 0)
        root_h.setSpacing(0)

        # Правая колонка: контент + ПОЛОСА ЗАГОЛОВКА ВНИЗУ
        right_panel = QWidget()
        right_v = QVBoxLayout(right_panel)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(0)

        # Стек контента (занимает всё сверху)
        right_v.addWidget(self.stack, 1)

        # Полоса названия активной вкладки (ТОЛЬКО в правой области, ВНИЗУ, высота 60)
        self.tab_title_bar = QWidget()
        self.tab_title_bar.setFixedHeight(60)
        self.tab_title_bar.setStyleSheet(f"background: {TITLE_BAR_BG};")
        title_lay = QHBoxLayout(self.tab_title_bar)
        title_lay.setContentsMargins(16, 0, 16, 0)
        title_lay.setSpacing(0)

        self.tab_title_label = QLabel("")  # задаём текст в _on_nav
        self.tab_title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.tab_title_label.setStyleSheet("color: #FFFFFF; font-size: 30px; font-weight: 800;")
        title_lay.addWidget(self.tab_title_label)

        right_v.addWidget(self.tab_title_bar, 0)

        # Собираем всё вместе
        root_h.addWidget(self.left, 1)    # ~1/8
        root_h.addWidget(self.divider)    # бордер
        root_h.addWidget(right_panel, 7)  # ~7/8

        self.setCentralWidget(root)
        self._apply_main_style()

        # ---- Статус-бар подключения ----
        sb = self.statusBar()
        sb.setStyleSheet("QStatusBar{background:#1f1a12;color:#fff;} QLabel{color:#fff;}")
        self._status_label = QLabel("")
        sb.addWidget(self._status_label, 1)  # растягиваем на ширину окна
        self._status_anim_timer = QTimer(self)
        self._status_anim_timer.setInterval(400)
        self._status_anim_timer.timeout.connect(self._animate_status_dots)
        self._status_mode = "disconnected"    # connected | connecting | reconnecting | error | disconnected
        self._status_dots = 0
        self._status_text_base = "Отключено"
        self._render_status("Отключено", color="#bdc3c7")

        # Флаг выполнения подключения (чтобы не запускать повторно)
        self._connect_job_active = False
        self._pending_conn: tuple[str, dict] | None = None

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
        self.stack.setStyleSheet(f"QWidget#RightStack {{ background: {APP_BG}; }}")

    # ---------- построение Домика ----------
    def _create_home_widget(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(16)

        # Титульная надпись/подсказка: скрываем при подключении
        self.lbl_home_hint = QLabel(HOME_SCREEN.get("title", ""))
        self.lbl_home_hint.setAlignment(Qt.AlignCenter)
        self.lbl_home_hint.setStyleSheet("font-size: 18px; color: #fff;")
        v.addWidget(self.lbl_home_hint)

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
        titles = {
            "home": "Домашний экран",
            "program": "Программный режим",
            "source": "Подключение к источнику",
            "settings": "Настройки",
            "info": "Информация",
        }
        self.left.set_active(key)
        self.stack.setCurrentIndex(mapping.get(key, 0))
        # обновить надпись в полосе названия вкладки (внизу)
        self.tab_title_label.setText(titles.get(key, ""))

    def _apply_nav_enabled(self, connected: bool):
        self.left.set_enabled_tabs(home=True, program=True, source=True, settings=True, info=True)

    # ---------- подключение / отключение ----------
    def on_connect(self, conn_type: str, settings: dict):
        if self._connect_job_active:
            return
        self._connect_job_active = True
        self._pending_conn = (conn_type, settings)

        # Показать активность «Подключение…» и ПРОРИСОВАТЬ немедленно
        self._set_status("connecting", "Подключение")
        QApplication.processEvents()

        QTimer.singleShot(0, self._do_connect)

    def _do_connect(self):
        try:
            conn_type, settings = self._pending_conn or ("RTU", {})
            ok = self.source.connect(conn_type, settings)
            if ok:
                self._start_epoch = time.time()
                self._elapsed = 0
                self._run_timer.start()
                self.power_state = "ready"
                self._update_power_icon()
                self.btn_power.setEnabled(True)
                self._apply_connected_ui(True)
                self.connection_tab.set_connected(True)
                self._on_nav("home")
                self._set_status("connected", f"Подключено ({conn_type})")
            else:
                err = getattr(self.store, "last_error", None) or "Не удалось подключиться. Проверьте параметры."
                self.stack.setCurrentWidget(self.connection_tab)
                self.connection_tab.show_connect_error(err)
                self._set_status("error", f"Ошибка подключения: {err}")
        finally:
            self._connect_job_active = False
            self._pending_conn = None

    def on_disconnect(self):
        try:
            if hasattr(self.source, "disconnect"):
                self.source.disconnect()
        finally:
            self._run_timer.stop()
            self._start_epoch = None
            self._elapsed = 0
            self._apply_connected_ui(False)
            self.connection_tab.set_connected(False)
            self._set_status("disconnected", "Отключено")

    def _on_connection_changed(self, connected: bool):
        if not connected:
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
            self.connection_tab.set_connected(False)
            self._set_status("reconnecting", "Переподключение")
        else:
            self.connection_tab.set_connected(True)
            self._set_status("connected", "Подключено")

    # ---------- синхронизация вида по подключению ----------
    def _apply_connected_ui(self, connected: bool):
        if hasattr(self, "lbl_home_hint"):
            self.lbl_home_hint.setVisible(not connected)

        if hasattr(self, "btn_connect_big"):
            self.btn_connect_big.setVisible(not connected)
        if hasattr(self, "bottom_container"):
            self.bottom_container.setVisible(connected)

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

    # ---------- статус-бар ----------
    def _render_status(self, text: str, color: str):
        dot = f'<span style="color:{color};">●</span>'
        self._status_label.setText(f'{dot} {text}')

    def _set_status(self, mode: str, base_text: str):
        mode_changed = (mode != self._status_mode)
        self._status_mode = mode
        if mode_changed:
            self._status_dots = 0
        self._status_text_base = base_text

        color = {
            "connected": "#27ae60",
            "connecting": "#f1c40f",
            "reconnecting": "#f1c40f",
            "error": "#e74c3c",
            "disconnected": "#bdc3c7",
        }.get(mode, "#bdc3c7")

        if mode in ("connecting", "reconnecting"):
            if not self._status_anim_timer.isActive():
                self._status_anim_timer.start()
        else:
            if self._status_anim_timer.isActive():
                self._status_anim_timer.stop()

        text = self._status_text_base
        if mode in ("connecting", "reconnecting"):
            text += "." * max(1, self._status_dots or 1)
        self._render_status(text, color)

    def _animate_status_dots(self):
        # 1 -> 2 -> 3 -> 1
        self._status_dots = (self._status_dots % 3) + 1
        color = {
            "connecting": "#f1c40f",
            "reconnecting": "#f1c40f",
        }.get(self._status_mode, "#bdc3c7")
        text = self._status_text_base + ("." * self._status_dots)
        self._render_status(text, color)
