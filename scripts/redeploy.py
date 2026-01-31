#!/usr/bin/env python3
"""Entry point for the redeploy tool.

Usage:
    uv run scripts/redeploy.py [OPTIONS]

Examples:
    # Full local build (default)
    uv run scripts/redeploy.py

    # Keep data between deploys
    uv run scripts/redeploy.py --keep-volumes

    # Use GHCR images for core, build AI locally
    uv run scripts/redeploy.py --mode hybrid

    # Dry run to see what would happen
    uv run scripts/redeploy.py --dry-run

    # Fix corrupted container storage
    uv run scripts/redeploy.py --reset-storage

    # Other commands
    uv run scripts/redeploy.py stop     # Stop all containers
    uv run scripts/redeploy.py status   # Show container status
    uv run scripts/redeploy.py prune    # Clean up build artifacts
"""

import sys
from pathlib import Path

# Add project root to sys.path so 'scripts.redeploy' imports work
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scripts.redeploy.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
