"""S3 batch-29 lane 00 - ``pipeline_workers`` tail battery (18 KILLABLE keys).

Module: ``backend/services/pipeline_workers.py``.  Dispositioned NOT by diff
shape but by the per-key construction probe ``/home/agent/runs/pw-equiv-probe.py``
(read-only sweep of the instrumented ``mutants/`` tree, per-key
``MUTANT_UNDER_TEST`` on the real trampolines, six driver groups, shipped half
rehearsed first, mandatory positive controls alive): **18 KILLABLE / 5
EQUIVALENT of 23 survivors**.  Every ``ship=``/``mut=`` diff-pair the probe
printed became a leg below.

Five keys are dispositioned EQUIVALENT and carry NO test here - the probe's
own corrections, in BOTH failure directions:

* ``drain_queues m55`` - L1768 ``stall_time >= stall_threshold`` -> ``>``.
  ``stall_time`` only ever reaches the 5.0 region on the IEEE ladder
  ``0.0`` + ``0.1`` * n: ``4.999999999999998 -> 5.099999999999998`` - no
  reachable value equals 5.0 exactly, so ``>=`` and ``>`` never disagree
  (0 diffs over every probe leg + a float-ladder simulation in the probe
  header).
* ``_process_analysis_item m219/m221/m271/m273`` - the
  ``extra={"batch_id": batch_id}`` on the two ``Failed to broadcast
  batch.analysis_failed`` DEBUGs (validation arm, analyzer arm) -> ``None`` /
  kwarg dropped.  The shipped body runs inside
  ``log_context(batch_id=batch_id, camera_id=..., operation="analysis")``
  (L1013-1016) and the ``ContextFilter`` that ``get_logger`` attaches
  (backend/core/logging.py:484-485, 1127-1129) merges those fields into EVERY
  in-scope record - drop the explicit ``extra`` and the filter re-injects the
  identical ``record.batch_id``.  Unobservable in production; this is also why
  they SURVIVED the real bank run.  (A probe pass that stubbed ``log_context``
  claimed them KILLABLE - the stub was the artifact.)

Test -> mutant-key map (18 KILLABLE keys)
=========================================
* ``broadcast_worker_event`` ``m19`` (L122
  ``logger.warning(f"Unknown worker event type: {event_type}")`` -> ``None)``)
  -> ``test_unknown_event_type_warning_names_the_event_type`` (plus the
  arm's one-record / no-emit shape in the same leg).
* ``broadcast_worker_event`` ``m33`` (L136 whole ``extra=`` dict -> ``None``),
  ``m35`` (kwarg dropped), ``m36``/``m37`` (``worker_name`` ->
  ``XXworker_nameXX`` / ``WORKER_NAME``), ``m38``/``m39`` (``worker_type`` ->
  ``XXworker_typeXX`` / ``WORKER_TYPE``)
  -> ``test_successful_broadcast_debug_carries_both_worker_identifiers``: all
  six variants change WHICH attributes the success DEBUG carries - pinning
  both identifiers to the shipped values reddens every one.
  ``worker_name``/``worker_type`` appear in no ``log_context`` and in no
  ``ContextFilter`` key (audited: the helper is never called inside a context
  scope), so unlike the analysis-arm ``batch_id`` above the record attribute
  really is the observable.  ``test_no_emitter_arm_broadcasts_nothing`` is the
  guard leg keeping the DEBUG-emitted-only contract honest.
* ``reset_pipeline_manager_state`` ``m1`` (L2101 ``_pipeline_manager = None``
  -> ``= ""``) -> ``test_reset_clears_the_manager_to_none_not_an_empty_string``
  - ``is None`` on BOTH module globals (the empty string is falsy, so only
  the type/identity sees the mutation).
* ``_process_detection_item`` ``m107`` (generic-arm L540 ``self._stats.errors
  += 1`` -> ``= 1``) -> ``test_generic_handler_increments_a_prewarmed_error_count``
  (pre=2 -> shipped 3, m107 1; the pre-warm is the ONLY discriminating input,
  which is why every 0-starting bank leg missed it) + the honest 0->1 control
  + ``test_detector_unavailable_arm_is_not_the_generic_arm`` (sibling-arm
  control proving the DLQ arm also increments, so 3 pins the GENERIC arm ran).
* ``drain_queues`` ``m21`` (L1737 init ``stall_time = 0.0`` -> ``1.0``),
  ``m23`` (L1738 ``stall_threshold = 5.0`` -> ``6.0``), ``m51`` (L1766
  ``current_count >= last_count`` -> ``>``), ``m52`` (L1767 ``stall_time +=
  0.1`` -> ``= 0.1``), ``m53`` (``+= 0.1`` -> ``-= 0.1``), ``m54`` (``+= 0.1``
  -> ``+= 1.1``), ``m57`` (L1775 on-progress ``stall_time = 0.0`` -> ``1.0``)
  -> three legs replaying the shipped poll loop under a scripted clock:
  - ``test_a_holding_queue_logs_the_shipped_stall_once`` (budget 6.6 s): the
    stall DEBUG EXISTS (kills m51's never-stalls, m52's frozen 0.1, m53's
    decrement), fires exactly ONCE (kills m54's 11 fires), with the shipped
    ``5.1s`` text/extra (kills m23's ``6.1s``).
  - ``test_a_longer_stall_budget_restarts_the_window_after_each_log`` (budget
    10.0 s): shipped still logs ONE stall (the post-log reset restarts a full
    5 s window that outlives the timeout); m21's 1.0 head-start fits TWO
    stalls inside the same budget.
  - ``test_progress_resets_the_accumulator_so_a_short_hold_stays_silent``
    (drain 9 -> 5, then hold; budget 4.8 s): shipped's 0.0 reset on the last
    progress step keeps the following 5.0 s hold BELOW the timeout-crossing
    point - zero stall DEBUGs; m57's 1.0 head-start logs one.
* ``get_pending_count`` ``m2`` (L1694 queue arg -> ``None``), ``m4`` (L1695
  queue arg -> ``None``) -> ``test_get_pending_count_reads_both_shipped_queues``
  (the two ``get_queue_length`` ARGS are the shipped constants - invisible in
  the return, visible in the autospec'd call records) + the value/degradation
  control the arg mutants pass, naming why the identity pin is the kill.

House rules honoured: every double is ``create_autospec``'d or installed with
``new=`` (WP4.2); ``time.time`` is patched on the ONE ``time`` module object
(the shipped body's function-local ``import time`` binds the same object) and
``asyncio.sleep`` is an autospec'd no-op that advances the same scripted clock,
so the poll loop's elapsed time is fully deterministic and every leg
terminates on the shipped timeout arm in microseconds of wall time; the
shipped ``log_context``/``ContextFilter`` stay REAL (see above); nothing in
production is bent; the autouse fixture restores both module globals.
"""

