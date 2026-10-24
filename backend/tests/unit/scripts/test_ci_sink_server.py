"""The CI sink server (``docker/ci-sinks/sink.py``), driven over loopback.

[r308a] puts a mail sink, a webhook sink and a Web Push service fake in the CI
harness beside ``FAKE_SERVICES``. The sink image installs nothing — the program
is stdlib-only Python — so these tests drive the real process the way its
clients do: SMTP through :mod:`smtplib` (the client
``NotificationService._send_email_sync`` uses), the read-back surfaces through
:mod:`urllib` (the client the compose healthchecks use).

Each test starts its own process on port 0 and reads the bound ports off its
stdout (``SMTP_PORT=…`` / ``HTTP_PORT=…`` lines), so tests never race each
other for a fixed port and no fixed port is needed anywhere. The process is
torn down in teardown: terminate first, kill only if it ignores that.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import shutil
import smtplib
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SINK = REPO_ROOT / "docker" / "ci-sinks" / "sink.py"


class SinkProcess:
    """One ``sink.py`` subprocess; ``ports`` holds the ports it announced.

    Each process gets its own ``SINK_DATA_DIR`` — the isolation the container
    gives each sink service (a per-service tmpfs) — so the JSON store never
    bridges two subprocesses.
    """

    def __init__(self, *args: str) -> None:
        self.data_dir = tempfile.mkdtemp(prefix="ci-sink-test-")
        env = {**os.environ, "SINK_DATA_DIR": self.data_dir}
        # The subprocess under test IS the sink server; it is not mockable
        # without untesting the file's subject.
        self.proc = subprocess.Popen(  # noqa: S603  # real - the sink under test
            [sys.executable, str(SINK), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self.ports: dict[str, int] = {}
        self._lines: queue.Queue[str] = queue.Queue()
        self._stderr: list[str] = []
        assert self.proc.stdout is not None and self.proc.stderr is not None
        threading.Thread(target=self._pump, args=(self.proc.stdout,), daemon=True).start()
        threading.Thread(target=self._pump_stderr, args=(self.proc.stderr,), daemon=True).start()

    def _pump(self, stream: Any) -> None:
        for line in stream:
            self._lines.put(line.strip())

    def _pump_stderr(self, stream: Any) -> None:
        self._stderr.extend(stream)

    def wait_ports(self, *names: str, timeout: float = 10.0) -> None:
        """Block until every named port is announced; fail with the stderr."""
        deadline = time.monotonic() + timeout
        needed = set(names)
        while time.monotonic() < deadline and needed - set(self.ports):
            if self.proc.poll() is not None:
                pytest.fail(
                    f"sink {SINK.name} exited {self.proc.returncode} before announcing "
                    f"{sorted(needed)}; stderr: {self._stderr[-20:]}"
                )
            try:
                line = self._lines.get(timeout=0.2)
            except queue.Empty:
                continue
            key, sep, value = line.partition("=")
            if sep and key.strip() in ("SMTP_PORT", "HTTP_PORT") and value.strip().isdigit():
                self.ports[key.strip()] = int(value.strip())
        assert not (needed - set(self.ports)), (
            f"sink never announced {sorted(needed)}; saw {self.ports}; stderr: {self._stderr[-20:]}"
        )

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        shutil.rmtree(self.data_dir, ignore_errors=True)


@pytest.fixture
def sink() -> Any:
    """A factory starting ``sink.py`` processes, all stopped at teardown."""
    started: list[SinkProcess] = []

    def start(*args: str) -> SinkProcess:
        process = SinkProcess(*args)
        started.append(process)
        return process

    yield start
    for process in started:
        process.stop()


def _http_json(
    url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None
) -> tuple[int, Any]:
    """One urllib request; returns (status, parsed-json-or-text)."""
    request = urllib.request.Request(  # noqa: S310 (the sink's own 127.0.0.1 port, announced above)
        url, data=data, headers=headers or {}, method=method
    )
    try:
        # nosemgrep: ssrf-requests - the URL is the sink subprocess's announced loopback port
        with urllib.request.urlopen(  # noqa: S310 (same loopback port as the Request above)
            request, timeout=5
        ) as response:
            raw = response.read().decode("utf-8")
            return response.status, (json.loads(raw) if raw.strip().startswith(("{", "[")) else raw)
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, raw


def _json_post(url: str, payload: dict, headers: dict | None = None) -> tuple[int, Any]:
    return _http_json(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
    )


class TestTheMailSink:
    def test_it_stores_and_returns_a_sent_message(self, sink: Any) -> None:
        """SMTP in, read-back out: the exact round the backend's smtplib does."""
        process = sink("smtp", "0", "0")
        process.wait_ports("SMTP_PORT", "HTTP_PORT")

        with smtplib.SMTP("127.0.0.1", process.ports["SMTP_PORT"], timeout=5) as client:
            client.sendmail(
                "ci-sink@nemotron.test",
                ["probe@nemotron.test"],
                "Subject: [LOW] Security Alert\r\n"
                "From: ci-sink@nemotron.test\r\n"
                "To: probe@nemotron.test\r\n"
                "\r\n"
                "sink smoke body",
            )

        status, body = _http_json(f"http://127.0.0.1:{process.ports['HTTP_PORT']}/messages")
        assert status == 200, body
        messages = body["messages"]
        assert len(messages) == 1, messages
        message = messages[0]
        assert message["from"] == "ci-sink@nemotron.test", message
        assert message["to"] == "probe@nemotron.test", message
        assert message["subject"] == "[LOW] Security Alert", message
        assert "sink smoke body" in message["data"], message
        assert message["received_at"], message

    def test_delete_messages_clears_the_store(self, sink: Any) -> None:
        process = sink("smtp", "0", "0")
        process.wait_ports("SMTP_PORT", "HTTP_PORT")
        with smtplib.SMTP("127.0.0.1", process.ports["SMTP_PORT"], timeout=5) as client:
            client.sendmail("a@nemotron.test", ["b@nemotron.test"], "Subject: x\r\n\r\ny")

        status, _ = _http_json(
            f"http://127.0.0.1:{process.ports['HTTP_PORT']}/messages", method="DELETE"
        )
        assert status == 204, status
        _, body = _http_json(f"http://127.0.0.1:{process.ports['HTTP_PORT']}/messages")
        assert body["messages"] == [], body

    def test_it_advertises_no_starttls(self, sink: Any) -> None:
        """The sink is plain; the overlay must set SMTP_USE_TLS=false.

        Pinned from the client side: if the sink advertised STARTTLS a TLS-on
        client would silently downgrade-race it, and a TLS-off backend would
        still work — the pin keeps the pair honest by holding the server to
        "no STARTTLS", so a TLS-on backend fails loudly instead of either
        side guessing.
        """
        process = sink("smtp", "0", "0")
        process.wait_ports("SMTP_PORT", "HTTP_PORT")
        with smtplib.SMTP("127.0.0.1", process.ports["SMTP_PORT"], timeout=5) as client:
            client.ehlo()
            assert "starttls" not in client.esmtp_features, client.esmtp_features

    def test_two_messages_accumulate_in_order(self, sink: Any) -> None:
        process = sink("smtp", "0", "0")
        process.wait_ports("SMTP_PORT", "HTTP_PORT")
        with smtplib.SMTP("127.0.0.1", process.ports["SMTP_PORT"], timeout=5) as client:
            client.sendmail("a@nemotron.test", ["b@nemotron.test"], "Subject: one\r\n\r\n1")
            client.sendmail("a@nemotron.test", ["b@nemotron.test"], "Subject: two\r\n\r\n2")
        _, body = _http_json(f"http://127.0.0.1:{process.ports['HTTP_PORT']}/messages")
        assert [m["subject"] for m in body["messages"]] == ["one", "two"], body


