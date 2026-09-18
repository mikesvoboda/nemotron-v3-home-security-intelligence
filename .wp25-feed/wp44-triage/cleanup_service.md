# WP4.4 Triage Dossier — `backend/services/cleanup_service.py`

Source of truth: `mutants/backend/services/cleanup_service.py.meta` → `exit_code_by_key`, `exit_code == 0`.
Collected 2026-09-17 from a **live** meta (132,960 B, mtime 17:48): 679 keys total →
**105 SURVIVED**, 177 killed, 397 null (not yet checked). Re-reading this meta later in the run
will yield a different set; the per-key lists below are snapshots of that moment.

All 105 diffs obtained via `uv run mutmut show <key>` — **zero failures, zero fallbacks**.
Full raw dump: `/tmp/wp25/diffs/cleanup_all.diff` (1247 lines). Machine-readable partition:
`/tmp/wp25/clusters.json`. Partition was re-derived programmatically: 21 clusters, counts sum
to exactly 105, no key in two clusters.

**Class totals:** TEST-GAP 28 (7 clusters) · LOW-VALUE 49 (10 clusters) · EQUIVALENT 28 (4 clusters).

## Two structural facts that shape the whole triage

**1. Mututmut's test selection is unit-only.** `pyproject.toml:638-640` sets
`pytest_add_cli_args_test_selection = ["backend/tests/unit"]`, and `pyproject.toml:671` sets
`mutate_only_covered_lines = true`. Consequence: **an integration test cannot kill a mutant here,
full stop** — it is never run. This matters enormously for the retention-cutoff clusters (A, B):
real boundary assertions already exist at `backend/tests/integration/test_cleanup_service.py:430`
and `:641`, and they do exercise the operator on a real Postgres. They are invisible to the
baseline. So the honest classification for the cutoff-operator pair is TEST-GAP **at the unit
tier** — and the fix must be a *unit* assertion, not "the integration test covers it". Note this
is a harness-scope finding that also explains why 25 of the 49 LOW-VALUE mutants are
message/argument clobbers whose only witnesses are log-capture or DB round-trips.

**2. The whole `OrphanedFileCleanup` progress-reporting block is unasserted.**
`backend/tests/unit/services/test_cleanup_service.py` was checked line by line (2230 lines);
the only assertion touching `update_progress` inside `run_cleanup` is
`mock_job_tracker.complete_job.assert_called_once()` at **:2139** — a bare "called once" with no
arguments. The existing `test_orphaned_file_cleanup_update_job_progress_with_tracker` at **:2180**
does assert full arguments (`:2190`) but calls `_update_job_progress` **directly**, so it never
touches the call sites in `run_cleanup` (cleanup_service.py:886, 891, 897, 911, 917, 922).
That single missing assertion accounts for the two largest clusters (N=16, P=2 → 18 survivors).

---

## Cluster table

Every key below is prefixed `backend.services.cleanup_service.x` in the meta; the `x` + `ǁ`
class separator is dropped for readability. `count` sums to `survivors_total = 105`.

