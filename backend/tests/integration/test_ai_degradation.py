"""Integration tests for AI service graceful degradation.

Tests the AIFallbackService and its integration with circuit breakers,
fallback strategies, and status broadcasting.

Test scenarios:
- Circuit breaker state transitions
- Fallback behavior verification
- Degradation level calculation
- WebSocket status notification
- Recovery scenario testing
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from backend.services.ai_fallback import (
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
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)


@pytest.fixture
def reset_fallback_service():
    """Reset the global AI fallback service before and after each test."""
    reset_ai_fallback_service()
    yield
    reset_ai_fallback_service()


@pytest.fixture
def ai_fallback_service(reset_fallback_service) -> AIFallbackService:
    """Create a fresh AI fallback service for testing."""
    return AIFallbackService(health_check_interval=1.0)


@pytest.fixture
def circuit_breaker_rtdetr() -> CircuitBreaker:
    """Create a circuit breaker for RT-DETR testing."""
    return CircuitBreaker(
        name="rtdetr_test",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,  # Short timeout for testing
            half_open_max_calls=2,
            success_threshold=2,
        ),
    )


@pytest.fixture
def circuit_breaker_nemotron() -> CircuitBreaker:
    """Create a circuit breaker for Nemotron testing."""
    return CircuitBreaker(
        name="nemotron_test",
        config=CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=1.0,
            half_open_max_calls=3,
            success_threshold=2,
        ),
    )


class TestAIFallbackServiceBasics:
    """Test basic AIFallbackService functionality."""

    def test_service_initialization(self, ai_fallback_service: AIFallbackService):
        """Test that service initializes with correct defaults."""
        # All services should start as healthy
        for service in AIService:
            state = ai_fallback_service.get_service_state(service)
            assert state.status == ServiceStatus.HEALTHY
            assert state.circuit_state == CircuitState.CLOSED
            assert state.failure_count == 0

    def test_degradation_level_normal(self, ai_fallback_service: AIFallbackService):
        """Test degradation level is normal when all services are healthy."""
        level = ai_fallback_service.get_degradation_level()
        assert level == DegradationLevel.NORMAL

    def test_is_service_available_returns_true_when_healthy(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that healthy services are reported as available."""
        assert ai_fallback_service.is_service_available(AIService.RTDETR) is True
        assert ai_fallback_service.is_service_available(AIService.NEMOTRON) is True
        assert ai_fallback_service.is_service_available(AIService.FLORENCE) is True
        assert ai_fallback_service.is_service_available(AIService.CLIP) is True

    def test_is_service_available_accepts_string(self, ai_fallback_service: AIFallbackService):
        """Test that service availability can be checked with string names."""
        assert ai_fallback_service.is_service_available("rtdetr") is True
        assert ai_fallback_service.is_service_available("nemotron") is True


class TestCircuitBreakerIntegration:
    """Test integration with circuit breakers."""

    def test_register_circuit_breaker(
        self,
        ai_fallback_service: AIFallbackService,
        circuit_breaker_rtdetr: CircuitBreaker,
    ):
        """Test registering a circuit breaker for a service."""
        ai_fallback_service.register_circuit_breaker(AIService.RTDETR, circuit_breaker_rtdetr)

        # Should be registered without error
        state = ai_fallback_service.get_service_state(AIService.RTDETR)
        assert state is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_marks_service_unavailable(
        self,
        ai_fallback_service: AIFallbackService,
        circuit_breaker_rtdetr: CircuitBreaker,
    ):
        """Test that an open circuit breaker marks the service as unavailable."""
        ai_fallback_service.register_circuit_breaker(AIService.RTDETR, circuit_breaker_rtdetr)

        # Simulate failures to open the circuit
        for _ in range(3):
            try:
                async with circuit_breaker_rtdetr:
                    raise Exception("Simulated failure")
            except Exception:
                pass

        assert circuit_breaker_rtdetr.get_state() == CircuitState.OPEN

        # Check service health (manually trigger since we didn't start background task)
        await ai_fallback_service._check_service_health(AIService.RTDETR)

        state = ai_fallback_service.get_service_state(AIService.RTDETR)
        assert state.status == ServiceStatus.UNAVAILABLE
        assert state.circuit_state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_marks_service_degraded(
        self,
        ai_fallback_service: AIFallbackService,
    ):
        """Test that a half-open circuit breaker marks the service as degraded."""
        # Create circuit breaker with very short timeout
        cb = CircuitBreaker(
            name="rtdetr_half_open_test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=0.1,  # Very short timeout
                half_open_max_calls=2,
                success_threshold=2,
            ),
        )
        ai_fallback_service.register_circuit_breaker(AIService.RTDETR, cb)

        # Open the circuit
        for _ in range(3):
            try:
                async with cb:
                    raise Exception("Simulated failure")
            except Exception:
                pass

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Try to enter half-open state by attempting a call
        # This triggers the state check in the circuit breaker
        try:
            async with cb:
                pass  # This will transition to half-open
        except Exception:
            pass

        # Circuit should be half-open after timeout
        assert cb.get_state() == CircuitState.HALF_OPEN

        await ai_fallback_service._check_service_health(AIService.RTDETR)

        state = ai_fallback_service.get_service_state(AIService.RTDETR)
        assert state.status == ServiceStatus.DEGRADED
        assert state.circuit_state == CircuitState.HALF_OPEN


