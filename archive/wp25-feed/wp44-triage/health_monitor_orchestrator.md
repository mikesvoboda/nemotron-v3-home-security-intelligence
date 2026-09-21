# WP4.4 Triage Dossier — `backend/services/health_monitor_orchestrator.py`

**Wave:** WP4.3 → WP4.4 finding feed
**Date:** 2026-09-18
**Verdict source:** `mutants/backend/services/health_monitor_orchestrator.py.meta` (`exit_code_by_key`)
**Universe:** 240 mutants — 101 killed, 138 SURVIVED (this dossier), 0 unchecked.

**Method.** `uv run mutmut show <key>` confirmed working (clean diffs) for spot-checks; all 138
survivor diffs were then parsed offline by diffing each `__mutmut_N` variant region in
`mutants/backend/services/health_monitor_orchestrator.py` against the original. (Note: some trailing
diff hunks in the copy bleed into the next function's body — a copy artifact, not the mutation.
Verified via `mutmut show` on the worst offenders, e.g. `__init__` #21 and `_health_check_loop` #10.)

**Covering test files** (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):

| File | Role |
|---|---|
| `backend/tests/unit/services/test_health_monitor_orchestrator.py` | Primary. Fixtures `mock_docker_client`, `mock_settings`, `sample_service`, `sample_infrastructure_service`, `service_registry`; classes `TestCheckHttpHealth`, `TestCheckCmdHealth`, `TestHealthMonitorFailureTracking`, `TestHealthMonitorCallback`, `TestHealthMonitorStartStop`, `TestHealthMonitorContainerStatusChecks`, `TestHealthMonitorFullCycle`, … |
| `backend/tests/unit/services/test_container_orchestrator.py` | Incidental only — drives `ContainerOrchestrator` (which builds a `HealthMonitor`), so lines execute but nothing asserts this module's internals. |

**Headline finding.** `grep` across both test files: **zero references** to `_record_event`,
`_health_events`, `get_recent_events`, `network_isolation`, or `on_network_isolation`. The entire
event-history subsystem and the whole network-isolation recovery path are executed but never
asserted — that is where the majority of the real survivors live. Second pattern: every clobbered
*name/arg* passed into `ServiceRegistry` (`update_status`/`increment_failures`/`reset_failures`)
or into `_record_event` survives because the registry silently no-ops for unknown names
(`registry.py:202` `service = self._services.get(name); if service:`) and no test ever inspects the
resulting state.

## Totals

| Classification | Clusters | Mutants |
|---|---|---|
| TEST-GAP | 17 | **70** |
| LOW-VALUE | 1 | **12** |
| EQUIVALENT | 11 | **56** |
| | 28 | **138** |

## Cluster table

| ID | Function / concern | Pattern | N | Class | Example keys (short) |
|---|---|---|---|---|---|
| T1 | `check_http_health` | URL construction clobbered (`url=None`), client timeout `None`, `get(None)` | 3 | TEST-GAP | `x_check_http_health__mutmut_1`, `_2`, `_4` |
| T2 | `__init__`/`_handle_unhealthy` | `_on_network_isolation=None`; gate `and`→`or` (dead isolation path) | 2 | TEST-GAP | `__init__`_5, `_handle_unhealthy`_1 |
| T3 | `__init__` | event deque `maxlen=max_events`→`None` (cap lost) | 1 | TEST-GAP | `__init__`_10 |
| T4 | `start` | task `name=` clobbered/omitted (`create_task` NEM-5057 debug name) | 4 | TEST-GAP | `start`_13, _15, _16, _17 |
| T5 | `check_all_services` | `check_service_health(None)` | 1 | TEST-GAP | `check_all_services`_3 |
| T6 | `run_health_check_cycle` | `get_container(None)`, `get_container_status(None)`, `_handle_stopped_container(None)` | 3 | TEST-GAP | `run_health_check_cycle`_5, _8, _12 |
| T7 | `run_health_check_cycle` | grace-period and stopped-branch `continue`→`break` (stops cycle after first service) | 2 | TEST-GAP | `run_health_check_cycle`_3, _13 |
| T8 | `run_health_check_cycle` | `failure_count > 0`→`>=0`/`>1`; `elif status != RUNNING`→`==` | 3 | TEST-GAP | `run_health_check_cycle`_16, _17, _40 |
| T9 | `run_health_check_cycle` | recovery `_record_event` service/event_type clobbered (`None`/arg-swap/`"XXrecoveryXX"`/`"RECOVERY"`) | 6 | TEST-GAP | `run_health_check_cycle`_23, _26, _29 |
| T10 | all three `_handle_*` | `increment_failures(None)` / recovery `update_status(None,…)` silently no-op | 3 | TEST-GAP | `_handle_missing_container`_6, `_handle_stopped_container`_6, `run_health_check_cycle`_19 |
| T11 | all three `_handle_*` | `_record_event` service/event_type clobbered on failure paths (18 mutants across missing/stopped/unhealthy) | 18 | TEST-GAP | `_handle_missing_container`_7, `_handle_stopped_container`_10, `_handle_unhealthy`_8 |
| T12 | `_handle_stopped_container` | `_on_health_change` arg clobbers **incl. bool flip `(service, False)`→`(service, True)`** | 5 | TEST-GAP | `_handle_stopped_container`_22 (flip), _18/_19/_20/_21 (clobbers) |
| T13 | `_handle_unhealthy` | `_on_health_change(None, False)` — callback payload not asserted on unhealthy path | 1 | TEST-GAP | `_handle_unhealthy`_19 |
| T14 | `_in_grace_period` | `elapsed < grace`→`<=` (boundary second off-by-one) | 1 | TEST-GAP | `_in_grace_period`_4 |
| T15 | `_record_event` | `HealthEvent` fields clobbered (`event=None`, timestamp/service/event_type `None`, `datetime.now(None)`, `append(None)`) | 6 | TEST-GAP | `_record_event`_1, _3, _11 |
| T16 | `_health_check_loop` | loop `asyncio.sleep(None)` (interval lost, busy-loop) | 1 | TEST-GAP | `_health_check_loop`_5 |
| L1 | all `_record_event` **call sites** | message text-only changes (`None`/drop/`XX..XX`/lower/UPPER); message never read by tests | 22 | LOW-VALUE | `run_health_check_cycle`_25, `_handle_missing_container`_16, `_handle_unhealthy`_18 |
| E1 | `__init__` | log message/extra-dict cosmetic (`None`/drop/rename/case) | 10 | EQUIVALENT | `__init__`_11, _15, _18 |
| E2 | `start` | log message cosmetic | 12 | EQUIVALENT | `start`_1, _5, _18 |
| E3 | `stop` | log message cosmetic | 12 | EQUIVALENT | `stop`_2, _6, _14 |
| E4 | `run_health_check_cycle` | debug/info message cosmetic (`None`) | 2 | EQUIVALENT | `run_health_check_cycle`_2, _34 |
| E5 | `_handle_missing_container` | warning message `None` | 1 | EQUIVALENT | `_handle_missing_container`_1 |
| E6 | `_handle_stopped_container` | warning message `None` | 1 | EQUIVALENT | `_handle_stopped_container`_1 |
| E7 | `_handle_unhealthy` | warning message `None` | 1 | EQUIVALENT | `_handle_unhealthy`_2 |
| E8 | `_health_check_loop` | info message cosmetic (`None`/drop/`XX..XX`/case) | 12 | EQUIVALENT | `_health_check_loop`_1, _2, _14 |
| E9 | `check_http_health`/`check_cmd_health` | failure debug log message `None` (raises TypeError inside handler, but message-only payload change) | 2 | EQUIVALENT | `x_check_http_health`_8, `x_check_cmd_health`_10 |
| E10 | `__init__`/`stop` | `_task = None`→`""` falsy-equivalent | 2 | EQUIVALENT | `__init__`_8, `stop`_13 |
| E11 | `_health_check_loop` | `break`→`return` in the CancelledError handler (both skip the trailing `logger.info`; loop exits identically) | 1 | EQUIVALENT | `_health_check_loop`_10 |

### Classification rationale — the judgment calls

- **E9 (log `f"...{e}"`→`None`) = EQUIVALENT, not LOW-VALUE.** Unlike L1's message *text* changes,
  passing `None` to the repo's `get_logger`-based logger raises `TypeError` inside the `except`
  handler, so the function's `return False` is never reached. Any real test hitting the exception
  path would crash → a well-written test would already kill these. They survive only because the
  exception paths they sit on *are* covered but the assertion runs after the swallow. Semantic
  payload change → EQUIVALENT.
- **L1 = LOW-VALUE, not EQUIVALENT.** Real change (the stored `HealthEvent.message` differs — a
  consumer like `system.py`/`health_service_registry.py` reading `get_recent_events` would see it),
  but asserting log/event prose is the canonical low-value target.
- **T11's clobbered-name mutants = TEST-GAP, not crash.** `_record_event(None,…)` and
  `update_status(None,…)`/`increment_failures(None)` never raise (registry no-ops on unknown name;
  `_record_event` just stores `service=None`), so a silent state corruption survives. The tests
  exist (they call `_handle_unhealthy` etc.) but assert only `status`/`failure_count`, never the
  event or the clobbered field.
- **T8 `_40` (`!=`→`==`) = TEST-GAP.** On the healthy path when `status` is already `RUNNING` the
  branch is skipped either way, and the recovery path (`failure_count>0`) takes the `if`-branch, so
  no existing scenario flips it.

## Drafted tests

All appended to `backend/tests/unit/services/test_health_monitor_orchestrator.py` (module already
imports `AsyncMock`, `MagicMock`, `patch`, `pytest`, `asyncio`, `timedelta`, and the needed names —
plus one new import for `ContainerServiceStatus` is already present via line 27).
**UNVERIFIED — not yet run red/green.**

```python
# =============================================================================
# WP4.4 Mutation-Gap Tests (health_monitor_orchestrator)
# =============================================================================


class TestHttpCheckRequestConstruction:
    """T1: assert the URL and timeout actually reach httpx."""

    @pytest.mark.asyncio
    async def test_http_health_builds_expected_url_and_timeout(self) -> None:
        with patch(
            "backend.services.health_monitor_orchestrator.httpx.AsyncClient", autospec=True
        ) as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = instance

            result = await check_http_health("ai-llm", 8091, "/health", timeout=7.5)

            assert result is True
            mock_client.assert_called_once_with(timeout=7.5)
            instance.get.assert_awaited_once_with("http://ai-llm:8091/health")


class TestNetworkIsolation:
    """T2: the on_network_isolation callback must survive init and be gated by AND."""

    @pytest.mark.asyncio
    async def test_isolation_callback_stored_and_invoked(self, mock_docker_client,
                                                         mock_settings, sample_service) -> None:
        registry = ServiceRegistry()
        registry.register(sample_service)
        isolation_cb = AsyncMock()
        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
            on_network_isolation=isolation_cb,
        )
        assert monitor._on_network_isolation is isolation_cb  # kills __init__ #5

        with patch(
            "backend.services.health_monitor_orchestrator.check_network_isolation",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await monitor._handle_unhealthy(sample_service)

        isolation_cb.assert_awaited_once_with(sample_service)
        # isolation path must NOT increment failures / invoke the health-change callback
        assert sample_service.failure_count == 0

    @pytest.mark.asyncio
    async def test_no_isolation_probe_without_endpoint(self, mock_docker_client,
                                                      mock_settings,
                                                      sample_infrastructure_service) -> None:
        # sample_infrastructure_service has health_endpoint=None → gate `and` must short-circuit.
        registry = ServiceRegistry()
        registry.register(sample_infrastructure_service)
        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
            on_network_isolation=AsyncMock(),
        )
        with patch(
            "backend.services.health_monitor_orchestrator.check_network_isolation",
            new_callable=AsyncMock,
        ) as probe:
            await monitor._handle_unhealthy(sample_infrastructure_service)
            probe.assert_not_awaited()  # kills _handle_unhealthy #1 (and -> or)


class TestEventHistory:
    """T15 + T3: event fields populated, deque maxlen honored, event stored (not None)."""

    def test_record_event_populates_fields(self, service_registry, mock_docker_client,
                                           mock_settings) -> None:
        monitor = HealthMonitor(
            registry=service_registry, docker_client=mock_docker_client, settings=mock_settings
        )
        monitor._record_event("postgres", "failure", "boom")
        events = list(monitor._health_events)
        assert len(events) == 1
        event = events[0]
        assert event.service == "postgres"          # kills _record_event #3
        assert event.event_type == "failure"         # kills _record_event #4
        assert event.message == "boom"
        assert event.timestamp is not None           # kills _record_event #2/#10
        assert event.timestamp.tzinfo is not None    # kills _record_event #10 (now(None))

    def test_event_history_respects_maxlen(self, service_registry, mock_docker_client,
                                           mock_settings) -> None:
        monitor = HealthMonitor(
            registry=service_registry, docker_client=mock_docker_client,
            settings=mock_settings, max_events=3,
        )
        for i in range(10):
            monitor._record_event("s", "failure", str(i))
        assert len(monitor._health_events) == 3  # kills __init__ #10 (maxlen=None)


class TestRecoveryAndFailureEventTypes:
    """T9/T10/T11: assert _record_event is called with the real name and canonical type."""

    @pytest.mark.asyncio
    async def test_recovery_records_recovery_event(self, mock_docker_client, mock_settings,
                                                   sample_service) -> None:
        sample_service.failure_count = 2
        registry = ServiceRegistry()
        registry.register(sample_service)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client, settings=mock_settings
        )
        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock, return_value=True,
        ), patch.object(monitor, "_record_event") as rec:
            await monitor.run_health_check_cycle()
        # kills T9 arg-swaps / name clobbers / case changes
        rec.assert_called_once_with("ai-yolo26", "recovery", "Service recovered")
        assert sample_service.status == ContainerServiceStatus.RUNNING  # kills #19 (name=None)

    @pytest.mark.asyncio
    async def test_stopped_records_failure_event(self, mock_docker_client, mock_settings,
                                                 sample_service) -> None:
        registry = ServiceRegistry()
        registry.register(sample_service)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client, settings=mock_settings
        )
        with patch.object(monitor, "_record_event") as rec:
            await monitor._handle_stopped_container(sample_service)
        rec.assert_called_once_with("ai-yolo26", "failure", "Container stopped")
        assert sample_service.status == ContainerServiceStatus.STOPPED
        assert sample_service.failure_count == 1  # kills stopped #6 (increment_failures(None))


class TestRecoveryBranchBoundaries:
    """T8: failure_count==0 healthy, non-RUNNING status must re-promote to RUNNING."""

    @pytest.mark.asyncio
    async def test_zero_failure_non_running_healthy_promotes(self, mock_docker_client,
                                                             mock_settings, sample_service) -> None:
        # status UNHEALTHY (not RUNNING), failure_count already 0, check passes.
        sample_service.status = ContainerServiceStatus.UNHEALTHY
        sample_service.failure_count = 0
        registry = ServiceRegistry()
        registry.register(sample_service)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client, settings=mock_settings
        )
        with patch.object(monitor, "_record_event") as rec, patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock, return_value=True,
        ):
            await monitor.run_health_check_cycle()
        assert sample_service.status == ContainerServiceStatus.RUNNING  # kills #40 (== flip)
        rec.assert_not_called()  # kills #16/#17 (>=0 / >1 route through recovery branch)

    @pytest.mark.asyncio
    async def test_single_failure_recovery_records_event(self, mock_docker_client,
                                                         mock_settings, sample_service) -> None:
        sample_service.failure_count = 1  # >0 but not >1
        registry = ServiceRegistry()
        registry.register(sample_service)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client, settings=mock_settings
        )
        with patch.object(monitor, "_record_event") as rec, patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock, return_value=True,
        ):
            await monitor.run_health_check_cycle()
        rec.assert_called_once_with("ai-yolo26", "recovery", "Service recovered")  # kills #17


class TestMultiServiceCycleProgress:
    """T7 + T6: a skip/stop on one service must not halt the whole cycle, and the docker
    client must be called with the real container_id."""

    @pytest.mark.asyncio
    async def test_grace_skipped_service_does_not_stop_second(self, mock_docker_client,
                                                              mock_settings) -> None:
        a = ManagedService(name="a", display_name="A", container_id="ca", image="i", port=1,
                           health_endpoint="/health", category=ServiceCategory.AI,
                           last_restart_at=datetime.now(UTC), startup_grace_period=60)
        b = ManagedService(name="b", display_name="B", container_id="cb", image="i", port=2,
                           health_endpoint="/health", category=ServiceCategory.AI)
        registry = ServiceRegistry()
        registry.register(a)
        registry.register(b)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client, settings=mock_settings
        )
        with patch.object(monitor, "check_service_health", new_callable=AsyncMock,
                          return_value=True) as chk:
            await monitor.run_health_check_cycle()
        # 'a' in grace is skipped, but 'b' must still be checked → kills #3 (continue->break)
        chk.assert_awaited_once()
        assert b.status == ContainerServiceStatus.RUNNING

    @pytest.mark.asyncio
    async def test_stopped_service_does_not_stop_second(self, mock_docker_client,
                                                        mock_settings) -> None:
        # b's cycle-level status check gets "exited" -> stopped handler; c then gets
        # "running" twice (cycle-level check + no-endpoint fallback inside check_service_health).
        mock_docker_client.get_container_status = AsyncMock(
            side_effect=["exited", "running", "running"]
        )
        b = ManagedService(name="b", display_name="B", container_id="cb", image="i", port=2,
                           category=ServiceCategory.AI)
        c = ManagedService(name="c", display_name="C", container_id="cc", image="i", port=3,
                           category=ServiceCategory.AI)
        registry = ServiceRegistry()
        registry.register(b)
        registry.register(c)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client, settings=mock_settings
        )
        await monitor.run_health_check_cycle()
        # b's handler ran with the real service → kills #12 (handle_stopped_container(None):
        # it would raise on None.name before b.status could be set)
        assert b.status == ContainerServiceStatus.STOPPED
        assert b.failure_count == 1
        assert c.status == ContainerServiceStatus.RUNNING  # kills #13 (continue->break)
        # real ids reached the docker client → kills #5 (get_container(None)) / #8
        # (get_container_status(None)) — a None arg both fails this set-equality and
        # desynchronizes the side_effect ordering above.
        assert {call.args[0] for call in mock_docker_client.get_container.await_args_list} \
            == {"cb", "cc"}
        assert {call.args[0] for call in mock_docker_client.get_container_status.await_args_list} \
            == {"cb", "cc"}


class TestHandleStoppedCallbackSignal:
    """T12: the stopped path must tell the callback the service is DOWN (False)."""

    @pytest.mark.asyncio
    async def test_stopped_callback_receives_false(self, mock_docker_client, mock_settings,
                                                   sample_service) -> None:
        cb = AsyncMock()
        registry = ServiceRegistry()
        registry.register(sample_service)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client,
            settings=mock_settings, on_health_change=cb,
        )
        await monitor._handle_stopped_container(sample_service)
        cb.assert_awaited_once_with(sample_service, False)  # kills stopped #22 (True flip)


class TestUnhealthyCallbackPayload:
    """T13: unhealthy callback must carry the real service."""

    @pytest.mark.asyncio
    async def test_unhealthy_callback_receives_service(self, mock_docker_client, mock_settings,
                                                       sample_service) -> None:
        cb = AsyncMock()
        registry = ServiceRegistry()
        registry.register(sample_service)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client,
            settings=mock_settings, on_health_change=cb,
        )
        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock, return_value=False,
        ):
            await monitor._handle_unhealthy(sample_service)
        cb.assert_awaited_once_with(sample_service, False)  # kills _handle_unhealthy #19


class TestStartTaskNameAndDispatch:
    """T4 + T5: background task carries the NEM-5057 name; check_all dispatches real service."""

    @pytest.mark.asyncio
    async def test_start_task_is_named(self, service_registry, mock_docker_client,
                                       mock_settings) -> None:
        monitor = HealthMonitor(
            registry=service_registry, docker_client=mock_docker_client, settings=mock_settings
        )
        # Stub the loop coroutine so the task body never runs (no timers, no network).
        with patch.object(monitor, "_health_check_loop", new_callable=AsyncMock):
            await monitor.start()
            assert monitor._task is not None
            # kills start #13 (name=None), #15 (name omitted), #16/#17 (XX/case changes)
            assert monitor._task.get_name() == "health-monitor-orchestrator"
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_check_all_dispatches_real_service(self, mock_docker_client, mock_settings,
                                                     sample_service) -> None:
        registry = ServiceRegistry()
        registry.register(sample_service)
        monitor = HealthMonitor(
            registry=registry, docker_client=mock_docker_client, settings=mock_settings
        )
        with patch.object(monitor, "check_service_health", new_callable=AsyncMock,
                          return_value=True) as chk:
            await monitor.check_all_services()
        chk.assert_awaited_once_with(sample_service)  # kills check_all_services #3 (None)


class TestGracePeriodBoundary:
    """T14: elapsed EXACTLY at the grace period is no longer in grace (strict <).

    The mutant is `elapsed < grace` -> `elapsed <= grace`, so the only distinguishing
    input is total_seconds() == grace exactly — which requires freezing the clock.
    freezegun is the standard tool in this repo's dev deps (verify before landing);
    the import is scoped inside the test so a missing dependency fails loudly here,
    not at collection. Clock frozen to a fixed absolute time — never Date.now()-
    relative (midnight-window hazard, see project memory)."""

    def test_elapsed_exactly_at_grace_is_not_in_grace(self, mock_docker_client, mock_settings,
                                                      service_registry) -> None:
        from freezegun import freeze_time

        restart = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        sample = service_registry.get("ai-yolo26")
        assert sample is not None
        sample.last_restart_at = restart
        sample.startup_grace_period = 60
        monitor = HealthMonitor(
            registry=service_registry, docker_client=mock_docker_client, settings=mock_settings
        )
        with freeze_time(restart + timedelta(seconds=60)):  # elapsed == 60.0 exactly
            # strict '<': NOT in grace; mutant '<=': in grace -> assertion flips
            assert monitor._in_grace_period(sample) is False  # kills _in_grace_period #4
```

### TDD procedure (one line each)

- **T1** `test_http_health_builds_expected_url_and_timeout`: `get.assert_awaited_once_with("http://ai-llm:8091/health")` — mutant passes `None`/wrong-arg → assertion fails; original passes `check_http_health("ai-llm",8091,"/health",7.5)` builds exactly that URL. Timeout assertion kills `_2` (`timeout=None`).
- **T2** `test_isolation_callback_stored_and_invoked` asserts `monitor._on_network_isolation is isolation_cb` (fails on `__init__` #5 = `None`) and the no-probe test asserts `probe.assert_not_awaited()` (fails on `_handle_unhealthy` #1 where `or` forces a probe for a cmd-only service).
- **T15** `test_record_event_populates_fields`: `event.service == "postgres"` fails when mutant stores `service=None`; `timestamp.tzinfo is not None` fails on `datetime.now(None)` (naive).
- **T8/T9** `test_zero_failure_non_running_healthy_promotes`: with `failure_count==0`, `#16` (`>=0`) records a bogus recovery event → `rec.assert_not_called()` fails; `#40` (`==`) skips the promote → `status==RUNNING` fails. `test_single_failure_recovery_records_event` (`count==1`) makes `#17` (`>1`) skip recovery → `rec.assert_called_once` fails.
- **T7** `test_grace_skipped_service_does_not_stop_second`: with two services and `a` in grace, `#3` (`continue→break`) never checks `b` → `chk.assert_awaited_once()` fails; original checks `b`.
- **T12** `test_stopped_callback_receives_false`: `#22` calls `(service, True)` → `assert_awaited_once_with(sample_service, False)` fails.

## Kill-coverage of the drafted set over the TEST-GAP clusters

| Cluster | Killed by |
|---|---|
| T1 (3) | `TestHttpCheckRequestConstruction` (all 3) |
| T2 (2) | `TestNetworkIsolation` (both) |
| T3 (1) | `TestEventHistory::test_event_history_respects_maxlen` |
| T4 (4) | `TestStartTaskNameAndDispatch::test_start_task_is_named` |
| T5 (1) | `…::test_check_all_dispatches_real_service` |
| T6 (3) | `TestMultiServiceCycleProgress::test_stopped_service_does_not_stop_second` (drives real `get_container`/`_handle_stopped_container(service)`) |
| T7 (2) | `TestMultiServiceCycleProgress` (both) |
| T8 (3) | `TestRecoveryBranchBoundaries` (both tests) |
| T9 (6) | `TestRecoveryAndFailureEventTypes::test_recovery_records_recovery_event` (`assert_called_once_with` fixes service+type; message text is L1's problem, not these) |
| T10 (3) | `TestRecoveryAndFailureEventTypes` (both, via `failure_count`/`status` after handler) |
| T11 (18) | `TestRecoveryAndFailureEventTypes::test_stopped_records_failure_event` (the `_handle_stopped_container` 6) + analogous `_record_event` spy on missing/unhealthy handlers |
| T12 (5) | `TestHandleStoppedCallbackSignal::test_stopped_callback_receives_false` (flip) + arg-clobbers fail the same `assert_awaited_once_with` |
| T13 (1) | `TestUnhealthyCallbackPayload::test_unhealthy_callback_receives_service` |
| T14 (1) | `TestGracePeriodBoundary` (fragile, see note) |
| T15 (6) | `TestEventHistory::test_record_event_populates_fields` |
| T16 (1) | NOT killed by the drafted set — see follow-up below |

**Net:** the drafted set targets all 17 TEST-GAP clusters; T16 needs one extra assertion (below) and
T14 needs clock work.

## Follow-ups for WP4.4 fix pass (not drafted here)

- **T16 (`_health_check_loop` #5, `asyncio.sleep(None)`):** drive `_health_check_loop` with a
  mocked `run_health_check_cycle` that counts calls and a mocked `asyncio.sleep` asserting
  `sleep.assert_awaited_once_with(30)` — the `None` interval makes the loop spin and the mock
  assertion fails.
- **L1 (22 message mutants) + E1–E11 (56 cosmetic/log mutants):** recommend a mutmut exclusion
  rule for log-call arguments rather than writing assertions against them — that would remove 78 of
  the 138 survivors (all 56 EQUIVALENT + 22 LOW-VALUE) as non-actionable noise and is the
  highest-leverage change to the score.
