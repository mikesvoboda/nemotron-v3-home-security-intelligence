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
from backend.services import ai_fallback as ai_fallback_module
from backend.services.ai_fallback import (
    CRITICAL_SERVICES,
    AIFallbackService,
    AIService,
    DegradationLevel,
    ServiceStatus,
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
    """Tests for analyzer/LLM service failure scenarios.

    Tier note after R8 S2b + S3: the class name says "LLM" because these ids
    were written when the Nemotron LLM was the analyzer. ``AIService.NEMOTRON``
    DID ship -- added at a50aa76d alongside ``should_use_default_risk()`` --
    and ``602379e2`` (R8-S2b) deleted it with the rest of that LLM's surface.
    Measured: this file was 33/33 green at ``602379e2^`` and 7-red at HEAD
    aaf29361, 5 of the 7 AttributeErrors from that deleted member. Each id is
    kept; each one now pins which half of its claim still ships and states
    the ABSENCE of the dead half against live forms.
    """

    # The dead slugs, written as the strings the retired fixtures used. Kept as
    # DATA so the absence pins below are enumerable instead of scattered.
    RETIRED_SERVICE_SLUGS = ("nemotron", "florence", "clip")

    @pytest.mark.asyncio
    async def test_nemotron_failure_detected_by_circuit_breaker(
        self, ai_fallback_service: AIFallbackService
    ):
        """Half retargeted, half tombstoned -- and the red is S2b's, not S3's.

        WHAT DIED: ``AIService.NEMOTRON``, the breaker key this id registered.
        The member DID ship (a50aa76d added it with the rest of the Nemotron
        arm) and ``602379e2`` -- "refactor(r8-s2b): delete the legacy LLM +
        enrichment tier", already merged into HEAD when this slice began --
        deleted it. Measured on throwaway worktrees of this byte-identical
        file: green at ``602379e2^``, AttributeError at HEAD. Filing it as
        S3 sweep collateral would hide that S2b went red MERGED, in the
        integration tier.

        WHAT STILL SHIPS (retargeted onto): a registered circuit breaker's
        OPEN state is propagated into the service's ``ServiceState`` by
        ``_check_service_health`` (ai_fallback.py:365-377: OPEN ->
        ServiceStatus.UNAVAILABLE, HALF_OPEN -> DEGRADED, CLOSED -> HEALTHY).
        That arm is live for YOLO26, the one service whose backend still
        boots. The breaker-driven assertion is carried over verbatim -- open
        breaker -> status "unavailable" + circuit_state OPEN -- because the
        propagation was never Nemotron-specific; only the key was.

        NON-VACUITY, stated because each failure mode is reachable: (a) a
        breaker nobody tripped would pass "circuit_state == OPEN" only by
        luck, so the OPEN state is proven BEFORE the health check; (b) a
        hand-set UNAVAILABLE status would pass the status assert without the
        breaker doing anything, so the state is seeded HEALTHY and the flip is
        observed; (c) the enum-lookup absence pin would be satisfied by an
        EMPTY enum, so the surviving census is proven non-empty in the same
        breath.
        """
        cb = CircuitBreaker(
            name="yolo26_test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=1.0,
                half_open_max_calls=2,
                success_threshold=2,
            ),
        )
        ai_fallback_service.register_circuit_breaker(AIService.YOLO26, cb)

        # Simulate failures to open circuit
        for _ in range(3):
            try:
                async with cb:
                    raise Exception("detector service unavailable")
            except Exception:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # Non-vacuity (b): the state starts HEALTHY, so the flip below can only
        # come from the breaker the registration just installed.
        seeded = ai_fallback_service.get_service_state(AIService.YOLO26)
        assert seeded.status == ServiceStatus.HEALTHY

        # Check service health
        await ai_fallback_service._check_service_health(AIService.YOLO26)

        state = ai_fallback_service.get_service_state(AIService.YOLO26)
        assert state.status.value == "unavailable"
        assert state.circuit_state == CircuitState.OPEN

        # TOMBSTONE half, asserted against LIVE forms: the retired slugs are not
        # enum members, so no deployment can name them. ``AIService(slug)`` is
        # the form that would have executed -- a comment naming them is prose.
        census = {member.value for member in AIService}
        assert census, "AIService is empty -- the absence pins below assert nothing"
        assert AIService.YOLO26.value in census, "the surviving service vanished"
        for slug in self.RETIRED_SERVICE_SLUGS:
            assert slug not in census, f"retired service {slug!r} is back on the enum"
            with pytest.raises(ValueError, match=slug):
                AIService(slug)
        # The breaker the test just proved alive is also refused a dead key --
        # registration keyed on a retired slug cannot silently reappear.
        with pytest.raises(ValueError, match="nemotron"):
            AIService("nemotron")

    @pytest.mark.asyncio
    async def test_yolo26_failure_triggers_detection_skip(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test that YOLO26 failures trigger detection skip."""
        # Mark YOLO26 as unavailable
        ai_fallback_service._service_states[
            AIService.YOLO26
        ].status = ai_fallback_service._service_states[
            AIService.YOLO26
        ].status.__class__.UNAVAILABLE

        assert ai_fallback_service.should_skip_detection() is True

    @pytest.mark.asyncio
    async def test_nemotron_failure_uses_fallback_risk_analysis(
        self, ai_fallback_service: AIFallbackService
    ):
        """Tombstone for the ``should_use_default_risk()`` gate, retarget for
        the analyzer-down ladder. Red from S2b (``602379e2``), not from S3.

        WHAT DIED: ``should_use_default_risk()`` SHIPPED -- a50aa76d added it
        as exactly ``return not self.is_service_available(AIService.NEMOTRON)``,
        and ``602379e2`` (R8-S2b) deleted it together with the member it keyed
        on. Measured: green at ``602379e2^``, AttributeError at HEAD. So this
        is a real retirement, and the hazard it writes out is the resurrection
        one: a reader who "restores the gate" re-adds a boolean availability
        flag for a service no deployment can boot, giving the module a second,
        decorative way to answer a question ``is_service_available`` already
        answers. Note what did NOT die: the PATTERN ``not
        is_service_available(<service>)`` still ships as
        ``should_skip_detection`` -- which is why the hasattr probe below is
        not a probe into a class with no predicates.

        WHAT STILL SHIPS (retargeted onto): the no-cache / no-object-types
        branch of ``get_fallback_risk_analysis`` -- ai_fallback.py:561-569
        returns ``risk_score=50``, ``source="default"``, ``is_fallback=True``
        with "VLM analyzer is currently unavailable" in the reasoning. That is
        the shipped expression of "the analyzer cannot score this frame", and
        it is a SCORE with a provenance tag rather than a boolean gate. The
        gate's intent ("when the analyzer is out, the caller still gets a
        number") is pinned honestly and not weakened: the number arrives and
        is marked as a fallback.

        NON-VACUITY: a ``FallbackRiskAnalysis`` defaulting to
        ``is_fallback=True`` / ``risk_score=50`` would make the three positive
        asserts pass for a method that never consulted anything, so the pin is
        made discriminating two ways -- the default score is pinned as the
        DISTINCT value 50 while the object-type and cache arms are pinned as
        different values (55 and 75, in the two tests below), and the absence
        of the retired predicate is asserted against LIVE forms (``hasattr``
        on the shipped class), plus non-vacuity on the ``hasattr`` check: the
        SURVIVING sibling predicate ``should_skip_detection`` must still be an
        attribute, so "not found" cannot be an artifact of looking in the
        wrong place.
        """
        # Non-vacuity FIRST, and it is the load-bearing line of this tombstone:
        # an absent attribute is also what a DELETED class reports, and every
        # hasattr below would then pass for free. The module is kept-and-DEAD
        # (zero shipped importers, ledgered flagged-not-deleted), so its final
        # deletion is a later slice's -- if that slice lands, these absences
        # stop being evidence and this line reddens instead of going quiet.
        assert ai_fallback_module.__file__ and Path(ai_fallback_module.__file__).exists()
        assert hasattr(AIFallbackService, "get_fallback_risk_analysis"), (
            "AIFallbackService is gone or gutted -- every hasattr-absence below "
            "would pass vacuously; re-tombstone this test as a module absence"
        )

        # TOMBSTONE half: the predicate is absent from the shipped class.
        assert not hasattr(ai_fallback_service, "should_use_default_risk"), (
            "should_use_default_risk() is back -- 602379e2 (R8-S2b) deleted it "
            "with the member it keyed on; the ladder is expressed by "
            "get_fallback_risk_analysis()'s arms instead of a second flag"
        )
        # Non-vacuity: the same lookup DOES find the surviving predicate.
        assert hasattr(ai_fallback_service, "should_skip_detection"), (
            "the hasattr probe above is vacuous -- the class has no predicates"
        )
        assert not hasattr(ai_fallback_service, "should_skip_captions"), (
            "S3 retired the caption arm (ruling 1); this predicate keyed on it"
        )
        assert not hasattr(ai_fallback_service, "should_skip_reid"), (
            "S3 retired the CLIP re-ID arm (ruling 5); this predicate keyed on it"
        )

        # RETARGETED half: analyzer-down -> default score, still marked fallback.
        result = ai_fallback_service.get_fallback_risk_analysis()

        assert result.is_fallback is True
        assert result.risk_score == 50  # Default medium risk
        assert result.source == "default"
        assert "unavailable" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_llm_failure_with_cached_risk_scores(
        self, ai_fallback_service: AIFallbackService
    ):
        """RETARGETED: the cache arm of the analyzer fallback ladder, with the
        dead Nemotron fixture cut out (red from S2b's ``602379e2``, not S3).

        WHAT DIED: only the fixture. The three lines as written marked
        ``AIService.NEMOTRON`` unavailable -- the member shipped at a50aa76d
        and ``602379e2`` deleted it; S3 then took Florence and CLIP, leaving
        the one-member census at ``backend/services/ai_fallback.py:57-61`` with
        ``CRITICAL_SERVICES = {YOLO26}`` at :199. The mutation never fed the
        assertion, measured at ``602379e2^`` as well as now:
        ``get_fallback_risk_analysis`` (ai_fallback.py:518-569) reads
        ``self._risk_cache``, never ``_service_states``, so even when the
        member existed those lines were decorative fixture. Cutting them loses
        no coverage -- and the cache arm's REASONING string is the one live
        change: "Nemotron analyzer is currently unavailable" became "VLM
        analyzer is currently unavailable" (asserted as ``"unavailable" in
        reasoning`` in the sibling test above, which is the form that survives
        either renaming).

        NON-VACUITY: ``RiskScoreCache.get_object_type_score`` falls back to 50
        for an unknown type (ai_fallback.py:185), so a cache that never
        actually stored the camera would hand back 50 -- the pin therefore
        asserts 75 (the stored value, reachable only through the cache) AND
        ``source == "cache"`` AND that the same camera name WITHOUT the write
        falls through to a different arm. That last leg is what makes "the
        cache was consulted" a measurement rather than an assumption.
        """
        # Control leg FIRST, before anything is cached: an uncached camera falls
        # through to the default arm. Proven non-empty so the 75 below means
        # "the cache answered", not "every arm returns the same number".
        before = ai_fallback_service.get_fallback_risk_analysis(camera_name="front_door")
        assert before.source == "default"
        assert before.risk_score == 50

        # Cache a risk score
        ai_fallback_service.cache_risk_score("front_door", 75)

        # Get fallback analysis with cache
        result = ai_fallback_service.get_fallback_risk_analysis(camera_name="front_door")

        assert result.risk_score == 75
        assert result.source == "cache"
        assert result.is_fallback is True
        # Cache beats the object-type arm even when both could answer.
        both = ai_fallback_service.get_fallback_risk_analysis(
            camera_name="front_door", object_types=["person", "vehicle"]
        )
        assert both.source == "cache"
        assert both.risk_score == 75

    @pytest.mark.asyncio
    async def test_llm_failure_with_object_type_estimation(
        self, ai_fallback_service: AIFallbackService
    ):
        """RETARGETED: the object-type estimate arm, with the dead Nemotron
        fixture cut out (red from S2b's ``602379e2``, not S3).

        WHAT DIED: only the ``AIService.NEMOTRON`` mutation -- shipped at
        a50aa76d, deleted by ``602379e2`` -- and the method under test never
        read it (ai_fallback.py:548-559 consumes ``object_types`` and
        ``_risk_cache`` only). The estimate arithmetic is unchanged since it
        was written.

        WHAT STILL SHIPS: the estimate arm at ai_fallback.py:548-559 --
        ``int(sum(scores) / len(scores))`` over ``RiskScoreCache.object_type_
        scores``, whose person=60 / vehicle=50 defaults at :152-165 give 55.

        NON-VACUITY: 55 is asserted, and the two arms that could masquerade as
        it are pinned apart -- the default arm yields 50 and the cache arm
        yields the stored value, both in the sibling tests. An averaging bug
        that returned the constant 50 would therefore fail HERE, not silently.
        The unknown-type default is also pinned (50 at :185) so the arithmetic
        is shown to be reading the table rather than returning a constant: an
        unknown object type alone must NOT produce 55.
        """
        # Get fallback with object types
        result = ai_fallback_service.get_fallback_risk_analysis(object_types=["person", "vehicle"])

        # Should average person (60) and vehicle (50) = 55
        assert result.risk_score == 55
        assert result.source == "object_type_estimate"
        assert result.is_fallback is True
        # Non-vacuity: an unknown type hits the table's 50 default, NOT this
        # arm's 55 -- so 55 is arithmetic over real entries, not a constant.
        unknown = ai_fallback_service.get_fallback_risk_analysis(object_types=["dragon"])
        assert unknown.risk_score == 50
        assert unknown.source == "object_type_estimate"


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
    async def test_degraded_mode_with_non_critical_service_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """RETARGETED onto the manager; the ai_fallback DEGRADED arm is dead.

        WHAT DIED: Florence-2 was this test's non-critical service, and
        ``AIService.FLORENCE`` is deleted (ruling 1) -- ai_fallback.py:7-12
        states the deletion, :57-61 is the one-member enum, :199 makes that
        member critical. With zero non-critical members, the
        ``non_critical_unavailable > 0`` branch at ai_fallback.py:472-473 can
        never fire and ``get_degradation_level()`` cannot return DEGRADED.

        WHAT STILL SHIPS (retargeted onto): DEGRADED on the LIVE ladder.
        ``DegradationManager._evaluate_mode_transition`` :544-545 returns
        DEGRADED when a NON-critical member is unhealthy and no critical one
        is. Same claim, surviving surface, and a stronger fixture than a
        hand-mutated private dict: this drives the manager's own
        register/update/evaluate path.

        NON-VACUITY: a DEGRADED result from a manager with NO registered
        services would be theatre (the branch needs total_unhealthy > 0), so
        the pin first proves the mode is NORMAL, proves the non-critical
        member is counted UNHEALTHY, and proves the critical member is still
        healthy -- i.e. the mode came from a non-critical outage specifically.
        It then proves the contrast: taking the CRITICAL member down moves the
        mode OFF the DEGRADED arm, so "degraded" is not simply what this
        manager says about everything.
        """
        manager = DegradationManager(failure_threshold=1)
        manager.register_service(
            name="analytics", health_check=AsyncMock(return_value=True), critical=False
        )
        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Populate real health first: a member nobody has checked reads
        # UNKNOWN, and asserting HEALTHY against UNKNOWN is the mistake this
        # line made on its first run -- the mode would move while the per-
        # member evidence stayed unobserved.
        await manager.run_health_checks()
        assert manager.mode == DegradationMode.NORMAL, (
            "fixture did not start clean; the DEGRADED transition below proves nothing"
        )
        assert manager.get_service_health("database").status == DegradationServiceStatus.HEALTHY

        await manager.update_service_health("analytics", is_healthy=False)

        assert manager.mode == DegradationMode.DEGRADED
        assert manager.get_service_health("analytics").status == DegradationServiceStatus.UNHEALTHY
        assert manager.get_service_health("database").status == DegradationServiceStatus.HEALTHY, (
            "a critical member is unhealthy -- this is not the non-critical arm"
        )
        assert manager.is_degraded is True

        # Contrast (non-vacuity): a critical outage leaves this arm entirely.
        await manager.update_service_health("database", is_healthy=False)
        assert manager.mode != DegradationMode.DEGRADED, (
            "critical outage still reads DEGRADED -- the critical/non-critical "
            "distinction this test pins has collapsed"
        )

        # TOMBSTONE half, against LIVE forms: the retired slugs are not enum
        # members, so this file's old fixture cannot be rebuilt by name.
        census = {m.value for m in AIService}
        assert census, "AIService is empty -- the reachability sweep below proves nothing"
        for slug in ("florence", "clip"):
            assert slug not in census
            with pytest.raises(ValueError, match=slug):
                AIService(slug)
        # And the DEGRADED arm is not merely un-driven here, it is UNREACHABLE:
        # every member is knocked over ALONE, one fresh service per member, and
        # no single-service outage yields DEGRADED.
        #
        # The per-member shape is the load-bearing part and it was chosen by
        # mutation, not by taste. The first draft of this block set EVERY
        # member to the same status and swept the statuses; run against the
        # pre-S3 tree in a throwaway worktree it PASSED, because all-down reads
        # OFFLINE there and none-down reads NORMAL -- the same way it passes
        # now. A pin that green-lights the world it claims to forbid is the
        # vacuity this repo's S2b compose lesson names. Per-member is what
        # discriminates: pre-S3, florence-alone and clip-alone each read
        # DEGRADED (measured), so this loop would have reddened then and only
        # goes green because those members are gone.
        observed: dict[str, str] = {}
        for member in AIService:
            probe = AIFallbackService(health_check_interval=1.0)
            probe._service_states[member].status = ServiceStatus.UNAVAILABLE
            observed[member.value] = probe.get_degradation_level().value
        assert observed, "AIService is empty -- the sweep below iterates nothing"
        assert set(observed.values()) == {DegradationLevel.OFFLINE.value}, (
            f"single-outage levels {observed}: the DEGRADED arm came back, which "
            "means a non-critical service is on the enum again and this test's "
            "tombstone premise is void"
        )
        # The shipped fixture this class is built on agrees with the sweep.
        assert ai_fallback_service.get_degradation_level() == DegradationLevel.NORMAL

    @pytest.mark.asyncio
    async def test_minimal_mode_with_critical_service_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """RETARGETED onto the live MINIMAL arm; this id went red in S2b
        (``602379e2``), NOT in S3, and the claim it made was live before that.

        THE MEASUREMENT, because the attribution is the whole point: this file
        ran 33/33 GREEN at ``602379e2^`` in a throwaway worktree. At that
        commit ``CRITICAL_SERVICES`` was ``{YOLO26, NEMOTRON}`` -- two members
        -- so knocking YOLO26 over was a genuine PARTIAL critical outage and
        ``get_degradation_level`` really did return MINIMAL. ``602379e2``
        deleted the NEMOTRON member and shrank the critical set to
        ``{YOLO26}`` in the same commit, which left ``critical_unavailable``
        either 0 or ``len(CRITICAL_SERVICES)`` and made the
        ``elif critical_unavailable > 0`` branch (ai_fallback.py:470-471)
        unreachable: MINIMAL is documented as "critical services PARTIALLY
        available" (:68) and a one-member set has no partial. So this id
        failed at HEAD with ``OFFLINE != MINIMAL`` for a reason that predates
        this slice, and calling it S3 collateral would bury an S2b red that
        went red ALREADY MERGED.

        WHAT DIED vs WHAT SHIPS: nothing about MINIMAL died -- it died only in
        this function's ability to EXPRESS it, because the census it needed
        (>=2 criticals) is what the deletion removed. MINIMAL ships on
        ``DegradationManager``: degradation_manager.py:546-547 returns it when
        some-but-not-all critical members are unhealthy, over a registry that
        takes as many criticals as you register. Retargeted onto that with no
        weakening -- the claim is still "one critical of several is down ->
        MINIMAL", which is exactly what this id asserted when it was green.

        NON-VACUITY: MINIMAL on a manager holding ONE critical would be a lie
        (that shape goes straight to OFFLINE -- precisely the HEAD failure
        above), so the pin proves the registry has two healthy criticals first,
        then proves three rungs are DISTINCT: NORMAL with both up, MINIMAL with
        one down, OFFLINE with both down. A manager whose mode never moved
        fails all three legs.
        """
        manager = DegradationManager(failure_threshold=1)
        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )
        manager.register_service(
            name="vlm_analyzer", health_check=AsyncMock(return_value=True), critical=True
        )
        criticals = [s for s in manager._services.values() if s.critical]
        assert len(criticals) == 2, (
            "MINIMAL needs a partial critical outage; a one-critical registry "
            "cannot express it and would make this pin the HEAD bug all over"
        )
        await manager.run_health_checks()
        assert manager.mode == DegradationMode.NORMAL

        await manager.update_service_health("database", is_healthy=False)
        assert manager.mode == DegradationMode.MINIMAL
        assert manager.get_service_health("vlm_analyzer").status == DegradationServiceStatus.HEALTHY

        # The endpoint that this file used to confuse with MINIMAL, pinned in
        # the same run so the two can never silently collapse into each other.
        await manager.update_service_health("vlm_analyzer", is_healthy=False)
        assert manager.mode == DegradationMode.OFFLINE

        # TOMBSTONE half: the ai_fallback arm stays pinned as unreachable, so a
        # reader cannot "restore" the old expectation against the wrong module.
        assert ai_fallback_service.get_degradation_level() == DegradationLevel.NORMAL
        ai_fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.UNAVAILABLE
        assert ai_fallback_service.get_degradation_level() == DegradationLevel.OFFLINE, (
            "CRITICAL_SERVICES grew a member -- re-derive the reachability claim"
        )
        assert set(CRITICAL_SERVICES) == set(AIService), (
            "a non-critical service returned to ai_fallback; MINIMAL/DEGRADED "
            "become reachable there again and this pin is stale"
        )
        assert DegradationLevel.MINIMAL.value == "minimal"
        assert DegradationLevel.DEGRADED.value == "degraded"

    @pytest.mark.asyncio
    async def test_offline_mode_with_all_critical_services_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """RETARGETED: OFFLINE is the arm that survives on BOTH surfaces; the
        dead fixture was the second critical, deleted in S2b (this id was red
        at HEAD aaf29361 on ``AIService.NEMOTRON``, green at ``602379e2^``).

        WHAT DIED: the line that marked ``AIService.NEMOTRON`` unavailable.
        That member shipped (a50aa76d) and ``602379e2`` deleted it, leaving
        one critical -- so the test could no longer name "all critical
        services", only one of them.

        WHAT STILL SHIPS: ``critical_unavailable == len(CRITICAL_SERVICES)`` ->
        OFFLINE on ai_fallback.py:468-469, and the same endpoint on the
        manager at :548-549. Both are driven here -- the ai_fallback form
        because this file's tier is the one that used it, the manager form
        because that is where a MULTI-critical OFFLINE is expressible.

        NON-VACUITY: taking down a set that is already the whole census makes
        "all critical services are down" vacuously true, so the pin proves
        ``CRITICAL_SERVICES`` non-empty, proves the level was NOT offline
        beforehand, and drives the manager's multi-critical OFFLINE as the
        independent second witness.
        """
        assert CRITICAL_SERVICES, "CRITICAL_SERVICES is empty -- the loop below is vacuous"

        assert ai_fallback_service.get_degradation_level() == DegradationLevel.NORMAL

        for service in CRITICAL_SERVICES:
            ai_fallback_service._service_states[service].status = ServiceStatus.UNAVAILABLE

        assert ai_fallback_service.get_degradation_level() == DegradationLevel.OFFLINE

        # Second witness on the LIVE multi-critical surface: all-of-N criticals
        # down must read OFFLINE, not MINIMAL (the distinction the test above
        # exists to keep honest).
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

    @pytest.mark.asyncio
    async def test_available_features_reduce_with_degradation(
        self, ai_fallback_service: AIFallbackService
    ):
        """RED FROM S2b (``602379e2``), not from S3 -- ``risk_analysis`` WAS a
        shipped feature name, and this id was green while it was.

        THE MEASUREMENT, corrected against git history rather than a reading
        of one commit: ``a50aa76d`` gave ``get_available_features`` the line
        ``features.extend(["risk_analysis", "llm_reasoning"])`` under a
        ``is_service_available(AIService.NEMOTRON)`` guard, and this file ran
        33/33 green at ``602379e2^``. ``602379e2`` deleted that line with the
        Nemotron arm -- ``git show 602379e2 -- backend/services/ai_fallback.py``
        shows the ``-`` on exactly that ``extend``. At HEAD aaf29361 the id
        then failed on ``assert "risk_analysis" in normal_features`` while
        ``image_captioning`` was still present (HEAD's list measured 11 names;
        "risk_analysis" was no longer among them). So the assertion was true
        once and S2b's deletion is what made it false -- NOT a name nobody
        ever produced, which is what an earlier draft of this docstring
        claimed, wrongly.

        WHAT DIED IN S3 (this slice): the two remaining retired arms, captions
        and re-ID (rulings 1 + 5). ai_fallback.py:477-497 now emits the
        detection pair plus the always-on trio and says why at :489-492 --
        person re-ID vectors come from the resident OSNet handle, not a
        degradation-gated flag, so no replacement arm is honest there.

        WHAT STILL SHIPS, and what this id now pins: the REDUCTION property --
        features strictly shrink as the detector goes down, and the always-on
        trio never moves. Pinned as an EXACT set on both sides, which is
        strictly stronger than the membership list it replaces. That is a
        measured claim, not a boast: I ran HEAD's 11-name list (Florence and
        CLIP still armed) through both pins -- the old membership assertions
        ACCEPTED it once their one dead line was removed, and the set equality
        REJECTED it. A resurrected or newly dropped arm cannot slip past a set
        equality.

        NON-VACUITY: an empty ``get_available_features()`` would satisfy every
        "not in" in the file, so the healthy list is proven to contain the
        detection pair before the down case is asserted, and the down case is
        proven to still contain the trio. The delta is pinned exactly, so the
        reduction is a measurement of one arm, not a collapse.
        """
        normal_features = ai_fallback_service.get_available_features()
        assert set(normal_features) == {
            "object_detection",
            "detection_alerts",
            "event_history",
            "camera_feeds",
            "system_monitoring",
        }, "the shipped feature census moved; re-derive this pin, do not re-add a name"

        ai_fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.UNAVAILABLE

        down_features = ai_fallback_service.get_available_features()
        assert set(down_features) == {"event_history", "camera_feeds", "system_monitoring"}
        assert set(normal_features) - set(down_features) == {
            "object_detection",
            "detection_alerts",
        }
        # The retired arms are ABSENT from the shipped surface, asserted against
        # the LIVE form (the emitted list) rather than a comment: prose is
        # allowed to name the dead, a returned feature name is not.
        for retired in (
            "image_captioning",
            "ocr",
            "dense_captioning",
            "entity_tracking",
            "re_identification",
            "anomaly_detection",
        ):
            assert retired not in normal_features, f"{retired} is back with no provider"


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
        """TOMBSTONE of the "Florence is down" precondition, RETARGET of the
        caption the system actually provides.

        WHAT DIED (full hazard): this test knocked Florence out of service and
        then asked for a caption, pinning "when the captioning model fails we
        still hand the UI a string". Florence-2 retired in R8 S3 under owner
        ruling 1 -- provider row, client, gateway adapter, Triton model and
        ``ai/florence`` serving dir all swept with ``git rm`` (ruling 4).
        ``AIService.FLORENCE`` is deleted, so the mutation this id opened with
        cannot be written at all any more: the enum has one member and it is
        the detector. The consequence, spelled out: there is no longer a
        captioning model that CAN be unavailable. ``get_fallback_caption``
        (ai_fallback.py:580-607) is not a degradation path -- it builds the
        string from YOLO detection labels and is the shipped captioning
        behavior, exactly as its own docstring at :586-589 states. The hazard
        this tombstone holds shut is the reverse edit: somebody "restores" the
        precondition by re-adding a FLORENCE member (or a ``should_skip_
        captions()`` gate at :629-631) so the test has something to knock
        down, and a deployment grows back a flag for a model no deployment can
        boot -- the decorative-config class this repo refuses.

        WHAT IS PINNED LIVE (the surviving half, unweakened): the caption
        string is produced with no vision-language model in the loop, in both
        shipped shapes -- camera-only and objects+camera -- and it names the
        camera. The old test asserted the camera-only shape; the objects shape
        is added rather than the old one softened.

        NON-VACUITY: ``assert "front_door" in caption`` would also pass on a
        template that ignores its input entirely, and ``len(caption) > 0``
        passes on any constant. So the two arms are pinned as DIFFERENT strings
        (the camera-only one is not the objects one), the no-argument arm is
        pinned as a third distinct value, and the caption is proven to vary
        with its arguments instead of merely being non-empty. The absence half
        is non-vacuous because the enum is proven to still carry the surviving
        member in the same assertion that rejects the retired ones.
        """
        # TOMBSTONE half -- LIVE forms only: the member is not on the enum and
        # cannot be constructed, so the old precondition is unwritable.
        with pytest.raises(ValueError, match="florence"):
            AIService("florence")
        assert "florence" not in {m.value for m in AIService}
        assert AIService.YOLO26.value in {m.value for m in AIService}, (
            "the surviving arm vanished -- the absence above is vacuous"
        )

        # RETARGETED half -- the shipped, detector-derived caption.
        camera_only = ai_fallback_service.get_fallback_caption(camera_name="front_door")
        assert "front_door" in camera_only
        assert len(camera_only) > 0

        with_objects = ai_fallback_service.get_fallback_caption(
            object_types=["person", "vehicle"], camera_name="front_door"
        )
        assert "front_door" in with_objects
        assert with_objects != camera_only, (
            "the caption ignores object_types -- the non-empty assert above proves nothing"
        )
        bare = ai_fallback_service.get_fallback_caption()
        assert bare not in {camera_only, with_objects}
        assert "front_door" not in bare

    @pytest.mark.asyncio
    async def test_system_provides_fallback_embeddings_when_clip_down(
        self, ai_fallback_service: AIFallbackService
    ):
        """TOMBSTONE of the "CLIP is down" precondition, RETARGET of the
        zero-vector contract onto the live vector width.

        WHAT DIED (full hazard): CLIP retired in R8 S3 by owner ruling 5 -- a
        prune consequence, not a separate ruling's subject: the Triton prune
        dropped ``clip``/``clip_text``, which makes a CLIP-backed deployment
        unbootable, so its ops could not register non-vacuously. Its client,
        adapter, five gateway ops, ``settings.clip_url`` and the
        /api/face-events/compare debug vertical went with it.
        ``AIService.CLIP`` is deleted, so the "mark CLIP unavailable"
        mutation this test opened with is unwritable. The hazard held shut
        here: re-adding a CLIP member, or ``should_skip_reid()``
        (deleted, ai_fallback.py:629-631), to give this test a lever would
        resurrect a service flag for a model the repository no longer ships.

        WHAT IS PINNED LIVE: the vector the fallback hands back is 512-wide
        and matches nothing. 512 is not this test's opinion -- it is
        ``backend.services.reid_service.EMBEDDING_DIMENSION``, the shipped
        OSNet-AIN x1.0 person-vector width (full swap, ledger item 20), read
        from the module that produces real vectors. Pinning the fallback
        against that constant is what keeps this an integration claim: if the
        re-ID service ever moves width and this zero vector does not, the
        fallback stops being comparable against the store's real rows, and the
        mismatch reddens HERE rather than in a similarity query. The old
        comment at :828 already said 512 was the OSNet space; it just never
        checked against the module that owns the number.

        NON-VACUITY: ``[0.0] * 512`` satisfies both original asserts by
        construction, so the width is now asserted as an EQUALITY AGAINST A
        LIVE CONSTANT (and that constant is separately pinned to 512 so it
        cannot drift to whatever the fallback happens to return), and the
        zero-vector's real contract -- it must not match a real vector -- is
        pinned by comparing it against a unit vector of the same width. A
        fallback that returned a plausible-looking nonzero vector would fail
        that leg, and a fallback of the wrong length fails the width leg.
        """
        from backend.services.reid_service import EMBEDDING_DIMENSION

        # TOMBSTONE half -- LIVE forms only.
        with pytest.raises(ValueError, match="clip"):
            AIService("clip")
        assert "clip" not in {m.value for m in AIService}
        assert not hasattr(ai_fallback_service, "should_skip_reid"), (
            "the CLIP skip gate is back; it retired with ruling 5"
        )

        # Non-vacuity on the constant itself: it must be a real, positive width
        # and the shipped one, or the equality below is an alias for itself.
        assert EMBEDDING_DIMENSION == 512
        assert EMBEDDING_DIMENSION > 0

        embedding = ai_fallback_service.get_fallback_embedding()

        assert len(embedding) == EMBEDDING_DIMENSION
        assert all(v == 0.0 for v in embedding)
        # Non-vacuity of the all-zero predicate: a same-width REAL person vector
        # is NOT all-zero, so the line above is a discrimination and not a tautology
        # about this codebase's vector space. A fallback that grew real-looking
        # values would fail that line and still pass a length check.
        unit = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)
        assert len(unit) == len(embedding)
        assert not all(v == 0.0 for v in unit), "the control vector is zero too -- no teeth"
        # And the zero vector's purpose, stated in the only form that is true of
        # it: it carries no magnitude, so it can never be the nearest neighbor of
        # anything the store holds.
        assert sum(v * v for v in embedding) == 0.0
        assert sum(v * v for v in unit) == 1.0
