"""Base template class for document analysis."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import re
from pathlib import Path


class DocumentTemplate(ABC):
    """
    Base class for document analysis templates.

    Templates define how to analyze specific types of documents by providing:
    - Pattern definitions for extracting themes
    - Section header patterns for document structure
    - Preprocessing and postprocessing logic
    - Report configuration
    """

    def __init__(self):
        self.validate_template()

    @property
    @abstractmethod
    def name(self) -> str:
        """Template name (used for CLI --template parameter)."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the template."""
        pass

    @property
    def section_headers(self) -> Dict[str, List[str]]:
        """
        Mapping of section types to header patterns.

        Returns:
            Dict mapping section names to lists of header patterns.
            Example: {'challenges': ['challenges', 'problems', 'issues']}
        """
        return {}

    @property
    def analysis_patterns(self) -> Dict[str, Dict[str, str]]:
        """
        Nested mapping of analysis categories and their regex patterns.

        Returns:
            Dict with category names as keys, each containing pattern dicts.
            Example: {
                'challenges': {
                    'resource_constraints': r'(?i)(resource|staff|capacity)',
                    'communication': r'(?i)(communication|coordination)'
                },
                'successes': {
                    'leadership': r'(?i)(leader|development|empowerment)'
                }
            }
        """
        return {}

    @property
    def report_sections(self) -> List[str]:
        """
        List of sections to include in generated reports.

        Returns:
            List of section names in order they should appear in reports.
        """
        return ["summary", "analysis", "themes"]

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Additional template metadata.

        Returns:
            Dict with template metadata (version, author, etc.)
        """
        return {
            "version": "1.0.0",
            "author": "Unknown",
            "created": None,
            "updated": None,
        }

    def validate_template(self) -> None:
        """
        Validate template configuration.

        Raises:
            ValueError: If template configuration is invalid.
        """
        if not self.name:
            raise ValueError("Template must have a name")

        if not self.description:
            raise ValueError("Template must have a description")

        # Validate patterns are valid regex
        for category, patterns in self.analysis_patterns.items():
            for pattern_name, pattern in patterns.items():
                try:
                    re.compile(pattern)
                except re.error as e:
                    raise ValueError(
                        f"Invalid regex pattern '{pattern}' in {category}.{pattern_name}: {e}"
                    )

    def preprocess_document(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Preprocess document content before analysis.

        Args:
            content: Raw document content
            metadata: Optional document metadata

        Returns:
            Preprocessed content
        """
        # Default preprocessing: normalize whitespace but preserve line structure
        content = content.strip()
        # Replace multiple spaces with single space, but preserve newlines
        content = re.sub(r" +", " ", content)
        # Remove excessive newlines (more than 2)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content

    def extract_sections(self, content: str) -> Dict[str, str]:
        """
        Extract sections from document based on section headers.

        Args:
            content: Document content

        Returns:
            Dict mapping section names to their content
        """
        sections = {}

        for section_name, headers in self.section_headers.items():
            section_content = []

            for header in headers:
                # Create pattern to match section headers (case-insensitive)
                # Match: # Header, ## Header, or Header:
                pattern = re.compile(
                    r"^\s*#{1,6}\s*"
                    + re.escape(header)
                    + r"|^\s*"
                    + re.escape(header)
                    + r":",
                    re.IGNORECASE | re.MULTILINE,
                )
                matches = list(pattern.finditer(content))

                for match in matches:
                    start_pos = match.end()

                    # Find next header or end of document
                    next_header_pattern = re.compile(
                        r"^\s*#{1,6}\s+\w+|^\s*\w+:", re.MULTILINE
                    )
                    next_match = next_header_pattern.search(content, start_pos)
                    end_pos = next_match.start() if next_match else len(content)

                    section_text = content[start_pos:end_pos].strip()
                    if section_text:
                        section_content.append(section_text)

            if section_content:
                sections[section_name] = "\n\n".join(section_content)

        return sections

    def postprocess_matches(
        self, matches: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Postprocess pattern matches after extraction.

        Args:
            matches: Raw pattern matches by category

        Returns:
            Processed matches
        """
        return matches

    def get_pattern_categories(self) -> List[str]:
        """
        Get list of analysis pattern categories.

        Returns:
            List of category names
        """
        return list(self.analysis_patterns.keys())

    def get_patterns_for_category(self, category: str) -> Dict[str, str]:
        """
        Get patterns for a specific category.

        Args:
            category: Category name

        Returns:
            Dict of pattern names to regex patterns

        Raises:
            KeyError: If category doesn't exist
        """
        if category not in self.analysis_patterns:
            raise KeyError(f"Category '{category}' not found in template '{self.name}'")

        return self.analysis_patterns[category]

    def __str__(self) -> str:
        """String representation of template."""
        return f"{self.name}: {self.description}"

    def __repr__(self) -> str:
        """Developer representation of template."""
        return f"DocumentTemplate(name='{self.name}')"


def load_template(template_name: str) -> DocumentTemplate:
    """
    Load a template by name.

    Args:
        template_name: Name of template to load

    Returns:
        Template instance

    Raises:
        ImportError: If template module can't be imported
        AttributeError: If template class can't be found
    """
    import importlib

    try:
        # Try to import template module
        module = importlib.import_module(f"gdrive_unified.templates.{template_name}")

        # Look for template class (convention: TemplateNameTemplate)
        template_class_name = f"{template_name.title().replace('_', '')}Template"

        if hasattr(module, template_class_name):
            template_class = getattr(module, template_class_name)
            return template_class()
        else:
            raise AttributeError(
                f"Template class '{template_class_name}' not found in module"
            )

    except ImportError as e:
        raise ImportError(f"Could not import template '{template_name}': {e}")


def list_available_templates() -> List[str]:
    """
    List all available templates.

    Returns:
        List of template names
    """
    templates = []
    templates_dir = Path(__file__).parent

    for template_file in templates_dir.glob("*.py"):
        if (
            template_file.name.startswith("_")
            or template_file.name == "base_template.py"
        ):
            continue

        template_name = template_file.stem
        try:
            # Try to load template to verify it works
            load_template(template_name)
            templates.append(template_name)
        except (ImportError, AttributeError):
            # Skip invalid templates
            continue

    return sorted(templates)
