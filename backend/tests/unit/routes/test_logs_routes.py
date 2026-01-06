"""Unit tests for backend.api.routes.logs.

These tests focus on the route logic with mocked database sessions
to achieve high coverage of the logs API endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.api.routes import logs as logs_routes
from backend.api.schemas.logs import FrontendLogCreate, LogEntry, LogsResponse, LogStats
from backend.models.log import Log

# =============================================================================
# List Logs Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_logs_empty_database() -> None:
    """Test listing logs when database is empty."""
    db = AsyncMock()

    # Mock execute for count query - scalar() is sync
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    # Mock execute for logs query - scalars().all() are sync
    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = []

    # Both queries return their respective results
    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source=None,
        search=None,
        start_date=None,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 0
    assert result["logs"] == []
    assert result["limit"] == 100
    assert result["offset"] == 0


@pytest.mark.asyncio
async def test_list_logs_with_results() -> None:
    """Test listing logs returns logs from database."""
    db = AsyncMock()

    # Create mock log objects
    mock_log1 = MagicMock(spec=Log)
    mock_log1.id = 1
    mock_log1.timestamp = datetime.now(UTC)
    mock_log1.level = "INFO"
    mock_log1.component = "api"
    mock_log1.message = "Test message"
    mock_log1.source = "backend"

    mock_log2 = MagicMock(spec=Log)
    mock_log2.id = 2
    mock_log2.timestamp = datetime.now(UTC)
    mock_log2.level = "ERROR"
    mock_log2.component = "api"
    mock_log2.message = "Error message"
    mock_log2.source = "backend"

    # Mock execute for count query
    count_result = MagicMock()
    count_result.scalar.return_value = 2

    # Mock execute for logs query
    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log1, mock_log2]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source=None,
        search=None,
        start_date=None,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 2
    assert len(result["logs"]) == 2


@pytest.mark.asyncio
async def test_list_logs_filter_by_level() -> None:
    """Test listing logs filtered by level."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1
    mock_log.level = "ERROR"

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level="error",  # Should be converted to uppercase
        component=None,
        camera_id=None,
        source=None,
        search=None,
        start_date=None,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 1
    assert len(result["logs"]) == 1


@pytest.mark.asyncio
async def test_list_logs_filter_by_component() -> None:
    """Test listing logs filtered by component."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1
    mock_log.component = "file_watcher"

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level=None,
        component="file_watcher",
        camera_id=None,
        source=None,
        search=None,
        start_date=None,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_logs_filter_by_camera_id() -> None:
    """Test listing logs filtered by camera_id."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1
    mock_log.camera_id = "front_door"

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id="front_door",
        source=None,
        search=None,
        start_date=None,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_logs_filter_by_source() -> None:
    """Test listing logs filtered by source."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1
    mock_log.source = "frontend"

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source="frontend",
        search=None,
        start_date=None,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_logs_filter_by_search() -> None:
    """Test listing logs filtered by search text."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1
    mock_log.message = "Connection timeout error"

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source=None,
        search="timeout",
        start_date=None,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_logs_filter_by_start_date() -> None:
    """Test listing logs filtered by start_date."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1
    mock_log.timestamp = datetime.now(UTC)

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    start_date = datetime.now(UTC) - timedelta(hours=1)

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source=None,
        search=None,
        start_date=start_date,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_logs_filter_by_end_date() -> None:
    """Test listing logs filtered by end_date."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1
    mock_log.timestamp = datetime.now(UTC) - timedelta(hours=2)

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    end_date = datetime.now(UTC) - timedelta(hours=1)

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source=None,
        search=None,
        start_date=None,
        end_date=end_date,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_logs_filter_by_date_range() -> None:
    """Test listing logs filtered by both start and end date."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    start_date = datetime.now(UTC) - timedelta(hours=2)
    end_date = datetime.now(UTC) - timedelta(hours=1)

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source=None,
        search=None,
        start_date=start_date,
        end_date=end_date,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_logs_with_all_filters() -> None:
    """Test listing logs with all filters applied."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 1
    mock_log.level = "ERROR"
    mock_log.component = "file_watcher"
    mock_log.camera_id = "front_door"
    mock_log.source = "backend"
    mock_log.message = "Connection timeout"

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [mock_log]

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level="ERROR",
        component="file_watcher",
        camera_id="front_door",
        source="backend",
        search="timeout",
        start_date=datetime.now(UTC) - timedelta(hours=1),
        end_date=datetime.now(UTC),
        limit=50,
        offset=10,
        db=db,
    )

    assert result["count"] == 1
    assert result["limit"] == 50
    assert result["offset"] == 10


