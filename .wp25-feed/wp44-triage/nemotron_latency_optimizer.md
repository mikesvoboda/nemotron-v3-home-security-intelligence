# WP4.4 Triage Dossier — backend/services/nemotron_latency_optimizer.py

Source: 651 lines. Mutants generated: 317 (76 killed, **131 survived**, 110 not yet checked at read time —
survivor count may grow as the live run progresses; this dossier covers the 131 checked survivors).

**Covering test file (the module's only one):**
`backend/tests/unit/services/test_nemotron_latency_optimizer.py`

- `TestLatencyStats` L57–105 (`test_to_dict` L89–105)
- `TestNemotronLatencyOptimizer` L108–229 (`should_process_request` L118–128, `record_latency` L130–165,
  `get_adaptive_timeout` L167–203, `reset_circuit` L205–216, `get_status` L218–229)
- `TestAsyncSemaphoreContextManager` L232–273 · `TestGlobalOptimizer` L276–299 ·
  `TestSemaphoreAcquireTimeout` L302–312 · `TestOptimizerIntegration` L315–383

All diffs were extracted with `uv run mutmut show <key>` (read-only; full dump at
`/tmp/wp25/wp44-triage-work/nlo_diffs.txt`, 131/131, zero failures).

## Reading of the module (for classification judgment)

- `LatencyOptimizerConfig` is a plain dataclass with defaults **equal to the values passed explicitly in
  `get_nemotron_optimizer()`**, and the constructor does `config or LatencyOptimizerConfig()` — so deleting
  a kwarg there is a true no-op (EQUIVALENT), while bumping one by +1 is a real operating-envelope drift
  that no test reads (TEST-GAP).
- `self._redis` is stored at L236 and **never read** anywhere in the module → dropping `redis_client=` is
  semantically dead (EQUIVALENT).
- `LatencyStats.last_sample_time` is written at L413 and **never read** anywhere in backend/ → `= None`
  unobservable (EQUIVALENT).
- Log call-site text/`extra`-key mutations (XXclobber, case-flip, `None`-msg, `extra=None`) are never
  asserted — the module's tests use no caplog, and project tests assert **metrics**, not log text
  (cf. `backend/tests/unit/services/test_action_recognition_service.py` L78–114 idiom
  `.labels(...)._value.get()`). All 63 log mutants are EQUIVALENT.
- `to_dict()` emits `"p95_latency_seconds"` which IS consumed by `backend/api/routes/system.py` and
  `backend/api/schemas/system.py` (and generated frontend types), yet **no test ever asserts that key** —
  so even a constant-valued mutation (`round(self.p95_latency,3)` → `round(3)`) survives (TEST-GAP).
- `get_status()` asserts only 4 of its ~10 dict keys in `test_get_status` (L218–229) — 10 key-rename
  mutants survive (TEST-GAP).
- The `CircuitState` gauge family (0/1/2 encoding) is never asserted anywhere (TEST-GAP).
- `CircuitBreaker.record_failure()` transitions CLOSED→OPEN exactly at `failure_threshold` and
  `CircuitBreaker.reset()` → CLOSED (verified in `backend/services/circuit_breaker.py` L802–819) — safe
  basis for gauge/counter tests.

## Cluster table (counts sum to 131)

| #   | Cluster (function — mutation pattern)                                                                                                                                                           | n   | Class        | Example keys (suffix)                                                                                                                  |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `get_nemotron_optimizer` — config kwarg dropped / set to None (falls back to identical dataclass default)                                                                                       | 20  | EQUIVALENT   | `_mutmut_10, _12, _20`                                                                                                                 |
| 2   | `get_nemotron_optimizer` — whole `config=LatencyOptimizerConfig(...)` → `config=None` (`config or LatencyOptimizerConfig()` → same values)                                                      | 1   | EQUIVALENT   | `_2`                                                                                                                                   |
| 3   | `get_nemotron_optimizer` — **singleton config numeric bump** (`10.0→11.0`, `30.0→31.0`, `20→21`, `50→51`, `5→6`, `60.0→61.0`, `2.0→3.0`, and ctor `config=config→None`)                         | 9   | **TEST-GAP** | `_21, _22, _24`                                                                                                                        |
| 4   | `get_nemotron_optimizer` — `redis_client` arg dropped/None'd (field never read)                                                                                                                 | 2   | EQUIVALENT   | `_32, _34`                                                                                                                             |
| 5   | `get_nemotron_optimizer` — `logger.info` message text mutations                                                                                                                                 | 4   | EQUIVALENT   | `_35, _36, _37`                                                                                                                        |
| 6   | `LatencyStats.to_dict` — **`p95_latency_seconds` value mutations** (round-arg None/empty/4, and `round(3)` constant)                                                                            | 5   | **TEST-GAP** | `to_dict__4-equiv,_11,_12,_14` (full set: 4,6,11,12,13,14 of which 4/6 equiv-flavored; cluster kept whole — killed together by test B) |
| 7   | `LatencyStats.to_dict` — **`p95_latency_seconds` key rename** (consumed by API schema + frontend, unasserted)                                                                                   | 1   | **TEST-GAP** | `to_dict__8`                                                                                                                           |
| 8   | `LatencyStats.to_dict` — `rolling_average_seconds` round-arg mutation (`None`/empty = identity on tested int-valued floats; `3→4` unobservable at asserted precision)                           | 3   | EQUIVALENT   | `to_dict__4, _6, _7`                                                                                                                   |
| 9   | `LatencyStats.to_dict` — `last_latency_seconds` round-arg mutation (same reasoning)                                                                                                             | 3   | EQUIVALENT   | `to_dict__18, _20, _21`                                                                                                                |
| 10  | `record_latency` — log text/extra mutations across all 3 call sites (warning/error/debug; msg→None, case flips, XX-clobber, extra key renames, extra→None)                                      | 34  | EQUIVALENT   | `rl__13, _17, _36`                                                                                                                     |
| 11  | `record_latency` — **`total_requests += 1` → `= 1`** (counter reset each call; test only ever asserts after 1 call)                                                                             | 1   | **TEST-GAP** | `rl__1`                                                                                                                                |
| 12  | `record_latency` — **`circuit_trips += 1` → `= 1`** (second trip never counted)                                                                                                                 | 1   | **TEST-GAP** | `rl__31`                                                                                                                               |
| 13  | `record_latency` — **`was_open = self._circuit.state == OPEN` → `was_open = None`** (double-trip would double-count `circuit_trips`)                                                            | 1   | **TEST-GAP** | `rl__26`                                                                                                                               |
| 14  | `record_latency` — **`NEMOTRON_CIRCUIT_STATE_GAUGE.set(1)`→`set(2)` on trip and `set(0)`→`set(1)` on closed** (gauge never asserted)                                                            | 2   | **TEST-GAP** | `rl__35, _51`                                                                                                                          |
| 15  | `record_latency` — **success-branch gauge condition `== CLOSED` → `!= CLOSED`**                                                                                                                 | 1   | **TEST-GAP** | `rl__49`                                                                                                                               |
| 16  | `record_latency` — **threshold `>` → `>=`** at exactly 15.0 (= config boundary; no test runs the boundary)                                                                                      | 1   | **TEST-GAP** | `rl__9`                                                                                                                                |
| 17  | `record_latency` — `last_sample_time = None` (field has no readers)                                                                                                                             | 1   | EQUIVALENT   | `rl__6`                                                                                                                                |
| 18  | `reset_circuit` — **`NEMOTRON_CIRCUIT_STATE_GAUGE.set(0)` → `set(1)`**                                                                                                                          | 1   | **TEST-GAP** | `rc__4`                                                                                                                                |
| 19  | `reset_circuit` — `logger.info` text mutations                                                                                                                                                  | 4   | EQUIVALENT   | `rc__5, _6, _7`                                                                                                                        |
| 20  | `should_process_request` — log text/extra mutations on both shed paths + caution path                                                                                                           | 20  | EQUIVALENT   | `spr__7, _11, _21`                                                                                                                     |
| 21  | `should_process_request` — **queue bound `>=` → `>` (off-by-one: request at exactly `max_queue_depth` stops being shed)**                                                                       | 1   | **TEST-GAP** | `spr__2`                                                                                                                               |
| 22  | `should_process_request` — **shed-metric label `reason=LoadSheddingReason.QUEUE_TOO_DEEP.value` → `reason=None`** (wrong Prometheus label → dashboards/alerts silently miscount)                | 1   | **TEST-GAP** | `spr__3`                                                                                                                               |
| 23  | `should_process_request` — **`shed_requests += 1` → `= 1`** (test only asserts after a single shed)                                                                                             | 1   | **TEST-GAP** | `spr__4`                                                                                                                               |
| 24  | `should_process_request` — caution-path warn threshold `>` → `>=` (warning-only branch, then `return True`; observable only via logs)                                                           | 1   | LOW-VALUE    | `spr__19`                                                                                                                              |
| 25  | `get_status` — **`config` subdict key renames** (all 4 keys × XX/UPPER variants; `test_get_status` only checks `"config" in status`)                                                            | 8   | **TEST-GAP** | `gs__11, _12, _13`                                                                                                                     |
| 26  | `get_status` — **`consecutive_high_latency` key rename** (consumed by `backend/api/routes/system.py`; test never checks it)                                                                     | 2   | **TEST-GAP** | `gs__5, _6`                                                                                                                            |
| 27  | `get_adaptive_timeout` — **`>` → `>=`** at `rolling_average == target` (boundary never run: tests use avg 0 or 10 vs target 5)                                                                  | 1   | **TEST-GAP** | `gat__10`                                                                                                                              |
| 28  | `get_adaptive_timeout` — **`latency_factor = avg / target` → `avg * target`** (timeout INFLATES under high latency: 60/2=30 becomes 60/50→clamped 5; integration test only asserts `< initial`) | 1   | **TEST-GAP** | `gat__12`                                                                                                                              |

Keys are suffixed from `backend.services.nemotron_latency_optimizer.<mangled>__mutmut_N`;
`rl`=record_latency, `spr`=should_process_request, `gs`=get_status, `rc`=reset_circuit, `gat`=get_adaptive_timeout.

**Totals: TEST-GAP 38 · EQUIVALENT 92 · LOW-VALUE 1 = 131.**

Why 92 are EQUIVALENT rather than gaps: 63 mutants are pure log message/`extra`-dict text (no test in this
repo asserts module log text); 21 are `get_nemotron_optimizer` config-kwarg/redis removals whose mutant
semantics are _bit-identical_ to the original (dataclass defaults equal the literals, `config or default`
fallback, `_redis` unread); 6 are round-arg tweaks on already-3-decimal values; 1 writes a field with zero
readers.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for each: add the test to the existing file → run green against original;
`mutmut apply <key>` (or check out the mutant copy) → same test must go red; restore original.
All drafts follow the file's existing style (fixtures `optimizer`/`optimizer_config`,
`target=5.0, max_acceptable=15.0, threshold=3, min_timeout=5.0, queue_factor=2.0`) and the
repo's established metric idiom `metric.labels(...)._value.get()`
(`test_action_recognition_service.py` L88–92). Add to the top-level imports:

