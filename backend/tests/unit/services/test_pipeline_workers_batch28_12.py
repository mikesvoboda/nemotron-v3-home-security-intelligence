"""S3 batch-28 lane 12 - ``pipeline_workers`` group g12 kill battery (20 keys).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - byte-identical
to the manifest-proven source).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/``
``manifest.json`` group 12 (20 KILLABLE / 0 EQUIVALENT / 0 NEEDS_INVESTIGATION),
plus ``group_12.keys`` and ``survivors.json`` for the exact per-key diffs.

All 20 keys sit on ``QueueMetricsWorker._run_loop`` (shipped lines 1451-1488).
Every leg drives the REAL coroutine - ``await M.QueueMetricsWorker._run_loop(worker)``
is the shipped function object called with an attribute-only ``self``, never an
autospec'd double of the loop.

Test -> mutant-key map
======================
Occurrence-twin check: each g12 diff ``(function, before, after, line)`` tuple was
searched across all 959 survivors - no pair occurs anywhere else, so NO twin keys
are carried here and none of these keys is claimed by another group (the
same-shaped banner/exit/depth mutants on the OTHER workers' loops sit on their own
lines and belong to g09/g10/g11).

- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_1/_2/_3/_4``
  L1453 ``logger.info("QueueMetricsWorker loop started")`` -> ``None`` /
  ``"XX...XX"`` / all-lower / all-upper
  -> ALL five legs (the banner precedes the ``while`` and every leg pins the
  ordered INFO surface, so each banner mutant reddens five tests at once).
- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_28/_29/_30/_31``
  L1488 ``logger.info("QueueMetricsWorker loop exited")`` -> ``None`` /
  ``"XX...XX"`` / all-lower / all-upper
  -> ALL five legs (the exit INFO follows the ``while``; every leg ends normally).
- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_5``  L1456 ``last_heartbeat =
  time_module.time()`` -> ``= None``  (the unconditional baseline READ disappears)
  -> measured 4 legs (1, 2, 3, 5): every leg that counts clock reads pins the shipped
  count - one baseline read for a supervisor-free loop (legs 1/3/5), three for the
  supervised one (leg 2) - and with the read gone the count is one short.  The failure
  leg (4) asserts no read count, which is exactly why it is not among the four.
- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_6``  L1457 ``heartbeat_interval =
  20.0`` -> ``= None``
  -> SOLE route: ``test_the_heartbeat_fires_once_per_shipped_20_second_step`` -
  the ONLY leg whose shipped run evaluates ``now - last_heartbeat >=
  heartbeat_interval`` (the other legs have ``_supervisor is None``, so the gate
  body never runs).  A ``None`` operand raises ``TypeError`` inside the shipped
  ``try``, so that leg loses BOTH heartbeats, both clean passes, all four depth
  publications and its zero-WARNING pin simultaneously.
- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_7``  L1457 ``20.0`` -> ``21.0``
  -> SOLE route: same leg.  Its clock steps EXACTLY the shipped 20.0 s per gated
  pass, so shipped beats twice; under ``21.0`` the first gate is short (and
  ``last_heartbeat`` never re-baselines), so it beats once - the heartbeat call
  list pins the difference.
- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_8``  L1462 ``if self._supervisor is
  not None:`` -> ``is None``
  -> measured ALL five legs.  With a supervisor present the flipped gate skips the arm
  (leg 2: zero beats and one clock read instead of three); with ``_supervisor is None``
  the flipped gate RUNS the arm, so the clock - scripted to the single baseline read
  shipped performs - is exhausted: the extra read raises ``StopIteration`` inside the
  shipped ``try`` and each leg's clean-pass / zero-WARNING / clock-read pin breaks
  (legs 1/3/5), while the failure leg's WARNING surface gains a second warning (leg 4).
- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_9``  L1469 ``detection_depth =
  await ...get_queue_length(DETECTION_QUEUE)`` -> ``= None``
- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_10`` L1469 arg -> ``None``
- ``xǁQueueMetricsWorkerǁ_run_loop__mutmut_11`` L1470 ``analysis_depth = ...``
  -> ``= None``
- ``xǁQueueMetricsWorkerǁrun_loop__mutmut_12`` L1470 arg -> ``None``
- ``xǁQueueMetricsWorkerǁrun_loop__mutmut_14`` L1473
  ``set_queue_depth("detection", detection_depth)`` -> depth ``None``
- ``xǁQueueMetricsWorkerǁrun_loop__mutmut_20`` L1474
  ``set_queue_depth("analysis", analysis_depth)`` -> depth ``None``
- ``xǁQueueMetricsWorkerǁrun_loop__mutmut_25`` L1476 DEBUG f-string arg -> ``None``
  -> ``test_two_clean_iterations_update_both_depths_and_log_the_success_debug``
  (queue-name ARGUMENTS pinned to the shipped constants, depths pinned to the
  injected 7/9 then 20/15 - every value distinct from ``None``, from the gauge
  default 0, and from the other queue's value - and the DEBUG text pinned
  character-for-character per pass), restated with a second value set (3/4 then
  11/12) by ``test_a_worker_without_a_supervisor_never_reads_the_clock`` and a
  third (6/8) by the failure leg, so the depth family is killed three times over.
- ``xǁQueueMetricsWorkerǁrun_loop__mutmut_26`` L1484 ``logger.warning(f"Failed
  to update queue metrics: {e}")`` -> ``logger.warning(None)``
  -> SOLE route: ``test_a_failing_depth_query_warns_the_shipped_text_and_the_loop_survives``
  (the ONLY leg whose shipped run reaches the ``except Exception`` arm; the
  loop-survival half - sleep with the worker's own interval on the failed pass, a
  clean second pass, no cancelled INFO - pins the control flow the warning
  travels with).

The arm the manifest lists separately
------------------------------------
(``test_a_cancelled_iteration_logs_the_cancelled_info_and_breaks``) states the
sibling ``asyncio.CancelledError`` arm - INFO + ``break``, zero sleeps, zero
publications - so the WARNING arm above cannot be satisfied by an accidental
fall-through from that handler.  Measured it is NOT a pure control: the banner,
exit-INFO and gate-flip families (m1-m4, m8, m9, m28-m31 - 11 keys) redden it too,
because the cancelled leg pins the ordered INFO triple and its own zero-
publication/zero-sleep surface.

Every leg above is the MEASURED failing set of the shadow-tree mutant run (each key
built from its exact survivor diff in a symlinked shadow of this tree, battery run
against it: 20/20 KILLED, and pristine green serially).

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it,
and every value an assertion depends on is injected by this file (the queue depths,
the clock script, the interval, the failure).

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  plus ``record.args`` / ``record.exc_info`` (batch27_01 pattern).
* Mocks of real attributes are autospec'd (WP4.2 fast path): the Redis client and
  the supervisor come from ``create_autospec(RedisClient)`` /
  ``create_autospec(WorkerSupervisor)``, and the ``set_queue_depth`` name that the
  shipped module holds by ``from ... import`` re-export is patched
  ``autospec=True`` through the LIVE name-resolution dict of the function under
  test (``patch_global``).  Patching ``backend.core.metrics.set_queue_depth``
  instead would leave ``M``'s own binding untouched, so that form is NOT used.
* The heartbeat clock is scripted by installing a ``MagicMock`` (whose ``time``
  reads a ``side_effect`` list) as the function's ``time_module`` GLOBAL through
  ``live_globals``; the shipped module attribute is never ``patch``-ed and no
  wall-clock duration is asserted.  Each leg scripts EXACTLY the reads the shipped
  body performs - one unconditional baseline read at L1456 plus one per gated pass
  - so a mutant that reads more exhausts the script and the ``StopIteration`` lands
  in the shipped ``except Exception`` as an unexpected WARNING, which every
  zero-WARNING pin rejects.  (The baseline read sits OUTSIDE the ``try``, so every
  leg scripts at least one clock value.)
* Termination is structural, not lucky: ``asyncio.sleep`` is patched
  ``autospec=True`` for the window of one leg and the spy counts passes - the
  shipped loop sleeps exactly once per pass on BOTH the success and the exception
  route - then flips ``worker._running`` so the shipped ``while`` test ends the
  loop.  A leg that must not sleep (the cancelled ``break``) scripts an unreachable
  pass count and relies on the shipped ``break``.  No mutant can hang this file:
  every pass ends at that sleep, and the ini ``timeout = 5`` bounds anything else.
* No import-time global spy; module-global access goes through ``live_globals``
  (three-worlds safe, proven in ``test_pipeline_workers_batch28_17.py`` /
  ``test_enrichment_pipeline_batch26_{11,20}.py``).
"""

