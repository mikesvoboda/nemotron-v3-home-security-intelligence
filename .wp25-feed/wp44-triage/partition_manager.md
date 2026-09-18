# WP4.4 Triage Dossier — backend/services/partition_manager.py

- **Run**: mutation baseline (live run in progress; cache may still hold `null` verdicts)
- **Meta**: `mutants/backend/services/partition_manager.py.meta` — 733 total, 150 killed, **436 unchecked**, 147 SURVIVED (triaged here; the 436 unchecked will likely add survivors later).
- **Diff extraction**: per-mutant variants in `mutants/backend/services/partition_manager.py` diffed against each `__mutmut_orig` copy (mechanical; scratch: `/tmp/pm_survivor_diffs.txt`).
- **Covering tests** (from `mutants/mutmut-stats.json::tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_partition_manager.py` — `_check_partition_exists` (:282-311), `_create_partition` (:314-332), `_drop_partition` (:335-349), `get_partition_stats` (:516-552)
  - `backend/tests/unit/services/test_partition_enhancements.py` — conversion SQL (:27-69), indexes (:81-125), pruning hint (:136-177), interval/retention (:188-236), balance (:248-324), gaps (:327-361), metadata/size (:372-408)

## Cluster table (147 survivors = 95 TEST-GAP, 48 EQUIVALENT, 4 LOW-VALUE)

| #     | Cluster                                                         | Pattern                                                                                                                             | N   | Class      | Example keys (fn `__mutmut_n`)                                                 | Killable by                                                                                                                    |
| ----- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --- | ---------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| CPE-1 | `_check_partition_exists` query-arg mutations                   | SQL text/params args to `session.execute` replaced by `None`/renamed param key/`text()` wrapper dropped                             | 6   | TEST-GAP   | `_check_partition_exists__mutmut_2`, `_3`, `_7`                                | Draft F — mock session records call but test (:282-311) asserts only the bool return                                           |
| CP-1  | `_create_partition` SQL construction                            | `table_name=None`, `strftime("%Y-%m-%d")` → `None`/`XX…XX`/`%y-%m-%d`/`%Y-%M-%D` on start/end bounds                                | 9   | TEST-GAP   | `_create_partition__mutmut_1`, `_5`, `_12`                                     | Draft F — test (:314-332) only asserts `"CREATE TABLE" in sql or "PARTITION" in sql`                                           |
| CP-2  | log payload mutations (`_create_partition` + `_drop_partition`) | `logger.info` message → `None`, `extra={...}` → `None`/dict-key renames                                                             | 12  | EQUIVALENT | `_create_partition__mutmut_18`, `_22`, `_drop_partition__mutmut_6`             | log text, no program state                                                                                                     |
| GPS-1 | `get_partition_stats` call-arg mutations                        | `self._list_partitions(session, config)` args → `None`                                                                              | 2   | TEST-GAP   | `get_partition_stats__mutmut_3`, `_4`                                          | Draft E — test (:516-552) fully mocks `_list_partitions`, never inspects its args                                              |
| GPS-2 | `get_partition_stats` output-dict keys                          | `start_date`/`end_date`/`is_expired` keys renamed                                                                                   | 6   | TEST-GAP   | `get_partition_stats__mutmut_10`, `_12`, `_16`                                 | Draft E — test asserts only `name` and `row_count`                                                                             |
| PH-1  | pruning hint early-return dict keys                             | `table`/`column`/`partitions`/`message` keys renamed                                                                                | 8   | TEST-GAP   | `get_partition_pruning_hint__mutmut_4`, `_6`, `_11`                            | Draft B — test (:168-177) asserts only `all_partitions`                                                                        |
| PH-2  | pruning hint early-return message text                          | message string case/wrap mutations                                                                                                  | 3   | EQUIVALENT | `_15`, `_16`, `_17`                                                            | pure message text                                                                                                              |
| PH-3  | pruning hint range-branch dict keys                             | `table`/`column`/`all_partitions`/`partition_count`/`message` keys renamed                                                          | 10  | TEST-GAP   | `_42`, `_46`, `_51`                                                            | Draft B — tests (:136-166) assert only `partitions` list                                                                       |
| PH-4  | pruning hint `all_partitions` flag                              | `"all_partitions": False` → `True` in range branch                                                                                  | 1   | TEST-GAP   | `_48`                                                                          | Draft B                                                                                                                        |
| PH-5  | pruning hint date-guard boolean mutations                       | `and`→`or` on both-None guard; `if x is None` → `is not None` default-overwrite flips                                               | 3   | TEST-GAP   | `_1`, `_21`, `_22`                                                             | Draft B — no test passes exactly one None bound                                                                                |
| PH-6  | pruning hint month-walk boundary/step                           | `while current <= end` → `<`; `month == 12` → `== 13` (ValueError on Dec rollover); step day `1`→`2` drift                          | 3   | TEST-GAP   | `_24`, `_29`, `_41`                                                            | Draft B — test ranges never touch a month-boundary end or cross Dec→Jan                                                        |
| RPI-1 | `recommend_partition_interval` 1M threshold                     | `> 1_000_000` → `>=` / `> 1000001`                                                                                                  | 2   | TEST-GAP   | `recommend_partition_interval__mutmut_1`, `_2`                                 | Draft D — test uses 5M / 50K only                                                                                              |
| RPI-2 | `recommend_partition_interval` "recent" branch                  | `== "recent"` → `!=` / `"XXrecentXX"` / `"RECENT"`                                                                                  | 3   | TEST-GAP   | `_3`, `_4`, `_5`                                                               | Draft D — test asserts `interval in ("weekly","monthly")`: kills nothing                                                       |
| RRP-1 | `recommend_retention_period` compliance set members             | `"audit_logs"`/`"events"`/`"alerts"` members renamed in `compliance_tables`                                                         | 6   | TEST-GAP   | `recommend_retention_period__mutmut_2`, `_4`, `_6`                             | Draft A — test (:216-236) asserts `retention >= 12` / `<= 6` bounds, not values                                                |
| RRP-2 | `recommend_retention_period` case-normalization                 | `table_name.lower()` → `.upper()` (both lookups)                                                                                    | 2   | TEST-GAP   | `_9`, `_19`                                                                    | Draft A — mixed-case table name never passed                                                                                   |
| RRP-3 | `recommend_retention_period` condition boolean mutations        | `and`→`or`; `in`→`not in` on membership conditions                                                                                  | 3   | TEST-GAP   | `_8`, `_10`, `_20`                                                             | Draft A — needs negative pairs (compliance-table with `compliance=False`, etc.)                                                |
| RRP-4 | `recommend_retention_period` return constants                   | `return 24`→`25`, `return 3`→`4`                                                                                                    | 2   | TEST-GAP   | `_11`, `_21`                                                                   | Draft A — loose `>=12`/`<=6` assertions admit both                                                                             |
| RRP-5 | `recommend_retention_period` short-retention set members        | `"gpu_stats"`/`"metrics"`/`"logs"` members renamed                                                                                  | 6   | TEST-GAP   | `_13`, `_15`, `_17`                                                            | Draft A — `metrics`/`logs` never exercised                                                                                     |
| CB-1  | `check_partition_balance` zero/one-count thresholds             | `row_count > 0` → `>= 0` / `> 1`; `avg_rows > 0` → `> 1`                                                                            | 3   | TEST-GAP   | `check_partition_balance__mutmut_3`, `_4`, `_18`                               | Draft C — test data never contains row_count 0 or 1                                                                            |
| CB-2  | `check_partition_balance` `min_rows` value                      | `min(row_counts)` → `None`                                                                                                          | 1   | TEST-GAP   | `_11`                                                                          | Draft C — `min_rows` never read by test (:248-263)                                                                             |
| CB-3  | dead-guard boolean mutations                                    | `avg_rows > 0` → `… or True` / `>= 0`; unreachable `else 0`→`1`; `if partitions … or True` (early-return makes guards tautological) | 4   | EQUIVALENT | `_15`, `_17`, `_19`, `_28`                                                     | filter `>0` + early returns guarantee guard conditions true on all reachable inputs                                            |
| CB-4  | `check_partition_balance` balance threshold boundary            | `variance_ratio <= 3.0` → `< 3.0`                                                                                                   | 1   | TEST-GAP   | `_21`                                                                          | Draft C — test ratios are 1.03 and 3.98, never exactly 3.0                                                                     |
| CB-6  | `check_partition_balance` output-dict keys                      | `average_rows`/`max_rows`/`min_rows` keys renamed                                                                                   | 6   | TEST-GAP   | `_33`, `_36`, `_38`                                                            | Draft C — test reads only `balanced`, `variance`, `largest_partition`                                                          |
| CB-7  | balance message key + pick flip                                 | `message` key renamed; `if balanced` → `and False`/`or True` (wrong message vs flag)                                                | 4   | LOW-VALUE  | `_42`, `_44`, `_45`                                                            | message is cosmetic display text; not worth a dedicated assertion (Draft C's key-set check kills the renames as a side effect) |
| CB-8  | balance message text value                                      | both message strings case/wrapped                                                                                                   | 6   | EQUIVALENT | `_46`, `_49`, `_51`                                                            | pure message text                                                                                                              |
| IPG-1 | `identify_partition_gaps` month-walk boundary/step              | `current < max_date` → `<=`; `month == 12` → `== 13`; step day `1`→`2`                                                              | 3   | TEST-GAP   | `identify_partition_gaps__mutmut_10`, `_18`, `_30`                             | Draft D — test (:327-361) asserts `any("2026m02" in gap)`, not exact list                                                      |
| CS-1  | conversion SQL comment text                                     | all `-- Step N: …` comment strings + `""` separators mutated in the statements list                                                 | 22  | EQUIVALENT | `generate_partition_conversion_sql__mutmut_6`, `_9`, `_13`                     | SQL comments/blank separators; tests (:27-69) correctly assert only real SQL                                                   |
| IDX-1 | `generate_partition_indexes` index-name interpolation           | `btree_idx_name`/`brin_idx_name` f-strings → `None` (index named "None")                                                            | 2   | TEST-GAP   | `generate_partition_indexes__mutmut_6`, `_8`                                   | Draft D — BRIN test (:112-125) uses an `or` disjunction; name never asserted                                                   |
| PM-1  | `get_partition_metadata` output-dict keys                       | `start_date`/`end_date` keys renamed                                                                                                | 4   | TEST-GAP   | `get_partition_metadata__mutmut_7`, `_9`, `_10`                                | Draft D — test (:372-393) asserts name/table/row_count/days_covered only                                                       |
| PM-2  | size-estimate constant mutations                                | `1024*1024` → `1025*1024`/`1024*1025`; `avg_row_size_bytes=500` → `501`                                                             | 3   | TEST-GAP   | `estimate_partition_size__mutmut_8`, `_9`, `get_partition_metadata__mutmut_21` | Draft D — test (:395-408) uses a 40–60 MB band                                                                                 |
| PM-3  | metadata default-arg removal                                    | `avg_row_size_bytes=500` kwarg dropped → resolves to same default                                                                   | 1   | EQUIVALENT | `get_partition_metadata__mutmut_20`                                            | identical result                                                                                                               |

Totals: TEST-GAP 95, EQUIVALENT 48, LOW-VALUE 4 → **147** (±0).

Highest-value drafted tests (Drafts A–F below) collectively kill all 95 TEST-GAP survivors (CB-7's 4 renames die as a side effect of Draft C, but stay classified LOW-VALUE).

## TDD procedure (one line)

For each draft: add it to the target file, run it against the mutant copy (or `mutmut run` scope) — the new assertion must FAIL on the cluster's mutant diff (red) and PASS on `backend/services/partition_manager.py` unchanged (green), before committing.

## Drafted tests

All UNVERIFIED — not yet run red/green (test execution forbidden in this sandbox session). Style follows each target file (lazy imports inside test bodies).

### Draft A — `recommend_retention_period` exact matrix (kills RRP-1..5, 19 survivors)

Target: `backend/tests/unit/services/test_partition_enhancements.py` (class `TestTimeSeriesOptimization`)

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.parametrize(
        ("table", "compliance", "expected"),
        [
            ("audit_logs", True, 24),
            ("events", True, 24),
            ("alerts", True, 24),
            ("Audit_Logs", True, 24),   # case-insensitive membership (kills .upper() mutants)
            ("detections", True, 12),   # compliance minimum, non-compliance table
            ("audit_logs", False, 6),   # non-compliance lookup of a compliance table
            ("gpu_stats", False, 3),
            ("GPU_STATS", False, 3),    # case-insensitive short-retention lookup
            ("metrics", False, 3),
            ("logs", False, 3),
            ("detections", False, 6),   # default retention
        ],
    )
    def test_retention_recommendation_exact_values(
        self, table: str, compliance: bool, expected: int
    ) -> None:
        """Each (table, compliance) pair must return its exact documented retention months."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()
        assert manager.recommend_retention_period(
            table_name=table, compliance_requirements=compliance
        ) == expected
```

Red/green: every row fails on its corresponding set-member / condition-flip / constant mutant; all pass on original.

### Draft B — `get_partition_pruning_hint` full contract (kills PH-1, PH-3, PH-4, PH-5, PH-6 = 25 survivors)

Target: `backend/tests/unit/services/test_partition_enhancements.py` (class `TestPartitionPruning`)

```python
    # UNVERIFIED - not yet run red/green
    EARLY_KEYS = {"table", "column", "all_partitions", "partitions", "message"}
    RANGE_KEYS = {"table", "column", "all_partitions", "partitions", "partition_count", "message"}

    def test_pruning_hint_no_bounds_contract(self) -> None:
        """Both-bounds-None branch: exact key set and flag values."""
        from backend.services.partition_manager import PartitionManager

        hint = PartitionManager().get_partition_pruning_hint("t", "c", None, None)
        assert set(hint) == self.EARLY_KEYS
        assert hint["all_partitions"] is True
        assert hint["partitions"] == []

    def test_pruning_hint_single_bound_defaults(self) -> None:
        """Only one bound given: the other must be defaulted, not overwritten when present."""
        from datetime import UTC, datetime

        from backend.services.partition_manager import PartitionManager

        end = datetime(2026, 2, 1, tzinfo=UTC)
        hint = PartitionManager().get_partition_pruning_hint("t", "c", None, end)
        assert hint["all_partitions"] is False  # kills and->or guard mutant
        assert hint["partitions"][0] == "t_y2020m01"
        assert hint["partitions"][-1] == "t_y2026m02"
        assert hint["partition_count"] == 74  # Jan 2020 .. Feb 2026 inclusive

    def test_pruning_hint_month_boundary_end(self) -> None:
        """Range ending exactly on a month start must include that month."""
        from datetime import UTC, datetime

        from backend.services.partition_manager import PartitionManager

        start = datetime(2026, 1, 31, 23, 59, 59, tzinfo=UTC)
        end = datetime(2026, 2, 1, tzinfo=UTC)
        hint = PartitionManager().get_partition_pruning_hint("t", "c", start, end)
        assert hint["partitions"] == ["t_y2026m01", "t_y2026m02"]  # kills <=/> and day-2 step
        assert hint["all_partitions"] is False
        assert set(hint) == self.RANGE_KEYS

    def test_pruning_hint_year_rollover(self) -> None:
        """Dec->Jan walk must step years without raising."""
        from datetime import UTC, datetime

        from backend.services.partition_manager import PartitionManager

        start = datetime(2026, 12, 15, tzinfo=UTC)
        end = datetime(2027, 1, 15, tzinfo=UTC)
        hint = PartitionManager().get_partition_pruning_hint("t", "c", start, end)
        assert hint["partitions"] == ["t_y2026m12", "t_y2027m01"]  # month==13 mutant raises ValueError
```

### Draft C — `check_partition_balance` exact contract (kills CB-1, CB-2, CB-4, CB-6 = 11; renames in CB-7 die too)

Target: `backend/tests/unit/services/test_partition_enhancements.py` (class `TestPartitionHealthChecks`)

```python
    # UNVERIFIED - not yet run red/green
    def test_balance_result_contract(self) -> None:
        """Balanced case: exact key set and every numeric field."""
        from datetime import UTC, datetime

        from backend.services.partition_manager import PartitionInfo, PartitionManager

        now = datetime.now(UTC)
        parts = [
            PartitionInfo("p1", "detections", now, now, row_count=1000),
            PartitionInfo("p2", "detections", now, now, row_count=1100),
            PartitionInfo("p3", "detections", now, now, row_count=900),
        ]
        health = PartitionManager().check_partition_balance(parts)
        assert set(health) == {
            "balanced", "variance", "average_rows", "max_rows", "min_rows",
            "largest_partition", "message",
        }
        assert health["balanced"] is True
        assert health["variance"] == 1.1
        assert health["average_rows"] == 1000
        assert health["max_rows"] == 1100
        assert health["min_rows"] == 900  # kills min->None mutant
        assert health["largest_partition"] == "p2"

    def test_balance_threshold_exactly_3x(self) -> None:
        """ratio == 3.0 must still count as balanced (<= 3.0, not < 3.0)."""
        from datetime import UTC, datetime

        from backend.services.partition_manager import PartitionInfo, PartitionManager

        now = datetime.now(UTC)
        parts = [
            PartitionInfo("p1", "detections", now, now, row_count=900),
            PartitionInfo("p2", "detections", now, now, row_count=100),
            PartitionInfo("p3", "detections", now, now, row_count=100),
            PartitionInfo("p4", "detections", now, now, row_count=100),
        ]  # avg 300, ratio exactly 3.0
        health = PartitionManager().check_partition_balance(parts)
        assert health["variance"] == 3.0
        assert health["balanced"] is True

    def test_balance_ignores_zero_and_honours_one_counts(self) -> None:
        """row_count 0 partitions are excluded; a count of 1 is not."""
        from datetime import UTC, datetime

        from backend.services.partition_manager import PartitionInfo, PartitionManager

        now = datetime.now(UTC)
        parts = [
            PartitionInfo("p1", "detections", now, now, row_count=1),
            PartitionInfo("p2", "detections", now, now, row_count=0),
            PartitionInfo("p3", "detections", now, now, row_count=0),
        ]
        health = PartitionManager().check_partition_balance(parts)
        assert health["variance"] == 1.0
        assert health["average_rows"] == 1
        assert health["min_rows"] == 1
        assert health["max_rows"] == 1
        assert health["largest_partition"] == "p1"
```

(For `[1,0,0]`: `> 0` filter keeps `[1]`; the `>= 0` mutant yields ratio 3.0 / average_rows 0, the `> 1` mutant takes the "No row count data" early return (key-set mismatch), and the `avg_rows > 1` guard mutant yields variance 0 — each fails at least one assert.)

### Draft D — interval / gaps / indexes / metadata exactness (kills RPI-1, RPI-2, IPG-1, IDX-1, PM-1, PM-2 = 17 survivors)

Target: `backend/tests/unit/services/test_partition_enhancements.py`

```python
    # UNVERIFIED - not yet run red/green
    def test_partition_interval_threshold(self) -> None:
        """1M-row boundary and the 'recent' branch must return exact intervals."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()
        assert manager.recommend_partition_interval(1_000_000, "recent") == "monthly"
        assert manager.recommend_partition_interval(1_000_001, "recent") == "weekly"
        assert manager.recommend_partition_interval(5_000_000, "historical") == "monthly"

    def test_identify_gaps_exact_year_rollover(self) -> None:
        """Gaps must be the exact sorted missing set, incl. Dec rollover and boundary end.

        Two end-date shapes are needed: an end landing exactly on a month start
        (kills the ``<`` -> ``<=`` mutant, which would emit a spurious y2027m02) and
        an end one day past the month start (kills the day-1 -> day-2 step mutant,
        which would drop y2027m02). Both cross Dec -> Jan, killing month==13 (ValueError).
        """
        from datetime import UTC, datetime

        from backend.services.partition_manager import (
            PartitionConfig,
            PartitionInfo,
            PartitionManager,
        )

        config = PartitionConfig("detections", "detected_at", "monthly")

        def part(name: str, start: datetime, end: datetime) -> PartitionInfo:
            return PartitionInfo(name, "detections", start, end)

        # End exactly at a month start: y2027m01 ends 2027-02-01 -> y2027m02 NOT expected
        existing = [
            part("detections_y2026m11", datetime(2026, 11, 1, tzinfo=UTC),
                 datetime(2026, 12, 1, tzinfo=UTC)),
            part("detections_y2027m01", datetime(2027, 1, 1, tzinfo=UTC),
                 datetime(2027, 2, 1, tzinfo=UTC)),
        ]
        assert PartitionManager().identify_partition_gaps(config, existing) == [
            "detections_y2026m12"
        ]

        # End one day past the month start: y2027m02 IS expected (walk visits 2027-02-01)
        existing[1] = part("detections_y2027m01", datetime(2027, 1, 1, tzinfo=UTC),
                           datetime(2027, 2, 2, tzinfo=UTC))
        assert PartitionManager().identify_partition_gaps(config, existing) == [
            "detections_y2026m12",
            "detections_y2027m02",
        ]

    def test_generated_index_names_exact(self) -> None:
        """Index statements carry the exact idx_{partition}_{column}[{,_brin}] names."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        config = PartitionConfig("detections", "detected_at", "monthly")
        sql = PartitionManager().generate_partition_indexes(config, "detections_y2026m01")
        assert sql == [
            "CREATE INDEX IF NOT EXISTS idx_detections_y2026m01_detected_at "
            "ON detections_y2026m01 USING btree (detected_at);"
        ]
        sql_brin = PartitionManager().generate_partition_indexes(
            config, "detections_y2026m01", include_brin=True
        )
        assert sql_brin[1] == (
            "CREATE INDEX IF NOT EXISTS idx_detections_y2026m01_detected_at_brin "
            "ON detections_y2026m01 USING brin (detected_at);"
        )

    def test_partition_metadata_dates_and_size_exact(self) -> None:
        """start/end date keys and the size estimate must be exact, not just present."""
        from datetime import UTC, datetime

        from backend.services.partition_manager import PartitionInfo, PartitionManager

        info = PartitionInfo(
            name="detections_y2026m01",
            table_name="detections",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 2, 1, tzinfo=UTC),
            row_count=5000,
        )
        manager = PartitionManager()
        meta = manager.get_partition_metadata(info)
        assert meta["start_date"] == "2026-01-01T00:00:00+00:00"
        assert meta["end_date"] == "2026-02-01T00:00:00+00:00"
        assert meta["size_estimate_mb"] == pytest.approx(
            5000 * 500 * 1.2 / (1024 * 1024)
        )
        assert manager.estimate_partition_size(100_000, 500) == pytest.approx(
            100_000 * 500 * 1.2 / (1024 * 1024)
        )
```

### Draft E — `get_partition_stats` inner-dict contract (kills GPS-1, GPS-2 = 8 survivors)

Target: `backend/tests/unit/services/test_partition_manager.py` (extend `test_get_partition_stats` or add alongside at :516-552)

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_get_partition_stats_entry_contract(self) -> None:
        """Each stats entry exposes exactly the documented keys, and the real session/config
        must reach _list_partitions."""
        from backend.services.partition_manager import (
            PartitionConfig,
            PartitionInfo,
            PartitionManager,
        )

        config = PartitionConfig("detections", "detected_at", "monthly")
        manager = PartitionManager(configs=[config])

        now = datetime.now(UTC)
        partition = PartitionInfo(
            name="detections_y2026m01",
            table_name="detections",
            start_date=datetime(now.year, 1, 1, tzinfo=UTC),
            end_date=datetime(now.year, 2, 1, tzinfo=UTC),
            row_count=5000,
        )
        mock_session = AsyncMock()

        with (
            patch.object(
                manager, "_list_partitions", return_value=[partition], autospec=True
            ) as mock_list,
            patch(
                "backend.services.partition_manager.get_session", autospec=True
            ) as mock_get_session,
        ):
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await manager.get_partition_stats()

        call_args = mock_list.call_args[0]
        assert any(a is mock_session for a in call_args)  # kills session->None mutant
        assert any(a is config for a in call_args)  # kills config->None mutant

        entry = stats["detections"][0]
        assert set(entry) == {"name", "start_date", "end_date", "row_count", "is_expired"}
        assert entry["start_date"] == datetime(now.year, 1, 1, tzinfo=UTC).isoformat()
        assert entry["end_date"] == datetime(now.year, 2, 1, tzinfo=UTC).isoformat()
        assert entry["is_expired"] is False
```

### Draft F — `_check_partition_exists` + `_create_partition` executed-SQL assertions (kills CPE-1, CP-1 = 15 survivors)

Target: `backend/tests/unit/services/test_partition_manager.py` (class `TestPartitionManager`, near :282-332)

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_check_partition_exists_executes_parameterized_query(self) -> None:
        """The executed statement must be a text() query with the :name bind intact."""
        from sqlalchemy import text as sqla_text

        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "detections_y2026m01"
        mock_session.execute.return_value = mock_result

        await manager._check_partition_exists(mock_session, "detections_y2026m01")

        stmt, params = mock_session.execute.call_args[0]
        assert isinstance(stmt, type(sqla_text("")))  # kills wrapper-removal / None mutants
        assert "pg_class" in str(stmt) and "relkind = 'r'" in str(stmt)
        assert params == {"name": "detections_y2026m01"}  # kills None / renamed-key mutants

    @pytest.mark.asyncio
    async def test_create_partition_sql_bounds_exact(self) -> None:
        """Generated DDL must embed the sanitized table and exact ISO date bounds."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")
        mock_session = AsyncMock()
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 2, 1, tzinfo=UTC)

        await manager._create_partition(
            mock_session, config, "detections_y2026m01", start, end
        )

        sql_text = str(mock_session.execute.call_args[0][0])
        assert "CREATE TABLE IF NOT EXISTS detections_y2026m01" in sql_text
        assert "PARTITION OF detections" in sql_text
        assert "FROM ('2026-01-01')" in sql_text  # kills strftime-format mutants
        assert "TO ('2026-02-01')" in sql_text
```

## Notes

- The 436 `null` (not-yet-checked) keys are excluded; when the live run finishes, re-diff this meta — expect additional survivors to land in the same clusters (the pattern taxonomy is complete at line level: every mutation site with at least one checked survivor is represented).
- CB-3 / PM-3 / CS-1 / CP-2 / PH-2 / CB-8 EQUIVALENT calls assume no test ever asserts on log output or unreachable branches; if the project later adds structlog capture assertions, revisit.
- `mutmut show <key>` was not needed — the copy-vs-orig diff method covered all 147 keys mechanically without touching the cache.
