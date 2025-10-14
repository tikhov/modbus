import sys
import time

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPalette, QColor
from app.gui.main_window import MainWindow
from app.gui.splash import SplashScreen
from app.db import init_db
import logging

# Уменьшаем логирование pymodbus (часто печатает повторяющиеся сообщения при отсутствии ответа)
logging.getLogger('pymodbus').setLevel(logging.WARNING)


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
        """
        Создаём главное окно заранее (в невидимом состоянии),
        затем запускаем fade_out заставки. После завершения fade_out
        закрываем splash и плавно делаем main видимым.
        """
        # Создаём окно, делаем полностью прозрачным и показываем в full screen
        window = MainWindow()
        window.setWindowOpacity(0.0)
        # показываем сразу в полноэкранном режиме — но прозрачный, чтобы не было "скачка"
        window.showFullScreen()

        # Функция, которая будет вызвана после завершения fade out заставки
        def _on_splash_faded():
            # Закрываем/скрываем splash чтобы он не перекрывал main
            try:
                splash.close()
            except Exception:
                try:
                    splash.hide()
                except Exception:
                    pass

            # Плавное проявление главного окна
            anim = QPropertyAnimation(window, b"windowOpacity")

            anim.setDuration(400)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.InOutQuad)
            window._fade_in_anim = anim

            def _clear_ref():
                try:
                    delattr(window, "_fade_in_anim")
                except Exception:
                    pass

            anim.finished.connect(_clear_ref)
            anim.start()

        # Запускаем fade out заставки и привязываем коллбэк
        splash.start_fade_out(on_finished=_on_splash_faded)

    time.sleep(1)
    QTimer.singleShot(1100, start_main)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
