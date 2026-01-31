"""CLI for downloading and converting AAR documents."""

import click
from pathlib import Path
from rich.console import Console

from ..config import get_config, DriveConfig
from ..drive import GoogleDriveDownloader, FileConverter, FileRelationshipTracker
from ..utils.logging import setup_logging


@click.command()
@click.option('--folder-url', '-u', help='Google Drive folder URL to download from')
@click.option('--file-url', '-f', help='Google Drive file URL to download (single file)')
@click.option('--file-id', help='Google Drive file ID to download (single file)')
@click.option('--output-dir', '-o', help='Base output directory (default: folder name from URL)')
@click.option('--documents-subdir', default='documents', help='Subdirectory for downloaded files')
@click.option('--markdown-subdir', default='markdown', help='Subdirectory for converted markdown files')
@click.option('--credentials', '-c', help='Path to Google API credentials file')
@click.option('--convert/--no-convert', default=True, help='Convert downloaded files to markdown')
@click.option('--track-relationships/--no-track', default=True, help='Track file relationships')
@click.option('--config-file', help='Path to configuration file')
@click.option('--log-level', default='INFO', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']))
def main(folder_url, file_url, file_id, output_dir, documents_subdir, markdown_subdir, credentials, convert, track_relationships, config_file, log_level):
    """Download documents from Google Drive and convert to markdown.

    Supports both folder downloads and individual file downloads.

    \b
    Examples:
      # Download all files from a folder
      gdrive-download -u "https://drive.google.com/drive/folders/FOLDER_ID"

      # Download a single file by URL
      gdrive-download -f "https://docs.google.com/document/d/FILE_ID/edit"

      # Download a single file by ID
      gdrive-download --file-id FILE_ID

    \b
    Creates a standardized directory structure:
    <base_dir>/
    ├── documents/              # Downloaded files
    ├── markdown/               # Converted markdown files
    └── file_relationships.csv  # URL to file mappings
    """
    
    # Setup logging
    logger = setup_logging(level=log_level)
    console = Console()

    # Validate input - must have exactly one of folder_url, file_url, or file_id
    source_count = sum(1 for x in [folder_url, file_url, file_id] if x)
    if source_count == 0:
        console.print("[red]Error: Must specify one of --folder-url, --file-url, or --file-id[/red]")
        raise click.Abort()
    if source_count > 1:
        console.print("[red]Error: Specify only one of --folder-url, --file-url, or --file-id[/red]")
        raise click.Abort()

    # Determine if this is a single file download
    single_file_mode = file_url or file_id

    try:
        # Load configuration
        config = get_config(Path(config_file) if config_file else None)

        # Determine base directory
        if output_dir:
            base_dir = Path(output_dir)
        elif folder_url:
            # Extract folder name from URL or use default
            import re
            match = re.search(r'/folders/([^/]+)', folder_url)
            if match:
                folder_id = match.group(1)
                base_dir = Path(f"gdrive_folder_{folder_id[:8]}")
            else:
                base_dir = Path("gdrive_download")
        else:
            # Single file mode - use current directory or simple name
            base_dir = Path("gdrive_download")
        
        # Create directory structure
        documents_dir = base_dir / documents_subdir
        markdown_dir = base_dir / markdown_subdir
        
        # Override with CLI arguments
        config.downloader.output_dir = documents_dir
        if credentials:
            credentials_path = Path(credentials)
            config.downloader.credentials_file = credentials_path
            # Store token in same directory as credentials
            config.downloader.token_file = credentials_path.parent / "token.pickle"
        elif config.downloader.credentials_file:
            # Use token file next to default credentials
            config.downloader.token_file = config.downloader.credentials_file.parent / "token.pickle"

        # Initialize downloader
        downloader = GoogleDriveDownloader(config.downloader)
        
        console.print(f"[blue]Base directory: {base_dir}[/blue]")
        console.print(f"[blue]Documents: {documents_dir}[/blue]")
        console.print(f"[blue]Markdown: {markdown_dir}[/blue]")

        # Download files (single file or folder mode)
        if single_file_mode:
            console.print(f"[blue]Downloading single file...[/blue]")
            web_link, file_path = downloader.download_single_file(
                file_id=file_id,
                file_url=file_url
            )
            results = [(web_link, file_path)] if file_path else []
        else:
            console.print(f"[blue]Downloading from folder: {folder_url}[/blue]")
            results = downloader.download_folder(folder_url)

        console.print(f"[green]Downloaded {len(results)} file(s)[/green]")
        
        # Convert to markdown if requested
        converted_files = []
        if convert:
            console.print(f"[blue]Converting files to markdown...[/blue]")
            
            converter = FileConverter(
                input_dir=config.downloader.output_dir,
                output_dir=markdown_dir
            )
            
            converted_files = converter.convert_all_files()
            console.print(f"[green]Converted {len(converted_files)} files to markdown[/green]")
        
        # Track relationships if requested
        if track_relationships and results:
            console.print(f"[blue]Tracking file relationships...[/blue]")

            # Extract URL mappings
            if single_file_mode:
                # For single file, create mapping from the download result
                url_mappings = []
                for web_link, file_path in results:
                    if file_path:
                        url_mappings.append({
                            'name': file_path.name,
                            'webViewLink': web_link,
                            'id': file_id or downloader.extract_file_id(file_url),
                            'mimeType': 'application/vnd.google-apps.document'  # Default
                        })
            else:
                url_mappings = downloader.extract_all_urls(folder_url)

            tracker = FileRelationshipTracker(
                downloads_dir=config.downloader.output_dir,
                markdown_dir=markdown_dir
            )

            relationships = tracker.scan_file_relationships(url_mappings)

            # Save relationships in base directory
            csv_path = base_dir / 'file_relationships.csv'
            tracker.save_relationships_csv(relationships, csv_path)

            # Generate report
            report = tracker.generate_report(relationships)
            console.print(f"[green]File relationship tracking complete[/green]")
            console.print(report)
        
        console.print(f"[bold green]Download and conversion complete![/bold green]")
        
    except Exception as e:
        logger.error(f"Error during download: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


if __name__ == '__main__':
    main()