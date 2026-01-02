"""Unit tests for audit logging service.

Tests cover:
- AuditService.log_action() - All parameters, enum conversion, IP extraction
- AuditService.get_audit_logs() - Filter combinations, pagination, date range filtering
- AuditService.get_audit_log_by_id() - Existence checks, not-found handling
- AI Pipeline AuditService (audit_service.py) - Model contribution flags, token estimation
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.audit import AuditAction, AuditLog, AuditStatus
from backend.services.audit import AuditService, audit_service
from backend.services.audit_service import (
    AuditService as AIPipelineAuditService,
)
from backend.services.audit_service import (
    get_audit_service,
    reset_audit_service,
)

# =============================================================================
# log_action Tests
# =============================================================================


class TestLogAction:
    """Tests for AuditService.log_action method."""

    @pytest.mark.asyncio
    async def test_log_action_minimal_parameters(self) -> None:
        """Test log_action with only required parameters."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.EVENT_REVIEWED,
            resource_type="event",
        )

        assert result.action == "event_reviewed"
        assert result.resource_type == "event"
        assert result.actor == "anonymous"
        assert result.resource_id is None
        assert result.details is None
        assert result.ip_address is None
        assert result.user_agent is None
        assert result.status == "success"
        mock_db.add.assert_called_once_with(result)
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_action_all_parameters(self) -> None:
        """Test log_action with all parameters provided."""
        mock_db = AsyncMock()

        # Create mock request
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": None,
            "user-agent": "Mozilla/5.0 TestBrowser",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="settings",
            actor="admin_user",
            resource_id="settings-123",
            details={"changed_fields": ["theme", "notifications"]},
            request=mock_request,
            status=AuditStatus.SUCCESS,
        )

        assert result.action == "settings_changed"
        assert result.resource_type == "settings"
        assert result.actor == "admin_user"
        assert result.resource_id == "settings-123"
        assert result.details == {"changed_fields": ["theme", "notifications"]}
        assert result.ip_address == "192.168.1.100"
        assert result.user_agent == "Mozilla/5.0 TestBrowser"
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_log_action_with_action_enum(self) -> None:
        """Test that action enum is properly converted to string."""
        mock_db = AsyncMock()

        for action in AuditAction:
            result = await AuditService.log_action(
                db=mock_db,
                action=action,
                resource_type="test",
            )
            assert result.action == action.value

    @pytest.mark.asyncio
    async def test_log_action_with_action_string(self) -> None:
        """Test that action string is passed through directly."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action="custom_action",
            resource_type="test",
        )

        assert result.action == "custom_action"

    @pytest.mark.asyncio
    async def test_log_action_with_status_enum(self) -> None:
        """Test that status enum is properly converted to string."""
        mock_db = AsyncMock()

        for status in AuditStatus:
            result = await AuditService.log_action(
                db=mock_db,
                action=AuditAction.LOGIN,
                resource_type="auth",
                status=status,
            )
            assert result.status == status.value

    @pytest.mark.asyncio
    async def test_log_action_with_status_string(self) -> None:
        """Test that status string is passed through directly."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            status="custom_status",
        )

        assert result.status == "custom_status"

    @pytest.mark.asyncio
    async def test_log_action_failure_status(self) -> None:
        """Test log_action with failure status."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            status=AuditStatus.FAILURE,
            details={"error": "Invalid credentials"},
        )

        assert result.status == "failure"
        assert result.details == {"error": "Invalid credentials"}

    @pytest.mark.asyncio
    async def test_log_action_timestamp_is_set(self) -> None:
        """Test that timestamp is automatically set."""
        mock_db = AsyncMock()

        before = datetime.now(UTC)
        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
        )
        after = datetime.now(UTC)

        assert result.timestamp is not None
        assert before <= result.timestamp <= after


# =============================================================================
# log_action Request/IP Extraction Tests
# =============================================================================


class TestLogActionRequestExtraction:
    """Tests for IP and user agent extraction from request."""

    @pytest.mark.asyncio
    async def test_log_action_x_forwarded_for_single_ip(self) -> None:
        """Test extraction of single IP from X-Forwarded-For header."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": "203.0.113.50",
            "user-agent": "TestAgent",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        # Should use X-Forwarded-For IP instead of client IP
        assert result.ip_address == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_log_action_x_forwarded_for_multiple_ips(self) -> None:
        """Test extraction of first IP from X-Forwarded-For with multiple IPs."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": "203.0.113.50, 198.51.100.25, 10.0.0.1",
            "user-agent": "TestAgent",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        # Should use the first IP (original client)
        assert result.ip_address == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_log_action_x_forwarded_for_with_spaces(self) -> None:
        """Test that IPs in X-Forwarded-For are properly trimmed."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": "  203.0.113.50  ,  198.51.100.25  ",
            "user-agent": "TestAgent",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        # Should trim whitespace
        assert result.ip_address == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_log_action_no_x_forwarded_for(self) -> None:
        """Test fallback to client IP when X-Forwarded-For is absent."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": None,
            "user-agent": "TestAgent",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        assert result.ip_address == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_log_action_no_client_info(self) -> None:
        """Test handling when request.client is None."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client = None
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": None,
            "user-agent": "TestAgent",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        assert result.ip_address is None
        assert result.user_agent == "TestAgent"

    @pytest.mark.asyncio
    async def test_log_action_no_request(self) -> None:
        """Test handling when no request object is provided."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.DATA_CLEARED,
            resource_type="system",
            actor="system",
        )

        assert result.ip_address is None
        assert result.user_agent is None

    @pytest.mark.asyncio
    async def test_log_action_no_user_agent(self) -> None:
        """Test handling when user-agent header is missing."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": None,
            "user-agent": None,
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        assert result.ip_address == "192.168.1.100"
        assert result.user_agent is None

    @pytest.mark.asyncio
    async def test_log_action_x_forwarded_for_overrides_client(self) -> None:
        """Test X-Forwarded-For takes precedence even when client is present."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": "8.8.8.8",
            "user-agent": "TestAgent",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        # X-Forwarded-For should override client IP
        assert result.ip_address == "8.8.8.8"


# =============================================================================
# AI Pipeline AuditService Tests (from audit_service.py)
# =============================================================================


@dataclass
class MockEnrichmentResult:
    """Mock EnrichmentResult for testing."""

    has_vision_extraction: bool = False
    person_reid_matches: dict = field(default_factory=dict)
    vehicle_reid_matches: dict = field(default_factory=dict)
    has_violence: bool = False
    has_clothing_classifications: bool = False
    has_vehicle_classifications: bool = False
    has_vehicle_damage: bool = False
    has_pet_classifications: bool = False
    weather_classification: object | None = None
    has_image_quality: bool = False


@dataclass
class MockEnrichedContext:
    """Mock EnrichedContext for testing."""

    zones: list = field(default_factory=list)
    baselines: object | None = None
    cross_camera: object | None = None


class TestAIPipelineAuditService:
    """Tests for the AI Pipeline AuditService (audit_service.py)."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        reset_audit_service()

    def test_create_partial_audit_basic(self) -> None:
        """Test creating partial audit with no enrichment."""
        service = AIPipelineAuditService()
        audit = service.create_partial_audit(
            event_id=123,
            llm_prompt="test prompt",
            enriched_context=None,
            enrichment_result=None,
        )
        assert audit.event_id == 123
        assert audit.prompt_length == len("test prompt")
        assert audit.has_rtdetr is True
        assert audit.has_florence is False

    def test_create_partial_audit_with_prompt_metrics(self) -> None:
        """Test prompt length and token estimate calculation."""
        service = AIPipelineAuditService()
        prompt = "This is a test prompt with multiple words"
        audit = service.create_partial_audit(
            event_id=456,
            llm_prompt=prompt,
            enriched_context=None,
            enrichment_result=None,
        )
        assert audit.prompt_length == len(prompt)
        assert audit.prompt_token_estimate == len(prompt) // 4

    def test_create_partial_audit_with_enrichment_result(self) -> None:
        """Test creating audit with enrichment result flags."""
        service = AIPipelineAuditService()

        # Mock enrichment result with florence and violence
        mock_result = MockEnrichmentResult(
            has_vision_extraction=True,
            has_violence=True,
            has_clothing_classifications=True,
        )

        audit = service.create_partial_audit(
            event_id=789,
            llm_prompt="test",
            enriched_context=None,
            enrichment_result=mock_result,  # type: ignore[arg-type]
        )

        assert audit.has_rtdetr is True
        assert audit.has_florence is True
        assert audit.has_violence is True
        assert audit.has_clothing is True
        assert audit.has_clip is False
        assert audit.has_vehicle is False

    def test_create_partial_audit_with_enriched_context(self) -> None:
        """Test creating audit with enriched context flags."""
        service = AIPipelineAuditService()

        # Mock enriched context with zones and baselines
        mock_context = MockEnrichedContext(
            zones=[{"zone_id": "z1"}],
            baselines=MagicMock(),
            cross_camera=MagicMock(),
        )

        audit = service.create_partial_audit(
            event_id=101,
            llm_prompt="test",
            enriched_context=mock_context,  # type: ignore[arg-type]
            enrichment_result=None,
        )

        assert audit.has_zones is True
        assert audit.has_baseline is True
        assert audit.has_cross_camera is True

    def test_create_partial_audit_no_prompt(self) -> None:
        """Test creating audit with no LLM prompt."""
        service = AIPipelineAuditService()
        audit = service.create_partial_audit(
            event_id=999,
            llm_prompt=None,
            enriched_context=None,
            enrichment_result=None,
        )
        assert audit.prompt_length == 0
        assert audit.prompt_token_estimate == 0

    def test_estimate_tokens_none(self) -> None:
        """Test token estimation with None input."""
        service = AIPipelineAuditService()
        assert service._estimate_tokens(None) == 0

    def test_estimate_tokens_empty(self) -> None:
        """Test token estimation with empty string."""
        service = AIPipelineAuditService()
        assert service._estimate_tokens("") == 0

    def test_estimate_tokens_short(self) -> None:
        """Test token estimation with short string."""
        service = AIPipelineAuditService()
        assert service._estimate_tokens("test") == 1  # 4 chars / 4 = 1

    def test_estimate_tokens_long(self) -> None:
        """Test token estimation with long string."""
        service = AIPipelineAuditService()
        assert service._estimate_tokens("a" * 100) == 25  # 100 chars / 4 = 25

    def test_estimate_tokens_calculation(self) -> None:
        """Test token estimation calculation (chars / 4)."""
        service = AIPipelineAuditService()
        # Test various lengths
        assert service._estimate_tokens("ab") == 0  # 2 / 4 = 0 (integer division)
        assert service._estimate_tokens("abcd") == 1  # 4 / 4 = 1
        assert service._estimate_tokens("abcdefgh") == 2  # 8 / 4 = 2
        assert service._estimate_tokens("x" * 12) == 3  # 12 / 4 = 3

    def test_calc_utilization_empty(self) -> None:
        """Test enrichment utilization with no enrichment."""
        service = AIPipelineAuditService()
        util = service._calc_utilization(None, None)
        # Should be 1/12 (just rtdetr)
        assert util == pytest.approx(1 / 12)

    def test_calc_utilization_with_florence(self) -> None:
        """Test enrichment utilization with Florence enabled."""
        service = AIPipelineAuditService()
        mock_result = MockEnrichmentResult(has_vision_extraction=True)
        util = service._calc_utilization(None, mock_result)  # type: ignore[arg-type]
        # rtdetr + florence = 2/12
        assert util == pytest.approx(2 / 12)

    def test_calc_utilization_with_multiple_enrichments(self) -> None:
        """Test enrichment utilization with multiple enrichments."""
        service = AIPipelineAuditService()
        mock_result = MockEnrichmentResult(
            has_vision_extraction=True,
            has_violence=True,
            has_clothing_classifications=True,
            has_vehicle_classifications=True,
            has_image_quality=True,
        )
        mock_context = MockEnrichedContext(
            zones=[{"z1": "zone"}],
            baselines=MagicMock(),
        )
        util = service._calc_utilization(mock_context, mock_result)  # type: ignore[arg-type]
        # rtdetr + florence + violence + clothing + vehicle + image_quality + zones + baseline = 8/12
        assert util == pytest.approx(8 / 12)

    def test_calc_utilization_full(self) -> None:
        """Test enrichment utilization with all enrichments."""
        service = AIPipelineAuditService()
        mock_result = MockEnrichmentResult(
            has_vision_extraction=True,
            person_reid_matches={"p1": []},  # Non-empty dict for clip
            has_violence=True,
            has_clothing_classifications=True,
            has_vehicle_classifications=True,
            has_vehicle_damage=True,
            has_pet_classifications=True,
            weather_classification=MagicMock(),
            has_image_quality=True,
        )
        mock_context = MockEnrichedContext(
            zones=[{"z1": "zone"}],
            baselines=MagicMock(),
            cross_camera=MagicMock(),
        )
        util = service._calc_utilization(mock_context, mock_result)  # type: ignore[arg-type]
        # All 12 enrichments enabled
        assert util == pytest.approx(12 / 12)

    def test_singleton_get_audit_service(self) -> None:
        """Test service singleton returns same instance."""
        s1 = get_audit_service()
        s2 = get_audit_service()
        assert s1 is s2

    def test_singleton_reset(self) -> None:
        """Test singleton reset creates new instance."""
        s1 = get_audit_service()
        reset_audit_service()
        s2 = get_audit_service()
        assert s1 is not s2

    def test_singleton_is_audit_service(self) -> None:
        """Test singleton is an AIPipelineAuditService instance."""
        service = get_audit_service()
        assert isinstance(service, AIPipelineAuditService)


