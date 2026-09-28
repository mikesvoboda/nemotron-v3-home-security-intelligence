"""S3 batch-28 lane gm06 - ``gpu_monitor`` group G07a kill battery (31 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda -
byte-identical to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/gpu_monitor/manifest.json`` group ``G07a`` (31 KILLABLE / 0
EQUIVALENT), plus ``group_11.keys`` and ``survivors.json`` for the exact per-key
diffs.  Splice report ``splice-group_11.json``: status ``{'clean': 28, 'twin': 3}``
- the three twins are the ``contextlib.suppress(pynvml.NVMLError)`` ->
``suppress(None)`` rows (keys 51/56/64), which share SEVEN occurrence sites
inside ``_get_gpu_stats_real`` (L571/L579/L586/L593/L598/L603/L608), so every
site must redden: the per-field NVML-failure battery below is parametrized over
ALL SEVEN blocks for exactly that reason.  No key of this group is
``unparseable`` - nothing here needed a manual mutate.py-style probe.

Function under test: ``GPUMonitor._get_gpu_stats_real`` (L551-L658).

Test -> mutant-key map
======================
Every key below is in ``group_11.keys`` (all carry the
``xǁGPUMonitorǁ_get_gpu_stats_real__mutmut_`` prefix, abbreviated to ``N``).

- ``_mutmut_5``   L561 ``raise RuntimeError("GPU not available")`` ->
  ``RuntimeError("XXGPU not availableXX")``
  -> ``test_gpu_absent_or_handle_absent_raises_the_exact_guard_message``
     (all 3 params - full ``str(exc) ==`` equality, so a wrap is a miss)
- ``_mutmut_8``   L566 ``handle = self._gpu_handle`` -> ``handle = None``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
     (SOLE route: a MagicMock answers a ``None`` handle with the same values, so
     no return-value leg can see the drop)
- ``_mutmut_10``  L570 ``memory_bandwidth_utilization: float | None = None`` ->
  ``= ""``            -> ``test_single_nvml_failure_leaves_that_field_none``
     (param ``nvmlDeviceGetUtilizationRates`` - the init survives only when the
     block is skipped, which is what the injection does)
- ``_mutmut_13``  L572 ``nvmlDeviceGetUtilizationRates(handle)`` -> ``(None)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_16``  L574 ``memory_bandwidth_utilization = float(utilization.memory)``
  -> ``= None``       -> ``test_success_returns_the_shipped_value_for_every_field``
- ``_mutmut_17``  L574 ``float(utilization.memory)`` -> ``float(None)``
  -> ``test_success_returns_the_shipped_value_for_every_field``
     (``float(None)`` is a TypeError, ``contextlib.suppress(NVMLError)`` lets it
     out to L646, which logs and re-raises - so the success leg raises)
- ``_mutmut_22``  L580 ``nvmlDeviceGetMemoryInfo(handle)`` -> ``(None)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_39``  L588 ``nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)``
  first arg -> ``None`` -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_40``  L588 second arg -> ``None``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_41``  L588 drop_arg -> ``(NVML_TEMPERATURE_GPU)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_42``  L588 drop_arg -> ``(handle, )``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_48``  L594 ``nvmlDeviceGetPowerUsage(handle)`` -> ``(None)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_50``  L597 ``fan_speed: int | None = None`` -> ``= ""``
  -> ``test_single_nvml_failure_leaves_that_field_none`` (param fan)
- ``_mutmut_51``  L598 ``contextlib.suppress(pynvml.NVMLError)`` -> ``suppress(None)``
  (TWIN of 7 sites) -> ``test_single_nvml_failure_leaves_that_field_none``,
  which covers all seven blocks; ``suppress(None)`` only diverges from shipped
  when the block RAISES (``issubclass(E, (None,))`` is itself a TypeError that
  escapes to the L646 handler), so the raising leg is the only observable
- ``_mutmut_52``  L599 ``fan_speed = int(nvmlDeviceGetFanSpeed(handle))`` -> ``None``
  -> ``test_success_returns_the_shipped_value_for_every_field``
- ``_mutmut_53``  L599 ``int(nvmlDeviceGetFanSpeed(handle))`` -> ``int(None)``
  -> ``test_success_returns_the_shipped_value_for_every_field`` (TypeError path)
- ``_mutmut_54``  L599 ``nvmlDeviceGetFanSpeed(handle)`` -> ``(None)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_55``  L602 ``sm_clock: int | None = None`` -> ``= ""``
  -> ``test_single_nvml_failure_leaves_that_field_none`` (param sm_clock)
- ``_mutmut_56``  L603 ``suppress(pynvml.NVMLError)`` -> ``suppress(None)`` (TWIN)
  -> ``test_single_nvml_failure_leaves_that_field_none``
- ``_mutmut_57``  L604 ``sm_clock = int(...)`` -> ``None``
  -> ``test_success_returns_the_shipped_value_for_every_field``
- ``_mutmut_58``  L604 ``int(nvmlDeviceGetClockInfo(handle, NVML_CLOCK_SM))`` ->
  ``int(None)`` -> ``test_success_returns_the_shipped_value_for_every_field``
- ``_mutmut_59``  L604 ``nvmlDeviceGetClockInfo(None, NVML_CLOCK_SM)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_60``  L604 ``nvmlDeviceGetClockInfo(handle, None)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_61``  L604 drop_arg -> ``(NVML_CLOCK_SM)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_62``  L604 drop_arg -> ``(handle, )``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_63``  L607 ``pstate: int | None = None`` -> ``= ""``
  -> ``test_single_nvml_failure_leaves_that_field_none`` (param pstate)
- ``_mutmut_64``  L608 ``suppress(pynvml.NVMLError)`` -> ``suppress(None)`` (TWIN)
  -> ``test_single_nvml_failure_leaves_that_field_none``
- ``_mutmut_65``  L609 ``pstate = int(nvmlDeviceGetPerformanceState(handle))`` ->
  ``None`` -> ``test_success_returns_the_shipped_value_for_every_field``
- ``_mutmut_66``  L609 ``int(nvmlDeviceGetPerformanceState(handle))`` -> ``int(None)``
  -> ``test_success_returns_the_shipped_value_for_every_field`` (TypeError path)
- ``_mutmut_67``  L609 ``nvmlDeviceGetPerformanceState(None)``
  -> ``test_every_nvml_read_is_called_with_the_gpu_handle_and_constants``
- ``_mutmut_83``  L621 ``datetime.now(UTC)`` -> ``datetime.now(None)``
  -> ``test_stats_recorded_at_carries_the_utc_timezone`` (naive datetime ->
  ``tzinfo is None``)

Control legs that kill nothing of their own:
``test_every_nvml_read_happens_exactly_once_per_metric`` (call-count contract the
arg rows leave intact), ``test_all_nvml_failures_degrade_every_field_to_none``
and ``test_nvml_failures_are_swallowed_without_a_single_log_record`` (the silent
partial-failure contract of ``contextlib.suppress``, and the leg that proves the
init-to-"" rows cannot be satisfied by a fall-through).

Shipped behaviour only - nothing here invents a contract.  Every pinned value is
the arithmetic result of a SHIPPED line (cited above each pin) applied to a value
THIS file injects; the GPU handle, the two NVML constants and the ``NVMLError``
class are all injected by the ``fake_nvml`` fixture, so nothing depends on real
GPU hardware, on the wall clock beyond "is it tz-aware", or on a real pynvml.

Discipline
----------
* ``pynvml`` is faked wholesale through ``sys.modules`` for the duration of one
  test (the ``test_gpu_monitor.py`` ``mock_pynvml`` idiom) and restored after; no
  import-time global spy exists in this file.
* ``_get_extended_metrics`` is stubbed with ``patch.object(..., autospec=True)``
  (WP4.2 fast path) so the extended block - group G04a/G04b/G07b's territory -
  stays out of this battery's observables.
* Log assertions open a capture window per ``win()`` (``set_level`` + ``clear()``)
  and read the RAW ``record.msg``.
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted; nothing here sleeps, so every test is synchronous.
"""

