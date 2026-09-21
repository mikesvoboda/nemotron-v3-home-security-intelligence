# WP4.4 Triage Dossier — backend/services/worker_supervisor.py

Wave: worker_supervisor | Date: 2026-09-18 | **UNVERIFIED — no tests were run** (live mutation run owns the machine; read-only triage per harness constraint).

- Survivors: **190** / 650 keys (303 killed, 157 uncheck, 190 exit_code 0)
- All diffs via `mutmut show` (direct `.venv/bin/mutmut`, read-only); raw dump `/tmp/wp25/wp44-triage/ws_diffs.txt` (190/190 keys), cluster map `/tmp/wp25/wp44-triage/ws_cluster_map.json`
- Covering test file (essentially the only one): `backend/tests/unit/services/test_worker_supervisor.py` (1742 lines; `tests_by_mangled_function_name` also lists `backend/tests/unit/services/test_xclip_loader.py` only for `get_worker_supervisor`). `asyncio_mode=auto` — drafted async tests need no decorator.
- Module source: `backend/services/worker_supervisor.py` — key regions: `WorkerInfo.to_dict` 168-190, `start` 356-379, `stop` 381-418, `_monitor_loop` 486-518, `_check_worker_heartbeat` 520-559, `_handle_stuck_worker` 561-609, `_handle_crashed_worker` 611-708, `stop_worker` 1056-1085, `restart_worker_task` 1087-1129, `get_worker_supervisor` 1136-1161.

## Totals

| Classification | Count |
|---|---|
| TEST-GAP | 73 |
| EQUIVALENT | 69 |
| LOW-VALUE | 48 |
| **Total** | **190** |

## Per-cluster table

