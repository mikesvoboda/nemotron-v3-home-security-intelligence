"""S3 batch-28 lane gm14 - ``gpu_monitor`` group G18 kill battery (53 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json``
group 22 (``G18 _get_gpu_stats_from_ai_containers``), ``group_22.keys`` and
``survivors.json`` for the exact per-key diffs.  Every key below is KILLABLE and
is claimed by no other group (the function contributes 53 keys in total, all of
them here).

Key -> test map (all 53 keys of ``group_22.keys``)
===================================================
* ``__mutmut_4`` ``gpu_name = None`` (L796), ``_5``/``_6``/``_7`` the wrapXX /
  lower / upper variants of ``"NVIDIA GPU (via AI Containers)"``
  -> ``test_fallback_payload_without_a_device_keeps_the_generic_gpu_name`` (SOLE
     route: the device-less payload is the only input that reads the L796
     initializer, because a present ``device`` overwrites it at L812).
* ``__mutmut_13`` ``client.get(None)`` (L805)
  -> ``test_health_url_is_the_yolo26_url_plus_health`` (call-arg identity is the
     only observable - m13 still returns the same response double).
* ``__mutmut_18`` ``total_vram_used_mb = vram_mb`` (L810, RE-DISPOSED
  EQUIVALENT->KILLABLE per manifest audit #10)
  -> ``test_malformed_vram_payload_is_a_single_debug_and_never_a_warning``
     (manifest test_spec row (h): shipped ``0.0 += "3072"`` raises inside the
     INNER try and yields exactly ONE DEBUG record and no WARNING; the plain
     assignment succeeds, the DEBUG text changes and the gate re-raises into the
     OUTER except, producing a WARNING.  The kill is the log-stream divergence.)
* ``__mutmut_27`` ``logger.debug(None)`` (L819-822) - UNPARSEABLE by the splice
  harness (multi-line f-string call; see ``probe_g18_m27.py``)
  -> ``test_successful_query_logs_the_exact_vram_util_temp_power_debug`` (manual
     probe, same route).
* ``__mutmut_28`` ``vram_mb * 1024`` and ``__mutmut_29`` ``1124`` (L820)
  -> same test (exact DEBUG text) + the no-device gate legs.
* ``__mutmut_30`` ``logger.debug(None)`` (L824)
  -> ``test_query_failure_debug_carries_the_exception_text_and_returns_none``.
* ``__mutmut_33`` number ``0 -> 1`` - occurrence-twin key, 9 candidates in this
  function.  Every candidate is reddened (the harness requires ALL of them):
  occ0 L795 accumulator init and occ3 L831 gate -> the 0.5 MB gate test;
  occ1 L806 ``status_code == 210`` -> the 200-success tests;
  occ2 L820 ``/ 1124`` -> the exact-DEBUG test;
  occ4 L832 / occ6 L838 comment digits and occ5/occ7/occ8 L836/L839/L840
  else-branch ``0.0``/``0``/``0.0`` -> ``1.0``/``1``/``1.0`` -> the no-device
  "all fields default to zero" legs.
* ``__mutmut_61``/``_62`` ``"recorded_at"`` wrapXX/upper and ``__mutmut_63``
  ``datetime.now(None)`` (L841)
  -> ``test_success_payload_carries_the_shipped_key_set_and_tz_aware_timestamp``.
* ``__mutmut_64``..``__mutmut_101`` the ten extended-metric key strings of the
  return dict (L843-L863) x wrapXX/upper
  -> ``test_all_extended_metrics_are_absent_values_under_shipped_names``
  -> ``test_success_payload_carries_the_shipped_key_set_and_tz_aware_timestamp``.
* ``__mutmut_102`` ``logger.warning(None)`` (L867)
  -> ``test_client_construction_failure_warns_with_the_exception_text``.

Discipline
----------
* Only shipped behaviour is asserted; ``httpx.AsyncClient`` is the legitimate
  double for the EXTERNAL YOLO26v2 service and is patched with ``autospec=True``.
* Log assertions read the RAW ``record.msg`` inside a ``set_level`` + ``clear()``
  window filtered to this module's logger (batch27_01 pattern).
* No clock patching anywhere - ``datetime.now`` is never patched, so the
  ``now(UTC) -> now(None)`` leg is pinned structurally (``tzinfo is not None``).
* No import-time global spies; every double is installed per test.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.services.gpu_monitor as M

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L796: gpu_name = "NVIDIA GPU (via AI Containers)"
GENERIC_GPU_NAME = "NVIDIA GPU (via AI Containers)"

# L841-L863: the 23 keys of the shipped success return dict, in source order.
# (the six core keys are written in full by the other G18 legs; the sixteen
# extended ones are listed here because 40 of the 53 keys are their mutants.)
SHIPPED_KEYS = frozenset(
    {
        "gpu_name",  # L835
        "gpu_utilization",  # L836
        "memory_used",  # L837
        "memory_total",  # L838
        "temperature",  # L839
        "power_usage",  # L840
        "recorded_at",  # L841
        "fan_speed",  # L843
        "sm_clock",  # L844
        "memory_bandwidth_utilization",  # L845
        "pstate",  # L846
        "throttle_reasons",  # L848
        "power_limit",  # L849
        "sm_clock_max",  # L850
        "compute_processes_count",  # L851
        "pcie_replay_counter",  # L852
        "temp_slowdown_threshold",  # L853
        "memory_clock",  # L855
        "memory_clock_max",  # L856
        "pcie_link_gen",  # L857
        "pcie_link_width",  # L858
        "pcie_tx_throughput",  # L859
        "pcie_rx_throughput",  # L860
        "encoder_utilization",  # L861
        "decoder_utilization",  # L862
        "bar1_used",  # L863
    }
)

# L843-L863: every extended metric is an explicit None in this payload.
EXTENDED_KEYS = (
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
)

YOLO26_URL = "http://y26.test:8000"


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


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped f-string log call.

    Every shipped site in this group is an already-interpolated f-string, so
    ``args`` stays empty (a moved/dropped message argument lands IN ``msg``) and
    ``exc_info`` stays absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for an f-string: {r.args!r}"
    assert r.exc_info is None, f"exc_info present where shipped passes none: {r.exc_info!r}"


def only(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


# =============================================================================
# GPUMonitor + httpx.AsyncClient harness
#
# The ctor probes pynvml (ImportError forced) and shutil.which (None), so the
# monitor is a pure mock-mode object: this file drives _get_gpu_stats_from_ai_
# containers directly and never depends on GPU state.
# =============================================================================


@pytest.fixture
def monitor():
    """A GPUMonitor in mock mode: ``import pynvml`` fails, nvidia-smi is absent.

    ``sys.modules["pynvml"] = None`` is the interpreter's OWN ImportError trigger
    ("import of pynvml halted; None in sys.modules"), so the ctor's
    ``_initialize_nvml`` takes its shipped ImportError arm and
    ``_check_nvidia_smi`` its not-found arm - no GPU, no subprocess, no real clock.
    """
    with (
        patch.dict("sys.modules", {"pynvml": None}),
        patch("backend.services.gpu_monitor.shutil.which", return_value=None, autospec=True),
    ):
        yield M.GPUMonitor()


def response(status_code: int = 200, payload: dict | None = None) -> MagicMock:
    """A shipped-shaped httpx.Response double for the YOLO26 /health call."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


