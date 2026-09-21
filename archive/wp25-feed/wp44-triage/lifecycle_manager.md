# WP4.4 Triage Dossier — `backend/services/lifecycle_manager.py`

**Wave**: read-only triage wave (parallel-triage protocol). Every verdict below is
**UNVERIFIED** — no pytest, no mutmut run, no file in the repo was touched. Only this file was written.

## Census

| | |
|---|---|
| Mutant keys in meta | 146 |
| Killed (exit_code != 0) | 117 |
| **Survived (exit_code == 0)** | **29** |
| Unchecked (null) | 0 |
| Cluster count sum | 29 ✓ |

Diffs obtained via `uv run mutmut show <key>` (all 29 succeeded; no manual-diff fallback needed).

## Mutation vocabulary in this file

mutmut's operator set here produced three shapes:

1. **`None` substitution** (22 of 29):
   - f-string **log message** → `None` (14): pure text loss.
   - registry **positional** argument → `None` (7, in `update_status`/`persist_state`): the call
     still executes, but `self._services.get(None)` misses and the write is silently dropped.
   - `service.last_failure_at` → `None` (1): the timestamp invariant.
2. **Argument removal** (5 of 29): the keyword arg `max_backoff=` removed on
   `calculate_backoff(...)` (drops the cap, 1) and one positional arg removed on the
   `update_status(...)` call (raises `TypeError` at the call site, 4).
3. **Boundary / comparison flips** (2 of 29): `<= 0` → `<= 1`, `==` → `!=`.

## Why argument-removal mutants "survive" instead of erroring (batch asymmetry)

Nine survivors are argument-removal mutants (`update_status(ContainerServiceStatus.STARTING)` —
one arg; `update_status(service.name, )` — one arg; `persist_state()` — zero args). These raise
`TypeError: missing 1 required positional argument`. Under **mutmut's batch runner** the raise is
swallowed by the enclosing `try/except Exception` in the same method (or, for `handle_unhealthy`,
propagates out of the awaited call and mutmut's batch harness does not charge the failure to any
test in the batch). They are therefore *not* EQUIVALENT — under a strict per-test runner they would
kill on their own. The existing tests *would* kill them individually (e.g.
`test_start_service_success` asserts `result is True`, and a `TypeError` path returns `False`).
The drafted tests below also assert `result is True`, so each keeps a strict-census kill.
**No test can be written that makes this cluster die more honestly — it is a runner artifact, so it
is classified TEST-GAP (test-existence, not test-strength) and needs no new assertion of its own.**
This mirrors the wave-66 batch-test asymmetry ruling.

## Cluster table

