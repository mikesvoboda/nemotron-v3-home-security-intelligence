# TARGET-MODULE: backend.services.job_history_service
"""Campaign #41 battery AQ — backend/services/job_history_service.py survivors.

Every test is an inventory pin: each assertion was chosen against a specific
mutmut family in /home/agent/runs/b41-inventory.txt (208 survivors, 8
families).  Style follows batteries AP/AO: strict recording doubles whose
signatures mirror the real collaborator (wrong/missing/None args raise
exactly where the real SQLAlchemy session or emitter would raise), call-list
spies, message EQUALITY over the full (level, args, kwargs) record — this
service passes its data through ``extra=`` kwargs, so the recorder captures
kwargs too and every key rename / value-swap / str(None) mutant dies on tuple
equality — and full-observable EQUALITY on constructed models and dataclasses
([[assertion-pinned-where-shipped-and-mutant-agree-fake-equiv]]).

Measured this session against the installed SQLAlchemy (this sandbox), the
kill-critical facts: ``.where(None)`` COMPILES to ``WHERE NULL`` (params
empty), ``select(None)`` to ``SELECT NULL AS anon_1``, ``order_by(None)``
DROPS the ORDER BY clause and ``limit(None)`` the LIMIT clause — so the
recorder pins the normalized statement STRING plus the compiled PARAMS dict
for every execute; the shipped level-filter rows land on
params ``level_1: ['info', 'warning', 'error']`` for INFO and
``['error']`` for ERROR while DEBUG/unknown levels carry NO filter clause at
all.  A None statement raises TypeError HERE, mirroring the real session's
"query expected" ArgumentError, so whole-statement-replacement mutants die at
the call instead of silently.

Honesty LEDGER — PREDICTED EQUIV by per-mutant reasoning this session; the
disposition sweep is the adjudicator and any prediction that turns out RED is
simply killed (the c41 ledger is authored FROM the sweep, never the reverse):
  * get_job_logs m21/m22 (``"DEBUG\": 0`` -> ``"XXDEBUGXX\"``/``"debug\"``):
    level_upper is always the .upper() form "DEBUG", the mutant key never
    matches, .get misses -> default 0 == shipped value 0 — identical for
    EVERY input.  The sibling renames m24/m27/m30/m31 DO change a nonzero
    lookup and are killed by the info/warning/error rows below.
No other prediction survives contact-by-argument: the m34 key->None lookup
always MISSES (returns the default 0) and the info/warning/error rows kill
it, and the bogus-level row kills the default mutants (m35 None raises at
``None > 0``, m37 trailing-comma drop returns None -> same raise, m38
default 1 adds a filter).
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest import mock
from uuid import UUID

import backend.services.job_history_service as jhs
import backend.services.job_log_emitter as jle
from backend.services.job_history_service import (
    AttemptRecord,
    JobHistory,
    JobHistoryService,
    JobLogEntry,
    TransitionRecord,
)

JID = "11111111-2222-3333-4444-555555555555"
JU = UUID(JID)
BAD = "not-a-uuid"

CREATED = datetime(2026, 10, 1, 8, 0, 0, tzinfo=UTC)
STARTED = datetime(2026, 10, 1, 8, 5, 0, tzinfo=UTC)
COMPLETED = datetime(2026, 10, 1, 8, 9, 30, tzinfo=UTC)
SINCE_DT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

JOB_TABLE = (
    "SELECT jobs.id, jobs.job_type, jobs.status, jobs.queue_name, jobs.priority, "
    "jobs.created_at, jobs.started_at, jobs.completed_at, jobs.progress_percent, "
    "jobs.current_step, jobs.result, jobs.error_message, jobs.error_traceback, "
    "jobs.attempt_number, jobs.max_attempts, jobs.next_retry_at FROM jobs "
    "WHERE jobs.id = :id_1"
)
TRANS_TABLE = (
    "SELECT job_transitions.id, job_transitions.job_id, job_transitions.from_status, "
    "job_transitions.to_status, job_transitions.transitioned_at, "
    "job_transitions.triggered_by, job_transitions.metadata_json "
    "FROM job_transitions WHERE job_transitions.job_id = :job_id_1 "
    "ORDER BY job_transitions.transitioned_at"
)
ATT_TABLE = (
    "SELECT job_attempts.id, job_attempts.job_id, job_attempts.attempt_number, "
    "job_attempts.started_at, job_attempts.ended_at, job_attempts.status, "
    "job_attempts.worker_id, job_attempts.error_message, "
    "job_attempts.error_traceback, job_attempts.result FROM job_attempts "
    "WHERE job_attempts.job_id = :job_id_1 ORDER BY job_attempts.attempt_number"
)
END_TABLE = (
    "SELECT job_attempts.id, job_attempts.job_id, job_attempts.attempt_number, "
    "job_attempts.started_at, job_attempts.ended_at, job_attempts.status, "
    "job_attempts.worker_id, job_attempts.error_message, "
    "job_attempts.error_traceback, job_attempts.result FROM job_attempts "
    "WHERE job_attempts.job_id = :job_id_1 AND job_attempts.attempt_number = "
    ":attempt_number_1"
)
LOG_HEAD = (
    "SELECT job_logs.id, job_logs.job_id, job_logs.attempt_number, "
    "job_logs.timestamp, job_logs.level, job_logs.message, job_logs.context "
    "FROM job_logs"
)
LOGS_PLAIN = (
    f"{LOG_HEAD} WHERE job_logs.job_id = :job_id_1 ORDER BY job_logs.timestamp LIMIT :param_1"
)
LOGS_LEVEL = (
    f"{LOG_HEAD} WHERE job_logs.job_id = :job_id_1 AND job_logs.level IN "
    "(__[POSTCOMPILE_level_1]) ORDER BY job_logs.timestamp LIMIT :param_1"
)
LOGS_SINCE = (
    f"{LOG_HEAD} WHERE job_logs.job_id = :job_id_1 AND job_logs.timestamp >= "
    ":timestamp_1 ORDER BY job_logs.timestamp LIMIT :param_1"
)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# =============================================================================
# Log recorder — swapped for jhs.logger.  Unlike reid (plain f-strings) this
# module logs via extra= KWARGS, so the record is (method, args, kwargs) and
# every pin below asserts the FULL tuple: message None/XX/CASE/lower twins,
# extra=None/missing twins, key renames and str(None) all die on equality.
# =============================================================================


class Rec:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def debug(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("debug", args, kw))

    def info(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("info", args, kw))

    def warning(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("warning", args, kw))

    def error(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("error", args, kw))

    def critical(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("critical", args, kw))


@contextmanager
def log_rec():
    rec = Rec()
    with mock.patch.object(jhs, "logger", rec):
        yield rec


# =============================================================================
# Recording session — signature mirrors AsyncSession.execute: the statement
# is a REQUIRED positional (a dropped/None query raises TypeError here, the
# way SQLAlchemy's "query expected" ArgumentError fires on a real session),
# and every accepted statement is recorded as (normalized-string, params).
# Results are consumed POSITIONALLY, so a mutant that skips or duplicates an
# execute surfaces as IndexError rather than a silent verdict.
# =============================================================================


class Result:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def scalar_one_or_none(self) -> Any:
        return self._payload

    def scalars(self) -> Result:
        return self

    def all(self) -> list[Any]:
        return list(self._payload)


class Session:
    def __init__(self, results: list[Any] | None = None) -> None:
        self.results = list(results or [])
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.added: list[Any] = []
        self.flushes = 0

    async def execute(self, query: Any) -> Result:
        if query is None:
            raise TypeError("query expected")  # mirrors SQLAlchemy ArgumentError
        stmt = query
        self.queries.append((" ".join(str(stmt).split()), dict(stmt.compile().params)))
        if not self.results:
            raise IndexError("unexpected execute — shipped issues no further queries")
        return Result(self.results.pop(0))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1


class Emitter:
    """Mirrors JobLogEmitter.emit_log's positional-or-keyword signature."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.error = error

    async def emit_log(self, job_id: Any, level: Any, message: Any, context: Any = None) -> bool:
        self.calls.append(("emit_log", job_id, level, message, context))
        if self.error is not None:
            raise self.error
        return True


