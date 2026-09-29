"""S3 batch-28 gpu_monitor lane 01 - nvidia-smi stats battery (G02a + G05a).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json``
groups ``G02a nvidia-smi sync: guard + subprocess call contract + len gate``
(``group_3.keys``, 23 KILLABLE) and ``G05a nvidia-smi async: guard +
async_subprocess_run contract + stderr/len gates`` (``group_4.keys``, 23 KILLABLE) -
46 keys total, 0 EQUIVALENT.

Test -> mutant-key map
======================
Every key below is in ``group_3.keys`` (sync, ``xǁGPUMonitorǁ
_get_gpu_stats_nvidia_smi``, L266-370) or ``group_4.keys`` (async twin,
``xǁGPUMonitorǁ_get_gpu_stats_nvidia_smi_async``, L372-480).

Sync (group_3)
- ``_mutmut_1`` L278 guard ``not avail or not path`` -> ``and`` and ``_mutmut_5``
  L279 message wrapXX -> ``test_unusable_probe_state_raises_the_unavailable_error``
  (both bad-half rows must raise; the ``and`` mutant raises on NEITHER).
- ``_mutmut_8`` argv -> ``None``, ``_mutmut_9/10/11/12``
  capture_output/text/timeout/check -> ``None``, ``_mutmut_13/14/15/16/17``
  drop_arg x5, ``_mutmut_18/19`` L288 query string wrap/upper, ``_mutmut_20/21``
  L289 query string wrap/upper, ``_mutmut_22`` L291 ``capture_output=True`` ->
  ``False``, ``_mutmut_23`` L292 ``text=True`` -> ``False``, ``_mutmut_24`` L293
  ``timeout=5`` -> ``6``, ``_mutmut_25`` L294 ``check=False`` -> ``True``
  -> ``test_six_field_row_is_parsed_into_the_shipped_dict`` (the
  ``run.assert_called_once_with(argv, capture_output=True, text=True, timeout=5,
  check=False)`` identity pin over L285-295).
- ``_mutmut_31`` L301 ``split("\\n")`` -> ``split("XX\\nXX")``
  -> ``test_two_gpu_rows_parse_only_the_first_gpu`` (the second row would be glued
  into ``parts[5]``, so the ``gpu_name`` pin is the discriminator).
- ``_mutmut_36`` L304 ``len(parts) < 5`` -> ``<= 5`` and ``_mutmut_37`` ``5`` ->
  ``6`` -> ``test_five_field_row_falls_back_to_the_stored_gpu_name`` (shipped
  ACCEPTS five fields; both mutants raise there) with the four-field row in
  ``test_short_row_raises_the_output_format_error`` as the shipped-raises leg.
  (``_mutmut_37`` also carries the L293 ``timeout=6`` leg - killed by the call
  identity pin - and the L333 ``parts[6]`` leg - killed by the six-field row's
  ``gpu_name`` pin - plus one INERT comment-leg at L300; see "Manual legs".)

Async (group_4)
- ``_mutmut_1`` L384 guard boolop + ``_mutmut_5`` L385 message wrapXX
  -> ``test_async_unusable_probe_state_raises_the_unavailable_error``.
- ``_mutmut_8`` argv -> ``None``, ``_mutmut_9/10/11`` capture_output/text/timeout
  -> ``None``, ``_mutmut_13/14/15`` drop_arg x3, ``_mutmut_16/17`` L395 and
  ``_mutmut_18/19`` L396 query-string wrap/upper, ``_mutmut_20`` L398
  ``capture_output=True`` -> ``False``, ``_mutmut_21`` L399 ``text=True`` ->
  ``False``, ``_mutmut_22`` L400 ``timeout=5.0`` -> ``6.0``, plus one
  call-leg of ``_mutmut_41`` (L400 ``5.0`` -> ``6.0``)
  -> ``test_async_six_field_row_is_parsed_into_the_shipped_dict`` (call-identity
  pin over L392-401 - the shipped async call has NO ``check`` kwarg, pinned too).
- ``_mutmut_26`` L405 ternary ``and False``, ``_mutmut_27`` ternary ``or True``,
  ``_mutmut_28`` ``str(result.stderr)`` -> ``str(None)``, ``_mutmut_29`` ``""`` ->
  ``"XXXX"`` -> ``test_async_nonzero_rc_interpolates_the_stderr`` (stderr
  ``"bad"`` -> the EXACT shipped message: kills 26 and 28) and
  ``test_async_nonzero_rc_without_stderr_stops_at_the_colon`` (stderr ``None`` ->
  the EXACT shipped message ending at "error: ": kills 27 and 29).  STR stderr on
  purpose - text=True is shipped, so a bytes row would interpolate as ``b'..'``.
- ``_mutmut_35`` L411 ``split("\\n")`` wrapXX
  -> ``test_async_two_gpu_rows_parse_only_the_first_gpu``.
- ``_mutmut_40`` L414 ``< 5`` -> ``<= 5`` and ``_mutmut_41`` ``5`` -> ``6``
  -> ``test_async_five_field_row_falls_back_to_the_stored_gpu_name`` +
  ``test_async_short_row_raises_the_output_format_error``.

Manual legs (measured, not skipped)
===================================
Six of these keys carry a candidate the replay harness enumerates but that NO test
can ever redden.  The ``5 -> 6``/``True -> False`` token twins match a number
INSIDE A COMMENT (the L300/L403 sample-output / text-mode comments) - comments are
not executed, so that occurrence is provably inert; for ``_mutmut_29`` the ``""``
token twins land on empty docstrings and the splice does not compile at all
(measured SyntaxErrors at L373/L1302).  The mutmut adjudicated tree at
``mutants/backend/services/gpu_monitor.py`` shows each key's TRUE mutated line:

* sync ``_mutmut_24`` true L293 ``timeout=6``   | sync ``_mutmut_37`` true L304
  ``if len(parts) < 6`` - BOTH keys enumerate the same 4 candidates (L293, L300
  comment, L304, L333) and this battery reddens all THREE behavioural ones
  (measured in ``/tmp/wp-pw/gm/replay_03.json``): the kwargs pin kills L293, the
  five-field row kills L304, the six-field ``gpu_name`` pin kills L333.
* async ``_mutmut_20`` true L398 ``capture_output=False`` | async ``_mutmut_21``
  true L399 ``text=False`` - both enumerate L398 + L399 + the L403 comment; both
  behavioural twins reddened by the kwargs pin (``replay_04.json``).
* async ``_mutmut_29`` true L405 ``else "XXXX"`` - the harness DID run this one
  (occ2/3) and it reddened ``test_async_nonzero_rc_without_stderr_stops_at_the_colon``;
  the key was only demoted by the two un-compiling docstring twins.
* async ``_mutmut_41`` true L414 ``if len(parts) < 6`` - same 4-candidate family
  (L400 ``timeout=6.0``, L410 comment, L414, L443), three reddened.

Each key is additionally proven BY CONSTRUCTION with ``/tmp/wp-pw/gm/probe_true_mutants.py``,
which rebuilds the TRUE mutant alone onto the shipped source, keeps this battery
GREEN on pristine and shows it RED (named failing test) on that mutant - output in
``/tmp/wp-pw/gm/probe_results.json``, mutant sources in ``/tmp/wp-pw/gm/probe_src/``.
All 6 (and file _00's ``__init____mutmut_33``): 7/7 PROVEN.

Discipline
----------
* The subprocess is always a double: ``subprocess.run`` for the sync path and
  ``backend.core.async_utils.async_subprocess_run`` for the async path (shipped
  L387 imports it per call, so the module attribute is the live site), each
  ``autospec=True``.  No process is ever spawned and no target is patched twice.
* The monitor is built with the shipped ``__new__`` + the three attributes the two
  functions read (``_nvidia_smi_available`` / ``_nvidia_smi_path`` / ``_gpu_name``)
  - the neighbour idiom in ``test_gpu_monitor.py`` - so no probe runs at all.
* ``subprocess.TimeoutExpired`` / ``CompletedProcess`` are the real classes.
* Exceptions are compared as EXACT strings (``str(exc) ==``), which is also what
  falsifies the wrapXX message mutants.
* No clock patch (these two functions have no timing site - ``datetime.now(UTC)``
  is only pinned for tz-awareness), no ``time.monotonic``/``perf_counter`` patch,
  no import-time global spy, no session-scoped patch.
"""

