"""Batch-25 kill battery — chunk "NemotronAnalyzer.analyze_batch#chunk3" (130 keys).

Full mutant-key namespace for every name below is
``backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_<N>``;
docstrings abbreviate that as ``analyze_batch__mutmut_<N>``.

Every expected value here was MEASURED against SHIPPED production this session
(/tmp/wp-batch25/probes/ad02_harness.py -> /tmp/wp-batch25/probes/ad02_measured.json);
production is NOT bent. Mutation sites covered (shipped line numbers, all inside
NemotronAnalyzer.analyze_batch, backend/services/nemotron_analyzer.py):

    2798      observe_ai_request_duration("nemotron", ...)          [success leg]
    2801-2809 add_span_event("nemotron_analysis.complete", {...})
    2811-2818 logger.debug("LLM analysis completed for batch {}", extra=...)
    2823      observe_ai_request_duration("nemotron", ...)          [failure leg]
    2824      record_pipeline_error("nemotron_analysis_error")
    2825      sanitized_error = sanitize_error(e)
    2826-2835 logger.error("LLM analysis failed for batch", extra=..., exc_info=True)
    2836-2842 risk_data = {...} fallback dict
    2879-2895 Event(...) row kwargs
    2913-2923 event_detections pg_insert VALUES dict + stmt
    2953-2958 create_partial_audit(llm_prompt=risk_data.get("llm_prompt"), ...)

Harness: analyzer built with a stub service facade (fetch_detections /
get_prompt_auto_tuner / get_cache_service stubbed — this also pins the
session.execute stream to exactly [camera SELECT, junction INSERT]), the optional
pipeline steps (enrichment, household, trajectory, scene-changes, enriched
context, broadcast, webhook, evaluation queue) are instance AsyncMocks,
session.add is captured, session2.flush assigns event.id=7, the audit service is
patched so create_partial_audit kwargs are directly observable, and
LLMInteraction is constructed SHIPPED (its raw_response is the read-back
observable for the fallback dict). Three scenarios drive every test: POPULATED
(risk_data carries every row field), EMPTY (risk_data={} -> shipped .get
defaults), FAIL (llm raises ValueError("llmboom"); a second FAIL variant carries
exc.raw_completion="RAWTEXT").

OCCURRENCE TWINNERS are carried whole — both keys of each shape group are killed
by tests on both legs: 320/372, 324/376, 325/377 (observe_ai_request_duration
arg shapes at 2798/2823); 359/392, 360/393, 363/396, 364/397 (camera_id /
duration_ms extra-key shapes at 2814/2829 and 2816/2831); 443/535, 457/539,
496/542, 497/543, 498/544 (llm_prompt shapes at Event 2888 / audit 2955).

RED-CHECK: apply each named mutant to a scratch copy of the module (variant
bodies extracted verbatim at /tmp/wp-batch25/probes/ad02_bodies.json), run the
named test, expect failure.
"""

from __future__ import annotations

import os

# Mirror the minimum env the repo conftest sets (this file lives OUTSIDE the repo
# tree so backend/tests/conftest.py does not apply). Values copied verbatim from
# backend/tests/conftest.py:107/114 and pytest_configure (:363-:385).
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("OTEL_ENABLED", "false")

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Explicit asyncio marker: run as an OUT-OF-TREE file the repo ini's
# asyncio_mode="auto" is not picked up (rootdir comes from the arg path), so the
# marker is applied here — same pattern as backend/tests/unit/services/
# test_nemotron_streaming_batch21.py.
pytestmark = [pytest.mark.unit, pytest.mark.asyncio, pytest.mark.timeout(60)]

MOD = "backend.services.nemotron_analyzer"
AUDIT_MOD = "backend.services.pipeline_quality_audit_service"
CAMERA_ID = "cam02"
BATCH_ID = "batch02"
EVENT_ID = 7

METRIC_FNS = [
    "observe_ai_request_duration",
    "observe_stage_duration",
    "record_pipeline_error",
    "record_event_created",
    "record_event_by_camera",
]

