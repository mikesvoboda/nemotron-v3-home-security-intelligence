"""S3 batch-28 lane L2 - ``detector_client`` group dc02 kill battery (45 keys).

Module: ``backend/services/detector_client.py`` (md5 ``294c938abe9e37cd0f979f9357982753``
- the manifest-proven source).  Admitted manifest: ``/tmp/wp-pw/detector_client/``
``manifest.json`` group ``dc02-init-flags-circuitbreaker-startup-log`` (45 KILLABLE /
0 EQUIVALENT), ``manifest_groups/dc02-init-flags-circuitbreaker-startup-log.keys``
(= ``group_01.keys``) and ``survivors.json`` for the exact per-key diffs.

Production ref: ``DetectorClient.__init__`` L262-370 - detector type/model + gateway
route (L280-288), retry/concurrency (L313-317), the ``CircuitBreaker`` config
(L336-345), the warmup flags (L347-350) and the startup INFO log (L352-370).

Construction legs autospec-patch ``backend.services.detector_client.get_settings`` (the
binding the shipped body calls at L277; ``get_settings`` is ``@cache``d at
``backend/core/config.py:3511``, so the module binding is the patch point) with a
``MagicMock(spec=Settings)`` stand-in - the idiom the shipped suite already uses at
``test_detector_client.py:463`` - plus ``httpx.AsyncClient`` so construction opens no
socket.

Test -> mutant-key map  (``mN`` == ``__init____mutmut_N``)
==========================================================
N1 ``test_the_shipped_detector_type_and_model_version_are_stored``
   ``m6``/``m7``/``m8`` (L281 ``_model_version`` -> ``None`` / XX-wrap / upper)
N2 ``test_the_gateway_route_is_used_only_for_a_configured_string_url`` (3 params)
   (control for the L284 gate - it sets the flag PRESENT, so neither ``m20`` nor ``m26``
   reaches it; the two defaults are only live when the attribute is ABSENT, which is N25)
N3 ``test_the_gateway_url_loses_only_its_trailing_slashes``
   ``m32`` (L285 ``rstrip("/")`` -> ``rstrip("XX/XX")``) - INEFFECTIVE for m32 (both strip-sets
   remove a run of pure slashes identically); the real route is N27
N4 ``test_the_max_retries_argument_overrides_the_setting_and_zero_is_kept`` (3 params) +
   ``test_the_constructor_without_an_argument_uses_the_setting``
   ``m59`` (L314 ``max_retries is not None`` -> ``... or True``); second route ``m61``
N5 ``test_the_inference_concurrency_limit_comes_from_the_setting``
   ``m61`` (L317 ``_max_concurrent`` -> ``None``)
N6 ``test_the_circuit_breaker_is_named_for_the_detector_type``
   (control) the per-detector breaker name; its ``failure_threshold == 5`` field read does
   NOT reach ``m94`` - the dataclass default IS 5, so the dropped argument is value-identical
   (see N29 for the kill route)
N7 ``test_the_circuit_breaker_config_is_pinned_and_its_arguments_are_present``
   ``m91``/``m92`` (the two -> ``None``), ``m101``/``m102`` (``3`` -> ``4``, ``2`` -> ``3``) -
   and see N29: the ``m94``/``m96``/``m97`` dropped arguments are NOT visible on the
   constructed config at all, so this field walkthrough does not reach them

The six repaired routes (the group's original 39/45 residual) and ONE equivalence
===================================================================================
N25 ``test_the_absent_gateway_flag_falls_back_to_the_shipped_false_default``
   ``m26`` (L284 ``getattr`` default ``False`` -> ``True``) - the attribute is made genuinely
   ABSENT, so the DEFAULT is the live value: shipped ``False is True`` keeps the direct URL,
   the mutant's ``True is True`` routes to the gateway
N26 ``test_the_startup_record_url_follows_the_absent_gateway_flag``
   ``m26`` - second route, via the startup record's ``detector_url`` KEY
N27 ``test_the_gateway_join_strips_only_forward_slashes`` (5 params)
   ``m32`` (L285 ``rstrip("/")`` -> ``rstrip("XX/XX")``) - the mutant's strip-set is
   ``{"X", "/"}``, so the legs put an uppercase ``X`` AT the strip boundary plus a
   no-trailing-slash identity leg; N3's ``"//"-ending`` base is invisible to the mutant
N28 ``test_the_gateway_route_requires_a_string_url`` (2 params)
   (control for the L284 ``isinstance(gw_url, str)`` conjunct - a non-str setting keeps the
   direct URL under every mutant of the ``getattr`` default, since the flag is PRESENT True)
N29 ``test_the_constructor_passes_every_circuit_breaker_argument_to_the_config``
   ``m94``/``m96``/``m97`` (the three DROPPED ``CircuitBreakerConfig`` arguments) via an
   autospec + ``side_effect`` spy on THIS module's binding, which is the ONLY place a dropped
   argument with a value-equal dataclass default is observable; second routes on ``m91``/
   ``m92``/``m101``/``m102`` (a VALUE assert on the same kwargs dict)
N30 ``test_the_client_breaker_excludes_only_the_client_error_type``
   (behaviour control, no group survivor routes here) - the L342 ``excluded_exceptions=
   (ValueError,)`` is observable BEHAVIOUR at ``circuit_breaker.py:486-491`` (an excluded
   exception is re-raised WITHOUT ``_record_failure``), which pins the tuple the N7 field
   assert only reads.  NOTE: the bank's ``m97`` drops ``success_threshold=2,`` - NOT this
   argument (measured: its splice deletes the L342 line, whose place is then taken by the
   L343 ``excluded_exceptions`` line) - and no surviving mutant touches ``excluded_exceptions``
   at all, so N29 is m94/m96/m97's kill route and this leg guards the shipped tuple itself
N31 ``test_the_client_breaker_records_a_non_excluded_failure``
   (control for N30) - a type outside the tuple DOES record, so N30's zeros are the exclusion

UNKILLABLE - ``m20`` (L284 ``getattr(settings, "use_ai_gateway", False)`` -> ``None``)
=====================================================================================
This key is reported NOT KILLED and no test is written for it, because no test CAN kill it.
The default is consumed by exactly one construct - the ``is True`` comparison - so the only
reachable divergence is an ABSENT attribute, where shipped reads ``False`` and the mutant
reads ``None``; ``False is True`` and ``None is True`` are both ``False``, so the branch,
``self._detector_url``, the breaker and every log record are identical.  For a PRESENT
attribute the default is never evaluated.  There is no input, settings posture or
observation that separates the two programs - a true call-site equivalence (this is
``/tmp/wp-pw/detector_client/audit.md`` correction ``C7``).  ``m26`` is the killable sibling
of the same line and N25/N26 kill it.
N8 ``test_the_warmup_flags_are_read_from_the_settings_verbatim``
   ``m104``/``m105`` (L349 ``_is_warming = False`` -> ``None`` / ``True``)
N9 ``test_the_startup_banner_is_an_info_record_with_the_shipped_key_set``
   ``m110`` (L357 message -> ``None``), ``m111`` (L357 ``extra`` -> ``None``), ``m113``
   (``extra`` argument dropped), ``m114``/``m115``/``m116`` (L358 message XX-wrap / lower
   / upper) and EVERY KEY rename: ``m117``/``m118``, ``m119``/``m120``, ``m121``/``m122``,
   ``m123``/``m124``, ``m125``/``m126``, ``m127``/``m128``, ``m129``/``m130``,
   ``m131``/``m132``, ``m134``/``m135``
N10 ``test_the_startup_extra_carries_the_measured_values_and_the_pinned_constants``
   ``m108``/``m109`` (the L354/L355 helper results -> ``None``), ``m133`` (``5`` ->
   ``6``), ``m136`` (``60.0`` -> ``61.0``) + second route onto ``m121``-``m128``
N11 ``test_the_startup_record_is_the_only_info_line_the_constructor_emits`` (control)
N12 ``test_the_startup_values_follow_the_settings_not_the_double_defaults``
   second route onto ``m129``/``m130`` and the value-carrying ``m123``-``m128``

Occurrence twins - ``m117``/``m118`` (17 sites) and ``m127``/``m128`` (7 sites)
==============================================================================
The splice report lists these four keys as ``twin``: ``__init__`` is the FIRST emitter of
the KEY strings ``"detector_type"`` / ``"max_retries"``, but the bank's stripped text also
matches the 16 / 6 later sites in ``_send_detection_request`` and ``detect_objects``, and
the bank does not say which site is the real mutant - so EVERY site must redden.  N9
kills the ``__init__`` site; N13-N24 drive every other site and pin the COMPLETE
``extra`` payload of each record.  All request legs use ``max_retries=2`` so the shipped
``if attempt < self._max_retries - 1`` gate emits BOTH the retry WARNING and the terminal
ERROR, and the backoff ``await asyncio.sleep(delay)`` (L713/L748/L767/L803/L836/L864/L896)
is autospec-patched for the window so no wall clock is spent or asserted:

  N13 ``test_the_happy_path_posts_the_multipart_body_and_logs_nothing``      (control)
  N14 ``test_the_connection_arm_warns_then_fails_with_the_pinned_payloads``
      ``m117``/``m118`` L695 + L710, ``m127``/``m128`` L699
  N15 ``test_the_timeout_arm_warns_then_fails_with_the_pinned_payloads``
      ``m117`` L726 + L741, ``m127`` L730
  N16 ``test_the_asyncio_timeout_arm_warns_then_fails_with_the_pinned_payloads``
      ``m117`` L759 + L775, ``m127`` L763
  N17 ``test_the_server_error_arm_warns_then_fails_with_the_pinned_payloads``
      ``m117`` L795 + L810, ``m127`` L800
  N18 ``test_the_unexpected_error_arm_warns_then_fails_with_the_pinned_payloads``
      ``m117`` L887 + L902, ``m127`` L891
  N19 ``test_the_4xx_leg_raises_valueerror_with_the_client_error_record``
      ``m117``/``m118`` L833 (the 4xx ERROR; no ``max_retries`` KEY sits there)
  N20 ``test_the_json_error_arm_warns_then_fails_with_the_pinned_payloads``
      ``m117`` L855 + L870, ``m127`` L859
  N21 ``test_detect_objects_rejects_the_request_while_the_circuit_is_open``
      ``m117``/``m118`` L1072
  N22 ``test_detect_objects_survives_a_tripped_breaker_inside_the_request``
      ``m117``/``m118`` L1409
  N23 ``test_detect_objects_reports_an_unexpected_read_failure_as_unavailable``
      ``m117``/``m118`` L1433
  N24 ``test_detect_objects_stores_the_detections_from_the_response``   (control)

Discipline
----------
* Log assertions open a capture window per leg (``caplog.set_level(DEBUG, logger=...)``
  plus ``clear()``, filtered to this module's logger name) and read the RAW
  ``record.msg``, ``record.args``, ``record.levelno`` and ``record.exc_info``; the
  ``extra=`` payload is recovered as "record attributes beyond the ``LogRecord`` core
  plus this module's ``ContextFilter`` contributions" (measured, below), which is how
  ``extra=None``, a dropped ``extra`` and a renamed KEY all become visible.
* Every mock of a real attribute is ``autospec=True``, or ``new=`` where the replacement
  is ALREADY a spec'd double (``patch`` rejects ``autospec`` + ``new`` together):
  ``get_settings``, ``httpx.AsyncClient``, ``_is_free_threaded``,
  ``_get_preprocess_worker_count``, ``asyncio.sleep``, ``_get_semaphore``,
  ``get_inference_semaphore``, ``get_baseline_service``, ``Path.exists`` /
  ``Path.read_bytes``, the ``DetectorClient`` image validator - and ``new=`` for
  ``httpx.AsyncClient.post``.  The ``CircuitBreaker`` is NEVER mocked: the two breaker legs
  drive the real state machine through its own ``force_open`` /
  ``_transition_to_half_open`` entry points.
  No import-time global spy, no session-scope clock, no ``time.monotonic`` /
  ``time.perf_counter`` patch and no wall-clock assertion.
* Nothing outside this file is written and production is never bent: every literal
  asserted here is transcribed from the shipped source at the cited line.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from pydantic import SecretStr

from backend.core.config import Settings
from backend.core.exceptions import DetectorUnavailableError
from backend.services import detector_client as M
from backend.services.baseline import BaselineService
from backend.services.circuit_breaker import CircuitBreakerConfig, CircuitState
from backend.services.detector_client import DetectorClient

LOG_NAME = M.logger.name  # "backend.services.detector_client" (get_logger(__name__))
MOD = "backend.services.detector_client"
# backend/services/circuit_breaker.py:73 - the breaker logs on ITS OWN logger, so its
# failure WARNING is filtered by this name rather than by LOG_NAME.
CB_LOG_NAME = CircuitBreakerConfig.__module__  # "backend.services.circuit_breaker"

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/detector_client.py
# =============================================================================

# L280-281: the only supported detector and its shipped model version
DETECTOR_TYPE = "yolo26"
MODEL_VERSION = "yolo26m"
# L285: f"{gw_url.rstrip('/')}/yolo26"
GATEWAY_SUFFIX = "/yolo26"
# L336-345: CircuitBreaker(name=f"detector_{self._detector_type}", config=CircuitBreakerConfig(...))
CIRCUIT_NAME = f"detector_{DETECTOR_TYPE}"
CB_FAILURE_THRESHOLD = 5
CB_RECOVERY_TIMEOUT = 60.0
CB_HALF_OPEN_MAX_CALLS = 3
CB_SUCCESS_THRESHOLD = 2
CB_EXCLUDED_EXCEPTIONS = (ValueError,)
# L357-369: logger.info("DetectorClient initialized", extra={...})
STARTUP_INFO = "DetectorClient initialized"
STARTUP_KEYS = {
    "detector_type",
    "detector_url",
    "free_threading",
    "max_concurrent_inferences",
    "preprocess_workers",
    "max_retries",
    "timeout_seconds",
    "circuit_breaker_failure_threshold",
    "circuit_breaker_recovery_timeout",
}
# _send_detection_request record texts
CONN_RETRY = "Detector connection error, retrying"  # L693
CONN_FINAL = "Detector connection error after all attempts"  # L709
TIMEOUT_RETRY = "Detector timeout, retrying"  # L727
TIMEOUT_FINAL = "Detector timeout after all attempts"  # L742
ASYNC_RETRY_TPL = (  # L756-757 (f-string)
    "Detector asyncio timeout (attempt {attempt}/{retries}), retrying in {delay}s: "
    "request timed out after {timeout}s"
)
ASYNC_FINAL_TPL = "Detector asyncio timeout after {retries} attempts: request timed out after {timeout}s"  # L772-773
SERVER_RETRY = "Detector server error, retrying"  # L792
SERVER_FINAL = "Detector server error after all attempts"  # L807
CLIENT_ERROR = "Detector client error"  # L830
JSON_RETRY_TPL = "Detector JSON/value error (attempt {attempt}/{retries}), retrying in {delay}s: {error}"  # L849-850
JSON_FINAL_TPL = "Detector JSON/value error after {retries} attempts: {error}"  # L866-867
UNEXPECTED_RETRY = "Unexpected detector error, retrying"  # L885
UNEXPECTED_FINAL = "Unexpected detector error after all attempts"  # L900
# detect_objects record texts
CIRCUIT_OPEN_TPL = "Circuit breaker open for {detector}, rejecting detection request"  # L1069
CIRCUIT_TRIPPED_TPL = "Circuit breaker open for {detector}"  # L1407
DETECT_UNEXPECTED = "Unexpected error during object detection"  # L1429
# L713 / L748 / ...: delay = min(2**attempt, 30)
BACKOFF_DELAY = 1
# Values injected by this file (never shipped values)
DETECTOR_URL = "http://detector.internal:8000"
DETECT_URL = f"{DETECTOR_URL}/detect"  # L668
GATEWAY_URL = "http://gateway.internal:9000/detector/"
API_KEY = "probe-api-key-4f2a"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 60.0
HEALTH_TIMEOUT = 5.0
MAX_CONCURRENT = 4
MAX_RETRIES_SETTING = 3
THRESHOLD = 0.55
CLASS_THRESHOLDS = {"person": 0.4}
WARMUP_ENABLED = True
COLD_START_SECONDS = 120.0
FREE_THREADED = True
PREPROCESS_WORKERS = 8
RETRIES = 2  # the request legs: one retry WARNING + one terminal ERROR
EXPLICIT_TIMEOUT = READ_TIMEOUT + CONNECT_TIMEOUT  # L636
CAMERA_ID = "front_door"
IMAGE_PATH = "/export/foscam/front_door/snapshot.jpeg"
IMAGE_NAME = "snapshot.jpeg"
IMAGE_DATA = b"\xff\xd8\xff\xe0fake-image-bytes"
CONN_MSG = "connection refused by the detector socket"
TIMEOUT_MSG = "read timed out on the detector socket"
ASYNC_MSG = "loop-level deadline fired while posting"
OS_MSG = "socket reset on the detector socket"
JSON_MSG = "detections must be a list"
DISK_MSG = "disk read failed on the snapshot"


# =============================================================================
# Observation helpers
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


def _baseline_attrs() -> frozenset[str]:
    """Attribute names that are NOT part of a shipped ``extra=`` payload.

    The union of (a) the fields ``logging.LogRecord.__init__`` always sets and (b) the
    fields this module's ``ContextFilter`` injects, MEASURED (the filter is idempotent,
    so running it over a record it has already seen adds exactly the injected names
    once).  ``message`` is excluded - the formatter sets it.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The ``extra=`` dict the shipped call passed, as the record shows it.

    ``Logger.makeRecord`` copies ``extra`` into the record verbatim, so removing the
    baseline leaves precisely the shipped payload - which is how ``extra=None``, the
    dropped ``extra`` argument and a renamed KEY become visible.
    """
    return {k: v for k, v in record.__dict__.items() if k not in BASELINE_ATTRS}


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped log call.

    ``record.msg`` is the RAW message; shipped f-strings arrive already interpolated, so
    ``record.args`` must stay empty (a moved or dropped argument lands IN ``msg``).
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args: {r.args!r}"


def pin_extra(r: logging.LogRecord, expected: dict[str, Any]) -> None:
    """Pin the complete ``extra=`` surface: exactly these keys, exactly these values."""
    got = shipped_extra(r)
    assert got == expected, f"extra payload mutated: {got!r} != {expected!r}"


def surface(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(r.levelno, r.msg) for r in mine(caplog)]


def one(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
    extra: dict[str, Any],
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, pinned on every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {surface(caplog)!r}"
    )
    r = recs[0]
    pin_record(r, msg=msg, level=level)
    pin_extra(r, extra)
    return r


def pin_retry_pair(
    caplog: pytest.LogCaptureFixture,
    warning: tuple[str, dict[str, Any]],
    error: tuple[str, dict[str, Any], type[BaseException]],
) -> None:
    """Pin the shipped retry pair: exactly one WARNING (the retry) then one ERROR (terminal).

    Both records are pinned on RAW text, level and the COMPLETE ``extra`` surface, and the
    ERROR on the exception ``exc_info=True`` reports.  No other record may appear at either
    level in the window.
    """
    warns, errs = at(caplog, logging.WARNING), at(caplog, logging.ERROR)
    assert len(warns) == 1, f"expected exactly 1 WARNING record, got {surface(caplog)!r}"
    assert len(errs) == 1, f"expected exactly 1 ERROR record, got {surface(caplog)!r}"
    w, e = warns[0], errs[0]
    pin_record(w, msg=warning[0], level=logging.WARNING)
    pin_extra(w, warning[1])
    assert w.exc_info is None, f"a retry warning passes no exc_info: {w.exc_info!r}"
    pin_record(e, msg=error[0], level=logging.ERROR)
    pin_extra(e, error[1])
    assert e.exc_info is not None, "the shipped terminal record passes exc_info=True"
    assert isinstance(e.exc_info[1], error[2]), (
        f"exc_info reports {type(e.exc_info[1]).__name__}, expected {error[2].__name__}"
    )


# =============================================================================
# Construction doubles
# =============================================================================


def settings_double(**overrides: Any) -> MagicMock:
    """A spec'd Settings stand-in carrying the values the shipped ``__init__`` reads."""
    cfg = MagicMock(spec=Settings)
    cfg.use_ai_gateway = False
    cfg.ai_gateway_url = None
    cfg.yolo26_url = DETECTOR_URL
    cfg.yolo26_api_key = SecretStr(API_KEY)
    cfg.yolo26_read_timeout = READ_TIMEOUT
    cfg.detection_confidence_threshold = THRESHOLD
    cfg.detection_class_thresholds = CLASS_THRESHOLDS
    cfg.ai_connect_timeout = CONNECT_TIMEOUT
    cfg.ai_health_timeout = HEALTH_TIMEOUT
    cfg.detector_max_retries = MAX_RETRIES_SETTING
    cfg.ai_max_concurrent_inferences = MAX_CONCURRENT
    cfg.ai_warmup_enabled = WARMUP_ENABLED
    cfg.ai_cold_start_threshold_seconds = COLD_START_SECONDS
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def construct(
    cfg: MagicMock | None = None,
    *,
    free_threaded: bool = FREE_THREADED,
    workers: int = PREPROCESS_WORKERS,
    retries: int | None = None,
    real_http: bool = False,
) -> DetectorClient:
    """Build a real DetectorClient with settings + both HTTP clients patched.

    ``httpx.AsyncClient`` is autospec-patched with a single queued instance double, so the
    two shipped constructions (detection client, health client) share it and no socket is
    ever opened.  ``real_http=True`` keeps the shipped client REAL - needed by the request
    legs, which patch the ``post`` METHOD on the class and so need an actual instance.
    """
    mgrs = [
        patch(f"{MOD}.get_settings", return_value=cfg or settings_double(), autospec=True),
        patch(f"{MOD}._is_free_threaded", return_value=free_threaded, autospec=True),
        patch(f"{MOD}._get_preprocess_worker_count", return_value=workers, autospec=True),
    ]
    if not real_http:
        http = AsyncMock(spec=httpx.AsyncClient)
        mgrs.append(patch(f"{MOD}.httpx.AsyncClient", return_value=http, autospec=True))
    with patches(*mgrs):
        return DetectorClient(max_retries=retries)


