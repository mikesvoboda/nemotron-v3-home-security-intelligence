# WP4.4 triage dossier — `backend/api/routes/jobs.py`

**Wave**: read-only triage of SURVIVING mutants (WP4.3 feed). UNVERIFIED — no test was run
(no pytest, no `mutmut run`). Diffs confirmed by two independent paths: per-variant diff of
`mutants/backend/api/routes/jobs.py` blocks (via `jobs.py.spans`) against the original, and
`uv run mutmut show <key>` cross-check on `__mutmut_5` (matched exactly).

## Census

| Fact | Value |
| --- | --- |
| meta keys total | 25 |
| `exit_code == 0` (SURVIVED) | **25** |
| `exit_code == null` (unchecked) | 0 |
| killed | 0 |
| functions with generated mutants | 1 — `x_run_export_job` (`hash_by_function_name` has a single entry) |
| module kill rate in this run | 0/25 = 0.0% |

All 25 survivors are argument-level mutants of the three `job_tracker` / `export_service` calls
inside `run_export_job` (`backend/api/routes/jobs.py:989-1031`). `jobs.py`'s 13 other route
functions produced no mutants in this cache — this module's survivor list *is* its entire
generated mutant set, so it is a 0%-coverage module, not a partially-covered one.

**Harness observation (out of census, flag for WP4.3):** the `except` branch line
`job_tracker.fail_job(job_id, str(e))` (`jobs.py:1031`) generated **zero** mutants — no
`fail_job(None, ...)` / `fail_job(job_id, None)` variant exists. `start_job` and `complete_job`
each generated 4 argument mutants. If the except block is being skipped by the mutator, every
`fail_job` call site in the baseline is unmutatable and the module's true denominator is larger
than 25.

## Covering tests (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`)

`backend.api.routes.jobs.x_run_export_job` is credited with exactly 4 tests, all in
`backend/tests/unit/api/routes/test_jobs.py`:

| Test | file:line | what it asserts |
| --- | --- | --- |
| `TestStartExportJob::test_start_export_job_csv` | `backend/tests/unit/api/routes/test_jobs.py:639` | 202, `job_id`, `status == "pending"`, `"GET /api/jobs" in message` |
| `TestStartExportJob::test_start_export_job_json` | `.../test_jobs.py:654` | 202, `job_id` |
| `TestStartExportJob::test_start_export_job_zip` | `.../test_jobs.py:667` | 202, `job_id` |
| `TestStartExportJob::test_start_export_job_with_filters` | `.../test_jobs.py:680` | 202, `job_id` — **sends all 5 filters and asserts nothing about them** |

These tests hit `POST /api/events/export`, so `TestClient` runs the scheduled background task and
`run_export_job`'s body *does* execute (that is why the lines are covered) — but under
`MagicMock(spec=JobTracker)` + `MagicMock` export service (`.../test_jobs.py:16-29`) every mutated
call still "succeeds" and **no assertion inspects any call argument or job state**. The fifth test
in the module that mentions this function is a placeholder that asserts only
`callable(run_export_job)` and `run_export_job.__name__`
(`backend/tests/unit/api/routes/test_jobs.py:1441-1456`, `TestRunExportJob::test_run_export_job_covered_by_integration_tests`)
— its docstring defers coverage to integration tests.

The integration tests it defers to are equally blind:
`backend/tests/integration/test_jobs.py:223-270` assert only 202 + key presence;
`:288-318` (`test_job_lifecycle_stages`) asserts `status in ("pending","running","completed","failed")`
— a set that any mis-addressed job_id, dropped filter, or `export_format=None` failure still lands in;
`:322-342` asserts `0 <= progress <= 100`. Nothing compares the job's id, message, result, or the
service's kwargs.

**Why the 4 mocks cannot kill anything (mechanism, per cluster):** `MagicMock(spec=JobTracker)`
accepts *any* argument list — `start_job(None, ...)`, `complete_job(None, ...)`, `start_job(message=...)`
(missing `job_id`) all return a MagicMock instead of raising the `KeyError`/`TypeError` a real tracker
raises (`backend/services/job_tracker.py:349-350, 451-452`). The fix is to drive these tests with a
**real `JobTracker()`** (hermetic: `_schedule_persist` returns early with `redis_client=None`
`job_tracker.py:236-237`; `_broadcast` returns with no callback `job_tracker.py:169-170`) and assert
job *end state* — then every mis-addressed id turns the job FAILED all by itself.

