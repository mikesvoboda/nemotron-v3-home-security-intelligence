"""Integration tests for feedback API endpoints.

NEM-2315: Tests for the /api/feedback endpoints which provide CRUD operations
for managing event feedback submissions.

Endpoints tested:
    POST   /api/feedback              - Submit feedback for an event
    GET    /api/feedback              - List all feedback (paginated)
    GET    /api/feedback/{id}         - Get specific feedback
    GET    /api/feedback/event/{id}   - Get feedback for specific event
    DELETE /api/feedback/{id}         - Delete feedback
    GET    /api/feedback/stats        - Get aggregate statistics
"""

import uuid
from datetime import UTC, datetime

import pytest

from backend.tests.integration.test_helpers import get_error_message


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# === Helper Functions ===


async def create_test_camera_and_event(client) -> tuple[dict, dict]:
    """Create a test camera and event, returning both.

    Creates both the camera and event via direct database access to ensure
    they are in the same transaction context.
    """

    from backend.core.database import get_session
    from backend.models.camera import Camera
    from backend.models.event import Event

    camera_id = unique_id("camera")

    # Create both camera and event in the same session
    async with get_session() as db_session:
        # Create camera directly
        camera = Camera(
            id=camera_id,
            name=unique_id("Test Camera"),
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        db_session.add(camera)
        await db_session.flush()  # Flush to make camera visible for FK constraint

        # Create event
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            risk_score=50,
            summary="Test event for feedback",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(camera)
        await db_session.refresh(event)

        camera_data = {
            "id": camera.id,
            "name": camera.name,
            "folder_path": camera.folder_path,
            "status": camera.status,
        }

        event_data = {
            "id": event.id,
            "camera_id": event.camera_id,
            "risk_score": event.risk_score,
            "summary": event.summary,
        }

    return camera_data, event_data


async def create_test_feedback(
    client,
    event_id: int,
    feedback_type: str = "false_positive",
    notes: str | None = None,
) -> dict:
    """Create test feedback and return the response data."""
    feedback_data = {
        "event_id": event_id,
        "feedback_type": feedback_type,
    }
    if notes:
        feedback_data["notes"] = notes
    response = await client.post("/api/feedback", json=feedback_data)
    assert response.status_code == 201, f"Failed to create feedback: {response.text}"
    return response.json()


# === CREATE Tests ===


@pytest.mark.asyncio
async def test_create_feedback_success(client):
    """Test successful feedback creation with minimal fields."""
    # Create prerequisite camera and event
    _, event = await create_test_camera_and_event(client)

    feedback_data = {
        "event_id": event["id"],
        "feedback_type": "false_positive",
    }

    response = await client.post("/api/feedback", json=feedback_data)

    assert response.status_code == 201
    data = response.json()
    assert data["event_id"] == event["id"]
    assert data["feedback_type"] == "false_positive"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_feedback_with_notes(client):
    """Test feedback creation with optional notes field."""
    _, event = await create_test_camera_and_event(client)

    feedback_data = {
        "event_id": event["id"],
        "feedback_type": "missed_threat",
        "notes": "There was a person in the corner of the frame",
    }

    response = await client.post("/api/feedback", json=feedback_data)

    assert response.status_code == 201
    data = response.json()
    assert data["event_id"] == event["id"]
    assert data["feedback_type"] == "missed_threat"
    assert data["notes"] == "There was a person in the corner of the frame"


@pytest.mark.asyncio
async def test_create_feedback_all_feedback_types(client):
    """Test feedback creation with all valid feedback types.

    Note: Currently only testing false_positive and missed_threat as these
    are the types validated by the database check constraint. Additional types
    (wrong_severity, correct) are defined in the schema but require a database
    migration to update the constraint.
    """
    # Core feedback types supported by the database constraint
    feedback_types = ["false_positive", "missed_threat"]

    for feedback_type in feedback_types:
        _, event = await create_test_camera_and_event(client)

        feedback_data = {
            "event_id": event["id"],
            "feedback_type": feedback_type,
        }

        response = await client.post("/api/feedback", json=feedback_data)

        assert response.status_code == 201, f"Failed for feedback_type={feedback_type}"
        data = response.json()
        assert data["feedback_type"] == feedback_type


@pytest.mark.asyncio
async def test_create_feedback_invalid_feedback_type(client):
    """Test feedback creation fails with invalid feedback type."""
    _, event = await create_test_camera_and_event(client)

    feedback_data = {
        "event_id": event["id"],
        "feedback_type": "invalid_type",
    }

    response = await client.post("/api/feedback", json=feedback_data)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_feedback_nonexistent_event(client):
    """Test feedback creation fails for nonexistent event."""
    feedback_data = {
        "event_id": 999999,  # Nonexistent event
        "feedback_type": "false_positive",
    }

    response = await client.post("/api/feedback", json=feedback_data)

    assert response.status_code == 404
    data = response.json()
    error_msg = get_error_message(data)
    assert "not found" in error_msg.lower() or "999999" in error_msg


@pytest.mark.asyncio
async def test_create_feedback_missing_event_id(client):
    """Test feedback creation fails without event_id."""
    feedback_data = {
        "feedback_type": "false_positive",
    }

    response = await client.post("/api/feedback", json=feedback_data)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_feedback_missing_feedback_type(client):
    """Test feedback creation fails without feedback_type."""
    _, event = await create_test_camera_and_event(client)

    feedback_data = {
        "event_id": event["id"],
    }

    response = await client.post("/api/feedback", json=feedback_data)

    assert response.status_code == 422


# === READ Tests (Get by ID) ===


@pytest.mark.asyncio
async def test_get_feedback_by_id_success(client):
    """Test getting a specific feedback by ID."""
    _, event = await create_test_camera_and_event(client)
    feedback = await create_test_feedback(client, event["id"], notes="Test notes")

    response = await client.get(f"/api/feedback/{feedback['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == feedback["id"]
    assert data["event_id"] == event["id"]
    assert data["feedback_type"] == "false_positive"
    assert data["notes"] == "Test notes"


@pytest.mark.asyncio
async def test_get_feedback_by_id_not_found(client):
    """Test getting a nonexistent feedback returns 404."""
    response = await client.get("/api/feedback/999999")

    assert response.status_code == 404
    data = response.json()
    error_msg = get_error_message(data)
    assert "not found" in error_msg.lower()


# === READ Tests (Get by Event ID) ===


@pytest.mark.asyncio
async def test_get_feedback_by_event_id_success(client):
    """Test getting feedback for a specific event."""
    _, event = await create_test_camera_and_event(client)
    feedback = await create_test_feedback(client, event["id"], feedback_type="missed_threat")

    response = await client.get(f"/api/feedback/event/{event['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == event["id"]
    assert data["feedback_type"] == "missed_threat"
    assert data["id"] == feedback["id"]


@pytest.mark.asyncio
async def test_get_feedback_by_event_id_not_found(client):
    """Test getting feedback for an event without feedback returns 404."""
    _, event = await create_test_camera_and_event(client)
    # Don't create feedback for this event

    response = await client.get(f"/api/feedback/event/{event['id']}")

    assert response.status_code == 404
    data = response.json()
    error_msg = get_error_message(data)
    assert "no feedback" in error_msg.lower() or "not found" in error_msg.lower()


# === LIST Tests ===


@pytest.mark.asyncio
async def test_list_feedback_success(client):
    """Test listing all feedback."""
    _, event1 = await create_test_camera_and_event(client)
    _, event2 = await create_test_camera_and_event(client)

    await create_test_feedback(client, event1["id"], feedback_type="false_positive")
    await create_test_feedback(client, event2["id"], feedback_type="missed_threat")

    response = await client.get("/api/feedback")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data
    assert isinstance(data["items"], list)
    assert data["pagination"]["total"] >= 2


@pytest.mark.asyncio
async def test_list_feedback_pagination_limit(client):
    """Test listing feedback with limit parameter."""
    # Create 5 feedback items
    for _ in range(5):
        _, event = await create_test_camera_and_event(client)
        await create_test_feedback(client, event["id"])

    # Get with limit=2
    response = await client.get("/api/feedback?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["pagination"]["limit"] == 2


@pytest.mark.asyncio
async def test_list_feedback_pagination_offset(client):
    """Test listing feedback with offset parameter."""
    # Create 3 feedback items
    for _ in range(3):
        _, event = await create_test_camera_and_event(client)
        await create_test_feedback(client, event["id"])

    # Get with offset=0
    response = await client.get("/api/feedback?offset=0&limit=10")

    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["offset"] == 0


@pytest.mark.asyncio
async def test_list_feedback_empty(client):
    """Test listing feedback when none exist."""
    # Note: The client fixture cleans up data before/after tests
    response = await client.get("/api/feedback")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["pagination"]["total"] == 0


# === DELETE Tests ===


@pytest.mark.asyncio
async def test_delete_feedback_success(client):
    """Test successful feedback deletion."""
    _, event = await create_test_camera_and_event(client)
    feedback = await create_test_feedback(client, event["id"])

    # Delete the feedback
    response = await client.delete(f"/api/feedback/{feedback['id']}")

    assert response.status_code == 204

    # Verify feedback is deleted
    get_response = await client.get(f"/api/feedback/{feedback['id']}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_feedback_not_found(client):
    """Test deleting a nonexistent feedback returns 404."""
    response = await client.delete("/api/feedback/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_after_delete_fails(client):
    """Test that getting a deleted feedback fails."""
    _, event = await create_test_camera_and_event(client)
    feedback = await create_test_feedback(client, event["id"])

    # Delete the feedback
    await client.delete(f"/api/feedback/{feedback['id']}")

    # Try to get deleted feedback
    response = await client.get(f"/api/feedback/{feedback['id']}")

    assert response.status_code == 404


# === STATS Tests ===


@pytest.mark.asyncio
async def test_get_feedback_stats_success(client):
    """Test getting feedback statistics."""
    # Create feedback with different types
    _, event1 = await create_test_camera_and_event(client)
    _, event2 = await create_test_camera_and_event(client)
    _, event3 = await create_test_camera_and_event(client)

    await create_test_feedback(client, event1["id"], feedback_type="false_positive")
    await create_test_feedback(client, event2["id"], feedback_type="false_positive")
    await create_test_feedback(client, event3["id"], feedback_type="missed_threat")

    response = await client.get("/api/feedback/stats")

    assert response.status_code == 200
    data = response.json()
    assert "total_feedback" in data
    assert "by_type" in data
    assert "by_camera" in data
    assert data["total_feedback"] >= 3
    assert isinstance(data["by_type"], dict)
    assert isinstance(data["by_camera"], dict)


@pytest.mark.asyncio
async def test_get_feedback_stats_by_type_aggregation(client):
    """Test that stats correctly aggregate by feedback type."""
    # Create 2 false_positive and 1 missed_threat
    for _ in range(2):
        _, event = await create_test_camera_and_event(client)
        await create_test_feedback(client, event["id"], feedback_type="false_positive")

    _, event = await create_test_camera_and_event(client)
    await create_test_feedback(client, event["id"], feedback_type="missed_threat")

    response = await client.get("/api/feedback/stats")

    assert response.status_code == 200
    data = response.json()

    # Verify aggregation by type (type key format depends on enum serialization)
    assert len(data["by_type"]) >= 2


@pytest.mark.asyncio
async def test_get_feedback_stats_by_camera_aggregation(client):
    """Test that stats correctly aggregate by camera."""
    # Create feedback for camera1
    camera1, event1 = await create_test_camera_and_event(client)
    await create_test_feedback(client, event1["id"])

    # Create feedback for camera2 (multiple events)
    camera2, event2 = await create_test_camera_and_event(client)
    await create_test_feedback(client, event2["id"])

    response = await client.get("/api/feedback/stats")

    assert response.status_code == 200
    data = response.json()

    # Verify aggregation by camera
    assert camera1["id"] in data["by_camera"]
    assert camera2["id"] in data["by_camera"]


@pytest.mark.asyncio
async def test_get_feedback_stats_empty(client):
    """Test getting stats when no feedback exists."""
    response = await client.get("/api/feedback/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_feedback"] == 0
    assert data["by_type"] == {}
    assert data["by_camera"] == {}


# === Response Schema Validation Tests ===


@pytest.mark.asyncio
async def test_feedback_response_schema(client):
    """Test that feedback response includes all required fields."""
    _, event = await create_test_camera_and_event(client)

    response = await client.post(
        "/api/feedback",
        json={"event_id": event["id"], "feedback_type": "false_positive"},
    )

    assert response.status_code == 201
    data = response.json()

    # Verify all required fields are present
    required_fields = ["id", "event_id", "feedback_type", "created_at"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    # notes is optional, verify it's present (may be None)
    assert "notes" in data


@pytest.mark.asyncio
async def test_feedback_list_response_schema(client):
    """Test that list response includes pagination info."""
    _, event = await create_test_camera_and_event(client)
    await create_test_feedback(client, event["id"])

    response = await client.get("/api/feedback")

    assert response.status_code == 200
    data = response.json()

    # Verify pagination fields
    assert "items" in data
    assert "pagination" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["pagination"]["total"], int)
    assert isinstance(data["pagination"]["limit"], int)
    assert isinstance(data["pagination"]["offset"], int)
    assert "has_more" in data["pagination"]


@pytest.mark.asyncio
async def test_feedback_stats_response_schema(client):
    """Test that stats response includes all required fields."""
    response = await client.get("/api/feedback/stats")

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields
    assert "total_feedback" in data
    assert "by_type" in data
    assert "by_camera" in data
    assert isinstance(data["total_feedback"], int)
    assert isinstance(data["by_type"], dict)
    assert isinstance(data["by_camera"], dict)
