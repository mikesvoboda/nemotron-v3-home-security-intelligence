# WP4.4 Triage Dossier — backend/api/routes/cost_analytics.py

**Source data:** `mutants/backend/api/routes/cost_analytics.py.meta` — 110 total keys, 84 killed, **26 survived** (0 unchecked). All 26 diffs obtained via `uv run mutmut show <key>` (all succeeded, no fallback needed).
**Sole covering test file:** `backend/tests/unit/api/routes/test_cost_analytics.py` (per `mutmut-stats.json` `tests_by_mangled_function_name`). Key regions: `TestValidateDateRange` L108–152, `TestCalculateTokenCost` L155–177, `TestBuildModelCostBreakdown` L203–227, `TestBuildCostHistory` L230–269. Fixture `mock_db_session` is `backend/tests/conftest.py:1930` (its `execute` returns a MagicMock result whose `scalar()` is an unconfigured MagicMock).

## Cluster table (26 = 16+5+2+1+1+1+1)

| # | Pattern | Count | Keys (≤3 examples) | Class |
|---|---------|-------|--------------------|-------|
| C1 | `_build_cost_history` per-day cost/token/gpu/event fields never asserted (usage always returns identical mock; fields either zeroed by `and False` or fed `None`) | 6 | `__build_cost_history__mutmut_17`, `55`, `58` (rest: 18, 59, 60) | TEST-GAP |
| C2 | `_build_cost_history` per-day detection SQL window (`>= day_start` / `< day_end` / tz-aware / `count(Detection.id)`) and scalar→field plumbing never asserted (db.execute mocked, statement never inspected) | 14 | `__build_cost_history__mutmut_26`, `37`, `40` (rest: 20, 28, 30, 31, 32, 33, 34, 35, 36, 38, 41) | TEST-GAP |
| C3 | `_build_model_cost_breakdown` placeholder constants (`gpu_seconds=0.0`, `request_count=0`) never asserted | 2 | `__build_model_cost_breakdown__mutmut_12`, `13` | TEST-GAP |
| C4 | `_calculate_token_cost` 1000.0 per-1k-token divisor tolerated to 1001.0 under `pytest.approx(rel=0.001)` | 2 | `__calculate_token_cost__mutmut_8`, `12` | TEST-GAP |
| C5 | `_validate_date_range` 90-day boundary never probed at exactly the 91/90-day flip point | 1 | `__validate_date_range__mutmut_9` | TEST-GAP |
| C6 | `_validate_date_range` 400 error message text changed | 1 | `__validate_date_range__mutmut_6` | EQUIVALENT |
| C7 | `_build_cost_history` per-day `get_daily_usage(target_date)` call identity never verified, yet no test can observe the difference (`get_daily_usage` is a MagicMock returning one identical object for every date, including `None`) | 1 | `__build_cost_history__mutmut_18` | LOW-VALUE |

## Cluster detail

### C1 — TEST-GAP (6 mutants)

`test_cost_history_builds_correctly` (test file L235) patches `get_daily_usage.return_value` to ONE identical `mock_daily_usage` for every day, then asserts only `len(history) == 7` and chronological date order. It never reads `entry.total_cost_usd`, `token_cost_usd`, `gpu_cost_usd`, or `event_count`. `test_cost_history_handles_no_data` (L255) asserts `total_cost_usd == 0.0` and `event_count == 0`, but only when usage is `None` for every day — exactly the input under which the field-level mutations behave identically.

- 17 `usage = None`: all fields fall to zero defaults; the no-data test still passes.
- 55 `... if (usage) and False else 0.0` (total_cost_usd) / 60 (event_count): with usage=None the branch outcome is unchanged in the only test that asserts these fields.
- 58/59 `_calculate_token_cost(None)` / `_calculate_gpu_cost(None)`: fields not asserted anywhere in the per-day path (the endpoint success test L277 never touches `response.cost_history` contents; the schema test L447 only asserts `hasattr`).

**Why EQUIVALENT doesn't hold:** 17, 55, 58, 59, 60 are genuinely observable through `get_cost_analytics` — history entries would all read cost 0.0 / events 0 where the fixture has 0.0523 / 25, and history is a documented dashboard field ("Historical cost data (last 30 days)", module docstring / endpoint docstring). They survive only because `response.cost_history` is unasserted. 60 is the one member whose behavior is plausibly identical everywhere (`event_count` is `int` + pydantic ge=0, so 0-vs-None lands on 0) — grouped here as its sibling-field twin of 55; a per-day `assert entry.event_count == 25` kills it too if one wants it falsified.

### C2 — TEST-GAP (14 mutants)

