"""Pattern matching utilities for document analysis."""

from typing import Dict, List, Optional, Any, Iterator
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatternMatch:
    """Represents a single pattern match in a document."""

    pattern_name: str
    text: str
    start: int
    end: int
    context: str
    section: Optional[str] = None
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class PatternMatcher:
    """
    Advanced pattern matching for document analysis.

    Provides sophisticated pattern matching capabilities including:
    - Regex pattern matching
    - Context extraction
    - Section-aware matching
    - Match deduplication
    - Confidence scoring
    """

    def __init__(
        self, patterns: Dict[str, Dict[str, str]], case_sensitive: bool = False
    ):
        """
        Initialize pattern matcher.

        Args:
            patterns: Nested dict of categories and their patterns
            case_sensitive: Whether to use case-sensitive matching
        """
        self.patterns = patterns
        self.case_sensitive = case_sensitive
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, Dict[str, re.Pattern]]:
        """Compile all regex patterns for better performance."""
        compiled = {}

        for category, category_patterns in self.patterns.items():
            compiled[category] = {}
            for pattern_name, pattern in category_patterns.items():
                flags = 0 if self.case_sensitive else re.IGNORECASE
                try:
                    compiled[category][pattern_name] = re.compile(pattern, flags)
                except re.error as e:
                    raise ValueError(
                        f"Invalid regex pattern '{pattern}' in {category}.{pattern_name}: {e}"
                    )

        return compiled

    def match_document(
        self, content: str, sections: Optional[Dict[str, str]] = None
    ) -> Dict[str, List[PatternMatch]]:
        """
        Match patterns against a document.

        Args:
            content: Document content to search
            sections: Optional section mapping for section-aware matching

        Returns:
            Dictionary mapping pattern names to lists of matches
        """
        all_matches = {}

        for category, category_patterns in self._compiled_patterns.items():
            category_matches = []

            for pattern_name, compiled_pattern in category_patterns.items():
                # Search in full content
                matches = self._find_matches(compiled_pattern, content, pattern_name)

                # Add section information if available
                if sections:
                    for match in matches:
                        match.section = self._find_section_for_position(
                            match.start, content, sections
                        )

                category_matches.extend(matches)

            # Sort matches by position and deduplicate
            category_matches.sort(key=lambda x: x.start)
            all_matches[category] = self._deduplicate_matches(category_matches)

        return all_matches

    def match_sections(self, sections: Dict[str, str]) -> Dict[str, List[PatternMatch]]:
        """
        Match patterns against specific sections.

        Args:
            sections: Dictionary mapping section names to content

        Returns:
            Dictionary mapping pattern names to lists of matches
        """
        all_matches = {}

        for category, category_patterns in self._compiled_patterns.items():
            category_matches = []

            # Look for matches in relevant sections
            target_sections = [category] if category in sections else sections.keys()

            for section_name in target_sections:
                if section_name not in sections:
                    continue

                section_content = sections[section_name]

                for pattern_name, compiled_pattern in category_patterns.items():
                    matches = self._find_matches(
                        compiled_pattern, section_content, pattern_name
                    )

                    # Set section information
                    for match in matches:
                        match.section = section_name

                    category_matches.extend(matches)

            category_matches.sort(key=lambda x: x.start)
            all_matches[category] = self._deduplicate_matches(category_matches)

        return all_matches

    def _find_matches(
        self, compiled_pattern: re.Pattern, content: str, pattern_name: str
    ) -> List[PatternMatch]:
        """Find all matches for a compiled pattern in content."""
        matches = []

        for match in compiled_pattern.finditer(content):
            context = self._extract_context(content, match.start(), match.end())

            pattern_match = PatternMatch(
                pattern_name=pattern_name,
                text=match.group(),
                start=match.start(),
                end=match.end(),
                context=context,
            )

            matches.append(pattern_match)

        return matches

    def _extract_context(
        self, content: str, start: int, end: int, context_size: int = 100
    ) -> str:
        """
        Extract context around a match.

        Args:
            content: Full content
            start: Match start position
            end: Match end position
            context_size: Characters to include on each side

        Returns:
            Context string with match highlighted
        """
        context_start = max(0, start - context_size)
        context_end = min(len(content), end + context_size)

        before = content[context_start:start]
        match_text = content[start:end]
        after = content[end:context_end]

        # Clean up whitespace
        before = before.strip()
        after = after.strip()

        # Build context with ellipsis if truncated
        context_parts = []

        if context_start > 0:
            context_parts.append("...")

        context_parts.append(before)
        context_parts.append(f"**{match_text}**")  # Highlight match
        context_parts.append(after)

        if context_end < len(content):
            context_parts.append("...")

        return " ".join(part for part in context_parts if part)

    def _find_section_for_position(
        self, position: int, content: str, sections: Dict[str, str]
    ) -> Optional[str]:
        """
        Find which section a position belongs to.

        Args:
            position: Character position in content
            content: Full document content
            sections: Section mapping

        Returns:
            Section name or None
        """
        # This is a simplified implementation
        # In practice, you'd need to track section positions during extraction

        # Find the section that contains this position
        current_pos = 0
        for section_name, section_content in sections.items():
            section_start = content.find(section_content, current_pos)
            if section_start != -1:
                section_end = section_start + len(section_content)
                if section_start <= position < section_end:
                    return section_name
                current_pos = section_end

        return None

    def _deduplicate_matches(self, matches: List[PatternMatch]) -> List[PatternMatch]:
        """
        Remove duplicate matches that overlap significantly.

        Args:
            matches: List of pattern matches

        Returns:
            Deduplicated list of matches
        """
        if not matches:
            return matches

        # Sort by start position
        sorted_matches = sorted(matches, key=lambda x: x.start)
        deduplicated = [sorted_matches[0]]

        for current_match in sorted_matches[1:]:
            last_match = deduplicated[-1]

            # Check for overlap
            overlap_start = max(last_match.start, current_match.start)
            overlap_end = min(last_match.end, current_match.end)
            overlap_length = max(0, overlap_end - overlap_start)

            # Calculate overlap percentage
            last_length = last_match.end - last_match.start
            current_length = current_match.end - current_match.start
            min_length = min(last_length, current_length)

            overlap_percentage = overlap_length / min_length if min_length > 0 else 0

            # If overlap is less than 50%, keep both matches
            if overlap_percentage < 0.5:
                deduplicated.append(current_match)
            else:
                # Keep the longer match
                if current_length > last_length:
                    deduplicated[-1] = current_match

        return deduplicated

    def get_match_statistics(
        self, matches: Dict[str, List[PatternMatch]]
    ) -> Dict[str, Any]:
        """
        Generate statistics about pattern matches.

        Args:
            matches: Pattern matches by category

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_matches": 0,
            "matches_by_category": {},
            "matches_by_pattern": {},
            "matches_by_section": {},
        }

        for category, category_matches in matches.items():
            stats["total_matches"] += len(category_matches)
            stats["matches_by_category"][category] = len(category_matches)

            # Pattern-level stats
            pattern_counts = {}
            section_counts = {}

            for match in category_matches:
                # Count by pattern
                if match.pattern_name not in pattern_counts:
                    pattern_counts[match.pattern_name] = 0
                pattern_counts[match.pattern_name] += 1

                # Count by section
                if match.section:
                    if match.section not in section_counts:
                        section_counts[match.section] = 0
                    section_counts[match.section] += 1

            stats["matches_by_pattern"][category] = pattern_counts

            # Merge section counts
            for section, count in section_counts.items():
                if section not in stats["matches_by_section"]:
                    stats["matches_by_section"][section] = 0
                stats["matches_by_section"][section] += count

        return stats

    def export_matches(
        self, matches: Dict[str, List[PatternMatch]], format: str = "json"
    ) -> str:
        """
        Export matches to various formats.

        Args:
            matches: Pattern matches
            format: Export format ('json', 'csv', 'markdown')

        Returns:
            Formatted string
        """
        if format == "json":
            import json

            serializable = {}
            for category, category_matches in matches.items():
                serializable[category] = [
                    {
                        "pattern_name": match.pattern_name,
                        "text": match.text,
                        "start": match.start,
                        "end": match.end,
                        "context": match.context,
                        "section": match.section,
                    }
                    for match in category_matches
                ]
            return json.dumps(serializable, indent=2)

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                ["Category", "Pattern", "Text", "Start", "End", "Section", "Context"]
            )

            for category, category_matches in matches.items():
                for match in category_matches:
                    writer.writerow(
                        [
                            category,
                            match.pattern_name,
                            match.text,
                            match.start,
                            match.end,
                            match.section or "",
                            match.context,
                        ]
                    )

            return output.getvalue()

        elif format == "markdown":
            lines = ["# Pattern Matches Report\\n"]

            for category, category_matches in matches.items():
                lines.append(f"## {category.title()}\\n")

                for match in category_matches:
                    lines.append(f"### {match.pattern_name}\\n")
                    lines.append(f"**Text:** {match.text}\\n")
                    lines.append(f'**Section:** {match.section or "Unknown"}\\n')
                    lines.append(f"**Context:** {match.context}\\n")
                    lines.append("---\\n")

            return "\\n".join(lines)

        else:
            raise ValueError(f"Unsupported export format: {format}")
