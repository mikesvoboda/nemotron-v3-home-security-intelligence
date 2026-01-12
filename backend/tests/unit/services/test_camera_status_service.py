"""Unit tests for CameraStatusService (NEM-1982, NEM-2295).

Tests for WebSocket camera status change broadcasting when camera status changes.

NEM-2295: Added tests for event_type, timestamp, and details fields.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.websocket import WebSocketCameraEventType
from backend.models import Camera
from backend.services.camera_status_service import (
    CameraStatusService,
    _get_event_type_for_status,
    broadcast_camera_status_change,
)


@pytest.fixture(autouse=True)
def _enable_log_capture(caplog: pytest.LogCaptureFixture) -> None:
    """Automatically enable INFO-level log capture for all tests."""
    caplog.set_level(logging.INFO)


class _FakeRedis:
    """Fake Redis client for testing."""

    def __init__(self) -> None:
        self.subscribe = AsyncMock(return_value=None)
        self.unsubscribe = AsyncMock(return_value=None)
        self.publish = AsyncMock(return_value=1)


def _create_mock_camera(
    camera_id: str = "front_door",
    name: str = "Front Door Camera",
    status: str = "online",
    folder_path: str = "/export/foscam/front_door",
) -> MagicMock:
    """Create a mock camera for testing."""
    camera = MagicMock(spec=Camera)
    camera.id = camera_id
    camera.name = name
    camera.status = status
    camera.folder_path = folder_path
    camera.created_at = datetime.now(UTC)
    camera.last_seen_at = None
    camera.deleted_at = None
    return camera


# ==============================================================================
# Tests for CameraStatusService
# ==============================================================================


@pytest.mark.asyncio
async def test_set_camera_status_updates_database_and_broadcasts() -> None:
    """Test set_camera_status updates the database and broadcasts via WebSocket.

    NEM-1982: Core functionality - status updates should be saved and broadcast.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    # Create mock camera with initial online status
    mock_camera = _create_mock_camera(status="online")

    # Mock repository methods
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    # Mock set_status to update the camera status
    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    # Mock the broadcaster
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        result = await service.set_camera_status(
            camera_id="front_door",
            status="offline",
            reason="Connection timeout",
        )

    # Verify database was updated
    mock_repo.set_status.assert_awaited_once_with("front_door", "offline")

    # Verify broadcast was called
    mock_broadcaster.broadcast_camera_status.assert_awaited_once()
    call_args = mock_broadcaster.broadcast_camera_status.await_args.args[0]
    assert call_args["camera_id"] == "front_door"
    assert call_args["camera_name"] == "Front Door Camera"
    assert call_args["status"] == "offline"
    assert call_args["previous_status"] == "online"
    assert call_args["reason"] == "Connection timeout"
    # NEM-2295: Verify new event_type and timestamp fields
    assert call_args["event_type"] == "camera.offline"
    assert "timestamp" in call_args
    assert call_args["details"] is None

    # Verify result
    assert result is not None
    assert result.status == "offline"


@pytest.mark.asyncio
async def test_set_camera_status_skips_unchanged_status() -> None:
    """Test set_camera_status skips update when status hasn't changed.

    NEM-1982: Don't broadcast if status is already the same.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    # Camera already offline
    mock_camera = _create_mock_camera(status="offline")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)
    mock_repo.set_status = AsyncMock()

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    result = await service.set_camera_status(
        camera_id="front_door",
        status="offline",
    )

    # Should return camera without updating
    assert result is mock_camera
    # set_status should NOT have been called
    mock_repo.set_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_camera_status_returns_none_for_missing_camera() -> None:
    """Test set_camera_status returns None when camera doesn't exist.

    NEM-1982: Non-existent cameras should be handled gracefully.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    result = await service.set_camera_status(
        camera_id="nonexistent",
        status="offline",
    )

    assert result is None


