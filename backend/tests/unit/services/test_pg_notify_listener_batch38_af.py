# TARGET-MODULE: backend.services.pg_notify_listener
"""Battery AF - campaign #30 backend/services/pg_notify_listener.py (238 survivors).

Kill surfaces (each proven by construction against the pristine module):
  * Handler message dicts are pinned WHOLE (and the redis publish call as a
    whole (args, kwargs) tuple on a signature-free recorder): the payload
    carries a UNIQUE value per key, so key renames, XX-wraps, and
    .get(None)/.get("XXkeyXX) arms - which all return None for a key the
    payload actually has - change the dict, never ride through it.
  * Log records are censused BY NAME (record.channels, record.event_id,
    ...) plus whole-msg equality: extra= renames/deletions surface as
    missing attributes, msg None/XX/case flips as msg inequality.
  * Backoff is pinned by the FULL sleep-argument sequence on both the
    _connect give-up path and the _listen_loop error path, so every
    * / / / ** -family and offset twin fails on some element.
  * asyncio/asyncpg/get_settings are swapped as MODULE GLOBALS on pgn
    (the mutants read their module __globals__): a fake asyncpg records
    the exact dsn and add_listener (channel, callback) pairs, a fake
    asyncio records sleeps without waiting and can hand out FakeTasks so
    start() never spins the real loop.
  * start() resets _reconnect_attempts BEFORE _connect - whose success
    ALSO resets it - so the m7(None)/m8(1) arms only bite when the FIRST
    connect attempt fails: the retry delay must be 1.0 (m8 gives 2.0) and
    None+1 must not raise (m7).

Honesty ledger (registered EQUIVALENTS - value-identical by construction):
  _listen_loop m15/m31: `break` -> `return` - the while loop is the last
    statement of the function, so exiting the loop and returning are the
    same observable behaviour (the task ends, nothing follows).
  get_status m8: `if self._connection` -> `if (self._connection) or True`
    - the always-true condition keeps the True-branch expression, whose
    `connection is not None and not is_closed()` evaluates False for a
    None connection - identical to the dropped else-branch False on all
    three polarities (None / open / closed).
"""

import asyncio
import contextlib
import json
import logging
from types import SimpleNamespace

import backend.services.pg_notify_listener as pgn
from backend.services.pg_notify_listener import PgNotifyChannel, PgNotifyListener

REAL = asyncio  # the real module - pgn.asyncio is shimmed by some tests
run = asyncio.run

MISSING = object()

# Static literals every expectation is pinned against (never derived from
# the module source at runtime - under the trampoline tree that text also
# contains every mutant body).
STUB_URL = "postgresql+asyncpg://db:pw@localhost:5432/db"  # pragma: allowlist secret
STUB_DSN = "postgresql://db:pw@localhost:5432/db"  # pragma: allowlist secret
STUB_CHANNEL = "events-ch"
ALL_CHANNELS = ["events_new", "events_update", "detections_new", "alerts_new"]

_EV_NEW = json.dumps(
    {
        "operation": "INSERT",
        "table": "events",
        "data": {
            "id": 11,
            "batch_id": "b-1",
            "camera_id": "cam-9",
            "risk_score": 7.25,
            "risk_level": "high",
            "summary": "s-1",
            "started_at": "2026-10-03T09:00:00",
        },
    }
)
_UPD = json.dumps(
    {
        "operation": "UPDATE",
        "table": "events",
        "data": {
            "id": 12,
            "risk_score": 3.5,
            "risk_level": "low",
            "summary": "s-2",
            "reviewed": True,
        },
    }
)
_DET_NEW = json.dumps(
    {
        "operation": "INSERT",
        "table": "detections",
        "data": {
            "id": 13,
            "camera_id": "cam-3",
            "object_type": "person",
            "confidence": 0.87,
            "detected_at": "2026-10-03T09:01:00",
        },
    }
)
_AL_NEW = json.dumps(
    {
        "operation": "INSERT",
        "table": "alerts",
        "data": {
            "id": 14,
            "event_id": 7,
            "rule_id": 2,
            "severity": "HIGH",
            "status": "ACTIVE",
        },
    }
)

