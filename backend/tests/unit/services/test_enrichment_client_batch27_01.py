"""S3 batch-27 lane 01 — enrichment_client LOG-TEXT + ``extra=`` kill battery (campaign #3).

Family probed: the ``log text + extra`` survivors in
backend/services/enrichment_client.py — mutants that rewrite a logger call's
message (``logger.debug(None)``, ``"XX...XX"``, ``.upper()``, ``.lower()``,
dropped lazy ``%s`` args), rewrite an ``extra=`` key (``"XXduration_msXX"`` /
``"DURATION_MS"``) or drop the whole ``extra=`` / ``exc_info=`` argument. Every
one of them is observability-only, which is exactly why they survived: no test in
the pre-existing enrichment suite reads a log record (caplog appears zero times).
Nothing here needs a production change — the kill is an assertion on the emitted
``logging.LogRecord``.

Each assertion reads the field the mutation moves:

``record.msg``           the RAW format string, never ``getMessage()``. Reading
                         the raw string is what makes the lazily-formatted
                         (``%s``) sites killable: had we asserted on the
                         interpolated text, the ``string:upper`` mutant on
                         ``"Sending vehicle classification request to %s"``
                         (which also upper-cases the conversion spec, ``%S``)
                         would still interpolate and hide. Raw msg also kills
                         ``logger.debug(None)`` and the "drop the message
                         argument" variant (that one moves the value INTO msg).
``record.args``          the lazy positional tuple — kills ``arg->None`` and the
                         dropped-arg variants.
``record.<extra key>``   presence is checked against a CLOSED catalogue
                         (``_EXTRA_KEYS``) so ``extra=None``, a deleted ``extra=``
                         and a renamed key all fail, and the values are checked
                         too. caplog records pass through ``ContextFilter``
                         (backend/core/logging.py) which only ADDS context keys
                         (request_id / correlation_id / trace_id / hostname / ...)
                         and never one of the four catalogue names, so "absent"
                         is a load-bearing assertion.
``record.exc_info``      pristine is always a live 3-tuple (``exc_info=True``
                         inside an ``except`` block); ``exc_info=None``,
                         ``exc_info=False`` and a dropped argument yield
                         ``None`` / ``False``.
``record.levelno``       not moved by this family, but level is the other half of
                         log observability so every check pins it.

Windows: ``caplog.set_level`` does NOT clear the buffer (the historical CI-flake
family), so every test opens its window with ``set_level`` + ``clear()`` and
filters records to this module's logger name so a collaborator module's output
can never pollute a count.

No behavior is invented: every expected string is transcribed from the shipped
source at the mutated line, and every interpolated value is one the test injects
(fixed settings URL, scripted clock, scripted backoff, chosen HTTP status).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.core.exceptions import EnrichmentUnavailableError
from backend.services import enrichment_client as M

logger = M.logger  # module attribute — logger identity is the module's logger
LOG_NAME = logger.name

pytestmark = [pytest.mark.unit]

SERVICE_URL = "http://test-enrichment:8094"
LIGHT_URL = "http://test-enrichment-light:8096"
MAX_RETRIES = 3
# settings: enrichment_read_timeout 60.0 + ai_connect_timeout 10.0
EXPLICIT_TIMEOUT = 70.0
# Scripted backoff (the shipped method adds +/-10% jitter to 2 ** attempt).
DELAY = 2.5
# Scripted clock: 1st read 1000.0 (start_time), every later read 1004.75, so
# duration_ms == int(4.75 * 1000) == 4750 regardless of how many probes the path
# makes. Both values are exact binary fractions, so no float drift.
DURATION_MS = 4750

# Closed world of keys this module ever routes through extra=.
_EXTRA_KEYS = ("duration_ms", "status_code", "explicit_timeout", "detection_type")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
async def reset_global_client() -> None:
    """Reset the global enrichment client around every test (house idiom)."""
    await M.reset_enrichment_client()
    yield
    await M.reset_enrichment_client()


def make_settings() -> MagicMock:
    settings = MagicMock()
    settings.enrichment_url = SERVICE_URL
    settings.enrichment_light_url = LIGHT_URL
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
    settings.enrichment_read_timeout = 60.0
    settings.enrichment_cb_failure_threshold = 5
    settings.enrichment_cb_recovery_timeout = 60.0
    settings.enrichment_cb_half_open_max_calls = 3
    settings.enrichment_max_retries = MAX_RETRIES
    settings.get_enrichment_url_for_model = MagicMock(return_value=SERVICE_URL)
    return settings


@pytest.fixture
def mock_settings() -> MagicMock:
    return make_settings()


def build_client(settings: MagicMock) -> Any:
    """EnrichmentClient with both persistent httpx clients mocked (NEM-1721)."""
    http_mock = AsyncMock()
    http_mock.aclose = AsyncMock()
    health_mock = AsyncMock()
    health_mock.aclose = AsyncMock()
    with (
        patch(
            "backend.services.enrichment_client.get_settings",
            return_value=settings,
            autospec=True,
        ),
        patch("httpx.AsyncClient", side_effect=[http_mock, health_mock], autospec=True),
    ):
        c = M.EnrichmentClient()
    c._http_client = http_mock
    c._health_http_client = health_mock
    return c


@pytest.fixture
def client(mock_settings: MagicMock) -> Any:
    return build_client(mock_settings)


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def frames() -> list[Image.Image]:
    return [Image.new("RGB", (20, 20), color=f"#{i:02x}0000") for i in range(4)]


class Res:
    """Bundles the two image-ish stimuli so parametrized tests take one arg."""

    def __init__(self, image: Image.Image, frames: list[Image.Image]) -> None:
        self.image = image
        self.frames = frames


@pytest.fixture
def res(image: Image.Image, frames: list[Image.Image]) -> Res:
    return Res(image, frames)


# =============================================================================
# Observation helpers
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def assert_record(
    r: logging.LogRecord,
    *,
    msg: str,
    level: int,
    extras: dict[str, Any] | None = None,
    lazy: tuple[Any, ...] | None = None,
    exc_of: type[BaseException] | None = None,
) -> None:
    """Assert the whole observable surface of one emitted record."""
    extras = extras or {}
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    present = {k for k in _EXTRA_KEYS if hasattr(r, k)}
    assert present == set(extras), f"extra= keys mutated: {sorted(present)} != {sorted(extras)}"
    for key, value in extras.items():
        assert getattr(r, key) == value, f"extra={key!r} mutated: {getattr(r, key)!r} != {value!r}"
    if lazy is None:
        assert tuple(r.args or ()) == (), f"unexpected lazy args {r.args!r} for an f-string message"
    else:
        assert tuple(r.args or ()) == tuple(lazy), (
            f"lazy args mutated: {r.args!r} != {tuple(lazy)!r}"
        )
    if exc_of is None:
        assert r.exc_info is None, (
            f"exc_info present where the shipped call passes none: {r.exc_info!r}"
        )
    else:
        assert isinstance(r.exc_info, tuple), f"exc_info=True mutated to {r.exc_info!r}"
        assert isinstance(r.exc_info[1], exc_of), f"exc_info payload mutated: {r.exc_info!r}"


def check(
    caplog: pytest.LogCaptureFixture,
    *,
    msg: str,
    level: int,
    extras: dict[str, Any] | None = None,
    lazy: tuple[Any, ...] | None = None,
    exc_of: type[BaseException] | None = None,
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    r = recs[0]
    assert_record(r, msg=msg, level=level, extras=extras, lazy=lazy, exc_of=exc_of)
    return r


# =============================================================================
# Stimulus helpers
# =============================================================================


def status_error(message: str, code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", f"{SERVICE_URL}/endpoint")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(message, request=request, response=response)


def scripted_clock() -> Callable[[], float]:
    state = {"i": 0}

    def _now() -> float:
        i = state["i"]
        state["i"] = i + 1
        return 1000.0 if i == 0 else 1004.75

    return _now


def ok_response(payload: dict[str, Any] | None = None, status: int = 200) -> MagicMock:
    response = MagicMock(name="response")
    response.json.return_value = payload if payload is not None else {}
    response.raise_for_status = MagicMock()
    response.status_code = status
    return response


def post_stimulus(client: Any, stimulus: BaseException | Any) -> AsyncMock:
    """Install a post stub that raises ``stimulus`` (exception) or returns it."""
    if isinstance(stimulus, BaseException):
        mock = AsyncMock(side_effect=stimulus)
    else:
        mock = AsyncMock(return_value=stimulus)
    client._http_client.post = mock
    return mock


def get_stimulus(
    client: Any, stimulus: BaseException | Any, *, target: str = "_http_client"
) -> AsyncMock:
    if isinstance(stimulus, BaseException):
        mock = AsyncMock(side_effect=stimulus)
    else:
        mock = AsyncMock(return_value=stimulus)
    getattr(client, target).get = mock
    return mock


def retry_patches(client: Any) -> tuple[Any, ...]:
    """Zero-sleep, deterministic-delay, deterministic-clock patch stack."""
    return (
        patch("backend.services.enrichment_client.asyncio.sleep", new_callable=AsyncMock),
        patch.object(client, "_calculate_backoff_delay", return_value=DELAY, autospec=True),
        patch(
            "backend.services.enrichment_client.time.time",
            side_effect=scripted_clock(),
            autospec=True,
        ),
        patch("backend.services.enrichment_client.record_pipeline_error", autospec=True),
        patch("backend.services.enrichment_client.increment_enrichment_retry", autospec=True),
    )


# Per-model table. ``log`` is the single DEBUG line emitted before the retry
# loop; ``unexpected`` is the shipped "Unexpected error during ..." message.
# Lines shared by all seven models carry the SAME mutant set at seven distinct
# source lines, so one parametrized test per path dispositions all seven sites.
MODELS: dict[str, dict[str, Any]] = {
    "vehicle": {
        "api": "classify_vehicle",
        "log_msg": "Sending vehicle classification request to %s",
        "unexpected": "Unexpected error during vehicle classification: kaboom",
        "metric": "enrichment_vehicle_unexpected_error",
        "payload": {
            "vehicle_type": "sedan",
            "display_name": "Sedan",
            "confidence": 0.5,
            "is_commercial": False,
            "all_scores": {},
            "inference_time_ms": 1.0,
        },
    },
    "pet": {
        "api": "classify_pet",
        "log_msg": "Sending pet classification request to %s",
        "unexpected": "Unexpected error during pet classification: kaboom",
        "metric": "enrichment_pet_unexpected_error",
        "payload": {
            "pet_type": "cat",
            "breed": "tabby",
            "confidence": 0.5,
            "is_household_pet": True,
            "inference_time_ms": 1.0,
        },
    },
    "clothing": {
        "api": "classify_clothing",
        "log_msg": "Sending clothing classification request to %s",
        "unexpected": "Unexpected error during clothing classification: kaboom",
        "metric": "enrichment_clothing_unexpected_error",
        "payload": {
            "clothing_type": "jacket",
            "color": "red",
            "style": "casual",
            "confidence": 0.5,
            "top_category": "outerwear",
            "description": "d",
            "is_suspicious": False,
            "is_service_uniform": False,
            "inference_time_ms": 1.0,
        },
    },
    "depth": {
        "api": "estimate_depth",
        "log_msg": "Sending depth estimation request to %s",
        "unexpected": "Unexpected error during depth estimation: kaboom",
        "metric": "enrichment_depth_unexpected_error",
        "payload": {
            "depth_map_base64": "AAA",
            "min_depth": 0.5,
            "max_depth": 9.5,
            "mean_depth": 3.0,
            "inference_time_ms": 1.0,
        },
    },
    "distance": {
        "api": "estimate_object_distance",
        "log_msg": "Sending object distance request with method=%s to %s",
        "unexpected": "Unexpected error during distance estimation: kaboom",
        "metric": "enrichment_distance_unexpected_error",
        "payload": {
            "estimated_distance_m": 2.5,
            "relative_depth": 0.4,
            "proximity_label": "medium",
            "inference_time_ms": 1.0,
        },
    },
    "pose": {
        "api": "analyze_pose",
        "log_msg": "Sending pose analysis request to %s",
        "unexpected": "Unexpected error during pose analysis: kaboom",
        "metric": "enrichment_pose_unexpected_error",
        "payload": {
            "keypoints": [],
            "posture": "standing",
            "alerts": [],
            "inference_time_ms": 1.0,
        },
    },
    "action": {
        "api": "classify_action",
        "log_msg": "Sending action classification request with %d frames to %s",
        "unexpected": "Unexpected error during action classification: kaboom",
        "metric": "enrichment_action_unexpected_error",
        "payload": {
            "action": "walking",
            "confidence": 0.5,
            "is_suspicious": False,
            "risk_weight": 0.1,
            "all_scores": {},
            "inference_time_ms": 1.0,
        },
    },
}
MODEL_NAMES = list(MODELS)
# endpoint_name differs from the routing key only for object-distance.
ENDPOINT_NAME = {"distance": "distance"}

# Line templates shared by all seven per-model retry bodies (the mutation feed
# gives each of the seven source lines the SAME mutant set, so one parametrized
# test dispositions all seven). {} slots: endpoint_name / attempt / explicit
# timeout, depending on the line.
CLIENT_ERROR_MSG = "Enrichment returned client error: 429 - client boom"
SERVER_RETRY_MSG = "Enrichment {} retry {}/3, waiting 2.5s after server error 503"
SERVER_FINAL_MSG = "Enrichment returned server error after 3 retries: 503 - server boom"
CONN_RETRY_MSG = "Enrichment {} retry {}/3, waiting 2.5s after connection_error"
CONN_FINAL_MSG = "Enrichment {} failed after 3 retries: conn boom"
TO_RETRY_MSG = (
    "Enrichment {} asyncio timeout (attempt {}/3), waiting 2.5s: request timed out after 70.0s"
)
TO_FINAL_MSG = "Enrichment {} asyncio timeout after 3 retries: request timed out after 70.0s"


def endpoint_name(model: str) -> str:
    return ENDPOINT_NAME.get(model, model)


def drive(client: Any, model: str, res: Res) -> Any:
    """Call the model's entry point with the arity its signature requires."""
    api = getattr(client, MODELS[model]["api"])
    if model == "action":
        return api(res.frames)
    if model == "depth":
        return api(res.image)
    if model == "distance":
        return api(res.image, (5.0, 5.0, 50.0, 60.0), "median")
    return api(res.image)


