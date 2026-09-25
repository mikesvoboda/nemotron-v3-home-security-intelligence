"""Batch-14b kill battery: the 34 SURVIVING mutants of batch-14 against
``backend/services/job_service.py::DatabaseJobService``.

batch14 (sibling file, untouched here) proved the query shapes for
get_active_jobs/get_job_stats/list_jobs/cleanup and pinned the cutoff math,
but left three gaps that the survivors fall into:

1. ``cleanup_old_jobs`` log surface — the message text, the ``> 0`` boundary
   and the ``extra={...}`` payload were never observed (14 mutants).
2. ``get_job_stats`` type_query / oldest_pending_query compiled text — batch14
   pinned the other five statements but not these two (7 mutants).
3. ``list_jobs`` DEFAULT arguments — every batch14 caller passed explicit
   kwargs, so the defaults never reached the rendered SQL (m1-m6), plus the
   sort-fallback / ``or 0`` / ``limit(None)`` shapes (m28, m31, m33, m34,
   m48) and the ``select(None)`` clobbers in list_jobs (m8) and in
   get_job_by_id, whose batch14 pin only looked at the WHERE text (m4).
   14 + 7 + 12 + 1 = the 34 survivors.

Every assertion below is a MEASURED shipped-behavior string (probe
2026-09-22, /tmp/b14b/p1.py + /tmp/b14b/p2.py + /tmp/b14b/p3.py, results
consolidated in /tmp/b14b-probes.json). Production was not bent to any
mutant.

EQUIVALENCE PROOFS (no test faked for these; the pin that does exist is the
documented-signature contract, see
TestListJobsDefaults.test_default_arguments_match_documented_contract):
* cleanup m10 renders ``< '2026-08-23 00:00:00.123456+00:00'`` where shipped
  renders ``< '2026-08-23 00:00:00+00:00'`` — killed only if now() carries
  microseconds, so the patched NOW uses microsecond=123456.
* list_jobs m5/m6 (order default ``"desc"`` -> ``"XXdescXX"``/``"DESC"``):
  the source only ever tests ``order == "asc"``, so all three values take the
  identical else-branch; MEASURED identical SQL
  (``ORDER BY jobs.created_at DESC \\n LIMIT 50 OFFSET 0``) — the SQL is
  provably blind to these mutants. Same for m3/m4 (sort default moved out of
  VALID_SORT_FIELDS → the ``else "created_at"`` fallback lands on the shipped
  column). Their only observable difference is the introspectable signature
  default that the docstring documents ("Default: 'desc'"), so they die to
  the signature pin, not to SQL.
"""

import inspect
import logging
from datetime import UTC, datetime
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from backend.services.job_service import DatabaseJobService

pytestmark = pytest.mark.unit

DIALECT = postgresql.dialect()

# MEASURED (probe /tmp/b14b/p1.py): the service module logger is a plain
# logging.Logger from logging.getLogger(__name__) that propagates to root, so
# caplog sees real LogRecords with the `extra` keys set as attributes.
LOGGER_NAME = "backend.services.job_service"


def compiled(stmt) -> str:
    return str(stmt.compile(dialect=DIALECT, compile_kwargs={"literal_binds": True}))


def cap_execute():
    """AsyncMock db whose execute captures every statement; returns
    queue of canned results in call order."""
    db = AsyncMock()
    captured: list = []
    results: list = []

    def _exec(stmt, *a, **k):
        captured.append(stmt)
        return results.pop(0)

    db.execute.side_effect = _exec
    return db, captured, results


def rows_result(rows):
    r = MagicMock()
    r.all.return_value = rows
    r.scalars.return_value.all.return_value = rows
    return r


def scalar_result(value):
    r = MagicMock()
    r.scalar.return_value = value
    return r


def rowcount_result(n):
    r = MagicMock()
    r.rowcount = n
    return r


# Patched "now" carrying nonzero microseconds: the microsecond=0 floor in the
# shipped cutoff is only observable when now() has microseconds (probe
# /tmp/b14b-probes.json cleanup). microsecond=123456 -> .123456 in SQL.
NOW = datetime(2026, 9, 22, 23, 59, 5, 123456, tzinfo=UTC)


def patch_now():
    """Patch the module-level datetime so tz-aware calls get NOW and
    tz-naive calls (the m11 mutant's datetime.now(None)) get NOW naive."""
    return patch("backend.services.job_service.datetime", autospec=True)


def _now_side_effect(tz=None):
    return NOW if tz is not None else NOW.replace(tzinfo=None)


