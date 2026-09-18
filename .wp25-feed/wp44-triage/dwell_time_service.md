# WP4.4 Triage Dossier — backend/services/dwell_time_service.py

- **Survivors:** 101 of 220 checked keys (meta: `mutants/backend/services/dwell_time_service.py.meta`, exit_code 0).
- **Functions hit:** `record_entry` (32), `record_exit` (23), `check_loitering` (23), `get_zone_entity_distribution` (23). No survivors in `get_active_record`, `get_active_dwellers`, `get_dwell_history`, `mark_alert_triggered`, `cleanup_stale_records`, `get_record_by_id`, `get_zone_statistics`, `get_zone_activity_heatmap`, `get_dwell_time_service` — the four surviving functions are the entire residue.
- **Method:** diffs extracted by diffing each `xǁ…__mutmut_N` variant body against its `__mutmut_orig` sibling in the mutant copy (all 101 resolved; `mutmut show` spot-checked and agrees). Key lists: `/tmp/wp25/wp44-triage/dts-survivor-keys.txt`, raw diffs: `/tmp/wp25/wp44-triage/dts_diffs.json`.

## Why the survivors cluster the way they do

The covering unit tests (`backend/tests/unit/services/test_dwell_time_service.py`) are **mock-session tests**: every test either patches `get_active_record`/`get_active_dwellers` (so the real SQL in the _calling_ function is never exercised, and the SQL _inside_ the mocked callee is never the mutated function) or mocks `db.execute` to return canned records (so the built `stmt` object is discarded, never asserted). Consequences:

1. **Every query-semantics mutant survives** — `select(None)`, dropped WHERE conjuncts, `==`→`!=`, `<=`→`<`, `>=`→`>`, `|`→`&`, `load_zone=True`→`False/None/omitted`. No test ever compiles or inspects the statement, and the only integration test (`backend/tests/integration/test_dwell_time_service.py:63`) queries a nonexistent zone 999999.
2. **Every "call with wrong target/args" mutant survives** — tests assert `mock_db.add.assert_called_once()` (arity, not identity) and never assert the _arguments_ of `get_active_record(zone_id, track_id)`.
3. **Boundary mutants survive** because mocks return dwell values (600/900/120) far from the threshold, never equal to it, and mock percentages are exact (60/30/10, `==` passes for `round(.,2)` AND `round(.,3)` AND int-truncation via `==` int-float equality).
4. **Log-payload mutants (57 of 101)** are all pure `logger.*(msg, extra={...})` text mutation — message→None, `extra`→None/omitted, key renames `"zone_id"→"XXzone_idXX"/"ZONE_ID"`. No test in the file references `caplog` or the logger; these are EQUIVALENT for practical purposes.

## Per-cluster table

