# TARGET-MODULE: backend.services.worker_supervisor
"""Battery AC — campaign #27 batch-38 killers for worker_supervisor.

Campaign #27 (ladder to 85%): the 243 survivor keys sit in the lifecycle
machinery (_handle_crashed_worker 44, _handle_stuck_worker 35, stop 26,
_run_worker 22, start 16, _start_worker 14, _monitor_loop 14, stop_worker
13, _broadcast_status 10, restart_worker_task 8, x_get_worker_supervisor
8, _check_worker_heartbeat 7, ...). The shipped suite exercises the
behavior (restarts happen, statuses transition, history trims) but never
pins WHAT WAS EMITTED: ~110 log-message arms (msg -> None), ~60
metrics-call arms (name -> None, state-string case flips, arg drops),
payload-key flips, control-flow boundary flips and task-guard conjunction
flips. This battery pins:

  * every backend.core.metrics call as its RAW (args, kwargs) tuple via
    CallSpies swapped into the ws module namespace - the real gauges
    collapse "FAILED" to the same state value as "failed"
    (PIPELINE_WORKER_STATE_VALUES.get(state.lower())) and sanitize
    names, so gauge-level observation could never kill the case-flip
    arms; the swap also keeps this file off the real Prometheus registry;
  * the WebSocket payload as ONE dict (type/data slots + exact data
    equality + sorted(ev) key census + "+00:00" tz offset on the
    timestamp) against a broadcaster fake recording call tuples;
  * log records on the FULL msgs() sequence (msg equality, never
    substring; the deterministic f-string values "attempt 2/5",
    "last: 45.0s ago", "Exceeded max restarts (2)" are themselves
    pins) plus exc_info IDENTITY (a tuple) on the crash record;
  * task-guard conjunctions via REAL asyncio tasks in three polarities
    (None / already-done / running): the or/None flips raise (await
    None / None.cancel / .done() on None) and the done-arm flips leave
    the real task NOT cancelled - observable via task.cancelled();
  * the stuck-worker force-cancel branch via a task that IGNORES its
    first cancellation for 3.5s: the orig wait_for(shield(task), 2.0)
    times out at ~2.0s and the shield keeps the task PENDING - pinning
    handler wall-clock in (1.9, 2.5) and task-not-done kills the
    timeout=None/deleted arms (wait until done ~3.5s), the
    shield-dropped arms (TypeError -> debug record) and timeout=3.0;
  * the >=/> boundaries as real polarities: restart_count EXACTLY ==
    max_restarts, missed count EXACTLY == threshold, threshold EXACTLY
    1 (disable-comparison arm) and 0 (disabled), plus a sentinel
    heartbeat_timeout (__lt__ False / __le__ True) for the overdue
    comparison itself;
  * history as whole event dicts (worker_name/attempt/status/error
    slots; timestamp asserted tz-aware) and WorkerInfo/RestartEvent
    to_dict as WHOLE dicts with the isoformat/None polarity both ways;
  * x_get_worker_supervisor by swapping a required-kwargs Spy class
    into ws.WorkerSupervisor - every kwarg (None-swap AND deletion)
    lands in the recorded kwargs dict or raises TypeError.

Style notes for the b30 sweep (module-level sync test_* only, zero args):
async paths run under asyncio.run INSIDE each test; fakes are plain
classes with REQUIRED positional parameters (arg-deletion mutants surface
as TypeErrors, never silent defaults); WorkerInfo/RestartEvent are real
dataclasses; workers are built DIRECTLY into sup._workers/_restart_locks
so handler tests do not depend on register_worker internals.

Honesty ledger (EQUIV candidates REGISTERED BY CONSTRUCTION; the sweep
verdict + the per-key probes are the evidence - a construction claim is
not a verdict claim).

  Not equivalent, KILLABLE - the arms this battery supplies:
  - every log None/XX/CASE arm everywhere: full msgs() sequence equality
    per scenario.
  - every metrics name-None / state-XX/CASE / count-perturbed /
    arg-dropped arm: raw spy tuples (the real gauges case-fold, the
    spies do not).
  - _broadcast_status payload key/None/case arms + naive timestamp.
  - the stuck wait_for family m9-m14 (shield None/arg-drop -> TypeError
    -> debug record; timeout None/deleted -> still-pending + elapsed
    pins; timeout=3.0 -> elapsed bound).
  - task-guard or/None/done flips (stop, stop_worker,
    restart_worker_task, pool counts): raise polarities and the
    task-NOT-cancelled pin.
  - boundaries: rc==max (hc m2), count==threshold (ch m22),
    threshold==1 (ch m21) and ==0, overdue-sentinel (ch m12).
  - restart-path attempt strings (m64-66), on_restart rc+2 (m79),
    duration None/sum (m91/92), reason/duration kwargs (m88-98),
    history error/attempt/status slots.
  - x_get_worker_supervisor kwarg None/deletion (required-kwargs Spy).
  - __init__/stop _running=None and _monitor_task="" : identity pins.
  - manual restart circuit_open=None/True and error="" via to_dict's
    whole dict; history attempt None/1 pins.
  - _monitor_loop sleep(None) m13: the loop SURVIVES on
    "Error in monitor loop: ..." every ~check_interval - the orig tail
    msgs is EXACTLY ["Monitor loop stopped"].
  - _monitor_loop m18 (break -> return): skips the tail
    "Monitor loop stopped" - pinned by the lifecycle msgs sequence.
  - the LIVE-TASK restart polarity (authoring-sweep lesson): a CRASHED
    worker whose task is still PENDING (exactly what _handle_stuck_worker
    leaves behind - the shield survives the 2.0s timeout) makes
    _start_worker EARLY-RETURN ("Worker 'w' already running"), so the
    values its fall-through would overwrite stay observable:
    _handle_crashed_worker m53 (`status = RESTARTING` -> None fails
    `w.status is RESTARTING`), m103/m107 (history-event error=worker.error
    -> None/deleted - the event keeps the stuck message under the orig).
    The dead-task round cannot see these three; the live-task round kills
    them.

  EQUIV candidates REGISTERED (construction, not verdict):
  - _calculate_backoff_static m2 (`restart_count <= 0` -> `<= 1`): the
    early return yields `base` and the formula at rc=1 is
    base * 2**(1-1) = base - IDENTICAL; rc=0 takes the early arm in both
    shapes; rc>=2 skips both. No input separates them.
  - _record_restart_event m14 (`len > max` -> `len >= max`): the trim is
    `history[-max:]`, whose result when len == max is the SAME list -
    every length behaves identically under the two comparisons.
  - restart_worker_task m13 (`worker.error = None` -> `""` at the state
    reset): restart_worker_task's pre-cancel AWARDS the task to done
    (cancel + await, even for a cancel-ignoring factory) or it starts
    None, so _start_worker never early-returns and its
    `worker.error = None` overwrites the reset before ANY read (the
    history event passes the literal "Manual restart requested"). The
    assignment is dead under every reachable state.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.services import worker_supervisor as ws
from backend.services.worker_supervisor import (
    RestartEvent,
    SupervisorConfig,
    WorkerInfo,
    WorkerStatus,
)

# ---------------------------------------------------------------------------
# capture / patch helpers (no fixtures - the sweep calls plain functions)
# ---------------------------------------------------------------------------


class RecordList(logging.Handler):
    """Captures EVERY record emitted through ws.logger while active."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def one(self, msg: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.getMessage() == msg]
        assert len(hits) == 1, (msg, [r.getMessage() for r in self.records])
        return hits[0]

    def msgs(self) -> list[str]:
        return [r.getMessage() for r in self.records]


