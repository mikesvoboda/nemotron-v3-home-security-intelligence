"""Batch-25 part 26 — chunk "tail:A" (97 keys) in backend/services/nemotron_analyzer.py.

Six functions are in scope. Key -> site map, verified occurrence-by-occurrence
against the instrumented copy
(mutants/backend/services/nemotron_analyzer.py, variant bodies
xǁNemotronAnalyzerǁ<fn>__mutmut_<N>):

_get_enrichment_result_from_data (shipped L2126-2219; 33 keys)
  call site L2159-2161 (``await self._run_enrichment_pipeline_from_data(
      detections_data, camera_id=camera_id)``):
    2  whole call -> None                      3  detections_data -> None
    4  camera_id -> None                       5  positional detections_data dropped
    6  camera_id kwarg dropped
  except-arm logger.warning L2203-2207:
    7   msg -> None            8   extra -> None       9   exc_info -> None
    11  extra= line removed    12  exc_info= line removed
    13  msg -> "XX..XX"        14  msg -> lowercase    15  msg -> UPPERCASE
    16  "batch_id" -> "XXbatch_idXX"   17 -> "BATCH_ID"
    18  "error" -> "XXerrorXX"         19 -> "ERROR"
    20  str(e) -> str(None)            21 exc_info=True -> False
  except-arm EnrichmentTrackingResult(...) L2210-2216:
    22 status -> None          23 successful_models -> None
    24 failed_models -> None   25 errors -> None
    26 status= line removed    27 successful_models= line removed  (EQUIVALENT)
    28 failed_models= line removed      29 errors= line removed
    30 data= line removed                                    (EQUIVALENT)
    31 ["all"] -> ["XXallXX"]  32 -> ["ALL"]
    33 {"all":...} -> {"XXallXX":...}   34 -> {"ALL":...}   35 str(e) -> str(None)

  EQUIVALENCE PROOFS (2 keys): both removals land on a dataclass field whose
  default already equals the removed argument, so no observable differs —
  27: ``successful_models=[],`` removed at L2211 while
      backend/services/enrichment_pipeline.py:538 declares
      ``successful_models: list[str] = field(default_factory=list)`` -> the
      constructed object holds a fresh empty list either way (literal no-op).
  30: ``data=None,`` removed at L2215 while
      backend/services/enrichment_pipeline.py:541 declares
      ``data: EnrichmentResult | None = None`` -> None either way (literal no-op).
  Every other key in this group changes a value some caller reads:
  analyze_batch reads ``.has_data``/``.data``
  (nemotron_analyzer.py:2571-2577), ``success_rate``/``failed_models``/
  ``successful_models`` are read by the partial-failure log at L2164-2180, and
  the LogRecord message/extra/ exc_info are written straight to the log stream.

_broadcast_event (shipped L4472-4523; 21 keys)
  soft-deleted debug L4491-4494:
    3  msg -> None        4  extra -> None      6  extra= line removed
    7  "event_id" -> "XXevent_idXX"   8 -> "EVENT_ID"
    9  "deleted_at" -> "XXdeleted_atXX"  10 -> "DELETED_AT"
  broadcast payload dict L4502-4513:
    22/23 "batch_id" -> "XXbatch_idXX"/"BATCH_ID"
    24/25 "camera_id" -> "XXcamera_idXX"/"CAMERA_ID"
    30/31 "summary"   -> "XXsummaryXX"/"SUMMARY"
    32/33 "reasoning" -> "XXreasoningXX"/"REASONING"
    34/35 "started_at"-> "XXstarted_atXX"/"STARTED_AT"
    36 "if event.started_at" -> "and False"   37 -> "or True"
  39 get_broadcaster(self._redis) -> get_broadcaster(None)
  41 success debug message -> None

_check_idempotency (shipped L1523-1555; 18 keys)
  hit debug L1542-1545:
    6  msg -> None   7  extra -> None   9  extra= line removed
    10/11 "batch_id" -> "XXbatch_idXX"/"BATCH_ID"
    12/13 "event_id" -> "XXevent_idXX"/"EVENT_ID"
  fail-open warning L1551-1554:
    15 msg -> None   16 extra -> None   18 extra= line removed
    19 msg -> "XX..XX"  20 -> lowercase  21 -> UPPERCASE
    22/23 "batch_id" -> "XXbatch_idXX"/"BATCH_ID"
    24/25 "error" -> "XXerrorXX"/"ERROR"
    26 str(e) -> str(None)

_enrich_with_trajectory_analysis (shipped L1931-1959; 14 keys)
  1   ``if enrichment_result is None`` -> ``is not None``
  2/3/4/5  that arm's debug message -> None/"XX..XX"/lowercase/UPPERCASE
  6   trackable_detections comprehension -> None
  7/8/9  d.get("track_id") -> d.get(None)/"XXtrack_idXX"/"TRACK_ID"
  11  ``if not trackable_detections`` -> ``if trackable_detections``
  12/13/14/15  second debug message -> None/"XX..XX"/lowercase/UPPERCASE

_format_detections (shipped L3637-3662; 7 keys)
  5  enumerate(detections, 1) -> (detections, )      6  -> (detections, 2)
  9  "%H:%M:%S" -> "XX%H:%M:%SXX"   13 "unknown" -> "XXunknownXX"
  19 quality.value.upper() -> .lower()               21 "N/A" -> "XXN/AXX"
  25 "\\n".join -> "XX\\nXX".join

_get_existing_event (shipped L1581-1591; 4 keys)
  2  execute(select(...)) -> execute(None)     3  .where(Event.id == event_id) -> .where(None)
  4  select(Event) -> select(None)             5  == -> !=

OCCURRENCE TWINS: none in this chunk — every shape group in feed.json holds
exactly one key (all 97 keys sit in 97 distinct single-key shape groups), so
no group-verdict is split across chunks.

killed_by_draft is empty for this chunk. The repo's tests for these functions
are all observable-blind to the mutated surface:
 - test_nemotron_analyzer.py:234-264 (_format_detections) asserts only
   substring membership — "unknown" is a substring of "XXunknownXX" and
   "N/A" of "XXN/AXX", and no assertion mentions the ordinal, the tier case
   or the separator;
 - :591-633 asserts message["type"]/data["id"]/data["event_id"]/risk_score/
   risk_level — none of the mutated payload keys;
 - :653-683 (soft-deleted) asserts only ``broadcast_event.assert_not_called()``;
 - :2839-2915/:3180-3209 (_check_idempotency) assert only the return value;
 - :1965-2075 tracks the args of _get_enrichment_result_from_data itself (it
   is replaced by a fake), and :2110-2198 drives the failing pipeline through
   analyze_batch asserting only ``event is not None`` / risk_score — which is
   invariant under all 33 mutants because every one of them still yields a
   falsy/failed enrichment path;
 - every streaming test stubs ``_get_existing_event``/``_broadcast_event`` with
   AsyncMock, so those bodies never execute.
The draft battery /tmp/wp-batch25/test_nemotron_analyzer_batch25.py only
touches _extract_json_from_response/_validate_* and never calls these six
functions.

All pinned expected values below were read off the SHIPPED functions with
/tmp/wp-batch25/probes/ch26/probe*.py (e.g. shipped
_format_detections renders
'  1. 14:30:00 - person (confidence: 0.95 EXCELLENT)\\n  2. ...', the failed
tracking result is EnrichmentTrackingResult(status=FAILED,
successful_models=[], failed_models=['all'], errors={'all': 'boom'},
data=None), and the warning record carries batch_id/error plus a live
exc_info triple), not from expectation.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_26.py -p no:cacheprovider -o addopts= -q
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
# import (values copied verbatim from backend/tests/conftest.py / part 17).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

from sqlalchemy import select

from backend.core.config import Settings
from backend.core.redis import RedisClient
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.enrichment_pipeline import (
    EnrichmentResult,
    EnrichmentStatus,
    EnrichmentTrackingResult,
)
from backend.services.nemotron_analyzer import NemotronAnalyzer

LOGGER = "backend.services.nemotron_analyzer"


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def mock_settings():
    """Settings mirroring the repo unit fixture (values copied, not invented)."""
    m = MagicMock(spec=Settings)
    m.nemotron_url = "http://localhost:8091"
    m.nemotron_api_key = None
    m.ai_connect_timeout = 10.0
    m.nemotron_read_timeout = 120.0
    m.ai_health_timeout = 5.0
    m.nemotron_max_retries = 2
    m.severity_low_max = 29
    m.severity_medium_max = 59
    m.severity_high_max = 84
    m.nemotron_context_window = 4096
    m.nemotron_max_output_tokens = 1536
    m.context_utilization_warning_threshold = 0.80
    m.context_truncation_enabled = True
    m.llm_tokenizer_encoding = "cl100k_base"
    m.image_quality_enabled = False
    m.ai_warmup_enabled = True
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
    return m


@pytest.fixture
def analyzer(mock_settings):
    """NemotronAnalyzer with a Redis mock, built under the repo's get_settings patches."""
    from backend.services.analyzer_facade import reset_analyzer_facade
    from backend.services.inference_semaphore import reset_inference_semaphore
    from backend.services.severity import reset_severity_service
    from backend.services.token_counter import reset_token_counter

    redis_client = MagicMock(spec=RedisClient)
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.publish = AsyncMock(return_value=1)
    with (
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            return_value=mock_settings,
            autospec=True,
        ),
        patch("backend.services.severity.get_settings", return_value=mock_settings, autospec=True),
        patch(
            "backend.services.token_counter.get_settings", return_value=mock_settings, autospec=True
        ),
        patch("backend.core.config.get_settings", return_value=mock_settings, autospec=True),
        patch(
            "backend.services.inference_semaphore.get_settings",
            return_value=mock_settings,
            autospec=True,
        ),
    ):
        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()
        try:
            an = NemotronAnalyzer(redis_client=redis_client)
            yield an
        finally:
            reset_severity_service()
            reset_token_counter()
            reset_analyzer_facade()
            reset_inference_semaphore()


