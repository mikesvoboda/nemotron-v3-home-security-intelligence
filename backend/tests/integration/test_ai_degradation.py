"""Integration tests for AI service graceful degradation.

Tests the AIFallbackService and its integration with circuit breakers,
fallback strategies, and status broadcasting.

Test scenarios:
- Circuit breaker state transitions
- Fallback behavior verification
- Degradation level calculation
- WebSocket status notification
- Recovery scenario testing

R8 S3 adjudication (2026-09-30, owner rulings 1 + 5). ``ai_fallback`` is
kept-and-DEAD (zero shipped importers, ledgered flagged-not-deleted), and S3
stripped its Florence-2 and CLIP members, breaker configs, health arms, the
two ``should_skip_*`` methods that keyed on them, and the caption/re-ID arms
of ``get_available_features``. Adjudication per test below is either:

  * RETARGET -- the pinned behavior still ships (the ladder, the availability
    gate, the feature calculator, the status broadcast, ``ServiceState``
    serialization all live), so the drive moved onto the surviving service set
    with the assertion kept or strengthened (several pins moved from a
    hand-written roster to a set derived from ``AIService``); or
  * TOMBSTONE -- the behavior is genuinely gone. Id kept, hazard written out,
    absence asserted against LIVE forms only (the enum constructor raising,
    ``hasattr`` on the shipped class, the values shipped functions actually
    return) plus a NON-VACUITY pin.

Two of the ladder arms the drafted file treated as tested -- DEGRADED and
MINIMAL -- are now UNREACHABLE in ``ai_fallback``, because
``CRITICAL_SERVICES == set(AIService) == {YOLO26}``: with one service and that
service critical, "a non-critical service is down" and "critical services are
PARTIALLY down" are both unsatisfiable. The non-critical-down verdict is still
shipped, just somewhere else (``health_ai_services._calculate_overall_status``
over a table whose ai-vlm row is ``critical: False``), so it retargets there;
"critical PARTIALLY down" has no surviving owner and is tombstoned.

Cause split, MEASURED (throwaway worktree at HEAD, same runner; the 5-test CI
hint for this file was a partial census -- the real count was 14): 10 of the 14
were already red at HEAD, and every one of those 10 traces to S2b (602379e2
deleted ``AIService.NEMOTRON``, ``should_use_default_risk``, the Nemotron-keyed
``risk_analysis``/``llm_reasoning`` feature arm, and shrank
``CRITICAL_SERVICES`` to one member). Exactly 4 are S3's:
``test_degradation_level_degraded_non_critical_down``,
``test_reduced_features_when_clip_unavailable``, and the two ``should_skip_*``
pins. (``test_reduced_features_when_florence_unavailable`` is on both lists --
red at HEAD on a phantom ``risk_analysis`` assertion, red now on the retired
member.)

Two of the 14 were red at HEAD for a reason the drafted file had wrong, and the
correction is recorded where it is asserted rather than laundered: see
``test_all_features_when_all_services_healthy`` (the S2b'd LLM feature arm) and
``test_status_callback_called_on_change`` (``"minimal"`` needed two critical
services and the module had, at HEAD, one).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from itertools import product
from typing import Any

import pytest

from backend.api.routes.health_ai_services import (
    AI_SERVICES_CONFIG,
    _calculate_overall_status,
)
from backend.api.schemas.ai_services_health import (
    AIServiceHealthDetail,
    AIServiceOverallStatus,
    AIServiceStatus,
)
from backend.services.ai_fallback import (
    CRITICAL_SERVICES,
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

# The service names this file's drafted pins addressed and no shipped enum can
# name any more. nemotron: deleted in S2b (602379e2, the legacy LLM tier).
# florence / clip: deleted here, owner rulings 1 and 5.
RETIRE_SERVICE_NAMES = ("nemotron", "florence", "clip")

# Feature strings that left with those providers. Florence's captioning arm
# (image_captioning/ocr/dense_captioning) and CLIP's re-ID/anomaly arm
# (entity_tracking/re_identification/anomaly_detection) were the only emitters
# -- ai_fallback.py:489-492 records the deletion -- so they can no longer be
# emitted for ANY service state. Re-ID itself did NOT leave the product: it
# became a resident OSNet vector handle (ledger item 20), which is exactly the
# non-vacuity the two feature tombstones below pin.
RETIRED_CAPTION_FEATURES = ("image_captioning", "ocr", "dense_captioning")
RETIRED_REID_FEATURES = ("entity_tracking", "re_identification", "anomaly_detection")

# A third retired arm, found while re-measuring rather than from the CI hint:
# ``risk_analysis`` / ``llm_reasoning`` were emitted by a Nemotron-keyed arm of
# get_available_features (added in a50aa76d, deleted in S2b 602379e2 --
# ``if self.is_service_available(AIService.NEMOTRON): features.extend([...])``).
# The drafted healthy-set pin still asserts both strings, which is why it reads
# red at HEAD; the absence sweep lives in that pin.
RETIRED_LLM_FEATURES = ("risk_analysis", "llm_reasoning")


def _every_live_state_assignment() -> list[dict[AIService, ServiceStatus]]:
    """Every combination of the LIVE service set x the LIVE status set.

    Derived from ``AIService`` and ``ServiceStatus``, never hand-written, so an
    absence pin built on it stays honest as the enum shrinks or grows (one
    member today -> 3 combinations; two members -> 9). The census is what lets
    these pins say "no state can produce X" instead of "the one state I picked
    did not produce X".
    """
    members = list(AIService)
    assert members, "AIService has no members: every census over it is vacuous"
    return [
        dict(zip(members, combo, strict=True))
        for combo in product(tuple(ServiceStatus), repeat=len(members))
    ]


def _service_in_state(assignment: dict[AIService, ServiceStatus]) -> AIFallbackService:
    """A fresh service with ``assignment`` written into its own state table."""
    service = AIFallbackService(health_check_interval=1.0)
    for member, status in assignment.items():
        service._service_states[member].status = status
    return service


def _state_key(assignment: dict[AIService, ServiceStatus]) -> dict[str, str]:
    return {member.value: status.value for member, status in assignment.items()}


def _feature_output_for_every_live_state() -> list[tuple[dict[str, str], list[str]]]:
    """``(state-as-names, get_available_features())`` for every live state."""
    return [
        (_state_key(assignment), _service_in_state(assignment).get_available_features())
        for assignment in _every_live_state_assignment()
    ]


def _ladder_output_for_every_live_state() -> list[tuple[dict[str, str], DegradationLevel]]:
    """``(state-as-names, get_degradation_level())`` for every live state."""
    return [
        (_state_key(assignment), _service_in_state(assignment).get_degradation_level())
        for assignment in _every_live_state_assignment()
    ]


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
def circuit_breaker_yolo26() -> CircuitBreaker:
    """Create a circuit breaker for YOLO26 testing."""
    return CircuitBreaker(
        name="yolo26_test",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,  # Short timeout for testing
            half_open_max_calls=2,
            success_threshold=2,
        ),
    )


async def _open_breaker(
    service: AIFallbackService,
    breaker: CircuitBreaker,
    target: AIService = AIService.YOLO26,
) -> None:
    """Trip ``breaker`` open, register it on ``target``, and let the shipped
    health check read it back into the service's state table.

    This is the LIVE route to an unavailable service: the shipped code derives
    status from the circuit state (ai_fallback.py:371-372), so driving the
    breaker is what makes an "unavailable" fixture real. The alternative --
    writing ``status`` by hand -- is what the drafted pins did, and it is how
    three of them ended up asserting a degradation tier no shipped state can
    reach: a hand-written status can name a service that no longer exists and
    a level no combination produces.
    """
    service.register_circuit_breaker(target, breaker)
    for _ in range(breaker.config.failure_threshold):
        try:
            async with breaker:
                raise RuntimeError("simulated failure")
        except Exception:
            # The injected failure (and any CircuitOpenError on re-entry) is
            # expected; the state it produces is asserted immediately below.
            pass
    assert breaker.get_state() is CircuitState.OPEN, (
        "the breaker did not open; every unavailable-tier assertion downstream "
        "would then be reading a closed circuit"
    )
    await service._check_service_health(target)


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
        """RETARGET. The drafted pin asked about four services -- yolo26,
        nemotron, florence, clip. Only one of those names resolves any more, so
        the drive is now DERIVED from ``AIService``: a future retirement cannot
        slip past this pin by dropping a member, because the roster is the enum.

        Three status tiers are pinned, not one. ``is_service_available`` is
        ``status != UNAVAILABLE`` (ai_fallback.py:436), so DEGRADED (a half-open
        breaker) is AVAILABLE and only UNAVAILABLE is not -- pinning all three
        is what makes "healthy -> True" mean something, since a stub returning
        True for everything would pass the healthy tier alone and fail the
        unavailable one.
        """
        live = list(AIService)
        assert live, "AIService is empty; the loop below would prove nothing"

        for member in live:
            ai_fallback_service._service_states[member].status = ServiceStatus.HEALTHY
            assert ai_fallback_service.is_service_available(member) is True, member

        for member in live:
            ai_fallback_service._service_states[member].status = ServiceStatus.DEGRADED
            assert ai_fallback_service.is_service_available(member) is True, member

        for member in live:
            ai_fallback_service._service_states[member].status = ServiceStatus.UNAVAILABLE
            assert ai_fallback_service.is_service_available(member) is False, member

    def test_is_service_available_accepts_string(self, ai_fallback_service: AIFallbackService):
        """RETARGET. The drafted pin checked ``"yolo26"`` and ``"nemotron"``.
        The live claim is the string->enum coercion at ai_fallback.py:432-433,
        so it is pinned as PARITY between the two spellings across the status
        tiers -- parity is only non-vacuous because one of the rows is False.

        The three names the drafted pin passed are pinned as UNNAMEABLE here:
        nemotron died in S2b, florence and clip die here (owner rulings 1 and
        5), and a caller holding one of those strings now gets a ``ValueError``
        out of ``AIService(...)`` instead of a silently-healthy verdict for a
        service no deployment can boot.
        """
        live = list(AIService)
        assert live, "AIService is empty; the loop below would prove nothing"

        for status in (ServiceStatus.HEALTHY, ServiceStatus.UNAVAILABLE):
            for member in live:
                ai_fallback_service._service_states[member].status = status
                assert ai_fallback_service.is_service_available(
                    member.value
                ) is ai_fallback_service.is_service_available(member), (member, status)

        assert {m.value for m in live} == {"yolo26"}, (
            "the live service set changed; the retired-name pin below needs re-reading"
        )
        for dead_name in RETIRE_SERVICE_NAMES:
            with pytest.raises(ValueError, match="not a valid AIService"):
                ai_fallback_service.is_service_available(dead_name)
        # Non-vacuity: the coercion path itself is still exercised above (it is
        # how the parity rows pass), and the enum still has a member to coerce
        # to -- a raise for EVERY string would also "pass" the loop above.
        assert AIService("yolo26") is AIService.YOLO26


class TestCircuitBreakerIntegration:
    """Test integration with circuit breakers."""

    def test_register_circuit_breaker(
        self,
        ai_fallback_service: AIFallbackService,
        circuit_breaker_yolo26: CircuitBreaker,
    ):
        """Test registering a circuit breaker for a service."""
        ai_fallback_service.register_circuit_breaker(AIService.YOLO26, circuit_breaker_yolo26)

        # Should be registered without error
        state = ai_fallback_service.get_service_state(AIService.YOLO26)
        assert state is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_marks_service_unavailable(
        self,
        ai_fallback_service: AIFallbackService,
        circuit_breaker_yolo26: CircuitBreaker,
    ):
        """Test that an open circuit breaker marks the service as unavailable."""
        ai_fallback_service.register_circuit_breaker(AIService.YOLO26, circuit_breaker_yolo26)

        # Simulate failures to open the circuit
        for _ in range(3):
            try:
                async with circuit_breaker_yolo26:
                    raise Exception("Simulated failure")
            except Exception:
                pass

        assert circuit_breaker_yolo26.get_state() == CircuitState.OPEN

        # Check service health (manually trigger since we didn't start background task)
        await ai_fallback_service._check_service_health(AIService.YOLO26)

        state = ai_fallback_service.get_service_state(AIService.YOLO26)
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
            name="yolo26_half_open_test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=0.1,  # Very short timeout
                half_open_max_calls=2,
                success_threshold=2,
            ),
        )
        ai_fallback_service.register_circuit_breaker(AIService.YOLO26, cb)

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

        await ai_fallback_service._check_service_health(AIService.YOLO26)

        state = ai_fallback_service.get_service_state(AIService.YOLO26)
        assert state.status == ServiceStatus.DEGRADED
        assert state.circuit_state == CircuitState.HALF_OPEN


class TestDegradationLevels:
    """Test degradation level calculations."""

    @pytest.mark.asyncio
    async def test_degradation_level_degraded_non_critical_down(
        self,
        ai_fallback_service: AIFallbackService,
    ):
        """RETARGET -- the VERDICT survives, the CALCULATOR that produced it
        does not.

        The drafted pin drove ``AIService.FLORENCE`` to UNAVAILABLE and expected
        DEGRADED. Florence's member is deleted (owner ruling 1) and CLIP's with
        it (ruling 5), and those two were the only non-critical rows: with
        ``CRITICAL_SERVICES == set(AIService) == {YOLO26}`` (ai_fallback.py:199
        and :57-60) the ``non_critical_unavailable > 0`` arm at :472-473 can no
        longer be reached, which the derived census below pins rather than
        asserts in prose.

        "One non-critical AI service is down, so the subsystem is degraded but
        functional" is still SHIPPED behavior -- it is produced by
        ``_calculate_overall_status`` over ``AI_SERVICES_CONFIG``, whose ai-vlm
        row carries ``critical: False`` (health_ai_services.py:58-70, :346-361).
        The drive moves there. The assertion is not weakened: it checks the
        exact verdict for the exact fixture AND that the fixture's service is
        non-critical in the shipped table, so the row that makes DEGRADED
        possible cannot be silently flipped to critical (which would turn this
        into a CRITICAL pin wearing a DEGRADED name).
        """
        non_critical = {c["name"] for c in AI_SERVICES_CONFIG if not c.get("critical", False)}
        critical = {c["name"] for c in AI_SERVICES_CONFIG if c.get("critical", False)}
        assert non_critical, (
            "no non-critical row survives in AI_SERVICES_CONFIG, so the degraded "
            "tier has no fixture here and this pin must be re-adjudicated"
        )

        def _all_healthy() -> dict[str, AIServiceHealthDetail]:
            return {
                cfg["name"]: AIServiceHealthDetail(status=AIServiceStatus.HEALTHY)
                for cfg in AI_SERVICES_CONFIG
            }

        def _with_down(name: str) -> dict[str, AIServiceHealthDetail]:
            health = _all_healthy()
            health[name].status = AIServiceStatus.UNHEALTHY
            return health

        # The all-healthy table reads HEALTHY. Without this row the DEGRADED
        # assertions below could be produced by a fixture that was never healthy.
        assert (
            _calculate_overall_status(_all_healthy(), AI_SERVICES_CONFIG)
            is AIServiceOverallStatus.HEALTHY
        )
        for down in sorted(non_critical):
            assert _calculate_overall_status(_with_down(down), AI_SERVICES_CONFIG) is (
                AIServiceOverallStatus.DEGRADED
            ), down
        # ... and a CRITICAL row going down reads differently, so the
        # non-critical branch is not just "any row down -> DEGRADED".
        for down in sorted(critical):
            assert _calculate_overall_status(_with_down(down), AI_SERVICES_CONFIG) is (
                AIServiceOverallStatus.CRITICAL
            ), down

        # Hazard left behind, pinned as absence: inside ai_fallback the DEGRADED
        # arm is now dead code. No live service assignment yields it.
        degraded_states = [
            state
            for state, level in _ladder_output_for_every_live_state()
            if level is DegradationLevel.DEGRADED
        ]
        assert degraded_states == [], degraded_states
        assert ai_fallback_service.get_degradation_level() is DegradationLevel.NORMAL

    @pytest.mark.asyncio
    async def test_degradation_level_minimal_critical_partially_down(
        self,
        ai_fallback_service: AIFallbackService,
    ):
        """TOMBSTONE -- this one has NO surviving owner; nothing was lost that
        still ships.

        What used to be true: the drafted pin marked ``AIService.YOLO26``
        UNAVAILABLE and asserted MINIMAL. It could do that only because a
        SECOND critical service existed --
        ``CRITICAL_SERVICES == {YOLO26, NEMOTRON}``. With two critical rows,
        "one of the two criticals is down" is a real middle state: the analyzer
        is gone but detection still runs, so the system is minimal rather than
        offline. That was true from the file's first commit through S2b.

        Why it died, in two steps, and only the second is this slice:
          * S2b (602379e2) deleted ``AIService.NEMOTRON`` and shrank
            ``CRITICAL_SERVICES`` to ``{YOLO26}``. The pin has been red at HEAD
            ever since -- measured, not guessed: at HEAD it fails as
            ``AssertionError: 'offline' == 'minimal'``, because yolo26 going
            down is now ALL of the criticals going down. The drafted drive is
            still a legal call (it names a surviving member), which is exactly
            why this arm could rot unnoticed: nothing raises, the verdict just
            silently moved a tier.
          * S3 (owner rulings 1 + 5) deleted ``FLORENCE`` and ``CLIP``, so
            ``set(AIService) == CRITICAL_SERVICES == {YOLO26}``. "Critical
            services PARTIALLY down" is now unsatisfiable as a matter of set
            arithmetic: the arm ``0 < critical_unavailable < len(CRITICAL_
            SERVICES)`` (ai_fallback.py:468-471) needs a critical set with at
            least two members, and there is one.

        The hazard, written out because it is the general one: an enum-keyed
        severity table silently degrades into a two-state switch when its key
        set shrinks to one member, and ``DegradationLevel`` keeps four members
        that the calculator can no longer all emit. A reader who checks that
        the ENUM still has MINIMAL (or that the level tests still exist) has
        verified nothing -- the pin has to be the output census below.

        Asserted against LIVE forms: the shipped ``CRITICAL_SERVICES`` /
        ``AIService`` sets, and the level the shipped function actually returns
        for every state it can be put in. Non-vacuity is the hard half: this
        class's sibling arms still prove the ladder EMITS real verdicts, so
        "MINIMAL is missing" is a retirement, not an empty table.
        """
        # (a) the arithmetic that killed it, pinned rather than described.
        assert set(AIService) == set(CRITICAL_SERVICES), (
            "a non-critical live service came back -- the DEGRADED arm is "
            "reachable again and this tombstone must be re-adjudicated"
        )
        assert len(CRITICAL_SERVICES) == 1, CRITICAL_SERVICES

        # (b) absence over the derived census: MINIMAL is emitted by NO live
        # state assignment.
        output = _ladder_output_for_every_live_state()
        assert len(output) == len(ServiceStatus) ** len(AIService) > 1, (
            f"census collapsed to {len(output)} entries: an absence over it is vacuous"
        )
        emitted = {level for _, level in output}
        assert DegradationLevel.MINIMAL not in emitted, output
        assert DegradationLevel.DEGRADED not in emitted, output

        # (c) NON-VACUITY: the calculator is not dead, the enum is not a stub,
        # and the drafted drive is still an input the service accepts. If
        # ``get_degradation_level`` were broken to always return NORMAL, or the
        # level enum had been trimmed to the reachable pair, both absence pins
        # above would pass -- the two rows below are what refuse that.
        assert output[0][1] is DegradationLevel.NORMAL
        assert output[-1][1] is DegradationLevel.OFFLINE, (
            "all-critical-down stopped producing a verdict; the census above is "
            "then an absence over a dead function, not a retirement"
        )
        assert set(DegradationLevel) == {"normal", "degraded", "minimal", "offline"}
        # The drafted drive is still a legal input and still produces a verdict
        # -- it just lands on OFFLINE now. If a second critical service is ever
        # added, this row turns MINIMAL and fails, which is the re-adjudication
        # tripwire for this tombstone.
        ai_fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.UNAVAILABLE
        assert ai_fallback_service.get_degradation_level() is DegradationLevel.OFFLINE

    @pytest.mark.asyncio
    async def test_degradation_level_offline_all_critical_down(
        self,
        ai_fallback_service: AIFallbackService,
    ):
        """RETARGET. The drafted pin hand-wrote two rows -- YOLO26 and
        NEMOTRON -- and Nemotron's member died in S2b, which is why this was
        already red at HEAD.

        The claim ("every critical service down -> OFFLINE") is LIVE and is now
        stated as a DERIVED biconditional over the census: OFFLINE is emitted
        exactly when every member of ``CRITICAL_SERVICES`` is UNAVAILABLE, and
        never otherwise. The drafted version could not say the second half, and
        a hand-written fixture list cannot drift from a table derived from the
        enum.
        """
        output = _ladder_output_for_every_live_state()
        assert len(output) > 1, f"census is only {len(output)} entries -- proves nothing"
        critical_names = {c.value for c in CRITICAL_SERVICES}

        for state, level in output:
            all_critical_down = all(
                state[n] == ServiceStatus.UNAVAILABLE.value for n in critical_names
            )
            assert (level is DegradationLevel.OFFLINE) is all_critical_down, (
                f"{state} -> {level!r}: OFFLINE must be emitted exactly when every "
                f"critical service is unavailable"
            )

        # The drafted drive, restated on the live set and still red-lining.
        for member in AIService:
            ai_fallback_service._service_states[member].status = ServiceStatus.UNAVAILABLE
        assert ai_fallback_service.get_degradation_level() is DegradationLevel.OFFLINE
        # Non-vacuity: OFFLINE is a DIFFERENT verdict from the one the same
        # service reports when it is merely degraded (the half-open tier), so
        # this arm cannot be satisfied by a calculator that ignores state.
        degraded_tier = _service_in_state(dict.fromkeys(AIService, ServiceStatus.DEGRADED))
        assert degraded_tier.get_degradation_level() is DegradationLevel.NORMAL


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

        # 512 dims — the OSNet-AIN x1.0 space (full swap, ledger item 20).
        assert len(embedding) == 512
        assert all(v == 0.0 for v in embedding)


class TestServiceAvailabilityChecks:
    """Test convenience methods for checking service availability."""

    def test_should_skip_detection_when_yolo26_unavailable(
        self, ai_fallback_service: AIFallbackService
    ):
        """Test detection skip flag when YOLO26 is unavailable."""
        # Initially should not skip
        assert ai_fallback_service.should_skip_detection() is False

        # Mark as unavailable
        ai_fallback_service._service_states[AIService.YOLO26].status = ServiceStatus.UNAVAILABLE

        assert ai_fallback_service.should_skip_detection() is True

    def test_should_use_default_risk_when_nemotron_unavailable(
        self, ai_fallback_service: AIFallbackService
    ):
        """TOMBSTONE (S2b, red here at HEAD -- not S3's, measured).

        What used to be true: ``should_use_default_risk()`` returned
        ``not is_service_available(AIService.NEMOTRON)`` (pre-602379e2,
        ai_fallback.py:662-670), so a caller could ask "is the analyzer down
        enough that I should publish a default risk score instead of waiting?"
        and get a per-service answer that tracked the Nemotron circuit breaker.

        Why it died: S2b deleted the legacy LLM tier -- the Nemotron member,
        its breaker config and this method with it. The verdict it produced did
        NOT die: ``get_fallback_risk_analysis`` still ships and still reports
        where its number came from (``source`` = cache / object_type_estimate /
        default), which is the live form asserted in
        ``TestFallbackBehavior`` above and re-read from the shipped instance
        below.

        The hazard: a "should I use the fallback?" boolean keyed on one service
        is the same information the fallback function already carries in its
        ``source`` field -- the boolean was a second, drift-prone spelling of it.
        Its absence must therefore be pinned next to the survival of the thing
        it gated, or a later reader cannot tell retirement from loss.

        Vacuity would come from ``AIFallbackService`` having been deleted or
        renamed wholesale (then every ``hasattr`` check passes), so the last
        block pins that the class is alive and its sibling arm still works.
        """
        assert not hasattr(ai_fallback_service, "should_use_default_risk")
        assert "nemotron" not in {m.value for m in AIService}
        # Non-vacuity: the service and the gated behavior are alive -- a dead
        # or renamed class would make the hasattr above vacuous.
        assert hasattr(ai_fallback_service, "should_skip_detection")
        assert hasattr(ai_fallback_service, "get_fallback_risk_analysis")
        assert ai_fallback_service.get_fallback_risk_analysis().source == "default"
        ai_fallback_service.cache_risk_score("tombstone_camera", 71)
        assert (
            ai_fallback_service.get_fallback_risk_analysis(camera_name="tombstone_camera").source
            == "cache"
        )

    def test_should_skip_captions_when_florence_unavailable(
        self, ai_fallback_service: AIFallbackService
    ):
        """TOMBSTONE (R8 S3, owner ruling 1).

        What used to be true: ``should_skip_captions()`` returned
        ``not is_service_available(AIService.FLORENCE)``, and a pipeline stage
        could ask it before spending a call on Florence-2 captioning.

        Why it died: ruling 1 retires the Florence provider outright --
        provider row, client, adapter, serving dir, Triton dir (ledgered in
        ``test_r8_s3_florence_provider_retirement.py``). The enum member it
        keyed on is deleted, and there is no captioning model left to be
        unavailable, so there is nothing left for a skip flag to skip. This is
        the "legacy-reachable, NOT VLM-reachable" case in the S3 scope census:
        the shipped VLM path never called Florence, so the gate had no live
        caller to re-point at a replacement.

        The hazard, and the part that is NOT gone: captions themselves still
        ship, built from YOLO detections (``get_fallback_caption`` -- renamed in
        intent by the S3 source comment at ai_fallback.py:585-589: since there
        is no captioning model, that string IS the caption, not a degradation).
        A pin that only asserted "the method is gone" would therefore also pass
        in a world where captioning itself was deleted, which would be a
        regression this file would bless. So the live caption output is pinned
        alongside the absence.

        Vacuity would come from the whole class being deleted or renamed (then
        ``hasattr`` is trivially false), hence the class-alive and sibling-arm
        assertions at the end.
        """
        # (a) absence against LIVE forms: the attribute on the shipped class,
        # and the enum member it keyed on, by constructor rather than by prose.
        assert not hasattr(ai_fallback_service, "should_skip_captions")
        with pytest.raises(ValueError, match="not a valid AIService"):
            AIService("florence")
        assert "florence" not in {m.value for m in AIService}
        # (b) the caption surface that replaced the degradation is live and
        # produces real text for every state -- not a stub returning "".
        caption = ai_fallback_service.get_fallback_caption(
            object_types=["person"], camera_name="front_door"
        )
        assert caption == "Person detected at front_door", caption
        assert ai_fallback_service.get_fallback_caption() == "Activity detected"
        # (c) NON-VACUITY: the class is alive with its surviving sibling arm,
        # so (a) is a retirement of one method, not the death of the file.
        assert hasattr(ai_fallback_service, "should_skip_detection")
        assert ai_fallback_service.should_skip_detection() is False
        assert not hasattr(ai_fallback_service, "should_skip_reid")

    def test_should_skip_reid_when_clip_unavailable(self, ai_fallback_service: AIFallbackService):
        """TOMBSTONE (R8 S3, owner ruling 5 -- CLIP retires as a PRUNE
        consequence: its Triton models were pruned, so its gateway ops could not
        register non-vacuously).

        What used to be true: ``should_skip_reid()`` returned
        ``not is_service_available(AIService.CLIP)`` -- a per-call gate on
        CLIP-embedding re-identification.

        Why it died: ruling 5. And note what did NOT die, which is the whole
        point of pinning it: person re-ID is still in the product, it just
        stopped being a *degradation-gated service call*. It is a resident OSNet
        vector handle (ledger item 20; ``get_fallback_embedding`` returns a
        512-dim vector in that space, ai_fallback.py:609-619), and the light
        lane's ``enrich_lt_person_reid`` op stays registered because ``reid`` is
        a KEPT model. Deleting this boolean must not be read as "re-ID went
        away", and a pin that cannot tell those two worlds apart is worthless.

        Vacuity would come from the service class vanishing, or from
        ``get_fallback_embedding`` having been trimmed to ``[]`` -- both are
        refused below.
        """
        assert not hasattr(ai_fallback_service, "should_skip_reid")
        with pytest.raises(ValueError, match="not a valid AIService"):
            AIService("clip")
        assert "clip" not in {m.value for m in AIService}
        # The gated capability survives, in the OSNet space: a 512-dim zero
        # vector, NOT a 768-dim CLIP-era stub (which could never have been
        # compared against anything the store holds anyway).
        embedding = ai_fallback_service.get_fallback_embedding()
        assert len(embedding) == 512 and all(v == 0.0 for v in embedding)
        # NON-VACUITY: sibling arms alive + the caption sibling, so the two
        # hasattr absences above are one method's retirement, not a dead class.
        assert hasattr(ai_fallback_service, "should_skip_detection")
        assert hasattr(ai_fallback_service, "get_fallback_caption")


class TestAvailableFeatures:
    """Test available features calculation."""

    def test_all_features_when_all_services_healthy(self, ai_fallback_service: AIFallbackService):
        """RETARGET -- and read the "what was wrong here before me" block,
        because two of this pin's six "critical features" never shipped.

        Live half: detection plus the always-available trio. That half is now
        pinned as a SET EQUALITY rather than six membership checks -- a
        membership list can quietly rot (see below) where an equality cannot.

        Pre-existing red, NOT S3's, and a tombstone of an EARLIER slice: the
        drafted pin also asserted ``"risk_analysis"`` and ``"llm_reasoning"``.
        Both strings DID ship -- a50aa76d added a Nemotron-keyed arm
        ``if self.is_service_available(AIService.NEMOTRON): features.extend(
        ["risk_analysis", "llm_reasoning"])``, which is also why this pin
        passed for so long. S2b (602379e2) deleted the legacy LLM tier, the
        Nemotron member and that arm together, and the pin has been red at HEAD
        ever since. The absence is therefore pinned below, not dropped: risk
        scoring itself did NOT leave the product (``get_fallback_risk_analysis``
        and the ai-vlm verdict engine are live), so "no feature string named
        risk_analysis" is a naming retirement and must not be read as "the
        system stopped scoring risk".

        S3 half: ``image_captioning`` and ``entity_tracking`` WERE real at HEAD
        and are gone with Florence (ruling 1) and CLIP (ruling 5); their
        absence is pinned across every live state in the two sibling tests, so
        it is asserted here only as part of the exact healthy set.
        """
        assert ai_fallback_service.get_degradation_level() is DegradationLevel.NORMAL
        assert set(ai_fallback_service.get_available_features()) == {
            "object_detection",
            "detection_alerts",
            "event_history",
            "camera_feeds",
            "system_monitoring",
        }, ai_fallback_service.get_available_features()

        # TOMBSTONE (S2b) for the LLM arm, swept over EVERY live state rather
        # than just the healthy one. Vacuity would be a calculator frozen to
        # ``[]`` -- refused by the equality above, which pins five strings the
        # healthy state really does emit, and by the risk-score read below.
        for _state, features in _feature_output_for_every_live_state():
            for name in RETIRED_LLM_FEATURES:
                assert name not in features, f"{_state} still emits {name}"
        # What replaced the arm is live: a risk number still comes back, and the
        # verdict engine has a health row.
        assert ai_fallback_service.get_fallback_risk_analysis().risk_score == 50
        assert "ai-vlm" in {c["name"] for c in AI_SERVICES_CONFIG}

    def test_reduced_features_when_florence_unavailable(
        self, ai_fallback_service: AIFallbackService
    ):
        """TOMBSTONE (R8 S3, owner ruling 1), rebuilt as a CENSUS.

        What used to be true: putting Florence-2's row UNAVAILABLE removed
        ``image_captioning`` / ``ocr`` / ``dense_captioning`` from
        ``get_available_features()`` while leaving detection and the
        always-available trio intact. Florence was one of two non-critical rows,
        so this was the "one optional service down" degradation a user could
        actually observe.

        Why it died: ruling 1 retires the Florence provider and, with the
        member, the whole caption arm (ai_fallback.py:489-492 records the
        deletion). There is no row left to put UNAVAILABLE, and no code path
        that can emit those three strings for ANY state.

        That is why the pin moved from "flip one row, check three strings" to a
        census over every combination ``AIService`` x ``ServiceStatus`` can
        build: the claim is now the stronger one -- *no* live state emits a
        caption string, not *this* state doesn't. It also survives the next
        retirement instead of dying with it.

        Non-vacuity, stated and pinned: this test would pass vacuously if
        ``get_available_features`` returned ``[]`` always, or if the census ran
        over zero states. Both are refused -- the census has more than one entry
        and every entry still carries the always-available trio, and the
        detection arm is proved to be state-dependent (present healthy, absent
        unavailable), so the function demonstrably reacts to state while never
        producing the retired strings.
        """
        corpus = _feature_output_for_every_live_state()
        assert len(corpus) > 1, f"census is only {len(corpus)} entries -- proves nothing"

        always = {"event_history", "camera_feeds", "system_monitoring"}
        for state, features in corpus:
            for name in RETIRED_CAPTION_FEATURES:
                assert name not in features, f"{state} still emits {name}"
            assert always <= set(features), (state, features)

        # The calculator still reacts to state (so "absence" is not the same
        # thing as "dead"), and the drafted pin's surviving assertions hold.
        healthy = _service_in_state(dict.fromkeys(AIService, ServiceStatus.HEALTHY))
        down = _service_in_state(dict.fromkeys(AIService, ServiceStatus.UNAVAILABLE))
        assert "object_detection" in healthy.get_available_features()
        assert "object_detection" not in down.get_available_features()
        # Non-vacuity in the other direction: the retired strings are not
        # merely absent from this module's reach -- the names this file reads
        # are still the shipped ones.
        assert RETIRED_CAPTION_FEATURES == ("image_captioning", "ocr", "dense_captioning")

    def test_reduced_features_when_clip_unavailable(self, ai_fallback_service: AIFallbackService):
        """TOMBSTONE (R8 S3, owner ruling 5), rebuilt as a census.

        What used to be true: CLIP's row going UNAVAILABLE dropped
        ``entity_tracking`` / ``re_identification`` / ``anomaly_detection``,
        while captioning and detection stayed -- the two optional arms were
        independent, which the drafted pin's final line ("``image_captioning``
        in features") was there to prove.

        Why it died: ruling 5 retires CLIP as a prune consequence, taking the
        member and the arm with it.

        The trap this version refuses: re-ID as a CAPABILITY is alive. Person
        re-ID vectors are a resident OSNet handle (ledger item 20) and the
        light lane keeps serving ``enrich_lt_person_reid`` because ``reid`` is a
        kept model. Absence from THIS list is not "re-ID was deleted" -- and the
        non-vacuity block below is what keeps that reading honest: the feature
        calculator is shown to still respond to service state, and the sibling
        caption/re-ID surface in ``TestFallbackBehavior`` is still driven.

        Vacuity would come from an empty census or a calculator frozen to a
        constant; both are refused exactly as in the sibling test.
        """
        corpus = _feature_output_for_every_live_state()
        assert len(corpus) > 1, f"census is only {len(corpus)} entries -- proves nothing"

        always = {"event_history", "camera_feeds", "system_monitoring"}
        for state, features in corpus:
            for name in RETIRED_REID_FEATURES:
                assert name not in features, f"{state} still emits {name}"
            assert always <= set(features), (state, features)

        healthy = _service_in_state(dict.fromkeys(AIService, ServiceStatus.HEALTHY))
        down = _service_in_state(dict.fromkeys(AIService, ServiceStatus.UNAVAILABLE))
        assert "object_detection" in healthy.get_available_features()
        assert "object_detection" not in down.get_available_features()
        # The drafted pin's cross-arm check, restated against a live arm:
        # killing detection does not touch the always-available trio, so the
        # two arms are still independently gated.
        assert always <= set(down.get_available_features())
        assert RETIRED_REID_FEATURES == (
            "entity_tracking",
            "re_identification",
            "anomaly_detection",
        )


class TestStatusBroadcasting:
    """Test WebSocket status broadcasting."""

    @pytest.mark.asyncio
    async def test_status_callback_called_on_change(
        self,
        ai_fallback_service: AIFallbackService,
        circuit_breaker_yolo26: CircuitBreaker,
    ):
        """RETARGET (red at HEAD, not S3's -- ``"minimal"`` was never true).

        The broadcast itself is live and fully pinned: the registered callback
        receives the status dict, and its three top-level keys carry the level,
        the per-service rows and the feature list.

        What was fixed rather than weakened: the drafted pin asserted
        ``degradation_mode == "minimal"`` and hand-wrote YOLO26's status, but
        MINIMAL needs TWO critical services and this module's entire service
        set is yolo26 -- that literal has been false since S2b shrank
        ``CRITICAL_SERVICES`` to one member, and the pin was red at HEAD. The
        fixture now goes through a real circuit breaker (the shipped route to
        "unavailable") and the expected mode is read from the shipped calculator
        as well as pinned by name, so the two cannot drift apart silently.
        """
        callback_called = asyncio.Event()
        received_status: dict[str, Any] = {}

        async def status_callback(status: dict[str, Any]):
            nonlocal received_status
            received_status = status
            callback_called.set()

        ai_fallback_service.register_status_callback(status_callback)

        # Trigger the broadcast with the detector's breaker OPEN -- the tier the
        # shipped path actually reaches (ai_fallback.py:371-372).
        await _open_breaker(ai_fallback_service, circuit_breaker_yolo26)

        await ai_fallback_service._notify_status_change()

        # Wait for callback
        await asyncio.wait_for(callback_called.wait(), timeout=1.0)

        assert "degradation_mode" in received_status
        assert "services" in received_status
        assert "available_features" in received_status
        # ``"minimal"`` was the drafted expectation and was NEVER true: it
        # needed two critical services, and ai_fallback's whole service set is
        # yolo26 -- the pin has been red since S2b shrank CRITICAL_SERVICES,
        # including at HEAD. ``get_degradation_level`` is read from the shipped
        # service here rather than hard-coded again, so this row cannot rot the
        # way the literal did; the exact verdict is still pinned by name.
        assert received_status["degradation_mode"] == "offline"
        assert received_status["degradation_mode"] == (
            ai_fallback_service.get_degradation_level().value
        )
        # Non-vacuity, two ways. (1) The fixture is a real breaker that really
        # transitioned -- a stub breaker frozen CLOSED would make the mode above
        # "normal" and the detection arm below trivially present. (2) The
        # broadcast is not a constant: it mirrors the service's own level, and
        # the detection feature disappears from the payload with the detector.
        assert circuit_breaker_yolo26.get_state() is CircuitState.OPEN
        assert received_status["services"][AIService.YOLO26.value]["status"] == "unavailable"
        assert "object_detection" not in received_status["available_features"]

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
            service=AIService.YOLO26,
            status=ServiceStatus.HEALTHY,
            circuit_state=CircuitState.CLOSED,
            last_success=now,
            failure_count=0,
            error_message=None,
            last_check=now,
        )

        result = state.to_dict()

        assert result["service"] == "yolo26"
        assert result["status"] == "healthy"
        assert result["circuit_state"] == "closed"
        assert result["failure_count"] == 0
        assert result["error_message"] is None

    def test_to_dict_with_error(self):
        """RETARGET (red at HEAD -- Nemotron's member died in S2b, not here).

        The pinned behavior is fully live: a service in the unavailable tier
        still serializes its error text, failure count and OPEN circuit for the
        degradation feed (ai_fallback.py:102-112), which is what an operator
        actually sees when the detector falls over. Only the SERVICE NAME in the
        fixture was dead, so the fixture is derived from ``AIService`` and the
        serialized key set is pinned exactly -- a payload schema drifting from
        what the status endpoint hands out is the thing this class exists to
        catch, and a membership-style check cannot see an EXTRA key.
        """
        state = ServiceState(
            service=AIService.YOLO26,
            status=ServiceStatus.UNAVAILABLE,
            circuit_state=CircuitState.OPEN,
            failure_count=5,
            error_message="Connection refused",
        )

        result = state.to_dict()

        assert result["service"] == "yolo26"
        assert result["status"] == "unavailable"
        assert result["circuit_state"] == "open"
        assert result["failure_count"] == 5
        assert result["error_message"] == "Connection refused"
        assert result["last_success"] is None
        assert result["last_check"] is None
        assert set(result) == {
            "service",
            "status",
            "circuit_state",
            "last_success",
            "failure_count",
            "error_message",
            "last_check",
        }, sorted(result)
        # Non-vacuity: the service field carries the ENUM's value, so a retired
        # name can never reappear in a serialized row -- and the fixture is the
        # live enum, not a string someone remembered.
        assert result["service"] == AIService.YOLO26.value
        assert {m.value for m in AIService} == {result["service"]}


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
        """RETARGET (red at HEAD on the ``nemotron`` row; S3 took the other
        two).

        The rollup is LIVE -- ``get_degradation_status`` still composes the
        per-service rows, the level and the feature list (ai_fallback.py:499-
        512) -- so the service roster is pinned as a SET EQUALITY against the
        enum and each row's payload schema is pinned exactly. An equality
        retires the dead names and pins the surviving set in the same move; the
        drafted four ``in`` checks could do neither (they passed for a row that
        should not be there and said nothing about the row's contents).
        """
        status = ai_fallback_service.get_degradation_status()

        assert set(status) == {"timestamp", "degradation_mode", "services", "available_features"}

        live = {m.value for m in AIService}
        assert live, "AIService is empty; the equality below would pass on nothing"
        assert set(status["services"]) == live, sorted(status["services"])

        for member in live:
            row = status["services"][member]
            assert row["service"] == member
            assert set(row) == {
                "service",
                "status",
                "circuit_state",
                "last_success",
                "failure_count",
                "error_message",
                "last_check",
            }, sorted(row)

        # TOMBSTONED names, asserted against the LIVE roster: the three rows the
        # drafted pin looked for. nemotron's went with S2b's LLM tier,
        # florence's and clip's with rulings 1 and 5. Non-vacuity is the
        # equality above -- a rollup emitting zero service rows would satisfy
        # three ``not in`` checks and fail that one.
        for dead in RETIRE_SERVICE_NAMES:
            assert dead not in status["services"], sorted(status["services"])

    def test_get_degradation_status_timestamp_format(self, ai_fallback_service: AIFallbackService):
        """Test degradation status timestamp is ISO format."""
        status = ai_fallback_service.get_degradation_status()

        # Should be parseable as ISO timestamp
        timestamp = datetime.fromisoformat(status["timestamp"].replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)