class TestCleanupCutoffLiteral:
    """m10 (microsecond=0 arg dropped) + m11 (datetime.now(None) naive)."""

    async def test_cutoff_is_midnight_floor_with_offset(self):
        db, cap, res = cap_execute()
        res.append(rowcount_result(3))
        svc = DatabaseJobService(db)
        with patch_now() as dt:
            dt.now.side_effect = _now_side_effect
            n = await svc.cleanup_old_jobs()
        assert n == 3
        sql = compiled(cap[0])
        # MEASURED shipped reference: 2026-09-22 23:59:05.123456+00 -> floor
        # 2026-09-22 00:00:00+00 -> -30d = 2026-08-23 00:00:00+00:00 exactly
        # (m10 renders '...00:00:00.123456+00:00', m11 renders no +00:00).
        assert "jobs.completed_at < '2026-08-23 00:00:00+00:00'" in sql
        assert ".123456" not in sql  # m10
        assert "jobs.completed_at < '2026-08-23 00:00:00'" not in sql  # m11

    async def test_cutoff_literal_exact_sql(self):
        db, cap, res = cap_execute()
        res.append(rowcount_result(0))
        with patch_now() as dt:
            dt.now.side_effect = _now_side_effect
            await DatabaseJobService(db).cleanup_old_jobs(days=14)
        # MEASURED whole statement (probe cleanup.shipped, days=30 default);
        # recomputed here for days=14 -> 2026-09-22 -> 2026-09-08 00:00+00
        assert compiled(cap[0]) == (
            "DELETE FROM jobs WHERE jobs.status IN ('completed', 'failed', 'cancelled') "
            "AND jobs.completed_at < '2026-09-08 00:00:00+00:00'"
        )


class TestCleanupLogging:
    """m32/m33 (`> 0` boundary) + m34/m38/m39/m40 (message text) +
    m35/m37/m41-m44 (extra payload keys).

    MEASURED (probe /tmp/b14b-p2): the shipped call produces exactly ONE
    LogRecord named backend.services.job_service at INFO whose getMessage()
    is "Cleaned up old jobs" and on which the two extra keys are set as
    attributes (`record.deleted_count`, `record.older_than_days`). There is
    deliberately NO `.extra` attribute to read — std logging copies the dict
    into the record — so the pin is the getattr pair, which m35 (extra=None)
    and m37 (kwarg dropped) lose and m41-m44 rename away from.
    """

    @staticmethod
    def _records(caplog):
        return [r for r in caplog.records if r.name == LOGGER_NAME]

    async def test_zero_deletions_are_not_logged(self, caplog):
        db, cap, res = cap_execute()
        res.append(rowcount_result(0))
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            n = await DatabaseJobService(db).cleanup_old_jobs(days=5)
        assert n == 0
        assert self._records(caplog) == []  # m32 (>= 0) logs here
        assert "Cleaned up old jobs" not in caplog.text

    async def test_rowcount_none_is_not_logged(self, caplog):
        db, cap, res = cap_execute()
        res.append(rowcount_result(None))  # `or 0` fallback -> 0
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            n = await DatabaseJobService(db).cleanup_old_jobs(days=5)
        assert n == 0
        assert self._records(caplog) == []

    async def test_single_deletion_is_logged(self, caplog):
        db, cap, res = cap_execute()
        res.append(rowcount_result(1))
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            n = await DatabaseJobService(db).cleanup_old_jobs(days=9)
        assert n == 1
        recs = self._records(caplog)
        assert len(recs) == 1  # m33 (`> 1`) skips the log entirely
        assert recs[0].getMessage() == "Cleaned up old jobs"
        assert recs[0].deleted_count == 1
        assert recs[0].older_than_days == 9

    async def test_message_and_extra_payload_exact(self, caplog):
        # probe values: rowcount 7, days 14
        db, cap, res = cap_execute()
        res.append(rowcount_result(7))
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            n = await DatabaseJobService(db).cleanup_old_jobs(days=14)
        assert n == 7
        recs = self._records(caplog)
        assert len(recs) == 1
        rec = recs[-1]
        assert rec.levelno == logging.INFO
        assert rec.getMessage() == "Cleaned up old jobs"  # m34/m38/m39/m40
        assert rec.deleted_count == 7  # m35/m37/m41/m42
        assert rec.older_than_days == 14  # m35/m37/m43/m44
        assert not hasattr(rec, "extra")  # MEASURED: keys are copied, not nested

    async def test_extra_keys_are_the_only_new_attributes(self, caplog):
        db, cap, res = cap_execute()
        res.append(rowcount_result(2))
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            await DatabaseJobService(db).cleanup_old_jobs(days=1)
        rec = self._records(caplog)[-1]
        # m41-m44 rename exactly one key: both names must be present, and the
        # XX/UPPER aliases from those mutants must not be.
        assert hasattr(rec, "deleted_count") and hasattr(rec, "older_than_days")
        for ghost in (
            "XXdeleted_countXX",
            "DELETED_COUNT",
            "XXolder_than_daysXX",
            "OLDER_THAN_DAYS",
        ):
            assert not hasattr(rec, ghost)


