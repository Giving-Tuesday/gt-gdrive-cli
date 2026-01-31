"""Unified configuration management for gdrive-unified.

This module provides configuration classes for all gdrive-unified functionality:
- Drive operations (download, search, upload)
- Document analysis
- GUI settings
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from .credentials import get_config_dir


class DriveConfig(BaseModel):
    """Configuration for Google Drive operations."""

    output_dir: Path = Field(
        default=Path("documents"),
        description="Directory to save downloaded files (relative to base directory)",
    )
    credentials_file: Optional[Path] = Field(
        default=None,
        description="Google API credentials file (auto-discovered if not set)",
    )
    token_file: Optional[Path] = Field(
        default=None,
        description="OAuth token storage file (auto-discovered if not set)",
    )
    batch_size: int = Field(default=10, description="Number of concurrent operations")
    default_mime_type: str = Field(
        default="text/markdown",
        description="Default MIME type for exports",
    )

    model_config = {"arbitrary_types_allowed": True}


class AnalyzerConfig(BaseModel):
    """Configuration for document analysis."""

    template: str = Field(
        default="aar",
        description="Default template to use for analysis",
    )
    output_format: str = Field(
        default="markdown",
        description="Default output format (markdown, json, csv)",
    )
    include_metadata: bool = Field(
        default=True,
        description="Include document metadata in analysis",
    )
    pattern_matching: bool = Field(
        default=True,
        description="Enable pattern matching in analysis",
    )

    model_config = {"arbitrary_types_allowed": True}


class GuiConfig(BaseModel):
    """Configuration for GUI application."""

    window_width: int = Field(default=1200, description="Default window width")
    window_height: int = Field(default=800, description="Default window height")
    theme: str = Field(default="system", description="Color theme (system, light, dark)")
    remember_position: bool = Field(
        default=True, description="Remember window position between sessions"
    )

    model_config = {"arbitrary_types_allowed": True}


class GlobalConfig(BaseModel):
    """Global configuration for gdrive-unified."""

    drive: DriveConfig = Field(default_factory=DriveConfig)
    analyzer: AnalyzerConfig = Field(default_factory=AnalyzerConfig)
    gui: GuiConfig = Field(default_factory=GuiConfig)
    working_dir: Path = Field(
        default_factory=Path.cwd,
        description="Base working directory",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    verbose: bool = Field(default=False, description="Enable verbose output")

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_yaml(cls, config_path: Path) -> "GlobalConfig":
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file.

        Returns:
            GlobalConfig instance with loaded settings.
        """
        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    def to_yaml(self, config_path: Path) -> None:
        """Save configuration to YAML file.

        Args:
            config_path: Path to save YAML configuration.
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert Path objects to strings for YAML serialization
        data = self.model_dump(mode="json")

        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def merge(self, overrides: Dict[str, Any]) -> "GlobalConfig":
        """Create a new config with overrides applied.

        Args:
            overrides: Dictionary of config values to override.

        Returns:
            New GlobalConfig instance with overrides applied.
        """
        current = self.model_dump()
        _deep_merge(current, overrides)
        return GlobalConfig(**current)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Deep merge override into base dict, modifying base in place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# Default config file locations
CONFIG_FILE_NAMES = [
    "gdrive.yaml",
    "gdrive.yml",
    "gdrive_config.yaml",
    "gdrive_config.yml",
    ".gdrive.yaml",
    ".gdrive.yml",
]


def find_config_file() -> Optional[Path]:
    """Find the configuration file.

    Search order:
    1. Current working directory
    2. Platform config directory

    Returns:
        Path to config file if found, None otherwise.
    """
    # Check current directory
    for name in CONFIG_FILE_NAMES:
        cwd_config = Path.cwd() / name
        if cwd_config.exists():
            return cwd_config

    # Check config directory
    config_dir = get_config_dir()
    for name in CONFIG_FILE_NAMES:
        config_path = config_dir / name
        if config_path.exists():
            return config_path

    return None


def get_config(config_path: Optional[Path] = None) -> GlobalConfig:
    """Get configuration from file or defaults.

    Args:
        config_path: Optional explicit path to config file.

    Returns:
        GlobalConfig instance.
    """
    if config_path is None:
        config_path = find_config_file()

    if config_path is not None:
        return GlobalConfig.from_yaml(config_path)

    return GlobalConfig()


def get_default_config_path() -> Path:
    """Get the default path for saving configuration.

    Returns:
        Path to default config file location.
    """
    return get_config_dir() / "gdrive.yaml"


def save_default_config(config: Optional[GlobalConfig] = None) -> Path:
    """Save configuration to the default location.

    Args:
        config: Configuration to save. Uses defaults if not provided.

    Returns:
        Path where config was saved.
    """
    if config is None:
        config = GlobalConfig()

    path = get_default_config_path()
    config.to_yaml(path)
    return path
