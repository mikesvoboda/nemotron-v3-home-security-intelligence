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

from backend.api.routes import events as events_routes
from backend.api.routes.events import parse_detection_ids
from backend.api.schemas.events import EventUpdate

# =============================================================================
# parse_detection_ids Function Tests
# =============================================================================


def test_parse_detection_ids_json_array() -> None:
    """Test parsing a JSON array detection IDs string."""
    result = parse_detection_ids("[1, 2, 3, 4]")
    assert result == [1, 2, 3, 4]


def test_parse_detection_ids_json_array_no_spaces() -> None:
    """Test parsing JSON array without spaces."""
    result = parse_detection_ids("[1,2,3,4]")
    assert result == [1, 2, 3, 4]


def test_parse_detection_ids_single_id() -> None:
    """Test parsing a single detection ID JSON array."""
    result = parse_detection_ids("[42]")
    assert result == [42]


def test_parse_detection_ids_legacy_comma_separated() -> None:
    """Test legacy fallback for comma-separated detection IDs string."""
    result = parse_detection_ids("1,2,3,4")
    assert result == [1, 2, 3, 4]


def test_parse_detection_ids_legacy_with_whitespace() -> None:
    """Test legacy fallback for comma-separated IDs with whitespace."""
    result = parse_detection_ids("1, 2 , 3 ,4")
    assert result == [1, 2, 3, 4]


def test_parse_detection_ids_none() -> None:
    """Test parsing None returns empty list."""
    result = parse_detection_ids(None)
    assert result == []


def test_parse_detection_ids_empty_string() -> None:
    """Test parsing empty string returns empty list."""
    result = parse_detection_ids("")
    assert result == []


def test_parse_detection_ids_whitespace_only() -> None:
    """Test parsing whitespace-only string returns empty list."""
    result = parse_detection_ids("   ")
    assert result == []


def test_parse_detection_ids_trailing_comma() -> None:
    """Test parsing string with trailing comma."""
    result = parse_detection_ids("1,2,3,")
    assert result == [1, 2, 3]


def test_parse_detection_ids_leading_comma() -> None:
    """Test parsing string with leading comma."""
    result = parse_detection_ids(",1,2,3")
    assert result == [1, 2, 3]


def test_parse_detection_ids_multiple_commas() -> None:
    """Test parsing string with multiple consecutive commas."""
    result = parse_detection_ids("1,,2,,,3")
    assert result == [1, 2, 3]


def test_parse_detection_ids_large_numbers() -> None:
    """Test parsing large detection IDs."""
    result = parse_detection_ids("1000000,2000000,3000000")
    assert result == [1000000, 2000000, 3000000]


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
) -> MagicMock:
    """Create a mock Event object for testing."""
    mock = MagicMock()
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
    mock.detection_ids = detection_ids
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
    mock = MagicMock()
    mock.id = detection_id
    mock.camera_id = camera_id
    mock.file_path = file_path
    mock.file_type = "image/jpeg"
    mock.detected_at = detected_at or datetime.now(UTC)
    mock.object_type = object_type
    mock.confidence = confidence
    mock.bbox_x = 100
    mock.bbox_y = 150
    mock.bbox_width = 200
    mock.bbox_height = 400
    mock.thumbnail_path = "/data/thumbnails/thumb.jpg"
    return mock


def create_mock_camera(
    camera_id: str = "cam-001",
    name: str = "Front Door",
) -> MagicMock:
    """Create a mock Camera object for testing."""
    mock = MagicMock()
    mock.id = camera_id
    mock.name = name
    return mock


# =============================================================================
# list_events Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_events_returns_empty_list_when_no_events() -> None:
    """Test that list_events returns an empty list when no events exist."""
    db = AsyncMock()

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert response["events"] == []
    assert response["count"] == 0
    assert response["limit"] == 50
    assert response["offset"] == 0


@pytest.mark.asyncio
async def test_list_events_returns_events_with_detection_count() -> None:
    """Test that list_events returns events with correct detection count."""
    db = AsyncMock()

    mock_event = create_mock_event(detection_ids="1,2,3")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["id"] == 1
    assert response["events"][0]["detection_count"] == 3
    assert response["count"] == 1


@pytest.mark.asyncio
async def test_list_events_returns_detection_ids_array() -> None:
    """Test that list_events returns detection_ids as integer array."""
    db = AsyncMock()

    mock_event = create_mock_event(detection_ids="10,20,30")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["detection_ids"] == [10, 20, 30]
    assert response["events"][0]["detection_count"] == 3


