# app/gui/info_screen.py
import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from resources import ASSETS_DIR
from dictionary import INFO_TAB


class InfoScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignCenter)



        # --- Контейнер для QR + текста ---
        qr_row = QHBoxLayout()
        qr_row.setSpacing(30)
        qr_row.setAlignment(Qt.AlignCenter)

        qr_label = QLabel()
        qr_pixmap = QPixmap(os.path.join(ASSETS_DIR, "icons", "QR_commerce.svg"))
        if qr_pixmap.isNull():
            qr_label.setText("[QR]")
            qr_label.setStyleSheet("color: #aaa; font-size: 12px;")
        else:
            qr_label.setPixmap(qr_pixmap.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        qr_label.setAlignment(Qt.AlignCenter)
        qr_row.addWidget(qr_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(15)

        line1 = QLabel("Коммерческий отдел")
        line2 = QLabel("8 800 700-57-98 доб. 1")
        line3 = QLabel("mail@ei-neon.ru")

        for lbl in (line1, line2, line3):
            lbl.setAlignment(Qt.AlignLeft)
            lbl.setStyleSheet("font-size: 34px; color: #FFFFFF; font-weight: bold;")

        text_layout.addWidget(line1)
        text_layout.addWidget(line2)
        text_layout.addWidget(line3)

        qr_row.addLayout(text_layout)
        main_layout.addLayout(qr_row)
