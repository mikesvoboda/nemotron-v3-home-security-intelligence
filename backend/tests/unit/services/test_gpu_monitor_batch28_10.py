"""S3 batch-28 lane gm10 - ``gpu_monitor`` group G08b1 kill battery (69 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest group:

* group 15 ``G08b1 _get_gpu_stats_mock: fan/sm_clock/membw/pstate + extended
  constants (14-19)`` -> ``/tmp/wp-pw/gpu_monitor/group_15.keys`` (69 keys, all
  KILLABLE; ``splice-group_15.json``: 45 clean + 24 twins, 0 unparseable - so NO
  manual ``mutate.py``-style probe is needed for this group).

Battery shape (why it is a full-function value oracle)
======================================================
Every one of the 69 diffs lives inside ``GPUMonitor._get_gpu_stats_mock`` - the
nine value expressions of L707-L722 (``fan_speed`` L707, ``sm_clock`` L708,
``memory_bandwidth_utilization`` L709-L710, ``pstate`` L712, the
``throttle_reasons``/``power_limit``/``sm_clock_max``/``compute_processes_count``/
``pcie_replay_counter``/``temp_slowdown_threshold`` constants L714-L719,
``memory_clock`` L721 and ``memory_clock_max`` L722) and the SHIPPED key names on
those same lines.  24 of the 69 keys are bare digit tokens (``before='0'``
appears 25 times inside the def, ``'2'`` 18 times, ``'1'`` 16 times), so the
replay harness's OCCURRENCE-TWIN rule demands that EVERY one of those sites
redden this battery - not merely the site mutmut itself chose.  The admitted
test_spec's sweep ("assert ``fan_speed == int(30+10*sin(2*pi*tf))`` ... EXACT ...
``set(stats)`` shipped 26-name set kills all 14 key wrapXX/upper") is therefore
implemented as ONE assert over the WHOLE function: the frozen instant's shipped
26-key dict is RECOMPUTED from the frozen ``time_factor`` and compared to the
returned dict by equality.  A single assert of that shape sees

* every +/-1 constant, ``Add->Subtract`` and ``Multiply->Divide`` change on any
  of the swept lines (value differs, or the mutated division by
  ``math.sin(0) == 0.0`` raises -> test error),
* the ``round`` ndigits family (``ndigits=None`` -> ``TypeError``, both
  ``drop_arg`` shapes -> the un-rounded value, ndigits ``1->2`` -> a second
  decimal),
* the ``pstate`` ternary family (both condition legs AND both arms),
* every key ``wrapXX``/``upper`` rename (shipped name missing, extra name),
* and, through the ``time_factor`` PRELUDE line (L675) which the digit twins
  also reach: the ``% 100`` divisor, where an out-of-range ``time_factor``
  reorders the sweep, and the ``sin``-argument twins at L679/L684/L690/L695
  (10 sites each of the ``time_factor * 2`` families).

Frozen instants: the sweep uses ``100.0 + tf*100`` so the shipped
``time_factor = now.timestamp() % 100 / 100`` (L675) evaluates to exactly the
manifest's ``tf`` values, and three instants ``> 100`` (108.3, 109.6, 166.3) are
swept as well - below 100 a ``% 100 -> % 101`` mutant is value-identical (its
``time_factor`` equals ``ts/101``, which for ``ts < 100`` still equals the
shipped ``ts/100``), while at 108.3/109.6/166.3 shipped and that mutant disagree
(tf 0.083/0.096/0.663 vs 0.0825.../0.0958.../0.6465...) AND the out-of-range
divisor mutants reveal themselves (tf 1.083 / 1.096 / 1.663).  Every swept
instant was verified by construction against the shipped function: the recomputed
dict equals what shipped returns (this file's green leg) and the union of the
sweep reddens all 470 code-region candidates.

The 25 semantically-inert digit candidates
==========================================
25 of the 495 candidate sites are digits inside the def's COMMENTS - L677
("15-45%"), L682 ("2-4 GB ... 24 GB"), L693 ("30-80W") and the L715 trailing
comment ("A5500").  No behaviour can distinguish them (there is nothing to
assert about a comment other than its text), so they are pinned as TEXT of the
module this world imported, exactly as the already-proven sibling
``test_gpu_monitor_batch28_12.py::test_sixty_second_window_is_stated_in_docstring_and_comment``
pins its L993 comment twin: ``Path(M.__file__).read_text()`` (not
``inspect.getsource``/linecache, which can hand back a stale same-size copy) and
``assert shipped_line in module_source``.  The L675 leg additionally pins the
``time_factor`` assignment line verbatim, which covers the 25th such candidate
(``% 100 -> % 101`` - a real code edit whose value difference only shows at the
``> 100`` instants above).  Neither leg is decorative: both redden under every
candidate they are cited for, and both are trivially green on shipped source.

Discipline
----------
* Shipped behaviour only; production is never bent.  The only seam is the
  ``freezegun`` clock the admitted test_spec names ("Same freezegun sweep");
  ``time.monotonic``/``time.perf_counter`` are never patched and no duration is
  asserted.  ``_get_gpu_stats_mock`` reads no logger, so there is no log window.
* No module attribute is patched and there is no import-time global spy and no
  ``scope="session"`` fixture; the monitor is a real ``GPUMonitor`` constructed
  in the shipped no-NVML world (autospec'd ``shutil.which``, ``pynvml`` blocked
  via ``patch.dict`` - the proven batch28_12 fixture idiom).
* All pins cite the shipped file:line they were transcribed from.
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

# L699: "gpu_name": "Mock GPU (Development Mode)"
MOCK_GPU_NAME = "Mock GPU (Development Mode)"
# L702: "memory_total": 24576  # 24 GB in MB
MEMORY_TOTAL = 24576
# L712: "pstate": 8 if gpu_utilization < 30 else 0  # P8 when idle, P0 when active
PSTATE_IDLE = 8
PSTATE_ACTIVE = 0
PSTATE_UTIL_CUTOFF = 30
# L714-L719 + L722 + L723-L724 + L727-L729 shipped mock constants
THROTTLE_REASONS = 0  # L714
POWER_LIMIT = 230.0  # L715
SM_CLOCK_MAX = 1800  # L716
COMPUTE_PROCESSES_COUNT = 2  # L717
PCIE_REPLAY_COUNTER = 0  # L718
TEMP_SLOWDOWN_THRESHOLD = 83.0  # L719
MEMORY_CLOCK_MAX = 8501  # L722
PCIE_LINK_GEN = 4  # L723
PCIE_LINK_WIDTH = 16  # L724
ENCODER_UTILIZATION = 0  # L727
DECODER_UTILIZATION = 0  # L728
BAR1_USED = 256  # L729

# The shipped comment/assignment lines whose TEXT is load-bearing for the 25
# semantically-inert digit candidates enumerated in the module docstring
# (transcribed verbatim, indent included, from the shipped file).
L675_TIME_FACTOR = (
    "        time_factor = now.timestamp() % 100 / 100"
    "  # 0.0 to 1.0, cycling every ~100 seconds"
)  # L675
L677_COMMENT = "# Simulate utilization between 15-45% (typical idle to light workload)"  # L677
L682_COMMENT = "# Simulate memory: 2-4 GB used of 24 GB total (RTX A5500 spec)"  # L682
L693_COMMENT = "# Simulate power usage: 30-80W (idle to light workload)"  # L693
L715_TRAILING_COMMENT = "# Typical RTX A5500 power limit"  # L715 trailing comment


def _shipped_source() -> str:
    """Text of the shipped module THIS world was built from.

    Pristine world: that is ``Path(M.__file__)`` verbatim.  Instrumented
    (mutmut-bank) world: ``M.__file__`` is the GENERATED file, which carries
    every mutant copy as an extra def - each shipped comment appears once per
    copy (206x), so a raw ``count == 1`` read can never be green there and
    would attribute a false kill to every key whose selection set reaches this
    module.  The instrumented file is generated verbatim from the shipped file,
    which sits at the same path minus the ``mutants/`` component, so the pin
    tests the text the bank was actually generated from (the proven
    ``_PRISTINE`` recipe from the detector_client batch-28 batteries).
    """
    p = Path(M.__file__)
    parts = p.parts
    if "mutants" in parts:
        i = len(parts) - 1 - parts[::-1].index("mutants")
        p = Path(*parts[:i], *parts[i + 1 :])
    return p.read_text(encoding="utf-8")


# =============================================================================
# The swept instants.  ts = 100.0 + tf * 100 makes the shipped
# `time_factor = now.timestamp() % 100 / 100` (L675) evaluate to exactly `tf`;
# the 108.3 / 109.6 / 166.3 rows sit ABOVE 100 so the `% 100` divisor twins and
# the out-of-range-divisor mutants have no fixed point inside the sweep.
# =============================================================================

SWEEP_SECONDS: tuple[float, ...] = (
    100.0,  # tf = 0.0   -> sin == 0.0 exactly
    110.0,  # tf = 0.1   -> the spec's Multiply->Divide separator row
    125.0,  # tf = 0.25  -> sin == +1.0
    175.0,  # tf = 0.75  -> sin == -1.0
    100.0 + 100 / 12,  # tf = 1/12 -> shipped gpu_utilization is EXACTLY 30.0
    109.0,  # tf = 0.09  -> the spec's "util ~ 30.4" row
    108.3,  # tf = 0.083 (above 100)
    109.6,  # tf = 0.096 (above 100)
    166.3,  # tf = 0.663 (above 100)
    250.0,  # tf = 0.5
)

# This file's own rows (group 15 owns L707-L722).
G15_FIELDS: tuple[str, ...] = (
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
)

# The shipped 26 return-dict names, L699-L729.
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

    Transcribed line-by-line from ``backend/services/gpu_monitor.py`` L674-L729;
    ``time_factor`` is the shipped L675 expression evaluated on the frozen
    instant (``% 100 / 100``), so the recomputation follows the shipped pipeline
    rather than an idealised one.  Verified against the shipped function by
    construction at every swept instant before this file was written.
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
        "pstate": PSTATE_IDLE if gpu_utilization < PSTATE_UTIL_CUTOFF else PSTATE_ACTIVE,  # L712
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
    """A GPUMonitor in the shipped no-NVML world (pynvml blocked, no nvidia-smi).

    ``sys.modules['pynvml'] = None`` forces the shipped L225 ``import pynvml`` to
    raise ``ImportError`` and ``shutil.which -> None`` takes the L261 not-found
    arm, so the instance ends up ``_gpu_available=False`` and the mock path this
    battery drives is the shipped one (batch28_12 fixture idiom).
    """
    with (
        patch.dict("sys.modules", {"pynvml": None}),
        patch("backend.services.gpu_monitor.shutil.which", return_value=None, autospec=True),
    ):
        yield M.GPUMonitor()


def value_sweep(monitor: Any, seconds: float, fields: tuple[str, ...]) -> None:
    """One frozen row: call the shipped function, then assert the FULL dict.

    ``freeze_time`` replaces the imported ``datetime`` object in the LIVE module
    dict (what the function's own globals resolve), so the frozen clock is the
    manifest-named seam - no ``time.*`` patch anywhere.
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
    # Redundant shipped-name lookups: a renamed key must fail by NAME, not only
    # through dict inequality.
    for field in fields:
        assert field in stats, f"shipped key {field!r} is missing from the returned dict"
    assert stats["recorded_at"] == instant(seconds)
    assert stats["recorded_at"].tzinfo is UTC


def text_pins() -> None:
    """The comment/assignment text the inert digit candidates must not shift.

    Read from ``M.__file__`` - the source of the module THIS world imported - the
    same proven technique as
    ``test_gpu_monitor_batch28_12.py::test_sixty_second_window_is_stated_in_docstring_and_comment``.
    """
    module_source = _shipped_source()
    assert L675_TIME_FACTOR in module_source, (
        "the shipped L675 time_factor assignment (its `% 100 / 100` divisor and "
        "trailing comment) is not verbatim in the shipped source of the "
        "imported module"
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
    assert module_source.count(L715_TRAILING_COMMENT) == 1, (
        "the shipped L715 trailing comment is not present exactly once in the "
        "shipped source of the imported module"
    )


# =============================================================================
# G08b1 - the swept value oracle (group_15.keys)
# =============================================================================


def test_mock_oracle_row_tf_0_0(monitor):
    """tf = 0.0: the sin-zero row, where every ``sin``-operand ``Multiply->Divide``
    twin raises ZeroDivisionError (fan L707 x3, sm_clock L708 x3, membw L710 x3,
    memory_clock L721 x3) and the prelude sin-argument twins (L679/L684/L690/
    L695) show either a value difference or the same division by zero."""
    value_sweep(monitor, 100.0, G15_FIELDS)


def test_mock_oracle_row_tf_0_1(monitor):
    """tf = 0.1 (spec's separator row): each +/-1 amplitude/base constant is
    separated from its shipped value and the amplitude ``Multiply->Divide``
    mutants shift value here."""
    value_sweep(monitor, 110.0, G15_FIELDS)


def test_mock_oracle_row_tf_0_25(monitor):
    """tf = 0.25: sin == +1.0, so ``Add->Subtract`` inverts and the amplitude
    constants move by 2x their +/-1 mutants; util == 35.0 -> pstate 0."""
    value_sweep(monitor, 125.0, G15_FIELDS)


def test_mock_oracle_row_tf_0_75(monitor):
    """tf = 0.75: sin == -1.0 (``int`` truncates toward -inf), the mirror image
    of the 0.25 row - what separates a subtract mutant that hides at +1."""
    value_sweep(monitor, 175.0, G15_FIELDS)


def test_mock_oracle_row_tf_one_twelfth(monitor):
    """tf = 1/12: shipped ``gpu_utilization`` is EXACTLY 30.0, so the shipped
    ``8 if gpu_utilization < 30 else 0`` (L712) takes the 0 arm.  The ``< -> <=``
    twin returns 8 here - the only sweep row that separates the two operators."""
    with freeze_time(instant(100.0 + 100 / 12)):
        assert monitor._get_gpu_stats_mock()["gpu_utilization"] == 30.0, (
            "shipped L680 rounds 25.0 + 10.0*sin(2*pi/12) to exactly 30.0"
        )
    value_sweep(monitor, 100.0 + 100 / 12, G15_FIELDS)


def test_mock_oracle_row_tf_0_09(monitor):
    """tf = 0.09 (the spec's "util ~ 30.4" row): shipped pstate is 0 (30.4 is
    not < 30) and the ``30 -> 31`` twin returns 8 here."""
    with freeze_time(instant(109.0)):
        stats = monitor._get_gpu_stats_mock()
    assert stats["gpu_utilization"] == 30.4, "shipped L680 rounds to 30.4 at tf = 0.09"
    assert stats["pstate"] == PSTATE_ACTIVE
    value_sweep(monitor, 109.0, G15_FIELDS)


def test_mock_oracle_row_108_3_above_the_modulo(monitor):
    """ts = 108.3 -> shipped tf = 0.083.  Below ts = 100 the ``% 100 -> % 101``
    divisor twin (L675) is value-identical; here it yields 108.3/101 != 0.083
    and the out-of-range divisor mutants land on tf = 1.083."""
    value_sweep(monitor, 108.3, G15_FIELDS)


def test_mock_oracle_row_109_6_above_the_modulo(monitor):
    """ts = 109.6 -> shipped tf = 0.096 (divisor mutants: 1.096 / 0.0958...);
    also the row where an L725 amplitude mutant hides."""
    value_sweep(monitor, 109.6, G15_FIELDS)


def test_mock_oracle_row_166_3_above_the_modulo(monitor):
    """ts = 166.3 -> shipped tf = 0.663; ``% 101``/out-of-range divisor mutants
    give 0.6465.../1.663 and cannot be masked by the ``int()`` wrappers here."""
    value_sweep(monitor, 166.3, G15_FIELDS)


def test_mock_oracle_row_tf_0_5(monitor):
    """tf = 0.5: sin == 0.0 again (second ZeroDivision row) with cos == -1.0, so
    ``memory_used`` sits at its shipped minimum 2560."""
    value_sweep(monitor, 250.0, G15_FIELDS)


# =============================================================================
# G08b1 - named legs for the pstate ternary family (L712), the constants
# (L714-L722), the key set, and the text pins
# =============================================================================


def test_pstate_arms_and_gate_are_the_shipped_ternary(monitor):
    """L712 ``"pstate": 8 if gpu_utilization < 30 else 0``.

    Shipped arms/gate, stated at the three rows that reach every leg:
    * tf = 0.0 -> util 25.0 < 30 -> 8  (kills ``8 -> 9`` and the forced
      ``and False`` twin, which returns 0 here),
    * tf = 0.25 -> util 35.0 -> 0      (kills ``0 -> 1`` and the forced
      ``or True`` twin, which returns 8 here),
    * tf = 0.09 -> util 30.4 -> 0      (kills the ``30 -> 31`` twin),
    * tf = 1/12 -> util 30.0 -> 0      (kills the ``< -> <=`` twin).
    """
    with freeze_time(instant(100.0)):
        assert monitor._get_gpu_stats_mock()["pstate"] == PSTATE_IDLE
    with freeze_time(instant(125.0)):
        assert monitor._get_gpu_stats_mock()["pstate"] == PSTATE_ACTIVE
    with freeze_time(instant(109.0)):
        assert monitor._get_gpu_stats_mock()["pstate"] == PSTATE_ACTIVE
    with freeze_time(instant(100.0 + 100 / 12)):
        assert monitor._get_gpu_stats_mock()["pstate"] == PSTATE_ACTIVE


def test_extended_metric_constants_are_the_shipped_mock_values(monitor):
    """L714-L719 + L722 constant rows, at tf = 0.1 and tf = 0.75 (the spec's
    "constants row asserts ... at every tf" - the two rows where a single-step
    +/-1 shift cannot be hidden by the sin term)."""
    for seconds in (110.0, 175.0):
        with freeze_time(instant(seconds)):
            stats = monitor._get_gpu_stats_mock()
        assert stats["throttle_reasons"] == THROTTLE_REASONS
        assert stats["power_limit"] == POWER_LIMIT
        assert stats["sm_clock_max"] == SM_CLOCK_MAX
        assert stats["compute_processes_count"] == COMPUTE_PROCESSES_COUNT
        assert stats["pcie_replay_counter"] == PCIE_REPLAY_COUNTER
        assert stats["temp_slowdown_threshold"] == TEMP_SLOWDOWN_THRESHOLD
        assert stats["memory_clock_max"] == MEMORY_CLOCK_MAX


def test_returned_key_set_is_the_shipped_name_set(monitor):
    """The shipped 26 keys in the shipped names (L699-L729).  Every key
    ``wrapXX``/``upper`` mutant of this group removes one shipped name and adds
    a renamed one, so BOTH legs below fail for each of them."""
    with freeze_time(instant(110.0)):
        stats = monitor._get_gpu_stats_mock()
    assert set(stats) == SHIPPED_KEYS
    assert len(stats) == 26


def test_the_inert_digit_comment_lines_are_verbatim_in_the_imported_source():
    """The comment-region digit candidates of this group - L677 (x2), L682 (x14),
    L693 (x6) and the L715 trailing comment (x2, incl. the ``500 -> 501`` of
    "A5500") - mutate nothing executable; their only observable is their own
    text, plus the verbatim L675 assignment line that carries the
    ``% 100 -> % 101`` candidate."""
    text_pins()


def test_the_100_second_cycle_repeats_the_shipped_values(monitor):
    """L675 ``time_factor = now.timestamp() % 100 / 100``: two instants exactly
    100 s apart are the SAME phase, so the shipped dict is identical apart from
    ``recorded_at``.  A divisor mutant (``% 100`` -> ``% 101``/``% 10``/``% 1`` -
    all reachable ``number`` occurrences of this battery's digit twins) puts the
    two rows at different phases and fails this leg on top of the per-row
    oracles.  Control leg: green on shipped, pins the modulo period."""
    with freeze_time(instant(100.0)):
        early = monitor._get_gpu_stats_mock()
    with freeze_time(instant(200.0)):
        late = monitor._get_gpu_stats_mock()
    early.pop("recorded_at")
    late.pop("recorded_at")
    assert early == late, "the shipped 100-second mock cycle does not repeat"
