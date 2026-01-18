"""Integration tests for Service Degradation - Redis/DB/LLM failures.

This module tests the system's graceful degradation capabilities when core services
experience failures. It verifies that the application:
- Handles Redis connection failures with fallback queues
- Manages Database connection failures with appropriate error responses
- Gracefully degrades LLM services with fallback analysis
- Activates circuit breakers to prevent cascading failures
- Reports accurate health status during degradation
- Recovers automatically when services become available

Test Scenarios:
- Redis unavailability (connection failures, timeouts)
- Database connection failures and recovery
- LLM service failures and fallback behavior
- Circuit breaker activation and recovery
- Partial service availability (degraded mode)
- Combined failures (multiple services down)
- Health endpoint reporting during degradation
"""

from __future__ import annotations

import asyncio
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy.exc import OperationalError

from backend.core.redis import RedisClient
from backend.services.ai_fallback import (
    AIFallbackService,
    AIService,
    DegradationLevel,
    reset_ai_fallback_service,
)
from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from backend.services.degradation_manager import (
    DegradationManager,
    DegradationMode,
    DegradationServiceStatus,
    reset_degradation_manager,
)


@pytest.fixture(autouse=True)
def reset_degradation_state() -> None:
    """Reset degradation manager and AI fallback service before each test."""
    reset_degradation_manager()
    reset_ai_fallback_service()


@pytest.fixture
def degradation_manager() -> DegradationManager:
    """Create a DegradationManager for testing."""
    with TemporaryDirectory() as tmpdir:
        manager = DegradationManager(
            fallback_dir=tmpdir,
            failure_threshold=2,
            recovery_threshold=2,
            health_check_timeout=1.0,
        )
        yield manager


@pytest.fixture
def ai_fallback_service() -> AIFallbackService:
    """Create an AIFallbackService for testing."""
    service = AIFallbackService(health_check_interval=1.0)
    yield service
    reset_ai_fallback_service()


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """Create a circuit breaker for testing."""
    return CircuitBreaker(
        name="test_service",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,
            half_open_max_calls=2,
            success_threshold=2,
        ),
    )


class TestRedisConnectionFailures:
    """Tests for Redis connection failure scenarios."""

    @pytest.mark.asyncio
    async def test_redis_connection_error_detected(self, degradation_manager: DegradationManager):
        """Test that Redis connection errors are detected by health checks."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.ping = AsyncMock(side_effect=RedisConnectionError("Connection refused"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)

            result = await manager.check_redis_health()

            assert result is False
            assert manager._redis_healthy is False

    @pytest.mark.asyncio
    async def test_redis_timeout_handled_gracefully(self, degradation_manager: DegradationManager):
        """Test that Redis timeout errors are handled gracefully."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.ping = AsyncMock(side_effect=RedisTimeoutError("Operation timed out"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)

            result = await manager.check_redis_health()

            assert result is False
            assert manager._redis_healthy is False

    @pytest.mark.asyncio
    async def test_redis_failure_uses_memory_queue_fallback(self):
        """Test that Redis failures trigger memory queue fallback."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.add_to_queue_safe = AsyncMock(
            side_effect=RedisConnectionError("Connection refused")
        )

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(
                redis_client=mock_redis, fallback_dir=tmpdir, max_memory_queue_size=100
            )

            # Queue a job - should fall back to memory
            success = await manager.queue_job_for_later("detection", {"test": "data"})

            assert success is True
            assert manager.get_queued_job_count() == 1
            # Verify Redis was marked unhealthy
            assert manager._redis_healthy is False

    @pytest.mark.asyncio
    async def test_redis_failure_uses_disk_queue_fallback(self):
        """Test that Redis failures trigger disk queue fallback."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.add_to_queue_safe = AsyncMock(
            side_effect=RedisConnectionError("Connection refused")
        )

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)

            # Queue with fallback - should use disk
            result = await manager.queue_with_fallback("test_queue", {"key": "value"})

            assert result is True
            assert manager._redis_healthy is False

    @pytest.mark.asyncio
    async def test_redis_recovery_drains_fallback_queue(self):
        """Test that Redis recovery drains items from fallback queues."""
        from backend.core.redis import QueueAddResult

        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)

            # Add items to fallback queue
            fallback = manager._get_fallback_queue("test_queue")
            await fallback.add({"item": 1})
            await fallback.add({"item": 2})

            assert fallback.count() == 2

            # Drain to Redis
            drained = await manager.drain_fallback_queue("test_queue")

            assert drained == 2
            assert fallback.count() == 0
            assert mock_redis.add_to_queue_safe.call_count == 2


