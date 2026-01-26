"""Unit tests for camera API routes.

Tests the camera management endpoints:
- GET /api/cameras - List all cameras with optional status filter
- GET /api/cameras/{camera_id} - Get specific camera
- POST /api/cameras - Create new camera
- PATCH /api/cameras/{camera_id} - Update camera
- DELETE /api/cameras/{camera_id} - Delete camera
- GET /api/cameras/{camera_id}/snapshot - Get camera snapshot
- GET /api/cameras/validation/paths - Validate camera paths

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking.
"""

import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.constants import CacheInvalidationReason
from backend.models.camera import Camera


class TestListCameras:
    """Tests for GET /api/cameras endpoint."""

    @pytest.mark.asyncio
    async def test_list_cameras_cache_hit(self) -> None:
        """Test listing cameras returns cached data when available."""
        from backend.api.routes.cameras import list_cameras

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache hit
        cached_data = {
            "cameras": [
                {
                    "id": "front_door",
                    "name": "Front Door",
                    "folder_path": "/cameras/front_door",
                    "status": "online",
                    "created_at": "2025-01-01T00:00:00",
                    "last_seen_at": "2025-01-08T12:00:00",
                }
            ],
            "count": 1,
        }
        mock_cache.get.return_value = cached_data

        result = await list_cameras(status_filter=None, db=mock_db, cache=mock_cache)

        assert result.pagination.total == len(cached_data["cameras"])
        assert len(result.items) == len(cached_data["cameras"])
        assert result.items[0].id == cached_data["cameras"][0]["id"]
        mock_cache.get.assert_called_once()
        mock_db.execute.assert_not_called()  # Database not queried on cache hit

    @pytest.mark.asyncio
    async def test_list_cameras_cache_miss(self) -> None:
        """Test listing cameras queries database on cache miss."""
        from backend.api.routes.cameras import list_cameras

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database query
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "online"
        mock_camera.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_result

        result = await list_cameras(status_filter=None, db=mock_db, cache=mock_cache)

        assert result.pagination.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == "front_door"
        assert result.items[0].name == "Front Door"
        mock_cache.set.assert_called_once()  # Cache should be populated

    @pytest.mark.asyncio
    async def test_list_cameras_with_status_filter(self) -> None:
        """Test listing cameras with status filter."""
        from backend.api.routes.cameras import list_cameras

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database query with only online cameras
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "online"
        mock_camera.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_result

        result = await list_cameras(status_filter="online", db=mock_db, cache=mock_cache)

        assert result.pagination.total == 1
        assert result.items[0].status == "online"

    @pytest.mark.asyncio
    async def test_list_cameras_empty_list(self) -> None:
        """Test listing cameras returns empty list when no cameras exist."""
        from backend.api.routes.cameras import list_cameras

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock empty database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await list_cameras(status_filter=None, db=mock_db, cache=mock_cache)

        assert result.pagination.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_list_cameras_cache_read_failure(self) -> None:
        """Test listing cameras falls back to database on cache read failure."""
        from backend.api.routes.cameras import list_cameras

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache read failure
        mock_cache.get.side_effect = Exception("Redis connection error")

        # Mock database query
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "backyard"
        mock_camera.name = "Backyard"
        mock_camera.folder_path = "/cameras/backyard"
        mock_camera.status = "offline"
        mock_camera.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_camera.last_seen_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_result

        result = await list_cameras(status_filter=None, db=mock_db, cache=mock_cache)

        assert result.pagination.total == 1
        assert result.items[0].id == "backyard"

    @pytest.mark.asyncio
    async def test_list_cameras_cache_write_failure(self) -> None:
        """Test listing cameras continues on cache write failure."""
        from backend.api.routes.cameras import list_cameras

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None
        # Mock cache write failure
        mock_cache.set.side_effect = Exception("Redis write error")

        # Mock database query
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "garage"
        mock_camera.name = "Garage"
        mock_camera.folder_path = "/cameras/garage"
        mock_camera.status = "online"
        mock_camera.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(2025, 1, 8, 12, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_result

        # Should not raise exception, just log warning
        result = await list_cameras(status_filter=None, db=mock_db, cache=mock_cache)

        assert result.pagination.total == 1
        assert result.items[0].id == "garage"


class TestGetCamera:
    """Tests for GET /api/cameras/{camera_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_camera_success(self) -> None:
        """Test getting a specific camera by ID."""
        from backend.api.routes.cameras import get_camera
        from backend.api.schemas.camera import CameraResponse

        mock_db = AsyncMock()

        # Mock camera found with all required attributes for CameraResponse
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "online"
        mock_camera.created_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
        mock_camera.property_id = 1

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            result = await get_camera("front_door", db=mock_db)

        # NEM-3597: Now returns CameraResponse instead of Camera
        assert isinstance(result, CameraResponse)
        assert result.id == "front_door"

    @pytest.mark.asyncio
    async def test_get_camera_not_found(self) -> None:
        """Test getting non-existent camera returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import get_camera

        mock_db = AsyncMock()

        # Mock camera not found
        with patch(
            "backend.api.routes.cameras.get_camera_or_404",
            side_effect=HTTPException(status_code=404, detail="Camera not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_camera("nonexistent", db=mock_db)

            assert exc_info.value.status_code == 404


class TestCreateCamera:
    """Tests for POST /api/cameras endpoint."""

    @pytest.mark.asyncio
    async def test_create_camera_success(self) -> None:
        """Test successfully creating a new camera."""
        from backend.api.routes.cameras import create_camera
        from backend.api.schemas.camera import CameraCreate, CameraResponse

        mock_db = AsyncMock()
        mock_db.add = MagicMock()  # db.add is synchronous in SQLAlchemy
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        camera_data = CameraCreate(
            name="New Camera",
            folder_path="/cameras/new_camera",
            status="online",
        )

        # Mock no existing camera with same name or path
        mock_name_result = MagicMock()
        mock_name_result.scalar_one_or_none.return_value = None
        mock_path_result = MagicMock()
        mock_path_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_name_result, mock_path_result]
        mock_db.commit = AsyncMock()

        # Mock db.refresh to set the created_at attribute (simulating database default)
        async def mock_refresh(camera: Camera) -> None:
            camera.created_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)

        mock_db.refresh = mock_refresh

        with patch("backend.api.routes.cameras.AuditService") as mock_audit:
            mock_audit.log_action = AsyncMock()
            result = await create_camera(
                camera_data=camera_data,
                request=mock_request,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

        # NEM-3597: Now returns CameraResponse instead of Camera
        assert isinstance(result, CameraResponse)
        assert result.name == "New Camera"
        assert result.folder_path == "/cameras/new_camera"
        mock_cache.invalidate_cameras.assert_called_once_with(
            reason=CacheInvalidationReason.CAMERA_CREATED
        )

    @pytest.mark.asyncio
    async def test_create_camera_duplicate_name(self) -> None:
        """Test creating camera with duplicate name returns 409."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import create_camera
        from backend.api.schemas.camera import CameraCreate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        camera_data = CameraCreate(
            name="Existing Camera",
            folder_path="/cameras/new_path",
            status="online",
        )

        # Mock existing camera with same name
        mock_existing = MagicMock(spec=Camera)
        mock_existing.id = "existing_camera"
        mock_existing.name = "Existing Camera"

        mock_name_result = MagicMock()
        mock_name_result.scalar_one_or_none.return_value = mock_existing

        mock_db.execute.return_value = mock_name_result

        with pytest.raises(HTTPException) as exc_info:
            await create_camera(
                camera_data=camera_data,
                request=mock_request,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_camera_duplicate_folder_path(self) -> None:
        """Test creating camera with duplicate folder_path returns 409."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import create_camera
        from backend.api.schemas.camera import CameraCreate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        camera_data = CameraCreate(
            name="New Camera",
            folder_path="/cameras/existing_path",
            status="online",
        )

        # Mock no existing camera with same name
        mock_name_result = MagicMock()
        mock_name_result.scalar_one_or_none.return_value = None

        # Mock existing camera with same path
        mock_existing = MagicMock(spec=Camera)
        mock_existing.id = "existing_camera"
        mock_existing.folder_path = "/cameras/existing_path"

        mock_path_result = MagicMock()
        mock_path_result.scalar_one_or_none.return_value = mock_existing

        mock_db.execute.side_effect = [mock_name_result, mock_path_result]

        with pytest.raises(HTTPException) as exc_info:
            await create_camera(
                camera_data=camera_data,
                request=mock_request,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

        assert exc_info.value.status_code == 409
        assert "folder_path" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_camera_audit_failure_recovers(self) -> None:
        """Test camera creation continues on audit log failure."""
        from backend.api.routes.cameras import create_camera
        from backend.api.schemas.camera import CameraCreate, CameraResponse

        mock_db = AsyncMock()
        mock_db.add = MagicMock()  # db.add is synchronous in SQLAlchemy
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        camera_data = CameraCreate(
            name="Test Camera",
            folder_path="/cameras/test",
            status="online",
        )

        # Mock no existing cameras
        mock_name_result = MagicMock()
        mock_name_result.scalar_one_or_none.return_value = None
        mock_path_result = MagicMock()
        mock_path_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_name_result, mock_path_result]
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        # Mock db.refresh to set the created_at attribute (simulating database default)
        async def mock_refresh(camera: Camera) -> None:
            camera.created_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)

        mock_db.refresh = mock_refresh

        with patch("backend.api.routes.cameras.AuditService") as mock_audit:
            # First commit fails (audit log failure)
            mock_audit.log_action = AsyncMock()
            mock_db.commit.side_effect = [Exception("Audit log error"), None]

            result = await create_camera(
                camera_data=camera_data,
                request=mock_request,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

        # NEM-3597: Now returns CameraResponse instead of Camera
        assert isinstance(result, CameraResponse)
        assert mock_db.rollback.called
        # Should commit twice (once with audit failure, once recovery)
        assert mock_db.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_create_camera_cache_invalidation_failure(self) -> None:
        """Test camera creation continues on cache invalidation failure."""
        from backend.api.routes.cameras import create_camera
        from backend.api.schemas.camera import CameraCreate, CameraResponse

        mock_db = AsyncMock()
        mock_db.add = MagicMock()  # db.add is synchronous in SQLAlchemy
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        camera_data = CameraCreate(
            name="Test Camera",
            folder_path="/cameras/test",
            status="online",
        )

        # Mock no existing cameras
        mock_name_result = MagicMock()
        mock_name_result.scalar_one_or_none.return_value = None
        mock_path_result = MagicMock()
        mock_path_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_name_result, mock_path_result]
        mock_db.commit = AsyncMock()

        # Mock db.refresh to set the created_at attribute (simulating database default)
        async def mock_refresh(camera: Camera) -> None:
            camera.created_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)

        mock_db.refresh = mock_refresh

        # Mock cache invalidation failure
        mock_cache.invalidate_cameras.side_effect = Exception("Cache error")

        with patch("backend.api.routes.cameras.AuditService") as mock_audit:
            mock_audit.log_action = AsyncMock()
            result = await create_camera(
                camera_data=camera_data,
                request=mock_request,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

        # NEM-3597: Should still succeed despite cache error, now returns CameraResponse
        assert isinstance(result, CameraResponse)


class TestUpdateCamera:
    """Tests for PATCH /api/cameras/{camera_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_camera_success(self) -> None:
        """Test successfully updating a camera."""
        from backend.api.routes.cameras import update_camera
        from backend.api.schemas.camera import CameraResponse, CameraUpdate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        camera_data = CameraUpdate(status="offline")

        # Mock existing camera with all required attributes for CameraResponse
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "offline"  # After update
        mock_camera.created_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
        mock_camera.property_id = 1

        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.AuditService") as mock_audit,
        ):
            mock_audit.log_action = AsyncMock()
            result = await update_camera(
                camera_id="front_door",
                camera_data=camera_data,
                request=mock_request,
                background_tasks=mock_background_tasks,
                db=mock_db,
                cache=mock_cache,
            )

        # NEM-3597: Now returns CameraResponse instead of Camera
        assert isinstance(result, CameraResponse)
        assert result.id == "front_door"
        mock_cache.invalidate_cameras.assert_called_once_with(
            reason=CacheInvalidationReason.CAMERA_UPDATED
        )

    @pytest.mark.asyncio
    async def test_update_camera_not_found(self) -> None:
        """Test updating non-existent camera returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import update_camera
        from backend.api.schemas.camera import CameraUpdate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        camera_data = CameraUpdate(status="offline")

        with patch(
            "backend.api.routes.cameras.get_camera_or_404",
            side_effect=HTTPException(status_code=404, detail="Camera not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_camera(
                    camera_id="nonexistent",
                    camera_data=camera_data,
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_camera_partial_update(self) -> None:
        """Test partial update only changes specified fields."""
        from backend.api.routes.cameras import update_camera
        from backend.api.schemas.camera import CameraResponse, CameraUpdate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        # Only update name, leave other fields unchanged
        camera_data = CameraUpdate(name="Updated Name")

        # Mock existing camera with all required attributes for CameraResponse
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Updated Name"  # After update
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "online"
        mock_camera.created_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
        mock_camera.property_id = 1

        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            with patch("backend.api.routes.cameras.AuditService") as mock_audit:
                mock_audit.log_action = AsyncMock()
                result = await update_camera(
                    camera_id="front_door",
                    camera_data=camera_data,
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

        # NEM-3597: Now returns CameraResponse instead of Camera
        assert isinstance(result, CameraResponse)
        assert result.id == "front_door"
        # Verify audit log contains changes
        mock_audit.log_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_camera_audit_failure_recovers(self) -> None:
        """Test camera update continues on audit log failure."""
        from backend.api.routes.cameras import update_camera
        from backend.api.schemas.camera import CameraResponse, CameraUpdate

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        camera_data = CameraUpdate(status="offline")

        # Mock existing camera with all required attributes for CameraResponse
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "offline"  # After update
        mock_camera.created_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
        mock_camera.last_seen_at = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
        mock_camera.property_id = 1

        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            with patch("backend.api.routes.cameras.AuditService") as mock_audit:
                mock_audit.log_action = AsyncMock()
                # First commit fails (audit log failure)
                mock_db.commit.side_effect = [Exception("Audit error"), None]

                result = await update_camera(
                    camera_id="front_door",
                    camera_data=camera_data,
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

        # NEM-3597: Now returns CameraResponse instead of Camera
        assert isinstance(result, CameraResponse)
        assert mock_db.rollback.called
        assert mock_db.commit.call_count == 2


class TestDeleteCamera:
    """Tests for DELETE /api/cameras/{camera_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_camera_success(self) -> None:
        """Test successfully deleting a camera."""
        from backend.api.routes.cameras import delete_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "online"

        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            with patch("backend.api.routes.cameras.AuditService") as mock_audit:
                mock_audit.log_action = AsyncMock()
                result = await delete_camera(
                    camera_id="front_door",
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

        assert result is None
        mock_db.delete.assert_called_once_with(mock_camera)
        mock_cache.invalidate_cameras.assert_called_once_with(
            reason=CacheInvalidationReason.CAMERA_DELETED
        )

    @pytest.mark.asyncio
    async def test_delete_camera_not_found(self) -> None:
        """Test deleting non-existent camera returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import delete_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        with patch(
            "backend.api.routes.cameras.get_camera_or_404",
            side_effect=HTTPException(status_code=404, detail="Camera not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_camera(
                    camera_id="nonexistent",
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_camera_audit_failure_recovers(self) -> None:
        """Test camera deletion continues on audit log failure."""
        from backend.api.routes.cameras import delete_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/cameras/front_door"
        mock_camera.status = "online"

        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            with patch("backend.api.routes.cameras.AuditService") as mock_audit:
                mock_audit.log_action = AsyncMock()
                # First commit fails (audit log failure)
                mock_db.commit.side_effect = [Exception("Audit error"), None]

                result = await delete_camera(
                    camera_id="front_door",
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

        assert result is None
        assert mock_db.rollback.called
        # Should delete twice (once with audit failure, once recovery)
        assert mock_db.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_camera_cache_invalidation_failure(self) -> None:
        """Test camera deletion continues on cache invalidation failure."""
        from backend.api.routes.cameras import delete_camera

        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_request = MagicMock()
        mock_background_tasks = MagicMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        # Mock cache invalidation failure
        mock_cache.invalidate_cameras.side_effect = Exception("Cache error")

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            with patch("backend.api.routes.cameras.AuditService") as mock_audit:
                mock_audit.log_action = AsyncMock()
                result = await delete_camera(
                    camera_id="front_door",
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    db=mock_db,
                    cache=mock_cache,
                )

        # Should still succeed despite cache error
        assert result is None


class TestGetCameraSnapshot:
    """Tests for GET /api/cameras/{camera_id}/snapshot endpoint."""

    @pytest.mark.asyncio
    async def test_get_snapshot_success(self) -> None:
        """Test successfully retrieving camera snapshot (from image file)."""
        from fastapi.responses import FileResponse

        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.folder_path = "/export/foscam/front_door"

        # Create a temporary directory structure
        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.get_settings") as mock_settings,
            patch("backend.api.routes.cameras._get_snapshot_cache_path") as mock_cache_path,
            patch("backend.api.routes.cameras._is_cache_valid") as mock_is_valid,
            patch("backend.api.routes.cameras.Path") as mock_path,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            # Cache is not valid - will search for images
            cache_path = MagicMock()
            mock_cache_path.return_value = cache_path
            mock_is_valid.return_value = False

            # Mock Path operations
            mock_camera_dir = MagicMock()
            mock_camera_dir.exists.return_value = True
            mock_camera_dir.is_dir.return_value = True
            mock_camera_dir.resolve.return_value = mock_camera_dir
            mock_camera_dir.relative_to.return_value = Path("front_door")

            mock_file = MagicMock()
            mock_file.is_file.return_value = True
            mock_file.suffix = ".jpg"
            mock_file.stat.return_value.st_mtime = 1234567890
            mock_file.name = "snapshot.jpg"

            mock_camera_dir.rglob.return_value = [mock_file]

            mock_path.return_value.resolve.side_effect = [
                Path("/export/foscam"),
                mock_camera_dir,
            ]

            result = await get_camera_snapshot(
                camera_id="front_door",
                db=mock_db,
                _rate_limit=None,
            )

            assert isinstance(result, FileResponse)

    @pytest.mark.asyncio
    async def test_get_snapshot_camera_not_found(self) -> None:
        """Test snapshot endpoint returns 404 for non-existent camera."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.cameras.get_camera_or_404",
            side_effect=HTTPException(status_code=404, detail="Camera not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_camera_snapshot(
                    camera_id="nonexistent",
                    db=mock_db,
                    _rate_limit=None,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_snapshot_directory_not_found(self) -> None:
        """Test snapshot endpoint returns 404 when camera directory doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.folder_path = "/export/foscam/front_door"

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            with patch("backend.api.routes.cameras.get_settings") as mock_settings:
                mock_settings.return_value.foscam_base_path = "/export/foscam"

                with patch("backend.api.routes.cameras.Path") as mock_path:
                    mock_camera_dir = MagicMock()
                    mock_camera_dir.exists.return_value = False
                    mock_camera_dir.resolve.return_value = mock_camera_dir
                    mock_camera_dir.relative_to.return_value = Path("front_door")

                    mock_path.return_value.resolve.side_effect = [
                        Path("/export/foscam"),
                        mock_camera_dir,
                    ]

                    with pytest.raises(HTTPException) as exc_info:
                        await get_camera_snapshot(
                            camera_id="front_door",
                            db=mock_db,
                            _rate_limit=None,
                        )

                    assert exc_info.value.status_code == 404
                    assert "does not exist" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_snapshot_no_images_found(self) -> None:
        """Test snapshot endpoint returns 404 when no images or videos found."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.folder_path = "/export/foscam/front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.get_settings") as mock_settings,
            patch("backend.api.routes.cameras._get_snapshot_cache_path") as mock_cache_path,
            patch("backend.api.routes.cameras._is_cache_valid") as mock_is_valid,
            patch("backend.api.routes.cameras.Path") as mock_path,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            # Cache is not valid
            cache_path = MagicMock()
            mock_cache_path.return_value = cache_path
            mock_is_valid.return_value = False

            mock_camera_dir = MagicMock()
            mock_camera_dir.exists.return_value = True
            mock_camera_dir.is_dir.return_value = True
            mock_camera_dir.resolve.return_value = mock_camera_dir
            mock_camera_dir.relative_to.return_value = Path("front_door")
            mock_camera_dir.rglob.return_value = []  # No images or videos

            mock_path.return_value.resolve.side_effect = [
                Path("/export/foscam"),
                mock_camera_dir,
            ]

            with pytest.raises(HTTPException) as exc_info:
                await get_camera_snapshot(
                    camera_id="front_door",
                    db=mock_db,
                    _rate_limit=None,
                )

            # NEM-2446: Message now includes video files
            assert exc_info.value.status_code == 404
            assert "No snapshot images or video files found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_snapshot_path_traversal_protection(self) -> None:
        """Test snapshot endpoint protects against path traversal attacks."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()

        # Camera with path that tries to escape base directory
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "malicious"
        mock_camera.folder_path = "/cameras/../../../etc"

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            with patch("backend.api.routes.cameras.get_settings") as mock_settings:
                mock_settings.return_value.foscam_base_path = "/export/foscam"

                with patch("backend.api.routes.cameras.Path") as mock_path:
                    mock_camera_dir = MagicMock()
                    # Resolve shows it's trying to access outside directory
                    mock_camera_dir.resolve.return_value = Path("/etc")
                    mock_camera_dir.relative_to.side_effect = ValueError("Not relative")

                    mock_path.return_value.resolve.side_effect = [
                        Path("/export/foscam"),
                        mock_camera_dir,
                    ]

                    with pytest.raises(HTTPException) as exc_info:
                        await get_camera_snapshot(
                            camera_id="malicious",
                            db=mock_db,
                            _rate_limit=None,
                        )

                    assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_snapshot_invalid_folder_name(self) -> None:
        """Test snapshot endpoint rejects folder names with path traversal."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.folder_path = "/old/path/../../../etc/passwd"

        with patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera):
            with patch("backend.api.routes.cameras.get_settings") as mock_settings:
                mock_settings.return_value.foscam_base_path = "/export/foscam"

                with patch("backend.api.routes.cameras.Path") as mock_path:
                    base_root = Path("/export/foscam")

                    # Camera dir outside base
                    mock_camera_dir = MagicMock()
                    mock_camera_dir.resolve.return_value = Path("/etc/passwd")
                    mock_camera_dir.relative_to.side_effect = ValueError("Not relative")

                    mock_path.return_value.resolve.side_effect = [base_root, mock_camera_dir]
                    mock_path.return_value.name = "../../../etc/passwd"

                    with pytest.raises(HTTPException) as exc_info:
                        await get_camera_snapshot(
                            camera_id="front_door",
                            db=mock_db,
                            _rate_limit=None,
                        )

                    assert exc_info.value.status_code == 404


class TestValidateCameraPaths:
    """Tests for GET /api/cameras/validation/paths endpoint."""

    @pytest.mark.asyncio
    async def test_validate_paths_all_valid(self) -> None:
        """Test validation endpoint with all valid camera paths."""
        from backend.api.routes.cameras import validate_camera_paths

        mock_db = AsyncMock()

        # Mock cameras
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/export/foscam/front_door"
        mock_camera.status = "online"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.cameras.get_settings") as mock_settings:
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            with patch("backend.api.routes.cameras.Path") as mock_path:
                mock_camera_path = MagicMock()
                mock_camera_path.exists.return_value = True
                mock_camera_path.is_dir.return_value = True
                mock_camera_path.resolve.return_value = Path("/export/foscam/front_door")
                mock_camera_path.relative_to.return_value = Path("front_door")
                mock_camera_path.rglob.return_value = [MagicMock()]  # Has images

                def path_constructor(_path_str):
                    return mock_camera_path

                mock_path.side_effect = path_constructor

                result = await validate_camera_paths(db=mock_db)

        assert result.total_cameras == 1
        assert result.valid_count == 1
        assert result.invalid_count == 0
        assert len(result.valid_cameras) == 1

    @pytest.mark.asyncio
    async def test_validate_paths_outside_base_path(self) -> None:
        """Test validation detects paths outside base path."""
        from backend.api.routes.cameras import validate_camera_paths

        mock_db = AsyncMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/other/path/front_door"
        mock_camera.status = "online"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.cameras.get_settings") as mock_settings:
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            with patch("backend.api.routes.cameras.Path") as mock_path:
                # Mock for camera path that's outside base
                mock_camera_path = MagicMock()
                mock_camera_path.resolve.return_value = Path("/other/path/front_door")
                mock_camera_path.relative_to.side_effect = ValueError("Not relative")
                mock_camera_path.exists.return_value = True
                mock_camera_path.is_dir.return_value = True
                # Empty image list to trigger "no images" issue
                mock_camera_path.rglob.return_value = []

                def path_constructor(_path_str):
                    return mock_camera_path

                mock_path.side_effect = path_constructor

                result = await validate_camera_paths(db=mock_db)

        assert result.total_cameras == 1
        assert result.valid_count == 0
        assert result.invalid_count == 1
        # The code first checks if path is under base, then checks for images
        # Both issues should be present
        assert len(result.invalid_cameras[0].issues) >= 1

    @pytest.mark.asyncio
    async def test_validate_paths_directory_not_exists(self) -> None:
        """Test validation detects non-existent directories."""
        from backend.api.routes.cameras import validate_camera_paths

        mock_db = AsyncMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/export/foscam/front_door"
        mock_camera.status = "online"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.cameras.get_settings") as mock_settings:
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            with patch("backend.api.routes.cameras.Path") as mock_path:
                mock_camera_path = MagicMock()
                mock_camera_path.exists.return_value = False

                def path_constructor(_path_str):
                    return mock_camera_path

                mock_path.side_effect = path_constructor

                result = await validate_camera_paths(db=mock_db)

        assert result.invalid_count == 1
        assert "does not exist" in result.invalid_cameras[0].issues[0]

    @pytest.mark.asyncio
    async def test_validate_paths_no_images(self) -> None:
        """Test validation detects directories without images."""
        from backend.api.routes.cameras import validate_camera_paths

        mock_db = AsyncMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera.folder_path = "/export/foscam/front_door"
        mock_camera.status = "online"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.cameras.get_settings") as mock_settings:
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            with patch("backend.api.routes.cameras.Path") as mock_path:
                mock_camera_path = MagicMock()
                mock_camera_path.exists.return_value = True
                mock_camera_path.is_dir.return_value = True
                mock_camera_path.resolve.return_value = Path("/export/foscam/front_door")
                mock_camera_path.relative_to.return_value = Path("front_door")
                # No images found
                mock_camera_path.rglob.return_value = []

                def path_constructor(_path_str):
                    return mock_camera_path

                mock_path.side_effect = path_constructor

                result = await validate_camera_paths(db=mock_db)

        assert result.invalid_count == 1
        assert "no image or video files found" in result.invalid_cameras[0].issues[0]


class TestGetCameraSnapshotVideoFallback:
    """Tests for GET /api/cameras/{camera_id}/snapshot video fallback (NEM-2446)."""

    @pytest.mark.asyncio
    async def test_get_snapshot_returns_cached_snapshot(self) -> None:
        """Test that a cached snapshot is returned if valid."""
        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.folder_path = "/export/foscam/front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.get_settings") as mock_settings,
            patch("backend.api.routes.cameras._get_snapshot_cache_path") as mock_cache_path,
            patch("backend.api.routes.cameras._is_cache_valid") as mock_is_valid,
            patch("backend.api.routes.cameras.Path") as mock_path,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            # Setup cache path mock
            cache_path = MagicMock()
            cache_path.__str__ = lambda _: "/export/foscam/.snapshot_cache/front_door_snapshot.jpg"
            mock_cache_path.return_value = cache_path
            mock_is_valid.return_value = True

            # Mock camera directory
            mock_camera_dir = MagicMock()
            mock_camera_dir.exists.return_value = True
            mock_camera_dir.is_dir.return_value = True
            mock_camera_dir.resolve.return_value = mock_camera_dir
            mock_camera_dir.relative_to.return_value = Path("front_door")

            mock_path.return_value.resolve.side_effect = [
                Path("/export/foscam"),
                mock_camera_dir,
            ]

            result = await get_camera_snapshot(
                camera_id="front_door",
                db=mock_db,
                _rate_limit=None,
            )

            assert result.media_type == "image/jpeg"
            mock_is_valid.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_snapshot_extracts_from_video_when_no_images(self) -> None:
        """Test that snapshot is extracted from video when no images exist."""
        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.folder_path = "/export/foscam/front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.get_settings") as mock_settings,
            patch("backend.api.routes.cameras._get_snapshot_cache_path") as mock_cache_path,
            patch("backend.api.routes.cameras._is_cache_valid") as mock_is_valid,
            patch("backend.api.routes.cameras._extract_frame_from_video") as mock_extract,
            patch("backend.api.routes.cameras.Path") as mock_path,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            # Cache is not valid - should trigger extraction
            cache_path = MagicMock()
            cache_path.__str__ = lambda _: "/export/foscam/.snapshot_cache/front_door_snapshot.jpg"
            cache_path.exists.return_value = True
            mock_cache_path.return_value = cache_path
            mock_is_valid.return_value = False

            # Mock camera directory - no images, but has video
            mock_camera_dir = MagicMock()
            mock_camera_dir.exists.return_value = True
            mock_camera_dir.is_dir.return_value = True
            mock_camera_dir.resolve.return_value = mock_camera_dir
            mock_camera_dir.relative_to.return_value = Path("front_door")

            # No images
            mock_video_file = MagicMock()
            mock_video_file.is_file.return_value = True
            mock_video_file.suffix = ".mkv"
            mock_video_file.stat.return_value.st_mtime = 1234567890
            mock_video_file.name = "recording.mkv"

            def rglob_side_effect(pattern):
                if (
                    ".jpg" in pattern
                    or ".jpeg" in pattern
                    or ".png" in pattern
                    or ".gif" in pattern
                ):
                    return []  # No images
                elif ".mkv" in pattern:
                    return [mock_video_file]  # Has video
                return []

            mock_camera_dir.rglob.side_effect = rglob_side_effect

            mock_path.return_value.resolve.side_effect = [
                Path("/export/foscam"),
                mock_camera_dir,
            ]

            # Extraction succeeds
            mock_extract.return_value = True

            result = await get_camera_snapshot(
                camera_id="front_door",
                db=mock_db,
                _rate_limit=None,
            )

            assert result.media_type == "image/jpeg"
            mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_snapshot_returns_404_when_no_images_or_videos(self) -> None:
        """Test that 404 is returned when no images or videos exist."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.folder_path = "/export/foscam/front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.get_settings") as mock_settings,
            patch("backend.api.routes.cameras._get_snapshot_cache_path") as mock_cache_path,
            patch("backend.api.routes.cameras._is_cache_valid") as mock_is_valid,
            patch("backend.api.routes.cameras.Path") as mock_path,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            cache_path = MagicMock()
            mock_cache_path.return_value = cache_path
            mock_is_valid.return_value = False

            # Mock camera directory - no images, no videos
            mock_camera_dir = MagicMock()
            mock_camera_dir.exists.return_value = True
            mock_camera_dir.is_dir.return_value = True
            mock_camera_dir.resolve.return_value = mock_camera_dir
            mock_camera_dir.relative_to.return_value = Path("front_door")
            mock_camera_dir.rglob.return_value = []  # Nothing found

            mock_path.return_value.resolve.side_effect = [
                Path("/export/foscam"),
                mock_camera_dir,
            ]

            with pytest.raises(HTTPException) as exc_info:
                await get_camera_snapshot(
                    camera_id="front_door",
                    db=mock_db,
                    _rate_limit=None,
                )

            assert exc_info.value.status_code == 404
            assert "No snapshot images or video files found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_snapshot_returns_404_when_video_extraction_fails(self) -> None:
        """Test that 404 is returned when video exists but extraction fails."""
        from fastapi import HTTPException

        from backend.api.routes.cameras import get_camera_snapshot

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.folder_path = "/export/foscam/front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.get_settings") as mock_settings,
            patch("backend.api.routes.cameras._get_snapshot_cache_path") as mock_cache_path,
            patch("backend.api.routes.cameras._is_cache_valid") as mock_is_valid,
            patch("backend.api.routes.cameras._extract_frame_from_video") as mock_extract,
            patch("backend.api.routes.cameras.Path") as mock_path,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            cache_path = MagicMock()
            cache_path.exists.return_value = False
            mock_cache_path.return_value = cache_path
            mock_is_valid.return_value = False

            # Mock camera directory - no images, has video
            mock_camera_dir = MagicMock()
            mock_camera_dir.exists.return_value = True
            mock_camera_dir.is_dir.return_value = True
            mock_camera_dir.resolve.return_value = mock_camera_dir
            mock_camera_dir.relative_to.return_value = Path("front_door")

            mock_video_file = MagicMock()
            mock_video_file.is_file.return_value = True
            mock_video_file.suffix = ".mkv"
            mock_video_file.stat.return_value.st_mtime = 1234567890

            def rglob_side_effect(pattern):
                if ".mkv" in pattern:
                    return [mock_video_file]
                return []

            mock_camera_dir.rglob.side_effect = rglob_side_effect

            mock_path.return_value.resolve.side_effect = [
                Path("/export/foscam"),
                mock_camera_dir,
            ]

            # Extraction fails
            mock_extract.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                await get_camera_snapshot(
                    camera_id="front_door",
                    db=mock_db,
                    _rate_limit=None,
                )

            assert exc_info.value.status_code == 404
            assert "frame extraction failed" in str(exc_info.value.detail)


class TestCameraSnapshotHelpers:
    """Tests for camera snapshot helper functions (NEM-2446)."""

    def test_is_cache_valid_with_fresh_file(self, tmp_path: Path) -> None:
        """Test that a recently created cache file is considered valid."""
        from backend.api.routes.cameras import _is_cache_valid

        # Create a temporary file
        cache_file = tmp_path / "test_snapshot.jpg"
        cache_file.write_text("test")

        # Should be valid (just created)
        assert _is_cache_valid(cache_file, ttl_seconds=3600) is True

    def test_is_cache_valid_with_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that a nonexistent file is not valid."""
        from backend.api.routes.cameras import _is_cache_valid

        cache_file = tmp_path / "nonexistent.jpg"
        assert _is_cache_valid(cache_file) is False

    def test_is_cache_valid_with_expired_file(self, tmp_path: Path) -> None:
        """Test that an old cache file is considered expired."""
        import os

        from backend.api.routes.cameras import _is_cache_valid

        # Create a temporary file
        cache_file = tmp_path / "test_snapshot.jpg"
        cache_file.write_text("test")

        # Set modification time to 2 hours ago
        old_time = time.time() - 7200
        os.utime(cache_file, (old_time, old_time))

        # Should be invalid with 1 hour TTL
        assert _is_cache_valid(cache_file, ttl_seconds=3600) is False

    @pytest.mark.asyncio
    async def test_extract_frame_from_video_success(self, tmp_path: Path) -> None:
        """Test successful frame extraction from video."""
        from backend.api.routes.cameras import _extract_frame_from_video

        video_path = tmp_path / "test.mkv"
        output_path = tmp_path / "output" / "snapshot.jpg"

        with patch("backend.api.routes.cameras.asyncio.to_thread") as mock_thread:
            # Mock successful ffmpeg execution
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_thread.return_value = mock_result

            # Create the output file to simulate ffmpeg creating it
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("fake image data")

            result = await _extract_frame_from_video(video_path, output_path)

            assert result is True
            mock_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_frame_from_video_ffmpeg_fails(self, tmp_path: Path) -> None:
        """Test frame extraction when ffmpeg fails."""
        from backend.api.routes.cameras import _extract_frame_from_video

        video_path = tmp_path / "test.mkv"
        output_path = tmp_path / "output" / "snapshot.jpg"

        with patch("backend.api.routes.cameras.asyncio.to_thread") as mock_thread:
            # Mock failed ffmpeg execution
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "ffmpeg error"
            mock_thread.return_value = mock_result

            result = await _extract_frame_from_video(video_path, output_path)

            assert result is False

    @pytest.mark.asyncio
    async def test_extract_frame_from_video_timeout(self, tmp_path: Path) -> None:
        """Test frame extraction when ffmpeg times out."""
        import subprocess

        from backend.api.routes.cameras import _extract_frame_from_video

        video_path = tmp_path / "test.mkv"
        output_path = tmp_path / "output" / "snapshot.jpg"

        with patch("backend.api.routes.cameras.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = subprocess.TimeoutExpired("ffmpeg", 30)

            result = await _extract_frame_from_video(video_path, output_path)

            assert result is False

    @pytest.mark.asyncio
    async def test_extract_frame_from_video_ffmpeg_not_found(self, tmp_path: Path) -> None:
        """Test frame extraction when ffmpeg is not installed."""
        from backend.api.routes.cameras import _extract_frame_from_video

        video_path = tmp_path / "test.mkv"
        output_path = tmp_path / "output" / "snapshot.jpg"

        with patch("backend.api.routes.cameras.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = FileNotFoundError("ffmpeg not found")

            result = await _extract_frame_from_video(video_path, output_path)

            assert result is False