| #   | Cluster                   | Pattern (function : change)                                                                                                                                                                                                                   | N                               | Class      | Example keys (suffix of full key)                                                 | Note                                                                                                                                                                                                                                                         |
| --- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- | ---------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| 1   | entry-lookup-None         | `record_entry:28` `get_active_record(zone_id, track_id)` → `(None, track_id)` / `(zone_id, None)`                                                                                                                                             | 2                               | TEST-GAP   | `record_entry__mutmut_2`, `…__mutmut_3`                                           | Test patches the callee but never asserts its args (test file :387, autospec mock unchecked). Wrong zone/track → dedupe lookup silently global. DRAFT T1                                                                                                     |
| 2   | exit-lookup-None          | `record_exit:21` same lookup args → None                                                                                                                                                                                                      | 2                               | TEST-GAP   | `record_exit__mutmut_2`, `…__mutmut_3`                                            | Same hole (:449). DRAFT T1                                                                                                                                                                                                                                   |
| 3   | entry-time-default        | `record_entry:46` `entry_time=entry_time or utc_now()` → `None` / kwarg deleted / `or`→`and`                                                                                                                                                  | 3                               | TEST-GAP   | `record_entry__mutmut_22`, `…__mutmut_29`, `…__mutmut_32`                         | (:378) asserts zone/track/class/triggered_alert but never `record.entry_time`. DRAFT T6                                                                                                                                                                      |
| 4   | total-seconds-init        | `record_entry:47` `total_seconds=0.0` → `None` / deleted / `1.0`                                                                                                                                                                              | 3                               | TEST-GAP   | `record_entry__mutmut_23`, `…__mutmut_30`, `…__mutmut_33`                         | Model column is `nullable=False` (models/dwell_time.py:86) — a real DB would reject `None`; mock session never notices. DRAFT T6                                                                                                                             |
| 5   | entry-persist-None        | `record_entry:50,52` `db.add(record)`/`db.refresh(record)` → `db.add(None)`/`refresh(None)`                                                                                                                                                   | 2                               | TEST-GAP   | `record_entry__mutmut_35`, `…__mutmut_36`                                         | (:400) asserts `add.assert_called_once()` — arity only, identity never. DRAFT T6                                                                                                                                                                             |
| 6   | exit-refresh-None         | `record_exit:36` `db.refresh(record)` → `refresh(None)`                                                                                                                                                                                       | 1                               | TEST-GAP   | `record_exit__mutmut_20`                                                          | Same one-line fix as #5 in TestRecordExit (:456).                                                                                                                                                                                                            |
| 7   | loiter-now-none           | `check_loitering:29` `now = current_time or utc_now()` → `now = None`                                                                                                                                                                         | 1                               | LOW-VALUE  | `check_loitering__mutmut_1`                                                       | `DwellTimeRecord.calculate_dwell_time(None)` self-falls-back to `utc_now()` (models/dwell_time.py:126) — observationally identical in prod. Not worth an assertion on its own.                                                                               |
| 8   | loiter-now-and            | `check_loitering:29` → `current_time and utc_now()`                                                                                                                                                                                           | 1                               | TEST-GAP   | `check_loitering__mutmut_2`                                                       | Caller-supplied clock silently swapped for wall clock. DRAFT T2 (`assert_called_once_with(now)`).                                                                                                                                                            |
| 9   | loiter-calc-now           | `check_loitering:36` `record.calculate_dwell_time(now)` → `(None)`                                                                                                                                                                            | 1                               | TEST-GAP   | `check_loitering__mutmut_11`                                                      | DRAFT T2.                                                                                                                                                                                                                                                    |
| 10  | loiter-threshold-boundary | `check_loitering:37` `dwell_seconds >= threshold` → `>`                                                                                                                                                                                       | 1                               | TEST-GAP   | `check_loitering__mutmut_12`                                                      | **Highest-value survivor**: a record sitting at exactly the threshold stops alerting. Tests only use 600/900 vs 300 / 120 vs 300 (test file :50, :149) — never equality. DRAFT T2                                                                            |
| 11  | loiter-dwellers-args      | `check_loitering:33` `get_active_dwellers(zone_id, load_zone=True)` → zone_id→None / `load_zone=None` / `load_zone=False` / kwarg omitted                                                                                                     | 4                               | TEST-GAP   | `check_loitering__mutmut_5`, `…__mutmut_6`, `…__mutmut_9`                         | All tests patch the callee (e.g. :56) and assert nothing about the call; `load_zone=False` degrades zone names to "unknown" in metrics only under the `record.zone is None` test. DRAFT T3                                                                   |
| 12  | dist-stmt-None            | `get_zone_entity_distribution` whole-query args → None: `stmt=(…)`→`stmt=None` (mutmut*1), `and*(…)`→`None`(2),`select(None)`(4), WHERE-clause args →None (6,7,8),`db.execute(None)` (17)                                                     | 7                               | TEST-GAP   | `get_zone_entity_distribution__mutmut_1`, `…__mutmut_4`, `…__mutmut_17`           | (:537) mocks `db.execute` return; the `stmt` argument is discarded, never asserted. DRAFT T4                                                                                                                                                                 |
| 13  | dist-conjunct-removed     | entire AND clause dropped: `zone_id == zone_id` (9), `entry_time <= end_time` (10), whole `exit>=start OR exit IS NULL` (11)                                                                                                                  | 3                               | TEST-GAP   | `…__mutmut_9`, `…__mutmut_10`, `…__mutmut_11`                                     | Deletes zone-scoping / window filter outright — cross-zone data leak invisible to mocked execute. DRAFT T4                                                                                                                                                   |
| 14  | dist-zone-neq             | `DwellTimeRecord.zone_id == zone_id` → `!=`                                                                                                                                                                                                   | 1                               | TEST-GAP   | `…__mutmut_12`                                                                    | DRAFT T4 (`"zone_id = 42" in compiled`).                                                                                                                                                                                                                     |
| 15  | dist-entry-lt             | `entry_time <= end_time` → `<`                                                                                                                                                                                                                | 1                               | TEST-GAP   | `…__mutmut_13`                                                                    | Boundary record at window end excluded. DRAFT T4.                                                                                                                                                                                                            |
| 16  | dist-or-to-and            | `(exit_time >= start)                                                                                                                                                                                                                         | (exit*time.is*(None))`→`&(...)` | 1          | TEST-GAP                                                                          | `…__mutmut_14`                                                                                                                                                                                                                                               | `exit >= start AND exit IS NULL` is a contradiction → all closed records vanish. DRAFT T4 (assert `OR` + `IS NULL` present). |
| 17  | dist-exit-gt              | `exit_time >= start_time` → `>`                                                                                                                                                                                                               | 1                               | TEST-GAP   | `…__mutmut_15`                                                                    | DRAFT T4.                                                                                                                                                                                                                                                    |
| 18  | dist-first-record         | `if records and records[0].zone is not None` → `records[1]` (24); `zone_name = records[0].zone.name` → `records[1]` (27)                                                                                                                      | 2                               | TEST-GAP   | `…__mutmut_24`, `…__mutmut_27`                                                    | Tests use one shared mock zone for ALL records (:566-572) and never a 1-record set → `records[1]` never raises / never differs. DRAFT T5                                                                                                                     |
| 19  | dist-guard-equiv          | `if total > 0 else 0.0` → `if (total > 0) or True` (37), `total >= 0` (41), `else 1.0` (43)                                                                                                                                                   | 3                               | EQUIVALENT | `…__mutmut_37`, `…__mutmut_41`, `…__mutmut_43`                                    | Unreachable-branch mutation: the loop only runs over non-empty `class_counts`, so `total >= 1` always; the false side never executes. Semantically identical — do not write a test.                                                                          |
| 20  | dist-total-gt1            | `total > 0` → `total > 1`                                                                                                                                                                                                                     | 1                               | TEST-GAP   | `…__mutmut_42`                                                                    | A zone with exactly ONE dwell record reports `percentage: 0.0` instead of 100.0. Smallest test set is 3 records. DRAFT T5                                                                                                                                    |
| 21  | dist-round                | `round(percentage, 2)` → `round(p, None)` (52) / `round(p,)` (54) / `round(p, 3)` (55)                                                                                                                                                        | 3                               | TEST-GAP   | `…__mutmut_52`, `…__mutmut_55`                                                    | 52/54 return **int** (Python: `round(x, None)` == `round(x)`); existing tests assert `== 60.0` / `== 100.0` so int-vs-float equality passes. Needs a fractional percentage (1/3 → 33.33 vs 33 vs 33.333). DRAFT T5                                           |
| 22  | log-payload               | pure logger call mutation across all four functions: message→None (re7/37, rx7/21, cl57), `extra={...}`→None or omitted (re8/10/38/40, rx8/10/22/24, cl58/60), dict-key renames `"k"→"XXkXX"`/`"K"` (re11-16, 41-50; rx11-14, 25-34; cl61-72) | 57                              | EQUIVALENT | `record_entry__mutmut_11`, `record_exit__mutmut_27`, `check_loitering__mutmut_63` | Changes only the log record's message text and `extra` payload; control flow, return values, DB calls untouched. No test asserts on log output (no caplog anywhere in the file). Recommend baseline suppression of `str` mutations for `logger.*` call args. |