| # | Cluster | Count | Class | Pattern | Example keys (fn__num) |
|---|---|---|---|---|---|
| 1 | LOG-TEXT | 60 | EQUIVALENT | logger arg → None / XX-wrapped / case / lowercase in `start`, `stop`, `_monitor_loop`, `unregister_worker`, `_handle_*`, `*_worker` control methods (e.g. `start__1` warning→None, `stop__36`, `_check_worker_heartbeat__17`) | start__1, stop__36, _handle_crashed_worker__28 |
| 2 | METRIC-ARG-FAILED | 18 | LOW-VALUE | `_handle_crashed_worker` metrics calls: `worker_name`→None, `reason`→None, `duration_seconds`→None, arg removed, `restart_duration = +` flip (`__92`: `monotonic() + start` garbage duration). Helpers swallow nothing but never raise on None labels → survived; observability-only | _handle_crashed_worker__93, __92, __95 |
| 3 | METRIC-ARG-STUCK | 12 | LOW-VALUE | `_handle_stuck_worker` `record_worker_crash`/`set_worker_status`/`set_pipeline_worker_state` arg→None / arg dropped. `__26`/`__30` (`status=None`) raise AttributeError inside the handler but `_monitor_loop`'s broad `except Exception` swallows it → survived (note swallowed-exception hazard) | _handle_stuck_worker__26, __23 |
| 4 | FAILED-PAYLOAD | 11 | TEST-GAP | `_handle_crashed_worker` give-up path: broadcast service name→None (`__29`), message→None (`__31`), positional shifts (`__34,__42`), history event `worker_name=None`/`attempt=None`/`status="XXfailedXX"/"FAILED"`/text-case (`__35-__38,__43,__44`), broadcast status-positional shift (`__67`). Tests check FAILED **status** only, never the payloads | _handle_crashed_worker__35, __44, __67 |
| 5 | METRIC-TEXT | 8 | LOW-VALUE | metric state string case/XX only: `set_pipeline_worker_state(name,"XXfailedXX"/"FAILED"/"XXrestartingXX"/"RESTARTING"/"XXstoppedXX"/"STOPPED"/"XXcrashedXX"/"CRASHED")` (stop__27/28, crashed__16/17/62/63, stuck__33/34) | _handle_crashed_worker__16 |
| 6 | SINGLETON-ARGS | 8 | TEST-GAP | `get_worker_supervisor` drops/None's `config`/`broadcaster`/`on_restart`/`on_failure` at the construction call (`__3-__10`). Singleton tests only call it with NO args — args never flow through any test | _get_worker_supervisor__3, __10 |
| 7 | STUCK-STATE | 6 | TEST-GAP | `_handle_stuck_worker` state clobbers: `error_msg=None` (`__4`), `last_crashed_at=None` (`__16`), naive `datetime.now(None)` (`__17`), `worker.error=None` (`__18`), `missed_heartbeat_count=None/1` (`__19/__20`). `test_stuck_worker_auto_restart` only asserts call_count/status — never these fields | _handle_stuck_worker__4, __18, __20 |
| 8 | STUCK-BROADCAST | 6 | TEST-GAP | stuck→`_broadcast_status(name,CRASHED,error_msg)` name→None (`__35`), status→None (`__36`), message→None (`__37`), positional shifts (`__38,__39,__40`). No test inspects a stuck-cycle broadcast | _handle_stuck_worker__35, __38 |
| 9 | SW-BROADCAST | 6 | TEST-GAP | `stop_worker` broadcast name→None (`__15`), status→None (`__17`), message→None/arg-removed/text-case (`__17,__20-__23`). `test_stop_worker_manually` asserts status enum only | stop_worker__15, __21 |
| 10 | METRIC-ARG-STOP | 5 | LOW-VALUE | `stop()` metrics: `worker_name`→None (`__19,__23,__29`), `uptime` −1.0→+1.0/−2.0 (`__33,__34`) | stop__19, __33 |
| 11 | START-TASKNAME | 4 | TEST-GAP | `start()`: `create_task(..., name="worker-supervisor")` name→None / arg-removed / text-case (`__14,__16,__17,__18`). NEM-5057 debug-name never asserted | start__14, __16 |
| 12 | STUCK-CANCEL-SWALLOWED | 4 | EQUIVALENT | mutations inside stuck-cancel `try/except Exception: pass`: `shield(None)`, `shield(task)` dropped, `wait_for()` args removed (`__9,__11,__12,__13`) → TypeError always caught → identical observable behavior | _handle_stuck_worker__12 |
| 13 | MANUAL-TASKGUARD | 4 | TEST-GAP | `stop_worker`/`restart_worker_task` task-guard `and`→`or`/`is None and`/`.done()` flips (`stop_worker__6,__7,__8`, `restart_worker_task__6`): with a **never-started** worker (task None) `or`-flips short-circuit into `None.done()` → AttributeError; never exercised (tests always stop a running worker) | stop_worker__6, restart_worker_task__6 |
| 14 | MANUAL-STATE | 4 | TEST-GAP | manual restart/stop state: `stop_worker` `worker.task=None→""` (`__10`, later pool-counts crash on `"".done()`), `restart_worker_task` `circuit_open=None/True`, `error=None→""` (`__11,__12,__13`). `test_restart_worker_task_manually` checks restart_count only | stop_worker__10, restart_worker_task__12 |
| 15 | STOP-STATE-CLOBBER | 3 | TEST-GAP | `stop()`: `_running=False→None`, `_monitor_task=None→""`, `worker.task=None→""` (`__10,__13,__18`). `assert not is_running` passes on None | stop__10, __18 |
| 16 | STOP-TASKGUARD | 3 | TEST-GAP | `stop()` per-worker guard `and`→`or`/`is None and`/`done()` (`__14,__15,__16`) → `None.cancel()/None.done()` AttributeError for never-started workers | stop__14, __16 |
| 17 | TODICT-TIMESTAMPS | 2 | TEST-GAP | `to_dict`: `if (self.last_started_at) and False else None` (`__15`), same `last_crashed_at` (`__19`) → serialized timestamps silently vanish; existing to_dict tests assert these fields **only when None** | to_dict__15, __19 |
| 18 | HB-THRESHOLD | 2 | TEST-GAP | `_check_worker_heartbeat`: `threshold > 0`→`> 1` (`__21`, disable-threshold=1 never restarts), `count >= threshold`→`>` (`__22`, one extra miss). `test_stuck_worker_threshold_disabled` only covers threshold=0 | _check_worker_heartbeat__21, __22 |
| 19 | STUCK-CANCEL-TIMEOUT | 2 | LOW-VALUE | `wait_for(..., timeout=2.0)`→None/3.0 (`__10,__14`). Only diverges for a never-cancelling task; parameter-capture could kill, low payoff | _handle_stuck_worker__10 |
| 20 | SUCCESS-EVENT-ERROR | 2 | TEST-GAP | `_handle_crashed_worker` success history: `error=worker.error→None` (`__103`) and arg dropped (`__107`). `test_get_restart_history_after_restart` asserts status/attempt but never `error` | _handle_crashed_worker__103, __107 |
| 21 | METRIC-IDLE-DEFLATE | 2 | EQUIVALENT | `_update_worker_pool_metrics`: `idle`→None / arg dropped (`__4,__7`) → helper recomputes `idle = max(0, active-busy)` → identical values | _update_worker_pool_metrics__4 |
| 22 | METRIC-ARG-POOL | 2 | LOW-VALUE | `update_worker_pool_metrics(busy, idle)` / `(active, idle)` positional misplace active/busy (`__5,__6`) → wrong gauge values; unasserted metric plumbing | _update_worker_pool_metrics__5 |
| 23 | MANUAL-HISTORY-ATTEMPT | 2 | TEST-GAP | manual-restart history `attempt=0→None/1` (`__16,__23`); history test checks status/error only | restart_worker_task__16, __23 |
| 24 | STOP-GUARD | 1 | TEST-GAP | `stop()`: `if self._monitor_task is not None:` → `is None` (`__12`) → monitor task left un-cancelled + handle left set after stop | stop__12 |
| 25 | MONITOR-SLEEP | 1 | TEST-GAP | `_monitor_loop`: `await asyncio.sleep(self._config.check_interval)`→`sleep(None)` (`__13`) → TypeError each cycle, swallowed by the loop's own except → silent error-loop; killable via caplog | _monitor_loop__13 |
| 26 | MONITOR-BREAK-RETURN | 1 | EQUIVALENT | `except CancelledError: break`→`return` (`__18`) — only skips the trailing "Monitor loop stopped" log | _monitor_loop__18 |
| 27 | HB-DISABLED-RET | 1 | TEST-GAP | `_check_worker_heartbeat` disabled-path `return False`→`True` (`__2`) → forces restart of EVERY running worker when heartbeat checks disabled. `test_heartbeat_check_disabled` checks missed-count only, never the return value | _check_worker_heartbeat__2 |
| 28 | HB-NONE-GUARD | 1 | TEST-GAP | `worker is None or last_heartbeat_at is None` → `and` (`__5`) → aware-minus-naive/None TypeError path for heartbeat-less workers; no test passes a worker with `last_heartbeat_at=None` | _check_worker_heartbeat__5 |
| 29 | HB-BOUNDARY | 1 | TEST-GAP | `seconds_since > timeout` → `>=` (`__12`) off-by-one at exact boundary; never asserted at equality | _check_worker_heartbeat__12 |
| 30 | STUCK-GUARD-EQUIV | 1 | EQUIVALENT | `_handle_stuck_worker` task-guard `and`→`or` (`__6`): reachable states always have a live/done task; done→cancel is a no-op, None-task unreachable (stuck only fires for RUNNING workers with tasks) | _handle_stuck_worker__6 |
| 31 | CRASH-THRESHOLD | 1 | TEST-GAP | `_handle_crashed_worker`: `restart_count >= max_restarts` → `>` (`__2`) → one EXTRA restart past the cap. `test_max_restarts_exceeded` asserts `restart_count >= 2` (mutant gives 3 — passes) | _handle_crashed_worker__2 |
| 32 | RESTART-STATUS-TRANSIENT | 1 | TEST-GAP | `worker.status = WorkerStatus.RESTARTING` → `None` (`__53`): status polls during backoff return None (frontend status break); no test reads status mid-backoff | _handle_crashed_worker__53 |
| 33 | CB-RESTART-ATTEMPT | 1 | TEST-GAP | `on_restart(name, restart_count + 1, ...)` → `+ 2` (`__79`); callback test asserts `attempt >= 1` — too weak | _handle_crashed_worker__79 |
| 34 | HB-NAIVE-DT | 1 | TEST-GAP | `record_heartbeat`: `datetime.now(UTC)` → `now(None)` naive stamp (`__7`) → later `aware - naive` TypeError inside heartbeat check (swallowed by monitor). Test asserts only `is not None` | record_heartbeat__7 |
| 35 | POOL-COUNTS-GUARD | 1 | TEST-GAP | `get_worker_pool_counts` busy-guard `and`→`or` (`__9`) → busy counted for finished tasks → busy>idle skew; live-task tests can't distinguish | get_worker_pool_counts__9 |
| 36 | BACKOFF-STATIC-LE1 | 1 | EQUIVALENT | `_calculate_backoff_static`: `restart_count <= 0` → `<= 1` (`__2`) — for count==1 both paths yield `base` (2⁰·base); provably equivalent | _calculate_backoff_static__2 |
| 37 | METRIC-ARG-MANUAL | 1 | LOW-VALUE | `stop_worker` `set_worker_status(name→None, ...)` (`__11`) | stop_worker__11 |