def startup_extra(cfg: MagicMock | None = None, **built: Any) -> dict[str, Any]:
    """The shipped startup ``extra`` payload for a client built with these values."""
    cfg = cfg or settings_double()
    return {
        "detector_type": DETECTOR_TYPE,
        "detector_url": cfg.yolo26_url,
        "free_threading": built.get("free_threaded", FREE_THREADED),
        "max_concurrent_inferences": cfg.ai_max_concurrent_inferences,
        "preprocess_workers": built.get("workers", PREPROCESS_WORKERS),
        "max_retries": built.get("max_retries", MAX_RETRIES_SETTING),
        "timeout_seconds": cfg.yolo26_read_timeout,
        "circuit_breaker_failure_threshold": CB_FAILURE_THRESHOLD,
        "circuit_breaker_recovery_timeout": CB_RECOVERY_TIMEOUT,
    }


@contextlib.contextmanager
def patches(*mgrs: Any) -> Iterator[None]:
    """Enter N pre-built ``patch`` context managers (Python has no starred ``with``)."""
    with contextlib.ExitStack() as stack:
        for mgr in mgrs:
            stack.enter_context(mgr)
        yield


# =============================================================================
# __init__ - detector type / model / gateway route  (refs: detector_client.py:280-288)
# =============================================================================


