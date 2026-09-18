# WP4.4 Triage Dossier — backend/services/restore_service.py

- **Survivors:** 149 of 382 keys (meta: `mutants/backend/services/restore_service.py.meta`)
- **Covering test file (sole):** `backend/tests/unit/services/test_restore_service.py` (per `mutants/mutmut-stats.json` `tests_by_mangled_function_name`)
  - Key landmarks: `TestValidateManifest` L130, `TestCalculateChecksum` L219, `TestVerifyChecksums` L270, `TestIsDatetimeField` L320, `TestProcessRecordData` L366, `TestGetModelClass` L444, `TestRestoreTable` L497, `TestRestoreFromBackup` L626, progress test L721, order test L805, rollback test L745.
- **Diff method:** manual region-diff of `__mutmut_N` copies vs `__mutmut_orig` in `mutants/backend/services/restore_service.py` (full extraction saved at `/tmp/wp25/wp44-triage/diffs-rf.txt`; all 149 obtained, no `mutmut show` dependence).

## Why so many survive (test-design root causes)

1. **`progress_callback` is an `AsyncMock` and only `call_count >= 4` is asserted** (`test_restore_from_backup_calls_progress_callback`, L721-743) — every argument mutation (percent, message, arity) passes unnoticed.
2. **Log calls and their `extra={}` payloads are never asserted** — the entire logger message/extra mutant family survives. The test even named `..._logs_warning` (L303) asserts nothing about the log.
3. **`mock_db_session.execute`/`.add` assertions check call *counts*, never call *arguments*** — `execute(None)`, `add(None)` sail through.
4. **`_get_model_class` is patched out in every `_restore_table`/`restore_from_backup` test** — the call-site argument mutant and any behavior depending on the real mapping is unexercised.
5. **No test feeds a manifest without a `"contents"` key** — the `get("contents", {})` → `None` default mutations convert a clean no-op into `AttributeError`/`TypeError` and nobody notices.
6. **Existing `pytest.raises(match=...)` patterns are substring regexes** — `"XXBackup manifest not foundXX"` still matches `"Backup manifest not found"`, so raise-message decoration mutants survive.
7. **Multi-table interaction gaps:** the existing "processes tables in order" test puts *every* table in the manifest, so `continue`-vs-`break` flips in the loop guards are never on the taken path.

## Cluster table (counts sum to 149)

