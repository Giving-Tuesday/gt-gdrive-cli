"""Thread-safe log panel widget."""

import logging
from typing import Optional

from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QApplication,
)


class LogSignalHandler(logging.Handler, QObject):
    """Thread-safe logging handler that emits Qt signals."""

    logMessage = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record)
        self.logMessage.emit(msg)


class LogPanel(QWidget):
    """A collapsible log output panel."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        layout.addWidget(self.log_text)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        # Set up log handler
        self.log_handler = LogSignalHandler()
        self.log_handler.logMessage.connect(self.append_message)

    def get_handler(self) -> LogSignalHandler:
        """Get the logging handler to attach to loggers."""
        return self.log_handler

    def append_message(self, message: str):
        """Append a message to the log (thread-safe via signal)."""
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def log(self, message: str):
        """Direct logging method for simple messages."""
        self.append_message(message)

    def clear(self):
        """Clear the log."""
        self.log_text.clear()

    def _copy_to_clipboard(self):
        """Copy log contents to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.log_text.toPlainText())

    def get_text(self) -> str:
        """Get all log text."""
        return self.log_text.toPlainText()
