import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt
from app.gui.main_window import MainWindow
from app.gui.splash import SplashScreen
from app.db import init_db


def main():
    app = QApplication(sys.argv)
    init_db()

    splash = SplashScreen()
    splash.show()
    splash.start_fade_in()

    def start_main():
        def show_main():
            window = MainWindow()
            window.setWindowState(Qt.WindowNoState)
            window.showFullScreen()
            splash.close()
        splash.start_fade_out(on_finished=show_main)

    # 2000 мс (2 сек) до начала fade out
    QTimer.singleShot(2000, start_main)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