from __future__ import annotations

import asyncio
import logging
import time as time_module
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import PipelineWorkerManager, WorkerStats

pytestmark = [pytest.mark.unit]

LOG_NAME = M.logger.name
MOD = "backend.services.pipeline_workers"

#: test-local guard (WALL seconds): a leg whose shipped exit disappeared fails
#: in milliseconds of real time instead of burning the tier timeout.  The
#: scripted clock makes every shipped drain end on the timeout arm anyway.
DRAIN_CEILING = 3.0
#: shipped pipeline_workers.py:1738 - legs are sized against this constant
STALL_THRESHOLD = 5.0


# ---------------------------------------------------------------------------
# fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_pipeline_manager_globals() -> Iterator[None]:
    """Restore the two module globals every leg touches (reset tests write them)."""
    manager, lock = M._pipeline_manager, M._pipeline_manager_lock
    yield
    M._pipeline_manager, M._pipeline_manager_lock = manager, lock


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG on this module's logger, buffer emptied."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_text(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped f-string log call.

    ``record.msg`` is the RAW message; every shipped site here is an
    already-interpolated f-string, so ``args`` must stay empty and no
    ``exc_info`` may ride along (except where the leg pins otherwise).
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for an f-string message: {r.args!r}"


def extra(r: logging.LogRecord, key: str) -> Any:
    """Read one ``extra=`` attribute so a DROP is distinguishable from ``None``."""
    assert key in r.__dict__, (
        f"record.{key} missing entirely - shipped passes extra={key} (m33 passes "
        f"extra=None, m35 drops the kwarg): {sorted(k for k in r.__dict__ if not k.startswith('_'))}"
    )
    return r.__dict__[key]


