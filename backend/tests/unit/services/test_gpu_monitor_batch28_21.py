"""S3 batch-28 lane gm-21 - ``gpu_monitor`` group G21 kill battery (36 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
verified identical to ``git show HEAD:backend/services/gpu_monitor.py``).
Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json`` group idx 32
("G21 _handle_pressure_level_change: counters, level routing, failure log +
exc_info", 36 KILLABLE), ``group_32.keys`` and ``survivors.json``.  This file is
that group's manifest ``battery_file``, so all 36 keys are claimed here.

Key -> test map (all keys ``xǁGPUMonitorǁ_handle_pressure_level_change__mutmut_N``;
L-numbers are shipped ``backend/services/gpu_monitor.py`` lines)
==============================================================================
* ``_2`` L1363 ``datetime.now(UTC)`` -> ``datetime.now(None)``
  -> ``test_warning_transition_stores_a_utc_aware_event_timestamp`` and
  ``test_critical_transition_stores_a_utc_aware_event_timestamp``.  ``now`` is not
  logged, so the observable is the SHIPPED public getter (L1425-L1432) which emits
  ``last_warning_event_at.isoformat()``: the shipped tz-aware value ends
  ``"+00:00"``, the naive mutant's does not (the assert is on the OFFSET text,
  never ``tzinfo is not None`` on a hand-built value).
* ``_4`` L1367 ``warning_events += 1`` -> ``= 1`` ->
  ``test_warning_events_accumulate_across_transitions`` (two WARNING transitions
  must reach 2; the plain-assign twin sticks at 1).
* ``_9`` L1370 ``critical_events += 1`` -> ``= 1`` ->
  ``test_critical_events_accumulate_across_transitions`` (same leg on CRITICAL).
* ``_14`` L1374 ternary ``and False`` (always ``"info"``) ->
  ``test_warning_and_normal_transitions_route_their_log_levels``: under it every
  transition logs INFO, so the WARNING record's ``levelno`` is 20 not 30.
* ``_15`` L1374 ternary ``or True`` (always ``"warning"``) -> the same test: the
  NORMAL-bound transition logs 30 instead of the shipped 20.
* ``_18`` L1374 ``!=`` -> ``==`` -> the same test (both rows flip at once).
* ``_26`` L1376 message -> ``None`` / ``_27`` L1376 ``extra`` -> ``None`` /
  ``_29`` L1376 the ``extra=`` line deleted - the three MULTI-LINE diffs the
  harness cannot splice ("unparseable" in ``splice-group_32.json``; proven with
  hand-built mutants in ``/tmp/wp-pw/gm/probe21/manual_mutants.py``).  Reddened by
  the message exactness (``_26``) and the five record attributes
  (``_27``/``_29``) in the two change-log tests.
* ``_30``/``_31`` L1380 ``"old_level"``, ``_32``/``_33`` L1381 ``"new_level"``,
  ``_34``/``_35`` L1382 ``"memory_usage_percent"``, ``_36``/``_37`` L1383
  ``"warning_threshold"``, ``_38``/``_39`` L1384 ``"critical_threshold"`` -> the
  same two change-log tests, via the record attributes.
* ``_47`` L1396 ``extra`` -> ``None`` and ``_50`` L1396 the ``extra=`` line
  deleted -> ``test_failing_callback_logs_the_exact_error_with_exc_info`` (record
  attrs).  ``_48`` L1396 ``exc_info=True`` -> ``exc_info=None`` and ``_64`` L1405
  the ``True`` in the trailing ``exc_info=True`` -> ``False`` -> the same test via
  ``record.exc_info`` TRUTHINESS plus ``rec.exc_info[0] is RuntimeError`` (audit
  correction #8: the shipped ``True`` -> ``False`` mutant leaves ``exc_info`` the
  FALSY ``False``, which ``is not None`` would happily accept - so the assert is
  truthiness + type, never ``is not None``).  ``_51`` L1396 deletes the trailing
  ``exc_info=True`` line: same truthiness leg.
* ``_52``/``_53`` L1399 ``"callback"``, ``_54``/``_55`` L1400 ``"new_level"``,
  ``_56``/``_57`` L1401 ``"old_level"``, ``_58``/``_59`` L1402 ``"error"``,
  ``_61``/``_62`` L1403 ``"error_type"`` -> the same test (record attrs).
* ``_60`` L1402 ``str(e)`` -> ``str(None)`` (``"cb!"`` -> ``"None"``) and ``_63``
  L1403 ``type(e)`` -> ``type(None)`` (``"RuntimeError"`` -> ``"NoneType"``) -> the
  same test and ``test_failing_callback_of_another_type_follows_the_injected_fault``.
* The callback-invocation wiring the failure log sits inside (L1389-L1394) is
  pinned by ``test_callbacks_run_in_order_and_async_callbacks_are_awaited``: sync
  and async callbacks both run, in registration order, exactly once each, so the
  ERROR leg above is reached through the shipped loop rather than by accident.

Occurrence-twins, measured (``/tmp/wp-pw/gm/twinsets_astwindow.json``; the shared
harness' block window truncates at a multi-line signature's closing paren and
then falls back to the WHOLE file, inventing twins - ``replay_fixed.py`` re-measures
with an AST window).  Inside the real ``_handle_pressure_level_change`` block
(L1348-L1406) the multi-candidate keys are exactly ``_30``/``_31`` (2: L1380 and
L1401), ``_32``/``_33`` (2: L1381 and L1400), ``_54``/``_55`` (2) and
``_56``/``_57`` (2) - each pair is the change-log line and the callback-failure
line, and BOTH candidates redden this file (measured per-candidate logs under
``/tmp/wp-pw/gm/replay_32.json.logs/``).  The other 28 splicable keys have ONE
candidate each inside the function.  Whole-file occurrences of the same text
outside the function - further ``datetime.now(UTC)`` sites for ``_2``, the
``"error"``/``"error_type"`` keys of the other five error logs for ``_58``-``_63``,
the ``True`` name for ``_64`` - appear only under that collapsed whole-file
window; those sites belong to other groups' functions and are reddened by the
sibling batteries ``test_gpu_monitor_batch28_{13,19,20}.py``.  The TRUE site of
every key here is confirmed against mutmut's own snapshot
(``/tmp/wp-pw/gpu_monitor/spans_copy.json`` + ``mutant_copy.py``).

Shipped behaviour only.  Levels, usage percentages and callbacks are injected
through the monitor's own attributes; the metrics getter (L1408-L1433) is read as
the shipped public surface it is.  ``datetime`` is frozen through a REAL module
attribute (``gpu_monitor.datetime``, imported at gpu_monitor.py:33) with a
``datetime`` SUBCLASS, so ``now(None)`` still returns a naive value (CPython
semantics) and the naive-vs-aware difference that kills ``_2`` stays observable.

Discipline
----------
* Log assertions use a per-window ``caplog.set_level`` + ``caplog.clear()``
  filtered to this module's logger and read the RAW ``record.msg`` /
  ``record.levelno`` / ``record.args`` / ``record.exc_info``.
* No ``time.monotonic`` / ``time.perf_counter`` patch anywhere and no duration is
  asserted; the only clock seam is the per-test ``M.datetime`` subclass that the
  manifest's "(c) now->None" leg requires.
* Every patch site names a REAL module attribute and uses ``new=`` or
  ``autospec=True`` (WP4.2); no import-time global spy.
* Async legs are plain ``async def`` tests under the repo's
  ``asyncio_mode = "auto"``; nothing sleeps.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from backend.services import gpu_monitor as M

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]

NORMAL = M.MemoryPressureLevel.NORMAL
WARNING = M.MemoryPressureLevel.WARNING
CRITICAL = M.MemoryPressureLevel.CRITICAL


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L1377-L1378: f"GPU memory pressure changed: {old} -> {new} (usage: {pct:.1f}%)"
CHANGE_MSG = "GPU memory pressure changed: {old} -> {new} (usage: {pct:.1f}%)"

# L1383-L1384: the two threshold extras (the L106-L107 constants)
WARNING_THRESHOLD = 85.0
CRITICAL_THRESHOLD = 95.0

# L1397: f"Memory pressure callback failed: {callback.__name__}"
CB_FAIL_MSG = "Memory pressure callback failed: {name}"

# The fault raised by the failing callback double (so ``str(e)`` == "cb!").
CB_FAULT = "cb!"

# Frozen clock for the timestamp legs (L1363 ``datetime.now(UTC)``).
FROZEN_NOW = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def frozen_datetime(moment: datetime) -> type[datetime]:
    """A ``datetime`` SUBCLASS whose ``now()`` returns ``moment``.

    ``datetime`` is a real module attribute of the module under test, so ``new=``
    is a legitimate seam.  Subclassing (rather than a ``MagicMock``) keeps
    ``timedelta`` arithmetic and ``isoformat()`` intact AND keeps ``now(None)``
    faithful to CPython: it returns a NAIVE datetime, which is exactly the
    difference the ``datetime.now(None)`` mutant must produce to be observable
    through the shipped metrics getter.
    """

    def now(cls: type[datetime], tz: object = None) -> datetime:
        return moment.astimezone(tz) if tz is not None else moment.replace(tzinfo=None)

    return type("FrozenDatetime", (datetime,), {"now": classmethod(now)})


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

    ``record.msg`` is the RAW message and every shipped site here passes an
    already-interpolated f-string, so ``args`` stays empty.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.getMessage() == msg, f"formatted text mutated: {r.getMessage()!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args: {r.args!r}"


def shape(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    """The ordered ``(levelno, msg)`` shape of everything this module logged."""
    return [(r.levelno, r.msg) for r in mine(caplog)]


def only(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level``, pinned.

    The shipped handler logs the CHANGE record and THEN (only if a callback
    raises) the failure ERROR, so the total record count of a leg is pinned
    separately by :func:`shape` at each call site rather than assumed here.
    """
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record, got {shape(caplog)!r}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


