"""P0.3 constrained verdict on the legacy Nemotron path (spec §3 + §6, F4-approved).

Three coupled changes, one premise: an unparseable verdict must NEVER surface
as a score (S5). Today every LLM/parse failure lands on `risk_score=50,
risk_level="medium"` - a fabricated middle-risk alert. Per the F4 ruling
(ledger 2026-09-24, owner "yes") these sites become `verification_failed`
events carrying NULL score/level, which P0.25 already made safe at every
consumer (WS schema, ack rule, notification filter, UI).

Mechanism (plan Task 3):
  1. Payload switch: `response_format: json_schema` (native, S-1/S-2-proven
     ENFORCED at the pinned build) replacing silently-ignored nvext.guided_json
     (E5) - schema taken from RISK_ANALYSIS_JSON_SCHEMA, the same object the
     parser validates against (single source, §3 drift doctrine).
  2. Startup enforcement probe: the S-1 nonce-const probe promoted to a
     once-per-endpoint runtime check. NOT-ENFORCED fails CLOSED - no silent
     prose mode, ever.
  3. Fail-closed: the nine default-50 sites become NULL + verification_failed.

R8: every legacy path stays reachable - `nemotron_constrained_decoding_enabled
= False` reproduces today's byte-identical behavior (the flip is a settings
change, deletion waits for R8). These tests pin BOTH sides of that line.
"""

from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.engine.result import Result, ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.llm_response import RISK_ANALYSIS_JSON_SCHEMA
from backend.services.nemotron_analyzer import NemotronAnalyzer

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60)]

CONSTRUCTION_FLAGS = (
    "nemotron_constrained_decoding_enabled",
    "nemotron_constrained_fail_closed",
    "nemotron_constrained_probe_enabled",
    "nemotron_constrained_probe_required_build",
)


# =============================================================================
# Harness: settings + analyzer under the established patch surface
# =============================================================================


def _base_settings() -> MagicMock:
    """Settings mock with every attribute __init__/analyze paths read, copied
    from the established analyzer fixtures - plus the P0.3 trio set explicitly.
    spec=Settings makes an unknown attribute an AttributeError: that IS the
    red-state signature that the flags do not exist on the real class (pinned
    separately by TestSettingsFlags against Settings itself)."""
    from backend.core.config import Settings

    m = MagicMock(spec=Settings)
    m.nemotron_url = "http://localhost:8091"
    m.nemotron_api_key = None
    m.ai_connect_timeout = 10.0
    m.nemotron_read_timeout = 120.0
    m.ai_health_timeout = 5.0
    m.nemotron_max_retries = 1
    m.severity_low_max = 29
    m.severity_medium_max = 59
    m.severity_high_max = 84
    m.nemotron_context_window = 4096
    m.nemotron_max_output_tokens = 1536
    m.context_utilization_warning_threshold = 0.80
    m.context_truncation_enabled = True
    m.llm_tokenizer_encoding = "cl100k_base"
    m.image_quality_enabled = False
    m.ai_warmup_enabled = False
    m.ai_cold_start_threshold_seconds = 300.0
    m.nemotron_warmup_prompt = "Test warmup prompt"
    m.scene_change_resize_width = 640
    m.use_enrichment_service = False
    m.ai_max_concurrent_inferences = 4
    m.nemotron_use_guided_json = False
    m.nemotron_guided_json_fallback = True
    m.batch_coalescing_enabled = False
    m.batch_coalescing_max_size = 10
    m.batch_coalescing_time_window = 5.0
    m.priority_queue_enabled = False
    m.priority_high_labels = ["weapon", "intruder", "fire"]
    m.priority_medium_labels = ["person", "unknown"]
    m.background_evaluation_enabled = True
    # P0.3 (spec §3/§6). Defaults here are the LEGACY defaults; the shipped
    # Settings defaults must match (pinned by TestSettingsFlags). On a spec'd
    # mock, setting a name Settings lacks raises AttributeError - that IS the
    # red-state signature of the flags not existing yet.
    m.nemotron_constrained_decoding_enabled = False
    m.nemotron_constrained_fail_closed = True
    m.nemotron_constrained_probe_enabled = True
    m.nemotron_constrained_probe_required_build = None
    # P0.4 row provenance (the event_verifications engine/model_id columns
    # are NOT NULL, so the analyzer ships defaults for them)
    m.nemotron_verification_engine = "llama.cpp"
    m.nemotron_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
    return m


def _constrained_settings() -> MagicMock:
    s = _base_settings()
    s.nemotron_constrained_decoding_enabled = True
    return s


@contextmanager
def analyzer_under(settings: MagicMock):
    """Fresh analyzer under the same get_settings-patch surface the
    established test_nemotron_analyzer fixture uses; stack closes at exit."""
    from backend.core.redis import RedisClient

    redis = MagicMock(spec=RedisClient)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)

    from backend.services.analyzer_facade import reset_analyzer_facade
    from backend.services.inference_semaphore import reset_inference_semaphore
    from backend.services.severity import reset_severity_service
    from backend.services.token_counter import reset_token_counter

    stack = ExitStack()
    for target in (
        "backend.services.nemotron_analyzer.get_settings",
        "backend.services.severity.get_settings",
        "backend.services.token_counter.get_settings",
        "backend.core.config.get_settings",
        "backend.services.inference_semaphore.get_settings",
    ):
        stack.enter_context(patch(target, return_value=settings, autospec=True))
    reset_severity_service()
    reset_token_counter()
    reset_analyzer_facade()
    reset_inference_semaphore()
    try:
        yield NemotronAnalyzer(redis_client=redis)
    finally:
        stack.close()
        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()