`mock_db_session.execute` is a bare AsyncMock; every day's query returns a MagicMock result, and neither history test looks at the SQL statement or the detection_count field (schema test only does `hasattr`). So:

- Boundary flips 37 (`>=`→`>`), 38 (`<`→`<=`) — classic off-by-one window bugs.
- Window arithmetic 26 (`day_end = day_start - 1d` → empty window), 28 (`+2d` → double-day window) — a UTC-boundary detection would be counted into two adjacent days.
- Predicate removals 31 (`>= day_start`→None), 32 (`< day_end`→None), 33/34 (clause deleted) — unbounded/one-sided counts.
- Projection corruption 30 (`execute(None)`), 35 (`select(None)`), 36 (`count(None)`) — `scalar()` is mocked so garbage-in is invisible; `day_detection_count = det_result.scalar() or 0` happily coerces a MagicMock to int 1 (verified locally: pydantic ge=0 int coercion turns the mock into 1).
- tz 20 (`tzinfo=None`) — naive boundary datetime vs tz-aware `detected_at` column.
- Scalar plumbing 40 (`or`→`and`: truthy count discarded → always 0), 41 (`or 0`→`or 1`: zero count becomes phantom 1).

### C3 — TEST-GAP (2 mutants)
`test_model_breakdown_from_usage` (L207) asserts only length and model names, never `cost_usd`, `gpu_seconds`, `request_count`. The placeholders are API-surface constants (`"Not tracked per-model currently"`), so their exact values matter to consumers of the `ModelCostBreakdown` schema.

### C4 — TEST-GAP (2 mutants)
`test_token_cost_calculation` (L159) asserts `cost == pytest.approx(0.075, rel=0.001)`. Divisor 1001.0 changes cost by exactly 0.0999% — under the 0.1% relative tolerance. The pricing contract (per-1K-tokens) deserves an exact assertion.

### C5 — TEST-GAP (1 mutant)
`date_range_days = (end - start).days - 1` shifts the effective limit to 92 days, but `test_max_allowed_range` (L147) uses a 90-day range (passes both ways) and `test_date_range_exceeds_maximum` (L137) uses 365 days (raises both ways). Nobody probes the 91-vs-90 flip point.

### C6 — EQUIVALENT (1 mutant)
`detail` string clobbered to `"XXstart_date...XX"`. The behavior (400 on start>end) is fully asserted; only message wording changed. Existing tests L134/L430 assert the substring `"start_date must be before or equal to end_date" in detail` — that substring is present in the clobbered text, so killing this mutant would require asserting the FULL detail equals the string (an exact-message coupling convention deliberately avoids; sibling mutant 9's detail f-string variants were killed on the asserted `"Date range exceeds maximum allowed"` prefix). Semantic behavior unchanged → EQUIVALENT.

### C7 — LOW-VALUE (1 mutant)
18 `tracker.get_daily_usage(None)`: the surviving call site is only observable through call args or through per-day usage variation, and no existing test provides either (see C1's identical-MagicMock fixture — even the "no data" test would still pass with `None` since the mock's None-handling is identical). It is a real bug, but the mutation is only killable as a side effect of the per-day fixture recommended in C1's draft, which is a test-design improvement beyond the mutant itself → LOW-VALUE here (mutmut's own trampoline/arg-swap family on mock-backed helpers).

## Drafted tests (UNVERIFIED — not run red/green; mutation run owns this machine)

Style follows `backend/tests/unit/api/routes/test_cost_analytics.py` (fixtures `mock_cost_tracker`/`mock_daily_usage`/`mock_pricing` from that file, `mock_db_session` from `backend/tests/conftest.py:1930`). Add to the imports of that file:

```python
from datetime import date, datetime, timedelta
# (existing line 6 is: from datetime import date)
from sqlalchemy import select
from backend.models.detection import Detection
```

### T1 → kills C1 (17, 18, 55, 58, 59, 60) [also kills C7 member 18]