def pin_change_extra(rec: logging.LogRecord, *, old: str, new: str, pct: float) -> None:
    """L1380-L1384 as RECORD ATTRIBUTES.

    ``extra=None``, a dropped ``extra`` kwarg and every key rename (``"XXkXX"`` /
    ``"K"``) leave the asserted attribute MISSING; the value asserts pin the
    shipped thresholds and the caller's percentage.
    """
    assert rec.old_level == old, (
        f'extra["old_level"] mutated: {getattr(rec, "old_level", "<missing>")!r}'
    )
    assert rec.new_level == new, (
        f'extra["new_level"] mutated: {getattr(rec, "new_level", "<missing>")!r}'
    )
    assert rec.memory_usage_percent == pct, (
        f'extra["memory_usage_percent"] mutated: '
        f"{getattr(rec, 'memory_usage_percent', '<missing>')!r}"
    )
    assert rec.warning_threshold == WARNING_THRESHOLD, (
        f'extra["warning_threshold"] mutated: {getattr(rec, "warning_threshold", "<missing>")!r}'
    )
    assert rec.critical_threshold == CRITICAL_THRESHOLD, (
        f'extra["critical_threshold"] mutated: {getattr(rec, "critical_threshold", "<missing>")!r}'
    )


def pin_callback_extra(
    rec: logging.LogRecord, *, name: str, new: str, old: str, error: str, error_type: str
) -> None:
    """L1399-L1403 as RECORD ATTRIBUTES (the callback-failure contract)."""
    assert rec.callback == name, (
        f'extra["callback"] mutated: {getattr(rec, "callback", "<missing>")!r}'
    )
    assert rec.new_level == new, (
        f'extra["new_level"] mutated: {getattr(rec, "new_level", "<missing>")!r}'
    )
    assert rec.old_level == old, (
        f'extra["old_level"] mutated: {getattr(rec, "old_level", "<missing>")!r}'
    )
    assert rec.error == error, f'extra["error"] mutated: {getattr(rec, "error", "<missing>")!r}'
    assert rec.error_type == error_type, (
        f'extra["error_type"] mutated: {getattr(rec, "error_type", "<missing>")!r}'
    )