class StepClock:
    """``time.time`` double advancing ``step`` seconds per CALL.

    ``drain_queues`` reads the clock once for ``start`` (L1718) and once per
    iteration (L1741); ``logging`` consumes one call per emitted record.  Every
    observable below is therefore a FUNCTION of read order, not of wall time.
    """

    def __init__(self, start: float = 1000.0, step: float = 0.1) -> None:
        self.t = start
        self.step = step
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        value = self.t
        self.t += self.step
        return value


def patch_time(clock: StepClock) -> Any:
    """``time.time`` -> a scripted double on the ONE ``time`` module object.

    The shipped ``drain_queues`` does a function-local ``import time``
    (L1716), which binds the same module object - one attribute patch reaches
    both it and ``logging``'s record stamps.
    """
    return patch.object(
        time_module, "time", new=create_autospec(time_module.time, side_effect=clock)
    )


async def run_drain(
    depths: list[int],
    *,
    budget: float,
    **call_kwargs: Any,
) -> tuple[int | None, BaseException | None]:
    """Run the shipped ``drain_queues(timeout=budget)`` against a scripted depth.

    The manager is ``__new__``-built with only the three collaborators the
    shipped body touches: ``stop_accepting`` (autospec'd spy),
    ``get_pending_count`` (replays ``depths``, then repeats its LAST value so a
    leg can never starve on a mutated branch), and the logger.  ``time.time``
    is a StepClock stepping 0.1 s per read and ``asyncio.sleep`` is an
    autospec'd no-op, so the loop's ENTIRE world advances 0.1 s per iteration
    and the shipped ``elapsed >= timeout`` arm (L1741) is reached
    deterministically - the shipped exit survives ANY stall-accumulator
    mutation because it depends only on the clock.  ``DRAIN_CEILING`` is the
    wall-clock guard.
    """
    manager = PipelineWorkerManager.__new__(PipelineWorkerManager)
    manager.stop_accepting = MagicMock(name="stop_accepting")  # type: ignore[method-assign]
    script = list(depths)

    async def next_depth(*_args: Any, **_kwargs: Any) -> int:
        return script.pop(0) if len(script) > 1 else script[0]

    manager.get_pending_count = next_depth  # type: ignore[method-assign]
    clock = StepClock(start=1000.0, step=0.1)

    async def advance(_delay: float = 0.0, *_a: Any, **_k: Any) -> None:
        return None

    raised: BaseException | None = None
    result: int | None = None
    with (
        patch_time(clock),
        patch("asyncio.sleep", new=create_autospec(asyncio.sleep, side_effect=advance)),
    ):
        try:
            result = await asyncio.wait_for(
                manager.drain_queues(timeout=budget, **call_kwargs), DRAIN_CEILING
            )
        except TimeoutError as exc:
            raised = exc
    return result, raised


def stall_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in at(caplog, logging.DEBUG) if r.msg.startswith("Queue drain stalled")]


def detection_worker(errors: int, failure: BaseException | None) -> Any:
    """A ``DetectionQueueWorker`` whose processing step raises ``failure``.

    ``__new__`` + the REAL ``WorkerStats`` so the error counter is the shipped
    dataclass; the payload validator is replaced (``new=``) by a stub yielding
    a well-formed image payload, so control reaches the HANDLER under test.
    The telemetry re-exports the handlers call are autospec'd inert doubles -
    everything else (``log_context``, the ContextFilter, the stats arithmetic)
    is shipped.
    """
    worker = M.DetectionQueueWorker.__new__(M.DetectionQueueWorker)
    worker._stats = WorkerStats()
    worker._stats.errors = errors
    worker._redis = None

    async def failing(*_args: Any, **_kwargs: Any) -> None:
        if failure is not None:
            raise failure

    worker._process_image_detection = failing  # type: ignore[method-assign]
    worker._process_video_detection = failing  # type: ignore[method-assign]
    return worker


