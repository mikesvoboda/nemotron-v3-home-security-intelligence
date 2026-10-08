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
from backend.services.session_service import SessionService

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
    monkeypatch.delenv("EXPOSE_LAN", raising=False)
    get_settings.cache_clear()
    yield


async def _reached(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("reached")


async def _reached_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text("reached")
    await websocket.close()


def _client() -> TestClient:
    inner = Starlette(
        routes=[
            Route("/{path:path}", _reached, methods=["GET", "POST", "OPTIONS"]),
            WebSocketRoute("/{path:path}", _reached_ws),
        ]
    )
    return TestClient(AuthMiddleware(inner))


def _ws(client: TestClient, path: str, **kwargs: object) -> str | int:
    """``reached`` when the handshake passed the gate, else the close code."""
    try:
        with client.websocket_connect(path, **kwargs) as websocket:
            return websocket.receive_text()
    except WebSocketDisconnect as exc:
        return exc.code


class TestGateOffOnLoopback:
    def test_http_without_credential_passes(self, loopback: None) -> None:
        response = _client().get("/api/events")
        assert response.status_code == 200
        assert response.text == "reached"

    def test_websocket_without_credential_passes(self, loopback: None) -> None:
        assert _ws(_client(), "/ws/events") == "reached"


class TestGateRefusesWithoutCredential:
    @pytest.mark.parametrize("path", ["/api/events", "/system/detectors", "/no/such/route", "/"])
    def test_http_is_refused_with_401(self, exposed: None, path: str) -> None:
        response = _client().get(path)
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required"}

    def test_post_is_refused(self, exposed: None) -> None:
        response = _client().post("/api/notification/test", json={"channel": "webhook"})
        assert response.status_code == 401

    def test_websocket_is_closed_with_4001(self, exposed: None) -> None:
        assert _ws(_client(), "/ws/events") == 4001

    def test_lifespan_passes_through(self, exposed: None) -> None:
        with _client() as client:
            assert client.get("/api/auth/login").status_code == 200


class TestOpenPaths:
    def test_open_paths_are_the_documented_allowlist(self) -> None:
        """Health probes, Prometheus targets, and getting or clearing a session."""
        documented = {
            "/health",
            "/ready",
            "/api/system/health",
            "/api/system/health/ready",
            "/api/metrics",
            "/api/system/gpu",
            "/api/system/stats",
            "/api/system/telemetry",
            "/api/auth/setup-status",
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/logout",
        }
        assert documented == OPEN_PATHS

    @pytest.mark.parametrize("path", sorted(OPEN_PATHS))
    def test_open_path_passes_without_credential(self, exposed: None, path: str) -> None:
        assert _client().get(path).text == "reached"

    @pytest.mark.parametrize(
        "path",
        ["/api/auth/login/", "/api/auth/login/x", "/api/metricsx", "/api/system/health/full"],
    )
    def test_open_paths_match_exactly(self, exposed: None, path: str) -> None:
        assert _client().get(path).status_code == 401


class TestApiKey:
    def test_header_key_passes(self, exposed: None) -> None:
        assert _client().get("/api/events", headers={"X-API-Key": VALID_KEY}).text == "reached"

    def test_wrong_header_key_is_refused(self, exposed: None) -> None:
        response = _client().get("/api/events", headers={"X-API-Key": "wrong-key-1234567"})
        assert response.status_code == 401

    def test_http_query_key_is_refused(self, exposed: None) -> None:
        """Over HTTP a key travels in a header, never in a URL that logs record."""
        assert _client().get(f"/api/events?api_key={VALID_KEY}").status_code == 401

    def test_no_configured_keys_accepts_none(
        self, exposed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("API_KEYS", "[]")
        get_settings.cache_clear()
        response = _client().get("/api/events", headers={"X-API-Key": VALID_KEY})
        assert response.status_code == 401

    def test_websocket_query_key_passes(self, exposed: None) -> None:
        assert _ws(_client(), f"/ws/events?api_key={VALID_KEY}") == "reached"

    def test_websocket_subprotocol_key_passes(self, exposed: None) -> None:
        assert _ws(_client(), "/ws/events", subprotocols=[f"api-key.{VALID_KEY}"]) == "reached"

    def test_websocket_wrong_key_is_closed(self, exposed: None) -> None:
        assert _ws(_client(), "/ws/events?api_key=wrong-key-1234567") == 4001


class TestSessionCookie:
    @pytest.mark.asyncio
    async def test_login_session_passes_http(
        self, exposed: None, session_store: _SessionStore
    ) -> None:
        session_id = await _login(session_store)
        response = _client().get("/api/events", headers={"Cookie": f"session_id={session_id}"})
        assert response.text == "reached"

    @pytest.mark.asyncio
    async def test_login_session_passes_websocket(
        self, exposed: None, session_store: _SessionStore
    ) -> None:
        session_id = await _login(session_store)
        headers = {"Cookie": f"session_id={session_id}"}
        assert _ws(_client(), "/ws/events", headers=headers) == "reached"

    def test_unknown_session_is_refused(self, exposed: None, session_store: _SessionStore) -> None:
        response = _client().get("/api/events", headers={"Cookie": "session_id=forged"})
        assert response.status_code == 401

    def test_unknown_session_websocket_is_closed(
        self, exposed: None, session_store: _SessionStore
    ) -> None:
        assert _ws(_client(), "/ws/events", headers={"Cookie": "session_id=forged"}) == 4001

    def test_redis_unavailable_refuses(
        self, exposed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _use_store(monkeypatch, None)
        response = _client().get("/api/events", headers={"Cookie": "session_id=any"})
        assert response.status_code == 401

    def test_redis_error_refuses(self, exposed: None, monkeypatch: pytest.MonkeyPatch) -> None:
        _use_store(monkeypatch, _BrokenStore())
        response = _client().get("/api/events", headers={"Cookie": "session_id=any"})
        assert response.status_code == 401


class TestCorsPreflight:
    def test_preflight_passes(self, exposed: None) -> None:
        response = _client().options(
            "/api/events",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        assert response.text == "reached"

    def test_plain_options_is_refused(self, exposed: None) -> None:
        assert _client().options("/api/events").status_code == 401


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
    async def test_api_key_is_named_api_key(
        self, exposed: None, session_store: _SessionStore
    ) -> None:
        assert await authenticated_principal(_request({"X-API-Key": VALID_KEY})) == "api-key"

    @pytest.mark.asyncio
    async def test_no_credential_is_none(self, session_store: _SessionStore) -> None:
        assert await authenticated_principal(_request({})) is None

    @pytest.mark.asyncio
    async def test_unknown_session_is_none(self, session_store: _SessionStore) -> None:
        assert await authenticated_principal(_request({"Cookie": "session_id=forged"})) is None
