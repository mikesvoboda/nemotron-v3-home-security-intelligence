"""S3 batch-28 gpu_monitor lane 00 - probe/init battery (groups G01, G03a, G03b).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json``
groups ``G01 _check_nvidia_smi ...`` (``group_0.keys``, 28 keys), ``G03a
GPUMonitor.__init__ ...`` (``group_1.keys``, 5 keys) and ``G03b _initialize_nvml
...`` (``group_2.keys``, 10 keys) - 43 KILLABLE keys, 0 EQUIVALENT.

Test -> mutant-key map
======================
Every key below is in ``group_0.keys`` / ``group_1.keys`` / ``group_2.keys``.

G01 - ``xǁGPUMonitorǁ_check_nvidia_smi`` (L234-264), 28 keys
- ``_mutmut_3`` / ``_mutmut_4``  L240 ``shutil.which("nvidia-smi")`` ->
  ``"XXnvidia-smiXX"`` / ``"NVIDIA-SMI"``
  -> ``test_probe_success_wires_the_flags_and_logs_the_available_info`` (the
     ``which`` argument identity is the ONLY observable of the lookup string).
- ``_mutmut_6`` .. ``_mutmut_10`` (call_arg: argv / capture_output / text /
  timeout / check -> None), ``_mutmut_11`` .. ``_mutmut_15`` (drop_arg x5),
  ``_mutmut_16`` .. ``_mutmut_19`` (L246 query strings wrap/upper), ``_mutmut_22``
  (L249 ``timeout=5`` -> 6), ``_mutmut_23`` (L250 ``check=False`` -> True), plus
  the L247/L248 legs of ``_mutmut_20`` / ``_mutmut_21``
  -> the ``run.assert_called_once_with([...], capture_output=True, text=True,
     timeout=5, check=False)`` call-identity pin (L245-251) repeated in every
  scenario that reaches the call.
- ``_mutmut_20`` (L247 ``capture_output=True`` -> False) and ``_mutmut_21``
  (L248 ``text=True`` -> False) carry a third occurrence-twin at L253
  (``self._nvidia_smi_available = True`` -> False), which the attribute-identity
  asserts in the success and rc=1 tests redden.
- ``_mutmut_32`` L255 ``split("\\n")`` -> ``split("XX\\nXX")``
  -> ``test_probe_takes_the_first_line_of_a_multi_gpu_blob``.
- ``_mutmut_34`` L256 ``logger.info(None)``
  -> ``test_probe_success_wires_the_flags_and_logs_the_available_info``.
- ``_mutmut_35`` L258 ``logger.warning(None)``
  -> ``test_probe_with_nonzero_rc_warns_with_the_captured_stderr``.
- ``_mutmut_36`` L262 ``logger.warning(None)``
  -> ``test_probe_oserror_from_the_test_query_warns_and_keeps_the_flag_false``.
- ``_mutmut_37`` .. ``_mutmut_40`` L264 ``logger.debug(None)`` / wrap / lower /
  upper -> ``test_probe_without_the_binary_logs_the_not_found_debug``.
  (The rc=1 / timeout / OSError rows also prove the L259-260 timed-out row is
  reached only by its own stimulus: ``test_probe_that_times_out_warns_the_timed_out_message``.)

G03a - ``xǁGPUMonitorǁ__init__`` (L144-201), 5 keys
- ``_mutmut_19`` L175 ``_gpu_handle = None`` -> ``""``, ``_mutmut_23`` L180
  ``_nvidia_smi_path``, ``_mutmut_30`` L187 ``_last_warning_event_at``,
  ``_mutmut_31`` L188 ``_last_critical_event_at``
  -> ``test_init_seeds_the_idle_state_attributes_to_none`` (``is None`` attribute
     identity; manifest notes L3 admits this because ``get_memory_pressure_metrics``
     falsy-shields ``""`` vs ``None``).
- ``_mutmut_33`` L197 ``logger.info(None)``
  -> ``test_init_logs_the_shipped_startup_summary_with_explicit_args``.

G03b - ``xǁGPUMonitorǁ_initialize_nvml`` (L203-232), 10 keys
- ``_mutmut_4`` L217 ``nvmlDeviceGetHandleByIndex(0)`` -> ``(None)`` and
  ``_mutmut_5`` ``0`` -> ``1`` and ``_mutmut_7`` L218
  ``nvmlDeviceGetName(self._gpu_handle)`` -> ``(None)`` and ``_mutmut_10`` L220
  ``logger.info(None)``
  -> ``test_nvml_success_wires_the_handle_and_logs_the_detected_info``.
- ``_mutmut_11`` L222 ``logger.warning(None)``
  -> ``test_nvml_device_error_warns_with_the_exception_and_keeps_nvml_live``.
- ``_mutmut_14`` .. ``_mutmut_17`` L226 ``logger.warning(None)`` + wrap/lower/
  upper -> ``test_missing_pynvml_warns_the_installed_message``.
- ``_mutmut_22`` L230 ``logger.warning(None)``
  -> ``test_nvml_init_failure_warns_the_initialize_message``.

Discipline
----------
* pynvml is ALWAYS fake: the ImportError branches install the documented
  ``sys.modules["pynvml"] = None`` sentinel (CPython turns that into an
  ``ImportError`` - verified) and the success branches a ``MagicMock`` module with
  a real ``NVMLError`` class.  No real GPU, no ``builtins.__import__`` spy, and
  the slot is restored by the fixture.
* nvidia-smi is always a double: construction is always scripted with
  ``shutil.which`` -> None (so the construction-time probe takes the not-found
  branch and never reaches ``subprocess.run``), and the probed call runs on its own
  ``autospec=True`` double that every test pins.  Nothing is ever spawned, and no
  target is patched twice at once (3.14 mock refuses to spec a Mock).
* Log assertions read the RAW ``record.msg`` / ``levelno`` / ``args`` /
  ``exc_info`` in a window opened per assertion (``set_level`` + ``clear()``) and
  filtered to this module's logger name.
* No clock is patched anywhere (G01/G03a/G03b contain no timing site), no
  import-time global spy, no session-scoped patch.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Iterator
from typing import Any, NamedTuple
from unittest.mock import MagicMock, patch

import pytest

from backend.services import gpu_monitor as M

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]

# Sentinel telling a fixture's restore path that the slot was absent beforehand.
_MISSING = object()

# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L240: nvidia_smi_path = shutil.which("nvidia-smi")
WHICH_ARG = "nvidia-smi"
# L246: [nvidia_smi_path, "--query-gpu=name", "--format=csv,noheader,nounits"]
PROBE_ARGV = ["/usr/bin/nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"]
# L247-L250: capture_output=True, text=True, timeout=5, check=False
PROBE_KWARGS = {"capture_output": True, "text": True, "timeout": 5, "check": False}
# L256: logger.info(f"nvidia-smi available at {nvidia_smi_path}, GPU: {self._gpu_name}")
PROBE_OK_INFO = "nvidia-smi available at /usr/bin/nvidia-smi, GPU: GeForce A"
# L258: logger.warning(f"nvidia-smi found but returned error: {result.stderr.strip()}")
PROBE_RC_WARNING = "nvidia-smi found but returned error: boom"
# L260: logger.warning("nvidia-smi found but timed out during test query")
PROBE_TIMEOUT_WARNING = "nvidia-smi found but timed out during test query"
# L262: logger.warning(f"nvidia-smi found but failed during test: {e}")
PROBE_FAIL_WARNING = "nvidia-smi found but failed during test: nope"
# L264: logger.debug("nvidia-smi not found in PATH")
PROBE_MISSING_DEBUG = "nvidia-smi not found in PATH"
# L197-L201: logger.info(f"GPUMonitor initialized (poll_interval=..., history_minutes=...,
#            http_timeout=..., gpu_available=..., nvidia_smi_available=...)")
INIT_INFO = (
    "GPUMonitor initialized (poll_interval=7.5s, history_minutes=3m, "
    "http_timeout=2.5s, gpu_available=False, nvidia_smi_available=False)"
)
# L197-L201 again, on the branch where NVML found the device
INIT_INFO_NVML_OK = (
    "GPUMonitor initialized (poll_interval=7.5s, history_minutes=3m, "
    "http_timeout=2.5s, gpu_available=True, nvidia_smi_available=False)"
)
# L220: logger.info(f"GPU detected: {self._gpu_name}")
DETECTED_INFO = "GPU detected: FakeGPU"
# L222: logger.warning(f"No GPU device found: {e}. Will return mock data.")
DEVICE_ERROR_WARNING = "No GPU device found: no device. Will return mock data."
# L226: logger.warning("pynvml not installed. Will try nvidia-smi fallback.")
NO_PYNVML_WARNING = "pynvml not installed. Will try nvidia-smi fallback."
# L230: logger.warning(f"Failed to initialize NVML: {e}. Will try nvidia-smi fallback.")
NVML_INIT_WARNING = "Failed to initialize NVML: nv. Will try nvidia-smi fallback."

NVML_SLOT = "pynvml"  # shipped L210 is a bare `import pynvml` -> the sys.modules slot
WHICH = "backend.services.gpu_monitor.shutil.which"  # shipped L240 attribute lookup
RUN = "backend.services.gpu_monitor.subprocess.run"  # shipped L245 attribute lookup


# =============================================================================
# Observation helpers (batch27_01 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load-bearing.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped log call.

    ``record.msg`` is the RAW message.  Every shipped site in these groups passes
    a single already-interpolated string, so ``args`` must stay empty (a moved
    argument would land IN ``msg``) and ``exc_info`` must stay absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for a plain message: {r.args!r}"
    assert r.exc_info is None, (
        f"exc_info present where the shipped call passes none: {r.exc_info!r}"
    )


def exactly_one(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` with RAW text ``msg`` in the window.

    Matching is on (level, msg) so a test that legitimately emits a second record
    at the same level (e.g. the construction summary alongside a detection line)
    still pins its own target exactly; the ``msg`` equality itself is what falsifies
    the wrap/upper/lower/None mutants.
    """
    recs = [r for r in at(caplog, level) if r.msg == msg]
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record {msg!r} from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in at(caplog, level)]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


