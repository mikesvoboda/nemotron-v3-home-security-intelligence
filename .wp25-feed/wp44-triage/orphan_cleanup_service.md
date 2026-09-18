# WP4.4 Triage Dossier — backend/services/orphan_cleanup_service.py

- **Run**: WP4.3 surviving-mutant feed (meta: `mutants/backend/services/orphan_cleanup_service.py.meta`, read 2026-09-18)
- **Keys**: 371 total → **170 SURVIVED** (exit_code 0), 132 killed, 69 unchecked (ignored)
- **Diff source**: `uv run mutmut show <key>` for all 170 keys (fast path, ~0.6 s each; no cache contention hit). No test execution, no repo writes.
- **Covering test file (every surviving function)**: `backend/tests/unit/services/test_orphan_cleanup_service.py` (1385 lines, `pytestmark = pytest.mark.unit`; per `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`, module prefix `backend.services.orphan_cleanup_service.`)
- **Partition check**: 26 clusters, counts sum to exactly 170, no key in two clusters (script-verified against the survivor set).

## Verdict roll-up

| Classification | Survivors | Share |
|---|---|---|
| EQUIVALENT | 87 | 51% — all log-message/log-payload text + equivalence-under-the-mock DB query mutants + 2 true-language equivalents |
| TEST-GAP | 68 | 40% — job-tracker plumbing, progress %, stats totals, loop cadence, orphan-query fidelity, singleton plumbing, age arithmetic |
| LOW-VALUE | 15 | 9% — human-readable job message text, one cosmetic log-skip, one dead-fallback arg |

**Root cause pattern**: the module's tests mock *at the wrong granularity* — job tracker verified with `assert_called_once()` only, DB session mocked to return the same canned scalar for any query, `asyncio.sleep` mocked with the argument unread, counters asserted `>= 1` on single-file fixtures. Fixing this is 6 drafted tests (below), all additions to the existing file, no repo-wide fixture work.

## Cluster table

Example keys are abbreviated to `func#mutmut_idx`; full key = `backend.services.orphan_cleanup_service.xǁOrphanedFileCleanupServiceǁ<func>__mutmut_<idx>` (singleton fn: `x_get_orphan_cleanup_service__mutmut_<idx>`). Test-file lines refer to `backend/tests/unit/services/test_orphan_cleanup_service.py`.

