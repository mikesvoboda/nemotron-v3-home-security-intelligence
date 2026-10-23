#!/usr/bin/env python3
"""The CI notification sinks ([r308a]): mail, webhook and Web Push fakes.

One stdlib-only program serves all three modes:

* ``smtp <smtp-port> <http-port>`` — the mail sink: a plain SMTP receiver
  (no STARTTLS, no auth) that stores every message, plus its read-back HTTP
  (``GET /messages`` lists them, ``DELETE /messages`` clears, ``/health``).
* ``http <port> <mode>`` — a request recorder; ``webhook`` answers every POST
  with 200, ``push`` answers POSTs under /push/ with 201 (RFC 8030's
  Created). ``GET /requests`` lists records (path, headers, body, body_b64,
  received_at); ``DELETE /requests`` clears. ``GET /health`` on both.

Writes nothing outside ``SINK_DATA_DIR`` (the container sets it to a tmpfs —
the service runs ``read_only: true``). No auth, loopback-only by deployment:
the overlay publishes to 127.0.0.1 only and the sinks join ci-net only.

Ports are announced on stdout as ``SMTP_PORT=<n>`` / ``HTTP_PORT=<n>`` lines —
the unit tests spawn with port 0 and read the kernel-assigned numbers off
them; in compose the ports are fixed and the lines are the boot log.
"""

from __future__ import annotations

import asyncio
import base64
import email
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# Only-writable root. The container sets it to a tmpfs; the tests set their own
# per-subprocess dir. The /tmp fallback is a local CI convenience, not a secret.
DATA_DIR = Path(os.environ.get("SINK_DATA_DIR", "/tmp/ci-sinks"))  # noqa: S108

MAX_STORE = 100
MAX_BODY = 256 * 1024


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class _Store:
    """The message/request store: one JSON file per sink kind, under DATA_DIR."""

    def __init__(self, name: str) -> None:
        self.name = name
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = DATA_DIR / f"{name}.json"
        self._items: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            # The path is SINK_DATA_DIR/<kind>.json — pinned by the compose file
            # (a tmpfs) or the test's own tmpdir; no request ever names it, so
            # there is no traversal surface.
            with open(self.path, encoding="utf-8") as handle:  # nosemgrep: path-traversal-open
                self._items = json.load(handle)
        except OSError, json.JSONDecodeError:
            self._items = []

    def _flush(self) -> None:
        # Same path as _load above, same answer.
        with open(self.path, "w", encoding="utf-8") as handle:  # nosemgrep: path-traversal-open
            json.dump(self._items, handle)

    def add(self, item: dict[str, Any]) -> None:
        self._items.append(item)
        if len(self._items) > MAX_STORE:
            self._items = self._items[-MAX_STORE:]
        self._flush()

    def items(self) -> list[dict[str, Any]]:
        return list(self._items)

    def clear(self) -> None:
        self._items = []
        self._flush()


_MESSAGES: _Store | None = None
_REQUESTS: _Store | None = None


def _messages() -> _Store:
    global _MESSAGES  # noqa: PLW0603 - one lazily-built store per process
    if _MESSAGES is None:
        _MESSAGES = _Store("messages")
    return _MESSAGES


def _requests() -> _Store:
    global _REQUESTS  # noqa: PLW0603 - one lazily-built store per process
    if _REQUESTS is None:
        _REQUESTS = _Store("requests")
    return _REQUESTS


def _parse_message(raw: bytes) -> dict[str, Any]:
    """One RFC 5322 message into a read-back record."""
    message = email.message_from_bytes(raw)
    headers = dict(message.items())
    body = ""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    body = payload.decode("utf-8", errors="replace")
                break
        else:
            first = message.get_payload(0)
            body = str(first) if first is not None else ""
    else:
        payload = message.get_payload(decode=True)
        body = (
            payload.decode("utf-8", errors="replace")
            if isinstance(payload, bytes)
            else str(message.get_payload())
        )
    return {
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", ""),
        "data": body,
        "received_at": _now(),
    }