**Latent source bug noticed while triaging (not a mutant):** `_handle_stuck_worker` line 603 calls `record_worker_crash(name, error_msg)` positionally — `record_worker_crash(worker_name, worker_type=None, exit_code=None, error=None)`, so the stuck reason lands in the **worker_type** label, not `error`. The crash path elsewhere uses `record_worker_crash(name, error=str(e))` keyword. Worth a fix alongside the tests.

## Drafted tests (UNVERIFIED - not yet run red/green)

Append to `backend/tests/unit/services/test_worker_supervisor.py`. TDD procedure for each: run against the mutant source copy → the marked assertion(s) fail on the mutant diff; run against original → pass.

### Draft 1 — lifecycle state exactness (kills STOP-STATE-CLOBBER, STOP-GUARD, STOP-TASKGUARD, START-TASKNAME; caplog kills MONITOR-SLEEP)

```python
class TestWP44LifecycleExactState:
    """WP4.4: exact lifecycle state + monitor-task identity (kills stop/start state and guard mutants)."""

    async def test_monitor_task_named_and_stop_clears_state_exactly(
        self, supervisor: WorkerSupervisor, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Monitor task carries the NEM-5057 debug name; stop() clears state exactly (not falsy-None)."""
        import logging

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("w1", worker)
        with caplog.at_level(logging.ERROR):
            await supervisor.start()
            try:
                assert supervisor._monitor_task is not None
                assert supervisor._monitor_task.get_name() == "worker-supervisor"  # kills start__14/16/17/18
                await asyncio.sleep(0.25)
                # monitor loop must not be raising internally every cycle (kills _monitor_loop__13 sleep(None))
                assert "Error in monitor loop" not in caplog.text
            finally:
                await supervisor.stop()

        assert supervisor.is_running is False  # kills stop__10 (_running = None)
        assert supervisor._monitor_task is None  # kills stop__12 (guard inverted) and stop__13 (task = "")
        info = supervisor.get_worker_info("w1")
        assert info is not None
        assert info.status == WorkerStatus.STOPPED
        assert info.task is None  # kills stop__18 (worker.task = "")

    async def test_stop_with_never_started_worker_does_not_raise(
        self, supervisor: WorkerSupervisor
    ) -> None:
        """stop() must tolerate workers whose task is None (kills stop__14/15/16 guard flips)."""

        async def worker() -> None:
            pass

        await supervisor.start()  # no workers registered yet
        await supervisor.register_worker("late_worker", worker)  # never started: task stays None
        await supervisor.stop()  # original: guard skips; and→or mutant: None.done() AttributeError
        assert supervisor.worker_count == 1
```

