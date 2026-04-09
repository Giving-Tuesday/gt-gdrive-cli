"""Smoke tests for CLI entry points.

These tests guard against startup-crash regressions by invoking each CLI
with --help, which exercises full module import + Click command setup.
Prior to this, a config refactor broke all three CLI tools with an
AttributeError on `config.downloader` that --help would have caught.
"""

from click.testing import CliRunner

from gdrive_unified.cli import main as gdrive_main
from gdrive_unified.cli.search import search
from gdrive_unified.cli.upload import upload
from gdrive_unified.cli.download import main as download_main


def test_search_help():
    result = CliRunner().invoke(search, ["--help"])
    assert result.exit_code == 0
    assert "Search" in result.output


def test_upload_help():
    result = CliRunner().invoke(upload, ["--help"])
    assert result.exit_code == 0
    assert "Upload" in result.output


def test_download_help():
    result = CliRunner().invoke(download_main, ["--help"])
    assert result.exit_code == 0


def test_pandoc_uploader_import_path():
    """Regression: the Pandoc upload path must not reference the legacy
    gdrive_download package (pre-unification import)."""
    from gdrive_unified.drive.pandoc_uploader import PandocUploader  # noqa: F401

    # Also assert the CLI's lazy import target exists on the expected module,
    # so renaming the class without updating cli/upload.py fails a test
    # rather than a user's live upload.
    import gdrive_unified.drive.pandoc_uploader as mod
    assert hasattr(mod, "PandocUploader")


def test_doctor_runs_offline():
    """`gdrive doctor` must never contact Google and must always exit 0."""
    result = CliRunner().invoke(gdrive_main, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "gdrive doctor" in result.output
    assert "## Environment" in result.output
    assert "## Credentials" in result.output


def test_search_config_attribute_exists():
    """Regression: GlobalConfig must expose the attribute the CLI writes to."""
    from gdrive_unified.config import GlobalConfig

    config = GlobalConfig()
    # This is the line that used to crash with AttributeError.
    assert hasattr(config, "drive")
    assert hasattr(config.drive, "credentials_file")
    assert hasattr(config.drive, "token_file")
    assert hasattr(config.drive, "output_dir")