@contextmanager
def logcap():
    cap = RecordList()
    old_level = ws.logger.level
    ws.logger.addHandler(cap)
    ws.logger.setLevel(logging.DEBUG)
    try:
        yield cap
    finally:
        ws.logger.removeHandler(cap)
        ws.logger.setLevel(old_level)


METRIC_NAMES = [
    "record_pipeline_worker_restart",
    "record_worker_crash",
    "record_worker_heartbeat_missed",
    "record_worker_max_restarts_exceeded",
    "record_worker_restart",
    "set_pipeline_worker_consecutive_failures",
    "set_pipeline_worker_state",
    "set_pipeline_worker_uptime",
    "set_worker_status",
    "update_worker_pool_metrics",
]


class CallSpy:
    """Raw (args, kwargs) recorder - module-level call, no fixture."""

    def __init__(self, name: str = "") -> None:
        self.name = name
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append((args, kwargs))

    def one(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        assert len(self.calls) == 1, (self.name, self.calls)
        return self.calls[0]


@contextmanager
def metric_spies():
    """Swap every imported metrics fn in the ws namespace for a CallSpy.

    Mutant bodies resolve these through the (mutant) module globals, so
    the swap observes the RAW call arguments - which is what the
    case-flip arms need: the real gauges case-fold state strings."""
    olds = {n: getattr(ws, n) for n in METRIC_NAMES}
    spies = {n: CallSpy(n) for n in METRIC_NAMES}
    for n, s in spies.items():
        setattr(ws, n, s)
    try:
        yield spies
    finally:
        for n, o in olds.items():
            setattr(ws, n, o)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _cleanup(*tasks: Any) -> None:
    for t in tasks:
        if t is not None and not t.done():
            t.cancel()
        if t is not None:
            with contextlib.suppress(BaseException):
                await t


async def _done_task() -> None:
    return None


async def forever() -> None:
    try:
        await asyncio.sleep(3600)  # cancelled by the test's _cleanup
    except asyncio.CancelledError:
        pass


async def stubborn() -> None:
    """Ignores its FIRST cancellation by sleeping 3.5s more (stuck)."""
    try:
        await asyncio.sleep(3600)  # cancelled - and the task IGNORES it
    except asyncio.CancelledError:
        await asyncio.sleep(3.5)  # cancelled again by _cleanup


async def _idle_factory() -> None:
    await asyncio.sleep(3600)  # cancelled via supervisor stop/cancel


# ---------------------------------------------------------------------------
# fakes (REQUIRED positional slots: arg-deletion mutants -> TypeError)
# ---------------------------------------------------------------------------


class FakeBroadcaster:
    def __init__(self, raises: Exception | None = None) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.raises = raises

    async def broadcast_service_status(self, event_data: Any) -> None:
        self.calls.append((event_data,))
        if self.raises is not None:
            raise self.raises


def pin_status_event(call: tuple[Any, ...], service: str, status: str, message: str | None) -> None:
    """Whole-payload pin for one broadcast_service_status call tuple."""
    (ev,) = call
    assert isinstance(ev, dict)
    assert ev["type"] == "service_status"
    assert ev["data"] == {"service": service, "status": status, "message": message}
    assert sorted(ev) == ["data", "timestamp", "type"]
    assert isinstance(ev["timestamp"], str)
    assert ev["timestamp"].endswith("+00:00")


STARTED_AT = datetime(2026, 1, 1, 1, 2, 3, tzinfo=UTC)
CRASHED_AT = datetime(2026, 2, 2, 3, 4, 5, tzinfo=UTC)
HEARTBEAT_AT = datetime(2026, 3, 3, 4, 5, 6, tzinfo=UTC)


def make_info(
    name: str = "w",
    *,
    factory: Any = None,
    task: Any = None,
    status: WorkerStatus = WorkerStatus.STOPPED,
    restart_count: int = 0,
    max_restarts: int = 5,
    backoff_base: float = 0.01,
    backoff_max: float = 60.0,
    error: str | None = None,
    circuit_open: bool = False,
    last_heartbeat_at: Any = HEARTBEAT_AT,
    heartbeat_timeout: float = 1000.0,
    missed_heartbeat_count: int = 0,
) -> WorkerInfo:
    return WorkerInfo(
        name=name,
        factory=factory if factory is not None else _idle_factory,
        task=task,
        status=status,
        restart_count=restart_count,
        max_restarts=max_restarts,
        backoff_base=backoff_base,
        backoff_max=backoff_max,
        error=error,
        circuit_open=circuit_open,
        last_heartbeat_at=last_heartbeat_at,
        heartbeat_timeout=heartbeat_timeout,
        missed_heartbeat_count=missed_heartbeat_count,
    )


CONFIG_FIELDS = frozenset(
    {
        "check_interval",
        "default_max_restarts",
        "default_backoff_base",
        "default_backoff_max",
        "max_restart_history",
        "default_heartbeat_timeout",
        "heartbeat_check_enabled",
        "missed_heartbeat_restart_threshold",
    }
)


def make_sup(**kwargs: Any) -> ws.WorkerSupervisor:
    """Build a supervisor: config-field kwargs -> SupervisorConfig, rest -> ctor."""
    cfg = {k: kwargs.pop(k) for k in list(kwargs) if k in CONFIG_FIELDS}
    return ws.WorkerSupervisor(config=SupervisorConfig(**cfg), **kwargs)


def add_worker(sup: ws.WorkerSupervisor, info: WorkerInfo) -> WorkerInfo:
    sup._workers[info.name] = info
    sup._restart_locks[info.name] = asyncio.Lock()
    return info


# ---------------------------------------------------------------------------
# __init__ / singleton
# ---------------------------------------------------------------------------


def test_init_identity_and_message() -> None:
    with logcap() as cap:
        sup = make_sup()
        assert cap.msgs() == ["WorkerSupervisor initialized: check_interval=5.0s"]
    assert sup._running is False  # m7: None fails identity
    assert sup._monitor_task is None  # m9: "" fails identity
    assert sup.is_running is False


class SpySupervisor:
    """Required-kwargs stand-in: any kwarg deletion raises TypeError."""

    def __init__(
        self,
        config: Any,
        broadcaster: Any,
        on_restart: Any,
        on_failure: Any,
    ) -> None:
        self.kwargs = {
            "config": config,
            "broadcaster": broadcaster,
            "on_restart": on_restart,
            "on_failure": on_failure,
        }


def test_get_worker_supervisor_passes_all_kwargs() -> None:
    cfg = SupervisorConfig(check_interval=1.5)
    bcast = FakeBroadcaster()
    on_r = CallSpy("on_restart")
    on_f = CallSpy("on_failure")
    old_cls = ws.WorkerSupervisor
    ws.reset_worker_supervisor()
    ws.WorkerSupervisor = SpySupervisor  # type: ignore[misc]
    try:
        inst = ws.get_worker_supervisor(
            config=cfg, broadcaster=bcast, on_restart=on_r, on_failure=on_f
        )
        assert inst.kwargs == {
            "config": cfg,
            "broadcaster": bcast,
            "on_restart": on_r,
            "on_failure": on_f,
        }
        assert ws.get_worker_supervisor() is inst  # singleton reused
    finally:
        ws.WorkerSupervisor = old_cls  # type: ignore[misc]
        ws.reset_worker_supervisor()


# ---------------------------------------------------------------------------
# WorkerInfo / RestartEvent to_dict whole-dict
# ---------------------------------------------------------------------------


def test_to_dict_full_both_stamp_polarities() -> None:
    full = make_info(
        "w",
        status=WorkerStatus.RUNNING,
        restart_count=2,
        error="boom",
        circuit_open=True,
    )
    full.last_started_at = STARTED_AT
    full.last_crashed_at = CRASHED_AT
    assert full.to_dict() == {
        "name": "w",
        "status": "running",
        "restart_count": 2,
        "max_restarts": 5,
        "backoff_base": 0.01,
        "backoff_max": 60.0,
        "last_started_at": "2026-01-01T01:02:03+00:00",
        "last_crashed_at": "2026-02-02T03:04:05+00:00",
        "error": "boom",
        "circuit_open": True,
        "last_heartbeat_at": "2026-03-03T04:05:06+00:00",
        "heartbeat_timeout": 1000.0,
        "missed_heartbeat_count": 0,
    }
    bare = make_info("v", status=WorkerStatus.STOPPED)
    bare.last_started_at = None
    bare.last_crashed_at = None
    bare.last_heartbeat_at = None
    got = bare.to_dict()
    assert got["last_started_at"] is None
    assert got["last_crashed_at"] is None  # the SET-stamp round above kills m19
    assert got["last_heartbeat_at"] is None


def test_restart_event_to_dict() -> None:
    ev = RestartEvent(
        worker_name="w", timestamp=STARTED_AT, attempt=3, status="success", error="boom"
    )
    assert ev.to_dict() == {
        "worker_name": "w",
        "timestamp": "2026-01-01T01:02:03+00:00",
        "attempt": 3,
        "status": "success",
        "error": "boom",
    }


# ---------------------------------------------------------------------------
# _broadcast_status
# ---------------------------------------------------------------------------


def test_broadcast_status_payload_shapes() -> None:
    async def go() -> None:
        bcast = FakeBroadcaster()
        sup = make_sup(broadcaster=bcast)
        await sup._broadcast_status("w", WorkerStatus.RUNNING)
        pin_status_event(bcast.calls[0], "worker:w", "running", None)
        await sup._broadcast_status("w2", WorkerStatus.FAILED, "Exceeded max restarts (2)")
        pin_status_event(bcast.calls[1], "worker:w2", "failed", "Exceeded max restarts (2)")

    async def no_broadcaster() -> None:
        sup = make_sup()
        await sup._broadcast_status("w", WorkerStatus.RUNNING)  # silent early return

    run(go())
    run(no_broadcaster())


def test_broadcast_status_failure_warns() -> None:
    async def go() -> None:
        bcast = FakeBroadcaster(raises=RuntimeError("be"))
        sup = make_sup(broadcaster=bcast)
        with logcap() as cap:
            await sup._broadcast_status("w", WorkerStatus.CRASHED, "boom")
        assert cap.msgs() == ["Failed to broadcast worker status: be"]

    run(go())


# ---------------------------------------------------------------------------
# _check_worker_heartbeat
# ---------------------------------------------------------------------------


def test_heartbeat_disabled_returns_false() -> None:
    sup = make_sup(heartbeat_check_enabled=False)
    w = add_worker(sup, make_info("w", status=WorkerStatus.RUNNING))
    with metric_spies() as spies:
        assert sup._check_worker_heartbeat("w") is False  # m2 -> True fails
        assert w.missed_heartbeat_count == 0
        assert spies["record_worker_heartbeat_missed"].calls == []


def test_heartbeat_missing_polarities() -> None:
    sup = make_sup()
    no_hb = add_worker(sup, make_info("w", status=WorkerStatus.RUNNING, last_heartbeat_at=None))
    with metric_spies() as spies:
        # m5 (or -> and) raises: `and` evaluates None.last_heartbeat_at,
        # and the unknown-name branch dereferences the None worker.
        assert sup._check_worker_heartbeat("w") is False
        assert sup._check_worker_heartbeat("ghost") is False
        assert no_hb.missed_heartbeat_count == 0
        assert spies["record_worker_heartbeat_missed"].calls == []


def test_heartbeat_overdue_warning_message() -> None:
    sup = make_sup()
    w = add_worker(
        sup,
        make_info(
            "w",
            status=WorkerStatus.RUNNING,
            last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=45),
            heartbeat_timeout=10.0,  # overdue at 45s
        ),
    )
    with metric_spies() as spies, logcap() as cap:
        assert sup._check_worker_heartbeat("w") is False  # count 1 < threshold 5
    assert w.missed_heartbeat_count == 1
    assert spies["record_worker_heartbeat_missed"].one() == (("w",), {})
    assert cap.msgs() == ["Worker 'w' missed heartbeat #1 (last: 45.0s ago, timeout: 10.0s)"]