## Cluster table (counts sum to 25)

| # | Cluster (pattern) | keys | n | Classification | drafted test |
| --- | --- | --- | --- | --- | --- |
| J1 | background task runs the export service with this job's identity + format (call deleted / `job_id`/`job_tracker`/`export_format` → `None` or kwarg dropped) | `...__mutmut_5`, `_6`, `_7`, `_8`, `_14`, `_15`, `_16` | 7 | TEST-GAP | T2 |
| J2 | user-supplied export filters are forwarded to the export service (`camera_id`/`risk_level`/`start_date`/`end_date`/`reviewed` → `None` or kwarg dropped) | `_9`, `_10`, `_11`, `_12`, `_13`, `_17`, `_18`, `_19`, `_20`, `_21` | 10 | TEST-GAP | T1 |
| J3 | job is addressed on completion (`complete_job(None, …)`, `job_id` kwarg dropped, `result=` dropped) | `_22`, `_23`, `_24`, `_25` | 4 | TEST-GAP | T4 |
| J4 | job is addressed + status-messaged on start (`start_job(None, …)`, `job_id` dropped, `message` → `None`/dropped) | `_1`, `_2`, `_3`, `_4` | 4 | TEST-GAP | T3 |
| **total** | | | **25** | | |

All keys abbreviated from `backend.api.routes.jobs.x_run_export_job__mutmut_N`.

### Cluster detail

**J1 (7) — TEST-GAP, highest blast radius.** `_5` deletes the whole `await
export_service.export_events_with_progress(...)` call (`jobs.py:1016-1025`) and substitutes
`result = None`: the job then reports **COMPLETED with an empty result having exported nothing** —
the worst failure shape in the module, and it passes every existing assertion including the
integration lifecycle test. `_6` (`job_id=None`) / `_14` (dropped) send progress updates to a
non-existent job id (real service: `job_tracker.update_progress(None, …)` → `KeyError`,
`export_service.py:795`); `_7` (`job_tracker=None`) / `_15` (dropped) strip the progress channel
entirely (`export_service.py:725` requires it); `_8` (`export_format=None`) / `_16` (dropped) hit
the format dispatch fallthrough `raise ValueError(f"Unsupported export format: {export_format}")`
(`export_service.py:871`). Nothing asserts `export_events_with_progress` was called, or with what.

**J2 (10) — TEST-GAP, data-correctness class.** Each of the five filters is either `None`-ed
(`_9`…`_13`) or its kwarg deleted (`_17`…`_21`, `_21` deletes `reviewed=` with the re-indented
closing paren). The service applies these only when non-None (`export_service.py:768-787`), so every
mutant silently exports the **entire event history instead of the requested subset** — a user asking
for `camera_id="cam-1"` receives every camera's events. `test_start_export_job_with_filters`
(`test_jobs.py:680`) posts all five filters and asserts only the job id, so the mutation path is
exactly the untested one.

**J3 (4) — TEST-GAP.** `_22` (`complete_job(None, …)`) and `_24` (`job_id` kwarg dropped) make
completion target the wrong/nonexistent job — real tracker raises `KeyError`
(`job_tracker.py:451-452`), which the broad `except Exception` (`jobs.py:1029`) swallows into
`fail_job`, so the job ends FAILED after a successful export. `_23` and `_25` drop the `result`
payload (`result=None`): `frontend/src/components/jobs/JobDetailPanel.tsx:260-264` renders
`job.result` (and the `JOB_COMPLETED` broadcast carries it, `job_tracker.py:469-477`), so the UI
shows a completed export with no file to open.