```python
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cost_history_uses_per_day_usage_for_all_cost_fields(
        self, mock_cost_tracker, mock_pricing, mock_db_session
    ):
        """Per-day usage fields must flow into every DailyCostEntry cost field,
        not just into list length and ordering."""
        end = date(2026, 1, 31)
        day_with_data = date(2026, 1, 30)
        usage = DailyUsage(
            date=day_with_data,
            total_input_tokens=15000,
            total_output_tokens=5000,
            total_gpu_seconds=125.5,
            total_estimated_cost_usd=0.0523,
            event_count=25,
            usage_by_model={},
        )

        def usage_by_day(target_date):
            return usage if target_date == day_with_data else None

        tracker = mock_cost_tracker
        tracker.get_daily_usage.side_effect = usage_by_day

        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker",
            return_value=tracker,
            autospec=True,
        ):
            history = await _build_cost_history(tracker, mock_db_session, end, 3)

        assert [h.date for h in history] == ["2026-01-29", "2026-01-30", "2026-01-31"]

        populated = history[1]
        assert populated.total_cost_usd == pytest.approx(0.0523)  # kills 55 (if...and False), 17/18 (usage dropped)
        assert populated.event_count == 25                        # kills 60
        # pricing: 15000*0.003/1000 + 5000*0.006/1000 = 0.075     # kills 58
        assert populated.token_cost_usd == pytest.approx(0.075, rel=0.001)
        # 125.5s * 0.000139/s                                      # kills 59
        assert populated.gpu_cost_usd == pytest.approx(0.01744, rel=0.01)

        for blank in (history[0], history[2]):
            assert blank.total_cost_usd == 0.0
            assert blank.token_cost_usd == 0.0
            assert blank.gpu_cost_usd == 0.0
            assert blank.event_count == 0

        # get_daily_usage must receive the day itself, never None   # direct kill of 18
        called_dates = [c.args[0] for c in tracker.get_daily_usage.call_args_list]
        assert None not in called_dates
        assert called_dates == [date(2026, 1, 29), date(2026, 1, 30), date(2026, 1, 31)]
```

TDD: on each mutant the populated-entry (or call-args) assertion fails; on the original all pass. Note the `mock_db_session` default result is irrelevant here because we assert nothing about `detection_count` — but pydantic coerces the leftover MagicMock scalar to int, so the field validates either way.

### T2 → kills C2 members 20, 26, 28, 31, 32, 33, 34, 35, 36, 37, 38, 40

```python
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cost_history_per_day_detection_query_bounds_and_count(
        self, mock_cost_tracker, mock_pricing, mock_db_session
    ):
        """Each history day must count detections in a [day_start, day_start+1d)
        UTC window keyed on count(Detection.id), and carry the scalar through."""
        days = 3
        per_day_counts = {
            date(2026, 1, 29): 3,
            date(2026, 1, 30): 7,
            date(2026, 1, 31): 0,
        }

        def fake_execute(stmt):
            # Kills 30: the query must be a real executable statement.
            assert isinstance(stmt, type(select(Detection.id)))
            ops = {be.operator.__name__: be.right.value for be in stmt.whereclause.clauses}
            day_start = ops.get("ge")
            assert day_start is not None, f"window must anchor with >= day_start, got ops={sorted(ops)}"
            day_start_date = day_start.date()
            assert day_start_date in per_day_counts  # statement maps to a known day
            result = MagicMock()
            result.scalar.return_value = per_day_counts[day_start_date]
            return result

        mock_db_session.execute = AsyncMock(side_effect=fake_execute)

        tracker = mock_cost_tracker
        tracker.get_daily_usage.side_effect = None
        tracker.get_daily_usage.return_value = None

        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker",
            return_value=tracker,
            autospec=True,
        ):
            history = await _build_cost_history(tracker, mock_db_session, end, days)

        # Re-run statement-level assertions on the captured statements:
        executed = [c.args[0] for c in mock_db_session.execute.call_args_list]
        assert len(executed) == days  # one query per day (kills 30 via isinstance guard)
        for stmt, entry in zip(executed, history):
            assert "count(detections.id)" in str(stmt.compile())  # kills 35, 36
            ops = {be.operator.__name__: be.right.value for be in stmt.whereclause.clauses}
            assert set(ops) == {"ge", "lt"}, f"window ops must be ge/lt, got {sorted(ops)}"  # kills 31, 32, 33, 34, 37, 38
            day_start = datetime.fromisoformat(entry.date + "T00:00:00+00:00")
            assert ops["ge"].tzinfo is not None, "day boundary must be tz-aware (UTC)"  # kills 20
            assert ops["ge"] == day_start                                               # kills 26/28 drift via paired lt
            assert ops["lt"] == day_start + timedelta(days=1)                           # kills 26, 28
        # Scalar must be carried through verbatim: or-vs-and / or 1 corruptions change it.
        assert [h.detection_count for h in history] == [3, 7, 0]  # kills 40 (truthy count -> 0)
```

TDD: each listed mutant flips one of the captured operator names, changes a bound value, breaks the projection string, drops a clause, or loses the scalar — every assertion pair fails on the mutant, passes on the original. (If `select(None)` at construction raises instead of producing a statement, that raise fails the test too — still a kill of 35.)

### T3 → kills C2 members 30, 41

