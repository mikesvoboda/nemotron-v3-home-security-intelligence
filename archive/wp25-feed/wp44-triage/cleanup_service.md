# WP4.4 Triage Dossier — `backend/services/cleanup_service.py`

Generation-2 survivor triage against the FINAL mutmut cache (WP4.3 feed).

- **Mutant universe (meta):** 679 keys — 331 killed, **348 survived** (exit_code 0), 0 unchecked.
  Source: `mutants/backend/services/cleanup_service.py.meta` → `exit_code_by_key`.
- **Diff extraction:** manual region-diff of `mutants/backend/services/cleanup_service.py`
  clobbered copies against `backend/services/cleanup_service.py` (body-region difflib, n=0),
  plus `uv run mutmut show <key>` (read-only) for the 10 keys whose mutation sat in the
  def-signature/arg region beyond the captured body (all resolved; 0 unresolved).
- **Covering test files (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):**
  - `backend/tests/unit/services/test_cleanup_service.py` — sole covering file for every
    function except `CleanupService.__init__/start/stop`, which are additionally touched by
    `backend/tests/unit/services/test_async_context_managers.py` (lifecycle/context-manager
    call sites only; they assert the same running/task flags).
- **Verdict split:** TEST-GAP 162 / EQUIVALENT 96 / LOW-VALUE 90 (= 348).

Raw per-mutant diff dump: `/tmp/wp25/wp44-triage/diffs_cleanup.txt`;
machine assignment: `/tmp/wp25/wp44-triage/final_assign.json`.

## Cluster table (counts sum to 348)