```python
from backend.services.circuit_breaker import CircuitState
from backend.services.nemotron_latency_optimizer import (
    NEMOTRON_CIRCUIT_STATE_GAUGE,
    NEMOTRON_SHED_REQUESTS_TOTAL,
)
```

### Test A — singleton config pins the operating envelope

**Kills:** cluster 3 (9) + cluster 2 (1, as a bonus guard). **Target:** `backend/tests/unit/services/test_nemotron_latency_optimizer.py`, class `TestGlobalOptimizer`.
A single mutant of the documented operating envelope (NEM-4522: circuit opens at 30s avg, max 50 queued,
5-strike threshold) is exactly what the mutation run flagged as drifting silently.

```python
    def test_singleton_config_pins_operating_envelope(self):
        """The global singleton must be built with the documented NEM-4522 defaults.

        get_nemotron_optimizer() spells these values out explicitly; if one silently
        drifts (mutants bumped each by +1) the circuit would open at 31s and stop
        shedding at 51 queued requests with no test noticing.
        """
        optimizer = get_nemotron_optimizer()

        cfg = optimizer.config
        assert cfg.target_latency_seconds == 10.0
        assert cfg.max_acceptable_latency_seconds == 30.0
        assert cfg.rolling_window_size == 20
        assert cfg.semaphore_acquire_timeout == 30.0
        assert cfg.max_queue_depth == 50
        assert cfg.circuit_failure_threshold == 5
        assert cfg.circuit_recovery_timeout == 60.0
        assert cfg.min_adaptive_timeout == 30.0
        assert cfg.adaptive_timeout_queue_factor == 2.0
```