@pytest.mark.asyncio
async def test_list_logs_pagination() -> None:
    """Test listing logs with pagination parameters."""
    db = AsyncMock()

    # Create multiple mock logs
    mock_logs = [MagicMock(spec=Log) for _ in range(5)]
    for i, log in enumerate(mock_logs):
        log.id = i + 11  # IDs 11-15 (second page)

    count_result = MagicMock()
    count_result.scalar.return_value = 15

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = mock_logs

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source=None,
        search=None,
        start_date=None,
        end_date=None,
        limit=5,
        offset=10,
        db=db,
    )

    assert result["count"] == 15
    assert len(result["logs"]) == 5
    assert result["limit"] == 5
    assert result["offset"] == 10


@pytest.mark.asyncio
async def test_list_logs_null_count() -> None:
    """Test listing logs when count returns None."""
    db = AsyncMock()

    count_result = MagicMock()
    count_result.scalar.return_value = None  # Simulate NULL result

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_result, logs_result])

    result = await logs_routes.list_logs(
        level=None,
        component=None,
        camera_id=None,
        source=None,
        search=None,
        start_date=None,
        end_date=None,
        limit=100,
        offset=0,
        db=db,
    )

    assert result["count"] == 0  # Should default to 0 when None


# =============================================================================
# Get Log Stats Endpoint Tests
# =============================================================================


def _create_totals_result(total: int | None, errors: int | None, warnings: int | None) -> MagicMock:
    """Create a mock result for the totals query."""
    totals_row = MagicMock()
    totals_row.total_today = total
    totals_row.errors_today = errors
    totals_row.warnings_today = warnings

    result = MagicMock()
    result.one.return_value = totals_row
    return result


def _create_breakdown_result(
    level_data: list[tuple[str, int]], component_data: list[tuple[str, int]]
) -> MagicMock:
    """Create a mock result for the breakdown query (UNION ALL of level + component)."""
    rows = []

    # Level rows
    for level, count in level_data:
        row = MagicMock()
        row.breakdown_type = "level"
        row.key = level
        row.count = count
        rows.append(row)

    # Component rows
    for component, count in component_data:
        row = MagicMock()
        row.breakdown_type = "component"
        row.key = component
        row.count = count
        rows.append(row)

    result = MagicMock()
    result.__iter__ = lambda _: iter(rows)
    return result


@pytest.mark.asyncio
async def test_get_log_stats_empty_database() -> None:
    """Test getting log stats when database is empty."""
    db = AsyncMock()

    # Optimized query returns two results: totals and breakdowns
    totals_result = _create_totals_result(0, 0, 0)
    breakdown_result = _create_breakdown_result([], [])

    db.execute = AsyncMock(side_effect=[totals_result, breakdown_result])

    result = await logs_routes.get_log_stats(db=db)

    assert result["total_today"] == 0
    assert result["errors_today"] == 0
    assert result["warnings_today"] == 0
    assert result["by_component"] == {}
    assert result["by_level"] == {}
    assert result["top_component"] is None


@pytest.mark.asyncio
async def test_get_log_stats_with_data() -> None:
    """Test getting log stats with actual data."""
    db = AsyncMock()

    # Totals query result
    totals_result = _create_totals_result(150, 10, 25)

    # Breakdown query result (UNION ALL of level and component)
    level_data = [("INFO", 115), ("WARNING", 25), ("ERROR", 10)]
    component_data = [("file_watcher", 80), ("api", 50), ("detector", 20)]
    breakdown_result = _create_breakdown_result(level_data, component_data)

    db.execute = AsyncMock(side_effect=[totals_result, breakdown_result])

    result = await logs_routes.get_log_stats(db=db)

    assert result["total_today"] == 150
    assert result["errors_today"] == 10
    assert result["warnings_today"] == 25
    assert result["by_component"]["file_watcher"] == 80
    assert result["by_component"]["api"] == 50
    assert result["by_component"]["detector"] == 20
    assert result["by_level"]["INFO"] == 115
    assert result["by_level"]["WARNING"] == 25
    assert result["by_level"]["ERROR"] == 10
    assert result["top_component"] == "file_watcher"