@pytest.mark.asyncio
async def test_list_events_with_empty_detection_ids() -> None:
    """Test that list_events handles events with no detection_ids."""
    db = AsyncMock()

    mock_event = create_mock_event(detection_ids=None)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["detection_count"] == 0


@pytest.mark.asyncio
async def test_list_events_with_empty_string_detection_ids() -> None:
    """Test that list_events handles events with empty string detection_ids."""
    db = AsyncMock()

    mock_event = create_mock_event(detection_ids="")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["detection_count"] == 0


@pytest.mark.asyncio
async def test_list_events_with_camera_id_filter() -> None:
    """Test that list_events filters by camera_id."""
    db = AsyncMock()

    mock_event = create_mock_event(camera_id="cam-001")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id="cam-001",
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["camera_id"] == "cam-001"


@pytest.mark.asyncio
async def test_list_events_with_risk_level_filter() -> None:
    """Test that list_events filters by risk_level."""
    db = AsyncMock()

    mock_event = create_mock_event(risk_level="high")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level="high",
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["risk_level"] == "high"


@pytest.mark.asyncio
async def test_list_events_with_date_filters() -> None:
    """Test that list_events filters by start_date and end_date."""
    db = AsyncMock()

    now = datetime.now(UTC)
    mock_event = create_mock_event(started_at=now)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=start,
        end_date=end,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1


@pytest.mark.asyncio
async def test_list_events_with_reviewed_filter_true() -> None:
    """Test that list_events filters by reviewed=True."""
    db = AsyncMock()

    mock_event = create_mock_event(reviewed=True)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=True,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["reviewed"] is True


@pytest.mark.asyncio
async def test_list_events_with_reviewed_filter_false() -> None:
    """Test that list_events filters by reviewed=False."""
    db = AsyncMock()

    mock_event = create_mock_event(reviewed=False)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=False,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["reviewed"] is False


@pytest.mark.asyncio
async def test_list_events_with_object_type_filter_matching() -> None:
    """Test that list_events filters by object_type when matches exist."""
    db = AsyncMock()

    mock_event = create_mock_event(detection_ids="1,2")

    # Mock detection IDs query for object_type filter
    detection_ids_result = MagicMock()
    detection_ids_result.scalars.return_value.all.return_value = [1, 2]

    # Mock all_events query (returns event_id, detection_ids tuples)
    all_events_result = MagicMock()
    all_events_result.all.return_value = [(1, "[1, 2]")]  # event_id=1, detection_ids=[1,2]

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(
        side_effect=[detection_ids_result, all_events_result, count_result, events_result]
    )

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type="person",
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1


@pytest.mark.asyncio
async def test_list_events_with_object_type_filter_no_matches() -> None:
    """Test that list_events returns empty when no detections match object_type."""
    db = AsyncMock()

    # Mock detection IDs query - no matching detections
    detection_ids_result = MagicMock()
    detection_ids_result.scalars.return_value.all.return_value = []

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[detection_ids_result, count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type="vehicle",
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 0
    assert response["count"] == 0


@pytest.mark.asyncio
async def test_list_events_pagination_with_custom_limit() -> None:
    """Test that list_events respects custom limit parameter."""
    db = AsyncMock()

    mock_events = [create_mock_event(event_id=i) for i in range(1, 4)]

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 10

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=3,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 3
    assert response["limit"] == 3


@pytest.mark.asyncio
async def test_list_events_pagination_with_offset() -> None:
    """Test that list_events respects offset parameter."""
    db = AsyncMock()

    mock_events = [create_mock_event(event_id=i) for i in range(6, 11)]

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 10

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=5,
        db=db,
    )

    assert len(response["events"]) == 5
    assert response["offset"] == 5


@pytest.mark.asyncio
async def test_list_events_multiple_events() -> None:
    """Test that list_events handles multiple events correctly."""
    db = AsyncMock()

    mock_events = [
        create_mock_event(event_id=1, camera_id="cam-001", risk_level="high"),
        create_mock_event(event_id=2, camera_id="cam-002", risk_level="medium"),
        create_mock_event(event_id=3, camera_id="cam-001", risk_level="low"),
    ]

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 3

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 3
    assert response["count"] == 3


@pytest.mark.asyncio
async def test_list_events_detection_ids_with_whitespace() -> None:
    """Test that list_events handles detection_ids with whitespace."""
    db = AsyncMock()

    mock_event = create_mock_event(detection_ids="1, 2, 3 , 4")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["detection_count"] == 4