| # | count | class | cluster | pattern (same change, same concern) | example keys (mutmut tail) |
|---|-------|-------|---------|--------------------------------------|----------------------------|
| 1 | 81 | EQUIVALENT | LOGTEXT | `logger.info/debug/warning(...)` message replaced by `None`, `XX..XX`-wrapped, or case-only variants (across run_cleanup, dry_run, loop, start/stop, __init__, orphan cleanup) | `xǁCleanupServiceǁrun_cleanup__mutmut_1`, `xǁCleanupServiceǁstart__mutmut_2`, `xǁOrphanedFileCleanupǁ__init____mutmut_4` |
| 2 | 59 | LOW-VALUE | PROGTEXT | job-progress **message slot** mutated (`None`, dropped, `XX`, case-only) while job_id and percent are preserved (`update_progress`/`start_job`/`_update_job_progress`) | `xǁCleanupServiceǁrun_cleanup__mutmut_37`, `xǁOrphanedFileCleanupǁrun_cleanup__mutmut_23` |
| 3 | 44 | TEST-GAP | PROGARG | job-progress **job_id or percent** mutated: `job_id→None`, arg dropped (message/percent shifts into job_id slot), percent `→None` or `N→N+1`, `complete_job(job_id, None)`/dropped result payload | `xǁCleanupServiceǁrun_cleanup__mutmut_30`, `xǁCleanupServiceǁrun_cleanup__mutmut_36`, `xǁOrphanedFileCleanupǁrun_cleanup__mutmut_22` |
| 4 | 44 | TEST-GAP | SQLDROP | SQL construction / execute argument replaced with `None` or an arg dropped: `delete(...)→None`, `.where(None)`, `select(None)`, `execute(None)`, `stream_scalars(None)` (run_cleanup, dry_run_cleanup, streaming path query, cleanup_old_logs, _count_old_logs, orphan get_referenced_files) | `xǁCleanupServiceǁrun_cleanup__mutmut_58`, `xǁCleanupServiceǁdry_run_cleanup__mutmut_14`, `xǁCleanupServiceǁ_get_detection_file_paths_streaming__mutmut_7` |
| 5 | 23 | TEST-GAP | GUARD_ANDOR | `if job_service is not None and job_id is not None:` progress gate flipped to `or`, `is None and`, `not None and job_id is None` (6 gate sites in run_cleanup) | `xǁCleanupServiceǁrun_cleanup__mutmut_27`, `xǁCleanupServiceǁrun_cleanup__mutmut_158` |
| 6 | 15 | LOW-VALUE | EXCINFO | `logger.error/warning(..., exc_info=True)` → `exc_info=None/False` or kwarg removed | `xǁCleanupServiceǁrun_cleanup__mutmut_167`, `xǁCleanupServiceǁ_delete_file__mutmut_10` |
| 7 | 10 | TEST-GAP | CUTOFF_INCL | retention predicate `< cutoff_date` → `<= cutoff_date` (detections/events/gpu stats DELETE + dry-run COUNT + Log delete/count + streaming select) | `xǁCleanupServiceǁrun_cleanup__mutmut_61`, `xǁCleanupServiceǁcleanup_old_logs__mutmut_10` |
| 8 | 9 | TEST-GAP | REF_NONE | `_get_referenced_files`: `abs_path = str(Path(p).resolve())` → `None` / `str(None)`("None") / `referenced.add(None)` — orphan-detection safety net silently mis-references | `xǁOrphanedFileCleanupǁ_get_referenced_files__mutmut_9`, `xǁOrphanedFileCleanupǁ_get_referenced_files__mutmut_12` |
| 9 | 8 | TEST-GAP | JOBARG | `start_job` payload kwargs mutated: `job_id=None` / kwarg dropped, `job_type=None`/dropped, `metadata=None`/dropped, `job_id` sentinel init `None→""` | `xǁCleanupServiceǁrun_cleanup__mutmut_8`, `xǁCleanupServiceǁrun_cleanup__mutmut_4` |
| 10 | 7 | LOW-VALUE | JOBTEXT | job-id `strftime` format / `job_type` / metadata-key literals `XX`-wrapped or case-flipped (`data_cleanup→DATA_CLEANUP`, `%y%m%d-%h%m%s`) | `xǁCleanupServiceǁrun_cleanup__mutmut_15`, `xǁCleanupServiceǁrun_cleanup__mutmut_19` |
| 11 | 5 | TEST-GAP | NAIVE_NOW | `datetime.now(UTC)` → `datetime.now(None)` (naive) in cutoff / wait / job-id timestamp | `xǁCleanupServiceǁrun_cleanup__mutmut_24`, `xǁCleanupServiceǁ_count_old_logs__mutmut_4` |
| 12 | 4 | TEST-GAP | TIMEBOUND | `_parse_cleanup_time` range check: `hours_int < 24` → `<= 24` / `< 25`, `minutes_int < 60` → `<= 60` / `< 61` — "24:00"/"23:60" accepted | `xǁCleanupServiceǁ_parse_cleanup_time__mutmut_12`, `xǁCleanupServiceǁ_parse_cleanup_time__mutmut_17` |
| 13 | 4 | TEST-GAP | TIMESIGN | cutoff sign flip `datetime.now(UTC) - timedelta(days=...)` → `+ timedelta(...)` (future cutoff = deletes everything newer) | `xǁCleanupServiceǁrun_cleanup__mutmut_23`, `xǁCleanupServiceǁdry_run_cleanup__mutmut_4` |
| 14 | 4 | EQUIVALENT | LOGGUARD | `if count > 0:` / `if deleted > 0:` → `>= 0` / `> 1` — only gates an info log, return value untouched | `xǁCleanupServiceǁ_count_old_logs__mutmut_16`, `xǁCleanupServiceǁcleanup_old_logs__mutmut_15` |
| 15 | 3 | EQUIVALENT | MSGTEXT | `ValueError("Invalid time range")` message `XX`/case-only | `xǁCleanupServiceǁ_parse_cleanup_time__mutmut_20` |
| 16 | 3 | LOW-VALUE | REPLACE_TWEAK | `now.replace(second=0/microsecond=0)` → `1` or kwarg dropped — 1-second schedule jitter nobody asserts | `xǁCleanupServiceǁ_calculate_next_cleanup__mutmut_13`, `xǁCleanupServiceǁ_calculate_next_cleanup__mutmut_11` |
| 17 | 2 | TEST-GAP | DRY_DIR_COUNT | dry-run file check `path.exists() and path.is_file()` → `or` (directory counted as deletable file) | `xǁCleanupServiceǁdry_run_cleanup__mutmut_24`, `xǁCleanupServiceǁdry_run_cleanup__mutmut_33` |
| 18 | 2 | TEST-GAP | SCAN_BREAK | `_scan_storage_directories` bad-root `continue` → `break` — later storage roots (clips) silently never scanned | `xǁOrphanedFileCleanupǁ_scan_storage_directories__mutmut_6`, `...__mutmut_9` |
| 19 | 2 | TEST-GAP | ORPH_LIST | `stats.orphaned_files.append(file_path)` → `append(None)`; `result = stats.to_dict()` → `None` (job-complete payload destroyed) | `xǁOrphanedFileCleanupǁrun_cleanup__mutmut_58`, `...__mutmut_80` |
| 20 | 2 | EQUIVALENT | EQUIV_GUARD_OR | orphan `if job_id and self._job_tracker:` → `or` at complete/fail sites — **unreachable divergence**: `create_job()` returns a truthy id whenever a tracker exists, so both operands are equivalent | `xǁOrphanedFileCleanupǁrun_cleanup__mutmut_79`, `...__mutmut_91` |
| 21 | 2 | LOW-VALUE | TASKNAME | `create_task(..., name="cleanup-service")` name literal `XX`/case-only | `xǁCleanupServiceǁstart__mutmut_16` |
| 22 | 2 | LOW-VALUE | TASKNAME_DROP | task `name=None` / name kwarg removed (NEM-5057 debugging aid) | `xǁCleanupServiceǁstart__mutmut_13`, `xǁCleanupServiceǁstart__mutmut_15` |
| 23 | 2 | EQUIVALENT | FMTBOUND | `format_bytes`: `if size < 0:` → `<= 0` (0 still returns "0 B") / `< 1` (0 hits int branch, still "0 B") | `x_format_bytes__mutmut_1`, `x_format_bytes__mutmut_2` |
| 24 | 1 | LOW-VALUE | BATCHSIZE | `self.batch_size = batch_size` → `= None` in `__init__` (batch_size never read in this module) | `xǁCleanupServiceǁ__init____mutmut_8` |
| 25 | 1 | EQUIVALENT | MSGNONE | `raise ValueError("Invalid time range")` → `ValueError(None)` — message swallowed by the wrapping ValueError | `xǁCleanupServiceǁ_parse_cleanup_time__mutmut_19` |
| 26 | 1 | TEST-GAP | REPLACE_MIN | `now.replace(hour=..., minute=minutes, ...)` drops `minute=` — scheduled cleanup minute silently ignored | `xǁCleanupServiceǁ_calculate_next_cleanup__mutmut_10` |
| 27 | 1 | EQUIVALENT | EQUIV_REPLACE12 | `now.replace(..., microsecond=0, )` trailing-comma no-op | `xǁCleanupServiceǁ_calculate_next_cleanup__mutmut_12` |
| 28 | 1 | TEST-GAP | FUTURE_BOUND | `if next_cleanup <= now:` → `<` — when the check lands exactly on the scheduled time, cleanup is deferred a full day | `xǁCleanupServiceǁ_calculate_next_cleanup__mutmut_15` |
| 29 | 1 | TEST-GAP | STREAM_OR | streaming collection `if self.delete_images and detection.file_path:` → `or` — image paths collected even when delete_images is off | `xǁCleanupServiceǁ_get_detection_file_paths_streaming__mutmut_9` |
| 30 | 1 | TEST-GAP | COUNT_ASSIGN | dry-run `stats.images_deleted += 1` → `= 1` (multi-image count collapses to 1) | `xǁCleanupServiceǁdry_run_cleanup__mutmut_34` |
| 31 | 1 | EQUIVALENT | EQUIV_DELFILE_OR | `_delete_file`: `path.exists() and path.is_file()` → `or` — in Python `is_file()` is False for a missing path, so the disjunction is equivalent | `xǁCleanupServiceǁ_delete_file__mutmut_3` |
| 32 | 1 | EQUIVALENT | EQUIV_LOOPBREAK | `_cleanup_loop` CancelledError handler `break` → `return` — identical (loop tail) | `xǁCleanupServiceǁ_cleanup_loop__mutmut_9` |
| 33 | 1 | LOW-VALUE | SLEEP61 | error-recovery backoff `asyncio.sleep(60)` → `61` | `xǁCleanupServiceǁ_cleanup_loop__mutmut_16` |
| 34 | 1 | TEST-GAP | ORPH_DEFAULT | `OrphanedFileCleanup.run_cleanup(dry_run: bool = True)` default → `False` — API default flips to destructive | `xǁOrphanedFileCleanupǁrun_cleanup__mutmut_1` |

