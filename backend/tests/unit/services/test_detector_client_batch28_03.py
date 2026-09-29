"""S3 batch-28 lane L2 - ``detector_client`` group dc03 kill battery (45 keys).

Module: ``backend/services/detector_client.py`` (md5 ``294c938abe9e37cd0f979f9357982753``
- the manifest-proven source).  Admitted manifest: ``/tmp/wp-pw/detector_client/``
``manifest.json`` group ``dc03-close-and-health-check`` (45 KILLABLE / 0 EQUIVALENT),
``manifest_groups/dc03-close-and-health-check.keys`` (= ``group_02.keys``) and
``survivors.json`` for the exact per-key diffs.

Production refs (current source):
  * ``DetectorClient.close`` L381-391 - the two ``aclose()`` awaits and the DEBUG record.
  * ``DetectorClient.health_check`` L415-451 - the ``GET {url}/health`` request, the
    ``raise_for_status()`` call, ``return True`` and the three handler arms.

Test -> mutant-key map
======================
``close()`` (9 keys)
  C1 ``test_close_awaits_each_persistent_client_once_then_logs_the_debug``
     ``m1`` (L388 message -> ``None``), ``m2`` (L390 ``extra`` -> ``None``),
     ``m4`` (L390 ``extra`` argument dropped) - the DEBUG call's own surface
  C2 ``test_close_debug_text_and_the_detector_type_key_are_pinned_verbatim``
     ``m5``/``m6``/``m7`` (L389 message XX-wrap / lower / upper),
     ``m8``/``m9`` (L390 KEY ``detector_type`` XX-wrap / upper)

``health_check()`` - the request (1 key)
  H1 ``test_health_check_gets_the_health_url_with_the_auth_headers``
     ``m2`` (L423 request URL -> ``None``) - SOLE route
  H2 ``test_health_check_returns_true_once_the_status_check_passes``  (control)

``health_check()`` - the ``ConnectError``/``TimeoutException`` arm (12 keys)
  H3 ``test_the_unreachable_warning_is_the_shipped_text_with_the_error_key``
     ``m7`` (L430 message -> ``None``), ``m8`` (L430 ``extra`` -> ``None``),
     ``m11`` (L432 ``extra`` argument dropped), ``m13``/``m14``/``m15`` (L431 message
     XX-wrap / lower / upper), ``m16``/``m17`` (L432 KEY ``error`` XX-wrap / upper)
  H4 ``test_the_unreachable_warning_attaches_the_live_traceback``
     ``m9`` (L430 ``exc_info`` -> ``None``), ``m12`` (L433 ``exc_info`` dropped),
     ``m19`` (L433 ``exc_info=True`` -> ``False``)
  H5 ``test_the_unreachable_error_text_is_the_exception_message``
     ``m18`` (L432 ``str(e)`` -> ``str(None)``) - SOLE route

``health_check()`` - the ``HTTPStatusError`` arm (13 keys)
  H6 ``test_the_error_status_warning_is_the_shipped_text_with_the_error_key``
     ``m21`` (L437 message -> ``None``), ``m22`` (L437 ``extra`` -> ``None``),
     ``m25`` (L439 ``extra`` dropped), ``m27``/``m28``/``m29`` (L438 message XX-wrap /
     lower / upper), ``m30``/``m31`` (L439 KEY ``error`` renames); second route ``m32``
  H7 ``test_the_error_status_error_text_is_the_status_exception_message``
     ``m32`` (L439 ``str(e)`` -> ``str(None)``); second route to ``m18``
  H8 ``test_the_error_status_warning_attaches_the_live_traceback``
     ``m23`` (L437 ``exc_info`` -> ``None``), ``m26`` (L440 dropped),
     ``m33`` (L440 ``True`` -> ``False``)
  H9 ``test_the_status_arm_never_emits_the_other_two_warning_texts``  (control)

``health_check()`` - the ``OSError``/``RuntimeError``/``ValueError`` arm (13 keys)
  H10 ``test_the_unexpected_failure_is_an_error_record_with_the_error_key``
      ``m35`` (L446 message -> ``None``), ``m36`` (L446 ``extra`` -> ``None``),
      ``m39`` (L448 ``extra`` dropped), ``m41``/``m42``/``m43`` (L447 message XX-wrap /
      lower / upper), ``m44``/``m45`` (L448 KEY ``error`` renames); second route ``m46``
  H11 ``test_the_unexpected_failure_record_attaches_the_live_traceback``
      ``m37`` (L446 ``exc_info`` -> ``None``), ``m40`` (L449 dropped),
      ``m47`` (L449 ``True`` -> ``False``)
  H12 ``test_the_unexpected_failure_text_is_the_sanitized_error``
      ``m46`` (L448 ``sanitize_error(e)`` -> ``sanitize_error(None)``) - SOLE route
  H13 ``test_the_runtime_failure_arm_uses_the_same_surface``  (second route m35-m47)
  H14 ``test_the_value_failure_arm_uses_the_same_surface``  (third route m35-m47)

Discipline
----------
* Log assertions open a capture window per leg (``caplog.set_level(DEBUG, logger=...)``
  plus ``clear()``, filtered to this module's logger name) and read the RAW
  ``record.msg``, ``record.args``, ``record.levelno`` and ``record.exc_info``; the
  ``extra=`` payload is recovered as "record attributes beyond the ``LogRecord`` core
  plus this module's ``ContextFilter`` contributions" (measured, below), which is how
  ``extra=None``, a dropped ``extra`` and a renamed KEY all become visible.
* Every mock of a real attribute is ``autospec=True`` (WP4.2): the HTTP surface is
  patched at ``backend.services.detector_client.httpx.AsyncClient`` (the shipped class,
  imported at detector_client.py:64) with ``autospec=True``; the control legs' per-client
  doubles come from ``create_autospec(httpx.AsyncClient, instance=True)`` and the real
  ``httpx.Response`` objects carry the shipped ``raise_for_status``.  Settings are patched
  at ``backend.services.detector_client.get_settings`` with ``autospec=True``.
* No import-time global spy, no session-scope clock, no ``time.monotonic`` /
  ``time.perf_counter`` patch, no wall-clock assertion.  Nothing outside this file is
  written and production is never bent: every literal asserted here is transcribed from
  the shipped source at the cited line.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, create_autospec, patch

import httpx
import pytest
from pydantic import SecretStr

from backend.services import detector_client as M
from backend.services.detector_client import DetectorClient

LOG_NAME = M.logger.name  # "backend.services.detector_client" (get_logger(__name__))
MOD = "backend.services.detector_client"

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/detector_client.py
# =============================================================================

# L388-391: logger.debug("DetectorClient HTTP connections closed", extra={"detector_type": ...})
CLOSE_DEBUG = "DetectorClient HTTP connections closed"
# L423: f"{self._detector_url}/health"
HEALTH_PATH = "/health"
# L430-433: logger.warning("Detector health check failed", extra={"error": str(e)}, exc_info=True)
UNREACHABLE_WARNING = "Detector health check failed"
# L437-440: logger.warning("Detector health check returned error status", ..., exc_info=True)
STATUS_WARNING = "Detector health check returned error status"
# L446-449: logger.error("Unexpected error during detector health check",
#                       extra={"error": sanitize_error(e)}, exc_info=True)
UNEXPECTED_ERROR = "Unexpected error during detector health check"
# L360 / L390 / L432 / L439 / L448: the ``extra`` KEY names
KEY_DETECTOR_TYPE = "detector_type"
KEY_ERROR = "error"
# L280: the only supported detector type
DETECTOR_TYPE = "yolo26"
# Values injected by this file (never shipped values)
DETECTOR_URL = "http://detector.internal:8000"
API_KEY = "probe-api-key-4f2a"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
CONNECT_MSG = "connection refused by detector host"
STATUS_MSG = "Server error 'HTTP 503 UNAVAILABLE' for url 'http://detector.internal:8000/health'"
OSERROR_MSG = "/export/foscam/front_door/snapshot.jpeg: socket reset"
OSERROR_SANITIZED = ".../snapshot.jpeg: socket reset"
STATUS_ERROR = "HTTP 503 UNAVAILABLE"
RUNTIME_MSG = "client is closed"
VALUE_MSG = "response body missing detections key"


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

    Every claimed site passes a constant message, so ``record.msg`` is the RAW text and
    ``record.args`` must stay empty (a moved or dropped message argument lands IN
    ``msg``; a ``None`` message raises ``TypeError`` inside ``logging``).
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for a constant message: {r.args!r}"


def pin_extra(r: logging.LogRecord, expected: dict[str, Any]) -> None:
    """Pin the complete ``extra=`` surface: exactly these keys, exactly these values."""
    got = shipped_extra(r)
    assert got == expected, f"extra payload mutated: {got!r} != {expected!r}"


def pin_exc_of(r: logging.LogRecord, exc: BaseException) -> None:
    """``exc_info=True`` inside a handler reports THAT live exception."""
    assert r.exc_info is not None, f"exc_info missing: {r.exc_info!r}"
    assert r.exc_info[1] is exc, f"exc_info reports the wrong exception: {r.exc_info[1]!r}"


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
        f"got {[(r.levelno, r.msg) for r in recs]!r}"
    )
    r = recs[0]
    pin_record(r, msg=msg, level=level)
    pin_extra(r, extra)
    return r


# =============================================================================
# Construction / request doubles
# =============================================================================


def settings_double() -> MagicMock:
    """A realistic Settings stand-in (the shipped body reads exactly these)."""
    cfg = MagicMock()
    cfg.use_ai_gateway = False
    cfg.ai_gateway_url = None
    cfg.yolo26_url = DETECTOR_URL
    cfg.yolo26_api_key = SecretStr(API_KEY)
    cfg.yolo26_read_timeout = 60.0
    cfg.detection_confidence_threshold = 0.5
    cfg.detection_class_thresholds = {}
    cfg.ai_connect_timeout = 10.0
    cfg.ai_health_timeout = 5.0
    cfg.detector_max_retries = 3
    cfg.ai_max_concurrent_inferences = 4
    cfg.ai_warmup_enabled = True
    cfg.ai_cold_start_threshold_seconds = 120.0
    return cfg


def settings_patch(cfg: MagicMock | None = None) -> Any:
    """An active-patch context manager for the module's ``get_settings`` binding."""
    return patch(f"{MOD}.get_settings", return_value=cfg or settings_double(), autospec=True)


