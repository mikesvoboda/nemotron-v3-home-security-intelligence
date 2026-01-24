"""Full stack integration tests for database, models, and workflows."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from backend.core.database import get_engine, get_session
from backend.models import Camera, Detection, Event
from backend.models.event_detection import EventDetection
from backend.tests.conftest import unique_id


@pytest.fixture
async def clean_full_stack(integration_db):
    """Delete all tables data before test runs for proper isolation.

    These tests use hardcoded camera IDs, so they need clean state.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    async with get_engine().begin() as conn:
        # Delete in order respecting foreign key constraints
        await conn.execute(text("DELETE FROM logs"))
        await conn.execute(text("DELETE FROM gpu_stats"))
        await conn.execute(text("DELETE FROM event_detections"))
        await conn.execute(text("DELETE FROM detections"))
        await conn.execute(text("DELETE FROM events"))
        await conn.execute(text("DELETE FROM cameras"))

    yield

    # Cleanup after test too (best effort)
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM logs"))
            await conn.execute(text("DELETE FROM gpu_stats"))
            await conn.execute(text("DELETE FROM event_detections"))
            await conn.execute(text("DELETE FROM detections"))
            await conn.execute(text("DELETE FROM events"))
            await conn.execute(text("DELETE FROM cameras"))
    except Exception:
        pass


@pytest.mark.asyncio
async def test_create_camera(integration_db, clean_full_stack):
    """Test creating a camera in the database."""
    camera_id = unique_id("front_door")
    camera_name = f"Front Door Camera {camera_id[-8:]}"
    async with get_session() as session:
        camera = Camera(
            id=camera_id,
            name=camera_name,
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
            created_at=datetime.now(UTC),
        )
        session.add(camera)
        await session.flush()

        # Verify camera was created
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        saved_camera = result.scalar_one_or_none()

        assert saved_camera is not None
        assert saved_camera.id == camera_id
        assert saved_camera.name == camera_name
        assert saved_camera.folder_path == f"/export/foscam/{camera_id}"
        assert saved_camera.status == "online"


@pytest.mark.asyncio
async def test_create_detection(integration_db, clean_full_stack):
    """Test creating a detection linked to a camera."""
    camera_id = unique_id("backyard")
    async with get_session() as session:
        # Create camera first
        camera = Camera(
            id=camera_id,
            name="Backyard Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        session.add(camera)
        await session.flush()

        # Create detection
        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image001.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=300,
        )
        session.add(detection)
        await session.flush()

        # Verify detection was created
        result = await session.execute(select(Detection).where(Detection.camera_id == camera_id))
        saved_detection = result.scalar_one_or_none()

        assert saved_detection is not None
        assert saved_detection.camera_id == camera_id
        assert saved_detection.object_type == "person"
        assert saved_detection.confidence == 0.95


@pytest.mark.asyncio
async def test_create_event(integration_db, clean_full_stack):
    """Test creating a security event linked to a camera."""
    camera_id = unique_id("driveway")
    batch_id = unique_id("batch_001")
    async with get_session() as session:
        # Create camera first
        camera = Camera(
            id=camera_id,
            name="Driveway Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        session.add(camera)
        await session.flush()

        # Create detections first to link to the event
        detection_ids = []
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/img{i}.jpg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.9,
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(detection.id)

        # Create event
        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC) + timedelta(minutes=2),
            risk_score=45,
            risk_level="medium",
            summary="Person detected near vehicle",
            reasoning="Multiple detections of person approaching parked car",
            reviewed=False,
        )
        session.add(event)
        await session.flush()

        # Link detections to event via junction table
        for det_id in detection_ids:
            junction = EventDetection(event_id=event.id, detection_id=det_id)
            session.add(junction)
        await session.flush()

        # Verify event was created
        result = await session.execute(select(Event).where(Event.camera_id == camera_id))
        saved_event = result.scalar_one_or_none()

        assert saved_event is not None
        assert saved_event.batch_id == batch_id
        assert saved_event.risk_score == 75
        assert saved_event.risk_level == "medium"
        # Verify detections are linked
        await session.refresh(saved_event, ["detections"])
        assert len(saved_event.detection_id_list) == 3


@pytest.mark.asyncio
async def test_camera_detection_relationship(integration_db, clean_full_stack):
    """Test relationship between camera and detections."""
    camera_id = unique_id("garage")
    async with get_session() as session:
        # Create camera with detections
        camera = Camera(
            id=camera_id,
            name="Garage Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        session.add(camera)
        await session.flush()

        # Add multiple detections
        detection1 = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img1.jpg",
            detected_at=datetime.now(UTC),
            object_type="car",
            confidence=0.92,
        )
        detection2 = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img2.jpg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.88,
        )
        session.add_all([detection1, detection2])
        await session.flush()

        # Query camera with detections
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        camera_with_detections = result.scalar_one()

        # Access relationship
        await session.refresh(camera_with_detections, ["detections"])
        assert len(camera_with_detections.detections) == 2