def test_heartbeat_threshold_force_rounds() -> None:
    # threshold == 1: m21 (threshold > 1) would never force
    sup = make_sup(missed_heartbeat_restart_threshold=1)
    w1 = add_worker(sup, make_info("a", status=WorkerStatus.RUNNING, missed_heartbeat_count=1))
    w1.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=45)
    w1.heartbeat_timeout = 10.0
    with logcap() as cap1:
        assert sup._check_worker_heartbeat("a") is True
    assert cap1.msgs() == [
        "Worker 'a' missed heartbeat #2 (last: 45.0s ago, timeout: 10.0s)",
        "Worker 'a' exceeded missed heartbeat threshold (2/1), forcing restart",
    ]
    assert w1.missed_heartbeat_count == 2
    # count EXACTLY == threshold: m22 (count > threshold) would not force
    sup2 = make_sup(missed_heartbeat_restart_threshold=2)
    w2 = add_worker(sup2, make_info("b", status=WorkerStatus.RUNNING, missed_heartbeat_count=1))
    w2.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=45)
    w2.heartbeat_timeout = 10.0
    with logcap() as cap2:
        assert sup2._check_worker_heartbeat("b") is True
    assert cap2.msgs() == [
        "Worker 'b' missed heartbeat #2 (last: 45.0s ago, timeout: 10.0s)",
        "Worker 'b' exceeded missed heartbeat threshold (2/2), forcing restart",
    ]
    # threshold == 0 disables forcing
    sup3 = make_sup(missed_heartbeat_restart_threshold=0)
    w3 = add_worker(sup3, make_info("c", status=WorkerStatus.RUNNING))
    w3.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=45)
    w3.heartbeat_timeout = 10.0
    assert sup3._check_worker_heartbeat("c") is False
    assert w3.missed_heartbeat_count == 1


