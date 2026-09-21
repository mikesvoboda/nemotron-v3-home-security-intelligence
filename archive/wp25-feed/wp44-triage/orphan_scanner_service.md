# WP4.4 Triage — backend/services/orphan_scanner_service.py

**Survivors:** 48 / 144 mutants (96 killed, 0 unchecked)
**Covering test file:** `backend/tests/unit/services/test_orphan_scanner_service.py` (single file; all covering tests live here)

## Reading the data

- Verdicts read from `mutants/backend/services/orphan_scanner_service.py.meta` (`exit_code_by_key`, 0 == survived).
- Diffs extracted by AST-diffing each `x…__mutmut_N` clobbered variant against its `__mutmut_orig` sibling in `mutants/…/orphan_scanner_service.py` (no mutmut run, no test execution — read-only).
- `tests_by_mangled_function_name` in `mutants/mutmut-stats.json` confirms every surviving mutation is executed by at least one test in `test_orphan_scanner_service.py`.

## Why so many survive (root cause)

Two structural weaknesses in the existing suite:
1. **The DB session is an `AsyncMock`.** `session.execute` is mocked to return canned rows keyed only by *call order*, never asserting the *query object* passed in. So every mutation of `select(...)`/`.where(...)`/the `execute(...)` argument is invisible → 10 survivors in `_get_referenced_paths` (cluster B).
2. **Assertions are length-only.** `test_scan_finds_orphans` checks `len(result.orphaned_files) == 1` and `test_get_referenced_paths_from_detections` checks `len(paths) >= 3`; `test_scan_handles_database_error` checks `len(result.scan_errors) > 0`. A `None`/`"None"` slipped into those collections keeps the length correct, so the poison passes. Clusters C, D, E exploit exactly this.

## Per-cluster table

| # | Cluster | Function | Count | Keys (≤3) | Class | Note |
|---|---------|----------|-------|-----------|-------|------|
| E | OrphanedFile field poisoning (`path`/`size_bytes`/`mtime`/`age`→None; `orphan`→None; `append(orphan)`→`append(None)`) | scan_directory | 6 | scan_directory__26, scan_directory__27, scan_directory__35 | TEST-GAP | `test_scan_finds_orphans` checks only `len==1` + `total>0`; never asserts `orphaned_files[0]` is an `OrphanedFile` with real fields. Poisoned record → cleanup job deletes wrong/nothing, `to_dict` crashes. **Highest value.** |
| C | Referenced-path set poisoning (thumbnail & clip `resolved`/`add`→None or `"None"`) | _get_referenced_paths | 6 | _get_referenced_paths__13, __15, __16 | TEST-GAP | Existing detection test asserts `len(paths) >= 3` (actual distinct = 4) so a dropped thumbnail/clip still passes. Referenced-on-disk file then mis-flagged as orphan → risky deletion. |
| B | Query construction hidden by mock (`select` column args, `.where(isnot(None))`, `execute(query)` arg → None) | _get_referenced_paths | 10 | _get_referenced_paths__2, __3, __18 | TEST-GAP | `AsyncMock.execute` ignores its argument, so dropping `file_path`/`thumbnail_path` from the projection or the `IS NOT NULL` filter is unobserved. Real query = wrong reference set. |
| A | Singleton factory drops propagated args (`base_path`/`extensions` → None / omitted) | get_orphan_scanner | 4 | x_get_orphan_scanner__3, __4, __6 | TEST-GAP | Singleton tests assert identity/reset only, never that `get_orphan_scanner(base_path=X)` yields `scanner.base_path == X`. |
| D | scan_errors message nulled (`error_msg`→None / `append(error_msg)`→`append(None)`) | scan_directory | 2 | scan_directory__15, scan_directory__17 | TEST-GAP | `test_scan_handles_database_error` asserts `len(scan_errors) > 0`; appending `None` still satisfies it. Consumers get `None` instead of a diagnostic string. |
| F | `total_orphaned_bytes += size` → `= size` (accumulate → overwrite) | scan_directory | 1 | scan_directory__36 | TEST-GAP | Only single-orphan test exists; with one file `+=` and `=` are identical. Multi-orphan sum never checked. |
| — | Log message args nulled (`logger.info/warning/debug(f"...")` → `logger.…(None)`) | __init__ / _get_file_info / _list_files / _get_referenced_paths / scan_directory | 11 | __init___9, _list_files__3, scan_directory__5 | LOW-VALUE | Only the log *text* changes; returns/branches unchanged. Nobody should assert log formatting. (`__init___9`, `_get_file_info__10`, `_get_referenced_paths__26`, `_list_files__3/5/12/13`, `scan_directory__5/10/16/40`) |
| — | scan_duration_seconds mutations (`=None`, `=mono()+start`, on early/error/happy returns) | scan_directory | 5 | scan_directory__11, scan_directory__12, scan_directory__39 | LOW-VALUE | Wall-clock timing metric; tests deliberately don't assert it (timing is flaky — cf. Date.now()-relative mock hazard). No product behavior depends on exact duration. |
| — | ScanResult.to_dict serialization cosmetics (`round(x,2)`→`round(x,3)`; `[:100]`→`[:101]`) | ScanResult.to_dict | 2 | to_dict__15, to_dict__18 | LOW-VALUE | Rounding precision and payload-display cap off-by-one; test value 1.5 is invariant to 2↔3 dp, and cap only bites at >100 items. |
| — | `scan_directory(self.base_path)` → `scan_directory(None)` | scan_all_directories | 1 | scan_all_directories__1 | EQUIVALENT | `scan_directory` does `scan_path = path or self.base_path`, so passing `self.base_path` vs `None` yields the identical `scan_path`. Semantically identical — no test can kill it. |