def test_the_shipped_detector_type_and_model_version_are_stored() -> None:
    """N1 - the two model-identity fields (m6 -> None, m7 XX-wrap, m8 upper)."""
    c = construct()

    assert c.detector_type == DETECTOR_TYPE
    assert c._detector_type == DETECTOR_TYPE
    assert c._model_version == MODEL_VERSION, (
        f"model version mutated: {c._model_version!r} != {MODEL_VERSION!r}"
    )


@pytest.mark.parametrize(
    ("gateway_url", "use_gateway", "expected"),
    [
        # use_ai_gateway is True and the configured URL is a str -> the gateway route wins
        (GATEWAY_URL, True, f"{GATEWAY_URL.rstrip('/')}{GATEWAY_SUFFIX}"),
        # the attribute is absent -> getattr's False default keeps the direct URL
        (None, False, DETECTOR_URL),
        # True but the configured value is not a str -> the direct URL
        (SecretStr("secret-not-a-url"), True, DETECTOR_URL),
    ],
    ids=["gateway-on", "gateway-off", "gateway-non-str"],
)
def test_the_gateway_route_is_used_only_for_a_configured_string_url(
    gateway_url: Any, use_gateway: bool, expected: str
) -> None:
    """N2 - the L284 gate, including its ``False`` default (m20 -> None, m26 -> True)."""
    cfg = settings_double(use_ai_gateway=use_gateway, ai_gateway_url=gateway_url)

    assert construct(cfg)._detector_url == expected, (
        f"detector url mutated: {construct(cfg)._detector_url!r} != {expected!r}"
    )


