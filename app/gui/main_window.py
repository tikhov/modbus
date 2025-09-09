from __future__ import annotations

import os, time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QAction, QKeySequence

from resources import ASSETS_DIR
from .connection_type_screen import ConnectionTypeScreen
from .settings_panel import SettingsPanel
from .program_screen import ProgramScreen
from .info_screen import InfoScreen
from .left_nav import LeftNav
from dictionary import HOME_SCREEN
from app.state.store import AppStore
from app.controllers.source_controller import SourceController

APP_BG = "#292116"
PRIMARY_BORDER = "#EF7F1A"
WHITE = "#FFFFFF"
ACCENT = "#EF7F1A"

BTN_STYLE = f"""
QPushButton {{
    background: {ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 700;
}}
QPushButton:hover {{ background: #ff973e; }}
QPushButton:disabled {{ background: #5c4a36; color: #b7a793; }}
"""

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

        self._is_fullscreen = False
        self.store = AppStore(self)
        self.source = SourceController(self.store, self)

        # Флаг, который принудительно меняет местами ток и напряжение ПРИ ОТОБРАЖЕНИИ
        # (независимо от того, что отдал драйвер). Включён под твой прибор.
        self._display_swap_iv = True

        self.power_state = "ready"  # "ready" | "on" | "stop"

        self._run_timer = QTimer(self)
        self._run_timer.setInterval(1000)
        self._run_timer.timeout.connect(self._tick_runtime)
        self._start_epoch = None
        self._elapsed = 0

        # слева — навигация
        self.left = LeftNav()
        self.left.navigate.connect(self._on_nav)

        # справа — стек экранов
        self.stack = QStackedWidget()
        self.stack.setObjectName("RightStack")

        self.home_widget = self._create_home_widget()               # 0
        self.program_widget = self._create_stub("Программный режим (заглушка)")  # 1
        self.connection_screen = ConnectionTypeScreen(              # 2
            on_next=self.show_settings,
            on_back=lambda: self._on_nav("home")
        )
        self.settings_panel = None
        self.info_widget = InfoScreen()                             # 3

        self.stack.addWidget(self.home_widget)
        self.stack.addWidget(self.program_widget)
        self.stack.addWidget(self.connection_screen)
        self.stack.addWidget(self.info_widget)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.left, 1)   # 1/8
        lay.addWidget(self.stack, 7)  # 7/8
        self.setCentralWidget(root)

        self._apply_main_style()

        # подписки
        self.store.connectionChanged.connect(self._on_connection_changed)
        self.store.measurementsChanged.connect(self._on_meas)

        self._apply_nav_enabled(False)
        self._on_nav("home")
        self._init_actions()  # F11

    # хоткей F11
    def _init_actions(self):
        act = QAction("Полноэкранный режим", self)
        act.setShortcut(QKeySequence("F11"))
        act.triggered.connect(self.toggle_fullscreen)
        self.addAction(act)

    def toggle_fullscreen(self):
        if self._is_fullscreen:
            self.showNormal(); self._is_fullscreen = False
        else:
            self.showFullScreen(); self._is_fullscreen = True

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F11: self.toggle_fullscreen()
        else: super().keyPressEvent(e)

    def _apply_main_style(self):
        self.stack.setStyleSheet(f"QWidget#RightStack {{ background: {APP_BG}; border-left: 3px solid {PRIMARY_BORDER}; }}")

    def _create_stub(self, text: str) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(24,24,24,24); v.addStretch()
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet("color:#fff;font-size:16px;")
        v.addWidget(lbl); v.addStretch(); return w

    def _create_home_widget(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(24,24,24,24); v.setSpacing(16)

        # крупные показания
        self.lbl_voltage = QLabel("0,0 В"); self.lbl_current = QLabel("0,0 А")
        for l in (self.lbl_voltage, self.lbl_current): l.setAlignment(Qt.AlignCenter)
        self.lbl_voltage.setStyleSheet(f"color:{WHITE}; font-size:180px; font-weight:800;")
        self.lbl_current.setStyleSheet(f"color:{ACCENT}; font-size:160px; font-weight:800;")

        v.addStretch(); v.addWidget(self.lbl_voltage); v.addWidget(self.lbl_current); v.addStretch()

        # нижняя полоса
        self.bottom_container = QWidget()
        bottom = QHBoxLayout(self.bottom_container); bottom.setSpacing(40); bottom.setContentsMargins(20,20,20,20)

        chip = icon_label("chip.svg", 72); lbl_prog = QLabel("Программа 1"); lbl_prog.setStyleSheet("color:#fff;font-size:42px;")
        bottom.addWidget(chip); bottom.addWidget(lbl_prog); bottom.addSpacing(60)

        sand = icon_label("hourglass.svg", 72); self.lbl_timer = QLabel("00:00:00"); self.lbl_timer.setStyleSheet("color:#fff;font-size:42px;")
        bottom.addWidget(sand); bottom.addWidget(self.lbl_timer); bottom.addSpacing(60)

        ah = icon_label("ah.svg", 72); self.lbl_ah = QLabel("0 А·ч"); self.lbl_ah.setStyleSheet("color:#fff;font-size:42px;")
        bottom.addWidget(ah); bottom.addWidget(self.lbl_ah); bottom.addSpacing(60)

        # индикатор/кнопка питания — ИКОНКА
        self.btn_power = QPushButton()
        self.btn_power.setCursor(Qt.PointingHandCursor)
        self.btn_power.setStyleSheet("""
            QPushButton { background: none; border: none; border-radius: 16px; }
            QPushButton:hover { background: rgba(255,255,255,0.08); }
            QPushButton:disabled { background: none; }
        """)
        self.btn_power.setIconSize(QSize(96, 96))
        self.btn_power.clicked.connect(self._toggle_power)
        self._update_power_icon()

        bottom.addStretch(); bottom.addWidget(self.btn_power)
        v.addWidget(self.bottom_container)

        # центр — «Подключиться» для оффлайна
        self.center_box = QWidget(); cbx = QVBoxLayout(self.center_box); cbx.setContentsMargins(0,0,0,0)
        cbx.addStretch(); self.btn_connect_big = QPushButton(HOME_SCREEN["connect_btn"]); self.btn_connect_big.setMinimumHeight(48)
        self.btn_connect_big.setStyleSheet(BTN_STYLE); self.btn_connect_big.setCursor(Qt.PointingHandCursor)
        self.btn_connect_big.clicked.connect(lambda: self._on_nav("source")); cbx.addWidget(self.btn_connect_big, alignment=Qt.AlignHCenter)
        cbx.addStretch(); v.addWidget(self.center_box, 1)

        self._apply_connected_ui(False)
        return w

    # навигация
    def _on_nav(self, key: str):
        mapping = {"home": 0, "program": 1, "source": 2, "settings": 2, "info": 3}
        self.left.set_active(key)
        self.stack.setCurrentIndex(mapping.get(key, 0))

    def show_settings(self, conn_type: str):
        self.settings_panel = SettingsPanel(
            conn_type=conn_type,
            on_back=lambda: self._on_nav("source"),
            on_connect=self.on_connect
        )
        idx = self.stack.indexOf(self.connection_screen)
        self.stack.insertWidget(idx + 1, self.settings_panel)
        self.stack.setCurrentWidget(self.settings_panel)
        self.left.set_active("settings")

    # подключение/состояние
    def on_connect(self, conn_type: str, settings: dict):
        ok = self.source.connect(conn_type, settings)
        if ok:
            self._start_epoch = time.time(); self._elapsed = 0; self._run_timer.start()
            self._apply_nav_enabled(True); self._apply_connected_ui(True)
            self.power_state = "ready"; self._update_power_icon()
            self._on_nav("home")
        else:
            err = getattr(self.store, "last_error", None) or "Не удалось подключиться. Проверьте параметры."
            if self.settings_panel:
                self.stack.setCurrentWidget(self.settings_panel)
                self.settings_panel.show_connect_error(err)

    def _on_connection_changed(self, connected: bool):
        if not connected:
            self._run_timer.stop(); self._start_epoch = None; self._elapsed = 0
            self.lbl_timer.setText("00:00:00"); self.power_state = "ready"; self._update_power_icon()
            self._apply_nav_enabled(False); self._apply_connected_ui(False)

    def _apply_nav_enabled(self, connected: bool):
        self.left.set_enabled_tabs(home=True, program=connected, source=connected, settings=connected, info=True)

    def _apply_connected_ui(self, connected: bool):
        self.lbl_voltage.setVisible(connected)
        self.lbl_current.setVisible(connected)
        self.bottom_container.setVisible(connected)
        self.center_box.setVisible(not connected)

    # измерения/таймер
    def _on_meas(self, meas):
        try:
            v = float(meas.voltage)
            i = float(meas.current)

            # >>> ЖЁСТКО: меняем местами для отображения, если требуется <<<
            if self._display_swap_iv:
                v, i = i, v

            # формат: одна десятая + запятая
            self.lbl_voltage.setText(f"{v:+.1f} В".replace("+", "").replace(".", ","))
            self.lbl_current.setText(f"{i:.1f} А".replace(".", ","))

            self.lbl_ah.setText(f"{int(meas.ah_counter)} А·ч")

            # Логика состояния оценивает уже «правильные» (после свопа) значения
            if getattr(meas, "error_overheat", False) or getattr(meas, "error_mains", False):
                self.power_state = "stop"
            else:
                if abs(i) > 0 or abs(v) > 0:
                    self.power_state = "on"
                else:
                    self.power_state = "ready"
            self._update_power_icon()
        except Exception:
            self.lbl_voltage.setText("0,0 В"); self.lbl_current.setText("0,0 А"); self.lbl_ah.setText("0 А·ч")

    def _tick_runtime(self):
        if self._start_epoch is None: return
        self._elapsed = int(time.time() - self._start_epoch)
        h = self._elapsed // 3600; m = (self._elapsed % 3600) // 60; s = self._elapsed % 60
        self.lbl_timer.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # индикатор питания
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
        # Оптимистично меняем иконку, но откатим, если запись не удастся
        self.power_state = "on" if want_on else "ready"; self._update_power_icon()

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
