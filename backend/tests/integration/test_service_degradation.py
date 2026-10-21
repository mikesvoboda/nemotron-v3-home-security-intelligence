"""Integration tests for Service Degradation - Redis/DB/analyzer failures.

This module tests the system's graceful degradation capabilities when core services
experience failures. It verifies that the application:
- Handles Redis connection failures with fallback queues
- Manages Database connection failures with appropriate error responses
- Gracefully degrades the analyzer with fallback risk analysis
- Activates circuit breakers to prevent cascading failures
- Reports accurate health status during degradation
- Recovers automatically when services become available

Test Scenarios:
- Redis unavailability (connection failures, timeouts)
- Database connection failures and recovery
- Analyzer failure and fallback behavior
- Circuit breaker activation and recovery
- Partial service availability (degraded mode)
- Combined failures (multiple services down)
- Health endpoint reporting during degradation

R8 S2b + S3 (both 2026-09-29; S3 by owner rulings 1 + 5) -- READ BEFORE
"FIXING" A TOMBSTONE BELOW
-------------------------------------------------------------------------
Two commits took three provider tiers out from under this file, and the
ATTRIBUTION of every red below is MEASURED, not assumed. The same 33-item
file (byte-identical blob bf1bbc7f, last touched by 4bfd6fa4 before this
rewrite -- it did not exist before d5eb7b54) ran 33/33 GREEN in a throwaway
worktree at ``602379e2^``, 26/33 green at HEAD aaf29361, and 23/33 green
against S3's index. Every red names the commit that actually killed it, and
NO test here pins a claim that was never true:

  * ``602379e2`` ("refactor(r8-s2b): delete the legacy LLM + enrichment
    tier", already an ancestor of HEAD when this slice started) deleted the
    Nemotron LLM's surface FROM THIS MODULE: the ``AIService.NEMOTRON``
    member, the ``should_use_default_risk()`` predicate, the
    ``"risk_analysis"``/``"llm_reasoning"`` feature names, and
    ``CRITICAL_SERVICES`` shrank from ``{YOLO26, NEMOTRON}`` to
    ``{YOLO26}``. All seven of those claims were LIVE and green before it.
    That commit turned 7 of this file's 33 red: the five ids that name
    ``AIService.NEMOTRON`` (AttributeError on the deleted member),
    ``test_minimal_mode_with_critical_service_down`` (with one critical
    member there is no "partial critical outage", so MINIMAL became
    unreachable on ``get_degradation_level`` -- it returned OFFLINE), and
    ``test_available_features_reduce_with_degradation`` (the
    ``risk_analysis`` feature name was deleted, not renamed).
  * S3 (this slice, rulings 1 + 5) deleted Florence-2 (captions) and CLIP
    (embeddings/re-ID): enum members, provider rows, clients, adapters and
    Triton models, the ``ai/florence`` + ``ai/clip`` serving dirs swept with
    ``git rm`` (ruling 4). That turned the remaining 3 red --
    ``test_degraded_mode_with_non_critical_service_down``,
    ``test_system_provides_fallback_captions_when_florence_down`` and
    ``test_system_provides_fallback_embeddings_when_clip_down`` -- which
    were still green at HEAD.

So: 7 of the 10 arrivals are S2b's and 3 are S3's, and a reader who files
all 10 as "S3 sweep collateral" buries the S2b report -- which matters
because the S2b seven went red MERGED, in the integration tier, and if any
CI view called them green that view is the bug to hunt, not this file.

WHAT IS LIVE, so no one re-retires machinery that still ships: the analyzer
fallback ladder (risk-score cache, object-type estimate, default score), the
detector-derived caption, the zero-vector re-ID stand-in, ``should_skip_
detection``, circuit breakers, and the ``DegradationManager`` NORMAL ->
DEGRADED -> MINIMAL -> OFFLINE ladder (the manager has five shipped importers;
``ai_fallback`` has ZERO and is kept-and-DEAD, ledgered as flagged-not-
deleted). The sibling file ``backend/tests/unit/services/test_ai_fallback.py``
owns that module's unit surface; the tombstones below are the INTEGRATION-tier
record of what walked out from under this file, and they never re-litigate a
property the unit tier already pins.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy.exc import OperationalError

from backend.core.redis import RedisClient
from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from backend.services.degradation_manager import (
    DegradationManager,
    DegradationMode,
    DegradationServiceStatus,
    reset_degradation_manager,
)


@pytest.fixture(autouse=True)
def reset_degradation_state() -> None:
    """Reset degradation manager before each test."""
    reset_degradation_manager()


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
    """B3.2 tombstone: non-shipping backend/services/ai_fallback.py is deleted."""

    def test_ai_fallback_module_deleted_in_b32(self) -> None:
        assert not (
            Path(__file__).resolve().parents[3] / "backend/services/ai_fallback.py"
        ).exists()


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
        await asyncio.sleep(1.2)  # mocked: circuit breaker timing

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
        await asyncio.sleep(1.2)  # mocked: circuit breaker timing

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
        await asyncio.sleep(1.2)  # mocked: circuit breaker timing

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
    """Graceful degradation with partial service availability.

    Two commits changed the SHAPE reachable from this class without changing
    its point, and the two arms they took are DIFFERENT arms:

      * ``602379e2`` (R8-S2b) shrank ``CRITICAL_SERVICES`` from
        ``{YOLO26, NEMOTRON}`` to ``{YOLO26}``. With a one-member critical set
        there is no such thing as "some but not all critical services down",
        so MINIMAL stopped being reachable on ``get_degradation_level`` (it
        falls through to OFFLINE). That is why
        ``test_minimal_mode_with_critical_service_down`` was already red when
        S3 started -- the state it drove had been gone since S2b.
      * This slice (rulings 1 + 5) deleted the two non-critical members,
        Florence and CLIP. With zero non-critical members the
        ``non_critical_unavailable > 0`` branch (ai_fallback.py:472-473) cannot
        fire, so DEGRADED stopped being reachable too -- which is why
        ``test_degraded_mode_with_non_critical_service_down`` is red only now.

    ``get_degradation_level`` (ai_fallback.py:451-475) can therefore return
    exactly two values today, NORMAL and OFFLINE. Verified by sweeping the
    census per member below, and the sweep is per-member on purpose: setting
    every member to the same status and sweeping the statuses PASSES against
    the pre-S3 tree too (all-down reads OFFLINE there as it does here), so it
    would have proved nothing.

    The four-mode ladder these ids were reaching for is NOT gone -- it lives
    on ``DegradationManager``, which has five shipped importers
    (backend/main.py, backend/api/routes/system.py, backend/services/__init__.py,
    backend/services/health_service_registry.py, backend/services/vlm_client.py)
    and whose ``_evaluate_mode_transition`` (degradation_manager.py:528-550)
    still computes all four modes over a service registry that can hold any
    number of critical and non-critical members. Both ids are RETARGETED onto
    that live ladder rather than tombstoned: the behavior they pinned still
    ships, only their dead-shaped fixture is gone.
    """

    @pytest.mark.asyncio
    async def test_degraded_mode_with_non_critical_service_down(self):
        """RETARGETED onto DegradationManager (ai_fallback.py deleted in B3.2)."""
        manager = DegradationManager(failure_threshold=1)
        manager.register_service(
            name="analytics", health_check=AsyncMock(return_value=True), critical=False
        )
        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        await manager.run_health_checks()
        assert manager.mode == DegradationMode.NORMAL
        assert manager.get_service_health("database").status == DegradationServiceStatus.HEALTHY

        await manager.update_service_health("analytics", is_healthy=False)

        assert manager.mode == DegradationMode.DEGRADED
        assert manager.get_service_health("analytics").status == DegradationServiceStatus.UNHEALTHY
        assert manager.get_service_health("database").status == DegradationServiceStatus.HEALTHY
        assert manager.is_degraded is True

        await manager.update_service_health("database", is_healthy=False)
        assert manager.mode != DegradationMode.DEGRADED

    @pytest.mark.asyncio
    async def test_minimal_mode_with_critical_service_down(self):
        """RETARGETED onto DegradationManager (ai_fallback.py deleted in B3.2)."""
        manager = DegradationManager(failure_threshold=1)
        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )
        manager.register_service(
            name="vlm_analyzer", health_check=AsyncMock(return_value=True), critical=True
        )
        criticals = [s for s in manager._services.values() if s.critical]
        assert len(criticals) == 2
        await manager.run_health_checks()
        assert manager.mode == DegradationMode.NORMAL

        await manager.update_service_health("database", is_healthy=False)
        assert manager.mode == DegradationMode.MINIMAL
        assert manager.get_service_health("vlm_analyzer").status == DegradationServiceStatus.HEALTHY

        await manager.update_service_health("vlm_analyzer", is_healthy=False)
        assert manager.mode == DegradationMode.OFFLINE

    @pytest.mark.asyncio
    async def test_offline_mode_with_all_critical_services_down(self):
        """RETARGETED onto DegradationManager (ai_fallback.py deleted in B3.2)."""
        manager = DegradationManager(failure_threshold=1)
        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )
        manager.register_service(
            name="vlm_analyzer", health_check=AsyncMock(return_value=True), critical=True
        )
        await manager.update_service_health("database", is_healthy=False)
        await manager.update_service_health("vlm_analyzer", is_healthy=False)
        assert manager.mode == DegradationMode.OFFLINE


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
