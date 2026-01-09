"""Unit tests for AI fallback service.

Tests cover:
- AIService, DegradationLevel, ServiceStatus enum values
- ServiceState dataclass and to_dict() serialization
- FallbackRiskAnalysis dataclass and to_dict() serialization
- RiskScoreCache caching behavior and TTL expiration
- AIFallbackService initialization and configuration
- Circuit breaker registration
- Status callback registration and notification
- Health check loop lifecycle (start/stop)
- Service health checks for all AI services
- Service availability checks
- Degradation level calculation based on service states
- Available features based on service health
- Fallback methods (risk analysis, captions, embeddings)
- Global instance management (get/reset functions)
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.ai_fallback import (
    CRITICAL_SERVICES,
    DEFAULT_CB_CONFIGS,
    AIFallbackService,
    AIService,
    DegradationLevel,
    FallbackRiskAnalysis,
    RiskScoreCache,
    ServiceState,
    ServiceStatus,
    get_ai_fallback_service,
    reset_ai_fallback_service,
)
from backend.services.circuit_breaker import CircuitBreaker, CircuitState

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_global_service():
    """Reset global AI fallback service before and after each test."""
    reset_ai_fallback_service()
    yield
    reset_ai_fallback_service()


@pytest.fixture
def mock_detector_client():
    """Create a mock RT-DETRv2 detector client."""
    client = MagicMock()
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_nemotron_analyzer():
    """Create a mock Nemotron analyzer."""
    analyzer = MagicMock()
    analyzer.health_check = AsyncMock(return_value=True)
    return analyzer


@pytest.fixture
def mock_florence_client():
    """Create a mock Florence-2 client."""
    client = MagicMock()
    client.check_health = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_clip_client():
    """Create a mock CLIP client."""
    client = MagicMock()
    client.check_health = AsyncMock(return_value=True)
    return client


@pytest.fixture
def fallback_service(
    mock_detector_client,
    mock_nemotron_analyzer,
    mock_florence_client,
    mock_clip_client,
):
    """Create an AIFallbackService with mock clients."""
    return AIFallbackService(
        detector_client=mock_detector_client,
        nemotron_analyzer=mock_nemotron_analyzer,
        florence_client=mock_florence_client,
        clip_client=mock_clip_client,
        health_check_interval=0.05,  # Fast for testing
    )


# =============================================================================
# Enum Tests
# =============================================================================


class TestAIServiceEnum:
    """Tests for AIService enum."""

    def test_service_enum_values(self) -> None:
        """Test that AIService enum has expected values."""
        assert AIService.RTDETR.value == "rtdetr"
        assert AIService.NEMOTRON.value == "nemotron"
        assert AIService.FLORENCE.value == "florence"
        assert AIService.CLIP.value == "clip"

    def test_service_enum_count(self) -> None:
        """Test that AIService has exactly 4 services."""
        assert len(list(AIService)) == 4


class TestDegradationLevelEnum:
    """Tests for DegradationLevel enum."""

    def test_degradation_level_values(self) -> None:
        """Test that DegradationLevel enum has expected values."""
        assert DegradationLevel.NORMAL.value == "normal"
        assert DegradationLevel.DEGRADED.value == "degraded"
        assert DegradationLevel.MINIMAL.value == "minimal"
        assert DegradationLevel.OFFLINE.value == "offline"


class TestServiceStatusEnum:
    """Tests for ServiceStatus enum."""

    def test_service_status_values(self) -> None:
        """Test that ServiceStatus enum has expected values."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.UNAVAILABLE.value == "unavailable"


# =============================================================================
# ServiceState Dataclass Tests
# =============================================================================


