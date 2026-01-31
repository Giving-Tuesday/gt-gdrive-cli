# gdrive-unified

Unified toolkit for Google Drive operations and document analysis.

## Features

- **Download**: Download files and folders from Google Drive with automatic conversion
- **Search**: Search across personal and shared drives with pattern matching
- **Upload**: Upload markdown files as native Google Docs
- **Analyze**: Analyze documents using configurable templates
- **GUI**: Optional desktop application for visual operations

## Installation

### Basic Installation

```bash
pip install gdrive-unified
```

### With Optional Features

```bash
# Document conversion (DOCX → Markdown)
pip install gdrive-unified[conversion]

# Document analysis
pip install gdrive-unified[analyzer]

# Desktop GUI
pip install gdrive-unified[gui]

# Everything
pip install gdrive-unified[all]

# Development
pip install gdrive-unified[full]
```

### Using uv (Recommended)

```bash
uvx install gdrive-unified[all]
```

## Quick Start

### 1. Setup Credentials

```bash
# Interactive setup
gdrive init

# Or check status
gdrive status
```

### 2. Search for Documents

```bash
# Search all drives
gdrive search -p "Project Report*"

# Search and download
gdrive search -p "AAR*" --download

# Create shortcuts to found files
gdrive search -p "Budget*" --create-shortcuts FOLDER_ID
```

### 3. Download Files

```bash
# Download single file
gdrive download -f "https://docs.google.com/document/d/DOC_ID/edit"

# Download folder
gdrive download -u "https://drive.google.com/drive/folders/FOLDER_ID"
```

### 4. Upload Files

```bash
# Upload markdown as Google Doc
gdrive upload -f report.md --folder-id FOLDER_ID
```

### 5. Analyze Documents

```bash
# Analyze documents with default template
gdrive analyze document.md

# Multiple documents with JSON output
gdrive analyze *.md -f json -o analysis.json
```

## CLI Commands

### Separate Commands (Backwards Compatible)

| Command | Description |
|---------|-------------|
| `gdrive-download` | Download files/folders from Google Drive |
| `gdrive-search` | Search and create shortcuts |
| `gdrive-upload` | Upload markdown as Google Docs |
| `gdrive-write-tab` | Update existing doc tabs |
| `gdrive-manage` | Config and status |
| `gdrive-analyze` | Document analysis |
| `gdrive-gui` | Desktop application (requires `[gui]`) |

### Unified Entry Point

| Command | Description |
|---------|-------------|
| `gdrive download` | Download files/folders |
| `gdrive search` | Search for files |
| `gdrive upload` | Upload files |
| `gdrive write-tab` | Write to doc tab |
| `gdrive manage` | Configuration |
| `gdrive analyze` | Document analysis |
| `gdrive init` | Setup credentials |
| `gdrive status` | Show status |

## Python API

```python
from gdrive_unified import (
    get_credentials,
    GoogleDriveDownloader,
    GoogleDriveSearcher,
    DocumentAnalyzer,
)
from gdrive_unified.config import DriveConfig

# Get credentials
creds = get_credentials()

# Search for files
searcher = GoogleDriveSearcher(creds)
results = searcher.search_files("AAR*")

# Download files
config = DriveConfig(output_dir=Path("./downloads"))
downloader = GoogleDriveDownloader(config)
downloaded = downloader.download_search_results(results)

# Analyze documents
analyzer = DocumentAnalyzer("aar")
for doc in Path("./downloads/markdown").glob("*.md"):
    result = analyzer.analyze_document(doc.read_text())
    print(f"{doc.name}: {len(result['matches'])} patterns found")
```

## Credentials

### Storage Locations

| Platform | Location |
|----------|----------|
| Linux | `~/.config/gdrive-unified/` |
| macOS | `~/Library/Application Support/gdrive-unified/` |
| Windows | `%APPDATA%/gdrive-unified/` |

### Search Order

1. `GDRIVE_CREDENTIALS_PATH` environment variable
2. Current working directory (`./credentials.json`)
3. Platform config directory

### Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 Client ID (Desktop application)
3. Download `credentials.json`
4. Run `gdrive init`

## Document Analysis

### Available Templates

```bash
gdrive analyze --list-templates
```

Currently available:
- `aar` - After Action Review documents

### Template Patterns

Templates define:
- **Section Headers**: Patterns for identifying document sections
- **Analysis Patterns**: Regex patterns for extracting information
- **Report Configuration**: Output formatting options

### Creating Custom Templates

```python
from gdrive_unified.templates import DocumentTemplate

class MyTemplate(DocumentTemplate):
    @property
    def name(self) -> str:
        return "my_template"

    @property
    def description(self) -> str:
        return "Custom analysis template"

    @property
    def section_headers(self):
        return {"summary": ["summary", "overview"]}

    @property
    def analysis_patterns(self):
        return {
            "metrics": {"percentage": r"\d+%"},
        }
```

## Configuration

### Config File

Create `gdrive.yaml` in your project or config directory:

```yaml
drive:
  output_dir: documents
  batch_size: 10

analyzer:
  template: aar
  output_format: markdown

log_level: INFO
```

### Environment Variables

- `GDRIVE_CREDENTIALS_PATH`: Override credentials location
- `XDG_CONFIG_HOME`: Linux config base (default: `~/.config`)

## Migration from Old Packages

### From gdrive-download

```python
# Old
from gdrive_download import GoogleDriveDownloader
from gdrive_download.config import DownloaderConfig

# New
from gdrive_unified.drive import GoogleDriveDownloader
from gdrive_unified.config import DriveConfig
```

### From document-analyzer

```python
# Old
from document_analyzer import DocumentAnalyzer

# New
from gdrive_unified.analyzer import DocumentAnalyzer
```

## Development

### Setup

```bash
git clone https://github.com/givingtuesday/gdrive-unified
cd gdrive-unified
uv pip install -e ".[full]"
```

### Testing

```bash
pytest tests/
```

### Code Quality

```bash
black src/
isort src/
mypy src/
```

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Run tests
5. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/givingtuesday/gdrive-unified/issues)
- **Documentation**: See `/docs` directory