@pytest.mark.asyncio
async def test_list_events_returns_reasoning_field() -> None:
    """Test that list_events returns the reasoning field for each event."""
    db = AsyncMock()

    mock_event = create_mock_event(
        event_id=1,
        reasoning="Multiple persons detected during late night hours",
    )

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["reasoning"] == "Multiple persons detected during late night hours"


@pytest.mark.asyncio
async def test_list_events_returns_none_reasoning_when_not_set() -> None:
    """Test that list_events returns None reasoning when not set."""
    db = AsyncMock()

    mock_event = create_mock_event(
        event_id=1,
        reasoning=None,
    )

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["reasoning"] is None


# =============================================================================
# get_event_stats Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_stats_returns_empty_stats_when_no_events() -> None:
    """Test that get_event_stats returns zero counts when no events exist."""
    db = AsyncMock()

    # Mock events query - empty result
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(return_value=events_result)

    response = await events_routes.get_event_stats(db=db)

    assert response["total_events"] == 0
    assert response["events_by_risk_level"]["critical"] == 0
    assert response["events_by_risk_level"]["high"] == 0
    assert response["events_by_risk_level"]["medium"] == 0
    assert response["events_by_risk_level"]["low"] == 0
    assert response["events_by_camera"] == []


@pytest.mark.asyncio
async def test_get_event_stats_counts_events_by_risk_level() -> None:
    """Test that get_event_stats correctly counts events by risk level."""
    db = AsyncMock()

    mock_events = [
        create_mock_event(event_id=1, risk_level="critical"),
        create_mock_event(event_id=2, risk_level="critical"),
        create_mock_event(event_id=3, risk_level="high"),
        create_mock_event(event_id=4, risk_level="medium"),
        create_mock_event(event_id=5, risk_level="medium"),
        create_mock_event(event_id=6, risk_level="medium"),
        create_mock_event(event_id=7, risk_level="low"),
    ]

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    response = await events_routes.get_event_stats(db=db)

    assert response["total_events"] == 7
    assert response["events_by_risk_level"]["critical"] == 2
    assert response["events_by_risk_level"]["high"] == 1
    assert response["events_by_risk_level"]["medium"] == 3
    assert response["events_by_risk_level"]["low"] == 1


@pytest.mark.asyncio
async def test_get_event_stats_counts_events_by_camera() -> None:
    """Test that get_event_stats correctly counts events by camera."""
    db = AsyncMock()

    mock_events = [
        create_mock_event(event_id=1, camera_id="cam-001"),
        create_mock_event(event_id=2, camera_id="cam-001"),
        create_mock_event(event_id=3, camera_id="cam-001"),
        create_mock_event(event_id=4, camera_id="cam-002"),
        create_mock_event(event_id=5, camera_id="cam-002"),
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

    response = await events_routes.get_event_stats(db=db)

    assert len(response["events_by_camera"]) == 2
    # Results should be sorted by event count descending
    assert response["events_by_camera"][0]["camera_id"] == "cam-001"
    assert response["events_by_camera"][0]["event_count"] == 3
    assert response["events_by_camera"][0]["camera_name"] == "Front Door"
    assert response["events_by_camera"][1]["camera_id"] == "cam-002"
    assert response["events_by_camera"][1]["event_count"] == 2


@pytest.mark.asyncio
async def test_get_event_stats_with_unknown_camera() -> None:
    """Test that get_event_stats handles unknown camera IDs."""
    db = AsyncMock()

    mock_events = [
        create_mock_event(event_id=1, camera_id="unknown-cam"),
    ]

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    # Mock camera query - no cameras found
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    response = await events_routes.get_event_stats(db=db)

    assert len(response["events_by_camera"]) == 1
    assert response["events_by_camera"][0]["camera_name"] == "Unknown"


@pytest.mark.asyncio
async def test_get_event_stats_with_date_filters() -> None:
    """Test that get_event_stats filters by date range."""
    db = AsyncMock()

    now = datetime.now(UTC)
    mock_events = [
        create_mock_event(event_id=1, started_at=now),
    ]

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)

    response = await events_routes.get_event_stats(start_date=start, end_date=end, db=db)

    assert response["total_events"] == 1