class ClientCtx:
    """``patch("httpx.AsyncClient", autospec=True)`` wired to a ``async with`` client.

    ``enter_error`` makes ``__aenter__`` raise (the client cannot even be built);
    ``get_error`` makes the awaited ``client.get(...)`` raise.  Both are the
    shipped function's own fault paths, not inventions.  ``responses`` is the
    per-call sequence of ``client.get`` returns (the shipped code issues exactly
    one GET, so a one-element list is the normal case).
    """

    def __init__(
        self,
        responses=None,
        *,
        enter_error: BaseException | None = None,
        get_error: BaseException | None = None,
    ):
        self._responses = responses
        self._enter_error = enter_error
        self._get_error = get_error
        self._patcher = None
        self.cls = None
        self.client = None

    def __enter__(self) -> ClientCtx:
        self._patcher = patch("httpx.AsyncClient", autospec=True)
        self.cls = self._patcher.start()
        client = AsyncMock()
        client.get = AsyncMock()
        if self._get_error is not None:
            client.get.side_effect = self._get_error
        elif self._responses is not None:
            client.get.side_effect = list(self._responses)
        if self._enter_error is not None:
            self.cls.return_value.__aenter__.side_effect = self._enter_error
        self.cls.return_value.__aenter__.return_value = client
        self.client = client
        return self

    def __exit__(self, *exc: object) -> bool:
        self._patcher.stop()
        return False

    @property
    def get_urls(self) -> list[object]:
        """Every URL the shipped code awaited ``client.get`` with, in order."""
        return [c.args[0] for c in self.client.get.await_args_list]