class TestDatabaseConnectionFailures:
    """Tests for database connection failure scenarios."""

    @pytest.mark.asyncio
    async def test_database_operational_error_detected(self):
        """Test that database operational errors are detected."""
        manager = DegradationManager(failure_threshold=1)

        async def failing_health_check() -> bool:
            raise OperationalError("statement", {}, Exception("Connection refused"))

        manager.register_service(name="database", health_check=failing_health_check, critical=True)

        await manager.run_health_checks()

        health = manager.get_service_health("database")
        assert health.status == DegradationServiceStatus.UNHEALTHY
        assert health.consecutive_failures >= 1

    @pytest.mark.asyncio
    async def test_database_connection_pool_exhaustion_detected(self):
        """Test that database connection pool exhaustion is detected."""
        manager = DegradationManager(failure_threshold=1)

        async def pool_exhausted_check() -> bool:
            raise OperationalError(
                "statement", {}, Exception("QueuePool limit reached, connection timed out")
            )

        manager.register_service(name="database", health_check=pool_exhausted_check, critical=True)

        await manager.run_health_checks()

        health = manager.get_service_health("database")
        assert health.status == DegradationServiceStatus.UNHEALTHY
        assert "QueuePool limit reached" in (health.error_message or "")

    @pytest.mark.asyncio
    async def test_database_failure_triggers_minimal_mode(self):
        """Test that database failures trigger MINIMAL degradation mode."""
        manager = DegradationManager(failure_threshold=2)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Start in NORMAL
        assert manager.mode == DegradationMode.NORMAL

        # Simulate consecutive failures to exceed threshold
        await manager.update_service_health("database", is_healthy=False)
        await manager.update_service_health("database", is_healthy=False)
        await manager.update_service_health("database", is_healthy=False)

        # Should transition to degraded mode
        assert manager.mode in (DegradationMode.MINIMAL, DegradationMode.OFFLINE)

    @pytest.mark.asyncio
    async def test_database_recovery_restores_normal_mode(self):
        """Test that database recovery restores normal operation."""
        manager = DegradationManager(failure_threshold=2)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Trigger degradation
        await manager.update_service_health("database", is_healthy=False)
        await manager.update_service_health("database", is_healthy=False)
        await manager.update_service_health("database", is_healthy=False)

        # Recover
        await manager.update_service_health("database", is_healthy=True)

        # Should be back to normal
        assert manager.mode == DegradationMode.NORMAL

    @pytest.mark.asyncio
    async def test_database_slow_queries_trigger_timeout(self):
        """Test that slow database queries trigger timeout detection."""
        manager = DegradationManager(failure_threshold=1, health_check_timeout=0.1)

        async def slow_health_check() -> bool:
            await asyncio.sleep(0.5)  # Longer than timeout
            return True

        manager.register_service(name="database", health_check=slow_health_check, critical=True)

        await manager.run_health_checks()

        health = manager.get_service_health("database")
        assert health.status == DegradationServiceStatus.UNHEALTHY
        assert "timed out" in (health.error_message or "").lower()


