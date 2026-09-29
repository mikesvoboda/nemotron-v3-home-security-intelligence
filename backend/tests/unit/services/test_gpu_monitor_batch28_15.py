"""S3 batch-28 lane gm-15 - ``gpu_monitor`` group G23a kill battery (56 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json``
group "G23a _store_stats: GPUStats kwarg wiring (27) + add/commit" (56 KILLABLE /
0 EQUIVALENT), plus ``group_23.keys`` and ``survivors.json`` for the exact
per-key diffs.

Battery shape (the manifest test_spec, ADMITTED): ``GPUMonitor._store_stats``
(gpu_monitor.py:1004-1060) is driven with a stub ``get_session`` async-context
factory and a full 25-key payload carrying a DISTINCT sentinel per field.  The
row captured from ``session.add.call_args[0][0]`` is asserted attribute-by-
attribute against the payload, the call contract (fps-with-session, add, commit)
is asserted, and the log stream is asserted by full window equality.  Every
survivable splice inside the function diverges from that oracle, which is the
only shape that satisfies occurrence-twin soundness for the bare-token twins in
this band (``/tmp/wp-pw/gm/probe2324/oracle_probe.py``: 136/137 harness-spliceable
candidates of groups 23+4 diverge under the two-environment oracle; the 137th is
``mutmut_3``, the known UNPARSEABLE key, proven by the manual probe recorded in
``test_gpu_monitor_batch28_16.py``).

Test -> mutant-key map (all keys are ``store_stats__mutmut_*`` in
``group_23.keys``; source line cites are gpu_monitor.py)
================================================================================
- ``mutmut_2``   L1014 ``self._calculate_inference_fps(session)`` -> ``(None)``
  -> ``test_core_row_fields_come_from_the_shipped_subscripts``
  (AsyncMock ignores args - the await-args identity assert is the ONLY observable)
- ``mutmut_4`` - ``mutmut_11``  L1016-L1023 call_arg -> None (recorded_at,
  gpu_name, gpu_utilization, memory_used, memory_total, temperature,
  power_usage, inference_fps)
  -> ``test_core_row_fields_come_from_the_shipped_subscripts``
- ``mutmut_12`` - ``mutmut_30``  L1025-L1045 call_arg -> None for the 19
  ``stats.get(...)`` extended kwargs
  -> ``test_extended_row_fields_come_from_the_shipped_get_keys``
- ``mutmut_31`` - ``mutmut_57``  drop_arg (each kwarg line; mut_38/42/48 also
  drop the following ``# ...`` comment line, killed by the same attribute
  equality - and secondarily by the window-equality DEBUG test)
  -> core kwargs -> ``test_core_row_fields_come_from_the_shipped_subscripts``;
  extended kwargs -> ``test_extended_row_fields_come_from_the_shipped_get_keys``
  and ``test_minimal_payload_keeps_the_row_attributes_present_as_none``
- ``mutmut_3``   L1015 ``gpu_stats = GPUStats(...)`` -> ``gpu_stats = None``
  UNPARSEABLE by the replay splicer (multi-line before-text; the harness splice
  is syntactically invalid).  MANUAL proof per the
  ``/tmp/wp-pw/pipeline_workers/audit/mutate.py`` pattern:
  ``/tmp/wp-pw/gm/probe2324/manual_mut3.py`` copies the shipped source to a
  scratch module, applies the diff as Python would (assert-before-replace),
  compiles/imports it and drives the shipped-vs-mutant differential.  The
  shipped side of that differential is exactly
  ``test_the_constructed_row_is_passed_to_the_session_call_contract`` (in
  ``test_gpu_monitor_batch28_16.py``), whose green side the manual probe shows
  is uncontaminated by every other candidate (probe env-B sweep: 136/136
  spliceable candidates keep it green, all 136 still fail the file elsewhere).

Every test asserts SHIPPED behavior only; production never bends.  ``GPUStats``
is the REAL ORM model (backend/models/gpu_stats.py) because the stored attribute
values ARE the shipped observable here - no DB connection is involved (the
session is a seam; nothing is flushed).
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.gpu_stats import GPUStats
from backend.services import gpu_monitor as M

pytestmark = [pytest.mark.unit]

LOGGER = "backend.services.gpu_monitor"

# The 19 extended kwargs of the GPUStats(...) call, in shipped order
# (gpu_monitor.py:1025-1045).
EXT_FIELDS = [
    "fan_speed",
    "sm_clock",
    "memory_bandwidth_utilization",
    "pstate",
    "throttle_reasons",
    "power_limit",
    "sm_clock_max",
    "compute_processes_count",
    "pcie_replay_counter",
    "temp_slowdown_threshold",
    "memory_clock",
    "memory_clock_max",
    "pcie_link_gen",
    "pcie_link_width",
    "pcie_tx_throughput",
    "pcie_rx_throughput",
    "encoder_utilization",
    "decoder_utilization",
    "bar1_used",
]

# Distinct sentinel per extended field; every value differs from every core
# value below, so a renamed/None'd kwarg can never alias onto a sibling.
EXT_VALUES = {name: float(100 + 7 * i) for i, name in enumerate(EXT_FIELDS)}

# Core payload values, one distinct sentinel per shipped subscript
# (gpu_monitor.py:1016-1022).
CORE_VALUES = {
    "gpu_name": "RTX-Sentinel",
    "gpu_utilization": 30.4,
    "memory_used": 1234,
    "memory_total": 24576,
    "temperature": 45.0,
    "power_usage": 88.5,
}


def make_stats(*, with_extended: bool = True) -> dict:
    """Payload with a fresh tz-aware recorded_at and distinct field values."""
    stats = {"recorded_at": datetime.now(UTC), **CORE_VALUES}
    if with_extended:
        stats.update(EXT_VALUES)
    return stats


def make_monitor() -> M.GPUMonitor:
    """GPUMonitor in mock mode: pynvml import forced to fail, no nvidia-smi.

    ``_store_stats`` never touches the GPU, but construction must be hermetic
    (gpu_monitor.py:226 ImportError branch + gpu_monitor.py:264 DEBUG branch).
    """
    with (
        patch.dict(sys.modules, {"pynvml": None}),
        patch.object(M.shutil, "which", autospec=True, return_value=None),
    ):
        return M.GPUMonitor(poll_interval=5.0, history_minutes=1, http_timeout=2.5)


def make_session(commit_side_effect=None):
    """Seam for ``backend.core.database.get_session`` (database.py:642).

    ``_store_stats`` (gpu_monitor.py:1011) uses it as ``async with ... as
    session``: the factory is called with no args and returns an async
    context manager.  Shipped calls ``session.add(row)`` SYNCHRONOUSLY
    (gpu_monitor.py:1047) and awaits ``session.commit()``
    (gpu_monitor.py:1048) - hence add is a MagicMock and commit an AsyncMock.
    """
    session = MagicMock(name="session")
    session.add = MagicMock(name="session-add")
    session.commit = AsyncMock(name="session-commit", side_effect=commit_side_effect)
    ctx = MagicMock(name="session-ctx")
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(name="get-session-factory", return_value=ctx)
    return session, factory


def stored_row(session: MagicMock) -> GPUStats:
    """The row handed to the synchronous ``session.add`` (gpu_monitor.py:1047).

    Audit correction #6: add() is NOT awaited on a real AsyncSession, so the
    shipped call is observed via ``call_args`` - never via ``await_args``.
    """
    assert session.add.call_count == 1, "shipped code adds exactly one row"
    return session.add.call_args[0][0]


async def run_store(monitor, stats, session_factory, fps_value=3.75):
    """Drive one ``_store_stats`` call with the two function-local seams."""
    fps = AsyncMock(name="calc-inference-fps", return_value=fps_value)
    with (
        patch.object(M, "get_session", new=session_factory),
        patch.object(monitor, "_calculate_inference_fps", new=fps),
    ):
        await monitor._store_stats(stats)
    return fps


async def test_core_row_fields_come_from_the_shipped_subscripts():
    """Core kwargs + call contract: kills mutmut_2 and mut_4..mut_11 (+31..38).

    Pins (gpu_monitor.py:1014 inference_fps await; :1016-:1023 the seven
    ``stats[...]`` subscripts; :1047 add; :1048 commit):
    the row is a REAL GPUStats whose seven core attributes equal the payload
    sentinels, ``recorded_at`` is the SAME object, ``inference_fps`` is the
    calculated value, and the fps coroutine was awaited with the session.
    """
    monitor = make_monitor()
    stats = make_stats()
    session, factory = make_session()
    fps = await run_store(monitor, stats, factory)

    assert factory.call_count == 1, "get_session() is called with no args"
    assert factory.call_args == ((), {}), "shipped opens the session with no arguments"
    assert session.commit.await_count == 1, "gpu_monitor.py:1048 awaits commit once"
    row = stored_row(session)
    assert type(row) is GPUStats, "the stored object is the shipped ORM row"
    assert row.recorded_at is stats["recorded_at"], "gpu_monitor.py:1016 passes it through"
    assert row.gpu_name == CORE_VALUES["gpu_name"], "gpu_monitor.py:1017"
    assert row.gpu_utilization == CORE_VALUES["gpu_utilization"], "gpu_monitor.py:1018"
    assert row.memory_used == CORE_VALUES["memory_used"], "gpu_monitor.py:1019"
    assert row.memory_total == CORE_VALUES["memory_total"], "gpu_monitor.py:1020"
    assert row.temperature == CORE_VALUES["temperature"], "gpu_monitor.py:1021"
    assert row.power_usage == CORE_VALUES["power_usage"], "gpu_monitor.py:1022"
    assert row.inference_fps == 3.75, "gpu_monitor.py:1023 uses the awaited value"
    assert fps.await_count == 1, "gpu_monitor.py:1014 calculates fps exactly once"
    assert fps.await_args[0] == (session,), "gpu_monitor.py:1014 passes THE SESSION"


async def test_extended_row_fields_come_from_the_shipped_get_keys():
    """19 extended kwargs: kills mutmut_12..mut_30 and drops mut_39..mut_57.

    Pins gpu_monitor.py:1025-:1045 - each row attribute equals the payload
    value stored under the shipped dict key (a renamed/None'd ``stats.get``
    key yields None here; a dropped kwarg leaves the attribute None).
    """
    monitor = make_monitor()
    stats = make_stats()
    session, factory = make_session()
    await run_store(monitor, stats, factory)

    row = stored_row(session)
    for name in EXT_FIELDS:
        assert getattr(row, name) == EXT_VALUES[name], f"gpu_monitor.py:1025-1045 {name}"


async def test_minimal_payload_keeps_the_row_attributes_present_as_none(caplog):
    """Payload without the extended keys: attrs present, values None.

    Second kill vector for the drop_arg family (mut_31..mut_57): a dropped
    kwarg would REMOVE the mapped attribute entirely (hasattr False), while
    shipped always constructs with all 27 kwargs.  Core values still flow
    (gpu_monitor.py:1016-:1023) and commit still runs (:1048).
    """
    monitor = make_monitor()
    stats = make_stats(with_extended=False)
    session, factory = make_session()
    await run_store(monitor, stats, factory)

    assert session.commit.await_count == 1, "shipped still commits the minimal row"
    row = stored_row(session)
    assert type(row) is GPUStats, "gpu_monitor.py:1015 constructs the row"
    for name in EXT_FIELDS:
        assert hasattr(row, name), f"shipped always passes the {name} kwarg"
        assert getattr(row, name) is None, f"missing key -> get() -> None ({name})"
    assert row.gpu_name == CORE_VALUES["gpu_name"], "gpu_monitor.py:1017"
    assert row.inference_fps == 3.75, "gpu_monitor.py:1023"


async def test_success_log_window_is_exactly_the_stored_debug(caplog):
    """Window equality after the commit: exactly one DEBUG line, no ERROR.

    Pins gpu_monitor.py:1049 ``logger.debug(f"Stored GPU stats: {gpu_stats}")``
    and the fact that the success path logs NOTHING else: a mutant that
    diverts into the except arm (e.g. mut_38/42/48 dropping a comment and a
    kwarg is caught above, but any flow-diverting splice shows here) breaks
    the window equality.
    """
    monitor = make_monitor()
    stats = make_stats()
    session, factory = make_session()
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    caplog.clear()
    await run_store(monitor, stats, factory)

    window = [r for r in caplog.records if r.name == LOGGER]
    assert len(window) == 1, "shipped logs exactly one line on the success path"
    record = window[0]
    assert record.levelno == logging.DEBUG, "gpu_monitor.py:1049 is a DEBUG line"
    assert record.msg.startswith("Stored GPU stats: "), "gpu_monitor.py:1049 f-string"
    assert "GPUStats" in record.msg, "the interpolated row repr (models/gpu_stats.py:97)"


async def test_commit_failure_is_swallowed_into_the_shipped_error_record(caplog):
    """Commit RuntimeError: no escape + one ERROR record with the shipped extras.

    Pins gpu_monitor.py:1050-:1060: ``_store_stats`` returns None (exception
    swallowed), the single record is ERROR with msg exactly "Failed to store
    GPU stats in database" (:1053) and extra attrs gpu_name/operation/error/
    error_type (:1055-:1058).  Companion context for the group-23 rows (the
    add() already happened at :1047 before the failing commit).
    """
    monitor = make_monitor()
    stats = make_stats()
    session, factory = make_session(commit_side_effect=RuntimeError("db down"))
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    caplog.clear()
    fps = await run_store(monitor, stats, factory)

    assert fps.await_count == 1, "fps was calculated before the failing commit"
    window = [r for r in caplog.records if r.name == LOGGER]
    assert len(window) == 1, "shipped logs exactly one line on the failure path"
    record = window[0]
    assert record.levelno == logging.ERROR, "gpu_monitor.py:1052 logs at ERROR"
    assert record.msg == "Failed to store GPU stats in database", "gpu_monitor.py:1053"
    assert record.gpu_name == CORE_VALUES["gpu_name"], "gpu_monitor.py:1055"
    assert record.operation == "store_stats", "gpu_monitor.py:1056"
    assert record.error == "db down", "gpu_monitor.py:1057 str(e)"
    assert record.error_type == "RuntimeError", "gpu_monitor.py:1058 type(e).__name__"
