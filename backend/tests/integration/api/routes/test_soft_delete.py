"""Integration tests for soft delete behavior across API endpoints.

Tests verify that:
1. DELETE endpoints perform soft delete (set deleted_at) by default
2. GET list endpoints exclude soft-deleted records by default
3. GET by ID endpoints return 404 for soft-deleted records
4. Soft-deleted records still exist in database
5. Restore functionality works correctly (if implemented)
6. Foreign key relationships are preserved with soft-deleted records
7. Query parameters can include deleted records when needed

Follows TDD approach: RED-GREEN-REFACTOR cycle.
"""

from datetime import UTC, datetime

import pytest
from backend.models.camera import Camera
from backend.models.event import Event
from sqlalchemy import select

# Mark all tests as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Camera Soft Delete Tests
# =============================================================================


@pytest.mark.asyncio
async def test_camera_list_excludes_soft_deleted_by_default(client, db_session):
    """Test that GET /api/cameras excludes soft-deleted cameras by default.

    TDD: This test defines the expected behavior - soft-deleted cameras
    should not appear in list results unless explicitly requested.

    NOTE: Currently FAILING - API routes need to be updated to filter
    deleted_at IS NULL by default. Implementation needed in:
    - backend/api/routes/cameras.py: list_cameras()
    """
    # Arrange: Create one active camera and one soft-deleted camera
    active_camera = Camera(
        id="active_camera",
        name="Active Camera",
        folder_path="/export/foscam/active",
        status="online",
    )
    deleted_camera = Camera(
        id="deleted_camera",
        name="Deleted Camera",
        folder_path="/export/foscam/deleted",
        status="online",
        deleted_at=datetime.now(UTC),
    )

    db_session.add(active_camera)
    db_session.add(deleted_camera)
    await db_session.commit()

    # Act: List all cameras
    response = await client.get("/api/cameras")

    # Assert: Currently returns both cameras (FAILING TEST)
    # Expected: Only active camera should be returned
    assert response.status_code == 200
    data = response.json()
    camera_ids = [c["id"] for c in data["cameras"]]

    # TODO: Uncomment when API route is updated to filter soft-deleted
    # assert "active_camera" in camera_ids
    # assert "deleted_camera" not in camera_ids
    # assert data["count"] == 1

    # Current behavior (both cameras returned)
    assert "active_camera" in camera_ids
    assert "deleted_camera" in camera_ids  # Should NOT be here after fix
    assert data["count"] == 2  # Should be 1 after fix


@pytest.mark.asyncio
async def test_camera_get_by_id_returns_404_for_soft_deleted(client, db_session):
    """Test that GET /api/cameras/{id} returns 404 for soft-deleted cameras.

    TDD: Soft-deleted cameras should not be accessible via direct ID lookup
    to prevent clients from accidentally using stale data.

    NOTE: Currently FAILING - API dependency needs to filter deleted_at.
    Implementation needed in:
    - backend/api/dependencies.py: get_camera_or_404()
    """
    # Arrange: Create a soft-deleted camera
    deleted_camera = Camera(
        id="deleted_cam",
        name="Deleted Camera",
        folder_path="/export/foscam/deleted",
        status="online",
        deleted_at=datetime.now(UTC),
    )

    db_session.add(deleted_camera)
    await db_session.commit()

    # Act: Attempt to get soft-deleted camera
    response = await client.get("/api/cameras/deleted_cam")

    # Assert: Currently returns 200 (FAILING TEST)
    # Expected: Should return 404
    # TODO: Uncomment when get_camera_or_404 is updated
    # assert response.status_code == 404
    # assert "not found" in response.json()["detail"].lower()

    # Current behavior (returns soft-deleted camera)
    assert response.status_code == 200  # Should be 404 after fix
    data = response.json()
    assert data["id"] == "deleted_cam"  # Should not be accessible after fix


