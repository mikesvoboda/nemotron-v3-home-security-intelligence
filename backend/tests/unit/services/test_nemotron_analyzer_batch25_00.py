"""Batch-25 kill battery — chunk "NemotronAnalyzer.analyze_batch#chunk1" (129 keys).

Adjudication basis
------------------
All 129 keys are survivors of backend/services/nemotron_analyzer.py::analyze_batch
(shipped lines 2341-3140). Shape groups: feed.json
functions['xǁNemotronAnalyzerǁanalyze_batch'].shapes groups 0-107. Every shape was
adjudicated against SHIPPED behavior probed end-to-end (probe harness under
/tmp/wp-batch25/probes/, same mock topology as this file).

Disposition summary (per-key, twins kept whole) — VERIFIED by an out-of-repo
red-check of all 129 keys (/tmp/wp-batch25/probes/c00/, plugin
/tmp/wp-batch25/probes/c00/c00plugin.py binds the reconstructed variant of
analyze_batch — lifted read-only from the instrumented copy — into the LIVE
module dict of backend.services.nemotron_analyzer, so every autospec patch here
is observed; nothing in the repo is written, mutmut is never run):

  killed_by_draft: NONE. Measured: for every one of the 129 keys the repo
      analyze_batch tests (backend/tests/unit/services/test_nemotron_analyzer.py,
      22 selected by -k analyze_batch) still pass under the mutant — the repo
      suite regex-SEARCHES messages and never pins the span/log/extra payloads,
      so not even key 3 dies there (mutant message
      "XXRedis client not initializedXX" satisfies match="Redis client not
      initialized"; the exact-equality pin in
      test_redis_missing_raises_exact_runtime_message is what kills it).
      The /tmp/wp-batch25/test_nemotron_analyzer_batch25.py draft battery
      targets _parse_llm_response / _validate_risk_data / _extract_json_objects
      only — it touches no analyze_batch occurrence.
  equivalent: ONE key, mutmut_98 — `if (detections)` ->
      `if (detections) or True` at :2476. Shipped raises
      ValueError("No detections found for batch ...") at :2454-2459 whenever
      `not detections`, and `detections` is not rebound between :2454 and the
      avg_confidence ternary (:2474-2478), so the ternary's else-`0.5` operand
      is unreachable and `(detections) or True` is truthy on every reachable
      path — a literal value-no-op. Confirmed empirically: with 98 bound all
      17 tests still pass (red.json: "98": []).
  killable: the remaining 128 keys — this file (red-check killed 128/129).

Twin-group notes (occurrence order among identical minus/plus shapes):
  * "batch.id" XX group 43,110,249,332,635,700 (+ UPPER twins 44,111,250,333,
    636,701): the six add_span_event dicts (batch_analysis.start :2411,
    batch_priority.calculated :2484, nemotron_analysis.start :2752,
    nemotron_analysis.complete :2804, database_write.complete :3076,
    batch_analysis.complete :3131). The pre-LLM pair is asserted by
    test_start_phase_span_dicts_exact and the post-LLM pair by
    test_llm_and_write_phase_span_dicts_exact, so both full groups are carried.
  * "camera.id" XX group 45,251,704 and UPPER group 46,252,705: lines
    :2412/:2753/:3133 — the same two dict-equality tests kill all six.
  * "batch_id" debug-extra XX group 130,361,394 (+ 131,362,395): debug/info/
    error extras at :2495 (Batch priority calculated), :2815 (LLM analysis
    completed), :2830 (LLM analysis failed — only on the _call_llm failure
    path). 130/131 die in test_batch_priority_debug_extra_exact; 361/362 and
    394/395 die in
    test_batch_id_pinned_in_llm_completion_and_failure_extras, which drives
    BOTH the success and the LLM-failure path so each group stays whole.
  * "priority" XX group 112,132 (+ UPPER 113,133): span :2485 and debug extra
    :2497 — 112/113 die in test_start_phase_span_dicts_exact, 132/133 in
    test_batch_priority_debug_extra_exact.
  * "confidence" XX group 170,271: :2540 (detections_for_enrichment dict) and
    :2768 (_det_dicts handed to _call_llm as detection_dicts) — both payloads
    are asserted by test_detection_dicts_and_enrichment_payload_exact.

Mock-patch ratchet: every patch() call below carries autospec=True (or
new=/side_effect values on an autospec'd target).

GREEN-CHECK: .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_00.py -p no:cacheprovider -o addopts= -q
RED-CHECK (already run, out-of-repo — results /tmp/wp-batch25/probes/c00/red.json):
    WP25_MUT=<num> PYTHONPATH=/tmp/wp-batch25:/tmp/wp-batch25/probes/c00 \
      .venv/bin/python -m pytest <this file> -p no:cacheprovider -p c00plugin \
      -o addopts= -q --tb=no          # expect >=1 FAILED for every key but 98
"""

from __future__ import annotations

import contextlib
import logging
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# Part file lives outside the repo tree, so backend/tests/conftest.py does NOT
# apply. Mirror the minimum env vars the repo conftest sets (values copied from
# backend/tests/conftest.py:107,114,363,367,385 — do not invent).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

from sqlalchemy.engine import Result, ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.nemotron_analyzer import NemotronAnalyzer