class TestServiceState:
    """Tests for ServiceState dataclass."""

    def test_default_initialization(self) -> None:
        """Test ServiceState with default values."""
        state = ServiceState(service=AIService.RTDETR)
        assert state.service == AIService.RTDETR
        assert state.status == ServiceStatus.HEALTHY
        assert state.circuit_state == CircuitState.CLOSED
        assert state.last_success is None
        assert state.failure_count == 0
        assert state.error_message is None
        assert state.last_check is None

    def test_custom_initialization(self) -> None:
        """Test ServiceState with custom values."""
        now = datetime.now(UTC)
        state = ServiceState(
            service=AIService.NEMOTRON,
            status=ServiceStatus.DEGRADED,
            circuit_state=CircuitState.HALF_OPEN,
            last_success=now,
            failure_count=2,
            error_message="Timeout error",
            last_check=now,
        )
        assert state.service == AIService.NEMOTRON
        assert state.status == ServiceStatus.DEGRADED
        assert state.circuit_state == CircuitState.HALF_OPEN
        assert state.last_success == now
        assert state.failure_count == 2
        assert state.error_message == "Timeout error"
        assert state.last_check == now

    def test_to_dict_with_timestamps(self) -> None:
        """Test to_dict() serialization with timestamps."""
        now = datetime.now(UTC)
        state = ServiceState(
            service=AIService.FLORENCE,
            status=ServiceStatus.UNAVAILABLE,
            last_success=now,
            failure_count=5,
            last_check=now,
        )
        result = state.to_dict()

        assert result["service"] == "florence"
        assert result["status"] == "unavailable"
        assert result["circuit_state"] == "closed"
        assert result["last_success"] == now.isoformat()
        assert result["failure_count"] == 5
        assert result["error_message"] is None
        assert result["last_check"] == now.isoformat()

    def test_to_dict_without_timestamps(self) -> None:
        """Test to_dict() serialization without timestamps."""
        state = ServiceState(
            service=AIService.CLIP,
            status=ServiceStatus.HEALTHY,
        )
        result = state.to_dict()

        assert result["last_success"] is None
        assert result["last_check"] is None


# =============================================================================
# FallbackRiskAnalysis Dataclass Tests
# =============================================================================


class TestFallbackRiskAnalysis:
    """Tests for FallbackRiskAnalysis dataclass."""

    def test_default_initialization(self) -> None:
        """Test FallbackRiskAnalysis with required fields."""
        analysis = FallbackRiskAnalysis(
            risk_score=50,
            reasoning="Default fallback reasoning",
        )
        assert analysis.risk_score == 50
        assert analysis.reasoning == "Default fallback reasoning"
        assert analysis.is_fallback is True
        assert analysis.source == "default"

    def test_custom_initialization(self) -> None:
        """Test FallbackRiskAnalysis with custom values."""
        analysis = FallbackRiskAnalysis(
            risk_score=75,
            reasoning="Cached risk score",
            is_fallback=True,
            source="cache",
        )
        assert analysis.risk_score == 75
        assert analysis.reasoning == "Cached risk score"
        assert analysis.is_fallback is True
        assert analysis.source == "cache"

    def test_to_dict(self) -> None:
        """Test to_dict() serialization."""
        analysis = FallbackRiskAnalysis(
            risk_score=60,
            reasoning="Object type estimate",
            source="object_type_estimate",
        )
        result = analysis.to_dict()

        assert result["risk_score"] == 60
        assert result["reasoning"] == "Object type estimate"
        assert result["is_fallback"] is True
        assert result["source"] == "object_type_estimate"


# =============================================================================
# RiskScoreCache Tests
# =============================================================================


class TestRiskScoreCache:
    """Tests for RiskScoreCache dataclass."""

    def test_default_initialization(self) -> None:
        """Test RiskScoreCache with default values."""
        cache = RiskScoreCache()
        assert cache.camera_scores == {}
        assert "person" in cache.object_type_scores
        assert cache.object_type_scores["person"] == 60
        assert cache.ttl_seconds == 300

    def test_custom_ttl(self) -> None:
        """Test RiskScoreCache with custom TTL."""
        cache = RiskScoreCache(ttl_seconds=600)
        assert cache.ttl_seconds == 600

    def test_set_and_get_cached_score(self) -> None:
        """Test caching and retrieving score."""
        cache = RiskScoreCache()
        cache.set_cached_score("front_door", 75)

        score = cache.get_cached_score("front_door")
        assert score == 75

    def test_get_cached_score_expired(self) -> None:
        """Test that expired cache returns None."""
        cache = RiskScoreCache(ttl_seconds=0.01)  # 10ms TTL
        cache.set_cached_score("back_door", 80)

        # Wait for expiration
        time.sleep(0.02)

        score = cache.get_cached_score("back_door")
        assert score is None

    def test_get_cached_score_not_found(self) -> None:
        """Test getting score for non-existent camera."""
        cache = RiskScoreCache()
        score = cache.get_cached_score("nonexistent_camera")
        assert score is None

    def test_get_object_type_score_known_type(self) -> None:
        """Test getting score for known object type."""
        cache = RiskScoreCache()
        assert cache.get_object_type_score("person") == 60
        assert cache.get_object_type_score("vehicle") == 50
        assert cache.get_object_type_score("dog") == 25

    def test_get_object_type_score_case_insensitive(self) -> None:
        """Test that object type lookup is case insensitive."""
        cache = RiskScoreCache()
        assert cache.get_object_type_score("PERSON") == 60
        assert cache.get_object_type_score("Person") == 60

    def test_get_object_type_score_unknown_type(self) -> None:
        """Test getting score for unknown object type returns default."""
        cache = RiskScoreCache()
        assert cache.get_object_type_score("alien") == 50


