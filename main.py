"""StudyFlow — a focus timer, study planner and camera-based attention tracker."""
import sys

from PySide6.QtWidgets import QApplication

from studyflow.db import Database
from studyflow.ui.main_window import MainWindow
from studyflow.ui.theme import STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("StudyFlow")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow(Database())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
