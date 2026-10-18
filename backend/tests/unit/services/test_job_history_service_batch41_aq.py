# TARGET-MODULE: backend.services.job_history_service
"""Campaign #41 battery AQ — backend/services/job_history_service.py survivors."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest import mock
from uuid import UUID

import backend.services.job_history_service as jhs
from backend.services.job_history_service import (
    JobHistoryService,
    JobLogEntry,
)

JID = "11111111-2222-3333-4444-555555555555"
JU = UUID(JID)
BAD = "not-a-uuid"

STARTED = datetime(2026, 10, 1, 8, 5, 0, tzinfo=UTC)
SINCE_DT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

JOB_TABLE = (
    "SELECT jobs.id, jobs.job_type, jobs.status, jobs.queue_name, jobs.priority, "
    "jobs.created_at, jobs.started_at, jobs.completed_at, jobs.progress_percent, "
    "jobs.current_step, jobs.result, jobs.error_message, jobs.error_traceback, "
    "jobs.attempt_number, jobs.max_attempts, jobs.next_retry_at FROM jobs "
    "WHERE jobs.id = :id_1"
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
            raise TypeError("query expected")
        stmt = query
        self.queries.append((" ".join(str(stmt).split()), dict(stmt.compile().params)))
        if not self.results:
            raise IndexError("unexpected execute — shipped issues no further queries")
        return Result(self.results.pop(0))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1


def svc_with(session: Session) -> JobHistoryService:
    return JobHistoryService(session)


def test_job_exists_found_and_not_found() -> None:
    session = Session(results=[SimpleNamespace(id=JID)])
    with log_rec() as rec:
        assert run(svc_with(session).job_exists(JID)) is True
    assert session.queries == [(JOB_TABLE, {"id_1": JID})]
    assert rec.calls == []

    session_missing = Session(results=[None])
    with log_rec() as rec_missing:
        assert run(svc_with(session_missing).job_exists(JU)) is False
    assert session_missing.queries == [(JOB_TABLE, {"id_1": JID})]
    assert rec_missing.calls == [
        ("debug", ("Job not found for logs lookup",), {"extra": {"job_id": JID}})
    ]


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
    session = Session(results=[[]])
    assert run(svc_with(session).get_job_logs(JID, level="debug")) == []
    assert session.queries == [(LOGS_PLAIN, {"job_id_1": JU, "param_1": 1000})]


def test_get_job_logs_unknown_level_defaults_unfiltered() -> None:
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


def test_add_job_log_stores_row() -> None:
    session = Session()
    with log_rec() as rec:
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
    assert rec.calls == []


def test_add_job_log_invalid_uuid_warns_and_adds_nothing() -> None:
    session = Session()
    with log_rec() as rec:
        assert run(svc_with(session).add_job_log(BAD, "info", "x")) is None
    assert session.added == []
    assert rec.calls == [
        ("warning", ("Invalid job ID format for log recording",), {"extra": {"job_id": BAD}})
    ]


def test_factory_returns_service_bound_to_session() -> None:
    session = Session()
    svc = jhs.get_job_history_service(session)
    assert isinstance(svc, JobHistoryService)
    assert svc._session is session
