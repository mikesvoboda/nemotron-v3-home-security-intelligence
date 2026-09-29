"""S3 batch-28 lane gm11 - ``gpu_monitor`` group G08b2 kill battery (33 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest group:

* group 16 ``G08b2 _get_gpu_stats_mock: link/throughput/encoder/BAR1 constants
  (20-25)`` -> ``/tmp/wp-pw/gpu_monitor/group_16.keys`` (33 keys, all KILLABLE;
  ``splice-group_16.json``: 24 clean + 9 twins, 0 unparseable - no manual
  ``mutate.py``-style probe is required for this group).

Battery shape
=============
All 33 diffs sit on ``backend/services/gpu_monitor.py`` L723-L729 - the
``pcie_link_gen`` / ``pcie_link_width`` constants, the ``pcie_tx_throughput`` /
``pcie_rx_throughput`` sinusoids, the ``encoder_utilization`` /
``decoder_utilization`` / ``bar1_used`` constants - plus the SHIPPED key names of
those same lines.  9 keys are bare digit tokens whose ``before`` text repeats
across ``_get_gpu_stats_mock`` (``'0'`` -> 25 sites, ``'2'`` -> 18, ``'4'`` -> 6),
so the replay harness's OCCURRENCE-TWIN rule obliges EVERY one of those sites to
redden this battery.  The admitted test_spec ("assert ``pcie_link_gen == 4``,
``pcie_link_width == 16``, ``pcie_tx_throughput == int(100000 + 50000*sin(2*pi*tf))``,
... EXACT ... 12 key wrapXX/upper die on ``set(stats)``/shipped-name lookup") is
therefore implemented as the whole-function value oracle of
``test_gpu_monitor_batch28_10.py``: at each frozen instant the shipped 26-key dict
is RECOMPUTED from the shipped expressions at L674-L729 and compared by equality
with the returned dict, plus the shipped-name lookups.  One assert therefore sees
every +/-1 constant, ``Add->Subtract``, ``Multiply->Divide`` (ZeroDivisionError
where ``sin == 0.0``, a value shift otherwise), every key rename, AND the prelude
sites the digit twins reach (L675 ``time_factor``, L679/L684/L690/L695).

Swept instants: ``100.0 + tf*100`` gives the manifest's tf values exactly through
the shipped ``% 100 / 100`` (L675); the three rows above 100 (108.3, 109.6,
166.3) exist because the ``% 100 -> % 101`` divisor twin at L675 has NO value
difference below 100 (``ts/101 == ts/100`` there is false in general but the
truncating ``int()`` wrappers hide it) and because out-of-range divisor mutants
only reveal themselves above 100.  The whole instant set was verified against the
shipped function by construction (this file's green leg) and its union reddens
every code-region candidate of the group.

The comment-region digit candidates
===================================
9 of this group's candidate sites are digits inside the def's comments (L677
"15-45%", L682 "2-4 GB ... 24 GB", L693 "30-80W").  They mutate nothing
executable, so the only available observable is their own TEXT, pinned from
``Path(M.__file__).read_text()`` - the module this world imported - exactly as the
already-proven sibling
``test_gpu_monitor_batch28_12.py::test_sixty_second_window_is_stated_in_docstring_and_comment``
pins its ``number:60 -> 61`` comment twin.  ``inspect.getsource``/linecache is
deliberately avoided (it can hand back a stale same-size copy).

Discipline
----------
* Shipped behaviour only.  The only seam is the ``freezegun`` clock named by the
  admitted test_spec; ``time.monotonic``/``time.perf_counter`` are never patched
  and no duration is asserted.  ``_get_gpu_stats_mock`` logs nothing, so there is
  no log window here.
* The monitor double is a REAL ``GPUMonitor`` built in the shipped no-NVML world
  (``sys.modules['pynvml'] = None`` + ``shutil.which -> None``, autospec'd); no
  module-level attribute is replaced, no import-time global spy, no
  ``scope="session"`` fixture.
* Every constant pin cites the shipped file:line it was transcribed from.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from freezegun import freeze_time

import backend.services.gpu_monitor as M

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

MOCK_GPU_NAME = "Mock GPU (Development Mode)"  # L699
MEMORY_TOTAL = 24576  # L702
PCIE_LINK_GEN = 4  # L723: "pcie_link_gen": 4,  # PCIe Gen4
PCIE_LINK_WIDTH = 16  # L724: "pcie_link_width": 16,  # x16
ENCODER_UTILIZATION = 0  # L727: "encoder_utilization": 0,  # No encoding in mock
DECODER_UTILIZATION = 0  # L728: "decoder_utilization": 0,  # No decoding in mock
BAR1_USED = 256  # L729: "bar1_used": 256,  # Typical BAR1 usage
THROTTLE_REASONS = 0  # L714
POWER_LIMIT = 230.0  # L715
SM_CLOCK_MAX = 1800  # L716
COMPUTE_PROCESSES_COUNT = 2  # L717
PCIE_REPLAY_COUNTER = 0  # L718
TEMP_SLOWDOWN_THRESHOLD = 83.0  # L719
MEMORY_CLOCK_MAX = 8501  # L722

# L675: time_factor = now.timestamp() % 100 / 100  # 0.0 to 1.0, cycling ...
L675_TIME_FACTOR = (
    "        time_factor = now.timestamp() % 100 / 100  # 0.0 to 1.0, cycling every ~100 seconds"
)
# L677: # Simulate utilization between 15-45% (typical idle to light workload)
L677_COMMENT = "# Simulate utilization between 15-45% (typical idle to light workload)"
# L682: # Simulate memory: 2-4 GB used of 24 GB total (RTX A5500 spec)
L682_COMMENT = "# Simulate memory: 2-4 GB used of 24 GB total (RTX A5500 spec)"
# L693: # Simulate power usage: 30-80W (idle to light workload)
L693_COMMENT = "# Simulate power usage: 30-80W (idle to light workload)"


def _shipped_source() -> str:
    """Text of the shipped module THIS world was built from.

    Pristine world: ``Path(M.__file__)`` verbatim.  Instrumented (mutmut-bank)
    world: ``M.__file__`` is the GENERATED file carrying every mutant copy as
    an extra def - each shipped comment appears once per copy, so a raw
    ``count == 1`` read can never be green there and would attribute a false
    kill to every key whose selection set reaches this module.  The
    instrumented file is generated verbatim from the shipped file, which sits
    at the same path minus the ``mutants/`` component (the proven ``_PRISTINE``
    recipe from the detector_client batch-28 batteries).
    """
    p = Path(M.__file__)
    parts = p.parts
    if "mutants" in parts:
        i = len(parts) - 1 - parts[::-1].index("mutants")
        p = Path(*parts[:i], *parts[i + 1 :])
    return p.read_text(encoding="utf-8")


# ts = 100.0 + tf*100 -> shipped ``time_factor`` (L675) == tf exactly; the rows
# above 100 exist so the L675 modulo-divisor twins have no fixed point.
SWEEP_SECONDS: tuple[float, ...] = (
    100.0,  # tf = 0.0   -> sin == 0.0 (ZeroDivision row for the sin divisors)
    110.0,  # tf = 0.1   -> the spec's Multiply->Divide separator row
    125.0,  # tf = 0.25  -> sin == +1.0
    175.0,  # tf = 0.75  -> sin == -1.0
    108.3,  # above the 100-second modulo
    109.6,  # above the 100-second modulo
    166.3,  # above the 100-second modulo
    250.0,  # tf = 0.5
)

# This file's own rows (group 16 owns L723-L729).
G16_FIELDS: tuple[str, ...] = (
    "pcie_link_gen",
    "pcie_link_width",
    "pcie_tx_throughput",
    "pcie_rx_throughput",
    "encoder_utilization",
    "decoder_utilization",
    "bar1_used",
)

SHIPPED_KEYS: frozenset[str] = frozenset(
    {
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
    }
)


def instant(seconds: float) -> datetime:
    """The aware UTC instant ``freeze_time`` installs for a sweep row."""
    return datetime.fromtimestamp(seconds, UTC)


def shipped_expectation(seconds: float) -> dict[str, Any]:
    """The EXACT 26-key dict shipped ``_get_gpu_stats_mock`` returns at ``seconds``.

    Transcribed line-by-line from ``backend/services/gpu_monitor.py`` L674-L729.
    ``time_factor`` is the SHIPPED L675 expression evaluated on the frozen
    instant, so the recomputation follows the shipped pipeline (including its
    ``% 100 / 100`` modulo) rather than an idealised one.  Verified equal to the
    shipped return value at every swept instant before this file was written.
    """
    now = instant(seconds)
    time_factor = now.timestamp() % 100 / 100  # L675
    gpu_utilization = round(25.0 + 10.0 * math.sin(time_factor * 2 * math.pi), 1)  # L678-L680
    memory_used = 3072 + int(512 * math.cos(time_factor * 2 * math.pi))  # L683-L685
    temperature = round(42.0 + 8.0 * math.sin(time_factor * 2 * math.pi + 0.5), 1)  # L689-L691
    power_usage = round(50.0 + 20.0 * math.sin(time_factor * 2 * math.pi + 1.0), 1)  # L694-L696
    return {
        "gpu_name": MOCK_GPU_NAME,  # L699
        "gpu_utilization": gpu_utilization,  # L700
        "memory_used": memory_used,  # L701
        "memory_total": MEMORY_TOTAL,  # L702
        "temperature": temperature,  # L703
        "power_usage": power_usage,  # L704
        "recorded_at": now,  # L705
        "fan_speed": int(30 + 10 * math.sin(time_factor * 2 * math.pi)),  # L707
        "sm_clock": int(1500 + 300 * math.sin(time_factor * 2 * math.pi)),  # L708
        "memory_bandwidth_utilization": round(  # L709-L711
            15.0 + 5.0 * math.sin(time_factor * 2 * math.pi), 1
        ),
        "pstate": 8 if gpu_utilization < 30 else 0,  # L712
        "throttle_reasons": THROTTLE_REASONS,  # L714
        "power_limit": POWER_LIMIT,  # L715
        "sm_clock_max": SM_CLOCK_MAX,  # L716
        "compute_processes_count": COMPUTE_PROCESSES_COUNT,  # L717
        "pcie_replay_counter": PCIE_REPLAY_COUNTER,  # L718
        "temp_slowdown_threshold": TEMP_SLOWDOWN_THRESHOLD,  # L719
        "memory_clock": int(8000 + 500 * math.sin(time_factor * 2 * math.pi)),  # L721
        "memory_clock_max": MEMORY_CLOCK_MAX,  # L722
        "pcie_link_gen": PCIE_LINK_GEN,  # L723
        "pcie_link_width": PCIE_LINK_WIDTH,  # L724
        "pcie_tx_throughput": int(  # L725
            100000 + 50000 * math.sin(time_factor * 2 * math.pi)
        ),
        "pcie_rx_throughput": int(  # L726
            80000 + 40000 * math.sin(time_factor * 2 * math.pi)
        ),
        "encoder_utilization": ENCODER_UTILIZATION,  # L727
        "decoder_utilization": DECODER_UTILIZATION,  # L728
        "bar1_used": BAR1_USED,  # L729
    }


@pytest.fixture
def monitor() -> Any:
    """A GPUMonitor in the shipped no-NVML world (pynvml import fails, no nvidia-smi).

    ``sys.modules['pynvml'] = None`` makes the shipped L225 ``import pynvml``
    raise ``ImportError`` and ``shutil.which -> None`` takes the L261 not-found
    arm, so the instance ends up ``_gpu_available=False`` and the mock path is
    the shipped one this battery drives.
    """
    with (
        patch.dict("sys.modules", {"pynvml": None}),
        patch("backend.services.gpu_monitor.shutil.which", return_value=None, autospec=True),
    ):
        yield M.GPUMonitor()


def value_sweep(monitor: Any, seconds: float, fields: tuple[str, ...]) -> None:
    """One frozen row: call the shipped function, then assert the FULL dict.

    ``freeze_time`` swaps the ``datetime`` name in the LIVE module dict (what the
    function's own globals resolve), so the frozen clock is the manifest-named
    seam - no ``time.*`` patch anywhere.
    """
    expected = shipped_expectation(seconds)
    with freeze_time(instant(seconds)):
        stats = monitor._get_gpu_stats_mock()
    assert isinstance(stats, dict), f"shipped function returned {type(stats)}"
    assert stats == expected, "\n".join(
        [
            f"_get_gpu_stats_mock() diverges from shipped at ts={seconds!r} "
            f"(time_factor={instant(seconds).timestamp() % 100 / 100!r}):",
            *[
                f"  {k!r}: returned {stats.get(k, '<MISSING>')!r} != shipped {expected[k]!r}"
                for k in sorted(set(stats) | set(expected))
                if stats.get(k, "<MISSING>") != expected[k]
            ],
        ]
    )
    for field in fields:
        assert field in stats, f"shipped key {field!r} is missing from the returned dict"
    assert stats["recorded_at"] == instant(seconds)
    assert stats["recorded_at"].tzinfo is UTC


# =============================================================================
# G08b2 - the swept value oracle (group_16.keys)
# =============================================================================


def test_mock_oracle_row_tf_0_0(monitor):
    """tf = 0.0: ``sin == 0.0``, so every ``sin``-operand ``Multiply->Divide``
    twin raises ZeroDivisionError - including this group's L725 x3 and L726 x3 -
    and the prelude L679/L684/L690/L695 twins are caught by the same leg."""
    value_sweep(monitor, 100.0, G16_FIELDS)


def test_mock_oracle_row_tf_0_1(monitor):
    """tf = 0.1 - the spec's separator row for ``Multiply->Divide``: shipped
    ``int(100000 + 50000*sin(0.2*pi))`` = 129389 vs the mutant
    ``int(100000 + 50000/sin(0.2*pi))`` = 185063, and the shipped
    ``int(80000 + 40000*sin(0.2*pi))`` = 123511 vs 168051."""
    with freeze_time(instant(110.0)):
        tx = monitor._get_gpu_stats_mock()["pcie_tx_throughput"]
    assert tx == 129389, "shipped L725 value at tf = 0.1 is int(100000 + 50000*sin(0.2*pi))"
    value_sweep(monitor, 110.0, G16_FIELDS)


def test_mock_oracle_row_tf_0_25(monitor):
    """tf = 0.25: ``sin == +1.0`` -> tx 150000, rx 120000; ``Add->Subtract``
    inverts both and every +/-1 amplitude constant moves by 2x its step."""
    value_sweep(monitor, 125.0, G16_FIELDS)


def test_mock_oracle_row_tf_0_75(monitor):
    """tf = 0.75: ``sin == -1.0`` -> tx 50000, rx 40000 (the mirror row that
    separates a subtract mutant which hides at +1)."""
    value_sweep(monitor, 175.0, G16_FIELDS)


def test_mock_oracle_row_108_3_above_the_modulo(monitor):
    """ts = 108.3 -> shipped tf = 0.083.  Below ts = 100 the L675
    ``% 100 -> % 101`` digit twin is value-identical through the truncating
    ``int()`` wrappers; here shipped and mutant disagree (0.083 vs 0.0825...)."""
    value_sweep(monitor, 108.3, G16_FIELDS)


def test_mock_oracle_row_109_6_above_the_modulo(monitor):
    """ts = 109.6 -> shipped tf = 0.096; also the row where the L726
    ``40000 -> 40001`` twin that hides at tf = 0.1 moves."""
    value_sweep(monitor, 109.6, G16_FIELDS)


def test_mock_oracle_row_166_3_above_the_modulo(monitor):
    """ts = 166.3 -> shipped tf = 0.663 (sin < 0), where an out-of-range
    ``time_factor`` from a broken divisor cannot be masked by rounding."""
    value_sweep(monitor, 166.3, G16_FIELDS)


def test_mock_oracle_row_tf_0_5(monitor):
    """tf = 0.5: ``sin == 0.0`` again (second ZeroDivision row) and
    ``cos == -1.0``, so ``memory_used`` sits at 2560."""
    value_sweep(monitor, 250.0, G16_FIELDS)


# =============================================================================
# G08b2 - named legs for the L723-L729 rows
# =============================================================================


def test_pcie_link_gen_and_width_are_the_shipped_mock_constants(monitor):
    """L723 ``"pcie_link_gen": 4`` and L724 ``"pcie_link_width": 16``: time-
    independent constants, asserted at the two extreme rows of the sweep so a
    value leg can never be satisfied by a rounding accident."""
    for seconds in (100.0, 125.0, 175.0):
        with freeze_time(instant(seconds)):
            stats = monitor._get_gpu_stats_mock()
        assert stats["pcie_link_gen"] == PCIE_LINK_GEN
        assert stats["pcie_link_width"] == PCIE_LINK_WIDTH


def test_encoder_decoder_and_bar1_are_the_shipped_mock_constants(monitor):
    """L727 ``"encoder_utilization": 0``, L728 ``"decoder_utilization": 0`` and
    L729 ``"bar1_used": 256`` (the ``0 -> 1`` pair and the ``256 -> 257`` step).
    L727/L728 are also the two rows whose ``0`` token repeats 25 times inside the
    def - the value oracle above is what proves every one of those sites."""
    for seconds in (100.0, 110.0, 250.0):
        with freeze_time(instant(seconds)):
            stats = monitor._get_gpu_stats_mock()
        assert stats["encoder_utilization"] == ENCODER_UTILIZATION
        assert stats["decoder_utilization"] == DECODER_UTILIZATION
        assert stats["bar1_used"] == BAR1_USED


def test_tx_and_rx_throughputs_recompute_from_the_shipped_sin(monitor):
    """L725/L726 at three rows: the shipped expressions
    ``int(100000 + 50000 * sin(tf * 2 * pi))`` / ``int(80000 + 40000 * ...)``
    recomputed inline, so the constant/amplitude mutants have nowhere to hide."""
    for seconds in (100.0, 110.0, 125.0, 175.0):
        now = instant(seconds)
        time_factor = now.timestamp() % 100 / 100  # L675
        tx = int(100000 + 50000 * math.sin(time_factor * 2 * math.pi))  # L725
        rx = int(80000 + 40000 * math.sin(time_factor * 2 * math.pi))  # L726
        with freeze_time(now):
            stats = monitor._get_gpu_stats_mock()
        assert stats["pcie_tx_throughput"] == tx
        assert stats["pcie_rx_throughput"] == rx


def test_returned_key_set_is_the_shipped_25_name_set(monitor):
    """The shipped 26 keys in the shipped names (L699-L729).  A key
    ``wrapXX``/``upper`` mutant of this group removes one shipped name and adds a
    renamed one, so both legs below fail for each of the 12 key mutants."""
    with freeze_time(instant(110.0)):
        stats = monitor._get_gpu_stats_mock()
    assert set(stats) == SHIPPED_KEYS
    assert len(SHIPPED_KEYS) == 26  # the shipped return dict carries 26 names (L699-L729)
    assert len(stats) == 26


def test_the_inert_digit_comment_lines_are_verbatim_in_the_imported_source():
    """The comment-region digit candidates of this group - L677 (``4`` of
    ``number:4->5``), L682 (the ``2``/``4``/``24``/``500`` occurrences inside
    ``number:2->3``/``0->1``/``4->5``) and L693 (the ``30``/``0`` occurrences of
    ``number:0->1``).  They mutate nothing executable; their only observable is
    their own text in the module this world imported."""
    module_source = _shipped_source()
    assert L675_TIME_FACTOR in module_source, (
        "the shipped L675 time_factor assignment is not verbatim in the "
        "shipped source of the imported module"
    )
    assert module_source.count(L677_COMMENT) == 1, (
        "the shipped L677 comment is not present exactly once in the shipped "
        "source of the imported module"
    )
    assert module_source.count(L682_COMMENT) == 1, (
        "the shipped L682 comment is not present exactly once in the shipped "
        "source of the imported module"
    )
    assert module_source.count(L693_COMMENT) == 1, (
        "the shipped L693 comment is not present exactly once in the shipped "
        "source of the imported module"
    )