POP = {
    "risk_score": 75,
    "risk_level": "high",
    "summary": "S-pop",
    "reasoning": "R-pop",
    "llm_prompt": "PROMPT",
    "entities": [{"k": "person"}],
    "flags": [{"name": "loitering"}],
    "confidence_factors": {"motion": 0.7},
    "recommended_action": "check camera",
}


def _settings():
    """Copy of the repo test_nemotron_analyzer.py mock_settings fixture."""
    from backend.core.config import Settings

    s = MagicMock(spec=Settings)
    # P0.3 flags (#6678): pydantic v2 field names are not in
    # dir(Settings), so a spec'd mock must pin them explicitly.
    s.nemotron_constrained_decoding_enabled = False
    s.nemotron_constrained_fail_closed = True
    s.nemotron_constrained_probe_enabled = True
    s.nemotron_constrained_probe_required_build = None
    s.nemotron_verification_engine = "llama.cpp"
    s.nemotron_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
    s.nemotron_url = "http://localhost:8091"
    s.nemotron_api_key = None
    s.ai_connect_timeout = 10.0
    s.nemotron_read_timeout = 120.0
    s.ai_health_timeout = 5.0
    s.nemotron_max_retries = 2
    s.severity_low_max = 29
    s.severity_medium_max = 59
    s.severity_high_max = 84
    s.nemotron_context_window = 4096
    s.nemotron_max_output_tokens = 1536
    s.context_utilization_warning_threshold = 0.80
    s.context_truncation_enabled = True
    s.llm_tokenizer_encoding = "cl100k_base"
    s.image_quality_enabled = False
    s.ai_warmup_enabled = True
    s.ai_cold_start_threshold_seconds = 300.0
    s.nemotron_warmup_prompt = "Test warmup prompt"
    s.scene_change_resize_width = 640
    s.use_enrichment_service = False
    s.ai_max_concurrent_inferences = 4
    s.nemotron_use_guided_json = False
    s.nemotron_guided_json_fallback = True
    s.batch_coalescing_enabled = False
    s.batch_coalescing_max_size = 10
    s.batch_coalescing_time_window = 5.0
    s.priority_queue_enabled = False
    s.priority_high_labels = ["weapon", "intruder", "fire"]
    s.priority_medium_labels = ["person", "unknown"]
    return s


def _detections():
    from backend.models.detection import Detection

    return [
        Detection(
            id=1,
            camera_id=CAMERA_ID,
            file_path=f"/export/{CAMERA_ID}/a.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=2,
            camera_id=CAMERA_ID,
            file_path=f"/export/{CAMERA_ID}/b.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
        ),
    ]