# =============================================================================
# AIFallbackService Initialization Tests
# =============================================================================


class TestAIFallbackServiceInit:
    """Tests for AIFallbackService initialization."""

    def test_initialization_without_clients(self) -> None:
        """Test initialization without any clients."""
        service = AIFallbackService()

        assert service._detector_client is None
        assert service._nemotron_analyzer is None
        assert service._florence_client is None
        assert service._clip_client is None
        assert service._health_check_interval == 15.0
        assert service._running is False

    def test_initialization_with_all_clients(self, fallback_service) -> None:
        """Test initialization with all clients."""
        assert fallback_service._detector_client is not None
        assert fallback_service._nemotron_analyzer is not None
        assert fallback_service._florence_client is not None
        assert fallback_service._clip_client is not None

    def test_initialization_creates_service_states(self, fallback_service) -> None:
        """Test that initialization creates states for all services."""
        assert len(fallback_service._service_states) == 4
        assert AIService.RTDETR in fallback_service._service_states
        assert AIService.NEMOTRON in fallback_service._service_states
        assert AIService.FLORENCE in fallback_service._service_states
        assert AIService.CLIP in fallback_service._service_states

    def test_initialization_creates_risk_cache(self, fallback_service) -> None:
        """Test that initialization creates risk cache."""
        assert fallback_service._risk_cache is not None
        assert isinstance(fallback_service._risk_cache, RiskScoreCache)

    def test_initialization_creates_empty_circuit_breakers(self, fallback_service) -> None:
        """Test that initialization creates empty circuit breaker dict."""
        assert len(fallback_service._circuit_breakers) == 4
        assert all(v is None for v in fallback_service._circuit_breakers.values())

    def test_custom_health_check_interval(self) -> None:
        """Test custom health check interval."""
        service = AIFallbackService(health_check_interval=30.0)
        assert service._health_check_interval == 30.0


# =============================================================================
# Circuit Breaker Registration Tests
# =============================================================================


class TestCircuitBreakerRegistration:
    """Tests for circuit breaker registration."""

    def test_register_circuit_breaker(self, fallback_service) -> None:
        """Test registering a circuit breaker for a service."""
        cb = CircuitBreaker(name="test", config=DEFAULT_CB_CONFIGS[AIService.RTDETR])
        fallback_service.register_circuit_breaker(AIService.RTDETR, cb)

        assert fallback_service._circuit_breakers[AIService.RTDETR] is cb

    def test_register_multiple_circuit_breakers(self, fallback_service) -> None:
        """Test registering circuit breakers for multiple services."""
        cb_rtdetr = CircuitBreaker(name="rtdetr", config=DEFAULT_CB_CONFIGS[AIService.RTDETR])
        cb_nemotron = CircuitBreaker(name="nemotron", config=DEFAULT_CB_CONFIGS[AIService.NEMOTRON])

        fallback_service.register_circuit_breaker(AIService.RTDETR, cb_rtdetr)
        fallback_service.register_circuit_breaker(AIService.NEMOTRON, cb_nemotron)

        assert fallback_service._circuit_breakers[AIService.RTDETR] is cb_rtdetr
        assert fallback_service._circuit_breakers[AIService.NEMOTRON] is cb_nemotron


