"""Authentication: the EXPOSE_LAN gate, and the routes' API-key checks.

The routes' checks are ``require_api_key`` (B1.3, the inbound webhooks: always
on) and ``validate_websocket_api_key`` (the WebSocket routes, ``API_KEY_ENABLED``).

``AuthMiddleware`` is the gate OD-12 rules (B1.5). With ``EXPOSE_LAN`` unset it
passes every request, as before B1.5. With ``EXPOSE_LAN=true`` it refuses every
HTTP request and WebSocket handshake that presents no valid credential, whatever
its path, except ``OPEN_PATHS``.

A credential is either
- the ``session_id`` cookie ``POST /api/auth/login`` sets, looked up in Redis; or
- a key from ``settings.api_keys``: the ``X-API-Key`` header over HTTP, the
  ``api_key`` query parameter or an ``api-key.<key>`` subprotocol on a WebSocket.

When exposed, a response to an authenticated HTTP request is marked
``Cache-Control: private`` so no shared cache (a tunnel, a CDN) can store it.

The per-route guards (``verify_api_key``, ``require_admin_access``,
``get_current_admin_user``, ``WEBSOCKET_TOKEN``) still run after the gate.
"""

import hashlib
import hmac
from typing import Annotated

from fastapi import Header, HTTPException, WebSocket, status
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.api.dependencies import get_redis_optional
from backend.api.middleware import websocket_auth
from backend.core import get_settings
from backend.core.logging import get_logger, mask_ip
from backend.core.websocket.subprotocol import offered_key_subprotocol
from backend.services.session_service import SESSION_COOKIE_NAME, SessionService

logger = get_logger(__name__)

# R55 (ruling 55): the cookie name is ONE constant in session_service — the
# second definition here is deleted; every consumer (routes/auth.py, both
# socket paths, this gate) imports it.

# Reachable without a credential when EXPOSE_LAN=true. Exact paths, no prefixes.
# Monitoring is not here: it is denied by default like everything else (UR-33);
# O1.11 gives Prometheus, Alertmanager and Grafana a credential.
OPEN_PATHS: frozenset[str] = frozenset(
    {
        # container healthchecks and Prometheus probes
        "/health",
        "/ready",
        "/api/system/health",
        "/api/system/health/ready",
        # first-run setup (register answers 409 once a user exists) and the session
        "/api/auth/setup-status",
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/logout",
    }
)

API_KEY_PRINCIPAL = "api-key"  # the audit actor for a key holder  # pragma: allowlist secret
WS_CLOSE_AUTH_REQUIRED = 4001  # the auth-failure close code websocket_auth.py uses


def _hash_key(key: str) -> str:
    """Hash API key using SHA-256.

    Args:
        key: Plain text API key

    Returns:
        SHA-256 hash of the key
    """
    return hashlib.sha256(key.encode()).hexdigest()


def _get_valid_key_hashes() -> set[str]:
    """Get the set of valid API key hashes from settings.

    Returns:
        Set of SHA-256 hashes of valid API keys
    """
    settings = get_settings()
    # Support both SecretStr and str for api_keys
    hashes = set()
    for key in settings.api_keys:
        key_value = key.get_secret_value() if hasattr(key, "get_secret_value") else key
        hashes.add(_hash_key(str(key_value)))
    return hashes


