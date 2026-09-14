"""Level 5 Validator: Git-based staleness detection.

This module checks if documentation is stale by comparing the last
modification times of the documentation file and the cited source files.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from ..config import Citation, CitationStatus, ValidationLevel, ValidationResult


@lru_cache(maxsize=256)
def _get_file_last_modified(file_path: Path, project_root: Path) -> datetime | None:
    """Get the last modification time of a file from git.

    Uses git log to get the commit timestamp of the last change.

    Args:
        file_path: Path to the file (relative to project root)
        project_root: Root directory of the git repository

    Returns:
        datetime of last modification or None if not in git
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(file_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )

        timestamp_str = result.stdout.strip()
        if not timestamp_str:
            return None

        # Parse ISO 8601 timestamp
        # Handle timezone offset format (+00:00 -> +0000)
        if "+" in timestamp_str:
            parts = timestamp_str.rsplit("+", 1)
            if len(parts) == 2 and ":" in parts[1]:
                timestamp_str = parts[0] + "+" + parts[1].replace(":", "")
        elif timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+0000"

        return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S%z")

    except (subprocess.CalledProcessError, ValueError):
        return None


def _clear_cache() -> None:
    """Clear the git timestamp cache (for testing)."""
    _get_file_last_modified.cache_clear()


def validate_staleness(
    citation: Citation,
    project_root: Path,
    staleness_days: int = 0,
) -> ValidationResult:
    """Check if documentation is stale relative to the cited source.

    This is Level 5 validation. Compares git modification times:
    - If source file was modified after documentation, flag as stale
    - staleness_days parameter allows some tolerance

    Args:
        citation: The citation to validate
        project_root: Root directory of the project
        staleness_days: Number of days grace period (0 = any modification flags)

    Returns:
        ValidationResult with STALENESS level
    """
    # Get source file modification time
    source_path = Path(citation.file_path)
    source_modified = _get_file_last_modified(source_path, project_root)

    if source_modified is None:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.STALENESS,
            message="Cannot check staleness: source file not in git history",
            details={"reason": "source_not_in_git", "source_file": citation.file_path},
        )

    # Get documentation file modification time
    if not citation.doc_file:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.STALENESS,
            message="Cannot check staleness: no documentation file specified",
            details={"reason": "no_doc_file"},
        )

    doc_path = Path(citation.doc_file)
    # Handle both absolute and relative paths
    if doc_path.is_absolute():
        try:
            doc_path = doc_path.relative_to(project_root)
        except ValueError:
            # Path is not relative to project root
            pass

    doc_modified = _get_file_last_modified(doc_path, project_root)

    if doc_modified is None:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.STALENESS,
            message="Cannot check staleness: documentation file not in git history",
            details={"reason": "doc_not_in_git", "doc_file": str(doc_path)},
        )

    # Compare modification times
    if source_modified > doc_modified:
        # Calculate how many days stale
        delta = source_modified - doc_modified
        days_stale = delta.days

        if days_stale > staleness_days:
            return ValidationResult(
                citation=citation,
                status=CitationStatus.STALE,
                level=ValidationLevel.STALENESS,
                message=f"STALE: source modified {days_stale} days after documentation",
                details={
                    "source_modified": source_modified.isoformat(),
                    "doc_modified": doc_modified.isoformat(),
                    "days_stale": days_stale,
                    "source_file": citation.file_path,
                    "doc_file": str(doc_path),
                },
            )

    # Documentation is up to date
    return ValidationResult(
        citation=citation,
        status=CitationStatus.VALID,
        level=ValidationLevel.STALENESS,
        message="Documentation is up to date with source",
        details={
            "source_modified": source_modified.isoformat(),
            "doc_modified": doc_modified.isoformat(),
        },
    )
