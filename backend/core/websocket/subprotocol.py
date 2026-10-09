"""Subprotocol echo for API-key offers (B-1).

RFC 6455 §1.3/§4.1: a client that lists subprotocols in
``Sec-WebSocket-Protocol`` MUST see one of its own tokens echoed in the 101
response or it MUST fail the connection — Chromium and undici close 1006
before ``open`` ever fires. The frontend mints such offers from
``VITE_API_KEY`` via ``buildWebSocketOptions`` — both the direct
``useWebSocketStatus`` path and (since #6922) the shared WebSocket manager
pass ``protocols`` through — so an ``accept()`` that named no subprotocol
killed every key-offering socket in every browser even when the credential
itself was fine.

Echoing is transport-level, not an authentication decision: the value is one
the CLIENT sent, and the handshake opens or fails the same way whichever
credential (api key, session cookie, JWT) the route goes on to accept. That
is why every production ``accept()`` passes this — including the accept-then-
close refusal paths, where a missing echo replaces the deliberate 4001 with
an unclassified 1006 the client retries (1006 is not terminal for the
manager's backoff).

The extraction is first-match-wins over the offered header, the same order
``_presented_api_key`` / ``validate_websocket_api_key`` scan it in, so for any
realistic offer (well-formed tokens) the echoed token is the one whose
credential gets authenticated. It is deliberately NOT read back out of the
authentication result: the echoed value must be a token the client offered
(RFC 6455 again), and in the constructed corner cases where the extractors
diverge — a first token that is the bare prefix, or a query-string key racing
a header offer — the echo names the first well-formed offered token while the
credential may come from elsewhere. No key is authenticated that the echo
implies otherwise; do not "fix" this toward echoing the authenticated token,
which could name a token the client never offered.
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
