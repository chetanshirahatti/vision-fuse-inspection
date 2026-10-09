import os, sys
from PySide6.QtWidgets import QApplication
from app_context import AppContext
from ui.main_window import MainWindow
from ui.theme import QSS


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    ctx = AppContext()
    win = MainWindow(ctx)
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