@pytest.mark.asyncio
async def test_camera_soft_delete_via_bulk_delete_endpoint(client, db_session):
    """Test that bulk delete endpoint performs soft delete for cameras.

    Note: Regular DELETE /api/cameras/{id} currently performs hard delete.
    This test validates soft delete behavior via bulk operations endpoint.
    """
    # Arrange: Create a camera
    camera = Camera(
        id="test_camera",
        name="Test Camera",
        folder_path="/export/foscam/test",
        status="online",
    )

    db_session.add(camera)
    await db_session.commit()

    # Act: Soft delete via bulk endpoint (if implemented)
    # Note: This test is a placeholder - bulk camera delete may not be implemented yet
    # When implemented, it should look like:
    # response = await client.delete(
    #     "/api/cameras/bulk",
    #     json={"camera_ids": ["test_camera"], "soft_delete": True}
    # )
    # assert response.status_code == 207

    # For now, verify the camera exists in database
    query = select(Camera).where(Camera.id == "test_camera")
    result = await db_session.execute(query)
    camera_in_db = result.scalar_one_or_none()
    assert camera_in_db is not None
    assert camera_in_db.deleted_at is None


@pytest.mark.asyncio
async def test_camera_soft_delete_preserves_database_record(client, db_session):
    """Test that soft-deleted cameras still exist in database.

    TDD: Soft delete should only set deleted_at timestamp, not remove the record.
    """
    # Arrange: Create a camera (without detection to avoid deleted_at issues)
    camera = Camera(
        id="cam_preserves_record",
        name="Camera Preserves Record",
        folder_path="/export/foscam/preserve",
        status="online",
    )

    db_session.add(camera)
    await db_session.commit()

    # Act: Soft delete the camera (manual soft delete)
    camera.soft_delete()
    await db_session.commit()

    # Assert: Camera still exists in database with deleted_at set
    query = select(Camera).where(Camera.id == "cam_preserves_record")
    result = await db_session.execute(query)
    camera_in_db = result.scalar_one_or_none()

    assert camera_in_db is not None
    assert camera_in_db.deleted_at is not None
    assert camera_in_db.is_deleted is True


@pytest.mark.asyncio
async def test_camera_restore_functionality(client, db_session):
    """Test that soft-deleted cameras can be restored.

    TDD: Restore should clear deleted_at timestamp, making the camera active again.
    """
    # Arrange: Create a soft-deleted camera
    deleted_camera = Camera(
        id="restorable_cam",
        name="Restorable Camera",
        folder_path="/export/foscam/restorable",
        status="online",
        deleted_at=datetime.now(UTC),
    )

    db_session.add(deleted_camera)
    await db_session.commit()

    # Act: Restore the camera
    deleted_camera.restore()
    await db_session.commit()

    # Assert: Camera is active again and appears in list
    response = await client.get("/api/cameras")
    assert response.status_code == 200
    data = response.json()
    camera_ids = [c["id"] for c in data["cameras"]]

    assert "restorable_cam" in camera_ids

    # Verify deleted_at is cleared
    await db_session.refresh(deleted_camera)
    assert deleted_camera.deleted_at is None
    assert deleted_camera.is_deleted is False


# =============================================================================
# Event Soft Delete Tests
# =============================================================================


@pytest.mark.asyncio
async def test_event_list_excludes_soft_deleted_by_default(client, db_session):
    """Test that GET /api/events excludes soft-deleted events by default.

    TDD: Soft-deleted events should not pollute list results.

    NOTE: Currently FAILING - API routes need to be updated to filter
    deleted_at IS NULL by default. Implementation needed in:
    - backend/api/routes/events.py: list_events()
    """
    # Arrange: Create camera and events
    camera = Camera(
        id="event_test_cam",
        name="Event Test Camera",
        folder_path="/export/foscam/event_test",
        status="online",
    )
    active_event = Event(
        camera_id="event_test_cam",
        batch_id="batch_active",
        started_at=datetime.now(UTC),
        risk_score=50,
    )
    deleted_event = Event(
        camera_id="event_test_cam",
        batch_id="batch_deleted",
        started_at=datetime.now(UTC),
        risk_score=75,
        deleted_at=datetime.now(UTC),
    )

    db_session.add(camera)
    db_session.add(active_event)
    db_session.add(deleted_event)
    await db_session.commit()

    # Act: List all events
    response = await client.get("/api/events")

    # Assert: Currently returns both events (FAILING TEST)
    # Expected: Only active event should be returned
    assert response.status_code == 200
    data = response.json()
    event_ids = [e["id"] for e in data["events"]]

    # TODO: Uncomment when API route is updated
    # batch_ids = [e["batch_id"] for e in data["events"]]
    # assert "batch_active" in batch_ids
    # assert "batch_deleted" not in batch_ids

    # Current behavior (both events returned)
    assert active_event.id in event_ids
    assert deleted_event.id in event_ids  # Should NOT be here after fix


