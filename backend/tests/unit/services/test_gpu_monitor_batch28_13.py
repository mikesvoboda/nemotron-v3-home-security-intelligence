"""S3 batch-28 lane gm13 - ``gpu_monitor`` groups G11 + G12 kill battery (44 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json``
groups 20 (``G11 get_current_stats_async``) and 21 (``G12 get_current_stats``),
``group_20.keys`` / ``group_21.keys`` and ``survivors.json``.  All 44 keys are
KILLABLE and are claimed by no other group (each function contributes exactly its
group's keys).

Key -> test map
===============
``get_current_stats_async`` (``group_20.keys``, 22 keys):
* ``__mutmut_1`` L893 ``logger.warning(None)``
  -> ``test_async_nvidia_smi_failure_warning_carries_the_exception_text``
  (SOLE route - no other arm of the method reaches L893).
* ``__mutmut_4`` msg -> None, ``_5`` ``extra=None``, ``_7`` drop the extra kwarg,
  ``_8``/``_9``/``_10`` the ERROR message string, ``_11``/``_12``/``_13``
  ``"gpu_id"``, ``_14``/``_15`` ``"gpu_name"``, ``_16``..``_19``
  ``"operation"`` + ``"get_current_stats_async"``, ``_20``/``_21``/``_22``
  ``"error"`` + ``str(e)``, ``_23``/``_24``/``_25`` ``"error_type"`` + ``type(e)``
  -> ``test_async_error_record_pins_every_extra_field`` and
     ``test_async_mock_producer_fault_logs_the_same_record`` (two independent
     routes to the same L905-L914 site, so no leg can be faked by a sibling).

``get_current_stats`` (``group_21.keys``, 22 keys) - the exact mirror:
* ``__mutmut_1`` L940 -> ``test_sync_nvidia_smi_failure_warning_carries_the_exception_text``
* ``_2``/``_3``/``_5``/``_6``/``_7``/``_8``/``_9``/``_10``/``_11``/``_12``/
  ``_13``/``_14``/``_15``/``_16``/``_17``/``_18``/``_19``/``_20``/``_21``/
  ``_22``/``_23`` -> ``test_sync_error_record_pins_every_extra_field`` and
  ``test_sync_mock_producer_fault_logs_the_same_record``.

Why the three bank rows each splice report calls UNPARSEABLE die on these legs
-----------------------------------------------------------------------------
``get_current_stats_async__mutmut_4/5/7`` and ``get_current_stats__mutmut_2/3/5``
are the multi-line ``logger.error(...)`` call whose AFTER text the bank reprints at
the statement indent, so mutmut's own line-based splice cannot be replayed by the
harness.  ``probe_g1x_m2345.py`` rebuilds each of the three AFTER texts verbatim,
compiles it, imports it and drives it with the fault this file injects.  Measured
divergence: shipped emits ONE ERROR whose ``getMessage()`` is the shipped text and
whose five extra attrs are present; msg->None gives ``getMessage() == "None"``,
``extra=None`` and the dropped-kwarg form give a record with NO
``gpu_id``/``gpu_name``/``operation``/``error``/``error_type``.  The two legs above
assert exactly those two surfaces (``only()`` + ``pin_error_extra()``), so all six
mutants redden.

Discipline
----------
* Shipped behaviour only.  The availability flags and the stats producers are the
  monitor's own attributes; faults are injected through them, never by bending
  production code.  ``_get_gpu_stats_mock`` is stubbed on the fault legs purely so
  the shipped handler's own fallback return can be observed (the shipped mock
  generator is pinned untouched on the control legs).
* Log assertions read the RAW ``record.msg`` inside a ``set_level`` + ``clear()``
  window filtered to this module's logger; the extra contract is asserted as
  record ATTRIBUTES, which is precisely what the renamed / ``extra=None`` /
  dropped-kwarg mutants break.
* No clock patching anywhere; ``datetime.now`` is never patched.
* No import-time global spies - every double is installed per test.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

import backend.services.gpu_monitor as M

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L893: logger.warning(f"nvidia-smi async fallback failed: {e}")
ASYNC_FALLBACK_WARNING = "nvidia-smi async fallback failed: down"

# L940: logger.warning(f"nvidia-smi fallback failed: {e}")
SYNC_FALLBACK_WARNING = "nvidia-smi fallback failed: down"

# L906 / L947: logger.error("Failed to get GPU stats", extra={...})
ERROR_MSG = "Failed to get GPU stats"

# L910 / L951: the shipped "operation" values (distinct per method).
OP_ASYNC = "get_current_stats_async"
OP_SYNC = "get_current_stats"

# L699: "gpu_name": "Mock GPU (Development Mode)" - the shipped mock fallback.
MOCK_GPU_NAME = "Mock GPU (Development Mode)"

# The monitor name the fault legs install; pinned so an error-record gpu_name
# assert can never be satisfied by an incidental value.
PROBE_GPU_NAME = "Probe GPU"
PROBE_FAULT = "probe fault"


def boom(text: str):
    """A zero-arg stand-in for a shipped producer that raises ``RuntimeError``."""

    def _raise() -> dict:
        raise RuntimeError(text)

    return _raise


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
    """Assert the observable surface of one shipped log call."""
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.getMessage() == msg, f"formatted text mutated: {r.getMessage()!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args: {r.args!r}"
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


def pin_error_extra(r: logging.LogRecord, *, operation: str) -> None:
    """The shipped NEM-1123 extra contract, asserted as record ATTRIBUTES.

    ``extra=None`` / a dropped ``extra`` kwarg leave NO attribute at all;
    ``"gpu_id" -> "GPU_ID"`` and friends move the value to another attribute;
    ``0 -> 1``, ``str(e) -> str(None)`` and ``type(e) -> type(None)`` keep the
    attribute but change the value.  Every assert below is therefore load bearing
    for the extra-side keys of each group.
    """
    assert r.gpu_id == 0, f'extra["gpu_id"] mutated: {getattr(r, "gpu_id", "<missing>")!r}'
    assert r.gpu_name == PROBE_GPU_NAME, (
        f'extra["gpu_name"] mutated: {getattr(r, "gpu_name", "<missing>")!r}'
    )
    assert r.operation == operation, (
        f'extra["operation"] mutated: {getattr(r, "operation", "<missing>")!r}'
    )
    assert r.error == PROBE_FAULT, f'extra["error"] mutated: {getattr(r, "error", "<missing>")!r}'
    assert r.error_type == "RuntimeError", (
        f'extra["error_type"] mutated: {getattr(r, "error_type", "<missing>")!r}'
    )


# =============================================================================
# Monitor harness
# =============================================================================


@pytest.fixture
def monitor() -> M.GPUMonitor:
    """A mock-mode GPUMonitor (pynvml import fails, nvidia-smi absent).

    ``sys.modules["pynvml"] = None`` is the interpreter's OWN ImportError trigger,
    so the ctor takes its shipped ImportError arm and never touches a GPU.  The
    name is replaced so an error-record ``gpu_name`` assert is a real pin rather
    than an incidental default.
    """
    with (
        patch.dict("sys.modules", {"pynvml": None}),
        patch("backend.services.gpu_monitor.shutil.which", return_value=None, autospec=True),
    ):
        mon = M.GPUMonitor()
    mon._gpu_name = PROBE_GPU_NAME
    return mon


# =============================================================================
# G11: get_current_stats_async (group_20, 22 keys)
# =============================================================================


@pytest.mark.asyncio
async def test_async_nvidia_smi_failure_warning_carries_the_exception_text(monitor, caplog):
    """L889-L893: the nvidia-smi arm fails -> WARNING carrying the exception text.

    mutmut_1's ``logger.warning(None)`` has no other route to this line.  Shipped
    then continues to the container arm (None) and the mock fallback, and logs NO
    ERROR - the continue-after-warning behaviour is part of the same pin.
    """
    monitor._nvidia_smi_available = True
    monitor._get_gpu_stats_nvidia_smi_async = AsyncMock(side_effect=RuntimeError("down"))
    monitor._get_gpu_stats_from_ai_containers = AsyncMock(return_value=None)

    win(caplog)
    stats = await monitor.get_current_stats_async()

    only(caplog, logging.WARNING, "nvidia-smi async fallback failed: down")
    assert monitor._get_gpu_stats_nvidia_smi_async.await_count == 1
    assert monitor._get_gpu_stats_from_ai_containers.await_count == 1
    assert at(caplog, logging.ERROR) == []
    assert stats["gpu_name"] == MOCK_GPU_NAME
    assert stats["recorded_at"].tzinfo is not None


@pytest.mark.asyncio
async def test_async_error_record_pins_every_extra_field(monitor, caplog):
    """L905-L914 via the pynvml arm: message + all five extras + mock fallback.

    ``_get_gpu_stats_real`` faults, the outer handler logs the record and returns
    the shipped mock dict (its ``_gpu_name`` stubbed to the probe name so this leg
    observes a record, not a second fault - the shipped generator is pinned
    untouched on the control legs).
    """
    monitor._gpu_available = True
    monitor._get_gpu_stats_real = boom(PROBE_FAULT)
    monitor._get_gpu_stats_mock = lambda: {"gpu_name": PROBE_GPU_NAME}

    win(caplog)
    stats = await monitor.get_current_stats_async()

    rec = only(caplog, logging.ERROR, ERROR_MSG)
    pin_error_extra(rec, operation=OP_ASYNC)
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.DEBUG) == []
    assert stats == {"gpu_name": PROBE_GPU_NAME}


@pytest.mark.asyncio
async def test_async_mock_producer_fault_logs_the_same_record(monitor, caplog):
    """Second, independent route to L905: the LAST-resort producer faults.

    Every earlier arm is disabled, so the outer except can only be reached
    through ``_get_gpu_stats_mock``.  Two independent routes to one site is what
    stops a single sibling mutant from faking the kill.
    """
    monitor._gpu_available = False
    monitor._nvidia_smi_available = False
    monitor._get_gpu_stats_from_ai_containers = AsyncMock(return_value=None)
    monitor._get_gpu_stats_mock = boom(PROBE_FAULT)

    win(caplog)
    with pytest.raises(RuntimeError, match="probe fault"):
        await monitor.get_current_stats_async()

    rec = only(caplog, logging.ERROR, ERROR_MSG)
    pin_error_extra(rec, operation=OP_ASYNC)


# ---------------------------------------------------------------------------
# G11 control legs - shipped arms the handler must not swallow.  These kill
# nothing of their own; they make the killing legs unambiguous.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_real_gpu_stats_short_circuits_everything(monitor, caplog):
    """L885-L886: the pynvml dict is returned verbatim, silently."""
    sentinel = {"gpu_name": PROBE_GPU_NAME, "marker": "real"}
    calls: list[str] = []
    monitor._gpu_available = True
    monitor._get_gpu_stats_real = lambda: (calls.append("real"), sentinel)[1]
    monitor._get_gpu_stats_from_ai_containers = AsyncMock(return_value=None)

    win(caplog)
    stats = await monitor.get_current_stats_async()

    assert stats == {"gpu_name": PROBE_GPU_NAME, "marker": "real"}
    assert calls == ["real"]
    assert monitor._get_gpu_stats_from_ai_containers.await_count == 0
    assert mine(caplog) == []


@pytest.mark.asyncio
async def test_async_nvidia_smi_success_returns_without_logging(monitor, caplog):
    """L891: the nvidia-smi dict is returned; the fallback WARNING stays silent."""
    monitor._gpu_available = False
    monitor._nvidia_smi_available = True
    monitor._get_gpu_stats_nvidia_smi_async = AsyncMock(return_value={"gpu_name": "via smi"})

    win(caplog)
    stats = await monitor.get_current_stats_async()

    assert stats == {"gpu_name": "via smi"}
    assert mine(caplog) == []


@pytest.mark.asyncio
async def test_async_ai_container_stats_short_circuit_the_mock_fallback(monitor, caplog):
    """L897-L899: the container dict is returned; no mock, no log."""
    monitor._gpu_available = False
    monitor._nvidia_smi_available = False
    monitor._get_gpu_stats_from_ai_containers = AsyncMock(
        return_value={"gpu_name": "NVIDIA GPU (via AI Containers)"}
    )

    win(caplog)
    stats = await monitor.get_current_stats_async()

    assert stats == {"gpu_name": "NVIDIA GPU (via AI Containers)"}
    assert mine(caplog) == []


@pytest.mark.asyncio
async def test_async_plain_mock_result_is_the_shipped_last_resort(monitor, caplog):
    """Control leg on the UNTOUCHED shipped mock generator: no GPU, no nvidia-smi,
    no containers -> the shipped mock dict, silently."""
    monitor._gpu_available = False
    monitor._nvidia_smi_available = False
    monitor._get_gpu_stats_from_ai_containers = AsyncMock(return_value=None)

    win(caplog)
    stats = await monitor.get_current_stats_async()

    assert stats["gpu_name"] == "Mock GPU (Development Mode)"
    assert stats["memory_total"] == 24576
    assert stats["recorded_at"].tzinfo is not None
    assert mine(caplog) == []


# =============================================================================
# G12: get_current_stats (group_21, 22 keys) - the sync mirror
# =============================================================================


def test_sync_nvidia_smi_failure_warning_carries_the_exception_text(monitor, caplog):
    """L936-L940: ``logger.warning(f"nvidia-smi fallback failed: {e}")``."""
    monitor._nvidia_smi_available = True
    monitor._get_gpu_stats_nvidia_smi = boom("down")

    win(caplog)
    stats = monitor.get_current_stats()

    only(caplog, logging.WARNING, "nvidia-smi fallback failed: down")
    assert at(caplog, logging.ERROR) == []
    assert stats["gpu_name"] == MOCK_GPU_NAME
    assert stats["recorded_at"].tzinfo is not None


def test_sync_error_record_pins_every_extra_field(monitor, caplog):
    """L946-L955 via the pynvml arm: message + all five extras + mock fallback."""
    monitor._gpu_available = True
    monitor._get_gpu_stats_real = boom(PROBE_FAULT)
    monitor._get_gpu_stats_mock = lambda: {"gpu_name": PROBE_GPU_NAME}

    win(caplog)
    stats = monitor.get_current_stats()

    rec = only(caplog, logging.ERROR, ERROR_MSG)
    pin_error_extra(rec, operation=OP_SYNC)
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.DEBUG) == []
    assert stats == {"gpu_name": PROBE_GPU_NAME}


def test_sync_mock_producer_fault_logs_the_same_record(monitor, caplog):
    """Second independent route to L946: the last-resort producer faults."""
    monitor._gpu_available = False
    monitor._nvidia_smi_available = False
    monitor._get_gpu_stats_mock = boom(PROBE_FAULT)

    win(caplog)
    with pytest.raises(RuntimeError, match="probe fault"):
        monitor.get_current_stats()

    rec = only(caplog, logging.ERROR, ERROR_MSG)
    pin_error_extra(rec, operation=OP_SYNC)


def test_sync_real_gpu_stats_short_circuits_the_fallback(monitor, caplog):
    """Control leg: L932-L933 returns the pynvml dict verbatim, silently."""
    calls: list[str] = []
    sentinel = {"gpu_name": PROBE_GPU_NAME, "marker": "real"}
    monitor._gpu_available = True
    monitor._get_gpu_stats_real = lambda: (calls.append("real"), sentinel)[1]

    win(caplog)
    stats = monitor.get_current_stats()

    assert stats == sentinel
    assert calls == ["real"]
    assert mine(caplog) == []


def test_sync_nvidia_smi_success_returns_without_logging(monitor, caplog):
    """Control leg: L938 returns the nvidia-smi dict; no warning, no error."""
    monitor._gpu_available = False
    monitor._nvidia_smi_available = True
    monitor._get_gpu_stats_nvidia_smi = lambda: {"gpu_name": "via smi"}

    win(caplog)
    stats = monitor.get_current_stats()

    assert stats == {"gpu_name": "via smi"}
    assert mine(caplog) == []


def test_sync_plain_mock_result_is_the_shipped_last_resort(monitor, caplog):
    """Control leg on the UNTOUCHED shipped mock generator: neither source
    available -> shipped mock dict, silently."""
    monitor._gpu_available = False
    monitor._nvidia_smi_available = False

    win(caplog)
    stats = monitor.get_current_stats()

    assert stats["gpu_name"] == "Mock GPU (Development Mode)"
    assert stats["gpu_utilization"] is not None
    assert stats["memory_total"] == 24576
    assert mine(caplog) == []


@pytest.mark.asyncio
async def test_the_two_operation_values_are_never_interchangeable(monitor, caplog):
    """Cross-method pin for the ``"operation"`` / value key mutants.

    The same fault driven through both methods must label the record with each
    method's OWN shipped value (L910 vs L951).  A mutant that renamed the value
    string on either line breaks one of the two asserts, and the pair rules out
    one shared literal satisfying both.
    """
    monitor._gpu_available = False
    monitor._nvidia_smi_available = False
    monitor._get_gpu_stats_from_ai_containers = AsyncMock(return_value=None)
    monitor._get_gpu_stats_mock = boom(PROBE_FAULT)

    win(caplog)
    with pytest.raises(RuntimeError, match=PROBE_FAULT):
        await monitor.get_current_stats_async()
    rec_async = only(caplog, logging.ERROR, ERROR_MSG)
    assert rec_async.operation == "get_current_stats_async"
    assert rec_async.operation != "get_current_stats"

    win(caplog)
    with pytest.raises(RuntimeError, match=PROBE_FAULT):
        monitor.get_current_stats()
    rec_sync = only(caplog, logging.ERROR, ERROR_MSG)
    assert rec_sync.operation == "get_current_stats"
    assert rec_sync.operation != "get_current_stats_async"