# =============================================================================
# Status Callback Tests
# =============================================================================


class TestStatusCallbacks:
    """Tests for status callback registration and notification."""

    @pytest.mark.asyncio
    async def test_register_status_callback(self, fallback_service) -> None:
        """Test registering a status callback."""
        callback = AsyncMock()
        fallback_service.register_status_callback(callback)

        assert callback in fallback_service._status_callbacks

    @pytest.mark.asyncio
    async def test_unregister_status_callback(self, fallback_service) -> None:
        """Test unregistering a status callback."""
        callback = AsyncMock()
        fallback_service.register_status_callback(callback)
        fallback_service.unregister_status_callback(callback)

        assert callback not in fallback_service._status_callbacks

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_callback(self, fallback_service) -> None:
        """Test unregistering a callback that was never registered."""
        callback = AsyncMock()
        # Should not raise
        fallback_service.unregister_status_callback(callback)

    @pytest.mark.asyncio
    async def test_notify_status_change_calls_callbacks(self, fallback_service) -> None:
        """Test that status change notification calls all callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        fallback_service.register_status_callback(callback1)
        fallback_service.register_status_callback(callback2)

        await fallback_service._notify_status_change()

        callback1.assert_called_once()
        callback2.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_status_change_handles_callback_error(self, fallback_service) -> None:
        """Test that callback errors don't break notification."""
        failing_callback = AsyncMock(side_effect=Exception("Callback error"))
        success_callback = AsyncMock()

        fallback_service.register_status_callback(failing_callback)
        fallback_service.register_status_callback(success_callback)

        # Should not raise
        await fallback_service._notify_status_change()

        # Success callback should still be called
        success_callback.assert_called_once()


# =============================================================================
# Lifecycle Management Tests
# =============================================================================