Red on: any `_21`…`_29` +1 bump (e.g. `max_queue_depth=51`), and `config=None` mutants
(they keep defaults equal to the _dataclass_, equal to expectations — those stay EQUIVALENT by design).
Green on original.

### Test B — to_dict exposes p95 under its contract key

**Kills:** clusters 6, 7 (6). **Target:** class `TestLatencyStats`. The API schema
(`backend/api/schemas/system.py`) and generated frontend types both consume `p95_latency_seconds`,
but no test ever reads it — a mutant can return the constant `3` there.

```python
    def test_to_dict_exposes_p95_under_contract_key(self):
        """to_dict must expose the p95 under the exact key the API schema consumes.

        Consumed by backend/api/routes/system.py + generated frontend types; the
        existing test_to_dict never reads it, so mutants renamed the key and
        replaced the value with a constant and survived.
        """
        stats = LatencyStats()
        # 20 samples 1..20 -> idx int(20*0.95)=19 -> p95 = 19.0
        stats.samples.extend(float(i) for i in range(1, 21))
        stats.last_latency = 19.123456

        result = stats.to_dict()

        assert "p95_latency_seconds" in result
        assert result["p95_latency_seconds"] == 19.0
        assert result["rolling_average_seconds"] == round(stats.rolling_average, 3)
        assert result["last_latency_seconds"] == round(19.123456, 3)
```