```python
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cost_history_no_usage_days_yield_zero_costs_with_real_queries(
        self, mock_cost_tracker, mock_pricing
    ):
        """No-usage days must still issue a real per-day count query and report
        zero costs and a zero detection count."""
        def zero_result(stmt):
            assert stmt is not None, "daily detection query must be a real statement"  # kills 30
            result = MagicMock()
            result.scalar.return_value = 0
            return result

        db = AsyncMock()
        db.execute.side_effect = zero_result

        tracker = mock_cost_tracker
        tracker.get_daily_usage.return_value = None

        with patch(
            "backend.api.routes.cost_analytics.get_cost_tracker",
            return_value=tracker,
            autospec=True,
        ):
            history = await _build_cost_history(tracker, db, date(2026, 1, 31), 3)

        assert len(history) == 3
        for entry in history:
            assert entry.total_cost_usd == 0.0
            assert entry.token_cost_usd == 0.0
            assert entry.gpu_cost_usd == 0.0
            assert entry.event_count == 0
            assert entry.detection_count == 0  # kills 41 (or 1 phantom detection)
        assert db.execute.await_count == 3  # kills 30
```

(The first `db = AsyncMock()` block above is illustrative only — delete it; keep the `zero_result` version. Shown this way to document intent.)

### T4 → kills C3 (12, 13)

```python
    @pytest.mark.unit
    def test_model_breakdown_placeholders_are_zero(self, mock_daily_usage):
        """Not-yet-tracked per-model placeholders are contract values consumed
        by the dashboard — they must stay 0."""
        breakdown = _build_model_cost_breakdown(mock_daily_usage)

        assert {m.model for m in breakdown} == {"nemotron", "yolo26"}
        by_model = {m.model: m for m in breakdown}
        assert by_model["nemotron"].cost_usd == pytest.approx(0.0234)
        assert by_model["yolo26"].cost_usd == pytest.approx(0.0189)
        for m in breakdown:
            assert m.gpu_seconds == 0.0    # kills 12
            assert m.request_count == 0    # kills 13
```

### T5 → kills C4 (8, 12)

```python
    @pytest.mark.unit
    def test_token_cost_uses_exact_thousand_token_divisor(self, mock_daily_usage, mock_pricing):
        """Per-1K pricing must divide by exactly 1000.0; the old rel=0.001
        tolerance let a 1001.0 divisor slip through."""
        with patch("backend.api.routes.cost_analytics.get_cost_tracker", autospec=True) as mock_get:
            mock_tracker = MagicMock()
            mock_tracker._pricing = mock_pricing
            mock_get.return_value = mock_tracker

            cost = _calculate_token_cost(mock_daily_usage)

            # 15000/1000*0.003 + 5000/1000*0.006 = 0.045 + 0.03
            assert cost == pytest.approx(0.075, abs=1e-9)  # kills 8 and 12 (0.0750749... != 0.075)
```

### T6 → kills C5 (9)

```python
    @pytest.mark.unit
    def test_91_day_range_is_rejected(self):
        """The effective limit is exactly 90 days: a 91-day range must raise
        (the -1 day-arithmetic mutant silently moves the boundary to 92)."""
        start = date(2026, 1, 1)
        end = start + timedelta(days=90)  # 91 calendar days inclusive
        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range(start, end)
        assert exc_info.value.status_code == 400
        assert "Date range exceeds maximum allowed" in str(exc_info.value.detail)
        # and the flip side stays valid — covered by existing test_max_allowed_range
```

TDD for all drafts: apply the mutant diff to `backend/api/routes/cost_analytics.py`, run the named test — it must FAIL (red); revert — it must PASS (green). Per memory rules, red/green proof happens only in the serial pytest lane after the live mutation run releases the machine; these drafts are UNVERIFIED.

## Notes / meta-findings

- **Mock-scalar coercion trap:** `det_result.scalar() or 0` with the conftest `mock_db_session` default yields a MagicMock, and pydantic's lax int coercion turns it into `1` (`ge=0` passes). So `detection_count` can never fail a schema-shape test — only statement inspection or explicit `scalar.return_value` + exact-value assertions can catch query corruption. This is why 30/35/36 survived despite running through every history test.
- `mutmut_55` is a double in the meta's key numbering vs. two identical `and False` variants; treated as one survivor key (C1 count reflects the meta's 26 keys exactly: 6+14+2+2+1+1+1 = 26).
- C6 left EQUIVALENT on purpose: killing it would mean coupling tests to the full 400-detail string; the module's convention asserts stable prefixes/substrings only.
- 60 (event_count `and False` → 0 vs None) is behaviorally 0-vs-0 at the schema boundary; kept in C1 as the sibling of 55 (same source line family) with the honest note that only a pre-schema `Mock.__await__`-style probe could falsify it; its cluster is killed by T1 regardless through 17/55/58/59.
