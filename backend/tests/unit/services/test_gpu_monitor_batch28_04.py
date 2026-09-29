"""S3 batch-28 lane gm04 - ``gpu_monitor`` G04a kill battery (45 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda
- byte-identical to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/gpu_monitor/manifest.json`` group 9 (``G04a _get_extended_metrics:
high-value block (handle wiring, suppress, values)`` - 45 KILLABLE / 0
EQUIVALENT), plus ``group_9.keys`` and ``survivors.json`` for the exact per-key
diffs.  Splice report ``splice-group_9.json``: 39 clean + 6 twin, 0 unparseable
=> every key of this group is proven through the shared replay harness
(``/tmp/wp-b28/replay_lib.py``); no manual ``mutate.py`` probe is needed here.

Target: ``GPUMonitor._get_extended_metrics`` (L482-L549).  The HIGH-VALUE block
is L491-L516 - the ``handle`` local plus six ``with contextlib.suppress
(pynvml.NVMLError)`` metric blocks.  The function logs NOTHING (no ``logger``
call exists between L482 and L549), so this battery carries no caplog window;
every observable is the returned dict and the NVML call journal.  The MEDIUM
block (L519-L547) is driven by ``test_gpu_monitor_batch28_05.py`` and is
injected here as a uniform ``NVMLError`` fault so that this file's dict
comparisons are exactly the six high-value keys.

Test -> mutant-key map
======================
Every key below is in ``group_9.keys`` (the bank's
``...xǁGPUMonitorǁ_get_extended_metrics__mutmut_N`` abbreviated to ``mN``).

``test_high_value_success_path_returns_the_six_shipped_metrics``
  Exact 6-key equality on the returned dict with this file's injected values.
  - assign->None (metric written as ``None`` -> the key is MISSING): m4 (L495),
    m10 (L499), m18 (L503), m29 (L508), m33 (L510), m39 (L512).
  - string wrapXX / upper (metric written under a RENAMED key -> shipped key
    MISSING and an extra key present): m5/m6, m11/m12, m19/m20, m30/m31,
    m34/m35, m40/m41 - all 12.
  - arithmetic on the power leg: m14 ``/ 1000.0`` -> ``* 1000.0``
    (230000000.0 != 230.0) and m16 ``1000.0`` -> ``1001.0``
    (230000 / 1001.0 = 229.77022977022978 != 230.0).
  - m27 ``processes = None`` (L507): the shipped next statement is
    ``len(processes)``, so the mutant raises ``TypeError``, which the block's
    ``suppress(pynvml.NVMLError)`` does NOT swallow -> the call raises instead
    of returning the dict.
  - the five wrapper call_arg mutants m7 (L495), m13 (L499), m21 (L503),
    m36 (L510), m42 (L512): the inner NVML call is replaced by ``None``, so
    ``int(None)`` / ``float(None)`` raises ``TypeError`` and escapes.

``test_high_value_nvml_calls_receive_the_handle_and_the_shipped_constant``
  The journal of metric-call ``(name, positional-args)`` pairs, in shipped
  source order, compared EXACTLY (identity of the handle object + the shipped
  NVML constant).
  - m2 ``handle = self._gpu_handle`` -> ``handle = None`` (L491): every recorded
    first positional stops being ``HANDLE``.
  - arg->None (handle replaced by ``None``, arity intact - journal-only
    observable): m8 (L496), m15 (L500), m22 (L504), m28 (L507), m37 (L510),
    m43 (L513-515).
  - second-arg->None: m23 (L504 ``NVML_CLOCK_SM`` -> ``None``) and m44
    (L513-515 ``NVML_TEMPERATURE_THRESHOLD_SLOWDOWN`` -> ``None``).  Both keep
    arity 2 and still RETURN a number, so only the recorded argument identity
    (and the injected per-constant value table, which answers an unknown
    constant with ``UNSELECTED_CLOCK``) sees them.
  - drop_arg (arity collapse): m24/m25 (L504) and m45/m46 (L513-515) - the
    exact-arity doubles raise ``TypeError`` (outside ``suppress(NVMLError)`` =>
    the call escapes) AND the journal entry's args shrink, so both legs kill
    them.
  - m2/m7/m13/m21/m36/m42 also surface here as a raised call and/or a short
    journal.

``test_nvml_fault_is_swallowed_only_by_its_own_suppress_call``
  ``contextlib.suppress(pynvml.NVMLError)`` -> ``suppress(None)`` - a diff whose
  before-text occurs 14 times inside the function (L494, L498, L502, L506,
  L509, L511, L519, L523, L527, L529, L531, L535, L539, L542), so the bank
  cannot disambiguate and the harness requires EVERY candidate to redden.
  Shipped: when EVERY NVML call faults with ``NVMLError``, each of the 14
  blocks suppresses independently and ``_get_extended_metrics()`` returns
  ``{}``.  Under ANY occurrence the mutated block's ``__exit__`` evaluates
  ``issubclass(NVMLError, None)`` -> ``TypeError`` escapes the still-raising
  body and the whole function raises, so the leg reddens at every one of the 14
  positions (OCCURRENCE-TWIN SOUNDNESS): m3 (L494), m9 (L498), m17 (L502),
  m26 (L506), m32 (L509), m38 (L511).

Control legs that kill nothing of their own
(``test_each_high_value_block_independently_suppresses_its_own_nvml_fault`` -
per-block fault -> that key absent, its five siblings present - and
``test_empty_gpu_handle_is_still_passed_through_unchanged``) pin the shipped
isolation and the handle pass-through so a killing leg can never be satisfied
by an accidental fall-through.

Shipped behaviour only - nothing here invents a contract.  Every pinned literal
is transcribed from the shipped file at the line quoted in the test that asserts
it, and every value an assertion depends on is injected by this file.

Discipline
----------
* ``pynvml`` is injected through ``sys.modules`` per test (the shipped module is
  imported INSIDE the function, L488) and restored; no import-time global spy
  and no ``scope="session"`` anything.  A real GPU is never touched.
* The doubles are exact-arity call recorders, so ``drop_arg`` cannot hide as an
  equivalent call, and the handle is a private sentinel compared with ``is``.
* No ``time.monotonic`` / ``time.perf_counter`` patch and no clock assertion
  anywhere (g04a contains no timing site); no log assertion because the target
  function logs nothing.
* The single ``mock.patch`` site is ``autospec=True`` (WP4.2 fast path); the
  NVML doubles arrive by ``new=``-equivalent ``sys.modules`` injection.
"""

