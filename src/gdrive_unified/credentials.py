"""Centralized credential management for gdrive-unified.

This module provides cross-platform credential storage following XDG spec
on Linux, standard paths on macOS/Windows, with environment variable overrides.

Storage locations:
- Linux: ~/.config/gdrive-unified/
- macOS: ~/Library/Application Support/gdrive-unified/
- Windows: %APPDATA%/gdrive-unified/

Search order:
1. GDRIVE_CREDENTIALS_PATH environment variable
2. Current working directory (for development)
3. XDG/platform config directory (production)
"""

import os
import pickle
import sys
from pathlib import Path
from typing import Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Default OAuth scopes for Google Drive operations
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

# Credential file names
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"


def get_config_dir() -> Path:
    """Get the platform-specific config directory.

    Returns:
        Path to the config directory for gdrive-unified.
    """
    if sys.platform == "darwin":
        # macOS
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        # Windows
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        # Linux and others - use XDG spec
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            base = Path(xdg_config)
        else:
            base = Path.home() / ".config"

    return base / "gdrive-unified"


def find_credentials_file() -> Optional[Path]:
    """Find the credentials.json file.

    Search order:
    1. GDRIVE_CREDENTIALS_PATH environment variable
    2. Current working directory
    3. Platform config directory

    Returns:
        Path to credentials.json if found, None otherwise.
    """
    # 1. Environment variable
    env_path = os.environ.get("GDRIVE_CREDENTIALS_PATH")
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
        # If env var points to a directory, look for credentials.json in it
        if path.is_dir():
            cred_file = path / CREDENTIALS_FILE
            if cred_file.exists():
                return cred_file

    # 2. Current working directory
    cwd_creds = Path.cwd() / CREDENTIALS_FILE
    if cwd_creds.exists():
        return cwd_creds

    # 3. Platform config directory
    config_creds = get_config_dir() / CREDENTIALS_FILE
    if config_creds.exists():
        return config_creds

    return None


def find_token_file() -> Optional[Path]:
    """Find the token.pickle file.

    Search order:
    1. GDRIVE_CREDENTIALS_PATH environment variable directory
    2. Current working directory
    3. Platform config directory

    Returns:
        Path to token.pickle if found, None otherwise.
    """
    # 1. Environment variable (directory)
    env_path = os.environ.get("GDRIVE_CREDENTIALS_PATH")
    if env_path:
        path = Path(env_path)
        if path.is_dir():
            token_file = path / TOKEN_FILE
            if token_file.exists():
                return token_file
        elif path.is_file():
            # If pointing to credentials.json, look in same directory
            token_file = path.parent / TOKEN_FILE
            if token_file.exists():
                return token_file

    # 2. Current working directory
    cwd_token = Path.cwd() / TOKEN_FILE
    if cwd_token.exists():
        return cwd_token

    # 3. Platform config directory
    config_token = get_config_dir() / TOKEN_FILE
    if config_token.exists():
        return config_token

    return None


def get_token_save_path() -> Path:
    """Get the path where tokens should be saved.

    Prefers saving next to credentials file, falls back to config directory.

    Returns:
        Path where token.pickle should be saved.
    """
    credentials_file = find_credentials_file()
    if credentials_file:
        return credentials_file.parent / TOKEN_FILE

    # Default to config directory
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / TOKEN_FILE