@pytest.mark.asyncio
async def test_get_event_stats_ignores_invalid_risk_levels() -> None:
    """Test that get_event_stats ignores events with invalid risk levels."""
    db = AsyncMock()

    mock_events = [
        create_mock_event(event_id=1, risk_level="high"),
        create_mock_event(event_id=2, risk_level="invalid_level"),
        create_mock_event(event_id=3, risk_level=None),
    ]

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    response = await events_routes.get_event_stats(db=db)

    assert response["total_events"] == 3
    assert response["events_by_risk_level"]["high"] == 1
    # Invalid and None risk levels should not be counted
    assert response["events_by_risk_level"]["critical"] == 0
    assert response["events_by_risk_level"]["medium"] == 0
    assert response["events_by_risk_level"]["low"] == 0


# =============================================================================
# get_event Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_returns_event_by_id() -> None:
    """Test that get_event returns the correct event."""
    db = AsyncMock()

    mock_event = create_mock_event(
        event_id=42,
        camera_id="cam-001",
        risk_score=85,
        risk_level="high",
        summary="Person detected",
        reviewed=True,
        notes="Verified",
        detection_ids="1,2,3",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=42, db=db)

    assert response["id"] == 42
    assert response["camera_id"] == "cam-001"
    assert response["risk_score"] == 85
    assert response["risk_level"] == "high"
    assert response["summary"] == "Person detected"
    assert response["reviewed"] is True
    assert response["notes"] == "Verified"
    assert response["detection_count"] == 3
    assert response["detection_ids"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_get_event_returns_404_when_not_found() -> None:
    """Test that get_event returns 404 when event doesn't exist."""
    db = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(Exception) as exc_info:
        await events_routes.get_event(event_id=999, db=db)

    # Check that it's an HTTPException with 404 status
    assert exc_info.value.status_code == 404
    assert "999" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_event_with_no_detection_ids() -> None:
    """Test that get_event handles events with no detection_ids."""
    db = AsyncMock()

    mock_event = create_mock_event(detection_ids=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=1, db=db)

    assert response["detection_count"] == 0
    assert response["detection_ids"] == []


@pytest.mark.asyncio
async def test_get_event_with_empty_detection_ids() -> None:
    """Test that get_event handles events with empty detection_ids."""
    db = AsyncMock()

    mock_event = create_mock_event(detection_ids="")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=1, db=db)

    assert response["detection_count"] == 0
    assert response["detection_ids"] == []


@pytest.mark.asyncio
async def test_get_event_includes_all_fields() -> None:
    """Test that get_event includes all required fields in response."""
    db = AsyncMock()

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

    response = await events_routes.get_event(event_id=1, db=db)

    assert "id" in response
    assert "camera_id" in response
    assert "started_at" in response
    assert "ended_at" in response
    assert "risk_score" in response
    assert "risk_level" in response
    assert "summary" in response
    assert "reasoning" in response
    assert "reviewed" in response
    assert "notes" in response
    assert "detection_count" in response
    assert "detection_ids" in response
    assert response["detection_ids"] == [1, 2]


@pytest.mark.asyncio
async def test_get_event_returns_reasoning_field() -> None:
    """Test that get_event returns the reasoning field."""
    db = AsyncMock()

    mock_event = create_mock_event(
        event_id=42,
        risk_score=85,
        risk_level="high",
        reasoning="Person detected at unusual hour near restricted area",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=42, db=db)

    assert response["reasoning"] == "Person detected at unusual hour near restricted area"


@pytest.mark.asyncio
async def test_get_event_returns_none_reasoning_when_not_set() -> None:
    """Test that get_event returns None reasoning when not set."""
    db = AsyncMock()

    mock_event = create_mock_event(
        event_id=1,
        reasoning=None,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)

    response = await events_routes.get_event(event_id=1, db=db)

    assert response["reasoning"] is None


# =============================================================================
# update_event Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_event_marks_as_reviewed() -> None:
    """Test that update_event can mark an event as reviewed."""
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, reviewed=False)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(reviewed=True)
    mock_request = MagicMock()
    await events_routes.update_event(
        event_id=1, update_data=update_data, request=mock_request, db=db
    )

    assert mock_event.reviewed is True
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(mock_event)


@pytest.mark.asyncio
async def test_update_event_marks_as_not_reviewed() -> None:
    """Test that update_event can mark an event as not reviewed."""
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, reviewed=True)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(reviewed=False)
    mock_request = MagicMock()
    await events_routes.update_event(
        event_id=1, update_data=update_data, request=mock_request, db=db
    )

    assert mock_event.reviewed is False


