"""Unit tests for backend.api.routes.events.

These tests cover all event-related API endpoints including:
- GET /api/events - List events with filtering and pagination
- GET /api/events/stats - Get aggregated event statistics
- GET /api/events/{event_id} - Get a specific event
- PATCH /api/events/{event_id} - Update an event
- GET /api/events/{event_id}/detections - Get detections for an event
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from backend.api.routes import events as events_routes
from backend.api.schemas.events import EventUpdate
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.cache_service import CacheService


@pytest.fixture
def mock_response() -> MagicMock:
    """Create a mock Response object for deprecation header tests."""
    return MagicMock(spec=Response)


# =============================================================================
# Module-level Fixtures
# =============================================================================


# Note: Previously this module had an autouse fixture that patched get_cache_service.
# With the migration to FastAPI dependency injection (NEM-1659), cache service is now
# injected via Depends(get_cache_service_dep). If you add API endpoint tests to this
# module, use FastAPI dependency_overrides instead:
#
# @pytest.fixture
# def client(mock_cache_service):
#     app = FastAPI()
#     app.include_router(router)
#     async def override_cache():
#         yield mock_cache_service
#     app.dependency_overrides[get_cache_service_dep] = override_cache
#     with TestClient(app) as test_client:
#         yield test_client


# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_event(
    event_id: int = 1,
    camera_id: str = "cam-001",
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    risk_score: int | None = 75,
    risk_level: str | None = "medium",
    summary: str | None = "Test event",
    reasoning: str | None = None,
    reviewed: bool = False,
    notes: str | None = None,
    detection_ids: str | None = "1,2,3",
    object_types: str | None = None,
) -> MagicMock:
    """Create a mock Event object for testing."""
    mock = MagicMock(spec=Event)
    mock.id = event_id
    mock.camera_id = camera_id
    mock.started_at = started_at or datetime.now(UTC)
    mock.ended_at = ended_at
    mock.risk_score = risk_score
    mock.risk_level = risk_level
    mock.summary = summary
    mock.reasoning = reasoning
    mock.reviewed = reviewed
    mock.notes = notes
    mock.object_types = object_types

    # Mock the detections relationship for detection_id_list and detection_count properties
    if detection_ids:
        # Parse detection_ids to create mock detection objects
        id_list = []
        if isinstance(detection_ids, str):
            # Handle JSON array format
            if detection_ids.startswith("["):
                import json

                id_list = json.loads(detection_ids)
            else:
                # Handle comma-separated format
                id_list = [int(x.strip()) for x in detection_ids.split(",") if x.strip()]
        elif isinstance(detection_ids, list):
            # Already a list
            id_list = detection_ids

        # Create minimal mock detection objects with just id attribute
        mock.detections = [MagicMock(id=det_id) for det_id in id_list]
        # Mock the detection_id_list property (used by Event model)
        mock.detection_id_list = id_list
        # Mock the detection_count property (used by Event model)
        mock.detection_count = len(id_list)
    else:
        mock.detections = []
        mock.detection_id_list = []
        mock.detection_count = 0

    return mock


def create_mock_detection(
    detection_id: int = 1,
    camera_id: str = "cam-001",
    file_path: str = "/export/foscam/front_door/image.jpg",
    object_type: str = "person",
    confidence: float = 0.95,
    detected_at: datetime | None = None,
) -> MagicMock:
    """Create a mock Detection object for testing."""
    mock = MagicMock(spec=Detection)
    mock.id = detection_id
    mock.camera_id = camera_id
    mock.file_path = file_path
    mock.file_type = "image/jpeg"
    mock.media_type = "image"
    mock.video_codec = None
    mock.detected_at = detected_at or datetime.now(UTC)
    mock.object_type = object_type
    mock.confidence = confidence
    mock.bbox_x = 100
    mock.bbox_y = 150
    mock.bbox_width = 200
    mock.bbox_height = 400
    mock.thumbnail_path = "/data/thumbnails/thumb.jpg"
    mock.enrichment_data = {}
    return mock


def create_mock_camera(
    camera_id: str = "cam-001",
    name: str = "Front Door",
) -> MagicMock:
    """Create a mock Camera object for testing."""
    mock = MagicMock(spec=Camera)
    mock.id = camera_id
    mock.name = name
    return mock


# =============================================================================
# list_events Endpoint Tests
# =============================================================================


# =============================================================================
# get_event_stats Endpoint Tests
# =============================================================================


def _create_mock_cache() -> MagicMock:
    """Create a mock cache service for use in tests (NEM-1659).

    This helper creates a mock CacheService that can be passed directly
    to route functions, replacing the previous @patch approach.
    """
    mock_cache = MagicMock(spec=CacheService)
    mock_cache.get = AsyncMock(return_value=None)  # Cache miss
    mock_cache.set = AsyncMock()
    return mock_cache


@pytest.mark.asyncio
async def test_get_event_stats_returns_empty_stats_when_no_events() -> None:
    """Test that get_event_stats returns zero counts when no events exist."""
    mock_cache = _create_mock_cache()
    db = AsyncMock(spec=AsyncSession)

    # Mock total count query - returns 0
    total_count_result = MagicMock()
    total_count_result.scalar.return_value = 0

    # Mock risk level GROUP BY query - empty result
    risk_level_result = MagicMock()
    risk_level_result.all.return_value = []

    # Mock camera stats GROUP BY query - empty result
    camera_stats_result = MagicMock()
    camera_stats_result.all.return_value = []

    db.execute = AsyncMock(side_effect=[total_count_result, risk_level_result, camera_stats_result])

    # Pass cache directly via DI pattern (NEM-1659)
    response = await events_routes.get_event_stats(db=db, cache=mock_cache)

    assert response.total_events == 0
    assert response.events_by_risk_level.critical == 0
    assert response.events_by_risk_level.high == 0
    assert response.events_by_risk_level.medium == 0
    assert response.events_by_risk_level.low == 0
    assert response.events_by_camera == []


@pytest.mark.asyncio
async def test_get_event_stats_counts_events_by_risk_level() -> None:
    """Test that get_event_stats correctly counts events by risk level using SQL GROUP BY."""
    mock_cache = _create_mock_cache()
    db = AsyncMock(spec=AsyncSession)

    # Mock total count query - returns 7
    total_count_result = MagicMock()
    total_count_result.scalar.return_value = 7

    # Mock risk level GROUP BY query - returns tuples of (risk_level, count)
    risk_level_result = MagicMock()
    risk_level_result.all.return_value = [
        ("critical", 2),
        ("high", 1),
        ("medium", 3),
        ("low", 1),
    ]

    # Mock camera stats GROUP BY query - returns tuples of (camera_id, camera_name, count)
    camera_stats_result = MagicMock()
    camera_stats_result.all.return_value = [("cam-001", "Front Door", 7)]

    db.execute = AsyncMock(side_effect=[total_count_result, risk_level_result, camera_stats_result])

    # Pass cache directly via DI pattern (NEM-1659)
    response = await events_routes.get_event_stats(db=db, cache=mock_cache)

    assert response.total_events == 7
    assert response.events_by_risk_level.critical == 2
    assert response.events_by_risk_level.high == 1
    assert response.events_by_risk_level.medium == 3
    assert response.events_by_risk_level.low == 1


@pytest.mark.asyncio
async def test_get_event_stats_counts_events_by_camera() -> None:
    """Test that get_event_stats correctly counts events by camera using SQL GROUP BY."""
    mock_cache = _create_mock_cache()
    db = AsyncMock(spec=AsyncSession)

    # Mock total count query - returns 5
    total_count_result = MagicMock()
    total_count_result.scalar.return_value = 5

    # Mock risk level GROUP BY query
    risk_level_result = MagicMock()
    risk_level_result.all.return_value = [("medium", 5)]

    # Mock camera stats GROUP BY query - returns tuples sorted by count descending
    # Returns (camera_id, camera_name, event_count) tuples
    camera_stats_result = MagicMock()
    camera_stats_result.all.return_value = [
        ("cam-001", "Front Door", 3),
        ("cam-002", "Back Door", 2),
    ]

    db.execute = AsyncMock(side_effect=[total_count_result, risk_level_result, camera_stats_result])

    # Pass cache directly via DI pattern (NEM-1659)
    response = await events_routes.get_event_stats(db=db, cache=mock_cache)

    assert len(response.events_by_camera) == 2
    # Results should be sorted by event count descending (from SQL ORDER BY)
    assert response.events_by_camera[0].camera_id == "cam-001"
    assert response.events_by_camera[0].event_count == 3
    assert response.events_by_camera[0].camera_name == "Front Door"
    assert response.events_by_camera[1].camera_id == "cam-002"
    assert response.events_by_camera[1].event_count == 2


@pytest.mark.asyncio
async def test_get_event_stats_with_unknown_camera() -> None:
    """Test that get_event_stats handles unknown camera IDs (NULL from LEFT JOIN)."""
    mock_cache = _create_mock_cache()
    db = AsyncMock(spec=AsyncSession)

    # Mock total count query - returns 1
    total_count_result = MagicMock()
    total_count_result.scalar.return_value = 1

    # Mock risk level GROUP BY query
    risk_level_result = MagicMock()
    risk_level_result.all.return_value = [("medium", 1)]

    # Mock camera stats GROUP BY query - camera name is None (no matching camera in JOIN)
    camera_stats_result = MagicMock()
    camera_stats_result.all.return_value = [("unknown-cam", None, 1)]

    db.execute = AsyncMock(side_effect=[total_count_result, risk_level_result, camera_stats_result])

    # Pass cache directly via DI pattern (NEM-1659)
    response = await events_routes.get_event_stats(db=db, cache=mock_cache)

    assert len(response.events_by_camera) == 1
    assert response.events_by_camera[0].camera_name == "Unknown"


@pytest.mark.asyncio
async def test_get_event_stats_with_date_filters() -> None:
    """Test that get_event_stats filters by date range."""
    mock_cache = _create_mock_cache()
    db = AsyncMock(spec=AsyncSession)

    now = datetime.now(UTC)

    # Mock total count query - returns 1
    total_count_result = MagicMock()
    total_count_result.scalar.return_value = 1

    # Mock risk level GROUP BY query
    risk_level_result = MagicMock()
    risk_level_result.all.return_value = [("medium", 1)]

    # Mock camera stats GROUP BY query
    camera_stats_result = MagicMock()
    camera_stats_result.all.return_value = [("cam-001", "Front Door", 1)]

    db.execute = AsyncMock(side_effect=[total_count_result, risk_level_result, camera_stats_result])

    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)

    # Pass cache directly via DI pattern (NEM-1659)
    response = await events_routes.get_event_stats(
        start_date=start, end_date=end, db=db, cache=mock_cache
    )

    assert response.total_events == 1


@pytest.mark.asyncio
async def test_get_event_stats_ignores_invalid_risk_levels() -> None:
    """Test that get_event_stats ignores events with invalid risk levels."""
    mock_cache = _create_mock_cache()
    db = AsyncMock(spec=AsyncSession)

    # Mock total count query - returns 3
    total_count_result = MagicMock()
    total_count_result.scalar.return_value = 3

    # Mock risk level GROUP BY query - includes invalid and None levels
    # Only valid levels should be counted in the response
    risk_level_result = MagicMock()
    risk_level_result.all.return_value = [
        ("high", 1),
        ("invalid_level", 1),  # Will be ignored
        (None, 1),  # Will be ignored
    ]

    # Mock camera stats GROUP BY query
    camera_stats_result = MagicMock()
    camera_stats_result.all.return_value = [("cam-001", "Front Door", 3)]

    db.execute = AsyncMock(side_effect=[total_count_result, risk_level_result, camera_stats_result])

    # Pass cache directly via DI pattern (NEM-1659)
    response = await events_routes.get_event_stats(db=db, cache=mock_cache)

    assert response.total_events == 3
    assert response.events_by_risk_level.high == 1
    # Invalid and None risk levels should not be counted
    assert response.events_by_risk_level.critical == 0
    assert response.events_by_risk_level.medium == 0
    assert response.events_by_risk_level.low == 0


# =============================================================================
# get_event Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_returns_event_by_id() -> None:
    """Test that get_event returns the correct event."""
    db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock(spec=Request)

    # Note: risk_level is computed from risk_score (NEM-3398)
    # risk_score=85 falls in the critical range (85-100)
    mock_event = create_mock_event(
        event_id=42,
        camera_id="cam-001",
        risk_score=85,
        risk_level="critical",  # Computed from score (85-100 = critical)
        summary="Person detected",
        reviewed=True,
        notes="Verified",
        detection_ids="1,2,3",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=42, request=mock_request, db=db)

    assert response.id == 42
    assert response.camera_id == "cam-001"
    assert response.risk_score == 85
    assert response.risk_level == "critical"  # Computed from risk_score=85
    assert response.summary == "Person detected"
    assert response.reviewed is True
    assert response.notes == "Verified"
    assert response.detection_count == 3
    assert response.detection_ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_get_event_returns_404_when_not_found() -> None:
    """Test that get_event returns 404 when event doesn't exist."""
    db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock(spec=Request)

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(Exception) as exc_info:
        await events_routes.get_event(event_id=999, request=mock_request, db=db)

    # Check that it's an HTTPException with 404 status
    assert exc_info.value.status_code == 404
    assert "999" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_event_with_no_detection_ids() -> None:
    """Test that get_event handles events with no detection_ids."""
    db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock(spec=Request)

    mock_event = create_mock_event(detection_ids=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=1, request=mock_request, db=db)

    assert response.detection_count == 0
    assert response.detection_ids == []


