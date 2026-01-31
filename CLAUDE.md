# CLAUDE.md - Developer Guide for gdrive-unified

## Project Overview

This is a unified Python package that combines Google Drive operations (download, upload, search) with document analysis capabilities. It's built with a modular architecture supporting optional dependencies.

## Package Structure

```
src/gdrive_unified/
├── __init__.py           # Main exports with optional import handling
├── config.py             # Configuration classes (DriveConfig, AnalyzerConfig, GlobalConfig)
├── credentials.py        # Centralized credential management (XDG-compliant)
├── drive/                # Google Drive operations
│   ├── drive_downloader.py    # Download files/folders
│   ├── drive_searcher.py      # Search across drives
│   ├── drive_uploader.py      # Upload markdown as Google Docs
│   ├── file_converter.py      # DOCX → Markdown conversion
│   ├── relationship_tracker.py # Track file relationships
│   └── pandoc_uploader.py     # Pandoc-based upload
├── analyzer/             # Document analysis
│   ├── document_analyzer.py   # Main analyzer class
│   └── pattern_matcher.py     # Pattern matching utilities
├── templates/            # Analysis templates
│   ├── base_template.py       # Abstract base template
│   └── aar.py                 # After Action Review template
├── cli/                  # Command-line interface
│   ├── __init__.py           # Unified 'gdrive' entry point
│   ├── download.py           # gdrive-download command
│   ├── search.py             # gdrive-search command
│   ├── upload.py             # gdrive-upload command
│   ├── manage.py             # gdrive-manage command
│   └── analyze.py            # gdrive-analyze command
├── gui/                  # PyQt5 GUI (optional [gui] extra)
│   ├── main_window.py
│   ├── tabs/
│   ├── widgets/
│   └── workers/
└── utils/                # Utilities
    ├── logging.py
    └── file_utils.py
```

## Key Design Decisions

### 1. Single Package with Extras (Not Namespace Packages)

We use a single `gdrive_unified` package with optional extras rather than namespace packages because:
- Simpler uvx installation
- Better optional dependency handling
- Clearer import paths

### 2. Centralized Credentials

`credentials.py` handles all credential management:
- XDG-compliant storage paths
- Environment variable override (`GDRIVE_CREDENTIALS_PATH`)
- Cross-platform support (Linux, macOS, Windows)

### 3. Configuration with Pydantic

All configuration uses Pydantic models in `config.py`:
- `DriveConfig`: Download/upload settings
- `AnalyzerConfig`: Analysis settings
- `GlobalConfig`: Combined configuration

### 4. Dual CLI Interface

Both separate commands and unified entry point:
- `gdrive-download`, `gdrive-search`, etc. (backwards compatible)
- `gdrive download`, `gdrive search`, etc. (unified)

## Installation Extras

| Extra | Purpose | Key Dependencies |
|-------|---------|------------------|
| (core) | Basic Drive ops | google-api-*, click, pydantic, rich |
| `conversion` | DOCX→Markdown | mammoth, markdownify, pypandoc |
| `analyzer` | Document analysis | pandas |
| `gui` | Desktop app | PyQt5 |
| `notebooks` | Jupyter support | jupyterlab, numpy, etc. |
| `dev` | Development | pytest, black, mypy |
| `all` | conversion + analyzer + gui | |
| `full` | Everything | |

## Common Development Tasks

### Running Tests

```bash
pytest tests/ -v
```

### Testing Imports

```bash
python -c "from gdrive_unified import get_credentials; print('OK')"
python -c "from gdrive_unified.drive import GoogleDriveSearcher; print('OK')"
python -c "from gdrive_unified.analyzer import DocumentAnalyzer; print('OK')"
```

### Testing CLI

```bash
gdrive --help
gdrive status
gdrive-search --help
gdrive-analyze --list-templates
```

### Building Package

```bash
python -m build
```

## Important Files

### pyproject.toml

Uses hatchling build system. Key sections:
- `[project.scripts]` - CLI entry points
- `[project.optional-dependencies]` - Extras
- `[tool.hatch.build.targets.wheel]` - Build config

### credentials.py

Critical for credential management:
- `get_credentials()` - Main function for OAuth
- `find_credentials_file()` - Credential discovery
- `get_config_dir()` - Platform-specific paths

### cli/__init__.py

Unified CLI using Click:
- Uses `click.group()` for subcommands
- Lazy imports to handle missing dependencies
- `_add_subcommands()` dynamically adds commands

## Migration Notes

### From gdrive-download

- `DownloaderConfig` → `DriveConfig`
- `from gdrive_download.downloader` → `from gdrive_unified.drive`
- `from gdrive_download.config` → `from gdrive_unified.config`

### From document-analyzer

- `from document_analyzer.templates` → `from gdrive_unified.templates`
- `from document_analyzer.core` → `from gdrive_unified.analyzer`

## Testing Checklist

1. ✅ Unit tests pass: `pytest tests/`
2. ✅ CLI commands work: `gdrive --help`
3. ✅ Separate commands work: `gdrive-search --help`
4. ✅ Imports work without optional deps
5. ✅ Imports work with optional deps

## Related Repositories

- **gdrive-skills**: Portable Claude Code skills for gdrive operations
