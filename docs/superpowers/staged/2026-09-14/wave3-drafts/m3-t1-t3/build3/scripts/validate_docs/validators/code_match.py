"""Level 3 Validator: Code block content matching.

This module validates that code blocks in documentation match
the actual source file content, allowing for fuzzy matching
to handle whitespace differences and minor changes.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from ..config import Citation, CitationStatus, ValidationLevel, ValidationResult


def _normalize_code(code: str) -> str:
    """Normalize code for comparison.

    - Strips leading/trailing whitespace from each line
    - Removes empty lines
    - Normalizes line endings

    Args:
        code: Code string to normalize

    Returns:
        Normalized code string
    """
    lines = code.replace("\r\n", "\n").split("\n")
    # Strip each line and filter out empty lines
    normalized_lines = [line.strip() for line in lines if line.strip()]
    return "\n".join(normalized_lines)


def _calculate_similarity(code1: str, code2: str) -> float:
    """Calculate similarity ratio between two code strings.

    Args:
        code1: First code string
        code2: Second code string

    Returns:
        Similarity ratio between 0.0 and 1.0
    """
    norm1 = _normalize_code(code1)
    norm2 = _normalize_code(code2)

    if not norm1 and not norm2:
        return 1.0
    if not norm1 or not norm2:
        return 0.0

    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def _extract_source_lines(
    file_path: Path,
    start_line: int,
    end_line: int | None,
) -> str | None:
    """Extract lines from a source file.

    Args:
        file_path: Path to the source file
        start_line: Starting line number (1-indexed)
        end_line: Optional ending line number (1-indexed, inclusive)

    Returns:
        Extracted code string or None if extraction fails
    """
    try:
        # Resolve path (semgrep: path-traversal-open)
        resolved_path = Path(file_path).resolve()
        with resolved_path.open(encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Convert to 0-indexed
        start_idx = start_line - 1
        end_idx = (end_line if end_line else start_line) - 1

        if start_idx < 0 or end_idx >= len(lines):
            return None

        return "".join(lines[start_idx : end_idx + 1])
    except OSError:
        return None


def validate_code_match(
    citation: Citation,
    project_root: Path,
    documented_code: str | None = None,
    threshold: float = 0.85,
) -> ValidationResult:
    """Validate that documented code matches the actual source.

    This is Level 3 validation. Compares code blocks in documentation
    against the actual source file content.

    Args:
        citation: The citation to validate
        project_root: Root directory of the project
        documented_code: Code content from documentation (if available)
        threshold: Similarity threshold (0.0-1.0) for fuzzy matching

    Returns:
        ValidationResult with CODE_MATCH level
    """
    file_path = project_root / citation.file_path

    # File must exist
    if not file_path.exists():
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.CODE_MATCH,
            message="Cannot match code: file does not exist",
            details={"file_path": citation.file_path},
        )

    # If no documented code provided, we can't do code matching
    if not documented_code:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.VALID,
            level=ValidationLevel.CODE_MATCH,
            message="Code match skipped: no documented code to compare",
            details={"reason": "no_documented_code"},
        )

    # Extract source lines
    source_code = _extract_source_lines(
        file_path,
        citation.start_line,
        citation.end_line,
    )

    if source_code is None:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.CODE_MATCH,
            message=f"Cannot extract source lines {citation.start_line}-{citation.end_line or citation.start_line}",
            details={
                "start_line": citation.start_line,
                "end_line": citation.end_line,
            },
        )

    # Calculate similarity
    similarity = _calculate_similarity(documented_code, source_code)

    if similarity >= threshold:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.VALID,
            level=ValidationLevel.CODE_MATCH,
            message=f"Code matches ({similarity:.0%} similarity)",
            details={
                "similarity": round(similarity, 3),
                "threshold": threshold,
            },
        )
    elif similarity >= 0.5:
        # Partial match - warn
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.CODE_MATCH,
            message=f"Code partially matches ({similarity:.0%} similarity, threshold {threshold:.0%})",
            details={
                "similarity": round(similarity, 3),
                "threshold": threshold,
                "documented_preview": documented_code[:100] + "..."
                if len(documented_code) > 100
                else documented_code,
                "source_preview": source_code[:100] + "..."
                if len(source_code) > 100
                else source_code,
            },
        )
    else:
        # Low match - error
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.CODE_MATCH,
            message=f"Code does not match ({similarity:.0%} similarity)",
            details={
                "similarity": round(similarity, 3),
                "threshold": threshold,
                "documented_preview": documented_code[:100] + "..."
                if len(documented_code) > 100
                else documented_code,
                "source_preview": source_code[:100] + "..."
                if len(source_code) > 100
                else source_code,
            },
        )
