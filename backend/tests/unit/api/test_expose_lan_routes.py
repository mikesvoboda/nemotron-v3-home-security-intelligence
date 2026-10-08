"""The EXPOSE_LAN gate over every mounted route (B1.5; OD-12; ISS-029).

The tests walk the real application's route table, so a route added later is
covered without editing this file.

- ``EXPOSE_LAN=true``: every route outside the gate's open paths refuses an
  unauthenticated request through the real application: HTTP ``401``, and a
  WebSocket closed with ``4001``. The gate answers before routing, so no
  handler runs.
- ``EXPOSE_LAN`` unset: every route's request reaches its endpoint, as before
  B1.5. The application's own middleware stack wraps a stub endpoint, so no
  handler touches a database.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from fastapi.routing import iter_route_contexts
from starlette.responses import PlainTextResponse
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from backend.api.middleware.auth import OPEN_PATHS, AuthMiddleware
from backend.api.middleware.setup_guard import SetupGuardMiddleware
from backend.core.config import get_settings
from backend.main import app

pytestmark = pytest.mark.unit

REFUSAL_BODY = {"detail": "Authentication required"}
WS_REFUSAL_CODE = 4001
REFUSED = "refused"
REACHED = "reached"
_PATH_PARAM = re.compile(r"\{[^}]+\}")
_BODY_METHODS = {"POST", "PUT", "PATCH"}


def _mounted_routes() -> list[tuple[str, str]]:
    """(method, concrete path) for every mounted route; ``WS`` for a WebSocket."""
    routes: list[tuple[str, str]] = []
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        path = _PATH_PARAM.sub("1", context.path_format or route.path_format)
        if isinstance(route, WebSocketRoute):
            routes.append(("WS", path))
        else:
            routes.extend((method, path) for method in sorted(context.methods or ()))
    return routes


MOUNTED = _mounted_routes()


def _send(client: TestClient, method: str, path: str) -> str:
    """Send one unauthenticated request and name its outcome.

    ``refused`` is the gate's answer (HTTP 401 with its body, or a WebSocket
    closed with 4001), ``reached`` is the stub endpoint's; anything else is
    described for the failure message.
    """
    if method == "WS":
        try:
            with client.websocket_connect(path) as websocket:
                return websocket.receive_text()
        except WebSocketDisconnect as exc:
            return REFUSED if exc.code == WS_REFUSAL_CODE else f"closed {exc.code}"
    response = client.request(method, path, json={} if method in _BODY_METHODS else None)
    bodiless = method == "HEAD"
    body = response.json() if response.text.startswith("{") else response.text
    if response.status_code == 401 and (bodiless or body == REFUSAL_BODY):
        return REFUSED
    if response.status_code == 200 and (bodiless or body == REACHED):
        return REACHED
    return f"{response.status_code} {response.text[:80]}"


async def _endpoint(scope: Scope, receive: Receive, send: Send) -> None:
    """Stands in for every route handler."""
    if scope["type"] == "websocket":
        websocket = WebSocket(scope, receive, send)
        await websocket.accept()
        await websocket.send_text(REACHED)
        await websocket.close()
        return
    await PlainTextResponse(REACHED)(scope, receive, send)


def _app_middleware_around_stub() -> ASGIApp:
    """The application's own middleware, in its own order, around the stub endpoint."""
    stack: ASGIApp = _endpoint
    for middleware in reversed(app.user_middleware):
        stack = middleware.cls(stack, *middleware.args, **middleware.kwargs)

    async def _as_the_application(scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = app  # as Starlette.__call__ sets it; middleware reads it
        await stack(scope, receive, send)

    return _as_the_application


@pytest.fixture
def setup_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first admin exists: the state in which today's API is open."""

    async def _complete(_self: SetupGuardMiddleware) -> bool:
        return True

    monkeypatch.setattr(SetupGuardMiddleware, "_check_setup_complete", _complete)


@pytest.fixture
def exposed(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("EXPOSE_LAN", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def loopback(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("EXPOSE_LAN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_the_route_table_is_enumerated() -> None:
    """The walk sees HTTP and WebSocket routes, with and without the /api prefix."""
    assert ("GET", "/api/events") in MOUNTED
    assert ("WS", "/ws/events") in MOUNTED
    assert ("GET", "/system/detectors") in MOUNTED
    assert len(MOUNTED) > 400


@pytest.mark.timeout(30)  # ~480 requests; the default 5 s is tight on a busy CI worker
def test_exposed_every_route_refuses_an_unauthenticated_request(exposed: None) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    not_refused = [
        (method, path, outcome)
        for method, path in MOUNTED
        if path not in OPEN_PATHS and (outcome := _send(client, method, path)) != REFUSED
    ]
    assert not_refused == []


@pytest.mark.timeout(30)  # ~480 requests; the default 5 s is tight on a busy CI worker
def test_exposed_open_paths_reach_their_endpoint(exposed: None, setup_complete: None) -> None:
    client = TestClient(_app_middleware_around_stub())
    blocked = [
        (method, path, outcome)
        for method, path in MOUNTED
        if path in OPEN_PATHS and (outcome := _send(client, method, path)) != REACHED
    ]
    assert blocked == []


@pytest.mark.timeout(30)  # ~480 requests; the default 5 s is tight on a busy CI worker
def test_loopback_every_route_reaches_its_endpoint(loopback: None, setup_complete: None) -> None:
    """With EXPOSE_LAN unset nothing is refused for want of a credential."""
    client = TestClient(_app_middleware_around_stub())
    blocked = [
        (method, path, outcome)
        for method, path in MOUNTED
        if (outcome := _send(client, method, path)) != REACHED
    ]
    assert blocked == []


def test_every_open_path_is_a_mounted_route() -> None:
    """The allowlist names real routes, so it cannot quietly outlive one."""
    unmounted = OPEN_PATHS - {path for _method, path in MOUNTED}
    assert unmounted == set()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/events"),
        ("GET", "/api/media/cameras/front_door/snapshot.jpg"),
        ("GET", "/api/known-persons"),
        ("GET", "/api/household/members"),
        ("POST", "/api/notification/test"),
        ("WS", "/ws/events"),
    ],
)
def test_exposed_iss_029_matrix_is_refused(exposed: None, method: str, path: str) -> None:
    """The unauthenticated-request matrix ISS-029's acceptance names."""
    client = TestClient(app, raise_server_exceptions=False)
    assert _send(client, method, path) == REFUSED


def test_the_gate_is_the_outermost_middleware() -> None:
    """Nothing answers before the gate.

    IdempotencyMiddleware replays a cached response for a repeated
    Idempotency-Key without consulting auth, so it must sit inside the gate.
    Starlette runs ``user_middleware[0]`` first.
    """
    assert app.user_middleware[0].cls is AuthMiddleware