def mock_probe_pass(analyzer: NemotronAnalyzer, calls: list | None = None) -> None:
    """Replace the promoted probe with a pass recorder: unit behavior of the
    probe itself is TestEnforcementProbe's job; everywhere else it's a
    dependency that has already passed."""

    async def _pass() -> None:
        if calls is not None:
            calls.append("probe")

    analyzer._ensure_constrained_enforcement = _pass  # type: ignore[method-assign]


def json_dumps(obj) -> str:
    return json.dumps(obj)


# =============================================================================
# 1. Settings surface: the flags exist, and their DEFAULTS are the legacy
#    behavior (byte-identical legacy invariant survives the merge itself)
# =============================================================================


class TestSettingsFlags:
    def test_constrained_fields_exist(self) -> None:
        from backend.core.config import Settings

        for name in CONSTRUCTION_FLAGS:
            assert name in Settings.model_fields, name

    def test_shipped_default_is_constrained(self) -> None:
        """R8/plan wording: "keep code paths, ADD THE NEW DEFAULT" - the
        new default is ON, and the old route survives behind the settings
        flip. The byte-identical legacy promise is about the code path
        behind nemotron_constrained_decoding_enabled=False (pinned by every
        legacy test with an explicit pin), NOT about the shipped default."""
        from backend.core.config import Settings

        f = Settings.model_fields
        assert f["nemotron_constrained_decoding_enabled"].default is True
        assert f["nemotron_constrained_fail_closed"].default is True
        assert f["nemotron_constrained_probe_enabled"].default is True
        assert f["nemotron_constrained_probe_required_build"].default is None


# =============================================================================
# 2. The promoted enforcement probe (S-1's contract as a runtime check):
#    ENFORCED caches, IGNORED/INCONCLUSIVE fail CLOSED, legacy never probes
# =============================================================================


class TestEnforcementProbe:
    @pytest.mark.asyncio
    async def test_enforced_verdict_passes_and_caches(self) -> None:
        """A /completion whose reply echoes the nonce const proves grammar
        enforcement (S-1 arm B2); a second call must not re-hit the network
        (once-per-endpoint)."""
        import uuid

        with analyzer_under(_constrained_settings()) as a:
            sent_nonces: list[str] = []

            async def fake_get(url: str, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"build_info": "b7972-e06088da0"}
                return r

            async def fake_post(url: str, json: dict | None = None, **kw):
                nonce = json["json_schema"]["properties"]["probe_const"]["const"]
                sent_nonces.append(nonce)
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"content": json_dumps({"probe_const": nonce})}
                return r

            a._http_client.get = AsyncMock(side_effect=fake_get)  # type: ignore[method-assign]
            a._http_client.post = AsyncMock(side_effect=fake_post)  # type: ignore[method-assign]

            await a._ensure_constrained_enforcement()
            await a._ensure_constrained_enforcement()  # cached

            assert a._http_client.post.await_count == 1
            uuid.UUID(sent_nonces[0])  # fresh uuid4 const, S-1's shape

    @pytest.mark.asyncio
    async def test_ignored_verdict_fails_closed(self) -> None:
        """S-1's IGNORED arm (prose back, const missing) must RAISE, not
        degrade: spec §3's 'fail closed' clause - no silent prose mode."""
        from backend.services.nemotron_analyzer import ConstrainedDecodingNotEnforced

        with analyzer_under(_constrained_settings()) as a:

            async def fake_get(url: str, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"build_info": "b7972-e06088da0"}
                return r

            async def prose_post(url: str, json: dict | None = None, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"content": "A person walks toward the door."}
                return r

            a._http_client.get = AsyncMock(side_effect=fake_get)  # type: ignore[method-assign]
            a._http_client.post = AsyncMock(side_effect=prose_post)  # type: ignore[method-assign]

            with pytest.raises(ConstrainedDecodingNotEnforced):
                await a._ensure_constrained_enforcement()

    @pytest.mark.asyncio
    async def test_build_info_mismatch_is_inconclusive_fail_closed(self) -> None:
        """A pinned build_info the endpoint does not report = wrong server =
        INCONCLUSIVE = closed (S-1's exit-2 arm), never 'assume enforced'."""
        from backend.services.nemotron_analyzer import ConstrainedDecodingNotEnforced

        s = _constrained_settings()
        s.nemotron_constrained_probe_required_build = "b7972"
        with analyzer_under(s) as a:

            async def fake_get(url: str, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"build_info": "b9999-deadbeef"}
                return r

            a._http_client.get = AsyncMock(side_effect=fake_get)  # type: ignore[method-assign]
            a._http_client.post = AsyncMock()  # type: ignore[method-assign]

            with pytest.raises(ConstrainedDecodingNotEnforced):
                await a._ensure_constrained_enforcement()
            a._http_client.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_legacy_config_never_probes(self) -> None:
        """Flag off = old route = zero new network traffic at startup: the
        legacy byte-identical invariant, applied to the probe itself."""
        with analyzer_under(_base_settings()) as a:
            a._http_client.get = AsyncMock()  # type: ignore[method-assign]
            await a._ensure_constrained_enforcement()
            a._http_client.get.assert_not_awaited()


# =============================================================================
# 3. Payload switch: native json_schema (same object the parser expects),
#    gated behind the probe; legacy payload untouched
# =============================================================================