def drive_detection(worker: Any) -> None:
    """Drive one shipped ``_process_detection_item`` round with inert telemetry."""
    payload = MagicMock(name="validated_payload")
    payload.camera_id = "cam1"
    payload.file_path = "/frames/x.jpg"
    payload.media_type = "image"
    payload.pipeline_start_time = None
    with (
        patch(
            f"{MOD}.validate_detection_payload",
            new=create_autospec(M.validate_detection_payload, return_value=payload),
        ),
        patch(f"{MOD}.record_pipeline_error", new=create_autospec(M.record_pipeline_error)),
        patch(f"{MOD}.record_exception", new=create_autospec(M.record_exception)),
        patch(f"{MOD}.observe_stage_duration", new=create_autospec(M.observe_stage_duration)),
        patch(
            f"{MOD}.record_pipeline_stage_latency",
            new=create_autospec(M.record_pipeline_stage_latency),
        ),
        patch(f"{MOD}.record_stage_latency", new=AsyncMock(name="record_stage_latency")),
        patch(
            f"{MOD}.set_pipeline_context_attributes",
            new=create_autospec(M.set_pipeline_context_attributes),
        ),
        patch(f"{MOD}.add_span_attributes", new=create_autospec(M.add_span_attributes)),
    ):
        asyncio.run(worker._process_detection_item({"k": 1}))


class Emitter:
    """A ``WebSocketEmitterService`` double recording the emitted event/payload."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def emit(self, event_type: Any, payload: dict[str, Any]) -> None:
        self.calls.append((getattr(event_type, "name", repr(event_type)), dict(payload)))


# ---------------------------------------------------------------------------
# 1) broadcast_worker_event m19 - the unknown-type WARNING text
# ---------------------------------------------------------------------------


async def test_unknown_event_type_warning_names_the_event_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``m19``: L122 ``f"Unknown worker event type: {event_type}"`` -> ``None)``.

    Shipped (pipeline_workers.py:121-123)::

        if ws_event_type is None:
            logger.warning(f"Unknown worker event type: {event_type}")
            return

    An event type outside the shipped ``event_type_map`` (L110-118) takes this
    arm; the interpolated name IS the observable and ``logger.warning(None)``
    emits the literal string ``"None"`` without it.  The leg also pins the
    arm's shape - exactly one record, nothing emitted - so the return-after-
    warning contract travels with the kill.
    """
    emitter = Emitter()
    win(caplog)

    await M.broadcast_worker_event(emitter, "worker.nope", "det-1", "detection")

    warnings = at(caplog, logging.WARNING)
    assert len(warnings) == 1, f"the unknown arm logs exactly once: {[r.msg for r in warnings]!r}"
    pin_text(warnings[0], msg="Unknown worker event type: worker.nope", level=logging.WARNING)
    assert emitter.calls == [], f"an unknown event type must never be emitted: {emitter.calls!r}"


# ---------------------------------------------------------------------------
# 2) broadcast_worker_event m33/m35/m36/m37/m38/m39 - success DEBUG extra dict
# ---------------------------------------------------------------------------