KEY = "backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_"

_FORMATTED = "FORMATTED-DETECTIONS-LIST"
_ENRICHED = "ENRICHED CTX"
_HEALTH = "HEALTH CTX"
_TUNING = "AUTO TUNING CTX"
_SCENE_SENTINEL = [{"scene": "SCENE-SENTINEL"}]
_BASE_TIME = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixtures (mirrors backend/tests/unit/services/test_nemotron_analyzer.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_client():
    from backend.core.redis import RedisClient

    mock_client = MagicMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def mock_settings():
    from backend.core.config import Settings

    mock = MagicMock(spec=Settings)
    mock.nemotron_url = "http://localhost:8091"
    mock.nemotron_api_key = None
    mock.ai_connect_timeout = 10.0
    mock.nemotron_read_timeout = 120.0
    mock.ai_health_timeout = 5.0
    mock.nemotron_max_retries = 2
    mock.severity_low_max = 29
    mock.severity_medium_max = 59
    mock.severity_high_max = 84
    mock.nemotron_context_window = 4096
    mock.nemotron_max_output_tokens = 1536
    mock.context_utilization_warning_threshold = 0.80
    mock.context_truncation_enabled = True
    mock.llm_tokenizer_encoding = "cl100k_base"
    mock.image_quality_enabled = False
    mock.ai_warmup_enabled = True
    mock.ai_cold_start_threshold_seconds = 300.0
    mock.nemotron_warmup_prompt = "Test warmup prompt"
    mock.scene_change_resize_width = 640
    mock.use_enrichment_service = False
    mock.ai_max_concurrent_inferences = 4
    mock.nemotron_use_guided_json = False
    mock.nemotron_guided_json_fallback = True
    mock.batch_coalescing_enabled = False
    mock.batch_coalescing_max_size = 10
    mock.batch_coalescing_time_window = 5.0
    mock.priority_queue_enabled = False
    mock.priority_high_labels = ["weapon", "intruder", "fire"]
    mock.priority_medium_labels = ["person", "unknown"]
    return mock


@pytest.fixture
def analyzer(mock_redis_client, mock_settings):
    with (
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            return_value=mock_settings,
            autospec=True,
        ),
        patch("backend.services.severity.get_settings", return_value=mock_settings, autospec=True),
        patch(
            "backend.services.token_counter.get_settings",
            return_value=mock_settings,
            autospec=True,
        ),
        patch("backend.core.config.get_settings", return_value=mock_settings, autospec=True),
        patch(
            "backend.services.inference_semaphore.get_settings",
            return_value=mock_settings,
            autospec=True,
        ),
    ):
        from backend.services.analyzer_facade import reset_analyzer_facade
        from backend.services.inference_semaphore import reset_inference_semaphore
        from backend.services.severity import reset_severity_service
        from backend.services.token_counter import reset_token_counter

        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()
        yield NemotronAnalyzer(redis_client=mock_redis_client)
        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _camera():
    return Camera(
        id="front_door",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door",
        status="online",
    )


def _detections():
    return [
        Detection(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img1.jpg",
            detected_at=_BASE_TIME,
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=2,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img2.jpg",
            detected_at=_BASE_TIME.replace(minute=31),
            object_type="car",
            confidence=0.88,
        ),
    ]


def _many_detections(n=12):
    """ids n..1 descending: list(set()) iteration order is unpredictable, so the
    payload id ORDER is left to shipped sort and only per-id VALUES are pinned."""
    return [
        Detection(
            id=i,
            camera_id="front_door",
            file_path=f"/export/foscam/front_door/img{i}.jpg",
            detected_at=_BASE_TIME.replace(minute=0, second=i % 60, microsecond=i),
            object_type=f"type{i}",
            # confidence encodes the id so per-dict values are attributable
            confidence=i / 100,
        )
        for i in range(n, 0, -1)
    ]


_DEFAULT_RISK = {
    "risk_score": 75,
    "risk_level": "high",
    "summary": "Person and vehicle at unusual hour",
    "reasoning": "harness",
}


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@contextlib.contextmanager
def _capture_logs():
    logger = logging.getLogger("backend.services.nemotron_analyzer")
    handler = _LogCapture()
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def _compiled(query):
    try:
        return str(query.compile(compile_kwargs={"literal_binds": True}))
    except Exception:  # non-SQLAlchemy statement (or un-renderable) — keep raw str
        return f"NOT-COMPILEABLE {query!r}"


def _find(records, *, message=None, level=None):
    return [
        r
        for r in records
        if (message is None or r.getMessage() == message) and (level is None or r.levelno == level)
    ]


def _span_attrs(spans, name):
    """Return the attrs dict of the unique span-event call named `name`."""
    matches = [attrs for (n, attrs) in spans if n == name]
    assert len(matches) == 1, f"expected exactly one add_span_event({name!r}), got {len(matches)}"
    return matches[0]


class _Driven:
    """Observables captured from one analyze_batch drive."""

    def __init__(self):
        self.spans = []
        self.logctx = []
        self.fchc = []
        self.tuner = []
        self.scene = []
        self.enriched = []
        self.fmt = []
        self.enrich = []
        self.call_llm = []
        self.rec_by_cam = []
        self.redis_keys = []
        self.event = None
        self.session = None
        self.session_repr = ""
        self.queries = []


