"""S3 batch-28 lane gm02 - ``gpu_monitor`` groups G02b + G02c kill battery (54 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 ``2f122c85a072b7bd00c2e4b36cdc1cda``
- byte-identical to the manifest-proven source). Admitted manifest
``/tmp/wp-pw/gpu_monitor/manifest.json`` groups ``G02b`` (``group_5.keys``, 12 keys)
and ``G02c`` (``group_6.keys``, 42 keys), both KILLABLE, plus ``survivors.json``
for the exact per-key diffs. No unparseable key and no EQUIVALENT key sits in
either group (``splice-group_5.json`` -> 10 twin / 2 clean, 0 bad;
``splice-group_6.json`` -> 42 clean, 0 bad).

Subject: ``GPUMonitor._get_gpu_stats_nvidia_smi`` - the CSV field-index twins at
L309/L314/L319/L324/L329, the ``gpu_name`` fallback gate at L333, the 26-key
identity of the returned dict (L342-L364), the ``recorded_at`` timezone and the
two exception re-wraps (L367-L370).

Test -> mutant-key map (every key is in ``group_5.keys`` or ``group_6.keys``;
``s`` = the sync function's survivor number, i.e. the ``__mutmut_`` suffix)
==========================================================================
- ``s45`` / ``s46``  L309 ``parts[0]`` -> ``parts[1]`` (value twin + guard twin)
  -> ``test_six_field_row_maps_the_positional_sextuple`` (value leg: temperature
     20.0 != 10.0) and ``test_slot_before_a_blank_neighbour_keeps_its_own_value[slot0-blank-after]``
     (both legs: shipped 10.0 vs a mutant None), and - because these two keys are
     NUMBER twins whose candidate set also spans ``result.returncode != 0``
     (L297) and ``.split("\\n")[0]`` (L301) - ``test_six_field_row_maps...`` and
     ``test_nonzero_returncode_raises_the_wrapped_stderr_message`` (L297 leg) and
     ``test_multiline_output_parses_the_first_gpu_row`` (L301 leg).
- ``s56`` / ``s57``  L314 ``parts[1]`` -> ``parts[2]``; the same key's candidate
  set also spans L364 ``"bar1_used": None`` -> ``2``
  -> ``test_six_field_row_maps...``, ``test_slot_before_a_blank_neighbour...[slot1-blank-after]``
  and ``test_return_dict_carries_the_shipped_twenty_six_keys`` (None-valued leg).
- ``s67`` / ``s68``  L319 ``parts[2]`` -> ``parts[3]``
  -> ``test_six_field_row_maps...`` (value leg) and
  ``test_slot_before_a_blank_neighbour...[slot2-blank-after]`` (both legs - the
  guard twin agrees with shipped on the all-numeric row, so the blank-successor
  row is what separates it)
- ``s79`` / ``s80``  L324 ``parts[3]`` -> ``parts[4]``
  -> ``test_six_field_row_maps...``, ``test_slot_before_a_blank_neighbour...[slot3-blank-after]``
- ``s91`` / ``s92``  L329 ``parts[4]`` -> ``parts[5]``
  -> ``test_six_field_row_maps...`` (value leg: ValueError -> None where shipped is
  50) and ``test_slot_before_a_blank_neighbour...[slot4-no-slot-after]`` (both legs
  read the non-existent slot 5 -> IndexError -> RuntimeError instead of a dict)
- ``s98`` L333 ternary forced-then / ``s100`` L333 ``> 5`` -> ``>= 5``
  -> ``test_exactly_five_fields_falls_back_to_the_nvml_gpu_name`` (shipped 5-field
     row returns the dict with the fallback name; BOTH mutants evaluate
     ``parts[5]`` -> IndexError -> RuntimeError) and ``test_six_field_row_maps...``
     (the fallback-off leg: ``gpu_name == "Sixty"``).
- ``s114``/``s115``/``s117``...``s154`` (all 40 L342-L364 ``string:wrapXX`` /
  ``string:upper`` key renames) -> ``test_return_dict_carries_the_shipped_twenty_six_keys``
  (a renamed entry breaks set equality and the shipped-name lookup).
- ``s116`` L342 ``datetime.now(UTC)`` -> ``datetime.now(None)``
  -> ``test_recorded_at_is_utc_aware``.
- ``s156`` L368 ``"nvidia-smi timed out"`` wrapXX
  -> ``test_timeout_expired_becomes_the_bare_timeout_runtimeerror`` (full-string
     equality plus the ``__cause__`` identity).

Control legs that kill nothing of their own
-------------------------------------------
``test_four_field_row_raises_the_unexpected_format_runtimeerror`` pins the L304
gate that keeps a 4-field row OUT of the indexing block the twin keys mutate (an
``IndexError`` path - without it a reader could not tell the sextuple legs from a
crash leg), ``test_oserror_becomes_the_wrapped_failed_runtimeerror`` pins the
L369-L370 wrapper that the ``gpu_name``-gate mutants escape through, and
``test_module_exposes_the_function_under_mutation`` names the callable the 54 keys
mutate.

Discipline
----------
* Only shipped behaviour is asserted; production is never bent. Every pinned
  string/value is transcribed from the shipped file with a ``file:line`` comment
  at the assert, and every value an assertion depends on is injected here (the
  CSV row, the fallback name, the fake ``CompletedProcess``).
* pynvml is never touched - these keys live in the nvidia-smi path, so the only
  double is the subprocess boundary (``subprocess.run`` with ``autospec=True``).
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted; the only clock observation is the shipped ``recorded_at`` tzinfo.
* No import-time global spy: every patch is installed per test via a context
  manager, and the monitor is built with ``GPUMonitor.__new__`` plus explicit
  attribute seeding (the ``test_gpu_monitor.py`` nvidia-smi idiom), so no module
  global is written anywhere.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.services import gpu_monitor as M
from backend.services.gpu_monitor import GPUMonitor

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L298: raise RuntimeError(f"nvidia-smi returned error: {result.stderr.strip()}")
INNER_ERROR_PREFIX = "nvidia-smi returned error: "
# L305: raise RuntimeError(f"Unexpected nvidia-smi output format: {line}")
INNER_FORMAT_PREFIX = "Unexpected nvidia-smi output format: "
# L368: raise RuntimeError("nvidia-smi timed out") from e
TIMEOUT_MSG = "nvidia-smi timed out"
# L370: raise RuntimeError(f"Failed to get GPU stats via nvidia-smi: {e}") from e
WRAP_PREFIX = "Failed to get GPU stats via nvidia-smi: "

SMI_PATH = "/usr/bin/nvidia-smi"
# L333: gpu_name = parts[5] if len(parts) > 5 else self._gpu_name
FALLBACK_NAME = "Fallback RTX A5500"

# L309-L329 read the CSV slots positionally and L333 reads slot 5, so every slot
# of a successful row is distinct - a one-slot shift then changes >= 2 fields.
SIX_ROW = "10, 20, 30, 40, 50, Sixty"

# L335-L365: the shipped return dict's 26 keys, in shipped order.
SHIPPED_KEYS = (
    # L336-L342
    "gpu_name",
    "gpu_utilization",
    "memory_used",
    "memory_total",
    "temperature",
    "power_usage",
    "recorded_at",
    # L344-L347 extended metrics (not available via the basic nvidia-smi query)
    "fan_speed",
    "sm_clock",
    "memory_bandwidth_utilization",
    "pstate",
    # L349-L354 high-value metrics
    "throttle_reasons",
    "power_limit",
    "sm_clock_max",
    "compute_processes_count",
    "pcie_replay_counter",
    "temp_slowdown_threshold",
    # L356-L364 medium-value metrics
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

# The 19 L344-L364 entries the basic nvidia-smi query cannot supply: shipped None.
NONE_KEYS = SHIPPED_KEYS[7:]

# (target-slot, row) where the slot AFTER the target is blank - except slot 4,
# whose row simply has no slot 5 at all.  This is the input family that separates
# the guard twins from shipped: shipped reads parts[i]'s own truthiness, while the
# guard mutant asks parts[i+1] (blank here -> falsy, or missing -> IndexError), so
# shipped still yields the number and the mutant yields None / raises.
BLANK_NEIGHBOUR_ROWS = (
    pytest.param(0, "10,  , 30, 40, 50, Sixty", id="slot0-blank-after"),
    pytest.param(1, "10, 20,  , 40, 50, Sixty", id="slot1-blank-after"),
    pytest.param(2, "10, 20, 30,  , 50, Sixty", id="slot2-blank-after"),
    pytest.param(3, "10, 20, 30, 40,  , Sixty", id="slot3-blank-after"),
    pytest.param(4, "10, 20, 30, 40, 50", id="slot4-no-slot-after"),
)

# Same family with nvidia-smi's ``[N/A]`` sentinel in the NEXT slot.  The third
# AST position of the index constant is the guard's compare LEFT side
# (``parts[i] != "[N/A]"``); shifted one slot it compares the NEIGHBOUR against the
# sentinel, so the mutant takes the else arm where shipped parses the number.  A
# blank neighbour cannot reveal that position (the truthiness leg short-circuits
# before the compare is evaluated) and an all-distinct row cannot either.
NA_NEIGHBOUR_ROWS = (
    pytest.param(0, "10, [N/A], 30, 40, 50, Sixty", id="slot0-na-after"),
    pytest.param(1, "10, 20, [N/A], 40, 50, Sixty", id="slot1-na-after"),
    pytest.param(2, "10, 20, 30, [N/A], 50, Sixty", id="slot2-na-after"),
    pytest.param(3, "10, 20, 30, 40, [N/A], Sixty", id="slot3-na-after"),
    pytest.param(4, "10, 20, 30, 40, 50, [N/A]", id="slot4-na-name-slot"),
)

# L333 takes parts[5] verbatim - the sentinel is NOT filtered on the name slot.
NA_SENTINEL = "[N/A]"

FIELD_NAMES = ("temperature", "power_usage", "gpu_utilization", "memory_used", "memory_total")
# The parsed value of each numeric slot of the rows above (L324/L329 parse through
# int(float(...)), so the memory slots are ints).
SLOT_VALUES = {0: 10.0, 1: 20.0, 2: 30.0, 3: 40, 4: 50}
# L333 takes parts[5] verbatim, sentinel included - the shipped row below keeps it.
NA_SENTINEL = "[N/A]"


def make_monitor() -> GPUMonitor:
    """A GPUMonitor wired for the nvidia-smi fallback path only.

    The shipped guard reads ``_nvidia_smi_available`` / ``_nvidia_smi_path``
    (L278) and the name fallback reads ``_gpu_name`` (L333); nothing else on the
    ``_get_gpu_stats_nvidia_smi`` path touches instance state, so the object is
    built without running ``__init__`` (which would probe real NVML/nvidia-smi).
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = SMI_PATH
    monitor._gpu_name = FALLBACK_NAME
    return monitor