| # | Cluster | N | Keys (≤3) | Class | Covering test | What is missing |
|---|---|---|---|---|---|---|
| C1 | `calculate_backoff` method: keyword arg `max_backoff=service.restart_backoff_max` removed → cap silently defaults to **300.0** | 1 | `…xǁLifecycleManagerǁcalculate_backoff__mutmut_6` | TEST-GAP | `test_lifecycle_manager.py:251` `TestLifecycleManagerCalculateBackoff` (src line 131) | cap is only asserted at 300.0 and below (16/20/300) — never above, so the drop is invisible |
| C2 | `should_restart`: `backoff_remaining(service) <= 0` → `<= 1` — restart allowed **1s early** | 1 | `…xǁLifecycleManagerǁshould_restart__mutmut_7` | TEST-GAP | `test_lifecycle_manager.py:287` `TestShouldRestart` (src line 159) | backoff gaps are coarse: 8s vs 5s, 160s vs 1s, 10s vs 30s. Nothing probes the 0–1s band |
| C3 | `handle_unhealthy`: `new_count == service.max_failures` → `!=` — max-failures warning fires on the wrong failure | 1 | `…handle_unhealthy__mutmut_5` | TEST-GAP | `test_lifecycle_manager.py:700` `TestHandleUnhealthy` (src line 415) | no test asserts the warning at all (0 `caplog` uses in the file) |
| C4 | `start_service`/`stop_service`/`handle_missing`: `registry.persist_state(service.name)` → `persist_state(None)` | 3 | `start_service__8`, `stop_service__12`, `handle_missing__8` | TEST-GAP | `:485 TestStartService`, `:521 TestStopService`, `:859 TestHandleMissing` (src 313, 337, 459) | `TestServiceRegistry::test_persist_state` (`:1152`) exercises persist on the real registry — never its call argument on these three methods |
| C5 | `start_service`/`stop_service`: `registry.update_status(service.name, …)` **name argument** → `None` | 2 | `start_service__4`, `stop_service__8` | TEST-GAP | `:485`, `:521` (src 312, 336) | only `restart_service` (and `enable`/`disable`) assert `update_status` args; the sibling start/stop paths assert none |
| C6 | `start_service`/`stop_service`: `registry.update_status(...)` **status argument** → `None` | 2 | `start_service__5`, `stop_service__9` | TEST-GAP | `:485`, `:521` (src 312, 336) | same — the STARTING / STOPPED transition itself is unobserved here |
| C7 | `start_service`/`stop_service`: `registry.update_status(...)` argument **removed** (raises `TypeError`) | 4 | `start_service__6`, `start_service__7`, `stop_service__10` (+`stop_service__11`) | TEST-GAP (runner artifact — see §asymmetry) | `:485 TestStartService`, `:521 TestStopService` (src 312, 336) | individually killable; batch runner does not charge the raise. Sibling arg-removal mutants did NOT survive: `restart_service`'s are killed by `test_restart_service_updates_tracking` (:406) asserting the args even though the raise is swallowed, and `enable`/`disable`/`handle_missing` have no `except` so the `TypeError` propagates — start/stop are the only combination of "swallowing except" **and** "no arg assertion" |
| C8 | `handle_unhealthy`: `service.last_failure_at = datetime.now(UTC)` → `= None` | 1 | `handle_unhealthy__8` | TEST-GAP | `test_lifecycle_manager.py:700` `TestHandleUnhealthy` (src line 423) | **every `last_failure_at` reference in the test file is a WRITE (setup); line 1072 asserts it on `reset_failures`, never on handle_unhealthy.** This is the module's "update the timestamp AFTER checking restart" invariant — completely unasserted |
| C9 | `logger.*(f-string)` → `logger.info(None)` / `logger.warning(None)` / `logger.debug(None)` | 13 | `restart_service__16`, `start_service__9`, `stop_service__13` | **LOW-VALUE** | all classes | real text loss in operator-facing logs; the tests here use `MagicMock(spec=ServiceRegistry)`/`AsyncMock` collaborators and assert only on mock calls + return values |
| C10 | `handle_unhealthy`: warning **message body** → `None` (the `==` branch still entered) | 1 | `handle_unhealthy__6` | **LOW-VALUE** | `:700` (src 416-419) | message text only |
| | **TOTAL** | **29** | | | | |

Totals: TEST-GAP 15 (C1,C2,C3,C4,C5,C6,C7,C8) · LOW-VALUE 14 (C9,C10) · EQUIVALENT 0.

C9 membership (all 13, log-message → `None`): `restart_service__16/18/20`, `start_service__9`,
`stop_service__13`, `enable_service__4/17`, `disable_service__4/16`, `handle_unhealthy__13`,
`handle_stopped__2/7`, `handle_missing__9`. Note that `restart_service`, `enable_service` and
`disable_service` had their **registry-argument** mutants killed (the existing
`*_updates_status`/`*_persists_state` tests assert those args) — only their log mutants survived.
That is the signature of a suite that asserts arguments on some paths and on siblings asserts
return values only.

## Why no EQUIVALENT cluster

Every `None`-of-a-registry-argument mutant is a real semantic change (the registry does a
`self._services.get(name)` lookup and **no-ops on a miss**, so `None` silently drops the write
instead of performing it — `backend/services/orchestrator/registry.py:182` and `:339`). The log
mutants are real text loss. Nothing here is semantically identical to the original.

## Coverage map — covering test files (from `mutmut-stats.json::tests_by_mangled_function_name`)

- **`backend/tests/unit/services/test_lifecycle_manager.py`** (1454 lines) — the module's own suite.
  Relevant classes: `TestCalculateBackoff` :142 · `TestLifecycleManagerCalculateBackoff` :251 ·
  `TestShouldRestart` :287 · `TestBackoffRemaining` :348 · `TestRestartService` :385 ·
  `TestStartService` :485 · `TestStopService` :521 · `TestEnableService` :559 ·
  `TestDisableService` :636 · `TestHandleUnhealthy` :700 · `TestHandleStopped` :807 ·
  `TestHandleMissing` :859 · `TestManualRestart` :1220 · `TestSelfHealingIntegration` :1326.
