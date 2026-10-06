# TARGET-MODULE: backend.services.transcoding_service
"""Battery AV - campaign #46 kill battery for backend/services/transcoding_service.py.

Style (proven on AT..AU): every observable an entered branch WRITES is asserted
([[entered-branch-must-assert-every-observable-it-writes]]) - return value, the
module globals it assigns, the exact log LEVEL+MESSAGE (FULL equality, never a
fragment: fragments and count pins pass XX-twins and message SWAPs -
[[fragment-count-asserts-pass-xx-mutants]]), and every subprocess argv pinned
as the WHOLE list. Dropped kwargs die at the CALL SITE on key-presence in a
raw capture the shipped call never refills
([[dropped-kwarg-mutants-needs-call-site-spy]]): the module-level literals
(codec/preset/crf strings) are RE-DECLARED HERE on purpose - reading ts's
constants would let a constant-twin mutant round-trip.
Log pins ride REAL LogRecords on the REAL logger ([[log-context-filter-fakes-extra-kwarg-mutants]]);
BY-NAME extra access never trips on the filter's ambient keys. Error-text
pins whose exception message carries an OS string (errno text) are computed
from a PROBE of the same deterministic operation, then pinned by FULL
equality - never by substring.
NO pytest fixtures anywhere: b30-sweep calls these functions directly with no
pytest machinery ([[b30-sweep-no-fixtures-tmp-path-fake-hang-storm]]); temp
worlds come from tempfile.mkdtemp inside contextmanagers that always clean up.
Settings are stubbed to explicit SimpleNamespaces so pins do not couple to the
environment.

Measured pins from the SHIPPED source (read 2026-10-06, lines cited):
- check_nvenc_available (L74-137): cache guard `is not None`; query argv
  ["ffmpeg","-hide_banner","-encoders"] then probe argv
  ["ffmpeg","-hide_banner","-f","lavfi","-i","nullsrc=s=64x64:d=0.1","-c:v",
  "h264_nvenc","-f","null","-"], each kwargs EXACTLY
  {"capture_output":True,"text":True,"timeout":10,"check":False}; guard
  `returncode == 0 and "h264_nvenc" in stdout`. Logs: INFO "NVENC hardware
  acceleration is available and working"; WARNING "NVENC encoder found but
  test failed, falling back to software encoding" extra stderr=
  test_result.stderr[:500] if stderr else "" (BOTH the 500-truncation and the
  falsy->"" conversion are load-bearing); INFO "NVENC encoder not available,
  using software encoding (libx264)"; WARNING "ffmpeg not found, cannot check
  NVENC availability" / "NVENC check timed out, assuming unavailable" /
  f"Error checking NVENC availability: {e}". EVERY path ASSIGNS
  _nvenc_available; the cached read-back makes a wrong assignment observable
  on the SECOND call (call-count pin).
- get_video_encoder_args (L146-187): `use_hardware and
  settings.hardware_acceleration_enabled and check_nvenc_available()` -
  short-circuit ORDER pinned by an order-witness: use_hardware=False or the
  setting off must NOT call the detector. HW list equality
  ["-c:v","h264_nvenc","-preset",<preset>,"-cq",str(<cq>),"-pix_fmt","yuv420p"]
  (str() wrap + all-strings), SW list ["-c:v","libx264","-preset","fast",
  "-crf","23","-pix_fmt","yuv420p"]. BOTH log lines are DEBUG (measured).
- _validate_video_path (L190-210): messages f"Video file not found:
  {video_path}"/f"Path is not a file: {video_path}" interpolate the ORIGINAL
  argument; the resolved path is returned. The dash-guard (L208) is
  UNREACHABLE through a real resolve() (an absolute path never starts with
  "-") - no row is written for an unreachable branch.
- _compute_file_hash (L213-230): hashlib.md5(f"{path}:{st_mtime}:{st_size}"
  .encode(), usedforsecurity=False).hexdigest() - pinned component-wise off a
  REAL hashlib.md5 spy + the RAW call kwargs, plus a same-mtime different-size
  second hash proving the st_size term is load-bearing.
- TranscodingService.__init__ (L263-286): `cache_directory if cache_directory
  is not None else getattr(settings,"transcoding_cache_directory",
  "data/transcoded_cache")` - "" is NOT None (truthiness twin takes the
  settings branch); the absent-setting row KILLS the deleted-default (2-arg
  getattr) twin by raising AttributeError and pins the constant. INFO
  f"TranscodingService initialized: cache_directory={dir}" + DEBUG
  f"Transcoding cache directory ready: {dir}" from _ensure_cache_directory
  (L288-297), whose error text is f"Failed to create transcoding cache
  directory {dir}: {e}" and RE-RAISES.
- get_cached_video (L316-351): ValueError -> WARNING f"Cache lookup failed -
  path validation error: {e}" + None; hit DEBUG f"Cache hit for video:
  {video_path} -> {cache_path}" (ORIGINAL arg interpolated); corrupted gate
  `file_size < 1000` STRICT (exactly 1000 is KEPT) -> WARNING f"Removing
  corrupted cache file ({file_size} bytes): {cache_path}" + unlink + None;
  miss DEBUG f"Cache miss for video: {video_path}".
- _remux_video (L377-447): argv ["ffmpeg","-y","-i",<video>,"-c:v","copy",
  "-c:a","copy","-movflags","+faststart",<cache>]; exec kwargs EXACTLY
  {"stdout":PIPE,"stderr":PIPE} with the REAL asyncio.subprocess.PIPE
  sentinel; wait_for kwargs EXACTLY {"timeout":30.0}; success
  `returncode == 0 and cache_path.exists()` then `file_size > 1000` STRICT
  (exactly 1000 unlinks + WARNING suspiciously-small, mutant >= returns it).
  Levels measured: "Attempting fast remux" INFO, "FFmpeg remux command"
  DEBUG, "Fast remux successful" INFO, small-file WARNING,
  f"Remux failed (returncode={rc}), will try full transcode" DEBUG,
  "Remux timed out, falling back to transcode" WARNING (except TimeoutError),
  f"Remux failed with exception: {e}, will try full transcode" DEBUG; all
  fail paths unlink(missing_ok=True) -> None.
- transcode_video (L449-532): validated path; cache short-circuit
  `if not force and cache_path.exists()` INFO f"Using cached transcoded
  video: {cache_path}" BEFORE any subprocess; remux forwarding pins the
  encoder-args call NEVER happens (raw-capture witness: an arg_drop twin of
  get_video_encoder_args(use_hardware=True) is a MISSING key); full argv
  ["ffmpeg","-y","-i",<validated>,*encoder_args,"-c:a","aac","-movflags",
  "+faststart",<cache>]; rc!=0 -> ERROR f"FFmpeg transcoding failed: {msg}"
  + TranscodingError f"FFmpeg exited with code {rc}: {msg}" with
  msg = stderr.decode() if stderr else "Unknown error"; rc==0-no-file ->
  TranscodingError f"Transcoded file was not created: {cache_path}"; success
  INFO f"Transcoding complete: {cache_path} ({size} bytes)"; FileNotFoundError
  ERROR "ffmpeg not found. Please ensure ffmpeg is installed." +
  TranscodingError("ffmpeg not found") `from None` (__cause__ IS None);
  generic ERROR f"Transcoding failed: {e}" with exc_info +
  TranscodingError(f"Transcoding failed: {e}") `from e` (__cause__ IS the
  original). TranscodingError re-raises bare (no double-wrap).
- get_or_transcode (L534-569): browser-compat returns the VALIDATED path and
  NEVER consults the cache (call-witness); cache hit forwards; miss awaits
  transcode_video with the validated path and NO force kwarg.
- is_transcoding_needed (L353-375): suffix.lower() `not in (".mp4",)`.
- cleanup_cache (L571-606): glob f"*_transcoded.mp4"; age `> days*86400`;
  per-file OSError (broken symlink stat) WARNING f"Failed to delete cache
  file {f}: {e}" ISOLATED (healthy files still delete); outer except logs
  ERROR f"Cache cleanup failed: {e}" and RETURNS THE COUNT (no re-raise);
  the summary INFO f"Cache cleanup: deleted {n} files older than {d} days"
  exists ONLY when n > 0.
- delete_cached (L608-632): success DEBUG f"Deleted cached transcoded file:
  {cache_path}" True; absent DEBUG f"No cached file to delete for:
  {video_path}" (ORIGINAL arg) False; ValueError False; OSError WARNING
  f"Failed to delete cached file: {e}" (ONLY {e} interpolated) False.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
import shutil
import subprocess as _real_subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

import backend.services.transcoding_service as ts

# ============================================================================
# Re-declared shipped constants (NEVER read from ts - see header)
# ============================================================================
SW_CODEC = "libx264"
NV_CODEC = "h264_nvenc"
AAC = "aac"
PIX = "yuv420p"
CONTAINER = "mp4"
CRF = "23"
PRESET_SW = "fast"
QUERY_ARGV = ["ffmpeg", "-hide_banner", "-encoders"]
PROBE_ARGV = [
    "ffmpeg",
    "-hide_banner",
    "-f",
    "lavfi",
    "-i",
    "nullsrc=s=64x64:d=0.1",
    "-c:v",
    "h264_nvenc",
    "-f",
    "null",
    "-",
]
RUN_KWARGS = {"capture_output": True, "text": True, "timeout": 10, "check": False}
PIPE = asyncio.subprocess.PIPE


# ============================================================================
# Fixture-free world helpers
# ============================================================================


@contextlib.contextmanager
def _nv_state():
    """Reset BOTH module globals; restore on exit (trampoline M.__dict__ world)."""
    old_nv = ts._nvenc_available
    old_svc = ts._transcoding_service
    ts._nvenc_available = None
    ts._transcoding_service = None
    try:
        yield
    finally:
        ts._nvenc_available = old_nv
        ts._transcoding_service = old_svc


@contextlib.contextmanager
def tmpdir():
    d = Path(tempfile.mkdtemp(prefix="b46av-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.recs: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.recs.append(record)

    def one(self, msg: str, level: int | None = None) -> logging.LogRecord:
        hits = [r for r in self.recs if r.getMessage() == msg]
        assert len(hits) == 1, (msg, [r.getMessage() for r in self.recs])
        if level is not None:
            assert hits[0].levelno == level, (msg, hits[0].levelno)
        return hits[0]

    def none_containing(self, fragment: str) -> None:
        hits = [r.getMessage() for r in self.recs if fragment in r.getMessage()]
        assert not hits, f"log containing {fragment!r} must NOT exist: {hits}"


@contextlib.contextmanager
def logcap():
    h = _Records()
    old = ts.logger.level
    ts.logger.addHandler(h)
    ts.logger.setLevel(logging.DEBUG)
    try:
        yield h
    finally:
        ts.logger.removeHandler(h)
        ts.logger.setLevel(old)


def _extra(rec: logging.LogRecord, name: str) -> Any:
    """BY NAME, never an attr census; an extra= drop reads MISSING."""
    assert hasattr(rec, name), (name, "MISSING from record (extra= drop?)")
    return getattr(rec, name)


class RunSpy:
    """subprocess.run stand-in: FULL argv+kwargs recorded, outcomes replayed."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[tuple, dict]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        out = self.outcomes[len(self.calls) - 1]
        if isinstance(out, BaseException):
            raise out
        return out


