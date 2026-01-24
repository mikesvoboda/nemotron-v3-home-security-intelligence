"""Level 1 Validator: File existence checks.

This module validates that cited files exist in the repository.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Citation, CitationStatus, ValidationLevel, ValidationResult


def validate_file_exists(
    citation: Citation,
    project_root: Path,
) -> ValidationResult:
    """Validate that the cited file exists.

    This is Level 1 validation - the most basic check.

    Args:
        citation: The citation to validate
        project_root: Root directory of the project

    Returns:
        ValidationResult with FILE_EXISTS level
    """
    file_path = project_root / citation.file_path

    if not file_path.exists():
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.FILE_EXISTS,
            message=f"File does not exist: {citation.file_path}",
            details={"expected_path": str(file_path)},
        )

    if not file_path.is_file():
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.FILE_EXISTS,
            message=f"Path is not a file: {citation.file_path}",
            details={"path_type": "directory" if file_path.is_dir() else "unknown"},
        )

    return ValidationResult(
        citation=citation,
        status=CitationStatus.VALID,
        level=ValidationLevel.FILE_EXISTS,
        message=f"File exists: {citation.file_path}",
        details={"file_size": file_path.stat().st_size},
    )