def test_the_gateway_url_loses_only_its_trailing_slashes() -> None:
    """N3 - ``rstrip('/')`` is what joins the gateway base to the detector path (m32)."""
    cfg = settings_double(use_ai_gateway=True, ai_gateway_url="http://gw.internal:9000/det//")

    assert construct(cfg)._detector_url == "http://gw.internal:9000/det/yolo26"


# The L285 strip-set discriminator.  ``m32`` replaces ``rstrip("/")`` with
# ``rstrip("XX/XX")``, whose character SET is ``{"X", "/"}`` - so a base whose trailing
# run contains an uppercase ``X`` is stripped DIFFERENTLY, while every base that ends in
# slashes only is identical under both programs.  N3 above ends in ``//`` and therefore
# cannot see the mutant at all; the legs below put an ``X`` AT the strip boundary (kept by
# the shipped strip-set, removed by the mutant's) and add the no-trailing-slash identity
# leg, where the shipped strip removes nothing while the mutant eats the base's last char.
# Every expected value below is the shipped ``f"{gw_url.rstrip('/')}/yolo26"``.
STRIP_SET_LEGS: tuple[tuple[str, str], ...] = (
    ("http://gw.internal:8000/probeX//", "http://gw.internal:8000/probeX/yolo26"),
    ("http://gw.internal:8000/maxX", "http://gw.internal:8000/maxX/yolo26"),
    ("http://gw.internal:8000/detXXX/", "http://gw.internal:8000/detXXX/yolo26"),
    ("http://gw.internal:8000/detector///", "http://gw.internal:8000/detector/yolo26"),
    ("http://gw:8000", "http://gw:8000/yolo26"),
)


@pytest.mark.parametrize(("gateway_url", "expected"), list(STRIP_SET_LEGS))
def test_the_gateway_join_strips_only_forward_slashes(gateway_url: str, expected: str) -> None:
    """N27 - the L285 strip-set is exactly ``"/"`` (``m32``'s ``XX/XX`` eats ``X`` too)."""
    cfg = settings_double(use_ai_gateway=True, ai_gateway_url=gateway_url)
    c = construct(cfg)

    assert c._detector_url == expected, (
        f"gateway join mutated: {c._detector_url!r} != {expected!r} for base {gateway_url!r}"
    )


@pytest.mark.parametrize(
    ("gateway_url", "expected"),
    [
        # the shipped isinstance guard keeps the DIRECT url for a non-str setting
        (SecretStr(API_KEY), DETECTOR_URL),
        (MagicMock(spec=object), DETECTOR_URL),
    ],
    ids=["secret-str", "not-a-str"],
)
def test_the_gateway_route_requires_a_string_url(gateway_url: Any, expected: str) -> None:
    """N28 - the L284 ``isinstance(gw_url, str)`` conjunct (a second route on m20/m26)."""
    cfg = settings_double(use_ai_gateway=True, ai_gateway_url=gateway_url)

    assert construct(cfg)._detector_url == expected


def test_the_absent_gateway_flag_falls_back_to_the_shipped_false_default() -> None:
    """N25 - L284's ``getattr`` DEFAULT: the attribute ABSENT selects ``False`` (m26).

    ``MagicMock(spec=Settings)`` carries only what ``dir(Settings)`` exposes, and a pydantic
    field is not there - so the flag can be made genuinely ABSENT (the value ``settings_double``
    sets is deleted, and the premise is pinned below: reading the attribute with a sentinel
    default must return the sentinel, or the leg would exercise the PRESENT-False path instead
    of the default).  With the flag absent the shipped default ``False`` makes
    ``False is True`` false and the direct ``settings.yolo26_url`` wins; ``m26``'s default
    ``True`` makes the same read ``True is True`` and routes to the gateway URL.

    ``m20`` (default ``False`` -> ``None``) is NOT reachable here or anywhere else: the default
    is consumed ONLY by ``... is True``, and ``False is True`` == ``None is True`` == ``False``,
    so shipped and that mutant agree on every possible settings object - see the module
    docstring's UNKILLABLE note.
    """
    cfg = settings_double(use_ai_gateway=True, ai_gateway_url=GATEWAY_URL)
    del cfg.use_ai_gateway
    assert getattr(cfg, "use_ai_gateway", "<<absent>>") == "<<absent>>", (
        "premise broken: the gateway flag is not absent from the settings double"
    )

    c = construct(cfg)

    assert c._detector_url == DETECTOR_URL, (
        f"getattr default mutated: {c._detector_url!r} != {DETECTOR_URL!r}"
    )
    assert c._detector_url != f"{GATEWAY_URL.rstrip('/')}{GATEWAY_SUFFIX}"