def lazy_for(model: str, res: Res) -> tuple[Any, ...]:
    if model == "distance":
        return ("median", SERVICE_URL)
    if model == "action":
        return (len(res.frames), SERVICE_URL)
    return (SERVICE_URL,)


# =============================================================================
# Construction / teardown lines (1 survivor at 930; 4 at 968)
# =============================================================================


def test_init_logs_info_with_resolved_base_url(caplog: pytest.LogCaptureFixture) -> None:
    """Ship 930: INFO ``EnrichmentClient initialized with base_url=<resolved>``.

    Kills ``logger.info(None)`` plus any rewrite of the prefix or of the
    interpolated URL (the settings fixture resolves enrichment_url).
    """
    win(caplog)
    build_client(make_settings())
    check(
        caplog, msg=f"EnrichmentClient initialized with base_url={SERVICE_URL}", level=logging.INFO
    )


@pytest.mark.asyncio
async def test_close_logs_debug_verbatim(caplog: pytest.LogCaptureFixture, client: Any) -> None:
    """Ship 968: DEBUG ``EnrichmentClient HTTP connections closed`` (4 mutants:
    None / XXwrap / lower / upper — exact equality kills all four)."""
    win(caplog)
    await client.close()
    check(caplog, msg="EnrichmentClient HTTP connections closed", level=logging.DEBUG)


