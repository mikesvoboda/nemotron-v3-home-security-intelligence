"""S3 batch-28 lane gm08 - ``gpu_monitor`` group G07c kill battery (29 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda -
byte-identical to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/gpu_monitor/manifest.json`` group
"G07c _get_gpu_stats_real: return-key identity L623-626 + failure-log extra
contract" (29 KILLABLE / 0 EQUIVALENT), plus ``group_13.keys`` and
``survivors.json`` for the exact per-key diffs.

Everything asserted below is SHIPPED behaviour read off the frozen file at the
line quoted in the comment above each pin; production never bends for a test.

Test -> mutant-key map
======================
Every key below is in ``group_13.keys`` (all are
``xǁGPUMonitorǁ_get_gpu_stats_real__mutmut_N``).

- ``__mutmut_84`` / ``_85``   L623 ``"fan_speed"`` -> ``"XXfan_speedXX"`` / ``"FAN_SPEED"``
- ``__mutmut_86`` / ``_87``   L624 ``"sm_clock"``  -> ``"XXsm_clockXX"``  / ``"SM_CLOCK"``
- ``__mutmut_88`` / ``_89``   L625 ``"memory_bandwidth_utilization"`` -> wrap/upper
- ``__mutmut_90`` / ``_91``   L626 ``"pstate"``    -> ``"XXpstateXX"``    / ``"PSTATE"``
  -> ``test_real_stats_return_carries_exactly_the_shipped_twenty_six_keys``
     (set equality + every shipped-name lookup + value pins)
- ``__mutmut_167`` L648 ``logger.error("Error reading GPU stats", extra=...)`` ->
  first positional argument ``None`` (UNPARSEABLE for the replay splicer - mutmut
  reprints the multi-line call at the statement indent; proven by the manual
  probe at /tmp/wp-pw/gm/probe0809/probe13_manual.py, mirrored here)
- ``__mutmut_171`` / ``_172`` / ``_173``  L649 message -> ``"XXError reading GPU statsXX"`` /
  all-lower / all-upper
  -> ``test_a_non_nvml_failure_escalates_as_exactly_one_error_then_the_original_raise``
     (``record.msg`` EXACT + ERROR level + exactly-one-record window)
- ``__mutmut_168`` L648 ``extra=...`` -> ``extra=None`` and ``__mutmut_170``
  ``extra=`` dropped entirely (both UNPARSEABLE for the splicer, same reason)
- ``__mutmut_174`` / ``_175`` / ``_176``  L651 ``"gpu_id"`` wrap/upper and the
  ``0`` -> ``1`` literal
- ``__mutmut_177`` / ``_178``            L652 ``"gpu_name"`` wrap/upper
- ``__mutmut_179`` / ``_180`` / ``_181`` / ``_182``  L653 ``"operation"`` and
  ``"get_gpu_stats_pynvml"`` wrap/upper
- ``__mutmut_183`` / ``_184`` / ``_185``  L654 ``"error"`` wrap/upper and
  ``str(e)`` -> ``str(None)``
- ``__mutmut_186`` / ``_187`` / ``_188``  L655 ``"error_type"`` wrap/upper and
  ``type(e)`` -> ``type(None)``
  -> ``test_the_failure_error_record_carries_every_shipped_extra_attribute``
     (``extra`` entries arrive on the record as attributes, so a renamed key is
     an ``AttributeError`` at the lookup and ``extra=None``/dropped leaves every
     one of them missing; ``__mutmut_176`` additionally needs the value pin
     ``record.gpu_id == 0`` because a renamed key kills nothing for a literal
     mutation, and ``_177``/``_178`` additionally need the success-side
     ``stats["gpu_name"]`` identity in the first test because those two keys ALSO
     occur at L615 (return-dict twin) - every candidate must redden.)

Control legs that pin the other shipped arms of the same def (and so make the
killing legs un-fall-through-able):
``test_the_real_getter_refuses_before_touching_nvml_when_no_gpu_is_wired``,
``test_an_nvml_failure_is_suppressed_into_a_none_valued_key``,
``test_missing_extended_metrics_arrive_as_explicit_none_values``.

Discipline
----------
* pynvml is mocked WHOLESALE (neighbour ``mock_pynvml`` idiom) - never a real
  GPU.  This file injects its own module-local fake (``gm08_nvml``) rather than
  the neighbour fixture because G07c needs (a) a REAL exception CLASS for
  ``pynvml.NVMLError`` so ``contextlib.suppress`` behaves faithfully and (b)
  exact numeric values, since the killed mutants are key-name and literal
  mutations.  ``sys.modules`` is restored by ``monkeypatch``.
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  plus the ``extra``-supplied attributes (batch27_01 pattern).
* No ``time.monotonic`` / ``time.perf_counter`` patch anywhere, no session-scoped
  clock patch, no import-time global spy.  ``datetime.now(UTC)`` is only read
  (tz-awareness), never faked - this group has no timing site.
* Every ``patch`` site is ``autospec=True``.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest

from backend.services import gpu_monitor as M

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L649: logger.error("Error reading GPU stats", extra={...})
READ_ERROR_MSG = "Error reading GPU stats"

# L653: "operation": "get_gpu_stats_pynvml"
READ_ERROR_OPERATION = "get_gpu_stats_pynvml"

# L614-L644: the return-dict key set, in shipped order (26 names - 7 core +
# 4 extended + 6 high-value + 9 medium-value).  Transcribed verbatim.
SHIPPED_KEYS = (
    "gpu_name",  # L615
    "gpu_utilization",  # L616
    "memory_used",  # L617
    "memory_total",  # L618
    "temperature",  # L619
    "power_usage",  # L620
    "recorded_at",  # L621
    "fan_speed",  # L623  <- G07c keys 84/85
    "sm_clock",  # L624  <- G07c keys 86/87
    "memory_bandwidth_utilization",  # L625  <- G07c keys 88/89
    "pstate",  # L626  <- G07c keys 90/91
    "throttle_reasons",  # L628
    "power_limit",  # L629
    "sm_clock_max",  # L630
    "compute_processes_count",  # L631
    "pcie_replay_counter",  # L632
    "temp_slowdown_threshold",  # L633
    "memory_clock",  # L635
    "memory_clock_max",  # L636
    "pcie_link_gen",  # L637
    "pcie_link_width",  # L638
    "pcie_tx_throughput",  # L639
    "pcie_rx_throughput",  # L640
    "encoder_utilization",  # L641
    "decoder_utilization",  # L642
    "bar1_used",  # L643
)

# The 15 keys the shipped dict takes from ``self._get_extended_metrics()``
# (L628-L643 - every one is ``extended.get(<name>)``).
EXTENDED_KEYS = SHIPPED_KEYS[11:]

# Values this file injects through the fake pynvml, so every pin below is a
# value WE chose (never a value production happens to produce on a host).
GPU_NAME = "Tesla-T4-lane-gm08"
UTIL_GPU = 75.0  # L573 float(utilization.gpu)
UTIL_MEMORY = 12.5  # L574 float(utilization.memory)
MEM_USED_BYTES = 3072 * 1024 * 1024  # L581 -> 3072 MB
MEM_TOTAL_BYTES = 24576 * 1024 * 1024  # L582 -> 24576 MB
TEMPERATURE_C = 65  # L587 -> 65.0
POWER_MW = 150_000  # L594 /1000.0 -> 150.0 W
FAN_PCT = 42  # L599 -> int
SM_CLOCK_MHZ = 1500  # L604 -> int
PSTATE = 8  # L609 -> int

# The L581/L582/L594 divisors, pinned from the shipped source so an injected
# value can be recomputed here instead of copied: memory_used = int(bytes /
# (1024 * 1024))  (L581), power_usage = float(milliwatts / 1000.0)  (L594).
BYTES_PER_MB = 1024 * 1024
MILLIWATTS_PER_WATT = 1000.0


class Gm08NVMLError(Exception):
    """Real exception class standing in for ``pynvml.NVMLError``.

    ``contextlib.suppress`` needs a class it can put in an ``except`` clause; a
    ``MagicMock`` cannot be one.  It is NOT a superclass of ``RuntimeError``, so
    a ``RuntimeError`` raised by one of the fake's getters escapes every
    ``suppress(pynvml.NVMLError)`` block and lands in the shipped
    ``except Exception as e`` at L646 - which is the G07c failure arm.
    """


class Gm08Nvml:
    """Wholesale pynvml double with the getters ``_get_gpu_stats_real`` calls.

    Handles are tracked per getter (``handles_for``) so the test can prove the
    shipped ``handle = self._gpu_handle`` wiring (L566) reached the calls, and
    ``raise_for`` marks individual getters as NVMLError-raising to exercise the
    ``contextlib.suppress`` arms.
    """

    NVMLError = Gm08NVMLError
    NVML_TEMPERATURE_GPU = 0
    NVML_CLOCK_SM = 1
    NVML_CLOCK_MEM = 2
    NVML_PCIE_UTIL_TX_BYTES = 3
    NVML_PCIE_UTIL_RX_BYTES = 4
    NVML_TEMPERATURE_THRESHOLD_SLOWDOWN = 5

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.handles_for: dict[str, list[Any]] = {}
        self.raise_for: set[str] = set()
        self._handle = object()

    def _call(self, name: str, handle: Any, result: Any) -> Any:
        self.calls.append(name)
        self.handles_for.setdefault(name, []).append(handle)
        if name in self.raise_for:
            raise Gm08NVMLError(f"{name} refused")
        return result

    # -- the getters _get_gpu_stats_real reaches directly (L572-L609) ---------
    def nvmlDeviceGetUtilizationRates(self, handle: Any) -> Any:
        util = self._call("nvmlDeviceGetUtilizationRates", handle, None)
        return _Rates(UTIL_GPU, UTIL_MEMORY) if util is None else util

    def nvmlDeviceGetMemoryInfo(self, handle: Any) -> Any:
        self._call("nvmlDeviceGetMemoryInfo", handle, None)
        return _Memory(MEM_USED_BYTES, MEM_TOTAL_BYTES)

    def nvmlDeviceGetTemperature(self, handle: Any, sensor: int) -> Any:
        return self._call("nvmlDeviceGetTemperature", handle, TEMPERATURE_C)

    def nvmlDeviceGetPowerUsage(self, handle: Any) -> Any:
        return self._call("nvmlDeviceGetPowerUsage", handle, POWER_MW)

    def nvmlDeviceGetFanSpeed(self, handle: Any) -> Any:
        return self._call("nvmlDeviceGetFanSpeed", handle, FAN_PCT)

    def nvmlDeviceGetClockInfo(self, handle: Any, clock: int) -> Any:
        return self._call("nvmlDeviceGetClockInfo", handle, SM_CLOCK_MHZ)

    def nvmlDeviceGetPerformanceState(self, handle: Any) -> Any:
        return self._call("nvmlDeviceGetPerformanceState", handle, PSTATE)

    # -- the getters _get_extended_metrics reaches (L494-L547) ----------------
    def nvmlInit(self) -> None:
        return None

    def nvmlShutdown(self) -> None:
        return None

    def nvmlDeviceGetHandleByIndex(self, index: int) -> Any:
        return self._handle

    def nvmlDeviceGetName(self, handle: Any) -> str:
        return GPU_NAME

    def _unsupported(self, name: str, handle: Any) -> Any:
        self.calls.append(name)
        self.handles_for.setdefault(name, []).append(handle)
        raise Gm08NVMLError(f"{name} unsupported by the gm08 fake")

    def nvmlDeviceGetCurrentClocksThrottleReasons(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetCurrentClocksThrottleReasons", handle)

    def nvmlDeviceGetPowerManagementLimit(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetPowerManagementLimit", handle)

    def nvmlDeviceGetMaxClockInfo(self, handle: Any, clock: int) -> Any:
        return self._unsupported("nvmlDeviceGetMaxClockInfo", handle)

    def nvmlDeviceGetComputeRunningProcesses(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetComputeRunningProcesses", handle)

    def nvmlDeviceGetPcieReplayCounter(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetPcieReplayCounter", handle)

    def nvmlDeviceGetTemperatureThreshold(self, handle: Any, threshold: int) -> Any:
        return self._unsupported("nvmlDeviceGetTemperatureThreshold", handle)

    def nvmlDeviceGetCurrPcieLinkGeneration(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetCurrPcieLinkGeneration", handle)

    def nvmlDeviceGetCurrPcieLinkWidth(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetCurrPcieLinkWidth", handle)

    def nvmlDeviceGetPcieThroughput(self, handle: Any, direction: int) -> Any:
        return self._unsupported("nvmlDeviceGetPcieThroughput", handle)

    def nvmlDeviceGetEncoderUtilization(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetEncoderUtilization", handle)

    def nvmlDeviceGetDecoderUtilization(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetDecoderUtilization", handle)

    def nvmlDeviceGetBAR1MemoryInfo(self, handle: Any) -> Any:
        return self._unsupported("nvmlDeviceGetBAR1MemoryInfo", handle)


class _Rates:
    __slots__ = ("gpu", "memory")

    def __init__(self, gpu: float, memory: float) -> None:
        self.gpu = gpu
        self.memory = memory


class _Memory:
    __slots__ = ("total", "used")

    def __init__(self, used: int, total: int) -> None:
        self.used = used
        self.total = total


# =============================================================================
# Fixtures (module-local; nothing is written to a module global at import time)
# =============================================================================


@pytest.fixture
def gm08_nvml(monkeypatch: pytest.MonkeyPatch) -> Iterator[Gm08Nvml]:
    """Install the fake pynvml for the whole test (the module imports it lazily).

    ``backend/services/gpu_monitor.py`` imports pynvml INSIDE ``__init__`` and
    inside each stats method, so a ``sys.modules`` entry is the seam; the shipped
    ``_get_gpu_stats_real`` also opens with ``import pynvml`` (L564).
    """
    fake = Gm08Nvml()
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    yield fake


@pytest.fixture
def gm08_monitor(gm08_nvml: Gm08Nvml) -> Iterator[M.GPUMonitor]:
    """A GPUMonitor wired to the fake NVML, logs from construction discarded.

    ``caplog.set_level`` does not clear the buffer, so every test opens its own
    window with :func:`win` after construction.
    """
    monitor = M.GPUMonitor(poll_interval=3600)
    assert monitor._gpu_available is True, "the fake must wire a GPU for G07c"
    assert monitor._nvml_initialized is True
    yield monitor


# =============================================================================
# Observation helpers (batch27_01 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def only(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, RAW ``msg`` verbatim."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    rec = recs[0]
    assert rec.msg == msg, f"log text mutated: {rec.msg!r} != {msg!r}"
    assert rec.levelno == level
    return rec


# =============================================================================
# G07c leg (a): the shipped 26-key return, read back by SHIPPED NAME
#   kills __mutmut_84.._91 (the L623-L626 return-key wrapXX/upper family)
# =============================================================================


def test_real_stats_return_carries_exactly_the_shipped_twenty_six_keys(
    gm08_monitor: M.GPUMonitor,
) -> None:
    """Every shipped return name is present, once, with its shipped value.

    The four G07c return-key mutants rename ONE entry (``XXfan_speedXX``,
    ``SM_CLOCK``, ...), which breaks both the key-set equality and the shipped-
    name lookup - the renamed entry is invisible to ``stats["fan_speed"]``.
    """
    extended = dict.fromkeys(EXTENDED_KEYS, None)
    with patch.object(gm08_monitor, "_get_extended_metrics", autospec=True, return_value=extended):
        stats = gm08_monitor._get_gpu_stats_real()

    assert set(stats) == set(SHIPPED_KEYS), (
        f"return-dict key set diverges from shipped L614-L644: "
        f"missing={sorted(set(SHIPPED_KEYS) - set(stats))} "
        f"extra={sorted(set(stats) - set(SHIPPED_KEYS))}"
    )
    # L623-L626 - the four G07c keys, by shipped name and injected value.
    assert stats["fan_speed"] == FAN_PCT
    assert stats["sm_clock"] == SM_CLOCK_MHZ
    assert stats["memory_bandwidth_utilization"] == UTIL_MEMORY
    assert stats["pstate"] == PSTATE
    # L615-L621 core block (also kills the L615 "gpu_name" twin of __mutmut_177/_178).
    assert stats["gpu_name"] == GPU_NAME
    assert stats["gpu_utilization"] == UTIL_GPU
    assert stats["memory_used"] == MEM_USED_BYTES // BYTES_PER_MB
    assert stats["memory_total"] == MEM_TOTAL_BYTES // BYTES_PER_MB
    assert stats["temperature"] == float(TEMPERATURE_C)
    assert stats["power_usage"] == POWER_MW / MILLIWATTS_PER_WATT
    # L621: "recorded_at": datetime.now(UTC) - the shipped call passes the tz arg.
    assert isinstance(stats["recorded_at"], datetime)
    assert stats["recorded_at"].tzinfo is not None


def test_missing_extended_metrics_arrive_as_explicit_none_values(
    gm08_monitor: M.GPUMonitor,
) -> None:
    """An extended mapping with NOTHING in it still yields all 26 keys.

    Control leg: the shipped dict reads every high/medium metric through
    ``extended.get(...)`` (L628-L643), so a missing entry is a present ``None``
    key, never an absent key.  Without this leg the key-set equality above could
    be satisfied by an implementation that simply omits unknown entries.
    """
    with patch.object(gm08_monitor, "_get_extended_metrics", autospec=True, return_value={}):
        stats = gm08_monitor._get_gpu_stats_real()

    assert set(stats) == set(SHIPPED_KEYS)
    for name in EXTENDED_KEYS:
        assert stats[name] is None, f"shipped .get() default lost for {name!r}"


def test_an_nvml_failure_is_suppressed_into_a_none_valued_key(
    gm08_monitor: M.GPUMonitor,
    gm08_nvml: Gm08Nvml,
) -> None:
    """An NVMLError on one getter nulls that metric and keeps the key present.

    Control leg for the shipped ``contextlib.suppress(pynvml.NVMLError)`` arms
    (L598 for fan_speed, L608 for pstate): the key stays in the dict with a
    ``None`` value, so a renamed return key cannot hide behind a missing metric.
    """
    extended = dict.fromkeys(EXTENDED_KEYS, None)
    gm08_nvml.raise_for = {"nvmlDeviceGetFanSpeed", "nvmlDeviceGetPerformanceState"}
    with patch.object(gm08_monitor, "_get_extended_metrics", autospec=True, return_value=extended):
        stats = gm08_monitor._get_gpu_stats_real()

    assert set(stats) == set(SHIPPED_KEYS)
    assert stats["fan_speed"] is None
    assert stats["pstate"] is None
    # The untouched neighbours prove the suppression was per-block, not global.
    assert stats["sm_clock"] == SM_CLOCK_MHZ
    assert stats["memory_bandwidth_utilization"] == UTIL_MEMORY


def test_the_real_getter_refuses_before_touching_nvml_when_no_gpu_is_wired(
    gm08_nvml: Gm08Nvml,
) -> None:
    """L560-L561: no GPU / no handle -> RuntimeError, and NVML is never called.

    Control leg pinning the guard that sits above the whole G07c region.
    """
    monitor = M.GPUMonitor(poll_interval=3600)
    monitor._gpu_available = False
    monitor._gpu_handle = gm08_nvml._handle
    gm08_nvml.calls.clear()

    with pytest.raises(RuntimeError, match="GPU not available"):
        monitor._get_gpu_stats_real()

    assert gm08_nvml.calls == []

    monitor._gpu_available = True
    monitor._gpu_handle = None
    with pytest.raises(RuntimeError, match="GPU not available"):
        monitor._get_gpu_stats_real()

    assert gm08_nvml.calls == []


# =============================================================================
# G07c leg (b): the failure arm's ERROR record - message (L648-L649)
#   kills __mutmut_167 (msg -> None), _171/_172/_173 (message wrap/lower/upper)
# =============================================================================


def test_a_non_nvml_failure_escalates_as_exactly_one_error_then_the_original_raise(
    gm08_monitor: M.GPUMonitor,
    gm08_nvml: Gm08Nvml,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-NVMLError escape is logged once, EXACTLY, then re-raised.

    ``nvmlDeviceGetFanSpeed`` raises ``RuntimeError`` (L598's
    ``suppress(pynvml.NVMLError)`` does not cover it), so it lands in the shipped
    ``except Exception as e`` at L646.  ``record.msg`` is the RAW shipped message
    text, so ``msg -> None`` (which logging renders as ``"None"``) and the
    wrap/lower/upper variants all fail this assert.
    """
    gm08_nvml.raise_for = set()
    gm08_nvml.nvmlDeviceGetFanSpeed = _raising(RuntimeError("gm08 fan fault"))
    win(caplog)

    with pytest.raises(RuntimeError, match="gm08 fan fault"):
        gm08_monitor._get_gpu_stats_real()

    rec = only(caplog, logging.ERROR, READ_ERROR_MSG)
    assert rec.name == LOG_NAME
    assert rec.getMessage() == READ_ERROR_MSG
    # Nothing else is logged by the failure arm.
    assert len(mine(caplog)) == 1, [(r.levelno, r.msg) for r in mine(caplog)]