from __future__ import annotations

import sys
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

from backend.services import gpu_monitor as M

pytestmark = [pytest.mark.unit]

# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L491 `handle = self._gpu_handle` -> the object below is what the instance holds
HANDLE = object()  # private sentinel: identity, never equality
PROCESS_A = object()
PROCESS_B = object()

# The shipped NVML enum constants, read at the quoted call sites.  They are all
# DISTINCT so a swap between two calls is visible.
NVML_CLOCK_SM = 1  # L504 nvmlDeviceGetMaxClockInfo(handle, pynvml.NVML_CLOCK_SM)
NVML_TEMPERATURE_SLOWDOWN = 2  # L513-515 ...GetTemperatureThreshold(..., ..._SLOWDOWN)
NVML_CLOCK_MEM = 3  # L521 / L525 nvmlDeviceGet*ClockInfo(..., pynvml.NVML_CLOCK_MEM)
NVML_PCIE_UTIL_TX_BYTES = 4  # L533 nvmlDeviceGetPcieThroughput(..., ..._TX_BYTES)
NVML_PCIE_UTIL_RX_BYTES = 5  # L537 nvmlDeviceGetPcieThroughput(..., ..._RX_BYTES)

# Shipped return-key spellings (L495 / L499 / L503 / L508 / L510 / L512)
KEY_THROTTLE = "throttle_reasons"
KEY_POWER_LIMIT = "power_limit"
KEY_SM_CLOCK_MAX = "sm_clock_max"
KEY_PROCESS_COUNT = "compute_processes_count"
KEY_REPLAY = "pcie_replay_counter"
KEY_SLOWDOWN = "temp_slowdown_threshold"

