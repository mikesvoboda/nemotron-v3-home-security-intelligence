"""Level 1 Validator: Line number bounds checking.

This module validates that cited line numbers are within file bounds
and that line ranges are valid (start <= end).
"""

from __future__ import annotations

from pathlib import Path

from ..config import Citation, CitationStatus, ValidationLevel, ValidationResult


def _count_lines(file_path: Path) -> int:
    """Count the number of lines in a file.

    Args:
        file_path: Path to the file

    Returns:
        Number of lines in the file
    """
    # Resolve path (semgrep: path-traversal-open)
    resolved_path = Path(file_path).resolve()
    with resolved_path.open(encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def validate_line_bounds(
    citation: Citation,
    project_root: Path,
) -> ValidationResult:
    """Validate that cited line numbers are within file bounds.

    This is Level 1 validation. Checks:
    1. Start line is >= 1
    2. End line is >= start line (if specified)
    3. All lines are within file bounds

    Args:
        citation: The citation to validate
        project_root: Root directory of the project

    Returns:
        ValidationResult with LINE_BOUNDS level
    """
    file_path = project_root / citation.file_path

    # File must exist (should be checked by file_exists validator first)
    if not file_path.exists():
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.LINE_BOUNDS,
            message="Cannot check line bounds: file does not exist",
            details={"file_path": citation.file_path},
        )

    # Count lines in file
    try:
        total_lines = _count_lines(file_path)
    except OSError as e:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.LINE_BOUNDS,
            message=f"Cannot read file to check line bounds: {e}",
            details={"error": str(e)},
        )

    # Check start line is valid (1-indexed)
    if citation.start_line < 1:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.LINE_BOUNDS,
            message=f"Invalid start line {citation.start_line}: must be >= 1",
            details={"start_line": citation.start_line, "total_lines": total_lines},
        )

    # Check start line is within bounds
    if citation.start_line > total_lines:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.LINE_BOUNDS,
            message=f"Line {citation.start_line} does not exist (file has {total_lines} lines)",
            details={
                "start_line": citation.start_line,
                "total_lines": total_lines,
                "file_path": citation.file_path,
            },
        )

    # Check end line if specified
    if citation.end_line is not None:
        # End must be >= start
        if citation.end_line < citation.start_line:
            return ValidationResult(
                citation=citation,
                status=CitationStatus.ERROR,
                level=ValidationLevel.LINE_BOUNDS,
                message=f"Invalid range: end line {citation.end_line} < start line {citation.start_line}",
                details={
                    "start_line": citation.start_line,
                    "end_line": citation.end_line,
                },
            )

        # End must be within bounds
        if citation.end_line > total_lines:
            return ValidationResult(
                citation=citation,
                status=CitationStatus.ERROR,
                level=ValidationLevel.LINE_BOUNDS,
                message=f"End line {citation.end_line} does not exist (file has {total_lines} lines)",
                details={
                    "start_line": citation.start_line,
                    "end_line": citation.end_line,
                    "total_lines": total_lines,
                },
            )

    # All checks passed
    line_count = citation.line_count
    message = f"Line bounds valid ({line_count} line{'s' if line_count > 1 else ''})"

    return ValidationResult(
        citation=citation,
        status=CitationStatus.VALID,
        level=ValidationLevel.LINE_BOUNDS,
        message=message,
        details={
            "start_line": citation.start_line,
            "end_line": citation.end_line,
            "total_lines": total_lines,
            "line_count": line_count,
        },
    )
