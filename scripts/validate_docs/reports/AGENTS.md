# Reports Package

## Purpose

This package provides different output formats for validation results. Supports both human-readable console output and machine-readable JSON for CI integration.

## Files

### `__init__.py`

Package exports:

- `ConsoleReporter` - Rich terminal output with colors
- `JSONReporter` - JSON output for CI integration

### `console.py`

**Purpose:** Generate colorful terminal output using the `rich` library.

**Class: `ConsoleReporter`**

| Method                 | Description                                               |
| ---------------------- | --------------------------------------------------------- |
| `__init__()`           | Initialize with output stream, errors_only, verbose flags |
| `report_document()`    | Print validation report for a single document             |
| `report_summary()`     | Print summary of all validation results                   |
| `print_no_citations()` | Print message when no citations found                     |

**Features:**

- Color-coded status indicators (OK=green, ERR=red, WARN/STALE=yellow)
- Falls back to plain text if `rich` is not installed
- Supports `--errors-only` flag to hide valid citations
- Supports `--verbose` flag for additional details

**Sample Output:**

```
Validating ai-pipeline.md...
  OK backend/services/file_watcher.py:67 (1 line)
  ERR backend/services/missing.py:42 (1 line)
  WARN backend/services/moved.py:100 (1 line)

------------------------------------------------------------
SUMMARY: 42 citations checked

  OK     38
  ERR    2 (must fix)
  WARN   1
  STALE  1 (docs need update)
```

### `json_report.py`

**Purpose:** Generate structured JSON output for CI/CD pipelines and automated processing.

**Class: `JSONReporter`**

| Method              | Description                                |
| ------------------- | ------------------------------------------ |
| `__init__()`        | Initialize with output stream, pretty flag |
| `generate_report()` | Generate complete JSON report dictionary   |
| `write_report()`    | Write JSON report to output stream         |
| `write_to_file()`   | Write JSON report to a file                |

**JSON Schema:**

```json
{
  "generated_at": "2025-01-24T10:30:45+00:00",
  "project_root": "/path/to/project",
  "documents": [
    {
      "doc_path": "docs/architecture/ai-pipeline.md",
      "citation_count": 15,
      "results": [
        {
          "citation": {
            "file_path": "backend/services/file_watcher.py",
            "start_line": 67,
            "end_line": null,
            "symbol_name": null,
            "doc_file": "docs/architecture/ai-pipeline.md",
            "doc_line": 42,
            "raw_text": "`backend/services/file_watcher.py:67`"
          },
          "status": "valid",
          "level": "FILE_EXISTS",
          "message": "File exists: backend/services/file_watcher.py",
          "details": { "file_size": 4523 }
        }
      ],
      "summary": {
        "valid": 12,
        "errors": 2,
        "warnings": 1,
        "stale": 0
      }
    }
  ],
  "summary": {
    "total_documents": 5,
    "total_citations": 42,
    "valid": 38,
    "errors": 2,
    "warnings": 1,
    "stale": 1
  },
  "has_errors": true
}
```

**CI Integration:**

```bash
# Generate JSON report
python -m scripts.validate_docs docs/ --format json > validation-report.json

# Use in CI to fail on errors
python -m scripts.validate_docs docs/ --format json | jq -e '.has_errors == false'
```

## Status Values

| Status    | Meaning                                 |
| --------- | --------------------------------------- |
| `valid`   | Citation passed all enabled validations |
| `error`   | Citation failed a critical validation   |
| `warning` | Citation has a potential issue          |
| `stale`   | Source modified after documentation     |

## Related Documentation

- `/scripts/validate_docs/AGENTS.md` - Main tool overview
- `/scripts/validate_docs/config.py` - Status and result data classes
