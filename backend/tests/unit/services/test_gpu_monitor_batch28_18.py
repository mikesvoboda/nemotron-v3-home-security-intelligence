"""S3 batch-28 lane gm18 - ``gpu_monitor`` groups g27 + g28 kill battery (49 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 ``2f122c85a072b7bd00c2e4b36cdc1cda``
- byte-identical to the manifest-proven source). Admitted manifest:
``/tmp/wp-pw/gpu_monitor/manifest.json`` group 27 (G14 ``stop()``, 19 keys) and
group 28 (G15 ``_poll_loop``, 30 keys) - both KILLABLE, 0 EQUIVALENT - plus
``group_27.keys`` / ``group_28.keys`` and ``survivors.json`` for the exact diffs.

Test -> mutant-key map
======================
Every key below is in ``group_27.keys`` or ``group_28.keys``. Splice report
``splice-group_27.json`` flags NOTHING (19/19 clean, no twins). Splice report
``splice-group_28.json`` flags ``_poll_loop__mutmut_16`` and
``_poll_loop__mutmut_18`` as **unparseable** (mutmut reprints the multi-line
``logger.error(...)`` call so the harness splice does not compile) and
``_poll_loop__mutmut_9`` as a **twin** (two candidates: L1118 and L1135 carry the
identical ``await asyncio.sleep(self.poll_interval)`` text). The twin is proven by
the harness reddening EVERY candidate, and this battery reddens both legs through
the shipped ``poll_interval`` identity - L1118 in the healthy-pass test and L1135
in the error-retry tests. The two unparseable keys were built and killed MANUALLY:
probe script ``/tmp/wp-pw/gm/manual/manual_prove.py`` run as
``manual_prove.py pl28_m16`` / ``manual_prove.py pl28_m18`` against THIS file (built
mutants ``mut_pl28_m16.py`` / ``mut_pl28_m18.py``, verdicts
``result_pl28_m16.json`` / ``result_pl28_m18.json``).

g14 - ``GPUMonitor.stop`` (``gpu_monitor.py:1157-1184``)
  * ``stop__mutmut_2`` L1160 ``logger.debug(None)``, ``_3`` wrapXX, ``_4`` lower,
    ``_5`` upper
    -> ``test_stopping_a_fresh_monitor_logs_only_the_not_running_debug`` (SOLE route:
       that arm logs nothing else and returns)
  * ``stop__mutmut_6`` L1163 ``logger.info(None)``, ``_7`` wrapXX, ``_8`` lower,
    ``_9`` upper; ``_21`` L1184 ``logger.info(None)``, ``_22`` wrapXX, ``_23`` lower,
    ``_24`` upper
    -> ``test_a_live_task_is_cancelled_between_the_shipped_info_pair`` (SOLE route:
       with NVML uninitialised the stopped path logs exactly those two INFO lines)
  * ``stop__mutmut_12`` L1167 ``and`` -> ``or``
    -> ``test_a_null_task_never_reaches_done_under_the_shipped_and`` (SOLE route:
       with ``_poll_task is None`` the shipped ``and`` short-circuits and never
       evaluates ``None.done()``; under ``or`` the right leg runs and the
       ``AttributeError`` escapes ``stop()``)
  * ``stop__mutmut_13`` L1167 ``not self._poll_task.done()`` ->
    ``self._poll_task.done()``
    -> ``test_a_finished_task_is_not_cancelled_again`` (SOLE route: a DONE task
       means shipped skips ``cancel()`` entirely; the mutant enters the body and
       cancels - observed through a recording stand-in)
  * ``stop__mutmut_16`` L1180 ``logger.debug(None)``, ``_17`` wrapXX, ``_18`` lower,
    ``_19`` upper
    -> ``test_initialized_nvml_is_shut_down_with_the_shipped_debug`` (SOLE route)
  * ``stop__mutmut_20`` L1182 ``logger.warning(f"Error shutting down NVML: {e}")``
    -> ``logger.warning(None)``
    -> ``test_nvml_shutdown_failure_becomes_the_shipped_interpolated_warning``
       (SOLE route: the L1180 DEBUG does not run on that path)

g15 - ``GPUMonitor._poll_loop`` (``gpu_monitor.py:1096-1137``)
  * ``_poll_loop__mutmut_1`` L1098 ``logger.info(None)``, ``_2`` wrapXX, ``_3``
    lower, ``_4`` upper
    -> ``test_a_healthy_pass_logs_the_pair_and_carries_the_stats_forward`` (first
       record of the run)
  * ``_35`` L1137 ``logger.info(None)``, ``_36`` wrapXX, ``_37`` lower, ``_38`` upper
    -> same test (last record of the run) and
       ``test_cancellation_logs_the_debug_and_still_reaches_the_stopped_info``
  * ``_6`` L1106 ``self._stats_history.append(stats)`` -> ``append(None)``
    -> ``test_a_healthy_pass_logs_the_pair_and_carries_the_stats_forward`` (the
       buffer must hold the SENTINEL the fixture returned, BY IDENTITY)
  * ``_9`` L1118/L1135 ``asyncio.sleep(self.poll_interval)`` -> ``sleep(None)``
    (TWIN - both occurrences reddens)
    -> ``test_a_healthy_pass_logs_the_pair_and_carries_the_stats_forward`` (L1118),
       ``test_the_error_pass_logs_the_shipped_context_then_retries`` and
       ``test_the_error_pass_sleeps_before_retries`` (L1135) - the spy asserts every
       delay equals ``monitor.poll_interval``
  * ``_10`` L1121 ``logger.debug(None)``, ``_11`` wrapXX, ``_12`` lower, ``_13`` upper
    -> ``test_cancellation_logs_the_debug_and_still_reaches_the_stopped_info``
  * ``_14`` L1122 ``break`` -> ``return``
    -> ``test_cancellation_logs_the_debug_and_still_reaches_the_stopped_info``
       (SOLE route: shipped ``break`` leaves the loop and still logs the L1137
       footer; ``return`` exits the function and that record never appears)
  * ``_16`` L1125 ``extra=None`` and ``_18`` L1125 ``extra`` dropped (both
    **UNPARSEABLE** -> ``manual_prove.py pl28_m16`` / ``manual_prove.py pl28_m18``)
    -> ``test_the_error_pass_logs_the_shipped_context_then_retries``
  * ``_19`` L1126 ``"Error in GPU monitor poll loop"`` -> wrapXX
    -> ``test_the_error_message_is_the_shipped_text_without_interpolation``
  * ``_22``/``_23`` L1128 ``"gpu_name"``, ``_24``/``_25`` L1129 ``"operation"``,
    ``_26``/``_27`` L1129 ``"poll_loop"``, ``_28``/``_29`` L1130 ``"error"``,
    ``_31``/``_32`` L1131 ``"error_type"``
    -> ``test_the_error_pass_logs_the_shipped_context_then_retries``
  * ``_30`` L1130 ``str(e)`` -> ``str(None)``, ``_33`` L1131 ``type(e)`` -> ``type(None)``
    -> same test (``error == "pollfail"`` / ``error_type == "RuntimeError"``)

Every leg above is MEASURED: each key was replayed against this battery in a
symlink shadow of this tree (``/tmp/wp-b28/replay_lib.py prove``), reddening with a
NAMED failed test for EVERY splice candidate, and this file is green on pristine
source.

Control legs that kill nothing of their own
(``test_uninitialised_nvml_is_never_touched``,
``test_the_stopped_info_is_logged_once_per_run``, and the state assertions of
``test_a_null_task_never_reaches_done_under_the_shipped_and``) complete the shipped
contract - L1175 keeps ``nvmlShutdown`` off the table until NVML was initialised,
the L1137 INFO is a per-run footer, and ``running`` (L1100) is the only thing that
owns the loop - so a killing leg can never be satisfied by an accidental
fall-through.

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it,
and every value an assertion depends on is injected by this file (a SENTINEL stats
dict, a scripted ``get_current_stats_async``, a recording ``asyncio.sleep`` spy, an
NVML stand-in in ``sys.modules``).

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg`` plus
  ``record.args`` / ``record.exc_info`` / ``record.levelno`` (the
  ``test_pipeline_workers_batch28_17.py`` pattern).  ``record.message`` is never
  used: it interpolates, which would hide the L1126 wrapper - and for the one
  f-string site (L1182) RAW ``msg`` plus empty ``args`` is exactly what pins that
  the interpolation happened IN the message.
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted.  The only timing surface is the shipped
  ``await asyncio.sleep(self.poll_interval)`` (L1118 / L1135), which is autospec'd
  for the window and asserted as a DELAY VALUE equal to ``monitor.poll_interval`` -
  never as elapsed wall-clock time. No real sleep elapses: the spy yields with a
  captured reference to the pre-patch ``asyncio.sleep(0)``.
* Mocks of real attributes are autospec'd (WP4.2 fast path):
  ``backend.services.gpu_monitor.get_settings``, ``shutil.which`` and
  ``asyncio.sleep``. Everything else is an INSTANCE-attribute seam: the shipped
  call sites reach ``self.get_current_stats_async()`` / ``self._store_stats()`` /
  ``self._broadcast_stats()`` / ``self.check_memory_pressure()`` through ``self``,
  so an instance attribute IS the shipped seam (restored by ``monkeypatch``).
* No import-time global spy: the ``sys.modules["pynvml"]`` entry that L210 and
  L1177 resolve is installed (with a raising ``nvmlInit`` in ``init_seam``, with the
  shutdown counter in ``nvml_module``) and restored per window, so construction never
  probes a real NVML library; nothing is written to the module under test at import
  time and no clock patch is session-scoped.
* No real sleeps and no unbounded loops: every drive is scripted, and the scripts
  raise ``AssertionError`` once a mutant exceeds the shipped number of passes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from backend.services import gpu_monitor as M
from backend.services.gpu_monitor import GPUMonitor

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__), L48)

pytestmark = [
    pytest.mark.unit,
]

# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# --- g14: stop() -------------------------------------------------------------
# L1160: logger.debug("GPUMonitor not running, nothing to stop")
NOT_RUNNING_DEBUG = "GPUMonitor not running, nothing to stop"
# L1163: logger.info("Stopping GPU monitoring")
STOPPING_INFO = "Stopping GPU monitoring"
# L1180: logger.debug("NVML shutdown successfully")
NVML_OK_DEBUG = "NVML shutdown successfully"
# L1182: logger.warning(f"Error shutting down NVML: {e}") - an f-string, so the RAW
# record.msg is the interpolated text: this prefix plus str(e).
NVML_FAIL_PREFIX = "Error shutting down NVML: "
# L1184: logger.info("GPU monitoring stopped")
STOPPED_INFO = "GPU monitoring stopped"

# --- g15: _poll_loop() -------------------------------------------------------
# L1098: logger.info("GPU monitoring poll loop started")
LOOP_START_INFO = "GPU monitoring poll loop started"
# L1121: logger.debug("GPU monitor poll loop cancelled")
LOOP_CANCEL_DEBUG = "GPU monitor poll loop cancelled"
# L1126: logger.error("Error in GPU monitor poll loop", extra={...})
LOOP_ERROR_MSG = "Error in GPU monitor poll loop"
# L1128-L1131: the shipped extra= dict, in the shipped key order.
LOOP_ERROR_CONTEXT = ("gpu_name", "operation", "error", "error_type")
LOOP_ERROR_OPERATION = "poll_loop"  # L1129 value
# L1137: logger.info("GPU monitoring poll loop stopped")
LOOP_STOP_INFO = "GPU monitoring poll loop stopped"

# The stimulus raised out of ``get_current_stats_async`` in the error legs. L1130
# is ``str(e)`` and L1131 ``type(e).__name__``, so both context values derive from it.
POLL_STIMULUS_TEXT = "pollfail"
# The GPU name L1128 puts into the context (``self._gpu_name``).
GPU_NAME = "NVIDIA RTX A5500"
# The shipped per-pass sleep value, asserted at L1118 and L1135.
POLL_INTERVAL = 0.25
# Hard ceiling on the passes any shipped path can take under these scripts.
PASS_CEILING = 4

# The stats object the scripted collector hands the loop (L1103); identity is what
# L1106 must append and what the downstream seams must receive.
SENTINEL: dict[str, Any] = {"gpu_name": GPU_NAME, "marker": "poll-loop-sentinel"}


# =============================================================================
# Construction seam
# =============================================================================

# L159-L163 read three settings; the poll_interval DEFAULT is left absurd so a leg
# that forgot the sleep spy blocks on a real sleep and dies to the shipped 5s
# pytest timeout instead of silently spinning.
_SETTINGS = {
    "gpu_poll_interval_seconds": 9999.0,
    "gpu_stats_history_minutes": 60,
    "gpu_http_timeout": 10.0,
}


def _settings_value() -> Any:
    mock = type("Settings", (), {})()
    for key, value in _SETTINGS.items():
        setattr(mock, key, value)
    return mock


def no_nvidia_lib() -> None:
    """Stand-in for ``pynvml.nvmlInit`` on a host with no NVML.

    ``_initialize_nvml`` calls it at L212 inside the OUTER ``try`` whose arms are
    ``except ImportError`` (L225) and ``except Exception`` (L229). A generic raise
    lands on L229, leaving ``_nvml_initialized`` / ``_gpu_available`` False - the
    shipped no-GPU state - WITHOUT touching a real NVML library. This matters for
    portability: the real ``pynvml`` IS importable in this interpreter, and on a GPU
    host ``nvmlInit`` would SUCCEED, setting ``_nvml_initialized`` True so ``stop()``
    entered the shipped L1175-L1182 NVML arm and broke the "no DEBUG / no WARNING"
    legs below. Construction is therefore pinned to one arm, not left to the host.
    """
    raise RuntimeError("NVML is not reachable from the test seam")


@contextlib.contextmanager
def init_seam() -> Iterator[Any]:
    """Neutralise the three environment reads ``GPUMonitor.__init__`` performs.

    * ``get_settings`` (L159) - autospec'd, so the shipped signature is enforced.
    * ``shutil.which`` - L240 ``shutil.which("nvidia-smi")`` would otherwise walk
      the real PATH and, on a hit, run a real ``subprocess.run`` (routed here to the
      shipped L263-L264 "nvidia-smi not found in PATH" DEBUG).
    * ``pynvml`` (L210 ``import pynvml``) - resolved through ``sys.modules``, so a
      per-window stand-in whose ``nvmlInit`` raises is the seam that reaches it (see
      ``no_nvidia_lib``); ``_nvml_initialized`` stays False, so ``stop()`` never
      reaches L1175-L1182 unless a leg sets it and installs ``nvml_module``. The
      entry the window started with is put back on exit - a per-window install,
      never an import-time spy.
    """
    saved = sys.modules.pop("pynvml", None)
    sys.modules["pynvml"] = SimpleNamespace(
        nvmlInit=no_nvidia_lib,
        NVMLError=Exception,
        __name__="pynvml",
    )
    try:
        with (
            patch.object(M, "get_settings", autospec=True) as settings,
            patch.object(M.shutil, "which", autospec=True, return_value=None),
        ):
            settings.side_effect = _settings_value
            yield settings
    finally:
        sys.modules.pop("pynvml", None)
        if saved is not None:
            sys.modules["pynvml"] = saved


def build_monitor(**kwargs: Any) -> GPUMonitor:
    """A real ``GPUMonitor`` built with no GPU, no subprocess and no real settings."""
    with init_seam():
        return GPUMonitor(**kwargs)


def scripted_monitor(
    monkeypatch: pytest.MonkeyPatch,
    script: list[Any],
    *,
    gpu_name: str = GPU_NAME,
) -> dict[str, Any]:
    """A monitor whose poll-loop collaborators are bounded instance seams.

    ``running`` is set True the way the shipped ``start()`` does it (L1149) - L1100
    ``while self.running`` is the ONLY thing that owns this loop, so the script owns
    the run length: serving the LAST scripted entry clears ``running`` (the shipped
    stop() clause the loop is designed to observe), and a collector call past the end
    of the script RAISES, so a mutant that ignored ``running`` hits the sleep spy's
    ceiling instead of spinning.

    Returns a rig dict: ``monitor`` plus the spy call logs (``sleeps`` / ``stored``
    / ``broadcast`` / ``pressure``).
    """
    monitor = build_monitor(poll_interval=POLL_INTERVAL)
    monitor._gpu_name = gpu_name
    monitor.running = True  # the shipped L1149 state that start() establishes
    pending = list(script)
    sleeps: list[Any] = []
    stored: list[Any] = []
    broadcast: list[Any] = []
    pressure = {"calls": 0}

    async def get_stats() -> dict[str, Any]:
        if not pending:
            raise AssertionError("get_current_stats_async ran past the scripted passes")
        entry = pending.pop(0)
        if not pending:
            monitor.running = False  # the shipped loop owner ends the run
        if isinstance(entry, BaseException):
            raise entry
        return entry

    async def store(stats: Any) -> None:
        stored.append(stats)

    async def send(stats: Any) -> None:
        broadcast.append(stats)

    async def pressure_check() -> None:
        pressure["calls"] += 1

    for attr, replacement in (
        ("get_current_stats_async", get_stats),
        ("_store_stats", store),
        ("_broadcast_stats", send),
        ("check_memory_pressure", pressure_check),
    ):
        monkeypatch.setattr(monitor, attr, replacement, raising=True)

    return {
        "monitor": monitor,
        "sleeps": sleeps,
        "stored": stored,
        "broadcast": broadcast,
        "pressure": pressure,
    }


@contextlib.contextmanager
def sleep_spy(sleeps: list[Any]) -> Iterator[SimpleNamespace]:
    """Autospec'd ``asyncio.sleep`` for the window, recording each requested delay.

    L1118 and L1135 both read ``await asyncio.sleep(self.poll_interval)``, so the
    module-level ``asyncio.sleep`` IS the shipped seam; ``autospec=True`` enforces
    its real ``(delay, result=None)`` signature. The spy records the delay and then
    yields cooperatively with the reference to the PRE-PATCH ``sleep`` it captured
    on entry (so it cannot recurse into itself), and raises past ``PASS_CEILING``
    rather than letting a mutant spin. Only delay VALUES are ever asserted.
    """
    real_sleep = asyncio.sleep

    async def spy_sleep(delay: Any, *args: Any, **kwargs: Any) -> None:
        sleeps.append(delay)
        if len(sleeps) > PASS_CEILING:
            raise AssertionError("the poll loop slept past any shipped path")
        await real_sleep(0)

    async def nap() -> None:
        await real_sleep(0)

    with patch("asyncio.sleep", autospec=True, side_effect=spy_sleep):
        yield SimpleNamespace(calls=sleeps, nap=nap)


def idle_loop() -> AsyncMock:
    """A coroutine double that returns immediately, so ``start()`` cannot spin."""

    async def idle() -> None:
        return None

    return AsyncMock(name="idle-poll-loop", side_effect=idle)


@contextlib.contextmanager
def nvml_module(shutdown: Any) -> Iterator[Any]:
    """Install an ``nvmlShutdown`` stand-in for the L1177 ``import pynvml``.

    The shipped name is resolved through ``sys.modules`` by the import statement
    inside ``stop()``, so a per-window ``sys.modules`` entry is the seam that
    reaches it. The entry is removed on exit and any prior entry restored, leaving
    no global mutation behind.
    """
    saved = sys.modules.pop("pynvml", None)
    double = SimpleNamespace(nvmlShutdown=shutdown, NVMLError=Exception, __name__="pynvml")
    sys.modules["pynvml"] = double
    try:
        yield double
    finally:
        sys.modules.pop("pynvml", None)
        if saved is not None:
            sys.modules["pynvml"] = saved


# =============================================================================
# Observation helpers (batch27_01 / pipeline_workers batch28_17 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load-bearing - it
    also drops the records ``__init__`` emits at L197 / L226 during ``build_monitor``.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def msgs(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [r.msg for r in at(caplog, level)]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped log call.

    Every site claimed here passes a single positional message with no lazy args
    (the L1182 site is an already-interpolated f-string, so its values land IN
    ``msg``), so ``args`` must stay empty and ``exc_info`` must be absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args: {r.args!r}"
    assert r.exc_info is None, (
        f"exc_info present where the shipped call passes none: {r.exc_info!r}"
    )


def only(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


# =============================================================================
# g14 - GPUMonitor.stop (gpu_monitor.py:1157-1184)
# =============================================================================


@pytest.mark.asyncio
async def test_stopping_a_fresh_monitor_logs_only_the_not_running_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_2``/``_3``/``_4``/``_5`` - the L1160 debug message.

    The shipped early return (L1161) means NOTHING else is logged and no state
    moves: no INFO, no task touched, ``running`` stays False.
    """
    monitor = build_monitor()
    assert monitor.running is False, "L166 initialises running=False"
    assert monitor._poll_task is None, "L167 initialises _poll_task=None"

    win(caplog)
    await monitor.stop()

    only(caplog, logging.DEBUG, NOT_RUNNING_DEBUG)
    assert at(caplog, logging.INFO) == [], "the not-running arm logs no INFO"
    assert at(caplog, logging.WARNING) == [], "the not-running arm logs no WARNING"
    assert at(caplog, logging.ERROR) == [], "the not-running arm logs no ERROR"
    assert monitor.running is False
    assert monitor._poll_task is None


