"""Level 1 Validator: File existence checks.

This module validates that cited files exist in the repository.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Citation, CitationStatus, ValidationLevel, ValidationResult


def _validate_path_security(
    file_path: str,
    project_root: Path,
) -> str | None:
    """Validate file path for security issues.

    Checks for path traversal attacks and ensures the resolved path
    stays within the project root directory (NEM-4480).

    Args:
        file_path: The citation file path to validate
        project_root: Root directory of the project

    Returns:
        Error message if path is invalid, None if valid
    """
    # Reject absolute paths (they should always be relative to project root)
    if Path(file_path).is_absolute():
        return f"Absolute path not allowed: {file_path}"

    # Reject explicit path traversal attempts
    if ".." in file_path:
        return f"Path traversal not allowed: {file_path}"

    # Resolve the full path and verify it's still under project root
    resolved_path = (project_root / file_path).resolve()
    resolved_root = project_root.resolve()

    # Use os.path.commonpath or string comparison to verify containment
    # str.startswith is safe here because we're comparing resolved absolute paths
    if (
        not str(resolved_path).startswith(str(resolved_root) + "/")
        and resolved_path != resolved_root
    ):
        return f"Path escapes project root: {file_path}"

    return None


def validate_file_exists(
    citation: Citation,
    project_root: Path,
) -> ValidationResult:
    """Validate that the cited file exists.

    This is Level 1 validation - the most basic check.

    Security: This function validates paths to prevent path traversal
    attacks before accessing the filesystem (NEM-4480).

    Args:
        citation: The citation to validate
        project_root: Root directory of the project

    Returns:
        ValidationResult with FILE_EXISTS level
    """
    # Security: Validate path before filesystem access (NEM-4480)
    path_error = _validate_path_security(citation.file_path, project_root)
    if path_error:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.FILE_EXISTS,
            message=f"Security error: {path_error}",
            details={"security_violation": True, "file_path": citation.file_path},
        )

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
