"""S3 batch-28 lane gm-20 - ``gpu_monitor`` groups G20 + G19 kill battery (35 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
verified identical to ``git show HEAD:backend/services/gpu_monitor.py``).
Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json`` groups idx 30
("G20 register_memory_pressure_callback: list append + debug extra", 5 KILLABLE)
and idx 31 ("G19 check_memory_pressure: guard branch group + DEBUG/ERROR log
contracts", 30 KILLABLE), plus ``group_30.keys`` / ``group_31.keys`` and
``survivors.json``.  This file is the manifest ``battery_file`` of BOTH groups, so
all 35 keys are claimed here and nowhere else.

Key -> test map
===============
G20 - ``xǁGPUMonitorǁregister_memory_pressure_callback__mutmut_N`` (L1279-L1283)
-------------------------------------------------------------------------------
* ``_2`` L1280 message -> ``None`` / ``_3`` L1280 ``extra`` -> ``None`` /
  ``_5`` L1280 ``extra=`` dropped - the three MULTI-LINE diffs the harness cannot
  splice (its AFTER text is re-indented wrongly, so the mutant does not compile;
  "unparseable" in ``splice-group_30.json``).  They are proven with hand-built
  mutants (``/tmp/wp-pw/gm/probe20/manual_mutants.py``) and reddened here by the
  same two legs the shipped site is pinned with: ``record.msg`` exactness (``_2``)
  and the ``record.callback_count`` attribute (``_3``/``_5``).
* ``_6`` L1282 ``"callback_count"`` -> ``"XXcallback_countXX"`` / ``_7`` ->
  ``"CALLBACK_COUNT"`` -> ``test_registration_logs_the_callback_name_and_count``
  (the renamed key leaves no ``callback_count`` attribute).
* The list wiring itself (``self._memory_pressure_callbacks.append(callback)``,
  L1279) is pinned by ``test_registered_callbacks_are_appended_in_order``: order +
  identity, so no leg above can be satisfied by an incidental fall-through.

G19 - ``xǁGPUMonitorǁcheck_memory_pressure__mutmut_N``
-----------------------------------------------------
* ``_10`` L1310 second ``or`` -> ``and`` ->
  ``test_missing_total_stats_log_the_debug_and_return_normal`` (used=5,
  ``total=None``: shipped takes the guard, the mutant falls through to
  ``5 / None`` -> TypeError -> the ERROR arm, so the LEVEL equality is the kill).
* ``_11`` L1310 first ``or`` -> ``and`` ->
  ``test_missing_used_stats_log_the_debug_and_return_normal`` (``used=None``,
  total=100: shipped takes the guard, the mutant falls through to
  ``None / 100`` -> TypeError -> ERROR).  The two rows are the distinct
  discriminating rows of the two ``Or``->``And`` twins.
* ``_15`` L1310 ``0`` -> ``1`` - TWO candidates (L1310 and the ``* 100.0`` at
  L1318), both killed:
  - ``test_zero_total_stats_log_the_debug_and_return_normal`` (total=0: shipped
    takes the guard; the ``== 1`` variant falls through to ``5 / 0`` ->
    ZeroDivisionError -> ERROR),
  - ``test_usage_percent_is_the_exact_ratio_times_one_hundred`` (used=80/total=100
    is 80.0% -> shipped NORMAL, the ``* 110.0`` variant 88.0% -> WARNING) and
    ``test_warning_leg_reports_the_percent_it_computed`` (the ``memory_usage_percent``
    extra is ``85.0`` shipped vs ``93.5``).
* ``_16`` L1312 message -> ``None`` / ``_17`` L1312 ``extra`` -> ``None`` /
  ``_18`` L1312 message dropped / ``_19`` L1312 ``extra`` dropped - the four
  MULTI-LINE "unparseable" diffs (probe:
  ``/tmp/wp-pw/gm/probe31/manual_mutants.py``); killed by the DEBUG message
  exactness + ``record.memory_used`` / ``record.memory_total`` attributes in the
  three guard tests.
* ``_20``/``_21``/``_22`` L1313 message XX / lower / upper -> the same three
  tests (``pin_record`` on the raw ``record.msg``).
* ``_23``/``_24`` L1314 ``"memory_used"`` key XX / upper - TWO candidates each
  (L1307 ``stats.get("memory_used")`` and the L1314 extra key), both killed:
  the L1314 twin by ``record.memory_used``, the L1307 twin by
  ``test_usage_percent_is_the_exact_ratio_times_one_hundred`` (the mutant reads a
  key that is absent, gets ``None``, and takes the DEBUG/NORMAL guard instead of
  the shipped 85.0% WARNING).
* ``_25``/``_26`` L1314 ``"memory_total"`` key XX / upper - the same two ways
  (L1308 ``stats.get("memory_total")`` twin killed by the same ratio test, where
  the shipped code computes CRITICAL from 96/100 and the mutant takes the guard).
* ``_45`` L1337 message -> ``None`` / ``_46`` L1337 ``extra`` -> ``None`` /
  ``_48`` L1337 ``extra=`` dropped - the three MULTI-LINE "unparseable" diffs of
  the ERROR arm (probe: ``/tmp/wp-pw/gm/probe31/manual_mutants.py``), killed by
  ``test_stats_failure_logs_the_exact_error_record``.
* ``_49``/``_50``/``_51`` L1338 message XX / lower / upper -> same test.
* ``_52``/``_53`` L1340 ``"operation"`` KEY XX / upper -> same test (the record
  attribute disappears); ``_54``/``_55`` L1340 VALUE
  ``"check_memory_pressure"`` XX / upper ->
  ``test_stats_failure_extra_payload_is_verbatim`` - ``extra`` never reaches the
  message, so the VALUE mutants need the raw payload.
* ``_56``/``_57`` L1341 ``"error"`` key XX / upper and ``_59``/``_60`` L1342
  ``"error_type"`` key XX / upper -> same test (record attributes).
* ``_58`` L1341 ``str(e)`` -> ``str(None)`` (``"stats"`` becomes ``"None"``) and
  ``_61`` L1342 ``type(e)`` -> ``type(None)`` (``"RuntimeError"`` becomes
  ``"NoneType"``) -> same test.

Occurrence-twins, measured (``/tmp/wp-pw/gm/replay_fixed.py`` documents the shared
harness' block-window bug that turns same-text occurrences elsewhere in the file
into "twins"): inside the real ``check_memory_pressure`` block the multi-candidate
keys are ``_15`` (2), ``_23``/``_24``/``_25``/``_26`` (2 each) and every one of
those candidates is reddened by this file.  For ``_52``/``_53``/``_56``/``_57``/
``_59``/``_60`` the second whole-file occurrence sits in the SIBLING function
``get_stats_from_db`` (killed by ``test_gpu_monitor_batch28_19.py``) and for
``_58``/``_61`` in ``_handle_pressure_level_change`` (killed by
``test_gpu_monitor_batch28_21.py``).

Shipped behaviour only.  Every pinned string is transcribed from the shipped file
at the line quoted in the test that asserts it; the stats the method reads are
injected through the monitor's own ``get_current_stats_async`` attribute, and the
level-change handler is replaced by a local ``AsyncMock`` on the numeric legs so
this group's assertions cannot be satisfied or masked by G21's code.

Discipline
----------
* Log assertions use a per-window ``caplog.set_level`` + ``caplog.clear()``
  filtered to this module's logger and read the RAW ``record.msg`` /
  ``record.levelno`` / ``record.args`` / ``record.exc_info``; the NEM-1123 extra
  contract is asserted as RECORD ATTRIBUTES (a renamed key, ``extra=None`` or a
  dropped ``extra`` kwarg removes the attribute).
* No clock patching anywhere in this file - ``datetime.now`` is untouched and no
  duration is asserted (neither group has a timing site).
* Every patch site names a REAL module attribute and uses ``new=`` or
  ``autospec=True`` (WP4.2); no import-time global spy - doubles are installed
  inside the test.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest

from backend.services import gpu_monitor as M

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L1281: logger.debug(f"Registered memory pressure callback: {callback.__name__}")
REGISTER_DEBUG = "Registered memory pressure callback: {}"

# L1313: logger.debug("Cannot determine memory pressure: missing memory stats")
MISSING_STATS_DEBUG = "Cannot determine memory pressure: missing memory stats"

# L1338: logger.error("Error checking memory pressure", extra={...})
CHECK_ERROR_MSG = "Error checking memory pressure"
# L1340: "operation": "check_memory_pressure"
CHECK_ERROR_OPERATION = "check_memory_pressure"

# L106/L107: MEMORY_PRESSURE_WARNING_THRESHOLD / MEMORY_PRESSURE_CRITICAL_THRESHOLD
WARNING_THRESHOLD = 85.0
CRITICAL_THRESHOLD = 95.0

# The fault injected into the error legs (``str(e)`` == "stats").
STATS_FAULT = "stats"


# =============================================================================
# Observation helpers (batch27_01 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load bearing.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped log call.

    ``record.msg`` is the RAW message.  Both shipped sites here pass a plain
    (already-interpolated) message plus ``extra``, so ``args`` stays empty - a
    moved or dropped message argument lands IN ``msg`` - and ``exc_info`` stays
    absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.getMessage() == msg, f"formatted text mutated: {r.getMessage()!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args: {r.args!r}"
    assert r.exc_info is None, f"exc_info present where shipped passes none: {r.exc_info!r}"


def only(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]!r}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


# =============================================================================
# Monitor double
# =============================================================================


@pytest.fixture
def monitor() -> Iterator[M.GPUMonitor]:
    """A mock-mode GPUMonitor (pynvml import fails, nvidia-smi absent).

    ``sys.modules["pynvml"] = None`` is the interpreter's OWN ImportError trigger,
    so the ctor takes its shipped ImportError arm and never touches a GPU.  The
    shipped memory-pressure state is asserted to be the shipped initial state so
    every counter/level pin below starts from a known place.
    """
    with (
        patch.dict("sys.modules", {"pynvml": None}),
        patch("backend.services.gpu_monitor.shutil.which", return_value=None, autospec=True),
    ):
        mon = M.GPUMonitor()
    assert mon._last_memory_pressure_level is M.MemoryPressureLevel.NORMAL  # L183
    assert mon._memory_pressure_callbacks == []  # L184
    assert mon._memory_pressure_warning_events == 0  # L185
    assert mon._memory_pressure_critical_events == 0  # L186
    yield mon


def stats_source(**values: object) -> AsyncMock:
    """Replace the monitor's own stats source with a shipped-shaped dict."""
    return AsyncMock(return_value=dict(values))


