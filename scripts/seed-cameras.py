#!/usr/bin/env python3
"""Seed the database with cameras from filesystem or config.

Usage:
    # Auto-discover cameras from /export/foscam (default)
    uv run python scripts/seed-cameras.py --discover

    # Auto-discover from custom path
    uv run python scripts/seed-cameras.py --discover /path/to/cameras

    # Use sample cameras (for testing)
    uv run python scripts/seed-cameras.py --count 6

    # List current cameras
    uv run python scripts/seed-cameras.py --list

    # Clear and re-seed from filesystem
    uv run python scripts/seed-cameras.py --clear --discover
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import get_session, init_db
from backend.models.camera import Camera, normalize_camera_id
from sqlalchemy import delete, select

# Default base path for Foscam cameras
DEFAULT_FOSCAM_PATH = "/export/foscam"

# Sample camera configurations (for testing when no real cameras available)
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


def _directory_has_images(folder: Path) -> bool:
    """Check if a directory contains any image files (recursively).

    Args:
        folder: Path to the camera directory

    Returns:
        True if directory contains at least one image file
    """
    image_patterns = ["*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG"]
    return any(any(folder.rglob(pattern)) for pattern in image_patterns)


def discover_cameras(base_path: str, include_empty: bool = False) -> list[dict]:
    """Discover camera directories from filesystem.

    Args:
        base_path: Root directory containing camera subdirectories
        include_empty: If False (default), skip directories without images

    Returns:
        List of camera configurations discovered from filesystem
    """
    base = Path(base_path)
    if not base.exists():
        print(f"Warning: Base path {base_path} does not exist")
        return []

    cameras = []
    skipped = 0
    for folder in sorted(base.iterdir()):
        if folder.is_dir() and not folder.name.startswith("."):
            # Skip empty directories unless explicitly included
            if not include_empty and not _directory_has_images(folder):
                print(f"Skipping empty directory: {folder.name}")
                skipped += 1
                continue

            # Normalize ID from folder name
            camera_id = normalize_camera_id(folder.name)
            # Create display name (replace underscores with spaces, title case)
            display_name = folder.name.replace("_", " ").title()

            cameras.append(
                {
                    "id": camera_id,
                    "name": display_name,
                    "folder_path": str(folder),
                    "status": "online",
                }
            )
            print(f"Discovered: {folder.name} -> {camera_id}")

    if skipped > 0:
        print(f"Skipped {skipped} empty directories")

    return cameras


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


async def seed_cameras_from_list(
    cameras_to_create: list[dict], create_folders: bool = False
) -> int:
    """Seed the database with cameras from a list.

    Args:
        cameras_to_create: List of camera config dicts
        create_folders: Whether to create corresponding folders

    Returns:
        Number of cameras created.
    """
    if not cameras_to_create:
        print("No cameras to create")
        return 0

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


async def seed_cameras(count: int, create_folders: bool = True) -> int:
    """Seed the database with sample test cameras.

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
    return await seed_cameras_from_list(cameras_to_create, create_folders)


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
        description="Seed the database with cameras from filesystem or samples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-discover cameras from /export/foscam
  uv run python scripts/seed-cameras.py --discover

  # Auto-discover from custom path
  uv run python scripts/seed-cameras.py --discover /mnt/cameras

  # Clear and re-seed from filesystem
  uv run python scripts/seed-cameras.py --clear --discover

  # Use sample cameras (for testing)
  uv run python scripts/seed-cameras.py --count 6

  # List current cameras
  uv run python scripts/seed-cameras.py --list
""",
    )
    parser.add_argument(
        "--discover",
        nargs="?",
        const=DEFAULT_FOSCAM_PATH,
        metavar="PATH",
        help=f"Discover cameras from filesystem (default: {DEFAULT_FOSCAM_PATH})",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove all cameras before seeding",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help=f"Number of sample cameras to create (1-{len(SAMPLE_CAMERAS)})",
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
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Include directories without images when discovering cameras",
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
    if args.discover:
        # Auto-discover from filesystem
        print(f"\nDiscovering cameras from {args.discover}...")
        discovered = discover_cameras(args.discover, include_empty=args.include_empty)
        if discovered:
            created = await seed_cameras_from_list(discovered, create_folders=False)
            if created > 0:
                print(f"\nSuccessfully created {created} cameras from filesystem")
            else:
                print("\nNo cameras were created (they may already exist)")
        else:
            print(f"\nNo camera directories found in {args.discover}")
    elif args.count:
        # Use sample cameras
        print(f"\nSeeding {args.count} sample cameras...")
        created = await seed_cameras(count=args.count, create_folders=not args.no_folders)
        if created > 0:
            print(f"\nSuccessfully created {created} cameras")
        else:
            print("\nNo cameras were created (they may already exist)")
    elif not args.clear:
        # No action specified
        print("\nNo action specified. Use --discover, --count, or --list")
        parser.print_help()
        return 1

    # List final state
    await list_cameras()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