class _OverdueSentinel:
    """`elapsed > timeout` False while `elapsed >= timeout` True (m12)."""

    def __lt__(self, _other: Any) -> bool:
        return False

    def __le__(self, _other: Any) -> bool:
        return True

    def __str__(self) -> str:
        return "sentinel"


def test_heartbeat_overdue_comparison_boundary() -> None:
    sup = make_sup()
    w = add_worker(
        sup,
        make_info(
            "w",
            status=WorkerStatus.RUNNING,
            last_heartbeat_at=datetime.now(UTC),
            heartbeat_timeout=_OverdueSentinel(),  # type: ignore[arg-type]
        ),
    )
    with metric_spies() as spies, logcap():
        assert sup._check_worker_heartbeat("w") is False
    assert w.missed_heartbeat_count == 0
    assert spies["record_worker_heartbeat_missed"].calls == []


# ---------------------------------------------------------------------------
# _run_worker
# ---------------------------------------------------------------------------


def test_run_worker_crash_full_surface() -> None:
    async def go() -> None:
        bcast = FakeBroadcaster()
        sup = make_sup(broadcaster=bcast)

        async def boom() -> None:
            raise RuntimeError("boom")

        w = add_worker(
            sup,
            make_info("w", factory=boom, status=WorkerStatus.RUNNING, restart_count=1),
        )
        with metric_spies() as spies, logcap() as cap:
            await sup._run_worker("w")

        assert w.status is WorkerStatus.CRASHED
        assert w.error == "boom"
        assert w.last_crashed_at is not None
        assert w.last_crashed_at.utcoffset() is not None  # m4: now(None) is naive

        assert spies["record_worker_crash"].one() == (("w",), {"error": "boom"})
        assert spies["set_worker_status"].one() == (("w", "crashed"), {})
        assert spies["set_pipeline_worker_state"].one() == (("w", "stopped"), {})
        assert spies["set_pipeline_worker_consecutive_failures"].one() == (("w", 2), {})
        assert spies["set_pipeline_worker_uptime"].one() == (("w", -1.0), {})

        rec = cap.one("Worker 'w' crashed: boom")
        assert isinstance(rec.exc_info, tuple) and rec.exc_info[0] is RuntimeError  # m35-38

        pin_status_event(bcast.calls[0], "worker:w", "crashed", "boom")

    run(go())


# ---------------------------------------------------------------------------
# _start_worker / start / stop
# ---------------------------------------------------------------------------


def test_start_worker_attrs_metrics_and_task_name() -> None:
    async def go() -> None:
        bcast = FakeBroadcaster()
        sup = make_sup(broadcaster=bcast)
        w = add_worker(sup, make_info("w", status=WorkerStatus.STOPPED, restart_count=2))
        before = datetime.now(UTC)
        with metric_spies() as spies, logcap() as cap:
            await sup._start_worker("w")
        task = w.task
        try:
            assert task is not None
            assert task.get_name() == "worker-w"  # m8 None / m10 deletion
            assert w.status is WorkerStatus.RUNNING
            assert w.error is None  # m19: "" fails
            assert w.missed_heartbeat_count == 0
            assert w.last_started_at is not None and w.last_started_at >= before
            assert w.last_started_at.utcoffset() is not None  # m14 naive
            assert w.last_heartbeat_at is not None and w.last_heartbeat_at >= before
            assert w.last_heartbeat_at.utcoffset() is not None  # m16 naive
            assert spies["set_worker_status"].one() == (("w", "running"), {})
            assert spies["set_pipeline_worker_state"].one() == (("w", "running"), {})
            assert spies["set_pipeline_worker_consecutive_failures"].one() == (("w", 2), {})
            assert spies["set_pipeline_worker_uptime"].one() == (("w", 0.0), {})
            assert cap.msgs() == ["Started worker 'w'"]
            pin_status_event(bcast.calls[0], "worker:w", "running", None)
        finally:
            await _cleanup(task)

    run(go())


def test_start_worker_unknown_warns() -> None:
    async def go() -> None:
        sup = make_sup()
        with logcap() as cap:
            await sup._start_worker("ghost")
        assert cap.msgs() == ["Cannot start unknown worker: ghost"]

    run(go())


