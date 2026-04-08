"""Tests for credentials module."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from gdrive_unified.credentials import (
    get_config_dir,
    find_credentials_file,
    find_token_file,
    get_token_save_path,
    get_credentials_info,
    CREDENTIALS_FILE,
    CREDENTIALS_FILE_LEGACY,
    TOKEN_FILE,
    TOKEN_FILE_LEGACY,
)


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_macos(self) -> None:
        """Test macOS config directory."""
        with patch.object(sys, "platform", "darwin"):
            config_dir = get_config_dir()
            assert "Library/Application Support/gdrive-unified" in str(config_dir)

    def test_windows(self) -> None:
        """Test Windows config directory."""
        with patch.object(sys, "platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": "/fake/appdata"}):
                config_dir = get_config_dir()
                assert "gdrive-unified" in str(config_dir)

    def test_linux_xdg(self) -> None:
        """Test Linux with XDG_CONFIG_HOME."""
        with patch.object(sys, "platform", "linux"):
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
                config_dir = get_config_dir()
                assert config_dir == Path("/custom/config/gdrive-unified")

    def test_linux_default(self) -> None:
        """Test Linux without XDG_CONFIG_HOME."""
        with patch.object(sys, "platform", "linux"):
            with patch.dict(os.environ, {}, clear=True):
                # Need to handle HOME for Path.home()
                with patch.dict(os.environ, {"HOME": "/home/user"}):
                    config_dir = get_config_dir()
                    assert ".config/gdrive-unified" in str(config_dir)


class TestFindCredentialsFile:
    """Tests for find_credentials_file function."""

    def test_env_var_file(self) -> None:
        """Test finding via GDRIVE_CREDENTIALS_PATH pointing to file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            with patch.dict(os.environ, {"GDRIVE_CREDENTIALS_PATH": f.name}):
                result = find_credentials_file()
                assert result == Path(f.name)
            os.unlink(f.name)

    def test_env_var_dir(self) -> None:
        """Test finding via GDRIVE_CREDENTIALS_PATH pointing to directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            creds_file = Path(tmpdir) / CREDENTIALS_FILE
            creds_file.write_text("{}")

            with patch.dict(os.environ, {"GDRIVE_CREDENTIALS_PATH": tmpdir}):
                result = find_credentials_file()
                assert result == creds_file

    def test_cwd(self) -> None:
        """Test finding in current working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Resolve symlinks for macOS /private/var vs /var
            tmpdir_resolved = Path(tmpdir).resolve()
            creds_file = tmpdir_resolved / CREDENTIALS_FILE
            creds_file.write_text("{}")

            with patch.dict(os.environ, {}, clear=False):
                # Remove env var if set
                os.environ.pop("GDRIVE_CREDENTIALS_PATH", None)
                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir_resolved)
                    result = find_credentials_file()
                    assert result is not None
                    assert result.resolve() == creds_file.resolve()
                finally:
                    os.chdir(original_cwd)

    def test_not_found(self) -> None:
        """Test when credentials not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir) / "home"
            fake_home.mkdir()
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("GDRIVE_CREDENTIALS_PATH", None)
                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir)
                    # Mock config dir AND home dir (for ~/.google/ lookup)
                    # to be empty so we get a clean "not found" result.
                    with patch(
                        "gdrive_unified.credentials.get_config_dir",
                        return_value=Path(tmpdir) / "nonexistent",
                    ), patch(
                        "gdrive_unified.credentials.Path.home",
                        return_value=fake_home,
                    ), patch(
                        "gdrive_unified.credentials._get_bundled_credentials_path",
                        return_value=None,
                    ):
                        result = find_credentials_file()
                        assert result is None
                finally:
                    os.chdir(original_cwd)


class TestFindTokenFile:
    """Tests for find_token_file function."""

    def test_env_var_dir(self) -> None:
        """Test finding via GDRIVE_CREDENTIALS_PATH directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / TOKEN_FILE
            token_file.write_text("token")

            with patch.dict(os.environ, {"GDRIVE_CREDENTIALS_PATH": tmpdir}):
                result = find_token_file()
                assert result == token_file

    def test_cwd(self) -> None:
        """Test finding in current working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Resolve symlinks for macOS /private/var vs /var
            tmpdir_resolved = Path(tmpdir).resolve()
            token_file = tmpdir_resolved / TOKEN_FILE
            token_file.write_text("token")

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("GDRIVE_CREDENTIALS_PATH", None)
                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir_resolved)
                    result = find_token_file()
                    assert result is not None
                    assert result.resolve() == token_file.resolve()
                finally:
                    os.chdir(original_cwd)


class TestGetCredentialsInfo:
    """Tests for get_credentials_info function."""

    def test_returns_dict(self) -> None:
        """Test that get_credentials_info returns expected structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("GDRIVE_CREDENTIALS_PATH", None)
                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir)
                    info = get_credentials_info()
                    assert "config_directory" in info
                    assert "credentials_file" in info
                    assert "credentials_found" in info
                    assert "token_file" in info
                    assert "token_found" in info
                finally:
                    os.chdir(original_cwd)

    def test_env_override_reported(self) -> None:
        """Test that env override is reported."""
        with patch.dict(os.environ, {"GDRIVE_CREDENTIALS_PATH": "/some/path"}):
            info = get_credentials_info()
            assert info["env_override"] == "/some/path"


class TestFilenameFallback:
    """Regression tests for namespaced filename + legacy fallback."""

    def test_canonical_name_preferred_over_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / CREDENTIALS_FILE).write_text("canonical")
            (d / CREDENTIALS_FILE_LEGACY).write_text("legacy")
            with patch.dict(os.environ, {"GDRIVE_CREDENTIALS_PATH": str(d)}):
                result = find_credentials_file()
                assert result is not None
                assert result.name == CREDENTIALS_FILE

    def test_legacy_name_still_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / CREDENTIALS_FILE_LEGACY).write_text("legacy-only")
            with patch.dict(os.environ, {"GDRIVE_CREDENTIALS_PATH": str(d)}):
                result = find_credentials_file()
                assert result is not None
                assert result.name == CREDENTIALS_FILE_LEGACY

    def test_legacy_token_preserved_when_it_already_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            creds = d / CREDENTIALS_FILE
            creds.write_text("{}")
            legacy_token = d / TOKEN_FILE_LEGACY
            legacy_token.write_text("existing")
            save_path = get_token_save_path(creds)
            assert save_path == legacy_token

    def test_canonical_token_chosen_for_fresh_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            creds = d / CREDENTIALS_FILE
            creds.write_text("{}")
            save_path = get_token_save_path(creds)
            assert save_path == d / TOKEN_FILE
