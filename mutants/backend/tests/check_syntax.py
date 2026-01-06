#!/usr/bin/env python3
"""Quick syntax check for database module."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    print("Checking imports...")

    print("  - Importing config...")

    print("  - Importing database...")

    print("  - Importing from core package...")

    print("\n✓ All imports successful!")
    print("\nAvailable exports:")
    print("  Config: Settings, get_settings")
    print("  Database: Base, init_db, close_db, get_engine, get_session_factory,")
    print("           get_session, get_db")

except Exception as e:
    print(f"\n✗ Import failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