class TestLLMServiceFailures:
    """Tests for LLM service failure scenarios."""

    @pytest.mark.asyncio
    async def test_nemotron_failure_detected_by_circuit_breaker(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that Nemotron failures are detected by circuit breaker."""
        cb = CircuitBreaker(
            name="nemotron_test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=1.0,
                half_open_max_calls=2,
                success_threshold=2,
            ),
        )
        ai_fallback_service.register_circuit_breaker(AIService.NEMOTRON, cb)

        # Simulate failures to open circuit
        for _ in range(3):
            try:
                async with cb:
                    raise Exception("Nemotron service unavailable")
            except Exception:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # Check service health
        await ai_fallback_service._check_service_health(AIService.NEMOTRON)

        state = ai_fallback_service.get_service_state(AIService.NEMOTRON)
        assert state.status.value == "unavailable"
        assert state.circuit_state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_rtdetr_failure_triggers_detection_skip(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that RT-DETR failures trigger detection skip."""
        # Mark RT-DETR as unavailable
        ai_fallback_service._service_states[
            AIService.RTDETR
        ].status = ai_fallback_service._service_states[
            AIService.RTDETR
        ].status.__class__.UNAVAILABLE

        assert ai_fallback_service.should_skip_detection() is True

    @pytest.mark.asyncio
    async def test_nemotron_failure_uses_fallback_risk_analysis(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that Nemotron failures use fallback risk analysis."""
        # Mark Nemotron as unavailable
        ai_fallback_service._service_states[
            AIService.NEMOTRON
        ].status = ai_fallback_service._service_states[
            AIService.NEMOTRON
        ].status.__class__.UNAVAILABLE

        assert ai_fallback_service.should_use_default_risk() is True

        # Get fallback risk analysis
        result = ai_fallback_service.get_fallback_risk_analysis()

        assert result.is_fallback is True
        assert result.risk_score == 50  # Default medium risk
        assert "unavailable" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_llm_failure_with_cached_risk_scores(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that LLM failures use cached risk scores when available."""
        # Cache a risk score
        ai_fallback_service.cache_risk_score("front_door", 75)

        # Mark Nemotron as unavailable
        ai_fallback_service._service_states[
            AIService.NEMOTRON
        ].status = ai_fallback_service._service_states[
            AIService.NEMOTRON
        ].status.__class__.UNAVAILABLE

        # Get fallback analysis with cache
        result = ai_fallback_service.get_fallback_risk_analysis(camera_name="front_door")

        assert result.risk_score == 75
        assert result.source == "cache"
        assert result.is_fallback is True

    @pytest.mark.asyncio
    async def test_llm_failure_with_object_type_estimation(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that LLM failures estimate risk from object types."""
        # Mark Nemotron as unavailable
        ai_fallback_service._service_states[
            AIService.NEMOTRON
        ].status = ai_fallback_service._service_states[
            AIService.NEMOTRON
        ].status.__class__.UNAVAILABLE

        # Get fallback with object types
        result = ai_fallback_service.get_fallback_risk_analysis(object_types=["person", "vehicle"])

        # Should average person (60) and vehicle (50) = 55
        assert result.risk_score == 55
        assert result.source == "object_type_estimate"


class TestCircuitBreakerActivation:
    """Tests for circuit breaker activation and recovery."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold_failures(
        self, circuit_breaker: CircuitBreaker
    ):
        """Test that circuit breaker opens after reaching failure threshold."""
        # Initially closed
        assert circuit_breaker.get_state() == CircuitState.CLOSED

        # Simulate 3 failures (threshold)
        for _ in range(3):
            try:
                async with circuit_breaker:
                    raise Exception("Service failure")
            except Exception:
                pass

        # Should be open
        assert circuit_breaker.get_state() == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_enters_half_open_after_timeout(
        self, circuit_breaker: CircuitBreaker
    ):
        """Test that circuit breaker enters half-open state after recovery timeout."""
        # Open the circuit
        for _ in range(3):
            try:
                async with circuit_breaker:
                    raise Exception("Service failure")
            except Exception:
                pass

        assert circuit_breaker.get_state() == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.2)  # circuit breaker timing - mocked

        # Attempt a call to trigger half-open
        try:
            async with circuit_breaker:
                pass
        except Exception:
            pass

        # Should be half-open
        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_after_successful_recovery(
        self, circuit_breaker: CircuitBreaker
    ):
        """Test that circuit breaker closes after successful recovery."""
        # Open the circuit
        for _ in range(3):
            try:
                async with circuit_breaker:
                    raise Exception("Service failure")
            except Exception:
                pass

        # Wait for recovery timeout
        await asyncio.sleep(1.2)  # circuit breaker timing - mocked

        # Perform successful calls to recover
        for _ in range(2):  # success_threshold = 2
            try:
                async with circuit_breaker:
                    pass  # Success
            except Exception:
                pass

        # Should be closed
        assert circuit_breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_reopens_on_half_open_failure(
        self, circuit_breaker: CircuitBreaker
    ):
        """Test that circuit breaker reopens if failures occur in half-open state."""
        # Open the circuit
        for _ in range(3):
            try:
                async with circuit_breaker:
                    raise Exception("Service failure")
            except Exception:
                pass

        # Wait for recovery timeout
        await asyncio.sleep(1.2)  # circuit breaker timing - mocked

        # Enter half-open
        try:
            async with circuit_breaker:
                pass
        except Exception:
            pass

        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN

        # Fail in half-open state
        try:
            async with circuit_breaker:
                raise Exception("Still failing")
        except Exception:
            pass

        # Should reopen
        assert circuit_breaker.get_state() == CircuitState.OPEN


class TestPartialServiceAvailability:
    """Tests for graceful degradation with partial service availability."""

    @pytest.mark.asyncio
    async def test_degraded_mode_with_non_critical_service_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test system enters DEGRADED mode when non-critical services are down."""
        # Mark Florence (non-critical) as unavailable
        from backend.services.ai_fallback import ServiceStatus

        ai_fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE

        level = ai_fallback_service.get_degradation_level()
        assert level == DegradationLevel.DEGRADED

    @pytest.mark.asyncio
    async def test_minimal_mode_with_critical_service_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test system enters MINIMAL mode when critical services are down."""
        from backend.services.ai_fallback import ServiceStatus

        # Mark RT-DETR (critical) as unavailable
        ai_fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE

        level = ai_fallback_service.get_degradation_level()
        assert level == DegradationLevel.MINIMAL

    @pytest.mark.asyncio
    async def test_offline_mode_with_all_critical_services_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test system enters OFFLINE mode when all critical services are down."""
        from backend.services.ai_fallback import ServiceStatus

        # Mark both critical services as unavailable
        ai_fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE
        ai_fallback_service._service_states[AIService.NEMOTRON].status = ServiceStatus.UNAVAILABLE

        level = ai_fallback_service.get_degradation_level()
        assert level == DegradationLevel.OFFLINE

    @pytest.mark.asyncio
    async def test_available_features_reduce_with_degradation(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that available features reduce as degradation level increases."""
        from backend.services.ai_fallback import ServiceStatus

        # Normal mode - all features
        normal_features = ai_fallback_service.get_available_features()
        assert "object_detection" in normal_features
        assert "risk_analysis" in normal_features
        assert "image_captioning" in normal_features

        # Mark Florence as unavailable
        ai_fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE

        degraded_features = ai_fallback_service.get_available_features()
        assert "image_captioning" not in degraded_features
        assert "object_detection" in degraded_features  # Still available

        # Mark RT-DETR as unavailable
        ai_fallback_service._service_states[AIService.RTDETR].status = ServiceStatus.UNAVAILABLE

        minimal_features = ai_fallback_service.get_available_features()
        assert "object_detection" not in minimal_features
        assert "event_history" in minimal_features  # Always available


class TestCombinedServiceFailures:
    """Tests for scenarios with multiple service failures."""

    @pytest.mark.asyncio
    async def test_redis_and_llm_failure_combined(self):
        """Test handling of combined Redis and LLM failures."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.ping = AsyncMock(side_effect=RedisConnectionError("Connection refused"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(
                redis_client=mock_redis, fallback_dir=tmpdir, failure_threshold=1
            )

            # Check Redis health
            redis_healthy = await manager.check_redis_health()
            assert redis_healthy is False

            # Register LLM service
            manager.register_service(
                name="llm",
                health_check=AsyncMock(side_effect=Exception("LLM unavailable")),
                critical=False,
            )

            # Run health checks multiple times to exceed failure threshold
            await manager.run_health_checks()
            await manager.run_health_checks()  # Second check to exceed threshold

            # Both services should be unhealthy
            assert manager._redis_healthy is False
            llm_health = manager.get_service_health("llm")
            assert llm_health.status == DegradationServiceStatus.UNHEALTHY

            # System should be degraded (non-critical service failures)
            assert manager.mode == DegradationMode.DEGRADED

    @pytest.mark.asyncio
    async def test_database_and_redis_failure_triggers_minimal_mode(self):
        """Test that database and Redis failures trigger MINIMAL mode."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.ping = AsyncMock(side_effect=RedisConnectionError("Connection refused"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(
                redis_client=mock_redis, fallback_dir=tmpdir, failure_threshold=2
            )

            # Register database as critical
            manager.register_service(
                name="database", health_check=AsyncMock(return_value=False), critical=True
            )

            # Trigger failures
            await manager.run_health_checks()
            await manager.run_health_checks()  # Second check to exceed threshold

            # Should be in minimal or offline mode
            assert manager.mode in (DegradationMode.MINIMAL, DegradationMode.OFFLINE)

    @pytest.mark.asyncio
    async def test_all_services_failing_reports_comprehensive_status(self):
        """Test that status report is comprehensive when all services are failing."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.ping = AsyncMock(side_effect=RedisConnectionError("Redis down"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(
                redis_client=mock_redis, fallback_dir=tmpdir, failure_threshold=1
            )

            # Register multiple services
            manager.register_service(
                name="database",
                health_check=AsyncMock(side_effect=Exception("DB down")),
                critical=True,
            )
            manager.register_service(
                name="llm",
                health_check=AsyncMock(side_effect=Exception("LLM down")),
                critical=False,
            )

            # Run health checks multiple times to exceed failure threshold
            await manager.run_health_checks()
            await manager.run_health_checks()  # Exceed threshold

            status = manager.get_status()

            # Check status structure
            assert "mode" in status
            assert "is_degraded" in status
            assert "services" in status
            assert status["is_degraded"] is True

            # Check service details
            assert "database" in status["services"]
            assert "llm" in status["services"]
            assert status["services"]["database"]["status"] == "unhealthy"
            assert status["services"]["llm"]["status"] == "unhealthy"


class TestHealthEndpointReporting:
    """Tests for health endpoint reporting during degradation."""

    @pytest.mark.asyncio
    async def test_health_status_reports_degraded_redis(self):
        """Test that health status correctly reports degraded Redis."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.ping = AsyncMock(side_effect=RedisConnectionError("Connection refused"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(
                redis_client=mock_redis, fallback_dir=tmpdir, failure_threshold=1
            )

            # Register Redis as a monitored service
            manager.register_service(
                name="redis",
                health_check=AsyncMock(side_effect=RedisConnectionError("Connection refused")),
                critical=False,
            )

            # Check Redis health
            await manager.check_redis_health()

            # Run health checks to trigger mode evaluation
            await manager.run_health_checks()
            await manager.run_health_checks()  # Exceed threshold

            status = manager.get_status()

            assert status["redis_healthy"] is False
            assert status["is_degraded"] is True
            assert status["mode"] != "normal"

    @pytest.mark.asyncio
    async def test_health_status_includes_service_error_messages(self):
        """Test that health status includes service error messages."""
        manager = DegradationManager(failure_threshold=1)

        manager.register_service(
            name="database",
            health_check=AsyncMock(side_effect=Exception("Connection pool exhausted")),
            critical=True,
        )

        await manager.run_health_checks()

        status = manager.get_status()

        assert "services" in status
        assert "database" in status["services"]
        db_status = status["services"]["database"]
        assert "Connection pool exhausted" in db_status.get("error_message", "")

    @pytest.mark.asyncio
    async def test_health_status_tracks_consecutive_failures(self):
        """Test that health status tracks consecutive failure counts."""
        manager = DegradationManager(failure_threshold=5)

        manager.register_service(
            name="test_service", health_check=AsyncMock(return_value=False), critical=False
        )

        # Run multiple health checks
        for _ in range(3):
            await manager.run_health_checks()

        health = manager.get_service_health("test_service")
        assert health.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_health_status_clears_errors_on_recovery(self):
        """Test that health status clears error messages on recovery."""
        manager = DegradationManager(failure_threshold=1)

        health_check_mock = AsyncMock(return_value=False)
        manager.register_service(
            name="test_service", health_check=health_check_mock, critical=False
        )

        # Fail
        await manager.run_health_checks()
        await manager.update_service_health(
            "test_service", is_healthy=False, error_message="Connection failed"
        )

        health = manager.get_service_health("test_service")
        assert health.error_message == "Connection failed"

        # Recover
        await manager.update_service_health("test_service", is_healthy=True)

        health = manager.get_service_health("test_service")
        assert health.error_message is None
        assert health.consecutive_failures == 0


