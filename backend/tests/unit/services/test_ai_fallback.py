"""Unit tests for AI fallback service.

R8 S3 (owner rulings 1 + 5, 2026-09-29) retired the two non-survivor arms of
this module -- the captioning provider and the embedding/re-ID provider -- so
their enum members, breaker configs and health arms are gone from
``backend/services/ai_fallback.py``. The module itself is kept-and-DEAD (zero
shipped importers) and its final deletion belongs to a later dead-code slice,
so the SURVIVOR's properties stay pinned here with their teeth intact: the
detector health arm, degradation levels, the risk-score cache, fallback risk
analysis, status callbacks, breaker registration, ``should_skip_detection``,
availability queries, ``get_available_features``, ``ServiceState.to_dict`` and
the start/stop lifecycle. The retirement history itself is pinned by
``backend/tests/unit/test_r8_s3_florence_provider_retirement.py`` -- nothing
here re-litigates it.

Tests cover:
- AIService, DegradationLevel, ServiceStatus enum values
- ServiceState dataclass and to_dict() serialization
- FallbackRiskAnalysis dataclass and to_dict() serialization
- RiskScoreCache caching behavior and TTL expiration
- AIFallbackService initialization and configuration
- Circuit breaker registration
- Status callback registration and notification
- Health check loop lifecycle (start/stop)
- Detector health checks and the no-client healthy default
- Service availability checks
- Degradation level calculation based on service states
- Available features based on service health
- Fallback methods (risk analysis, detector-derived caption, zero vector)
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

# The service census, DERIVED from the module rather than hand-numbered: S3
# left exactly one member, and every count below is restated from this set so
# a future slice that re-adds (or deletes) an arm moves these pins with the
# module instead of silently holding a stale number.
SHIPPED_SERVICES: set[AIService] = set(AIService)

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
    """Create a mock YOLO26 detector client."""
    client = MagicMock()
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_analyzer():
    """Create a mock VLM analyzer (the shipped analyzer side of the ctor)."""
    return MagicMock()


@pytest.fixture
def fallback_service(mock_detector_client, mock_analyzer):
    """Create an AIFallbackService on the shipped constructor surface."""
    return AIFallbackService(
        detector_client=mock_detector_client,
        analyzer=mock_analyzer,
        health_check_interval=0.05,  # Fast for testing
    )


# =============================================================================
# Enum Tests
# =============================================================================


class TestAIServiceEnum:
    """Tests for AIService enum."""

    def test_service_enum_values(self) -> None:
        """Test that AIService enum has expected values.

        Every member's value is a lowercase wire slug (the string form
        ``is_service_available()`` and ``get_degradation_status()`` expose);
        the pin is looped over the module's own members so a newly added arm
        cannot arrive with a mis-cased value. Non-vacuity: the loop is proven
        to have run.
        """
        assert AIService.YOLO26.value == "yolo26"
        members = list(AIService)
        assert members, "AIService enumerated no members -- the slug pin below is vacuous"
        for member in members:
            assert member.value == member.value.lower()
            assert member.value
            assert member.name == member.name.upper()

    def test_service_enum_count(self) -> None:
        """Test that AIService has exactly the surviving services.

        This was written as a three-member census. R8 S3's rulings 1 and 5
        retired the other two arms' providers, so the count dropped to the
        detector alone -- the census IS the point of the test, so the expected
        set is literal here (deriving it from the enum would compare the module
        to itself) and it stays an equality pin, not a membership pin.
        """
        assert {s.value for s in AIService} == {"yolo26"}


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
        state = ServiceState(service=AIService.YOLO26)
        assert state.service == AIService.YOLO26
        assert state.status == ServiceStatus.HEALTHY
        assert state.circuit_state == CircuitState.CLOSED
        assert state.last_success is None
        assert state.failure_count == 0
        assert state.error_message is None
        assert state.last_check is None

    def test_custom_initialization(self) -> None:
        """Test ServiceState with custom values.

        Carried on the survivor member: which service the record keys on is
        incidental to what this dataclass is FOR -- holding a non-default
        status, circuit state, timestamps, failure count and error message.
        """
        now = datetime.now(UTC)
        state = ServiceState(
            service=AIService.YOLO26,
            status=ServiceStatus.DEGRADED,
            circuit_state=CircuitState.HALF_OPEN,
            last_success=now,
            failure_count=2,
            error_message="Timeout error",
            last_check=now,
        )
        assert state.service == AIService.YOLO26
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
            service=AIService.YOLO26,
            status=ServiceStatus.UNAVAILABLE,
            last_success=now,
            failure_count=5,
            last_check=now,
        )
        result = state.to_dict()

        assert set(result) == {
            "service",
            "status",
            "circuit_state",
            "last_success",
            "failure_count",
            "error_message",
            "last_check",
        }
        assert result["service"] == "yolo26"
        assert result["status"] == "unavailable"
        assert result["circuit_state"] == "closed"
        assert result["last_success"] == now.isoformat()
        assert result["failure_count"] == 5
        assert result["error_message"] is None
        assert result["last_check"] == now.isoformat()

    def test_to_dict_without_timestamps(self) -> None:
        """Test to_dict() serialization without timestamps."""
        state = ServiceState(
            service=AIService.YOLO26,
            status=ServiceStatus.HEALTHY,
        )
        result = state.to_dict()

        assert result["service"] == "yolo26"
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
        assert service._analyzer is None
        assert service._health_check_interval == 15.0
        assert service._running is False

    def test_initialization_with_all_clients(self, fallback_service) -> None:
        """Test initialization with every client the shipped ctor accepts."""
        assert fallback_service._detector_client is not None
        assert fallback_service._analyzer is not None

    def test_initialization_creates_service_states(self, fallback_service) -> None:
        """Test that initialization creates states for all services."""
        assert SHIPPED_SERVICES, "AIService is empty -- the state census below is vacuous"
        assert set(fallback_service._service_states) == SHIPPED_SERVICES
        assert fallback_service._service_states[AIService.YOLO26].service is AIService.YOLO26

    def test_initialization_creates_risk_cache(self, fallback_service) -> None:
        """Test that initialization creates risk cache."""
        assert fallback_service._risk_cache is not None
        assert isinstance(fallback_service._risk_cache, RiskScoreCache)

    def test_initialization_creates_empty_circuit_breakers(self, fallback_service) -> None:
        """Test that initialization creates empty circuit breaker dict.

        One slot per enumerated service, each unwired -- the count is derived
        from the module, and the non-empty guard is what keeps "all values are
        None" from passing on an empty dict.
        """
        assert SHIPPED_SERVICES, "AIService is empty -- the breaker-slot census is vacuous"
        assert set(fallback_service._circuit_breakers) == SHIPPED_SERVICES
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
        cb = CircuitBreaker(name="test", config=DEFAULT_CB_CONFIGS[AIService.YOLO26])
        fallback_service.register_circuit_breaker(AIService.YOLO26, cb)

        assert fallback_service._circuit_breakers[AIService.YOLO26] is cb

    def test_register_multiple_circuit_breakers(self, fallback_service) -> None:
        """Test registering circuit breakers for every enumerated service.

        Written when the census held three services, so this proved two
        breakers coexisted under distinct keys. With the shipped census the
        loop runs once -- what still has teeth here is (a) every service that
        has a breaker config can be registered and is stored under its own
        key, and (b) re-registering replaces only that key's entry.
        """
        services = set(DEFAULT_CB_CONFIGS)
        assert services, "DEFAULT_CB_CONFIGS is empty -- the registration loop is vacuous"

        breakers = {
            service: CircuitBreaker(name=service.value, config=config)
            for service, config in DEFAULT_CB_CONFIGS.items()
        }
        for service, cb in breakers.items():
            fallback_service.register_circuit_breaker(service, cb)

        for service, cb in breakers.items():
            assert fallback_service._circuit_breakers[service] is cb

        replacement = CircuitBreaker(
            name="replacement", config=DEFAULT_CB_CONFIGS[AIService.YOLO26]
        )
        fallback_service.register_circuit_breaker(AIService.YOLO26, replacement)
        assert fallback_service._circuit_breakers[AIService.YOLO26] is replacement
        assert breakers[AIService.YOLO26] is not replacement


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

    @pytest.mark.asyncio
    async def test_notify_status_change_broadcasts_the_status_payload(
        self, fallback_service
    ) -> None:
        """The callback receives the degradation-status dict, not a bare flag."""
        callback = AsyncMock()
        fallback_service.register_status_callback(callback)

        await fallback_service._notify_status_change()

        callback.assert_called_once()
        (payload,) = callback.call_args.args
        assert payload["degradation_mode"] == DegradationLevel.NORMAL.value
        assert payload["services"], "the broadcast carried no per-service state"
        assert payload["services"]["yolo26"]["status"] == ServiceStatus.HEALTHY.value


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
        two_checks_done = asyncio.Event()

        async def mock_check():
            check_count[0] += 1
            if check_count[0] >= 2:
                two_checks_done.set()
            return True

        fallback_service._detector_client.health_check = mock_check

        await fallback_service.start()
        try:
            # 0.05s interval -> two rounds in well under a second; the bound is
            # kept inside the 5s per-test tier timeout rather than at it.
            await asyncio.wait_for(two_checks_done.wait(), timeout=2.0)
        finally:
            await fallback_service.stop()

        assert check_count[0] >= 2


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthChecks:
    """Tests for the detector health arm.

    S3 left exactly one service whose backend still boots, so every case here
    keys on the survivor; the module's no-circuit-breaker path (the counting
    arm) is pinned in full.
    """

    @pytest.mark.asyncio
    async def test_check_service_health_with_circuit_breaker(self, fallback_service) -> None:
        """Test health check when circuit breaker is registered."""
        cb = CircuitBreaker(name="test", config=DEFAULT_CB_CONFIGS[AIService.YOLO26])
        fallback_service.register_circuit_breaker(AIService.YOLO26, cb)

        await fallback_service._check_service_health(AIService.YOLO26)

        state = fallback_service._service_states[AIService.YOLO26]
        assert state.status == ServiceStatus.HEALTHY
        assert state.circuit_state == CircuitState.CLOSED
        # The breaker arm wins over the client arm: no health_check() call.
        fallback_service._detector_client.health_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_service_health_circuit_open(self, fallback_service) -> None:
        """Test health check when circuit breaker is open."""
        cb = CircuitBreaker(name="test", config=DEFAULT_CB_CONFIGS[AIService.YOLO26])
        # Force circuit open
        for _ in range(5):
            try:
                await cb.call(AsyncMock(side_effect=Exception("Fail")))
            except Exception:
                pass

        fallback_service.register_circuit_breaker(AIService.YOLO26, cb)
        await fallback_service._check_service_health(AIService.YOLO26)

        state = fallback_service._service_states[AIService.YOLO26]
        assert state.status == ServiceStatus.UNAVAILABLE
        assert state.circuit_state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_check_service_health_without_circuit_breaker_healthy(
        self, fallback_service
    ) -> None:
        """Test health check without circuit breaker when service is healthy."""
        fallback_service._detector_client.health_check = AsyncMock(return_value=True)

        await fallback_service._check_service_health(AIService.YOLO26)

        state = fallback_service._service_states[AIService.YOLO26]
        assert state.status == ServiceStatus.HEALTHY
        assert state.failure_count == 0
        assert state.last_check is not None

    @pytest.mark.asyncio
    async def test_check_service_health_without_circuit_breaker_unhealthy(
        self, fallback_service
    ) -> None:
        """Test health check without circuit breaker when service fails."""
        fallback_service._detector_client.health_check = AsyncMock(return_value=False)

        # First failure - should be degraded
        await fallback_service._check_service_health(AIService.YOLO26)
        state = fallback_service._service_states[AIService.YOLO26]
        assert state.status == ServiceStatus.DEGRADED
        assert state.failure_count == 1

        # Third failure - should be unavailable
        await fallback_service._check_service_health(AIService.YOLO26)
        await fallback_service._check_service_health(AIService.YOLO26)
        state = fallback_service._service_states[AIService.YOLO26]
        assert state.status == ServiceStatus.UNAVAILABLE
        assert state.failure_count == 3

    @pytest.mark.asyncio
    async def test_check_service_health_recovers_after_healthy_check(
        self, fallback_service
    ) -> None:
        """A healthy check clears the counting arm's failure bookkeeping."""
        fallback_service._detector_client.health_check = AsyncMock(return_value=False)
        await fallback_service._check_service_health(AIService.YOLO26)
        assert fallback_service._service_states[AIService.YOLO26].failure_count == 1

        fallback_service._detector_client.health_check = AsyncMock(return_value=True)
        await fallback_service._check_service_health(AIService.YOLO26)

        state = fallback_service._service_states[AIService.YOLO26]
        assert state.status == ServiceStatus.HEALTHY
        assert state.failure_count == 0
        assert state.last_success is not None
        assert state.error_message is None

    @pytest.mark.asyncio
    async def test_check_service_health_exception(self, fallback_service) -> None:
        """Test health check when exception is raised."""
        fallback_service._detector_client.health_check = AsyncMock(
            side_effect=Exception("Health check failed")
        )

        await fallback_service._check_service_health(AIService.YOLO26)

        state = fallback_service._service_states[AIService.YOLO26]
        assert state.status == ServiceStatus.UNAVAILABLE
        assert state.failure_count == 1
        assert state.error_message == "Health check failed"

    @pytest.mark.asyncio
    async def test_perform_health_check_yolo26(self, fallback_service) -> None:
        """Test performing health check for YOLO26."""
        result = await fallback_service._perform_health_check(AIService.YOLO26)
        assert result is True
        fallback_service._detector_client.health_check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_perform_health_check_no_client(self) -> None:
        """Test health check without client assumes healthy."""
        service = AIFallbackService()
        result = await service._perform_health_check(AIService.YOLO26)
        assert result is True

    @pytest.mark.asyncio
    async def test_perform_health_check_routes_every_enumerated_service(self) -> None:
        """The survivor arm is the only one: every enumerated service routes to
        the detector client when one is wired. Derived from the census, so an
        added service cannot be silently left unrouted; the guard proves the
        loop has something to iterate."""
        assert SHIPPED_SERVICES, "AIService is empty -- the routing loop would be vacuous"
        service = AIFallbackService(detector_client=MagicMock())
        service._detector_client.health_check = AsyncMock(return_value=True)

        for member in SHIPPED_SERVICES:
            assert await service._perform_health_check(member) is True
        service._detector_client.health_check.assert_awaited()

    @pytest.mark.asyncio
    async def test_check_all_services(self, fallback_service) -> None:
        """Test checking all services at once."""
        await fallback_service._check_all_services()

        # All services should have been checked
        assert SHIPPED_SERVICES, "AIService is empty -- the last_check sweep is vacuous"
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

    @pytest.mark.asyncio
    async def test_check_all_services_stable_state_does_not_notify(self, fallback_service) -> None:
        """An unchanged status must not spam the WebSocket broadcasters."""
        callback = AsyncMock()
        fallback_service.register_status_callback(callback)

        await fallback_service._check_all_services()

        callback.assert_not_called()