Red on: key renames (`"XXp95_latency_secondsXX"`, `"P95_LATENCY_SECONDS"`), `round(3)` constant,
`round(x)`→int coercion (19.0 vs 19 — passes `==` but `round(19.123456)` = 19 ≠ 19.123). Green on original.

### Test C — record_latency counters + circuit-state gauge track the state machine

**Kills:** clusters 11, 12, 13, 14, 15, 16 (7). **Target:** class `TestNemotronLatencyOptimizer`.

```python
    def test_record_latency_counters_and_circuit_state_gauge(self):
        """Counters accumulate and the circuit-state gauge (0/1/2) mirrors the breaker.

        The gauge encoding is the ops dashboard's only view of this breaker; mutants
        setting 2-on-trip / 1-on-closed / flipped gauge conditions survived because
        no test reads the gauge, and += mutants survived because no test records a
        second request after a trip.
        """
        base = NEMOTRON_CIRCUIT_STATE_GAUGE._value.get()
        # Trip the circuit: 3 high-latency requests at the threshold (max_acceptable=15)
        for _ in range(optimizer.config.circuit_failure_threshold):
            optimizer.record_latency(20.0)

        assert optimizer.circuit_state == CircuitState.OPEN
        assert optimizer.stats.circuit_trips == 1
        assert optimizer.stats.total_requests == optimizer.config.circuit_failure_threshold
        assert NEMOTRON_CIRCUIT_STATE_GAUGE._value.get() == base + 1  # 1 = OPEN

        # Boundary: exactly max_acceptable does NOT count (strict > on original).
        # The `>` -> `>=` mutant makes this 1 instead of 0.
        optimizer.reset_circuit()
        optimizer.record_latency(optimizer.config.max_acceptable_latency_seconds)
        assert optimizer._consecutive_high_latency == 0

        # Good latency closes the breaker -> gauge back to 0 = CLOSED
        optimizer.record_latency(1.0)
        optimizer.record_latency(1.0)
        assert optimizer.circuit_state == CircuitState.CLOSED
        assert NEMOTRON_CIRCUIT_STATE_GAUGE._value.get() == base + 0  # 0 = CLOSED
        assert optimizer.stats.total_requests == optimizer.config.circuit_failure_threshold + 3
        # A manual reset must not double-count a trip and pins gauge 0
        assert optimizer.stats.circuit_trips == 1
```

