"""S3 batch-28 lane 10 - ``pipeline_workers`` group g10 kill battery (46 keys).

Module: ``backend/services/pipeline_workers.py`` (lane ``05b50f5a``, blob md5
``d6e3c91fc85bfaea19f0d907491eefbf``).  The survivor bank was measured against blob
``74649fd3``; ``DetectionQueueWorker._run_loop`` is BYTE-IDENTICAL between that blob
and this one (verified: ``diff <(sed -n '363,452p' /tmp/wp-b28/pw_OLDSRC_74649fd3.py)
<(sed -n '364,453p' backend/services/pipeline_workers.py)`` is empty), so the bank's
per-key lines carry a uniform +1 shift from the import hunk above this function - the
MUTANTS are unchanged, only their coordinates moved.  EVERY LINE NUMBER CITED BELOW IS
THE CURRENT SHIPPED BLOB'S (``d6e3c91f``): the loop is L364-453, the consumer_name
binding is L369, the factory call L372, the streams banner L374-376, the legacy banner
L378, ``last_heartbeat`` L381, ``heartbeat_interval`` L382, ``last_claim_check`` L385,
``claim_interval`` L386, the supervisor gate L391-395, the arm conjunction L397, the
claim gate L399-400 and its body L401-408, the consume call L411-413, the
``if not messages: continue`` L414-415, the consume ``for`` L417-419, the BLPOP read
L422-425, ``if item is None: continue`` L427-428, the legacy process L430, the
``CancelledError`` arm L432-434, the ``Exception`` arm L435-448 and the exit INFO
L450-453.
Admitted manifest: ``/tmp/wp-pw/pipeline_workers/`` ``manifest.json`` group 10 ("g10
DetectionQueueWorker._run_loop", 45 KILLABLE / 1 EQUIVALENT / 0 NEEDS_INVESTIGATION),
plus ``group_10.keys`` and ``survivors.json`` for the exact per-key diffs.

All 46 keys sit on ``DetectionQueueWorker._run_loop`` (L364-453).  Every leg drives the
REAL coroutine - ``await M.DetectionQueueWorker._run_loop(worker)`` is the shipped
function object called with an attribute-only ``self``, never an autospec'd double of
the loop.  Termination is scripted, never lucky: the last pass of every leg raises
``asyncio.CancelledError`` from the queue/stream read the loop performs exactly once per
iteration, so the shipped ``break`` (L434) ends the drive.

THE EQUIVALENT KEY (UPHELD - no test needed, per the manifest's PER-KEY EXCEPTIONS)
-----------------------------------------------------------------------------------
``xǁDetectionQueueWorkerǁ_run_loop__mutmut_3`` - L368
``stream_service: DetectionStreamService | None = None`` -> ``= ""``.  DEAD DECLARATION
VALUE: the binding is written at L368 and re-written unconditionally at L372 on the only
path that reads it (L371 ``if use_streams:`` gates both the write and any truthy
``use_streams`` reaching the single read at L397), so the initialiser's value is never
observed; and on the ``use_streams`` falsy path L397 short-circuits on ``use_streams``
before the ``stream_service is not None`` conjunct, so ``""`` is behaviourally identical
to ``None`` at every reachable read.  No shipped-behaviour assert can separate them; it
is reported as uncovered-by-design, not faked.

Test -> mutant-key map
======================
Occurrence-twin check (against THIS blob, via the shared replay's own
``candidates()``): 42 of the 46 diffs resolve to ONE textual position; four resolve to
TWO, and BOTH twins are reddened here - ``m30`` (``now = time_module.time()`` matches
the heartbeat gate read at L392 as well as the claim gate read at L399: the heartbeat leg
drives legacy mode, where L397 short-circuits and only L392 can raise, while the claim leg
drives streams mode with NO supervisor, where only L399 can raise), ``m44``/``m45``
(``_process_detection_item(msg.raw_data)`` / ``acknowledge(msg.id)`` match the claimed
``for`` body at L406-407 as well as the consume ``for`` body at L418-419: the claim leg
pins the claimed message's raw_data and ``acknowledge("9-1")`` as its OWN call list, the
consume leg pins the fresh message's raw_data and ``acknowledge("1-0")``/``("2-0")``) and
``m52`` (``continue`` matches the streams ``if not messages`` at L415 as well as the
legacy one at L428: the empty-consume control legs pin 4 consume reads / zero errors,
which a ``break`` cannot produce, and the legacy leg scripts an idle pass in between two
item passes).

- ``..._mutmut_4/_5`` L369 ``consumer_name = f"detection-worker-{id(self)}"`` -> ``None``
  / ``f"detection-worker-{id(None)}"``, ``_8``/``_10``/``_12`` L374 the streams banner
  message -> ``None`` / the message dropped (a ``TypeError`` from the autospec'd
  ``logger.info`` INSIDE the shipped ``try`` of the pass that follows, so this leg ends
  in the error arm) / ``"XX...XX"``, and ``_9``/``_11``/``_15``/``_16`` L375
  ``extra={"consumer_name": consumer_name}`` -> ``extra=None`` / the ``extra`` drop / the
  two key renames
  -> ``test_streams_mode_builds_the_service_announces_the_consumer_and_consumes``, the
  SOLE leg whose shipped run takes ``if use_streams:`` at L371 with a service object, so
  this banner exists nowhere else: message AND payload pinned together, and the payload
  VALUE is ``f"detection-worker-{id(worker)}"`` - which is also what kills m4 (a ``None``
  payload) and m5 (the process-wide ``id(None)``).  ``_mutmut_7`` L372 factory ARGUMENT
  -> ``None`` is killed only by that call's argument IDENTITY pin.
- ``..._mutmut_6`` L372 ``stream_service = await get_detection_stream_service(...)`` ->
  ``= None``, and ``_28``/``_29`` L397 ``if use_streams and stream_service is not None:``
  -> ``or`` / ``stream_service is None``
  -> ``test_streams_mode_without_a_service_object_still_uses_the_legacy_queue``, the ONE
  drive where the two conjuncts DISAGREE (flag True, the factory answered ``None``): the
  shipped conjunction reads the LEGACY queue - four idle BLPOP reads, streams banner,
  zero errors, zero sleeps.  m6 makes this drive legacy too, which the BLPOP-count pin
  cannot see, so m6 is killed positively by the streams leg and the claim leg, whose
  consume-call pin goes empty under it.  Both conjunct mutants enter the streams arm
  anyway and call ``None.consume_detections(...)`` - an ``AttributeError`` per iteration
  whose ERROR/sleep surface these pins forbid; the same conjunction is restated from the
  falsy side by every legacy leg (a real service object plus a falsy flag must still read
  the BLPOP queue).
- ``..._mutmut_34/_35/_37`` L411-413 ``consume_detections(consumer_name, count=1,
  block=True)`` -> ``None`` consumer / ``count=None`` / the dropped positional
  -> the streams leg and the two empty-consume controls pin the EXACT call record,
  positional AND keywords, three and four times respectively.
- ``..._mutmut_44/_45`` L418-419 (and their L406-407 twins, above)
  -> the streams leg pins ``_process_detection_item.await_args_list == [call(msg.raw_data)]``
  with the REAL dict the shipped ``DetectionStreamMessage`` carries, plus the
  ``[call(msg1.raw_data), call(msg2.raw_data)]`` pair on the second pass, and
  ``acknowledge.await_args_list == [call("1-0"), call("2-0")]``.  Neither a ``None``
  payload nor a ``None`` message id can satisfy an identity/VALUE equality pin.
- ``..._mutmut_21`` L381 ``last_heartbeat = time_module.time()`` -> ``= None``,
  ``_22``/``_23`` L382 ``heartbeat_interval = 20.0`` -> ``None`` / ``21.0``, ``_27`` L391
  ``if self._supervisor is not None:`` -> ``is None``, and ``_30``'s L392 twin
  -> ``test_the_detection_heartbeat_fires_once_per_shipped_20_second_step`` is the ONLY
  leg whose shipped run evaluates ``now - last_heartbeat >= heartbeat_interval``: the
  alias walks ``0.0 (L381) -> 0.0 (L385, unused) -> 20.0 -> 40.0 -> 60.0``, so every
  gated pass advances EXACTLY 20.0 s from the previous beat and shipped beats three times
  - m23's ``21.0`` can never keep a 20 s pace (pass 1 short, pass 2 beats from the
  UNMOVED baseline, pass 3 short again: exactly ONE beat), a ``None`` operand (m21/m22)
  raises ``TypeError`` inside the shipped ``try`` and replaces all three beats with the
  error arm, and the m27 flip beats never.
  ``test_an_unsupervised_detection_worker_never_reads_the_heartbeat_clock`` reads m27 and
  m30 from the other side (under the flip the arm runs for a ``None`` supervisor, so a
  read is added - which is also this alias's behaviour when m30 makes it raise).
  ``test_a_supervisor_present_in_legacy_mode_never_touches_the_legacy_queue`` makes the
  same gate live in a leg that also pins the BLPOP call list, so a heartbeat mutant
  cannot buy its way into the wrong arm.
- ``..._mutmut_25`` L386 ``claim_interval = 30.0`` -> ``None``, ``_30``'s L399 twin,
  ``_31``/``_32`` L400 ``now - last_claim_check >= claim_interval`` -> ``now +
  last_claim_check`` / ``>``
  -> ``test_the_stale_claim_gate_fires_once_per_shipped_30_second_step``.  Its alias
  starts at ``1000.0`` - deliberately NOT ``0.0``, because at a zero baseline
  ``now - last`` and ``now + last`` coincide and m31 would be unobservable.  Pass 1 reads
  ``1000.0`` again (elapsed 0.0): shipped does NOT claim, m31 DOES (``1000.0 + 1000.0 >=
  30.0``).  Pass 2 reads ``1030.0`` (elapsed EXACTLY 30.0): shipped's ``>=`` claims,
  m32's ``>`` does not.  A ``None`` operand (m25/m30) raises ``TypeError`` inside the
  shipped ``try`` and lands in the error arm, which the zero-error pins reject.  The same
  leg pins the claim ARGUMENTS and the DLQ / process / acknowledge routing of what the
  claim returns, so entering the streams arm is never enough.
- ``..._mutmut_46`` L422-425 the whole BLPOP read -> ``item = None``, ``_49`` L423 queue
  name -> ``None`` / the dropped argument, ``_48``/``_50`` L424 ``timeout=None`` / the
  ``timeout`` line dropped
  -> the legacy leg pins ``await_args_list`` exactly: four ``call("detection_queue-b28",
  timeout=7)`` records carrying THIS file's injected attribute values (deliberately NOT
  the shipped defaults, so no mutant can alias them), and m46 empties that list while
  still claiming the loop processed an item.
- ``..._mutmut_51`` L427 ``if item is None:`` -> ``is not None``, ``_52``'s L428 twin
  ``continue`` -> ``break``, ``_53`` L430 ``_process_detection_item(item)`` -> ``(None)``
  -> the legacy leg alternates item / idle / item: shipped skips processing on the idle
  pass and LOOPs, the flip processes ``None``, and ``break`` leaves the loop early - all
  three visible in the exact processed-item list (IDENTITY of the injected dict is what a
  ``None`` argument cannot match) and the read count.
- ``..._mutmut_54/_56/_57`` L433 ``logger.info("DetectionQueueWorker loop cancelled")``
  -> ``None`` / all-lower / all-upper, and ``_58`` L434 ``break`` -> ``return``
  -> ``test_a_cancelled_read_logs_the_cancelled_info_then_the_exit_info`` pins the
  ordered INFO triple ``[legacy banner, cancelled, exited]``: under m58 the ``return``
  skips L450's exit INFO, so the surface loses its third record, and each message variant
  fails the equality pin.  The control legs pin the same triple a second time.
- ``..._mutmut_60/_61`` L436 ``self._stats.errors += 1`` -> ``-= 1`` / ``+= 2``,
  ``_62`` L437 ``state = WorkerState.ERROR`` -> ``None``, and
  ``_63``/``_64``/``_65`` L439 ``error_type = categorize_exception(e, "detection")`` ->
  ``= None`` / ``categorize_exception(None, "detection")`` / ``(e, None)``
  -> both error legs pin ``errors`` ACROSS two failures (shipped 1 then 2, so m60's -1 and
  m61's 2 show in the payload pair AND the final stats), the state read INSIDE the L440
  ``record_pipeline_error`` call window - the only place L437 is observable, and under
  m62 the shipped ``WorkerStats.to_dict()`` raises ``AttributeError`` right there - and
  the state AFTER the failed pass through the shipped ``to_dict()`` as ``"running"``
  (which is also what makes the L447 ``sleep(1.0)`` observable as ``[1.0, 1.0]``).
  ``record_pipeline_error`` is pinned with the EXACT shipped label
  ``"detection_connection_error"``, which exists only when BOTH categorizer arguments are
  shipped: m63 hands over ``None``, m64's ``None`` exception falls through to
  ``"detection_processing_error"``, and m65's ``None`` worker name yields
  ``"None_connection_error"``.
- ``..._mutmut_17/_20`` L378 ``logger.info("DetectionQueueWorker loop started")`` ->
  ``None`` / all-upper, and the L450-453 exit INFO's message + ``extra={"items_processed
  ...}`` -> EVERY legacy leg pins the ordered INFO surface with the legacy banner text and
  the exit payload ``{"items_processed": 0}`` (which the streams legs pin as ``{}``, so
  the two arms cannot be confused).

Every leg above is the MEASURED failing set of the shadow-tree mutant run (each key built
from its exact survivor diff in a symlinked shadow of this tree, battery run against it).

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it, and
every value an assertion depends on is injected by this file (the settings flag, the queue
items, the stream messages, the clock scripts, the failures).

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``, then
  filtered to this module's logger name), read the RAW ``record.msg`` plus
  ``record.args`` / ``record.exc_info`` / ``record.levelno``, and read ``extra`` payloads
  as the record attributes the shipped ``Logger.makeRecord`` added beyond the
  ``LogRecord`` core plus this module's ``ContextFilter`` contributions.
* Mocks of real attributes are autospec'd (WP4.2 fast path) and installed with ``new=``:
  ``get_settings``, ``get_detection_stream_service`` (this module's
  ``from backend.services.redis_streams import ...`` binding at L69-73 - patching the
  origin module would leave ``M``'s own binding live), ``record_pipeline_error`` and
  ``asyncio.sleep``.  ``Logger.info`` is deliberately NOT patched: leaving the shipped
  logging call live is what makes the banner's message-argument keys visible twice over -
  a substituted ``None`` shows up as a ``record.msg`` the caplog pins read, and a DROPPED
  message argument raises ``TypeError`` out of the real
  ``Logger.info(self, msg, *args, **kwargs)`` inside the shipped ``try``, which lands in
  the error arm.  Injected
  collaborators (Redis client, the stream service, the supervisor) are attributes of a
  ``create_autospec(DetectionQueueWorker)`` INSTANCE double, never patch sites, and the
  autospec'd ``_run_loop`` on that double is NEVER awaited.
* ``self._process_detection_item`` is replaced by an ``AsyncMock`` INSTANCE attribute: a
  replay mutant re-sources the class, so a class-level patch would sail past it, while an
  instance attribute wins in every world.
* The heartbeat / claim clock is the module-level ``time_module`` alias (L33, read at
  L381 / L385 / L392 / L399) and is installed with ``patch.object(M, "time_module",
  new=...)`` - a scripted stepper, never an attribute patch of the real ``time`` module.
  ``time.monotonic`` / ``time.perf_counter`` are never patched and never asserted.
* Termination is structural: every leg's last pass raises ``CancelledError`` from the read
  the loop performs exactly once per iteration, so the shipped ``break`` ends the drive;
  the pass index advances on that read (NOT on a sleep - the streams arm and the idle
  legacy pass never sleep), and a mutant that iterates past the script gets a loud
  ``AssertionError`` inside the shipped ``try`` instead of riding the 5 s ini timeout.
* No import-time global spy: every double is installed inside the leg that uses it,
  module-global access goes through ``live_globals`` (three-worlds safe), and the only
  import-time capture is the real ``asyncio.sleep`` FUNCTION OBJECT, so the injected stubs
  can yield without recursing.
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
from backend.core.redis import RedisClient
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import DetectionQueueWorker, WorkerStats
from backend.services.redis_streams import DetectionStreamMessage, DetectionStreamService
from backend.services.worker_supervisor import WorkerSupervisor

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]

# The real asyncio.sleep, captured at import time so this file's injected stubs can yield
# control to the loop without recursing into themselves.
_REAL_SLEEP = asyncio.sleep


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L374-376: logger.info("DetectionQueueWorker loop started (Redis Streams mode)",
#                       extra={"consumer_name": consumer_name})
STREAMS_BANNER_INFO = "DetectionQueueWorker loop started (Redis Streams mode)"
# L378: logger.info("DetectionQueueWorker loop started")
LEGACY_BANNER_INFO = "DetectionQueueWorker loop started"
# L433: logger.info("DetectionQueueWorker loop cancelled")
CANCELLED_INFO = "DetectionQueueWorker loop cancelled"
# L450-453: logger.info("DetectionQueueWorker loop exited",
#                       extra={"items_processed": self._stats.items_processed})
EXIT_INFO = "DetectionQueueWorker loop exited"
# L442: f"Error in DetectionQueueWorker loop: {e}"
ERROR_INFO_TPL = "Error in DetectionQueueWorker loop: {}"
# L439 categorize_exception(<ConnectionError>, "detection") -> the L156-164 name tuple
# fires first, so the shipped label is f"{worker_name}_connection_error".
ERROR_LABEL = "detection_connection_error"
# L401: await stream_service.claim_stale_messages(consumer_name, count=5)
CLAIM_COUNT = 5
# L404: await stream_service.move_to_dlq(msg, "max_delivery_exceeded")
DLQ_REASON = "max_delivery_exceeded"
# L403 compares the claimed message's delivery_count against
# stream_service._max_delivery_count; this file injects that threshold.
DLQ_THRESHOLD = 3
# L447: await asyncio.sleep(1.0)
ERROR_DELAY = 1.0
# WorkerState values as the shipped WorkerStats.to_dict() renders them (L212-219); a
# fresh WorkerStats starts STOPPED (L210).
STATE_STOPPED = "stopped"
STATE_RUNNING = "running"
STATE_ERROR = "error"


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

    ``record.msg`` is the RAW message and ``args`` must stay empty (every shipped site in
    this group is an already-interpolated f-string or a constant).  ``exc_info`` is pinned
    separately by the legs that reach the L441-445 ERROR call.
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

    The union of (a) the fields ``logging.LogRecord.__init__`` always sets and (b) the
    fields this module's ``ContextFilter`` injects - (b) MEASURED, since the filter is
    idempotent, so running it over a record it has already seen adds exactly the injected
    names once.  ``message`` is excluded: the formatter sets it.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The ``extra=`` dict the shipped call passed, as the record shows it.

    ``Logger.makeRecord`` copies ``extra`` into the record verbatim, so removing the
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

    ``now - baseline`` is ``0.0``, so neither the 20 s heartbeat nor the 30 s claim gate
    opens - which is what keeps a consume / legacy leg owned by its own keys.  ``reads`` is
    still counted and pinned: it is the observable that catches a removed read, an added
    read and both gate flips.
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

    ``time()`` returns ``steps[i]`` for read ``i`` and repeats the last value, so a leg can
    step the clock by exactly the shipped heartbeat / claim period per iteration and pin
    the read count alongside the behaviour.
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

    ``item`` is what the BLPOP read returns (a dict for a real item, ``None`` for an idle
    timeout); ``messages`` is what ``consume_detections`` returns; ``claims`` is what
    ``claim_stale_messages`` returns, with ``None`` meaning THIS pass must not ask the gate
    at all (the stub then raises loudly); ``raises`` replaces the read's result with a
    failure - a plain ``Exception`` for the error arm, ``asyncio.CancelledError`` as the
    sentinel that ends the drive through the shipped ``break``.
    """

    item: Any = None
    messages: list[Any] = field(default_factory=list)
    claims: list[Any] | None = None
    raises: BaseException | None = None


