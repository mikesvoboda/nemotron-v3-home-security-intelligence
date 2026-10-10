"""Unit tests for backend/api/middleware/auth.py.

- ``AuthMiddleware``, the EXPOSE_LAN gate (B1.5, OD-12): with EXPOSE_LAN unset
  it passes every request; set, it refuses any HTTP request or WebSocket
  handshake without a valid credential, except the open paths. Credentials are
  the login session cookie and the configured API keys.
- ``authenticated_principal``: who presented the credential, for audit rows.
- ``validate_websocket_api_key``: the WebSocket routes' API-key check and its
  security logging.
"""

import os
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import WebSocket
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api.middleware.auth import (
    OPEN_PATHS,
    AuthMiddleware,
    authenticated_principal,
    validate_websocket_api_key,
)
from backend.core.config import get_settings
from backend.services.session_service import SESSION_COOKIE_NAME, SessionService

VALID_KEY = "test-valid-key-12345"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear settings cache before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = MagicMock(spec=WebSocket)
    ws.url = MagicMock()
    ws.url.path = "/api/events/stream"
    ws.query_params = {}
    ws.headers = {}
    ws.client = MagicMock()
    ws.client.host = "10.0.0.50"
    return ws


@pytest.fixture
def enable_api_key_auth():
    """Enable API key authentication with a test key."""
    os.environ["API_KEY_ENABLED"] = "true"  # pragma: allowlist secret
    os.environ["API_KEYS"] = '["test-valid-key-12345"]'  # pragma: allowlist secret
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )
    get_settings.cache_clear()
    yield
    os.environ.pop("API_KEY_ENABLED", None)
    os.environ.pop("API_KEYS", None)
    get_settings.cache_clear()


class TestWebSocketAuthLogging:
    """Tests for WebSocket authentication failure logging."""

    @pytest.mark.asyncio
    async def test_websocket_missing_key_logs_warning(self, mock_websocket, enable_api_key_auth):
        """When WebSocket has no API key, a warning should be logged."""
        with patch("backend.api.middleware.auth.logger", autospec=True) as mock_logger:
            result = await validate_websocket_api_key(mock_websocket)

            assert result is False

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args

            # Verify log message
            assert "WebSocket authentication attempt without API key" in call_args[0][0]

            # Verify extra fields
            extra = call_args[1]["extra"]
            assert extra["path"] == "/api/events/stream"
            assert extra["security_event"] is True
            assert extra["event_type"] == "ws_auth_missing_key"
            # IP should be masked (10.xxx.xxx.xxx)
            assert extra["client_ip"] == "10.xxx.xxx.xxx"

    @pytest.mark.asyncio
    async def test_websocket_invalid_key_logs_warning(self, mock_websocket, enable_api_key_auth):
        """When WebSocket has invalid API key, a warning should be logged."""
        mock_websocket.query_params = {"api_key": "invalid-ws-key"}  # pragma: allowlist secret

        with patch("backend.api.middleware.auth.logger", autospec=True) as mock_logger:
            result = await validate_websocket_api_key(mock_websocket)

            assert result is False

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args

            # Verify log message
            assert "WebSocket authentication attempt with invalid API key" in call_args[0][0]

            # Verify extra fields
            extra = call_args[1]["extra"]
            assert extra["path"] == "/api/events/stream"
            assert extra["security_event"] is True
            assert extra["event_type"] == "ws_auth_invalid_key"

    @pytest.mark.asyncio
    async def test_websocket_valid_key_no_warning(self, mock_websocket, enable_api_key_auth):
        """When WebSocket has valid API key, no warning should be logged."""
        mock_websocket.query_params = {
            "api_key": "test-valid-key-12345"  # pragma: allowlist secret
        }

        with patch("backend.api.middleware.auth.logger", autospec=True) as mock_logger:
            result = await validate_websocket_api_key(mock_websocket)

            assert result is True
            mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_handles_no_client(self, enable_api_key_auth):
        """When WebSocket has no client info, should log 'unknown'."""
        ws = MagicMock(spec=WebSocket)
        ws.url = MagicMock()
        ws.url.path = "/api/events/stream"
        ws.query_params = {}
        ws.headers = {}
        ws.client = None  # No client info

        with patch("backend.api.middleware.auth.logger", autospec=True) as mock_logger:
            result = await validate_websocket_api_key(ws)

            assert result is False
            extra = mock_logger.warning.call_args[1]["extra"]
            assert extra["client_ip"] == "unknown"