# Injected NVML returns -> the shipped arithmetic this battery pins:
#   L495 int(7)                        -> 7
#   L499 float(230000 / 1000.0)        -> 230.0
#   L503 int(1800)                     -> 1800
#   L508 len((PROCESS_A, PROCESS_B))   -> 2
#   L510 int(3)                        -> 3
#   L512 float(83.0)                   -> 83.0
THROTTLE_VALUE = 7
POWER_LIMIT_MW = 230_000
SM_CLOCK_MHZ = 1800
REPLAY_COUNTER = 3
SLOWDOWN_C = 83.0
PROCESSES = (PROCESS_A, PROCESS_B)

# Answer this file's doubles give for a constant they were not primed with.  It
# is a plain number (never equal to any injected metric) so a second-arg->None
# mutant keeps the shipped return TYPE while the journal and the dict both see
# the wrong selection.
UNSELECTED = -957

EXPECTED_HIGH_VALUE: dict[str, Any] = {
    KEY_THROTTLE: THROTTLE_VALUE,
    KEY_POWER_LIMIT: 230.0,
    KEY_SM_CLOCK_MAX: SM_CLOCK_MHZ,
    KEY_PROCESS_COUNT: len(PROCESSES),
    KEY_REPLAY: REPLAY_COUNTER,
    KEY_SLOWDOWN: SLOWDOWN_C,
}

# The shipped call ORDER of the high-value block (L496 -> L513) and each call's
# shipped positional-argument tuple.
HIGH_VALUE_CALL_SEQUENCE: list[tuple[str, tuple[Any, ...]]] = [
    ("nvmlDeviceGetCurrentClocksThrottleReasons", (HANDLE,)),  # L496
    ("nvmlDeviceGetPowerManagementLimit", (HANDLE,)),  # L500
    ("nvmlDeviceGetMaxClockInfo", (HANDLE, NVML_CLOCK_SM)),  # L504
    ("nvmlDeviceGetComputeRunningProcesses", (HANDLE,)),  # L507
    ("nvmlDeviceGetPcieReplayCounter", (HANDLE,)),  # L510
    ("nvmlDeviceGetTemperatureThreshold", (HANDLE, NVML_TEMPERATURE_SLOWDOWN)),  # L513-515
]

# Every metric call of the function (both value tiers); ``journal()`` filters the
# two ``_initialize_nvml`` calls (L212 / L217-218) out with this tuple.
METRIC_CALLS: frozenset[str] = frozenset(
    (
        "nvmlDeviceGetCurrentClocksThrottleReasons",  # L496
        "nvmlDeviceGetPowerManagementLimit",  # L500
        "nvmlDeviceGetMaxClockInfo",  # L504 and L525
        "nvmlDeviceGetComputeRunningProcesses",  # L507
        "nvmlDeviceGetPcieReplayCounter",  # L510
        "nvmlDeviceGetTemperatureThreshold",  # L513-515
        "nvmlDeviceGetClockInfo",  # L521
        "nvmlDeviceGetCurrPcieLinkGeneration",  # L528
        "nvmlDeviceGetCurrPcieLinkWidth",  # L530
        "nvmlDeviceGetPcieThroughput",  # L533 and L537
        "nvmlDeviceGetEncoderUtilization",  # L540
        "nvmlDeviceGetDecoderUtilization",  # L543
        "nvmlDeviceGetBAR1MemoryInfo",  # L546
    )
)