| # | Pattern | Function / concern | Count | Class | Example keys (≤3) | Killable by |
|---|---------|--------------------|-------|-------|-------------------|-------------|
| 1 | `progress_callback(...)` fixed-stage argument clobber: percent→None, percent+1, message→None, message case/`XX`/lowercase, arity drop (one-arg call) — 5 call sites × 8 variants | `restore_from_backup` L152/165/186/192/243 | 40 | TEST-GAP | `restore_from_backup__mutmut_13`, `_31`, `_155` | Draft T1 |
| 2 | `progress_percent = 20 + int((tc / max(t,1)) * 70)` operator/constant flips (+→−, `+21`, `/70`, `*`, `*71`, `max(...,2)`) | `restore_from_backup` L216 | 7 | TEST-GAP | `_107`, `_112`, `_118` | Draft T1 (`_117` `max(t,2)` is unreachable-equivalent — see note) |
| 3 | `tables_completed` counter arithmetic (`=0`→`1`, `+=1`→`-=1`/`+=2`/`=1`) feeding progress % | `restore_from_backup` L198/224 | 4 | TEST-GAP | `_86`, `_130`, `_131` | Draft T1 |
| 4 | `total_items += count` → `total_items = count` (assignment replaces accumulation) | `restore_from_backup` L223 | 1 | TEST-GAP | `_127` | Draft T1 (assert `result.total_items` across ≥2 tables) |
| 5 | `items_restored[table_name] = count` → `= None` (per-table dict value clobber; `in`-membership assertions still pass) | `restore_from_backup` L222 | 1 | TEST-GAP | `_126` | Draft T1 (assert `result.items_restored` values) |
| 6 | `manifest.get("contents", {})` default flipped to `None` (incl. arity-drop `get("contents", )`) → `None.items()`/`in None` crash when manifest has no `contents` key (valid per `_validate_manifest`) | `_validate_manifest` L292, `_verify_checksums` L312, `restore_from_backup` L203 | 6 | TEST-GAP | `validate_manifest__mutmut_22`, `verify_checksums__mutmut_3`, `restore_from_backup__mutmut_89` | Draft T2 |
| 7 | `_verify_checksums` missing-file guard `continue`→`break` (verification stops at first absent file) | `_verify_checksums` L319 | 1 | TEST-GAP | `verify_checksums__mutmut_12` | Draft T3 |
| 8 | Restore-loop contents-membership guard `continue`→`break` (tables after the first manifest-absent table are skipped) | `restore_from_backup` L204 | 2 | TEST-GAP | `restore_from_backup__mutmut_94`, `_106` | Draft T4 |
| 9 | `_is_datetime_field` ISO-shape heuristic weakened: `and`→`or`; `value[:10]`→`value[:11]` | `_is_datetime_field` L490 | 2 | TEST-GAP | `is_datetime_field__mutmut_12`, `_17` | Draft T5 |
| 10 | `_process_record_data` `isinstance(value, str) and` → `or` (non-str values routed into `_is_datetime_field` → `TypeError`) | `_process_record_data` L466 | 1 | TEST-GAP | `process_record_data__mutmut_4` | Draft T5 (combined) |
| 11 | `_restore_table` clears table via `db.execute(None)` (delete stmt arg clobber; count-only mock assertions) | `_restore_table` L399 | 1 | TEST-GAP | `restore_table__mutmut_17` | Draft T6 |
| 12 | `_restore_table` inserts via `db.add(None)` (instance arg clobber) | `_restore_table` L411 | 1 | TEST-GAP | `restore_table__mutmut_24` | Draft T6 |
| 13 | `_restore_table` calls `self._get_model_class(None)` (table-name arg clobber; every test patches the callee so mock hides it) | `_restore_table` L392 | 1 | TEST-GAP | `restore_table__mutmut_13` | Draft T6 |
| 14 | ISO `"Z"`→`"z"` / `"XXZXX"` in `fromisoformat(value.replace(...))` — no-op on real data and `fromisoformat` accepts `Z` natively on py≥3.11 | `_process_record_data` L469, `restore_from_backup` L247 | 4 | EQUIVALENT | `process_record_data__mutmut_15`, `_16`, `restore_from_backup__mutmut_172` | — |
| 15 | `zipfile.ZipFile(backup_file, "r")` → `ZipFile(backup_file, )` (arg dropped; default mode is `"r"`) | `restore_from_backup` L159 | 1 | EQUIVALENT | `restore_from_backup__mutmut_26` | — |
| 16 | `_validate_manifest` `manifest.get("version", "")` default changed (`""`→`None`/`"XXXX"`/arity-drop) — unreachable: `version` presence enforced by required-field loop above | `_validate_manifest` L285 | 3 | EQUIVALENT | `validate_manifest__mutmut_12`, `_14`, `_17` | — |
| 17 | `_verify_checksums` `content_info.get("checksum", "")` default changed — `""` vs `None` vs `"XXXX"` all mismatch any real hex digest → same `BackupCorruptedError` | `_verify_checksums` L321 | 3 | EQUIVALENT | `verify_checksums__mutmut_15`, `_17`, `_20` | — |
| 18 | `_calculate_checksum` chunk size `f.read(8192)`→`f.read(8193)`/`f.read(None)` (digest unchanged — same bytes hashed) | `_calculate_checksum` L347 | 2 | EQUIVALENT | `calculate_checksum__mutmut_16`, `_17` | — |
| 19 | "Starting restore from backup" logger.info message + `extra` payload mutations (None/case/`XX`/keycase/`str(None)`) | `restore_from_backup` L146-149 | 11 | LOW-VALUE | `restore_from_backup__mutmut_1`, `_2`, `_8` | log-assertion only; not worth asserting |
| 20 | "Restore completed successfully" logger.info message + `extra` dict mutations (job_id/backup_id/total_items/items_restored keys & values) | `restore_from_backup` L257-265 | 14 | LOW-VALUE | `restore_from_backup__mutmut_185`, `_186`, `_193` | — |
| 21 | "Restore failed, rolled back transaction" logger.error message + `extra={"job_id","error"}` mutations | `restore_from_backup` L236-239 | 11 | LOW-VALUE | `restore_from_backup__mutmut_142`, `_143`, `_150` | — |
| 22 | Per-table "not found, skipping" `logger.info`... actually `logger.info` extra `{"job_id","table"}` mutations (skip branch) | `restore_from_backup` L209-212 | 6 | LOW-VALUE | `restore_from_backup__mutmut_99`, `_102`, `_105` | — |
| 23 | "Restored {count} records to {table}" `logger.info` extra `{"job_id","table","count"}` mutations | `restore_from_backup` L226-229 | 8 | LOW-VALUE | `restore_from_backup__mutmut_133`, `_136`, `_141` | — |
| 24 | `_restore_table` per-record-failure `logger.warning` `extra={"table","record"}` mutations (incl. `[:200]`→`[:201]`) | `_restore_table` L415-418 | 8 | LOW-VALUE | `restore_table__mutmut_29`, `_33`, `_37` | — |
| 25 | `_restore_table` warning/error **messages** → `None` (no-model-mapping warning; per-record failure warning) | `_restore_table` L394/416 | 2 | LOW-VALUE | `restore_table__mutmut_15`, `_28` | — |
| 26 | `_verify_checksums` missing-file `logger.warning` message → `None` | `_verify_checksums` L318 | 1 | LOW-VALUE | `verify_checksums__mutmut_11` | — |
| 27 | `_calculate_checksum` `FileNotFoundError(f"File not found: ...")` message → `None` (type still raised; `pytest.raises(FileNotFoundError)` passes) | `_calculate_checksum` L342 | 1 | LOW-VALUE | `calculate_checksum__mutmut_3` | — |
| 28 | `_get_model_class` import-failure `logger.error` message → `None` | `_get_model_class` L446 | 1 | LOW-VALUE | `get_model_class__mutmut_22` | — |
| 29 | `raise BackupValidationError("...")` message text `XX`-decorated (path-traversal, manifest-not-found, invalid-contents) — survive because existing `pytest.raises(match=)` is a *substring* regex | `restore_from_backup` L171/173, `_validate_manifest` L294 | 3 | LOW-VALUE | `restore_from_backup__mutmut_48`, `_53`, `validate_manifest__mutmut_29` | exact-`args[0]` assert possible but brittle; not recommended |
| 30 | "Backup file for {table} not found, skipping" message → `None` | `restore_from_backup` L209 | 1 | LOW-VALUE | `restore_from_backup__mutmut_98` | — |
| 31 | "Restored {count} records to {table}" message → `None` (interpolation lost) | `restore_from_backup` L227 | 1 | LOW-VALUE | `restore_from_backup__mutmut_132` | — |