def test_start_already_running_warns() -> None:
    async def go() -> None:
        sup = make_sup()
        sup._running = True
        with metric_spies() as spies, logcap() as cap:
            await sup.start()
        assert cap.msgs() == ["WorkerSupervisor already running"]
        assert sup._monitor_task is None
        assert spies["update_worker_pool_metrics"].calls == []

    run(go())


def test_start_lifecycle_task_name_and_msgs() -> None:
    async def go() -> None:
        sup = make_sup(check_interval=0.01)
        with metric_spies() as spies, logcap() as cap:
            await sup.start()
            assert sup._monitor_task is not None
            assert sup._monitor_task.get_name() == "worker-supervisor"  # m14-m18
            assert spies["update_worker_pool_metrics"].calls[0] == ((0, 0, 0), {})
            await asyncio.sleep(0.05)  # let the monitor loop suspend in its sleep
            await sup.stop()
        assert sup._monitor_task is None  # m13 stop: "" fails identity
        assert sup._running is False  # stop m10: None fails identity
        assert cap.msgs() == [
            "Starting WorkerSupervisor",
            "WorkerSupervisor started",
            "Monitor loop started",
            "Stopping WorkerSupervisor",
            "Monitor loop cancelled",
            "Monitor loop stopped",
            "WorkerSupervisor stopped",
        ]

    run(go())


def test_stop_cancels_monitor_task_when_present() -> None:
    async def go() -> None:
        sup = make_sup(check_interval=0.01)
        with metric_spies():
            await sup.start()
            monitor = sup._monitor_task
            assert monitor is not None
            await asyncio.sleep(0.05)
            try:
                with logcap():
                    await sup.stop()
                # m12 (`is not None` -> `is None`): the block is skipped ->
                # attr stays set and the task is left pending. The orig
                # awaited it to FINISHED (the loop swallows the
                # CancelledError, so the task is done-not-cancelled).
                assert sup._monitor_task is None
                assert monitor.done() and not monitor.cancelled()
            finally:
                await _cleanup(monitor)

    run(go())


def test_stop_not_running_debug() -> None:
    async def go() -> None:
        sup = make_sup()
        with logcap() as cap:
            await sup.stop()
        assert cap.msgs() == ["WorkerSupervisor not running"]
        assert sup._running is False

    run(go())


def test_stop_worker_task_polarities() -> None:
    async def go() -> None:
        sup = make_sup()
        sup._running = True
        w_none = add_worker(sup, make_info("none", status=WorkerStatus.RUNNING, task=None))
        done = asyncio.create_task(_done_task(), name="done-t")
        with contextlib.suppress(BaseException):
            await done
        w_done = add_worker(sup, make_info("done", status=WorkerStatus.RUNNING, task=done))
        live = asyncio.create_task(forever(), name="worker-live")
        w_live = add_worker(sup, make_info("live", status=WorkerStatus.RUNNING, task=live))
        try:
            with metric_spies(), logcap():
                await sup.stop()
            # m14/m15 flips raise on the None-task worker (.done()/cancel)
            assert w_none.task is None and w_done.task is None and w_live.task is None
            assert live.cancelled()  # m16 done-arm flip: skip-cancel leaves it pending
            assert w_none.status is WorkerStatus.STOPPED
            assert w_done.status is WorkerStatus.STOPPED
            assert w_live.status is WorkerStatus.STOPPED
        finally:
            await _cleanup(live)

    run(go())


def test_stop_metrics_per_worker() -> None:
    async def go() -> None:
        sup = make_sup()
        sup._running = True
        w = add_worker(sup, make_info("w", status=WorkerStatus.RUNNING, task=None))
        with metric_spies() as spies, logcap() as cap:
            await sup.stop()
        assert spies["set_worker_status"].one() == (("w", "stopped"), {})
        assert spies["set_pipeline_worker_state"].one() == (("w", "stopped"), {})
        assert spies["set_pipeline_worker_uptime"].one() == (("w", -1.0), {})
        assert spies["update_worker_pool_metrics"].one() == ((0, 0, 0), {})
        assert cap.msgs() == [
            "Stopping WorkerSupervisor",
            "WorkerSupervisor stopped",
        ]
        assert w.task is None  # m18: "" fails identity

    run(go())


def test_register_and_unregister_rounds() -> None:
    async def go() -> None:
        sup = make_sup()
        with logcap() as cap:
            await sup.register_worker("w", _idle_factory, max_restarts=7)
        assert sup.worker_count == 1
        w = sup.get_worker_info("w")
        assert w is not None and w.max_restarts == 7
        assert cap.msgs() == [
            "Registered worker 'w': max_restarts=7, backoff_base=1.0s, heartbeat_timeout=30.0s"
        ]
        with logcap() as cap2:
            await sup.unregister_worker("w")
        assert cap2.msgs() == ["Unregistered worker 'w'"]
        assert sup.worker_count == 0 and "w" not in sup._restart_locks
        with logcap() as cap3:
            await sup.unregister_worker("ghost")
        assert cap3.msgs() == ["Cannot unregister unknown worker: ghost"]
        await sup.register_worker("w", _idle_factory)
        try:
            await sup.register_worker("w", _idle_factory)
            raise AssertionError("duplicate register must raise")
        except ValueError as e:
            assert str(e) == "Worker 'w' is already registered"

    run(go())


# ---------------------------------------------------------------------------
# _handle_stuck_worker (the shield/timeout family needs a cancel-ignoring task)
# ---------------------------------------------------------------------------


