"""Integration tests for CameraRepository.

Tests follow TDD approach - these tests are written BEFORE the implementation.
Run with: uv run pytest backend/tests/integration/repositories/test_camera_repository.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.models import Camera
from backend.repositories.camera_repository import CameraRepository
from backend.tests.conftest import unique_id


@pytest.fixture
def camera_repo(test_db):
    """Create a CameraRepository instance with a test session."""

    async def _get_repo():
        async with test_db() as session:
            return CameraRepository(session), session

    return _get_repo


class TestCameraRepositoryBasicCRUD:
    """Test basic CRUD operations inherited from Repository base class."""

    @pytest.mark.asyncio
    async def test_create_camera(self, test_db):
        """Test creating a new camera."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            camera = Camera(
                id=camera_id,
                name="Front Door Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )

            created = await repo.create(camera)

            assert created.id == camera_id
            assert created.name == "Front Door Camera"
            assert created.status == "online"
            assert created.created_at is not None

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, test_db):
        """Test retrieving an existing camera by ID."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            # Create camera first
            camera = Camera(
                id=camera_id,
                name="Back Yard Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            await repo.create(camera)

            # Retrieve by ID
            retrieved = await repo.get_by_id(camera_id)

            assert retrieved is not None
            assert retrieved.id == camera_id
            assert retrieved.name == "Back Yard Camera"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, test_db):
        """Test retrieving a non-existent camera returns None."""
        async with test_db() as session:
            repo = CameraRepository(session)

            result = await repo.get_by_id("nonexistent_camera")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_all_cameras(self, test_db):
        """Test retrieving all cameras."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Create multiple cameras
            camera1 = Camera(
                id=unique_id("camera1"),
                name="Camera 1",
                folder_path=f"/export/foscam/{unique_id('path1')}",
            )
            camera2 = Camera(
                id=unique_id("camera2"),
                name="Camera 2",
                folder_path=f"/export/foscam/{unique_id('path2')}",
            )
            await repo.create(camera1)
            await repo.create(camera2)

            # Get all
            all_cameras = await repo.get_all()

            # Should have at least the 2 we created
            camera_ids = [c.id for c in all_cameras]
            assert camera1.id in camera_ids
            assert camera2.id in camera_ids

    @pytest.mark.asyncio
    async def test_update_camera(self, test_db):
        """Test updating a camera's properties."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            # Create camera
            camera = Camera(
                id=camera_id,
                name="Original Name",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            await repo.create(camera)

            # Update
            camera.name = "Updated Name"
            camera.status = "offline"
            updated = await repo.update(camera)

            assert updated.name == "Updated Name"
            assert updated.status == "offline"

            # Verify persistence
            retrieved = await repo.get_by_id(camera_id)
            assert retrieved.name == "Updated Name"
            assert retrieved.status == "offline"

    @pytest.mark.asyncio
    async def test_delete_camera(self, test_db):
        """Test deleting a camera."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            # Create camera
            camera = Camera(
                id=camera_id,
                name="To Delete",
                folder_path=f"/export/foscam/{camera_id}",
            )
            await repo.create(camera)

            # Delete
            await repo.delete(camera)

            # Verify deleted
            result = await repo.get_by_id(camera_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_by_id(self, test_db):
        """Test deleting a camera by ID."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            # Create camera
            camera = Camera(
                id=camera_id,
                name="To Delete",
                folder_path=f"/export/foscam/{camera_id}",
            )
            await repo.create(camera)

            # Delete by ID
            deleted = await repo.delete_by_id(camera_id)

            assert deleted is True

            # Verify deleted
            result = await repo.get_by_id(camera_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(self, test_db):
        """Test delete_by_id returns False for non-existent camera."""
        async with test_db() as session:
            repo = CameraRepository(session)

            deleted = await repo.delete_by_id("nonexistent")

            assert deleted is False

    @pytest.mark.asyncio
    async def test_exists(self, test_db):
        """Test checking if a camera exists."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            # Create camera
            camera = Camera(
                id=camera_id,
                name="Existing Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )
            await repo.create(camera)

            # Check existence
            assert await repo.exists(camera_id) is True
            assert await repo.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_count(self, test_db):
        """Test counting cameras."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Get initial count
            initial_count = await repo.count()

            # Create cameras
            for i in range(3):
                camera = Camera(
                    id=unique_id(f"camera{i}"),
                    name=f"Camera {i}",
                    folder_path=f"/export/foscam/{unique_id(f'path{i}')}",
                )
                await repo.create(camera)

            # Verify count increased
            new_count = await repo.count()
            assert new_count == initial_count + 3


class TestCameraRepositorySpecificMethods:
    """Test camera-specific repository methods."""

    @pytest.mark.asyncio
    async def test_get_by_folder_path(self, test_db):
        """Test finding a camera by its folder path."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")
            folder_path = f"/export/foscam/{camera_id}"

            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=folder_path,
            )
            await repo.create(camera)

            # Find by folder path
            found = await repo.get_by_folder_path(folder_path)

            assert found is not None
            assert found.id == camera_id
            assert found.folder_path == folder_path

    @pytest.mark.asyncio
    async def test_get_by_folder_path_not_found(self, test_db):
        """Test get_by_folder_path returns None for non-existent path."""
        async with test_db() as session:
            repo = CameraRepository(session)

            result = await repo.get_by_folder_path("/nonexistent/path")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name(self, test_db):
        """Test finding a camera by its display name."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")
            name = f"Unique Camera Name {camera_id}"

            camera = Camera(
                id=camera_id,
                name=name,
                folder_path=f"/export/foscam/{camera_id}",
            )
            await repo.create(camera)

            # Find by name
            found = await repo.get_by_name(name)

            assert found is not None
            assert found.id == camera_id
            assert found.name == name

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, test_db):
        """Test get_by_name returns None for non-existent name."""
        async with test_db() as session:
            repo = CameraRepository(session)

            result = await repo.get_by_name("Nonexistent Camera Name")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_online_cameras(self, test_db):
        """Test getting all cameras with status='online'."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Create online and offline cameras
            online1 = Camera(
                id=unique_id("online1"),
                name="Online 1",
                folder_path=f"/export/foscam/{unique_id('path1')}",
                status="online",
            )
            online2 = Camera(
                id=unique_id("online2"),
                name="Online 2",
                folder_path=f"/export/foscam/{unique_id('path2')}",
                status="online",
            )
            offline = Camera(
                id=unique_id("offline"),
                name="Offline Camera",
                folder_path=f"/export/foscam/{unique_id('path3')}",
                status="offline",
            )
            await repo.create(online1)
            await repo.create(online2)
            await repo.create(offline)

            # Get online cameras
            online_cameras = await repo.get_online_cameras()

            online_ids = [c.id for c in online_cameras]
            assert online1.id in online_ids
            assert online2.id in online_ids
            assert offline.id not in online_ids

    @pytest.mark.asyncio
    async def test_get_by_status(self, test_db):
        """Test filtering cameras by arbitrary status."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Create cameras with different statuses
            online = Camera(
                id=unique_id("online"),
                name="Online",
                folder_path=f"/export/foscam/{unique_id('online')}",
                status="online",
            )
            error = Camera(
                id=unique_id("error"),
                name="Error",
                folder_path=f"/export/foscam/{unique_id('error')}",
                status="error",
            )
            await repo.create(online)
            await repo.create(error)

            # Filter by status
            error_cameras = await repo.get_by_status("error")

            error_ids = [c.id for c in error_cameras]
            assert error.id in error_ids
            assert online.id not in error_ids

    @pytest.mark.asyncio
    async def test_update_last_seen(self, test_db):
        """Test updating a camera's last_seen_at timestamp."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                last_seen_at=None,
            )
            await repo.create(camera)

            # Update last seen
            updated = await repo.update_last_seen(camera_id)

            assert updated is not None
            assert updated.last_seen_at is not None
            # Check it's recent (within last minute)
            assert (datetime.now(UTC) - updated.last_seen_at).total_seconds() < 60

    @pytest.mark.asyncio
    async def test_update_last_seen_not_found(self, test_db):
        """Test update_last_seen returns None for non-existent camera."""
        async with test_db() as session:
            repo = CameraRepository(session)

            result = await repo.update_last_seen("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_set_status(self, test_db):
        """Test setting a camera's status."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            await repo.create(camera)

            # Set status
            updated = await repo.set_status(camera_id, "offline")

            assert updated is not None
            assert updated.status == "offline"

            # Verify persistence
            retrieved = await repo.get_by_id(camera_id)
            assert retrieved.status == "offline"

    @pytest.mark.asyncio
    async def test_set_status_not_found(self, test_db):
        """Test set_status returns None for non-existent camera."""
        async with test_db() as session:
            repo = CameraRepository(session)

            result = await repo.set_status("nonexistent", "offline")

            assert result is None


class TestCameraRepositoryPagination:
    """Test pagination operations from Repository base class."""

    @pytest.mark.asyncio
    async def test_list_paginated_default(self, test_db):
        """Test list_paginated with default parameters."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Create cameras
            for i in range(5):
                camera = Camera(
                    id=unique_id(f"camera{i}"),
                    name=f"Camera {i}",
                    folder_path=f"/export/foscam/{unique_id(f'path{i}')}",
                )
                await repo.create(camera)

            # Get paginated (default limit=100, skip=0)
            cameras = await repo.list_paginated()

            # Should have at least our 5 cameras
            assert len(cameras) >= 5

    @pytest.mark.asyncio
    async def test_list_paginated_with_limit(self, test_db):
        """Test list_paginated respects limit parameter."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Create cameras
            for i in range(10):
                camera = Camera(
                    id=unique_id(f"camera{i}"),
                    name=f"Camera {i}",
                    folder_path=f"/export/foscam/{unique_id(f'path{i}')}",
                )
                await repo.create(camera)

            # Get with limit
            cameras = await repo.list_paginated(limit=3)

            assert len(cameras) == 3

    @pytest.mark.asyncio
    async def test_list_paginated_with_skip(self, test_db):
        """Test list_paginated respects skip parameter."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Get initial count to know how many exist
            initial_count = await repo.count()

            # Create cameras in known order
            created_ids = []
            for i in range(5):
                camera = Camera(
                    id=unique_id(f"camera{i}"),
                    name=f"Camera {i}",
                    folder_path=f"/export/foscam/{unique_id(f'path{i}')}",
                )
                await repo.create(camera)
                created_ids.append(camera.id)

            # Skip past initial cameras and our first 2
            cameras = await repo.list_paginated(skip=initial_count + 2, limit=10)

            # Should have at most 3 (5 created - 2 skipped)
            assert len(cameras) <= 3

    @pytest.mark.asyncio
    async def test_list_paginated_empty_result(self, test_db):
        """Test list_paginated with skip beyond data returns empty."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Skip past all possible data
            cameras = await repo.list_paginated(skip=999999)

            assert len(cameras) == 0


class TestCameraRepositoryMerge:
    """Test merge operation for detached entities."""

    @pytest.mark.asyncio
    async def test_merge_detached_entity(self, test_db):
        """Test merging a detached entity back into session."""
        camera_id = unique_id("camera")

        # Create camera in one session
        async with test_db() as session:
            repo = CameraRepository(session)
            camera = Camera(
                id=camera_id,
                name="Original Name",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            await repo.create(camera)

        # Now camera is detached - modify and merge in new session
        async with test_db() as session:
            repo = CameraRepository(session)

            # Create a new instance with same ID (simulating detached entity)
            detached = Camera(
                id=camera_id,
                name="Updated via Merge",
                folder_path=f"/export/foscam/{camera_id}",
                status="offline",
            )

            merged = await repo.merge(detached)

            assert merged.id == camera_id
            assert merged.name == "Updated via Merge"
            assert merged.status == "offline"

        # Verify persistence in another session
        async with test_db() as session:
            repo = CameraRepository(session)
            retrieved = await repo.get_by_id(camera_id)

            assert retrieved.name == "Updated via Merge"
            assert retrieved.status == "offline"


class TestCameraRepositorySave:
    """Test save (upsert) operation from Repository base class."""

    @pytest.mark.asyncio
    async def test_save_creates_new_entity(self, test_db):
        """Test save creates a new entity when it doesn't exist."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            camera = Camera(
                id=camera_id,
                name="New Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )

            saved = await repo.save(camera)

            assert saved.id == camera_id
            assert saved.name == "New Camera"

            # Verify it was created
            retrieved = await repo.get_by_id(camera_id)
            assert retrieved is not None

    @pytest.mark.asyncio
    async def test_save_updates_existing_entity(self, test_db):
        """Test save updates an existing entity."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            # Create initial entity
            camera = Camera(
                id=camera_id,
                name="Original Name",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            await repo.create(camera)

        # Save with updated values in new session
        async with test_db() as session:
            repo = CameraRepository(session)

            updated_camera = Camera(
                id=camera_id,
                name="Updated Name",
                folder_path=f"/export/foscam/{camera_id}",
                status="offline",
            )

            saved = await repo.save(updated_camera)

            assert saved.id == camera_id
            assert saved.name == "Updated Name"
            assert saved.status == "offline"

        # Verify persistence
        async with test_db() as session:
            repo = CameraRepository(session)
            retrieved = await repo.get_by_id(camera_id)

            assert retrieved.name == "Updated Name"
            assert retrieved.status == "offline"

    @pytest.mark.asyncio
    async def test_save_with_none_id_creates(self, test_db):
        """Test save with None ID creates new entity."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Camera with explicit ID (since Camera requires ID)
            camera_id = unique_id("camera")
            camera = Camera(
                id=camera_id,
                name="New Camera",
                folder_path=f"/export/foscam/{camera_id}",
            )

            # First check it doesn't exist
            assert await repo.exists(camera_id) is False

            saved = await repo.save(camera)

            assert saved.id == camera_id
            assert await repo.exists(camera_id) is True


class TestCameraRepositoryGetMany:
    """Test get_many batch retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_many(self, test_db):
        """Test retrieving multiple cameras by IDs."""
        async with test_db() as session:
            repo = CameraRepository(session)

            # Create cameras
            camera1 = Camera(
                id=unique_id("camera1"),
                name="Camera 1",
                folder_path=f"/export/foscam/{unique_id('path1')}",
            )
            camera2 = Camera(
                id=unique_id("camera2"),
                name="Camera 2",
                folder_path=f"/export/foscam/{unique_id('path2')}",
            )
            camera3 = Camera(
                id=unique_id("camera3"),
                name="Camera 3",
                folder_path=f"/export/foscam/{unique_id('path3')}",
            )
            await repo.create(camera1)
            await repo.create(camera2)
            await repo.create(camera3)

            # Get multiple
            cameras = await repo.get_many([camera1.id, camera3.id])

            camera_ids = [c.id for c in cameras]
            assert camera1.id in camera_ids
            assert camera3.id in camera_ids
            assert camera2.id not in camera_ids

    @pytest.mark.asyncio
    async def test_get_many_empty_list(self, test_db):
        """Test get_many with empty list returns empty sequence."""
        async with test_db() as session:
            repo = CameraRepository(session)

            cameras = await repo.get_many([])

            assert len(cameras) == 0

    @pytest.mark.asyncio
    async def test_get_many_partial_match(self, test_db):
        """Test get_many returns only existing cameras."""
        async with test_db() as session:
            repo = CameraRepository(session)
            camera_id = unique_id("camera")

            camera = Camera(
                id=camera_id,
                name="Existing",
                folder_path=f"/export/foscam/{camera_id}",
            )
            await repo.create(camera)

            # Request mix of existing and non-existing
            cameras = await repo.get_many([camera_id, "nonexistent1", "nonexistent2"])

            assert len(cameras) == 1
            assert cameras[0].id == camera_id