# Shipped arity of every NVML call this file can reach.  A double that accepts
# any arity would let a ``drop_arg`` mutant pass as an equivalent call, so the
# stubs below enforce it.
_STUB_ARITY: dict[str, int] = {
    "nvmlInit": 0,  # L212
    "nvmlDeviceGetHandleByIndex": 1,  # L217
    "nvmlDeviceGetName": 1,  # L218
    "nvmlDeviceGetCurrentClocksThrottleReasons": 1,  # L496
    "nvmlDeviceGetPowerManagementLimit": 1,  # L500
    "nvmlDeviceGetMaxClockInfo": 2,  # L504 / L525
    "nvmlDeviceGetComputeRunningProcesses": 1,  # L507
    "nvmlDeviceGetPcieReplayCounter": 1,  # L510
    "nvmlDeviceGetTemperatureThreshold": 2,  # L513-515
    "nvmlDeviceGetClockInfo": 2,  # L521
    "nvmlDeviceGetCurrPcieLinkGeneration": 1,  # L528
    "nvmlDeviceGetCurrPcieLinkWidth": 1,  # L530
    "nvmlDeviceGetPcieThroughput": 2,  # L533 / L537
    "nvmlDeviceGetEncoderUtilization": 1,  # L540
    "nvmlDeviceGetDecoderUtilization": 1,  # L543
    "nvmlDeviceGetBAR1MemoryInfo": 1,  # L546
}


class NVMLError(Exception):
    """Stand-in for ``pynvml.NVMLError`` - the class the shipped blocks suppress.

    Same role as the ``mock_pynvml`` fixture's ``mock_nvml.NVMLError = Exception``
    (test_gpu_monitor.py), but a REAL class so that ``contextlib.suppress``'s
    ``issubclass`` semantics are genuinely exercised (a ``suppress(None)``
    mutant has to blow up on ``issubclass(NVMLError, None)``, and a ``Mock()``
    would swallow that).
    """