# =============================================================================
# check_health (4 + 4 + 3 survivors at 1113 / 1121 / 1129)
# =============================================================================


@pytest.mark.asyncio
async def test_check_health_connection_failure_warning_text_and_exc_info(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 1113: WARNING ``Enrichment health check failed: <str(e)>`` + exc_info=True.

    Covers all four mutants at that line: text -> None / case rewrites,
    ``exc_info=None``, the dropped ``exc_info=`` argument (``record.exc_info``
    stops being a live tuple) and ``exc_info=False``.
    """
    exc = httpx.ConnectError("hb conn")
    get_stimulus(client, exc, target="_health_http_client")
    win(caplog)
    result = await client.check_health()
    assert result["status"] == "unavailable"
    r = check(
        caplog,
        msg=f"Enrichment health check failed: {exc}",
        level=logging.WARNING,
        exc_of=httpx.ConnectError,
    )
    assert r.exc_info[1] is exc


@pytest.mark.asyncio
async def test_check_health_error_status_warning_text_and_exc_info(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 1121: WARNING ``Enrichment health check returned error status: <e>``."""
    exc = status_error("hb status boom", 502)
    get_stimulus(client, exc, target="_health_http_client")
    win(caplog)
    result = await client.check_health()
    assert result["status"] == "error"
    r = check(
        caplog,
        msg=f"Enrichment health check returned error status: {exc}",
        level=logging.WARNING,
        exc_of=httpx.HTTPStatusError,
    )
    assert r.exc_info[1] is exc


@pytest.mark.asyncio
async def test_check_health_unexpected_error_text_and_exc_info(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 1129: ERROR ``Unexpected error during Enrichment health check:
    <sanitize_error(e)>``. ``sanitize_error`` is the identity for a message with
    no path / credential pattern, which is what the expected text encodes."""
    exc = RuntimeError("healthcheck kaboom")
    get_stimulus(client, exc, target="_health_http_client")
    win(caplog)
    result = await client.check_health()
    assert result["status"] == "error"
    check(
        caplog,
        msg="Unexpected error during Enrichment health check: healthcheck kaboom",
        level=logging.ERROR,
        exc_of=RuntimeError,
    )


# =============================================================================
# The seven per-model "sending request" DEBUG lines (7 survivors each)
# =============================================================================


@pytest.mark.parametrize("model", MODEL_NAMES)
@pytest.mark.asyncio
async def test_send_request_debug_line_text_and_lazy_args(
    model: str, caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1199 / 1390 / 1579 / 1771 / 1994 / 2190 / 2399.

    These are the only lazily-formatted logger calls in the retry family, so
    each carries three mutant shapes: the text (None / XXwrap / upper / lower —
    the upper mutant also destroys the conversion spec, ``%s`` -> ``%S``), the
    positional args (``arg->None``) and the two dropped-arg variants. Raw
    ``record.msg`` + exact ``record.args`` kills all seven.
    """
    post_stimulus(client, ok_response(MODELS[model]["payload"]))
    win(caplog)
    with patch("backend.services.enrichment_client.observe_ai_request_duration", autospec=True):
        got = await drive(client, model, res)
    assert got is not None
    check(
        caplog,
        msg=MODELS[model]["log_msg"],
        level=logging.DEBUG,
        lazy=lazy_for(model, res),
    )


# =============================================================================
# The seven 4xx sites (9 survivors each)
# =============================================================================


@pytest.mark.parametrize("model", MODEL_NAMES)
@pytest.mark.asyncio
async def test_client_error_4xx_log_text_extra_keys_and_exc_info(
    model: str, caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1250 / 1440 / 1633 / 1819 / 2045 / 2253 / 2461 (+ their extra= dicts).

    ERROR ``Enrichment returned client error: 429 - client boom`` with
    ``extra={"duration_ms": 4750, "status_code": 429}`` + exc_info=True, then
    ``return None``. The closed-world KEY check is what kills ``XXduration_msXX``
    / ``DURATION_MS`` / ``STATUS_CODE`` / ``extra=None`` / a deleted ``extra=``;
    the values kill a swapped payload.
    """
    post_stimulus(client, status_error("client boom", 429))
    win(caplog)
    with (
        patch(
            "backend.services.enrichment_client.time.time",
            side_effect=scripted_clock(),
            autospec=True,
        ),
        patch("backend.services.enrichment_client.record_pipeline_error", autospec=True),
    ):
        assert await drive(client, model, res) is None
    check(
        caplog,
        msg=CLIENT_ERROR_MSG,
        level=logging.ERROR,
        extras={"duration_ms": DURATION_MS, "status_code": 429},
        exc_of=httpx.HTTPStatusError,
    )


# =============================================================================
# The seven 5xx retry/final sites (1 + 9 survivors each)
# =============================================================================


@pytest.mark.parametrize("model", MODEL_NAMES)
@pytest.mark.asyncio
async def test_server_error_retry_and_final_log_text_and_extra(
    model: str, caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1262 / 1452 / 1645 / 1831 / 2057 / 2265 / 2473 (retry WARNING) and
    1272 / 1462 / 1655 / 1841 / 2067 / 2275 / 2483 (final ERROR + extra keys).

    Both lines interpolate endpoint_name, the attempt/max-retries counter, the
    scripted delay and the status code, so a ``call_arg_mut`` that replaces the
    message with ``None`` is visible. The retry WARNING carries NO extra= and NO
    exc_info: asserting their absence kills a mutant that moved a payload onto
    the wrong call.
    """
    post_stimulus(client, status_error("server boom", 503))
    win(caplog)
    p0, p1, p2, p3, p4 = retry_patches(client)
    with p0, p1, p2, p3, p4:
        with pytest.raises(EnrichmentUnavailableError):
            await drive(client, model, res)
    recs = mine(caplog)
    assert [r.levelno for r in recs] == [
        logging.DEBUG,
        logging.WARNING,
        logging.WARNING,
        logging.ERROR,
    ], [(r.levelno, r.msg) for r in recs]
    # attempt 0 and 1 each log a retry line; the counter is interpolated, so the
    # two lines differ (1/3 then 2/3) — pinning both kills an off-by-one mutant.
    for idx, r in enumerate(recs[1:3], start=1):
        assert_record(
            r, msg=SERVER_RETRY_MSG.format(endpoint_name(model), idx), level=logging.WARNING
        )
    assert_record(
        recs[3],
        msg=SERVER_FINAL_MSG,
        level=logging.ERROR,
        extras={"duration_ms": DURATION_MS, "status_code": 503},
        exc_of=httpx.HTTPStatusError,
    )


# =============================================================================
# The seven ConnectError sites (1 + 7 survivors each)
# =============================================================================


@pytest.mark.parametrize("model", MODEL_NAMES)
@pytest.mark.asyncio
async def test_connection_error_retry_and_final_log_text_and_extra(
    model: str, caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1286 / 1476 / 1669 / 1855 / 2081 / 2289 / 2497 (retry WARNING — the
    ``error_type`` interpolation is exactly ``connection_error`` here) and
    1297 / 1487 / 1680 / 1866 / 2092 / 2300 / 2508 (final ERROR with the
    SINGLE-key ``{"duration_ms"}`` payload).

    Asserting that this payload has no ``status_code`` / ``explicit_timeout``
    kills a mutant that hoists a sibling call's payload onto this line.
    """
    post_stimulus(client, httpx.ConnectError("conn boom"))
    win(caplog)
    p0, p1, p2, p3, p4 = retry_patches(client)
    with p0, p1, p2, p3, p4:
        with pytest.raises(EnrichmentUnavailableError):
            await drive(client, model, res)
    recs = mine(caplog)
    assert [r.levelno for r in recs] == [
        logging.DEBUG,
        logging.WARNING,
        logging.WARNING,
        logging.ERROR,
    ], [(r.levelno, r.msg) for r in recs]
    for idx, r in enumerate(recs[1:3], start=1):
        assert_record(
            r, msg=CONN_RETRY_MSG.format(endpoint_name(model), idx), level=logging.WARNING
        )
    assert_record(
        recs[3],
        msg=CONN_FINAL_MSG.format(endpoint_name(model)),
        level=logging.ERROR,
        extras={"duration_ms": DURATION_MS},
        exc_of=httpx.ConnectError,
    )


# =============================================================================
# The asyncio-timeout sites that actually carry survivors (1 + 9 each)
# =============================================================================


@pytest.mark.parametrize("model", ["vehicle", "clothing", "pose", "distance", "action"])
@pytest.mark.asyncio
async def test_asyncio_timeout_retry_and_final_log_text_and_extra(
    model: str, caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1309 / 1692 / 2104 / 2312 / 2520 (retry WARNING) and
    1320 / 1703 / 2115 / 2323 / 2531 (final ERROR).

    This final payload is the only place in the module that routes
    ``explicit_timeout`` through extra=, so the closed-world key check pins it
    apart from its four sibling paths. Every parametrized model computes
    ``explicit_timeout`` the same way (read 60.0 + connect 10.0 == 70.0), so one
    template covers all five. pet/depth are deliberately NOT parametrized here:
    their asyncio-timeout lines 1499/1510/1878/1889 carry ZERO survivors (the
    feed never executed those lines, so mutmut generated nothing to kill), and
    asserting unmutated text is a pin, not a kill.
    """
    post_stimulus(client, TimeoutError())
    win(caplog)
    p0, p1, p2, p3, p4 = retry_patches(client)
    with p0, p1, p2, p3, p4:
        with pytest.raises(EnrichmentUnavailableError):
            await drive(client, model, res)
    recs = mine(caplog)
    assert [r.levelno for r in recs] == [
        logging.DEBUG,
        logging.WARNING,
        logging.WARNING,
        logging.ERROR,
    ], [(r.levelno, r.msg) for r in recs]
    for idx, r in enumerate(recs[1:3], start=1):
        assert_record(r, msg=TO_RETRY_MSG.format(endpoint_name(model), idx), level=logging.WARNING)
    assert_record(
        recs[3],
        msg=TO_FINAL_MSG.format(endpoint_name(model)),
        level=logging.ERROR,
        extras={"duration_ms": DURATION_MS, "explicit_timeout": EXPLICIT_TIMEOUT},
        exc_of=TimeoutError,
    )


# =============================================================================
# The seven unexpected-error sites (7 survivors each)
# =============================================================================


@pytest.mark.parametrize("model", MODEL_NAMES)
@pytest.mark.asyncio
async def test_unexpected_error_log_text_extra_and_exc_info(
    model: str, caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1332 / 1522 / 1715 / 1901 / 2127 / 2335 / 2543: ERROR
    ``Unexpected error during <phase>: <sanitize_error(e)>`` with
    ``extra={"duration_ms": ...}`` + exc_info=True, then raise.

    The phase word in the message is the ONLY thing distinguishing these seven
    sites from one another ("vehicle classification" vs "distance estimation"
    vs "pose analysis" ...), so verbatim text is what kills a word-level mutant.
    """
    exc = RuntimeError("kaboom")
    post_stimulus(client, exc)
    win(caplog)
    with (
        patch(
            "backend.services.enrichment_client.time.time",
            side_effect=scripted_clock(),
            autospec=True,
        ),
        patch("backend.services.enrichment_client.record_pipeline_error", autospec=True) as metric,
    ):
        with pytest.raises(EnrichmentUnavailableError):
            await drive(client, model, res)
    metric.assert_called_once_with(MODELS[model]["metric"])
    r = check(
        caplog,
        msg=MODELS[model]["unexpected"],
        level=logging.ERROR,
        extras={"duration_ms": DURATION_MS},
        exc_of=RuntimeError,
    )
    assert r.exc_info[1] is exc


# =============================================================================
# estimate_object_distance bbox lines (1 survivor each: 1970 / 1979 / 1989)
# =============================================================================


@pytest.mark.asyncio
async def test_object_distance_invalid_bbox_warning_text(
    caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1970: WARNING built from an f-string IMMEDIATELY followed by a plain
    ``str`` — the two literals concatenate at compile time, so the whole two
    sentences must appear in one record. Zero-width bbox short-circuits before
    any HTTP call (``return None``)."""
    win(caplog)
    assert (
        await client.estimate_object_distance(res.image, (50.0, 50.0, 50.0, 80.0), "center") is None
    )
    check(
        caplog,
        msg=(
            "Invalid bounding box for object distance estimation: (50.0, 50.0, 50.0, 80.0). "
            "Bounding box has invalid dimensions (zero width/height, NaN, or inverted)."
        ),
        level=logging.WARNING,
    )


@pytest.mark.asyncio
async def test_object_distance_out_of_image_warning_text(
    caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1979: WARNING ``Bounding box <bbox> is invalid after validation:
    <warnings>. Image size: <w>x<h>`` — the shipped warning list for a wholly
    outside box plus the 100x100 fixture image size are both interpolated."""
    win(caplog)
    assert (
        await client.estimate_object_distance(res.image, (200.0, 200.0, 300.0, 300.0), "center")
        is None
    )
    check(
        caplog,
        msg=(
            "Bounding box (200.0, 200.0, 300.0, 300.0) is invalid after validation: "
            "['Bounding box is completely outside image boundaries']. Image size: 100x100"
        ),
        level=logging.WARNING,
    )


@pytest.mark.asyncio
async def test_object_distance_clamped_bbox_debug_text(
    caplog: pytest.LogCaptureFixture, client: Any, res: Res
) -> None:
    """Ship 1989: DEBUG ``Bounding box clamped from <bbox> to <clamped> for image
    size <w>x<h>``, emitted only when validation reports ``was_clamped``.

    The follow-on 1994 DEBUG line is asserted in the same test so the two
    adjacent debug messages can never be conflated (the negative x1/y1 clamp to
    the int ``0`` that ``max(0, -10.0)`` yields is part of the pinned text).
    """
    post_stimulus(client, ok_response(MODELS["distance"]["payload"]))
    win(caplog)
    with patch("backend.services.enrichment_client.observe_ai_request_duration", autospec=True):
        got = await client.estimate_object_distance(res.image, (-10.0, -10.0, 50.0, 60.0), "center")
    assert got is not None
    assert [r.msg for r in mine(caplog)] == [
        "Bounding box clamped from (-10.0, -10.0, 50.0, 60.0) to (0, 0, 50.0, 60.0) "
        "for image size 100x100",
        "Sending object distance request with method=%s to %s",
    ], [r.msg for r in mine(caplog)]
    recs = mine(caplog)
    assert [r.levelno for r in recs] == [logging.DEBUG, logging.DEBUG]
    assert tuple(recs[1].args) == ("center", SERVICE_URL)


# =============================================================================
# enrich_detection (1 + 7 + 7 + 5 survivors: 3161 / 3209 / 3226 / 3234)
# =============================================================================


@pytest.mark.asyncio
async def test_enrich_detection_debug_line_interpolates_detection_type(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 3161: DEBUG ``Sending unified enrichment request for <detection_type>``
    — kills ``logger.debug(None)`` and any rewrite of the prefix or the type."""
    post_stimulus(client, ok_response({}))
    win(caplog)
    with patch("backend.services.enrichment_client.observe_ai_request_duration", autospec=True):
        await client.enrich_detection(b"IMG", "person", (1.0, 2.0, 3.0, 4.0))
    check(caplog, msg="Sending unified enrichment request for person", level=logging.DEBUG)


@pytest.mark.asyncio
async def test_enrich_detection_timeout_warning_text_and_extra(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 3209 (+ 3211 keys): WARNING ``Enrichment unified_enrich request timed
    out`` with ``{"duration_ms", "detection_type"}`` — the only call site in the
    module that routes ``detection_type`` through extra=. Note this call passes
    NO exc_info (asserted)."""
    post_stimulus(client, httpx.ReadTimeout("t"))
    win(caplog)
    with patch(
        "backend.services.enrichment_client.time.time", side_effect=scripted_clock(), autospec=True
    ):
        out = await client.enrich_detection(b"IMG", "vehicle", (1.0, 2.0, 3.0, 4.0))
    assert out == M.UnifiedEnrichmentResult()
    check(
        caplog,
        msg="Enrichment unified_enrich request timed out",
        level=logging.WARNING,
        extras={"duration_ms": DURATION_MS, "detection_type": "vehicle"},
    )


@pytest.mark.asyncio
async def test_enrich_detection_http_error_text_and_extra(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 3226 (+ 3228 keys): ERROR ``Enrichment unified_enrich HTTP error:
    <status>`` with ``{"duration_ms", "status_code"}``.

    The wording is NOT the shared ``Enrichment returned client error:`` line used
    by the per-model paths — pinning it verbatim keeps the two families distinct.
    """
    post_stimulus(client, status_error("unified boom", 500))
    win(caplog)
    with patch(
        "backend.services.enrichment_client.time.time", side_effect=scripted_clock(), autospec=True
    ):
        out = await client.enrich_detection(b"IMG", "animal", (1.0, 2.0, 3.0, 4.0))
    assert out == M.UnifiedEnrichmentResult()
    check(
        caplog,
        msg="Enrichment unified_enrich HTTP error: 500",
        level=logging.ERROR,
        extras={"duration_ms": DURATION_MS, "status_code": 500},
    )


@pytest.mark.asyncio
async def test_enrich_detection_connection_error_text_and_extra(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 3234 (+ 3236 key): WARNING ``Enrichment unified_enrich connection
    error: <e>`` with the single-key ``{"duration_ms"}`` payload."""
    post_stimulus(client, httpx.ConnectError("unified conn"))
    win(caplog)
    with patch(
        "backend.services.enrichment_client.time.time", side_effect=scripted_clock(), autospec=True
    ):
        out = await client.enrich_detection(b"IMG", "object", (1.0, 2.0, 3.0, 4.0))
    assert out == M.UnifiedEnrichmentResult()
    check(
        caplog,
        msg="Enrichment unified_enrich connection error: unified conn",
        level=logging.WARNING,
        extras={"duration_ms": DURATION_MS},
    )


# =============================================================================
# get_model_status / preload_model (1 survivor each: 3271 / 3297 / 3300 / 3303)
# =============================================================================


@pytest.mark.asyncio
async def test_get_model_status_connection_failure_warning_text(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 3271: WARNING ``Failed to get model status: <e>``. Pinning the wording
    keeps it distinct from the 3268 ``...: HTTP <code>`` sibling (whose line
    carries zero mutants — never executed by the feed)."""
    exc = httpx.ConnectError("status conn")
    get_stimulus(client, exc)
    win(caplog)
    assert await client.get_model_status() == {"error": "status conn", "loaded_models": []}
    check(caplog, msg=f"Failed to get model status: {exc}", level=logging.WARNING)


@pytest.mark.asyncio
async def test_preload_model_success_info_text(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 3297: INFO ``Successfully preloaded model: <model_name>``."""
    post_stimulus(client, ok_response({}, status=200))
    win(caplog)
    assert await client.preload_model("pose") is True
    check(caplog, msg="Successfully preloaded model: pose", level=logging.INFO)


@pytest.mark.asyncio
async def test_preload_model_http_failure_warning_text(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 3300: WARNING ``Failed to preload model <name>: HTTP <status>``.

    The shipped branch reads ``response.status_code`` only (no raise_for_status),
    so a bare mock carrying just that attribute is the faithful stimulus; the
    ``HTTP`` token and the code are both interpolated into the pinned text.
    """
    response = MagicMock(name="preload-response")
    response.status_code = 503
    post_stimulus(client, response)
    win(caplog)
    assert await client.preload_model("threat") is False
    check(caplog, msg="Failed to preload model threat: HTTP 503", level=logging.WARNING)


@pytest.mark.asyncio
async def test_preload_model_connection_failure_warning_text(
    caplog: pytest.LogCaptureFixture, client: Any
) -> None:
    """Ship 3303: WARNING ``Failed to preload model <name>: <e>``."""
    exc = httpx.ConnectError("preload conn")
    post_stimulus(client, exc)
    win(caplog)
    assert await client.preload_model("clothing") is False
    check(caplog, msg="Failed to preload model clothing: preload conn", level=logging.WARNING)
