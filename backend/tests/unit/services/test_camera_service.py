"""Unit tests for CameraService.

Tests the camera service's optimistic concurrency control logic
and WebSocket event emission with debouncing using mocked dependencies.

Run with: uv run pytest backend/tests/unit/services/test_camera_service.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.websocket.event_types import WebSocketEventType
from backend.services.camera_service import (
    CAMERA_DEBOUNCE_KEY_PREFIX,
    CAMERA_STATUS_DEBOUNCE_SECONDS,
    CameraService,
    _map_status_string_to_enum,
    get_camera_service,
)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_camera():
    """Create a mock camera object."""
    camera = MagicMock()
    camera.id = "front_door"
    camera.name = "Front Door Camera"
    camera.status = "online"
    camera.last_seen_at = datetime.now(UTC)
    camera.folder_path = "/export/foscam/front_door"
    return camera


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_emitter():
    """Create a mock WebSocket emitter."""
    emitter = MagicMock()
    emitter.emit = AsyncMock(return_value=True)
    return emitter


@pytest.fixture
def mock_camera_offline():
    """Create a mock camera with offline status."""
    camera = MagicMock()
    camera.id = "front_door"
    camera.name = "Front Door Camera"
    camera.status = "offline"
    camera.last_seen_at = datetime.now(UTC)
    camera.folder_path = "/export/foscam/front_door"
    return camera


@pytest.fixture
def mock_camera_error():
    """Create a mock camera with error status."""
    camera = MagicMock()
    camera.id = "front_door"
    camera.name = "Front Door Camera"
    camera.status = "error"
    camera.last_seen_at = datetime.now(UTC)
    camera.folder_path = "/export/foscam/front_door"
    return camera


class TestCameraServiceUpdateStatus:
    """Test update_camera_status method."""

    @pytest.mark.asyncio
    async def test_update_camera_status_calls_repository(self, mock_session, mock_camera):
        """Test that update_camera_status delegates to repository correctly."""
        service = CameraService(mock_session)
        timestamp = datetime.now(UTC)

        # Mock the repository methods
        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        updated, camera = await service.update_camera_status(
            "front_door", "online", timestamp, emit_event=False
        )

        assert updated is True
        assert camera == mock_camera
        service.repository.update_status_optimistic.assert_called_once_with(
            camera_id="front_door",
            new_status="online",
            new_last_seen=timestamp,
        )

    @pytest.mark.asyncio
    async def test_update_camera_status_uses_current_time_if_none(self, mock_session, mock_camera):
        """Test that None timestamp defaults to current UTC time."""
        service = CameraService(mock_session)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online", None, emit_event=False)

        # Verify a timestamp was passed (can't check exact value)
        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_last_seen"] is not None
        assert isinstance(call_args.kwargs["new_last_seen"], datetime)

    @pytest.mark.asyncio
    async def test_update_camera_status_returns_false_for_stale_update(
        self, mock_session, mock_camera
    ):
        """Test that stale updates return (False, camera)."""
        service = CameraService(mock_session)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(False, mock_camera))

        updated, camera = await service.update_camera_status(
            "front_door", "offline", datetime.now(UTC), emit_event=False
        )

        assert updated is False
        assert camera == mock_camera

    @pytest.mark.asyncio
    async def test_update_camera_status_returns_none_for_missing_camera(self, mock_session):
        """Test that missing camera returns (False, None)."""
        service = CameraService(mock_session)

        service.repository.get_by_id = AsyncMock(return_value=None)
        service.repository.update_status_optimistic = AsyncMock(return_value=(False, None))

        updated, camera = await service.update_camera_status(
            "nonexistent", "online", datetime.now(UTC), emit_event=False
        )

        assert updated is False
        assert camera is None


class TestCameraServiceConvenienceMethods:
    """Test convenience methods for setting camera status."""

    @pytest.mark.asyncio
    async def test_set_camera_online(self, mock_session, mock_camera):
        """Test set_camera_online convenience method."""
        service = CameraService(mock_session)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.set_camera_online("front_door")

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_status"] == "online"

    @pytest.mark.asyncio
    async def test_set_camera_offline(self, mock_session, mock_camera):
        """Test set_camera_offline convenience method."""
        service = CameraService(mock_session)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.set_camera_offline("front_door")

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_status"] == "offline"

    @pytest.mark.asyncio
    async def test_set_camera_error(self, mock_session, mock_camera):
        """Test set_camera_error convenience method."""
        service = CameraService(mock_session)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.set_camera_error("front_door")

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_status"] == "error"

    @pytest.mark.asyncio
    async def test_convenience_methods_accept_timestamp(self, mock_session, mock_camera):
        """Test that convenience methods accept explicit timestamp."""
        service = CameraService(mock_session)
        timestamp = datetime.now(UTC) - timedelta(hours=1)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.set_camera_online("front_door", timestamp)

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_last_seen"] == timestamp


class TestCameraServiceGetMethods:
    """Test get methods."""

    @pytest.mark.asyncio
    async def test_get_camera(self, mock_session, mock_camera):
        """Test get_camera delegates to repository."""
        service = CameraService(mock_session)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)

        result = await service.get_camera("front_door")

        assert result == mock_camera
        service.repository.get_by_id.assert_called_once_with("front_door")

    @pytest.mark.asyncio
    async def test_get_camera_by_folder_path(self, mock_session, mock_camera):
        """Test get_camera_by_folder_path delegates to repository."""
        service = CameraService(mock_session)

        service.repository.get_by_folder_path = AsyncMock(return_value=mock_camera)

        result = await service.get_camera_by_folder_path("/export/foscam/front_door")

        assert result == mock_camera
        service.repository.get_by_folder_path.assert_called_once_with("/export/foscam/front_door")


class TestCameraServiceFactory:
    """Test factory function."""

    def test_get_camera_service_returns_service(self, mock_session):
        """Test that get_camera_service creates a service bound to session."""
        service = get_camera_service(mock_session)

        assert isinstance(service, CameraService)
        assert service.session == mock_session


class TestCameraServiceWebSocketEvents:
    """Test WebSocket event emission for camera status changes."""

    @pytest.mark.asyncio
    async def test_emits_camera_online_event_when_status_changes_to_online(
        self, mock_session, mock_camera, mock_emitter
    ):
        """Test that camera.online event is emitted when status changes to online."""
        # Set up camera with previous offline status
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        # Updated camera status is online
        mock_camera.status = "online"

        service = CameraService(mock_session, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online")

        # Should emit both camera.online and camera.status_changed events
        assert mock_emitter.emit.call_count == 2

        # Check camera.online event
        first_call = mock_emitter.emit.call_args_list[0]
        assert first_call[0][0] == WebSocketEventType.CAMERA_ONLINE
        payload = first_call[0][1]
        assert payload["camera_id"] == "front_door"
        assert payload["camera_name"] == "Front Door Camera"
        assert "timestamp" in payload

        # Check camera.status_changed event
        second_call = mock_emitter.emit.call_args_list[1]
        assert second_call[0][0] == WebSocketEventType.CAMERA_STATUS_CHANGED
        payload = second_call[0][1]
        assert payload["status"] == "online"
        assert payload["previous_status"] == "offline"

    @pytest.mark.asyncio
    async def test_emits_camera_offline_event_when_status_changes_to_offline(
        self, mock_session, mock_camera_offline, mock_emitter
    ):
        """Test that camera.offline event is emitted when status changes to offline."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "online"

        service = CameraService(mock_session, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(
            return_value=(True, mock_camera_offline)
        )

        await service.update_camera_status("front_door", "offline", reason="Connection timeout")

        assert mock_emitter.emit.call_count == 2

        # Check camera.offline event
        first_call = mock_emitter.emit.call_args_list[0]
        assert first_call[0][0] == WebSocketEventType.CAMERA_OFFLINE
        payload = first_call[0][1]
        assert payload["camera_id"] == "front_door"
        assert payload["reason"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_emits_camera_error_event_when_status_changes_to_error(
        self, mock_session, mock_camera_error, mock_emitter
    ):
        """Test that camera.error event is emitted when status changes to error."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "online"

        service = CameraService(mock_session, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(
            return_value=(True, mock_camera_error)
        )

        await service.update_camera_status("front_door", "error", reason="Hardware malfunction")

        assert mock_emitter.emit.call_count == 2

        # Check camera.error event
        first_call = mock_emitter.emit.call_args_list[0]
        assert first_call[0][0] == WebSocketEventType.CAMERA_ERROR
        payload = first_call[0][1]
        assert payload["camera_id"] == "front_door"
        assert payload["error"] == "Hardware malfunction"

    @pytest.mark.asyncio
    async def test_does_not_emit_event_when_status_unchanged(
        self, mock_session, mock_camera, mock_emitter
    ):
        """Test that no event is emitted when status doesn't change."""
        # Both previous and current status are "online"
        mock_camera.status = "online"

        service = CameraService(mock_session, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=mock_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online")

        # No events should be emitted
        mock_emitter.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_emit_event_when_emit_disabled(
        self, mock_session, mock_camera, mock_emitter
    ):
        """Test that no event is emitted when emit_event=False."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        mock_camera.status = "online"

        service = CameraService(mock_session, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online", emit_event=False)

        mock_emitter.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_emit_when_no_emitter_configured(self, mock_session, mock_camera):
        """Test that service works without emitter configured."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        mock_camera.status = "online"

        # No emitter configured
        service = CameraService(mock_session)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        # Should not raise and should return correctly
        updated, camera = await service.update_camera_status("front_door", "online")

        assert updated is True
        assert camera == mock_camera

    @pytest.mark.asyncio
    async def test_event_emission_error_does_not_fail_update(
        self, mock_session, mock_camera, mock_emitter
    ):
        """Test that WebSocket emission failure doesn't fail the status update."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        mock_camera.status = "online"

        # Make emitter raise an exception
        mock_emitter.emit = AsyncMock(side_effect=Exception("WebSocket error"))

        service = CameraService(mock_session, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        # Should not raise, status update succeeds
        updated, camera = await service.update_camera_status("front_door", "online")

        assert updated is True
        assert camera == mock_camera


class TestCameraServiceDebouncing:
    """Test debouncing logic for camera status events."""

    @pytest.mark.asyncio
    async def test_debounce_first_status_change_sets_pending(
        self, mock_session, mock_camera, mock_redis, mock_emitter
    ):
        """Test that first status change sets pending and doesn't emit."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        mock_camera.status = "online"
        mock_redis.get = AsyncMock(return_value=None)  # No pending status

        service = CameraService(mock_session, redis=mock_redis, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online")

        # Should set pending status in Redis
        mock_redis.setex.assert_called_once_with(
            f"{CAMERA_DEBOUNCE_KEY_PREFIX}front_door",
            CAMERA_STATUS_DEBOUNCE_SECONDS,
            "online",
        )

        # Should NOT emit events (debounced)
        mock_emitter.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_debounce_stable_status_emits_event(
        self, mock_session, mock_camera, mock_redis, mock_emitter
    ):
        """Test that matching pending status causes event emission."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        mock_camera.status = "online"
        # Pending status matches new status - stable
        mock_redis.get = AsyncMock(return_value="online")

        service = CameraService(mock_session, redis=mock_redis, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online")

        # Should delete debounce key
        mock_redis.delete.assert_called_once_with(f"{CAMERA_DEBOUNCE_KEY_PREFIX}front_door")

        # Should emit events
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_debounce_status_change_resets_pending(
        self, mock_session, mock_camera, mock_redis, mock_emitter
    ):
        """Test that status change during pending resets the debounce."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "online"

        mock_camera.status = "offline"
        # Pending status was "online" but now we're going to "offline"
        mock_redis.get = AsyncMock(return_value="online")

        service = CameraService(mock_session, redis=mock_redis, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "offline")

        # Should update pending status to new value
        mock_redis.setex.assert_called_once_with(
            f"{CAMERA_DEBOUNCE_KEY_PREFIX}front_door",
            CAMERA_STATUS_DEBOUNCE_SECONDS,
            "offline",
        )

        # Should NOT emit events (status changed while pending)
        mock_emitter.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_debounce_without_redis(self, mock_session, mock_camera, mock_emitter):
        """Test that debouncing is skipped when no Redis is configured."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        mock_camera.status = "online"

        # No Redis configured
        service = CameraService(mock_session, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online")

        # Should emit events immediately (no debouncing)
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_redis_error_emits_anyway(
        self, mock_session, mock_camera, mock_redis, mock_emitter
    ):
        """Test that Redis errors don't block event emission."""
        previous_camera = MagicMock()
        previous_camera.id = "front_door"
        previous_camera.status = "offline"

        mock_camera.status = "online"
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))

        service = CameraService(mock_session, redis=mock_redis, emitter=mock_emitter)
        service.repository.get_by_id = AsyncMock(return_value=previous_camera)
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online")

        # Should emit events (fallback when Redis fails)
        assert mock_emitter.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_debounce_constant_is_30_seconds(self):
        """Verify the debounce constant is set to 30 seconds as specified."""
        assert CAMERA_STATUS_DEBOUNCE_SECONDS == 30


class TestMapStatusStringToEnum:
    """Test the status string to enum mapping helper."""

    def test_maps_online_status(self):
        """Test mapping of 'online' status."""
        assert _map_status_string_to_enum("online") == "online"
        assert _map_status_string_to_enum("ONLINE") == "online"
        assert _map_status_string_to_enum("Online") == "online"

    def test_maps_offline_status(self):
        """Test mapping of 'offline' status."""
        assert _map_status_string_to_enum("offline") == "offline"
        assert _map_status_string_to_enum("OFFLINE") == "offline"

    def test_maps_error_status(self):
        """Test mapping of 'error' status."""
        assert _map_status_string_to_enum("error") == "error"
        assert _map_status_string_to_enum("ERROR") == "error"

    def test_maps_unknown_status(self):
        """Test mapping of 'unknown' status."""
        assert _map_status_string_to_enum("unknown") == "unknown"

    def test_handles_none(self):
        """Test handling of None input."""
        assert _map_status_string_to_enum(None) is None

    def test_returns_unknown_status_as_is(self):
        """Test that unrecognized status is returned as-is."""
        assert _map_status_string_to_enum("custom_status") == "custom_status"