from __future__ import annotations

import logging
import sys
import types
from datetime import UTC
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.services import gpu_monitor as M
from backend.services.gpu_monitor import GPUMonitor

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L561: raise RuntimeError("GPU not available")
GUARD_MSG = "GPU not available"
# L649: logger.error("Error reading GPU stats", extra={...})
READ_ERROR_MSG = "Error reading GPU stats"


# Injected pynvml surface (fixture-owned sentinels, never a real GPU).
class FakeNVMLError(Exception):
    """Stands in for ``pynvml.NVMLError`` (the only exception the shipped
    ``contextlib.suppress`` blocks swallow)."""


GPU_NAME = "Fake RTX 6000 (battery-injected)"
HANDLE = object()  # the truthy, identity-comparable GPU handle
TEMP_CONST = "NVML_TEMPERATURE_GPU"  # L588 second positional argument
SM_CONST = "NVML_CLOCK_SM"  # L604 second positional argument

# Values the fake NVML layer reports, and what the shipped lines compute from them.
GPU_UTIL_RAW = 31.4  # L573 float(utilization.gpu) -> 31.4
MEMBW_RAW = 12.5  # L574 float(utilization.memory) -> 12.5
USED_BYTES = 3 * 1024**3 + 7  # L581 int(used / (1024 * 1024)) -> 3072
TOTAL_BYTES = 24 * 1024**3 + 512  # L582 int(total / (1024 * 1024)) -> 24576
TEMP_RAW = 41  # L587 float(nvmlDeviceGetTemperature(...)) -> 41.0
POWER_RAW = 12_500_000  # L594 float(power_usage / 1000.0) -> 12500.0
FAN_RAW = 42.4  # L599 int(nvmlDeviceGetFanSpeed(...)) -> 42
SM_CLOCK_RAW = 1500.6  # L604 int(nvmlDeviceGetClockInfo(...)) -> 1500
PSTATE_RAW = 8  # L609 int(nvmlDeviceGetPerformanceState(...)) -> 8

