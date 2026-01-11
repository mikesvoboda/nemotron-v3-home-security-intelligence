"""Unit tests for API dependency functions.

Tests for reusable entity lookup functions in backend/api/dependencies.py
that provide consistent 404 handling across route handlers.

Test cases cover:
- get_alert_rule_or_404: Alert rule lookup and 404 handling
- get_zone_or_404: Zone lookup with optional camera filter
- get_prompt_version_or_404: Prompt version lookup
- get_event_audit_or_404: Event audit lookup by event_id
- get_audit_log_or_404: Audit log lookup
- get_or_404_factory: Generic factory for entity lookups
- AI service dependencies (NEM-2003): FaceDetectorService, PlateDetectorService,
  OCRService, YOLOWorldService via DI container
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.api.dependencies import (
    get_alert_rule_or_404,
    get_audit_log_or_404,
    get_event_audit_or_404,
    get_or_404_factory,
    get_prompt_version_or_404,
    get_zone_or_404,
)


class TestGetAlertRuleOr404:
    """Tests for the get_alert_rule_or_404 function."""

    @pytest.mark.asyncio
    async def test_returns_rule_when_found(self) -> None:
        """Test that function returns AlertRule when found in database."""
        mock_rule = MagicMock()
        mock_rule.id = str(uuid4())
        mock_rule.name = "Test Rule"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rule

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_alert_rule_or_404(mock_rule.id, mock_db)

        assert result == mock_rule
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when rule not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        rule_id = str(uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await get_alert_rule_or_404(rule_id, mock_db)

        assert exc_info.value.status_code == 404
        assert "Alert rule" in exc_info.value.detail
        assert rule_id in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_includes_rule_id(self) -> None:
        """Test that the 404 error message includes the requested rule_id."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        rule_id = "test-rule-id-123"
        with pytest.raises(HTTPException) as exc_info:
            await get_alert_rule_or_404(rule_id, mock_db)

        assert rule_id in exc_info.value.detail


