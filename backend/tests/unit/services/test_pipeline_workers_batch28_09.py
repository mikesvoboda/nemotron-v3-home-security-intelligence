"""S3 batch-28 lane 09 - ``pipeline_workers`` group g09 kill battery (72 keys).

Module: ``backend/services/pipeline_workers.py``.  The manifest was proven against
blob ``74649fd3``; the shared lane has since moved to ``b3965679``, whose only change is
an import plus the analyzer construction inside ``AnalysisQueueWorker.__init__`` - so
BOTH functions this file drives are BYTE-IDENTICAL between the two blobs (verified:
``diff <(sed -n '885,973p' old) <(sed -n '888,976p' new)`` is empty), and the manifest's
per-key line numbers carry a uniform +3 shift that the replay's before-text-anchored
splice absorbs.  Every line number below is the CURRENT shipped (``b3965679``) one:
the manifest keys were admitted against the pre-rebase numbering, so a citation reads
+1 below the new import and +3 below the constructor hunk - the MUTANTS are unchanged,
only their coordinates moved.
Admitted manifest: ``/tmp/wp-pw/pipeline_workers/``
``manifest.json`` group 9 ("g09 BatchTimeoutWorker._run_loop", 72 KILLABLE /
0 EQUIVALENT / 0 NEEDS_INVESTIGATION), plus ``group_9.keys`` and ``survivors.json``
for the exact per-key diffs.  The lane's other half - g11, the 50 keys of
``AnalysisQueueWorker._run_loop`` - is delivered next door in
``test_pipeline_workers_batch28_09b.py``, because no file may carry more than 80
tests (this file: 8 tests, that one: 11).

All 72 keys sit on ``BatchTimeoutWorker._run_loop`` (shipped lines 1289-1366).
Every leg drives the REAL coroutine - ``await M.BatchTimeoutWorker._run_loop(worker)``
is the shipped function object called with an attribute-only ``self``, never an
autospec'd double of the loop.  Termination is scripted, never lucky: the last pass
of every leg raises ``asyncio.CancelledError`` from the aggregator, so the shipped
``break`` (L1348) ends the drive.

Test -> mutant-key map
======================
Occurrence-twin check: each g09 diff ``(before, after, line)`` tuple was searched
across all 959 survivors - no pair occurs anywhere else, so NO twin keys are carried
here and none of these keys is claimed by another group.

- ``xǁBatchTimeoutWorkerǁ_run_loop__mutmut_1/_2/_3/_4`` L1297
  ``logger.info("BatchTimeoutWorker loop started")`` -> ``None`` / ``"XX...XX"`` /
  all-lower / all-upper, and ``..._mutmut_85/_86/_88/_89/_90/_91/_92/_93``
  L1363-1365 exit INFO: message -> ``None`` / ``XX..XX`` / lower / upper and
  ``extra={"batches_closed": items_processed}`` -> ``extra=None`` / the ``extra``
  drop / the two key renames.  -> ALL eight legs: the banner precedes the ``while``
  and the exit INFO follows it, and every leg pins the complete ordered INFO surface
  of one whole drive, payload included.
- ``..._mutmut_11`` L1320 ``items_processed += len(...)`` -> ``= len(...)``
  -> leg A drives ONE closing pass of 2 batches and a second of 1 and pins
  ``items_processed == 3`` (``=`` leaves 1) and the exit payload ``batches_closed
  == 3``.
- ``..._mutmut_14/_15`` L1324 ``duration = time.time() - start_time`` -> ``= None`` /
  ``= time.time() + start_time``; ``_16``-``_21`` L1325
  ``observe_stage_duration("batch", duration)`` -> ``None`` stage / ``None`` duration
  / the two argument drops / the two label renames
  -> every cadence leg pins the EXACT ``call("batch", <duration>)`` list against its
  OWN scripted clock, so ``+ start_time`` (m15: 2005.0 where shipped says 5.0) and a
  substituted ``None`` cannot alias the shipped value.
- ``..._mutmut_22``-``_29`` L1327
  ``record_pipeline_stage_latency("detect_to_batch", duration * 1000)`` -> ``None``
  label / ``None`` value / the two drops / both renames / ``/ 1000`` / ``* 1001``
  -> the cadence legs pin ``call("detect_to_batch", D * 1000)`` with ``D`` chosen so
  that ``D``, ``D * 1000``, ``D / 1000`` and ``D * 1001`` are four different numbers.
- ``..._mutmut_30``-``_39`` L1329
  ``await record_stage_latency(self._redis, "batch", duration * 1000)`` -> ``None``
  client / ``None`` stage / ``None`` value / the two drops (which shift the client
  argument out of slot 0) / both renames / ``/ 1000`` / ``* 1001``
  -> the cadence legs pin the full ``await_args_list`` INCLUDING the identity of
  argument 0, which is the only observable of the dropped-client mutants.
- ``..._mutmut_40``-``_47`` L1331-1335
  ``logger.info(f"Closed {len(closed_batches)} timed-out batches",
  extra={"batch_count": ..., "batch_ids": closed_batches})`` -> message ``None`` /
  message drop (a ``TypeError`` in the shipped ``try``) / ``extra=None`` / ``extra``
  drop / the four key renames
  -> legs A, B, C and D pin the CLOSED INFO's message AND payload, with a different
  batch-id list and count in each.
- ``..._mutmut_57`` L1343 ``if sleep_time > 0:`` -> ``>= 0``
  -> THE THREE-SIDED CADENCE CONTRACT the manifest spec mandates: a battery that
  scripts only ``elapsed < interval`` is VACUOUS for m57 because shipped and m57
  agree there (probe3 §F).  Legs A and B script ``elapsed < interval`` and pin every
  recorded ``asyncio.sleep`` argument to ``check_interval - elapsed`` EXACTLY; leg C
  scripts ``elapsed > interval`` and leg D the ``elapsed == interval`` boundary, and
  both pin that ``asyncio.sleep`` is NEVER awaited, because shipped clamps
  ``sleep_time = max(0.0, self._check_interval - elapsed)`` (L1342) to ``0.0`` and
  ``if 0.0 > 0`` is False.  m57 sleeps ``0.0`` in exactly those two legs - measured
  shipped ``[]`` vs m57 ``[0.0]`` - and nowhere else.
- ``..._mutmut_5`` L1300 ``last_heartbeat = time_module.time()`` -> ``= None``,
  ``_6``/``_7`` L1301 ``heartbeat_interval = 20.0`` -> ``None`` / ``21.0``,
  ``_9`` L1308 ``if self._supervisor is not None:`` -> ``is None``
  -> ``test_the_batch_timeout_heartbeat_fires_once_per_20_second_step`` is the ONLY leg
  whose shipped run evaluates ``now - last_heartbeat >= heartbeat_interval``: its
  heartbeat alias walks ``0.0 -> 20.0 -> 40.0``, so shipped beats exactly twice and
  re-baselines both times - ``21.0`` beats once (its first gate is short and never
  re-baselines), a ``None`` operand raises ``TypeError`` inside the shipped ``try``
  and replaces both beats with the error arm, and the m9 flip beats never.
  ``test_an_unsupervised_batch_worker_never_reads_the_heartbeat_clock`` reads m9
  from the other side (under the flip the arm runs for a ``None`` supervisor and the
  read count doubles).  Every OTHER leg pins the heartbeat module's read count at
  exactly 1 - the single unconditional L1300 baseline - as an m5/m9 backstop.
- ``..._mutmut_60``/``_62`` L1350 ``self._stats.errors += 1`` -> ``= 1`` / ``+= 2``,
  ``_63`` L1351 ``state = WorkerState.ERROR`` -> ``None``,
  ``_84`` L1361 ``state = WorkerState.RUNNING`` -> ``None``
  -> the two error legs pin ``errors`` ACROSS two failures (shipped 1 then 2, so
  both mutants are visible in the payload pair and in the final stats), the state
  read INSIDE the ``record_pipeline_error`` call window - the only place L1351 is
  observable, and under m63 the shipped ``WorkerStats.to_dict()`` raises
  ``AttributeError: 'NoneType' object has no attribute 'value'`` right there - and
  the state AFTER the failed pass (L1361) through the shipped ``to_dict()``.
- ``..._mutmut_64/_65/_66/_69/_70/_71/_72/_73/_74/_76/_77/_78/_79``-``_82``
  L1353-1358: ``categorize_exception(e, "batch_timeout")`` -> ``error_type = None`` /
  ``categorize_exception(None, ...)`` / worker name -> ``None`` / ``"XXbatch_timeoutXX"``
  / ``"BATCH_TIMEOUT"``, ``record_pipeline_error(error_type)`` -> ``None``, and the
  ERROR call's message -> ``None``, ``exc_info=True`` -> ``None`` / ``False`` /
  dropped, ``extra`` -> ``None`` / dropped / the four key renames.
  -> both error legs pin ``record_pipeline_error`` awaited with the EXACT shipped
  label ``"batch_timeout_connection_error"`` - a string that exists only when BOTH
  categorizer arguments are shipped (the injected ``ConnectionError`` name hits the
  L164-167 name tuple first, so a ``None`` worker name yields
  ``"None_connection_error"``, a renamed one ``"XXbatch_timeoutXX_connection_error"``,
  and ``categorize_exception(None, ...)`` - which does NOT raise, it falls through to
  ``"batch_timeout_processing_error"`` - is caught by the same equality pin), the
  ERROR message ``f"Error in BatchTimeoutWorker loop: {e}"`` carrying the injected
  exception's text, the record's ``exc_info`` TYPE and VALUE (``None`` / ``False`` /
  dropped all leave ``record.exc_info is None``), and the payload
  ``{"error_count": <that pass's count>, "error_type": <exact label>}``.

The control leg ``test_a_cancelled_pass_logs_the_cancelled_info_and_breaks_before_
the_sleep`` states the sibling ``asyncio.CancelledError`` arm - a DIFFERENT INFO text,
``break`` before the cadence arithmetic, one clock read, zero metric calls - so the
cadence legs' ``sleeps == []`` cannot be re-explained as an accidental cancellation
and no CLOSED/ERROR pin can be satisfied by that arm's record.

Every leg above is the MEASURED failing set of the shadow-tree mutant run (each key
built from its exact survivor diff in a symlinked shadow of this tree, battery run
against it: 72/72 KILLED, and pristine green serially and co-run with
``test_pipeline_workers_batch28_17.py``).

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it,
and every value an assertion depends on is injected by this file (the aggregator's
pass script, the two clock scripts, the interval, the failure).

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``, then
  filtered to this module's logger name) and read the RAW ``record.msg`` plus
  ``record.args`` / ``record.exc_info`` / ``record.levelno``; ``extra`` payloads are
  read as the record attributes the shipped ``Logger.makeRecord`` added beyond the
  ``LogRecord`` core plus this module's ``ContextFilter`` contributions (measured -
  batch28_13 pattern).
* Mocks of real attributes are autospec'd (WP4.2 fast path) and installed with
  ``new=``: ``observe_stage_duration`` / ``record_pipeline_stage_latency`` /
  ``record_stage_latency`` / ``record_pipeline_error`` (all four are held by
  ``from ... import`` on THIS module - pipeline_workers.py:43 and 55-59 - so the
  patch lands on the binding the loop actually resolves, not on the origin module)
  and ``asyncio.sleep``.  Injected collaborators - the Redis client, the
  ``BatchAggregator``, the ``WorkerSupervisor`` - are attributes of a
  ``create_autospec(BatchTimeoutWorker)`` INSTANCE double, never patch sites, and the
  autospec'd ``_run_loop`` on that double is NEVER awaited.
* Two clocks, exactly as the shipped body reads them.  Its function-local
  ``import time`` (L1295 - the cadence / duration / stamp clock) is scripted by
  swapping the ``sys.modules["time"]`` ENTRY for the window - a function-local
  ``import`` binds from there, so no attribute of the real ``time`` module is ever
  touched and the stand-in itself reports how many reads the shipped body performed
  (a pin in its own right).  The ``time_module`` alias (L33 - the heartbeat clock) is
  installed with ``patch.object(M, "time_module", new=...)``: pinned to a CONSTANT in
  the cadence and error legs (so those legs cannot be killed by a heartbeat mutation
  and cannot sleep twenty simulated seconds) and walked deliberately in the two
  heartbeat legs.  ``time.monotonic`` / ``time.perf_counter`` are never patched and
  never asserted.
* Termination is structural: the ``asyncio.sleep`` double records the delay and ends
  the scripted pass, and every leg's final pass raises ``CancelledError`` so the
  shipped ``break`` ends the drive; the aggregator stub also raises
  ``AssertionError`` if a mutant walks off the script, which lands in the shipped
  handler and goes red on the pinned INFO surface instead of riding the 5 s ini
  timeout.
* No import-time global spy: every double is installed inside the leg that uses it,
  module-global access goes through ``live_globals`` (three-worlds safe, proven in
  ``test_pipeline_workers_batch28_17.py``), and the only import-time capture is the
  real ``asyncio.sleep`` FUNCTION OBJECT, so the injected stubs can yield to the loop
  without recursing into themselves.
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import logging
import sys
import time as real_time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import call, create_autospec, patch

import pytest

from backend.services import pipeline_workers as M
from backend.services.batch_aggregator import BatchAggregator
from backend.services.pipeline_workers import BatchTimeoutWorker, WorkerStats
from backend.services.worker_supervisor import WorkerSupervisor

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]

# The real asyncio.sleep, captured at import time so this file's injected stubs can
# yield control to the loop without recursing into themselves.
_REAL_SLEEP = asyncio.sleep


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L1297: logger.info("BatchTimeoutWorker loop started")
BANNER_INFO = "BatchTimeoutWorker loop started"
# L1347: logger.info("BatchTimeoutWorker loop cancelled")
CANCELLED_INFO = "BatchTimeoutWorker loop cancelled"
# L1363-1365: logger.info("BatchTimeoutWorker loop exited",
#                         extra={"batches_closed": self._stats.items_processed})
EXIT_INFO = "BatchTimeoutWorker loop exited"
# L1332: f"Closed {len(closed_batches)} timed-out batches"
CLOSED_INFO_TPL = "Closed {} timed-out batches"
# L1356: f"Error in BatchTimeoutWorker loop: {e}"
ERROR_INFO_TPL = "Error in BatchTimeoutWorker loop: {}"
# L1353 categorize_exception(<ConnectionError>, "batch_timeout") -> the L164-167 name
# tuple fires first, so the shipped label is f"{worker_name}_connection_error".
ERROR_LABEL = "batch_timeout_connection_error"
# WorkerState values (L196-200) as the shipped WorkerStats.to_dict() renders them
# (L212-219).  A fresh WorkerStats starts STOPPED (L210).
STATE_STOPPED = "stopped"
STATE_RUNNING = "running"
STATE_ERROR = "error"
# L1301: heartbeat_interval = 20.0  # Send heartbeat every 20 seconds
HEARTBEAT_INTERVAL = 20.0

# The four module-level metric collaborators the loop calls (see the module docstring
# for the import lines that put them on this module).
PATCHED_GLOBALS = (
    "observe_stage_duration",
    "record_pipeline_stage_latency",
    "record_stage_latency",
    "record_pipeline_error",
)


# =============================================================================
# Observation helpers (batch27_01 / batch28_13 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load-bearing.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped f-string / constant log call.

    ``record.msg`` is the RAW message.  Every shipped site in this group is an
    already-interpolated f-string or a constant, so ``args`` must stay empty (a moved
    or dropped message argument lands IN ``msg``).  ``exc_info`` is NOT pinned here -
    the L1355-1359 ERROR call passes ``exc_info=True`` and is pinned field-by-field by
    the legs that reach it.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for an f-string message: {r.args!r}"


def pin_levels(caplog: pytest.LogCaptureFixture, msgs: list[str], level: int) -> None:
    """Pin the ordered, complete surface of ONE level for a whole leg."""
    recs = at(caplog, level)
    name = logging.getLevelName(level)
    assert [r.msg for r in recs] == msgs, (
        f"{name} surface mutated: {[r.msg for r in recs]} != {msgs}"
    )
    for r, msg in zip(recs, msgs, strict=True):
        pin_record(r, msg=msg, level=level)


def _baseline_attrs() -> frozenset[str]:
    """Attribute names that are NOT part of a shipped ``extra=`` payload.

    The union of (a) the fields ``logging.LogRecord.__init__`` always sets and
    (b) the fields this module's ``ContextFilter`` injects.  (b) is MEASURED, not
    transcribed: the filter is idempotent, so running it over a record it has already
    seen adds exactly the injected names once.  ``message`` is excluded as well - it
    is set by the formatter, not by the log call.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The ``extra=`` dict the shipped call passed, as the record shows it.

    ``Logger.makeRecord`` copies ``extra`` into the record verbatim
    (``for key in extra: record.__dict__[key] = extra[key]``), so removing the
    baseline leaves precisely the shipped payload - which is how ``extra=None``, the
    dropped ``extra`` argument and the renamed keys become visible.
    """
    return {k: v for k, v in record.__dict__.items() if k not in BASELINE_ATTRS}


def pin_payloads(
    caplog: pytest.LogCaptureFixture,
    level: int,
    payloads: list[dict[str, Any]],
) -> None:
    """Pin the ``extra=`` payload of EVERY record at ``level``, in order."""
    recs = at(caplog, level)
    assert len(recs) == len(payloads), (
        f"expected {len(payloads)} {logging.getLevelName(level)} records, got {len(recs)}: "
        f"{[r.msg for r in recs]}"
    )
    for r, payload in zip(recs, payloads, strict=True):
        assert shipped_extra(r) == payload, (
            f"extra payload mutated on {r.msg!r}: {shipped_extra(r)!r} != {payload!r}"
        )


def live_globals(fn: Any) -> dict[str, Any]:
    """Name-resolution dict of the LIVE function object (three-worlds safe).

    * Pristine repo / replay shadow (the mutant module IS the imported module):
      ``fn.__globals__ is M.__dict__`` - identity fast path.
    * ep_plugin-style lane exec'ing a variant body into a snapshot COPY of the module
      dict: that copy is what the body reads, so it is returned.
    * ``mutants/`` re-bank home: the mutmut trampoline's ``__globals__`` is mutmut's
      dict while the shipped body sits behind ``__wrapped__`` with globals ==
      ``M.__dict__``; the identity guard fires only there.
    """
    g = fn.__globals__
    if g is not M.__dict__:
        w = getattr(fn, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return g


def autospec_of(target: Any) -> Any:
    """One double, visibly ``create_autospec``'d from a shipped callable (WP4.2).

    ``create_autospec`` infers the coroutine flag from ``inspect``, so doubles of the
    shipped ``async def`` collaborators come out ``AsyncMock`` (``await_args_list``
    available on ``record_stage_latency``) and the sync ones ``MagicMock``
    (``call_args_list`` on ``observe_stage_duration`` / ``record_pipeline_error``).
    """
    return create_autospec(target)


# =============================================================================
# Clocks - exactly the two the shipped body reads
#
# (1) The function-local ``import time`` (L1295) is the cadence / duration / stamp
#     clock.  A function-local ``import`` binds from sys.modules, so the scripted
#     clock is a per-window swap of THAT ENTRY (patch.dict - never an attribute PATCH
#     on the real module, and never a time.monotonic / time.perf_counter touch).
# (2) The module-level ``import time as time_module`` alias (L33) is the heartbeat
#     clock, reached through this module's binding via
#     ``patch.object(M, "time_module", new=...)``.
# =============================================================================


class FakeTimeModule:
    """Drop-in for the ``time`` module answering from a scripted list.

    Every other attribute delegates to the real module, so anything else that lazily
    ``import time`` inside the window (logging internals never do; asyncio binds at
    import time) keeps working unchanged.  ``reads`` counts the ``time()`` calls the
    shipped body actually performed - itself a load-bearing pin, since the shipped
    body reads this clock 4 times per closing pass, 2 per idle pass and 1 per failing
    pass.  Running the script off the end RAISES instead of repeating, so a mutant
    that ADDS a read surfaces inside the shipped ``try`` rather than silently reusing
    a value.
    """

    def __init__(self, *answers: float) -> None:
        self._answers = answers
        self.reads = 0

    def time(self) -> float:
        i = self.reads
        self.reads += 1
        if i >= len(self._answers):
            raise StopIteration(
                f"the loop read the clock {i + 1} times; this leg scripted {len(self._answers)}"
            )
        return self._answers[i]

    def __getattr__(self, name: str) -> Any:
        return getattr(real_time, name)


class ConstantTimeModule:
    """The ``time_module`` alias pinned to one value: the leg's heartbeat is inert.

    With every read equal, ``now - last_heartbeat`` is ``0.0`` and
    ``0.0 >= 20.0`` is False, so no beat fires and no heartbeat operand can raise -
    which is what keeps the cadence and error legs owned by their own keys.  ``reads``
    is still counted: a shipped run performs exactly ONE read (the unconditional
    L1300 baseline) whatever the supervisor.
    """

    def __init__(self, value: float = 500.0) -> None:
        self.value = value
        self.reads = 0

    def time(self) -> float:
        self.reads += 1
        return self.value

    def __getattr__(self, name: str) -> Any:
        return getattr(real_time, name)


class SteppingTimeModule:
    """The ``time_module`` alias walked deliberately - the heartbeat legs only.

    ``time()`` returns ``steps[i]`` for read ``i`` and then repeats the last value, so
    a leg can advance the clock by exactly the shipped ``heartbeat_interval`` per
    gated pass and pin BOTH the ``record_heartbeat`` call list and the read count.
    """

    def __init__(self, *steps: float) -> None:
        self._steps = steps
        self.reads = 0

    def time(self) -> float:
        i = self.reads
        self.reads += 1
        return self._steps[i] if i < len(self._steps) else self._steps[-1]

    def __getattr__(self, name: str) -> Any:
        return getattr(real_time, name)


# =============================================================================
# Harness: the pass script, the worker double, the driver
# =============================================================================


@dataclass
class Pass:
    """One scripted iteration of the shipped loop.

    ``returns`` is what ``check_batch_timeouts()`` yields (``[]`` for an idle pass,
    batch ids for a closing pass); ``raises`` replaces that result with a failure - a
    plain ``Exception`` for the error arm, or ``asyncio.CancelledError`` as the
    sentinel that ends the drive through the shipped ``break``.
    """

    returns: list[str] = field(default_factory=list)
    raises: BaseException | None = None


@dataclass
class Run:
    """One scripted drive, its clock script, and everything it observed.

    ``clock`` lists the function-local ``time()`` reads IN THE ORDER the shipped body
    performs them::

        start_time = time.time()                     # L1305, every pass
        self._stats.last_processed_at = time.time()  # L1321, closing pass only
        duration = time.time() - start_time          # L1324, closing pass only
        elapsed = time.time() - start_time           # L1341, every pass

    so ``duration`` is ``read[2] - read[0]`` and ``elapsed`` is the LAST read minus
    ``read[0]`` of that pass.
    """

    passes: list[Pass]
    clock: list[float]
    interval: float = 0.0
    supervisor: Any = None
    heartbeat: Any = ConstantTimeModule
    hb_module: Any = None
    calls: int = 0
    sleeps: list[float] = field(default_factory=list)
    states_at_error_call: list[str | None] = field(default_factory=list)

    def heartbeat_reads(self) -> int:
        """How many ``time_module.time()`` reads the shipped body actually made.

        Shipped performs exactly one read more than the number of iterations that
        reach the gate: the unconditional L1300 baseline, plus one L1309 read per
        pass (the gate read happens BEFORE ``check_batch_timeouts``, so even a pass
        that is cancelled by the aggregator still costs one).
        """
        assert self.hb_module is not None, "the drive has not run yet"
        return self.hb_module.reads

    def next_pass(self) -> Pass:
        """The scripted pass in flight.

        The shipped body calls ``check_batch_timeouts()`` exactly ONCE per iteration
        (L1317), so a NEW call means a new pass - which is how the index advances.  It
        must NOT be driven by the sleep spy: a pass whose ``elapsed >= check_interval``
        never reaches L1344 at all, and a pass that fails inside the aggregator never
        reaches it either.  A mutant that calls the aggregator more times than there
        are scripted passes walks off the script and gets a loud ``AssertionError``,
        which lands in the shipped ``except Exception`` and reddens the leg's pinned
        INFO / stats surface.
        """
        self.calls += 1
        index = self.calls - 1
        if index >= len(self.passes):
            raise AssertionError(
                f"the loop entered iteration {index + 1} of a {len(self.passes)}-pass script"
            )
        return self.passes[index]


PASS_CEILING = 40


def make_worker(run: Run) -> Any:
    """Attribute-only ``self`` for the real coroutine, on an autospec'd instance.

    ``create_autospec(BatchTimeoutWorker)`` enforces every method signature; its
    ``_run_loop`` AsyncMock is NEVER awaited - every leg calls the shipped function
    object directly.  Only the attributes the loop resolves through ``self`` are
    installed and every one of them is this file's: ``_aggregator`` is an autospec'd
    ``BatchAggregator`` whose ``check_batch_timeouts`` serves the pass script after a
    REAL await (so nothing can spin without yielding to the loop), ``_redis`` is an
    autospec'd Redis client whose IDENTITY the L1329 stage-latency call must forward,
    ``_check_interval`` is the leg's interval, ``_stats`` a real shipped
    ``WorkerStats()`` so ``items_processed`` / ``errors`` / ``state`` are the shipped
    accumulators, ``_worker_name`` is the shipped constructor default (L1207) and
    ``_running`` is the loop's own switch.
    """
    worker = create_autospec(BatchTimeoutWorker).return_value
    aggregator = create_autospec(BatchAggregator).return_value

    async def check_batch_timeouts() -> list[str]:
        if run.calls > PASS_CEILING:
            raise RuntimeError("the loop iterated more times than any shipped path can")
        scripted_pass = run.next_pass()
        await _REAL_SLEEP(0)  # a real yield point, so no driver can spin
        if scripted_pass.raises is not None:
            raise scripted_pass.raises
        return list(scripted_pass.returns)

    aggregator.check_batch_timeouts.side_effect = check_batch_timeouts
    worker._redis = create_autospec(M.RedisClient).return_value
    worker._aggregator = aggregator
    worker._check_interval = run.interval
    worker._stop_timeout = 10.0
    worker._supervisor = run.supervisor
    worker._worker_name = "batch_timeout"
    worker._running = True
    worker._task = None
    worker._stats = WorkerStats()
    return worker


@contextlib.asynccontextmanager
async def scripted(run: Run) -> Any:
    """Drive the shipped loop through the leg's whole script, then hand out the spies.

    Yields ``(worker, doubles, clock)`` INSIDE the patch window, because the state
    pins (``states_at_error_call``, the final ``to_dict()``) must be taken while the
    doubles are still installed.  Every double is autospec'd from the shipped callable
    and installed with ``new=`` (the WP4.2 spelling), so a leg can also read the call
    lists after the window closes.
    """
    worker = make_worker(run)
    sleep_double = autospec_of(_REAL_SLEEP)

    async def sleep_side_effect(delay: float, *_args: Any, **_kwargs: Any) -> None:
        """Record the delay; stop the loop if every scripted pass has been driven.

        This is only a backstop - every leg's LAST pass raises ``CancelledError`` from
        the aggregator, so the shipped ``break`` (L1348) is what really ends the
        drive.  It cannot be the mechanism that advances the pass script, because a
        pass whose ``elapsed >= check_interval`` never reaches L1344 at all.
        """
        run.sleeps.append(delay)
        if run.calls >= min(len(run.passes), PASS_CEILING):
            worker._running = False

    sleep_double.side_effect = sleep_side_effect

    record_error = autospec_of(M.record_pipeline_error)
    # L1351 writes the ERROR state and L1361 restores RUNNING, so the ONLY place the
    # shipped L1351 write is observable is inside the L1354 record_pipeline_error call
    # that sits between them.  This side effect snapshots the state at exactly that
    # moment through the shipped WorkerStats.to_dict() - which is also what makes m63
    # (state = None) raise right there instead of passing silently.
    record_error.side_effect = lambda _error_type: run.states_at_error_call.append(
        worker._stats.to_dict()["state"]
    )

    doubles: dict[str, Any] = {name: autospec_of(getattr(M, name)) for name in PATCHED_GLOBALS}
    doubles["record_pipeline_error"] = record_error

    run.hb_module = run.heartbeat()
    clock = FakeTimeModule(*run.clock)
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.dict(sys.modules, {"time": clock}))
        stack.enter_context(patch.object(M, "time_module", new=run.hb_module))
        for name in PATCHED_GLOBALS:
            stack.enter_context(patch.object(M, name, new=doubles[name]))
        stack.enter_context(patch.object(asyncio, "sleep", new=sleep_double))
        await M.BatchTimeoutWorker._run_loop(worker)
        yield worker, doubles, clock


def closed_msgs(counts: list[int]) -> list[str]:
    return [CLOSED_INFO_TPL.format(n) for n in counts]


def error_msgs(errors: list[builtins.Exception]) -> list[str]:
    return [ERROR_INFO_TPL.format(e) for e in errors]


# =============================================================================
# Cadence-leg clock scripts.  Values chosen so that duration, duration * 1000,
# duration / 1000, duration * 1001 and elapsed are all different numbers, and so
# that the clamp at L1342 bites in exactly two legs (C and D).
# =============================================================================

CANCEL = asyncio.CancelledError


# =============================================================================
# 1) leg A - two closing passes: the += accumulator, the instrumentation triple,
#    the CLOSED INFO family, the ``elapsed < interval`` cadence side
#    (m11, m14-m21, m22-m29, m30-m39, m40-m47 + the banner / exit families)
# =============================================================================


async def test_two_closing_passes_accumulate_count_report_and_pace(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1289-1366 over a 2-batch then a 1-batch pass, ``interval=8.0``.

    ::

        closed_batches = await self._aggregator.check_batch_timeouts()   # L1317
        if closed_batches:
            self._stats.items_processed += len(closed_batches)           # L1320
            self._stats.last_processed_at = time.time()                  # L1321
            duration = time.time() - start_time                          # L1324
            observe_stage_duration("batch", duration)                    # L1325
            record_pipeline_stage_latency("detect_to_batch", duration * 1000)  # L1327
            await record_stage_latency(self._redis, "batch", duration * 1000)  # L1329
            logger.info(f"Closed {len(closed_batches)} timed-out batches",  # L1331-1337
                        extra={"batch_count": ..., "batch_ids": closed_batches})
        elapsed = time.time() - start_time                               # L1341
        sleep_time = max(0.0, self._check_interval - elapsed)            # L1342
        if sleep_time > 0:                                               # L1343
            await asyncio.sleep(sleep_time)                              # L1344

    36 keys live in this window.  The accumulator is pinned at 3 (m11's ``=`` leaves
    1) and again as the exit payload ``batches_closed == 3``.  Pass 1's script is
    ``start 1000.0 / stamp 1003.0 / duration 1005.0 / elapsed 1006.0`` - duration
    5.0 s, elapsed 6.0 s - so ``observe_stage_duration`` must see ``("batch", 5.0)``,
    ``record_pipeline_stage_latency`` ``("detect_to_batch", 5000.0)`` (m28's
    ``/ 1000`` is 0.005 and m29's ``* 1001`` is 5005.0), and the Redis stage call
    ``(redis, "batch", 5000.0)`` with the client's IDENTITY pinned (the only
    observable of m33/m35's dropped client argument).  Pass 2 repeats the whole
    surface at 1.0 s / 1000.0 ms with a different batch list.  The CLOSED pair is
    pinned as message AND payload (m40-m47).  Both sleeps are pinned to the shipped
    clamp ``8.0 - elapsed`` = 2.0 and 5.0 - the ``elapsed < interval`` side of m57,
    where shipped and m57 agree, so this leg alone is NOT the m57 proof.
    """
    run = Run(
        passes=[
            Pass(returns=["b1", "b2"]),
            Pass(returns=["b3"]),
            Pass(raises=CANCEL()),
        ],
        clock=[1000.0, 1003.0, 1005.0, 1006.0, 1010.0, 1011.0, 1011.0, 1013.0, 1020.0],
        interval=8.0,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, clock):
        stats = worker._stats.to_dict()

    assert stats == {
        "items_processed": 3,
        "errors": 0,
        "last_processed_at": 1011.0,
        "state": STATE_STOPPED,
    }, f"the shipped WorkerStats.to_dict() surface mutated: {stats!r}"
    assert worker._aggregator.check_batch_timeouts.await_count == 3, (
        "one aggregator call per pass, the sentinel pass included"
    )

    redis = worker._redis
    assert doubles["observe_stage_duration"].call_args_list == [
        call("batch", 5.0),
        call("batch", 1.0),
    ], f"observe_stage_duration mutated: {doubles['observe_stage_duration'].call_args_list!r}"
    assert doubles["record_pipeline_stage_latency"].call_args_list == [
        call("detect_to_batch", 5000.0),
        call("detect_to_batch", 1000.0),
    ], (
        "record_pipeline_stage_latency mutated: "
        f"{doubles['record_pipeline_stage_latency'].call_args_list!r}"
    )
    latency_calls = doubles["record_stage_latency"].await_args_list
    assert len(latency_calls) == 2, f"record_stage_latency awaited {len(latency_calls)} times"
    for c in latency_calls:
        assert not c.kwargs, f"record_stage_latency is called positionally: {c!r}"
    assert latency_calls[0].args[0] is redis, (
        f"self._redis mutated: record_stage_latency got {latency_calls[0].args[0]!r}"
    )
    assert latency_calls[0].args[1:] == ("batch", 5000.0), (
        f"stage label / milliseconds mutated: {latency_calls[0].args!r}"
    )
    assert latency_calls[1].args[0] is redis
    assert latency_calls[1].args[1:] == ("batch", 1000.0)
    assert doubles["record_pipeline_error"].call_count == 0, (
        "a clean drive must never record a pipeline error"
    )

    pin_payloads(
        caplog,
        logging.INFO,
        [
            {},
            {"batch_count": 2, "batch_ids": ["b1", "b2"]},
            {"batch_count": 1, "batch_ids": ["b3"]},
            {},
            {"batches_closed": 3},
        ],
    )
    pin_levels(
        caplog,
        [BANNER_INFO, *closed_msgs([2, 1]), CANCELLED_INFO, EXIT_INFO],
        logging.INFO,
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [2.0, 5.0], (
        f"sleep_time = max(0.0, 8.0 - elapsed) per pass (elapsed 6.0, 3.0): {run.sleeps!r}"
    )
    assert clock.reads == 9, f"4 reads per closing pass + 1 for the cancelled pass: {clock.reads}"
    assert run.heartbeat_reads() == 1, (
        "the only heartbeat-clock read of the drive is the unconditional L1300 baseline"
    )


# =============================================================================
# 2) leg B - second, independently-valued route, with an IDLE pass in between
# =============================================================================


async def test_a_closing_pass_and_an_idle_pass_keep_the_shipped_cadence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second route to the same families at different injected values.

    ``interval=6.0``; pass 1 closes one batch (start 2000.0, stamp 2003.0, duration
    read 2004.0 -> 4.0 s, elapsed 2004.5 -> 4.5 s -> sleep 1.5 s), pass 2 closes
    NOTHING - so the whole ``if closed_batches:`` body is skipped and the pass still
    sleeps ``6.0 - 1.0`` = 5.0 s - and pass 3 is the sentinel.  The idle pass carries
    its own weight: it pins that no metric call and no CLOSED INFO happen without
    closed batches, which is what stops this family from being satisfied by a stray
    second close.
    """
    run = Run(
        passes=[Pass(returns=["a1"]), Pass(returns=[]), Pass(raises=CANCEL())],
        clock=[2000.0, 2003.0, 2004.0, 2004.5, 2010.0, 2011.0, 2020.0],
        interval=6.0,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, clock):
        stats = worker._stats.to_dict()

    assert stats == {
        "items_processed": 1,
        "errors": 0,
        "last_processed_at": 2003.0,
        "state": STATE_STOPPED,
    }, f"the shipped WorkerStats.to_dict() surface mutated: {stats!r}"
    assert worker._aggregator.check_batch_timeouts.await_count == 3

    assert doubles["observe_stage_duration"].call_args_list == [call("batch", 4.0)]
    assert doubles["record_pipeline_stage_latency"].call_args_list == [
        call("detect_to_batch", 4000.0)
    ]
    latency_call = doubles["record_stage_latency"].await_args
    assert latency_call is not None
    assert latency_call.args == (worker._redis, "batch", 4000.0), (
        f"record_stage_latency mutated: {latency_call.args!r}"
    )
    assert doubles["record_pipeline_error"].call_count == 0

    pin_levels(
        caplog,
        [BANNER_INFO, CLOSED_INFO_TPL.format(1), CANCELLED_INFO, EXIT_INFO],
        logging.INFO,
    )
    pin_payloads(
        caplog,
        logging.INFO,
        [{}, {"batch_count": 1, "batch_ids": ["a1"]}, {}, {"batches_closed": 1}],
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [1.5, 5.0], run.sleeps
    assert clock.reads == 7, f"4 reads closing + 2 idle + 1 cancelled: {clock.reads}"
    assert run.heartbeat_reads() == 1


# =============================================================================
# 3) leg C - elapsed > check_interval: the sleep must NOT happen (m57 route 1)
# =============================================================================


async def test_a_pass_that_outruns_its_interval_sleeps_not_at_all(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1341-1344 with ``elapsed`` 12.0 > ``check_interval`` 8.0.

    ::

        elapsed = time.time() - start_time                     # 3012.0 - 3000.0
        sleep_time = max(0.0, self._check_interval - elapsed)  # max(0.0, -4.0) = 0.0
        if sleep_time > 0:                                     # False -> no sleep
            await asyncio.sleep(sleep_time)

    ``run.sleeps == []`` is the whole point: under m57 (``>= 0``) the SAME pass awaits
    ``asyncio.sleep(0.0)`` once - measured shipped ``[]`` vs m57 ``[0.0]`` - with
    nothing else about the leg differing.  The pass still does its work (one close of
    three batches, duration 4.0 s / 4000.0 ms reported), so a mutant cannot dodge the
    pin by failing the pass.
    """
    run = Run(
        passes=[Pass(returns=["c1", "c2", "c3"]), Pass(raises=CANCEL())],
        clock=[3000.0, 3002.0, 3004.0, 3012.0, 3020.0],
        interval=8.0,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, clock):
        stats = worker._stats.to_dict()

    assert run.sleeps == [], (
        f"shipped clamps sleep_time to 0.0 and skips the sleep; got {run.sleeps!r}"
    )
    assert stats == {
        "items_processed": 3,
        "errors": 0,
        "last_processed_at": 3002.0,
        "state": STATE_STOPPED,
    }, f"stats mutated: {stats!r}"
    assert doubles["observe_stage_duration"].call_args_list == [call("batch", 4.0)]
    assert doubles["record_pipeline_stage_latency"].call_args_list == [
        call("detect_to_batch", 4000.0)
    ]
    latency_call = doubles["record_stage_latency"].await_args
    assert latency_call is not None
    assert latency_call.args == (worker._redis, "batch", 4000.0)
    assert doubles["record_pipeline_error"].call_count == 0
    pin_levels(
        caplog,
        [BANNER_INFO, CLOSED_INFO_TPL.format(3), CANCELLED_INFO, EXIT_INFO],
        logging.INFO,
    )
    pin_payloads(
        caplog,
        logging.INFO,
        [{}, {"batch_count": 3, "batch_ids": ["c1", "c2", "c3"]}, {}, {"batches_closed": 3}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert clock.reads == 5, clock.reads
    assert run.heartbeat_reads() == 1


# =============================================================================
# 4) leg D - elapsed == check_interval: the boundary (m57 route 2)
# =============================================================================


async def test_a_pass_whose_elapsed_equals_its_interval_sleeps_not_at_all(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The boundary leg: ``elapsed`` is EXACTLY ``check_interval`` (8.0).

    ``sleep_time = max(0.0, 8.0 - 8.0) = 0.0`` and shipped's ``if sleep_time > 0`` is
    False, so the sleep is skipped; m57's ``>=`` sleeps ``0.0``.  Without this leg a
    ``>``/``>=`` swap at L1343 could still hide behind legs whose elapsed is strictly
    below the interval, where the two operators agree - which is precisely the
    vacuity the manifest spec calls out.
    """
    run = Run(
        passes=[Pass(returns=["d1", "d2"]), Pass(raises=CANCEL())],
        clock=[4000.0, 4002.0, 4006.0, 4008.0, 4020.0],
        interval=8.0,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, clock):
        stats = worker._stats.to_dict()

    assert run.sleeps == [], f"the 0.0 clamp must skip the sleep; got {run.sleeps!r}"
    assert stats["items_processed"] == 2
    assert stats["last_processed_at"] == 4002.0
    assert doubles["observe_stage_duration"].call_args_list == [call("batch", 6.0)]
    assert doubles["record_pipeline_stage_latency"].call_args_list == [
        call("detect_to_batch", 6000.0)
    ]
    latency_call = doubles["record_stage_latency"].await_args
    assert latency_call is not None
    assert latency_call.args[0] is worker._redis
    assert latency_call.args[1:] == ("batch", 6000.0)
    pin_levels(
        caplog,
        [BANNER_INFO, CLOSED_INFO_TPL.format(2), CANCELLED_INFO, EXIT_INFO],
        logging.INFO,
    )
    pin_payloads(
        caplog,
        logging.INFO,
        [{}, {"batch_count": 2, "batch_ids": ["d1", "d2"]}, {}, {"batches_closed": 2}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert clock.reads == 5, clock.reads
    assert run.heartbeat_reads() == 1


# =============================================================================
# 5) the heartbeat gate (m5, m6, m7, m9) - the ONLY leg whose shipped run
#    evaluates the heartbeat comparison
# =============================================================================


def supervisor_double() -> Any:
    """autospec'd instance double of the shipped ``WorkerSupervisor``."""
    return create_autospec(WorkerSupervisor).return_value


async def test_the_batch_timeout_heartbeat_fires_once_per_20_second_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1299-1312 - one ``record_heartbeat(worker_name)`` per 20.0 s of clock.

    ::

        last_heartbeat = time_module.time()      # read 1 -> 0.0
        heartbeat_interval = 20.0                # the shipped constant (L1301)
        while self._running:
            try:
                start_time = time.time()
                if self._supervisor is not None:              # L1308
                    now = time_module.time()                  # read 2 -> 20.0, 3 -> 40.0
                    if now - last_heartbeat >= heartbeat_interval:   # L1310
                        self._supervisor.record_heartbeat(self._worker_name)
                        last_heartbeat = now

    The heartbeat alias walks EXACTLY the shipped interval per pass, so shipped beats
    twice and re-baselines both times.  Under m7 (``21.0``) the first gate is short
    and ``last_heartbeat`` never re-baselines, so only ONE beat fires.  Under m5
    (``last_heartbeat = None``) or m6 (``heartbeat_interval = None``) the comparison
    raises ``TypeError`` inside the shipped ``try``, so BOTH beats are replaced by the
    error arm - which the zero-ERROR and zero-``record_pipeline_error`` pins see.
    Under the m9 flip the arm never runs for a present supervisor: zero beats and a
    single read.

    The read count is one per iteration PLUS the L1300 baseline - four for this
    three-pass drive - because the gate read at L1309 sits ABOVE the aggregator call,
    so even the pass the sentinel cancels still pays a read (its own comparison,
    ``40.0 - 40.0 >= 20.0``, is False, which is why only two beats are recorded).
    The worker name interpolated into the call is the shipped constructor default
    (L1207 / L1226).
    """
    supervisor = supervisor_double()
    run = Run(
        passes=[Pass(returns=[]), Pass(returns=[]), Pass(raises=CANCEL())],
        clock=[9000.0, 9001.0, 9010.0, 9011.0, 9020.0],
        interval=4.0,
        supervisor=supervisor,
        heartbeat=lambda: SteppingTimeModule(0.0, 20.0, 40.0),
    )
    win(caplog)

    async with scripted(run) as (_worker, doubles, clock):
        pass

    assert supervisor.record_heartbeat.call_args_list == [
        call("batch_timeout"),
        call("batch_timeout"),
    ], f"heartbeat contract mutated: {supervisor.record_heartbeat.call_args_list!r}"
    assert run.heartbeat_reads() == 4, (
        f"the L1300 baseline plus one gate read per iteration (the sentinel pass pays "
        f"its gate read before the aggregator raises): {run.heartbeat_reads()} reads"
    )
    assert clock.reads == 5, f"2 reads per idle pass + 1 for the cancelled pass: {clock.reads}"
    assert doubles["record_pipeline_error"].call_count == 0, (
        "the heartbeat gate must never error: the shipped comparison runs on floats"
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"batches_closed": 0}])
    assert run.sleeps == [3.0, 3.0], (
        "the two idle passes pace at interval - elapsed = 4.0 - 1.0 each"
    )


# =============================================================================
# 6) control + second m9 route: no supervisor -> the gate body never runs
# =============================================================================


async def test_an_unsupervised_batch_worker_never_reads_the_heartbeat_clock(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1308 - ``if self._supervisor is not None:`` with NO supervisor.

    Three idle passes perform exactly ONE heartbeat-clock read in total - the
    unconditional L1300 baseline - because the gate body is skipped every pass.  The
    flip (m9) runs the arm anyway, so the read count doubles and this leg goes red;
    the zero-heartbeat-beat guarantee and the zero-ERROR pin state the rest of that
    arm's absence.
    """
    run = Run(
        passes=[Pass(returns=[]), Pass(returns=[]), Pass(returns=[]), Pass(raises=CANCEL())],
        clock=[8000.0, 8001.0, 8010.0, 8011.0, 8020.0, 8021.0, 8030.0],
        interval=5.0,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (_worker, doubles, clock):
        pass

    assert run.heartbeat_reads() == 1, (
        f"a None supervisor must not read the heartbeat clock: {run.heartbeat_reads()} reads"
    )
    assert clock.reads == 7, clock.reads
    assert doubles["record_pipeline_error"].call_count == 0
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"batches_closed": 0}])
    assert run.sleeps == [4.0, 4.0, 4.0], run.sleeps


# =============================================================================
# 7) the ``except Exception`` arm (m60-m82, m84) - sole route to that family
# =============================================================================


async def test_two_failures_count_incrementally_and_report_the_shipped_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1349-1361 over two failing passes, ``interval=6.0``.

    ::

        except Exception as e:
            self._stats.errors += 1                              # L1350
            self._stats.state = WorkerState.ERROR                # L1351
            error_type = categorize_exception(e, "batch_timeout")  # L1353
            record_pipeline_error(error_type)                    # L1354
            logger.error(
                f"Error in BatchTimeoutWorker loop: {e}",        # L1356
                exc_info=True,                                   # L1357
                extra={"error_count": self._stats.errors, "error_type": error_type},  # L1358
            )
            await asyncio.sleep(self._check_interval)            # L1360
            self._stats.state = WorkerState.RUNNING              # L1361

    20 keys live here.  ``errors`` is pinned ACROSS two failures - shipped 1 then 2 -
    so m60's ``= 1`` and m62's ``+= 2`` are visible in the payload pair AND in the
    final stats.  ``record_pipeline_error`` is pinned awaited with the EXACT shipped
    label, which exists only when both ``categorize_exception`` arguments are shipped
    (m64, m65, m66, m69, m70, m71).  The ERROR record's message, its ``exc_info``
    TYPE and VALUE, and its payload are pinned per pass (m72-m82); the failed pass
    sleeps the worker's OWN ``check_interval`` (6.0), and the loop's survival is
    pinned by the second failure plus the exit INFO.
    """
    first = builtins.ConnectionError("redis connection reset by peer")
    second = builtins.ConnectionError("pool exhausted, cannot CONNECT")
    run = Run(
        passes=[Pass(raises=first), Pass(raises=second), Pass(raises=CANCEL())],
        clock=[5000.0, 5040.0, 5080.0],
        interval=6.0,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, clock):
        stats_at_exit = worker._stats.to_dict()
        states = list(run.states_at_error_call)

    assert states == [STATE_ERROR, STATE_ERROR], (
        f"the L1351 ERROR state must be live inside record_pipeline_error: {states!r}"
    )
    assert stats_at_exit == {
        "items_processed": 0,
        "errors": 2,
        "last_processed_at": None,
        "state": STATE_RUNNING,
    }, f"stats mutated: {stats_at_exit!r}"
    assert worker._aggregator.check_batch_timeouts.await_count == 3
    assert doubles["record_pipeline_error"].call_args_list == [
        call(ERROR_LABEL),
        call(ERROR_LABEL),
    ], f"record_pipeline_error mutated: {doubles['record_pipeline_error'].call_args_list!r}"
    for name in ("observe_stage_duration", "record_pipeline_stage_latency"):
        assert doubles[name].call_count == 0, f"{name} ran on a failing pass"
    assert doubles["record_stage_latency"].await_count == 0

    pin_levels(caplog, [BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"batches_closed": 0}])
    pin_levels(caplog, error_msgs([first, second]), logging.ERROR)
    pin_payloads(
        caplog,
        logging.ERROR,
        [
            {"error_count": 1, "error_type": ERROR_LABEL},
            {"error_count": 2, "error_type": ERROR_LABEL},
        ],
    )
    for record, err in zip(at(caplog, logging.ERROR), [first, second], strict=True):
        assert record.exc_info is not None, "the shipped ERROR call passes exc_info=True"
        assert record.exc_info[0] is type(err), (
            f"exc_info type mutated: {record.exc_info[0]!r} != {type(err)!r}"
        )
        assert record.exc_info[1] is err, f"exc_info value mutated: {record.exc_info[1]!r}"

    assert run.sleeps == [6.0, 6.0], (
        "the failed pass sleeps the worker's own check_interval (L1360)"
    )
    assert clock.reads == 3, f"a failing pass reads only its L1305 start_time: {clock.reads}"
    assert run.heartbeat_reads() == 1


async def test_the_pass_after_a_failure_closes_batches_and_reports_them(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second, independently-valued route: one failure, then a real close.

    ``interval=7.0``; pass 1 fails (one clock read, sleep 7.0), pass 2 closes one
    batch (start 7100.0, stamp 7101.5, duration read 7101.5 -> 1.5 s, elapsed 7103.0
    -> 3.0 s, sleep 4.0 s).  This is the leg that pins the ERROR arm's SURVIVAL from
    the other side: the state has to be back to ``running`` AND the closed-batch arm
    has to work afterwards, so the error family cannot be satisfied by a leg that
    only ever fails.
    """
    err = builtins.ConnectionError("connection reset during timeout sweep")
    run = Run(
        passes=[Pass(raises=err), Pass(returns=["z9"]), Pass(raises=CANCEL())],
        clock=[7000.0, 7100.0, 7101.5, 7101.5, 7103.0, 7110.0],
        interval=7.0,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, clock):
        stats = worker._stats.to_dict()
        states = list(run.states_at_error_call)

    assert states == [STATE_ERROR], states
    assert stats == {
        "items_processed": 1,
        "errors": 1,
        "last_processed_at": 7101.5,
        "state": STATE_RUNNING,
    }, f"stats mutated: {stats!r}"
    assert doubles["record_pipeline_error"].call_args_list == [call(ERROR_LABEL)]
    assert doubles["observe_stage_duration"].call_args_list == [call("batch", 1.5)]
    assert doubles["record_pipeline_stage_latency"].call_args_list == [
        call("detect_to_batch", 1500.0)
    ]
    latency_call = doubles["record_stage_latency"].await_args
    assert latency_call is not None
    assert latency_call.args == (worker._redis, "batch", 1500.0)
    pin_levels(
        caplog,
        [BANNER_INFO, CLOSED_INFO_TPL.format(1), CANCELLED_INFO, EXIT_INFO],
        logging.INFO,
    )
    pin_payloads(
        caplog,
        logging.INFO,
        [{}, {"batch_count": 1, "batch_ids": ["z9"]}, {}, {"batches_closed": 1}],
    )
    pin_levels(caplog, error_msgs([err]), logging.ERROR)
    pin_payloads(caplog, logging.ERROR, [{"error_count": 1, "error_type": ERROR_LABEL}])
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [7.0, 4.0], run.sleeps
    assert clock.reads == 6, clock.reads
    assert run.heartbeat_reads() == 1


# =============================================================================
# 8) control: the sibling CancelledError arm (no survivor sits on its INFO)
# =============================================================================


async def test_a_cancelled_pass_logs_the_cancelled_info_and_breaks_before_the_sleep(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1346-1348 - ``except asyncio.CancelledError``: INFO + ``break``.

    The cancelled INFO's text is DIFFERENT from the exit INFO, the ``break`` skips the
    cadence arithmetic entirely (the pass reads its ``start_time`` and nothing else,
    so the script is ONE value and ``elapsed`` is never computed), no batch work
    happens and no metric is recorded.  Stated so the cadence legs' ``sleeps == []``
    cannot be re-explained as an accidental cancellation, and so neither the CLOSED
    nor the ERROR surface can be satisfied by this arm's record.
    """
    run = Run(
        passes=[Pass(raises=CANCEL())],
        clock=[6000.0],
        interval=9.0,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, clock):
        stats = worker._stats.to_dict()

    assert run.sleeps == [], "the break skips the cadence sleep"
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"a cancelled pass changed the stats: {stats!r}"
    assert clock.reads == 1, f"the break happens before the elapsed arithmetic: {clock.reads} reads"
    assert worker._aggregator.check_batch_timeouts.await_count == 1
    for name in PATCHED_GLOBALS:
        assert doubles[name].call_count == 0, f"{name} ran on a cancelled pass"
    pin_levels(caplog, [BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"batches_closed": 0}])
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    assert run.heartbeat_reads() == 1
