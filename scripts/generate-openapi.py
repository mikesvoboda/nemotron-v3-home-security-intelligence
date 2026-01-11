#!/usr/bin/env python3
"""Generate standalone OpenAPI spec from FastAPI app.

This script extracts the OpenAPI specification from the FastAPI application
and saves it as a standalone JSON file for:
- API documentation hosting
- Client SDK generation
- Contract testing
- CI validation

Usage:
    # Generate the OpenAPI spec
    uv run python scripts/generate-openapi.py

    # Check if spec is current (for CI)
    uv run python scripts/generate-openapi.py --check

    # Specify custom output path
    uv run python scripts/generate-openapi.py --output api/openapi.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set required environment variables before importing the app
# fmt: off
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/security")  # pragma: allowlist secret
# fmt: on
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


def get_openapi_spec() -> dict:
    """Extract OpenAPI spec from FastAPI app."""
    from backend.main import app

    return app.openapi()


def main() -> int:
    """Generate or check OpenAPI specification."""
    parser = argparse.ArgumentParser(
        description="Generate standalone OpenAPI spec from FastAPI app"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if spec is current (exits with error if not)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/openapi.json"),
        help="Output path for OpenAPI spec (default: docs/openapi.json)",
    )
    args = parser.parse_args()

    # Resolve and validate output path
    project_root = Path(__file__).parent.parent.resolve()
    output_path = (project_root / args.output).resolve()

    # Security: Ensure output path is within project directory
    if not str(output_path).startswith(str(project_root)):
        print(f"ERROR: Output path must be within project directory: {project_root}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get current spec from app
    spec = get_openapi_spec()

    if args.check:
        # Validate existing spec matches current
        if not output_path.exists():
            print(f"ERROR: {output_path} does not exist.")
            print(f"Run: uv run python {__file__}")
            return 1

        # Compare file content directly (includes formatting)
        expected_content = json.dumps(spec, indent=2, sort_keys=True) + "\n"
        existing_content = output_path.read_text()

        if existing_content != expected_content:
            print(f"ERROR: {output_path} is out of date.")
            print(f"Run: uv run python {__file__}")
            return 1

        print(f"✓ {output_path} is current")
        return 0

    # Generate the new spec content
    new_content = json.dumps(spec, indent=2, sort_keys=True) + "\n"

    # Check if file already exists with same content (skip unnecessary writes)
    if output_path.exists():
        existing_content = output_path.read_text()
        if existing_content == new_content:
            print(f"✓ {output_path} is already up to date")
            return 0

    # Write spec (path validated above to be within project directory)
    with open(output_path, "w") as f:  # nosemgrep: path-traversal-open
        f.write(new_content)

    print(f"Generated {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
