"""B-1: a browser offered ``api-key.<key>`` — the 101 must echo a token back.

RFC 6455 §1.3/§4.1: a client that lists subprotocols in
``Sec-WebSocket-Protocol`` MUST see one of its own tokens echoed in the 101
response or it MUST fail the connection — Chromium and undici close 1006
before ``open`` ever fires. The frontend bakes ``VITE_API_KEY`` into exactly
such an offer, so on an ``EXPOSE_LAN=true`` + ``VITE_API_KEY`` deployment the
key-offering sockets used to die in every browser: no ``accept()`` in the
backend ever passed ``subprotocol=``. (On this base the offering client is the
``buildWebSocketOptions`` → ``useWebSocketStatus`` path — the shared WebSocket
manager still constructs ``new WebSocket(url)`` with no protocols and picks the
offer up in #6922.)

Two tiers pin it:

* the **site sweep** — an AST walk over every production ``accept(`` in the
  package dirs. The fix is a keyword at each accept call (there is no single
  choke point: ``AuthMiddleware`` is mounted last, therefore outermost, so the
  gate's accept-then-close never passes through any inner shim), and a sweep
  that enumerates calls can pin a site added tomorrow. It fails with file:line
  for every bare accept.
* the **raw handshake** — a real uvicorn serving the real ``app`` on
  127.0.0.1, driven by a hand-written HTTP upgrade over a plain socket. Mock
  WebSockets assert constructor arguments and never see the 101; jsdom's
  WebSocket never sends one. This is the only tier in the suite that reads the
  bytes a browser reads. ``curl -i`` is NOT one — curl sends the header and
  ignores whether it is echoed — so the pin parses the response itself.

Scenario env and the assertions that consume it live together in
``_b1_ws_subprotocol_server.MODE_ENV``.
"""

from __future__ import annotations

import ast
import base64
import os
import pathlib
import socket
import struct
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import ClassVar

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SERVER_SCRIPT = pathlib.Path(__file__).with_name("_b1_ws_subprotocol_server.py")
TEST_KEY = "b1-pin-key-5f3a"

# Dirs whose accept() calls are production handshake sites. api + services is
# where every route-reachable accept lives after B1.5 moved the gate into
# middleware; core is swept too so a future accept there cannot dodge the pin.
SWEEP_DIRS = ("backend/api", "backend/services", "backend/core")


# --------------------------------------------------------------------------
# tier 1: the site sweep
# --------------------------------------------------------------------------


def _production_accepts() -> list[str]:
    """Every production ``X.accept(`` call as ``file:line`` (methods named
    accept on non-websocket objects, e.g. a queue, are matched by name and
    excluded by their call context — the sweep is on ``.accept(`` receivers
    that are named like a websocket/connection, plus bare ``accept(`` defs)."""
    sites: list[str] = []
    for rel in SWEEP_DIRS:
        for path in sorted((REPO_ROOT / rel).rglob("*.py")):
            if "_b1_ws_subprotocol_server" in path.name:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not (isinstance(fn, ast.Attribute) and fn.attr == "accept"):
                    continue
                if _iswebsocket_receiver(fn):
                    relpath = path.relative_to(REPO_ROOT)
                    sites.append(f"{relpath}:{node.lineno}")
    return sites


def _iswebsocket_receiver(fn: ast.Attribute) -> bool:
    """True when the call's receiver reads as a WebSocket-ish name.

    The sweep deliberately keys on the receiver name (``websocket``,
    ``ws``, ``connection``…) rather than types: an AST pass has no type
    info, and the names this codebase uses for accepts are uniform. A new
    accept site named anything else still surfaces — test_the_accept_name_
    vocabulary_stays_sweepable below fails when the vocabulary drifts.
    """
    parts: list[str] = []
    node: ast.expr = fn.value
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    tail = parts[0].lower() if parts else ""
    return any(h in tail for h in ("websocket", "ws", "connection", "socket"))


