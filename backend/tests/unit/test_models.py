"""Unit tests for SQLAlchemy database models.

Tests use PostgreSQL via the isolated_db fixture since models use
PostgreSQL-specific features like JSONB.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from backend.models import Camera, Detection, Event, GPUStats


@pytest.fixture
async def session(isolated_db):
    """Create a new database session for each test.

    Uses PostgreSQL via the isolated_db fixture from conftest.py.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        yield session


class TestCameraModel:
    """Tests for the Camera model."""

    @pytest.mark.asyncio
    async def test_create_camera(self, session):
        """Test creating a camera with required fields."""
        camera = Camera(
            id="front_door",
            name="Front Door Camera",
            folder_path="/export/foscam/front_door",
        )
        session.add(camera)
        await session.flush()

        assert camera.id == "front_door"
        assert camera.name == "Front Door Camera"
        assert camera.folder_path == "/export/foscam/front_door"
        assert camera.status == "online"
        assert isinstance(camera.created_at, datetime)
        assert camera.last_seen_at is None

    @pytest.mark.asyncio
    async def test_camera_default_status(self, session):
        """Test that camera status defaults to 'online'."""
        camera = Camera(
            id="garage",
            name="Garage Camera",
            folder_path="/export/foscam/garage",
        )
        session.add(camera)
        await session.flush()

        assert camera.status == "online"

    @pytest.mark.asyncio
    async def test_camera_custom_status(self, session):
        """Test creating a camera with custom status."""
        camera = Camera(
            id="backyard",
            name="Backyard Camera",
            folder_path="/export/foscam/backyard",
            status="offline",
        )
        session.add(camera)
        await session.flush()

        assert camera.status == "offline"

    @pytest.mark.asyncio
    async def test_camera_last_seen_update(self, session):
        """Test updating camera last_seen_at timestamp."""
        camera = Camera(
            id="driveway",
            name="Driveway Camera",
            folder_path="/export/foscam/driveway",
        )
        session.add(camera)
        await session.flush()

        now = datetime.utcnow()
        camera.last_seen_at = now
        await session.flush()

        assert camera.last_seen_at == now

    @pytest.mark.asyncio
    async def test_camera_repr(self, session):
        """Test camera string representation."""
        camera = Camera(
            id="side_gate",
            name="Side Gate Camera",
            folder_path="/export/foscam/side_gate",
        )
        session.add(camera)
        await session.flush()

        repr_str = repr(camera)

        assert "Camera" in repr_str
        assert "side_gate" in repr_str
        assert "Side Gate Camera" in repr_str
        assert "online" in repr_str

    @pytest.mark.asyncio
    async def test_query_camera_by_id(self, session):
        """Test querying camera by ID."""
        camera = Camera(
            id="test_cam",
            name="Test Camera",
            folder_path="/export/foscam/test",
        )
        session.add(camera)
        await session.flush()

        result = await session.get(Camera, "test_cam")
        assert result is not None
        assert result.id == "test_cam"
        assert result.name == "Test Camera"