class ByConstant:
    """A return-table entry selected by the call's SECOND positional (the NVML
    enum constant).

    ``nvmlDeviceGetMaxClockInfo`` (L504 SM / L525 MEM) and
    ``nvmlDeviceGetPcieThroughput`` (L533 TX / L537 RX) are each called twice in
    the shipped function with different constants, so a name-keyed table alone
    cannot give the two blocks independent outcomes.  An unrecognised constant
    (e.g. the ``None`` of a second-arg->None mutant) answers ``default``, which
    keeps the shipped return type while making the selection visible.
    """

    def __init__(self, cases: dict[object, Any], default: Any = UNSELECTED) -> None:
        self.cases = cases
        self.default = default

    def __call__(self, args: tuple[Any, ...]) -> Any:
        outcome = self.cases.get(args[1], self.default) if len(args) > 1 else self.default
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakePynvml:
    """``sys.modules["pynvml"]`` double: EXACT-ARITY recording stubs.

    Each stub journals its positional args, raises ``TypeError`` when the arity
    does not match the shipped call (which is what makes the ``drop_arg`` family
    observable instead of equivalent), and then yields the table entry - a
    value, a raised exception instance, or a ``ByConstant`` selection.
    """

    NVMLError: ClassVar[type[Exception]] = NVMLError
    NVML_CLOCK_SM: ClassVar[int] = NVML_CLOCK_SM
    NVML_TEMPERATURE_THRESHOLD_SLOWDOWN: ClassVar[int] = NVML_TEMPERATURE_SLOWDOWN
    NVML_CLOCK_MEM: ClassVar[int] = NVML_CLOCK_MEM
    NVML_PCIE_UTIL_TX_BYTES: ClassVar[int] = NVML_PCIE_UTIL_TX_BYTES
    NVML_PCIE_UTIL_RX_BYTES: ClassVar[int] = NVML_PCIE_UTIL_RX_BYTES

    def __init__(self, returns: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.returns: dict[str, Any] = dict(returns or {})
        for name, arity in _STUB_ARITY.items():
            setattr(self, name, self._stub(name, arity))

    def _stub(self, name: str, arity: int):
        def stub(*args: Any) -> Any:
            self.calls.append((name, tuple(args)))
            if len(args) != arity:
                msg = f"pynvml.{name}() takes exactly {arity} positional args, got {len(args)}"
                raise TypeError(msg)
            outcome = self.returns[name]
            if isinstance(outcome, ByConstant):
                return outcome(tuple(args))
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        return stub

    def journal(self) -> list[tuple[str, tuple[Any, ...]]]:
        """Metric-call journal (the init-time NVML calls are filtered out)."""
        return [(name, args) for name, args in self.calls if name in METRIC_CALLS]

    def fault_everything(self) -> None:
        """Make EVERY metric call raise ``NVMLError`` (both value tiers)."""
        for name in _STUB_ARITY:
            if name in METRIC_CALLS:
                self.returns[name] = NVMLError(f"nvml fault at {name}")


def returns_with(**overrides: Any) -> dict[str, Any]:
    """The success-path NVML return table, with per-test overrides applied.

    The MEDIUM block (L519-L547) defaults to a uniform ``NVMLError`` fault: each
    of its blocks is suppressed on its own, so a returned dict in this file is
    exactly the six high-value keys.  (g04b owns that block's values - see
    ``test_gpu_monitor_batch28_05.py``.)
    """
    mem_fault = NVMLError("medium block disabled in this battery")
    table: dict[str, Any] = {
        "nvmlInit": None,
        "nvmlDeviceGetHandleByIndex": HANDLE,
        "nvmlDeviceGetName": "NVIDIA RTX A5500",
        "nvmlDeviceGetCurrentClocksThrottleReasons": THROTTLE_VALUE,
        "nvmlDeviceGetPowerManagementLimit": POWER_LIMIT_MW,
        "nvmlDeviceGetMaxClockInfo": ByConstant({NVML_CLOCK_SM: SM_CLOCK_MHZ}, default=mem_fault),
        "nvmlDeviceGetComputeRunningProcesses": PROCESSES,
        "nvmlDeviceGetPcieReplayCounter": REPLAY_COUNTER,
        "nvmlDeviceGetTemperatureThreshold": SLOWDOWN_C,
        "nvmlDeviceGetClockInfo": mem_fault,
        "nvmlDeviceGetCurrPcieLinkGeneration": mem_fault,
        "nvmlDeviceGetCurrPcieLinkWidth": mem_fault,
        "nvmlDeviceGetPcieThroughput": ByConstant({}, default=mem_fault),
        "nvmlDeviceGetEncoderUtilization": mem_fault,
        "nvmlDeviceGetDecoderUtilization": mem_fault,
        "nvmlDeviceGetBAR1MemoryInfo": mem_fault,
    }
    table.update(overrides)
    return table


@pytest.fixture
def fake_pynvml():
    """Inject a fresh ``pynvml`` double for one test, restore it afterwards."""
    fake = FakePynvml(returns_with())
    saved = sys.modules.get("pynvml")
    sys.modules["pynvml"] = fake
    try:
        yield fake
    finally:
        if saved is None:
            sys.modules.pop("pynvml", None)
        else:
            sys.modules["pynvml"] = saved


@pytest.fixture
def monitor(fake_pynvml):
    """A GPUMonitor whose NVML state is this file's double + the HANDLE sentinel."""
    with patch.object(M.GPUMonitor, "_check_nvidia_smi", autospec=True, return_value=None):
        # L191 `self._initialize_nvml()` runs against the double and stores
        # nvmlDeviceGetHandleByIndex(0) - HANDLE - into self._gpu_handle (L217).
        # L194-195: _gpu_available is True so _check_nvidia_smi is never
        # reached; the autospec patch is the deterministic guard if that ever
        # changes (it also keeps shutil.which/subprocess out of the battery).
        mon = M.GPUMonitor(poll_interval=60.0, history_minutes=5, http_timeout=1.0)
    assert mon._gpu_handle is HANDLE  # fixture pre-condition, not a shipped claim
    return mon


# =============================================================================
# Values leg - the exact shipped 6-key return dict of the high-value block
# =============================================================================


def test_high_value_success_path_returns_the_six_shipped_metrics(monitor) -> None:
    """Every high-value metric lands under its shipped key and shipped value.

    Injected NVML returns are this file's (throttle 7, limit 230000 mW, max SM
    clock 1800 MHz, two compute processes, replay 3, slowdown 83).  Shipped
    L495-L516 turns them into ``{"throttle_reasons": 7, "power_limit": 230.0,
    "sm_clock_max": 1800, "compute_processes_count": 2, "pcie_replay_counter":
    3, "temp_slowdown_threshold": 83.0}`` - and nothing else, because the medium
    block faults in this scenario.

    Kills (``mN`` = ``..._get_extended_metrics__mutmut_N``):
      * the six assign->None mutants m4/m10/m18/m29/m33/m39 - their key is
        missing from the dict entirely,
      * all twelve key-string mutants m5/m6, m11/m12, m19/m20, m30/m31,
        m34/m35, m40/m41 - the renamed key is present and the shipped one is not,
      * m14 (``/ 1000.0`` -> ``* 1000.0``: 230000000.0) and m16 (``1000.0`` ->
        ``1001.0``: 229.77022977022978),
      * m27 (``processes = None``) - the shipped ``len(processes)`` of L508
        raises ``TypeError``, which ``suppress(pynvml.NVMLError)`` does not
        swallow, so the method raises instead of returning,
      * the wrapper call_arg mutants m7/m13/m21/m36/m42 - ``int(None)`` /
        ``float(None)`` raises ``TypeError`` and escapes.
    """
    metrics = monitor._get_extended_metrics()

    assert metrics == EXPECTED_HIGH_VALUE
    assert metrics[KEY_POWER_LIMIT] == 230.0  # L499-500 float(230000 / 1000.0)
    assert isinstance(metrics[KEY_POWER_LIMIT], float)  # L499 float(...)
    assert isinstance(metrics[KEY_THROTTLE], int)  # L495 int(...)
    assert isinstance(metrics[KEY_PROCESS_COUNT], int)  # L508 len(...)
    assert isinstance(metrics[KEY_SLOWDOWN], float)  # L512 float(...)


# =============================================================================
# Wiring leg - the shipped handle + constant reach the right NVML call
# =============================================================================


def test_high_value_nvml_calls_receive_the_handle_and_the_shipped_constant(
    monitor,
) -> None:
    """The block's NVML journal is EXACTLY the shipped call sequence.

    The handle is a private sentinel, so ``is``-identity of the first positional
    is a hard observable, and the second positional must be the shipped NVML
    constant.  The doubles enforce the shipped arity, so a collapsed call raises
    ``TypeError`` - which escapes ``suppress(pynvml.NVMLError)`` - instead of
    looking like the shipped two-argument call.

    Kills:
      * m2 (L491 ``handle = None``) - no recorded first positional is HANDLE,
      * arg->None m8 (L496), m15 (L500), m22 (L504), m28 (L507), m37 (L510),
        m43 (L513-515) - arity intact but the handle slot is ``None``, a
        journal-only observable,
      * second-arg->None m23 (``NVML_CLOCK_SM`` -> ``None``) and m44
        (``NVML_TEMPERATURE_THRESHOLD_SLOWDOWN`` -> ``None``) - both still hand
        back a number, so only this journal (and the ``UNSELECTED`` answer of the
        primed value table) sees them,
      * drop_arg m24/m25 (L504) and m45/m46 (L513-515) - arity collapse raises
        ``TypeError`` and shrinks the recorded args,
      * wrapper call_arg m7/m13/m21/m36/m42 - the inner call never happens, so
        its journal entry is missing and ``int(None)`` raises.
    """
    metrics = monitor._get_extended_metrics()
    nvml: FakePynvml = sys.modules["pynvml"]
    journal = nvml.journal()[: len(HIGH_VALUE_CALL_SEQUENCE)]

    assert journal == HIGH_VALUE_CALL_SEQUENCE
    assert [args[0] for _name, args in journal] == [HANDLE] * 6  # L491 wiring
    assert journal[2] == ("nvmlDeviceGetMaxClockInfo", (HANDLE, NVML_CLOCK_SM))  # L504
    assert journal[5] == (  # L513-515
        "nvmlDeviceGetTemperatureThreshold",
        (HANDLE, NVML_TEMPERATURE_SLOWDOWN),
    )
    assert metrics[KEY_SM_CLOCK_MAX] == SM_CLOCK_MHZ  # L503 returns the SM clock
    assert metrics[KEY_SLOWDOWN] == SLOWDOWN_C  # L512 returns the slowdown limit


def test_empty_gpu_handle_is_still_passed_through_unchanged(monitor) -> None:
    """Control: the method never substitutes a handle - it forwards the local.

    L491 is a plain read of ``self._gpu_handle``.  With the attribute set to
    ``None`` the shipped code still calls every high-value NVML function with
    ``None`` (it is the double's arity check that objects to a dropped
    argument, never the shipped code) and still writes the six metrics.  This
    pins the pass-through that the identity leg above leans on: the mutant
    ``handle = None`` produces this journal while the instance still holds
    HANDLE, which is precisely why the test above asserts identity.
    """
    monitor._gpu_handle = None

    metrics = monitor._get_extended_metrics()

    nvml: FakePynvml = sys.modules["pynvml"]
    # Same shape as the shipped sequence with the handle slot emptied out (the
    # NVML constant of the two 2-arg calls is still passed, L504 / L513-515).
    assert nvml.journal()[: len(HIGH_VALUE_CALL_SEQUENCE)] == [
        (name, (None, *args[1:])) for name, args in HIGH_VALUE_CALL_SEQUENCE
    ]
    assert metrics == EXPECTED_HIGH_VALUE


# =============================================================================
# Suppress leg - every block leans on its own contextlib.suppress call
# =============================================================================


def test_nvml_fault_is_swallowed_only_by_its_own_suppress_call(monitor) -> None:
    """All 14 blocks suppress independently -> an EMPTY dict, never a raise.

    Every metric call in the function faults with ``NVMLError``.  Shipped, each
    metric line sits inside its own ``with contextlib.suppress(pynvml.NVMLError)``
    (L494, L498, L502, L506, L509, L511 for the high tier and L519, L523, L527,
    L529, L531, L535, L539, L542 for the medium tier), so the method returns
    ``{}``.

    The six g04a suppress mutants rewrite one such call to
    ``contextlib.suppress(None)``; the bank cannot say WHICH of the 14 identical
    sites the survivor came from, so every candidate must redden.  On every one
    of the 14 positions the mutated block's body raises ``NVMLError`` and the
    mutated ``__exit__`` then evaluates ``issubclass(NVMLError, None)``, which
    raises ``TypeError`` - an exception no ``with`` body here is protected
    against - so the shipped empty-dict contract breaks wherever the mutation
    lands: m3 (L494), m9 (L498), m17 (L502), m26 (L506), m32 (L509), m38 (L511).
    """
    nvml: FakePynvml = sys.modules["pynvml"]
    nvml.fault_everything()

    assert monitor._get_extended_metrics() == {}


@pytest.mark.parametrize(
    ("fault_call", "lost_key"),
    [
        pytest.param("nvmlDeviceGetCurrentClocksThrottleReasons", KEY_THROTTLE, id="L496"),
        pytest.param("nvmlDeviceGetPowerManagementLimit", KEY_POWER_LIMIT, id="L500"),
        pytest.param("nvmlDeviceGetMaxClockInfo", KEY_SM_CLOCK_MAX, id="L504"),
        pytest.param("nvmlDeviceGetComputeRunningProcesses", KEY_PROCESS_COUNT, id="L507"),
        pytest.param("nvmlDeviceGetPcieReplayCounter", KEY_REPLAY, id="L510"),
        pytest.param("nvmlDeviceGetTemperatureThreshold", KEY_SLOWDOWN, id="L513"),
    ],
)
def test_each_high_value_block_independently_suppresses_its_own_nvml_fault(
    monitor,
    fault_call: str,
    lost_key: str,
) -> None:
    """Control: one block faulting costs exactly ONE key - five siblings land.

    ``_get_extended_metrics`` has no all-or-nothing failure mode: a
    ``NVMLError`` raised by the call named ``fault_call`` is swallowed by that
    block's own ``with contextlib.suppress(pynvml.NVMLError)`` and never reaches
    the other blocks, so the returned dict is the shipped six keys minus the
    faulted one.
    """
    nvml: FakePynvml = sys.modules["pynvml"]
    nvml.returns[fault_call] = NVMLError(f"nvml fault at {fault_call}")

    metrics = monitor._get_extended_metrics()

    expected = dict(EXPECTED_HIGH_VALUE)
    del expected[lost_key]
    assert metrics == expected
    assert lost_key not in metrics
