"""File conversion utilities for AAR documents."""
# MATURE CODE. DO NOT TOUCH THIS FILE WITHOUT SPECIFIC INSTRUCTIONS
# Modified with permission to add footnote preservation support

import io
from pathlib import Path
from typing import Optional, List, Dict
import mammoth
import markdownify
from markdownify import MarkdownConverter
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn


class FootnotePreservingConverter(MarkdownConverter):
    """Converts HTML to Markdown while preserving footnote semantics.

    This converter extends the standard MarkdownConverter to detect and preserve
    footnotes in the HTML output from Mammoth, converting them to Pandoc-style
    markdown footnotes ([^1] for references and [^1]: content for definitions).

    Mammoth converts Word footnotes to HTML like:
        <p>Text<sup><a href="#fn1">[1]</a></sup></p>
        <ol><li id="fn1">Footnote content ↩</li></ol>

    This converter transforms them to:
        Text[^1]

        [^1]: Footnote content
    """

    def __init__(self, **options):
        """Initialize the converter with footnote tracking."""
        super().__init__(**options)
        self.footnote_map: Dict[str, int] = {}  # Maps HTML footnote IDs to sequential numbers
        self.footnote_counter = 1
        self.footnote_definitions: List[str] = []  # Collected footnote definitions
        self.in_footnote_list = False  # Track if we're in a footnote definition list

    def convert_sup(self, el, text, parent_tags):
        """Handle <sup> tags - detect footnote references.

        Args:
            el: BeautifulSoup element
            text: Converted text content
            parent_tags: Set of parent tag names

        Returns:
            Markdown representation of the superscript
        """
        # Look for footnote reference pattern: <sup><a href="#fnX">[n]</a></sup>
        # Supports both #fn1 and #footnote-1 formats
        link = el.find('a')
        href = link.get('href', '') if link else ''

        if href.startswith('#fn') or href.startswith('#footnote'):
            fn_id = href[1:]  # Remove '#' prefix

            # Assign sequential number if this is a new footnote reference
            if fn_id not in self.footnote_map:
                self.footnote_map[fn_id] = self.footnote_counter
                self.footnote_counter += 1

            # Return Pandoc-style footnote reference
            return f'[^{self.footnote_map[fn_id]}]'

        # Not a footnote reference, use default superscript handling
        return super().convert_sup(el, text, parent_tags)

    def convert_ol(self, el, text, parent_tags):
        """Handle <ol> tags - detect footnote definition lists.

        Args:
            el: BeautifulSoup element
            text: Converted text content
            parent_tags: Set of parent tag names

        Returns:
            Markdown representation of the ordered list or footnote definitions
        """
        # Check if this is a footnote definition list
        # Mammoth creates: <ol><li id="fn1">Content ↩</li>...</ol>
        # or <ol><li id="footnote-1">Content ↩</li>...</ol>
        first_li = el.find('li')
        li_id = first_li.get('id', '') if first_li else ''

        if li_id.startswith('fn') or li_id.startswith('footnote'):
            # This is a footnote definition list
            footnotes = []

            for li in el.find_all('li', recursive=False):
                fn_id = li.get('id', '')
                if fn_id in self.footnote_map:
                    # Extract footnote content, removing the backlink arrow
                    content = self._extract_footnote_content(li)
                    footnote_num = self.footnote_map[fn_id]
                    footnotes.append(f'[^{footnote_num}]: {content}')

            if footnotes:
                # Return footnote definitions with proper spacing
                # Add blank line before footnotes section
                return '\n\n' + '\n'.join(footnotes) + '\n'

        # Not a footnote list, use default ordered list handling
        return super().convert_ol(el, text, parent_tags)

    def _extract_footnote_content(self, li_element) -> str:
        """Extract clean content from a footnote <li> element.

        Args:
            li_element: BeautifulSoup <li> element containing footnote content

        Returns:
            Cleaned footnote content without backlink arrows
        """
        # Get all text, then clean it
        content = li_element.get_text()

        # Remove common footnote backlink markers
        content = content.rstrip('↩ \n\r\t')
        content = content.strip()

        return content