# The nine locally-initialised numeric fields (L569-L609), keyed by the shipped
# return-dict names (L616-L626).
FIELDS = (
    "gpu_utilization",
    "memory_bandwidth_utilization",
    "memory_used",
    "memory_total",
    "temperature",
    "power_usage",
    "fan_speed",
    "sm_clock",
    "pstate",
)


# Full-success expectation for those nine fields, computed by hand from the
# shipped arithmetic above (each line cited inline in ``success_values``).
def success_values() -> dict[str, Any]:
    return {
        "gpu_utilization": 31.4,  # L573
        "memory_bandwidth_utilization": 12.5,  # L574
        "memory_used": 3072,  # L581
        "memory_total": 24576,  # L582
        "temperature": 41.0,  # L587
        "power_usage": 12500.0,  # L594
        "fan_speed": 42,  # L599
        "sm_clock": 1500,  # L604
        "pstate": 8,  # L609
    }


# Which of the nine fields the shipped ``suppress`` block leaves at its L569-L607
# init (None) when that one NVML call fails.  Everything else stays populated.
# This pairing is what kills the ``init -> ""`` rows (10/50/55/63): under those
# mutants the skipped block leaves "" behind, not None.
FAIL_TO_NONE = {
    "nvmlDeviceGetUtilizationRates": ("gpu_utilization", "memory_bandwidth_utilization"),
    "nvmlDeviceGetMemoryInfo": ("memory_used", "memory_total"),
    "nvmlDeviceGetTemperature": ("temperature",),
    "nvmlDeviceGetPowerUsage": ("power_usage",),
    "nvmlDeviceGetFanSpeed": ("fan_speed",),
    "nvmlDeviceGetClockInfo": ("sm_clock",),
    "nvmlDeviceGetPerformanceState": ("pstate",),
}


