"""Main document analyzer class."""

from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import re
import json
import csv
import io
from datetime import datetime
from ..templates.base_template import DocumentTemplate, load_template


class DocumentAnalyzer:
    """
    Main document analyzer that uses templates to analyze documents.

    This class coordinates the analysis process by:
    1. Loading a document template
    2. Preprocessing documents using the template
    3. Extracting sections from documents
    4. Matching patterns against document content
    5. Generating analysis reports
    """

    def __init__(self, template: Union[str, DocumentTemplate]):
        """
        Initialize the analyzer with a template.

        Args:
            template: Either a template name (string) or a DocumentTemplate instance
        """
        if isinstance(template, str):
            self.template = load_template(template)
        else:
            self.template = template

    def analyze_document(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single document.

        Args:
            content: Document content to analyze
            metadata: Optional document metadata (should include document_name, document_url, etc.)

        Returns:
            Analysis results dictionary containing:
            - sections: Extracted sections
            - matches: Pattern matches by category
            - themes: Extracted themes
            - metadata: Document metadata
        """
        # Ensure metadata has required fields
        if metadata is None:
            metadata = {}
        
        # Set defaults for required fields if not provided
        if "document_name" not in metadata:
            metadata["document_name"] = "unknown_document"
        if "document_url" not in metadata:
            metadata["document_url"] = ""
        if "document_id" not in metadata:
            # Generate a simple ID based on name and timestamp
            import hashlib
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            metadata["document_id"] = f"{metadata['document_name']}_{content_hash}"
        
        # Preprocess document
        processed_content = self.template.preprocess_document(content, metadata)

        # Extract sections
        sections = self.template.extract_sections(processed_content)

        # Match patterns against content
        matches = self._match_patterns(processed_content, sections)

        # Extract themes from matches
        themes = self._extract_themes(matches)

        return {
            "sections": sections,
            "matches": matches,
            "themes": themes,
            "metadata": metadata,
            "template": self.template.name,
        }

    def analyze_documents(
        self, documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple documents.

        Args:
            documents: List of document dictionaries with 'content' and optional 'metadata'
                      Each document should have metadata including 'document_name', 'document_url', etc.

        Returns:
            List of analysis results
        """
        results = []

        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            if content:
                analysis = self.analyze_document(content, metadata)
                results.append(analysis)

        return results

    def _match_patterns(
        self, content: str, sections: Dict[str, str]
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Match patterns against document content.

        Args:
            content: Processed document content
            sections: Extracted sections

        Returns:
            Nested dictionary of pattern matches by category and pattern name
        """
        matches = {}

        # Get analysis patterns from template
        analysis_patterns = self.template.analysis_patterns

        for category, patterns in analysis_patterns.items():
            matches[category] = {}

            for pattern_name, pattern in patterns.items():
                pattern_matches = []

                # Search in full content
                regex = re.compile(pattern, re.IGNORECASE)
                for match in regex.finditer(content):
                    pattern_matches.append(
                        {
                            "pattern": pattern_name,
                            "text": match.group(),
                            "start": match.start(),
                            "end": match.end(),
                            "context": self._get_context(
                                content, match.start(), match.end()
                            ),
                            "section": self._find_section_for_match(
                                match.start(), sections
                            ),
                        }
                    )

                # Also search in specific sections if available
                if category in sections:
                    section_content = sections[category]
                    for match in regex.finditer(section_content):
                        pattern_matches.append(
                            {
                                "pattern": pattern_name,
                                "text": match.group(),
                                "start": match.start(),
                                "end": match.end(),
                                "context": self._get_context(
                                    section_content, match.start(), match.end()
                                ),
                                "section": category,
                            }
                        )

                matches[category][pattern_name] = pattern_matches

        return matches

    def _extract_themes(
        self, matches: Dict[str, Dict[str, List[Dict[str, Any]]]]
    ) -> Dict[str, List[str]]:
        """
        Extract themes from pattern matches.

        Args:
            matches: Pattern matches by category

        Returns:
            Dictionary mapping theme names to descriptions
        """
        # Use template's theme extraction if available
        if hasattr(self.template, "extract_themes"):
            return self.template.extract_themes(matches)

        # Default theme extraction
        themes = {}

        for category, category_matches in matches.items():
            theme_counts = {}

            for pattern_name, pattern_matches in category_matches.items():
                if pattern_matches:  # Only count patterns with matches
                    theme_counts[pattern_name] = len(pattern_matches)

            if theme_counts:
                # Sort by frequency and take top themes
                sorted_themes = sorted(
                    theme_counts.items(), key=lambda x: x[1], reverse=True
                )
                top_themes = [
                    f"{theme.replace('_', ' ').title()} ({count} matches)"
                    for theme, count in sorted_themes[:3]
                ]
                themes[f"top_{category}"] = top_themes

        return themes

    def _get_context(
        self, content: str, start: int, end: int, context_size: int = 50
    ) -> str:
        """
        Get context around a match.

        Args:
            content: Document content
            start: Match start position
            end: Match end position
            context_size: Number of characters to include on each side

        Returns:
            Context string
        """
        context_start = max(0, start - context_size)
        context_end = min(len(content), end + context_size)

        context = content[context_start:context_end]

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(content):
            context = context + "..."

        return context

    def _find_section_for_match(
        self, match_start: int, sections: Dict[str, str]
    ) -> Optional[str]:
        """
        Find which section a match belongs to.

        Args:
            match_start: Start position of the match
            sections: Extracted sections

        Returns:
            Section name or None if not found
        """
        # This is a simplified implementation
        # In practice, you'd need to track section positions in the original content
        return None

    def get_summary(self, analysis_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary across multiple analysis results.

        Args:
            analysis_results: List of analysis results from analyze_documents

        Returns:
            Summary dictionary
        """
        total_docs = len(analysis_results)

        if not analysis_results:
            return {
                "total_documents": 0,
                "template": self.template.name,
                "overall_themes": {},
                "pattern_frequencies": {},
            }

        # Aggregate themes across all documents
        overall_themes = {}
        pattern_frequencies = {}

        for category in self.template.get_pattern_categories():
            pattern_frequencies[category] = {}

            for result in analysis_results:
                matches = result.get("matches", {})
                if category in matches:
                    for pattern_name, pattern_matches in matches[category].items():
                        if pattern_name not in pattern_frequencies[category]:
                            pattern_frequencies[category][pattern_name] = 0
                        pattern_frequencies[category][pattern_name] += len(
                            pattern_matches
                        )

        # Extract overall themes
        for category, patterns in pattern_frequencies.items():
            if patterns:
                sorted_patterns = sorted(
                    patterns.items(), key=lambda x: x[1], reverse=True
                )
                top_patterns = [
                    f"{pattern.replace('_', ' ').title()} ({count} total matches)"
                    for pattern, count in sorted_patterns[:5]
                    if count > 0
                ]
                overall_themes[f"top_{category}"] = top_patterns

        return {
            "total_documents": total_docs,
            "template": self.template.name,
            "overall_themes": overall_themes,
            "pattern_frequencies": pattern_frequencies,
        }

    def analyze_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """
        Analyze all documents in a directory.
        
        Args:
            directory_path: Path to directory containing documents
            
        Returns:
            List of analysis results
        """
        from pathlib import Path
        import pandas as pd
        
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Load the search_results.csv to map document names to URLs
        url_mapping = {}
        search_results_path = directory.parent / "search_results.csv"
        if search_results_path.exists():
            try:
                df = pd.read_csv(search_results_path)
                # Clean document names and create mapping
                for _, row in df.iterrows():
                    # Clean the name by stripping whitespace and removing prefixes
                    doc_name = str(row['name']).strip()
                    # Handle various document name formats
                    clean_name = doc_name
                    if clean_name.startswith('[') and ']' in clean_name:
                        # Remove prefixes like "[GivingTuesday Internal]" or "[Giving Tuesday Data Commons]"
                        clean_name = clean_name.split(']', 1)[1].strip()
                    
                    url_mapping[clean_name] = row['webViewLink']
                    # Also map the original name for exact matches
                    url_mapping[doc_name] = row['webViewLink']
                    
                print(f"Loaded URL mappings for {len(url_mapping)} documents")
            except Exception as e:
                print(f"Warning: Could not load search_results.csv: {e}")
        else:
            print(f"Warning: search_results.csv not found at {search_results_path}")
        
        results = []
        
        # Process markdown files
        for file_path in directory.glob("*.md"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Try to find URL from search_results mapping
                doc_name = file_path.stem
                document_url = ""
                
                # Clean the document name to match search_results.csv format
                clean_doc_name = doc_name
                if clean_doc_name.startswith('[') and ']' in clean_doc_name:
                    # Remove prefixes like "[Giving Tuesday Data Commons]" and strip spaces
                    clean_doc_name = clean_doc_name.split(']', 1)[1].strip()
                
                # Try multiple matching strategies
                if clean_doc_name in url_mapping:
                    document_url = url_mapping[clean_doc_name]
                elif doc_name in url_mapping:
                    document_url = url_mapping[doc_name]
                else:
                    # Try to find partial matches
                    for mapped_name, url in url_mapping.items():
                        if clean_doc_name in mapped_name or mapped_name in clean_doc_name:
                            document_url = url
                            break
                    # If still no match, try with original doc_name
                    if not document_url:
                        for mapped_name, url in url_mapping.items():
                            if doc_name in mapped_name or mapped_name in doc_name:
                                document_url = url
                                break
                
                # Fallback to extracting URLs from document content if no mapping found
                if not document_url:
                    import re
                    url_pattern = r'https?://[^\s\)\]\>]+' 
                    urls = re.findall(url_pattern, content)
                    document_url = urls[0] if urls else ""
                
                metadata = {
                    "document_name": file_path.stem,
                    "document_path": str(file_path),
                    "document_url": document_url,
                    "file_size": file_path.stat().st_size,
                    "modified_date": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                }
                
                analysis = self.analyze_document(content, metadata)
                results.append(analysis)
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        return results

    def export_to_dataframe_format(self, analysis_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert analysis results to a flat format suitable for pandas DataFrame.
        
        Args:
            analysis_results: List of analysis results from analyze_documents
            
        Returns:
            List of flattened dictionaries, one per document
        """
        flattened_results = []
        
        for result in analysis_results:
            # Start with core document metadata
            flat_record = {
                "document_name": result.get("metadata", {}).get("document_name", "unknown"),
                "document_url": result.get("metadata", {}).get("document_url", ""),
                "document_path": result.get("metadata", {}).get("document_path", ""),
                "template_used": result.get("template", "unknown"),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            # Add any additional metadata fields
            metadata = result.get("metadata", {})
            for key, value in metadata.items():
                if key not in ["document_name", "document_url", "document_path"]:
                    flat_record[f"metadata_{key}"] = value
            
            # Add sections as individual columns
            sections = result.get("sections", {})
            for section_name, section_content in sections.items():
                flat_record[f"section_{section_name}"] = section_content
            
            # Add pattern matches as JSON strings
            matches = result.get("matches", {})
            for category, category_matches in matches.items():
                flat_record[f"patterns_{category}"] = json.dumps(category_matches)
            
            # Add themes
            themes = result.get("themes", {})
            for theme_name, theme_content in themes.items():
                if isinstance(theme_content, list):
                    flat_record[f"themes_{theme_name}"] = "; ".join(theme_content)
                else:
                    flat_record[f"themes_{theme_name}"] = str(theme_content)
            
            flattened_results.append(flat_record)
        
        return flattened_results

    def export_to_csv(self, analysis_results: List[Dict[str, Any]], output_path: Optional[str] = None) -> str:
        """
        Export analysis results to CSV format.
        
        Args:
            analysis_results: List of analysis results
            output_path: Optional path to write CSV file
            
        Returns:
            CSV string content
        """
        flattened_data = self.export_to_dataframe_format(analysis_results)
        
        if not flattened_data:
            return "No data to export"
        
        # Get all unique column names across all records
        all_columns = set()
        for record in flattened_data:
            all_columns.update(record.keys())
        
        # Sort columns for consistent output
        sorted_columns = sorted(all_columns)
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=sorted_columns)
        writer.writeheader()
        
        for record in flattened_data:
            # Fill missing columns with empty strings
            complete_record = {col: record.get(col, "") for col in sorted_columns}
            writer.writerow(complete_record)
        
        csv_content = output.getvalue()
        
        # Write to file if path provided
        if output_path:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                f.write(csv_content)
        
        return csv_content

    def export_to_json(self, analysis_results: List[Dict[str, Any]], output_path: Optional[str] = None) -> str:
        """
        Export analysis results to JSON format.
        
        Args:
            analysis_results: List of analysis results
            output_path: Optional path to write JSON file
            
        Returns:
            JSON string content
        """
        flattened_data = self.export_to_dataframe_format(analysis_results)
        
        json_content = json.dumps(flattened_data, indent=2, ensure_ascii=False)
        
        # Write to file if path provided
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_content)
        
        return json_content
