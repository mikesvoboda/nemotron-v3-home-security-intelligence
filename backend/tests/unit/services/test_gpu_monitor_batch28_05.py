"""S3 batch-28 lane gm05 - ``gpu_monitor`` G04b kill battery (66 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda
- byte-identical to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/gpu_monitor/manifest.json`` group 10 (``G04b _get_extended_metrics:
medium block + encoder/decoder/BAR1 + suppress args`` - 66 KILLABLE / 0
EQUIVALENT), plus ``group_10.keys`` and ``survivors.json`` for the exact per-key
diffs.  Splice report ``splice-group_10.json``: 58 clean + 6 twin + 2
UNPARSEABLE (``..._get_extended_metrics__mutmut_103`` and ``__mutmut_104``, the
two ``drop_arg`` mutants of the L545 ``suppress(pynvml.NVMLError,
AttributeError)`` call - mutmut reprints a ``drop_arg`` as an empty ``after`` so
the harness splices ``with :`` and cannot compile it).  Those two keys are
proved by manual ``mutate.py``-style probes - see
``/tmp/wp-pw/gm/manual_05.py`` (evidence JSON:
``/tmp/wp-pw/gm/manual_05_result.json``), which builds each mutant by applying
the bank diff as Python would at L545, installs it in a symlink shadow of this
lane and runs THIS file against it.  Every other key of the group is proven
through ``/tmp/wp-b28/replay_lib.py``.

Target: the MEDIUM-VALUE block of ``GPUMonitor._get_extended_metrics`` -
L519-L547 - plus the encoder/decoder tuple-unpack statements (L540, L543), the
two-argument ``contextlib.suppress`` of L545 and the BAR1 arithmetic of L547.
The function logs nothing (no ``logger`` call exists between L482 and L549), so
this battery carries no caplog window and no clock seam: the observables are the
returned dict, the NVML call journal, and what escapes the call.  The HIGH-VALUE
block (L491-L516) is driven by ``test_gpu_monitor_batch28_04.py`` and is
injected here as a uniform ``NVMLError`` fault so this file's dict comparisons
are exactly the nine medium keys.

Test -> mutant-key map
======================
Every key below is in ``group_10.keys`` (the bank's
``...xǁGPUMonitorǁ_get_extended_metrics__mutmut_N`` abbreviated to ``mN``).

``test_medium_success_path_returns_the_nine_shipped_metrics``
  Exact 9-key equality on the returned dict with this file's injected returns.
  - assign->None (key MISSING): m48 (L520), m57 (L524), m66 (L528), m72 (L530),
    m78 (L532), m87 (L536), m107 (L547), and m105 (L546 ``bar1_info = None`` ->
    the shipped ``bar1_info.bar1Used`` raises ``AttributeError``, which L545's
    ``suppress(pynvml.NVMLError, AttributeError)`` DOES swallow, so the shipped
    ``bar1_used`` key simply never lands).
  - key wrapXX / upper (RENAMED key + missing shipped key): m49/m50, m58/m59,
    m67/m68, m73/m74, m79/m80, m88/m89, m108/m109 - all 14.
  - tuple-unpack assign->None: m96 (L540 ``enc_util, _ = None``) and m99 (L543) -
    unpacking ``None`` raises ``TypeError``, which ``suppress(pynvml.NVMLError)``
    does not swallow, so the call raises instead of returning.
  - the six wrapper call_arg mutants m51 (L520), m60 (L524), m69 (L528), m75
    (L530), m81 (L532), m90 (L536): the inner NVML call is replaced by ``None``,
    so ``int(None)`` raises ``TypeError`` and escapes.
  - drop_arg arity collapse: m54/m55 (L521), m63/m64 (L525), m84/m85 (L533),
    m93/m94 (L537) - this file's doubles take exactly the shipped arity, so a
    collapsed call raises ``TypeError`` outside the suppress.
  - second-arg->None m53 (L521) and m62 (L525): the value table selects on the
    NVML constant, so ``None`` answers ``UNSELECTED``... and in THIS file the
    unselected answer for those two calls is an ``NVMLError`` fault (only the
    primed constants have values), which drops ``memory_clock`` /
    ``memory_clock_max`` from the dict.

``test_medium_nvml_calls_receive_the_handle_and_the_shipped_constants``
  The journal of ALL 15 metric calls of the function (name + positional args, in
  shipped source order) compared EXACTLY.  The first six entries are the
  high-tier calls of the faulting injection above - they are still journalled,
  because a stub journals its args before it raises.
  - m52 (L521), m61 (L525), m70 (L528), m76 (L530), m82 (L533), m91 (L537), m97
    (L540), m100 (L543), m106 (L546): ``handle`` -> ``None`` with the arity
    intact, so the returned values are unchanged and ONLY the journal sees it.
  - m83 (L533 ``NVML_PCIE_UTIL_TX_BYTES`` -> ``None``) and m92 (L537 RX): both
    keep arity 2, so the journal's second positional (and the distinct TX/RX
    values this file injects per constant) is the observable.
  - m53/m62/m54/m55/m63/m64/m84/m85/m93/m94 also surface here.

``test_medium_block_faults_never_reach_the_other_blocks``
  ``contextlib.suppress(pynvml.NVMLError)`` -> ``suppress(None)`` - a diff whose
  before-text occurs 14 times inside the function, so the bank cannot
  disambiguate and the harness requires EVERY candidate to redden.  Shipped:
  when EVERY metric call faults with ``NVMLError``, all 14 blocks suppress
  independently and the method returns ``{}``.  On ANY of the 14 positions the
  mutated block's ``__exit__`` evaluates ``issubclass(NVMLError, None)`` ->
  ``TypeError`` escapes the still-raising body, so the leg reddens at every
  position (OCCURRENCE-TWIN SOUNDNESS): m47 (L519), m56 (L523), m65 (L527), m71
  (L529), m77 (L531), m86 (L535).

``test_bar1_block_suppresses_either_fault_flavor_without_a_bar1_key``
  The audit-correction #5 leg: BAR1 gets BOTH fault flavors, because an
  NVMLError-only injection is vacuous for m102/m104.  Shipped swallows
  ``NVMLError`` (call raises) AND ``AttributeError`` (returned object lacks
  ``bar1Used``), and both flavors yield the 8-key dict with ``bar1_used``
  ABSENT.  Kill map: m101 ``suppress(None, AttributeError)`` reddens under BOTH
  flavors (``except None:`` -> ``TypeError``), m103 ``suppress(AttributeError)``
  reddens under the NVMLError flavor (it escapes uncaught), m102
  ``suppress(pynvml.NVMLError, None)`` and m104 ``suppress(pynvml.NVMLError, )``
  (the trailing-comma single-arg form) redden under the AttributeError flavor.
  m103/m104 are the two manually-proved keys.

``test_bar1_used_is_whole_megabytes_of_the_nvml_byte_counter``
  L547 ``int(bar1_info.bar1Used / (1024 * 1024))`` pinned on two injected
  counters (2 MiB -> 2, 5 MiB -> 5) with an ``int`` type assert.  Kills m110
  (``int(None)`` raises), m111 (``/`` -> ``*`` -> 2199023255552), m112
  (``(1024 * 1024)`` -> ``(1024 / 1024)`` -> 2097152) and both
  ``number:1024->1025`` twins m113/m114 (``int(2097152 / (1025 * 1024))`` == 1).

``test_encoder_and_decoder_utilization_take_the_first_tuple_element``
  L540-L544: ``enc_util, _ = ...`` keeps the PERCENT and drops the duration, so
  ``(55, 7)`` -> ``{"encoder_utilization": 55}`` and ``(66, 8)`` ->
  ``{"decoder_utilization": 66}``.  Re-states the m96/m99 raise, and pins the
  tuple shape that those two assign->None mutants destroy.

``test_tx_and_rx_differ_only_by_the_nvml_constant``
  Both throughput keys come from the SAME shipped function with different
  constants (L533 TX, L537 RX); the journal pair and the two injected values are
  asserted together, so a swapped/dropped constant cannot be equivalent.

Control legs that kill nothing of their own
(``test_each_medium_block_independently_suppresses_its_own_nvml_fault``, 9
params) pin the shipped per-block isolation of the whole medium tier, so a
killing leg above can never be satisfied by an accidental fall-through.

Shipped behaviour only - nothing here invents a contract.  Every pinned literal
is transcribed from the shipped file at the line quoted in the test that asserts
it, and every value an assertion depends on is injected by this file.

Discipline
----------
* ``pynvml`` is injected through ``sys.modules`` per test (the shipped module is
  imported INSIDE the function, L488) and restored; no import-time global spy,
  no ``scope="session"`` anything, and a real GPU is never touched.
* The doubles are exact-arity call recorders, so ``drop_arg`` cannot hide as an
  equivalent call, and the handle is a private sentinel compared with ``is``.
* No ``time.monotonic`` / ``time.perf_counter`` patch and no clock assertion
  anywhere (g04b contains no timing site); no log assertion because the target
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

HANDLE = object()  # L491 `handle = self._gpu_handle` - identity, never equality

# The shipped NVML enum constants, read at the quoted call sites.  All DISTINCT,
# so a swap between two call sites is visible.
NVML_CLOCK_SM = 1  # L504 nvmlDeviceGetMaxClockInfo(handle, pynvml.NVML_CLOCK_SM)
NVML_TEMPERATURE_SLOWDOWN = 2  # L513-515 ...GetTemperatureThreshold(..., ..._SLOWDOWN)
NVML_CLOCK_MEM = 3  # L521 nvmlDeviceGetClockInfo / L525 ...GetMaxClockInfo
NVML_PCIE_UTIL_TX_BYTES = 4  # L533 nvmlDeviceGetPcieThroughput(..., ..._TX_BYTES)
NVML_PCIE_UTIL_RX_BYTES = 5  # L537 nvmlDeviceGetPcieThroughput(..., ..._RX_BYTES)

# Shipped return-key spellings of the medium tier (L520 / L524 / L528 / L530 /
# L532 / L536 / L541 / L544 / L547)
KEY_MEM_CLOCK = "memory_clock"
KEY_MEM_CLOCK_MAX = "memory_clock_max"
KEY_LINK_GEN = "pcie_link_gen"
KEY_LINK_WIDTH = "pcie_link_width"
KEY_TX = "pcie_tx_throughput"
KEY_RX = "pcie_rx_throughput"
KEY_ENCODER = "encoder_utilization"
KEY_DECODER = "decoder_utilization"
KEY_BAR1 = "bar1_used"

# Injected NVML returns -> the shipped arithmetic this battery pins:
#   L520 int(8001)                                  -> 8001
#   L524 int(8501)                                  -> 8501
#   L528 int(4)                                     -> 4
#   L530 int(16)                                    -> 16
#   L532 int(100000)                                -> 100000
#   L536 int(80000)                                 -> 80000
#   L540 enc_util, _ = (55, 7); int(55)             -> 55
#   L543 dec_util, _ = (66, 8); int(66)             -> 66
#   L547 int(2097152 / (1024 * 1024))               -> 2
MEM_CLOCK_MHZ = 8001
MEM_CLOCK_MAX_MHZ = 8501
LINK_GEN = 4
LINK_WIDTH = 16
TX_KB = 100_000
RX_KB = 80_000
ENC_PERCENT = 55
ENC_DURATION_MS = 7
DEC_PERCENT = 66
DEC_DURATION_MS = 8
BAR1_USED_BYTES = 2 * 1024 * 1024
BAR1_USED_MB = 2

EXPECTED_MEDIUM_VALUE: dict[str, Any] = {
    KEY_MEM_CLOCK: MEM_CLOCK_MHZ,
    KEY_MEM_CLOCK_MAX: MEM_CLOCK_MAX_MHZ,
    KEY_LINK_GEN: LINK_GEN,
    KEY_LINK_WIDTH: LINK_WIDTH,
    KEY_TX: TX_KB,
    KEY_RX: RX_KB,
    KEY_ENCODER: ENC_PERCENT,
    KEY_DECODER: DEC_PERCENT,
    KEY_BAR1: BAR1_USED_MB,
}

# The shipped call order of the WHOLE function (L496 -> L546) with each call's
# shipped positional tuple.  Entries 0-5 are the high tier (injected as faults in
# this file, still journalled); entries 6-14 are g04b's medium tier.
FULL_CALL_SEQUENCE: list[tuple[str, tuple[Any, ...]]] = [
    ("nvmlDeviceGetCurrentClocksThrottleReasons", (HANDLE,)),  # L496
    ("nvmlDeviceGetPowerManagementLimit", (HANDLE,)),  # L500
    ("nvmlDeviceGetMaxClockInfo", (HANDLE, NVML_CLOCK_SM)),  # L504
    ("nvmlDeviceGetComputeRunningProcesses", (HANDLE,)),  # L507
    ("nvmlDeviceGetPcieReplayCounter", (HANDLE,)),  # L510
    ("nvmlDeviceGetTemperatureThreshold", (HANDLE, NVML_TEMPERATURE_SLOWDOWN)),  # L513-515
    ("nvmlDeviceGetClockInfo", (HANDLE, NVML_CLOCK_MEM)),  # L521
    ("nvmlDeviceGetMaxClockInfo", (HANDLE, NVML_CLOCK_MEM)),  # L525
    ("nvmlDeviceGetCurrPcieLinkGeneration", (HANDLE,)),  # L528
    ("nvmlDeviceGetCurrPcieLinkWidth", (HANDLE,)),  # L530
    ("nvmlDeviceGetPcieThroughput", (HANDLE, NVML_PCIE_UTIL_TX_BYTES)),  # L533
    ("nvmlDeviceGetPcieThroughput", (HANDLE, NVML_PCIE_UTIL_RX_BYTES)),  # L537
    ("nvmlDeviceGetEncoderUtilization", (HANDLE,)),  # L540
    ("nvmlDeviceGetDecoderUtilization", (HANDLE,)),  # L543
    ("nvmlDeviceGetBAR1MemoryInfo", (HANDLE,)),  # L546
]
HIGH_TIER_CALLS = 6  # entries 0..5 above; the medium tier starts at L521

# Shipped arity of every NVML call this file can reach.  A double that accepted
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

# Every metric call of the function - ``journal()`` filters the two
# ``_initialize_nvml`` calls (L212 / L217-218) out with this set.
METRIC_CALLS: frozenset[str] = frozenset(name for name, _args in FULL_CALL_SEQUENCE)


class NVMLError(Exception):
    """Stand-in for ``pynvml.NVMLError`` - the class the shipped blocks suppress.

    Same role as the ``mock_pynvml`` fixture's ``mock_nvml.NVMLError = Exception``
    (test_gpu_monitor.py), but a REAL class so ``contextlib.suppress``'s
    ``issubclass`` semantics are genuinely exercised: this group's whole
    ``suppress``-argument family (m101-m104) is only observable through it.
    """


class Bar1Info:
    """The shipped ``nvmlDeviceGetBAR1MemoryInfo`` result shape (L547 reads
    ``bar1_info.bar1Used``, an NVML byte counter)."""

    def __init__(self, bar1_used: int) -> None:
        self.bar1Used = bar1_used


class Bar1InfoWithoutCounter:
    """A BAR1 result object LACKING ``bar1Used`` - the shipped code then hits
    ``AttributeError``, which is the second flavor L545 suppresses."""

    def __init__(self) -> None:
        self.bar1Free = 1024  # attribute present, `bar1Used` absent


class ByConstant:
    """A return-table entry selected by the call's SECOND positional (the NVML
    enum constant).

    ``nvmlDeviceGetMaxClockInfo`` (L504 SM / L525 MEM) and
    ``nvmlDeviceGetPcieThroughput`` (L533 TX / L537 RX) are each called more than
    once with different constants, so a name-keyed table alone cannot give those
    blocks independent outcomes.  An unrecognised constant answers ``default``,
    which here is an NVML fault: that is what turns a wrong/dropped constant
    (m53, m62) into a missing key instead of a reused sibling value.
    """

    def __init__(self, cases: dict[object, Any], default: Any) -> None:
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
    observable instead of equivalent), then yields the table entry - a value, a
    raised exception instance, or a ``ByConstant`` selection.
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


def medium_fault() -> NVMLError:
    return NVMLError("high tier disabled in this battery")


def returns_with(**overrides: Any) -> dict[str, Any]:
    """The medium-tier success return table; the HIGH tier is a uniform fault.

    With the high tier faulting, each of its blocks is suppressed on its own
    (L494-L511) and a returned dict in this file is exactly the nine medium keys
    - the high tier is ``test_gpu_monitor_batch28_04.py``'s territory.
    """
    high_fault = medium_fault()
    table: dict[str, Any] = {
        "nvmlInit": None,
        "nvmlDeviceGetHandleByIndex": HANDLE,
        "nvmlDeviceGetName": "NVIDIA RTX A5500",
        "nvmlDeviceGetCurrentClocksThrottleReasons": high_fault,
        "nvmlDeviceGetPowerManagementLimit": high_fault,
        "nvmlDeviceGetMaxClockInfo": ByConstant(
            {NVML_CLOCK_MEM: MEM_CLOCK_MAX_MHZ}, default=high_fault
        ),
        "nvmlDeviceGetComputeRunningProcesses": high_fault,
        "nvmlDeviceGetPcieReplayCounter": high_fault,
        "nvmlDeviceGetTemperatureThreshold": high_fault,
        "nvmlDeviceGetClockInfo": ByConstant({NVML_CLOCK_MEM: MEM_CLOCK_MHZ}, default=high_fault),
        "nvmlDeviceGetCurrPcieLinkGeneration": LINK_GEN,
        "nvmlDeviceGetCurrPcieLinkWidth": LINK_WIDTH,
        "nvmlDeviceGetPcieThroughput": ByConstant(
            {NVML_PCIE_UTIL_TX_BYTES: TX_KB, NVML_PCIE_UTIL_RX_BYTES: RX_KB}, default=high_fault
        ),
        "nvmlDeviceGetEncoderUtilization": (ENC_PERCENT, ENC_DURATION_MS),
        "nvmlDeviceGetDecoderUtilization": (DEC_PERCENT, DEC_DURATION_MS),
        "nvmlDeviceGetBAR1MemoryInfo": Bar1Info(BAR1_USED_BYTES),
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
# Values leg - the exact shipped 9-key return dict of the medium block
# =============================================================================


def test_medium_success_path_returns_the_nine_shipped_metrics(monitor) -> None:
    """Every medium metric lands under its shipped key and shipped value.

    Injected returns are this file's (mem clock 8001, max mem clock 8501, link
    gen 4, width 16, TX 100000, RX 80000, encoder ``(55, 7)``, decoder
    ``(66, 8)``, BAR1 2 MiB) and shipped L520-L547 turns them into
    ``{"memory_clock": 8001, "memory_clock_max": 8501, "pcie_link_gen": 4,
    "pcie_link_width": 16, "pcie_tx_throughput": 100000,
    "pcie_rx_throughput": 80000, "encoder_utilization": 55,
    "decoder_utilization": 66, "bar1_used": 2}``.

    Kills (``mN`` = ``..._get_extended_metrics__mutmut_N``):
      * assign->None m48/m57/m66/m72/m78/m87/m107 (their key is missing) and
        m105 (L546 ``bar1_info = None`` -> ``None.bar1Used`` -> ``AttributeError``
        -> suppressed by L545, so ``bar1_used`` never lands),
      * the 14 key-string mutants m49/m50, m58/m59, m67/m68, m73/m74, m79/m80,
        m88/m89, m108/m109,
      * m96 (L540) / m99 (L543) - ``enc_util, _ = None`` raises ``TypeError``,
        which ``suppress(pynvml.NVMLError)`` does not swallow, so the method
        raises instead of returning,
      * wrapper call_arg m51/m60/m69/m75/m81/m90 - ``int(None)`` raises,
      * drop_arg m54/m55, m63/m64, m84/m85, m93/m94 - arity collapse raises
        ``TypeError`` outside the suppress,
      * second-arg->None m53/m62 - the value table has no entry for ``None``, so
        the call faults and the key disappears,
      * the BAR1 arithmetic family m110-m114 (wrong magnitude or a raise).
    """
    metrics = monitor._get_extended_metrics()

    assert metrics == EXPECTED_MEDIUM_VALUE
    assert metrics[KEY_BAR1] == 2  # L547 int(2097152 / (1024 * 1024))
    assert isinstance(metrics[KEY_BAR1], int)  # L547 int(...)
    assert isinstance(metrics[KEY_ENCODER], int)  # L541 int(enc_util)
    assert metrics[KEY_ENCODER] == ENC_PERCENT  # the PERCENT, not the duration
    assert isinstance(metrics[KEY_MEM_CLOCK], int)  # L520 int(...)


# =============================================================================
# Wiring leg - handle + shipped constants reach the right NVML call
# =============================================================================


def test_medium_nvml_calls_receive_the_handle_and_the_shipped_constants(monitor) -> None:
    """The function's NVML journal is EXACTLY the shipped 15-call sequence.

    The handle is a private sentinel, so ``is``-identity of the first positional
    is a hard observable, and each second positional must be the shipped NVML
    constant.  The doubles enforce the shipped arity, so a collapsed call raises
    ``TypeError`` (escaping ``suppress(pynvml.NVMLError)``) instead of masquerading
    as the shipped two-argument call.

    Kills the nine handle->None mutants whose returned values are otherwise
    unchanged - m52 (L521), m61 (L525), m70 (L528), m76 (L530), m82 (L533), m91
    (L537), m97 (L540), m100 (L543), m106 (L546) - plus the throughput-constant
    mutants m83 (TX -> ``None``) and m92 (RX -> ``None``), which keep arity 2 and
    would otherwise reuse the sibling block's value.  m53/m62 and the eight
    ``drop_arg`` keys surface here too.
    """
    monitor._get_extended_metrics()
    nvml: FakePynvml = sys.modules["pynvml"]

    assert nvml.journal() == FULL_CALL_SEQUENCE
    medium = nvml.journal()[HIGH_TIER_CALLS:]
    assert [args[0] for _name, args in medium] == [HANDLE] * 9  # L491 wiring
    assert medium[0] == ("nvmlDeviceGetClockInfo", (HANDLE, NVML_CLOCK_MEM))  # L521
    assert medium[1] == ("nvmlDeviceGetMaxClockInfo", (HANDLE, NVML_CLOCK_MEM))  # L525
    assert medium[4] == (
        "nvmlDeviceGetPcieThroughput",
        (HANDLE, NVML_PCIE_UTIL_TX_BYTES),
    )  # L533
    assert medium[5] == (
        "nvmlDeviceGetPcieThroughput",
        (HANDLE, NVML_PCIE_UTIL_RX_BYTES),
    )  # L537
    assert medium[6] == ("nvmlDeviceGetEncoderUtilization", (HANDLE,))  # L540
    assert medium[7] == ("nvmlDeviceGetDecoderUtilization", (HANDLE,))  # L543
    assert medium[8] == ("nvmlDeviceGetBAR1MemoryInfo", (HANDLE,))  # L546


def test_tx_and_rx_differ_only_by_the_nvml_constant(monitor) -> None:
    """Both throughput keys come from ONE shipped call site pair (L533/L537).

    ``nvmlDeviceGetPcieThroughput`` is called twice, so the only difference
    between ``pcie_tx_throughput`` and ``pcie_rx_throughput`` is the constant.
    The journal pair and the two distinct injected values are asserted together -
    a mutant that drops or ``None``-s the constant can neither keep both values
    nor keep the journal.
    """
    metrics = monitor._get_extended_metrics()
    nvml: FakePynvml = sys.modules["pynvml"]
    throughput = [entry for entry in nvml.journal() if entry[0] == "nvmlDeviceGetPcieThroughput"]

    assert throughput == [
        ("nvmlDeviceGetPcieThroughput", (HANDLE, NVML_PCIE_UTIL_TX_BYTES)),  # L533
        ("nvmlDeviceGetPcieThroughput", (HANDLE, NVML_PCIE_UTIL_RX_BYTES)),  # L537
    ]
    assert metrics[KEY_TX] == TX_KB
    assert metrics[KEY_RX] == RX_KB
    assert metrics[KEY_TX] != metrics[KEY_RX]  # the two constants are not interchangeable


# =============================================================================
# Encoder / decoder tuple unpacking (L540-L544)
# =============================================================================


def test_encoder_and_decoder_utilization_take_the_first_tuple_element(monitor) -> None:
    """``enc_util, _ = ...`` keeps the percent and drops the duration (L540-L544).

    Shipped unpacks the NVML ``(percent, duration)`` pair and writes only the
    percent, so ``(55, 7)`` -> ``55`` and ``(66, 8)`` -> ``66``; the duration is
    never written under any key.  Under ``enc_util, _ = None`` (m96) /
    ``dec_util, _ = None`` (m99) the unpacking raises ``TypeError``, which
    ``suppress(pynvml.NVMLError)`` does not swallow - the method raises instead
    of returning a dict.
    """
    metrics = monitor._get_extended_metrics()

    assert metrics[KEY_ENCODER] == ENC_PERCENT  # L541 int(enc_util)
    assert metrics[KEY_DECODER] == DEC_PERCENT  # L544 int(dec_util)
    assert ENC_DURATION_MS not in metrics.values()  # L540 the duration is discarded
    assert DEC_DURATION_MS not in metrics.values()


# =============================================================================
# BAR1 arithmetic (L547)
# =============================================================================


@pytest.mark.parametrize(
    ("bar1_used_bytes", "expected_mb"),
    [
        pytest.param(2 * 1024 * 1024, 2, id="2MiB"),
        pytest.param(5 * 1024 * 1024, 5, id="5MiB"),
    ],
)
def test_bar1_used_is_whole_megabytes_of_the_nvml_byte_counter(
    monitor, bar1_used_bytes: int, expected_mb: int
) -> None:
    """L547 ``int(bar1_info.bar1Used / (1024 * 1024))`` - bytes to whole MB.

    The divisor is the shipped ``1024 * 1024``, so 2 MiB is ``2`` and 5 MiB is
    ``5``.  m111 (``*`` instead of ``/``) yields 2199023255552, m112
    (``(1024 / 1024)`` = 1) yields 2097152, and both ``number:1024->1025`` twins
    m113/m114 yield ``int(2097152 / (1025 * 1024)) == 1``; m110
    (``int(None)``) raises ``TypeError``, which the L545 suppress does not
    swallow.
    """
    nvml: FakePynvml = sys.modules["pynvml"]
    nvml.returns["nvmlDeviceGetBAR1MemoryInfo"] = Bar1Info(bar1_used_bytes)

    metrics = monitor._get_extended_metrics()

    assert metrics[KEY_BAR1] == expected_mb
    assert metrics == {**EXPECTED_MEDIUM_VALUE, KEY_BAR1: expected_mb}


# =============================================================================
# Suppress leg - the per-block isolation and the two-argument L545 block
# =============================================================================


def test_medium_block_faults_never_reach_the_other_blocks(monitor) -> None:
    """All 14 blocks suppress independently -> an EMPTY dict, never a raise.

    Every metric call of the function faults with ``NVMLError``.  Shipped, each
    metric line sits inside its own ``with contextlib.suppress(...)`` (L494,
    L498, L502, L506, L509, L511, L519, L523, L527, L529, L531, L535, L539 and
    the two-argument L545), so the method returns ``{}``.

    The six g04b suppress mutants rewrite one of the single-argument calls to
    ``contextlib.suppress(None)``; the bank cannot say WHICH of the 14 identical
    sites the survivor came from, so every candidate must redden.  On each of the
    14 positions the mutated body raises ``NVMLError`` and the mutated
    ``__exit__`` then evaluates ``issubclass(NVMLError, None)`` -> ``TypeError``
    escapes, so the shipped empty-dict contract breaks wherever the mutation
    lands: m47 (L519), m56 (L523), m65 (L527), m71 (L529), m77 (L531), m86
    (L535).
    """
    nvml: FakePynvml = sys.modules["pynvml"]
    nvml.fault_everything()

    assert monitor._get_extended_metrics() == {}


@pytest.mark.parametrize(
    ("fault_call", "lost_key"),
    [
        pytest.param("nvmlDeviceGetClockInfo", KEY_MEM_CLOCK, id="L521"),
        pytest.param("nvmlDeviceGetMaxClockInfo", KEY_MEM_CLOCK_MAX, id="L525"),
        pytest.param("nvmlDeviceGetCurrPcieLinkGeneration", KEY_LINK_GEN, id="L528"),
        pytest.param("nvmlDeviceGetCurrPcieLinkWidth", KEY_LINK_WIDTH, id="L530"),
        pytest.param("nvmlDeviceGetEncoderUtilization", KEY_ENCODER, id="L540"),
        pytest.param("nvmlDeviceGetDecoderUtilization", KEY_DECODER, id="L543"),
        pytest.param("nvmlDeviceGetBAR1MemoryInfo", KEY_BAR1, id="L546"),
    ],
)
def test_each_medium_block_independently_suppresses_its_own_nvml_fault(
    monitor,
    fault_call: str,
    lost_key: str,
) -> None:
    """Control: one block faulting costs exactly ONE key - the rest still land.

    ``_get_extended_metrics`` has no all-or-nothing failure mode: a
    ``NVMLError`` from the named call is swallowed by that block's own
    ``with contextlib.suppress(...)`` and never reaches the other blocks, so the
    dict is the shipped nine keys minus the faulted one.  (The two throughput
    blocks are excluded: they share one function and are pinned by
    ``test_tx_and_rx_differ_only_by_the_nvml_constant`` instead.)
    """
    nvml: FakePynvml = sys.modules["pynvml"]
    nvml.returns[fault_call] = NVMLError(f"nvml fault at {fault_call}")

    metrics = monitor._get_extended_metrics()

    expected = dict(EXPECTED_MEDIUM_VALUE)
    del expected[lost_key]
    assert metrics == expected
    assert lost_key not in metrics


def test_tx_or_rx_constant_fault_drops_only_its_own_key(monitor) -> None:
    """Control: faulting ONE of the two throughput constants costs one key.

    ``nvmlDeviceGetPcieThroughput`` is one function called twice (L533 TX, L537
    RX); the shipped ``ByConstant``-shaped selection means a fault on the TX
    constant leaves RX intact and vice versa.  This is the isolation the TX/RX
    kill leg depends on, so it is pinned separately from the shared-function
    blocks above.
    """
    nvml: FakePynvml = sys.modules["pynvml"]
    nvml.returns["nvmlDeviceGetPcieThroughput"] = ByConstant(
        {NVML_PCIE_UTIL_RX_BYTES: RX_KB}, default=NVMLError("tx fault")
    )

    metrics = monitor._get_extended_metrics()

    assert KEY_TX not in metrics
    assert metrics[KEY_RX] == RX_KB
    assert metrics == {k: v for k, v in EXPECTED_MEDIUM_VALUE.items() if k != KEY_TX}


@pytest.mark.parametrize("flavor", ["nvml", "attribute"])
def test_bar1_block_suppresses_either_fault_flavor_without_a_bar1_key(monitor, flavor: str) -> None:
    """L545 suppresses BOTH ``NVMLError`` and ``AttributeError`` - no BAR1 key.

    Audit correction #5: an NVMLError-only injection is VACUOUS for m102/m104,
    so this file drives both shipped flavors of the L545 block.  ``nvml`` flavor:
    ``nvmlDeviceGetBAR1MemoryInfo`` raises ``NVMLError``.  ``attribute`` flavor:
    the returned object has no ``bar1Used``, so L547 raises ``AttributeError``.
    Shipped, either flavor is swallowed by the same ``with`` and the result is
    the 8-key dict with ``bar1_used`` ABSENT.

    Per-mutant kill map (each mutant either raises or lands ``bar1_used`` where
    shipped has none):
      * m101 ``suppress(None, AttributeError)`` - ``issubclass(..., None)``
        ``TypeError`` under BOTH flavors,
      * m102 ``suppress(pynvml.NVMLError, None)`` - ``TypeError`` under the
        ``attribute`` flavor (the nvml flavor is still swallowed),
      * m103 ``suppress(AttributeError)`` - the injected ``NVMLError`` escapes
        uncaught under the ``nvml`` flavor,
      * m104 ``suppress(pynvml.NVMLError, )`` - the trailing-comma single-arg
        form does not suppress ``AttributeError``, so it escapes under the
        ``attribute`` flavor.
    """
    nvml: FakePynvml = sys.modules["pynvml"]
    if flavor == "nvml":
        nvml.returns["nvmlDeviceGetBAR1MemoryInfo"] = NVMLError("bar1 unavailable")
    else:
        nvml.returns["nvmlDeviceGetBAR1MemoryInfo"] = Bar1InfoWithoutCounter()

    metrics = monitor._get_extended_metrics()

    assert KEY_BAR1 not in metrics
    assert metrics == {k: v for k, v in EXPECTED_MEDIUM_VALUE.items() if k != KEY_BAR1}