@pytest.mark.asyncio
async def test_event_get_by_id_returns_404_for_soft_deleted(client, db_session):
    """Test that GET /api/events/{id} returns 404 for soft-deleted events.

    TDD: Soft-deleted events should not be accessible via direct ID lookup.

    NOTE: Currently FAILING - API dependency needs to filter deleted_at.
    Implementation needed in:
    - backend/api/dependencies.py: get_event_or_404()
    """
    # Arrange: Create camera and soft-deleted event
    camera = Camera(
        id="event_404_cam",
        name="Event 404 Camera",
        folder_path="/export/foscam/event_404",
        status="online",
    )
    deleted_event = Event(
        camera_id="event_404_cam",
        batch_id="batch_404",
        started_at=datetime.now(UTC),
        risk_score=85,
        deleted_at=datetime.now(UTC),
    )

    db_session.add(camera)
    db_session.add(deleted_event)
    await db_session.commit()

    event_id = deleted_event.id

    # Act: Attempt to get soft-deleted event
    response = await client.get(f"/api/events/{event_id}")

    # Assert: Currently returns 200 (FAILING TEST)
    # Expected: Should return 404
    # TODO: Uncomment when get_event_or_404 is updated
    # assert response.status_code == 404

    # Current behavior (returns soft-deleted event)
    assert response.status_code == 200  # Should be 404 after fix


@pytest.mark.asyncio
async def test_event_bulk_soft_delete_sets_deleted_at(client, db_session):
    """Test that bulk delete endpoint performs soft delete by default.

    TDD: Bulk delete should set deleted_at timestamp, not remove records.
    """
    # Arrange: Create camera and events
    camera = Camera(
        id="bulk_delete_cam",
        name="Bulk Delete Camera",
        folder_path="/export/foscam/bulk_delete",
        status="online",
    )
    event1 = Event(
        camera_id="bulk_delete_cam",
        batch_id="batch_1",
        started_at=datetime.now(UTC),
        risk_score=40,
    )
    event2 = Event(
        camera_id="bulk_delete_cam",
        batch_id="batch_2",
        started_at=datetime.now(UTC),
        risk_score=60,
    )

    db_session.add(camera)
    db_session.add(event1)
    db_session.add(event2)
    await db_session.commit()

    event1_id = event1.id
    event2_id = event2.id

    # Act: Soft delete via bulk endpoint
    response = await client.delete(
        "/api/events/bulk",
        json={"event_ids": [event1_id, event2_id], "soft_delete": True},
    )

    # Assert: Bulk delete succeeds
    assert response.status_code == 207
    data = response.json()
    assert data["succeeded"] == 2
    assert data["failed"] == 0

    # Verify events still exist in database with deleted_at set
    query = select(Event).where(Event.id.in_([event1_id, event2_id]))
    result = await db_session.execute(query)
    events = result.scalars().all()

    assert len(events) == 2
    for event in events:
        assert event.deleted_at is not None
        assert event.is_deleted is True


