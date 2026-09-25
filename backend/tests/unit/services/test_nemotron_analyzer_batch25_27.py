"""Batch-25 kill battery — chunk "tail:B" (chunk-27, 97 keys) of the
nemotron_analyzer survivor set.

Seven shipped functions adjudicated (line refs are shipped
backend/services/nemotron_analyzer.py on branch mutation-testing-s3):

  NemotronAnalyzer._get_enriched_context     (1610-1651)  26 keys
  NemotronAnalyzer.model_readiness_probe     (1422-1463)  22 keys
  NemotronAnalyzer._run_enrichment_pipeline  (3664-3742)  20 keys
  NemotronAnalyzer._enqueue_for_evaluation   (4564-4601)  14 keys
  NemotronAnalyzer._to_serializable          (1700-1714)  11 keys
  NemotronAnalyzer._get_auth_headers         (2316-2339)   3 keys
  NemotronAnalyzer.record_rollout_feedback   (1258-1280)   1 key

Verdict: 97/97 KILLABLE, 0 killed_by_draft (the draft battery covers only
_parse_llm_response / _validate_risk_data / _extract_json_objects; the repo
tests for these functions pin return values and result identities only —
probed test-by-test, none of them kills any of these 97 keys), 0 equivalent,
0 true_gap.

Every expected value below was MEASURED against shipped production by the
probe at /tmp/wp-batch25/probes/chunk27/ (pytest -s, this session) —
production is asserted AS SHIPPED, never as expected.  Log records are
captured with a direct logging.Handler on the shipped module logger with
level DEBUG raised for the duration of the test (the shipped effective
level is WARNING, so DEBUG records need the level raised at the seam —
same technique as chunk 24; the shipped code path itself is untouched).

KEY MAP (feed.json shape groups; every group here holds exactly ONE key,
no occurrence-twins straddle this chunk — cross-checked):
  gec: 1 gate-flip | 2 3 4 5 6 7 8 9 10 11 12 enrich-call/return/debug
       13 14 15 17 18 19 20 21 22 23 24 25 26 27 except-branch warning
  mrp: 3 4 5 7 8 url/headers/json shape | 9 10 11 12 13 14 15 16 payload
       literals | 18 duration arithmetic | 19 20 22 23 24 completion debug
       26 28 30 connection/timeout/HTTP warning texts
  rep: 4 5 6 7 skip-condition or->and | 13 continue->break
       17 18 19 20 25 26 27 28 29 30 31 32 40 42 DetectionInput fields
       46 shared-image condition and->or
  ee:  4 disabled-debug | 6 queue(redis)->None | 11 success-debug
       12 13 15 16 17 18 19 20 21 22 23 failure-warning
  tsr: 1 None-guard | 2 3 4 5 6 7 model_dump hasattr | 8 9 10 dataclass
       guard | 11 asdict arg
  ga:  4 8 9 hasattr(self._api_key, "get_secret_value") mutations
  rrb: 3 get_group_for_camera(camera_id)->None

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m \
  pytest /tmp/wp-batch25/parts/test_batch25_27.py -p no:cacheprovider \
  -o addopts= -q
"""

from __future__ import annotations

import dataclasses
import logging
import os
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

# Out-of-repo file: the repo's asyncio_mode=auto is not picked up, so async
# tests carry an explicit @pytest.mark.asyncio (same as sibling part files).
pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py
# does NOT apply. Mirror the minimum env vars the repo conftest sets
# (values copied verbatim from backend/tests/conftest.py and the unit
# conftest's enable_api_key_auth_for_unit_tests fixture).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("API_KEY_ENABLED", "true")  # pragma: allowlist secret
os.environ.setdefault("API_KEYS", '["test-unit-api-key-12345"]')  # pragma: allowlist secret

import httpx
from pydantic import BaseModel, SecretStr

import backend.services.nemotron_analyzer as NA
from backend.config.prompt_ab_rollout import ExperimentGroup
from backend.models.detection import Detection
from backend.services.context_enricher import ContextEnricher
from backend.services.enrichment_pipeline import BoundingBox