# =============================================================================
# Fixtures (no import-time spies; every global is restored)
# =============================================================================


@pytest.fixture
def no_pynvml() -> Iterator[None]:
    """Force ``import pynvml`` (shipped L210) to raise ImportError.

    ``sys.modules[name] = None`` is CPython's documented ImportError sentinel, so
    no ``builtins.__import__`` spy is needed and nothing global is rebound.
    """
    saved = sys.modules.get(NVML_SLOT, _MISSING)
    sys.modules[NVML_SLOT] = None
    try:
        yield
    finally:
        if saved is _MISSING:
            del sys.modules[NVML_SLOT]
        else:
            sys.modules[NVML_SLOT] = saved


@pytest.fixture
def fake_pynvml() -> Iterator[MagicMock]:
    """Install a fake ``pynvml`` module whose ``NVMLError`` is a real class."""
    saved = sys.modules.get(NVML_SLOT, _MISSING)
    module = MagicMock(name="pynvml-module")
    module.NVMLError = type("NVMLError", (Exception,), {})
    module.nvmlInit.return_value = None
    module.nvmlDeviceGetHandleByIndex.return_value = MagicMock(name="gpu-handle")
    module.nvmlDeviceGetName.return_value = "FakeGPU"
    sys.modules[NVML_SLOT] = module
    try:
        yield module
    finally:
        if saved is _MISSING:
            del sys.modules[NVML_SLOT]
        else:
            sys.modules[NVML_SLOT] = saved