Totals: **TEST-GAP 162, EQUIVALENT 96, LOW-VALUE 90 → 348**.

## Why these are TEST-GAP (covering-test evidence)

All in `backend/tests/unit/services/test_cleanup_service.py` unless noted:

- **SQLDROP / PROGARG / JOBARG / GUARD_ANDOR / CUTOFF_INCL** — `test_run_cleanup_with_redis_job_tracking`
  (line 1548) asserts only `start_job.assert_called_once()`, `update_progress.call_count >= 4`,
  `complete_job.assert_called_once()` — no args, no percents, no sequence. The delete tests
  (`test_run_cleanup_basic` L799, `..._with_thumbnail_files` L848, `..._with_image_files_enabled` L896)
  drive `session.execute` with a positional `side_effect` list that ignores the statement, so
  `execute(None)` / `whereclause→None` / `<`→`<=` are invisible. The mocks execute nothing.
- **REF_NONE** — `test_orphaned_file_cleanup_get_referenced_files` (L1923) asserts only
  `len(referenced) >= 5`; `add(None)` and `str(None)` preserve the count while poisoning the set
  that the real orphan run uses to spare referenced files.
- **SCAN_BREAK** — scan tests (L1960, L1991, L2003) each use a **single** storage root, so
  `continue→break` cannot differ; the "later root skipped" divergence needs ≥2 roots.