@dataclass
class Run:
    """One scripted drive, its clock script, and everything it observed.

    ``clock`` is the script handed to ``clock_kind`` - the object installed as the shipped
    module's ``time_module`` alias.  A one-element script (the ``ConstantTimeModule`` legs)
    freezes the clock so neither gate opens; a multi-element script (``ScriptedTimeModule``)
    answers read ``i`` with ``clock[i]`` and then repeats its last value.  The shipped body
    reads the alias at L381 (``last_heartbeat``) and L385 (``last_claim_check``) up front,
    then at L392 once per iteration when a supervisor is present and at L399 once per
    iteration in streams mode - so the read COUNT is pinned too.
    """

    passes: list[Pass]
    clock: list[float] = field(default_factory=lambda: [0.0])
    clock_kind: Any = ConstantTimeModule
    use_streams: bool = False
    build_service: bool = True
    supervisor: Any = None
    queue_name: str = "detection_queue-b28"
    poll_timeout: int = 7
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

        The shipped body performs the driving read (L401 claim / L411 consume / L422 BLPOP)
        exactly ONCE per iteration, so a NEW call means a NEW pass.  Advancing on a SLEEP
        would be wrong: the streams arm and the idle legacy pass never sleep.  A mutant
        that iterates past the script gets a loud ``AssertionError`` inside the shipped
        ``try``, which reddens the leg's pinned INFO / stats surface.
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

    ``create_autospec(DetectionQueueWorker)`` enforces every method signature; its
    ``_run_loop`` AsyncMock is NEVER awaited.  Every attribute the loop resolves through
    ``self`` is this file's, carrying the values the pins assert: ``_redis`` is an
    autospec'd ``RedisClient`` whose ``get_from_queue`` serves the item script,
    ``_queue_name`` / ``_poll_timeout`` are the leg's own (deliberately NOT the shipped
    defaults L242-243, so an argument mutation cannot alias them), ``_worker_name`` is the
    shipped constructor default (L246), ``_stats`` a real shipped ``WorkerStats()`` and
    ``_process_detection_item`` an instance-level ``AsyncMock`` spy - an instance attribute
    beats the class attribute in every world, including a replay mutant's re-sourced class.
    """
    worker = create_autospec(DetectionQueueWorker).return_value
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
    worker._queue_name = run.queue_name
    worker._poll_timeout = run.poll_timeout
    worker._stop_timeout = 10.0
    worker._supervisor = run.supervisor
    worker._worker_name = "detection"
    worker._running = True
    worker._task = None
    worker._stats = WorkerStats()
    # The instance-level AsyncMock is the processing spy.  Its recorded call ARGS carry the
    # exact object the shipped call passed, so a leg can pin both the VALUE and the
    # IDENTITY (.args[0] is expected) - the latter is what a
    # ``_process_detection_item(None)`` mutation cannot satisfy.
    worker._process_detection_item = AsyncMock(name="process-detection-item")
    return worker


def make_stream_service(run: Run) -> Any:
    """autospec'd ``DetectionStreamService`` instance serving the stream script.

    ``_max_delivery_count`` is a real int (L403 compares the claimed message's
    ``delivery_count`` against it) and every read yields to the loop.

    ``claim_stale_messages`` does NOT advance the pass index - the shipped gate (L400)
    opens at most once per iteration and the iteration's own read (L411) is what marks a
    new pass.  The pass' ``claims`` field is the answer, and ``None`` means this pass must
    not reach the gate: the stub then raises inside the shipped ``try``, which reddens the
    leg's zero-error pins.
    """
    service = create_autospec(DetectionStreamService).return_value
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
        # Return the scripted objects WITHOUT copying, so the shipped call hands
        # ``move_to_dlq`` / ``should_move_to_dlq`` the very message this leg built and the
        # ``call(message)`` pins below can compare by identity.
        return claims

    async def consume_detections(*args: Any, **kwargs: Any) -> list[Any]:
        if run.calls > PASS_CEILING:
            raise RuntimeError("the loop iterated more times than any shipped path can")
        scripted_pass = run.next_pass()
        await _REAL_SLEEP(0)
        if scripted_pass.raises is not None:
            raise scripted_pass.raises
        return list(scripted_pass.messages)

    async def stale_goes_to_dlq(msg: Any, *_a: Any, **_k: Any) -> bool:
        # The shipped gate at L403 is ``if await stream_service.should_move_to_dlq(msg):``.
        # An autospec'd AsyncMock answers a truthy Mock, which would send EVERY claimed
        # message down the DLQ branch; answering with the shipped predicate's own shape
        # (``delivery_count >= self._max_delivery_count``, redis_streams.py:677-686) keeps
        # the else-branch (process + acknowledge, where the m44/m45 twins live) reachable.
        return msg.delivery_count >= DLQ_THRESHOLD

    service.claim_stale_messages.side_effect = claim_stale_messages
    service.consume_detections.side_effect = consume_detections
    service.should_move_to_dlq.side_effect = stale_goes_to_dlq
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
    # build_service=False drives the SHIPPED `stream_service is None` state inside streams
    # mode (L368 declares None, L372 writes whatever the factory returns): the factory is
    # made to answer None - not an autospec'd mock, which would be non-None and defeat the
    # whole point of the leg.
    service = make_stream_service(run) if (run.use_streams and run.build_service) else None

    sleep_double = autospec_of(_REAL_SLEEP)

    async def sleep_side_effect(delay: float, *_args: Any, **_kwargs: Any) -> None:
        """Records the delay and stops a runaway loop.

        Every leg really ends on its sentinel pass' ``CancelledError`` -> shipped ``break``,
        so the shipped loop never reaches L447 here at all.  A MUTANT can reach it
        repeatedly: the L397 ``and`` -> ``or`` flip, for instance, sends a
        ``stream_service is None`` drive into the streams arm, where
        ``None.consume_detections`` raises ``AttributeError`` on every iteration and the
        error arm sleeps forever.  This backstop turns that into a bounded drive whose log
        surface the pins then reject, instead of a hang.
        """
        run.sleeps.append(delay)
        if len(run.sleeps) > run.sleep_limit or run.calls > PASS_CEILING:
            worker._running = False

    sleep_double.side_effect = sleep_side_effect

    settings = create_autospec(Settings, instance=True)
    settings.use_redis_streams = run.use_streams
    get_settings = autospec_of(M.get_settings)
    get_settings.return_value = settings

    factory = autospec_of(M.get_detection_stream_service)
    factory.return_value = service

    record_error = autospec_of(M.record_pipeline_error)
    # L437 writes the ERROR state and L448 restores RUNNING, so the ONLY place the shipped
    # L437 write is observable is inside the L440 record_pipeline_error call between them.
    # Snapshot it there, through the shipped WorkerStats.to_dict() - which is also what
    # makes m62 (state = None) raise instead of passing silently.
    record_error.side_effect = lambda _error_type: run.states_at_error_call.append(
        worker._stats.to_dict()["state"]
    )

    run.hb_module = run.clock_kind(*run.clock)
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(M, "time_module", new=run.hb_module))
        stack.enter_context(patch.object(M, "get_settings", new=get_settings))
        stack.enter_context(patch.object(M, "get_detection_stream_service", new=factory))
        stack.enter_context(patch.object(M, "record_pipeline_error", new=record_error))
        stack.enter_context(patch.object(asyncio, "sleep", new=sleep_double))
        await M.DetectionQueueWorker._run_loop(worker)
        yield (
            worker,
            {"record_pipeline_error": record_error, "asyncio.sleep": sleep_double},
            service,
            factory,
        )


def message(
    msg_id: str,
    *,
    camera_id: str,
    detection_id: int,
    file_path: str,
    delivery_count: int = 1,
) -> DetectionStreamMessage:
    """A REAL shipped ``DetectionStreamMessage`` (a dataclass, not a mock).

    Its ``raw_data`` (redis_streams.py:178) is the value the shipped loop forwards to
    ``_process_detection_item`` at both L406 and L418, and its ``id`` is what L407 / L419
    acknowledges - so the pins assert the shipped dataclass and not a mock's echo.
    """
    return DetectionStreamMessage(
        id=msg_id,
        camera_id=camera_id,
        detection_id=detection_id,
        file_path=file_path,
        delivery_count=delivery_count,
        raw_data={
            "camera_id": camera_id,
            "detection_id": str(detection_id),
            "file_path": file_path,
        },
    )


CANCEL = asyncio.CancelledError


# =============================================================================
# 1) streams mode: the banner family, the consumer_name family, the factory,
#    the consume-call family and the consume for-body (m4, m5, m7, m8, m9, m10,
#    m11, m12, m15, m16, m34, m35, m37, m44@L418, m45@L419, m6 positively)
# =============================================================================


async def test_streams_mode_builds_the_service_announces_the_consumer_and_consumes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:364-419 + L450 in STREAMS mode (``use_redis_streams`` True).

    ::

        settings = get_settings()                                    # L366
        use_streams = settings.use_redis_streams                     # L367
        stream_service: DetectionStreamService | None = None         # L368
        consumer_name = f"detection-worker-{id(self)}"               # L369
        if use_streams:                                              # L371
            stream_service = await get_detection_stream_service(self._redis)  # L372
            logger.info(                                             # L374-376
                "DetectionQueueWorker loop started (Redis Streams mode)",
                extra={"consumer_name": consumer_name},
            )
        ...
                if use_streams and stream_service is not None:       # L397
                    messages = await stream_service.consume_detections(
                        consumer_name, count=1, block=True           # L411-413
                    )
                    if not messages:                                 # L414
                        continue                                     # L415
                    for msg in messages:                             # L417
                        await self._process_detection_item(msg.raw_data)  # L418
                        await stream_service.acknowledge(msg.id)     # L419

    16 keys live here.  The banner is ONLY reachable in this mode, so its message
    (m8/m10/m12) and payload (m9/m11/m15/m16) die here - and the payload VALUE is the
    shipped ``f"detection-worker-{id(worker)}"``, which is also what kills m4 (``consumer_name
    = None``) and m5 (``id(None)``).  The same value is pinned as ``consume_detections``'
    positional (m34/m37) with ``count=1`` (m35) and ``block=True``.  The factory call's
    argument IDENTITY kills m7, and its existence plus the consume-call pin kill m6 (whose
    ``stream_service = None`` silently turns this drive legacy).  The ``for`` body is pinned
    with the REAL ``raw_data`` dict of a real shipped message on both passes (m44) and the
    two stream ids in order (m45), and ``_process_detection_item``/``acknowledge`` are the
    ONLY processing that happens: ``items_processed`` stays 0 because the shipped loop never
    increments it on this path.
    """
    run = Run(
        passes=[
            Pass(
                messages=[message("1-0", camera_id="cam-3", detection_id=11, file_path="/d/1.jpg")]
            ),
            Pass(
                messages=[message("2-0", camera_id="cam-4", detection_id=21, file_path="/d/2.jpg")]
            ),
            Pass(raises=CANCEL()),
        ],
        # ConstantTimeModule: every read identical, so elapsed is 0.0 and NEITHER the 20 s
        # heartbeat nor the 30 s claim gate opens.
        clock=[0.0],
        use_streams=True,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, service, factory):
        stats = worker._stats.to_dict()

    consumer_name = f"detection-worker-{id(worker)}"
    assert factory.await_count == 1, f"the stream service was built {factory.await_count} times"
    assert factory.await_args is not None
    assert factory.await_args.args == (worker._redis,), (
        f"get_detection_stream_service argument mutated: {factory.await_args!r}"
    )
    assert not factory.await_args.kwargs, (
        f"the factory takes one positional: {factory.await_args!r}"
    )

    consume_calls = service.consume_detections.await_args_list
    assert consume_calls == [
        call(consumer_name, count=1, block=True),
        call(consumer_name, count=1, block=True),
        call(consumer_name, count=1, block=True),
    ], f"consume_detections mutated: {consume_calls!r}"
    assert service.claim_stale_messages.await_count == 0, (
        "the 30-second claim gate must stay shut while the clock does not advance"
    )
    fresh = [
        {"camera_id": "cam-3", "detection_id": "11", "file_path": "/d/1.jpg"},
        {"camera_id": "cam-4", "detection_id": "21", "file_path": "/d/2.jpg"},
    ]
    processed = worker._process_detection_item.await_args_list
    assert processed == [call(fresh[0]), call(fresh[1])], (
        f"_process_detection_item / msg.raw_data mutated: {processed!r}"
    )
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

    pin_levels(caplog, [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(
        caplog,
        logging.INFO,
        [{"consumer_name": consumer_name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [], "the streams arm never sleeps"
    assert doubles["record_pipeline_error"].call_count == 0
    assert run.heartbeat_reads() == 5, (
        "L381 + L385 baselines plus one L399 read on every one of the three iterations "
        "(the sentinel pass reads the gate clock before its read raises): "
        f"{run.heartbeat_reads()}"
    )


# =============================================================================
# 2) the stale-claim gate (m25, m30@L399, m31, m32) + the claim for-body
#    (m44@L406, m45@L407) + the DLQ routing control
# =============================================================================


async def test_the_stale_claim_gate_fires_once_per_shipped_30_second_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:385-408 - claim stale messages once per 30.0 s of alias clock.

    ::

        last_claim_check = time_module.time()                      # L385 -> 1000.0
        claim_interval = 30.0                                      # L386
        ...
                if use_streams and stream_service is not None:     # L397
                    now = time_module.time()                       # L399
                    if now - last_claim_check >= claim_interval:   # L400
                        claimed = await stream_service.claim_stale_messages(
                            consumer_name, count=5                 # L401
                        )
                        for msg in claimed:                        # L402
                            if await stream_service.should_move_to_dlq(msg):
                                await stream_service.move_to_dlq(msg, "max_delivery_exceeded")
                            else:
                                await self._process_detection_item(msg.raw_data)   # L406
                                await stream_service.acknowledge(msg.id)           # L407
                        last_claim_check = now                     # L408

    The alias is scripted ``1000.0 -> 1000.0 -> 1000.0 -> 1030.0 -> 1030.0`` (the L381 and
    L385 baselines share the first value).  A NON-ZERO baseline is load-bearing: at
    ``last_claim_check == 0.0`` the shipped difference and m31's ``now + last_claim_check``
    coincide, so with a zero baseline m31 would be unobservable.  Pass 1 (``now`` 1000.0,
    elapsed 0.0) must NOT claim - m31 DOES claim there (``1000.0 + 1000.0 >= 30.0``).  Pass
    2 (``now`` 1030.0, elapsed EXACTLY 30.0) is the ``>=`` boundary: shipped claims, m32's
    ``>`` does not.  ``claim_interval = None`` (m25) and ``now = None`` (m30) raise
    ``TypeError`` inside the shipped ``try`` and land in the error arm, which the zero-error
    pins reject.

    NO supervisor is installed, so L391's gate body never runs and the five alias reads are
    ONLY ever the two baselines plus the three L399 gate reads - which is what makes this
    leg the sole owner of the m30 twin at L399.

    Pass 2's claim returns one message AT the injected delivery limit (routed to the DLQ
    with the shipped reason) and one BELOW it (processed through its shipped ``raw_data``
    and acknowledged by id) - so entering the streams arm is never enough: what the claim
    yields must be routed correctly, and that pair is this leg's OWN ``_process_detection_item``
    / ``acknowledge`` call list (the m44/m45 twins at L406/L407).  Pass 1 and pass 3 script
    ``claims=None``, so any claim the shipped gate should not make raises inside the shipped
    ``try`` and shows up as an ERROR record plus a non-zero ``errors`` count.  Both gated
    passes return NO new messages from ``consume_detections``, so ``if not messages:
    continue`` (L414-415) is what ends them.
    """
    over_limit = message(
        "9-0",
        camera_id="cam-9",
        detection_id=5,
        file_path="/d/old.jpg",
        delivery_count=DLQ_THRESHOLD,
    )
    claimable = message(
        "9-1",
        camera_id="cam-8",
        detection_id=6,
        file_path="/d/stale.jpg",
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

    consumer_name = f"detection-worker-{id(worker)}"
    assert service.claim_stale_messages.await_args_list == [
        call(consumer_name, count=CLAIM_COUNT)
    ], f"claim gate contract mutated: {service.claim_stale_messages.await_args_list!r}"
    assert service.should_move_to_dlq.await_args_list == [call(over_limit), call(claimable)], (
        f"delivery-limit probe mutated: {service.should_move_to_dlq.await_args_list!r}"
    )
    assert service.move_to_dlq.await_args_list == [call(over_limit, DLQ_REASON)], (
        f"DLQ routing mutated: {service.move_to_dlq.await_args_list!r}"
    )
    processed = worker._process_detection_item.await_args_list
    assert processed == [call(claimable.raw_data)], (
        f"claimed-message processing mutated: {processed!r}"
    )
    assert service.acknowledge.await_args_list == [call("9-1")], (
        f"acknowledge after a claim mutated: {service.acknowledge.await_args_list!r}"
    )
    assert service.consume_detections.await_count == 3, (
        "one consume read per iteration INCLUDING the sentinel pass, whose read raises"
    )
    assert worker._redis.get_from_queue.await_count == 0, (
        "streams mode must never touch the legacy BLPOP arm"
    )
    assert stats["errors"] == 0, f"the claim gate must not error: {stats!r}"
    assert stats["items_processed"] == 0
    pin_levels(caplog, [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(
        caplog,
        logging.INFO,
        [{"consumer_name": consumer_name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    assert run.sleeps == []
    assert run.heartbeat_reads() == 5, (
        "L381 + L385 baselines plus one L399 read per iteration (3 iterations): "
        f"{run.heartbeat_reads()}"
    )


# =============================================================================
# 2b) the claim gate's FAILURE surface: the second, independently-valued route to
#     m25 / m30@L399 / m31 (a gate that must NOT open)
# =============================================================================


async def test_an_unanswered_stale_claim_attempt_reaches_the_error_arm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:399-408 + L435-448 when the claim attempt itself fails.

    The claim legs' zero-error pins read m25 and the m30 twin only as "something raised",
    so this leg states the other half of the contract: with the alias pinned so
    ``now - last_claim_check`` is ``0.0`` on every pass, shipped must NEVER reach
    ``claim_stale_messages`` at all - and here that stub answers a hypothetical attempt with
    an ``AssertionError`` inside the shipped ``try``.  The shipped loop therefore performs NO
    claim, so nothing can error: zero ERROR records, zero sleeps, zero pipeline errors,
    ``errors == 0``, state ``stopped``, and four consume reads including the sentinel.

    Under m25 (``claim_interval = None``) or m30 (``now = None``) the L400 comparison raises
    ``TypeError`` on EVERY iteration, and under m31 (``now + last_claim_check``) it is
    ``0.0 + 0.0 >= 30.0`` - False on the shipped clock, so m31 stays home here and is killed
    by the stepping leg above.  Either way this leg's pins are violated by exactly the
    ERROR/sleep surface the shipped loop cannot produce on a frozen clock.
    """
    run = Run(
        passes=[
            Pass(messages=[], claims=None),
            Pass(messages=[], claims=None),
            Pass(messages=[], claims=None),
            Pass(raises=CANCEL()),
        ],
        clock=[400.0],
        use_streams=True,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, service, _factory):
        stats = worker._stats.to_dict()

    consumer_name = f"detection-worker-{id(worker)}"
    assert service.claim_stale_messages.await_count == 0, (
        "a frozen clock must never open the 30-second claim gate"
    )
    assert service.consume_detections.await_count == 4, (
        f"one consume read per scripted pass, sentinel included: "
        f"{service.consume_detections.await_count}"
    )
    assert worker._process_detection_item.await_count == 0
    assert service.acknowledge.await_count == 0
    assert worker._redis.get_from_queue.await_count == 0
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"the shipped WorkerStats.to_dict() surface mutated: {stats!r}"
    assert doubles["record_pipeline_error"].call_count == 0, (
        "the shipped gate never opens here, so the error arm must never run"
    )
    pin_levels(caplog, [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(
        caplog,
        logging.INFO,
        [{"consumer_name": consumer_name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == []
    assert run.heartbeat_reads() == 6, (
        "L381 + L385 baselines plus one L399 read per iteration on the frozen clock: "
        f"{run.heartbeat_reads()}"
    )


# =============================================================================
# 3) legacy mode: the banner family, the BLPOP read family, the idle/item alternation
#    (m6 as a mode pin, m17, m20, m28, m29 via the falsy side, m46, m48, m49, m50,
#    m51, m52@L428, m53)
# =============================================================================


async def test_legacy_mode_reads_the_queue_by_name_processes_and_survives_idle_reads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:364-378 + L420-430 with ``use_redis_streams`` False.

    ::

        else:
            logger.info("DetectionQueueWorker loop started")           # L378
        ...
            else:
                # Legacy list-based queue (BLPOP)
                item = await self._redis.get_from_queue(               # L422-425
                    self._queue_name,
                    timeout=self._poll_timeout,
                )
                if item is None:                                       # L427
                    continue                                           # L428
                await self._process_detection_item(item)               # L430

    Four scripted passes: item / idle / second item / sentinel.  The BLPOP call list is
    pinned to four identical ``call("detection_queue-b28", timeout=7)`` records using THIS
    file's injected attribute values (deliberately NOT the shipped defaults), so m49 (queue
    name -> ``None`` and the argument drop, whose survivor diff covers both), m48
    (``timeout=None``), m50 (the ``timeout`` line dropped) and m46 (the whole read replaced
    by ``item = None``) all show up - the last one empties the list while still claiming an
    item was processed.  The alternating idle pass is what reads m51 and the m52 twin:
    shipped skips processing and LOOPs, the flip processes ``None``, and ``break`` leaves the
    loop early - both caught by the exact processed-item list and read count.  m53's ``None``
    argument cannot match the injected dict's identity.  The legacy banner text is pinned
    because only this mode reaches L378 (m17/m20), and m28 is read from the falsy side: the
    leg installs a REAL autospec'd service object, so a truthy service plus a falsy flag must
    still take this arm.
    """
    first = {"camera_id": "cam-1", "file_path": "/d/a.jpg", "media_type": "image"}
    second = {"camera_id": "cam-2", "file_path": "/d/b.jpg", "media_type": "video"}
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
        queue_name="detection_queue-b28",
        poll_timeout=7,
    )
    win(caplog)

    async with scripted(run) as (worker, _doubles, _service, factory):
        stats = worker._stats.to_dict()

    redis = worker._redis
    assert redis.get_from_queue.await_count == 4, (
        f"one BLPOP read per iteration: {redis.get_from_queue.await_count}"
    )
    assert redis.get_from_queue.await_args_list == [
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
    ], f"the BLPOP call shape mutated: {redis.get_from_queue.await_args_list!r}"
    assert worker._process_detection_item.await_args_list == [call(first), call(second)], (
        f"_process_detection_item mutated: {worker._process_detection_item.await_args_list!r}"
    )
    assert worker._process_detection_item.await_args_list[0].args[0] is first, (
        "the processed item must be the object the read returned, not a stand-in"
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
    pin_levels(caplog, [], logging.WARNING)
    assert run.sleeps == [], "neither the item nor the idle legacy pass sleeps"
    assert run.heartbeat_reads() == 2, (
        "exactly the L381 + L385 baselines: no supervisor means no L392 read, and legacy "
        f"mode short-circuits L397 on use_streams so there is no L399 read: "
        f"{run.heartbeat_reads()}"
    )


# =============================================================================
# 3b) the legacy idle pass as a control on the m52 twin at L428 with a DIFFERENT
#     clock and a different call list (second, independently-valued route)
# =============================================================================


async def test_five_idle_legacy_reads_keep_the_loop_reading_without_processing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:427-428 restated with an all-idle script: five reads, zero processing.

    The legacy leg above interleaves items with the idle pass; this one has FIVE idle reads
    before the sentinel, so the ``continue`` (L428) is the only thing that can keep the loop
    alive: under m52's ``break`` the drive ends after the FIRST idle read and the five-record
    BLPOP list, the read count and the exit payload all go red.  The clock is a different
    constant (``250.0``) and the queue name/timeout differ from every other leg, so nothing
    here can be re-explained by another leg's script.  m51 is visible too - the flip would
    hand ``None`` to the processor five times.
    """
    run = Run(
        passes=[
            Pass(item=None),
            Pass(item=None),
            Pass(item=None),
            Pass(item=None),
            Pass(item=None),
            Pass(raises=CANCEL()),
        ],
        clock=[250.0],
        use_streams=False,
        supervisor=None,
        queue_name="detection_queue-b28-idle",
        poll_timeout=2,
    )
    win(caplog)

    async with scripted(run) as (worker, _doubles, _service, _factory):
        stats = worker._stats.to_dict()

    assert worker._redis.get_from_queue.await_count == 6, (
        f"one BLPOP read per iteration, sentinel included: "
        f"{worker._redis.get_from_queue.await_count}"
    )
    assert (
        worker._redis.get_from_queue.await_args_list
        == [call("detection_queue-b28-idle", timeout=2)] * 6
    ), f"the BLPOP call shape mutated: {worker._redis.get_from_queue.await_args_list!r}"
    assert worker._process_detection_item.await_count == 0, (
        "an idle read must skip processing, not process None"
    )
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"stats mutated: {stats!r}"
    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"items_processed": 0}])
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == []
    assert run.heartbeat_reads() == 2, run.heartbeat_reads()


# =============================================================================
# 4) the heartbeat gate (m21, m22, m23, m27, m30@L392) - the ONLY leg whose shipped
#    run evaluates the heartbeat comparison
# =============================================================================


def supervisor_double() -> Any:
    """autospec'd instance double of the shipped ``WorkerSupervisor``."""
    return create_autospec(WorkerSupervisor).return_value


async def test_the_detection_heartbeat_fires_once_per_shipped_20_second_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:380-395 - one ``record_heartbeat(worker_name)`` per 20.0 s of clock.

    ::

        last_heartbeat = time_module.time()        # read 1 -> 0.0
        heartbeat_interval = 20.0                  # the shipped constant (L382)
        while self._running:
            try:
                if self._supervisor is not None:                    # L391
                    now = time_module.time()                        # L392
                    if now - last_heartbeat >= heartbeat_interval:  # L393
                        self._supervisor.record_heartbeat(self._worker_name)
                        last_heartbeat = now

    LEGACY mode, so the claim gate's reads cannot blur the count.  The alias walks
    ``0.0 (L381 baseline) -> 0.0 (L385 claim baseline, unused here) -> 20.0 -> 40.0 ->
    60.0``: EVERY gated pass advances EXACTLY 20.0 s from the previous beat, so the shipped
    ``>=`` fires on all three iterations (the sentinel pass pays its gate read before its
    queue read raises) - ``[detection, detection, detection]``.  m23 (``21.0``) can never
    keep pace with a 20 s step: pass 1 is short (20.0 >= 21.0 is False), pass 2 beats from
    the UNMOVED baseline (40.0 - 0.0), pass 3 is short again (20.0 < 21.0) - exactly ONE
    beat, a different call list.  (A coarser script - a first gate already past 21.0 - would
    let the mutant beat once and match shipped; that is the vacuity this script avoids.)
    Under m21 (``last_heartbeat = None``), m22 (``heartbeat_interval = None``) or the L392
    twin of m30 (``now = None``) the comparison raises ``TypeError`` inside the shipped
    ``try`` and turns every iteration into the error arm, which the zero-ERROR pin rejects.
    Under the m27 flip the arm never runs for a present supervisor: zero beats and TWO reads
    instead of five.  The call argument is the shipped default worker name (L246 / L296).
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
        call("detection"),
        call("detection"),
        call("detection"),
    ], f"heartbeat contract mutated: {supervisor.record_heartbeat.call_args_list!r}"
    assert run.heartbeat_reads() == 5, (
        "L381 baseline, L385 baseline, plus one L392 gate read in every one of the three "
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
# 4b) the heartbeat gate made live in a leg that ALSO pins the BLPOP arm - a
#     heartbeat mutant must not be able to trade the arm away
# =============================================================================


async def test_a_supervisor_present_in_legacy_mode_never_touches_the_legacy_queue(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:390-397 with a supervisor in legacy mode: the gates stay independent.

    A supervisor IS present, so L392 reads the alias on each of the three iterations, and
    ``use_streams`` is False, so L397 short-circuits on its first conjunct and every
    iteration must read the BLPOP queue - never the stream service, which this leg does
    install as a real object.  The point of the leg is the pair of pins TOGETHER: the
    heartbeat gate runs (one alias read per iteration, on top of the two baselines) AND the
    BLPOP call list keeps its two shipped-shape records AND ``consume_detections`` is never
    awaited.  A mutant that reaches the streams arm here - the m28 ``and`` -> ``or`` flip
    being the obvious one - loses the BLPOP pins and the factory-never-awaited pin at once,
    and one that breaks the heartbeat arithmetic lands in the error arm and loses the
    zero-ERROR pin.
    """
    item = {"camera_id": "cam-7", "file_path": "/d/e.jpg", "media_type": "image"}
    run = Run(
        passes=[Pass(item=item), Pass(raises=CANCEL())],
        clock=[300.0],
        use_streams=False,
        supervisor=supervisor_double(),
        queue_name="detection_queue-b28-hb",
        poll_timeout=11,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, _service, factory):
        stats = worker._stats.to_dict()

    assert factory.await_count == 0, "legacy mode must never build the stream service"
    assert worker._redis.get_from_queue.await_args_list == [
        call("detection_queue-b28-hb", timeout=11),
        call("detection_queue-b28-hb", timeout=11),
    ], f"the BLPOP call list mutated: {worker._redis.get_from_queue.await_args_list!r}"
    assert worker._process_detection_item.await_args_list == [call(item)]
    assert run.heartbeat_reads() == 4, (
        "L381 + L385 baselines plus one L392 gate read in each of the two iterations: "
        f"{run.heartbeat_reads()}"
    )
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"stats mutated: {stats!r}"
    assert doubles["record_pipeline_error"].call_count == 0
    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"items_processed": 0}])
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == []


# =============================================================================
# 5) control: no supervisor -> the gate body never runs (m27 and the m30 twin at L392
#    from the other side)
# =============================================================================


async def test_an_unsupervised_detection_worker_never_reads_the_heartbeat_clock(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:391 - ``if self._supervisor is not None:`` with NO supervisor.

    Two idle legacy passes read the alias exactly TWICE - the L381 and L385 baselines -
    because the gate body is skipped every iteration.  The m27 flip runs the arm anyway, so
    the read count grows, and the L392 twin of m30 makes that extra read ``None`` and
    raises - either way this leg goes red.  The zero-beat and zero-error pins state the rest
    of that arm's absence.
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
# 6) the ``except Exception`` arm (m60, m61, m62, m63, m64, m65) - sole route
# =============================================================================


async def test_two_failures_count_incrementally_and_report_the_shipped_label(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:435-448 over two failing reads, then the sentinel.

    ::

        except Exception as e:
            self._stats.errors += 1                              # L436
            self._stats.state = WorkerState.ERROR                # L437
            error_type = categorize_exception(e, "detection")    # L439
            record_pipeline_error(error_type)                    # L440
            logger.error(
                f"Error in DetectionQueueWorker loop: {e}",       # L442
                exc_info=True,                                    # L443
                extra={"error_count": self._stats.errors, "error_type": error_type},  # L444
            )
            await asyncio.sleep(1.0)                              # L447
            self._stats.state = WorkerState.RUNNING               # L448

    6 keys live here.  ``errors`` is pinned ACROSS two failures - shipped 1 then 2 - so
    m60's ``-= 1`` and m61's ``+= 2`` both show up in the payload pair and in the final
    stats.  ``record_pipeline_error`` is pinned with the EXACT shipped label: m63 hands over
    ``None``, m64 (``categorize_exception(None, "detection")``) does NOT raise - it falls
    through every branch to ``"detection_processing_error"`` - and m65's ``None`` worker
    name yields ``"None_connection_error"``.  The state is read INSIDE the L440 call (the
    only place L437 is visible; m62 makes the shipped ``to_dict()`` raise ``AttributeError``
    right there) and after the pass through the shipped ``to_dict()`` as ``"running"`` -
    which is only reached because the failed pass slept the shipped ``1.0``.
    """
    first = builtins.ConnectionError("detection queue connection reset")
    second = builtins.ConnectionError("detection pool exhausted, cannot CONNECT")
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
        f"the L437 ERROR state must be live inside record_pipeline_error: {states!r}"
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
    assert worker._process_detection_item.await_count == 0, "a failing pass processes nothing"

    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(caplog, logging.INFO, [{}, {}, {"items_processed": 0}])
    pin_levels(
        caplog,
        [ERROR_INFO_TPL.format(first), ERROR_INFO_TPL.format(second)],
        logging.ERROR,
    )
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
    assert run.sleeps == [ERROR_DELAY, ERROR_DELAY], "the failed pass sleeps the shipped 1.0 s"
    assert run.heartbeat_reads() == 2, run.heartbeat_reads()


async def test_the_iteration_after_a_failure_reads_the_queue_again_and_stays_running(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second, independently-valued route: one failure, then a real item.

    This is the leg that pins the ERROR arm's SURVIVAL contract - the state has to be back
    to ``running`` AND the next iteration has to read the queue and process the item it
    returns - so the error family cannot be satisfied by a drive that only ever fails.  The
    ERROR payload's ``error_count`` is the FIRST failure's count here, which the accumulating
    ``+= 1`` (L436) pins a second time from a different angle (m60's ``-= 1`` and m61's
    ``+= 2`` both break this payload as well as the pair above).
    """
    err = builtins.ConnectionError("detection read timeout on BLPOP")
    item = {"camera_id": "cam-5", "file_path": "/d/c.jpg", "media_type": "image"}
    run = Run(
        passes=[Pass(raises=err), Pass(item=item), Pass(raises=CANCEL())],
        clock=[1500.0],
        use_streams=False,
        supervisor=None,
        queue_name="detection_queue-b28",
        poll_timeout=7,
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
    assert worker._process_detection_item.await_args_list == [call(item)]
    assert worker._redis.get_from_queue.await_args_list == [
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
    ], "the loop must re-read the queue after a failure"
    pin_levels(caplog, [LEGACY_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_levels(caplog, [ERROR_INFO_TPL.format(err)], logging.ERROR)
    pin_payloads(caplog, logging.ERROR, [{"error_count": 1, "error_type": ERROR_LABEL}])
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [ERROR_DELAY], run.sleeps


# =============================================================================
# 7) control: the CancelledError arm (m54, m56, m57, m58)
# =============================================================================


async def test_a_cancelled_read_logs_the_cancelled_info_then_the_exit_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:432-434 + L450 - ``except asyncio.CancelledError``: INFO then ``break``.

    The ordered INFO triple ``[legacy banner, cancelled, exited]`` is the whole contract,
    and it is what kills the three message mutants at L433 (m54/m56/m57) and m58: replacing
    the ``break`` with ``return`` skips the L450 exit INFO entirely, so the surface loses its
    third record.  Nothing else happens on this drive - no processing, no sleep, no error, no
    ERROR record - which is what stops the ERROR and claim surfaces of the other legs from
    being re-explained by this arm.
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
    assert worker._process_detection_item.await_count == 0
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
# 8a) streams mode with NO service object: the L397 conjunct decides the arm
#     (m28 ``and`` -> ``or``, m29 ``is not None`` -> ``is None``; m6 as the state)
# =============================================================================


async def test_streams_mode_without_a_service_object_still_uses_the_legacy_queue(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:397 - ``if use_streams and stream_service is not None:``.

    The one drive where the two conjuncts DISAGREE: ``use_streams`` is True (so the STREAMS
    banner fired at L374 and the factory was awaited at L372) but what the factory returned
    was ``None``, so the shipped conjunction is False and every iteration must read the
    LEGACY queue.  This is a reachable shipped state - L368 declares ``stream_service =
    None`` and L372 writes whatever the factory hands back.

    * m28 (``and`` -> ``or``): ``True or ...`` is True, so the mutant enters the streams arm
      and calls ``None.consume_detections(...)`` - an ``AttributeError`` on every iteration.
      Its ERROR surface and its ``asyncio.sleep(1.0)`` per failed pass are exactly what the
      pins here forbid, and the sleep-count backstop keeps such a mutant bounded instead of
      hanging.
    * m29 (``stream_service is not None`` -> ``is None``): ``True and True`` is True, so it
      enters the same arm and dies the same way.
    * The shipped path is pinned positively too: the BLPOP call list carries the worker's own
      queue name and timeout across FOUR idle reads, the legacy banner is ABSENT (this drive
      is in streams mode - the streams banner fired instead) and the factory call is still
      pinned, so the leg cannot be satisfied by a drive that simply forgot about streams.
    """
    run = Run(
        passes=[
            Pass(item=None),
            Pass(item=None),
            Pass(item=None),
            Pass(raises=CANCEL()),
        ],
        clock=[0.0],
        use_streams=True,
        build_service=False,
        supervisor=None,
        queue_name="detection_queue-b28",
        poll_timeout=7,
    )
    win(caplog)

    async with scripted(run) as (worker, doubles, _service, factory):
        stats = worker._stats.to_dict()

    consumer_name = f"detection-worker-{id(worker)}"
    assert factory.await_count == 1, "L372 runs whenever use_streams is truthy"
    assert worker._redis.get_from_queue.await_args_list == [
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
    ], (
        "the no-service drive must stay on the legacy queue: "
        f"{worker._redis.get_from_queue.await_args_list!r}"
    )
    assert worker._process_detection_item.await_count == 0, "an idle legacy read processes nothing"
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
    assert run.sleeps == [], "no failed pass means no L447 sleep"
    assert run.heartbeat_reads() == 2, (
        "legacy mode short-circuits L397 on use_streams, so no L399 read even in streams "
        f"mode with no service: {run.heartbeat_reads()}"
    )


# =============================================================================
# 8) streams-mode control: an empty consume read continues WITHOUT touching legacy
#    (the m52 twin at L415, a second route to the consume-call family)
# =============================================================================


async def test_an_empty_consume_read_continues_without_the_legacy_arm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:414-415 - ``if not messages: continue`` in streams mode.

    Stated because the legacy leg's ``continue`` pins (the m52 twin at L428) sit in a
    DIFFERENT arm: an empty stream read must loop back to the top WITHOUT falling into the
    BLPOP arm and without processing anything.  Four empty reads, then the sentinel; the
    clock stays constant so neither gate opens, and the two INFO records pin the streams
    banner a second time with a different worker object (a second route to the banner family
    at a different ``consumer_name``).  The four ``consume_detections`` records are a second
    route to m34/m35/m37.
    """
    run = Run(
        passes=[
            Pass(messages=[]),
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

    consumer_name = f"detection-worker-{id(worker)}"
    assert (
        service.consume_detections.await_args_list == [call(consumer_name, count=1, block=True)] * 5
    ), f"consume_detections mutated: {service.consume_detections.await_args_list!r}"
    assert service.claim_stale_messages.await_count == 0
    assert worker._redis.get_from_queue.await_count == 0, (
        "streams mode must never fall into the legacy BLPOP arm"
    )
    assert worker._process_detection_item.await_count == 0
    assert stats["items_processed"] == 0
    assert stats["errors"] == 0
    pin_levels(caplog, [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(
        caplog,
        logging.INFO,
        [
            {"consumer_name": consumer_name},
            {},
            {"items_processed": 0},
        ],
    )
    assert run.sleeps == []
    assert run.heartbeat_reads() == 7, (
        "the L381 + L385 baselines plus one L399 read per iteration on the frozen clock: "
        f"{run.heartbeat_reads()}"
    )


async def test_five_empty_consume_reads_under_a_supervisor_still_never_claim(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The empty-consume control again, this time WITH a supervisor and a new clock.

    Second, independently-valued route to the L415 twin of m52: six empty stream reads with
    the alias pinned at ``640.0`` (so the heartbeat gate is open for business but the 20 s
    interval never elapses) must produce SIX consume records, ZERO claims, ZERO BLPOP reads
    and the shipped two baseline-plus-per-iteration alias reads.  Under m52's ``break`` at
    L415 the drive ends after the FIRST empty read - four fewer consume records, two fewer
    alias reads and an exit payload nothing like this - and the supervisor's presence makes
    the L392 read count part of the same pin, so the two gates cannot both be quietly wrong.
    """
    supervisor = supervisor_double()
    run = Run(
        passes=[
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(raises=CANCEL()),
        ],
        clock=[640.0],
        use_streams=True,
        supervisor=supervisor,
    )
    win(caplog)

    async with scripted(run) as (worker, _doubles, service, _factory):
        stats = worker._stats.to_dict()

    consumer_name = f"detection-worker-{id(worker)}"
    assert service.consume_detections.await_count == 7, (
        f"one consume read per scripted pass, sentinel included: "
        f"{service.consume_detections.await_count}"
    )
    assert (
        service.consume_detections.await_args_list == [call(consumer_name, count=1, block=True)] * 7
    ), f"consume_detections mutated: {service.consume_detections.await_args_list!r}"
    assert service.claim_stale_messages.await_count == 0
    assert supervisor.record_heartbeat.call_count == 0, (
        "a frozen alias never advances the 20-second heartbeat interval"
    )
    assert worker._redis.get_from_queue.await_count == 0
    assert worker._process_detection_item.await_count == 0
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"stats mutated: {stats!r}"
    pin_levels(caplog, [STREAMS_BANNER_INFO, CANCELLED_INFO, EXIT_INFO], logging.INFO)
    pin_payloads(
        caplog,
        logging.INFO,
        [{"consumer_name": consumer_name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == []
    assert run.heartbeat_reads() == 16, (
        "L381 + L385 baselines plus one L392 AND one L399 read in each of the seven "
        f"iterations: {run.heartbeat_reads()}"
    )
