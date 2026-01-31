"""Document templates module.

This module provides template functionality for document analysis:
- DocumentTemplate: Base template class
- load_template: Load a template by name
- list_available_templates: List all available templates
- AarTemplate: After Action Review template
"""

from .base_template import (
    DocumentTemplate,
    load_template,
    list_available_templates,
)
from .aar import AarTemplate

__all__ = [
    "DocumentTemplate",
    "load_template",
    "list_available_templates",
    "AarTemplate",
]