async def _ab_run(risk_data=POP, llm_exc=None, exc_attrs=None):
    """Run shipped analyze_batch with the platform fully stubbed; return observables.

    risk_data defaults to the POPULATED dict; pass {} for the shipped-.get-defaults
    leg, or risk_data=None + llm_exc to drive the except leg.
    """
    from backend.core.redis import RedisClient
    from backend.models.camera import Camera
    from backend.models.event import Event
    from backend.services.nemotron_analyzer import NemotronAnalyzer

    detections = _detections()
    camera = Camera(
        id=CAMERA_ID, name="Front Door Camera", folder_path="/export/cam", status="online"
    )

    redis = MagicMock(spec=RedisClient)
    redis.get = AsyncMock(return_value=None)  # idempotency miss
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)

    # Stub service facade: keeps cache/auto-tuner off the real-redis path and
    # pins the session.execute stream to exactly [camera SELECT, junction INSERT].
    facade = MagicMock()
    facade.fetch_detections = AsyncMock(return_value=detections)
    facade.get_prompt_auto_tuner = MagicMock(
        return_value=MagicMock(get_tuning_context=AsyncMock(return_value=""))
    )
    cache_stub = MagicMock()
    cache_stub.invalidate_event_stats = AsyncMock()
    facade.get_cache_service = AsyncMock(return_value=cache_stub)

    with patch(f"{MOD}.get_settings", autospec=True, return_value=_settings()):
        analyzer = NemotronAnalyzer(redis_client=redis, service_facade=facade)

    if llm_exc is None:
        analyzer._call_llm = AsyncMock(return_value=risk_data)
    else:
        for k, v in (exc_attrs or {}).items():
            setattr(llm_exc, k, v)
        analyzer._call_llm = AsyncMock(side_effect=llm_exc)
    analyzer._get_enriched_context = AsyncMock(return_value=None)
    analyzer._get_recent_scene_changes = AsyncMock(return_value=[])
    analyzer._get_enrichment_result_from_data = AsyncMock(return_value=None)
    analyzer._get_household_context = AsyncMock(return_value=None)
    analyzer._enrich_with_trajectory_analysis = AsyncMock(return_value=None)
    analyzer._broadcast_event = AsyncMock(return_value=None)
    analyzer._trigger_event_created_webhook = AsyncMock(return_value=None)
    analyzer._enqueue_for_evaluation = AsyncMock(return_value=None)

    session = AsyncMock()
    exec_calls = []
    camera_result = MagicMock()
    camera_result.scalar_one_or_none.return_value = camera
    insert_result = MagicMock()

    async def execute(query, *a, **k):
        exec_calls.append((query, a, k))
        return camera_result if len(exec_calls) == 1 else insert_result

    session.execute = execute
    added = []
    session.add = lambda o: added.append(o)

    async def flush(*a, **k):
        for o in added:
            if getattr(o, "id", None) is None and (
                isinstance(o, Event) or type(o).__name__ == "LLMInteraction"
            ):
                o.id = EVENT_ID

    session.flush = flush
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = None

    audit_service = MagicMock()
    audit_service.create_partial_audit = MagicMock(return_value=MagicMock(id=99))

    patchers = {
        "get_session": patch(f"{MOD}.get_session", autospec=True),
        "add_span_event": patch(f"{MOD}.add_span_event", autospec=True),
        "audit": patch(f"{AUDIT_MOD}.get_audit_service", autospec=True, return_value=audit_service),
        "log_debug": patch(f"{MOD}.logger.debug", autospec=True),
        "log_error": patch(f"{MOD}.logger.error", autospec=True),
    }
    for m in METRIC_FNS:
        patchers[m] = patch(f"{MOD}.{m}", autospec=True)

    started = {name: p.start() for name, p in patchers.items()}
    try:
        started["get_session"].return_value = ctx
        event = await analyzer.analyze_batch(
            batch_id=BATCH_ID, camera_id=CAMERA_ID, detection_ids=[1, 2]
        )
    finally:
        for p in patchers.values():
            p.stop()

    def calls_of(mock):
        return [SimpleNamespace(args=c.args, kwargs=c.kwargs) for c in mock.call_args_list]

    spans = calls_of(started["add_span_event"])
    debugs = calls_of(started["log_debug"])
    return SimpleNamespace(
        event=event,
        added=added,
        exec_calls=exec_calls,
        spans=spans,
        spans_by=lambda name: [s for s in spans if s.args[:1] == (name,)],
        metrics={m: calls_of(started[m]) for m in METRIC_FNS},
        debugs=debugs,
        debugs_matching=lambda msg: [d for d in debugs if d.args[:1] == (msg,)],
        errors=calls_of(started["log_error"]),
        audit=audit_service.create_partial_audit,
    )


def _duration(int_val):
    assert isinstance(int_val, int) and 0 <= int_val < 60_000, f"bad duration {int_val!r}"