from __future__ import annotations

import subprocess
from datetime import UTC
from typing import Any
from unittest.mock import patch

import pytest

from backend.services import gpu_monitor as M

pytestmark = [pytest.mark.unit]

RUN = "backend.services.gpu_monitor.subprocess.run"  # shipped L285 attribute lookup
ARUN = "backend.core.async_utils.async_subprocess_run"  # shipped L387/L392 import site

# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

PATH = "/usr/bin/nvidia-smi"
# L286-L290 / L393-L397: the argv list, both paths identical
ARGV = [
    PATH,
    "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name",
    "--format=csv,noheader,nounits",
]
# L291-L294: capture_output=True, text=True, timeout=5, check=False
SYNC_KWARGS = {"capture_output": True, "text": True, "timeout": 5, "check": False}
# L398-L400: capture_output=True, text=True, timeout=5.0 -- shipped has NO check kwarg
ASYNC_KWARGS = {"capture_output": True, "text": True, "timeout": 5.0}
# L279 / L385: raise RuntimeError("nvidia-smi not available")
UNAVAILABLE = "nvidia-smi not available"
# L300 / L410: the six-field sample row the shipped comment documents
SIX_FIELDS = "39, 29.61, 35, 175, 24576, NVIDIA RTX A5500"
# L305 / L415 raise RuntimeError(f"Unexpected nvidia-smi output format: {line}")
# INSIDE the try opened at L281 / L389, so the outer handler (L369-370 / L479-480)
# re-wraps it -- the shipped text is the WRAPPED one.
SHORT_ROW = "39, 29.61, 35, 175"
SHORT_ROW_MSG = (
    f"Failed to get GPU stats via nvidia-smi: Unexpected nvidia-smi output format: {SHORT_ROW}"
)
# Five fields: no name column, so L333/L443 falls back to self._gpu_name
FIVE_FIELDS = "39, 29.61, 35, 175, 24576"
# L301/L411 take the FIRST line only
FIRST_ROW = "39, 29.61, 35, 175, 24576, GPU One"
SECOND_ROW = "40, 30.5, 40, 200, 24576, GPU Two"
TWO_GPU_ROWS = f"{FIRST_ROW}\n{SECOND_ROW}"
# Stored name used by the five-field fallback leg (an attribute this battery sets)
STORED_NAME = "Stored Fallback GPU"