def test_the_startup_record_url_follows_the_absent_gateway_flag(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N26 - the second route on ``m26``: the banner's ``detector_url`` KEY.

    The gateway decision is the only thing the absent flag feeds, and it reaches the startup
    record through ``self._detector_url`` - so the complete ``extra`` pin below is a second,
    independent observation of the same shipped behaviour.
    """
    cfg = settings_double(use_ai_gateway=True, ai_gateway_url=GATEWAY_URL)
    del cfg.use_ai_gateway
    win(caplog)

    construct(cfg)

    one(caplog, logging.INFO, STARTUP_INFO, startup_extra(cfg))


# =============================================================================
# __init__ - retry / concurrency  (refs: detector_client.py:313-317)
# =============================================================================


@pytest.mark.parametrize("argument", [0, 1, 7])
def test_the_max_retries_argument_overrides_the_setting_and_zero_is_kept(
    argument: int,
) -> None:
    """N4 - the override keeps a falsy 0; the setting only wins when it is None (m59)."""
    cfg = settings_double(detector_max_retries=MAX_RETRIES_SETTING)

    assert construct(cfg, retries=argument)._max_retries == argument, (
        f"max_retries mutated: {construct(cfg, retries=argument)._max_retries!r}"
    )


def test_the_constructor_without_an_argument_uses_the_setting() -> None:
    """N4 control - the ``None`` arm of the L313-315 conditional reads the setting."""
    cfg = settings_double(detector_max_retries=MAX_RETRIES_SETTING)
    c = construct(cfg, retries=None)

    assert c._max_retries == MAX_RETRIES_SETTING
    assert c._max_concurrent == cfg.ai_max_concurrent_inferences


def test_the_inference_concurrency_limit_comes_from_the_setting() -> None:
    """N5 - the NEM-1500 limit is stored, not invented (m61 -> None)."""
    c = construct(settings_double(ai_max_concurrent_inferences=MAX_CONCURRENT))

    assert c._max_concurrent == MAX_CONCURRENT, f"concurrency limit mutated: {c._max_concurrent!r}"


# =============================================================================
# __init__ - the circuit breaker  (refs: detector_client.py:336-345)
# =============================================================================


def test_the_circuit_breaker_is_named_for_the_detector_type() -> None:
    """N6 - the per-detector name and the shipped failure threshold (m94 drops the arg)."""
    c = construct()

    assert c._circuit_breaker.name == CIRCUIT_NAME
    assert c._circuit_breaker.config.failure_threshold == CB_FAILURE_THRESHOLD


def test_the_circuit_breaker_config_is_pinned_and_its_arguments_are_present() -> None:
    """N7 - all five config fields carry the shipped values, so all args were PASSED."""
    cfg = construct()._circuit_breaker.config

    assert cfg.failure_threshold == CB_FAILURE_THRESHOLD, (
        f"failure_threshold mutated/absent: {cfg.failure_threshold!r}"
    )
    assert cfg.recovery_timeout == CB_RECOVERY_TIMEOUT, (
        f"recovery_timeout mutated: {cfg.recovery_timeout!r}"
    )
    assert cfg.half_open_max_calls == CB_HALF_OPEN_MAX_CALLS, (
        f"half_open_max_calls mutated/absent: {cfg.half_open_max_calls!r}"
    )
    assert cfg.success_threshold == CB_SUCCESS_THRESHOLD, (
        f"success_threshold mutated/absent: {cfg.success_threshold!r}"
    )
    assert cfg.excluded_exceptions == CB_EXCLUDED_EXCEPTIONS, (
        f"excluded_exceptions mutated: {cfg.excluded_exceptions!r}"
    )


# The five L338-342 arguments, as the shipped call passes them.
CB_CALL_KWARGS: dict[str, Any] = {
    "failure_threshold": CB_FAILURE_THRESHOLD,
    "recovery_timeout": CB_RECOVERY_TIMEOUT,
    "half_open_max_calls": CB_HALF_OPEN_MAX_CALLS,
    "success_threshold": CB_SUCCESS_THRESHOLD,
    "excluded_exceptions": CB_EXCLUDED_EXCEPTIONS,
}
# The instance that call builds - the real class, so the spy's delegation can be verified.
CB_SHIPPED_CONFIG = CircuitBreakerConfig(**CB_CALL_KWARGS)


def real_config(**kwargs: Any) -> CircuitBreakerConfig:
    """The REAL ``CircuitBreakerConfig`` - the spy's delegation target (no behaviour bend)."""
    return CircuitBreakerConfig(**kwargs)


async def _raise_client_error() -> None:
    """The operation handed to the breaker: the shipped 4xx arm raises exactly this."""
    raise ValueError("Detector client error")


async def _raise_type_error() -> None:
    """The operation handed to the breaker: a type OUTSIDE the excluded tuple."""
    raise TypeError("detector socket reset")


def test_the_constructor_passes_every_circuit_breaker_argument_to_the_config() -> None:
    """N29 - the L338-342 CALL SURFACE: every argument is PRESENT with the shipped value.

    ``m94``/``m96``/``m97`` drop ``failure_threshold=5`` / ``half_open_max_calls=3`` /
    ``success_threshold=2``, and those three are NOT observable on the constructed config:
    ``backend/services/circuit_breaker.py:150-153`` gives the dataclass the defaults
    ``5`` / ``3`` / ``2`` - EQUAL to the shipped explicit values - so the mutant instance is
    attribute-for-attribute equal to shipped and every field ``==`` above (N6/N7) holds under
    them too.  Measured: ``CircuitBreakerConfig(**{drop one of the three}) == shipped`` is
    ``True``.  The ONLY observable difference is at the call site, so this test spies
    ``CircuitBreakerConfig`` on THIS module's binding with ``autospec=True`` +
    ``side_effect=<the real class>`` - the spy DELEGATES, so the shipped ``DetectorClient`` is
    built exactly as it is everywhere else and the breaker below is the real state machine.
    Presence is asserted KEY-BY-KEY (a dropped argument removes its KEY, which a whole-dict
    ``==`` would also show) and each value on equality.

    Second routes: ``m91``/``m92`` (``half_open_max_calls``/``success_threshold`` -> ``None``)
    and ``m101``/``m102`` (``3`` -> ``4``, ``2`` -> ``3``) fail a VALUE assert on the same dict.
    """
    with patch(f"{MOD}.CircuitBreakerConfig", autospec=True, side_effect=real_config) as spy:
        c = construct()

    assert spy.call_count == 1, f"the shipped config construction count mutated: {spy.call_count}"
    assert spy.call_args.args == (), (
        f"the shipped config takes only keyword arguments: {spy.call_args.args!r}"
    )
    passed = spy.call_args.kwargs
    for name, shipped in CB_CALL_KWARGS.items():
        assert name in passed, (
            f"CircuitBreakerConfig argument {name!r} was DROPPED (shipped passes "
            f"{name}={shipped!r} at L338-342): {sorted(passed)!r}"
        )
    assert passed == CB_CALL_KWARGS, (
        f"CircuitBreakerConfig arguments mutated: {passed!r} != {CB_CALL_KWARGS!r}"
    )
    # the delegation is real: the client under the spy carries the shipped config
    assert c._circuit_breaker.config == CB_SHIPPED_CONFIG
    assert c._circuit_breaker.name == CIRCUIT_NAME


def cb_warns(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """The breaker's OWN WARNING-and-up records (it logs on its module's logger).

    ``_record_failure`` (``circuit_breaker.py:534-539``) emits one WARNING per recorded
    failure, so the count is a second, independent reading of whether the client error was
    excluded.  ``win`` opens a window only on THIS module's logger, hence the separate filter.
    """
    return [r for r in caplog.records if r.name == CB_LOG_NAME and r.levelno >= logging.WARNING]


def test_the_client_breaker_excludes_only_the_client_error_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N30 - the L342 ``excluded_exceptions=(ValueError,)`` is BEHAVIOUR, not just a field.

    ``CircuitBreaker.call`` (``circuit_breaker.py:486-491``) re-raises an exception listed in
    ``config.excluded_exceptions`` WITHOUT calling ``_record_failure()``, and records a failure
    for one outside the tuple - so driving the client's own breaker makes the shipped tuple
    observable in a way the N7 field ``==`` never does (a counter and a log line, not just an
    attribute read).

    Scope, stated honestly: NO surviving mutant of this module touches ``excluded_exceptions``,
    so this leg kills nothing in the group - the bank's ``m97`` drops ``success_threshold=2,``
    (L342; the printed "mutated" line of a dropped line is the line BELOW the hole - the
    ``excluded_exceptions`` line at L343 - which is why a splice summary alone mis-attributes
    it) and ``m94``/``m96``/``m97`` are all killed by N29's call-site kwargs pin.  This test is
    the behaviour guard for the shipped tuple itself: had a mutant dropped or ``-> None``'d the
    argument, ``()`` would have recorded the client error (counter 1 + one breaker WARNING) and
    a ``None`` would have raised ``TypeError: isinstance() arg 2 must be a type, a tuple of
    types, or a union`` from that same line (both measured) - the asserts below catch either.

    Exactly one call is driven, so the counter cannot reach the threshold of 5 and no state
    transition is involved; the breaker is the client's REAL one, never mocked.
    """
    c = construct()
    breaker = c._circuit_breaker
    caplog.clear()

    with pytest.raises(ValueError) as raised:
        asyncio.run(breaker.call(_raise_client_error))

    assert str(raised.value) == "Detector client error", (
        f"the excluded exception must propagate unchanged: {str(raised.value)!r}"
    )

    assert breaker.failure_count == 0, (
        f"a client error must not count as a detector failure: {breaker.failure_count}"
    )
    assert breaker.state is CircuitState.CLOSED
    assert breaker._config.excluded_exceptions == CB_EXCLUDED_EXCEPTIONS, (
        f"excluded_exceptions mutated: {breaker._config.excluded_exceptions!r}"
    )
    assert cb_warns(caplog) == [], (
        f"an excluded exception must record no failure: {[r.msg for r in cb_warns(caplog)]!r}"
    )


def test_the_client_breaker_records_a_non_excluded_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N31 (control for N30) - a type OUTSIDE the tuple DOES count as a failure.

    Without this leg, ``failure_count == 0`` would also be satisfied by a breaker that records
    nothing at all.  This pins that the same call surface moves the counter to 1 and emits
    exactly one breaker WARNING, so N30's zeros are the EXCLUSION and not a dead instrument.
    """
    c = construct()
    breaker = c._circuit_breaker
    caplog.clear()

    with pytest.raises(TypeError) as raised:
        asyncio.run(breaker.call(_raise_type_error))

    # the operation's OWN error propagates - not the TypeError a broken tuple would raise
    # out of `isinstance(e, self._config.excluded_exceptions)`
    assert str(raised.value) == "detector socket reset", (
        f"unexpected propagation: {str(raised.value)!r}"
    )
    assert breaker.failure_count == 1, (
        f"a non-excluded exception must record exactly one failure: {breaker.failure_count}"
    )
    assert breaker.state is CircuitState.CLOSED, "one failure is below the threshold of 5"
    assert breaker._config.failure_threshold == CB_FAILURE_THRESHOLD
    assert len(cb_warns(caplog)) == 1, (
        f"the shipped failure arm logs one WARNING: {[r.msg for r in cb_warns(caplog)]!r}"
    )


# =============================================================================
# __init__ - the warmup flags  (refs: detector_client.py:347-350)
# =============================================================================


def test_the_warmup_flags_are_read_from_the_settings_verbatim() -> None:
    """N8 - the NEM-1670 flags (m104/m105 flip ``_is_warming`` to None / True)."""
    cfg = settings_double(
        ai_warmup_enabled=WARMUP_ENABLED, ai_cold_start_threshold_seconds=COLD_START_SECONDS
    )
    c = construct(cfg)

    assert c._last_inference_time is None
    assert c._is_warming is False, f"_is_warming mutated: {c._is_warming!r}"
    assert c._warmup_enabled is WARMUP_ENABLED
    assert c._cold_start_threshold == COLD_START_SECONDS


# =============================================================================
# __init__ - the startup INFO log  (refs: detector_client.py:352-370)
# =============================================================================


def test_the_startup_banner_is_an_info_record_with_the_shipped_key_set(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N9 - the message text/level and the COMPLETE startup KEY set (m110-m135)."""
    cfg = settings_double()
    win(caplog)

    construct(cfg, retries=MAX_RETRIES_SETTING)

    rec = one(caplog, logging.INFO, STARTUP_INFO, startup_extra(cfg))
    assert sorted(shipped_extra(rec)) == sorted(STARTUP_KEYS), (
        f"startup KEY set mutated: {sorted(shipped_extra(rec))!r}"
    )
    assert rec.exc_info is None, f"the constructor passes no exc_info: {rec.exc_info!r}"


def test_the_startup_extra_carries_the_measured_values_and_the_pinned_constants(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N10 - the helper-derived values and the two pinned breaker constants.

    ``m108``/``m109`` (the L354/L355 helper results -> ``None``), ``m133`` (``5`` ->
    ``6``), ``m136`` (``60.0`` -> ``61.0``) plus a second route onto the KEY renames that
    move a value off its shipped name.
    """
    win(caplog)

    construct(free_threaded=True, workers=8, retries=MAX_RETRIES_SETTING)

    one(caplog, logging.INFO, STARTUP_INFO, startup_extra(free_threaded=True, workers=8))


def test_the_startup_record_is_the_only_info_line_the_constructor_emits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N11 (control) - the banner is one INFO record and nothing else is logged."""
    win(caplog)

    construct()

    assert surface(caplog) == [(logging.INFO, STARTUP_INFO)], (
        f"constructor log surface mutated: {surface(caplog)!r}"
    )


def test_the_startup_values_follow_the_settings_not_the_double_defaults(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N12 - a SECOND value set proves the payload is read, not hard-coded."""
    cfg = settings_double(
        yolo26_url="http://yolo26-alt:9100",
        ai_max_concurrent_inferences=11,
        yolo26_read_timeout=17.5,
    )
    win(caplog)

    construct(cfg, retries=2, free_threaded=False, workers=2)

    one(
        caplog,
        logging.INFO,
        STARTUP_INFO,
        {
            "detector_type": DETECTOR_TYPE,
            "detector_url": "http://yolo26-alt:9100",
            "free_threading": False,
            "max_concurrent_inferences": 11,
            "preprocess_workers": 2,
            "max_retries": 2,
            "timeout_seconds": 17.5,
            "circuit_breaker_failure_threshold": CB_FAILURE_THRESHOLD,
            "circuit_breaker_recovery_timeout": CB_RECOVERY_TIMEOUT,
        },
    )


# =============================================================================
# The twin sites of m117/m118/m127/m128  (refs: detector_client.py:692-904, 1068-1438)
# =============================================================================


def request_client(
    post: AsyncMock,
    *,
    retries: int = RETRIES,
    cfg: MagicMock | None = None,
) -> DetectorClient:
    """A real client whose detection POST is the (already spec'd) ``post`` double.

    ``new=`` is required here because ``patch`` refuses ``autospec`` and ``new`` together;
    the replacement is a ``AsyncMock(spec=httpx.AsyncClient.post)``, so the shipped call
    signature is still enforced.  The patcher is registered so the autouse fixture below
    always undoes it.
    """
    c = construct(cfg, retries=retries, real_http=True)
    patcher = patch.object(httpx.AsyncClient, "post", new=post)
    patcher.start()
    request_client.patchers.append(patcher)
    request_client.clients.append(c)
    return c


request_client.patchers: list[Any] = []
request_client.clients: list[DetectorClient] = []


@pytest.fixture(autouse=True)
def _stop_request_patchers() -> Iterator[None]:
    """Undo every ``post`` patcher this module started, after each test."""
    yield
    while request_client.patchers:
        request_client.patchers.pop().stop()
    request_client.clients.clear()


def response_double(
    *, status_code: int = 200, payload: Any | None = None, method: str = "POST"
) -> httpx.Response:
    """A REAL ``httpx.Response``, so the shipped ``raise_for_status`` stays in play."""
    return httpx.Response(status_code, json=payload, request=httpx.Request(method, DETECT_URL))


def retry_extra(**overrides: Any) -> dict[str, Any]:
    """The shipped retry-WARNING payload core (L694-703, L740-748, L758-766, L774-783,
    L854-863, L886-895): attempt 1 of ``RETRIES``, backoff ``min(2**0, 30) == 1``."""
    payload: dict[str, Any] = {
        "detector_type": DETECTOR_TYPE,
        "camera_id": CAMERA_ID,
        "file_path": IMAGE_PATH,
        "attempt": 1,
        "max_retries": RETRIES,
        "retry_delay": BACKOFF_DELAY,
    }
    payload.update(overrides)
    return payload


def final_extra(**overrides: Any) -> dict[str, Any]:
    """The shipped terminal-ERROR payload core (L708-716, L739-747, L772-780, L806-815,
    L866-876, L898-907): ``attempts`` replaces ``attempt`` / ``retry_delay``."""
    payload: dict[str, Any] = {
        "detector_type": DETECTOR_TYPE,
        "camera_id": CAMERA_ID,
        "file_path": IMAGE_PATH,
        "attempts": RETRIES,
    }
    payload.update(overrides)
    return payload


async def send(c: DetectorClient) -> dict[str, Any]:
    """Call the shipped request path with the backoff sleep autospec-patched away.

    ``_get_semaphore`` is also pinned to a fresh ``asyncio.Semaphore`` so the class-level
    semaphore the shipped L218-221 RECREATES when the configured limit changed cannot
    contribute its DEBUG banner to a capture window (that banner depends on other tests'
    settings, so it is never assertable).
    """
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    with (
        patch("asyncio.sleep", autospec=True) as nap,
        patch.object(DetectorClient, "_get_semaphore", return_value=sem, autospec=True),
    ):
        try:
            return await c._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)
        finally:
            if nap.call_args_list:
                assert nap.call_args_list == [call(BACKOFF_DELAY)], (
                    f"the shipped backoff mutated: {nap.call_args_list!r}"
                )


@pytest.mark.asyncio
async def test_the_happy_path_posts_the_multipart_body_and_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N13 (control) - the happy POST shape and a completely silent success."""
    post = AsyncMock(spec=httpx.AsyncClient.post)
    post.return_value = response_double(payload={"detections": [], "inference_time_ms": 5.0})
    c = request_client(post)
    win(caplog)

    assert await send(c) == {"detections": [], "inference_time_ms": 5.0}

    assert post.call_args.args == (DETECT_URL,), f"request URL mutated: {post.call_args.args!r}"
    assert post.call_args.kwargs["files"] == {"file": (IMAGE_NAME, IMAGE_DATA, "image/jpeg")}
    assert post.call_args.kwargs["headers"]["X-API-Key"] == API_KEY
    assert post.await_count == 1, f"the happy path retried: {post.await_count} posts"
    assert surface(caplog) == [], f"a success emitted records: {surface(caplog)!r}"


@pytest.mark.asyncio
async def test_the_connection_arm_warns_then_fails_with_the_pinned_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N14 - ConnectError: the retry WARNING (L692-712) + terminal ERROR (L708-717)."""
    boom = httpx.ConnectError(CONN_MSG)
    post = AsyncMock(spec=httpx.AsyncClient.post, side_effect=boom)
    c = request_client(post)
    win(caplog)

    with pytest.raises(DetectorUnavailableError, match="Detection failed after 2 attempts"):
        await send(c)

    assert post.await_count == RETRIES, f"retry count mutated: {post.await_count}"
    pin_retry_pair(
        caplog,
        (CONN_RETRY, retry_extra(error=CONN_MSG)),
        (CONN_FINAL, final_extra(error=CONN_MSG), httpx.ConnectError),
    )


@pytest.mark.asyncio
async def test_the_timeout_arm_warns_then_fails_with_the_pinned_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N15 - TimeoutException: the retry WARNING (L726-735) + terminal ERROR (L741-750)."""
    boom = httpx.TimeoutException(TIMEOUT_MSG)
    post = AsyncMock(spec=httpx.AsyncClient.post, side_effect=boom)
    c = request_client(post)
    win(caplog)

    with pytest.raises(DetectorUnavailableError):
        await send(c)

    pin_retry_pair(
        caplog,
        (TIMEOUT_RETRY, retry_extra(error=TIMEOUT_MSG)),
        (TIMEOUT_FINAL, final_extra(error=TIMEOUT_MSG), httpx.TimeoutException),
    )


@pytest.mark.asyncio
async def test_the_asyncio_timeout_arm_warns_then_fails_with_the_pinned_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N16 - the NEM-1465 arm (L752-781): the only f-string texts AND the only payload
    that carries ``explicit_timeout`` instead of ``error``.

    A builtin ``TimeoutError`` raised by the POST body escapes the shipped
    ``asyncio.timeout()`` unchanged, so it lands on ``except TimeoutError``.
    """
    boom = TimeoutError(ASYNC_MSG)
    post = AsyncMock(spec=httpx.AsyncClient.post, side_effect=boom)
    c = request_client(post)
    win(caplog)

    with pytest.raises(DetectorUnavailableError):
        await send(c)

    pin_retry_pair(
        caplog,
        (
            ASYNC_RETRY_TPL.format(
                attempt=1, retries=RETRIES, delay=BACKOFF_DELAY, timeout=EXPLICIT_TIMEOUT
            ),
            retry_extra(explicit_timeout=EXPLICIT_TIMEOUT),
        ),
        (
            ASYNC_FINAL_TPL.format(retries=RETRIES, timeout=EXPLICIT_TIMEOUT),
            final_extra(explicit_timeout=EXPLICIT_TIMEOUT),
            TimeoutError,
        ),
    )


@pytest.mark.asyncio
async def test_the_server_error_arm_warns_then_fails_with_the_pinned_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N17 - HTTP 503: the retry WARNING (L791-804) + terminal ERROR (L806-820)."""
    post = AsyncMock(spec=httpx.AsyncClient.post)
    post.return_value = response_double(status_code=503)
    c = request_client(post)
    win(caplog)

    with pytest.raises(DetectorUnavailableError):
        await send(c)

    pin_retry_pair(
        caplog,
        (SERVER_RETRY, retry_extra(status_code=503)),
        (SERVER_FINAL, final_extra(status_code=503), httpx.HTTPStatusError),
    )


@pytest.mark.asyncio
async def test_the_unexpected_error_arm_warns_then_fails_with_the_pinned_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N18 - OSError: the retry WARNING (L885-897) + terminal ERROR (L900-910).

    ``RuntimeError`` shares this arm, so this leg is also the second route onto the L887
    and L891 sites.
    """
    boom = OSError(OS_MSG)
    post = AsyncMock(spec=httpx.AsyncClient.post, side_effect=boom)
    c = request_client(post)
    win(caplog)

    with pytest.raises(DetectorUnavailableError):
        await send(c)

    pin_retry_pair(
        caplog,
        (UNEXPECTED_RETRY, retry_extra(error=OS_MSG)),
        (UNEXPECTED_FINAL, final_extra(error=OS_MSG), OSError),
    )


@pytest.mark.asyncio
async def test_the_4xx_leg_raises_valueerror_with_the_client_error_record(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N19 - HTTP 400: no retry, ONE error record (L829-841) and a ``ValueError``."""
    post = AsyncMock(spec=httpx.AsyncClient.post)
    post.return_value = response_double(status_code=400, payload={"detail": "bad image"})
    c = request_client(post)
    win(caplog)

    with pytest.raises(ValueError, match="Detector client error 400: bad image"):
        await send(c)

    assert post.await_count == 1, f"a 4xx must not be retried: {post.await_count} posts"
    rec = one(
        caplog,
        logging.ERROR,
        CLIENT_ERROR,
        {
            "detector_type": DETECTOR_TYPE,
            "camera_id": CAMERA_ID,
            "file_path": IMAGE_PATH,
            "status_code": 400,
            "error_detail": "bad image",
        },
    )
    assert rec.exc_info is None, f"the 4xx record passes no exc_info: {rec.exc_info!r}"


@pytest.mark.asyncio
async def test_the_json_error_arm_warns_then_fails_with_the_pinned_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N20 - a ``ValueError`` from the response body: retry WARNING (L849-864) + terminal
    ERROR (L866-880), both carrying the ``sanitize_error``-interpolated f-string text."""
    boom = ValueError(JSON_MSG)
    post = AsyncMock(spec=httpx.AsyncClient.post, side_effect=boom)
    c = request_client(post)
    win(caplog)

    with pytest.raises(DetectorUnavailableError):
        await send(c)

    pin_retry_pair(
        caplog,
        (
            JSON_RETRY_TPL.format(attempt=1, retries=RETRIES, delay=BACKOFF_DELAY, error=JSON_MSG),
            retry_extra(),
        ),
        (JSON_FINAL_TPL.format(retries=RETRIES, error=JSON_MSG), final_extra(), ValueError),
    )


# =============================================================================
# The ``detect_objects`` sites  (refs: detector_client.py:1068-1080, 1406-1417, 1426-1438)
# =============================================================================


def session_double() -> AsyncMock:
    """A DB-session stand-in: async ``get``/``commit``/``flush``, sync ``add``."""
    session = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock(return_value=None)  # camera absent -> no last_seen_at update
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


def detect_patches(*extra: Any, read: Any = None) -> Any:
    """The stand-ins every ``detect_objects`` leg needs, plus any leg-specific ones.

    ``get_inference_semaphore`` (L1114) and ``get_baseline_service`` (L1352) are the two
    module bindings the shipped body calls.  The baseline double is spec'd from the real
    ``BaselineService`` so its ``update_baseline`` is the AsyncMock the spec produces (the
    shipped L1360 awaits it).  ``get_inference_semaphore`` hands back a fresh semaphore so
    the shipped ``async with`` is a no-op that cannot serialise against another window.
    ``read`` drives the shipped L1084 frame read (autospec cannot spec a mock, so a leg
    must NOT stack a second patcher on the same attribute): an exception makes that read
    fail, a callable REPLACES its return value - and the read sits exactly between the two
    shipped breaker checks (the ``allow_call`` gate at L1067 and ``call`` at L1127), so a
    callable is how a leg lands a state change in that window.
    """
    read_mgr = (
        patch("pathlib.Path.read_bytes", side_effect=read, autospec=True)
        if read is not None
        else patch("pathlib.Path.read_bytes", return_value=IMAGE_DATA, autospec=True)
    )
    return patches(
        patch("pathlib.Path.exists", return_value=True, autospec=True),
        read_mgr,
        patch.object(
            DetectorClient,
            "_validate_image_for_detection_async",
            return_value=True,
            autospec=True,
        ),
        patch(f"{MOD}.get_inference_semaphore", return_value=asyncio.Semaphore(16), autospec=True),
        patch(
            f"{MOD}.get_baseline_service",
            return_value=MagicMock(spec=BaselineService),
            autospec=True,
        ),
        *extra,
    )


@pytest.mark.asyncio
async def test_detect_objects_rejects_the_request_while_the_circuit_is_open(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N21 - the circuit-open gate (L1068-1080): the site at L1072 (m117/m118).

    ``force_open`` is the shipped maintenance entry point; the recovery timeout is 60 s, so
    ``allow_call`` (``circuit_breaker.py:426-436``) keeps rejecting and the shipped gate
    logs + raises without touching the detector.
    """
    post = AsyncMock(spec=httpx.AsyncClient.post)
    c = request_client(post)
    session = session_double()
    win(caplog)

    with detect_patches():
        c._circuit_breaker.force_open()
        with pytest.raises(DetectorUnavailableError, match="circuit breaker open"):
            await c.detect_objects(IMAGE_PATH, CAMERA_ID, session)

    assert post.await_count == 0, f"an open circuit still called the detector: {post.await_count}"
    assert c._circuit_breaker.state is CircuitState.OPEN
    one(
        caplog,
        logging.WARNING,
        CIRCUIT_OPEN_TPL.format(detector=DETECTOR_TYPE),
        {
            "detector_type": DETECTOR_TYPE,
            "camera_id": CAMERA_ID,
            "file_path": IMAGE_PATH,
            "circuit_state": "open",
        },
    )


@pytest.mark.asyncio
async def test_detect_objects_survives_a_tripped_breaker_inside_the_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N22 - the ``CircuitBreakerError`` arm (L1406-1419): the site at L1409 (m117/m118).

    The shipped ``allow_call`` gate (L1067) PASSES (CLOSED), the frame read happens, and by
    the time the shipped ``call`` runs at L1127 the half-open trial budget has been spent by
    concurrent callers - exactly the race the shipped comment at L1064-1066 describes - so
    ``call`` rejects with ``CircuitBreakerError`` (``circuit_breaker.py:474-479``) and this
    arm logs and re-raises ``from e``.  The budget is consumed through the breaker's OWN
    state machine (``_transition_to_half_open``, the shipped entry point used by
    ``allow_call``), from inside the frame read - the only window between the two shipped
    checks.  Nothing in ``detector_client.py`` is stubbed to get here.
    """
    post = AsyncMock(spec=httpx.AsyncClient.post)
    c = request_client(post, retries=1)
    breaker = c._circuit_breaker
    session = session_double()
    win(caplog)

    def spend_the_trial_budget(*_a: Any, **_k: Any) -> bytes:
        breaker._transition_to_half_open()  # the shipped OPEN -> HALF_OPEN entry point
        breaker._half_open_calls = CB_HALF_OPEN_MAX_CALLS  # concurrent trials in flight
        return IMAGE_DATA

    with detect_patches(read=spend_the_trial_budget):
        assert breaker.state is CircuitState.CLOSED
        with pytest.raises(DetectorUnavailableError) as raised:
            await c.detect_objects(IMAGE_PATH, CAMERA_ID, session)

    assert breaker.state is CircuitState.HALF_OPEN
    boom = raised.value.__cause__
    assert isinstance(boom, M.CircuitBreakerError), f"cause is {type(boom).__name__}"
    assert post.await_count == 0, f"a rejected breaker still posted: {post.await_count}"
    recs = at(caplog, logging.WARNING)
    assert len(recs) == 1, f"expected one WARNING record, got {surface(caplog)!r}"
    pin_record(
        recs[0], msg=CIRCUIT_TRIPPED_TPL.format(detector=DETECTOR_TYPE), level=logging.WARNING
    )
    got = shipped_extra(recs[0])
    duration = got.pop("duration_ms", "<<missing>>")
    assert isinstance(duration, int), f"the shipped arm stamps duration_ms: {duration!r}"
    assert got == {
        "detector_type": DETECTOR_TYPE,
        "camera_id": CAMERA_ID,
        "file_path": IMAGE_PATH,
        "circuit_state": "half_open",
        "error": str(boom),
    }, f"extra payload mutated: {got!r}"


@pytest.mark.asyncio
async def test_detect_objects_reports_an_unexpected_read_failure_as_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N23 - the ``OSError`` arm of ``detect_objects`` (L1426-1441): site L1433."""
    post = AsyncMock(spec=httpx.AsyncClient.post)
    c = request_client(post)
    session = session_double()
    win(caplog)

    with detect_patches(read=OSError(DISK_MSG)):
        with pytest.raises(
            DetectorUnavailableError, match="Unexpected error during object detection"
        ):
            await c.detect_objects(IMAGE_PATH, CAMERA_ID, session)

    recs = at(caplog, logging.ERROR)
    assert len(recs) == 1, f"expected one ERROR record, got {surface(caplog)!r}"
    pin_record(recs[0], msg=DETECT_UNEXPECTED, level=logging.ERROR)
    got = shipped_extra(recs[0])
    duration = got.pop("duration_ms", "<<missing>>")
    assert isinstance(duration, int), f"the shipped arm stamps duration_ms: {duration!r}"
    assert got == {
        "detector_type": DETECTOR_TYPE,
        "camera_id": CAMERA_ID,
        "error": DISK_MSG,
    }, f"extra payload mutated: {got!r}"
    assert recs[0].exc_info is not None, "the shipped arm passes exc_info=True"
    assert isinstance(recs[0].exc_info[1], OSError)


@pytest.mark.asyncio
async def test_detect_objects_stores_the_detections_from_the_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N24 (control) - the success path stores one detection and warns/errors nothing."""
    post = AsyncMock(spec=httpx.AsyncClient.post)
    post.return_value = response_double(
        payload={
            "detections": [{"class": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}],
            "inference_time_ms": 12.0,
            "image_width": 1920,
            "image_height": 1080,
        }
    )
    c = request_client(post)
    session = session_double()
    win(caplog)

    with detect_patches():
        detections = await c.detect_objects(IMAGE_PATH, CAMERA_ID, session)

    assert len(detections) == 1
    assert detections[0].camera_id == CAMERA_ID
    assert session.add.call_count == 1
    assert [r.levelno for r in mine(caplog) if r.levelno >= logging.WARNING] == [], (
        f"a success warned/errored: {surface(caplog)!r}"
    )