### Draft 2 — heartbeat check semantics (kills HB-DISABLED-RET, HB-NONE-GUARD, HB-BOUNDARY, HB-THRESHOLD, HB-NAIVE-DT)

```python
class TestWP44HeartbeatCheckSemantics:
    """WP4.4: _check_worker_heartbeat return contract at boundaries (NEM-4148)."""

    async def test_returns_false_when_disabled_or_unknown(self, mock_broadcaster: AsyncMock) -> None:
        """Disabled config and unknown/heartbeat-less workers must return exactly False (kills __2, __5)."""
        from datetime import UTC, datetime, timedelta

        config = SupervisorConfig(check_interval=0.1, heartbeat_check_enabled=False)
        sup = WorkerSupervisor(config=config, broadcaster=mock_broadcaster)

        async def worker() -> None:
            pass

        await sup.register_worker("w", worker)
        sup._workers["w"].last_heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
        assert sup._check_worker_heartbeat("w") is False  # kills _check_worker_heartbeat__2 (return True)

        # heartbeat-less worker: __5 (`or`→`and`) falls through to aware-minus-None TypeError
        await sup.register_worker("no_hb", worker)  # heartbeat_check disabled here; use enabled sup below
        config2 = SupervisorConfig(check_interval=0.1)
        sup2 = WorkerSupervisor(config=config2, broadcaster=mock_broadcaster)
        await sup2.register_worker("no_hb", worker)
        sup2._workers["no_hb"].last_heartbeat_at = None
        assert sup2._check_worker_heartbeat("no_hb") is False  # kills _check_worker_heartbeat__5

    async def test_threshold_boundary_and_off_by_one(self, mock_broadcaster: AsyncMock) -> None:
        """Exact-timeout is NOT a miss; restart fires AT threshold, not after (kills __12, __21, __22)."""
        from datetime import UTC, datetime, timedelta

        config = SupervisorConfig(
            check_interval=0.1,
            default_heartbeat_timeout=10.0,
            missed_heartbeat_restart_threshold=2,
        )
        sup = WorkerSupervisor(config=config, broadcaster=mock_broadcaster)

        async def worker() -> None:
            pass

        await sup.register_worker("w", worker)
        # exactly at timeout -> strictly-greater means NOT overdue
        sup._workers["w"].last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=10)
        assert sup._check_worker_heartbeat("w") is False  # kills __12 (>=)
        assert sup._workers["w"].missed_heartbeat_count == 0

        # overdue: first miss counts but is below threshold
        sup._workers["w"].last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=11)
        assert sup._check_worker_heartbeat("w") is False
        assert sup._workers["w"].missed_heartbeat_count == 1
        # second miss REACHES threshold -> must restart (kills __22: `count > threshold`)
        assert sup._check_worker_heartbeat("w") is True

        # threshold=1: first miss must restart (kills __21: `threshold > 1` disables threshold-1 configs)
        config1 = SupervisorConfig(
            check_interval=0.1,
            default_heartbeat_timeout=1.0,
            missed_heartbeat_restart_threshold=1,
        )
        sup1 = WorkerSupervisor(config=config1, broadcaster=mock_broadcaster)
        await sup1.register_worker("w1", worker)
        sup1._workers["w1"].last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=2)
        assert sup1._check_worker_heartbeat("w1") is True  # kills _check_worker_heartbeat__21

    async def test_record_heartbeat_is_timezone_aware(self, supervisor: WorkerSupervisor) -> None:
        """record_heartbeat stamp must be tz-aware or heartbeat math raises (kills record_heartbeat__7)."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("w", worker)
        assert supervisor.record_heartbeat("w") is True
        info = supervisor.get_worker_info("w")
        assert info is not None
        assert info.last_heartbeat_at is not None
        assert info.last_heartbeat_at.tzinfo is not None  # kills naive datetime.now(None)
        assert info.last_heartbeat_at.utcoffset() is not None
```