from __future__ import annotations

import asyncio
import builtins
import logging
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, call, create_autospec, patch

import pytest

from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.redis import RedisClient
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import QueueMetricsWorker
from backend.services.worker_supervisor import WorkerSupervisor

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L1453: logger.info("QueueMetricsWorker loop started")
BANNER_INFO = "QueueMetricsWorker loop started"
# L1476-1478: logger.debug(f"Updated queue metrics: detection={detection_depth}, analysis={analysis_depth}")
METRICS_DEBUG_TPL = "Updated queue metrics: detection={}, analysis={}"
# L1481: logger.info("QueueMetricsWorker loop cancelled")
CANCELLED_INFO = "QueueMetricsWorker loop cancelled"
# L1484: logger.warning(f"Failed to update queue metrics: {e}")
FAILED_WARNING_TPL = "Failed to update queue metrics: {}"
# L1488: logger.info("QueueMetricsWorker loop exited")
EXIT_INFO = "QueueMetricsWorker loop exited"


# =============================================================================
# Observation helpers (batch27_01 pattern)
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
    """Assert the observable surface of one shipped f-string log call.

    ``record.msg`` is the RAW message.  Every shipped site in this group is an
    already-interpolated f-string or a constant, so ``args`` must stay empty (a
    moved or dropped message argument lands IN ``msg``) and ``exc_info`` must be
    absent (the shipped ``logger.warning(f"...{e}")`` carries the exception as
    interpolated TEXT only).
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for an f-string message: {r.args!r}"
    assert r.exc_info is None, (
        f"exc_info present where the shipped call passes none: {r.exc_info!r}"
    )


def pin_levels(caplog: pytest.LogCaptureFixture, msgs: list[str], level: int) -> None:
    """Pin the ordered, complete surface of ONE level for a whole leg."""
    recs = at(caplog, level)
    name = logging.getLevelName(level)
    assert [r.msg for r in recs] == msgs, (
        f"{name} surface mutated: {[r.msg for r in recs]} != {msgs}"
    )
    for r, msg in zip(recs, msgs, strict=True):
        pin_record(r, msg=msg, level=level)


def live_globals(fn: Any) -> dict[str, Any]:
    """Name-resolution dict of the LIVE function object (three-worlds safe).

    * Pristine repo: ``fn.__globals__ is M.__dict__`` (identity fast path).
    * ep_plugin red-check lane: the variant body is exec'd into a snapshot COPY
      of the module dict and carries no ``__wrapped__`` - that copy is exactly the
      dict the variant body reads, so return it.
    * ``mutants/`` re-bank home: mutmut 3.8 wraps every function in its
      trampoline, whose ``__globals__`` is mutmut's OWN module dict while the
      shipped implementation sits behind ``__wrapped__`` with globals ==
      ``M.__dict__``.  The identity guard fires only there.
    """
    g = fn.__globals__
    if g is not M.__dict__:
        w = getattr(fn, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return g


class _DictOwner:
    """Attribute facade over a module-globals dict for ``patch.object``."""

    def __init__(self, d: dict[str, Any]) -> None:
        self._d = d

    def __getattr__(self, name: str) -> Any:
        try:
            return self._d[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_d":
            super().__setattr__(name, value)
        else:
            self._d[name] = value

    def __delattr__(self, name: str) -> None:
        del self._d[name]


def patch_global(name: str, **kwargs: Any) -> Any:
    """``patch.object`` on the module the function under test resolves through.

    ``set_queue_depth`` reaches the loop via the shipped module's own
    ``from backend.core.metrics import set_queue_depth`` binding, so the patch has
    to land on THAT binding - inside the LIVE dict, which is the real module dict
    in the pristine/shadow worlds and the copy in the ep_plugin lane.
    """
    g = live_globals(M.QueueMetricsWorker._run_loop)
    if g is M.__dict__:
        return patch.object(M, name, **kwargs)
    return patch.object(_DictOwner(g), name, create=True, **kwargs)


# =============================================================================
# Harness
# =============================================================================


@dataclass
class Loop:
    """One scripted run of the shipped loop.

    ``steps`` is the iteration script - one element per pass, either a
    ``(detection, analysis)`` pair of depths or an ``Exception`` that the depth
    query raises.  ``passes`` is how many passes the leg expects: the
    ``asyncio.sleep`` spy stops the loop after that many, because the shipped loop
    sleeps exactly once per pass on BOTH the success and the exception route.
    """

    steps: list[Any]
    passes: int
    clock: list[float] = field(default_factory=lambda: [0.0])
    interval: float = 5.0
    supervisor: Any = None
    pass_index: int = 0
    calls_this_pass: int = 0
    queue_calls: list[Any] = field(default_factory=list)
    sleeps: list[float] = field(default_factory=list)
    clock_reads: int = 0

    def step(self) -> Any:
        """The scripted element for the pass in flight (one element per pass)."""
        if self.pass_index >= len(self.steps):
            raise AssertionError("the loop ran one iteration more than scripted")
        return self.steps[self.pass_index]

    def end_pass(self) -> None:
        """Called by the sleep spy: the shipped loop sleeps once per pass."""
        self.pass_index += 1
        self.calls_this_pass = 0


PASS_CEILING = 40


def make_worker(run_spec: Loop) -> Any:
    """Attribute-only ``self`` for the real coroutine, on an autospec'd instance.

    ``create_autospec(QueueMetricsWorker)`` enforces every method signature; its
    ``_run_loop`` AsyncMock is NEVER awaited - every leg calls the shipped function
    object directly.  Only the five data attributes the loop reads are installed:
    ``_redis`` (an autospec'd Redis client whose ``get_queue_length`` serves the
    script POSITIONALLY - the first call of a pass yields the detection depth, the
    second the analysis depth, so an argument mutant still gets a plausible value
    and the failure surfaces only on the pinned queue-name argument), ``_running``
    (the stop switch the sleep spy flips), ``_update_interval``, ``_supervisor``
    and ``_worker_name``.
    """
    worker = create_autospec(QueueMetricsWorker).return_value
    redis = create_autospec(RedisClient).return_value

    async def get_queue_length(queue_name: str) -> Any:
        if len(run_spec.queue_calls) > 8 * PASS_CEILING:
            # Harness guard, far above any shipped count (this group queries at
            # most 4 times): an unbounded mutant spin surfaces as a bounded
            # RuntimeError -> shipped WARNING -> the pins go red, instead of
            # burning the 5 s ini timeout.
            raise RuntimeError("the loop queried the queues more times than any shipped path can")
        run_spec.queue_calls.append(queue_name)
        step = run_spec.step()
        if isinstance(step, BaseException):
            # BaseException, not Exception: the control leg scripts a real
            # asyncio.CancelledError, which is a BaseException on py3.8+.
            raise step
        index = run_spec.calls_this_pass
        run_spec.calls_this_pass += 1
        if index >= len(step):
            raise AssertionError(f"a pass queries {len(step)} queues, not {index + 1}")
        return step[index]

    redis.get_queue_length.side_effect = get_queue_length
    worker._redis = redis
    worker._running = True
    worker._update_interval = run_spec.interval
    worker._supervisor = run_spec.supervisor
    worker._worker_name = "metrics"
    return worker


async def drive(run_spec: Loop) -> Any:
    """Run the shipped ``_run_loop`` for exactly ``run_spec.passes`` passes.

    * ``asyncio.sleep`` is patched ``autospec=True`` for the window: the spy
      records the interval, ends the scripted pass, and once the scripted pass
      count is reached flips ``worker._running`` so the shipped ``while`` ends.
    * ``time_module`` is installed in the loop's own live globals as a MagicMock
      reading ``clock`` verbatim; the leg then asserts how many reads the shipped
      body actually needed.
    """
    worker = make_worker(run_spec)
    g = live_globals(M.QueueMetricsWorker._run_loop)
    saved_time = g.get("time_module")
    time_mock = MagicMock(name="time-module")
    time_mock.time = MagicMock(name="time", side_effect=list(run_spec.clock))
    g["time_module"] = time_mock

    async def spy_sleep(delay: float, *args: Any, **kwargs: Any) -> None:
        run_spec.sleeps.append(delay)
        run_spec.end_pass()
        if len(run_spec.sleeps) >= min(run_spec.passes, PASS_CEILING):
            worker._running = False

    try:
        with patch("asyncio.sleep", autospec=True, side_effect=spy_sleep):
            await M.QueueMetricsWorker._run_loop(worker)
    finally:
        g["time_module"] = saved_time
    run_spec.clock_reads = time_mock.time.call_count
    return worker


def supervisor_double() -> Any:
    """autospec'd instance double of the shipped ``WorkerSupervisor``."""
    return create_autospec(WorkerSupervisor).return_value