async def _run_batch(
    analyzer,
    mock_redis_client,
    *,
    camera_row="default",
    detections=None,
    risk=None,
    llm_exc=None,
    redis_side=None,
    batch_kwargs=None,
    tuning_return="AUTO TUNING CTX",
    tuning_exc=None,
):
    """Drive analyze_batch end-to-end against in-memory doubles (no DB/Redis).

    Mirrors the repo harness (test_nemotron_analyzer.py::test_analyze_batch_success)
    plus autospec'd spies on the observability call sites. The camera / events /
    detections queries are routed by compiled SQL prefix so the Camera select's
    literal bind values are observable (kills the where-mutants).
    """
    driven = _Driven()
    camera_row = _camera() if camera_row == "default" else camera_row
    dets = _detections() if detections is None else detections

    mock_session = AsyncMock(spec=AsyncSession)
    cam_res = MagicMock(spec=Result)
    cam_res.scalar_one_or_none.return_value = camera_row
    det_res = MagicMock(spec=Result)
    scal = MagicMock(spec=ScalarResult)
    scal.all.return_value = dets
    det_res.scalars.return_value = scal
    generic = MagicMock(spec=Result)
    existing = Event(
        id=999,
        batch_id="b00",
        camera_id="front_door",
        started_at=_BASE_TIME,
        ended_at=_BASE_TIME.replace(minute=31),
        risk_score=75,
        risk_level="high",
        summary="Pre-existing",
        reasoning="R",
        reviewed=False,
    )
    event_res = MagicMock(spec=Result)
    event_res.scalar_one_or_none.return_value = existing
    queries = []

    async def _execute(query, *args, **kwargs):
        sql = _compiled(query)
        queries.append(sql)
        if sql.startswith("SELECT cameras."):
            return cam_res
        if sql.startswith("SELECT events."):
            return event_res
        if sql.startswith("SELECT detections."):
            return det_res
        return generic

    mock_session.execute = _execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    if redis_side is not None:
        mock_redis_client.get = AsyncMock(side_effect=redis_side)

    from backend.services.prompt_auto_tuner import PromptAutoTuner

    patches = {
        "span": patch(
            "backend.services.nemotron_analyzer.add_span_event",
            autospec=True,
        ),
        "get_session": patch(
            "backend.services.nemotron_analyzer.get_session",
            autospec=True,
        ),
        "logctx": patch(
            "backend.services.nemotron_analyzer.log_context",
            autospec=True,
        ),
        "fchc": patch(
            "backend.services.nemotron_analyzer.format_camera_health_context",
            autospec=True,
            return_value="HEALTH CTX",
        ),
        "tuner": patch.object(PromptAutoTuner, "get_tuning_context", autospec=True),
        "enrich": patch.object(analyzer, "_get_enrichment_result_from_data", autospec=True),
        "house": patch.object(analyzer, "_get_household_context", autospec=True),
        "traj": patch.object(analyzer, "_enrich_with_trajectory_analysis", autospec=True),
        "enriched": patch.object(analyzer, "_get_enriched_context", autospec=True),
        "scene": patch.object(analyzer, "_get_recent_scene_changes", autospec=True),
        "fmt": patch.object(analyzer, "_format_detections", autospec=True),
        "webhook": patch.object(analyzer, "_trigger_event_created_webhook", autospec=True),
        "broadcast": patch.object(analyzer, "_broadcast_event", autospec=True),
        "rec_by_cam": patch(
            "backend.services.nemotron_analyzer.record_event_by_camera", autospec=True
        ),
        "duration": patch(
            "backend.services.nemotron_analyzer.observe_stage_duration", autospec=True
        ),
        "created": patch("backend.services.nemotron_analyzer.record_event_created", autospec=True),
        "ai_duration": patch(
            "backend.services.nemotron_analyzer.observe_ai_request_duration", autospec=True
        ),
        "pipe_error": patch(
            "backend.services.nemotron_analyzer.record_pipeline_error", autospec=True
        ),
        "audit": patch(
            "backend.services.pipeline_quality_audit_service.get_audit_service",
            autospec=True,
            side_effect=RuntimeError("audit disabled in harness"),
        ),
        "cache": patch(
            "backend.services.analyzer_facade.AnalyzerServiceFacade.get_cache_service",
            autospec=True,
            side_effect=RuntimeError("cache disabled in harness"),
        ),
        "call_llm": patch.object(
            analyzer,
            "_call_llm",
            autospec=True,
            **(
                {"side_effect": llm_exc}
                if llm_exc
                else {"return_value": dict(risk or _DEFAULT_RISK)}
            ),
        ),
    }
    with contextlib.ExitStack() as stack:
        spies = {name: stack.enter_context(cm) for name, cm in patches.items()}
        spies["tuner"].return_value = tuning_return
        if tuning_exc is not None:
            spies["tuner"].side_effect = tuning_exc
        spies["enrich"].return_value = None
        spies["house"].return_value = ""
        spies["traj"].return_value = None
        spies["enriched"].return_value = "ENRICHED CTX"
        spies["scene"].return_value = [{"scene": "SCENE-SENTINEL"}]
        spies["fmt"].return_value = "FORMATTED-DETECTIONS-LIST"
        spies["webhook"].return_value = None
        spies["broadcast"].return_value = None
        ctx = AsyncMock(spec=AsyncSession)
        ctx.__aenter__.return_value = mock_session
        ctx.__aexit__.return_value = None
        spies["get_session"].return_value = ctx
        kwargs = batch_kwargs or {
            "batch_id": "b00",
            "camera_id": "front_door",
            "detection_ids": [1, 2],
        }
        event = await analyzer.analyze_batch(**kwargs)

    span_spy = spies["span"]
    logctx_spy = spies["logctx"]
    fchc_spy = spies["fchc"]
    tuner_spy = spies["tuner"]
    scene_spy = spies["scene"]
    enriched_spy = spies["enriched"]
    fmt_spy = spies["fmt"]
    enrich_spy = spies["enrich"]
    call_llm_spy = spies["call_llm"]
    rec_by_cam_spy = spies["rec_by_cam"]
    driven.event = event
    driven.spans = [
        (
            c.args[0] if c.args else c.kwargs.get("name"),
            c.args[1] if len(c.args) > 1 else c.kwargs.get("attributes"),
        )
        for c in span_spy.call_args_list
    ]
    driven.logctx = [(list(c.args), dict(c.kwargs)) for c in logctx_spy.call_args_list]
    driven.fchc = [((repr(c.args[0]), c.args[1]), dict(c.kwargs)) for c in fchc_spy.call_args_list]
    driven.tuner = [(list(c.args), dict(c.kwargs)) for c in tuner_spy.call_args_list]
    driven.scene = [[repr(a) for a in c.args] for c in scene_spy.call_args_list]
    driven.enriched = [[repr(a) for a in c.args] for c in enriched_spy.call_args_list]
    driven.fmt = [
        [d.id for d in c.args[1]] if len(c.args) > 1 else [repr(a) for a in c.args]
        for c in fmt_spy.call_args_list
    ]
    driven.enrich = [list(c.args) for c in enrich_spy.call_args_list]
    driven.call_llm = [
        {"args": [repr(a) for a in c.args], "kwargs": dict(c.kwargs)}
        for c in call_llm_spy.call_args_list
    ]
    driven.rec_by_cam = [tuple(c.args) for c in rec_by_cam_spy.call_args_list]
    driven.redis_keys = [c.args[0] for c in mock_redis_client.get.call_args_list]
    driven.queries = queries
    driven.session = mock_session
    driven.session_repr = repr(mock_session)
    return driven