- **TIMEBOUND** — parse tests (L280–308, L700) only try `"25:00"` and valid `"23:59"`; the widened
  bounds (`24:00`, `23:60`) are never exercised.
- **TIMESIGN / CUTOFF_INCL** — no run_cleanup/dry_run test captures the cutoff value or the WHERE
  literal at all (`patch("...datetime", autospec=True)` is used only by the two
  `_calculate_next_cleanup` tests at L319/L341).
- **DRY_DIR_COUNT / COUNT_ASSIGN** — `test_dry_run_cleanup_with_files` (L1056) and
  `..._delete_images_disabled` (L1240) use only regular files and ≤1 image each; a directory
  masquerading as a deletable file and a 2→1 count collapse both pass.
- **STREAM_OR** — no streaming-path test exists with `delete_images=False` + non-null `file_path`
  that asserts the collected image list (the service-level equivalent at L1240 asserts only
  `stats.images_deleted == 0`, and the unit under test is reached through it but the query
  predicate mutants still survive because the query object itself is never asserted).
- **REPLACE_MIN / FUTURE_BOUND** — the two schedule tests assert hour only on the tomorrow branch
  (L371 asserts hour/minute **after** the `<=` path was taken; nothing asserts minute on the
  today branch and nothing pins the exact-`now` boundary).
