# WP4.4 Triage Dossier — backend/services/baseline.py

- **Module:** `backend/services/baseline.py` (1121 lines, `BaselineService`)
- **Survivors:** 369 of 766 keys (397 killed) — from `mutants/backend/services/baseline.py.meta` `exit_code_by_key == 0`
- **Diffs:** extracted mechanically (mutant-copy variant blocks keyed by `__mutmut_N` names, line-diffed vs `__mutmut_orig`; spot-verified with `uv run mutmut show`). Raw survivor/diff working files: `/tmp/wp25/wp44-triage/.bl_surv.txt`, `.bl_diffs2.pkl`, `.bl_clusters_final.json`, `.bl_examples_final.json`.
- **Covering test files:** `backend/tests/unit/services/test_baseline.py` (primary; class line numbers below) and `backend/tests/unit/services/test_baseline_properties.py:573` (`test_z_score_interpretation_ranges`).

## The systemic root cause (why 369 survive)

Every async DB test in `test_baseline.py` drives the service against `AsyncMock` sessions whose `execute()` returns canned `MagicMock` results. The service's **SQL text is never inspected**: `select(...).where(None)`, `.where(col != v)`, `execute(None)`'s statement, the UPDATE's `.values(...)`, the INSERT's constructor args, `ORDER BY` columns, and method-call arguments are all invisible to the asserts (which check `.called` / `call_count >= 1` / returned values only). Verified against the real library: `str(select(ActivityBaseline).where(None))` compiles to a filter-less **full-table SELECT** — these mutants are *live production bugs* (wrong-camera reads), not artifacts.

Second root cause: **assertion imprecision** — `assert 0 < decay < 1`, `assert score < 0.5`, `assert std_dev > 0`, never asserting `deviation.score` or rounding; z-score tests use `-2.5/-1.5/0.5/1.5/2.5/3.5`, never the exact boundaries; the hypothesis property test replicates `<` (never tests the `<=` boundary).

## Cluster table (counts sum to 369 exactly)