def svc_with(session: Session) -> JobHistoryService:
    return JobHistoryService(session)


def patch_emitter(em: Emitter, *, boom: bool = False):
    """Patch the FUNCTION THE SERVICE IMPORTS AT CALL TIME (the service does
    ``from backend.services.job_log_emitter import get_job_log_emitter``
    inside add_job_log, so patching the emitter MODULE attribute is the one
    position the call actually reads)."""

    async def _getter() -> Emitter:
        return em

    async def _boom() -> Emitter:
        # the GETTER raises — patching emit_log instead would never fire:
        # the service's late `from ... import get_job_log_emitter` re-reads
        # THIS attribute inside every add_job_log call, after the session
        # flush, so the import itself is the failure-injection point.
        raise RuntimeError("redis down")

    return mock.patch.object(jle, "get_job_log_emitter", new=_boom if boom else _getter)


# =============================================================================
# JobHistory.to_dict — the whole 32-key family is dict-key renames/XX-wraps
# plus started/completed/ended `and False`/`or True` polarity.  Two full-dict
# EQUALITY rows (populated + null-datetime) pin every literal key once and
# both polarities of all three ternaries.
# =============================================================================


def _full_history() -> JobHistory:
    return JobHistory(
        job_id=JID,
        job_type="video_analysis",
        status="completed",
        created_at=CREATED,
        started_at=STARTED,
        completed_at=COMPLETED,
        transitions=[
            TransitionRecord(
                from_status="queued",
                to_status="running",
                at=STARTED,
                triggered_by="worker-7",
                details={"metadata": {"gpu": "a100"}},
            )
        ],
        attempts=[
            AttemptRecord(
                attempt_number=2,
                started_at=STARTED,
                ended_at=COMPLETED,
                status="succeeded",
                error=None,
                worker_id="worker-7",
                duration_seconds=270.5,
                result={"objects": 3},
            )
        ],
    )