def completed(stdout: str, stderr: str = "", returncode: int = 0) -> Any:
    """A stand-in for ``subprocess.CompletedProcess`` (the shipped L285 result)."""
    result = MagicMock(name="completed-process")
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def run_stats(stdout: str) -> dict:
    """Drive ``_get_gpu_stats_nvidia_smi`` over one canned successful nvidia-smi row."""
    monitor = make_monitor()
    with patch("subprocess.run", autospec=True, return_value=completed(stdout)):
        return monitor._get_gpu_stats_nvidia_smi()


# =============================================================================
# G02b: positional sextuple (L309/L314/L319/L324/L329) + gpu_name gate (L333)
# =============================================================================


def test_six_field_row_maps_the_positional_sextuple() -> None:
    """Six-field row -> each CSV slot lands in its own shipped field.

    Given: nvidia-smi exits 0 with "10, 20, 30, 40, 50, Sixty" (every slot distinct)
    When: _get_gpu_stats_nvidia_smi() parses the row
    Then: temperature 10.0, power_usage 20.0, gpu_utilization 30.0, memory_used 40,
        memory_total 50 and gpu_name "Sixty" - the EXACT positional sextuple

    Kills s45/s46 (L309), s56/s57 (L314), s67/s68 (L319), s79/s80 (L324) and
    s91/s92 (L329) on their value twins - a one-slot shift rewrites at least two
    fields for ANY row.  It also kills the L297 ``!= 0`` -> ``!= 1`` twin
    candidate of s45/s46 (a zero-exit row would take the "returned error" raise
    instead of returning), the L301 ``[0]`` -> ``[1]`` candidate (a one-line row
    has no index 1 -> IndexError) and s98's forced-then arm (fallback OFF).
    """
    stats = run_stats(SIX_ROW)

    # L309: temperature = float(parts[0]) if parts[0] and parts[0] != "[N/A]" else None
    assert stats["temperature"] == 10.0
    # L314: power_usage = float(parts[1]) ...
    assert stats["power_usage"] == 20.0
    # L319: gpu_utilization = float(parts[2]) ...
    assert stats["gpu_utilization"] == 30.0
    # L324: memory_used = int(float(parts[3])) ...
    assert stats["memory_used"] == 40
    # L329: memory_total = int(float(parts[4])) ...
    assert stats["memory_total"] == 50
    # L333: gpu_name = parts[5] if len(parts) > 5 else self._gpu_name
    assert stats["gpu_name"] == "Sixty"
    assert stats["gpu_name"] != FALLBACK_NAME