def failing_stats(text: str) -> AsyncMock:
    return AsyncMock(side_effect=RuntimeError(text))


# =============================================================================
# G20: register_memory_pressure_callback (group_30, 5 keys)
# =============================================================================


def cb1(_new: object, _old: object) -> None:  # pragma: no cover - callback double
    """A named, non-async pressure callback."""


def cb2(_new: object, _old: object) -> None:  # pragma: no cover - callback double
    """A second named pressure callback (order/identity pin)."""


def test_registered_callbacks_are_appended_in_order(monitor):
    """L1279 ``self._memory_pressure_callbacks.append(callback)``.

    Order and object identity, so the two registrations below are the shipped
    append (not an insert/replace) and the DEBUG legs can never be reached with a
    differently-built list.
    """
    monitor.register_memory_pressure_callback(cb1)
    monitor.register_memory_pressure_callback(cb2)
    assert monitor._memory_pressure_callbacks == [cb1, cb2], (
        f"append wiring mutated: {monitor._memory_pressure_callbacks!r}"
    )
    assert monitor._memory_pressure_callbacks[0] is cb1
    assert monitor._memory_pressure_callbacks[1] is cb2


def test_registration_logs_the_callback_name_and_count(monitor, caplog):
    """L1280-L1282: one DEBUG per registration, message EXACT and
    ``record.callback_count`` == the list length AT THAT MOMENT (1 then 2).

    ``record.msg`` exactness kills the message->``None`` mutant; the record
    ATTRIBUTE kills ``extra=None``, the dropped ``extra`` kwarg and both key
    renames (``"XXcallback_countXX"`` / ``"CALLBACK_COUNT"`` leave no
    ``callback_count`` attribute).
    """
    win(caplog)
    monitor.register_memory_pressure_callback(cb1)
    first = only(caplog, logging.DEBUG, REGISTER_DEBUG.format("cb1"))
    assert first.callback_count == 1, (  # L1282
        f'extra["callback_count"] mutated: {getattr(first, "callback_count", "<missing>")!r}'
    )

    win(caplog)
    monitor.register_memory_pressure_callback(cb2)
    second = only(caplog, logging.DEBUG, REGISTER_DEBUG.format("cb2"))
    assert second.callback_count == 2, (  # L1282
        f'extra["callback_count"] mutated: {getattr(second, "callback_count", "<missing>")!r}'
    )


