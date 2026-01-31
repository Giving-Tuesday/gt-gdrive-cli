"""Allow running the GUI as a module: python -m gdrive_unified.gui"""

import sys
from PyQt5.QtWidgets import QApplication

from gdrive_unified.gui.main_window import MainWindow


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Google Drive Tools")
    app.setOrganizationName("GivingTuesday")
    app.setOrganizationDomain("givingtuesday.org")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