@pytest.mark.asyncio
async def test_camera_event_relationship(integration_db, clean_full_stack):
    """Test relationship between camera and events."""
    camera_id = unique_id("porch")
    batch_id_100 = unique_id("batch_100")
    batch_id_101 = unique_id("batch_101")
    async with get_session() as session:
        # Create camera
        camera = Camera(
            id=camera_id,
            name="Porch Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        session.add(camera)
        await session.flush()

        # Add multiple events
        event1 = Event(
            batch_id=batch_id_100,
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            risk_score=30,
            risk_level="low",
        )
        event2 = Event(
            batch_id=batch_id_101,
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            risk_score=85,
            risk_level="high",
        )
        session.add_all([event1, event2])
        await session.flush()

        # Query camera with events
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        camera_with_events = result.scalar_one()

        # Access relationship
        await session.refresh(camera_with_events, ["events"])
        assert len(camera_with_events.events) == 2


@pytest.mark.asyncio
async def test_complete_workflow_camera_to_event(integration_db, clean_full_stack):
    """Test complete workflow: create camera -> add detection -> create event."""
    camera_id = unique_id("workflow_cam")
    batch_id = unique_id("batch_workflow_001")
    async with get_session() as session:
        # Step 1: Create camera
        camera = Camera(
            id=camera_id,
            name="Workflow Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
            created_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
        session.add(camera)
        await session.flush()

    # Step 2: Add detections (in separate session to simulate real usage)
    detection_ids = []
    async with get_session() as session:
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/img{i:03d}.jpg",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type="person" if i % 2 == 0 else "car",
                confidence=0.90 + (i * 0.02),
                bbox_x=100 + (i * 10),
                bbox_y=100 + (i * 10),
                bbox_width=150,
                bbox_height=200,
            )
            session.add(detection)
            await session.flush()
            detection_ids.append(detection.id)

    # Step 3: Create event based on detections and link via junction table
    async with get_session() as session:
        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=datetime.now(UTC) - timedelta(minutes=5),
            ended_at=datetime.now(UTC),
            risk_score=65,
            risk_level="medium",
            summary="Multiple objects detected in sequence",
            reasoning="Pattern suggests normal activity",
            reviewed=False,
        )
        session.add(event)
        await session.flush()

        # Link detections to event via junction table
        for det_id in detection_ids:
            junction = EventDetection(event_id=event.id, detection_id=det_id)
            session.add(junction)
        await session.flush()

    # Step 4: Query and verify complete workflow
    async with get_session() as session:
        # Get camera with all related data
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        final_camera = result.scalar_one()

        await session.refresh(final_camera, ["detections", "events"])

        # Verify camera
        assert final_camera.id == camera_id
        assert final_camera.name == "Workflow Test Camera"

        # Verify detections
        assert len(final_camera.detections) == 3
        assert all(d.camera_id == camera_id for d in final_camera.detections)

        # Verify events
        assert len(final_camera.events) == 1
        event = final_camera.events[0]
        assert event.batch_id == batch_id
        assert event.risk_score == 65
        assert event.risk_level == "medium"
        # Verify detections are linked via junction table
        await session.refresh(event, ["detections"])
        assert len(event.detection_id_list) == 3
        assert set(event.detection_id_list) == set(detection_ids)


@pytest.mark.asyncio
async def test_query_detections_by_time_range(integration_db, clean_full_stack):
    """Test querying detections within a specific time range."""
    camera_id = unique_id("time_test")
    async with get_session() as session:
        # Create camera
        camera = Camera(
            id=camera_id,
            name="Time Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create detections at different times
        base_time = datetime.now(UTC)
        for i in range(5):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/img{i}.jpg",
                detected_at=base_time - timedelta(minutes=i * 10),
                object_type="person",
                confidence=0.9,
            )
            session.add(detection)
        await session.flush()

        # Query detections from last 30 minutes
        cutoff_time = base_time - timedelta(minutes=30)
        result = await session.execute(
            select(Detection)
            .where(Detection.camera_id == camera_id)
            .where(Detection.detected_at >= cutoff_time)
            .order_by(Detection.detected_at.desc())
        )
        recent_detections = result.scalars().all()

        # Should get 3 detections (0, 10, 20 minutes ago)
        assert len(recent_detections) == 4