# ---- APPEND MARKER A ----


# ---------------------------------------------------------------------------
# Tests (each docstring names the exact mutant keys it kills)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_missing_raises_exact_runtime_message(analyzer):
    """Kills __mutmut_3.

    With _redis falsy analyze_batch must raise RuntimeError whose message is
    EXACTLY "Redis client not initialized". The repo test
    test_analyze_batch_no_redis_client only regex-SEARCHES that substring,
    so the XX-prefixed mutant message still passes IT — the exact-equality
    pin here is what kills mutant 3 ("XXRedis client not initializedXX").
    This is why key 3 adjudicates killable-here, not killed_by_draft.
    """
    analyzer._redis = None
    with pytest.raises(RuntimeError) as excinfo:
        await analyzer.analyze_batch("b00")
    assert str(excinfo.value) == "Redis client not initialized"


@pytest.mark.asyncio
async def test_idempotency_hit_pins_info_log_and_event_lookup(analyzer, mock_redis_client):
    """Kills __mutmut_9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 21.

    Pre-seeds the idempotency key so analyze_batch takes the NEM-1725 early
    return. Pins the shipped INFO record exactly — message "Idempotency hit:
    batch already processed as event" at INFO level with extra
    {"batch_id": "b00", "event_id": 999} — and pins that the existing-Event
    lookup query used the stored id (WHERE events.id = 999, never NULL).

    Key map: 9 (message -> None), 13/14/15 (message XX/lower/UPPER), 10/12
    (extra -> None / extra arg removed: record loses batch_id/event_id),
    16/17 ("XXbatch_idXX"/"BATCH_ID"), 18/19 ("XXevent_idXX"/"EVENT_ID"),
    21 (_get_existing_event(None) -> WHERE events.id IS NULL).
    """

    async def redis_get(key):
        return "999" if key.startswith("batch_event:") else None

    with _capture_logs() as cap:
        driven = await _run_batch(analyzer, mock_redis_client, redis_side=redis_get)

    hits = _find(cap.records, message="Idempotency hit: batch already processed as event")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.levelno == logging.INFO
    assert hit.batch_id == "b00"
    assert hit.event_id == 999
    # the existing event was returned without running the pipeline
    assert driven.event.id == 999
    assert driven.call_llm == []
    assert "WHERE events.id = 999" in driven.queries[0]


