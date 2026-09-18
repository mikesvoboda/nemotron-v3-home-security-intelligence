# WP4.4 Triage Dossier — backend/services/job_service.py

Source of truth: `mutants/backend/services/job_service.py.meta` → **176 survivors** (exit_code 0;
83 killed; 301 keys still null at triage time — re-check this dossier against fresh verdicts when
the run completes). Diffs derived by AST-diffing each clobbered variant in
`mutants/backend/services/job_service.py` against `backend/services/job_service.py`
(mutmut-show-equivalent; zero cache contention; every survivor individually classified —
cluster counts below are script-counted, not hand-counted).

Covering test files:

- `backend/tests/unit/services/test_database_job_service.py` (DatabaseJobService; 30 tests;
  every query-shape question is dodged because `mock_db_session` — root conftest
  `backend/tests/conftest.py:1930` — is a permissive AsyncMock that never compiles SQL)
- `backend/tests/unit/services/test_job_service.py` (JobService half; mock-tracker style,
  already contains the `assert_called_once_with("test-job-123")` pattern at line 117)

## Why this module survives so loudly

The DatabaseJobService tests drive every query through `AsyncMock` and assert only what the mock
hands back — the mock is a mirror: whatever the test stuffs into
`execute.return_value.X.return_value` comes out of the function unchanged. So every mutation of
the SQL itself (WHERE / ORDER BY / GROUP BY / status lists / cutoff computation / select columns)
is invisible, and every mutation that _breaks_ the query (`stmt = None`, `select(None)`, clause
deleted) never crashes because the mock never compiles it. The one stats test
(`test_database_job_service.py:541`) asserts only `"total_jobs" in stats` — key presence, no
values — while feeding canned results. On top of that, mutmut's string mutations hit log
messages, log `extra` keys, stats response keys and `"epoch"` extract units — display/log text
nothing captures.

## Cluster table (script-counted; sums to 176)

| Cluster | Pattern                                                                                                                                                                                                               | Fn (count)                                                          | N      | Classification | Example keys (prefix `backend.services.job_service.`)                                                |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------ | -------------- | ---------------------------------------------------------------------------------------------------- |
| C1      | Log-message text mutated → `None` / `XX..XX` / case flips                                                                                                                                                             | cancel 4, cleanup 4, complete 4, fail 4, retry 4, start 4, update 4 | **28** | EQUIVALENT     | `xǁDatabaseJobServiceǁcancel_job__mutmut_5`, `.._9`, `.._10`                                         |
| C2      | Log `extra` dict: keys `XX..XX`/UPPER, entry dropped, `extra=None`, extra arg deleted                                                                                                                                 | cancel 6, cleanup 6, complete 6, fail 8, retry 6, start 4, update 6 | **42** | EQUIVALENT     | `xǁDatabaseJobServiceǁstart_job__mutmut_13`, `.._14`, `.._7`                                         |
| C3      | Query-build clobbered — stmt/`select(...)`/where-arg/execute-arg → `None`, select-column removed, whole clause deleted — never compiled under the mock                                                                | get_job_stats 38, cleanup_old_jobs 6, get_active_jobs 4             | **48** | TEST-GAP       | `xǁDatabaseJobServiceǁget_job_stats__mutmut_1`, `.._3`, `xǁ...ǁcleanup_old_jobs__mutmut_19`, `.._22` |
| C4      | Stats result-value mutations: response keys `status`/`count`/`job_type` → `XX..XX`/UPPER, `row[0]`→`row[1]` (label becomes its count), computed value → `None`/`""`                                                   | get_job_stats 16                                                    | **16** | TEST-GAP       | `xǁDatabaseJobServiceǁget_job_stats__mutmut_11`, `.._13`, `.._29`                                    |
| C5      | Predicate operator flipped: `Job.status ==` → `!=` (COMPLETED avg filter, QUEUED oldest filter), `job_type ==` → `!=`, optional-filter `is not None` → `is None`                                                      | get_job_stats 2, get_active_jobs 2                                  | **4**  | TEST-GAP       | `xǁDatabaseJobServiceǁget_job_stats__mutmut_63`, `.._71`, `xǁ...ǁget_active_jobs__mutmut_5`          |
| C6      | Cleanup cutoff-date math: `days` default 30→31, each `.replace(hour/minute/second/microsecond=0)` kwarg dropped or set to 1, `datetime.now(UTC)` → `now(None)`, `cutoff - timedelta` → `+ timedelta`                  | cleanup_old_jobs 11                                                 | **11** | TEST-GAP       | `xǁDatabaseJobServiceǁcleanup_old_jobs__mutmut_1`, `.._7`, `.._17`                                   |
| C7      | `get_active_jobs` order_by shape: `order_by(priority.asc(), created_at.asc())` → single column / arg→`None` / assignment→`None`                                                                                       | get_active_jobs 5                                                   | **5**  | TEST-GAP       | `xǁDatabaseJobServiceǁget_active_jobs__mutmut_10`, `.._12`, `.._13`                                  |
| C8      | Boundary & fallback arithmetic: `completed_at < cutoff` → `<=`; `rowcount or 0` → `or 1` (empty cleanup reports 1 deleted); `scalar() or 0` → `and 0` / `or 1`; avg truthiness guard folded (`and False` / `or True`) | cleanup 2, get_job_stats 4                                          | **6**  | TEST-GAP       | `xǁDatabaseJobServiceǁcleanup_old_jobs__mutmut_26`, `.._31`, `xǁ...ǁget_job_stats__mutmut_39`        |
| C9      | Requested id passed as `None` to tracker lookup — killable with unit mocks                                                                                                                                            | JobService.get_job_or_404 1, get_job_detail 1                       | **2**  | TEST-GAP       | `xǁJobServiceǁget_job_or_404__mutmut_2`, `xǁJobServiceǁget_job_detail__mutmut_2`                     |
| C10     | `get_job_by_id(job_id)` → `get_job_by_id(None)` in lifecycle methods — unit tests stub the lookup's _return_, so the swapped arg is unobservable under mocks                                                          | start/complete/fail/cancel/update_progress/retry 1 each             | **6**  | TEST-GAP       | `xǁDatabaseJobServiceǁstart_job__mutmut_2`, `.._cancel_job__mutmut_2`                                |
| C11     | `func.extract("epoch", col)` literal/arg clobbered (`"EPOCH"`, `"XXepochXX"`, arg→`None`) — never compiled under the mock                                                                                             | get_job_stats 6                                                     | **6**  | EQUIVALENT     | `xǁDatabaseJobServiceǁget_job_stats__mutmut_51`, `.._55`, `.._62`                                    |
| C12     | Log-gate operator on `if deleted_count > 0:` (`>= 0`, `> 1`) — only the cleanup info-log fires                                                                                                                        | cleanup_old_jobs 2                                                  | **2**  | LOW-VALUE      | `xǁDatabaseJobServiceǁcleanup_old_jobs__mutmut_32`, `.._33`                                          |