### Draft 3 — crash/restart/failure payloads (kills CRASH-THRESHOLD, FAILED-PAYLOAD, CB-RESTART-ATTEMPT, SUCCESS-EVENT-ERROR, RESTART-STATUS-TRANSIENT)

```python
class TestWP44CrashRestartPayloads:
    """WP4.4: max-restart cap is exact and FAILED/history/broadcast payloads are asserted."""

    async def test_max_restarts_exact_cap_and_failure_payload(
        self, mock_broadcaster: AsyncMock
    ) -> None:
        """restart_count lands EXACTLY on max_restarts; give-up broadcast/history carry the name+message."""
        restart_calls: list[int] = []

        async def on_restart(name: str, attempt: int, error: str | None) -> None:
            restart_calls.append(attempt)

        config = SupervisorConfig(
            check_interval=0.05,
            default_max_restarts=2,
            default_backoff_base=0.02,
            default_backoff_max=0.05,
        )
        sup = WorkerSupervisor(config=config, broadcaster=mock_broadcaster, on_restart=on_restart)

        calls = 0

        async def always_crashes() -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("boom")

        await sup.register_worker("w", always_crashes, max_restarts=2, backoff_base=0.02)
        await sup.start()
        try:
            await asyncio.sleep(1.2)  # all attempts settle

            info = sup.get_worker_info("w")
            assert info is not None
            assert info.status == WorkerStatus.FAILED
            assert info.restart_count == 2  # EXACTLY max (kills _handle_crashed_worker__2 `>=`→`>`)
            assert calls == 3  # initial + exactly 2 restarts
            assert info.circuit_open is True
            assert restart_calls == [1, 2]  # kills __79 (+1→+2)

            failed_events = [e for e in sup.get_restart_history(worker_name="w") if e["status"] == "failed"]
            assert len(failed_events) == 1
            ev = failed_events[0]
            assert ev["worker_name"] == "w"  # kills __35 (worker_name=None)
            assert ev["attempt"] == 2  # kills __36 (attempt=None)
            assert "Exceeded max restarts (2)" in ev["error"]  # kills __38 (error=None)

            failed_bcasts = [
                c[0][0]["data"]
                for c in mock_broadcaster.broadcast_service_status.call_args_list
                if c[0][0]["data"]["status"] == "failed"
            ]
            assert failed_bcasts
            assert all(d["service"] == "worker:w" for d in failed_bcasts)  # kills __29/__67
            assert any(d["message"] and "Exceeded max restarts (2)" in d["message"] for d in failed_bcasts)  # kills __31/__34
        finally:
            await sup.stop()

    async def test_success_history_event_keeps_error_and_status_transitions_restart(
        self, mock_broadcaster: AsyncMock
    ) -> None:
        """Success restart event keeps the triggering error; status is RESTARTING during backoff."""
        statuses_during_restart: list[WorkerStatus | None] = []

        async def on_restart(name: str, attempt: int, error: str | None) -> None:
            # called after status is set to RESTARTING and before the backoff sleep
            statuses_during_restart.append(sup.get_worker_status(name))

        config = SupervisorConfig(
            check_interval=0.05, default_max_restarts=3, default_backoff_base=0.05, default_backoff_max=0.1
        )
        sup = WorkerSupervisor(config=config, broadcaster=mock_broadcaster, on_restart=on_restart)

        call_count = 0

        async def flaky_worker() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First crash")
            await asyncio.sleep(10)  # cancelled

        await sup.register_worker("w", flaky_worker, backoff_base=0.05)
        await sup.start()
        try:
            await asyncio.sleep(0.6)

            assert statuses_during_restart == [WorkerStatus.RESTARTING]  # kills __53 (status=None)

            succ = [e for e in sup.get_restart_history(worker_name="w") if e["status"] == "success"]
            assert len(succ) >= 1
            assert succ[0]["attempt"] == 1
            assert succ[0]["error"] == "First crash"  # kills __103/__107 (error dropped)
        finally:
            await sup.stop()
```