class Collector(logging.Handler):
    """Collect this module's records verbatim (caplog's handler level is not enough here)."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name == LOGGER:
            self.records.append(record)

    @property
    def messages(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def only(self) -> logging.LogRecord:
        assert len(self.records) == 1, f"expected exactly one record, got {self.messages}"
        return self.records[0]


@pytest.fixture
def logbox():
    """Attach a DEBUG collector to the analyzer logger for one test."""
    logger = logging.getLogger(LOGGER)
    previous = logger.level
    logger.setLevel(logging.DEBUG)
    handler = Collector()
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def extras(record: logging.LogRecord, keys: tuple[str, ...]) -> dict:
    """Only the extra= keys under test (ContextFilter injects unrelated ones)."""
    return {k: getattr(record, k, "<absent>") for k in keys}


# ------------------------------------------------------------------ _get_enrichment_result_from_data


@pytest.mark.asyncio
async def test_enrichment_from_data_success_passthrough_and_call_shape(analyzer, logbox):
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_get_enrichment_result_from_data__mutmut_2, _3, _4, _5, _6.

    Shipped (L2159-2161) forwards detections_data positionally and camera_id by
    keyword to _run_enrichment_pipeline_from_data and returns whatever it yields
    (probe: ``call([{'id': 2}], camera_id='cam-10')`` and ``res is sentinel``).
    3/4/6 break the forwarded shape, 5 drops the positional (autospec raises
    TypeError *inside* the try, so the mutant returns the FAILED result instead
    of the pipeline's object), 2 replaces the whole call with None.
    """
    sentinel = EnrichmentTrackingResult(status=EnrichmentStatus.SKIPPED)
    detections_data = [{"id": 2}]
    with patch.object(
        analyzer, "_run_enrichment_pipeline_from_data", autospec=True, return_value=sentinel
    ) as pipeline:
        result = await analyzer._get_enrichment_result_from_data(
            "batch-10", detections_data, camera_id="cam-10"
        )

    assert result is sentinel, "shipped returns the pipeline's tracking result verbatim"
    assert pipeline.await_args.args == (detections_data,), pipeline.await_args
    assert pipeline.await_args.kwargs == {"camera_id": "cam-10"}, pipeline.await_args
    assert logbox.records == [], (
        "SKIPPED result is not partial/failed/data-bearing: L2162-2186 logs nothing"
    )