@pytest.mark.asyncio
async def test_get_event_with_empty_detection_ids() -> None:
    """Test that get_event handles events with empty detection_ids."""
    db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock(spec=Request)

    mock_event = create_mock_event(detection_ids="")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=1, request=mock_request, db=db)

    assert response.detection_count == 0
    assert response.detection_ids == []


@pytest.mark.asyncio
async def test_get_event_includes_all_fields() -> None:
    """Test that get_event includes all required fields in response."""
    db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock(spec=Request)

    now = datetime.now(UTC)
    ended = now + timedelta(minutes=5)

    mock_event = create_mock_event(
        event_id=1,
        camera_id="cam-123",
        started_at=now,
        ended_at=ended,
        risk_score=50,
        risk_level="medium",
        summary="Test summary",
        reviewed=False,
        notes="Test notes",
        detection_ids="1,2",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=1, request=mock_request, db=db)

    assert hasattr(response, "id")
    assert hasattr(response, "camera_id")
    assert hasattr(response, "started_at")
    assert hasattr(response, "ended_at")
    assert hasattr(response, "risk_score")
    assert hasattr(response, "risk_level")
    assert hasattr(response, "summary")
    assert hasattr(response, "reasoning")
    assert hasattr(response, "reviewed")
    assert hasattr(response, "notes")
    assert hasattr(response, "detection_count")
    assert hasattr(response, "detection_ids")
    assert response.detection_ids == [1, 2]