class TestDetectionModel:
    """Tests for the Detection model."""

    @pytest.mark.asyncio
    async def test_create_detection(self, session):
        """Test creating a detection with required fields."""
        camera = Camera(
            id="front_door",
            name="Front Door Camera",
            folder_path="/export/foscam/front_door",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image_001.jpg",
        )
        session.add(detection)
        await session.flush()

        assert detection.id is not None
        assert detection.camera_id == "front_door"
        assert detection.file_path == "/export/foscam/front_door/image_001.jpg"
        assert isinstance(detection.detected_at, datetime)

    @pytest.mark.asyncio
    async def test_detection_with_bbox(self, session):
        """Test creating a detection with bounding box coordinates."""
        camera = Camera(
            id="garage",
            name="Garage Camera",
            folder_path="/export/foscam/garage",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id="garage",
            file_path="/export/foscam/garage/image_002.jpg",
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=300,
        )
        session.add(detection)
        await session.flush()

        assert detection.object_type == "person"
        assert detection.confidence == 0.95
        assert detection.bbox_x == 100
        assert detection.bbox_y == 150
        assert detection.bbox_width == 200
        assert detection.bbox_height == 300

    @pytest.mark.asyncio
    async def test_detection_camera_relationship(self, session):
        """Test the relationship between Detection and Camera."""
        camera = Camera(
            id="backyard",
            name="Backyard Camera",
            folder_path="/export/foscam/backyard",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id="backyard",
            file_path="/export/foscam/backyard/image_003.jpg",
            object_type="car",
        )
        session.add(detection)
        await session.flush()

        # Test forward relationship - need to refresh to load relationship
        await session.refresh(detection, ["camera"])
        assert detection.camera is not None
        assert detection.camera.id == "backyard"
        assert detection.camera.name == "Backyard Camera"

    @pytest.mark.asyncio
    async def test_detection_repr(self, session):
        """Test detection string representation."""
        camera = Camera(
            id="front_door",
            name="Front Door Camera",
            folder_path="/export/foscam/front_door",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image_001.jpg",
            object_type="person",
            confidence=0.89,
        )
        session.add(detection)
        await session.flush()

        repr_str = repr(detection)
        assert "Detection" in repr_str
        assert "front_door" in repr_str
        assert "person" in repr_str

    @pytest.mark.asyncio
    async def test_query_detections_by_camera(self, session):
        """Test querying all detections for a specific camera."""
        camera1 = Camera(
            id="cam1",
            name="Camera 1",
            folder_path="/export/foscam/cam1",
        )
        camera2 = Camera(
            id="cam2",
            name="Camera 2",
            folder_path="/export/foscam/cam2",
        )
        session.add_all([camera1, camera2])
        await session.flush()

        # Add detections to camera1
        for i in range(3):
            detection = Detection(
                camera_id="cam1",
                file_path=f"/export/foscam/cam1/image_{i:03d}.jpg",
            )
            session.add(detection)

        # Add detection to camera2
        detection = Detection(
            camera_id="cam2",
            file_path="/export/foscam/cam2/image_001.jpg",
        )
        session.add(detection)
        await session.flush()

        # Query detections for camera1
        stmt = select(Detection).where(Detection.camera_id == "cam1")
        result = await session.execute(stmt)
        results = result.scalars().all()

        assert len(results) == 3
        assert all(d.camera_id == "cam1" for d in results)


