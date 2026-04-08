---
name: gdrive
description: Search, download, upload, and manage Google Drive files with the gdrive CLI. Use when the user wants to download files or folders from Drive, search across Drive, create shortcuts, convert Google Docs to markdown, upload markdown as native Google Docs, or write to a specific Google Doc tab.
---

# gdrive — Google Drive CLI

Wraps the `gdrive` CLI from the [gdrive-unified](https://github.com/Giving-Tuesday/gt-gdrive-cli) package. Use this skill for any Drive I/O: search, download, upload, doc-tab writes, and environment/status checks. For template-driven document analysis of already-downloaded files, use the `gdrive-analyze` skill instead.

## Prerequisites

The `gdrive` CLI must be on `PATH`. Check with `which gdrive`. If missing, install via `uv`:

```bash
# Core + markdown conversion (required for upload / write-tab / --convert)
uv tool install 'gdrive-unified[conversion]' \
  --from git+https://github.com/Giving-Tuesday/gt-gdrive-cli.git

# Or, for everything (adds analyzer + GUI):
uv tool install 'gdrive-unified[all]' \
  --from git+https://github.com/Giving-Tuesday/gt-gdrive-cli.git
```

The `[conversion]` extra is **required** for `gdrive upload`, `gdrive write-tab`, and any `--convert` flag (it pulls in `mammoth`, `markdownify`, `markdown-it-py`, `pypandoc`). `pypandoc` also needs the `pandoc` binary on `PATH` (`brew install pandoc` on macOS) for the Pandoc upload method.

## First-run authentication

Run `gdrive init` once. This handles the OAuth flow end-to-end using the credentials it finds (or falls back to bundled credentials).

```bash
gdrive init         # interactive OAuth setup
gdrive status       # show credential + token state
```

`gdrive` auto-discovers the credentials file in this order. At each location it tries the namespaced name first, then falls back to the generic legacy name:

1. `$GDRIVE_CREDENTIALS_PATH` (env var — file or directory)
2. Current working directory
3. Platform config dir (`~/Library/Application Support/gdrive-unified/` on macOS, `~/.config/gdrive-unified/` on Linux, `%APPDATA%\gdrive-unified\` on Windows)
4. `~/.google/` — preferred: `gdrive-unified-credentials.json`; legacy fallback: `credentials.json`
5. Bundled fallback credentials shipped with the package

Tokens are saved next to the credentials file (or in the platform config dir for bundled creds), under `gdrive-unified-token.pickle` or the legacy `token.pickle` name if one already exists there. When a refresh fails because the saved token has been revoked or aged out, `gdrive` prints the offending path, deletes it, and re-runs the OAuth flow automatically — the user doesn't need to intervene manually unless `gdrive init` itself fails.

**See [`docs/CREDENTIALS.md`](../../docs/CREDENTIALS.md) in the repo** for the full story: shared-client vs. roll-your-own, Google Cloud Console walkthrough, scope notes, and the common troubleshooting cases.

## Command reference

Every command is available under both the unified `gdrive <sub>` form and its standalone alias (`gdrive-<sub>`). Prefer the unified form when writing examples.

### `gdrive search` — find files by pattern

```bash
gdrive search -p "Report*"                      # wildcard
gdrive search -p "*2024*" --since 7d            # last 7 days
gdrive search -p "^Q[1-4] Report$"              # regex (prefix with ^)
gdrive search -p "Budget*" -s personal          # personal drive only
gdrive search -p "Budget*" -s shared            # shared drives only
gdrive search -p "Q4*" -t spreadsheet           # file type filter
gdrive search -p "Slides*" -t presentation
gdrive search -p "AAR*" --no-download           # preview without downloading
gdrive search -p "Project*" --create-shortcuts <FOLDER_ID>  # collect shortcuts
gdrive search -p "*" --max-results 500
```

Key flags: `-p/--pattern` (wildcard or `^regex`), `-s/--scope` (`personal`/`shared`/`all`), `-t/--file-types` (`document`/`spreadsheet`/`presentation`), `--since` (e.g. `7d`, `2w`, `1m`, `2024-01-01`), `--download/--no-download`, `--convert/--no-convert`, `--create-shortcuts FOLDER_ID`, `--max-results`.

Output lands in `search_<pattern>/` with `documents/`, `markdown/`, `search_results.csv`, `file_relationships.csv`.

### `gdrive download` — grab a folder or file

```bash
gdrive download -u "https://drive.google.com/drive/folders/FOLDER_ID"
gdrive download -f "https://docs.google.com/document/d/FILE_ID/edit"
gdrive download --file-id FILE_ID
gdrive download -u "URL" -o ./out --no-convert
```

Flags: `-u/--folder-url`, `-f/--file-url`, `--file-id`, `-o/--output-dir`, `--documents-subdir`, `--markdown-subdir`, `--convert/--no-convert`, `--track-relationships/--no-track`. Shortcuts in the folder are followed automatically with cycle protection.

### `gdrive upload` — markdown → native Google Docs

```bash
gdrive upload -f report.md --folder-id <FOLDER_ID>
gdrive upload -f doc1.md -f doc2.md --folder-id <FOLDER_ID>
gdrive upload -d ./markdown/ --folder-id <FOLDER_ID>          # whole directory
gdrive upload -d ./markdown/ --folder-id <FOLDER_ID> -p "*.md"
gdrive upload -f report.md --folder-id root                   # root of My Drive
gdrive upload -f doc.md --folder-url "<FOLDER_URL>"
gdrive upload -f doc.md --folder-id <ID> --no-preview         # skip confirmation
gdrive upload -f doc.md --folder-id <ID> --replace-existing   # overwrite
gdrive upload -f doc.md --folder-id <ID> --method pandoc      # preserve footnotes
```

**Two upload methods** — pick intentionally:

- `--method html` (default): fast, renders markdown → HTML → imported as Google Doc. Preserves headings, bold, italic, lists, links, code blocks. **Does not preserve footnotes.**
- `--method pandoc`: converts markdown → DOCX via Pandoc → imports. Slower; requires the `pandoc` binary. **Preserves footnotes** as native Google Docs footnotes. Use this for AARs, academic writing, anything with `[^1]`-style references.

By default, an existing doc with the same name in the target folder is skipped — pass `--replace-existing` to overwrite.

### `gdrive write-tab` — append/replace content in a Doc tab

```bash
gdrive write-tab -f notes.md --doc-id <DOC_ID>
gdrive write-tab -f notes.md --doc-url "https://docs.google.com/document/d/<DOC_ID>/edit?tab=t.<TAB_ID>"
gdrive write-tab -f notes.md --doc-id <DOC_ID> --replace   # replace tab content
gdrive write-tab -f notes.md --doc-id <DOC_ID> --force     # no confirmation
```

Append (default) adds to the end of the existing tab; `--replace` wipes and replaces. A 300-char preview of existing content is shown before writing. Tab ID is auto-extracted from `?tab=t.xxx` in the URL, or pass `--tab-id` explicitly. Requires the Google Docs API to be enabled in your Google Cloud project.

### `gdrive manage` — config and status utilities

```bash
gdrive manage status        # show credential + download/conversion state
gdrive manage init-config   # write a default gdrive.yaml
gdrive manage cleanup       # clear orphaned tokens/cache
gdrive manage version
```

`gdrive manage status` uses the `FileRelationshipTracker` under the hood — it walks the `documents/` and `markdown/` folders and prints a mapping of Drive URLs ↔ local files ↔ converted markdown. Use this when the user asks "what have I already downloaded?" or "did this URL get converted?".

### `gdrive-gui` — desktop app

Optional PyQt5 desktop app, installed only with the `[gui]` or `[all]` extra. Launch with `gdrive-gui`. Four tabs: Search, Download, Manage, Settings. Mention it to the user if they prefer a visual workflow; otherwise stay in the CLI.

## Common workflows

### 1. Search → download → convert

```bash
gdrive search -p "AAR*" --since 1m                # preview matches first
gdrive search -p "AAR*" --since 1m --convert       # then download + convert
```

Skim `search_AAR*/search_results.csv` to confirm the pattern caught the right files before doing the full download.

### 2. Pipeline into analysis

```bash
gdrive search -p "AAR*" --since 3m --convert
gdrive analyze search_AAR*/markdown/ --template aar --format markdown -o aar_report.md
```

The second step is covered by the `gdrive-analyze` skill.

### 3. Upload a doc with footnotes

```bash
gdrive upload -f article.md --folder-id <ID> --method pandoc
```

Always use `--method pandoc` when footnotes matter. The HTML method will silently drop them.

### 4. Write generated notes into an existing Doc tab

```bash
gdrive write-tab -f meeting-notes.md \
  --doc-url "https://docs.google.com/document/d/<DOC_ID>/edit?tab=t.<TAB_ID>"
```

Default is append, so running this repeatedly keeps adding sections. Use `--replace` only when the tab is a scratch buffer you own.

## Troubleshooting

- **`AttributeError: 'GlobalConfig' object has no attribute 'downloader'`** — you're on an old pre-unification version. Reinstall: `uv tool install --reinstall 'gdrive-unified[conversion]' --from git+https://github.com/Giving-Tuesday/gt-gdrive-cli.git`.
- **`Could not find credentials.json`** — run `gdrive init`, or place the file in one of the five auto-discovered locations listed above, or set `GDRIVE_CREDENTIALS_PATH`.
- **`ModuleNotFoundError: No module named 'mammoth'` / `markdown_it` / `pypandoc`** — install with the `[conversion]` extra (see Prerequisites). These aren't in the core install.
- **Pandoc upload fails with "No pandoc was found"** — `brew install pandoc` (macOS) or `apt-get install pandoc` (Debian/Ubuntu). `pypandoc` wraps the system binary; it doesn't ship one.
- **`Token has been expired or revoked`** — delete `token.pickle` from the location `gdrive status` prints, then re-run any command.
- **OAuth "unverified app" warning on a personal Gmail** — expected when using your own Google Cloud project with an External consent screen. Add your account as a Test User in the OAuth consent screen settings, then click through the warning.

## Programmatic API (quick reference)

When shelling out isn't the right fit, the Python API is available after `pip install gdrive-unified[conversion]`:

```python
from gdrive_unified.config import GlobalConfig
from gdrive_unified.drive import (
    GoogleDriveSearcher, GoogleDriveDownloader, GoogleDriveUploader,
)

config = GlobalConfig()
searcher = GoogleDriveSearcher(config.drive.credentials_file)   # or pass creds explicitly
results = searcher.search_files(pattern="AAR*", drive_scope="all", max_results=50)
```

Full class surface in `src/gdrive_unified/drive/` in the repo. Keep skill use focused on the CLI unless the user explicitly asks for Python.