def test_registration_debug_record_count_tracks_a_fresh_monitor(monitor, caplog):
    """The count is ``len(self._memory_pressure_callbacks)`` AFTER the append, so a
    third registration on the same monitor reports 3 (and the message name comes
    from ``callback.__name__``, not from an index)."""

    def third_callback(_new: object, _old: object) -> None:  # pragma: no cover
        """Third named callback."""

    monitor.register_memory_pressure_callback(cb1)
    monitor.register_memory_pressure_callback(cb2)
    win(caplog)
    monitor.register_memory_pressure_callback(third_callback)
    rec = only(caplog, logging.DEBUG, REGISTER_DEBUG.format("third_callback"))
    assert rec.callback_count == 3, (  # L1282
        f'extra["callback_count"] mutated: {getattr(rec, "callback_count", "<missing>")!r}'
    )
    assert len(mine(caplog)) == 1, f"registration logged twice: {[r.msg for r in mine(caplog)]!r}"


# =============================================================================
# G19: check_memory_pressure - the guard truth table (L1304-L1316)
# =============================================================================


def pin_missing_stats_debug(
    caplog: pytest.LogCaptureFixture, *, used: object, total: object
) -> logging.LogRecord:
    """The shipped DEBUG arm, pinned as text + LEVEL + both extra attributes.

    The LEVEL is what distinguishes the two ``Or``->``And`` twins and the
    ``0``->``1`` twin (each of them falls through into an arithmetic fault, which
    lands in the except arm and logs an ERROR instead); the two extra attributes
    are what distinguish ``extra=None``, the dropped ``extra`` kwarg, the dropped
    message and the four key renames.
    """
    rec = only(caplog, logging.DEBUG, MISSING_STATS_DEBUG)
    assert at(caplog, logging.ERROR) == [], (
        f"guard fell through into the error arm: {[r.msg for r in at(caplog, logging.ERROR)]!r}"
    )
    assert rec.memory_used == used, (  # L1314
        f'extra["memory_used"] mutated: {getattr(rec, "memory_used", "<missing>")!r}'
    )
    assert rec.memory_total == total, (  # L1314
        f'extra["memory_total"] mutated: {getattr(rec, "memory_total", "<missing>")!r}'
    )
    return rec