# =============================================================================
# Service Availability Tests
# =============================================================================


class TestServiceAvailability:
    """Tests for is_service_available method."""

    def test_is_service_available_healthy(self, fallback_service) -> None:
        """Test availability when service is healthy."""
        fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.HEALTHY
        assert fallback_service.is_service_available(AIService.YOLO26) is True

    def test_is_service_available_degraded(self, fallback_service) -> None:
        """Test availability when service is degraded."""
        fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.DEGRADED
        assert fallback_service.is_service_available(AIService.YOLO26) is True

    def test_is_service_available_unavailable(self, fallback_service) -> None:
        """Test availability when service is unavailable."""
        fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.UNAVAILABLE
        assert fallback_service.is_service_available(AIService.YOLO26) is False

    def test_is_service_available_string_parameter(self, fallback_service) -> None:
        """Test availability with string parameter."""
        fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.HEALTHY
        assert fallback_service.is_service_available("yolo26") is True

    def test_is_service_available_rejects_an_unknown_slug(self, fallback_service) -> None:
        """The string form is coerced through the enum, so a slug the shipped
        census does not own raises rather than reporting availability."""
        with pytest.raises(ValueError, match="not-a-shipped-service"):
            fallback_service.is_service_available("not-a-shipped-service")


# =============================================================================
# Service State Tests
# =============================================================================


