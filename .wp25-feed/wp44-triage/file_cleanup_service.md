# WP4.4 triage dossier — backend/services/file_cleanup_service.py

- **Census**: 125 mutants total (92 killed, **33 survivors**, 0 unchecked). All 33 survivor diffs pulled via
  `uv run mutmut show <key>` (no failures, no manual fallback needed).
- **Covering tests**: single file `backend/tests/unit/services/test_file_cleanup_service.py` (all functions covered;
  per-class line ranges: GetEventFiles L141-284, DeleteEventFiles L287-453, DeleteFilesBatch L456-583,
  DeleteFilesByPaths L586-644, DeleteSingleFile L647-693).
- **Cluster accounting**: 7+2+8+3+6+5+1+1 = 33 ✓

## Why so many survivors: one systemic weakness

Every existing test asserts **counts** (`len(result.deleted) == 2`, `total_missing == 1`) and side-effects
(file gone from disk), but never the **contents** of the result lists, never **exact byte totals**,
never **cross-event aggregates** (each aggregate test uses one contributor event so `+=` ≡ `=`), and the DB layer
is fully mocked so the **emitted SQL is never inspected** (`db.execute` is an `AsyncMock` returning canned events).

## Per-cluster table

| # | Pattern | Mutants | n | Class | Example keys (≤3) | What the tests miss |
|---|---------|---------|---|-------|-------------------|---------------------|
| C1 | log message/format arg clobbered to `None` (debug/info text in `_delete_single_file`, `delete_event_files`, `delete_files_batch`, `get_event_files`) | `_delete_single_file__5,8`, `delete_event_files__9,19`, `delete_files_batch__5,20`, `get_event_files__12` | 7 | **EQUIVALENT** | `…_delete_single_file__mutmut_5`, `…delete_files_batch__mutmut_20` | Pure logging text. `logger.x(None)` still runs, result objects unchanged; nobody should assert log strings. |
| C2 | result identity dropped: `FileCleanupResult(event_id=event_id)` → `event_id=None`; fallback `event_id or 0` → `or 1` | `delete_event_files__2`, `delete_files_by_paths__4` | 2 | **TEST-GAP** | `…delete_event_files__mutmut_2` | `delete_event_files` never asserts `result.event_id` at all; by_paths tests only pass a truthy `event_id=123` so the `or 0` fallback branch never executes. |
| C3 | `result.deleted/missing.append(str(file_path))` → `append(None)` / `append(str(None))` — entry CONTENT destroyed while count preserved | `delete_event_files__12,13,16,17`, `delete_files_by_paths__11,12,15,16` | 8 | **TEST-GAP** | `…delete_event_files__mutmut_12`, `…delete_files_by_paths__mutmut_15` | Tests assert `len(result.deleted)`/`len(result.missing)` and disk state only — list contents (`None` / `"None"` instead of the path string) are never inspected. This is the biggest cluster: downstream retention/reporting consumers of `to_dict()`/`deleted` lists would silently log `None` paths. |
| C4 | `total_bytes_freed += bytes` → `=` (drop accumulation) / `-=` — single-event and by-paths byte accounting | `delete_event_files__14`, `delete_files_by_paths__13,14` | 3 | **TEST-GAP** | `…delete_event_files__mutmut_14` | `test_delete_event_files_success` asserts only `total_bytes_freed > 0` (2 files → last-file bytes still >0, mutant survives); by_paths tests never assert bytes. No exact-sum assertion anywhere. |
| C5 | batch aggregation destroyed: `per_event_results.append(None)`, `total_missing/total_failed/total_bytes_freed +=` → `=` / `-=` | `delete_files_batch__11,14,16,17,18,19` | 6 | **TEST-GAP** | `…delete_files_batch__mutmut_11`, `…delete_files_batch__mutmut_17` | `test_batch_delete_aggregates_stats` gives event2 the only missing file (so `+=` ≡ `=` on total_missing), zero failures on both events (`+=`/`=`/`-=` all ≡ 0), and never asserts `total_bytes_freed` or per_event entries. Every aggregate needs ≥2 events each contributing distinct nonzero counts, asserted exactly. |
| C6 | SQL construction ignored: whole `stmt=None`, `where(None)` (no filter), `select(None)` (wrong columns), `Event.id ==` → `!=` (fetches a DIFFERENT event), `execute(None)` | `get_event_files__1,2,4,6,9` | 5 | **TEST-GAP** | `…get_event_files__mutmut_6` | All tests stub `db.execute` to return canned events and never look at the statement passed in. The `!=` flip (mutant 6) is production-dangerous: it would resolve a wrong event's files and delete them. Fix = capture `mock_db_session.execute.call_args` and compile the statement. |
| C7 | summary-log condition `if result.deleted or result.failed:` → `and` | `delete_event_files__18` | 1 | **LOW-VALUE** | `…delete_event_files__mutmut_18` | Only changes whether an INFO summary line is emitted (deleted-only cleanup no longer logs). Real change, observable only via log presence — behavior nobody should assert. |
| C8 | empty-path skip `continue` → `break` | `delete_files_by_paths__6` | 1 | **TEST-GAP** | `…delete_files_by_paths__mutmut_6` | `test_delete_files_by_paths_filters_empty_paths` puts the real path BEFORE the empties, so `break` ≡ `continue`. No test with a real path AFTER an empty entry (mutant would abandon the rest of a retention batch). |