class PayloadGrab(logging.Handler):
    """Captures the record ``__dict__`` of every record of this module.

    ``extra`` entries never reach ``getMessage()``, so a handler-side capture is
    the second, payload-level observation of the same keys - the one an
    ``extra=None`` / dropped-kwarg mutant cannot satisfy.
    """

    def __init__(self) -> None:
        super().__init__()
        self.payloads: list[dict[str, object]] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name == LOG_NAME:
            self.payloads.append(dict(record.__dict__))


class GrabContext:
    """Installs/uninstalls a :class:`PayloadGrab` on the shipped logger."""

    def __init__(self) -> None:
        self.handler = PayloadGrab()

    def __enter__(self) -> PayloadGrab:
        M.logger.addHandler(self.handler)
        return self.handler

    def __exit__(self, *exc_info: object) -> bool:
        M.logger.removeHandler(self.handler)
        return False


def grab_logs() -> GrabContext:
    return GrabContext()


# =============================================================================
# Monitor double
# =============================================================================


@pytest.fixture
def monitor() -> Iterator[M.GPUMonitor]:
    """A mock-mode GPUMonitor (pynvml import fails, nvidia-smi absent).

    ``sys.modules["pynvml"] = None`` is the interpreter's OWN ImportError trigger,
    so the ctor takes its shipped ImportError arm and never touches a GPU.  The
    shipped memory-pressure initial state is asserted, so every counter and
    timestamp pin below starts from a measured place (L183-L188).
    """
    with (
        patch.dict("sys.modules", {"pynvml": None}),
        patch("backend.services.gpu_monitor.shutil.which", return_value=None, autospec=True),
    ):
        mon = M.GPUMonitor()
    assert mon._last_memory_pressure_level is NORMAL, "shipped L183 state drifted"
    assert mon._memory_pressure_callbacks == [], "shipped L184 state drifted"
    assert mon._memory_pressure_warning_events == 0, "shipped L185 state drifted"
    assert mon._memory_pressure_critical_events == 0, "shipped L186 state drifted"
    assert mon._last_warning_event_at is None, "shipped L187 state drifted"
    assert mon._last_critical_event_at is None, "shipped L188 state drifted"
    yield mon


