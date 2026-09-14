#!/usr/bin/env python3
"""Data migration script to fix entities with missing cameras_seen field.

This script fixes NEM-3262 by populating the cameras_seen field in entity_metadata
for entities that don't have it. This is a one-time migration for legacy data.

The script:
1. Finds entities without cameras_seen in entity_metadata
2. Populates cameras_seen from camera_id if available
3. Falls back to primary_detection.camera_id if needed

Usage:
    uv run python scripts/fix_entity_cameras_seen.py

This script is idempotent - safe to run multiple times.
"""

import asyncio
from datetime import UTC, datetime

from backend.core.database import async_session_maker
from backend.core.logging import get_logger
from backend.models import Detection, Entity
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

logger = get_logger(__name__)


async def fix_entity_cameras_seen() -> dict[str, int]:
    """Fix entities with missing cameras_seen field.

    Returns:
        Dictionary with migration statistics:
        - total_entities: Total number of entities checked
        - fixed_from_camera_id: Entities fixed using camera_id
        - fixed_from_primary_detection: Entities fixed using primary_detection
        - already_ok: Entities that already had cameras_seen
        - unfixable: Entities that couldn't be fixed
    """
    stats = {
        "total_entities": 0,
        "fixed_from_camera_id": 0,
        "fixed_from_primary_detection": 0,
        "already_ok": 0,
        "unfixable": 0,
    }

    async with async_session_maker() as session:
        # Get all entities
        stmt = select(Entity)
        result = await session.execute(stmt)
        entities = result.scalars().all()

        stats["total_entities"] = len(entities)
        logger.info(f"Processing {stats['total_entities']} entities...")

        for entity in entities:
            # Check if entity_metadata exists
            if entity.entity_metadata is None:
                entity.entity_metadata = {}

            # Check if cameras_seen already exists and is non-empty
            if (
                "cameras_seen" in entity.entity_metadata
                and isinstance(entity.entity_metadata["cameras_seen"], list)
                and len(entity.entity_metadata["cameras_seen"]) > 0
            ):
                stats["already_ok"] += 1
                continue

            # Try to fix from camera_id in metadata
            if "camera_id" in entity.entity_metadata:
                camera_id = entity.entity_metadata["camera_id"]
                if camera_id:
                    entity.entity_metadata["cameras_seen"] = [camera_id]
                    flag_modified(entity, "entity_metadata")
                    stats["fixed_from_camera_id"] += 1
                    logger.debug(
                        f"Entity {entity.id}: Set cameras_seen from camera_id: {camera_id}"
                    )
                    continue

            # Try to fix from primary_detection
            if entity.primary_detection_id:
                # Query detection to get camera_id
                det_stmt = select(Detection.camera_id).where(
                    Detection.id == entity.primary_detection_id
                )
                det_result = await session.execute(det_stmt)
                camera_id = det_result.scalar_one_or_none()

                if camera_id:
                    entity.entity_metadata["cameras_seen"] = [camera_id]
                    entity.entity_metadata["camera_id"] = camera_id
                    flag_modified(entity, "entity_metadata")
                    stats["fixed_from_primary_detection"] += 1
                    logger.debug(
                        f"Entity {entity.id}: Set cameras_seen from primary_detection: {camera_id}"
                    )
                    continue

            # Couldn't fix this entity
            stats["unfixable"] += 1
            logger.warning(
                f"Entity {entity.id}: Could not determine cameras_seen "
                f"(detection_count={entity.detection_count}, "
                f"primary_detection_id={entity.primary_detection_id})"
            )

        # Commit all changes
        await session.commit()

    return stats


async def main():
    """Run the migration and print results."""
    logger.info("Starting entity cameras_seen migration (NEM-3262)...")
    start_time = datetime.now(UTC)

    stats = await fix_entity_cameras_seen()

    end_time = datetime.now(UTC)
    duration = (end_time - start_time).total_seconds()

    # Print summary
    print("\n" + "=" * 60)
    print("Entity cameras_seen Migration Complete (NEM-3262)")
    print("=" * 60)
    print(f"Total entities processed: {stats['total_entities']}")
    print(f"Already correct: {stats['already_ok']}")
    print(f"Fixed from camera_id: {stats['fixed_from_camera_id']}")
    print(f"Fixed from primary_detection: {stats['fixed_from_primary_detection']}")
    print(f"Could not fix: {stats['unfixable']}")
    print(f"Duration: {duration:.2f} seconds")
    print("=" * 60)

    if stats["unfixable"] > 0:
        print(f"\n⚠️  {stats['unfixable']} entities could not be fixed automatically.")
        print("These entities have no camera_id or primary_detection to infer from.")
        print("They will continue to show '0 cameras' until they are re-detected.")


if __name__ == "__main__":
    asyncio.run(main())
