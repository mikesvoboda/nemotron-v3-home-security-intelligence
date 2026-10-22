"""Integration tests for the email delivery channel (B4.2).

The adapter's SMTP conversation is stdlib (``smtplib.SMTP`` with the F9
timeout); the seam the tests drive is the real ``EmailChannel.send`` path —
construction, message build (F13 escaping inside), worker-thread dispatch, and
outcome mapping — with the SMTP wire faked the way the repo's existing email
integration tests do (autospec patch, test_notification_delivery.py idiom).
The message-level contract (headers, escaping, Message-ID) has its own unit
coverage; here the full send path runs and its error mapping is verified.
"""

from __future__ import annotations

import smtplib
from typing import Any

import pytest

from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import DeliveryTask
from backend.services.alerting.channels.email import EmailChannel

pytestmark = pytest.mark.integration


def _task() -> DeliveryTask:
    return DeliveryTask(
        delivery_id="d-email-1",
        channel_id="ch-email",
        channel_kind=DeliveryChannelKind.EMAIL,
        recipient_id="rec-1",
        idempotency_key="idem-email-1",
        payload={"title": "Person at the door", "summary": "A summary", "severity": "high"},
        include_names=False,
        target="household@example.com",
    )


def _channel(**kw: Any) -> EmailChannel:
    base: dict[str, Any] = {
        "smtp_host": "smtp.example.test",
        "smtp_port": 587,
        "smtp_from": "alerts@example.test",
        "use_tls": True,
    }
    base.update(kw)
    return EmailChannel(**base)


class TestEmailChannelSendPath:
    async def test_send_runs_the_real_path_and_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Full send path: build_message -> to_thread -> SMTP conversation."""
        captured: dict[str, Any] = {}

        class FakeSMTP:
            def __init__(self, host: str, port: int, timeout: Any = None) -> None:
                captured["host"] = host
                captured["port"] = port
                captured["timeout"] = timeout

            def __enter__(self) -> FakeSMTP:
                return self

            def __exit__(self, *a: Any) -> None:
                return None

            def starttls(self, context: Any = None) -> None:
                captured["tls"] = True

            def send_message(self, msg: Any) -> None:
                captured["msg"] = msg

        monkeypatch.setattr("backend.services.alerting.channels.email.smtplib.SMTP", FakeSMTP)
        result = await _channel().send(_task())
        assert result.success is True
        assert result.error is None
        # F9: the connect/read timeout is passed to the socket, not the asyncio
        # wrapper only — the thread-side conversation is bounded.
        assert captured["timeout"] == 30.0
        assert captured["tls"] is True
        # The message that reached the wire carries the idempotency Message-ID.
        assert str(captured["msg"]["Message-ID"]).replace(" ", "") == (
            "<idem-email-1@alerts.nemotron.local>"
        )

    async def test_starttls_unsupported_falls_back_to_plain(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A server that does not offer STARTTLS still gets the mail."""

        class NoTLS_SMTP:
            def __init__(self, host: str, port: int, timeout: Any = None) -> None:
                pass

            def __enter__(self) -> NoTLS_SMTP:
                return self

            def __exit__(self, *a: Any) -> None:
                return None

            def starttls(self, context: Any = None) -> None:
                raise smtplib.SMTPNotSupportedError("no tls")

            def send_message(self, msg: Any) -> None:
                pass

        monkeypatch.setattr("backend.services.alerting.channels.email.smtplib.SMTP", NoTLS_SMTP)
        result = await _channel().send(_task())
        assert result.success is True

    async def test_smtp_exception_maps_to_smtp_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FailingSMTP:
            def __init__(self, *a: Any, **kw: Any) -> None:
                pass

            def __enter__(self) -> FailingSMTP:
                return self

            def __exit__(self, *a: Any) -> None:
                return None

            def starttls(self, context: Any = None) -> None:
                pass

            def send_message(self, msg: Any) -> None:
                raise smtplib.SMTPException("relay refused")

        monkeypatch.setattr("backend.services.alerting.channels.email.smtplib.SMTP", FailingSMTP)
        result = await _channel().send(_task())
        assert result.success is False
        assert result.error is not None and result.error.startswith("smtp_error")

    async def test_unconfigured_host_fails_closed_before_connecting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty smtp_host fails without touching the network."""

        def _boom(*a: Any, **kw: Any) -> None:
            raise AssertionError("SMTP must not be constructed when unconfigured")

        monkeypatch.setattr("backend.services.alerting.channels.email.smtplib.SMTP", _boom)
        result = await _channel(smtp_host="").send(_task())
        assert result.success is False
        assert result.error == "email_not_configured: smtp_host unset"