# =============================================================================
# Callback doubles (module-level so they carry real ``__name__`` values)
# =============================================================================


def ok_sync(new_level: object, old_level: object) -> None:
    """A sync callback double; records its calls, returns None (not a coroutine)."""
    ok_sync.calls.append((new_level, old_level))


ok_sync.calls: list[tuple[object, object]] = []


def boom(_new_level: object, _old_level: object) -> None:
    """A sync callback that raises the pinned fault."""
    raise RuntimeError(CB_FAULT)


async def ok_async(new_level: object, old_level: object) -> None:
    """An async callback double (the shipped ``iscoroutine`` -> await arm)."""
    ok_async.calls.append((new_level, old_level))


ok_async.calls: list[tuple[object, object]] = []


@pytest.fixture(autouse=True)
def reset_callback_doubles() -> Iterator[None]:
    """Per-test reset of the callback double ledgers (no cross-test bleed)."""
    ok_sync.calls = []
    ok_async.calls = []
    yield


# =============================================================================
# L1373-L1386: level routing + the change log
# =============================================================================


async def test_warning_and_normal_transitions_route_their_log_levels(monitor, caplog):
    """L1374 ``log_level = "warning" if new_level != NORMAL else "info"``.

    Two rows, one per direction of the flip:
    * NORMAL -> WARNING at 87.3% logs at WARNING (30).  The ternary-forced
      ``and False`` mutant always logs "info" (20) and ``!=`` -> ``==`` routes
      this transition to "info" too.
    * WARNING -> NORMAL at 12.0% logs at INFO (20).  The forced ``or True``
      mutant always logs "warning" (30) and ``!=`` -> ``==`` also does.

    Both records are pinned message-exact (kills the ``None`` message) and with
    the full L1380-L1384 extra set as record attributes (kills ``extra=None``, the
    dropped kwarg and the ten key renames).
    """
    monitor._last_memory_pressure_level = NORMAL
    win(caplog)
    await monitor._handle_pressure_level_change(WARNING, NORMAL, 87.3)
    rec = only(caplog, logging.WARNING, CHANGE_MSG.format(old="normal", new="warning", pct=87.3))
    pin_change_extra(rec, old="normal", new="warning", pct=87.3)
    assert rec.exc_info is None, f"change log must not carry exc_info: {rec.exc_info!r}"
    assert shape(caplog) == [(logging.WARNING, rec.msg)], (
        f"unexpected record set for a WARNING transition: {shape(caplog)!r}"
    )

    monitor._last_memory_pressure_level = WARNING
    win(caplog)
    await monitor._handle_pressure_level_change(NORMAL, WARNING, 12.0)
    rec = only(caplog, logging.INFO, CHANGE_MSG.format(old="warning", new="normal", pct=12.0))
    pin_change_extra(rec, old="warning", new="normal", pct=12.0)
    assert shape(caplog) == [(logging.INFO, rec.msg)], (
        f"unexpected record set for a NORMAL-bound transition: {shape(caplog)!r}"
    )