**Sum check:** TEST-GAP = 40+7+4+1+1+6+1+2+2+1+1+1+1 = **68** · EQUIVALENT = 4+1+3+3+2 = **13** · LOW-VALUE = 11+14+11+6+8+8+2+1+1+1+3+1+1 = **68** · **total = 149** ✓

Notes:
- **Cluster 2 `_117`** (`max(total_tables, 2)`): unreachable-equivalent — for `total_tables ≥ 2` the max is identical, and with `total_tables == 1` the sole iteration has `tables_completed == 0`, so `0/1 == 0/2`. Keep in cluster; T1 kills the other six.
- **Cluster 10 (`process_record_data__mutmut_4`)**: mutant only diverges for a *non-str* value under a `_at/_date/_time/_timestamp` key (`len(5)` → `TypeError`) — existing fixtures only pass str values, hence survival.
- Verdicts taken as-is from the meta per harness instructions; nothing re-executed.

## Drafted tests (UNVERIFIED — not yet run red/green)

All drafts target `backend/tests/unit/services/test_restore_service.py`, reusing its existing fixtures (`mock_db_session`, `sample_manifest`, `sample_camera_data`) and imports. TDD procedure (one line): add the test, run the named mutant copy — the new assertion must FAIL on the mutant diff (red) and PASS on the original (green) before the mutant flips to killed.

### T1 — `test_restore_from_backup_progress_callback_exact_contract` (kills clusters 1, 2, 3, 4, 5 — up to 52 mutants)

Asserts the full `(percent, step)` call sequence plus the aggregated result. The manifest carries all 8 `RESTORE_TABLE_ORDER` tables plus 4 bogus extra `contents` entries so `total_tables == 12` and the 8th table's percent is `20+int(7/12*70)=60` (the only small-ratio point where `*70` vs `*71`, mutant 118, diverges).

