"""CLI command for searching Google Drive files by pattern."""

import re
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import click
from rich.console import Console
from rich.prompt import Confirm

from ..config import GlobalConfig
from ..drive import GoogleDriveSearcher, GoogleDriveDownloader, FileConverter

console = Console()


def sanitize_pattern_for_dir(pattern: str) -> str:
    """Convert a search pattern to a safe directory name."""
    safe_name = pattern.replace('^', '').replace('$', '').replace('.*', '_')
    safe_name = re.sub(r'[<>:"/\\|?*\[\]]', '_', safe_name)
    safe_name = safe_name.strip('_. ')
    
    if not safe_name:
        safe_name = "search_results"
    
    return safe_name[:50]


def parse_since_date(since_str: str) -> datetime:
    """Parse a since date string into a datetime object.
    
    Supports:
    - ISO date format: 2024-01-01
    - Relative formats: 7d (days), 1w (weeks), 1m (months), 1h (hours)
    """
    # Try to parse as ISO date first
    try:
        return datetime.strptime(since_str, '%Y-%m-%d')
    except ValueError:
        pass
    
    # Try relative formats
    now = datetime.now()
    
    # Extract number and unit
    import re
    match = re.match(r'^(\d+)([dwmh])$', since_str.lower())
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'd':
            return now - timedelta(days=num)
        elif unit == 'w':
            return now - timedelta(weeks=num)
        elif unit == 'm':
            return now - timedelta(days=num * 30)  # Approximate
        elif unit == 'h':
            return now - timedelta(hours=num)
    
    # If we can't parse, raise an error
    raise click.BadParameter(
        f"Invalid date format: {since_str}. "
        "Use ISO format (2024-01-01) or relative format (7d, 1w, 1m, 1h)"
    )


@click.command()
@click.option('-p', '--pattern', required=True, 
              help='File name pattern (supports * and ? wildcards, or regex if starts with ^)')
@click.option('-s', '--scope', type=click.Choice(['personal', 'all', 'shared']), 
              default='all', help='Drive scope to search')
@click.option('--shared-drive-id', help='Specific shared drive ID when scope is "shared"')
@click.option('-t', '--file-types', multiple=True, 
              type=click.Choice(['document', 'spreadsheet', 'presentation']),
              default=['document'], help='File types to search for')
@click.option('-o', '--output-dir', type=click.Path(), 
              help='Output directory (default: search_<pattern>)')
@click.option('-c', '--credentials', type=click.Path(exists=True), 
              default='credentials.json', help='Google API credentials file')
@click.option('--download/--no-download', default=True, 
              help='Download found files')
@click.option('--convert/--no-convert', default=True, 
              help='Convert downloaded files to markdown')
@click.option('--max-results', type=int, default=100, 
              help='Maximum number of results')
@click.option('--create-shortcuts', type=str, 
              help='Create shortcuts in the specified folder ID (e.g., --create-shortcuts FOLDER_ID)')
@click.option('--since', type=str,
              help='Filter files modified since date (e.g., 2024-01-01, 7d, 1w, 1m)')