def _sub_result(returncode: int = 0, stdout: str = "", stderr: Any = ""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


@contextlib.contextmanager
def run_spy(outcomes: list[Any]):
    spy = RunSpy(outcomes)
    ns = SimpleNamespace(run=spy, TimeoutExpired=_real_subprocess.TimeoutExpired)
    with mock.patch.object(ts, "subprocess", ns):
        yield spy


class ExecSpy:
    """asyncio.create_subprocess_exec stand-in (argv + kwargs, per-call action)."""

    def __init__(self, results: list[Any], actions: list[Any] | None = None) -> None:
        self.results = list(results)
        self.actions = actions or []
        self.calls: list[tuple[tuple, dict]] = []

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        i = len(self.calls) - 1
        if i < len(self.actions) and self.actions[i] is not None:
            self.actions[i]()
        res = self.results[i] if i < len(self.results) else self.results[-1]
        if isinstance(res, BaseException):
            raise res
        return res


def _process(
    returncode: int = 0,
    communicate_retval: Any = (b"", b""),
    exc: BaseException | None = None,
):
    proc = SimpleNamespace()
    proc.returncode = returncode

    async def communicate() -> Any:
        if exc is not None:
            raise exc
        return communicate_retval

    proc.communicate = communicate
    return proc


class WaitSpy:
    """asyncio.wait_for stand-in: records kwargs, then awaits OR raises."""

    def __init__(self, raise_exc: BaseException | None = None) -> None:
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    async def __call__(self, awaitable: Any, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        if self.raise_exc is not None:
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise self.raise_exc
        return await awaitable


@contextlib.contextmanager
def exec_world(
    results: list[Any],
    actions: list[Any] | None = None,
    wait_exc: BaseException | None = None,
):
    """Patches ts.asyncio: exec spy + wait spy; the PIPE identity stays REAL."""
    spy = ExecSpy(results, actions)
    wait = WaitSpy(wait_exc)
    ns = SimpleNamespace(
        create_subprocess_exec=spy,
        wait_for=wait,
        subprocess=SimpleNamespace(PIPE=PIPE),
    )
    with mock.patch.object(ts, "asyncio", ns):
        yield SimpleNamespace(exec=spy, wait=wait)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _settings(**kw: Any):
    return lambda: SimpleNamespace(**kw)


def _service(cache_dir: Path) -> Any:
    return ts.TranscodingService(cache_directory=str(cache_dir))


def _cache_path_for(service: Any, video: Path) -> Path:
    return service._get_cache_path(video)


# ============================================================================
# check_nvenc_available  (survivors: 71 of 89)
# ============================================================================


def test_nvenc_success_path_writes_every_observable():
    """Every argv token, every kwarg, the cache global, the INFO log, the
    call COUNT and the cached SECOND read (call-count frozen) all at once.
    The SECOND call also kills the `is not None` -> `is not False` guard
    twin: that re-enters subprocess on every call, so the spy count moves."""
    with (
        _nv_state(),
        logcap() as cap,
        run_spy([_sub_result(0, "has h264_nvenc now"), _sub_result(0)]) as spy,
    ):
        assert ts.check_nvenc_available() is True
        assert ts._nvenc_available is True
        assert len(spy.calls) == 2, spy.calls
        # subprocess.run takes the argv as ONE list arg (not *cmd): the
        # positional tuple has exactly 1 element and it is the full argv.
        assert len(spy.calls[0][0]) == 1
        assert spy.calls[0][0][0] == QUERY_ARGV
        assert spy.calls[0][1] == RUN_KWARGS
        assert len(spy.calls[1][0]) == 1
        assert spy.calls[1][0][0] == PROBE_ARGV
        assert spy.calls[1][1] == RUN_KWARGS
        cap.one("NVENC hardware acceleration is available and working", logging.INFO)
        assert ts.check_nvenc_available() is True
        assert len(spy.calls) == 2


def test_nvenc_cache_true_short_circuits_before_any_subprocess():
    with _nv_state(), run_spy([]) as spy:
        ts._nvenc_available = True
        assert ts.check_nvenc_available() is True
        assert spy.calls == []


def test_nvenc_cache_false_short_circuits_returns_false():
    """The `is not None` polarity twin reads subprocess instead of the cache;
    the return-constant twins die on the False return with zero calls."""
    with _nv_state(), run_spy([]) as spy:
        ts._nvenc_available = False
        assert ts.check_nvenc_available() is False
        assert spy.calls == []


def test_nvenc_probe_failure_path_logs_truncated_stderr():
    """stderr[:500] truncation is load-bearing: a 1200-char stderr must land
    as EXACTLY its first 500 chars in the WARNING's extra=stderr."""
    long_err = "E" * 1200
    with (
        _nv_state(),
        logcap() as cap,
        run_spy([_sub_result(0, "has h264_nvenc here"), _sub_result(1, "", long_err)]) as spy,
    ):
        assert ts.check_nvenc_available() is False
        assert ts._nvenc_available is False
        assert len(spy.calls) == 2
        rec = cap.one(
            "NVENC encoder found but test failed, falling back to software encoding",
            logging.WARNING,
        )
        assert _extra(rec, "stderr") == long_err[:500]
        assert len(_extra(rec, "stderr")) == 500


def test_nvenc_probe_failure_none_stderr_logs_empty_string():
    """`test_result.stderr else ""`: None stderr must log "" - the
    drop-the-else twin passes None straight into extra=."""
    with (
        _nv_state(),
        logcap() as cap,
        run_spy([_sub_result(0, "h264_nvenc"), _sub_result(1, "", None)]),
    ):
        assert ts.check_nvenc_available() is False
        rec = cap.one(
            "NVENC encoder found but test failed, falling back to software encoding",
            logging.WARNING,
        )
        assert _extra(rec, "stderr") == ""


def test_nvenc_query_nonzero_rc_path():
    """rc!=0 branch: ONE call, INFO not-available, cache False, return False."""
    with _nv_state(), logcap() as cap, run_spy([_sub_result(1, "anything")]) as spy:
        assert ts.check_nvenc_available() is False
        assert ts._nvenc_available is False
        assert len(spy.calls) == 1
        cap.one("NVENC encoder not available, using software encoding (libx264)", logging.INFO)
        cap.none_containing("NVENC hardware acceleration is available")


def test_nvenc_name_absent_path():
    """rc==0 but stdout lacks the encoder name: the `and`-to-`or` twin would
    take the probe branch (2nd call) - call count pins the `and`."""
    with (
        _nv_state(),
        logcap() as cap,
        run_spy([_sub_result(0, "libx264 - H.264 software only")]) as spy,
    ):
        assert ts.check_nvenc_available() is False
        assert ts._nvenc_available is False
        assert len(spy.calls) == 1
        cap.one("NVENC encoder not available, using software encoding (libx264)", logging.INFO)


def test_nvenc_ffmpeg_not_found():
    with _nv_state(), logcap() as cap, run_spy([FileNotFoundError("nope")]) as spy:
        assert ts.check_nvenc_available() is False
        assert ts._nvenc_available is False
        assert len(spy.calls) == 1
        cap.one("ffmpeg not found, cannot check NVENC availability", logging.WARNING)


def test_nvenc_timeout():
    exc = _real_subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10)
    with _nv_state(), logcap() as cap, run_spy([exc]):
        assert ts.check_nvenc_available() is False
        assert ts._nvenc_available is False
        cap.one("NVENC check timed out, assuming unavailable", logging.WARNING)


def test_nvenc_generic_exception_interpolates_the_error():
    with _nv_state(), logcap() as cap, run_spy([RuntimeError("kaboom-77")]):
        assert ts.check_nvenc_available() is False
        assert ts._nvenc_available is False
        cap.one("Error checking NVENC availability: kaboom-77", logging.WARNING)


# ============================================================================
# get_video_encoder_args  (survivors: 13 of 29)
# ============================================================================


def _hw_probe(witness: list[int], answer: bool):
    def _nv() -> bool:
        witness.append(1)
        return answer

    return _nv


def test_encoder_args_nvenc_path_is_the_ordered_full_list():
    seen: list[int] = []
    with (
        mock.patch.object(
            ts,
            "get_settings",
            _settings(hardware_acceleration_enabled=True, nvenc_preset="p7", nvenc_cq=19),
        ),
        mock.patch.object(ts, "check_nvenc_available", _hw_probe(seen, True)),
        logcap() as cap,
    ):
        assert ts.get_video_encoder_args(use_hardware=True) == [
            "-c:v",
            NV_CODEC,
            "-preset",
            "p7",
            "-cq",
            "19",
            "-pix_fmt",
            PIX,
        ]
        assert seen == [1]
        cap.one("Using NVENC hardware encoder for video transcoding", logging.DEBUG)


def test_encoder_args_software_path_is_the_ordered_full_list():
    seen: list[int] = []
    with (
        mock.patch.object(
            ts,
            "get_settings",
            _settings(hardware_acceleration_enabled=True, nvenc_preset="p7", nvenc_cq=19),
        ),
        mock.patch.object(ts, "check_nvenc_available", _hw_probe(seen, False)),
        logcap() as cap,
    ):
        assert ts.get_video_encoder_args(use_hardware=True) == [
            "-c:v",
            SW_CODEC,
            "-preset",
            PRESET_SW,
            "-crf",
            CRF,
            "-pix_fmt",
            PIX,
        ]
        assert seen == [1]
        cap.one("Using libx264 software encoder for video transcoding", logging.DEBUG)


def test_encoder_args_use_hardware_false_never_touches_nvenc():
    """Short-circuit ORDER: use_hardware=False must not even CALL the
    detector (an and->or twin evaluates it and returns NVENC in this world)."""
    seen: list[int] = []
    with (
        mock.patch.object(
            ts,
            "get_settings",
            _settings(hardware_acceleration_enabled=True, nvenc_preset="p7", nvenc_cq=19),
        ),
        mock.patch.object(ts, "check_nvenc_available", _hw_probe(seen, True)),
    ):
        assert ts.get_video_encoder_args(use_hardware=False) == [
            "-c:v",
            SW_CODEC,
            "-preset",
            PRESET_SW,
            "-crf",
            CRF,
            "-pix_fmt",
            PIX,
        ]
        assert seen == []


def test_encoder_args_setting_off_short_circuits_before_nvenc():
    seen: list[int] = []
    with (
        mock.patch.object(
            ts,
            "get_settings",
            _settings(hardware_acceleration_enabled=False, nvenc_preset="p7", nvenc_cq=19),
        ),
        mock.patch.object(ts, "check_nvenc_available", _hw_probe(seen, True)),
    ):
        out = ts.get_video_encoder_args(use_hardware=True)
        assert out == ["-c:v", SW_CODEC, "-preset", PRESET_SW, "-crf", CRF, "-pix_fmt", PIX]
        assert seen == []


def test_encoder_args_cq_is_the_str_of_the_setting():
    """The str() wrap and position are both pinned: nvenc_cq=5 must land as
    the STRING "5" at index 5 (a lost str() lands the INT and dies here)."""
    with (
        mock.patch.object(
            ts,
            "get_settings",
            _settings(hardware_acceleration_enabled=True, nvenc_preset="p1", nvenc_cq=5),
        ),
        mock.patch.object(ts, "check_nvenc_available", lambda: True),
    ):
        args = ts.get_video_encoder_args(use_hardware=True)
        assert args == ["-c:v", NV_CODEC, "-preset", "p1", "-cq", "5", "-pix_fmt", PIX]
        assert all(isinstance(a, str) for a in args)


# ============================================================================
# _validate_video_path / _compute_file_hash  (2+3 survivors)
# ============================================================================


def test_validate_missing_file_message_uses_the_original_string():
    with tmpdir() as d:
        missing = d / "gone.mp4"
        with pytest.raises(ValueError) as ei:
            ts._validate_video_path(str(missing))
        assert str(ei.value) == f"Video file not found: {missing}"


def test_validate_directory_message():
    with tmpdir() as d:
        with pytest.raises(ValueError) as ei:
            ts._validate_video_path(d)
        assert str(ei.value) == f"Path is not a file: {d}"


def test_validate_success_returns_resolved_path():
    with tmpdir() as d:
        f = d / "vid.avi"
        f.write_bytes(b"abc")
        rel = Path(os.path.relpath(f))
        assert ts._validate_video_path(rel) == f.resolve()


def test_compute_file_hash_pins_input_format_and_security_kwarg():
    """hash_input f"{path}:{mtime}:{size}" pinned component-wise off a REAL
    hashlib.md5 spy (an order-swap twin changes the components), and the
    usedforsecurity=False call-site kwarg captured RAW (drop = MISSING)."""
    captured: dict[str, Any] = {}
    real_md5 = hashlib.md5

    def _md5(data: bytes, **kw: Any):
        captured["data"] = data
        captured["kwargs"] = kw
        return real_md5(data, **kw)

    with tmpdir() as d:
        f = d / "vid.avi"
        f.write_bytes(b"hello world")
        st = f.stat()
        with mock.patch.object(ts.hashlib, "md5", _md5):
            out = ts._compute_file_hash(f)
        assert captured["kwargs"] == {"usedforsecurity": False}
        expected = f"{f}:{st.st_mtime}:{st.st_size}"
        assert captured["data"].decode() == expected
        assert out == real_md5(expected.encode(), usedforsecurity=False).hexdigest()


def test_compute_file_hash_changes_when_size_changes_at_same_mtime():
    """The st_size term is load-bearing: same path, mtime restored
    explicitly, different size -> different hash."""
    with tmpdir() as d:
        f = d / "vid.avi"
        f.write_bytes(b"a" * 10)
        st = f.stat()
        h1 = ts._compute_file_hash(f)
        f.write_bytes(b"b" * 20)
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))
        h2 = ts._compute_file_hash(f)
        st2 = f.stat()
        assert st2.st_mtime_ns == st.st_mtime_ns
        assert st2.st_size != st.st_size
        assert h1 != h2