def test_the_accept_sweep_finds_the_known_sites() -> None:
    """The sweep finds the 12 production accept sites B-1 counted on
    2026-10-09 (7 in websocket_auth, 2 in auth.py — gate refuse + route-key
    fallback, 1 route accept, 2 broadcaster connects) — if it finds fewer,
    the sweep itself rotted and every other test here would pass vacuously."""
    sites = _production_accepts()
    assert len(sites) >= 12, f"sweep found only {len(sites)} accept sites: {sites}"
    files = {s.split(":")[0] for s in sites}
    for expected in (
        "backend/api/middleware/auth.py",
        "backend/api/middleware/websocket_auth.py",
        "backend/services/event_broadcaster.py",
        "backend/services/system_broadcaster.py",
    ):
        assert expected in files, f"sweep missed {expected}: {sorted(files)}"


def test_every_production_accept_passes_subprotocol() -> None:
    """B-1's fix shape: every production accept passes ``subprotocol=``.

    An accept with no ``subprotocol`` keyword answers a browser that offered
    protocols with a 101 no conforming client will accept. The keyword is
    what the fix adds at each call; this sweep is what keeps the list whole.
    """
    bare: list[str] = []
    for rel in SWEEP_DIRS:
        for path in sorted((REPO_ROOT / rel).rglob("*.py")):
            if "_b1_ws_subprotocol_server" in path.name:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not (isinstance(fn, ast.Attribute) and fn.attr == "accept"):
                    continue
                if not _iswebsocket_receiver(fn):
                    continue
                if not any(kw.arg == "subprotocol" for kw in node.keywords):
                    bare.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not bare, "accept() call(s) answer a subprotocol offer with no echo: " + ", ".join(bare)