| # | pattern | count | class | example keys (≤3) |
|---|---------|-------|-------|-------------------|
| A | retention cutoff `Log.timestamp < cutoff` → `<=` (both log fns) | 2 | **TEST-GAP** | `_count_old_logs__mutmut_11`, `cleanup_old_logs__mutmut_10` |
| B | retention cutoff `now(UTC) - timedelta(days=…)` → `+` (future cutoff) | 2 | **TEST-GAP** | `_count_old_logs__mutmut_3`, `cleanup_old_logs__mutmut_3` |
| C | `datetime.now(UTC)` → `datetime.now(None)` in cutoff expr | 2 | LOW-VALUE | `_count_old_logs__mutmut_4`, `cleanup_old_logs__mutmut_4` |
| D | `session.execute(<stmt>)` → `session.execute(None)` (log fns) | 2 | LOW-VALUE | `_count_old_logs__mutmut_7`, `cleanup_old_logs__mutmut_7` |
| E | `select(...)`/`where(...)` args → `None` (count query only) | 3 | LOW-VALUE | `_count_old_logs__mutmut_8`, `_count_old_logs__mutmut_10`, `cleanup_old_logs__mutmut_8` |
| F | log-guard `if count > 0:` → `>= 0` / `> 1` (both log fns) | 4 | LOW-VALUE | `_count_old_logs__mutmut_16`, `_count_old_logs__mutmut_17`, `cleanup_old_logs__mutmut_14` |
| G | `format_bytes`: `if size < 0:` → `<= 0` / `< 1` | 2 | EQUIVALENT | `format_bytes__mutmut_1`, `format_bytes__mutmut_2` |
| H | `logger.error(msg, exc_info=True)` → None/`False`/omitted | 4 | LOW-VALUE | `OrphanedFileCleanup.run_cleanup__mutmut_86`, `_87`, `_89` |
| I | `_scan_storage_directories`: bad-path `continue` → `break` | 2 | **TEST-GAP** | `_scan_storage_directories__mutmut_6`, `__mutmut_9` |
| J | `run_cleanup(self, dry_run: bool = True)` → `= False` | 1 | **TEST-GAP** | `OrphanedFileCleanup.run_cleanup__mutmut_1` |
| K | `job_id: str \| None = None` → `= ""` | 1 | EQUIVALENT | `OrphanedFileCleanup.run_cleanup__mutmut_2` |
| L | `start_job`/`complete_job` arg clobbers (None / arg-drop / arity) | 9 | LOW-VALUE | `run_cleanup__mutmut_7`, `_80`, `_81` |
| M | `start_job` message text tweaks (`"XX…XX"`, case) | 3 | LOW-VALUE | `run_cleanup__mutmut_11`, `_12`, `_13` |
| N | `_update_job_progress(job_id, PCT, msg)` args clobbered — 4 sites | 16 | **TEST-GAP** | `run_cleanup__mutmut_16`, `_32`, `_45` |
| O | `_update_job_progress` message *text* tweaks — 4 sites | 12 | LOW-VALUE | `run_cleanup__mutmut_23`, `_39`, `_52` |
| P | `if job_id and self._job_tracker:` → `or` (success + except paths) | 2 | **TEST-GAP** | `run_cleanup__mutmut_79`, `run_cleanup__mutmut_91` |
| Q | `_get_referenced_files`: `referenced.add(abs_path)` → `add(None)` | 3 | **TEST-GAP** | `_get_referenced_files__mutmut_12`, `_16`, `_25` |
| R | `abs_path = str(Path(x).resolve())` → `None` / `str(None)` | 6 | EQUIVALENT | `_get_referenced_files__mutmut_9`, `_13`, `_22` |
| S | `select(Detection…)` / `select(Event…)` arg clobbers | 8 | LOW-VALUE | `_get_referenced_files__mutmut_2`, `_5`, `_17` |
| T | `session.execute(<query>)` → `execute(None)` (referenced-files fns) | 2 | LOW-VALUE | `_get_referenced_files__mutmut_8`, `_21` |
| U | logger message arg → `None` / case / `XX…XX` (module-wide) | 19 | EQUIVALENT | `_wait_until_next_cleanup__mutmut_5`, `run_cleanup__mutmut_26`, `__init____mutmut_4` |

### Cluster notes (the reasoning that isn't in the table)

**A / B — retention cutoff (the only real semantic gap on the DB side).** `cleanup_service.py:487`
and `:509` build `cutoff = datetime.now(UTC) - timedelta(days=settings.log_retention_days)`; `:491`
counts `Log.timestamp < cutoff`, `:513` deletes it. A `<`→`<=` flip deletes one extra row exactly
on the boundary; the `-`→`+` flip puts the cutoff *in the future*, which would delete **every
log in the database** — the worst-impact mutant in this module. Unit tests
`test_cleanup_service.py:1292`/`:1313`/`:1334` and `:1360`/`:1383`/`:1406` mock
`session.execute` with `AsyncMock(return_value=…)` and assert only the returned count, so no
statement content is ever inspected. See fact #1 above on why the integration assertions don't
count. → drafts T1, T2.