def test_stuck_worker_full_surface() -> None:
    async def go() -> None:
        bcast = FakeBroadcaster()
        sup = make_sup(broadcaster=bcast, missed_heartbeat_restart_threshold=2)
        task = asyncio.create_task(stubborn(), name="worker-stuck")
        await asyncio.sleep(0)  # let it reach its sleep
        w = add_worker(
            sup,
            make_info("w", status=WorkerStatus.RUNNING, task=task, missed_heartbeat_count=2),
        )
        t0 = time.perf_counter()
        with metric_spies() as spies, logcap() as cap:
            await sup._handle_stuck_worker("w")
        elapsed = time.perf_counter() - t0
        try:
            # orig: wait_for(shield(task), 2.0) times out at ~2.0s and the
            # shield keeps the task PENDING. timeout=None/deleted arms wait
            # for the task (~3.5s, done); timeout=3.0 waits 3.0s; the
            # shield-dropped arms (TypeError) record a debug line.
            assert 1.9 < elapsed < 2.5, elapsed
            assert not task.done()  # m10/m11/m12 arms finish it
            expected_error = "Worker stuck - missed 2 consecutive heartbeats (threshold: 2)"
            assert w.status is WorkerStatus.CRASHED
            assert w.error == expected_error
            assert w.missed_heartbeat_count == 0  # m19 None / m20 1 fail
            assert w.last_crashed_at is not None
            assert w.last_crashed_at.utcoffset() is not None  # m17 naive; m16 None
            assert spies["record_worker_crash"].one() == (("w", expected_error), {})
            assert spies["set_worker_status"].one() == (("w", "crashed"), {})
            assert spies["set_pipeline_worker_state"].one() == (("w", "crashed"), {})
            pin_status_event(bcast.calls[0], "worker:w", "crashed", expected_error)
            assert cap.msgs() == [
                f"Force-cancelling stuck worker 'w': {expected_error}",
                "Worker 'w' marked as crashed, will restart on next monitor cycle",
            ]
            # ---- phase 2: the NEXT monitor cycle (production sequence).
            # The shielded task is STILL PENDING (3.5s stubborn window,
            # ~1.5s left), so _start_worker EARLY-RETURNS and the values
            # its fall-through would overwrite stay observable:
            # hc m53 (status=RESTARTING vs None) and the history-event
            # error slot m103/m107 (keeps the stuck message).
            sup._running = True  # past the post-backoff guard
            with metric_spies() as spies2, logcap() as cap2:
                await sup._handle_crashed_worker("w")
            assert w.status is WorkerStatus.RESTARTING  # hc m53 -> None RED
            assert w.error == expected_error
            assert w.restart_count == 1
            assert w.task is task and not task.done()
            assert spies2["set_worker_status"].one() == (("w", "restarting"), {})
            assert spies2["set_pipeline_worker_state"].one() == (("w", "restarting"), {})
            assert spies2["record_worker_restart"].one() == (("w",), {"reason": expected_error})
            (_, rkw) = spies2["record_pipeline_worker_restart"].one()
            assert rkw["reason"] == expected_error
            (ev,) = sup.get_restart_history()
            assert {k: v for k, v in ev.items() if k != "timestamp"} == {
                "worker_name": "w",
                "attempt": 1,
                "status": "success",
                "error": expected_error,  # hc m103 None / m107 deleted -> RED
            }
            assert cap2.msgs() == [
                "Restarting worker 'w' in 0.0s (attempt 1/5)",
                "Worker 'w' already running",  # _start_worker early-return
                "Recorded restart event: w attempt=1 status=success",
            ]
        finally:
            await _cleanup(task)

    run(go())


def test_stuck_worker_none_task_round() -> None:
    async def go() -> None:
        sup = make_sup()
        with logcap() as cap0:
            await sup._handle_stuck_worker("ghost")  # unknown -> silent
        assert cap0.msgs() == []
        # orig skips the cancel guard for task=None; the m6 or-flip ENTERS
        # it and raises (None.done() -> AttributeError) -> RED.
        w = add_worker(sup, make_info("w", status=WorkerStatus.RUNNING, task=None))
        with logcap() as cap:
            await sup._handle_stuck_worker("w")
        assert w.status is WorkerStatus.CRASHED
        assert cap.msgs() == [
            "Force-cancelling stuck worker 'w': Worker stuck - missed 0 consecutive "
            "heartbeats (threshold: 5)",
            "Worker 'w' marked as crashed, will restart on next monitor cycle",
        ]

    run(go())


# ---------------------------------------------------------------------------
# _handle_crashed_worker
# ---------------------------------------------------------------------------


def test_handle_crashed_failed_path() -> None:
    async def go() -> None:
        bcast = FakeBroadcaster()
        failures: list[tuple[Any, ...]] = []

        async def on_failure(name: str, error: str | None) -> None:
            failures.append((name, error))

        sup = make_sup(broadcaster=bcast, on_failure=on_failure)
        w = add_worker(
            sup,
            make_info(
                "w",
                status=WorkerStatus.CRASHED,
                restart_count=2,
                max_restarts=2,
                error="boom",
            ),
        )
        with metric_spies() as spies, logcap() as cap:
            await sup._handle_crashed_worker("w")
        assert w.status is WorkerStatus.FAILED  # m2 >-flip takes RESTARTING instead
        assert w.circuit_open is True
        assert spies["record_worker_max_restarts_exceeded"].one() == (("w",), {})
        assert spies["set_worker_status"].one() == (("w", "failed"), {})
        assert spies["set_pipeline_worker_state"].one() == (("w", "failed"), {})
        assert spies["set_pipeline_worker_consecutive_failures"].one() == (("w", 2), {})
        assert spies["set_pipeline_worker_uptime"].one() == (("w", -1.0), {})
        assert cap.msgs() == [
            "Worker 'w' exceeded max restarts (2), giving up",
            "Recorded restart event: w attempt=2 status=failed",
        ]
        pin_status_event(bcast.calls[0], "worker:w", "failed", "Exceeded max restarts (2)")
        assert failures == [("w", "boom")]
        (ev,) = sup.get_restart_history()
        assert {k: v for k, v in ev.items() if k != "timestamp"} == {
            "worker_name": "w",
            "attempt": 2,
            "status": "failed",
            "error": "Exceeded max restarts (2)",
        }
        assert ev["timestamp"].endswith("+00:00")  # record_restart_event m12

    run(go())


def test_handle_crashed_failed_callback_raise() -> None:
    async def go() -> None:
        async def bad_failure(name: str, error: str | None) -> None:
            raise RuntimeError("cb")

        sup = make_sup(on_failure=bad_failure)
        add_worker(
            sup,
            make_info("w", status=WorkerStatus.CRASHED, restart_count=5, max_restarts=5),
        )
        with logcap() as cap:
            await sup._handle_crashed_worker("w")
        assert cap.msgs() == [
            "Worker 'w' exceeded max restarts (5), giving up",
            "Recorded restart event: w attempt=5 status=failed",
            "on_failure callback raised exception: cb",
        ]

    run(go())


