# WP4.4 Triage Dossier — backend/services/baseline.py

Generated: 2026-09-17. Source: `mutants/backend/services/baseline.py.meta` (`exit_code == 0` keys).

**Snapshot caveat: the mutation run is still in flight.** 766 total mutant keys,
333 verdicts at read time: 216 killed, **117 survived**, 433 still `null` (unchecked).
This dossier triages the 117 survivors that exist now; re-run this triage (cheap — the
key→diff pipeline below) once the remaining verdicts land.

Pipeline used (reusable): parse meta → surviving keys (`/tmp/wp25/wp44-triage/keys.txt`) →
`uv run mutmut show <key>` batch-dumped to `/tmp/wp25/wp44-triage/diffs/all.diff` →
compact one-line-per-mutant view at `/tmp/wp25/wp44-triage/diffs/compact.txt`.

## Why so many survive (root cause — read this before the table)

`backend/tests/unit/services/test_baseline.py` drives every DB method with
`AsyncMock()` sessions: the code *builds* a SQLAlchemy `select(...)` and hands it to
`sess.execute(stmt)`, but the mock ignores the argument and replays a canned result.
Consequently **every mutation inside any `select(...)` expression is invisible**:
`where(None)`, dropped `==` clauses, `==`→`!=`, `order_by` surgery, even
`stmt = None` / `execute(None)` all return the canned row unchanged (a real DB would
raise or return wrong rows). That single test-design fact explains 59 of the 117
survivors (clusters C3–C7 + summary statement mutants). The fix pattern already exists
in this repo: `backend/tests/unit/services/test_search.py:519-553` captures the built
statement and asserts on its compiled SQL text. Drafted test T1 below ports that pattern.

The remaining survivors are *assert-strength* gaps (range-only asserts, non-discriminating
fixtures) plus a pile of genuinely unreachable dead-branch mutations (EQUIVALENT).

## Covering test file

All coverage: `backend/tests/unit/services/test_baseline.py` (1895 lines). Anchors used below:

| Test class | line | What it asserts (gap) |
|---|---|---|
| `TestGetActivityRate` | :396 (with-baseline :413) | `0 < rate <= 10.0` — range-only; stmt never inspected |
| `TestGetClassFrequency` | :454 (:471) | `0 < freq <= 0.8` — same |
| `TestGetCameraBaselineSummary` | :754 (:787) | shape + names only (`top_classes[0]["class"]`); totals, slice cap, value keys unchecked |
| `TestGetHourlyPatterns` | :861 (:907) | `std_dev > 0` (:939) — any corrupted variance formula passes |
| `TestGetDailyPatterns` | :971 (:990) | checks only `monday`/`tuesday` keys (:1025) — days 2–6 names unchecked |
| `TestGetObjectBaselines` | :1062 (:1081) | fixture has peak at max hour-key, round-number data (argmax & rounding mutants undetectable) |
| `TestGetActivityBaselinesRaw` | :1473 (:1492) | asserts the canned mock list — SQL order_by never executed |
| `TestGetClassBaselinesRaw` | :1545 (:1564) | same |
| `TestUpdateConfig` | :1590 (:1615/:1633) | rejects 0 / -1 / 0 only — the (0,1] / ==1 boundary untested; messages via `in` substring |
| `TestBaselineSingleton` | :1648 (:1662) | `is not` only — never checks reset yields a *BaselineService* |

Sibling pattern source: `backend/tests/unit/services/test_search.py:519-553` (compile + SQL-text asserts).

SQLAlchemy render facts used by the drafts (verified against sa 2.0.53):
`where(None, x)` → `WHERE NULL AND ...`; `order_by(None, h)` → `ORDER BY NULL, ...`;
dropped clause → predicate simply absent; `!=` renders `!=`; with `literal_binds` string
values render quoted; `select(None)` → `SELECT NULL AS anon_1`; `round(x, None)` and
`round(x,)` return an int (no exception).

## Cluster table (counts sum to 117)