def monitor_with_probe() -> Any:
    """Monitor in the shipped "nvidia-smi mode" without running any probe.

    Shipped ``_get_gpu_stats_nvidia_smi`` / its async twin read exactly
    ``_nvidia_smi_available`` (L278/L384), ``_nvidia_smi_path`` (L287/L394) and
    ``_gpu_name`` (L333/L443); nothing else is reached, so the double-attribute
    construction of the shipped neighbour file is the faithful stimulus.
    """
    monitor = M.GPUMonitor.__new__(M.GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = PATH
    monitor._gpu_name = STORED_NAME
    return monitor


def completed(returncode: int, stdout: str, stderr: str = "") -> subprocess.CompletedProcess[str]:
    """A real CompletedProcess - shipped reads returncode/stdout/stderr only."""
    return subprocess.CompletedProcess(ARGV, returncode, stdout, stderr)


def parsed_six_fields(stats: dict[str, Any]) -> None:
    """The shipped parse of the six-field row (L308-L333 / L418-L443)."""
    assert stats["gpu_name"] == "NVIDIA RTX A5500"
    assert stats["gpu_utilization"] == 35.0
    assert stats["memory_used"] == 175
    assert stats["memory_total"] == 24576
    assert stats["temperature"] == 39.0
    assert stats["power_usage"] == 29.61
    # L342 / L452: "recorded_at": datetime.now(UTC) - tz-aware, never naive.
    assert stats["recorded_at"].tzinfo is UTC


# =============================================================================
# Sync guard (G02a): mutmut_1 (boolop) + mutmut_5 (message wrapXX)
# =============================================================================


@pytest.mark.parametrize(
    ("available", "path"),
    [
        # Probe succeeded but the path was never stored.
        (True, ""),
        # A path survived from an earlier mode while the probe flag is off.
        (False, PATH),
    ],
    ids=["no-path", "no-flag"],
)
def test_unusable_probe_state_raises_the_unavailable_error(
    available: bool,
    path: str,
) -> None:
    """Either half of the guard alone raises, with the shipped message verbatim.

    Shipped backend/services/gpu_monitor.py:278-279::

        if not self._nvidia_smi_available or not self._nvidia_smi_path:
            raise RuntimeError("nvidia-smi not available")

    ``Or`` -> ``And`` (mutmut_1) only raises when BOTH halves are bad, so each
    single-bad row must raise to kill it; the exact text kills the wrapXX mutant.
    """
    monitor = M.GPUMonitor.__new__(M.GPUMonitor)
    monitor._nvidia_smi_available = available
    monitor._nvidia_smi_path = path
    monitor._gpu_name = STORED_NAME

    with (
        patch(RUN, autospec=True) as run,
        pytest.raises(RuntimeError) as caught,
    ):
        monitor._get_gpu_stats_nvidia_smi()

    assert str(caught.value) == UNAVAILABLE
    run.assert_not_called()


# =============================================================================
# Sync success + gates: mutmut_8..25, 31, 36, 37
# =============================================================================


def test_six_field_row_is_parsed_into_the_shipped_dict() -> None:
    """rc=0 + six fields -> the exact call contract and the parsed values.

    Shipped ``...:285-333``::

        result = subprocess.run(
            [
                self._nvidia_smi_path,
                "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        ...
        gpu_name = parts[5] if len(parts) > 5 else self._gpu_name

    The argv/kwargs identity is the kill for all 17 keys on that call (5 x
    call_arg->None, 5 x drop_arg, 4 x query-string wrap/upper, 2 x True->False,
    timeout 5->6, check False->True); the values are the kill for the ``parts[6]``
    leg of mutmut_37.
    """
    monitor = monitor_with_probe()
    with patch(RUN, return_value=completed(0, SIX_FIELDS), autospec=True) as run:
        stats = monitor._get_gpu_stats_nvidia_smi()

    run.assert_called_once_with(ARGV, **SYNC_KWARGS)
    parsed_six_fields(stats)


def test_five_field_row_falls_back_to_the_stored_gpu_name() -> None:
    """Five fields is ACCEPTED: no name column, so ``_gpu_name`` is returned.

    Shipped ``...:304`` is ``if len(parts) < 5:`` and ``...:333`` is
    ``gpu_name = parts[5] if len(parts) > 5 else self._gpu_name``.  ``<= 5``
    (mutmut_36) and ``< 6`` (mutmut_37) both RAISE here, so this shipped-success row
    is their discriminator.
    """
    monitor = monitor_with_probe()
    with patch(RUN, return_value=completed(0, FIVE_FIELDS), autospec=True) as run:
        stats = monitor._get_gpu_stats_nvidia_smi()

    run.assert_called_once_with(ARGV, **SYNC_KWARGS)
    assert stats["gpu_name"] == STORED_NAME
    assert stats["temperature"] == 39.0
    assert stats["memory_total"] == 24576


def test_short_row_raises_the_output_format_error() -> None:
    """Four fields -> the format RuntimeError, re-wrapped by the outer handler.

    Shipped ``...:304-305``::

        if len(parts) < 5:
            raise RuntimeError(f"Unexpected nvidia-smi output format: {line}")

    sits INSIDE the ``try`` opened at L281, so what ships is the L369-370 wrap of
    that message.  Both gate mutants also raise on this row, so it is the
    shipped-leg pin, not the discriminator (that is the five-field row above).
    """
    monitor = monitor_with_probe()
    with (
        patch(RUN, return_value=completed(0, SHORT_ROW), autospec=True) as run,
        pytest.raises(RuntimeError) as caught,
    ):
        monitor._get_gpu_stats_nvidia_smi()

    run.assert_called_once_with(ARGV, **SYNC_KWARGS)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value) == SHORT_ROW_MSG