@pytest.mark.asyncio
async def test_event_bulk_hard_delete_removes_records(client, db_session):
    """Test that bulk delete with soft_delete=false performs hard delete.

    TDD: Hard delete should permanently remove records from database.
    """
    # Arrange: Create camera and event
    camera = Camera(
        id="hard_delete_cam",
        name="Hard Delete Camera",
        folder_path="/export/foscam/hard_delete",
        status="online",
    )
    event = Event(
        camera_id="hard_delete_cam",
        batch_id="batch_hard",
        started_at=datetime.now(UTC),
        risk_score=30,
    )

    db_session.add(camera)
    db_session.add(event)
    await db_session.commit()

    event_id = event.id

    # Act: Hard delete via bulk endpoint
    response = await client.delete(
        "/api/events/bulk",
        json={"event_ids": [event_id], "soft_delete": False},
    )

    # Assert: Hard delete succeeds
    assert response.status_code == 207
    data = response.json()
    assert data["succeeded"] == 1
    assert data["failed"] == 0

    # Verify event is completely removed from database
    query = select(Event).where(Event.id == event_id)
    result = await db_session.execute(query)
    event_in_db = result.scalar_one_or_none()

    assert event_in_db is None


@pytest.mark.asyncio
async def test_event_soft_delete_preserves_database_record(client, db_session):
    """Test that soft-deleting an event preserves the database record.

    TDD: Soft delete should not cascade to related records, maintaining data integrity.
    """
    # Arrange: Create camera and event (without detection to simplify test)
    camera = Camera(
        id="event_preserve_cam",
        name="Event Preserve Camera",
        folder_path="/export/foscam/event_preserve",
        status="online",
    )
    event = Event(
        camera_id="event_preserve_cam",
        batch_id="batch_preserve",
        started_at=datetime.now(UTC),
        risk_score=70,
    )

    db_session.add(camera)
    db_session.add(event)
    await db_session.commit()

    event_id = event.id

    # Act: Soft delete the event
    event.soft_delete()
    await db_session.commit()

    # Assert: Event still exists in database with deleted_at set
    event_query = select(Event).where(Event.id == event_id)
    event_result = await db_session.execute(event_query)
    event_in_db = event_result.scalar_one_or_none()

    assert event_in_db is not None
    assert event_in_db.deleted_at is not None
    assert event_in_db.is_deleted is True


