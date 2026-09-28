"""S3 batch-28 lane gm17 - ``gpu_monitor`` groups g25 + g26 kill battery (49 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 ``2f122c85a072b7bd00c2e4b36cdc1cda``
- byte-identical to the manifest-proven source). Admitted manifest:
``/tmp/wp-pw/gpu_monitor/manifest.json`` group 25 (G24 ``_broadcast_stats``,
33 keys) and group 26 (G13 ``start()``, 16 keys) - both KILLABLE, 0 EQUIVALENT -
plus ``group_25.keys`` / ``group_26.keys`` and ``survivors.json`` for the exact diffs.

Test -> mutant-key map
======================
Every key below is in ``group_25.keys`` or ``group_26.keys``. Splice report
``splice-group_25.json`` flags ``_broadcast_stats__mutmut_2`` and
``splice-group_26.json`` flags ``start__mutmut_15`` as **unparseable** (mutmut
reprints the multi-line statement so the harness splice does not compile); both
were built and killed MANUALLY - probe script
``/tmp/wp-pw/gm/manual/manual_prove.py`` run as ``manual_prove.py bc25_m2`` /
``manual_prove.py start26_m15`` against THIS file (built mutants
``mut_bc25_m2.py`` / ``mut_start26_m15.py``, verdicts
``result_bc25_m2.json`` / ``result_start26_m15.json``). Every other key of both groups
carries exactly ONE splice candidate (measured with ``replay_lib.candidates`` over
all 49 diffs), so no occurrence-twin proof is owed for any key claimed here.

g25 - ``GPUMonitor._broadcast_stats`` (``gpu_monitor.py:1062-1094``)
  * ``_broadcast_stats__mutmut_2``  L1073 ``broadcast_stats = {...}`` -> ``None``
    (UNPARSEABLE -> ``manual_prove.py bc25_m2``)
    -> ``test_success_frame_is_the_shipped_seven_key_projection`` (SOLE route: the
       mutant still awaits, so the frame VALUE is the only observable)
  * ``_3``/``_4`` L1074 ``"gpu_name"`` -> ``XXgpu_nameXX`` / ``GPU_NAME``;
    ``_7``/``_8`` L1075 ``gpu_utilization``; ``_11``/``_12`` L1076 ``memory_used``;
    ``_15``/``_16`` L1077 ``memory_total``; ``_19``/``_20`` L1078 ``temperature``;
    ``_23``/``_24`` L1079 ``power_usage``; ``_27``/``_28`` L1080 ``recorded_at``
    (14 key-name wrapXX/upper mutants)
    -> all fourteen: ``test_success_frame_is_the_shipped_seven_key_projection``
       (the frame is projected out of the ``stats`` INPUT dict, so a mutated
       OUTPUT key name is visible only in the frame's key set)
  * ``_31`` L1083 ``broadcast_gpu_stats(broadcast_stats)`` -> ``(None)``
    -> ``test_success_frame_is_the_shipped_seven_key_projection``,
       ``test_the_frame_is_forwarded_verbatim_and_awaited_exactly_once``
       (the projection legs alone cannot see the ARGUMENT)
  * ``_32`` L1084 ``logger.debug(None)``, ``_33`` wrapXX, ``_34`` lower, ``_35`` upper
    -> ``test_success_debug_line_is_the_shipped_static_text`` (SOLE route: the
       success arm logs nothing else, so the window holds exactly this record)
  * ``_37`` L1087 ``extra=None``, ``_39`` L1087 ``extra`` dropped
    -> ``test_broadcast_failure_is_swallowed_into_the_context_rich_error``
       (SOLE route: the shipped ``extra`` keys are the only surface)
  * ``_40`` L1088 ``"Failed to broadcast GPU stats"`` -> wrapXX
    -> ``test_failure_message_is_the_shipped_text_without_interpolation``
       (the shipped text carries NO placeholder, so a wrapper sits in ``msg``)
  * ``_43``/``_44`` L1090 ``"operation"``, ``_47``/``_48`` L1091 ``"error"``,
    ``_50``/``_51`` L1092 ``"error_type"``
    -> ``test_failure_context_keys_are_the_shipped_names_verbatim`` (+ value legs)
  * ``_45``/``_46`` L1090 ``"broadcast_stats"``, ``_49`` L1091 ``str(e)`` ->
    ``str(None)``, ``_52`` L1092 ``type(e)`` -> ``type(None)``
    -> ``test_failure_context_carries_the_stimulus_error_and_its_type``
       (m49 -> ``error == "None"``; m52 -> ``error_type == "NoneType"``)

g13 - ``GPUMonitor.start`` (``gpu_monitor.py:1139-1155``)
  * ``start__mutmut_1`` L1145 ``logger.warning(None)``, ``_2`` wrapXX, ``_3``
    lower, ``_4`` upper
    -> ``test_already_running_short_circuits_with_the_shipped_warning`` (SOLE route)
  * ``start__mutmut_5`` L1148 ``logger.info(None)``, ``_6`` wrapXX, ``_7`` lower,
    ``_8`` upper; ``_18`` L1155 ``logger.info(None)``, ``_19`` wrapXX, ``_20``
    lower, ``_21`` upper
    -> ``test_cold_start_logs_the_shipped_pair_in_order`` (SOLE route: the shipped
       cold start logs exactly two INFO lines, in order, and nothing else)
  * ``start__mutmut_13`` L1153 ``create_task(..., name=None)``, ``_15`` ``name=``
    dropped (**UNPARSEABLE** -> ``manual_prove.py start26_m15``), ``_16``
    ``"XXgpu-monitorXX"``, ``_17`` ``"GPU-MONITOR"``
    -> ``test_the_poll_task_carries_the_shipped_debug_name`` (SOLE route: the task
       NAME is the only observable - every variant returns a live task)

Every leg above is MEASURED: each key was replayed against this battery in a
symlink shadow of this tree (``/tmp/wp-b28/replay_lib.py prove``), reddening with
a NAMED failed test, and this file is green on pristine source.

Control legs that kill nothing of their own
(``test_none_guard_short_circuits_before_the_stats_lookup``,
``test_the_frame_is_forwarded_verbatim_and_awaited_exactly_once``,
``test_the_context_manager_still_swallows_a_none_broadcaster``,
``test_start_creates_a_live_task_and_flips_running``,
``test_start_is_idempotent_and_hands_back_the_same_task``) state the rest of the
shipped contract - the ``broadcaster is None`` short-circuit, the single await of
the forwarded object, and the idempotency clause documented at L1142 - so a
killing leg can never be satisfied by an accidental fall-through.

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it,
and every value an assertion depends on is injected by this file (a crafted
21-key ``GPUStatsDict``-shaped input with a fixed tz-aware ``recorded_at``, an
AsyncMock broadcaster, a coroutine swap-in for the poll loop).

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  plus ``record.args`` / ``record.exc_info`` / ``record.levelno`` (the
  ``test_pipeline_workers_batch28_17.py`` pattern).  ``record.message`` is never
  used: it interpolates, so a wrapper inside the raw text could hide.
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted - g25/g26 contain no timing site.  Every asserted value (the datetime,
  the metrics, the exception text) is fixture-injected, so the wall clock plays no
  part in any assertion.  The construction seam is the shipped
  ``get_settings``/``shutil.which``/``import pynvml`` reads, neutralised per
  window so a forgotten poll-loop swap would hit the shipped 5s pytest timeout
  loudly instead of polling forever.
* Mocks of real attributes are autospec'd or ``new=``'d (WP4.2 fast path):
  ``backend.services.gpu_monitor.get_settings`` and ``shutil.which`` are
  autospec'd; the poll loop is replaced through the INSTANCE attribute (an
  instance attribute is not a patch site - it is the shipped seam itself, which
  L1153 reaches as ``self._poll_loop()``).  The broadcaster is a bare
  ``AsyncMock`` injected through the shipped ``broadcaster=`` parameter.
* No import-time global spy: every double is window-scoped, and the
  ``sys.modules["pynvml"]`` entry that ``_initialize_nvml`` resolves (L210) is
  installed and restored inside ``init_seam`` - a per-window stand-in with a
  raising ``nvmlInit``, so construction never touches a real NVML library and
  ``_nvml_initialized`` is False on every host (the entry the test *started*
  with is put back on exit).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from backend.services import gpu_monitor as M
from backend.services.gpu_monitor import GPUMonitor

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__), L48)

pytestmark = [
    pytest.mark.unit,
]

# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L1073-L1081: the broadcast frame is EXACTLY this 7-key projection of the
# ``stats`` argument. The shipped ``GPUStatsDict`` (L51-L100) carries 28 keys, so
# "exactly these seven" is a real assertion rather than a restatement.
#   L1074 "gpu_name":         stats["gpu_name"]
#   L1075 "gpu_utilization":  stats["gpu_utilization"]
#   L1076 "memory_used":      stats["memory_used"]
#   L1077 "memory_total":     stats["memory_total"]
#   L1078 "temperature":      stats["temperature"]
#   L1079 "power_usage":      stats["power_usage"]
#   L1080 "recorded_at":      stats["recorded_at"].isoformat()
BROADCAST_KEYS = (
    "gpu_name",
    "gpu_utilization",
    "memory_used",
    "memory_total",
    "temperature",
    "power_usage",
    "recorded_at",
)

# L1084: logger.debug("Broadcasted GPU stats via WebSocket") - a STATIC string with
# no interpolation. (Audit correction #7: "GPU stats broadcast: <gpu_name>" is NOT
# shipped text.)
BC_OK_DEBUG = "Broadcasted GPU stats via WebSocket"

# L1088: logger.error("Failed to broadcast GPU stats", extra={...}) - the shipped
# message text carries no placeholder.
BC_FAIL_MSG = "Failed to broadcast GPU stats"

# L1090-L1092: the shipped extra= dict - key names, and the one static value.
BC_FAIL_CONTEXT = ("operation", "error", "error_type")
BC_FAIL_OPERATION = "broadcast_stats"  # L1090 value

# L1145: logger.warning("GPUMonitor already running")
ALREADY_WARN = "GPUMonitor already running"
# L1148: logger.info("Starting GPU monitoring")
STARTING_INFO = "Starting GPU monitoring"
# L1153: asyncio.create_task(self._poll_loop(), name="gpu-monitor")   (NEM-5057)
TASK_NAME = "gpu-monitor"
# L1155: logger.info("GPU monitoring started successfully")
STARTED_INFO = "GPU monitoring started successfully"

# The ``recorded_at`` of the crafted input stats - fixed and tz-aware, so the
# asserted ISO text is fixture-derived and never clock-dependent (L1080).
RECORDED_AT = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)

# The stimulus raised out of the broadcaster in the failure legs. Shipped L1091
# is ``str(e)`` and L1092 is ``type(e).__name__``, so both context values are
# derived from this one injected exception.
STIMULUS = RuntimeError("ws")


# =============================================================================
# Construction seam
# =============================================================================

# L159-L163 read three settings; poll_interval is deliberately absurd so that any
# leg which forgot to bound its poll loop blocks on a real sleep and dies to the
# shipped 5s pytest timeout instead of silently spinning.
_SETTINGS = {
    "gpu_poll_interval_seconds": 9999.0,
    "gpu_stats_history_minutes": 60,
    "gpu_http_timeout": 10.0,
}


def no_nvidia_lib() -> None:
    """Stand-in for ``pynvml.nvmlInit`` on a host with no NVML.

    ``_initialize_nvml`` calls it at L212, inside the OUTER ``try`` whose arms are
    ``except ImportError`` (L225) and ``except Exception`` (L229). A generic raise
    here therefore lands on L229 and leaves ``_nvml_initialized`` / ``_gpu_available``
    False - the shipped no-GPU state - WITHOUT probing a real NVML library. That
    matters for portability: the real ``pynvml`` IS importable in this interpreter
    (and on a GPU host ``nvmlInit`` would SUCCEED, setting ``_nvml_initialized`` True
    so ``stop()`` reached the shipped L1175-L1182 NVML arm), so the shipped
    construction path has to be pinned to one arm rather than left to the host.
    """
    raise RuntimeError("NVML is not reachable from the test seam")


@contextlib.contextmanager
def init_seam() -> Iterator[Any]:
    """Neutralise the three environment reads ``GPUMonitor.__init__`` performs.

    * ``get_settings`` (L159) - autospec'd, so the shipped signature is enforced.
    * ``shutil.which`` - L240 ``shutil.which("nvidia-smi")`` would otherwise hit
      the real PATH and, when it finds a binary, run a real ``subprocess.run``.
    * ``pynvml`` (L210 ``import pynvml``) - resolved through ``sys.modules``, so a
      per-window stand-in whose ``nvmlInit`` raises is the seam that reaches it (see
      ``no_nvidia_lib``). The prior entry - or its absence - is restored on exit, so
      nothing is left mutated. This is a per-window install, NOT an import-time spy.

    ``_initialize_nvml``'s no-GPU outcome makes L194 call ``_check_nvidia_smi``, which
    the ``which`` patch routes to the shipped L263-L264 "not found in PATH" DEBUG;
    ``win()`` clears that construction record before any assertion window opens.
    """
    saved = sys.modules.pop("pynvml", None)
    sys.modules["pynvml"] = SimpleNamespace(
        nvmlInit=no_nvidia_lib,
        NVMLError=Exception,
        __name__="pynvml",
    )
    try:
        with (
            patch.object(M, "get_settings", autospec=True) as settings,
            patch.object(M.shutil, "which", autospec=True, return_value=None),
        ):
            settings.side_effect = _settings_value
            yield settings
    finally:
        sys.modules.pop("pynvml", None)
        if saved is not None:
            sys.modules["pynvml"] = saved


def _settings_value() -> Any:
    s: dict[str, Any] = dict(_SETTINGS)
    mock = type("Settings", (), {})()
    for k, v in s.items():
        setattr(mock, k, v)
    return mock


def build_monitor(**kwargs: Any) -> GPUMonitor:
    """A real ``GPUMonitor`` built with no GPU, no subprocess and no real settings."""
    with init_seam():
        return GPUMonitor(**kwargs)


@pytest.fixture
def broadcaster() -> AsyncMock:
    """Injected WebSocket collaborator (shipped attribute set at L162)."""
    mock = AsyncMock(name="broadcaster")
    mock.broadcast_gpu_stats = AsyncMock(name="broadcast_gpu_stats")
    return mock


@pytest.fixture
def stats_in() -> dict[str, Any]:
    """A crafted 21-key ``GPUStatsDict``-shaped input for ``_broadcast_stats``.

    Every metric value is distinct, so a cross-wired projection (``memory_used``
    under ``memory_total``) cannot pass; the extra keys are present precisely
    because the shipped frame DROPS them (L1073-L1081 carries seven).
    """
    return {
        # --- the seven the shipped frame carries -----------------------------
        "gpu_name": "NVIDIA RTX A5500",
        "gpu_utilization": 42.5,
        "memory_used": 8192,
        "memory_total": 24576,
        "temperature": 65.0,
        "power_usage": 150.0,
        "recorded_at": RECORDED_AT,
        # --- the rest of the shipped TypedDict, NOT broadcast ----------------
        "fan_speed": 33,
        "sm_clock": 1410,
        "memory_bandwidth_utilization": 12.5,
        "pstate": 2,
        "throttle_reasons": 0,
        "power_limit": 230.0,
        "sm_clock_max": 1700,
        "compute_processes_count": 3,
        "pcie_replay_counter": 7,
        "temp_slowdown_threshold": 89.0,
        "memory_clock": 9501,
        "memory_clock_max": 9501,
        "pcie_link_gen": 4,
        "pcie_link_width": 16,
    }


def expected_frame(stats: dict[str, Any]) -> dict[str, Any]:
    """The shipped L1073-L1081 projection, re-derived from the SAME input dict."""
    return {
        "gpu_name": stats["gpu_name"],
        "gpu_utilization": stats["gpu_utilization"],
        "memory_used": stats["memory_used"],
        "memory_total": stats["memory_total"],
        "temperature": stats["temperature"],
        "power_usage": stats["power_usage"],
        "recorded_at": stats["recorded_at"].isoformat(),
    }


# =============================================================================
# Observation helpers (batch27_01 / pipeline_workers batch28_17 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load-bearing -
    it is also what drops the two INFO/WARNING records the shipped ``__init__``
    emits at L197 / L226 while ``build_monitor`` runs.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped log call.

    Every g25/g26 site passes a single positional message and no lazy args, so
    ``args`` must stay empty (a moved or dropped message argument lands IN ``msg``)
    and ``exc_info`` must be absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args: {r.args!r}"
    assert r.exc_info is None, (
        f"exc_info present where the shipped call passes none: {r.exc_info!r}"
    )


def only(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


def idle_loop() -> AsyncMock:
    """A coroutine double that returns immediately, so ``start()`` cannot spin.

    L1153 reaches the loop through the INSTANCE attribute ``self._poll_loop()``, so
    an instance attribute IS the shipped seam (and ``monkeypatch`` restores it).
    """

    async def idle() -> None:
        return None

    return AsyncMock(name="idle-poll-loop", side_effect=idle)


def bound_monitor(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> GPUMonitor:
    """``build_monitor`` plus a bounded poll loop installed on the instance."""
    monitor = build_monitor(**kwargs)
    monkeypatch.setattr(monitor, "_poll_loop", idle_loop(), raising=True)
    return monitor


# =============================================================================
# g25 - GPUMonitor._broadcast_stats (gpu_monitor.py:1062-1094)
# =============================================================================


@pytest.mark.asyncio
async def test_none_guard_short_circuits_before_the_stats_lookup(
    stats_in: dict[str, Any],
) -> None:
    """Control: L1068-L1069 - a None broadcaster means no frame, no lookup, no log.

    ``stats_in`` arrives MISSING ``gpu_name`` here: the shipped frame is built
    before the broadcast await, so under a None broadcaster the function never
    touches ``stats`` at all. A mutant that moved the guard below the frame build
    would raise ``KeyError`` at this await.
    """
    stats_in.pop("gpu_name")
    monitor = build_monitor(broadcaster=None)
    assert monitor.broadcaster is None, "L162 stores the injected broadcaster"

    await monitor._broadcast_stats(stats_in)  # must return None without touching stats

    assert monitor.broadcaster is None, "_broadcast_stats must not adopt a broadcaster"


@pytest.mark.asyncio
async def test_success_frame_is_the_shipped_seven_key_projection(
    broadcaster: AsyncMock,
    stats_in: dict[str, Any],
) -> None:
    """Kills g25 ``_2`` (whole frame -> None, UNPARSEABLE/manual) and the 14
    key-name wrapXX/upper variants of L1074-L1080.

    The frame is projected out of the ``stats`` INPUT dict, so a mutated OUTPUT key
    name is observable only in the frame: the mutant hands over a frame whose keys
    are no longer the seven shipped names. ``recorded_at`` must be the ISO text
    (L1080), never the datetime object. ``_2`` hands over ``None``, which fails the
    ``isinstance`` leg - the await still happens in that mutant, so the argument
    VALUE is the only observable.
    """
    monitor = build_monitor(broadcaster=broadcaster)
    frame = expected_frame(stats_in)

    await monitor._broadcast_stats(stats_in)

    sent = broadcaster.broadcast_gpu_stats.await_args[0][0]
    assert isinstance(sent, dict), f"the broadcast frame stopped being a dict: {sent!r}"
    assert set(sent) == set(BROADCAST_KEYS), (
        f"frame key set mutated: {sorted(sent)} != {sorted(BROADCAST_KEYS)}"
    )
    assert len(sent) == 7, f"frame carries {len(sent)} keys, shipped carries 7"
    # per-key identity, spelled out so each mutated shipped name has its own leg
    assert sent["gpu_name"] == stats_in["gpu_name"]
    assert sent["gpu_utilization"] == stats_in["gpu_utilization"]
    assert sent["memory_used"] == stats_in["memory_used"]
    assert sent["memory_total"] == stats_in["memory_total"]
    assert sent["temperature"] == stats_in["temperature"]
    assert sent["power_usage"] == stats_in["power_usage"]
    assert sent["recorded_at"] == RECORDED_AT.isoformat(), "L1080 serialises via isoformat()"
    assert sent == frame, "frame drifted from the shipped L1073-L1081 projection"


@pytest.mark.asyncio
async def test_the_frame_is_forwarded_verbatim_and_awaited_exactly_once(
    broadcaster: AsyncMock,
    stats_in: dict[str, Any],
) -> None:
    """Control + kills ``_31`` - L1083 argument -> ``None``.

    The shipped call is ``await self.broadcaster.broadcast_gpu_stats(broadcast_stats)``
    - exactly one positional argument, no kwargs, awaited exactly once. m31 hands
    over the literal ``None``; the projection leg above sees it too, but the
    call-shape legs here are what pin "the object built at L1073 is the object
    forwarded at L1083".
    """
    monitor = build_monitor(broadcaster=broadcaster)

    await monitor._broadcast_stats(stats_in)

    assert broadcaster.broadcast_gpu_stats.await_count == 1, "shipped code awaits the frame once"
    call = broadcaster.broadcast_gpu_stats.await_args
    assert len(call[0]) == 1, f"shipped call is single-positional, got {call.args!r}"
    assert call[1] == {}, f"shipped call passes no kwargs, got {call.kwargs!r}"
    sent = call[0][0]
    assert sent is not None, "L1083 forwards the built frame, never None"
    assert sent["gpu_name"] == stats_in["gpu_name"], "the forwarded object IS the shipped frame"
    assert sent["recorded_at"] == RECORDED_AT.isoformat()


@pytest.mark.asyncio
async def test_success_debug_line_is_the_shipped_static_text(
    broadcaster: AsyncMock,
    stats_in: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_32``/``_33``/``_34``/``_35`` - the L1084 ``logger.debug`` message.

    The success arm logs nothing else, so the window holds EXACTLY this DEBUG and
    no record at any other level.
    """
    monitor = build_monitor(broadcaster=broadcaster)

    win(caplog)
    await monitor._broadcast_stats(stats_in)

    only(caplog, logging.DEBUG, BC_OK_DEBUG)
    assert at(caplog, logging.INFO) == [], "the shipped success arm logs no INFO"
    assert at(caplog, logging.WARNING) == [], "a successful broadcast logs no warning"
    assert at(caplog, logging.ERROR) == [], "a successful broadcast logs no error"