_MSG_NEW = {
    "type": "event",
    "source": "pg_notify",
    "data": {
        "id": 11,
        "event_id": 11,
        "batch_id": "b-1",
        "camera_id": "cam-9",
        "risk_score": 7.25,
        "risk_level": "high",
        "summary": "s-1",
        "started_at": "2026-10-03T09:00:00",
    },
}
_MSG_UPD = {
    "type": "event_update",
    "source": "pg_notify",
    "data": {
        "id": 12,
        "event_id": 12,
        "risk_score": 3.5,
        "risk_level": "low",
        "summary": "s-2",
        "reviewed": True,
    },
}
_MSG_DET = {
    "type": "detection.new",
    "source": "pg_notify",
    "data": {
        "detection_id": 13,
        "camera_id": "cam-3",
        "label": "person",
        "confidence": 0.87,
        "timestamp": "2026-10-03T09:01:00",
    },
}
_MSG_ALERT = {
    "type": "alert_created",
    "source": "pg_notify",
    "data": {
        "id": 14,
        "event_id": 7,
        "rule_id": 2,
        "severity": "HIGH",
        "status": "ACTIVE",
    },
}


def settings_stub():
    return SimpleNamespace(
        database_url=STUB_URL,
        redis_event_channel=STUB_CHANNEL,
    )


class PublishSpy:
    """Signature-free recorder: publish is awaited, so the arms are
    recorded as (args, kwargs) and compared WHOLE."""

    def __init__(self, fail=None):
        self.calls = []
        self._fail = fail

    async def publish(self, *args, **kwargs):
        if self._fail is not None:
            raise self._fail
        self.calls.append((args, kwargs))


class FakeConn:
    def __init__(self, closed=False, close_error=None, is_closed_error=None):
        self.subs = []
        self.closed = closed
        self.close_error = close_error
        self.is_closed_error = is_closed_error
        self.close_calls = 0

    async def add_listener(self, *args):
        self.subs.append(args)

    async def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error

    def is_closed(self):
        if self.is_closed_error is not None:
            raise self.is_closed_error
        return self.closed