### Draft 4 — stuck worker state + broadcast (kills STUCK-STATE, STUCK-BROADCAST)

```python
class TestWP44StuckWorkerPayload:
    """WP4.4: stuck handler records real error/timestamps and broadcasts a well-formed crashed event."""

    async def test_stuck_worker_marked_crashed_with_error_and_broadcast(
        self, mock_broadcaster: AsyncMock
    ) -> None:
        """After force-cancel, worker fields + broadcast payload describe the stuck event."""
        from datetime import UTC, datetime, timedelta

        config = SupervisorConfig(
            check_interval=0.05,
            default_heartbeat_timeout=0.05,
            missed_heartbeat_restart_threshold=1,
            default_backoff_base=20.0,  # keep worker parked in CRASHED long enough to inspect fields
            default_backoff_max=20.0,
        )
        sup = WorkerSupervisor(config=config, broadcaster=mock_broadcaster)

        async def worker() -> None:
            await asyncio.sleep(10)  # will be force-cancelled

        await sup.register_worker("w", worker)
        await sup.start()
        try:
            sup._workers["w"].last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=5)
            for _ in range(40):  # up to ~2s: stuck handler fires
                await asyncio.sleep(0.05)
                if sup.get_worker_status("w") in (WorkerStatus.CRASHED, WorkerStatus.RESTARTING):
                    break

            info = sup.get_worker_info("w")
            assert info is not None
            assert info.status in (WorkerStatus.CRASHED, WorkerStatus.RESTARTING)
            assert info.last_crashed_at is not None
            assert info.last_crashed_at.tzinfo is not None  # kills __17 (naive stamp)
            assert info.error is not None  # kills __4/__18 (error_msg/ error=None)
            assert "stuck" in info.error.lower() and "missed" in info.error.lower()
            assert info.missed_heartbeat_count == 0  # kills __19/__20

            crashed_bcasts = [
                c[0][0]["data"]
                for c in mock_broadcaster.broadcast_service_status.call_args_list
                if c[0][0]["data"]["status"] == "crashed"
            ]
            assert crashed_bcasts
            assert any(d["service"] == "worker:w" for d in crashed_bcasts)  # kills __35/__38/__39
            assert any(
                d["message"] and "stuck" in d["message"].lower() for d in crashed_bcasts
            )  # kills __37/__40 (message None/shifted)
        finally:
            await sup.stop()
```

