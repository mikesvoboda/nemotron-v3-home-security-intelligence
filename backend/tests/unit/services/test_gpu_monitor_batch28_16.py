"""S3 batch-28 lane gm-16 - ``gpu_monitor`` group G23b kill battery (77 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json``
group "G23b _store_stats: extended stats.get kwargs + debug/error logs"
(77 KILLABLE / 0 EQUIVALENT), plus ``group_24.keys`` and ``survivors.json``.

Sibling file: ``test_gpu_monitor_batch28_15.py`` (G23a, same function).  Design
probe proving every candidate of groups 23+24 diverges under this two-environment
oracle: ``/tmp/wp-pw/gm/probe2324/oracle_probe.py`` (136/137 spliceable candidates
kill; the 137th, ``store_stats__mutmut_3`` of group 23, is the known-unparseable
key - manual proof ``/tmp/wp-pw/gm/probe2324/manual_mut3.py``).

Payload poison (manifest test_spec row (a) hardened for the twin sites): the
success payload carries, besides each shipped key, the UPPERCASE and
``XX...XX`` twins of every extended key with deliberately WRONG values, so a
key-string mutant inside ``stats.get("...")`` (gpu_monitor.py:1025-1045) can
never alias onto the shipped value: ``get("FAN_SPEED")`` returns the poison
-777.0 and ``get("XXfan_speedXX")`` returns -888.0 - neither equals the
sentinel the shipped lookup must return.

Test -> mutant-key map (all keys are ``store_stats__mutmut_*`` in
``group_24.keys``; cites are gpu_monitor.py)
================================================================================
- ``mutmut_72`` - ``mutmut_128`` (57 keys: 19 metrics x {get-arg->None,
  wrapXX, upper} on the 19 ``stats.get(...)`` kwargs at L1025-L1045)
  -> ``test_full_payload_row_matches_the_shipped_lookup_oracle``
  (row attribute != sentinel: None for the arg->None rows, poison value for
  the renamed-key rows; the gpu_name twin occ0 keys ``mut_138``/``mut_139`` hit
  the L1017 subscript site here)
- ``mutmut_130``  L1049 ``logger.debug(f"Stored GPU stats: {gpu_stats}")`` ->
  ``logger.debug(None)``
  -> ``test_success_debug_line_names_the_constructed_row`` (SOLE route: msg is
  None -> the startswith assert AttributeErrors)
- ``mutmut_129``  L1047 ``session.add(gpu_stats)`` -> ``session.add(None)``
  -> ``test_commit_failure_stores_then_logs_the_shipped_error_context``
  (audit correction #6: the row is observed via the SYNCHRONOUS
  ``session.add.call_args[0][0]`` - never ``await_args`` - so the
  identity/type assert is what fails for the mutant)
- ``mutmut_132`` drop of the whole ``extra={...}`` (call_arg -> None) and
  ``mutmut_134`` drop of the extra + closing paren
  -> ``test_commit_failure_stores_then_logs_the_shipped_error_context``
  (every ``record.<attr>`` assert AttributeErrors when extra is absent)
- ``mutmut_135``  L1053 msg wrapXX -> same test (msg exact equality)
- ``mutmut_138``/``mut_139``/``mut_141``/``mut_142`` (occurrence twins on the
  token ``"gpu_name"``: occ0 = the L1017 ``stats["gpu_name"]`` subscript,
  occ1 = the L1055 error-extra key)
  -> occ0 killed by the full-payload oracle test (row.gpu_name None),
     occ1 by the error-context test (``record.gpu_name`` AttributeError)
- ``mutmut_140``  L1055 ``stats.get("gpu_name")`` -> ``stats.get(None)``
  -> error-context test (record.gpu_name None != payload value)
- ``mutmut_143``/``mut_144`` (extra key ``"operation"`` x2) and
  ``mutmut_145``/``mut_146`` (VALUE ``"store_stats"`` x2),
  ``mutmut_147``/``mut_148`` (key ``"error"`` x2), ``mutmut_149``
  (``str(e)`` -> ``str(None)``), ``mutmut_150``/``mut_151`` (key
  ``"error_type"`` x2), ``mutmut_152`` (``type(e)`` -> ``type(None)``)
  -> error-context test (record.operation / record.error == "db down" /
  record.error_type == "RuntimeError" / renames AttributeError)

Every assert targets shipped behavior; production never bends.  The real
``GPUStats`` model is used (the stored attributes ARE the observable); the
session is a seam, no DB I/O happens.
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

# The 19 extended ``stats.get`` kwargs of the GPUStats(...) call, shipped order
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

EXT_VALUES = {name: float(200 + 11 * i) for i, name in enumerate(EXT_FIELDS)}

CORE_VALUES = {
    "gpu_name": "RTX-Sentinel",
    "gpu_utilization": 30.9,
    "memory_used": 4321,
    "memory_total": 49152,
    "temperature": 61.5,
    "power_usage": 102.25,
}

# Poison twins: a key-string mutation inside stats.get(...) must return one of
# these WRONG values instead of silently matching a missing-key None - the
# shipped lookup still returns the sentinel because it asks for the shipped key.
POISON_UPPER = {name.upper(): -777.0 for name in EXT_FIELDS if name != name.upper()}
POISON_WRAP = {f"XX{name}XX": -888.0 for name in EXT_FIELDS}


def make_full_stats() -> dict:
    """Full success payload: shipped sentinels + the poisoned twins."""
    stats = {"recorded_at": datetime.now(UTC), **CORE_VALUES, **EXT_VALUES}
    stats.update(POISON_UPPER)
    stats.update(POISON_WRAP)
    return stats


def make_minimal_stats() -> dict:
    """Error-path payload: the six required keys only (extended -> None)."""
    return {"recorded_at": datetime.now(UTC), **CORE_VALUES}


def make_monitor() -> M.GPUMonitor:
    """GPUMonitor in mock mode: pynvml import forced to fail, no nvidia-smi.

    ``_store_stats`` never touches the GPU; construction stays hermetic
    (gpu_monitor.py:226 ImportError branch, gpu_monitor.py:264 not-found DEBUG).
    """
    with (
        patch.dict(sys.modules, {"pynvml": None}),
        patch.object(M.shutil, "which", autospec=True, return_value=None),
    ):
        return M.GPUMonitor(poll_interval=5.0, history_minutes=1, http_timeout=2.5)


def make_session(commit_side_effect=None):
    """Seam for ``backend.core.database.get_session`` (database.py:642).

    ``async with get_session() as session`` (gpu_monitor.py:1011).  Shipped
    calls ``session.add`` synchronously (gpu_monitor.py:1047) and awaits
    ``session.commit()`` (gpu_monitor.py:1048).
    """
    session = MagicMock(name="session")
    session.add = MagicMock(name="session-add")
    session.commit = AsyncMock(name="session-commit", side_effect=commit_side_effect)
    ctx = MagicMock(name="session-ctx")
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(name="get-session-factory", return_value=ctx)
    return session, factory


async def run_store(monitor, stats, session_factory, fps_value=2.5):
    """Drive one ``_store_stats`` call with the two function-local seams."""
    fps = AsyncMock(name="calc-inference-fps", return_value=fps_value)
    with (
        patch.object(M, "get_session", new=session_factory),
        patch.object(monitor, "_calculate_inference_fps", new=fps),
    ):
        await monitor._store_stats(stats)
    return fps


async def test_full_payload_row_matches_the_shipped_lookup_oracle():
    """Full poisoned payload: 27 shipped row attributes, add + commit wiring.

    Kills the 57 ``stats.get`` rows of L1025-L1045 (arg->None yields None,
    key-renames yield the poison values - never the sentinel) and the occ0
    site of the four ``"gpu_name"`` twin keys (L1017 subscript -> None).  The
    call contract (row identity through the synchronous add, one awaited
    commit, fps awaited with the session) is asserted on the same run so no
    sibling can fake a kill.
    """
    monitor = make_monitor()
    stats = make_full_stats()
    session, factory = make_session()
    fps = await run_store(monitor, stats, factory)

    assert session.add.call_count == 1, "shipped adds exactly one row"
    row = session.add.call_args[0][0]
    assert type(row) is GPUStats, "gpu_monitor.py:1015 constructs the ORM row"
    assert row.recorded_at is stats["recorded_at"], "gpu_monitor.py:1016"
    assert row.gpu_name == CORE_VALUES["gpu_name"], "gpu_monitor.py:1017"
    assert row.gpu_utilization == CORE_VALUES["gpu_utilization"], "gpu_monitor.py:1018"
    assert row.memory_used == CORE_VALUES["memory_used"], "gpu_monitor.py:1019"
    assert row.memory_total == CORE_VALUES["memory_total"], "gpu_monitor.py:1020"
    assert row.temperature == CORE_VALUES["temperature"], "gpu_monitor.py:1021"
    assert row.power_usage == CORE_VALUES["power_usage"], "gpu_monitor.py:1022"
    assert row.inference_fps == 2.5, "gpu_monitor.py:1023"
    for name in EXT_FIELDS:
        assert getattr(row, name) == EXT_VALUES[name], (
            f"gpu_monitor.py:1025-1045 shipped key {name}"
        )
    assert fps.await_args[0] == (session,), "gpu_monitor.py:1014 passes THE SESSION"
    assert session.commit.await_count == 1, "gpu_monitor.py:1048 commit awaited once"


async def test_success_debug_line_names_the_constructed_row(caplog):
    """L1049 DEBUG stream window: exactly one DEBUG naming the GPUStats row.

    Kills ``mutmut_130`` (``logger.debug(None)`` -> msg None) and the
    window-equality leg catches any splice that diverts the success path into
    the except arm (the window would then hold an ERROR record).
    """
    monitor = make_monitor()
    stats = make_full_stats()
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
    assert session.commit.await_count == 1, "the DEBUG follows the awaited commit"


async def test_commit_failure_stores_then_logs_the_shipped_error_context(caplog):
    """Commit raises: row still added, no escape, one ERROR with shipped extras.

    Kills the L1047 add-arg row (``mut_129``: call_args[0][0] is None, not the
    GPUStats row), the extra-dropping rows (``mut_132``/``mut_134``: every
    ``record.<attr>`` assert AttributeErrors), the msg wrap (``mut_135``) and
    the whole error-extra field family (``mut_138``/``mut_139``/``mut_141``/
    ``mut_142`` occ1, ``mut_140``, ``mut_143``-``mut_152``).  Also the red
    side of the manual ``mutmut_3`` differential (gpu_stats=None -> add(None)
    fails the row-identity assert): see
    ``/tmp/wp-pw/gm/probe2324/manual_mut3.py``.
    """
    monitor = make_monitor()
    stats = make_minimal_stats()
    session, factory = make_session(commit_side_effect=RuntimeError("db down"))
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    caplog.clear()
    fps = await run_store(monitor, stats, factory)

    assert fps.await_count == 1, "gpu_monitor.py:1014 runs before the failing commit"
    assert session.add.call_count == 1, "gpu_monitor.py:1047 adds before committing"
    row = session.add.call_args[0][0]
    assert type(row) is GPUStats, "shipped adds the constructed row (audit fix #6)"
    assert row.gpu_name == CORE_VALUES["gpu_name"], "gpu_monitor.py:1017"
    assert row.inference_fps == 2.5, "gpu_monitor.py:1023"
    assert session.commit.await_count == 1, "the commit was attempted"

    window = [r for r in caplog.records if r.name == LOGGER]
    assert len(window) == 1, "shipped logs exactly one line on the failure path"
    record = window[0]
    assert record.levelno == logging.ERROR, "gpu_monitor.py:1052 logs at ERROR"
    assert record.msg == "Failed to store GPU stats in database", "gpu_monitor.py:1053"
    assert record.gpu_name == stats["gpu_name"], "gpu_monitor.py:1055"
    assert record.operation == "store_stats", "gpu_monitor.py:1056"
    assert record.error == "db down", "gpu_monitor.py:1057 str(e)"
    assert record.error_type == "RuntimeError", "gpu_monitor.py:1058 type(e).__name__"
