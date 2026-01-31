"""Search tab for finding files in Google Drive."""

from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QSizePolicy,
)

from ..widgets import ResultsTable
from ..workers import SearchWorker, DownloadWorker, ShortcutWorker


class SearchTab(QWidget):
    """Tab for searching Google Drive and managing results."""

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
        layout.setContentsMargins(5, 5, 5, 5)

        # Use a splitter so user can resize between options and results
        splitter = QSplitter(Qt.Vertical)

        # Top section: options in a scroll area
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)

        # Search criteria section
        criteria_group = QGroupBox("Search Criteria")
        criteria_layout = QFormLayout(criteria_group)

        # Pattern
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText("e.g., AAR*, *2024*, ^Report.*")
        criteria_layout.addRow("Pattern:", self.pattern_edit)

        # Scope and Since row
        scope_row = QHBoxLayout()
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["all", "personal", "shared"])
        scope_row.addWidget(self.scope_combo)
        scope_row.addWidget(QWidget())  # Spacer

        self.since_edit = QLineEdit()
        self.since_edit.setPlaceholderText("e.g., 7d, 30d, 2024-01-01")
        self.since_edit.setMaximumWidth(150)
        scope_row.addWidget(self.since_edit)

        scope_widget = QWidget()
        scope_widget.setLayout(scope_row)
        criteria_layout.addRow("Scope / Since:", scope_widget)

        # File types
        types_layout = QHBoxLayout()
        self.type_document = QCheckBox("Document")
        self.type_document.setChecked(True)
        types_layout.addWidget(self.type_document)
        self.type_spreadsheet = QCheckBox("Spreadsheet")
        types_layout.addWidget(self.type_spreadsheet)
        self.type_presentation = QCheckBox("Presentation")
        types_layout.addWidget(self.type_presentation)
        types_layout.addStretch()

        types_widget = QWidget()
        types_widget.setLayout(types_layout)
        criteria_layout.addRow("File Types:", types_widget)

        # Shared drive ID
        self.shared_drive_edit = QLineEdit()
        self.shared_drive_edit.setPlaceholderText("Optional: specific shared drive ID")
        criteria_layout.addRow("Shared Drive ID:", self.shared_drive_edit)

        # Max results
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 1000)
        self.max_results_spin.setValue(100)
        criteria_layout.addRow("Max Results:", self.max_results_spin)

        options_layout.addWidget(criteria_group)

        # Actions section
        actions_group = QGroupBox("Actions")
        actions_layout = QFormLayout(actions_group)

        # Download/convert toggles
        toggles_layout = QHBoxLayout()
        self.download_check = QCheckBox("Download files")
        self.download_check.setChecked(True)
        toggles_layout.addWidget(self.download_check)
        self.convert_check = QCheckBox("Convert to Markdown")
        self.convert_check.setChecked(True)
        toggles_layout.addWidget(self.convert_check)
        toggles_layout.addStretch()

        toggles_widget = QWidget()
        toggles_widget.setLayout(toggles_layout)
        actions_layout.addRow("Options:", toggles_widget)

        # Shortcuts folder ID
        self.shortcuts_edit = QLineEdit()
        self.shortcuts_edit.setPlaceholderText("Folder ID to create shortcuts in")
        actions_layout.addRow("Shortcuts Folder:", self.shortcuts_edit)

        # Search buttons
        btn_layout = QHBoxLayout()
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._start_search)
        btn_layout.addWidget(self.search_btn)

        self.search_shortcuts_btn = QPushButton("Search + Create Shortcuts")
        self.search_shortcuts_btn.clicked.connect(self._start_search_with_shortcuts)
        btn_layout.addWidget(self.search_shortcuts_btn)
        btn_layout.addStretch()

        actions_layout.addRow("", btn_layout)
        options_layout.addWidget(actions_group)

        # Wrap options in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(options_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setMinimumHeight(200)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        splitter.addWidget(scroll_area)

        # Results section - should expand
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)

        self.results_table = ResultsTable()
        self.results_table.selectionChanged.connect(self._update_action_buttons)
        self.results_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        results_layout.addWidget(self.results_table, 1)  # stretch factor 1

        # Result action buttons
        result_btn_layout = QHBoxLayout()
        self.download_selected_btn = QPushButton("Download Selected")
        self.download_selected_btn.clicked.connect(self._download_selected)
        self.download_selected_btn.setEnabled(False)
        result_btn_layout.addWidget(self.download_selected_btn)

        self.download_all_btn = QPushButton("Download All")
        self.download_all_btn.clicked.connect(self._download_all)
        self.download_all_btn.setEnabled(False)
        result_btn_layout.addWidget(self.download_all_btn)

        self.create_shortcuts_btn = QPushButton("Create Shortcuts")
        self.create_shortcuts_btn.clicked.connect(self._create_shortcuts)
        self.create_shortcuts_btn.setEnabled(False)
        result_btn_layout.addWidget(self.create_shortcuts_btn)

        result_btn_layout.addStretch()
        results_layout.addLayout(result_btn_layout)

        results_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(results_group)

        # Set initial splitter sizes (options smaller, results larger)
        splitter.setSizes([250, 400])
        splitter.setStretchFactor(0, 0)  # Options don't stretch
        splitter.setStretchFactor(1, 1)  # Results stretch

        layout.addWidget(splitter, 1)

    def _get_file_types(self):
        """Get selected file types."""
        types = []
        if self.type_document.isChecked():
            types.append("document")
        if self.type_spreadsheet.isChecked():
            types.append("spreadsheet")
        if self.type_presentation.isChecked():
            types.append("presentation")
        return types if types else ["document"]

    def _parse_since_date(self) -> Optional[datetime]:
        """Parse the since date field."""
        text = self.since_edit.text().strip()
        if not text:
            return None

        # Try relative format (7d, 2w, 1m)
        import re
        match = re.match(r"^(\d+)([dhwm])$", text.lower())
        if match:
            from datetime import timedelta
            value = int(match.group(1))
            unit = match.group(2)
            delta_map = {
                "h": timedelta(hours=value),
                "d": timedelta(days=value),
                "w": timedelta(weeks=value),
                "m": timedelta(days=value * 30),
            }
            return datetime.now() - delta_map.get(unit, timedelta())

        # Try ISO date format
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _start_search(self):
        """Start a search operation."""
        self._run_search(create_shortcuts=False)

    def _start_search_with_shortcuts(self):
        """Start search and create shortcuts."""
        if not self.shortcuts_edit.text().strip():
            QMessageBox.warning(
                self,
                "Shortcuts Folder Required",
                "Please enter a folder ID to create shortcuts in.",
            )
            return
        self._run_search(create_shortcuts=True)

    def _run_search(self, create_shortcuts: bool = False):
        """Execute the search."""
        creds = self.get_credentials()
        if not creds:
            QMessageBox.warning(
                self,
                "Credentials Required",
                "Please configure credentials in the Settings tab.",
            )
            return

        pattern = self.pattern_edit.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Pattern Required", "Please enter a search pattern.")
            return

        self._set_ui_enabled(False)
        self._create_shortcuts_after = create_shortcuts

        self._worker = SearchWorker(
            credentials_path=creds,
            pattern=pattern,
            scope=self.scope_combo.currentText(),
            file_types=self._get_file_types(),
            max_results=self.max_results_spin.value(),
            since_date=self._parse_since_date(),
            shared_drive_id=self.shared_drive_edit.text().strip() or None,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.resultsReady.connect(self._on_search_complete)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_search_complete(self, results):
        """Handle search results."""
        self.results_table.populate(results)

        # Auto-download if enabled
        if self.download_check.isChecked() and results:
            self._download_files(results)
        elif self._create_shortcuts_after and results:
            self._create_shortcuts_for_files(results)

    def _download_selected(self):
        """Download selected files."""
        files = self.results_table.get_selected()
        if files:
            self._download_files(files)

    def _download_all(self):
        """Download all result files."""
        files = self.results_table.get_all()
        if files:
            self._download_files(files)

    def _download_files(self, files):
        """Download the specified files."""
        creds = self.get_credentials()
        if not creds:
            return

        self._set_ui_enabled(False)

        self._worker = DownloadWorker(
            credentials_path=creds,
            output_dir=self.get_output_dir(),
            files=files,
            convert=self.convert_check.isChecked(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.conversionProgress.connect(self._on_progress)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.start()

    def _on_download_finished(self):
        """Handle download completion."""
        self._set_ui_enabled(True)
        self._worker = None

        # Create shortcuts if that was requested
        if self._create_shortcuts_after:
            files = self.results_table.get_all()
            if files:
                self._create_shortcuts_for_files(files)
            self._create_shortcuts_after = False

    def _create_shortcuts(self):
        """Create shortcuts for selected or all files."""
        files = self.results_table.get_selected()
        if not files:
            files = self.results_table.get_all()
        if files:
            self._create_shortcuts_for_files(files)

    def _create_shortcuts_for_files(self, files):
        """Create shortcuts for the given files."""
        folder_id = self.shortcuts_edit.text().strip()
        if not folder_id:
            QMessageBox.warning(
                self,
                "Folder ID Required",
                "Please enter a folder ID to create shortcuts in.",
            )
            return

        creds = self.get_credentials()
        if not creds:
            return

        self._set_ui_enabled(False)

        self._worker = ShortcutWorker(
            credentials_path=creds,
            files=files,
            folder_id=folder_id,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_progress(self, message: str):
        """Handle progress messages."""
        self.logMessage.emit(message)

    def _on_error(self, message: str):
        """Handle errors."""
        self.logMessage.emit(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)
        self._set_ui_enabled(True)

    def _on_worker_finished(self):
        """Handle worker completion."""
        self._set_ui_enabled(True)
        self._worker = None

    def _update_action_buttons(self):
        """Update action button states based on results."""
        has_results = self.results_table.has_results()
        has_selection = self.results_table.has_selection()

        self.download_selected_btn.setEnabled(has_selection)
        self.download_all_btn.setEnabled(has_results)
        self.create_shortcuts_btn.setEnabled(has_results)

    def _set_ui_enabled(self, enabled: bool):
        """Enable/disable UI elements during operations."""
        self.pattern_edit.setEnabled(enabled)
        self.scope_combo.setEnabled(enabled)
        self.since_edit.setEnabled(enabled)
        self.type_document.setEnabled(enabled)
        self.type_spreadsheet.setEnabled(enabled)
        self.type_presentation.setEnabled(enabled)
        self.shared_drive_edit.setEnabled(enabled)
        self.max_results_spin.setEnabled(enabled)
        self.download_check.setEnabled(enabled)
        self.convert_check.setEnabled(enabled)
        self.shortcuts_edit.setEnabled(enabled)
        self.search_btn.setEnabled(enabled)
        self.search_shortcuts_btn.setEnabled(enabled)
        self.results_table.setEnabled(enabled)

        if enabled:
            self._update_action_buttons()
        else:
            self.download_selected_btn.setEnabled(False)
            self.download_all_btn.setEnabled(False)
            self.create_shortcuts_btn.setEnabled(False)
