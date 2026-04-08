"""CLI module for gdrive-unified.

This module provides both separate CLI commands (backwards compatible)
and a unified 'gdrive' entry point.

Separate commands:
- gdrive-download: Download files/folders
- gdrive-search: Search and create shortcuts
- gdrive-upload: Upload markdown as Google Docs
- gdrive-write-tab: Update existing doc tabs
- gdrive-manage: Config and status
- gdrive-analyze: Document analysis

Unified entry point:
- gdrive download
- gdrive search
- gdrive upload
- gdrive manage
- gdrive analyze
- gdrive init
- gdrive status
"""

import click

# Commands that require Google Drive authentication
AUTH_REQUIRED_COMMANDS = {"download", "search", "upload", "write-tab", "manage"}


@click.group()
@click.version_option(package_name="gdrive-unified")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """Unified Google Drive toolkit.

    A comprehensive toolkit for Google Drive operations and document analysis.

    Use 'gdrive COMMAND --help' for help on specific commands.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Auto-init: check authentication for commands that need it
    if ctx.invoked_subcommand in AUTH_REQUIRED_COMMANDS:
        from ..credentials import ensure_authenticated

        try:
            ensure_authenticated()
        except click.Abort:
            raise


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Setup credentials interactively.

    Guides you through:
    1. Locating or placing credentials.json
    2. Running the OAuth2 flow
    3. Saving the authentication token
    """
    from ..credentials import setup_credentials_interactive

    setup_credentials_interactive()


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show credential and configuration status."""
    from rich.console import Console
    from rich.table import Table

    from ..credentials import get_credentials_info
    from ..config import find_config_file

    console = Console()

    # Credential status
    cred_info = get_credentials_info()

    console.print("\n[bold]Credential Status[/bold]")
    cred_table = Table(show_header=False)
    cred_table.add_column("Property", style="cyan")
    cred_table.add_column("Value")

    cred_table.add_row("Config Directory", cred_info["config_directory"])

    # Show credentials file with bundled indicator
    creds_display = cred_info["credentials_file"] or "[red]Not found[/red]"
    if cred_info.get("using_bundled"):
        creds_display = f"{creds_display} [green](built-in)[/green]"
    cred_table.add_row("Credentials File", creds_display)

    cred_table.add_row(
        "Token File",
        cred_info["token_file"] or "[yellow]Not found[/yellow]",
    )
    cred_table.add_row(
        "Token Valid",
        "[green]Yes[/green]" if cred_info["token_valid"] else "[red]No[/red]",
    )
    if cred_info.get("env_override"):
        cred_table.add_row("Env Override", cred_info["env_override"])

    console.print(cred_table)

    # Config status
    console.print("\n[bold]Configuration Status[/bold]")
    config_file = find_config_file()
    if config_file:
        console.print(f"Config file: [cyan]{config_file}[/cyan]")
    else:
        console.print("Config file: [yellow]Using defaults[/yellow]")


@main.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Print a plaintext diagnostic for bug reports.

    Collects environment, install, and credential state in a copy-paste
    friendly format. Does not contact Google — safe to run when offline
    or when auth is broken.
    """
    import importlib
    import importlib.metadata
    import os
    import pickle
    import platform
    import shutil
    import sys

    from ..credentials import (
        CREDENTIALS_FILE,
        CREDENTIALS_FILE_LEGACY,
        TOKEN_FILE,
        TOKEN_FILE_LEGACY,
        find_credentials_file,
        find_token_file,
        get_config_dir,
        is_bundled_credentials,
    )
    from ..config import find_config_file

    lines: list[str] = []

    def section(title: str) -> None:
        lines.append("")
        lines.append(f"## {title}")

    def kv(k: str, v) -> None:
        lines.append(f"- {k}: {v}")

    lines.append("# gdrive doctor")
    lines.append("Paste this whole block into a bug report.")

    # --- Environment ---
    section("Environment")
    try:
        version = importlib.metadata.version("gdrive-unified")
    except importlib.metadata.PackageNotFoundError:
        version = "(not installed as a package)"
    kv("gdrive-unified", version)
    kv("python", sys.version.split()[0])
    kv("platform", f"{platform.system()} {platform.release()} ({platform.machine()})")
    kv("executable", sys.executable)
    kv("GDRIVE_CREDENTIALS_PATH", os.environ.get("GDRIVE_CREDENTIALS_PATH") or "(unset)")

    # --- Optional dependencies ---
    section("Optional dependencies")
    extras = {
        "mammoth": "[conversion] — DOCX→markdown",
        "markdownify": "[conversion] — HTML→markdown",
        "markdown_it": "[conversion] — markdown→Google Docs upload",
        "pypandoc": "[conversion] — Pandoc upload method",
        "pandas": "[analyzer] — document analysis",
        "PyQt5": "[gui] — desktop app",
    }
    for mod, label in extras.items():
        try:
            importlib.import_module(mod)
            kv(f"{mod} ({label})", "ok")
        except ImportError:
            kv(f"{mod} ({label})", "MISSING")

    pandoc_bin = shutil.which("pandoc")
    kv("pandoc binary", pandoc_bin or "MISSING (needed for --method pandoc)")

    # --- Credentials ---
    section("Credentials")
    kv("config directory", get_config_dir())
    kv("canonical creds filename", CREDENTIALS_FILE)
    kv("legacy creds filename", CREDENTIALS_FILE_LEGACY)
    kv("canonical token filename", TOKEN_FILE)
    kv("legacy token filename", TOKEN_FILE_LEGACY)

    creds_path = find_credentials_file()
    if creds_path is None:
        kv("credentials file", "NOT FOUND")
    else:
        kv("credentials file", creds_path)
        kv("  exists", creds_path.exists())
        kv("  bundled", is_bundled_credentials(creds_path))
        try:
            kv("  size", f"{creds_path.stat().st_size} bytes")
        except OSError as e:
            kv("  stat error", e)

    token_path = find_token_file()
    if token_path is None:
        kv("token file", "NOT FOUND")
    else:
        kv("token file", token_path)
        try:
            with open(token_path, "rb") as f:
                token_obj = pickle.load(f)
            kv("  loaded", "ok")
            kv("  valid", getattr(token_obj, "valid", "?"))
            kv("  expired", getattr(token_obj, "expired", "?"))
            kv("  has_refresh_token", bool(getattr(token_obj, "refresh_token", None)))
            scopes = getattr(token_obj, "scopes", None)
            if scopes:
                kv("  scopes", ", ".join(scopes))
        except Exception as e:
            kv("  load_error", f"{e.__class__.__name__}: {e}")

    # --- Config file ---
    section("Config file")
    cfg = find_config_file()
    kv("config file", cfg or "(none — using defaults)")

    # --- Emit ---
    click.echo("\n".join(lines))


# Import and add subcommands from individual modules
# Using lazy imports to avoid dependency issues

def _add_subcommands():
    """Add subcommands from individual CLI modules."""
    try:
        from .download import main as download_cmd
        main.add_command(download_cmd, name="download")
    except ImportError:
        pass

    try:
        from .search import search as search_cmd
        main.add_command(search_cmd, name="search")
    except ImportError:
        pass

    try:
        from .upload import upload as upload_cmd
        from .upload import write_to_doc as write_tab_cmd
        main.add_command(upload_cmd, name="upload")
        main.add_command(write_tab_cmd, name="write-tab")
    except ImportError:
        pass

    try:
        from .manage import main as manage_group
        main.add_command(manage_group, name="manage")
    except ImportError:
        pass

    try:
        from .analyze import main as analyze_cmd
        main.add_command(analyze_cmd, name="analyze")
    except ImportError:
        pass


_add_subcommands()


if __name__ == "__main__":
    main()