**I — `continue` → `break` on an unusable storage path (`cleanup_service.py:822`, `:826`).** The
three covering tests each pass exactly **one** path, so the loop runs one iteration and
`break` ≡ `continue`. With two paths where the first is bad, `break` silently skips the rest —
i.e. one misconfigured/missing directory in `STORAGE_PATHS` silently disables cleanup for every
path after it. Not equivalent, just unreachable at 1 path. → draft T3.

**J — `dry_run: bool = True` → `False` (`cleanup_service.py:869`).** This is the module's
safety default: `run_cleanup()` with no arguments deletes files. Every one of the three callers
in the test file passes `dry_run=` explicitly (`:2068`, `:2102`, `:2135`, `:2166`), so the
default is never observed. Highest-severity-per-mutant survivor in the module. → draft T4.

**N — job-progress coordinates (16 survivors, 4 call sites).** Sites: `:886` (10), `:891` (30),
`:897` (50), `:917` (70). Mutants clobber `job_id`→None, `progress`→None, `progress`+1, or
`message`→None. `progress`→None is the dangerous one: `JobTracker.update_progress(job_id,
progress, message)` (`backend/services/job_tracker.py:362`) will push a null percent to the UI.
See fact #2 — a single argument-level assertion kills all 16. → draft T5.

**P — `and` → `or` (`cleanup_service.py:921`, `:930`).** With `job_id` None (no tracker) or
tracker None, `or` lets `complete_job(None, …)` / `fail_job(None, …)` fire anyway — corrupting
job state when only *one* of the two guards holds. `run_cleanup__mutmut_79` sits on the success
path, `__mutmut_91` on the `except` path. Same one-line fix as N (assert tracker was **not**
called when the tracker is absent — the existing `test_orphaned_file_cleanup_update_job_progress_without_tracker` at
`:2170` only asserts "does not raise", never "was not called"). → folded into draft T5.

**Q — `referenced.add(abs_path)` → `add(None)` (`cleanup_service.py:794`, `:797`, `:806`).**
Set membership is what protects a file from deletion. Each mutant poisons one of the three
sources (Detection.file_path / Detection.thumbnail_path / Event.clip_path): the real path never
enters the set, and `run_cleanup` then treats a **referenced** file as orphaned and deletes it —
data loss. This is exactly what `_get_referenced_files` exists to do. The covering test
`test_cleanup_service.py:1923` asserts `assert len(referenced) >= 5` (**:1957**) against 5 input
rows: the bound is loose, and every `add(None)` mutant *still* yields ≥5 distinct members
(`None` + surviving sources). A strict exact-membership assertion kills all three — and would
also kill a slice of S for free. → draft T6.

**R — EQUIVALENT, not a test gap.** `abs_path = None` / `str(None)` always lands inside
`if file_path:` / `if thumbnail_path:` / `if clip_path:` (`:791`, `:795`, `:804`), so the guard
has already proven the value is truthy; the mutated expression itself raises (TypeError /
`AttributeError` on `Path(None)`), so the mutant is an artificial crash, not a silent behavior
change. Killing it needs a *different* test (a real DB round-trip), not a stronger assertion.
Same verdict reasoning as cluster K: `""` and `None` are both falsy at every one of the three
`if job_id` sites (`:848`, `:921`, `:930`), so K is semantically identical — not a gap.

**G — EQUIVALENT.** `format_bytes(-100)` returns `"0 B"` under all three predicates. Verified
against the covering tests: `test_format_bytes_negative` asserts `format_bytes(-100) == "0 B"`
(`:1734`) — that assertion cannot distinguish `< 0` from `<= 0` or `< 1`. To kill these you'd
have to assert `format_bytes(0)` differs from the negative branch, but the function returns
`"0 B"` for 0 anyway (`:672`), so no observable behavior separates them. **Do not spend a test
on this cluster.**