# ============================================================================
# TranscodingService.__init__ / _ensure_cache_directory  (5+4 survivors)
# ============================================================================


def test_init_explicit_cache_directory_writes_every_observable():
    with tmpdir() as d, logcap() as cap:
        cache = d / "nested" / "deeper"
        svc = ts.TranscodingService(cache_directory=str(cache))
        assert svc.cache_directory == cache
        assert cache.is_dir()
        cap.one(f"TranscodingService initialized: cache_directory={cache}", logging.INFO)
        cap.one(f"Transcoding cache directory ready: {cache}", logging.DEBUG)


def test_init_empty_string_is_not_none_takes_the_explicit_branch():
    """`cache_directory if cache_directory is not None else settings…`: a
    truthiness twin takes the SETTINGS branch for "" - shipped lands Path("")."""
    with (
        mock.patch.object(
            ts, "get_settings", _settings(transcoding_cache_directory="from/settings")
        ),
        tmpdir(),
    ):
        svc = ts.TranscodingService(cache_directory="")
        assert svc.cache_directory == Path()
        assert svc.cache_directory != Path("from/settings")


def test_init_settings_default_used_when_argument_none():
    with (
        mock.patch.object(
            ts, "get_settings", _settings(transcoding_cache_directory="from/settings")
        ),
        tmpdir(),
    ):
        svc = ts.TranscodingService(cache_directory=None)
        assert svc.cache_directory == Path("from/settings")


