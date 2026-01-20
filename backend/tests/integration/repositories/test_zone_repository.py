"""Integration tests for ZoneRepository.

Tests follow TDD approach covering CRUD operations, query methods with filters,
relationship loading, and error handling.

Run with: uv run pytest backend/tests/integration/repositories/test_zone_repository.py -v
"""

from __future__ import annotations

import pytest

from backend.models import Camera, CameraZone, CameraZoneShape, CameraZoneType
from backend.repositories.zone_repository import ZoneRepository
from backend.tests.conftest import unique_id

# Aliases for backward compatibility
Zone = CameraZone
ZoneShape = CameraZoneShape
ZoneType = CameraZoneType


@pytest.fixture
def zone_repo(test_db):
    """Create a ZoneRepository instance with a test session."""

    async def _get_repo():
        async with test_db() as session:
            return ZoneRepository(session), session

    return _get_repo


class TestZoneRepositoryBasicCRUD:
    """Test basic CRUD operations inherited from Repository base class."""

    @pytest.mark.asyncio
    async def test_create_zone(self, test_db):
        """Test creating a new zone."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera first
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zone
            zone_id = unique_id("zone")
            zone = Zone(
                id=zone_id,
                camera_id=camera.id,
                name="Front Driveway",
                zone_type=ZoneType.DRIVEWAY,
                coordinates=[[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
                shape=ZoneShape.RECTANGLE,
                enabled=True,
                priority=10,
            )

            created = await repo.create(zone)

            assert created.id == zone_id
            assert created.name == "Front Driveway"
            assert created.zone_type == ZoneType.DRIVEWAY
            assert created.enabled is True
            assert created.priority == 10
            assert created.created_at is not None

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, test_db):
        """Test retrieving an existing zone by ID."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zone
            zone_id = unique_id("zone")
            zone = Zone(
                id=zone_id,
                camera_id=camera.id,
                name="Entry Point",
                zone_type=ZoneType.ENTRY_POINT,
                coordinates=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            )
            await repo.create(zone)

            # Retrieve by ID
            retrieved = await repo.get_by_id(zone_id)

            assert retrieved is not None
            assert retrieved.id == zone_id
            assert retrieved.name == "Entry Point"
            assert retrieved.zone_type == ZoneType.ENTRY_POINT

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, test_db):
        """Test retrieving a non-existent zone returns None."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            result = await repo.get_by_id("nonexistent_zone")

            assert result is None

    @pytest.mark.asyncio
    async def test_update_zone(self, test_db):
        """Test updating a zone's properties."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zone
            zone_id = unique_id("zone")
            zone = Zone(
                id=zone_id,
                camera_id=camera.id,
                name="Original Name",
                zone_type=ZoneType.YARD,
                coordinates=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
                enabled=True,
                priority=5,
            )
            await repo.create(zone)

            # Update
            zone.name = "Updated Name"
            zone.zone_type = ZoneType.SIDEWALK
            zone.priority = 15
            updated = await repo.update(zone)

            assert updated.name == "Updated Name"
            assert updated.zone_type == ZoneType.SIDEWALK
            assert updated.priority == 15

            # Verify persistence
            retrieved = await repo.get_by_id(zone_id)
            assert retrieved.name == "Updated Name"
            assert retrieved.zone_type == ZoneType.SIDEWALK
            assert retrieved.priority == 15

    @pytest.mark.asyncio
    async def test_delete_zone(self, test_db):
        """Test deleting a zone."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zone
            zone_id = unique_id("zone")
            zone = Zone(
                id=zone_id,
                camera_id=camera.id,
                name="To Delete",
                zone_type=ZoneType.OTHER,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            await repo.create(zone)

            # Delete
            await repo.delete(zone)

            # Verify deleted
            result = await repo.get_by_id(zone_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_count_zones(self, test_db):
        """Test counting zones."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Get initial count
            initial_count = await repo.count()

            # Create zones
            for i in range(3):
                zone = Zone(
                    id=unique_id(f"zone{i}"),
                    camera_id=camera.id,
                    name=f"Zone {i}",
                    zone_type=ZoneType.YARD,
                    coordinates=[[0.0, 0.0], [1.0, 1.0]],
                )
                await repo.create(zone)

            # Verify count increased
            new_count = await repo.count()
            assert new_count == initial_count + 3