- **`backend/tests/unit/services/test_container_orchestrator.py`** — appears in every function's
  test list, but `TestWp44ControlPathArgsAndMessages` (:1983+) injects a **`MagicMock()` lifecycle
  manager**, so it runs none of this module's lines. Its
  `test_restart_service_fallback_updates_status_and_persists_by_name` (:2011) /
  `test_start_service_fallback_persists_by_name` (:2031) assert exactly the name-targeting
  discipline we need — **on `ContainerOrchestrator`'s own fallback branch** (`container_orchestrator.py:425-427`),
  not on the LifecycleManager. The pattern exists in the repo; it was simply never applied here.

## Two structural traps found while triaging

1. **The shared `ai_service` fixture has `restart_backoff_max=300.0`, equal to the library default.**
   Any cap test built on `ai_service` is a no-op probe. Use `monitoring_service`
   (`base=10.0, max=600.0`) or `infrastructure_service` (`base=2.0, max=60.0`).
2. **`restart_via_compose` (src :219-291) contains a near-identical
   `update_status(service.name, STARTING)` / `persist_state(service.name)` pair (src :275, :278).**
   `ContainerOrchestrator` never calls that method, so a start/stop assertion written carelessly
   could match the compose path. The drafted `handle_missing` test therefore asserts
   `call_count == 1` on `update_status`, and the start/stop tests assert `called_once_with`.

---

# Drafted tests

All below are **UNVERIFIED — not yet run red/green**. Style follows
`backend/tests/unit/services/test_lifecycle_manager.py`: `from __future__ import annotations`,
`@pytest.mark.asyncio` (asyncio_mode is `auto`, but the file marks explicitly), class-per-method
grouping, mock-registry `assert_called_once_with`.

**TDD procedure (one line each):** run the new test against the mutant copy → the named assertion
must FAIL; run it against `backend/services/lifecycle_manager.py` → it must PASS; then re-run the
STRICT census for these keys.

Existing imports needed (all already at the top of the test file):
`from datetime import UTC, datetime, timedelta` · `from unittest.mock import AsyncMock, MagicMock` ·
`import pytest` · `ContainerServiceStatus` · `LifecycleManager, ManagedService, ServiceRegistry, calculate_backoff`.
**One import to ADD** for D3: `from freezegun import freeze_time` (already a dev dependency,
`pyproject.toml:121`; precedent: `backend/tests/unit/services/test_unique_counter_service.py`).

---

## D1 → kills C1 (`calculate_backoff__mutmut_6`) + strengthens C8

Append to `TestLifecycleManagerCalculateBackoff` (after `test_calculate_backoff_monitoring_service`, line 279).

```python
    def test_calculate_backoff_uses_service_max_not_library_default(
        self, lifecycle_manager: LifecycleManager, monitoring_service: ManagedService
    ) -> None:
        """Cap must come from service.restart_backoff_max, never the 300.0 function default.

        WP4.4 C1: dropping the `max_backoff=service.restart_backoff_max` keyword silently
        reverts to the module default of 300.0. The existing cap tests assert exactly 300.0
        or values below it, so they cannot see the difference. monitoring_service has
        max=600.0, so the uncapped mutant returns 300.0 and this assertion fails.
        """
        # base=10.0 * 2**6 = 640.0, capped by the service's own 600.0 (NOT the 300.0 default).
        monitoring_service.failure_count = 6
        result = lifecycle_manager.calculate_backoff(monitoring_service)

        assert result == 600.0

    def test_calculate_backoff_cap_is_service_max_for_infrastructure(
        self, lifecycle_manager: LifecycleManager, infrastructure_service: ManagedService
    ) -> None:
        """Second cap probe in the other direction: infrastructure max=60.0 vs default 300.0."""
        # base=2.0 * 2**7 = 256.0 -> capped at the service's 60.0.
        infrastructure_service.failure_count = 7
        result = lifecycle_manager.calculate_backoff(infrastructure_service)

        assert result == 60.0
```

- **Red on mutant**: `max_backoff` omitted → `min(640.0, 300.0) == 300.0 != 600.0`. FAIL.
- **Green on original**: `min(640.0, 600.0) == 600.0`. PASS.
- Note: `ai_service` must NOT be used here — its `restart_backoff_max` is 300.0, identical to the
  default, which is precisely why the existing suite leaked this mutant.

---

## D2 → kills C2 (`should_restart__mutmut_7`)

Append to `TestShouldRestart` (after `test_should_restart_disabled_service`, line 340).