def test_init_getattr_default_when_setting_absent():
    """getattr(settings, name, "data/transcoded_cache"): the deleted-default
    (2-arg) twin RAISES AttributeError here; the constant-swap twin lands the
    wrong path. Both die."""
    with mock.patch.object(ts, "get_settings", lambda: SimpleNamespace()), tmpdir():
        svc = ts.TranscodingService(cache_directory=None)
        assert svc.cache_directory == Path("data/transcoded_cache")


def test_ensure_cache_directory_error_logs_exact_message_and_reraises():
    """mkdir over a FILE parent raises NotADirectoryError. The expected log
    line is computed from the SAME deterministic error a probe mkdir raises,
    then pinned by FULL equality; the raise-drop twin dies on pytest.raises."""
    with tmpdir() as d:
        blocker = d / "blocker"
        blocker.write_bytes(b"x")
        cache = blocker / "sub"
        try:
            cache.mkdir(parents=True, exist_ok=True)
            expected = None
        except OSError as probe_exc:
            expected = f"Failed to create transcoding cache directory {cache}: {probe_exc}"
        assert expected is not None
        svc = object.__new__(ts.TranscodingService)
        svc._cache_directory = cache
        with logcap() as cap, pytest.raises(NotADirectoryError):
            svc._ensure_cache_directory()
        cap.one(expected, logging.ERROR)


