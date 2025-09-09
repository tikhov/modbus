import sys
from PySide6.QtWidgets import QApplication
from app.db import init_db
from app.gui.main_window import MainWindow

def main():
    init_db()
    app = QApplication(sys.argv)
    with open('app/gui/style.qss', 'r', encoding='utf-8') as f:
        app.setStyleSheet(f.read())
    # лёгкая тема/скейл по желанию
    app.setStyleSheet("""
        QLabel { font-size: 14px; }
        QPushButton { font-size: 14px; }
    """)
    w = MainWindow()
    # w.show() — не обязательно, т.к. в MainWindow я вызываю showMaximized()
    w.show()   # оставим, на всякий случай
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