async def test_successful_broadcast_debug_carries_both_worker_identifiers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Six mutants of the L133-137 ``extra=`` dict, one pinned record.

    Shipped (pipeline_workers.py:133-137)::

        await emitter.emit(ws_event_type, payload)
        logger.debug(
            f"Broadcast worker event: {event_type}",
            extra={"worker_name": worker_name, "worker_type": worker_type},
        )

    m33 replaces the dict with ``None`` and m35 drops the kwarg - both leave
    the record with NEITHER identifier; m36 renames ``worker_name`` to
    ``XXworker_nameXX``, m37 to ``WORKER_NAME``; m38/m39 do the same pair to
    ``worker_type``.  Pinning BOTH attributes to the shipped values reddens all
    six and nothing else can pass it.  Neither key exists in any
    ``log_context`` or in the ``ContextFilter`` fixed set, so the record
    attribute is the mutation's only observable surface (unlike the analysis
    arms - see the module docstring).
    """
    emitter = Emitter()
    win(caplog)

    await M.broadcast_worker_event(emitter, "worker.started", "det-7", "detection", foo="bar")

    debugs = [r for r in at(caplog, logging.DEBUG) if r.msg.startswith("Broadcast worker event")]
    assert len(debugs) == 1, f"one broadcast, one success DEBUG: {[r.msg for r in debugs]!r}"
    record = debugs[0]
    pin_text(record, msg="Broadcast worker event: worker.started", level=logging.DEBUG)
    assert extra(record, "worker_name") == "det-7", (
        f"record.worker_name mutated/renamed: {record.__dict__.get('worker_name')!r} "
        f"(m33/m35 leave no such attribute, m36 -> XXworker_nameXX, m37 -> WORKER_NAME)"
    )
    assert extra(record, "worker_type") == "detection", (
        f"record.worker_type mutated/renamed: {record.__dict__.get('worker_type')!r} "
        f"(m33/m35 leave no such attribute, m38 -> XXworker_typeXX, m39 -> WORKER_TYPE)"
    )
    emitted = [
        (name, {k: v for k, v in p.items() if k != "timestamp"}) for name, p in emitter.calls
    ]
    assert emitted == [
        ("WORKER_STARTED", {"worker_name": "det-7", "worker_type": "detection", "foo": "bar"})
    ], f"the emitted payload drifted: {emitted!r}"


async def test_no_emitter_arm_broadcasts_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The guard leg for the group: the success DEBUG is emitted-only surface.

    Shipped (pipeline_workers.py:103-105): ``if emitter is None: logger.debug(
    f"WebSocket emitter not available, skipping {event_type} broadcast");
    return`` - a ``None`` emitter must produce exactly its own DEBUG and never
    a ``Broadcast worker event`` one.  Without this leg, a mutant that hoisted
    the success DEBUG above the guard could still satisfy the leg above.
    """
    win(caplog)

    await M.broadcast_worker_event(None, "worker.started", "det-7", "detection")

    assert [r.msg for r in mine(caplog)] == [
        "WebSocket emitter not available, skipping worker.started broadcast"
    ], f"the no-emitter arm logs exactly its own DEBUG: {[r.msg for r in mine(caplog)]!r}"


# ---------------------------------------------------------------------------
# 3) reset_pipeline_manager_state m1 - None -> ""
# ---------------------------------------------------------------------------


def test_reset_clears_the_manager_to_none_not_an_empty_string() -> None:
    """``m1``: L2101 ``_pipeline_manager = None`` -> ``= ""``.

    Shipped (pipeline_workers.py:2100-2102)::

        global _pipeline_manager, _pipeline_manager_lock  # noqa: PLW0603
        _pipeline_manager = None
        _pipeline_manager_lock = None

    The empty string is falsy, so ``if _pipeline_manager is not None`` guards
    read the same EITHER way - only type/identity sees the difference, which is
    precisely what ``get_pipeline_manager``'s cache check will eventually hand
    back as a "manager".  ``is None`` on both globals is the shipped contract;
    the lock is pinned in the same breath because the shipped reset clears both.
    """
    M._pipeline_manager = "SET"  # type: ignore[assignment]
    M._pipeline_manager_lock = "LOCK"  # type: ignore[assignment]

    M.reset_pipeline_manager_state()

    assert M._pipeline_manager is None, (
        f"the manager global must reset to the None SINGLETON: "
        f"{type(M._pipeline_manager).__name__}={M._pipeline_manager!r} (m1 gives str='')"
    )
    assert M._pipeline_manager_lock is None, (
        f"the lock global must reset to the None singleton: "
        f"{type(M._pipeline_manager_lock).__name__}={M._pipeline_manager_lock!r}"
    )


# ---------------------------------------------------------------------------
# 4) _process_detection_item m107 - generic arm errors += 1 -> = 1
# ---------------------------------------------------------------------------