def completed(returncode: int, stdout: str, stderr: str = "") -> subprocess.CompletedProcess[str]:
    """A real CompletedProcess - shipped code reads exactly three plain attributes."""
    return subprocess.CompletedProcess(["/usr/bin/nvidia-smi"], returncode, stdout, stderr)


class Probe(NamedTuple):
    """The outcome of one ``_check_nvidia_smi`` call under a scripted environment."""

    monitor: Any
    which: MagicMock
    run: MagicMock


def probe_once(
    caplog: pytest.LogCaptureFixture,
    which_return: str | None,
    *,
    result: subprocess.CompletedProcess[str] | None = None,
    side_effect: BaseException | None = None,
) -> Probe:
    """Build a monitor (pynvml absent, binary absent) then probe it ONCE.

    Construction gets ``which`` -> None, so the construction-time probe (shipped
    L194-195) takes the not-found branch and NEVER reaches ``subprocess.run``; the
    scenario double therefore sees exactly the one explicit call below, with no
    mock reset and no nested patch of the same target.
    """
    with patch(WHICH, return_value=None, autospec=True):
        monitor = M.GPUMonitor(poll_interval=7.5, history_minutes=3, http_timeout=2.5)
    with (
        patch(WHICH, return_value=which_return, autospec=True) as which,
        patch(RUN, return_value=result, side_effect=side_effect, autospec=True) as run,
    ):
        win(caplog)
        monitor._check_nvidia_smi()
    return Probe(monitor, which, run)