# =============================================================================
# Observation helpers (batch27_01 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load-bearing.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def msgs(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Raw ``record.msg`` of every record captured for this module's logger."""
    return [r.msg for r in caplog.records if r.name == LOG_NAME]


# =============================================================================
# Fake pynvml + GPU-ready monitor
# =============================================================================


@pytest.fixture
def fake_nvml() -> Any:
    """Install a fake ``pynvml`` module into ``sys.modules`` for one test.

    Every read returns the fixture-owned value above, ``NVMLError`` is a REAL
    exception class (so ``contextlib.suppress`` behaves like production and like
    the ``suppress(None)`` mutants), and the two NVML constants used by
    ``_get_gpu_stats_real`` are identifiable sentinels rather than MagicMock
    auto-attributes.
    """
    saved = sys.modules.get("pynvml")
    module = MagicMock(name="pynvml")
    module.NVMLError = FakeNVMLError
    module.NVML_TEMPERATURE_GPU = TEMP_CONST
    module.NVML_CLOCK_SM = SM_CONST
    module.nvmlInit.return_value = None
    module.nvmlDeviceGetHandleByIndex.return_value = HANDLE
    module.nvmlDeviceGetName.return_value = GPU_NAME
    module.nvmlDeviceGetUtilizationRates.return_value = types.SimpleNamespace(
        gpu=GPU_UTIL_RAW, memory=MEMBW_RAW
    )
    module.nvmlDeviceGetMemoryInfo.return_value = types.SimpleNamespace(
        used=USED_BYTES, total=TOTAL_BYTES
    )
    module.nvmlDeviceGetTemperature.return_value = TEMP_RAW
    module.nvmlDeviceGetPowerUsage.return_value = POWER_RAW
    module.nvmlDeviceGetFanSpeed.return_value = FAN_RAW
    module.nvmlDeviceGetClockInfo.return_value = SM_CLOCK_RAW
    module.nvmlDeviceGetPerformanceState.return_value = PSTATE_RAW
    sys.modules["pynvml"] = module
    try:
        yield module
    finally:
        if saved is None:
            sys.modules.pop("pynvml", None)
        else:
            sys.modules["pynvml"] = saved


def ready_monitor() -> GPUMonitor:
    """A ``GPUMonitor`` whose ``_initialize_nvml`` ran against ``fake_nvml``.

    L217-L219 wire ``_gpu_handle`` / ``_gpu_name`` / ``_gpu_available`` from the
    fake module, so the guard at L560 passes and the nvidia-smi probe (L194-L195)
    is never reached.
    """
    monitor = GPUMonitor(poll_interval=5.0)
    assert monitor._gpu_available is True  # L219
    assert monitor._gpu_handle is HANDLE  # L217
    return monitor


def read_stats(monitor: GPUMonitor) -> dict[str, Any]:
    """``_get_gpu_stats_real`` with the extended-metric helper stubbed to ``{}``.

    ``_get_extended_metrics`` (L482) is another group's battery; stubbing it with
    an autospec'd mock keeps the fifteen ``extended.get(...)`` legs (L628-L643) at
    their shipped None and leaves this file's observables exactly the L560-L626
    guard/init/wiring/tz band.
    """
    with patch.object(GPUMonitor, "_get_extended_metrics", autospec=True, return_value={}) as ext:
        stats = monitor._get_gpu_stats_real()
    assert ext.call_count == 1  # L612
    return stats


# =============================================================================
# L560-L561 - the guard message (key 5)
# =============================================================================