## Drafted tests (6 clusters → 6 drafts)

**TDD procedure (one line)**: apply each cluster's mutant diff to a scratch copy of the service (or run the new
test under the mutmut harness) — the new assertion must fail on the mutant and pass on the original — then fold
the keys as killed. **All drafts UNVERIFIED — not yet run red/green (no test execution permitted in this triage).**

Existing test-file style: `MagicMock` session with `AsyncMock` execute, `@pytest.mark.asyncio`, real temp files via
`tempfile.NamedTemporaryFile(delete=False)`, cleanup in `finally`. All needed imports (`AsyncMock`, `MagicMock`,
`tempfile`, `Path`, `pytest`, `FileCleanupResult`) already exist in the file; C6 adds `from sqlalchemy import select`
(not needed) — actually C6 only needs what's already imported.

### T1 → kills C3 (8 mutants). Add to `TestFileCleanupServiceDeleteEventFiles`

```python
    @pytest.mark.asyncio
    async def test_delete_event_files_result_entries_are_path_strings(
        self, mock_db_session: MagicMock
    ) -> None:
        """Deleted/missing lists must carry the actual path strings, not None placeholders.

        Kills content-clobber mutants: append(None) / append(str(None)) on both the
        deleted and missing branches (delete_event_files AND delete_files_by_paths).
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f1:
            temp1 = f1.name
        try:
            detection = self._create_mock_detection(
                detection_id=1,
                file_path=temp1,
                thumbnail_path="/nonexistent/thumb_1.jpg",
            )
            event = self._create_mock_event(event_id=123, clip_path=None, detections=[detection])
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = event
            mock_db_session.execute.return_value = mock_result

            service = FileCleanupService()
            result = await service.delete_event_files(event_id=123, db=mock_db_session)

            # content, not just length: entries must be the resolved path strings
            assert result.deleted == [str(Path(temp1))]
            assert result.missing == ["/nonexistent/thumb_1.jpg"]
            assert None not in result.deleted
            assert None not in result.missing
            assert "None" not in result.deleted
            assert "None" not in result.missing

            # twin assertion for delete_files_by_paths (same append sites, other method)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f2:
                temp2 = f2.name
            try:
                result2 = await service.delete_files_by_paths(
                    file_paths=[temp2, "/nonexistent/other.jpg"]
                )
                assert result2.deleted == [str(Path(temp2))]
                assert result2.missing == ["/nonexistent/other.jpg"]
            finally:
                Path(temp2).unlink(missing_ok=True)
        finally:
            Path(temp1).unlink(missing_ok=True)
```

