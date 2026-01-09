"""Unit tests for restore API endpoints.

Tests the restore functionality for soft-deleted records:
- POST /api/cameras/{camera_id}/restore - Restore a soft-deleted camera
- POST /api/events/{event_id}/restore - Restore a soft-deleted event

These endpoints implement RFC 7807 error format and clear the deleted_at
timestamp to restore records.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.models.camera import Camera
from backend.models.event import Event
from backend.services.cascade_delete import CascadeDeleteResult


class TestRestoreCamera:
    """Tests for POST /api/cameras/{camera_id}/restore endpoint."""

    @pytest.mark.asyncio
    async def test_restore_camera_success(self) -> None:
        """Test successfully restoring a soft-deleted camera."""
        from backend.api.routes.cameras import restore_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        # Create a soft-deleted camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "offline"
        mock_camera.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)
        mock_camera.deleted_at = datetime(2025, 1, 9, tzinfo=UTC)  # Soft-deleted
        mock_camera.is_deleted = True

        # Setup database mocks
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Mock refresh to update camera state after restore
        async def refresh_side_effect(_camera):
            mock_camera.deleted_at = None
            mock_camera.is_deleted = False

        mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

        # Mock the repository restore method
        mock_restore_result = CascadeDeleteResult(
            parent_deleted=True, events_deleted=2, detections_deleted=5
        )

        with (
            patch("backend.api.routes.cameras.CameraRepository") as mock_repo_class,
            patch("backend.api.routes.cameras.AuditService") as mock_audit,
        ):
            mock_repo = MagicMock()
            mock_repo.restore = AsyncMock(return_value=mock_restore_result)
            mock_repo_class.return_value = mock_repo
            mock_audit.log_action = AsyncMock()

            result = await restore_camera(
                camera_id="front_door",
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert result.id == "front_door"
        assert result.name == "Front Door"
        assert result.restored is True
        assert result.message == "Camera restored successfully"
        assert result.deleted_at is None
        mock_repo.restore.assert_called_once()
        # Verify the camera_id was passed correctly
        call_args = mock_repo.restore.call_args
        assert call_args[0][0] == "front_door"  # First positional arg
        mock_cache.invalidate_cameras.assert_called_once_with(reason="camera_restored")

    @pytest.mark.asyncio
    async def test_restore_camera_not_found(self) -> None:
        """Test restoring non-existent camera returns 404."""
        from backend.api.routes.cameras import restore_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        # Camera not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await restore_camera(
                camera_id="nonexistent",
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_restore_camera_not_deleted_returns_400(self) -> None:
        """Test restoring a camera that is not deleted returns 400."""
        from backend.api.routes.cameras import restore_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        # Camera exists but is not deleted
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.deleted_at = None
        mock_camera.is_deleted = False  # Not deleted

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await restore_camera(
                camera_id="front_door",
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert exc_info.value.status_code == 400
        assert "not deleted" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_restore_camera_audit_failure_recovers(self) -> None:
        """Test camera restore continues on audit log failure."""
        from backend.api.routes.cameras import restore_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "offline"
        mock_camera.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)
        mock_camera.deleted_at = datetime(2025, 1, 9, tzinfo=UTC)
        mock_camera.is_deleted = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_result
        mock_db.rollback = AsyncMock()

        # Mock refresh to update camera state after restore
        async def refresh_side_effect(_camera):
            mock_camera.deleted_at = None
            mock_camera.is_deleted = False

        mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

        # Mock the repository restore method
        mock_restore_result = CascadeDeleteResult(
            parent_deleted=True, events_deleted=0, detections_deleted=0
        )

        with (
            patch("backend.api.routes.cameras.CameraRepository") as mock_repo_class,
            patch("backend.api.routes.cameras.AuditService") as mock_audit,
        ):
            mock_repo = MagicMock()
            mock_repo.restore = AsyncMock(return_value=mock_restore_result)
            mock_repo_class.return_value = mock_repo
            mock_audit.log_action = AsyncMock()
            # First commit fails (audit log failure)
            mock_db.commit = AsyncMock(side_effect=[Exception("Audit error"), None])

            result = await restore_camera(
                camera_id="front_door",
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert result.restored is True
        assert mock_db.rollback.called
        # Repository restore is called once, then recovery commit happens
        mock_repo.restore.assert_called_once()
        assert mock_db.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_restore_camera_cache_invalidation_failure(self) -> None:
        """Test camera restore continues on cache invalidation failure."""
        from backend.api.routes.cameras import restore_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "offline"
        mock_camera.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_camera.last_seen_at = None
        mock_camera.deleted_at = datetime(2025, 1, 9, tzinfo=UTC)
        mock_camera.is_deleted = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Mock refresh to update camera state after restore
        async def refresh_side_effect(_camera):
            mock_camera.deleted_at = None

        mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

        # Mock cache invalidation failure
        mock_cache.invalidate_cameras.side_effect = Exception("Cache error")

        # Mock the repository restore method
        mock_restore_result = CascadeDeleteResult(
            parent_deleted=True, events_deleted=0, detections_deleted=0
        )

        with (
            patch("backend.api.routes.cameras.CameraRepository") as mock_repo_class,
            patch("backend.api.routes.cameras.AuditService") as mock_audit,
        ):
            mock_repo = MagicMock()
            mock_repo.restore = AsyncMock(return_value=mock_restore_result)
            mock_repo_class.return_value = mock_repo
            mock_audit.log_action = AsyncMock()

            result = await restore_camera(
                camera_id="front_door",
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        # Should still succeed despite cache error
        assert result.restored is True


class TestRestoreEvent:
    """Tests for POST /api/events/{event_id}/restore endpoint."""

    @pytest.mark.asyncio
    async def test_restore_event_success(self) -> None:
        """Test successfully restoring a soft-deleted event."""
        from backend.api.routes.events import restore_event

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        # Create a soft-deleted event
        mock_event = MagicMock(spec=Event)
        mock_event.id = 123
        mock_event.camera_id = "front_door"
        mock_event.started_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 8, 12, 5, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Person detected at front door"
        mock_event.reviewed = False
        mock_event.deleted_at = datetime(2025, 1, 9, tzinfo=UTC)  # Soft-deleted
        mock_event.is_deleted = True

        # Setup database mocks
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Mock refresh to update event state after restore
        async def refresh_side_effect(_event):
            mock_event.deleted_at = None
            mock_event.is_deleted = False

        mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

        # Mock the repository restore method
        mock_restore_result = CascadeDeleteResult(
            parent_deleted=True, events_deleted=0, detections_deleted=3
        )

        with (
            patch("backend.api.routes.events.EventRepository") as mock_repo_class,
            patch("backend.api.routes.events.AuditService") as mock_audit,
        ):
            mock_repo = MagicMock()
            mock_repo.restore = AsyncMock(return_value=mock_restore_result)
            mock_repo_class.return_value = mock_repo
            mock_audit.log_action = AsyncMock()

            result = await restore_event(
                event_id=123,
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert result.id == 123
        assert result.camera_id == "front_door"
        assert result.restored is True
        assert result.message == "Event restored successfully"
        assert result.deleted_at is None
        mock_repo.restore.assert_called_once()
        mock_cache.invalidate_events.assert_called_once_with(reason="event_restored")
        mock_cache.invalidate_event_stats.assert_called_once_with(reason="event_restored")

    @pytest.mark.asyncio
    async def test_restore_event_not_found(self) -> None:
        """Test restoring non-existent event returns 404."""
        from backend.api.routes.events import restore_event

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        # Event not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await restore_event(
                event_id=999,
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_restore_event_not_deleted_returns_400(self) -> None:
        """Test restoring an event that is not deleted returns 400."""
        from backend.api.routes.events import restore_event

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        # Event exists but is not deleted
        mock_event = MagicMock(spec=Event)
        mock_event.id = 123
        mock_event.camera_id = "front_door"
        mock_event.deleted_at = None
        mock_event.is_deleted = False  # Not deleted

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await restore_event(
                event_id=123,
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert exc_info.value.status_code == 400
        assert "not deleted" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_restore_event_audit_failure_recovers(self) -> None:
        """Test event restore continues on audit log failure."""
        from backend.api.routes.events import restore_event

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        mock_event = MagicMock(spec=Event)
        mock_event.id = 123
        mock_event.camera_id = "front_door"
        mock_event.started_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 8, 12, 5, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Person detected"
        mock_event.reviewed = False
        mock_event.deleted_at = datetime(2025, 1, 9, tzinfo=UTC)
        mock_event.is_deleted = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result
        mock_db.rollback = AsyncMock()

        # Mock refresh to update event state after restore
        async def refresh_side_effect(_event):
            mock_event.deleted_at = None
            mock_event.is_deleted = False

        mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

        # Mock the repository restore method
        mock_restore_result = CascadeDeleteResult(
            parent_deleted=True, events_deleted=0, detections_deleted=0
        )

        with (
            patch("backend.api.routes.events.EventRepository") as mock_repo_class,
            patch("backend.api.routes.events.AuditService") as mock_audit,
        ):
            mock_repo = MagicMock()
            mock_repo.restore = AsyncMock(return_value=mock_restore_result)
            mock_repo_class.return_value = mock_repo
            mock_audit.log_action = AsyncMock()
            # First commit fails (audit log failure)
            mock_db.commit = AsyncMock(side_effect=[Exception("Audit error"), None])

            result = await restore_event(
                event_id=123,
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert result.restored is True
        assert mock_db.rollback.called
        # Repository restore is called once, then recovery commit happens
        mock_repo.restore.assert_called_once()
        assert mock_db.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_restore_event_cache_invalidation_failure(self) -> None:
        """Test event restore continues on cache invalidation failure."""
        from backend.api.routes.events import restore_event

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        mock_event = MagicMock(spec=Event)
        mock_event.id = 123
        mock_event.camera_id = "front_door"
        mock_event.started_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)
        mock_event.ended_at = None
        mock_event.risk_score = 50
        mock_event.risk_level = "medium"
        mock_event.summary = "Motion detected"
        mock_event.reviewed = False
        mock_event.deleted_at = datetime(2025, 1, 9, tzinfo=UTC)
        mock_event.is_deleted = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Mock refresh to update event state after restore
        async def refresh_side_effect(_event):
            mock_event.deleted_at = None

        mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

        # Mock cache invalidation failure
        mock_cache.invalidate_events.side_effect = Exception("Cache error")
        mock_cache.invalidate_event_stats.side_effect = Exception("Cache error")

        # Mock the repository restore method
        mock_restore_result = CascadeDeleteResult(
            parent_deleted=True, events_deleted=0, detections_deleted=0
        )

        with (
            patch("backend.api.routes.events.EventRepository") as mock_repo_class,
            patch("backend.api.routes.events.AuditService") as mock_audit,
        ):
            mock_repo = MagicMock()
            mock_repo.restore = AsyncMock(return_value=mock_restore_result)
            mock_repo_class.return_value = mock_repo
            mock_audit.log_action = AsyncMock()

            result = await restore_event(
                event_id=123,
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        # Should still succeed despite cache error
        assert result.restored is True

    @pytest.mark.asyncio
    async def test_restore_event_with_null_optional_fields(self) -> None:
        """Test restoring an event with null optional fields."""
        from backend.api.routes.events import restore_event

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()

        # Event with null optional fields
        mock_event = MagicMock(spec=Event)
        mock_event.id = 456
        mock_event.camera_id = "backyard"
        mock_event.started_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)
        mock_event.ended_at = None
        mock_event.risk_score = None
        mock_event.risk_level = None
        mock_event.summary = None
        mock_event.reviewed = False
        mock_event.deleted_at = datetime(2025, 1, 9, tzinfo=UTC)
        mock_event.is_deleted = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Mock refresh to update event state after restore
        async def refresh_side_effect(_event):
            mock_event.deleted_at = None
            mock_event.is_deleted = False

        mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

        # Mock the repository restore method
        mock_restore_result = CascadeDeleteResult(
            parent_deleted=True, events_deleted=0, detections_deleted=0
        )

        with (
            patch("backend.api.routes.events.EventRepository") as mock_repo_class,
            patch("backend.api.routes.events.AuditService") as mock_audit,
        ):
            mock_repo = MagicMock()
            mock_repo.restore = AsyncMock(return_value=mock_restore_result)
            mock_repo_class.return_value = mock_repo
            mock_audit.log_action = AsyncMock()

            result = await restore_event(
                event_id=456,
                request=mock_request,
                db=mock_db,
                cache=mock_cache,
            )

        assert result.id == 456
        assert result.risk_score is None
        assert result.risk_level is None
        assert result.summary is None
        assert result.restored is True