# ============================================================================
# get_cached_video  (5 of 10)
# ============================================================================


def test_cached_video_hit_returns_path_and_logs_debug():
    with tmpdir() as d:
        video = d / "v.avi"
        video.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        cp = _cache_path_for(svc, video.resolve())
        # the cache KEY itself: full filename, not just the returned Path
        assert cp.name == f"{ts._compute_file_hash(video.resolve())}_transcoded.{CONTAINER}"
        assert cp.parent == (d / "cache")
        cp.write_bytes(b"y" * 1000)
        with logcap() as cap:
            assert svc.get_cached_video(video) == cp
            cap.one(f"Cache hit for video: {video} -> {cp}", logging.DEBUG)


def test_cached_video_size_boundary_exactly_1000_is_kept():
    """`file_size < 1000` is STRICT - exactly 1000 bytes is a VALID hit (the
    <= twin removes it)."""
    with tmpdir() as d:
        video = d / "v.avi"
        video.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        cp = _cache_path_for(svc, video.resolve())
        cp.write_bytes(b"y" * 1000)
        assert svc.get_cached_video(video) == cp
        assert cp.exists()


def test_cached_video_corrupted_999_is_removed_and_none():
    with tmpdir() as d:
        video = d / "v.avi"
        video.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        cp = _cache_path_for(svc, video.resolve())
        cp.write_bytes(b"y" * 999)
        with logcap() as cap:
            assert svc.get_cached_video(video) is None
            assert not cp.exists()
            cap.one(f"Removing corrupted cache file (999 bytes): {cp}", logging.WARNING)


def test_cached_video_miss_logs_miss():
    with tmpdir() as d:
        video = d / "v.avi"
        video.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        with logcap() as cap:
            assert svc.get_cached_video(video) is None
            cap.one(f"Cache miss for video: {video}", logging.DEBUG)


def test_cached_video_invalid_path_warns_and_returns_none():
    with tmpdir() as d, logcap() as cap:
        svc = _service(d / "cache")
        missing = d / "gone.avi"
        assert svc.get_cached_video(missing) is None
        cap.one(
            f"Cache lookup failed - path validation error: Video file not found: {missing}",
            logging.WARNING,
        )


# ============================================================================
# _remux_video  (36 of 50)
# ============================================================================


def _remux_setup(d: Path):
    video = d / "src.avi"
    video.write_bytes(b"x" * 1600)
    svc = _service(d / "cache")
    resolved = video.resolve()
    return svc, resolved, svc._get_cache_path(resolved)