**Sum: 28+42+48+16+4+11+5+6+2+6+6+2 = 176.**
TEST-GAP 98 (C3–C10) · EQUIVALENT 76 (C1, C2, C11) · LOW-VALUE 2 (C12).

## Cluster judgments

- **C1/C2 (70, EQUIVALENT).** Variants mutate only `logger.*("...", extra={...})` payloads. No
  test in either file uses `caplog`; nothing downstream consumes the message text or extra keys
  (no consumer greps `extra["job_id"]`). Pure log cosmetics → leave surviving or mark no-cover.
- **C11 (6, EQUIVALENT).** `func.extract("EPOCH"/"XXepochXX"/None, ...)` is only ever executed
  against Postgres; the AsyncMock never compiles it, so it survives unit tests. Not truly
  equivalent in prod (the query would error), but unkillable without SQL-shape assertions —
  and T1's compile assertion (below) does kill them anyway, so close EQUIVALENT-under-mocks.
- **C12 (2, LOW-VALUE).** `deleted_count >= 0` logs on an empty cleanup, `> 1` under-logs a
  single-row cleanup. Behavior change exists (an info line), but asserting on it is
  caplog-theater. Leave, or absorb into a future structured-log-contract test.
- **C4 (16, TEST-GAP — highest value in module).** The only stats test
  (`test_database_job_service.py:541`) asserts key _presence_ against a mock whose rows it
  planted. Meanwhile `get_job_stats__mutmut_13` turns `{"status": row[0], "count": row[1]}` into
  `{"status": row[1], "count": row[1]}` — the dashboard would render counts where status names
  belong and no test notices. Value assertions kill this cluster plus most of C3∩stats and C11.
- **C3 (48) / C7 (5) (TEST-GAP).** Tests execute the query-building lines but the built
  statement is never captured/compiled. Kill = compile the `execute` argument and compare
  against a reference query / predicate text. (Covering test: `TestGetActiveJobs`,
  `TestGetJobStats`, `TestCleanupOldJobs`, `test_database_job_service.py:493-685`.)
- **C5 (4) (TEST-GAP).** `==` → `!=` inverts _which jobs_ the avg-duration and oldest-pending
  stats measure; `job_type is None` inverts the optional active-jobs filter (filtered →
  unfiltered and vice versa). Observable only in compiled SQL/params.
