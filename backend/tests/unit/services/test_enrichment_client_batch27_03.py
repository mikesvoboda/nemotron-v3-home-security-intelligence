"""Campaign #3 batch-27 slice 03 — mock-boundary REQUEST-KWARG kill battery for
``backend/services/enrichment_client.py``.

Family (from ``/tmp/wp-ec/diffs_exact.json``): mutations to the ``headers=`` and
``timeout=`` request kwargs, to the ``httpx.Timeout(...)`` connect/read/write/pool
field values, and ``exc_info=`` argument mutations on the logger calls in the same
methods.  The inventory proves the gap — ``headers=`` 11 survivors / 0 killed,
``timeout=`` 3/0, read/write/pool 3/3/3 with 0 killed: every shipped test reads
``json=``/``payload=`` off ``call_args`` and NOTHING reads the other kwargs, so
``headers=None``, ``headers=<DELETED>`` and ``httpx.Timeout(read=None)`` are all
invisible.

House idiom: the boundary is the transport, not construction —
``client._http_client.post = AsyncMock(return_value=mock_response)`` and then the
WHOLE recorded call is asserted (positional URL + exact kwargs name-set + exact
kwargs values), so a single-field mutation cannot hide inside a subset assert.
Where the code builds a second ``httpx.Timeout`` internally (``classify_action``)
the FIELDS are asserted, never object identity.  Construction args are captured
separately by patching ``httpx.AsyncClient`` with a recording factory.

Pinned constants — measured off the shipped tree, not guessed:

=============================================  ==========  ==========================
constant                                       value       source (file:line)
=============================================  ==========  ==========================
Settings.ai_connect_timeout                    10.0        backend/core/config.py:1042
Settings.ai_health_timeout                      5.0        backend/core/config.py:1048
Settings.enrichment_read_timeout               60.0        backend/core/config.py:1088
``analyze_pose`` min_confidence default         0.3        .../enrichment_client.py:2147
classify_action ``action_read_timeout``        60.0        .../enrichment_client.py:2396
``self._timeout``                   connect/pool = ai_connect_timeout,
                                    read/write   = enrichment_read_timeout   client:879-884
``self._health_timeout``            all four fields = ai_health_timeout      client:885-890
action request ``timeout=``         connect=self._timeout.connect,
                                    read=60.0 literal, write/pool=self._timeout.*
                                                                           client:2412-2417,2433
=============================================  ==========  ==========================

The injected settings do NOT use the shipped default numbers: ``connect=7.0``,
``read=42.0``, ``health=3.0`` are three mutually different values (all inside the
shipped ``Field`` bounds above, so the mock stays realistic) which makes every
Timeout field individually identifiable — in particular the ``read=60.0`` at the
action call site is provably the literal from client:2396 only because
``enrichment_read_timeout`` is not 60.0.  ``_CONNECT/_READ/_HEALTH`` carry those
numbers into the assertions, and one extra test re-pins the fields at the SHIPPED
default numbers.

Error branches are driven with ``enrichment_max_retries = 1`` so attempt 0 is the
final attempt: the shipped backoff sleeps (client:1044-1061, 1s + 2s) never run,
which keeps every test far inside the 5s pytest timeout (pyproject.toml:536).

No production file is touched, and the global ``_enrichment_client`` singleton is
never populated, so no ``reset_enrichment_client()`` dance is needed.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.enrichment_client import (
    EnrichmentClient,
    EnrichmentUnavailableError,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

# =============================================================================
# Pinned values (see module docstring table)
# =============================================================================

_CONNECT = 7.0  # -> settings.ai_connect_timeout    (used at client:880, 883)
_READ = 42.0  # -> settings.enrichment_read_timeout (used at client:881, 882)
_HEALTH = 3.0  # -> settings.ai_health_timeout      (used at client:886-889)

# Literal at enrichment_client.py:2396 — deliberately != _READ so a swapped field
# cannot masquerade as the shipped value.
_ACTION_READ = 60.0

# Shipped defaults (config.py:1042 / :1048 / :1088) for the default-numbering test.
_D_CONNECT, _D_READ, _D_HEALTH = 10.0, 60.0, 5.0

_BASE_URL = "http://test-enrichment:8094"
_LIGHT_URL = "http://test-enrichment-light:8096"
_LOGGER_NAME = "backend.services.enrichment_client"

# Deterministic stand-in for get_correlation_headers() — client:950-959 forwards
# its return value verbatim into ``headers=``.  Content is irrelevant; presence is
# everything (``headers=None`` / dropped-kwarg mutants lose this dict).
_HEADERS = {"X-Correlation-ID": "corr-b27-03", "traceparent": "00-deadbeef-cafe01-01"}

# Valid, unclamped bbox for the 100x100 sample image.  MEASURED:
# validate_and_clamp_bbox((10,10,50,50), 100, 100) -> is_valid=True,
# was_clamped=False, clamped_bbox=(10.0, 10.0, 50.0, 50.0)
_BBOX: tuple[float, float, float, float] = (10.0, 10.0, 50.0, 50.0)
_BBOX_LIST = [10.0, 10.0, 50.0, 50.0]

# (endpoint_name, "Unexpected error during <phrase>", debug "Sending ..." needle)
# — measured from the shipped endpoint_name assignments and error-handler strings.
_LABEL: dict[str, tuple[str, str, str]] = {
    "vehicle": ("vehicle", "vehicle classification", "Sending vehicle classification request"),
    "pet": ("pet", "pet classification", "Sending pet classification request"),
    "clothing": ("clothing", "clothing classification", "Sending clothing classification request"),
    "depth": ("depth", "depth estimation", "Sending depth estimation request"),
    "distance": ("distance", "distance estimation", "Sending object distance request"),
    "pose": ("pose", "pose analysis", "Sending pose analysis request"),
    "action": ("action", "action classification", "Sending action classification request"),
}
_METHODS = list(_LABEL)

# method -> callable(client, args) awaiting the shipped endpoint, where ``args``
# carries both the sample image and frames (table form avoids an if-chain).
_DISPATCH: dict[str, Any] = {
    "vehicle": lambda c, a: c.classify_vehicle(a.image),
    "pet": lambda c, a: c.classify_pet(a.image),
    "clothing": lambda c, a: c.classify_clothing(a.image),
    "depth": lambda c, a: c.estimate_depth(a.image),
    "distance": lambda c, a: c.estimate_object_distance(a.image, _BBOX),
    "pose": lambda c, a: c.analyze_pose(a.image),
    "action": lambda c, a: c.classify_action(a.frames),
}

# Success payloads — exactly the keys the shipped return blocks read.
_OK: dict[str, dict[str, Any]] = {
    "vehicle": {
        "vehicle_type": "sedan",
        "display_name": "Sedan",
        "confidence": 0.92,
        "is_commercial": False,
        "all_scores": {"sedan": 0.92},
        "inference_time_ms": 42.0,
    },
    "pet": {
        "pet_type": "dog",
        "breed": "labrador",
        "confidence": 0.81,
        "is_household_pet": True,
        "inference_time_ms": 31.0,
    },
    "clothing": {
        "clothing_type": "hoodie",
        "color": "black",
        "style": "casual",
        "confidence": 0.7,
        "top_category": "upper_body",
        "description": "dark hoodie",
        "is_suspicious": False,
        "is_service_uniform": False,
        "inference_time_ms": 27.0,
    },
    "depth": {
        "depth_map_base64": "AAAA",
        "min_depth": 0.5,
        "max_depth": 6.0,
        "mean_depth": 2.0,
        "inference_time_ms": 55.0,
    },
    "distance": {
        "estimated_distance_m": 3.5,
        "relative_depth": 0.4,
        "proximity_label": "medium",
        "inference_time_ms": 19.0,
    },
    "pose": {
        "keypoints": [{"name": "nose", "x": 0.5, "y": 0.4, "confidence": 0.9}],
        "posture": "standing",
        "alerts": [],
        "inference_time_ms": 23.0,
    },
    "action": {
        "action": "loitering",
        "confidence": 0.66,
        "is_suspicious": True,
        "risk_weight": 0.7,
        "all_scores": {"loitering": 0.66},
        "inference_time_ms": 88.0,
    },
}
_ENRICH_OK = {"models_loaded": ["pose"], "inference_time_ms": 1.5}


# =============================================================================
# Fixtures
# =============================================================================


def _settings(*, connect: float, read: float, health: float, retries: int = 1) -> MagicMock:
    """MagicMock Settings with discriminating, in-bounds timeout values."""
    s = MagicMock()
    s.enrichment_url = _BASE_URL
    s.enrichment_light_url = _LIGHT_URL
    s.ai_connect_timeout = connect
    s.ai_health_timeout = health
    s.enrichment_read_timeout = read
    s.enrichment_cb_failure_threshold = 5
    s.enrichment_cb_recovery_timeout = 60.0
    s.enrichment_cb_half_open_max_calls = 3
    s.enrichment_max_retries = retries
    s.use_ai_gateway = False
    s.ai_gateway_url = None
    s.get_enrichment_url_for_model = MagicMock(return_value=_BASE_URL)
    return s


class _Recorder(logging.Handler):
    """Own log-capture handler — capture never depends on pytest's shared handler.

    Own handler (rather than ``caplog.handler``) so delivery is a property of this
    module alone: the shipped logger's records reach us regardless of what other
    suite files have done to the root logger / ``setup_logging()`` mid-session, and
    nothing has to be restored inside pytest's per-item handler.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def logs() -> Iterator[_Recorder]:
    """Capture every record the shipped module logger emits, exactly once."""
    rec = _Recorder()
    lg = logging.getLogger(_LOGGER_NAME)
    saved_handlers = list(lg.handlers)
    saved_propagate = lg.propagate
    saved_level = lg.level
    lg.handlers = [rec]
    lg.propagate = False
    lg.setLevel(logging.DEBUG)
    try:
        yield rec
    finally:
        lg.handlers = saved_handlers
        lg.propagate = saved_propagate
        lg.setLevel(saved_level)