async def test_critical_transition_record_carries_the_full_extra(monitor, caplog):
    """NORMAL -> CRITICAL at 97.65% logs at WARNING (the shipped routing sends
    every non-NORMAL transition to ``logger.warning``) and the percentage is
    formatted ``:.1f`` in the MESSAGE while the EXTRA keeps the raw float.

    That split pins ``memory_usage_percent`` (97.65) independently of the message
    ("97.7%"), so a mutant that moves the value or renames the key cannot satisfy
    both legs.
    """
    win(caplog)
    await monitor._handle_pressure_level_change(CRITICAL, NORMAL, 97.65)
    rec = only(
        caplog, logging.WARNING, "GPU memory pressure changed: normal -> critical (usage: 97.7%)"
    )
    pin_change_extra(rec, old="normal", new="critical", pct=97.65)
    assert shape(caplog) == [(logging.WARNING, rec.msg)], (
        f"unexpected record set for a CRITICAL transition: {shape(caplog)!r}"
    )


async def test_change_record_payload_is_verbatim(monitor, caplog):
    """The change ``extra`` DICT as the logger receives it, captured by a handler.

    The payload-level twin of the attribute leg: it is what a value-level mutation
    cannot hide behind, and it is the leg that the ``extra`` -> ``None`` and
    dropped-kwarg mutants fail outright (no keys at all).
    """
    win(caplog)
    with grab_logs() as grab:
        await monitor._handle_pressure_level_change(WARNING, NORMAL, 87.3)

    assert len(grab.payloads) == 1, f"expected one payload: {grab.payloads!r}"
    payload = grab.payloads[0]
    assert payload["msg"] == CHANGE_MSG.format(old="normal", new="warning", pct=87.3), (
        f"payload message mutated: {payload.get('msg')!r}"
    )
    assert payload["old_level"] == "normal", f"extra mutated: {payload.get('old_level')!r}"
    assert payload["new_level"] == "warning", f"extra mutated: {payload.get('new_level')!r}"
    assert payload["memory_usage_percent"] == 87.3, (
        f"extra mutated: {payload.get('memory_usage_percent')!r}"
    )
    assert payload["warning_threshold"] == WARNING_THRESHOLD, (
        f"extra mutated: {payload.get('warning_threshold')!r}"
    )
    assert payload["critical_threshold"] == CRITICAL_THRESHOLD, (
        f"extra mutated: {payload.get('critical_threshold')!r}"
    )


# =============================================================================
# L1363-L1371: counters and event timestamps
# =============================================================================


async def test_warning_events_accumulate_across_transitions(monitor):
    """L1367 ``self._memory_pressure_warning_events += 1`` read through the shipped
    getter (L1425 ``total_warning_events``).

    Two WARNING transitions must reach 2 - the ``+= 1`` -> ``= 1`` twin sticks at
    1 - and the CRITICAL counter must stay 0 (its ``elif`` arm is not taken).
    """
    await monitor._handle_pressure_level_change(WARNING, NORMAL, 90.0)
    await monitor._handle_pressure_level_change(NORMAL, WARNING, 10.0)
    await monitor._handle_pressure_level_change(WARNING, NORMAL, 91.0)

    metrics = monitor.get_memory_pressure_metrics()
    assert metrics["total_warning_events"] == 2, (
        f"warning counter did not accumulate (augassign twin): {metrics!r}"
    )
    assert metrics["total_critical_events"] == 0, f"critical counter moved: {metrics!r}"


