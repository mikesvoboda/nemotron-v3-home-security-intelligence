"""batch-28 lane 16 - ``pipeline_workers`` group g16: manager signal handlers, the
``drain_queues`` default, and the ``get_status`` timeout slot.

Module: ``backend/services/pipeline_workers.py`` (md5 d6e3c91fc85bfaea19f0d907491eefbf,
git blob 05b50f5a).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/manifest.json``
``idx == 16`` with ``group_16.keys`` (11 keys, ALL KILLABLE - this group has NO
EQUIVALENT and NO NEEDS_INVESTIGATION key) and ``diffs.json`` / ``survivors.json`` for the
per-key diffs.  Every line number below is a coordinate in the CURRENT blob, and every
assert is justified by that shipped text.

Sites under test
================
* ``PipelineWorkerManager._install_signal_handlers`` - L1966-1988
* ``PipelineWorkerManager.drain_queues`` default      - L1701, L1729-1732, L1740-1752
* ``PipelineWorkerManager.get_status`` timeout slot   - L1806-1807

Test -> mutant-key map (11 KILLABLE keys)
=========================================
* ``_install_signal_handlers`` ``m2`` (L1977 ``logger.info(f"Received signal {sig.name},
  initiating graceful shutdown")`` -> ``logger.info(None)``) + ``m3`` (L1978
  ``asyncio.create_task(self.stop())`` -> ``create_task(None)``, which raises
  ``TypeError`` synchronously and therefore loses BOTH observables)
  -> ``test_sigterm_handler_logs_and_schedules_the_manager_stop`` and
  ``test_sigint_handler_names_SIGINT``.  ``create_shutdown_handler`` is called once per
  signal, so each of those two keys has TWO OCCURRENCES with one shared mutant body - the
  occurrence-twin rule is honoured by giving each signal its own reddening leg rather than
  by one leg that could pass on the other closure.
* ``_install_signal_handlers`` ``m10`` (L1984 ``self._signal_handlers_installed = True``
  -> ``None``) + ``m11`` (L1984 -> ``False``)
  -> ``test_a_second_start_cycle_does_not_re_register``, which drives the shipped
  ``start()`` guard at L1838 through a real start/stop/start cycle.  Under either variant
  the flag stays falsy, the second ``start()`` re-enters the installer, and the injected
  loop receives FOUR registrations instead of TWO - the CALL COUNT is the kill.
  ``test_running_manager_warns_and_skips_re_install`` is the control that shows why the
  cycle is the only route back to that guard (``start()`` on a running manager returns at
  L1824-1826, before it).
* ``_install_signal_handlers`` ``m12``/``m13``/``m14``/``m15`` (L1985 confirmation DEBUG
  -> ``None`` / ``XX…XX`` wrap / ``.lower()`` / ``.upper()``)
  -> ``test_install_logs_the_confirmation_debug_and_registers_both_signals`` - raw text,
  level, zero lazy args, no ``exc_info``, a DEBUG-only window, and exactly two
  registrations in the shipped ``(SIGTERM, SIGINT)`` order.
* ``_install_signal_handlers`` ``m16`` (L1988 ``logger.debug(f"Could not install signal
  handlers: {e}")`` -> ``logger.debug(None)``)
  -> ``test_not_implemented_error_becomes_one_debug``.  A Windows ``ProactorEventLoop``
  cannot be constructed on this Linux host, so the ``NotImplementedError`` comes from the
  INJECTED loop double; the shipped ``except`` arm still interpolates the exception into
  the message, and that text - plus the untouched flag and zero registrations - is pinned.
* ``drain_queues`` ``m1`` (L1701 METHOD default ``timeout: float = 30.0`` -> ``31.0``)
  -> ``test_drain_default_logs_the_shipped_thirty_second_message`` (the default reaches the
  observable surface through the INFO message text AND ``extra["timeout"]``) together with
  ``test_drain_default_lets_the_elapsed_ge_timeout_comparison_decide`` (the third surface:
  under ``31.0`` the shipped loop would keep polling a non-empty queue instead of returning
  the remaining 2).  ``test_explicit_timeout_reaches_the_message_and_extra_verbatim`` is the
  control that proves both surfaces are the PARAMETER rather than a hard-coded number.
  (The module-level ``drain_queues`` at L2064 carries its own default and is group g17's
  key, not this group's.)
* ``get_status`` ``m26`` (L1807 ``status["workers"]["timeout"] =
  self._timeout_worker.stats.to_dict()`` -> ``= None``)
  -> ``test_get_status_stores_the_timeout_workers_own_to_dict``, which pins the slot to the
  ENABLED worker's ``to_dict()`` RESULT by identity (and pins
  ``WorkerStats.to_dict()["state"]`` as the enum's ``.value`` through the real class in the
  companion leg).  ``test_get_status_omits_a_disabled_timeout_worker`` is the "absent vs
  ``None``" control - the ``None`` variant writes into a slot shipped leaves entirely
  absent, so the two shapes must not be conflated - and
  ``test_get_status_fills_the_three_optional_slots_independently`` keeps the kill specific
  to one slot.

Discipline
==========
* Every patch of a real attribute is ``create_autospec``'d and installed with ``new=`` (so
  the double outlives its window for call-record reads).  No import-time global spy and no
  module-global mutation: the manager is built with its four worker CLASSES and
  ``BatchAggregator`` substituted, so no real worker loop or task is ever started and there
  is no global state to save or restore.
* The event-loop stand-in (``RecordingLoop``) is an INJECTED object returned by an
  autospec'd ``asyncio.get_running_loop``, not a mock of a real attribute - and it keeps a
  real SIGTERM/SIGINT handler out of the pytest process.
* Exact shipped strings / numbers / call arguments only.  Log legs read the RAW
  ``record.msg``, the level, the absence of lazy args and ``exc_info``, and the ``extra``
  fields as record attributes.
* ``time.monotonic`` / ``time.perf_counter`` are never patched.  ``drain_queues``'
  function-local ``import time`` (L1716) binds the same module object as
  ``pipeline_workers``' ``import time as time_module`` alias, so patching ``time.time``
  once inside a ``with`` window reaches the drain clock - a function patch in a window,
  never an edit to module state.
* No leg waits on a real 30-second drain: every drain runs under a test-local ``wait_for``
  ceiling, so a mutant that removes the exit it depends on goes RED in milliseconds instead
  of riding a tier timeout.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import time as time_module
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

from backend.core.config import Settings
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import (
    PipelineWorkerManager,
    WorkerState,
)

MOD = "backend.services.pipeline_workers"
LOG_NAME = M.logger.name  # "backend.services.pipeline_workers"

pytestmark = [pytest.mark.unit]

# The real asyncio primitives, captured at import time so a leg that patches the module
# attribute can still delegate to the shipped implementation.
_REAL_WAIT_FOR = asyncio.wait_for
_REAL_CREATE_TASK = asyncio.create_task

# =============================================================================
# Shipped literals, transcribed from the current blob
# =============================================================================

# L1977 / L1985 / L1988 - the three texts _install_signal_handlers logs.
SIGNAL_RECEIVED_INFO = "Received signal {}, initiating graceful shutdown"
SIGNALS_INSTALLED_DEBUG = "Signal handlers installed for SIGTERM and SIGINT"
SIGNAL_FAILED_DEBUG = "Could not install signal handlers: {}"
# L1726 / L1730 / L1745 / L1757 - drain_queues texts.
QUEUES_EMPTY_INFO = "Queues already empty, no draining needed"
DRAIN_START_INFO = "Starting queue drain with {} pending tasks, timeout={}s"
DRAIN_TIMEOUT_WARNING = "Queue drain timeout after {}s, {} tasks remaining"
DRAIN_DONE_INFO = "Queue drain completed in {}s"
# L1701 - the METHOD default under test (g16 drain_queues m1).
DRAIN_DEFAULT_TIMEOUT = 30.0
# L1825 / L1897 / L1900 / L1927 - manager guard + stop texts.
ALREADY_RUNNING_WARNING = "PipelineWorkerManager already running"
NOT_RUNNING_DEBUG = "PipelineWorkerManager not running, nothing to stop"
MANAGER_STOPPING_INFO = "Stopping PipelineWorkerManager"
MANAGER_STOPPED_INFO = "PipelineWorkerManager stopped all workers"
# L1679 - stop_accepting(), the shipped first act of every drain.
STOP_ACCEPTING_INFO = "Stopping PipelineWorkerManager from accepting new tasks"

# Values this file INJECTS through the Settings double; the manager only has to accept them.
THUMBNAIL_DIR = "var/thumbs-b28-16"
BATCH_CHECK_INTERVAL = 9.0
DETECTION_WORKER_COUNT = 1
ANALYSIS_WORKER_COUNT = 1

# Test-local ceilings (never shipped values): they bound how long a leg can hang if a
# mutant removes the exit it depends on.
DRAIN_CEILING = 1.5
STOP_TEST_TIMEOUT = 1.5

# The queue-depth script used by the drain legs.
PENDING_AT_START = 3


# =============================================================================
# Observation helpers (inlined - the sibling batteries keep these file-locally)
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


def texts(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [r.msg for r in at(caplog, level)]


def pin_record(record: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped single-argument log call.

    Every site this file cites passes ONE already-built message, so ``args`` must stay
    empty and ``exc_info`` must stay absent - the ``except`` arm does NOT hand the
    exception object to the logger, it interpolates ``{e}`` into the text.
    """
    assert record.msg == msg, f"log text mutated: {record.msg!r} != {msg!r}"
    assert record.levelno == level, f"log level mutated: {record.levelno} != {level}"
    assert tuple(record.args or ()) == (), f"unexpected lazy args for this site: {record.args!r}"
    assert record.exc_info is None, (
        f"exc_info present where the shipped call passes none: {record.exc_info!r}"
    )