def test_two_gpu_rows_parse_only_the_first_gpu() -> None:
    """Two stdout lines -> the FIRST row's values, name included (L301).

    ``split("XX\\nXX")`` (mutmut_31) never splits, so ``parts[5]`` becomes
    ``"GPU One\\n40"`` and the name pin reddens.
    """
    monitor = monitor_with_probe()
    with patch(RUN, return_value=completed(0, TWO_GPU_ROWS), autospec=True) as run:
        stats = monitor._get_gpu_stats_nvidia_smi()

    run.assert_called_once_with(ARGV, **SYNC_KWARGS)
    assert stats["gpu_name"] == "GPU One"
    assert stats["temperature"] == 39.0
    assert stats["power_usage"] == 29.61


def test_nonzero_rc_raises_the_wrapped_stderr_message() -> None:
    """rc=1 -> the L298 message, then re-wrapped by the L369-370 outer handler.

    Shipped ``...:297-298`` raises inside the ``try``::

        if result.returncode != 0:
            raise RuntimeError(f"nvidia-smi returned error: {result.stderr.strip()}")

    and the outer ``except Exception as e`` (L369-370) re-raises it as
    ``f"Failed to get GPU stats via nvidia-smi: {e}"`` with ``__cause__`` set - the
    audit-correction #2 shape, pinned verbatim.
    """
    monitor = monitor_with_probe()
    with (
        patch(RUN, return_value=completed(1, "", "  driver down  "), autospec=True) as run,
        pytest.raises(RuntimeError) as caught,
    ):
        monitor._get_gpu_stats_nvidia_smi()

    run.assert_called_once_with(ARGV, **SYNC_KWARGS)
    assert str(caught.value) == (
        "Failed to get GPU stats via nvidia-smi: nvidia-smi returned error: driver down"
    )
    assert isinstance(caught.value.__cause__, RuntimeError)


