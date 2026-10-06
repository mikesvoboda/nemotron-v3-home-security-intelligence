"""Campaign #24 (batch-38, battery Z) - `backend/services.stream_manager`.

# TARGET-MODULE: backend.services.stream_manager

Harness contract (b30 sweep, /home/agent/runs/b30-sweep.py): NO pytest
fixtures, NO parametrize, NO monkeypatch - the sweep imports this file
directly and calls every module-level ``test_*`` with zero arguments in
ONE process, flipping os.environ[MUTANT_UNDER_TEST] per key. Everything
async is driven with asyncio.run INSIDE the test body. Seams are patched
through the TARGET MODULE's globals (sm.asyncio.sleep,
sm.asyncio.get_running_loop, sm.cv2) or through constructor dependency
injection (capture_factory, redis_client), always save/restore via the
patched() contextmanager so a mid-test assert failure cannot leak a patch
into the next key's window.

Determinism strategy (the loops are real):
  * asyncio.sleep is swapped for a recorder - backoff/dither SEQUENCES are
    asserted exactly (a mutated 5 -> 55 or a dropped kwarg changes the
    recorded list); the fake awaits the REAL sleep(0) captured at import,
    so cancellation still lands;
  * asyncio.get_running_loop is swapped for a FakeLoop wrapping the real
    one - time() pops a scripted clock so the FPS math is exact (no wall
    floats in any assert), run_in_executor delegates to the real loop so
    the thread-pool paths are genuine;
  * VideoCapture behavior is scripted per call (isOpened / read sequences,
    raise-polarities, and side-effect callbacks that flip manager.running or
    delete the camera at the precise iteration - the ONLY loop exits);
    a script that runs dry sets running=False and returns a CLOSED capture
    so an over-running mutant fails LOUD but terminates (no sweep hangs);
  * Redis is a recording fake: every hset/hgetall/delete call (key +
    mapping COPY) lands in an ordered call list - health payloads are
    compared as WHOLE dicts, so renamed mapping keys, format flips
    (".1f"), str()-drops and status-literal swaps all die;
  * log records are captured from sm.logger (stdlib Logger; the repo's
    ContextFilter only ENRICHES) and asserted on msg + the FULL extra=
    surface as record attributes.

Honesty ledger (EQUIV candidates REGISTERED BY CONSTRUCTION; the sweep
verdict + the per-key probes in the campaign notes are the evidence - a
construction claim is not a verdict claim). Authoring sweep over the 257
survivor keys: RED=248 GREEN=9; after the two KILLABLE-arm tests below:
RED=250 GREEN=7, and the 7 GREENs below are EXACTLY this ledger:
  - _cleanup_stream m5 + remove_stream m7: trailing-comma pops delete the
    None DEFAULT (pop(task_name, ) -> KeyError on a missing key), but both
    pops are GUARDED - the cleanup pop sits behind `if task_name in
    self._background_tasks` (and between its only awaits a cancelled task
    is never re-raced) and the remove pop behind the `not in self._streams`
    early return. The key is always present at the pop, so the deleted
    default is unreachable.
  - _handle_connection_failure m32/m33 (retry_count/last_error overrides
    -> None) and m36/m37 (the two kwargs DELETED): four arms, ONE reason -
    the handler writes EXACTLY those values into the stream context
    (retry_count+1, error_message) under the lock BEFORE awaiting
    _update_health, whose None-fallbacks re-read the same ctx fields. The
    hset mapping is byte-identical in every arm; the battery's state+log+
    health asserts cover the ctx write itself, so the redundancy is
    demonstrated, not assumed.
  - _health_monitoring_loop m51: `break` -> `return` in the read-failure
    exit - the while loop is the LAST statement of the function (nothing
    follows it, no finally); both exits unwind identically (release
    already awaited before the break).
  - BORN in the campaign #24 run's generation (2 slots,
    _health_monitoring_loop; pre-run these lines had fewer mutants -
    battery coverage grew the function): both are break -> return at the
    two in-try exits (disconnect branch, read-failure branch) - the same
    registered construction as m51 above (the while loop is the LAST
    statement of the function, no finally, release already awaited), so
    both exits unwind identically. verdict-0 in the live bank.
  Not equivalent, KILLABLE - the two arms this battery supplies:
  - _health_monitoring_loop m25 (elapsed > 0 -> elapsed > 1): every other
    update arm has elapsed exactly 0 or >= 5; the fractional-elapsed test
    (interval 0.5, clock 0.0->0.5, fps "2.0") is the ONLY 0 < elapsed < 1
    arm in the file.
  - add_stream m1 (`in` -> `not in`): a cleanup-CALL stub is blind to the
    guard direction (the mutant just moves cleanup to the first add and
    leaves the live first connection task pending) - the replace test
    therefore runs the REAL _cleanup_stream against a cancelable parked
    loop and asserts the OLD task is cancelled.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from backend.services import stream_manager as sm

_REAL_SLEEP = asyncio.sleep


# ---------------------------------------------------------------------------
# capture / patch helpers (no fixtures - the sweep calls plain functions)
# ---------------------------------------------------------------------------


class RecordList(logging.Handler):
    """Captures EVERY record emitted through sm.logger while active."""

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
    old_level = sm.logger.level
    sm.logger.addHandler(cap)
    sm.logger.setLevel(logging.DEBUG)
    try:
        yield cap
    finally:
        sm.logger.removeHandler(cap)
        sm.logger.setLevel(old_level)


@contextmanager
def patched(obj: Any, attr: str, value: Any):
    old = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield value
    finally:
        setattr(obj, attr, old)


class FakeLoop:
    """get_running_loop() replacement: scripted time() + delegated
    run_in_executor (the REAL thread pool keeps _release_capture and the
    executor capture path genuine)."""

    def __init__(self, times: list[float]) -> None:
        self._real = asyncio.get_running_loop()
        self._times = times
        self._i = 0

    def time(self) -> float:
        t = self._times[self._i] if self._i < len(self._times) else self._times[-1]
        self._i += 1
        return t

    def is_running(self) -> bool:
        return True

    def run_in_executor(self, executor: Any, fn: Callable[[], Any]) -> Any:
        return self._real.run_in_executor(executor, fn)


class SleepRec:
    """asyncio.sleep replacement: records durations, yields once."""

    def __init__(self) -> None:
        self.slept: list[Any] = []

    async def __call__(self, delay: Any) -> None:
        self.slept.append(delay)
        await _REAL_SLEEP(0)


class FakeRedis:
    """Ordered call log of hset/hgetall/delete; scripted hgetall values."""

    def __init__(
        self, hgetall_values: list[Any] | None = None, raises: list[Exception | None] | None = None
    ) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self._hgetall = list(hgetall_values or [])
        self._raises = list(raises) if raises is not None else []

    def _maybe_raise(self, op: str) -> None:
        if self._raises:
            exc = self._raises.pop(0)
            if exc is not None:
                raise exc

    async def hset(self, key: str, mapping: dict[str, str]) -> None:
        self._maybe_raise("hset")
        self.calls.append(("hset", key, dict(mapping)))

    async def hgetall(self, key: str) -> Any:
        self._maybe_raise("hgetall")
        self.calls.append(("hgetall", key, None))
        return self._hgetall.pop(0) if self._hgetall else {}

    async def delete(self, key: str) -> None:
        self._maybe_raise("delete")
        self.calls.append(("delete", key, None))

    def hsets(self) -> list[tuple[str, dict[str, str]]]:
        return [(op[1], op[2]) for op in self.calls if op[0] == "hset"]


class FakeCapture:
    """Scripted VideoCapture: isOpened bools, read results (bool,
    ('raise', exc), or a callback invoked BEFORE the scripted answer),
    release counting. Script exhaustion CLOSES the capture (loud-but-safe:
    an over-running mutant ends the loop instead of hanging the sweep)."""

    READ_CAP = 400

    def __init__(
        self,
        opened: list[bool] | None = None,
        reads: list[Any] | None = None,
        mgr: Any = None,
    ) -> None:
        self._opened = list(opened if opened is not None else [True])
        self._reads = list(reads or [True])
        self.mgr = mgr
        self.released = 0
        self.reads_done = 0

    def isOpened(self) -> bool:
        return self._opened.pop(0) if len(self._opened) > 1 else self._opened[0]

    def _force_stop(self) -> tuple[Any, Any]:
        self._opened = [False]
        if self.mgr is not None:
            self.mgr.running = False
        return False, None

    def read(self) -> tuple[Any, Any]:
        self.reads_done += 1
        if self.reads_done > self.READ_CAP:
            return self._force_stop()
        item = self._reads.pop(0) if len(self._reads) > 1 else self._reads[0]
        if isinstance(item, tuple) and item and item[0] == "raise":
            raise item[1]
        if callable(item):
            item()
            if self.reads_done > self.READ_CAP:
                return self._force_stop()
            return True, object()
        return bool(item), object() if item else None

    def set(self, prop: Any, value: Any) -> None:  # pragma: no cover - not mutated here
        raise AssertionError("set() outside _create_capture_sync")

    def release(self) -> None:
        self.released += 1


def scripted_factory(mgr: sm.StreamManager, script: list[Any]):
    """capture_factory: script items are FakeCapture instances, callables
    (called with the url; may return a capture or set manager state), or
    ('raise', exc). Exhaustion: running=False + CLOSED capture."""

    calls: list[Any] = []

    def make(rtsp_url: str) -> Any:
        calls.append(rtsp_url)
        if not script:
            mgr.running = False
            return FakeCapture(opened=[False])
        item = script.pop(0)
        if isinstance(item, tuple) and item and item[0] == "raise":
            raise item[1]
        if callable(item):
            out = item(rtsp_url)
            return out if out is not None else FakeCapture(opened=[True])
        return item

    make.calls = calls  # type: ignore[attr-defined]
    return make


class FakeCV2:
    """sm.cv2 replacement: constant sentinels + a recording VideoCapture."""

    CAP_FFMPEG = "SENT_FFMPEG"
    CAP_PROP_OPEN_TIMEOUT_MSEC = "SENT_OPEN_TO"
    CAP_PROP_READ_TIMEOUT_MSEC = "SENT_READ_TO"

    def __init__(self) -> None:
        self.made: list[tuple[Any, Any]] = []

    def VideoCapture(self, url: Any, api: Any) -> Any:
        cap = _FakeSyncCapture()
        self.made.append((url, api))
        return cap


class _FakeSyncCapture:
    def __init__(self) -> None:
        self.sets: list[tuple[Any, Any]] = []

    def set(self, prop: Any, value: Any) -> None:
        self.sets.append((prop, value))


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# __init__ / start / stop
# ---------------------------------------------------------------------------


def test_init_stores_every_dependency_exactly() -> None:
    redis = FakeRedis()
    factory = object()
    with logcap() as cap:
        mgr = sm.StreamManager(redis, capture_factory=factory, health_update_interval=9.5)
    assert mgr.redis_client is redis
    assert mgr._capture_factory is factory
    assert mgr._health_update_interval == 9.5
    assert mgr._streams == {}
    assert mgr._background_tasks == {}
    assert mgr.running is False
    assert mgr._loop is None
    assert isinstance(mgr._lock, asyncio.Lock)
    rec = cap.one("StreamManager initialized")
    assert cap.msgs() == ["StreamManager initialized"]
    assert rec.health_update_interval == 9.5


def test_init_default_health_interval_is_the_constant() -> None:
    with logcap() as cap:
        mgr = sm.StreamManager(FakeRedis())
    assert mgr._health_update_interval == 5.0
    assert mgr._health_update_interval == sm.DEFAULT_HEALTH_UPDATE_INTERVAL
    assert cap.one("StreamManager initialized").health_update_interval == 5.0


def test_start_captures_the_running_loop_and_logs() -> None:
    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        with logcap() as cap:
            await mgr.start()
        assert mgr.running is True
        assert mgr._loop is asyncio.get_running_loop()
        assert cap.msgs() == ["Starting StreamManager", "StreamManager started successfully"]

    run(main())


def test_start_when_already_running_warns_and_returns() -> None:
    mgr = sm.StreamManager(FakeRedis())
    mgr.running = True
    sentinel_loop = object()
    mgr._loop = sentinel_loop

    async def main() -> None:
        with logcap() as cap:
            await mgr.start()
        assert cap.msgs() == ["StreamManager already running"]
        assert mgr.running is True
        assert mgr._loop is sentinel_loop

    run(main())


def test_start_without_running_loop_raises_with_exact_message() -> None:
    mgr = sm.StreamManager(FakeRedis())

    def boom() -> Any:
        raise RuntimeError("NO LOOP HERE")

    async def main() -> None:
        with patched(sm.asyncio, "get_running_loop", boom), logcap() as cap:
            try:
                await mgr.start()
                raise AssertionError("expected RuntimeError")
            except RuntimeError as exc:
                assert str(exc) == (
                    "StreamManager MUST be started within an async context. "
                    "No running event loop detected."
                )
        rec = cap.one(
            "StreamManager MUST be started within an async context. No running event loop detected."
        )
        assert rec.error == "NO LOOP HERE"
        assert mgr.running is False

    run(main())


def test_start_rejects_a_none_loop() -> None:
    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        with patched(sm.asyncio, "get_running_loop", lambda: None), logcap() as cap:
            try:
                await mgr.start()
                raise AssertionError("expected RuntimeError")
            except RuntimeError as exc:
                assert str(exc) == "Event loop capture failed or loop is not running."
        assert cap.one("Event loop capture failed or loop is not running.")
        assert mgr.running is False

    run(main())


def test_start_rejects_a_not_running_loop() -> None:
    class _IdleLoop(FakeLoop):
        def is_running(self) -> bool:
            return False

    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        idle = _IdleLoop([0.0])
        with patched(sm.asyncio, "get_running_loop", lambda: idle), logcap() as cap:
            try:
                await mgr.start()
                raise AssertionError("expected RuntimeError")
            except RuntimeError as exc:
                assert str(exc) == "Event loop capture failed or loop is not running."
        assert cap.one("Event loop capture failed or loop is not running.")
        assert mgr.running is False

    run(main())


def test_stop_cancels_tasks_releases_captures_and_resets_state() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        await mgr.start()

        async def forever() -> None:
            await _REAL_SLEEP(3600)

        task = asyncio.create_task(forever())
        mgr._background_tasks["connection_cam1"] = task
        cap_fake = FakeCapture(opened=[True])
        mgr._streams["cam1"] = {
            "rtsp_url": "rtsp://u",
            "capture": cap_fake,
            "retry_count": 0,
            "last_error": None,
            "connection_time": None,
        }
        with logcap() as log:
            await mgr.stop()
        assert task.done() and task.cancelled()
        assert cap_fake.released == 1
        assert mgr.running is False
        assert mgr._streams == {}
        assert mgr._background_tasks == {}
        assert mgr._loop is None
        assert log.msgs() == [
            "Stopping StreamManager",
            "Cancelled background task: connection_cam1",
            "StreamManager stopped",
        ]

    run(main())


# ---------------------------------------------------------------------------
# add_stream / remove_stream / get_stream_health
# ---------------------------------------------------------------------------


def test_add_stream_builds_the_exact_context_spawns_named_task_and_health() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)
    seen: list[tuple[Any, ...]] = []

    async def fake_loop(camera_id: Any, rtsp_url: Any) -> None:
        seen.append((camera_id, rtsp_url))

    async def main() -> None:
        await mgr.start()
        with patched(mgr, "_connection_loop", fake_loop), logcap() as cap:
            await mgr.add_stream("cam1", "rtsp://host/live")
            assert list(mgr._background_tasks.keys()) == ["connection_cam1"]
        task = mgr._background_tasks["connection_cam1"]
        await task
        assert seen == [("cam1", "rtsp://host/live")]
        assert mgr._streams["cam1"] == {
            "rtsp_url": "rtsp://host/live",
            "capture": None,
            "retry_count": 0,
            "last_error": None,
            "connection_time": None,
        }
        assert redis.hsets() == [
            (
                "hsi:stream:health:cam1",
                {"status": "connecting", "retry_count": "0"},
            )
        ]
        rec = cap.one("Adding stream for camera cam1")
        assert rec.camera_id == "cam1"
        assert rec.rtsp_url == "rtsp://host/live"

    run(main())


def test_add_stream_replaces_an_existing_camera_cleanly() -> None:
    # THE observable of the replace guard `if camera_id in self._streams:`
    # is that the FIRST connection task gets CANCELLED by the real
    # _cleanup_stream (a cleanup-call stub cannot see an in/not-in flip:
    # swapping the test moved the call to the first add but kept the
    # count - hence this lives-state assert instead).
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)
    gate: asyncio.Event | None = None

    async def parked_loop(camera_id: Any, rtsp_url: Any) -> None:
        assert gate is not None
        await gate.wait()  # cancelable park - only cleanup may end it

    async def done_loop(camera_id: Any, rtsp_url: Any) -> None:
        return None

    async def main() -> None:
        nonlocal gate
        gate = asyncio.Event()
        await mgr.start()
        with patched(mgr, "_connection_loop", parked_loop):
            await mgr.add_stream("cam1", "rtsp://old")
            task1 = mgr._background_tasks["connection_cam1"]
        with patched(mgr, "_connection_loop", done_loop):
            await mgr.add_stream("cam1", "rtsp://new")
            task2 = mgr._background_tasks["connection_cam1"]
            await task2
        assert task1.cancelled(), "replace must cancel the old connection task"
        assert mgr._streams["cam1"]["rtsp_url"] == "rtsp://new"
        assert mgr._streams["cam1"]["retry_count"] == 0
        assert mgr._streams["cam1"]["capture"] is None
        assert mgr._streams["cam1"]["last_error"] is None
        assert redis.hsets() == [
            (
                "hsi:stream:health:cam1",
                {"status": "connecting", "retry_count": "0"},
            ),
            (
                "hsi:stream:health:cam1",
                {"status": "connecting", "retry_count": "0"},
            ),
        ]
        task1.cancel()

    run(main())


def test_remove_stream_deletes_task_stream_and_redis_key() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)
    cleanup_calls: list[Any] = []

    async def fake_cleanup(camera_id: Any) -> None:
        cleanup_calls.append(camera_id)

    async def main() -> None:
        mgr._streams["cam1"] = {
            "rtsp_url": "rtsp://u",
            "capture": None,
            "retry_count": 0,
            "last_error": None,
            "connection_time": None,
        }
        with patched(mgr, "_cleanup_stream", fake_cleanup), logcap() as cap:
            await mgr.remove_stream("cam1")
        assert cleanup_calls == ["cam1"]
        assert mgr._streams == {}
        assert redis.calls == [("delete", "hsi:stream:health:cam1", None)]
        assert cap.msgs() == ["Removing stream for camera cam1"]

    run(main())


def test_remove_stream_unknown_camera_is_a_logged_noop() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        with logcap() as cap:
            await mgr.remove_stream("ghost")
        assert cap.msgs() == ["No stream to remove for camera ghost"]
        assert redis.calls == []
        assert mgr._streams == {}

    run(main())


def test_get_stream_health_decodes_bytes_and_pins_the_key() -> None:
    redis = FakeRedis(
        hgetall_values=[
            {b"status": b"connected", b"fps": b"12.5", "retry_count": "2"},
            {"status": "connected"},
        ]
    )
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        first = await mgr.get_stream_health("cam1")
        assert first == {"status": "connected", "fps": "12.5", "retry_count": "2"}
        second = await mgr.get_stream_health("cam2")
        assert second == {"status": "connected"}
        assert [c[1] for c in redis.calls] == [
            "hsi:stream:health:cam1",
            "hsi:stream:health:cam2",
        ]

    run(main())


def test_get_stream_health_empty_hash_returns_none() -> None:
    redis = FakeRedis(hgetall_values=[{}])
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        assert await mgr.get_stream_health("cam1") is None

    run(main())


def test_get_stream_health_redis_error_warns_and_returns_none() -> None:
    redis = FakeRedis(raises=[RuntimeError("redis down")])
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        with logcap() as cap:
            assert await mgr.get_stream_health("cam1") is None
        assert cap.msgs() == ["Failed to get stream health for cam1: redis down"]
        rec = cap.one("Failed to get stream health for cam1: redis down")
        assert rec.camera_id == "cam1"
        assert rec.error == "redis down"

    run(main())


# ---------------------------------------------------------------------------
# _update_health (direct - the mapping is asserted WHOLE)
# ---------------------------------------------------------------------------


def _stream_dict(**over: Any) -> dict[str, Any]:
    base = {
        "rtsp_url": "rtsp://u",
        "capture": None,
        "retry_count": 0,
        "last_error": None,
        "connection_time": None,
    }
    base.update(over)
    return base


def test_update_health_minimal_mapping_and_key() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        await mgr._update_health("cam1", "connecting")
        assert redis.calls == [
            ("hset", "hsi:stream:health:cam1", {"status": "connecting", "retry_count": "0"})
        ]

    run(main())


def test_update_health_carries_stream_context_fields() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)
    mgr._streams["cam1"] = _stream_dict(
        retry_count=3, last_error="wire down", connection_time="TS-CONN"
    )

    async def main() -> None:
        await mgr._update_health("cam1", "connected")
        assert redis.hsets() == [
            (
                "hsi:stream:health:cam1",
                {
                    "status": "connected",
                    "connection_time": "TS-CONN",
                    "retry_count": "3",
                    "last_error": "wire down",
                },
            )
        ]

    run(main())


def test_update_health_overrides_beat_stream_context() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)
    mgr._streams["cam1"] = _stream_dict(retry_count=3, last_error="old")

    async def main() -> None:
        await mgr._update_health("cam1", "reconnecting", retry_count=7, last_error="fresh")
        assert redis.hsets() == [
            (
                "hsi:stream:health:cam1",
                {
                    "status": "reconnecting",
                    "retry_count": "7",
                    "last_error": "fresh",
                },
            )
        ]

    run(main())


def test_update_health_fps_is_one_decimal_and_zero_survives() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        await mgr._update_health("camA", "connected", fps=29.876)
        await mgr._update_health("camB", "connected", fps=0.0)
        assert redis.hsets() == [
            (
                "hsi:stream:health:camA",
                {"status": "connected", "retry_count": "0", "fps": "29.9"},
            ),
            (
                "hsi:stream:health:camB",
                {"status": "connected", "retry_count": "0", "fps": "0.0"},
            ),
        ]

    run(main())


def test_update_health_redis_failure_warns_with_exact_extras() -> None:
    redis = FakeRedis(raises=[RuntimeError("redis is dead")])
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        with logcap() as cap:
            await mgr._update_health("cam1", "connected")
        assert cap.msgs() == ["Failed to update health for camera cam1: redis is dead"]
        rec = cap.one("Failed to update health for camera cam1: redis is dead")
        assert rec.camera_id == "cam1"
        assert rec.error == "redis is dead"

    run(main())


# ---------------------------------------------------------------------------
# _handle_connection_failure + the backoff ladder THROUGH the handler
# ---------------------------------------------------------------------------


def test_handle_failure_unknown_camera_is_silent() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        sleep = SleepRec()
        with patched(sm.asyncio, "sleep", sleep), logcap() as cap:
            await mgr._handle_connection_failure("ghost", "boom")
        assert cap.msgs() == []
        assert redis.calls == []
        assert sleep.slept == []

    run(main())


def test_handle_failure_advances_state_backoff_log_and_health() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)
    mgr._streams["cam1"] = _stream_dict()

    async def main() -> None:
        sleep = SleepRec()
        with patched(sm.asyncio, "sleep", sleep), logcap() as cap:
            await mgr._handle_connection_failure("cam1", "line cut")
        assert mgr._streams["cam1"]["retry_count"] == 1
        assert mgr._streams["cam1"]["last_error"] == "line cut"
        assert sleep.slept == [5]
        assert cap.msgs() == ["Stream connection failed for camera cam1, retrying in 5s"]
        rec = cap.one("Stream connection failed for camera cam1, retrying in 5s")
        assert rec.camera_id == "cam1"
        assert rec.error == "line cut"
        assert rec.retry_count == 1
        assert rec.backoff_seconds == 5
        assert redis.hsets() == [
            (
                "hsi:stream:health:cam1",
                {
                    "status": "reconnecting",
                    "retry_count": "1",
                    "last_error": "line cut",
                },
            )
        ]

    run(main())


def test_backoff_ladder_five_ten_twenty_forty_capped_sixty() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        for retry, expected in [(0, 5), (1, 10), (2, 20), (3, 40), (4, 60), (9, 60)]:
            mgr._streams["camX"] = _stream_dict(retry_count=retry)
            sleep = SleepRec()
            with patched(sm.asyncio, "sleep", sleep):
                await mgr._handle_connection_failure("camX", "e")
            assert sleep.slept == [expected], (retry, sleep.slept)

    run(main())


# ---------------------------------------------------------------------------
# _connection_loop: success / closed-capture / raising-capture / cancel
# ---------------------------------------------------------------------------


def test_connection_loop_success_stores_capture_resets_and_monitors() -> None:
    redis = FakeRedis()
    cap_fake = FakeCapture(opened=[True])
    mgr = sm.StreamManager(redis, capture_factory=lambda _url: None)

    async def fake_monitor(camera_id: Any, capture: Any) -> None:
        monitor_calls.append((camera_id, capture))
        mgr.running = False

    monitor_calls: list[tuple[Any, Any]] = []

    async def main() -> None:
        await mgr.start()
        mgr._streams["cam1"] = _stream_dict(
            retry_count=7, last_error="old", connection_time="stale"
        )
        factory = scripted_factory(mgr, [cap_fake])
        with (
            patched(mgr, "_capture_factory", factory),
            patched(mgr, "_health_monitoring_loop", fake_monitor),
            logcap() as cap,
        ):
            await mgr._connection_loop("cam1", "rtsp://h/s?x=1")
        assert monitor_calls == [("cam1", cap_fake)]
        ctx = mgr._streams["cam1"]
        assert ctx["capture"] is cap_fake
        assert ctx["retry_count"] == 0
        assert ctx["last_error"] is None
        stamp = datetime.fromisoformat(str(ctx["connection_time"]))
        assert stamp.tzinfo is not None
        assert cap.msgs() == ["Stream connected for camera cam1"]
        assert cap.one("Stream connected for camera cam1").camera_id == "cam1"
        connected = [h for h in redis.hsets() if h[1]["status"] == "connected"]
        assert connected == [
            (
                "hsi:stream:health:cam1",
                {
                    "status": "connected",
                    "connection_time": ctx["connection_time"],
                    "retry_count": "0",
                },
            )
        ]
        assert factory.calls == ["rtsp://h/s?x=1"]

    run(main())


class FailureSpy:
    """async _handle_connection_failure replacement: records (camera_id,
    error_message) EXACTLY and stops the loop by flipping running."""

    def __init__(self, mgr: sm.StreamManager) -> None:
        self.mgr = mgr
        self.calls: list[tuple[Any, ...]] = []

    async def __call__(self, camera_id: Any, error_message: Any) -> None:
        self.calls.append((camera_id, error_message))
        self.mgr.running = False


def test_connection_loop_closed_capture_takes_the_failure_branch() -> None:
    cap_fake = FakeCapture(opened=[False])
    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        await mgr.start()
        mgr._streams["cam1"] = _stream_dict()
        spy = FailureSpy(mgr)
        factory = scripted_factory(mgr, [cap_fake])
        with (
            patched(mgr, "_capture_factory", factory),
            patched(mgr, "_handle_connection_failure", spy),
        ):
            await mgr._connection_loop("cam1", "rtsp://x")
        assert spy.calls == [("cam1", "Failed to open stream")]
        assert factory.calls == ["rtsp://x"]

    run(main())


def test_connection_loop_factory_raise_is_swallowed_to_open_failure() -> None:
    # _create_capture catches the factory's OSError, logs it with its own
    # extras and returns None, so the connection loop takes the SAME
    # "Failed to open stream" branch as a closed capture - both the error
    # log and the failure payload are pinned.
    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        await mgr.start()
        mgr._streams["cam1"] = _stream_dict()
        spy = FailureSpy(mgr)
        factory = scripted_factory(mgr, [("raise", OSError("tcp refused"))])
        with (
            patched(mgr, "_capture_factory", factory),
            patched(mgr, "_handle_connection_failure", spy),
            logcap() as cap,
        ):
            await mgr._connection_loop("cam1", "rtsp://x")
        assert spy.calls == [("cam1", "Failed to open stream")]
        rec = cap.one("Failed to create capture for rtsp://x: tcp refused")
        assert rec.rtsp_url == "rtsp://x"
        assert rec.error == "tcp refused"

    run(main())


def test_connection_loop_cancel_propagates_after_debug_log() -> None:
    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        await mgr.start()
        mgr._streams["cam1"] = _stream_dict()

        def cancel_factory(url: Any) -> Any:
            raise asyncio.CancelledError()

        with patched(mgr, "_capture_factory", cancel_factory), logcap() as cap:
            try:
                await mgr._connection_loop("cam1", "rtsp://x")
                raise AssertionError("expected CancelledError")
            except asyncio.CancelledError:
                pass
        assert cap.msgs() == ["Connection loop cancelled for camera cam1"]

    run(main())


def test_connection_loop_exits_when_camera_removed() -> None:
    redis = FakeRedis()
    mgr = sm.StreamManager(redis)

    async def main() -> None:
        await mgr.start()
        mgr._streams["cam1"] = _stream_dict()

        def evict(url: Any) -> Any:
            mgr._streams.pop("cam1", None)
            return FakeCapture(opened=[False])

        factory = scripted_factory(mgr, [evict])
        with patched(mgr, "_capture_factory", factory), patched(sm.asyncio, "sleep", SleepRec()):
            await mgr._connection_loop("cam1", "rtsp://x")
        assert "cam1" not in mgr._streams

    run(main())


def test_connection_loop_exits_when_manager_stopped() -> None:
    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        await mgr.start()
        mgr._streams["cam1"] = _stream_dict()

        def stopper(url: Any) -> Any:
            mgr.running = False
            return FakeCapture(opened=[False])

        factory = scripted_factory(mgr, [stopper])
        with patched(mgr, "_capture_factory", factory), patched(sm.asyncio, "sleep", SleepRec()):
            await mgr._connection_loop("cam1", "rtsp://x")
        assert mgr.running is False
        assert mgr._streams["cam1"]["retry_count"] == 1

    run(main())


# ---------------------------------------------------------------------------
# _health_monitoring_loop (scripted loop exits + FakeLoop clock)
# ---------------------------------------------------------------------------


def test_health_loop_disconnect_releases_and_exits() -> None:
    redis = FakeRedis()
    cap_fake = FakeCapture(opened=[False])
    mgr = sm.StreamManager(redis)
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
    cap_fake.mgr = mgr

    async def main() -> None:
        loop = FakeLoop([0.0])
        with patched(sm.asyncio, "get_running_loop", lambda: loop), logcap() as cap:
            await mgr._health_monitoring_loop("cam1", cap_fake)
        assert cap.msgs() == ["Stream disconnected for camera cam1"]
        assert cap_fake.released == 1

    run(main())


def test_health_loop_read_failure_releases_and_exits() -> None:
    redis = FakeRedis()
    cap_fake = FakeCapture(opened=[True], reads=[False])
    mgr = sm.StreamManager(redis)
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
    cap_fake.mgr = mgr

    async def main() -> None:
        loop = FakeLoop([0.0])
        with patched(sm.asyncio, "get_running_loop", lambda: loop), logcap() as cap:
            await mgr._health_monitoring_loop("cam1", cap_fake)
        assert cap.msgs() == ["Failed to read frame for camera cam1"]
        assert cap_fake.released == 1

    run(main())


def test_health_loop_fps_math_exact_and_dither_sequence() -> None:
    redis = FakeRedis()
    # scripted clock: start 0.0; iter1 current 5.0 (elapsed 5.0 >= 5.0,
    # ONE frame -> fps 1/5 = 0.2 -> "0.2", frame_count resets); iter2
    # current 7.0 (elapsed 2.0 < 5.0 -> no update, frame count CARRIES);
    # iter3's read callback stops the manager and current 12.5 (elapsed
    # 7.5 >= 5.0 -> fps 2/7.5 = 0.2666 -> "0.3" - this arm pins the
    # rounding format AND that the carry feeds the numerator; a reset-in-
    # the-wrong-place mutant says "0.1", a "%.2f" flip says "0.27"). The
    # stop-callback is the ONLY loop exit, so slept has all three dithers.
    cap_fake = FakeCapture(
        opened=[True],
        reads=[True, True, lambda: setattr(mgr, "running", False)],
    )
    mgr = sm.StreamManager(redis, health_update_interval=5.0)
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
    cap_fake.mgr = mgr

    async def main() -> None:
        loop = FakeLoop([0.0, 5.0, 7.0, 12.5])
        sleep = SleepRec()
        with (
            patched(sm.asyncio, "get_running_loop", lambda: loop),
            patched(sm.asyncio, "sleep", sleep),
        ):
            await mgr._health_monitoring_loop("cam1", cap_fake)
        assert redis.hsets() == [
            (
                "hsi:stream:health:cam1",
                {"status": "connected", "retry_count": "0", "fps": "0.2"},
            ),
            (
                "hsi:stream:health:cam1",
                {"status": "connected", "retry_count": "0", "fps": "0.3"},
            ),
        ]
        assert sleep.slept == [0.033, 0.033, 0.033]
        assert cap_fake.reads_done == 3

    run(main())


def test_health_loop_zero_elapsed_records_zero_fps() -> None:
    redis = FakeRedis()
    # interval 0.0 makes the FIRST iteration trip the update with ZERO
    # elapsed (clock pinned at 7.0) - the `elapsed > 0` guard answers 0.0
    # (fps would ZeroDivisionError without the guard). The read callback
    # stops the manager so the loop ends after exactly one iteration.
    cap_fake = FakeCapture(
        opened=[True],
        reads=[lambda: setattr(mgr, "running", False)],
    )
    mgr = sm.StreamManager(redis, health_update_interval=0.0)
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
    cap_fake.mgr = mgr

    async def main() -> None:
        loop = FakeLoop([7.0, 7.0])
        sleep = SleepRec()
        with (
            patched(sm.asyncio, "get_running_loop", lambda: loop),
            patched(sm.asyncio, "sleep", sleep),
        ):
            await mgr._health_monitoring_loop("cam1", cap_fake)
        assert redis.hsets() == [
            (
                "hsi:stream:health:cam1",
                {"status": "connected", "retry_count": "0", "fps": "0.0"},
            )
        ]
        assert sleep.slept == [0.033]

    run(main())


def test_health_loop_fractional_elapsed_computes_real_fps() -> None:
    # The `if elapsed > 0` guard is ONLY reachable-with-work between 0 and
    # interval... no: it is the ZERO-vs-TINY discriminator. interval 0.5,
    # clock 0.0 -> 0.5: elapsed 0.5 fires the update (>= pins the boundary
    # too) and shipped computes 1/0.5 = "2.0". A mutant flipping the guard
    # to `elapsed > 1` answers 0.0 -> "0.0" for every sub-second update -
    # this test is the ONLY arm in the battery where 0 < elapsed < 1.
    redis = FakeRedis()
    cap_fake = FakeCapture(
        opened=[True],
        reads=[lambda: setattr(mgr, "running", False)],
    )
    mgr = sm.StreamManager(redis, health_update_interval=0.5)
    cap_fake.mgr = mgr
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)

    async def main() -> None:
        loop = FakeLoop([0.0, 0.5])
        sleep = SleepRec()
        with (
            patched(sm.asyncio, "get_running_loop", lambda: loop),
            patched(sm.asyncio, "sleep", sleep),
        ):
            await mgr._health_monitoring_loop("cam1", cap_fake)
        assert redis.hsets() == [
            (
                "hsi:stream:health:cam1",
                {"status": "connected", "retry_count": "0", "fps": "2.0"},
            )
        ]
        assert sleep.slept == [0.033]

    run(main())


def test_health_loop_exception_releases_logs_and_exits() -> None:
    redis = FakeRedis()
    boom = RuntimeError("sensor fused")
    cap_fake = FakeCapture(opened=[True], reads=[("raise", boom)])
    mgr = sm.StreamManager(redis)
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
    cap_fake.mgr = mgr

    async def main() -> None:
        loop = FakeLoop([0.0])
        with patched(sm.asyncio, "get_running_loop", lambda: loop), logcap() as cap:
            await mgr._health_monitoring_loop("cam1", cap_fake)
        assert cap.msgs() == ["Error in health monitoring for camera cam1: sensor fused"]
        rec = cap.one("Error in health monitoring for camera cam1: sensor fused")
        assert rec.camera_id == "cam1"
        assert rec.error == "sensor fused"
        assert cap_fake.released == 1

    run(main())


def test_health_loop_cancel_releases_then_reraises() -> None:
    cap_fake = FakeCapture(opened=[True], reads=[("raise", asyncio.CancelledError())])
    mgr = sm.StreamManager(FakeRedis())
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
    cap_fake.mgr = mgr

    async def main() -> None:
        loop = FakeLoop([0.0])
        with patched(sm.asyncio, "get_running_loop", lambda: loop):
            try:
                await mgr._health_monitoring_loop("cam1", cap_fake)
                raise AssertionError("expected CancelledError")
            except asyncio.CancelledError:
                pass
        assert cap_fake.released == 1

    run(main())


def test_health_loop_exits_when_camera_evicted_midloop() -> None:
    cap_fake = FakeCapture(
        opened=[True],
        reads=[
            lambda: None,
            lambda: mgr._streams.pop("cam1", None),
        ],
    )
    mgr = sm.StreamManager(FakeRedis(), health_update_interval=100.0)
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
    cap_fake.mgr = mgr

    async def main() -> None:
        loop = FakeLoop([0.0, 1.0, 2.0])
        sleep = SleepRec()
        with (
            patched(sm.asyncio, "get_running_loop", lambda: loop),
            patched(sm.asyncio, "sleep", sleep),
        ):
            await mgr._health_monitoring_loop("cam1", cap_fake)
        assert "cam1" not in mgr._streams
        assert sleep.slept == [0.033, 0.033]
        assert cap_fake.released == 0

    run(main())


def test_health_loop_exits_when_manager_stopped_midloop() -> None:
    cap_fake = FakeCapture(opened=[True], reads=[lambda: setattr(mgr, "running", False)])
    mgr = sm.StreamManager(FakeRedis(), health_update_interval=100.0)
    mgr.running = True
    mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
    cap_fake.mgr = mgr

    async def main() -> None:
        loop = FakeLoop([0.0, 1.0])
        sleep = SleepRec()
        with (
            patched(sm.asyncio, "get_running_loop", lambda: loop),
            patched(sm.asyncio, "sleep", sleep),
        ):
            await mgr._health_monitoring_loop("cam1", cap_fake)
        assert mgr.running is False
        assert sleep.slept == [0.033]

    run(main())


# ---------------------------------------------------------------------------
# _release_capture / _cleanup_stream / _create_capture / _create_capture_sync
# ---------------------------------------------------------------------------


def test_release_capture_runs_in_the_executor_and_swallows_errors() -> None:
    cap_fake = FakeCapture(opened=[True])
    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        await mgr._release_capture(cap_fake)
        assert cap_fake.released == 1

        class _NoLoop:
            def run_in_executor(self, *a: Any) -> Any:
                raise RuntimeError("no loop here")

        with patched(sm.asyncio, "get_running_loop", lambda: _NoLoop()), logcap() as cap:
            await mgr._release_capture(cap_fake)
        assert cap_fake.released == 1
        assert cap.msgs() == ["Error releasing capture: no loop here"]

    run(main())


def test_cleanup_stream_cancels_task_and_releases_capture() -> None:
    released: list[Any] = []
    mgr = sm.StreamManager(FakeRedis())

    async def fake_release(capture: Any) -> None:
        released.append(capture)

    async def main() -> None:
        await mgr.start()

        async def forever() -> None:
            await _REAL_SLEEP(3600)

        task = asyncio.create_task(forever())
        mgr._background_tasks["connection_cam1"] = task
        cap_fake = FakeCapture(opened=[True])
        mgr._streams["cam1"] = _stream_dict(capture=cap_fake)
        cap_fake.mgr = mgr
        with patched(mgr, "_release_capture", fake_release):
            await mgr._cleanup_stream("cam1")
        assert task.done() and task.cancelled()
        assert "connection_cam1" not in mgr._background_tasks
        assert released == [cap_fake]
        assert mgr._streams["cam1"]["capture"] is None

    run(main())


def test_cleanup_stream_no_task_no_capture_is_quiet() -> None:
    released: list[Any] = []
    mgr = sm.StreamManager(FakeRedis())

    async def fake_release(capture: Any) -> None:
        released.append(capture)

    async def main() -> None:
        mgr._streams["cam9"] = _stream_dict(capture=None)
        with patched(mgr, "_release_capture", fake_release):
            await mgr._cleanup_stream("cam9")
        assert released == []
        assert mgr._streams["cam9"]["capture"] is None

        mgr._streams.pop("cam9")
        await mgr._cleanup_stream("ghost")
        assert released == []

    run(main())


def test_create_capture_prefers_the_injected_factory() -> None:
    made = FakeCapture(opened=[True])
    mgr = sm.StreamManager(FakeRedis(), capture_factory=lambda _url: made)

    async def main() -> None:
        assert await mgr._create_capture("rtsp://a") is made

    run(main())


def test_create_capture_falls_back_to_executor_and_returns_sync_capture() -> None:
    mgr = sm.StreamManager(FakeRedis())
    mgr._capture_factory = None
    cv2f = FakeCV2()

    async def main() -> None:
        with patched(sm, "cv2", cv2f):
            cap = await mgr._create_capture("rtsp://b")
        assert cap is not None
        assert cv2f.made == [("rtsp://b", "SENT_FFMPEG")]
        assert cap.sets == [("SENT_OPEN_TO", 10000), ("SENT_READ_TO", 5000)]

    run(main())


def test_create_capture_error_path_logs_and_returns_none() -> None:
    mgr = sm.StreamManager(FakeRedis())
    mgr._capture_factory = None
    cv2f = FakeCV2()

    class _Boom:
        def run_in_executor(self, executor: Any, fn: Any) -> Any:
            raise OSError("fork failed")

    async def main() -> None:
        with (
            patched(sm, "cv2", cv2f),
            patched(sm.asyncio, "get_running_loop", lambda: _Boom()),
            logcap() as cap,
        ):
            assert await mgr._create_capture("rtsp://bad") is None
        assert cap.msgs() == ["Failed to create capture for rtsp://bad: fork failed"]
        rec = cap.one("Failed to create capture for rtsp://bad: fork failed")
        assert rec.rtsp_url == "rtsp://bad"
        assert rec.error == "fork failed"

    run(main())


def test_create_capture_factory_exception_is_swallowed_to_none() -> None:
    def bad_factory(url: str) -> Any:
        raise ValueError("nope")

    mgr = sm.StreamManager(FakeRedis(), capture_factory=bad_factory)

    async def main() -> None:
        with logcap() as cap:
            assert await mgr._create_capture("rtsp://z") is None
        assert cap.msgs() == ["Failed to create capture for rtsp://z: nope"]
        rec = cap.one("Failed to create capture for rtsp://z: nope")
        assert rec.rtsp_url == "rtsp://z"
        assert rec.error == "nope"

    run(main())


def test_create_capture_sync_builds_ffmpeg_capture_with_timeouts() -> None:
    mgr = sm.StreamManager(FakeRedis())
    cv2f = FakeCV2()
    with patched(sm, "cv2", cv2f):
        cap = mgr._create_capture_sync("rtsp://s")
    assert cv2f.made == [("rtsp://s", "SENT_FFMPEG")]
    assert cap.sets == [("SENT_OPEN_TO", 10000), ("SENT_READ_TO", 5000)]


# ---------------------------------------------------------------------------
# async context manager surface
# ---------------------------------------------------------------------------


def test_async_context_manager_starts_and_stops() -> None:
    mgr = sm.StreamManager(FakeRedis())

    async def main() -> None:
        async with mgr as entered:
            assert entered is mgr
            assert mgr.running is True
            assert mgr._loop is not None
        assert mgr.running is False
        assert mgr._loop is None

    run(main())
