# WP4.4 Triage Dossier — backend/services/trend_service.py

- **Meta**: `mutants/backend/services/trend_service.py.meta` — 268 keys, 182 killed, **86 survivors**, 0 unchecked.
- **Diffs**: all 86 via `uv run mutmut show <key>` (worked; no manual fallback needed).
- **Covering test file (sole)**: `backend/tests/unit/services/test_trend_service.py` (per `mutmut-stats.json::tests_by_mangled_function_name`).
  Key anchor lines: `:23` hourly bucketing, `:51` daily bucketing, `:82` baseline avg, `:118-158` `_calculate_deviation` direct tests, `:165` high-risk threshold, `:196-291` edge cases, `:297` `_aggregate_into_buckets`, `:321` `_calculate_metrics_from_buckets`.
- **API/frontend contract**: `backend/api/routes/trends.py` (FastAPI `TrendsResponse` model), `frontend/src/types/trends.ts:30-35` (`values: number[]`, `baseline: number`, `deviation_pct: number` per metric).

## Root-cause observations (why so many survive)

1. **Shared mock return kills all window mutants.** Every test does `mock_repo.get_in_date_range = AsyncMock(return_value=same_list)` — the same events are returned for the *current* and the *baseline* fetch, and no test ever inspects the call arguments. So mutating `current_start`, `baseline_start`, `baseline_end`, or the fetch arguments changes nothing observable.
2. **The ternary guards are dead code.** `x / num_buckets if num_buckets > 0 else 0` appears 6× in `get_trend_data` (lines 228-230, 243-247). `num_buckets` is always 12 or 24 (module constants, never parameterized), so the `else` branch is unreachable — 39 survivors ride this dead branch.
3. **`BucketData["total_risk"]` is a dead field.** Written at `trend_service.py:94,113`, read nowhere (`_calculate_metrics_from_buckets` uses `risk_scores`). Grep across `backend/` and `frontend/` finds zero consumers.
4. **The try/except at line 270-290 masks every crash-path mutant** — the fallback response (`values=[0.0]*n, baseline=0.0, deviation=0.0`) is *byte-identical* to a legitimate no-data response, and the mock repo never raises, so tests cannot distinguish "fallback fired" from "all-zero data" unless they assert exact non-zero numbers or the fetch call args.
5. **Existing deviation tests use exact decimal inputs** (50.0, -20.0, 0.0) where `round(x, 1)`, `round(x, 2)`, and `round(x)` all agree — rounding-precision mutants survive.
6. **Baseline semantics quirk**: the baseline fetch spans 24 h (`baseline_start = now - BASELINE_WINDOW - current_window`), but `_aggregate_into_buckets(..., baseline_end, bucket_size, num_buckets)` only fills buckets in `[baseline_end - 1h, baseline_end]` for hourly — events older than that fetch but outside the 12 buckets vanish. Tests never construct events in that band, so `avg_risk.baseline` was never asserted with a nonzero, multi-decimal value.

## Cluster table (counts sum to 86)