**J4 (4) — TEST-GAP.** `_1` (`start_job(None, …)`) and `_3` (`job_id` kwarg dropped → `TypeError`,
`job_tracker.py:335`) prevent the pending → running transition, so the job stays PENDING through a
running export (and `_1`/`_3` end FAILED via the swallowed exception). `_2`/`_4` drop the status
message: `create_job` initialises `message=None` (`job_tracker.py:316`) and `start_job` only writes
it when non-None (`job_tracker.py:354-355`), so `JobsListItem.tsx:148` renders no status line at all.
Message-only mutants are the weakest of the four sub-classes (user-visible status text, not data
correctness), but they are still asserted nowhere and the same test kills them for free.

No cluster classifies as EQUIVALENT (no pure log-text or dead-defensive mutations) or LOW-VALUE
(no debug hooks; every mutation changes what the export actually contains, which job it is
attributed to, or whether it runs at all).

## Drafted tests — UNVERIFIED, not yet run red/green

Target file: `backend/tests/unit/api/routes/test_jobs.py` (append a new class; existing fixtures
`mock_export_service` at `:23-29` and module-level imports of `JobStatus`, `JobTracker` at `:13`
are reused). `asyncio_mode = "auto"` (`pyproject.toml:492`) plus the registered `asyncio` marker
(`:508`) — the `@pytest.mark.asyncio` decorator matches sibling style in
`backend/tests/unit/api/routes/test_exports.py:226`.