def test_to_dict_populated_full_equality() -> None:
    assert _full_history().to_dict() == {
        "job_id": JID,
        "job_type": "video_analysis",
        "status": "completed",
        "created_at": "2026-10-01T08:00:00+00:00",
        "started_at": "2026-10-01T08:05:00+00:00",
        "completed_at": "2026-10-01T08:09:30+00:00",
        "transitions": [
            {
                "from": "queued",
                "to": "running",
                "at": "2026-10-01T08:05:00+00:00",
                "triggered_by": "worker-7",
                "details": {"metadata": {"gpu": "a100"}},
            }
        ],
        "attempts": [
            {
                "attempt_number": 2,
                "started_at": "2026-10-01T08:05:00+00:00",
                "ended_at": "2026-10-01T08:09:30+00:00",
                "status": "succeeded",
                "error": None,
                "worker_id": "worker-7",
                "duration_seconds": 270.5,
                "result": {"objects": 3},
            }
        ],
    }


def test_to_dict_null_datetimes_full_equality() -> None:
    hist = _full_history()
    hist.started_at = None
    hist.completed_at = None
    hist.attempts[0].ended_at = None
    assert hist.to_dict() == {
        "job_id": JID,
        "job_type": "video_analysis",
        "status": "completed",
        "created_at": "2026-10-01T08:00:00+00:00",
        "started_at": None,
        "completed_at": None,
        "transitions": [
            {
                "from": "queued",
                "to": "running",
                "at": "2026-10-01T08:05:00+00:00",
                "triggered_by": "worker-7",
                "details": {"metadata": {"gpu": "a100"}},
            }
        ],
        "attempts": [
            {
                "attempt_number": 2,
                "started_at": "2026-10-01T08:05:00+00:00",
                "ended_at": None,
                "status": "succeeded",
                "error": None,
                "worker_id": "worker-7",
                "duration_seconds": 270.5,
                "result": {"objects": 3},
            }
        ],
    }