class TestGetJobByIdColumns:
    """m4: select(Job) -> select(None) (batch14 only pinned the WHERE text)."""

    async def test_full_select_list_from_jobs(self):
        db, cap, res = cap_execute()
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        res.append(r)
        assert await DatabaseJobService(db).get_job_by_id("abc-123") is None
        # MEASURED whole statement (probe get_job_by_id.shipped)
        assert compiled(cap[0]) == (
            "SELECT jobs.id, jobs.job_type, jobs.status, jobs.queue_name, jobs.priority, "
            "jobs.created_at, jobs.started_at, jobs.completed_at, jobs.progress_percent, "
            "jobs.current_step, jobs.result, jobs.error_message, jobs.error_traceback, "
            "jobs.attempt_number, jobs.max_attempts, jobs.next_retry_at \nFROM jobs \n"
            "WHERE jobs.id = 'abc-123'"
        )
        assert "NULL AS anon_1" not in compiled(cap[0])  # MEASURED m4 rendering


class TestGetJobStatsTypeAndOldestPending:
    """m19-m23 (type_query) + m69/m70 (oldest_pending_query).

    MEASURED execution ORDER is status, type, total, avg-duration, oldest —
    five statements; batch14 pinned #0/#2/#3/#4 shapes but only "GROUP BY"
    for type_query and only the WHERE for oldest, so the projection lists of
    #1 and #4 were free real estate. All five are pinned whole here.
    """

    MEASURED_SQLS: ClassVar[list[str]] = [
        "SELECT jobs.status, count(jobs.id) AS count_1 \nFROM jobs GROUP BY jobs.status",
        "SELECT jobs.job_type, count(jobs.id) AS count_1 \nFROM jobs GROUP BY jobs.job_type",
        "SELECT count(jobs.id) AS count_1 \nFROM jobs",
        "SELECT avg(EXTRACT(epoch FROM jobs.completed_at) - EXTRACT(epoch FROM jobs.started_at))"
        " AS avg_1 \nFROM jobs \nWHERE jobs.status = 'completed' AND jobs.started_at IS NOT NULL"
        " AND jobs.completed_at IS NOT NULL",
        "SELECT min(jobs.created_at) AS min_1 \nFROM jobs \nWHERE jobs.status = 'queued'",
    ]

    def _results(self, res):
        res.extend(
            [
                rows_result([("completed", 3), ("failed", 1)]),  # by_status
                rows_result([("export", 7)]),  # by_type
                scalar_result(9),  # total
                scalar_result(42.5),  # avg duration
                scalar_result(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)),  # oldest
            ]
        )

    async def test_all_five_statements_verbatim(self):
        db, cap, res = cap_execute()
        self._results(res)
        with patch_now() as dt:
            dt.now.return_value = datetime(2024, 1, 15, 10, 1, 30, tzinfo=UTC)
            stats = await DatabaseJobService(db).get_job_stats()
        assert [compiled(s) for s in cap] == self.MEASURED_SQLS
        assert stats["by_type"] == [{"job_type": "export", "count": 7}]
        assert stats["oldest_pending_job_age_seconds"] == 90.0

    async def test_projection_columns_of_the_two_unpinned_queries(self):
        db, cap, res = cap_execute()
        self._results(res)
        with patch_now() as dt:
            dt.now.return_value = datetime(2024, 1, 15, 10, 1, 30, tzinfo=UTC)
            await DatabaseJobService(db).get_job_stats()
        type_sql = compiled(cap[1])
        oldest_sql = compiled(cap[4])
        # m19 (select(None, ...)) / m20 (second column None) / m21, m22
        # (single-column) / m23 (func.count(None) -> count(*))
        assert type_sql.startswith("SELECT jobs.job_type, count(jobs.id) AS count_1")
        assert "NULL" not in type_sql and "count(*)" not in type_sql
        # m69 (select(None)) / m70 (func.min(None))
        assert oldest_sql.startswith("SELECT min(jobs.created_at) AS min_1")
        assert "NULL" not in oldest_sql