class TestPayloadSwitch:
    @pytest.mark.asyncio
    async def test_constrained_payload_carries_native_schema_and_no_nvext(self) -> None:
        """response_format.json_schema is the S-2-proven ENFORCED mechanism;
        the schema is RISK_ANALYSIS_JSON_SCHEMA itself - single source (§3):
        what is demanded is what is parsed."""
        with analyzer_under(_constrained_settings()) as a:
            calls: list[str] = []
            mock_probe_pass(a, calls)

            captured: dict = {}

            async def fake_post(url: str, json: dict | None = None, **kw):
                captured.update(json or {})
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": json_dumps(
                        {"risk_score": 40, "risk_level": "medium", "summary": "s", "reasoning": "r"}
                    ),
                    "usage": {},
                }
                return r

            a._http_client.post = AsyncMock(side_effect=fake_post)  # type: ignore[method-assign]

            out = await a._call_llm(
                camera_name="cam_x",
                start_time="2026-01-07T12:00:00",
                end_time="2026-01-07T12:01:00",
                detections_list="1. 12:00:00 - person (confidence: 0.95)",
            )

        assert out["risk_score"] == 40
        # S-1 arm B2 [V] verified this exact shape at the pinned build:
        # top-level json_schema on /completion, carrying THE parser's schema.
        assert captured["json_schema"] is RISK_ANALYSIS_JSON_SCHEMA
        assert "nvext" not in captured
        assert calls == ["probe"]  # enforcement checked before the inference call

    @pytest.mark.asyncio
    async def test_legacy_payload_is_untouched_and_unprobed(self) -> None:
        """Byte-identical legacy: no response_format, no probe call - a
        settings-off install sees zero of this work."""
        with analyzer_under(_base_settings()) as a:
            captured: dict = {}

            async def fake_post(url: str, json: dict | None = None, **kw):
                captured.update(json or {})
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": json_dumps(
                        {"risk_score": 40, "risk_level": "medium", "summary": "s", "reasoning": "r"}
                    ),
                    "usage": {},
                }
                return r

            a._http_client.post = AsyncMock(side_effect=fake_post)  # type: ignore[method-assign]
            probe = AsyncMock()
            a._ensure_constrained_enforcement = probe  # type: ignore[method-assign]

            await a._call_llm(
                camera_name="cam_y",
                start_time="2026-01-07T12:00:00",
                end_time="2026-01-07T12:01:00",
                detections_list="1. 12:00:00 - person (confidence: 0.95)",
            )

        assert "json_schema" not in captured
        assert "nvext" not in captured
        probe.assert_not_awaited()


# =============================================================================
# 4. Fail-closed validation: unparseable scores become NULL+flag, never 50
# =============================================================================


class TestFailClosedValidation:
    def test_unsalvageable_score_becomes_null_and_flag(self) -> None:
        """_validate_risk_data's salvage branch (:4392, ledger [V] list): with
        fail-closed on, garbage never becomes 50/medium; partial text
        survives as text, never laundered into a score."""
        with analyzer_under(_constrained_settings()) as a:
            out = a._validate_risk_data({"risk_score": "not_a_number", "reasoning": "partial text"})
        assert out["risk_score"] is None
        assert out["risk_level"] is None
        assert out["verification_failed"] is True
        assert out["reasoning"] == "partial text"

    def test_legacy_salvage_still_defaults_50(self) -> None:
        """R8: flag off -> today's behavior verbatim (mirrors
        test_nemotron_analyzer.py:374-385 - those pins stay green too)."""
        with analyzer_under(_base_settings()) as a:
            out = a._validate_risk_data({"risk_score": "not_a_number"})
        assert out["risk_score"] == 50
        assert out["risk_level"] == "medium"


# =============================================================================
# 5. Fail-closed end to end: the analyze_batch / fast-path except clusters
#    (:2837, :3350 + their Event-creation gets) produce NULL-score events
# =============================================================================


def _camera():
    from backend.models.camera import Camera

    return Camera(
        id="front_door",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door",
        status="online",
    )


def _detection(det_id: int = 1):
    from backend.models.detection import Detection

    return Detection(
        id=det_id,
        camera_id="front_door",
        file_path="/export/foscam/front_door/img1.jpg",
        detected_at=datetime(2026, 1, 7, 12, 0, tzinfo=UTC),
        object_type="person",
        confidence=0.95,
    )


class _Ctx:
    """Minimal async context manager for get_session() call sites."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


def _session_factory(read_session, write_session):
    """get_session() is entered per phase: first entry = READ session,
    every later entry = WRITE session."""
    pending = [read_session]

    def factory(*a, **k):
        if pending:
            return _Ctx(pending.pop(0))
        return _Ctx(write_session)

    return factory


def _read_session(camera, rows, *, rows_via="scalars"):
    """READ session mock: query 1 -> camera (scalar_one_or_none),
    query 2 -> rows (either .scalars().all() [batch] or .scalar_one_or_none()
    [fast path])."""
    session = MagicMock(spec=AsyncSession)
    cam_res = MagicMock(spec=Result)
    cam_res.scalar_one_or_none.return_value = camera

    row_res = MagicMock(spec=Result)
    if rows_via == "scalars":
        scalars = MagicMock(spec=ScalarResult)
        scalars.all.return_value = rows
        row_res.scalars.return_value = scalars
    else:
        row_res.scalar_one_or_none.return_value = rows[0]

    results = [cam_res, row_res]

    async def execute(query):
        return results.pop(0) if results else _empty_result()

    session.execute = execute
    return session


def _empty_result():
    """A DB result for the auxiliary reads (enriched context, scene
    changes): every accessor answers 'nothing found'."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = []
    r.scalars.return_value.first.return_value = None
    r.scalar_one_or_none.return_value = None
    r.all.return_value = []
    r.first.return_value = None
    r.fetchone.return_value = None
    return r