# =============================================================================
# get_job_history — query-shape trio (None/where-None/!=/select-None), the
# JobHistory constructor fields, and the not-found debug + extra family.
# =============================================================================


def _job_row() -> SimpleNamespace:
    # completed_at non-None on purpose: with None on BOTH sides the
    # completed_at=job.completed_at -> =None mutant (m28) would agree with
    # shipped.  Every JobHistory field the ctor writes is asserted non-None.
    return SimpleNamespace(
        id=JID,
        job_type="video_analysis",
        status="running",
        created_at=CREATED,
        started_at=STARTED,
        completed_at=COMPLETED,
    )


def test_get_job_history_success_queries_and_records() -> None:
    session = Session(
        results=[
            _job_row(),
            [
                SimpleNamespace(
                    from_status="queued",
                    to_status="running",
                    transitioned_at=STARTED,
                    triggered_by="scheduler",
                    metadata_json={"q": 1},
                )
            ],
            [
                SimpleNamespace(
                    attempt_number=1,
                    started_at=STARTED,
                    ended_at=None,
                    status="running",
                    error_message=None,
                    worker_id="worker-7",
                    duration_seconds=None,
                    result=None,
                )
            ],
        ]
    )
    with log_rec() as rec:
        hist = run(svc_with(session).get_job_history(JID))
    assert session.queries == [
        (JOB_TABLE, {"id_1": JID}),
        (TRANS_TABLE, {"job_id_1": JID}),
        (ATT_TABLE, {"job_id_1": JU}),
    ]
    assert hist == JobHistory(
        job_id=JID,
        job_type="video_analysis",
        status="running",
        created_at=CREATED,
        started_at=STARTED,
        completed_at=COMPLETED,
        transitions=[
            TransitionRecord(
                from_status="queued",
                to_status="running",
                at=STARTED,
                triggered_by="scheduler",
                details={"metadata": {"q": 1}},
            )
        ],
        attempts=[
            AttemptRecord(
                attempt_number=1,
                started_at=STARTED,
                ended_at=None,
                status="running",
                error=None,
                worker_id="worker-7",
                duration_seconds=None,
                result=None,
            )
        ],
    )
    assert rec.calls == []


def test_get_job_history_not_found_logs_debug_only() -> None:
    session = Session(results=[None])
    with log_rec() as rec:
        assert run(svc_with(session).get_job_history(JID)) is None
    assert session.queries == [(JOB_TABLE, {"id_1": JID})]
    assert rec.calls == [
        ("debug", ("Job not found for history lookup",), {"extra": {"job_id": JID}})
    ]


# =============================================================================
# _get_transitions / _get_attempts — direct-call rows: statement pins catch
# the where(None)/!=/order_by(None)/select(None)/whole-statement family that
# still RETURNS rows under the keyed fake, while full dataclass-list EQUALITY
# catches every field-swap and the initial/falsy-metadata polarity pair.
# =============================================================================


def test_get_transitions_maps_every_field_and_both_polarities() -> None:
    session = Session(
        results=[
            [
                SimpleNamespace(
                    from_status="initial",
                    to_status="queued",
                    transitioned_at=CREATED,
                    triggered_by="api",
                    metadata_json={},
                ),
                SimpleNamespace(
                    from_status="queued",
                    to_status="running",
                    transitioned_at=STARTED,
                    triggered_by="worker-7",
                    metadata_json={"gpu": "a100"},
                ),
            ]
        ]
    )
    rows = run(svc_with(session)._get_transitions(JID))
    assert session.queries == [(TRANS_TABLE, {"job_id_1": JID})]
    assert rows == [
        TransitionRecord(
            from_status=None,
            to_status="queued",
            at=CREATED,
            triggered_by="api",
            details=None,
        ),
        TransitionRecord(
            from_status="queued",
            to_status="running",
            at=STARTED,
            triggered_by="worker-7",
            details={"metadata": {"gpu": "a100"}},
        ),
    ]


