"""Download tab for downloading entire folders."""

from pathlib import Path
from typing import Optional, Callable

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QMessageBox,
)

from ..workers import DownloadWorker


class DownloadTab(QWidget):
    """Tab for downloading entire Google Drive folders."""

    logMessage = pyqtSignal(str)

    def __init__(
        self,
        get_credentials: Callable[[], Optional[Path]],
        get_output_dir: Callable[[], Path],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.get_credentials = get_credentials
        self.get_output_dir = get_output_dir
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Folder download section
        folder_group = QGroupBox("Folder Download")
        folder_layout = QFormLayout(folder_group)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://drive.google.com/drive/folders/...")
        folder_layout.addRow("Folder URL:", self.url_edit)

        layout.addWidget(folder_group)

        # Options section
        options_group = QGroupBox("Options")
        options_layout = QFormLayout(options_group)

        self.convert_check = QCheckBox("Convert to Markdown")
        self.convert_check.setChecked(True)
        options_layout.addRow("", self.convert_check)

        self.track_check = QCheckBox("Track file relationships")
        self.track_check.setChecked(True)
        options_layout.addRow("", self.track_check)

        # Subdirectory names
        self.docs_subdir_edit = QLineEdit("documents")
        options_layout.addRow("Documents Subdir:", self.docs_subdir_edit)

        self.markdown_subdir_edit = QLineEdit("markdown")
        options_layout.addRow("Markdown Subdir:", self.markdown_subdir_edit)

        layout.addWidget(options_group)

        # Download button
        self.download_btn = QPushButton("Download Folder")
        self.download_btn.clicked.connect(self._start_download)
        layout.addWidget(self.download_btn)

        # Add stretch to push everything to top
        layout.addStretch()

    def _start_download(self):
        """Start the folder download."""
        creds = self.get_credentials()
        if not creds:
            QMessageBox.warning(
                self,
                "Credentials Required",
                "Please configure credentials in the Settings tab.",
            )
            return

        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Required", "Please enter a folder URL.")
            return

        if "drive.google.com" not in url:
            QMessageBox.warning(
                self,
                "Invalid URL",
                "Please enter a valid Google Drive folder URL.",
            )
            return

        self._set_ui_enabled(False)

        self._worker = DownloadWorker(
            credentials_path=creds,
            output_dir=self.get_output_dir(),
            folder_url=url,
            convert=self.convert_check.isChecked(),
            track_relationships=self.track_check.isChecked(),
            documents_subdir=self.docs_subdir_edit.text() or "documents",
            markdown_subdir=self.markdown_subdir_edit.text() or "markdown",
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.conversionProgress.connect(self._on_progress)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, message: str):
        """Handle progress messages."""
        self.logMessage.emit(message)

    def _on_error(self, message: str):
        """Handle errors."""
        self.logMessage.emit(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)
        self._set_ui_enabled(True)

    def _on_finished(self):
        """Handle completion."""
        self._set_ui_enabled(True)
        self._worker = None
        self.logMessage.emit("Folder download complete")

    def _set_ui_enabled(self, enabled: bool):
        """Enable/disable UI elements."""
        self.url_edit.setEnabled(enabled)
        self.convert_check.setEnabled(enabled)
        self.track_check.setEnabled(enabled)
        self.docs_subdir_edit.setEnabled(enabled)
        self.markdown_subdir_edit.setEnabled(enabled)
        self.download_btn.setEnabled(enabled)