# =============================================================================
# 1) two clean iterations: depths, labels, success DEBUG, banner + exit INFO
#    (m9, m10, m11, m12, m14, m20, m25; the INFO pins also kill m1-m4 and m28-m31)
# =============================================================================


async def test_two_clean_iterations_update_both_depths_and_log_the_success_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1451-1488 over two passes, then the ``while`` test ends the loop.

    ::

        logger.info("QueueMetricsWorker loop started")
        last_heartbeat = time_module.time()
        heartbeat_interval = 20.0
        while self._running:
            try:
                if self._supervisor is not None: ...   # -> legs 2 and 3
                detection_depth = await self._redis.get_queue_length(DETECTION_QUEUE)
                analysis_depth = await self._redis.get_queue_length(ANALYSIS_QUEUE)
                set_queue_depth("detection", detection_depth)
                set_queue_depth("analysis", analysis_depth)
                logger.debug(
                    f"Updated queue metrics: detection={detection_depth}, analysis={analysis_depth}"
                )
            except asyncio.CancelledError: ...         # -> leg 5
            except Exception as e: ...                 # -> leg 4
            await asyncio.sleep(self._update_interval)
        logger.info("QueueMetricsWorker loop exited")

    Seven keys sit on this window.  Every injected depth is distinct from ``None``,
    from the gauge default 0 and from the other queue's value (7 / 9 then 20 / 15),
    so a ``None``-substituted depth (m9, m11) or published depth (m14, m20) can
    never alias a real one.  The queue-name ARGUMENTS are pinned to the shipped
    constants (m10, m12); the DEBUG text is pinned character-for-character per pass
    (m25); the ordered INFO pair kills the banner family (m1-m4) and the exit
    family (m28-m31).  ``_supervisor`` is ``None``, so the shipped gate performs
    exactly one clock read - the unconditional baseline at L1456 - and the leg
    scripts exactly that one value.
    """
    spec = Loop(steps=[(7, 9), (20, 15)], passes=2, clock=[0.0], interval=4.25, supervisor=None)
    win(caplog)

    with patch_global("set_queue_depth", autospec=True) as set_depth:
        worker = await drive(spec)

    assert worker._redis.get_queue_length.await_count == 4, (
        f"the loop queried the queues {worker._redis.get_queue_length.await_count} times, expected 4"
    )
    assert spec.queue_calls == [DETECTION_QUEUE, ANALYSIS_QUEUE, DETECTION_QUEUE, ANALYSIS_QUEUE], (
        f"queue-name arguments mutated: {spec.queue_calls!r}"
    )
    assert set_depth.call_count == 4, f"set_queue_depth called {set_depth.call_count} times"
    assert set_depth.call_args_list == [
        call("detection", 7),
        call("analysis", 9),
        call("detection", 20),
        call("analysis", 15),
    ], f"depth publications mutated: {set_depth.call_args_list!r}"
    for c in set_depth.call_args_list:
        assert c.args and not c.kwargs, f"set_queue_depth is called positionally: {c!r}"

    pin_levels(
        caplog, [METRICS_DEBUG_TPL.format(7, 9), METRICS_DEBUG_TPL.format(20, 15)], logging.DEBUG
    )
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [BANNER_INFO, EXIT_INFO], logging.INFO)
    assert spec.sleeps == [4.25, 4.25], (
        f"one sleep per pass with the worker's own interval: {spec.sleeps!r}"
    )
    assert spec.clock_reads == 1, (
        f"the baseline read at L1456 is the only read when there is no supervisor: "
        f"{spec.clock_reads} reads"
    )


# =============================================================================
# 2) the supervisor heartbeat gate (m5, m6, m7, m8)
# =============================================================================


async def test_the_heartbeat_fires_once_per_shipped_20_second_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1456-1466 - one ``record_heartbeat`` per 20.0 s of clock advance.

    ::

        last_heartbeat = time_module.time()      # clock[0] = 0.0
        heartbeat_interval = 20.0                # the shipped constant
        while self._running:
            try:
                if self._supervisor is not None:
                    now = time_module.time()     # clock[1] = 20.0, clock[2] = 40.0
                    if now - last_heartbeat >= heartbeat_interval:
                        self._supervisor.record_heartbeat(self._worker_name)
                        last_heartbeat = now

    The scripted clock steps EXACTLY the shipped interval, so shipped beats once per
    gated pass - two beats for two passes - while ``21.0`` (m7) fires at most once
    (its gate never re-baselines, so the second pass still measures from 0.0 and
    ``40.0 - 0.0 >= 21.0`` is the only one that passes... which it does not, because
    the FIRST pass is what the ``[call("metrics"), call("metrics")]`` pin sees).
    This is the ONLY leg whose shipped run evaluates the comparison, so it is the
    only place a ``None`` operand is observable: m5's ``last_heartbeat`` and m6's
    ``heartbeat_interval`` both raise ``TypeError`` inside the shipped ``try``,
    wiping BOTH beats, both clean passes, all four publications and the
    zero-WARNING pin at once.  m8's flip skips the arm for a present supervisor:
    zero beats and a single clock read.
    """
    supervisor = supervisor_double()
    spec = Loop(
        steps=[(1, 2), (6, 8)],
        passes=2,
        clock=[0.0, 20.0, 40.0],
        interval=3.5,
        supervisor=supervisor,
    )
    win(caplog)

    with patch_global("set_queue_depth", autospec=True) as set_depth:
        await drive(spec)

    assert supervisor.record_heartbeat.call_args_list == [call("metrics"), call("metrics")], (
        f"heartbeat contract mutated: {supervisor.record_heartbeat.call_args_list!r}"
    )
    assert spec.clock_reads == 3, (
        f"shipped reads the clock once for the baseline plus once per gated pass: "
        f"{spec.clock_reads} reads"
    )
    pin_levels(caplog, [], logging.WARNING)
    assert set_depth.call_args_list == [
        call("detection", 1),
        call("analysis", 2),
        call("detection", 6),
        call("analysis", 8),
    ], f"depth publications mutated: {set_depth.call_args_list!r}"
    pin_levels(
        caplog,
        [METRICS_DEBUG_TPL.format(1, 2), METRICS_DEBUG_TPL.format(6, 8)],
        logging.DEBUG,
    )
    pin_levels(caplog, [BANNER_INFO, EXIT_INFO], logging.INFO)
    assert spec.sleeps == [3.5, 3.5], spec.sleeps