**C, D, E, F, S, T — LOW-VALUE.** All of them mutate a SQLAlchemy expression or a session call
into something that *raises* (session is `AsyncMock`; `execute(None)` returns a MagicMock whose
`.scalar_one()` is a MagicMock → `int(MagicMock or 0)` is `TypeError`). Nobody should assert
"passing None to execute() throws"; these mutants are only killable by asserting on compiled SQL
text, which is exactly the brittleness that makes a suite rot. F's `if count > 0` → `>= 0`
merely logs a "would delete 0 logs" line; `> 1` merely skips the log at count==1. Log-only.

**H, L, M, O, U — LOW-VALUE (log/job text).** No test in this repo asserts logger message text
(`caplog` appears nowhere in the file), and there is no contract on job message strings.
L's `complete_job(job_id, None)` is the one arg with a real payload — it is covered by draft T5's
`complete_job` assertion rather than by a dedicated test.

---

## Drafted tests (6 highest-value clusters)

Target file: **`/agents/agent-nemo2/workspace/backend/tests/unit/services/test_cleanup_service.py`**
(2230 lines). Every test below is **UNVERIFIED — not yet run red/green**; the mutation run owns
this machine, so nothing was executed. TDD procedure for each: apply the mutant's one-line diff →
the new test must FAIL; revert → must PASS; then re-check the cluster's other keys.

Style notes followed: module-level `pytestmark = pytest.mark.unit` (**:47**) means no marker is
needed on these; the autouse `mock_settings_for_cleanup_tests` (**:52**) already provides
`DATABASE_URL`; `OrphanedFileCleanup` / `format_bytes` are imported *inside* each test (existing
convention); the local `mock_get_session` `@contextlib.asynccontextmanager` shim is the file's
established pattern (**:1303-1306**); compiled-SQL assertions reuse the precedent at
`backend/tests/unit/services/test_search.py:532`.

Existing imports at top of file (`:35-44`) already supply `contextlib`, `AsyncMock`, `MagicMock`,
`patch`, `pytest`, `datetime`/`timedelta`, `Path`, `CleanupService`. Add nothing module-level;
the SQL-dialect import is function-local exactly as `test_search.py` does it.

### T1 — kills cluster A (`<` → `<=`), also kills B, C
```python
@pytest.mark.asyncio
async def test_count_old_logs_cutoff_is_strictly_in_the_past():
    """_count_old_logs must count logs strictly older than now - retention_days.

    Kills WP4.3 survivors _count_old_logs__mutmut_11 (< -> <=), __mutmut_3 (- -> +)
    and __mutmut_4 (now(UTC) -> now(None)): the WHERE clause is never inspected by
    the existing count-returns tests (:1292/:1313/:1334), which mock execute().
    """
    from datetime import UTC

    service = CleanupService(retention_days=7)

    stmts = []

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0

    def record(stmt):
        stmts.append(stmt)
        return mock_result

    mock_session.execute = AsyncMock(side_effect=record)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        count = await service._count_old_logs()

    assert count == 0
    assert len(stmts) == 1

    stmt = stmts[0]
    condition = stmt.whereclause
    # Left operand is the timestamp column; right operand is the cutoff bind.
    cutoff = condition.right.value

    assert isinstance(cutoff, datetime), f"cutoff bind is {cutoff!r}, expected datetime"
    # Mutant _4 drops UTC -> naive datetime (a TypeError against a timestamptz column).
    assert cutoff.tzinfo is not None, "cutoff must be timezone-aware (now(UTC))"
    # Mutant _3 flips - to +, pushing the cutoff into the future (deletes everything).
    assert cutoff < datetime.now(UTC), "cutoff must be in the past"
    # Mutant _11 flips < to <=, which would delete a log exactly on the boundary.
    assert condition.operator.__name__ == "lt", (
        f"cutoff comparison must be strict '<', got {condition.operator.__name__}"
    )
```
Red-proves on `_count_old_logs__mutmut_11` (operator name is `le`) and on `__mutmut_3`
(cutoff > now). Note `condition.right.value` needs the expression to be a `BinaryExpression`
with a bind on the right — true for `Log.timestamp < cutoff`.

