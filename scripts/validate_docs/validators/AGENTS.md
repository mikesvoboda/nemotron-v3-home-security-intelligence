# Validators Package

## Purpose

This package implements the five validation levels for checking documentation citations against the actual codebase. Each validator is independent and returns a `ValidationResult`.

## Files

### `__init__.py`

Package exports:

- `validate_file_exists` - Level 1: File existence
- `validate_line_bounds` - Level 1: Line number validation
- `validate_python_ast` - Level 2: Python AST verification (optional)
- `validate_typescript_ast` - Level 2: TypeScript/JS AST verification (optional)
- `validate_code_match` - Level 3: Code block content matching
- `validate_cross_references` - Level 4: Cross-document consistency
- `validate_staleness` - Level 5: Git staleness detection

AST validators are optional and require tree-sitter packages to be installed.

### `file_exists.py`

**Level 1 Validator: File existence checks.**

**Function:** `validate_file_exists(citation, project_root) -> ValidationResult`

Validates that the cited file exists in the repository and is a file (not a directory).

**Returns:**

- `VALID` - File exists
- `ERROR` - File does not exist or path is a directory

### `line_bounds.py`

**Level 1 Validator: Line number bounds checking.**

**Function:** `validate_line_bounds(citation, project_root) -> ValidationResult`

Validates that cited line numbers are within file bounds:

1. Start line >= 1
2. End line >= start line (if specified)
3. All lines within file bounds

**Returns:**

- `VALID` - Line bounds are valid
- `ERROR` - Lines out of bounds or invalid range

### `ast_python.py`

**Level 2 Validator: Python AST verification using tree-sitter.**

**Function:** `validate_python_ast(citation, project_root) -> ValidationResult`

Validates that cited symbols (functions, classes) exist at the specified lines.

**Behavior:**

- If `symbol_name` is specified: Verifies symbol exists and citation points to it
- If no `symbol_name`: Reports symbols found at the cited line

**Returns:**

- `VALID` - Symbol found or line is valid code
- `WARNING` - tree-sitter not installed or symbol at different line
- `ERROR` - Symbol not found in file

**Dependencies:** `tree-sitter`, `tree-sitter-python` (optional)

### `ast_typescript.py`

**Level 2 Validator: TypeScript/JavaScript AST verification using tree-sitter.**

**Function:** `validate_typescript_ast(citation, project_root) -> ValidationResult`

Same as Python validator but for TypeScript/JavaScript files (.ts, .tsx, .js, .jsx, .mjs).

**Supported Node Types:**

- `function_declaration`
- `class_declaration`
- `method_definition`
- `arrow_function`
- `variable_declarator`
- `interface_declaration`
- `type_alias_declaration`

**Dependencies:** `tree-sitter`, `tree-sitter-typescript` (optional)

### `code_match.py`

**Level 3 Validator: Code block content matching.**

**Function:** `validate_code_match(citation, project_root, documented_code, threshold) -> ValidationResult`

Validates that code blocks in documentation match the actual source file content using fuzzy matching.

**Matching:**

- Normalizes code (strips whitespace, removes empty lines)
- Uses `difflib.SequenceMatcher` for similarity ratio
- Default threshold: 85% similarity

**Returns:**

- `VALID` - Similarity >= threshold
- `WARNING` - Similarity 50-85%
- `ERROR` - Similarity < 50%

### `cross_reference.py`

**Level 4 Validator: Cross-document consistency checking.**

**Class: `CrossReferenceIndex`**

Maintains an index of citations across all documents for consistency checking.

| Method                       | Description                             |
| ---------------------------- | --------------------------------------- |
| `add_citation()`             | Add single citation to index            |
| `add_citations()`            | Add multiple citations from a document  |
| `get_citations_for_file()`   | Get all citations for a specific file   |
| `get_citations_for_symbol()` | Get all citations for a specific symbol |

**Function:** `validate_cross_references(citation, index, current_doc) -> ValidationResult`

Validates that the same file/symbol is cited consistently across documents.

**Detects:**

- Same symbol cited at different lines in different docs
- Conflicting line references for the same file

**Returns:**

- `VALID` - Consistent with other documents or no cross-references
- `WARNING` - Inconsistent line numbers for same symbol

### `staleness.py`

**Level 5 Validator: Git-based staleness detection.**

**Function:** `validate_staleness(citation, project_root, staleness_days) -> ValidationResult`

Checks if documentation is stale by comparing git modification times:

- Gets last commit timestamp for source file
- Gets last commit timestamp for documentation file
- Flags as stale if source modified after documentation

**Parameters:**

- `staleness_days` - Grace period in days (0 = any modification flags)

**Returns:**

- `VALID` - Documentation is up to date
- `STALE` - Source modified after documentation
- `WARNING` - Cannot determine (file not in git)

## Validation Flow

```
Citation
    │
    ├── Level 1: validate_file_exists()
    │       │
    │       └── ERROR? → Stop
    │
    ├── Level 1: validate_line_bounds()
    │       │
    │       └── ERROR? → Stop
    │
    ├── Level 2: validate_python_ast() or validate_typescript_ast()
    │       (if file type supported and tree-sitter installed)
    │
    ├── Level 3: validate_code_match()
    │       (if documented code available)
    │
    ├── Level 4: validate_cross_references()
    │       (if cross-ref checking enabled)
    │
    └── Level 5: validate_staleness()
            (if staleness checking enabled)
```

## ValidationResult Structure

```python
@dataclass
class ValidationResult:
    citation: Citation      # The citation that was validated
    status: CitationStatus  # VALID, ERROR, WARNING, STALE
    level: ValidationLevel  # Which validation level
    message: str           # Human-readable description
    details: dict          # Additional details
```

## Related Documentation

- `/scripts/validate_docs/AGENTS.md` - Main tool overview
- `/scripts/validate_docs/config.py` - ValidationResult and ValidationLevel definitions