| # | Count | Class | Pattern (function — mutation) | Example keys | Why |
|---|---|---|---|---|---|
| C1 | 28 | EQUIVALENT | start()/stop() — logger message literal → None / case-flip / XX-wrap (start 1-4,6-13,18-21; stop 2-5,6-9,14-17) | start#1, start#13, stop#9 | Only the string passed to logger changes. All 16 start/stop mutants that touched guards/create_task were killed — lifecycle logic is already tight. |
| C2 | 17 | EQUIVALENT | _cleanup_loop — logger messages + `exc_info=True` → None/False/dropped (loop 1-4,8,10-13,15,16,18,19,22-25) | loop#1, loop#16, loop#25 | Log-record content only; no loop-contract change lives in this cluster (cadence mutants are C19/C20). |
| C3 | 11 | EQUIVALENT | _broadcast — failure-path `logger.warning` message + `extra{}` key/value text (broadcast 11,12,14-22) | broadcast#15, broadcast#19 | Callback invocation untouched; log payload keys only. |
| C4 | 11 | EQUIVALENT | run_cleanup — logger message literals + `exc_info` (run 12,16-19,61,62,69,70,72,73) | run#17, run#70 | Stats/progress/tracker calls untouched by these keys. |
| C5 | 8 | EQUIVALENT | Leaf helpers — `logger.debug/warning/error(<f-string>)` → `(None)` (_is_orphan 4,13,22,25; _is_file_old_enough 8; _delete_file 5,7; _check_file_not_in_database 7) | _is_orphan#13, _delete_file#5 | Return values unchanged. |
| C6 | 11 | **TEST-GAP** | **Job-tracker identity lost** — `create_job(None)`, `start_job(None,…)`, id-dropped forms, `complete_job(None,…)`, `update_progress(None,…)`/`(progress,…)`, `fail_job(None,…)` (run 4,5,7,21,23,35,38,64,66,75,77) | run#4, run#21, run#75 | `TestJobTrackerIntegration` (:686-689) and progress test (:1300) use bare `assert_called_once()`/`call_count` — never the job_id the work is attributed to, never the `"orphan_cleanup"` job-type constant. A tracker bug that logs progress against the wrong job passes CI. **Killed by draft T1.** |
| C7 | 4 | **TEST-GAP** | **`complete_job(result=None)` / result kwarg dropped** on empty-run and normal paths (run 22,24,65,67) | run#22, run#65 | Acceptance criterion "Reports cleanup statistics via job tracking system" is entirely unasserted — tests only check `complete_job` was called. **Killed by draft T1.** |
| C8 | 4 | **TEST-GAP** | **Guard `if self._job_tracker and job_id:` → `or`** at all four call sites (run 20,27,63,74) | run#20, run#63 | Invisible behind `MagicMock(create_job→"test-job-id")` (truthy). With a tracker returning a falsy id, original skips tracker calls; mutant fires `start/complete/fail_job(None,…)`. Real safety logic (never call the tracker for a job that was never created). **Killed by draft T2.** |
| C9 | 7 | **TEST-GAP** | **Progress % arithmetic** `int((i+1)/len(files)*90)` → `/90`, `*91`, `(i-1)`, `(i+2)`, `*len(files)`, `None`, progress→None arg (run 28,30-34,36) | run#30, run#33 | :1300 asserts only `call_count >= 3` — never the percentage, never the 0..90 bound ("Reserve 10% for cleanup"). `*91` lets progress exceed 90; `/90` pins it to 0. **Killed by draft T1** (exact `call_args_list`). |
| C10 | 13 | LOW-VALUE | Human-readable job message text / cosmetic call shape — `message=` f-string index tweaks, message/reason kwarg dropped/None/case (run 6,8-11,37,39-42,76,78,79) | run#9, run#41, run#76 | Operator-facing job log text; nothing depends on it programmatically. Full-signature asserts in T1 kill these as collateral — do not write a dedicated test. |
| C11 | 8 | **TEST-GAP** | **Stats accumulators `+=` → `=1` / `+=2`; `space_reclaimed = size` / `-= size`** (run 45,47,51,53,56,58,59,60) | run#59, run#60 | `space_reclaimed` reported to the job result + broadcast would be wrong (or negative with `-=`). Every existing assert is `>= 1` / `== 0` on single-file fixtures (:582-585, :615, :650, :1341) — no mutant can fire. **Killed by draft T4.** |
| C12 | 1 | **TEST-GAP** | **`continue` → `break`** in per-file loop (run 48) | run#48 | One too-young file silently aborts the whole scan — every later orphan is never deleted. `test_run_cleanup_respects_age_threshold` (:588) uses a single young file, so break ≡ continue there. **Killed by draft T4** (5 files, 2 young). |
| C13 | 2 | **TEST-GAP** | **File-path argument lost on orphan DB lookup** — `_is_orphan(str(None))`, `_check_file_not_in_database(None)` (run 50, _is_orphan 5) | run#50, _is_orphan#5 | `events.clip_path` then matches the string `"None"`: **live, DB-referenced files classify as orphans and are deleted.** All existing DB mocks return one canned scalar for any query, so nothing notices. **Killed by draft T3b.** |
| C14 | 3 | **TEST-GAP** | **ORM `==` → `!=`** inside orphan queries: `Event.id == event_id`, `Event.clip_path == file_path` (×2 + CFD) (_is_orphan 10,19; _check_file_not_in_database 5) | _is_orphan#10, _check#5 | Deletes exactly the files that DO have DB records. No test reads the generated SQL. **Killed by draft T3a.** |
| C15 | 9 | EQUIVALENT | **Query object gutted** — `execute(None)`, `where(None)`, `select(None)` (_is_orphan 7,8,9,16,17,18; _check_file_not_in_database 2,3,4) | _is_orphan#7, _check#3 | Verified against the pinned SQLAlchemy: `select(None)` → `SELECT NULL AS anon_1`, `where(None)` → `WHERE NULL`, `execute(None)` builds fine — no exception, the AsyncMock session still returns the canned scalar → green (equivalent-*under-mock*). Not equivalent in production (bind error → broad except → "never delete anything"). Classified honestly; draft T3a kills all nine via SQL-text inspection anyway. |
| C16 | 12 | **TEST-GAP** | **Singleton ignores every caller argument** — each kwarg of `get_orphan_cleanup_service(…)` forwarded as `None` or dropped (x_get_orphan_cleanup_service 3-14) | gs#3, gs#6, gs#14 | Both `TestSingleton` tests (:941-970) call the factory with zero arguments. Misplumbing is *permanent* — later calls return the cached instance. In prod `main.py`-style callers pass real trackers/dirs. **Killed by draft T5.** |
| C17 | 2 | **TEST-GAP** | **Age unit arithmetic** `(now - mtime)/3600` → `*3600` / `/3601` (_is_file_old_enough 3,6) | _age#3, _age#6 | `*3600` is the worst mutant in the module: a **1-second-old file computes as ~86,400 "hours" old and is deleted immediately**. Existing tests use wide margins (2 h vs 1 h; just-created vs 24 h) at :318-359. `/3601` = 0.03% age shrink → boundary flapping. **Killed by draft T6.** |
| C18 | 1 | **TEST-GAP** | **Age comparison `>=` → `>`** (exact-threshold boundary) (_is_file_old_enough 7) | _age#7 | A file exactly `age_threshold_hours` old becomes permanently undeletable. Needs a frozen clock to pin (live re-read of `now()` between fixture and call makes a live-clock boundary test flaky — see draft T6). |
| C19 | 4 | **TEST-GAP** | **Loop cadence arithmetic** — `wait_seconds = interval*3600` → `None` / `/3600` / `*3601`; error-retry `sleep(60)` → `sleep(61)` (loop 5,6,7,21) | loop#6, loop#21 | Both loop tests (:871-875, :923-927) patch `asyncio.sleep` with `AsyncMock` and never read the argument. `/3600` turns a 24 h cadence into 0.0003 s → constant full cleanup scans. **Killed by draft T7.** |
| C20 | 2 | **TEST-GAP** | **`asyncio.sleep(None)`** on normal wait + error retry (loop 9,20) | loop#9, loop#20 | `TypeError` under a real loop → production loop spins forever on the 60 s retry path. Silent only because sleep is mocked. Draft T7's `call_args_list` assert kills these with the same code as C19. |
| C21 | 1 | LOW-VALUE | `break` → `return` in CancelledError handler (loop 14) | loop#14 | Only the trailing "loop stopped" info log is lost; function exits either way. |
| C22 | 1 | LOW-VALUE | `asyncio.run(None)` on no-running-loop broadcast fallback (broadcast 10) | broadcast#10 | Existing test (:1244-1249) asserts `mock_asyncio_run.assert_called_once()` without checking the awaitable. Optional one-line add-on shown under draft T8. |
| C23 | 7 | **TEST-GAP** | **Broadcast envelope payload** — `"type"` → `XXtypeXX`/`TYPE`, event value case-flip, `"timestamp"` → `XXtimestampXX`/`TIMESTAMP`, `now(UTC)` → `now(None)` (naive) (_broadcast_completion 7,8,9,10,15,16,17) | bcast_c#9, bcast_c#17 | WebSocket tests assert only outer `event_type` + `"stats" in data` (:746-749, :1221-1223). The `type` discriminator a client switches on and the tz-aware timestamp the UI renders are unasserted. **Killed by draft T8** (extends an existing test, +5 lines). |
| C24 | 1 | EQUIVALENT | Regex literal case-flip `r"event[_-]?(\d+)"` → `r"EVENT…"`, `re.IGNORECASE` still passed (_extract_event_id_from_path 12) | _extract#12 | Accepted language identical. Not killable without source inspection — do not chase. |
| C25 | 1 | EQUIVALENT | Annotated local default `job_id: str \| None = None` → `""` (run 2) | run#2 | `""` and `None` are indistinguishable at the `and job_id` guards and create_job overwrites it whenever a tracker exists. |
| C26 | 1 | EQUIVALENT | `datetime.now(UTC)` → `datetime.now(None)` on the age computation (_is_file_old_enough 5) | _age#5 | `datetime.now(None).timestamp() == datetime.now(UTC).timestamp()` in every timezone (a naive local reading converted back to epoch is the same instant — verified locally; the line is only used via `.timestamp()`). Truly unkillable by behavior; style-only nit. |