@pytest.mark.asyncio
async def test_set_camera_online_convenience_method() -> None:
    """Test set_camera_online sets status to online.

    NEM-1982: Convenience method for online status changes.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    mock_camera = _create_mock_camera(status="offline")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        result = await service.set_camera_online(
            camera_id="front_door",
            reason="Camera reconnected",
        )

    mock_repo.set_status.assert_awaited_once_with("front_door", "online")
    assert result is not None
    assert result.status == "online"


@pytest.mark.asyncio
async def test_set_camera_offline_convenience_method() -> None:
    """Test set_camera_offline sets status to offline.

    NEM-1982: Convenience method for offline status changes.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    mock_camera = _create_mock_camera(status="online")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        result = await service.set_camera_offline(
            camera_id="front_door",
            reason="No activity detected",
        )

    mock_repo.set_status.assert_awaited_once_with("front_door", "offline")
    assert result is not None
    assert result.status == "offline"


@pytest.mark.asyncio
async def test_set_camera_error_convenience_method() -> None:
    """Test set_camera_error sets status to error.

    NEM-1982: Convenience method for error status changes.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    mock_camera = _create_mock_camera(status="online")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        result = await service.set_camera_error(
            camera_id="front_door",
            reason="Hardware malfunction",
        )

    mock_repo.set_status.assert_awaited_once_with("front_door", "error")
    assert result is not None
    assert result.status == "error"


@pytest.mark.asyncio
async def test_broadcast_error_doesnt_fail_status_update(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that broadcast errors don't fail the database update.

    NEM-1982: Broadcasting is best-effort - database update is the primary operation.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    mock_camera = _create_mock_camera(status="online")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    # Broadcaster that fails
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(side_effect=RuntimeError("Redis down"))

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        # Should NOT raise despite broadcast failure
        result = await service.set_camera_status(
            camera_id="front_door",
            status="offline",
        )

    # Database update should still succeed
    assert result is not None
    assert result.status == "offline"

    # Error should be logged
    assert "Failed to broadcast camera status change" in caplog.text


@pytest.mark.asyncio
async def test_set_camera_status_logs_info_on_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test set_camera_status logs info on successful broadcast.

    NEM-1982: Status changes should be logged for observability.
    """
    mock_session = MagicMock()
    mock_redis = _FakeRedis()

    mock_camera = _create_mock_camera(status="online")

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_camera)

    async def mock_set_status(camera_id: str, status: str) -> Camera:
        mock_camera.status = status
        return mock_camera

    mock_repo.set_status = AsyncMock(side_effect=mock_set_status)

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=2)

    service = CameraStatusService(mock_session, mock_redis)  # type: ignore[arg-type]
    service._repository = mock_repo

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        await service.set_camera_status(
            camera_id="front_door",
            status="offline",
        )

    # Info log should contain relevant details
    assert any(
        "Broadcast camera status change" in record.message
        and "front_door" in record.message
        and "online" in record.message
        and "offline" in record.message
        for record in caplog.records
    )


# ==============================================================================
# Tests for broadcast_camera_status_change standalone function
# ==============================================================================


@pytest.mark.asyncio
async def test_broadcast_camera_status_change_function() -> None:
    """Test standalone broadcast_camera_status_change function.

    NEM-1982: Standalone function for broadcasting when database is already updated.
    """
    mock_redis = _FakeRedis()

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=3)

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        result = await broadcast_camera_status_change(
            redis=mock_redis,  # type: ignore[arg-type]
            camera_id="back_yard",
            camera_name="Back Yard Camera",
            status="online",
            previous_status="offline",
            reason="Camera reconnected",
        )

    assert result == 3
    mock_broadcaster.broadcast_camera_status.assert_awaited_once()

    call_args = mock_broadcaster.broadcast_camera_status.await_args.args[0]
    assert call_args["camera_id"] == "back_yard"
    assert call_args["camera_name"] == "Back Yard Camera"
    assert call_args["status"] == "online"
    assert call_args["previous_status"] == "offline"
    assert call_args["reason"] == "Camera reconnected"
    # NEM-2295: Verify new event_type and timestamp fields
    assert call_args["event_type"] == "camera.online"
    assert "timestamp" in call_args
    assert call_args["details"] is None