Equality assertion (`result.deleted == [str(Path(temp1))]`) kills `append(None)` (list becomes `[None]`) and
`append(str(None))` (`["None"]`); the trailing `None not in` / `"None" not in` lines are belt-and-braces.

### T2 → kills C6 (5 mutants). Add to `TestFileCleanupServiceGetEventFiles`

```python
    @pytest.mark.asyncio
    async def test_get_event_files_queries_selected_event_by_id(
        self, mock_db_session: MagicMock
    ) -> None:
        """The statement actually handed to db.execute must select the Event entity,
        filtered on events.id == event_id, with detections eager-loaded.

        Kills: stmt=None, execute(None), where(None), select(None), Event.id != int(event_id).
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        await service.get_event_files(event_id=123, db=mock_db_session)

        stmt = mock_db_session.execute.call_args.args[0]
        assert stmt is not None  # kills whole-stmt / execute(None) clobbers
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "SELECT events." in sql  # kills select(None) -> "SELECT NULL FROM events..."
        assert "events.id = 123" in sql  # kills where(None) (no filter) and int() loss
        assert "!=" not in sql  # kills the == -> != freshness/wrong-row flip
        # detections must be eager-loaded (collect_event_file_paths needs the relationship)
        assert any("detections" in repr(opt) for opt in stmt._with_options)
```

Note: `stmt._with_options` is a SQLAlchemy-2.0 private attribute; if it proves brittle, drop that last line — the
surviving cluster does not include options clobbers, the four SQL-text asserts already kill keys 1,2,4,6,9.

### T3 → kills C5 (6 mutants). Add to `TestFileCleanupServiceDeleteFilesBatch`

```python
    @pytest.mark.asyncio
    async def test_batch_delete_aggregates_every_statistic_across_events(
        self, mock_db_session: MagicMock
    ) -> None:
        """Both events must contribute to every aggregate: deleted, missing, failed AND
        bytes — so += cannot be replaced by = or -= — and per_event_results must hold
        the real FileCleanupResult objects.

        Kills: per_event_results.append(None); total_missing/total_failed/total_bytes_freed
        += -> = / -= .
        """
        detection1 = self._create_mock_detection(detection_id=1, file_path="/x/a.jpg")
        event1 = self._create_mock_event(event_id=1, clip_path="/x/clip1.mp4", detections=[detection1])
        detection2 = self._create_mock_detection(detection_id=2, file_path="/x/b.jpg")
        event2 = self._create_mock_event(event_id=2, clip_path="/x/clip2.mp4", detections=[detection2])

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            result = MagicMock()
            result.scalar_one_or_none.return_value = event1 if call_count == 0 else event2
            call_count += 1
            return result

        mock_db_session.execute = mock_execute

        service = FileCleanupService()
        # event1: one deleted (10 B), one missing; event2: one deleted (20 B), one failed
        service._delete_single_file = MagicMock(
            side_effect=[
                (True, None, 10),
                (False, None, 0),
                (True, None, 20),
                (False, "OS error: boom", 0),
            ]
        )

        result = await service.delete_files_batch(event_ids=[1, 2], db=mock_db_session)

        assert result.total_deleted == 2
        assert result.total_missing == 1  # killed by = (last event has 0) and -=
        assert result.total_failed == 1  # killed by = (0) and -= (-1)
        assert result.total_bytes_freed == 30  # killed by = (20) and -= (-10)
        assert result.success is False
        assert [r.event_id for r in result.per_event_results] == [1, 2]  # kills append(None)
```

Key ordering note: event1 carries the missing, event2 the failure — the mirror of that asymmetry is what makes
`total_missing = ...` observable (the current `test_batch_delete_aggregates_stats` has it backwards).

### T4 → kills C4 (3 mutants). Add to `TestFileCleanupServiceDeleteEventFiles`