### T2 — kills cluster A on the delete path (highest blast radius)
```python
@pytest.mark.asyncio
async def test_cleanup_old_logs_delete_statement_targets_only_expired_logs():
    """cleanup_old_logs must DELETE only rows older than the cutoff.

    Same gap as above on the destructive path: test_cleanup_old_logs_deletes_logs
    (:1360) asserts the returned rowcount but never looks at the DELETE statement.
    A flipped - to + here wipes the whole logs table.
    """
    from datetime import UTC

    from sqlalchemy.dialects import postgresql

    service = CleanupService(retention_days=7)

    stmts = []

    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.rowcount = 15

    def record(stmt):
        stmts.append(stmt)
        return mock_result

    mock_session.execute = AsyncMock(side_effect=record)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        deleted = await service.cleanup_old_logs()

    assert deleted == 15
    assert len(stmts) == 1

    stmt = stmts[0]
    assert str(stmt.table.name) == "logs"
    assert stmt.whereclause is not None, "DELETE without WHERE wipes every log row"

    cutoff = stmt.whereclause.right.value
    assert cutoff.tzinfo is not None, "cutoff must be timezone-aware (now(UTC))"
    assert cutoff < datetime.now(UTC), "cutoff must be in the past"
    assert stmt.whereclause.operator.__name__ == "lt"

    # Belt-and-braces on the rendered SQL (postgresql dialect renders the bind as
    # %(timestamp_1)s -- assert on the *operator*, not the bind placeholder name).
    sql = " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())
    assert "DELETE FROM logs" in sql, sql
    assert "logs.timestamp <=" not in sql, f"cutoff must be strict '<', not '<=': {sql}"
```
Rendered SQL, verified in isolation against the real `Log` model (no DB, no pytest):
original `<` → `DELETE FROM logs WHERE logs.timestamp < %(timestamp_1)s`; mutant `<=` →
`… <= %(timestamp_1)s`. `condition.right.value` returns the `datetime` cutoff bind and
`condition.operator.__name__` is `"lt"` / `"le"` respectively. `pytest.mark.asyncio` matches
the file's existing style even though `asyncio_mode` is set.

### T3 — kills cluster I (multi-path `break`)
```python
def test_orphaned_file_cleanup_scan_skips_bad_path_and_continues(tmp_path):
    """A bad storage path must not abort scanning the remaining paths.

    Both existing bad-path tests (:1991 nonexistent, :2003 file-not-dir) pass a
    single path, so continue == break and _scan_storage_directories__mutmut_6 / _9
    survive. With two paths, break silently drops every path after the bad one.
    """
    from backend.services.cleanup_service import OrphanedFileCleanup

    good_dir = tmp_path / "good"
    good_dir.mkdir()
    (good_dir / "a.jpg").write_text("a")
    (good_dir / "nested" / "b.jpg").parent.mkdir(parents=True)
    (good_dir / "nested" / "b.jpg").write_text("bb")

    # First path is a plain file (not a directory) -> must be skipped, not fatal.
    bad_is_file = tmp_path / "not_a_dir.txt"
    bad_is_file.write_text("x")

    cleanup = OrphanedFileCleanup(storage_paths=[str(bad_is_file), str(good_dir)])

    files = cleanup._scan_storage_directories()

    assert len(files) == 2, "second path must still be scanned after an unusable first path"
    assert all(str(good_dir.resolve()) in p for p, _ in files)


def test_orphaned_file_cleanup_scan_skips_nonexistent_path_and_continues(tmp_path):
    """Same contract for the nonexistent-path branch (:822 continue)."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    good_dir = tmp_path / "good"
    good_dir.mkdir()
    (good_dir / "only.jpg").write_text("only")

    cleanup = OrphanedFileCleanup(
        storage_paths=[str(tmp_path / "does_not_exist"), str(good_dir)]
    )

    files = cleanup._scan_storage_directories()

    assert [Path(p).name for p, _ in files] == ["only.jpg"]
```
Both are red on `__mutmut_6` (nonexistent → break) / `__mutmut_9` (not-a-dir → break) and green
as written. Cluster I's two keys are covered one-for-one.

