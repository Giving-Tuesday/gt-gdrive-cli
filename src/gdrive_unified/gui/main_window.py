"""Main application window with tabbed interface."""

import logging
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QDockWidget,
    QStatusBar,
    QMessageBox,
)

from .tabs import SearchTab, DownloadTab, ManageTab, SettingsTab
from .widgets import LogPanel


class MainWindow(QMainWindow):
    """Main application window for Google Drive Tools."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Google Drive Tools")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        self._setup_ui()
        self._setup_logging()
        self._check_credentials()

    def _setup_ui(self):
        """Set up the user interface."""
        # Central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Settings tab (created first so other tabs can reference it)
        self.settings_tab = SettingsTab()
        self.settings_tab.settingsChanged.connect(self._on_settings_changed)

        # Search tab
        self.search_tab = SearchTab(
            get_credentials=self.settings_tab.get_credentials_path,
            get_output_dir=self.settings_tab.get_output_dir,
        )
        self.search_tab.logMessage.connect(self._log)

        # Download tab
        self.download_tab = DownloadTab(
            get_credentials=self.settings_tab.get_credentials_path,
            get_output_dir=self.settings_tab.get_output_dir,
        )
        self.download_tab.logMessage.connect(self._log)

        # Manage tab
        self.manage_tab = ManageTab()
        self.manage_tab.logMessage.connect(self._log)

        # Add tabs
        self.tabs.addTab(self.search_tab, "Search")
        self.tabs.addTab(self.download_tab, "Download")
        self.tabs.addTab(self.manage_tab, "Manage")
        self.tabs.addTab(self.settings_tab, "Settings")

        # Log panel as dock widget
        self.log_panel = LogPanel()
        log_dock = QDockWidget("Log", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status()

    def _setup_logging(self):
        """Set up logging to the log panel."""
        # Get the application logger
        logger = logging.getLogger("gdrive_unified")
        logger.setLevel(logging.DEBUG)

        # Add our handler
        handler = self.log_panel.get_handler()
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

    def _check_credentials(self):
        """Check for valid credentials on startup."""
        if not self.settings_tab.has_valid_credentials():
            self._log("No credentials found. Please configure in Settings tab.")
            self.status_bar.showMessage("Credentials not configured", 5000)
            # Switch to settings tab
            self.tabs.setCurrentWidget(self.settings_tab)

    def _on_settings_changed(self):
        """Handle settings changes."""
        self._update_status()

        # Update log level
        log_level = self.settings_tab.get_log_level()
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        handler = self.log_panel.get_handler()
        handler.setLevel(level_map.get(log_level, logging.INFO))

    def _update_status(self):
        """Update the status bar."""
        if self.settings_tab.has_valid_credentials():
            self.status_bar.showMessage("Ready")
        else:
            self.status_bar.showMessage("Credentials not configured")

    def _log(self, message: str):
        """Log a message to the log panel."""
        self.log_panel.log(message)

    def closeEvent(self, event):
        """Handle window close."""
        # Could add confirmation dialog for running operations
        event.accept()