class TestSuccessLegObservability:
    """Lines 2798-2818: metrics / span / debug trio emitted after a good _call_llm."""

    async def test_ai_duration_metric_literal_nemotron_pop(self):
        """Kills analyze_batch__mutmut_320, analyze_batch__mutmut_324,
        analyze_batch__mutmut_325 (320 is twin-carried with 372; 324/376 and
        325/377 are twin pairs whose FAIL-leg occurrence is pinned by
        test_fail_leg_duration_and_pipeline_error_literals):
        observe_ai_request_duration("nemotron", ...) at line 2798 with arg
        ->None / "XXnemotronXX" / "NEMOTRON". Pins exactly one call with args
        ("nemotron", <float in [0, 60)>) and kwargs {} on the POPULATED run.
        """
        r = await _ab_run()
        calls = r.metrics["observe_ai_request_duration"]
        assert len(calls) == 1
        assert calls[0].args[0] == "nemotron"
        assert len(calls[0].args) == 2
        assert isinstance(calls[0].args[1], float) and 0 <= calls[0].args[1] < 60
        assert calls[0].kwargs == {}

    async def test_span_complete_name_and_dict_pop(self):
        """Kills analyze_batch__mutmut_326, _327, _328, _329, _330, _331, _334,
        _335, _336, _338, _340, _341, _343, _344, _345, _347, _349, _350, _353,
        _354: the add_span_event("nemotron_analysis.complete", {...}) site (lines
        2801-2809) on the POPULATED leg — name ->None (326) / name removed (328)
        / renamed XX (330) / upper (331), attributes arg ->None (327) / removed
        (329), dict-key renames "XXrisk.scoreXX"/"RISK.SCORE" (334/335),
        "XXrisk.levelXX"/"RISK.LEVEL" (343/344), "XXanalysis.duration_msXX"/
        "ANALYSIS.DURATION_MS" (353/354), and get-key renames risk_data.get(None)
        (336), get(0) (338), "XXrisk_scoreXX"/"RISK_SCORE" (340/341),
        get(None)/"XXrisk_levelXX"/"RISK_LEVEL" (345/349/350), get("unknown")
        (347) — each yields a value != the populated one or breaks the call.
        Pins args EXACTLY: ("nemotron_analysis.complete", {"batch.id",
        "risk.score": 75, "risk.level": "high", "analysis.duration_ms": int}).
        """
        r = await _ab_run()
        hits = r.spans_by("nemotron_analysis.complete")
        assert len(hits) == 1
        s = hits[0]
        assert len(s.args) == 2 and s.kwargs == {}
        d = dict(s.args[1])
        assert set(d) == {"batch.id", "risk.score", "risk.level", "analysis.duration_ms"}
        _duration(d["analysis.duration_ms"])
        assert {k: v for k, v in d.items() if k != "analysis.duration_ms"} == {
            "batch.id": BATCH_ID,
            "risk.score": 75,
            "risk.level": "high",
        }

    async def test_span_complete_shipped_defaults_empty(self):
        """Kills analyze_batch__mutmut_337, _339, _342, _346, _348, _351, _352:
        the risk_data.get("risk_score", 0) / risk_data.get("risk_level",
        "unknown") DEFAULTS at lines 2805-2806 -> None (337/346), no-default
        (339/348), 1 (342), "XXunknownXX" (351), "UNKNOWN" (352). With
        risk_data={} shipped emits risk.score 0 and risk.level "unknown"
        (MEASURED pre-#6678). P0.3 drift re-pin (#6678): a NULL score now
        reads _span_risk_value(None) == "unverified" and a NULL level
        `or "unverified"` -- honest-incomparable, never a laundered 0.
        """
        r = await _ab_run(risk_data={})
        hits = r.spans_by("nemotron_analysis.complete")
        assert len(hits) == 1
        s = hits[0]
        assert len(s.args) == 2
        d = dict(s.args[1])
        assert set(d) == {"batch.id", "risk.score", "risk.level", "analysis.duration_ms"}
        _duration(d["analysis.duration_ms"])
        assert {k: v for k, v in d.items() if k != "analysis.duration_ms"} == {
            "batch.id": BATCH_ID,
            "risk.score": "unverified",  # P0.3: NULL score marker, not 0
            "risk.level": "unverified",  # P0.3: `or`-fallback, not `get` default
        }

    async def test_debug_completed_message_and_extra_pop(self):
        """Kills analyze_batch__mutmut_355, _356, _358, _359, _360, _363, _364
        (359/360 and 363/364 are twin-carried with 392/393 and 396/397, whose
        second occurrence at the logger.error extra is pinned by
        test_fail_leg_error_log_exact): the logger.debug(f"LLM analysis
        completed for batch {batch_id}", extra={camera_id, batch_id,
        duration_ms}) site (lines 2811-2818) — message ->None (355), extra
        ->None (356) / removed (358), key renames "XXcamera_idXX"/"CAMERA_ID"
        (359/360) and "XXduration_msXX"/"DURATION_MS" (363/364). Pins the single
        debug call with EXACT message and extra dict.
        """
        r = await _ab_run()
        hits = r.debugs_matching(f"LLM analysis completed for batch {BATCH_ID}")
        assert len(hits) == 1
        d = hits[0]
        assert "extra" in d.kwargs and len(d.kwargs) == 1
        extra = dict(d.kwargs["extra"])
        assert set(extra) == {"camera_id", "batch_id", "duration_ms"}
        _duration(extra["duration_ms"])
        assert {k: v for k, v in extra.items() if k != "duration_ms"} == {
            "camera_id": CAMERA_ID,
            "batch_id": BATCH_ID,
        }