def test_get_attempts_maps_every_field() -> None:
    session = Session(
        results=[
            [
                SimpleNamespace(
                    attempt_number=3,
                    started_at=STARTED,
                    ended_at=COMPLETED,
                    status="failed",
                    error_message="gpu OOM",
                    worker_id="worker-9",
                    duration_seconds=12.5,
                    result={"partial": True},
                )
            ]
        ]
    )
    rows = run(svc_with(session)._get_attempts(JID))
    assert session.queries == [(ATT_TABLE, {"job_id_1": JU})]
    assert rows == [
        AttemptRecord(
            attempt_number=3,
            started_at=STARTED,
            ended_at=COMPLETED,
            status="failed",
            error="gpu OOM",
            worker_id="worker-9",
            duration_seconds=12.5,
            result={"partial": True},
        )
    ]


# =============================================================================
# get_job_logs — the 44-key family.  Every row pins the FULL (statement,
# params) so the query-shape mutants (where(None)->WHERE NULL, select(None),
# !=, order_by(None), limit(None)->no LIMIT, timestamp >= vs >) die even
# though the keyed fake returns the same rows; the level-table mutants die on
# the per-level params.  Invalid-ID row pins the debug message + extra.
# =============================================================================


def _log_rows() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            timestamp=STARTED,
            level="info",
            message="frame 100 processed",
            context={"fps": 24},
            attempt_number=3,
        )
    ]


def _entry() -> JobLogEntry:
    return JobLogEntry(
        timestamp=STARTED,
        level="info",
        message="frame 100 processed",
        context={"fps": 24},
        attempt_number=3,
    )


def test_get_job_logs_plain_default_shape_and_entries() -> None:
    session = Session(results=[_log_rows()])
    entries = run(svc_with(session).get_job_logs(JID))
    assert session.queries == [(LOGS_PLAIN, {"job_id_1": JU, "param_1": 1000})]
    assert entries == [_entry()]


def test_get_job_logs_level_error_slice_params() -> None:
    session = Session(results=[[]])
    assert run(svc_with(session).get_job_logs(JID, level="error")) == []
    assert session.queries == [
        (LOGS_LEVEL, {"job_id_1": JU, "level_1": ["error"], "param_1": 1000})
    ]


def test_get_job_logs_level_info_slice_params() -> None:
    session = Session(results=[[]])
    assert run(svc_with(session).get_job_logs(JID, level="info")) == []
    assert session.queries == [
        (LOGS_LEVEL, {"job_id_1": JU, "level_1": ["info", "warning", "error"], "param_1": 1000})
    ]


def test_get_job_logs_level_warning_slice_params() -> None:
    session = Session(results=[[]])
    assert run(svc_with(session).get_job_logs(JID, level="WARNING")) == []
    assert session.queries == [
        (LOGS_LEVEL, {"job_id_1": JU, "level_1": ["warning", "error"], "param_1": 1000})
    ]


def test_get_job_logs_level_debug_adds_no_filter_clause() -> None:
    # min_level 0 -> the `if min_level > 0:` block must NOT run: any mutant
    # that shifts DEBUG to 1 (m23) or relaxes the guard (m39) adds an IN
    # clause here and dies on this exact-shape pin.
    session = Session(results=[[]])
    assert run(svc_with(session).get_job_logs(JID, level="debug")) == []
    assert session.queries == [(LOGS_PLAIN, {"job_id_1": JU, "param_1": 1000})]


