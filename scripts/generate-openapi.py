#!/usr/bin/env python3
"""Generate standalone OpenAPI spec from FastAPI app with smart change detection.

This script extracts the OpenAPI specification from the FastAPI application
and saves it as a standalone JSON file for:
- API documentation hosting
- Client SDK generation
- Contract testing
- CI validation

Performance Optimizations:
- Hash-based change detection: Only regenerates when API files actually change
- Content comparison: Skips write if output would be identical
- Timing metrics: Reports execution time for performance monitoring

Expected Runtime:
- Skip path (no changes): ~50-200ms (hash comparison only)
- Regeneration path: ~1-3s (full app import + spec generation)

Usage:
    # Generate the OpenAPI spec (with smart caching)
    uv run python scripts/generate-openapi.py

    # Check if spec is current (for CI)
    uv run python scripts/generate-openapi.py --check

    # Force regeneration (bypass change detection)
    uv run python scripts/generate-openapi.py --force

    # Specify custom output path
    uv run python scripts/generate-openapi.py --output api/openapi.json

    # Verbose mode with timing details
    uv run python scripts/generate-openapi.py --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import IO

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set required environment variables before importing the app
# fmt: off
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/security")  # pragma: allowlist secret
# fmt: on
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# =============================================================================
# Constants
# =============================================================================

# Directories containing API-related files that affect OpenAPI spec
API_DIRECTORIES = [
    "backend/api",
    "backend/models",
    "backend/schemas",
]

# File patterns to include in hash calculation
API_FILE_PATTERNS = ["*.py"]

# Cache file location for storing the hash of API files
CACHE_FILE = Path(".openapi-cache")

# =============================================================================
# Timing Utilities
# =============================================================================


class Timer:
    """Simple timer for measuring execution time."""

    def __init__(self) -> None:
        self._start: float | None = None
        self._end: float | None = None
        self._checkpoints: list[tuple[str, float]] = []

    def start(self) -> None:
        """Start the timer."""
        self._start = time.perf_counter()

    def checkpoint(self, name: str) -> None:
        """Record a checkpoint with the given name."""
        if self._start is None:
            return
        self._checkpoints.append((name, time.perf_counter() - self._start))

    def stop(self) -> None:
        """Stop the timer."""
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self._start is None:
            return 0.0
        end = self._end if self._end is not None else time.perf_counter()
        return (end - self._start) * 1000

    def format_report(self) -> str:
        """Format a timing report with checkpoints."""
        lines = []
        for name, elapsed in self._checkpoints:
            lines.append(f"  {name}: {elapsed * 1000:.1f}ms")
        lines.append(f"  Total: {self.elapsed_ms:.1f}ms")
        return "\n".join(lines)


# =============================================================================
# Change Detection
# =============================================================================


def _hash_file(file_path: Path, project_root: Path | None = None) -> str:
    """Compute SHA256 hash of a file's contents.

    Args:
        file_path: Path to the file to hash
        project_root: Optional project root to validate path is within bounds

    Returns:
        SHA256 hex digest of file contents
    """
    # Resolve to absolute path to prevent path traversal
    resolved_path = file_path.resolve()

    # If project_root provided, ensure path is within it
    if project_root is not None:
        resolved_root = project_root.resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            raise ValueError(  # noqa: B904
                f"Path {resolved_path} is outside project root {resolved_root}"
            )

    hasher = hashlib.sha256()
    with resolved_path.open("rb") as f:  # nosemgrep: path-traversal-open
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _get_api_files(project_root: Path) -> list[Path]:
    """Get all API-related Python files sorted by path for deterministic hashing."""
    files: list[Path] = []

    for dir_name in API_DIRECTORIES:
        dir_path = project_root / dir_name
        if not dir_path.exists():
            continue

        for pattern in API_FILE_PATTERNS:
            files.extend(dir_path.rglob(pattern))

    # Sort for deterministic ordering
    return sorted(files)


def compute_api_hash(project_root: Path) -> str:
    """Compute a combined hash of all API-related files.

    This hash represents the current state of all files that could affect
    the OpenAPI specification. If this hash matches the cached hash,
    regeneration can be safely skipped.

    Args:
        project_root: Root directory of the project

    Returns:
        SHA256 hash string representing the combined state of all API files
    """
    combined_hasher = hashlib.sha256()

    api_files = _get_api_files(project_root)

    for file_path in api_files:
        # Include relative path in hash to detect file renames/moves
        rel_path = file_path.relative_to(project_root)
        combined_hasher.update(str(rel_path).encode())
        combined_hasher.update(_hash_file(file_path).encode())

    return combined_hasher.hexdigest()


def read_cached_hash(project_root: Path) -> str | None:
    """Read the cached hash from the cache file.

    Args:
        project_root: Root directory of the project

    Returns:
        Cached hash string, or None if cache doesn't exist or is invalid
    """
    cache_path = project_root / CACHE_FILE
    if not cache_path.exists():
        return None

    try:
        content = cache_path.read_text().strip()
        # Validate it looks like a SHA256 hash
        if len(content) == 64 and all(c in "0123456789abcdef" for c in content):
            return content
        return None
    except (OSError, UnicodeDecodeError):
        return None


def write_cached_hash(project_root: Path, hash_value: str) -> None:
    """Write the hash to the cache file.

    Args:
        project_root: Root directory of the project
        hash_value: Hash string to cache
    """
    cache_path = project_root / CACHE_FILE
    cache_path.write_text(hash_value + "\n")


def spec_needs_regeneration(project_root: Path, verbose: bool = False) -> tuple[bool, str]:
    """Check if the OpenAPI spec needs to be regenerated.

    This compares the current hash of API files against the cached hash
    from the last successful generation.

    Args:
        project_root: Root directory of the project
        verbose: Whether to print verbose output

    Returns:
        Tuple of (needs_regeneration, reason)
    """
    current_hash = compute_api_hash(project_root)
    cached_hash = read_cached_hash(project_root)

    if cached_hash is None:
        return True, "No cached hash found (first run or cache cleared)"

    if current_hash != cached_hash:
        return True, "API files have changed since last generation"

    return False, f"No changes detected (hash: {current_hash[:12]}...)"


# =============================================================================
# OpenAPI Generation
# =============================================================================


def get_openapi_spec() -> dict[str, object]:
    """Extract OpenAPI spec from FastAPI app."""
    from backend.main import app

    result: dict[str, object] = app.openapi()
    return result


def format_spec(spec: dict[str, object]) -> str:
    """Format the OpenAPI spec as JSON with consistent formatting."""
    return json.dumps(spec, indent=2, sort_keys=True) + "\n"


# =============================================================================
# Main Entry Point
# =============================================================================


def main(
    args: argparse.Namespace | None = None,
    stdout: IO[str] | None = None,
) -> int:
    """Generate or check OpenAPI specification.

    Args:
        args: Parsed command-line arguments (for testing)
        stdout: Output stream (for testing)

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    if stdout is None:
        stdout = sys.stdout

    if args is None:
        parser = argparse.ArgumentParser(
            description="Generate standalone OpenAPI spec from FastAPI app"
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Check if spec is current (exits with error if not)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force regeneration (bypass change detection)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed timing and progress information",
        )
        parser.add_argument(
            "--output",
            type=Path,
            default=Path("docs/openapi.json"),
            help="Output path for OpenAPI spec (default: docs/openapi.json)",
        )
        args = parser.parse_args()

    timer = Timer()
    timer.start()

    # Resolve and validate paths
    project_root = Path(__file__).parent.parent.resolve()
    output_path = (project_root / args.output).resolve()

    # Security: Ensure output path is within project directory
    if not str(output_path).startswith(str(project_root)):
        print(f"ERROR: Output path must be within project directory: {project_root}", file=stdout)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    timer.checkpoint("Path validation")

    # Check mode: validate existing spec matches current
    if args.check:
        return _handle_check_mode(project_root, output_path, timer, args.verbose, stdout)

    # Generation mode: check if regeneration is needed
    if not args.force:
        needs_regen, reason = spec_needs_regeneration(project_root, args.verbose)
        timer.checkpoint("Change detection")

        if not needs_regen:
            # Double-check that the output file exists
            if output_path.exists():
                print(f"[SKIP] {reason}", file=stdout)
                if args.verbose:
                    timer.stop()
                    print(f"\nTiming:\n{timer.format_report()}", file=stdout)
                return 0
            else:
                reason = "Output file missing despite matching hash"

        if args.verbose:
            print(f"[REGEN] {reason}", file=stdout)

    # Generate the spec
    spec = get_openapi_spec()
    timer.checkpoint("Spec generation")

    new_content = format_spec(spec)
    timer.checkpoint("JSON formatting")

    # Check if file already exists with same content (skip unnecessary writes)
    if output_path.exists():
        existing_content = output_path.read_text()
        if existing_content == new_content:
            # Update cache even if content matches (API files may have changed
            # in ways that don't affect output, e.g., comments)
            current_hash = compute_api_hash(project_root)
            write_cached_hash(project_root, current_hash)

            print(f"[OK] {output_path} is already up to date", file=stdout)
            if args.verbose:
                timer.stop()
                print(f"\nTiming:\n{timer.format_report()}", file=stdout)
            return 0

    # Write spec (path validated above to be within project directory)
    with open(output_path, "w") as f:  # nosemgrep: path-traversal-open
        f.write(new_content)
    timer.checkpoint("File write")

    # Update cache with current hash
    current_hash = compute_api_hash(project_root)
    write_cached_hash(project_root, current_hash)
    timer.checkpoint("Cache update")

    timer.stop()

    print(f"[GENERATED] {output_path}", file=stdout)
    if args.verbose:
        print(f"\nTiming:\n{timer.format_report()}", file=stdout)
    else:
        print(f"  Time: {timer.elapsed_ms:.0f}ms", file=stdout)

    return 0