class TestListJobsDefaults:
    """m1/m2 (limit/offset defaults) + m3/m4 (sort default) + m5/m6 (order
    default) + m8 (select(None) main query) + m48 (.limit(None)).

    MEASURED no-kwargs statements (probe list_default_*): the count query
    projects every jobs column into the subselect and the paged query ends
    "ORDER BY jobs.created_at DESC \\n LIMIT 50 OFFSET 0". m48 renders
    "LIMIT ALL" (measured); m8 renders "SELECT NULL AS anon_1".
    """

    MEASURED_COUNT_PREFIX = (
        "SELECT count(*) AS count_1 \nFROM (SELECT jobs.id AS id, jobs.job_type AS job_type, "
    )
    MEASURED_MAIN_SQL = (
        "SELECT jobs.id, jobs.job_type, jobs.status, jobs.queue_name, jobs.priority, "
        "jobs.created_at, jobs.started_at, jobs.completed_at, jobs.progress_percent, "
        "jobs.current_step, jobs.result, jobs.error_message, jobs.error_traceback, "
        "jobs.attempt_number, jobs.max_attempts, jobs.next_retry_at \nFROM jobs "
        "ORDER BY jobs.created_at DESC \n LIMIT 50 OFFSET 0"
    )

    async def test_no_kwargs_pagination_and_order_verbatim(self):
        db, cap, res = cap_execute()
        res.append(scalar_result(12))
        res.append(rows_result(["jobA"]))
        jobs, total = await DatabaseJobService(db).list_jobs()
        assert (list(jobs), total) == (["jobA"], 12)
        count_sql, main_sql = compiled(cap[0]), compiled(cap[1])
        assert main_sql == self.MEASURED_MAIN_SQL  # m1,m2,m3,m4,m5,m6,m48
        assert count_sql.startswith(self.MEASURED_COUNT_PREFIX)  # m8
        assert "LIMIT ALL" not in main_sql  # MEASURED m48 rendering
        assert "NULL AS anon_1" not in main_sql  # MEASURED m8 rendering
        assert " LIMIT 50 OFFSET 0" in main_sql  # m1 (51) / m2 (1)

    async def test_default_arguments_match_documented_contract(self):
        # SQL is provably blind to m3-m6 (see module docstring equivalence
        # note): order is only ever compared to "asc" and an out-of-set sort
        # falls back to created_at, so all four mutants re-render the shipped
        # SQL. Their only observable difference is the signature itself, which
        # the docstring documents ("Default: 50 / 0 / 'created_at' / 'desc'").
        params = inspect.signature(DatabaseJobService.list_jobs).parameters
        assert params["limit"].default == 50  # m1
        assert params["offset"].default == 0  # m2
        assert params["sort"].default == "created_at"  # m3, m4
        assert params["order"].default == "desc"  # m5, m6
        assert all(
            params[k].kind is inspect.Parameter.KEYWORD_ONLY
            for k in ("limit", "offset", "sort", "order")
        )


class TestListJobsSortFallback:
    """m31 (`or True`), m33/m34 (fallback string renamed)."""

    async def test_invalid_sort_falls_back_to_jobs_created_at(self):
        db, cap, res = cap_execute()
        res.append(scalar_result(0))
        res.append(rows_result([]))
        jobs, total = await DatabaseJobService(db).list_jobs(sort="bogus")
        assert (list(jobs), total) == ([], 0)
        sql = compiled(cap[1])
        # MEASURED shipped fallback: identical SQL to the no-kwargs call.
        # m31 would pass "bogus" to getattr(Job, ...) -> AttributeError;
        # m33/m34 do the same with their renamed fallbacks.
        assert "ORDER BY jobs.created_at DESC" in sql
        assert "\nFROM jobs ORDER BY jobs.created_at DESC" in sql
        assert "bogus" not in sql

    async def test_valid_sort_still_honoured(self):
        db, cap, res = cap_execute()
        res.append(scalar_result(0))
        res.append(rows_result([]))
        await DatabaseJobService(db).list_jobs(sort="priority", order="asc")
        assert "ORDER BY jobs.priority ASC" in compiled(cap[1])


class TestListJobsTotalFallback:
    """m28: ``count_result.scalar() or 0`` -> ``or 1``."""

    async def test_none_count_scalar_yields_zero(self):
        db, cap, res = cap_execute()
        res.append(scalar_result(None))
        res.append(rows_result([]))
        jobs, total = await DatabaseJobService(db).list_jobs()
        assert jobs == []
        assert total == 0  # MEASURED: scalar None -> total 0, m28 gives 1

    async def test_zero_count_scalar_yields_zero(self):
        db, cap, res = cap_execute()
        res.append(scalar_result(0))
        res.append(rows_result([]))
        _, total = await DatabaseJobService(db).list_jobs()
        assert total == 0

    async def test_real_count_is_passed_through(self):
        db, cap, res = cap_execute()
        res.append(scalar_result(7))
        res.append(rows_result([]))
        _, total = await DatabaseJobService(db).list_jobs()
        assert total == 7