def test_get_job_logs_unknown_level_defaults_unfiltered() -> None:
    # shipped: .get miss -> 0 -> no clause, call completes.  m35/m37 make the
    # miss return None -> TypeError at `min_level > 0`; m38's default 1 adds
    # a filter.  Both polarities die against this row.
    session = Session(results=[[]])
    assert run(svc_with(session).get_job_logs(JID, level="bogus")) == []
    assert session.queries == [(LOGS_PLAIN, {"job_id_1": JU, "param_1": 1000})]


def test_get_job_logs_since_uses_ge_not_gt() -> None:
    session = Session(results=[[]])
    assert run(svc_with(session).get_job_logs(JID, since=SINCE_DT)) == []
    assert session.queries == [
        (LOGS_SINCE, {"job_id_1": JU, "timestamp_1": SINCE_DT, "param_1": 1000})
    ]


def test_get_job_logs_explicit_limit_param() -> None:
    session = Session(results=[[]])
    assert run(svc_with(session).get_job_logs(JID, limit=5)) == []
    assert session.queries == [(LOGS_PLAIN, {"job_id_1": JU, "param_1": 5})]


def test_get_job_logs_invalid_uuid_logs_and_skips_query() -> None:
    session = Session()
    with log_rec() as rec:
        assert run(svc_with(session).get_job_logs(BAD)) == []
    assert session.queries == []
    assert rec.calls == [
        ("debug", ("Invalid job ID format for logs lookup",), {"extra": {"job_id": BAD}})
    ]


# =============================================================================
# record_attempt_start / record_attempt_end — the real JobAttempt model
# RAISES on unknown kwargs and leaves unset columns at None, so asserting
# every ctor field on the returned instance kills the removed/None twins at
# their site; attempt_number=2 (not the default) pins the ctor-vs-default
# confusion; the ended-at row pins tz-awareness (datetime.now(None) is
# NAIVE -> kills m26, =None dies on the attribute access).
# =============================================================================


def test_record_attempt_start_persists_exact_fields_and_info() -> None:
    session = Session()
    with log_rec() as rec:
        attempt = run(svc_with(session).record_attempt_start(JID, 2, "worker-7"))
    assert session.added == [attempt]
    assert attempt is not None
    assert (attempt.job_id, attempt.attempt_number, attempt.worker_id) == (JU, 2, "worker-7")
    assert attempt.status == "started"
    assert session.flushes == 1
    assert rec.calls == [
        (
            "info",
            ("Job attempt started",),
            {"extra": {"job_id": JID, "attempt_number": 2, "worker_id": "worker-7"}},
        )
    ]


def test_record_attempt_start_invalid_uuid_warns_and_adds_nothing() -> None:
    session = Session()
    with log_rec() as rec:
        assert run(svc_with(session).record_attempt_start(BAD, 1, "w")) is None
    assert session.added == []
    assert rec.calls == [
        (
            "warning",
            ("Invalid job ID format for attempt recording",),
            {"extra": {"job_id": BAD}},
        )
    ]


def test_record_attempt_end_found_query_assigns_all_and_logs() -> None:
    attempt = SimpleNamespace(
        ended_at=None,
        status="started",
        error_message=None,
        error_traceback=None,
        result=None,
    )
    session = Session(results=[attempt])
    with log_rec() as rec:
        out = run(
            svc_with(session).record_attempt_end(
                JID,
                2,
                "failed",
                error_message="gpu OOM",
                error_traceback="Traceback...",
                result={"retry": True},
            )
        )
    assert out is attempt
    assert session.queries == [(END_TABLE, {"job_id_1": JU, "attempt_number_1": 2})]
    assert attempt.status == "failed"
    assert attempt.error_message == "gpu OOM"
    assert attempt.error_traceback == "Traceback..."
    assert attempt.result == {"retry": True}
    assert attempt.ended_at is not None and attempt.ended_at.tzinfo is not None
    assert rec.calls == [
        (
            "info",
            ("Job attempt ended",),
            {"extra": {"job_id": JID, "attempt_number": 2, "status": "failed"}},
        )
    ]