```python
    def test_should_restart_is_false_within_one_second_of_backoff_expiry(
        self, lifecycle_manager: LifecycleManager, infrastructure_service: ManagedService
    ) -> None:
        """Backoff boundary is EXACT: 0.5s of backoff left means no restart.

        WP4.4 C2: `backoff_remaining(service) <= 0` mutated to `<= 1` lets a service restart a
        full second before its backoff elapses. Existing probes are coarse (8s vs 5s, 160s vs 1s,
        10s vs 30s) so the 0-1s band is never observed. infrastructure_service (base=2.0) gives a
        small backoff so a sub-second offset is reachable without fake clocks.
        """
        infrastructure_service.failure_count = 2
        # Backoff = 2.0 * 2**2 = 8.0s. Fail 7.5s ago -> 0.5s still in backoff.
        infrastructure_service.last_failure_at = datetime.now(UTC) - timedelta(
            milliseconds=7500
        )

        assert lifecycle_manager.should_restart(infrastructure_service) is False

    def test_should_restart_is_true_just_after_backoff_expiry(
        self, lifecycle_manager: LifecycleManager, infrastructure_service: ManagedService
    ) -> None:
        """Mirror probe: 0.5s PAST expiry must allow the restart, so the boundary is pinned both ways."""
        infrastructure_service.failure_count = 2
        # Backoff 8.0s; 8.5s elapsed -> remaining 0.0.
        infrastructure_service.last_failure_at = datetime.now(UTC) - timedelta(
            milliseconds=8500
        )

        assert lifecycle_manager.should_restart(infrastructure_service) is True
```

- **Red on mutant**: first test → `backoff_remaining == 0.5 <= 1` → mutant returns `True`,
  `is False` FAILS.
- **Green on original**: `0.5 <= 0` is False → `should_restart` returns False. PASS.
- **Flake note (memory: vitest-midnight-flake / clock-mock discipline)**: these use real
  `datetime.now(UTC)` with a 0.5s tolerance band and no global fake timers, matching the file's
  existing style (`assert 7.0 <= remaining <= 9.0` at line 367). `pytest-timeout` is 5s, so a
  scheduler stall beyond 0.5s is not plausible; if the CI lane shows jitter, switch to
  `freeze_time` pinned inside the test body only.

---

## D3 → kills C4 (`start_service__8`, `stop_service__12`, `handle_missing__8`), C5 (`__4`/`__8`),
## and argument-removal members of C7

New class, insert after `TestHandleMissing` (line 887).

```python
# =============================================================================
# Registry Write Targeting Tests (WP4.4 C4 / C5 / C6 / C7)
# =============================================================================


class TestRegistryWritesTargetTheServiceName:
    """The status/persist writes must carry the service NAME and the right STATUS enum.

    WP4.4 C4/C5/C6/C7: start_service, stop_service and handle_missing write to the shared
    registry, but nothing asserted the arguments of those writes. `ServiceRegistry.update_status`
    and `.persist_state` look the service up by name and silently no-op on a miss
    (orchestrator/registry.py:182, :339), so `None` in place of the name is a *silent* loss of the
    write: the UI keeps showing the stale status and Redis never learns the new failure state.
    A mutation that removes an argument raises TypeError and is caught by the method's own
    `except Exception` under the batch runner, so `result is True` is asserted alongside.

    Uses monitoring_service deliberately: ai_service.restart_backoff_max happens to equal the
    library default, and these tests are about argument identity, not backoff.
    """

    @pytest.mark.asyncio
    async def test_start_service_updates_status_by_name_with_starting(
        self,
        lifecycle_manager: LifecycleManager,
        monitoring_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """start_service must call update_status(NAME, STARTING) — never (None, ...) / (name, None)."""
        result = await lifecycle_manager.start_service(monitoring_service)

        assert result is True
        mock_registry.update_status.assert_called_once_with(
            "grafana", ContainerServiceStatus.STARTING
        )

    @pytest.mark.asyncio
    async def test_start_service_persists_state_by_name(
        self,
        lifecycle_manager: LifecycleManager,
        monitoring_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """start_service must persist the named service, not persist_state(None)."""
        result = await lifecycle_manager.start_service(monitoring_service)

        assert result is True
        mock_registry.persist_state.assert_awaited_once_with("grafana")

    @pytest.mark.asyncio
    async def test_stop_service_updates_status_by_name_with_stopped(
        self,
        lifecycle_manager: LifecycleManager,
        monitoring_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """stop_service must call update_status(NAME, STOPPED)."""
        result = await lifecycle_manager.stop_service(monitoring_service)

        assert result is True
        mock_registry.update_status.assert_called_once_with(
            "grafana", ContainerServiceStatus.STOPPED
        )

    @pytest.mark.asyncio
    async def test_stop_service_persists_state_by_name(
        self,
        lifecycle_manager: LifecycleManager,
        monitoring_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """stop_service must persist the named service, not persist_state(None)."""
        result = await lifecycle_manager.stop_service(monitoring_service)

        assert result is True
        mock_registry.persist_state.assert_awaited_once_with("grafana")

    @pytest.mark.asyncio
    async def test_handle_missing_persists_state_by_name(
        self,
        lifecycle_manager: LifecycleManager,
        monitoring_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """handle_missing must persist the named service after clearing container_id.

        `update_status` is asserted with call_count==1 so this test cannot be satisfied by the
        restart_via_compose branch (orchestrator/…:275), which carries the same STARTING write and
        is unreachable from these tests.
        """
        await lifecycle_manager.handle_missing(monitoring_service)

        mock_registry.update_status.assert_called_once_with(
            "grafana", ContainerServiceStatus.NOT_FOUND
        )
        mock_registry.update_container_id.assert_called_once_with("grafana", None)
        mock_registry.persist_state.assert_awaited_once_with("grafana")
```