@pytest.mark.asyncio
async def test_enrichment_from_data_failure_warning_text_and_extra(analyzer, logbox):
    """Kills ..._get_enrichment_result_from_data__mutmut_7, _8, _11, _13, _14, _15, _16, _17, _18, _19, _20.

    Shipped except-arm warning (L2203-2207) is
    "Enrichment pipeline failed, continuing without enrichment" with
    extra={"batch_id": batch_id, "error": str(e)}; the ContextFilter turns that
    dict into record attributes, so a renamed/removed/dereferenced key shows up
    as a missing attribute and a rewritten message as a different getMessage().
    """

    async def boom(*args, **kwargs):
        raise RuntimeError("boom")

    analyzer._run_enrichment_pipeline_from_data = boom
    result = await analyzer._get_enrichment_result_from_data(
        "batch-9", [{"id": 1}], camera_id="cam-9"
    )

    assert logbox.messages == ["Enrichment pipeline failed, continuing without enrichment"]
    record = logbox.only()
    assert record.levelno == logging.WARNING
    assert extras(record, ("batch_id", "error")) == {"batch_id": "batch-9", "error": "boom"}
    assert result.status is EnrichmentStatus.FAILED


@pytest.mark.asyncio
async def test_enrichment_from_data_failure_exc_info(analyzer, logbox):
    """Kills ..._get_enrichment_result_from_data__mutmut_9, _12, _21.

    Shipped passes ``exc_info=True`` (L2206), so the record carries the live
    (type, value, tb) triple; None (9), a removed kwarg (12) and False (21) all
    leave record.exc_info non-truthy/or False.
    """

    async def boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    analyzer._run_enrichment_pipeline_from_data = boom
    await analyzer._get_enrichment_result_from_data("batch-e", [{"id": 1}], camera_id="cam-e")

    record = logbox.only()
    assert record.exc_info is not None and record.exc_info[0] is RuntimeError
    assert isinstance(record.exc_info[1], RuntimeError)
    assert str(record.exc_info[1]) == "kaboom"