async def test_missing_used_stats_log_the_debug_and_return_normal(monitor, caplog):
    """``memory_used=None`` -> shipped DEBUG + NORMAL (kills the FIRST ``Or``->``And``
    twin, which needs ``total is None`` too and so falls through to ``None / 100``)."""
    monitor.get_current_stats_async = stats_source(memory_used=None, memory_total=100)
    monitor._handle_pressure_level_change = AsyncMock()
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.NORMAL, f"guard returned {level!r}"
    pin_missing_stats_debug(caplog, used=None, total=100)
    monitor._handle_pressure_level_change.assert_not_awaited()
    assert monitor._last_memory_pressure_level is M.MemoryPressureLevel.NORMAL


async def test_missing_total_stats_log_the_debug_and_return_normal(monitor, caplog):
    """``memory_total=None`` -> shipped DEBUG + NORMAL (kills the SECOND ``Or``->``And``
    twin, which needs ``memory_used is None`` too and so falls through to ``5 / None``)."""
    monitor.get_current_stats_async = stats_source(memory_used=5, memory_total=None)
    monitor._handle_pressure_level_change = AsyncMock()
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.NORMAL, f"guard returned {level!r}"
    pin_missing_stats_debug(caplog, used=5, total=None)
    monitor._handle_pressure_level_change.assert_not_awaited()