- **Red**: C4/C5/C6 → the mock records `(None, STARTING)` / `(name, None)` / `(None,)` and the
  `*_with` assertion fails. C7 → `TypeError` is swallowed, `result is False`, `is True` fails
  (a strict runner also errors on the raise). `handle_missing` has no `try`, so its
  `persist_state(None)` mutant fails the `assert_awaited_once_with("grafana")` directly.
- **Green**: original passes `(name, STARTING/STOPPED/NOT_FOUND)` and `persist_state(name)`.

---

## D4 → kills C8 (`handle_unhealthy__mutmut_8`)

Append to `TestHandleUnhealthy` (after `test_handle_unhealthy_skips_restart_during_backoff`, line 799).

```python
    @pytest.mark.asyncio
    @freeze_time("2026-09-19T12:00:00+00:00")
    async def test_handle_unhealthy_stamps_last_failure_at_after_restart_check(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """handle_unhealthy must refresh last_failure_at, and must do so AFTER the restart check.

        WP4.4 C8: `service.last_failure_at = datetime.now(UTC)` mutated to `= None` removes the
        only memory of "when did this service last fail" — every later should_restart() then takes
        the `last_failure_at is None` early-return and the backoff ladder collapses into an
        immediate-restart loop. No existing test ever asserts this field: every
        `last_failure_at` mention in this file is SETUP, and the only read-assertion (line 1072)
        belongs to reset_failures.
        """
        ai_service.failure_count = 0
        ai_service.last_failure_at = None
        mock_registry.increment_failure.return_value = 1

        await lifecycle_manager.handle_unhealthy(ai_service)

        assert ai_service.last_failure_at == datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)
        assert ai_service.failure_count == 1

    @pytest.mark.asyncio
    async def test_handle_unhealthy_backoff_is_measured_from_the_new_failure(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Consequence probe: a second unhealthy call inside the backoff window must NOT restart.

        If the stamp is dropped (mutant `= None`) the second call sees no prior failure and
        restarts again — so this kills C8 through behaviour the operator actually depends on,
        without depending on an exact clock value.
        """
        ai_service.failure_count = 0
        ai_service.last_failure_at = None
        # First call: no prior failure -> restart allowed. Second call: failure_count is now 1
        # (backoff 5.0 * 2**1 = 10s) and the stamp is milliseconds old -> must be skipped.
        mock_registry.increment_failure.side_effect = [1, 2]

        await lifecycle_manager.handle_unhealthy(ai_service)
        await lifecycle_manager.handle_unhealthy(ai_service)

        assert ai_service.failure_count == 2
        assert ai_service.last_failure_at is not None
        mock_docker_client.stop_container.assert_called_once()
        mock_docker_client.start_container.assert_called_once()
```

- **Red**: mutant sets `last_failure_at = None` → first test's equality assertion fails; second
  test sees `stop_container` called twice, so `assert_called_once()` fails.
