"""Tests for configuration module."""

import tempfile
from pathlib import Path

import pytest

from gdrive_unified.config import (
    GlobalConfig,
    DriveConfig,
    AnalyzerConfig,
    GuiConfig,
    get_config,
)


class TestDriveConfig:
    """Tests for DriveConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = DriveConfig()
        assert config.output_dir == Path("documents")
        assert config.batch_size == 10
        assert config.credentials_file is None
        assert config.token_file is None

    def test_custom_values(self) -> None:
        """Test custom values."""
        config = DriveConfig(
            output_dir=Path("/custom/path"),
            batch_size=20,
        )
        assert config.output_dir == Path("/custom/path")
        assert config.batch_size == 20


class TestAnalyzerConfig:
    """Tests for AnalyzerConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = AnalyzerConfig()
        assert config.template == "aar"
        assert config.output_format == "markdown"
        assert config.include_metadata is True
        assert config.pattern_matching is True


class TestGuiConfig:
    """Tests for GuiConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = GuiConfig()
        assert config.window_width == 1200
        assert config.window_height == 800
        assert config.theme == "system"
        assert config.remember_position is True


class TestGlobalConfig:
    """Tests for GlobalConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = GlobalConfig()
        assert isinstance(config.drive, DriveConfig)
        assert isinstance(config.analyzer, AnalyzerConfig)
        assert isinstance(config.gui, GuiConfig)
        assert config.log_level == "INFO"
        assert config.verbose is False

    def test_from_yaml(self) -> None:
        """Test loading from YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
drive:
  batch_size: 25
analyzer:
  template: custom
log_level: DEBUG
""")
            f.flush()
            config = GlobalConfig.from_yaml(Path(f.name))

        assert config.drive.batch_size == 25
        assert config.analyzer.template == "custom"
        assert config.log_level == "DEBUG"

    def test_to_yaml(self) -> None:
        """Test saving to YAML."""
        config = GlobalConfig()
        config.drive.batch_size = 30

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_config.yaml"
            config.to_yaml(path)

            # Reload and verify
            loaded = GlobalConfig.from_yaml(path)
            assert loaded.drive.batch_size == 30

    def test_merge(self) -> None:
        """Test merging overrides."""
        config = GlobalConfig()
        new_config = config.merge({"drive": {"batch_size": 50}})

        assert new_config.drive.batch_size == 50
        # Original unchanged
        assert config.drive.batch_size == 10

    def test_nonexistent_file(self) -> None:
        """Test loading from nonexistent file returns defaults."""
        config = GlobalConfig.from_yaml(Path("/nonexistent/path.yaml"))
        assert config.log_level == "INFO"


class TestGetConfig:
    """Tests for get_config function."""

    def test_returns_defaults(self) -> None:
        """Test that get_config returns defaults when no file found."""
        config = get_config(Path("/nonexistent/config.yaml"))
        assert isinstance(config, GlobalConfig)
        assert config.log_level == "INFO"
