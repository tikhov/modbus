from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
import os
from resources import ASSETS_DIR

class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(12)

        def iconLbl(name, size=22):
            lbl = QLabel()
            ico = QIcon(os.path.join(ASSETS_DIR, "icons", name))
            lbl.setPixmap(ico.pixmap(size, size))
            return lbl

        # Program/Step
        h.addWidget(iconLbl("chip.svg"))
        self.lblProgram = QLabel("Программа: —   Шаг: —")
        h.addWidget(self.lblProgram)
        # Timer
        h.addSpacing(12)
        h.addWidget(iconLbl("hourglass.svg"))
        self.lblTimer = QLabel("00:00:00")
        h.addWidget(self.lblTimer)
        # Ah
        h.addSpacing(12)
        h.addWidget(iconLbl("ah.svg"))
        self.lblAh = QLabel("АЧ: 0")
        h.addWidget(self.lblAh)
        h.addStretch()
        # State icon
        self.iconState = iconLbl("state_ready_yellow_triangle.svg")
        h.addWidget(self.iconState)

    # API to update values
    def setProgramStep(self, program_text: str):
        self.lblProgram.setText(program_text)

    def setTimer(self, text: str):
        self.lblTimer.setText(text)

    def setAh(self, text: str):
        self.lblAh.setText(text)

    def setStateIcon(self, icon_filename: str):
        from PySide6.QtGui import QIcon
        import os
        ico = QIcon(os.path.join(ASSETS_DIR, "icons", icon_filename))
        self.iconState.setPixmap(ico.pixmap(22, 22))
