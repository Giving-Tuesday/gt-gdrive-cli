"""After Action Review (AAR) document analysis template."""

import re
from typing import Dict, List
from .base_template import DocumentTemplate


class AarTemplate(DocumentTemplate):
    """Template for analyzing After Action Review documents."""

    @property
    def name(self) -> str:
        return "aar"

    @property
    def description(self) -> str:
        return "Analysis template for After Action Review documents"

    @property
    def section_headers(self) -> Dict[str, List[str]]:
        """Section headers commonly found in AAR documents."""
        return {
            "challenges": [
                "challenges",
                "problems",
                "issues",
                "difficulties",
                "areas for improvement",
                "improvements",
                "lessons learned",
                "what didn't work",
                "obstacles",
                "barriers",
                "pain points",
            ],
            "successes": [
                "successes",
                "wins",
                "what went well",
                "achievements",
                "positive outcomes",
                "strengths",
                "accomplishments",
                "highlights",
                "good news",
                "what worked",
            ],
            "lessons": [
                "lessons learned",
                "key learnings",
                "takeaways",
                "insights",
                "learnings",
                "key insights",
                "lessons",
            ],
            "recommendations": [
                "recommendations",
                "next steps",
                "action items",
                "improvements",
                "suggestions",
                "future actions",
            ],
        }

    @property
    def analysis_patterns(self) -> Dict[str, Dict[str, str]]:
        """Analysis patterns for AAR documents."""
        return {
            "challenges": {
                "resource_constraints": r"(?i)(resource|staff|capacity|time|budget|money|funding|personnel|shortage|limited|lack)",
                "data_collection": r"(?i)(data|metric|measurement|tracking|report|survey|collection|analysis|reporting|dashboard)",
                "communication": r"(?i)(communication|coordination|messaging|coverage|press|media|outreach|marketing|promotion)",
                "partnership": r"(?i)(partner|collaboration|relationship|stakeholder|alignment|coordination|external|vendor)",
                "timing_scope": r"(?i)(timeline|scope|planning|expectation|deadline|schedule|timing|rushed|delayed|late)",
                "technical": r"(?i)(technical|technology|system|platform|tool|software|hardware|infrastructure|bug|error)",
                "process": r"(?i)(process|procedure|workflow|protocol|documentation|training|onboarding|handoff)",
            },
            "successes": {
                "leadership": r"(?i)(leader|leadership|development|empowerment|capacity|growth|management|direction|guidance)",
                "content": r"(?i)(content|engagement|quality|storytelling|media|creative|messaging|narrative|brand)",
                "agility": r"(?i)(agility|opportunity|adaptive|innovation|strategic|flexible|responsive|quick|pivot)",
                "data_excellence": r"(?i)(measurement|research|data|analysis|insight|evidence|metrics|tracking|dashboard)",
                "partnerships": r"(?i)(partnership|collaboration|relationship|network|alliance|cooperation|teamwork)",
                "community": r"(?i)(community|engagement|mobilization|participation|involvement|activation|grassroots)",
                "impact": r"(?i)(impact|outcome|result|achievement|success|goal|objective|target|reach|scale)",
            },
        }

    @property
    def report_sections(self) -> List[str]:
        """Sections to include in AAR analysis reports."""
        return [
            "executive_summary",
            "key_challenges",
            "major_successes",
            "lessons_learned",
            "recommendations",
            "detailed_analysis",
        ]

    @property
    def metadata(self) -> Dict:
        """AAR template metadata."""
        return {
            "version": "1.0.0",
            "author": "Document Analyzer Framework",
            "created": "2024-01-01",
            "updated": "2024-01-01",
            "document_type": "After Action Review",
            "purpose": "Organizational learning and improvement",
            "typical_sections": list(self.section_headers.keys()),
        }

    def preprocess_document(self, content: str, metadata=None) -> str:
        """
        AAR-specific preprocessing.

        Args:
            content: Raw document content
            metadata: Optional document metadata

        Returns:
            Preprocessed content suitable for AAR analysis
        """
        # Remove common AAR template instructions first
        template_phrases = [
            r"Please complete this template.*?(?=\n|$)",
            r"Instructions:.*?(?=\n|$)",
            r"\[.*?INSERT.*?.*?\]",
            r"\[.*?REPLACE.*?.*?\]",
            r"Delete this text.*?(?=\n|$)",
            r"Remove this section.*?(?=\n|$)",
        ]

        for phrase_pattern in template_phrases:
            content = re.sub(
                phrase_pattern, "", content, flags=re.IGNORECASE | re.DOTALL
            )

        # Normalize common AAR section headers
        header_replacements = {
            "what went well": "successes",
            "what didn't go well": "challenges", 
            "what didn't work": "challenges",
            "areas for improvement": "challenges",
            "improvements": "challenges",
            "lessons learned": "lessons",
            "key learnings": "lessons",
            "learnings/insights": "lessons",
            "learnings": "lessons",
            "insights": "lessons",
            "next steps": "recommendations",
            "action items": "recommendations",
            "action plan": "recommendations",
        }

        for old_header, new_header in header_replacements.items():
            escaped_header = re.escape(old_header)
            pattern = (
                r"^\s*#{1,6}\s*" + escaped_header + r"|^\s*" + escaped_header + r":"
            )
            content = re.sub(
                pattern, f"# {new_header}", content, flags=re.IGNORECASE | re.MULTILINE
            )

        # Then apply base preprocessing
        content = super().preprocess_document(content, metadata)

        return content

    def extract_themes(self, matches: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
        """
        Extract high-level themes from AAR pattern matches.

        Args:
            matches: Pattern matches organized by category

        Returns:
            Dict mapping theme names to descriptions
        """
        themes = {}

        # Analyze challenge themes
        if "challenges" in matches:
            challenge_themes = []

            # Count pattern frequencies to identify major themes
            pattern_counts = {}
            for match_list in matches["challenges"].values():
                for match in match_list:
                    pattern = match.get("pattern", "")
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

            # Identify top challenge themes
            sorted_patterns = sorted(
                pattern_counts.items(), key=lambda x: x[1], reverse=True
            )
            for pattern, count in sorted_patterns[:5]:  # Top 5 themes
                if count >= 2:  # Must appear at least twice
                    challenge_themes.append(
                        f"{pattern.replace('_', ' ').title()} (mentioned {count} times)"
                    )

            themes["major_challenges"] = challenge_themes

        # Analyze success themes
        if "successes" in matches:
            success_themes = []

            pattern_counts = {}
            for match_list in matches["successes"].values():
                for match in match_list:
                    pattern = match.get("pattern", "")
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

            sorted_patterns = sorted(
                pattern_counts.items(), key=lambda x: x[1], reverse=True
            )
            for pattern, count in sorted_patterns[:5]:
                if count >= 2:
                    success_themes.append(
                        f"{pattern.replace('_', ' ').title()} (mentioned {count} times)"
                    )

            themes["key_strengths"] = success_themes

        return themes