async def test_critical_events_accumulate_across_transitions(monitor):
    """L1370 ``self._memory_pressure_critical_events += 1``: two CRITICAL
    transitions reach 2 (kills the ``= 1`` twin) and the WARNING counter
    accumulates to 1 across the same sequence (both arms, one run)."""
    await monitor._handle_pressure_level_change(CRITICAL, WARNING, 96.0)
    await monitor._handle_pressure_level_change(WARNING, CRITICAL, 90.0)
    await monitor._handle_pressure_level_change(CRITICAL, WARNING, 99.0)

    metrics = monitor.get_memory_pressure_metrics()
    assert metrics["total_critical_events"] == 2, (
        f"critical counter did not accumulate (augassign twin): {metrics!r}"
    )
    assert metrics["total_warning_events"] == 1, f"warning counter mutated: {metrics!r}"


async def test_normal_transition_touches_neither_counter(monitor):
    """A transition INTO NORMAL updates no counter and leaves both timestamps
    untouched - the shipped ``if/elif`` has no else arm (L1366-L1371)."""
    await monitor._handle_pressure_level_change(NORMAL, WARNING, 5.0)
    metrics = monitor.get_memory_pressure_metrics()
    assert metrics["total_warning_events"] == 0, f"warning counter moved on NORMAL: {metrics!r}"
    assert metrics["total_critical_events"] == 0, f"critical counter moved on NORMAL: {metrics!r}"
    assert metrics["last_warning_event_at"] is None, f"warning timestamp written: {metrics!r}"
    assert metrics["last_critical_event_at"] is None, f"critical timestamp written: {metrics!r}"


async def test_warning_transition_stores_a_utc_aware_event_timestamp(monitor):
    """L1363 ``now = datetime.now(UTC)`` -> L1368 ``_last_warning_event_at`` ->
    L1427-L1429 ``isoformat()`` through the shipped getter.

    The shipped value carries the UTC offset ("+00:00"); the ``now(None)`` mutant
    stores a NAIVE datetime whose ISO string has no offset.  The stored attribute's
    own ``utcoffset()`` is pinned too, and the CRITICAL timestamp must stay
    unwritten - so this leg cannot be satisfied by an incidental aware value.
    """
    with patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)):
        await monitor._handle_pressure_level_change(WARNING, NORMAL, 88.0)

    metrics = monitor.get_memory_pressure_metrics()
    stamp = metrics["last_warning_event_at"]
    assert stamp is not None, f"warning timestamp not stored: {metrics!r}"
    assert stamp.startswith("2026-03-04T05:06:07"), f"timestamp value mutated: {stamp!r}"
    assert stamp.endswith("+00:00"), (
        f"timestamp is naive - datetime.now(None) dropped the UTC flag: {stamp!r}"
    )
    assert datetime.fromisoformat(stamp) == FROZEN_NOW, f"timestamp round-trip broke: {stamp!r}"
    assert monitor._last_warning_event_at.utcoffset() == timedelta(0), (
        f"stored timestamp offset mutated: {monitor._last_warning_event_at!r}"
    )
    assert metrics["last_critical_event_at"] is None, (
        f"critical timestamp written on a WARNING transition: {metrics!r}"
    )


async def test_critical_transition_stores_a_utc_aware_event_timestamp(monitor):
    """The L1371 twin of the timestamp store: ``_last_critical_event_at`` is
    tz-aware (same ``now`` -> ``None`` kill) and the WARNING timestamp is
    untouched."""
    with patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)):
        await monitor._handle_pressure_level_change(CRITICAL, WARNING, 99.0)

    metrics = monitor.get_memory_pressure_metrics()
    stamp = metrics["last_critical_event_at"]
    assert stamp is not None, f"critical timestamp not stored: {metrics!r}"
    assert stamp.endswith("+00:00"), f"critical timestamp is naive: {stamp!r}"
    assert datetime.fromisoformat(stamp) == FROZEN_NOW, f"timestamp broke: {stamp!r}"
    assert monitor._last_critical_event_at.utcoffset() == timedelta(0), (
        f"stored critical offset mutated: {monitor._last_critical_event_at!r}"
    )
    assert metrics["last_warning_event_at"] is None, (
        f"warning timestamp written on a CRITICAL transition: {metrics!r}"
    )