@pytest.mark.parametrize(("slot", "row"), BLANK_NEIGHBOUR_ROWS)
def test_slot_before_a_blank_neighbour_keeps_its_own_value(slot: int, row: str) -> None:
    """A numeric slot is parsed from itself even when the NEXT slot is blank.

    Given: a row whose slot `slot` carries a number and whose slot ``slot + 1`` is
        blank (nvidia-smi prints an empty field for an unreadable sensor), with no
        slot 5 at all in the slot-4 case
    When: _get_gpu_stats_nvidia_smi() parses the row
    Then: the target field holds its own number, the blank neighbour is None and
        every earlier field is untouched

    Kills BOTH twins of each index pair.  The VALUE twin reads ``parts[i+1]``
    (blank -> ValueError -> None, or missing -> IndexError -> RuntimeError) where
    shipped returns the number.  The GUARD twin tests the truthiness of
    ``parts[i+1]`` - blank, i.e. falsy (or an IndexError for slot 4) - so it takes
    the else arm and returns None for a slot shipped parses.
    """
    stats = run_stats(row)

    # L309/L314/L319/L324/L329 - shipped parses parts[i] from its own value.
    assert stats[FIELD_NAMES[slot]] == SLOT_VALUES[slot]
    for earlier in range(slot):
        assert stats[FIELD_NAMES[earlier]] == SLOT_VALUES[earlier]
    if slot < 4:
        # The blank slot after the target: shipped's falsy guard yields None.
        assert stats[FIELD_NAMES[slot + 1]] is None
        # L333 - six fields here, so the name comes from parts[5].
        assert stats["gpu_name"] == "Sixty"
    else:
        # L333 - five fields only: the shipped gate is False -> fallback name.
        assert stats["gpu_name"] == FALLBACK_NAME


