"""S3 batch-28 lane 09b - ``pipeline_workers`` group g11 kill battery (50 keys).

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
``manifest.json`` group 11 ("g11 AnalysisQueueWorker._run_loop", 49 KILLABLE /
1 EQUIVALENT), plus ``group_11.keys`` and ``survivors.json`` for the exact per-key
diffs.  The lane's other half - g09, the 72 keys of ``BatchTimeoutWorker._run_loop`` -
is ``test_pipeline_workers_batch28_09.py``; the file split is the <= 80-tests rule.

All 50 keys sit on ``AnalysisQueueWorker._run_loop`` (shipped lines 888-976).  Every
leg drives the REAL coroutine - ``await M.AnalysisQueueWorker._run_loop(worker)`` is
the shipped function object called with an attribute-only ``self``, never an
autospec'd double of the loop.  Termination is scripted: the last pass of every leg
raises ``asyncio.CancelledError`` from the queue/stream read, so the shipped ``break``
(L958) ends the drive.

The EQUIVALENT key (UPHELD - no test needed, per the manifest's PER-KEY EXCEPTIONS)
-------------------------------------------------------------------------------
``xǁAnalysisQueueWorkerǁ_run_loop__mutmut_3`` - L892
``stream_service: AnalysisStreamService | None = None`` -> ``= ""``.  DEAD
DECLARATION: the binding is WRITTEN at L892 and re-WRITTEN unconditionally at L896 on
the only path that reads it (L895 ``if use_streams:`` gates both the write and any
truthy ``use_streams`` reaching L921), so the initialiser's value is never observed -
and on the ``use_streams`` falsy path L921 short-circuits on ``use_streams`` before
the ``stream_service is not None`` conjunct, so ``""`` (also falsy, but NOT ``None``,
so even a bare ``is not None`` read would not route it into the streams arm) is
behaviourally identical to ``None`` at every reachable read.  No shipped-behaviour
assert can separate them; it is reported as uncovered-by-design, not faked.

Test -> mutant-key map
======================
Occurrence-twin check: each g11 diff ``(before, after, line)`` tuple was searched
across all 959 survivors - no pair occurs anywhere else, so NO twin keys are carried
here and none is claimed by another group.

- ``xǁAnalysisQueueWorkerǁ_run_loop__mutmut_8/_10/_12/_13/_14`` L897-898
  ``logger.info("AnalysisQueueWorker loop started (Redis Streams mode)", ...)`` ->
  message ``None`` / message drop / ``"XX..XX"`` / lower / upper, and
  ``_9/_11/_15/_16`` L899 ``extra={"consumer_name": consumer_name}`` -> ``extra=None``
  / the ``extra`` drop / the two key renames
  -> ``test_streams_mode_builds_the_service_announces_the_consumer_and_consumes`` (the
  SOLE leg whose shipped run takes the ``if use_streams:`` arm at L895, so this banner
  exists nowhere else) - message AND payload pinned together, and the payload VALUE is
  ``f"analysis-worker-{id(worker)}"``, which is also what kills m4 (``consumer_name =
  None``) and m5 (``id(None)``) alongside the consume-call argument pin.
- ``..._mutmut_2`` L891 ``use_streams = settings.use_redis_streams`` -> ``= None``
  -> the same streams leg, read from the OTHER side: a ``None`` flag is falsy, so the
  banner becomes the legacy one, the factory is never awaited and the loop falls into
  the BLPOP arm - which the leg's ``consume_batches`` / factory / legacy-never-called
  pins all reject simultaneously.  ``..._mutmut_6`` L896 ``stream_service = await
  get_analysis_stream_service(...)`` -> ``= None`` dies the same way (L921's
  ``stream_service is not None`` conjunct sends the loop legacy, so the consume-call
  pin goes empty).  ``..._mutmut_7`` L896 factory ARGUMENT -> ``None`` is killed only
  by the factory-argument IDENTITY pin.
- ``..._mutmut_28/_29`` L921 ``if use_streams and stream_service is not None:`` ->
  ``or`` / ``stream_service is None``
  -> ``test_streams_mode_without_a_service_object_still_uses_the_legacy_queue``, the one
  drive where the two conjuncts DISAGREE (``use_streams`` True, the factory returned
  ``None``): the shipped conjunction takes the LEGACY arm, while both mutants take the
  streams arm and call ``None.consume_batches(...)`` - an ``AttributeError`` every
  iteration, so their ERROR/sleep surface breaks this leg's zero-error and sleep pins.
  The same leg restates the shipped conjunction from the legacy leg's side too (a truthy
  service object plus a falsy flag must still read the BLPOP queue).
- ``..._mutmut_34/_35/_37`` L935-937 ``consume_batches(consumer_name, count=1,
  block=True)`` -> ``None`` consumer / ``count=None`` / the dropped positional
  -> the streams leg pins the EXACT call record, positional AND keywords.
- ``..._mutmut_25`` L910 ``claim_interval = 30.0`` -> ``None``, ``_30`` L923 ``now =
  time_module.time()`` -> ``= None``, ``_31``/``_32`` L924 ``now - last_claim_check >=
  claim_interval`` -> ``now + last_claim_check`` / ``>``
  -> ``test_the_stale_claim_gate_fires_once_per_shipped_30_second_step``.  Its
  heartbeat alias starts at ``1000.0`` - deliberately NOT ``0.0``, because at a zero
  baseline ``now - last`` and ``now + last`` coincide and m31 would be unobservable.
  Pass 1 reads ``1000.0`` again (``elapsed`` 0): shipped does NOT claim, m31 DOES
  (``1000.0 + 1000.0 >= 30.0``).  Pass 2 reads ``1030.0`` (``elapsed`` EXACTLY 30.0):
  shipped's ``>=`` claims, m32's ``>`` does not.  A ``None`` operand (m25/m30) raises
  ``TypeError`` inside the shipped ``try`` and lands in the error arm, which the
  zero-error pins see.  The same leg pins the claim ARGUMENTS and the DLQ / process /
  acknowledge routing of what the claim returns, so the streams arm cannot be entered
  by a mutant without its work being checked.
- ``..._mutmut_21/_22/_23/_27`` L905 ``last_heartbeat = time_module.time()`` ->
  ``None``, L906 ``heartbeat_interval = 20.0`` -> ``None`` / ``21.0``, L915
  ``if self._supervisor is not None:`` -> ``is None``
  -> ``test_the_analysis_heartbeat_fires_once_per_shipped_20_second_step`` (legacy mode, so the
  claim gate cannot confuse the read count: shipped reads the alias once for the
  L905 baseline plus once per iteration at L916) and
  ``test_an_unsupervised_analysis_worker_never_reads_the_heartbeat_clock`` (m27 from the
  other side).
- ``..._mutmut_44/_45/_46/_48`` L946-949 the BLPOP read: the whole call -> ``item =
  None`` / queue name -> ``None`` / ``timeout=None`` / the ``timeout`` line dropped
  -> the legacy leg pins ``await_args_list`` exactly - four calls of
  ``call(queue_name, timeout=poll_timeout)`` with the worker's OWN attribute values.
- ``..._mutmut_49`` L951 ``if item is None:`` -> ``is not None``, ``_50`` L952
  ``continue`` -> ``break``, ``_51`` L954 ``_process_analysis_item(item)`` -> ``(None)``
  -> the legacy leg alternates item / idle / item, so the flip and the break are both
  visible (an idle pass must loop again WITHOUT processing and without leaving the
  loop) and the processed-item pin asserts IDENTITY of the dict the read returned,
  which a ``None`` argument cannot satisfy.
- ``..._mutmut_52/_53/_54`` L957 ``logger.info("AnalysisQueueWorker loop cancelled")``
  -> ``None`` / ``XX..XX`` / lower and ``_56`` L958 ``break`` -> ``return``
  -> the cancelled control leg pins the ordered INFO triple
  ``[banner, cancelled, exited]``: under m56 the ``return`` skips L973's exit INFO, and
  the three message variants each fail the equality pin.
- ``..._mutmut_57/_58`` L960 ``self._stats.errors += 1`` -> ``= 1`` / ``-= 1``,
  ``_60`` L961 ``state = WorkerState.ERROR`` -> ``None``, and ``_61``-``_65`` L963
  ``error_type = categorize_exception(e, "analysis")`` -> ``= None`` /
  ``categorize_exception(None, "analysis")`` / ``(e, None)`` / ``("analysis")`` /
  ``(e, )``
  -> the two error legs pin ``errors`` ACROSS two failures (shipped 1 then 2), the
  state read INSIDE the ``record_pipeline_error`` call window (the only place L961 is
  observable - m60 makes the shipped ``WorkerStats.to_dict()`` raise ``AttributeError``
  right there), the ERROR payload's ``{"error_count", "error_type"}`` pair, and
  ``record_pipeline_error`` called with the EXACT shipped label
  ``"analysis_connection_error"`` - which exists only when BOTH categorizer arguments
  are shipped (m61 ``None``, m62 ``"analysis_processing_error"``, m63
  ``"None_connection_error"``, and the ``"None_connection_error"`` / mis-shaped
  variants).  m64 and m65 are calls that drop a REQUIRED argument, so the shipped
  handler itself raises ``TypeError`` straight out of ``_run_loop`` - measured as an
  errored test, not a silently-passing one.

Every leg above is the MEASURED failing set of the shadow-tree mutant run (each key
built from its exact survivor diff in a symlinked shadow of this tree, battery run
against it: 49/49 KILLED + m3 upheld EQUIVALENT, and pristine green serially and
co-run with ``test_pipeline_workers_batch28_17.py``).

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it, and
every value an assertion depends on is injected by this file (the settings flag, the
queue items, the stream messages, the clock scripts, the failures).

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``, then
  filtered to this module's logger name), read the RAW ``record.msg`` plus
  ``record.args`` / ``record.exc_info`` / ``record.levelno``, and read ``extra``
  payloads as the record attributes the shipped ``Logger.makeRecord`` added beyond the
  ``LogRecord`` core plus this module's ``ContextFilter`` contributions.
* Mocks of real attributes are autospec'd (WP4.2 fast path) and installed with
  ``new=``: ``get_settings``, ``get_analysis_stream_service`` (this module's
  ``from backend.services.redis_streams import ...`` binding, L69-74 - patching the
  origin module would leave ``M``'s own binding live), ``record_pipeline_error`` and
  ``asyncio.sleep``.  Injected collaborators (Redis client, the stream service, the
  supervisor) are attributes of a ``create_autospec(AnalysisQueueWorker)`` INSTANCE
  double, never patch sites, and the autospec'd ``_run_loop`` on that double is NEVER
  awaited.
* ``self._process_analysis_item`` is replaced by an ``AsyncMock`` INSTANCE attribute:
  a replay mutant re-sources the class, so a class-level patch would sail past it,
  while an instance attribute wins in every world.
* The heartbeat / claim clock is the module-level ``time_module`` alias (L33, read at
  L905 / L909 / L916 / L923) and is installed with ``patch.object(M, "time_module",
  new=...)`` - a scripted stepper, never an attribute patch of the real ``time``
  module.  ``time.monotonic`` / ``time.perf_counter`` are never patched and never
  asserted.
* Termination is structural: every leg's last pass raises ``CancelledError`` from the
  read the loop performs exactly once per iteration, so the shipped ``break`` ends the
  drive; the pass index advances on that read (NOT on a sleep - the streams arm and
  the idle legacy pass never sleep), and a mutant that iterates past the script gets a
  loud ``AssertionError`` inside the shipped ``try`` instead of riding the 5 s ini
  timeout.
* No import-time global spy: every double is installed inside the leg that uses it,
  module-global access goes through ``live_globals`` (three-worlds safe), and the only
  import-time capture is the real ``asyncio.sleep`` FUNCTION OBJECT, so the injected
  stubs can yield without recursing.
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import logging
import time as real_time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, call, create_autospec, patch

import pytest

from backend.core.config import Settings
from backend.core.constants import ANALYSIS_QUEUE
from backend.core.redis import RedisClient
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import AnalysisQueueWorker, WorkerStats
from backend.services.redis_streams import AnalysisStreamMessage, AnalysisStreamService
from backend.services.worker_supervisor import WorkerSupervisor

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]

# The real asyncio.sleep, captured at import time so this file's injected stubs can
# yield control to the loop without recursing into themselves.
_REAL_SLEEP = asyncio.sleep


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L897-900: logger.info("AnalysisQueueWorker loop started (Redis Streams mode)",
#                       extra={"consumer_name": consumer_name})
STREAMS_BANNER_INFO = "AnalysisQueueWorker loop started (Redis Streams mode)"
# L902: logger.info("AnalysisQueueWorker loop started")
LEGACY_BANNER_INFO = "AnalysisQueueWorker loop started"
# L957: logger.info("AnalysisQueueWorker loop cancelled")
CANCELLED_INFO = "AnalysisQueueWorker loop cancelled"
# L973-975: logger.info("AnalysisQueueWorker loop exited",
#                       extra={"items_processed": self._stats.items_processed})
EXIT_INFO = "AnalysisQueueWorker loop exited"
# L966: f"Error in AnalysisQueueWorker loop: {e}"
ERROR_INFO_TPL = "Error in AnalysisQueueWorker loop: {}"
# L963 categorize_exception(<ConnectionError>, "analysis") -> the L164-167 name tuple
# fires first, so the shipped label is f"{worker_name}_connection_error".
ERROR_LABEL = "analysis_connection_error"
# L925: await stream_service.claim_stale_messages(consumer_name, count=5)
CLAIM_COUNT = 5
# L928: await stream_service.move_to_dlq(msg, "max_delivery_exceeded")
DLQ_REASON = "max_delivery_exceeded"
# L927 compares the message's delivery_count against stream_service._max_delivery_count;
# this leg injects that threshold so its two sides are both exercised.
DLQ_THRESHOLD = 3
# WorkerState values as the shipped WorkerStats.to_dict() renders them (L212-219); a
# fresh WorkerStats starts STOPPED (L210).
STATE_STOPPED = "stopped"
STATE_RUNNING = "running"
STATE_ERROR = "error"

# The queue name / BLPOP timeout the shipped constructor defaults give (L782, L783),
# restated only so a leg can assert its own injected value is NOT the one used.
SHIPPED_QUEUE_NAME = ANALYSIS_QUEUE


# =============================================================================
# Observation helpers (batch27_01 / batch28_13 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped f-string / constant log call.

    ``record.msg`` is the RAW message and ``args`` must stay empty (every shipped site
    here is an already-interpolated f-string or a constant).  ``exc_info`` is pinned
    separately by the legs that reach the L965-969 ERROR call.
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
    (b) the fields this module's ``ContextFilter`` injects - (b) MEASURED, since the
    filter is idempotent, so running it over a record it has already seen adds exactly
    the injected names once.  ``message`` is excluded: the formatter sets it.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The ``extra=`` dict the shipped call passed, as the record shows it."""
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

    Pristine / replay shadow: ``fn.__globals__ is M.__dict__``.  ep_plugin lane: the
    snapshot COPY the variant body reads.  ``mutants/`` home: the mutmut trampoline's
    ``__globals__`` differs while the shipped body behind ``__wrapped__`` points at
    ``M.__dict__`` - the identity guard fires only there.
    """
    g = fn.__globals__
    if g is not M.__dict__:
        w = getattr(fn, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return g


def autospec_of(target: Any) -> Any:
    """One double, visibly ``create_autospec``'d from a shipped callable (WP4.2)."""
    return create_autospec(target)