def test_record_attempt_end_not_found_warns_exact() -> None:
    session = Session(results=[None])
    with log_rec() as rec:
        assert run(svc_with(session).record_attempt_end(JID, 7, "succeeded")) is None
    assert session.queries == [(END_TABLE, {"job_id_1": JU, "attempt_number_1": 7})]
    assert rec.calls == [
        (
            "warning",
            ("Job attempt not found for end recording",),
            {"extra": {"job_id": JID, "attempt_number": 7}},
        )
    ]


# =============================================================================
# add_job_log — the x2 occurrence twins: ONE success row exercises BOTH
# kwargs sites (the JobLog constructor AND the emitter call), so the removed/
# None context/message twins die at their own site (redcheck-subset-feed-
# shape-twins).  level="WARNING" input -> stored "warning" (the .lower()) but
# emitted RAW (the emitter gets what the caller passed).  context non-None
# pins the context=None/removed twins; attempt_number=4 (not default 1)
# pins that pair.
# =============================================================================


def test_add_job_log_stores_row_and_emits_raw_kwargs() -> None:
    session = Session()
    em = Emitter()
    with patch_emitter(em), log_rec() as rec:
        entry = run(
            svc_with(session).add_job_log(
                JID, "WARNING", "latency high", context={"p95": 2.1}, attempt_number=4
            )
        )
    assert session.added == [entry]
    assert entry is not None
    assert (entry.job_id, entry.attempt_number, entry.level) == (JU, 4, "warning")
    assert entry.message == "latency high"
    assert entry.context == {"p95": 2.1}
    assert session.flushes == 1
    assert em.calls == [("emit_log", JID, "WARNING", "latency high", {"p95": 2.1})]
    assert rec.calls == []


def test_add_job_log_skips_emitter_when_flag_false() -> None:
    session = Session()
    em = Emitter()
    with patch_emitter(em), log_rec() as rec:
        entry = run(svc_with(session).add_job_log(JID, "info", "quiet", emit_to_websocket=False))
    assert entry is not None
    assert entry.level == "info"
    assert em.calls == []
    assert rec.calls == []


def test_add_job_log_emit_failure_is_swallowed() -> None:
    session = Session()
    with patch_emitter(Emitter(), boom=True), log_rec() as rec:
        entry = run(svc_with(session).add_job_log(JID, "error", "disk full"))
    assert entry is not None
    assert session.added == [entry]
    assert rec.calls == [
        (
            "warning",
            ("Failed to emit job log to WebSocket: redis down",),
            {"extra": {"job_id": JID}},
        )
    ]


def test_add_job_log_invalid_uuid_warns_and_adds_nothing() -> None:
    session = Session()
    with log_rec() as rec:
        assert run(svc_with(session).add_job_log(BAD, "info", "x")) is None
    assert session.added == []
    assert rec.calls == [
        ("warning", ("Invalid job ID format for log recording",), {"extra": {"job_id": BAD}})
    ]


# =============================================================================
# Factory + invalid-path UUID=None twins (job_uuid=None -> params None on the
# pinned statement, covered above by the query pins).
# =============================================================================


def test_record_attempt_end_invalid_uuid_warns_before_query() -> None:
    session = Session()
    with log_rec() as rec:
        assert run(svc_with(session).record_attempt_end(BAD, 1, "succeeded")) is None
    assert session.queries == []
    assert rec.calls == [
        (
            "warning",
            ("Invalid job ID format for attempt end recording",),
            {"extra": {"job_id": BAD}},
        )
    ]


def test_get_job_history_uuid_input_stringifies_into_query() -> None:
    session = Session(results=[None])
    with log_rec():
        assert run(svc_with(session).get_job_history(JU)) is None
    assert session.queries == [(JOB_TABLE, {"id_1": JID})]


def test_factory_returns_service_bound_to_session() -> None:
    session = Session()
    svc = jhs.get_job_history_service(session)
    assert isinstance(svc, JobHistoryService)
    assert svc._session is session
