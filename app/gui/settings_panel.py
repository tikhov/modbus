from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFormLayout,
    QMessageBox, QComboBox, QInputDialog, QHBoxLayout, QSizePolicy
)
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QBrush, QPen, QIntValidator
from PySide6.QtCore import Qt
import serial
from serial.tools import list_ports

from app import db
from resources import DEFAULT_RTU, DEFAULT_WIFI
from dictionary import SETTINGS_SCREEN, TOOLTIPS_RTU, TOOLTIPS_TCP, PROFILE_MSGS
from .widgets import AlertBox, DangerOverlay

PRIMARY_BORDER = "#EF7F1A"
PANEL_BG = "#3B2F22"
FIELD_BG = "#453D31"
FIELD_FG = "#FFFFFF"

BTN_STYLE = f"""
QPushButton {{
    background: {PRIMARY_BORDER};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 700;
}}
QPushButton:hover {{ background: #ff973e; }}
"""

def dot_icon(color: QColor, size: int = 12) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(color.darker(140)))
    p.setBrush(QBrush(color))
    r = size - 2
    p.drawEllipse(1, 1, r, r)
    p.end()
    return QIcon(pm)

GREEN = QColor("#16A34A")
RED   = QColor("#DC2626")
GRAY  = QColor("#9CA3AF")


