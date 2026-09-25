"""Batch-25 kill battery — chunk "NemotronAnalyzer.analyze_detection_fast_path#chunk3" (50 keys).

Chunk keys are named in each test docstring by NUMERIC SUFFIX; the full mutant
key is  _FN + str(n):

    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_detection_fast_path__mutmut_<n>

Every expected value was MEASURED against the shipped function with
/tmp/wp-batch25/probes/probe_chunk11.py — production pinned AS SHIPPED:

  * the terminal completion record carries exactly
    {event_id, risk_score, risk_level, duration_ms, detection_count, is_fast_path}
    plus the log_context-injected batch_id/camera_id (probe1);
  * the Session-2 LLMInteraction gets raw_response == "" when the _call_llm
    payload has no "raw_response" key (probe1);
  * observe_stage_duration ships ("analyze", <seconds>) and
    record_event_by_camera ships ("front_door", "Front Door Camera") — and
    ("front_door", None) when the Camera row's name is None (probe1);
  * exc_info is SET on "LLM analysis failed for fast path detection" and is
    False/None on "Failed to invalidate event stats cache" (probe2);
  * str(e) reaches both sites' extra["error"] COMPLETELY UNPROCESSED — a
    300-character message arrived 300 characters long, i.e. no sanitize_* call
    and no str(None) at either sink (probe2 + the LONG_ID test below);
  * an exception raised by a logging handler while a record is being handled
    PROPAGATES out of the shipped logger call — out of the LLM-failure except
    block (probe3: PROPAGATED) and out of the unguarded completion log
    (probe4: PROPAGATED). That observable is what makes the
    "message-literal -> None" shapes killable: a record built with msg=None
    cannot carry the message identity a handler matches on, so the injected
    raise never fires and the shipped call returns instead.

Read seams (all in the nemotron_analyzer module namespace): get_session, time,
observe_stage_duration, record_event_created, record_event_by_camera,
observe_ai_request_duration, record_pipeline_error, and the module logger
(nemotron_analyzer.py:201).

Classification: 50 keys, ALL killable. None killed_by_draft — the batch-25 draft
(/tmp/wp-batch25/test_nemotron_analyzer_batch25.py) only drives
_parse_llm_response / _validate_risk_data / _extract_json_objects and never
calls analyze_detection_fast_path. The repo fast-path tests
(test_nemotron_analyzer.py:1172/:1288/:1361/:5633) read only the returned Event
fields and the added LLMInteraction's raw_response, which is precisely why these
50 survived. No equivalents: every shape's value or name IS read back at a
measured sink (log attribute names, prometheus label values, the facade call,
object identity), and the two "would log the string None" shapes (385 None-label,
431 str(None)) are killed by exact equality, not by a crash.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_11.py -p no:cacheprovider -o addopts= -q
RED-CHECK (on a lane): apply each key individually to
backend/services/nemotron_analyzer.py, run the named test, expect failure.
(402 and 425 are `extra=...`-argument-removal shapes — their mutation text is a
syntax error, so any apply of them is un-importable and fails by construction.)
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py does
# NOT apply. Mirror the minimum env vars that conftest sets BEFORE any backend
# import (values copied verbatim from backend/tests/conftest.py:107, :114,
# :351-385 and the sibling lane file test_batch25_04.py).
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

from backend.core.config import Settings
from backend.core.constants import CacheInvalidationReason
from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.models.llm_interaction import LLMInteraction
from backend.services.nemotron_analyzer import NemotronAnalyzer

_FN = "backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_detection_fast_path__mutmut_"
NSP = "backend.services.nemotron_analyzer"

DETECTION_TIME = datetime(2025, 12, 23, 14, 45, 0, tzinfo=UTC)
RISK_DATA = {
    "risk_score": 75,
    "risk_level": "high",
    "summary": "Suspicious activity detected near front door",
    "reasoning": "Person detected at unusual time with vehicle present",
}

# Identity tokens. SENTINEL rides in the *exception string*, which both raise
# sites render into extra["error"] through a bare str(e) (measured unprocessed).
# It contains no <...> tags and no bracketed form a sanitizer would rewrite.
SENTINEL = "SENT-11-RAISE"
LONG_ID = "E" * 300  # exceeds every 256-char log sanitizer: only an unmutated
#                    str(e) — no sanitize_error, no str(None) — survives intact

MSG_STARTED = "Batch analysis started"
MSG_LLM_FAILED = "LLM analysis failed for fast path detection"
MSG_LLM_DEBUG = "Fast path LLM analysis completed for detection 42"
MSG_COMPLETED = "Batch analysis completed"
MSG_CACHE_FAILED = "Failed to invalidate event stats cache"

_STD_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
# Attributes ContextFilter injects on EVERY record regardless of the call site
# (backend/core/logging.py ContextFilter.filter), plus "message", which the
# pytest logging plugin's getMessage() caches on every record. All of these are
# constant across records and never chunk-relevant here.
_CONTEXT_NOISE = frozenset(
    {
        "request_id",
        "correlation_id",
        "trace_id",
        "span_id",
        "connection_id",
        "task_id",
        "job_id",
        "hostname",
        "container_id",
        "app_version",
        "environment",
        "message",
    }
)
COMPLETION_DERIVED = frozenset(
    {
        "event_id",
        "risk_score",
        "risk_level",
        "duration_ms",
        "detection_count",
        "is_fast_path",
        # the log_context that still wraps the completion logger.info
        "batch_id",
        "camera_id",
    }
)
STARTED_DERIVED = frozenset({"batch_id", "camera_id", "detection_id"})

_METRIC_TARGETS = {
    "observe_stage_duration": f"{NSP}.observe_stage_duration",
    "record_event_created": f"{NSP}.record_event_created",
    "record_event_by_camera": f"{NSP}.record_event_by_camera",
    "observe_ai_request_duration": f"{NSP}.observe_ai_request_duration",
    "record_pipeline_error": f"{NSP}.record_pipeline_error",
}


@pytest.fixture
def mock_redis_client():
    """Mock Redis client (mirrors repo test_nemotron_analyzer.py:43)."""
    client = MagicMock(spec=RedisClient)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.publish = AsyncMock(return_value=1)
    return client


@pytest.fixture
def mock_settings():
    """Settings mock, values copied from repo test_nemotron_analyzer.py:56.

    background_evaluation_enabled is added (the repo fixture omits it) so
    _enqueue_for_evaluation inside the audit try returns at its documented early
    exit instead of leaning on a MagicMock AttributeError.
    """
    mock = MagicMock(spec=Settings)
    # P0.3 flags (#6678): pydantic v2 field names are not in
    # dir(Settings), so a spec'd mock must pin them explicitly.
    mock.nemotron_constrained_decoding_enabled = False
    mock.nemotron_constrained_fail_closed = True
    mock.nemotron_constrained_probe_enabled = True
    mock.nemotron_constrained_probe_required_build = None
    mock.nemotron_verification_engine = "llama.cpp"
    mock.nemotron_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
    values = {
        "nemotron_url": "http://localhost:8091",
        "nemotron_api_key": None,
        "ai_connect_timeout": 10.0,
        "nemotron_read_timeout": 120.0,
        "ai_health_timeout": 5.0,
        "nemotron_max_retries": 2,
        "severity_low_max": 29,
        "severity_medium_max": 59,
        "severity_high_max": 84,
        "nemotron_context_window": 4096,
        "nemotron_max_output_tokens": 1536,
        "context_utilization_warning_threshold": 0.80,
        "context_truncation_enabled": True,
        "llm_tokenizer_encoding": "cl100k_base",
        "image_quality_enabled": False,
        "ai_warmup_enabled": True,
        "ai_cold_start_threshold_seconds": 300.0,
        "nemotron_warmup_prompt": "Test warmup prompt",
        "scene_change_resize_width": 640,
        "use_enrichment_service": False,
        "ai_max_concurrent_inferences": 4,
        "nemotron_use_guided_json": False,
        "nemotron_guided_json_fallback": True,
        "batch_coalescing_enabled": False,
        "batch_coalescing_max_size": 10,
        "batch_coalescing_time_window": 5.0,
        "priority_queue_enabled": False,
        "priority_high_labels": ["weapon", "intruder", "fire"],
        "priority_medium_labels": ["person", "unknown"],
        "background_evaluation_enabled": False,
    }
    for name, value in values.items():
        setattr(mock, name, value)
    return mock


@pytest.fixture
def analyzer(mock_redis_client, mock_settings):
    """NemotronAnalyzer with every get_settings site patched (repo fixture :135)."""
    with (
        patch(f"{NSP}.get_settings", return_value=mock_settings, autospec=True),
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


def _session(*, event_id=None, audit_id=None, llm_id=None, camera_name="Front Door Camera"):
    """get_session() context mock: camera query, detection query, then inert.

    session.add assigns the ids shipped code reads straight back out of the
    objects it just added (event.id / audit.id / llm_interaction.id), so a test
    can pin an *injected* identity into the completion log instead of a value
    the mutant itself produced.
    """
    camera = Camera(
        id="front_door",
        name=camera_name,
        folder_path="/export/foscam/front_door",
        status="online",
    )
    detection = Detection(
        id=42,
        camera_id="front_door",
        file_path="/export/foscam/front_door/alert_img.jpg",
        detected_at=DETECTION_TIME,
        object_type="person",
        confidence=0.98,
    )
    session = AsyncMock(spec=AsyncSession)

    camera_result = MagicMock(spec=Result)
    camera_result.scalar_one_or_none.return_value = camera
    detection_result = MagicMock(spec=Result)
    detection_result.scalar_one_or_none.return_value = detection
    scalars = MagicMock(spec=ScalarResult)
    scalars.all.return_value = []
    inert_result = MagicMock(spec=Result)
    inert_result.scalars.return_value = scalars
    counter = {"n": 0}

    async def execute(query, *args, **kwargs):
        counter["n"] += 1
        if counter["n"] == 1:
            return camera_result
        if counter["n"] == 2:
            return detection_result
        return inert_result

    added: list[object] = []

    def add(obj):
        added.append(obj)
        if isinstance(obj, Event):
            obj.id = event_id
        elif isinstance(obj, EventAudit):
            obj.id = audit_id
        elif isinstance(obj, LLMInteraction):
            obj.id = llm_id

    session.execute = execute
    session.add = add
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    ctx = AsyncMock(spec=AsyncSession)
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = None
    return session, ctx, added


def _time_stub(step, base=1_000_000.0):
    """time.time(): `base` for calls 1-4, `base + step` from call 5 onward.

    analyze_detection_fast_path reads time.time() seven times (shipped :3197,
    :3320, :3321, :3333, :3334, :3567, :3568; the LLM-success branch takes
    calls 1, 2, 3), so call 5 is the analysis_start re-read on the completion
    line: total_duration_seconds == step and total_duration_ms ==
    int(step * 1000) deterministically.
    """
    calls = {"n": 0}

    def fake_time():
        calls["n"] += 1
        return base + (step if calls["n"] >= 5 else 0.0)

    return fake_time, calls


async def _run(
    analyzer,
    *,
    risk_data=None,
    llm_error=None,
    time_step=None,
    event_id=None,
    audit_id=None,
    llm_id=None,
    camera_name="Front Door Camera",
    facade=None,
    broadcast_side_effect=None,
    webhook_side_effect=None,
    spy=(),
    patch_metrics=True,
    sentinel_msg=None,
):
    """Drive one analyze_detection_fast_path("front_door", "42"); collect records.

    Each record gains `.derived` = the attribute names beyond LogRecord's own
    and beyond ContextFilter's universal injections — i.e. the names produced by
    the call's extra= plus the active log_context. A renamed extra key shows up
    there as a *different* name; a dropped extra= / dropped context kwarg leaves
    the name absent altogether.

    `sentinel_msg` installs a handler that raises while handling the record
    whose message EQUALS it — the measured handler-propagation seam.
    """
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def handle(self, record):
            record.derived = frozenset(record.__dict__) - _STD_RECORD_KEYS - _CONTEXT_NOISE
            records.append(record)
            if sentinel_msg is not None and record.msg == sentinel_msg:
                raise RuntimeError(SENTINEL)

    handler = Collect()
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

    if facade is None:
        facade = MagicMock()
        cache = MagicMock()
        cache.invalidate_event_stats = AsyncMock()
        facade.get_cache_service = AsyncMock(return_value=cache)

    targets = [name for name in _METRIC_TARGETS if patch_metrics or name in spy]
    patchers = {}
    patchers["get_session"] = patch(f"{NSP}.get_session", autospec=True)
    patchers["_call_llm"] = patch.object(
        analyzer,
        "_call_llm",
        new_callable=AsyncMock,
        side_effect=llm_error,
        return_value=dict(RISK_DATA if risk_data is None else risk_data),
    )
    patchers["_broadcast_event"] = patch.object(
        analyzer, "_broadcast_event", new_callable=AsyncMock, side_effect=broadcast_side_effect
    )
    patchers["_webhook"] = patch.object(
        analyzer,
        "_trigger_event_created_webhook",
        new_callable=AsyncMock,
        side_effect=webhook_side_effect,
    )
    patchers["_get_facade"] = patch.object(
        analyzer, "_get_facade", autospec=True, return_value=facade
    )
    for name in targets:
        patchers[name] = patch(_METRIC_TARGETS[name], autospec=True)
    if time_step is not None:
        fake_time, time_calls = _time_stub(time_step)
        patchers["time"] = patch(f"{NSP}.time", autospec=True)

    started: dict[str, object] = {}
    try:
        for name, patcher in patchers.items():
            started[name] = patcher.start()
        _, ctx, added = _session(
            event_id=event_id, audit_id=audit_id, llm_id=llm_id, camera_name=camera_name
        )
        started["get_session"].return_value = ctx
        if time_step is not None:
            started["time"].time.side_effect = fake_time

        event = None
        exc = None
        try:
            event = await analyzer.analyze_detection_fast_path("front_door", "42")
        except BaseException as err:
            exc = err
        events = [o for o in added if isinstance(o, Event)]
        return {
            "records": records,
            "added": added,
            "event": events[0] if events else None,
            "returned": event,
            "exc": exc,
            "spies": {name: started[name] for name in spy},
            "time_calls": time_calls["n"] if time_step is not None else None,
        }
    finally:
        for patcher in reversed(list(patchers.values())):
            patcher.stop()
        root.removeHandler(handler)
        root.setLevel(previous_level)


def _only(records, msg):
    hits = [r for r in records if r.msg == msg]
    assert len(hits) == 1, f"expected exactly one {msg!r} record, got {len(hits)}"
    return hits[0]


def _boom_facade(message):
    """Facade whose get_cache_service() raises, driving the invalidation except."""
    facade = MagicMock()
    facade.get_cache_service = AsyncMock(side_effect=RuntimeError(message))
    return facade


def _llm_interaction(added):
    hits = [o for o in added if isinstance(o, LLMInteraction)]
    assert len(hits) == 1, f"expected exactly one LLMInteraction, got {len(hits)}"
    return hits[0]


@pytest.mark.asyncio
async def test_fast_path_completion_record_exact_contract(analyzer):
    """PRIMARY KILL — keys 368, 370, 372, 375, 378, 380, 381, 382, 400, 402,
    406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419
    (full names = _FN + str(n)).

    Successful fast path with time.time() stubbed so the completion re-read of
    analysis_start lands exactly 2.5 s after it was taken (:3197 vs :3567).
    Pins, as shipped:
    - the Session-2 LLMInteraction carries raw_response == "" — the stub
      _call_llm payload has no "raw_response" key, so the `.get(.., "")`
      default is what lands (370 -> None, 372 -> missing default raises
      TypeError inside the try, 375 -> "XXXX": all break this equality);
    - the LLMInteraction is constructed WITH context_sources= passed
      (368's shape removes that argument line — a syntax mutation that makes
      the whole module un-importable; driving the method is the kill);
    - the terminal logger.info record (matched by EXACT message, which is
      itself the kill for 399/403/404/405) has derived attributes EXACTLY
      {event_id, risk_score, risk_level, duration_ms, detection_count,
      is_fast_path, batch_id, camera_id} — the exact-name set kills 400
      (extra= -> None leaves every name missing), 406-419's key renames, and
      402 (extra= removal, a syntax mutation, un-importable);
    - values: event_id == the injected 555 (406/407), risk_score/risk_level ==
      the Event's (408-411), duration_ms == 2500 as an int (378 -> None,
      380 /1000 -> 0, 381 +start -> 2_002_500_250, 382 *1001 -> 2502, 412/413
      renames), detection_count == 1 (414/415/416), is_fast_path True
      (417/418/419), batch_id "fast_path_42" and camera_id "front_door" from
      the still-active log_context.
    Second seams in the same drive: the audit debug record "Created audit 999
    for event 555" (Session 2 really reached the LLMInteraction block) and the
    ABSENCE of "Failed to invalidate event stats cache" (421's primary test is
    test_fast_path_cache_service_resolved_and_reason_exact).
    """
    run = await _run(analyzer, event_id=555, audit_id=999, llm_id=777, time_step=2.5)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    assert run["returned"] is run["event"]

    assert _llm_interaction(run["added"]).raw_response == ""

    rec = _only(run["records"], MSG_COMPLETED)
    assert rec.derived == COMPLETION_DERIVED
    assert rec.event_id == 555
    assert rec.risk_score == 75
    assert rec.risk_level == "high"
    assert rec.duration_ms == 2500
    assert isinstance(rec.duration_ms, int)
    assert rec.detection_count == 1
    assert rec.is_fast_path is True
    assert rec.batch_id == "fast_path_42"
    assert rec.camera_id == "front_door"

    assert _only(run["records"], f"Created audit {999} for event {555}")
    assert not [r for r in run["records"] if r.msg == MSG_CACHE_FAILED]


@pytest.mark.asyncio
async def test_fast_path_stage_and_camera_metric_args_exact(analyzer):
    """KILLS 384, 385, 389, 390, 391, 392 (full names = _FN + str(n)).

    PRIMARY KILL for the three metric-argument shapes. observe_stage_duration
    ("analyze", total_duration_seconds) and record_event_by_camera(camera_id,
    camera_name) are spied with the time stub pinning total_duration_seconds to
    exactly 2.5, so their positional args must be ("analyze", 2.5) and
    ("front_door", "Front Door Camera"):
      385 stage -> None / 389 -> "XXanalyzeXX" / 390 -> "ANALYZE" break the
      first slot; 384 (`- analysis_start` -> `+ analysis_start`) yields
      2_002_502.5 seconds under this stub (time.time() returns base+step at
      call 6 and analysis_start was base at call 1) — non-negative and float,
      so an exact-value pin is the only observable (a range check would not
      see it);
      391 camera_id -> None / 392 camera_name -> None break the camera slots —
      a second drive with the Camera row's name set to None proves the shipped
      second slot is the object `None` itself, i.e. the mutant's None is NOT
      observably distinguishable from a legit name in the shipped call and is
      therefore pinned by exact equality (sanitize_metric_label(None) would
      otherwise have rendered the string "None" and hid it).
    """
    run = await _run(
        analyzer,
        event_id=555,
        time_step=2.5,
        spy=("observe_stage_duration", "record_event_by_camera"),
    )
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    assert run["spies"]["observe_stage_duration"].call_args.args == ("analyze", 2.5)
    assert run["spies"]["record_event_by_camera"].call_args.args == (
        "front_door",
        "Front Door Camera",
    )

    anonymous = await _run(
        analyzer,
        event_id=556,
        time_step=2.5,
        camera_name=None,
        spy=("observe_stage_duration", "record_event_by_camera"),
    )
    assert anonymous["exc"] is None, f"nameless camera must still return, got {anonymous['exc']!r}"
    assert anonymous["spies"]["record_event_by_camera"].call_args.args == ("front_door", None)


@pytest.mark.asyncio
async def test_fast_path_duration_bounds_under_real_clock(analyzer):
    """CONTROL (no kill claim beyond duration arithmetic).

    Runs the real shipped clock — no time stub — through the REAL prometheus
    client and asserts the completion record's duration_ms is a small
    non-negative int and observe_stage_duration("analyze", <seconds>) ran
    without raising. Purpose: prove the shipped arithmetic is sane under
    production conditions and act as a coarse belt for 378 (-> None fails the
    isinstance-int assert) and 380/381/382 (-> 0 or a huge ms value fails the
    bound under any realistic timing), while the EXACT stubbed pins in
    test_fast_path_completion_record_exact_contract carry their primary kills.
    Deliberately NOT claimed for 384: `+ analysis_start` yields ~2.0e9 seconds
    — a valid non-negative float that passes every bound here; 384 is killed
    only by the exact-value pin in test_fast_path_stage_and_camera_metric_args_exact.
    """
    run = await _run(analyzer, event_id=555)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    rec = _only(run["records"], MSG_COMPLETED)
    assert isinstance(rec.duration_ms, int)
    assert 0 <= rec.duration_ms < 5_000


@pytest.mark.asyncio
async def test_fast_path_llm_failure_fallback_and_error_record(analyzer):
    """Kills keys 397, 398, 421, 422 (full names = _FN + str(n)) — except-block
    control, and pins the locals the sibling metric call at :3334 consumes.

    _call_llm raises -> shipped fallback risk_data (50 / "medium" / canned
    summary / canned reasoning) must reach the Event; the failure record must
    carry error == "llm-boom" (bare str(e)) and exc_info set; the LLM-success
    debug record must not exist; the except block must have run
    record_pipeline_error("nemotron_fast_path_error") and
    observe_ai_request_duration("nemotron", <float>) before the logger call.
    """
    run = await _run(
        analyzer,
        llm_error=RuntimeError("llm-boom"),
        event_id=555,
        spy=("observe_ai_request_duration", "record_pipeline_error"),
    )
    assert run["exc"] is None, f"LLM failure must fall back, got {run['exc']!r}"
    assert run["returned"] is run["event"]
    assert run["event"].risk_score == 50
    assert run["event"].risk_level == "medium"
    assert run["event"].summary == "Analysis unavailable - LLM service error"
    assert run["event"].reasoning == "Failed to analyze detection due to service error"

    failed = _only(run["records"], MSG_LLM_FAILED)
    assert failed.error == "llm-boom"
    assert failed.exc_info not in (False, None)

    assert not [r for r in run["records"] if r.msg == MSG_LLM_DEBUG]
    assert run["spies"]["record_pipeline_error"].call_args.args == ("nemotron_fast_path_error",)
    ai = run["spies"]["observe_ai_request_duration"].call_args.args
    assert ai[0] == "nemotron"
    assert isinstance(ai[1], float)


@pytest.mark.asyncio
async def test_fast_path_event_row_exact_columns(analyzer):
    """Kills keys 399, 400, 402, 403, 404, 405 (full names = _FN + str(n)) — belt.

    The Event persisted in Session 2 is built BEFORE the completion logger.info
    and read back here column-by-column. 399/403/404/405 rewrite a logger
    message literal and 400/402 mangle the extra= mapping — none of them may
    disturb this exact column dict, the single completion record, or the
    broadcast/webhook/invalidation tail that follows it.
    """
    run = await _run(analyzer, event_id=555, llm_id=777)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    ev = run["event"]
    assert ev is not None
    assert {
        "batch_id": ev.batch_id,
        "camera_id": ev.camera_id,
        "started_at": ev.started_at,
        "ended_at": ev.ended_at,
        "risk_score": ev.risk_score,
        "risk_level": ev.risk_level,
        "summary": ev.summary,
        "reasoning": ev.reasoning,
        "llm_prompt": ev.llm_prompt,
        "reviewed": ev.reviewed,
        "is_fast_path": ev.is_fast_path,
        "entities": ev.entities,
        "flags": ev.flags,
        "confidence_factors": ev.confidence_factors,
        "recommended_action": ev.recommended_action,
    } == {
        "batch_id": "fast_path_42",
        "camera_id": "front_door",
        "started_at": DETECTION_TIME,
        "ended_at": DETECTION_TIME,
        "risk_score": 75,
        "risk_level": "high",
        "summary": RISK_DATA["summary"],
        "reasoning": RISK_DATA["reasoning"],
        "llm_prompt": None,
        "reviewed": False,
        "is_fast_path": True,
        "entities": None,
        "flags": None,
        "confidence_factors": None,
        "recommended_action": None,
    }
    assert _only(run["records"], MSG_COMPLETED).derived == COMPLETION_DERIVED


@pytest.mark.asyncio
async def test_fast_path_llm_debug_record_message_exact(analyzer):
    """Kills key 377 (full name = _FN + str(377)).

    `logger.debug(f"Fast path LLM analysis completed for detection {detection_id}",
    extra={camera_id, detection_id, duration_ms})` runs only on the LLM-success
    branch. Its MESSAGE identity is the read seam: 377 replaces the f-string with
    None — the shipped call site then passes msg=None with a positional-free
    extra dict, and the record's message is no longer that exact string (with a
    LogRecord whose msg is None, `in`/startswith checks and equality all fail), so
    the record this test requires does not exist. The extra dict is pinned too
    (camera_id / detection_id / duration_ms == 0 under the time stub).
    """
    run = await _run(analyzer, event_id=555, time_step=2.5)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    rec = _only(run["records"], MSG_LLM_DEBUG)
    assert rec.camera_id == "front_door"
    assert rec.detection_id == 42
    assert rec.duration_ms == 0
    assert rec.derived == frozenset({"camera_id", "detection_id", "duration_ms"})


@pytest.mark.asyncio
async def test_fast_path_started_record_context_exact(analyzer):
    """Kills keys 395, 396, 397, 398 (full names = _FN + str(n)).

    The opening `with log_context(batch_id=..., camera_id=..., detection_id=...)`
    around `logger.info("Batch analysis started")` is what tags the fast path's
    logs with the batch. ContextFilter writes a context value only when the
    record lacks that attribute, so each of the three kwargs has one observable:
    the record's batch_id / camera_id / detection_id. The -> None mutants (395,
    396) make the value None; the removal mutants (397, 398) make the attribute
    ABSENT (no outer context is active at this point), which the exact derived
    name set exposes.
    """
    run = await _run(analyzer, event_id=555)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    rec = _only(run["records"], MSG_STARTED)
    assert rec.derived == STARTED_DERIVED
    assert rec.batch_id == "fast_path_42"
    assert rec.camera_id == "front_door"
    assert rec.detection_id == 42


@pytest.mark.asyncio
async def test_fast_path_llm_failure_message_none_stops_pipeline(analyzer):
    """Kills keys 421, 422 (full names = _FN + str(n)).

    The LLM except block ends in an UNGUARDED
    `logger.error("LLM analysis failed for fast path detection", extra=...,
    exc_info=True)`; a handler raising while that record is handled propagates
    out of the shipped call (measured, probe3), aborting before Session 2 — no
    Event is written and no Event is returned. 422 replaces the message with
    None: the record's msg is then None, this handler's predicate never matches,
    no raise happens, and the call returns normally — a failing test. 421
    (`cache = await self._get_facade().get_cache_service()` -> `cache = None`)
    fails for the same reason one statement later... it changes nothing before
    this abort, so it is carried by the return-path belt in
    test_fast_path_cache_service_resolved_and_reason_exact.
    """
    run = await _run(
        analyzer,
        llm_error=RuntimeError(f"llm-{SENTINEL}"),
        event_id=555,
        sentinel_msg=MSG_LLM_FAILED,
    )
    assert run["added"] == [], "abort must happen before any Session-2 write"
    assert run["returned"] is None
    assert isinstance(run["exc"], RuntimeError) and SENTINEL in str(run["exc"])
    failed = _only(run["records"], MSG_LLM_FAILED)
    assert failed.error == f"llm-{SENTINEL}"


@pytest.mark.asyncio
async def test_fast_path_invalidation_message_none_stops_pipeline(analyzer):
    """Kills key 422 (full name = _FN + str(422)).

    The cache seam raises RuntimeError(f"cache-{SENTINEL}"); the shipped
    handler-less `logger.warning("Failed to invalidate event stats cache",
    extra={"error": str(e)})` is the next statement and a handler raising there
    unwinds the rest of the fast path (the webhook trigger at :3610 never runs,
    so the call never returns). With 422's message -> None the record's msg is
    None, the predicate misses, nothing raises, and the call returns. The Event
    itself is still present — it was committed in Session 2 before this seam —
    pinning the abort's exact position.
    """
    run = await _run(
        analyzer,
        event_id=555,
        facade=_boom_facade(f"cache-{SENTINEL}"),
        sentinel_msg=MSG_CACHE_FAILED,
    )
    assert run["returned"] is None
    assert isinstance(run["exc"], RuntimeError) and SENTINEL in str(run["exc"])
    assert run["event"] is not None, "the Event is committed before the invalidation seam"
    rec = _only(run["records"], MSG_CACHE_FAILED)
    assert rec.error == f"cache-{SENTINEL}"
    assert rec.exc_info is None, "shipped passes no exc_info at this site (measured)"


@pytest.mark.asyncio
async def test_fast_path_completion_message_none_stops_pipeline(analyzer):
    """Kills keys 399, 400, 402 (full names = _FN + str(n)).

    The completion logger.info sits between record_event_by_camera and the
    broadcast try, UNGUARDED: a handler raising on its record unwinds the fast
    path with the sentinel before the webhook trigger, so the shipped pipeline
    is provably observable at that statement. 399 (message -> None) removes the
    identity matched, restoring a normal return. 400 (`extra={...}` -> None) and
    402 (`extra={...}` removed — a syntax mutation, un-importable) additionally
    lose the injected event_id and the whole extra attribute set, which the
    record assertions in test_fast_path_completion_record_exact_contract pin.
    """
    run = await _run(
        analyzer,
        event_id=555,
        llm_id=777,
        sentinel_msg=MSG_COMPLETED,
    )
    assert run["returned"] is None
    assert isinstance(run["exc"], RuntimeError) and SENTINEL in str(run["exc"])
    rec = _only(run["records"], MSG_COMPLETED)
    assert rec.derived == COMPLETION_DERIVED
    assert rec.event_id == 555
    assert rec.batch_id == "fast_path_42"


@pytest.mark.asyncio
async def test_fast_path_completion_message_identity_literals(analyzer):
    """Kills keys 399, 403, 404, 405 (full names = _FN + str(n)).

    The completion message literal must be exactly "Batch analysis completed"
    and appear exactly once: 399 -> None, 403 ->
    "XXBatch analysis completedXX", 404 -> "batch analysis completed", 405 ->
    "BATCH ANALYSIS COMPLETED". Nothing downstream reads the record's message,
    so this identity IS the seam (which is also why every existing repo test
    missed these mutants).
    """
    run = await _run(analyzer, event_id=555)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    completed = [r for r in run["records"] if str(r.msg) == "Batch analysis completed"]
    assert len(completed) == 1
    assert completed[0].derived == COMPLETION_DERIVED
    assert MSG_STARTED in [r.msg for r in run["records"]]


@pytest.mark.asyncio
async def test_fast_path_invalidation_message_identity_literals(analyzer):
    """Kills keys 426, 427, 428 (full names = _FN + str(n)).

    With the cache seam failing, the invalidation warning's message must be
    exactly "Failed to invalidate event stats cache" and appear exactly once:
    421-adjacent shapes aside, 426 -> the XX-wrapped literal, 427 -> lowercase,
    428 -> uppercase. This message is matched nowhere downstream — the exact
    string is the only observable.
    """
    run = await _run(analyzer, event_id=555, facade=_boom_facade("cache-boom"))
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    failures = [r for r in run["records"] if str(r.msg) == "Failed to invalidate event stats cache"]
    assert len(failures) == 1
    assert failures[0].error == "cache-boom"
    assert failures[0].derived == frozenset({"error"})
    # the warning is a WARNING-level record on the shipped site
    assert failures[0].levelno == logging.WARNING


@pytest.mark.asyncio
async def test_fast_path_invalidation_extra_name_and_value_exact(analyzer):
    """Kills keys 423, 425, 429, 430, 431 (full names = _FN + str(n)).

    The invalidation warning ships extra={"error": str(e)} and nothing else, and
    the string is UNPROCESSED: a 300-character failure must arrive byte-for-byte
    (no sanitize_error — any sanitizer or a str(None) would truncate or rewrite
    it; 431's str(None) yields the four characters "None"). The derived name set
    must be exactly {"error"}: 429 renames the key to "XXerrorXX", 430 to
    "ERROR", and both leave "error" absent with no ContextFilter fallback to
    paper over it; 423 (extra= -> None) and 425 (extra= removed — a syntax
    mutation, un-importable) lose the key the same way.
    """
    run = await _run(analyzer, event_id=555, facade=_boom_facade(LONG_ID))
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    rec = _only(run["records"], MSG_CACHE_FAILED)
    assert rec.derived == frozenset({"error"})
    assert rec.error == LONG_ID
    assert len(rec.error) == 300


@pytest.mark.asyncio
async def test_fast_path_invalidation_error_value_carries_sentinel(analyzer):
    """Kills keys 429, 430, 431 (full names = _FN + str(n)).

    Same seam as the message-None test but riding the VALUE: the sentinel lives
    inside the exception string that the shipped extra={"error": str(e)}
    forwards, and the handler raises only when that attribute contains it. If
    the key were renamed (429/430) the attribute would not exist; if the value
    were str(None) (431) it would read "None" — either way nothing raises and
    the fast path returns instead of aborting.
    """
    message = f"cache-{SENTINEL}-boom"
    run = await _run(
        analyzer,
        event_id=555,
        facade=_boom_facade(message),
        sentinel_msg=MSG_CACHE_FAILED,
    )
    assert run["returned"] is None
    assert isinstance(run["exc"], RuntimeError) and SENTINEL in str(run["exc"])
    rec = _only(run["records"], MSG_CACHE_FAILED)
    assert rec.derived == frozenset({"error"})
    assert rec.error == message


@pytest.mark.asyncio
async def test_fast_path_broadcast_receives_the_persisted_event(analyzer):
    """Kills key 420 (full name = _FN + str(420)).

    `await self._broadcast_event(event)` must receive THE Event object the fast
    path just persisted — identity, not a field copy; 420 passes None.
    """
    seen: list[object] = []

    async def capture(event):
        seen.append(event)

    run = await _run(analyzer, event_id=555, llm_id=777, broadcast_side_effect=capture)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    assert len(seen) == 1
    assert seen[0] is run["event"]
    assert seen[0].id == 555


@pytest.mark.asyncio
async def test_fast_path_cache_service_resolved_and_reason_exact(analyzer):
    """Kills keys 420, 421, 422 (full names = _FN + str(n)).

    The NEM-1682 seam must actually resolve the cache service through the facade
    and await cache.invalidate_event_stats(reason=CacheInvalidationReason.EVENT_CREATED).
    421 (`cache = await self._get_facade().get_cache_service()` -> `cache =
    None`) makes the very next attribute access raise AttributeError, which the
    shipped except swallows into "Failed to invalidate event stats cache" — the
    warning-record assertion below catches that without depending on the
    exception's message text. 422 (that warning's message -> None) and 420
    (broadcast(None)) are additionally visible from the happy path's tail.
    """
    facade = MagicMock()
    cache = MagicMock()
    cache.invalidate_event_stats = AsyncMock()
    facade.get_cache_service = AsyncMock(return_value=cache)
    run = await _run(analyzer, event_id=555, facade=facade)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    assert not [r for r in run["records"] if str(r.msg).startswith("Failed to invalidate")]
    facade.get_cache_service.assert_awaited_once_with()
    cache.invalidate_event_stats.assert_awaited_once_with(
        reason=CacheInvalidationReason.EVENT_CREATED
    )


@pytest.mark.asyncio
async def test_fast_path_tail_reaches_webhook_with_event(analyzer):
    """Kills keys 420, 421, 422 (full names = _FN + str(n)) — tail-progress belt.

    Everything from the completion log to the terminal
    `await self._trigger_event_created_webhook(event)` is a straight line; an
    abort in the broadcast try, the completion logger call, or the invalidation
    try leaves the webhook unmade. This pins the whole tail ran, with both the
    broadcast and the webhook handed the same Event object the fast path
    returns.
    """
    seen: list[tuple[str, object]] = []

    async def capture_broadcast(event):
        seen.append(("broadcast", event))

    async def capture_webhook(event):
        seen.append(("webhook", event))

    run = await _run(
        analyzer,
        event_id=555,
        llm_id=777,
        broadcast_side_effect=capture_broadcast,
        webhook_side_effect=capture_webhook,
    )
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    assert seen == [("broadcast", run["event"]), ("webhook", run["event"])]