@pytest.fixture
def timeout_delays(monkeypatch: pytest.MonkeyPatch) -> list[float | None]:
    """Record the delay each ``async with asyncio.timeout(x)`` is armed with.

    The shipped NEM-1465 defense-in-depth sites are ``asyncio.timeout(explicit_timeout)``
    (client:1218, 1409, 1598, 1788, 2015, 2212, 2428, 3187).  No log or payload
    assert can see the ``arg->None`` mutant there — the guard simply stops firing —
    so the delay VALUE is asserted.  The spy delegates to the real context manager,
    so behavior is unchanged.
    """
    real = asyncio.timeout
    recorded: list[float | None] = []

    def spy(delay: float | None):
        recorded.append(delay)
        return real(delay)

    monkeypatch.setattr(asyncio, "timeout", spy)
    return recorded


@pytest.fixture
def headers() -> Iterator[dict[str, str]]:
    """Deterministic ``_get_headers()`` for the whole test (client:950-959)."""
    with patch(
        "backend.services.enrichment_client.get_correlation_headers",
        side_effect=lambda: dict(_HEADERS),
        autospec=True,
    ):
        yield _HEADERS


@pytest.fixture
def client(headers: dict[str, str]) -> Iterator[EnrichmentClient]:
    """Client built with the transport replaced and construction args recorded.

    ``httpx.AsyncClient`` is patched to a recording factory, so the two clients the
    constructor creates ARE the AsyncMocks the tests drive, and the kwargs handed
    to each constructor call land on ``client.ctor_calls``.  The patches stay
    active for the test body (``enrich_detection`` calls ``get_settings()`` itself,
    client:3179) and are torn down here — nothing leaks.
    """
    settings = _settings(connect=_CONNECT, read=_READ, health=_HEALTH)
    main = AsyncMock()
    health = AsyncMock()
    main.aclose = AsyncMock()
    health.aclose = AsyncMock()
    ctor_calls: list[dict[str, Any]] = []

    def factory(*args: Any, **kwargs: Any) -> AsyncMock:
        ctor_calls.append({"args": args, **kwargs})
        return main if len(ctor_calls) == 1 else health

    with (
        patch(
            "backend.services.enrichment_client.get_settings",
            return_value=settings,
            autospec=True,
        ),
        patch("httpx.AsyncClient", side_effect=factory, autospec=True),
    ):
        instance = EnrichmentClient()
        instance.ctor_calls = ctor_calls  # type: ignore[attr-defined]
        yield instance