| # | Cluster | N | Class | Pattern | Example keys |
|---|---------|---|-------|---------|--------------|
| 1 | TG_WHERE_DROP | 93 | TEST-GAP | WHERE predicate (`camera_id==/hour==/day_of_week==/detection_class==`) replaced by `None`, clause deleted, or whole `stmt`→`None` — in `_update_activity_baseline`, `_update_class_baseline`, `get_activity_rate`, `get_class_frequency`, `is_anomalous`, `get_current_deviation`, `get_camera_baseline_summary`, `get_hourly_patterns`, `get_daily_patterns`, `get_object_baselines`, `get_baseline_established_date`, both `*_baselines_raw` | `_update_activity_baseline__mutmut_1/2`, `is_anomalous__mutmut_3` |
| 2 | TG_EWMA_VALUES | 84 | TEST-GAP | EWMA update/insert payload never asserted: `new_avg/new_freq = decay*old + (1-decay)*1.0` operator/constant flips, `new_count +1`→`-1/+2/None`, stale-reset `1.0/1`→`2.0/2/None`, dropped `None`/kwargs in `.values(avg_count=…, sample_count=…, last_updated=…)`, `update().where(id==existing.id)`→`None`/`!=`, INSERT constructor args→`None`/`2`, `if decay > 0`→`>=0`/`>1`, `existing=None` | `_update_activity_baseline__mutmut_22/23/37`, `_update_class_baseline__mutmut_45` |
| 3 | TG_WHERE_FLIP | 33 | TEST-GAP | `==` → `!=` in WHERE predicates (inverted camera/hour/class filter — returns *wrong* rows) | `_update_activity_baseline__mutmut_9`, `get_daily_patterns__mutmut_19` |
| 4 | TG_STATS_SCORE | 24 | TEST-GAP | Statistics/rounding precision unasserted: variance `**2`→`**3`, `(x-mean)`→`(x+mean)`, `/len`→`*len`, `sum(avg_counts)/len`→`*len`; `round(x,2)`→`round(x,3)/round(x,None)/round(2)` (all legal calls that drop 2-dp precision; test fixtures make rounding a no-op); z-score formula `/std_dev`→`*std_dev`, `(current-mean)`→`(current+mean)`, else-arm `0.0`→`1.0` | `get_current_deviation__mutmut_36/44/55`, `get_hourly_patterns__mutmut_24/47` |
| 5 | TG_STMT_NONE | 20 | TEST-GAP | `await sess.execute(stmt)` → `execute(None)` — mock session happily answers | `_update_activity_baseline__mutmut_13`, `get_camera_baseline_summary__mutmut_6` |
| 6 | TG_ANOM_AGG | 11 | TEST-GAP | `is_anomalous` aggregation untested: accumulators `total_frequency/class_frequency/total_samples` init `0.0/0`→`1.0/1`, `+=`→`=` (multi-class only), `if total_samples < min`→`<=`, `relative_frequency` guard `>0`→`>=0`/`>1`/`or True`, `class_frequency==0.0`→`==1.0` (`is_anomalous__mutmut_36/62` folded in as EQUIV-adjacent inputs: see note) | `is_anomalous__mutmut_46/48/52` |
| 7 | EQ_UNREACHABLE | 11 | EQUIVALENT | Defensive-guard tweaks unreachable with valid inputs: `max(0.0,min(1.0,…))`→`min(2.0,…)` (inner term always ≤1), `if avg_counts/hour_freq/hours_covered else 0.0` `or True` and `0→1` else-arms (empty branch unreachable — dict key exists only after `.append`), `0 <= day_num <= len(day_names)` (no records for day 7) | `is_anomalous__mutmut_78`, `get_hourly_patterns__mutmut_16/19` |
| 8 | TG_ZSCORE_BOUNDS | 11 | TEST-GAP | `<`→`<=` at z-score band boundaries (5), `min_samples <`→`<=` gate, `z_score > 1.5`→`>=1.5`/`>2.5`, `cb.frequency > 2.0`→`>=2.0`/`>3.0`, `threshold_stdev <= 0`→`<=1`, `min_samples < 1`→`<=1`/`<2` — boundary values never asserted | `_interpret_z_score__mutmut_1/4/7`, `update_config__mutmut_3` |
| 9 | EQ_DAYNAME→reclassed **TG_DAYNAME_KEY** | 10 | TEST-GAP | `day_names` entries `→"WEDNESDAY"`/`→"XXwednesdayXX"` change the API response **dict keys** (payload identity, not prose); existing test only checks lowercase `"monday"/"tuesday"` (index 0/1) — days 2-6 unchecked | `get_daily_patterns__mutmut_7/9/11` |
| 10 | TG_ORDER_DROP | 10 | TEST-GAP | `order_by(day_of_week, hour)` / `(detection_class, hour)` columns→`None`/removed — raw-list row order unasserted | `get_activity_baselines_raw__mutmut_2/3`, `get_class_baselines_raw__mutmut_1` |
| 11 | TG_DISPATCH_ARG | 9 | TEST-GAP | `update_baseline` forwards `None` for `camera_id/hour/day_of_week/now/detection_class` into `_update_*_baseline` — existing tests use uniform mocks that can't see the args | `update_baseline__mutmut_3/6/7` |
| 12 | TG_ANOM_THRESHOLD | 8 | TEST-GAP | `is_anomaly = score > (1.0 - 1.0/(std+1))` threshold expression flips (`>=`, `1.0+`, `2.0-`, `*`, `std-1`, `std+2`, `is_anomaly=None`) — no test asserts the boolean flag | `is_anomalous__mutmut_81/82/87` |
| 13 | TG_ARG_NULL | 7 | TEST-GAP | `hour=timestamp.hour`→`None`, `day_of_week`→`None`, `datetime.now(UTC)`→`datetime.now(None)`/`None` (naive/None timestamps silently change query keys) | `update_baseline__mutmut_1/2/4`, `is_anomalous__mutmut_1` |
| 14 | TG_FACTORS | 9 | TEST-GAP | `get_current_deviation` `contributing_factors`: `"overall_activity_deviation"`→`"XX…XX"`/`"OVERALL_ACTIVITY_DEVIATION"` (2, payload strings like day-names) + boundary tweaks (7, with #8) | `get_current_deviation__mutmut_79/83/86` |
| 15 | TG_SUMMARY_AGG | 6 | TEST-GAP | `get_camera_baseline_summary` aggregation: per-key accumulators `=0.0`→`=1.0`, `+=`→`=`, top-5 slice `[:5]`→`[:6]` — test uses one entry per key, can't see summation/limit | `get_camera_baseline_summary__mutmut_19/25/37` |
| 16 | TG_PEAK_ORDER | 5 | TEST-GAP | `max(keys(), key=lambda h: freq[h])` → `key=None` (TypeError→test fails? **no — survives because mocked hour_activity has 1 entry and… actually `key=None` raises; survives only where the branch isn't hit by the exact assertion path**) / key-lambda removal | `get_daily_patterns__mutmut_36/38`, `get_object_baselines__mutmut_29` |
| 17 | TG_SUMMARY_PAYLOAD | 4 | TEST-GAP | Summary dict **keys** `"total_frequency"`/`"total_activity"` → `XX`/UPPER — response payload contract | `get_camera_baseline_summary__mutmut_61/62/67` |
| 18 | EQ_VAL_MSG | 6 | EQUIVALENT | Validation `raise ValueError("…")` message text wrapped `XX…XX` (4 in `__init__`, 2 in `update_config`); tests assert `"decay_factor" in str(exc)` substring which survives the XX wrapper | `__init____mutmut_7/12`, `update_config__mutmut_5/12` |
| 19 | EQ_LOG | 6 | EQUIVALENT | `logger.info/debug(f"…")` first-arg → `None` (`__init__`, `update_baseline`, `is_anomalous` ×2, `update_config`, init) — pure logging | `__init____mutmut_28`, `is_anomalous__mutmut_30/53` |
| 20 | TG_TIMEDECAY_UNIT | 1 | TEST-GAP | `/ 86400.0` → `/ 86401.0` — 0.001% days-elapsed shift; 1-day decay test asserts `0 < decay < 1` and the 0.5-formula test allows `< 0.01` tolerance | `_calculate_time_decay__mutmut_10` |
| 21 | TG_SINGLETON_RESET | 1 | TEST-GAP | `reset_baseline_service`: `_baseline_service = None` → `= ""` — truthy empty string passes the `is None` re-create check, so the next `get_baseline_service()` silently *keeps* the instance… test only asserts `service1 is not service2` | `x_reset_baseline_service__mutmut_1` |

**Totals:** TEST-GAP **346** · EQUIVALENT **23** · **369** ✓ (no LOW-VALUE: the debug-logging mutants are semantically inert, i.e. EQUIVALENT).

**Note on `is_anomalous__mutmut_36/62`** (`class_frequency=0.0→1.0` init, else-arm `0.0→1.0`): the named class's record always sets `class_frequency` when present, and `class_frequency==0` only via decay; the exact-dose mutant survives only because no test pins the numeric score at those points — kept in TG_ANOM_AGG's kill set since the same test kills them.

## Why existing tests can't see these (file:line)

`backend/tests/unit/services/test_baseline.py` —
- `TestUpdateBaseline` :216 — asserts only `mock_session.execute.called` / `add.call_count >= 1`
- `TestUpdateActivityBaseline` :253, `TestUpdateClassBaseline` :303 — `call_count >= 1`; the UPDATE's `.values(...)` payload never inspected ⇒ EWMA cluster invisible
- `TestGetActivityRate` :396, `TestGetClassFrequency` :454 — pass a mock session; the SELECT's WHERE is never compiled/asserted
- `TestIsAnomalous` :548 — asserts `(is False, score == 0.5)` for the two neutral early-returns; multi-class relative-frequency math and the `is_anomaly` boolean never pinned
- `TestGetCameraBaselineSummary` :754 — one entry per hour/class ⇒ `+=`→`=` undetectable
- `TestGetHourlyPatterns` :861 / `TestGetDailyPatterns` :971 / `TestGetObjectBaselines` :1062 — `avg_detections`/`peak_hour` asserted with fixture values that make variance-formula mutants coincidentally equal; `std_dev > 0` not exact
- `TestInterpretZScore` :1127 — z ∈ {±.5 offsets}; no exact boundary
- `TestGetCurrentDeviation` :1204 — `isinstance` checks only, `deviation.score` unasserted ⇒ TG_STATS_SCORE
- `TestGetActivityBaselinesRaw` :1473 / `TestGetClassBaselinesRaw` :1545 — data lists unsorted-tolerant asserts
- `TestBaselineSingleton` :1648 — `is not` identity, no `is None` after reset
- `TestEdgeCases` :1788, `TestPropertyBasedDecay` :1679 — `test_decay_one_day` = `0 < decay < 1` (tolerant) ⇒ 86401 survives
`backend/tests/unit/services/test_baseline_properties.py:573` — hypothesis replicates `<` semantics, cannot kill `<=`.

## Drafted kill-tests (UNVERIFIED — never run; the live mutation run owns this machine)

TDD procedure (one line): each new assertion must FAIL (red) against the mutant diff above and PASS (green) against the unmutated source before it counts as a kill.

### Draft 1 — `TestQueryPredicateIntegrity` (kills #1 + #3 = 126 mutants)

Target file: `backend/tests/unit/services/test_baseline.py` (append; imports already present at :12-19; add `import math` only if Draft 3 lands separately).

```python
# =============================================================================
# SQL Predicate Integrity (kills WHERE-drop / WHERE-flip survivors)
# // UNVERIFIED - not yet run red/green
# =============================================================================


class TestQueryPredicateIntegrity:
    """Mocked sessions never let the service's SQL be observed, and
    SQLAlchemy compiles .where(None) into a *filter-less* full-table SELECT
    (verified against backend.models.baseline). Compiling the captured
    statement with literal_binds makes every dropped/inverted predicate fail.
    """

    @staticmethod
    def _literal(stmt) -> str:
        return str(stmt.compile(compile_kwargs={"literal_binds": True}))

    @pytest.mark.asyncio
    async def test_get_activity_rate_filters_camera_hour_day(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        await service.get_activity_rate("cam-alpha", 14, 2, session=mock_session)

        sql = self._literal(mock_session.execute.call_args[0][0])
        assert "activity_baselines.camera_id = 'cam-alpha'" in sql
        assert "activity_baselines.hour = 14" in sql
        assert "activity_baselines.day_of_week = 2" in sql

    @pytest.mark.asyncio
    async def test_get_class_frequency_filters_camera_class_hour(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        await service.get_class_frequency("cam-alpha", "person", 14, session=mock_session)

        sql = self._literal(mock_session.execute.call_args[0][0])
        assert "class_baselines.camera_id = 'cam-alpha'" in sql
        assert "class_baselines.detection_class = 'person'" in sql
        assert "class_baselines.hour = 14" in sql

    @pytest.mark.asyncio
    async def test_is_anomalous_filters_both_class_queries(self) -> None:
        mock_session = AsyncMock()
        none_one = MagicMock()
        none_one.scalar_one_or_none.return_value = None
        none_all = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        none_all.scalars.return_value = scalars
        mock_session.execute.side_effect = [none_one, none_all]

        service = BaselineService()
        ts = datetime(2025, 12, 23, 14, 30, tzinfo=UTC)
        await service.is_anomalous("cam-alpha", "person", ts, session=mock_session)

        class_sql = self._literal(mock_session.execute.call_args_list[0][0][0])
        all_sql = self._literal(mock_session.execute.call_args_list[1][0][0])
        assert "class_baselines.camera_id = 'cam-alpha'" in class_sql
        assert "class_baselines.detection_class = 'person'" in class_sql
        assert "class_baselines.hour = 14" in class_sql
        assert "class_baselines.camera_id = 'cam-alpha'" in all_sql
        assert "class_baselines.hour = 14" in all_sql

    @pytest.mark.asyncio
    async def test_update_activity_baseline_select_keys(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()

        service = BaselineService()
        await service._update_activity_baseline(
            mock_session, "cam-alpha", 14, 2, datetime.now(UTC)
        )

        sql = self._literal(mock_session.execute.call_args_list[0][0][0])
        assert "activity_baselines.camera_id = 'cam-alpha'" in sql
        assert "activity_baselines.hour = 14" in sql
        assert "activity_baselines.day_of_week = 2" in sql

    @pytest.mark.asyncio
    async def test_update_class_baseline_select_keys(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()

        service = BaselineService()
        await service._update_class_baseline(
            mock_session, "cam-alpha", "person", 14, datetime.now(UTC)
        )

        sql = self._literal(mock_session.execute.call_args_list[0][0][0])
        assert "class_baselines.camera_id = 'cam-alpha'" in sql
        assert "class_baselines.detection_class = 'person'" in sql
        assert "class_baselines.hour = 14" in sql
```

(Repeat the pattern for `get_camera_baseline_summary`, `get_hourly_patterns`, `get_daily_patterns`, `get_object_baselines`, `get_current_deviation`, `get_baseline_established_date` — same call-capture idiom.)

### Draft 2 — `TestRawQueriesOrdered` (kills #10 = 10)

```python
class TestRawQueriesOrdered:
    """// UNVERIFIED - not yet run red/green"""

    @pytest.mark.asyncio
    async def test_activity_raw_ordered_by_day_then_hour(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        mock_result.scalars.return_value = scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        await service.get_activity_baselines_raw("cam-alpha", session=mock_session)

        sql = str(
            mock_session.execute.call_args[0][0].compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "ORDER BY activity_baselines.day_of_week, activity_baselines.hour" in sql

    @pytest.mark.asyncio
    async def test_class_raw_ordered_by_class_then_hour(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        mock_result.scalars.return_value = scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        await service.get_class_baselines_raw("cam-alpha", session=mock_session)

        sql = str(
            mock_session.execute.call_args[0][0].compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert (
            "ORDER BY class_baselines.detection_class, class_baselines.hour" in sql
        )
```

### Draft 3 — `TestUpdateBaselinePersistedValues` (kills #2 = 84)

```python
class TestUpdateBaselinePersistedValues:
    """// UNVERIFIED - not yet run red/green
    Kills EWMA operator/constant flips, sample_count off-by-one, dropped
    .values kwargs, wrong-id UPDATE keys, and INSERT constructor nulls by
    reading the compiled UPDATE payload and the session.add() record.
    """

    @staticmethod
    def _literal(stmt) -> str:
        return str(stmt.compile(compile_kwargs={"literal_binds": True}))

    @pytest.mark.asyncio
    async def test_existing_activity_baseline_ewma_payload(self) -> None:
        mock_session = AsyncMock()
        now = datetime.now(UTC)
        existing = MagicMock()
        existing.id = 1
        existing.avg_count = 5.0
        existing.sample_count = 10
        existing.last_updated = now - timedelta(seconds=86400)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        service = BaselineService(decay_factor=0.1, window_days=30)
        await service._update_activity_baseline(mock_session, "cam-1", 14, 0, now)

        update_stmt = mock_session.execute.call_args_list[1][0][0]
        sql = self._literal(update_stmt)
        # keyed on the right row (kills .where(id != existing.id) / where(None))
        assert "activity_baselines.id = 1" in sql
        # independent expected value: decay = e^(-1 * ln(10)) = 0.1 exactly
        expected_avg = 0.1 * 5.0 + 0.9 * 1.0  # 1.4
        m_avg = re.search(r"avg_count = ([0-9.eE+-]+)", sql)
        assert m_avg is not None
        assert float(m_avg.group(1)) == pytest.approx(1.4, abs=1e-9)
        m_cnt = re.search(r"sample_count = (\d+)", sql)
        assert m_cnt is not None and int(m_cnt.group(1)) == 11
        assert "last_updated" in sql and "last_updated = NULL" not in sql

    @pytest.mark.asyncio
    async def test_stale_activity_baseline_resets_to_one(self) -> None:
        mock_session = AsyncMock()
        now = datetime.now(UTC)
        existing = MagicMock()
        existing.id = 7
        existing.avg_count = 9.0
        existing.sample_count = 99
        existing.last_updated = now - timedelta(days=35)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        service = BaselineService(window_days=30)
        await service._update_activity_baseline(mock_session, "cam-1", 14, 0, now)

        sql = self._literal(mock_session.execute.call_args_list[1][0][0])
        assert "avg_count = 1" in sql and "sample_count = 1" in sql

    @pytest.mark.asyncio
    async def test_new_activity_baseline_constructor_fields(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()

        service = BaselineService()
        await service._update_activity_baseline(mock_session, "cam-1", 14, 2, datetime.now(UTC))

        record = mock_session.add.call_args[0][0]
        assert record.camera_id == "cam-1"
        assert record.hour == 14
        assert record.day_of_week == 2
        assert record.avg_count == 1.0
        assert record.sample_count == 1
        assert record.last_updated is not None
```

Mirror three tests for `_update_class_baseline` (`frequency = 1.4` / reset / constructor `detection_class == "person"`). Add `import re` to the module imports.

### Draft 4 — `TestIsAnomalousNumericContract` (kills #6 + #12 = 19)

```python
class TestIsAnomalousNumericContract:
    """// UNVERIFIED - not yet run red/green
    Existing tests only pin the two neutral (False, 0.5) early returns. These
    pin the accumulator/relative-frequency/threshold math.
    """

    @staticmethod
    def _mk(freq: float, samples: int, cls: str, age: timedelta, now):
        b = MagicMock()
        b.detection_class = cls
        b.frequency = freq
        b.sample_count = samples
        b.last_updated = now - age
        return b

    @pytest.mark.asyncio
    async def test_class_never_seen_scores_one_and_flags_true(self) -> None:
        mock_session = AsyncMock()
        now = datetime.now(UTC)
        none_one = MagicMock()
        none_one.scalar_one_or_none.return_value = None  # class_stmt finds nothing
        vehicle = self._mk(10.0, 50, "vehicle", timedelta(hours=1), now)
        all_res = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [vehicle]
        all_res.scalars.return_value = scalars
        mock_session.execute.side_effect = [none_one, all_res]

        service = BaselineService(min_samples=10, decay_factor=0.9)
        is_anom, score = await service.is_anomalous(
            "cam-1", "bear", datetime(2025, 12, 23, 14, 30, tzinfo=UTC), session=mock_session
        )
        assert score == 1.0          # kills init=1.0 and +=/= variants at this point
        assert is_anomaly if False else is_anom is True  # threshold must flag score 1.0

    @pytest.mark.asyncio
    async def test_total_is_sum_not_last_multi_class(self) -> None:
        """rel_freq must divide by the SUM across 3 classes: person 1/(1+1+8)=0.1."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)
        person = self._mk(1.0, 50, "person", timedelta(0), now)
        vehicle = self._mk(1.0, 50, "vehicle", timedelta(0), now)
        cat = self._mk(8.0, 50, "cat", timedelta(0), now)
        one_res = MagicMock()
        one_res.scalar_one_or_none.return_value = person
        all_res = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [person, vehicle, cat]
        all_res.scalars.return_value = scalars
        mock_session.execute.side_effect = [one_res, all_res]

        # decay_factor=1.0 -> decay == 1.0 exactly for any age within window
        service = BaselineService(min_samples=10, decay_factor=1.0)
        _flag, score = await service.is_anomalous(
            "cam-1", "person", datetime(2025, 12, 23, 14, 30, tzinfo=UTC), session=mock_session
        )
        # `+=`->`=` leaves total=8 (last) -> rel=1/8 -> score 0.875 != 0.9
        assert score == pytest.approx(1.0 - 1.0 / 10.0, abs=1e-9)

    @pytest.mark.asyncio
    async def test_anomaly_flag_uses_threshold_formula(self) -> None:
        """score 1/11 ≈ 0.0909; threshold(1.0)=0.5 -> False; threshold(0.05)=0.0476 -> True."""
        for threshold_std, expected_flag in ((1.0, False), (0.05, True)):
            mock_session = AsyncMock()
            now = datetime.now(UTC)
            person = self._mk(10.0, 50, "person", timedelta(0), now)
            vehicle = self._mk(1.0, 50, "vehicle", timedelta(0), now)
            one_res = MagicMock()
            one_res.scalar_one_or_none.return_value = person
            all_res = MagicMock()
            scalars = MagicMock()
            scalars.all.return_value = [person, vehicle]
            all_res.scalars.return_value = scalars
            mock_session.execute.side_effect = [one_res, all_res]

            service = BaselineService(min_samples=10, decay_factor=1.0,
                                      anomaly_threshold_std=threshold_std)
            flag, score = await service.is_anomalous(
                "cam-1", "person", datetime(2025, 12, 23, 14, 30, tzinfo=UTC),
                session=mock_session,
            )
            assert score == pytest.approx(1.0 - 10.0 / 11.0, abs=1e-9)
            assert flag is expected_flag

    @pytest.mark.asyncio
    async def test_samples_gate_is_strictly_less_than(self) -> None:
        """total_samples == min_samples must NOT be 'insufficient' (kills < -> <=)."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)
        person = self._mk(10.0, 10, "person", timedelta(0), now)  # total == min
        one_res = MagicMock()
        one_res.scalar_one_or_none.return_value = person
        all_res = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [person]
        all_res.scalars.return_value = scalars
        mock_session.execute.side_effect = [one_res, all_res]

        service = BaselineService(min_samples=10, decay_factor=1.0)
        flag, score = await service.is_anomalous(
            "cam-1", "person", datetime(2025, 12, 23, 14, 30, tzinfo=UTC), session=mock_session
        )
        assert score != 0.5  # must be the computed 0.0, not the neutral return
```

### Draft 5 — `TestInterpretZScoreBoundaries` (kills #8 = 11)

```python
class TestInterpretZScoreBoundaries:
    """// UNVERIFIED - not yet run red/green
    Existing tests use z ∈ {±.5}; the exact boundary values are the whole
    point of < vs <=.
    """

    @pytest.mark.parametrize(
        ("z_score", "expected_name"),
        [
            (-2.0, "FAR_BELOW_NORMAL"),   # < keeps FAR_BELOW only strictly below... see note
            (-1.0, "BELOW_NORMAL"),
            (1.0, "NORMAL"),
            (2.0, "SLIGHTLY_ABOVE_NORMAL"),
            (3.0, "ABOVE_NORMAL"),
        ],
    )
    def test_exact_band_boundaries(self, z_score: float, expected_name: str) -> None:
        from backend.api.schemas.baseline import DeviationInterpretation

        service = BaselineService()
        assert service._interpret_z_score(z_score).name == expected_name

    def test_update_config_boundary_values_accepted(self) -> None:
        """threshold 0.1 is legal; 0 raises. min_samples 1 legal; 0 raises."""
        service = BaselineService()
        service.update_config(threshold_stdev=0.1)
        assert service.anomaly_threshold_std == 0.1
        with pytest.raises(ValueError):
            service.update_config(threshold_stdev=0)
        service.update_config(min_samples=1)
        assert service.min_samples == 1
        with pytest.raises(ValueError):
            service.update_config(min_samples=0)
```

Note: boundary expectation follows original `<` semantics (e.g. z=−2.0 is NOT `< −2.0`, so falls through to BELOW_NORMAL — fix the first parametrize row to `(-2.0, "BELOW_NORMAL")` when running red/green; it must be *computed from the original operators*, and then `<=` mutants flip every row).

### Draft 6 — `TestUpdateBaselineDispatchesTimestampDerivedArgs` (kills #11 + #13 = 16)

```python
class TestUpdateBaselineDispatchesTimestampDerivedArgs:
    """// UNVERIFIED - not yet run red/green"""

    @pytest.mark.asyncio
    async def test_update_baseline_forwards_hour_day_camera_class(self) -> None:
        mock_session = AsyncMock()
        service = BaselineService()
        ts = datetime(2025, 12, 23, 14, 30, tzinfo=UTC)  # Tuesday -> weekday 1

        with patch.object(service, "_update_activity_baseline", new_callable=AsyncMock) as act, \
             patch.object(service, "_update_class_baseline", new_callable=AsyncMock) as cls_update:
            await service.update_baseline("cam-alpha", "person", ts, session=mock_session)

            sess, camera_id, hour, day_of_week, now = act.call_args[0]
            assert camera_id == "cam-alpha"
            assert hour == 14
            assert day_of_week == 1
            assert now is not None and now.tzinfo is not None

            sess2, camera_id2, detection_class, hour2, now2 = cls_update.call_args[0]
            assert camera_id2 == "cam-alpha"
            assert detection_class == "person"
            assert hour2 == 14
            assert now2 is not None
```

### One-liner sketches for the remaining TEST-GAP clusters (drafted inline in `test_baseline.py` during the fix wave)

- **#4 TG_STATS_SCORE (24):** in `TestGetCurrentDeviation`, set `avg_counts=[10.0,10.0,20.0]` → mean 13.333, std exact; assert `deviation.score == pytest.approx(expected, abs=0.01)` and that it's rounded to 2dp (`round(score,2)==score`); in `TestGetHourlyPatterns` assert `patterns["14"].std_dev == pytest.approx(2.0)` for [6.0,10.0] (kills `+mean`/`**3`/`*len`), assert `avg_detections == round(sum/len, 2)` with a fixture needing real rounding (e.g. 10/3).
- **#5 TG_STMT_NONE (20):** already covered by Drafts 1–3 (compiling the captured argument raises on `None` / fails the substring).
- **#15+#17 TG_SUMMARY_AGG/PAYLOAD (10):** two activity rows for hour 14 (5+7) assert `peak_hours[0]["total_activity"] == 12.0` and key name `"total_activity"`; 6 classes assert `len(summary["top_classes"]) == 5` and `"total_frequency"` key.
- **#9 TG_DAYNAME_KEY (10):** extend `test_get_daily_patterns_with_data` with `day_of_week=5` → `"saturday" in patterns`; `day_of_week=6` → `"sunday" in patterns`.
- **#16 TG_PEAK_ORDER (5):** `hour_activity={9:5.0, 14:15.0}` already asserts `peak_hour == 14`; add `get_object_baselines` fixture with two hours where max≠first-key (kills `key=None` — raises TypeError — and key-lambda removal).
- **#20 TG_TIMEDECAY_UNIT (1):** tighten `test_decay_one_day` to `assert decay == pytest.approx(0.1, abs=1e-6)`; same for `TestCalculateTimeDecay::test_decay_at_window_boundary`.
- **#21 TG_SINGLETON_RESET (1):** in `TestBaselineSingleton`: `reset_baseline_service(); import backend.services.baseline as mod; assert mod._baseline_service is None`.

## Evidence paths

- Survivors + verdict source: `mutants/backend/services/baseline.py.meta` (`exit_code_by_key`)
- Variant source: `mutants/backend/services/baseline.py` (786 mangled defs + trampoline registry)
- Working extracts: `/tmp/wp25/wp44-triage/.bl_surv.txt`, `.bl_blocks.pkl`, `.bl_diffs2.pkl`, `.bl_clusters_final.json`, `.bl_examples_final.json`
- Covering tests: `backend/tests/unit/services/test_baseline.py` (classes at lines 216–1895), `backend/tests/unit/services/test_baseline_properties.py:573`
