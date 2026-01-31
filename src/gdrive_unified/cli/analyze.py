"""CLI command for document analysis."""

import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table

console = Console()


def analyze_documents(
    documents: List[str],
    template: str,
    output: Optional[str],
    output_format: str,
    verbose: bool,
) -> None:
    """Analyze documents using the specified template.

    Args:
        documents: List of document paths to analyze
        template: Template name to use
        output: Output file path (None for stdout)
        output_format: Output format (markdown, json, csv)
        verbose: Enable verbose output
    """
    try:
        from ..analyzer import DocumentAnalyzer
        from ..templates import load_template, list_available_templates
    except ImportError as e:
        console.print(f"[red]Error loading analyzer: {e}[/red]")
        console.print("[yellow]Install with: pip install gdrive-unified[analyzer][/yellow]")
        raise SystemExit(1)

    # Load template
    try:
        analyzer = DocumentAnalyzer(template)
        if verbose:
            console.print(f"[blue]Using template: {template}[/blue]")
    except ImportError as e:
        console.print(f"[red]Template not found: {template}[/red]")
        available = list_available_templates()
        console.print(f"Available templates: {', '.join(available)}")
        raise SystemExit(1)

    # Analyze each document
    results = []
    for doc_path in documents:
        path = Path(doc_path)
        if not path.exists():
            console.print(f"[yellow]Skipping non-existent file: {doc_path}[/yellow]")
            continue

        if verbose:
            console.print(f"[blue]Analyzing: {path.name}[/blue]")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        metadata = {
            "document_name": path.name,
            "document_path": str(path.absolute()),
        }

        result = analyzer.analyze_document(content, metadata)
        results.append(result)

    if not results:
        console.print("[yellow]No documents to analyze[/yellow]")
        return

    # Generate output
    if output_format == "json":
        import json
        output_content = json.dumps(results, indent=2, default=str)
    elif output_format == "csv":
        output_content = _format_csv(results)
    else:  # markdown
        output_content = _format_markdown(results)

    # Write or display output
    if output:
        output_path = Path(output)
        output_path.write_text(output_content)
        console.print(f"[green]Analysis saved to: {output}[/green]")
    else:
        console.print(output_content)


def _format_markdown(results: List[dict]) -> str:
    """Format results as markdown."""
    lines = []

    for i, result in enumerate(results):
        metadata = result.get("metadata", {})
        doc_name = metadata.get("document_name", f"Document {i+1}")

        lines.append(f"# {doc_name}")
        lines.append("")

        # Sections
        sections = result.get("sections", {})
        if sections:
            lines.append("## Sections Found")
            lines.append("")
            for section_name, section_content in sections.items():
                lines.append(f"### {section_name}")
                if section_content:
                    preview = section_content[:200] + "..." if len(section_content) > 200 else section_content
                    lines.append(preview)
                lines.append("")

        # Matches
        matches = result.get("matches", {})
        if matches:
            lines.append("## Pattern Matches")
            lines.append("")
            for category, category_matches in matches.items():
                if category_matches:
                    lines.append(f"### {category}")
                    for match in category_matches[:5]:  # Limit to 5 per category
                        lines.append(f"- {match.get('text', match)[:100]}")
                    if len(category_matches) > 5:
                        lines.append(f"- ... and {len(category_matches) - 5} more")
                    lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _format_csv(results: List[dict]) -> str:
    """Format results as CSV."""
    import csv
    import io

    output = io.StringIO()
    writer = None

    for result in results:
        metadata = result.get("metadata", {})
        doc_name = metadata.get("document_name", "Unknown")

        matches = result.get("matches", {})
        for category, category_matches in matches.items():
            for match in category_matches:
                row = {
                    "document": doc_name,
                    "category": category,
                    "text": match.get("text", str(match))[:500],
                    "section": match.get("section", ""),
                }

                if writer is None:
                    writer = csv.DictWriter(output, fieldnames=row.keys())
                    writer.writeheader()

                writer.writerow(row)

    return output.getvalue()


@click.command()
@click.argument("documents", type=click.Path(exists=True), nargs=-1, required=True)
@click.option(
    "-t", "--template",
    default="aar",
    help="Analysis template to use (default: aar)",
)
@click.option(
    "-o", "--output",
    type=click.Path(),
    help="Output file (default: stdout)",
)
@click.option(
    "-f", "--format", "output_format",
    type=click.Choice(["markdown", "json", "csv"]),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option(
    "--list-templates",
    is_flag=True,
    help="List available templates and exit",
)
def main(
    documents: tuple,
    template: str,
    output: Optional[str],
    output_format: str,
    verbose: bool,
    list_templates: bool,
) -> None:
    """Analyze documents using templates.

    Analyze one or more documents using a specified template
    and output the results in various formats.

    \b
    Examples:
      # Analyze a single document
      gdrive-analyze document.md

      # Analyze multiple documents with JSON output
      gdrive-analyze *.md -f json -o results.json

      # Use a specific template
      gdrive-analyze document.md -t aar

      # List available templates
      gdrive-analyze --list-templates
    """
    if list_templates:
        try:
            from ..templates import list_available_templates
            templates = list_available_templates()
            console.print("[bold]Available templates:[/bold]")
            for tmpl in templates:
                console.print(f"  - {tmpl}")
        except ImportError:
            console.print("[yellow]Could not load templates module[/yellow]")
        return

    analyze_documents(list(documents), template, output, output_format, verbose)


if __name__ == "__main__":
    main()