@pytest.mark.asyncio
async def test_redis_detections_falsy_selects_empty_list_branch(analyzer, mock_redis_client):
    """Kills __mutmut_32.

    With the detections key present but EMPTY (""), shipped takes the else
    branch: detection_ids = [] -> ValueError("Batch b00 has no detections").
    Mutant 32 (`if (detections_data) or True`) always json.loads(""), which
    raises json.JSONDecodeError whose message ("Expecting value...") breaks
    the "has no detections" match below.
    """

    async def redis_get(key):
        if key.endswith(":camera_id"):
            return "front_door"
        if key.endswith(":detections"):
            return ""
        return None

    with pytest.raises(ValueError, match="has no detections"):
        await _run_batch(
            analyzer,
            mock_redis_client,
            redis_side=redis_get,
            batch_kwargs={"batch_id": "b00"},
        )


@pytest.mark.asyncio
async def test_camera_row_selected_by_id_and_name_flows_everywhere(analyzer, mock_redis_client):
    """Kills __mutmut_63, 64, 65, 66, 67, 68, 69.

    Session-1 camera fetch, happy row present. Pins the compiled SELECT —
    "FROM cameras ... WHERE cameras.id = 'front_door'" — and pins the camera
    NAME ("Front Door Camera", never the id/None) as it flows into the
    nemotron_analysis.start span attribute, the _call_llm camera_name kwarg,
    and record_event_by_camera's label.

    Key map: 63 (execute(None) — no camera query at all), 64 (where(None) ->
    WHERE NULL), 65 (select(None) -> "SELECT NULL AS anon_1"), 66 (!= ->
    WHERE cameras.id != 'front_door'), 67 (camera forced None -> shipped
    row-present path instead takes the id-as-name fallback + WARNING),
    68 (`if camera:` -> with a truthy row the branch inverts: id-as-name
    fallback instead of camera.name), 69 (camera_name = None -> None
    reaches span/kwarg/metric).
    """
    driven = await _run_batch(analyzer, mock_redis_client)

    assert driven.queries[0].startswith("SELECT cameras.")
    assert "WHERE cameras.id = 'front_door'" in driven.queries[0]
    assert driven.rec_by_cam == [("front_door", "Front Door Camera")]
    assert driven.call_llm[0]["kwargs"]["camera_name"] == "Front Door Camera"
    assert _span_attrs(driven.spans, "nemotron_analysis.start")["camera.name"] == (
        "Front Door Camera"
    )


@pytest.mark.asyncio
async def test_camera_row_missing_falls_back_to_id_with_warning(analyzer, mock_redis_client):
    """Kills __mutmut_63, 65, 68 (measured). Pins the shipped row-missing
    fallback the chunk's camera-name assertions lean on.

    With scalar_one_or_none() -> None shipped logs the WARNING "Camera not
    found, using ID as name" (extra camera_id) and uses the camera ID as the
    camera name everywhere (span, _call_llm, metrics label).

    Key map (red-check measured): 63 (execute(None) -> the mock session's
    query router sees str(None), the generic Result's scalar_one_or_none()
    returns a truthy MagicMock and the id-as-name/label pins break), 65
    (select(None) likewise routes away from the camera row), 68 (`if camera:`
    with camera None takes camera.name -> AttributeError crash). 67 (camera
    forced None) and 69 (camera_name = None) are behaviourally identical to
    shipped ON THIS path (camera is already None / the row-missing branch
    never reads camera.name) and are killed by the companion
    test_camera_row_selected_by_id_and_name_flows_everywhere instead —
    all of 63-69 stay in this chunk's killable set.
    """
    with _capture_logs() as cap:
        driven = await _run_batch(analyzer, mock_redis_client, camera_row=None)

    warns = _find(cap.records, message="Camera not found, using ID as name")
    assert len(warns) == 1
    assert warns[0].levelno == logging.WARNING
    assert warns[0].camera_id == "front_door"
    assert driven.call_llm[0]["kwargs"]["camera_name"] == "front_door"
    assert driven.rec_by_cam == [("front_door", "front_door")]
    assert _span_attrs(driven.spans, "nemotron_analysis.start")["camera.name"] == "front_door"


@pytest.mark.asyncio
async def test_log_context_receives_exact_tracing_kwargs(analyzer, mock_redis_client):
    """Kills __mutmut_49, 50, 51, 52, 53, 54.

    Pins both shipped log_context(...) invocations of analyze_batch exactly:
    first ([], {batch_id, camera_id, detection_count=2}), second
    ([], {batch_id, camera_id}). Any None-substitution (49/50/51) or dropped
    keyword breaks the equality: 52 removes the batch_id kwarg, 53 removes
    camera_id, and 54 removes the detection_count kwarg (the trailing-argument
    removal shape) so the first call loses "detection_count" — all measured
    KILLED by this test in the red-check, none equivalent.
    """
    driven = await _run_batch(analyzer, mock_redis_client)

    assert driven.logctx == [
        ([], {"batch_id": "b00", "camera_id": "front_door", "detection_count": 2}),
        ([], {"batch_id": "b00", "camera_id": "front_door"}),
    ]


@pytest.mark.asyncio
async def test_batch_analysis_started_info_message_exact(analyzer, mock_redis_client):
    """Kills __mutmut_55, 56, 57, 58.

    The pipeline-start marker is exactly the string "Batch analysis started"
    at INFO level inside the log_context scope. Mutants 55 (None), 56 (XX),
    57 (lower), 58 (UPPER) all fail the message-identity lookup.
    """
    with _capture_logs() as cap:
        await _run_batch(analyzer, mock_redis_client)

    started = _find(cap.records, message="Batch analysis started")
    assert len(started) == 1
    assert started[0].levelno == logging.INFO