Sum: 28+17+11+11+8+11+4+4+7+13+8+1+2+3+9+12+2+1+4+2+1+1+7+1+1+1 = **170**. EQUIVALENT 87 + TEST-GAP 68 + LOW-VALUE 15 = 170.

## Drafted tests

All target the existing file `backend/tests/unit/services/test_orphan_cleanup_service.py`; they follow its style (local imports in body, `contextlib.asynccontextmanager` `mock_get_session`, `AsyncMock` session, `@pytest.mark.asyncio`, Given/When/Then docstrings). New classes append at end of file.

Add to the file's top-level imports: `from unittest.mock import AsyncMock, MagicMock, patch` already present — extend with `call`; add `timedelta` to the `datetime` import.

**TDD procedure (one line, applies to every draft below): run the draft against the mutant copy (`uv run pytest backend/tests/unit/services/test_orphan_cleanup_service.py -k <new_test>` with the module swapped for the clobbered variant) → assert fails on the mutant diff; run against `backend/services/orphan_cleanup_service.py` → passes.**

// UNVERIFIED - not yet run red/green (WP4.3 run owns the machine; no test executed during triage)

### T1 — exact job-tracker call signatures (kills C6 + C7 + C9, 22 survivors; collaterally the 13 C10 message-text mutants)