class TestDegradationLevels:
    """Test degradation level calculations."""

    @pytest.mark.asyncio
    async def test_degradation_level_degraded_non_critical_down(
        self,
        ai_fallback_service: AIFallbackService,
    ):
        """Test degradation level is DEGRADED when non-critical services are down."""
        # Mark Florence as unavailable
        ai_fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE

        level = ai_fallback_service.get_degradation_level()
        assert level == DegradationLevel.DEGRADED

    @pytest.mark.asyncio
    async def test_degradation_level_minimal_critical_partially_down(
        self,
        ai_fallback_service: AIFallbackService,
    ):
        """Test degradation level is MINIMAL when critical services are partially down."""
        # Mark RT-DETR as unavailable (critical)
        ai_fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE

        level = ai_fallback_service.get_degradation_level()
        assert level == DegradationLevel.MINIMAL

    @pytest.mark.asyncio
    async def test_degradation_level_offline_all_critical_down(
        self,
        ai_fallback_service: AIFallbackService,
    ):
        """Test degradation level is OFFLINE when all critical services are down."""
        # Mark both critical services as unavailable
        ai_fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE
        ai_fallback_service._service_states[AIService.NEMOTRON].status = ServiceStatus.UNAVAILABLE

        level = ai_fallback_service.get_degradation_level()
        assert level == DegradationLevel.OFFLINE


class TestFallbackBehavior:
    """Test fallback strategies for unavailable services."""

    def test_fallback_risk_analysis_default(self, ai_fallback_service: AIFallbackService):
        """Test default fallback risk analysis returns medium risk."""
        result = ai_fallback_service.get_fallback_risk_analysis()

        assert isinstance(result, FallbackRiskAnalysis)
        assert result.risk_score == 50
        assert result.is_fallback is True
        assert result.source == "default"
        assert "unavailable" in result.reasoning.lower()

    def test_fallback_risk_analysis_with_cached_score(self, ai_fallback_service: AIFallbackService):
        """Test fallback uses cached score when available."""
        # Cache a score
        ai_fallback_service.cache_risk_score("front_door", 75)

        result = ai_fallback_service.get_fallback_risk_analysis(camera_name="front_door")

        assert result.risk_score == 75
        assert result.source == "cache"

    def test_fallback_risk_analysis_with_object_types(self, ai_fallback_service: AIFallbackService):
        """Test fallback estimates risk from object types."""
        result = ai_fallback_service.get_fallback_risk_analysis(object_types=["person", "vehicle"])

        # Should average person (60) and vehicle (50) = 55
        assert result.risk_score == 55
        assert result.source == "object_type_estimate"

    def test_fallback_caption_basic(self, ai_fallback_service: AIFallbackService):
        """Test basic fallback caption."""
        caption = ai_fallback_service.get_fallback_caption()
        assert caption == "Activity detected"

    def test_fallback_caption_with_camera(self, ai_fallback_service: AIFallbackService):
        """Test fallback caption with camera name."""
        caption = ai_fallback_service.get_fallback_caption(camera_name="front_door")
        assert "front_door" in caption

    def test_fallback_caption_with_objects(self, ai_fallback_service: AIFallbackService):
        """Test fallback caption with object types."""
        caption = ai_fallback_service.get_fallback_caption(
            object_types=["person", "vehicle"], camera_name="driveway"
        )
        assert "person" in caption.lower()
        assert "vehicle" in caption.lower()
        assert "driveway" in caption

    def test_fallback_embedding_returns_zero_vector(self, ai_fallback_service: AIFallbackService):
        """Test fallback embedding returns zero vector."""
        embedding = ai_fallback_service.get_fallback_embedding()

        assert len(embedding) == 768
        assert all(v == 0.0 for v in embedding)