class TestGetZoneOr404:
    """Tests for the get_zone_or_404 function."""

    @pytest.mark.asyncio
    async def test_returns_zone_when_found(self) -> None:
        """Test that function returns Zone when found in database."""
        mock_zone = MagicMock()
        mock_zone.id = str(uuid4())
        mock_zone.name = "Test Zone"
        mock_zone.camera_id = "camera-1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_zone

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_zone_or_404(mock_zone.id, mock_db)

        assert result == mock_zone
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zone_when_found_with_camera_filter(self) -> None:
        """Test that function returns Zone when found with camera_id filter."""
        mock_zone = MagicMock()
        mock_zone.id = str(uuid4())
        mock_zone.name = "Test Zone"
        mock_zone.camera_id = "camera-1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_zone

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_zone_or_404(mock_zone.id, mock_db, camera_id="camera-1")

        assert result == mock_zone
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when zone not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        zone_id = str(uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await get_zone_or_404(zone_id, mock_db)

        assert exc_info.value.status_code == 404
        assert "Zone" in exc_info.value.detail
        assert zone_id in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_404_with_camera_filter_not_found(self) -> None:
        """Test that 404 message includes camera_id when filter is used."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        zone_id = str(uuid4())
        camera_id = "camera-1"
        with pytest.raises(HTTPException) as exc_info:
            await get_zone_or_404(zone_id, mock_db, camera_id=camera_id)

        assert exc_info.value.status_code == 404
        assert zone_id in exc_info.value.detail
        assert camera_id in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_without_camera_filter(self) -> None:
        """Test that 404 message format is correct without camera filter."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        zone_id = "zone-123"
        with pytest.raises(HTTPException) as exc_info:
            await get_zone_or_404(zone_id, mock_db)

        # Without camera filter, should not mention "for camera"
        assert "Zone with id" in exc_info.value.detail
        assert "for camera" not in exc_info.value.detail


class TestGetPromptVersionOr404:
    """Tests for the get_prompt_version_or_404 function."""

    @pytest.mark.asyncio
    async def test_returns_version_when_found(self) -> None:
        """Test that function returns PromptVersion when found in database."""
        mock_version = MagicMock()
        mock_version.id = 42
        mock_version.model = "nemotron"
        mock_version.version = 3

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_version

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_prompt_version_or_404(42, mock_db)

        assert result == mock_version
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when version not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        version_id = 999
        with pytest.raises(HTTPException) as exc_info:
            await get_prompt_version_or_404(version_id, mock_db)

        assert exc_info.value.status_code == 404
        assert "Prompt version" in exc_info.value.detail
        assert str(version_id) in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_includes_version_id(self) -> None:
        """Test that the 404 error message includes the requested version_id."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        version_id = 12345
        with pytest.raises(HTTPException) as exc_info:
            await get_prompt_version_or_404(version_id, mock_db)

        assert str(version_id) in exc_info.value.detail


class TestGetEventAuditOr404:
    """Tests for the get_event_audit_or_404 function."""

    @pytest.mark.asyncio
    async def test_returns_audit_when_found(self) -> None:
        """Test that function returns EventAudit when found in database."""
        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 100
        mock_audit.overall_quality_score = 4.5

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_audit

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_event_audit_or_404(100, mock_db)

        assert result == mock_audit
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when audit not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        event_id = 999
        with pytest.raises(HTTPException) as exc_info:
            await get_event_audit_or_404(event_id, mock_db)

        assert exc_info.value.status_code == 404
        assert "audit" in exc_info.value.detail.lower()
        assert str(event_id) in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_includes_event_id(self) -> None:
        """Test that the 404 error message includes the requested event_id."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        event_id = 54321
        with pytest.raises(HTTPException) as exc_info:
            await get_event_audit_or_404(event_id, mock_db)

        assert str(event_id) in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_format(self) -> None:
        """Test that the 404 error message has the expected format."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        event_id = 123
        with pytest.raises(HTTPException) as exc_info:
            await get_event_audit_or_404(event_id, mock_db)

        # Should match the format "No audit found for event {event_id}"
        assert "No audit found for event" in exc_info.value.detail


class TestGetAuditLogOr404:
    """Tests for get_audit_log_or_404 dependency function."""

    @pytest.mark.asyncio
    async def test_returns_log_when_found(self) -> None:
        """Test that function returns AuditLog when found in database."""
        mock_log = MagicMock()
        mock_log.id = 123
        mock_log.action = "camera_created"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_log

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_audit_log_or_404(123, mock_db)

        assert result == mock_log
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when log not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_audit_log_or_404(999, mock_db)

        assert exc_info.value.status_code == 404
        assert "Audit log" in exc_info.value.detail
        assert "999" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_accepts_integer_id(self) -> None:
        """Test that function accepts integer IDs (AuditLog uses int primary key)."""
        mock_log = MagicMock()
        mock_log.id = 42

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_log

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_audit_log_or_404(42, mock_db)

        assert result == mock_log


class TestGetOr404Factory:
    """Tests for the generic get_or_404_factory function."""

    @pytest.mark.asyncio
    async def test_factory_creates_working_function(self) -> None:
        """Test that factory creates a functional get_or_404 function."""
        from backend.models import Camera

        get_camera = get_or_404_factory(Camera, "Camera")

        mock_camera = MagicMock()
        mock_camera.id = "test-cam"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_camera("test-cam", mock_db)

        assert result == mock_camera

    @pytest.mark.asyncio
    async def test_factory_function_raises_404_when_not_found(self) -> None:
        """Test that factory-generated function raises 404 when entity not found."""
        from backend.models import Camera

        get_camera = get_or_404_factory(Camera, "Camera")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_camera("missing-id", mock_db)

        assert exc_info.value.status_code == 404
        assert "Camera" in exc_info.value.detail
        assert "missing-id" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_factory_uses_custom_id_field(self) -> None:
        """Test that factory can use a custom ID field name."""
        from backend.models import Camera

        get_camera_by_name = get_or_404_factory(Camera, "Camera", id_field="name")

        mock_camera = MagicMock()
        mock_camera.name = "front_door"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_camera_by_name("front_door", mock_db)

        assert result == mock_camera

    @pytest.mark.asyncio
    async def test_factory_preserves_entity_name_in_error(self) -> None:
        """Test that factory includes entity name in error message."""
        from backend.models import Detection

        get_detection = get_or_404_factory(Detection, "Detection")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_detection(123, mock_db)

        assert "Detection" in exc_info.value.detail
        assert "123" in exc_info.value.detail


class TestExistingDependencies:
    """Tests to verify existing dependency functions still work correctly."""

    @pytest.mark.asyncio
    async def test_get_camera_or_404_still_works(self) -> None:
        """Test that existing get_camera_or_404 function still works."""
        from backend.api.dependencies import get_camera_or_404
        from backend.models import Camera

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "test-camera"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_camera_or_404("test-camera", mock_db)

        assert result == mock_camera

    @pytest.mark.asyncio
    async def test_get_event_or_404_still_works(self) -> None:
        """Test that existing get_event_or_404 function still works."""
        from backend.api.dependencies import get_event_or_404
        from backend.models import Event

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_event_or_404(1, mock_db)

        assert result == mock_event

    @pytest.mark.asyncio
    async def test_get_detection_or_404_still_works(self) -> None:
        """Test that existing get_detection_or_404 function still works."""
        from backend.api.dependencies import get_detection_or_404
        from backend.models import Detection

        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 42

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_detection_or_404(42, mock_db)

        assert result == mock_detection


class TestAIServiceDependencies:
    """Tests for AI service dependency functions (NEM-2003).

    These tests verify that the AI service dependency functions properly
    retrieve services from the DI container.
    """

    @pytest.mark.asyncio
    async def test_get_face_detector_service_dep_uses_container(self) -> None:
        """Test that get_face_detector_service_dep retrieves from DI container."""
        from unittest.mock import patch

        from backend.api.dependencies import get_face_detector_service_dep

        mock_service = MagicMock()
        mock_service.name = "face_detector"

        mock_container = MagicMock()
        mock_container.get.return_value = mock_service

        # Patch at the module where get_container is defined (backend.core.container)
        with patch(
            "backend.core.container.get_container",
            return_value=mock_container,
        ):
            result = get_face_detector_service_dep()

        assert result == mock_service
        mock_container.get.assert_called_once_with("face_detector_service")

    @pytest.mark.asyncio
    async def test_get_plate_detector_service_dep_uses_container(self) -> None:
        """Test that get_plate_detector_service_dep retrieves from DI container."""
        from unittest.mock import patch

        from backend.api.dependencies import get_plate_detector_service_dep

        mock_service = MagicMock()
        mock_service.name = "plate_detector"

        mock_container = MagicMock()
        mock_container.get.return_value = mock_service

        # Patch at the module where get_container is defined (backend.core.container)
        with patch(
            "backend.core.container.get_container",
            return_value=mock_container,
        ):
            result = get_plate_detector_service_dep()

        assert result == mock_service
        mock_container.get.assert_called_once_with("plate_detector_service")

    @pytest.mark.asyncio
    async def test_get_ocr_service_dep_uses_container(self) -> None:
        """Test that get_ocr_service_dep retrieves from DI container."""
        from unittest.mock import patch

        from backend.api.dependencies import get_ocr_service_dep

        mock_service = MagicMock()
        mock_service.name = "ocr_service"

        mock_container = MagicMock()
        mock_container.get.return_value = mock_service

        # Patch at the module where get_container is defined (backend.core.container)
        with patch(
            "backend.core.container.get_container",
            return_value=mock_container,
        ):
            result = get_ocr_service_dep()

        assert result == mock_service
        mock_container.get.assert_called_once_with("ocr_service")

    @pytest.mark.asyncio
    async def test_get_yolo_world_service_dep_uses_container(self) -> None:
        """Test that get_yolo_world_service_dep retrieves from DI container."""
        from unittest.mock import patch

        from backend.api.dependencies import get_yolo_world_service_dep

        mock_service = MagicMock()
        mock_service.name = "yolo_world"

        mock_container = MagicMock()
        mock_container.get.return_value = mock_service

        # Patch at the module where get_container is defined (backend.core.container)
        with patch(
            "backend.core.container.get_container",
            return_value=mock_container,
        ):
            result = get_yolo_world_service_dep()

        assert result == mock_service
        mock_container.get.assert_called_once_with("yolo_world_service")