### Draft 5 — manual control state + history + broadcast (kills MANUAL-TASKGUARD, MANUAL-STATE, MANUAL-HISTORY-ATTEMPT, SW-BROADCAST)

```python
class TestWP44ManualControlPayloads:
    """WP4.4: manual stop/restart guard None tasks and emit exact state/history/broadcast payloads."""

    async def test_manual_stop_and_restart_on_never_started_worker(
        self, supervisor: WorkerSupervisor
    ) -> None:
        """stop_worker/restart_worker_task must tolerate task=None (kills stop_worker__6/7/8, restart_worker_task__6)."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("w", worker)  # never started: task is None
        assert await supervisor.stop_worker("w") is True
        assert await supervisor.restart_worker_task("w") is False or True  # returns True and must not raise
        # (the real assertion is "did not raise": and→or guard flips hit None.done() → AttributeError)

    async def test_manual_stop_broadcast_and_task_clear_payload(
        self, supervisor: WorkerSupervisor, mock_broadcaster: AsyncMock
    ) -> None:
        """stop_worker clears task to None and broadcasts stopped payload exactly."""

        async def worker() -> None:
            await asyncio.sleep(10)

        await supervisor.register_worker("w", worker)
        await supervisor.start_worker("w")
        await asyncio.sleep(0.1)

        assert await supervisor.stop_worker("w") is True
        info = supervisor.get_worker_info("w")
        assert info is not None
        assert info.status == WorkerStatus.STOPPED
        assert info.task is None  # kills stop_worker__10 (task = "")

        stopped = [
            c[0][0]["data"]
            for c in mock_broadcaster.broadcast_service_status.call_args_list
            if c[0][0]["data"]["status"] == "stopped"
        ]
        assert stopped
        assert stopped[-1]["service"] == "worker:w"  # kills __15 (name=None) / __17 status shift
        assert stopped[-1]["message"] == "Manually stopped"  # kills __17/__20/__21/__22/__23

    async def test_manual_restart_resets_error_circuit_and_attempt(
        self, supervisor: WorkerSupervisor
    ) -> None:
        """restart_worker_task clears error/circuit and records attempt=0 manual event."""

        async def worker() -> None:
            await asyncio.sleep(10)

        await supervisor.register_worker("w", worker)
        await supervisor.start_worker("w")
        await asyncio.sleep(0.1)

        sup_w = supervisor._workers["w"]
        sup_w.status = WorkerStatus.FAILED
        sup_w.restart_count = 4
        sup_w.circuit_open = True
        sup_w.error = "previous error"

        assert await supervisor.restart_worker_task("w") is True
        await asyncio.sleep(0.1)

        info = supervisor.get_worker_info("w")
        assert info is not None
        assert info.restart_count == 0
        assert info.circuit_open is False  # kills restart_worker_task__11/__12
        assert info.error is None  # kills __13 (error = "")

        hist = supervisor.get_restart_history(worker_name="w")
        assert hist[0]["attempt"] == 0  # kills __16 (None) / __23 (1)
        assert hist[0]["status"] == "success"
```