Note: `record_failure` opens at exactly `failure_threshold` (circuit_breaker.py L802–819) and
`reset()` → CLOSED; `record_success` twice closes the half-open... — if HALF_OPEN→CLOSED needs
`success_threshold=2` it is satisfied by the two 1.0s records. Red on: `total_requests = 1` (expects 3), `circuit_trips` counting, `was_open=None` (re-trip would
double-count trips — covered by the post-reset `circuit_trips == 1` line only if a second trip occurs;
kept as guard), gauge 2-on-open / 1-on-closed mutants, the `!= CLOSED` gauge condition, and the strict
boundary record (`15.0 > 15.0` is False on original → 0; `>=` mutant → 1).

### Test D — should_process_request sheds at exactly max_queue_depth and labels the metric correctly

**Kills:** clusters 21, 22, 23 (3). **Target:** class `TestNemotronLatencyOptimizer`.

```python
    def test_queue_depth_shed_boundary_and_metric_labels(self):
        """Shed at pending == max_queue_depth (inclusive) and count it under the
        queue_too_deep Prometheus label.

        Mutant `>= -> >` let a request through at exactly the limit; mutant
        reason=None registered the shed under label "None"; mutant `shed_requests = 1`
        stopped the counter climbing on the second shed.
        """
        before = NEMOTRON_SHED_REQUESTS_TOTAL.labels(reason="queue_too_deep")._value.get()

        optimizer._pending_count = optimizer.config.max_queue_depth - 1  # 4 < 5 -> allowed
        assert optimizer.should_process_request() is True

        optimizer._pending_count = optimizer.config.max_queue_depth  # 5 >= 5 -> shed
        assert optimizer.should_process_request() is False
        optimizer._pending_count = optimizer.config.max_queue_depth + 1
        assert optimizer.should_process_request() is False

        assert optimizer.stats.shed_requests == 2  # kills the "= 1" reset mutant
        assert (
            NEMOTRON_SHED_REQUESTS_TOTAL.labels(reason="queue_too_deep")._value.get()
            == before + 2
        )
```

`LoadSheddingReason.QUEUE_TOO_DEEP.value == "queue_too_deep"` (StrEnum auto, verified). Red on `reason=None`
(the "queue_too_deep" child never increments — `None` child is created instead), on `>` (first boundary
call returns True), and on `shed_requests = 1`.

### Test E — get_status reports the full API contract

**Kills:** clusters 25, 26 (10). **Target:** class `TestNemotronLatencyOptimizer` (extends existing `test_get_status` spirit; consume-only keys renamed by the API schema — `backend/api/routes/system.py`).

