"""S3 batch-28 lane gm03 - ``gpu_monitor`` groups G05b + G05c kill battery (54 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 ``2f122c85a072b7bd00c2e4b36cdc1cda``
- byte-identical to the manifest-proven source). Admitted manifest
``/tmp/wp-pw/gpu_monitor/manifest.json`` groups ``G05b`` (``group_7.keys``, 12 keys)
and ``G05c`` (``group_8.keys``, 42 keys), both KILLABLE, plus ``survivors.json``
for the exact per-key diffs. No unparseable key and no EQUIVALENT key sits in
either group (``splice-group_7.json`` -> 10 twin / 2 clean, 0 bad;
``splice-group_8.json`` -> 42 clean, 0 bad).

Subject: ``GPUMonitor._get_gpu_stats_nvidia_smi_async`` - the async twin of the
gm02 subject: CSV field-index mutations at L419/L424/L429/L434/L439, the
``gpu_name`` fallback gate at L443, the 26-key identity of the returned dict
(L452-L474), the ``recorded_at`` timezone and the two exception re-wraps
(L477-L480).

Test -> mutant-key map (every key is in ``group_7.keys`` or ``group_8.keys``;
``a`` = the async function's survivor number, i.e. the ``__mutmut_`` suffix)
==========================================================================
- ``a49`` / ``a50``  L419 ``parts[0]`` -> ``parts[1]`` (value twin + guard twin)
  -> ``test_six_field_row_maps_the_positional_sextuple`` (value leg: temperature
     20.0 != 10.0) and ``test_slot_before_a_blank_neighbour_keeps_its_own_value[slot0-blank-after]``
     (both legs), and - these are NUMBER twins whose candidate set also spans L400
     ``timeout=5.0``, L407 ``result.returncode != 0`` and L411 ``.split("\\n")[0]``
     - the call-contract leg of ``test_six_field_row_maps...`` (``timeout == 5.0``,
     which also kills the ``timeout=5.0`` mutant), that test's zero-exit leg and
     ``test_nonzero_returncode_raises_the_wrapped_stderr_message`` (L407), and
     ``test_multiline_output_parses_the_first_gpu_row`` (L411).
- ``a60`` / ``a61``  L424 ``parts[1]`` -> ``parts[2]``; the same key's candidate
  set also spans L474 ``"bar1_used": None`` -> ``2``
  -> ``test_six_field_row_maps...``, ``test_slot_before_a_blank_neighbour...[slot1-blank-after]``
  and ``test_return_dict_carries_the_shipped_twenty_six_keys`` (None-valued leg).
- ``a71`` / ``a72``  L429 ``parts[2]`` -> ``parts[3]``
  -> ``test_six_field_row_maps...`` (value leg) and
  ``test_slot_before_a_blank_neighbour...[slot2-blank-after]`` (both legs - the
  guard twin agrees with shipped on the all-numeric row, so the blank-successor row
  is what separates it)
- ``a83`` / ``a84``  L434 ``parts[3]`` -> ``parts[4]``
  -> ``test_six_field_row_maps...``, ``test_slot_before_a_blank_neighbour...[slot3-blank-after]``
- ``a95`` / ``a96``  L439 ``parts[4]`` -> ``parts[5]``
  -> ``test_six_field_row_maps...`` (value leg: ValueError -> None where shipped is
  50) and ``test_slot_before_a_blank_neighbour...[slot4-no-slot-after]`` (both legs
  read the non-existent slot 5 -> IndexError -> RuntimeError instead of a dict)
- ``a102`` L443 ternary forced-then / ``a104`` L443 ``> 5`` -> ``>= 5``
  -> ``test_exactly_five_fields_falls_back_to_the_nvml_gpu_name`` (shipped 5-field
     row returns the dict with the fallback name; BOTH mutants evaluate
     ``parts[5]`` -> IndexError -> RuntimeError) and ``test_six_field_row_maps...``
     (fallback-off leg ``gpu_name == "Sixty"``).
- ``a118``/``a119``/``a121``...``a158`` (all 40 L452-L474 ``string:wrapXX`` /
  ``string:upper`` key renames) -> ``test_return_dict_carries_the_shipped_twenty_six_keys``.
- ``a120`` L452 ``datetime.now(UTC)`` -> ``datetime.now(None)``
  -> ``test_recorded_at_is_utc_aware``.
- ``a160`` L478 ``"nvidia-smi timed out"`` wrapXX
  -> ``test_timeout_expired_becomes_the_bare_timeout_runtimeerror``.

Control legs that kill nothing of their own
-------------------------------------------
``test_four_field_row_raises_the_unexpected_format_runtimeerror`` pins the L414
gate that keeps a short row OUT of the indexing block the twins mutate,
``test_oserror_becomes_the_wrapped_failed_runtimeerror`` pins the L479-L480
wrapper the L443 gate mutants escape through, and
``test_module_exposes_the_function_under_mutation`` names the mutated callable.

Discipline
----------
* Only shipped behaviour is asserted; production is never bent. Every pinned
  string/value is transcribed from the shipped file with a ``file:line`` comment
  at the assert; every value an assertion depends on is injected here (the CSV
  row, the fallback name, the fake ``CompletedProcess``).
* The ONLY double is the external subprocess boundary:
  ``backend.core.async_utils.async_subprocess_run`` (the shipped import site is
  the function-local ``from backend.core.async_utils import async_subprocess_run``
  at L387, so that module attribute is the patchable seam). No pynvml, no real
  subprocess, no real sleep - the awaited mock returns immediately.
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted; the only clock observation is the shipped ``recorded_at`` tzinfo.
* No import-time global spy: every patch is installed per test via a context
  manager and the monitor comes from ``GPUMonitor.__new__`` + explicit attribute
  seeding (the ``test_gpu_monitor.py`` nvidia-smi idiom).
"""