class TestLifecycleManagement:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_service(self, fallback_service) -> None:
        """Test starting the fallback service."""
        await fallback_service.start()

        assert fallback_service._running is True
        assert fallback_service._health_check_task is not None

        await fallback_service.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, fallback_service) -> None:
        """Test starting when already running does nothing."""
        await fallback_service.start()
        task1 = fallback_service._health_check_task

        await fallback_service.start()
        task2 = fallback_service._health_check_task

        assert task1 is task2

        await fallback_service.stop()

    @pytest.mark.asyncio
    async def test_stop_service(self, fallback_service) -> None:
        """Test stopping the fallback service."""
        await fallback_service.start()
        await fallback_service.stop()

        assert fallback_service._running is False
        assert fallback_service._health_check_task is None

    @pytest.mark.asyncio
    async def test_stop_not_running(self, fallback_service) -> None:
        """Test stopping when not running does nothing."""
        # Should not raise
        await fallback_service.stop()

    @pytest.mark.asyncio
    async def test_health_check_loop_runs(self, fallback_service) -> None:
        """Test that health check loop runs periodically."""
        check_count = [0]

        async def mock_check():
            check_count[0] += 1
            return True

        fallback_service._detector_client.health_check = mock_check

        await fallback_service.start()
        await asyncio.sleep(0.15)  # Allow multiple checks
        await fallback_service.stop()

        assert check_count[0] >= 2


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthChecks:
    """Tests for service health checks."""

    @pytest.mark.asyncio
    async def test_check_service_health_with_circuit_breaker(self, fallback_service) -> None:
        """Test health check when circuit breaker is registered."""
        cb = CircuitBreaker(name="test", config=DEFAULT_CB_CONFIGS[AIService.RTDETR])
        fallback_service.register_circuit_breaker(AIService.RTDETR, cb)

        await fallback_service._check_service_health(AIService.RTDETR)

        state = fallback_service._service_states[AIService.RTDETR]
        assert state.status == ServiceStatus.HEALTHY
        assert state.circuit_state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_check_service_health_circuit_open(self, fallback_service) -> None:
        """Test health check when circuit breaker is open."""
        cb = CircuitBreaker(name="test", config=DEFAULT_CB_CONFIGS[AIService.RTDETR])
        # Force circuit open
        for _ in range(5):
            try:
                await cb.call(AsyncMock(side_effect=Exception("Fail")))
            except Exception:  # noqa: S110 - intentionally forcing circuit open
                pass

        fallback_service.register_circuit_breaker(AIService.RTDETR, cb)
        await fallback_service._check_service_health(AIService.RTDETR)

        state = fallback_service._service_states[AIService.RTDETR]
        assert state.status == ServiceStatus.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_check_service_health_without_circuit_breaker_healthy(
        self, fallback_service
    ) -> None:
        """Test health check without circuit breaker when service is healthy."""
        fallback_service._detector_client.health_check = AsyncMock(return_value=True)

        await fallback_service._check_service_health(AIService.RTDETR)

        state = fallback_service._service_states[AIService.RTDETR]
        assert state.status == ServiceStatus.HEALTHY
        assert state.failure_count == 0

    @pytest.mark.asyncio
    async def test_check_service_health_without_circuit_breaker_unhealthy(
        self, fallback_service
    ) -> None:
        """Test health check without circuit breaker when service fails."""
        fallback_service._detector_client.health_check = AsyncMock(return_value=False)

        # First failure - should be degraded
        await fallback_service._check_service_health(AIService.RTDETR)
        state = fallback_service._service_states[AIService.RTDETR]
        assert state.status == ServiceStatus.DEGRADED
        assert state.failure_count == 1

        # Third failure - should be unavailable
        await fallback_service._check_service_health(AIService.RTDETR)
        await fallback_service._check_service_health(AIService.RTDETR)
        state = fallback_service._service_states[AIService.RTDETR]
        assert state.status == ServiceStatus.UNAVAILABLE
        assert state.failure_count == 3

    @pytest.mark.asyncio
    async def test_check_service_health_exception(self, fallback_service) -> None:
        """Test health check when exception is raised."""
        fallback_service._detector_client.health_check = AsyncMock(
            side_effect=Exception("Health check failed")
        )

        await fallback_service._check_service_health(AIService.RTDETR)

        state = fallback_service._service_states[AIService.RTDETR]
        assert state.status == ServiceStatus.UNAVAILABLE
        assert state.failure_count == 1
        assert state.error_message == "Health check failed"

    @pytest.mark.asyncio
    async def test_perform_health_check_rtdetr(self, fallback_service) -> None:
        """Test performing health check for RT-DETRv2."""
        result = await fallback_service._perform_health_check(AIService.RTDETR)
        assert result is True

    @pytest.mark.asyncio
    async def test_perform_health_check_nemotron(self, fallback_service) -> None:
        """Test performing health check for Nemotron."""
        result = await fallback_service._perform_health_check(AIService.NEMOTRON)
        assert result is True

    @pytest.mark.asyncio
    async def test_perform_health_check_florence(self, fallback_service) -> None:
        """Test performing health check for Florence-2."""
        result = await fallback_service._perform_health_check(AIService.FLORENCE)
        assert result is True

    @pytest.mark.asyncio
    async def test_perform_health_check_clip(self, fallback_service) -> None:
        """Test performing health check for CLIP."""
        result = await fallback_service._perform_health_check(AIService.CLIP)
        assert result is True

    @pytest.mark.asyncio
    async def test_perform_health_check_no_client(self) -> None:
        """Test health check without client assumes healthy."""
        service = AIFallbackService()
        result = await service._perform_health_check(AIService.RTDETR)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_all_services(self, fallback_service) -> None:
        """Test checking all services at once."""
        await fallback_service._check_all_services()

        # All services should have been checked
        for service in AIService:
            state = fallback_service._service_states[service]
            assert state.last_check is not None

    @pytest.mark.asyncio
    async def test_check_all_services_triggers_notification(self, fallback_service) -> None:
        """Test that status change triggers notification."""
        callback = AsyncMock()
        fallback_service.register_status_callback(callback)

        # Force a status change
        fallback_service._detector_client.health_check = AsyncMock(return_value=False)

        await fallback_service._check_all_services()
        await fallback_service._check_all_services()
        await fallback_service._check_all_services()

        # Should have been notified
        assert callback.call_count >= 1


# =============================================================================
# Service Availability Tests
# =============================================================================