class TestEventModel:
    """Tests for the Event model."""

    @pytest.mark.asyncio
    async def test_create_event(self, session):
        """Test creating an event with required fields."""
        camera = Camera(
            id="front_door",
            name="Front Door Camera",
            folder_path="/export/foscam/front_door",
        )
        session.add(camera)
        await session.flush()

        now = datetime.utcnow()
        event = Event(
            batch_id="batch_001",
            camera_id="front_door",
            started_at=now,
        )
        session.add(event)
        await session.flush()

        assert event.id is not None
        assert event.batch_id == "batch_001"
        assert event.camera_id == "front_door"
        assert event.started_at == now
        assert event.reviewed is False

    @pytest.mark.asyncio
    async def test_event_with_risk_assessment(self, session):
        """Test creating an event with LLM risk assessment."""
        camera = Camera(
            id="backyard",
            name="Backyard Camera",
            folder_path="/export/foscam/backyard",
        )
        session.add(camera)
        await session.flush()

        now = datetime.utcnow()
        event = Event(
            batch_id="batch_002",
            camera_id="backyard",
            started_at=now,
            ended_at=now + timedelta(seconds=90),
            risk_score=75,
            risk_level="high",
            summary="Multiple persons detected near entrance",
            reasoning="Detected 3 persons approaching the door at night",
            detection_ids="1,2,3,4",
        )
        session.add(event)
        await session.flush()

        assert event.risk_score == 75
        assert event.risk_level == "high"
        assert event.summary == "Multiple persons detected near entrance"
        assert "3 persons" in event.reasoning
        assert event.detection_ids == "1,2,3,4"

    @pytest.mark.asyncio
    async def test_event_camera_relationship(self, session):
        """Test the relationship between Event and Camera."""
        camera = Camera(
            id="garage",
            name="Garage Camera",
            folder_path="/export/foscam/garage",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id="batch_003",
            camera_id="garage",
            started_at=datetime.utcnow(),
        )
        session.add(event)
        await session.flush()

        # Test forward relationship
        await session.refresh(event, ["camera"])
        assert event.camera is not None
        assert event.camera.id == "garage"
        assert event.camera.name == "Garage Camera"

    @pytest.mark.asyncio
    async def test_event_reviewed_flag(self, session):
        """Test event reviewed flag functionality."""
        camera = Camera(
            id="driveway",
            name="Driveway Camera",
            folder_path="/export/foscam/driveway",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id="batch_004",
            camera_id="driveway",
            started_at=datetime.utcnow(),
        )
        session.add(event)
        await session.flush()

        assert event.reviewed is False

        # Mark as reviewed
        event.reviewed = True
        event.notes = "False alarm - delivery driver"
        await session.flush()

        assert event.reviewed is True
        assert event.notes == "False alarm - delivery driver"

    @pytest.mark.asyncio
    async def test_event_repr(self, session):
        """Test event string representation."""
        camera = Camera(
            id="front_door",
            name="Front Door Camera",
            folder_path="/export/foscam/front_door",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id="batch_005",
            camera_id="front_door",
            started_at=datetime.utcnow(),
            risk_score=85,
        )
        session.add(event)
        await session.flush()

        repr_str = repr(event)
        assert "Event" in repr_str
        assert "batch_005" in repr_str
        assert "front_door" in repr_str
        assert "85" in repr_str

    @pytest.mark.asyncio
    async def test_query_high_risk_events(self, session):
        """Test querying events by risk score."""
        camera = Camera(
            id="test_cam",
            name="Test Camera",
            folder_path="/export/foscam/test",
        )
        session.add(camera)
        await session.flush()

        # Create events with different risk scores
        for i, score in enumerate([10, 45, 75, 90, 25]):
            event = Event(
                batch_id=f"batch_{i:03d}",
                camera_id="test_cam",
                started_at=datetime.utcnow(),
                risk_score=score,
            )
            session.add(event)
        await session.flush()

        # Query high risk events (score >= 70)
        stmt = select(Event).where(Event.risk_score >= 70)
        result = await session.execute(stmt)
        results = result.scalars().all()

        assert len(results) == 2
        assert all(e.risk_score >= 70 for e in results)


class TestGPUStatsModel:
    """Tests for the GPUStats model."""

    @pytest.mark.asyncio
    async def test_create_gpu_stats(self, session):
        """Test creating GPU stats with all fields."""
        stats = GPUStats(
            gpu_utilization=85.5,
            memory_used=16384,
            memory_total=24576,
            temperature=72.3,
            inference_fps=30.5,
        )
        session.add(stats)
        await session.flush()

        assert stats.id is not None
        assert isinstance(stats.recorded_at, datetime)
        assert stats.gpu_utilization == 85.5
        assert stats.memory_used == 16384
        assert stats.memory_total == 24576
        assert stats.temperature == 72.3
        assert stats.inference_fps == 30.5

    @pytest.mark.asyncio
    async def test_gpu_stats_partial_data(self, session):
        """Test creating GPU stats with partial data."""
        stats = GPUStats(
            gpu_utilization=45.0,
            temperature=68.5,
        )
        session.add(stats)
        await session.flush()

        assert stats.gpu_utilization == 45.0
        assert stats.temperature == 68.5
        assert stats.memory_used is None
        assert stats.memory_total is None
        assert stats.inference_fps is None

    @pytest.mark.asyncio
    async def test_gpu_stats_repr(self, session):
        """Test GPU stats string representation."""
        stats = GPUStats(
            gpu_utilization=80.0,
            temperature=75.0,
        )
        session.add(stats)
        await session.flush()

        repr_str = repr(stats)
        assert "GPUStats" in repr_str
        assert "80.0" in repr_str
        assert "75.0" in repr_str

    @pytest.mark.asyncio
    async def test_query_recent_gpu_stats(self, session):
        """Test querying GPU stats by time range."""
        now = datetime.utcnow()

        # Create stats at different times
        for i in range(5):
            stats = GPUStats(
                recorded_at=now - timedelta(minutes=i),
                gpu_utilization=50.0 + i * 10,
            )
            session.add(stats)
        await session.flush()

        # Query stats from last 3 minutes
        cutoff = now - timedelta(minutes=3)
        stmt = select(GPUStats).where(GPUStats.recorded_at >= cutoff)
        result = await session.execute(stmt)
        results = result.scalars().all()

        # Should get 4 results (0, 1, 2, 3 minutes ago)
        assert len(results) == 4

    @pytest.mark.asyncio
    async def test_gpu_stats_time_series(self, session):
        """Test storing and retrieving GPU stats as time series."""
        from datetime import UTC

        base_time = datetime.now(UTC)

        # Record stats every 10 seconds for 1 minute
        for i in range(6):
            stats = GPUStats(
                recorded_at=base_time + timedelta(seconds=i * 10),
                gpu_utilization=70.0 + i * 2,
                memory_used=15000 + i * 100,
                temperature=70.0 + i * 0.5,
            )
            session.add(stats)
        await session.flush()

        # Query all stats ordered by time
        stmt = select(GPUStats).order_by(GPUStats.recorded_at)
        result = await session.execute(stmt)
        results = result.scalars().all()

        assert len(results) == 6
        # Verify chronological order
        for i in range(len(results) - 1):
            assert results[i].recorded_at < results[i + 1].recorded_at


