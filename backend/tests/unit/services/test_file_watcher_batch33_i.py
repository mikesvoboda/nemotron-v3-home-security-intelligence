# TARGET-MODULE: backend.services.file_watcher
"""Campaign #9 battery I: kill-real for backend/services/file_watcher.py survivors.

Campaign #9 (mutation ladder, 2026-09-30). 339 survivor keys, 336/675 = 49.78%
module kt before this battery. The shipped test_file_watcher.py suite drives the
service through watchdog events and asserts MESSAGES ONLY ("backpressure" in
message.lower()), so the whole `extra=` payload mutation family (key renames,
extra=None), the exact queue/stream payloads, the observer-call arg families,
the log-record ATTRIBUTES, the size-boundary comparisons and the duration/
latency arithmetic survive. This battery:

  * captures the module logger with its own handler and asserts record ATTRS
    (camera_id, file_path, media_type, queue_name, queue_length, loop_exists,
    ...) not just messages -- ContextFilter (audited at backend/core/logging.py)
    injects only request/correlation/trace/span/connection/task/job/hostname
    keys, never camera_id/file_path/media_type/..., so a dropped or renamed
    extra key really disappears from the record; file_watcher has NO
    log_context call sites (grep-verified) -- no masking family here;
  * replaces mocks with recorder objects capturing (name, args, kwargs) and
    subclasses that override the sub-calls (_wait_for_file_stability,
    _ensure_camera_exists, _queue_for_detection, _process_file) so EXACT
    positional forwarding is asserted, not mock-accepts-anything;
  * pins time inside _run(): fw.time -> a clock shim and fw.asyncio -> a proxy
    whose sleep() logs + advances the same clock (the proxy is set on the
    module attribute ONLY -- swapping asyncio.sleep globally would freeze the
    test body's own cooperative awaits, discovered at authoring time). Tests
    that need real cooperative scheduling (task cancel/cleanup/event handler)
    run _run(..., fake_sleep=False): the task then suspends on the REAL sleep
    while durations stay frozen;
  * uses real files for the size gates (0 B, 1 B, valid JPEG padded to EXACTLY
    MIN_IMAGE_FILE_SIZE, 1024/1025-byte videos) and swaps fw.Path for a
    PermissionError-raising subclass to drive the retry-race arm;
  * drives start()/stop() with an injected _FakeObs observer recorder (zero
    real watchdog threads except the two polling-fallback arms) and the
    no-running-loop arm by driving start() with coro.send(None).

Honesty ledger -- survivor keys expected to sweep GREEN with this battery
loaded (registered EQUIVALENT only after the sweep proves it; key numbers are
the M10-era meta, and a battery that GROWS coverage can renumber tails --
adjudicate any flipped number by body diff, see docs/plans ledger):
  * _wait_for_file_stability: last_size init -1 -> None/-2/+1 (a present file's
    size is 10/42 here -- never equals the init, so the reset branch fires
    identically and the warning's last_size attr is the FINAL stat size);
    stable_since init None -> "" (the size-changed branch overwrites it before
    any comparison reads it).
  * _queue_for_detection streams extra_fields .get variants that only change
    an UNREACHABLE default: .get(key, None) / .get("") / .get(key,) -- the
    "pipeline_start_time" key is ALWAYS present in detection_data, so the
    default never surfaces (the get(None, "") and get("XX..", "") lookups DO
    miss and are killed by the equality asserts).
  * start() mkdir exist_ok True -> False (the branch only runs when the dir
    does NOT exist -- exist_ok is irrelevant there) and exist_ok -> None
    (truthy); the RuntimeError guards AFTER successful loop capture (self._loop
    is None / not is_running()) -- get_running_loop either returns the RUNNING
    loop or raises, both guards are dead under any driver.
  * _create_event_handler loop_running ternary `and False` arm: inside the
    no-loop branch _loop is falsy on entry, both sides yield False.
  * _schedule_file_processing pop(file_path, None) -> pop(file_path, ) -- the
    done-callback's `is t` guard guarantees the key is present.
  * _queue_for_detection legacy Semaphore(self._max_concurrent_queue) arg-drop
    and the streams-side duplicate: a single acquisition cannot observe the
    permit count.
  * stop() asyncio.gather(*self._pending_tasks.values()) arg-drop: the tasks
    are already cancel()d synchronously before the gather, so awaiting nothing
    still settles them cancelled -- no observable channel in-process.
"""

import asyncio
import contextlib
import errno
import logging
import pathlib
import shutil
import tempfile
import types
import unittest.mock

from PIL import Image

import backend.services.file_watcher as fw
from backend.core.redis import QueueAddResult, QueueOverflowPolicy

MIN_SIZE = fw.MIN_IMAGE_FILE_SIZE
_REAL_ASYNCIO = asyncio


# ---------------------------------------------------------------------------
# capture + clock pinning
# ---------------------------------------------------------------------------


class _Capture(logging.Handler):
    """Records EVERY record emitted by fw.logger while attached.

    Attached to the module logger; logger-level filters (ContextFilter via
    get_logger) run inside handle(), so captured records carry the same
    injected context keys production emits -- exactly the shape mutmut edits.
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def by_fragment(self, frag: str) -> list[logging.LogRecord]:
        return [r for r in self.records if frag in r.getMessage()]


@contextlib.contextmanager
def _capture_logs():
    cap = _Capture()
    fw.logger.addHandler(cap)
    prev_level = fw.logger.level
    fw.logger.setLevel(logging.DEBUG)
    try:
        yield cap
    finally:
        fw.logger.removeHandler(cap)
        fw.logger.setLevel(prev_level)


class _Clock:
    """Fake clock: fw.time shim; sleep()/asleep() log the sleep AND advance t."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.t

    def monotonic(self) -> float:
        return self.t

    def sleep(self, d: float) -> None:  # time.sleep (PermissionError retry)
        self.sleeps.append(float(d))
        self.t += float(d)

    async def asleep(self, d: float) -> None:  # fw's asyncio.sleep
        self.sleeps.append(float(d))
        self.t += float(d)


class _AsyncProxy:
    """Stands in for the asyncio module INSIDE file_watcher only.

    Everything delegates to the real module except ``sleep`` -> the clock's
    fake. (Authoring lesson: swapping asyncio.sleep GLOBALLY makes the test
    body's own awaits return without yielding, so nothing cooperative ever
    runs -- scope the swap to the module attribute.)
    """

    def __init__(self, real, asleep) -> None:
        self._real = real
        self._asleep = asleep

    def __getattr__(self, name):
        if name == "sleep":
            return self._asleep
        return getattr(self._real, name)