- **ORPH_DEFAULT** — `test_orphaned_file_cleanup_run_dry_run` (L2045) always passes
  `dry_run=True` explicitly, so the parameter default is never observed.

## Drafted kill-tests (append to `backend/tests/unit/services/test_cleanup_service.py`)

All style-matched to the file (`pytestmark = pytest.mark.unit`, mock-session +
`create_stream_scalars_mock` idiom, `patch("backend.services.cleanup_service.get_session", ...)`).
**// UNVERIFIED - not yet run red/green** (no test execution permitted during the live mutation run).
Needed additions to the file's import block: `from datetime import UTC` (line-33 import line),
`from unittest.mock import ...` already covers AsyncMock/MagicMock/patch, plus `from sqlalchemy import operators`
inside the tests that use it.

### 1. `test_run_cleanup_delete_predicates_use_strict_cutoff` — kills CUTOFF_INCL (10) + TIMESIGN (4) + tz part of NAIVE_NOW

TDD: on the mutant, `stmt.whereclause.right.operator` is `le` (or the cutoff param is in the
future / naive) so the assert fails; on the original, all three DELETE statements carry a strict
`lt` against a UTC-aware cutoff ~30 days back and it passes.

```python
@pytest.mark.asyncio
async def test_run_cleanup_delete_predicates_use_strict_cutoff():
    """Every retention DELETE must target strictly-older-than a UTC cutoff (NEM-1539 semantics).

    Given: retention_days=30, empty streaming scan, zero-row deletes
    When: run_cleanup() executes
    Then: each of the 3 DELETE statements (detections, events, gpu stats) has a
          `< cutoff_date` predicate (never `<=`) and a UTC-aware cutoff ≈ now-30d,
          so a record exactly at the cutoff timestamp is retained.
    """
    from datetime import UTC
    from sqlalchemy import operators

    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_session.stream_scalars = create_stream_scalars_mock([])
    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 0
    mock_session.execute = AsyncMock(return_value=mock_delete_result)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0, autospec=True),
    ):
        await service.run_cleanup()

    expected_cutoff = datetime.now(UTC) - timedelta(days=30)

    assert mock_session.execute.call_count == 3  # detections, events, gpu stats
    for call in mock_session.execute.call_args_list:
        (stmt,), _ = call
        assert str(stmt).startswith("DELETE FROM")
        assert stmt.whereclause.right.operator is operators.lt, (
            "retention predicate must be strict '<' - records exactly at the cutoff stay"
        )
        params = stmt.compile().params
        cutoffs = [v for v in params.values() if isinstance(v, datetime)]
        assert len(cutoffs) == 1
        actual = cutoffs[0]
        assert actual.tzinfo is not None  # datetime.now(UTC), not a naive now()
        assert abs((expected_cutoff - actual).total_seconds()) < 5
```

Same capture pattern extended to `dry_run_cleanup` (COUNT queries at the 3 `.where(...)` sites)
kills the dry-run members of CUTOFF_INCL/TIMESIGN/SQLDROP; and to `cleanup_old_logs` /
`_count_old_logs` (`Log.timestamp < cutoff`) for the remaining members.

### 2. `test_run_cleanup_reports_canonical_job_progress_and_payload` — kills PROGARG (44) + JOBARG (8) + most of JOBTEXT (7)

TDD: mutant shifts the percent ladder (5,15,30,45,55,70), swaps job_id for `None`, drops the
result payload, or nulls start_job kwargs → the corresponding `call_args_list` / kwargs assert
fails; original passes.