class TestServiceAvailabilityChecks:
    """Test convenience methods for checking service availability."""

    def test_should_skip_detection_when_rtdetr_unavailable(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test detection skip flag when RT-DETR is unavailable."""
        # Initially should not skip
        assert ai_fallback_service.should_skip_detection() is False

        # Mark as unavailable
        ai_fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE

        assert ai_fallback_service.should_skip_detection() is True

    def test_should_use_default_risk_when_nemotron_unavailable(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test default risk flag when Nemotron is unavailable."""
        assert ai_fallback_service.should_use_default_risk() is False

        ai_fallback_service._service_states[AIService.NEMOTRON].status = ServiceStatus.UNAVAILABLE

        assert ai_fallback_service.should_use_default_risk() is True

    def test_should_skip_captions_when_florence_unavailable(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test caption skip flag when Florence is unavailable."""
        assert ai_fallback_service.should_skip_captions() is False

        ai_fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE

        assert ai_fallback_service.should_skip_captions() is True

    def test_should_skip_reid_when_clip_unavailable(self, ai_fallback_service: AIFallbackService):
        """Test re-id skip flag when CLIP is unavailable."""
        assert ai_fallback_service.should_skip_reid() is False

        ai_fallback_service._service_states[AIService.CLIP].status = ServiceStatus.UNAVAILABLE

        assert ai_fallback_service.should_skip_reid() is True


class TestAvailableFeatures:
    """Test available features calculation."""

    def test_all_features_when_all_services_healthy(self, ai_fallback_service: AIFallbackService):
        """Test all features available when all services are healthy."""
        features = ai_fallback_service.get_available_features()

        # Check critical features
        assert "object_detection" in features
        assert "detection_alerts" in features
        assert "risk_analysis" in features
        assert "llm_reasoning" in features
        assert "image_captioning" in features
        assert "entity_tracking" in features

        # Check always-available features
        assert "event_history" in features
        assert "camera_feeds" in features
        assert "system_monitoring" in features

    def test_reduced_features_when_florence_unavailable(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test caption features removed when Florence is unavailable."""
        ai_fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE

        features = ai_fallback_service.get_available_features()

        assert "image_captioning" not in features
        assert "ocr" not in features
        assert "dense_captioning" not in features

        # Other features should remain
        assert "object_detection" in features
        assert "risk_analysis" in features

    def test_reduced_features_when_clip_unavailable(self, ai_fallback_service: AIFallbackService):
        """Test re-id features removed when CLIP is unavailable."""
        ai_fallback_service._service_states[AIService.CLIP].status = ServiceStatus.UNAVAILABLE

        features = ai_fallback_service.get_available_features()

        assert "entity_tracking" not in features
        assert "re_identification" not in features
        assert "anomaly_detection" not in features

        # Other features should remain
        assert "object_detection" in features
        assert "image_captioning" in features


class TestStatusBroadcasting:
    """Test WebSocket status broadcasting."""

    @pytest.mark.asyncio
    async def test_status_callback_called_on_change(self, ai_fallback_service: AIFallbackService):
        """Test that registered callbacks are called when status changes."""
        callback_called = asyncio.Event()
        received_status: dict[str, Any] = {}

        async def status_callback(status: dict[str, Any]):
            nonlocal received_status
            received_status = status
            callback_called.set()

        ai_fallback_service.register_status_callback(status_callback)

        # Trigger status change
        ai_fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE
        await ai_fallback_service._notify_status_change()

        # Wait for callback
        await asyncio.wait_for(callback_called.wait(), timeout=1.0)

        assert "degradation_mode" in received_status
        assert "services" in received_status
        assert "available_features" in received_status
        assert received_status["degradation_mode"] == "minimal"

    @pytest.mark.asyncio
    async def test_unregister_callback(self, ai_fallback_service: AIFallbackService):
        """Test that unregistered callbacks are not called."""
        call_count = 0

        async def status_callback(status: dict[str, Any]):
            nonlocal call_count
            call_count += 1

        ai_fallback_service.register_status_callback(status_callback)
        ai_fallback_service.unregister_status_callback(status_callback)

        # Trigger status change
        await ai_fallback_service._notify_status_change()

        # Small delay to ensure callback would have been called
        await asyncio.sleep(0.1)

        assert call_count == 0


class TestRiskScoreCache:
    """Test the risk score cache."""

    def test_cache_stores_and_retrieves(self):
        """Test basic cache storage and retrieval."""
        cache = RiskScoreCache(ttl_seconds=60)

        cache.set_cached_score("front_door", 75)
        assert cache.get_cached_score("front_door") == 75

    def test_cache_returns_none_for_unknown_camera(self):
        """Test cache returns None for unknown cameras."""
        cache = RiskScoreCache()

        assert cache.get_cached_score("unknown_camera") is None

    def test_cache_expires_after_ttl(self):
        """Test cache entries expire after TTL."""
        cache = RiskScoreCache(ttl_seconds=0)  # Immediate expiration

        cache.set_cached_score("front_door", 75)

        # Should be expired
        assert cache.get_cached_score("front_door") is None

    def test_object_type_scores(self):
        """Test object type default scores."""
        cache = RiskScoreCache()

        assert cache.get_object_type_score("person") == 60
        assert cache.get_object_type_score("vehicle") == 50
        assert cache.get_object_type_score("dog") == 25
        assert cache.get_object_type_score("unknown_type") == 50  # Default


class TestServiceState:
    """Test ServiceState dataclass."""

    def test_to_dict_serialization(self):
        """Test ServiceState serializes correctly."""
        now = datetime.now(UTC)
        state = ServiceState(
            service=AIService.RTDETR,
            status=ServiceStatus.HEALTHY,
            circuit_state=CircuitState.CLOSED,
            last_success=now,
            failure_count=0,
            error_message=None,
            last_check=now,
        )

        result = state.to_dict()

        assert result["service"] == "rtdetr"
        assert result["status"] == "healthy"
        assert result["circuit_state"] == "closed"
        assert result["failure_count"] == 0
        assert result["error_message"] is None

    def test_to_dict_with_error(self):
        """Test ServiceState serializes error message correctly."""
        state = ServiceState(
            service=AIService.NEMOTRON,
            status=ServiceStatus.UNAVAILABLE,
            circuit_state=CircuitState.OPEN,
            failure_count=5,
            error_message="Connection refused",
        )

        result = state.to_dict()

        assert result["status"] == "unavailable"
        assert result["circuit_state"] == "open"
        assert result["failure_count"] == 5
        assert result["error_message"] == "Connection refused"


class TestFallbackRiskAnalysis:
    """Test FallbackRiskAnalysis dataclass."""

    def test_to_dict_serialization(self):
        """Test FallbackRiskAnalysis serializes correctly."""
        analysis = FallbackRiskAnalysis(
            risk_score=50,
            reasoning="Test reasoning",
            is_fallback=True,
            source="default",
        )

        result = analysis.to_dict()

        assert result["risk_score"] == 50
        assert result["reasoning"] == "Test reasoning"
        assert result["is_fallback"] is True
        assert result["source"] == "default"


class TestGlobalInstance:
    """Test global instance management."""

    def test_get_ai_fallback_service_returns_same_instance(self, reset_fallback_service):
        """Test that get_ai_fallback_service returns singleton."""
        instance1 = get_ai_fallback_service()
        instance2 = get_ai_fallback_service()

        assert instance1 is instance2

    def test_reset_creates_new_instance(self, reset_fallback_service):
        """Test that reset_ai_fallback_service creates new instance."""
        instance1 = get_ai_fallback_service()
        reset_ai_fallback_service()
        instance2 = get_ai_fallback_service()

        assert instance1 is not instance2


class TestDegradationStatus:
    """Test the full degradation status output."""

    def test_get_degradation_status_structure(self, ai_fallback_service: AIFallbackService):
        """Test degradation status returns correct structure."""
        status = ai_fallback_service.get_degradation_status()

        assert "timestamp" in status
        assert "degradation_mode" in status
        assert "services" in status
        assert "available_features" in status

        # Check services structure
        assert "rtdetr" in status["services"]
        assert "nemotron" in status["services"]
        assert "florence" in status["services"]
        assert "clip" in status["services"]

    def test_get_degradation_status_timestamp_format(self, ai_fallback_service: AIFallbackService):
        """Test degradation status timestamp is ISO format."""
        status = ai_fallback_service.get_degradation_status()

        # Should be parseable as ISO timestamp
        timestamp = datetime.fromisoformat(status["timestamp"].replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)