@pytest.mark.asyncio
async def test_broadcast_failure_is_swallowed_into_the_context_rich_error(
    broadcaster: AsyncMock,
    stats_in: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_37`` (``extra=None``) and ``_39`` (``extra`` dropped) - L1087.

    The shipped ``except Exception`` (L1085) SWALLOWS the broadcaster failure - a
    re-raise escapes the await below and reddens - and replaces it with ONE ERROR
    carrying the shipped ``extra`` context, which is the only surface those two
    mutants touch (with ``extra`` gone, ``record.operation`` stops existing).
    """
    monitor = build_monitor(broadcaster=broadcaster)
    broadcaster.broadcast_gpu_stats.side_effect = RuntimeError(*STIMULUS.args)

    win(caplog)
    await monitor._broadcast_stats(stats_in)  # must NOT raise

    err = only(caplog, logging.ERROR, BC_FAIL_MSG)
    assert err.operation == BC_FAIL_OPERATION, "L1090 context lost: record.operation"
    assert err.error == "ws", "L1091 context lost: record.error"
    assert err.error_type == "RuntimeError", "L1092 context lost: record.error_type"
    assert at(caplog, logging.DEBUG) == [], "a failed broadcast logs no success DEBUG"


@pytest.mark.asyncio
async def test_failure_message_is_the_shipped_text_without_interpolation(
    broadcaster: AsyncMock,
    stats_in: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_40`` - the L1088 message wrapXX variant.

    The shipped message has no placeholder and no ``%``-args, so ``record.msg`` is
    the literal text and ``record.args`` stays empty - which is also what stops a
    wrapper (``"XX...XX"``) from hiding behind interpolation. A second stimulus
    class is used here so no assertion can be satisfied by the other leg's type.
    """
    monitor = build_monitor(broadcaster=broadcaster)
    broadcaster.broadcast_gpu_stats.side_effect = ValueError("bad frame")

    win(caplog)
    await monitor._broadcast_stats(stats_in)

    err = only(caplog, logging.ERROR, BC_FAIL_MSG)
    assert "%s" not in err.msg, "the shipped failure text is not a format template"
    assert tuple(err.args or ()) == (), "no lazy args on the shipped failure call"
    assert err.levelno == logging.ERROR
    assert err.error == "bad frame"
    assert err.error_type == "ValueError"


@pytest.mark.asyncio
async def test_failure_context_keys_are_the_shipped_names_verbatim(
    broadcaster: AsyncMock,
    stats_in: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_43``/``_44`` (``"operation"``), ``_47``/``_48`` (``"error"``) and
    ``_50``/``_51`` (``"error_type"``) - the L1090-L1092 context KEY names.

    Each shipped context key is read off the record BY NAME, and each is also
    pinned to its value, so an ambient ``log_context`` value can never stand in for
    a renamed ``extra`` key.
    """
    monitor = build_monitor(broadcaster=broadcaster)
    broadcaster.broadcast_gpu_stats.side_effect = RuntimeError(*STIMULUS.args)

    win(caplog)
    await monitor._broadcast_stats(stats_in)

    err = only(caplog, logging.ERROR, BC_FAIL_MSG)
    for key in BC_FAIL_CONTEXT:
        assert hasattr(err, key), f"shipped extra= key {key!r} is absent from the record"
    assert err.operation == BC_FAIL_OPERATION
    assert err.error == "ws"
    assert err.error_type == "RuntimeError"


@pytest.mark.asyncio
async def test_failure_context_carries_the_stimulus_error_and_its_type(
    broadcaster: AsyncMock,
    stats_in: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_45``/``_46`` (``"broadcast_stats"`` value), ``_49`` (``str(e)`` ->
    ``str(None)``) and ``_52`` (``type(e)`` -> ``type(None)``) - L1090-L1092 values.

    m45/m46 mutate the operation VALUE, m49 turns the error text into ``"None"``
    and m52 turns the type name into ``"NoneType"`` - four distinct legs, none of
    them reachable from the key-name test.
    """
    monitor = build_monitor(broadcaster=broadcaster)
    broadcaster.broadcast_gpu_stats.side_effect = RuntimeError(*STIMULUS.args)

    win(caplog)
    await monitor._broadcast_stats(stats_in)

    err = only(caplog, logging.ERROR, BC_FAIL_MSG)
    assert err.operation == "broadcast_stats", "L1090 value mutated"
    assert err.operation != "XXbroadcast_statsXX", "L1090 wrapped"
    assert err.error == str(STIMULUS), "L1091 must be str(e) of the stimulus"
    assert err.error != "None", "L1091 stopped describing the actual exception"
    assert err.error_type == type(STIMULUS).__name__, "L1092 must be type(e).__name__"
    assert err.error_type != "NoneType", "L1092 describes None, not the raised exception"


@pytest.mark.asyncio
async def test_the_context_manager_still_swallows_a_none_broadcaster() -> None:
    """Control: two None-broadcaster calls stay side-effect free.

    States the idempotence of the L1068 guard; kills nothing on its own, but it
    pins the guard against a variant whose early return started doing work.
    """
    monitor = build_monitor(broadcaster=None)

    await monitor._broadcast_stats({"gpu_name": "x"})
    await monitor._broadcast_stats({"gpu_name": "y"})

    assert len(monitor._stats_history) == 0, "_broadcast_stats never touches the history buffer"
    assert monitor.running is False, "_broadcast_stats never touches the running flag"


# =============================================================================
# g13 - GPUMonitor.start (gpu_monitor.py:1139-1155)
# =============================================================================


@pytest.mark.asyncio
async def test_start_creates_a_live_task_and_flips_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: the shipped cold start sets ``running`` and owns a live task."""
    monitor = bound_monitor(monkeypatch)

    await monitor.start()
    try:
        assert monitor.running is True, "L1149 sets running=True"
        assert monitor._poll_task is not None, "L1153 creates the polling task"
        assert not monitor._poll_task.done(), "start() does not await the task"
    finally:
        await monitor.stop()


@pytest.mark.asyncio
async def test_already_running_short_circuits_with_the_shipped_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_1``/``_2``/``_3``/``_4`` - the L1145 warning message.

    The shipped idempotency clause (documented at L1142) is the observable: the
    second call logs ONLY the warning, creates no task and logs neither INFO line.
    """
    monitor = bound_monitor(monkeypatch)
    await monitor.start()
    first = monitor._poll_task

    win(caplog)
    await monitor.start()

    only(caplog, logging.WARNING, ALREADY_WARN)
    assert at(caplog, logging.INFO) == [], "the already-running arm logs no INFO pair"
    assert at(caplog, logging.DEBUG) == [], "the already-running arm logs no DEBUG"
    assert monitor._poll_task is first, "the second start() must not replace the task"
    assert monitor.running is True
    await monitor.stop()


@pytest.mark.asyncio
async def test_cold_start_logs_the_shipped_pair_in_order(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kills ``_5``/``_6``/``_7``/``_8`` (L1148) and ``_18``/``_19``/``_20``/``_21`` (L1155).

    The shipped cold start logs EXACTLY two INFO lines, in this order, and no
    warning or debug: "Starting GPU monitoring" (L1148) then "GPU monitoring
    started successfully" (L1155).
    """
    monitor = bound_monitor(monkeypatch)

    win(caplog)
    await monitor.start()

    infos = at(caplog, logging.INFO)
    assert [r.msg for r in infos] == [STARTING_INFO, STARTED_INFO], (
        f"start() INFO pair mutated: {[r.msg for r in infos]}"
    )
    pin_record(infos[0], msg=STARTING_INFO, level=logging.INFO)
    pin_record(infos[1], msg=STARTED_INFO, level=logging.INFO)
    assert at(caplog, logging.WARNING) == [], "a cold start is not a warning"
    assert at(caplog, logging.DEBUG) == [], "the shipped start logs no DEBUG"
    await monitor.stop()


@pytest.mark.asyncio
async def test_the_poll_task_carries_the_shipped_debug_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kills ``_13`` (``name=None``), ``_15`` (``name=`` dropped, UNPARSEABLE/manual),
    ``_16`` (``"XXgpu-monitorXX"``) and ``_17`` (``"GPU-MONITOR"``).

    NEM-5057 added the name precisely so ``asyncio.all_tasks()`` reads well, so the
    NAME is the contract - and it is the ONLY observable, since every variant still
    hands back a live, running task with identical behaviour.
    """
    monitor = bound_monitor(monkeypatch)

    await monitor.start()
    try:
        task = monitor._poll_task
        assert isinstance(task, asyncio.Task), "L1153 creates an asyncio.Task"
        assert task.get_name() == TASK_NAME, (
            f"L1153 task name mutated: {task.get_name()!r} != {TASK_NAME!r}"
        )
    finally:
        await monitor.stop()


@pytest.mark.asyncio
async def test_start_is_idempotent_and_hands_back_the_same_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: three start() calls leave exactly one task standing.

    States the shipped docstring clause at L1142; kills nothing of its own, but it
    is what licenses the already-running leg to assert "no INFO pair" at all.
    """
    monitor = bound_monitor(monkeypatch)

    await monitor.start()
    first = monitor._poll_task
    await monitor.start()
    await monitor.start()

    assert monitor._poll_task is first, "repeated start() must not spawn extra pollers"
    await monitor.stop()
    assert monitor.running is False, "stop() clears the flag start() set"