### Draft 6 — singleton arg pass-through + to_dict timestamps (kills SINGLETON-ARGS, TODICT-TIMESTAMPS)

```python
class TestWP44SingletonAndSerialization:
    """WP4.4: get_worker_supervisor forwards constructor args; to_dict serializes timestamps."""

    def test_get_worker_supervisor_forwards_all_constructor_args(self) -> None:
        """Args given on first call must land on the instance (kills _get_worker_supervisor__3-__10)."""
        reset_worker_supervisor()
        config = SupervisorConfig(check_interval=12.5, default_max_restarts=9)
        broadcaster = AsyncMock()

        async def on_restart(name: str, attempt: int, error: str | None) -> None:
            pass

        async def on_failure(name: str, error: str | None) -> None:
            pass

        sup = get_worker_supervisor(
            config=config, broadcaster=broadcaster, on_restart=on_restart, on_failure=on_failure
        )
        assert sup._config is config  # kills __3 (config=None) / __7 (dropped)
        assert sup._broadcaster is broadcaster  # kills __4 / __8
        assert sup._on_restart is on_restart  # kills __5 / __9
        assert sup._on_failure is on_failure  # kills __6 / __10

    def test_worker_info_to_dict_serializes_all_timestamps(self) -> None:
        """last_started_at/last_crashed_at serialize to ISO strings when set (kills to_dict__15/__19)."""
        from datetime import UTC, datetime

        started = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        crashed = datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC)
        heartbeat = datetime(2026, 1, 2, 3, 4, 7, tzinfo=UTC)

        info = WorkerInfo(
            name="w",
            factory=AsyncMock(),
            last_started_at=started,
            last_crashed_at=crashed,
            last_heartbeat_at=heartbeat,
        )
        d = info.to_dict()
        assert d["last_started_at"] == started.isoformat()  # kills `and False` → None
        assert d["last_crashed_at"] == crashed.isoformat()
        assert d["last_heartbeat_at"] == heartbeat.isoformat()
```

## Notes for WP4.4 close-out

- Draft 1's caplog assertion depends on backend logger propagation; if `caplog.text` stays empty, drop that one assert — it's the only line with environment risk.
- Draft 5 test 1: rewrite the `False or True` placeholder line as a bare `await supervisor.stop_worker("w")` / `await supervisor.restart_worker_task("w")` (the kill signal is the AttributeError on the mutant, not a value). Left visible deliberately — remove before merge.
- LOW-VALUE metric clusters (48 survivors): the module's test file never patches the `backend.core.metrics` helpers; recommend the team add ONE parameter-capture test (monkeypatch `set_worker_status`/`set_pipeline_worker_state`/`record_worker_*`) if Prometheus label identity is considered contract — that single test would convert ~30 of the METRIC-ARG survivors from noise to kills, but the baseline treats metric plumbing as out of scope, hence LOW-VALUE here.
- Fix `record_worker_crash(name, error_msg)` → `record_worker_crash(name, error=error_msg)` at worker_supervisor.py:603 while touching this module.