@pytest.mark.asyncio
async def test_enrichment_from_data_failed_tracking_result_fields(analyzer, logbox):
    """Kills ..._get_enrichment_result_from_data__mutmut_22, _23, _24, _25, _26, _28, _29, _31, _32, _33, _34, _35.

    Shipped except-arm return (L2210-2216) is exactly
    EnrichmentTrackingResult(status=EnrichmentStatus.FAILED,
    successful_models=[], failed_models=["all"], errors={"all": str(e)},
    data=None) — probe-confirmed. ``analyze_batch`` reads .has_data/.data
    (L2575-2577) and the partial-failure path reads success_rate/failed_models
    (L2164-2180), so each field value is a live contract. Keys 27 and 30 are the
    two provably-equivalent removals and are asserted here as the shipped
    defaults they cannot escape.
    """

    async def boom(*args, **kwargs):
        raise ValueError("plate model exploded")

    analyzer._run_enrichment_pipeline_from_data = boom
    result = await analyzer._get_enrichment_result_from_data(
        "batch-f", [{"id": 3}], camera_id="cam-f"
    )

    assert result.status is EnrichmentStatus.FAILED
    assert result.successful_models == []
    assert result.failed_models == ["all"]
    assert result.errors == {"all": "plate model exploded"}
    assert result.data is None
    assert result.all_failed is True
    assert result.has_data is False
    assert result.success_rate == 0.0


# ------------------------------------------------------------------------ _check_idempotency


@pytest.mark.asyncio
async def test_check_idempotency_hit_debug_message_and_extra(analyzer, logbox):
    """Kills ..._check_idempotency__mutmut_6, _7, _9, _10, _11, _12, _13.

    Shipped hit arm (L1541-1546) logs the f-string
    "Idempotency check: batch {batch_id} already has event {event_id}" at DEBUG
    with extra={"batch_id": batch_id, "event_id": event_id} and returns
    int(event_id). Redis holds the string "42", so the record's event_id is the
    string and the return value the int (probe-confirmed).
    """
    analyzer._redis.get = AsyncMock(return_value="42")

    result = await analyzer._check_idempotency("b-7")

    assert result == 42
    assert logbox.messages == ["Idempotency check: batch b-7 already has event 42"]
    record = logbox.only()
    assert record.levelno == logging.DEBUG
    assert extras(record, ("batch_id", "event_id")) == {"batch_id": "b-7", "event_id": "42"}