```python
    def test_get_status_reports_full_api_contract(self):
        """Every key the API surface consumes must be present with correct values.

        The existing test only spot-checks membership of 4 top-level keys, so all 10
        key-rename mutants (config subdict + consecutive_high_latency) survived.
        """
        optimizer.record_latency(8.0)
        optimizer.record_latency(20.0)  # high (> max_acceptable=15)
        optimizer._pending_count = 2

        status = optimizer.get_status()

        assert set(status) == {
            "circuit_state",
            "pending_requests",
            "consecutive_high_latency",
            "latency_stats",
            "config",
        }
        assert status["consecutive_high_latency"] == 1
        assert status["circuit_state"] == optimizer.circuit_state.value
        assert set(status["config"]) == {
            "target_latency_seconds",
            "max_acceptable_latency_seconds",
            "max_queue_depth",
            "semaphore_acquire_timeout",
        }
        assert status["config"]["target_latency_seconds"] == optimizer.config.target_latency_seconds
        assert set(status["latency_stats"]) == {
            "rolling_average_seconds",
            "p95_latency_seconds",
            "last_latency_seconds",
            "sample_count",
            "total_requests",
            "shed_requests",
            "circuit_trips",
        }
```

### Test F — reset_circuit pins the gauge to CLOSED + adaptive timeout exact math

**Kills:** cluster 18 (1) and clusters 27, 28 (2). **Target:** class `TestNemotronLatencyOptimizer`.
(Folded: two small tests, one per behavior.)

```python
    def test_reset_circuit_pins_state_gauge_to_closed(self):
        base = NEMOTRON_CIRCUIT_STATE_GAUGE._value.get()
        for _ in range(3):
            optimizer.record_latency(20.0)
        assert NEMOTRON_CIRCUIT_STATE_GAUGE._value.get() == base + 1
        optimizer.reset_circuit()
        assert NEMOTRON_CIRCUIT_STATE_GAUGE._value.get() == base + 0

    def test_get_adaptive_timeout_high_latency_exact_value(self):
        """Timeout must DIVIDE by the latency factor, not inflate via multiplication."""
        for _ in range(5):
            optimizer.record_latency(10.0)  # avg 10.0, target 5.0 -> factor 2.0

        timeout = optimizer.get_adaptive_timeout(base_timeout=60.0)
        # queue empty: 60 -> 60 / 2.0 = 30 (clamped at min 5.0)
        assert timeout == 30.0

        # exactly at target -> factor branch must NOT engage
        opt2 = NemotronLatencyOptimizer(config=LatencyOptimizerConfig(target_latency_seconds=10.0))
        opt2.record_latency(10.0)
        assert opt2.get_adaptive_timeout(base_timeout=60.0) == 60.0
```

`gat__12` (`/`→`*`): factor = 10*5=50 → 60/50=1.2 → clamped to 5.0 ≠ 30.0 → red.
`gat__10` (`>`→`>=`): second block returns 60/1.0=60 on mutant → 60.0 == 60.0 — hmm: on mutant the
factor branch engages, `60 / (10/10=1.0)` = 60.0 → SAME. This mutant instead flips the *equal-average\*
path only when factor≠1; it is only killable via a record whose avg equals target while timeout math
differs — i.e. avg==target always gives factor 1.0, so `>` vs `>=` at equality is genuinely
**equivalent on this code** (division by 1.0 is the identity). Demote cluster 27 to EQUIVALENT —
see corrected table below.

## Corrections after red/green reasoning

- **Cluster 27 (`get_adaptive_timeout` `>` → `>=`)**: when `rolling_average == target`, `latency_factor`
  is exactly 1.0 and the guarded branch is a no-op either way → reclassified **EQUIVALENT** (28 → stays
  TEST-GAP only for the `*` mutant). Final totals: TEST-GAP 37 · EQUIVALENT 93 · LOW-VALUE 1.
- Test C's boundary assertion stands as written (`== 0` on original, red for `rl__9`); flagged inline.

## Residual notes

- Cluster 24 (`spr__19`, warning-branch `>`→`>=`): observable only through a log line; not drafted.
- The 92 EQUIVALENT log/config mutants are the cost of spelling defaults twice
  (`get_nemotron_optimizer` re-states dataclass defaults). One cheap production fix (out of scope here):
  drop the redundant kwargs so mutmut stops generating them.
- 110 mutants of this module were `null` (unchecked) at triage time; after tests A–F land, rerun should
  push the module score materially (36 of the 37 TEST-GAP survivors killed — only cluster 24, the
  warning-branch `>=`, is deliberately not drafted).