# =============================================================================
# G07c leg (c): the failure arm's ``extra=`` contract (L650-L656)
#   kills __mutmut_168, _170, _174.._188
# =============================================================================


def test_the_failure_error_record_carries_every_shipped_extra_attribute(
    gm08_monitor: M.GPUMonitor,
    gm08_nvml: Gm08Nvml,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The NEM-1123 extras arrive as record attributes with shipped identities.

    ``extra={...}`` (L650-L656) makes each entry an ATTRIBUTE of the record, so:

    * ``extra=None`` (``_168``) / the ``extra`` argument dropped (``_170``) ->
      every one of the five lookups below raises ``AttributeError``;
    * a renamed key (``_174``/``_175``/``_177``/``_178``/``_179``/``_180``/
      ``_183``/``_184``/``_186``/``_187``) -> the shipped-name lookup raises;
    * ``"gpu_id": 0`` -> ``1`` (``_176``) -> the value pin below fails;
    * ``"operation": "get_gpu_stats_pynvml"`` renamed (``_181``/``_182``) -> the
      shipped-value pin ``record.operation`` fails;
    * ``str(e)`` -> ``str(None)`` (``_185``) -> ``record.error`` reads ``"None"``;
    * ``type(e)`` -> ``type(None)`` (``_188``) -> ``record.error_type`` reads
      ``"NoneType"``.
    """
    gm08_nvml.raise_for = set()
    gm08_nvml.nvmlDeviceGetFanSpeed = _raising(RuntimeError("gm08 fan fault"))
    win(caplog)

    with pytest.raises(RuntimeError, match="gm08 fan fault"):
        gm08_monitor._get_gpu_stats_real()

    rec = only(caplog, logging.ERROR, READ_ERROR_MSG)
    # L651: "gpu_id": 0 - literal AND value.
    assert rec.gpu_id == 0, f"gpu_id extra mutated: {rec.gpu_id!r} != 0"
    # L652: "gpu_name": self._gpu_name - the wired device name.
    assert rec.gpu_name == GPU_NAME
    # L653: "operation": "get_gpu_stats_pynvml"
    assert rec.operation == READ_ERROR_OPERATION
    # L654: "error": str(e)
    assert rec.error == "gm08 fan fault"
    # L655: "error_type": type(e).__name__
    assert rec.error_type == "RuntimeError"


def test_the_failure_extra_values_track_the_exception_that_fired(
    gm08_monitor: M.GPUMonitor,
    gm08_nvml: Gm08Nvml,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A different fault text / type produces different ``error``/``error_type``.

    Control leg that makes the two value pins above non-coincidental: the extras
    are the EXCEPTION's own str/type (L654/L655), not constants.  A
    ``str(None)``/``type(None)`` mutant reads "None"/"NoneType" here too.
    """
    gm08_nvml.raise_for = set()
    gm08_nvml.nvmlDeviceGetPowerUsage = _raising(ValueError("gm08 power fault"))
    win(caplog)

    with pytest.raises(ValueError, match="gm08 power fault"):
        gm08_monitor._get_gpu_stats_real()

    rec = only(caplog, logging.ERROR, READ_ERROR_MSG)
    assert rec.error == "gm08 power fault"
    assert rec.error_type == "ValueError"
    assert rec.gpu_id == 0
    assert rec.gpu_name == GPU_NAME
    assert rec.operation == READ_ERROR_OPERATION


def _raising(exc: BaseException):
    """A callable that ignores its arguments and raises ``exc``."""

    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise exc

    return _raise
