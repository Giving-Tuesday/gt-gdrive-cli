---
name: gdrive-analyze
description: Run template-driven analysis over local documents (After Action Reviews, etc.) with the gdrive analyze CLI. Use when the user asks to analyze, extract themes from, categorize challenges/successes/lessons in, or summarize a batch of local markdown or docx files using a named template such as "aar".
---

# gdrive-analyze — Template-driven document analysis

Wraps `gdrive analyze` (alias: `gdrive-analyze`) from the [gdrive-unified](https://github.com/Giving-Tuesday/gt-gdrive-cli) package. Use this skill when the user wants to run a structured, pattern-matching analysis over a directory of already-local documents — typically a batch of AARs, interview notes, or reports. For downloading the documents in the first place, use the `gdrive` skill.

## When this skill triggers

- "Analyze these AARs / after action reviews"
- "Extract lessons learned / challenges / successes from this folder"
- "Summarize these documents using the AAR template"
- "Run a template analysis over these markdown files"

If the user just wants a free-form summary of a single document, this skill is overkill — use a plain read + summary instead.

## Prerequisites

```bash
# Install with the analyzer extra
uv tool install 'gdrive-unified[analyzer]' \
  --from git+https://github.com/Giving-Tuesday/gt-gdrive-cli.git

# Or install with [all] to also get conversion + GUI
uv tool install 'gdrive-unified[all]' \
  --from git+https://github.com/Giving-Tuesday/gt-gdrive-cli.git
```

The `[analyzer]` extra pulls in `pandas`, which is needed for CSV/JSON output. Confirm with `gdrive analyze --list-templates` — it should print at least `aar`.

## Quick start

```bash
# Analyze a directory of markdown files with the AAR template
gdrive analyze ./markdown/ --template aar -o aar_report.md

# Analyze specific files
gdrive analyze doc1.md doc2.md doc3.md --template aar

# JSON output for downstream tooling
gdrive analyze ./markdown/ --template aar --format json -o results.json

# CSV for spreadsheet handoff
gdrive analyze ./markdown/ --template aar --format csv -o results.csv

# List installed templates
gdrive analyze --list-templates
```

Flags: positional `DOCUMENTS` (one or more files or directories), `-t/--template` (default `aar`), `-o/--output`, `-f/--format` (`markdown`/`json`/`csv`), `-v/--verbose`, `--list-templates`.

## Built-in templates

### `aar` — After Action Review

Pattern-matches AAR-style documents and extracts four categories:

| Section | Looks for headers like | Categorizes into |
|---|---|---|
| `challenges` | "challenges", "problems", "issues", "what didn't work", "obstacles", "barriers", "pain points" | resource_constraints, data_collection, communication, partnership, timing_scope, technical, process |
| `successes` | "successes", "wins", "what went well", "achievements", "highlights", "what worked" | leadership, team_dynamics, execution, stakeholder_engagement, innovation, resource_utilization, process_efficiency |
| `lessons` | "lessons learned", "key learnings", "takeaways", "insights" | internal_learning, external_partnerships, process_improvement, tool_adoption |
| `recommendations` | "recommendations", "next steps", "action items" | operational_improvements, strategic_direction, team_development, technical_enhancement |

Output (markdown format) gives per-document extracts grouped by section, plus aggregated theme counts across the whole batch. Use JSON when you want to feed results into another tool; use CSV when the user wants to open it in a spreadsheet.

The canonical template source is `src/gdrive_unified/templates/aar.py` in the repo — read it when a user asks "what exactly does the AAR template look for?".

## Writing a custom template

When the user's document type doesn't fit AAR, subclass `DocumentTemplate`:

```python
# src/gdrive_unified/templates/interview.py
from .base_template import DocumentTemplate

class InterviewTemplate(DocumentTemplate):
    @property
    def name(self) -> str:
        return "interview"

    @property
    def section_headers(self):
        return {
            "background": ["background", "context", "about"],
            "findings":   ["findings", "observations", "quotes"],
            "themes":     ["themes", "patterns"],
        }

    @property
    def analysis_patterns(self):
        return {
            "findings": {
                "direct_quote": r'"[^"]{20,}"',
                "numeric_claim": r"\b\d+\s*(?:percent|%)\b",
            },
        }

    @property
    def report_sections(self):
        return ["background", "findings", "themes"]
```

Register it in `src/gdrive_unified/templates/__init__.py` so `load_template("interview")` can find it, then `gdrive analyze ./docs/ --template interview`. Use `aar.py` as the worked example.

## Typical pipeline

```bash
# 1. Download with the gdrive skill
gdrive search -p "AAR*" --since 6m --convert
# ...produces search_AAR*/markdown/*.md

# 2. Analyze with this skill
gdrive analyze search_AAR*/markdown/ --template aar -o aar_summary.md
```

The analyzer operates on **local** files — it does not reach into Drive. Always make sure files are downloaded and (if needed) converted to markdown first.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'pandas'`** — you didn't install the `[analyzer]` extra. Reinstall with `uv tool install 'gdrive-unified[analyzer]' --from git+https://github.com/Giving-Tuesday/gt-gdrive-cli.git`.
- **`Unknown template: <name>`** — run `gdrive analyze --list-templates` to see what's registered. Custom templates must be registered in `templates/__init__.py`.
- **Empty results** — the template's `section_headers` didn't match any headings in the input. Either the input documents don't use the expected headings, or they're in a format (PDF/DOCX) that wasn't converted to markdown first. Run `gdrive search ... --convert` or `gdrive download ... --convert` to get markdown.
- **Want a quick sanity check?** Run with `--format json` and inspect `matches` and `sections` to see what the template actually extracted per document.