LOGGER = NA.logger
MOD = "backend.services.nemotron_analyzer"


def _analyzer() -> NA.NemotronAnalyzer:
    # __new__ skips the heavy __init__ (http client / settings wiring);
    # every method under test reads only the attributes each test sets.
    return NA.NemotronAnalyzer.__new__(NA.NemotronAnalyzer)


@pytest.fixture
def logs():
    """Capture records emitted on the shipped module logger (DEBUG raised)."""

    class _H(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records: list[logging.LogRecord] = []

        def emit(self, record):
            self.records.append(record)

    h = _H()
    LOGGER.addHandler(h)
    prev = LOGGER.level
    LOGGER.setLevel(logging.DEBUG)
    try:
        yield h.records
    finally:
        LOGGER.setLevel(prev)
        LOGGER.removeHandler(h)


# =========================================================================
# NemotronAnalyzer._get_enriched_context  (shipped L1610-1651)
# =========================================================================


def _enricher_returning(ctx):
    enricher = create_autospec(ContextEnricher, instance=True)
    enricher.enrich.return_value = ctx
    return enricher


@pytest.mark.asyncio
async def test_gec_01_gate_off_short_circuits_without_touching_enricher():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_get_enriched_context__mutmut_1.

    SHIPPED (probed): with _use_enriched_context False the method returns
    None WITHOUT calling _get_context_enricher and logs nothing.  The
    gate-flip mutant (``if self._use_enriched_context: return None``) falls
    through to the try-block and calls the builder — call_count kills it.
    """
    a = _analyzer()
    a._use_enriched_context = False
    a._get_context_enricher = MagicMock(name="builder")
    got = await a._get_enriched_context("BATCH-1", "CAM-A", [1, 2], "SENTINEL")
    assert got is None
    a._get_context_enricher.assert_not_called()


@pytest.mark.asyncio
async def test_gec_02_success_path_pins_call_return_and_debug(logs):
    """Kills _get_enriched_context__mutmut_2, _3, _4, _5, _6, _7, _8, _9,
    _10, _11, _12.

    MEASURED shipped: enricher = self._get_context_enricher(); the awaited
    call is enrich(batch_id=..., camera_id=..., detection_ids=...,
    session=...) — all four as KEYWORDS; the enrich() result object is
    returned BY IDENTITY; one DEBUG record with the exact
    "Context enriched for batch {batch_id}: {len(zones)} zones,
    {len(cross_camera)} cross-camera activities" message and no WARNING.

    Mutant 2 (enricher=None) and 3 (context=None) die on the builder/return
    pins (context=None additionally crashes the debug f-string and reroutes
    into the except-branch -> WARNING).  4-7 (a kwarg value -> None) and
    8-10 (a REQUIRED kwarg dropped -> autospec TypeError -> except-branch)
    and 11 (session kwarg dropped; session is kw-only-defaulted so only the
    exact kwargs dict distinguishes) die on the call-shape pin.  12
    (debug message -> None) dies on the message pin.
    """
    a = _analyzer()
    a._use_enriched_context = True
    ctx = SimpleNamespace(zones=["z1", "z2"], cross_camera=["x1"])
    enricher = _enricher_returning(ctx)
    a._get_context_enricher = MagicMock(return_value=enricher)

    got = await a._get_enriched_context("BATCH-1", "CAM-A", [1, 2], "SENTINEL-SESSION")

    assert got is ctx
    a._get_context_enricher.assert_called_once_with()
    assert enricher.enrich.call_args.kwargs == {
        "batch_id": "BATCH-1",
        "camera_id": "CAM-A",
        "detection_ids": [1, 2],
        "session": "SENTINEL-SESSION",
    }
    assert [r.levelno for r in logs] == [logging.DEBUG]
    assert logs[0].getMessage() == (
        "Context enriched for batch BATCH-1: 2 zones, 1 cross-camera activities"
    )


@pytest.mark.asyncio
async def test_gec_03_failure_path_pins_warning_exactly(logs):
    """Kills _get_enriched_context__mutmut_13, _14, _15, _17, _18, _19, _20,
    _21, _22, _23, _24, _25, _26, _27.

    MEASURED shipped: when enrich() raises, the method returns None and
    emits ONE WARNING record:
      message  "Context enrichment failed, falling back to basic prompt"
      extra    {"batch_id": batch_id, "error": str(e)}  (flattened onto the
               LogRecord: record.batch_id / record.error — probed present)
      exc_info True (record.exc_info is the (type, exc, tb) triple)
    Mutant 13/19/20/21 (message None / XX-wrapped / lower / upper) die on
    the message; 14/17 (extra=None / extra dropped) and 22/23/24/25 (extra
    key renames) die on the record.batch_id/record.error pins; 26
    ("error": str(None)) on the record.error VALUE; 15/18/27 (exc_info
    None/dropped/False) on the exc_info pin.
    """
    a = _analyzer()
    a._use_enriched_context = True
    enricher = create_autospec(ContextEnricher, instance=True)
    enricher.enrich.side_effect = RuntimeError("boom-77")
    a._get_context_enricher = MagicMock(return_value=enricher)

    got = await a._get_enriched_context("BATCH-X", "CAM-A", [1], "SESSION")

    assert got is None
    assert [r.levelno for r in logs] == [logging.WARNING]
    rec = logs[0]
    assert rec.getMessage() == "Context enrichment failed, falling back to basic prompt"
    assert getattr(rec, "batch_id", "<absent>") == "BATCH-X"
    assert getattr(rec, "error", "<absent>") == "boom-77"
    assert rec.exc_info is not None
    assert rec.exc_info[0] is RuntimeError


# =========================================================================
# NemotronAnalyzer.model_readiness_probe  (shipped L1422-1463)
# =========================================================================


def _probe_analyzer(post):
    a = _analyzer()
    a._llm_url = "http://nemotron-probe:8091"
    a._warmup_prompt = "WARMUP-PROMPT-MARKER"
    a._api_key = None
    client = MagicMock(name="http_client")
    client.post = post
    a._http_client = client
    a._get_auth_headers = lambda: {"X-Auth-Sentinel": "AUTH-HEADERS"}
    return a, client


@pytest.mark.asyncio
async def test_mrp_01_success_pins_request_payload_clock_and_debug(logs, monkeypatch):
    """Kills model_readiness_probe__mutmut_3, _4, _5, _7, _8, _9, _10, _11,
    _12, _13, _14, _15, _16, _18, _19, _20, _22, _23, _24.

    MEASURED shipped: a SINGLE post call, positional url
    f"{self._llm_url}/v1/completions", kwargs headers=self._get_auth_headers()
    and json={"prompt": self._warmup_prompt, "max_tokens": 50,
    "temperature": 0.1}; returns True; one DEBUG record
    "Nemotron readiness probe completed in {duration:.2f}s" with
    extra {"duration": duration}.

    The clock is faked (monkeypatch on time.monotonic, value advanced ONLY
    by the fake post): start reads 1000.0, the completion reads 1000.25, so
    the shipped ``time.monotonic() - start_time`` (L1447) is EXACTLY 0.25.
    Mutant 18 (``+``) yields 2000.25 and dies on the duration/message pins.
    Mutants 3/4/5 (url/headers/json -> None) and 7/8 (headers/json kwarg
    dropped) die on the post-call pin; 9-16 (payload key renames and the
    max_tokens 50->51 / temperature 0.1->1.1 numeric flips) die on the
    exact payload dict; 19 (debug message -> None), 20/22 (extra=None /
    dropped -> record.duration absent) and 23/24 (extra key renames) die on
    the DEBUG pins.
    """
    clock = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["t"])

    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = MagicMock(return_value=None)

    async def _post(*args, **kwargs):
        clock["t"] = 1000.25
        return resp

    a, client = _probe_analyzer(AsyncMock(side_effect=_post))
    got = await a.model_readiness_probe()

    assert got is True
    call = client.post.call_args
    assert call.args == ("http://nemotron-probe:8091/v1/completions",)
    assert call.kwargs == {
        "headers": {"X-Auth-Sentinel": "AUTH-HEADERS"},
        "json": {
            "prompt": "WARMUP-PROMPT-MARKER",
            "max_tokens": 50,
            "temperature": 0.1,
        },
    }
    assert [r.levelno for r in logs] == [logging.DEBUG]
    assert logs[0].getMessage() == "Nemotron readiness probe completed in 0.25s"
    assert getattr(logs[0], "duration", "<absent>") == 0.25


@pytest.mark.asyncio
async def test_mrp_02_connection_error_warning_text(logs):
    """Kills model_readiness_probe__mutmut_26.

    MEASURED shipped: httpx.ConnectError -> WARNING
    "Nemotron readiness probe connection error: {e}", return False.  The
    None-message mutant fails the exact-message pin.
    """
    a, _ = _probe_analyzer(AsyncMock(side_effect=httpx.ConnectError("conn-refused-marker")))
    got = await a.model_readiness_probe()
    assert got is False
    assert [r.levelno for r in logs] == [logging.WARNING]
    assert logs[0].getMessage() == (
        "Nemotron readiness probe connection error: conn-refused-marker"
    )


@pytest.mark.asyncio
async def test_mrp_03_timeout_warning_text(logs):
    """Kills model_readiness_probe__mutmut_28.

    MEASURED shipped: httpx.TimeoutException -> WARNING
    "Nemotron readiness probe timeout: {e}", return False.
    """
    a, _ = _probe_analyzer(AsyncMock(side_effect=httpx.TimeoutException("too-slow-marker")))
    got = await a.model_readiness_probe()
    assert got is False
    assert [r.levelno for r in logs] == [logging.WARNING]
    assert logs[0].getMessage() == "Nemotron readiness probe timeout: too-slow-marker"


@pytest.mark.asyncio
async def test_mrp_04_http_status_error_warning_text(logs):
    """Kills model_readiness_probe__mutmut_30.

    MEASURED shipped: raise_for_status -> httpx.HTTPStatusError -> WARNING
    "Nemotron readiness probe HTTP error: {e}", return False.
    """
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 503
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server-meltdown", request=MagicMock(spec=httpx.Request), response=resp
    )
    a, _ = _probe_analyzer(AsyncMock(return_value=resp))
    got = await a.model_readiness_probe()
    assert got is False
    assert [r.levelno for r in logs] == [logging.WARNING]
    assert logs[0].getMessage() == "Nemotron readiness probe HTTP error: server-meltdown"


# =========================================================================
# NemotronAnalyzer._run_enrichment_pipeline  (shipped L3664-3742)
# =========================================================================


def _mkdet(**kw):
    base = dict(
        id=1,
        camera_id="cam",
        file_path="/export/img1.jpg",
        detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        object_type="person",
        confidence=0.9,
        bbox_x=10,
        bbox_y=20,
        bbox_width=30,
        bbox_height=40,
        video_width=1920,
        video_height=1080,
    )
    base.update(kw)
    return Detection(**base)


def _pipeline_analyzer():
    a = _analyzer()
    pipe = MagicMock(name="pipeline")
    pipe.enrich_batch_with_tracking = AsyncMock(return_value="TRACKING-SENTINEL")
    a._get_enrichment_pipeline = MagicMock(return_value=pipe)
    return a, pipe


@pytest.mark.asyncio
async def test_rep_01_detection_input_fields_pinned_exactly():
    """Kills _run_enrichment_pipeline__mutmut_17, _18, _19, _20, _25, _26,
    _27, _28, _29, _30, _31, _32, _40, _42.

    MEASURED shipped for det(x=10,y=20,w=30,h=40,conf=0.9,vw=1920,vh=1080):
    DetectionInput(id=1, class_name="person", confidence=0.9,
    bbox=BoundingBox(x1=10.0, y1=20.0, x2=40.0, y2=60.0, confidence=0.0),
    video_width=1920, video_height=1080) and for a confidence=None det the
    shipped ``det.confidence or 0.0`` yields EXACTLY 0.0 (probed).  The
    pipeline is awaited as enrich_batch_with_tracking(inputs, images,
    camera_id=camera_id) — inputs/images positional, camera_id keyword
    (probed) — and its result is returned.

    17 (confidence=None) and 27 (``and 0.0`` -> 0.0 for a truthy 0.9) die
    on the 0.9 pin; 28 (``or 1.0``) on the None-confidence 0.0 pin; 18
    (bbox=None), 29-32 (a coordinate -> None) and 40/42 (x2/y2 computed by
    SUBTRACTION) on the exact BoundingBox equality; 19/20/25/26 (video
    dims -> None / kwargs dropped -> dataclass default None) on the 1920/1080
    pins.
    """
    a, pipe = _pipeline_analyzer()
    dets = [_mkdet(), _mkdet(id=2, file_path="/export/img2.jpg", confidence=None)]

    got = await a._run_enrichment_pipeline(dets, camera_id="cam-x")

    assert got == "TRACKING-SENTINEL"
    call = pipe.enrich_batch_with_tracking.call_args
    assert call.kwargs == {"camera_id": "cam-x"}
    inputs, images = call.args
    assert images == {
        1: "/export/img1.jpg",
        2: "/export/img2.jpg",
        None: "/export/img1.jpg",
    }
    assert [d.id for d in inputs] == [1, 2]
    di = inputs[0]
    assert di.class_name == "person"
    assert di.confidence == 0.9
    assert di.bbox == BoundingBox(x1=10.0, y1=20.0, x2=40.0, y2=60.0)
    assert di.video_width == 1920
    assert di.video_height == 1080
    di2 = inputs[1]
    assert di2.confidence == 0.0  # shipped: `det.confidence or 0.0` on None
    assert di2.class_name == "person"


@pytest.mark.asyncio
async def test_rep_02_each_missing_field_skips_the_detection():
    """Kills _run_enrichment_pipeline__mutmut_4, _5, _6, _7.

    MEASURED shipped: a detection with ANY ONE of bbox_x/bbox_y/
    bbox_width/bbox_height/object_type set to None is skipped (the
    five-way OR at L3695-3701); with only such detections the method
    returns None BEFORE building the pipeline.  Each or->and mutant keeps
    the detection whose (and-ed) pair is not both-None and crashes on
    float(None) (or at least calls the builder) — both fail this pin.
    """
    for field in ("bbox_x", "bbox_y", "bbox_width", "bbox_height", "object_type"):
        a, pipe = _pipeline_analyzer()
        dets = [_mkdet(id=9, **{field: None})]
        got = await a._run_enrichment_pipeline(dets, camera_id="cam")
        assert got is None, f"detection with {field}=None must be skipped"
        assert a._get_enrichment_pipeline.call_count == 0
        pipe.enrich_batch_with_tracking.assert_not_called()


@pytest.mark.asyncio
async def test_rep_03_invalid_detection_does_not_abort_the_loop():
    """Kills _run_enrichment_pipeline__mutmut_13 (continue -> break).

    MEASURED shipped (probed): list [invalid, valid, invalid, valid]
    processes the WHOLE list -> detection_inputs ids [2, 4].  The break
    mutant stops at the first invalid detection -> no inputs -> returns
    None before the pipeline (probed break semantics).
    """
    a, pipe = _pipeline_analyzer()
    dets = [
        _mkdet(id=1, bbox_x=None),
        _mkdet(id=2),
        _mkdet(id=3, object_type=None),
        _mkdet(id=4),
    ]
    got = await a._run_enrichment_pipeline(dets, camera_id="cam")
    assert got == "TRACKING-SENTINEL"
    inputs = pipe.enrich_batch_with_tracking.call_args.args[0]
    assert [d.id for d in inputs] == [2, 4]


@pytest.mark.asyncio
async def test_rep_04_shared_image_requires_first_detection_file_path():
    """Kills _run_enrichment_pipeline__mutmut_46 (``and`` -> ``or``).

    MEASURED shipped: with detections[0].file_path None the images dict is
    EXACTLY {2: <second path>} — the ``if detections and
    detections[0].file_path`` guard (L3727) keeps images[None] ABSENT
    (probed: None not in images).  The ``or`` mutant unconditionally sets
    images[None] = None once a pipeline run is happening.
    """
    a, pipe = _pipeline_analyzer()
    dets = [_mkdet(id=1, file_path=None), _mkdet(id=2, file_path="/export/img2.jpg")]
    got = await a._run_enrichment_pipeline(dets, camera_id="cam")
    assert got == "TRACKING-SENTINEL"
    images = pipe.enrich_batch_with_tracking.call_args.args[1]
    assert None not in images
    assert images == {2: "/export/img2.jpg"}


# =========================================================================
# NemotronAnalyzer._enqueue_for_evaluation  (shipped L4564-4601)
# =========================================================================


@pytest.mark.asyncio
async def test_ee_01_success_pins_queue_arg_and_debug(logs):
    """Kills _enqueue_for_evaluation__mutmut_6, _11.

    MEASURED shipped: get_evaluation_queue is called with the analyzer's
    OWN redis client (positional — probed call(REDIS-SENTINEL)); then
    ``await queue.enqueue(event_id=event_id, priority=risk_score)``; then
    ONE DEBUG record "Enqueued event {event_id} for background evaluation
    (priority: {risk_score})".  Mutant 6 (queue(get_evaluation_queue(None)))
    dies on the queue-argument pin (the repo test patches
    get_evaluation_queue with a return_value only and never inspects the
    argument, so it does NOT kill this key); mutant 11 (debug message ->
    None) on the message pin.
    """
    a = _analyzer()
    a._redis = "REDIS-SENTINEL"
    queue = MagicMock(name="queue")
    queue.enqueue = AsyncMock()
    settings = MagicMock()
    settings.background_evaluation_enabled = True

    with (
        patch(
            "backend.services.evaluation_queue.get_evaluation_queue",
            autospec=True,
            side_effect=lambda redis_client: queue,
        ) as geq,
        patch("backend.core.config.get_settings", autospec=True, return_value=settings),
    ):
        await a._enqueue_for_evaluation(event_id=123, risk_score=75)

    assert geq.call_args.args == ("REDIS-SENTINEL",)
    assert queue.enqueue.call_args.kwargs == {"event_id": 123, "priority": 75}
    assert [r.levelno for r in logs] == [logging.DEBUG]
    assert logs[0].getMessage() == ("Enqueued event 123 for background evaluation (priority: 75)")


@pytest.mark.asyncio
async def test_ee_02_disabled_debug_text(logs):
    """Kills _enqueue_for_evaluation__mutmut_4.

    MEASURED shipped: background_evaluation_enabled False -> ONE DEBUG
    record "Background evaluation disabled, not queueing event 99" and no
    queue touched.  The debug(None) mutant fails the message pin (the repo
    disabled-test asserts only "does not raise").
    """
    a = _analyzer()
    a._redis = "REDIS"
    settings = MagicMock()
    settings.background_evaluation_enabled = False
    with patch("backend.core.config.get_settings", autospec=True, return_value=settings):
        await a._enqueue_for_evaluation(event_id=99, risk_score=10)
    assert [r.levelno for r in logs] == [logging.DEBUG]
    assert logs[0].getMessage() == "Background evaluation disabled, not queueing event 99"


@pytest.mark.asyncio
async def test_ee_03_failure_warning_pins_message_and_extra(logs):
    """Kills _enqueue_for_evaluation__mutmut_12, _13, _15, _16, _17, _18,
    _19, _20, _21, _22, _23.

    MEASURED shipped: when queue.enqueue raises, the except-branch emits
    ONE WARNING record:
      message "Failed to enqueue event for evaluation"
      extra   {"event_id": event_id, "error": str(e)} -> record.event_id ==
              55 and record.error == "redis-down" (both probed present)
    and swallows the exception.  Mutants 12/16/17/18 (message None /
    XX-wrapped / lower / upper) die on the message; 13/15 (extra None /
    dropped) and 19/20/21/22 (event_id / error key renames) on the record
    attribute pins; 23 ("error": str(None)) on the record.error VALUE.
    """
    a = _analyzer()
    a._redis = "REDIS"
    queue = MagicMock(name="queue")
    queue.enqueue = AsyncMock(side_effect=RuntimeError("redis-down"))
    settings = MagicMock()
    settings.background_evaluation_enabled = True

    with (
        patch(
            "backend.services.evaluation_queue.get_evaluation_queue",
            autospec=True,
            return_value=queue,
        ),
        patch("backend.core.config.get_settings", autospec=True, return_value=settings),
    ):
        await a._enqueue_for_evaluation(event_id=55, risk_score=3)

    assert [r.levelno for r in logs] == [logging.WARNING]
    rec = logs[0]
    assert rec.getMessage() == "Failed to enqueue event for evaluation"
    assert getattr(rec, "event_id", "<absent>") == 55
    assert getattr(rec, "error", "<absent>") == "redis-down"


# =========================================================================
# NemotronAnalyzer._to_serializable  (shipped L1700-1714, staticmethod)
# =========================================================================


@dataclasses.dataclass
class _DC:
    a: int
    b: str


class _PM(BaseModel):
    x: int = 1
    nested: dict[str, int] = {}


def _tsr(obj):
    return NA.NemotronAnalyzer._to_serializable(obj)


def test_tsr_01_passthrough_branch():
    """PRIMARY kills _to_serializable__mutmut_1, _3, _4, _5, _8.

    MEASURED shipped: None -> None; a dict/list/int/str passes through BY
    IDENTITY.  Mutant 1 (``obj is not None``) returns None for every
    non-None input; mutants 3 (hasattr(obj, None)), 4 (hasattr("model_dump"))
    and 5 (hasattr(obj, )) raise TypeError at the hasattr call for ANY
    non-None input; mutant 8 (``or not isinstance(obj, type)``) sends every
    non-type input into dataclasses.asdict -> TypeError for the plain dict.
    """
    assert _tsr(None) is None
    d = {"k": 1}
    lst = [1, 2]
    assert _tsr(d) is d
    assert _tsr(lst) is lst
    assert _tsr(7) == 7
    assert _tsr("s") == "s"


def test_tsr_02_pydantic_branch_uses_model_dump():
    """Kills _to_serializable__mutmut_2, _6, _7.

    MEASURED shipped: an object with .model_dump() is converted through
    model_dump() -> EXACT dict {"x": 3, "nested": {}} (probed).  Mutant 2
    (hasattr(None, "model_dump") -> False), 6 ("XXmodel_dumpXX") and 7
    ("MODEL_DUMP") skip the branch and return the model INSTANCE itself —
    the identity-vs-dict pin kills them.  (3/4/5 raise TypeError at the
    hasattr call on ANY non-None input; they are PRIMARY-KILLED by
    test_tsr_01_passthrough_branch, which runs the same crash on a plain
    dict.)
    """
    pm = _PM(x=3)
    got = _tsr(pm)
    assert got == {"x": 3, "nested": {}}
    assert got is not pm


def test_tsr_03_dataclass_instance_uses_asdict():
    """Kills _to_serializable__mutmut_9, _11 (mutants 3/4/5 crash here too
    and mutant 10 dies here as well — their primary pins live in
    test_tsr_01_passthrough_branch and test_tsr_04_dataclass_class_passes_through_by_identity).

    MEASURED shipped: a dataclass INSTANCE becomes
    dataclasses.asdict(obj) == {"a": 5, "b": "q"} (probed).  Mutant 9
    (is_dataclass(None)) skips the branch and returns the instance itself;
    mutant 11 (asdict(None)) raises TypeError.
    """
    inst = _DC(a=5, b="q")
    assert _tsr(inst) == {"a": 5, "b": "q"}


def test_tsr_04_dataclass_class_passes_through_by_identity():
    """Kills _to_serializable__mutmut_8 and _to_serializable__mutmut_10
    (redundant pins: for the verdict ledger key 8 is attributed to
    test_tsr_01_passthrough_branch and key 10 to
    test_tsr_03_dataclass_instance_uses_asdict — both die on those inputs
    too; this test kills them on the dataclass-CLASS input instead).

    MEASURED shipped: the dataclass CLASS (is_dataclass True but
    isinstance(obj, type) True) is EXCLUDED by the
    ``and not isinstance(obj, type)`` guard and returned by identity
    (probed: ``_tsr(DC) is DC`` True).  Mutant 8 (or) and 10 (inverted
    isinstance) route the class into dataclasses.asdict -> TypeError
    (asdict requires an instance).
    """
    assert _tsr(_DC) is _DC


# =========================================================================
# NemotronAnalyzer._get_auth_headers  (shipped L2316-2339)
# =========================================================================


CORR = {"X-Correlation-Sentinel": "CID-42"}


def _auth_headers(api_key):
    a = _analyzer()
    a._api_key = api_key
    with patch(
        f"{MOD}.get_correlation_headers",
        autospec=True,
        return_value=dict(CORR),
    ):
        return a._get_auth_headers()


def test_ga_01_secret_str_key_uses_get_secret_value():
    """Kills _get_auth_headers__mutmut_4, _8, _9.

    MEASURED shipped: with a SecretStr key the header value is
    key.get_secret_value() -> "sekret-value" (probed).  All three mutants
    replace the hasattr(self._api_key, "get_secret_value") operand
    (hasattr(None, ...), "XXget_secret_valueXX", "GET_SECRET_VALUE") so the
    check goes False and the shipped fallback ``str(self._api_key)`` emits
    the MASKED pydantic repr instead of the secret — killed on the exact
    header dict.  (The repo's with-api-key test uses a plain str, where
    every mutant is value-identical, so it does NOT kill these keys.)

    Also pins the shipped str/None/"" passthrough contract (probed): a
    plain str key ships str(self._api_key) verbatim and a falsy key ships
    NO X-API-Key header — these paths are mutant-invariant for this chunk
    and guard the SecretStr premise.
    """
    headers = _auth_headers(SecretStr("sekret-value"))
    assert headers == {"X-Correlation-Sentinel": "CID-42", "X-API-Key": "sekret-value"}
    assert _auth_headers("plain-key") == {
        "X-Correlation-Sentinel": "CID-42",
        "X-API-Key": "plain-key",
    }
    assert _auth_headers(None) == {"X-Correlation-Sentinel": "CID-42"}
    assert _auth_headers("") == {"X-Correlation-Sentinel": "CID-42"}


# =========================================================================
# NemotronAnalyzer.record_rollout_feedback  (shipped L1258-1280)
# =========================================================================


def test_rrb_01_routes_by_exact_camera_id_both_groups():
    """Kills record_rollout_feedback__mutmut_3.

    MEASURED shipped: get_group_for_camera is called with the EXACT
    camera_id string (probed call('camera-9')) and the returned group
    routes TREATMENT -> record_treatment_feedback(is_false_positive) and
    CONTROL -> record_control_feedback (both probed; None does NOT compare
    equal to ExperimentGroup.CONTROL, so the mutant cannot dodge the pin by
    landing in the other routing branch).  The mutant passes None instead
    of camera_id -> assert_called_once_with dies on BOTH blocks (the repo
    control-group test uses a return_value-only MagicMock whose result
    ignores arguments and never inspects the call, so it does NOT kill this
    key).
    """
    a = _analyzer()
    mgr = MagicMock(name="rollout")
    mgr.get_group_for_camera.return_value = ExperimentGroup.TREATMENT
    a._rollout_manager = mgr

    a.record_rollout_feedback("camera-9", is_false_positive=True)

    mgr.get_group_for_camera.assert_called_once_with("camera-9")
    mgr.record_treatment_feedback.assert_called_once_with(True)
    mgr.record_control_feedback.assert_not_called()

    mgr2 = MagicMock(name="rollout2")
    mgr2.get_group_for_camera.return_value = ExperimentGroup.CONTROL
    a._rollout_manager = mgr2

    a.record_rollout_feedback("camera-3", is_false_positive=False)

    mgr2.get_group_for_camera.assert_called_once_with("camera-3")
    mgr2.record_control_feedback.assert_called_once_with(False)
    mgr2.record_treatment_feedback.assert_not_called()
