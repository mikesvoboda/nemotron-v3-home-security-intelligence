# WP4.4 triage dossier — backend/services/calibration_monitor.py

Wave: gen-2, first tally for this module. Meta snapshot: `mutants/backend/services/calibration_monitor.py.meta` (201 keys: 114 killed, 87 survived, 0 unchecked).

- Module: `backend/services/calibration_monitor.py` (341 lines, CalibrationMonitor / CalibrationStatus / singleton factory)
- Covering test file (sole): `backend/tests/unit/test_calibration_monitor.py` (445 lines) — per `mutmut-stats.json` `tests_by_mangled_function_name`, every surviving function maps only to this file.
- Diffs taken via `uv run mutmut show <key>` (all 87 succeeded, no cache contention).
- Production surface: `record_score` is called live from `backend/services/nemotron_analyzer.py:4240`; `check_calibration` feeds the analytics route `get_calibration_status` (`backend/api/routes/analytics.py:736-759`) — that route reads the dataclass fields directly and does **not** use `to_dict()`; `CalibrationStatus.to_dict` has no production caller found in the repo (lowers severity of the G cluster but it is a public serialization method whose own test executes every line).

## Classification totals

| Class      | Count |
|------------|-------|
| TEST-GAP   | 39    |
| LOW-VALUE  | 41    |
| EQUIVALENT | 7     |
| **Total**  | **87** |

## Per-cluster table

Cluster keys below use the `__mutmut_N` number within the named function (prefix `backend.services.calibration_monitor.xǁ<qual>ǁ`).