from __future__ import annotations

import subprocess
from datetime import UTC, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services import gpu_monitor as M
from backend.services.gpu_monitor import GPUMonitor

pytestmark = [pytest.mark.unit]


# The shipped call site imports the helper function-locally (L387), so the live
# attribute of backend.core.async_utils is the seam the function resolves at
# call time.
RUN_TARGET = "backend.core.async_utils.async_subprocess_run"


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L408: raise RuntimeError(f"nvidia-smi returned error: {stderr_str.strip()}")
INNER_ERROR_PREFIX = "nvidia-smi returned error: "
# L415: raise RuntimeError(f"Unexpected nvidia-smi output format: {line}")
INNER_FORMAT_PREFIX = "Unexpected nvidia-smi output format: "
# L478: raise RuntimeError("nvidia-smi timed out") from e
TIMEOUT_MSG = "nvidia-smi timed out"
# L480: raise RuntimeError(f"Failed to get GPU stats via nvidia-smi: {e}") from e
WRAP_PREFIX = "Failed to get GPU stats via nvidia-smi: "

SMI_PATH = "/usr/bin/nvidia-smi"
# L395-L396: the two query strings of the shipped argv list (L393-L397).
QUERY_ARGS = (
    "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name",
    "--format=csv,noheader,nounits",
)
# L443: gpu_name = parts[5] if len(parts) > 5 else self._gpu_name
FALLBACK_NAME = "Fallback RTX A5500"

# L419-L439 read the CSV slots positionally and L443 reads slot 5, so every slot
# of a successful row is distinct - a one-slot shift then changes >= 2 fields.
SIX_ROW = "10, 20, 30, 40, 50, Sixty"

