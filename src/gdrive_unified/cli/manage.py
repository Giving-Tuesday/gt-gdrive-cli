"""CLI for managing AAR tools and workflows."""

import click
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

from ..config import get_config, GlobalConfig
from ..drive import FileRelationshipTracker
from ..utils.logging import setup_logging


@click.group()
@click.option('--config-file', help='Path to configuration file')
@click.option('--log-level', default='INFO', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']))
@click.pass_context
def main(ctx, config_file, log_level):
    """Manage AAR tools and workflows."""
    
    # Setup logging
    logger = setup_logging(level=log_level)
    
    # Store in context
    ctx.ensure_object(dict)
    ctx.obj['logger'] = logger
    ctx.obj['console'] = Console()
    ctx.obj['config'] = get_config(Path(config_file) if config_file else None)


@main.command()
@click.pass_context
def init_config(ctx):
    """Initialize a new configuration file."""
    console = ctx.obj['console']
    
    config_path = Path('gdrive_config.yaml')
    if config_path.exists():
        if not click.confirm(f"Configuration file {config_path} already exists. Overwrite?"):
            return
    
    # Create default configuration
    config = GlobalConfig()
    config.to_yaml(config_path)
    
    console.print(f"[green]Configuration file created: {config_path}[/green]")
    console.print("[blue]Edit this file to customize your settings.[/blue]")


@main.command()
@click.option('--downloads-dir', default='downloads', help='Downloads directory')
@click.option('--markdown-dir', default='markdown', help='Markdown directory')
@click.option('--url-mappings', help='Path to URL mappings JSON file')
@click.pass_context
def status(ctx, downloads_dir, markdown_dir, url_mappings):
    """Show status of AAR files and relationships."""
    console = ctx.obj['console']
    
    # Load URL mappings if provided
    url_mapping_list = []
    if url_mappings and Path(url_mappings).exists():
        with open(url_mappings, 'r') as f:
            url_mapping_list = json.load(f)
    
    # Initialize tracker
    tracker = FileRelationshipTracker(
        downloads_dir=Path(downloads_dir),
        markdown_dir=Path(markdown_dir)
    )
    
    # Scan relationships
    relationships = tracker.scan_file_relationships(url_mapping_list)
    
    # Create status table
    table = Table(title="AAR File Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("Percentage", style="green")
    
    total_files = len(relationships['files'])
    with_downloads = sum(1 for f in relationships['files'] if f['has_download'])
    with_markdown = sum(1 for f in relationships['files'] if f['has_markdown'])
    with_urls = sum(1 for f in relationships['files'] if f['google_drive_url'])
    
    table.add_row("Total Files", str(total_files), "100%")
    table.add_row("With Downloads", str(with_downloads), f"{with_downloads/total_files*100:.1f}%" if total_files > 0 else "0%")
    table.add_row("With Markdown", str(with_markdown), f"{with_markdown/total_files*100:.1f}%" if total_files > 0 else "0%")
    table.add_row("With URLs", str(with_urls), f"{with_urls/total_files*100:.1f}%" if total_files > 0 else "0%")
    
    console.print(table)
    
    # Show detailed report
    report = tracker.generate_report(relationships)
    console.print("\\n" + report)


# URL update functionality moved to document_analyzer package


@main.command()
@click.option('--downloads-dir', default='downloads', help='Downloads directory')
@click.option('--markdown-dir', default='markdown', help='Markdown directory')
@click.pass_context
def cleanup(ctx, downloads_dir, markdown_dir):
    """Clean up temporary files and duplicates."""
    console = ctx.obj['console']
    
    downloads_path = Path(downloads_dir)
    markdown_path = Path(markdown_dir)
    
    # Find potential duplicates
    download_files = list(downloads_path.glob('*')) if downloads_path.exists() else []
    markdown_files = list(markdown_path.glob('*')) if markdown_path.exists() else []
    
    console.print(f"[blue]Found {len(download_files)} download files[/blue]")
    console.print(f"[blue]Found {len(markdown_files)} markdown files[/blue]")
    
    # TODO: Implement duplicate detection and cleanup logic
    console.print("[yellow]Cleanup functionality not yet implemented[/yellow]")


@main.command()
@click.pass_context
def version(ctx):
    """Show version information."""
    console = ctx.obj['console']
    
    from .. import __version__
    console.print(f"GivingTuesday AAR Tools v{__version__}")


if __name__ == '__main__':
    main()