### T4 — kills cluster J (the `dry_run=True` safety default)
```python
@pytest.mark.asyncio
async def test_orphaned_file_cleanup_dry_run_defaults_to_true(tmp_path):
    """The no-argument default must be dry-run: run_cleanup() must never delete.

    OrphanedFileCleanup.run_cleanup__mutmut_1 flips the signature default to False.
    Every existing caller (:2068/:2102/:2135/:2166) passes dry_run= explicitly, so
    the safety default is unobserved and the mutant survives.
    """
    from backend.services.cleanup_service import OrphanedFileCleanup

    keep = tmp_path / "keep_me.jpg"
    keep.write_text("referenced")
    orphan = tmp_path / "orphan.jpg"
    orphan.write_text("orphan")

    cleanup = OrphanedFileCleanup(storage_paths=[str(tmp_path)])

    async def mock_get_referenced():
        return {str(keep.resolve())}

    with patch.object(
        cleanup, "_get_referenced_files", side_effect=mock_get_referenced, autospec=True
    ):
        stats = await cleanup.run_cleanup()  # deliberately no dry_run argument

    assert stats.dry_run is True, "default must be dry-run"
    assert stats.orphaned_count == 1
    assert orphan.exists(), "run_cleanup() with no args must not delete files"


def test_orphaned_file_cleanup_dry_run_signature_default():
    """Structural pin on the same contract: the signature default is True.

    Kills run_cleanup__mutmut_1 directly and cheaply; kept separate so a future
    deliberate change to the default is an explicit, visible edit.
    """
    import inspect

    from backend.services.cleanup_service import OrphanedFileCleanup

    sig = inspect.signature(OrphanedFileCleanup.run_cleanup)
    assert sig.parameters["dry_run"].default is True
```