class FileConverter:
    """Converts downloaded files to markdown format."""
    
    def __init__(self, input_dir: Path, output_dir: Path):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.console = Console()
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def convert_docx_to_markdown(self, docx_path: Path) -> str:
        """Convert a DOCX file to markdown using mammoth + custom footnote-preserving converter."""
        try:
            with open(docx_path, "rb") as docx_file:
                result = mammoth.convert_to_html(docx_file)
                html_content = result.value

            # Convert HTML to markdown using custom converter that preserves footnotes
            converter = FootnotePreservingConverter(heading_style="ATX")
            markdown_content = converter.convert(html_content)

            if result.messages:
                self.console.print(f"[yellow]Conversion warnings for {docx_path.name}:[/yellow]")
                for message in result.messages:
                    self.console.print(f"  {message}")

            return markdown_content

        except Exception as e:
            self.console.print(f"[red]Error converting {docx_path.name}: {e}[/red]")
            raise
    
    def convert_file(self, file_path: Path) -> Optional[Path]:
        """Convert a single file to markdown."""
        if not file_path.exists():
            self.console.print(f"[red]File not found: {file_path}[/red]")
            return None
        
        # Determine output path
        output_name = file_path.stem + '.md'
        output_path = self.output_dir / output_name
        
        if output_path.exists():
            self.console.print(f"[yellow]Skipping existing file: {output_name}[/yellow]")
            return output_path
        
        try:
            if file_path.suffix.lower() == '.docx':
                markdown_content = self.convert_docx_to_markdown(file_path)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                
                self.console.print(f"[green]Converted: {file_path.name} → {output_name}[/green]")
                return output_path
            
            else:
                self.console.print(f"[yellow]Unsupported file type: {file_path.suffix}[/yellow]")
                return None
                
        except Exception as e:
            self.console.print(f"[red]Error converting {file_path.name}: {e}[/red]")
            return None
    
    def convert_all_files(self, file_patterns: List[str] = None) -> List[Path]:
        """Convert all supported files in the input directory."""
        if file_patterns is None:
            file_patterns = ['*.docx', '*.doc']
        
        # Find all files to convert
        files_to_convert = []
        for pattern in file_patterns:
            files_to_convert.extend(self.input_dir.glob(pattern))
        
        if not files_to_convert:
            self.console.print("[yellow]No files found to convert[/yellow]")
            return []
        
        converted_files = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Converting files...", total=len(files_to_convert))
            
            for file_path in files_to_convert:
                converted_path = self.convert_file(file_path)
                if converted_path:
                    converted_files.append(converted_path)
                
                progress.advance(task)
        
        self.console.print(f"[green]Converted {len(converted_files)} files to markdown[/green]")
        return converted_files
    
    def get_conversion_stats(self) -> dict:
        """Get statistics about the conversion process."""
        input_files = list(self.input_dir.glob('*.docx')) + list(self.input_dir.glob('*.doc'))
        output_files = list(self.output_dir.glob('*.md'))
        
        return {
            'input_files': len(input_files),
            'output_files': len(output_files),
            'conversion_rate': len(output_files) / len(input_files) if input_files else 0
        }
    
    def update_csv_with_conversions(self, csv_file: Path, converted_files: List[Path]) -> None:
        """Update a CSV file with markdown conversion information.
        
        This is a convenience method that delegates to GoogleDriveSearcher.
        
        Args:
            csv_file: Path to the CSV file to update  
            converted_files: List of converted markdown file paths
        """
        from .drive_searcher import GoogleDriveSearcher
        
        # Create a temporary searcher instance just for the CSV update method
        class TempSearcher(GoogleDriveSearcher):
            def __init__(self):
                pass
        
        searcher = TempSearcher()
        searcher.update_csv_with_conversions(csv_file, converted_files)