@pytest.fixture
def sample_image() -> Image.Image:
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def sample_frames() -> list[Image.Image]:
    return [Image.new("RGB", (24, 24), color=f"#{i:02x}0000") for i in range(8)]


# =============================================================================
# Helpers
# =============================================================================


def _response(payload: Any, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock()
    return resp


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", f"{_BASE_URL}/endpoint")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"HTTP {code}", request=request, response=response)


def _invoke(method: str, client: EnrichmentClient, image: Image.Image, frames: list[Any]) -> Any:
    """Call the endpoint under test (one awaitable per method name)."""
    return _DISPATCH[method](client, SimpleNamespace(image=image, frames=frames))


def _b64(client: EnrichmentClient, image: Image.Image) -> str:
    """Expected payload value, derived from the shipped encoder (client:970-983)."""
    return client._encode_image_to_base64(image)


def _assert_request(call: Any, *, url: str, **expected: Any) -> None:
    """Whole-call assertion: positional URL, exact kwargs name-set, exact values.

    Kills ``<kw>=None``, ``<DELETED> <kw>=...`` and the ``drop_arg -> ')'`` form
    (which strips the URL plus every kwarg) at every client-call site.
    """
    assert call.args == (url,), f"positional URL mutated: {call.args!r}"
    assert set(call.kwargs) == set(expected), (
        f"kwargs name-set mutated: {sorted(call.kwargs)} != {sorted(expected)}"
    )
    for name, value in expected.items():
        assert call.kwargs[name] == value, f"{name} mutated: {call.kwargs[name]!r} != {value!r}"


def _only(logs: _Recorder, level: int, needle: str) -> logging.LogRecord:
    hits = [r for r in logs.records if r.levelno == level and needle in r.getMessage()]
    if len(hits) != 1:
        seen = [(r.levelname, r.getMessage()) for r in logs.records]
        raise AssertionError(
            f"want exactly one {logging.getLevelName(level)} record containing {needle!r}, got {seen}"
        )
    return hits[0]


def _assert_exc_info(logs: _Recorder, level: int, needle: str, exc: BaseException) -> None:
    """``exc_info=True`` sites: the record must carry the live exception.

    Kills ``exc_info=None`` / ``exc_info=False`` / deleted ``exc_info`` (all leave
    ``LogRecord.exc_info`` None/falsy) and the ``logger.x(None, ...)`` message
    mutants (the needle vanishes).
    """
    rec = _only(logs, level, needle)
    assert rec.exc_info is not None, f"exc_info mutated away at {needle!r}"
    assert rec.exc_info[0] is type(exc)
    assert rec.exc_info[1] is exc


def explicit_timeout(method: str) -> float:
    """``explicit_timeout`` as the shipped code computes it (defense-in-depth guard).

    Six methods: ``enrichment_read_timeout + ai_connect_timeout`` (client:1195-1197
    and the per-endpoint twins); ``classify_action``: ``action_read_timeout +
    ai_connect_timeout`` with the 60.0 literal (client:2396-2397).
    """
    base = _ACTION_READ if method == "action" else _READ
    return base + _CONNECT


def _branch_exc_and_needle(method: str, kind: str) -> tuple[BaseException, str]:
    """(exception to inject, log-message needle) for one final-attempt branch.

    ``enrichment_max_retries`` is 1, so attempt 0 IS the last attempt and the
    branch runs with no backoff sleep (client:1044-1061).
    """
    endpoint_name, phrase, _send = _LABEL[method]
    if kind == "server_error":
        return _status_error(503), "Enrichment returned server error after 1 retries: 503"
    if kind == "connect_error":
        exc: BaseException = httpx.ConnectError("connection refused")
        return exc, f"Enrichment {endpoint_name} failed after 1 retries:"
    if kind == "asyncio_timeout":
        exc = TimeoutError("request timed out")
        # the shipped message interpolates explicit_timeout, so pinning the number
        # also kills ``explicit_timeout = None`` / ``Add->Subtract`` (client:1195-1197,
        # 1386-1388, 1575-1577, 1767-1769, 1963-1965, 2186-2188, 2397)
        return exc, (
            f"Enrichment {endpoint_name} asyncio timeout after 1 retries: "
            f"request timed out after {explicit_timeout(method)}s"
        )
    if kind == "unexpected":
        exc = ValueError("kaboom")
        return exc, f"Unexpected error during {phrase}:"
    raise AssertionError(f"unknown branch {kind}")


async def _final_branch(
    client: EnrichmentClient,
    method: str,
    kind: str,
    logs: _Recorder,
    image: Image.Image,
    frames: list[Any],
    timeout_delays: list[float | None] | None = None,
) -> None:
    """Drive one final-attempt error branch of ``method`` and assert its exc_info."""
    exc, needle = _branch_exc_and_needle(method, kind)
    client._http_client.post = AsyncMock(side_effect=exc)  # type: ignore[union-attr]
    logs.records.clear()
    with pytest.raises(EnrichmentUnavailableError):
        await _invoke(method, client, image, frames)
    _assert_exc_info(logs, logging.ERROR, needle, exc)
    if kind == "asyncio_timeout" and timeout_delays is not None:
        # the guard must have been armed with the shipped sum, not None
        assert explicit_timeout(method) in timeout_delays, (
            f"asyncio.timeout armed with {timeout_delays!r}, want {explicit_timeout(method)}"
        )


# =============================================================================
# Construction-time timeouts (client:879-890, 921-928)
# =============================================================================


class TestConstructionTimeouts:
    """``self._timeout`` / ``self._health_timeout`` field values and the ``timeout=``
    kwargs handed to the two ``httpx.AsyncClient`` constructors."""

    async def test_main_timeout_fields(self, client: EnrichmentClient) -> None:
        # client:879-884 — connect/pool = ai_connect_timeout, read/write = enrichment_read_timeout
        t = client._timeout
        assert isinstance(t, httpx.Timeout)
        assert (t.connect, t.read, t.write, t.pool) == (_CONNECT, _READ, _READ, _CONNECT)

    async def test_health_timeout_fields(self, client: EnrichmentClient) -> None:
        # client:885-890 — all four fields = ai_health_timeout
        t = client._health_timeout
        assert isinstance(t, httpx.Timeout)
        assert (t.connect, t.read, t.write, t.pool) == (_HEALTH, _HEALTH, _HEALTH, _HEALTH)

    async def test_main_async_client_gets_main_timeout(self, client: EnrichmentClient) -> None:
        # client:921-924 — timeout=self._timeout (mutants: timeout=None / kwarg deleted)
        kwargs = client.ctor_calls[0]  # type: ignore[attr-defined]
        assert set(kwargs) == {"args", "timeout", "limits"}
        t = kwargs["timeout"]
        assert isinstance(t, httpx.Timeout)
        assert (t.connect, t.read, t.write, t.pool) == (_CONNECT, _READ, _READ, _CONNECT)
        assert t is client._timeout

    async def test_health_async_client_gets_health_timeout(self, client: EnrichmentClient) -> None:
        # client:925-928 — timeout=self._health_timeout
        kwargs = client.ctor_calls[1]  # type: ignore[attr-defined]
        assert set(kwargs) == {"args", "timeout", "limits"}
        t = kwargs["timeout"]
        assert isinstance(t, httpx.Timeout)
        assert (t.connect, t.read, t.write, t.pool) == (_HEALTH, _HEALTH, _HEALTH, _HEALTH)
        assert t is client._health_timeout

    async def test_fields_with_shipped_default_settings(self) -> None:
        """Same field assertions at the SHIPPED defaults (config.py:1042/1048/1088)."""
        settings = _settings(connect=_D_CONNECT, read=_D_READ, health=_D_HEALTH)
        with (
            patch(
                "backend.services.enrichment_client.get_settings",
                return_value=settings,
                autospec=True,
            ),
            patch(
                "httpx.AsyncClient",
                side_effect=[AsyncMock(), AsyncMock()],  # exactly two constructions
                autospec=True,
            ),
        ):
            c = EnrichmentClient()
        assert (c._timeout.connect, c._timeout.read, c._timeout.write, c._timeout.pool) == (
            _D_CONNECT,
            _D_READ,
            _D_READ,
            _D_CONNECT,
        )
        assert (
            c._health_timeout.connect,
            c._health_timeout.read,
            c._health_timeout.write,
            c._health_timeout.pool,
        ) == (_D_HEALTH, _D_HEALTH, _D_HEALTH, _D_HEALTH)


# =============================================================================
# Request kwargs at each client-call site — one test per site
# =============================================================================


class TestRequestKwargs:
    """Positional URL + exact ``headers=`` / ``json=`` / ``params=`` / ``timeout=``."""

    async def test_classify_vehicle_kwargs(
        self, client: EnrichmentClient, sample_image: Image.Image, headers: dict[str, str]
    ) -> None:
        # client:1219-1223; endpoint literal client:1191
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK["vehicle"])
        )
        await client.classify_vehicle(sample_image)
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        _assert_request(
            call,
            url=f"{_BASE_URL}/vehicle-classify",
            json={"image": _b64(client, sample_image)},
            headers=dict(headers),
        )

    async def test_classify_pet_kwargs(
        self, client: EnrichmentClient, sample_image: Image.Image, headers: dict[str, str]
    ) -> None:
        # client:1410-1414; endpoint literal client:1382
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK["pet"])
        )
        await client.classify_pet(sample_image)
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        _assert_request(
            call,
            url=f"{_BASE_URL}/pet-classify",
            json={"image": _b64(client, sample_image)},
            headers=dict(headers),
        )

    async def test_classify_clothing_kwargs(
        self, client: EnrichmentClient, sample_image: Image.Image, headers: dict[str, str]
    ) -> None:
        # client:1599-1603; endpoint literal client:1571
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK["clothing"])
        )
        await client.classify_clothing(sample_image)
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        _assert_request(
            call,
            url=f"{_BASE_URL}/clothing-classify",
            json={"image": _b64(client, sample_image)},
            headers=dict(headers),
        )

    async def test_estimate_depth_kwargs(
        self, client: EnrichmentClient, sample_image: Image.Image, headers: dict[str, str]
    ) -> None:
        # client:1789-1793; endpoint literal client:1763
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK["depth"])
        )
        await client.estimate_depth(sample_image)
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        _assert_request(
            call,
            url=f"{_BASE_URL}/depth-estimate",
            json={"image": _b64(client, sample_image)},
            headers=dict(headers),
        )

    async def test_estimate_object_distance_kwargs(
        self, client: EnrichmentClient, sample_image: Image.Image, headers: dict[str, str]
    ) -> None:
        # client:2016-2020; payload client:2000-2004; endpoint literal client:1959
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK["distance"])
        )
        await client.estimate_object_distance(sample_image, _BBOX)
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        _assert_request(
            call,
            url=f"{_BASE_URL}/object-distance",
            json={"image": _b64(client, sample_image), "bbox": _BBOX_LIST, "method": "center"},
            headers=dict(headers),
        )

    async def test_analyze_pose_kwargs(
        self, client: EnrichmentClient, sample_image: Image.Image, headers: dict[str, str]
    ) -> None:
        # client:2213-2217; payload client:2196-2199 (min_confidence default 0.3,
        # client:2147); endpoint literal client:2182
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK["pose"])
        )
        await client.analyze_pose(sample_image)
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        _assert_request(
            call,
            url=f"{_BASE_URL}/pose-analyze",
            json={"image": _b64(client, sample_image), "min_confidence": 0.3},
            headers=dict(headers),
        )

    async def test_classify_action_kwargs(
        self, client: EnrichmentClient, sample_frames: list[Image.Image], headers: dict[str, str]
    ) -> None:
        # client:2429-2434 — the only call site that also passes timeout=
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK["action"])
        )
        await client.classify_action(sample_frames)
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        assert "timeout" in call.kwargs, "timeout= kwarg deleted at client:2433"
        _assert_request(
            call,
            url=f"{_BASE_URL}/action-classify",
            json={"frames": [_b64(client, f) for f in sample_frames]},
            headers=dict(headers),
            timeout=call.kwargs["timeout"],
        )

    async def test_classify_action_request_timeout_fields(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """FIELDS of the internally-built httpx.Timeout (client:2412-2417).

        connect/write/pool are copied off ``self._timeout`` (client:2413/2415/2416)
        while ``read`` is the 60.0 literal at client:2396 — the discriminating
        settings (_READ=42.0) make that distinction observable.
        """
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK["action"])
        )
        await client.classify_action(sample_frames)
        t = client._http_client.post.call_args.kwargs["timeout"]  # type: ignore[union-attr]
        assert isinstance(t, httpx.Timeout), "action_timeout mutated away from httpx.Timeout"
        assert (t.connect, t.read, t.write, t.pool) == (_CONNECT, _ACTION_READ, _READ, _CONNECT)

    async def test_enrich_detection_kwargs(
        self,
        client: EnrichmentClient,
        headers: dict[str, str],
        timeout_delays: list[float | None],
    ) -> None:
        # client:3188-3192; payload client:3165-3176; endpoint literal client:3158
        raw = b"\x89PNG-rax-test-bytes"
        frame = b"frame-one"
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_ENRICH_OK)
        )
        await client.enrich_detection(
            raw,
            "person",
            (1.0, 2.0, 3.0, 4.0),
            frames=[frame],
            options={"face_visible": True},
        )
        # client:3180/3187 — guard armed with enrichment_read_timeout + ai_connect_timeout
        assert _READ + _CONNECT in timeout_delays, (
            f"asyncio.timeout armed with {timeout_delays!r}, want {_READ + _CONNECT}"
        )
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        _assert_request(
            call,
            url=f"{_BASE_URL}/enrich",
            json={
                "image": base64.b64encode(raw).decode("utf-8"),
                "detection_type": "person",
                "bbox": {"x1": 1.0, "y1": 2.0, "x2": 3.0, "y2": 4.0},
                "frames": [base64.b64encode(frame).decode("utf-8")],
                "options": {"face_visible": True},
            },
            headers=dict(headers),
        )

    async def test_check_health_kwargs(
        self, client: EnrichmentClient, headers: dict[str, str]
    ) -> None:
        # client:1103-1106 — health client .get(), headers only
        client._health_http_client.get = AsyncMock(  # type: ignore[union-attr]
            return_value=_response({"status": "healthy"})
        )
        await client.check_health()
        call = client._health_http_client.get.call_args  # type: ignore[union-attr]
        _assert_request(call, url=f"{_BASE_URL}/health", headers=dict(headers))

    async def test_get_model_status_kwargs(
        self, client: EnrichmentClient, headers: dict[str, str]
    ) -> None:
        # client:3261-3264
        client._http_client.get = AsyncMock(  # type: ignore[union-attr]
            return_value=_response({"loaded_models": []})
        )
        await client.get_model_status()
        call = client._http_client.get.call_args  # type: ignore[union-attr]
        _assert_request(call, url=f"{_BASE_URL}/models/status", headers=dict(headers))

    async def test_preload_model_kwargs(
        self, client: EnrichmentClient, headers: dict[str, str]
    ) -> None:
        # client:3291-3295 — params= + headers= (no json)
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response({"ok": True}, status_code=200)
        )
        assert await client.preload_model("pose") is True
        call = client._http_client.post.call_args  # type: ignore[union-attr]
        _assert_request(
            call,
            url=f"{_BASE_URL}/models/preload",
            params={"model_name": "pose"},
            headers=dict(headers),
        )