# =============================================================================
# L796 + L812: gpu_name (mutmut_4/5/6/7)
# =============================================================================


@pytest.mark.asyncio
async def test_fallback_payload_without_a_device_keeps_the_generic_gpu_name(monitor, caplog):
    """No ``device`` field -> the L796 initializer is what the payload carries.

    L796 ``gpu_name = "NVIDIA GPU (via AI Containers)"`` is only observable on
    this route: L811-L812 replaces it whenever the response carries a device.
    Kills ``__mutmut_4`` (=None), ``_5`` (wrapXX), ``_6`` (lower), ``_7`` (upper).
    """
    win(caplog)
    ctx = ClientCtx([response(200, {"vram_used_gb": 1.0})])
    with ctx:
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is not None
    assert stats["gpu_name"] == "NVIDIA GPU (via AI Containers)"
    # L812 leg (device present -> f"NVIDIA GPU ({device})"): the same guard that
    # protects the initializer above.
    ctx2 = ClientCtx([response(200, {"vram_used_gb": 1.0, "device": "RTX A5500"})])
    with ctx2:
        stats2 = await monitor._get_gpu_stats_from_ai_containers()
    assert stats2 is not None
    assert stats2["gpu_name"] == "NVIDIA GPU (RTX A5500)"
    # L820-L822 ran twice on this path.
    assert len(at(caplog, logging.DEBUG)) == 2


# =============================================================================
# L805: the health URL (mutmut_13)
# =============================================================================


@pytest.mark.asyncio
async def test_health_url_is_the_yolo26_url_plus_health(monitor, caplog):
    """L805 ``await client.get(f"{settings.yolo26_url}/health")``.

    Arg identity is the ONLY observable for ``client.get(None)`` - the response
    double answers either way - so the awaited URL is pinned exactly.
    """
    win(caplog)
    with patch(
        "backend.services.gpu_monitor.get_settings",
        return_value=MagicMock(yolo26_url=YOLO26_URL, gpu_http_timeout=2.5),
        autospec=True,
    ):
        ctx = ClientCtx([response(200, {"vram_used_gb": 1.0})])
        with ctx:
            stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is not None
    assert ctx.client.get.await_count == 1
    assert ctx.get_urls == ["http://y26.test:8000/health"]
    # L802 opens exactly one client for the single endpoint the shipped code probes.
    assert ctx.cls.call_count == 1


# =============================================================================
# L819-L822: the DEBUG stats line (mutmut_27 manual, _28, _29, _33-occ2)
# =============================================================================