@pytest.mark.asyncio
async def test_no_db_detections_raises_with_pinned_warning(analyzer, mock_redis_client):
    """Kills __mutmut_76, 77, 79, 80, 81, 82, 83, 84, 85, 86.

    Empty detection fetch -> ValueError("No detections found for batch b00")
    AFTER a WARNING whose message is exactly "No detections found in database
    for batch" carrying extra {"batch_id", "detection_ids"}. Key map: 76
    (message None), 80/81/82 (XX/lower/UPPER), 77 (extra None -> attributes
    missing), 83/84 ("XXbatch_idXX"/"BATCH_ID"), 85/86 ("XXdetection_idsXX"/
    "DETECTION_IDS"). 79 is the extra-arg-REMOVAL twin of 77's occurrence
    (record loses both attributes -> AttributeError) and is likewise in THIS
    chunk and killed here; key 78 (the lower-case twin) lives in chunk-2's
    ledger, not here.
    """
    with _capture_logs() as cap:
        with pytest.raises(ValueError, match="No detections found for batch b00"):
            await _run_batch(analyzer, mock_redis_client, detections=[])

    warns = _find(cap.records, message="No detections found in database for batch")
    assert len(warns) == 1
    assert warns[0].levelno == logging.WARNING
    assert warns[0].batch_id == "b00"
    assert warns[0].detection_ids == [1, 2]


@pytest.mark.asyncio
async def test_detections_list_and_avg_confidence_pins(analyzer, mock_redis_client):
    """Kills __mutmut_93, 96, 97, 99, 101.

    93: detections_list must be the real _format_detections return value —
    pinned via a sentinel from the autospec'd spy reaching _call_llm (None
    mutant sends None). 96/97/99/101: the DEBUG "Batch priority calculated"
    record's avg_confidence must be exactly mean(0.95, 0.88) = 0.915 —
    None-mutant (96), `and False` -> else-branch 0.5 (97), `* len` -> 3.66
    (99), `is None` filter -> 0.0 (101) all break the approx equality.
    """
    with _capture_logs() as cap:
        driven = await _run_batch(analyzer, mock_redis_client)

    assert driven.call_llm[0]["kwargs"]["detections_list"] == _FORMATTED
    dbg = _find(cap.records, message="Batch priority calculated")
    assert len(dbg) == 1
    assert dbg[0].levelno == logging.DEBUG
    assert dbg[0].avg_confidence == pytest.approx(0.915)


@pytest.mark.asyncio
async def test_start_phase_span_dicts_exact(analyzer, mock_redis_client):
    """Kills __mutmut_37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 104,
    105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 119,
    121, 122.

    Full-dict equality on the two pre-LLM span events:
      batch_analysis.start      {batch.id, camera.id, detection.count}
      batch_priority.calculated {batch.id, priority, priority_value,
                                 object_types_sample, detection_count}
    Key map: 37/104 (name -> None -> no matching call), 39/106 (name arg
    removed -> first positional becomes the dict), 38/105 (attrs -> None),
    40/107 (attrs arg removed entirely), 41/42 + 108/109 (name XX/UPPER),
    43/44 + 110/111 (batch.id XX/UPPER), 45/46 (camera.id XX/UPPER), 47/48
    (detection.count XX/UPPER), 112/113 (priority XX/UPPER), 114/115
    (priority_value key), 116/117 (object_types_sample key), 119 (joiner
    "XX,XX"), 121/122 (detection_count key). 120 ([11]-slice) is
    indistinguishable at 2 detections and is killed instead by
    test_detection_dicts_and_enrichment_payload_exact.
    """
    driven = await _run_batch(analyzer, mock_redis_client)

    assert _span_attrs(driven.spans, "batch_analysis.start") == {
        "batch.id": "b00",
        "camera.id": "front_door",
        "detection.count": 2,
    }
    assert _span_attrs(driven.spans, "batch_priority.calculated") == {
        "batch.id": "b00",
        "priority": "P1_HIGH",
        "priority_value": 3,
        "object_types_sample": "person,car",
        "detection_count": 2,
    }