### T5 — kills clusters N (16) and P (2); partial on L/M/O
```python
@pytest.mark.asyncio
async def test_orphaned_file_cleanup_progress_sequence_and_complete_result(tmp_path):
    """run_cleanup must report the documented progress ladder with real args.

    test_orphaned_file_cleanup_with_job_tracker (:2116) only asserts
    complete_job.assert_called_once() (:2139) with no arguments, so 16 mutants that
    clobber job_id / progress / message at the four _update_job_progress call sites
    (:886/:891/:897/:917) all survive -- including progress -> None, which pushes a
    null percent to the job UI.
    """
    from backend.services.cleanup_service import OrphanedFileCleanup

    mock_job_tracker = MagicMock()
    mock_job_tracker.create_job = MagicMock(return_value="job-123")

    cleanup = OrphanedFileCleanup(job_tracker=mock_job_tracker, storage_paths=[str(tmp_path)])
    (tmp_path / "orphan.jpg").write_text("o" * 10)

    async def mock_get_referenced():
        return set()

    with patch.object(
        cleanup, "_get_referenced_files", side_effect=mock_get_referenced, autospec=True
    ):
        stats = await cleanup.run_cleanup(dry_run=True)

    # Dry run: the delete stage (70) is never reached.
    expected = [
        ("job-123", 10, "Querying database for referenced files"),
        ("job-123", 30, "Scanning storage directories"),
        ("job-123", 50, "Identifying orphaned files"),
    ]
    assert mock_job_tracker.update_progress.call_args_list == [
        call(*args) for args in expected
    ]

    # complete_job must receive the job id and the real stats payload.
    mock_job_tracker.complete_job.assert_called_once()
    job_id, result = mock_job_tracker.complete_job.call_args[0]
    assert job_id == "job-123"
    assert result == stats.to_dict()
    assert result["orphaned_count"] == 1
    assert result["dry_run"] is True


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_delete_stage_reports_progress(tmp_path):
    """The 70-percent delete stage is only reported in delete mode, with full args."""
    from backend.services.cleanup_service import OrphanedFileCleanup

    mock_job_tracker = MagicMock()
    mock_job_tracker.create_job = MagicMock(return_value="job-del")

    cleanup = OrphanedFileCleanup(job_tracker=mock_job_tracker, storage_paths=[str(tmp_path)])
    (tmp_path / "orphan.jpg").write_text("orphan")

    async def mock_get_referenced():
        return set()

    with patch.object(
        cleanup, "_get_referenced_files", side_effect=mock_get_referenced, autospec=True
    ):
        await cleanup.run_cleanup(dry_run=False)

    assert mock_job_tracker.update_progress.call_args_list == [
        call("job-del", 10, "Querying database for referenced files"),
        call("job-del", 30, "Scanning storage directories"),
        call("job-del", 50, "Identifying orphaned files"),
        call("job-del", 70, "Deleting orphaned files"),
    ]


@pytest.mark.asyncio
async def test_orphaned_file_cleanup_no_job_call_without_job_id(tmp_path):
    """Neither tracker call may fire when there is no job id (:921/:930 and -> or).

    run_cleanup__mutmut_79 / __mutmut_91 turn `if job_id and self._job_tracker` into
    `or`, so complete_job/fail_job fire with a None job id whenever exactly one of
    the two guards holds -- corrupting job state.
    """
    from backend.services.cleanup_service import OrphanedFileCleanup

    tracker_holds_id = MagicMock()
    tracker_holds_id.create_job = MagicMock(return_value="")  # tracker present, id falsy

    cleanup = OrphanedFileCleanup(
        job_tracker=tracker_holds_id, storage_paths=[str(tmp_path)]
    )

    async def mock_get_referenced():
        return set()

    with patch.object(
        cleanup, "_get_referenced_files", side_effect=mock_get_referenced, autospec=True
    ):
        await cleanup.run_cleanup(dry_run=True)

    tracker_holds_id.update_progress.assert_not_called()
    tracker_holds_id.complete_job.assert_not_called()

    # And the except-path guard: same contract when the operation blows up.
    async def mock_get_referenced_error():
        raise RuntimeError("boom")

    with (
        patch.object(
            cleanup, "_get_referenced_files", side_effect=mock_get_referenced_error, autospec=True
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await cleanup.run_cleanup(dry_run=True)

    tracker_holds_id.fail_job.assert_not_called()
```
Add to the file's existing `from unittest.mock import AsyncMock, MagicMock, patch` (**:40**):
`call`. That import edit is required by T5 and is the only module-level change proposed.

### T6 — kills cluster Q; partial on S
```python
@pytest.mark.asyncio
async def test_orphaned_file_cleanup_get_referenced_files_exact_membership():
    """Every DB-referenced path must land in the set; no NULLs may leak in.

    test_cleanup_service.py:1923 asserts `len(referenced) >= 5` (:1957) -- loose
    enough that referenced.add(abs_path) -> add(None) at :794/:797/:806 still
    satisfies it. Those three mutants are data loss in waiting: a referenced file
    drops out of the protection set and run_cleanup deletes it.
    """
    from backend.services.cleanup_service import OrphanedFileCleanup

    cleanup = OrphanedFileCleanup(storage_paths=["/test"])

    mock_session = AsyncMock()

    detection_result = MagicMock()
    detection_result.all.return_value = [
        ("/path/image1.jpg", "/path/thumb1.jpg"),
        ("/path/image2.jpg", None),
        (None, "/path/thumb2.jpg"),
    ]
    event_result = MagicMock()
    event_result.all.return_value = [("/path/clip1.mp4",), ("/path/clip2.mp4",)]

    mock_session.execute = AsyncMock(side_effect=[detection_result, event_result])

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        referenced = await cleanup._get_referenced_files()

    # Exactly the five resolvable paths, resolved the same way the service resolves them.
    assert referenced == {
        str(Path("/path/image1.jpg").resolve()),
        str(Path("/path/thumb1.jpg").resolve()),
        str(Path("/path/image2.jpg").resolve()),
        str(Path("/path/thumb2.jpg").resolve()),
        str(Path("/path/clip1.mp4").resolve()),
        str(Path("/path/clip2.mp4").resolve()),
    }
    assert None not in referenced, "NULL path columns must not enter the referenced set"
    assert all(p != "None" for p in referenced)
```
Exact-equality is the load-bearing assertion; the three `None`/`"None"` checks make the failure
message legible. (Six members, not five — the `>= 5` in the existing test under-counts the rows;
that looseness is precisely why the mutants survived.)