**Sum check:** TEST-GAP 6+6+10+4+2+1 = 29; LOW-VALUE 11+5+2 = 18; EQUIVALENT 1 → **48 = survivors_total.** ✓

## Drafted tests (6 highest-value TEST-GAP clusters)

All drafts append to `backend/tests/unit/services/test_orphan_scanner_service.py`. Style mirrors the existing file (imports inside test body, `@pytest.mark.asyncio`, `mock_get_session` asynccontextmanager, `tmp_path`/`scanner` fixtures). TDD procedure for each: **assertion fails on the mutant diff, passes on the original.**

> // UNVERIFIED - not yet run red/green

### Test E — orphan records carry real fields (kills cluster E: scan_directory__26/27/28/29/30/35)

```python
@pytest.mark.asyncio
async def test_scan_orphan_record_fields_populated(self, tmp_path, scanner):
    """An orphan in the result must be an OrphanedFile with real path/size/mtime/age."""
    from datetime import datetime, timedelta

    from backend.services.orphan_scanner_service import OrphanedFile

    (tmp_path / "orphan.jpg").write_text("orphan data")  # 11 bytes

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.orphan_scanner_service.get_session", mock_get_session):
        result = await scanner.scan_directory(tmp_path)

    assert len(result.orphaned_files) == 1
    orphan = result.orphaned_files[0]
    assert isinstance(orphan, OrphanedFile)          # kills __26, __35 (orphan/append -> None)
    assert orphan.path == tmp_path / "orphan.jpg"    # kills __27 (path=None)
    assert orphan.size_bytes == 11                    # kills __28 (size_bytes=None)
    assert isinstance(orphan.mtime, datetime)         # kills __29 (mtime=None)
    assert isinstance(orphan.age, timedelta)          # kills __30 (age=None)
```

### Test C — referenced set contains resolved thumbnail & clip paths (kills cluster C: _get_referenced_paths__13/15/16/22/24/25)

```python
@pytest.mark.asyncio
async def test_get_referenced_paths_includes_resolved_thumbnail_and_clip(self, scanner):
    """Thumbnail and clip paths must land in the referenced set, resolved, never None/'None'."""
    from pathlib import Path

    mock_session = AsyncMock()
    detection_result = MagicMock()
    detection_result.all.return_value = [
        ("/export/foscam/img/a.jpg", "/export/foscam/thumb/a.jpg"),
    ]
    event_result = MagicMock()
    event_result.all.return_value = [("/export/foscam/clip1.mp4",)]

    call_count = [0]

    async def mock_execute(query):
        call_count[0] += 1
        return detection_result if call_count[0] == 1 else event_result

    mock_session.execute = mock_execute

    paths = await scanner._get_referenced_paths(mock_session)

    assert str(Path("/export/foscam/img/a.jpg").resolve()) in paths
    assert str(Path("/export/foscam/thumb/a.jpg").resolve()) in paths   # kills __13/15/16
    assert str(Path("/export/foscam/clip1.mp4").resolve()) in paths     # kills __22/24/25
    assert None not in paths
    assert "None" not in paths
```

