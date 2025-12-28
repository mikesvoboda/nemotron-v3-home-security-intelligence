#!/usr/bin/env python3
"""Seed the database with test cameras for development."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import get_session, init_db
from backend.models.camera import Camera
from sqlalchemy import delete, select

# Sample camera configurations
SAMPLE_CAMERAS = [
    {
        "id": "front-door",
        "name": "Front Door",
        "folder_path": "/export/foscam/front_door",
        "status": "online",
    },
    {
        "id": "backyard",
        "name": "Backyard",
        "folder_path": "/export/foscam/backyard",
        "status": "online",
    },
    {
        "id": "garage",
        "name": "Garage",
        "folder_path": "/export/foscam/garage",
        "status": "offline",
    },
    {
        "id": "driveway",
        "name": "Driveway",
        "folder_path": "/export/foscam/driveway",
        "status": "online",
    },
    {
        "id": "side-gate",
        "name": "Side Gate",
        "folder_path": "/export/foscam/side_gate",
        "status": "online",
    },
    {
        "id": "living-room",
        "name": "Living Room",
        "folder_path": "/export/foscam/living_room",
        "status": "offline",
    },
]


async def clear_cameras() -> int:
    """Remove all cameras from the database.

    Returns:
        Number of cameras deleted.
    """
    async with get_session() as session:
        result = await session.execute(select(Camera))
        cameras = result.scalars().all()
        count = len(cameras)

        if count > 0:
            await session.execute(delete(Camera))
            await session.commit()
            print(f"Cleared {count} existing cameras")
        else:
            print("No cameras to clear")

        return count


async def seed_cameras(count: int, create_folders: bool = True) -> int:
    """Seed the database with test cameras.

    Args:
        count: Number of cameras to create (1-6)
        create_folders: Whether to create corresponding folders

    Returns:
        Number of cameras created.
    """
    if count < 1 or count > len(SAMPLE_CAMERAS):
        print(f"Error: count must be between 1 and {len(SAMPLE_CAMERAS)}")
        return 0

    cameras_to_create = SAMPLE_CAMERAS[:count]
    created_count = 0

    async with get_session() as session:
        for camera_data in cameras_to_create:
            # Check if camera already exists
            result = await session.execute(select(Camera).where(Camera.id == camera_data["id"]))
            existing = result.scalar_one_or_none()

            if existing:
                print(
                    f"Camera '{camera_data['name']}' ({camera_data['id']}) already exists, skipping"
                )
                continue

            # Create camera folder if requested
            if create_folders:
                folder_path = Path(camera_data["folder_path"])
                if not folder_path.exists():
                    try:
                        folder_path.mkdir(parents=True, exist_ok=True)
                        print(f"Created folder: {folder_path}")
                    except OSError as e:
                        print(f"Warning: Could not create folder {folder_path}: {e}")
                        print("Continuing with database entry...")

            # Create camera in database
            camera = Camera(
                id=camera_data["id"],
                name=camera_data["name"],
                folder_path=camera_data["folder_path"],
                status=camera_data["status"],
            )
            session.add(camera)
            created_count += 1
            print(f"Added camera: {camera.name} ({camera.id}) - {camera.status}")

        await session.commit()

    return created_count


async def list_cameras() -> None:
    """List all cameras in the database."""
    async with get_session() as session:
        result = await session.execute(select(Camera).order_by(Camera.name))
        cameras = result.scalars().all()

        if not cameras:
            print("No cameras in database")
            return

        print(f"\nFound {len(cameras)} cameras:")
        print("-" * 80)
        for camera in cameras:
            folder_exists = Path(camera.folder_path).exists()
            folder_status = "✓" if folder_exists else "✗"
            print(
                f"{folder_status} {camera.name:20} | {camera.id:20} | {camera.status:10} | {camera.folder_path}"
            )
        print("-" * 80)


async def main() -> int:
    """Main entry point for the seed script."""
    parser = argparse.ArgumentParser(
        description="Seed the database with test cameras for development"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove all cameras before seeding",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=6,
        help=f"Number of cameras to create (1-{len(SAMPLE_CAMERAS)}, default: 6)",
    )
    parser.add_argument(
        "--no-folders",
        action="store_true",
        help="Don't create camera folders on filesystem",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all cameras in the database and exit",
    )

    args = parser.parse_args()

    # Initialize database
    print("Initializing database...")
    await init_db()

    # List cameras if requested
    if args.list:
        await list_cameras()
        return 0

    # Clear existing cameras if requested
    if args.clear:
        await clear_cameras()

    # Seed cameras
    print(f"\nSeeding {args.count} cameras...")
    created = await seed_cameras(count=args.count, create_folders=not args.no_folders)

    if created > 0:
        print(f"\nSuccessfully created {created} cameras")
    else:
        print("\nNo cameras were created (they may already exist)")

    # List final state
    await list_cameras()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
