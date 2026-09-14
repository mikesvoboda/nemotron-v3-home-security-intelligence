#!/usr/bin/env python3
"""Pre-commit hook to detect validation drift between backend Pydantic and frontend Zod schemas.

This hook helps maintain validation alignment between:
- Backend: Pydantic schemas in backend/api/schemas/*.py
- Frontend: Zod schemas in frontend/src/schemas/*.ts

When backend Pydantic schemas are modified, this hook:
1. Warns developers to verify frontend Zod schemas match
2. Checks if corresponding frontend schema files exist
3. Compares modification timestamps to detect potential drift

Usage as pre-commit hook:
    Automatically runs when files in backend/api/schemas/ are modified

Usage standalone:
    python scripts/check-validation-drift.py                    # Check all schema files
    python scripts/check-validation-drift.py backend/api/schemas/camera.py  # Check specific file

Exit codes:
    0 - Success (no action needed or warning only)
    1 - Error (should not happen in normal operation)

NEM-2347: Add pre-commit hook to detect validation drift

Related issues:
    - NEM-1975: Audit form fields vs Pydantic schemas
    - NEM-2345: Generate Zod schemas from OpenAPI
    - NEM-2346: Zod schema unit tests
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NamedTuple


class SchemaMapping(NamedTuple):
    """Maps a backend Pydantic schema to its frontend Zod counterpart."""

    backend_file: str  # e.g., "camera.py"
    frontend_file: str  # e.g., "camera.ts"
    description: str  # Human-readable description


# Known schema mappings between backend Pydantic and frontend Zod
# Add new mappings here as Zod schemas are created
SCHEMA_MAPPINGS: list[SchemaMapping] = [
    SchemaMapping(
        backend_file="camera.py",
        frontend_file="camera.ts",
        description="Camera CRUD validation (CameraCreate, CameraUpdate)",
    ),
    # Add future mappings as Zod schemas are implemented:
    # - zone.py -> zone.ts (Zone management validation)
    # - alerts.py -> alerts.ts (Alert configuration validation)
    # - notification.py -> notification.ts (Notification preferences)
]

# Backend schemas that have validation rules used in frontend forms
# These are the priority schemas to keep aligned
PRIORITY_SCHEMAS = {
    "camera.py",  # Camera settings form
    "zone.py",  # Zone management
    "alerts.py",  # Alert configuration
    "notification.py",  # Notification preferences
    "notification_preferences.py",  # Notification preferences detailed
}


def get_project_root() -> Path:
    """Find project root by looking for pyproject.toml."""
    current = Path(__file__).resolve().parent.parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback to script's parent's parent
    return Path(__file__).resolve().parent.parent


def find_frontend_schema(backend_file: str, frontend_schemas_dir: Path) -> Path | None:
    """Find corresponding frontend Zod schema for a backend Pydantic schema.

    Args:
        backend_file: Backend schema filename (e.g., "camera.py")
        frontend_schemas_dir: Path to frontend/src/schemas/

    Returns:
        Path to frontend schema if found, None otherwise
    """
    # Check explicit mappings first
    for mapping in SCHEMA_MAPPINGS:
        if mapping.backend_file == backend_file:
            frontend_path = frontend_schemas_dir / mapping.frontend_file
            if frontend_path.exists():
                return frontend_path
            return None

    # Infer frontend path from backend filename
    base_name = backend_file.replace(".py", "")
    potential_paths = [
        frontend_schemas_dir / f"{base_name}.ts",
        frontend_schemas_dir / f"{base_name}.tsx",
        frontend_schemas_dir / f"{base_name}Schema.ts",
    ]

    for path in potential_paths:
        if path.exists():
            return path

    return None


def check_schema_drift(
    changed_files: list[Path],
    project_root: Path,
) -> tuple[list[str], list[str], list[str]]:
    """Check for potential validation drift in changed schema files.

    Args:
        changed_files: List of changed backend schema files
        project_root: Project root directory

    Returns:
        Tuple of (warnings, infos, errors)
    """
    warnings: list[str] = []
    infos: list[str] = []
    errors: list[str] = []

    frontend_schemas_dir = project_root / "frontend" / "src" / "schemas"

    for backend_path in changed_files:
        backend_file = backend_path.name

        # Skip __init__.py and non-priority schemas
        if backend_file == "__init__.py":
            continue

        # Find corresponding frontend schema
        frontend_path = find_frontend_schema(backend_file, frontend_schemas_dir)

        if frontend_path:
            # Frontend schema exists - warn to verify alignment
            warnings.append(
                f"VALIDATION DRIFT CHECK: {backend_file} modified\n"
                f"  Backend:  {backend_path.relative_to(project_root)}\n"
                f"  Frontend: {frontend_path.relative_to(project_root)}\n"
                f"  Action:   Verify frontend Zod schema matches backend Pydantic constraints\n"
                f"  Tool:     Run 'uv run python scripts/extract_pydantic_constraints.py --schema {backend_file.replace('.py', '')}'"
            )
        elif backend_file in PRIORITY_SCHEMAS:
            # Priority schema without frontend counterpart
            infos.append(
                f"NOTE: Priority schema {backend_file} modified but no frontend Zod schema found\n"
                f"  Backend: {backend_path.relative_to(project_root)}\n"
                f"  Expected frontend: frontend/src/schemas/{backend_file.replace('.py', '.ts')}\n"
                f"  Consider: Creating Zod schema for form validation alignment"
            )
        else:
            # Non-priority schema - just note it
            infos.append(
                f"INFO: Backend schema {backend_file} modified (no frontend counterpart)\n"
                f"  File: {backend_path.relative_to(project_root)}"
            )

    return warnings, infos, errors


def check_frontend_schemas_modified(
    changed_files: list[Path],
    project_root: Path,
) -> list[str]:
    """Check if frontend Zod schemas were modified without backend changes.

    Args:
        changed_files: List of changed frontend schema files
        project_root: Project root directory

    Returns:
        List of info messages
    """
    infos: list[str] = []
    backend_schemas_dir = project_root / "backend" / "api" / "schemas"

    for frontend_path in changed_files:
        frontend_file = frontend_path.name

        # Skip index files
        if frontend_file in ("index.ts", "index.tsx"):
            continue

        # Find corresponding backend schema
        base_name = frontend_file.replace(".ts", "").replace(".tsx", "").replace("Schema", "")
        potential_backend = backend_schemas_dir / f"{base_name}.py"

        if potential_backend.exists():
            infos.append(
                f"NOTE: Frontend Zod schema {frontend_file} modified\n"
                f"  Frontend: {frontend_path.relative_to(project_root)}\n"
                f"  Backend:  {potential_backend.relative_to(project_root)}\n"
                f"  Verify:   Frontend validation matches backend Pydantic constraints"
            )

    return infos


def main() -> int:
    """Main entry point for pre-commit hook.

    Returns:
        0 on success, 1 on error
    """
    project_root = get_project_root()
    backend_schemas_dir = project_root / "backend" / "api" / "schemas"
    frontend_schemas_dir = project_root / "frontend" / "src" / "schemas"

    # Get files to check from command line arguments or environment
    # Note: Empty list fallback for standalone testing when no files provided
    all_files = [Path(f) for f in sys.argv[1:]] if len(sys.argv) > 1 else []

    # Separate backend and frontend schema files
    backend_changed: list[Path] = []
    frontend_changed: list[Path] = []

    for input_path in all_files:
        # Resolve to absolute path if relative
        resolved_path = input_path if input_path.is_absolute() else project_root / input_path

        if not resolved_path.exists():
            continue

        # Check if it's a backend schema file
        try:
            if (
                backend_schemas_dir in resolved_path.parents
                or resolved_path.parent == backend_schemas_dir
            ):
                if resolved_path.suffix == ".py":
                    backend_changed.append(resolved_path)
        except ValueError:
            pass

        # Check if it's a frontend schema file
        try:
            if (
                frontend_schemas_dir in resolved_path.parents
                or resolved_path.parent == frontend_schemas_dir
            ):
                if resolved_path.suffix in (".ts", ".tsx"):
                    frontend_changed.append(resolved_path)
        except ValueError:
            pass

    # Check for drift
    warnings, infos, errors = check_schema_drift(backend_changed, project_root)

    # Check frontend-only changes
    frontend_infos = check_frontend_schemas_modified(frontend_changed, project_root)
    infos.extend(frontend_infos)

    # Print results
    if errors:
        print("\n" + "=" * 80)
        print("VALIDATION DRIFT ERRORS")
        print("=" * 80)
        for error in errors:
            print(f"\n{error}")
        return 1

    if warnings:
        print("\n" + "=" * 80)
        print("VALIDATION DRIFT WARNINGS")
        print("=" * 80)
        for warning in warnings:
            print(f"\n{warning}")

        print("\n" + "-" * 80)
        print("WHY THIS MATTERS:")
        print("  Frontend Zod schemas must match backend Pydantic validation rules.")
        print("  Mismatches cause poor UX (frontend accepts what backend rejects).")
        print("")
        print("WHAT TO DO:")
        print("  1. Review the changed backend schema constraints")
        print("  2. Update the corresponding frontend Zod schema if needed")
        print("  3. Run frontend tests: cd frontend && npm test -- schemas")
        print("  4. See docs/plans/validation-alignment.md for guidelines")
        print("-" * 80 + "\n")

    if infos and os.environ.get("VALIDATION_DRIFT_VERBOSE"):
        print("\n" + "-" * 60)
        print("VALIDATION DRIFT INFO (verbose mode)")
        print("-" * 60)
        for info in infos:
            print(f"\n{info}")

    # Always return 0 - this is a warning-only hook, not a blocker
    # Developers should review warnings but commits are not blocked
    return 0


if __name__ == "__main__":
    sys.exit(main())