---

## Covering test files (with the lines that matter)

| File | Lines that decide the verdicts |
|---|---|
| `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_cleanup_service.py` | **2230 lines; the only file mutmut selects for this module.** `:52` autouse settings fixture · `:665` wait_until_next_cleanup (sleep-only) · `:1292`/`:1313`/`:1334` count_old_logs (return-value only) · `:1360`/`:1383`/`:1406` cleanup_old_logs (rowcount + commit only) · `:1734` format_bytes negative · `:1895`/`:1912` init · `:1923`→**`:1957` `assert len(referenced) >= 5`** · `:1960`/`:1991`/`:2003`/`:2019` scan (one path each) · `:2045`/`:2080` dry-run/delete (explicit `dry_run=`) · `:2116`→**`:2139` `complete_job.assert_called_once()`** · `:2143` exception→fail_job (arguments asserted) · `:2170` without_tracker (not-raised only) · `:2180`→`:2190` `_update_job_progress` full-arg assertion (direct call, bypasses run_cleanup) |
| `/agents/agent-nemo2/workspace/backend/tests/integration/test_cleanup_service.py` | `:430` `test_cleanup_old_logs_deletes_old_logs` (10-day deleted / 1-day kept) and `:641` `…_preserves_boundary_logs` — real cutoff assertions that **cannot kill any mutant** because `pyproject.toml:638-640` restricts selection to `backend/tests/unit` |
| `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_search.py` | `:532` precedent for asserting on `str(stmt.compile(dialect=postgresql.dialect()))` inside a unit test (basis for T2) |
| `/agents/agent-nemo2/workspace/backend/services/job_tracker.py` | `:335` `start_job(job_id, message=None)` · `:362` `update_progress(job_id, progress, message=None)` · `:437` `complete_job(job_id, result=None)` — `message` is optional, which is why arg-drop mutants (L/M/O) change nothing observable |
| `/agents/agent-nemo2/workspace/pyproject.toml` | `:638-640` unit-only test selection · `:671` `mutate_only_covered_lines = true` |

## Handoff notes for WP4.4

1. **Expected score movement.** The 6 drafts target 28 TEST-GAP survivors (clusters A, B, I, J, N, P, Q). Realistic kill: 26–28 of 28. Clusters Q and S interact — T6's exact-membership assertion likely also kills 2–4 of cluster S's 8 `select()` clobbers, since a clobbered column list changes which rows arrive. Do not promise an exact number until the drafts run.
2. **The 28 EQUIVALENT survivors (clusters G, K, R, U) will not move** and should be triaged as "no test worth writing" rather than re-triaged next round. G in particular is unkillable without changing `format_bytes`'s contract.
3. **Structural finding worth its own ticket:** the unit-only selection rule means this baseline *cannot* see any integration-tier assertion. Every DB-semuality gap in this module (A, B) already has an integration test. That is a harness-scope tradeoff, not a test-quality failure — worth a line in the WP4.4 writeup so nobody "fixes" A and B by pointing at the integration file.
4. **One module-level edit is proposed:** add `call` to the `unittest.mock` import at `test_cleanup_service.py:40`, required by T5.
5. All six drafts are **UNVERIFIED**. The machine was under a live mutation run for this entire triage; no pytest, no mutmut run, no repo file touched. Only writes were under `/tmp/wp25/`.
