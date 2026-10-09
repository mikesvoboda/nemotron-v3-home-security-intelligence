"""Subprotocol echo for API-key offers (B-1).

RFC 6455 §1.3/§4.1: a client that lists subprotocols in
``Sec-WebSocket-Protocol`` MUST see one of its own tokens echoed in the 101
response or it MUST fail the connection — Chromium and undici close 1006
before ``open`` ever fires. The browser WebSocket manager offers
``api-key.<key>`` (frontend/src/services/api.ts), so an ``accept()`` that
names no subprotocol kills every manager-routed socket in every browser even
when the credential itself is fine.

Echoing is transport-level, not an authentication decision: the value is one
the CLIENT sent, and the handshake opens or fails the same way whichever
credential (api key, session cookie, JWT) the route goes on to accept. That
is why every production ``accept()`` passes this — including the accept-then-
close refusal paths, where a missing echo replaces the deliberate 4001 with
an unclassified 1006 the client retries (1006 is not terminal for the
manager's backoff).

The extraction is first-match-wins over the offered header, mirroring
``_presented_api_key`` / ``validate_websocket_api_key``, so the echoed token
is the same token those extractors read the credential from. A bare
``api-key.`` (no key) is not an offer and is not echoed.
"""

from __future__ import annotations

from starlette.websockets import WebSocket

API_KEY_PROTOCOL_PREFIX = "api-key."


def offered_key_subprotocol(websocket: WebSocket) -> str | None:
    """The first offered token that carries an API key, or ``None``.

    Returns a token exactly as offered (trimmed of whitespace): echoing
    anything the client did not offer is its own RFC violation, and echoing
    nothing to a client that offered one is B-1.
    """
    for protocol in websocket.headers.get("sec-websocket-protocol", "").split(","):
        token = protocol.strip()
        if token.startswith(API_KEY_PROTOCOL_PREFIX) and len(token) > len(API_KEY_PROTOCOL_PREFIX):
            return token
    return None
