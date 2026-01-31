"""Google Drive uploading functionality for markdown files."""

import io
import os
import pickle
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..config import DriveConfig


class MarkdownToDocsConverter:
    """Converts markdown content to Google Docs API batchUpdate requests."""

    # Named style types for headings
    HEADING_STYLES = {
        1: 'HEADING_1',
        2: 'HEADING_2',
        3: 'HEADING_3',
        4: 'HEADING_4',
        5: 'HEADING_5',
        6: 'HEADING_6',
    }

    def __init__(self):
        try:
            from markdown_it import MarkdownIt
            from mdit_py_plugins.footnote import footnote_plugin

            self.md = MarkdownIt("commonmark")
            self.md.use(footnote_plugin)  # Enable footnote support
            self.footnote_definitions = {}  # Store footnote content by ID
        except ImportError:
            raise ImportError("markdown-it-py and mdit-py-plugins are required")

    def convert(self, markdown_content: str, tab_id: Optional[str] = None) -> List[dict]:
        """Convert markdown to Google Docs API requests.

        Args:
            markdown_content: The markdown text to convert
            tab_id: Optional tab ID to target

        Returns:
            List of batchUpdate request dicts
        """
        # Reset footnote definitions for each conversion
        self.footnote_definitions = {}

        tokens = self.md.parse(markdown_content)
        requests = []
        current_index = 1  # Google Docs starts at index 1

        # First pass: collect all text and structure (including footnote definitions)
        elements = self._parse_tokens(tokens)

        # Second pass: generate requests
        # Note: footnote insertions are handled within _generate_style_requests
        # and automatically adjust the document indices
        for element in elements:
            elem_requests, new_index = self._generate_requests(
                element, current_index, tab_id
            )
            requests.extend(elem_requests)
            current_index = new_index

        return requests

    def _parse_tokens(self, tokens: list) -> List[dict]:
        """Parse markdown-it tokens into structured elements."""
        elements = []
        i = 0

        while i < len(tokens):
            token = tokens[i]

            if token.type == 'heading_open':
                level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.
                # Next token should be inline with content
                if i + 1 < len(tokens) and tokens[i + 1].type == 'inline':
                    text, inline_styles = self._parse_inline(tokens[i + 1])
                    elements.append({
                        'type': 'heading',
                        'level': level,
                        'text': text + '\n',
                        'styles': inline_styles
                    })
                i += 3  # Skip heading_open, inline, heading_close

            elif token.type == 'paragraph_open':
                if i + 1 < len(tokens) and tokens[i + 1].type == 'inline':
                    text, inline_styles = self._parse_inline(tokens[i + 1])
                    elements.append({
                        'type': 'paragraph',
                        'text': text + '\n',
                        'styles': inline_styles
                    })
                i += 3  # Skip paragraph_open, inline, paragraph_close

            elif token.type == 'bullet_list_open':
                # Collect all list items
                list_items = []
                i += 1
                while i < len(tokens) and tokens[i].type != 'bullet_list_close':
                    if tokens[i].type == 'list_item_open':
                        i += 1
                        if i < len(tokens) and tokens[i].type == 'paragraph_open':
                            i += 1
                            if i < len(tokens) and tokens[i].type == 'inline':
                                text, styles = self._parse_inline(tokens[i])
                                list_items.append({'text': text, 'styles': styles})
                            i += 2  # Skip inline and paragraph_close
                        i += 1  # Skip list_item_close
                    else:
                        i += 1
                elements.append({
                    'type': 'bullet_list',
                    'items': list_items
                })
                i += 1  # Skip bullet_list_close

            elif token.type == 'ordered_list_open':
                list_items = []
                i += 1
                while i < len(tokens) and tokens[i].type != 'ordered_list_close':
                    if tokens[i].type == 'list_item_open':
                        i += 1
                        if i < len(tokens) and tokens[i].type == 'paragraph_open':
                            i += 1
                            if i < len(tokens) and tokens[i].type == 'inline':
                                text, styles = self._parse_inline(tokens[i])
                                list_items.append({'text': text, 'styles': styles})
                            i += 2
                        i += 1
                    else:
                        i += 1
                elements.append({
                    'type': 'ordered_list',
                    'items': list_items
                })
                i += 1

            elif token.type == 'fence':
                # Code block
                elements.append({
                    'type': 'code_block',
                    'text': token.content + '\n',
                    'language': token.info
                })
                i += 1

            elif token.type == 'hr':
                elements.append({'type': 'hr'})
                i += 1

            elif token.type == 'footnote_block_open':
                # Parse footnote definitions
                i += 1
                footnote_id = 0
                while i < len(tokens) and tokens[i].type != 'footnote_block_close':
                    if tokens[i].type == 'footnote_open':
                        # Get footnote ID from meta
                        footnote_meta = tokens[i].meta
                        footnote_id = footnote_meta.get('id', footnote_id)
                        i += 1

                        # Collect footnote content (typically paragraph with inline)
                        footnote_content = ''
                        while i < len(tokens) and tokens[i].type != 'footnote_close':
                            if tokens[i].type == 'inline':
                                footnote_content, _ = self._parse_inline_with_state(tokens[i].children)
                            i += 1

                        # Store footnote content by ID
                        self.footnote_definitions[footnote_id] = footnote_content
                        i += 1  # Skip footnote_close
                    else:
                        i += 1
                i += 1  # Skip footnote_block_close

            else:
                i += 1

        return elements

    def _parse_inline(self, token) -> Tuple[str, List[dict]]:
        """Parse inline token and extract text with style ranges."""
        if not token.children:
            return token.content or '', []

        text = ''
        styles = []

        for child in token.children:
            start = len(text)

            if child.type == 'text':
                text += child.content
            elif child.type == 'code_inline':
                text += child.content
                styles.append({
                    'type': 'code',
                    'start': start,
                    'end': len(text)
                })
            elif child.type == 'strong_open':
                # Find content until strong_close
                pass  # Handled by tracking state
            elif child.type == 'em_open':
                pass
            elif child.type == 'softbreak':
                text += ' '
            elif child.type == 'hardbreak':
                text += '\n'
            elif child.type == 'link_open':
                # Get href from attrs
                href = ''
                if child.attrs:
                    href = dict(child.attrs).get('href', '')
                styles.append({
                    'type': 'link_start',
                    'start': len(text),
                    'href': href
                })
            elif child.type == 'link_close':
                # Find matching link_start and update end
                for style in reversed(styles):
                    if style.get('type') == 'link_start':
                        style['type'] = 'link'
                        style['end'] = len(text)
                        break

        # Handle bold/italic by re-parsing with state tracking
        text, styles = self._parse_inline_with_state(token.children)

        return text, styles

    def _parse_inline_with_state(self, children: list) -> Tuple[str, List[dict]]:
        """Parse inline children with state tracking for nested styles."""
        text = ''
        styles = []
        bold_start = None
        italic_start = None
        link_start = None
        link_href = None

        for child in children:
            if child.type == 'text':
                text += child.content
            elif child.type == 'code_inline':
                start = len(text)
                text += child.content
                styles.append({'type': 'code', 'start': start, 'end': len(text)})
            elif child.type == 'strong_open':
                bold_start = len(text)
            elif child.type == 'strong_close':
                if bold_start is not None:
                    styles.append({'type': 'bold', 'start': bold_start, 'end': len(text)})
                    bold_start = None
            elif child.type == 'em_open':
                italic_start = len(text)
            elif child.type == 'em_close':
                if italic_start is not None:
                    styles.append({'type': 'italic', 'start': italic_start, 'end': len(text)})
                    italic_start = None
            elif child.type == 'link_open':
                link_start = len(text)
                if child.attrs:
                    link_href = dict(child.attrs).get('href', '')
            elif child.type == 'link_close':
                if link_start is not None and link_href:
                    styles.append({
                        'type': 'link',
                        'start': link_start,
                        'end': len(text),
                        'href': link_href
                    })
                    link_start = None
                    link_href = None
            elif child.type == 'softbreak':
                text += ' '
            elif child.type == 'hardbreak':
                text += '\n'
            elif child.type == 'footnote_ref':
                # Track footnote reference position
                # The footnote will be inserted at this position in the document
                footnote_label = child.meta.get('label', '1')
                footnote_id = child.meta.get('id', 0)
                styles.append({
                    'type': 'footnote_ref',
                    'position': len(text),
                    'label': footnote_label,
                    'id': footnote_id
                })
                # Don't add any text - footnote will be inserted via API

        return text, styles

    def _generate_requests(
        self,
        element: dict,
        start_index: int,
        tab_id: Optional[str]
    ) -> Tuple[List[dict], int]:
        """Generate API requests for a single element.

        Returns:
            Tuple of (requests list, new current index)
        """
        requests = []
        location_base = {'index': start_index}
        if tab_id:
            location_base['tabId'] = tab_id

        if element['type'] == 'heading':
            text = element['text']
            end_index = start_index + len(text)

            # Insert text
            requests.append({
                'insertText': {
                    'location': dict(location_base),
                    'text': text
                }
            })

            # Apply heading style
            range_base = {
                'startIndex': start_index,
                'endIndex': end_index - 1  # Exclude newline from style
            }
            if tab_id:
                range_base['tabId'] = tab_id

            requests.append({
                'updateParagraphStyle': {
                    'range': range_base,
                    'paragraphStyle': {
                        'namedStyleType': self.HEADING_STYLES.get(element['level'], 'HEADING_1')
                    },
                    'fields': 'namedStyleType'
                }
            })

            # Apply inline styles
            requests.extend(self._generate_style_requests(
                element.get('styles', []), start_index, tab_id
            ))

            return requests, end_index

        elif element['type'] == 'paragraph':
            text = element['text']
            end_index = start_index + len(text)

            requests.append({
                'insertText': {
                    'location': dict(location_base),
                    'text': text
                }
            })

            # Apply inline styles
            requests.extend(self._generate_style_requests(
                element.get('styles', []), start_index, tab_id
            ))

            return requests, end_index

        elif element['type'] in ('bullet_list', 'ordered_list'):
            items = element['items']
            text = '\n'.join(item['text'] for item in items) + '\n'
            end_index = start_index + len(text)

            # Insert all list text
            requests.append({
                'insertText': {
                    'location': dict(location_base),
                    'text': text
                }
            })

            # Apply bullet/number formatting
            range_base = {
                'startIndex': start_index,
                'endIndex': end_index - 1
            }
            if tab_id:
                range_base['tabId'] = tab_id

            bullet_preset = (
                'BULLET_DISC_CIRCLE_SQUARE' if element['type'] == 'bullet_list'
                else 'NUMBERED_DECIMAL_ALPHA_ROMAN'
            )

            requests.append({
                'createParagraphBullets': {
                    'range': range_base,
                    'bulletPreset': bullet_preset
                }
            })

            # Apply inline styles for each item
            current = start_index
            for item in items:
                requests.extend(self._generate_style_requests(
                    item.get('styles', []), current, tab_id
                ))
                current += len(item['text']) + 1  # +1 for newline

            return requests, end_index

        elif element['type'] == 'code_block':
            text = element['text']
            end_index = start_index + len(text)

            requests.append({
                'insertText': {
                    'location': dict(location_base),
                    'text': text
                }
            })

            # Apply monospace font
            range_base = {
                'startIndex': start_index,
                'endIndex': end_index
            }
            if tab_id:
                range_base['tabId'] = tab_id

            requests.append({
                'updateTextStyle': {
                    'range': range_base,
                    'textStyle': {
                        'weightedFontFamily': {
                            'fontFamily': 'Courier New'
                        }
                    },
                    'fields': 'weightedFontFamily'
                }
            })

            return requests, end_index

        elif element['type'] == 'hr':
            # Insert a horizontal line using repeated dashes
            text = '─' * 50 + '\n'
            end_index = start_index + len(text)

            requests.append({
                'insertText': {
                    'location': dict(location_base),
                    'text': text
                }
            })

            return requests, end_index

        return requests, start_index

    def _generate_style_requests(
        self,
        styles: List[dict],
        base_index: int,
        tab_id: Optional[str]
    ) -> List[dict]:
        """Generate text style requests for inline formatting.

        Note: Footnote references in styles are ignored as Google Docs API
        footnote creation requires a complex two-pass process that is not
        currently supported. Footnotes will appear as plain text (e.g., [^1]).
        """
        requests = []

        for style in styles:
            # Skip footnote references - they'll appear as plain text
            if style.get('type') == 'footnote_ref':
                continue

            range_base = {
                'startIndex': base_index + style['start'],
                'endIndex': base_index + style['end']
            }
            if tab_id:
                range_base['tabId'] = tab_id

            if style['type'] == 'bold':
                requests.append({
                    'updateTextStyle': {
                        'range': range_base,
                        'textStyle': {'bold': True},
                        'fields': 'bold'
                    }
                })
            elif style['type'] == 'italic':
                requests.append({
                    'updateTextStyle': {
                        'range': range_base,
                        'textStyle': {'italic': True},
                        'fields': 'italic'
                    }
                })
            elif style['type'] == 'code':
                requests.append({
                    'updateTextStyle': {
                        'range': range_base,
                        'textStyle': {
                            'weightedFontFamily': {'fontFamily': 'Courier New'}
                        },
                        'fields': 'weightedFontFamily'
                    }
                })
            elif style['type'] == 'link':
                requests.append({
                    'updateTextStyle': {
                        'range': range_base,
                        'textStyle': {
                            'link': {'url': style['href']}
                        },
                        'fields': 'link'
                    }
                })

        return requests

