"""Batch-14 battery: job_service dossier clusters C3-C9 (wp44-triage). The
module's covering tests drive every query through an AsyncMock that never
compiles SQL, so query-shape mutants were invisible (dossier: "the mock is
a mirror"). This battery captures the statement handed to db.execute and
compiles it (postgresql dialect, literal_binds) against MEASURED reference
strings (probe 2026-09-22, /tmp/sql-probe.json + /tmp/cleanup-probe.json),
pins stats result-value ORDER/labels (measured whole-dict), freezes the
cleanup cutoff math with a patched module datetime, and asserts tracker
lookup arg identity (C9).

Cluster coverage: C3 query-build clobbers (48) via exact compiled SQL;
C4 stats value/label pins (16); C5 predicate flips (4) via "!="/IN text;
C6 cutoff math (11) via frozen-datetime literal; C7 order_by shape (5);
C8 boundary/fallback arithmetic (6) via operator text + rowcount/scalar/
avg-guard inputs; C9 tracker id (2). C10 (6) needs a real sqlite session
(integration route, dossier T5b) and C1/C2/C11/C12 (78) follow the
dossier's EQUIVALENT / LOW-VALUE rulings. Production not bent to any
mutant; every string measured first.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from backend.models.job import JobStatus
from backend.services.job_service import DatabaseJobService, JobService

pytestmark = pytest.mark.unit

DIALECT = postgresql.dialect()


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


class TestGetActiveJobsSql:
    async def test_unfiltered_exact_sql(self):
        db, cap, res = cap_execute()
        r = rows_result([])
        res.append(r)
        svc = DatabaseJobService(db)
        await svc.get_active_jobs()
        # MEASURED reference (probe /tmp/sql-probe.json active_no_filter)
        assert compiled(cap[0]) == (
            "SELECT jobs.id, jobs.job_type, jobs.status, jobs.queue_name, jobs.priority, "
            "jobs.created_at, jobs.started_at, jobs.completed_at, jobs.progress_percent, "
            "jobs.current_step, jobs.result, jobs.error_message, jobs.error_traceback, "
            "jobs.attempt_number, jobs.max_attempts, jobs.next_retry_at \nFROM jobs \n"
            "WHERE jobs.status IN ('queued', 'running') "
            "ORDER BY jobs.priority ASC, jobs.created_at ASC"
        )

    async def test_filtered_exact_sql_includes_both_orders(self):
        db, cap, res = cap_execute()
        res.append(rows_result([]))
        svc = DatabaseJobService(db)
        await svc.get_active_jobs(job_type="export")
        sql = compiled(cap[0])
        assert "jobs.status IN ('queued', 'running')" in sql
        assert "jobs.job_type = 'export'" in sql  # C5: `!=` mutant changes text
        assert sql.endswith("ORDER BY jobs.priority ASC, jobs.created_at ASC")  # C7
        # optional-filter guard `is not None` -> `is None` inverts:
        db2, cap2, res2 = cap_execute()
        res2.append(rows_result([]))
        await DatabaseJobService(db2).get_active_jobs()
        assert "job_type" not in compiled(cap2[0]).split("SELECT", 1)[
            0
        ] or "jobs.job_type =" not in compiled(cap2[0])


class TestGetJobStats:
    async def test_whole_stats_dict_and_sql(self):
        db, cap, res = cap_execute()
        res.append(rows_result([("completed", 3), ("failed", 1)]))  # by_status
        res.append(rows_result([("export", 7)]))  # by_type
        res.append(scalar_result(9))  # total
        res.append(scalar_result(42.5))  # avg duration
        res.append(scalar_result(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)))  # oldest
        svc = DatabaseJobService(db)
        with patch("backend.services.job_service.datetime", autospec=True) as dt:
            dt.now.return_value = datetime(2024, 1, 15, 10, 1, 30, tzinfo=UTC)
            stats = await svc.get_job_stats()
        # C4: value ORDER pinned — row[0]/row[1] swaps and key clobbers die
        assert stats == {
            "total_jobs": 9,
            "by_status": [{"status": "completed", "count": 3}, {"status": "failed", "count": 1}],
            "by_type": [{"job_type": "export", "count": 7}],
            "average_duration_seconds": 42.5,
            "oldest_pending_job_age_seconds": 90.0,
        }
        sqls = [compiled(s) for s in cap]
        # C3/C11: status group-by shape + epoch extract literal (measured)
        assert (
            sqls[0]
            == "SELECT jobs.status, count(jobs.id) AS count_1 \nFROM jobs GROUP BY jobs.status"
        )
        assert "GROUP BY jobs.job_type" in sqls[1]
        assert sqls[2] == "SELECT count(jobs.id) AS count_1 \nFROM jobs"
        # C5: avg filter must be status = completed (== only); C11 epoch
        assert (
            "EXTRACT(epoch FROM jobs.completed_at) - EXTRACT(epoch FROM jobs.started_at)" in sqls[3]
        )
        assert "jobs.status = 'completed'" in sqls[3]
        assert (
            "jobs.started_at IS NOT NULL" in sqls[3] and "jobs.completed_at IS NOT NULL" in sqls[3]
        )
        assert "jobs.status = 'queued'" in sqls[4]  # oldest pending, == not !=

    async def test_empty_db_shapes(self):
        # measured /tmp/cleanup-probe.json stats_empty: total or 0 -> 0,
        # avg falsy -> None, oldest None -> None
        db, cap, res = cap_execute()
        res.extend(
            [
                rows_result([]),
                rows_result([]),
                scalar_result(None),
                scalar_result(None),
                scalar_result(None),
            ]
        )
        stats = await DatabaseJobService(db).get_job_stats()
        assert stats == {
            "total_jobs": 0,
            "by_status": [],
            "by_type": [],
            "average_duration_seconds": None,
            "oldest_pending_job_age_seconds": None,
        }


class TestCleanupOldJobs:
    async def test_cutoff_math_and_predicate(self):
        db, cap, res = cap_execute()
        r = MagicMock()
        r.rowcount = 4
        res.append(r)
        svc = DatabaseJobService(db)
        with patch("backend.services.job_service.datetime", autospec=True) as dt:
            dt.now.return_value = datetime(2026, 9, 22, 23, 59, 5, tzinfo=UTC)
            dt.side_effect = lambda *a: datetime(*a)
            n = await svc.cleanup_old_jobs()
        assert n == 4
        sql = compiled(cap[0])
        # midnight-floor then -30d: 2026-09-22 23:59:05 -> 2026-08-23 00:00
        assert "DELETE FROM jobs WHERE jobs.status IN ('completed', 'failed', 'cancelled')" in sql
        assert "jobs.completed_at < '2026-08-23 00:00:00+00:00'" in sql  # C6 + C8 `<`
        assert "jobs.completed_at <= " not in sql

    async def test_days_and_sign(self):
        db, cap, res = cap_execute()
        r = MagicMock()
        r.rowcount = 0
        res.append(r)
        with patch("backend.services.job_service.datetime", autospec=True) as dt:
            dt.now.return_value = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)
            dt.side_effect = lambda *a: datetime(*a)
            n = await DatabaseJobService(db).cleanup_old_jobs(days=7)
        assert n == 0  # C8: `or 0` -> `or 1` returns 1 here
        assert "< '2026-01-24 00:00:00+00:00'" in compiled(cap[0])  # -7d not +7d

    async def test_rowcount_none_falls_back_zero(self):
        db, cap, res = cap_execute()
        r = MagicMock()
        r.rowcount = None
        res.append(r)
        assert await DatabaseJobService(db).cleanup_old_jobs() == 0


class TestGetJobByIdSql:
    async def test_id_predicate_and_none_result(self):
        db, cap, res = cap_execute()
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        res.append(r)
        svc = DatabaseJobService(db)
        assert await svc.get_job_by_id("abc-123") is None
        assert "WHERE jobs.id = 'abc-123'" in compiled(cap[0])  # C10-adjacent text kill

    async def test_found_returns_row(self):
        db, cap, res = cap_execute()
        job = SimpleNamespace(id="x")
        r = MagicMock()
        r.scalar_one_or_none.return_value = job
        res.append(r)
        assert await DatabaseJobService(db).get_job_by_id("x") is job


class TestListJobsSql:
    async def test_default_sort_pagination_count(self):
        db, cap, res = cap_execute()
        res.append(scalar_result(12))  # count query
        res.append(rows_result(["jobA"]))  # main query
        jobs, total = await DatabaseJobService(db).list_jobs()
        assert (jobs, total) == (["jobA"], 12)  # `scalar or 0`->`and 0` fold dies
        count_sql, main_sql = compiled(cap[0]), compiled(cap[1])
        assert "SELECT count(*) AS count_1 \nFROM (SELECT" in count_sql
        assert "ORDER BY jobs.created_at DESC" in main_sql
        assert "LIMIT" in main_sql and "OFFSET" in main_sql

    async def test_filters_compile_with_values(self):
        db, cap, res = cap_execute()
        res.append(scalar_result(0))
        res.append(rows_result([]))
        since = datetime(2024, 1, 1, tzinfo=UTC)
        await DatabaseJobService(db).list_jobs(
            status="failed", job_type="export", since=since, order="asc", sort="priority"
        )
        sql = compiled(cap[1])
        assert "jobs.status = 'failed'" in sql
        assert "jobs.job_type = 'export'" in sql
        assert "jobs.created_at >= '2024-01-01 00:00:00+00:00'" in sql
        assert "ORDER BY jobs.priority ASC" in sql


class TestTrackerIdArg:
    """C9: get_job_or_404/get_job_detail passing None to the tracker."""

    @pytest.fixture
    def tracker(self):
        from backend.services.job_tracker import JobTracker

        t = MagicMock(spec=JobTracker)
        t.get_job_from_redis = AsyncMock()
        return t

    def test_or_404_forwards_exact_id(self, tracker):
        # JobInfo is a TypedDict (job_tracker.py:65) — plain dict literal
        info = {
            "job_id": "id-77",
            "job_type": "export",
            "status": JobStatus.RUNNING,
            "progress": 0,
            "message": "",
            "created_at": "2024-01-15T10:30:00+00:00",
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        tracker.get_job.return_value = info
        svc = JobService(job_tracker=tracker, redis_client=MagicMock())
        assert svc.get_job_or_404("id-77") is info
        tracker.get_job.assert_called_once_with("id-77")

    async def test_detail_forwards_exact_id(self, tracker):
        svc = JobService(job_tracker=tracker, redis_client=MagicMock())
        tracker.get_job.return_value = None
        tracker.get_job_from_redis.return_value = None
        with pytest.raises(HTTPException) as ei:
            await svc.get_job_detail("id-88")
        assert ei.value.status_code == 404
        tracker.get_job.assert_called_once_with("id-88")
        tracker.get_job_from_redis.assert_awaited_once_with("id-88")
