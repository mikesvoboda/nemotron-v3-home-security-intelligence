#!/usr/bin/env python3
"""One-time cleanup script to remove orphaned 'Test Camera' entries from the database.

This script removes cameras that were left behind by integration tests that didn't
properly clean up after themselves.

Usage:
    # Dry run (shows what would be deleted):
    python scripts/cleanup_orphaned_test_cameras.py --dry-run

    # Actually delete:
    python scripts/cleanup_orphaned_test_cameras.py

    # With custom database URL:
    DATABASE_URL=postgresql://... python scripts/cleanup_orphaned_test_cameras.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


async def cleanup_orphaned_cameras(dry_run: bool = True) -> dict:
    """Clean up orphaned test camera entries from the database.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        dict with counts of deleted items
    """
    from backend.core.config import get_settings
    from backend.core.database import close_db, get_session, init_db
    from sqlalchemy import text

    # Patterns that identify test cameras
    test_camera_patterns = [
        "Test Camera",
        "Test Camera %",
        "Front Door Camera",
        "Back Door Camera",
        "Garage Camera",
        "Camera 1",
        "Camera 2",
        "Camera 3",
        "Camera 4",
        "Camera 5",
        "Online Camera",
        "Offline Camera",
        "Error Camera",
        "Old Name %",
        "New Name",
        "Bad Cam %",
        "Front Door %",
        "Front Door",
        "Front %",
        "Back %",
        "Back Yard",
        "Garage",
        "Garage %",
        "Driveway",
        "Driveway %",
        "Side Gate",
        "Porch",
        "Backyard",
        "Backyard %",
        "Workflow Test Camera",
        "Time Test Camera",
        "Risk Test Camera",
        "Cascade Test Camera",
        "Isolation Camera %",
        "Review Test Camera",
        "Video Test Camera",
        "cam_%",
    ]

    # Clear settings cache and initialize database
    get_settings.cache_clear()
    await init_db()

    try:
        async with get_session() as session:
            # Build the WHERE clause for all patterns
            conditions = " OR ".join(
                [f"name LIKE :pattern{i}" for i in range(len(test_camera_patterns))]
            )
            params = {f"pattern{i}": pattern for i, pattern in enumerate(test_camera_patterns)}

            # Count cameras to be deleted
            # Note: conditions is built from hardcoded patterns, params are parameterized
            count_query = text(f"SELECT COUNT(*) FROM cameras WHERE {conditions}")  # noqa: S608  # nosemgrep
            result = await session.execute(count_query, params)
            camera_count = result.scalar() or 0

            if camera_count == 0:
                print("No orphaned test cameras found.")
                return {"cameras": 0, "detections": 0, "events": 0}

            # Get the camera names for reporting
            names_query = text(  # nosemgrep
                f"SELECT id, name FROM cameras WHERE {conditions} ORDER BY name LIMIT 50"  # noqa: S608
            )
            result = await session.execute(names_query, params)
            cameras = result.fetchall()

            print(f"\nFound {camera_count} orphaned test camera(s):")
            for camera_id, name in cameras:
                print(f"  - {name} (ID: {camera_id})")
            if camera_count > 50:
                print(f"  ... and {camera_count - 50} more")

            # Count related detections
            detection_count_query = text(  # nosemgrep
                f"SELECT COUNT(*) FROM detections WHERE camera_id IN (SELECT id FROM cameras WHERE {conditions})"  # noqa: S608
            )
            result = await session.execute(detection_count_query, params)
            detection_count = result.scalar() or 0

            # Count related events
            event_count_query = text(  # nosemgrep
                f"SELECT COUNT(*) FROM events WHERE camera_id IN (SELECT id FROM cameras WHERE {conditions})"  # noqa: S608
            )
            result = await session.execute(event_count_query, params)
            event_count = result.scalar() or 0

            print("\nRelated data to be deleted:")
            print(f"  - {detection_count} detection(s)")
            print(f"  - {event_count} event(s)")
            print(f"  - {camera_count} camera(s)")

            if dry_run:
                print("\n[DRY RUN] No changes made. Run without --dry-run to delete.")
                return {
                    "cameras": camera_count,
                    "detections": detection_count,
                    "events": event_count,
                }

            # Actually delete the data
            print("\nDeleting...")

            # Delete detections first (foreign key constraint)
            await session.execute(
                text(  # nosemgrep
                    f"DELETE FROM detections WHERE camera_id IN (SELECT id FROM cameras WHERE {conditions})"  # noqa: S608
                ),
                params,
            )
            print(f"  Deleted {detection_count} detection(s)")

            # Delete events (foreign key constraint)
            await session.execute(
                text(  # nosemgrep
                    f"DELETE FROM events WHERE camera_id IN (SELECT id FROM cameras WHERE {conditions})"  # noqa: S608
                ),
                params,
            )
            print(f"  Deleted {event_count} event(s)")

            # Delete cameras
            await session.execute(
                text(f"DELETE FROM cameras WHERE {conditions}"),  # noqa: S608  # nosemgrep
                params,
            )
            print(f"  Deleted {camera_count} camera(s)")

            await session.commit()
            print("\nCleanup complete!")

            return {"cameras": camera_count, "detections": detection_count, "events": event_count}

    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean up orphaned test camera entries from the database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be deleted without actually deleting",
    )
    args = parser.parse_args()

    # Check if DATABASE_URL is set
    if not os.environ.get("DATABASE_URL"):
        # Try to use the default development URL
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"
        )
        print(f"Using default DATABASE_URL: {os.environ['DATABASE_URL']}")

    asyncio.run(cleanup_orphaned_cameras(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
