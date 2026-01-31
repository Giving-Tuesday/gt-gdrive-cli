"""Track relationships between URLs, downloads, and markdown files."""
# MATURE CODE. DO NOT TOUCH THIS FILE WITHOUT SPECIFIC INSTRUCTIONS

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from difflib import SequenceMatcher
from rich.console import Console


class FileRelationshipTracker:
    """Tracks relationships between Google Drive URLs, downloaded files, and markdown conversions."""
    
    def __init__(self, downloads_dir: Path, markdown_dir: Path):
        self.downloads_dir = Path(downloads_dir)
        self.markdown_dir = Path(markdown_dir)
        self.console = Console()
    
    def similarity(self, a: str, b: str) -> float:
        """Calculate similarity between two strings."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def find_best_match(self, target_name: str, candidates: List[Path], threshold: float = 0.7) -> Optional[Path]:
        """Find the best matching file from candidates."""
        best_match = None
        best_score = 0
        
        target_stem = Path(target_name).stem.lower()
        
        for candidate in candidates:
            candidate_stem = candidate.stem.lower()
            score = self.similarity(target_stem, candidate_stem)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate
        
        return best_match
    
    def scan_file_relationships(self, url_mappings: List[Dict[str, str]] = None) -> Dict:
        """Scan and map relationships between files."""
        relationships = {
            "scan_timestamp": datetime.now().isoformat(),
            "files": []
        }
        
        # Get all downloaded and markdown files
        downloaded_files = []
        for pattern in ['*.docx', '*.doc', '*.pdf', '*.txt']:
            downloaded_files.extend(list(self.downloads_dir.glob(pattern)))
        
        markdown_files = list(self.markdown_dir.glob('*.md'))
        
        # Process URL mappings if provided
        if url_mappings:
            for url_mapping in url_mappings:
                file_name = url_mapping['name']
                google_url = url_mapping['webViewLink']
                google_id = url_mapping.get('id', None)
                
                # Find corresponding downloaded file
                downloaded_file = self.find_best_match(file_name, downloaded_files)
                
                # Find corresponding markdown file
                markdown_file = self.find_best_match(file_name, markdown_files)
                
                relationship = {
                    "id": google_id,
                    "name": file_name,
                    "webViewLink": google_url,
                    "downloaded_file": str(downloaded_file) if downloaded_file else None,
                    "markdown_file": str(markdown_file) if markdown_file else None,
                    "has_download": downloaded_file is not None,
                    "has_markdown": markdown_file is not None
                }
                
                relationships["files"].append(relationship)
        
        else:
            # Fallback: match downloaded files to markdown files
            for downloaded_file in downloaded_files:
                markdown_file = self.find_best_match(downloaded_file.name, markdown_files)
                
                relationship = {
                    "id": None,
                    "name": downloaded_file.name,
                    "webViewLink": None,
                    "downloaded_file": str(downloaded_file),
                    "markdown_file": str(markdown_file) if markdown_file else None,
                    "has_download": True,
                    "has_markdown": markdown_file is not None
                }
                
                relationships["files"].append(relationship)
        
        return relationships
    
    def save_relationships_csv(self, relationships: Dict, output_path: Path) -> None:
        """Save relationships to CSV file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'id', 'name', 'webViewLink', 'downloaded_file', 
                'markdown_file', 'has_download', 'has_markdown'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for file_info in relationships['files']:
                writer.writerow(file_info)
        
        self.console.print(f"[green]Saved relationships to {output_path}[/green]")
    
    def get_url_mapping_for_file(self, file_name: str, relationships: Dict) -> Optional[str]:
        """Get Google Drive URL for a specific file."""
        file_stem = Path(file_name).stem.lower()
        
        for file_info in relationships['files']:
            if file_info['markdown_file']:
                markdown_stem = Path(file_info['markdown_file']).stem.lower()
                if self.similarity(file_stem, markdown_stem) > 0.8:
                    return file_info['webViewLink']
        
        return None
    
    def generate_report(self, relationships: Dict) -> str:
        """Generate a summary report of file relationships."""
        total_files = len(relationships['files'])
        with_downloads = sum(1 for f in relationships['files'] if f['has_download'])
        with_markdown = sum(1 for f in relationships['files'] if f['has_markdown'])
        with_urls = sum(1 for f in relationships['files'] if f['webViewLink'])
        
        report = f"""File Relationship Analysis Report
Generated: {relationships['scan_timestamp']}

Summary:
- Total files tracked: {total_files}
- Files with downloads: {with_downloads} ({with_downloads/total_files*100:.1f}%)
- Files with markdown: {with_markdown} ({with_markdown/total_files*100:.1f}%)
- Files with Google Drive URLs: {with_urls} ({with_urls/total_files*100:.1f}%)

Missing Downloads: {total_files - with_downloads}
Missing Markdown: {total_files - with_markdown}
Missing URLs: {total_files - with_urls}
"""
        
        return report
