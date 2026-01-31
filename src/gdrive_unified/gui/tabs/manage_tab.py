"""Manage tab for utility commands."""

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QPushButton,
    QTextEdit,
    QMessageBox,
)

from ..widgets import FileBrowser
from ..workers import ManageWorker


class ManageTab(QWidget):
    """Tab for management utilities."""

    logMessage = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Commands section
        commands_group = QGroupBox("Commands")
        commands_layout = QVBoxLayout(commands_group)

        # Command buttons row
        btn_layout = QHBoxLayout()

        self.init_config_btn = QPushButton("Init Config")
        self.init_config_btn.setToolTip("Create a new gdrive_config.yaml file")
        self.init_config_btn.clicked.connect(lambda: self._run_command("init-config"))
        btn_layout.addWidget(self.init_config_btn)

        self.status_btn = QPushButton("Show Status")
        self.status_btn.setToolTip("Show file status and relationships")
        self.status_btn.clicked.connect(lambda: self._run_command("status"))
        btn_layout.addWidget(self.status_btn)

        self.cleanup_btn = QPushButton("Cleanup")
        self.cleanup_btn.setToolTip("Clean up temporary files")
        self.cleanup_btn.clicked.connect(lambda: self._run_command("cleanup"))
        btn_layout.addWidget(self.cleanup_btn)

        self.version_btn = QPushButton("Version")
        self.version_btn.setToolTip("Show version information")
        self.version_btn.clicked.connect(lambda: self._run_command("version"))
        btn_layout.addWidget(self.version_btn)

        btn_layout.addStretch()
        commands_layout.addLayout(btn_layout)

        layout.addWidget(commands_group)

        # Options section (for status and cleanup)
        options_group = QGroupBox("Options (for Status/Cleanup)")
        options_layout = QFormLayout(options_group)

        self.downloads_dir_browser = FileBrowser(
            mode="directory",
            placeholder="downloads",
        )
        options_layout.addRow("Downloads Dir:", self.downloads_dir_browser)

        self.markdown_dir_browser = FileBrowser(
            mode="directory",
            placeholder="markdown",
        )
        options_layout.addRow("Markdown Dir:", self.markdown_dir_browser)

        self.url_mappings_browser = FileBrowser(
            mode="file",
            filter_str="JSON Files (*.json);;All Files (*)",
            placeholder="Optional: URL mappings file",
        )
        options_layout.addRow("URL Mappings:", self.url_mappings_browser)

        layout.addWidget(options_group)

        # Output section
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)
        output_layout.addWidget(self.output_text)

        # Clear button
        clear_btn = QPushButton("Clear Output")
        clear_btn.clicked.connect(self.output_text.clear)
        output_layout.addWidget(clear_btn)

        layout.addWidget(output_group)

    def _run_command(self, command: str):
        """Run a manage command."""
        # Confirm destructive operations
        if command == "cleanup":
            reply = QMessageBox.question(
                self,
                "Confirm Cleanup",
                "This will remove temporary files. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._set_ui_enabled(False)
        self.output_text.clear()

        # Get optional paths
        downloads_dir = None
        markdown_dir = None
        url_mappings = None

        if self.downloads_dir_browser.path():
            downloads_dir = Path(self.downloads_dir_browser.path())
        if self.markdown_dir_browser.path():
            markdown_dir = Path(self.markdown_dir_browser.path())
        if self.url_mappings_browser.path():
            url_mappings = Path(self.url_mappings_browser.path())

        self._worker = ManageWorker(
            command=command,
            downloads_dir=downloads_dir,
            markdown_dir=markdown_dir,
            url_mappings=url_mappings,
        )
        self._worker.output.connect(self._on_output)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_output(self, text: str):
        """Handle command output."""
        self.output_text.append(text)
        self.logMessage.emit(text)

    def _on_error(self, message: str):
        """Handle errors."""
        self.output_text.append(f"Error: {message}")
        self.logMessage.emit(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)
        self._set_ui_enabled(True)

    def _on_finished(self):
        """Handle completion."""
        self._set_ui_enabled(True)
        self._worker = None

    def _set_ui_enabled(self, enabled: bool):
        """Enable/disable UI elements."""
        self.init_config_btn.setEnabled(enabled)
        self.status_btn.setEnabled(enabled)
        self.cleanup_btn.setEnabled(enabled)
        self.version_btn.setEnabled(enabled)
        self.downloads_dir_browser.setEnabled(enabled)
        self.markdown_dir_browser.setEnabled(enabled)
        self.url_mappings_browser.setEnabled(enabled)