def _handle_check_mode(
    project_root: Path,
    output_path: Path,
    timer: Timer,
    verbose: bool,
    stdout: IO[str],
) -> int:
    """Handle --check mode: validate existing spec matches current.

    Args:
        project_root: Root directory of the project
        output_path: Path to the OpenAPI spec file
        timer: Timer instance for performance tracking
        verbose: Whether to show verbose output
        stdout: Output stream

    Returns:
        Exit code (0 if spec is current, 1 if not)
    """
    if not output_path.exists():
        print(f"ERROR: {output_path} does not exist.", file=stdout)
        print(f"Run: uv run python {__file__}", file=stdout)
        return 1

    # Generate current spec
    spec = get_openapi_spec()
    timer.checkpoint("Spec generation")

    expected_content = format_spec(spec)
    existing_content = output_path.read_text()

    timer.checkpoint("Content comparison")
    timer.stop()

    if existing_content != expected_content:
        print(f"ERROR: {output_path} is out of date.", file=stdout)
        print(f"Run: uv run python {__file__}", file=stdout)
        return 1

    print(f"[OK] {output_path} is current", file=stdout)
    if verbose:
        print(f"\nTiming:\n{timer.format_report()}", file=stdout)

    return 0


if __name__ == "__main__":
    sys.exit(main())