# L445-L475: the shipped return dict's 26 keys, in shipped order.
SHIPPED_KEYS = (
    # L446-L452
    "gpu_name",
    "gpu_utilization",
    "memory_used",
    "memory_total",
    "temperature",
    "power_usage",
    "recorded_at",
    # L454-L457 extended metrics (not available via the basic nvidia-smi query)
    "fan_speed",
    "sm_clock",
    "memory_bandwidth_utilization",
    "pstate",
    # L459-L464 high-value metrics
    "throttle_reasons",
    "power_limit",
    "sm_clock_max",
    "compute_processes_count",
    "pcie_replay_counter",
    "temp_slowdown_threshold",
    # L466-L474 medium-value metrics
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

# The 19 L454-L474 entries the basic nvidia-smi query cannot supply: shipped None.
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
# sentinel, so the mutant takes the else arm where shipped parses the number.
NA_NEIGHBOUR_ROWS = (
    pytest.param(0, "10, [N/A], 30, 40, 50, Sixty", id="slot0-na-after"),
    pytest.param(1, "10, 20, [N/A], 40, 50, Sixty", id="slot1-na-after"),
    pytest.param(2, "10, 20, 30, [N/A], 50, Sixty", id="slot2-na-after"),
    pytest.param(3, "10, 20, 30, 40, [N/A], Sixty", id="slot3-na-after"),
    pytest.param(4, "10, 20, 30, 40, 50, [N/A]", id="slot4-na-name-slot"),
)

# L443 takes parts[5] verbatim - the sentinel is NOT filtered on the name slot.
NA_SENTINEL = "[N/A]"

FIELD_NAMES = ("temperature", "power_usage", "gpu_utilization", "memory_used", "memory_total")
# The parsed value of each numeric slot of the rows above (L434/L439 parse through
# int(float(...)), so the memory slots are ints).
SLOT_VALUES = {0: 10.0, 1: 20.0, 2: 30.0, 3: 40, 4: 50}


def make_monitor() -> GPUMonitor:
    """A GPUMonitor wired for the async nvidia-smi fallback path only.

    The shipped guard reads ``_nvidia_smi_available`` / ``_nvidia_smi_path``
    (L384) and the name fallback reads ``_gpu_name`` (L443); nothing else on this
    path touches instance state, so the object is built without running
    ``__init__`` (which would probe real NVML/nvidia-smi).
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = SMI_PATH
    monitor._gpu_name = FALLBACK_NAME
    return monitor


def completed(stdout: str, stderr: str = "", returncode: int = 0) -> Any:
    """A stand-in for the ``CompletedProcess`` the helper returns (L401)."""
    result = MagicMock(name="completed-process")
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


async def run_stats(stdout: str) -> dict:
    """Drive ``_get_gpu_stats_nvidia_smi_async`` over one canned successful row."""
    monitor = make_monitor()
    with patch(RUN_TARGET, new_callable=AsyncMock, return_value=completed(stdout)):
        return await monitor._get_gpu_stats_nvidia_smi_async()


# =============================================================================
# G05b: positional sextuple (L419/L424/L429/L434/L439) + gpu_name gate (L443)
# =============================================================================


async def test_six_field_row_maps_the_positional_sextuple() -> None:
    """Six-field row -> each CSV slot lands in its own shipped field.

    Given: the async helper returns rc=0 with "10, 20, 30, 40, 50, Sixty"
    When: _get_gpu_stats_nvidia_smi_async() parses the row
    Then: temperature 10.0, power_usage 20.0, gpu_utilization 30.0, memory_used 40,
        memory_total 50 and gpu_name "Sixty"; the helper was awaited with the
        shipped argv list and ``timeout == 5.0``

    Kills a49/a50 (L419), a60/a61 (L424), a71/a72 (L429), a83/a84 (L434) and
    a95/a96 (L439) on their value twins - a one-slot shift rewrites at least two
    fields for ANY row. It also kills the L400 ``timeout=5.0`` -> ``5.1`` twin
    candidate of a49/a50 (the ``timeout`` leg below), their L407 ``!= 0`` ->
    ``!= 1`` candidate (a zero-exit row would raise instead of returning) and
    their L411 ``[0]`` -> ``[1]`` candidate (a one-line row has no index 1), plus
    a102's forced-then arm (fallback OFF, so parts[5] is shipped).
    """
    monitor = make_monitor()
    helper = AsyncMock(name="async_subprocess_run", return_value=completed(SIX_ROW))
    with patch(RUN_TARGET, new=helper):
        stats = await monitor._get_gpu_stats_nvidia_smi_async()

    # L392-L401: the shipped call contract (argv identity + the three kwargs).
    awaited = helper.await_args
    assert awaited is not None
    assert awaited.args[0] == [SMI_PATH, *QUERY_ARGS]
    assert awaited.kwargs["capture_output"] is True
    assert awaited.kwargs["text"] is True
    # L400: timeout=5.0
    assert awaited.kwargs["timeout"] == 5.0

    # L419: temperature = float(parts[0]) if parts[0] and parts[0] != "[N/A]" else None
    assert stats["temperature"] == 10.0
    # L424: power_usage = float(parts[1]) ...
    assert stats["power_usage"] == 20.0
    # L429: gpu_utilization = float(parts[2]) ...
    assert stats["gpu_utilization"] == 30.0
    # L434: memory_used = int(float(parts[3])) ...
    assert stats["memory_used"] == 40
    # L439: memory_total = int(float(parts[4])) ...
    assert stats["memory_total"] == 50
    # L443: gpu_name = parts[5] if len(parts) > 5 else self._gpu_name
    assert stats["gpu_name"] == "Sixty"
    assert stats["gpu_name"] != FALLBACK_NAME


@pytest.mark.parametrize(("slot", "row"), BLANK_NEIGHBOUR_ROWS)
async def test_slot_before_a_blank_neighbour_keeps_its_own_value(slot: int, row: str) -> None:
    """A numeric slot is parsed from itself even when the NEXT slot is blank.

    Given: a row whose slot `slot` carries a number and whose slot ``slot + 1`` is
        blank (nvidia-smi prints an empty field for an unreadable sensor), with no
        slot 5 at all in the slot-4 case
    When: _get_gpu_stats_nvidia_smi_async() parses the row
    Then: the target field holds its own number, the blank neighbour is None and
        every earlier field is untouched

    Kills BOTH twins of each index pair.  The VALUE twin reads ``parts[i+1]``
    (blank -> ValueError -> None, or missing -> IndexError -> RuntimeError) where
    shipped returns the number.  The GUARD twin tests the truthiness of
    ``parts[i+1]`` - blank, i.e. falsy (or an IndexError for slot 4) - so it takes
    the else arm and returns None for a slot shipped parses.
    """
    stats = await run_stats(row)

    # L419/L424/L429/L434/L439 - shipped parses parts[i] from its own value.
    assert stats[FIELD_NAMES[slot]] == SLOT_VALUES[slot]
    for earlier in range(slot):
        assert stats[FIELD_NAMES[earlier]] == SLOT_VALUES[earlier]
    if slot < 4:
        # The blank slot after the target: shipped's falsy guard yields None.
        assert stats[FIELD_NAMES[slot + 1]] is None
        # L443 - six fields here, so the name comes from parts[5].
        assert stats["gpu_name"] == "Sixty"
    else:
        # L443 - five fields only: the shipped gate is False -> fallback name.
        assert stats["gpu_name"] == FALLBACK_NAME


@pytest.mark.parametrize(("slot", "row"), NA_NEIGHBOUR_ROWS)
async def test_slot_before_an_na_sentinel_neighbour_is_still_parsed(slot: int, row: str) -> None:
    """A numeric slot is parsed even when the NEXT slot is the ``[N/A]`` sentinel.

    Given: a row whose slot `slot` carries a number and whose slot ``slot + 1`` is
        nvidia-smi's ``[N/A]`` sentinel (for slot 4 the sentinel sits in the name slot)
    When: _get_gpu_stats_nvidia_smi_async() parses the row
    Then: the target field holds its own number, the sentinel neighbour is None, the
        earlier fields are untouched and the name slot keeps the sentinel verbatim

    Kills the THIRD AST position of each index constant - the left operand of the
    guard's ``!= "[N/A]"`` comparison.  Shifted one slot that leg compares the
    NEIGHBOUR against the sentinel, so the mutant takes the else arm and yields None
    where shipped parses the number.  A blank neighbour cannot reveal this position
    (the truthiness leg short-circuits before the compare runs) and an all-distinct
    numeric row cannot either - hence this second family.
    """
    stats = await run_stats(row)

    # L419/L424/L429/L434/L439 - shipped's guard tests parts[i] on both legs.
    assert stats[FIELD_NAMES[slot]] == SLOT_VALUES[slot]
    for earlier in range(slot):
        assert stats[FIELD_NAMES[earlier]] == SLOT_VALUES[earlier]
    if slot < 4:
        # The sentinel neighbour itself is shipped None (it is not a number).
        assert stats[FIELD_NAMES[slot + 1]] is None
    # L443: the name comes from parts[5] with no sentinel filtering.
    assert stats["gpu_name"] == (NA_SENTINEL if slot == 4 else "Sixty")


async def test_multiline_output_parses_the_first_gpu_row() -> None:
    """Multi-GPU output: only the FIRST line is parsed (shipped L411).

    Given: stdout carries two divergent rows
    When: _get_gpu_stats_nvidia_smi_async() parses it
    Then: the fields come from row 1 and the second row is ignored

    Kills the ``.split("\\n")[0]`` -> ``[1]`` twin candidate of a49/a50: that
    mutant reads the 999-row, so the sextuple diverges instead of matching.
    """
    stats = await run_stats(f"{SIX_ROW}\n999, 998, 997, 996, 995, Second")

    # L411: line = stdout_str.strip().split("\\n")[0]  # Take first GPU if multiple
    assert stats["temperature"] == 10.0
    assert stats["power_usage"] == 20.0
    assert stats["gpu_utilization"] == 30.0
    assert stats["memory_used"] == 40
    assert stats["memory_total"] == 50
    assert stats["gpu_name"] == "Sixty"


async def test_exactly_five_fields_falls_back_to_the_nvml_gpu_name() -> None:
    """A five-field row keeps the name from NVML/init (shipped L443 gate False).

    Given: nvidia-smi reports five fields (no trailing ``name`` column)
    When: _get_gpu_stats_nvidia_smi_async() parses the row
    Then: a dict is returned whose ``gpu_name`` is ``self._gpu_name``

    Sole kill for a102 (``len(parts) > 5`` forced True) and a104 (``>= 5``): both
    mutants evaluate ``parts[5]`` on a five-element list, the IndexError escapes to
    the L479 wrapper, and the call raises instead of returning.
    """
    stats = await run_stats("10, 20, 30, 40, 50")

    # L443 (else arm): self._gpu_name
    assert stats["gpu_name"] == FALLBACK_NAME
    assert stats["temperature"] == 10.0
    assert stats["memory_total"] == 50


async def test_four_field_row_raises_the_unexpected_format_runtimeerror() -> None:
    """A four-field row is rejected before any slot is read (shipped L414-L415).

    Given: nvidia-smi reports four fields
    When: _get_gpu_stats_nvidia_smi_async() validates the field count
    Then: RuntimeError whose text is the L480 wrap of the L415 message

    Control leg: it shows the indexing block the G05b twins mutate is only
    reachable with >= 5 fields, so a sextuple leg can never be satisfied by a
    crash path.
    """
    monitor = make_monitor()

    with (
        patch(RUN_TARGET, new_callable=AsyncMock, return_value=completed("10, 20, 30, 40")),
        pytest.raises(RuntimeError) as caught,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    assert str(caught.value) == f"{WRAP_PREFIX}{INNER_FORMAT_PREFIX}10, 20, 30, 40"


# =============================================================================
# G05c: return-dict key identity (L452-L474), tz, and the two wraps
# =============================================================================


async def test_return_dict_carries_the_shipped_twenty_six_keys() -> None:
    """The nvidia-smi dict is exactly the 26 shipped names, extended ones None.

    Given: a six-field row succeeds
    When: the return dict is inspected
    Then: its key set equals the shipped 26-name set and the 19 metrics the basic
        nvidia-smi query cannot provide are all None

    Kills all 40 L452-L474 ``string:wrapXX``/``string:upper`` key mutants (a
    renamed entry breaks set equality and the shipped-name lookup below) and the
    L474 ``"bar1_used": None`` -> ``2`` twin candidate of a60/a61.
    """
    stats = await run_stats(SIX_ROW)

    assert set(stats) == set(SHIPPED_KEYS)
    assert len(SHIPPED_KEYS) == 26
    # L446-L451: the six populated entries, looked up by shipped name.
    assert stats["gpu_name"] == "Sixty"
    assert stats["gpu_utilization"] == 30.0
    assert stats["memory_used"] == 40
    assert stats["memory_total"] == 50
    assert stats["temperature"] == 10.0
    assert stats["power_usage"] == 20.0
    # L454-L474: every extended entry ships None for this source.
    for name in NONE_KEYS:
        assert stats[name] is None


async def test_recorded_at_is_utc_aware() -> None:
    """``recorded_at`` is timezone-aware UTC (shipped L452 ``datetime.now(UTC)``).

    Given: a six-field row succeeds
    When: the ``recorded_at`` entry is inspected
    Then: it is an aware datetime pinned to UTC

    Sole kill for a120 (``datetime.now(UTC)`` -> ``datetime.now(None)``): the
    naive timestamp has ``tzinfo is None``.
    """
    stats = await run_stats(SIX_ROW)

    recorded_at = stats["recorded_at"]
    assert recorded_at.tzinfo is not None
    # L452: "recorded_at": datetime.now(UTC),
    assert recorded_at.tzinfo is UTC
    assert recorded_at.utcoffset() == timedelta(0)


async def test_timeout_expired_becomes_the_bare_timeout_runtimeerror() -> None:
    """A subprocess timeout raises the EXACT bare message (shipped L477-L478).

    Given: the async helper raises ``subprocess.TimeoutExpired``
    When: _get_gpu_stats_nvidia_smi_async() handles it
    Then: RuntimeError("nvidia-smi timed out") - unwrapped - caused by that very
        TimeoutExpired

    Sole kill for a160 (``"nvidia-smi timed out"`` -> ``"XXnvidia-smi timed outXX"``)
    via full-string equality; the ``__cause__`` identity pins the ``from e``.
    """
    monitor = make_monitor()
    boom = subprocess.TimeoutExpired("nvidia-smi", 5.0)

    with (
        patch(RUN_TARGET, new_callable=AsyncMock, side_effect=boom),
        pytest.raises(RuntimeError) as caught,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    assert str(caught.value) == TIMEOUT_MSG
    assert caught.value.__cause__ is boom


async def test_oserror_becomes_the_wrapped_failed_runtimeerror() -> None:
    """Any other failure is re-wrapped with the shipped prefix (L479-L480).

    Given: the async helper raises ``OSError("kaput")``
    When: _get_gpu_stats_nvidia_smi_async() handles it
    Then: RuntimeError whose text is exactly the L480 f-string

    Control leg: it pins the wrapper through which the L443 gate mutants
    (a102/a104) surface, so their kills cannot be re-read as an un-wrapped crash.
    """
    monitor = make_monitor()

    with (
        patch(RUN_TARGET, new_callable=AsyncMock, side_effect=OSError("kaput")),
        pytest.raises(RuntimeError) as caught,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    assert str(caught.value) == f"{WRAP_PREFIX}kaput"
    assert isinstance(caught.value.__cause__, OSError)


async def test_nonzero_returncode_raises_the_wrapped_stderr_message() -> None:
    """A non-zero exit becomes the wrapped ``returned error`` text (L407-L408).

    Given: nvidia-smi exits 1 with stderr ``bad``
    When: _get_gpu_stats_nvidia_smi_async() checks the return code
    Then: RuntimeError with exactly the L480 wrap of the L408 message

    Second observable face of the L407 guard: shipped raises here while the
    ``!= 0`` -> ``!= 1`` twin candidate of a49/a50 falls through and parses the
    (empty) stdout instead.
    """
    monitor = make_monitor()

    with (
        patch(RUN_TARGET, new_callable=AsyncMock, return_value=completed("", "bad", 1)),
        pytest.raises(RuntimeError) as caught,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    assert str(caught.value) == f"{WRAP_PREFIX}{INNER_ERROR_PREFIX}bad"


def test_module_exposes_the_function_under_mutation() -> None:
    """Sanity: the battery drives the shipped method, not a local re-creation.

    Control leg: it names the exact callable the 54 keys mutate
    (``backend.services.gpu_monitor.GPUMonitor._get_gpu_stats_nvidia_smi_async``).
    """
    target = GPUMonitor._get_gpu_stats_nvidia_smi_async
    assert M.GPUMonitor._get_gpu_stats_nvidia_smi_async is target