class _SMTPSession(asyncio.Protocol):
    """A minimal SMTP receiver: EHLO/HELO, MAIL, RCPT, DATA, RSET, NOOP, QUIT.

    Deliberately minimal and deliberately WITHOUT extensions: the EHLO answer
    advertises none, so no STARTTLS and no AUTH — the shape the CI backend's
    ``SMTP_USE_TLS=false`` is paired with (pinned both from the client side in
    ``test_ci_sink_server.py`` and in the overlay's env).
    """

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport: asyncio.Transport = transport  # type: ignore[assignment]
        self.buffer = b""
        self.state = "greet"
        self.envelope_from = ""
        self.envelope_to: list[str] = []
        self.data_buffer = b""
        self.transport.write(b"220 ci-sink ready\r\n")

    def data_received(self, data: bytes) -> None:
        self.buffer += data
        if self.state == "data-body":
            self._feed_data_body()
            if self.state == "data-body":
                return
        while b"\r\n" in self.buffer:
            line, _, self.buffer = self.buffer.partition(b"\r\n")
            self._command(line.decode("utf-8", errors="replace"))
            if self.state == "data-body":
                self._feed_data_body()
                if self.state == "data-body":
                    return
        if self.state != "data-body" and len(self.buffer) > 64 * 1024:
            self.transport.write(b"500 line too long\r\n")
            self.transport.close()

    def _feed_data_body(self) -> None:
        """Accumulate the DATA payload until the lone ``.`` terminator."""
        while b"\r\n" in self.buffer:
            line, _, self.buffer = self.buffer.partition(b"\r\n")
            if line == b".":
                try:
                    _messages().add(_parse_message(self.data_buffer))
                except Exception as error:  # a bad message must not kill the sink
                    print(f"SINK_ERROR parse: {error}", flush=True)  # noqa: T201 - boot log
                self.data_buffer = b""
                self.envelope_from = ""
                self.envelope_to = []
                self.state = "cmd"
                self.transport.write(b"250 stored\r\n")
                return
            # Dot-stuffing (RFC 5321 4.5.2): a leading ".." unfolds to ".".
            if line.startswith(b".."):
                line = line[1:]
            self.data_buffer += line + b"\r\n"
        if len(self.data_buffer) > MAX_BODY:
            self.transport.write(b"552 message too large\r\n")
            self.data_buffer = b""
            self.state = "cmd"

    def _command(self, line: str) -> None:
        verb = line.split(" ", 1)[0].upper() if line else ""
        if self.state == "greet":
            if verb in ("EHLO", "HELO"):
                self.state = "cmd"
                # Multi-line EHLO answer with NO extensions: 250-ci-sink then
                # the final 250. No STARTTLS, no AUTH.
                self.transport.write(b"250-ci-sink\r\n250 OK\r\n")
            else:
                self.transport.write(b"503 send EHLO first\r\n")
            return
        if verb == "MAIL":
            self.envelope_from = line.partition("FROM:")[2].strip().strip("<>")
            self.transport.write(b"250 OK\r\n")
        elif verb == "RCPT":
            self.envelope_to.append(line.partition("TO:")[2].strip().strip("<>"))
            self.transport.write(b"250 OK\r\n")
        elif verb == "DATA":
            self.state = "data-body"
            self.data_buffer = b""
            self.transport.write(b"354 end with <CRLF>.<CRLF>\r\n")
        elif verb == "RSET":
            self.envelope_from = ""
            self.envelope_to = []
            self.transport.write(b"250 OK\r\n")
        elif verb == "NOOP":
            self.transport.write(b"250 OK\r\n")
        elif verb == "QUIT":
            self.transport.write(b"221 bye\r\n")
            self.transport.close()
        else:
            self.transport.write(b"502 not implemented\r\n")