# =============================================================================
# The heartbeat / claim clock - the module-level ``time_module`` alias (L33)
# =============================================================================


class ConstantTimeModule:
    """The ``time_module`` alias pinned to one value: nothing gated by it fires.

    ``now - baseline`` is ``0.0``, so neither the 20 s heartbeat nor the 30 s claim
    gate opens - which is what keeps a consume/legacy leg owned by its own keys.
    ``reads`` is still counted and pinned: it is the observable that catches a removed
    read, an added read and both gate flips.
    """

    def __init__(self, value: float = 500.0, *_ignored: float) -> None:
        self.value = value
        self.reads = 0

    def time(self) -> float:
        self.reads += 1
        return self.value

    def __getattr__(self, name: str) -> Any:
        return getattr(real_time, name)


class ScriptedTimeModule:
    """The ``time_module`` alias answering from an explicit per-read script.

    ``time()`` returns ``steps[i]`` for read ``i`` and repeats the last value, so a leg
    can step the clock by exactly the shipped heartbeat / claim period per iteration and
    pin the read count alongside the behaviour.
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
    """One scripted iteration.

    ``item`` is what the queue read returns (a dict for a real item, ``None`` for an
    idle BLPOP timeout); ``messages`` is what ``consume_batches`` returns; ``claims`` is
    what ``claim_stale_messages`` returns, with ``None`` meaning THIS pass must not ask
    the gate at all (the stub then raises loudly); ``raises`` replaces the read's result
    with a failure - a plain ``Exception`` for the error arm, ``asyncio.CancelledError``
    as the sentinel that ends the drive through the shipped ``break``.
    """

    item: Any = None
    messages: list[Any] = field(default_factory=list)
    claims: list[Any] | None = None
    raises: BaseException | None = None


@dataclass
class Run:
    """One scripted drive, its clock script, and everything it observed.

    ``clock`` is the script handed to ``clock_kind`` - the object installed as the
    shipped module's ``time_module`` alias.  A one-element script (the
    ``ConstantTimeModule`` legs) freezes the clock so neither gate opens; a multi-element
    script (``ScriptedTimeModule``) answers read ``i`` with ``clock[i]`` and then repeats
    its last value.  The shipped body reads the alias at L905 (``last_heartbeat``) and
    L909 (``last_claim_check``) up front, then at L916 once per iteration when a
    supervisor is present and at L923 once per iteration in streams mode - so the read
    COUNT is pinned too.
    """

    passes: list[Pass]
    clock: list[float] = field(default_factory=lambda: [0.0])
    clock_kind: Any = ConstantTimeModule
    use_streams: bool = False
    build_service: bool = True
    supervisor: Any = None
    queue_name: str = "analysis_queue-b28"
    poll_timeout: int = 3
    hb_module: Any = None
    calls: int = 0
    sleeps: list[float] = field(default_factory=list)
    sleep_limit: int = 5
    states_at_error_call: list[str | None] = field(default_factory=list)

    def heartbeat_reads(self) -> int:
        """``time_module.time()`` reads the shipped body actually made."""
        assert self.hb_module is not None, "the drive has not run yet"
        return self.hb_module.reads

    def next_pass(self) -> Pass:
        """The scripted pass in flight.

        The shipped body performs the driving read (L925 claim / L935 consume / L946
        BLPOP) exactly ONCE per iteration, so a NEW call means a NEW pass.  Advancing on
        a SLEEP would be wrong: the streams arm and the idle legacy pass never sleep.
        A mutant that iterates past the script gets a loud ``AssertionError`` inside the
        shipped ``try``, which reddens the leg's pinned INFO / stats surface.
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

    ``create_autospec(AnalysisQueueWorker)`` enforces every method signature; its
    ``_run_loop`` AsyncMock is NEVER awaited.  Every attribute the loop resolves through
    ``self`` is this file's, carrying the values the pins assert: ``_redis`` is an
    autospec'd ``RedisClient`` whose ``get_from_queue`` serves the item script,
    ``_queue_name`` / ``_poll_timeout`` are the leg's own (deliberately NOT the shipped
    defaults, so an argument mutation cannot alias them), ``_worker_name`` is the shipped
    constructor default (L786), ``_stats`` a real shipped ``WorkerStats()`` and
    ``_process_analysis_item`` an instance-level ``AsyncMock`` spy - an instance
    attribute beats the class attribute in every world, including a replay mutant's
    re-sourced class.
    """
    worker = create_autospec(AnalysisQueueWorker).return_value
    redis = create_autospec(RedisClient).return_value

    async def get_from_queue(*args: Any, **kwargs: Any) -> Any:
        if run.calls > PASS_CEILING:
            raise RuntimeError("the loop iterated more times than any shipped path can")
        scripted_pass = run.next_pass()
        await _REAL_SLEEP(0)  # a real yield point, so no driver can spin
        if scripted_pass.raises is not None:
            raise scripted_pass.raises
        return scripted_pass.item

    redis.get_from_queue.side_effect = get_from_queue
    worker._redis = redis
    worker._analyzer = create_autospec(M.NemotronAnalyzer).return_value
    worker._queue_name = run.queue_name
    worker._poll_timeout = run.poll_timeout
    worker._stop_timeout = 30.0
    worker._supervisor = run.supervisor
    worker._worker_name = "analysis"
    worker._running = True
    worker._task = None
    worker._stats = WorkerStats()
    worker._broadcaster = None
    # The instance-level AsyncMock is the processing spy.  Its recorded call ARGS carry
    # the exact object the shipped call passed, so a leg can pin both the VALUE
    # (``call(expected_dict)``) and the IDENTITY (``.args[0] is expected_dict``) - the
    # latter is what an ``_process_analysis_item(None)`` mutation cannot satisfy.
    worker._process_analysis_item = AsyncMock(name="process-analysis-item")
    return worker


def make_stream_service(run: Run) -> Any:
    """autospec'd ``AnalysisStreamService`` instance serving the stream script.

    ``_max_delivery_count`` is set to a real int (L927 compares the message's
    ``delivery_count`` against it), and every read yields to the loop.

    ``claim_stale_messages`` does NOT advance the pass index - the shipped gate (L924)
    opens at most once per iteration and the iteration's own read (L935) is what marks a
    new pass.  The pass' ``claims`` field is the answer, and ``None`` means this pass
    must not reach the gate: the stub then raises inside the shipped ``try``, which
    reddens the leg's zero-error pins.
    """
    service = create_autospec(AnalysisStreamService).return_value
    service._max_delivery_count = DLQ_THRESHOLD

    async def claim_stale_messages(*args: Any, **kwargs: Any) -> list[Any]:
        # The shipped gate runs BEFORE this iteration's own consume read, so the pass in
        # flight is index `run.calls` - NOT `run.calls - 1`, which is the previous pass.
        index = run.calls
        claims = run.passes[index].claims if 0 <= index < len(run.passes) else None
        if claims is None:
            raise AssertionError(
                "claim_stale_messages ran on a pass whose shipped clock cannot open the "
                "30-second claim gate"
            )
        await _REAL_SLEEP(0)
        return list(claims)

    async def consume_batches(*args: Any, **kwargs: Any) -> list[Any]:
        if run.calls > PASS_CEILING:
            raise RuntimeError("the loop iterated more times than any shipped path can")
        scripted_pass = run.next_pass()
        await _REAL_SLEEP(0)
        if scripted_pass.raises is not None:
            raise scripted_pass.raises
        return list(scripted_pass.messages)

    service.claim_stale_messages.side_effect = claim_stale_messages
    service.consume_batches.side_effect = consume_batches
    service.acknowledge.return_value = True
    return service


@contextlib.asynccontextmanager
async def scripted(run: Run) -> Any:
    """Drive the shipped loop through the leg's whole script, then hand out the spies.

    Yields ``(worker, doubles, service, factory)`` INSIDE the patch window, because the
    state pins must be taken while the doubles are installed.  Every double is autospec'd
    from the shipped callable and installed with ``new=``.
    """
    worker = make_worker(run)
    # build_service=False drives the SHIPPED `stream_service is None` state inside
    # streams mode (L892 declares None, L896 writes whatever the factory returns): the
    # factory is made to answer None, so L921's second conjunct is what decides the arm.
    service = make_stream_service(run) if (run.use_streams and run.build_service) else None

    sleep_double = autospec_of(_REAL_SLEEP)

    async def sleep_side_effect(delay: float, *_args: Any, **_kwargs: Any) -> None:
        """Records the delay and stops a runaway loop.

        Every leg really ends on its sentinel pass' ``CancelledError`` -> shipped
        ``break``, so the shipped loop never reaches L970 here at all.  A MUTANT can
        reach it repeatedly: the L921 ``and`` -> ``or`` flip, for instance, sends a
        ``stream_service is None`` drive into the streams arm, where
        ``None.consume_batches`` raises ``AttributeError`` on every iteration and the
        error arm sleeps forever.  This backstop turns that into a bounded drive whose
        log surface the pins then reject, instead of a hang.
        """
        run.sleeps.append(delay)
        if len(run.sleeps) > run.sleep_limit or run.calls > PASS_CEILING:
            worker._running = False

    sleep_double.side_effect = sleep_side_effect

    settings = create_autospec(Settings, instance=True)
    settings.use_redis_streams = run.use_streams
    get_settings = autospec_of(M.get_settings)
    get_settings.return_value = settings

    factory = autospec_of(M.get_analysis_stream_service)
    # build_service=False drives the shipped `stream_service is None` state INSIDE
    # streams mode, so the factory must answer None - not an autospec'd mock, which
    # would be non-None and defeat the whole point of the leg.
    factory.return_value = service

    record_error = autospec_of(M.record_pipeline_error)
    # L961 writes the ERROR state and L971 restores RUNNING, so the ONLY place the
    # shipped L961 write is observable is inside the L964 record_pipeline_error call
    # between them.  Snapshot it there, through the shipped WorkerStats.to_dict() -
    # which is also what makes m60 (state = None) raise instead of pass silently.
    record_error.side_effect = lambda _error_type: run.states_at_error_call.append(
        worker._stats.to_dict()["state"]
    )

    run.hb_module = run.clock_kind(*run.clock)
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(M, "time_module", new=run.hb_module))
        stack.enter_context(patch.object(M, "get_settings", new=get_settings))
        stack.enter_context(patch.object(M, "get_analysis_stream_service", new=factory))
        stack.enter_context(patch.object(M, "record_pipeline_error", new=record_error))
        stack.enter_context(patch.object(asyncio, "sleep", new=sleep_double))
        await M.AnalysisQueueWorker._run_loop(worker)
        yield (
            worker,
            {"record_pipeline_error": record_error, "asyncio.sleep": sleep_double},
            (service),
            factory,
        )


def message(
    msg_id: str,
    *,
    batch_id: str,
    camera_id: str,
    detection_ids: list[int],
    delivery_count: int = 1,
) -> AnalysisStreamMessage:
    """A REAL shipped ``AnalysisStreamMessage`` (a dataclass, not a mock).

    Its ``to_queue_dict()`` (redis_streams.py:936-950) is the value the shipped loop
    forwards to ``_process_analysis_item``, so the pin asserts the shipped conversion and
    not a mock's echo.
    """
    return AnalysisStreamMessage(
        id=msg_id,
        batch_id=batch_id,
        camera_id=camera_id,
        detection_ids=detection_ids,
        delivery_count=delivery_count,
    )


CANCEL = asyncio.CancelledError


# =============================================================================
# 1) streams mode: the banner family, the consumer_name family, the factory,
#    the consume-call family (m2, m4, m5, m6, m7, m8-m16, m28, m29, m34, m35, m37)
# =============================================================================


async def test_streams_mode_builds_the_service_announces_the_consumer_and_consumes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:888-943 + L973 in STREAMS mode (``use_redis_streams`` True).

    ::

        settings = get_settings()                                   # L890
        use_streams = settings.use_redis_streams                    # L891
        stream_service: AnalysisStreamService | None = None         # L892
        consumer_name = f"analysis-worker-{id(self)}"               # L893
        if use_streams:                                             # L895
            stream_service = await get_analysis_stream_service(self._redis)  # L896
            logger.info(                                            # L897-900
                "AnalysisQueueWorker loop started (Redis Streams mode)",
                extra={"consumer_name": consumer_name},
            )
        ...
                if use_streams and stream_service is not None:      # L921
                    messages = await stream_service.consume_batches(
                        consumer_name, count=1, block=True          # L935-937
                    )
                    ...
                    for msg in messages:
                        await self._process_analysis_item(msg.to_queue_dict())  # L942
                        await stream_service.acknowledge(msg.id)    # L943

    21 keys live here.  The banner is ONLY reachable in this mode, so its message
    (m8/m10/m12/m13/m14) and payload (m9/m11/m15/m16) die here - and the payload VALUE
    is the shipped ``f"analysis-worker-{id(worker)}"``, which is also what makes m4
    (``consumer_name = None``) and m5 (``id(None)``) visible.  The same value is pinned
    as ``consume_batches``' positional (m34/m37) with ``count=1`` (m35) and
    ``block=True``.  The mode pins kill m2, m6 and m29 - each one silently converts
    this leg into a legacy drive, so the factory call, the consume call and the legacy
    ``get_from_queue``-never-called pin break together.  m7 is caught by the factory
    argument's IDENTITY, and m28 by the claim-gate / legacy legs restating the same
    conjunct from the falsy side.
    """
    run = Run(
        passes=[
            Pass(
                messages=[
                    message("1-0", batch_id="batch-7", camera_id="cam-3", detection_ids=[11, 12])
                ]
            ),
            Pass(
                messages=[message("2-0", batch_id="batch-8", camera_id="cam-4", detection_ids=[21])]
            ),
            Pass(raises=CANCEL()),
        ],
        # ConstantTimeModule: every read identical, so elapsed is 0.0 and NEITHER the
        # 20 s heartbeat nor the 30 s claim gate opens.
        clock=[0.0],
        use_streams=True,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (worker, _doubles, service, factory):
        stats = worker._stats.to_dict()

    consumer_name = f"analysis-worker-{id(worker)}"
    assert factory.await_count == 1, f"the stream service was built {factory.await_count} times"
    assert factory.await_args is not None
    assert factory.await_args.args == (worker._redis,), (
        f"get_analysis_stream_service argument mutated: {factory.await_args!r}"
    )
    assert not factory.await_args.kwargs, (
        f"the factory takes one positional: {factory.await_args!r}"
    )

    consume_calls = service.consume_batches.await_args_list
    assert consume_calls == [
        call(consumer_name, count=1, block=True),
        call(consumer_name, count=1, block=True),
        call(consumer_name, count=1, block=True),
    ], f"consume_batches mutated: {consume_calls!r}"
    assert service.claim_stale_messages.await_count == 0, (
        "the 30-second claim gate must stay shut while the clock does not advance"
    )
    processed = worker._process_analysis_item.await_args_list
    assert processed == [
        call({"batch_id": "batch-7", "camera_id": "cam-3", "detection_ids": [11, 12]}),
        call({"batch_id": "batch-8", "camera_id": "cam-4", "detection_ids": [21]}),
    ], f"_process_analysis_item / to_queue_dict mutated: {processed!r}"
    assert service.acknowledge.await_args_list == [call("1-0"), call("2-0")], (
        f"acknowledge ids mutated: {service.acknowledge.await_args_list!r}"
    )
    assert worker._redis.get_from_queue.await_count == 0, (
        "streams mode must never touch the legacy BLPOP arm"
    )
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"the shipped WorkerStats.to_dict() surface mutated: {stats!r}"

    pin_levels(
        caplog,
        [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO],
        logging.INFO,
    )
    pin_payloads(
        caplog,
        logging.INFO,
        [{"consumer_name": consumer_name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [], "the streams arm never sleeps"
    assert run.heartbeat_reads() == 5, (
        "L905 + L909 baselines plus one L923 read on every one of the three iterations "
        "(the sentinel pass reads the gate clock before its read raises): "
        f"{run.heartbeat_reads()}"
    )


# =============================================================================
# 2) the stale-claim gate (m25, m30, m31, m32) + the DLQ routing control
# =============================================================================


async def test_the_stale_claim_gate_fires_once_per_shipped_30_second_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:908-932 - claim stale messages once per 30.0 s of alias clock.

    ::

        last_claim_check = time_module.time()                     # L909 -> 1000.0
        claim_interval = 30.0                                     # L910
        ...
                    now = time_module.time()                      # L923
                    if now - last_claim_check >= claim_interval:  # L924
                        claimed = await stream_service.claim_stale_messages(
                            consumer_name, count=5                # L925
                        )
                        for msg in claimed:
                            if msg.delivery_count >= stream_service._max_delivery_count:
                                await stream_service.move_to_dlq(msg, "max_delivery_exceeded")
                            else:
                                await self._process_analysis_item(msg.to_queue_dict())
                                await stream_service.acknowledge(msg.id)
                        last_claim_check = now                    # L932

    The alias is scripted ``1000.0 -> 1000.0 -> 1030.0 -> 1030.0`` (the L905 baseline
    and the L909 baseline share it).  A NON-ZERO baseline is load-bearing: at
    ``last_claim_check == 0.0`` the shipped difference and m31's ``now + last_claim_check``
    coincide, so with a zero baseline m31 is unobservable.  Pass 1 (``now`` 1000.0,
    ``elapsed`` 0.0) must NOT claim - m31 does claim there
    (``1000.0 + 1000.0 >= 30.0``).  Pass 2 (``now`` 1030.0, ``elapsed`` EXACTLY 30.0)
    is the ``>=`` boundary: shipped claims, m32's ``>`` does not.  ``claim_interval =
    None`` (m25) and ``now = None`` (m30) raise ``TypeError`` inside the shipped
    ``try`` and land in the error arm, which the zero-error pins reject.

    Pass 2's claim returns one message AT the injected delivery limit (routed to the DLQ
    with the shipped reason) and one BELOW it (processed through the shipped
    ``to_queue_dict()`` and acknowledged by id) - the DLQ leg the manifest lists as a
    control, so entering the streams arm is never enough: what the claim yields must be
    routed correctly.  Pass 1 and pass 3 script ``claims=None``, so any claim the shipped
    gate should not make raises inside the shipped ``try`` and shows up as an ERROR
    record plus a non-zero ``errors`` count.  Both gated passes return NO new messages
    from ``consume_batches``, so the ``if not messages: continue`` (L938-939) is what ends
    them.
    """
    over_limit = message(
        "9-0",
        batch_id="batch-old",
        camera_id="cam-9",
        detection_ids=[5],
        delivery_count=DLQ_THRESHOLD,
    )
    claimable = message(
        "9-1",
        batch_id="batch-stale",
        camera_id="cam-8",
        detection_ids=[6, 7],
        delivery_count=1,
    )
    run = Run(
        passes=[
            Pass(messages=[], claims=None),
            Pass(messages=[], claims=[over_limit, claimable]),
            Pass(raises=CANCEL()),
        ],
        clock=[1000.0, 1000.0, 1000.0, 1030.0, 1030.0],
        clock_kind=ScriptedTimeModule,
        use_streams=True,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (worker, _doubles, service, _factory):
        stats = worker._stats.to_dict()

    consumer_name = f"analysis-worker-{id(worker)}"
    assert service.claim_stale_messages.await_args_list == [
        call(consumer_name, count=CLAIM_COUNT)
    ], f"claim gate contract mutated: {service.claim_stale_messages.await_args_list!r}"
    assert service.move_to_dlq.await_args_list == [call(over_limit, DLQ_REASON)], (
        f"DLQ routing mutated: {service.move_to_dlq.await_args_list!r}"
    )
    processed = worker._process_analysis_item.await_args_list
    assert processed == [
        call({"batch_id": "batch-stale", "camera_id": "cam-8", "detection_ids": [6, 7]}),
    ], f"claimed-message processing mutated: {processed!r}"
    assert service.acknowledge.await_args_list == [call("9-1")], (
        f"acknowledge after a claim mutated: {service.acknowledge.await_args_list!r}"
    )
    assert service.consume_batches.await_count == 3, (
        "one consume read per iteration INCLUDING the sentinel pass, whose read raises"
    )
    assert worker._redis.get_from_queue.await_count == 0, (
        "streams mode must never touch the legacy BLPOP arm"
    )
    assert stats["errors"] == 0, f"the claim gate must not error: {stats!r}"
    pin_levels(caplog, [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(
        caplog,
        logging.INFO,
        [{"consumer_name": consumer_name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == []
    assert run.heartbeat_reads() == 5, (
        "L905 + L909 baselines plus one L923 read per iteration (3 iterations): "
        f"{run.heartbeat_reads()}"
    )


# =============================================================================
# 3) legacy mode: the BLPOP family, the None-item / continue arms, processing
#    (m17, m18, m20, m44-m46, m48-m51; the L921 conjunction restated from the falsy side)
# =============================================================================


async def test_legacy_mode_reads_the_queue_by_name_processes_and_survives_idle_reads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:888-902 + L944-954 with ``use_redis_streams`` False.

    ::

        else:
            logger.info("AnalysisQueueWorker loop started")          # L902
        ...
            else:
                # Legacy list-based queue (BLPOP)
                item = await self._redis.get_from_queue(             # L946-949
                    self._queue_name,
                    timeout=self._poll_timeout,
                )
                if item is None:                                      # L951
                    continue                                          # L952
                await self._process_analysis_item(item)              # L954

    Four scripted passes: item / idle / second item / sentinel.  The BLPOP call list is
    pinned to four identical ``call(queue_name, timeout=poll_timeout)`` records using
    THIS file's injected attribute values (``"analysis_queue-b28"`` / ``3``), so m45
    (queue name -> ``None``), m46 (``timeout=None``) and m48 (the ``timeout`` keyword
    dropped) all show up, and m44 (the whole read replaced by ``item = None``) empties
    the list.  The alternating idle pass is what reads m49 and m50: shipped skips
    processing and LOOPs, the flip processes ``None``, and ``break`` leaves the loop
    early - both caught by the exact processed-item and call-count pins.  m51's ``None``
    argument cannot match the injected dict's identity.  The legacy banner text is
    pinned because only this mode reaches L902 (m17/m18/m20), and m28 is read from the
    falsy side: a real service object plus a falsy flag must still take this arm.
    """
    first = {"batch_id": "batch-A", "camera_id": "cam-1", "detection_ids": [1]}
    second = {"batch_id": "batch-B", "camera_id": "cam-2", "detection_ids": [2, 3]}
    run = Run(
        passes=[
            Pass(item=first),
            Pass(item=None),
            Pass(item=second),
            Pass(raises=CANCEL()),
        ],
        clock=[700.0],
        use_streams=False,
        supervisor=None,
        queue_name="analysis_queue-b28",
        poll_timeout=3,
    )
    win(caplog)

    async with scripted(run) as (worker, _doubles, _service, factory):
        stats = worker._stats.to_dict()

    redis = worker._redis
    assert redis.get_from_queue.await_count == 4, (
        f"one BLPOP read per iteration: {redis.get_from_queue.await_count}"
    )
    assert redis.get_from_queue.await_args_list == [
        call("analysis_queue-b28", timeout=3),
        call("analysis_queue-b28", timeout=3),
        call("analysis_queue-b28", timeout=3),
        call("analysis_queue-b28", timeout=3),
    ], f"the BLPOP call shape mutated: {redis.get_from_queue.await_args_list!r}"
    assert worker._process_analysis_item.await_args_list == [call(first), call(second)], (
        f"_process_analysis_item mutated: {worker._process_analysis_item.await_args_list!r}"
    )
    assert factory.await_count == 0, "legacy mode must not build the stream service"
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"stats mutated: {stats!r}"

    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"items_processed": 0}])
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == [], "neither the item nor the idle legacy pass sleeps"
    assert run.heartbeat_reads() == 2, (
        "exactly the L905 + L909 baselines: no supervisor means no L916 read, and "
        f"legacy mode short-circuits L921 on use_streams so there is no L923 read: "
        f"{run.heartbeat_reads()}"
    )