@contextlib.contextmanager
def _time_patch(clock: _Clock, fake_sleep: bool = True):
    old_time, old_asyncio = fw.time, fw.asyncio
    fw.time = clock
    if fake_sleep:
        fw.asyncio = _AsyncProxy(_REAL_ASYNCIO, clock.asleep)
    try:
        yield clock
    finally:
        fw.time = old_time
        fw.asyncio = old_asyncio


def _run(coro, clock: _Clock | None = None, fake_sleep: bool = True):
    """Drive a coroutine with fw's time pinned; see module docstring re flags."""
    clk = clock or _Clock()
    with _time_patch(clk, fake_sleep=fake_sleep):
        return asyncio.run(coro)


def _settings(**over):
    base = {
        "foscam_base_path": "/nonexistent-foscam-root",
        "file_watcher_polling": False,
        "file_watcher_polling_interval": 1.0,
        "file_watcher_max_concurrent_queue": 3,
        "file_watcher_queue_delay_ms": 0,
        "use_redis_streams": False,
    }
    base.update(over)
    return types.SimpleNamespace(**base)


@contextlib.contextmanager
def _use_settings(stub):
    old = fw.get_settings
    fw.get_settings = lambda: stub
    try:
        yield stub
    finally:
        fw.get_settings = old


# ---------------------------------------------------------------------------
# recorders + watcher builders (no mock.* except the two autospec sites)
# ---------------------------------------------------------------------------


class _Recorder:
    """Records (method_name, args, kwargs) for every call; returns preset."""

    def __init__(self, **returns) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self._returns = returns

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def _call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name in self._returns:
                val = self._returns[name]
                return val(*args, **kwargs) if callable(val) else val
            return None

        return _call


class _AsyncRecorder(_Recorder):
    """Recorder whose recorded methods are awaitable coroutines."""

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        async def _call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name in self._returns:
                val = self._returns[name]
                return val(*args, **kwargs) if callable(val) else val
            return None

        return _call


class _CallableRecorder(_AsyncRecorder):
    """Also callable ITSELF (file_watcher awaits the camera_creator directly,
    so it cannot be an attribute-proxy recorder)."""

    async def __call__(self, *args, **kwargs):
        self.calls.append(("camera_creator", args, kwargs))


class _FakeObs:
    """Observer stand-in: records schedule/start/stop/join, starts nothing."""

    def __init__(self, start_raises: OSError | None = None) -> None:
        self.schedule_calls: list[tuple] = []
        self.starts = 0
        self.stops = 0
        self.joins: list[dict] = []
        self._start_raises = start_raises

    def schedule(self, handler, path, recursive=False):
        self.schedule_calls.append((handler, path, recursive))

    def start(self) -> None:
        if self._start_raises is not None:
            raise self._start_raises
        self.starts += 1

    def stop(self) -> None:
        self.stops += 1

    def join(self, timeout=None):
        self.joins.append({"timeout": timeout})


class _ProbeOk:
    supported = True
    error = None


class _ProbeFail:
    supported = True
    error = errno.EACCES


def _mkwatcher(root, **kw):
    with _use_settings(_settings()):
        return fw.FileWatcher(camera_root=str(root), watch_probe=lambda _p: _ProbeOk(), **kw)


class _RecorderSubs(fw.FileWatcher):
    """Sub-call recorders for stability/ensure/queue; REAL _process_file."""

    stub_wait = True

    def __init__(self, *a, stable=True, **kw) -> None:
        super().__init__(*a, **kw)
        self._stable = stable
        self.stability_calls: list[tuple] = []
        self.ensure_calls: list[tuple] = []
        self.queue_calls: list[tuple] = []

    async def _wait_for_file_stability(self, file_path, stability_time=None):
        if not self.stub_wait:
            return await super()._wait_for_file_stability(file_path, stability_time)
        self.stability_calls.append((file_path, stability_time))
        return self._stable

    async def _ensure_camera_exists(self, camera_id, folder_name):
        self.ensure_calls.append((camera_id, folder_name))

    async def _queue_for_detection(self, camera_id, file_path, media_type=None):
        self.queue_calls.append((camera_id, file_path, media_type))


class _RealWait(_RecorderSubs):
    stub_wait = False


class _SchedSubs(fw.FileWatcher):
    """Overrides ONLY _process_file -- for debounce/schedule tests."""

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.process_calls: list[tuple] = []

    async def _process_file(self, file_path):
        self.process_calls.append((file_path,))


# ---------------------------------------------------------------------------
# real-file fixtures
# ---------------------------------------------------------------------------


def _valid_image(path, size=None):
    """Smooth 64x64 JPEG (compressible: a few KB, always < MIN_SIZE), padded
    with post-EOI bytes to an EXACT st_size (default MIN_SIZE + 1024)."""
    w = h = 64
    data = bytes((x + y) % 256 for y in range(h) for x in range(w * 3))
    Image.frombytes("RGB", (w, h), data).save(path, "JPEG")
    if size is None:
        size = MIN_SIZE + 1024
    pad = size - path.stat().st_size
    if pad < 0:  # pragma: no cover - guard the fixture itself
        raise AssertionError(f"image already exceeds {size} bytes")
    # nosemgrep: path-traversal-open - path is a pytest tmp_path fixture file
    with open(path, "ab") as fh:  # padding written AFTER the JPEG EOI marker
        fh.write(b"\0" * pad)
    return path


def _file(path, nbytes):
    path.write_bytes(b"\0" * nbytes)
    return path


def _fp(root, name):
    return pathlib.Path(root) / name


# ---------------------------------------------------------------------------
# 1. image/video validation gates
# ---------------------------------------------------------------------------