def search(
    pattern: str,
    scope: str,
    shared_drive_id: Optional[str],
    file_types: tuple,
    output_dir: Optional[str],
    credentials: str,
    download: bool,
    convert: bool,
    max_results: int,
    create_shortcuts: Optional[str],
    since: Optional[str]
):
    """Search for files in Google Drive by name pattern and optionally download them.
    
    Creates a standardized directory structure:
    <base_dir>/
    ├── documents/              # Downloaded files
    ├── markdown/               # Converted markdown files
    ├── search_results.csv      # Search metadata
    └── search_summary.md       # Search summary
    
    Examples:
    
    \b
    # Search for all AAR documents
    aar-search -p 'AAR*'
    
    \b
    # Search only in personal drive
    aar-search -p '*2024*' -s personal
    
    \b
    # Search with regex pattern
    aar-search -p '^AAR.*\\.docx$'
    
    \b
    # Search without downloading
    aar-search -p 'AAR*' --no-download
    
    \b
    # Search multiple file types
    aar-search -p 'Report*' -t document -t spreadsheet
    
    \b
    # Create shortcuts to found files in a folder
    aar-search -p 'AAR*' --no-download --create-shortcuts 1ABC123folderID
    
    \b
    # Search and create shortcuts without downloading
    aar-search -p 'Project Brief*' --no-download --create-shortcuts 1XYZ789folderID
    
    \b
    # Search for files modified in the last week
    aar-search -p 'AAR*' --since 7d
    
    \b
    # Search for files modified since specific date
    aar-search -p 'Report*' --since 2024-01-01
    """
    # Setup configuration
    config = GlobalConfig()
    credentials_path = Path(credentials)
    config.downloader.credentials_file = credentials_path
    # Store token in same directory as credentials
    config.downloader.token_file = credentials_path.parent / "token.pickle"
    
    # Determine output directory
    if output_dir:
        base_dir = Path(output_dir)
    else:
        base_dir = Path(f"search_{sanitize_pattern_for_dir(pattern)}")
    
    # Use consistent directory structure
    documents_dir = base_dir / "documents"
    markdown_dir = base_dir / "markdown"
    config.downloader.output_dir = documents_dir
    
    # Create base directory (always needed for CSV)
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Create download directories if downloading
    if download:
        for dir_path in [documents_dir, markdown_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    console.print(f"[bold blue]🔍 Searching Google Drive[/bold blue]")
    console.print(f"Pattern: [cyan]{pattern}[/cyan]")
    console.print(f"Scope: [cyan]{scope}[/cyan]")
    
    # Parse since parameter
    since_date = None
    if since:
        since_date = parse_since_date(since)
        console.print(f"Since: [cyan]{since_date.strftime('%Y-%m-%d %H:%M:%S')}[/cyan]")
    
    if download:
        console.print(f"Output: [cyan]{base_dir}/[/cyan]")
    
    # Search for files
    try:
        searcher = GoogleDriveSearcher(config.downloader)
        
        search_results = searcher.search_files(
            pattern=pattern,
            drive_scope=scope,
            shared_drive_id=shared_drive_id,
            file_types=list(file_types),
            max_results=max_results,
            since_date=since_date
        )
        
        console.print(f"\n[green]✓ Found {len(search_results)} matching files[/green]")
        
        if not search_results:
            console.print("[yellow]No files found matching the pattern.[/yellow]")
            return
        
        # Display results
        searcher.display_results(search_results, show_limit=20)
        
        # Always save search results to CSV
        results_file = base_dir / "search_results.csv"
        searcher.save_results(search_results, results_file)
        
    except Exception as e:
        console.print(f"[red]Error during search: {e}[/red]")
        return
    
    # Create shortcuts if requested
    if create_shortcuts:
        console.print(f"\n[bold blue]🔗 Creating shortcuts...[/bold blue]")
        
        # Confirm if many files
        if len(search_results) > 20:
            if not Confirm.ask(f"\n⚠️  Create shortcuts for all {len(search_results)} files?"):
                console.print("[yellow]Shortcut creation cancelled[/yellow]")
            else:
                try:
                    shortcut_results = searcher.create_shortcuts(search_results, create_shortcuts)
                    
                    if shortcut_results['success_count'] > 0:
                        console.print(f"[green]✓ Created {shortcut_results['success_count']} shortcuts in folder '{shortcut_results['folder_name']}'[/green]")
                    
                    if shortcut_results.get('skipped_count', 0) > 0:
                        console.print(f"[yellow]⚠️  Skipped {shortcut_results['skipped_count']} existing shortcuts[/yellow]")
                    
                    if shortcut_results['errors']:
                        console.print(f"[yellow]⚠️  {len(shortcut_results['errors'])} shortcuts failed:[/yellow]")
                        for error in shortcut_results['errors'][:5]:  # Show first 5 errors
                            console.print(f"  [dim]• {error}[/dim]")
                        if len(shortcut_results['errors']) > 5:
                            console.print(f"  [dim]... and {len(shortcut_results['errors']) - 5} more errors[/dim]")
                            
                except Exception as e:
                    console.print(f"[red]Error creating shortcuts: {e}[/red]")
        else:
            # Automatically create shortcuts for small result sets
            try:
                shortcut_results = searcher.create_shortcuts(search_results, create_shortcuts)
                
                if shortcut_results['success_count'] > 0:
                    console.print(f"[green]✓ Created {shortcut_results['success_count']} shortcuts in folder '{shortcut_results['folder_name']}'[/green]")
                
                if shortcut_results.get('skipped_count', 0) > 0:
                    console.print(f"[yellow]⚠️  Skipped {shortcut_results['skipped_count']} existing shortcuts[/yellow]")
                
                if shortcut_results['errors']:
                    console.print(f"[yellow]⚠️  Some shortcuts failed:[/yellow]")
                    for error in shortcut_results['errors']:
                        console.print(f"  [dim]• {error}[/dim]")
                        
            except Exception as e:
                console.print(f"[red]Error creating shortcuts: {e}[/red]")
    
    # Download files if requested
    if download:
        # Confirm if many files
        if len(search_results) > 20:
            if not Confirm.ask(f"\n⚠️  Download all {len(search_results)} files?"):
                console.print("[red]Download cancelled[/red]")
                return
        
        console.print(f"\n[bold blue]📥 Downloading files...[/bold blue]")
        
        try:
            downloader = GoogleDriveDownloader(config.downloader)
            download_results = downloader.download_search_results(search_results)
            
            successful_downloads = [r for r in download_results if r[1] is not None]
            console.print(f"[green]✓ Downloaded {len(successful_downloads)} files[/green]")
            
            # Update CSV with download results
            results_file = base_dir / "search_results.csv"
            searcher.update_csv_with_downloads(results_file, download_results)
            
        except Exception as e:
            console.print(f"[red]Error during download: {e}[/red]")
            return
        
        # Convert to markdown if requested
        if convert and successful_downloads:
            console.print(f"\n[bold blue]🔄 Converting to markdown...[/bold blue]")
            
            converter = FileConverter(
                input_dir=documents_dir,
                output_dir=markdown_dir
            )
            
            converted_files = converter.convert_all_files()
            console.print(f"[green]✓ Converted {len(converted_files)} files[/green]")
            
            # Update CSV with conversion results
            results_file = base_dir / "search_results.csv"
            searcher.update_csv_with_conversions(results_file, converted_files)
        
        # Create summary
        summary_file = base_dir / "search_summary.md"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"# Google Drive Search Results\n\n")
            f.write(f"**Search Pattern:** `{pattern}`\n")
            f.write(f"**Search Scope:** {scope}\n")
            f.write(f"**Files Found:** {len(search_results)}\n")
            if download:
                f.write(f"**Files Downloaded:** {len(successful_downloads)}\n")
                if convert:
                    f.write(f"**Files Converted:** {len(converted_files)}\n")
            f.write("\n## Files\n\n")
            
            # Group by drive
            drives = {}
            for result in search_results:
                drive = result.get('drive', 'Unknown')
                if drive not in drives:
                    drives[drive] = []
                drives[drive].append(result)
            
            for drive, files in sorted(drives.items()):
                f.write(f"### {drive} ({len(files)} files)\n\n")
                for file in files:
                    f.write(f"- [{file['name']}]({file.get('webViewLink', '#')})\n")
                f.write("\n")
        
        console.print(f"\n[green]✓ Summary saved to {summary_file}[/green]")
        console.print(f"\n[bold green]🎉 Search complete![/bold green]")
        console.print(f"[green]📁 All outputs saved to: {base_dir}/[/green]")


if __name__ == '__main__':
    search()