@pytest.mark.parametrize(
    ("available", "handle"),
    [
        (True, None),  # `not self._gpu_handle` leg of the L560 `or`
        (False, HANDLE),  # `not self._gpu_available` leg
        (False, None),  # both falsy
    ],
)
def test_gpu_absent_or_handle_absent_raises_the_exact_guard_message(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_nvml: Any,
    available: bool,
    handle: Any,
) -> None:
    """L560-L561: either falsy operand raises ``RuntimeError("GPU not available")``.

    Full ``str(exc) ==`` equality (not ``in``/``match``) so the
    ``"XXGPU not availableXX"`` wrap of key 5 is a miss.  The raise happens
    BEFORE the L563 ``try``, so the L648 error log never fires for this route.
    """
    monitor = ready_monitor()
    monkeypatch.setattr(monitor, "_gpu_available", available)
    monkeypatch.setattr(monitor, "_gpu_handle", handle)
    win(caplog)

    with pytest.raises(RuntimeError) as excinfo:
        monitor._get_gpu_stats_real()

    assert str(excinfo.value) == GUARD_MSG  # L561 verbatim
    assert READ_ERROR_MSG not in msgs(caplog)  # the guard is outside the try
    fake_nvml.nvmlDeviceGetUtilizationRates.assert_not_called()


# =============================================================================
# L563-L626 - the success dict (keys 16/17/52/53/57/58/65/66) + tz (key 83)
# =============================================================================


def test_success_returns_the_shipped_value_for_every_field(fake_nvml: Any) -> None:
    """Nine locally-initialised fields carry the shipped computed values.

    The ``assign -> None`` rows (16/52/57/65) show up as a None value here, and
    the ``float(None)`` / ``int(None)`` rows (17/53/58/66) show up as a TypeError
    escaping the ``suppress(NVMLError)`` blocks into the L646 handler (which logs
    and re-raises), so this one leg is red for all eight keys.
    """
    stats = read_stats(ready_monitor())

    assert stats["gpu_name"] == GPU_NAME  # L615 self._gpu_name
    assert stats["gpu_utilization"] == 31.4  # L573 float(31.4)
    assert stats["memory_bandwidth_utilization"] == 12.5  # L574 float(12.5)
    assert stats["memory_used"] == 3072  # L581 int((3*1024**3 + 7) / 1024**2)
    assert stats["memory_total"] == 24576  # L582 int((24*1024**3 + 512) / 1024**2)
    assert stats["temperature"] == 41.0  # L587 float(41)
    assert stats["power_usage"] == 12500.0  # L594 float(12_500_000 / 1000.0)
    assert stats["fan_speed"] == 42  # L599 int(42.4)
    assert stats["sm_clock"] == 1500  # L604 int(1500.6)
    assert stats["pstate"] == 8  # L609 int(8)
    assert {k: type(stats[k]) for k in FIELDS[:2]} == {
        "gpu_utilization": float,
        "memory_bandwidth_utilization": float,
    }
    assert {
        k: type(stats[k]) for k in ("memory_used", "memory_total", "fan_speed", "sm_clock")
    } == {
        "memory_used": int,
        "memory_total": int,
        "fan_speed": int,
        "sm_clock": int,
    }
    assert {k: stats[k] for k in FIELDS} == success_values()


def test_stats_recorded_at_carries_the_utc_timezone(fake_nvml: Any) -> None:
    """L621 ``datetime.now(UTC)`` stamps a timezone-aware UTC timestamp.

    ``datetime.now(None)`` (key 83) is NAIVE - the ``tzinfo is UTC`` pin is the
    observable, and no clock is patched to reach it.
    """
    stats = read_stats(ready_monitor())

    assert stats["recorded_at"].tzinfo is UTC  # L621 datetime.now(UTC)


# =============================================================================
# L566-L609 - handle / constant wiring (keys 8/13/22/39/40/41/42/48/54/59/60/61/62/67)
# =============================================================================