# =============================================================================
# exc_info= sites — one test per site
# =============================================================================


class TestClientErrorExcInfo:
    """4xx branch: ``logger.error(..., exc_info=True)`` immediately before ``return None``."""

    @pytest.mark.parametrize("method", _METHODS)
    async def test_client_error_has_exc_info(
        self,
        method: str,
        client: EnrichmentClient,
        sample_image: Image.Image,
        sample_frames: list[Image.Image],
        logs: _Recorder,
    ) -> None:
        exc = _status_error(400)
        client._http_client.post = AsyncMock(side_effect=exc)  # type: ignore[union-attr]
        logs.records.clear()
        assert await _invoke(method, client, sample_image, sample_frames) is None
        _assert_exc_info(logs, logging.ERROR, "Enrichment returned client error: 400", exc)


class TestServerErrorExcInfo:
    """Final 5xx attempt (client:1272-1277 and per-endpoint twins)."""

    @pytest.mark.parametrize("method", _METHODS)
    async def test_server_error_has_exc_info(
        self,
        method: str,
        client: EnrichmentClient,
        sample_image: Image.Image,
        sample_frames: list[Image.Image],
        logs: _Recorder,
    ) -> None:
        await _final_branch(client, method, "server_error", logs, sample_image, sample_frames)


class TestConnectErrorExcInfo:
    """Final ConnectError attempt (client:1297-1301 and twins)."""

    @pytest.mark.parametrize("method", _METHODS)
    async def test_connect_error_has_exc_info(
        self,
        method: str,
        client: EnrichmentClient,
        sample_image: Image.Image,
        sample_frames: list[Image.Image],
        logs: _Recorder,
    ) -> None:
        await _final_branch(client, method, "connect_error", logs, sample_image, sample_frames)