**Counts:** 101 total = 40 TEST-GAP (clusters 1-6, 8-18, 20-21) + 1 LOW-VALUE (7) + 60 EQUIVALENT (19, 22).

## Covering test files (file:line)

- `backend/tests/unit/services/test_dwell_time_service.py` — the only unit coverage:
  - `TestLoiteringMetricsEmission` :27-366 (all mock `get_active_dwellers`; metric assertions only)
  - `TestRecordEntry` :374-424 (args of `get_active_record` never asserted; `add.assert_called_once()` at :400)
  - `TestRecordExit` :432-467 (loose `total_seconds >= 299` at :455)
  - `TestAlertTriggering` :475-526
  - `TestZoneEntityDistribution` :534-676 (mocks `db.execute` result; `stmt` discarded; exact-value asserts at :591, :641-649 all pass under `round(.,3)`/int-rounding)
- `backend/tests/integration/test_dwell_time_service.py` — only nonexistent-zone smoke tests (:63-68 `check_loitering` for zone 999999); exercises no query semantics. A real-row integration test would be the durable killer for clusters 12-17.

## Drafted tests (TDD)

All UNVERIFIED — not yet run red/green. Procedure per test: apply the cluster's mutant diff to `backend/services/dwell_time_service.py` → new test FAILS (red); revert to original → test PASSES (green). Style follows the existing mock-session tests in `backend/tests/unit/services/test_dwell_time_service.py`.