class TestGracefulDegradation:
    """Tests for graceful degradation behavior."""

    @pytest.mark.asyncio
    async def test_system_continues_operation_with_redis_down(self):
        """Test that system continues operation when Redis is down."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.add_to_queue_safe = AsyncMock(
            side_effect=RedisConnectionError("Connection refused")
        )

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)

            # System should continue with fallback
            success = await manager.queue_job_for_later("task", {"data": "value"})

            assert success is True
            assert manager.get_queued_job_count() > 0

    @pytest.mark.asyncio
    async def test_system_provides_fallback_captions_when_florence_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that system provides fallback captions when Florence is down."""
        from backend.services.ai_fallback import ServiceStatus

        # Mark Florence as unavailable
        ai_fallback_service._service_states[AIService.FLORENCE].status = ServiceStatus.UNAVAILABLE

        # Should provide fallback caption
        caption = ai_fallback_service.get_fallback_caption(camera_name="front_door")

        assert "front_door" in caption
        assert len(caption) > 0

    @pytest.mark.asyncio
    async def test_system_provides_fallback_embeddings_when_clip_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that system provides fallback embeddings when CLIP is down."""
        from backend.services.ai_fallback import ServiceStatus

        # Mark CLIP as unavailable
        ai_fallback_service._service_states[AIService.CLIP].status = ServiceStatus.UNAVAILABLE

        # Should provide fallback embedding (zero vector)
        embedding = ai_fallback_service.get_fallback_embedding()

        assert len(embedding) == 768
        assert all(v == 0.0 for v in embedding)
