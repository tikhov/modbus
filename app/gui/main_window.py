from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QApplication, QToolTip
)

from resources import ASSETS_DIR
from dictionary import HOME_SCREEN
from .left_nav import LeftNav
from .program_screen import ProgramScreen
from .connection_tab import ConnectionTab
from .settings_screen import SourceTableWidget
from .info_screen import InfoScreen

from app.state.store import AppStore
from app.controllers.source_controller import SourceController
from .source_header import SourceHeaderWidget

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
        self.setMinimumSize(1000, 650)

        # Сервисы
        self.store = AppStore(self)
        self.source = SourceController(self.store, self)

        # Состояния экрана
        self._is_fullscreen = True
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
        self.left.navigate.connect(self._on_left_nav_event)   # слушаем lock/unlock

        # Правая часть — стек всех вкладок
        self.stack = QStackedWidget()
        self.stack.setObjectName("RightStack")

        # Вкладки
        self.home_widget = self._create_home_widget()     # 0 — Домик
        self.program_widget = ProgramScreen()             # 1 — Программный режим
        self.connection_tab = ConnectionTab(              # 2 — Подключение
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect
        )
        self.settings_screen = SourceTableWidget(source_controller=self.source)           # 3 — Настройки
        self.info_widget = InfoScreen()                   # 4 — Инфо

        for w in (self.home_widget, self.program_widget, self.connection_tab,
                  self.settings_screen, self.info_widget):
            self.stack.addWidget(w)

        # --- ВЕРТИКАЛЬНЫЙ РАЗДЕЛИТЕЛЬ ---
        self.divider = QWidget()
        self.divider.setFixedWidth(3)
        self.divider.setStyleSheet(f"background: {PRIMARY_BORDER};")

        # -------- Правая колонка: контент + полоска заголовка --------
        self.right_panel = QWidget()
        right_v = QVBoxLayout(self.right_panel)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(0)

        right_v.addWidget(self.stack, 1)

        self.tab_title_bar = QWidget()
        self.tab_title_bar.setFixedHeight(60)
        self.tab_title_bar.setStyleSheet(f"background: {TITLE_BAR_BG};")
        title_lay = QHBoxLayout(self.tab_title_bar)
        title_lay.setContentsMargins(16, 0, 16, 0)
        self.tab_title_label = QLabel("")
        self.tab_title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.tab_title_label.setStyleSheet("color: #FFFFFF; font-size: 30px; font-weight: 800;")
        title_lay.addWidget(self.tab_title_label)
        right_v.addWidget(self.tab_title_bar, 0)

        # --- Overlay блокировки ---
        self.overlay = QWidget(self.right_panel)
        self.overlay.setStyleSheet("background: transparent;")
        self.overlay.hide()

        # -------- Собираем всё вместе --------
        root = QWidget()
        root_h = QHBoxLayout(root)
        root_h.setContentsMargins(0, 0, 0, 0)
        root_h.setSpacing(0)

        root_h.addWidget(self.left, 1)
        root_h.addWidget(self.divider)
        root_h.addWidget(self.right_panel, 7)

        self.setCentralWidget(root)
        self._apply_main_style()

        # ---- Статус-бар подключения ----
        sb = self.statusBar()
        sb.setStyleSheet("QStatusBar{background:#1f1a12;color:#fff;} QLabel{color:#fff;}")
        self._status_label = QLabel("")
        self._btn_copy_err = QPushButton("📋")
        self._btn_copy_err.setToolTip("Скопировать текст ошибки")
        self._btn_copy_err.setVisible(False)
        self._btn_copy_err.setCursor(Qt.PointingHandCursor)
        self._btn_copy_err.setStyleSheet(
            "QPushButton { border:none; color:#fff; font-size:16px; padding:2px 6px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.12); border-radius:6px; }"
        )
        sb.addPermanentWidget(self._btn_copy_err, 0)
        self._last_status_error = ""
        self._btn_copy_err.clicked.connect(lambda: QApplication.clipboard().setText(self._last_status_error or ""))
        sb.addWidget(self._status_label, 1)

        self._status_anim_timer = QTimer(self)
        self._status_anim_timer.setInterval(400)
        self._status_anim_timer.timeout.connect(self._animate_status_dots)
        self._status_mode = "disconnected"
        self._status_dots = 0
        self._status_text_base = "Отключено"
        self._render_status("Отключено", color="#bdc3c7")

        self._connect_job_active = False
        self._pending_conn: tuple[str, dict] | None = None

        # Сигналы стора
        self.store.connectionChanged.connect(self._on_connection_changed)
        self.store.measurementsChanged.connect(self._on_meas)
        self.source_table = SourceTableWidget(self.source)
        self.stack.addWidget(self.source_table)

        # Все вкладки активны
        self._apply_nav_enabled(True)
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

    # ---------- overlay ----------
    def _on_left_nav_event(self, key: str):
        if key == "lock":
            self._show_overlay(True)
        elif key == "unlock":
            self._show_overlay(False)

    def _show_overlay(self, show: bool):
        if show:
            self.overlay.setGeometry(self.right_panel.rect())
            self.overlay.raise_()
            self.overlay.show()
        else:
            self.overlay.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.right_panel.rect())

    # ---------- стили ----------
    def _apply_main_style(self):
        self.stack.setStyleSheet(f"QWidget#RightStack {{ background: {APP_BG}; }}")

    # ---------- построение Домика ----------
    def _create_home_widget(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(16)

        self.lbl_home_hint = QLabel(HOME_SCREEN.get("title", ""))
        self.lbl_home_hint.setAlignment(Qt.AlignCenter)
        self.lbl_home_hint.setStyleSheet("font-size: 18px; color: #fff;")
        v.addWidget(self.lbl_home_hint)

        # --- Напряжение с кнопками + и - ---
        self.lbl_voltage = QLabel("0,0 В")  # измерение
        self.lbl_voltage.setAlignment(Qt.AlignCenter)
        self.lbl_voltage_dup = QLabel("0,0 В")  # уставка
        voltage_layout = self._create_adjustable_value_layout(
            label=self.lbl_voltage,
            label_style=f"color:{WHITE}; font-size:180px; font-weight:800;",
            duplicate_label=self.lbl_voltage_dup,
            duplicate_style="font-size: 90px; color: #aaa;",
            on_plus=lambda: self._adjust_voltage(10),
            on_minus=lambda: self._adjust_voltage(-10)
        )
        v.addStretch()
        v.addLayout(voltage_layout)

        # --- Ток с кнопками + и - ---
        self.lbl_current = QLabel("0,0 А")  # измерение
        self.lbl_current.setAlignment(Qt.AlignCenter)
        self.lbl_current_dup = QLabel("0,0 А")  # уставка
        current_layout = self._create_adjustable_value_layout(
            label=self.lbl_current,
            label_style=f"color:{ACCENT}; font-size:160px; font-weight:800;",
            duplicate_label=self.lbl_current_dup,
            duplicate_style="font-size: 80px; color: #aaa;",
            on_plus=lambda: self._adjust_current(10),
            on_minus=lambda: self._adjust_current(-10)
        )
        v.addLayout(current_layout)
        v.addStretch()

        self.source_header_home = SourceHeaderWidget(source_controller=self.source)
        v.addWidget(self.source_header_home)

        # --- Кнопка подключения ---
        cbx = QVBoxLayout()
        self.btn_connect_big = QPushButton(HOME_SCREEN.get("connect_btn", "Подключиться"))
        self.btn_connect_big.setMinimumHeight(48)
        self.btn_connect_big.setStyleSheet(
            "font-size: 16px; padding: 10px 18px; font-weight: 700; "
            "background: #EF7F1A; color: #fff; border: none; border-radius: 8px;"
        )
        self.btn_connect_big.clicked.connect(lambda: self._on_nav("source"))
        cbx.addWidget(self.btn_connect_big, alignment=Qt.AlignHCenter)
        v.addLayout(cbx)

        # --- Нижняя панель ---
        self.bottom_container = QWidget()
        bottom = QHBoxLayout(self.bottom_container)
        bottom.setSpacing(40)
        bottom.setContentsMargins(20, 20, 20, 20)

        chip = icon_label("chip.svg", 72)
        lbl_prog = QLabel("Программа 1")
        lbl_prog.setStyleSheet("color:#fff; font-size:42px;")
        bottom.addWidget(chip)
        bottom.addWidget(lbl_prog)
        bottom.addSpacing(60)

        sand = icon_label("hourglass.svg", 72)
        self.lbl_timer = QLabel("00:00:00")
        self.lbl_timer.setStyleSheet("color:#fff; font-size:42px;")
        bottom.addWidget(sand)
        bottom.addWidget(self.lbl_timer)
        bottom.addSpacing(60)

        ah = icon_label("ah.svg", 72)
        self.lbl_ah = QLabel("0 А·ч")
        self.lbl_ah.setStyleSheet("color:#fff; font-size:42px;")
        bottom.addWidget(ah)
        bottom.addWidget(self.lbl_ah)
        bottom.addSpacing(60)

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
        self._apply_connected_ui(False)

        return w

    def _create_adjustable_value_layout(self, label: QLabel, label_style: str, duplicate_label: QLabel, duplicate_style: str, on_plus, on_minus):
        """
        Создаёт QVBoxLayout (вместо QHBoxLayout), где:
        - В строке: кнопка "-", основной label, кнопка "+"
        - Ниже: duplicate_label (меньше, смещен на 43px от правого края)
        """
        # Общий контейнер
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # --- Первая строка: кнопки и основной label ---
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        btn_minus = QPushButton()
        btn_minus.setIcon(QIcon(os.path.join(ASSETS_DIR, "icons", "minus.svg")))
        btn_minus.setFixedSize(180, 180)
        btn_minus.setIconSize(QSize(80, 80))
        btn_minus.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: white; font-size: 32px; font-weight: bold; border: none; border-radius: 40px;"
            "}"
            "QPushButton:hover {"
            "  background: transparent;"
            "}"
        )
        btn_minus.clicked.connect(on_minus)

        label.setStyleSheet(label_style)
        label.setAlignment(Qt.AlignCenter)

        btn_plus = QPushButton()
        btn_plus.setIcon(QIcon(os.path.join(ASSETS_DIR, "icons", "plus.svg")))
        btn_plus.setIconSize(QSize(80, 80))
        btn_plus.setFixedSize(180, 180)
        btn_plus.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: white; font-size: 32px; font-weight: bold; border: none; border-radius: 40px;"
            "}"
            "QPushButton:hover {"
            "  background: transparent;"
            "}"
        )
        btn_plus.clicked.connect(on_plus)

        row_layout.addWidget(btn_minus)
        row_layout.addWidget(label, 1)  # растягиваем label
        row_layout.addWidget(btn_plus)

        # --- Дублирующий label с отступом 43px от правого края ---
        dup_h_layout = QHBoxLayout()
        dup_h_layout.setContentsMargins(0, 0, 0, 0)
        dup_h_layout.addStretch()  # растяжение слева (двигает вправо)
        dup_h_layout.addWidget(duplicate_label)
        dup_h_layout.addSpacing(430)  # отступ справа (двигает лейбл влево от края)

        duplicate_label.setStyleSheet(duplicate_style)

        # Добавляем строку и дубль в общий layout
        main_layout.addLayout(row_layout)
        main_layout.addLayout(dup_h_layout)

        return main_layout

    def _adjust_voltage(self, delta: float):
        """
        Изменяет значение в регистре напряжения на delta (например, +1 или -1)
        """
        if not hasattr(self.source, 'driver') or not self.source.driver:
            print("Нет активного драйвера для изменения напряжения.")
            return

        try:
            # 1. Прочитать текущее значение из регистра
            current_raw_value = self.source.driver.read_voltage_register()
            if current_raw_value is None:
                print("Не удалось прочитать текущее значение напряжения из регистра.")
                return


            new_raw_value = current_raw_value + int(delta)

            # 3. Записать новое значение в регистр
            success = self.source.driver.write_voltage_register(new_raw_value)

            if success:
                scaled_new = new_raw_value * 0.1
                self.lbl_voltage_dup.setText(f"{scaled_new:+.1f} В".replace("+", "").replace(".", ","))
            else:
                print("Не удалось записать новое значение напряжения в регистр.")

        except Exception as e:
            print(f"Ошибка при изменении напряжения: {e}")

    def _adjust_current(self, delta: float):
        """
        Изменяет значение в регистре тока на delta (например, +1 или -1)
        """
        if not hasattr(self.source, 'driver') or not self.source.driver:
            print("Нет активного драйвера для изменения тока.")
            return

        try:
            # 1. Прочитать текущее значение из регистра
            current_raw_value = self.source.driver.read_current_register()
            if current_raw_value is None:
                print("Не удалось прочитать текущее значение тока из регистра.")
                return

            new_raw_value = current_raw_value + int(delta)

            # 3. Записать новое значение в регистр
            success = self.source.driver.write_current_register(new_raw_value)

            if success:
                # 4. Обновить дублирующий лейбл (уставку тока)
                scaled_new = new_raw_value * 0.1
                self.lbl_current_dup.setText(f"{scaled_new:.1f} А".replace(".", ","))


            else:
                print("Не удалось записать новое значение тока в регистр.")

        except Exception as e:
            print(f"Ошибка при изменении тока: {e}")

    # ---------- навигация ----------
    def _on_nav(self, key: str):
        mapping = {"home": 0, "program": 1, "source": 2, "settings": 3, "info": 4}
        titles = {
            "home": "Домашний экран",
            "program": "Программный режим",
            "source": "Подключение к источнику",
            "settings": "Список источников",
            "info": "Информация",
        }
        self.left.set_active(key)
        self.stack.setCurrentIndex(mapping.get(key, 0))
        self.tab_title_label.setText(titles.get(key, ""))

    def _apply_nav_enabled(self, connected: bool):
        self.left.set_enabled_tabs(home=True, program=False, source=True, settings=True, info=True)

    # ---------- подключение ----------
    def on_connect(self, conn_type: str, settings: dict):
        if self._connect_job_active:
            return
        self._connect_job_active = True
        self._pending_conn = (conn_type, settings)
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
                self._last_status_error = str(err)
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
            self.lbl_voltage_dup.setText("0,0 В")
            self.lbl_current_dup.setText("0,0 А")
            self.lbl_ah.setText("0 А·ч")
            self.btn_power.setEnabled(False)
            self._apply_connected_ui(False)
            self.connection_tab.set_connected(False)
            self._set_status("reconnecting", "Переподключение")
        else:
            self.connection_tab.set_connected(True)
            self._set_status("connected", "Подключено")

    # ---------- UI по подключению ----------
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
            self.settings_screen.update_from_meas(meas)
            v = float(meas.voltage)
            i = float(meas.current)
            i_i = float(meas.current_i)/10
            v_i = float(meas.voltage_i)/10

            if self._display_swap_iv:
                v, i = i, v

            self.lbl_voltage.setText(f"{v:+.1f} В".replace("+", "").replace(".", ","))
            self.lbl_current.setText(f"{i:.1f} А".replace(".", ","))

            self.lbl_voltage_dup.setText(f"{v_i:+.1f} В".replace("+", "").replace(".", ","))
            self.lbl_current_dup.setText(f"{i_i:.1f} А".replace(".", ","))

            self.lbl_ah.setText(f"{int(meas.ah_counter)} А·ч")

            current_val = self.source.read_register(1)

            if getattr(meas, "error_overheat", False) or getattr(meas, "error_mains", False):
                self.power_state = "stop"
            else:
                if current_val:
                    self.power_state = "on"
                else:
                    self.power_state = "ready"
                    self.lbl_voltage.setText("0,0 В")
                    self.lbl_current.setText("0,0 А")
            self._update_power_icon()
            self.btn_power.setEnabled(True)
        except Exception:
            self.lbl_voltage.setText("0,0 В")
            self.lbl_current.setText("0,0 А")

    # ---------- таймер ----------
    def _tick_runtime(self):
        if self._start_epoch is None:
            return
        self._elapsed = int(time.time() - self._start_epoch)
        h = self._elapsed // 3600
        m = (self._elapsed % 3600) // 60
        s = self._elapsed % 60
        self.lbl_timer.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # ---------- питание ----------
    def _update_power_icon(self):
        name = {
            "ready": "power.svg",
            "on":    "power_on.svg",
            "stop":  "power.svg",
        }.get(self.power_state, "power.svg")
        self.btn_power.setIcon(QIcon(os.path.join(ASSETS_DIR, "icons", name)))

    def _toggle_power(self):
        current_val = self.source.read_register(1)


        if current_val:
            new_power_val = False
        else:
            new_power_val = True
            self.power_state = current_val
            self._update_power_icon()

        self.source.write_register(1, new_power_val)

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
        if mode == "error":
            self._btn_copy_err.setVisible(True)
        else:
            self._btn_copy_err.setVisible(False)
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
        self._status_dots = (self._status_dots % 3) + 1
        color = {
            "connecting": "#f1c40f",
            "reconnecting": "#f1c40f",
        }.get(self._status_mode, "#bdc3c7")
        text = self._status_text_base + ("." * self._status_dots)
        self._render_status(text, color)