def client_double() -> Any:
    """An autospec'd stand-in for one ``httpx.AsyncClient`` instance."""
    return create_autospec(httpx.AsyncClient, instance=True)


def response_double(*, status_code: int = 200, payload: Any | None = None) -> httpx.Response:
    """A REAL ``httpx.Response`` so the shipped ``raise_for_status`` stays in play."""
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", f"{DETECTOR_URL}{HEALTH_PATH}"),
    )


@pytest.fixture
def patched_clients() -> Iterator[tuple[DetectorClient, AsyncMock, AsyncMock]]:
    """A real DetectorClient with the shipped class autospec-patched, twice.

    ``httpx.AsyncClient`` is autospec-patched with two queued instance doubles, so the
    detection client and the health client stay distinguishable objects while every call
    still goes through the shipped class's spec.
    """
    detection, health = client_double(), client_double()
    with settings_patch(), patch(f"{MOD}.httpx.AsyncClient", autospec=True) as AC:
        AC.side_effect = [detection, health]
        yield DetectorClient(max_retries=1), detection, health


@pytest.fixture
def health_only() -> Iterator[tuple[DetectorClient, AsyncMock]]:
    """A real DetectorClient with autospec'd per-client doubles (used by the controls)."""
    detection, health = client_double(), client_double()
    with settings_patch():
        c = DetectorClient(max_retries=1)
    c._http_client = detection
    c._health_http_client = health
    yield c, health