```python
    @pytest.mark.asyncio
    async def test_delete_event_files_bytes_are_summed_exactly(self, mock_db_session: MagicMock) -> None:
        """total_bytes_freed must be the SUM of every deleted file's size, not the last
        file's size (=) or a running subtraction (-=).

        Kills: delete_event_files += -> =, delete_files_by_paths += -> = and -=.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f1:
            f1.write(b"x" * 10)
            temp1 = f1.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f2:
            f2.write(b"y" * 20)
            temp2 = f2.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f3:
            f3.write(b"z" * 30)
            temp3 = f3.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f4:
            f4.write(b"w" * 5)
            temp4 = f4.name
        try:
            detection = self._create_mock_detection(
                detection_id=1, file_path=temp1, thumbnail_path=temp2
            )
            event = self._create_mock_event(event_id=123, clip_path=None, detections=[detection])
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = event
            mock_db_session.execute.return_value = mock_result

            service = FileCleanupService()
            result = await service.delete_event_files(event_id=123, db=mock_db_session)
            assert result.total_bytes_freed == 30  # kills = (20) and -= (-10)

            # twin for delete_files_by_paths: fresh 30 B + 5 B pair -> exact sum 35
            result2 = await service.delete_files_by_paths(file_paths=[temp3, temp4])
            assert result2.total_bytes_freed == 35  # kills by_paths = (5) and -= (-25)
        finally:
            for p in (temp1, temp2, temp3, temp4):
                Path(p).unlink(missing_ok=True)
```

### T5 → kills C2 (2 mutants). Add to `TestFileCleanupServiceDeleteEventFiles`

```python
    @pytest.mark.asyncio
    async def test_results_carry_the_requested_event_id(self, mock_db_session: MagicMock) -> None:
        """FileCleanupResult.event_id must be the event the caller asked about (not None),
        and delete_files_by_paths must fall back to 0 (not 1) when no event_id is given.

        Kills: delete_event_files event_id=None; delete_files_by_paths event_id or 0 -> or 1.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = FileCleanupService()
        result = await service.delete_event_files(event_id=456, db=mock_db_session)
        assert result.event_id == 456  # kills event_id=None clobber

        result2 = await service.delete_files_by_paths(file_paths=[])
        assert result2.event_id == 0  # kills `or 0` -> `or 1` (only branch where it shows)
```

### T6 → kills C8 (1 mutant). Add to `TestFileCleanupServiceDeleteFilesByPaths`

```python
    @pytest.mark.asyncio
    async def test_delete_files_by_paths_skips_empty_entries_without_stopping(self) -> None:
        """An empty path mid-list must be skipped, not abort the run — later real
        paths must still be deleted.

        Kills: `continue` -> `break` on the empty-path guard.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f1:
            temp1 = f1.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f2:
            temp2 = f2.name
        try:
            service = FileCleanupService()
            # empty FIRST and MIDDLE: with break, nothing (or only temp1) would be processed
            result = await service.delete_files_by_paths(
                file_paths=["", temp1, "", temp2]  # type: ignore[list-item]
            )
            assert len(result.deleted) == 2
            assert not Path(temp1).exists()
            assert not Path(temp2).exists()
        finally:
            Path(temp1).unlink(missing_ok=True)
            Path(temp2).unlink(missing_ok=True)
```

## Notes / rulings

- C1 EQUIVALENT: logging a `None` message does not raise (`logging` accepts it, renders "None"), result objects and
  control flow untouched, and asserting log strings is baseline-forbidden. C7 LOW-VALUE: `or`→`and` only suppresses
  the INFO summary line for deleted-only cleanups — a real-but-cosmetic observability change.
- Highest production risk among survivors: **C6 mutant 6 (`==`→`!=`)** — silent wrong-event file deletion — and
  **C3 (8 mutants)** — result lists full of `None` flow straight into `to_dict()` used by API/logging. T2 and T1
  are the priority drafts.
- No test execution was performed (mutation run owns the machine); every draft is **UNVERIFIED**.