def test_remux_success_argv_kwargs_and_logs():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)

        def make() -> None:
            cp.write_bytes(b"z" * 1001)

        with exec_world([_process(0)], actions=[make]) as w, logcap() as cap:
            out = _run(svc._remux_video(video, cp))
            assert out == cp
            expected_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(video),
                "-c:v",
                "copy",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(cp),
            ]
            assert list(w.exec.calls[0][0]) == expected_cmd
            assert w.exec.calls[0][1] == {"stdout": PIPE, "stderr": PIPE}
            assert w.wait.calls == [{"timeout": 30.0}]
            cap.one(f"Attempting fast remux: {video} -> {cp}", logging.INFO)
            cap.one("FFmpeg remux command: " + " ".join(expected_cmd), logging.DEBUG)
            cap.one(f"Fast remux successful: {cp} (1001 bytes)", logging.INFO)


def test_remux_size_boundary_exactly_1000_falls_back():
    """`file_size > 1000` is STRICT: exactly 1000 bytes must be unlinked +
    None + the suspicious-small WARNING (the >= twin returns the file)."""
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)

        def make() -> None:
            cp.write_bytes(b"z" * 1000)

        with exec_world([_process(0)], actions=[make]), logcap() as cap:
            assert _run(svc._remux_video(video, cp)) is None
            assert not cp.exists()
            cap.one(
                "Remux produced suspiciously small file (1000 bytes), falling back to transcode",
                logging.WARNING,
            )


def test_remux_rc_zero_but_no_output_file():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        with exec_world([_process(0)]), logcap() as cap:
            assert _run(svc._remux_video(video, cp)) is None
            cap.one("Remux failed (returncode=0), will try full transcode", logging.DEBUG)


def test_remux_nonzero_rc_removes_partial_file():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)

        def make_partial() -> None:
            cp.write_bytes(b"partial garbage")

        with exec_world([_process(42)], actions=[make_partial]), logcap() as cap:
            assert _run(svc._remux_video(video, cp)) is None
            assert not cp.exists()
            cap.one("Remux failed (returncode=42), will try full transcode", logging.DEBUG)


def test_remux_timeout_warns_and_cleans():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)

        def make() -> None:
            cp.write_bytes(b"z" * 2000)

        with exec_world([_process(0)], actions=[make], wait_exc=TimeoutError()), logcap() as cap:
            assert _run(svc._remux_video(video, cp)) is None
            assert not cp.exists()
            cap.one("Remux timed out, falling back to transcode", logging.WARNING)


def test_remux_generic_exception_debug_and_cleanup():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        with exec_world([RuntimeError("spawn-hosed")]), logcap() as cap:
            assert _run(svc._remux_video(video, cp)) is None
            assert not cp.exists()
            cap.one(
                "Remux failed with exception: spawn-hosed, will try full transcode",
                logging.DEBUG,
            )


# ============================================================================
# transcode_video  (36 of 62)
# ============================================================================


def test_transcode_cache_hit_short_circuits_everything():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        cp.write_bytes(b"c" * 2000)
        with exec_world([_process(0)]) as w, logcap() as cap:
            assert _run(svc.transcode_video(video)) == cp
            assert w.exec.calls == []
            cap.one(f"Using cached transcoded video: {cp}", logging.INFO)


def test_transcode_force_true_bypasses_cache():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        cp.write_bytes(b"old" * 1000)

        def make() -> None:
            cp.write_bytes(b"n" * 1500)

        with exec_world([_process(0)], actions=[make]) as w, logcap() as cap:
            out = _run(svc.transcode_video(video, force=True))
            assert out == cp
            assert cp.read_bytes() == b"n" * 1500
            assert len(w.exec.calls) == 1
            cap.none_containing("Using cached transcoded video")


def test_transcode_remux_result_forwards_without_encoder_call():
    """The remux-success early return: get_video_encoder_args is NEVER called
    (its absence is the observable - a drop-the-early-return twin calls it)."""
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)

        def make() -> None:
            cp.write_bytes(b"n" * 1500)

        encoder_calls: list[dict] = []

        def _enc(**kw: Any) -> list[str]:
            encoder_calls.append(kw)
            return ["-c:v", SW_CODEC]

        with (
            exec_world([_process(0)], actions=[make]),
            mock.patch.object(ts, "get_video_encoder_args", _enc),
        ):
            assert _run(svc.transcode_video(video)) == cp
            assert encoder_calls == []


def _sw_encoder(**kw: Any) -> list[str]:
    assert kw == {"use_hardware": True}
    return ["-c:v", SW_CODEC]


def test_transcode_full_path_pins_complete_cmd_and_encoder_kwargs():
    """remux (exec call 0) fails rc=7; full transcode (call 1) must carry the
    COMPLETE argv: raw-kwargs capture proves use_hardware=True is PRESENT
    (arg_drop = missing key = empty dict fails the assert inside _enc)."""
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        made: list[int] = []

        def make() -> None:
            made.append(1)
            cp.write_bytes(b"t" * 4321)

        raw_kwargs: list[dict] = []

        def _enc(**kw: Any) -> list[str]:
            raw_kwargs.append(dict(kw))
            return ["-c:v", NV_CODEC, "-preset", "p9", "-cq", "11", "-pix_fmt", PIX]

        with (
            mock.patch.object(ts, "get_video_encoder_args", _enc),
            logcap() as cap,
        ):
            with exec_world([_process(7), _process(0)], actions=[None, make]) as w:
                out = _run(svc.transcode_video(video))
                assert out == cp
                assert raw_kwargs == [{"use_hardware": True}]
                assert made == [1]
                expected_cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(video),
                    "-c:v",
                    NV_CODEC,
                    "-preset",
                    "p9",
                    "-cq",
                    "11",
                    "-pix_fmt",
                    PIX,
                    "-c:a",
                    AAC,
                    "-movflags",
                    "+faststart",
                    str(cp),
                ]
                assert list(w.exec.calls[1][0]) == expected_cmd
                assert w.exec.calls[1][1] == {"stdout": PIPE, "stderr": PIPE}
                cap.one(f"Full transcoding video: {video} -> {cp}", logging.INFO)
                cap.one("FFmpeg command: " + " ".join(expected_cmd), logging.DEBUG)
                cap.one(f"Transcoding complete: {cp} (4321 bytes)", logging.INFO)


