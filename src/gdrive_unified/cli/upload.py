"""CLI command for uploading markdown files to Google Drive as native Google Docs."""

from pathlib import Path
from typing import List, Optional
import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..config import GlobalConfig
from ..drive import GoogleDriveUploader

console = Console()


def collect_markdown_files(
    files: tuple,
    directory: Optional[Path],
    pattern: str
) -> List[Path]:
    """Collect markdown files from file arguments and/or directory.

    Args:
        files: Tuple of file paths from --file options
        directory: Directory path from --directory option
        pattern: Glob pattern for directory search

    Returns:
        List of unique Path objects
    """
    markdown_files = []
    seen = set()

    # Add explicitly specified files
    for file_path in files:
        path = Path(file_path)
        if path.exists() and path.suffix.lower() == '.md':
            if path not in seen:
                markdown_files.append(path)
                seen.add(path)
        elif path.exists():
            console.print(f"[yellow]Warning: Skipping non-markdown file: {path}[/yellow]")
        else:
            console.print(f"[yellow]Warning: File not found: {path}[/yellow]")

    # Add files from directory
    if directory:
        dir_path = Path(directory)
        if dir_path.is_dir():
            for path in dir_path.glob(pattern):
                # Only include markdown files
                if path.is_file() and path.suffix.lower() == '.md' and path not in seen:
                    markdown_files.append(path)
                    seen.add(path)
        else:
            console.print(f"[yellow]Warning: Directory not found: {dir_path}[/yellow]")

    return sorted(markdown_files, key=lambda p: p.name.lower())


def display_preview_table(files: List[Path], folder_name: str):
    """Display a preview table of files to upload.

    Args:
        files: List of markdown file paths
        folder_name: Name of target folder
    """
    table = Table(title=f"Files to upload to '{folder_name}'")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan", no_wrap=False)
    table.add_column("Size", style="green", justify="right")

    for i, path in enumerate(files, 1):
        size = path.stat().st_size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / 1024 / 1024:.2f} MB"

        table.add_row(str(i), str(path), size_str)

    console.print(table)
    console.print(f"\n[bold]Total: {len(files)} files[/bold]")


def display_results_table(results: List[dict]):
    """Display a results table after upload.

    Args:
        results: List of upload result dicts
    """
    table = Table(title="Upload Results")
    table.add_column("Status", style="bold", width=8)
    table.add_column("Document", style="cyan", no_wrap=False)
    table.add_column("Link", style="blue", no_wrap=False)

    for result in results:
        status = result['status']
        if status == 'created':
            status_str = "[green]Created[/green]"
        elif status == 'skipped':
            status_str = "[yellow]Skipped[/yellow]"
        else:
            status_str = "[red]Error[/red]"

        link = ""
        if result.get('webViewLink'):
            # Make the link clickable in Rich terminal
            link = f"[link={result['webViewLink']}]Open[/link]"

        table.add_row(status_str, result['name'], link)

    console.print(table)

    # Summary
    created = len([r for r in results if r['status'] == 'created'])
    skipped = len([r for r in results if r['status'] == 'skipped'])
    errors = len([r for r in results if r['status'] == 'error'])

    console.print(f"\n[bold]Summary:[/bold] {created} created, {skipped} skipped, {errors} errors")


@click.command()
@click.option('-f', '--file', 'files', multiple=True, type=click.Path(),
              help='Markdown file(s) to upload (can be specified multiple times)')
@click.option('-d', '--directory', type=click.Path(exists=True),
              help='Directory containing markdown files')
@click.option('-t', '--folder-id', 'folder_id',
              help='Target Google Drive folder ID')
@click.option('--folder-url', 'folder_url',
              help='Target Google Drive folder URL (alternative to --folder-id)')
@click.option('-c', '--credentials', type=click.Path(), default=None,
              help='Google API credentials file (auto-discovered if not specified)')
@click.option('-p', '--pattern', default='*.md',
              help='Glob pattern for directory search (default: *.md)')
@click.option('--preview/--no-preview', default=True,
              help='Preview files before upload (default: preview)')
@click.option('--skip-existing/--replace-existing', 'skip_existing', default=True,
              help='Skip documents that already exist (default: skip)')
@click.option('--method', type=click.Choice(['html', 'pandoc'], case_sensitive=False),
              default='pandoc',
              help='Conversion method: "pandoc" (preserves footnotes) or "html" (fallback)')