@pytest.mark.asyncio
async def test_successful_query_logs_the_exact_vram_util_temp_power_debug(monitor, caplog):
    """L819-L822 f"YOLO26v2 GPU stats: {vram_mb / 1024:.2f} GB, util=..C, power..W".

    The full interpolated text pins the GB arithmetic: ``vram_mb * 1024`` renders
    "99614720.00 GB" and ``/ 1124`` renders "94.91 GB", so both L820 mutants die
    on the exact string.  ``logger.debug(None)`` (manual mutant_27) dies HERE too:
    with the message gone the only surviving records are the ctor's own, so the
    window holds no DEBUG at all.
    """
    win(caplog)
    payload = {
        "vram_used_gb": 95.0,
        "device": "RTX A5500",
        "gpu_utilization": 37.5,
        "temperature": 61,
        "power_watts": 120.5,
    }
    with ClientCtx([response(200, payload)]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is not None
    only(caplog, logging.DEBUG, "YOLO26v2 GPU stats: 95.00 GB, util=37.5%, temp=61C, power=120.5W")


# =============================================================================
# L810 vs L820 vs L831: the augassign key (mutmut_18)
# =============================================================================


@pytest.mark.asyncio
async def test_malformed_vram_payload_is_a_single_debug_and_never_a_warning(monitor, caplog):
    """L810 ``total_vram_used_mb += vram_mb`` (manifest row (h), audit #10).

    A misbehaving remote answers 200 with a JSON *string* for ``vram_used_gb``.
    ``_parse_yolo26_response`` computes ``vram_mb = data["vram_used_gb"] * 1024``,
    and ``str * 1024`` is a legal str, so the shipped accumulator statement
    ``0.0 += "3072"`` raises TypeError inside the INNER try: exactly ONE DEBUG
    record and NO warning, gate False, return None.

    The ``= vram_mb`` twin succeeds, so the TypeError moves to the L820 DEBUG
    line (different text) and then to the L831 gate (``"3072" > 0``), which the
    INNER handler does not cover - it escapes to the OUTER except and emits a
    WARNING.  Both return None; the LOG STREAM is the observable.
    """
    win(caplog)
    with ClientCtx([response(200, {"vram_used_gb": "3", "device": "D"})]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is None
    recs = mine(caplog)
    assert len(recs) == 1, (
        f"shipped emits exactly one DEBUG record, got {[(r.levelno, r.msg) for r in recs]}"
    )
    assert recs[0].levelno == logging.DEBUG
    assert recs[0].msg == (
        "Failed to query YOLO26v2 health: unsupported operand type(s) for +=: 'float' and 'str'"
    )
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.ERROR) == []


@pytest.mark.asyncio
async def test_list_valued_vram_payload_diverges_the_same_way(monitor, caplog):
    """Same L810 leg with a JSON *list* (``[1, 2] * 1024`` is also a legal str/list)."""
    win(caplog)
    with ClientCtx([response(200, {"vram_used_gb": [1, 2], "device": "D"})]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is None
    recs = mine(caplog)
    assert len(recs) == 1
    assert recs[0].levelno == logging.DEBUG
    assert recs[0].msg == (
        "Failed to query YOLO26v2 health: unsupported operand type(s) for +=: 'float' and 'list'"
    )
    assert at(caplog, logging.WARNING) == []


# =============================================================================
# L824: the inner failure DEBUG (mutmut_30)
# =============================================================================


@pytest.mark.asyncio
async def test_query_failure_debug_carries_the_exception_text_and_returns_none(monitor, caplog):
    """L823-L824 ``except Exception as e: logger.debug(f"Failed to query YOLO26v2 health: {e}")``.

    ``logger.debug(None)`` leaves this window empty (the ctor's records are
    outside it), so the DEBUG count + text is the kill.
    """
    win(caplog)
    with ClientCtx(get_error=RuntimeError("boom")):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is None
    only(caplog, logging.DEBUG, "Failed to query YOLO26v2 health: boom")
    assert at(caplog, logging.WARNING) == []


# =============================================================================
# L831 gate family (mutmut_33 occ0/occ3) + zero-default legs (occ4..occ8)
# =============================================================================


@pytest.mark.asyncio
async def test_half_megabyte_vram_still_returns_a_dict(monitor, caplog):
    """L831 ``if total_vram_used_mb > 0 or gpu_utilization is not None:``.

    0.000488 GB = 0.5 MB -> shipped gate True and a dict; the ``> 1`` twin (and
    the L795 ``total_vram_used_mb = 1.0`` init twin, whose 1.0 also fails the
    shipped 0.5-vs-threshold comparison path) return None here.
    """
    win(caplog)
    with ClientCtx([response(200, {"vram_used_gb": 0.000488})]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert isinstance(stats, dict)
    assert stats["memory_used"] == 0
    assert stats["gpu_utilization"] == 0.0
    assert stats["memory_total"] == 24576
    assert stats["temperature"] == 0
    assert stats["power_usage"] == 0.0
    assert len(at(caplog, logging.DEBUG)) == 1


@pytest.mark.asyncio
async def test_zero_vram_with_utilization_returns_the_zero_default_dict(monitor, caplog):
    """Gate passes on the util half alone; every field defaults to the shipped zero.

    Pins L836/L839/L840 else-branches (``0.0``/``0``/``0.0``) against the
    ``number:0->1`` twins and the L831 ``> 1`` twin.
    """
    win(caplog)
    with ClientCtx([response(200, {"gpu_utilization": 12.5})]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is not None
    assert stats["gpu_name"] == "NVIDIA GPU (via AI Containers)"
    assert stats["gpu_utilization"] == 12.5
    assert stats["memory_used"] == 0
    assert stats["memory_total"] == 24576
    assert stats["temperature"] == 0
    assert stats["power_usage"] == 0.0
    assert len(at(caplog, logging.DEBUG)) == 1


@pytest.mark.asyncio
async def test_device_only_payload_without_vram_returns_none(monitor, caplog):
    """Gate False on BOTH halves: a device alone never trips L831.

    Shipped: the accumulator stays 0.0 and utilisation stays None, so no dict is
    returned even though the inner parse succeeded and the DEBUG fired.  The L795
    ``total_vram_used_mb = 1.0`` init twin starts above the gate and returns a
    dict here - that inversion is the kill for that occurrence.
    """
    win(caplog)
    with ClientCtx([response(200, {"device": "cuda:0"})]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is None
    only(caplog, logging.DEBUG, "YOLO26v2 GPU stats: 0.00 GB, util=None%, temp=NoneC, power=NoneW")
    assert at(caplog, logging.WARNING) == []


# =============================================================================
# L841-L863: return-dict key identity + tz (mutmut_61.._101)
# =============================================================================


@pytest.mark.asyncio
async def test_success_payload_carries_the_shipped_key_set_and_tz_aware_timestamp(monitor, caplog):
    """L841 ``"recorded_at": datetime.now(UTC)`` + every dict key name.

    A renamed key drops the shipped name -> ``set()`` inequality; ``now(None)``
    yields a naive timestamp -> ``tzinfo is None``.
    """
    win(caplog)
    payload = {
        "vram_used_gb": 95.0,
        "device": "RTX A5500",
        "gpu_utilization": 37.5,
        "temperature": 61,
        "power_watts": 120.5,
    }
    with ClientCtx([response(200, payload)]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is not None
    assert set(stats) == SHIPPED_KEYS
    assert stats["gpu_name"] == "NVIDIA GPU (RTX A5500)"
    assert stats["gpu_utilization"] == 37.5
    assert stats["memory_used"] == 97280
    assert stats["memory_total"] == 24576
    assert stats["temperature"] == 61
    assert stats["power_usage"] == 120.5
    assert stats["recorded_at"].tzinfo is not None
    assert len(at(caplog, logging.DEBUG)) == 1


@pytest.mark.asyncio
async def test_all_extended_metrics_are_absent_values_under_shipped_names(monitor, caplog):
    """L843-L863: the nineteen extended metrics are explicit ``None`` under the
    shipped names.  Reading them BY NAME is the kill for the 36 wrapXX/upper key
    mutants here (a renamed entry leaves the shipped name missing)."""
    win(caplog)
    with ClientCtx([response(200, {"vram_used_gb": 1.0})]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is not None
    for name in EXTENDED_KEYS:
        assert name in stats, f"shipped extended key missing from the payload: {name}"
        assert stats[name] is None, f"{name} is not the shipped None: {stats[name]!r}"
    assert set(stats) == SHIPPED_KEYS
    assert len(at(caplog, logging.DEBUG)) == 1


# =============================================================================
# L806 gate (mutmut_33 occ1) + L867 outer warning (mutmut_102)
# =============================================================================


@pytest.mark.asyncio
async def test_non_200_status_yields_no_dict_and_no_log(monitor, caplog):
    """L806 ``if resp.status_code == 200:`` - the ``== 210`` twin parses nothing.

    A 500 answer leaves the accumulator at 0.0 with no utilisation, so the gate
    fails and the shipped code returns None without logging anything.
    """
    win(caplog)
    with ClientCtx([response(500, None)]):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is None
    assert mine(caplog) == []


@pytest.mark.asyncio
async def test_client_construction_failure_warns_with_the_exception_text(monitor, caplog):
    """L866-L867 ``except Exception as e: logger.warning(f"Failed to query AI containers for GPU stats: {e}")``.

    The fault is raised by ``__aenter__``, i.e. OUTSIDE the inner handler, so it
    reaches the OUTER except.  ``logger.warning(None)`` loses the text.
    """
    win(caplog)
    with ClientCtx(enter_error=OSError("no client")):
        stats = await monitor._get_gpu_stats_from_ai_containers()

    assert stats is None
    only(
        caplog,
        logging.WARNING,
        "Failed to query AI containers for GPU stats: no client",
    )
    assert at(caplog, logging.DEBUG) == []
    assert at(caplog, logging.ERROR) == []


@pytest.mark.asyncio
async def test_payload_parser_is_not_part_of_this_group(monitor, caplog):
    """Control leg (kills nothing of its own): the shipped ``_parse_yolo26_response``
    contract that every payload leg above rides.  Pins the GB->MB conversion and
    the pass-through of device/util/temp/power so a payload assertion above can
    never be satisfied by a parser accident."""
    win(caplog)
    vram, device, util, temp, power = monitor._parse_yolo26_response(
        {
            "vram_used_gb": 2.0,
            "device": "cuda:0",
            "gpu_utilization": 5.0,
            "temperature": 40,
            "power_watts": 10.0,
        }
    )
    assert (vram, device, util, temp, power) == (2048.0, "cuda:0", 5.0, 40, 10.0)
    assert mine(caplog) == []
    empty = monitor._parse_yolo26_response({})
    assert empty == (0.0, None, None, None, None)
    assert mine(caplog) == []
