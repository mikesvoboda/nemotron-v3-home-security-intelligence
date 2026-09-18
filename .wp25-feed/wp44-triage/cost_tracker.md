# WP4.4 Triage Dossier — backend/services/cost_tracker.py

**Run basis:** `mutants/backend/services/cost_tracker.py.meta` → 572 keys, **205 SURVIVED** (exit_code 0), 169 killed, 198 null (not yet checked; excluded).
**Covering test file (every function, per `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):** `backend/tests/unit/services/test_cost_tracker.py` (811 lines). Anchors: enrichment :275 · estimation :295-338 · budget status :375/:396 · monthly :476-502 · summary :505-539 · Redis :665-717 (`test_persist_usage` :669, `test_load_usage` :685) · edge cases :774-808.

**Diff method:** `uv run mutmut show <key>` verified (spot-checks); bulk diffs from slicing each `def x…__mutmut_N` variant of `mutants/backend/services/cost_tracker.py` against its embedded `__mutmut_orig` twin (raw: `/tmp/wp25/wp44-triage/survivor_diffs.txt`, 205/205 explained; `@_mutmut_mutated` lines at region ends are the *next* function's trampoline decorator, not mutations).
**Partition check:** machine-built, disjoint, exhaustive (`/tmp/wp25/wp44-triage/final_clusters.json`): 34 clusters, TEST-GAP 137 + EQUIVALENT 68 = **205**.

Keys below abbreviate `backend.services.cost_tracker.xǁCostTrackerǁ<fn>__mutmut_<n>`.

---

## Cluster table (authoritative — 34 clusters, n sums to 205)

| # | Pattern @ concern | n | Class | Ex. keys | Why / what test_cost_tracker.py misses | Kill |
|---|---|---|---|---|---|---|
| 1 | persist_usage hash **field-name constants** (Xx/UPPERCASE renames) | 16 | EQUIVALENT | persist 4, 6, 7 | Mocked Redis never sees the mapping; no round-trip. Contract risk flagged: killed for free by exact-mapping assert. | T01 |
| 2 | load_usage `decoded.get` **key-constant** renames | 18 | EQUIVALENT | load 51, 55, 63 | Symmetric reader side; `test_load_usage` (:685) feeds only all-keys-present records. | T04 |
| 3 | `logger.debug/info` message → `None` (enrichment/persist/load) | 3 | EQUIVALENT | persist 35, load 99, enrich 28 | Pure log text; logger patch asserts only `warning`. | — |
| 4 | estimate_cost component gates `> 0` → `>= 0` | 5 | EQUIVALENT | estimate 3, 10, 17 | Adds exactly `0 × price` = 0.0 (IEEE-754: finite×0.0==0.0) — output identical on every input. No test can kill. | — |
| 5 | budget ternary guards `> 0` → `>= 0` (4 sites) | 2 | EQUIVALENT (2) | budget 48, 56 | At budget=0 the ratio/exceeded fallbacks are pinned by existing 0-budget tests; guards only decide 0.0-vs-0.0 there. | T02 (free) |
| 6 | get_budget_status ternary guards `>= 0` / `> 1` | 4 | TEST-GAP | budget 33, 40, 41, 57 | `>= 0` at budget=0 raises ZeroDivisionError (method aborts; no test calls get_budget_status on the unlimited tracker); `> 1` distorts ratios for sub-$1 budgets. | T02 |
| 7 | `daily/monthly_exceeded` boundary `>= 1.0` → `> 1.0` | 2 | TEST-GAP | budget 46, 54 | Exactly-100% spend flips True→False; no boundary test. | T02 |
| 8 | exceeded misc (`>= 2.0`, `else True`, guard bool swaps) | 4 | TEST-GAP | budget 47, 50, 55, 58 | `else True` = "no budget set ⇒ exceeded"; unasserted combo. | T02 |
| 9 | warning_reached expression (`or`→`and`, boundary `>`, →None) | 4 | TEST-GAP | budget 59, 60, 61 | `warning_threshold_reached` never asserted anywhere. | T02 |
| 10 | month filter `d.year== and d.month==` → `or`/`!=` | 3 | TEST-GAP | budget 12, 13, 14 | All budget tests use fresh same-month trackers. | T02/T08 |
| 11 | get_monthly_usage filter `and` → `or` | 1 | TEST-GAP | monthly 8 | Single same-month record; adjacent month never seeded. | T08 |
| 12 | remaining floors `max(0.0, …)` → `max(1.0, …)` | 2 | TEST-GAP | budget 20, 27 | Overspend reports $1 remaining, not 0.0; exceeded tests assert only the flag. | T02 |
| 13 | ternary fallback constants 0.0→1.0 (daily_used, ratios) | 3 | TEST-GAP | budget 9, 35, 42 | Phantom $1 on empty day; unlimited ⇒ ratio 1.0 ⇒ false warning. | T02 |
| 14 | BudgetStatus field values → None (monthly_*, warning) | 7 | TEST-GAP | budget 22, 51, 66 | `test_get_budget_status` (:375) asserts 7 of 11 fields; every monthly field unasserted. | T02 |
| 15 | arithmetic flips (`-` in max, `*` for ratio) | 2 | TEST-GAP | budget 28, 39 | Floor masks the + variant until over-budget; product ratio needs mid-range assert. | T02 |
| 16 | `(cond) or True` / `and False` in budget+summary ternaries | 9 | TEST-GAP | budget 8, 31, 37 | `or True` crashes on empty tracker (`None.total_estimated_cost_usd`); `and False` forces 0.0 fallbacks / skips guards. | T02 |
| 17 | usage-summary dict **key constants** (Xx/UPPER) | 24 | EQUIVALENT | summary 42, 56, 80 | API consumers read these keys; unit tests touch 9 of ~21 leaves; T03/T08 pin the tested ones. | T03/T08 |
| 18 | summary aggregate math (`in-out`, `cost*events`, `>1` avg guard, else 1.0) | 4 | TEST-GAP | summary 11, 21, 23 | `this_month.total_tokens`/`avg_cost_per_event_usd` never asserted; existing test has exactly 1 event. | T03 |
| 19 | summary empty-day fallbacks 0→1 | 4 | TEST-GAP | summary 36, 41, 51 | `test_get_usage_summary_empty` (:508) asserts 3 of 13 leaf values. | T03 |
| 20 | summary values → None (tokens, gpu, avg) | 3 | TEST-GAP | summary 9, 12, 18 | Unasserted keys. | T03 |
| 21 | persist hset/expire args → None or dropped | 10 | TEST-GAP | persist 20, 21, 24 | `assert_called()` is arg-blind. | T01 |
| 22 | persist TTL constants (90d→91d/25h/61m, `/60`) + dropped `match=` | 7 | TEST-GAP | persist 28, 31, load 4 | `expire.assert_called()` without args. | T01 |
| 23 | persist key/data sub-expressions → None | (in 21) | TEST-GAP | persist 2, 3 | `hset(None, mapping=data)` still "called". | T01 |
| 24 | load_usage redis args / key-str sub-expressions → None | 6 | TEST-GAP | load 2, 5, 6 | Mocked scan_iter ignores `match`; `hgetall(None)` still returns fixture; key decode unasserted. | T04 |
| 25 | load_usage byte-decode predicates flipped `or True` | 4 | TEST-GAP | load 7, 8, 16, 19 | Production Redis uses decode_responses=True (core/redis.py:59) ⇒ *str*-payload path IS the production path; flipping it crashes str.decode — the all-`b"…"` fixture in :685 never hits it. | T04 (str fixture) |
| 26 | load_usage restored-field values → None | 7 | TEST-GAP | load 26, 28, 29 | `test_load_usage` asserts only `total_input_tokens`. | T04 |
| 27 | load_usage restored **kwargs dropped** (default masks) | 6 | TEST-GAP | load 36, 37, 41 | Verified raw: kwarg deleted from `DailyUsage(...)`; dataclass default silently zeroes it. | T04 |
| 28 | load_usage `decoded.get` fallback constants 0→1 / dropped | 21 | TEST-GAP | load 44, 49, 57 | Partial-record path (missing Redis field) never exercised. | T04 |
| 29 | `datetime.now(UTC)` → `now(None)` | 4 | TEST-GAP | enrich 18, budget 2 | Day-keying goes local-time; tests run UTC-aligned ⇒ invisible. | T06 |
| 30 | enrichment cost arithmetic (`*`→`/`, `+`→`-`) | 3 | TEST-GAP | enrich 2, 4, 6 | Only assert is `cost > 0`; `/` gives 7.2e6, `-` gives 6.9e-5 — both > 0. | T05 |
| 31 | enrichment metrics args → None / dropped args | 8 | TEST-GAP | enrich 19, 21, 22 | LLM twin (:199) proves the *pattern* of arg-asserts; enrichment tests have zero metrics asserts. | T05 |
| 32 | estimate_cost gates `> 0` → `> 1` (5 components) | 5 | TEST-GAP | estimate 4, 11, 18 | `estimate_cost(gpu_seconds=0.5)` ⇒ 0.0; every test passes units ≥ 1. | T07 |
| 33 | `cost +=` → `cost =` (input overwrites prior components) | 1 | TEST-GAP | estimate 5 | Combined test orders input_tokens first. | T07 |
| 34 | token divisor 1000.0→1001.0; `+=`→`-=` (enrichment) | 3 | TEST-GAP | estimate 9, 16, 30 | Tolerance 1e-4 swallows 8e-7 and 2e-5 deltas; tests use loose `abs(…) < 0.0001`. | T07 |

Class totals: **TEST-GAP 137, EQUIVALENT 68** (clusters 1-5 = 68; rest = 137). LOW-VALUE 0 — no debug hooks/cosmetic-only behaviors present.

---

## Drafted tests (ALL UNVERIFIED — not yet run red/green)

TDD procedure (each): add test → run against the mutant build, expect FAIL on the mutated line/field → run against original `backend/services/cost_tracker.py`, expect PASS. One test at a time.

Style: file has `from __future__ import annotations`; fixtures `cost_tracker` (budgets $10/$100, warn 0.8), `mock_metrics_service`, `mock_redis_client` (AsyncMock); `@pytest.mark.asyncio`; autouse `reset_singleton`.

### T01 — persist_usage wire contract → clusters 1, 21, 22, 23
Add to `TestRedisPersistence` after `test_persist_usage` (~:683):

```python
    @pytest.mark.asyncio
    async def test_persist_usage_writes_exact_hash_contract(
        self, mock_redis_client, mock_metrics_service
    ):
        """Test persisting writes the exact hash key, field map and 90-day TTL."""
        from datetime import date

        today = date(2026, 1, 15)
        tracker = CostTracker(redis_client=mock_redis_client)
        tracker._daily_usage[today] = DailyUsage(
            date=today,
            total_input_tokens=1000,
            total_output_tokens=500,
            total_gpu_seconds=2.5,
            total_images_processed=7,
            total_enrichment_operations=3,
            total_estimated_cost_usd=0.25,
            event_count=2,
        )

        await tracker.persist_usage()

        key = f"hsi:cost_tracking:daily:{today.isoformat()}"
        expected = {
            "date": today.isoformat(),
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "total_gpu_seconds": 2.5,
            "total_images_processed": 7,
            "total_enrichment_operations": 3,
            "total_estimated_cost_usd": 0.25,
            "event_count": 2,
        }
        mock_redis_client.hset.assert_awaited_once_with(key, mapping=expected)
        mock_redis_client.expire.assert_awaited_once_with(key, 90 * 24 * 60 * 60)
```

### T02 — budget status field-by-field at boundaries + unlimited leg → clusters 6-16
Add to `TestBudgetTracking` after `test_budget_exceeded_detection` (~:421):

```python
    @pytest.mark.asyncio
    async def test_budget_status_exact_fields_boundaries(self, mock_metrics_service):
        """Test every BudgetStatus field at the warning, 100%-exactly and unlimited edges."""
        tracker = CostTracker(
            daily_budget_usd=10.0, monthly_budget_usd=20.0, warning_threshold=0.8
        )
        # Inject synthetic spend: today $8.00 (exactly 80% daily), $18.00 month to date.
        today = datetime.now(UTC).date()
        first = today.replace(day=1)
        prior = first - timedelta(days=1)  # previous month — must be excluded
        tracker._daily_usage[today] = DailyUsage(date=today, total_estimated_cost_usd=8.0)
        tracker._daily_usage[first] = DailyUsage(date=first, total_estimated_cost_usd=10.0)
        tracker._daily_usage[prior] = DailyUsage(date=prior, total_estimated_cost_usd=50.0)

        status = await tracker.get_budget_status()

        assert status.daily_used_usd == 8.0
        assert status.monthly_used_usd == 18.0  # month window excludes prior month (cluster 10)
        assert status.daily_remaining_usd == 2.0
        assert status.monthly_remaining_usd == 2.0
        assert status.daily_utilization_ratio == pytest.approx(0.8)
        assert status.monthly_utilization_ratio == pytest.approx(0.9)
        assert not status.daily_exceeded  # exactly 80% is warning, not exceed
        assert status.warning_threshold_reached  # daily == threshold (clusters 8, 9)

        # Boundary: ratio lands on exactly 1.0 → exceeded True, remaining floored to 0.0
        tracker._daily_usage[today] = DailyUsage(date=today, total_estimated_cost_usd=10.0)
        boundary = await tracker.get_budget_status()
        assert boundary.daily_exceeded
        assert boundary.daily_remaining_usd == 0.0

        # Unlimited budgets must not divide, flag, or warn (clusters 6, 13)
        free = CostTracker(daily_budget_usd=0.0, monthly_budget_usd=0.0)
        free._daily_usage[today] = DailyUsage(date=today, total_estimated_cost_usd=5.0)
        open_status = await free.get_budget_status()
        assert open_status.daily_used_usd == 5.0
        assert open_status.daily_utilization_ratio == 0.0
        assert open_status.monthly_utilization_ratio == 0.0
        assert not open_status.daily_exceeded
        assert not open_status.monthly_exceeded
        assert not open_status.warning_threshold_reached
```

### T03 — usage summary full schema, empty day, one-event average → clusters 17(partial), 18, 19, 20
Add to `TestUsageSummary` after `test_get_usage_summary_with_data` (~:539):

```python
    def test_get_usage_summary_empty_day_defaults(self, cost_tracker, mock_metrics_service):
        """Test that a fresh tracker reports exact zero defaults on every summary leaf."""
        summary = cost_tracker.get_usage_summary()

        today = summary["today"]
        assert today["cost_usd"] == 0.0
        assert today["input_tokens"] == 0
        assert today["output_tokens"] == 0
        assert today["gpu_seconds"] == 0.0
        assert today["events"] == 0
        assert summary["this_month"]["total_tokens"] == 0
        assert summary["this_month"]["gpu_seconds"] == 0.0
        assert summary["this_month"]["days_tracked"] == 0
        assert summary["all_time"]["total_events"] == 0
        assert summary["all_time"]["avg_cost_per_event_usd"] == 0.0
        assert summary["all_time"]["days_tracked"] == 0
        assert summary["budgets"]["warning_threshold"] == 0.8
        assert summary["pricing"]["input_cost_per_1k_tokens"] == 0.003
        assert summary["pricing"]["output_cost_per_1k_tokens"] == 0.006
        assert summary["pricing"]["gpu_cost_per_second"] == 0.000139

    def test_get_usage_summary_single_event_averages(
        self, cost_tracker, mock_metrics_service
    ):
        """Test monthly token/gpu sums and the one-event average are exact."""
        cost_tracker.track_llm_usage(
            input_tokens=1000, output_tokens=500, model="nemotron", duration_seconds=2.5
        )
        cost_tracker.track_detection_usage(model="yolo26", duration_seconds=0.5)
        cost_tracker.increment_event_count()  # exactly ONE event

        summary = cost_tracker.get_usage_summary()

        assert summary["today"]["gpu_seconds"] == pytest.approx(3.0)
        assert summary["this_month"]["total_tokens"] == 1500  # in + out, never in - out
        assert summary["this_month"]["gpu_seconds"] == pytest.approx(3.0)
        assert summary["this_month"]["days_tracked"] == 1
        assert summary["all_time"]["total_events"] == 1
        expected_avg = summary["all_time"]["total_cost_usd"] / 1.0
        assert summary["all_time"]["avg_cost_per_event_usd"] == pytest.approx(expected_avg)
```

### T04 — load_usage round trip + partial record → clusters 2, 24, 25, 26, 27, 28 (+1 for free)
Add to `TestRedisPersistence` after `test_load_usage` (~:717):

```python
    @pytest.mark.asyncio
    async def test_load_usage_round_trips_all_fields(
        self, mock_redis_client, mock_metrics_service
    ):
        """Test load_usage restores every persisted field (round trip)."""
        from datetime import date

        day = date(2026, 1, 15)
        persisted = {
            "date": day.isoformat(),
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "total_gpu_seconds": 2.5,
            "total_images_processed": 7,
            "total_enrichment_operations": 3,
            "total_estimated_cost_usd": 0.25,
            "event_count": 2,
        }
        key = f"hsi:cost_tracking:daily:{day.isoformat()}"

        async def async_scan_iter(*args, **kwargs):
            assert kwargs.get("match") == "hsi:cost_tracking:daily:*"
            yield key.encode()

        mock_redis_client.scan_iter = async_scan_iter
        mock_redis_client.hgetall = AsyncMock(return_value=dict(persisted))

        writer = CostTracker(redis_client=mock_redis_client)
        writer._daily_usage[day] = DailyUsage(**persisted)
        await writer.persist_usage()
        assert mock_redis_client.hset.await_args.kwargs["mapping"] == persisted

        reader = CostTracker(redis_client=mock_redis_client)
        await reader.load_usage()

        usage = reader.get_daily_usage(day)
        assert usage is not None
        mock_redis_client.hgetall.assert_any_call(key)  # key-str decode, not None
        assert usage.total_input_tokens == 1000
        assert usage.total_output_tokens == 500  # kills dropped-kwarg mutants
        assert usage.total_gpu_seconds == 2.5
        assert usage.total_images_processed == 7
        assert usage.total_enrichment_operations == 3
        assert usage.total_estimated_cost_usd == 0.25
        assert usage.event_count == 2

    @pytest.mark.asyncio
    async def test_load_usage_partial_record_uses_zero_defaults(
        self, mock_redis_client, mock_metrics_service
    ):
        """Test a hash missing optional fields restores them as 0, never 1."""
        from datetime import date

        day = date(2026, 1, 15)
        key = f"hsi:cost_tracking:daily:{day.isoformat()}"

        async def async_scan_iter(*args, **kwargs):
            yield key.encode()

        mock_redis_client.scan_iter = async_scan_iter
        mock_redis_client.hgetall = AsyncMock(
            return_value={"date": day.isoformat(), "total_input_tokens": 1000}
        )

        tracker = CostTracker(redis_client=mock_redis_client)
        await tracker.load_usage()

        usage = tracker.get_daily_usage(day)
        assert usage is not None
        assert usage.total_input_tokens == 1000
        assert usage.total_output_tokens == 0
        assert usage.total_gpu_seconds == 0.0
        assert usage.total_images_processed == 0
        assert usage.total_enrichment_operations == 0
        assert usage.total_estimated_cost_usd == 0.0
        assert usage.event_count == 0

    @pytest.mark.asyncio
    async def test_load_usage_accepts_str_payloads(
        self, mock_redis_client, mock_metrics_service
    ):
        """Test load_usage works with decode_responses=True payloads (str, not bytes)."""
        from datetime import date

        day = date(2026, 1, 15)
        key = f"hsi:cost_tracking:daily:{day.isoformat()}"

        async def async_scan_iter(*args, **kwargs):
            yield key  # str: scan_iter yields decoded keys with decode_responses=True

        mock_redis_client.scan_iter = async_scan_iter
        mock_redis_client.hgetall = AsyncMock(
            return_value={"date": day.isoformat(), "event_count": 2}
        )

        tracker = CostTracker(redis_client=mock_redis_client)
        await tracker.load_usage()

        usage = tracker.get_daily_usage(day)
        assert usage is not None
        assert usage.event_count == 2
```

### T05 — enrichment record + metrics parity → clusters 30, 31 (+29 log side-effects N/A)
Add to `TestEnrichmentUsageTracking` (~:293):

```python
    def test_track_enrichment_usage_calculates_cost_and_records_metrics(
        self, cost_tracker, mock_metrics_service
    ):
        """Test enrichment cost = gpu*price + ops*price and metrics carry exact args."""
        record = cost_tracker.track_enrichment_usage(
            model="florence", duration_seconds=0.5, operations=3
        )

        expected = (0.5 * 0.000139) + (3 * 0.00001)
        assert record.estimated_cost_usd == pytest.approx(expected)
        mock_metrics_service.record_gpu_seconds.assert_called_once_with("florence", 0.5)
        mock_metrics_service.record_estimated_cost.assert_called_once_with(
            "florence", pytest.approx(expected)
        )
```

### T06 — UTC day-keying → cluster 29
Add to `TestEdgeCases` (end of file ~:808):

```python
    def test_daily_bucket_keys_on_utc_day(self, mock_metrics_service):
        """Test the daily bucket uses the UTC calendar day, not local time."""
        from datetime import datetime as dt

        utc_instant = dt(2026, 1, 15, 23, 30, tzinfo=UTC)
        with patch("backend.services.cost_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = utc_instant
            tracker = CostTracker()
            tracker.increment_event_count()
        assert utc_instant.date() in tracker._daily_usage

    def test_clock_calls_pass_utc(self):
        """White-box guard: no datetime.now() or datetime.now(None) in the module."""
        import inspect
        import re

        src = inspect.getsource(sys.modules[CostTracker.__module__])
        assert re.search(r"datetime\.now\((?:None|\s*)\)", src) is None
```

**Honesty note:** with `datetime` patched, `now(UTC)` and `now(None)` return the same object, so the behavioral half of T06 is weak on its own; the source-regex guard is the real killer for the `now(None)` variants. If white-box source inspection is barred for this repo, flag cluster 29 as needing an integration-level TZ test instead (accepting the survivors for now). Needs `import sys` (file does not currently import it).

### T07 — estimate_cost exactness → clusters 32, 33, 34
Add to `TestCostEstimation` (~:338); requires adding `DEFAULT_PRICING` to the module's import list from `backend.services.cost_tracker`:

```python
    def test_estimate_cost_single_unit_components(self, cost_tracker, mock_metrics_service):
        """Test each component contributes for a single unit at exact pricing (no tolerance)."""
        p = DEFAULT_PRICING
        assert cost_tracker.estimate_cost(input_tokens=1) == pytest.approx(
            (1 / 1000.0) * p.input_cost_per_1k_tokens
        )
        assert cost_tracker.estimate_cost(output_tokens=1) == pytest.approx(
            (1 / 1000.0) * p.output_cost_per_1k_tokens
        )
        assert cost_tracker.estimate_cost(gpu_seconds=0.5) == pytest.approx(
            0.5 * p.gpu_cost_per_second
        )  # kills >1 gate mutants
        assert cost_tracker.estimate_cost(images=1) == pytest.approx(
            1 * p.detection_cost_per_image
        )
        assert cost_tracker.estimate_cost(operations=1) == pytest.approx(
            1 * p.enrichment_cost_per_operation
        )
        assert cost_tracker.estimate_cost() == 0.0
        # >= 0 gate mutants stay green here by construction (EQUIVALENT) — intentional.

    def test_estimate_cost_input_after_other_component(
        self, cost_tracker, mock_metrics_service
    ):
        """Test input-token cost accumulates instead of overwriting earlier components."""
        p = DEFAULT_PRICING
        cost = cost_tracker.estimate_cost(gpu_seconds=10.0, input_tokens=1000)
        assert cost == pytest.approx(
            10.0 * p.gpu_cost_per_second + 1.0 * p.input_cost_per_1k_tokens
        )
```

Exact-ish asserts also kill the 1001.0-divisor (cluster 34; tolerance in existing tests is 1e-4 > the 8e-7 delta) and the `+=`→`-=` enrichment flip (cluster 34; 2e-5 delta).

### T08 — monthly usage month isolation → cluster 11 (+month-window double-check)
Add to `TestMonthlyUsage` (~:502):

```python
    def test_get_monthly_usage_excludes_adjacent_months(
        self, cost_tracker, mock_metrics_service
    ):
        """Test filtering is AND of year and month, and is exact-match."""
        from datetime import date

        jan = date(2026, 1, 15)
        feb = date(2026, 2, 10)
        other_year = date(2025, 1, 20)
        for day in (jan, feb, other_year):
            cost_tracker._daily_usage[day] = DailyUsage(
                date=day, total_estimated_cost_usd=1.0
            )

        assert [u.date for u in cost_tracker.get_monthly_usage(2026, 1)] == [jan]
        assert [u.date for u in cost_tracker.get_monthly_usage(2026, 2)] == [feb]
        assert [u.date for u in cost_tracker.get_monthly_usage(2025, 1)] == [other_year]
```

---

## Kill-matrix summary (drafted tests → clusters)

| Test | Clusters killed (n) | Direct | Free (EQUIVALENT-but-contract) |
|---|---|---|---|
| T01 | 21,22,23 (17) | — | 1 (16, via exact mapping) |
| T02 | 6,7,8,9,12,13,14,15,16 (28) + 10 (3) | 31 | 5 (2) |
| T03 | 18,19,20 (11) | — | 17 partial (24) |
| T04 | 24,25,26,27,28 (46) + 2 partially | 46 | 2 (18), 1 (16) |
| T05 | 30,31 (11) | | |
| T06 | 29 (4) | | |
| T07 | 32,33,34 (9) | | 4 (5) stays green — proven-equivalent |
| T08 | 11 (1) | | 10 overlap |

Residual after all eight: the EQUIVALENT clusters (4: n=5; plus 1/2/17 key-rename survivors not covered by a field assert — recommend the WP4.4 owner add one `assert set(summary) == {...}` / mapping-keys assert if the roadmap wants those pinned) and cluster 5's two guards. No LOW-VALUE residue.

**Machine-readable partition:** `/tmp/wp25/wp44-triage/final_clusters.json` · raw diffs: `/tmp/wp25/wp44-triage/survivor_diffs.txt` · survivor keys: `/tmp/wp25/wp44-triage/survivor_keys_cost_tracker.txt`.
