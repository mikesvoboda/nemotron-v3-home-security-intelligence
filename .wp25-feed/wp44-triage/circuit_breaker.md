# WP4.4 Triage Dossier — backend/services/circuit_breaker.py

**Verdict source:** `mutants/backend/services/circuit_breaker.py.meta` (exit_code_by_key; 0 = survived).
**Survivors:** 118 of 500 keys (169 killed, 213 unchecked at read time).
**Diff method:** manual block diff of clobbered variant defs (`xǁ…__mutmut_N`) against `…__mutmut_orig` blocks in the mutant copy (mutmut show avoided; cache under concurrent write).

## Covering test files (from mutmut-stats tests_by_mangled_function_name)

| File | Role |
|---|---|
| `backend/tests/unit/services/test_circuit_breaker.py` | Primary; fixtures `default_config`/`breaker` (L47-61); state transitions L171-306; reset L463-517; get_metrics L524-619; ctx-manager L1110-1180; error L1187-1220; get_status L1239-1252 |
| `backend/tests/unit/core/test_circuit_breaker.py` | Re-exports same impl; **mock-gauge Prometheus pattern** L438-525; log tests (message string only) L603-657 |
| `backend/tests/unit/api/routes/test_debug.py` | `/api/debug/circuit-breakers` payload check L305-341 (asserts only `state`, `failure_count`) |
| `backend/tests/unit/core/test_circuit_breaker_integration.py` | get_state_info consumer (sync core interface) |

Key negative findings (greps): no test asserts `get_metrics().success_count`/`.last_state_change` from the *breaker* (only the bare dataclass L1343-1400); no `caplog`/`record.extra` assertions; no HSI-gauge or otel-call assertions in circuit tests; no `recovery_timeout` attr assertion on `CircuitBreakerError`.

## Cluster table (counts sum = 118)