def only(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    records = at(caplog, level)
    assert len(records) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in records]}"
    )
    pin_record(records[0], msg=msg, level=level)
    return records[0]


def named(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` WITH THIS TEXT, matching every field.

    Used where the shipped call is one of several records at that level in the window (the
    drain legs log ``stop_accepting()``'s INFO first), so ``only()``'s window-wide count
    would be wrong while the per-record pin is still exact.
    """
    records = [r for r in at(caplog, level) if r.msg == msg]
    assert len(records) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record {msg!r}, got "
        f"{[(r.levelno, r.msg) for r in at(caplog, level)]}"
    )
    pin_record(records[0], msg=msg, level=level)
    return records[0]


# =============================================================================
# Doubles and construction helpers
# =============================================================================


def settings_double() -> Any:
    """autospec'd ``Settings`` instance carrying the values these legs inject.

    Built from the real class, so a renamed attribute at a shipped read site raises
    ``AttributeError`` here instead of passing silently.
    """
    spec = create_autospec(Settings, instance=True)
    spec.use_redis_streams = False
    spec.video_frame_interval_seconds = 1.25
    spec.video_max_frames = 7
    spec.video_thumbnails_dir = THUMBNAIL_DIR
    spec.detection_worker_count = DETECTION_WORKER_COUNT
    spec.analysis_worker_count = ANALYSIS_WORKER_COUNT
    spec.batch_check_interval_seconds = BATCH_CHECK_INTERVAL
    return spec


class PatchedDouble:
    """``patch(target, new=double)`` that also hands the leg its ``double``.

    ``patch(target, autospec=True)`` builds the double itself and restores the real
    callable on exit without leaving a handle behind, so a leg that must read call records
    after its window has closed cannot use that spelling.  Every double here is
    ``create_autospec``'d from the shipped callable and installed with ``new=``.
    """

    def __init__(self, target: str, double: Any) -> None:
        self._context = patch(target, new=double)
        self.double = double

    def __enter__(self) -> Any:
        self._context.__enter__()
        return self.double

    def __exit__(self, *exc_info: Any) -> Any:
        return self._context.__exit__(*exc_info)


def patch_module(attribute: str, **autospec_kwargs: Any) -> PatchedDouble:
    """autospec'd ``patch("backend.services.pipeline_workers.<attribute>")``."""
    return PatchedDouble(
        f"{MOD}.{attribute}",
        create_autospec(getattr(M, attribute), **autospec_kwargs),
    )


def patch_settings() -> PatchedDouble:
    """``get_settings`` -> an autospec'd callable returning the injected double."""
    return PatchedDouble(
        f"{MOD}.get_settings",
        create_autospec(M.get_settings, return_value=settings_double()),
    )


def patch_running_loop(loop: RecordingLoop) -> PatchedDouble:
    """``asyncio.get_running_loop`` -> the given ``RecordingLoop``.

    The autospec'd part is the zero-argument accessor; ``RecordingLoop`` itself is the
    INJECTED value, not a mock of a real attribute.
    """
    return PatchedDouble(
        "asyncio.get_running_loop",
        create_autospec(asyncio.get_running_loop, side_effect=lambda: loop),
    )


def patch_time(**autospec_kwargs: Any) -> PatchedDouble:
    """``time.time`` -> a scripted double on the ONE ``time`` module object.

    ``drain_queues`` does a function-local ``import time`` (L1716) which binds the same
    module object the shipped ``time_module`` alias refers to, so one attribute patch
    reaches it.
    """
    return PatchedDouble("time.time", create_autospec(time_module.time, **autospec_kwargs))


class RecordingLoop:
    """Stand-in for the running loop inside ``_install_signal_handlers``.

    That method uses exactly one loop method (``add_signal_handler``, L1980), so an
    injected object with call records states the whole contract - and it keeps a real
    SIGTERM/SIGINT handler out of the pytest process.  ``side_effect`` makes the shipped
    ``except (NotImplementedError, RuntimeError)`` arm reachable on a Linux host, where a
    Windows ``ProactorEventLoop`` cannot be constructed.
    """

    def __init__(self, *, side_effect: BaseException | None = None) -> None:
        self.added: list[tuple[Any, Any]] = []
        self._side_effect = side_effect

    def add_signal_handler(self, sig: Any, handler: Any, *args: Any, **kwargs: Any) -> None:
        if self._side_effect is not None:
            raise self._side_effect
        self.added.append((sig, handler))

    @property
    def signals(self) -> list[Any]:
        return [s for s, _handler in self.added]

    def handler_for(self, sig: Any) -> Any:
        matches = [h for s, h in self.added if s is sig]
        assert len(matches) == 1, f"expected exactly one handler for {sig!r}: {self.signals!r}"
        return matches[0]


def record_task(sink: list[asyncio.Task]) -> Any:
    """autospec'd ``asyncio.create_task`` double that records the task it creates.

    It delegates to the REAL ``create_task`` so a handler's scheduled coroutine actually
    runs; the ``create_task(None)`` variant instead raises ``TypeError`` inside the
    handler, which the legs below pin with ``raised == []``.
    """

    def spy(*args: Any, **kwargs: Any) -> asyncio.Task:
        task = _REAL_CREATE_TASK(*args, **kwargs)
        sink.append(task)
        return task

    return create_autospec(asyncio.create_task, side_effect=spy)


def build_manager(**kwargs: Any) -> tuple[PipelineWorkerManager, dict[str, Any]]:
    """A manager built by the shipped ``__init__`` with no real worker attached.

    Two layers of substitution, both autospec'd and passed via ``new=`` so the doubles stay
    readable after the window:

    1. during construction each worker CLASS is an autospec'd constructor double, so
       ``__init__`` runs its shipped branches (the ``enable_*`` flags, the ``worker_stop_
       timeout`` pair of arms, the NEM-5375 count loops) and stores a spec'd instance
       double in the matching attribute - AsyncMock ``start``/``stop``, MagicMock
       ``running``/``stats``; and
    2. ``BatchAggregator`` (which the constructor builds directly at L1561) is patched too,
       and ``websocket_emitter`` stays ``None`` so the shipped ``broadcast_worker_event``
       helper takes its documented no-emitter arm.

    No real worker loop or task is ever started, and the ``start()`` / ``stop()`` /
    ``drain_queues`` control flow - the ``asyncio.TaskGroup`` bodies included - is the
    shipped one.  Returns ``(manager, doubles)`` mapping the worker attribute name to its
    instance double.
    """
    kwargs.setdefault("enable_detection_worker", False)
    kwargs.setdefault("enable_analysis_worker", False)
    kwargs.setdefault("enable_timeout_worker", True)
    kwargs.setdefault("enable_metrics_worker", False)
    patches = {
        "_detection_worker": patch_module("DetectionQueueWorker"),
        "_analysis_workers": patch_module("AnalysisQueueWorker"),
        "_timeout_worker": patch_module("BatchTimeoutWorker"),
        "_metrics_worker": patch_module("QueueMetricsWorker"),
    }
    with contextlib.ExitStack() as stack:
        doubles: dict[str, Any] = {}
        for attribute, patcher in patches.items():
            factory = stack.enter_context(patcher)
            doubles[attribute] = factory.return_value
        stack.enter_context(patch_settings())
        stack.enter_context(patch_module("BatchAggregator"))
        manager = PipelineWorkerManager(redis_client=MagicMock(name="manager-redis"), **kwargs)
    return manager, doubles


class StepClock:
    """``time.time`` double stepping ``step`` seconds per call.

    ``drain_queues`` reads the clock once at L1718 and once per iteration at L1741, so a
    fixed step makes ``elapsed`` deterministic and lets a leg reach the shipped
    ``elapsed >= timeout`` comparison without sleeping.
    """

    def __init__(self, start: float = 1000.0, step: float = 0.05) -> None:
        self.t = start
        self.step = step
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        value = self.t
        self.t += self.step
        return value


async def run_drain(
    manager: PipelineWorkerManager,
    depths: list[int],
    *,
    clock: Any,
    ceiling: float = DRAIN_CEILING,
    **call_kwargs: Any,
) -> tuple[int | None, BaseException | None]:
    """Run ``manager.drain_queues(**call_kwargs)`` against a scripted queue depth.

    ``get_pending_count`` is an autospec'd method double installed with ``new=`` replaying
    ``depths`` and then repeating its last value (the shipped drain reads it once before the
    INFO at L1724 and once per iteration at L1754, so a leg can never starve on a mutated
    branch).  The ``ceiling`` is a TEST-LOCAL guard: a leg whose shipped exit disappeared
    reports a guard ``TimeoutError`` in milliseconds rather than burning a tier timeout.
    Returns ``(result_or_None, raised_or_None, counter)``.
    """
    script = list(depths)

    def next_depth(*_args: Any, **_kwargs: Any) -> int:
        # Replay the script, then keep returning the LAST value: the shipped drain re-reads
        # the depth every iteration, so a leg must never starve on a mutated branch.
        return script.pop(0) if len(script) > 1 else script[0]

    raised: BaseException | None = None
    result: int | None = None
    reads = 0
    counter = AsyncMock(name="get_pending_count", side_effect=next_depth)
    # ``new=`` on a CLASS attribute means the shipped ``self.get_pending_count()`` call
    # reaches the double unbound, so the double takes no arguments; the read COUNT is
    # taken inside the window because the double is not carried out of it.
    with (
        patch.object(M.PipelineWorkerManager, "get_pending_count", new=counter),
        patch_time(side_effect=clock),
    ):
        try:
            result = await _REAL_WAIT_FOR(manager.drain_queues(**call_kwargs), ceiling)
        except TimeoutError as exc:
            raised = exc
        reads = counter.await_count
    return result, raised, reads


# =============================================================================
# g16 - 1) the shipped registration shape + the confirmation DEBUG (m12-m15)
# =============================================================================


def test_install_logs_the_confirmation_debug_and_registers_both_signals(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``m12``/``m13``/``m14``/``m15`` (L1985 - ``arg->None`` / ``XX…XX`` wrap /
    ``.lower()`` / ``.upper()`` on the confirmation DEBUG) plus the registration shape.

    Shipped (pipeline_workers.py:1972-1988)::

        try:
            loop = asyncio.get_running_loop()

            def create_shutdown_handler(sig: signal.Signals) -> None:
                def handler() -> None: ...
                loop.add_signal_handler(sig, handler)

            create_shutdown_handler(signal.SIGTERM)
            create_shutdown_handler(signal.SIGINT)
            self._signal_handlers_installed = True
            logger.debug("Signal handlers installed for SIGTERM and SIGINT")
        except (NotImplementedError, RuntimeError) as e:
            logger.debug(f"Could not install signal handlers: {e}")

    A fresh manager starts with the flag clear (L1649), so this first install is the arm
    under test.  The DEBUG text is pinned RAW - one read kills the ``None``, the XX wrap and
    both case folds - and the window must hold EXACTLY one record so the failure arm cannot
    also have fired.  The two registrations must arrive in the shipped order: that is what
    "exactly two registrations (SIGTERM, SIGINT) per install()" means.
    """
    manager, _doubles = build_manager()
    assert manager._signal_handlers_installed is False, (
        "a fresh manager must start with the flag clear (L1649)"
    )
    loop = RecordingLoop()
    win(caplog)

    with patch_running_loop(loop):
        assert manager._install_signal_handlers() is None

    only(caplog, logging.DEBUG, SIGNALS_INSTALLED_DEBUG)
    assert texts(caplog, logging.INFO) == [], "installing handlers logs no INFO"
    assert texts(caplog, logging.WARNING) == []
    assert loop.signals == [signal.SIGTERM, signal.SIGINT], (
        f"registrations mutated: {loop.signals!r} - shipped registers exactly twice"
    )
    assert manager._signal_handlers_installed is True, (
        f"the shipped install ends by raising the flag: {manager._signal_handlers_installed!r}"
    )


def test_not_implemented_error_becomes_one_debug(caplog: pytest.LogCaptureFixture) -> None:
    """g16 ``m16`` (L1988 ``logger.debug(f"Could not install signal handlers: {e}")`` ->
    ``logger.debug(None)``).

    The ``NotImplementedError`` is produced by the INJECTED loop double (a Windows
    ``ProactorEventLoop`` cannot be constructed on this Linux host) and the shipped arm
    still interpolates it into the message.  ``str(NotImplementedError())`` is the empty
    string, so the shipped text ends at the colon - that exact value is pinned, along with
    the DEBUG-only shape and the untouched flag (L1984 is never reached).
    """
    manager, _doubles = build_manager()
    error = NotImplementedError()
    loop = RecordingLoop(side_effect=error)
    win(caplog)

    with patch_running_loop(loop):
        assert manager._install_signal_handlers() is None

    only(caplog, logging.DEBUG, SIGNAL_FAILED_DEBUG.format(error))
    assert texts(caplog, logging.INFO) == []
    assert texts(caplog, logging.WARNING) == []
    assert loop.added == [], "nothing may be registered when the install fails"
    assert manager._signal_handlers_installed is False, (
        "the failure arm never reaches the flag write at L1984"
    )


# =============================================================================
# g16 - 2) the installed handlers (m2 INFO text, m3 create_task argument)
# =============================================================================


async def test_sigterm_handler_logs_and_schedules_the_manager_stop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``m2`` (L1977 ``logger.info(None)``) + ``m3`` (L1978 ``create_task(None)``).

    The installed handler body (pipeline_workers.py:1976-1978)::

        def handler() -> None:
            logger.info(f"Received signal {sig.name}, initiating graceful shutdown")
            asyncio.create_task(self.stop())

    Two discriminators, in shipped order.  ``create_task(None)`` raises ``TypeError``
    SYNCHRONOUSLY - the real ``create_task`` insists on a coroutine - and
    ``_install_signal_handlers`` catches only ``NotImplementedError`` / ``RuntimeError``, so
    ``raised == []`` is m3's kill.  m2's ``logger.info(None)`` instead lands a ``None``
    message in the window, which the raw ``only()`` pin rejects.  The captured task is then
    awaited so the shipped ``manager.stop()`` really runs its ``asyncio.TaskGroup`` fan-out
    into the worker doubles - the proof that what ``create_task`` received WAS
    ``self.stop()``.
    """
    manager, doubles = build_manager()
    loop = RecordingLoop()
    created: list[asyncio.Task] = []

    win(caplog)
    with (
        patch_running_loop(loop),
        patch("asyncio.create_task", new=record_task(created)),
    ):
        manager._install_signal_handlers()
        handler = loop.handler_for(signal.SIGTERM)
        raised: list[BaseException] = []
        try:
            handler()
        except TypeError as exc:  # shipped never raises; create_task(None) does
            raised.append(exc)

    only(caplog, logging.INFO, SIGNAL_RECEIVED_INFO.format(signal.SIGTERM.name))
    assert raised == [], (
        f"the shipped handler cannot raise: {raised!r} - create_task(None) schedules "
        "nothing, so a SIGTERM would never start the shutdown"
    )
    assert len(created) == 1, f"create_task call count mutated: {created!r}"

    # A signal only ever arrives on a RUNNING manager, so the scheduled stop() takes its
    # fan-out arm rather than the L1896-1898 "not running" guard return.
    manager._running = True
    win(caplog)
    await _REAL_WAIT_FOR(created[0], timeout=STOP_TEST_TIMEOUT)
    assert doubles["_timeout_worker"].stop.await_count == 1, (
        "the scheduled stop() never reached the enabled timeout worker"
    )
    assert texts(caplog, logging.INFO) == [
        MANAGER_STOPPING_INFO,
        MANAGER_STOPPED_INFO,
    ], f"the scheduled shutdown logged {texts(caplog, logging.INFO)!r}"
    assert manager.running is False, "stop() cleared _running"


async def test_sigint_handler_names_SIGINT(caplog: pytest.LogCaptureFixture) -> None:
    """The SIGINT occurrence twin of ``m2`` / ``m3``.

    ``create_shutdown_handler(signal.SIGTERM)`` and ``create_shutdown_handler(signal.SIGINT)``
    are two calls, so each of those keys has TWO occurrences of the same mutated node and
    each closure captures its own ``sig``.  The interpolated name must be ``SIGINT`` here and
    never ``SIGTERM``; the same scheduling contract applies, so m2's ``None`` message and
    m3's ``TypeError`` are both caught in this leg as well.
    """
    manager, doubles = build_manager()
    loop = RecordingLoop()
    created: list[asyncio.Task] = []

    win(caplog)
    with (
        patch_running_loop(loop),
        patch("asyncio.create_task", new=record_task(created)),
    ):
        manager._install_signal_handlers()
        handler = loop.handler_for(signal.SIGINT)
        raised: list[BaseException] = []
        try:
            handler()
        except TypeError as exc:
            raised.append(exc)

    only(caplog, logging.INFO, SIGNAL_RECEIVED_INFO.format(signal.SIGINT.name))
    assert SIGNAL_RECEIVED_INFO.format(signal.SIGTERM.name) not in texts(caplog, logging.INFO), (
        "the SIGINT closure must interpolate SIGINT, not SIGTERM"
    )
    assert raised == [], f"the shipped handler cannot raise: {raised!r}"
    assert len(created) == 1, f"create_task call count mutated: {created!r}"

    manager._running = True
    win(caplog)
    await _REAL_WAIT_FOR(created[0], timeout=STOP_TEST_TIMEOUT)
    assert doubles["_timeout_worker"].stop.await_count == 1
    assert SIGNAL_RECEIVED_INFO.format(signal.SIGTERM.name) not in texts(caplog, logging.INFO), (
        "the SIGINT handler must not have logged the SIGTERM sentence"
    )


# =============================================================================
# g16 - 3) the installed-flag guard (m10 -> None, m11 -> False)
# =============================================================================


async def test_a_second_start_cycle_does_not_re_register(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``m10``/``m11`` (L1984 ``self._signal_handlers_installed = True`` -> ``None`` /
    ``False``) through the shipped caller's guard.

    ``start()`` (pipeline_workers.py:1837-1839)::

        # Install signal handlers (only once)
        if not self._signal_handlers_installed:
            self._install_signal_handlers()

    Under either variant the flag stays falsy, so the SECOND ``start()`` (after ``stop()``
    cleared ``_running``) re-enters the installer and the injected loop receives FOUR
    registrations instead of TWO.  The CALL COUNT is the kill, which is why this leg counts
    ``loop.signals``, the confirmation-DEBUG occurrences, and the flag itself.  The workers
    are constructor doubles and the websocket emitter is ``None``, so the real ``start()`` /
    ``stop()`` bodies run their shipped control flow - both ``asyncio.TaskGroup`` blocks and
    the no-emitter broadcast arms included - with nothing real attached.
    """
    manager, _doubles = build_manager()
    loop = RecordingLoop()
    win(caplog)

    with patch_running_loop(loop):
        await manager.start()
        assert manager._signal_handlers_installed is True
        assert manager.running is True
        assert loop.signals == [signal.SIGTERM, signal.SIGINT], (
            f"the first start registered {loop.signals!r}"
        )
        await manager.stop()
        assert manager.running is False
        await manager.start()

    assert loop.signals == [signal.SIGTERM, signal.SIGINT], (
        f"a start/stop/start cycle registered {loop.signals!r} - the guard at L1838 "
        "decides on the flag these two keys clear"
    )
    assert manager._signal_handlers_installed is True, (
        f"the installed flag mutated: {manager._signal_handlers_installed!r}"
    )
    assert texts(caplog, logging.DEBUG).count(SIGNALS_INSTALLED_DEBUG) == 1, (
        f"the installer ran more than once: {texts(caplog, logging.DEBUG)!r}"
    )


async def test_running_manager_warns_and_skips_re_install(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control for the flag pair: ``start()`` on a running manager takes the L1824-1826
    early return (one WARNING, zero registrations).

    The install guard sits AFTER that return, so a start/stop/start cycle is the only route
    back to it - which is why ``m10``/``m11`` need the cycle above rather than a second
    direct ``start()``.  ``stop()`` on a manager that never started is the sibling guard
    (L1896-1898): a DEBUG, no fan-out, and - importantly for the cycle leg - it does NOT
    clear ``_signal_handlers_installed``.
    """
    manager, doubles = build_manager()
    manager._running = True
    loop = RecordingLoop()
    win(caplog)

    with patch_running_loop(loop):
        assert await manager.start() is None

    only(caplog, logging.WARNING, ALREADY_RUNNING_WARNING)
    assert texts(caplog, logging.INFO) == [], (
        "the already-running arm returns before the Starting INFO"
    )
    assert loop.added == [], "a running manager must not install handlers"
    assert manager._signal_handlers_installed is False

    win(caplog)
    with patch_running_loop(RecordingLoop()):
        assert await manager.stop() is None
    assert NOT_RUNNING_DEBUG not in texts(caplog, logging.DEBUG), (
        "stop() on a RUNNING manager takes the fan-out arm, not the L1897 guard DEBUG"
    )
    assert texts(caplog, logging.INFO) == [
        MANAGER_STOPPING_INFO,
        MANAGER_STOPPED_INFO,
    ], f"stop() INFOs mutated: {texts(caplog, logging.INFO)!r}"
    assert doubles["_timeout_worker"].stop.await_count == 1, (
        "the running manager's stop() must fan out to the enabled worker double"
    )
    assert manager._signal_handlers_installed is False, (
        "stop() must leave the install flag alone - that is what the cycle leg relies on"
    )


# =============================================================================
# g16 - 4) drain_queues default (m1)
# =============================================================================


async def test_drain_default_logs_the_shipped_thirty_second_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``drain_queues m1`` (L1701 METHOD default ``timeout: float = 30.0`` -> ``31.0``)
    - the message + ``extra`` surface.

    Shipped (pipeline_workers.py:1724-1732)::

        initial_count = await self.get_pending_count()
        if initial_count == 0:
            logger.info("Queues already empty, no draining needed")
            return 0

        logger.info(
            f"Starting queue drain with {initial_count} pending tasks, timeout={timeout}s",
            extra={"initial_count": initial_count, "timeout": timeout},
        )

    Only a NO-ARGUMENT call consults the default, so this leg calls ``drain_queues()`` with
    nothing and pins both surfaces of the default: the interpolated message text and
    ``extra["timeout"]`` (the ``extra`` read also pins the two key names).
    ``get_pending_count`` answers 3 then 0, so the drain leaves through the shipped
    ``current_count == 0`` arm after one iteration and the completion INFO carries
    ``elapsed == 0.0`` (the clock is a constant while the drain loop turns).
    """
    manager, _doubles = build_manager()
    assert manager.accepting is True
    win(caplog)

    result, raised, reads = await run_drain(
        manager,
        [PENDING_AT_START, 0],
        clock=lambda: 500.0,
    )

    assert raised is None, f"the drain did not finish inside the test ceiling: {raised!r}"
    assert result == 0, f"the drained queue must report 0 remaining, got {result!r}"
    assert reads >= 2, (
        f"the drain read the depth {reads} times - shipped reads it once before the INFO "
        "and once per iteration"
    )
    assert manager.accepting is False, "drain_queues calls stop_accepting() first (L1721)"
    start_message = DRAIN_START_INFO.format(PENDING_AT_START, DRAIN_DEFAULT_TIMEOUT)
    done_message = DRAIN_DONE_INFO.format(0.0)
    assert texts(caplog, logging.INFO) == [
        STOP_ACCEPTING_INFO,
        start_message,
        done_message,
    ], f"drain INFO sequence mutated: {texts(caplog, logging.INFO)!r}"
    start = named(caplog, logging.INFO, start_message)
    assert start.initial_count == PENDING_AT_START, (
        f"extra.initial_count mutated: {start.initial_count!r}"
    )
    assert start.timeout == DRAIN_DEFAULT_TIMEOUT, (
        f"extra.timeout mutated: {start.timeout!r} != {DRAIN_DEFAULT_TIMEOUT!r}"
    )
    done = named(caplog, logging.INFO, done_message)
    assert done.initial_count == PENDING_AT_START, (
        f"completion extra.initial_count mutated: {done.initial_count!r}"
    )
    assert done.elapsed_seconds == 0.0, f"completion elapsed mutated: {done.elapsed_seconds!r}"
    assert texts(caplog, logging.WARNING) == [], (
        "a drain that finished must not log the timeout WARNING"
    )


async def test_explicit_timeout_reaches_the_message_and_extra_verbatim(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The control that keeps the drain INFO honest: an EXPLICIT timeout must reach both
    surfaces unchanged.

    Without this leg a variant that hard-coded ``30.0`` into the message and ``extra`` would
    still pass the default-value pin.  Read together, the two legs show both surfaces carry
    the PARAMETER - and that the parameter's shipped default is exactly ``30.0``.
    """
    manager, _doubles = build_manager()
    win(caplog)

    result, raised, reads = await run_drain(
        manager,
        [PENDING_AT_START, 0],
        clock=lambda: 500.0,
        timeout=12.5,
    )

    assert raised is None, f"the drain did not finish inside the test ceiling: {raised!r}"
    assert result == 0
    message = DRAIN_START_INFO.format(PENDING_AT_START, 12.5)
    start = named(caplog, logging.INFO, message)
    assert start.initial_count == PENDING_AT_START
    assert start.timeout == 12.5, f"extra.timeout mutated: {start.timeout!r}"


async def test_drain_default_lets_the_elapsed_ge_timeout_comparison_decide(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The third surface of g16 ``drain_queues m1``: ``elapsed >= timeout`` (L1742).

    Shipped (pipeline_workers.py:1740-1752)::

        while True:
            elapsed = time.time() - start
            if elapsed >= timeout:
                remaining = await self.get_pending_count()
                logger.warning(
                    f"Queue drain timeout after {elapsed:.1f}s, {remaining} tasks remaining",
                    extra={
                        "elapsed_seconds": elapsed,
                        "remaining_count": remaining,
                        "initial_count": initial_count,
                    },
                )
                return remaining

    The clock steps 1.0 s per read and the queue depth is pinned at 2, so a drain given
    ``timeout=5.0`` returns the remaining 2 after ``elapsed`` reaches 5.0.  Under the
    ``31.0`` default mutant the SAME call (given the default) would keep polling a queue that
    never empties and hit the test ceiling instead - that is why this leg reads as a third
    occurrence of the default rather than a duplicate of the INFO pin.  It doubles as the
    pin of the timeout arm's message and its three ``extra`` fields.
    """
    manager, _doubles = build_manager()
    win(caplog)

    result, raised, reads = await run_drain(
        manager,
        [PENDING_AT_START, 2],
        clock=StepClock(start=1000.0, step=1.0),
        timeout=5.0,
    )

    assert raised is None, f"the timeout arm must return, not hang: {raised!r}"
    assert result == 2, f"the timeout arm must return the freshly read depth: {result!r}"
    warning = DRAIN_TIMEOUT_WARNING.format("5.0", 2)
    record = only(caplog, logging.WARNING, warning)
    assert record.elapsed_seconds == 5.0, (
        f"extra.elapsed_seconds mutated: {record.elapsed_seconds!r}"
    )
    assert record.remaining_count == 2, f"extra.remaining_count mutated: {record.remaining_count!r}"
    assert record.initial_count == PENDING_AT_START, (
        f"extra.initial_count mutated: {record.initial_count!r}"
    )
    assert texts(caplog, logging.INFO) == [
        STOP_ACCEPTING_INFO,
        DRAIN_START_INFO.format(PENDING_AT_START, 5.0),
    ], f"drain INFOs mutated: {texts(caplog, logging.INFO)!r}"
    assert DRAIN_DONE_INFO.format("5.0") not in texts(caplog, logging.INFO), (
        "a timed-out drain must not log the completion INFO"
    )


async def test_zero_pending_drain_returns_before_the_default_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``initial_count == 0`` early return (L1725-1727).

    This is the control that shows ``DRAIN_START_INFO`` fires exactly once per drain and only
    on the pending path, and that the default is never consulted on this arm - so the m1 kill
    really lives on the pending path above.
    """
    manager, _doubles = build_manager()
    win(caplog)

    result, raised, reads = await run_drain(manager, [0], clock=lambda: 500.0)

    assert raised is None, f"the empty-queue return must be immediate: {raised!r}"
    assert result == 0, f"the empty-queue arm returns 0, got {result!r}"
    assert reads == 1, f"the shipped guard reads the depth once (L1724), got {reads}"
    assert texts(caplog, logging.INFO) == [
        STOP_ACCEPTING_INFO,
        QUEUES_EMPTY_INFO,
    ], f"empty-drain INFOs mutated: {texts(caplog, logging.INFO)!r}"
    named(caplog, logging.INFO, QUEUES_EMPTY_INFO)
    assert texts(caplog, logging.WARNING) == []


async def test_stop_accepting_is_the_shipped_first_act_of_every_drain(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``stop_accepting()`` (L1721) and its INFO (L1679) run before any depth is read.

    Pinned so a drain leg cannot pass by skipping the side-effect half of the method, and so
    the INFO ordering contract - this INFO first - is on record.  The second call is the
    documented idempotent arm (L1675-L1677): one DEBUG, no second INFO.
    """
    manager, _doubles = build_manager()
    assert manager.accepting is True
    win(caplog)

    result, raised, reads = await run_drain(
        manager,
        [PENDING_AT_START, 0],
        clock=lambda: 500.0,
    )

    assert raised is None and result == 0
    assert manager.accepting is False
    assert texts(caplog, logging.INFO)[0] == STOP_ACCEPTING_INFO, (
        f"INFO order mutated: {texts(caplog, logging.INFO)!r}"
    )
    assert reads >= 2, "stop_accepting must not skip the depth read"

    win(caplog)
    assert manager.stop_accepting() is None
    only(caplog, logging.DEBUG, "PipelineWorkerManager already not accepting new tasks")


# =============================================================================
# g16 - 5) get_status timeout slot (m26)
# =============================================================================


def test_get_status_stores_the_timeout_workers_own_to_dict() -> None:
    """g16 ``get_status m26`` (L1807 ``status["workers"]["timeout"] =
    self._timeout_worker.stats.to_dict()`` -> ``= None``).

    Shipped (pipeline_workers.py:1806-1807)::

        if self._timeout_worker:
            status["workers"]["timeout"] = self._timeout_worker.stats.to_dict()

    The slot IS the enabled worker's ``to_dict()`` RESULT, so it is pinned by IDENTITY
    against a sentinel return value: the ``None`` variant fails that read immediately, and a
    rebuilt look-alike would fail it too.  ``get_status`` logs nothing, so the empty window is
    part of the contract.
    """
    manager, doubles = build_manager(enable_metrics_worker=True)
    sentinel = {
        "items_processed": 4,
        "errors": 1,
        "last_processed_at": 12.5,
        "state": WorkerState.RUNNING.value,
    }
    doubles["_timeout_worker"].stats.to_dict.return_value = sentinel
    doubles["_metrics_worker"].running = True
    manager._running = True
    manager._accepting = False

    status = manager.get_status()

    assert status["workers"]["timeout"] is not None, (
        "the timeout slot became None - shipped stores the worker's to_dict()"
    )
    assert status["workers"]["timeout"] is sentinel, (
        f"the timeout slot must BE the worker's own to_dict() result: "
        f"{status['workers']['timeout']!r}"
    )
    assert doubles["_timeout_worker"].stats.to_dict.call_count == 1, (
        f"to_dict call count mutated: {doubles['_timeout_worker'].stats.to_dict.call_count}"
    )
    assert status["workers"]["metrics"] == {"running": True}, (
        "the metrics slot is the running flag, not a stats dict"
    )
    assert "detection" not in status["workers"] and "analysis" not in status["workers"], (
        f"disabled workers grew slots: {sorted(status['workers'])!r}"
    )
    assert status["running"] is True and status["accepting"] is False


def test_get_status_timeout_slot_carries_the_real_stats_dict() -> None:
    """The same slot read against a REAL ``WorkerStats``, which additionally pins
    ``to_dict()["state"]`` as the enum's ``.value`` and the shipped field set.

    The double above proves identity; this one proves the payload the shipped line stores is
    a genuine stats snapshot rather than an unrelated dict, so a variant that stored e.g. the
    worker object or a hand-built dict would not pass either leg.
    """
    manager, _doubles = build_manager()
    stats = M.WorkerStats()
    manager._timeout_worker.stats = stats

    status = manager.get_status()

    assert status["workers"]["timeout"] == stats.to_dict(), (
        f"timeout slot mutated: {status['workers']['timeout']!r}"
    )
    assert status["workers"]["timeout"]["state"] == WorkerState.STOPPED.value, (
        "to_dict reports the enum's .value, not the enum or its name"
    )
    assert status["workers"]["timeout"]["items_processed"] == 0
    assert status["workers"]["timeout"]["errors"] == 0


def test_get_status_omits_a_disabled_timeout_worker() -> None:
    """The "absent vs ``None``" control for ``get_status m26``.

    With the timeout worker disabled the attribute stays ``None``, the shipped ``if`` never
    runs, and the KEY IS ABSENT.  The ``= None`` mutant writes ``"timeout": None`` into a slot
    shipped leaves out entirely - a different observable than this leg, and the reason both
    shapes are pinned so a ``None`` in the slot cannot be mistaken for a disabled worker.
    """
    manager, _doubles = build_manager(enable_timeout_worker=False)
    assert manager._timeout_worker is None

    status = manager.get_status()

    assert "timeout" not in status["workers"], (
        f"a disabled timeout worker must leave the slot absent: {status['workers']!r}"
    )
    assert status["workers"] == {}, f"unexpected worker slots: {status['workers']!r}"
    assert status["running"] is False and status["accepting"] is True


def test_get_status_fills_the_three_optional_slots_independently() -> None:
    """All four enabled workers at once: each ``if`` writes its own slot and the timeout slot
    keeps its ``to_dict()`` shape even beside the list-shaped slots.

    ``m26``'s ``None`` lands in exactly ONE of these four entries, so the multi-slot view is
    what keeps the kill specific rather than incidental.
    """
    manager, doubles = build_manager(
        enable_detection_worker=True,
        enable_analysis_worker=True,
        enable_metrics_worker=True,
    )
    timeout_sentinel = {"state": WorkerState.STOPPED.value, "items_processed": 2}
    doubles["_timeout_worker"].stats.to_dict.return_value = timeout_sentinel
    doubles["_metrics_worker"].running = False

    status = manager.get_status()
    workers = status["workers"]

    assert set(workers) == {"detection", "analysis", "timeout", "metrics"}, (
        f"slot set mutated: {sorted(workers)!r}"
    )
    assert workers["timeout"] is timeout_sentinel, f"timeout slot mutated: {workers['timeout']!r}"
    assert workers["metrics"] == {"running": False}, (
        f"metrics slot shape mutated: {workers['metrics']!r}"
    )
    for slot in ("detection", "analysis"):
        assert workers[slot]["count"] == 1, f"{slot} count mutated: {workers[slot]!r}"
        assert isinstance(workers[slot]["workers"], list), (
            f"{slot} workers must be a list: {workers[slot]!r}"
        )