@pytest.mark.parametrize(("slot", "row"), NA_NEIGHBOUR_ROWS)
def test_slot_before_an_na_sentinel_neighbour_is_still_parsed(slot: int, row: str) -> None:
    """A numeric slot is parsed even when the NEXT slot is the ``[N/A]`` sentinel.

    Given: a row whose slot `slot` carries a number and whose slot ``slot + 1`` is
        nvidia-smi's ``[N/A]`` sentinel (for slot 4 the sentinel sits in the name slot)
    When: _get_gpu_stats_nvidia_smi() parses the row
    Then: the target field holds its own number, the sentinel neighbour is None, the
        earlier fields are untouched and the name slot keeps the sentinel verbatim

    Kills the THIRD AST position of each index constant - the left operand of the
    guard's ``!= "[N/A]"`` comparison.  Shifted one slot that leg compares the
    NEIGHBOUR against the sentinel, so the mutant takes the else arm and yields None
    where shipped parses the number.  A blank neighbour cannot reveal this position
    (the truthiness leg short-circuits before the compare runs) and an all-distinct
    numeric row cannot either - hence this second family.
    """
    stats = run_stats(row)

    # L309/L314/L319/L324/L329 - shipped's guard tests parts[i] on both legs.
    assert stats[FIELD_NAMES[slot]] == SLOT_VALUES[slot]
    for earlier in range(slot):
        assert stats[FIELD_NAMES[earlier]] == SLOT_VALUES[earlier]
    if slot < 4:
        # The sentinel neighbour itself is shipped None (it is not a number).
        assert stats[FIELD_NAMES[slot + 1]] is None
    # L333: the name comes from parts[5] with no sentinel filtering.
    assert stats["gpu_name"] == (NA_SENTINEL if slot == 4 else "Sixty")


