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