# =============================================================================
# 4) the heartbeat gate (m21, m22, m23, m27) - the ONLY leg whose shipped run
#    evaluates the heartbeat comparison
# =============================================================================


def supervisor_double() -> Any:
    """autospec'd instance double of the shipped ``WorkerSupervisor``."""
    return create_autospec(WorkerSupervisor).return_value


async def test_the_analysis_heartbeat_fires_once_per_shipped_20_second_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:904-919 - one ``record_heartbeat(worker_name)`` per 20.0 s of clock.

    ::

        last_heartbeat = time_module.time()      # read 1 -> 0.0
        heartbeat_interval = 20.0                # the shipped constant (L906)
        while self._running:
            try:
                if self._supervisor is not None:              # L915
                    now = time_module.time()                  # gate reads
                    if now - last_heartbeat >= heartbeat_interval:   # L917
                        self._supervisor.record_heartbeat(self._worker_name)
                        last_heartbeat = now

    LEGACY mode, so the claim gate's reads cannot blur the count.  The alias walks
    ``0.0 (L905 baseline) -> 0.0 (L909 claim baseline, unused here) -> 20.0 -> 40.0 ->
    60.0``: EVERY gated pass advances EXACTLY 20.0 s from the previous beat, so the
    shipped ``>=`` fires on all three iterations (the sentinel pass pays its gate read
    before its queue read raises) - ``[analysis, analysis, analysis]``.  m23 (``21.0``)
    can never keep pace with a 20 s step: pass 1 is short (20.0 >= 21.0 is False), pass
    2 beats from the UNMOVED baseline (40.0 - 0.0), pass 3 is short again (20.0 < 21.0) -
    exactly ONE beat, a different call list.  (A coarser script - a first gate already
    past 21.0 - would let the mutant beat once and match shipped; that is the vacuity
    this script is built to avoid.)  Under m21 (``last_heartbeat = None``) or m22
    (``heartbeat_interval = None``) the comparison raises ``TypeError`` inside the
    shipped ``try`` and turns every iteration into the error arm, which the zero-ERROR
    pin rejects.  Under the m27 flip the arm never runs for a present supervisor: zero
    beats and TWO reads instead of five.  The call argument is the shipped default
    worker name (L786 / L809).
    """
    supervisor = supervisor_double()
    run = Run(
        passes=[Pass(item=None), Pass(item=None), Pass(raises=CANCEL())],
        clock=[0.0, 0.0, 20.0, 40.0, 60.0],
        clock_kind=ScriptedTimeModule,
        use_streams=False,
        supervisor=supervisor,
    )
    win(caplog)

    async with scripted(run) as (_worker, _doubles, _service, _factory):
        pass

    assert supervisor.record_heartbeat.call_args_list == [
        call("analysis"),
        call("analysis"),
        call("analysis"),
    ], f"heartbeat contract mutated: {supervisor.record_heartbeat.call_args_list!r}"
    assert run.heartbeat_reads() == 5, (
        "L905 baseline, L909 baseline, plus one L916 gate read in every one of the three "
        f"iterations (the sentinel pass reads before its read raises): "
        f"{run.heartbeat_reads()}"
    )
    assert _doubles["record_pipeline_error"].call_count == 0, (
        "the heartbeat gate must never error: the shipped comparison runs on floats"
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"items_processed": 0}])
    assert run.sleeps == []


# =============================================================================
# 5) control: no supervisor -> the gate body never runs (m27 from the other side)
# =============================================================================


async def test_an_unsupervised_analysis_worker_never_reads_the_heartbeat_clock(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:915 - ``if self._supervisor is not None:`` with NO supervisor.

    Two idle legacy passes read the alias exactly TWICE - the L905 and L909 baselines -
    because the gate body is skipped every iteration.  The flip (m27) runs the arm
    anyway, so the read count grows and this leg goes red; the zero-beat and zero-error
    pins state the rest of that arm's absence.
    """
    run = Run(
        passes=[Pass(item=None), Pass(item=None), Pass(raises=CANCEL())],
        clock=[123.0],
        use_streams=False,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (_worker, doubles, _service, _factory):
        pass

    assert run.heartbeat_reads() == 2, (
        f"a None supervisor must not read the heartbeat clock: {run.heartbeat_reads()} reads"
    )
    assert doubles["record_pipeline_error"].call_count == 0
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    assert run.sleeps == []


# =============================================================================
# 6) the ``except Exception`` arm (m57, m58, m60, m61-m65) - sole route
# =============================================================================


async def test_two_failures_count_incrementally_and_report_the_shipped_label(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:959-971 over two failing reads, then the sentinel.

    ::

        except Exception as e:
            self._stats.errors += 1                            # L960
            self._stats.state = WorkerState.ERROR              # L961
            error_type = categorize_exception(e, "analysis")    # L963
            record_pipeline_error(error_type)                   # L964
            logger.error(
                f"Error in AnalysisQueueWorker loop: {e}",      # L966
                exc_info=True,                                  # L967
                extra={"error_count": self._stats.errors, "error_type": error_type},  # L968
            )
            await asyncio.sleep(1.0)                            # L970
            self._stats.state = WorkerState.RUNNING             # L971

    8 keys live here.  ``errors`` is pinned ACROSS two failures - shipped 1 then 2 - so
    m57's ``= 1`` and m58's ``-= 1`` both show up in the payload pair and in the final
    stats.  ``record_pipeline_error`` is pinned with the EXACT shipped label: m61
    (``error_type = None``) hands over ``None``, m62
    (``categorize_exception(None, "analysis")``) the ``"analysis_processing_error"``
    that a ``None`` exception falls through to, and m63 (``(e, None)``) the
    ``"None_connection_error"`` a ``None`` worker name produces.  m64
    (``categorize_exception("analysis")``) and m65 (``categorize_exception(e, )``) drop
    a REQUIRED argument, so the shipped handler itself raises ``TypeError`` straight out
    of ``_run_loop`` - measured as an errored test.  The state is read INSIDE the L964
    call (only place L961 is visible; m60 makes the shipped ``to_dict()`` raise there)
    and after the pass through the shipped ``to_dict()`` as ``"running"``.
    """
    first = builtins.ConnectionError("analysis queue connection reset")
    second = builtins.ConnectionError("analysis pool exhausted, cannot CONNECT")
    run = Run(
        passes=[Pass(raises=first), Pass(raises=second), Pass(raises=CANCEL())],
        clock=[900.0],
        use_streams=False,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, _service, _factory):
        stats = worker._stats.to_dict()
        states = list(run.states_at_error_call)

    assert states == [STATE_ERROR, STATE_ERROR], (
        f"the L961 ERROR state must be live inside record_pipeline_error: {states!r}"
    )
    assert stats == {
        "items_processed": 0,
        "errors": 2,
        "last_processed_at": None,
        "state": STATE_RUNNING,
    }, f"stats mutated: {stats!r}"
    assert doubles["record_pipeline_error"].call_args_list == [
        call(ERROR_LABEL),
        call(ERROR_LABEL),
    ], f"record_pipeline_error mutated: {doubles['record_pipeline_error'].call_args_list!r}"
    assert worker._process_analysis_item.await_count == 0, "a failing pass processes nothing"

    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"items_processed": 0}])
    pin_levels(caplog, [ERROR_INFO_TPL.format(first), ERROR_INFO_TPL.format(second)], logging.ERROR)
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
    assert run.sleeps == [1.0, 1.0], "the failed pass sleeps the shipped 1.0 s (L970)"
    assert run.heartbeat_reads() == 2, run.heartbeat_reads()


async def test_the_iteration_after_a_failure_reads_the_queue_again_and_stays_running(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second, independently-valued route: one failure, then a real item.

    This is the leg that pins the ERROR arm's SURVIVAL contract - the state has to be
    back to ``running`` AND the next iteration has to read the queue and process the
    item it returns - so the error family cannot be satisfied by a drive that only ever
    fails.  The ERROR payload's ``error_count`` is the FIRST failure's count here, which
    the accumulating ``+= 1`` (L960) pins a second time from a different angle.
    """
    err = builtins.ConnectionError("analysis read timeout on BLPOP")
    item = {"batch_id": "batch-C", "camera_id": "cam-5", "detection_ids": [42]}
    run = Run(
        passes=[Pass(raises=err), Pass(item=item), Pass(raises=CANCEL())],
        clock=[1500.0],
        use_streams=False,
        supervisor=None,
        queue_name="analysis_queue-b28",
        poll_timeout=3,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, _service, _factory):
        stats = worker._stats.to_dict()
        states = list(run.states_at_error_call)

    assert states == [STATE_ERROR]
    assert stats == {
        "items_processed": 0,
        "errors": 1,
        "last_processed_at": None,
        "state": STATE_RUNNING,
    }, f"stats mutated: {stats!r}"
    assert doubles["record_pipeline_error"].call_args_list == [call(ERROR_LABEL)]
    assert worker._process_analysis_item.await_args_list == [call(item)]
    assert worker._redis.get_from_queue.await_args_list == [
        call("analysis_queue-b28", timeout=3),
        call("analysis_queue-b28", timeout=3),
        call("analysis_queue-b28", timeout=3),
    ], "the loop must re-read the queue after a failure"
    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_levels(caplog, [ERROR_INFO_TPL.format(err)], logging.ERROR)
    pin_payloads(caplog, logging.ERROR, [{"error_count": 1, "error_type": ERROR_LABEL}])
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [1.0], run.sleeps


# =============================================================================
# 7) control: the CancelledError arm (m52, m53, m54, m56)
# =============================================================================


async def test_a_cancelled_read_logs_the_cancelled_info_then_the_exit_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:956-958 + L973 - ``except asyncio.CancelledError``: INFO then ``break``.

    The ordered INFO triple ``[legacy banner, cancelled, exited]`` is the whole
    contract, and it is what kills the three message mutants at L957 (m52/m53/m54) and
    m56: replacing the ``break`` with ``return`` skips the L973 exit INFO entirely, so
    the surface loses its third record.  Nothing else happens on this drive - no
    processing, no sleep, no error, no ERROR record - which is what stops the ERROR and
    cadence surfaces of the other legs from being re-explained by this arm.
    """
    run = Run(
        passes=[Pass(raises=CANCEL())],
        clock=[1800.0],
        use_streams=False,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, _service, _factory):
        stats = worker._stats.to_dict()

    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"items_processed": 0}])
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert worker._redis.get_from_queue.await_count == 1
    assert worker._process_analysis_item.await_count == 0
    assert run.sleeps == [], "the break skips everything after the handler"
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"a cancelled read changed the stats: {stats!r}"
    assert doubles["record_pipeline_error"].call_count == 0
    assert run.heartbeat_reads() == 2, run.heartbeat_reads()


# =============================================================================
# 8a) streams mode with NO service object: the L921 conjunct decides the arm
#     (m28 `and` -> `or`, m29 `is not None` -> `is None`)
# =============================================================================


async def test_streams_mode_without_a_service_object_still_uses_the_legacy_queue(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:921 - ``if use_streams and stream_service is not None:``.

    The one drive where the two conjuncts DISAGREE: ``use_streams`` is True (so the
    STREAMS banner fired at L897 and the factory was awaited at L896) but what the
    factory returned was ``None``, so the shipped conjunction is False and every
    iteration must read the LEGACY queue.  This is a reachable shipped state - L892
    declares ``stream_service = None`` and L896 writes whatever the factory hands back.

    * m28 (``and`` -> ``or``): ``True or ...`` is True, so the mutant enters the streams
      arm and calls ``None.consume_batches(...)`` - an ``AttributeError`` on every
      iteration.  Its ERROR surface and its ``asyncio.sleep(1.0)`` per failed pass are
      exactly what the pins here forbid, and the sleep-count backstop keeps such a
      mutant bounded instead of hanging.
    * m29 (``stream_service is not None`` -> ``is None``): ``True and True`` is True, so
      it enters the same arm and dies the same way.
    * The shipped path is pinned positively too: the BLPOP call list carries the worker's
      own queue name and timeout, the legacy banner is ABSENT (this drive is in streams
      mode - the streams banner fired instead), and the factory call is still pinned, so
      the leg cannot be satisfied by a drive that simply forgot about streams.
    """
    item = {"batch_id": "batch-D", "camera_id": "cam-6", "detection_ids": [77]}
    run = Run(
        passes=[Pass(item=item), Pass(raises=CANCEL())],
        clock=[0.0],
        use_streams=True,
        build_service=False,
        supervisor=None,
        queue_name="analysis_queue-b28",
        poll_timeout=3,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, _service, factory):
        stats = worker._stats.to_dict()

    consumer_name = f"analysis-worker-{id(worker)}"
    assert factory.await_count == 1, "L896 runs whenever use_streams is truthy"
    assert worker._redis.get_from_queue.await_args_list == [
        call("analysis_queue-b28", timeout=3),
        call("analysis_queue-b28", timeout=3),
    ], (
        f"the no-service drive must stay on the legacy queue: {worker._redis.get_from_queue.await_args_list!r}"
    )
    assert worker._process_analysis_item.await_args_list == [call(item)], (
        f"the legacy item must still be processed: {worker._process_analysis_item.await_args_list!r}"
    )
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"a no-service streams drive must not error: {stats!r}"
    assert doubles["record_pipeline_error"].call_count == 0, (
        "the shipped conjunction never enters the streams arm here"
    )
    pin_levels(caplog, [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(
        caplog,
        logging.INFO,
        [{"consumer_name": consumer_name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == [], "no failed pass means no L970 sleep"


# =============================================================================
# 8) streams-mode control: an empty consume read continues WITHOUT touching legacy
# =============================================================================


async def test_an_empty_consume_read_continues_without_the_legacy_arm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:938-939 - ``if not messages: continue`` in streams mode.

    Stated because the legacy leg's ``continue`` pins (m49/m50) sit in a DIFFERENT arm:
    an empty stream read must loop back to the top WITHOUT falling into the BLPOP arm
    and without processing anything.  Three empty reads, then the sentinel; the clock
    stays constant so neither gate opens, and the two INFO records pin the streams
    banner a second time with a different worker object (a second route to the banner
    family at a different ``consumer_name``).
    """
    run = Run(
        passes=[
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(raises=CANCEL()),
        ],
        clock=[0.0],
        use_streams=True,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (worker, _doubles, service, _factory):
        stats = worker._stats.to_dict()

    assert service.consume_batches.await_count == 4, (
        "one consume read per scripted pass, the sentinel pass included"
    )
    assert service.claim_stale_messages.await_count == 0
    assert worker._redis.get_from_queue.await_count == 0, (
        "streams mode must never fall into the legacy BLPOP arm"
    )
    assert worker._process_analysis_item.await_count == 0
    assert stats["items_processed"] == 0
    assert stats["errors"] == 0
    pin_levels(caplog, [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(
        caplog,
        logging.INFO,
        [
            {"consumer_name": f"analysis-worker-{id(worker)}"},
            {},
            {"items_processed": 0},
        ],
    )
    assert run.sleeps == []
    assert run.heartbeat_reads() == 6, (
        "the L905 + L909 baselines plus one L923 read per iteration on the frozen clock: "
        f"{run.heartbeat_reads()}"
    )