class TestTheRecorderSinks:
    def test_the_webhook_sink_records_posts_and_answers_200(self, sink: Any) -> None:
        process = sink("http", "0", "webhook")
        process.wait_ports("HTTP_PORT")
        url = f"http://127.0.0.1:{process.ports['HTTP_PORT']}"

        status, body = _json_post(f"{url}/hook", {"event_type": "alert_acknowledged", "n": 1})
        assert status == 200, body
        assert body["received"] is True, body

        status, listing = _http_json(f"{url}/requests")
        assert status == 200, listing
        records = listing["requests"]
        assert len(records) == 1, records
        record = records[0]
        assert record["path"] == "/hook", record
        assert json.loads(record["body"]) == {"event_type": "alert_acknowledged", "n": 1}, record
        assert record["headers"]["content-type"] == "application/json", record
        assert record["received_at"], record

        status, _ = _http_json(f"{url}/requests", method="DELETE")
        assert status == 204, status
        _, listing = _http_json(f"{url}/requests")
        assert listing["requests"] == [], listing

    def test_the_push_sink_answers_201_like_a_web_push_service(self, sink: Any) -> None:
        """RFC 8030: a push service answers 201 Created on acceptance.

        B4.3's adapter will judge its own requests by that status, so the fake
        answers it from day one rather than being loosened later.
        """
        process = sink("http", "0", "push")
        process.wait_ports("HTTP_PORT")
        url = f"http://127.0.0.1:{process.ports['HTTP_PORT']}"

        status, body = _json_post(
            f"{url}/push/endpoint-1",
            {"blob": "encrypted-bytes"},
            headers={"TTL": "60", "Authorization": "vapid t=ci-token,k=ci-key"},
        )
        assert status == 201, body

        _, listing = _http_json(f"{url}/requests")
        record = listing["requests"][0]
        assert record["path"] == "/push/endpoint-1", record
        assert record["headers"]["ttl"] == "60", record
        assert record["headers"]["authorization"].startswith("vapid "), record
        assert json.loads(record["body"]) == {"blob": "encrypted-bytes"}, record

    def test_the_recorder_keeps_the_exact_bytes_it_received(self, sink: Any) -> None:
        """``body_b64`` carries the raw request bytes (B4.3's decrypt leg).

        Web Push bodies are AES128GCM ciphertext (RFC 8291) — not valid UTF-8,
        so the text form (``errors="replace"``) mangles them and a golden leg
        could never prove the round-trip against what was actually on the
        wire. The base64 twin decodes to the bytes that arrived; for a plain
        JSON body it is the same payload re-encoded, which this pin asserts
        alongside the text form for a non-ASCII byte too (0xFF has no UTF-8
        meaning, so the text form's fidelity for it is exactly what the
        replacement-scheme gives and no more).
        """
        process = sink("http", "0", "webhook")
        process.wait_ports("HTTP_PORT")
        url = f"http://127.0.0.1:{process.ports['HTTP_PORT']}"

        import urllib.request

        request = urllib.request.Request(  # noqa: S310 (the sink's own 127.0.0.1 port, announced above)
            f"{url}/hook",
            data=b"\xff\xfe binary \x00 bytes",
            method="POST",
        )
        # nosemgrep: ssrf-requests - the URL is the sink subprocess's announced loopback port
        with urllib.request.urlopen(  # noqa: S310 (same loopback port as the Request above)
            request, timeout=5.0
        ) as response:
            assert response.status == 200

        _, listing = _http_json(f"{url}/requests")
        record = listing["requests"][0]
        assert base64.b64decode(record["body_b64"]) == b"\xff\xfe binary \x00 bytes", record

    def test_the_recorder_refuses_unexpected_methods(self, sink: Any) -> None:
        process = sink("http", "0", "webhook")
        process.wait_ports("HTTP_PORT")
        url = f"http://127.0.0.1:{process.ports['HTTP_PORT']}"

        status, _ = _http_json(f"{url}/requests", method="PUT", data=b"{}")
        assert status == 405, status

    def test_both_record_kinds_serve_health(self, sink: Any) -> None:
        for args in (("http", "0", "webhook"), ("http", "0", "push")):
            process = sink(*args)
            process.wait_ports("HTTP_PORT")
            status, body = _http_json(f"http://127.0.0.1:{process.ports['HTTP_PORT']}/health")
            assert status == 200, body
            assert body["ok"] is True, body