class TestModelIntegration:
    """Integration tests across multiple models."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self, session):
        """Test a complete workflow: camera -> detections -> event."""
        # Create camera
        camera = Camera(
            id="test_workflow",
            name="Test Workflow Camera",
            folder_path="/export/foscam/test_workflow",
        )
        session.add(camera)
        await session.flush()

        # Create multiple detections
        detection_ids = []
        for i in range(5):
            detection = Detection(
                camera_id="test_workflow",
                file_path=f"/export/foscam/test_workflow/image_{i:03d}.jpg",
                object_type="person" if i % 2 == 0 else "car",
                confidence=0.85 + i * 0.02,
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(str(detection.id))

        # Create event referencing detections
        event = Event(
            batch_id="workflow_batch_001",
            camera_id="test_workflow",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow() + timedelta(seconds=90),
            risk_score=65,
            risk_level="medium",
            summary="Mixed activity detected",
            detection_ids=",".join(detection_ids),
        )
        session.add(event)
        await session.flush()

        # Verify camera exists
        result = await session.get(Camera, "test_workflow")
        assert result is not None
        assert result.id == "test_workflow"

    @pytest.mark.asyncio
    async def test_multiple_cameras_isolation(self, session):
        """Test that data is properly isolated between cameras."""
        # Create two cameras
        camera1 = Camera(
            id="cam1",
            name="Camera 1",
            folder_path="/export/foscam/cam1",
        )
        camera2 = Camera(
            id="cam2",
            name="Camera 2",
            folder_path="/export/foscam/cam2",
        )
        session.add_all([camera1, camera2])
        await session.flush()

        # Add data to each camera
        detection1 = Detection(
            camera_id="cam1",
            file_path="/export/foscam/cam1/image_001.jpg",
        )
        detection2 = Detection(
            camera_id="cam2",
            file_path="/export/foscam/cam2/image_001.jpg",
        )
        session.add_all([detection1, detection2])
        await session.flush()

        event1 = Event(
            batch_id="batch_cam1",
            camera_id="cam1",
            started_at=datetime.utcnow(),
        )
        event2 = Event(
            batch_id="batch_cam2",
            camera_id="cam2",
            started_at=datetime.utcnow(),
        )
        session.add_all([event1, event2])
        await session.flush()

        # Query to verify isolation
        stmt1 = select(Detection).where(Detection.camera_id == "cam1")
        result1 = await session.execute(stmt1)
        cam1_detections = result1.scalars().all()

        stmt2 = select(Detection).where(Detection.camera_id == "cam2")
        result2 = await session.execute(stmt2)
        cam2_detections = result2.scalars().all()

        assert len(cam1_detections) == 1
        assert len(cam2_detections) == 1
        assert cam1_detections[0].id != cam2_detections[0].id