def _write_session():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.execute.return_value = _empty_result()
    return session


def _no_enrichment(analyzer: NemotronAnalyzer):
    """Neutralize the enrichment stage (unit scope: it has its own suite);
    returns a patcher to optionally replace with a fire-holding result."""
    tracking = MagicMock()
    tracking.has_data = False
    tracking.data = None
    return patch.object(
        analyzer, "_get_enrichment_result_from_data", AsyncMock(return_value=tracking)
    )


class TestFailClosedEvents:
    @pytest.mark.asyncio
    async def test_llm_failure_yields_null_score_event(self) -> None:
        """The F4 behavior change, executed: LLM service error -> an Event
        EXISTS (D11: it still reaches the dashboard) with NULL score+level,
        verification-failure summary; the broadcast still fires."""
        with analyzer_under(_constrained_settings()) as a:
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            async def failing_llm(*a2, **k2):
                raise httpx.ConnectError("LLM service unavailable")

            broadcast = AsyncMock()
            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(
                    a, "_broadcast_event", broadcast
                ),  # assertion handle passed as new; autospec forbids the pair
            ):
                event = await a.analyze_batch(
                    batch_id="batch_p03", camera_id="front_door", detection_ids=[det.id]
                )

        assert event.risk_score is None
        assert event.risk_level is None
        assert "Verification unavailable" in event.summary
        assert "Analysis unavailable" not in event.summary  # S5: 50-era wording gone
        broadcast.assert_awaited_once()  # D11: NULL events still reach clients

    @pytest.mark.asyncio
    async def test_unparseable_prose_completion_yields_null_event(self) -> None:
        """S5's sharpest edge: the LLM answers 200 with PROSE. If the schema
        was not enforced (the probe exists to make that impossible), the
        parse must NOT invent a 50 - the event is unverified."""
        with analyzer_under(_constrained_settings()) as a:
            mock_probe_pass(a)
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            async def prose_post(url: str, json: dict | None = None, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"content": "A person is walking to the door.", "usage": {}}
                return r

            a._http_client.post = AsyncMock(side_effect=prose_post)  # type: ignore[method-assign]

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                event = await a.analyze_batch(
                    batch_id="batch_p03_prose",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        assert event.risk_score is None
        assert event.risk_level is None
        assert "Verification unavailable" in event.summary

    @pytest.mark.asyncio
    async def test_fast_path_failure_yields_null_score_event(self) -> None:
        """Cluster 2 (:3350/:3391): the fast path shares the semantics - same
        NULL rule, is_fast_path preserved."""
        with analyzer_under(_constrained_settings()) as a:
            camera, det = _camera(), _detection()
            read_s = _read_session(camera, [det], rows_via="scalar")
            write_s = _write_session()

            async def failing_llm(*a2, **k2):
                raise httpx.ReadTimeout("slow")

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                event = await a.analyze_detection_fast_path("front_door", det.id)

        assert event.risk_score is None
        assert event.risk_level is None
        assert event.is_fast_path is True
        assert "Verification unavailable" in event.summary

    @pytest.mark.asyncio
    async def test_legacy_failure_still_50_medium(self) -> None:
        """The flip side of the F4 ruling: with the flag off the fallback is
        today's, unchanged (test_nemotron_analyzer.py's 50-pin stays green)."""
        with analyzer_under(_base_settings()) as a:
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            async def failing_llm(*a2, **k2):
                raise httpx.ConnectError("LLM service unavailable")

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                event = await a.analyze_batch(
                    batch_id="batch_legacy_p03",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        assert event.risk_score == 50
        assert event.risk_level == "medium"
        assert "Analysis unavailable" in event.summary

    @pytest.mark.asyncio
    async def test_fire_override_still_scores_over_a_null(self) -> None:
        """NEM-5566 is safety-critical and non-LLM: fire detected by the
        smoke model scores 100/critical even when LLM verification failed -
        fail-closed must not silence a real fire. The reasoning says
        'unverified', never renders a None."""
        with analyzer_under(_constrained_settings()) as a:
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            fire = MagicMock()
            fire.has_fire = True
            fire.highest_confidence = 0.97
            enrichment = MagicMock()
            enrichment.smoke_fire_detection = fire
            tracking = MagicMock()
            tracking.has_data = True
            tracking.data = enrichment
            tracking.status = "completed"
            enrichment.to_storage_dict = MagicMock(return_value={})

            async def failing_llm(*a2, **k2):
                raise httpx.ConnectError("down")

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                patch.object(
                    a, "_get_enrichment_result_from_data", AsyncMock(return_value=tracking)
                ),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                event = await a.analyze_batch(
                    batch_id="batch_fire_p03",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        assert event.risk_score == 100
        assert event.risk_level == "critical"
        assert "unverified" in event.reasoning
        assert "None" not in event.reasoning


class TestAuditPriorityForNull:
    @pytest.mark.asyncio
    async def test_null_event_not_evaluated_at_medium_priority(self) -> None:
        """`event.risk_score or 50` (:2965/:3459) would rank an unverified
        event at MEDIUM for GPU-idle audit priority. It is not medium - an
        unverified event gets the floor, never a disguised middle risk."""
        with analyzer_under(_constrained_settings()) as a:
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()
            enqueue = AsyncMock()

            async def failing_llm(*a2, **k2):
                raise httpx.ConnectError("down")

            audit_service = MagicMock()
            audit = MagicMock()
            audit.id = 99
            audit_service.create_partial_audit.return_value = audit

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_broadcast_event", AsyncMock()),
                patch.object(
                    a, "_enqueue_for_evaluation", enqueue
                ),  # assertion handle passed as new; autospec forbids the pair
                patch(
                    "backend.services.pipeline_quality_audit_service.get_audit_service",
                    autospec=True,
                    return_value=audit_service,
                ),
            ):
                event = await a.analyze_batch(
                    batch_id="batch_prio_p03",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        assert event.risk_score is None
        assert enqueue.await_count == 1, "audit enqueue must still happen"
        priority = enqueue.await_args.args[1]
        assert priority != 50
        assert priority == 0  # the floor: an unverified event is least trusted


# =============================================================================
# 6. NULL-score safety beyond the event row: metrics, shadow comparison,
#    the provenance-row producer (P0.4 table) and notification composition
# =============================================================================


class TestNullScoreMetricsSafety:
    @pytest.mark.asyncio
    async def test_fail_closed_metrics_block_survives_none(self, caplog) -> None:
        """A fail-closed NULL must travel the WHOLE _call_llm pipeline
        cleanly. The NEM-769 metrics block is the landmine: observe(None)
        raises TypeError, which used to get swallowed by the retry loop -
        the event still ended NULL (masking the bug) but the metric was
        silently lost and every verification failure logged a spurious
        ERROR. No-score observations are SKIPPED, never laundered to 0."""
        import logging

        with analyzer_under(_constrained_settings()) as a:
            mock_probe_pass(a)

            async def scoreless_post(url: str, json: dict | None = None, **kw):
                # JSON arrives but carries a NULL score: the lenient parser
                # would launder it to 50, the P0.3 outcome check catches that
                # and returns the NULL dict WITHOUT raising - so the NEM-769
                # metrics block downstream is handed None.
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": json_dumps(
                        {
                            "risk_score": None,
                            "risk_level": None,
                            "summary": "A person.",
                            "reasoning": "hmm",
                        }
                    ),
                    "usage": {},
                }
                return r

            a._http_client.post = AsyncMock(side_effect=scoreless_post)  # type: ignore[method-assign]
            with caplog.at_level(logging.WARNING):
                out = await a._call_llm(
                    camera_name="Front Door Camera",
                    start_time="2026-01-07T12:00:00+00:00",
                    end_time="2026-01-07T12:00:30+00:00",
                    detections_list=[{"file_path": "/x.jpg", "object_type": "person"}],
                )

        assert out["verification_failed"] is True
        assert out["risk_score"] is None
        messages = [r.getMessage() for r in caplog.records]
        assert any(
            m.startswith("Failed to validate LLM response - fail-closed NULL") for m in messages
        )
        assert not any(
            r.levelno >= logging.ERROR for r in caplog.records if "nemotron" in r.name
        ), f"fail-closed NULL must not emit ERROR logs: {messages}"

    def test_shipped_provenance_defaults_exist(self) -> None:
        """The EventVerification row's engine/model_id columns are NOT NULL,
        so the analyzer needs shipped defaults for them (the repo has no
        served-model-id setting; the endpoint name lives in the error text,
        the ids live here)."""
        from backend.core.config import Settings

        f = Settings.model_fields
        assert f["nemotron_verification_engine"].default == "llama.cpp"
        assert f["nemotron_model_id"].default == "Nemotron-3-Nano-30B-A3B-Q4_K_M"


class TestVersionRouteAndShadowSafety:
    @pytest.mark.asyncio
    async def test_version_route_carries_native_schema_and_probes(self) -> None:
        """The prompt-A/B/shadow route is the payload switch's second site
        (plan Task 3 names :1033-1049): same native json_schema, same
        once-per-endpoint probe gate - no nvext half-measures."""
        with analyzer_under(_constrained_settings()) as a:
            calls: list = []
            mock_probe_pass(a, calls)
            captured: dict = {}

            async def ok_post(url: str, json: dict | None = None, **kw):
                captured["url"] = url
                captured["payload"] = json
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": json_dumps(
                        {
                            "risk_score": 30,
                            "risk_level": "low",
                            "summary": "s",
                            "reasoning": "r",
                        }
                    ),
                    "usage": {},
                }
                return r

            a._http_client.post = AsyncMock(side_effect=ok_post)  # type: ignore[method-assign]
            out = await a._call_llm_with_version("ctx prompt")

        assert out["risk_score"] == 30
        assert captured["payload"].get("json_schema") is RISK_ANALYSIS_JSON_SCHEMA
        assert "nvext" not in captured["payload"]
        assert calls == ["probe"]

    @pytest.mark.asyncio
    async def test_legacy_version_route_untouched_and_unprobed(self) -> None:
        with analyzer_under(_base_settings()) as a:
            captured: dict = {}

            async def ok_post(url: str, json: dict | None = None, **kw):
                captured["payload"] = json
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": json_dumps(
                        {
                            "risk_score": 30,
                            "risk_level": "low",
                            "summary": "s",
                            "reasoning": "r",
                        }
                    ),
                    "usage": {},
                }
                return r

            a._http_client.post = AsyncMock(side_effect=ok_post)  # type: ignore[method-assign]
            await a._call_llm_with_version("ctx prompt")

        payload = captured["payload"]
        assert "json_schema" not in payload
        assert "response_format" not in payload
        assert "nvext" not in payload
        assert a._constrained_enforced is None, "legacy never probes"

    @pytest.mark.asyncio
    async def test_shadow_score_diff_survives_a_null(self) -> None:
        """Shadow comparison must not crash when treatment fails closed:
        NULL vs scored is honestly incomparable (-1.0 sentinel), never a
        TypeError swallowed into a silent V2-failure - and never laundered
        through a 0 that would fake a 70-point delta."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        with analyzer_under(_constrained_settings()) as a:
            mock_probe_pass(a)
            a.set_experiment_config(PromptExperimentConfig(shadow_mode=True))
            responses = [
                json_dumps(
                    {
                        "risk_score": 70,
                        "risk_level": "high",
                        "summary": "s",
                        "reasoning": "r",
                    }
                ),
                "prose with no json at all",
            ]

            async def seq_post(url: str, json: dict | None = None, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"content": responses.pop(0), "usage": {}}
                return r

            a._http_client.post = AsyncMock(side_effect=seq_post)  # type: ignore[method-assign]
            out = await a.run_shadow_analysis("front_door", "ctx prompt")

        assert out["primary_result"]["risk_score"] == 70
        assert out["shadow_result"]["risk_score"] is None
        assert out["score_diff"] == -1.0


class TestVerificationRowProducer:
    """Task 4 box 4 (landed, producer deferred to this slice): P0.3's
    fail-closed path writes the event_verifications row - verdict
    'verification_failed', engine/model from settings, latency honest (NULL
    when the failure happened before any timed call)."""

    @pytest.mark.asyncio
    async def test_batch_fail_closed_writes_verification_row(self) -> None:
        from backend.models.event_verification import EventVerification

        with analyzer_under(_constrained_settings()) as a:
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            async def failing_llm(*a2, **k2):
                raise httpx.ConnectError("LLM service unavailable")

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                event = await a.analyze_batch(
                    batch_id="batch_row_p03",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        rows = [
            o
            for o in (c.args[0] for c in write_s.add.call_args_list)
            if isinstance(o, EventVerification)
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row.verdict == "verification_failed"
        assert row.engine == "llama.cpp"
        assert row.model_id == "Nemotron-3-Nano-30B-A3B-Q4_K_M"
        assert row.latency_ms is None, "transport failure before any call: honest NULL"
        assert event.risk_score is None

    @pytest.mark.asyncio
    async def test_fast_path_fail_closed_writes_verification_row(self) -> None:
        from backend.models.event_verification import EventVerification

        with analyzer_under(_constrained_settings()) as a:
            camera, det = _camera(), _detection()
            read_s = _read_session(camera, [det], rows_via="scalar")
            write_s = _write_session()

            async def failing_llm(*a2, **k2):
                raise httpx.ReadTimeout("slow")

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                await a.analyze_detection_fast_path("front_door", det.id)

        rows = [
            o
            for o in (c.args[0] for c in write_s.add.call_args_list)
            if isinstance(o, EventVerification)
        ]
        assert len(rows) == 1
        assert rows[0].verdict == "verification_failed"

    @pytest.mark.asyncio
    async def test_prose_launder_row_carries_the_raw_completion(self) -> None:
        """The parse-failure path DID make a call, so latency is real, and
        the raw text rides the provenance row (the events table has no
        raw-response column; the UI resolves key frames separately)."""
        from backend.models.event_verification import EventVerification

        with analyzer_under(_constrained_settings()) as a:
            mock_probe_pass(a)
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            async def prose_post(url: str, json: dict | None = None, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": "The scene shows a person near the door.",
                    "usage": {},
                }
                return r

            a._http_client.post = AsyncMock(side_effect=prose_post)  # type: ignore[method-assign]
            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                await a.analyze_batch(
                    batch_id="batch_row_prose",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        rows = [
            o
            for o in (c.args[0] for c in write_s.add.call_args_list)
            if isinstance(o, EventVerification)
        ]
        assert len(rows) == 1
        assert rows[0].verdict == "verification_failed"
        assert "person near the door" in (rows[0].scene_description or "")

    @pytest.mark.asyncio
    async def test_fire_override_writes_verified_row(self) -> None:
        """The fire override makes the event VERIFIED by non-LLM evidence,
        so the row is 'confirmed' with the fire text - the provenance never
        contradicts the score the UI shows (spec §4's UI contract)."""
        from backend.models.event_verification import EventVerification

        with analyzer_under(_constrained_settings()) as a:
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            fire = MagicMock()
            fire.has_fire = True
            fire.highest_confidence = 0.97
            enrichment = MagicMock()
            enrichment.smoke_fire_detection = fire
            tracking = MagicMock()
            tracking.has_data = True
            tracking.data = enrichment
            tracking.status = "completed"
            enrichment.to_storage_dict = MagicMock(return_value={})

            async def failing_llm(*a2, **k2):
                raise httpx.ConnectError("down")

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                patch.object(
                    a, "_get_enrichment_result_from_data", AsyncMock(return_value=tracking)
                ),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                event = await a.analyze_batch(
                    batch_id="batch_fire_row",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        rows = [
            o
            for o in (c.args[0] for c in write_s.add.call_args_list)
            if isinstance(o, EventVerification)
        ]
        assert event.risk_score == 100
        assert len(rows) == 1
        assert rows[0].verdict == "confirmed"
        assert "fire" in (rows[0].scene_description or "").lower()

    @pytest.mark.asyncio
    async def test_success_writes_no_verification_row(self) -> None:
        """Row presence is spec §4's branch: a scored success has NOTHING
        to record here (the verifier itself lands rows in 0.6's pipeline)."""
        from backend.models.event_verification import EventVerification

        with analyzer_under(_constrained_settings()) as a:
            mock_probe_pass(a)
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            async def ok_post(url: str, json: dict | None = None, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": json_dumps(
                        {
                            "risk_score": 30,
                            "risk_level": "low",
                            "summary": "Quiet street scene.",
                            "reasoning": "Nothing unusual.",
                        }
                    ),
                    "usage": {},
                }
                return r

            a._http_client.post = AsyncMock(side_effect=ok_post)  # type: ignore[method-assign]
            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                await a.analyze_batch(
                    batch_id="batch_ok_row",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        kinds = [type(c.args[0]).__name__ for c in write_s.add.call_args_list]
        assert "EventVerification" not in kinds
        assert "Event" in kinds
        assert not any(isinstance(c.args[0], EventVerification) for c in write_s.add.call_args_list)

    @pytest.mark.asyncio
    async def test_legacy_fail_closed_off_writes_no_row(self) -> None:
        """Flag off = pre-0.3 payload exactly (F4 ruled only the SEMANTICS
        change) - the row's existence is a 0.3/0.6 product surface, not
        legacy behavior to duplicate."""
        with analyzer_under(_base_settings()) as a:
            camera, det = _camera(), _detection()
            read_s, write_s = _read_session(camera, [det]), _write_session()

            async def failing_llm(*a2, **k2):
                raise httpx.ConnectError("LLM service unavailable")

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    autospec=True,
                    side_effect=_session_factory(read_s, write_s),
                ),
                _no_enrichment(a),
                patch.object(a, "_call_llm", side_effect=failing_llm, autospec=True),
                patch.object(a, "_enqueue_for_evaluation", AsyncMock()),
                patch.object(a, "_broadcast_event", AsyncMock()),
            ):
                event = await a.analyze_batch(
                    batch_id="batch_legacy_row",
                    camera_id="front_door",
                    detection_ids=[det.id],
                )

        assert event.risk_score == 50
        kinds = [type(c.args[0]).__name__ for c in write_s.add.call_args_list]
        assert "EventVerification" not in kinds