class SettingsPanel(QWidget):
    def __init__(self, conn_type: str, on_back, on_connect):
        super().__init__()
        self.conn_type = conn_type
        self.on_back = on_back
        self.on_connect = on_connect
        self.current_profile = None
        self._error_overlay = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        center_row = QHBoxLayout()
        center_row.addStretch()

        self.card = QWidget()
        self.card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.card.setStyleSheet(f"""
            QWidget {{
                background: {PANEL_BG};
                border-radius: 8px;
            }}
            QLabel {{ color: #ffffff; }}
            QLineEdit, QComboBox {{
                background: {FIELD_BG};
                color: {FIELD_FG};
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 28px;
            }}
            QComboBox::drop-down {{ border: none; }}
            /* help-«?» НЕ красим здесь (у него свой id) */
        """)
        v = QVBoxLayout(self.card)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        title = QLabel(f"<b>{SETTINGS_SCREEN['title']}: {self.conn_type}</b>")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        # --- Профили ---
        profiles_row = QHBoxLayout()
        self.profiles_cb = QComboBox()
        self.profiles_cb.setToolTip(SETTINGS_SCREEN["profiles_tooltip"])
        self.profiles_cb.setMinimumWidth(260)
        profiles_row.addWidget(self.profiles_cb, 1)

        self.btn_rename = QPushButton("Переименовать")
        self.btn_rename.setCursor(Qt.PointingHandCursor)
        self.btn_rename.setStyleSheet(BTN_STYLE)
        self.btn_rename.setMinimumHeight(30)
        self.btn_rename.clicked.connect(self.rename_profile)
        profiles_row.addWidget(self.btn_rename)

        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setStyleSheet(BTN_STYLE)
        self.btn_delete.setMinimumHeight(30)
        self.btn_delete.clicked.connect(self.delete_profile)
        profiles_row.addWidget(self.btn_delete)

        v.addLayout(profiles_row)

        # Подсказки (синий алерт без бордера)
        self.alert = AlertBox()
        v.addWidget(self.alert)

        # --- Форма полей ---
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.inputs = {}

        if self.conn_type == "RTU":
            # Порт + «Обновить порты»
            self.port_cb = QComboBox()
            self.port_cb.setMinimumWidth(260)
            self.refresh_btn = QPushButton(SETTINGS_SCREEN["refresh_ports_btn"])
            self.refresh_btn.setToolTip(SETTINGS_SCREEN["refresh_ports_tooltip"])
            self.refresh_btn.setCursor(Qt.PointingHandCursor)
            self.refresh_btn.setStyleSheet(BTN_STYLE)
            self.refresh_btn.setMinimumHeight(30)
            self.refresh_btn.clicked.connect(self._populate_ports)

            port_row = QHBoxLayout()
            port_row.setSpacing(6)
            port_row.addWidget(self.port_cb, 1)
            port_row.addWidget(self.refresh_btn)

            port_wrap = QWidget()
            port_wrap.setLayout(port_row)
            self.inputs["port"] = self.port_cb
            self.form.addRow("port", port_wrap)

            self._populate_ports()

            # Baudrate
            baud = QLineEdit()
            baud.setText(str(DEFAULT_RTU.get("baudrate", "9600")))
            baud.setValidator(QIntValidator(1200, 10000000, self))
            self.inputs["baudrate"] = baud
            self._add_row("baudrate", baud, TOOLTIPS_RTU["baudrate"])

            # Parity
            self.parity_cb = QComboBox()
            self.parity_cb.addItems(["N", "E", "O"])
            self.parity_cb.setCurrentText(str(DEFAULT_RTU.get("parity", "N")).upper())
            self.inputs["parity"] = self.parity_cb
            self._add_row("parity", self.parity_cb, TOOLTIPS_RTU["parity"])

            # Stopbits
            self.stopbits_cb = QComboBox()
            self.stopbits_cb.addItems(["1", "1.5", "2"])
            self.stopbits_cb.setCurrentText(str(DEFAULT_RTU.get("stopbits", "1")))
            self.inputs["stopbits"] = self.stopbits_cb
            self._add_row("stopbits", self.stopbits_cb, TOOLTIPS_RTU["stopbits"])

            # Unit ID
            unit = QLineEdit()
            unit.setText(str(DEFAULT_RTU.get("unit_id", "1")))
            unit.setValidator(QIntValidator(1, 247, self))
            self.inputs["unit_id"] = unit
            self._add_row("unit_id", unit, TOOLTIPS_RTU["unit_id"])

        else:  # TCP
            host = QLineEdit()
            host.setText(str(DEFAULT_WIFI.get("host", "192.168.1.100")))
            self.inputs["host"] = host
            self._add_row("host", host, TOOLTIPS_TCP["host"])

            port = QLineEdit()
            port.setText(str(DEFAULT_WIFI.get("port", "502")))
            port.setValidator(QIntValidator(1, 65535, self))
            self.inputs["port"] = port
            self._add_row("port", port, TOOLTIPS_TCP["port"])

            unit = QLineEdit()
            unit.setText(str(DEFAULT_WIFI.get("unit_id", "1")))
            unit.setValidator(QIntValidator(1, 247, self))
            self.inputs["unit_id"] = unit
            self._add_row("unit_id", unit, TOOLTIPS_TCP["unit_id"])

        v.addLayout(self.form)

        # Кнопки (явный стиль, чтобы не «съедались»)
        btns = QHBoxLayout()
        self.save_btn = QPushButton(SETTINGS_SCREEN["save_btn"])
        self.save_btn.setStyleSheet(BTN_STYLE)
        self.save_btn.setMinimumHeight(34)
        self.save_btn.clicked.connect(self.on_save)

        self.connect_btn = QPushButton(SETTINGS_SCREEN["connect_btn"])
        self.connect_btn.setStyleSheet(BTN_STYLE)
        self.connect_btn.setMinimumHeight(34)
        self.connect_btn.clicked.connect(self._connect)

        back_btn = QPushButton(SETTINGS_SCREEN["back_btn"])
        back_btn.setStyleSheet(BTN_STYLE)
        back_btn.setMinimumHeight(34)
        back_btn.clicked.connect(self.on_back)

        btns.addWidget(self.save_btn)
        btns.addWidget(self.connect_btn)
        btns.addStretch()
        btns.addWidget(back_btn)
        v.addLayout(btns)

        center_row.addWidget(self.card)
        center_row.addStretch()

        root.addStretch()
        root.addLayout(center_row)
        root.addStretch()

        self.load_profiles()

    # === Ошибка подключения ===
    def show_connect_error(self, text: str):
        if self._error_overlay is None:
            self._error_overlay = DangerOverlay(self)
        self._error_overlay.setGeometry(self.rect())
        self._error_overlay.show_error(text or "Не удалось подключиться к источнику.", on_back=self._hide_error_only)
        self._error_overlay.raise_()

    def _hide_error_only(self):
        if self._error_overlay:
            self._error_overlay.hide_overlay()

    def resizeEvent(self, e):
        w = max(420, int(self.width() * 0.5))
        w = min(900, w)
        self.card.setFixedWidth(w)
        if self._error_overlay and self._error_overlay.isVisible():
            self._error_overlay.setGeometry(self.rect())
        super().resizeEvent(e)

    # --- строка формы с «?» ---
    def _add_row(self, key: str, widget, tooltip: str):
        if key not in self.inputs:
            self.inputs[key] = widget

        row = QHBoxLayout()
        row.setSpacing(6)
        widget.setMinimumWidth(260)
        row.addWidget(widget)

        help_btn = QPushButton("?")
        help_btn.setObjectName("HelpDot")   # собственный стиль
        help_btn.setFixedSize(24, 24)
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.setStyleSheet("""
            QPushButton#HelpDot {
                color: #383d41;
                background: #cce5ff;
                border: none;
                border-radius: 12px;
                font-weight: 800;
            }
            QPushButton#HelpDot:hover { background: #b8daff; }
        """)
        help_btn.clicked.connect(lambda _, t=tooltip: self.alert.show_message(t))
        row.addWidget(help_btn)

        wrapper = QWidget()
        wrapper.setLayout(row)
        self.form.addRow(key, wrapper)

    # --- Порты ---
    def _populate_ports(self):
        self.port_cb.clear()
        items = []
        for p in list_ports.comports():
            name = p.device
            desc = p.description or ""
            items.append((name, desc, p))

        if not items:
            self.port_cb.addItem("Портов не найдено", None)
            return

        for name, desc, p in items:
            color = GRAY
            try:
                s = serial.Serial(name, timeout=0)
                s.close()
                color = GREEN
            except Exception:
                color = RED
            ic = dot_icon(color)
            label = f"{name} — {desc}" if desc else name
            self.port_cb.addItem(ic, label, userData=name)

        self.port_cb.setCurrentIndex(0)

    # --- Профили ---
    def load_profiles(self):
        self.profiles_cb.clear()
        profiles = db.get_all_profiles()
        filtered = [p for p in profiles if (p.get("conn_type", "").upper() == self.conn_type)]
        self.profiles = {p["name"]: p for p in filtered}
        self.profiles_cb.addItem("-- Новый профиль --")
        for name in sorted(self.profiles.keys()):
            self.profiles_cb.addItem(name)
        self.profiles_cb.currentTextChanged.connect(self.on_profile_selected)
        self._update_profile_buttons()

    def _update_profile_buttons(self):
        is_real = self.profiles_cb.currentText() != "-- Новый профиль --"
        self.btn_rename.setEnabled(is_real)
        self.btn_delete.setEnabled(is_real)

    def on_profile_selected(self, text):
        from PySide6.QtWidgets import QLineEdit
        self._update_profile_buttons()

        if text == "-- Новый профиль --":
            self.current_profile = None
            defaults = DEFAULT_RTU if self.conn_type == "RTU" else DEFAULT_WIFI
            for k, w in self.inputs.items():
                if isinstance(w, QLineEdit):
                    w.setText(str(defaults.get(k, "")))
                elif isinstance(w, QComboBox):
                    val = str(defaults.get(k, w.currentText()))
                    idx = w.findText(val)
                    if idx >= 0:
                        w.setCurrentIndex(idx)
            return

        prof = self.profiles.get(text)
        if not prof:
            return
        self.current_profile = prof
        settings = prof.get("settings", {})
        if self.conn_type == "RTU":
            target = settings.get("port", "")
            idx = self.port_cb.findData(target)
            if idx >= 0:
                self.port_cb.setCurrentIndex(idx)
        for k, widget in self.inputs.items():
            if isinstance(widget, QLineEdit):
                widget.setText(str(settings.get(k, widget.text())))
            elif isinstance(widget, QComboBox):
                val = str(settings.get(k, widget.currentText()))
                i = widget.findText(val)
                if i >= 0:
                    widget.setCurrentIndex(i)

    # --- CRUD профилей ---
    def on_save(self):
        data = self._collect()
        if self.current_profile:
            name = self.current_profile["name"]
            db.update_profile(name, self.conn_type, data)
            QMessageBox.information(self, "Сохранено", PROFILE_MSGS["saved"].format(name=name))
            self.load_profiles()
            self.profiles_cb.setCurrentText(name)
        else:
            name, ok = QInputDialog.getText(self, "Имя профиля", "Введите имя нового профиля:")
            if not ok or not name.strip():
                QMessageBox.warning(self, PROFILE_MSGS["canceled"], PROFILE_MSGS["not_named"])
                return
            name = name.strip()
            db.create_profile(name, self.conn_type, data)
            QMessageBox.information(self, "Создано", PROFILE_MSGS["created"].format(name=name))
            self.load_profiles()
            self.profiles_cb.setCurrentText(name)

    def rename_profile(self):
        cur = self.profiles_cb.currentText()
        if cur == "-- Новый профиль --":
            return
        new_name, ok = QInputDialog.getText(self, "Переименовать профиль", f"Новое имя для «{cur}»:")
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        try:
            db.rename_profile(cur, new_name)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать: {e}")
            return
        QMessageBox.information(self, "Готово", f"Профиль «{cur}» переименован в «{new_name}».")
        self.load_profiles()
        self.profiles_cb.setCurrentText(new_name)

    def delete_profile(self):
        cur = self.profiles_cb.currentText()
        if cur == "-- Новый профиль --":
            return
        ret = QMessageBox.question(self, "Удалить профиль", f"Удалить профиль «{cur}»?", QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        try:
            db.delete_profile(cur)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {e}")
            return
        QMessageBox.information(self, "Готово", f"Профиль «{cur}» удалён.")
        self.load_profiles()
        self.profiles_cb.setCurrentIndex(0)

    # --- сбор/подключение ---
    def _collect(self):
        from PySide6.QtWidgets import QLineEdit, QComboBox
        d = {}
        if self.conn_type == "RTU":
            port_data = self.port_cb.currentData()
            port_text = self.port_cb.currentText()
            d["port"] = port_data or port_text
        for k, w in self.inputs.items():
            if isinstance(w, QLineEdit):
                d[k] = w.text().strip()
            elif isinstance(w, QComboBox):
                d[k] = w.currentText().strip()
        return d

    def _connect(self):
        data = self._collect()
        self.on_connect(self.conn_type, data)
