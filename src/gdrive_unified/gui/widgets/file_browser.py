"""File/directory browser widget with status indicator."""

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QLabel,
)


class FileBrowser(QWidget):
    """A widget combining a path input, browse button, and optional status."""

    pathChanged = pyqtSignal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        mode: str = "file",  # "file" or "directory"
        filter_str: str = "",
        placeholder: str = "",
        show_status: bool = False,
    ):
        super().__init__(parent)
        self.mode = mode
        self.filter_str = filter_str
        self.show_status = show_status

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Status label (optional)
        if show_status:
            self.status_label = QLabel("Not set")
            self.status_label.setMinimumWidth(80)
            layout.addWidget(self.status_label)

        # Path input
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(placeholder)
        self.path_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.path_edit, 1)

        # Browse button
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse)
        layout.addWidget(self.browse_btn)

    def _browse(self):
        """Open file/directory dialog."""
        if self.mode == "directory":
            path = QFileDialog.getExistingDirectory(
                self,
                "Select Directory",
                self.path_edit.text() or str(Path.home()),
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select File",
                self.path_edit.text() or str(Path.home()),
                self.filter_str,
            )

        if path:
            self.path_edit.setText(path)

    def _on_text_changed(self, text: str):
        """Handle text changes and update status."""
        if self.show_status:
            path = Path(text) if text else None
            if path and path.exists():
                self.status_label.setText("Found")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
            elif text:
                self.status_label.setText("Not found")
                self.status_label.setStyleSheet("color: red;")
            else:
                self.status_label.setText("Not set")
                self.status_label.setStyleSheet("color: gray;")

        self.pathChanged.emit(text)

    def path(self) -> str:
        """Get current path."""
        return self.path_edit.text()

    def setPath(self, path: str):
        """Set the path."""
        self.path_edit.setText(path)

    def setEnabled(self, enabled: bool):
        """Enable/disable the widget."""
        self.path_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