@pytest.mark.asyncio
async def test_get_event_returns_reasoning_field() -> None:
    """Test that get_event returns the reasoning field."""
    db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock(spec=Request)

    mock_event = create_mock_event(
        event_id=42,
        risk_score=85,
        risk_level="high",
        reasoning="Person detected at unusual hour near restricted area",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=42, request=mock_request, db=db)

    assert response.reasoning == "Person detected at unusual hour near restricted area"


@pytest.mark.asyncio
async def test_get_event_returns_none_reasoning_when_not_set() -> None:
    """Test that get_event returns None reasoning when not set."""
    db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock(spec=Request)

    mock_event = create_mock_event(
        event_id=1,
        reasoning=None,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=1, request=mock_request, db=db)

    assert response.reasoning is None


# =============================================================================
# update_event Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_event_marks_as_reviewed() -> None:
    """Test that update_event can mark an event as reviewed."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, reviewed=False)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(reviewed=True)
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    await events_routes.update_event(
        event_id=1,
        update_data=update_data,
        request=mock_request,
        background_tasks=mock_background_tasks,
        db=db,
    )

    assert mock_event.reviewed is True
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(mock_event)


@pytest.mark.asyncio
async def test_update_event_marks_as_not_reviewed() -> None:
    """Test that update_event can mark an event as not reviewed."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, reviewed=True)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(reviewed=False)
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    await events_routes.update_event(
        event_id=1,
        update_data=update_data,
        request=mock_request,
        background_tasks=mock_background_tasks,
        db=db,
    )

    assert mock_event.reviewed is False