class TestNotificationComposition:
    """Spec §6 step 3 composed on the REAL consumers (the rule itself is
    P0.25's, pinned in test_null_score_p025.py; no production caller exists
    yet - these pins are the composition contract 0.6+ builds on)."""

    def _prefs(self):
        from backend.models.notification_preferences import NotificationPreferences

        p = NotificationPreferences()
        p.enabled = True
        p.risk_filters = ["low", "medium", "high", "critical"]
        return p

    def _camera(self, threshold: int = 0):
        from backend.models.notification_preferences import CameraNotificationSetting

        c = CameraNotificationSetting()
        c.enabled = True
        c.risk_threshold = threshold
        return c

    def test_null_broadcast_never_demands_ack(self) -> None:
        from backend.services.event_broadcaster import requires_ack

        assert (
            requires_ack(
                {
                    "event_type": "event_created",
                    "data": {"risk_score": None, "risk_level": None},
                }
            )
            is False
        )

    def test_null_strong_person_notifies_via_detector_only(self, monkeypatch) -> None:
        from types import SimpleNamespace

        import backend.services.notification_filter as nf
        from backend.services.notification_filter import NotificationFilterService

        monkeypatch.setattr(
            nf,
            "get_settings",
            lambda: SimpleNamespace(detection_confidence_threshold=0.40),
            raising=False,
        )
        assert (
            NotificationFilterService().should_notify(
                risk_score=None,
                camera_id="front_door",
                timestamp=datetime(2026, 1, 7, 12, 0, tzinfo=UTC),
                global_prefs=self._prefs(),
                camera_setting=self._camera(threshold=90),  # a score threshold must NOT veto
                detection_class="person",
                detection_confidence=0.9,
            )
            is True
        )

    def test_null_weak_person_suppressed(self) -> None:
        from backend.services.notification_filter import NotificationFilterService

        assert (
            NotificationFilterService().should_notify(
                risk_score=None,
                camera_id="front_door",
                timestamp=datetime(2026, 1, 7, 12, 0, tzinfo=UTC),
                global_prefs=self._prefs(),
                detection_class="person",
                detection_confidence=0.10,
            )
            is False
        )