class TestGetServiceState:
    """Tests for get_service_state method."""

    def test_get_service_state_enum(self, fallback_service) -> None:
        """Test getting service state with enum."""
        state = fallback_service.get_service_state(AIService.YOLO26)
        assert state.service == AIService.YOLO26

    def test_get_service_state_string(self, fallback_service) -> None:
        """Test getting service state with string."""
        state = fallback_service.get_service_state("yolo26")
        assert state.service == AIService.YOLO26

    def test_get_service_state_returns_the_live_object(self, fallback_service) -> None:
        """The accessor hands back the stored state, not a copy -- callers
        mutate through it (the degradation tests in this file depend on it)."""
        state = fallback_service.get_service_state(AIService.YOLO26)
        state.status = ServiceStatus.UNAVAILABLE

        assert fallback_service._service_states[AIService.YOLO26] is state
        assert fallback_service.is_service_available(AIService.YOLO26) is False


# =============================================================================
# Degradation Level Tests
# =============================================================================


class TestDegradationLevel:
    """Tests for degradation level calculation."""

    def test_degradation_level_all_healthy(self, fallback_service) -> None:
        """Test degradation level when all services are healthy."""
        level = fallback_service.get_degradation_level()
        assert level == DegradationLevel.NORMAL

    def test_degradation_level_all_critical_down(self, fallback_service) -> None:
        """Test degradation level when all critical services are down.

        Census-driven rather than hard-numbered: every critical service is
        taken down, and the loop is proven to have run.
        """
        assert CRITICAL_SERVICES, "CRITICAL_SERVICES is empty -- taking them all down is vacuous"
        for service in CRITICAL_SERVICES:
            fallback_service._service_states[service].status = ServiceStatus.UNAVAILABLE

        level = fallback_service.get_degradation_level()
        assert level == DegradationLevel.OFFLINE

    def test_partial_critical_outage_takes_the_system_offline(self, fallback_service) -> None:
        """An outage of any single critical service is an outage of the critical
        tier: with the shipped census the critical set has one member, so a
        one-service outage IS the full critical outage. Loop guard proves the
        census is not empty."""
        assert CRITICAL_SERVICES, "CRITICAL_SERVICES is empty -- the per-service loop is vacuous"
        for service in CRITICAL_SERVICES:
            # Fresh service per iteration would be the same object here; reset
            # the whole board first so each round is a one-outage scenario.
            for other in fallback_service._service_states:
                fallback_service._service_states[other].status = ServiceStatus.HEALTHY
            fallback_service._service_states[service].status = ServiceStatus.UNAVAILABLE
            assert fallback_service.get_degradation_level() == DegradationLevel.OFFLINE

    def test_critical_services_constant(self) -> None:
        """Test that CRITICAL_SERVICES contains expected services."""
        assert AIService.YOLO26 in CRITICAL_SERVICES
        # R8 S2b: the analyzer's membership left with its enum member; R8 S3
        # rulings 1 + 5 took the two arms that were NOT critical with theirs.
        # What is left is a singleton census -- which is why 'one critical
        # down' and 'all critical down' are the same scenario, and why the
        # level below is pinned as structurally unreachable rather than driven.
        assert {AIService.YOLO26} == CRITICAL_SERVICES

    def test_no_non_critical_service_remains_so_degraded_is_unreachable(
        self, fallback_service
    ) -> None:
        """Restates, on the shipped surface, the property the old 'non-critical
        service is down -> DEGRADED' case drove.

        That case needed a non-critical service to knock over and S3 left none,
        so the DEGRADED and MINIMAL arms of get_degradation_level() cannot be
        reached by state any more -- they are pinned here structurally: the
        critical set covers the whole census, and the two levels that keyed on
        a partial outage stay reachable only as enum values (pinned in
        TestDegradationLevelEnum). A slice that adds a non-critical service has
        to bring the behavioural case back with it.
        """
        assert SHIPPED_SERVICES, "AIService is empty -- the coverage pin below is vacuous"
        assert set(CRITICAL_SERVICES) == SHIPPED_SERVICES
        non_critical = SHIPPED_SERVICES - set(CRITICAL_SERVICES)
        assert non_critical == set()
        assert DegradationLevel.DEGRADED.value == "degraded"
        assert DegradationLevel.MINIMAL.value == "minimal"


