"""Batch-25 part 25 — chunk "tail:NemotronAnalyzer._trigger_event_created_webhook+5more#chunk1" (97 keys).

Six shipped functions are adjudicated here (backend/services/nemotron_analyzer.py):

  _trigger_event_created_webhook  L4525-4561   38 keys (1-35, 37, 38, 39)
  _get_recent_scene_changes       L1653-1694   21 keys (1-21)
  _get_household_context          L1854-1929   17 keys (3, 11, 20-27, 29-32, 34, 35, 39)
  health_check                    L3614-3634   13 keys (2, 9-21)
  execute_rollout_rollback        L1305-1322    7 keys (2, 3, 6-10)
  is_cold                         L1380-1393    1 key  (5)

Every key in this chunk is its OWN one-member shape group in
/tmp/wp-batch25/feed.json (verified: no shape group covering a chunk key
carries a second key), so no occurrence twin has to be carried across tests
here.

KILL MECHANISM, per family — every observable below was taken from a PROBE OF
THE SHIPPED CODE (/tmp/wp-batch25/probes/ch25/probe.py), never from
expectation:

* webhook payload (keys 2-33): the (args, kwargs) handed to
  WebhookService.trigger_webhooks_for_event(db, event_type, event_data,
  event_id=...) (backend/services/webhook_service.py:486-492) is forwarded to
  every delivery (:545), so exact call-args equality sees the renamed
  ("XXevent_idXX") and re-cased ("EVENT_ID") payload keys, dropped payload
  entries, the `, -> ` argument removals (keys 7/8/9/10 drop db / event_type
  / payload / event_id wholesale), `db -> None`, the whole-payload `-> None`,
  and the started_at/ended_at guard flips: `if x` -> `if x and False` is a
  VALUE change on the timestamped drive, while `if x` -> `if x or True`
  crashes .isoformat() on the None-timestamped drive INSIDE the shipped try,
  where the swallowed AttributeError means "no trigger call + one WARNING" —
  an observable kill with no test-visible exception.
* log-call shapes (webhook 34-39, scene 14-21 — all six sit on the DEBUG call
  inside the try, killed by the shape drive — health 9-21): `logger.warning`
  writes `msg` and every `extra=` key straight into the LogRecord, so
  `record.getMessage()` equality kills the -> None / lower / upper / XX
  message shapes and a curated `extra` view (ContextFilter injects
  request_id/trace_id/hostname/... into every record, so the raw __dict__
  cannot be compared whole) kills `extra -> None`, the `extra=` removals, the
  key renames and `str(e) -> str(None)`. `exc_info` is asserted as shipped
  (True -> a real (type, value, tb) triple for health_check; absent/None for
  the two sites that do not pass it). Message-argument REMOVALS (scene 16)
  raise TypeError at the log call, which at that site sits INSIDE the try and
  therefore shows up as "returns [] instead of the rows".
* SQLAlchemy statement (scene 1-13): the statement is the single positional
  argument of session.execute, so a postgresql-dialect compile with
  literal_binds pins the FROM entity, both WHERE clauses, the ORDER BY and
  the LIMIT. Every mutant render was PROBED distinct from shipped:
  `where(None)` renders "... AND NULL" / "WHERE NULL AND" (keys 5, 6 —
  `col = NULL` is UNKNOWN and matches NO rows, where shipped's
  `acknowledged = false` matches exactly the unacknowledged ones, so the
  shape is semantically wrong as well as textually), `select(None)` renders
  "SELECT NULL AS anon_1", `.limit(None)` drops the LIMIT clause,
  `.order_by(None)` drops ORDER BY, `== False` -> "= false" vs `!= False` ->
  "!= false" vs `== True` -> "= true", `limit(5)` -> `limit(6)` renders
  "LIMIT 6"; the return-value assertions separately kill keys 1, 12, 13
  (`result = None` / `scene_changes = None` / `list(None)` raising TypeError
  into the shipped except arm, which returns []).
* household detections (keys 11, 20-27, 29-31): the SimpleNamespace fields
  flow into format_household_context_by_detection
  (backend/services/prompts.py:3346-3432) which renders
  "- Detection #{id} ({object_type}, {zone}, {time}): {match}" applying
  `or "unknown"` to ZONE ONLY — object_type is interpolated raw, so an
  object_type of None renders the STRING "None" in the line. Exact line
  equality therefore sees the -> None shape (11), the `get(None, "unknown")`
  and key-rename shapes (20, 24, 25 — detection #11 loses "person"), the
  missing-default shapes `get(..., None)` / `get("unknown")` /
  `get("object_type", )` (21, 22, 23 — detection #12 renders "(None, "
  instead of "(unknown, "), the "XXunknownXX"/"UNKNOWN" default rewrites
  (26, 27) and the detected_at key-rename shapes (29, 30, 31 — detection #11
  falls through to `or datetime.now(UTC)` and loses its pinned 07:08:09).
* clock operand (key 32): `datetime.now(UTC) -> datetime.now(None)` at L1917
  is the detected_at FALLBACK that ships INTO a detection and that the
  renderer prints with strftime("%H:%M:%S"), so the test pins the shipped
  tz-awareness (`tzinfo is UTC`) directly. The drive pins TZ=Asia/Kolkata
  (UTC+5:30) via time.tzset so a naive now() is 5h30m off the UTC instant on
  any host (this sandbox is EDT4, so the shift exists even unpinned).
* health_check URL (key 2): `self._health_http_client.get` call-args equality
  pinned to the shipped render `('<llm_url>/health', headers=<auth headers>)`,
  with a non-200 drive proving the status operand is untouched. Keys 9-21 sit
  in the `except` arm, whose only observables are the WARNING record and
  `return False`.
* rollback labels (keys 2, 3, 6-9): `from backend.core.metrics import
  record_prompt_rollback` (L1314) resolves the ATTRIBUTE at call time, so
  patching backend.core.metrics.record_prompt_rollback (autospec) sees the
  exact positional pair ("nemotron", "ab_rollout_failure") that
  sanitize_metric_label would otherwise launder into the PROMPT_ROLLBACKS_TOTAL
  labels (backend/core/metrics.py:3967-3976); manager.stop() is asserted so a
  mutant is known to have executed. Key 10 is the two-fragment f-string ->
  None shape: the shipped record is "A/B rollout experiment stopped: exp-42"
  with NO space at the fragment boundary, pinned verbatim.
* is_cold boundary (key 5): `>` -> `>=` is only observable at the exact
  boundary, which is reachable because time.monotonic() has 1ns resolution
  here. patch("time.monotonic", autospec=True) side_effect [400.0, 250.0]
  against _last_inference_time=100.0 / _cold_start_threshold=300.0: shipped
  `300.0 > 300.0` is False and `150.0 > 300.0` is False; the `>=` mutant's
  first answer is True.

EQUIVALENCE (4 keys, all in _get_household_context; each proof re-verified
against the instrumented variant bodies in
/tmp/wp-batch25/instrumented-nemotron_analyzer.py, and all four SURVIVE the
in-memory red-check run of this file):

* key 3  `if enrichment_result is None:` -> `is not None:` (L1896): the
  guarded body is literally only `pass` (L1897-1898 — verified inside variant
  xǁNemotronAnalyzerǁ_get_household_context__mutmut_3) and the match-dict
  reads live under the SEPARATE unconditional guard `if enrichment_result:`
  at L1904, so flipping this guard changes no value, no control flow and no
  exception (literal no-op).
* keys 34/35 at L1923 (`current_time = None` and
  `datetime.now(UTC) -> datetime.now(None)`) and key 39 at L1928
  (`current_time=current_time,` -> `current_time=None,`): current_time's only
  consumer in the shipped code is the keyword argument of
  format_household_context_by_detection, whose signature declares
  `current_time: datetime,  # noqa: ARG001  # Reserved for future schedule
  display` (backend/services/prompts.py:3350) and whose 112-line body never
  references the name (grep over the body: the identifier occurs in the
  signature and the docstring only). The returned string — the shipped
  function's only return value — is therefore value-blind to current_time,
  and no exception or log is reachable from it (operand unreachable in the
  only consumer). The tests deliberately never assert the VALUE of that
  argument.

killed_by_draft: none. No repo test drives _trigger_event_created_webhook at
all (grep trigger_webhooks_for_event / EVENT_CREATED across
backend/tests/unit/services/test_nemotron_*.py: zero hits — the analyze_batch
tests that reach the call site mock the webhook service away); no repo test
asserts the statement _get_recent_scene_changes passes to session.execute
(the callers patch the method itself, test_nemotron_analyzer.py:2004, :2148,
:2285, :2501); the three health_check tests (test_nemotron_analyzer.py:197-229
and :2635) assert only `result is True/False`; test_execute_rollout_rollback_no_manager
(:4948) covers only the early return and test_prompt_ab_rollout_integration.py:466
only `manager.is_active is False`; the four repo _get_household_context tests
(:4602-4723) assert "HOUSEHOLD MATCHES BY DETECTION" / "Detection #N" /
"NO MATCH" / "KNOWN PERSON" substrings and `== ""`, none of which any key in
this chunk changes except key 3 (a no-op anyway); test_is_cold_* (:3704-3721)
never lands on the exact boundary (it uses -400s against a 300s threshold, a
fresh _track_inference, and the never-used early return), so key 5 stays
killable; the batch-25 draft battery
(/tmp/wp-batch25/test_nemotron_analyzer_batch25.py) only drives
_parse_llm_response / _validate_risk_data / _extract_json_objects.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_25.py -p no:cacheprovider -o addopts= -q
RED-CHECK (executed in-memory; the repo is never written):
    /agents/agent-veranda3/workspace/.venv/bin/python \
        /tmp/wp-batch25/probes/ch25/redcheck.py
    — per key, /tmp/wp-batch25/probes/ch25/red_plugin.py swaps the
    reconstructed variant (read-only oracle over the instrumented copy) into
    NemotronAnalyzer, mirroring mutmut's globals semantics. All 93 killable
    keys turn RED; the 4 equivalent keys above SURVIVE.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py does
# NOT apply. Mirror the minimum env vars that conftest sets BEFORE any backend
# import (values copied verbatim from backend/tests/conftest.py +
# backend/tests/unit/conftest.py, not invented).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

from sqlalchemy.dialects import postgresql

import backend.core.metrics as METRICS
from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.services.nemotron_analyzer import NemotronAnalyzer

NS = "backend.services.nemotron_analyzer"
LOGGER = logging.getLogger(NS)

# --------------------------------------------------------------------------- #
# shipped literals, copied from the source lines each mutant rewrites
# --------------------------------------------------------------------------- #
WEBHOOK_MSG = "Failed to trigger EVENT_CREATED webhooks: kaboom-webhook"
SCENE_MSG = "Found 3 unacknowledged scene changes for camera cam-9"
SCENE_FAIL_MSG = "Failed to query scene changes, continuing without camera health context"
HEALTH_MSG = "LLM health check failed"
ROLLBACK_MSG = "A/B rollout experiment stopped: exp-42"
LLM_URL = "http://nemotron.test:8091"

# The webhook payload AS SHIPPED (probe output for the event built below).
WEBHOOK_PAYLOAD = {
    "event_id": 7,
    "batch_id": "batch-7",
    "camera_id": "cam-A",
    "risk_score": 88,
    "risk_level": "high",
    "summary": "a person at the front door",
    "started_at": "2026-01-02T03:04:05+00:00",
    "ended_at": "2026-01-02T03:10:11+00:00",
    "is_fast_path": True,
}
# Same payload with the two optional timestamps absent (they render as None).
WEBHOOK_PAYLOAD_NO_TIMES = {**WEBHOOK_PAYLOAD, "started_at": None, "ended_at": None}

# The shipped statement, rendered through the postgresql dialect with literal
# binds (verified render, probe ch25/probe.py).
SCENE_SQL = (
    "SELECT scene_changes.id, scene_changes.camera_id, scene_changes.detected_at, "
    "scene_changes.change_type, scene_changes.similarity_score, "
    "scene_changes.acknowledged, scene_changes.acknowledged_at, "
    "scene_changes.file_path FROM scene_changes "
    "WHERE scene_changes.camera_id = 'cam-9' AND scene_changes.acknowledged = false "
    "ORDER BY scene_changes.detected_at DESC LIMIT 5"
)

# Curated view of a LogRecord's `extra=` payload: ONLY the keys this chunk
# mutates. backend/core/logging.py ContextFilter injects request_id /
# correlation_id / trace_id / span_id / connection_id / task_id / job_id /
# hostname / container_id / app_version / environment into every record, so
# the raw record __dict__ cannot be compared whole.
CURATED = ("event_id", "camera_id", "count", "error")


def _analyzer() -> NemotronAnalyzer:
    # __new__ skips the heavy __init__ (redis, http clients, settings); every
    # function in this chunk reads only the instance attributes the driving
    # test sets explicitly.
    return NemotronAnalyzer.__new__(NemotronAnalyzer)


def _curated(record: logging.LogRecord) -> dict:
    return {k: getattr(record, k) for k in CURATED if hasattr(record, k)}


@contextmanager
def collected_logs():
    """Collect EVERY record emitted on the analyzer logger, at any level."""
    records: list[logging.LogRecord] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Collect()
    previous_level = LOGGER.level
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        LOGGER.removeHandler(handler)
        LOGGER.setLevel(previous_level)


def _event(**overrides) -> SimpleNamespace:
    """Event-shaped namespace: Event is a SQLAlchemy declarative model whose
    instrumented attributes refuse assignment on a bare __new__ instance, and
    the shipped function only ever reads these ten attributes."""
    event = SimpleNamespace(
        deleted_at=None,
        id=7,
        batch_id="batch-7",
        camera_id="cam-A",
        risk_score=88,
        risk_level="high",
        summary="a person at the front door",
        started_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        ended_at=datetime(2026, 1, 2, 3, 10, 11, tzinfo=UTC),
        is_fast_path=True,
    )
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


def _drive_trigger(event, trigger_side_effect=None):
    """Run _trigger_event_created_webhook against a spied webhook service.

    Returns (method_return_value, trigger_webhooks_for_event_mock); the mock
    is None when get_webhook_service was never reached. Under mutant 2
    (`webhook_service = None`) the attribute access raises AttributeError,
    the shipped except arm swallows it, and the drive then fails the
    "exactly one WARNING record" / call-count assertions instead.
    """
    service = MagicMock(name="webhook_service")
    service.trigger_webhooks_for_event = AsyncMock(
        return_value=["DELIVERY"], side_effect=trigger_side_effect
    )
    session_ctx = AsyncMock()
    session_ctx.__aenter__.return_value = "DB-SENTINEL"
    session_ctx.__aexit__.return_value = None
    analyzer = _analyzer()
    with (
        patch(f"{NS}.get_webhook_service", autospec=True, return_value=service) as get_ws,
        patch(f"{NS}.get_session", autospec=True) as get_session,
    ):
        get_session.return_value = session_ctx
        result = asyncio.run(analyzer._trigger_event_created_webhook(event))
    return result, (None if get_ws.call_count == 0 else service.trigger_webhooks_for_event)


def _scene_session(rows=None, error=None):
    """AsyncSession stand-in whose execute() returns a Result-like object."""
    result = MagicMock(name="result")
    result.scalars.return_value.all.return_value = rows
    session = MagicMock(name="session")
    session.execute = AsyncMock(return_value=result, side_effect=error)
    return session


def _sql(statement) -> str:
    rendered = statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    return " ".join(str(rendered).split())


# =========================================================================== #
# 1. _trigger_event_created_webhook — 38 keys
# =========================================================================== #


def test_trigger_webhook_payload_is_pinned_exactly():
    """Kills xǁNemotronAnalyzerǁ_trigger_event_created_webhook keys 2, 3, 4,
    5, 6, 7, 8, 9, 10, 11-25, 27, 28, 29, 31, 32, 33.

    Pins the shipped trigger_webhooks_for_event call (nemotron_analyzer.py:
    4539-4557) as an exact (args, kwargs) pair against the SHIPPED render
    probed from the shipped code. That single equality sees:
      - 2  `webhook_service = get_webhook_service()` -> None (AttributeError
         on `.trigger_webhooks_for_event`, swallowed into a WARNING with zero
         calls)
      - 3  db -> None and 4 WebhookEventType.EVENT_CREATED -> None (args)
      - 5  the whole payload dict -> None
      - 6  event_id=str(event.id) -> event_id=None, and 10 the removal of the
         `event_id=` keyword (kwargs equality -> {})
      - 7  db removal / 8 event_type removal / 9 payload removal (arity plus
         positional shift)
      - 11-24 every "XXkeyXX"/"KEY" rename of the nine payload keys
      - 25/29 `if event.started_at`/`if event.ended_at` -> `(x) and False`
         (payload value None where shipped renders the isoformat)
      - 31/32/33 event_id=str(event.id) -> str(None) == "None"
    The success path logs nothing — pinned, because several of these shapes
    are only distinguishable from a swallowed crash by the ABSENCE of a
    record.
    """
    with collected_logs() as records:
        result, trigger = _drive_trigger(_event())

    assert result is None
    assert trigger is not None and trigger.call_count == 1
    args, kwargs = trigger.call_args
    assert args[0] == "DB-SENTINEL"
    assert args[1] is WebhookEventType.EVENT_CREATED
    assert args[2] == WEBHOOK_PAYLOAD
    assert kwargs == {"event_id": "7"}
    assert records == []


def test_trigger_webhook_skips_soft_deleted_event():
    """Kills xǁNemotronAnalyzerǁ_trigger_event_created_webhook key 1.

    `if event.deleted_at is not None:` -> `if event.deleted_at is None:`
    (nemotron_analyzer.py:4534) inverts the soft-delete guard. Shipped: a
    deleted event reaches neither get_webhook_service nor get_session and
    returns None with zero log records; the mutant instead drives a
    soft-deleted event into the try and calls the webhook service for it. The
    second half (undeleted -> MUST trigger) bounds the guard so the first
    half cannot pass with the guard removed altogether.
    """
    deleted = _event(deleted_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    with collected_logs() as records:
        result, trigger = _drive_trigger(deleted)
    assert result is None
    assert trigger is None  # get_webhook_service was never reached
    assert records == []

    result2, trigger2 = _drive_trigger(_event())
    assert result2 is None
    assert trigger2 is not None and trigger2.call_count == 1


def test_trigger_webhook_payload_without_optional_timestamps():
    """Kills xǁNemotronAnalyzerǁ_trigger_event_created_webhook keys 26, 30.

    With started_at/ended_at = None shipped renders both payload entries as
    None. `if event.started_at else None` -> `if (event.started_at) or True
    else None` (nemotron_analyzer.py:4552/4553) then calls .isoformat() on
    None, raising AttributeError *inside* the shipped try — the except arm
    swallows it into a WARNING and the trigger call never happens, so the
    mutant is killed by the missing call plus the unexpected record, not by a
    visible exception. (The `and False` twins 25/29 are value-differences and
    stay on the timestamped drive above.)
    """
    with collected_logs() as records:
        result, trigger = _drive_trigger(_event(started_at=None, ended_at=None))
    assert result is None
    assert trigger is not None and trigger.call_count == 1
    args, kwargs = trigger.call_args
    assert args[2] == WEBHOOK_PAYLOAD_NO_TIMES
    assert kwargs == {"event_id": "7"}
    assert records == []


def test_trigger_webhook_failure_log_is_pinned():
    """Kills xǁNemotronAnalyzerǁ_trigger_event_created_webhook keys 34, 35,
    37, 38, 39.

    The except arm (nemotron_analyzer.py:4558-4561) swallows the failure and
    returns None, so the single WARNING record is the only observable — and
    the shipped record carries the interpolated message plus
    extra={"event_id": event.id}:
      - 34 msg -> None                   -> record message becomes "None"
      - 35 extra=None                    -> curated extra is {}
      - 37 removal of the `extra=` kwarg -> curated extra is {}
      - 38/39 "event_id" -> "XXevent_idXX" / "EVENT_ID" -> curated extra {}
    exc_info is asserted ABSENT, as shipped at this site (the call passes no
    exc_info), which also catches any shape smuggling one in.
    """
    failure = RuntimeError("kaboom-webhook")
    with collected_logs() as records:
        result, trigger = _drive_trigger(_event(), trigger_side_effect=failure)

    assert result is None  # webhook failures never fail event creation
    assert trigger is not None and trigger.call_count == 1
    assert [r.levelno for r in records] == [logging.WARNING]
    record = records[0]
    assert record.getMessage() == WEBHOOK_MSG
    assert _curated(record) == {"event_id": 7}
    assert record.exc_info is None


# =========================================================================== #
# 2. _get_recent_scene_changes — 21 keys
# =========================================================================== #


@pytest.mark.asyncio
async def test_scene_query_shape_is_pinned():
    """Kills xǁNemotronAnalyzerǁ_get_recent_scene_changes keys 1-21 (all 21).

    session.execute receives ONE positional argument — the statement — so
    compiling it through the postgresql dialect with literal binds pins the
    entity, both WHERE clauses, the ORDER BY and the LIMIT (shipped render
    probed from the shipped code; every mutant render probed DISTINCT):
      - 1  result = None                 -> AttributeError on None.scalars ->
         except arm returns [] (return-value assert)
      - 2  statement -> None             -> None has no .compile / no rows
      - 3  `.limit(5)` -> `.limit(None)` -> LIMIT clause disappears
      - 4  `.order_by(...)` -> `.order_by(None)` -> ORDER BY disappears
      - 5  ack `.where(...) -> .where(None)`   -> renders "... AND NULL"
      - 6  camera `.where(...) -> .where(None)` -> renders "WHERE NULL AND"
      - 7  `select(SceneChange)` -> `select(None)` -> "SELECT NULL AS anon_1"
      - 8  `== camera_id` -> `!= camera_id`     -> "= 'cam-9'" vs "!= 'cam-9'"
      - 10 `== False` -> `== True`              -> "= false" vs "= true"
      - 11 `.limit(5)` -> `.limit(6)`           -> "LIMIT 6"
      - 12 scene_changes = None                 -> returns None, logs nothing
      - 13 list(None) -> TypeError              -> except arm returns []
    The DEBUG record is part of the contract (it is the only trace a populated
    query leaves), and ALL SIX of its shapes 14-21 sit on that call inside the
    try: 14 rewrites the message to None, 16 removes the message argument
    (TypeError raised inside the try -> returns [] instead of the rows), 15
    rewrites extra={...} to extra=None, 17 removes the extra= kwarg and
    18-21 rename "camera_id"/"count" inside extra — so message plus
    curated-extra equality kills every one of them. (The except arm's own
    extra={"camera_id", "error"} is a different shape and carries no key in
    this chunk; its drive lives in
    test_scene_query_failure_returns_empty_list_and_logs.)
    """
    session = _scene_session(rows=["SC-1", "SC-2", "SC-3"])
    with collected_logs() as records:
        result = await _analyzer()._get_recent_scene_changes("cam-9", session)

    assert result == ["SC-1", "SC-2", "SC-3"]
    statement = session.execute.call_args.args[0]
    assert _sql(statement) == SCENE_SQL
    assert session.execute.call_args.kwargs == {}
    assert [r.levelno for r in records] == [logging.DEBUG]
    assert records[0].getMessage() == SCENE_MSG
    assert _curated(records[0]) == {"camera_id": "cam-9", "count": 3}


@pytest.mark.asyncio
async def test_scene_query_uses_equality_on_acknowledged_column():
    """Kills xǁNemotronAnalyzerǁ_get_recent_scene_changes key 9.

    `.where(SceneChange.acknowledged == False) -> .where(... != False)`
    (L1686) renders "acknowledged != false", i.e. it would pull the
    ALREADY-acknowledged changes into the prompt — the opposite of the
    documented contract ("unacknowledged scene changes", docstring L1666).
    The zero-rows drive keeps the statement observable without log noise.
    """
    session = _scene_session(rows=[])
    await _analyzer()._get_recent_scene_changes("cam-9", session)
    rendered = _sql(session.execute.call_args.args[0])
    assert "scene_changes.acknowledged != false" not in rendered
    assert "scene_changes.acknowledged = false" in rendered
    assert "AND NULL" not in rendered and "WHERE NULL" not in rendered


@pytest.mark.asyncio
async def test_scene_query_empty_result_returns_empty_list():
    """Support drive for the `if scene_changes:` gate at L1689 and for the
    return-value arms of keys 1/12/13. No key claimed: with zero rows shipped
    logs nothing, and this drive proves the populated-path assertions of
    test_scene_query_shape_is_pinned describe the populated path rather than
    a stub that returns whatever execute handed back.
    """
    session = _scene_session(rows=[])
    with collected_logs() as records:
        result = await _analyzer()._get_recent_scene_changes("cam-9", session)
    assert result == []
    assert records == []


@pytest.mark.asyncio
async def test_scene_query_failure_returns_empty_list_and_logs():
    """Support drive for the except arm (L1691-1694). No key claimed: every
    key on the log calls in this function (14-21) sits on the DEBUG call
    inside the try, and no chunk key rewrites the except arm's
    extra={"camera_id", "error"} or its message. The drive still pins the
    shipped contract (error swallowed, [] returned, one WARNING) and re-kills
    key 1 incidentally — under `result = None` the recorded error string
    becomes "NoneType object has no attribute 'scalars'" instead of the
    session's own RuntimeError, which is a bound on WHERE key 1's exception
    lands. The key-1 claim lives with test_scene_query_shape_is_pinned.
    """
    session = _scene_session(error=RuntimeError("db down"))
    with collected_logs() as records:
        result = await _analyzer()._get_recent_scene_changes("cam-9", session)

    assert result == []
    assert [r.levelno for r in records] == [logging.WARNING]
    assert records[0].getMessage() == SCENE_FAIL_MSG
    assert _curated(records[0]) == {"camera_id": "cam-9", "error": "db down"}


# =========================================================================== #
# 3. _get_household_context — 17 keys
# =========================================================================== #

HOUSEHOLD_HEADER = "HOUSEHOLD MATCHES BY DETECTION:"
DETECTED_AT = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)


def _household_detections():
    return [
        {"id": "11", "object_type": "person", "detected_at": DETECTED_AT},
        {"id": "12"},
    ]


def _enrichment(person_matches=None, vehicle_matches=None):
    # None -> fresh empty dict; otherwise the CALLER'S object (identity is
    # preserved so the shipped `person_matches = enrichment_result...`
    # forwarding at L1905-1906 is assertable by identity).
    return SimpleNamespace(
        person_household_matches={} if person_matches is None else person_matches,
        vehicle_household_matches={} if vehicle_matches is None else vehicle_matches,
    )


@pytest.mark.asyncio
async def test_household_context_renders_detection_defaults():
    """Kills xǁNemotronAnalyzerǁ_get_household_context keys 11, 20, 21, 22,
    23, 24, 25, 26, 27, 29, 30, 31.

    The shipped function builds SimpleNamespace detections from the raw dicts
    (L1913-1920) and format_household_context_by_detection renders
    "- Detection #{id} ({object_type}, {zone}, {time}): ..." with `or
    "unknown"` applied to ZONE ONLY, so exact line equality sees every
    get()/default shape:
      - 11 object_type=None -> "#11 (None, ..." — the detection that HAS
        object_type "person" renders the string "None"
      - 20 `get("object_type", ...)` -> `get(None, ...)` -> miss -> the
        default renders where shipped renders "person" for #11
      - 21 `get("object_type", None)` / 22 `get("unknown")` / 23
        `get("object_type", )` (an empty second argument is the ONE-argument
        call, whose default is None) -> #12 renders "(None, ..." instead of
        "(unknown, ..."
      - 24/25 "object_type" -> "XXobject_typeXX"/"OBJECT_TYPE" -> #11 misses
        and renders the default instead of "person"
      - 26/27 the default "unknown" -> "XXunknownXX"/"UNKNOWN" -> #12 renders
        the rewritten default
      - 29/30/31 `get("detected_at")` -> `get(None)` / "XXdetected_atXX" /
        "DETECTED_AT" -> miss -> `or datetime.now(UTC)` -> #11 loses its
        pinned 07:08:09 and shows the wall clock instead
    """
    # Precondition for keys 29/30/31: their mutant value is
    # datetime.now(UTC) rendered to the second, so the pinned 07:08:09 stays a
    # discriminator only while the wall clock is not exactly at it. Asserted
    # rather than assumed (one second in 86 400 would otherwise read as a
    # survivor instead of a kill).
    assert datetime.now(UTC).strftime("%H:%M:%S") != "07:08:09"

    result = await _analyzer()._get_household_context(_household_detections(), None)
    lines = result.split("\n")
    assert lines[0] == HOUSEHOLD_HEADER
    assert lines[1] == "- Detection #11 (person, unknown, 07:08:09): NO MATCH"
    # detection #12 falls back to the shipped UTC clock; only its shape is
    # pinned here (the naive-now question is pinned under a TZ pin below).
    assert lines[2].startswith("- Detection #12 (unknown, unknown, ")
    assert lines[2].endswith("): NO MATCH")


@pytest.mark.asyncio
async def test_household_context_uses_enrichment_matches():
    """Support drive for the enrichment plumbing at L1904-1906. No key
    claimed: the key-3 guard at L1896 is a proven no-op (its body is only
    `pass`) and no other chunk key sits on the match-dict reads. The drive
    exists so the renderer whose lines are pinned above is shown to produce
    match-attributed output for the SAME two detections — bounding that the
    default/None shapes above change the rendered (obj_type, time) tuple
    rather than merely the presence of the line.
    """
    from backend.services.household_matcher import HouseholdMatch

    person_match = HouseholdMatch(
        member_id=1,
        member_name="Mike",
        similarity=0.92,
        match_type="person",
        member_role="resident",
    )
    enrichment = _enrichment(person_matches={11: person_match})
    result = await _analyzer()._get_household_context(_household_detections(), enrichment)
    detection_11 = next(line for line in result.split("\n") if "Detection #11" in line)
    assert detection_11.startswith("- Detection #11 (person, unknown, 07:08:09): ")
    assert 'KNOWN PERSON "Mike"' in detection_11

    result_none = await _analyzer()._get_household_context(_household_detections(), None)
    detection_11_none = next(line for line in result_none.split("\n") if "Detection #11" in line)
    assert "NO MATCH" in detection_11_none


@pytest.mark.asyncio
async def test_household_context_forwards_detections_and_match_dicts():
    """Support drive for the call contract at L1924-1928. No key claimed —
    the only key on this call site (39, `current_time=None,`) is value-blind
    to the shipped consumer, see the module docstring — but the autospec spy
    pins that the shipped call passes exactly four keyword arguments in
    shipped order, with int-cast detection ids, zone_name None, the supplied
    detected_at VALUE and the enrichment match dicts BY IDENTITY, so the
    rendered-line assertions above are known to describe objects built here.
    """
    person_matches = {11: "PERSON-MATCH"}
    vehicle_matches: dict = {}
    enrichment = _enrichment(person_matches=person_matches, vehicle_matches=vehicle_matches)
    with patch(f"{NS}.format_household_context_by_detection", autospec=True) as fmt:
        fmt.return_value = "SPY-OUT"
        result = await _analyzer()._get_household_context(_household_detections(), enrichment)

    assert result == "SPY-OUT"
    assert fmt.call_count == 1
    assert fmt.call_args.args == ()
    assert list(fmt.call_args.kwargs) == [
        "detections",
        "person_matches",
        "vehicle_matches",
        "current_time",
    ]
    kwargs = fmt.call_args.kwargs
    assert [(d.id, d.zone_name) for d in kwargs["detections"]] == [(11, None), (12, None)]
    assert kwargs["detections"][0].detected_at == DETECTED_AT
    assert kwargs["person_matches"] is person_matches
    assert kwargs["vehicle_matches"] is vehicle_matches


@pytest.mark.asyncio
async def test_household_context_detected_at_fallback_is_utc_aware():
    """Kills xǁNemotronAnalyzerǁ_get_household_context key 32.

    `detected_at=det_data.get("detected_at") or datetime.now(UTC)` ->
    `... or datetime.now(None)` (L1917) stamps a NAIVE local datetime into
    the detection that the renderer prints with strftime("%H:%M:%S"). The
    drive pins TZ=Asia/Kolkata (UTC+5:30) for its duration, so a naive now()
    is 5h30m away from the UTC instant on any host, and shipped's fallback is
    pinned tz-aware UTC directly. The second half runs the REAL renderer: a
    detection carrying its own UTC stamp must print exactly its UTC seconds.
    (Keys 34/35/39 sit on current_time, which the shipped consumer never
    reads — deliberately not asserted on.)
    """
    previous_tz = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Kolkata"
    time.tzset()
    try:
        with patch(f"{NS}.format_household_context_by_detection", autospec=True) as fmt:
            fmt.return_value = "SPY-OUT"
            await _analyzer()._get_household_context([{"id": "12"}], _enrichment())
        fallback = fmt.call_args.kwargs["detections"][0].detected_at
        assert fallback.tzinfo is UTC, "shipped detected_at fallback is tz-aware UTC"

        result = await _analyzer()._get_household_context(
            [
                {
                    "id": "5",
                    "object_type": "car",
                    "detected_at": datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC),
                }
            ],
            _enrichment(),
        )
        assert "- Detection #5 (car, unknown, 05:06:07): NO MATCH" in result
    finally:
        if previous_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous_tz
        time.tzset()


@pytest.mark.asyncio
async def test_household_context_without_detections_returns_empty_string():
    """Support drive for the early exit at L1894 (`if not detections_data:
    return ""`). No key claimed — nothing in this chunk mutates that line —
    but it is the boundary that makes the rendered-line assertions above the
    whole behavior of every remaining body line.
    """
    with patch(f"{NS}.format_household_context_by_detection", autospec=True) as fmt:
        result = await _analyzer()._get_household_context([], _enrichment())
    assert result == ""
    assert fmt.call_count == 0


# =========================================================================== #
# 4. health_check — 13 keys
# =========================================================================== #


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _health_analyzer(get_mock) -> NemotronAnalyzer:
    analyzer = _analyzer()
    analyzer._health_http_client = MagicMock(name="health_client")
    analyzer._health_http_client.get = get_mock
    analyzer._llm_url = LLM_URL
    analyzer._get_auth_headers = lambda: {"authorization": "Bearer test"}
    return analyzer


@pytest.mark.asyncio
async def test_health_check_success_requests_the_health_url():
    """Kills xǁNemotronAnalyzerǁhealth_check key 2.

    `f"{self._llm_url}/health",` -> `None,` at L3622-3624 changes the
    positional URL argument of self._health_http_client.get, pinned by exact
    call-args equality against the shipped render. The 404 drive re-proves
    the status-comparison operand is untouched, so the kill cannot be claimed
    from a mutant that skipped the request but still returned True.
    """
    get_mock = AsyncMock(return_value=_Response(200))
    analyzer = _health_analyzer(get_mock)
    with collected_logs() as records:
        assert await analyzer.health_check() is True
    assert get_mock.call_args.args == (f"{LLM_URL}/health",)
    assert get_mock.call_args.kwargs == {"headers": {"authorization": "Bearer test"}}
    assert records == []

    get_404 = AsyncMock(return_value=_Response(404))
    analyzer404 = _health_analyzer(get_404)
    with collected_logs():
        assert await analyzer404.health_check() is False


@pytest.mark.asyncio
async def test_health_check_failure_log_is_pinned():
    """Kills xǁNemotronAnalyzerǁhealth_check keys 9, 10, 11, 13, 14, 15, 16,
    17, 18, 19, 21.

    The except arm (L3629-3634) returns False, so the WARNING record is the
    only observable of these shapes:
      - 9  msg -> None, and 15/16/17 the XX/lower/upper message rewrites
      - 10 extra=None, 13 removal of the `extra=` kwarg, 18/19 "error" ->
        "XXerrorXX"/"ERROR"
      - 11 `exc_info=True` -> None, 21 -> False and 14 removal of the
        `exc_info=` kwarg: shipped passes True inside an active except, so
        record.exc_info is the live (type, value, tb) triple; all three
        mutants leave record.exc_info None.
    """
    get_mock = AsyncMock(side_effect=RuntimeError("conn refused"))
    analyzer = _health_analyzer(get_mock)
    with collected_logs() as records:
        assert await analyzer.health_check() is False

    assert [r.levelno for r in records] == [logging.WARNING]
    record = records[0]
    assert record.getMessage() == HEALTH_MSG
    assert _curated(record) == {"error": "conn refused"}
    assert isinstance(record.exc_info, tuple)
    assert record.exc_info[0] is RuntimeError


@pytest.mark.asyncio
async def test_health_check_failure_log_error_string_is_from_the_exception():
    """Kills xǁNemotronAnalyzerǁhealth_check key 20.

    `extra={"error": str(e)},` -> `extra={"error": str(None)},` (L3632) makes
    every failure log the literal string "None". Driven with a parameterless
    RuntimeError, whose shipped str() is the empty string, so shipped and
    mutant differ on exactly the operand the key rewrites.
    """
    get_mock = AsyncMock(side_effect=RuntimeError())
    analyzer = _health_analyzer(get_mock)
    with collected_logs() as records:
        assert await analyzer.health_check() is False
    assert _curated(records[0]) == {"error": ""}


# =========================================================================== #
# 5. execute_rollout_rollback — 7 keys
# =========================================================================== #


def _rollout_manager():
    manager = MagicMock(name="rollout_manager")
    manager.rollout_config.experiment_name = "exp-42"
    return manager


def test_execute_rollout_rollback_records_and_logs_as_shipped():
    """Kills xǁNemotronAnalyzerǁexecute_rollout_rollback keys 2, 3, 6, 7, 8,
    9, 10.

    record_prompt_rollback is imported from backend.core.metrics INSIDE the
    function (L1314), so patching the module attribute (autospec) observes the
    shipped positional pair ("nemotron", "ab_rollout_failure") verbatim,
    before sanitize_metric_label launders it into the PROMPT_ROLLBACKS_TOTAL
    labels. Keys 2/6/7 mutate the model label (None / "XXnemotronXX" /
    "NEMOTRON") and keys 3/8/9 the reason label (None /
    "XXab_rollout_failureXX" / "AB_ROLLOUT_FAILURE"). Key 10 replaces the
    two-fragment f-string of the WARNING with None: the shipped record is
    "A/B rollout experiment stopped: exp-42" with NO space at the fragment
    boundary, pinned verbatim. stop() is asserted first because every label
    mutant runs it before the record call — proving the mutant executed
    rather than the whole body having been skipped.
    """
    analyzer = _analyzer()
    manager = _rollout_manager()
    analyzer._rollout_manager = manager
    with (
        patch.object(METRICS, "record_prompt_rollback", autospec=True) as rollback,
        collected_logs() as records,
    ):
        analyzer.execute_rollout_rollback()

    assert manager.stop.call_count == 1
    assert [c.args for c in rollback.call_args_list] == [("nemotron", "ab_rollout_failure")]
    assert rollback.call_args_list[0].kwargs == {}
    assert [r.levelno for r in records] == [logging.WARNING]
    assert records[0].getMessage() == ROLLBACK_MSG


def test_execute_rollout_rollback_without_manager_is_silent():
    """Support drive for the guard at L1312 (`if self._rollout_manager is
    None: return`). No key claimed — nothing in this chunk mutates that line
    — but it bounds the drive above: the record/log assertions describe the
    manager-configured path only. (Repo precedent
    test_execute_rollout_rollback_no_manager asserts nothing at all.)
    """
    analyzer = _analyzer()
    analyzer._rollout_manager = None
    with (
        patch.object(METRICS, "record_prompt_rollback", autospec=True) as rollback,
        collected_logs() as records,
    ):
        analyzer.execute_rollout_rollback()
    assert rollback.call_count == 0
    assert records == []


# =========================================================================== #
# 6. is_cold — 1 key
# =========================================================================== #


def test_is_cold_uses_strict_greater_than_at_the_threshold():
    """Kills xǁNemotronAnalyzerǁis_cold key 5.

    `return seconds_since_last > self._cold_start_threshold` -> `>=` (L1393)
    is only observable at the exact boundary, and the boundary is reachable
    because time.monotonic() has 1ns resolution here: with
    _last_inference_time = 100.0 and _cold_start_threshold = 300.0 a patched
    monotonic returning 400.0 gives seconds_since_last == 300.0, where shipped
    answers False (not cold) and the `>=` mutant answers True. The second
    drive (250.0 -> 150.0s) must answer False under BOTH, so the kill cannot
    come from an inverted comparison or swapped operands.
    """
    analyzer = _analyzer()
    analyzer._last_inference_time = 100.0
    analyzer._cold_start_threshold = 300.0
    with patch("time.monotonic", autospec=True) as monotonic:
        monotonic.side_effect = [400.0, 250.0]
        at_threshold = analyzer.is_cold()
        well_within = analyzer.is_cold()

    assert at_threshold is False
    assert well_within is False
    assert monotonic.call_count == 2


def test_is_cold_is_true_when_never_used():
    """Support drive for the early return at L1391 and the reachability anchor
    for key 5: shipped returns True WITHOUT calling time.monotonic, so the
    patched-clock drive above is known to exercise the comparison line
    itself. No key claimed (the repo's
    test_is_cold_returns_true_when_never_used already asserts this).
    """
    analyzer = _analyzer()
    analyzer._last_inference_time = None
    analyzer._cold_start_threshold = 300.0
    with patch("time.monotonic", autospec=True) as monotonic:
        assert analyzer.is_cold() is True
    assert monotonic.call_count == 0