### T1 — kills clusters 1 + 2 (lookup args passed to get_active_record)

Add to `TestRecordEntry` (and the mirrored method to `TestRecordExit`):

```python
    @pytest.mark.asyncio
    async def test_record_entry_queries_lookup_with_zone_and_track(self) -> None:
        """Verify get_active_record is scoped by BOTH zone_id and track_id."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        service = DwellTimeService(mock_db)

        with patch.object(
            service, "get_active_record", return_value=None, autospec=True
        ) as mock_lookup:
            await service.record_entry(
                zone_id=42,
                track_id=100,
                camera_id="camera-001",
                object_class="person",
            )

            args = mock_lookup.call_args.args  # (zone_id, track_id) as called on the instance
            assert args[0] == 42, "lookup must be scoped to the entered zone"
            assert args[1] == 100, "lookup must be scoped to the tracked object"

    # TestRecordExit counterpart (kills record_exit__mutmut_2/_3):
    @pytest.mark.asyncio
    async def test_record_exit_queries_lookup_with_zone_and_track(self) -> None:
        """Verify record_exit scopes its lookup by zone_id AND track_id."""
        mock_db = AsyncMock()

        service = DwellTimeService(mock_db)

        with patch.object(
            service, "get_active_record", return_value=None, autospec=True
        ) as mock_lookup:
            await service.record_exit(zone_id=42, track_id=100)

            args = mock_lookup.call_args.args
            assert args[0] == 42
            assert args[1] == 100
```

// UNVERIFIED - not yet run red/green. Red under `get_active_record(None, track_id)` / `(zone_id, None)`; green on original.

### T2 — kills clusters 8, 9, 10 (threshold boundary + clock propagation) — highest value

Add to `TestLoiteringMetricsEmission`:

```python
    @pytest.mark.asyncio
    async def test_check_loitering_alerts_at_exact_threshold_using_current_time(self) -> None:
        """Record dwelling EXACTLY at threshold must alert, computed from caller's clock."""
        mock_db = AsyncMock()

        fixed_now = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)

        mock_record = MagicMock(spec=DwellTimeRecord)
        mock_record.id = 1
        mock_record.zone_id = 42
        mock_record.track_id = 100
        mock_record.camera_id = "camera-001"
        mock_record.object_class = "person"
        mock_record.entry_time = fixed_now - timedelta(seconds=300)
        mock_record.triggered_alert = True  # already triggered: no metric side-effects to patch
        mock_record.calculate_dwell_time = MagicMock(return_value=300.0)  # EXACTLY threshold
        mock_record.zone = None

        service = DwellTimeService(mock_db)

        with patch.object(
            service, "get_active_dwellers", return_value=[mock_record], autospec=True
        ):
            alerts = await service.check_loitering(
                zone_id=42, threshold_seconds=300.0, current_time=fixed_now
            )

            # Dwell must be evaluated AT the caller-supplied time (kills mutmut_1/_2/_11)
            mock_record.calculate_dwell_time.assert_called_once_with(fixed_now)
            # Threshold comparison is INCLUSIVE: dwell == threshold must alert (kills mutmut_12)
            assert len(alerts) == 1
            assert alerts[0].dwell_seconds == 300.0
            assert alerts[0].threshold_seconds == 300.0
```