@pytest.mark.asyncio
async def test_get_log_stats_null_values() -> None:
    """Test getting log stats when queries return None."""
    db = AsyncMock()

    # Totals with None values (should default to 0)
    totals_result = _create_totals_result(None, None, None)
    breakdown_result = _create_breakdown_result([], [])

    db.execute = AsyncMock(side_effect=[totals_result, breakdown_result])

    result = await logs_routes.get_log_stats(db=db)

    assert result["total_today"] == 0
    assert result["errors_today"] == 0
    assert result["warnings_today"] == 0
    assert result["top_component"] is None


@pytest.mark.asyncio
async def test_get_log_stats_single_component() -> None:
    """Test getting log stats with only one component."""
    db = AsyncMock()

    totals_result = _create_totals_result(50, 5, 10)

    level_data = [("INFO", 35)]
    component_data = [("api", 50)]
    breakdown_result = _create_breakdown_result(level_data, component_data)

    db.execute = AsyncMock(side_effect=[totals_result, breakdown_result])

    result = await logs_routes.get_log_stats(db=db)

    assert result["top_component"] == "api"
    assert result["by_component"]["api"] == 50


@pytest.mark.asyncio
async def test_get_log_stats_component_sorting() -> None:
    """Test that components are sorted by count descending for top_component."""
    db = AsyncMock()

    totals_result = _create_totals_result(100, 5, 10)

    # Components returned in arbitrary order from DB
    level_data = [("INFO", 85)]
    component_data = [("api", 20), ("detector", 50), ("file_watcher", 30)]
    breakdown_result = _create_breakdown_result(level_data, component_data)

    db.execute = AsyncMock(side_effect=[totals_result, breakdown_result])

    result = await logs_routes.get_log_stats(db=db)

    # Should be sorted by count descending
    assert result["top_component"] == "detector"
    component_keys = list(result["by_component"].keys())
    assert component_keys == ["detector", "file_watcher", "api"]


# =============================================================================
# Get Single Log Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_log_found() -> None:
    """Test getting a single log by ID when it exists."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 42
    mock_log.timestamp = datetime.now(UTC)
    mock_log.level = "INFO"
    mock_log.component = "api"
    mock_log.message = "Test message"
    mock_log.source = "backend"
    mock_log.camera_id = None
    mock_log.event_id = None
    mock_log.request_id = None
    mock_log.detection_id = None
    mock_log.duration_ms = None
    mock_log.extra = None

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_log

    db.execute = AsyncMock(return_value=result)

    log = await logs_routes.get_log(log_id=42, db=db)

    assert log.id == 42
    assert log.message == "Test message"


@pytest.mark.asyncio
async def test_get_log_not_found() -> None:
    """Test getting a single log by ID when it doesn't exist."""
    db = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc_info:
        await logs_routes.get_log(log_id=99999, db=db)

    assert exc_info.value.status_code == 404
    assert "Log 99999 not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_log_with_all_fields() -> None:
    """Test getting a log with all optional fields populated."""
    db = AsyncMock()

    mock_log = MagicMock(spec=Log)
    mock_log.id = 100
    mock_log.timestamp = datetime.now(UTC)
    mock_log.level = "ERROR"
    mock_log.component = "detector"
    mock_log.message = "Detection failed"
    mock_log.source = "backend"
    mock_log.camera_id = "front_door"
    mock_log.event_id = 5
    mock_log.request_id = "abc-123"
    mock_log.detection_id = 10
    mock_log.duration_ms = 150
    mock_log.extra = {"error_code": 500}

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_log

    db.execute = AsyncMock(return_value=result)

    log = await logs_routes.get_log(log_id=100, db=db)

    assert log.id == 100
    assert log.camera_id == "front_door"
    assert log.event_id == 5
    assert log.detection_id == 10


