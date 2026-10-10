"""A running fake, reached as if it were the in-process app (O2.1).

``remote_app(base_url)`` is an ASGI app that forwards every HTTP request to
the fake at ``base_url`` (the container ``docker-compose.fake-ai.yml``
starts) and relays the answer unchanged. Anything that drives the fake
through ``httpx.ASGITransport(app=...)`` - the whole contract suite under
``backend/tests/contracts/ai_providers/`` - can therefore run its assertions
against the image instead of the app object, with no change to the tests:
the tier's conftest swaps this in for ``create_fake_app()`` when
``FAKE_AI_URL`` is set.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import httpx

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

# Hop-by-hop or recomputed headers: httpx sets its own on the way out, and the
# relayed body is already decoded, so its length is recomputed on the way back.
_DROP_REQUEST = {b"host", b"content-length", b"connection", b"transfer-encoding"}
_DROP_RESPONSE = {"content-length", "content-encoding", "transfer-encoding", "connection"}


def remote_app(
    base_url: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = 120.0,
    on_request: Callable[[str, str], None] | None = None,
) -> Callable[[Scope, Receive, Send], Awaitable[None]]:
    """An ASGI app forwarding to the fake at ``base_url``.

    ``timeout`` outlasts the fake's own stalls (the timeout fault, a slow
    scenario). ``on_request(method, path)`` is told about every forwarded
    request, so a caller can prove the remote was really reached.
    """

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            raise RuntimeError(f"remote_app forwards HTTP only, got {scope['type']!r}")
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        path = scope["path"]
        if scope.get("query_string"):
            path = f"{path}?{scope['query_string'].decode('latin-1')}"
        headers = [(k, v) for k, v in scope["headers"] if k.lower() not in _DROP_REQUEST]
        async with httpx.AsyncClient(
            base_url=base_url, transport=transport, timeout=timeout
        ) as client:
            response = await client.request(scope["method"], path, content=body, headers=headers)
        if on_request is not None:
            on_request(scope["method"], scope["path"])
        content = response.content
        relayed = [
            (k.encode("latin-1"), v.encode("latin-1"))
            for k, v in response.headers.items()
            if k.lower() not in _DROP_RESPONSE
        ]
        relayed.append((b"content-length", str(len(content)).encode()))
        await send(
            {"type": "http.response.start", "status": response.status_code, "headers": relayed}
        )
        await send({"type": "http.response.body", "body": content})

    return app