def test_transcode_ffmpeg_error_rc_and_stderr():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        with (
            exec_world([_process(7), _process(1, (b"", b"encoder exploded"))]),
            mock.patch.object(ts, "get_video_encoder_args", _sw_encoder),
            logcap() as cap,
        ):
            with pytest.raises(ts.TranscodingError) as ei:
                _run(svc.transcode_video(video))
            assert str(ei.value) == "FFmpeg exited with code 1: encoder exploded"
            cap.one("FFmpeg transcoding failed: encoder exploded", logging.ERROR)


def test_transcode_ffmpeg_error_empty_stderr_says_unknown():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        with (
            exec_world([_process(7), _process(2, (b"", b""))]),
            mock.patch.object(ts, "get_video_encoder_args", _sw_encoder),
        ):
            with pytest.raises(ts.TranscodingError) as ei:
                _run(svc.transcode_video(video))
            assert str(ei.value) == "FFmpeg exited with code 2: Unknown error"


def test_transcode_zero_rc_but_missing_output():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        with (
            exec_world([_process(7), _process(0)]),
            mock.patch.object(ts, "get_video_encoder_args", _sw_encoder),
        ):
            with pytest.raises(ts.TranscodingError) as ei:
                _run(svc.transcode_video(video))
            assert str(ei.value) == f"Transcoded file was not created: {cp}"


def test_transcode_file_not_found_maps_with_no_cause():
    """remux swallows the FileNotFoundError; the full-transcode spawn raises
    it -> mapped to "ffmpeg not found" with __cause__ IS None (the
    drop-`from None` twin chains the original)."""
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        with (
            exec_world([_process(7), FileNotFoundError("ffmpeg gone")]),
            mock.patch.object(ts, "get_video_encoder_args", _sw_encoder),
            logcap() as cap,
        ):
            with pytest.raises(ts.TranscodingError) as ei:
                _run(svc.transcode_video(video))
            assert str(ei.value) == "ffmpeg not found"
            assert ei.value.__cause__ is None
            cap.one("ffmpeg not found. Please ensure ffmpeg is installed.", logging.ERROR)


def test_transcode_generic_error_wraps_with_cause():
    with tmpdir() as d:
        svc, video, cp = _remux_setup(d)
        boom = RuntimeError("disk on fire")
        with (
            exec_world([_process(7), boom]),
            mock.patch.object(ts, "get_video_encoder_args", _sw_encoder),
            logcap() as cap,
        ):
            with pytest.raises(ts.TranscodingError) as ei:
                _run(svc.transcode_video(video))
            assert str(ei.value) == "Transcoding failed: disk on fire"
            assert ei.value.__cause__ is boom
            rec = cap.one("Transcoding failed: disk on fire", logging.ERROR)
            assert rec.exc_info, "ERROR must carry exc_info=True"


def test_transcode_validation_error_propagates():
    with tmpdir() as d:
        svc = _service(d / "cache")
        missing = d / "nope.avi"
        with pytest.raises(ValueError) as ei:
            _run(svc.transcode_video(missing))
        assert str(ei.value) == f"Video file not found: {missing}"


# ============================================================================
# get_or_transcode  (2 of 7)
# ============================================================================


def test_get_or_transcode_mp4_returns_validated_original_never_touches_cache():
    with tmpdir() as d:
        mp4 = d / "ok.mp4"
        mp4.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        cache_calls: list[Any] = []
        with (
            mock.patch.object(svc, "get_cached_video", lambda *a: cache_calls.append(a) or None),
            logcap() as cap,
        ):
            out = _run(svc.get_or_transcode(mp4))
            assert out == mp4.resolve()
            assert cache_calls == []
            cap.one(f"Video is already browser-compatible: {mp4}", logging.DEBUG)


def test_get_or_transcode_cache_hit_forwards_cached():
    with tmpdir() as d:
        avi = d / "v.avi"
        avi.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        cp = _cache_path_for(svc, avi.resolve())
        cp.write_bytes(b"c" * 1500)
        out = _run(svc.get_or_transcode(avi))
        assert out == cp


def test_get_or_transcode_miss_calls_transcode_once_with_validated():
    """The forwarding contract: transcode_video awaited with EXACTLY the
    resolved path and no force kwarg."""
    with tmpdir() as d:
        avi = d / "v.avi"
        avi.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        seen: list[tuple] = []

        async def fake_transcode(path: Any, force: bool = False) -> Path:
            seen.append((path, force))
            return Path("TRANSCODED")

        with (
            mock.patch.object(svc, "get_cached_video", lambda *_a: None),
            mock.patch.object(svc, "transcode_video", fake_transcode),
        ):
            out = _run(svc.get_or_transcode(avi))
            assert out == Path("TRANSCODED")
            assert seen == [(avi.resolve(), False)]


# ============================================================================
# is_transcoding_needed (suffix-table branch witnesses)
# ============================================================================


def test_is_transcoding_needed_suffix_table_rows():
    with tmpdir() as d:
        svc = _service(d / "cache")
        mp4 = d / "a.mp4"
        mp4.write_bytes(b"x" * 1600)
        avi = d / "b.avi"
        avi.write_bytes(b"x" * 1600)
        upper = d / "C.MP4"
        upper.write_bytes(b"x" * 1600)
        assert svc.is_transcoding_needed(mp4) is False
        assert svc.is_transcoding_needed(avi) is True
        assert svc.is_transcoding_needed(upper) is False
        assert svc.is_transcoding_needed(d / "missing.mp4") is True


# ============================================================================
# cleanup_cache  (13 of 22)
# ============================================================================


