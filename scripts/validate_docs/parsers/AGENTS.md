# Parsers Package

## Purpose

The `parsers/` package extracts code citations from various documentation formats. Each parser handles a specific format and returns a list of `Citation` objects.

## Files

### `__init__.py`

Package exports:

- `extract_code_block_citations` - Extract from fenced code blocks
- `extract_markdown_citations` - Extract from markdown prose and frontmatter
- `extract_mermaid_citations` - Extract from mermaid diagrams
- `parse_document` - Parse document and extract all citations

### `markdown.py`

**Purpose:** Extract citations from markdown prose and YAML frontmatter.

**Functions:**

| Function                         | Description                                 |
| -------------------------------- | ------------------------------------------- |
| `extract_markdown_citations()`   | Main entry: extracts all markdown citations |
| `parse_document()`               | Parse file and return (content, citations)  |
| `_extract_frontmatter()`         | Split YAML frontmatter from body            |
| `_parse_frontmatter_citations()` | Parse source_refs from frontmatter          |
| `_extract_symbol_from_context()` | Extract symbol name from text near citation |

**Supported Formats:**

```markdown
<!-- Inline citation -->

The `backend/services/file_watcher.py:67` function...

<!-- Range citation -->

Lines `backend/services/file_watcher.py:67-89` implement...

## <!-- YAML frontmatter -->

source_refs:

- backend/services/file_watcher.py:FileWatcher:34
- backend/services/file_watcher.py:is_image_file
- backend/services/file_watcher.py:67

---
```

### `code_blocks.py`

**Purpose:** Extract citations from fenced code blocks with `# Source:` comments.

**Functions:**

| Function                         | Description                                     |
| -------------------------------- | ----------------------------------------------- |
| `extract_code_block_citations()` | Extract citations from code blocks              |
| `extract_code_block_content()`   | Extract code content for Level 3 validation     |
| `_find_code_blocks()`            | Find all fenced code blocks (excluding mermaid) |

**Supported Format:**

````markdown
```python
# Source: backend/services/file_watcher.py:67-89
def is_image_file(file_path: str) -> bool:
    ...
```
````

The `# Source:` comment links the documented code to its location in the codebase. The code after the comment is used for Level 3 code matching validation.

### `mermaid.py`

**Purpose:** Extract citations from mermaid diagram blocks.

**Functions:**

| Function                      | Description                           |
| ----------------------------- | ------------------------------------- |
| `extract_mermaid_citations()` | Extract citations from mermaid blocks |
| `_find_mermaid_blocks()`      | Find all ```mermaid blocks            |

**Supported Formats:**

````markdown
```mermaid
sequenceDiagram
    %% See `backend/services/batch_aggregator.py:112`
    Note right of RT: ~30-50ms `backend/services/detector_client.py:45`
    [Detection `backend/models/detection.py:1-50`]
```
````

````

Citations can appear in:
- Note annotations
- Comments (`%%`)
- Node labels

## Citation Data Structure

Each parser returns `Citation` objects with:

```python
@dataclass
class Citation:
    file_path: str      # Path to cited file (relative to project root)
    start_line: int     # Starting line number (1-indexed)
    end_line: int | None  # Optional ending line for ranges
    symbol_name: str | None  # Function/class name from context
    doc_file: str       # Source documentation file
    doc_line: int       # Line in documentation where citation appears
    raw_text: str       # Original citation text
````

## Deduplication

The CLI (`cli.py`) deduplicates citations by `(file_path, start_line, end_line)` after collecting from all parsers.

## Related Documentation

- `/scripts/validate_docs/AGENTS.md` - Main tool overview
- `/scripts/validate_docs/config.py` - Citation patterns and data classes