# =============================================================================
# 7. Startup gate (plan Task 3 box 1): once per endpoint, and the lifespan
#    SURVIVES both an IGNORED verdict and an unreachable endpoint
# =============================================================================


def _fake_container(analyzer):
    calls: list = []

    async def get_async(name):
        calls.append(name)
        return analyzer

    container = MagicMock()
    container.get_async = get_async
    container.lookups = calls
    return container


class TestStartupGate:
    @pytest.mark.asyncio
    async def test_constrained_startup_probes_once(self) -> None:
        from backend.main import run_constrained_startup_check

        with analyzer_under(_constrained_settings()) as a:
            calls: list = []
            mock_probe_pass(a, calls)
            container = _fake_container(a)
            outcome = await run_constrained_startup_check(container)

        assert outcome == "enforced"
        assert calls == ["probe"]
        assert container.lookups == ["nemotron_analyzer"]

    @pytest.mark.asyncio
    async def test_ignored_verdict_is_reported_not_raised(self) -> None:
        """Fail-closed = the VERDICTS fail closed, not the process: the
        lifespan must keep starting (legacy pipeline still useful) and the
        per-call gate still blocks verdicts; swallowing SILENTLY is the
        R-T7-CRASH class of failure this pins out."""
        from backend.main import run_constrained_startup_check
        from backend.services.nemotron_analyzer import ConstrainedDecodingNotEnforced

        async def boom() -> None:
            raise ConstrainedDecodingNotEnforced("verdict=IGNORED")

        with analyzer_under(_constrained_settings()) as a:
            a._ensure_constrained_enforcement = boom  # type: ignore[method-assign]
            outcome = await run_constrained_startup_check(_fake_container(a))

        assert outcome == "not_enforced"

    @pytest.mark.asyncio
    async def test_endpoint_unreachable_is_inconclusive_never_crashes(self) -> None:
        from backend.main import run_constrained_startup_check

        async def boom() -> None:
            raise httpx.ConnectError("endpoint down")

        with analyzer_under(_constrained_settings()) as a:
            a._ensure_constrained_enforcement = boom  # type: ignore[method-assign]
            outcome = await run_constrained_startup_check(_fake_container(a))

        assert outcome == "inconclusive"

    @pytest.mark.asyncio
    async def test_legacy_config_makes_no_network_call(self) -> None:
        from backend.main import run_constrained_startup_check

        with analyzer_under(_base_settings()) as a:
            a._http_client.get = AsyncMock(side_effect=AssertionError("no network expected"))
            a._http_client.post = AsyncMock(side_effect=AssertionError("no network expected"))
            outcome = await run_constrained_startup_check(_fake_container(a))

        assert outcome == "disabled"

    def test_lifespan_wires_the_gate(self) -> None:
        """The gate must be CALLED at startup, inside lifespan, outside the
        Redis try/except that swallows everything (that block would eat the
        probe failure and hide the enforcement state)."""
        import inspect

        import backend.main as main_module

        src = inspect.getsource(main_module)
        lifespan_src = src[src.index("async def lifespan") :]
        assert "run_constrained_startup_check" in lifespan_src
        redis_pos = lifespan_src.index("Redis connection failed")
        gate_pos = lifespan_src.index("run_constrained_startup_check")
        assert gate_pos < redis_pos, "gate must run BEFORE the Redis block"


