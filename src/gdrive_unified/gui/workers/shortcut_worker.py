"""Background worker for creating shortcuts."""

from pathlib import Path
from typing import List, Dict

from PyQt5.QtCore import QThread, pyqtSignal

from gdrive_unified.config import DriveConfig
from gdrive_unified.drive import GoogleDriveSearcher


class ShortcutWorker(QThread):
    """Worker thread for creating Google Drive shortcuts."""

    progress = pyqtSignal(str)
    finished_with_results = pyqtSignal(int, int)  # created, skipped
    error = pyqtSignal(str)

    def __init__(
        self,
        credentials_path: Path,
        files: List[Dict],
        folder_id: str,
    ):
        super().__init__()
        self.credentials_path = credentials_path
        self.files = files
        self.folder_id = folder_id

    def run(self):
        """Execute the shortcut creation operation."""
        try:
            self.progress.emit(f"Creating shortcuts for {len(self.files)} files...")

            # Store token in same directory as credentials
            token_path = self.credentials_path.parent / "token.pickle"

            config = DriveConfig(
                credentials_file=self.credentials_path,
                token_file=token_path,
            )

            searcher = GoogleDriveSearcher(config)

            results = searcher.create_shortcuts(
                self.files,
                self.folder_id,
            )

            created = results.get("created", 0)
            skipped = results.get("skipped", 0)

            self.progress.emit(f"Created {created} shortcuts, skipped {skipped}")
            self.finished_with_results.emit(created, skipped)

        except Exception as e:
            self.error.emit(str(e))