// UNVERIFIED - not yet run red/green. Red under `if dwell_seconds > threshold_seconds` (alerts == []) and under `calculate_dwell_time(None)` / `current_time and utc_now()` (call-arg mismatch); green on original.

### T3 — kills cluster 11 (get_active_dwellers call contract)

```python
    @pytest.mark.asyncio
    async def test_check_loitering_loads_zone_for_requested_zone_only(self) -> None:
        """check_loitering must query the requested zone with load_zone=True."""
        mock_db = AsyncMock()
        service = DwellTimeService(mock_db)

        with patch.object(service, "get_active_dwellers", return_value=[], autospec=True) as mock_dw:
            await service.check_loitering(zone_id=42, threshold_seconds=300.0)

            call = mock_dw.call_args
            assert 42 in call.args, "must query the requested zone, not None"
            assert call.kwargs.get("load_zone") is True, "zone must be eager-loaded for metrics"
```

// UNVERIFIED. Red under `get_active_dwellers(None, load_zone=True)` (mutmut_5), `load_zone=None` (6), `load_zone=False` (9), and the kwarg-omitted variant (8); green on original.

### T4 — kills clusters 12-17 (distribution WHERE semantics)

Add to `TestZoneEntityDistribution`:

```python
    @pytest.mark.asyncio
    async def test_get_zone_entity_distribution_builds_window_and_zone_filter(self) -> None:
        """The executed statement must carry zone + window + active-or-exited predicates."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DwellTimeService(mock_db)
        start = datetime(2026, 9, 17, 0, 0, 0, tzinfo=UTC)
        end = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)

        await service.get_zone_entity_distribution(zone_id=42, start_time=start, end_time=end)

        stmt = mock_db.execute.call_args.args[0]
        assert stmt is not None, "must execute a real statement"
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        assert "dwell_time_records.zone_id = 42" in sql          # kills mutmut_6/9 (None/deleted), _12 (!=)
        assert "entry_time <= " in sql                            # kills mutmut_7/10, _13 (<)
        assert "entry_time < " not in sql
        assert "exit_time >= " in sql                             # kills mutmut_15 (>)
        assert "exit_time > " not in sql
        assert " OR " in sql and "IS NULL" in sql                 # kills mutmut_8/11 (clause removed), _14 (&)
```

// UNVERIFIED. Red under `stmt=None`/`select(None)`/`execute(None)` (mutmut_1/4/17 — raise or stmt None), each deleted conjunct (9/10/11), `!=` (12), `<` (13), `&` (14), `>` (15); green on original. Note: if the team prefers, a real-row integration test (seed two zones, one boundary-exit record) is the more durable killer — current integration file has no real rows.

### T5 — kills clusters 18, 20, 21 (zone-name first record, single-entity percentage, rounding)

```python
    @pytest.mark.asyncio
    async def test_get_zone_entity_distribution_single_record_and_fractional_percent(self) -> None:
        """One record => 100.0%; fractions rounded to exactly 2 decimals; zone name from FIRST record."""
        # Scenario 1: 1 person + 2 vehicles => 66.67 / 33.33 (kills round-None/int and round-3)
        zone_a = MagicMock()
        zone_a.name = "Driveway"
        records = []
        for cls in ("vehicle", "vehicle", "person"):
            r = MagicMock(spec=DwellTimeRecord)
            r.object_class = cls
            r.zone = zone_a
            records.append(r)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DwellTimeService(mock_db)
        result = await service.get_zone_entity_distribution(
            zone_id=1,
            start_time=datetime(2026, 9, 17, 0, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC),
        )
        assert result["total_entities"] == 3
        assert result["entity_types"][0] == {"entity_type": "vehicle", "count": 2, "percentage": 66.67}
        assert result["entity_types"][1] == {"entity_type": "person", "count": 1, "percentage": 33.33}

        # Scenario 2: exactly ONE record => 100.0% (kills mutmut_42 total > 1),
        # zone name taken from records[0] (kills mutmut_24 IndexError / mutmut_27 wrong name)
        zone_b = MagicMock()
        zone_b.name = "Front Yard"
        lone = MagicMock(spec=DwellTimeRecord)
        lone.object_class = "person"
        lone.zone = zone_b
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [lone]
        mock_db2 = AsyncMock()
        mock_db2.execute = AsyncMock(return_value=mock_result2)

        service2 = DwellTimeService(mock_db2)
        result2 = await service2.get_zone_entity_distribution(
            zone_id=1,
            start_time=datetime(2026, 9, 17, 0, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC),
        )
        assert result2["zone_name"] == "Front Yard"
        assert result2["entity_types"][0]["percentage"] == 100.0
```