| # | Pattern (function / concern) | Count | Keys (≤3 examples) | Class | Note |
|---|---|---|---|---|---|
| 1 | `__aenter__` half-open trial-call accounting: `!=` flip, `= 1`, `-= 1`, `+= 2` on `_half_open_calls += 1` | 4 | …`__aenter____mutmut_12`,`_13`,`_14` | TEST-GAP | No test enters half-open via ctx-mgr more than once / checks `half_open_calls` (get_state_info key never asserted); limit unenforced |
| 2 | `__aenter__` rejection counter `+= 1` → `= 1` / `-= 1` / `+= 2` on `_rejected_calls` | 3 | …`__aenter____mutmut_5`,`_6`,`_7` | TEST-GAP | `test_context_manager_rejects_when_open` (L1143) never reads `rejected_calls`; only `call()` path counter asserted (L381) |
| 3 | `__aenter__` raises `CircuitBreakerError(name, state)` with args → None / dropped / swapped | 4 | …`__aenter____mutmut_8`,`_9`,`_10` | TEST-GAP | Catching test (L1152) never asserts `err.service_name` / `err.state` |
| 4 | `get_metrics()` field wiring & monotonic→datetime arithmetic: `+`/`-` timedelta sign, `now(None)`, `success_count=None`/dropped, `last_state_change=None`/dropped | 7 | …`get_metrics____mutmut_4`,`_8`,`_21` | TEST-GAP | TestGetMetrics (L524-619) covers name/state/failure/total/rejected/last_failure_time-not-None but never `success_count`, `last_state_change`, or plausibility of `last_failure_time` |
| 5 | `reset()` guard flip `prev_state != CLOSED` → `==` on change-counter/otel | 1 | …`reset____mutmut_19` | TEST-GAP | TestReset never asserts state-change counter emission (none from CLOSED, one from OPEN/HALF_OPEN) |
| 6 | `get_state_info()` `if (x) and False` → `last_state_change` always None | 1 | …`get_state_info____mutmut_19` | TEST-GAP | Only consumer test (debug route / core integration) never asserts this key is populated |
| 7 | `get_status()` payload dict-key renames XX/UPPER (`success_count`,`rejected_calls`,`last_failure_time`,`opened_at`) | 8 | …`get_status____mutmut_7`,`_11`,`_13` | TEST-GAP | `test_get_status` (L1239) asserts only 4 keys + config; payload feeds `/api/debug/circuit-breakers` — rename breaks API contract silently |
| 8 | `get_state_info()` payload dict-key renames (`half_open_max_calls`,`half_open_calls`,`last_state_change`) | 6 | …`get_state_info____mutmut_11`,`_13`,`_17` | TEST-GAP | Same consumer blind spot (debug route asserts 2 of 9 keys) |
| 9 | `CircuitBreakerError.__init__` attr loss: `recovery_timeout=None`; `CircuitState(None)` → always-OPEN fallback | 2 | …`CircuitBreakerErrorǁ__init____mutmut_3`,`_9` | TEST-GAP | No test asserts `err.recovery_timeout`; `err.state` asserted only for "open" (L1198), never a non-open string |
| 10 | `datetime.now(UTC)` → `datetime.now(None)` tz-naive stamp on `_last_state_change` (transition_to_closed/half_open, reset) | 3 | …`_transition_to_closed____mutmut_10`, …half_open`_7`, …reset`_12` | TEST-GAP | Tests assert `is not None` / `!= before` only; naive stamp serializes tz-less via `isoformat()` into API payloads |
| 11 | Prometheus **gauge value** wrong on recovery/reset: closed `set(0)→set(1)`, half_open `set(2)→set(3)`, reset legacy/HSI `set(0)→set(1)` | 4 | …`_transition_to_closed____mutmut_16`, …half_open`_13`, …reset`_15` | TEST-GAP | Core mock-gauge pattern asserts `.set()` on the OPEN path only (core L438-496); recovery/reset gauge values never checked |
| 12 | Prometheus **label value → None** on legacy/HSI gauge & state-changes counter in `_transition_to_closed`(5), `_transition_to_half_open`(5), `reset`(5) | 15 | …`_transition_to_closed____mutmut_12`,`_17`; …reset`_14` | TEST-GAP | Mislabels series (`service="None"`, `from_state="None"`); existing `labels.assert_called_with` pattern covers only CLOSED→OPEN transition labels |
| 13 | Prometheus label **case/wrap text** (`"half_open"`→`"HALF_OPEN"`/`"XXhalf_openXX"`) in state-changes labels (closed 4, half 4, reset 2) | 10 | …`_transition_to_closed____mutmut_23`,`_24`; …reset`_26` | LOW-VALUE | Convention-only label text; asserting log/metric text case is the classic weak-test trap; dashboard breakage is integration territory |
| 14 | otel `record_state_change` args → None (closed 3, half 3, reset 3) | 9 | …`_transition_to_closed____mutmut_27`,`_28`,`_29` | LOW-VALUE | Telemetry attr plumbing; no test in repo asserts otel_record_* call args for breakers (test_otel_metrics.py tests the otel module itself) |
| 15 | otel args case/wrap text (closed 4, half 4, reset 2) | 10 | …`_transition_to_half_open____mutmut_30`..`_33` | LOW-VALUE | Same as 14 |
| 16 | structured-log `extra={…}` payload dropped / `extra=None` on info logs (closed 39,41; half 36,38) | 4 | …`_transition_to_closed____mutmut_39`,`_41` | LOW-VALUE | Message string intact (what TestLogging L603+ checks); structured-context loss nobody consumes in tests; no caplog use anywhere in these files |
| 17 | log `extra` dict key/value case/wrap text (closed 10, half 12) | 22 | …`_transition_to_half_open____mutmut_39`,`_49`; …closed`_42` | LOW-VALUE | Pure log-field text cosmetics |
| 18 | Dead/no-op-equivalent: `CircuitBreakerRegistry.__init__` `_lock=None` (never used); message-only text loss `logger.info(None)`/`logger.warning(None)` (reset_all_1, reset_36, force_open_1), `CircuitOpenError` `super().__init__(None)` msg | 5 | …`CircuitBreakerRegistryǁ__init____mutmut_2`, …`reset____mutmut_36`, …`CircuitOpenErrorǁ__init____mutmut_1` | EQUIVALENT | `_lock` is assigned and never read in registry methods; message text asserted nowhere; attributes intact |

**Totals:** TEST-GAP 58, LOW-VALUE 55, EQUIVALENT 5 = 118.

## Drafted tests (highest-value clusters)

All marked **UNVERIFIED — not yet run red/green**. TDD procedure for each: run new test against the mutant build (expect FAIL on the mutated line), then against `backend/services/circuit_breaker.py` original (expect PASS).

### T1 — TestContextManagerHalfOpenAccounting (kills clusters 1, 2, 3; extends to reset counter) → `backend/tests/unit/services/test_circuit_breaker.py`