# =============================================================================
# close()  (production refs: detector_client.py:381-391)
# =============================================================================


@pytest.mark.asyncio
async def test_close_awaits_each_persistent_client_once_then_logs_the_debug(
    patched_clients: tuple[DetectorClient, AsyncMock, AsyncMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """C1 - both shipped ``aclose()`` awaits, then exactly one DEBUG record (m1, m2, m4)."""
    c, detection, health = patched_clients
    order: list[str] = []
    detection.aclose.side_effect = lambda: order.append("detection")
    health.aclose.side_effect = lambda: order.append("health")
    win(caplog)

    assert await c.close() is None

    assert order == ["detection", "health"], f"aclose order/count mutated: {order!r}"
    assert detection.aclose.await_count == 1, f"detection aclose: {detection.aclose.await_count}"
    assert health.aclose.await_count == 1, f"health aclose: {health.aclose.await_count}"
    rec = one(caplog, logging.DEBUG, CLOSE_DEBUG, {KEY_DETECTOR_TYPE: DETECTOR_TYPE})
    assert rec.exc_info is None, f"close() passes no exc_info: {rec.exc_info!r}"


@pytest.mark.asyncio
async def test_close_debug_text_and_the_detector_type_key_are_pinned_verbatim(
    patched_clients: tuple[DetectorClient, AsyncMock, AsyncMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """C2 - the DEBUG message, its level and the complete ``extra`` KEY set."""
    c, _detection, _health = patched_clients
    win(caplog)

    await c.close()

    rec = one(caplog, logging.DEBUG, CLOSE_DEBUG, {KEY_DETECTOR_TYPE: DETECTOR_TYPE})
    assert sorted(shipped_extra(rec)) == [KEY_DETECTOR_TYPE]
    assert rec.levelno == logging.DEBUG, f"close() logs at DEBUG: {rec.levelno}"
    assert [r.levelno for r in mine(caplog)] == [logging.DEBUG], (
        f"close() emitted more than its one DEBUG record: {[(r.levelno, r.msg) for r in mine(caplog)]!r}"
    )


# =============================================================================
# health_check() - the request  (production refs: detector_client.py:415-428)
# =============================================================================


@pytest.mark.asyncio
async def test_health_check_gets_the_health_url_with_the_auth_headers(
    health_only: tuple[DetectorClient, AsyncMock],
) -> None:
    """H1 - ``GET {detector_url}/health`` with the auth headers, on the HEALTH client (m2)."""
    c, health = health_only
    health.get.return_value = response_double(payload={"status": "healthy"})

    assert await c.health_check() is True

    assert health.get.call_args_list == [
        call(f"{DETECTOR_URL}{HEALTH_PATH}", headers={"X-API-Key": API_KEY})
    ], "the health request shape mutated"


@pytest.mark.asyncio
async def test_health_check_returns_true_once_the_status_check_passes(
    health_only: tuple[DetectorClient, AsyncMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """H2 (control) - a 2xx response returns True and emits nothing at WARNING+."""
    c, health = health_only
    health.get.return_value = response_double(status_code=204)
    win(caplog)

    assert await c.health_check() is True

    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.ERROR) == []


# =============================================================================
# health_check() - the transport-failure arm  (refs: detector_client.py:429-434)
# =============================================================================


@pytest.mark.parametrize(
    "exc_type", [httpx.ConnectError, httpx.TimeoutException], ids=["connect", "timeout"]
)
@pytest.mark.asyncio
async def test_the_unreachable_warning_is_the_shipped_text_with_the_error_key(
    health_only: tuple[DetectorClient, AsyncMock],
    caplog: pytest.LogCaptureFixture,
    exc_type: type[httpx.HTTPError],
) -> None:
    """H3 - one WARNING: shipped text, ``{"error": str(e)}``, and False (m7-m17)."""
    c, health = health_only
    health.get.side_effect = exc_type(CONNECT_MSG)
    win(caplog)

    assert await c.health_check() is False

    one(caplog, logging.WARNING, UNREACHABLE_WARNING, {KEY_ERROR: CONNECT_MSG})


@pytest.mark.parametrize(
    "exc_type", [httpx.ConnectError, httpx.TimeoutException], ids=["connect", "timeout"]
)
@pytest.mark.asyncio
async def test_the_unreachable_warning_attaches_the_live_traceback(
    health_only: tuple[DetectorClient, AsyncMock],
    caplog: pytest.LogCaptureFixture,
    exc_type: type[httpx.HTTPError],
) -> None:
    """H4 - the same record carries ``exc_info`` reporting THAT exception (m9, m12, m19)."""
    c, health = health_only
    boom = exc_type(CONNECT_MSG)
    health.get.side_effect = boom
    win(caplog)

    assert await c.health_check() is False

    rec = one(caplog, logging.WARNING, UNREACHABLE_WARNING, {KEY_ERROR: CONNECT_MSG})
    pin_exc_of(rec, boom)


@pytest.mark.asyncio
async def test_the_unreachable_error_text_is_the_exception_message(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H5 - the error text is the transport exception's OWN message (m18; routes m32 too)."""
    c, health = health_only
    health.get.side_effect = httpx.ConnectError("no route to yolo26")
    win(caplog)

    assert await c.health_check() is False

    one(caplog, logging.WARNING, UNREACHABLE_WARNING, {KEY_ERROR: "no route to yolo26"})


# =============================================================================
# health_check() - the HTTPStatusError arm  (refs: detector_client.py:435-441)
# =============================================================================


def status_error(message: str, status_code: int = 503) -> httpx.HTTPStatusError:
    """An ``HTTPStatusError`` carrying a real request/response pair."""
    response = response_double(status_code=status_code)
    return httpx.HTTPStatusError(message, request=response.request, response=response)


@pytest.mark.asyncio
async def test_the_error_status_warning_is_the_shipped_text_with_the_error_key(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H6 - one WARNING from the status arm: text, level and ``error`` KEY (m21-m31)."""
    c, health = health_only
    health.get.side_effect = status_error(STATUS_MSG, status_code=422)
    win(caplog)

    assert await c.health_check() is False

    rec = one(caplog, logging.WARNING, STATUS_WARNING, {KEY_ERROR: STATUS_MSG})
    assert rec.levelno == logging.WARNING, "the status arm logs at WARNING, not ERROR"


@pytest.mark.asyncio
async def test_the_error_status_error_text_is_the_status_exception_message(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H7 - the KEY's value is THAT exception's message (m32; second route to m18)."""
    c, health = health_only
    health.get.side_effect = status_error(STATUS_ERROR, status_code=409)
    win(caplog)

    assert await c.health_check() is False

    one(caplog, logging.WARNING, STATUS_WARNING, {KEY_ERROR: STATUS_ERROR})


@pytest.mark.asyncio
async def test_the_error_status_warning_attaches_the_live_traceback(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H8 - the status WARNING carries ``exc_info`` for the status error (m23, m26, m33)."""
    c, health = health_only
    boom = status_error(STATUS_MSG)
    health.get.side_effect = boom
    win(caplog)

    assert await c.health_check() is False

    rec = one(caplog, logging.WARNING, STATUS_WARNING, {KEY_ERROR: STATUS_MSG})
    pin_exc_of(rec, boom)


@pytest.mark.asyncio
async def test_the_status_arm_never_emits_the_other_two_warning_texts(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H9 (control) - the whole WARNING surface is exactly the one shipped status text."""
    c, health = health_only
    health.get.side_effect = status_error(STATUS_MSG)
    win(caplog)

    assert await c.health_check() is False

    assert [r.msg for r in at(caplog, logging.WARNING)] == [STATUS_WARNING]
    assert at(caplog, logging.ERROR) == []


# =============================================================================
# health_check() - the unexpected-failure arm  (refs: detector_client.py:442-451)
# =============================================================================


@pytest.mark.asyncio
async def test_the_unexpected_failure_is_an_error_record_with_the_error_key(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H10 - one ERROR: shipped text, ``{"error": sanitize_error(e)}``, False (m35-m45)."""
    c, health = health_only
    health.get.side_effect = OSError(OSERROR_MSG)
    win(caplog)

    assert await c.health_check() is False

    one(caplog, logging.ERROR, UNEXPECTED_ERROR, {KEY_ERROR: OSERROR_SANITIZED})


@pytest.mark.asyncio
async def test_the_unexpected_failure_record_attaches_the_live_traceback(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H11 - the ERROR record carries ``exc_info`` for the OSError (m37, m40, m47)."""
    c, health = health_only
    boom = OSError(OSERROR_MSG)
    health.get.side_effect = boom
    win(caplog)

    assert await c.health_check() is False

    rec = one(caplog, logging.ERROR, UNEXPECTED_ERROR, {KEY_ERROR: OSERROR_SANITIZED})
    pin_exc_of(rec, boom)


@pytest.mark.asyncio
async def test_the_unexpected_failure_text_is_the_sanitized_error(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H12 - the shipped KEY goes through ``sanitize_error`` (paths shortened), unlike the
    transport arms which use ``str(e)`` (m46; routes to m18/m32)."""
    assert OSERROR_SANITIZED != OSERROR_MSG, "the fixture lost its path-shortening contrast"
    c, health = health_only
    health.get.side_effect = OSError(OSERROR_MSG)
    win(caplog)

    assert await c.health_check() is False

    rec = one(caplog, logging.ERROR, UNEXPECTED_ERROR, {KEY_ERROR: OSERROR_SANITIZED})
    assert rec.levelno == logging.ERROR, "the unexpected arm logs at ERROR, not WARNING"


@pytest.mark.asyncio
async def test_the_runtime_failure_arm_uses_the_same_surface(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H13 - ``RuntimeError`` lands on the same ERROR record (second route to m35-m47)."""
    c, health = health_only
    boom = RuntimeError(RUNTIME_MSG)
    health.get.side_effect = boom
    win(caplog)

    assert await c.health_check() is False

    rec = one(caplog, logging.ERROR, UNEXPECTED_ERROR, {KEY_ERROR: RUNTIME_MSG})
    pin_exc_of(rec, boom)


@pytest.mark.asyncio
async def test_the_value_failure_arm_uses_the_same_surface(
    health_only: tuple[DetectorClient, AsyncMock], caplog: pytest.LogCaptureFixture
) -> None:
    """H14 - ``ValueError`` lands on the same ERROR record (third route to m35-m47)."""
    c, health = health_only
    boom = ValueError(VALUE_MSG)
    health.get.side_effect = boom
    win(caplog)

    assert await c.health_check() is False

    rec = one(caplog, logging.ERROR, UNEXPECTED_ERROR, {KEY_ERROR: VALUE_MSG})
    pin_exc_of(rec, boom)
    assert [(r.levelno, r.msg) for r in mine(caplog)] == [(logging.ERROR, UNEXPECTED_ERROR)], (
        f"unexpected extra records: {[(r.levelno, r.msg) for r in mine(caplog)]!r}"
    )