```python
class TestJobTrackerCallFidelity:
    """Job tracker must be told WHICH job, the job TYPE, the progress PERCENT
    and the stats RESULT - not merely that each method fired once."""

    @pytest.mark.asyncio
    async def test_run_cleanup_reports_exact_job_tracker_calls(self, tmp_path, mock_job_tracker):
        """Given 3 old orphan clips and a tracker
        When run_cleanup completes
        Then every tracker call carries the real job id, job type, exact progress
        percentages and the exact stats dict."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        for i in range(3):  # 3 old orphan files, 6 bytes each -> 18 bytes total
            f = tmp_path / f"event_{i}.mp4"
            f.write_text(f"test {i}")
            old_time = datetime.now().timestamp() - (48 * 3600)
            os.utime(f, (old_time, old_time))

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path),
            age_threshold_hours=24,
            job_tracker=mock_job_tracker,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # every file is an orphan
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            await service.run_cleanup()

        # Which job, and what kind of job (kills create_job(None))
        mock_job_tracker.create_job.assert_called_once_with("orphan_cleanup")
        # Started against the real job id (kills start_job(None, ...) / id-dropped forms)
        mock_job_tracker.start_job.assert_called_once_with(
            "test-job-id", message="Starting orphan cleanup scan"
        )
        # Progress: int((i+1)/len * 90) -> exactly 30, 60, 90 against the real job id.
        # Kills /90 (all 0), *91 (91), (i-1) (0,30,60), (i+2) (60,90,120),
        # *len(files) (270...), None, and the id-less call shapes.
        assert mock_job_tracker.update_progress.call_args_list == [
            call("test-job-id", 30, message="Checking file 1/3"),
            call("test-job-id", 60, message="Checking file 2/3"),
            call("test-job-id", 90, message="Checking file 3/3"),
        ]
        # Completion carries job id AND the stats payload (kills result=None / dropped)
        mock_job_tracker.complete_job.assert_called_once_with(
            "test-job-id",
            result={
                "files_scanned": 3,
                "orphans_found": 3,
                "files_deleted": 3,
                "files_skipped_young": 0,
                "space_reclaimed": 18,
            },
        )
        mock_job_tracker.fail_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_cleanup_fails_job_with_id_and_reason(self, mock_job_tracker):
        """Given scan raises
        When run_cleanup propagates the error
        Then fail_job gets the real job id and the error message."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(
            clips_directory="/some/path", job_tracker=mock_job_tracker
        )
        with patch.object(
            service, "_scan_clip_files", side_effect=Exception("Test error"), autospec=True
        ):
            with pytest.raises(Exception, match="Test error"):
                await service.run_cleanup()

        # Kills fail_job(None, ...), fail_job(str(e)), reason None / str(None) / dropped
        mock_job_tracker.fail_job.assert_called_once_with("test-job-id", "Test error")
```

### T2 — falsy job id must silence tracker calls (kills C8, 4 survivors: run 20/27/63/74)