@pytest.mark.asyncio
async def test_update_event_updates_notes() -> None:
    """Test that update_event can update event notes."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, notes=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(notes="New notes")
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    await events_routes.update_event(
        event_id=1,
        update_data=update_data,
        request=mock_request,
        background_tasks=mock_background_tasks,
        db=db,
    )

    assert mock_event.notes == "New notes"


@pytest.mark.asyncio
async def test_update_event_clears_notes() -> None:
    """Test that update_event can clear event notes."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, notes="Existing notes")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(notes=None)
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    await events_routes.update_event(
        event_id=1,
        update_data=update_data,
        request=mock_request,
        background_tasks=mock_background_tasks,
        db=db,
    )

    assert mock_event.notes is None


@pytest.mark.asyncio
async def test_update_event_updates_both_reviewed_and_notes() -> None:
    """Test that update_event can update both reviewed and notes."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, reviewed=False, notes=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(reviewed=True, notes="Verified - delivery person")
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    await events_routes.update_event(
        event_id=1,
        update_data=update_data,
        request=mock_request,
        background_tasks=mock_background_tasks,
        db=db,
    )

    assert mock_event.reviewed is True
    assert mock_event.notes == "Verified - delivery person"


@pytest.mark.asyncio
async def test_update_event_returns_404_when_not_found() -> None:
    """Test that update_event returns 404 when event doesn't exist."""
    db = AsyncMock(spec=AsyncSession)

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    update_data = EventUpdate(reviewed=True)
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)

    with pytest.raises(Exception) as exc_info:
        await events_routes.update_event(
            event_id=999,
            update_data=update_data,
            request=mock_request,
            background_tasks=mock_background_tasks,
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert "999" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_update_event_returns_correct_response() -> None:
    """Test that update_event returns the updated event with all fields."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(
        event_id=1,
        camera_id="cam-001",
        risk_score=75,
        risk_level="medium",
        summary="Test summary",
        reviewed=False,
        notes=None,
        detection_ids="1,2,3",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(reviewed=True)
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    response = await events_routes.update_event(
        event_id=1,
        update_data=update_data,
        request=mock_request,
        background_tasks=mock_background_tasks,
        db=db,
    )

    assert response.id == 1
    assert response.camera_id == "cam-001"
    assert response.detection_count == 3
    assert response.detection_ids == [1, 2, 3]
    assert hasattr(response, "started_at")
    assert hasattr(response, "ended_at")
    assert hasattr(response, "risk_score")
    assert hasattr(response, "risk_level")
    assert hasattr(response, "summary")
    assert hasattr(response, "reasoning")
    assert hasattr(response, "reviewed")
    assert hasattr(response, "notes")


@pytest.mark.asyncio
async def test_update_event_preserves_reasoning_field() -> None:
    """Test that update_event preserves reasoning field in response."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(
        event_id=1,
        reasoning="Original reasoning for risk score",
        reviewed=False,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(reviewed=True)
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    response = await events_routes.update_event(
        event_id=1,
        update_data=update_data,
        request=mock_request,
        background_tasks=mock_background_tasks,
        db=db,
    )

    assert response.reasoning == "Original reasoning for risk score"


@pytest.mark.asyncio
async def test_update_event_with_no_changes() -> None:
    """Test that update_event works when no fields are changed."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, reviewed=True, notes="Existing")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    # Empty update - no fields set
    update_data = EventUpdate()
    mock_request = MagicMock(spec=Request)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    response = await events_routes.update_event(
        event_id=1,
        update_data=update_data,
        request=mock_request,
        background_tasks=mock_background_tasks,
        db=db,
    )

    # Should still return a valid response
    assert response.id == 1


# =============================================================================
# get_event_detections Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_detections_returns_detections() -> None:
    """Test that get_event_detections returns detections for an event."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, detection_ids="1,2,3")

    mock_detections = [
        create_mock_detection(detection_id=1),
        create_mock_detection(detection_id=2),
        create_mock_detection(detection_id=3),
    ]

    # Mock event query
    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 3

    # Mock detections query
    detections_result = MagicMock()
    detections_result.scalars.return_value.all.return_value = mock_detections

    db.execute = AsyncMock(side_effect=[event_result, count_result, detections_result])

    response = await events_routes.get_event_detections(
        event_id=1, limit=50, offset=0, order_detections_by="detected_at", db=db
    )

    assert len(response.items) == 3
    assert response.pagination.total == 3
    assert response.pagination.limit == 50
    assert response.pagination.offset == 0


@pytest.mark.asyncio
async def test_get_event_detections_returns_404_when_event_not_found() -> None:
    """Test that get_event_detections returns 404 when event doesn't exist."""
    db = AsyncMock(spec=AsyncSession)

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(Exception) as exc_info:
        await events_routes.get_event_detections(
            event_id=999, limit=50, offset=0, order_detections_by="detected_at", db=db
        )

    assert exc_info.value.status_code == 404
    assert "999" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_event_detections_returns_empty_list_when_no_detections() -> None:
    """Test that get_event_detections returns empty list when event has no detections."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, detection_ids=None)

    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=event_result)

    response = await events_routes.get_event_detections(
        event_id=1, limit=50, offset=0, order_detections_by="detected_at", db=db
    )

    assert response.items == []
    assert response.pagination.total == 0


@pytest.mark.asyncio
async def test_get_event_detections_returns_empty_list_when_empty_string() -> None:
    """Test that get_event_detections returns empty list when detection_ids is empty string."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, detection_ids="")

    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=event_result)

    response = await events_routes.get_event_detections(
        event_id=1, limit=50, offset=0, order_detections_by="detected_at", db=db
    )

    assert response.items == []
    assert response.pagination.total == 0