class TestFailureLegObservability:
    """Lines 2823-2842: metrics, error log, and fallback dict on LLM failure."""

    async def test_fail_leg_duration_and_pipeline_error_literals(self):
        """Kills analyze_batch__mutmut_372, _376, _377 (second occurrences —
        twin-carried with 320/324/325 — of the observe_ai_request_duration arg
        shapes at line 2823), analyze_batch__mutmut_378, _379, _380
        (record_pipeline_error("nemotron_analysis_error") -> None/"XX...XX"/
        "NEMOTRON_ANALYSIS_ERROR" at line 2824). Pins both calls exactly on the
        FAIL run: one observe_ai_request_duration("nemotron", <float in [0,60)>)
        and one record_pipeline_error("nemotron_analysis_error",).
        """
        r = await _ab_run(risk_data=None, llm_exc=ValueError("llmboom"))
        ai = r.metrics["observe_ai_request_duration"]
        assert len(ai) == 1
        assert ai[0].args[0] == "nemotron" and len(ai[0].args) == 2
        assert isinstance(ai[0].args[1], float) and 0 <= ai[0].args[1] < 60
        assert ai[0].kwargs == {}
        err = r.metrics["record_pipeline_error"]
        assert len(err) == 1
        assert err[0].args == ("nemotron_analysis_error",) and err[0].kwargs == {}

    async def test_fail_leg_error_log_exact(self):
        """Kills analyze_batch__mutmut_381, _382, _383, _384, _385, _387, _388,
        _389, _390, _391, _392, _393, _396, _397, _398, _399, _400: the
        logger.error("LLM analysis failed for batch", extra={camera_id,
        batch_id, duration_ms, error: sanitize_error(e)}, exc_info=True) site
        (lines 2825-2835) — sanitized_error None / sanitize_error(None)
        (381/382, shipped yields 'llmboom' / mutant yields None / 'None'),
        message ->None (383) / "XX..." (389) / lower (390) / upper (391), extra
        ->None (384) / removed (387), key renames "XXcamera_idXX"/"CAMERA_ID"
        (392/393 — twin-carried first occurrences at the debug site),
        "XXduration_msXX"/"DURATION_MS" (396/397), "XXerrorXX"/"ERROR"
        (398/399), and exc_info ->None (385) / removed (388) / False (400).
        Pins the single error call EXACTLY (MEASURED).
        """
        r = await _ab_run(risk_data=None, llm_exc=ValueError("llmboom"))
        assert len(r.errors) == 1
        e = r.errors[0]
        assert e.args == ("LLM analysis failed for batch",)
        kw = dict(e.kwargs)
        assert kw.pop("exc_info", "MISSING") is True
        assert "extra" in kw
        extra = dict(kw.pop("extra"))
        assert set(extra) == {"camera_id", "batch_id", "duration_ms", "error"}
        _duration(extra["duration_ms"])
        assert {k: v for k, v in extra.items() if k != "duration_ms"} == {
            "camera_id": CAMERA_ID,
            "batch_id": BATCH_ID,
            "error": "llmboom",
        }
        assert kw == {}

    async def test_fail_leg_fallback_strings_persisted(self):
        """Kills analyze_batch__mutmut_411, _416, _417: the fallback risk_data
        summary/reasoning LITERAL values (lines 2839-2840) -> XX-wrapped /
        lower-cased. The Event row read-backs .get("summary", ...) /
        .get("reasoning", ...) at lines 2886-2887 sees the present fallback keys,
        so the persisted Event carries the EXACT shipped strings.
        """
        r = await _ab_run(risk_data=None, llm_exc=ValueError("llmboom"))
        assert r.event.risk_score == 50 and r.event.risk_level == "medium"
        assert r.event.summary == "Analysis unavailable - LLM service error"
        assert r.event.reasoning == "Failed to analyze detections due to service error"

    async def test_fail_leg_raw_response_getattr_to_llm_interaction(self):
        """Kills analyze_batch__mutmut_419, _420, _421, _423, _427, _428, _429:
        the "raw_response": getattr(e, "raw_completion", "") entry of the
        fallback dict (line 2841) — key renames "XXraw_responseXX"/
        "RAW_RESPONSE" (419/420), getattr(None, ...) (421), default ->None
        (423), attr renames "XXraw_completionXX"/"RAW_COMPLETION" (427/428),
        default ->"XXXX" (429). LLMInteraction read-backs
        risk_data.get("raw_response", "") at line 3016: shipped yields '' with a
        bare exception and 'RAWTEXT' when exc.raw_completion="RAWTEXT" (both
        MEASURED); each mutant changes one of those two legs.
        """
        plain = await _ab_run(risk_data=None, llm_exc=ValueError("llmboom"))
        inter = [o for o in plain.added if type(o).__name__ == "LLMInteraction"]
        assert len(inter) == 1
        assert inter[0].raw_response == ""
        raw = await _ab_run(
            risk_data=None,
            llm_exc=ValueError("llmboom2"),
            exc_attrs={"raw_completion": "RAWTEXT"},
        )
        inter2 = [o for o in raw.added if type(o).__name__ == "LLMInteraction"]
        assert len(inter2) == 1
        assert inter2[0].raw_response == "RAWTEXT"


