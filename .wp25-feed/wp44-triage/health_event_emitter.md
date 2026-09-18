# WP4.4 Triage Dossier — backend/services/health_event_emitter.py

**Survivors:** 86 of 223 checked mutants (exit_code 0). All 86 diffs extracted by
block-diffing each `*__mutmut_N` variant against its `*__mutmut_orig` in
`mutants/backend/services/health_event_emitter.py` (raw dump: `/tmp/wp25/wp44-triage/survivor_diffs.txt`).
Source under test: `backend/services/health_event_emitter.py` (539 lines).

**Covering test files** (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):

- `backend/tests/unit/services/test_health_event_emitter.py` — primary (fixtures: `health_emitter`,
  `mock_websocket_emitter`, autouse `caplog.set_level(DEBUG)` + autouse `reset_health_event_emitter()`)
- `backend/tests/unit/test_health_event_emitter.py` — parallel older suite (fixtures `health_emitter`, `mock_ws_emitter`)
- `backend/tests/unit/routes/test_system_routes.py` — indirect only (5 tests touch `get_health_event_emitter` via routes, no payload asserts)

**Headline:** 18/86 (21%) survivors are pure logger message-text tweaks and 6 more dead defensive tweaks
(24 EQUIVALENT together), 29 (34%) are logger-`extra` metadata mutations (LOW-VALUE). The interesting
33 (38%) are TEST-GAPs concentrated in these payload/state-fidelity holes: **no test asserts payload `error`/`message`/`details`/`recoverable` on the
module-level delegation path, no test asserts `payload["components"]` content, no test asserts per-component
`details` through `update_all_components`, and the DI "registered-but-not-yet-instantiated" branch is entirely
unexercised.**

## Cluster table

