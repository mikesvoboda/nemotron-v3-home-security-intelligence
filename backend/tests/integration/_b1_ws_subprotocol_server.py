"""Child-process bootstrap for the B-1 raw-handshake pin.

Runs in a spawned subprocess (``mp.get_context("spawn")``) so the Settings
singleton is built from this file's environment and nothing imported in the
pytest worker leaks in. The child prints ``LISTENING <port>`` once the socket
binds, then serves ``backend.main.app`` — the FULL middleware stack, the
EXPOSE_LAN gate included — on 127.0.0.1 until the parent terminates it.

``lifespan="off"``: the pin cares about the handshake, not startup wiring, and
the real lifespan would reach for Redis/DB/services this process has none of.
The one route the pin drives (``/ws/system``) touches Redis only through its
``Depends(get_redis)`` parameter (rate limiting is switched off below), so a
dependency override covers it without touching module internals.

``MODE_ENV`` selects the deployment the parent asked for; the scenario names,
the env they flip, and the assertions that read them live on one page.
"""

from __future__ import annotations

import os
import socket
import sys

# One valid key for every key-bearing mode; the tests offer tokens built from
# it and assert the echo byte-for-byte.
TEST_KEY = "b1-pin-key-5f3a"

MODE_ENV: dict[str, dict[str, str]] = {
    # The B-1 deployment: API keys on, gate off. A valid-key offer reaches the
    # route and the broadcaster's accept is the first 101.
    "keys-on": {
        "API_KEY_ENABLED": "true",
        "API_KEYS": f'["{TEST_KEY}"]',
        "EXPOSE_LAN": "false",
        "RATE_LIMIT_ENABLED": "false",
    },
    # The OD-12 gate up: an invalid-key offer dies at the gate's accept-then-
    # close-4001 (auth.py _refuse) — its 101 is the one a browser sees.
    "gate-on": {
        "API_KEY_ENABLED": "true",
        "API_KEYS": f'["{TEST_KEY}"]',
        "EXPOSE_LAN": "true",
        "RATE_LIMIT_ENABLED": "false",
    },
    # No credentials anywhere: control proving a no-offer handshake is
    # untouched by the fix (the 101 must NOT grow a Sec-WebSocket-Protocol).
    "open": {
        "API_KEY_ENABLED": "false",
        "EXPOSE_LAN": "false",
        "RATE_LIMIT_ENABLED": "false",
    },
}


def _serve(mode: str) -> None:  # pragma: no cover - child process body
    for name, value in MODE_ENV[mode].items():
        os.environ[name] = value
    os.environ.setdefault("LOG_LEVEL", "CRITICAL")

    from unittest.mock import AsyncMock

    import uvicorn

    from backend.core.redis import get_redis
    from backend.main import app

    async def _stub_redis():
        yield AsyncMock()

    app.dependency_overrides[get_redis] = _stub_redis

    # Bind the port here and hand the socket to uvicorn (run(sockets=...)) —
    # binding twice (probe then uvicorn) races another process for the port,
    # and an un-listening held socket just refuses connections. asyncio calls
    # listen() on the socket it is given.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    print(f"LISTENING {sock.getsockname()[1]}", flush=True)

    uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=sock.getsockname()[1],
            log_level="critical",
            lifespan="off",
        )
    ).run(sockets=[sock])


if __name__ == "__main__":
    _serve(sys.argv[1])
