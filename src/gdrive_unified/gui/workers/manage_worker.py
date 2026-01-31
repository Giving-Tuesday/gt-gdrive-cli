"""Background worker for manage commands."""

import io
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal


class ManageWorker(QThread):
    """Worker thread for running manage commands."""

    output = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        command: str,
        downloads_dir: Optional[Path] = None,
        markdown_dir: Optional[Path] = None,
        url_mappings: Optional[Path] = None,
        config_file: Optional[Path] = None,
    ):
        super().__init__()
        self.command = command
        self.downloads_dir = downloads_dir
        self.markdown_dir = markdown_dir
        self.url_mappings = url_mappings
        self.config_file = config_file

    def run(self):
        """Execute the manage command."""
        try:
            if self.command == "version":
                self._run_version()
            elif self.command == "init-config":
                self._run_init_config()
            elif self.command == "status":
                self._run_status()
            elif self.command == "cleanup":
                self._run_cleanup()
            else:
                self.error.emit(f"Unknown command: {self.command}")

        except Exception as e:
            self.error.emit(str(e))

    def _run_version(self):
        """Show version information."""
        try:
            from importlib.metadata import version
            ver = version("gdrive-download")
        except Exception:
            ver = "unknown"
        self.output.emit(f"gdrive-download version: {ver}")

    def _run_init_config(self):
        """Initialize configuration file."""
        from gdrive_unified.config import GlobalConfig

        config_path = Path("gdrive_config.yaml")
        if config_path.exists():
            self.output.emit(f"Config file already exists: {config_path}")
            return

        config = GlobalConfig()
        # Write default config
        import yaml
        with open(config_path, "w") as f:
            yaml.dump(config.model_dump(), f, default_flow_style=False)

        self.output.emit(f"Created configuration file: {config_path}")

    def _run_status(self):
        """Show status of files and relationships."""
        downloads_dir = self.downloads_dir or Path("downloads")
        markdown_dir = self.markdown_dir or Path("markdown")

        output_lines = ["=== File Status ===", ""]

        # Count downloads
        if downloads_dir.exists():
            doc_count = len(list(downloads_dir.glob("*")))
            output_lines.append(f"Documents directory: {downloads_dir}")
            output_lines.append(f"  Files: {doc_count}")
        else:
            output_lines.append(f"Documents directory not found: {downloads_dir}")

        output_lines.append("")

        # Count markdown
        if markdown_dir.exists():
            md_count = len(list(markdown_dir.glob("*.md")))
            output_lines.append(f"Markdown directory: {markdown_dir}")
            output_lines.append(f"  Files: {md_count}")
        else:
            output_lines.append(f"Markdown directory not found: {markdown_dir}")

        # URL mappings
        if self.url_mappings and self.url_mappings.exists():
            output_lines.append("")
            output_lines.append(f"URL mappings: {self.url_mappings}")

        self.output.emit("\n".join(output_lines))

    def _run_cleanup(self):
        """Clean up temporary files."""
        downloads_dir = self.downloads_dir or Path("downloads")
        markdown_dir = self.markdown_dir or Path("markdown")

        output_lines = ["=== Cleanup ===", ""]

        # Look for temp files
        temp_patterns = ["*.tmp", "~*", ".DS_Store"]
        cleaned = 0

        for directory in [downloads_dir, markdown_dir]:
            if directory.exists():
                for pattern in temp_patterns:
                    for f in directory.glob(pattern):
                        try:
                            f.unlink()
                            cleaned += 1
                            output_lines.append(f"Removed: {f}")
                        except Exception as e:
                            output_lines.append(f"Failed to remove {f}: {e}")

        if cleaned == 0:
            output_lines.append("No temporary files found to clean up.")
        else:
            output_lines.append(f"\nCleaned up {cleaned} files.")

        self.output.emit("\n".join(output_lines))
