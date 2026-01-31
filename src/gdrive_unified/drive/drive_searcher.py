"""Google Drive file searcher for finding files by pattern across drives."""

import re
from pathlib import Path
from typing import List, Dict, Optional, Literal, Union, Any, Tuple
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.table import Table
from rich.progress import (
    track,
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from .drive_downloader import GoogleDriveDownloader

console = Console()


class GoogleDriveSearcher:
    """Search for files across Google Drive by name pattern."""

    def __init__(self, credentials: Union[Credentials, Path, str]):
        """Initialize the searcher with credentials.

        Args:
            credentials: Google OAuth2 credentials object, or path to credentials file
        """
        if isinstance(credentials, (Path, str)):
            # Create a minimal config to initialize downloader for auth
            from ..config import DriveConfig

            config = DriveConfig(
                credentials_file=Path(credentials), token_file=Path("token.pickle")
            )
            downloader = GoogleDriveDownloader(config)
            self.service = downloader.service
        elif isinstance(credentials, Credentials):
            self.service = build("drive", "v3", credentials=credentials)
        else:
            # Assume it's a downloader config
            downloader = GoogleDriveDownloader(credentials)
            self.service = downloader.service

    def search_files(
        self,
        pattern: str,
        drive_scope: Literal["personal", "all", "shared"] = "all",
        shared_drive_id: Optional[str] = None,
        file_types: Optional[List[str]] = None,
        max_results: int = 100,
        since_date: Optional[datetime] = None,
    ) -> List[Dict[str, str]]:
        """Search for files matching a pattern across specified drives.

        Args:
            pattern: File name pattern (supports * and ? wildcards, or regex if starts with ^)
            drive_scope: Where to search - "personal", "all", or "shared"
            shared_drive_id: Specific shared drive ID if scope is "shared"
            file_types: List of MIME types to filter (e.g., ['document', 'spreadsheet'])
            max_results: Maximum number of results to return
            since_date: Only return files modified after this date

        Returns:
            List of file info dicts with keys: id, name, mimeType, parents, webViewLink, drive
        """
        results = []
        seen_file_ids: set[str] = set()  # Track file IDs to prevent duplicates

        # Build the query
        query_parts = []

        # Convert pattern to Google Drive query
        if pattern.startswith("^"):
            # Regex pattern - we'll filter results later
            regex_pattern = re.compile(pattern, re.IGNORECASE)
            query_parts.append("trashed = false")
        else:
            # Convert wildcards to Google Drive query
            # Google Drive uses 'contains' for partial matches
            search_term = pattern.replace("*", "").replace("?", "")
            if search_term:
                query_parts.append(f"name contains '{search_term}'")
            query_parts.append("trashed = false")

        # Add file type filters
        if file_types:
            mime_types = []
            for file_type in file_types:
                if file_type == "document":
                    mime_types.extend(
                        [
                            "application/vnd.google-apps.document",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "application/msword",
                        ]
                    )
                elif file_type == "spreadsheet":
                    mime_types.extend(
                        [
                            "application/vnd.google-apps.spreadsheet",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "application/vnd.ms-excel",
                        ]
                    )
                elif file_type == "presentation":
                    mime_types.extend(
                        [
                            "application/vnd.google-apps.presentation",
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            "application/vnd.ms-powerpoint",
                        ]
                    )
                else:
                    mime_types.append(file_type)

            if mime_types:
                mime_query = " or ".join([f"mimeType = '{mt}'" for mt in mime_types])
                query_parts.append(f"({mime_query})")

        # Exclude folders
        query_parts.append("mimeType != 'application/vnd.google-apps.folder'")

        # Add date filter if provided
        if since_date:
            # Format date for Google Drive API (RFC 3339)
            date_str = since_date.strftime("%Y-%m-%dT%H:%M:%S")
            query_parts.append(f"modifiedTime > '{date_str}'")

        query = " and ".join(query_parts)

        # Search based on scope - fetch more results initially to account for deduplication
        search_limit = (
            max_results * 3
        )  # Search for 3x more results to ensure we have enough unique ones

        if drive_scope == "personal":
            raw_results = self._search_drive(
                query, None, search_limit, "My Drive", since_date
            )
            results.extend(self._deduplicate_results(raw_results, seen_file_ids))
        elif drive_scope == "shared" and shared_drive_id:
            raw_results = self._search_drive(
                query, shared_drive_id, search_limit, "Shared Drive", since_date
            )
            results.extend(self._deduplicate_results(raw_results, seen_file_ids))
        elif drive_scope == "all":
            # Search personal drive
            console.print("[blue]Searching My Drive...[/blue]")
            personal_results = self._search_drive(
                query, None, search_limit, "My Drive", since_date
            )
            results.extend(self._deduplicate_results(personal_results, seen_file_ids))

            # Search all shared drives
            console.print("[blue]Searching Shared Drives...[/blue]")
            try:
                # Get all shared drives with pagination
                all_shared_drives = []
                page_token = None

                while True:
                    response = (
                        self.service.drives()
                        .list(
                            pageSize=100,
                            fields="nextPageToken, drives(id, name)",
                            pageToken=page_token,
                        )
                        .execute()
                    )

                    all_shared_drives.extend(response.get("drives", []))
                    page_token = response.get("nextPageToken")

                    if not page_token:
                        break

                for drive in track(
                    all_shared_drives, description="Searching shared drives"
                ):
                    # Stop if we already have enough unique results
                    if len(results) >= max_results:
                        break

                    drive_results = self._search_drive(
                        query,
                        drive["id"],
                        search_limit,  # Search for many results from each drive
                        drive["name"],
                        since_date,
                    )
                    results.extend(
                        self._deduplicate_results(drive_results, seen_file_ids)
                    )
            except HttpError as e:
                console.print(
                    f"[yellow]Warning: Could not list shared drives: {e}[/yellow]"
                )

        # Filter by regex if provided
        if pattern.startswith("^"):
            results = [r for r in results if regex_pattern.match(r["name"])]
        elif "*" in pattern or "?" in pattern:
            # Convert wildcard to regex
            regex_pattern = pattern.replace("*", ".*").replace("?", ".")
            regex_pattern = f"^{regex_pattern}$"
            compiled_pattern = re.compile(regex_pattern, re.IGNORECASE)
            results = [r for r in results if compiled_pattern.match(r["name"])]

        # Limit results and show deduplication stats
        total_found = len(results)
        results = results[:max_results]

        # Show deduplication info if we found duplicates
        total_files_searched = len(seen_file_ids)
        if total_files_searched > total_found:
            duplicates_removed = total_files_searched - total_found
            console.print(
                f"[dim]Removed {duplicates_removed} duplicate files. Returning {len(results)} unique results.[/dim]"
            )

        return results

    def _deduplicate_results(
        self, results: List[Dict[str, str]], seen_file_ids: set
    ) -> List[Dict[str, str]]:
        """Remove duplicate files based on file ID.

        Args:
            results: List of file info dicts
            seen_file_ids: Set of file IDs already seen (modified in place)

        Returns:
            List of unique file info dicts
        """
        unique_results = []
        for file_info in results:
            file_id = file_info["id"]
            if file_id not in seen_file_ids:
                seen_file_ids.add(file_id)
                unique_results.append(file_info)
        return unique_results

    def _search_drive(
        self,
        query: str,
        drive_id: Optional[str],
        max_results: int,
        drive_name: str,
        since_date: Optional[datetime] = None,
    ) -> List[Dict[str, str]]:
        """Search a specific drive or personal drive."""
        results = []
        page_token = None

        while len(results) < max_results:
            try:
                params = {
                    "q": query,
                    "pageSize": min(100, max_results - len(results)),
                    "fields": "nextPageToken, files(id, name, mimeType, parents, webViewLink, modifiedTime, createdTime)",
                    "orderBy": "modifiedTime desc",
                    "supportsAllDrives": True,
                    "includeItemsFromAllDrives": True,
                }

                if drive_id:
                    params["driveId"] = drive_id
                    params["corpora"] = "drive"
                else:
                    params["corpora"] = "user"

                if page_token:
                    params["pageToken"] = page_token

                response = self.service.files().list(**params).execute()

                files = response.get("files", [])
                for file in files:
                    file["drive"] = drive_name
                    results.append(file)

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            except HttpError as e:
                console.print(f"[red]Error searching {drive_name}: {e}[/red]")
                break

        return results

    def display_results(self, results: List[Dict[str, str]], show_limit: int = 20):
        """Display search results in a formatted table.

        Args:
            results: List of file info dicts
            show_limit: Maximum number of results to display
        """
        if not results:
            console.print("[yellow]No files found matching the pattern.[/yellow]")
            return

        table = Table(title=f"Found {len(results)} files")
        table.add_column("Name", style="cyan", no_wrap=False)
        table.add_column("Type", style="green")
        table.add_column("Drive", style="yellow")
        table.add_column("ID", style="dim")

        # Show limited results
        for i, file in enumerate(results[:show_limit]):
            mime_type = file["mimeType"]
            if "document" in mime_type:
                type_str = "📄 Document"
            elif "spreadsheet" in mime_type:
                type_str = "📊 Spreadsheet"
            elif "presentation" in mime_type:
                type_str = "📽️ Presentation"
            else:
                type_str = "📎 File"

            table.add_row(
                file["name"],
                type_str,
                file.get("drive", "Unknown"),
                file["id"][:8] + "...",
            )

        console.print(table)

        if len(results) > show_limit:
            console.print(
                f"\n[dim]... and {len(results) - show_limit} more files[/dim]"
            )

    def save_results(self, results: List[Dict[str, str]], output_file: Path):
        """Save search results to a CSV file.

        Args:
            results: List of file info dicts
            output_file: Path to save CSV file
        """
        import csv

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            if results:
                # Build fieldnames based on what's actually in the first result
                fieldnames = []
                first_result = results[0]
                
                # Core fields in preferred order
                core_fields = ["id", "name", "webViewLink", "mimeType", "modifiedTime", "createdTime", "drive"]
                for field in core_fields:
                    if field in first_result:
                        fieldnames.append(field)
                
                # Add parents if present
                if "parents" in first_result:
                    fieldnames.append("parents")
                    
                # Add relationship tracking fields for consistency with file_relationships.csv
                fieldnames.extend(["downloaded_file", "markdown_file", "has_download", "has_markdown"])

                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(results)

        console.print(f"[green]✓ Results saved to {output_file}[/green]")

    def update_csv_with_downloads(
        self, csv_file: Path, download_results: List[Tuple[str, Optional[Path]]]
    ) -> None:
        """Update search results CSV with download information.
        
        Args:
            csv_file: Path to the CSV file to update
            download_results: List of tuples (webViewLink, local_file_path)
        """
        if not csv_file.exists():
            console.print(f"[yellow]Warning: CSV file {csv_file} not found[/yellow]")
            return
            
        import csv
        import tempfile
        
        # Create mapping of URLs to download paths
        download_map = {url: path for url, path in download_results if url}
        
        # Read existing CSV
        rows = []
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            for row in reader:
                url = row.get('webViewLink', '')
                if url in download_map:
                    download_path = download_map[url]
                    row['downloaded_file'] = str(download_path) if download_path else ''
                    row['has_download'] = str(download_path is not None)
                rows.append(row)
        
        # Write updated CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            if fieldnames and rows:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        
        updated_count = len([r for r in rows if r.get('has_download') == 'True'])
        console.print(f"[green]✓ Updated {updated_count} download records in {csv_file}[/green]")

    def update_csv_with_conversions(
        self, csv_file: Path, converted_files: List[Path]
    ) -> None:
        """Update search results CSV with markdown conversion information.
        
        Args:
            csv_file: Path to the CSV file to update  
            converted_files: List of converted markdown file paths
        """
        if not csv_file.exists():
            console.print(f"[yellow]Warning: CSV file {csv_file} not found[/yellow]")
            return
            
        import csv
        
        # Create mapping of base names to markdown paths for fuzzy matching
        markdown_map = {}
        for md_path in converted_files:
            base_name = md_path.stem.lower()
            markdown_map[base_name] = str(md_path)
        
        # Read existing CSV
        rows = []
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            for row in reader:
                # Try to match by downloaded file name or original name
                downloaded_file = row.get('downloaded_file', '')
                original_name = row.get('name', '')
                
                matched_md = None
                if downloaded_file:
                    # Match by downloaded file name
                    base_name = Path(downloaded_file).stem.lower()
                    matched_md = markdown_map.get(base_name)
                
                if not matched_md and original_name:
                    # Match by original name (remove extension)
                    base_name = Path(original_name).stem.lower()
                    matched_md = markdown_map.get(base_name)
                
                if matched_md:
                    row['markdown_file'] = matched_md
                    row['has_markdown'] = 'True'
                    
                rows.append(row)
        
        # Write updated CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            if fieldnames and rows:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        
        updated_count = len([r for r in rows if r.get('has_markdown') == 'True'])
        console.print(f"[green]✓ Updated {updated_count} markdown records in {csv_file}[/green]")

    def create_shortcuts(
        self, results: List[Dict[str, str]], target_folder_id: str
    ) -> Dict[str, Any]:
        """Create shortcuts to all matching files in a specified folder.

        Args:
            results: List of file info dicts from search results
            target_folder_id: ID of the folder where shortcuts will be created

        Returns:
            Dictionary with success count, skip count, and list of any errors
        """
        success_count = 0
        skipped_count = 0
        errors = []

        # First verify the target folder exists and we have access
        try:
            folder_info = (
                self.service.files()
                .get(
                    fileId=target_folder_id,
                    fields="id,name,mimeType",
                    supportsAllDrives=True,
                )
                .execute()
            )

            if folder_info.get("mimeType") != "application/vnd.google-apps.folder":
                return {
                    "success_count": 0,
                    "skipped_count": 0,
                    "errors": [f"Target ID {target_folder_id} is not a folder"],
                    "folder_name": None,
                }

            folder_name = folder_info.get("name", "Unknown Folder")
            console.print(f"[blue]Creating shortcuts in folder: {folder_name}[/blue]")

        except HttpError as e:
            return {
                "success_count": 0,
                "skipped_count": 0,
                "errors": [f"Cannot access target folder: {e}"],
                "folder_name": None,
            }

        # Get existing shortcuts in the target folder to avoid duplicates
        console.print("[dim]Checking for existing shortcuts...[/dim]")
        existing_shortcuts = {}
        page_token = None

        try:
            while True:
                response = (
                    self.service.files()
                    .list(
                        q=f"'{target_folder_id}' in parents and mimeType='application/vnd.google-apps.shortcut' and trashed=false",
                        fields="nextPageToken, files(id, name, shortcutDetails)",
                        pageSize=1000,
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )

                for file in response.get("files", []):
                    target_id = file.get("shortcutDetails", {}).get("targetId")
                    if target_id:
                        existing_shortcuts[target_id] = file["name"]

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        except HttpError as e:
            console.print(
                f"[yellow]Warning: Could not check existing shortcuts: {e}[/yellow]"
            )

        # Create shortcuts for each file
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Creating shortcuts...", total=len(results))

            for file_info in results:
                file_id = file_info["id"]
                file_name = file_info["name"]
                drive_name = file_info.get("drive", "")

                # Check if shortcut already exists for this file
                if file_id in existing_shortcuts:
                    skipped_count += 1
                    progress.advance(task)
                    continue

                # Create shortcut name with drive prefix if not from My Drive
                if drive_name and drive_name != "My Drive":
                    shortcut_name = f"[{drive_name}] {file_name}"
                else:
                    shortcut_name = file_name

                try:
                    # Create the shortcut
                    shortcut_metadata = {
                        "name": shortcut_name,
                        "mimeType": "application/vnd.google-apps.shortcut",
                        "parents": [target_folder_id],
                        "shortcutDetails": {"targetId": file_id},
                    }

                    self.service.files().create(
                        body=shortcut_metadata, fields="id,name", supportsAllDrives=True
                    ).execute()

                    success_count += 1

                except HttpError as e:
                    error_msg = f"Failed to create shortcut for '{file_name}': {str(e)}"
                    errors.append(error_msg)

                progress.advance(task)

        return {
            "success_count": success_count,
            "skipped_count": skipped_count,
            "errors": errors,
            "folder_name": folder_name,
            "folder_id": target_folder_id,
        }