# =============================================================================
# Async guard (G05a): mutmut_1 (boolop) + mutmut_5 (message wrapXX)
# =============================================================================


@pytest.mark.parametrize(
    ("available", "path"),
    [(True, ""), (False, PATH)],
    ids=["no-path", "no-flag"],
)
async def test_async_unusable_probe_state_raises_the_unavailable_error(
    available: bool,
    path: str,
) -> None:
    """The async twin raises on either bad half, verbatim (L384-L385)."""
    monitor = M.GPUMonitor.__new__(M.GPUMonitor)
    monitor._nvidia_smi_available = available
    monitor._nvidia_smi_path = path
    monitor._gpu_name = STORED_NAME

    with (
        patch(ARUN, autospec=True) as run,
        pytest.raises(RuntimeError) as caught,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    assert str(caught.value) == UNAVAILABLE
    run.assert_not_called()


# =============================================================================
# Async success + gates: mutmut_8..22, 35, 40, 41
# =============================================================================


async def test_async_six_field_row_is_parsed_into_the_shipped_dict() -> None:
    """rc=0 + six fields -> the exact async call contract and the parsed values.

    Shipped ``...:392-401``::

        result = await async_subprocess_run(
            [
                self._nvidia_smi_path,
                "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5.0,
        )

    The shipped async call passes NO ``check`` kwarg - pinned, because the sync
    twin does and a "shared" helper rewrite would otherwise be invisible.
    """
    monitor = monitor_with_probe()
    with patch(ARUN, return_value=completed(0, SIX_FIELDS), autospec=True) as run:
        stats = await monitor._get_gpu_stats_nvidia_smi_async()

    run.assert_called_once_with(ARGV, **ASYNC_KWARGS)
    assert "check" not in run.call_args.kwargs
    parsed_six_fields(stats)


async def test_async_five_field_row_falls_back_to_the_stored_gpu_name() -> None:
    """Five fields is ACCEPTED by the async twin (L414 / L443)."""
    monitor = monitor_with_probe()
    with patch(ARUN, return_value=completed(0, FIVE_FIELDS), autospec=True) as run:
        stats = await monitor._get_gpu_stats_nvidia_smi_async()

    run.assert_called_once_with(ARGV, **ASYNC_KWARGS)
    assert stats["gpu_name"] == STORED_NAME
    assert stats["memory_used"] == 175


async def test_async_short_row_raises_the_output_format_error() -> None:
    """Four fields -> the same wrapped message as the sync twin (L414-415, L479-480)."""
    monitor = monitor_with_probe()
    with (
        patch(ARUN, return_value=completed(0, SHORT_ROW), autospec=True) as run,
        pytest.raises(RuntimeError) as caught,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    run.assert_called_once_with(ARGV, **ASYNC_KWARGS)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value) == SHORT_ROW_MSG


async def test_async_two_gpu_rows_parse_only_the_first_gpu() -> None:
    """``split("XX\\nXX")`` (mutmut_35) glues the rows -> the name pin reddens."""
    monitor = monitor_with_probe()
    with patch(ARUN, return_value=completed(0, TWO_GPU_ROWS), autospec=True) as run:
        stats = await monitor._get_gpu_stats_nvidia_smi_async()

    run.assert_called_once_with(ARGV, **ASYNC_KWARGS)
    assert stats["gpu_name"] == "GPU One"


# =============================================================================
# Async stderr interpolation (L405): mutmut_26, 27, 28, 29
# =============================================================================


async def test_async_nonzero_rc_interpolates_the_stderr() -> None:
    """stderr="bad" -> the shipped message carries it verbatim (L405 + L408).

    Shipped ``...:405-408``::

        stderr_str: str = str(result.stderr) if result.stderr else ""
        if result.returncode != 0:
            raise RuntimeError(f"nvidia-smi returned error: {stderr_str.strip()}")

    re-wrapped by the outer handler (L479-480) exactly like the sync twin.  ``str``
    stderr is the shipped ``text=True`` shape.  ``str(None)`` (mutmut_28) yields
    "error: None" and the ``and False`` forcing (mutmut_26) yields "error: ".
    """
    monitor = monitor_with_probe()
    with (
        patch(ARUN, return_value=completed(1, "", "bad"), autospec=True) as run,
        pytest.raises(RuntimeError) as caught,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    run.assert_called_once_with(ARGV, **ASYNC_KWARGS)
    assert str(caught.value) == (
        "Failed to get GPU stats via nvidia-smi: nvidia-smi returned error: bad"
    )
    assert isinstance(caught.value.__cause__, RuntimeError)


async def test_async_nonzero_rc_without_stderr_stops_at_the_colon() -> None:
    """Falsy stderr -> ``stderr_str`` is the empty string, NOT "None" or "XXXX".

    The ``else ""`` branch is the only thing this row can observe: ``or True``
    (mutmut_27) takes the ``then`` leg and interpolates "None"; the wrap mutant
    ``"XXXX"`` (mutmut_29) interpolates "XXXX".
    """
    monitor = monitor_with_probe()
    empty = subprocess.CompletedProcess(ARGV, 1, "", None)
    with (
        patch(ARUN, return_value=empty, autospec=True) as run,
        pytest.raises(RuntimeError) as caught,
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()

    run.assert_called_once_with(ARGV, **ASYNC_KWARGS)
    assert (
        str(caught.value) == "Failed to get GPU stats via nvidia-smi: nvidia-smi returned error: "
    )