@pytest.mark.asyncio
async def test_get_event_detections_with_pagination() -> None:
    """Test that get_event_detections supports pagination."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, detection_ids="1,2,3,4,5")

    mock_detections = [
        create_mock_detection(detection_id=3),
        create_mock_detection(detection_id=4),
    ]

    # Mock event query
    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 5

    # Mock detections query
    detections_result = MagicMock()
    detections_result.scalars.return_value.all.return_value = mock_detections

    db.execute = AsyncMock(side_effect=[event_result, count_result, detections_result])

    response = await events_routes.get_event_detections(
        event_id=1, limit=2, offset=2, order_detections_by="detected_at", db=db
    )

    assert len(response.items) == 2
    assert response.pagination.total == 5
    assert response.pagination.limit == 2
    assert response.pagination.offset == 2


@pytest.mark.asyncio
async def test_get_event_detections_handles_whitespace_in_detection_ids() -> None:
    """Test that get_event_detections handles whitespace in detection_ids."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, detection_ids="1, 2 , 3")

    mock_detections = [
        create_mock_detection(detection_id=1),
        create_mock_detection(detection_id=2),
        create_mock_detection(detection_id=3),
    ]

    # Mock event query
    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 3

    # Mock detections query
    detections_result = MagicMock()
    detections_result.scalars.return_value.all.return_value = mock_detections

    db.execute = AsyncMock(side_effect=[event_result, count_result, detections_result])

    response = await events_routes.get_event_detections(
        event_id=1, limit=50, offset=0, order_detections_by="detected_at", db=db
    )

    assert len(response.items) == 3
    assert response.pagination.total == 3