```python
    async def test_restore_from_backup_progress_callback_exact_contract(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """Progress callback receives the exact (percent, step) contract and totals aggregate."""
        import hashlib

        backup_file = tmp_path / "backup.zip"
        empty_json = "[]"
        correct_checksum = hashlib.sha256(empty_json.encode()).hexdigest()

        for table in RESTORE_TABLE_ORDER:
            sample_manifest["contents"][table] = {"count": 1, "checksum": correct_checksum}
        # Extra contents entries make total_tables=12 so the loop-percent ladder is
        # sensitive to *70 vs *71 and division mutations.
        for bogus in ("bogus_a", "bogus_b", "bogus_c", "bogus_d"):
            sample_manifest["contents"][bogus] = {"count": 0, "checksum": correct_checksum}

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))
            for table in RESTORE_TABLE_ORDER:
                zf.writestr(f"{table}.json", empty_json)

        service = RestoreService()
        progress_callback = AsyncMock()

        async def fake_restore(db, table_name, file_path):
            return 1

        with patch.object(service, "_restore_table", side_effect=fake_restore, autospec=True):
            result = await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
                progress_callback=progress_callback,
            )

        expected_ladder = [20 + int(tc / 12 * 70) for tc in range(8)]
        assert progress_callback.call_args_list == [
            ((5, "Extracting backup file..."),),
            ((10, "Reading manifest..."),),
            ((15, "Verifying checksums..."),),
            ((20, "Starting restore..."),),
            *(( (p, f"Restoring {t}..."), ) for p, t in zip(expected_ladder, RESTORE_TABLE_ORDER)),
            ((95, "Finalizing restore..."),),
        ]
        assert result.items_restored == {t: 1 for t in RESTORE_TABLE_ORDER}
        assert result.total_items == 8
```

TDD: red on every cluster-1/2/3 mutant (percent/message/arity/counter diverge from the frozen sequence, or totals collapse for `_127`/`_126`), green on original. (`__mutmut_117` is unreachable-equivalent and will stay red-proof — accept as equivalent.)

### T2 — `test_restore_from_backup_manifest_without_contents_succeeds` (kills cluster 6, all 6)

```python
    async def test_restore_from_backup_manifest_without_contents_succeeds(
        self, mock_db_session, tmp_path
    ):
        """A manifest may omit the optional contents key; restore is a clean no-op."""
        backup_file = tmp_path / "backup.zip"
        manifest = {
            "backup_id": "backup-456",
            "version": "1.0",
            "created_at": "2024-02-01T08:00:00Z",
        }  # NOTE: no "contents" key

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))

        service = RestoreService()
        result = await service.restore_from_backup(
            backup_file=backup_file,
            db=mock_db_session,
            job_id="job-456",
        )

        assert result.total_items == 0
        assert result.items_restored == {}

        # Same optional-key tolerance at the validator seam:
        service._validate_manifest(dict(manifest))  # must not raise
```

TDD: mutants turn the `contents` default into `None`, producing `AttributeError` (`None.items()`) in `_verify_checksums`, `TypeError` (`in None`) in the loop, or a spurious `BackupValidationError` in `_validate_manifest` — red on mutants, green on original.

### T3 — `test_verify_checksums_missing_file_does_not_skip_remaining_tables` (kills cluster 7, `_verify_checksums__mutmut_12`)

```python
    def test_verify_checksums_missing_file_does_not_skip_remaining_tables(
        self, tmp_path, sample_manifest
    ):
        """An absent backup file warns and continues — later tables are still verified."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text('{"test": "cameras"}')
        # events.json deliberately NOT created and listed FIRST in contents so the
        # continue/break difference is observable on the subsequent cameras check.
        sample_manifest["contents"] = {
            "events": {"count": 5, "checksum": "whatever"},
            "cameras": {"count": 2, "checksum": "wrong_checksum"},
        }

        service = RestoreService()

        with pytest.raises(BackupCorruptedError, match="Checksum mismatch for cameras"):
            service._verify_checksums(tmp_path, sample_manifest)
```

TDD: with `break`, the loop stops at missing events.json and never reaches cameras — no exception, red; original continues and raises, green.

### T4 — `test_restore_from_backup_skips_table_not_in_contents_without_halting` (kills cluster 8, `restore_from_backup__mutmut_94`/`_106`)