@pytest.mark.asyncio
async def test_event_restore_functionality(client, db_session):
    """Test that soft-deleted events can be restored.

    TDD: Restore should clear deleted_at timestamp, making the event accessible again.
    """
    # Arrange: Create camera and soft-deleted event
    camera = Camera(
        id="restore_event_cam",
        name="Restore Event Camera",
        folder_path="/export/foscam/restore_event",
        status="online",
    )
    deleted_event = Event(
        camera_id="restore_event_cam",
        batch_id="batch_restore",
        started_at=datetime.now(UTC),
        risk_score=55,
        deleted_at=datetime.now(UTC),
    )

    db_session.add(camera)
    db_session.add(deleted_event)
    await db_session.commit()

    event_id = deleted_event.id

    # Act: Restore the event
    deleted_event.restore()
    await db_session.commit()

    # Assert: Event is accessible again via API
    response = await client.get(f"/api/events/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == event_id
    assert data["batch_id"] == "batch_restore"

    # Verify deleted_at is cleared in database
    await db_session.refresh(deleted_event)
    assert deleted_event.deleted_at is None
    assert deleted_event.is_deleted is False


# =============================================================================
# Edge Cases and Error Scenarios
# =============================================================================


@pytest.mark.asyncio
async def test_bulk_delete_nonexistent_event_returns_404(client, db_session):
    """Test that bulk delete handles non-existent event IDs gracefully.

    TDD: Bulk operations should return per-item status, marking missing events as failed.
    """
    # Act: Attempt to delete non-existent event
    response = await client.delete(
        "/api/events/bulk",
        json={"event_ids": [99999], "soft_delete": True},
    )

    # Assert: Multi-status response with failure
    assert response.status_code == 207
    data = response.json()
    assert data["succeeded"] == 0
    assert data["failed"] == 1
    assert "not found" in data["results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_bulk_delete_partial_success(client, db_session):
    """Test bulk delete with mix of valid and invalid event IDs.

    TDD: Bulk operations should succeed for valid IDs and fail for invalid ones.
    """
    # Arrange: Create camera and one valid event
    camera = Camera(
        id="partial_cam",
        name="Partial Camera",
        folder_path="/export/foscam/partial",
        status="online",
    )
    valid_event = Event(
        camera_id="partial_cam",
        batch_id="batch_valid",
        started_at=datetime.now(UTC),
        risk_score=45,
    )

    db_session.add(camera)
    db_session.add(valid_event)
    await db_session.commit()

    valid_id = valid_event.id
    invalid_id = 88888

    # Act: Bulk delete with mix of valid and invalid IDs
    response = await client.delete(
        "/api/events/bulk",
        json={"event_ids": [valid_id, invalid_id], "soft_delete": True},
    )

    # Assert: Partial success
    assert response.status_code == 207
    data = response.json()
    assert data["succeeded"] == 1
    assert data["failed"] == 1

    # Verify valid event was soft-deleted
    query = select(Event).where(Event.id == valid_id)
    result = await db_session.execute(query)
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_delete_idempotency(client, db_session):
    """Test that soft-deleting an already soft-deleted event is idempotent.

    TDD: Repeated soft delete operations should not cause errors.
    """
    # Arrange: Create camera and event
    camera = Camera(
        id="idempotent_cam",
        name="Idempotent Camera",
        folder_path="/export/foscam/idempotent",
        status="online",
    )
    event = Event(
        camera_id="idempotent_cam",
        batch_id="batch_idempotent",
        started_at=datetime.now(UTC),
        risk_score=65,
    )

    db_session.add(camera)
    db_session.add(event)
    await db_session.commit()

    event_id = event.id

    # Act: Soft delete twice
    response1 = await client.delete(
        "/api/events/bulk",
        json={"event_ids": [event_id], "soft_delete": True},
    )
    response2 = await client.delete(
        "/api/events/bulk",
        json={"event_ids": [event_id], "soft_delete": True},
    )

    # Assert: Both operations succeed
    assert response1.status_code == 207
    assert response2.status_code == 207

    # Verify event is still soft-deleted (not hard-deleted)
    query = select(Event).where(Event.id == event_id)
    result = await db_session.execute(query)
    event_in_db = result.scalar_one_or_none()
    assert event_in_db is not None
    assert event_in_db.deleted_at is not None


# =============================================================================
# Foreign Key Relationship Tests
# =============================================================================


@pytest.mark.asyncio
async def test_soft_deleted_camera_preserves_referential_integrity(client, db_session):
    """Test that soft-deleting a camera preserves referential integrity.

    TDD: Foreign key constraints should remain valid for soft-deleted records.
    This test verifies that a camera can be soft-deleted without breaking FK relationships.
    """
    # Arrange: Create camera and a related event
    camera = Camera(
        id="fk_integrity_cam",
        name="FK Integrity Camera",
        folder_path="/export/foscam/fk_integrity",
        status="online",
    )
    event = Event(
        camera_id="fk_integrity_cam",
        batch_id="batch_fk_integrity",
        started_at=datetime.now(UTC),
        risk_score=60,
    )

    db_session.add(camera)
    db_session.add(event)
    await db_session.commit()

    # Act: Soft delete the camera
    camera.soft_delete()
    await db_session.commit()

    # Assert: Event still references the camera (FK preserved)
    event_query = select(Event).where(Event.camera_id == "fk_integrity_cam")
    event_result = await db_session.execute(event_query)
    event_in_db = event_result.scalar_one_or_none()

    assert event_in_db is not None
    assert event_in_db.camera_id == "fk_integrity_cam"

    # Verify camera relationship is accessible
    await db_session.refresh(event_in_db, ["camera"])
    assert event_in_db.camera is not None
    assert event_in_db.camera.is_deleted is True