class TestAIPipelineAuditServiceModelFlags:
    """Tests for model contribution flag detection."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        reset_audit_service()

    def test_has_florence_true(self) -> None:
        """Test Florence detection when has_vision_extraction is True."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_vision_extraction=True)
        assert service._has_florence(result) is True  # type: ignore[arg-type]

    def test_has_florence_false(self) -> None:
        """Test Florence detection when has_vision_extraction is False."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_vision_extraction=False)
        assert service._has_florence(result) is False  # type: ignore[arg-type]

    def test_has_florence_none(self) -> None:
        """Test Florence detection when result is None."""
        service = AIPipelineAuditService()
        assert service._has_florence(None) is False

    def test_has_clip_with_person_matches(self) -> None:
        """Test CLIP detection with person re-ID matches."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(person_reid_matches={"p1": []})
        assert service._has_clip(result) is True  # type: ignore[arg-type]

    def test_has_clip_with_vehicle_matches(self) -> None:
        """Test CLIP detection with vehicle re-ID matches."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(vehicle_reid_matches={"v1": []})
        assert service._has_clip(result) is True  # type: ignore[arg-type]

    def test_has_clip_empty(self) -> None:
        """Test CLIP detection with no re-ID matches."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult()
        assert service._has_clip(result) is False  # type: ignore[arg-type]

    def test_has_violence_true(self) -> None:
        """Test violence detection flag."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_violence=True)
        assert service._has_violence(result) is True  # type: ignore[arg-type]

    def test_has_violence_false(self) -> None:
        """Test violence detection flag when False."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_violence=False)
        assert service._has_violence(result) is False  # type: ignore[arg-type]

    def test_has_clothing_true(self) -> None:
        """Test clothing classification flag."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_clothing_classifications=True)
        assert service._has_clothing(result) is True  # type: ignore[arg-type]

    def test_has_vehicle_classifications(self) -> None:
        """Test vehicle classification flag."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_vehicle_classifications=True)
        assert service._has_vehicle(result) is True  # type: ignore[arg-type]

    def test_has_vehicle_damage(self) -> None:
        """Test vehicle damage flag."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_vehicle_damage=True)
        assert service._has_vehicle(result) is True  # type: ignore[arg-type]

    def test_has_pet_true(self) -> None:
        """Test pet classification flag."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_pet_classifications=True)
        assert service._has_pet(result) is True  # type: ignore[arg-type]

    def test_has_weather_true(self) -> None:
        """Test weather classification flag."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(weather_classification=MagicMock())
        assert service._has_weather(result) is True  # type: ignore[arg-type]

    def test_has_weather_none(self) -> None:
        """Test weather classification flag when None."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(weather_classification=None)
        assert service._has_weather(result) is False  # type: ignore[arg-type]

    def test_has_image_quality_true(self) -> None:
        """Test image quality flag."""
        service = AIPipelineAuditService()
        result = MockEnrichmentResult(has_image_quality=True)
        assert service._has_image_quality(result) is True  # type: ignore[arg-type]

    def test_has_zones_true(self) -> None:
        """Test zones flag when zones list is non-empty."""
        service = AIPipelineAuditService()
        context = MockEnrichedContext(zones=[{"z1": "zone"}])
        assert service._has_zones(context) is True  # type: ignore[arg-type]

    def test_has_zones_empty(self) -> None:
        """Test zones flag when zones list is empty."""
        service = AIPipelineAuditService()
        context = MockEnrichedContext(zones=[])
        assert service._has_zones(context) is False  # type: ignore[arg-type]

    def test_has_zones_none(self) -> None:
        """Test zones flag when context is None."""
        service = AIPipelineAuditService()
        assert service._has_zones(None) is False

    def test_has_baseline_true(self) -> None:
        """Test baseline flag when baselines is not None."""
        service = AIPipelineAuditService()
        context = MockEnrichedContext(baselines=MagicMock())
        assert service._has_baseline(context) is True  # type: ignore[arg-type]

    def test_has_baseline_none(self) -> None:
        """Test baseline flag when baselines is None."""
        service = AIPipelineAuditService()
        context = MockEnrichedContext(baselines=None)
        assert service._has_baseline(context) is False  # type: ignore[arg-type]

    def test_has_cross_camera_true(self) -> None:
        """Test cross_camera flag when not None."""
        service = AIPipelineAuditService()
        context = MockEnrichedContext(cross_camera=MagicMock())
        assert service._has_cross_camera(context) is True  # type: ignore[arg-type]

    def test_has_cross_camera_none(self) -> None:
        """Test cross_camera flag when None."""
        service = AIPipelineAuditService()
        context = MockEnrichedContext(cross_camera=None)
        assert service._has_cross_camera(context) is False  # type: ignore[arg-type]


