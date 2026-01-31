"""Document analysis module.

This module provides document analysis capabilities:
- DocumentAnalyzer: Main analysis class
- PatternMatcher: Pattern matching for document content
- PatternMatch: Result of pattern matching
"""

from .document_analyzer import DocumentAnalyzer
from .pattern_matcher import PatternMatcher, PatternMatch

__all__ = [
    "DocumentAnalyzer",
    "PatternMatcher",
    "PatternMatch",
]