def test_handle_crashed_restart_path() -> None:
    async def go() -> None:
        bcast = FakeBroadcaster()
        restarts: list[tuple[Any, ...]] = []

        async def on_restart(name: str, attempt: int, error: str | None) -> None:
            restarts.append((name, attempt, error))

        sup = make_sup(broadcaster=bcast, on_restart=on_restart)
        sup._running = True  # the post-backoff guard: `if not self._running: return`
        w = add_worker(
            sup,
            make_info(
                "w",
                status=WorkerStatus.CRASHED,
                restart_count=1,
                max_restarts=5,
                error="boom",
            ),
        )
        with metric_spies() as spies, logcap() as cap:
            await sup._handle_crashed_worker("w")
        task = w.task
        try:
            assert w.status is WorkerStatus.RUNNING  # _start_worker overwrote RESTARTING
            assert w.restart_count == 2
            assert spies["set_worker_status"].calls[0] == (("w", "restarting"), {})
            assert spies["set_pipeline_worker_state"].calls[0] == (("w", "restarting"), {})
            assert spies["record_worker_restart"].one() == (("w",), {"reason": "boom"})
            (args, kwargs) = spies["record_pipeline_worker_restart"].one()
            assert args == ("w",)
            assert kwargs["reason"] == "boom"  # m94 None; m97/m98 deletion
            duration = kwargs.get("duration_seconds", None)
            assert duration is not None and 0.0 <= duration < 60.0  # m91/m92
            assert restarts == [("w", 2, "boom")]  # m79 rc+2
            assert cap.msgs() == [
                "Restarting worker 'w' in 0.0s (attempt 2/5)",
                "Started worker 'w'",
                "Recorded restart event: w attempt=2 status=success",
            ]
            pin_status_event(bcast.calls[0], "worker:w", "restarting", None)
            # NOTE the ordering: _start_worker clears worker.error BEFORE the
            # success history event is recorded, so the event's error is None
            # even though the reason kwargs (recorded earlier) kept "boom".
            (ev,) = sup.get_restart_history()
            assert {k: v for k, v in ev.items() if k != "timestamp"} == {
                "worker_name": "w",
                "attempt": 2,
                "status": "success",
                "error": None,
            }
        finally:
            await _cleanup(task)

    run(go())


def test_handle_crashed_restart_callback_raise() -> None:
    async def go() -> None:
        async def bad_restart(name: str, attempt: int, error: str | None) -> None:
            raise RuntimeError("cb")

        sup = make_sup(on_restart=bad_restart)
        sup._running = True
        w = add_worker(
            sup,
            make_info("w", status=WorkerStatus.CRASHED, restart_count=0, max_restarts=5),
        )
        with logcap() as cap:
            await sup._handle_crashed_worker("w")
        task = w.task
        try:
            assert cap.msgs() == [
                "Restarting worker 'w' in 0.0s (attempt 1/5)",
                "on_restart callback raised exception: cb",
                "Started worker 'w'",
                "Recorded restart event: w attempt=1 status=success",
            ]
        finally:
            await _cleanup(task)

    run(go())


# ---------------------------------------------------------------------------
# monitor loop
# ---------------------------------------------------------------------------


def test_monitor_loop_invalid_sleep_error_path() -> None:
    async def go() -> None:
        sup = make_sup(check_interval=0.01)
        with metric_spies():
            await sup.start()
            monitor = sup._monitor_task
            assert monitor is not None
            await asyncio.sleep(0.05)  # let a few clean iterations run
            try:
                with logcap() as cap:
                    sup._running = False
                    await asyncio.sleep(0.05)
                    with contextlib.suppress(BaseException):
                        await monitor
                # m13 sleep(None): the loop SURVIVES, logging
                # "Error in monitor loop: ..." every iteration.
                assert cap.msgs() == ["Monitor loop stopped"]
                assert monitor.done()
            finally:
                await _cleanup(monitor)

    run(go())


# ---------------------------------------------------------------------------
# restart history / pool counts / manual controls
# ---------------------------------------------------------------------------


def test_restart_history_trim_and_rounds() -> None:
    sup = make_sup(max_restart_history=3)
    with logcap() as cap:
        for i in range(4):
            sup._record_restart_event(worker_name=f"w{i % 2}", attempt=i, status="success")
    names = [e.worker_name for e in sup._restart_history]
    assert names == ["w1", "w0", "w1"]  # trims to the LAST 3
    assert cap.msgs() == [
        "Recorded restart event: w0 attempt=0 status=success",
        "Recorded restart event: w1 attempt=1 status=success",
        "Recorded restart event: w0 attempt=2 status=success",
        "Recorded restart event: w1 attempt=3 status=success",
    ]
    assert sup.get_restart_history_count() == 3
    assert sup.get_restart_history_count("w1") == 2
    # deterministic sort/pagination via a hand-built history (distinct ts)
    sup._restart_history = [
        RestartEvent(
            worker_name="h",
            timestamp=STARTED_AT + timedelta(seconds=i),
            attempt=i,
            status="success",
        )
        for i in range(4)
    ]
    assert [e["attempt"] for e in sup.get_restart_history()] == [3, 2, 1, 0]
    assert [e["attempt"] for e in sup.get_restart_history(limit=2)] == [3, 2]
    assert [e["attempt"] for e in sup.get_restart_history(offset=1, limit=2)] == [2, 1]
    assert sup.get_restart_history()[0]["timestamp"].endswith("+00:00")


def test_pool_counts_and_metrics_tuples() -> None:
    async def go() -> None:
        sup = make_sup()
        live = asyncio.create_task(forever(), name="w-live")
        add_worker(sup, make_info("live", status=WorkerStatus.RUNNING, task=live))
        done = asyncio.create_task(_done_task(), name="w-done")
        with contextlib.suppress(BaseException):
            await done
        add_worker(sup, make_info("done", status=WorkerStatus.RUNNING, task=done))
        try:
            assert sup.get_worker_pool_counts() == (2, 1, 1)  # m9 or-flip -> (2, 2, 0)
            with metric_spies() as spies:
                sup._update_worker_pool_metrics()
            assert spies["update_worker_pool_metrics"].one() == ((2, 1, 1), {})
        finally:
            await _cleanup(live)

    run(go())


def test_reset_worker_rounds() -> None:
    sup = make_sup()
    w = add_worker(sup, make_info("w", status=WorkerStatus.FAILED, restart_count=4))
    with logcap() as cap:
        assert sup.reset_worker("w") is True
    assert w.restart_count == 0 and w.status is WorkerStatus.STOPPED
    assert cap.msgs() == ["Reset worker 'w' restart count"]
    with logcap() as cap2:
        assert sup.reset_worker("ghost") is False
    assert cap2.msgs() == []