def test_valid_image_accepted_and_missing_rejected():
    root = tempfile.mkdtemp()
    try:
        good = _valid_image(_fp(root, "ok.jpg"))
        with _capture_logs() as logs:
            assert fw.is_valid_image(str(good)) is True
            assert fw.is_valid_image(str(_fp(root, "absent.jpg"))) is False
        assert not logs.by_fragment("Empty image file")
        assert not logs.by_fragment("too small")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_zero_and_one_byte_images_take_their_own_warnings():
    root = tempfile.mkdtemp()
    try:
        empty = _file(_fp(root, "e.png"), 0)
        tiny = _file(_fp(root, "t.png"), 1)
        with _capture_logs() as logs:
            assert fw.is_valid_image(str(empty)) is False
            assert fw.is_valid_image(str(tiny)) is False
        empty_logs = logs.by_fragment("Empty image file detected")
        small_logs = logs.by_fragment("Image file too small")
        assert len(empty_logs) == 1, [r.getMessage() for r in logs.records]
        assert len(small_logs) == 1
        assert f"({1} bytes, minimum {MIN_SIZE})" in small_logs[0].getMessage()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_image_exactly_at_minimum_size_is_validated_not_rejected():
    root = tempfile.mkdtemp()
    try:
        img = _valid_image(_fp(root, "min.jpg"), size=MIN_SIZE)
        assert img.stat().st_size == MIN_SIZE
        with _capture_logs() as logs:
            assert fw.is_valid_image(str(img)) is True
        assert not logs.by_fragment("too small")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_image_async_gates_run_under_async_sleep_and_same_boundaries():
    root = tempfile.mkdtemp()
    try:
        empty = _file(_fp(root, "e.png"), 0)
        tiny = _file(_fp(root, "t.png"), 1)
        img = _valid_image(_fp(root, "min.jpg"), size=MIN_SIZE)

        async def body():
            assert await fw.is_valid_image_async(str(empty)) is False
            assert await fw.is_valid_image_async(str(tiny)) is False
            assert await fw.is_valid_image_async(str(img)) is True

        with _capture_logs() as logs:
            _run(body())
        assert len(logs.by_fragment("Empty image file detected")) == 1
        assert len(logs.by_fragment("Image file too small")) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_permission_error_race_retries_after_one_second():
    root = tempfile.mkdtemp()
    try:
        target = _file(_fp(root, "p.jpg"), 64)
        real_path = fw.Path

        class _NoPermPath(real_path):  # type: ignore[valid-type,misc]
            def exists(self):
                raise PermissionError(1, "denied")

        clock = _Clock()
        fw.Path = _NoPermPath
        try:
            with _capture_logs() as logs, _time_patch(clock):
                assert fw.is_valid_image(str(target)) is False
        finally:
            fw.Path = real_path
        assert clock.sleeps[:1] == [1.0], clock.sleeps
        assert logs.by_fragment("got PermissionError, retrying")
        assert logs.by_fragment("validation failed after retry (corrupt/truncated)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_corrupt_image_logs_oserror_arm():
    root = tempfile.mkdtemp()
    try:
        junk = _fp(root, "j.jpg")
        junk.write_bytes(b"not a jpeg at all" * 5000)  # > MIN_SIZE -> reaches PIL
        with _capture_logs() as logs:
            assert fw.is_valid_image(str(junk)) is False
        arm = logs.by_fragment("Image validation failed (corrupt/truncated)")
        assert len(arm) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_retry_validation_helpers_report_corrupt_files():
    root = tempfile.mkdtemp()
    try:
        junk = _fp(root, "j.jpg")
        junk.write_bytes(b"nope" * 4000)
        with _capture_logs() as logs:
            assert fw._retry_validation_sync(str(junk)) is False

            async def body():
                assert await fw._retry_validation_async(str(junk)) is False

            _run(body())
        arm = logs.by_fragment("validation failed after retry (corrupt/truncated)")
        assert len(arm) == 2, [r.getMessage() for r in logs.records]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_video_size_gates_with_exact_boundaries():
    root = tempfile.mkdtemp()
    try:
        empty = _file(_fp(root, "a.mp4"), 0)
        tiny = _file(_fp(root, "b.mp4"), 1)
        at1024 = _file(_fp(root, "c.mp4"), 1024)
        at1025 = _file(_fp(root, "d.mp4"), 1025)
        with _capture_logs() as logs:
            assert fw.is_valid_video(str(empty)) is False
            assert fw.is_valid_video(str(tiny)) is False
            assert fw.is_valid_video(str(at1024)) is True
            assert fw.is_valid_video(str(at1025)) is True
        assert len(logs.by_fragment("Empty video file detected")) == 1
        small = logs.by_fragment("Video file too small")
        assert len(small) == 1
        assert "(1 bytes)" in small[0].getMessage()
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. constructor
# ---------------------------------------------------------------------------


def test_constructor_defaults_recorded_on_the_instance_and_log():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()), _capture_logs() as logs:
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=_Recorder(),
                watch_probe=lambda _p: _ProbeOk(),
            )
        assert w.debounce_delay == 0.5
        assert w.stability_time == 2.0
        assert w._queue_semaphore is None
        assert w.running is False
        assert w.watch_mode == "native"
        assert w.watch_fallback_reason is None
        assert w._known_cameras == set()
        assert isinstance(w._dedupe_service, fw.DedupeService)
        assert w._dedupe_service._redis_client is not None
        assert w._hash_executor._max_workers == 4
        info = logs.by_fragment("FileWatcher initialized for camera root")
        assert len(info) == 1
        msg = info[0].getMessage()
        assert root in msg
        assert "observer=native" in msg
        assert "interval=" not in msg
        assert "dedupe=enabled" in msg
        assert "auto_create=disabled" in msg
        assert f"executor={fw.get_executor_type()}" in msg
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_constructor_polling_branches_and_disabled_flags():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings(file_watcher_polling=True, file_watcher_polling_interval=1.0)):
            w = fw.FileWatcher(
                camera_root=root, use_polling=None, watch_probe=lambda _p: _ProbeOk()
            )
            assert w._use_polling is True
            assert w._polling_interval == 1.0
            assert w.observer.timeout == 1.0
            assert w.watch_mode == "polling"
        with _use_settings(_settings()):
            explicit = fw.FileWatcher(
                camera_root=root,
                use_polling=True,
                polling_interval=7.5,
                watch_probe=lambda _p: _ProbeOk(),
            )
        assert explicit._polling_interval == 7.5
        assert explicit.observer.timeout == 7.5
        with _use_settings(_settings()), _capture_logs() as logs:
            fw.FileWatcher(
                camera_root=root,
                redis_client=None,
                auto_create_cameras=True,
                camera_creator=None,
                watch_probe=lambda _p: _ProbeOk(),
            )
            fw.FileWatcher(
                camera_root=root,
                auto_create_cameras=True,
                camera_creator=lambda _c: None,
                watch_probe=lambda _p: _ProbeOk(),
            )
        msgs = [r.getMessage() for r in logs.by_fragment("FileWatcher initialized for camera root")]
        assert any("dedupe=disabled" in m and "auto_create=disabled" in m for m in msgs), msgs
        assert any("dedupe=disabled" in m and "auto_create=enabled" in m for m in msgs), msgs
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_explicit_dedupe_service_is_taken_verbatim():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            shared = object()
            w = fw.FileWatcher(
                camera_root=root, dedupe_service=shared, watch_probe=lambda _p: _ProbeOk()
            )
        assert w._dedupe_service is shared
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 3. _wait_for_file_stability under the fake clock
# ---------------------------------------------------------------------------