async def test_zero_total_stats_log_the_debug_and_return_normal(monitor, caplog):
    """``memory_total == 0`` -> shipped DEBUG + NORMAL (kills the ``0``->``1``
    guard candidate, which falls through to ``5 / 0`` -> ZeroDivisionError)."""
    monitor.get_current_stats_async = stats_source(memory_used=5, memory_total=0)
    monitor._handle_pressure_level_change = AsyncMock()
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.NORMAL, f"guard returned {level!r}"
    pin_missing_stats_debug(caplog, used=5, total=0)
    monitor._handle_pressure_level_change.assert_not_awaited()


async def test_both_missing_stats_log_the_debug_and_return_normal(monitor, caplog):
    """Both None (the shipped ``{}``-stats case): still exactly ONE DEBUG with both
    extras None - the row where all three guard clauses agree, so the record
    contract is pinned without any branch discrimination."""
    monitor.get_current_stats_async = stats_source()
    monitor._handle_pressure_level_change = AsyncMock()
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.NORMAL
    pin_missing_stats_debug(caplog, used=None, total=None)


async def test_usage_percent_is_the_exact_ratio_times_one_hundred(monitor, caplog):
    """L1318 ``usage_percent = (memory_used / memory_total) * 100.0``.

    80/100 is 80.0% - below the shipped 85.0 WARNING threshold, so the shipped
    code returns NORMAL and calls NO handler.  The ``* 100.0`` -> ``* 110.0``
    candidate computes 88.0% and returns WARNING.  The same leg also kills the
    ``stats.get("XXmemory_usedXX")`` / ``stats.get("MEMORY_TOTAL")`` candidates:
    with the key renamed the shipped code reads ``None`` and takes the DEBUG/NORMAL
    guard, which changes BOTH the record set and the handler call.
    """
    monitor.get_current_stats_async = stats_source(memory_used=80, memory_total=100)
    handler = AsyncMock()
    monitor._handle_pressure_level_change = handler
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.NORMAL, (
        f"usage 80.0% must stay NORMAL (thresholds {WARNING_THRESHOLD}/{CRITICAL_THRESHOLD}): "
        f"{level!r}"
    )
    assert at(caplog, logging.DEBUG) == [], (
        f"80/100 took the missing-stats guard: {[r.msg for r in at(caplog, logging.DEBUG)]!r}"
    )
    assert at(caplog, logging.ERROR) == []
    handler.assert_not_awaited()
    assert monitor._last_memory_pressure_level is M.MemoryPressureLevel.NORMAL


async def test_warning_leg_reports_the_percent_it_computed(monitor, caplog):
    """85/100 == 85.0% -> WARNING, and the handler receives EXACTLY the shipped
    ``(new_level, old_level, usage_percent)`` triple.

    ``usage_percent`` is the second candidate of the ``number:0->1`` key (the
    ``* 100.0`` -> ``* 110.0`` form hands the handler 93.5) and the
    ``stats.get(...)`` renames (a renamed key means no handler call at all).
    """
    monitor.get_current_stats_async = stats_source(memory_used=85, memory_total=100)
    handler = AsyncMock()
    monitor._handle_pressure_level_change = handler
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.WARNING, f"85.0% must be WARNING: {level!r}"
    handler.assert_awaited_once()
    assert handler.await_args[0] == (
        M.MemoryPressureLevel.WARNING,
        M.MemoryPressureLevel.NORMAL,
        85.0,
    ), f"handler args mutated: {handler.await_args!r}"
    assert monitor._last_memory_pressure_level is M.MemoryPressureLevel.WARNING  # L1333
    assert at(caplog, logging.ERROR) == []


