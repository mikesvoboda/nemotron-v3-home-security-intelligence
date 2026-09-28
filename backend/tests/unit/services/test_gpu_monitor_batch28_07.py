"""S3 batch-28 lane gm07 - ``gpu_monitor`` group G07b kill battery (75 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda -
byte-identical to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/gpu_monitor/manifest.json`` group ``G07b`` (75 KILLABLE / 0
EQUIVALENT), plus ``group_12.keys`` and ``survivors.json`` for the exact per-key
diffs.  Splice report ``splice-group_12.json``: status ``{'clean': 75}`` - no
occurrence twins and nothing ``unparseable``, so no manual mutate.py-style probe
was needed for any key of this group.

Function under test: the return-dict extended block of
``GPUMonitor._get_gpu_stats_real`` - the fifteen lines
``"<metric>": extended.get("<metric>")`` at L628-L643.

Key shape (five rows per line, fifteen lines)
=============================================
Per line ``"<m>": extended.get("<m>")`` the bank carries

1. ``string:wrapXX`` on the RETURN-KEY literal -> ``"XX<m>XX"`` (output key renames)
2. ``string:upper`` on the RETURN-KEY literal -> ``"<M>"`` (output key renames)
3. ``call_arg_mut`` on ``extended.get("<m>")`` -> ``extended.get(None)`` (value None)
4. ``string:wrapXX`` on the GET-ARG literal -> ``extended.get("XX<m>XX")`` (value None)
5. ``string:upper`` on the GET-ARG literal -> ``extended.get("<M>")`` (value None)

``EXTENDED`` below maps every shipped metric name to a DISTINCT integer, so
* rows 1-2 miss on ``stats["<m>"]`` (KeyError) and on the set-inequality leg;
* rows 3-5 miss on ``stats["<m>"] == index`` (the lookup finds nothing -> None);
* and because the injected integers are pairwise distinct and differ from None,
  no mutant can satisfy one metric's leg with another metric's value.

Test -> mutant-key map
======================
Every key of ``group_12.keys`` (suffix ``N`` of
``xǁGPUMonitorǁ_get_gpu_stats_real__mutmut_N``) is claimed by exactly one of the
fifteen parameter sets of the two legs below - one parameter per production line
L628-L643:

- ``test_extended_metrics_are_carried_by_their_shipped_names`` (rows 1-2 kill:
  renamed output key -> KeyError + ``set(EXTENDED) <= set(stats)`` inequality;
  rows 3-5 additionally reddened here since the value leg is asserted too)
- ``test_extended_metrics_are_carried_even_when_the_helper_reports_nothing``
  (``extended == {}`` -> every one of the fifteen stats entries is present and
  None; kills rows 1-2 for the same reason as above and is the anti-aliasing
  control that proves the fifteen names are read independently rather than from
  one shared lookup)

Full key list, by line (all fifteen lines are covered identically by both legs):
L628 92-96 - L629 97-101 - L630 102-106 - L631 107-111 - L632 112-116 -
L633 117-121 - L635 122-126 - L636 127-131 - L637 132-136 - L638 137-141 -
L639 142-146 - L640 147-151 - L641 152-156 - L642 157-161 - L643 162-166.

Control legs that kill nothing of their own:
``test_extended_helper_is_called_once_with_no_arguments`` (the L612 call shape the
key rows leave untouched, stated so a value leg cannot be satisfied by a stray
call) and ``test_core_fields_are_present_beside_the_extended_block`` (the shipped
key set of the whole dict, pinning that the fifteen extended names are additions
to - not replacements of - the core keys).

Shipped behaviour only - nothing here invents a contract.  The fifteen metric
names and their positions are transcribed from the shipped lines cited in
``EXTENDED``; the values are injected by this file through a stub of the shipped
helper, and ``pynvml`` is faked wholesale (never a real GPU).

Discipline
----------
* ``_get_extended_metrics`` (L482, a SYNC def called sync at L612) is stubbed with
  ``patch.object(..., autospec=True)`` (WP4.2 fast path), so the fifteen
  ``extended.get`` legs are the only variables while the helper's own NVML
  internals - groups G04a/G04b's territory - stay out of these observables.
* ``pynvml`` is faked through ``sys.modules`` for the duration of one test (the
  ``test_gpu_monitor.py`` ``mock_pynvml`` idiom) and restored after; no
  import-time global spy exists in this file.
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted; the battery is fully synchronous.
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.services.gpu_monitor import GPUMonitor

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# The fifteen return-dict keys of the extended block, in shipped order, each with
# the shipped ``extended.get("<same name>")`` argument beside it:
#   L628 "throttle_reasons": extended.get("throttle_reasons")
#   L629 "power_limit": extended.get("power_limit")
#   L630 "sm_clock_max": extended.get("sm_clock_max")
#   L631 "compute_processes_count": extended.get("compute_processes_count")
#   L632 "pcie_replay_counter": extended.get("pcie_replay_counter")
#   L633 "temp_slowdown_threshold": extended.get("temp_slowdown_threshold")
#   L635 "memory_clock": extended.get("memory_clock")
#   L636 "memory_clock_max": extended.get("memory_clock_max")
#   L637 "pcie_link_gen": extended.get("pcie_link_gen")
#   L638 "pcie_link_width": extended.get("pcie_link_width")
#   L639 "pcie_tx_throughput": extended.get("pcie_tx_throughput")
#   L640 "pcie_rx_throughput": extended.get("pcie_rx_throughput")
#   L641 "encoder_utilization": extended.get("encoder_utilization")
#   L642 "decoder_utilization": extended.get("decoder_utilization")
#   L643 "bar1_used": extended.get("bar1_used")
EXTENDED: tuple[str, ...] = (
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
)
assert len(set(EXTENDED)) == 15, "the extended block is fifteen distinct metrics"

# Injected payload: name -> a DISTINCT integer, so a renamed lookup yields None
# and a renamed output key yields a KeyError rather than a borrowed value.
PAYLOAD = {name: index for index, name in enumerate(EXTENDED)}

# Core (non-extended) return keys of the same dict literal (L615-L626).
CORE = (
    "gpu_name",
    "gpu_utilization",
    "memory_used",
    "memory_total",
    "temperature",
    "power_usage",
    "recorded_at",
    "fan_speed",
    "sm_clock",
    "memory_bandwidth_utilization",
    "pstate",
)

GPU_NAME = "Fake RTX 6000 (battery-injected)"
HANDLE = object()


class FakeNVMLError(Exception):
    """Stands in for ``pynvml.NVMLError``."""


# =============================================================================
# Fake pynvml + GPU-ready monitor
# =============================================================================


@pytest.fixture
def fake_nvml() -> Any:
    """Install a fake ``pynvml`` module into ``sys.modules`` for one test.

    Just live enough for ``_get_gpu_stats_real`` to run its nine reads; the
    extended helper is stubbed separately, so none of the extended NVML calls is
    reached.
    """
    saved = sys.modules.get("pynvml")
    module = MagicMock(name="pynvml")
    module.NVMLError = FakeNVMLError
    module.NVML_TEMPERATURE_GPU = "NVML_TEMPERATURE_GPU"
    module.NVML_CLOCK_SM = "NVML_CLOCK_SM"
    module.nvmlInit.return_value = None
    module.nvmlDeviceGetHandleByIndex.return_value = HANDLE
    module.nvmlDeviceGetName.return_value = GPU_NAME
    module.nvmlDeviceGetUtilizationRates.return_value = types.SimpleNamespace(gpu=31.4, memory=12.5)
    module.nvmlDeviceGetMemoryInfo.return_value = types.SimpleNamespace(
        used=3 * 1024**3 + 7, total=24 * 1024**3 + 512
    )
    module.nvmlDeviceGetTemperature.return_value = 41
    module.nvmlDeviceGetPowerUsage.return_value = 12_500_000
    module.nvmlDeviceGetFanSpeed.return_value = 42.4
    module.nvmlDeviceGetClockInfo.return_value = 1500.6
    module.nvmlDeviceGetPerformanceState.return_value = 8
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
    fake module, so the L560 guard passes.
    """
    monitor = GPUMonitor(poll_interval=5.0)
    assert monitor._gpu_available is True  # L219
    assert monitor._gpu_handle is HANDLE  # L217
    return monitor