def test_cleanup_deletes_only_old_matching_and_logs_summary():
    """old deleted; recent kept; wrong suffix kept; wrong name kept; the
    summary INFO text pinned exactly; per-file DEBUG lines pinned too.
    The clock is FROZEN (cleanup_cache does `import time; now = time.time()`
    per call - patching the time module's attribute lands): the EXACT-
    boundary file at age == 7*86400 is kept by shipped `>` but deleted by a
    `>=` twin - red-check age-guard killed.
    """
    with tmpdir() as d:
        svc = _service(d)
        now = 1_800_000_000.0  # exact in float64; 7*86400 subtracts exactly

        def touch(name: str, age: float) -> Path:
            f = d / name
            f.write_bytes(b"x" * 10)
            os.utime(f, (now - age, now - age))
            return f

        old = touch("aaa_transcoded.mp4", 8 * 86400)
        recent = touch("ccc_transcoded.mp4", 1)
        near_old = touch("ddd_transcoded.mp4", 7 * 86400 + 90)
        boundary = touch("bbb_transcoded.mp4", 7 * 86400)
        wrong_ext = touch("eee_transcoded.avi", 8 * 86400)
        wrong_name = touch("fff_transcodedXmp4", 8 * 86400)
        other = touch("ggg.mp4", 8 * 86400)
        with mock.patch.object(time, "time", lambda: now), logcap() as cap:
            assert svc.cleanup_cache(max_age_days=7) == 2
            assert not old.exists()
            assert not near_old.exists()
            assert boundary.exists()
            assert recent.exists()
            assert wrong_ext.exists()
            assert wrong_name.exists()
            assert other.exists()
            cap.one("Cache cleanup: deleted 2 files older than 7 days", logging.INFO)
            cap.one(f"Deleted old cache file: {old}", logging.DEBUG)
            cap.one(f"Deleted old cache file: {near_old}", logging.DEBUG)
            cap.none_containing(f"Deleted old cache file: {recent}")


def test_cleanup_default_age_is_seven_days():
    with tmpdir() as d:
        svc = _service(d)
        now = time.time()
        f = d / "zzz_transcoded.mp4"
        f.write_bytes(b"x")
        os.utime(f, (now - 8 * 86400, now - 8 * 86400))
        assert svc.cleanup_cache() == 1
        assert not f.exists()


def test_cleanup_zero_deletes_logs_no_summary():
    with tmpdir() as d:
        svc = _service(d)
        (d / "fresh_transcoded.mp4").write_bytes(b"x")
        with logcap() as cap:
            assert svc.cleanup_cache(max_age_days=7) == 0
            cap.none_containing("Cache cleanup: deleted")


def test_cleanup_oserror_on_one_file_is_isolated():
    """A broken symlink matches the glob but stat() raises OSError: the
    per-file handler logs the exact WARNING (message computed from the probe
    stat's own deterministic error) and the healthy old file still deletes."""
    with tmpdir() as d:
        svc = _service(d)
        now = time.time()
        good = d / "good_transcoded.mp4"
        good.write_bytes(b"x")
        os.utime(good, (now - 9 * 86400, now - 9 * 86400))
        broken = d / "broken_transcoded.mp4"
        broken.symlink_to(d / "not-there")
        try:
            broken.stat()
            expected = None
        except OSError as probe_exc:
            expected = f"Failed to delete cache file {broken}: {probe_exc}"
        assert expected is not None
        with logcap() as cap:
            assert svc.cleanup_cache(max_age_days=7) == 1
            assert not good.exists()
            cap.one(expected, logging.WARNING)


def test_cleanup_outer_failure_logs_error_and_returns_count():
    """Path.glob raising lands in the OUTER except Exception: ERROR line +
    NO re-raise, count 0 (a drop-the-catch twin propagates and dies here)."""

    def _boom(self: Any, *_a: Any, **_k: Any):
        raise PermissionError("nope-9")

    with tmpdir() as d:
        svc = _service(d)
        with mock.patch.object(Path, "glob", _boom), logcap() as cap:
            assert svc.cleanup_cache() == 0
            cap.one("Cache cleanup failed: nope-9", logging.ERROR)


# ============================================================================
# delete_cached  (2 of 9)
# ============================================================================


def test_delete_cached_success_removes_file_and_logs():
    with tmpdir() as d:
        video = d / "v.avi"
        video.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        cp = _cache_path_for(svc, video.resolve())
        cp.write_bytes(b"c" * 1500)
        with logcap() as cap:
            assert svc.delete_cached(video) is True
            assert not cp.exists()
            cap.one(f"Deleted cached transcoded file: {cp}", logging.DEBUG)


def test_delete_cached_not_found_logs_nothing_to_delete():
    with tmpdir() as d:
        video = d / "v.avi"
        video.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        with logcap() as cap:
            assert svc.delete_cached(video) is False
            cap.one(f"No cached file to delete for: {video}", logging.DEBUG)


def test_delete_cached_invalid_path_is_false():
    with tmpdir() as d:
        svc = _service(d / "cache")
        assert svc.delete_cached(d / "gone.avi") is False


def test_delete_cached_oserror_warns_false():
    """cache path exists as a DIRECTORY: exists() True, unlink() raises
    IsADirectoryError (an OSError) - exact WARNING (message from the probe
    unlink's own error) + False."""
    with tmpdir() as d:
        video = d / "v.avi"
        video.write_bytes(b"x" * 1600)
        svc = _service(d / "cache")
        cp = _cache_path_for(svc, video.resolve())
        cp.mkdir()
        try:
            cp.unlink()
            expected = None
        except OSError as probe_exc:
            expected = f"Failed to delete cached file: {probe_exc}"
        assert expected is not None
        assert cp.is_dir()
        with logcap() as cap:
            assert svc.delete_cached(video) is False
            cap.one(expected, logging.WARNING)


# ============================================================================
# singleton (module-level)
# ============================================================================


def test_get_transcoding_service_caches_and_reset_clears():
    with tmpdir() as d, _nv_state():
        with mock.patch.object(
            ts, "get_settings", _settings(transcoding_cache_directory=str(d / "c1"))
        ):
            s1 = ts.get_transcoding_service()
            s2 = ts.get_transcoding_service()
            assert s1 is s2
            assert ts._transcoding_service is s1
        ts.reset_transcoding_service()
        assert ts._transcoding_service is None
        with mock.patch.object(
            ts, "get_settings", _settings(transcoding_cache_directory=str(d / "c2"))
        ):
            s3 = ts.get_transcoding_service()
            assert s3 is not s1
            assert s3.cache_directory == Path(str(d / "c2"))