class TestServiceAvailability:
    """Tests for is_service_available method."""

    def test_is_service_available_healthy(self, fallback_service) -> None:
        """Test availability when service is healthy."""
        fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.HEALTHY
        assert fallback_service.is_service_available(AIService.RTDETR) is True

    def test_is_service_available_degraded(self, fallback_service) -> None:
        """Test availability when service is degraded."""
        fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.DEGRADED
        assert fallback_service.is_service_available(AIService.RTDETR) is True

    def test_is_service_available_unavailable(self, fallback_service) -> None:
        """Test availability when service is unavailable."""
        fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE
        assert fallback_service.is_service_available(AIService.RTDETR) is False

    def test_is_service_available_string_parameter(self, fallback_service) -> None:
        """Test availability with string parameter."""
        fallback_service._service_states[AIService.NEMOTRON].status = ServiceStatus.HEALTHY
        assert fallback_service.is_service_available("nemotron") is True


# =============================================================================
# Service State Tests
# =============================================================================


class TestGetServiceState:
    """Tests for get_service_state method."""

    def test_get_service_state_enum(self, fallback_service) -> None:
        """Test getting service state with enum."""
        state = fallback_service.get_service_state(AIService.FLORENCE)
        assert state.service == AIService.FLORENCE

    def test_get_service_state_string(self, fallback_service) -> None:
        """Test getting service state with string."""
        state = fallback_service.get_service_state("clip")
        assert state.service == AIService.CLIP


# =============================================================================
# Degradation Level Tests
# =============================================================================


class TestDegradationLevel:
    """Tests for degradation level calculation."""

    def test_degradation_level_all_healthy(self, fallback_service) -> None:
        """Test degradation level when all services are healthy."""
        level = fallback_service.get_degradation_level()
        assert level == DegradationLevel.NORMAL

    def test_degradation_level_non_critical_down(self, fallback_service) -> None:
        """Test degradation level when non-critical service is down."""
        fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE
        level = fallback_service.get_degradation_level()
        assert level == DegradationLevel.DEGRADED

    def test_degradation_level_one_critical_down(self, fallback_service) -> None:
        """Test degradation level when one critical service is down."""
        fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE
        level = fallback_service.get_degradation_level()
        assert level == DegradationLevel.MINIMAL

    def test_degradation_level_all_critical_down(self, fallback_service) -> None:
        """Test degradation level when all critical services are down."""
        fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE
        fallback_service._service_states[AIService.NEMOTRON].status = ServiceStatus.UNAVAILABLE
        level = fallback_service.get_degradation_level()
        assert level == DegradationLevel.OFFLINE

    def test_critical_services_constant(self) -> None:
        """Test that CRITICAL_SERVICES contains expected services."""
        assert AIService.RTDETR in CRITICAL_SERVICES
        assert AIService.NEMOTRON in CRITICAL_SERVICES
        assert len(CRITICAL_SERVICES) == 2


# =============================================================================
# Available Features Tests
# =============================================================================


class TestAvailableFeatures:
    """Tests for get_available_features method."""

    def test_get_available_features_all_healthy(self, fallback_service) -> None:
        """Test available features when all services are healthy."""
        features = fallback_service.get_available_features()

        assert "object_detection" in features
        assert "detection_alerts" in features
        assert "risk_analysis" in features
        assert "llm_reasoning" in features
        assert "image_captioning" in features
        assert "ocr" in features
        assert "entity_tracking" in features
        assert "re_identification" in features
        assert "event_history" in features
        assert "camera_feeds" in features
        assert "system_monitoring" in features

    def test_get_available_features_rtdetr_down(self, fallback_service) -> None:
        """Test available features when RT-DETRv2 is down."""
        fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE
        features = fallback_service.get_available_features()

        assert "object_detection" not in features
        assert "detection_alerts" not in features
        assert "event_history" in features  # Basic features always available

    def test_get_available_features_nemotron_down(self, fallback_service) -> None:
        """Test available features when Nemotron is down."""
        fallback_service._service_states[AIService.NEMOTRON].status = ServiceStatus.UNAVAILABLE
        features = fallback_service.get_available_features()

        assert "risk_analysis" not in features
        assert "llm_reasoning" not in features

    def test_get_available_features_florence_down(self, fallback_service) -> None:
        """Test available features when Florence-2 is down."""
        fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE
        features = fallback_service.get_available_features()

        assert "image_captioning" not in features
        assert "ocr" not in features

    def test_get_available_features_clip_down(self, fallback_service) -> None:
        """Test available features when CLIP is down."""
        fallback_service._service_states[AIService.CLIP].status = ServiceStatus.UNAVAILABLE
        features = fallback_service.get_available_features()

        assert "entity_tracking" not in features
        assert "re_identification" not in features