| # | Cluster | N | Class | Example keys (≤3) |
|---|---------|---|-------|-------------------|
| C1 | module-level `emit_system_error` delegation kwarg sabotage (`error_code=None`, `message=None`, `details=None`/dropped, `recoverable=None`/dropped) → payload loses real data | 6 | TEST-GAP | `x_emit_system_error__mutmut_3`, `_mutmut_11`, `_mutmut_12` |
| C2 | `recoverable: bool = True` default flipped → `False` on both `emit_system_error` (class + module) | 2 | TEST-GAP | `x_emit_system_error__mutmut_1`, `xǁ…ǁemit_system_error__mutmut_1` |
| C3 | `_emit_health_changed`: `components = None` → `payload["components"]` becomes None | 1 | TEST-GAP | `xǁ…ǁ_emit_health_changed__mutmut_6` |
| C4a | `check_and_emit` records naive/None `last_changed` (`now=None`, `datetime.now(None)` — naive wall clock, explicit `last_changed=None`) | 3 | TEST-GAP | `xǁ…ǁcheck_and_emit__mutmut_15`, `_16`, `_19` |
| C4b | `check_and_emit` drops caller details on the **first** transition (`details=None`, kwarg removed → dataclass `{}`, `details and {}`) | 3 | TEST-GAP | `xǁ…ǁcheck_and_emit__mutmut_20`, `_23`, `_24` |
| C5 | severity normalization invisible: `ErrorSeverity(severity.upper())` / `(None)` collapse any string severity to MEDIUM, and module-level delegation drops `severity=` — payload carries no severity, only the log `extra` does | 3 | TEST-GAP | `x_emit_system_error__mutmut_10`, `xǁ…ǁemit_system_error__mutmut_9`, `_10` |
| C6 | `update_all_components` never forwards per-component details (`=None`, `.get(None)`, `check_and_emit(comp, status, None)`, 3rd arg dropped) | 4 | TEST-GAP | `xǁ…ǁupdate_all_components__mutmut_4`, `_5`, `_8` |
| C7 | DI branch unexercised: registered service with `instance is None` must resolve via `container.get("health_event_emitter")` — mutants return None / skip branch / call `get` with wrong key; `and`→`or` returns None | 8 | TEST-GAP | `x_get_health_event_emitter__mutmut_6`, `_9`, `_12` |
| C8 | `check_and_emit` `if previous_state and details:` → `or` → **AttributeError crash** (`None.details`) when an invalid-status string is first seen with details | 1 | TEST-GAP | `xǁ…ǁcheck_and_emit__mutmut_12` |
| C9 | `emit_system_error` payload timestamp built with `datetime.now(None)` → naive ISO string (no offset) | 1 | TEST-GAP | `xǁ…ǁemit_system_error__mutmut_19` |
| C10 | `_emit_health_changed` `_30` deletes the debug message line → `logger.debug(extra=…)` raises TypeError inside the try → spurious **ERROR** log on every *successful* emit | 1 | TEST-GAP | `xǁ…ǁ_emit_health_changed__mutmut_30` |
| C11 | logger `extra=` dict mutations (None/removed/key-case): structured log metadata only; no test or consumer reads record extras — `_emit_health_changed` 10 (`_28`,`_29`,`_31`–`_35`,`_37`,`_39`,`_40`), `check_and_emit` 10 (`_38`,`_40`–`_48`), `emit_system_error` 9 (`_28`,`_29`,`_31`–`_37`) | 29 | LOW-VALUE | `xǁ…ǁcheck_and_emit__mutmut_38`, `_41`, `xǁ…ǁ_emit_health_changed__mutmut_29` |
| C12 | pure log message text (None / `XX…XX` / case variants): `__init__` 4, `reset` 4, `set_emitter` 4, `get_health_event_emitter` 4, `_emit_health_changed _3`, class `emit_system_error _4` (debug-text only); existing substring asserts (`"No emitter configured"` etc.) still match the XX variants | 18 | EQUIVALENT | `xǁ…ǁ__init____mutmut_5`, `xǁ…ǁreset__mutmut_2`, `x_get_health_event_emitter__mutmut_20` |
| C13 | dead defensive tweaks: `_calculate_overall_status` critical-block removal (`state=None`, `.get(None)`) is redundant — UNHEALTHY already has best priority so the worst-loop returns UNHEALTHY anyway (4); `.get(..., default)` default never used (all enum values are keys); `check_and_emit` `_22` (`last_changed=now` removed → default_factory gives the same tz-aware now) (1) | 5 | EQUIVALENT | `xǁ…ǁ_calculate_overall_status__mutmut_2`, `_10`, `xǁ…ǁcheck_and_emit__mutmut_22` |
| — | `reset_health_event_emitter__mutmut_6` (`and`→`or`): raises `AttributeError` on `None.reset()`, swallowed by the function's own `except ImportError, AttributeError` → behaviorally identical to the false path (folded into C13) | 1 | EQUIVALENT | `x_reset_health_event_emitter__mutmut_6` |

Counts: TEST-GAP 33, LOW-VALUE 29, EQUIVALENT 24 (C12 18 + C13 5 + reset-row 1) → **86** total.

## Why "test exists but too weak" for each TEST-GAP

- **C1/C2/C9**: `test_emit_system_error_module_function` (services file :530) asserts only
  `result is True` + `emit.assert_awaited_once()`; the payload-level asserts in
  `test_system_error_payload_structure` (:643) all pass **explicit** kwargs to the *instance* method,
  never exercising the module-level delegation or defaults.
- **C3**: `test_health_changed_payload_structure` (:615) asserts `"components" in payload` — key
  presence only, so `components=None` slips through.
- **C4a/C4b**: `test_check_and_emit_updates_details_when_status_unchanged` (:113) only checks the
  unchanged-path reassignment (`previous_state.details = details`), never the constructed-on-change state;
  nothing reads `state.last_changed` after `check_and_emit`.
- **C5**: `test_emit_system_error_severity_normalization` (:553) and
  `test_emit_system_error_invalid_severity_defaults_to_medium` (:570) assert `result is True` only;
  severity reaches no payload field, only `extra` on the success log.
- **C6**: `test_update_all_components` (:178) passes `details` but asserts only the changed-name list
  and emit count.
