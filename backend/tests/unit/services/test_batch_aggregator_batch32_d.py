# TARGET-MODULE: backend.services.batch_aggregator
"""Batch-32 kill battery D: BatchAggregator.check_batch_timeouts (66 keys).

``check_batch_timeouts`` had 66 of its keys green. They were classified off the
normalized def-diffs (script /home/agent/runs/b32-key-diff.py; deduplicated
shapes in /home/agent/runs/b32-compact-timeouts.txt). The census below is the
classifier's OUTPUT over those diffs (it sums to 66), not an estimate: 30 LOG
CALLS across the three log sites, 5 bytes-decode polarity pairs, 4 call-argument
swaps (``get(None)``, ``batch_keys.append(None)``), 4 metadata index-math
mutations, 4 ``close_reason`` mutations, 3 ``zip(strict=True)``, 3
``json.loads`` polarity, 2 ``RuntimeError`` messages, 2 ``float(...)`` polarity,
2 arithmetic swaps (``-`` -> ``+``), 2 ``should_close`` initializers, 2 boundary
polarity flips (``>=`` -> ``>``), 2 ``camera_id_for_log`` fetches and the
``continue`` -> ``break`` swap.

Why a plain happy-path test cannot kill most of them, and what this battery does
instead:

* BOUNDARIES. ``window_elapsed >= self._batch_window`` -> ``>`` is invisible
  unless a batch sits EXACTLY on the threshold, so there is a test at
  ``elapsed == window`` (must close) and one at ``elapsed == window - 0.05``
  (must not). Same for the idle timeout. Thresholds are read from the instance
  (``agg._batch_window`` / ``agg._idle_timeout``), never hardcoded, so the
  battery tracks settings instead of freezing them.
* INDEX MATH. ``metadata_results[i * 2]`` / ``[i * 2 + 1]`` -> ``i * 3`` /
  ``i * 2 - 1`` / ``i * 3 + 1`` need AT LEAST TWO batches whose four metadata
  values are all different, so a wrong slot reads a different number. The
  two-batch test therefore mixes a window-close and an idle-close batch; the
  mutants either change the decision, change the ``reason`` string, or walk off
  the end into the per-batch ``except`` arm.
* ``zip(strict=True)`` -> ``strict=False``/dropped/``strict=None`` only shows up
  as a LENGTH MISMATCH, which is exactly what the strict argument exists for:
  one test hands back fewer ids than keys and asserts the shipped
  ``ValueError`` message, which the lenient mutants replace with a silent
  short zip.
* ``continue`` -> ``break`` in the missing-``started_at`` arm needs a second
  batch AFTER the bad one — every such test carries a good batch second.
* the bytes-decode polarity pairs (``.decode() if isinstance(..., bytes) and
  False else ...``) need BYTES from the fake, because that is the branch they
  disable. Scan keys and several metadata values arrive as bytes here (what
  redis-py returns), and ``batch_key`` is observable through the per-batch
  ``except`` arm's ``extra={'batch_key': ...}``, so that arm is exercised too.
* the clock is a stand-in for the ``time`` MODULE inside
  ``batch_aggregator``'s globals (module dict beats builtins; the shared stdlib
  module is never patched, and the shim is restored with a leak assert), which
  makes every elapsed/idle number exact.
* ``close_batch`` is spied on a SUBCLASS, so a close is observed as an exact
  call and a raising close drives the ``except`` arm without breaking the loop.
* the ``close_reason = None`` mutants (``_99``/``_103``, one per close branch)
  die for free: ``reason=None`` would reach the log as the string ``"None"`` via
  f-string interpolation, but every closing test asserts the EXACT reason string
  (``"batch window exceeded (12.0s >= 12.0s)"`` / the idle form), which a ``None``
  cannot reproduce.

Honesty ledger (measured by the FINAL sweep of this file: RED=62 GREEN=4 of 66,
shipped-green control OK — 20 tests pass unmutated). The four greens are all
EQUIVALENT, each proven two ways (fingerprint probe
/home/agent/runs/b32-probe-d.py — shipped-vs-mutant fingerprints across a
14-scenario grid covering both thresholds and both sides, missing/empty/BOM'd
values, bytes, two batches and a raising close — AND the construction argument):

``__mutmut_92`` (``should_close = False`` -> ``= True``): the init is a dead
store. The window branch sets it True, the elif leaves it, and the only reader is
``if should_close:``, reached only after the branch assignment — the init feeds
nothing. (falsy↔truthy on a value the init writes but no path reads; the batch-30
dead-store family.)
``__mutmut_94`` (``close_reason = ""`` -> ``= None``) / ``__mutmut_95``
(``= 'XXXX'``): ``close_reason`` is read exactly once, inside ``if should_close:``,
and by then the window/elif branch has overwritten the init (there is no path
into that ``if`` with the init still standing), so the initializer's value —
empty, None, or 'XXXX' — never surfaces.
``__mutmut_80`` (``json.loads(x) if x or True else None``): forces the parse
always. When ``last_activity_str`` is falsy the shipped code passes ``None``; the
mutant calls ``json.loads(None)`` → TypeError, and the shipped
``except (json.JSONDecodeError, TypeError): pass`` catches it and leaves the
variable unchanged. Same for ``""`` → JSONDecodeError → caught. So falsy-input
behavior is identical; truthy input was already parsed by both.

The other 62 go red, and the three that needed the extra scenarios were
``_71``/``_74`` (bytes-decode polarity, killed only by a UTF-8 BOM — ``.decode()``
keeps the BOM so ``json.loads`` then fails, whereas the mutant's
``json.loads(bytes)`` STRIPS the BOM and parses, so the shipped code lands in the
``except`` arm where the mutant closes the batch) and ``_86``
(``float(x) if x or True else started_at`` — killed by a batch that has
started_at but NO last_activity, where the shipped fallback to started_at differs
observably from the mutant's ``float(None)`` TypeError). Those three were green on
the first 16-test pass and turned red only after the BOM and fresh-batch
scenarios were added.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Mirror the repo conftest env (the trampoline sweep imports this file
# directly; setdefault makes this a no-op under repo pytest). See battery A.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "batch_aggregator.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.services import batch_aggregator as ba  # noqa: E402
from backend.services.batch_aggregator import BatchAggregator  # noqa: E402

CAM = "cam-north"
B1 = "batch-aaaa1111"
B2 = "batch-bbbb2222"
KEY1 = f"batch:{CAM}:current"
KEY2 = "batch:cam-south:current"
T0 = 1_700_000_100.0
BOOM = RuntimeError("spy close boom")
_MISS = object()


# --- event loop -------------------------------------------------------------
def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- log capture (same discipline as battery C) -------------------------------
class _ListHandler(logging.Handler):
    def __init__(self, sink: list[logging.LogRecord]) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.append(record)


class LogCapture:
    """Installs the shipped ContextFilter so ambient context keys are real."""

    def __enter__(self) -> LogCapture:
        self.records: list[logging.LogRecord] = []
        self._handler = _ListHandler(self.records)
        found = [f for f in ba.logger.filters if type(f).__name__ == "ContextFilter"]
        assert len(found) == 1, f"ba.logger must carry exactly one ContextFilter, got {found}"
        self._handler.addFilter(found[0])
        ba.logger.addHandler(self._handler)
        self._old_level = ba.logger.level
        ba.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        ba.logger.removeHandler(self._handler)
        ba.logger.setLevel(self._old_level)

    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def at(self, level: int, message: str) -> list[logging.LogRecord]:
        return [r for r in self.records if r.levelno == level and r.getMessage() == message]

    def one(self, level: int, message: str) -> logging.LogRecord:
        hits = self.at(level, message)
        assert len(hits) == 1, f"want exactly one {message!r} at {level}, got {self.texts()}"
        return hits[0]

    def count(self, level: int, message: str) -> int:
        return len(self.at(level, message))

    def none_at_all(self) -> None:
        assert self.records == [], f"expected no log records, got {self.texts()}"


def _shown(rec: logging.LogRecord) -> str:
    return f"msg={rec.getMessage()!r} attrs={sorted(vars(rec))}"


def _attrs(rec: logging.LogRecord, want: dict[str, Any], absent: tuple[str, ...] = ()) -> None:
    """Exact value per ``extra`` key + explicit ABSENCE of mutant spellings."""
    for key, value in want.items():
        got = getattr(rec, key, _MISS)
        assert got == value, f"extra {key!r} = {got!r}, want {value!r}; {_shown(rec)}"
    for key in absent:
        assert not hasattr(rec, key), f"unexpected extra attr {key!r} on {_shown(rec)}"


# --- the pinned clock ---------------------------------------------------------
class _TimeShim:
    def __init__(self, t0: float = T0) -> None:
        self.calls: list[float] = []
        self._t = t0

    def time(self) -> float:
        self.calls.append(self._t)
        value = self._t
        self._t += 0.5
        return value


@contextlib.contextmanager
def _clock(shim: _TimeShim) -> Any:
    saved = ba.__dict__.get("time", _MISS)
    ba.__dict__["time"] = shim
    try:
        yield shim
    finally:
        if saved is _MISS:
            ba.__dict__.pop("time", None)
        else:
            ba.__dict__["time"] = saved
        assert "time" not in ba.__dict__ or ba.__dict__["time"] is saved, "clock shim leaked"


# --- redis fake ---------------------------------------------------------------
class FakePipe:
    """A redis-py pipeline: ``execute()`` returns ONE reply per queued command,
    in order — so the scripted replies are one flat queue shared by both pipes
    and each pipe consumes exactly the number of commands it was handed. That
    fidelity is what makes the ``zip(strict=True)`` and index-math mutants die
    instead of tripping over a fake that over- or under-delivers.
    """

    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.keys: list[Any] = []
        self.executes = 0

    def get(self, key: Any) -> None:
        self.keys.append(key)

    async def execute(self) -> list[Any]:
        self.executes += 1
        assert self.executes == 1, "the shipped code executes each pipeline exactly once"
        # ``client.short_by`` is a fake-only knob: real redis-py always replies
        # 1:1, so the zip(strict=True) defensive arm can only be reached by a
        # fake that deliberately answers one command short.
        want = len(self.keys) - self.client.short_by
        assert 0 <= want <= len(self.client.queue), (
            f"pipe asked for {want} replies, {len(self.client.queue)} scripted"
        )
        return [self.client.queue.pop(0) for _ in range(want)]


class FakeClient:
    """Records scan_iter args and every pipeline it hands out."""

    def __init__(self, keys: list[Any], results: list[Any], *, short_by: int = 0) -> None:
        self.keys = keys
        self.queue: list[Any] = list(results)
        self.short_by = short_by
        self.scans: list[tuple[Any, ...]] = []
        self.pipes: list[FakePipe] = []
        self.pipe_calls = 0

    def scan_iter(self, *, match: Any = None, count: Any = None) -> Any:
        self.scans.append((match, count))

        async def _gen() -> Any:
            for k in self.keys:
                yield k

        return _gen()

    def pipeline(self) -> FakePipe:
        self.pipe_calls += 1
        pipe = FakePipe(self)
        self.pipes.append(pipe)
        return pipe


class FakeRedis:
    def __init__(
        self,
        *,
        keys: list[Any],
        results: list[Any],
        values: dict[str, Any] | None = None,
        short_by: int = 0,
    ) -> None:
        self._client = FakeClient(keys, results, short_by=short_by)
        self.values = dict(values or {})
        self.gets: list[Any] = []

    async def get(self, key: Any) -> Any:
        self.gets.append(key)
        return self.values.get(key)


# --- spy aggregator -----------------------------------------------------------
class TimeoutAgg(BatchAggregator):
    """Spies close_batch so a close is an exact observed call.

    ``boom`` is the batch_id whose close raises, which drives the per-batch
    ``except`` arm — that arm is where ``batch_key`` becomes observable.
    """

    def __init__(self, redis: Any, *, boom: str | None = None) -> None:
        super().__init__(redis_client=redis)  # type: ignore[arg-type]
        self.close_calls: list[str] = []
        self.boom = boom

    async def close_batch(self, batch_id: str) -> dict[str, Any]:
        self.close_calls.append(batch_id)
        if batch_id == self.boom:
            raise BOOM
        return {"batch_id": batch_id}


def _agg(
    keys: list[Any],
    results: list[Any],
    *,
    values: dict[str, Any] | None = None,
    boom: str | None = None,
    short_by: int = 0,
) -> tuple[TimeoutAgg, FakeRedis, FakeClient]:
    fake = FakeRedis(keys=keys, results=results, values=values, short_by=short_by)
    return TimeoutAgg(fake, boom=boom), fake, fake._client


def _scan(n: int = 2, *, as_bytes: bool = False) -> list[Any]:
    src = [KEY1, KEY2][:n]
    return [k.encode() for k in src] if as_bytes else list(src)


def _j(value: Any, *, as_bytes: bool = False) -> Any:
    """What RedisClient.set() actually stores: a JSON string, optionally bytes."""
    text = json.dumps(value)
    return text.encode() if as_bytes else text


def _timeouts(agg: TimeoutAgg) -> Any:
    return _run(agg.check_batch_timeouts())


def _raises(want: type[BaseException], call: Any) -> BaseException:
    """Captures ONLY the declared exception type.

    Deliberately not a blanket ``except``: the fakes assert on their own usage,
    and a swallowed AssertionError here would turn a broken harness into a
    passing test.
    """
    try:
        call()
    except want as exc:
        return exc
    raise AssertionError(f"expected {want.__name__}")


def _closing(cap: LogCapture, batch_id: str, camera_id: Any, reason: str) -> logging.LogRecord:
    """The one INFO 'Closing batch' record for THIS batch.

    Selected by ``batch_id``, not by count: a batch whose close then raises
    still logs "Closing batch" first, so a failure test legitimately has two of
    these records. The shipped attrs are still asserted exactly.
    """
    hits = [
        r for r in cap.records if r.levelno == logging.INFO and r.getMessage() == "Closing batch"
    ]
    matched = [r for r in hits if getattr(r, "batch_id", _MISS) == batch_id]
    assert len(matched) == 1, f"want one 'Closing batch' for {batch_id!r}, got {cap.texts()}"
    rec = matched[0]
    _attrs(
        rec,
        {"camera_id": camera_id, "batch_id": batch_id, "reason": reason},
        (
            "XXcamera_idXX",
            "CAMERA_ID",
            "XXbatch_idXX",
            "BATCH_ID",
            "XXreasonXX",
            "REASON",
        ),
    )
    return rec


# --- guards -------------------------------------------------------------------
def test_timeouts_without_redis_raises_exact_message() -> None:
    agg, _, _ = _agg([], [])
    agg._redis = None
    with LogCapture() as cap:
        err = _raises(RuntimeError, lambda: _timeouts(agg))
    assert isinstance(err, RuntimeError), err
    assert str(err) == "Redis client not initialized", str(err)
    cap.none_at_all()


def test_timeouts_without_connection_raises_the_second_exact_message() -> None:
    agg, _, _ = _agg([], [])
    assert agg._redis is not None
    agg._redis._client = None
    with LogCapture() as cap:
        err = _raises(RuntimeError, lambda: _timeouts(agg))
    assert isinstance(err, RuntimeError), err
    assert str(err) == "Redis client connection not initialized", str(err)
    cap.none_at_all()


# --- scan phase ---------------------------------------------------------------
def test_no_batch_keys_returns_empty_without_any_pipeline_or_log() -> None:
    shim = _TimeShim()
    agg, _, client = _agg([], [])
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == []
    assert client.scans == [("batch:*:current", 100)], client.scans
    assert client.pipe_calls == 0, "nothing to fetch -> no pipeline"
    assert agg.close_calls == []
    assert shim.calls == [T0], f"exactly one clock read: {shim.calls}"
    cap.none_at_all()


def test_all_current_keys_empty_returns_empty_and_builds_only_the_id_pipe() -> None:
    shim = _TimeShim()
    agg, _, client = _agg(_scan(2), [None, None])
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == []
    assert len(client.pipes) == 1, "the metadata pipeline must not be built"
    assert client.pipes[0].keys == [KEY1, KEY2], client.pipes[0].keys
    cap.none_at_all()
    assert agg.close_calls == []


def test_id_shorter_than_keys_raises_because_zip_is_strict() -> None:
    shim = _TimeShim()
    agg, _, client = _agg(_scan(2), [_j(B1), _j(B2)], short_by=1)
    with _clock(shim), LogCapture() as cap:
        err = _raises(ValueError, lambda: _timeouts(agg))
    assert isinstance(err, ValueError), err
    assert str(err) == "zip() argument 2 is shorter than argument 1", str(err)
    assert len(client.pipes) == 1, "must fail before building the metadata pipeline"
    assert agg.close_calls == []
    cap.none_at_all()


# --- missing started_at -------------------------------------------------------
def test_missing_started_at_warns_with_the_sanitized_id_and_keeps_going() -> None:
    shim = _TimeShim()
    win = 12.0
    # slots: [id1, id2, started1, activity1, started2, activity2] — batch 1's
    # started_at is MISSING, so the shipped code warns and CONTINUES to batch 2.
    agg, fake, _ = _agg(
        _scan(2, as_bytes=True),
        [_j(B1, as_bytes=True), _j(B2), None, None, f"{T0 - win}", f"{T0}"],
        values={f"batch:{B2}:camera_id": CAM},
    )
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        out = _timeouts(agg)
    assert out == [B2], f"the bad batch must be skipped, not abort the loop: {out}"
    assert agg.close_calls == [B2], agg.close_calls
    rec = cap.one(logging.WARNING, "Batch missing started_at timestamp, skipping")
    _attrs(
        rec,
        {"batch_id": B1},
        (
            "XXbatch_idXX",
            "BATCH_ID",
            "XXBatch missing started_at timestamp, skippingXX",
            "BATCH MISSING STARTED_AT TIMESTAMP, SKIPPING",
            "batch missing started_at timestamp, skipping",
        ),
    )
    _closing(cap, B2, CAM, f"batch window exceeded ({win:.1f}s >= {win:.1f}s)")
    assert fake.gets == [f"batch:{B2}:camera_id"], fake.gets
    assert cap.count(logging.INFO, "Closed timed-out batches") == 1
    _attrs(
        cap.one(logging.INFO, "Closed timed-out batches"),
        {"batch_count": 1},
        ("XXbatch_countXX", "BATCH_COUNT"),
    )


# --- window boundary ----------------------------------------------------------
def test_window_elapsed_exactly_equal_closes_with_the_exact_reason() -> None:
    shim = _TimeShim()
    win = 11.0
    agg, fake, _ = _agg(
        _scan(1),
        [_j(B1), f"{T0 - win}", f"{T0}"],
        values={f"batch:{B1}:camera_id": CAM},
    )
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        out = _timeouts(agg)
    assert out == [B1] and agg.close_calls == [B1], (out, agg.close_calls)
    _closing(cap, B1, CAM, f"batch window exceeded ({win:.1f}s >= {win:.1f}s)")
    assert cap.count(logging.WARNING, "Batch missing started_at timestamp, skipping") == 0


def test_window_elapsed_just_below_the_threshold_closes_nothing() -> None:
    shim = _TimeShim()
    win = 11.0
    agg, _, _ = _agg(_scan(1), [_j(B1), f"{T0 - win + 0.05}", f"{T0}"])
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == []
    assert agg.close_calls == []
    assert cap.count(logging.INFO, "Closed timed-out batches") == 0, "nothing closed -> no summary"
    cap.none_at_all()


# --- idle boundary ------------------------------------------------------------
def test_idle_elapsed_exactly_equal_closes_with_the_idle_reason() -> None:
    shim = _TimeShim()
    win, idle = 20.0, 7.0
    agg, fake, _ = _agg(
        _scan(1),
        [_j(B1), f"{T0 - (win - 1)}", f"{T0 - idle}"],
        values={f"batch:{B1}:camera_id": CAM},
    )
    agg._batch_window = win
    agg._idle_timeout = idle
    with _clock(shim), LogCapture() as cap:
        out = _timeouts(agg)
    assert out == [B1] and agg.close_calls == [B1], (out, agg.close_calls)
    _closing(cap, B1, CAM, f"idle timeout exceeded ({idle:.1f}s >= {idle:.1f}s)")
    assert fake.gets == [f"batch:{B1}:camera_id"], fake.gets


def test_idle_elapsed_just_below_the_threshold_closes_nothing() -> None:
    shim = _TimeShim()
    win, idle = 20.0, 7.0
    agg, _, _ = _agg(_scan(1), [_j(B1), f"{T0 - (win - 1)}", f"{T0 - idle + 0.05}"])
    agg._batch_window = win
    agg._idle_timeout = idle
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == []
    assert agg.close_calls == []
    cap.none_at_all()


# --- two batches: metadata index math ------------------------------------------
def test_two_batches_read_exactly_two_slots_per_batch() -> None:
    shim = _TimeShim()
    win, idle = 20.0, 7.0
    # batch 1 closes on the WINDOW, batch 2 on the IDLE timeout, and all four
    # metadata values differ -> a wrong slot cannot reproduce both decisions.
    agg, fake, client = _agg(
        _scan(2),
        [
            _j(B1),
            _j(B2, as_bytes=True),
            f"{T0 - win}",
            f"{T0}",
            f"{T0 - (win - 1)}",
            f"{T0 - idle}",
        ],
        values={f"batch:{B1}:camera_id": CAM, f"batch:{B2}:camera_id": "cam-south"},
    )
    agg._batch_window = win
    agg._idle_timeout = idle
    with _clock(shim), LogCapture() as cap:
        out = _timeouts(agg)
    assert out == [B1, B2], out
    assert agg.close_calls == [B1, B2], agg.close_calls
    assert len(client.pipes) == 2, [p.keys for p in client.pipes]
    assert client.pipes[0].keys == [KEY1, KEY2], client.pipes[0].keys
    assert client.pipes[1].keys == [
        f"batch:{B1}:started_at",
        f"batch:{B1}:last_activity",
        f"batch:{B2}:started_at",
        f"batch:{B2}:last_activity",
    ], client.pipes[1].keys
    infos = [
        r for r in cap.records if r.levelno == logging.INFO and r.getMessage() == "Closing batch"
    ]
    assert len(infos) == 2, cap.texts()
    assert [r.batch_id for r in infos] == [B1, B2], [r.batch_id for r in infos]
    assert infos[0].reason == f"batch window exceeded ({win:.1f}s >= {win:.1f}s)", infos[0].reason
    assert infos[1].reason == f"idle timeout exceeded ({idle:.1f}s >= {idle:.1f}s)", infos[1].reason
    assert [r.camera_id for r in infos] == [CAM, "cam-south"], [r.camera_id for r in infos]
    assert fake.gets == [f"batch:{B1}:camera_id", f"batch:{B2}:camera_id"], fake.gets
    summary = cap.one(logging.INFO, "Closed timed-out batches")
    _attrs(summary, {"batch_count": 2}, ("XXbatch_countXX", "BATCH_COUNT"))


# --- the per-batch except arm -------------------------------------------------
def test_close_failure_logs_batch_key_error_and_exc_info_then_continues() -> None:
    shim = _TimeShim()
    win = 9.0
    agg, fake, _ = _agg(
        _scan(2, as_bytes=True),
        [_j(B1), _j(B2), f"{T0 - win}", f"{T0}", f"{T0 - win}", f"{T0}"],
        values={f"batch:{B1}:camera_id": CAM, f"batch:{B2}:camera_id": "cam-south"},
        boom=B1,
    )
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        out = _timeouts(agg)
    assert out == [B2], f"a failed close must not be reported as closed: {out}"
    assert agg.close_calls == [B1, B2], "the loop must continue after a failure"
    err = cap.one(logging.ERROR, "Error checking timeout for batch key")
    _attrs(
        err,
        {"batch_key": KEY1, "error": str(BOOM)},
        ("XXbatch_keyXX", "BATCH_KEY", "XXerrorXX", "ERROR"),
    )
    assert err.exc_info is not None and err.exc_info[1] is BOOM, err.exc_info
    _closing(cap, B2, "cam-south", f"batch window exceeded ({win:.1f}s >= {win:.1f}s)")
    assert cap.count(logging.INFO, "Closed timed-out batches") == 1
    _attrs(
        cap.one(logging.INFO, "Closed timed-out batches"),
        {"batch_count": 1},
        ("XXbatch_countXX", "BATCH_COUNT"),
    )


def test_unparseable_started_at_lands_in_the_except_arm_with_the_real_batch_key() -> None:
    shim = _TimeShim()
    agg, _, client = _agg(_scan(1), [_j(B1), "not-a-number", f"{T0}"])
    agg._batch_window = 9.0
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == []
    err = cap.one(logging.ERROR, "Error checking timeout for batch key")
    # KEY1 arrives as a str here, and stays a str: the decode branch is a no-op
    assert client.pipes[0].keys == [KEY1], client.pipes[0].keys
    _attrs(err, {"batch_key": KEY1})
    assert isinstance(err.exc_info[1], ValueError), err.exc_info


# --- bytes in, str out --------------------------------------------------------
def test_bytes_metadata_values_are_decoded_and_the_key_stays_a_str() -> None:
    shim = _TimeShim()
    win = 9.0
    agg, _, client = _agg(
        _scan(1, as_bytes=True),
        [_j(B1, as_bytes=True), f"{T0 - win}".encode(), f"{T0}".encode()],
        values={f"batch:{B1}:camera_id": CAM},
    )
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == [B1]
    assert client.pipes[1].keys == [
        f"batch:{B1}:started_at",
        f"batch:{B1}:last_activity",
    ], client.pipes[1].keys
    _closing(cap, B1, CAM, f"batch window exceeded ({win:.1f}s >= {win:.1f}s)")


def test_non_json_batch_id_is_used_verbatim() -> None:
    shim = _TimeShim()
    win = 9.0
    agg, _, _ = _agg(_scan(1), ["legacy-plain-id", f"{T0 - win}", f"{T0}"], values={})
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture():
        assert _timeouts(agg) == ["legacy-plain-id"]
    assert agg.close_calls == ["legacy-plain-id"], agg.close_calls


def test_fresh_batch_without_last_activity_falls_back_to_started_at() -> None:
    # started_at present, last_activity MISSING: the shipped code falls back to
    # ``started_at`` (so idle_time == window_elapsed and nothing closes). The
    # ``if last_activity_str or True`` mutant instead does float(None) and
    # raises, which is a visible ERROR here.
    shim = _TimeShim()
    win = 9.0
    agg, _, _ = _agg(_scan(1), [_j(B1), f"{T0 - 5}", None], values={})
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == []
    assert agg.close_calls == [], agg.close_calls
    assert cap.count(logging.ERROR, "Error checking timeout for batch key") == 0, cap.texts()
    cap.none_at_all()


# --- the decode branches are NOT no-ops (a BOM proves it) ----------------------
# ``x.decode() if isinstance(x, bytes) else x`` followed by ``json.loads(x)``
# looks redundant, but it is not: json.loads ACCEPTS bytes and strips a UTF-8 BOM
# on the way in, while .decode() KEEPS the BOM, so the two spellings diverge
# observably on a BOM'd value. These three tests are what kill the
# ``... and False else x`` polarity mutants (_39/_71/_74); without them those
# keys would look equivalent.
_BOM = b"\xef\xbb\xbf"


def test_scan_key_bom_survives_the_decode_and_reaches_the_metadata_get() -> None:
    shim = _TimeShim()
    win = 9.0
    # batch_id itself is plain JSON, so it parses; the KEY keeps its BOM through
    # .decode(), so the metadata pipeline asks for the BOM'd key and finds no
    # started_at -> the shipped warning fires with the BOM'd batch key.
    agg, _, client = _agg(
        [_BOM + KEY1.encode()],
        [_j(B1), None, None],
        values={},
    )
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == []
    warned = cap.one(logging.WARNING, "Batch missing started_at timestamp, skipping")
    _attrs(warned, {"batch_id": B1})
    assert client.pipes[1].keys == [
        f"batch:{B1}:started_at",
        f"batch:{B1}:last_activity",
    ], client.pipes[1].keys
    assert client.pipes[0].keys == [_BOM + KEY1.encode()], client.pipes[0].keys


def test_bom_on_started_at_breaks_the_float_and_lands_in_the_except_arm() -> None:
    shim = _TimeShim()
    win = 9.0
    # shipped: .decode() keeps the BOM -> json.loads raises JSONDecodeError ->
    # the pass keeps the BOM'd str -> float() raises ValueError -> except arm.
    # mutant (json.loads on the raw bytes): the BOM is stripped, the value
    # parses, and the batch CLOSES instead.
    agg, _, _ = _agg(_scan(1), [_j(B1), _BOM + f"{T0 - win}".encode(), f"{T0}"], values={})
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == [], "a BOM'd started_at must not close the batch"
    assert agg.close_calls == [], agg.close_calls
    err = cap.one(logging.ERROR, "Error checking timeout for batch key")
    _attrs(err, {"batch_key": KEY1})
    assert isinstance(err.exc_info[1], ValueError), err.exc_info


def test_bom_on_last_activity_breaks_the_float_and_lands_in_the_except_arm() -> None:
    shim = _TimeShim()
    win = 9.0
    agg, _, _ = _agg(_scan(1), [_j(B1), f"{T0 - win}", _BOM + f"{T0}".encode()], values={})
    agg._batch_window = win
    agg._idle_timeout = 1e9
    with _clock(shim), LogCapture() as cap:
        assert _timeouts(agg) == []
    assert agg.close_calls == [], agg.close_calls
    err = cap.one(logging.ERROR, "Error checking timeout for batch key")
    _attrs(err, {"batch_key": KEY1})
    assert isinstance(err.exc_info[1], ValueError), err.exc_info


# --- the clock shim really is module-local -------------------------------------
def test_clock_shim_does_not_touch_the_stdlib_time_module() -> None:
    import time as time_mod

    real = time_mod.time
    shim = _TimeShim()
    with _clock(shim):
        assert ba.time.time() == T0
        assert time_mod.time is real, "the stdlib module must not be patched"
    assert ba.__dict__.get("time") is not shim, "shim leaked into the module globals"
    assert time_mod.time is real