def test_stability_returns_true_at_exactly_stability_time():
    root = tempfile.mkdtemp()
    try:
        f = _file(_fp(root, "s.dat"), 10)
        with _use_settings(_settings()):
            w = fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())

        async def body():
            return await w._wait_for_file_stability(str(f), stability_time=2.0)

        with _capture_logs() as logs:
            clock = _Clock()
            ok = _run(body(), clock)
        assert ok is True
        assert sum(clock.sleeps) == 2.0, clock.sleeps  # stable at EXACTLY 2.0
        assert all(d == 0.5 for d in clock.sleeps), clock.sleeps
        dbg = logs.by_fragment("File stable after 2.0s")
        assert len(dbg) == 1
        assert getattr(dbg[0], "file_path", None) == str(f)
        assert getattr(dbg[0], "file_size", None) == 10
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_stability_disabled_zero_returns_immediately():
    root = tempfile.mkdtemp()
    try:
        f = _file(_fp(root, "s.dat"), 10)
        with _use_settings(_settings()):
            w = fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())

        async def body():
            return await w._wait_for_file_stability(str(f), stability_time=0)

        clock = _Clock()
        assert _run(body(), clock) is True
        assert clock.sleeps == []
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_stability_gives_up_at_max_checks_with_exact_message_and_attrs():
    root = tempfile.mkdtemp()
    try:
        f = _file(_fp(root, "s.dat"), 42)
        with _use_settings(_settings()):
            w = fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())

        async def body():
            return await w._wait_for_file_stability(str(f), stability_time=10000.0)

        with _capture_logs() as logs:
            clock = _Clock()
            ok = _run(body(), clock)
        assert ok is False
        assert len(clock.sleeps) == 20, clock.sleeps  # max_checks, not 21
        warn = logs.by_fragment("File never stabilized after 10.0s")
        assert len(warn) == 1
        assert getattr(warn[0], "last_size", None) == 42
        assert getattr(warn[0], "file_path", None) == str(f)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_disappearing_file_returns_false_with_warning():
    root = tempfile.mkdtemp()
    try:
        gone = str(_fp(root, "ghost.jpg"))
        with _use_settings(_settings()):
            w = fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())

        async def body():
            return await w._wait_for_file_stability(gone, stability_time=1.0)

        with _capture_logs() as logs:
            assert _run(body()) is False
        warn = logs.by_fragment("File disappeared during stability check")
        assert len(warn) == 1
        assert getattr(warn[0], "file_path", None) == gone
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. _get_camera_id_from_path + _ensure_camera_exists
# ---------------------------------------------------------------------------


def test_camera_id_extracts_folder_and_warns_on_foreign_path():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        inside = str(_fp(root, "Front Door/a.jpg"))
        assert w._get_camera_id_from_path(inside) == ("front_door", "Front Door")
        foreign = "/somewhere/else/a.jpg"
        with _capture_logs() as logs:
            assert w._get_camera_id_from_path(foreign) == (None, None)
        warn = logs.by_fragment("Could not extract camera ID from path")
        assert len(warn) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ensure_camera_creates_marks_known_and_swallows_creator_errors():
    root = tempfile.mkdtemp()
    try:
        creator = _CallableRecorder()
        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                auto_create_cameras=True,
                camera_creator=creator,
                watch_probe=lambda _p: _ProbeOk(),
            )

        async def body():
            await w._ensure_camera_exists("cam1", "Cam1")
            await w._ensure_camera_exists("cam1", "Cam1")  # known -> no-op

        with _capture_logs() as logs:
            _run(body())
        assert w._known_cameras == {"cam1"}
        assert len(creator.calls) == 1, creator.calls
        name, (camera,), _kw = creator.calls[0]
        assert name == "camera_creator"
        assert camera.id == "cam1"
        assert camera.name == "Cam1"
        assert camera.folder_path == str(pathlib.Path(root) / "Cam1")
        info = logs.by_fragment("Auto-creating camera 'cam1' for folder 'Cam1'")
        assert len(info) == 1
        assert getattr(info[0], "camera_id", None) == "cam1"
        assert getattr(info[0], "folder_path", None) == str(pathlib.Path(root) / "Cam1")

        def _raise(*_a, **_k):
            raise RuntimeError("db down")

        with _use_settings(_settings()):
            w2 = fw.FileWatcher(
                camera_root=root,
                auto_create_cameras=True,
                camera_creator=_raise,
                watch_probe=lambda _p: _ProbeOk(),
            )

        async def body2():
            await w2._ensure_camera_exists("cam2", "Cam2")

        with _capture_logs() as logs2:
            _run(body2())  # must NOT propagate
        warn = logs2.by_fragment("Failed to auto-create camera 'cam2'")
        assert len(warn) == 1
        assert getattr(warn[0], "camera_id", None) == "cam2"
        assert getattr(warn[0], "folder_name", None) == "Cam2"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ensure_without_creator_marks_known_and_returns():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                auto_create_cameras=True,
                camera_creator=None,
                watch_probe=lambda _p: _ProbeOk(),
            )

        async def body():
            await w._ensure_camera_exists("cam3", "Cam3")

        with _capture_logs() as logs:
            _run(body())
        assert w._known_cameras == {"cam3"}
        assert not logs.by_fragment("Auto-creating camera")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 5. debounce + scheduling
# ---------------------------------------------------------------------------