# =============================================================================
# G01  xǁGPUMonitorǁ_check_nvidia_smi - the success arm
#      mutmut_3/4 (which string), 6-15 (call contract), 16-19 (query strings),
#      20-23 (kwargs values / timeout / check), 32 (first line), 34 (INFO arg)
# =============================================================================


def test_probe_success_wires_the_flags_and_logs_the_available_info(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Found + rc=0 -> the exact which/subprocess call, the wiring, and the INFO.

    Shipped backend/services/gpu_monitor.py:240-256::

        nvidia_smi_path = shutil.which("nvidia-smi")
        if nvidia_smi_path:
            try:
                result = subprocess.run(
                    [nvidia_smi_path, "--query-gpu=name", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    self._nvidia_smi_available = True
                    self._nvidia_smi_path = nvidia_smi_path
                    self._gpu_name = result.stdout.strip().split("\\n")[0]
                    logger.info(f"nvidia-smi available at {nvidia_smi_path}, GPU: {self._gpu_name}")

    The probe has exactly four observables - the two calls it makes, the three
    attributes it writes and the one INFO it logs - and all four are pinned.
    """
    found = probe_once(caplog, "/usr/bin/nvidia-smi", result=completed(0, "GeForce A"))

    # L240: the lookup string itself is shipped behaviour (kills wrap/upper).
    assert found.which.call_args.args == (WHICH_ARG,), f"which() arg mutated: {found.which!r}"
    # L245-251: argv list plus all four keyword names/values, verbatim.
    found.run.assert_called_once_with(PROBE_ARGV, **PROBE_KWARGS)
    # L253-255: the wiring the success arm performs.
    assert found.monitor._nvidia_smi_available is True
    assert found.monitor._nvidia_smi_path == "/usr/bin/nvidia-smi"
    assert found.monitor._gpu_name == "GeForce A"
    # L256: the INFO text.
    exactly_one(caplog, logging.INFO, PROBE_OK_INFO)


def test_probe_takes_the_first_line_of_a_multi_gpu_blob(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Two stdout lines -> ``_gpu_name`` is the FIRST line only (L255).

    ``split("XX\\nXX")`` (mutmut_32) never splits the blob, so the whole two-line
    stdout would become the GPU name.
    """
    found = probe_once(caplog, "/usr/bin/nvidia-smi", result=completed(0, "GeForce A\nGeForce B"))

    found.run.assert_called_once_with(PROBE_ARGV, **PROBE_KWARGS)
    assert found.monitor._gpu_name == "GeForce A"
    exactly_one(caplog, logging.INFO, PROBE_OK_INFO)


# =============================================================================
# G01  the four non-success arms of _check_nvidia_smi
#      mutmut_23 (second route), 35, 36, 37-40 + the L253 twin leg
# =============================================================================


def test_probe_with_nonzero_rc_warns_with_the_captured_stderr(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """rc=1 -> WARNING naming the stripped stderr, every flag left untouched.

    Shipped ``...:252-258``: the ``else`` arm logs
    ``f"nvidia-smi found but returned error: {result.stderr.strip()}"``.  With the
    shipped ``check=False`` (L250) a non-zero rc is NOT raised, which is what makes
    this row the second route for the ``check=True`` mutant as well.
    """
    found = probe_once(caplog, "/usr/bin/nvidia-smi", result=completed(1, "", "  boom  "))

    found.run.assert_called_once_with(PROBE_ARGV, **PROBE_KWARGS)
    exactly_one(caplog, logging.WARNING, PROBE_RC_WARNING)
    assert found.monitor._nvidia_smi_available is False
    assert found.monitor._nvidia_smi_path is None
    assert found.monitor._gpu_name is None


def test_probe_that_times_out_warns_the_timed_out_message(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TimeoutExpired -> the constant timed-out WARNING, flag stays False (L259-260)."""
    found = probe_once(
        caplog,
        "/usr/bin/nvidia-smi",
        side_effect=subprocess.TimeoutExpired("nvidia-smi", 5),
    )

    found.run.assert_called_once_with(PROBE_ARGV, **PROBE_KWARGS)
    exactly_one(caplog, logging.WARNING, PROBE_TIMEOUT_WARNING)
    assert found.monitor._nvidia_smi_available is False


def test_probe_oserror_from_the_test_query_warns_and_keeps_the_flag_false(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A generic ``Exception`` -> WARNING carrying the exception text (L261-262)::

    except Exception as e:
        logger.warning(f"nvidia-smi found but failed during test: {e}")
    """
    found = probe_once(caplog, "/usr/bin/nvidia-smi", side_effect=OSError("nope"))

    found.run.assert_called_once_with(PROBE_ARGV, **PROBE_KWARGS)
    exactly_one(caplog, logging.WARNING, PROBE_FAIL_WARNING)
    assert found.monitor._nvidia_smi_available is False


def test_probe_without_the_binary_logs_the_not_found_debug(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``which`` -> None -> exactly one DEBUG with the shipped text (L263-264).

    All four L264 keys (``logger.debug(None)`` + wrap + lower + upper) are
    falsified by the raw-text + level + exactly-one pin.
    """
    found = probe_once(caplog, None)

    assert found.which.call_args.args == (WHICH_ARG,)
    found.run.assert_not_called()
    exactly_one(caplog, logging.DEBUG, PROBE_MISSING_DEBUG)
    assert found.monitor._nvidia_smi_available is False
    assert found.monitor._nvidia_smi_path is None


# =============================================================================
# G03a  xǁGPUMonitorǁ__init__ - idle state + startup summary
#       mutmut_19/23/30/31 (None -> "") + mutmut_33 (logger.info(None))
# =============================================================================


def test_init_seeds_the_idle_state_attributes_to_none(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A monitor that found nothing holds ``None`` (not ``""``) in four slots.

    Shipped ``...:175/180/187/188``::

        self._gpu_handle: Any = None
        self._nvidia_smi_path: str | None = None
        self._last_warning_event_at: datetime | None = None
        self._last_critical_event_at: datetime | None = None

    ``get_memory_pressure_metrics`` renders falsy ``""`` and ``None`` the same, so
    the ATTRIBUTE IDENTITY is the shipped-state observable the manifest admits
    (notes L3).
    """
    with patch(WHICH, return_value=None, autospec=True):
        monitor = M.GPUMonitor(poll_interval=7.5, history_minutes=3, http_timeout=2.5)

    assert monitor._gpu_handle is None
    assert monitor._nvidia_smi_path is None
    assert monitor._last_warning_event_at is None
    assert monitor._last_critical_event_at is None


def test_init_logs_the_shipped_startup_summary_with_explicit_args(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The construction INFO summarises the five live settings (L197-201)::

        logger.info(
            f"GPUMonitor initialized (poll_interval={self.poll_interval}s, "
            f"history_minutes={self.history_minutes}m, http_timeout={self._http_timeout}s, "
            f"gpu_available={self._gpu_available}, nvidia_smi_available={self._nvidia_smi_available})"
        )

    ``logger.info(None)`` (mutmut_33) replaces the whole f-string with ``None``.
    The ``pynvml not installed`` WARNING (L226) rides a different level, so the
    level filter keeps this pin about the shipped INFO call.
    """
    with patch(WHICH, return_value=None, autospec=True):
        win(caplog)
        M.GPUMonitor(poll_interval=7.5, history_minutes=3, http_timeout=2.5)

    exactly_one(caplog, logging.INFO, INIT_INFO)


# =============================================================================
# G03b  xǁGPUMonitorǁ_initialize_nvml - the four branches
#       mutmut_4/5/7/10 (success), 11 (NVMLError), 14-17 (ImportError), 22 (init)
# =============================================================================


def test_nvml_success_wires_the_handle_and_logs_the_detected_info(
    fake_pynvml: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """pynvml present -> index 0, the name read from THAT handle, INFO with it.

    Shipped ``...:212-220``::

        pynvml.nvmlInit()
        self._nvml_initialized = True
        try:
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._gpu_name = pynvml.nvmlDeviceGetName(self._gpu_handle)
            self._gpu_available = True
            logger.info(f"GPU detected: {self._gpu_name}")

    The NVML-success path never runs the nvidia-smi check (L194-195), so the window
    holds the L220 detection INFO plus the L197 startup summary; ``exactly_one``
    filters the level+text pair, and the ``which`` double proves the probe branch
    was skipped.
    """
    with patch(WHICH, return_value=None, autospec=True) as which:
        win(caplog)
        monitor = M.GPUMonitor(poll_interval=7.5, history_minutes=3, http_timeout=2.5)

    assert fake_pynvml.nvmlDeviceGetHandleByIndex.call_args.args == (0,)
    assert fake_pynvml.nvmlDeviceGetName.call_args.args[0] is monitor._gpu_handle
    assert monitor._gpu_available is True
    assert monitor._nvml_initialized is True
    assert monitor._gpu_name == "FakeGPU"
    which.assert_not_called()
    exactly_one(caplog, logging.INFO, DETECTED_INFO)
    # The window holds EXACTLY the two shipped INFO calls (L220 then L197) - a
    # mutant that logs the detection line twice or loses the summary trips this.
    assert [(r.levelno, r.msg) for r in at(caplog, logging.INFO)] == [
        (logging.INFO, DETECTED_INFO),
        (logging.INFO, INIT_INFO_NVML_OK),
    ]


def test_nvml_device_error_warns_with_the_exception_and_keeps_nvml_live(
    fake_pynvml: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``NVMLError`` from the handle lookup -> mock-data WARNING, NVML stays live.

    Shipped ``...:221-223``::

        except pynvml.NVMLError as e:
            logger.warning(f"No GPU device found: {e}. Will return mock data.")
            self._gpu_available = False

    ``_nvml_initialized`` stays True (L213 already ran) while ``_gpu_available``
    drops, and construction then falls through to the nvidia-smi check.
    """
    fake_pynvml.nvmlDeviceGetHandleByIndex.side_effect = fake_pynvml.NVMLError("no device")
    with patch(WHICH, return_value=None, autospec=True):
        win(caplog)
        monitor = M.GPUMonitor(poll_interval=7.5, history_minutes=3, http_timeout=2.5)

    exactly_one(caplog, logging.WARNING, DEVICE_ERROR_WARNING)
    assert monitor._gpu_available is False
    assert monitor._nvml_initialized is True
    assert monitor._gpu_name is None


def test_missing_pynvml_warns_the_installed_message(
    no_pynvml: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ImportError -> the constant fallback WARNING + both flags cleared (L225-228)::

    except ImportError:
        logger.warning("pynvml not installed. Will try nvidia-smi fallback.")
    """
    with patch(WHICH, return_value=None, autospec=True):
        win(caplog)
        monitor = M.GPUMonitor(poll_interval=7.5, history_minutes=3, http_timeout=2.5)

    exactly_one(caplog, logging.WARNING, NO_PYNVML_WARNING)
    assert monitor._gpu_available is False
    assert monitor._nvml_initialized is False


def test_nvml_init_failure_warns_the_initialize_message(
    fake_pynvml: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-ImportError from ``nvmlInit`` -> the generic NVML-failure WARNING.

    Shipped ``...:229-232``::

        except Exception as e:
            logger.warning(f"Failed to initialize NVML: {e}. Will try nvidia-smi fallback.")

    ``RuntimeError("nv")`` is not an ``ImportError``, so the L230 arm - not the
    L226 arm - is the one that runs.
    """
    fake_pynvml.nvmlInit.side_effect = RuntimeError("nv")
    with patch(WHICH, return_value=None, autospec=True):
        win(caplog)
        monitor = M.GPUMonitor(poll_interval=7.5, history_minutes=3, http_timeout=2.5)

    exactly_one(caplog, logging.WARNING, NVML_INIT_WARNING)
    assert monitor._gpu_available is False
    assert monitor._nvml_initialized is False