```python
class TestRunExportJobTask:
    """Direct unit tests for the run_export_job background task.

    WP4.4: the HTTP-level TestStartExportJob tests execute this coroutine under a
    MagicMock tracker, so no argument mutation of start_job/export_events_with_progress/
    complete_job can fail them. These tests drive the task with a REAL JobTracker
    (hermetic without a redis client or broadcast callback) so a mis-addressed job id
    surfaces as a wrong end state instead of a silent MagicMock return.
    """

    @pytest.mark.asyncio
    async def test_run_export_job_passes_filters_through_to_export_service(
        self, mock_export_service: MagicMock
    ) -> None:
        """Should forward every request filter to export_events_with_progress.

        TDD: fails on J2 mutants (_9-_13, _17-_21) — a None-ed filter breaks the
        equality assert, a dropped kwarg raises KeyError on call_args.kwargs —
        passes on original.
        """
        from backend.api.routes.jobs import run_export_job
        from backend.api.schemas.jobs import ExportFormat
        from backend.services.job_tracker import JobTracker

        tracker = JobTracker()
        job_id = tracker.create_job("export")
        expected = {"file_path": "/api/exports/jobs.csv", "event_count": 3}
        # Snapshot nothing here; just let the payload flow through to complete_job.
        mock_export_service.export_events_with_progress.side_effect = (
            lambda **kwargs: expected
        )

        await run_export_job(
            job_id=job_id,
            export_format=ExportFormat.CSV,
            camera_id="cam-1",
            risk_level="high",
            start_date="2024-01-01T00:00:00+00:00",
            end_date="2024-01-15T23:59:59+00:00",
            reviewed=True,
            export_service=mock_export_service,
            job_tracker=tracker,
        )

        kwargs = mock_export_service.export_events_with_progress.call_args.kwargs
        assert kwargs["camera_id"] == "cam-1"
        assert kwargs["risk_level"] == "high"
        assert kwargs["start_date"] == "2024-01-01T00:00:00+00:00"
        assert kwargs["end_date"] == "2024-01-15T23:59:59+00:00"
        assert kwargs["reviewed"] is True

    @pytest.mark.asyncio
    async def test_run_export_job_runs_export_with_this_job_identity(
        self, mock_export_service: MagicMock
    ) -> None:
        """Should run the export exactly once, bound to this job id and tracker.

        TDD: fails on J1 mutants — _5 never calls the service (assert_called_once),
        _6/_14 mis-set job_id, _7/_15 lose the tracker, _8/_16 lose the format —
        passes on original.
        """
        from backend.api.routes.jobs import run_export_job
        from backend.api.schemas.jobs import ExportFormat
        from backend.services.job_tracker import JobStatus, JobTracker

        tracker = JobTracker()
        job_id = tracker.create_job("export")
        expected = {"file_path": "/api/exports/jobs.csv", "event_count": 3}
        mock_export_service.export_events_with_progress.return_value = expected

        await run_export_job(
            job_id=job_id,
            export_format=ExportFormat.CSV,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            export_service=mock_export_service,
            job_tracker=tracker,
        )

        mock_export_service.export_events_with_progress.assert_called_once()
        kwargs = mock_export_service.export_events_with_progress.call_args.kwargs
        assert kwargs["job_id"] == job_id
        assert kwargs["job_tracker"] is tracker
        assert kwargs["export_format"] == "csv"

        info = tracker.get_job(job_id)
        assert info is not None
        assert info["status"] == JobStatus.COMPLETED
        assert info["result"] == expected

    @pytest.mark.asyncio
    async def test_run_export_job_marks_job_running_while_exporting(
        self, mock_export_service: MagicMock
    ) -> None:
        """Should transition this job to running with a starting message pre-export.

        TDD: fails on J4 mutants — _1/_3 never reach RUNNING (the swallowed
        KeyError/TypeError leaves the job PENDING-or-failed), _2/_4 leave message
        None — passes on original.
        """
        from backend.api.routes.jobs import run_export_job
        from backend.api.schemas.jobs import ExportFormat
        from backend.services.job_tracker import JobStatus, JobTracker

        tracker = JobTracker()
        job_id = tracker.create_job("export")
        seen: list[tuple[object, object]] = []

        def snapshot(**kwargs):  # runs while the export is in flight
            info = tracker.get_job(job_id)
            seen.append((info["status"] if info else None, info["message"] if info else None))
            return {"file_path": "/api/exports/jobs.csv", "event_count": 0}

        mock_export_service.export_events_with_progress.side_effect = snapshot

        await run_export_job(
            job_id=job_id,
            export_format=ExportFormat.CSV,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            export_service=mock_export_service,
            job_tracker=tracker,
        )

        assert seen == [(JobStatus.RUNNING, "Starting csv export...")]

    @pytest.mark.asyncio
    async def test_run_export_job_completes_this_job_with_the_export_result(
        self, mock_export_service: MagicMock
    ) -> None:
        """Should complete this job id carrying the service result payload.

        TDD: fails on J3 mutants — _22/_24 mis-address completion so the job ends
        FAILED/uncompleted, _23/_25 drop the result — passes on original.
        """
        from backend.api.routes.jobs import run_export_job
        from backend.api.schemas.jobs import ExportFormat
        from backend.services.job_tracker import JobStatus, JobTracker

        tracker = JobTracker()
        job_id = tracker.create_job("export")
        expected = {
            "file_path": "/api/exports/jobs.csv",
            "file_size": 12345,
            "event_count": 7,
            "format": "csv",
        }
        mock_export_service.export_events_with_progress.return_value = expected

        await run_export_job(
            job_id=job_id,
            export_format=ExportFormat.CSV,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            export_service=mock_export_service,
            job_tracker=tracker,
        )

        info = tracker.get_job(job_id)
        assert info is not None
        assert info["status"] == JobStatus.COMPLETED
        assert info["error"] is None
        assert info["result"] == expected
        assert info["started_at"] is not None
        assert info["completed_at"] is not None
```

Kill map (STRICT expectation, unverified): T1 → J2 (10); T2 → J1 (7), also `_22`/`_24` via the
`COMPLETED` end-state check; T3 → J4 (4); T4 → J3 (4). All 25 survivors have at least one killer.

Preconditions to check when the serial pytest lane is free (per memory `mutants-tree-test-sync-trap`):
run these against the **pristine** tree first for green, then re-verify kills in `mutants/` with the
touched test file synced into the mutants tree, or the census silently records 0 kills.

Secondary notes for whoever lands the fix:
- `mock_export_service` (`test_jobs.py:23-29`) is the shared blind spot — consider also converting
  `TestStartExportJob` to a real tracker so the endpoint-level tests stop masking future call-site
  mutations in `start_export_job` (`jobs.py:1044-1094`).
- `JobStatus` is a `StrEnum` with `auto()` (`job_tracker.py:48-54`), so compare against the enum
  member, never a string literal, to stay immune to value churn.
- `ExportFormat` is a `StrEnum` (`backend/api/schemas/jobs.py:249-254`), so
  `assert kwargs["export_format"] == "csv"` is true on the original and false for `None` — no need
  to import the member for the comparison, though T2 imports it for the call itself.