# =============================================================================
# AuthMiddleware: the EXPOSE_LAN gate
# =============================================================================


class _SessionStore:
    """In-memory stand-in for Redis: the two calls SessionService makes."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


class _BrokenStore:
    async def get(self, key: str) -> str | None:
        raise ConnectionError("redis down")


def _use_store(monkeypatch: pytest.MonkeyPatch, store: object) -> None:
    async def _redis() -> object:
        return store

    monkeypatch.setattr("backend.api.middleware.auth.get_redis_optional", _redis)


@pytest.fixture
def session_store(monkeypatch: pytest.MonkeyPatch) -> _SessionStore:
    store = _SessionStore()
    _use_store(monkeypatch, store)
    return store


async def _login(store: _SessionStore, username: str = "admin") -> str:
    """A session exactly as POST /api/auth/login creates it."""
    return await SessionService(store).create_session(
        user_id="user-1", session_data={"username": username, "is_admin": True}
    )


@pytest.fixture
def exposed(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("EXPOSE_LAN", "true")
    monkeypatch.setenv("API_KEYS", f'["{VALID_KEY}"]')
    get_settings.cache_clear()
    yield


@pytest.fixture
def loopback(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("EXPOSE_LAN", "false")  # outranks any .env a developer keeps
    get_settings.cache_clear()
    yield


async def _reached(request: Request) -> PlainTextResponse:
    """Answer ``reached``, with the Cache-Control a ``cache`` query parameter asks for."""
    cache = request.query_params.get("cache")
    return PlainTextResponse("reached", headers={"Cache-Control": cache} if cache else None)


async def _reached_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text("reached")
    await websocket.close()


def _client(client: tuple[str, int] = ("testclient", 50000)) -> TestClient:
    inner = Starlette(
        routes=[
            Route("/{path:path}", _reached, methods=["GET", "POST", "OPTIONS"]),
            WebSocketRoute("/{path:path}", _reached_ws),
        ]
    )
    return TestClient(AuthMiddleware(inner), client=client)


def _ws(client: TestClient, path: str, **kwargs: object) -> str | int:
    """``reached`` when the handshake passed the gate, else the close code."""
    try:
        with client.websocket_connect(path, **kwargs) as websocket:
            return websocket.receive_text()
    except WebSocketDisconnect as exc:
        return exc.code


class TestGateOffOnLoopback:
    @pytest.mark.usefixtures("loopback")
    def test_http_without_credential_passes(self) -> None:
        response = _client().get("/api/events")
        assert response.status_code == 200
        assert response.text == "reached"

    @pytest.mark.usefixtures("loopback")
    def test_websocket_without_credential_passes(self) -> None:
        assert _ws(_client(), "/ws/events") == "reached"


class TestGateRefusesWithoutCredential:
    @pytest.mark.parametrize("path", ["/api/events", "/system/detectors", "/no/such/route", "/"])
    @pytest.mark.usefixtures("exposed")
    def test_http_is_refused_with_401(self, path: str) -> None:
        response = _client().get(path)
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required"}

    @pytest.mark.usefixtures("exposed")
    def test_post_is_refused(self) -> None:
        response = _client().post("/api/notification/test", json={"channel": "webhook"})
        assert response.status_code == 401

    @pytest.mark.usefixtures("exposed")
    def test_websocket_is_closed_with_4001(self) -> None:
        assert _ws(_client(), "/ws/events") == 4001

    @pytest.mark.usefixtures("exposed")
    def test_lifespan_passes_through(self) -> None:
        with _client() as client:
            assert client.get("/api/auth/login").status_code == 200


class TestOpenPaths:
    def test_open_paths_are_the_documented_allowlist(self) -> None:
        """Health probes, first-run setup, and getting or clearing a session.

        Monitoring is not on it: the owner ruled it denied by default (UR-33).
        """
        documented = {
            "/health",
            "/ready",
            "/api/system/health",
            "/api/system/health/ready",
            "/api/auth/setup-status",
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/logout",
        }
        assert documented == OPEN_PATHS

    @pytest.mark.parametrize("path", sorted(OPEN_PATHS))
    @pytest.mark.usefixtures("exposed")
    def test_open_path_passes_without_credential(self, path: str) -> None:
        assert _client().get(path).text == "reached"

    @pytest.mark.parametrize(
        "path",
        ["/api/auth/login/", "/api/auth/login/x", "/api/auth/loginx", "/api/system/health/full"],
    )
    @pytest.mark.usefixtures("exposed")
    def test_open_paths_match_exactly(self, path: str) -> None:
        assert _client().get(path).status_code == 401


class TestApiKey:
    @pytest.mark.usefixtures("exposed")
    def test_header_key_passes(self) -> None:
        assert _client().get("/api/events", headers={"X-API-Key": VALID_KEY}).text == "reached"

    @pytest.mark.usefixtures("exposed")
    def test_wrong_header_key_is_refused(self) -> None:
        response = _client().get("/api/events", headers={"X-API-Key": "wrong-key-1234567"})
        assert response.status_code == 401

    @pytest.mark.usefixtures("exposed")
    def test_http_query_key_is_refused(self) -> None:
        """Over HTTP a key travels in a header, never in a URL that logs record."""
        assert _client().get(f"/api/events?api_key={VALID_KEY}").status_code == 401

    @pytest.mark.usefixtures("exposed")
    def test_no_configured_keys_accepts_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("API_KEYS", "[]")
        get_settings.cache_clear()
        response = _client().get("/api/events", headers={"X-API-Key": VALID_KEY})
        assert response.status_code == 401

    @pytest.mark.usefixtures("exposed")
    def test_websocket_query_key_passes(self) -> None:
        assert _ws(_client(), f"/ws/events?api_key={VALID_KEY}") == "reached"

    @pytest.mark.usefixtures("exposed")
    def test_websocket_subprotocol_key_passes(self) -> None:
        assert _ws(_client(), "/ws/events", subprotocols=[f"api-key.{VALID_KEY}"]) == "reached"

    @pytest.mark.usefixtures("exposed")
    def test_websocket_wrong_key_is_closed(self) -> None:
        assert _ws(_client(), "/ws/events?api_key=wrong-key-1234567") == 4001


class TestSessionCookie:
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("exposed")
    async def test_login_session_passes_http(self, session_store: _SessionStore) -> None:
        session_id = await _login(session_store)
        response = _client().get("/api/events", headers={"Cookie": f"session_id={session_id}"})
        assert response.text == "reached"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("exposed")
    async def test_login_session_passes_websocket(self, session_store: _SessionStore) -> None:
        session_id = await _login(session_store)
        headers = {"Cookie": f"session_id={session_id}"}
        assert _ws(_client(), "/ws/events", headers=headers) == "reached"

    @pytest.mark.usefixtures("exposed")
    def test_unknown_session_is_refused(self, session_store: _SessionStore) -> None:
        response = _client().get("/api/events", headers={"Cookie": "session_id=forged"})
        assert response.status_code == 401

    @pytest.mark.usefixtures("exposed")
    def test_unknown_session_websocket_is_closed(self, session_store: _SessionStore) -> None:
        assert _ws(_client(), "/ws/events", headers={"Cookie": "session_id=forged"}) == 4001

    @pytest.mark.usefixtures("exposed")
    def test_redis_unavailable_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use_store(monkeypatch, None)
        response = _client().get("/api/events", headers={"Cookie": "session_id=any"})
        assert response.status_code == 401

    @pytest.mark.usefixtures("exposed")
    def test_redis_error_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use_store(monkeypatch, _BrokenStore())
        response = _client().get("/api/events", headers={"Cookie": "session_id=any"})
        assert response.status_code == 401


# =============================================================================
# authenticate_websocket: route-level hybrid auth (R55 terminal-failure pin)
# =============================================================================


class _HybridSocket:
    """ASGI-faithful fake for authenticate_websocket: accept-after-close raises.

    A MagicMock can't guard the crash this pins — a mock's accept() never
    raises, so the pre-R55 fall-through looked green under one. Starlette
    raises RuntimeError on accept() after close(); this fake does too, so a
    regression that returns True for an already-closed socket fails loudly at
    whichever caller accepts next (the route does ``broadcaster.connect`` →
    accept — the exact live crash from the ruling-55 investigation).
    """

    def __init__(self, *, cookie: str | None, query: dict[str, str], first_message: str) -> None:
        self.cookies = {} if cookie is None else {SESSION_COOKIE_NAME: cookie}
        self.query_params = query
        self.headers: dict[str, str] = {}
        self.url = SimpleNamespace(path="/ws/events")
        # The key-leg refusal logs a masked client IP (auth.py reads
        # websocket.client.host); a MagicMock resolved this silently — the
        # fake must carry it explicitly or the refusal path AttributeErrors.
        self.client = SimpleNamespace(host="10.0.0.50")
        self._first_message = first_message
        self.accepts: list[str | None] = []
        self.closes: list[int] = []

    async def accept(self, subprotocol: str | None = None) -> None:
        if self.closes:
            raise RuntimeError("Cannot accept() after close()")
        self.accepts.append(subprotocol)

    async def close(self, code: int = 1000) -> None:
        self.closes.append(code)

    async def receive_text(self) -> str:
        return self._first_message


class TestInvalidCredentialCastsNoVote:
    """R55 round 2 (self-review finding 1): the HTTP gate's rule for sockets.

    A PRESENT-BUT-INVALID credential must not refuse a socket by itself —
    authenticated_principal() never lets a dead cookie refuse; here the dead
    cookie simply isn't a valid credential, so the pre-existing API-key
    hierarchy decides, exactly as for a client that never had a cookie. The
    round-1 build made every hybrid failure terminal, and that over-refused
    the single-user default (gate off, keys disabled, sockets open to all):
    one login + an aged-out Redis session = every socket 4001-forever, while
    a browser that never logged in kept working — /me is disabled in that
    mode, so nothing clears the cookie. These pins hold both halves: invalid
    credentials never refuse alone, and the key leg's refusal still closes
    exactly once (the accept-after-close crash stays structurally dead: no
    validation path touches accept/close anymore — the fake raises if one
    ever does, which a plain MagicMock could never catch).
    """

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("session_store", "enable_api_key_auth")
    async def test_stale_cookie_does_not_outvote_a_valid_query_key(self) -> None:
        from backend.api.middleware.auth import authenticate_websocket

        ws = _HybridSocket(
            cookie="session-that-expired",  # absent from the empty store
            query={"api_key": VALID_KEY},
            first_message="ping",  # never read now: no leg accepts, so none waits
        )
        assert await authenticate_websocket(ws) is True
        # The authenticator never touches the socket on success — the route's
        # broadcaster.connect() owns the accept.
        assert ws.accepts == []
        assert ws.closes == []

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("session_store", "enable_api_key_auth")
    async def test_stale_cookie_alone_is_refused_by_the_key_leg_closing_once(
        self, monkeypatch
    ) -> None:
        from backend.api.middleware.auth import authenticate_websocket

        monkeypatch.setenv(
            "JWT_SECRET", "test-jwt-secret-stale-refusal"
        )  # pragma: allowlist secret
        get_settings.cache_clear()
        ws = _HybridSocket(cookie="session-that-expired", query={}, first_message="ping")
        # No key offered and keys are enabled → the key-leg refusal, closing
        # exactly once (one accept, then the hybrid close code 4001 — no
        # second close, no close before an accept). Without JWT_SECRET the
        # same refusal closes 1008, the backward-compat code.
        assert await authenticate_websocket(ws) is False
        assert ws.accepts == [None]
        assert ws.closes == [4001]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("session_store")
    async def test_stale_cookie_on_single_user_box_is_served(self, monkeypatch) -> None:
        """The exact dead zone finding 1 measured: loopback box, keys OFF.

        Sockets are open to everyone here by design (the gate is off; the key
        leg skips when disabled) — a stale cookie must not change that. At
        base it didn't (dead cookie name); in the round-1 build it did, for
        up to the cookie's 24h. This test is that regression's pin.
        """
        from backend.api.middleware.auth import authenticate_websocket

        monkeypatch.delenv("API_KEY_ENABLED", raising=False)
        ws = _HybridSocket(cookie="session-that-expired", query={}, first_message="ping")
        assert await authenticate_websocket(ws) is True
        assert ws.accepts == []
        assert ws.closes == []  # and the route's accept() below can't raise

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("enable_api_key_auth")
    async def test_expired_token_does_not_outvote_a_valid_query_key(self, monkeypatch) -> None:
        from backend.api.middleware.auth import authenticate_websocket

        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-cast-no-vote")  # pragma: allowlist secret
        get_settings.cache_clear()
        ws = _HybridSocket(
            cookie=None,
            query={"token": "eyJhbGciOiJIUzI1NiJ9.garbage.sig", "api_key": VALID_KEY},
            first_message="ping",
        )
        # The ?token= leg cannot decode → casts no vote; the key serves.
        assert await authenticate_websocket(ws) is True
        assert ws.accepts == []
        assert ws.closes == []

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("enable_api_key_auth")
    async def test_query_key_without_cookie_is_still_served(self) -> None:
        from backend.api.middleware.auth import authenticate_websocket

        ws = _HybridSocket(cookie=None, query={"api_key": VALID_KEY}, first_message="ping")
        assert await authenticate_websocket(ws) is True
        assert ws.accepts == []  # the route accepts on success, not the authenticator
        assert ws.closes == []


class TestCorsPreflight:
    @pytest.mark.usefixtures("exposed")
    def test_preflight_passes(self) -> None:
        response = _client().options(
            "/api/events",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        assert response.text == "reached"

    @pytest.mark.usefixtures("exposed")
    def test_preflight_without_origin_is_refused(self) -> None:
        """CORSMiddleware hands an Origin-less preflight to the router, so the gate must not."""
        response = _client().options(
            "/api/events", headers={"Access-Control-Request-Method": "GET"}
        )
        assert response.status_code == 401

    @pytest.mark.usefixtures("exposed")
    def test_plain_options_is_refused(self) -> None:
        assert _client().options("/api/events").status_code == 401


class TestSharedCaches:
    """No shared cache (a tunnel, a CDN) may keep a response the gate authenticated."""

    @pytest.mark.parametrize(
        ("sent", "received"),
        [
            ("public, max-age=3600", "private, max-age=3600"),
            (None, "private"),
            ("no-store", "no-store"),
            ("private, max-age=60", "private, max-age=60"),
        ],
    )
    @pytest.mark.usefixtures("exposed")
    def test_authenticated_response_is_private(self, sent: str | None, received: str) -> None:
        query = f"?cache={sent}" if sent else ""
        response = _client().get(f"/api/media/x.jpg{query}", headers={"X-API-Key": VALID_KEY})
        assert response.headers["cache-control"] == received

    @pytest.mark.usefixtures("loopback")
    def test_loopback_leaves_cache_control_alone(self) -> None:
        response = _client().get("/api/media/x.jpg?cache=public, max-age=3600")
        assert response.headers["cache-control"] == "public, max-age=3600"


class TestRefusalLog:
    @pytest.mark.usefixtures("exposed")
    def test_refusal_is_a_security_event_with_the_client_ip_masked(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="backend.api.middleware.auth"):
            _client(client=("192.168.1.100", 50000)).get("/api/events")
        (record,) = [
            r for r in caplog.records if r.getMessage() == "Unauthenticated request refused"
        ]
        assert record.event_type == "auth_required"
        assert record.security_event is True
        assert record.path == "/api/events"
        assert record.client_ip == "192.xxx.xxx.xxx"


# =============================================================================
# authenticated_principal
# =============================================================================


def _request(headers: dict[str, str]) -> Request:
    raw = [(name.lower().encode(), value.encode()) for name, value in headers.items()]
    return Request(
        {"type": "http", "method": "POST", "path": "/", "headers": raw, "query_string": b""}
    )


class TestAuthenticatedPrincipal:
    @pytest.mark.asyncio
    async def test_session_names_its_user(self, session_store: _SessionStore) -> None:
        session_id = await _login(session_store, username="alice")
        assert (
            await authenticated_principal(_request({"Cookie": f"session_id={session_id}"}))
            == "alice"
        )

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("exposed")
    async def test_api_key_is_named_api_key(self, session_store: _SessionStore) -> None:
        assert await authenticated_principal(_request({"X-API-Key": VALID_KEY})) == "api-key"

    @pytest.mark.asyncio
    async def test_no_credential_is_none(self, session_store: _SessionStore) -> None:
        assert await authenticated_principal(_request({})) is None

    @pytest.mark.asyncio
    async def test_unknown_session_is_none(self, session_store: _SessionStore) -> None:
        assert await authenticated_principal(_request({"Cookie": "session_id=forged"})) is None