@pytest.mark.asyncio
async def test_query_events_by_risk_level(integration_db, clean_full_stack):
    """Test querying events filtered by risk level."""
    camera_id = unique_id("risk_test")
    async with get_session() as session:
        # Create camera
        camera = Camera(
            id=camera_id,
            name="Risk Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create events with different risk levels
        risk_configs = [
            (unique_id("batch_r1"), 25, "low"),
            (unique_id("batch_r2"), 50, "medium"),
            (unique_id("batch_r3"), 85, "high"),
            (unique_id("batch_r4"), 35, "low"),
        ]

        for batch_id, risk_score, risk_level in risk_configs:
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=risk_score,
                risk_level=risk_level,
            )
            session.add(event)
        await session.flush()

        # Query high risk events
        result = await session.execute(
            select(Event).where(Event.camera_id == camera_id).where(Event.risk_level == "high")
        )
        high_risk_events = result.scalars().all()

        assert len(high_risk_events) == 1
        assert high_risk_events[0].risk_score == 85


@pytest.mark.asyncio
async def test_cascade_delete_camera(integration_db, clean_full_stack):
    """Test that deleting a camera cascades to detections and events."""
    camera_id = unique_id("cascade_test")
    batch_id = unique_id("batch_cascade")
    async with get_session() as session:
        # Create camera with detections and events
        camera = Camera(
            id=camera_id,
            name="Cascade Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Add detection
        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img.jpg",
            detected_at=datetime.now(UTC),
        )
        session.add(detection)

        # Add event
        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()

        # Verify data exists
        detection_count = (
            (await session.execute(select(Detection).where(Detection.camera_id == camera_id)))
            .scalars()
            .all()
        )
        event_count = (
            (await session.execute(select(Event).where(Event.camera_id == camera_id)))
            .scalars()
            .all()
        )

        assert len(detection_count) == 1
        assert len(event_count) == 1

    # Delete camera in new session
    async with get_session() as session:
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one()
        await session.delete(camera)
        await session.flush()

    # Verify detections and events were deleted
    async with get_session() as session:
        detection_count = (
            (await session.execute(select(Detection).where(Detection.camera_id == camera_id)))
            .scalars()
            .all()
        )
        event_count = (
            (await session.execute(select(Event).where(Event.camera_id == camera_id)))
            .scalars()
            .all()
        )

        assert len(detection_count) == 0
        assert len(event_count) == 0


@pytest.mark.asyncio
async def test_multiple_cameras_isolation(integration_db, clean_full_stack):
    """Test that operations on multiple cameras are properly isolated."""
    camera_id_1 = unique_id("iso_cam1")
    camera_id_2 = unique_id("iso_cam2")
    async with get_session() as session:
        # Create two cameras
        camera1 = Camera(
            id=camera_id_1,
            name="Isolation Camera 1",
            folder_path=f"/export/foscam/{camera_id_1}",
        )
        camera2 = Camera(
            id=camera_id_2,
            name="Isolation Camera 2",
            folder_path=f"/export/foscam/{camera_id_2}",
        )
        session.add_all([camera1, camera2])
        await session.flush()

        # Add detections to each
        det1 = Detection(
            camera_id=camera_id_1,
            file_path=f"/export/foscam/{camera_id_1}/img.jpg",
            detected_at=datetime.now(UTC),
        )
        det2 = Detection(
            camera_id=camera_id_2,
            file_path=f"/export/foscam/{camera_id_2}/img.jpg",
            detected_at=datetime.now(UTC),
        )
        session.add_all([det1, det2])
        await session.flush()

        # Query each camera's detections
        result1 = await session.execute(select(Detection).where(Detection.camera_id == camera_id_1))
        cam1_detections = result1.scalars().all()

        result2 = await session.execute(select(Detection).where(Detection.camera_id == camera_id_2))
        cam2_detections = result2.scalars().all()

        # Each camera should only see its own detections
        assert len(cam1_detections) == 1
        assert len(cam2_detections) == 1
        assert cam1_detections[0].camera_id == camera_id_1
        assert cam2_detections[0].camera_id == camera_id_2


@pytest.mark.asyncio
async def test_event_reviewed_status_update(integration_db, clean_full_stack):
    """Test updating event reviewed status."""
    camera_id = unique_id("review_test")
    batch_id = unique_id("batch_review")
    async with get_session() as session:
        # Create camera and event
        camera = Camera(
            id=camera_id,
            name="Review Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            risk_score=60,
            reviewed=False,
        )
        session.add(event)
        await session.flush()

        event_id = event.id

    # Update reviewed status
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one()

        assert event.reviewed is False

        event.reviewed = True
        event.notes = "Reviewed - false alarm"
        await session.flush()

    # Verify update
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.id == event_id))
        updated_event = result.scalar_one()

        assert updated_event.reviewed is True
        assert updated_event.notes == "Reviewed - false alarm"