@pytest.mark.asyncio
async def test_llm_and_write_phase_span_dicts_exact(analyzer, mock_redis_client):
    """Kills __mutmut_249, 250, 251, 252, 332, 333, 635, 636, 700, 701, 704, 705.

    Full-dict equality on the four post-LLM span events carries every
    "batch.id"/"camera.id" twin occurrence past the first two dicts:
    nemotron_analysis.start (249/250, 251/252), nemotron_analysis.complete
    (332/333), database_write.complete (635/636), batch_analysis.complete
    (700/701, 704/705 — also killed by sibling chunk-04's terminal-dict pin).
    """
    driven = await _run_batch(analyzer, mock_redis_client)

    assert _span_attrs(driven.spans, "nemotron_analysis.start") == {
        "batch.id": "b00",
        "camera.id": "front_door",
        "camera.name": "Front Door Camera",
        "detection.count": 2,
        "has_enriched_context": True,
        "has_enrichment_result": False,
        "has_household_context": False,
        "batch_priority": "P1_HIGH",
        "coalesced_count": 1,
    }
    complete = _span_attrs(driven.spans, "nemotron_analysis.complete")
    assert set(complete) == {"batch.id", "risk.score", "risk.level", "analysis.duration_ms"}
    assert complete["batch.id"] == "b00"
    assert complete["risk.score"] == 75
    assert complete["risk.level"] == "high"
    dbw = _span_attrs(driven.spans, "database_write.complete")
    assert set(dbw) == {"batch.id", "event.id", "detection.count", "enrichment_data.count"}
    assert dbw["batch.id"] == "b00"
    terminal = _span_attrs(driven.spans, "batch_analysis.complete")
    assert set(terminal) == {
        "batch.id",
        "event.id",
        "camera.id",
        "risk.score",
        "risk.level",
        "detection.count",
        "total.duration_ms",
    }
    assert terminal["batch.id"] == "b00"
    assert terminal["camera.id"] == "front_door"


@pytest.mark.asyncio
async def test_batch_priority_debug_extra_exact(analyzer, mock_redis_client):
    """Kills __mutmut_123, 124, 126, 127, 128, 129, 130, 131, 132, 133, 134,
    135, 136, 137.

    The DEBUG "Batch priority calculated" record: message exactly at DEBUG
    level (123 None / 127 XX / 128 lower / 129 UPPER) with extra exactly
    {batch_id: "b00", priority: "P1_HIGH", object_types: [...],
    avg_confidence: 0.915}. Key renames 130/131 (batch_id XX/UPPER),
    132/133 (priority XX/UPPER), 134/135 (object_types), 136/137
    (avg_confidence) drop the attribute -> AttributeError on access;
    124/126 (extra -> None / extra-arg removal) likewise strip every attribute
    from the record -> AttributeError. Measured kill set of THIS test (red
    check): 96, 97, 99, 101 (the avg_confidence value also flows through this
    record), 123, 124, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136,
    137 — all keys of THIS chunk; none of them adjudicates equivalent.
    """
    with _capture_logs() as cap:
        await _run_batch(analyzer, mock_redis_client)

    dbg = _find(cap.records, message="Batch priority calculated")
    assert len(dbg) == 1
    assert dbg[0].levelno == logging.DEBUG
    assert dbg[0].batch_id == "b00"
    assert dbg[0].priority == "P1_HIGH"
    assert dbg[0].object_types == ["person", "car"]
    assert dbg[0].avg_confidence == pytest.approx(0.915)


@pytest.mark.asyncio
async def test_batch_id_pinned_in_llm_completion_and_failure_extras(analyzer, mock_redis_client):
    """Kills __mutmut_361, 362, 394, 395 (measured; 130/131 — the other
    "batch_id" debug-extra twins — die in
    test_batch_priority_debug_extra_exact, keeping both groups whole).

    Both LLM-outcome log records must carry batch_id "b00":
      DEBUG "LLM analysis completed for batch b00" (extra camera_id/batch_id/
      duration_ms) on the success path — 361/362 rename it to
      XXbatch_idXX/BATCH_ID; and on the _call_llm-failure path the ERROR
      "LLM analysis failed for batch" with extra batch_id — 394/395.
    """
    import httpx

    with _capture_logs() as cap:
        await _run_batch(analyzer, mock_redis_client)
    done = _find(cap.records, message="LLM analysis completed for batch b00")
    assert len(done) == 1
    assert done[0].levelno == logging.DEBUG
    assert done[0].batch_id == "b00"
    assert done[0].camera_id == "front_door"

    with _capture_logs() as cap2:
        driven = await _run_batch(
            analyzer,
            mock_redis_client,
            llm_exc=httpx.ConnectError("LLM service unavailable"),
        )
    failed = _find(cap2.records, message="LLM analysis failed for batch")
    assert len(failed) == 1
    assert failed[0].levelno == logging.ERROR
    assert failed[0].batch_id == "b00"
    assert failed[0].camera_id == "front_door"
    assert failed[0].error == "LLM service unavailable"
    # shipped fallback still completes the pipeline with medium risk
    assert driven.event.risk_score == 50
    assert driven.event.risk_level == "medium"


@pytest.mark.asyncio
async def test_enrichment_helper_invocations_pin_arguments(analyzer, mock_redis_client):
    """Kills __mutmut_138, 139, 140, 141, 142, 147, 148, 149, 152, 153, 154.

    Pins the exact call arguments of the three session-1 enrichment helpers:
      _get_enriched_context(batch_id, camera_id, int_detection_ids, session)
      -> 139 (None, ...), 140 (..., None, ...), 141 (..., None, session),
         142 (..., None), 138 (call replaced by None -> context None ->
         _call_llm enriched_context=None and span has_enriched_context=False)
      _get_recent_scene_changes(camera_id, session) -> 147 (no call),
         148 (None camera), 149 (None session)
      format_camera_health_context(camera_id, recent_scene_changes) ->
         152 (no call / context None), 153 (None camera), 154 (None changes)
    """
    driven = await _run_batch(analyzer, mock_redis_client)

    assert len(driven.enriched) == 1
    assert driven.enriched[0] == ["'b00'", "'front_door'", "[1, 2]", driven.session_repr]
    assert len(driven.scene) == 1
    assert driven.scene[0] == ["'front_door'", driven.session_repr]
    assert len(driven.fchc) == 1
    assert driven.fchc[0] == (("'front_door'", _SCENE_SENTINEL), {})
    assert driven.call_llm[0]["kwargs"]["enriched_context"] == _ENRICHED
    assert driven.call_llm[0]["kwargs"]["camera_health_context"] == _HEALTH