- **C6 (11) (TEST-GAP — prod-damage risk).** `cutoff = midnight − timedelta(days)` is the
  retention boundary (CLAUDE.md: Retention 30 days). Tests pass `days=30/7` and assert the mocked
  `rowcount` only — the date math is never asserted, and `-`→`+` (would delete the _newest_
  jobs' predecessors) passes.
- **C8 (6) (TEST-GAP).** `<` vs `<=` boundary-second; `rowcount or 0` → `or 1` makes an empty
  cleanup API-report "1 deleted"; `total or 0` → `and 0` zeroes a nonzero total; avg-guard folds
  turn `float(None)` into a crash on empty data.
- **C9 (2) / C10 (6) (TEST-GAP).** `self.get_job_by_id(job_id)` → `(None)`. C9's functions run
  against a MagicMock tracker — `get_job.assert_called_once_with(id)` kills them in unit style
  (the file already proves this pattern for `get_job` at `test_job_service.py:117`; the 404 /
  detail tests at lines ~211/~572 assert return values only). C10's same one-liner needs the
  real `select(Job).where(Job.id == <arg>)` to run — unit-mock-proof by construction; kill with
  an integration test on the repo's sqlite async-session pattern (draft T5b, in
  `backend/tests/integration/`).

## Drafted tests

All marked **// UNVERIFIED — not yet run red/green**. TDD procedure for each: add the test,
apply that cluster's one-line mutation (or run against the mutants/ copy), see the _new_
assertion FAIL; revert to original source, see it PASS; then re-run `mutmut run` scoped to this
file and confirm the cluster's keys turn non-zero.

File-level import additions for the unit drafts: add `from sqlalchemy import func, select` to
`backend/tests/unit/services/test_database_job_service.py` (it currently imports no sqlalchemy).

### T1 — kills C4 (16), C3∩stats (38), C11 (6) [~60 survivors]

```python
# UNVERIFIED - not yet run red/green
# append to class TestGetJobStats in backend/tests/unit/services/test_database_job_service.py
    @pytest.mark.asyncio
    async def test_get_job_stats_values_and_sql_shape(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Stats values must be derived from query results, and each query must have
        the exact shape the /api/jobs/stats contract relies on."""
        mock_status_result = MagicMock()
        mock_status_result.all.return_value = [("completed", 50), ("running", 5)]
        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [("export", 30)]
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 55
        mock_duration_result = MagicMock()
        mock_duration_result.scalar.return_value = 42.0
        mock_oldest_result = MagicMock()
        mock_oldest_result.scalar.return_value = datetime(2026, 1, 1, tzinfo=UTC)

        mock_db_session.execute.side_effect = [
            mock_status_result,
            mock_type_result,
            mock_total_result,
            mock_duration_result,
            mock_oldest_result,
        ]

        stats = await service.get_job_stats()

        # --- values (kills key/row-index/value clobbers: XXstatusXX, STATUS, row[1]) ---
        assert stats["by_status"] == [
            {"status": "completed", "count": 50},
            {"status": "running", "count": 5},
        ]
        assert stats["by_type"] == [{"job_type": "export", "count": 30}]
        assert stats["total_jobs"] == 55
        assert stats["average_duration_seconds"] == 42.0
        assert stats["oldest_pending_job_age_seconds"] == pytest.approx(
            (datetime.now(UTC) - datetime(2026, 1, 1, tzinfo=UTC)).total_seconds(),
            rel=1e-3,
        )

        # --- compiled SQL shape (kills stmt=None, select(None), column drops, "epoch") ---
        compiled = [call.args[0].compile() for call in mock_db_session.execute.call_args_list]
        assert str(compiled[0]) == str(
            select(Job.status, func.count(Job.id)).group_by(Job.status).compile()
        )
        assert str(compiled[1]) == str(
            select(Job.job_type, func.count(Job.id)).group_by(Job.job_type).compile()
        )
        assert str(compiled[2]) == str(select(func.count(Job.id)).compile())
        assert (
            "EXTRACT(epoch FROM jobs.completed_at) - EXTRACT(epoch FROM jobs.started_at)"
            in str(compiled[3])
        )
        # compile() on a None stmt raises AttributeError -> kills execute(None)/query=None keys

        # --- empty-data fallbacks (kills `or 0`->`or 1`/`and 0`, avg-guard folds) ---
        mock_db_session.execute.side_effect = [
            MagicMock(all=MagicMock(return_value=[])),
            MagicMock(all=MagicMock(return_value=[])),
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=None)),
            MagicMock(scalar=MagicMock(return_value=None)),
        ]
        stats0 = await service.get_job_stats()
        assert stats0["total_jobs"] == 0
        assert stats0["average_duration_seconds"] is None
        assert stats0["oldest_pending_job_age_seconds"] is None
```