async def test_critical_leg_and_the_no_change_repeat(monitor, caplog):
    """96/100 == 96.0% -> CRITICAL with the handler awaited once; a SECOND call at
    the same level does NOT re-invoke it (L1329-L1331 ``if new_level != old_level``).

    The repeat leg is the guard that keeps the change handler off the normal path,
    so a mutant that diverts into the except/DEBUG arm cannot hide behind an
    identical return value.
    """
    monitor.get_current_stats_async = stats_source(memory_used=96, memory_total=100)
    handler = AsyncMock()
    monitor._handle_pressure_level_change = handler
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.CRITICAL, f"96.0% must be CRITICAL: {level!r}"
    assert handler.await_args[0] == (
        M.MemoryPressureLevel.CRITICAL,
        M.MemoryPressureLevel.NORMAL,
        96.0,
    ), f"handler args mutated: {handler.await_args!r}"
    assert at(caplog, logging.DEBUG) == []
    assert at(caplog, logging.ERROR) == []

    win(caplog)
    again = await monitor.check_memory_pressure()
    assert again is M.MemoryPressureLevel.CRITICAL
    assert handler.await_count == 1, (
        f"unchanged level re-invoked the handler: {handler.await_count}"
    )
    assert mine(caplog) == [], f"no-change repeat logged: {[r.msg for r in mine(caplog)]!r}"


# =============================================================================
# G19: the error arm (L1336-L1346)
# =============================================================================


async def test_stats_failure_logs_the_exact_error_record(monitor, caplog):
    """``get_current_stats_async`` raises ``RuntimeError("stats")`` -> NORMAL plus
    exactly ONE ERROR.

    Pins the message text (kills message->``None`` and the XX/lower/upper
    variants) and every extra as a RECORD ATTRIBUTE - a renamed key moves the
    value (``record.operation`` / ``record.error`` / ``record.error_type``
    disappears), ``extra=None`` and the dropped kwarg leave nothing, and the
    ``str(None)`` / ``type(None)`` value mutants change the value while keeping
    the key.
    """
    monitor.get_current_stats_async = failing_stats(STATS_FAULT)
    monitor._handle_pressure_level_change = AsyncMock()
    win(caplog)
    level = await monitor.check_memory_pressure()

    assert level is M.MemoryPressureLevel.NORMAL, (
        "an error must return NORMAL to avoid unnecessary throttling"
    )
    rec = only(caplog, logging.ERROR, CHECK_ERROR_MSG)
    assert len(mine(caplog)) == 1, f"extra records: {[r.msg for r in mine(caplog)]!r}"
    assert rec.operation == "check_memory_pressure", (  # L1340 key
        f'extra["operation"] key mutated: {getattr(rec, "operation", "<missing>")!r}'
    )
    assert rec.error == STATS_FAULT, (  # L1341 str(e)
        f'extra["error"] mutated: {getattr(rec, "error", "<missing>")!r}'
    )
    assert rec.error_type == "RuntimeError", (  # L1342 type(e).__name__
        f'extra["error_type"] mutated: {getattr(rec, "error_type", "<missing>")!r}'
    )
    monitor._handle_pressure_level_change.assert_not_awaited()
    assert monitor._last_memory_pressure_level is M.MemoryPressureLevel.NORMAL