async def test_metrics_report_the_shipped_thresholds_and_current_level(monitor):
    """The shipped getter's remaining fields (L1422-L1424): the level string and
    the two thresholds - pinned so the extra-value asserts above read the same
    constants the getter publishes."""
    metrics = monitor.get_memory_pressure_metrics()
    assert metrics["current_level"] == "normal", f"current_level mutated: {metrics!r}"
    assert metrics["warning_threshold"] == WARNING_THRESHOLD, f"warning_threshold: {metrics!r}"
    assert metrics["critical_threshold"] == CRITICAL_THRESHOLD, (
        f"critical_threshold mutated: {metrics!r}"
    )


# =============================================================================
# L1388-L1406: callback wiring + the failure log
# =============================================================================


async def test_callbacks_run_in_order_and_async_callbacks_are_awaited(monitor):
    """L1389-L1394: every registered callback is invoked once with
    ``(new_level, old_level)`` in registration order, and a coroutine result is
    awaited (L1393-L1394).

    This is the wiring the failure log sits inside, so the ERROR legs below are
    reached through the shipped loop rather than by accident.  A failing callback
    in the middle must not stop the later one - that is the shipped ``try`` arm.
    """
    monitor.register_memory_pressure_callback(ok_sync)
    monitor.register_memory_pressure_callback(ok_async)
    monitor.register_memory_pressure_callback(boom)
    monitor.register_memory_pressure_callback(ok_sync)

    await monitor._handle_pressure_level_change(WARNING, NORMAL, 90.0)

    assert ok_sync.calls == [(WARNING, NORMAL), (WARNING, NORMAL)], (
        f"sync callback calls mutated: {ok_sync.calls!r}"
    )
    assert ok_async.calls == [(WARNING, NORMAL)], (
        f"async callback was not awaited exactly once: {ok_async.calls!r}"
    )


async def test_failing_callback_logs_the_exact_error_with_exc_info(monitor, caplog):
    """L1396-L1406: a raising callback -> exactly ONE ERROR with the shipped
    message, the five-entry extra as record attributes, ``exc_info`` TRUTHINESS
    with its exception type, and the loop continuing to the next callback.

    audit correction #8: the ``exc_info`` assert is truthiness plus
    ``exc_info[0] is RuntimeError``, NEVER ``is not None`` - the shipped
    ``exc_info=True`` -> ``False`` mutant leaves ``exc_info`` the falsy ``False``
    and ``False is not None`` would accept it.
    """
    monitor.register_memory_pressure_callback(boom)
    monitor.register_memory_pressure_callback(ok_sync)
    win(caplog)
    await monitor._handle_pressure_level_change(WARNING, NORMAL, 90.0)

    change = only(caplog, logging.WARNING, CHANGE_MSG.format(old="normal", new="warning", pct=90.0))
    rec = only(caplog, logging.ERROR, CB_FAIL_MSG.format(name="boom"))
    pin_callback_extra(
        rec, name="boom", new="warning", old="normal", error=CB_FAULT, error_type="RuntimeError"
    )
    assert shape(caplog) == [(logging.WARNING, change.msg), (logging.ERROR, rec.msg)], (
        f"unexpected record set for a failing callback: {shape(caplog)!r}"
    )
    assert rec.exc_info, f"exc_info must be truthy (True -> False mutant): {rec.exc_info!r}"
    assert rec.exc_info[0] is RuntimeError, f"exc_info type mutated: {rec.exc_info!r}"
    assert rec.exc_info[1] is not None, f"exc_info lost the exception instance: {rec.exc_info!r}"
    assert ok_sync.calls == [(WARNING, NORMAL)], (
        f"the loop did not continue past the failing callback: {ok_sync.calls!r}"
    )