- **C7**: `test_get_health_event_emitter_from_container` (:712) sets `instance = <emitter>` (instantiated)
  — the `instance is None` + `container.get(...)` branch has zero coverage, so all 8 branch mutants live.
- **C8**: `test_invalid_status_string_defaults_to_unknown` (:418) calls without `details`, missing the
  only input that reaches the `or`-flipped guard with `previous_state is None`.
- **C10**: no test asserts the *absence* of ERROR records on the success path.

## Drafted kill-tests (UNVERIFIED — not yet run red/green)

All target `backend/tests/unit/services/test_health_event_emitter.py` (style-matched: `@pytest.mark.asyncio`,
fixtures `health_emitter` / `mock_websocket_emitter` / `caplog`).

```python
// UNVERIFIED - not yet run red/green
# TDD procedure: uv run pytest backend/tests/unit/services/test_health_event_emitter.py -k <name> -q
# must FAIL against each cluster mutant (uv run mutmut show <key>) and PASS on the original source.


# --- D1: kills C7 (get_health_event_emitter _6/_9/_10/_11/_12/_13/_14/_15) ---
@pytest.mark.asyncio
async def test_get_health_event_emitter_uses_container_for_registered_uninstantiated_service() -> None:
    """Registered-but-not-instantiated DI service must resolve via container.get(), not the legacy singleton."""
    with patch("backend.core.container.get_container", autospec=True) as mock_container:
        # Arrange - service registered in the container but never instantiated
        container_emitter = HealthEventEmitter()
        mock_reg = MagicMock()
        mock_reg.instance = None
        mock_container.return_value._registrations = {"health_event_emitter": mock_reg}
        mock_container.return_value.get = MagicMock(return_value=container_emitter)

        # Act
        result = get_health_event_emitter()

        # Assert - branch mutants skip the branch (legacy singleton), return None, or call get(wrong_key)
        assert result is container_emitter
        mock_container.return_value.get.assert_called_once_with("health_event_emitter")


# --- D2: kills C1 (_3/_4/_6/_7/_11/_12) + C5 (module _10, class _9/_10) ---
@pytest.mark.asyncio
async def test_emit_system_error_module_function_forwards_every_argument(
    mock_websocket_emitter: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Module-level convenience function must forward every argument into the payload and the log."""
    # Arrange
    emitter = get_health_event_emitter()
    emitter.set_emitter(mock_websocket_emitter)

    # Act - string severity exercises normalization through the delegation path
    result = await emit_system_error(
        error_code="CAMERA_OFFLINE",
        message="cam-3 unreachable",
        severity="HIGH",
        details={"rtsp_url": "rtsp://cam-3"},
        recoverable=False,
    )

    # Assert
    assert result is True
    payload = mock_websocket_emitter.emit.call_args[0][1]
    assert payload["error"] == "CAMERA_OFFLINE"          # kills _3 (error_code=None)
    assert payload["message"] == "cam-3 unreachable"     # kills _4 (message=None)
    assert payload["details"] == {"rtsp_url": "rtsp://cam-3"}  # kills _6, _11
    assert payload["recoverable"] is False               # kills _7, _12

    success = [r for r in caplog.records if getattr(r, "error_code", None) == "CAMERA_OFFLINE"]
    assert success and getattr(success[0], "severity", None) == "high"  # kills severity sabotage (C5)


# --- D3: kills C6 (update_all_components _4/_5/_8/_11) ---
@pytest.mark.asyncio
async def test_update_all_components_forwards_details_per_component(
    health_emitter: HealthEventEmitter,
) -> None:
    """Batch update must route each component's details into its stored state."""
    # Arrange
    statuses = {
        "database": HealthStatus.HEALTHY,
        "redis": HealthStatus.DEGRADED,
        "gpu": HealthStatus.HEALTHY,
    }
    details = {"database": {"latency_ms": 4}, "redis": {"memory_used_mb": 812}}

    # Act
    changed = await health_emitter.update_all_components(statuses, details)

    # Assert
    assert set(changed) == {"database", "redis", "gpu"}
    assert health_emitter._component_states["database"].details == {"latency_ms": 4}
    assert health_emitter._component_states["redis"].details == {"memory_used_mb": 812}
    assert health_emitter._component_states["gpu"].details == {}


# --- D4: kills C4a (check_and_emit _15/_16/_19) + C4b (_20/_23/_24) ---
@pytest.mark.asyncio
async def test_check_and_emit_records_details_and_tz_aware_last_changed(
    health_emitter: HealthEventEmitter,
) -> None:
    """First status transition must persist caller details and a timezone-aware last_changed."""
    # Arrange
    before = datetime.now(UTC)

    # Act
    await health_emitter.check_and_emit("gpu", HealthStatus.DEGRADED, {"memory_free": 500})

    # Assert
    state = health_emitter._component_states["gpu"]
    assert state.details == {"memory_free": 500}      # kills _20, _23, _24
    assert state.last_changed is not None             # kills _15, _19
    assert state.last_changed.tzinfo is not None      # kills _16 (naive datetime.now(None))
    assert before <= state.last_changed <= datetime.now(UTC)


# --- D5: kills C2 (class+module _1) + C9 (emit_system_error _19) ---
@pytest.mark.asyncio
async def test_emit_system_error_defaults_recoverable_true_and_aware_timestamp(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Default call contract: recoverable=True and a UTC-offset-bearing timestamp."""
    # Act - rely on defaults for severity/details/recoverable
    await health_emitter.emit_system_error(error_code="DISK_FULL", message="/export at 95% used")

    # Assert
    payload = mock_websocket_emitter.emit.call_args[0][1]
    assert payload["recoverable"] is True            # kills class emit_system_error _1
    assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None  # kills _19

    # Module-level convenience function on its defaults (kills module-level emit_system_error _1).
    # Point the singleton at the mock first - get_health_event_emitter() may resolve the DI
    # container's own instance, so bind explicitly rather than assume identity.
    get_health_event_emitter().set_emitter(mock_websocket_emitter)
    await emit_system_error(error_code="SECOND", message="default check")
    assert mock_websocket_emitter.emit.call_args[0][1]["recoverable"] is True


# --- D6: kills C3 (_emit_health_changed _6) + C10 (_30) ---
@pytest.mark.asyncio
async def test_health_changed_payload_includes_component_map_and_no_error_logs(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """payload['components'] carries the live status map; the success path logs no ERROR."""
    # Act
    await health_emitter.check_and_emit("database", HealthStatus.DEGRADED)

    # Assert
    payload = mock_websocket_emitter.emit.call_args[0][1]
    assert payload["components"] == {"database": "degraded"}   # kills _6 (components=None)
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]  # kills _30 (TypeError->swallowed ERROR)
```

**Not drafted (folded into C8, kill-gist for the WP4.4 lane):** C8 —
`assert await health_emitter.check_and_emit("gpu", "bogus_status", {"x": 1}) is False` —
original records UNKNOWN and returns False; the `or`-flip raises `AttributeError` on `None.details`
because `previous_state` is None when an unknown status string is seen for the first time with details.

## Notes on the equivalence rulings

- **C12 message-text:** mutants that case-flip or wrap in `XX…XX` survive *because* the only log asserts
  are substring `in` checks whose needles stay intact (`"No emitter configured"` ⊂ `"XXNo emitter configured…XX"`).
  Per WP4.4 taxonomy, pure message text = EQUIVALENT; do not write kill-tests.
- **C13 redundancy proof (`_calculate_overall_status` critical block):** `UNHEALTHY` has priority 0 = the
  minimum of `_STATUS_PRIORITY`, so the generic "worst status across all components" loop already returns
  UNHEALTHY whenever a critical component is unhealthy. The explicit critical early-return is dead logic under
  the current table; `state=None` / `.get(None)` mutants are undetectable by any assertion that respects the
  public contract. If a future status is ever added *worse* than UNHEALTHY, this block becomes live again —
  flag for the WP4.4 register, not for a test today.