@pytest.mark.asyncio
async def test_get_event_detections_custom_limit() -> None:
    """Test that get_event_detections respects custom limit."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, detection_ids="1,2,3,4,5,6,7,8,9,10")

    mock_detections = [create_mock_detection(detection_id=i) for i in range(1, 6)]

    # Mock event query
    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 10

    # Mock detections query
    detections_result = MagicMock()
    detections_result.scalars.return_value.all.return_value = mock_detections

    db.execute = AsyncMock(side_effect=[event_result, count_result, detections_result])

    response = await events_routes.get_event_detections(
        event_id=1, limit=5, offset=0, order_detections_by="detected_at", db=db
    )

    assert len(response.items) == 5
    assert response.pagination.limit == 5


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_stats_empty_camera_list() -> None:
    """Test that get_event_stats handles case with events but no camera lookup (NULL from JOIN)."""
    mock_cache = _create_mock_cache()
    db = AsyncMock(spec=AsyncSession)

    # Mock total count query - returns 1
    total_count_result = MagicMock()
    total_count_result.scalar.return_value = 1

    # Mock risk level GROUP BY query
    risk_level_result = MagicMock()
    risk_level_result.all.return_value = [("medium", 1)]

    # Mock camera stats GROUP BY query - camera_name is NULL (no matching camera)
    camera_stats_result = MagicMock()
    camera_stats_result.all.return_value = [("cam-001", None, 1)]

    db.execute = AsyncMock(side_effect=[total_count_result, risk_level_result, camera_stats_result])

    # Pass cache directly via DI pattern (NEM-1659)
    response = await events_routes.get_event_stats(db=db, cache=mock_cache)

    assert response.total_events == 1
    assert response.events_by_camera[0].camera_name == "Unknown"


@pytest.mark.asyncio
async def test_get_event_detections_count_returns_zero_on_none() -> None:
    """Test that get_event_detections handles None count result."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, detection_ids="1,2,3")

    # Mock event query
    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event

    # Mock count query returning None
    count_result = MagicMock()
    count_result.scalar.return_value = None

    # Mock detections query
    detections_result = MagicMock()
    detections_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[event_result, count_result, detections_result])

    response = await events_routes.get_event_detections(
        event_id=1, limit=50, offset=0, order_detections_by="detected_at", db=db
    )

    assert response.pagination.total == 0


