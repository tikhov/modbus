import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPalette, QColor
from app.gui.main_window import MainWindow
from app.gui.splash import SplashScreen
from app.db import init_db


def main():
    app = QApplication(sys.argv)

    # 1. Устанавливаем стиль Fusion
    app.setStyle("Fusion")

    # 2. Создаём и устанавливаем фиксированную тёмную палитру
    palette = QPalette()
    BG_COLOR = QColor("#292116")  # фон всего приложения (как в вашем APP_BG)
    NAV_BG = QColor("#453D31")  # фон левой панели
    TEXT_COLOR = QColor("#FFFFFF")

    # Основные цвета фона и текста
    palette.setColor(QPalette.Window, BG_COLOR)
    palette.setColor(QPalette.Base, BG_COLOR)
    palette.setColor(QPalette.AlternateBase, BG_COLOR)
    palette.setColor(QPalette.Text, TEXT_COLOR)
    palette.setColor(QPalette.Button, NAV_BG)
    palette.setColor(QPalette.ButtonText, TEXT_COLOR)
    palette.setColor(QPalette.WindowText, TEXT_COLOR)
    palette.setColor(QPalette.Highlight, QColor("#EF7F1A"))
    palette.setColor(QPalette.HighlightedText, TEXT_COLOR)

    app.setPalette(palette)

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
    QTimer.singleShot(500, start_main)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()