def test_every_nvml_read_is_called_with_the_gpu_handle_and_constants(fake_nvml: Any) -> None:
    """Each read receives ``self._gpu_handle`` (L566) plus its NVML constant.

    The only observable for ``handle = None`` (key 8) and for the
    ``arg -> None`` / ``drop_arg`` rows: a MagicMock answers ANY handle with the
    same value, so the return dict alone can never see the drop.
    """
    read_stats(ready_monitor())

    fake_nvml.nvmlDeviceGetUtilizationRates.assert_called_once_with(HANDLE)  # L572
    fake_nvml.nvmlDeviceGetMemoryInfo.assert_called_once_with(HANDLE)  # L580
    # L588 - both positionals, in order
    fake_nvml.nvmlDeviceGetTemperature.assert_called_once_with(HANDLE, TEMP_CONST)
    fake_nvml.nvmlDeviceGetPowerUsage.assert_called_once_with(HANDLE)  # L594
    fake_nvml.nvmlDeviceGetFanSpeed.assert_called_once_with(HANDLE)  # L599
    # L604 - both positionals, in order
    fake_nvml.nvmlDeviceGetClockInfo.assert_called_once_with(HANDLE, SM_CONST)
    fake_nvml.nvmlDeviceGetPerformanceState.assert_called_once_with(HANDLE)  # L609


def test_every_nvml_read_happens_exactly_once_per_metric(fake_nvml: Any) -> None:
    """Control: one call per metric, no retry, no aliasing between metrics.

    Kills nothing of its own (the arg rows leave the counts alone) - it is here so
    the ``assert_called_once_with`` legs above cannot be satisfied by a stray
    second call with the right shape.
    """
    read_stats(ready_monitor())

    for name in FAIL_TO_NONE:
        assert getattr(fake_nvml, name).call_count == 1, name


# =============================================================================
# L571-L609 - per-block NVML failure (keys 10/50/55/63 + twins 51/56/64)
# =============================================================================


@pytest.mark.parametrize("failing_call", sorted(FAIL_TO_NONE))
def test_single_nvml_failure_leaves_that_field_none(
    caplog: pytest.LogCaptureFixture, fake_nvml: Any, failing_call: str
) -> None:
    """One failing read degrades only its own field and raises nothing.

    * kills the ``init -> ""`` rows (10 L570, 50 L597, 55 L602, 63 L607): the
      block is skipped, so the shipped init (None) is the value the dict carries;
    * kills all SEVEN ``suppress(None)`` candidates of the twin keys 51/56/64 -
      under ``suppress(None)`` the ``NVMLError`` survives ``__enter__`` only to
      have ``__exit__`` fail on ``issubclass(exctype, (None,))``, which escapes as
      a TypeError to the L646 handler and re-raises.  Because the harness cannot
      tell which of the seven sites a ``suppress`` diff really mutated, every
      site is covered by the matching parameter of this test.
    """
    expected = success_values()
    for field in FAIL_TO_NONE[failing_call]:
        expected[field] = None
    getattr(fake_nvml, failing_call).side_effect = FakeNVMLError(f"{failing_call} unavailable")
    win(caplog)

    stats = read_stats(ready_monitor())

    assert {k: stats[k] for k in FIELDS} == expected
    assert READ_ERROR_MSG not in msgs(caplog)  # suppress is silent


def test_all_nvml_failures_degrade_every_field_to_none(
    caplog: pytest.LogCaptureFixture, fake_nvml: Any
) -> None:
    """Every block failing leaves all nine fields at their shipped None init.

    Control leg: it states the whole-band init contract (L569-L607) at once, so
    the per-field legs above cannot pass by an accidental fall-through, and the
    ``assign -> None`` rows are consistent with it.
    """
    monitor = ready_monitor()
    for name in FAIL_TO_NONE:
        getattr(fake_nvml, name).side_effect = FakeNVMLError(f"{name} unavailable")
    win(caplog)  # opened AFTER construction so only the read's own records are captured

    stats = read_stats(monitor)

    assert {k: stats[k] for k in FIELDS} == dict.fromkeys(FIELDS, None)
    assert stats["gpu_name"] == GPU_NAME  # L615 still comes from _gpu_name
    assert msgs(caplog) == []  # nine suppressed blocks, zero log records