```python
class TestJobGuardSemantics:
    """`if self._job_tracker and job_id` guards exist so a job that was never
    created is never started/completed/failed. Mock-tracker truthiness hides it."""

    @pytest.mark.asyncio
    async def test_run_cleanup_skips_tracker_calls_when_job_id_is_falsy(
        self, tmp_path, mock_job_tracker
    ):
        """Given a tracker whose create_job returns None (falsy job id)
        When run_cleanup runs empty / normal / failing scans
        Then no start/update/complete/fail call is made with the bogus id."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        mock_job_tracker.create_job = MagicMock(return_value=None)  # job id is falsy
        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path), job_tracker=mock_job_tracker
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            # Phase 1: empty directory -> empty-run completion guard (run#20)
            await service.run_cleanup()
            # Phase 2: one old orphan -> per-file guard (run#27) + completion guard (run#63)
            old = tmp_path / "old_clip.mp4"
            old.write_text("old")
            old_time = datetime.now().timestamp() - (48 * 3600)
            os.utime(old, (old_time, old_time))
            await service.run_cleanup()

        # Original skips every call (job_id falsy); `or` mutants would call with None.
        mock_job_tracker.update_progress.assert_not_called()
        mock_job_tracker.complete_job.assert_not_called()

        # Phase 3: critical failure -> fail-job guard (run#74)
        service2 = OrphanedFileCleanupService(
            clips_directory="/some/path", job_tracker=mock_job_tracker
        )
        with patch.object(
            service2, "_scan_clip_files", side_effect=Exception("boom"), autospec=True
        ):
            with pytest.raises(Exception, match="boom"):
                await service2.run_cleanup()
        mock_job_tracker.fail_job.assert_not_called()
```

### T3 — orphan-query fidelity (kills C14 + C13, 5 survivors; T3a also kills the 9 C15 equivalent-under-mock keys)

```python
class TestOrphanQueryFidelity:
    """_is_orphan runs two SELECTs whose WHERE columns/values ARE the safety of
    live files. Existing mocks answer any query with the same canned scalar."""

    @pytest.mark.asyncio
    async def test_is_orphan_queries_exact_columns_and_values(self, tmp_path):
        """Given file event_123.mp4
        When _is_orphan runs
        Then query 1 filters events.id == 123 and query 2 filters
        events.clip_path == <the real path> (never !=, never NULL-gutted)."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        test_file = tmp_path / "event_123.mp4"
        test_file.write_text("clip")
        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            await service._is_orphan(str(test_file))

        assert mock_session.execute.await_count == 2
        q_id, q_clip = (c.args[0] for c in mock_session.execute.await_args_list)

        assert "events.id = :id_1" in str(q_id)          # kills != (== flipped) and None-column guts
        assert q_id.compile().params == {"id_1": 123}
        assert "events.clip_path = :clip_path_1" in str(q_clip)  # kills != and gutted variants
        assert q_clip.compile().params == {"clip_path_1": str(test_file)}

    @pytest.mark.asyncio
    async def test_referenced_files_survive_query_honest_database(self, tmp_path):
        """Given a DB that actually evaluates WHERE params (not a fixed scalar)
        When run_cleanup scans one path-referenced file WITH an event id and one
        path-referenced file WITHOUT a parseable id
        Then neither is deleted - str(None)/None file-path mutants delete both."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        named = tmp_path / "event_123.mp4"   # id parseable -> _is_orphan two-query branch
        unnamed = tmp_path / "unknown_clip.mp4"  # no id -> _check_file_not_in_database branch
        for f in (named, unnamed):
            f.write_text("clip")
            old_time = datetime.now().timestamp() - (48 * 3600)
            os.utime(f, (old_time, old_time))
        referenced = {str(named), str(unnamed)}

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path), age_threshold_hours=24
        )

        async def honest_execute(query):
            """Answer like a database: look at the query's actual WHERE params."""
            params = query.compile().params
            result = MagicMock()
            if "id_1" in params:
                result.scalar_one_or_none.return_value = params["id_1"] if params["id_1"] == 123 else None
            elif "clip_path_1" in params:
                result.scalar_one_or_none.return_value = 1 if params["clip_path_1"] in referenced else None
            else:  # query no longer carries a real filter -> no rows, i.e. "orphan"
                result.scalar_one_or_none.return_value = None
            return result

        mock_session = AsyncMock()
        mock_session.execute = honest_execute

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            await service.run_cleanup()

        assert named.exists()      # mutant run#50: str(None) -> clip_path "None" unmatched -> deleted
        assert unnamed.exists()    # mutant _is_orphan#5: None path unmatched -> deleted
```

