"""PyQt5 GUI for Google Drive Tools."""

import sys
from PyQt5.QtWidgets import QApplication

from .main_window import MainWindow


def main():
    """Main entry point for the GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Google Drive Tools")
    app.setOrganizationName("GivingTuesday")
    app.setOrganizationDomain("givingtuesday.org")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


__all__ = ["main", "MainWindow"]