| # | Pattern (function / concern) | Count | Class | Example keys (≤3) | Notes / kill condition |
|---|---|---|---|---|---|
| C1 | Ternary-guard mutants on the 6 avg computations `x/num_buckets if num_buckets>0 else 0` — whole-expr→None, `and False`/`or True` wrappers, `/`→`*`, `>0`→`>=0`/`>1`, `else 0`→`else 1` (`get_trend_data` lines 228-230, 243-247) | 39 | **LOW-VALUE** | `…get_trend_data__mutmut_58`, `…mutmut_61`, `…mutmut_112` | `num_buckets` is a module constant (12/24) — guard condition always True, else-branch unreachable; `*`↔`/` and `else 1` only differ on unreachable input. Nobody should assert on a parameterized-zero-bucket config (would need to patch `HOURLY_NUM_BUCKETS`). |
| C2 | `round(v, 1)` precision literal → `None` / omitted / `2` in avg-risk bucket metrics + the three displayed baselines (`_calculate_metrics_from_buckets:145`, `get_trend_data:253,258,263`) | 12 | **TEST-GAP** | `…_calculate_metrics_from_buckets__mutmut_19`, `get_trend_data__mutmut_132`, `…mutmut_154` | Test file computes avg_risks only with exactly-representable values (`test_trend_service.py:321` — 50.0/60.0/0.0) and asserts baseline only `>= 0` (`:115`). Needs a bucket avg / baseline with ≥2 real decimals. Killed by T2. |
| C3 | Response dict key string clobbered (`"values"`→`"XXvaluesXX"`/`"VALUES"`, `"deviation_pct"`→clobbers) for `avg_risk` + `high_risk_count` (`get_trend_data:257-266`) | 6 | **TEST-GAP** | `get_trend_data__mutmut_144`, `…mutmut_155`, `…mutmut_174` | `event_count` key mutants were killed; the other two metrics' key sets are never asserted. Breaks the FastAPI `TrendsResponse` schema and `frontend/src/types/trends.ts` contract. Killed by T2 (`set(result[m]) == {...}`). |
| C4 | Current-average argument to `_calculate_deviation` replaced with `None` (`get_trend_data:254,259,264`) → TypeError → swallowed by outer `except` → silent all-zero fallback | 3 | **TEST-GAP** | `get_trend_data__mutmut_138`, `…mutmut_157`, `…mutmut_176` | Real degradation: live dashboard silently goes flat. Existing tests can't tell fallback from no-data (obs. 4). Killed by T2 exact-number asserts. |
| C5 | Window datetime arithmetic + `get_in_date_range` call args mutated (`get_trend_data:202-205,209,212`) | 14 | **TEST-GAP** | `get_trend_data__mutmut_17`, `…mutmut_22`, `…mutmut_25` | Tests never look at the two fetch calls' args (obs. 1). Killed by T2 companion T1 (assert both calls' args against captured `now`). |
| C6 | Trend-config constants mutated: `DAILY_BUCKET_SIZE`→None, daily/hourly `current_window` 24h→25h, 1h→2h (`get_trend_data:192-198`) | 3 | **TEST-GAP** | `get_trend_data__mutmut_6`, `…mutmut_10`, `…mutmut_15` | Same no-arg-inspection root cause; killed by T1 (hourly) + T6 (daily). |
| C7 | Constructor attribute → None: `self.db = None`, `EventRepository(None)` (`__init__:175-176`) | 2 | **LOW-VALUE** | `__init____mutmut_1`, `__init____mutmut_3` | `self.db` is never read anywhere in `backend/`; `EventRepository(None)` is invisible under the autospec'd repo patch. `self.db` is documented public surface — a 2-line `assert service.db is mock_db / assert service.repo is mock_repo.return_value` kills both cheaply (not drafted — priority went to behavioral clusters). |
| C8 | Empty-bucket init `"total_risk": 0.0` → `1.0` (`_aggregate_into_buckets:94`) | 1 | **EQUIVALENT** | `…_aggregate_into_buckets__mutmut_9` | `total_risk` never read downstream (obs. 3); no observable difference anywhere. |
| C9 | Bucket boundary guard `0 <= bucket_index < num_buckets` → `<= num_buckets` (`_aggregate_into_buckets:109`) | 1 | **TEST-GAP** | `…_aggregate_into_buckets__mutmut_23` | On the original an event exactly `num_buckets` buckets ago is excluded; on the mutant it indexes one past the end → `IndexError` (which the service's try/except would convert to an all-zero response for any real event at that age). Test file's aggregate test only places events in buckets 0-1 (`:306-319`). Killed by T4. |
| C10 | `total_risk` accumulation operator `+=` → `=` / `-=` (`_aggregate_into_buckets:113`) | 2 | **EQUIVALENT** | `…_aggregate_into_buckets__mutmut_30`, `…mutmut_31` | Dead field again (obs. 3) — unobservable through any public surface. Drafted T5 nonetheless kills them at the unit level (cheap, pins field semantics). |
| C11 | `_calculate_deviation` rounding digits `1` → `None` / omitted / `2` (`:68`) | 3 | **TEST-GAP** | `…_calculate_deviation__mutmut_5`, `…mutmut_7`, `…mutmut_12` | Existing tests at `test_trend_service.py:118-158` use values where all roundings coincide (obs. 5). Needs a third-decimal case. Killed by T3. |

**Totals**: TEST-GAP 6 clusters / 41 survivors (C2,C3,C4,C5,C6,C9,C11 → 12+6+3+14+3+1+3 = 41, spanning 7 cluster entries), LOW-VALUE 2 / 41 (C1,C7), EQUIVALENT 2 / 4 (C8,C10). 41+41+4 = 86.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for each: add test → run against the mutant copy (assert must FAIL on the mutant diff) → run against `backend/services/trend_service.py` original (assert must PASS). Target file: `backend/tests/unit/services/test_trend_service.py`.

```python
# =====================================================================
# WP4.4 kill-tests for trend_service survivors.
# // UNVERIFIED - not yet run red/green
# =====================================================================


class TestTrendServiceWindowContract:
    """The two repository fetches must use the documented window offsets."""

    @pytest.mark.asyncio
    async def test_fetches_current_and_baseline_windows_at_documented_offsets(
        self,
    ) -> None:
        """Hourly: current = [now-1h, now]; baseline = [now-25h, now-1h].

        Kills C5 (14 keys: window arithmetic + get_in_date_range args) and
        C6 key mutmut_15 (hourly current_window 1h -> 2h). The service's
        except-branch fallback is indistinguishable from zero data in the
        result, so the kill signal is the recorded call arguments.
        """
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch(
            "backend.services.trend_service.EventRepository", autospec=True
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_in_date_range = AsyncMock(return_value=[])

            service = TrendService(mock_db)
            await service.get_trend_data("hourly")

            calls = mock_repo.get_in_date_range.await_args_list
            assert len(calls) == 2, "expected a current-window and a baseline fetch"

            # The current fetch's end argument IS `now` (trend_service.py:209).
            current_start, now = calls[0].args
            assert current_start == now - timedelta(hours=1)
            # Baseline window sits 24h before the current window (lines 204-205).
            assert calls[1].args == (
                now - timedelta(hours=25),
                now - timedelta(hours=1),
            )

    @pytest.mark.asyncio
    async def test_daily_uses_24h_window_and_one_hour_bucket_size(self) -> None:
        """Daily: current = [now-24h, now]; baseline = [now-48h, now-24h];
        events must land in 1-hour buckets. Kills C6 keys mutmut_6, mutmut_10.
        """
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch(
            "backend.services.trend_service.EventRepository", autospec=True
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            now = datetime.now(UTC)
            mock_repo.get_in_date_range = AsyncMock(
                return_value=[
                    MagicMock(started_at=now - timedelta(minutes=5), risk_score=75),
                ]
            )

            service = TrendService(mock_db)
            result = await service.get_trend_data("daily")

            calls = mock_repo.get_in_date_range.await_args_list
            assert len(calls) == 2
            current_start, now_arg = calls[0].args
            assert current_start == now_arg - timedelta(hours=24)
            assert calls[1].args == (
                now_arg - timedelta(hours=48),
                now_arg - timedelta(hours=24),
            )
            # bucket_size=None (mutmut_6) raises TypeError inside the service's
            # try-block -> all-zero fallback, so pin an exact placement.
            assert result["event_count"]["values"][0] == 1.0
            assert result["high_risk_count"]["values"][0] == 1.0
            assert sum(result["event_count"]["values"]) == 1


class TestTrendServiceResponseContract:
    """Exact numbers + key names for all three metrics with a live baseline."""

    @pytest.mark.asyncio
    async def test_metrics_expose_documented_keys_with_exact_rounded_numbers(
        self,
    ) -> None:
        """Kills C3 (6 key clobbers), C2 baseline-precision mutants (9), C4 (3
        deviation-arg-None), and C2 metrics-rounding mutmut_19/21/22 via the
        exact avg_risk values array (33.3 pins round(...,1) over round(...,2)
        and round(...)).
        Fixture math (hourly, 5-min buckets, 12 buckets):
          current  bucket0: scores 60, 80        -> avg 70.0, high 1, count 2
          current  bucket2: scores 33,33,34,33,34,33 -> avg 200/6 = 33.3 (2dp!)
          baseline bucket0: score 80 (high), bucket1: 40, bucket2: 41
            baseline totals: events 3, risk avgs 80+40+41=161, high 1
          baselines: events 3/12=0.25 -> round 0.2 (banker's; round(...,2)=0.25,
                     round(...,None)=0);  risk 161/12=13.4167 -> 13.4;
                     high 1/12=0.0833 -> 0.1
          deviations: event_count (8/12 vs 3/12) -> +166.7
                      avg_risk (103.3/12 vs 161/12) -> -35.8
                      high_risk (1/12 vs 1/12) -> 0.0
        A None deviation argument (C4) or a clobbered key (C3) breaks these
        asserts; the service's except-branch fallback zeroes the values arrays,
        which the exact values assert catches.
        """
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch(
            "backend.services.trend_service.EventRepository", autospec=True
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            now = datetime.now(UTC)

            current_events = [
                MagicMock(started_at=now - timedelta(minutes=2), risk_score=60),
                MagicMock(started_at=now - timedelta(minutes=3), risk_score=80),
                MagicMock(started_at=now - timedelta(minutes=10), risk_score=33),
                MagicMock(started_at=now - timedelta(minutes=10), risk_score=33),
                MagicMock(started_at=now - timedelta(minutes=11), risk_score=34),
                MagicMock(started_at=now - timedelta(minutes=12), risk_score=33),
                MagicMock(started_at=now - timedelta(minutes=13), risk_score=34),
                MagicMock(started_at=now - timedelta(minutes=14), risk_score=33),
            ]
            # Baseline events: inside [baseline_end-1h, baseline_end] =
            # [now-2h, now-1h] for hourly, i.e. 60-120 minutes ago.
            baseline_events = [
                MagicMock(started_at=now - timedelta(minutes=62), risk_score=80),
                MagicMock(started_at=now - timedelta(minutes=65), risk_score=40),
                MagicMock(started_at=now - timedelta(minutes=70), risk_score=41),
            ]
            mock_repo.get_in_date_range = AsyncMock(
                side_effect=[current_events, baseline_events]
            )

            service = TrendService(mock_db)
            result = await service.get_trend_data("hourly")

            # --- key contract (C3): every metric dict has exactly the
            # documented keys (frontend/src/types/trends.ts:30-35).
            for metric in ("event_count", "avg_risk", "high_risk_count"):
                assert set(result[metric]) == {"values", "baseline", "deviation_pct"}

            # --- values arrays (C2 metrics-rounding: bucket avg 33.3333 must
            # round to exactly 33.3 as a float, not 33.33 / 33 / int).
            zeros = [0.0] * 12
            expected_events = list(zeros)
            expected_events[0] = 2.0
            expected_events[2] = 6.0
            assert result["event_count"]["values"] == expected_events

            expected_risks = list(zeros)
            expected_risks[0] = 70.0
            expected_risks[2] = 33.3
            assert result["avg_risk"]["values"] == expected_risks
            assert all(isinstance(v, float) for v in result["avg_risk"]["values"])

            expected_high = list(zeros)
            expected_high[0] = 1.0
            assert result["high_risk_count"]["values"] == expected_high

            # --- baselines, rounded to exactly 1 decimal (C2 baseline mutants:
            # 0.25->0.2 vs 0.25/0; 13.4167->13.4 vs 13.42/13; 0.0833->0.1 vs
            # 0.08/0).
            assert result["event_count"]["baseline"] == 0.2
            assert result["avg_risk"]["baseline"] == 13.4
            assert result["high_risk_count"]["baseline"] == 0.1

            # --- deviations (C4: None current arg -> TypeError -> fallback).
            assert result["event_count"]["deviation_pct"] == 166.7
            assert result["avg_risk"]["deviation_pct"] == -35.8
            assert result["high_risk_count"]["deviation_pct"] == 0.0


class TestDeviationRounding:
    def test_deviation_rounds_to_one_decimal(self) -> None:
        """C11: 100*(1-3)/3 = -66.6666... -> round(...,1) = -66.7, but
        round(...,2) = -66.67 and round(...)/round(...,None) = -67. Existing
        deviation tests (test_trend_service.py:118-158) only use values where
        every rounding agrees."""
        from backend.services.trend_service import _calculate_deviation

        assert _calculate_deviation(1.0, 3.0) == -66.7


class TestBucketBoundary:
    def test_event_exactly_num_buckets_ago_is_excluded(self) -> None:
        """C9: `bucket_index < num_buckets` -> `<=` makes an event exactly
        num_buckets buckets old index buckets[num_buckets] -> IndexError."""
        from backend.services.trend_service import _aggregate_into_buckets

        now = datetime.now(UTC)
        buckets = _aggregate_into_buckets(
            [MagicMock(started_at=now - timedelta(minutes=60), risk_score=50)],
            now,
            timedelta(minutes=5),
            12,
        )
        assert sum(b["count"] for b in buckets) == 0  # out of range -> dropped

        near = _aggregate_into_buckets(
            [MagicMock(started_at=now - timedelta(minutes=59), risk_score=50)],
            now,
            timedelta(minutes=5),
            12,
        )
        assert near[11]["count"] == 1  # last legal bucket still fills


class TestBucketTotalRiskField:
    def test_total_risk_accumulates_all_non_null_scores(self) -> None:
        """C10: `+=` -> `=` keeps only the last score (60.0), `+=` -> `-=`
        negates the sum (-110.0). Also pins C8's empty-bucket init (0.0).
        Note: no production code currently reads total_risk, so this is a
        cheap field-semantics pin, not a behavioral gap."""
        from backend.services.trend_service import _aggregate_into_buckets

        now = datetime.now(UTC)
        buckets = _aggregate_into_buckets(
            [
                MagicMock(started_at=now - timedelta(minutes=2), risk_score=50),
                MagicMock(started_at=now - timedelta(minutes=3), risk_score=60),
                MagicMock(started_at=now - timedelta(minutes=4), risk_score=None),
            ],
            now,
            timedelta(minutes=5),
            12,
        )
        assert buckets[0]["count"] == 3
        assert buckets[0]["total_risk"] == pytest.approx(110.0)
        assert buckets[0]["risk_scores"] == [50, 60]
        assert buckets[1]["total_risk"] == 0.0
```

## Draft → cluster kill map

| Draft | Kills | Count |
|---|---|---|
| T1 `test_fetches_current_and_baseline_windows_at_documented_offsets` | C5 (all 14) + C6 mutmut_15 | 15 |
| T6 `test_daily_uses_24h_window_and_one_hour_bucket_size` | C6 mutmut_6, mutmut_10 | 2 |
| T2 `test_metrics_expose_documented_keys_with_exact_rounded_numbers` | C3 (6) + C2 (12) + C4 (3) | 21 |
| T3 `test_deviation_rounds_to_one_decimal` | C11 (3) | 3 |
| T4 `test_event_exactly_num_buckets_ago_is_excluded` | C9 (1) | 1 |
| T5 `test_total_risk_accumulates_all_non_null_scores` | C10 (2) + pins C8 init | 2 |

Drafts collectively kill 44 of 86. Not drafted against: C1 (39, LOW-VALUE dead guards — would require patching module constants to fabricate an unreachable config), C7 (2, LOW-VALUE — trivial attribute asserts available if desired), C8 (1, EQUIVALENT).