- **Green**: stamp written between the `should_restart` check and the restart dispatch.
- `freeze_time` import must be added; the decorator pins the clock **inside this test only**
  (per-test freeze, never a global fake-timer fixture — see the vitest-midnight-flake lesson).

---

## D5 → kills C3 (`handle_unhealthy__mutmut_5`)

Append to `TestHandleUnhealthy`. Introduces the file's first `caplog` usage.

```python
    @pytest.mark.asyncio
    async def test_handle_unhealthy_warns_exactly_at_max_failures_threshold(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The max-failures warning fires ONCE, on the failure that reaches max_failures.

        WP4.4 C3: `if new_count == service.max_failures` mutated to `!=` inverts the threshold —
        the operator sees the "exceeded N failures" warning on every failure except the one it
        describes, and stays silent at the moment it matters. This is the file's first caplog
        assertion; the guard is that the module's logger must propagate to caplog (backend.core
        logging), so `caplog.set_level` plus the logger-name check below make the test fail loudly
        rather than vacuously if propagation is disabled.
        """
        caplog.set_level("WARNING", logger="backend.services.lifecycle_manager")
        assert "backend.services.lifecycle_manager" in caplog.record_names or caplog.records

        ai_service.failure_count = ai_service.max_failures - 1  # 4
        ai_service.last_failure_at = None
        mock_registry.increment_failure.return_value = ai_service.max_failures  # 5

        await lifecycle_manager.handle_unhealthy(ai_service)

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("exceeded 5 failures" in r.getMessage() for r in warnings), caplog.text

    @pytest.mark.asyncio
    async def test_handle_unhealthy_does_not_warn_below_max_failures(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """One failure in (count 1 of 5) must NOT emit the max-failures warning.

        Pair-probe for C3: the `!=` mutant warns here. Together the two tests pin the `==`
        boundary and also pin LOW-VALUE C10 (the message body -> None), since the message text
        is now asserted.
        """
        caplog.set_level("WARNING", logger="backend.services.lifecycle_manager")

        ai_service.failure_count = 0
        ai_service.last_failure_at = None
        mock_registry.increment_failure.return_value = 1

        await lifecycle_manager.handle_unhealthy(ai_service)

        # The backoff branch does not run here (can_restart is True), so the only WARNING that
        # could appear is the max-failures one.
        warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert not any("exceeded" in m for m in warnings), caplog.text
```

- **Red**: mutant `!=` → at `new_count == max_failures` the warning block is skipped, so
  `any(...)` is False and the first test fails; below the threshold the mutant DOES warn and the
  second test fails. Either alone kills C3; the pair also kills C10 (the `None` message body makes
  `getMessage()` return `"None"`, so the `"exceeded 5 failures"` substring is gone).
- **Green**: `==` warns only at the threshold, with the real text.
- **Propagation assumption, checked statically (still UNVERIFIED at runtime)**:
  `get_logger` (backend/core/logging.py:1107-1123) is a plain `logging.getLogger(name)` with a
  filter attached, and the word `propagate` appears exactly once in that module — in a docstring
  (:432), never as an assignment. `setup_logging` puts its handlers on the ROOT logger (:871,
  :887, :898). So the module logger propagates to root and caplog's root handler sees the record.
  The in-test guard makes a wrong guess read as a loud failure instead of a vacuous pass.
  Propagation-independent fallback if needed:
  `monkeypatch.setattr(lifecycle_module.logger, "warning", MagicMock())` + assert on call args.

---

## Deliberately NOT drafted

- **C9 (13 log-message → `None` mutants) + C10 (1): LOW-VALUE, no test drafted.** Killing them means
  `caplog`/`caplog`-equivalent text assertions on 15 f-strings in a module whose whole suite is
  built on `MagicMock` collaborators. That converts the suite into a log-text mirror: every future
  wording change breaks N tests, and the behaviour at risk (an operator reading a log line) is not
  something a unit test protects. C5/C6/C8 are the assertions that actually earn their keep here.
  Recorded so the module's 117→? ceiling is understood: **a realistic strict-census ceiling for this
  file after D1–D5 lands is 117 + 15 = 132/146 (90.4%)**, with the 14 LOW-VALUE log mutants as the
  accepted residual.

## Reconciliation check

Cluster counts `1+1+1+3+2+2+4+1+13+1 = 29` = survivor total from the meta (29). Killed 117 +
survived 29 + unchecked 0 = 146 keys. ✓