def test_debounce_sleeps_exact_delay_then_processes():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = _SchedSubs(camera_root=root, debounce_delay=0.25, watch_probe=lambda _p: _ProbeOk())

        async def body():
            await w._debounced_process("/x/whatever.jpg")

        clock = _Clock()
        _run(body(), clock)
        assert clock.sleeps[:1] == [0.25], clock.sleeps
        assert w.process_calls == [("/x/whatever.jpg",)]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_cancelled_debounce_logs_debug_message():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = _SchedSubs(camera_root=root, debounce_delay=30.0, watch_probe=lambda _p: _ProbeOk())

        async def body():
            task = asyncio.create_task(w._debounced_process("/x/x.jpg"))
            await _REAL_ASYNCIO.sleep(0.02)  # real: task suspends on its 30s sleep
            task.cancel()
            with contextlib.suppress(_REAL_ASYNCIO.CancelledError):
                await task

        with _capture_logs() as logs:
            _run(body(), fake_sleep=False)
        dbg = logs.by_fragment("Processing cancelled for /x/x.jpg")
        assert len(dbg) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_schedule_cancels_previous_task_and_cleanup_removes_entry():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = _SchedSubs(camera_root=root, debounce_delay=30.0, watch_probe=lambda _p: _ProbeOk())
            w2 = _SchedSubs(camera_root=root, debounce_delay=0.0, watch_probe=lambda _p: _ProbeOk())

        async def body():
            await w._schedule_file_processing("/x/a.jpg")
            first = w._pending_tasks["/x/a.jpg"]
            await w._schedule_file_processing("/x/a.jpg")
            second = w._pending_tasks["/x/a.jpg"]
            assert second is not first
            await _REAL_ASYNCIO.sleep(0.02)  # let the cancel settle + fire cleanup
            assert first.cancelled()
            # the done-callback ran but its `is t` guard spared the replacement
            assert w._pending_tasks.get("/x/a.jpg") is second
            assert w.process_calls == []  # 30s debounce never elapsed
            w._pending_tasks.clear()  # first's done-callback must NOT delete second

            await w2._schedule_file_processing("/x/b.jpg")
            assert "/x/b.jpg" in w2._pending_tasks
            await _REAL_ASYNCIO.sleep(0.03)  # b finishes -> done callback pops
            assert "/x/b.jpg" not in w2._pending_tasks

        _run(body(), fake_sleep=False)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 6. _queue_for_detection legacy path
# ---------------------------------------------------------------------------


def test_queue_without_redis_warns_and_skips():
    root = tempfile.mkdtemp()
    try:

        async def body():
            await w._queue_for_detection("cam1", "/x/a.jpg", "image")

        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root, redis_client=None, watch_probe=lambda _p: _ProbeOk()
            )
            with _capture_logs() as logs:
                _run(body())
        warn = logs.by_fragment("Redis client not configured, skipping queue")
        assert len(warn) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _qresult(**over):
    base = {
        "success": True,
        "queue_length": 4,
        "dropped_count": 0,
        "moved_to_dlq_count": 0,
        "error": None,
        "warning": None,
    }
    base.update(over)
    return QueueAddResult(**base)


