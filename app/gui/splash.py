from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QApplication,
    QGraphicsOpacityEffect  # ← именно здесь!
)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPalette
import os
from resources import ASSETS_DIR


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Загрузка...")

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#2B2A29"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        screen = QApplication.primaryScreen()
        size = screen.size()
        self.setFixedSize(int(size.width() * 1), int(size.height() * 1))

        # --- Поведение окна ---
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(30)
        layout.setAlignment(Qt.AlignCenter)

        # --- Логотипы ---
        logo1 = QSvgWidget(os.path.join(ASSETS_DIR, "icons", "logo.svg"))
        logo1.setFixedSize(400, 500)
        layout.addWidget(logo1, alignment=Qt.AlignCenter)

        logo2 = QSvgWidget(os.path.join(ASSETS_DIR, "icons", "made_in_russia.svg"))
        logo2.setFixedSize(200, 200)
        layout.addWidget(logo2, alignment=Qt.AlignCenter)

        # --- Прозрачность ---
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        # --- Анимации ---
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(800)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.InOutQuad)

        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(800)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.InOutQuad)

    def start_fade_in(self):
        self.fade_in.start()

    def start_fade_out(self, on_finished=None):
        if on_finished:
            self.fade_out.finished.connect(on_finished)
        self.fade_out.start()