@pytest.mark.asyncio
async def test_auto_tuning_success_pins_call_and_context(analyzer, mock_redis_client):
    """Kills __mutmut_159, 160, 161, 162, 163, 164.

    get_prompt_auto_tuner().get_tuning_context must be awaited with keyword
    session=<session-1 session> AND camera_id="front_door", and its returned
    string must reach _call_llm's auto_tuning_context kwarg verbatim.
    159 (auto_tuner=None -> method never runs), 160 (context assigned None),
    161 (session=None), 162 (camera_id=None), 163 (session kwarg removed),
    164 (camera_id kwarg removed) each break the kwargs identity/equality.
    """
    driven = await _run_batch(analyzer, mock_redis_client)

    assert len(driven.tuner) == 1
    args, kwargs = driven.tuner[0]
    assert set(kwargs) == {"session", "camera_id"}
    assert kwargs["session"] is driven.session
    assert kwargs["camera_id"] == "front_door"
    assert driven.call_llm[0]["kwargs"]["auto_tuning_context"] == _TUNING


@pytest.mark.asyncio
async def test_auto_tuning_failure_degrades_to_empty_string(analyzer, mock_redis_client):
    """Kills __mutmut_157, 158.

    When the auto-tuner raises, shipped keeps the pipeline alive and passes
    auto_tuning_context EXACTLY "" (empty string) to _call_llm, after a
    WARNING "Failed to fetch auto-tuning context" carrying the error. Mutant
    157 passes None and mutant 158 passes "XXXX" (the XXXX string mutant on
    the initial assignment survives the success path but cannot survive the
    failure path where the assignment value is what reaches _call_llm).
    """
    with _capture_logs() as cap:
        driven = await _run_batch(
            analyzer, mock_redis_client, tuning_exc=RuntimeError("tuner boom")
        )

    assert driven.call_llm[0]["kwargs"]["auto_tuning_context"] == ""
    warns = _find(cap.records, message="Failed to fetch auto-tuning context")
    assert len(warns) == 1
    assert warns[0].levelno == logging.WARNING
    assert warns[0].error == "tuner boom"


@pytest.mark.asyncio
async def test_detection_dicts_and_enrichment_payload_exact(analyzer, mock_redis_client):
    """Kills __mutmut_120, 168, 169, 170, 271.

    With 12 detections (id 1..12, object_type typeN, confidence id/100; the
    id SET is [1..12] but per-id attribution only — set-dedup order is the
    driver's, not the shipped code's contract):
      * batch_priority.calculated object_types_sample is exactly the first
        TEN types joined by "," — the [:11] mutant (120) appends type11.
      * the enrichment payload handed to _get_enrichment_result_from_data
        pins every dict key of the L2537-2549 comprehension — the
        "object_type" renamers (168 XX / 169 UPPER) and the "confidence"
        renamer (170) break the key equality.
      * _call_llm detection_dicts is [{"confidence", "class_name"}, ...] —
        the SECOND-occurrence "confidence" renamer (271, L2768) breaks it.
    """
    dets = _many_detections(12)
    driven = await _run_batch(
        analyzer,
        mock_redis_client,
        detections=dets,
        batch_kwargs={
            "batch_id": "b00",
            "camera_id": "front_door",
            "detection_ids": list(range(1, 13)),
        },
    )

    attrs = _span_attrs(driven.spans, "batch_priority.calculated")
    # object_types follows the fetch order (our descending id order);
    # shipped samples the FIRST TEN, mutant 120 ([11:]) yields eleven
    assert attrs["object_types_sample"] == ",".join(f"type{i}" for i in range(12, 2, -1))
    assert attrs["detection_count"] == 12

    payload = driven.enrich[0][1]
    assert len(payload) == 12
    by_id = {d["id"]: d for d in payload}
    assert set(by_id) == set(range(1, 13))
    for i, d in by_id.items():
        assert set(d) == {
            "id",
            "object_type",
            "confidence",
            "file_path",
            "bounding_box",
            "video_width",
            "video_height",
            "detected_at",
            "track_id",
            "camera_id",
        }
        assert d["object_type"] == f"type{i}"
        assert d["confidence"] == pytest.approx(i / 100)
        assert d["file_path"] == f"/export/foscam/front_door/img{i}.jpg"
        assert d["bounding_box"] is None
        assert d["camera_id"] == "front_door"

    dd = driven.call_llm[0]["kwargs"]["detection_dicts"]
    assert len(dd) == 12
    for entry in dd:
        assert set(entry) == {"confidence", "class_name"}
    dd_by_class = {e["class_name"]: e["confidence"] for e in dd}
    assert dd_by_class == {f"type{i}": pytest.approx(i / 100) for i in range(1, 13)}