# =============================================================================
# Create Frontend Log Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_frontend_log_basic() -> None:
    """Test creating a basic frontend log."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    request = MagicMock()
    request.headers.get.return_value = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    log_data = FrontendLogCreate(
        level="ERROR",
        component="DashboardPage",
        message="Failed to load events",
        extra=None,
        user_agent=None,
    )

    result = await logs_routes.create_frontend_log(log_data=log_data, request=request, db=db)

    assert result == {"status": "created"}
    db.add.assert_called_once()
    db.commit.assert_called_once()

    # Verify the log object was created correctly
    added_log = db.add.call_args[0][0]
    assert added_log.level == "ERROR"
    assert added_log.component == "DashboardPage"
    assert added_log.message == "Failed to load events"
    assert added_log.source == "frontend"
    assert added_log.user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


@pytest.mark.asyncio
async def test_create_frontend_log_with_user_agent_in_payload() -> None:
    """Test creating a frontend log with user_agent provided in payload."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    request = MagicMock()
    request.headers.get.return_value = "Default User Agent"

    log_data = FrontendLogCreate(
        level="WARNING",
        component="EventCard",
        message="Slow render detected",
        extra={"render_time_ms": 500},
        user_agent="Custom User Agent",
    )

    result = await logs_routes.create_frontend_log(log_data=log_data, request=request, db=db)

    assert result == {"status": "created"}

    # Should use user_agent from payload, not from headers
    added_log = db.add.call_args[0][0]
    assert added_log.user_agent == "Custom User Agent"


@pytest.mark.asyncio
async def test_create_frontend_log_with_extra_data() -> None:
    """Test creating a frontend log with extra structured data."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    request = MagicMock()
    request.headers.get.return_value = "TestAgent/1.0"

    log_data = FrontendLogCreate(
        level="INFO",
        component="CameraGrid",
        message="Camera view changed",
        extra={
            "previous_camera": "front_door",
            "new_camera": "back_yard",
            "timestamp": "2025-12-27T10:00:00Z",
        },
        user_agent=None,
    )

    result = await logs_routes.create_frontend_log(log_data=log_data, request=request, db=db)

    assert result == {"status": "created"}

    added_log = db.add.call_args[0][0]
    assert added_log.extra["previous_camera"] == "front_door"
    assert added_log.extra["new_camera"] == "back_yard"


@pytest.mark.asyncio
async def test_create_frontend_log_level_normalized() -> None:
    """Test that log level is normalized to uppercase."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    request = MagicMock()
    request.headers.get.return_value = None

    log_data = FrontendLogCreate(
        level="DEBUG",  # Lowercase in schema validation
        component="TestComponent",
        message="Debug message",
        extra=None,
        user_agent=None,
    )

    await logs_routes.create_frontend_log(log_data=log_data, request=request, db=db)

    added_log = db.add.call_args[0][0]
    assert added_log.level == "DEBUG"  # Should be uppercase


@pytest.mark.asyncio
async def test_create_frontend_log_no_user_agent() -> None:
    """Test creating a frontend log when no user_agent is available."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    request = MagicMock()
    request.headers.get.return_value = None  # No user-agent header

    log_data = FrontendLogCreate(
        level="ERROR",
        component="ErrorBoundary",
        message="Uncaught exception",
        extra=None,
        user_agent=None,  # No user_agent in payload
    )

    result = await logs_routes.create_frontend_log(log_data=log_data, request=request, db=db)

    assert result == {"status": "created"}

    added_log = db.add.call_args[0][0]
    assert added_log.user_agent is None


@pytest.mark.asyncio
async def test_create_frontend_log_all_log_levels() -> None:
    """Test creating frontend logs with all valid log levels."""
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        request = MagicMock()
        request.headers.get.return_value = "TestAgent"

        log_data = FrontendLogCreate(
            level=level,
            component="TestComponent",
            message=f"Test {level} message",
            extra=None,
            user_agent=None,
        )

        result = await logs_routes.create_frontend_log(log_data=log_data, request=request, db=db)

        assert result == {"status": "created"}
        added_log = db.add.call_args[0][0]
        assert added_log.level == level


@pytest.mark.asyncio
async def test_create_frontend_log_timestamp_is_set() -> None:
    """Test that timestamp is set on created log."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    request = MagicMock()
    request.headers.get.return_value = "TestAgent"

    before_create = datetime.now(UTC)

    log_data = FrontendLogCreate(
        level="INFO",
        component="TestComponent",
        message="Test message",
        extra=None,
        user_agent=None,
    )

    await logs_routes.create_frontend_log(log_data=log_data, request=request, db=db)

    after_create = datetime.now(UTC)

    added_log = db.add.call_args[0][0]
    assert added_log.timestamp >= before_create
    assert added_log.timestamp <= after_create


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestLogEntrySchema:
    """Tests for LogEntry schema validation."""

    def test_log_entry_valid(self):
        """Test LogEntry with valid data."""
        data = {
            "id": 1,
            "timestamp": datetime.now(UTC),
            "level": "INFO",
            "component": "api",
            "message": "Test message",
            "source": "backend",
        }
        entry = LogEntry(**data)
        assert entry.id == 1
        assert entry.level == "INFO"

    def test_log_entry_with_all_fields(self):
        """Test LogEntry with all optional fields."""
        data = {
            "id": 1,
            "timestamp": datetime.now(UTC),
            "level": "ERROR",
            "component": "detector",
            "message": "Detection failed",
            "camera_id": "front_door",
            "event_id": 5,
            "request_id": "abc-123",
            "detection_id": 10,
            "duration_ms": 150,
            "extra": {"error_code": 500},
            "source": "backend",
        }
        entry = LogEntry(**data)
        assert entry.camera_id == "front_door"
        assert entry.event_id == 5
        assert entry.duration_ms == 150