class TestEventRow:
    """Lines 2879-2895: the Event(...) kwargs — values, defaults, removals."""

    async def test_event_row_started_ended_at_min_max(self):
        """Kills analyze_batch__mutmut_437, _438, _451, _452: Event(started_at=
        start_time / ended_at=end_time) at lines 2882-2883 -> None (437/438) and
        kwarg REMOVAL (451/452, leaves the mapped attribute unset -> read is
        None/raises, never the shipped datetime). Shipped carries min/max of the
        two detection times (MEASURED 14:30:00Z / 14:30:15Z).
        """
        r = await _ab_run()
        assert r.event.started_at == datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
        assert r.event.ended_at == datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC)

    async def test_event_row_populated_optional_fields(self):
        """Kills analyze_batch__mutmut_443, _445, _446, _447, _448, _457, _459,
        _460, _461, _462, _496, _497, _498, _500, _501, _502, _503, _504, _505,
        _506, _507, _508, _509, _510, _511: the llm_prompt / entities / flags /
        confidence_factors / recommended_action Event kwargs (lines 2888-2894)
        — arg ->None (443/445/446/447/448), kwarg REMOVAL (457/459/460/461/462;
        unset attribute reads None), and risk_data.get key ->None/renamed:
        get(None)/"XXllm_promptXX"/"LLM_PROMPT" (496/497/498),
        get(None)/"XXentitiesXX"/"ENTITIES" (500/501/502), flags family
        (503/504/505), confidence_factors family (506/507/508),
        recommended_action family (509/510/511). 443/535, 457/539, 496/542,
        497/543 and 498/544 are twin shapes — the audit-site occurrence (line
        2955) is pinned by test_audit_llm_prompt_kwarg_pop_exact; both keys of
        each pair are carried here and there. POPULATED risk_data ships all
        five values (MEASURED); every mutant yields None where shipped is a
        value.
        """
        r = await _ab_run()
        assert r.event.llm_prompt == "PROMPT"
        assert r.event.entities == [{"k": "person"}]
        assert r.event.flags == [{"name": "loitering"}]
        assert r.event.confidence_factors == {"motion": 0.7}
        assert r.event.recommended_action == "check camera"

    async def test_event_row_shipped_defaults_empty_risk_data(self):
        """Kills analyze_batch__mutmut_464, _466, _469, _471, _473, _476, _477,
        _479, _481, _484, _485, _486, _488, _490, _493, _494, _495: the Event()
        risk_data.get DEFAULTS at lines 2884-2887 — risk_score default 50 ->
        None (464) / absent (466) / 51 (469); risk_level default "medium" ->
        None (471) / absent (473) / "XXmediumXX" (476) / "MEDIUM" (477);
        summary default "No summary available" -> None (479) / absent (481) /
        "XXNo summary availableXX" (484) / "no summary available" (485) /
        "NO SUMMARY AVAILABLE" (486); reasoning default "No reasoning
        available" -> None (488) / absent (490) / "XXNo reasoning
        availableXX" (493) / "no reasoning available" (494) / "NO REASONING
        AVAILABLE" (495). With risk_data={} shipped persists 50 / 'medium' /
        'No summary available' / 'No reasoning available' (MEASURED).
        """
        r = await _ab_run(risk_data={})
        assert r.event.risk_score == 50
        assert r.event.risk_level == "medium"
        assert r.event.summary == "No summary available"
        assert r.event.reasoning == "No reasoning available"
        assert r.event.llm_prompt is None
        assert r.event.entities is None and r.event.flags is None
        assert r.event.confidence_factors is None and r.event.recommended_action is None