async def test_callback_failure_extra_payload_is_verbatim(monitor, caplog):
    """The failure record's ``extra`` DICT as captured by a handler, plus its
    ``exc_info`` truthiness - the payload-side twin of the attribute leg."""
    monitor.register_memory_pressure_callback(boom)
    win(caplog)
    with grab_logs() as grab:
        await monitor._handle_pressure_level_change(CRITICAL, WARNING, 96.5)

    # Shipped logs the change record FIRST and the callback failure SECOND, so the
    # failure payload is grab.payloads[1]; asserting the count pins the ordering.
    assert len(grab.payloads) == 2, f"expected change + failure payloads: {grab.payloads!r}"
    assert grab.payloads[0]["levelname"] == "WARNING", (
        f"change record level mutated: {grab.payloads[0].get('levelname')!r}"
    )
    payload = grab.payloads[1]
    assert payload["msg"] == CB_FAIL_MSG.format(name="boom"), (
        f"failure message mutated: {payload.get('msg')!r}"
    )
    assert payload["callback"] == "boom", f"extra mutated: {payload.get('callback')!r}"
    assert payload["new_level"] == "critical", f"extra mutated: {payload.get('new_level')!r}"
    assert payload["old_level"] == "warning", f"extra mutated: {payload.get('old_level')!r}"
    assert payload["error"] == CB_FAULT, f'extra["error"] mutated: {payload.get("error")!r}'
    assert payload["error_type"] == "RuntimeError", (
        f'extra["error_type"] mutated: {payload.get("error_type")!r}'
    )
    exc = payload["exc_info"]
    assert exc, f"exc_info must be truthy: {exc!r}"
    assert exc[0] is RuntimeError, f"exc_info type mutated: {exc!r}"


async def test_failing_callback_of_another_type_follows_the_injected_fault(monitor, caplog):
    """A different exception class through the same arm: ``error`` / ``error_type``
    / ``exc_info[0]`` all follow the injected fault, so those three legs cannot be
    satisfied by hard-coded strings (they kill ``str(e)`` -> ``str(None)`` and
    ``type(e)`` -> ``type(None)`` from the other side too)."""

    def bad_value(_new_level: object, _old_level: object) -> None:
        """Callback double raising ``ValueError("nope")`` (name == "bad_value")."""
        raise ValueError("nope")

    monitor.register_memory_pressure_callback(bad_value)
    win(caplog)
    await monitor._handle_pressure_level_change(NORMAL, CRITICAL, 3.0)

    change = only(caplog, logging.INFO, CHANGE_MSG.format(old="critical", new="normal", pct=3.0))
    rec = only(caplog, logging.ERROR, CB_FAIL_MSG.format(name="bad_value"))
    pin_callback_extra(
        rec, name="bad_value", new="normal", old="critical", error="nope", error_type="ValueError"
    )
    assert rec.exc_info and rec.exc_info[0] is ValueError, f"exc_info mutated: {rec.exc_info!r}"
    assert shape(caplog) == [(logging.INFO, change.msg), (logging.ERROR, rec.msg)], (
        f"unexpected record set for a failing callback: {shape(caplog)!r}"
    )


async def test_a_sync_callback_that_returns_a_value_is_not_awaited(monitor, caplog):
    """L1393 ``if asyncio.iscoroutine(result):`` - a callback returning a plain
    value is NOT awaited and NOTHING extra is logged: the change record is the
    only output.

    A mutant that swapped the guard for an unconditional ``await`` raises
    TypeError, which lands in the shipped ERROR arm - so the absence of an ERROR
    here is the pin, not a filler assert.
    """

    def returns_value(_new_level: object, _old_level: object) -> str:
        """Callback returning a non-coroutine value."""
        return "not-a-coroutine"

    monitor.register_memory_pressure_callback(returns_value)
    win(caplog)
    await monitor._handle_pressure_level_change(WARNING, NORMAL, 90.0)

    rec = only(caplog, logging.WARNING, CHANGE_MSG.format(old="normal", new="warning", pct=90.0))
    assert shape(caplog) == [(logging.WARNING, rec.msg)], (
        f"a good callback must not reach the ERROR arm: {shape(caplog)!r}"
    )


async def test_no_callbacks_means_only_the_change_record(monitor, caplog):
    """The empty-callback-list control: the shipped loop iterates zero times and
    the change log is the only output, at the routed level."""
    win(caplog)
    await monitor._handle_pressure_level_change(CRITICAL, WARNING, 99.9)
    rec = only(caplog, logging.WARNING, CHANGE_MSG.format(old="warning", new="critical", pct=99.9))
    assert shape(caplog) == [(logging.WARNING, rec.msg)], (
        f"empty callback list must log only the change: {shape(caplog)!r}"
    )