### T4 — multi-file stats exactness + young-file `continue` (kills C11 + C12, 9 survivors)

```python
class TestRunCleanupMultiFileStats:
    """Counters must SUM across files (not clamp/overshoot) and a young file
    must not abort the scan."""

    @pytest.mark.asyncio
    async def test_run_cleanup_multi_file_exact_stats_and_young_continue(self, tmp_path):
        """Given 3 old orphans (100/200/300 bytes) + 2 brand-new files
        When run_cleanup completes
        Then scanned=5, orphans=3, deleted=3, skipped_young=2, space=600
        and the young files survive."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        for name, size in (("old_a.mp4", 100), ("old_b.mp4", 200), ("old_c.mp4", 300)):
            f = tmp_path / name
            f.write_bytes(b"x" * size)
            old_time = datetime.now().timestamp() - (48 * 3600)
            os.utime(f, (old_time, old_time))
        for name in ("young_a.mp4", "young_b.mp4"):  # fresh mtime -> too young
            (tmp_path / name).write_bytes(b"y" * 50)

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path), age_threshold_hours=24
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            stats = await service.run_cleanup()

        # Exact totals kill every =1 / +=2 / =size / -=size mutant:
        assert stats.files_scanned == 5
        assert stats.orphans_found == 3
        assert stats.files_deleted == 3
        assert stats.space_reclaimed == 600  # mutant: =300 or 0, never 600
        # 2 young files force skipped==2; break mutant aborts at first young -> 1
        assert stats.files_skipped_young == 2
        assert (tmp_path / "young_a.mp4").exists()
        assert (tmp_path / "young_b.mp4").exists()
```

### T5 — singleton forwards every caller argument (kills C16, 12 survivors)

```python
class TestSingletonArgumentPlumbing:
    """The factory is the only construction path for app wiring; args must
    reach the instance, not be replaced by None/defaults."""

    def test_get_orphan_cleanup_service_forwards_all_arguments(self):
        """Given every kwarg set to non-default sentinels
        When get_orphan_cleanup_service first constructs the singleton
        Then every kwarg is on the instance (mutants silently send None)."""
        from backend.services.orphan_cleanup_service import (
            OrphanedFileCleanupService,
            get_orphan_cleanup_service,
            reset_orphan_cleanup_service,
        )

        reset_orphan_cleanup_service()
        try:
            tracker = MagicMock()
            callback = MagicMock()
            service = get_orphan_cleanup_service(
                scan_interval_hours=5,
                age_threshold_hours=7,
                clips_directory="/tmp/orphan-plumbing",
                enabled=False,
                job_tracker=tracker,
                broadcast_callback=callback,
            )
            assert isinstance(service, OrphanedFileCleanupService)
            assert service.scan_interval_hours == 5
            assert service.age_threshold_hours == 7
            assert str(service.clips_directory) == "/tmp/orphan-plumbing"
            assert service.enabled is False
            assert service._job_tracker is tracker
            assert service._broadcast_callback is callback
            # Second call returns the SAME (correctly configured) instance
            assert get_orphan_cleanup_service() is service
        finally:
            reset_orphan_cleanup_service()
```

### T6 — age arithmetic + boundary with a frozen clock (kills C17 + C18, 3 survivors)