def test_the_accept_name_vocabulary_stays_sweepable() -> None:
    """Guard for the sweep's name heuristic: every production accept the tree
    walk sees under ANY receiver must have a sweepable name. A site named,
    say, ``upstream.accept()`` would silently dodge tier 1 — this fails first."""
    dodges: list[str] = []
    for rel in SWEEP_DIRS:
        for path in sorted((REPO_ROOT / rel).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr == "accept":
                    if not _iswebsocket_receiver(fn):
                        # Not a websocket receiver — must be something
                        # genuinely unrelated (a queue). Flag the ambiguous
                        # middle: receivers that look connection-ish.
                        src = ast.unparse(fn.value).lower()
                        if any(
                            h in src
                            for h in ("conn", "socket", "client", "session", "channel", "upstream")
                        ):
                            dodges.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {src}")
    assert not dodges, "accept() on a connection-ish receiver the name sweep misses: " + ", ".join(
        dodges
    )


# --------------------------------------------------------------------------
# tier 2: raw handshakes against a live uvicorn
# --------------------------------------------------------------------------

_GUARD = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _raw_handshake(
    port: int,
    path: str,
    protocols: list[str] | None,
    cookie: str | None = None,
) -> tuple[int, dict[str, str], socket.socket, bytes]:
    """Drive a real HTTP upgrade over a plain socket. Returns (status,
    headers-lowercased, live socket). No ws library — a client lib that
    enforces the echo would itself raise before we can read the header, and
    one that doesn't prove nothing. Hand-written is the pin."""
    # RFC 6455 §1.3: the key MUST decode to exactly 16 bytes; servers reject
    # any other length (measured: a 18-byte key gets HTTP 400 before the 101).
    key = base64.b64encode(b"b1-pin-key!12345").decode()
    lines = [
        f"GET {path} HTTP/1.1",
        f"Host: 127.0.0.1:{port}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    if protocols:
        lines.append(f"Sec-WebSocket-Protocol: {', '.join(protocols)}")
    if cookie:
        lines.append(f"Cookie: {cookie}")
    request = "\r\n".join([*lines, "", ""]).encode()

    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        sock.sendall(request)
        # Read the response head: until the header block ends.
        buf = b""
        deadline = time.monotonic() + 5
        while b"\r\n\r\n" not in buf and time.monotonic() < deadline:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        if not head:
            raise AssertionError(f"no response head from :{port}{path}")
        status_line, *header_lines = head.decode("latin-1").split("\r\n")
        status = int(status_line.split(" ", 2)[1])
        headers = {}
        for line in header_lines:
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        sock.settimeout(5)
        return status, headers, sock, rest
    except Exception:
        sock.close()
        raise


def _close_frame_code(rest: bytes) -> int | None:
    """First close-frame code from already-read bytes, if one is there."""
    if len(rest) >= 4 and rest[0] == 0x88:  # FIN | opcode 8 (close)
        return struct.unpack("!H", rest[2:4])[0]
    return None


class _Server:
    """One live uvicorn per scenario mode, spawned once per mode."""

    _by_mode: ClassVar[dict[str, _Server]] = {}

    def __init__(self, mode: str) -> None:
        env = dict(os.environ)
        env.update(
            {
                "PYTHONPATH": str(REPO_ROOT),
                # Silence the OTLP exporter reaching for a collector.
                "OTEL_ENABLED": "false",
                # Settings validates DATABASE_URL at import; lifespan=off and
                # the redis dependency override mean nothing ever connects.
                "DATABASE_URL": "postgresql+asyncpg://pin:pin@127.0.0.1:1/pin",
            }
        )
        self.proc = subprocess.Popen(  # noqa: S603  # fixed argv, our own script, no shell
            [sys.executable, str(SERVER_SCRIPT), mode],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        line = self.proc.stdout.readline() if self.proc.stdout else ""
        if not line.startswith("LISTENING "):
            err = self.proc.stderr.read()[-2000:] if self.proc.stderr else ""
            raise AssertionError(f"child (mode={mode}) never bound: {line!r} stderr={err}")
        self.port = int(line.split()[1])
        self.mode = mode
        self._wait_ready()

    def _wait_ready(self) -> None:
        """LISTENING prints after bind(); the kernel only ACCEPTS once the
        child's event loop calls listen() during uvicorn startup — which is
        after importing all of backend.main (seconds). Poll connect until it
        completes; a refused connect is still booting, any other error is
        real."""
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                err = self.proc.stderr.read()[-2000:] if self.proc.stderr else ""
                raise AssertionError(f"child (mode={self.mode}) died: {err}")
            try:
                probe = socket.create_connection(("127.0.0.1", self.port), timeout=1)
                probe.close()
                return
            except ConnectionRefusedError:
                time.sleep(0.2)
        raise AssertionError(f"child (mode={self.mode}) not accepting after 25s")

    @classmethod
    def get(cls, mode: str) -> _Server:
        if mode not in cls._by_mode:
            cls._by_mode[mode] = cls(mode)
        return cls._by_mode[mode]

    @classmethod
    def stop_all(cls) -> None:
        for srv in cls._by_mode.values():
            srv.proc.terminate()
            try:
                srv.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                srv.proc.kill()


@pytest.fixture(scope="module")
def b1_servers() -> Iterator[type[_Server]]:
    yield _Server
    _Server.stop_all()


def _offer(port: int, protocols: list[str] | None, path: str = "/ws/system", cookie=None):
    return _raw_handshake(port, path, protocols, cookie)


# --------------------------------------------------------------------------
# Done-when pins
# --------------------------------------------------------------------------


@pytest.mark.timeout(30)
def test_valid_key_subprotocol_offer_is_echoed_in_101(b1_servers: type[_Server]) -> None:
    """B-1, the headline: offer ``api-key.<valid>`` with keys on, the 101 must
    echo that exact token back. Pre-fix this header is ABSENT (measured on
    main: raw socket direct AND via nginx) and Chromium closes 1006."""
    srv = b1_servers.get("keys-on")
    status, headers, sock, _rest = _offer(srv.port, [f"api-key.{TEST_KEY}"])
    try:
        assert status == 101, f"expected the handshake to succeed, got {status}"
        assert headers.get("sec-websocket-protocol") == f"api-key.{TEST_KEY}", (
            "the 101 does not echo the offered token — every browser fails this "
            f"handshake per RFC 6455 §4.1. Headers: {headers}"
        )
    finally:
        sock.close()


@pytest.mark.timeout(30)
def test_second_offered_token_echoed_when_first_unknown(b1_servers: type[_Server]) -> None:
    """The echoed value must be one the client OFFERED. A client that offers
    ``superproto, api-key.<valid>`` and gets ``superproto`` back is being lied
    to; it must get the api-key token — and not the raw key smuggled through
    as some other token."""
    srv = b1_servers.get("keys-on")
    status, headers, sock, _rest = _offer(srv.port, ["superproto", f"api-key.{TEST_KEY}"])
    try:
        assert status == 101
        echo = headers.get("sec-websocket-protocol")
        assert echo == f"api-key.{TEST_KEY}", f"echoed {echo!r}, not the offered api-key token"
    finally:
        sock.close()


@pytest.mark.timeout(30)
def test_no_offer_grows_no_subprotocol_header(b1_servers: type[_Server]) -> None:
    """Control: a client that offered nothing (cookie path, plain socket) must
    see NO Sec-WebSocket-Protocol in the 101. Echoing a token nobody offered
    is its own RFC violation — this is what keeps the fix from over-applying."""
    srv = b1_servers.get("open")
    status, headers, sock, _rest = _offer(srv.port, None)
    try:
        assert status == 101, f"expected open-mode handshake to succeed, got {status}"
        assert "sec-websocket-protocol" not in headers, (
            f"the server echoed a protocol nobody offered: {headers}"
        )
    finally:
        sock.close()


@pytest.mark.timeout(30)
def test_gate_refusal_of_key_offer_echoes_and_closes_4001(
    b1_servers: type[_Server],
) -> None:
    """The gate (AuthMiddleware._refuse, outermost — mounted last) answers an
    unauthenticated websocket with accept-then-close-4001 so the client sees a
    proper close, not a 403. Browsers enforce the echo BEFORE any close code
    (Chromium: 1006, close code never delivered — measured on main), so that
    accept must echo too or the operator loses 4001 and gets retry-noise
    instead: a 1006 is an abstraction-level failure, not a close code the
    client's backoff treats as terminal (on the #6922 branch that set is
    AUTH_TERMINAL_CLOSE_CODES; the offering useWebSocketStatus hook retries
    an unknown code up to its 15 attempts). Offer an api-key token the gate cannot
    authenticate (wrong key, gate on) — the 101 echoes it, then 4001 rides."""
    srv = b1_servers.get("gate-on")
    status, headers, sock, rest = _offer(srv.port, ["api-key.the-wrong-key"])
    try:
        assert status == 101, f"the gate refused at HTTP level ({status}), not as a close"
        assert headers.get("sec-websocket-protocol") == "api-key.the-wrong-key", (
            f"gate-refuse 101 grew no echo: {headers}"
        )
        code = _close_frame_code(rest)
        if code is None:  # the close frame had not arrived in the first read
            try:
                frame = sock.recv(64)
                code = _close_frame_code(frame) if frame else None
            except TimeoutError:  # socket.timeout IS TimeoutError on 3.10+
                code = None
        assert code == 4001, f"expected the auth close 4001 after the echoing 101, got {code}"
    finally:
        sock.close()


@pytest.mark.timeout(30)
def test_garbage_offers_do_not_crash_the_handshake(b1_servers: type[_Server]) -> None:
    """Robustness floor for the extractor: a header carrying junk (empty
    tokens, a bare ``api-key.`` with no key, tokens with spaces) must neither
    500 the upgrade nor echo junk back. With keys on and nothing valid in the
    offer, auth fails the same way a missing key does: the 101 (if the route
    still accepts) echoes nothing."""
    srv = b1_servers.get("keys-on")
    status, headers, sock, _rest = _offer(srv.port, ["", "api-key.", " spaced , api-key .x"])
    try:
        # Auth-rejected paths accept-then-close (4001/1008) or HTTP-refuse;
        # a 500 on the upgrade is likewise out of the question. What may
        # never happen is a 101 that names a protocol the extractor would
        # not pick: the bare "api-key." carries no key, so a compliant echo
        # here is absent — and a response that grew no upgrade at all has no
        # echo header either, which is why status is pinned first.
        assert status != 500, "junk in Sec-WebSocket-Protocol 500'd the upgrade"
        echo = headers.get("sec-websocket-protocol")
        assert echo is None, (
            f"the server echoed {echo!r}; the offer held no well-formed "
            "api-key token, so nothing may be echoed (module docstring: a "
            "bare 'api-key.' is not an offer and is not echoed)"
        )
    finally:
        sock.close()