@pytest.mark.asyncio
async def test_check_idempotency_fail_open_warning_text_and_extra(analyzer, logbox):
    """Kills ..._check_idempotency__mutmut_15, _16, _18, _19, _20, _21, _22, _23, _24, _25, _26.

    Shipped fail-open arm (L1549-1555) logs
    "Idempotency check failed, proceeding" at WARNING with
    extra={"batch_id": batch_id, "error": str(e)} and returns None. str(e) is
    the Redis error text, so key 26 (str(None)) is caught by the value of the
    ``error`` attribute, and 22/23/24/25 by its presence.
    """
    analyzer._redis.get = AsyncMock(side_effect=RuntimeError("redis down"))

    result = await analyzer._check_idempotency("b-err")

    assert result is None
    assert logbox.messages == ["Idempotency check failed, proceeding"]
    record = logbox.only()
    assert record.levelno == logging.WARNING
    assert extras(record, ("batch_id", "error")) == {"batch_id": "b-err", "error": "redis down"}


# ------------------------------------------------------------- _enrich_with_trajectory_analysis


@pytest.mark.asyncio
async def test_trajectory_none_result_arm_takes_the_first_early_return(analyzer, logbox):
    """Kills ..._enrich_with_trajectory_analysis__mutmut_1, _2, _3, _4, _5.

    Shipped L1951-1953: with enrichment_result None the ONLY observable is one
    debug record "No enrichment result available for trajectory analysis" and no
    DB session. Key 1 flips the guard, which makes the same drive fall through
    to the second early return and emit the *other* message instead — so this
    single exact-record assertion pins both the message text (2-5) and the
    guard polarity (1).
    """
    with patch("backend.services.nemotron_analyzer.get_session", autospec=True) as get_session:
        await analyzer._enrich_with_trajectory_analysis([], None, "cam-1")

    assert get_session.call_count == 0
    assert logbox.messages == ["No enrichment result available for trajectory analysis"]


@pytest.mark.asyncio
async def test_trajectory_trackable_detection_reaches_the_db_session(analyzer, logbox):
    """Kills ..._enrich_with_trajectory_analysis__mutmut_6, _7, _8, _9, _11.

    Shipped L1955-1959 keeps every detection whose d.get("track_id") is not
    None and, when that list is non-empty, opens exactly one DB session and
    logs nothing (probe: session 1, execute 1, zero records — the unfound track
    hits the L2019 ``continue``). Keys 6/7/8/9 empty the list (wrong key name /
    whole comprehension -> None) so the session is never opened and the second
    debug record appears; key 11 inverts the guard so the record appears even
    though the session is still opened.
    """
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=exec_result)

    detections_data = [{"track_id": 7, "camera_id": "cam-1", "id": 5, "object_type": "person"}]
    result = EnrichmentResult()
    with patch("backend.services.nemotron_analyzer.get_session", autospec=True) as get_session:
        get_session.return_value = session
        await analyzer._enrich_with_trajectory_analysis(detections_data, result, None)

    assert logbox.messages == [], (
        f"shipped logs nothing for a trackable detection: {logbox.messages}"
    )
    assert get_session.call_count == 1
    assert session.execute.await_count == 1
    assert result.trajectory_analyses == {}


@pytest.mark.asyncio
async def test_trajectory_empty_trackable_debug_message(analyzer, logbox):
    """Kills ..._enrich_with_trajectory_analysis__mutmut_12, _13, _14, _15.

    Shipped L1957-1959: detections present but none carrying a track_id yields
    exactly one debug record "No detections with track IDs for trajectory
    analysis" and no DB session.
    """
    with patch("backend.services.nemotron_analyzer.get_session", autospec=True) as get_session:
        await analyzer._enrich_with_trajectory_analysis(
            [{"id": 1, "object_type": "person"}], EnrichmentResult(), "cam-2"
        )

    assert get_session.call_count == 0
    assert logbox.messages == ["No detections with track IDs for trajectory analysis"]


# --------------------------------------------------------------------------- _format_detections


