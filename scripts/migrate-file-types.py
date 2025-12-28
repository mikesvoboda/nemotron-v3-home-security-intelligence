#!/usr/bin/env python
"""Migration script to normalize file_type values to MIME types.

This script updates existing Detection records that have file extensions
(e.g., ".jpg", ".mp4") in the file_type field to use proper MIME types
(e.g., "image/jpeg", "video/mp4").

Usage:
    python scripts/migrate-file-types.py [--dry-run]

Options:
    --dry-run    Preview changes without modifying the database
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.database import close_db, get_session_factory, init_db  # noqa: E402
from backend.core.mime_types import normalize_file_type  # noqa: E402
from backend.models.detection import Detection  # noqa: E402
from sqlalchemy import select, update  # noqa: E402


async def migrate_file_types(dry_run: bool = False) -> None:
    """Migrate file_type values from extensions to MIME types.

    Args:
        dry_run: If True, only preview changes without modifying database
    """
    # Initialize database
    await init_db()
    session_factory = get_session_factory()

    async with session_factory() as session:
        # Find all detections with file_type that looks like an extension
        # (starts with "." or doesn't contain "/")
        query = select(Detection).where(
            Detection.file_type.is_not(None),
            # Extension format: starts with "." or doesn't contain "/"
            ~Detection.file_type.contains("/"),
        )

        result = await session.execute(query)
        detections = result.scalars().all()

        if not detections:
            print("No detections with extension-based file_type values found.")
            return

        print(f"Found {len(detections)} detections with extension-based file_type values.")
        print()

        updates = []
        for detection in detections:
            old_value = detection.file_type
            new_value = normalize_file_type(old_value, detection.file_path)

            if new_value and new_value != old_value:
                updates.append(
                    {
                        "id": detection.id,
                        "old_file_type": old_value,
                        "new_file_type": new_value,
                    }
                )
                print(f"  Detection {detection.id}: '{old_value}' -> '{new_value}'")

        print()
        print(f"Total updates to apply: {len(updates)}")

        if dry_run:
            print("\n[DRY RUN] No changes were made to the database.")
            return

        if not updates:
            print("No updates needed.")
            return

        # Apply updates
        print("\nApplying updates...")
        for update_data in updates:
            stmt = (
                update(Detection)
                .where(Detection.id == update_data["id"])
                .values(file_type=update_data["new_file_type"])
            )
            await session.execute(stmt)

        await session.commit()
        print(f"Successfully updated {len(updates)} detection records.")

    await close_db()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate file_type values from extensions to MIME types"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying the database",
    )
    args = parser.parse_args()

    asyncio.run(migrate_file_types(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