```python
class TestContextManagerHalfOpenAccounting:
    """UNVERIFIED - not yet run red/green. Kills __aenter__ half-open
    accounting (_half_open_calls += 1 mutants + != flip), rejected_calls
    counter mutants, and CircuitBreakerError arg mutants in __aenter__."""

    @pytest.mark.asyncio
    async def test_half_open_trial_limit_and_rejection_error_context(self) -> None:
        # success_threshold high so the circuit stays HALF_OPEN across entries.
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.05,
            half_open_max_calls=2,
            success_threshold=99,
        )
        breaker = CircuitBreaker(name="ctx_accounting", config=config)

        async def failing_op() -> str:
            raise ConnectionError("boom")

        with pytest.raises(ConnectionError):
            async with breaker:
                await failing_op()
        assert breaker.state == CircuitState.OPEN

        await asyncio.sleep(0.1)  # past recovery timeout

        # Trial 1 and 2 allowed; each must consume one half_open_calls slot.
        async with breaker:
            pass
        assert breaker._half_open_calls == 1
        async with breaker:
            pass
        assert breaker._half_open_calls == 2
        assert breaker.state == CircuitState.HALF_OPEN

        # Trial 3 must be rejected with full error context.
        with pytest.raises(CircuitBreakerError) as exc_info:
            async with breaker:
                pass  # pragma: no cover
        err = exc_info.value
        assert err.service_name == "ctx_accounting"
        assert err.state == CircuitState.HALF_OPEN
        assert breaker._half_open_calls == 2
        assert breaker.get_status()["rejected_calls"] == 1

        # Second rejection accumulates (kills rejected_calls = 1 mutant).
        with pytest.raises(CircuitBreakerError):
            async with breaker:
                pass  # pragma: no cover
        assert breaker.get_status()["rejected_calls"] == 2
```

Mutant behaviour it kills: `_12` (`!=` → never increments, trial 3 enters, no raise); `_13` (`=1` → `_half_open_calls == 1` after trial 2 assertion fails); `_14` (`-=1` → limit never reached); `_15` (`+=2` → trial 2 rejected → second `async with` raises inside try → `pytest.raises` unmet… actually first failure is `assert breaker._half_open_calls == 2` seeing 2 after one entry + rejection path — either way red); `_5/_6/_7` (rejected_calls values); `_8-_11` (service_name/state attrs).

### T2 — TestGetMetricsCompleteness (kills cluster 4, with tz leg of cluster 10) → `backend/tests/unit/services/test_circuit_breaker.py`

```python
class TestGetMetricsCompleteness:
    """UNVERIFIED - not yet run red/green. Kills get_metrics() success_count /
    last_state_change kwarg mutants (+drops), timedelta sign mutants,
    and now(None) in get_metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics_wires_success_count_state_and_timestamps(
        self, breaker: CircuitBreaker
    ) -> None:
        async def failing_op() -> str:
            raise ConnectionError("Failed")

        async def success_op() -> str:
            return "ok"

        assert breaker.get_metrics().last_state_change is None

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        metrics = breaker.get_metrics()
        now = datetime.now(UTC)
        assert metrics.last_failure_time is not None
        # Plausibility: failure just happened (kills +timedelta and sign-flip).
        delta = now - metrics.last_failure_time
        assert timedelta(seconds=-2) < delta < timedelta(seconds=5)
        assert metrics.last_failure_time.tzinfo == UTC
        assert metrics.last_state_change is None  # no transition yet

        # Drive OPEN -> HALF_OPEN -> CLOSED (transition stamps last_state_change).
        breaker._state = CircuitState.HALF_OPEN
        breaker._success_count = 2
        breaker._opened_at = time.monotonic()
        await breaker._record_success()  # success_threshold=2 -> CLOSED

        metrics = breaker.get_metrics()
        assert metrics.state == CircuitState.CLOSED
        assert metrics.success_count == 0  # transition reset (kills kwarg drop)

        breaker._success_count = 3
        assert breaker.get_metrics().success_count == 3  # kills =None / dropped

        metrics = breaker.get_metrics()
        assert metrics.last_state_change is not None
        assert metrics.last_state_change.tzinfo == UTC  # kills now(None)
```

### T3 — ResetInstrumentation (kills clusters 5, 11, and reset half of cluster 12) → `backend/tests/unit/core/test_circuit_breaker.py` (mirrors TestPrometheusMetrics pattern, L438)

