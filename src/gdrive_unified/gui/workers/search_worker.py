"""Background worker for search operations."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from gdrive_unified.config import DriveConfig
from gdrive_unified.drive import GoogleDriveSearcher


class SearchWorker(QThread):
    """Worker thread for searching Google Drive."""

    progress = pyqtSignal(str)
    resultsReady = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        credentials_path: Path,
        pattern: str,
        scope: str = "all",
        file_types: Optional[List[str]] = None,
        max_results: int = 100,
        since_date: Optional[datetime] = None,
        shared_drive_id: Optional[str] = None,
    ):
        super().__init__()
        self.credentials_path = credentials_path
        self.pattern = pattern
        self.scope = scope
        self.file_types = file_types or ["document"]
        self.max_results = max_results
        self.since_date = since_date
        self.shared_drive_id = shared_drive_id

    def run(self):
        """Execute the search operation."""
        try:
            self.progress.emit(f"Searching for: {self.pattern}")

            # Store token in same directory as credentials
            token_path = self.credentials_path.parent / "token.pickle"

            config = DriveConfig(
                credentials_file=self.credentials_path,
                token_file=token_path,
            )

            searcher = GoogleDriveSearcher(config)

            results = searcher.search_files(
                pattern=self.pattern,
                drive_scope=self.scope,
                shared_drive_id=self.shared_drive_id,
                file_types=self.file_types,
                max_results=self.max_results,
                since_date=self.since_date,
            )

            self.progress.emit(f"Found {len(results)} files")
            self.resultsReady.emit(results)

        except Exception as e:
            self.error.emit(str(e))