def test_reset_circuit_breaker_rounds() -> None:
    sup = make_sup()
    w = add_worker(
        sup,
        make_info("w", status=WorkerStatus.FAILED, restart_count=3, circuit_open=True),
    )
    with logcap() as cap:
        assert sup.reset_circuit_breaker("w") is True
    assert w.circuit_open is False and w.restart_count == 0
    assert w.status is WorkerStatus.STOPPED
    assert cap.msgs() == ["Reset circuit breaker for worker 'w'"]
    with logcap() as cap2:
        assert sup.reset_circuit_breaker("ghost") is False
    assert cap2.msgs() == ["Cannot reset circuit breaker for unknown worker: ghost"]


def test_record_heartbeat_rounds() -> None:
    sup = make_sup()
    w = add_worker(
        sup,
        make_info("w", status=WorkerStatus.RUNNING, missed_heartbeat_count=3),
    )
    w.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=500)
    with logcap() as cap:
        assert sup.record_heartbeat("w") is True
    assert w.missed_heartbeat_count == 0
    assert w.last_heartbeat_at is not None
    assert w.last_heartbeat_at.utcoffset() is not None  # m7 naive
    assert cap.msgs() == ["Heartbeat recorded for worker 'w'"]
    with logcap() as cap2:
        assert sup.record_heartbeat("ghost") is False
    assert cap2.msgs() == ["Cannot record heartbeat for unknown worker: ghost"]


def test_manual_start_worker_rounds() -> None:
    async def go() -> None:
        sup = make_sup()
        with logcap() as cap0:
            assert await sup.start_worker("ghost") is False
        assert cap0.msgs() == ["Cannot start unknown worker: ghost"]
        live = asyncio.create_task(forever(), name="pre")
        w = add_worker(sup, make_info("w", status=WorkerStatus.RUNNING, task=live))
        with logcap() as cap1:
            assert await sup.start_worker("w") is True  # already running -> idempotent
        assert w.task is live
        assert cap1.msgs() == ["Worker 'w' is already running"]
        await _cleanup(live)
        w.status = WorkerStatus.FAILED
        w.restart_count = 3
        w.circuit_open = True
        w.task = None
        with logcap() as cap:
            assert await sup.start_worker("w") is True
        task = w.task
        try:
            assert w.restart_count == 0 and w.circuit_open is False
            assert task is not None and task.get_name() == "worker-w"
            assert cap.msgs() == ["Started worker 'w'", "Manually started worker 'w'"]
        finally:
            await _cleanup(task)

    run(go())


def test_manual_stop_worker_rounds() -> None:
    async def go() -> None:
        bcast = FakeBroadcaster()
        sup = make_sup(broadcaster=bcast)
        with logcap() as cap0:
            assert await sup.stop_worker("ghost") is False
        assert cap0.msgs() == ["Cannot stop unknown worker: ghost"]
        live = asyncio.create_task(forever(), name="worker-w")
        w = add_worker(sup, make_info("w", status=WorkerStatus.RUNNING, task=live))
        with metric_spies() as spies, logcap() as cap:
            assert await sup.stop_worker("w") is True
        assert w.task is None  # m10: "" fails identity
        assert w.status is WorkerStatus.STOPPED
        assert live.cancelled()  # m8 done-arm flip leaves it un-cancelled
        assert spies["set_worker_status"].one() == (("w", "stopped"), {})
        pin_status_event(bcast.calls[0], "worker:w", "stopped", "Manually stopped")
        assert cap.msgs() == ["Manually stopped worker 'w'"]
        # None-task round: the m6/m7 or/None flips raise (.done() on None)
        w2 = add_worker(sup, make_info("w2", status=WorkerStatus.RUNNING, task=None))
        with metric_spies(), logcap() as cap2:
            assert await sup.stop_worker("w2") is True
        assert w2.status is WorkerStatus.STOPPED
        assert cap2.msgs() == ["Manually stopped worker 'w2'"]

    run(go())


def test_manual_restart_worker_task_rounds() -> None:
    async def go() -> None:
        sup = make_sup()
        with logcap() as cap0:
            assert await sup.restart_worker_task("ghost") is False
        assert cap0.msgs() == ["Cannot restart unknown worker: ghost"]
        live = asyncio.create_task(forever(), name="worker-w")
        w = add_worker(
            sup,
            make_info(
                "w",
                status=WorkerStatus.RUNNING,
                task=live,
                restart_count=2,
                circuit_open=True,
                error="boom",
            ),
        )
        with logcap() as cap:
            assert await sup.restart_worker_task("w") is True
        task = w.task
        try:
            assert live.cancelled()
            assert w.restart_count == 0
            assert w.to_dict()["circuit_open"] is False  # m11 None / m12 True
            assert w.to_dict()["error"] is None  # m13 "" fails
            assert task is not None and task.get_name() == "worker-w"
            (ev,) = sup.get_restart_history()
            assert {k: v for k, v in ev.items() if k != "timestamp"} == {
                "worker_name": "w",
                "attempt": 0,  # m16 None / m23 1
                "status": "success",
                "error": "Manual restart requested",
            }
            assert cap.msgs() == [
                "Started worker 'w'",
                "Recorded restart event: w attempt=0 status=success",
                "Manually restarted worker 'w'",
            ]
        finally:
            await _cleanup(task)
        # None-task round: the m6 or-flip raises (.done() on None)
        w2 = add_worker(sup, make_info("w2", status=WorkerStatus.RUNNING, task=None))
        with logcap() as cap2:
            assert await sup.restart_worker_task("w2") is True
        task2 = w2.task
        try:
            assert cap2.msgs() == [
                "Started worker 'w2'",
                "Recorded restart event: w2 attempt=0 status=success",
                "Manually restarted worker 'w2'",
            ]
        finally:
            await _cleanup(task2)

    run(go())


def test_calculate_backoff_static_formula() -> None:
    # m2 EQUIV probe: `<= 0` vs `<= 1` both yield base at rc=1
    assert ws.WorkerSupervisor._calculate_backoff_static(0, 1.0, 10.0) == 1.0
    assert ws.WorkerSupervisor._calculate_backoff_static(1, 1.0, 10.0) == 1.0
    assert ws.WorkerSupervisor._calculate_backoff_static(2, 1.0, 10.0) == 2.0
    assert ws.WorkerSupervisor._calculate_backoff_static(3, 1.0, 10.0) == 4.0
    assert ws.WorkerSupervisor._calculate_backoff_static(10, 1.0, 10.0) == 10.0
