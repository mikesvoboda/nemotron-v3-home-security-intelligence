"""Integration tests for cameras API endpoints."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select


@pytest.fixture
async def clean_cameras(clean_tables, client):
    """Ensure clean database state before test runs for proper isolation.

    Uses clean_tables fixture to truncate all tables, ensuring no leftover
    data from parallel tests.
    """
    # clean_tables already truncated, just yield
    yield


# === CREATE Tests ===


@pytest.mark.asyncio
async def test_create_camera_success(client):
    """Test successful camera creation."""
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Front Door Camera {unique_id}",
        "folder_path": f"/export/foscam/front_door_{unique_id}",
        "status": "online",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == camera_data["name"]
    assert data["folder_path"] == camera_data["folder_path"]
    assert data["status"] == camera_data["status"]
    assert "id" in data
    assert "created_at" in data
    # ID should be normalized camera name (e.g., "front_door_camera_abc12345")
    assert data["id"] == f"front_door_camera_{unique_id}"


@pytest.mark.asyncio
async def test_create_camera_default_status(client):
    """Test camera creation with default status."""
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Back Door Camera {unique_id}",
        "folder_path": f"/export/foscam/back_door_{unique_id}",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "online"  # Default status


@pytest.mark.asyncio
async def test_create_camera_missing_name(client):
    """Test camera creation fails without name."""
    camera_data = {
        "folder_path": "/export/foscam/test",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_camera_missing_folder_path(client):
    """Test camera creation fails without folder_path."""
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Test Camera {unique_id}",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_camera_empty_name(client):
    """Test camera creation fails with empty name."""
    camera_data = {
        "name": "",
        "folder_path": "/export/foscam/test",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_camera_empty_folder_path(client):
    """Test camera creation fails with empty folder_path."""
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Test Camera {unique_id}",
        "folder_path": "",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422  # Validation error


# === READ Tests ===


@pytest.mark.asyncio
@pytest.mark.xdist_group("clean_db")
async def test_list_cameras_empty(client, clean_cameras):
    """Test listing cameras when none exist."""
    response = await client.get("/api/cameras")

    assert response.status_code == 200
    data = response.json()
    assert data["cameras"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
@pytest.mark.xdist_group("clean_db")
async def test_list_cameras_with_data(client, clean_cameras):
    """Test listing cameras with existing data."""
    # Create test cameras
    cameras = [
        {"name": "Camera 1", "folder_path": "/export/foscam/cam1"},
        {"name": "Camera 2", "folder_path": "/export/foscam/cam2"},
        {"name": "Camera 3", "folder_path": "/export/foscam/cam3"},
    ]

    for camera in cameras:
        await client.post("/api/cameras", json=camera)

    response = await client.get("/api/cameras")

    assert response.status_code == 200
    data = response.json()
    assert len(data["cameras"]) == 3
    assert data["count"] == 3


@pytest.mark.asyncio
@pytest.mark.xdist_group("clean_db")
async def test_list_cameras_filter_by_status(client, clean_cameras):
    """Test listing cameras filtered by status."""
    # Create cameras with different statuses
    await client.post(
        "/api/cameras",
        json={"name": "Online Camera", "folder_path": "/export/foscam/cam1", "status": "online"},
    )
    await client.post(
        "/api/cameras",
        json={"name": "Offline Camera", "folder_path": "/export/foscam/cam2", "status": "offline"},
    )
    await client.post(
        "/api/cameras",
        json={"name": "Error Camera", "folder_path": "/export/foscam/cam3", "status": "error"},
    )

    # Filter by online status
    response = await client.get("/api/cameras?status=online")

    assert response.status_code == 200
    data = response.json()
    assert len(data["cameras"]) == 1
    assert data["cameras"][0]["status"] == "online"
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_get_camera_by_id_success(client):
    """Test getting a specific camera by ID."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    camera_name = f"Test Camera {unique_id}"
    create_response = await client.post(
        "/api/cameras",
        json={"name": camera_name, "folder_path": f"/export/foscam/test_{unique_id}"},
    )
    camera_id = create_response.json()["id"]

    # Get the camera
    response = await client.get(f"/api/cameras/{camera_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == camera_id
    assert data["name"] == camera_name


@pytest.mark.asyncio
async def test_get_camera_by_id_not_found(client):
    """Test getting a non-existent camera returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/cameras/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_camera_snapshot_returns_latest_image(client, integration_env, tmp_path):
    """GET /api/cameras/{id}/snapshot returns the most recently modified image."""
    import uuid

    from backend.core.config import get_settings

    # Arrange a fake foscam root and camera directory using pytest's tmp_path fixture.
    unique_id = str(uuid.uuid4())[:8]
    foscam_root = tmp_path / "foscam"
    cam_dir = foscam_root / f"front_door_{unique_id}"
    cam_dir.mkdir(parents=True, exist_ok=True)

    # Create two images with different mtimes.
    older = cam_dir / "a.jpg"
    newer = cam_dir / "b.jpg"
    older.write_bytes(b"older")
    await asyncio.sleep(0.01)
    newer.write_bytes(b"newer")

    # Ensure settings pick up our foscam base path.
    import os

    os.environ["FOSCAM_BASE_PATH"] = str(foscam_root)
    get_settings.cache_clear()

    # Create camera pointing at cam_dir
    create_resp = await client.post(
        "/api/cameras",
        json={"name": f"Front Door {unique_id}", "folder_path": str(cam_dir), "status": "online"},
    )
    assert create_resp.status_code == 201
    camera_id = create_resp.json()["id"]

    # Act
    resp = await client.get(f"/api/cameras/{camera_id}/snapshot")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
    assert resp.content == b"newer"


@pytest.mark.asyncio
async def test_get_camera_snapshot_folder_outside_root_forbidden(client, integration_env, tmp_path):
    """Snapshot endpoint returns 404 for cameras whose folder_path is outside foscam_base_path."""
    import uuid

    from backend.core.config import get_settings

    unique_id = str(uuid.uuid4())[:8]
    foscam_root = tmp_path / "foscam"
    foscam_root.mkdir(parents=True, exist_ok=True)
    outside_dir = tmp_path / f"outside_{unique_id}"
    outside_dir.mkdir(parents=True, exist_ok=True)

    import os

    os.environ["FOSCAM_BASE_PATH"] = str(foscam_root)
    get_settings.cache_clear()

    create_resp = await client.post(
        "/api/cameras",
        json={"name": f"Bad Cam {unique_id}", "folder_path": str(outside_dir), "status": "online"},
    )
    camera_id = create_resp.json()["id"]

    resp = await client.get(f"/api/cameras/{camera_id}/snapshot")
    assert resp.status_code == 404


# === UPDATE Tests ===


@pytest.mark.asyncio
async def test_update_camera_name(client):
    """Test updating camera name."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={"name": f"Old Name {unique_id}", "folder_path": f"/export/foscam/test_{unique_id}"},
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    camera_id = create_response.json()["id"]

    # Update the name
    response = await client.patch(
        f"/api/cameras/{camera_id}",
        json={"name": "New Name"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert "/export/foscam/test_" in data["folder_path"]  # Unchanged (with unique suffix)


@pytest.mark.asyncio
async def test_update_camera_status(client):
    """Test updating camera status."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={
            "name": f"Test Camera {unique_id}",
            "folder_path": f"/export/foscam/test_{unique_id}",
        },
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    camera_id = create_response.json()["id"]

    # Update the status
    response = await client.patch(
        f"/api/cameras/{camera_id}",
        json={"status": "offline"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "offline"


@pytest.mark.asyncio
async def test_update_camera_folder_path(client):
    """Test updating camera folder path."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={"name": f"Test Camera {unique_id}", "folder_path": f"/export/foscam/old_{unique_id}"},
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    camera_id = create_response.json()["id"]

    # Update the folder path
    response = await client.patch(
        f"/api/cameras/{camera_id}",
        json={"folder_path": "/export/foscam/new"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["folder_path"] == "/export/foscam/new"


@pytest.mark.asyncio
async def test_update_camera_multiple_fields(client):
    """Test updating multiple camera fields at once."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={
            "name": f"Old Name {unique_id}",
            "folder_path": f"/export/foscam/old_{unique_id}",
            "status": "online",
        },
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    camera_id = create_response.json()["id"]

    # Update multiple fields
    response = await client.patch(
        f"/api/cameras/{camera_id}",
        json={"name": "New Name", "status": "offline", "folder_path": "/export/foscam/new"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["status"] == "offline"
    assert data["folder_path"] == "/export/foscam/new"


@pytest.mark.asyncio
async def test_update_camera_not_found(client):
    """Test updating a non-existent camera returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.patch(
        f"/api/cameras/{fake_id}",
        json={"name": "New Name"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_camera_empty_payload(client):
    """Test updating camera with empty payload."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    camera_name = f"Test Camera {unique_id}"
    create_response = await client.post(
        "/api/cameras",
        json={"name": camera_name, "folder_path": f"/export/foscam/test_{unique_id}"},
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    camera_id = create_response.json()["id"]

    # Update with empty payload
    response = await client.patch(f"/api/cameras/{camera_id}", json={})

    assert response.status_code == 200
    data = response.json()
    # Nothing should change
    assert data["name"] == camera_name


@pytest.mark.asyncio
async def test_update_camera_invalid_empty_name(client):
    """Test updating camera with empty name fails validation."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={
            "name": f"Test Camera {unique_id}",
            "folder_path": f"/export/foscam/test_{unique_id}",
        },
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    camera_id = create_response.json()["id"]

    # Try to update with empty name
    response = await client.patch(
        f"/api/cameras/{camera_id}",
        json={"name": ""},
    )

    assert response.status_code == 422  # Validation error


# === DELETE Tests ===


@pytest.mark.asyncio
async def test_delete_camera_success(client):
    """Test successful camera deletion."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={
            "name": f"Test Camera {unique_id}",
            "folder_path": f"/export/foscam/test_{unique_id}",
        },
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    camera_id = create_response.json()["id"]

    # Delete the camera
    response = await client.delete(f"/api/cameras/{camera_id}")

    assert response.status_code == 204

    # Verify camera is deleted
    get_response = await client.get(f"/api/cameras/{camera_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_camera_not_found(client):
    """Test deleting a non-existent camera returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.delete(f"/api/cameras/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_camera_cascades_to_related_data(client):
    """Test that deleting a camera cascades to detections and events."""
    from backend.models.detection import Detection
    from backend.models.event import Event

    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={
            "name": f"Test Camera {unique_id}",
            "folder_path": f"/export/foscam/test_{unique_id}",
        },
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    camera_id = create_response.json()["id"]

    # Add related data directly to database
    from backend.core.database import get_session

    async with get_session() as db_session:
        detection = Detection(
            camera_id=camera_id,
            file_path="/export/foscam/test/image1.jpg",
            object_type="person",
            confidence=0.95,
        )
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            risk_score=75,
            summary="Test event",
        )

        db_session.add(detection)
        db_session.add(event)
        await db_session.commit()

        # Verify data exists
        detection_result = await db_session.execute(
            select(Detection).where(Detection.camera_id == camera_id)
        )
        event_result = await db_session.execute(select(Event).where(Event.camera_id == camera_id))
        assert detection_result.scalar_one_or_none() is not None
        assert event_result.scalar_one_or_none() is not None

    # Delete the camera
    response = await client.delete(f"/api/cameras/{camera_id}")
    assert response.status_code == 204

    # Verify cascade delete worked
    from backend.core.database import get_session

    async with get_session() as db_session:
        detection_result = await db_session.execute(
            select(Detection).where(Detection.camera_id == camera_id)
        )
        event_result = await db_session.execute(select(Event).where(Event.camera_id == camera_id))
        assert detection_result.scalar_one_or_none() is None
        assert event_result.scalar_one_or_none() is None


# === Validation Tests ===


@pytest.mark.asyncio
async def test_create_camera_with_very_long_name(client):
    """Test camera creation with name exceeding max length."""
    camera_data = {
        "name": "A" * 256,  # Exceeds 255 character limit
        "folder_path": "/export/foscam/test",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_camera_with_very_long_folder_path(client):
    """Test camera creation with folder_path exceeding max length."""
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Test Camera {unique_id}",
        "folder_path": "/export/foscam/" + "a" * 500,  # Exceeds 500 character limit
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_cameras_returns_correct_schema(client):
    """Test that list cameras endpoint returns correct response schema."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={
            "name": f"Test Camera {unique_id}",
            "folder_path": f"/export/foscam/test_{unique_id}",
        },
    )
    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"

    response = await client.get("/api/cameras")

    assert response.status_code == 200
    data = response.json()
    # Verify schema structure
    assert "cameras" in data
    assert "count" in data
    assert isinstance(data["cameras"], list)
    assert isinstance(data["count"], int)

    # Verify camera object structure
    if data["cameras"]:
        camera = data["cameras"][0]
        required_fields = ["id", "name", "folder_path", "status", "created_at"]
        for field in required_fields:
            assert field in camera


@pytest.mark.asyncio
async def test_camera_response_includes_all_fields(client):
    """Test that camera response includes all expected fields."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={
            "name": f"Test Camera {unique_id}",
            "folder_path": f"/export/foscam/test_{unique_id}",
        },
    )

    assert create_response.status_code == 201, f"Failed to create camera: {create_response.json()}"
    data = create_response.json()

    required_fields = ["id", "name", "folder_path", "status", "created_at", "last_seen_at"]
    for field in required_fields:
        assert field in data


# === Edge Cases ===


@pytest.mark.asyncio
@pytest.mark.xdist_group("clean_db")
async def test_concurrent_camera_creation(client, clean_cameras):
    """Test creating multiple cameras concurrently."""
    import asyncio

    cameras = [{"name": f"Camera {i}", "folder_path": f"/export/foscam/cam{i}"} for i in range(5)]

    # Create cameras concurrently
    tasks = [client.post("/api/cameras", json=camera) for camera in cameras]
    responses = await asyncio.gather(*tasks)

    # All should succeed
    for response in responses:
        assert response.status_code == 201

    # Verify all were created
    list_response = await client.get("/api/cameras")
    data = list_response.json()
    assert data["count"] == 5


@pytest.mark.asyncio
async def test_update_after_delete_fails(client):
    """Test that updating a deleted camera fails."""
    # Create a camera with unique name/path to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    create_response = await client.post(
        "/api/cameras",
        json={
            "name": f"Test Camera {unique_id}",
            "folder_path": f"/export/foscam/test_{unique_id}",
        },
    )
    camera_id = create_response.json()["id"]

    # Delete the camera
    await client.delete(f"/api/cameras/{camera_id}")

    # Try to update deleted camera
    response = await client.patch(
        f"/api/cameras/{camera_id}",
        json={"name": "New Name"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_filter_by_nonexistent_status(client):
    """Test filtering by a status that doesn't exist returns empty list."""
    # Create a camera with online status
    await client.post(
        "/api/cameras",
        json={"name": "Online Camera", "folder_path": "/export/foscam/cam1", "status": "online"},
    )

    # Filter by non-existent status
    response = await client.get("/api/cameras?status=nonexistent")

    assert response.status_code == 200
    data = response.json()
    assert len(data["cameras"]) == 0
    assert data["count"] == 0