# =============================================================================
# Degradation Status Tests
# =============================================================================


class TestDegradationStatus:
    """Tests for get_degradation_status method."""

    def test_get_degradation_status_structure(self, fallback_service) -> None:
        """Test that degradation status has expected structure."""
        status = fallback_service.get_degradation_status()

        assert "timestamp" in status
        assert "degradation_mode" in status
        assert "services" in status
        assert "available_features" in status

    def test_get_degradation_status_normal_mode(self, fallback_service) -> None:
        """Test degradation status in normal mode."""
        status = fallback_service.get_degradation_status()

        assert status["degradation_mode"] == "normal"
        assert len(status["services"]) == 4

    def test_get_degradation_status_service_details(self, fallback_service) -> None:
        """Test that service details are included in status."""
        status = fallback_service.get_degradation_status()

        assert "rtdetr" in status["services"]
        assert "nemotron" in status["services"]
        assert "florence" in status["services"]
        assert "clip" in status["services"]


# =============================================================================
# Fallback Methods Tests
# =============================================================================


class TestGetFallbackRiskAnalysisMethod:
    """Tests for get_fallback_risk_analysis method."""

    def test_fallback_risk_analysis_with_cache(self, fallback_service) -> None:
        """Test fallback risk analysis uses cached value."""
        fallback_service.cache_risk_score("front_door", 85)

        result = fallback_service.get_fallback_risk_analysis(camera_name="front_door")

        assert result.risk_score == 85
        assert result.source == "cache"
        assert result.is_fallback is True
        assert "cached" in result.reasoning.lower()

    def test_fallback_risk_analysis_with_object_types(self, fallback_service) -> None:
        """Test fallback risk analysis with object types."""
        result = fallback_service.get_fallback_risk_analysis(object_types=["person", "vehicle"])

        # Average of person (60) and vehicle (50) = 55
        assert result.risk_score == 55
        assert result.source == "object_type_estimate"
        assert "person" in result.reasoning
        assert "vehicle" in result.reasoning

    def test_fallback_risk_analysis_single_object(self, fallback_service) -> None:
        """Test fallback risk analysis with single object type."""
        result = fallback_service.get_fallback_risk_analysis(object_types=["dog"])

        assert result.risk_score == 25  # Dog score
        assert result.source == "object_type_estimate"

    def test_fallback_risk_analysis_default(self, fallback_service) -> None:
        """Test fallback risk analysis with no information."""
        result = fallback_service.get_fallback_risk_analysis()

        assert result.risk_score == 50
        assert result.source == "default"
        assert "default medium risk" in result.reasoning.lower()

    def test_fallback_risk_analysis_cache_priority(self, fallback_service) -> None:
        """Test that cache takes priority over object types."""
        fallback_service.cache_risk_score("back_door", 90)

        result = fallback_service.get_fallback_risk_analysis(
            camera_name="back_door", object_types=["person"]
        )

        assert result.risk_score == 90
        assert result.source == "cache"


class TestCacheRiskScore:
    """Tests for cache_risk_score method."""

    def test_cache_risk_score(self, fallback_service) -> None:
        """Test caching a risk score."""
        fallback_service.cache_risk_score("test_camera", 75)

        cached = fallback_service._risk_cache.get_cached_score("test_camera")
        assert cached == 75