@pytest.mark.asyncio
async def test_update_event_updates_notes() -> None:
    """Test that update_event can update event notes."""
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, notes=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(notes="New notes")
    mock_request = MagicMock()
    await events_routes.update_event(
        event_id=1, update_data=update_data, request=mock_request, db=db
    )

    assert mock_event.notes == "New notes"


@pytest.mark.asyncio
async def test_update_event_clears_notes() -> None:
    """Test that update_event can clear event notes."""
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, notes="Existing notes")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(notes=None)
    mock_request = MagicMock()
    await events_routes.update_event(
        event_id=1, update_data=update_data, request=mock_request, db=db
    )

    assert mock_event.notes is None


@pytest.mark.asyncio
async def test_update_event_updates_both_reviewed_and_notes() -> None:
    """Test that update_event can update both reviewed and notes."""
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, reviewed=False, notes=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    update_data = EventUpdate(reviewed=True, notes="Verified - delivery person")
    mock_request = MagicMock()
    await events_routes.update_event(
        event_id=1, update_data=update_data, request=mock_request, db=db
    )

    assert mock_event.reviewed is True
    assert mock_event.notes == "Verified - delivery person"


@pytest.mark.asyncio
async def test_update_event_returns_404_when_not_found() -> None:
    """Test that update_event returns 404 when event doesn't exist."""
    db = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    update_data = EventUpdate(reviewed=True)
    mock_request = MagicMock()

    with pytest.raises(Exception) as exc_info:
        await events_routes.update_event(
            event_id=999, update_data=update_data, request=mock_request, db=db
        )

    assert exc_info.value.status_code == 404
    assert "999" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_update_event_returns_correct_response() -> None:
    """Test that update_event returns the updated event with all fields."""
    db = AsyncMock()

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
    mock_request = MagicMock()
    response = await events_routes.update_event(
        event_id=1, update_data=update_data, request=mock_request, db=db
    )

    assert response["id"] == 1
    assert response["camera_id"] == "cam-001"
    assert response["detection_count"] == 3
    assert response["detection_ids"] == [1, 2, 3]
    assert "started_at" in response
    assert "ended_at" in response
    assert "risk_score" in response
    assert "risk_level" in response
    assert "summary" in response
    assert "reasoning" in response
    assert "reviewed" in response
    assert "notes" in response


@pytest.mark.asyncio
async def test_update_event_preserves_reasoning_field() -> None:
    """Test that update_event preserves reasoning field in response."""
    db = AsyncMock()

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
    mock_request = MagicMock()
    response = await events_routes.update_event(
        event_id=1, update_data=update_data, request=mock_request, db=db
    )

    assert response["reasoning"] == "Original reasoning for risk score"


@pytest.mark.asyncio
async def test_update_event_with_no_changes() -> None:
    """Test that update_event works when no fields are changed."""
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, reviewed=True, notes="Existing")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    # Empty update - no fields set
    update_data = EventUpdate()
    mock_request = MagicMock()
    response = await events_routes.update_event(
        event_id=1, update_data=update_data, request=mock_request, db=db
    )

    # Should still return a valid response
    assert response["id"] == 1


# =============================================================================
# get_event_detections Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_detections_returns_detections() -> None:
    """Test that get_event_detections returns detections for an event."""
    db = AsyncMock()

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

    response = await events_routes.get_event_detections(event_id=1, limit=50, offset=0, db=db)

    assert len(response["detections"]) == 3
    assert response["count"] == 3
    assert response["limit"] == 50
    assert response["offset"] == 0


@pytest.mark.asyncio
async def test_get_event_detections_returns_404_when_event_not_found() -> None:
    """Test that get_event_detections returns 404 when event doesn't exist."""
    db = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(Exception) as exc_info:
        await events_routes.get_event_detections(event_id=999, limit=50, offset=0, db=db)

    assert exc_info.value.status_code == 404
    assert "999" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_event_detections_returns_empty_list_when_no_detections() -> None:
    """Test that get_event_detections returns empty list when event has no detections."""
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, detection_ids=None)

    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=event_result)

    response = await events_routes.get_event_detections(event_id=1, limit=50, offset=0, db=db)

    assert response["detections"] == []
    assert response["count"] == 0


@pytest.mark.asyncio
async def test_get_event_detections_returns_empty_list_when_empty_string() -> None:
    """Test that get_event_detections returns empty list when detection_ids is empty string."""
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, detection_ids="")

    event_result = MagicMock()
    event_result.scalar_one_or_none.return_value = mock_event
    db.execute = AsyncMock(return_value=event_result)

    response = await events_routes.get_event_detections(event_id=1, limit=50, offset=0, db=db)

    assert response["detections"] == []
    assert response["count"] == 0