`stmt.compile()` output formats verified read-only against this SQLAlchemy version
(`GROUP BY jobs.status`, `EXTRACT(epoch FROM jobs.completed_at) - ...`, `count(jobs.id)`).

### T2 — kills C5 (4) + cleanup/stats predicate-arg mutants inside C3 (6)

```python
# UNVERIFIED - not yet run red/green
# append to backend/tests/unit/services/test_database_job_service.py (new class)
class TestQueryPredicates:
    """WHERE predicates must target the right columns and literals; the mock session
    never compiles SQL, so predicate identity is asserted from the captured statement."""

    @pytest.fixture
    def service(self, mock_db_session: AsyncMock) -> DatabaseJobService:
        return DatabaseJobService(mock_db_session)

    @staticmethod
    def _compiled(mock_db_session: AsyncMock, index: int = 0):
        stmt = mock_db_session.execute.call_args_list[index].args[0]
        return str(stmt.compile()), stmt.compile().params

    @pytest.mark.asyncio
    async def test_get_job_stats_avg_filters_completed_and_oldest_filters_queued(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        mock_db_session.execute.side_effect = [
            MagicMock(all=MagicMock(return_value=[])),
            MagicMock(all=MagicMock(return_value=[])),
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=None)),
            MagicMock(scalar=MagicMock(return_value=None)),
        ]
        await service.get_job_stats()

        avg_sql, avg_params = self._compiled(mock_db_session, 3)
        assert avg_params["status_1"] == JobStatus.COMPLETED.value
        assert "jobs.started_at IS NOT NULL" in avg_sql
        assert "jobs.completed_at IS NOT NULL" in avg_sql

        oldest_sql, oldest_params = self._compiled(mock_db_session, 4)
        assert oldest_params["status_1"] == JobStatus.QUEUED.value
        assert "min(jobs.created_at)" in oldest_sql

    @pytest.mark.asyncio
    async def test_get_active_jobs_optional_type_filter_and_status_scope(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

        await service.get_active_jobs()
        sql, _ = self._compiled(mock_db_session)
        where = sql.split("WHERE", 1)[1]
        assert "jobs.status IN (" in where          # active-status filter present
        assert "jobs.job_type" not in where          # no type filter when not requested

        await service.get_active_jobs(job_type="export")
        sql2, params2 = self._compiled(mock_db_session, 1)
        where2 = sql2.split("WHERE", 1)[1]
        assert "jobs.job_type = :" in where2
        assert params2["job_type_1"] == "export"
        assert "jobs.status IN (" in where2          # status filter survives alongside

    @pytest.mark.asyncio
    async def test_cleanup_targets_finished_statuses_and_age_clause(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        mock_db_session.execute.return_value = MagicMock(rowcount=0)
        await service.cleanup_old_jobs(days=30)

        stmt = mock_db_session.execute.call_args.args[0]
        sql = str(stmt.compile())
        assert sql.startswith("DELETE FROM jobs")
        assert "jobs.completed_at < :" in sql
        lit = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        for status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value):
            assert f"'{status}'" in lit              # kills in_(...)->None / clause-deleted
```

Note (from read-only dialect introspection): `IN_` renders as
`IN (__[POSTCOMPILE_status_1])` on the default dialect and its list does **not** appear in
`params` — hence the `literal_binds` compile for the status list. Adjust only during
red/green; do not weaken to key-presence.

### T3 — kills C6 (11) + C8∩cleanup (2)

```python
# UNVERIFIED - not yet run red/green
# append to class TestCleanupOldJobs in backend/tests/unit/services/test_database_job_service.py
    @pytest.mark.asyncio
    async def test_cleanup_cutoff_is_midnight_minus_days(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Cutoff = today's UTC midnight minus `days`, bound as the DELETE parameter.

        Kills: days default drift, dropped/altered replace() kwargs, naive now(None),
        and `- timedelta` -> `+ timedelta`.
        """
        mock_db_session.execute.return_value = MagicMock(rowcount=0)

        deleted = await service.cleanup_old_jobs(days=30)
        assert deleted == 0  # kills `rowcount or 0` -> `or 1`

        stmt = mock_db_session.execute.call_args.args[0]
        cutoff = stmt.compile().params["completed_at_1"]
        expected = (datetime.now(UTC) - timedelta(days=30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        assert cutoff == expected
        assert "jobs.completed_at < :completed_at_1" in str(stmt.compile())  # strict '<'

        # default retention must remain 30 days (kills `days: int = 31`)
        mock_db_session.execute.reset_mock()
        await service.cleanup_old_jobs()
        cutoff_default = mock_db_session.execute.call_args.args[0].compile().params[
            "completed_at_1"
        ]
        assert cutoff_default == expected
```