@pytest.mark.asyncio
async def test_broadcast_camera_status_change_without_optional_fields() -> None:
    """Test broadcast_camera_status_change with minimal required fields.

    NEM-1982: Optional fields can be omitted.
    """
    mock_redis = _FakeRedis()

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        await broadcast_camera_status_change(
            redis=mock_redis,  # type: ignore[arg-type]
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="error",
        )

    call_args = mock_broadcaster.broadcast_camera_status.await_args.args[0]
    assert call_args["previous_status"] is None
    assert call_args["reason"] is None
    # NEM-2295: Verify new event_type and timestamp fields
    assert call_args["event_type"] == "camera.error"
    assert "timestamp" in call_args
    assert call_args["details"] is None


# ==============================================================================
# Tests for event type mapping (NEM-2295)
# ==============================================================================


def test_get_event_type_for_online_status() -> None:
    """Test _get_event_type_for_status returns camera.online for online status."""
    assert _get_event_type_for_status("online") == WebSocketCameraEventType.CAMERA_ONLINE


def test_get_event_type_for_offline_status() -> None:
    """Test _get_event_type_for_status returns camera.offline for offline status."""
    assert _get_event_type_for_status("offline") == WebSocketCameraEventType.CAMERA_OFFLINE


def test_get_event_type_for_error_status() -> None:
    """Test _get_event_type_for_status returns camera.error for error status."""
    assert _get_event_type_for_status("error") == WebSocketCameraEventType.CAMERA_ERROR


def test_get_event_type_for_unknown_status() -> None:
    """Test _get_event_type_for_status returns camera.updated for unknown status."""
    assert _get_event_type_for_status("unknown") == WebSocketCameraEventType.CAMERA_UPDATED


def test_get_event_type_for_arbitrary_status() -> None:
    """Test _get_event_type_for_status returns camera.updated for arbitrary status values."""
    assert _get_event_type_for_status("custom_status") == WebSocketCameraEventType.CAMERA_UPDATED


def test_get_event_type_case_insensitive() -> None:
    """Test _get_event_type_for_status handles different cases."""
    assert _get_event_type_for_status("ONLINE") == WebSocketCameraEventType.CAMERA_ONLINE
    assert _get_event_type_for_status("Offline") == WebSocketCameraEventType.CAMERA_OFFLINE
    assert _get_event_type_for_status("ERROR") == WebSocketCameraEventType.CAMERA_ERROR


@pytest.mark.asyncio
async def test_broadcast_camera_status_change_with_explicit_event_type() -> None:
    """Test broadcast_camera_status_change with explicit event_type parameter.

    NEM-2295: Test that explicit event_type overrides derived event type.
    """
    mock_redis = _FakeRedis()

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        await broadcast_camera_status_change(
            redis=mock_redis,  # type: ignore[arg-type]
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="online",
            event_type=WebSocketCameraEventType.CAMERA_UPDATED,  # Override
        )

    call_args = mock_broadcaster.broadcast_camera_status.await_args.args[0]
    # Should use explicit event_type, not derived from status
    assert call_args["event_type"] == "camera.updated"


@pytest.mark.asyncio
async def test_broadcast_camera_status_change_with_details() -> None:
    """Test broadcast_camera_status_change with details parameter.

    NEM-2295: Test that details are included in the broadcast.
    """
    mock_redis = _FakeRedis()

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_camera_status = AsyncMock(return_value=1)

    details = {
        "firmware_version": "2.1.0",
        "ip_address": "192.168.1.100",
    }

    with patch(
        "backend.services.camera_status_service.get_broadcaster",
        return_value=mock_broadcaster,
    ):
        await broadcast_camera_status_change(
            redis=mock_redis,  # type: ignore[arg-type]
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="online",
            details=details,
        )

    call_args = mock_broadcaster.broadcast_camera_status.await_args.args[0]
    assert call_args["details"] == details