def test_format_detections_exact_rendering(analyzer):
    """Kills ..._format_detections__mutmut_5, _6, _9, _13, _19, _21, _25.

    Full-string pins of the shipped renderer (L3650-3662, probe-confirmed):
    1-based ordinal from ``enumerate(detections, 1)``, "%H:%M:%S" time,
    ``object_type or "unknown"``, ``f"{confidence:.2f} {quality.value.upper()}"``
    ("0.95 EXCELLENT" / "0.88 GOOD"), "N/A" when confidence is None, and a bare
    "\\n" join. The repo's own tests use substring membership only, which
    "XXunknownXX"/"XXN/AXX" survive.
    """
    d1 = Detection(
        id=1,
        camera_id="front_door",
        file_path="/export/foscam/front_door/img1.jpg",
        detected_at=datetime(2025, 12, 23, 14, 30, 0),
        object_type="person",
        confidence=0.95,
    )
    d2 = Detection(
        id=2,
        camera_id="front_door",
        file_path="/export/foscam/front_door/img2.jpg",
        detected_at=datetime(2025, 12, 23, 14, 30, 15),
        object_type="car",
        confidence=0.88,
    )
    assert analyzer._format_detections([d1, d2]) == (
        "  1. 14:30:00 - person (confidence: 0.95 EXCELLENT)\n"
        "  2. 14:30:15 - car (confidence: 0.88 GOOD)"
    )

    d3 = Detection(
        id=3,
        camera_id="front_door",
        file_path="/export/foscam/front_door/img3.jpg",
        detected_at=datetime(2025, 12, 23, 14, 30, 30),
        object_type=None,
        confidence=None,
    )
    assert analyzer._format_detections([d3]) == "  1. 14:30:30 - unknown (confidence: N/A)"
    assert analyzer._format_detections([]) == ""


# ---------------------------------------------------------------------------- _broadcast_event