def test_generic_handler_increments_a_prewarmed_error_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``m107``: L540 ``self._stats.errors += 1`` -> ``= 1`` (generic arm).

    Shipped (pipeline_workers.py:535-547)::

        except Exception as e:
            self._stats.errors += 1
            record_pipeline_error("detection_processing_error")
            record_exception(e)
            logger.error(f"Failed to process detection item: {e}", exc_info=True)

    A NON-ZERO starting count is the only input class that separates the
    variants: two errors already banked, a third arrives -> shipped 3, the
    assignment 1.  That is why the mutant survived every pre-existing bank leg
    - they all entered with ``errors=0``, where ``+= 1`` and ``= 1`` agree.
    The ERROR text pins WHICH arm ran (generic), so the count cannot be
    credited to the sibling DLQ arm.
    """
    worker = detection_worker(errors=2, failure=RuntimeError("cuda exploded"))
    win(caplog)

    drive_detection(worker)

    assert worker._stats.errors == 3, (
        f"the generic handler must INCREMENT the banked count (2 + 1 = 3), got "
        f"{worker._stats.errors} - m107's assignment collapses it to 1"
    )
    errors = [
        r for r in at(caplog, logging.ERROR) if r.msg.startswith("Failed to process detection item")
    ]
    assert [r.msg for r in errors] == ["Failed to process detection item: cuda exploded"], (
        f"the generic arm's ERROR text is the arm's identity: {[r.msg for r in errors]!r}"
    )


def test_generic_handler_from_zero_counts_one(caplog: pytest.LogCaptureFixture) -> None:
    """The 0 -> 1 case BOTH variants agree on - recorded deliberately.

    This leg passes under m107.  It pins the shipped arithmetic's base case and
    documents why the PREWARMED leg, not this one, is the kill.
    """
    worker = detection_worker(errors=0, failure=RuntimeError("boom"))
    win(caplog)

    drive_detection(worker)

    assert worker._stats.errors == 1, (
        f"one failure from zero banked errors is exactly one: {worker._stats.errors}"
    )


def test_detector_unavailable_arm_is_not_the_generic_arm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The sibling-arm control: ``DetectorUnavailableError`` lands at L536-541, not L540.

    Shipped routes the detector-down case to the DLQ arm - increments, logs a
    WARNING, and does NOT take the generic arm's ERROR.  Proving that arm ALSO
    increments is what licenses reading the pre-warmed leg's 3 as "the generic
    arm ran"; without it, one increment could not distinguish the handlers.
    """
    worker = detection_worker(
        errors=2,
        failure=M.DetectorUnavailableError("detector down", original_error=RuntimeError("x")),
    )
    win(caplog)

    drive_detection(worker)

    assert worker._stats.errors == 3, f"the DLQ arm also increments: got {worker._stats.errors}"
    assert at(caplog, logging.ERROR) == [], (
        f"the DLQ arm must never take the generic ERROR: {[r.msg for r in at(caplog, logging.ERROR)]!r}"
    )
    warnings = [r for r in at(caplog, logging.WARNING) if r.name == LOG_NAME]
    assert [r.msg for r in warnings] == ["Detection unavailable, job sent to DLQ: detector down"], (
        f"the DLQ path is one WARNING naming the event: {[r.msg for r in warnings]!r}"
    )


# ---------------------------------------------------------------------------
# 5) drain_queues m21/m23/m51/m52/m53/m54/m57 - the stall accumulator
# ---------------------------------------------------------------------------