# =============================================================================
# Available Features Tests
# =============================================================================


class TestAvailableFeatures:
    """Tests for get_available_features method."""

    def test_get_available_features_all_healthy(self, fallback_service) -> None:
        """Test available features when the detector is up.

        Pinned as an exact set, not a membership list: S3 retired the arms that
        once contributed here, so the shipped surface emits exactly the
        detection pair plus the always-on trio, and a resurrected arm would
        have to be added to this pin on purpose.
        """
        features = fallback_service.get_available_features()

        assert set(features) == {
            "object_detection",
            "detection_alerts",
            "event_history",
            "camera_feeds",
            "system_monitoring",
        }
        assert len(features) == len(set(features)), "a feature is emitted twice"

    def test_get_available_features_yolo26_down(self, fallback_service) -> None:
        """Test available features when YOLO26 is down."""
        fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.UNAVAILABLE
        features = fallback_service.get_available_features()

        assert "object_detection" not in features
        assert "detection_alerts" not in features
        # Basic features always available -- and the container is proven
        # non-empty, so the two absences above are not an empty-list artifact.
        assert set(features) == {"event_history", "camera_feeds", "system_monitoring"}

    def test_always_on_features_survive_both_states(self, fallback_service) -> None:
        """The always-on trio is exactly the intersection of the healthy and
        detector-down feature lists."""
        healthy = set(fallback_service.get_available_features())
        fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.UNAVAILABLE
        down = set(fallback_service.get_available_features())

        assert healthy > down
        assert healthy - down == {"object_detection", "detection_alerts"}


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
        assert SHIPPED_SERVICES, "AIService is empty -- the service-count pin would be vacuous"
        assert len(status["services"]) == len(SHIPPED_SERVICES)
        assert status["available_features"], "normal mode reported no features"

    def test_get_degradation_status_service_details(self, fallback_service) -> None:
        """Test that service details are included in status.

        The keys are pinned against the enum's own wire spellings rather than a
        hand-written list, so the report and the census cannot drift apart.
        """
        status = fallback_service.get_degradation_status()

        assert SHIPPED_SERVICES, "AIService is empty -- the key pin below is vacuous"
        assert set(status["services"]) == {s.value for s in SHIPPED_SERVICES}
        assert "yolo26" in status["services"]
        assert status["services"]["yolo26"]["status"] == ServiceStatus.HEALTHY.value


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

    def test_fallback_risk_analysis_expired_cache_falls_through(self, fallback_service) -> None:
        """A stale cached score is not served: the estimator arm answers."""
        fallback_service._risk_cache.ttl_seconds = 0
        fallback_service.cache_risk_score("attic", 99)

        result = fallback_service.get_fallback_risk_analysis(
            camera_name="attic", object_types=["person"]
        )

        assert result.risk_score == 60
        assert result.source == "object_type_estimate"


