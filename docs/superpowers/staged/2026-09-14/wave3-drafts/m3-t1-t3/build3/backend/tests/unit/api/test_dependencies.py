"""Unit tests for API dependency functions.

Tests for reusable entity lookup functions in backend/api/dependencies.py
that provide consistent 404 handling across route handlers.

Test cases cover:
- validate_uuid: UUID format validation utility (NEM-2563)
- get_alert_rule_or_404: Alert rule lookup and 404 handling (string IDs)
- get_zone_or_404: Zone lookup with optional camera filter (string IDs)
- get_prompt_version_or_404: Prompt version lookup
- get_event_audit_or_404: Event audit lookup by event_id
- get_audit_log_or_404: Audit log lookup
- get_or_404_factory: Generic factory for entity lookups (with optional UUID validation)
- AI service dependencies (NEM-2003): FaceDetectorService, PlateDetectorService,
  OCRService, YOLOWorldService via DI container
- NullCache: Graceful degradation pattern (NEM-2538)
- Cache availability tracking
- Service dependency injection functions
- Transaction management utilities (NEM-3346)

Note: Camera, Zone, and AlertRule use STRING IDs (not UUIDs). UUID validation
is available via get_or_404_factory's validate_uuid_format parameter for models
that do use UUID primary keys.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
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
        camera_id = str(uuid4())
        mock_zone.camera_id = camera_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_zone

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_zone_or_404(mock_zone.id, mock_db, camera_id=camera_id)

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
        camera_id = str(uuid4())
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

        zone_id = str(uuid4())
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
        """Test that existing get_camera_or_404 function works with string IDs.

        Note: Camera IDs are normalized folder names (e.g., "front_door"), not UUIDs.
        """
        from backend.api.dependencies import get_camera_or_404
        from backend.models import Camera

        camera_id = "front_door"  # Camera IDs are strings, not UUIDs
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = camera_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_camera_or_404(camera_id, mock_db)

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


class TestValidateUuid:
    """Tests for the validate_uuid utility function (NEM-2563)."""

    def test_returns_uuid_for_valid_uuid_string(self) -> None:
        """Test that function returns UUID object for valid UUID strings."""
        from uuid import UUID

        from backend.api.dependencies import validate_uuid

        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_uuid(valid_uuid, "test_field")

        assert isinstance(result, UUID)
        assert str(result) == valid_uuid

    def test_accepts_uuid_with_uppercase_letters(self) -> None:
        """Test that function accepts UUIDs with uppercase letters."""
        from uuid import UUID

        from backend.api.dependencies import validate_uuid

        valid_uuid = "550E8400-E29B-41D4-A716-446655440000"
        result = validate_uuid(valid_uuid, "test_field")

        assert isinstance(result, UUID)

    def test_accepts_uuid_without_dashes(self) -> None:
        """Test that function accepts UUIDs without dashes."""
        from uuid import UUID

        from backend.api.dependencies import validate_uuid

        valid_uuid = "550e8400e29b41d4a716446655440000"  # pragma: allowlist secret
        result = validate_uuid(valid_uuid, "test_field")

        assert isinstance(result, UUID)

    def test_raises_400_for_invalid_uuid_format(self) -> None:
        """Test that function raises 400 for invalid UUID format."""
        from backend.api.dependencies import validate_uuid

        invalid_uuid = "not-a-valid-uuid"
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid(invalid_uuid, "camera_id")

        assert exc_info.value.status_code == 400
        assert "Invalid camera_id format" in exc_info.value.detail
        assert invalid_uuid in exc_info.value.detail

    def test_raises_400_for_empty_string(self) -> None:
        """Test that function raises 400 for empty string."""
        from backend.api.dependencies import validate_uuid

        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("", "zone_id")

        assert exc_info.value.status_code == 400
        assert "Invalid zone_id format" in exc_info.value.detail

    def test_raises_400_for_too_short_uuid(self) -> None:
        """Test that function raises 400 for UUID that is too short."""
        from backend.api.dependencies import validate_uuid

        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("550e8400-e29b-41d4", "rule_id")

        assert exc_info.value.status_code == 400
        assert "Invalid rule_id format" in exc_info.value.detail

    def test_raises_400_for_sql_injection_attempt(self) -> None:
        """Test that function raises 400 for SQL injection attempts."""
        from backend.api.dependencies import validate_uuid

        injection_attempt = "'; DROP TABLE cameras; --"
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid(injection_attempt, "camera_id")

        assert exc_info.value.status_code == 400
        assert "Invalid camera_id format" in exc_info.value.detail

    def test_error_message_includes_field_name(self) -> None:
        """Test that error message includes the correct field name."""
        from backend.api.dependencies import validate_uuid

        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("bad-uuid", "custom_field_name")

        assert "custom_field_name" in exc_info.value.detail


class TestUuidValidationInGetOr404Factory:
    """Tests for UUID validation in get_or_404_factory (NEM-2563)."""

    @pytest.mark.asyncio
    async def test_factory_with_uuid_validation_raises_400_for_invalid_uuid(self) -> None:
        """Test that factory with validate_uuid_format=True raises 400 for invalid UUID."""
        from backend.models import Camera

        get_camera = get_or_404_factory(Camera, "Camera", validate_uuid_format=True)

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_camera("not-a-valid-uuid", mock_db)

        assert exc_info.value.status_code == 400
        assert "Invalid id format" in exc_info.value.detail
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_factory_without_uuid_validation_allows_any_string(self) -> None:
        """Test that factory without validate_uuid_format allows any string ID."""
        from backend.models import Camera

        get_camera = get_or_404_factory(Camera, "Camera", validate_uuid_format=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        # Should NOT raise 400, but should query database and raise 404
        with pytest.raises(HTTPException) as exc_info:
            await get_camera("any-string-value", mock_db)

        # Without UUID validation, it should query and return 404 (not 400)
        assert exc_info.value.status_code == 404
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_factory_with_uuid_validation_accepts_valid_uuid(self) -> None:
        """Test that factory with validate_uuid_format=True accepts valid UUIDs."""
        from backend.models import Camera

        get_camera = get_or_404_factory(Camera, "Camera", validate_uuid_format=True)

        mock_camera = MagicMock()
        valid_uuid = str(uuid4())
        mock_camera.id = valid_uuid

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_camera(valid_uuid, mock_db)

        assert result == mock_camera

    @pytest.mark.asyncio
    async def test_factory_uuid_validation_skips_integer_ids(self) -> None:
        """Test that factory UUID validation skips integer IDs."""
        from backend.models import Detection

        get_detection = get_or_404_factory(Detection, "Detection", validate_uuid_format=True)

        mock_detection = MagicMock()
        mock_detection.id = 42

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        # Integer IDs should NOT be validated as UUIDs
        result = await get_detection(42, mock_db)

        assert result == mock_detection