# =============================================================================
# get_audit_logs Tests
# =============================================================================


class TestGetAuditLogs:
    """Tests for AuditService.get_audit_logs method."""

    @pytest.mark.asyncio
    async def test_get_audit_logs_no_filters(self) -> None:
        """Test get_audit_logs with no filters returns all logs."""
        mock_db = AsyncMock()

        # Setup mock for count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        # Setup mock audit logs
        mock_log1 = MagicMock(spec=AuditLog)
        mock_log2 = MagicMock(spec=AuditLog)
        mock_log3 = MagicMock(spec=AuditLog)

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_log1, mock_log2, mock_log3]
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(db=mock_db)

        assert len(logs) == 3
        assert total == 5

    @pytest.mark.asyncio
    async def test_get_audit_logs_empty_results(self) -> None:
        """Test get_audit_logs returns empty list when no logs exist."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(db=mock_db)

        assert logs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_action(self) -> None:
        """Test filtering logs by action type."""
        mock_db = AsyncMock()

        mock_log = MagicMock(spec=AuditLog)
        mock_log.action = "login"

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_log]
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            action="login",
        )

        assert len(logs) == 1
        assert total == 1
        # Verify that execute was called (filter applied)
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_resource_type(self) -> None:
        """Test filtering logs by resource type."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(), MagicMock()]
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            resource_type="event",
        )

        assert len(logs) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_resource_id(self) -> None:
        """Test filtering logs by specific resource ID."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()]
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            resource_id="event-123",
        )

        assert len(logs) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_actor(self) -> None:
        """Test filtering logs by actor."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            actor="admin_user",
        )

        assert len(logs) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_status(self) -> None:
        """Test filtering logs by status."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(), MagicMock()]
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            status="failure",
        )

        assert len(logs) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_date_range(self) -> None:
        """Test filtering logs by date range."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()] * 5
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        start_date = datetime(2025, 1, 1, tzinfo=UTC)
        end_date = datetime(2025, 12, 31, tzinfo=UTC)

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            start_date=start_date,
            end_date=end_date,
        )

        assert len(logs) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_start_date_only(self) -> None:
        """Test filtering logs with only start date."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()] * 3
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        start_date = datetime(2025, 6, 1, tzinfo=UTC)

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            start_date=start_date,
        )

        assert len(logs) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_end_date_only(self) -> None:
        """Test filtering logs with only end date."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 4

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()] * 4
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        end_date = datetime(2025, 6, 30, tzinfo=UTC)

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            end_date=end_date,
        )

        assert len(logs) == 4
        assert total == 4

    @pytest.mark.asyncio
    async def test_get_audit_logs_combined_filters(self) -> None:
        """Test get_audit_logs with multiple filters combined."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()]
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            action="login",
            resource_type="auth",
            actor="admin",
            status="success",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 12, 31, tzinfo=UTC),
        )

        assert len(logs) == 1
        assert total == 1


# =============================================================================
# get_audit_logs Pagination Tests
# =============================================================================


class TestGetAuditLogsPagination:
    """Tests for pagination in get_audit_logs."""

    @pytest.mark.asyncio
    async def test_get_audit_logs_default_pagination(self) -> None:
        """Test default pagination (limit=100, offset=0)."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 150

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()] * 100
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(db=mock_db)

        assert len(logs) == 100
        assert total == 150

    @pytest.mark.asyncio
    async def test_get_audit_logs_custom_limit(self) -> None:
        """Test custom limit parameter."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()] * 10
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            limit=10,
        )

        assert len(logs) == 10
        assert total == 50

    @pytest.mark.asyncio
    async def test_get_audit_logs_custom_offset(self) -> None:
        """Test custom offset parameter."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()] * 20
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            offset=30,
        )

        assert len(logs) == 20
        assert total == 50

    @pytest.mark.asyncio
    async def test_get_audit_logs_pagination_boundary_first_page(self) -> None:
        """Test pagination at first page boundary."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 25

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()] * 10
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            limit=10,
            offset=0,
        )

        assert len(logs) == 10
        assert total == 25

    @pytest.mark.asyncio
    async def test_get_audit_logs_pagination_boundary_last_page(self) -> None:
        """Test pagination at last page with partial results."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 25

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        # Last page has only 5 items
        mock_scalars.all.return_value = [MagicMock()] * 5
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            limit=10,
            offset=20,
        )

        assert len(logs) == 5
        assert total == 25

    @pytest.mark.asyncio
    async def test_get_audit_logs_pagination_beyond_total(self) -> None:
        """Test pagination when offset exceeds total records."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 25

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            limit=10,
            offset=100,
        )

        assert logs == []
        assert total == 25

    @pytest.mark.asyncio
    async def test_get_audit_logs_limit_one(self) -> None:
        """Test with limit=1."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()]
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(
            db=mock_db,
            limit=1,
        )

        assert len(logs) == 1
        assert total == 100

    @pytest.mark.asyncio
    async def test_get_audit_logs_count_returns_none(self) -> None:
        """Test handling when count query returns None."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = None

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await AuditService.get_audit_logs(db=mock_db)

        assert logs == []
        assert total == 0


# =============================================================================
# get_audit_log_by_id Tests
# =============================================================================


class TestGetAuditLogById:
    """Tests for AuditService.get_audit_log_by_id method."""

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_found(self) -> None:
        """Test retrieving an existing audit log by ID."""
        mock_db = AsyncMock()

        mock_log = MagicMock(spec=AuditLog)
        mock_log.id = 123
        mock_log.action = "login"
        mock_log.resource_type = "auth"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_log
        mock_db.execute.return_value = mock_result

        result = await AuditService.get_audit_log_by_id(
            db=mock_db,
            audit_id=123,
        )

        assert result is mock_log
        assert result.id == 123

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_not_found(self) -> None:
        """Test retrieving a non-existent audit log returns None."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await AuditService.get_audit_log_by_id(
            db=mock_db,
            audit_id=999,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_zero(self) -> None:
        """Test retrieving with ID 0."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await AuditService.get_audit_log_by_id(
            db=mock_db,
            audit_id=0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_negative(self) -> None:
        """Test retrieving with negative ID."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await AuditService.get_audit_log_by_id(
            db=mock_db,
            audit_id=-1,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_large_id(self) -> None:
        """Test retrieving with very large ID."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await AuditService.get_audit_log_by_id(
            db=mock_db,
            audit_id=999999999,
        )

        assert result is None


# =============================================================================
# Singleton Tests
# =============================================================================


class TestAuditServiceSingleton:
    """Tests for the audit_service singleton instance."""

    def test_audit_service_singleton_exists(self) -> None:
        """Test that audit_service singleton is an AuditService instance."""
        assert audit_service is not None
        assert isinstance(audit_service, AuditService)

    @pytest.mark.asyncio
    async def test_audit_service_singleton_log_action(self) -> None:
        """Test that singleton can be used for log_action."""
        mock_db = AsyncMock()

        result = await audit_service.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
        )

        assert result.action == "login"

    @pytest.mark.asyncio
    async def test_audit_service_singleton_get_audit_logs(self) -> None:
        """Test that singleton can be used for get_audit_logs."""
        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_logs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_logs_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_logs_result]

        logs, total = await audit_service.get_audit_logs(db=mock_db)

        assert logs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_audit_service_singleton_get_audit_log_by_id(self) -> None:
        """Test that singleton can be used for get_audit_log_by_id."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await audit_service.get_audit_log_by_id(
            db=mock_db,
            audit_id=1,
        )

        assert result is None