class TestCacheRiskScore:
    """Tests for cache_risk_score method."""

    def test_cache_risk_score(self, fallback_service) -> None:
        """Test caching a risk score."""
        fallback_service.cache_risk_score("test_camera", 75)

        cached = fallback_service._risk_cache.get_cached_score("test_camera")
        assert cached == 75


class TestFallbackCaption:
    """Tests for get_fallback_caption method.

    Since S3 this is the shipped caption path -- it is built from detector
    outputs, so all four shapes stay with their exact-string teeth.
    """

    def test_fallback_caption_with_objects_and_camera(self, fallback_service) -> None:
        """Test fallback caption with objects and camera name."""
        caption = fallback_service.get_fallback_caption(
            object_types=["person", "vehicle"], camera_name="front_door"
        )

        assert caption == "Person, vehicle detected at front_door"

    def test_fallback_caption_with_objects_only(self, fallback_service) -> None:
        """Test fallback caption with objects but no camera."""
        caption = fallback_service.get_fallback_caption(object_types=["dog", "cat"])

        assert caption == "Dog, cat detected"

    def test_fallback_caption_with_camera_only(self, fallback_service) -> None:
        """Test fallback caption with camera but no objects."""
        caption = fallback_service.get_fallback_caption(camera_name="back_door")

        assert caption == "Activity detected at back_door"

    def test_fallback_caption_no_info(self, fallback_service) -> None:
        """Test fallback caption with no information."""
        caption = fallback_service.get_fallback_caption()

        assert caption == "Activity detected"