def upload(
    files: tuple,
    directory: Optional[str],
    folder_id: Optional[str],
    folder_url: Optional[str],
    credentials: str,
    pattern: str,
    preview: bool,
    skip_existing: bool,
    method: str
):
    """Upload markdown files to Google Drive as native Google Docs.

    Converts markdown files to Google Docs using either Pandoc (default, preserves
    footnotes) or HTML (fallback). The Pandoc method converts to DOCX first, which
    Google Drive then converts to Google Docs format with native footnotes.

    Examples:

    \b
    # Upload with Pandoc (default, preserves footnotes)
    gdrive-upload -f report.md --folder-id 1ABC123

    \b
    # Upload multiple files
    gdrive-upload -f doc1.md -f doc2.md --folder-id 1ABC123

    \b
    # Upload all markdown files from a directory
    gdrive-upload -d markdown/ --folder-id 1ABC123

    \b
    # Upload using folder URL instead of ID
    gdrive-upload -f doc.md --folder-url "https://drive.google.com/drive/folders/1ABC123"

    \b
    # Use HTML method (if Pandoc not available)
    gdrive-upload -f doc.md --folder-id 1ABC123 --method html

    \b
    # Upload without preview prompt
    gdrive-upload -f doc.md --folder-id 1ABC123 --no-preview

    \b
    # Replace existing documents instead of skipping
    gdrive-upload -f doc.md --folder-id 1ABC123 --replace-existing
    """
    # Validate folder specification
    if not folder_id and not folder_url:
        raise click.UsageError("Either --folder-id or --folder-url is required")

    if folder_id and folder_url:
        raise click.UsageError("Specify either --folder-id or --folder-url, not both")

    # Validate file specification
    if not files and not directory:
        raise click.UsageError("Either --file or --directory is required")

    # Setup configuration
    config = GlobalConfig()
    if credentials:
        credentials_path = Path(credentials)
    else:
        from ..credentials import find_credentials_file
        credentials_path = find_credentials_file()
        if credentials_path is None:
            console.print("[red]Error: Could not find credentials.json. Run 'gdrive init' to set up.[/red]")
            raise click.Abort()
    config.drive.credentials_file = credentials_path
    from ..credentials import get_token_save_path
    config.drive.token_file = get_token_save_path(credentials_path)

    console.print(f"[bold blue]Preparing to upload markdown files to Google Drive[/bold blue]")

    # Initialize uploader
    try:
        uploader = GoogleDriveUploader(config.drive)
    except ImportError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    # Extract folder ID from URL if provided
    target_folder_id = folder_id
    if folder_url:
        try:
            target_folder_id = uploader.extract_folder_id(folder_url)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()

    # Verify folder access
    console.print(f"[blue]Verifying folder access...[/blue]")
    try:
        folder_info = uploader.verify_folder_access(target_folder_id)
        console.print(f"[green]Target folder: {folder_info['name']}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    # Collect markdown files
    dir_path = Path(directory) if directory else None
    markdown_files = collect_markdown_files(files, dir_path, pattern)

    if not markdown_files:
        console.print("[yellow]No markdown files found to upload.[/yellow]")
        return

    # Preview and confirm
    if preview:
        display_preview_table(markdown_files, folder_info['name'])

        if not Confirm.ask("\nProceed with upload?"):
            console.print("[yellow]Upload cancelled.[/yellow]")
            return

    # Upload files
    console.print(f"\n[bold blue]Uploading files using {method.upper()} method...[/bold blue]")

    # Choose upload method
    if method.lower() == 'pandoc':
        # Use Pandoc method (preserves footnotes)
        try:
            from gdrive_download.downloader.pandoc_uploader import PandocUploader
            pandoc_uploader = PandocUploader(uploader)

            # Upload files using Pandoc
            results = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Uploading files...", total=len(markdown_files))

                for markdown_path in markdown_files:
                    result = pandoc_uploader.upload_markdown_as_google_doc(
                        markdown_path,
                        target_folder_id,
                        skip_existing=skip_existing
                    )
                    results.append(result)
                    progress.advance(task)

        except RuntimeError as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[yellow]Tip: Install Pandoc or use --method html[/yellow]")
            raise click.Abort()
        except ImportError as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[yellow]Tip: Install pypandoc or use --method html[/yellow]")
            raise click.Abort()
    else:
        # Use HTML method (original implementation)
        results = uploader.upload_multiple(
            markdown_files,
            target_folder_id,
            skip_existing=skip_existing
        )

    # Display results
    console.print()
    display_results_table(results)

    # Print clickable links for created documents
    created_docs = [r for r in results if r['status'] == 'created' and r.get('webViewLink')]
    if created_docs:
        console.print(f"\n[bold green]Created documents:[/bold green]")
        for doc in created_docs:
            console.print(f"  - {doc['webViewLink']}")

    console.print(f"\n[bold green]Upload complete![/bold green]")


@click.command()
@click.option('-f', '--file', 'markdown_file', required=True, type=click.Path(exists=True),
              help='Markdown file to write')
@click.option('--doc-url', 'doc_url',
              help='Google Doc URL (may include tab ID, e.g., ?tab=t.xyz)')
@click.option('--doc-id', 'doc_id',
              help='Google Doc document ID (alternative to --doc-url)')
@click.option('--tab-id', 'tab_id',
              help='Tab ID to write to (default: first tab)')
@click.option('-c', '--credentials', type=click.Path(), default=None,
              help='Google API credentials file (auto-discovered if not specified)')
@click.option('--append/--replace', 'append_mode', default=True,
              help='Append to existing content (default) or replace it')
@click.option('--force/--no-force', 'force', default=False,
              help='Skip confirmation prompt')
def write_to_doc(
    markdown_file: str,
    doc_url: Optional[str],
    doc_id: Optional[str],
    tab_id: Optional[str],
    credentials: str,
    append_mode: bool,
    force: bool
):
    """Write markdown content to a tab in an existing Google Doc.

    This command writes the contents of a markdown file to a specific tab
    in an existing Google Document, preserving formatting.

    SAFETY FEATURES:
    - By default, appends to existing content (use --replace to clear first)
    - Shows preview of existing content before writing
    - Requires confirmation unless --force is specified

    Examples:

    \b
    # Write to first tab of a document (append mode)
    gdrive-upload-tab -f notes.md --doc-id 1ABC123XYZ

    \b
    # Write to specific tab using URL with tab parameter
    gdrive-upload-tab -f notes.md --doc-url "https://docs.google.com/document/d/1ABC123/edit?tab=t.0"

    \b
    # Replace existing content in tab
    gdrive-upload-tab -f notes.md --doc-id 1ABC123 --replace

    \b
    # Skip confirmation prompt
    gdrive-upload-tab -f notes.md --doc-id 1ABC123 --force
    """
    # Validate document specification
    if not doc_url and not doc_id:
        raise click.UsageError("Either --doc-url or --doc-id is required")

    if doc_url and doc_id:
        raise click.UsageError("Specify either --doc-url or --doc-id, not both")

    # Setup configuration
    config = GlobalConfig()
    if credentials:
        credentials_path = Path(credentials)
    else:
        from ..credentials import find_credentials_file
        credentials_path = find_credentials_file()
        if credentials_path is None:
            console.print("[red]Error: Could not find credentials.json. Run 'gdrive init' to set up.[/red]")
            raise click.Abort()
    config.drive.credentials_file = credentials_path
    from ..credentials import get_token_save_path
    config.drive.token_file = get_token_save_path(credentials_path)

    console.print(f"[bold blue]Preparing to write markdown to Google Doc[/bold blue]")

    # Initialize uploader
    try:
        uploader = GoogleDriveUploader(config.drive)
    except ImportError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    # Extract document and tab IDs
    target_doc_id = doc_id
    target_tab_id = tab_id

    if doc_url:
        try:
            target_doc_id, url_tab_id = uploader.extract_doc_and_tab_id(doc_url)
            # URL tab ID takes precedence if not explicitly specified
            if not target_tab_id and url_tab_id:
                target_tab_id = url_tab_id
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()

    # Get document and tab info
    console.print(f"[blue]Verifying document access...[/blue]")
    try:
        tab_info = uploader.get_tab_info(target_doc_id, target_tab_id)
        console.print(f"[green]Document found[/green]")
        console.print(f"  Tab: {tab_info['title']} (ID: {tab_info['id']})")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    # Get existing content preview
    existing_preview = uploader.get_tab_content_preview(
        target_doc_id, tab_info['id'], max_chars=300
    )

    # Read markdown file
    markdown_path = Path(markdown_file)
    with open(markdown_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    # Display operation summary
    console.print()
    mode_str = "[yellow]APPEND[/yellow]" if append_mode else "[red]REPLACE[/red]"
    console.print(f"[bold]Operation:[/bold] {mode_str} mode")
    console.print(f"[bold]File:[/bold] {markdown_path.name} ({len(markdown_content)} chars)")
    console.print()

    # Show existing content
    if existing_preview and existing_preview != "(empty)":
        console.print("[bold]Existing tab content:[/bold]")
        console.print(f"[dim]{existing_preview}[/dim]")
        console.print()

        if not append_mode:
            console.print("[yellow]⚠ WARNING: --replace will DELETE all existing content![/yellow]")
            console.print()

    # Show markdown preview
    preview_lines = markdown_content[:500]
    if len(markdown_content) > 500:
        preview_lines += "..."
    console.print("[bold]Markdown to write:[/bold]")
    console.print(f"[dim]{preview_lines}[/dim]")
    console.print()

    # Confirm unless --force
    if not force:
        action = "replace content in" if not append_mode else "append to"
        if not Confirm.ask(f"Proceed to {action} tab '{tab_info['title']}'?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    # Perform write
    console.print(f"[blue]Writing to document...[/blue]")

    result = uploader.write_to_tab(
        target_doc_id,
        markdown_content,
        tab_info['id'],
        replace=not append_mode
    )

    # Display result
    if result['status'] == 'success':
        console.print(f"[bold green]✓ {result['message']}[/bold green]")
        if result.get('webViewLink'):
            console.print(f"[blue]View: {result['webViewLink']}[/blue]")
    else:
        console.print(f"[red]✗ Error: {result['message']}[/red]")
        raise click.Abort()


if __name__ == '__main__':
    upload()
