"""Unit tests for scene change API routes.

Tests the scene change endpoints:
- GET /api/cameras/{camera_id}/scene-changes
- POST /api/cameras/{camera_id}/scene-changes/{id}/acknowledge

These tests follow TDD methodology - written before implementation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.scene_change import (
    SceneChangeAcknowledgeResponse,
    SceneChangeListResponse,
    SceneChangeResponse,
)


class TestGetCameraSceneChanges:
    """Tests for GET /api/cameras/{camera_id}/scene-changes endpoint."""

    @pytest.mark.asyncio
    async def test_get_scene_changes_camera_not_found(self) -> None:
        """Test that scene changes endpoint returns 404 for non-existent camera."""
        from backend.api.routes.cameras import get_camera_scene_changes

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(Exception) as exc_info:
            await get_camera_scene_changes("nonexistent_camera", db=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_scene_changes_empty_list(self) -> None:
        """Test scene changes endpoint returns empty list when no changes exist."""
        from backend.api.routes.cameras import get_camera_scene_changes

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera.name = "Test Camera"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        # Mock scene changes query
        mock_changes_result = MagicMock()
        mock_changes_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_camera_result, mock_changes_result]

        result = await get_camera_scene_changes(
            "test_camera", acknowledged=None, limit=50, offset=0, db=mock_db
        )

        assert isinstance(result, SceneChangeListResponse)
        assert result.camera_id == "test_camera"
        assert result.scene_changes == []
        assert result.total_changes == 0

    @pytest.mark.asyncio
    async def test_get_scene_changes_with_data(self) -> None:
        """Test scene changes endpoint returns scene change data."""
        from backend.api.routes.cameras import get_camera_scene_changes
        from backend.models.scene_change import SceneChange, SceneChangeType

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        # Mock scene changes
        now = datetime.now(UTC)
        mock_change1 = MagicMock(spec=SceneChange)
        mock_change1.id = 1
        mock_change1.camera_id = "front_door"
        mock_change1.detected_at = now - timedelta(hours=2)
        mock_change1.change_type = SceneChangeType.VIEW_BLOCKED
        mock_change1.similarity_score = 0.23
        mock_change1.acknowledged = False
        mock_change1.acknowledged_at = None
        mock_change1.file_path = "/path/to/image.jpg"

        mock_change2 = MagicMock(spec=SceneChange)
        mock_change2.id = 2
        mock_change2.camera_id = "front_door"
        mock_change2.detected_at = now - timedelta(hours=1)
        mock_change2.change_type = SceneChangeType.ANGLE_CHANGED
        mock_change2.similarity_score = 0.45
        mock_change2.acknowledged = True
        mock_change2.acknowledged_at = now - timedelta(minutes=30)
        mock_change2.file_path = "/path/to/image2.jpg"

        mock_changes_result = MagicMock()
        mock_changes_result.scalars.return_value.all.return_value = [
            mock_change1,
            mock_change2,
        ]

        mock_db.execute.side_effect = [mock_camera_result, mock_changes_result]

        result = await get_camera_scene_changes(
            "front_door", acknowledged=None, limit=50, offset=0, db=mock_db
        )

        assert isinstance(result, SceneChangeListResponse)
        assert result.camera_id == "front_door"
        assert result.total_changes == 2
        assert len(result.scene_changes) == 2
        assert result.scene_changes[0].id == 1
        assert result.scene_changes[0].change_type == "view_blocked"
        assert result.scene_changes[0].similarity_score == 0.23
        assert result.scene_changes[0].acknowledged is False
        assert result.scene_changes[1].id == 2
        assert result.scene_changes[1].acknowledged is True

    @pytest.mark.asyncio
    async def test_get_scene_changes_filters_unacknowledged(self) -> None:
        """Test scene changes endpoint can filter by acknowledged status."""
        from backend.api.routes.cameras import get_camera_scene_changes
        from backend.models.scene_change import SceneChange, SceneChangeType

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        # Mock scene changes - only unacknowledged
        now = datetime.now(UTC)
        mock_change = MagicMock(spec=SceneChange)
        mock_change.id = 1
        mock_change.camera_id = "test_camera"
        mock_change.detected_at = now
        mock_change.change_type = SceneChangeType.VIEW_BLOCKED
        mock_change.similarity_score = 0.30
        mock_change.acknowledged = False
        mock_change.acknowledged_at = None
        mock_change.file_path = None

        mock_changes_result = MagicMock()
        mock_changes_result.scalars.return_value.all.return_value = [mock_change]

        mock_db.execute.side_effect = [mock_camera_result, mock_changes_result]

        result = await get_camera_scene_changes(
            "test_camera", acknowledged=False, limit=50, offset=0, db=mock_db
        )

        assert isinstance(result, SceneChangeListResponse)
        assert result.total_changes == 1
        assert result.scene_changes[0].acknowledged is False


class TestAcknowledgeSceneChange:
    """Tests for POST /api/cameras/{camera_id}/scene-changes/{id}/acknowledge endpoint."""

    @pytest.mark.asyncio
    async def test_acknowledge_camera_not_found(self) -> None:
        """Test that acknowledge endpoint returns 404 for non-existent camera."""
        from backend.api.routes.cameras import acknowledge_scene_change

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        mock_request = MagicMock()

        with pytest.raises(Exception) as exc_info:
            await acknowledge_scene_change(
                "nonexistent_camera", 1, request=mock_request, db=mock_db
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_acknowledge_scene_change_not_found(self) -> None:
        """Test that acknowledge endpoint returns 404 for non-existent scene change."""
        from backend.api.routes.cameras import acknowledge_scene_change

        mock_db = AsyncMock()

        # Mock camera query - camera exists
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        # Mock scene change query - not found
        mock_change_result = MagicMock()
        mock_change_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_camera_result, mock_change_result]

        mock_request = MagicMock()

        with pytest.raises(Exception) as exc_info:
            await acknowledge_scene_change("test_camera", 999, request=mock_request, db=mock_db)

        assert exc_info.value.status_code == 404
        assert "scene change" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_acknowledge_scene_change_success(self) -> None:
        """Test successful acknowledgement of a scene change."""
        from backend.api.routes.cameras import acknowledge_scene_change
        from backend.models.scene_change import SceneChange, SceneChangeType

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        # Mock scene change
        now = datetime.now(UTC)
        mock_change = MagicMock(spec=SceneChange)
        mock_change.id = 1
        mock_change.camera_id = "front_door"
        mock_change.detected_at = now - timedelta(hours=1)
        mock_change.change_type = SceneChangeType.VIEW_BLOCKED
        mock_change.similarity_score = 0.25
        mock_change.acknowledged = False
        mock_change.acknowledged_at = None
        mock_change.file_path = "/path/to/image.jpg"

        mock_change_result = MagicMock()
        mock_change_result.scalar_one_or_none.return_value = mock_change

        mock_db.execute.side_effect = [mock_camera_result, mock_change_result]
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_request = MagicMock()

        with patch("backend.api.routes.cameras.AuditService") as mock_audit:
            mock_audit.log_action = AsyncMock()
            result = await acknowledge_scene_change(
                "front_door", 1, request=mock_request, db=mock_db
            )

        assert isinstance(result, SceneChangeAcknowledgeResponse)
        assert result.id == 1
        assert result.acknowledged is True
        assert mock_change.acknowledged is True
        assert mock_change.acknowledged_at is not None

    @pytest.mark.asyncio
    async def test_acknowledge_already_acknowledged(self) -> None:
        """Test acknowledging an already acknowledged scene change."""
        from backend.api.routes.cameras import acknowledge_scene_change
        from backend.models.scene_change import SceneChange, SceneChangeType

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        # Mock already acknowledged scene change
        now = datetime.now(UTC)
        mock_change = MagicMock(spec=SceneChange)
        mock_change.id = 1
        mock_change.camera_id = "front_door"
        mock_change.detected_at = now - timedelta(hours=2)
        mock_change.change_type = SceneChangeType.VIEW_BLOCKED
        mock_change.similarity_score = 0.25
        mock_change.acknowledged = True
        mock_change.acknowledged_at = now - timedelta(hours=1)
        mock_change.file_path = "/path/to/image.jpg"

        mock_change_result = MagicMock()
        mock_change_result.scalar_one_or_none.return_value = mock_change

        mock_db.execute.side_effect = [mock_camera_result, mock_change_result]
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_request = MagicMock()

        with patch("backend.api.routes.cameras.AuditService") as mock_audit:
            mock_audit.log_action = AsyncMock()
            result = await acknowledge_scene_change(
                "front_door", 1, request=mock_request, db=mock_db
            )

        # Should still return success even if already acknowledged
        assert isinstance(result, SceneChangeAcknowledgeResponse)
        assert result.id == 1
        assert result.acknowledged is True


class TestSceneChangeSchemas:
    """Tests for scene change Pydantic schemas."""

    def test_scene_change_response_validation(self) -> None:
        """Test SceneChangeResponse schema validation."""
        now = datetime.now(UTC)
        response = SceneChangeResponse(
            id=1,
            detected_at=now,
            change_type="view_blocked",
            similarity_score=0.45,
            acknowledged=False,
            acknowledged_at=None,
            file_path="/path/to/image.jpg",
        )
        assert response.id == 1
        assert response.change_type == "view_blocked"
        assert response.similarity_score == 0.45
        assert response.acknowledged is False

    def test_scene_change_response_with_acknowledgement(self) -> None:
        """Test SceneChangeResponse with acknowledged data."""
        now = datetime.now(UTC)
        response = SceneChangeResponse(
            id=2,
            detected_at=now - timedelta(hours=1),
            change_type="angle_changed",
            similarity_score=0.30,
            acknowledged=True,
            acknowledged_at=now,
            file_path=None,
        )
        assert response.acknowledged is True
        assert response.acknowledged_at is not None

    def test_scene_change_list_response(self) -> None:
        """Test SceneChangeListResponse schema."""
        now = datetime.now(UTC)
        changes = [
            SceneChangeResponse(
                id=1,
                detected_at=now,
                change_type="view_blocked",
                similarity_score=0.20,
                acknowledged=False,
                acknowledged_at=None,
                file_path=None,
            ),
            SceneChangeResponse(
                id=2,
                detected_at=now - timedelta(hours=1),
                change_type="view_tampered",
                similarity_score=0.35,
                acknowledged=True,
                acknowledged_at=now,
                file_path="/path/image.jpg",
            ),
        ]
        response = SceneChangeListResponse(
            camera_id="test_camera",
            scene_changes=changes,
            total_changes=2,
        )
        assert response.camera_id == "test_camera"
        assert response.total_changes == 2
        assert len(response.scene_changes) == 2

    def test_scene_change_acknowledge_response(self) -> None:
        """Test SceneChangeAcknowledgeResponse schema."""
        now = datetime.now(UTC)
        response = SceneChangeAcknowledgeResponse(
            id=1,
            acknowledged=True,
            acknowledged_at=now,
        )
        assert response.id == 1
        assert response.acknowledged is True
        assert response.acknowledged_at == now

    def test_scene_change_similarity_score_bounds(self) -> None:
        """Test that similarity_score accepts valid float values."""
        now = datetime.now(UTC)
        # Valid boundary values (SSIM returns 0-1)
        response_low = SceneChangeResponse(
            id=1,
            detected_at=now,
            change_type="unknown",
            similarity_score=0.0,
            acknowledged=False,
            acknowledged_at=None,
            file_path=None,
        )
        assert response_low.similarity_score == 0.0

        response_high = SceneChangeResponse(
            id=2,
            detected_at=now,
            change_type="unknown",
            similarity_score=1.0,
            acknowledged=False,
            acknowledged_at=None,
            file_path=None,
        )
        assert response_high.similarity_score == 1.0

    def test_scene_change_type_values(self) -> None:
        """Test valid change_type values."""
        now = datetime.now(UTC)
        valid_types = ["view_blocked", "angle_changed", "view_tampered", "unknown"]
        for change_type in valid_types:
            response = SceneChangeResponse(
                id=1,
                detected_at=now,
                change_type=change_type,
                similarity_score=0.5,
                acknowledged=False,
                acknowledged_at=None,
                file_path=None,
            )
            assert response.change_type == change_type