def test_multiline_output_parses_the_first_gpu_row() -> None:
    """Multi-GPU output: only the FIRST line is parsed (shipped L301).

    Given: stdout carries two divergent rows
    When: _get_gpu_stats_nvidia_smi() parses it
    Then: the fields come from row 1 and the second row is ignored

    Kills the ``.split("\\n")[0]`` -> ``[1]`` twin candidate of s45/s46: that
    mutant reads the 999-row, so the sextuple diverges instead of matching.
    """
    stats = run_stats(f"{SIX_ROW}\n999, 998, 997, 996, 995, Second")

    # L301: line = result.stdout.strip().split("\\n")[0]  # Take first GPU if multiple
    assert stats["temperature"] == 10.0
    assert stats["power_usage"] == 20.0
    assert stats["gpu_utilization"] == 30.0
    assert stats["memory_used"] == 40
    assert stats["memory_total"] == 50
    assert stats["gpu_name"] == "Sixty"


def test_exactly_five_fields_falls_back_to_the_nvml_gpu_name() -> None:
    """A five-field row keeps the name from NVML/init (shipped L333 gate False).

    Given: nvidia-smi reports five fields (no trailing ``name`` column)
    When: _get_gpu_stats_nvidia_smi() parses the row
    Then: a dict is returned whose ``gpu_name`` is ``self._gpu_name``

    Sole kill for s98 (``len(parts) > 5`` forced True) and s100 (``>= 5``): both
    mutants evaluate ``parts[5]`` on a five-element list, the IndexError escapes to
    the L369 wrapper, and the call raises instead of returning.
    """
    stats = run_stats("10, 20, 30, 40, 50")

    # L333 (else arm): self._gpu_name
    assert stats["gpu_name"] == FALLBACK_NAME
    assert stats["temperature"] == 10.0
    assert stats["memory_total"] == 50


def test_four_field_row_raises_the_unexpected_format_runtimeerror() -> None:
    """A four-field row is rejected before any slot is read (shipped L304-L305).

    Given: nvidia-smi reports four fields
    When: _get_gpu_stats_nvidia_smi() validates the field count
    Then: RuntimeError whose text is the L370 wrap of the L305 message

    Control leg: it shows the indexing block the G02b twins mutate is only
    reachable with >= 5 fields, so a sextuple leg can never be satisfied by a
    crash path.
    """
    monitor = make_monitor()

    with (
        patch("subprocess.run", autospec=True, return_value=completed("10, 20, 30, 40")),
        pytest.raises(RuntimeError) as caught,
    ):
        monitor._get_gpu_stats_nvidia_smi()

    assert str(caught.value) == f"{WRAP_PREFIX}{INNER_FORMAT_PREFIX}10, 20, 30, 40"


# =============================================================================
# G02c: return-dict key identity (L342-L364), tz, and the two wraps
# =============================================================================


def test_return_dict_carries_the_shipped_twenty_six_keys() -> None:
    """The nvidia-smi dict is exactly the 26 shipped names, extended ones None.

    Given: a six-field row succeeds
    When: the return dict is inspected
    Then: its key set equals the shipped 26-name set and the 19 metrics the basic
        nvidia-smi query cannot provide are all None

    Kills all 40 L342-L364 ``string:wrapXX``/``string:upper`` key mutants (a
    renamed entry breaks set equality and the shipped-name lookup below) and the
    L364 ``"bar1_used": None`` -> ``2`` twin candidate of s56/s57.
    """
    stats = run_stats(SIX_ROW)

    assert set(stats) == set(SHIPPED_KEYS)
    assert len(SHIPPED_KEYS) == 26
    # L336-L341: the six populated entries, looked up by shipped name.
    assert stats["gpu_name"] == "Sixty"
    assert stats["gpu_utilization"] == 30.0
    assert stats["memory_used"] == 40
    assert stats["memory_total"] == 50
    assert stats["temperature"] == 10.0
    assert stats["power_usage"] == 20.0
    # L344-L364: every extended entry ships None for this source.
    for name in NONE_KEYS:
        assert stats[name] is None


