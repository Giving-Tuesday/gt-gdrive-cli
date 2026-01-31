"""Settings tab for application configuration."""

import os
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal, QSettings
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QLabel,
)

from ..widgets import FileBrowser


def get_app_data_dir() -> Path:
    """Return platform-appropriate app data directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "gdrive-download"


def get_default_output_dir() -> Path:
    """Return default output directory (user's Documents folder)."""
    if sys.platform == "win32":
        docs = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
    else:
        docs = Path.home() / "Documents"

    if not docs.exists():
        docs = Path.home()

    return docs / "GDrive Downloads"


class SettingsTab(QWidget):
    """Settings tab for credentials, output, and logging configuration."""

    settingsChanged = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Credentials section
        creds_group = QGroupBox("Credentials")
        creds_layout = QFormLayout(creds_group)

        self.creds_browser = FileBrowser(
            mode="file",
            filter_str="JSON Files (*.json);;All Files (*)",
            placeholder="Path to credentials.json",
            show_status=True,
        )
        self.creds_browser.pathChanged.connect(self._on_settings_changed)
        creds_layout.addRow("Credentials File:", self.creds_browser)

        layout.addWidget(creds_group)

        # Output section
        output_group = QGroupBox("Output Location")
        output_layout = QFormLayout(output_group)

        self.output_browser = FileBrowser(
            mode="directory",
            placeholder="Default output directory",
        )
        self.output_browser.pathChanged.connect(self._on_settings_changed)
        output_layout.addRow("Default Output:", self.output_browser)

        layout.addWidget(output_group)

        # Logging section
        logging_group = QGroupBox("Logging")
        logging_layout = QFormLayout(logging_group)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        self.log_level_combo.currentTextChanged.connect(self._on_settings_changed)
        logging_layout.addRow("Log Level:", self.log_level_combo)

        layout.addWidget(logging_group)

        # Config file section
        config_group = QGroupBox("Configuration File")
        config_layout = QFormLayout(config_group)

        self.config_browser = FileBrowser(
            mode="file",
            filter_str="YAML Files (*.yaml *.yml);;All Files (*)",
            placeholder="Optional config file",
        )
        self.config_browser.pathChanged.connect(self._on_settings_changed)
        config_layout.addRow("Config File:", self.config_browser)

        layout.addWidget(config_group)

        # Add stretch to push everything to top
        layout.addStretch()

    def _load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings("GivingTuesday", "GDriveTools")

        # Credentials - check saved path, then default locations
        creds_path = settings.value("credentials_path", "")
        if not creds_path or not Path(creds_path).exists():
            creds_path = self._find_credentials()
        self.creds_browser.setPath(creds_path)

        # Output directory
        output_dir = settings.value("output_dir", str(get_default_output_dir()))
        self.output_browser.setPath(output_dir)

        # Log level
        log_level = settings.value("log_level", "INFO")
        self.log_level_combo.setCurrentText(log_level)

        # Config file
        config_file = settings.value("config_file", "")
        self.config_browser.setPath(config_file)

    def _find_credentials(self) -> str:
        """Try to find credentials in default locations."""
        search_paths = [
            get_app_data_dir() / "credentials.json",
            Path.cwd() / "credentials.json",
            Path.home() / "credentials.json",
        ]
        for path in search_paths:
            if path.exists():
                return str(path)
        return ""

    def _on_settings_changed(self):
        """Save settings when changed."""
        settings = QSettings("GivingTuesday", "GDriveTools")
        settings.setValue("credentials_path", self.creds_browser.path())
        settings.setValue("output_dir", self.output_browser.path())
        settings.setValue("log_level", self.log_level_combo.currentText())
        settings.setValue("config_file", self.config_browser.path())
        self.settingsChanged.emit()

    def get_credentials_path(self) -> Optional[Path]:
        """Get the credentials path if valid."""
        path = self.creds_browser.path()
        if path and Path(path).exists():
            return Path(path)
        return None

    def get_output_dir(self) -> Path:
        """Get the output directory."""
        path = self.output_browser.path()
        if path:
            return Path(path)
        return get_default_output_dir()

    def get_log_level(self) -> str:
        """Get the selected log level."""
        return self.log_level_combo.currentText()

    def get_config_file(self) -> Optional[Path]:
        """Get the config file path if set."""
        path = self.config_browser.path()
        if path and Path(path).exists():
            return Path(path)
        return None

    def has_valid_credentials(self) -> bool:
        """Check if valid credentials are set."""
        return self.get_credentials_path() is not None