```python
@pytest.mark.asyncio
async def test_run_cleanup_reports_canonical_job_progress_and_payload():
    """NEM-2292 contract: every progress beat carries the real job id and the exact
    percent ladder; completion carries the full stats payload."""
    mock_redis_client = AsyncMock()
    service = CleanupService(retention_days=30, redis_client=mock_redis_client)

    mock_job_service = AsyncMock()
    mock_job_service.start_job = AsyncMock(return_value="job-abc")
    mock_job_service.update_progress = AsyncMock()
    mock_job_service.complete_job = AsyncMock()

    mock_session = AsyncMock()
    mock_session.stream_scalars = create_stream_scalars_mock([])
    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 1
    mock_session.execute = AsyncMock(return_value=mock_delete_result)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(
            service, "_get_job_status_service", return_value=mock_job_service, autospec=True
        ),
        patch.object(service, "cleanup_old_logs", return_value=0, autospec=True),
    ):
        stats = await service.run_cleanup()

    start_kwargs = mock_job_service.start_job.call_args.kwargs
    assert start_kwargs["job_type"] == "data_cleanup"
    assert start_kwargs["metadata"] == {"retention_days": 30}
    assert start_kwargs["job_id"].startswith("cleanup-")

    beats = mock_job_service.update_progress.call_args_list
    assert [c.args[1] for c in beats] == [5, 15, 30, 45, 55, 70]
    assert all(c.args[0] == "job-abc" for c in beats)

    mock_job_service.complete_job.assert_called_once_with("job-abc", result=stats.to_dict())
```

(Mirror test for the orphan class asserts `_job_tracker.update_progress` calls with
`(job_id, [10, 30, 50])` and `complete_job("job-123", stats.to_dict())` — same construction,
kills the 20 orphan-side PROGARG members.)

### 3. `test_get_detection_file_paths_streaming_bounds_and_gates` — kills the streaming members of SQLDROP (7 keys) + STREAM_OR (1) + one CUTOFF_INCL member

TDD: mutant passes `None`/a predicate-free query into `stream_scalars`, or collects image
paths while `delete_images=False` → captured-query / image-list asserts fail; original passes.

```python
@pytest.mark.asyncio
async def test_get_detection_file_paths_streaming_bounds_and_gates():
    """Streaming path collection must bound by `detected_at < cutoff` and only
    gather image paths when delete_images is enabled."""
    from sqlalchemy import operators

    old = MockDetection(id=1, thumbnail_path="old/thumb.jpg", file_path="old/image.jpg")
    cutoff = datetime(2025, 1, 1)

    for delete_images, expect_images in ((False, 0), (True, 1)):
        service = CleanupService(retention_days=30, delete_images=delete_images)
        captured = {}
        inner = create_stream_scalars_mock([old])

        async def fake_stream(query, *args, **kwargs):
            captured["query"] = query
            return await inner(query, *args, **kwargs)

        mock_session = AsyncMock()
        mock_session.stream_scalars = fake_stream

        thumbs, images = await service._get_detection_file_paths_streaming(
            mock_session, cutoff
        )

        assert thumbs == ["old/thumb.jpg"]
        assert len(images) == expect_images
        query = captured["query"]
        assert query is not None
        assert query.whereclause.operator is operators.lt
        assert query.whereclause.left.name == "detected_at"
```

### 4. `test_orphan_referenced_files_collect_all_absolute_paths` — kills REF_NONE (9) + the orphan-query members of SQLDROP (8)

TDD: with `abs_path=None` / `add(None)` the set gains `None`/"None" and loses a real path → the
exact-equality assert fails; with `execute(None)`/`where(None)` the captured query asserts fail;
original passes.