async def test_stats_failure_extra_payload_is_verbatim(monitor, caplog):
    """The ``extra`` DICT as the logger receives it.

    ``extra`` entries never reach the message, so the two VALUE mutants
    (``"check_memory_pressure"`` -> ``"XXcheck_memory_pressureXX"`` /
    ``"CHECK_MEMORY_PRESSURE"``) are invisible to the attribute asserts above and
    need the captured payload.
    """
    payloads: list[dict[str, object]] = []

    class _Grab(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.name == LOG_NAME:
                payloads.append(dict(record.__dict__))

    handler = _Grab()
    monitor.get_current_stats_async = failing_stats(STATS_FAULT)
    monitor._handle_pressure_level_change = AsyncMock()
    win(caplog)
    M.logger.addHandler(handler)
    try:
        level = await monitor.check_memory_pressure()
    finally:
        M.logger.removeHandler(handler)

    assert level is M.MemoryPressureLevel.NORMAL
    assert len(payloads) == 1, f"expected exactly one payload: {payloads!r}"
    payload = payloads[0]
    assert payload["operation"] == CHECK_ERROR_OPERATION, (
        f'extra["operation"] value mutated: {payload.get("operation")!r}'
    )
    assert payload["error"] == STATS_FAULT, f"extra mutated: {payload.get('error')!r}"
    assert payload["error_type"] == "RuntimeError", f"extra mutated: {payload.get('error_type')!r}"


async def test_stats_failure_of_another_type_keeps_the_contract(monitor, caplog):
    """A second fault type through the same arm: the shipped record follows the
    injected exception, not a hard-coded pair of strings (``error`` == the text,
    ``error_type`` == ``type(e).__name__``)."""
    monitor.get_current_stats_async = AsyncMock(side_effect=ValueError("bad stats"))
    monitor._handle_pressure_level_change = AsyncMock()
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.NORMAL
    rec = only(caplog, logging.ERROR, CHECK_ERROR_MSG)
    assert rec.operation == CHECK_ERROR_OPERATION
    assert rec.error == "bad stats", (
        f'extra["error"] mutated: {getattr(rec, "error", "<missing>")!r}'
    )
    assert rec.error_type == "ValueError", (
        f'extra["error_type"] mutated: {getattr(rec, "error_type", "<missing>")!r}'
    )


async def test_missing_stats_keys_do_not_reach_the_error_arm(monitor, caplog):
    """A stats dict with NEITHER key (the shipped ``{}`` from a mock-mode producer)
    is the guard's own case: DEBUG, never ERROR.

    This is the row that separates ``"memory_used"``/``"memory_total"`` renames AT
    THE ``stats.get`` SITES (both read ``None`` -> guard -> DEBUG, already pinned)
    from anything that could fall through into the except arm, and it pins the
    guard's LEVEL for a producer-shaped input rather than a crafted kwarg dict.
    """
    monitor.get_current_stats_async = AsyncMock(return_value={})
    monitor._handle_pressure_level_change = AsyncMock()
    win(caplog)
    level = await monitor.check_memory_pressure()
    assert level is M.MemoryPressureLevel.NORMAL
    pin_missing_stats_debug(caplog, used=None, total=None)


def test_pressure_thresholds_are_the_shipped_pairs() -> None:
    """L106-L107: the two module constants the guard and the level routing read.

    ``M.MEMORY_PRESSURE_*_THREADSHOLD`` is what ``check_memory_pressure`` looks up
    at L1321/L1323; pinning the values here means the WARNING/CRITICAL legs above
    discriminate the ARITHMETIC (``* 100.0``) rather than an incidental threshold.
    """
    assert M.MEMORY_PRESSURE_WARNING_THRESHOLD == WARNING_THRESHOLD, (
        f"warning threshold mutated: {M.MEMORY_PRESSURE_WARNING_THRESHOLD!r}"
    )
    assert M.MEMORY_PRESSURE_CRITICAL_THRESHOLD == CRITICAL_THRESHOLD, (
        f"critical threshold mutated: {M.MEMORY_PRESSURE_CRITICAL_THRESHOLD!r}"
    )


def test_memory_pressure_level_values_are_the_shipped_strings() -> None:
    """L122-L124 ``MemoryPressureLevel``: the ``.value`` strings the DEBUG/ERROR legs
    and the level routing depend on (pinned so ``is``-comparisons in the tests
    above cannot be satisfied by a re-declared enum)."""
    assert M.MemoryPressureLevel.NORMAL.value == "normal"
    assert M.MemoryPressureLevel.WARNING.value == "warning"
    assert M.MemoryPressureLevel.CRITICAL.value == "critical"