try:
    from markdown_it import MarkdownIt
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False


class GoogleDriveUploader:
    """Uploads markdown files as native Google Docs to Google Drive."""

    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/documents'
    ]

    # Google Docs import limit (approximately 1.5MB for HTML)
    MAX_IMPORT_SIZE = 1.5 * 1024 * 1024  # 1.5 MB

    def __init__(self, config: DriveConfig):
        self.config = config
        self.console = Console()
        self.drive_service = None
        self.docs_service = None
        # Keep 'service' as alias for backwards compatibility
        self.service = None
        self._setup_service()

        if not MARKDOWN_IT_AVAILABLE:
            raise ImportError(
                "markdown-it-py is required for markdown to HTML conversion. "
                "Install it with: pip install markdown-it-py"
            )

        self.md = MarkdownIt("commonmark", {"html": True, "typographer": True})
        self.markdown_converter = MarkdownToDocsConverter()

    def _setup_service(self):
        """Initialize Google Drive and Docs API services."""
        creds = None

        if self.config.token_file and self.config.token_file.exists():
            with open(self.config.token_file, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.config.credentials_file or not self.config.credentials_file.exists():
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.config.credentials_file}"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config.credentials_file, self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            if self.config.token_file:
                self.config.token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.config.token_file, 'wb') as token:
                    pickle.dump(creds, token)

        self.drive_service = build('drive', 'v3', credentials=creds)
        self.docs_service = build('docs', 'v1', credentials=creds)
        # Backwards compatibility alias
        self.service = self.drive_service

    def extract_folder_id(self, folder_url: str) -> str:
        """Extract folder ID from Google Drive URL."""
        if '/folders/' in folder_url:
            folder_part = folder_url.split('/folders/')[1]
            return folder_part.split('?')[0].split('/')[0]

        parsed = urlparse(folder_url)
        if 'id' in parse_qs(parsed.query):
            return parse_qs(parsed.query)['id'][0]

        raise ValueError(f"Cannot extract folder ID from URL: {folder_url}")

    def extract_doc_and_tab_id(self, doc_url: str) -> Tuple[str, Optional[str]]:
        """Extract document ID and optional tab ID from a Google Doc URL.

        Args:
            doc_url: Google Doc URL, may include tab parameter

        Returns:
            Tuple of (document_id, tab_id) where tab_id may be None

        Supported URL formats:
            - https://docs.google.com/document/d/DOC_ID/edit
            - https://docs.google.com/document/d/DOC_ID/edit?tab=t.TAB_ID
            - https://docs.google.com/document/d/DOC_ID/edit#tab=t.TAB_ID
        """
        doc_id = None
        tab_id = None

        # Extract document ID
        match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', doc_url)
        if match:
            doc_id = match.group(1)
        else:
            raise ValueError(f"Cannot extract document ID from URL: {doc_url}")

        # Extract tab ID from query string or fragment
        parsed = urlparse(doc_url)

        # Check query parameters (?tab=t.xxx)
        query_params = parse_qs(parsed.query)
        if 'tab' in query_params:
            tab_id = query_params['tab'][0]

        # Check fragment (#tab=t.xxx)
        if not tab_id and parsed.fragment:
            frag_match = re.search(r'tab=([^&]+)', parsed.fragment)
            if frag_match:
                tab_id = frag_match.group(1)

        return doc_id, tab_id

    def get_document_info(
        self,
        doc_id: str,
        include_tabs: bool = True
    ) -> Dict:
        """Get document metadata including tab information.

        Args:
            doc_id: Google Doc document ID
            include_tabs: Whether to include tab content

        Returns:
            Document metadata dict
        """
        try:
            doc = self.docs_service.documents().get(
                documentId=doc_id,
                includeTabsContent=include_tabs
            ).execute()
            return doc
        except HttpError as e:
            if e.resp.status == 404:
                raise ValueError(f"Document not found: {doc_id}")
            elif e.resp.status == 403:
                # Check if this is an API not enabled error
                error_str = str(e)
                if 'SERVICE_DISABLED' in error_str or 'has not been used' in error_str:
                    raise ValueError(
                        f"Google Docs API is not enabled for this project. "
                        f"Enable it at: https://console.developers.google.com/apis/api/docs.googleapis.com"
                    )
                raise ValueError(f"No access to document: {doc_id}")
            raise ValueError(f"Error accessing document: {e}")

    def get_tab_info(self, doc_id: str, tab_id: Optional[str] = None) -> Dict:
        """Get information about a specific tab or the first tab.

        Args:
            doc_id: Document ID
            tab_id: Tab ID (None for first tab)

        Returns:
            Dict with tab info: id, title, content_length
        """
        doc = self.get_document_info(doc_id)
        tabs = doc.get('tabs', [])

        if not tabs:
            raise ValueError("Document has no tabs")

        if tab_id:
            # Find specific tab
            for tab in tabs:
                props = tab.get('tabProperties', {})
                if props.get('tabId') == tab_id:
                    doc_tab = tab.get('documentTab', {})
                    body = doc_tab.get('body', {})
                    content = body.get('content', [])
                    # Calculate content length from last element's endIndex
                    end_index = 1
                    if content:
                        last_elem = content[-1]
                        end_index = last_elem.get('endIndex', 1)
                    return {
                        'id': props.get('tabId'),
                        'title': props.get('title', 'Untitled'),
                        'index': props.get('index', 0),
                        'content_length': end_index
                    }
            raise ValueError(f"Tab not found: {tab_id}")
        else:
            # Return first tab
            first_tab = tabs[0]
            props = first_tab.get('tabProperties', {})
            doc_tab = first_tab.get('documentTab', {})
            body = doc_tab.get('body', {})
            content = body.get('content', [])
            end_index = 1
            if content:
                last_elem = content[-1]
                end_index = last_elem.get('endIndex', 1)
            return {
                'id': props.get('tabId'),
                'title': props.get('title', 'Untitled'),
                'index': props.get('index', 0),
                'content_length': end_index
            }

    def get_tab_content_preview(
        self,
        doc_id: str,
        tab_id: Optional[str] = None,
        max_chars: int = 500
    ) -> str:
        """Get a text preview of tab content.

        Args:
            doc_id: Document ID
            tab_id: Tab ID (None for first tab)
            max_chars: Maximum characters to return

        Returns:
            Plain text preview of tab content
        """
        doc = self.get_document_info(doc_id)
        tabs = doc.get('tabs', [])

        target_tab = None
        if tab_id:
            for tab in tabs:
                if tab.get('tabProperties', {}).get('tabId') == tab_id:
                    target_tab = tab
                    break
        else:
            target_tab = tabs[0] if tabs else None

        if not target_tab:
            return "(empty)"

        doc_tab = target_tab.get('documentTab', {})
        body = doc_tab.get('body', {})
        content = body.get('content', [])

        # Extract text from content elements
        text_parts = []
        for element in content:
            if 'paragraph' in element:
                para = element['paragraph']
                for elem in para.get('elements', []):
                    if 'textRun' in elem:
                        text_parts.append(elem['textRun'].get('content', ''))

        full_text = ''.join(text_parts).strip()
        if len(full_text) > max_chars:
            return full_text[:max_chars] + '...'
        return full_text if full_text else "(empty)"

    def write_to_tab(
        self,
        doc_id: str,
        markdown_content: str,
        tab_id: Optional[str] = None,
        replace: bool = False
    ) -> Dict[str, str]:
        """Write markdown content to a specific tab in a document.

        Args:
            doc_id: Document ID
            markdown_content: Markdown text to write
            tab_id: Tab ID (None for first tab)
            replace: If True, clear existing content first

        Returns:
            Dict with result info
        """
        result = {
            'doc_id': doc_id,
            'tab_id': tab_id,
            'status': 'pending',
            'message': '',
            'webViewLink': None
        }

        try:
            # Get tab info
            tab_info = self.get_tab_info(doc_id, tab_id)
            actual_tab_id = tab_info['id']
            result['tab_id'] = actual_tab_id

            requests = []

            if replace:
                # Delete existing content (keep index 1, the minimum)
                if tab_info['content_length'] > 1:
                    delete_range = {
                        'startIndex': 1,
                        'endIndex': tab_info['content_length'] - 1
                    }
                    if actual_tab_id:
                        delete_range['tabId'] = actual_tab_id

                    requests.append({
                        'deleteContentRange': {
                            'range': delete_range
                        }
                    })

            # Convert markdown to API requests
            insert_requests = self.markdown_converter.convert(
                markdown_content,
                actual_tab_id
            )

            # Adjust indices if not replacing (append mode)
            if not replace and tab_info['content_length'] > 1:
                # Insert before the final newline (end_index - 1 is last char position)
                # Converter starts at index 1, so offset = (end_index - 1) - 1
                offset = tab_info['content_length'] - 2
                for req in insert_requests:
                    if 'insertText' in req:
                        req['insertText']['location']['index'] += offset
                    elif 'updateTextStyle' in req:
                        req['updateTextStyle']['range']['startIndex'] += offset
                        req['updateTextStyle']['range']['endIndex'] += offset
                    elif 'updateParagraphStyle' in req:
                        req['updateParagraphStyle']['range']['startIndex'] += offset
                        req['updateParagraphStyle']['range']['endIndex'] += offset
                    elif 'createParagraphBullets' in req:
                        req['createParagraphBullets']['range']['startIndex'] += offset
                        req['createParagraphBullets']['range']['endIndex'] += offset

            requests.extend(insert_requests)

            if not requests:
                result['status'] = 'skipped'
                result['message'] = 'No content to write'
                return result

            # Execute batch update
            self.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            # Build web link
            web_link = f"https://docs.google.com/document/d/{doc_id}/edit"
            if actual_tab_id:
                web_link += f"?tab={actual_tab_id}"

            result['status'] = 'success'
            result['message'] = f"Successfully wrote to tab '{tab_info['title']}'"
            result['webViewLink'] = web_link

        except HttpError as e:
            result['status'] = 'error'
            if e.resp.status == 403:
                result['message'] = f"No write permission for document: {doc_id}"
            else:
                result['message'] = f"API error: {e}"
        except ValueError as e:
            result['status'] = 'error'
            result['message'] = str(e)
        except Exception as e:
            result['status'] = 'error'
            result['message'] = f"Error: {e}"

        return result

    def write_markdown_file_to_tab(
        self,
        markdown_path: Path,
        doc_id: str,
        tab_id: Optional[str] = None,
        replace: bool = False
    ) -> Dict[str, str]:
        """Write a markdown file to a specific tab.

        Args:
            markdown_path: Path to markdown file
            doc_id: Document ID
            tab_id: Tab ID (None for first tab)
            replace: If True, clear existing content first

        Returns:
            Dict with result info
        """
        if not markdown_path.exists():
            return {
                'doc_id': doc_id,
                'tab_id': tab_id,
                'status': 'error',
                'message': f"File not found: {markdown_path}",
                'webViewLink': None
            }

        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        return self.write_to_tab(doc_id, markdown_content, tab_id, replace)

    def convert_markdown_to_html(self, markdown_path: Path) -> str:
        """Convert a markdown file to HTML.

        Args:
            markdown_path: Path to the markdown file

        Returns:
            HTML string with proper document structure
        """
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        # Convert markdown to HTML body
        html_body = self.md.render(markdown_content)

        # Wrap in a proper HTML document for Google Docs import
        # Add CSS to minimize style override and promote inheritance from target document
        title = markdown_path.stem
        html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        /* Prevent explicit font specifications to allow target document styles to apply */
        body {{
            font-family: sans-serif;
            font-size: inherit;
        }}
        /* Let headings use document's heading styles */
        h1, h2, h3, h4, h5, h6 {{
            font-family: inherit;
        }}
        /* Normal paragraph text should inherit from document */
        p {{
            font-family: inherit;
            font-size: inherit;
            margin: 1em 0;
        }}
        /* Code blocks should use monospace */
        pre, code {{
            font-family: 'Courier New', monospace;
        }}
        /* Remove any other styling that might interfere */
        * {{
            -webkit-text-size-adjust: none;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""

        return html_document

    def verify_folder_access(self, folder_id: str) -> Dict[str, str]:
        """Verify target folder exists and is writable.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            Dict with folder metadata (id, name, mimeType)

        Raises:
            ValueError: If folder doesn't exist or isn't writable
        """
        try:
            folder_info = self.service.files().get(
                fileId=folder_id,
                fields="id,name,mimeType,capabilities",
                supportsAllDrives=True
            ).execute()

            if folder_info.get('mimeType') != 'application/vnd.google-apps.folder':
                raise ValueError(f"Target ID {folder_id} is not a folder")

            # Check write permissions
            capabilities = folder_info.get('capabilities', {})
            can_add_children = capabilities.get('canAddChildren', False)

            if not can_add_children:
                raise ValueError(f"No write access to folder: {folder_info.get('name', folder_id)}")

            return {
                'id': folder_info['id'],
                'name': folder_info.get('name', 'Unknown Folder'),
                'mimeType': folder_info['mimeType']
            }

        except HttpError as e:
            if e.resp.status == 404:
                raise ValueError(f"Folder not found: {folder_id}")
            raise ValueError(f"Cannot access folder: {e}")

    def check_existing_doc(self, folder_id: str, doc_name: str) -> Optional[Dict[str, str]]:
        """Check if a document with the given name exists in the folder.

        Args:
            folder_id: Target folder ID
            doc_name: Document name to check

        Returns:
            File info dict if exists, None otherwise
        """
        try:
            # Search for exact name match in folder
            query = (
                f"'{folder_id}' in parents and "
                f"name = '{doc_name}' and "
                f"mimeType = 'application/vnd.google-apps.document' and "
                f"trashed = false"
            )

            response = self.service.files().list(
                q=query,
                fields="files(id,name,webViewLink)",
                pageSize=1,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            files = response.get('files', [])
            if files:
                return files[0]
            return None

        except HttpError:
            return None

    def upload_as_google_doc(
        self,
        markdown_path: Path,
        target_folder_id: str,
        custom_name: Optional[str] = None,
        skip_existing: bool = True
    ) -> Dict[str, str]:
        """Upload a markdown file as a native Google Doc.

        Args:
            markdown_path: Path to the markdown file
            target_folder_id: ID of the target Google Drive folder
            custom_name: Custom name for the Google Doc (default: markdown filename without extension)
            skip_existing: Skip if document with same name exists (default: True)

        Returns:
            Dict with upload result:
                - id: Google Doc ID
                - name: Document name
                - webViewLink: URL to view the document
                - status: 'created', 'skipped', or 'error'
                - message: Status message
        """
        # Determine document name
        doc_name = custom_name or markdown_path.stem

        result = {
            'source_file': str(markdown_path),
            'name': doc_name,
            'id': None,
            'webViewLink': None,
            'status': 'pending',
            'message': ''
        }

        # Check if file exists
        if not markdown_path.exists():
            result['status'] = 'error'
            result['message'] = f"File not found: {markdown_path}"
            return result

        # Check for existing document
        if skip_existing:
            existing = self.check_existing_doc(target_folder_id, doc_name)
            if existing:
                result['status'] = 'skipped'
                result['id'] = existing['id']
                result['webViewLink'] = existing.get('webViewLink')
                result['message'] = f"Document already exists: {doc_name}"
                return result

        try:
            # Convert markdown to HTML
            html_content = self.convert_markdown_to_html(markdown_path)

            # Check size limit
            html_bytes = html_content.encode('utf-8')
            if len(html_bytes) > self.MAX_IMPORT_SIZE:
                result['status'] = 'error'
                result['message'] = (
                    f"File too large for Google Docs import. "
                    f"Size: {len(html_bytes) / 1024 / 1024:.2f}MB, "
                    f"Limit: {self.MAX_IMPORT_SIZE / 1024 / 1024:.2f}MB"
                )
                return result

            # Prepare file metadata
            file_metadata = {
                'name': doc_name,
                'mimeType': 'application/vnd.google-apps.document',
                'parents': [target_folder_id]
            }

            # Create media upload from HTML content
            media = MediaIoBaseUpload(
                io.BytesIO(html_bytes),
                mimetype='text/html',
                resumable=True
            )

            # Upload and convert to Google Doc
            uploaded_file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink',
                supportsAllDrives=True
            ).execute()

            result['id'] = uploaded_file['id']
            result['name'] = uploaded_file['name']
            result['webViewLink'] = uploaded_file.get('webViewLink')
            result['status'] = 'created'
            result['message'] = f"Successfully uploaded: {doc_name}"

        except HttpError as e:
            result['status'] = 'error'
            result['message'] = f"Upload failed: {e}"

        except Exception as e:
            result['status'] = 'error'
            result['message'] = f"Error processing file: {e}"

        return result

    def upload_multiple(
        self,
        markdown_paths: List[Path],
        target_folder_id: str,
        skip_existing: bool = True,
        progress_callback=None
    ) -> List[Dict[str, str]]:
        """Upload multiple markdown files as Google Docs.

        Args:
            markdown_paths: List of markdown file paths
            target_folder_id: ID of the target Google Drive folder
            skip_existing: Skip if document with same name exists
            progress_callback: Optional callback function for progress updates

        Returns:
            List of upload result dicts
        """
        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Uploading files...", total=len(markdown_paths))

            for markdown_path in markdown_paths:
                result = self.upload_as_google_doc(
                    markdown_path,
                    target_folder_id,
                    skip_existing=skip_existing
                )
                results.append(result)

                if progress_callback:
                    progress_callback(result)

                progress.advance(task)

        return results