async def test_a_holding_queue_logs_the_shipped_stall_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Budget 6.6 s over a queue pinned at 4 pending: existence, count, text.

    Shipped (pipeline_workers.py:1737-1776)::

        stall_time = 0.0
        stall_threshold = 5.0  # Log if no progress for 5 seconds
        ...
            if current_count >= last_count:
                stall_time += 0.1
                if stall_time >= stall_threshold:
                    logger.debug(
                        f"Queue drain stalled for {stall_time:.1f}s at {current_count} pending",
                        extra={"stall_time": stall_time, "pending_count": current_count},
                    )
                    stall_time = 0.0  # Reset to avoid flooding logs
            else:
                stall_time = 0.0
                last_count = current_count

    The scripted clock makes ``stall_time`` cross 5.0 on the 51st poll
    (ladder 5.099999999999998), so shipped logs EXACTLY ONE stall DEBUG -
    ``"Queue drain stalled for 5.1s at 4 pending"`` - inside 6.6 s of fake
    time, then returns on the timeout arm.  Four reddening surfaces from one
    call set:
    * m51 (strict ``>``): a count-EQUAL hold takes the ELSE arm -> zero stalls;
    * m52 (``= 0.1``): the accumulator is pinned below the threshold -> zero;
    * m53 (``-= 0.1``): it runs negative -> zero;
    * m54 (``+= 1.1``): it crosses after FIVE iterations and logs 11 stalls,
      each saying ``5.5s``;
    * m23 (threshold 6.0): the single stall says ``6.1s`` and its extra is
      6.099999999999998.
    The shipped ``5.1`` text + the extra pin kill m23/m54 by value; the
    one-and-only existence count kills m51/m52/m53.
    """
    win(caplog)

    result, raised = await run_drain([4] * 900, budget=6.6)

    assert raised is None, (
        f"the drain must end on the shipped timeout arm, not the wall guard: {raised!r}"
    )
    stalls = stall_records(caplog)
    assert len(stalls) == 1, (
        f"one 5.0s stall window fits in 6.6s: got {len(stalls)} "
        f"{[r.msg for r in stalls]!r} (m51/m52/m53 log none, m54 logs eleven)"
    )
    record = stalls[0]
    pin_text(record, msg="Queue drain stalled for 5.1s at 4 pending", level=logging.DEBUG)
    assert round(extra(record, "stall_time"), 1) == 5.1, (
        f"extra.stall_time mutated: {record.__dict__.get('stall_time')!r} (m23's ladder reaches 6.1 before firing)"
    )
    assert extra(record, "pending_count") == 4, (
        f"extra.pending_count mutated: {record.__dict__.get('pending_count')!r}"
    )
    assert result == 4, f"the timeout arm returns the freshly read depth: {result!r}"
    warnings = at(caplog, logging.WARNING)
    assert len(warnings) == 1, f"exactly one timeout WARNING: {[r.msg for r in warnings]!r}"
    assert warnings[0].msg.startswith("Queue drain timeout after ") and warnings[0].msg.endswith(
        "s, 4 tasks remaining"
    ), f"the termination is the shipped timeout WARNING naming 4 remaining: {warnings[0].msg!r}"
    assert (
        extra(warnings[0], "remaining_count") == 4 and extra(warnings[0], "initial_count") == 4
    ), "the timeout extras carry the remaining and initial depths"


async def test_a_longer_stall_budget_restarts_the_window_after_each_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``m21``: budget 10.0 s over the same pinned-at-4 queue - still ONE stall.

    The post-log reset (L1773) restarts a FULL 5 s window, and a second window
    cannot complete before the 10 s timeout (51 further polls would land past
    ``elapsed`` 10.0) - so shipped logs exactly one stall DEBUG in this budget
    too.  m21 (L1737 init ``stall_time = 1.0``) starts the accumulator a full
    second ahead of the shipped loop, so its second stall closes the budget
    window - TWO stall DEBUGs where shipped logs one.  The count is the kill;
    the first record's shipped text is pinned again so the pair cannot pass on
    two early-but-mislabelled logs.
    """
    win(caplog)

    result, raised = await run_drain([4] * 900, budget=10.0)

    assert raised is None, f"expected the shipped timeout exit: {raised!r}"
    stalls = stall_records(caplog)
    assert len(stalls) == 1, (
        f"the post-log 5.0s reset keeps a 10.0s budget at ONE stall: got "
        f"{len(stalls)} {[r.msg for r in stalls]!r} (m21's 1.0 head-start fits two)"
    )
    pin_text(stalls[0], msg="Queue drain stalled for 5.1s at 4 pending", level=logging.DEBUG)
    assert result == 4, f"the remaining depth must be returned: {result!r}"