# =============================================================================
# All AuditAction Enum Values Tests
# =============================================================================


class TestAuditActionEnumValues:
    """Tests to ensure all AuditAction enum values work correctly."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action",
        list(AuditAction),
        ids=[a.name for a in AuditAction],
    )
    async def test_log_action_with_all_enum_values(self, action: AuditAction) -> None:
        """Test log_action works with each AuditAction enum value."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action=action,
            resource_type="test",
        )

        assert result.action == action.value


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    @pytest.mark.asyncio
    async def test_log_action_with_empty_details_dict(self) -> None:
        """Test log_action with empty details dictionary."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="settings",
            details={},
        )

        assert result.details == {}

    @pytest.mark.asyncio
    async def test_log_action_with_nested_details(self) -> None:
        """Test log_action with deeply nested details."""
        mock_db = AsyncMock()

        complex_details = {
            "changes": {
                "before": {"theme": "light", "notifications": {"email": True}},
                "after": {"theme": "dark", "notifications": {"email": False}},
            },
            "metadata": {
                "version": "1.0",
                "timestamp": "2025-01-01T00:00:00Z",
            },
        }

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="settings",
            details=complex_details,
        )

        assert result.details == complex_details

    @pytest.mark.asyncio
    async def test_log_action_with_special_characters_in_resource_id(self) -> None:
        """Test log_action with special characters in resource_id."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.EVENT_REVIEWED,
            resource_type="event",
            resource_id="event/123/sub-event_456",
        )

        assert result.resource_id == "event/123/sub-event_456"

    @pytest.mark.asyncio
    async def test_log_action_with_unicode_in_actor(self) -> None:
        """Test log_action with unicode characters in actor."""
        mock_db = AsyncMock()

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            actor="user_test_name",
        )

        assert result.actor == "user_test_name"

    @pytest.mark.asyncio
    async def test_log_action_with_long_user_agent(self) -> None:
        """Test log_action with very long user agent string."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"

        long_user_agent = "Mozilla/5.0 " + "x" * 1000

        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": None,
            "user-agent": long_user_agent,
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        assert result.user_agent == long_user_agent

    @pytest.mark.asyncio
    async def test_log_action_ipv6_address(self) -> None:
        """Test log_action with IPv6 address in X-Forwarded-For."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "user-agent": "TestAgent",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        assert result.ip_address == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

    @pytest.mark.asyncio
    async def test_log_action_mixed_ipv4_ipv6_forwarded(self) -> None:
        """Test X-Forwarded-For with mixed IPv4 and IPv6 addresses."""
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: {
            "x-forwarded-for": "2001:db8::1, 192.168.1.1, 10.0.0.1",
            "user-agent": "TestAgent",
        }.get(key)

        result = await AuditService.log_action(
            db=mock_db,
            action=AuditAction.LOGIN,
            resource_type="auth",
            request=mock_request,
        )

        # Should use first IP (IPv6)
        assert result.ip_address == "2001:db8::1"
