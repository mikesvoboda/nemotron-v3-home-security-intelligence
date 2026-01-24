"""Configuration and patterns for documentation validation.

This module defines:
- Citation patterns for different documentation formats
- File extension mappings for AST parsing
- Validation settings and thresholds
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from re import Pattern


class ValidationLevel(Enum):
    """Validation levels for citations."""

    FILE_EXISTS = auto()  # Level 1: File exists
    LINE_BOUNDS = auto()  # Level 1: Line numbers valid
    AST_VERIFY = auto()  # Level 2: AST symbol verification
    CODE_MATCH = auto()  # Level 3: Code block content matching
    CROSS_REF = auto()  # Level 4: Cross-document consistency
    STALENESS = auto()  # Level 5: Git staleness detection


class CitationStatus(Enum):
    """Status of a validated citation."""

    VALID = "valid"
    ERROR = "error"
    WARNING = "warning"
    STALE = "stale"


@dataclass
class Citation:
    """A parsed citation from documentation.

    Attributes:
        file_path: Path to the cited file (relative to project root)
        start_line: Starting line number (1-indexed)
        end_line: Optional ending line number for ranges
        symbol_name: Optional function/class name from surrounding context
        doc_file: Source documentation file containing this citation
        doc_line: Line number in documentation where citation appears
        raw_text: Original citation text as it appears in documentation
    """

    file_path: str
    start_line: int
    end_line: int | None = None
    symbol_name: str | None = None
    doc_file: str = ""
    doc_line: int = 0
    raw_text: str = ""

    @property
    def is_range(self) -> bool:
        """Return True if this citation specifies a line range."""
        return self.end_line is not None

    @property
    def line_count(self) -> int:
        """Return the number of lines in this citation."""
        if self.end_line:
            return self.end_line - self.start_line + 1
        return 1

    def __str__(self) -> str:
        """Return human-readable string representation."""
        if self.end_line:
            return f"{self.file_path}:{self.start_line}-{self.end_line}"
        return f"{self.file_path}:{self.start_line}"


@dataclass
class ValidationResult:
    """Result of validating a citation.

    Attributes:
        citation: The citation that was validated
        status: Overall status (valid, error, warning, stale)
        level: Highest validation level that passed
        message: Human-readable description of the result
        details: Additional details about the validation
    """

    citation: Citation
    status: CitationStatus
    level: ValidationLevel
    message: str
    details: dict[str, str | int | float | bool | list[str] | None] = field(default_factory=dict)


@dataclass
class DocumentReport:
    """Validation report for a single document.

    Attributes:
        doc_path: Path to the documentation file
        citations: List of all citations found
        results: List of validation results
    """

    doc_path: str
    citations: list[Citation] = field(default_factory=list)
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        """Count of valid citations."""
        return sum(1 for r in self.results if r.status == CitationStatus.VALID)

    @property
    def error_count(self) -> int:
        """Count of error citations."""
        return sum(1 for r in self.results if r.status == CitationStatus.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning citations."""
        return sum(1 for r in self.results if r.status == CitationStatus.WARNING)

    @property
    def stale_count(self) -> int:
        """Count of stale citations."""
        return sum(1 for r in self.results if r.status == CitationStatus.STALE)


# ============================================================================
# Citation Patterns
# ============================================================================

# Standard inline citation: `backend/services/file_watcher.py:67`
# or range: `backend/services/file_watcher.py:67-89`
INLINE_CITATION_PATTERN: Pattern[str] = re.compile(
    r"`([a-zA-Z0-9_/.-]+\.[a-zA-Z]+):(\d+)(?:-(\d+))?`"
)

# YAML frontmatter source_refs pattern:
# - backend/services/file_watcher.py:FileWatcher:34
# - backend/services/file_watcher.py:is_image_file
FRONTMATTER_CITATION_PATTERN: Pattern[str] = re.compile(
    r"^\s*-\s+([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)(?::([a-zA-Z_][a-zA-Z0-9_]*(?::[a-zA-Z_][a-zA-Z0-9_]*)?))?(?::(\d+))?$",
    re.MULTILINE,
)

# Source comment in code blocks: # Source: path:lines
CODE_BLOCK_SOURCE_PATTERN: Pattern[str] = re.compile(
    r"#\s*[Ss]ource:\s*([a-zA-Z0-9_/.-]+\.[a-zA-Z]+):(\d+)(?:-(\d+))?"
)

# Mermaid diagram reference pattern (in notes/comments)
MERMAID_REFERENCE_PATTERN: Pattern[str] = re.compile(
    r"(?:Note|note).*?`([a-zA-Z0-9_/.-]+\.[a-zA-Z]+):(\d+)(?:-(\d+))?`"
)

# Pattern to extract function/class name from text near citation
SYMBOL_CONTEXT_PATTERN: Pattern[str] = re.compile(
    r"(?:function|class|method|def|const|var|let)\s+[`\"]?([a-zA-Z_][a-zA-Z0-9_]*)[`\"]?"
)


# ============================================================================
# File Extension Mappings
# ============================================================================

# Map file extensions to tree-sitter language names
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

# Extensions that support AST verification
AST_SUPPORTED_EXTENSIONS: set[str] = {".py", ".ts", ".tsx", ".js", ".jsx"}


# ============================================================================
# Validation Settings
# ============================================================================


@dataclass
class ValidationConfig:
    """Configuration for documentation validation.

    Attributes:
        project_root: Root directory of the project
        enable_ast: Whether to enable AST verification (Level 2)
        enable_code_match: Whether to enable code block matching (Level 3)
        enable_cross_ref: Whether to enable cross-reference checking (Level 4)
        enable_staleness: Whether to enable staleness detection (Level 5)
        fuzzy_match_threshold: Threshold for fuzzy code matching (0.0-1.0)
        staleness_days: Number of days before a citation is considered stale
    """

    project_root: Path
    enable_ast: bool = True
    enable_code_match: bool = True
    enable_cross_ref: bool = True
    enable_staleness: bool = True
    fuzzy_match_threshold: float = 0.85
    staleness_days: int = 0  # 0 means any modification after doc update is flagged

    @classmethod
    def from_project_root(cls, project_root: str | Path) -> ValidationConfig:
        """Create config from project root path."""
        return cls(project_root=Path(project_root).resolve())


def get_language_for_file(file_path: str | Path) -> str | None:
    """Get the tree-sitter language name for a file.

    Args:
        file_path: Path to the source file

    Returns:
        Language name (e.g., "python", "typescript") or None if unsupported
    """
    suffix = Path(file_path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(suffix)


def supports_ast_verification(file_path: str | Path) -> bool:
    """Check if a file supports AST verification.

    Args:
        file_path: Path to the source file

    Returns:
        True if AST verification is supported for this file type
    """
    suffix = Path(file_path).suffix.lower()
    return suffix in AST_SUPPORTED_EXTENSIONS