`cutoff` param name confirmed via compile introspection (bound as `:completed_at_1`).
`now(None)` yields a naive datetime whose equality against the aware `expected` fails, so the
naive mutants die on the assert rather than crashing.

### T4 — kills C7 (5) + C3∩get_active_jobs (4)

```python
# UNVERIFIED - not yet run red/green
# append to class TestGetActiveJobs in backend/tests/unit/services/test_database_job_service.py
    @pytest.mark.asyncio
    async def test_get_active_jobs_orders_by_priority_then_created_at(
        self, service: DatabaseJobService, mock_db_session: AsyncMock
    ) -> None:
        """Ordering contract: priority ASC, then created_at ASC (oldest queued first)."""
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

        await service.get_active_jobs()

        stmt = mock_db_session.execute.call_args.args[0]
        expected = str(
            select(Job)
            .where(Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]))
            .order_by(Job.priority.asc(), Job.created_at.asc())
            .compile()
        )
        assert str(stmt.compile()) == expected
```

Full-string comparison kills dropped `order_by` args, arg→`None`, single-column forms,
`where(...None)` and `select(None)` in one assertion (rendering verified via read-only
introspection: `ORDER BY jobs.priority ASC, jobs.created_at ASC`).

### T5 — kills C9 (2)

```python
# UNVERIFIED - not yet run red/green
# append to TestJobServiceGetJobOr404 in backend/tests/unit/services/test_job_service.py
    def test_get_job_or_404_looks_up_the_requested_id(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        sample_job_info: JobInfo,
    ) -> None:
        """The tracker must be asked for exactly the id that was requested."""
        mock_job_tracker.get_job.return_value = sample_job_info

        job_service.get_job_or_404("test-job-123")

        mock_job_tracker.get_job.assert_called_once_with("test-job-123")

# append to TestJobServiceGetJobDetail (same file; fixtures job_service /
# mock_job_tracker / sample_job_info already exist at lines 26-43)
    @pytest.mark.asyncio
    async def test_get_job_detail_looks_up_the_requested_id(
        self,
        job_service: JobService,
        mock_job_tracker: MagicMock,
        sample_job_info: JobInfo,
    ) -> None:
        mock_job_tracker.get_job.return_value = sample_job_info

        await job_service.get_job_detail("test-job-123")

        mock_job_tracker.get_job.assert_called_once_with("test-job-123")
```

### T5b — kills C10 (6) — integration skeleton

```python
# UNVERIFIED - not yet run red/green
# backend/tests/integration/services/test_database_job_service_lookup.py
# Use whatever AsyncSession-over-sqlite fixture backend/tests/integration/ already uses
# (mirror an existing integration test's fixture import at red/green time).
@pytest.mark.asyncio
async def test_lifecycle_methods_act_on_the_requested_job_only(session) -> None:
    """get_job_by_id(None) must resolve nothing, so acting on job A must never
    mutate job B — kills get_job_by_id(job_id) -> get_job_by_id(None) clobbers
    that unit mocks structurally cannot see."""
    service = DatabaseJobService(session)
    await service.create_job("export", job_id="job-a")
    await service.create_job("export", job_id="job-b")
    await session.commit()

    started = await service.start_job("job-a")
    await session.commit()
    assert started is not None and started.id == "job-a"
    assert started.status == JobStatus.RUNNING.value

    fresh_b = await service.get_job_by_id("job-b")
    assert fresh_b is not None
    assert fresh_b.status == JobStatus.QUEUED.value  # B untouched -> arg-clobbers die here
```

## Recommended kill order (value per effort)

1. **T1** — one test, ~60 survivors die (stats values + SQL shape + epoch literals).
2. **T2 + T4** — compile/param assertions on predicates and ordering: ~19 more.
3. **T3** — retention-boundary math, the worst latent prod bug here: 13 more.
4. **T5** — two 6-line unit tests: 2 more.
5. **T5b** — integration, one test: 6 more.
6. **Close-out**: C1+C2 (70) EQUIVALENT, C11 (6) EQUIVALENT-under-mocks, C12 (2) LOW-VALUE —
   mark in the baseline so the module's kill ratio reflects the 98 real gaps, not log text.
