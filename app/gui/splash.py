from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
import os
from resources import ASSETS_DIR


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Загрузка...")
        self.setStyleSheet("background-color: #2B2A29;")
        self.setFixedSize(300, 400)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)

        # --- Logo 1 ---
        logo1_path =  os.path.join(ASSETS_DIR, "icons", "logo.svg")
        self.logo1 = QSvgWidget(logo1_path)
        self.logo1.setFixedSize(200, 100)
        layout.addWidget(self.logo1, alignment=Qt.AlignCenter)

        # --- Logo 2 ---
        logo2_path = os.path.join(ASSETS_DIR, "icons", "made_in_russia.svg")
        self.logo2 = QSvgWidget(logo2_path)
        self.logo2.setFixedSize(200, 100)
        layout.addWidget(self.logo2, alignment=Qt.AlignCenter)

        # --- Opacity effect ---
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        # --- Fade in animation ---
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(800)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)
        self.fade_in.setEasingCurve(QEasingCurve.InOutQuad)

        # --- Fade out animation ---
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(800)
        self.fade_out.setStartValue(1)
        self.fade_out.setEndValue(0)
        self.fade_out.setEasingCurve(QEasingCurve.InOutQuad)

    def start_fade_in(self):
        self.fade_in.start()

    def start_fade_out(self, on_finished=None):
        if on_finished:
            self.fade_out.finished.connect(on_finished)
        self.fade_out.start()