### Test B — queries select the right columns and filter NULL clips (kills cluster B: _get_referenced_paths__2/3/4/5/6/8/17/18/19/21)

```python
@pytest.mark.asyncio
async def test_get_referenced_paths_builds_expected_queries(self, scanner):
    """Session must be queried on file_path+thumbnail_path and non-null clip_path."""
    mock_session = AsyncMock()
    captured: list = []

    detection_result = MagicMock()
    detection_result.all.return_value = []
    event_result = MagicMock()
    event_result.all.return_value = []

    async def mock_execute(query):
        captured.append(query)
        return detection_result if len(captured) == 1 else event_result

    mock_session.execute = mock_execute

    await scanner._get_referenced_paths(mock_session)

    assert len(captured) == 2
    detection_sql, event_sql = (str(c) for c in captured)   # str(None) == "None" -> fails below
    assert "file_path" in detection_sql       # kills __2/__8 (query=None), __3/__5 (drops file_path)
    assert "thumbnail_path" in detection_sql  # kills __4/__6 (drops thumbnail)
    assert "clip_path" in event_sql           # kills __17/__21 (query=None), __19 (select(None))
    assert "IS NOT NULL" in event_sql         # kills __18 (where(None) drops the filter)
```

### Test A — singleton propagates base_path/extensions at creation (kills cluster A: x_get_orphan_scanner__3/4/5/6)

```python
def test_get_orphan_scanner_propagates_construction_args(self, tmp_path):
    """First call's base_path/extensions must reach the constructed scanner."""
    from backend.services.orphan_scanner_service import get_orphan_scanner, reset_orphan_scanner

    reset_orphan_scanner()
    try:
        scanner = get_orphan_scanner(base_path=str(tmp_path), extensions={".jpg"})
        assert scanner.base_path == tmp_path          # kills __3/__5 (base_path -> None)
        assert scanner.extensions == {".jpg"}         # kills __4/__6 (extensions -> None)
    finally:
        reset_orphan_scanner()
```

### Test D — scan_errors carries a real message string (kills cluster D: scan_directory__15/17)

```python
@pytest.mark.asyncio
async def test_scan_database_error_records_message_string(self, tmp_path, scanner):
    """DB-failure path must record a non-empty message, not None."""
    (tmp_path / "test.jpg").write_text("test")

    @contextlib.asynccontextmanager
    async def mock_get_session():
        raise Exception("Database connection failed")
        yield  # required for asynccontextmanager syntax

    with patch("backend.services.orphan_scanner_service.get_session", mock_get_session):
        result = await scanner.scan_directory(tmp_path)

    assert len(result.scan_errors) == 1
    msg = result.scan_errors[0]
    assert isinstance(msg, str) and msg.strip()   # kills __15/__17 (message appended -> None)
```

### Test F — total_orphaned_bytes sums across multiple orphans (kills cluster F: scan_directory__36)

```python
@pytest.mark.asyncio
async def test_scan_total_orphaned_bytes_sums_multiple_orphans(self, tmp_path, scanner):
    """With two orphans the total must be the SUM, not the last file's size."""
    (tmp_path / "a.jpg").write_text("aaaa")  # 4 bytes
    (tmp_path / "b.jpg").write_text("bb")    # 2 bytes

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.orphan_scanner_service.get_session", mock_get_session):
        result = await scanner.scan_directory(tmp_path)

    assert result.scanned_files == 2
    assert result.total_orphaned_bytes == 6   # kills __36 (= size -> 2, last file only)
```

## Covering test file(s)
- `backend/tests/unit/services/test_orphan_scanner_service.py:431` `TestScanDirectory::test_scan_finds_orphans` — asserts `len==1`/`total>0` only; misses clusters **E** and **F**.
- `backend/tests/unit/services/test_orphan_scanner_service.py:350` `TestGetReferencedPaths::test_get_referenced_paths_from_detections` — `len(paths) >= 3`; misses cluster **C**.
- `backend/tests/unit/services/test_orphan_scanner_service.py:382` `test_get_referenced_paths_handles_none` — asserts length; misses cluster **B** (no query assertion).
- `backend/tests/unit/services/test_orphan_scanner_service.py:531` `TestSingleton::test_get_orphan_scanner_returns_singleton` — identity only; misses cluster **A**.
- `backend/tests/unit/services/test_orphan_scanner_service.py:572` `test_scan_handles_database_error` — `len(scan_errors) > 0` only; misses cluster **D**.