class TestFallbackEmbedding:
    """Tests for get_fallback_embedding method."""

    def test_fallback_embedding_returns_zero_vector(self, fallback_service) -> None:
        """Test that fallback embedding returns zero vector.

        512 dims -- the OSNet-AIN x1.0 space the full swap (ledger item 20)
        made the only person-vector space; a stub in any other space could
        never be compared against anything the store holds. The dimension is
        pinned against the vector's own length so a shape change here reads as
        the store-wide migration it would be, not a one-line edit.
        """
        embedding = fallback_service.get_fallback_embedding()

        assert embedding, "the fallback vector is empty -- the checks below are vacuous"
        assert len(embedding) == 512
        assert all(v == 0.0 for v in embedding)
        assert all(isinstance(v, float) for v in embedding)


class TestShouldSkipDetection:
    """Tests for the should_skip_detection convenience method.

    S3 deleted the sibling skip helpers with the enum members they keyed on;
    this one keys on the survivor and stays.
    """

    def test_should_skip_detection(self, fallback_service) -> None:
        """Test should_skip_detection method."""
        fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.UNAVAILABLE
        assert fallback_service.should_skip_detection() is True

        fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.HEALTHY
        assert fallback_service.should_skip_detection() is False

    def test_should_skip_detection_matches_availability(self, fallback_service) -> None:
        """The skip flag is the detector arm's availability, inverted -- pinned
        across every status the arm can hold (the loop guard proves the status
        enum is not empty)."""
        statuses = list(ServiceStatus)
        assert statuses, "ServiceStatus is empty -- the sweep below is vacuous"
        for status in statuses:
            fallback_service._service_states[AIService.YOLO26].status = status
            assert fallback_service.should_skip_detection() is (status is ServiceStatus.UNAVAILABLE)
            assert fallback_service.should_skip_detection() is not (
                fallback_service.is_service_available(AIService.YOLO26)
            )


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
        assert SHIPPED_SERVICES, "AIService is empty -- the state-count pin would be vacuous"
        assert len(service._service_states) == len(SHIPPED_SERVICES)
        assert set(service._service_states) == SHIPPED_SERVICES


# =============================================================================
# Default Config Tests
# =============================================================================


class TestDefaultConfigs:
    """Tests for DEFAULT_CB_CONFIGS constant."""

    def test_default_cb_configs_has_all_services(self) -> None:
        """Test that DEFAULT_CB_CONFIGS has configs for all services.

        Pinned as an equality against the enum so no enumerated service can
        lose its breaker config (and no config can outlive its service).
        """
        assert SHIPPED_SERVICES, "AIService is empty -- the coverage pin below is vacuous"
        assert set(DEFAULT_CB_CONFIGS) == SHIPPED_SERVICES
        assert AIService.YOLO26 in DEFAULT_CB_CONFIGS

    def test_yolo26_config(self) -> None:
        """Test YOLO26 circuit breaker config."""
        config = DEFAULT_CB_CONFIGS[AIService.YOLO26]
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 60.0