// UNVERIFIED. Red under `total > 1` (0.0 != 100.0), `round(p, None)`/`round(p,)` (33 != 33.33 via exact dict equality), `round(p, 3)` (33.333), `records[1]` (IndexError on the one-record set); green on original. (33.33 dict-equality also pins `round(.,2)` vs int — int 33 != float 33.33.)

### T6 — kills clusters 3, 4, 5 (+ one-line extension of cluster 6)

Add to `TestRecordEntry`:

```python
    @pytest.mark.asyncio
    async def test_record_entry_persists_exact_record_with_defaulted_entry_time(self) -> None:
        """Entry defaults entry_time to utc_now, starts total_seconds at 0.0, and persists THAT record."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        service = DwellTimeService(mock_db)
        fixed_now = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)

        with patch.object(service, "get_active_record", return_value=None, autospec=True):
            # Explicit entry_time must be stored verbatim (kills mutmut_22/_29/_32)
            explicit = fixed_now - timedelta(minutes=3)
            with patch("backend.services.dwell_time_service.utc_now", return_value=fixed_now):
                record = await service.record_entry(
                    zone_id=42,
                    track_id=100,
                    camera_id="camera-001",
                    object_class="person",
                    entry_time=explicit,
                )
                assert record.entry_time == explicit
                assert record.total_seconds == 0.0  # kills mutmut_23 (None) / _30 (deleted) / _33 (1.0)

            # Omitted entry_time defaults to utc_now() (kills mutmut_22/_29/_32 on the default branch)
            record2 = await service.record_entry(
                zone_id=42,
                track_id=101,
                camera_id="camera-001",
                object_class="person",
            )
            assert record2.entry_time == fixed_now

            # The record ADDED/REFRESHED must be the returned one (kills mutmut_35/_36)
            mock_db.add.assert_any_call(record)
            mock_db.refresh.assert_any_await(record)
```

And the cluster-6 one-liner: in `TestRecordExit::test_record_exit_updates_record_with_dwell_time` (:435), change the existing `mock_db.refresh` coverage to `mock_db.refresh.assert_awaited_once_with(mock_record)` — kills `record_exit__mutmut_20`.

// UNVERIFIED - not yet run red/green. Red under each clobbered kwarg/target (entry_time None/deleted/`and`-swapped, total_seconds None/deleted/1.0, add(None)/refresh(None)); green on original. (`assert_any_call` because the second call adds `record2`.)

## Notes for the WP4.4 baseline owner

- **Suppress candidate:** cluster 22 (57 survivors, 56% of this module's residue) is pure log-text mutation. If the mutmut config can skip string constants that are arguments to `logger.*` calls, the module's honest score jumps from 119/220 to 176/220-equivalent.
- **Do not chase:** cluster 19 (unreachable `total == 0` guard arm — EQUIVALENT by construction) and cluster 7 (model-internal fallback makes `now=None` unobservable — LOW-VALUE).
- **Durable fix beyond these drafts:** clusters 12-17 live in SQL no unit test can see; a seeded integration test in `backend/tests/integration/test_dwell_time_service.py` (two zones, one record exiting exactly at `start_time`, one record entering exactly at `end_time`) would kill the whole query cluster family permanently.