def test_queue_legacy_payload_and_policy_are_exact():
    root = tempfile.mkdtemp()
    try:
        clock = _Clock()
        redis = _AsyncRecorder(add_to_queue_safe=_qresult())
        dedupe = _AsyncRecorder(is_duplicate_and_mark=(False, "abc123" * 6))

        async def body():
            await w._queue_for_detection("front_door", "/x/a.jpg", "image")

        with _use_settings(_settings(file_watcher_queue_delay_ms=60)):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=redis,
                dedupe_service=dedupe,
                watch_probe=lambda _p: _ProbeOk(),
            )
            _run(body(), clock)
        assert len(redis.calls) == 1, redis.calls
        name, (qname, payload), kwargs = redis.calls[0]
        assert name == "add_to_queue_safe"
        assert qname == w.queue_name
        assert kwargs["overflow_policy"] is QueueOverflowPolicy.DLQ
        assert set(payload) == {
            "camera_id",
            "file_path",
            "timestamp",
            "media_type",
            "pipeline_start_time",
            "file_hash",
        }
        assert payload["camera_id"] == "front_door"
        assert payload["file_path"] == "/x/a.jpg"
        assert payload["media_type"] == "image"
        assert payload["timestamp"] == payload["pipeline_start_time"]
        assert "+00:00" in payload["timestamp"]  # tz-aware (now(None) is naive -> kill)
        assert payload["file_hash"] == "abc123" * 6
        assert clock.sleeps[-1:] == [0.06], clock.sleeps  # 60 ms / 1000
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_legacy_zero_delay_does_not_sleep():
    root = tempfile.mkdtemp()
    try:
        clock = _Clock()
        redis = _AsyncRecorder(add_to_queue_safe=_qresult())

        async def body():
            await w._queue_for_detection("cam1", "/x/a.jpg", "image")

        with _use_settings(_settings(file_watcher_queue_delay_ms=0)):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=redis,
                dedupe_service=None,
                watch_probe=lambda _p: _ProbeOk(),
            )
            _run(body(), clock)
        assert clock.sleeps == [], clock.sleeps  # > 0 guard, not >= 0
        assert redis.calls
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_media_type_falls_back_then_image():
    root = tempfile.mkdtemp()
    try:
        redis = _AsyncRecorder(add_to_queue_safe=_qresult())

        async def media(media_type, path):
            redis.calls.clear()
            await w._queue_for_detection("cam1", path, media_type)
            return redis.calls[0][1][1]["media_type"]

        async def body():
            return (
                await media(None, "/x/a.mp4"),  # None -> get_media_type -> video
                await media(None, "/x/a.jpg"),  # None -> get_media_type -> image
                await media(None, "/x/a.xyz"),  # None -> "image" final default
                await media("video", "/x/a.jpg"),  # given wins over suffix
            )

        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=redis,
                dedupe_service=None,
                watch_probe=lambda _p: _ProbeOk(),
            )
            got = _run(body())
        assert got == ("video", "image", "image", "video"), got
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_duplicate_skips_enqueue_with_exact_message():
    root = tempfile.mkdtemp()
    try:
        redis = _AsyncRecorder(add_to_queue_safe=_qresult())
        dedupe = _AsyncRecorder(is_duplicate_and_mark=(True, "f" * 64))

        async def body():
            await w._queue_for_detection("cam1", "/x/a.jpg", "image")

        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=redis,
                dedupe_service=dedupe,
                watch_probe=lambda _p: _ProbeOk(),
            )
            with _capture_logs() as logs:
                _run(body())
        assert redis.calls == []
        info = logs.by_fragment("Skipping duplicate file")
        assert len(info) == 1
        assert info[0].getMessage() == (
            "Skipping duplicate file: /x/a.jpg (hash=" + "f" * 16 + "...)"
        )
        assert getattr(info[0], "file_path", None) == "/x/a.jpg"
        assert getattr(info[0], "file_hash", None) == "f" * 64
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_duplicate_without_hash_logs_unknown():
    root = tempfile.mkdtemp()
    try:
        redis = _AsyncRecorder(add_to_queue_safe=_qresult())
        dedupe = _AsyncRecorder(is_duplicate_and_mark=(True, None))

        async def body():
            await w._queue_for_detection("cam1", "/x/a.jpg", "image")

        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=redis,
                dedupe_service=dedupe,
                watch_probe=lambda _p: _ProbeOk(),
            )
            with _capture_logs() as logs:
                _run(body())
        info = logs.by_fragment("(hash=unknown...)")
        assert len(info) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_failure_logs_error_attrs_and_raises():
    root = tempfile.mkdtemp()
    try:
        redis = _AsyncRecorder(
            add_to_queue_safe=_qresult(success=False, queue_length=900, error="maxlen")
        )

        async def body():
            await w._queue_for_detection("cam1", "/x/a.jpg", "image")

        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=redis,
                dedupe_service=None,
                watch_probe=lambda _p: _ProbeOk(),
            )
            with _capture_logs() as logs:
                raised = None
                try:
                    _run(body())
                except RuntimeError as e:
                    raised = e
        assert raised is not None and "maxlen" in str(raised)
        err = logs.by_fragment("Failed to queue detection for /x/a.jpg: maxlen")
        assert len(err) == 1
        assert getattr(err[0], "camera_id", None) == "cam1"
        assert getattr(err[0], "file_path", None) == "/x/a.jpg"
        assert getattr(err[0], "queue_name", None) == w.queue_name
        assert getattr(err[0], "queue_length", None) == 900
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_backpressure_logs_warning_attrs():
    root = tempfile.mkdtemp()
    try:
        redis = _AsyncRecorder(add_to_queue_safe=_qresult(moved_to_dlq_count=3, warning="trimmed"))

        async def body():
            await w._queue_for_detection("cam1", "/x/a.jpg", "image")

        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=redis,
                dedupe_service=None,
                watch_probe=lambda _p: _ProbeOk(),
            )
            with _capture_logs() as logs:
                _run(body())
        warn = logs.by_fragment("Queue backpressure detected while adding detection for /x/a.jpg")
        assert len(warn) == 1
        assert getattr(warn[0], "queue_name", None) == w.queue_name
        assert getattr(warn[0], "queue_length", None) == 4
        assert getattr(warn[0], "moved_to_dlq", None) == 3
        assert getattr(warn[0], "warning", None) == "trimmed"
        assert getattr(warn[0], "camera_id", None) == "cam1"
        assert getattr(warn[0], "file_path", None) == "/x/a.jpg"
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 7. streams path (the battery's ONLY patch.object sites, both autospec=True)
# ---------------------------------------------------------------------------


def test_queue_streams_path_forwards_exact_kwargs_and_skips_legacy():
    root = tempfile.mkdtemp()
    try:
        clock = _Clock()
        redis = _AsyncRecorder()
        stream = _AsyncRecorder()
        dedupe = _AsyncRecorder(is_duplicate_and_mark=(False, "h" * 40))

        async def body():
            await w._queue_for_detection("front_door", "/x/a.jpg", "image")

        with _use_settings(_settings(use_redis_streams=True, file_watcher_queue_delay_ms=60)):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=redis,
                dedupe_service=dedupe,
                watch_probe=lambda _p: _ProbeOk(),
            )
            with unittest.mock.patch.object(
                fw,
                "get_detection_stream_service",
                autospec=True,
                return_value=stream,
            ) as factory:
                _run(body(), clock)
        assert factory.call_args[0][0] is redis  # redis_client forwarded, not None
        assert redis.calls == []  # streams arm RETURNS before the legacy queue
        assert len(stream.calls) == 1, stream.calls
        name, _args, kwargs = stream.calls[0]
        assert name == "add_detection"
        assert kwargs["camera_id"] == "front_door"
        assert kwargs["detection_id"] == 0
        assert kwargs["file_path"] == "/x/a.jpg"
        ef = kwargs["extra_fields"]
        assert set(ef) == {"timestamp", "media_type", "pipeline_start_time", "file_hash"}
        assert ef["media_type"] == "image"
        assert ef["timestamp"] == ef["pipeline_start_time"]
        assert "+00:00" in ef["timestamp"]
        assert ef["file_hash"] == "h" * 40
        assert clock.sleeps[-1:] == [0.06], clock.sleeps
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 8. _process_file orchestration
# ---------------------------------------------------------------------------