class TestLogsResponseSchema:
    """Tests for LogsResponse schema validation."""

    def test_logs_response_valid(self):
        """Test LogsResponse with valid data."""
        data = {
            "logs": [],
            "count": 0,
            "limit": 100,
            "offset": 0,
        }
        response = LogsResponse(**data)
        assert response.count == 0
        assert response.limit == 100

    def test_logs_response_with_logs(self):
        """Test LogsResponse with log entries."""
        data = {
            "logs": [
                {
                    "id": 1,
                    "timestamp": datetime.now(UTC),
                    "level": "INFO",
                    "component": "api",
                    "message": "Test message",
                    "source": "backend",
                }
            ],
            "count": 1,
            "limit": 100,
            "offset": 0,
        }
        response = LogsResponse(**data)
        assert len(response.logs) == 1
        assert response.count == 1


class TestLogStatsSchema:
    """Tests for LogStats schema validation."""

    def test_log_stats_valid(self):
        """Test LogStats with valid data."""
        data = {
            "total_today": 100,
            "errors_today": 5,
            "warnings_today": 10,
            "by_component": {"api": 50, "detector": 50},
            "by_level": {"INFO": 85, "WARNING": 10, "ERROR": 5},
            "top_component": "api",
        }
        stats = LogStats(**data)
        assert stats.total_today == 100
        assert stats.top_component == "api"

    def test_log_stats_empty(self):
        """Test LogStats with empty data."""
        data = {
            "total_today": 0,
            "errors_today": 0,
            "warnings_today": 0,
            "by_component": {},
            "by_level": {},
            "top_component": None,
        }
        stats = LogStats(**data)
        assert stats.total_today == 0
        assert stats.top_component is None


class TestFrontendLogCreateSchema:
    """Tests for FrontendLogCreate schema validation."""

    def test_frontend_log_create_valid(self):
        """Test FrontendLogCreate with valid data."""
        data = {
            "level": "ERROR",
            "component": "DashboardPage",
            "message": "Test error message",
        }
        log = FrontendLogCreate(**data)
        assert log.level == "ERROR"
        assert log.component == "DashboardPage"

    def test_frontend_log_create_with_all_fields(self):
        """Test FrontendLogCreate with all optional fields."""
        data = {
            "level": "WARNING",
            "component": "EventCard",
            "message": "Slow render",
            "extra": {"render_time": 500},
            "user_agent": "Test/1.0",
            "url": "http://localhost:3000/events",
        }
        log = FrontendLogCreate(**data)
        assert log.extra["render_time"] == 500
        assert log.user_agent == "Test/1.0"
        assert log.url == "http://localhost:3000/events"

    def test_frontend_log_create_invalid_level(self):
        """Test FrontendLogCreate rejects invalid log level."""
        from pydantic import ValidationError

        data = {
            "level": "INVALID",
            "component": "TestComponent",
            "message": "Test message",
        }
        with pytest.raises(ValidationError):
            FrontendLogCreate(**data)