def test_recorded_at_is_utc_aware() -> None:
    """``recorded_at`` is timezone-aware UTC (shipped L342 ``datetime.now(UTC)``).

    Given: a six-field row succeeds
    When: the ``recorded_at`` entry is inspected
    Then: it is an aware datetime pinned to UTC

    Sole kill for s116 (``datetime.now(UTC)`` -> ``datetime.now(None)``): the
    naive timestamp has ``tzinfo is None``.
    """
    stats = run_stats(SIX_ROW)

    recorded_at = stats["recorded_at"]
    assert recorded_at.tzinfo is not None
    # L342: "recorded_at": datetime.now(UTC),
    assert recorded_at.tzinfo is UTC
    assert recorded_at.utcoffset() == timedelta(0)


def test_timeout_expired_becomes_the_bare_timeout_runtimeerror() -> None:
    """A subprocess timeout raises the EXACT bare message (shipped L367-L368).

    Given: ``subprocess.run`` raises ``TimeoutExpired``
    When: _get_gpu_stats_nvidia_smi() handles it
    Then: RuntimeError("nvidia-smi timed out") - unwrapped - caused by that very
        TimeoutExpired

    Sole kill for s156 (``"nvidia-smi timed out"`` -> ``"XXnvidia-smi timed outXX"``)
    via full-string equality; the ``__cause__`` identity pins the ``from e``.
    """
    monitor = make_monitor()
    boom = subprocess.TimeoutExpired("nvidia-smi", 5)

    with (
        patch("subprocess.run", autospec=True, side_effect=boom),
        pytest.raises(RuntimeError) as caught,
    ):
        monitor._get_gpu_stats_nvidia_smi()

    assert str(caught.value) == TIMEOUT_MSG
    assert caught.value.__cause__ is boom


def test_oserror_becomes_the_wrapped_failed_runtimeerror() -> None:
    """Any other failure is re-wrapped with the shipped prefix (L369-L370).

    Given: ``subprocess.run`` raises ``OSError("kaput")``
    When: _get_gpu_stats_nvidia_smi() handles it
    Then: RuntimeError whose text is exactly the L370 f-string

    Control leg: it pins the wrapper through which the L333 gate mutants
    (s98/s100) surface, so their kills cannot be re-read as an un-wrapped crash.
    """
    monitor = make_monitor()

    with (
        patch("subprocess.run", autospec=True, side_effect=OSError("kaput")),
        pytest.raises(RuntimeError) as caught,
    ):
        monitor._get_gpu_stats_nvidia_smi()

    assert str(caught.value) == f"{WRAP_PREFIX}kaput"
    assert isinstance(caught.value.__cause__, OSError)


def test_nonzero_returncode_raises_the_wrapped_stderr_message() -> None:
    """A non-zero exit becomes the wrapped ``returned error`` text (L297-L298).

    Given: nvidia-smi exits 1 with stderr ``bad``
    When: _get_gpu_stats_nvidia_smi() checks the return code
    Then: RuntimeError with exactly the L370 wrap of the L298 message

    Second observable face of the L297 guard: shipped raises here while the
    ``!= 0`` -> ``!= 1`` twin candidate of s45/s46 falls through and parses the
    (empty) stdout instead.
    """
    monitor = make_monitor()

    with (
        patch("subprocess.run", autospec=True, return_value=completed("", "bad", 1)),
        pytest.raises(RuntimeError) as caught,
    ):
        monitor._get_gpu_stats_nvidia_smi()

    assert str(caught.value) == f"{WRAP_PREFIX}{INNER_ERROR_PREFIX}bad"


def test_module_exposes_the_function_under_mutation() -> None:
    """Sanity: the battery drives the shipped method, not a local re-creation.

    Control leg: it names the exact callable the 54 keys mutate
    (``backend.services.gpu_monitor.GPUMonitor._get_gpu_stats_nvidia_smi``).
    """
    assert M.GPUMonitor._get_gpu_stats_nvidia_smi is GPUMonitor._get_gpu_stats_nvidia_smi
