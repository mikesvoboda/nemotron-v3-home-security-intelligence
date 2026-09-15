"""Snapshot tests for feedback API schema validation (NEM-5021).

These tests validate API response schemas using syrupy snapshots.
Structure-only snapshots ensure schema changes are detected while
ignoring dynamic data like timestamps and IDs.

When schemas change intentionally:
1. Review the snapshot diff carefully
2. Run: pytest backend/tests/integration/api/test_feedback_routes_snapshots.py --snapshot-update
3. Commit the updated snapshot file
"""

import uuid

import pytest
from syrupy.assertion import SnapshotAssertion

from backend.tests.conftest import extract_schema


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# === Helper Functions ===


async def create_test_camera_and_event(client) -> tuple[dict, dict]:
    """Create a test camera and event, returning both."""
    from datetime import UTC, datetime

    from backend.core.database import get_session
    from backend.models.camera import Camera
    from backend.models.event import Event

    camera_id = unique_id("camera")

    async with get_session() as db_session:
        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("Test Camera"),
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        db_session.add(camera)
        await db_session.flush()

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


# === POST /api/feedback Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_feedback_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test POST /api/feedback response schema with snapshot."""
    _, event = await create_test_camera_and_event(client)

    feedback_data = {
        "event_id": event["id"],
        "feedback_type": "false_positive",
    }

    response = await client.post("/api/feedback", json=feedback_data)
    assert response.status_code == 201

    schema = extract_schema(response.json())
    assert schema == snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_feedback_with_notes_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test feedback creation with notes field maintains schema."""
    _, event = await create_test_camera_and_event(client)

    feedback_data = {
        "event_id": event["id"],
        "feedback_type": "missed_threat",
        "notes": "There was a person in the corner of the frame",
    }

    response = await client.post("/api/feedback", json=feedback_data)
    assert response.status_code == 201

    schema = extract_schema(response.json())
    assert schema == snapshot


# === GET /api/feedback/event/{id} Snapshots ===
#
# Removed (ledger R-T9-FEEDBACK): GET /api/feedback/{id} and the three
# GET /api/feedback list tests. The shipped router (api/routes/feedback.py)
# registers exactly POST /api/feedback, GET /api/feedback/event/{event_id},
# and GET /api/feedback/stats — there is no list endpoint (GET hit the POST
# route → 405) and no by-id route (→ 404). Testing a 405/404 shape adds no
# contract coverage, so the ghost-endpoint snapshots were dropped rather
# than rewritten.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_feedback_by_event_id_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test GET /api/feedback/event/{id} response schema with snapshot."""
    _, event = await create_test_camera_and_event(client)

    # Create feedback
    await client.post(
        "/api/feedback",
        json={
            "event_id": event["id"],
            "feedback_type": "missed_threat",
        },
    )

    # Get feedback by event ID
    response = await client.get(f"/api/feedback/event/{event['id']}")
    assert response.status_code == 200

    schema = extract_schema(response.json())
    assert schema == snapshot


# === GET /api/feedback Snapshots ===


# (list / pagination / empty-list snapshots removed — see R-T9-FEEDBACK note
# above: GET /api/feedback is not a shipped endpoint.)

# === GET /api/feedback/stats Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_feedback_stats_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test GET /api/feedback/stats response schema with snapshot."""
    # Create feedback with different types
    _, event1 = await create_test_camera_and_event(client)
    _, event2 = await create_test_camera_and_event(client)

    await client.post(
        "/api/feedback",
        json={"event_id": event1["id"], "feedback_type": "false_positive"},
    )
    await client.post(
        "/api/feedback",
        json={"event_id": event2["id"], "feedback_type": "missed_threat"},
    )

    response = await client.get("/api/feedback/stats")
    assert response.status_code == 200

    data = response.json()
    # by_camera is keyed by dynamic test camera ids (unique_id()); collapse it
    # to one representative entry so the snapshot stays key-stable across runs.
    if isinstance(data.get("by_camera"), dict) and data["by_camera"]:
        first = next(iter(data["by_camera"]))
        data["by_camera"] = {"<camera_id>": data["by_camera"][first]}
    schema = extract_schema(data)
    assert schema == snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_feedback_stats_empty_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test stats endpoint schema when no feedback exists."""
    response = await client.get("/api/feedback/stats")
    assert response.status_code == 200

    schema = extract_schema(response.json())
    assert schema == snapshot


# === Error Response Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feedback_not_found_error_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test GET feedback 404 error has consistent schema."""
    response = await client.get("/api/feedback/999999")
    assert response.status_code == 404

    schema = extract_schema(response.json())
    assert schema == snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feedback_invalid_event_error_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test POST feedback with nonexistent event has consistent error schema."""
    response = await client.post(
        "/api/feedback",
        json={
            "event_id": 999999,
            "feedback_type": "false_positive",
        },
    )
    assert response.status_code == 404

    schema = extract_schema(response.json())
    assert schema == snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feedback_validation_error_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test POST feedback validation error has consistent schema."""
    response = await client.post(
        "/api/feedback",
        json={
            "feedback_type": "false_positive",
            # Missing required event_id
        },
    )
    assert response.status_code == 422

    schema = extract_schema(response.json())
    assert schema == snapshot


# === Cross-Endpoint Schema Consistency ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feedback_schema_consistency_across_endpoints(
    client,
    snapshot: SnapshotAssertion,
):
    """Test that feedback objects have identical schema across endpoints."""
    _, event = await create_test_camera_and_event(client)

    # Create feedback
    create_response = await client.post(
        "/api/feedback",
        json={"event_id": event["id"], "feedback_type": "false_positive"},
    )
    create_schema = extract_schema(create_response.json())

    # Get by event ID (the shipped read path — there is no GET /api/feedback/{id})
    get_event_response = await client.get(f"/api/feedback/event/{event['id']}")
    get_event_schema = extract_schema(get_event_response.json())

    # Both should have identical schema
    assert create_schema == get_event_schema

    # Snapshot the common schema
    assert create_schema == snapshot