class _Asyncpg:
    """Fake asyncpg module: connect(dsn) records the dsn and pops the
    scripted outcome (reusing the LAST one forever once exhausted)."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    async def connect(self, dsn):
        self.calls.append(dsn)
        item = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(item, BaseException):
            raise item
        return item


class FakeTask:
    """Awaitable no-op stand-in for the listener task (start tests)."""

    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def __await__(self):
        return iter(())


def _stub_asyncio(sleeps, tasks=None):
    """pgn.asyncio shim: fake sleep records delays (no waiting) and can
    fire an after(d) hook; create_task records coroutines and hands out a
    FakeTask unless tasks is given (then the coro is scheduled for real)."""

    async def fake_sleep(delay):
        sleeps.append(delay)
        after = getattr(fake_sleep, "after", None)
        if after is not None:
            after(delay)
        await REAL.sleep(0)

    def create_task(coro):
        if tasks is None:
            tasks_seen.append(coro)
            coro.close()  # never scheduled here - close it, no GC warning
            return FakeTask()
        t = REAL.create_task(coro)
        tasks.append(t)
        return t

    tasks_seen = []
    stub = SimpleNamespace(
        sleep=fake_sleep,
        create_task=create_task,
        CancelledError=REAL.CancelledError,
    )
    stub.created = tasks_seen
    return stub


def _rec_msgs(records, level):
    return [r.msg for r in records if r.levelno == level]


def caplogs(fn):
    def wrapper():
        handler = _RecHandler()
        lg = pgn.logger
        prev_propagate, prev_level = lg.propagate, lg.level
        lg.addHandler(handler)
        lg.propagate = False
        lg.setLevel(logging.DEBUG)
        try:
            return fn(handler.records)
        finally:
            lg.removeHandler(handler)
            lg.propagate = prev_propagate
            lg.setLevel(prev_level)

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


class _RecHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def patched(fn):
    def wrapper():
        names = ("get_settings", "asyncpg", "asyncio", "_listener")
        saved = {n: getattr(pgn, n, MISSING) for n in names}
        try:
            return fn()
        finally:
            for n, v in saved.items():
                if v is MISSING:
                    with contextlib.suppress(AttributeError):
                        delattr(pgn, n)
                else:
                    setattr(pgn, n, v)

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


# ---------------------------------------------------------------- init / status


@caplogs
def test_init_defaults_extras_and_status(logs):
    ln = PgNotifyListener(redis_client="R", broadcaster="B")
    assert ln._redis == "R" and ln._broadcaster == "B"
    assert ln._channels is PgNotifyListener.DEFAULT_CHANNELS
    assert ln.get_status() == {
        "running": False,
        "healthy": False,
        "connected": False,
        "reconnect_attempts": 0,
        "channels": ALL_CHANNELS,
    }
    assert ln.is_healthy() is False
    assert _rec_msgs(logs, logging.INFO) == ["PgNotifyListener initialized"]
    assert logs[0].channels == ALL_CHANNELS
    assert not hasattr(logs[0], "XXchannelsXX") and not hasattr(logs[0], "CHANNELS")


def test_get_status_connection_polarities():
    ln = PgNotifyListener(channels=[PgNotifyChannel.ALERTS_NEW])
    conn = FakeConn(closed=False)
    ln._connection = conn
    assert ln.get_status() == {
        "running": False,
        "healthy": False,
        "connected": True,
        "reconnect_attempts": 0,
        "channels": ["alerts_new"],
    }
    conn.closed = True
    assert ln.get_status() == {
        "running": False,
        "healthy": False,
        "connected": False,
        "reconnect_attempts": 0,
        "channels": ["alerts_new"],
    }
    ln._connection = None
    assert ln.get_status() == {
        "running": False,
        "healthy": False,
        "connected": False,
        "reconnect_attempts": 0,
        "channels": ["alerts_new"],
    }


@patched
def test_singleton_forwards_dependencies():
    pgn._listener = None
    r, b = object(), object()

    async def main():
        first = await pgn.get_pg_notify_listener(redis_client=r, broadcaster=b)
        second = await pgn.get_pg_notify_listener(redis_client=object(), broadcaster=object())
        return first, second

    first, second = run(main())
    assert first._redis is r
    assert first._broadcaster is b
    assert second is first


# ---------------------------------------------------------------- connect


@patched
@caplogs
def test_connect_success_subscribes_and_logs(logs):
    sleeps = []
    conn = FakeConn()
    apg = _Asyncpg([conn])
    pgn.asyncpg = apg
    pgn.asyncio = _stub_asyncio(sleeps)
    pgn.get_settings = settings_stub
    ln = PgNotifyListener()
    run(ln._connect())
    assert apg.calls == [STUB_DSN]
    assert conn.subs == [
        ("events_new", ln._notification_callback),
        ("events_update", ln._notification_callback),
        ("detections_new", ln._notification_callback),
        ("alerts_new", ln._notification_callback),
    ]
    assert sleeps == []
    assert ln._is_healthy is True and ln._reconnect_attempts == 0
    assert _rec_msgs(logs, logging.INFO) == [
        "PgNotifyListener initialized",
        "PgNotifyListener connected to database",
    ]
    assert [r.channels for r in logs] == [ALL_CHANNELS, ALL_CHANNELS]


@patched
@caplogs
def test_connect_retries_backoff_then_gives_up(logs):
    sleeps = []
    apg = _Asyncpg([RuntimeError("nope")])
    pgn.asyncpg = apg
    pgn.asyncio = _stub_asyncio(sleeps)
    pgn.get_settings = settings_stub
    ln = PgNotifyListener()
    raised = None
    try:
        run(ln._connect())
    except RuntimeError as e:
        raised = str(e)
    assert raised == "nope"
    assert apg.calls == [STUB_DSN] * 10
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0, 60.0]
    assert _rec_msgs(logs, logging.WARNING) == [
        f"Connection attempt {n} failed, retrying in {d:.1f}s: nope"
        for n, d in zip(range(1, 10), sleeps, strict=True)
    ]
    assert _rec_msgs(logs, logging.ERROR) == ["Failed to connect after 10 attempts: nope"]
    assert [bool(r.exc_info) for r in logs if r.levelno == logging.ERROR] == [True]
    assert ln._is_healthy is False and ln._reconnect_attempts == 10


@patched
@caplogs
def test_connect_guard_blocks_entry_at_max(logs):
    # The loop GUARD is separately observable from the give-up raise:
    # entering _connect with the counter already at MAX must not start an
    # attempt at all - pristine `10 < 10` fails the guard, so _connect
    # falls straight off the while and returns. The `<=` twin ENTERS an
    # 11th attempt: its connect raises, the >= MAX arm logs and re-raises
    # - an extra connect call, an extra error record, an exception, and a
    # bumped counter, none of which the pristine path produces.
    sleeps = []
    apg = _Asyncpg([RuntimeError("nope")])
    pgn.asyncpg = apg
    pgn.asyncio = _stub_asyncio(sleeps)
    pgn.get_settings = settings_stub
    ln = PgNotifyListener()
    ln._reconnect_attempts = PgNotifyListener.MAX_RECONNECT_ATTEMPTS
    raised = None
    try:
        run(ln._connect())
    except RuntimeError as e:
        raised = str(e)
    assert raised is None
    assert apg.calls == []
    assert sleeps == []
    assert _rec_msgs(logs, logging.ERROR) == []
    assert ln._reconnect_attempts == PgNotifyListener.MAX_RECONNECT_ATTEMPTS


# ---------------------------------------------------------------- start / stop


@patched
@caplogs
def test_start_resets_subscribes_and_double_start(logs):
    sleeps = []
    apg = _Asyncpg([FakeConn()])
    stub = _stub_asyncio(sleeps)
    pgn.asyncpg = apg
    pgn.asyncio = stub
    pgn.get_settings = settings_stub
    ln = PgNotifyListener()
    ln._reconnect_attempts = 3
    run(ln.start())
    assert ln._is_running is True
    assert ln._reconnect_attempts == 0
    assert len(stub.created) == 1
    # the scheduled coroutine must be the listener loop, judged by CODE
    # IDENTITY against a same-world reference - under the trampoline tree
    # BOTH coroutines report co_name "_trampoline_wrapper", so a name
    # literal is only sound on the pristine tree and fake-fails every key.
    ref = ln._listen_loop()
    assert stub.created[0].cr_code is ref.cr_code
    ref.close()
    stub.created[0].close()
    assert isinstance(ln._listener_task, FakeTask)
    run(ln.start())
    assert ln._is_running is True
    assert apg.calls == [STUB_DSN]
    assert len(stub.created) == 1
    assert _rec_msgs(logs, logging.INFO) == [
        "PgNotifyListener initialized",
        "PgNotifyListener connected to database",
        "PgNotifyListener started",
    ]
    assert _rec_msgs(logs, logging.WARNING) == ["PgNotifyListener already running"]


@patched
def test_start_first_retry_delay_pins_attempts_reset():
    sleeps = []
    apg = _Asyncpg([RuntimeError("nope"), FakeConn()])
    pgn.asyncpg = apg
    pgn.asyncio = _stub_asyncio(sleeps)
    pgn.get_settings = settings_stub
    ln = PgNotifyListener()
    ln._reconnect_attempts = 5
    run(ln.start())
    assert apg.calls == [STUB_DSN, STUB_DSN]
    assert sleeps == [1.0]
    assert ln._reconnect_attempts == 0


@patched
@caplogs
def test_stop_suppresses_close_error_and_clears_state(logs):
    ln = PgNotifyListener()
    task = FakeTask()
    ln._listener_task = task
    conn = FakeConn(close_error=RuntimeError("zap"))
    ln._connection = conn
    ln._is_running = True
    ln._is_healthy = True
    run(ln.stop())
    assert task.cancelled is True
    assert conn.close_calls == 1
    assert ln._is_running is False and ln._is_healthy is False
    assert ln._listener_task is None and ln._connection is None
    assert _rec_msgs(logs, logging.INFO) == [
        "PgNotifyListener initialized",
        "PgNotifyListener stopped",
    ]


# ---------------------------------------------------------------- handlers


@patched
@caplogs
def test_notification_routing_publishes_exact_messages(logs):
    pgn.get_settings = settings_stub
    plan = [
        ("events_new", _EV_NEW, _MSG_NEW),
        ("events_update", _UPD, _MSG_UPD),
        ("detections_new", _DET_NEW, _MSG_DET),
        ("alerts_new", _AL_NEW, _MSG_ALERT),
    ]
    spies = {chan: PublishSpy() for chan, _, _ in plan}

    async def main():
        for chan, js, _ in plan:
            listener = PgNotifyListener(redis_client=spies[chan])
            await listener._handle_notification(chan, js)

    run(main())
    for chan, _, expect in plan:
        assert spies[chan].calls == [((STUB_CHANNEL, expect), {})]
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Received notification on events_new",
        "Published new event notification",
        "Received notification on events_update",
        "Published event update notification",
        "Received notification on detections_new",
        "Published new detection notification",
        "Received notification on alerts_new",
        "Published new alert notification",
    ]
    recv = [r for r in logs if str(r.msg).startswith("Received notification")]
    assert [(r.channel, r.operation, r.table) for r in recv] == [
        ("events_new", "INSERT", "events"),
        ("events_update", "UPDATE", "events"),
        ("detections_new", "INSERT", "detections"),
        ("alerts_new", "INSERT", "alerts"),
    ]
    pub = [r for r in logs if str(r.msg).startswith("Published")]
    assert [r.event_id for r in pub[:2]] == [11, 12]
    assert pub[2].detection_id == 13
    assert pub[3].alert_id == 14


@patched
@caplogs
def test_notification_unknown_bad_payload_and_handler_error(logs):
    pgn.get_settings = settings_stub
    ln = PgNotifyListener(redis_client=PublishSpy())
    run(ln._handle_notification("zzz_channel", _EV_NEW))
    run(ln._handle_notification("events_new", "notjson"))
    boom = PgNotifyListener(redis_client=PublishSpy())

    async def raiser(_payload):
        raise RuntimeError("boom")

    boom._handle_event_new = raiser
    run(boom._handle_notification("events_new", _EV_NEW))
    # A ValueError raised by a HANDLER lands in the parse-error arm too -
    # the first except clause covers handler bodies. Pinning both polarities
    # keeps the two error arms from being swapped or merged.
    vboom = PgNotifyListener(redis_client=PublishSpy())

    async def raiser_ve(_payload):
        raise ValueError("venom")

    vboom._handle_event_new = raiser_ve
    run(vboom._handle_notification("events_new", _EV_NEW))
    assert _rec_msgs(logs, logging.WARNING) == ["Unhandled notification channel: zzz_channel"]
    assert _rec_msgs(logs, logging.ERROR) == [
        "Failed to parse notification payload: Invalid JSON payload: notjson",
        "Error handling notification: boom",
        "Failed to parse notification payload: venom",
    ]
    assert [bool(r.exc_info) for r in logs if r.levelno == logging.ERROR] == [
        False,
        True,
        False,
    ]
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Received notification on zzz_channel",
        "Received notification on events_new",
        "Received notification on events_new",
    ]
    recv = [r for r in logs if r.levelno == logging.DEBUG]
    assert recv[0].channel == "zzz_channel"
    assert recv[0].operation == "INSERT" and recv[0].table == "events"


@patched
@caplogs
def test_redis_publish_failure_logs_per_handler_error(logs):
    pgn.get_settings = settings_stub
    boom = RuntimeError("boom")

    async def main():
        for chan, js in (
            ("events_new", _EV_NEW),
            ("events_update", _UPD),
            ("detections_new", _DET_NEW),
            ("alerts_new", _AL_NEW),
        ):
            listener = PgNotifyListener(redis_client=PublishSpy(fail=boom))
            await listener._handle_notification(chan, js)

    run(main())
    assert _rec_msgs(logs, logging.ERROR) == [
        "Failed to publish event to Redis: boom",
        "Failed to publish event update to Redis: boom",
        "Failed to publish detection to Redis: boom",
        "Failed to publish alert to Redis: boom",
    ]
    # the trailing "Published" debug fires even when the publish raised -
    # the except only logs the error and falls through.
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Received notification on events_new",
        "Published new event notification",
        "Received notification on events_update",
        "Published event update notification",
        "Received notification on detections_new",
        "Published new detection notification",
        "Received notification on alerts_new",
        "Published new alert notification",
    ]
    pub = [r for r in logs if str(r.msg).startswith("Published")]
    assert [r.event_id for r in pub[:2]] == [11, 12]
    assert pub[2].detection_id == 13
    assert pub[3].alert_id == 14


# ---------------------------------------------------------------- listen loop


@patched
@caplogs
def test_listen_loop_reconnects_when_connection_lost(logs):
    sleeps = []
    stub = _stub_asyncio(sleeps)
    pgn.asyncpg = _Asyncpg([FakeConn()])
    pgn.asyncio = stub
    pgn.get_settings = settings_stub
    ln = PgNotifyListener()
    ln._is_running = True
    ln._connection = FakeConn(closed=True)
    stub.sleep.after = lambda _d: setattr(ln, "_is_running", False)
    run(ln._listen_loop())
    assert _rec_msgs(logs, logging.WARNING) == ["Database connection lost, reconnecting..."]
    assert pgn.asyncpg.calls == [STUB_DSN]
    assert sleeps == [1.0]
    assert ln._is_healthy is True


@patched
@caplogs
def test_listen_loop_error_backoff_then_max_attempts(logs):
    sleeps = []
    stub = _stub_asyncio(sleeps)
    pgn.asyncpg = _Asyncpg([FakeConn()])
    pgn.asyncio = stub
    pgn.get_settings = settings_stub
    ln = PgNotifyListener()
    ln._is_running = True
    ln._connection = FakeConn(is_closed_error=RuntimeError("conn-broke"))

    def stop_after_two(delay):
        if len(sleeps) >= 2:
            ln._is_running = False

    stub.sleep.after = stop_after_two
    run(ln._listen_loop())
    assert sleeps == [1.0, 2.0]
    assert ln._reconnect_attempts == 2
    assert _rec_msgs(logs, logging.ERROR) == ["Error in listen loop: conn-broke"] * 2
    assert [bool(r.exc_info) for r in logs if r.levelno == logging.ERROR] == [
        True,
        True,
    ]

    sleeps2 = []
    stub2 = _stub_asyncio(sleeps2)
    pgn.asyncio = stub2
    l2 = PgNotifyListener()
    l2._is_running = True
    l2._reconnect_attempts = 9
    l2._connection = FakeConn(is_closed_error=RuntimeError("conn-broke"))
    run(l2._listen_loop())
    assert sleeps2 == []
    assert _rec_msgs(logs, logging.ERROR)[-1] == (
        "Max reconnection attempts exceeded, stopping listener"
    )


@patched
@caplogs
def test_listen_loop_cancel_logs_info(logs):
    sleeps = []
    stub = _stub_asyncio(sleeps)
    pgn.asyncpg = _Asyncpg([FakeConn()])
    pgn.asyncio = stub
    pgn.get_settings = settings_stub
    ln = PgNotifyListener()
    ln._is_running = True
    ln._connection = FakeConn(closed=False)
    started = asyncio.Event()
    stub.sleep.after = lambda _d: started.set()

    async def main():
        task = asyncio.create_task(ln._listen_loop())
        await started.wait()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    run(main())
    assert sleeps == [1.0]
    assert _rec_msgs(logs, logging.INFO)[-1] == "Listen loop cancelled"


# ---------------------------------------------------------------- callback


@patched
@caplogs
def test_notification_callback_schedules_handler(logs):
    pgn.get_settings = settings_stub
    tasks = []

    def create_task(coro):
        t = REAL.create_task(coro)
        tasks.append(t)
        return t

    pgn.asyncio = SimpleNamespace(
        sleep=REAL.sleep,
        create_task=create_task,
        CancelledError=REAL.CancelledError,
    )
    spy = PublishSpy()
    ln = PgNotifyListener(redis_client=spy)
    raised = None

    async def main():
        nonlocal raised
        try:
            ln._notification_callback(None, 42, "events_new", _EV_NEW)
        except TypeError as e:
            raised = str(e)
        if tasks:
            await asyncio.gather(*tasks)

    run(main())
    assert raised is None
    assert spy.calls == [((STUB_CHANNEL, _MSG_NEW), {})]
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Received notification on events_new",
        "Published new event notification",
    ]