class TestJunctionInsert:
    """Lines 2913-2923: the event_detections ON CONFLICT DO NOTHING insert."""

    async def test_junction_sql_columns_and_on_conflict_exact(self):
        """Kills analyze_batch__mutmut_514, _515, _516, _517, _518: the VALUES
        dict keys {"event_id": event.id, "detection_id": det_id} (line 2915)
        renamed "XXevent_idXX"/"EVENT_ID"/"XXdetection_idXX"/"DETECTION_ID"
        (514-517 — SQLAlchemy rejects the unknown keys / drops the real bind
        params) and stmt = None (518, lines 2918-2922 — the executed object is
        no longer the INSERT). Pins exactly TWO session.execute calls and the
        compiled SQL of the second: INSERT INTO event_detections (event_id,
        detection_id, created_at) VALUES (%(event_id_m0)s,
        %(detection_id_m0)s, ...) ON CONFLICT (event_id, detection_id) DO
        NOTHING (MEASURED).
        """
        from sqlalchemy.dialects import postgresql

        r = await _ab_run()
        assert len(r.exec_calls) == 2
        stmt = r.exec_calls[1][0]
        assert type(stmt).__name__ == "Insert"
        sql = str(stmt.compile(dialect=postgresql.dialect())).lower()
        assert "insert into event_detections (event_id, detection_id, created_at)" in sql
        assert "%(event_id_m0)s" in sql and "%(detection_id_m0)s" in sql
        assert "on conflict (event_id, detection_id) do nothing" in sql


class TestAuditLlmPrompt:
    """Lines 2953-2958: create_partial_audit(llm_prompt=risk_data.get(...))."""

    async def test_audit_llm_prompt_kwarg_pop_exact(self):
        """Kills analyze_batch__mutmut_535, _539, _542, _543, _544 (first
        occurrences twin-carried with 443, 457, 496, 497, 498 at the Event row):
        the audit-site llm_prompt=risk_data.get("llm_prompt") kwarg (line 2955)
        -> None (535), kwarg REMOVAL (539 — the create_partial_audit call loses
        llm_prompt), get(None) (542), get("XXllm_promptXX") (543),
        get("LLM_PROMPT") (544). POPULATED run pins exactly one call with args
        () and kwargs EXACTLY {event_id: 7, llm_prompt: 'PROMPT',
        enriched_context: None, enrichment_result: None} plus that audit object
        added to the session.
        """
        r = await _ab_run()
        calls = r.audit.call_args_list
        assert len(calls) == 1
        assert calls[0].args == ()
        assert dict(calls[0].kwargs) == {
            "event_id": EVENT_ID,
            "llm_prompt": "PROMPT",
            "enriched_context": None,
            "enrichment_result": None,
        }
        assert r.audit.return_value in r.added
