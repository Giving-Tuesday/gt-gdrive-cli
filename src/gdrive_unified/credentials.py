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
4. ~/.google/ (common user location)
5. Bundled package data (built-in fallback)
"""

import os
import pickle
import sys
from pathlib import Path
from typing import Optional, Tuple

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Default OAuth scopes for Google Drive operations
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

# Credential file names. The canonical (preferred) name is namespaced to
# avoid collisions with other Google tools that also use ~/.google/credentials.json
# (gspread, google-api-python-client quickstarts, etc.). The generic name is
# retained as a fallback so existing installs keep working.
CREDENTIALS_FILE = "gdrive-unified-credentials.json"
CREDENTIALS_FILE_LEGACY = "credentials.json"
CREDENTIALS_FILENAMES = (CREDENTIALS_FILE, CREDENTIALS_FILE_LEGACY)

TOKEN_FILE = "gdrive-unified-token.pickle"
TOKEN_FILE_LEGACY = "token.pickle"
TOKEN_FILENAMES = (TOKEN_FILE, TOKEN_FILE_LEGACY)


def _first_existing(directory: Path, names) -> Optional[Path]:
    """Return the first existing file from `names` inside `directory`, or None."""
    for name in names:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


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


def _get_bundled_credentials_path() -> Optional[Path]:
    """Get path to bundled credentials.json shipped with the package.

    Returns:
        Path to bundled credentials.json if it exists and contains real
        credentials (not placeholder), None otherwise.
    """
    # Try importlib.resources first (works with installed packages)
    try:
        from importlib.resources import files

        data_path = files("gdrive_unified") / "data" / "credentials.json"
        resolved = Path(str(data_path))
        if resolved.is_file():
            return resolved
    except (ImportError, TypeError, FileNotFoundError):
        pass

    # Fallback: relative path from this file (works with editable installs)
    bundled = Path(__file__).parent / "data" / "credentials.json"
    if bundled.exists():
        return bundled

    return None


def _is_placeholder_credentials(path: Path) -> bool:
    """Check if a credentials file contains placeholder values.

    Returns:
        True if the file contains placeholder client_id values.
    """
    try:
        import json

        with open(path) as f:
            data = json.load(f)
        client_id = data.get("installed", {}).get("client_id", "")
        return "REPLACE_WITH" in client_id
    except Exception:
        return False


def is_bundled_credentials(path: Path) -> bool:
    """Check if a credentials path points to the bundled package credentials.

    Args:
        path: Path to check.

    Returns:
        True if this is the bundled credentials file.
    """
    bundled = _get_bundled_credentials_path()
    if bundled is None:
        return False
    try:
        return path.resolve() == bundled.resolve()
    except (OSError, ValueError):
        return False


def find_credentials_file() -> Optional[Path]:
    """Find the credentials.json file.

    Search order:
    1. GDRIVE_CREDENTIALS_PATH environment variable
    2. Current working directory
    3. Platform config directory
    4. Bundled package data (built-in fallback)

    Returns:
        Path to credentials.json if found, None otherwise.
    """
    # 1. Environment variable
    env_path = os.environ.get("GDRIVE_CREDENTIALS_PATH")
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
        # If env var points to a directory, try preferred then legacy filename
        if path.is_dir():
            found = _first_existing(path, CREDENTIALS_FILENAMES)
            if found is not None:
                return found

    # 2. Current working directory
    found = _first_existing(Path.cwd(), CREDENTIALS_FILENAMES)
    if found is not None:
        return found

    # 3. Platform config directory
    found = _first_existing(get_config_dir(), CREDENTIALS_FILENAMES)
    if found is not None:
        return found

    # 4. ~/.google/ (common user location; works on macOS/Linux/Windows)
    found = _first_existing(Path.home() / ".google", CREDENTIALS_FILENAMES)
    if found is not None:
        return found

    # 5. Bundled package data (lowest priority)
    bundled = _get_bundled_credentials_path()
    if bundled is not None and not _is_placeholder_credentials(bundled):
        return bundled

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
    # 1. Environment variable (directory or file)
    env_path = os.environ.get("GDRIVE_CREDENTIALS_PATH")
    if env_path:
        path = Path(env_path)
        if path.is_dir():
            found = _first_existing(path, TOKEN_FILENAMES)
            if found is not None:
                return found
        elif path.is_file():
            # If pointing to credentials file, look in the same directory
            found = _first_existing(path.parent, TOKEN_FILENAMES)
            if found is not None:
                return found

    # 2. Current working directory
    found = _first_existing(Path.cwd(), TOKEN_FILENAMES)
    if found is not None:
        return found

    # 3. Platform config directory
    found = _first_existing(get_config_dir(), TOKEN_FILENAMES)
    if found is not None:
        return found

    # 4. ~/.google/ (common user location)
    found = _first_existing(Path.home() / ".google", TOKEN_FILENAMES)
    if found is not None:
        return found

    return None


def get_token_save_path(credentials_file: Optional[Path] = None) -> Path:
    """Get the path where tokens should be saved.

    When using bundled credentials, tokens are always saved to the platform
    config directory (never inside the package installation). Otherwise,
    prefers saving next to credentials file.

    Args:
        credentials_file: The credentials file being used. If None, auto-discovered.

    Returns:
        Path where token.pickle should be saved.
    """
    if credentials_file is None:
        credentials_file = find_credentials_file()

    # When using bundled credentials, always save to config dir under the
    # canonical (namespaced) filename.
    if credentials_file and is_bundled_credentials(credentials_file):
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / TOKEN_FILE

    # Save next to credentials file. If a legacy token already exists there,
    # keep writing to that path so existing installs aren't silently forked.
    if credentials_file:
        parent = credentials_file.parent
        legacy = parent / TOKEN_FILE_LEGACY
        if legacy.exists():
            return legacy
        return parent / TOKEN_FILE

    # Default to config directory under the canonical name.
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / TOKEN_FILE


def get_credentials(
    scopes: Optional[list] = None,
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
        try:
            creds.refresh(Request())
        except RefreshError as e:
            # Refresh token was revoked, expired (7-day limit for unpublished
            # OAuth apps), or the client_id changed. The stored token is now
            # useless — delete it and fall through to a fresh OAuth flow.
            stale_path = token_path
            try:
                if stale_path and stale_path.exists():
                    stale_path.unlink()
            except OSError:
                pass
            print(
                f"\nYour saved Google auth token is no longer valid "
                f"({e.__class__.__name__}: {e}).\n"
                f"Removed stale token at: {stale_path}\n"
                f"Re-running OAuth flow...\n"
            )
            creds = None
        else:
            # Save refreshed token
            save_path = token_path or get_token_save_path(credentials_path)
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
            f"4. Place credentials.json in {Path.home() / '.google'}\n"
            "\nTo obtain credentials.json, visit the Google Cloud Console:\n"
            "https://console.cloud.google.com/apis/credentials"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    creds = flow.run_local_server(port=0)

    # Save the token
    save_path = token_path or get_token_save_path(credentials_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as token:
        pickle.dump(creds, token)

    return creds


def ensure_authenticated() -> None:
    """Check if user is authenticated; if not, prompt for OAuth flow.

    Detects whether bundled or user-provided credentials are in use and
    shows appropriate messaging. Asks for confirmation before opening browser.

    Raises:
        click.Abort: If user declines authentication.
        FileNotFoundError: If no credentials.json can be found at all.
    """
    import click
    from rich.console import Console

    console = Console()

    # Check if token already exists
    token_file = find_token_file()
    if token_file and token_file.exists():
        try:
            with open(token_file, "rb") as f:
                creds = pickle.load(f)
            if creds and creds.valid:
                return
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError as e:
                    # Revoked or expired refresh token. Surface the reason,
                    # delete the stale file, and fall through to re-auth.
                    console.print(
                        f"[yellow]Saved token at {token_file} is no longer "
                        f"valid ({e.__class__.__name__}). "
                        f"Removing it and re-authenticating.[/yellow]"
                    )
                    try:
                        token_file.unlink()
                    except OSError:
                        pass
                else:
                    with open(token_file, "wb") as f:
                        pickle.dump(creds, f)
                    return
        except (pickle.UnpicklingError, EOFError, OSError) as e:
            console.print(
                f"[yellow]Saved token at {token_file} could not be loaded "
                f"({e.__class__.__name__}). Removing it and re-authenticating.[/yellow]"
            )
            try:
                token_file.unlink()
            except OSError:
                pass

    # No valid token — find credentials
    credentials_file = find_credentials_file()

    if credentials_file is None:
        console.print("\n[red bold]No credentials found.[/red bold]")
        console.print(
            "\nTo get started, you need a Google OAuth credentials file.\n"
            "Please either:\n"
            "  1. Set GDRIVE_CREDENTIALS_PATH environment variable\n"
            "  2. Place credentials.json in current directory\n"
            f"  3. Place credentials.json in {get_config_dir()}\n"
            f"  4. Place credentials.json in {Path.home() / '.google'}\n"
            "\nTo obtain credentials.json, visit the Google Cloud Console:\n"
            "  https://console.cloud.google.com/apis/credentials"
        )
        raise click.Abort()

    using_bundled = is_bundled_credentials(credentials_file)

    if using_bundled:
        console.print("\n[bold]First-time setup[/bold]")
        console.print(
            "This tool includes built-in Google OAuth credentials.\n"
            "You need to authorize access to your Google Drive account."
        )
    else:
        console.print("\n[bold]Authentication required[/bold]")
        console.print(
            f"Using credentials from: [cyan]{credentials_file}[/cyan]\n"
            "You need to complete the OAuth flow to authorize access."
        )

    console.print(
        "\nA browser window will open for you to sign in with your Google account."
    )

    if not click.confirm("Proceed with authentication?", default=True):
        raise click.Abort()

    get_credentials(credentials_path=credentials_file)
    console.print("[green]Authentication successful![/green]\n")


def get_credentials_info() -> dict:
    """Get information about current credential configuration.

    Returns:
        Dictionary with credential file locations and status.
    """
    creds_file = find_credentials_file()
    token_file = find_token_file()
    config_dir = get_config_dir()

    using_bundled = creds_file is not None and is_bundled_credentials(creds_file)

    info = {
        "config_directory": str(config_dir),
        "credentials_file": str(creds_file) if creds_file else None,
        "credentials_found": creds_file is not None,
        "using_bundled": using_bundled,
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
    When bundled credentials are available, skips the Google Cloud Console
    guidance and proceeds directly to OAuth.

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
        using_bundled = is_bundled_credentials(existing_creds)
        if using_bundled:
            console.print("[green]Using built-in credentials (bundled with package)[/green]")
        else:
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
    token_path = get_token_save_path(existing_creds)

    console.print(f"\n[green]Setup complete![/green]")
    console.print(f"Credentials: {existing_creds}")
    console.print(f"Token saved: {token_path}")

    return existing_creds, token_path