@pytest.mark.asyncio
async def test_get_event_detections_with_pagination() -> None:
    """Test that get_event_detections supports pagination."""
    db = AsyncMock()

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

    response = await events_routes.get_event_detections(event_id=1, limit=2, offset=2, db=db)

    assert len(response["detections"]) == 2
    assert response["count"] == 5
    assert response["limit"] == 2
    assert response["offset"] == 2


@pytest.mark.asyncio
async def test_get_event_detections_handles_whitespace_in_detection_ids() -> None:
    """Test that get_event_detections handles whitespace in detection_ids."""
    db = AsyncMock()

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

    response = await events_routes.get_event_detections(event_id=1, limit=50, offset=0, db=db)

    assert len(response["detections"]) == 3
    assert response["count"] == 3


@pytest.mark.asyncio
async def test_get_event_detections_custom_limit() -> None:
    """Test that get_event_detections respects custom limit."""
    db = AsyncMock()

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

    response = await events_routes.get_event_detections(event_id=1, limit=5, offset=0, db=db)

    assert len(response["detections"]) == 5
    assert response["limit"] == 5


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_events_with_all_filters_combined() -> None:
    """Test that list_events handles all filters combined."""
    db = AsyncMock()

    now = datetime.now(UTC)
    mock_event = create_mock_event(
        event_id=1,
        camera_id="cam-001",
        risk_level="high",
        reviewed=True,
        started_at=now,
    )

    # Mock detection IDs query for object_type filter
    detection_ids_result = MagicMock()
    detection_ids_result.scalars.return_value.all.return_value = [1]

    # Mock all_events query (to find events containing matching detection IDs)
    all_events_result = MagicMock()
    all_events_result.all.return_value = [(1, "[1]")]  # event_id=1 has detection_id=1

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(
        side_effect=[detection_ids_result, all_events_result, count_result, events_result]
    )

    response = await events_routes.list_events(
        camera_id="cam-001",
        risk_level="high",
        start_date=now - timedelta(hours=1),
        end_date=now + timedelta(hours=1),
        reviewed=True,
        object_type="person",
        limit=10,
        offset=0,
        db=db,
    )

    assert len(response["events"]) == 1


@pytest.mark.asyncio
async def test_get_event_stats_empty_camera_list() -> None:
    """Test that get_event_stats handles case with events but no camera lookup."""
    db = AsyncMock()

    mock_events = [
        create_mock_event(event_id=1, camera_id="cam-001"),
    ]

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    # Mock camera query - camera not found
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    response = await events_routes.get_event_stats(db=db)

    assert response["total_events"] == 1
    assert response["events_by_camera"][0]["camera_name"] == "Unknown"


@pytest.mark.asyncio
async def test_list_events_count_returns_zero_on_none() -> None:
    """Test that list_events handles None count result."""
    db = AsyncMock()

    # Mock count query returning None
    count_result = MagicMock()
    count_result.scalar.return_value = None

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        db=db,
    )

    assert response["count"] == 0


@pytest.mark.asyncio
async def test_get_event_detections_count_returns_zero_on_none() -> None:
    """Test that get_event_detections handles None count result."""
    db = AsyncMock()

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

    response = await events_routes.get_event_detections(event_id=1, limit=50, offset=0, db=db)

    assert response["count"] == 0


# =============================================================================
# export_events Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_export_events_returns_csv_streaming_response() -> None:
    """Test that export_events returns a StreamingResponse with CSV content."""
    db = AsyncMock()

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

    mock_request = MagicMock()
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
    db = AsyncMock()

    # Mock empty events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    # Mock camera query (won't be used since no events)
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock()
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
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, camera_id="cam-001")

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock()
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
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, risk_level="high")

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock()
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
    db = AsyncMock()

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

    mock_request = MagicMock()
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
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, reviewed=True)

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = [create_mock_camera(camera_id="cam-001")]

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock()
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
    db = AsyncMock()

    mock_event = create_mock_event(event_id=1, camera_id="unknown-cam")

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    # Mock camera query - no matching cameras
    camera_result = MagicMock()
    camera_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[events_result, camera_result])

    mock_request = MagicMock()
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
    db = AsyncMock()

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

    mock_request = MagicMock()
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
    db = AsyncMock()

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

    mock_request = MagicMock()
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