| # | Cluster (pattern @ function/concern) | n | Class | Example keys (≤3) | Kill / note |
|---|---|---|---|---|---|
| C6 | Whole-statement destruction `stmt = None` / `select(None)` / `execute(None)` @ all 8 read methods | 27 | TEST-GAP | `…get_activity_rate__mutmut_1`, `…get_camera_baseline_summary__mutmut_10`, `…get_hourly_patterns__mutmut_6` | T1 — `isinstance(stmt, Select)`; AsyncMock swallows None |
| C3 | WHERE clause replaced by `None` / `.where(None)` @ all 8 read methods | 13 | TEST-GAP | `…get_activity_rate__mutmut_2`, `…get_camera_baseline_summary__mutmut_2`, `…get_object_baselines__mutmut_2` | T1 — `"NULL" not in sql` |
| C5 | WHERE `==` flipped to `!=` (camera/hour/day/class) @ all 8 read methods | 13 | TEST-GAP | `…get_activity_rate__mutmut_9`, `…get_class_frequency__mutmut_11`, `…get_class_baselines_raw__mutmut_8` | T1 — exact `col = value` text + `"!=" not in sql` |
| C4 | WHERE clause dropped entirely (no None) @ get_activity_rate, get_class_frequency | 6 | TEST-GAP | `…get_activity_rate__mutmut_5`, `…get_class_frequency__mutmut_6`, `…get_activity_rate__mutmut_7` | T1 — per-predicate presence asserts |
| C7 | `order_by` column → None / dropped (2-key ORDER BY degraded) @ get_activity_baselines_raw :990, get_class_baselines_raw :1021 | 8 | TEST-GAP | `…get_activity_baselines_raw__mutmut_2`, `…get_class_baselines_raw__mutmut_4`, `…get_activity_baselines_raw__mutmut_5` | T1b — `ORDER BY activity_baselines.day_of_week, activity_baselines.hour` text assert; existing test only replays a canned list |
| C12 | `day_names` entry renamed (`friday`→`FRIDAY`/`XX…XX`) for days 2–6 @ get_daily_patterns :666 | 10 | TEST-GAP | `…get_daily_patterns__mutmut_7`, `…get_daily_patterns__mutmut_11`, `…get_daily_patterns__mutmut_15` | T3 — seeded 7 days, sorted key list; test checks only monday/tuesday |
| C14 | Rounding precision `round(x, 2)` → `2→3` / `→None` / `digits dropped(→int)` @ daily/hourly/object pattern builders (:697, :634-635, :758) | 8 | TEST-GAP | `…get_hourly_patterns__mutmut_47`, `…get_daily_patterns__mutmut_54`, `…get_object_baselines__mutmut_47` | T4/T5/T6 — non-round fixture values; existing fixtures all round to ≤2dp exactly |
| C11 | Summary payload dict keys renamed (`total_frequency`/`total_activity` → `XX…XX`/`UPPER`) @ get_camera_baseline_summary :579-580 | 4 | TEST-GAP | `…get_camera_baseline_summary__mutmut_61`, `…get_camera_baseline_summary__mutmut_68`, `…get_camera_baseline_summary__mutmut_62` | T2 — assert exact key names + values; test checks only `"class"`/`"hour"` keys (plain dict, no schema to catch it) |
| C-peak | `peak_hour` argmax degraded to max-of-keys (`key=lambda` → None / omitted) @ get_daily_patterns :691, get_object_baselines :752 | 4 | TEST-GAP | `…get_daily_patterns__mutmut_36`, `…get_object_baselines__mutmut_29`, `…get_object_baselines__mutmut_31` | T3/T5 — fixture where peak activity sits at the *lower* hour (existing data: freq rises with hour, so identity-max == argmax by coincidence) |
| C19a | `update_config` validation boundary: `<= 0`→`<= 1`, `< 1`→`<= 1`/`< 2` @ :1088, :1093 | 3 | TEST-GAP | `update_config__mutmut_3`, `update_config__mutmut_9`, `update_config__mutmut_10` | T6 — accept `threshold_stdev=0.5`, `min_samples=1`; existing tests use only 0/-1 |
| C8 | Aggregate seed `0.0`→`1.0` on first dict insert @ get_camera_baseline_summary :558, :565 | 2 | TEST-GAP | `…get_camera_baseline_summary__mutmut_18`, `…get_camera_baseline_summary__mutmut_24` | T2 — exact totals (seed inflates every class/hour total) |
| C9 | `+=` accumulation → `=` last-wins @ get_camera_baseline_summary :559, :566 | 2 | TEST-GAP | `…get_camera_baseline_summary__mutmut_19`, `…get_camera_baseline_summary__mutmut_25` | T2 — fixture with ≥2 rows per class and per hour (existing has 1 each) |
| C10 | Top-5 slice `[:5]`→`[:6]` @ get_camera_baseline_summary :569, :572 | 2 | TEST-GAP | `…get_camera_baseline_summary__mutmut_37`, `…get_camera_baseline_summary__mutmut_48` | T2 — 6 distinct classes/hours, `len(...) == 5` |
| C-var | Population-variance corruption: `/ len`→`* len`, `(x - mean)`→`(x + mean)` @ get_hourly_patterns :627 | 2 | TEST-GAP | `…get_hourly_patterns__mutmut_24`, `…get_hourly_patterns__mutmut_27` | T4 — exact `std_dev == 1.25` for [10,7,8]; test only says `std_dev > 0` |
| C1 | Singleton reset clobbered `_baseline_service = None` → `""` @ reset_baseline_service :1121 | 1 | TEST-GAP | `x_reset_baseline_service__mutmut_1` | T6 — `isinstance(get_baseline_service(), BaselineService)` after reset (mutant returns a bare `""`) |
| C16 | Dead-guard/dead-else no-ops: `hours_covered > 0`→`>= 0`/`or True`, `else 0.0→1.0`, `else 12→13`, `if hour_freq or True` @ get_object_baselines :746-752 | 5 | EQUIVALENT | `…get_object_baselines__mutmut_18`, `…get_object_baselines__mutmut_22`, `…get_object_baselines__mutmut_33` | Unkillable, do not chase: groups built by append are never empty, so every altered guard/else is unreachable (and `>0`→`>=0` can't fire with len≥1) |
| C15a | Dead guard/else: `if avg_counts else 0.0` → `or True` / `else 1.0` @ get_hourly_patterns :623 | 2 | EQUIVALENT | `…get_hourly_patterns__mutmut_16`, `…get_hourly_patterns__mutmut_19` | Same reasoning — `avg_counts` is a non-empty append-group |
| C20 | `if len(avg_counts) > 1` → `>= 1` @ get_hourly_patterns :625 | 1 | EQUIVALENT | `…get_hourly_patterns__mutmut_20` | Population variance of a single point is exactly 0.0 — the altered branch computes what the old else did; no observable difference |
| C19b | Error/log message text: `"XXmin_samples must be at least 1XX"`, `"XXthreshold_stdev…XX"`, `logger.info(...)` → `logger.info(None)` @ update_config :1089/1094/1097 | 3 | LOW-VALUE | `update_config__mutmut_5`, `update_config__mutmut_12`, `update_config__mutmut_15` | Tests assert messages with `in` (substring survives the XX-wrap — that's why they passed); pinning exact message text/log content is brittle over-specification |
| C13 | Defensive day guard `0 <= day_num < 7` → `<= 7` @ get_daily_patterns :695 | 1 | LOW-VALUE | `…get_daily_patterns__mutmut_42` | day_of_week originates from `datetime.weekday()` (0–6); mutant only alters an unreachable-index path (would IndexError, not misbehave). If the skip-on-garbage contract is ever wanted, C12's test gains a day_num=7 row for free |

Totals: TEST-GAP 98 (14 clusters), EQUIVALENT 8 (3 clusters), LOW-VALUE 4 (2 clusters) → 117.

**Leverage summary:** T1/T1b (2–3 test methods + 7 near-copies) kill 59 of 117 (50%).
T2 kills 10, T3 kills 12-13, T4 kills 6, T5 kills 4, T6 kills 4. Six drafted tests ≈
95–98 of the TEST-GAP survivors; EQUIVALENT/LOW-VALUE clusters (12) are baseline noise to
accept in WP4.4, not to chase.

## Drafted tests (UNVERIFIED — not yet run red/green)

All target `backend/tests/unit/services/test_baseline.py` (append new classes; style copied
from existing `TestGetHourlyPatterns`/`TestGetCameraBaselineSummary`). TDD procedure for
each: apply the cluster's mutant diff to `backend/services/baseline.py` → run the drafted
test → it must FAIL on the named assertion; revert diff → must PASS. No test below was
executed (live mutation run owns the machine).

### T1 + T1b — statement-integrity capture (kills C6, C3, C5, C4, C7 = 59 keys)

```python
# =============================================================================
# Statement Integrity Tests (WP4.4 mutation triage)
# UNVERIFIED - not yet run red/green
# =============================================================================


class TestStatementIntegrity:
    """Assert on the SQL each read method actually builds.

    The rest of this file stubs the session with AsyncMock, which ignores the
    statement passed to execute() — so every WHERE/ORDER BY mutation survives.
    These tests capture the statement and inspect its compiled SQL
    (pattern from tests/unit/services/test_search.py TestILikeFallbackBehavior).
    """

    @staticmethod
    def _capturing_session() -> tuple[AsyncMock, list]:
        """AsyncMock session that records every statement passed to execute()."""
        captured: list = []

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar_one_or_none.return_value = None

        async def _execute(stmt, *args, **kwargs):  # noqa: ANN001, ANN202
            captured.append(stmt)
            return mock_result

        mock_session = AsyncMock()
        mock_session.execute.side_effect = _execute
        return mock_session, captured

    @staticmethod
    def _sql(stmt) -> str:  # noqa: ANN001
        """Compile a captured statement with literal binds (kills stmt=None/select(None))."""
        from sqlalchemy import Select
        from sqlalchemy.dialects import postgresql

        assert isinstance(stmt, Select), f"execute() got non-Select statement: {stmt!r}"
        return str(
            stmt.compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )

    @pytest.mark.asyncio
    async def test_get_activity_rate_filters_on_all_three_keys(self) -> None:
        """Kills get_activity_rate mutants 1-11, 13 (None/select(None)/execute(None),
        clause->None, clause dropped, == flipped to !=)."""
        service = BaselineService()
        session, captured = self._capturing_session()

        rate = await service.get_activity_rate("camera-1", 14, 0, session=session)

        assert rate == 0.0
        sql = self._sql(captured[0])
        assert "NULL" not in sql                      # kills clause->None mutants
        assert "!=" not in sql                        # kills ==->!= flips
        assert "activity_baselines.camera_id = 'camera-1'" in sql  # kills dropped camera clause
        assert "activity_baselines.hour = 14" in sql               # kills dropped hour clause
        assert "activity_baselines.day_of_week = 0" in sql         # kills dropped dow clause

    @pytest.mark.asyncio
    async def test_get_activity_baselines_raw_filters_and_orders(self) -> None:
        """Kills get_activity_baselines_raw mutants 1-8, 10 (incl. both order_by columns)."""
        service = BaselineService()
        session, captured = self._capturing_session()

        baselines = await service.get_activity_baselines_raw("camera-1", session=session)

        assert baselines == []
        sql = self._sql(captured[0])
        assert "NULL" not in sql
        assert "!=" not in sql
        assert "activity_baselines.camera_id = 'camera-1'" in sql
        assert (
            "ORDER BY activity_baselines.day_of_week, activity_baselines.hour" in sql
        )  # kills order_by column ->None / dropped
```

Replication note: the same three asserts, retargeted, kill the other 21 statement
mutants + 4 class_raw order mutants + the 6 summary statement mutants — one test method
per: `get_class_frequency` (`class_baselines.camera_id/detection_class/hour`, 3 key
predicates), `get_class_baselines_raw` (WHERE + `ORDER BY class_baselines.detection_class,
class_baselines.hour`), `get_camera_baseline_summary` (two captured statements, one per
table — side_effect yields two result mocks as the existing summary test does),
`get_daily_patterns` / `get_hourly_patterns` (activity WHERE), `get_object_baselines`
(class WHERE). The helper makes each ~8 lines.

### T2 — summary aggregation + payload (kills C8, C9, C10, C11 = 10 keys)

```python
class TestSummaryAggregationPrecision:
    """UNVERIFIED - not yet run red/green. Kills dict-seed 0.0->1.0 (18/24),
    += -> = (19/25), [:5] -> [:6] (37/48), payload key renames (61/62/67/68)."""

    @pytest.mark.asyncio
    async def test_summary_sums_duplicates_caps_top_five_with_exact_keys(self) -> None:
        mock_session = AsyncMock()

        def _activity(hour: int, avg_count: float) -> MagicMock:
            m = MagicMock()
            m.hour = hour
            m.avg_count = avg_count
            return m

        def _class(detection_class: str, frequency: float) -> MagicMock:
            m = MagicMock()
            m.detection_class = detection_class
            m.frequency = frequency
            return m

        # Two rows share hour 0 and two rows share "person" -> += vs = observable;
        # 6 distinct hours/classes -> slice cap observable.
        activity_rows = [
            _activity(0, 3.0), _activity(0, 2.0),   # hour 0 total 5.0
            _activity(1, 9.0), _activity(2, 8.0), _activity(3, 7.0),
            _activity(4, 6.0), _activity(5, 5.0),
        ]
        class_rows = [
            _class("person", 5.0), _class("person", 3.5),  # person total 8.5
            _class("vehicle", 3.0), _class("dog", 2.0), _class("cat", 1.5),
            _class("bird", 1.0), _class("car", 0.5),
        ]

        act_result = MagicMock()
        act_scalars = MagicMock()
        act_scalars.all.return_value = activity_rows
        act_result.scalars.return_value = act_scalars

        cls_result = MagicMock()
        cls_scalars = MagicMock()
        cls_scalars.all.return_value = class_rows
        cls_result.scalars.return_value = cls_scalars

        mock_session.execute.side_effect = [act_result, cls_result]

        service = BaselineService()
        summary = await service.get_camera_baseline_summary("camera-1", session=mock_session)

        # += (not =): person must be 5.0 + 3.5, seed 0.0 (not 1.0)
        assert summary["top_classes"][0]["class"] == "person"
        assert summary["top_classes"][0]["total_frequency"] == 8.5   # exact key name too
        assert len(summary["top_classes"]) == 5                      # [:5] cap
        assert summary["peak_hours"][0]["hour"] == 1
        assert summary["peak_hours"][0]["total_activity"] == 9.0
        assert len(summary["peak_hours"]) == 5
        # duplicate hour total present via exact value lookup:
        totals = {e["hour"]: e["total_activity"] for e in summary["peak_hours"]}
        assert totals[0] == 5.0   # += with 0.0 seed; = -> 2.0; seed 1.0 -> 6.0
```

### T3 — day-name table + peak_hour argmax + daily rounding (kills C12, daily C14, daily C-peak = 13 keys)

```python
class TestDailyPatternNaming:
    """UNVERIFIED - not yet run red/green. Kills day_names renames 6-15,
    avg rounding 51/53/54, peak_hour key removal 36/38."""

    @pytest.mark.asyncio
    async def test_all_seven_day_names_and_exact_math(self) -> None:
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday",
                     "saturday", "sunday"]
        baselines = []
        for day in range(7):
            m = MagicMock()
            m.day_of_week = day
            m.hour = 3            # sole hour per day -> peak_hour 3, kills nothing here,
            m.avg_count = 1.0     #   but names assert below covers all 7 entries
            m.sample_count = 1
            baselines.append(m)
        # Monday gets a second row at a LOWER hour with HIGHER activity: peak must be
        # hour 2 (argmax), not max(keys)=14-ish; sum 1.234 + 2.345 = 3.579 exercises
        # round(.,2) == 3.58 vs round(.,3) == 3.579 vs round() == 4.
        extra = MagicMock()
        extra.day_of_week, extra.hour = 0, 9
        extra.avg_count, extra.sample_count = 2.345, 1
        first = baselines[0]
        first.hour, first.avg_count = 2, 1.234
        baselines.append(extra)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = baselines
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        patterns = await service.get_daily_patterns("camera-1", session=mock_session)

        assert sorted(patterns) == sorted(day_names)   # kills every renamed day (days 2-6)
        assert patterns["friday"].avg_detections == 1.0 and patterns["friday"].peak_hour == 3
        assert patterns["monday"].avg_detections == 3.58
        assert patterns["monday"].peak_hour == 2       # argmax hour; key-less max -> 9
```

### T4 — hourly std_dev/rounding exact math (kills C-var + hourly C14 = 6 keys)

```python
class TestHourlyPatternMath:
    """UNVERIFIED - not yet run red/green. Kills variance /len -> *len (24),
    (x - mean) -> (x + mean) (27), rounding 47/49/51/52."""

    @pytest.mark.asyncio
    async def test_std_dev_is_population_std_with_two_dp_rounding(self) -> None:
        rows = []
        for avg_count, samples in ((10.0, 1), (7.0, 2), (8.0, 3)):   # all hour 14
            m = MagicMock()
            m.hour, m.avg_count, m.sample_count = 14, avg_count, samples
            rows.append(m)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = rows
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        patterns = await service.get_hourly_patterns("camera-1", session=mock_session)

        # mean 25/3 -> 8.33; pop var 1.5556 -> std 1.2472 -> round 1.25
        assert patterns["14"].avg_detections == 8.33   # kills round 2->3 (8.333), ->int (8)
        assert patterns["14"].std_dev == 1.25          # kills *len (3.74), +mean (16.71),
        assert patterns["14"].sample_count == 6        #   round 2->3 (1.247), ->int (1)
```

### T5 — object peak_hour argmax + rounding (kills object C-peak + object C14 = 3 keys)

```python
class TestObjectBaselinePeakHour:
    """UNVERIFIED - not yet run red/green. Kills key=lambda -> None/omitted
    (29/31) and avg_hourly round 2->3 (47)."""

    @pytest.mark.asyncio
    async def test_peak_hour_is_highest_frequency_hour(self) -> None:
        m9, m14 = MagicMock(), MagicMock()
        for m, hour, freq in ((m9, 9, 10.0), (m14, 14, 8.667)):
            m.detection_class, m.hour, m.frequency, m.sample_count = "person", hour, freq, 5
        # peak at the LOWER hour key: identity max(keys) would answer 14.

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [m9, m14]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        baselines = await service.get_object_baselines("camera-1", session=mock_session)

        assert baselines["person"].peak_hour == 9
        assert baselines["person"].avg_hourly == 9.33   # 9.3335: round(,3)=9.333 kills _47
```

### T6 — update_config boundary + singleton reset identity (kills C19a + C1 = 4 keys)

```python
class TestConfigBoundaryAndReset:
    """UNVERIFIED - not yet run red/green. Kills threshold <=0 -> <=1 (3),
    min_samples <1 -> <=1 (9) / <2 (10), reset None -> "" (reset_baseline_service_1)."""

    def test_update_config_accepts_boundary_values(self) -> None:
        service = BaselineService()
        service.update_config(threshold_stdev=0.5)   # mutant (<= 1) raises -> red
        assert service.anomaly_threshold_std == 0.5
        service.update_config(min_samples=1)         # mutants (<=1 / <2) raise -> red
        assert service.min_samples == 1

    def test_reset_yields_fresh_service_instance(self) -> None:
        from backend.services.baseline import get_baseline_service, reset_baseline_service

        get_baseline_service()
        reset_baseline_service()
        service = get_baseline_service()
        assert isinstance(service, BaselineService)  # mutant leaves global == "" -> red
        reset_baseline_service()
```

## Triage artifacts (this run)

- `/tmp/wp25/wp44-triage/keys.txt` — the 117 survivor keys
- `/tmp/wp25/wp44-triage/diffs/all.diff` — full `mutmut show` diffs (117/117 fetched, zero failures)
- `/tmp/wp25/wp44-triage/diffs/compact.txt` — one line per mutant (`-`removed / `+`added)

## Notes for WP4.4

- 433 keys still unverified in meta; verdicts for the rest of the file (and `is_anomalous`,
  `get_current_deviation`, `get_baseline_estimated_date` etc. — zero survivors *so far*,
  all in unchecked range) must be re-triaged when the run completes. The unchecked
  functions have the same AsyncMock session, so expect the same statement-mutation
  survivor pattern there; the T1 helper generalizes unchanged.
- Do not spend effort on C16/C15a/C20/C19b/C13 (12 keys): unreachable branches and
  message-text churn. Recommend marking them `no-cover` in the WP4.4 ledger.
- Root-cause note worth a one-liner in the WP4.4 narrative: unit tests of DB services that
  mock the session cannot kill *any* statement-content mutant; the compile-text pattern
  (already used by test_search.py) is the cheap antidote and likely pays off across the
  whole services/ module set.
