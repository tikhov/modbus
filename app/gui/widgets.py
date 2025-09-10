from PySide6.QtWidgets import (
    QVBoxLayout, QPushButton, QGraphicsOpacityEffect
)

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QToolButton, QSizePolicy, QToolTip, QMessageBox


class AlertBox(QWidget):
    """
    Лёгкий алерт (info/warning/success/danger) с плавным появлением.
    Для kind='danger' показывает кнопку копирования текста в буфер.
    Сигналы:
        alertShown(text:str, kind:str)
        alertCleared()
    """
    alertShown = Signal(str, str)
    alertCleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self._text = ""
        self._kind = "info"

        # ОДНА ГОРИЗОНТАЛЬНАЯ СТРОКА: текст + кнопка копирования
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._card = QWidget(self)
        self._card.setObjectName("AlertCard")
        self._card.setStyleSheet("""
            QWidget#AlertCard {
                background-color: #cce5ff; /* info */
                border-radius: 12px;
            }
        """)
        card_l = QHBoxLayout(self._card)
        card_l.setContentsMargins(12, 10, 12, 10)
        card_l.setSpacing(8)

        self._label = QLabel("", self._card)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setStyleSheet("color: #383d41;")
        card_l.addWidget(self._label, 1, Qt.AlignVCenter)

        # Кнопка «копировать» — справа, в той же строке
        self._btn_copy = QToolButton(self._card)
        self._btn_copy.setText("📋")
        self._btn_copy.setToolTip("Скопировать текст ошибки")
        self._btn_copy.setAutoRaise(True)
        self._btn_copy.setCursor(Qt.PointingHandCursor)
        self._btn_copy.setStyleSheet(
            "QToolButton { border: none; color: #383d41; font-size: 16px; padding: 2px 6px; }"
            "QToolButton:hover { background: rgba(0,0,0,0.06); border-radius: 6px; }"
        )
        self._btn_copy.clicked.connect(self._copy_to_clipboard)
        self._btn_copy.hide()  # только для danger
        card_l.addWidget(self._btn_copy, 0, Qt.AlignVCenter)

        row.addWidget(self._card)

        # анимация появления
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.hide()

    # API
    def show_message(self, text: str, kind: str = "info"):
        if not text:
            self.clear(); return
        self._text = text
        self._kind = kind or "info"

        if self._kind == "danger":
            bg, fg = "#f8d7da", "#842029"
        elif self._kind == "warning":
            bg, fg = "#fff3cd", "#664d03"
        elif self._kind == "success":
            bg, fg = "#d1e7dd", "#0f5132"
        else:
            bg, fg = "#cce5ff", "#383d41"

        self._card.setStyleSheet(f"""
            QWidget#AlertCard {{
                background-color: {bg};
                border-radius: 12px;
            }}
        """)
        self._label.setStyleSheet(f"color: {fg};")
        self._label.setText(text)
        self._btn_copy.setVisible(self._kind == "danger")

        self.setWindowOpacity(0.0)
        self.show()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

        self.alertShown.emit(self._text, self._kind)

    def show_error(self, text: str):
        self.show_message(text, "danger")

    def clear(self):
        self._text = ""
        self._kind = "info"
        self.hide()
        self.alertCleared.emit()

    def _copy_to_clipboard(self):
        if self._text:
            QGuiApplication.clipboard().setText(self._text)
            # всплывающий тултип рядом с кнопкой
            pos = self._btn_copy.mapToGlobal(self._btn_copy.rect().center())
            QToolTip.showText(pos, "Ошибка скопирована в буфер обмена", self._btn_copy)


class DangerOverlay(QWidget):
    """
    Полупрозрачный фон + большая danger-плашка.
    Кнопки в одной строке: слева «Копировать текст ошибки», справа «Вернуться к настройкам подключения».
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DangerOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setVisible(False)
        self._on_back = None

        self.setStyleSheet("QWidget#DangerOverlay { background-color: rgba(0,0,0,0.35); }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addStretch()

        self.panel = QWidget(self)
        self.panel.setObjectName("DangerPanel")
        self.panel.setAttribute(Qt.WA_StyledBackground, True)

        panel_l = QVBoxLayout(self.panel)
        panel_l.setContentsMargins(16, 16, 16, 16)
        panel_l.setSpacing(10)

        self.label = QLabel("")
        self.label.setWordWrap(True)
        panel_l.addWidget(self.label, 1)

        # --- Ряд кнопок: слева «Копировать», справа «Вернуться» ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_copy = QPushButton("Копировать текст ошибки")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy_error)
        btn_row.addWidget(self.btn_copy, 0, Qt.AlignLeft)

        btn_row.addStretch(1)

        self.btn = QPushButton("Вернуться к настройкам подключения")
        self.btn.setMinimumHeight(38)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self._go_back)
        btn_row.addWidget(self.btn, 0, Qt.AlignRight)

        panel_l.addLayout(btn_row)

        # danger-стили с фоном, без влияния глобального
        self.panel.setStyleSheet("""
            QWidget#DangerPanel {
                color: #842029;
                background-color: #f8d7da;
                border: 1px solid #f5c2c7;
                border-radius: 6px;
            }
            QWidget#DangerPanel QLabel {
                color: #842029;
                font-size: 15px;
                background: transparent;
            }
            QWidget#DangerPanel QPushButton {
                background: #842029;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QWidget#DangerPanel QPushButton:hover { background: #6c1b22; }
        """)

        outer.addWidget(self.panel, 0, Qt.AlignHCenter)
        outer.addStretch()

        self._fx = QGraphicsOpacityEffect(self.panel)
        self.panel.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def show_error(self, text: str, on_back):
        print(text)
        self._on_back = on_back
        self.label.setText(text or "Ошибка подключения")
        self._resize_panel()
        self.setVisible(True)
        self._fx.setOpacity(0.0)
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def hide_overlay(self):
        self.setVisible(False)

    def _copy_error(self):
        text = self.label.text() if hasattr(self, "label") else ""
        if text:
            QGuiApplication.clipboard().setText(text)
            # системное диалоговое окно
            QMessageBox.information(self, "Скопировано", "Ошибка скопирована в буфер обмена")

    def _go_back(self):
        self.hide_overlay()
        if callable(self._on_back):
            self._on_back()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._resize_panel()

    def _resize_panel(self):
        if not self.parent():
            return
        w = self.parent().width() if isinstance(self.parent(), QWidget) else self.width()
        target_w = max(400, int(w * 0.8))
        self.panel.setFixedWidth(target_w)