```python
class TestFileAgeArithmeticPrecision:
    """Existing age tests pass on wide margins, so *3600, /3601 and >= -> >
    all survive. Pin now() and sit on the boundary."""

    def test_is_file_old_enough_exact_unit_conversion_and_boundary(self, tmp_path):
        """Given a frozen clock
        When age == threshold (3600 s, threshold 1h) -> True   (kills > and /3601)
        When age == 1 s      (threshold 1h)          -> False  (kills *3600: 1s age reads as 3600h)."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService
        import backend.services.orphan_cleanup_service as ocs_module

        fixed = datetime(2020, 1, 1, tzinfo=UTC)

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # noqa: ANN001 - mirror stdlib signature
                return fixed

        test_file = tmp_path / "clip.mp4"
        test_file.write_text("clip")
        service = OrphanedFileCleanupService(age_threshold_hours=1)

        with patch.object(ocs_module, "datetime", FrozenDateTime):
            # Exactly at the threshold: original (>=) True; > mutant False; /3601 3600/3601 False.
            with patch.object(
                Path, "stat", autospec=True,
                return_value=MagicMock(st_mtime=fixed.timestamp() - 3600),
            ):
                assert service._is_file_old_enough(test_file) is True
            # One second old: original False; *3600 mutant reads 1*3600=3600 "hours" -> True.
            with patch.object(
                Path, "stat", autospec=True,
                return_value=MagicMock(st_mtime=fixed.timestamp() - 1),
            ):
                assert service._is_file_old_enough(test_file) is False
```

(Requires `from datetime import UTC, datetime` — file currently imports only `datetime`; extend the import.)

### T7 — loop cadence read from the mocked sleep (kills C19 + C20, 6 survivors)

```python
class TestCleanupLoopCadence:
    """The scan interval IS behavior. Assert what asyncio.sleep is told."""

    @pytest.mark.asyncio
    async def test_cleanup_loop_sleeps_retry_then_interval(self):
        """Given first run raises, second run stops the loop
        When _cleanup_loop exits
        Then sleep was called exactly (60) then (scan_interval_hours * 3600)."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(scan_interval_hours=1, enabled=True)
        service.running = True

        calls = 0

        async def run_then_stop(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise Exception("transient")
            service.running = False
            from backend.services.orphan_cleanup_service import OrphanedFileCleanupStats

            return OrphanedFileCleanupStats()

        with patch.object(service, "run_cleanup", side_effect=run_then_stop, autospec=True):
            with patch(
                "backend.services.orphan_cleanup_service.asyncio.sleep",
                new_callable=AsyncMock,
            ) as sleep_mock:
                await service._cleanup_loop()

        # Kills wait_seconds -> None (sleep(None)), /3600, *3601, retry 61, sleep(None) x2
        assert sleep_mock.call_args_list == [call(60), call(3600)]
```

### T8 — broadcast payload contract (kills C23, 7 survivors) — extend the existing test

Replace the tail of `test_broadcasts_on_cleanup_completion` (currently :745-749) with:

```python
        # Verify broadcast was called with the full client contract
        mock_broadcast_callback.assert_called_once()
        call_args = mock_broadcast_callback.call_args
        assert call_args[0][0] == "orphan_cleanup_completed"
        envelope = call_args[0][1]
        assert envelope["type"] == "orphan_cleanup_completed"  # kills XXtypeXX/TYPE/case flips
        data = envelope["data"]
        assert set(data) == {"stats", "timestamp"}             # kills XXtimestampXX/TIMESTAMP renames
        assert "stats" in data
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert timestamp.tzinfo is not None and timestamp.utcoffset() == timedelta(0)  # kills now(None)
```

Optional C22 (LOW-VALUE) add-on to `test_broadcast_with_async_callback_no_running_loop` (:1249):

```python
        mock_asyncio_run.assert_called_once()
        assert asyncio.iscoroutine(mock_asyncio_run.call_args.args[0])  # kills asyncio.run(None)
```

## Coverage reconciliation

- Drafted tests kill, of the 68 TEST-GAP survivors: C6 11 + C7 4 + C9 7 (T1 = 22), C8 4 (T2), C13 2 + C14 3 (T3 = 5), C11 8 + C12 1 (T4 = 9), C16 12 (T5), C17 2 + C18 1 (T6 = 3), C19 4 + C20 2 (T7 = 6), C23 7 (T8) = **68 of 68**. Collateral: T1 also kills all 13 C10 LOW-VALUE message-shape mutants; T3a also kills all 9 C15 equivalent-under-mock keys; T8 add-on kills C22.
- Nothing is written for the 87 EQUIVALENT keys (log text, regex IGNORECASE, naive-clock identity, annotated default). C21/C24/C25/C26 are explicitly marked **do-not-chase**.
- All drafts are **UNVERIFIED** — per the WP4.3 live-run constraint no pytest was executed; the serial verify lane runs them red-on-mutant / green-on-original before merge.
