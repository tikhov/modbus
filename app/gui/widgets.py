from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPalette


class AlertBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AlertBox")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.label = QLabel("")
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedWidth(28)
        self.close_btn.clicked.connect(self.hide_message)
        layout.addWidget(self.close_btn, 0, Qt.AlignTop)

        # ВАЖНО: без margin-bottom и без рамки (бордера)
        self.setStyleSheet("""
            QWidget#AlertBox {
                padding: 12px;
                border: none;
                border-radius: 4px;
                background-color: #cce5ff;
            }
            QWidget#AlertBox QLabel {
                color: #004085;
                font-size: 14px;
                background: transparent;
            }
            QWidget#AlertBox QPushButton {
                border: none;
                background: transparent;
                font-size: 18px;
                color: #383d41;
                padding: 0 6px;
            }
            QWidget#AlertBox QPushButton:hover {
                background-color: #b8daff;
                border-radius: 12px;
            }
        """)

        self._anim_h = QPropertyAnimation(self, b"maximumHeight", self)
        self._anim_h.setDuration(220)
        self._anim_h.setEasingCurve(QEasingCurve.OutCubic)

        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._anim_op = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim_op.setDuration(200)
        self._anim_op.setEasingCurve(QEasingCurve.OutCubic)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMaximumHeight(0)
        self.setVisible(False)

        self._hiding = False
        self._anim_h.finished.connect(self._maybe_hide)

    def show_message(self, text: str):
        self.label.setText(text or "")
        self.setVisible(True)
        self._hiding = False

        self._anim_h.stop()
        self._anim_h.setStartValue(0)
        self._anim_h.setEndValue(max(1, self.sizeHint().height()))
        self._anim_h.start()

        self._anim_op.stop()
        self._fx.setOpacity(0.0)
        self._anim_op.setStartValue(0.0)
        self._anim_op.setEndValue(1.0)
        self._anim_op.start()

    def hide_message(self):
        self._hiding = True
        self._anim_h.stop()
        self._anim_h.setStartValue(max(1, self.height()))
        self._anim_h.setEndValue(0)
        self._anim_h.start()

        self._anim_op.stop()
        self._anim_op.setStartValue(1.0)
        self._anim_op.setEndValue(0.0)
        self._anim_op.start()

    def _maybe_hide(self):
        if self._hiding and self.maximumHeight() == 0:
            self.setVisible(False)


class DangerOverlay(QWidget):
    """
    Полупрозрачный фон + большая danger-плашка.
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

        self.btn = QPushButton("вернуться к настройкам подключения")
        self.btn.setMinimumHeight(38)
        self.btn.clicked.connect(self._go_back)
        panel_l.addWidget(self.btn, 0, Qt.AlignRight)

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
                padding: 8px 14px;   /* комфортные внутренние отступы */
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