```python
class TestResetInstrumentation:
    """UNVERIFIED - not yet run red/green. Kills reset() gauge-value mutants
    (set(0)->set(1)), the prev_state guard flip, and reset() service/from/to
    label-None mutants."""

    def test_reset_emits_closed_gauges_and_change_event_from_open(self) -> None:
        with (
            patch("backend.services.circuit_breaker.CIRCUIT_BREAKER_STATE", autospec=True) as g1,
            patch("backend.services.circuit_breaker.HSI_CIRCUIT_BREAKER_STATE", autospec=True) as g2,
            patch("backend.services.circuit_breaker.CIRCUIT_BREAKER_STATE_CHANGES_TOTAL", autospec=True) as g3,
        ):
            cb = CircuitBreaker(name="reset_metrics", failure_threshold=2)
            l1, l2, l3 = MagicMock(), MagicMock(), MagicMock()
            g1.labels.return_value = l1
            g2.labels.return_value = l2
            g3.labels.return_value = l3

            cb._state = CircuitState.OPEN
            cb.reset()

            g1.labels.assert_called_with(service="reset_metrics")
            l1.set.assert_called_with(0)
            g2.labels.assert_called_with(service="reset_metrics")
            l2.set.assert_called_with(0)
            g3.labels.assert_called_with(
                service="reset_metrics", from_state="open", to_state="closed"
            )
            l3.inc.assert_called_once()

    def test_reset_from_closed_does_not_emit_change_event(self) -> None:
        with patch(
            "backend.services.circuit_breaker.CIRCUIT_BREAKER_STATE_CHANGES_TOTAL",
            autospec=True,
        ) as g3:
            cb = CircuitBreaker(name="reset_closed")
            cb.reset()
            g3.labels.assert_not_called()
```

(The two `_transition_to_*` label-None halves of cluster 12 die by the same pattern on the recovery path — extend with an OPEN→HALF_OPEN→CLOSED sequence under the same patches; same for the gauge-`set` values of cluster 11 and stamp tz of cluster 10.)

### T4 — TestStatusPayloadContract (kills clusters 7, 8) → `backend/tests/unit/services/test_circuit_breaker.py`

```python
class TestStatusPayloadContract:
    """UNVERIFIED - not yet run red/green. Kills every get_status()/
    get_state_info() dict-key rename mutant by pinning the wire contract
    consumed by GET /api/debug/circuit-breakers."""

    def test_get_status_and_state_info_key_contract(self, breaker: CircuitBreaker) -> None:
        status = breaker.get_status()
        assert set(status) == {
            "name", "state", "failure_count", "success_count", "total_calls",
            "rejected_calls", "last_failure_time", "opened_at", "config",
        }
        assert set(status["config"]) == {
            "failure_threshold", "recovery_timeout", "half_open_max_calls",
            "success_threshold",
        }

        info = breaker.get_state_info()
        assert set(info) == {
            "name", "state", "failure_count", "failure_threshold",
            "recovery_timeout", "half_open_max_calls", "half_open_calls",
            "opened_at", "last_state_change",
        }
        assert info["half_open_max_calls"] == 2
        assert info["half_open_calls"] == 0
```

### T5 — ErrorAttrsAndStateChangeStamps (kills clusters 6, 9, 10) → `backend/tests/unit/services/test_circuit_breaker.py`

```python
class TestErrorAttrsAndStateChangeStamps:
    """UNVERIFIED - not yet run red/green. Kills CircuitBreakerError attr
    mutants, get_state_info and-False mutant, and the datetime.now(None)
    tz-naive stamp mutants."""

    def test_error_keeps_recovery_timeout_and_string_state(self) -> None:
        err = CircuitBreakerError("svc", "half_open", recovery_timeout=12.5)
        assert err.recovery_timeout == 12.5
        assert err.state == CircuitState.HALF_OPEN  # not forced to OPEN

    def test_last_state_change_is_tz_aware_and_serialized(self, breaker: CircuitBreaker) -> None:
        assert breaker.get_state_info()["last_state_change"] is None

        breaker._transition_to_half_open()
        stamp = breaker.get_state_info()["last_state_change"]
        assert stamp is not None  # kills `and False` mutant
        assert datetime.fromisoformat(stamp).tzinfo is not None  # kills now(None)

        breaker._transition_to_closed()
        stamp = breaker.get_state_info()["last_state_change"]
        assert datetime.fromisoformat(stamp).tzinfo is not None

        breaker.reset()
        stamp = breaker.get_state_info()["last_state_change"]
        assert datetime.fromisoformat(stamp).tzinfo is not None
```

## Clusters intentionally NOT drafted (accepted as LOW-VALUE / EQUIVALENT)

13 (10), 14 (9), 15 (10), 16 (4), 17 (22), 18 (5) = 60 survivors → recommend marking these EQUIVALENT/LOW-VALUE suppression candidates in the WP4.4 baseline rather than writing text-equality tests (asserting log/label casing produces brittle tests with no failure-catching power).