class TestFallbackCaption:
    """Tests for get_fallback_caption method."""

    def test_fallback_caption_with_objects_and_camera(self, fallback_service) -> None:
        """Test fallback caption with objects and camera name."""
        caption = fallback_service.get_fallback_caption(
            object_types=["person", "vehicle"], camera_name="front_door"
        )

        assert "person" in caption.lower() or "vehicle" in caption.lower()
        assert "front_door" in caption

    def test_fallback_caption_with_objects_only(self, fallback_service) -> None:
        """Test fallback caption with objects but no camera."""
        caption = fallback_service.get_fallback_caption(object_types=["dog", "cat"])

        assert "dog" in caption.lower() or "cat" in caption.lower()

    def test_fallback_caption_with_camera_only(self, fallback_service) -> None:
        """Test fallback caption with camera but no objects."""
        caption = fallback_service.get_fallback_caption(camera_name="back_door")

        assert "back_door" in caption
        assert "activity detected" in caption.lower()

    def test_fallback_caption_no_info(self, fallback_service) -> None:
        """Test fallback caption with no information."""
        caption = fallback_service.get_fallback_caption()

        assert caption == "Activity detected"


class TestFallbackEmbedding:
    """Tests for get_fallback_embedding method."""

    def test_fallback_embedding_returns_zero_vector(self, fallback_service) -> None:
        """Test that fallback embedding returns zero vector."""
        embedding = fallback_service.get_fallback_embedding()

        assert len(embedding) == 768
        assert all(v == 0.0 for v in embedding)


class TestShouldSkipMethods:
    """Tests for should_skip_* convenience methods."""

    def test_should_skip_detection(self, fallback_service) -> None:
        """Test should_skip_detection method."""
        fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE
        assert fallback_service.should_skip_detection() is True

        fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.HEALTHY
        assert fallback_service.should_skip_detection() is False

    def test_should_use_default_risk(self, fallback_service) -> None:
        """Test should_use_default_risk method."""
        fallback_service._service_states[AIService.NEMOTRON].status = ServiceStatus.UNAVAILABLE
        assert fallback_service.should_use_default_risk() is True

        fallback_service._service_states[AIService.NEMOTRON].status = ServiceStatus.HEALTHY
        assert fallback_service.should_use_default_risk() is False

    def test_should_skip_captions(self, fallback_service) -> None:
        """Test should_skip_captions method."""
        fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE
        assert fallback_service.should_skip_captions() is True

        fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.HEALTHY
        assert fallback_service.should_skip_captions() is False

    def test_should_skip_reid(self, fallback_service) -> None:
        """Test should_skip_reid method."""
        fallback_service._service_states[AIService.CLIP].status = ServiceStatus.UNAVAILABLE
        assert fallback_service.should_skip_reid() is True

        fallback_service._service_states[AIService.CLIP].status = ServiceStatus.HEALTHY
        assert fallback_service.should_skip_reid() is False


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalInstance:
    """Tests for global instance management."""

    def test_get_ai_fallback_service_creates_singleton(self) -> None:
        """Test that get_ai_fallback_service returns singleton."""
        service1 = get_ai_fallback_service()
        service2 = get_ai_fallback_service()

        assert service1 is service2

    def test_reset_ai_fallback_service(self) -> None:
        """Test resetting the global service."""
        service1 = get_ai_fallback_service()
        reset_ai_fallback_service()
        service2 = get_ai_fallback_service()

        assert service1 is not service2

    def test_global_service_initialization(self) -> None:
        """Test that global service is properly initialized."""
        service = get_ai_fallback_service()

        assert isinstance(service, AIFallbackService)
        assert len(service._service_states) == 4


# =============================================================================
# Default Config Tests
# =============================================================================


class TestDefaultConfigs:
    """Tests for DEFAULT_CB_CONFIGS constant."""

    def test_default_cb_configs_has_all_services(self) -> None:
        """Test that DEFAULT_CB_CONFIGS has configs for all services."""
        assert AIService.RTDETR in DEFAULT_CB_CONFIGS
        assert AIService.NEMOTRON in DEFAULT_CB_CONFIGS
        assert AIService.FLORENCE in DEFAULT_CB_CONFIGS
        assert AIService.CLIP in DEFAULT_CB_CONFIGS

    def test_rtdetr_config(self) -> None:
        """Test RT-DETRv2 circuit breaker config."""
        config = DEFAULT_CB_CONFIGS[AIService.RTDETR]
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 60.0

    def test_nemotron_config(self) -> None:
        """Test Nemotron circuit breaker config."""
        config = DEFAULT_CB_CONFIGS[AIService.NEMOTRON]
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 90.0
