"""Background worker for download operations."""

from pathlib import Path
from typing import List, Dict, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from gdrive_unified.config import DriveConfig
from gdrive_unified.drive import GoogleDriveDownloader, FileConverter


class DownloadWorker(QThread):
    """Worker thread for downloading files from Google Drive."""

    progress = pyqtSignal(str)
    fileDownloaded = pyqtSignal(str, str)  # filename, local_path
    conversionProgress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        credentials_path: Path,
        output_dir: Path,
        files: Optional[List[Dict]] = None,
        folder_url: Optional[str] = None,
        convert: bool = True,
        track_relationships: bool = True,
        documents_subdir: str = "documents",
        markdown_subdir: str = "markdown",
    ):
        super().__init__()
        self.credentials_path = credentials_path
        self.output_dir = output_dir
        self.files = files  # For downloading specific files from search results
        self.folder_url = folder_url  # For downloading entire folder
        self.convert = convert
        self.track_relationships = track_relationships
        self.documents_subdir = documents_subdir
        self.markdown_subdir = markdown_subdir

    def run(self):
        """Execute the download operation."""
        try:
            # Store token in same directory as credentials
            token_path = self.credentials_path.parent / "token.pickle"

            config = DriveConfig(
                credentials_file=self.credentials_path,
                token_file=token_path,
                output_dir=self.output_dir,
            )

            downloader = GoogleDriveDownloader(config)
            docs_dir = self.output_dir / self.documents_subdir
            docs_dir.mkdir(parents=True, exist_ok=True)

            if self.folder_url:
                # Download entire folder
                self.progress.emit(f"Downloading folder: {self.folder_url}")
                downloaded = downloader.download_folder(
                    self.folder_url,
                    docs_dir,
                    track_relationships=self.track_relationships,
                )
                self.progress.emit(f"Downloaded {len(downloaded)} files")

            elif self.files:
                # Download specific files
                total = len(self.files)
                for i, file_info in enumerate(self.files, 1):
                    if self.isInterruptionRequested():
                        self.progress.emit("Download cancelled")
                        return

                    name = file_info.get("name", "unknown")
                    file_id = file_info.get("id")
                    self.progress.emit(f"Downloading ({i}/{total}): {name}")

                    try:
                        local_path = downloader.download_file(
                            file_id,
                            docs_dir,
                            name,
                        )
                        if local_path:
                            self.fileDownloaded.emit(name, str(local_path))
                    except Exception as e:
                        self.progress.emit(f"Failed to download {name}: {e}")

                self.progress.emit(f"Downloaded {total} files")

            # Convert to markdown if requested
            if self.convert:
                markdown_dir = self.output_dir / self.markdown_subdir
                markdown_dir.mkdir(parents=True, exist_ok=True)

                self.conversionProgress.emit("Converting to markdown...")
                converter = FileConverter(
                    input_dir=docs_dir,
                    output_dir=markdown_dir,
                )
                converted = converter.convert_all_files()
                self.conversionProgress.emit(f"Converted {len(converted)} files to markdown")

            self.progress.emit("Download complete")

        except Exception as e:
            self.error.emit(str(e))