def _validate_key_hash_constant_time(key_hash: str, valid_hashes: set[str]) -> bool:
    """Validate API key hash using constant-time comparison.

    Uses hmac.compare_digest to prevent timing attacks (OWASP A07:2021).
    Compares the key hash against all valid hashes using constant-time
    comparison to avoid leaking information about which keys are valid.

    Args:
        key_hash: SHA-256 hash of the API key to validate
        valid_hashes: Set of valid API key hashes

    Returns:
        True if the key hash matches any valid hash, False otherwise
    """
    return any(hmac.compare_digest(key_hash, valid_hash) for valid_hash in valid_hashes)


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    """Validate an API key against ``settings.api_keys``, unconditionally.

    The shared dependency the inbound-webhook routes use (B1.3, D3, UR-12).
    Unlike the two older copies in ``routes/dlq.py`` and ``routes/system.py``
    this one does **not** honour ``settings.api_key_enabled``: those two
    return early when the flag is off, and the shipped default is off
    (``config.py`` ``api_key_enabled=False``). A webhook dependency with the
    same branch would let every caller through unauthenticated — the exact
    hole D3 records — so this validates fail-closed: with no keys
    configured, every request is refused.

    Comparison is by SHA-256 digest with ``hmac.compare_digest``, reusing the
    module's helpers; the two older copies compare digests with ``in``, which
    leaks timing (OWASP A07:2021).

    Args:
        x_api_key: API key from the ``X-API-Key`` header.

    Returns:
        The validated key.

    Raises:
        HTTPException: 401 if the header is absent, or if the key is not in
            ``settings.api_keys``.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    if not _validate_key_hash_constant_time(_hash_key(x_api_key), _get_valid_key_hashes()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return x_api_key


async def validate_websocket_api_key(websocket: WebSocket) -> bool:
    """Validate API key for WebSocket connections.

    Checks if API key authentication is enabled and validates the key
    provided via query parameter or Sec-WebSocket-Protocol header.

    Args:
        websocket: WebSocket connection to validate

    Returns:
        True if authentication is disabled or key is valid, False otherwise
    """
    settings = get_settings()

    # Skip authentication if disabled
    if not settings.api_key_enabled:
        return True

    # Extract API key from query parameter
    api_key = websocket.query_params.get("api_key")

    # Fall back to Sec-WebSocket-Protocol header
    if not api_key:
        # The Sec-WebSocket-Protocol header can contain multiple protocols
        # We look for one that starts with "api-key." followed by the key
        protocols = websocket.headers.get("sec-websocket-protocol", "")
        for protocol in protocols.split(","):
            stripped_protocol = protocol.strip()
            if stripped_protocol.startswith("api-key."):
                api_key = stripped_protocol[8:]  # Extract key after "api-key."
                break

    # No API key provided
    if not api_key:
        logger.warning(
            "WebSocket authentication attempt without API key",
            extra={
                "path": str(websocket.url.path),
                "client_ip": mask_ip(websocket.client.host if websocket.client else "unknown"),
                "security_event": True,
                "event_type": "ws_auth_missing_key",
            },
        )
        return False

    # Validate the API key using constant-time comparison (OWASP A07:2021)
    key_hash = _hash_key(api_key)
    valid_hashes = _get_valid_key_hashes()
    is_valid = _validate_key_hash_constant_time(key_hash, valid_hashes)

    if not is_valid:
        logger.warning(
            "WebSocket authentication attempt with invalid API key",
            extra={
                "path": str(websocket.url.path),
                "client_ip": mask_ip(websocket.client.host if websocket.client else "unknown"),
                "security_event": True,
                "event_type": "ws_auth_invalid_key",
            },
        )

    return is_valid


async def authenticate_websocket(websocket: WebSocket) -> bool:
    """Authenticate a WebSocket connection using hybrid authentication.

    Supports multiple authentication methods in priority order:
    1. Cookie authentication (web UI clients)
    2. JWT token in query parameter (API/mobile clients)
    3. API key (existing functionality for backward compatibility)

    R55 round 2: an INVALID credential casts no vote and refuses nothing on
    its own — any one valid credential serves, exactly like the HTTP gate's
    authenticated_principal. A request whose present credentials all fail
    falls through to the API-key leg, which is the pre-existing hierarchy for
    a client with no cookie at all (keys disabled -> served: single-user
    mode is open by design; keys enabled and no valid key -> refused).

    On refusal the connection is first accepted and then closed with an
    appropriate code. This is required because in the WebSocket protocol,
    you cannot send a close frame without first completing the handshake.

    Note: Attempting to close without accepting would result in the HTTP layer
    returning a 403 Forbidden, which is not a proper WebSocket close.

    Close codes (key-leg refusal only, R55 round 2):
    - 4001: Authentication failure (when hybrid auth is configured - JWT_SECRET set)
    - 1008: Policy violation (API key only - backward compatible when no JWT_SECRET)

    IMPORTANT: This function does NOT accept the WebSocket on success.
    The caller (route) is responsible for accepting via broadcaster.connect()
    or websocket.accept(). No validation path here accepts or closes —
    accept-after-close crashes are structurally impossible in this function.

    Args:
        websocket: WebSocket connection to authenticate

    Returns:
        True if authenticated successfully, False if connection was rejected
    """
    settings = get_settings()

    # Check if hybrid auth is configured (JWT_SECRET is set)
    hybrid_auth_enabled = bool(settings.jwt_secret)

    # R55: SESSION_COOKIE_NAME, not the literal "session" no login ever set —
    # this dead read is why the cookie leg never ran on a real login.
    # The inline isinstance checks do double duty: they exclude the MagicMock
    # some tests hand back (not None, but not a string either) and they
    # narrow the Optional getters for mypy inside each and-chain (a boolean
    # "has_cookie" variable would do neither).
    cookie_value = websocket.cookies.get(SESSION_COOKIE_NAME)
    token_value = websocket.query_params.get("token")

    # R55 round 2 (self-review finding 1, both fresh-context reviews): a
    # present-but-INVALID credential must not refuse the socket by itself —
    # literally the HTTP gate's rule. authenticated_principal() passes a
    # request when ANY credential it checks is valid; a dead cookie simply
    # isn't one, and it never refuses merely for existing. The first R55
    # build made every hybrid failure terminal, and that over-refused: a
    # single-user box (gate off, keys disabled, sockets open to everyone)
    # killed every socket for a browser that once logged in and aged out —
    # 4001 is terminal in the frontend and /me is disabled in single-user
    # mode (AuthContext: enabled: authRequired !== false), so nothing 401s
    # to clear the auth state (the cookie itself is only ever removed by a
    # server-side logout, which this mode also never triggers): a browser
    # that never logged in worked, one that did was dead for up to 24h. So:
    # validate each present credential,
    # first valid one wins (cookie before ?token=, the order the priority
    # test pins); an invalid one casts no vote and the API-key leg below —
    # the pre-existing hierarchy — decides, exactly as it does for a client
    # with no cookie at all. EXPOSE_LAN mode is untouched by this: the gate
    # runs BEFORE these routes and still refuses a stale-cookie+no-key
    # handshake with 4001 there, where /me's 401 clears the auth state and
    # the login screen returns (and a fresh login replaces the cookie).
    # Gate-off refusal was the bug; gate-on was not.
    #
    # No validation path here accepts or closes the socket (the first
    # accept-then-close owner inside this function is deleted with the
    # verify_websocket_auth delegation): success hands an unaccepted socket
    # to the route (broadcaster.connect accepts), and the ONLY close stays
    # the key-leg refusal below, which accepts-then-closes exactly once.
    # That is also why the accept-after-close RuntimeError cannot come back
    # through here: nothing else in this function can close.
    if (
        isinstance(cookie_value, str)
        and cookie_value
        and (await websocket_auth.validate_session_cookie(cookie_value)) is not None
    ):
        logger.info(
            "WebSocket authenticated via cookie",
            extra={"path": str(websocket.url.path), "auth_method": "cookie"},
        )
        # Do NOT accept here - let the route/broadcaster handle it
        return True
    if (
        isinstance(token_value, str)
        and token_value
        and (websocket_auth.validate_websocket_jwt(token_value) is not None)
    ):
        logger.info(
            "WebSocket authenticated via query_param",
            extra={"path": str(websocket.url.path), "auth_method": "query_param"},
        )
        return True

    # Fall back to API key authentication
    if not await validate_websocket_api_key(websocket):
        # Must accept the WebSocket before we can close it with a proper close frame.
        # Without accept(), calling close() results in HTTP 403 during handshake.
        # The accept echoes an offered api-key.* subprotocol (B-1): browsers
        # enforce the echo BEFORE they read any close code, so a bare accept
        # here turns the deliberate 4001 into a 1006 the client retries.
        await websocket.accept(subprotocol=offered_key_subprotocol(websocket))
        # Use 4001 if hybrid auth is enabled (new behavior), otherwise 1008 (backward compat)
        close_code = 4001 if hybrid_auth_enabled else status.WS_1008_POLICY_VIOLATION
        await websocket.close(code=close_code)
        return False

    # API key auth succeeded - do NOT accept here, let the caller handle it
    return True


def _presented_api_key(conn: HTTPConnection) -> str | None:
    """The API key a connection carries where its transport allows one."""
    if conn.scope["type"] == "http":
        return conn.headers.get("x-api-key")
    if key := conn.query_params.get("api_key"):
        return key
    for protocol in conn.headers.get("sec-websocket-protocol", "").split(","):
        if (stripped := protocol.strip()).startswith("api-key."):
            return stripped.removeprefix("api-key.")
    return None


async def _session_username(session_id: str) -> str | None:
    """The user a login session belongs to, or None if Redis does not hold it."""
    try:
        redis = await get_redis_optional()
        if redis is None:
            logger.warning("Session check failed: Redis unavailable")
            return None
        session = await SessionService(redis).get_session(session_id)
    except Exception as e:
        logger.debug(f"Session not accepted: {type(e).__name__}")
        return None
    user_id = session.get("user_id")
    return None if user_id is None else str(session.get("username") or user_id)


async def authenticated_principal(conn: HTTPConnection) -> str | None:
    """Who presented a valid credential: a username, ``api-key``, or None."""
    key = _presented_api_key(conn)
    if key and _validate_key_hash_constant_time(_hash_key(key), _get_valid_key_hashes()):
        return API_KEY_PRINCIPAL
    if session_id := conn.cookies.get(SESSION_COOKIE_NAME):
        return await _session_username(session_id)
    return None


def _is_cors_preflight(scope: Scope) -> bool:
    """A preflight carries no credential, and CORSMiddleware answers it without a route.

    CORSMiddleware answers only when ``Origin`` is present; without it the request
    would reach the router, so the gate requires ``Origin`` too.
    """
    headers = Headers(scope=scope)
    return (
        scope["method"] == "OPTIONS"
        and "origin" in headers
        and "access-control-request-method" in headers
    )


def _never_shared(send: Send) -> Send:
    """Mark a response the gate authenticated as unfit for shared caches.

    Detection media answers ``Cache-Control: public``; behind a caching tunnel or
    CDN that would hand authenticated footage to whoever asks next.
    """

    async def send_private(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = MutableHeaders(scope=message)
            directives = [d.strip() for d in headers.get("cache-control", "").split(",")]
            lowered = {d.lower() for d in directives}
            if not lowered & {"private", "no-store"}:
                kept = [d for d in directives if d and d.lower() != "public"]
                headers["cache-control"] = ", ".join(["private", *kept])
        await send(message)

    return send_private


class AuthMiddleware:
    """Refuse unauthenticated requests when EXPOSE_LAN=true (OD-12).

    Mounted outermost in ``backend/main.py``, so nothing answers a request
    before the gate has checked it; ``IdempotencyMiddleware``, for one, replays
    stored responses by key alone. A refusal is logged as a security event
    (``event_type="auth_required"``, client IP masked).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or not get_settings().expose_lan:
            await self.app(scope, receive, send)
            return
        if scope["path"] in OPEN_PATHS or (scope["type"] == "http" and _is_cors_preflight(scope)):
            await self.app(scope, receive, send)
            return
        if await authenticated_principal(HTTPConnection(scope)) is None:
            await self._refuse(scope, receive, send)
            return
        await self.app(scope, receive, _never_shared(send) if scope["type"] == "http" else send)

    async def _refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        conn = HTTPConnection(scope)
        logger.warning(
            "Unauthenticated request refused",
            extra={
                "path": scope["path"],
                "method": scope.get("method", "WEBSOCKET"),
                "client_ip": mask_ip(conn.client.host if conn.client else "unknown"),
                "security_event": True,
                "event_type": "auth_required",
            },
        )
        if scope["type"] == "websocket":
            websocket = WebSocket(scope, receive, send)
            # Echo an offered api-key.* token (B-1): the browser enforces the
            # echo before it ever reads the 4001, so a bare accept here would
            # surface as a retried 1006 instead of the terminal close.
            await websocket.accept(subprotocol=offered_key_subprotocol(websocket))
            await websocket.close(code=WS_CLOSE_AUTH_REQUIRED, reason="Authentication required")
            return
        response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Authentication required"},
        )
        await response(scope, receive, send)
