"""Pandoc-based uploader for converting markdown to Google Docs via DOCX."""

import io
import tempfile
from pathlib import Path
from typing import Dict, Optional

import pypandoc
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from rich.console import Console

from .drive_uploader import GoogleDriveUploader


class PandocUploader:
    """Upload markdown to Google Docs via Pandoc → DOCX → Drive API conversion.

    This uploader uses Pandoc to convert markdown (with footnotes) to DOCX format,
    then uploads the DOCX to Google Drive where it's automatically converted to
    Google Docs format. This preserves footnotes as native Google Docs footnotes.
    """

    def __init__(self, uploader: GoogleDriveUploader):
        """Initialize the Pandoc uploader.

        Args:
            uploader: GoogleDriveUploader instance for Drive API access
        """
        self.uploader = uploader
        self.console = Console()

        # Verify pypandoc is available
        try:
            pypandoc.get_pandoc_version()
        except OSError as e:
            raise RuntimeError(
                "Pandoc is not installed or not found in PATH. "
                "Install it from https://pandoc.org/installing.html or use: "
                "brew install pandoc (macOS), apt-get install pandoc (Linux)"
            ) from e

    def convert_markdown_to_docx(
        self,
        markdown_path: Path,
        output_path: Optional[Path] = None,
        reference_doc: Optional[Path] = None
    ) -> Path:
        """Convert Pandoc markdown to DOCX with preserved footnotes.

        Args:
            markdown_path: Path to the markdown file
            output_path: Optional output path for DOCX (default: temp file)
            reference_doc: Optional reference DOCX for styling

        Returns:
            Path to the generated DOCX file

        Raises:
            RuntimeError: If Pandoc conversion fails
        """
        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        # Use temp file if no output path specified
        if output_path is None:
            # Create temp file with proper extension
            temp_fd, temp_path = tempfile.mkstemp(suffix='.docx')
            import os
            os.close(temp_fd)  # Close the file descriptor
            output_path = Path(temp_path)

        # Build Pandoc arguments
        extra_args = [
            '--standalone',  # Create complete document
            '--wrap=auto',   # Automatic text wrapping
        ]

        # Add reference doc if provided
        if reference_doc and reference_doc.exists():
            extra_args.append(f'--reference-doc={reference_doc}')

        try:
            pypandoc.convert_file(
                str(markdown_path),
                'docx',
                outputfile=str(output_path),
                extra_args=extra_args
            )

            if not output_path.exists():
                raise RuntimeError("Pandoc conversion produced no output file")

            return output_path

        except RuntimeError as e:
            error_msg = str(e)
            if 'Pandoc died with exitcode' in error_msg:
                raise RuntimeError(
                    f"Pandoc conversion failed: {error_msg}. "
                    "Check if your markdown file has syntax errors."
                ) from e
            raise RuntimeError(f"Pandoc conversion failed: {error_msg}") from e

    def upload_docx_as_google_doc(
        self,
        docx_path: Path,
        target_folder_id: str,
        doc_name: Optional[str] = None,
        skip_existing: bool = True
    ) -> Dict[str, str]:
        """Upload DOCX to Google Drive and convert to Google Docs format.

        Args:
            docx_path: Path to the DOCX file
            target_folder_id: ID of the target Google Drive folder
            doc_name: Custom name for the Google Doc (default: DOCX filename)
            skip_existing: Skip if document with same name exists

        Returns:
            Dict with upload result (same format as GoogleDriveUploader.upload_as_google_doc)
        """
        if not docx_path.exists():
            return {
                'source_file': str(docx_path),
                'name': doc_name or docx_path.stem,
                'id': None,
                'webViewLink': None,
                'status': 'error',
                'message': f"DOCX file not found: {docx_path}"
            }

        # Determine document name
        doc_name = doc_name or docx_path.stem

        result = {
            'source_file': str(docx_path),
            'name': doc_name,
            'id': None,
            'webViewLink': None,
            'status': 'pending',
            'message': ''
        }

        # Check for existing document
        if skip_existing:
            existing = self.uploader.check_existing_doc(target_folder_id, doc_name)
            if existing:
                result['status'] = 'skipped'
                result['id'] = existing['id']
                result['webViewLink'] = existing.get('webViewLink')
                result['message'] = f"Document already exists: {doc_name}"
                return result

        try:
            # Read DOCX file
            with open(docx_path, 'rb') as f:
                docx_bytes = f.read()

            # Prepare file metadata - set mimeType to Google Docs for automatic conversion
            file_metadata = {
                'name': doc_name,
                'mimeType': 'application/vnd.google-apps.document',  # Converts to Google Docs
                'parents': [target_folder_id]
            }

            # Create media upload from DOCX content
            media = MediaIoBaseUpload(
                io.BytesIO(docx_bytes),
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                resumable=True
            )

            # Upload and convert to Google Doc
            uploaded_file = self.uploader.drive_service.files().create(
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

    def upload_markdown_as_google_doc(
        self,
        markdown_path: Path,
        target_folder_id: str,
        custom_name: Optional[str] = None,
        skip_existing: bool = True,
        reference_doc: Optional[Path] = None,
        keep_docx: bool = False,
        docx_output_path: Optional[Path] = None
    ) -> Dict[str, str]:
        """Convert markdown to DOCX via Pandoc and upload as Google Doc.

        This is the main entry point that combines conversion and upload.

        Args:
            markdown_path: Path to the markdown file
            target_folder_id: ID of the target Google Drive folder
            custom_name: Custom name for the Google Doc (default: markdown filename)
            skip_existing: Skip if document with same name exists
            reference_doc: Optional reference DOCX for styling
            keep_docx: If True, keep the intermediate DOCX file
            docx_output_path: Where to save DOCX if keep_docx=True

        Returns:
            Dict with upload result including:
                - id: Google Doc ID
                - name: Document name
                - webViewLink: URL to view the document
                - status: 'created', 'skipped', or 'error'
                - message: Status message
                - docx_path: Path to DOCX file (if keep_docx=True)
        """
        doc_name = custom_name or markdown_path.stem

        result = {
            'source_file': str(markdown_path),
            'name': doc_name,
            'id': None,
            'webViewLink': None,
            'status': 'pending',
            'message': ''
        }

        if not markdown_path.exists():
            result['status'] = 'error'
            result['message'] = f"Markdown file not found: {markdown_path}"
            return result

        docx_path = None
        temp_docx = False

        try:
            # Convert markdown to DOCX
            if keep_docx and docx_output_path:
                docx_path = docx_output_path
            else:
                docx_path = None  # Will create temp file
                temp_docx = True

            docx_path = self.convert_markdown_to_docx(
                markdown_path,
                output_path=docx_path,
                reference_doc=reference_doc
            )

            if keep_docx:
                result['docx_path'] = str(docx_path)

            # Upload DOCX as Google Doc
            upload_result = self.upload_docx_as_google_doc(
                docx_path,
                target_folder_id,
                doc_name=doc_name,
                skip_existing=skip_existing
            )

            # Merge upload result into our result
            result.update(upload_result)

        except (RuntimeError, FileNotFoundError) as e:
            result['status'] = 'error'
            result['message'] = str(e)
        except Exception as e:
            result['status'] = 'error'
            result['message'] = f"Unexpected error: {e}"
        finally:
            # Clean up temp DOCX if needed
            if temp_docx and docx_path and docx_path.exists():
                try:
                    docx_path.unlink()
                except Exception:
                    pass  # Ignore cleanup errors

        return result
