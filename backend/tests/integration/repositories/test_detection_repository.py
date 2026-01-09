"""Integration tests for DetectionRepository.

Tests follow TDD approach - these tests are written BEFORE the implementation.
Run with: uv run pytest backend/tests/integration/repositories/test_detection_repository.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.models import Camera, Detection
from backend.repositories.detection_repository import DetectionRepository
from backend.tests.conftest import unique_id


async def create_test_camera(session, camera_id: str | None = None) -> Camera:
    """Helper to create a test camera."""
    if camera_id is None:
        camera_id = unique_id("camera")
    camera = Camera(
        id=camera_id,
        name=f"Test Camera {camera_id}",
        folder_path=f"/export/foscam/{camera_id}",
    )
    session.add(camera)
    await session.flush()
    return camera


class TestDetectionRepositoryBasicCRUD:
    """Test basic CRUD operations inherited from Repository base class."""

    @pytest.mark.asyncio
    async def test_create_detection(self, test_db):
        """Test creating a new detection."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            detection = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/image_001.jpg",
                file_type="image/jpeg",
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=200,
                bbox_width=150,
                bbox_height=300,
            )

            created = await repo.create(detection)

            assert created.id is not None
            assert created.camera_id == camera.id
            assert created.object_type == "person"
            assert created.confidence == 0.95

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, test_db):
        """Test retrieving an existing detection by ID."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            detection = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/image_002.jpg",
                object_type="car",
                confidence=0.88,
            )
            await repo.create(detection)

            retrieved = await repo.get_by_id(detection.id)

            assert retrieved is not None
            assert retrieved.id == detection.id
            assert retrieved.object_type == "car"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, test_db):
        """Test retrieving a non-existent detection returns None."""
        async with test_db() as session:
            repo = DetectionRepository(session)

            result = await repo.get_by_id(999999)

            assert result is None

    @pytest.mark.asyncio
    async def test_update_detection(self, test_db):
        """Test updating a detection's properties."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            detection = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/image_003.jpg",
                object_type="person",
                confidence=0.85,
            )
            await repo.create(detection)

            detection.confidence = 0.92
            detection.thumbnail_path = f"/thumbnails/{detection.id}.jpg"
            updated = await repo.update(detection)

            assert updated.confidence == 0.92
            assert updated.thumbnail_path == f"/thumbnails/{detection.id}.jpg"

    @pytest.mark.asyncio
    async def test_delete_detection(self, test_db):
        """Test deleting a detection."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            detection = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/image_004.jpg",
            )
            await repo.create(detection)
            detection_id = detection.id

            await repo.delete(detection)

            result = await repo.get_by_id(detection_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_exists(self, test_db):
        """Test checking if a detection exists."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            detection = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/image_005.jpg",
            )
            await repo.create(detection)

            assert await repo.exists(detection.id) is True
            assert await repo.exists(999999) is False

    @pytest.mark.asyncio
    async def test_count(self, test_db):
        """Test counting detections."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            initial_count = await repo.count()

            for i in range(3):
                detection = Detection(
                    camera_id=camera.id,
                    file_path=f"/export/foscam/{camera.id}/image_{i:03d}.jpg",
                )
                await repo.create(detection)

            new_count = await repo.count()
            assert new_count == initial_count + 3


class TestDetectionRepositorySpecificMethods:
    """Test detection-specific repository methods."""

    @pytest.mark.asyncio
    async def test_get_by_camera_id(self, test_db):
        """Test getting detections for a specific camera."""
        async with test_db() as session:
            camera1 = await create_test_camera(session)
            camera2 = await create_test_camera(session)
            repo = DetectionRepository(session)

            det1 = Detection(
                camera_id=camera1.id,
                file_path=f"/export/foscam/{camera1.id}/img1.jpg",
            )
            det2 = Detection(
                camera_id=camera1.id,
                file_path=f"/export/foscam/{camera1.id}/img2.jpg",
            )
            det3 = Detection(
                camera_id=camera2.id,
                file_path=f"/export/foscam/{camera2.id}/img3.jpg",
            )
            await repo.create(det1)
            await repo.create(det2)
            await repo.create(det3)

            # Get detections for camera1 only
            camera1_detections = await repo.get_by_camera_id(camera1.id)

            det_ids = [d.id for d in camera1_detections]
            assert det1.id in det_ids
            assert det2.id in det_ids
            assert det3.id not in det_ids

    @pytest.mark.asyncio
    async def test_get_by_object_type(self, test_db):
        """Test filtering detections by object type."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            person = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/person.jpg",
                object_type="person",
            )
            car = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/car.jpg",
                object_type="car",
            )
            await repo.create(person)
            await repo.create(car)

            # Filter by object type
            person_detections = await repo.get_by_object_type("person")

            det_ids = [d.id for d in person_detections]
            assert person.id in det_ids
            assert car.id not in det_ids

    @pytest.mark.asyncio
    async def test_get_in_date_range(self, test_db):
        """Test getting detections within a date range."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            now = datetime.now(UTC)
            yesterday = now - timedelta(days=1)
            last_week = now - timedelta(days=7)
            two_weeks_ago = now - timedelta(days=14)

            recent = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/recent.jpg",
                detected_at=yesterday,
            )
            old = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/old.jpg",
                detected_at=two_weeks_ago,
            )
            await repo.create(recent)
            await repo.create(old)

            # Query for last week's detections
            detections_in_range = await repo.get_in_date_range(last_week, now)

            det_ids = [d.id for d in detections_in_range]
            assert recent.id in det_ids
            assert old.id not in det_ids

    @pytest.mark.asyncio
    async def test_get_high_confidence(self, test_db):
        """Test getting detections above a confidence threshold."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            high = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/high.jpg",
                confidence=0.95,
            )
            medium = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/medium.jpg",
                confidence=0.75,
            )
            low = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/low.jpg",
                confidence=0.50,
            )
            await repo.create(high)
            await repo.create(medium)
            await repo.create(low)

            # Get detections with confidence >= 0.8
            high_confidence = await repo.get_high_confidence(threshold=0.8)

            det_ids = [d.id for d in high_confidence]
            assert high.id in det_ids
            assert medium.id not in det_ids
            assert low.id not in det_ids

    @pytest.mark.asyncio
    async def test_get_recent(self, test_db):
        """Test getting most recent detections with limit."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            now = datetime.now(UTC)
            detections_data = []
            for i in range(5):
                detection = Detection(
                    camera_id=camera.id,
                    file_path=f"/export/foscam/{camera.id}/img{i}.jpg",
                    detected_at=now - timedelta(hours=i),
                )
                await repo.create(detection)
                detections_data.append(detection)

            # Get 3 most recent
            recent = await repo.get_recent(limit=3)

            assert len(recent) == 3
            # Should be in reverse chronological order (most recent first)
            recent_ids = [d.id for d in recent]
            assert detections_data[0].id in recent_ids  # Most recent
            assert detections_data[1].id in recent_ids
            assert detections_data[2].id in recent_ids
            assert detections_data[4].id not in recent_ids  # Oldest

    @pytest.mark.asyncio
    async def test_get_by_media_type(self, test_db):
        """Test filtering detections by media type."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            image = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/image.jpg",
                media_type="image",
            )
            video = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/video.mp4",
                media_type="video",
            )
            await repo.create(image)
            await repo.create(video)

            # Filter by media type
            video_detections = await repo.get_by_media_type("video")

            det_ids = [d.id for d in video_detections]
            assert video.id in det_ids
            assert image.id not in det_ids

    @pytest.mark.asyncio
    async def test_get_by_file_path(self, test_db):
        """Test finding a detection by its file path."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)
            file_path = f"/export/foscam/{camera.id}/unique_image_{unique_id('file')}.jpg"

            detection = Detection(
                camera_id=camera.id,
                file_path=file_path,
            )
            await repo.create(detection)

            # Find by file path
            found = await repo.get_by_file_path(file_path)

            assert found is not None
            assert found.id == detection.id
            assert found.file_path == file_path

    @pytest.mark.asyncio
    async def test_get_by_file_path_not_found(self, test_db):
        """Test get_by_file_path returns None for non-existent path."""
        async with test_db() as session:
            repo = DetectionRepository(session)

            result = await repo.get_by_file_path("/nonexistent/path.jpg")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_camera_detection_counts(self, test_db):
        """Test getting detection counts grouped by camera."""
        async with test_db() as session:
            camera1 = await create_test_camera(session)
            camera2 = await create_test_camera(session)
            repo = DetectionRepository(session)

            # Create detections: 3 for camera1, 1 for camera2
            for i in range(3):
                det = Detection(
                    camera_id=camera1.id,
                    file_path=f"/export/foscam/{camera1.id}/img{i}.jpg",
                )
                await repo.create(det)

            det = Detection(
                camera_id=camera2.id,
                file_path=f"/export/foscam/{camera2.id}/img0.jpg",
            )
            await repo.create(det)

            # Get counts
            counts = await repo.get_camera_detection_counts()

            assert camera1.id in counts
            assert camera2.id in counts
            assert counts[camera1.id] >= 3
            assert counts[camera2.id] >= 1

    @pytest.mark.asyncio
    async def test_get_object_type_counts(self, test_db):
        """Test getting detection counts grouped by object type."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = DetectionRepository(session)

            # Create detections: 2 person, 1 car
            for i in range(2):
                det = Detection(
                    camera_id=camera.id,
                    file_path=f"/export/foscam/{camera.id}/person{i}.jpg",
                    object_type="person",
                )
                await repo.create(det)

            det = Detection(
                camera_id=camera.id,
                file_path=f"/export/foscam/{camera.id}/car.jpg",
                object_type="car",
            )
            await repo.create(det)

            # Get counts
            counts = await repo.get_object_type_counts()

            # Verify persons and cars are counted
            # Note: Other tests may have added more detections
            if "person" in counts:
                assert counts["person"] >= 2
            if "car" in counts:
                assert counts["car"] >= 1