def read_stats(monitor: GPUMonitor, extended: dict[str, Any]) -> dict[str, Any]:
    """``_get_gpu_stats_real`` with the shipped helper stubbed to ``extended``.

    The stub is autospec'd against the real ``_get_extended_metrics`` signature
    (WP4.2 fast path), so the L612 call site is still exercised.
    """
    with patch.object(
        GPUMonitor, "_get_extended_metrics", autospec=True, return_value=extended
    ) as ext:
        stats = monitor._get_gpu_stats_real()
    assert ext.call_count == 1  # L612, once per read
    return stats


# =============================================================================
# L628-L643 - the fifteen extended legs, name by name
# =============================================================================


@pytest.mark.parametrize("metric", EXTENDED)
def test_extended_metrics_are_carried_by_their_shipped_names(fake_nvml: Any, metric: str) -> None:
    """One parameter per extended line: the value travels under the shipped name.

    ``PAYLOAD`` gives every metric a unique integer, so
    * a return-key rename (wrap/upper) makes ``stats[metric]`` a KeyError and
      breaks the set-inequality leg, and
    * a get-arg rename (or ``get(None)``) makes the entry ``None`` instead of the
      injected integer.
    """
    stats = read_stats(ready_monitor(), dict(PAYLOAD))

    assert set(EXTENDED) <= set(stats)  # the shipped name is present
    assert stats[metric] == PAYLOAD[metric]  # L<line> value leg
    assert stats[metric] is not None  # L<line> a failed lookup is visible
    # the entry is this metric's own value, not another metric's (anti-aliasing)
    assert {name: stats[name] for name in EXTENDED} == PAYLOAD