@pytest.mark.asyncio
async def test_a_live_task_is_cancelled_between_the_shipped_info_pair(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_6``/``_7``/``_8``/``_9`` (L1163) and ``_21``/``_22``/``_23``/``_24`` (L1184).

    The live task is created through the SHIPPED ``start()`` (its poll loop is the
    bounded instance seam). With NVML uninitialised the shipped stop path logs
    EXACTLY two INFO lines - "Stopping GPU monitoring" before the cancel (L1163)
    and "GPU monitoring stopped" after the cleanup (L1184) - and the task ends
    cancelled with its ``CancelledError`` swallowed by the shipped L1169-L1170
    ``contextlib.suppress``.
    """
    monitor = build_monitor()
    loop = idle_loop()
    monitor._poll_loop = loop  # the L1153 seam: self._poll_loop()
    await monitor.start()
    task = monitor._poll_task
    assert task is not None and not task.done(), "start() leaves a live polling task"

    win(caplog)
    await monitor.stop()

    infos = at(caplog, logging.INFO)
    assert [r.msg for r in infos] == [STOPPING_INFO, STOPPED_INFO], (
        f"stop() INFO pair mutated: {[r.msg for r in infos]}"
    )
    pin_record(infos[0], msg=STOPPING_INFO, level=logging.INFO)
    pin_record(infos[1], msg=STOPPED_INFO, level=logging.INFO)
    assert task.cancelled(), "L1168 cancels the live task and L1170 awaits it"
    assert monitor.running is False, "L1164 clears the flag"
    assert monitor._poll_task is None, "L1172 drops the task reference"
    assert at(caplog, logging.WARNING) == [], "no NVML, so no shutdown warning"
    assert at(caplog, logging.DEBUG) == [], "no NVML, so no shutdown debug"


@pytest.mark.asyncio
async def test_a_null_task_never_reaches_done_under_the_shipped_and() -> None:
    """Kills ``stop__mutmut_12`` - L1167 ``and`` -> ``or``.

    ``running=True`` with ``_poll_task is None`` is a SHIPPED-REACHABLE state:
    ``stop()`` itself nulls the task at L1172, and ``start()`` leaves it None until
    L1153 assigns. The shipped ``self._poll_task and not self._poll_task.done()``
    short-circuits on the falsy left leg and never evaluates ``None.done()``; under
    ``or`` the right leg runs and the ``AttributeError`` escapes ``stop()``. The
    state assertions are control legs; the absence of a raise IS the kill.
    """
    monitor = build_monitor()
    monitor.running = True
    monitor._poll_task = None

    await monitor.stop()  # shipped: returns quietly (the mutant raises AttributeError)

    assert monitor.running is False, "L1164 runs before the guard"
    assert monitor._poll_task is None, "L1172 re-nulls the already-null task"


@pytest.mark.asyncio
async def test_a_finished_task_is_not_cancelled_again() -> None:
    """Kills ``stop__mutmut_13`` - L1167 ``not self._poll_task.done()`` (drop_unary:Not).

    A DONE task must be skipped entirely: shipped evaluates
    ``task and not task.done()`` -> False and never calls ``cancel()``; the mutant
    evaluates ``task and task.done()`` -> True and cancels. A recording stand-in
    makes that the only observable - everything after the guard is identical.
    """
    cancels: list[int] = []
    monitor = build_monitor()
    monitor.running = True
    monitor._poll_task = SimpleNamespace(  # type: ignore[assignment]
        done=lambda: True,
        cancel=lambda: cancels.append(1),
    )

    await monitor.stop()

    assert cancels == [], "shipped must NOT cancel an already-finished task"
    assert monitor._poll_task is None
    assert monitor.running is False


@pytest.mark.asyncio
async def test_initialized_nvml_is_shut_down_with_the_shipped_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_16``/``_17``/``_18``/``_19`` - the L1180 debug message.

    With ``_nvml_initialized`` True the shipped stop path calls
    ``pynvml.nvmlShutdown()`` (L1179) and logs the DEBUG (L1180). The two INFO
    lines around it keep their shipped texts, which is why they are pinned too.
    """
    shutdowns: list[int] = []
    monitor = build_monitor()
    monitor.running = True
    monitor._nvml_initialized = True

    win(caplog)
    with nvml_module(lambda: shutdowns.append(1)):
        await monitor.stop()

    assert shutdowns == [1], "L1179 calls nvmlShutdown exactly once"
    only(caplog, logging.DEBUG, NVML_OK_DEBUG)
    assert msgs(caplog, logging.INFO) == [STOPPING_INFO, STOPPED_INFO]
    assert at(caplog, logging.WARNING) == [], "a clean shutdown logs no warning"


@pytest.mark.asyncio
async def test_nvml_shutdown_failure_becomes_the_shipped_interpolated_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``stop__mutmut_20`` - L1182 ``logger.warning(f"Error shutting down NVML: {e}")``.

    The message is an f-string, so the RAW ``record.msg`` is the fully interpolated
    text (shipped prefix + ``str(e)``) and ``record.args`` stays empty - that pair
    is what separates the shipped call from ``logger.warning(None)``. The failure is
    swallowed, the L1180 DEBUG does NOT run on this path, and the L1184 INFO footer
    still runs.
    """
    monitor = build_monitor()
    monitor.running = True
    monitor._nvml_initialized = True

    def boom() -> None:
        raise RuntimeError("nvml-bye")

    win(caplog)
    with nvml_module(boom):
        await monitor.stop()

    warn = only(caplog, logging.WARNING, NVML_FAIL_PREFIX + "nvml-bye")
    assert warn.msg.startswith(NVML_FAIL_PREFIX), "L1182 prefix mutated"
    assert tuple(warn.args or ()) == (), "an f-string message carries no lazy args"
    assert at(caplog, logging.DEBUG) == [], "L1180 must be skipped when shutdown raised"
    assert msgs(caplog, logging.INFO) == [STOPPING_INFO, STOPPED_INFO], (
        "the shipped footer survives an NVML shutdown failure"
    )
    assert monitor.running is False


@pytest.mark.asyncio
async def test_uninitialised_nvml_is_never_touched(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control: L1175 ``if self._nvml_initialized`` keeps shutdown off the table.

    Kills nothing on its own, but it is what licenses the INFO-pair test to assert
    "no DEBUG at all" - if that guard fell, the NVML legs would be ambiguous.
    """
    shutdowns: list[int] = []
    monitor = build_monitor()
    monitor.running = True
    assert monitor._nvml_initialized is False, "L174 initialises to False"

    win(caplog)
    with nvml_module(lambda: shutdowns.append(1)):
        await monitor.stop()

    assert shutdowns == [], "an uninitialised NVML is never shut down"
    assert at(caplog, logging.DEBUG) == []
    assert msgs(caplog, logging.INFO) == [STOPPING_INFO, STOPPED_INFO]


# =============================================================================
# g15 - GPUMonitor._poll_loop (gpu_monitor.py:1096-1137)
# =============================================================================


@pytest.mark.asyncio
async def test_a_healthy_pass_logs_the_pair_and_carries_the_stats_forward(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_1``-``_4`` (L1098), ``_35``-``_38`` (L1137), ``_6`` (L1106), ``_9`` (L1118).

    One scripted pass, then the script releases the loop: the run's records are
    exactly the shipped INFO footer pair, the SENTINEL lands in ``_stats_history``
    BY IDENTITY (L1106 appends what L1103 returned - ``_6`` appends ``None``) and is
    forwarded to the store/broadcast/pressure seams, and the shipped sleep is
    awaited with the monitor's own ``poll_interval`` (L1118 - ``_9`` passes ``None``,
    which the spy records as a mutated delay).
    """
    rig = scripted_monitor(monkeypatch, [SENTINEL])
    monitor: GPUMonitor = rig["monitor"]

    win(caplog)
    with sleep_spy(rig["sleeps"]):
        await monitor._poll_loop()

    infos = at(caplog, logging.INFO)
    assert [r.msg for r in infos] == [LOOP_START_INFO, LOOP_STOP_INFO], (
        f"poll-loop INFO footer mutated: {[r.msg for r in infos]}"
    )
    pin_record(infos[0], msg=LOOP_START_INFO, level=logging.INFO)
    pin_record(infos[1], msg=LOOP_STOP_INFO, level=logging.INFO)
    assert len(monitor._stats_history) == 1, "one scripted pass appends exactly one entry"
    assert monitor._stats_history[-1] is SENTINEL, (
        "L1106 appends the stats the loop just collected, not None"
    )
    assert rig["stored"] == [SENTINEL], "the pass forwards the stats to _store_stats"
    assert rig["broadcast"] == [SENTINEL], "the pass forwards the stats to _broadcast_stats"
    assert rig["pressure"]["calls"] == 1, "the pass runs check_memory_pressure (NEM-1727)"
    assert rig["sleeps"] == [POLL_INTERVAL], (
        f"L1118 sleeps for self.poll_interval, got {rig['sleeps']!r}"
    )
    assert monitor.poll_interval == POLL_INTERVAL, "the delay IS the shipped attribute"
    assert at(caplog, logging.ERROR) == [], "a healthy pass logs no error"
    assert at(caplog, logging.DEBUG) == [], "a healthy pass logs no debug"


@pytest.mark.asyncio
async def test_cancellation_logs_the_debug_and_still_reaches_the_stopped_info(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_10``-``_13`` (L1121) and ``_14`` (L1122 ``break`` -> ``return``).

    Cancelling while the shipped loop is inside its L1118 sleep drives the L1120
    arm. Shipped ``break`` leaves the ``while`` and falls through to the L1137
    footer; the ``return`` mutant exits the FUNCTION, so that footer never appears -
    it is the sole observable for ``_14`` and is asserted alongside the exact
    cancelled-path DEBUG text.
    """
    rig = scripted_monitor(monkeypatch, [SENTINEL, SENTINEL])
    monitor: GPUMonitor = rig["monitor"]

    win(caplog)
    with sleep_spy(rig["sleeps"]) as spy:
        task = asyncio.create_task(monitor._poll_loop())
        while not spy.calls:
            await spy.nap()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    only(caplog, logging.DEBUG, LOOP_CANCEL_DEBUG)
    infos = msgs(caplog, logging.INFO)
    assert infos[0] == LOOP_START_INFO, f"start INFO mutated: {infos}"
    assert LOOP_STOP_INFO in infos, (
        "L1122 break leaves the loop and still logs the L1137 footer; the return "
        "mutant skips it entirely"
    )
    assert at(caplog, logging.ERROR) == [], "cancellation is not an error"
    assert monitor.running is True, "cancellation does not clear the running flag"


@pytest.mark.asyncio
async def test_the_error_pass_logs_the_shipped_context_then_retries(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_16``/``_18`` (L1125 ``extra`` -> ``None`` / dropped; both UNPARSEABLE,
    killed via ``manual_prove.py pl28_m16`` / ``pl28_m18``), ``_22``/``_23`` (L1128
    ``"gpu_name"``), ``_24``/``_25`` (L1129
    ``"operation"``), ``_26``/``_27`` (L1129 ``"poll_loop"``), ``_28``/``_29`` (L1130
    ``"error"``), ``_30`` (L1130 ``str(e)`` -> ``str(None)``), ``_31``/``_32`` (L1131
    ``"error_type"``) and ``_33`` (L1131 ``type(e)`` -> ``type(None)``).

    The shipped error arm (L1123) logs ONE ERROR carrying the shipped four-key
    ``extra`` and then RETRIES (L1135 sleeps, the loop runs the next pass). Every
    context key is read BY NAME and pinned to its shipped value, so a renamed key
    and a mutated value each get their own leg, and the recovery leg proves the arm
    really did continue rather than abort.
    """
    stimulus = RuntimeError(POLL_STIMULUS_TEXT)
    rig = scripted_monitor(monkeypatch, [stimulus, SENTINEL])
    monitor: GPUMonitor = rig["monitor"]

    win(caplog)
    with sleep_spy(rig["sleeps"]):
        await monitor._poll_loop()

    err = only(caplog, logging.ERROR, LOOP_ERROR_MSG)
    for key in LOOP_ERROR_CONTEXT:
        assert hasattr(err, key), f"shipped extra= key {key!r} is absent from the record"
    assert err.gpu_name == GPU_NAME, "L1128 must carry the monitor's own GPU name"
    assert err.operation == LOOP_ERROR_OPERATION, "L1129 value mutated"
    assert err.operation != "XXpoll_loopXX", "L1129 wrapped"
    assert err.error == str(stimulus), "L1130 must be str(e) of the stimulus"
    assert err.error != "None", "L1130 stopped describing the actual exception"
    assert err.error_type == type(stimulus).__name__, "L1131 must be type(e).__name__"
    assert err.error_type != "NoneType", "L1131 describes None, not the raised exception"
    # and the shipped "keep polling" clause: the retry pass completed
    assert monitor._stats_history[-1] is SENTINEL, "the loop recovered and ran the next pass"
    assert rig["sleeps"] == [POLL_INTERVAL, POLL_INTERVAL], (
        f"shipped sleep interval mutated on the retry/error path: {rig['sleeps']!r}"
    )
    assert rig["stored"] == [SENTINEL], "the failed pass stored nothing"
    assert msgs(caplog, logging.INFO) == [LOOP_START_INFO, LOOP_STOP_INFO]


@pytest.mark.asyncio
async def test_the_error_message_is_the_shipped_text_without_interpolation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_poll_loop__mutmut_19`` - the L1126 message wrapXX variant.

    The shipped text has no placeholder and no ``%``-args, so ``record.msg`` is the
    literal string and ``record.args`` stays empty - which is exactly what stops a
    ``"XX...XX"`` wrapper from hiding behind interpolation. A distinct stimulus keeps
    this leg independent of the context test above.
    """
    rig = scripted_monitor(monkeypatch, [ValueError("nope"), SENTINEL])
    monitor: GPUMonitor = rig["monitor"]

    win(caplog)
    with sleep_spy(rig["sleeps"]):
        await monitor._poll_loop()

    err = only(caplog, logging.ERROR, LOOP_ERROR_MSG)
    assert "%s" not in err.msg, "the shipped poll-loop error text is not a format template"
    assert tuple(err.args or ()) == (), "no lazy args on the shipped error call"
    assert err.levelno == logging.ERROR
    assert err.error == "nope"
    assert err.error_type == "ValueError"


@pytest.mark.asyncio
async def test_the_error_pass_sleeps_before_retries(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control + the SECOND twin leg of ``_9`` - L1135 sleeps ``self.poll_interval``.

    Three passes (error, error, healthy) show the loop can only be released by the
    shipped ``while self.running`` owner at L1100 and that every error arm sleeps at
    L1135. That site is the second splice candidate of the L1118 twin, so this leg is
    what kills the ``_9`` variant spliced there.
    """
    second = ValueError("second")
    stimulus = RuntimeError(POLL_STIMULUS_TEXT)
    rig = scripted_monitor(monkeypatch, [stimulus, second, SENTINEL])
    monitor: GPUMonitor = rig["monitor"]

    win(caplog)
    with sleep_spy(rig["sleeps"]):
        await monitor._poll_loop()

    errors = at(caplog, logging.ERROR)
    assert [r.msg for r in errors] == [LOOP_ERROR_MSG, LOOP_ERROR_MSG]
    assert [r.error for r in errors] == [POLL_STIMULUS_TEXT, "second"]
    assert [r.error_type for r in errors] == ["RuntimeError", "ValueError"]
    assert [r.gpu_name for r in errors] == [GPU_NAME, GPU_NAME]
    assert rig["sleeps"] == [POLL_INTERVAL, POLL_INTERVAL, POLL_INTERVAL], (
        f"shipped sleep interval mutated: {rig['sleeps']!r}"
    )
    assert len(monitor._stats_history) == 1, "only the healthy pass appended"
    assert msgs(caplog, logging.INFO) == [LOOP_START_INFO, LOOP_STOP_INFO]


@pytest.mark.asyncio
async def test_the_stopped_info_is_logged_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control: the L1137 footer is a per-run tail, not a per-pass one.

    Two healthy passes produce ONE footer - the assertion that stops a footer leg
    from being satisfied by a mid-loop record.
    """
    rig = scripted_monitor(monkeypatch, [SENTINEL, SENTINEL])
    monitor: GPUMonitor = rig["monitor"]

    win(caplog)
    with sleep_spy(rig["sleeps"]):
        await monitor._poll_loop()

    infos = msgs(caplog, logging.INFO)
    assert infos.count(LOOP_STOP_INFO) == 1
    assert infos.count(LOOP_START_INFO) == 1
    assert len(monitor._stats_history) == 2, "two scripted passes append two entries"
    assert rig["sleeps"] == [POLL_INTERVAL, POLL_INTERVAL]