```python
    async def test_restore_from_backup_skips_table_not_in_contents_without_halting(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """A manifest-absent table is skipped via continue; later tables still restore."""
        import hashlib

        backup_file = tmp_path / "backup.zip"
        empty_json = "[]"
        correct_checksum = hashlib.sha256(empty_json.encode()).hexdigest()

        # cameras, events, alerts are in the manifest; zones (which sits between
        # cameras and events in RESTORE_TABLE_ORDER) is NOT.
        sample_manifest["contents"] = {
            table: {"count": 0, "checksum": correct_checksum}
            for table in ("cameras", "events", "alerts")
        }

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))
            for table in ("cameras", "events", "alerts"):
                zf.writestr(f"{table}.json", empty_json)

        service = RestoreService()
        restore_order = []

        async def track_restore_order(db, table_name, file_path):
            restore_order.append(table_name)
            return 0

        with patch.object(
            service, "_restore_table", side_effect=track_restore_order, autospec=True
        ):
            await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-789",
            )

        assert restore_order == ["cameras", "events", "alerts"]
```

TDD: with `break`, zones halts the loop after cameras → `["cameras"]`, red; original skips zones and restores all three, green.

### T5 — `test_is_datetime_field_boundary_and_process_record_data_type_guard` (kills clusters 9 and 10)

```python
    def test_is_datetime_field_requires_dash_within_first_ten_chars(self):
        """ISO-shape heuristic is an AND of length>=10 and dash in value[:10]."""
        service = RestoreService()
        # >=10 chars, no dash anywhere: must be False (kills and->or flip)
        assert not service._is_datetime_field("created_at", "abcdefghijk")
        # Dash exactly at index 10 (outside [:10]): must be False (kills [:10]->[:11])
        assert not service._is_datetime_field("created_at", "abcdefghij-k")

    def test_process_record_data_does_not_route_non_strings_through_datetime_check(self):
        """Non-string values pass through untouched even under datetime-suffixed keys."""
        service = RestoreService()
        # and->or mutant would call _is_datetime_field("started_at", 7) -> len(7) TypeError
        processed = service._process_record_data({"started_at": 7, "risk_score": 9})
        assert processed == {"started_at": 7, "risk_score": 9}
```

TDD: each first assert is False-but-True (or TypeError) under its mutant, red; green on original.

### T6 — `test_restore_table_arguments_delete_stmt_instances_and_table_name` (kills clusters 11, 12, 13)

Uses the REAL `_get_model_class` (no patch) so the `None`-arg mutant falls off the mapping, and asserts the `execute`/`add` call *arguments* (existing tests only count calls).

```python
    async def test_restore_table_arguments_delete_stmt_instances_and_table_name(
        self, mock_db_session, tmp_path, sample_camera_data
    ):
        """_restore_table clears via a real delete stmt and adds real model instances."""
        from sqlalchemy.sql.dml import Delete

        from backend.models.camera import Camera

        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text(json.dumps(sample_camera_data))

        service = RestoreService()
        # NOTE: no patch of _get_model_class — the real mapping must resolve "cameras".

        count = await service._restore_table(mock_db_session, "cameras", cameras_file)

        assert count == 2
        # Clear happened with a real DELETE statement, not None
        assert mock_db_session.execute.call_count == 1
        stmt = mock_db_session.execute.call_args.args[0]
        assert isinstance(stmt, Delete)
        # Every added object is a real Camera instance, not None
        added = [call.args[0] for call in mock_db_session.add.call_args_list]
        assert all(isinstance(obj, Camera) for obj in added)
        assert {obj.id for obj in added} == {"camera-1", "camera-2"}
```

TDD: `execute(None)` / `add(None)` fail the isinstance asserts; `_get_model_class(None)` returns `None` from the real mapping so `count == 0` — red on each mutant, green on original.

## Kill-coverage tally of the drafts

| Draft | Clusters killed | Mutants |
|-------|-----------------|---------|
| T1 | 1, 2 (minus equiv `_117`), 3, 4, 5 | ~51 |
| T2 | 6 | 6 |
| T3 | 7 | 1 |
| T4 | 8 | 2 |
| T5 | 9, 10 | 3 |
| T6 | 11, 12, 13 | 3 |
| **Total killable via drafts** | | **~66 / 68 TEST-GAP** |

Remaining 2 TEST-GAP without a dedicated draft: `_117` (unreachable-equivalent, reclassify) and the theoretical half of cluster 9 already folded into T5. LOW-VALUE (68) and EQUIVALENT (13) clusters: recommend accepting into the baseline denominator as score-exempt or unkillable rather than writing log-text assertions.