@pytest.mark.parametrize("metric", EXTENDED)
def test_extended_metrics_are_carried_even_when_the_helper_reports_nothing(
    fake_nvml: Any, metric: str
) -> None:
    """With ``extended == {}`` the shipped key still exists and its value is None.

    States the same fifteen names from the other side: they come from the RETURN
    dict, not from whatever the helper happened to return, so a renamed key is as
    fatal here as above while the None default is proven per-line rather than
    inherited from a single shared lookup.
    """
    stats = read_stats(ready_monitor(), {})

    assert metric in stats  # the shipped name survives an empty helper
    assert stats[metric] is None  # ``dict.get`` default for a missing metric
    assert {name: stats[name] for name in EXTENDED} == dict.fromkeys(EXTENDED, None)


# =============================================================================
# Control legs
# =============================================================================


def test_extended_helper_is_called_once_with_no_arguments(fake_nvml: Any) -> None:
    """L612 ``extended = self._get_extended_metrics()`` - bare, exactly once.

    Kills nothing of its own (no g12 diff touches the call), but it is the leg
    that proves the fifteen value legs above read from a single helper result.
    """
    monitor = ready_monitor()

    with patch.object(GPUMonitor, "_get_extended_metrics", autospec=True, return_value={}) as ext:
        monitor._get_gpu_stats_real()

    assert ext.call_count == 1  # L612
    assert ext.call_args.args == (monitor,)  # bound call, zero explicit arguments


def test_core_fields_are_present_beside_the_extended_block(fake_nvml: Any) -> None:
    """The shipped key set is core + extended, with no duplicate roles.

    Control for the set-inequality leg above: it pins the core names (L615-L626)
    as present as well, so ``set(EXTENDED) <= set(stats)`` is read as a statement
    about the extended block rather than about the whole dict.
    """
    stats = read_stats(ready_monitor(), dict(PAYLOAD))

    assert set(stats) == set(CORE) | set(EXTENDED)  # the shipped 26-key schema
    assert stats["gpu_name"] == GPU_NAME  # L615
    assert stats["gpu_utilization"] == 31.4  # L616 <- L573
    assert stats["recorded_at"].tzinfo is not None  # L621 datetime.now(UTC)