# =============================================================================
# export_events Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_export_events_returns_csv_streaming_response() -> None:
    """Test that export_events returns a StreamingResponse with CSV content."""
    db = AsyncMock(spec=AsyncSession)

    now = datetime.now(UTC)
    mock_events = [
        create_mock_event(
            event_id=1,
            camera_id="cam-001",
            started_at=now,
            ended_at=now,
            risk_score=75,
            risk_level="medium",
            summary="Person detected",
            reviewed=True,
            detection_ids="1,2,3",
        ),
    ]

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        db=db,
    )

    # Check response type
    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/csv"
    assert "Content-Disposition" in response.headers
    assert "attachment" in response.headers["Content-Disposition"]
    assert "events_export_" in response.headers["Content-Disposition"]
    assert ".csv" in response.headers["Content-Disposition"]


@pytest.mark.asyncio
async def test_export_events_returns_empty_csv_when_no_events() -> None:
    """Test that export_events returns CSV with only headers when no events."""
    db = AsyncMock(spec=AsyncSession)

    # Mock empty events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    # Mock camera query (won't be used since no events)
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        db=db,
    )

    # Check it's a valid response
    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/csv"


@pytest.mark.asyncio
async def test_export_events_with_camera_filter() -> None:
    """Test that export_events filters by camera_id."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, camera_id="cam-001")

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id="cam-001",
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        db=db,
    )

    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)


@pytest.mark.asyncio
async def test_export_events_with_risk_level_filter() -> None:
    """Test that export_events filters by risk_level."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, risk_level="high")

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id=None,
        risk_level="high",
        start_date=None,
        end_date=None,
        reviewed=None,
        db=db,
    )

    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)