class TestZoneRepositorySpecificMethods:
    """Test zone-specific repository methods."""

    @pytest.mark.asyncio
    async def test_get_by_camera_id(self, test_db):
        """Test getting all zones for a specific camera."""
        async with test_db() as session:
            repo = ZoneRepository(session)

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
            session.add(camera1)
            session.add(camera2)
            await session.flush()

            # Create zones for different cameras
            zone1 = Zone(
                id=unique_id("zone1"),
                camera_id=camera1.id,
                name="Zone 1",
                zone_type=ZoneType.DRIVEWAY,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                priority=10,
            )
            zone2 = Zone(
                id=unique_id("zone2"),
                camera_id=camera1.id,
                name="Zone 2",
                zone_type=ZoneType.ENTRY_POINT,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                priority=20,
            )
            zone3 = Zone(
                id=unique_id("zone3"),
                camera_id=camera2.id,
                name="Zone 3",
                zone_type=ZoneType.YARD,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            await repo.create(zone1)
            await repo.create(zone2)
            await repo.create(zone3)

            # Get zones for camera1
            zones = await repo.get_by_camera_id(camera1.id)

            zone_ids = [z.id for z in zones]
            assert zone1.id in zone_ids
            assert zone2.id in zone_ids
            assert zone3.id not in zone_ids

            # Verify ordering by priority (descending)
            assert zones[0].id == zone2.id  # priority 20
            assert zones[1].id == zone1.id  # priority 10

    @pytest.mark.asyncio
    async def test_get_by_name(self, test_db):
        """Test finding a zone by camera ID and name."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zone
            zone_name = f"Unique Zone {unique_id('name')}"
            zone = Zone(
                id=unique_id("zone"),
                camera_id=camera.id,
                name=zone_name,
                zone_type=ZoneType.ENTRY_POINT,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            await repo.create(zone)

            # Find by name
            found = await repo.get_by_name(camera.id, zone_name)

            assert found is not None
            assert found.name == zone_name
            assert found.camera_id == camera.id

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, test_db):
        """Test get_by_name returns None for non-existent name."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            result = await repo.get_by_name(camera.id, "Nonexistent Zone")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_enabled_zones(self, test_db):
        """Test getting only enabled zones for a camera."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create enabled and disabled zones
            enabled_zone = Zone(
                id=unique_id("enabled"),
                camera_id=camera.id,
                name="Enabled Zone",
                zone_type=ZoneType.DRIVEWAY,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                enabled=True,
            )
            disabled_zone = Zone(
                id=unique_id("disabled"),
                camera_id=camera.id,
                name="Disabled Zone",
                zone_type=ZoneType.YARD,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                enabled=False,
            )
            await repo.create(enabled_zone)
            await repo.create(disabled_zone)

            # Get enabled zones
            zones = await repo.get_enabled_zones(camera.id)

            zone_ids = [z.id for z in zones]
            assert enabled_zone.id in zone_ids
            assert disabled_zone.id not in zone_ids

    @pytest.mark.asyncio
    async def test_get_by_type(self, test_db):
        """Test getting zones by type."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zones with different types
            driveway = Zone(
                id=unique_id("driveway"),
                camera_id=camera.id,
                name="Driveway",
                zone_type=ZoneType.DRIVEWAY,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            entry = Zone(
                id=unique_id("entry"),
                camera_id=camera.id,
                name="Entry",
                zone_type=ZoneType.ENTRY_POINT,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            await repo.create(driveway)
            await repo.create(entry)

            # Get driveway zones
            driveway_zones = await repo.get_by_type(ZoneType.DRIVEWAY)

            zone_ids = [z.id for z in driveway_zones]
            assert driveway.id in zone_ids
            assert entry.id not in zone_ids

    @pytest.mark.asyncio
    async def test_set_enabled(self, test_db):
        """Test enabling/disabling a zone."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create enabled zone
            zone_id = unique_id("zone")
            zone = Zone(
                id=zone_id,
                camera_id=camera.id,
                name="Test Zone",
                zone_type=ZoneType.YARD,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                enabled=True,
            )
            await repo.create(zone)

            # Disable the zone
            updated = await repo.set_enabled(zone_id, False)

            assert updated is not None
            assert updated.enabled is False

            # Verify persistence
            retrieved = await repo.get_by_id(zone_id)
            assert retrieved.enabled is False

            # Re-enable the zone
            updated = await repo.set_enabled(zone_id, True)
            assert updated.enabled is True

    @pytest.mark.asyncio
    async def test_set_enabled_not_found(self, test_db):
        """Test set_enabled returns None for non-existent zone."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            result = await repo.set_enabled("nonexistent", True)

            assert result is None

    @pytest.mark.asyncio
    async def test_update_priority(self, test_db):
        """Test updating a zone's priority."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zone with initial priority
            zone_id = unique_id("zone")
            zone = Zone(
                id=zone_id,
                camera_id=camera.id,
                name="Test Zone",
                zone_type=ZoneType.DRIVEWAY,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                priority=10,
            )
            await repo.create(zone)

            # Update priority
            updated = await repo.update_priority(zone_id, 50)

            assert updated is not None
            assert updated.priority == 50

            # Verify persistence
            retrieved = await repo.get_by_id(zone_id)
            assert retrieved.priority == 50

    @pytest.mark.asyncio
    async def test_update_priority_not_found(self, test_db):
        """Test update_priority returns None for non-existent zone."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            result = await repo.update_priority("nonexistent", 10)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_by_camera_and_type(self, test_db):
        """Test getting zones by camera and type."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zones with different types
            driveway = Zone(
                id=unique_id("driveway"),
                camera_id=camera.id,
                name="Driveway",
                zone_type=ZoneType.DRIVEWAY,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            entry = Zone(
                id=unique_id("entry"),
                camera_id=camera.id,
                name="Entry",
                zone_type=ZoneType.ENTRY_POINT,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            await repo.create(driveway)
            await repo.create(entry)

            # Get driveway zones for this camera
            zones = await repo.get_by_camera_and_type(camera.id, ZoneType.DRIVEWAY)

            assert len(zones) == 1
            assert zones[0].id == driveway.id

    @pytest.mark.asyncio
    async def test_count_by_camera(self, test_db):
        """Test counting zones for a specific camera."""
        async with test_db() as session:
            repo = ZoneRepository(session)

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
            session.add(camera1)
            session.add(camera2)
            await session.flush()

            # Create zones for camera1
            for i in range(3):
                zone = Zone(
                    id=unique_id(f"zone{i}"),
                    camera_id=camera1.id,
                    name=f"Zone {i}",
                    zone_type=ZoneType.YARD,
                    coordinates=[[0.0, 0.0], [1.0, 1.0]],
                )
                await repo.create(zone)

            # Create one zone for camera2
            zone = Zone(
                id=unique_id("zone_cam2"),
                camera_id=camera2.id,
                name="Camera 2 Zone",
                zone_type=ZoneType.YARD,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            await repo.create(zone)

            # Count zones for camera1
            count = await repo.count_by_camera(camera1.id)
            assert count == 3

            # Count zones for camera2
            count = await repo.count_by_camera(camera2.id)
            assert count == 1

    @pytest.mark.asyncio
    async def test_exists_by_name(self, test_db):
        """Test checking if a zone exists by name."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zone
            zone = Zone(
                id=unique_id("zone"),
                camera_id=camera.id,
                name="Existing Zone",
                zone_type=ZoneType.DRIVEWAY,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            await repo.create(zone)

            # Check existence
            assert await repo.exists_by_name(camera.id, "Existing Zone") is True
            assert await repo.exists_by_name(camera.id, "Nonexistent") is False

    @pytest.mark.asyncio
    async def test_delete_by_camera_id(self, test_db):
        """Test deleting all zones for a camera."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create multiple zones
            for i in range(3):
                zone = Zone(
                    id=unique_id(f"zone{i}"),
                    camera_id=camera.id,
                    name=f"Zone {i}",
                    zone_type=ZoneType.YARD,
                    coordinates=[[0.0, 0.0], [1.0, 1.0]],
                )
                await repo.create(zone)

            # Delete all zones for camera
            deleted_count = await repo.delete_by_camera_id(camera.id)

            assert deleted_count == 3

            # Verify no zones remain
            remaining = await repo.get_by_camera_id(camera.id)
            assert len(remaining) == 0


class TestZoneRepositoryRelationshipLoading:
    """Test relationship loading for zones."""

    @pytest.mark.asyncio
    async def test_zone_loads_camera_relationship(self, test_db):
        """Test that zone properly loads its camera relationship."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zone
            zone_id = unique_id("zone")
            zone = Zone(
                id=zone_id,
                camera_id=camera.id,
                name="Test Zone",
                zone_type=ZoneType.ENTRY_POINT,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
            )
            await repo.create(zone)

            # Retrieve and access relationship
            retrieved = await repo.get_by_id(zone_id)
            assert retrieved is not None

            # Access camera relationship (should be loaded)
            assert retrieved.camera is not None
            assert retrieved.camera.id == camera.id
            assert retrieved.camera.name == "Test Camera"


class TestZoneRepositoryErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_get_by_camera_id_no_zones(self, test_db):
        """Test get_by_camera_id returns empty list when no zones exist."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera with no zones
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            zones = await repo.get_by_camera_id(camera.id)

            assert len(zones) == 0

    @pytest.mark.asyncio
    async def test_count_by_camera_no_zones(self, test_db):
        """Test count_by_camera returns 0 when no zones exist."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera with no zones
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            count = await repo.count_by_camera(camera.id)

            assert count == 0

    @pytest.mark.asyncio
    async def test_delete_by_camera_id_no_zones(self, test_db):
        """Test delete_by_camera_id returns 0 when no zones exist."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera with no zones
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            deleted_count = await repo.delete_by_camera_id(camera.id)

            assert deleted_count == 0


class TestZoneRepositoryPriorityOrdering:
    """Test zone priority ordering."""

    @pytest.mark.asyncio
    async def test_zones_ordered_by_priority_descending(self, test_db):
        """Test that zones are returned in priority order (high to low)."""
        async with test_db() as session:
            repo = ZoneRepository(session)

            # Create camera
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)
            await session.flush()

            # Create zones with different priorities
            low_priority = Zone(
                id=unique_id("low"),
                camera_id=camera.id,
                name="Low Priority",
                zone_type=ZoneType.YARD,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                priority=5,
            )
            high_priority = Zone(
                id=unique_id("high"),
                camera_id=camera.id,
                name="High Priority",
                zone_type=ZoneType.ENTRY_POINT,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                priority=20,
            )
            medium_priority = Zone(
                id=unique_id("medium"),
                camera_id=camera.id,
                name="Medium Priority",
                zone_type=ZoneType.DRIVEWAY,
                coordinates=[[0.0, 0.0], [1.0, 1.0]],
                priority=10,
            )
            # Create in random order
            await repo.create(low_priority)
            await repo.create(high_priority)
            await repo.create(medium_priority)

            # Get zones (should be ordered by priority descending)
            zones = await repo.get_by_camera_id(camera.id)

            assert len(zones) == 3
            assert zones[0].id == high_priority.id  # priority 20
            assert zones[1].id == medium_priority.id  # priority 10
            assert zones[2].id == low_priority.id  # priority 5