| # | Cluster | Fn | Pattern | n | Class | Kill mechanism / note |
|---|---------|----|---------|---|-------|------------------------|
| A | A | check_calibration | Returned status fields swapped to `None`: `target_pct=None` (20), `is_drifting=None` (22), `window_seconds=None` (34), `drift_threshold_pct=None` (35) | 4 | TEST-GAP | Tests read `status.total_scores`/`actual_pct`/global `is_drifting` but never `status.window_seconds`, `status.drift_threshold_pct`, `tier.target_pct`, or `tier.is_drifting`. Killed by T5. |
| B | B | check_calibration | Drift boundary flip `deviation > threshold` → `>=` (16) | 1 | TEST-GAP | No test has deviation exactly == threshold (custom-threshold test uses dev 5.0 vs thresh 10.0, line 227-250). Killed by T3 (dev == 5.0 must NOT drift). |
| C | C | check_calibration | `len(drifting_tiers) > 0` → `> 1` (31): global flag False when exactly one tier drifts | 1 | TEST-GAP | Existing drift tests have 3 or 4 drifting tiers; empty-window and custom-threshold tests have 4 and 0. Exactly-one-drifting-tier never exercised. Killed by T4/T5. |
| D1 | D | _cleanup_expired | Window bound / Redis call shape: `cutoff=None` (1), `cutoff=time.time()+window` (2), call `...,"-inf",None` (6), cutoff arg dropped (9) | 4 | TEST-GAP | `test_cleanup_expired_scores` (line 252-266) asserts `call_args[0][0]==KEY`, `[0][1]=="-inf"` but the cutoff positional — where the window math lands — is explicitly NOT asserted (file has the comment "should be approximately now - 3600" and stops). Killed by T2. |
| D2 | D | _get_scores_in_window | Redis query args: `cutoff=None` (1), `cutoff=+window` (2), `key→None` (4), `cutoff→None` (5), `"+inf"→None` (6), args dropped (7,8,9), `"+inf"→"XX+infXX"` (10) | 9 | TEST-GAP | `test_get_scores_in_window_parses_members` (267-286) asserts only parsed return values — the AsyncMock ignores arguments entirely, and no test asserts the zrangebyscore call shape. Killed by T2. |
| E | E | record_score | `now = time.time()` → `None` (1): member becomes `"None:42"`, sorted-set score None | 1 | TEST-GAP | `test_record_score_calls_zadd` (96-111) asserts `member.endswith(":25")` — `"None:25".endswith(":25")` is True — and never asserts the mapping value (the sorted-set score) is a timestamp. Live impact: nemotron_analyzer's writes would land in Redis with an invalid score → silent except-path data loss. Killed by T6. |
| F | F | init_calibration_monitor | Singleton wires `redis_client=None` instead of the passed client (2) | 1 | TEST-GAP | `test_init_calibration_monitor_returns_instance` (365-371) asserts type + global identity but never that the monitor holds the client. One-line fix: add `assert monitor._redis is redis` to that existing test (not drafted as a separate cluster test — see note). |
| G | G | CalibrationStatus.to_dict | Output-schema key renames (`XXkeyXX`/`KEY` case clobbers on window_seconds, drift_threshold_pct, actual_pct, target_pct, deviation_pct: 3,4,5,6,15,16,22,23,24,25) + rounding mutations (round 2→None/3/arg-drop on actual_pct & deviation_pct: 18,19,20,21,27,28,29,30) | 18 | TEST-GAP | `test_to_dict` (391-424) asserts only 6 of 11 output entries and zero rounding — renamed keys and changed values execute unasserted. No production consumer (route reads fields), so severity moderate, but the method's own test is weak. Killed by T1 (exact dict equality). |
| L1 | L1 | check_calibration | Drift-warning log message text: `None` (45), `XX...XX` (49), lowercase (50), UPPERCASE (51) | 4 | LOW-VALUE | Human-facing log line; no caplog assertion anywhere and no log-text-driven alerting found (grep of config/**.yml/.yaml/json). Cosmetic per WP4.4 convention. |
| L2 | L2 | check_calibration | Drift-warning `extra=` payload: whole-payload drop/None (46,48), key clobbers on drifting_tiers/total_scores/distribution/actual/target/deviation (52-59,65-68), rounding tweaks (61-64,70-73) | 22 | LOW-VALUE | Changes only structured-log contents; no consumer of the extra keys found in repo (Prometheus rules, docs). Observability-only; nobody should have to assert a warning's payload. |
| L3 | L3 | record_score | Redis-failure warning: message clobbers (12,18,19,20), `exc_info=True→False/None/line-dropped` (13,16,21), `extra` drop/None/key-clobbers (14,17,22,23) | 11 | LOW-VALUE | Except-path logging cosmetics. `test_record_score_handles_redis_error` (124-132) asserts "does not raise" only; log-record shape is debug-surface, not asserted contract. |
| L4 | L4 | _cleanup_expired / _get_scores_in_window | Debug-log gating `removed > 0` → `>=0`/`>1` (cleanup 12,13) and message-arg `→ None` (cleanup 14, get 24) | 4 | LOW-VALUE | The `if removed > 0:` body is *only* a `logger.debug` call — control flow unchanged; `logger.warning(None)` is cosmetic (std logging stringifies). |
| Q1 | Q1 | _get_scores_in_window | `"+inf"` → `"+INF"` (11) | 1 | EQUIVALENT | Redis parses `+inf` case-insensitively; identical server-side range. Pure constant casing. |
| Q2 | Q2 | _get_scores_in_window | `member.rsplit(":", 1)` → `rsplit(":")` (17), `split(":", 1)` (18), `rsplit(":", 2)` (20) | 3 | EQUIVALENT | Members are written only as `f"{now}:{score}"` (exactly one colon; floats carry no colons). All variants yield the same `parts[1]`; colon-free malformed members still IndexError and are skipped identically (the malformed-members test passes unchanged under all three). |
| Q3 | Q3 | check_calibration | `actual_pcts.get(tier_name, 0.0)` → default dropped (10), `None` (8), `1.0` (11) | 3 | EQUIVALENT | Dead defensive default: `actual_pcts` keys come from `dict.fromkeys(self._target)` over the *same* `self._target` being iterated, so the default is never reached for any input. |

Count check: 4+1+1+4+9+1+1+18 (TEST-GAP=39) + 4+22+11+4 (LOW-VALUE=41) + 1+3+3 (EQUIVALENT=7) = **87**. ✔

## Covering-test weak spots (file:line)

All in `backend/tests/unit/test_calibration_monitor.py`:

- `test_record_score_calls_zadd` 96-111 — asserts member suffix, not the zadd mapping **value** (E).
- `test_record_score_handles_redis_error` 124-132 — "not raise" only (L3 context).
- `test_cleanup_expired_scores` 252-266 — asserts key + `"-inf"`, cutoff deliberately unchecked (D1).
- `test_get_scores_in_window_parses_members` 267-286 / `test_get_scores_handles_malformed_members` 288-307 — return-value only, call shape never inspected (D2, and proves Q2 equivalence behaviorally).
- `test_check_calibration_detects_drift` 181-210 / `_target_distribution` 148-179 / `_empty_window` 134-146 / `test_custom_drift_threshold` 227-250 — never touch `status.window_seconds`, `status.drift_threshold_pct`, `tier.target_pct`, `tier.is_drifting`; no deviation==threshold case; no exactly-one-drifting-tier case (A, B, C).
- `test_init_calibration_monitor_returns_instance` 365-371 — no client-plumbing assert (F).
- `TestCalibrationStatus.test_to_dict` 391-424 — 6 of 11 keys, no rounding (G).
- No `caplog` anywhere in the file (that is what keeps L1-L4 surviving).

## Drafted tests (6)

All target `backend/tests/unit/test_calibration_monitor.py`; they reuse the existing `_make_redis_mock()` helper (line 85-94) and `@pytest.mark.asyncio` style. T1 goes in `TestCalibrationStatus`; T2-T6 in `TestCalibrationMonitor`. T5/T6/T2 need two more imports from the module: add `DEFAULT_WINDOW_SECONDS, DEFAULT_DRIFT_THRESHOLD_PCT` to the existing `from backend.services.calibration_monitor import (...)` block.

**TDD procedure (same for all six):** add the test, run `uv run pytest backend/tests/unit/test_calibration_monitor.py -k <name>` against the mutant copy (`mutants/backend/services/calibration_monitor.py`) → red on the named mutant diff; run against `backend/services/calibration_monitor.py` → green.

### T1 — kills G (18 mutants). `// UNVERIFIED - not yet run red/green`

```python
    def test_to_dict_full_schema_and_rounding(self) -> None:
        """to_dict must expose the full documented schema with 2-dp rounding."""
        status = CalibrationStatus(
            total_scores=100,
            window_seconds=86400,
            drift_threshold_pct=5.0,
            is_drifting=True,
            tiers=[
                TierStatus(
                    tier="low",
                    actual_pct=80.126,
                    target_pct=85.0,
                    deviation_pct=5.678,
                    is_drifting=False,
                ),
            ],
            drifting_tiers=["low"],
        )

        d = status.to_dict()

        assert d == {
            "total_scores": 100,
            "window_seconds": 86400,
            "drift_threshold_pct": 5.0,
            "is_drifting": True,
            "drifting_tiers": ["low"],
            "tiers": [
                {
                    "tier": "low",
                    "actual_pct": 80.13,
                    "target_pct": 85.0,
                    "deviation_pct": 5.68,
                    "is_drifting": False,
                }
            ],
        }
```

Kills: any key rename (dict equality), `round(x, 3)` (80.126≠80.13), `round(x, None)`/`round(x)` (80≠80.13), `round(2)` call-arg drops. Fixture values verified: `round(80.126, 2)==80.13`, `round(5.678, 2)==5.68`, `round(80.126, None)==80`.

### T2 — kills D1 (4) + D2 (9) = 13 mutants. `// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_window_queries_use_correct_redis_call_shape(self) -> None:
        """Cleanup and range query must pass (key, -inf|cutoff, cutoff|+inf) with cutoff = now - window."""
        redis = self._make_redis_mock()
        redis.zremrangebyscore = AsyncMock(return_value=2)
        monitor = CalibrationMonitor(redis_client=redis, window_seconds=3600)

        before = time.time()
        await monitor._get_scores_in_window()
        after = time.time()

        cleanup_args = redis.zremrangebyscore.call_args[0]
        assert len(cleanup_args) == 3
        assert cleanup_args[0] == CALIBRATION_SCORES_KEY
        assert cleanup_args[1] == "-inf"
        assert before - 3600 <= cleanup_args[2] <= after - 3600

        query_args = redis.zrangebyscore.call_args[0]
        assert len(query_args) == 3
        assert query_args[0] == CALIBRATION_SCORES_KEY
        assert before - 3600 <= query_args[1] <= after - 3600
        assert query_args[2] == "+inf"
```

Kills: cutoff→None (comparisons raise TypeError = red), cutoff sign flip (`before-3600 <= t+3600` holds? — no: `t+3600 <= after-3600` fails), key→None, `"+inf"` clobbers, every dropped-arg variant via `len==3`.

### T3 — kills B (1 mutant). `// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_deviation_exactly_at_threshold_is_not_drifting(self) -> None:
        """A tier deviating exactly the threshold (not beyond) must not be flagged."""
        redis = self._make_redis_mock()
        now = time.time()
        # 90 low / 10 medium => low dev is exactly 5.0 vs the 5.0 default threshold
        members = [f"{now + i}:{10}" for i in range(90)]
        members += [f"{now + 90 + i}:{40}" for i in range(10)]
        redis.zrangebyscore = AsyncMock(return_value=members)
        monitor = CalibrationMonitor(redis_client=redis)

        status = await monitor.check_calibration()

        tier_map = {t.tier: t for t in status.tiers}
        assert tier_map["low"].deviation_pct == 5.0
        assert tier_map["low"].is_drifting is False
        assert not status.is_drifting
        assert status.drifting_tiers == []
```

Exact-float verified: `(90/100)*100.0 == 90.0`, `90.0-85.0 == 5.0`. Mutant `5.0 >= 5.0 → True` flips both asserts red.

### T4 — kills C (1 mutant). `// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_single_drifting_tier_sets_global_flag(self) -> None:
        """Exactly one drifting tier must still raise the global is_drifting flag."""
        redis = self._make_redis_mock()
        now = time.time()
        # low 92% (dev 7.0 > 5.0) is the ONLY drifting tier; medium dev 2.0
        members = [f"{now + i}:{10}" for i in range(92)]
        members += [f"{now + 92 + i}:{40}" for i in range(8)]
        redis.zrangebyscore = AsyncMock(return_value=members)
        monitor = CalibrationMonitor(redis_client=redis)

        status = await monitor.check_calibration()

        assert status.drifting_tiers == ["low"]
        assert status.is_drifting is True
```

Mutant `len(drifting_tiers) > 1 → is_drifting False` kills the last assert. (Also co-killed by T5.)

### T5 — kills A (4 mutants), co-kills C. `// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_check_calibration_populates_all_status_fields(self) -> None:
        """Every CalibrationStatus/TierStatus field the status carries must be populated."""
        redis = self._make_redis_mock()
        now = time.time()
        members = [f"{now + i}:{10}" for i in range(92)]
        members += [f"{now + 92 + i}:{40}" for i in range(8)]
        redis.zrangebyscore = AsyncMock(return_value=members)
        monitor = CalibrationMonitor(redis_client=redis)

        status = await monitor.check_calibration()

        assert status.total_scores == 100
        assert status.window_seconds == DEFAULT_WINDOW_SECONDS
        assert status.drift_threshold_pct == DEFAULT_DRIFT_THRESHOLD_PCT
        assert status.is_drifting is True
        assert status.drifting_tiers == ["low"]
        tier_map = {t.tier: t for t in status.tiers}
        assert tier_map["low"].target_pct == 85.0
        assert tier_map["low"].actual_pct == 92.0
        assert tier_map["low"].is_drifting is True
        assert tier_map["medium"].is_drifting is False
```

`window_seconds=None` / `drift_threshold_pct=None` / `target_pct=None` / tier `is_drifting=None` each break one assert. Needs `DEFAULT_WINDOW_SECONDS`, `DEFAULT_DRIFT_THRESHOLD_PCT` added to the module import block.

### T6 — kills E (1 mutant). `// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_record_score_uses_timestamp_as_sorted_set_score(self) -> None:
        """The sorted-set score must be the record timestamp, matching the member prefix."""
        redis = self._make_redis_mock()
        monitor = CalibrationMonitor(redis_client=redis)

        before = time.time()
        await monitor.record_score(42)
        after = time.time()

        mapping = redis.zadd.call_args[0][1]
        member = next(iter(mapping))
        ts_part, _, score_part = member.rpartition(":")
        assert score_part == "42"
        ts = float(ts_part)  # mutant writes member "None:42" -> ValueError here
        assert before <= ts <= after
        assert mapping[member] == ts
```

Kills `now=None` via the `float("None")` TypeError/ValueError and the mapping-value equality.

### F — not drafted; one-line fix instead

Append to existing `test_init_calibration_monitor_returns_instance` (line 365-371): `assert monitor._redis is redis`. Cheaper than a new test for a 1-mutant cluster; flagged here so the wave doesn't re-triage it.

## Residual notes

- Python 3.14.4 in-sandbox parses `except IndexError, ValueError:` at `calibration_monitor.py:205` (PEP 758 relaxed the paren requirement) — verified locally with `ast.parse` and a script run; the file compiles, no mutants are affected, but it will not parse on ≤3.9/CI-lower targets, worth a separate cleanup ticket outside WP4.4 scope.
- L2 severity lever: if a JSON-log consumer ever keys on `extra.drifting_tiers`, L2 promotes to TEST-GAP via a single caplog test; none exists today (grep across config/, docs/, *.yml/*.yaml/*.json found only unrelated yolo26 INT8 calibration assets).