@pytest.mark.asyncio
async def test_export_events_with_date_filters() -> None:
    """Test that export_events filters by date range."""
    db = AsyncMock(spec=AsyncSession)

    now = datetime.now(UTC)
    mock_event = create_mock_event(event_id=1, started_at=now)

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id=None,
        risk_level=None,
        start_date=start,
        end_date=end,
        reviewed=None,
        db=db,
    )

    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)


@pytest.mark.asyncio
async def test_export_events_with_reviewed_filter() -> None:
    """Test that export_events filters by reviewed status."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, reviewed=True)

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=True,
        db=db,
    )

    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)


@pytest.mark.asyncio
async def test_export_events_handles_unknown_camera() -> None:
    """Test that export_events shows 'Unknown' for missing camera."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(event_id=1, camera_id="unknown-cam")

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query - no matching cameras
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        db=db,
    )

    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)


@pytest.mark.asyncio
async def test_export_events_handles_none_values() -> None:
    """Test that export_events handles events with None values gracefully."""
    db = AsyncMock(spec=AsyncSession)

    # Event with many None values
    mock_event = create_mock_event(
        event_id=1,
        camera_id="cam-001",
        started_at=datetime.now(UTC),
        ended_at=None,
        risk_score=None,
        risk_level=None,
        summary=None,
        reviewed=False,
        detection_ids=None,
    )

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        db=db,
    )

    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)


@pytest.mark.asyncio
async def test_export_events_multiple_events() -> None:
    """Test that export_events handles multiple events correctly."""
    db = AsyncMock(spec=AsyncSession)

    now = datetime.now(UTC)
    mock_events = [
        create_mock_event(
            event_id=1,
            camera_id="cam-001",
            started_at=now,
            risk_level="high",
            reviewed=True,
        ),
        create_mock_event(
            event_id=2,
            camera_id="cam-002",
            started_at=now - timedelta(hours=1),
            risk_level="medium",
            reviewed=False,
        ),
        create_mock_event(
            event_id=3,
            camera_id="cam-001",
            started_at=now - timedelta(hours=2),
            risk_level="low",
            reviewed=True,
        ),
    ]

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [
        create_mock_camera(camera_id="cam-001", name="Front Door"),
        create_mock_camera(camera_id="cam-002", name="Back Door"),
    ]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock(spec=Request)
    response = await events_routes.export_events(
        request=mock_request,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        db=db,
    )

    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)


# =============================================================================
# Date Range Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_stats_invalid_date_range_returns_400() -> None:
    """Test that get_event_stats returns HTTP 400 when start_date > end_date."""
    from fastapi import HTTPException

    mock_cache = _create_mock_cache()
    db = AsyncMock(spec=AsyncSession)

    # start_date is after end_date
    start_date = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
    end_date = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)

    with pytest.raises(HTTPException) as exc_info:
        # Pass cache directly via DI pattern (NEM-1659)
        await events_routes.get_event_stats(
            start_date=start_date,
            end_date=end_date,
            db=db,
            cache=mock_cache,
        )

    assert exc_info.value.status_code == 400
    assert "start_date" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_export_events_invalid_date_range_returns_400() -> None:
    """Test that export_events returns HTTP 400 when start_date > end_date."""
    from fastapi import HTTPException

    db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock(spec=Request)

    # start_date is after end_date
    start_date = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
    end_date = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)

    with pytest.raises(HTTPException) as exc_info:
        await events_routes.export_events(
            request=mock_request,
            camera_id=None,
            risk_level=None,
            start_date=start_date,
            end_date=end_date,
            reviewed=None,
            db=db,
        )

    assert exc_info.value.status_code == 400
    assert "start_date" in exc_info.value.detail.lower()


# =============================================================================
# Soft Delete Tests
# =============================================================================
