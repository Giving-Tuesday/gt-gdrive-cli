"""gdrive-unified - Unified toolkit for Google Drive operations and document analysis.

This package combines Google Drive download/upload/search functionality with
document analysis capabilities. It provides:

- Drive operations: Download, upload, search, and manage Google Drive files
- Document conversion: Convert Google Docs to Markdown and vice versa
- Document analysis: Analyze documents using configurable templates
- GUI application: Desktop interface for Drive operations

Basic usage:

    from gdrive_unified import GoogleDriveDownloader, GoogleDriveSearcher
    from gdrive_unified.credentials import get_credentials

    # Get authenticated credentials
    creds = get_credentials()

    # Download files
    downloader = GoogleDriveDownloader(creds)
    downloader.download_file(file_id, output_path)

    # Search for files
    searcher = GoogleDriveSearcher(creds)
    results = searcher.search("budget report")

For document analysis:

    from gdrive_unified import DocumentAnalyzer, load_template

    template = load_template("aar")
    analyzer = DocumentAnalyzer(template)
    results = analyzer.analyze_documents(documents)

"""

__version__ = "1.0.0"
__author__ = "GivingTuesday"

# Import handling for optional dependencies
_DRIVE_AVAILABLE = False
_ANALYZER_AVAILABLE = False

try:
    from .drive import (
        GoogleDriveDownloader,
        GoogleDriveSearcher,
        GoogleDriveUploader,
        FileConverter,
        FileRelationshipTracker,
        PandocUploader,
    )
    _DRIVE_AVAILABLE = True
except ImportError:
    GoogleDriveDownloader = None  # type: ignore
    GoogleDriveSearcher = None  # type: ignore
    GoogleDriveUploader = None  # type: ignore
    FileConverter = None  # type: ignore
    FileRelationshipTracker = None  # type: ignore
    PandocUploader = None  # type: ignore

try:
    from .analyzer import (
        DocumentAnalyzer,
        PatternMatcher,
        PatternMatch,
    )
    from .templates import (
        DocumentTemplate,
        load_template,
        list_available_templates,
    )
    _ANALYZER_AVAILABLE = True
except ImportError:
    DocumentAnalyzer = None  # type: ignore
    PatternMatcher = None  # type: ignore
    PatternMatch = None  # type: ignore
    DocumentTemplate = None  # type: ignore
    load_template = None  # type: ignore
    list_available_templates = None  # type: ignore

# Configuration always available
from .config import GlobalConfig, DriveConfig, AnalyzerConfig, get_config
from .credentials import get_credentials, get_credentials_info

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Configuration
    "GlobalConfig",
    "DriveConfig",
    "AnalyzerConfig",
    "get_config",
    # Credentials
    "get_credentials",
    "get_credentials_info",
    # Drive operations (may be None if imports fail)
    "GoogleDriveDownloader",
    "GoogleDriveSearcher",
    "GoogleDriveUploader",
    "FileConverter",
    "FileRelationshipTracker",
    "PandocUploader",
    # Analyzer (may be None if imports fail)
    "DocumentAnalyzer",
    "PatternMatcher",
    "PatternMatch",
    "DocumentTemplate",
    "load_template",
    "list_available_templates",
]