async def test_progress_resets_the_accumulator_so_a_short_hold_stays_silent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``m57``: L1775 on-progress ``stall_time = 0.0`` -> ``stall_time = 1.0``.

    Shipped (pipeline_workers.py:1774-1776)::

            else:
                stall_time = 0.0
                last_count = current_count

    The reset is only observable when a progress step is FOLLOWED by a hold
    that ALMOST crosses the threshold before the timeout: this leg drains
    9 -> 5 over the first five polls (each drop resets the accumulator - 0.0
    shipped, 1.0 under m57) and then pins at 5 with a 4.8 s budget.  Shipped's
    hold accumulates from 0.0 and never reaches 5.0 before the timeout -> ZERO
    stall DEBUGs; m57 starts the same hold already 1.0 in and logs ONE stall
    (``"Queue drain stalled for 5.1s at 5 pending"``) inside the same budget.
    Absence-of-the-DEBUG is the shipped behaviour being pinned - the only
    route the reset has onto the observable surface.
    """
    win(caplog)

    result, raised = await run_drain([9, 8, 7, 6, 5] + [5] * 900, budget=4.8)

    assert raised is None, f"expected the shipped timeout exit: {raised!r}"
    assert result == 5, f"the held depth must be returned: {result!r}"
    stalls = stall_records(caplog)
    assert stalls == [], (
        f"a 5s hold that starts at 0.0 cannot stall inside 4.8s of budget: "
        f"{[r.msg for r in stalls]!r} (m57's 1.0 head-start logs one)"
    )
    starts = [r for r in mine(caplog) if r.msg.startswith("Starting queue drain")]
    assert (
        len(starts) == 1
        and starts[0].msg == "Starting queue drain with 9 pending tasks, timeout=4.8s"
    ), f"the drain ran normally to its timeout (opening INFO pinned): {[r.msg for r in starts]!r}"


# ---------------------------------------------------------------------------
# 6) get_pending_count m2/m4 - the queue-name arguments
# ---------------------------------------------------------------------------


async def test_get_pending_count_reads_both_shipped_queues() -> None:
    """``m2`` (L1694 queue arg -> ``None``), ``m4`` (L1695 queue arg -> ``None``).

    Shipped (pipeline_workers.py:1693-1697)::

        detection_depth = await self._redis.get_queue_length(DETECTION_QUEUE)
        analysis_depth = await self._redis.get_queue_length(ANALYSIS_QUEUE)
        return detection_depth + analysis_depth

    The queue NAME is the observable: both mutants pass ``None`` where a
    shipped constant is required - invisible in the return value (a fake redis
    answers either way, and in production a ``None`` queue silently reads some
    other/empty key), visible only in the call arguments.  The autospec'd
    double keeps the positional args, and the pin uses the IMPORTED constants
    themselves so a legitimate re-spelling upstream still matches.
    """
    redis = MagicMock(name="redis")
    redis.get_queue_length = AsyncMock(name="get_queue_length", side_effect=[3, 4])
    manager = PipelineWorkerManager.__new__(PipelineWorkerManager)
    manager._redis = redis

    total = await manager.get_pending_count()

    assert total == 7, f"the two queue depths are summed: {total!r}"
    calls = redis.get_queue_length.await_args_list
    assert len(calls) == 2, f"exactly two queue reads: {calls!r}"
    assert calls[0].args == (DETECTION_QUEUE,), (
        f"the detection arm must read DETECTION_QUEUE={DETECTION_QUEUE!r}, got "
        f"{calls[0].args!r} - m2 passes None"
    )
    assert calls[1].args == (ANALYSIS_QUEUE,), (
        f"the analysis arm must read ANALYSIS_QUEUE={ANALYSIS_QUEUE!r}, got "
        f"{calls[1].args!r} - m4 passes None"
    )


async def test_get_pending_count_sums_depths_and_degrades_to_zero_on_redis_failure() -> None:
    """The value/exception control the arg mutants PASS - naming why args are the kill.

    Shipped returns ``detection + analysis`` and swallows a redis failure into
    ``0`` with one WARNING (L1696-1699).  m2/m4 leave every value here intact,
    which is exactly why the identity pin above is the kill and this leg is
    the contract it must not break.
    """
    ok_redis = MagicMock(name="redis")
    ok_redis.get_queue_length = AsyncMock(name="get_queue_length", side_effect=[0, 0])
    manager = PipelineWorkerManager.__new__(PipelineWorkerManager)
    manager._redis = ok_redis

    assert await manager.get_pending_count() == 0, "two empty queues total zero"

    down_redis = MagicMock(name="redis")
    down_redis.get_queue_length = AsyncMock(
        name="get_queue_length", side_effect=RuntimeError("redis down")
    )
    manager._redis = down_redis

    assert await manager.get_pending_count() == 0, "a redis failure degrades to 0 and never raises"