class TestAsyncioTimeoutExcInfo:
    """Final ``asyncio.timeout()`` attempt (client:1320-1325 and twins).

    Also asserts the guard was armed with ``explicit_timeout`` (not ``None``), via
    the ``timeout_delays`` spy.
    """

    @pytest.mark.parametrize("method", _METHODS)
    async def test_asyncio_timeout_has_exc_info(
        self,
        method: str,
        client: EnrichmentClient,
        sample_image: Image.Image,
        sample_frames: list[Image.Image],
        logs: _Recorder,
        timeout_delays: list[float | None],
    ) -> None:
        await _final_branch(
            client, method, "asyncio_timeout", logs, sample_image, sample_frames, timeout_delays
        )


class TestUnexpectedErrorExcInfo:
    """Generic-Exception branch (client:1332-1336 and twins)."""

    @pytest.mark.parametrize("method", _METHODS)
    async def test_unexpected_error_has_exc_info(
        self,
        method: str,
        client: EnrichmentClient,
        sample_image: Image.Image,
        sample_frames: list[Image.Image],
        logs: _Recorder,
    ) -> None:
        await _final_branch(client, method, "unexpected", logs, sample_image, sample_frames)


class TestHealthCheckExcInfo:
    """check_health's three handlers (client:1113, 1121, 1129-1132)."""

    async def test_connect_error_has_exc_info(
        self, client: EnrichmentClient, logs: _Recorder
    ) -> None:
        exc: BaseException = httpx.ConnectError("refused")
        client._health_http_client.get = AsyncMock(side_effect=exc)  # type: ignore[union-attr]
        logs.records.clear()
        result = await client.check_health()
        assert result["status"] == "unavailable"
        _assert_exc_info(logs, logging.WARNING, "Enrichment health check failed:", exc)

    async def test_error_status_has_exc_info(
        self, client: EnrichmentClient, logs: _Recorder
    ) -> None:
        exc = _status_error(503)
        client._health_http_client.get = AsyncMock(side_effect=exc)  # type: ignore[union-attr]
        logs.records.clear()
        result = await client.check_health()
        assert result["status"] == "error"
        _assert_exc_info(
            logs, logging.WARNING, "Enrichment health check returned error status:", exc
        )

    async def test_unexpected_error_has_exc_info(
        self, client: EnrichmentClient, logs: _Recorder
    ) -> None:
        exc: BaseException = RuntimeError("weird")
        client._health_http_client.get = AsyncMock(side_effect=exc)  # type: ignore[union-attr]
        logs.records.clear()
        result = await client.check_health()
        assert result["status"] == "error"
        _assert_exc_info(
            logs, logging.ERROR, "Unexpected error during Enrichment health check:", exc
        )


# =============================================================================
# Contrast: sites that ship WITHOUT exc_info stay exc_info-free
# =============================================================================


class TestSendDebugRecordsHaveNoExcInfo:
    """The ``Sending ...`` debug calls (client:1199, 1390, 1579, 1771, 1994, 2190,
    2399) pass no ``exc_info`` — pinned so an exc_info-introducing mutant cannot
    hide behind the positive assertions above."""

    @pytest.mark.parametrize("method", _METHODS)
    async def test_debug_send_record_has_no_exc_info(
        self,
        method: str,
        client: EnrichmentClient,
        sample_image: Image.Image,
        sample_frames: list[Image.Image],
        logs: _Recorder,
    ) -> None:
        needle = _LABEL[method][2]
        client._http_client.post = AsyncMock(  # type: ignore[union-attr]
            return_value=_response(_OK[method])
        )
        logs.records.clear()
        await _invoke(method, client, sample_image, sample_frames)
        rec = _only(logs, logging.DEBUG, needle)
        assert rec.exc_info is None