def test_process_file_happy_path_forwards_every_stage():
    root = tempfile.mkdtemp()
    try:
        cam = _fp(root, "Front Door")
        cam.mkdir()
        img = _valid_image(cam / "a.jpg")
        with _use_settings(_settings()):
            w = _RecorderSubs(
                camera_root=root,
                stability_time=2.0,
                debounce_delay=0.0,
                watch_probe=lambda _p: _ProbeOk(),
            )
        with unittest.mock.patch.object(fw, "record_pipeline_stage_latency", autospec=True) as lat:
            with _capture_logs() as logs:
                clock = _Clock()
                _run(w._process_file(str(img)), clock)
        assert w.stability_calls == [(str(img), None)]
        assert w.queue_calls == [("front_door", str(img), "image")], w.queue_calls
        assert lat.call_args[0][0] == "watch_to_detect"
        assert lat.call_args[0][1] == 0.0
        info = logs.by_fragment(f"Queued image for detection: {img} (camera: front_door)")
        assert len(info) == 1
        assert getattr(info[0], "camera_id", None) == "front_door"
        assert getattr(info[0], "file_path", None) == str(img)
        assert getattr(info[0], "media_type", None) == "image"
        assert getattr(info[0], "duration_ms", None) == 0
        dbg = logs.by_fragment(f"Processing file: {img}")
        assert len(dbg) == 1
        assert getattr(dbg[0], "media_type", None) == "image"
        assert getattr(dbg[0], "camera_id", None) == "front_door"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_process_file_forwards_stability_check_exactly():
    root = tempfile.mkdtemp()
    try:
        cam = _fp(root, "Front Door")
        cam.mkdir()
        img = _valid_image(cam / "a.jpg")
        with _use_settings(_settings()):
            w = _RecorderSubs(
                camera_root=root, stable=True, stability_time=2.0, watch_probe=lambda _p: _ProbeOk()
            )
        _run(w._process_file(str(img)))
        assert w.stability_calls == [(str(img), None)]  # ONE call, no arg drift
        assert len(w.queue_calls) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_process_file_warns_when_real_stability_fails():
    root = tempfile.mkdtemp()
    try:
        cam = _fp(root, "Front Door")
        cam.mkdir()
        img = _valid_image(cam / "a.jpg")
        with _use_settings(_settings()):
            w = _RealWait(
                camera_root=root, stability_time=10000.0, watch_probe=lambda _p: _ProbeOk()
            )
        clock = _Clock()
        with _capture_logs() as logs:
            _run(w._process_file(str(img)), clock)
        assert w.queue_calls == []
        assert sum(clock.sleeps) == 10.0, clock.sleeps  # the REAL wait ran 20x0.5
        warn = logs.by_fragment("Skipping file that never stabilized")
        assert len(warn) == 1
        assert getattr(warn[0], "camera_id", None) == "front_door"
        assert getattr(warn[0], "media_type", None) == "image"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_process_file_skips_unsupported_with_debug_attrs():
    root = tempfile.mkdtemp()
    try:
        cam = _fp(root, "Front Door")
        cam.mkdir()
        txt = cam / "note.txt"
        txt.write_text("hello")
        with _use_settings(_settings()):
            w = _RecorderSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        with _capture_logs() as logs:
            _run(w._process_file(str(txt)))
        assert w.stability_calls == [] and w.queue_calls == []
        dbg = logs.by_fragment(f"Skipping unsupported file: {txt}")
        assert len(dbg) == 1
        assert getattr(dbg[0], "camera_id", None) == "front_door"
        assert getattr(dbg[0], "file_path", None) == str(txt)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_process_file_skips_invalid_media_naming_the_type():
    root = tempfile.mkdtemp()
    try:
        cam = _fp(root, "Front Door")
        cam.mkdir()
        zero = cam / "z.jpg"
        zero.write_bytes(b"")
        with _use_settings(_settings()):
            w = _RecorderSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        with _capture_logs() as logs:
            _run(w._process_file(str(zero)))
        assert w.queue_calls == []
        warn = logs.by_fragment(f"Skipping invalid/corrupted image file: {zero}")
        assert len(warn) == 1
        assert getattr(warn[0], "media_type", None) == "image"
        assert getattr(warn[0], "camera_id", None) == "front_door"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_process_file_skips_when_camera_id_unknown():
    root = tempfile.mkdtemp()
    other = tempfile.mkdtemp()
    try:
        outside = _valid_image(_fp(other, "a.jpg"))
        with _use_settings(_settings()):
            w = _RecorderSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        with _capture_logs() as logs:
            _run(w._process_file(str(outside)))
        assert w.queue_calls == []
        warn = logs.by_fragment(f"Could not determine camera ID for: {outside}")
        assert len(warn) == 1
        assert getattr(warn[0], "file_path", None) == str(outside)
    finally:
        shutil.rmtree(other, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def test_process_file_auto_create_gate_and_queue_error_arm():
    root = tempfile.mkdtemp()
    try:
        cam = _fp(root, "Front Door")
        cam.mkdir()
        img = _valid_image(cam / "a.jpg")

        with _use_settings(_settings()):
            w = _RecorderSubs(
                camera_root=root,
                auto_create_cameras=True,
                camera_creator=None,
                watch_probe=lambda _p: _ProbeOk(),
            )
        _run(w._process_file(str(img)))
        assert w.ensure_calls == []
        assert w._known_cameras == set()  # an `or`-flip would reach _ensure

        with _use_settings(_settings()):
            w2 = _RecorderSubs(
                camera_root=root,
                auto_create_cameras=True,
                camera_creator=lambda _c: None,
                watch_probe=lambda _p: _ProbeOk(),
            )
        _run(w2._process_file(str(img)))
        assert w2.ensure_calls == [("front_door", "Front Door")], w2.ensure_calls

        class _Boom(_RecorderSubs):
            async def _queue_for_detection(self, camera_id, file_path, media_type=None):
                self.queue_calls.append((camera_id, file_path, media_type))
                raise RuntimeError("redis exploded")

        with _use_settings(_settings()):
            w3 = _Boom(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        with unittest.mock.patch.object(fw, "record_pipeline_stage_latency", autospec=True) as lat:
            with _capture_logs() as logs:
                _run(w3._process_file(str(img)))  # swallowed
        assert lat.call_args_list == []  # the error arm records NOTHING
        err = logs.by_fragment(f"Failed to queue image {img}: redis exploded")
        assert len(err) == 1
        assert getattr(err[0], "duration_ms", None) == 0
        assert getattr(err[0], "media_type", None) == "image"
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 9. event handler
# ---------------------------------------------------------------------------


def test_created_and_modified_events_schedule_with_str_path():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = _SchedSubs(camera_root=root, debounce_delay=0.0, watch_probe=lambda _p: _ProbeOk())
        target = str(_fp(root, "Front Door/a.jpg"))
        ev_str = types.SimpleNamespace(src_path=target, is_directory=False)
        ev_bytes = types.SimpleNamespace(src_path=target.encode(), is_directory=False)
        ev_dir = types.SimpleNamespace(src_path=target, is_directory=True)
        ev_txt = types.SimpleNamespace(src_path=str(_fp(root, "n.txt")), is_directory=False)

        async def body():
            w._loop = asyncio.get_running_loop()
            w._event_handler.on_created(ev_str)
            await _REAL_ASYNCIO.sleep(0.03)
            w._event_handler.on_modified(ev_bytes)
            await _REAL_ASYNCIO.sleep(0.03)
            w._event_handler.on_created(ev_dir)  # directory -> ignored
            w._event_handler.on_created(ev_txt)  # unsupported ext -> ignored
            await _REAL_ASYNCIO.sleep(0.03)

        _run(body(), fake_sleep=False)
        assert w.process_calls == [(target,), (target,)], w.process_calls
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_event_without_loop_logs_critical_error_attrs():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = _SchedSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        target = str(_fp(root, "a.jpg"))
        ev = types.SimpleNamespace(src_path=target, is_directory=False)
        w._loop = None
        with _capture_logs() as logs:
            w._event_handler.on_created(ev)  # must not raise
        assert w.process_calls == []
        err = logs.by_fragment("CRITICAL: Event loop not available for processing")
        assert len(err) == 1
        assert "File will NOT be processed" in err[0].getMessage()
        assert getattr(err[0], "file_path", None) == target
        assert getattr(err[0], "loop_exists", None) is False
        assert getattr(err[0], "loop_running", None) is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_event_logs_loop_running_true_when_loop_present():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = _SchedSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        target = str(_fp(root, "a.jpg"))
        ev = types.SimpleNamespace(src_path=target, is_directory=False)

        class _DeadLoop:
            """Present but not running -> error branch, loop_exists True."""

            def is_running(self):
                return False

            def is_closed(self):
                return False

        async def body():
            w._loop = _DeadLoop()
            w._event_handler.on_created(ev)

        with _capture_logs() as logs:
            _run(body(), fake_sleep=False)
        assert w.process_calls == []
        err = logs.by_fragment("CRITICAL: Event loop not available for processing")
        assert len(err) == 1
        assert getattr(err[0], "loop_exists", None) is True
        assert getattr(err[0], "loop_running", None) is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 10. start / _fall_back_to_polling / stop
# ---------------------------------------------------------------------------


def test_start_already_running_warns_and_returns():
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        w.running = True
        obs = _FakeObs()
        w.observer = obs
        with _capture_logs() as logs:
            _run(w.start())
        assert obs.starts == 0
        assert logs.by_fragment("FileWatcher already running")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_without_running_loop_raises_and_logs():
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        with _capture_logs() as logs:
            coro = w.start()
            raised = None
            try:
                coro.send(None)  # no running loop -> the RuntimeError arm
            except RuntimeError as e:
                raised = e
            finally:
                coro.close()
        assert raised is not None
        assert "MUST be started within an async context" in str(raised)
        err = logs.by_fragment("FileWatcher MUST be started within an async context")
        assert len(err) == 1
        assert getattr(err[0], "camera_root", None) == str(root)
        assert "error" in err[0].__dict__
        assert logs.by_fragment(f"Starting FileWatcher for {root}")
        assert w.running is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_native_schedules_root_and_logs_success():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(
            _settings(
                file_watcher_polling=False,
                file_watcher_max_concurrent_queue=3,
                file_watcher_queue_delay_ms=7,
            )
        ):
            w = fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        obs = _FakeObs()
        w.observer = obs
        with _capture_logs() as logs:
            _run(w.start())
        assert obs.schedule_calls == [(w._event_handler, str(root), True)]
        assert obs.starts == 1
        assert w.running is True
        assert w.watch_mode == "native"
        assert w._queue_semaphore is not None
        assert w._queue_semaphore._value == 3
        dbg = logs.by_fragment("Queue rate limiting initialized: max_concurrent=3, delay_ms=7")
        assert len(dbg) == 1
        assert logs.by_fragment("Event loop captured successfully for FileWatcher")
        ok = logs.by_fragment("FileWatcher started successfully (mode=native)")
        assert len(ok) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_creates_missing_camera_root_with_parents():
    parent = tempfile.mkdtemp()
    missing = str(pathlib.Path(parent) / "a" / "b")
    try:
        w = _mkwatcher(missing)
        w.observer = _FakeObs()
        with _capture_logs() as logs:
            _run(w.start())
        assert pathlib.Path(missing).is_dir()
        assert logs.by_fragment(f"Camera root directory does not exist: {missing}")
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def test_start_probe_refusal_falls_back_to_polling_before_scheduling():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings(file_watcher_polling_interval=2.5)):
            w = fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        w._watch_probe = lambda _p: _ProbeFail()
        obs = _FakeObs()
        w.observer = obs
        with _capture_logs() as logs:
            _run(w.start())
        try:
            assert w.watch_mode == "polling-fallback"
            assert w.watch_fallback_reason == "EACCES"
            assert w._use_polling is True
            assert isinstance(w.observer, fw.PollingObserver)
            assert w.observer.timeout == 2.5
            assert obs.starts == 0  # refused native observer REPLACED, never started
            assert len(w.observer.emitters) == 1  # watchdog registered our handler
            err = logs.by_fragment("the kernel REFUSED an inotify watch on")
            assert len(err) == 1
            assert "Permission denied" in err[0].getMessage()
            assert getattr(err[0], "camera_root", None) == str(root)
            assert getattr(err[0], "watch_errno", None) == "EACCES"
            assert logs.by_fragment("POLLING-FALLBACK mode (EACCES)")
        finally:
            w.observer.stop()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_observer_oserror_on_start_falls_back_and_retries():
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        boom = OSError(errno.ENOSPC, "no space")
        obs = _FakeObs(start_raises=boom)
        w.observer = obs
        with _capture_logs():
            _run(w.start())
        try:
            assert obs.starts == 0
            assert w.watch_mode == "polling-fallback"
            assert w.watch_fallback_reason == "ENOSPC"
            assert w.running is True
            assert isinstance(w.observer, fw.PollingObserver)
        finally:
            w.observer.stop()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_stop_short_path_and_full_path_record_every_resource():
    root = tempfile.mkdtemp()
    try:
        w = _SchedSubs(camera_root=root, debounce_delay=30.0, watch_probe=lambda _p: _ProbeOk())
        obs = _FakeObs()
        w.observer = obs
        ex = _Recorder()
        w._hash_executor = ex
        with _capture_logs() as logs:
            _run(w.stop())  # not running -> short path
        assert obs.stops == 0
        assert logs.by_fragment("FileWatcher not running, nothing to stop")
        assert w.running is False

        with _capture_logs() as logs:

            async def body():
                await w._schedule_file_processing("/x/p.jpg")
                assert "/x/p.jpg" in w._pending_tasks
                w.running = True
                await w.stop()

            _run(body(), fake_sleep=False)
        assert w._pending_tasks == {}
        assert obs.stops == 1
        assert obs.joins == [{"timeout": 5}]
        assert ex.calls == [("shutdown", (), {"wait": True, "cancel_futures": False})], ex.calls
        assert w._loop is None
        assert w.running is False
        assert logs.by_fragment("Stopping FileWatcher")
        assert logs.by_fragment("FileWatcher stopped")
        assert logs.by_fragment("Hash executor shut down")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_stop_cancels_pending_tasks():
    root = tempfile.mkdtemp()
    try:
        w = _SchedSubs(camera_root=root, debounce_delay=30.0, watch_probe=lambda _p: _ProbeOk())
        w.observer = _FakeObs()
        w._hash_executor = _Recorder()

        captured: list = []

        async def body():
            await w._schedule_file_processing("/x/p.jpg")
            task = w._pending_tasks["/x/p.jpg"]
            w.running = True
            await w.stop()
            captured.append(task.cancelled())

        _run(body(), fake_sleep=False)
        assert captured == [True]
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 11. async context manager
# ---------------------------------------------------------------------------


def test_async_context_manager_starts_and_stops():
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        obs = _FakeObs()

        async def body():
            w.observer = obs
            async with w as entered:
                assert entered is w
                assert w.running is True
            assert w.running is False

        _run(body())
        assert obs.starts == 1 and obs.stops == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