def get_credentials(
    scopes: Optional[list[str]] = None,
    credentials_path: Optional[Path] = None,
    token_path: Optional[Path] = None,
) -> Credentials:
    """Get or create OAuth2 credentials for Google APIs.

    This function will:
    1. Load existing credentials from token file if available and valid
    2. Refresh credentials if expired but refresh token is available
    3. Run OAuth flow to obtain new credentials if needed

    Args:
        scopes: OAuth scopes to request. Defaults to Drive and Docs access.
        credentials_path: Path to credentials.json. Auto-discovered if not provided.
        token_path: Path to token.pickle. Auto-discovered if not provided.

    Returns:
        Valid Google OAuth2 Credentials object.

    Raises:
        FileNotFoundError: If credentials.json cannot be found.
        ValueError: If OAuth flow fails.
    """
    if scopes is None:
        scopes = DEFAULT_SCOPES

    creds = None

    # Try to load existing token
    if token_path is None:
        token_path = find_token_file()

    if token_path and token_path.exists():
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # Check if credentials are valid or can be refreshed
    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token
        save_path = token_path or get_token_save_path()
        with open(save_path, "wb") as token:
            pickle.dump(creds, token)
        return creds

    # Need to run OAuth flow
    if credentials_path is None:
        credentials_path = find_credentials_file()

    if credentials_path is None or not credentials_path.exists():
        raise FileNotFoundError(
            "Could not find credentials.json. Please either:\n"
            "1. Set GDRIVE_CREDENTIALS_PATH environment variable\n"
            "2. Place credentials.json in current directory\n"
            f"3. Place credentials.json in {get_config_dir()}\n"
            "\nTo obtain credentials.json, visit the Google Cloud Console:\n"
            "https://console.cloud.google.com/apis/credentials"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    creds = flow.run_local_server(port=0)

    # Save the token
    save_path = token_path or get_token_save_path()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as token:
        pickle.dump(creds, token)

    return creds


def get_credentials_info() -> dict:
    """Get information about current credential configuration.

    Returns:
        Dictionary with credential file locations and status.
    """
    creds_file = find_credentials_file()
    token_file = find_token_file()
    config_dir = get_config_dir()

    info = {
        "config_directory": str(config_dir),
        "credentials_file": str(creds_file) if creds_file else None,
        "credentials_found": creds_file is not None,
        "token_file": str(token_file) if token_file else None,
        "token_found": token_file is not None,
        "env_override": os.environ.get("GDRIVE_CREDENTIALS_PATH"),
    }

    # Check token validity if it exists
    if token_file and token_file.exists():
        try:
            with open(token_file, "rb") as f:
                creds = pickle.load(f)
            info["token_valid"] = creds.valid
            info["token_expired"] = creds.expired if hasattr(creds, "expired") else None
            info["has_refresh_token"] = creds.refresh_token is not None
        except Exception as e:
            info["token_valid"] = False
            info["token_error"] = str(e)
    else:
        info["token_valid"] = False

    return info


def setup_credentials_interactive() -> Tuple[Path, Path]:
    """Interactive setup for credentials.

    Guides user through placing credentials.json and running OAuth flow.

    Returns:
        Tuple of (credentials_path, token_path) after successful setup.
    """
    from rich.console import Console
    from rich.prompt import Confirm, Prompt

    console = Console()
    config_dir = get_config_dir()

    console.print("\n[bold]Google Drive Credentials Setup[/bold]\n")
    console.print(f"Config directory: [cyan]{config_dir}[/cyan]\n")

    # Check for existing credentials
    existing_creds = find_credentials_file()
    if existing_creds:
        console.print(f"[green]Found existing credentials:[/green] {existing_creds}")
        if not Confirm.ask("Use these credentials?", default=True):
            existing_creds = None

    if not existing_creds:
        console.print("\n[yellow]No credentials.json found.[/yellow]")
        console.print("\nTo obtain credentials.json:")
        console.print("1. Go to [link]https://console.cloud.google.com/apis/credentials[/link]")
        console.print("2. Create OAuth 2.0 Client ID (Desktop application)")
        console.print("3. Download the JSON file")
        console.print(f"\nPlace the file at: [cyan]{config_dir / CREDENTIALS_FILE}[/cyan]")
        console.print("Or in your current directory.")

        input("\nPress Enter when ready...")

        existing_creds = find_credentials_file()
        if not existing_creds:
            raise FileNotFoundError("credentials.json still not found. Setup aborted.")

    # Run OAuth flow
    console.print("\n[bold]Starting OAuth flow...[/bold]")
    console.print("A browser window will open for authentication.\n")

    creds = get_credentials(credentials_path=existing_creds)
    token_path = get_token_save_path()

    console.print(f"\n[green]Setup complete![/green]")
    console.print(f"Credentials: {existing_creds}")
    console.print(f"Token saved: {token_path}")

    return existing_creds, token_path