```python
@pytest.mark.asyncio
async def test_orphan_referenced_files_collect_all_absolute_paths():
    """_get_referenced_files is the 'do-not-delete' whitelist - it must contain the
    RESOLVED absolute path of every referenced file, and no junk entries."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    cleanup = OrphanedFileCleanup(storage_paths=["/test"])

    detection_result = MagicMock()
    detection_result.all.return_value = [
        ("/data/image1.jpg", "/data/thumb1.jpg"),
        ("/data/sub/../image2.jpg", None),
        (None, "/data/thumb2.jpg"),
    ]
    event_result = MagicMock()
    event_result.all.return_value = [("/clips/clip1.mp4",), (None,)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[detection_result, event_result])

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        referenced = await cleanup._get_referenced_files()

    assert referenced == {
        str(Path("/data/image1.jpg").resolve()),
        str(Path("/data/image2.jpg").resolve()),  # relative/.. segments normalized
        str(Path("/data/thumb1.jpg").resolve()),
        str(Path("/data/thumb2.jpg").resolve()),
        str(Path("/clips/clip1.mp4").resolve()),
    }
    assert None not in referenced and "None" not in referenced

    detection_query = mock_session.execute.call_args_list[0].args[0]
    event_query = mock_session.execute.call_args_list[1].args[0]
    assert detection_query is not None and len(detection_query.column_descriptions) == 2
    assert event_query is not None and event_query.whereclause is not None
```

### 5. `test_scan_storage_directories_skips_bad_root_but_scans_later_roots` — kills SCAN_BREAK (2)

TDD: with `continue→break`, the first bad root aborts the whole scan and the good root's file
is never found (`len==0` fails `==1`); original passes.

```python
def test_scan_storage_directories_skips_bad_root_but_scans_later_roots(tmp_path):
    """A bad storage root must be SKIPPED, not abort the whole scan - clips dir must
    still be scanned after a missing thumbnails dir (and after a non-directory root)."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    good = tmp_path / "good"
    good.mkdir()
    target = good / "f.jpg"
    target.write_text("x")

    cleanup = OrphanedFileCleanup(
        storage_paths=["/definitely/does/not/exist", str(good)]
    )
    files = cleanup._scan_storage_directories()
    assert [f[0] for f in files] == [str(target.resolve())]

    file_root = tmp_path / "afile.txt"
    file_root.write_text("y")
    cleanup2 = OrphanedFileCleanup(storage_paths=[str(file_root), str(good)])
    assert len(cleanup2._scan_storage_directories()) == 1
```

### 6. `test_parse_cleanup_time_rejects_range_boundaries` — kills TIMEBOUND (4)

TDD: with `hours_int <= 24` (or `<= 60` minutes), `"24:00"`/`"23:60"` parse without raising →
`pytest.raises` fails; original raises the wrapped ValueError for all four boundary strings.

```python
def test_parse_cleanup_time_rejects_range_boundaries():
    """Hours are 0-23 and minutes 0-59; boundary values 24:00 / 23:60 must raise."""
    for bad_time in ("24:00", "24:59", "23:60", "23:61"):
        service = CleanupService(cleanup_time=bad_time)
        with pytest.raises(ValueError, match="Invalid cleanup_time format"):
            service._parse_cleanup_time()
```

Lower-value follow-ups (not drafted): PROGARG orphan mirror (above), FUTURE_BOUND needs a
frozen-`datetime.now`-at-the-scheduled-minute test (mirrors the L341 pattern with
`cleanup_time` equal to `now` exactly), ORPH_DEFAULT needs a default-arg call
`await cleanup.run_cleanup()` asserting `stats.dry_run is True` + files survive,
COUNT_ASSIGN/DRY_DIR_COUNT need a dry-run test with 2 images + a directory at a referenced
thumbnail path.

## Notes for the fix lane (WP4.4)

- Test #1's `stmt.compile().params` captures bind values from the mocked session; if the sandbox
  SQLAlchemy returns lazy/immature params, re-verify with a `select`-form smoke check first — the
  assertion structure (operator identity on `whereclause.right.operator`) does not depend on it.
- Existing tests must stay green: test #2 reuses the L1548 mock scaffold, whose `>= 4` progress
  assert is strictly weaker (it passes on both original and mutants); replacing it with the
  ladder assert is the intended strengthening, not a rewrite.
- `test_async_context_managers.py` needs no changes for any cluster (it only drives start/stop
  flags; no surviving cluster mutates those semantics).
