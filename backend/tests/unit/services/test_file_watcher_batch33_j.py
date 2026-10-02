# TARGET-MODULE: backend.services.file_watcher
"""Campaign #9 battery J: v2 pass over the 65 battery-I survivors (2026-09-30).

Battery I (test_file_watcher_batch33_i.py) took file_watcher 336/675 -> 639/704
and its sweep reconciled with the bank 65/65. Probing the survivors by
construction (never by diff-shape) showed the GREENs split two ways:

  REAL GAPS battery J closes (each claim re-verified by construction):
  * is_valid_image_async 6/7 -- the flipped/==1 gate SWAPS the "Empty image
    file detected" vs "Image file too small" messages between the 0-byte and
    1-byte files; battery I counts fragments (1 + 1 still 1 + 1). J asserts
    the message PATH attribution, not counts.
  * is_valid_image_async 15 -- the async PermissionError debug arm is never
    driven by battery I (only the sync arm); debug(None) survives.
  * _create_event_handler 4 -- `or True` lives in on_created only; battery I
    drives bytes src_path on on_modified only. Under the mutant on_created
    schedules the UNDECODED bytes path (bytes != str in the recorder).
  * _create_event_handler 12 -- the and->or flip lives in on_modified only;
    the discriminator is a DIRECTORY on_modified event whose path has a
    supported suffix: orig ignores, mutant schedules.
  * __init__ 62 -- the else-arm "XXXX" survives `"interval=" not in msg`.
    J asserts ", interval=7.5s" PRESENT on a polling build and the absence
    of the filler on a native build.
  * _process_file extra-rename family -- battery I asserts SOME attrs per
    record, never the COMPLETE set: the "Processing file" debug never
    asserted file_path; the queue-error arm never asserted camera_id /
    file_path. J asserts every source-visible attr on every record it drives.
  * _process_file duration arithmetic (happy + error arm) -- invisible while
    elapsed == 0; J advances the pinned clock EXACTLY 1.0 s inside the
    stability stub, so duration_ms must be 1000 (/1000 -> 0, *1001 -> 1001).
  * _queue_for_detection 3 -- fragment match passes XX-wrapped text; J uses
    message EQUALITY.
  * _queue_for_detection 18/19 -- duplicate-skip record camera_id attr
    never asserted by battery I.
  * _queue_for_detection 78 -- `if file_hash or True` only observable on the
    streams path WITHOUT a dedupe service (file_hash stays None): J asserts
    "file_hash" absent from extra_fields there (mutant adds file_hash=None).
  * queue delay gates (both arms) -- zero-delay STREAMS never driven (battery
    I's zero-delay test is legacy-side), and delay_ms == 1 discriminates the
    `> 0 -> > 1` variants on both arms (sleep 0.001 vs none).
  * _wait_for_file_stability 7 (init +1) -- a 1-BYTE file: orig sees the
    first size != init, sets stable_since and returns True at 2.0 s; under
    the +1 init the first size EQUALS it, stable_since is never set and the
    loop gives up False. 6/8 (None/-2) stay unreachable inits (registered).
  * start message/attr family -- battery I matches by fragment; J pins the
    exact strings and the real error attr (get_running_loop's RuntimeError
    says "no running event loop" -- str(None) loses that).
  * start success-debug record attrs (camera_root / loop_running /
    loop_closed) -- never asserted by battery I.
  * start dead-guard arms REACHED via a module-scope asyncio proxy whose
    get_running_loop returns a DEAD (not running) loop, and a variant that
    returns None: the "not running" / "returned None" RuntimeError arms do
    execute, so their extra payloads are observable after all.
  * start 70 -- `!= "native" or errno is None -> and`: a POLLING-mode watcher
    whose observer.start() raises OSError(ENOSPC) must RAISE under orig
    (mode != native is True -> or short-circuits True); the and-mutant
    swallows and falls back. J asserts the raise.
  * start 75/79 -- the OSError-arm fallback log's camera_root attr (str root
    vs None vs "None") is never asserted by battery I (only the probe-arm
    test asserts it, on a different call site).
  * start 80/82/85/86/87 -- the OSError-arm RE-SCHEDULE happens on the
    REPLACED PollingObserver, so battery I's _FakeObs never sees the args;
    J patches fw.PollingObserver (autospec, return_value=_FakeObs) so the
    re-schedule is recorded and asserts (handler, str(root), True).
  * stop messages 3/9/35/42 -- fragment match passes XX text; equality
    closes all four.

  Registered EQUIVALENT (J does NOT try; sweep must prove each GREEN):
  * _wait_for_file_stability 6/8/9: last_size init -1 -> None / -2 and
    stable_since init None -> "" -- no real stat size equals those and the
    changed-branch overwrites stable_since before any read; (+1 = key 7 is
    killed above via the 1-byte file).
  * _queue_for_detection 6 (file_hash init -> ""): both falsy, only feeds
    `if file_hash:`; and 71/73/76: the streams .get("pipeline_start_time",
    DEFAULT) defaults are unreachable -- the key is always present in
    detection_data.
  * _schedule_file_processing 10: pop(file_path, None) -> pop(file_path, )
    -- the cleanup `is t` guard guarantees presence.
  * start 44/46/48: mkdir exist_ok True -> False/None/dropped -- the branch
    runs only when the directory is MISSING, where exist_ok is irrelevant.
  * _create_event_handler 33: `if self.watcher._loop else False` -> `and
    False` -- inside the else-arm _loop is falsy on entry; both sides False.
  * stop 13: gather(*tasks) arg-drop -- tasks are cancel()d synchronously
    before the gather and every later await yields to the loop, so no
    in-process channel distinguishes them.
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
from backend.core.redis import QueueAddResult

MIN_SIZE = fw.MIN_IMAGE_FILE_SIZE
_REAL_ASYNCIO = asyncio


# ---------------------------------------------------------------------------
# machinery (mirrors battery I -- the sweep loads ONE battery per process, so
# no cross-import; keep the two files' helpers behaviourally identical)
# ---------------------------------------------------------------------------


class _Capture(logging.Handler):
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
    def __init__(self, start: float = 1000.0) -> None:
        self.t = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.t

    def monotonic(self) -> float:
        return self.t

    def sleep(self, d: float) -> None:
        self.sleeps.append(float(d))
        self.t += float(d)

    async def asleep(self, d: float) -> None:
        self.sleeps.append(float(d))
        self.t += float(d)


class _AsyncProxy:
    def __init__(self, real, asleep=None, loop_result=..., loop_raises=...) -> None:
        self._real = real
        self._asleep = asleep
        self._loop_result = loop_result
        self._loop_raises = loop_raises

    def get_running_loop(self):
        if self._loop_raises is not ...:
            raise self._loop_raises
        if self._loop_result is not ...:
            return self._loop_result
        return self._real.get_running_loop()

    def __getattr__(self, name):
        if name == "sleep" and self._asleep is not None:
            return self._asleep
        return getattr(self._real, name)


@contextlib.contextmanager
def _time_patch(clock: _Clock, fake_sleep: bool = True, loop_result=..., loop_raises=...):
    old_time, old_asyncio = fw.time, fw.asyncio
    fw.time = clock
    fw.asyncio = _AsyncProxy(
        _REAL_ASYNCIO, clock.asleep if fake_sleep else None, loop_result, loop_raises
    )
    try:
        yield clock
    finally:
        fw.time = old_time
        fw.asyncio = old_asyncio


def _run(
    coro, clock: _Clock | None = None, fake_sleep: bool = True, loop_result=..., loop_raises=...
):
    clk = clock or _Clock()
    with _time_patch(clk, fake_sleep=fake_sleep, loop_result=loop_result, loop_raises=loop_raises):
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


class _Recorder:
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


class _FakeObs:
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


def _valid_image(path, size=None):
    w = h = 64
    data = bytes((x + y) % 256 for y in range(h) for x in range(w * 3))
    Image.frombytes("RGB", (w, h), data).save(path, "JPEG")
    if size is None:
        size = MIN_SIZE + 1024
    pad = size - path.stat().st_size
    if pad < 0:  # pragma: no cover
        raise AssertionError(f"image already exceeds {size} bytes")
    # nosemgrep: path-traversal-open - path is a pytest tmp_path fixture file
    with open(path, "ab") as fh:
        fh.write(b"\0" * pad)
    return path


def _file(path, nbytes):
    path.write_bytes(b"\0" * nbytes)
    return path


def _fp(root, name):
    return pathlib.Path(root) / name


def _mkwatcher(root, **kw):
    with _use_settings(_settings()):
        return fw.FileWatcher(camera_root=str(root), watch_probe=lambda _p: _ProbeOk(), **kw)


class _RecorderSubs(fw.FileWatcher):
    stub_wait = True

    def __init__(self, *a, stable=True, advance=0.0, **kw) -> None:
        super().__init__(*a, **kw)
        self._stable = stable
        self._advance = advance
        self.clock = None  # set by tests that need elapsed time
        self.stability_calls: list[tuple] = []
        self.ensure_calls: list[tuple] = []
        self.queue_calls: list[tuple] = []

    async def _wait_for_file_stability(self, file_path, stability_time=None):
        if not self.stub_wait:
            return await super()._wait_for_file_stability(file_path, stability_time)
        self.stability_calls.append((file_path, stability_time))
        if self.clock is not None:
            self.clock.t += self._advance
        return self._stable

    async def _ensure_camera_exists(self, camera_id, folder_name):
        self.ensure_calls.append((camera_id, folder_name))

    async def _queue_for_detection(self, camera_id, file_path, media_type=None):
        self.queue_calls.append((camera_id, file_path, media_type))


class _SchedSubs(fw.FileWatcher):
    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.process_calls: list[tuple] = []

    async def _process_file(self, file_path):
        self.process_calls.append((file_path,))


class _RealWait(_RecorderSubs):
    stub_wait = False


# ---------------------------------------------------------------------------
# 1. async validator: message attribution + PermissionError debug arm
# ---------------------------------------------------------------------------


def test_async_empty_and_tiny_messages_are_attributed_per_file():
    """is_valid_image_async 6/7: a flipped or ==1 gate SWAPS the two warning
    messages between the 0-byte and 1-byte files -- fragment COUNTS stay 1+1,
    attribution does not."""
    root = tempfile.mkdtemp()
    try:
        empty = _file(_fp(root, "e.png"), 0)
        tiny = _file(_fp(root, "t.png"), 1)

        async def body():
            assert await fw.is_valid_image_async(str(empty)) is False
            assert await fw.is_valid_image_async(str(tiny)) is False

        with _capture_logs() as logs:
            _run(body())
        empties = logs.by_fragment("Empty image file detected")
        assert len(empties) == 1, [r.getMessage() for r in logs.records]
        assert empties[0].getMessage() == f"Empty image file detected: {empty}"
        smalls = logs.by_fragment("Image file too small")
        assert len(smalls) == 1
        assert smalls[0].getMessage() == (
            f"Image file too small (1 bytes, minimum {MIN_SIZE}): {tiny}"
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_async_permission_error_arm_logs_debug_retry_message():
    """is_valid_image_async 15: the async retry arm's debug message is the
    only survivor reachable there; debug(None) must not pass."""
    root = tempfile.mkdtemp()
    try:
        target = _file(_fp(root, "p.jpg"), 64)
        real_path = fw.Path

        class _NoPermPath(real_path):  # type: ignore[valid-type,misc]
            def exists(self):
                raise PermissionError(1, "denied")

        clock = _Clock()

        async def body():
            assert await fw.is_valid_image_async(str(target)) is False

        fw.Path = _NoPermPath
        try:
            with _capture_logs() as logs:
                _run(body(), clock)
        finally:
            fw.Path = real_path
        assert clock.sleeps[:1] == [1.0], clock.sleeps
        dbg = logs.by_fragment("Image validation got PermissionError, retrying in 1s")
        assert len(dbg) == 1
        assert str(target) in dbg[0].getMessage()
        assert logs.by_fragment("validation failed after retry (corrupt/truncated)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. constructor init-log payload
# ---------------------------------------------------------------------------


def test_init_log_polling_info_exact_on_both_branches():
    """__init__ 62: the else-arm literal 'XXXX' passes `"interval=" not in
    msg`; pin the polling branch's interval text and the filler's absence."""
    root = tempfile.mkdtemp()
    try:
        with (
            _use_settings(_settings()),
            _capture_logs() as logs,
        ):
            fw.FileWatcher(
                camera_root=root,
                use_polling=True,
                polling_interval=7.5,
                watch_probe=lambda _p: _ProbeOk(),
            )
            fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        msgs = [r.getMessage() for r in logs.by_fragment("FileWatcher initialized for camera root")]
        assert len(msgs) == 2, msgs
        assert ", interval=7.5s," in msgs[0], msgs[0]
        assert "observer=polling" in msgs[0]
        assert "interval=" not in msgs[1]
        assert "XXXX" not in msgs[1]
        assert "observer=native" in msgs[1]
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 3. event handler: bytes on_created, directory on_modified
# ---------------------------------------------------------------------------


def test_created_event_with_bytes_path_schedules_the_decoded_str():
    """_create_event_handler 4: `or True` in on_created keeps bytes
    (Path(b'..').suffix still validates!), so the mutant schedules the raw
    bytes -- the recorder tuple proves str vs bytes."""
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = _SchedSubs(camera_root=root, debounce_delay=0.0, watch_probe=lambda _p: _ProbeOk())
        target = str(_fp(root, "Front Door/a.jpg"))
        ev_bytes = types.SimpleNamespace(src_path=target.encode(), is_directory=False)

        async def body():
            w._loop = asyncio.get_running_loop()
            w._event_handler.on_created(ev_bytes)
            await _REAL_ASYNCIO.sleep(0.05)

        _run(body(), fake_sleep=False)
        assert w.process_calls == [(target,)], w.process_calls
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_directory_modified_event_is_never_scheduled():
    """_create_event_handler 12: and->or in on_modified schedules a DIRECTORY
    event as long as its path has a supported suffix."""
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = _SchedSubs(camera_root=root, debounce_delay=0.0, watch_probe=lambda _p: _ProbeOk())
        dir_path = str(_fp(root, "Front Door"))
        ev_dir_jpg = types.SimpleNamespace(src_path=dir_path + ".jpg", is_directory=True)

        async def body():
            w._loop = asyncio.get_running_loop()
            w._event_handler.on_modified(ev_dir_jpg)
            await _REAL_ASYNCIO.sleep(0.05)

        _run(body(), fake_sleep=False)
        assert w.process_calls == [], w.process_calls
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. _process_file: complete extra attrs + real elapsed durations
# ---------------------------------------------------------------------------


def _cam_img(root):
    cam = _fp(root, "Front Door")
    cam.mkdir()
    return cam, _valid_image(cam / "a.jpg")


def test_process_file_every_record_carries_the_complete_extra_set():
    """Happy-path debug + queue-error extra dicts: EVERY key the source puts
    in extra= must be present on the record with the right value (the rename
    family hides wherever battery I asserted only a subset)."""
    root = tempfile.mkdtemp()
    try:
        cam, img = _cam_img(root)

        with _use_settings(_settings()):
            w = _RecorderSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        clock = _Clock()
        with unittest.mock.patch.object(fw, "record_pipeline_stage_latency", autospec=True) as lat:
            with _capture_logs() as logs:
                _run(w._process_file(str(img)), clock)
        dbg = logs.by_fragment(f"Processing file: {img}")
        assert len(dbg) == 1
        assert getattr(dbg[0], "camera_id", None) == "front_door"
        assert getattr(dbg[0], "file_path", None) == str(img)
        assert getattr(dbg[0], "media_type", None) == "image"
        info = logs.by_fragment(f"Queued image for detection: {img} (camera: front_door)")
        assert len(info) == 1
        assert getattr(info[0], "camera_id", None) == "front_door"
        assert getattr(info[0], "file_path", None) == str(img)
        assert getattr(info[0], "media_type", None) == "image"
        assert lat.call_args_list != []

        class _Boom(_RecorderSubs):
            async def _queue_for_detection(self, camera_id, file_path, media_type=None):
                self.queue_calls.append((camera_id, file_path, media_type))
                raise RuntimeError("j exploded")

        with _use_settings(_settings()):
            w2 = _Boom(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        with unittest.mock.patch.object(fw, "record_pipeline_stage_latency", autospec=True) as lat2:
            with _capture_logs() as logs2:
                _run(w2._process_file(str(img)))
        lat2.assert_not_called()
        err = logs2.by_fragment(f"Failed to queue image {img}: j exploded")
        assert len(err) == 1
        assert getattr(err[0], "camera_id", None) == "front_door"
        assert getattr(err[0], "file_path", None) == str(img)
        assert getattr(err[0], "media_type", None) == "image"

        # unsupported-file debug + no-camera-id warning attrs
        txt = cam / "note.txt"
        txt.write_text("hi")
        with _use_settings(_settings()):
            w3 = _RecorderSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        with _capture_logs() as logs3:
            _run(w3._process_file(str(txt)))
        un = logs3.by_fragment(f"Skipping unsupported file: {txt}")
        assert len(un) == 1
        assert getattr(un[0], "camera_id", None) == "front_door"
        assert getattr(un[0], "file_path", None) == str(txt)

        # never-stabilized warning (34/35 rename family): real stability,
        # impossible window -> the warning record's full extra set
        with _use_settings(_settings()):
            w5 = _RealWait(
                camera_root=root, stability_time=10000.0, watch_probe=lambda _p: _ProbeOk()
            )
        with _capture_logs() as logs5:
            _run(w5._process_file(str(img)), _Clock())
        ns = logs5.by_fragment(
            f"Skipping file that never stabilized (may still be uploading): {img}"
        )
        assert len(ns) == 1
        assert getattr(ns[0], "camera_id", None) == "front_door"
        assert getattr(ns[0], "file_path", None) == str(img)
        assert getattr(ns[0], "media_type", None) == "image"

        # invalid/corrupted warning (46/47 rename family): a 0-byte image
        zero = cam / "z.jpg"
        zero.write_bytes(b"")
        with _use_settings(_settings()):
            w6 = _RecorderSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        with _capture_logs() as logs6:
            _run(w6._process_file(str(zero)))
        bad = logs6.by_fragment(f"Skipping invalid/corrupted image file: {zero}")
        assert len(bad) == 1
        assert getattr(bad[0], "camera_id", None) == "front_door"
        assert getattr(bad[0], "file_path", None) == str(zero)
        assert getattr(bad[0], "media_type", None) == "image"

        outside = _valid_image(_fp(tempfile.mkdtemp(), "b.jpg"))
        with _use_settings(_settings()):
            w4 = _RecorderSubs(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        with _capture_logs() as logs4:
            _run(w4._process_file(str(outside)))
        warn = logs4.by_fragment(f"Could not determine camera ID for: {outside}")
        assert len(warn) == 1
        assert getattr(warn[0], "file_path", None) == str(outside)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_process_file_duration_ms_tracks_real_elapsed_time():
    """Duration arithmetic survivors: with a pinned clock, advancing EXACTLY
    1.0 s inside the stability stub forces duration_ms == 1000 (the /1000
    mutants give 0, the *1001 mutants 1001) on BOTH the success and error
    arms."""

    def harness(boom: bool):
        root = tempfile.mkdtemp()
        try:
            _cam, img = _cam_img(root)
            clock = _Clock()
            base = _RecorderSubs

            class _W(base):
                async def _queue_for_detection(self, camera_id, file_path, media_type=None):
                    self.queue_calls.append((camera_id, file_path, media_type))
                    if boom:
                        raise RuntimeError("slow explode")

            with _use_settings(_settings()):
                w = _W(camera_root=root, watch_probe=lambda _p: _ProbeOk())
            w.clock = clock
            w._advance = 1.0
            with unittest.mock.patch.object(
                fw, "record_pipeline_stage_latency", autospec=True
            ) as lat:
                with _capture_logs() as logs:
                    _run(w._process_file(str(img)), clock)
            if boom:
                rec = logs.by_fragment(f"Failed to queue image {img}: slow explode")
                assert len(rec) == 1
                assert getattr(rec[0], "duration_ms", None) == 1000
                assert lat.call_args_list == []
            else:
                rec = logs.by_fragment(f"Queued image for detection: {img}")
                assert len(rec) == 1
                assert getattr(rec[0], "duration_ms", None) == 1000
                assert lat.call_args[0][1] == 1000.0
        finally:
            shutil.rmtree(root, ignore_errors=True)

    harness(boom=False)
    harness(boom=True)


# ---------------------------------------------------------------------------
# 5. _queue_for_detection payloads and delay gates
# ---------------------------------------------------------------------------


def test_queue_no_redis_warning_message_is_exact():
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root, redis_client=None, watch_probe=lambda _p: _ProbeOk()
            )

        async def body():
            await w._queue_for_detection("cam", "/x/a.jpg", "image")

        with _capture_logs() as logs:
            _run(body())
        arm = logs.by_fragment("Redis client not configured")
        assert len(arm) == 1
        assert arm[0].getMessage() == "Redis client not configured, skipping queue"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_duplicate_skip_record_carries_camera_id():
    root = tempfile.mkdtemp()
    try:
        dedupe = _AsyncRecorder(is_duplicate_and_mark=(True, "h" * 40))
        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=_AsyncRecorder(),
                dedupe_service=dedupe,
                watch_probe=lambda _p: _ProbeOk(),
            )

        async def body():
            await w._queue_for_detection("front_door", "/x/dup.jpg", "image")

        with _capture_logs() as logs:
            _run(body())
        skip = logs.by_fragment("Skipping duplicate file: /x/dup.jpg")
        assert len(skip) == 1
        assert getattr(skip[0], "camera_id", None) == "front_door"
        assert getattr(skip[0], "file_path", None) == "/x/dup.jpg"
        assert getattr(skip[0], "file_hash", None) == "h" * 40
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_streams_extra_fields_omits_file_hash_when_absent():
    """queue 78: `if file_hash or True` is only visible streams-side WITHOUT
    a dedupe service -- then file_hash is None and must NOT be added."""
    root = tempfile.mkdtemp()
    try:
        stream = _AsyncRecorder()
        dedupe = _AsyncRecorder(is_duplicate_and_mark=(False, None))

        async def body():
            await w._queue_for_detection("front_door", "/x/n.jpg", "image")

        with _use_settings(_settings(use_redis_streams=True)):
            w = fw.FileWatcher(
                camera_root=root,
                redis_client=_AsyncRecorder(),
                dedupe_service=dedupe,
                watch_probe=lambda _p: _ProbeOk(),
            )
            with unittest.mock.patch.object(
                fw, "get_detection_stream_service", autospec=True, return_value=stream
            ):
                _run(body())
        name, _args, kwargs = stream.calls[0]
        assert name == "add_detection"
        ef = kwargs["extra_fields"]
        assert set(ef) == {"timestamp", "media_type", "pipeline_start_time"}, ef
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_delay_zero_sleeps_on_neither_arm():
    root = tempfile.mkdtemp()
    try:
        # legacy arm
        clock1 = _Clock()
        redis = _AsyncRecorder()
        redis_result = QueueAddResult(success=True, queue_length=1)
        redis._returns["add_to_queue_safe"] = redis_result

        async def legacy():
            await w._queue_for_detection("cam", "/x/z.jpg", "image")

        with _use_settings(_settings(file_watcher_queue_delay_ms=0)):
            w = fw.FileWatcher(
                camera_root=root, redis_client=redis, watch_probe=lambda _p: _ProbeOk()
            )
            _run(legacy(), clock1)
        assert clock1.sleeps == [], clock1.sleeps

        # streams arm -- the battery-I zero-delay test never drove this one
        clock2 = _Clock()
        stream = _AsyncRecorder()

        async def streams():
            await w._queue_for_detection("cam", "/x/z.jpg", "image")

        with _use_settings(_settings(use_redis_streams=True, file_watcher_queue_delay_ms=0)):
            with unittest.mock.patch.object(
                fw, "get_detection_stream_service", autospec=True, return_value=stream
            ):
                _run(streams(), clock2)
        assert clock2.sleeps == [], clock2.sleeps
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_queue_delay_one_ms_sleeps_exactly_one_millisecond_on_both_arms():
    """`> 0 -> > 1` variants: delay_ms == 1 still sleeps 0.001 under orig."""
    root = tempfile.mkdtemp()
    try:
        clock1 = _Clock()
        redis = _AsyncRecorder()
        redis._returns["add_to_queue_safe"] = QueueAddResult(success=True, queue_length=1)

        async def legacy():
            await w._queue_for_detection("cam", "/x/one.jpg", "image")

        with _use_settings(_settings(file_watcher_queue_delay_ms=1)):
            w = fw.FileWatcher(
                camera_root=root, redis_client=redis, watch_probe=lambda _p: _ProbeOk()
            )
            _run(legacy(), clock1)
        assert clock1.sleeps == [0.001], clock1.sleeps

        clock2 = _Clock()
        stream = _AsyncRecorder()

        async def streams():
            await w._queue_for_detection("cam", "/x/one.jpg", "image")

        with _use_settings(_settings(use_redis_streams=True, file_watcher_queue_delay_ms=1)):
            with unittest.mock.patch.object(
                fw, "get_detection_stream_service", autospec=True, return_value=stream
            ):
                _run(streams(), clock2)
        assert clock2.sleeps == [0.001], clock2.sleeps
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 6. stability init sentinel (+1)
# ---------------------------------------------------------------------------


def test_one_byte_file_stabilizes_because_size_differs_from_init():
    """stability 7: last_size init -1 -> +1 makes a 1-byte file look stable
    from check #1 with stable_since never set -- orig returns True at 2.0 s,
    the +1 mutant gives up False after 20 checks."""
    root = tempfile.mkdtemp()
    try:
        one = _file(_fp(root, "one.jpg"), 1)
        with _use_settings(_settings()):
            w = fw.FileWatcher(camera_root=root, watch_probe=lambda _p: _ProbeOk())
        clock = _Clock()

        async def body():
            return await w._wait_for_file_stability(str(one), 2.0)

        with _capture_logs() as logs:
            verdict = _run(body(), clock)
        assert verdict is True
        assert sum(clock.sleeps) == 2.0, clock.sleeps
        assert not logs.by_fragment("never stabilized")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 7. start(): exact strings, real error attr, guard arms, fallback args
# ---------------------------------------------------------------------------


def _exact(record, text):
    assert record.getMessage() == text, record.getMessage()


def test_start_already_running_message_is_exact():
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        w.running = True
        w.observer = _FakeObs()
        with _capture_logs() as logs:
            _run(w.start())
        arm = logs.by_fragment("already running")
        assert len(arm) == 1
        _exact(arm[0], "FileWatcher already running")
    finally:
        shutil.rmtree(root, ignore_errors=True)


_NO_LOOP_MSG = (
    "FileWatcher MUST be started within an async context (e.g., during "
    "FastAPI lifespan). No running event loop detected - file events "
    "will be lost. This is a critical configuration error."
)


def test_start_no_loop_error_message_and_error_attr_are_real():
    """start 8/17: XX-wrapped message text and str(None) both pass the
    old fragment / key-presence asserts."""
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        with _capture_logs() as logs:
            coro = w.start()
            raised = None
            try:
                coro.send(None)
            except RuntimeError as e:
                raised = e
            finally:
                coro.close()
        assert raised is not None
        assert str(raised) == _NO_LOOP_MSG
        arm = logs.by_fragment("MUST be started within an async context")
        assert len(arm) == 1
        _exact(arm[0], _NO_LOOP_MSG)
        assert getattr(arm[0], "camera_root", None) == str(root)
        assert "no running event loop" in getattr(arm[0], "error", "")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_success_debug_record_carries_exact_attrs():
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        w.observer = _FakeObs()
        with _capture_logs() as logs:
            _run(w.start())
        dbg = logs.by_fragment("Event loop captured successfully")
        assert len(dbg) == 1
        _exact(dbg[0], "Event loop captured successfully for FileWatcher")
        assert getattr(dbg[0], "camera_root", None) == str(root)
        assert getattr(dbg[0], "loop_running", None) is True
        assert getattr(dbg[0], "loop_closed", None) is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


class _DeadLoop:
    def is_running(self):
        return False

    def is_closed(self):
        return True


_NOT_RUNNING_MSG = (
    "Captured event loop is not running. FileWatcher requires "
    "a running event loop for thread-safe task scheduling."
)
_NONE_LOOP_MSG = (
    "Event loop capture returned None. FileWatcher cannot function "
    "without a valid event loop. This should not happen - please report this bug."
)


def test_start_dead_loop_guard_executes_with_extra_payload():
    """start 24/26: the 'not running' guard is reachable with a module-scope
    asyncio proxy -- the guard's extra payload is then observable."""
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        with _capture_logs() as logs:
            raised = None
            try:
                _run(w.start(), loop_result=_DeadLoop())
            except RuntimeError as e:
                raised = e
        assert raised is not None
        assert str(raised) == _NOT_RUNNING_MSG
        arm = logs.by_fragment("Captured event loop is not running")
        assert len(arm) == 1
        _exact(arm[0], _NOT_RUNNING_MSG)
        assert getattr(arm[0], "camera_root", None) == str(root)
        assert getattr(arm[0], "loop_closed", None) is True
        assert w.running is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_none_loop_guard_executes_with_extra_payload():
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        with _capture_logs() as logs:
            raised = None
            try:
                _run(w.start(), loop_result=None)
            except RuntimeError as e:
                raised = e
        assert raised is not None
        assert str(raised) == _NONE_LOOP_MSG
        arm = logs.by_fragment("Event loop capture returned None")
        assert len(arm) == 1
        _exact(arm[0], _NONE_LOOP_MSG)
        assert getattr(arm[0], "camera_root", None) == str(root)
        assert w.running is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_observer_oserror_on_polling_mode_raises_instead_of_falling_back():
    """start 70: with `and` instead of `or`, a POLLING watcher's ENOSPC stops
    raising and quietly falls back -- orig MUST re-raise (mode != native)."""
    root = tempfile.mkdtemp()
    try:
        with _use_settings(_settings()):
            w = fw.FileWatcher(
                camera_root=root,
                use_polling=True,
                watch_probe=lambda _p: _ProbeOk(),
            )
        assert w.watch_mode == "polling"
        w.observer = _FakeObs(start_raises=OSError(errno.ENOSPC, "no space"))
        raised = None
        try:
            _run(w.start())
        except OSError as e:
            raised = e
        assert raised is not None and raised.errno == errno.ENOSPC
        assert w.running is False
        assert w.watch_mode == "polling"  # no silent fallback
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_oserror_fallback_reschedules_with_exact_args_on_the_new_observer():
    """start 75-87 family: the OSError-arm re-schedule happens on the
    REPLACED observer -- patch fw.PollingObserver (autospec) to a recorder so
    schedule(handler, str(root), True) and the fallback log's camera_root are
    asserted, not just the mode flags."""
    root = tempfile.mkdtemp()
    try:
        w = _mkwatcher(root)
        w.observer = _FakeObs(start_raises=OSError(errno.ENOSPC, "no space"))
        fake2 = _FakeObs()
        with unittest.mock.patch.object(fw, "PollingObserver", autospec=True, return_value=fake2):
            with _capture_logs() as logs:
                _run(w.start())
        assert w.watch_mode == "polling-fallback"
        assert w.watch_fallback_reason == "ENOSPC"
        assert w.running is True
        assert fake2.schedule_calls == [(w._event_handler, str(root), True)], fake2.schedule_calls
        assert fake2.starts == 1
        err = logs.by_fragment("the kernel REFUSED an inotify watch on")
        assert len(err) == 1
        assert getattr(err[0], "camera_root", None) == str(root)
        assert getattr(err[0], "watch_errno", None) == "ENOSPC"
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 8. stop(): exact strings
# ---------------------------------------------------------------------------


def test_stop_messages_are_exact_on_both_paths():
    root = tempfile.mkdtemp()
    try:
        w = _SchedSubs(camera_root=root, debounce_delay=30.0, watch_probe=lambda _p: _ProbeOk())
        w.observer = _FakeObs()
        w._hash_executor = _Recorder()
        with _capture_logs() as logs:
            _run(w.stop())  # short path
        _exact(
            logs.by_fragment("not running, nothing to stop")[0],
            "FileWatcher not running, nothing to stop",
        )

        with _capture_logs() as logs:

            async def body():
                await w._schedule_file_processing("/x/p.jpg")
                w.running = True
                await w.stop()

            _run(body(), fake_sleep=False)
        _exact(logs.by_fragment("Stopping FileWatcher")[0], "Stopping FileWatcher")
        _exact(logs.by_fragment("Hash executor shut down")[0], "Hash executor shut down")
        _exact(logs.by_fragment("FileWatcher stopped")[0], "FileWatcher stopped")
    finally:
        shutil.rmtree(root, ignore_errors=True)