# =============================================================================
# 8. The promoted operator/CI CLI (scripts/vlm_probes/enforcement.py): the
#    runtime gate's contract as a standalone probe, verdict vocabulary
#    shared with s1_nvext's arms
# =============================================================================


def _load_enforcement_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "scripts" / "vlm_probes" / "enforcement.py"
    assert path.exists(), f"missing promoted probe CLI: {path}"
    spec = importlib.util.spec_from_file_location("vss_enforcement_cli", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestEnforcementCliSurface:
    def test_promoted_cli_exists_with_the_probe_contract(self) -> None:
        m = _load_enforcement_module()
        for attr in ("run_probe", "main"):
            assert hasattr(m, attr), f"scripts/vlm_probes/enforcement.py lacks {attr}()"

    @pytest.mark.asyncio
    async def test_schema_valid_answer_without_the_const_is_ignored(self) -> None:
        """The whole point of the nonce const: a schema-valid JSON answer
        that does NOT echo the never-prompted const is NOT proof of the
        grammar (it could be pure prompt-following)."""
        m = _load_enforcement_module()
        sent: list = []

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *e):
                return False

            async def get(self, url, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"build_info": {"build": "b99999", "hash": "deadbeef"}}
                return r

            async def post(self, url, json=None, **kw):
                sent.append(json)
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": json_dumps(
                        {
                            "risk_score": 72,
                            "risk_level": "high",
                            "summary": "s",
                            "reasoning": "r",
                        }
                    )
                }
                return r

        with patch("httpx.AsyncClient", FakeClient):
            res = await m.run_probe("http://endpoint:8081")

        assert res["verdict"] == "IGNORED"
        assert sent and "json_schema" in sent[0]
        props = sent[0]["json_schema"]["properties"]
        assert "risk_score" in props, "the probe must ask the REAL schema"
        assert "probe_const" in props, "the nonce const must be schema-required"
        assert props["probe_const"]["const"], "the nonce must be a const"

    @pytest.mark.asyncio
    async def test_const_echo_is_enforced(self) -> None:
        m = _load_enforcement_module()
        sent: list = []

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *e):
                return False

            async def get(self, url, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"build_info": {"build": "b7972", "hash": "cafe0000"}}
                return r

            async def post(self, url, json=None, **kw):
                sent.append(json)
                nonce = json["json_schema"]["properties"]["probe_const"]["const"]
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {
                    "content": json_dumps(
                        {
                            "risk_score": 72,
                            "risk_level": "high",
                            "summary": "s",
                            "reasoning": "r",
                            "probe_const": nonce,
                        }
                    )
                }
                return r

        with patch("httpx.AsyncClient", FakeClient):
            res = await m.run_probe("http://endpoint:8081", expect_build="b7972")

        assert res["verdict"] == "ENFORCED"

    @pytest.mark.asyncio
    async def test_build_mismatch_is_inconclusive_before_any_completion(self) -> None:
        """Enforcement is proven per-BUILD; answering anyway against a
        different build would launder a stale proof onto an unknown
        endpoint."""
        m = _load_enforcement_module()
        posts: list = []

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *e):
                return False

            async def get(self, url, **kw):
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"build_info": {"build": "b80000"}}
                return r

            async def post(self, url, json=None, **kw):
                posts.append(json)
                raise AssertionError("must not probe completions on a build mismatch")

        with patch("httpx.AsyncClient", FakeClient):
            res = await m.run_probe("http://endpoint:8081", expect_build="b7972")

        assert res["verdict"] == "INCONCLUSIVE"
        assert posts == []
