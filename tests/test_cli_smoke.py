"""Smoke tests for CLI entry points.

These tests guard against startup-crash regressions by invoking each CLI
with --help, which exercises full module import + Click command setup.
Prior to this, a config refactor broke all three CLI tools with an
AttributeError on `config.downloader` that --help would have caught.
"""

from click.testing import CliRunner

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


def test_search_config_attribute_exists():
    """Regression: GlobalConfig must expose the attribute the CLI writes to."""
    from gdrive_unified.config import GlobalConfig

    config = GlobalConfig()
    # This is the line that used to crash with AttributeError.
    assert hasattr(config, "drive")
    assert hasattr(config.drive, "credentials_file")
    assert hasattr(config.drive, "token_file")
    assert hasattr(config.drive, "output_dir")