@pytest.mark.asyncio
async def test_broadcast_soft_deleted_debug_message_and_extra(analyzer, logbox):
    """Kills ..._broadcast_event__mutmut_3, _4, _6, _7, _8, _9, _10.

    Shipped L4490-4495 logs
    "Skipping broadcast of soft-deleted event {event.id}" at DEBUG with
    extra={"event_id": event.id, "deleted_at": event.deleted_at.isoformat()}
    and returns before the try block. Probe-pinned deleted_at text:
    "2026-01-02T03:04:05+00:00".
    """
    event = Event(
        id=9,
        batch_id="b-9",
        camera_id="cam",
        started_at=datetime(2025, 12, 23, 14, 30, 0),
        risk_score=70,
        risk_level="high",
        summary="s",
        reasoning="r",
        deleted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    broadcaster = MagicMock()
    broadcaster.broadcast_event = AsyncMock()
    with patch(
        "backend.services.event_broadcaster.get_broadcaster",
        autospec=True,
        return_value=broadcaster,
    ):
        await analyzer._broadcast_event(event)

    broadcaster.broadcast_event.assert_not_awaited()
    assert logbox.messages == ["Skipping broadcast of soft-deleted event 9"]
    record = logbox.only()
    assert record.levelno == logging.DEBUG
    assert extras(record, ("event_id", "deleted_at")) == {
        "event_id": 9,
        "deleted_at": "2026-01-02T03:04:05+00:00",
    }


@pytest.mark.asyncio
async def test_broadcast_payload_key_names_and_started_at_branch(analyzer, logbox):
    """Kills ..._broadcast_event__mutmut_22, _23, _24, _25, _30, _31, _32, _33, _34, _35, _36, _37.

    Shipped payload (L4502-4513) is the canonical envelope
    {"type": "event", "data": {id, event_id, batch_id, camera_id, risk_score,
    risk_level, summary, reasoning, started_at}} with
    ``started_at.isoformat() if event.started_at else None``. Probe-pinned
    shipped dict for the started-at drive and ``"started_at": None`` for the
    started_at=None drive (which key 37 cannot produce — its ``or True`` makes
    the isoformat() call on None raise AttributeError, land in the except arm,
    and skip the broadcast entirely).
    """
    event = Event(
        id=10,
        batch_id="b-10",
        camera_id="cam",
        started_at=datetime(2025, 12, 23, 14, 30, 0),
        risk_score=70,
        risk_level="high",
        summary="summ",
        reasoning="reaso",
    )
    broadcaster = MagicMock()
    broadcaster.broadcast_event = AsyncMock()
    with patch(
        "backend.services.event_broadcaster.get_broadcaster",
        autospec=True,
        return_value=broadcaster,
    ):
        await analyzer._broadcast_event(event)

    assert broadcaster.broadcast_event.await_args.args[0] == {
        "type": "event",
        "data": {
            "id": 10,
            "event_id": 10,
            "batch_id": "b-10",
            "camera_id": "cam",
            "risk_score": 70,
            "risk_level": "high",
            "summary": "summ",
            "reasoning": "reaso",
            "started_at": "2025-12-23T14:30:00",
        },
    }

    # Second drive: started_at is None -> shipped emits the key with value None.
    broadcaster.broadcast_event.reset_mock()
    no_start = Event(
        id=11,
        batch_id="b-11",
        camera_id="cam",
        started_at=None,
        risk_score=30,
        risk_level="low",
        summary="s",
        reasoning="r",
    )
    with patch(
        "backend.services.event_broadcaster.get_broadcaster",
        autospec=True,
        return_value=broadcaster,
    ):
        await analyzer._broadcast_event(no_start)

    broadcaster.broadcast_event.assert_awaited_once()
    payload = broadcaster.broadcast_event.await_args.args[0]["data"]
    assert payload["started_at"] is None
    assert "started_at" in payload


@pytest.mark.asyncio
async def test_broadcast_passes_redis_to_broadcaster_and_logs_success(analyzer, logbox):
    """Kills ..._broadcast_event__mutmut_39, _41.

    Shipped L4518 hands the analyzer's own Redis client to
    ``get_broadcaster`` (probe: ``call(<MagicMock spec='RedisClient'>)`` — the
    very object in ``analyzer._redis``) and then logs
    "Broadcasted event {event.id} via WebSocket" at DEBUG (L4520). The repo test
    injects get_broadcaster with ``new=AsyncMock(...)`` and never inspects the
    argument.
    """
    event = Event(
        id=12,
        batch_id="b-12",
        camera_id="cam",
        started_at=datetime(2025, 12, 23, 14, 30, 0),
        risk_score=40,
        risk_level="medium",
        summary="s",
        reasoning="r",
    )
    broadcaster = MagicMock()
    broadcaster.broadcast_event = AsyncMock()
    with patch(
        "backend.services.event_broadcaster.get_broadcaster",
        autospec=True,
        return_value=broadcaster,
    ) as get_broadcaster:
        await analyzer._broadcast_event(event)

    assert get_broadcaster.await_args.args == (analyzer._redis,)
    assert logbox.messages == ["Broadcasted event 12 via WebSocket"]
    assert logbox.only().levelno == logging.DEBUG


# -------------------------------------------------------------------------- _get_existing_event


@pytest.mark.asyncio
async def test_get_existing_event_selects_events_by_id_equality(analyzer, logbox):
    """Kills ..._get_existing_event__mutmut_2, _3, _4, _5.

    Shipped L1589-1591 executes exactly
    ``select(Event).where(Event.id == event_id)`` in one session and returns
    ``scalar_one_or_none()``. The oracle statement is rebuilt in the test from
    the same SQLAlchemy expression the shipped line uses, so a
    ``execute(None)`` / ``where(None)`` / ``select(None)`` / ``!=`` mutant
    cannot produce it, and the sentinel return pins the passthrough.
    """
    event_id = 4242
    expected = str(select(Event).where(Event.id == event_id))
    sentinel = Event(
        id=event_id,
        batch_id="b-4242",
        camera_id="cam",
        started_at=datetime(2025, 12, 23, 14, 30, 0),
        risk_score=50,
        risk_level="medium",
        summary="s",
        reasoning="r",
    )
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = sentinel
    session.execute = AsyncMock(return_value=exec_result)

    with patch("backend.services.nemotron_analyzer.get_session", autospec=True) as get_session:
        get_session.return_value = session
        result = await analyzer._get_existing_event(event_id)

    assert result is sentinel
    assert get_session.call_count == 1
    assert session.execute.await_count == 1
    statement = session.execute.await_args.args[0]
    assert str(statement) == expected
    assert session.execute.await_args.kwargs == {}