# =============================================================================
# 3) the gate is ``is not None`` (second route to m8, second value set for depths)
# =============================================================================


async def test_a_worker_without_a_supervisor_never_reads_the_clock(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1462 - with NO supervisor the gate body must not run at all.

    Second, independently-valued route to the depth family (3/4 then 11/12) and the
    leg that reads m8 from the other side: under the flipped gate the arm RUNS for a
    ``None`` supervisor, so it consumes a second clock value the leg never scripted
    (only the shipped baseline read is scripted), the ``StopIteration`` lands in the
    shipped ``except Exception``, and the four publications, both DEBUGs, the
    zero-WARNING pin and the single-read pin below all break together.
    """
    spec = Loop(steps=[(3, 4), (11, 12)], passes=2, clock=[0.0], interval=1.25, supervisor=None)
    win(caplog)

    with patch_global("set_queue_depth", autospec=True) as set_depth:
        await drive(spec)

    assert spec.queue_calls == [DETECTION_QUEUE, ANALYSIS_QUEUE, DETECTION_QUEUE, ANALYSIS_QUEUE], (
        f"queue-name arguments mutated: {spec.queue_calls!r}"
    )
    assert set_depth.call_args_list == [
        call("detection", 3),
        call("analysis", 4),
        call("detection", 11),
        call("analysis", 12),
    ], f"depth publications mutated: {set_depth.call_args_list!r}"
    pin_levels(
        caplog,
        [METRICS_DEBUG_TPL.format(3, 4), METRICS_DEBUG_TPL.format(11, 12)],
        logging.DEBUG,
    )
    pin_levels(caplog, [], logging.WARNING)
    assert spec.clock_reads == 1, (
        f"a None supervisor must not read the clock past the baseline: {spec.clock_reads} reads"
    )
    assert spec.sleeps == [1.25, 1.25], spec.sleeps
    pin_levels(caplog, [BANNER_INFO, EXIT_INFO], logging.INFO)


# =============================================================================
# 4) the ``except Exception`` arm (sole route to m26)
# =============================================================================


async def test_a_failing_depth_query_warns_the_shipped_text_and_the_loop_survives(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1483-1486 - ``except Exception`` warns, sleeps, and iterates again.

    ::

            except Exception as e:
                logger.warning(f"Failed to update queue metrics: {e}")

            await asyncio.sleep(self._update_interval)

        logger.info("QueueMetricsWorker loop exited")

    The failure is injected into the FIRST ``get_queue_length`` of pass 1 (the
    scripted pair is replaced by a ``ConnectionError``); pass 2 then runs clean.
    ``e`` is interpolated into the message, so the WARNING text is pinned
    character-for-character - m26's ``logger.warning(None)`` cannot satisfy it - and
    the survival half (a sleep with the worker's own interval ON THE FAILED PASS,
    the clean pass's publication pair and DEBUG, and no cancelled INFO) pins the
    control flow the warning travels with.  ``_supervisor`` is ``None``, so the
    injected error is the ONLY thing that can warn in this leg.
    """
    err = builtins.ConnectionError("redis connection reset by peer")
    spec = Loop(steps=[err, (6, 8)], passes=2, clock=[0.0], interval=2.5, supervisor=None)
    win(caplog)

    with patch_global("set_queue_depth", autospec=True) as set_depth:
        await drive(spec)

    pin_levels(caplog, [FAILED_WARNING_TPL.format(err)], logging.WARNING)
    assert spec.queue_calls == [DETECTION_QUEUE, DETECTION_QUEUE, ANALYSIS_QUEUE], (
        f"pass 1 dies at the detection query, pass 2 queries both: {spec.queue_calls!r}"
    )
    assert set_depth.call_args_list == [call("detection", 6), call("analysis", 8)], (
        f"the pass after a failure must publish both depths: {set_depth.call_args_list!r}"
    )
    pin_levels(caplog, [METRICS_DEBUG_TPL.format(6, 8)], logging.DEBUG)
    assert spec.sleeps == [2.5, 2.5], (
        f"the loop sleeps with its own interval on the FAILED pass too: {spec.sleeps!r}"
    )
    pin_levels(caplog, [BANNER_INFO, EXIT_INFO], logging.INFO)


# =============================================================================
# 5) control: the ``asyncio.CancelledError`` arm (no survivor sits there)
# =============================================================================


async def test_a_cancelled_iteration_logs_the_cancelled_info_and_breaks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1480-1482 - the sibling handler: INFO + ``break``, no sleep, no warn.

    Stated so leg 4's WARNING pin cannot be satisfied by an accidental fall-through
    from this arm: the cancelled INFO text is DIFFERENT from the exit INFO, the
    ``break`` skips the trailing ``await asyncio.sleep(...)`` (zero sleeps recorded
    - the ``break``, not the spy, ends the loop: ``passes`` is unreachable), no depth
    is published and nothing warns.
    """
    spec = Loop(
        steps=[asyncio.CancelledError()],
        passes=10**6,
        clock=[0.0],
        interval=7.75,
        supervisor=None,
    )
    win(caplog)

    with patch_global("set_queue_depth", autospec=True) as set_depth:
        await drive(spec)

    assert spec.queue_calls == [DETECTION_QUEUE], spec.queue_calls
    assert set_depth.call_args_list == [], "a cancelled pass publishes nothing"
    assert spec.sleeps == [], "the break skips the trailing sleep"
    assert spec.clock_reads == 1, spec.clock_reads
    pin_levels(caplog, [BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_levels(caplog, [], logging.DEBUG)
    pin_levels(caplog, [], logging.WARNING)