class _SinkHTTP(BaseHTTPRequestHandler):
    """The read-back surface: /messages or /requests by mode, plus /health."""

    mode = "webhook"  # class attr overridden per server

    # --- helpers ---------------------------------------------------------
    def _json(self, status: int, body: dict[str, Any] | None) -> None:
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def _store_and_prefix(self) -> tuple[_Store | None, str]:
        if self.mode == "mail":
            return _messages(), "/messages"
        return _requests(), "/requests"

    def log_message(self, format: str, *args: Any) -> None:  # stdlib signature
        print(f"SINK_HTTP {self.mode} {format % args}", flush=True)  # noqa: T201 - boot log

    # --- verbs -----------------------------------------------------------
    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"ok": True, "mode": self.mode})
            return
        store, prefix = self._store_and_prefix()
        if store is not None and self.path == prefix:
            self._json(200, {prefix[1:]: store.items()})
            return
        self._json(404, {"error": f"unknown path {self.path}"})

    def do_DELETE(self) -> None:
        store, prefix = self._store_and_prefix()
        if store is not None and self.path == prefix:
            store.clear()
            self._json(204, None)
            return
        self._json(404, {"error": f"unknown path {self.path}"})

    def do_PUT(self) -> None:
        # BaseHTTPRequestHandler's default for an unknown verb is 501; the
        # sink's contract says 405 (method exists, not allowed here).
        self._json(405, {"error": f"{self.command} not supported"})

    def do_POST(self) -> None:
        if self.mode == "mail":
            self._json(405, {"error": "the mail sink records SMTP, not HTTP POSTs"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(min(length, MAX_BODY))
        record = {
            "path": self.path,
            "headers": {key.lower(): value for key, value in self.headers.items()},
            "body": body.decode("utf-8", errors="replace"),
            # B4.3: Web Push bodies are AES128GCM ciphertext (RFC 8291) — not
            # valid UTF-8, so the decoded form above mangles them. The base64
            # twin carries the exact bytes a golden leg decrypts; for plain
            # JSON bodies it is the same payload re-encoded.
            "body_b64": base64.b64encode(body).decode("ascii"),
            "received_at": _now(),
        }
        _requests().add(record)
        if self.mode == "push" and self.path.startswith("/push/"):
            # RFC 8030 5: 201 Created on acceptance.
            self._json(201, None)
            return
        self._json(200, {"received": True})


def _serve_http(port: int, mode: str) -> int:
    """One read-back/recorder HTTP server; returns the port it bound."""
    handler = type(f"_SinkHTTP_{mode}", (_SinkHTTP,), {"mode": mode})
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)  # noqa: S104 - container-local
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def _serve_smtp_forever(port: int) -> None:
    """The SMTP receiver, served on this thread until the process ends.

    Announces the actually-bound port (the tests pass 0 and read the
    kernel-assigned number off stdout) before serving.
    """

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        server = await loop.create_server(_SMTPSession, "0.0.0.0", port)  # noqa: S104
        _announce("SMTP_PORT", server.sockets[0].getsockname()[1])
        await server.serve_forever()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:  # the operator's Ctrl-C, not the sink's business
        pass


def main(argv: list[str]) -> int:
    usage = "usage: sink.py smtp <smtp-port> <http-port> | http <port> <webhook|push>"
    if (
        len(argv) != 4
        or argv[1] not in ("smtp", "http")
        or (argv[1] == "http" and argv[3] not in ("webhook", "push"))
    ):
        print(usage, file=sys.stderr)  # noqa: T201 - CLI contract
        return 2
    if argv[1] == "smtp":
        # The mail sink: SMTP plus its read-back surface, one process.
        _announce("HTTP_PORT", _serve_http(int(argv[3]), "mail"))
        _serve_smtp_forever(int(argv[2]))
    else:
        _announce("HTTP_PORT", _serve_http(int(argv[2]), argv[3]))
        try:
            threading.Event().wait()  # the HTTP thread serves; this thread waits
        except KeyboardInterrupt:
            pass
    return 0


def _announce(key: str, port: int) -> None:
    print(f"{key}={port}", flush=True)  # noqa: T201 - the port announcement IS the contract


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
