"""Email channel adapter (B4.2).

Sends alert deliveries as email, fixing the F9 defect on this path: the SMTP
connection gets an explicit ``timeout=`` (notification.py:278/:288 left it off).
Message bodies are HTML-escaped (F13). The idempotency key is the Message-ID so
retaining mail servers dedupe re-sends.

This adapter does NOT reuse NotificationService.send_email — that call path is
the Settings-page test-send and legacy alert mail; the delivery path needs the
timeout, the escaping, and the idempotency header.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import Channel, DeliveryTask, SendResult
from backend.services.alerting.redact import escape_html

_TIMEOUT_SECONDS = 30.0


def build_message(
    task: DeliveryTask,
    smtp_from: str,
) -> EmailMessage:
    """Build the email for one delivery. HTML-escaped body (F13)."""
    payload = task.payload
    msg = EmailMessage()
    msg["Subject"] = f"[{str(payload.get('severity', '')).upper()}] {payload.get('title', 'Security alert')}"
    msg["From"] = smtp_from
    msg["To"] = task.target
    # Message-ID is the idempotency key: re-sends are dedupable end to end.
    msg["Message-ID"] = f"<{task.idempotency_key}@alerts.nemotron.local>"
    summary = escape_html(str(payload.get("summary", "")))
    title = escape_html(str(payload.get("title", "Security alert")))
    camera = escape_html(str(payload.get("camera_id", "")))
    severity = escape_html(str(payload.get("severity", "")).upper())
    link = str(payload.get("link", ""))
    html_body = (
        f"<html><body>"
        f"<h2>{title}</h2>"
        f"<p><strong>Severity:</strong> {severity} &nbsp; <strong>Camera:</strong> {camera}</p>"
        f"<p>{summary}</p>"
        + (f'<p><a href="{escape_html(link)}">View in dashboard</a></p>' if link else "")
        + f"</body></html>"
    )
    msg.set_content(summary)
    msg.add_alternative(html_body, subtype="html")
    return msg


class EmailChannel(Channel):
    """Deliver alerts by email with a bounded SMTP connect/read timeout (F9)."""

    kind = DeliveryChannelKind.EMAIL

    def __init__(self, *, smtp_host: str, smtp_port: int, smtp_from: str, use_tls: bool = True) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_from = smtp_from
        self._use_tls = use_tls

    async def send(self, task: DeliveryTask) -> SendResult:
        if not self._smtp_host:
            return SendResult(success=False, error="email_not_configured: smtp_host unset")
        msg = build_message(task, self._smtp_from)
        try:
            # Send outside the event loop's critical path: the SMTP conversation
            # is blocking, so run it in a worker thread with a socket timeout.
            await asyncio.wait_for(
                asyncio.to_thread(self._send_sync, msg),
                timeout=_TIMEOUT_SECONDS + 10.0,
            )
        except TimeoutError:
            return SendResult(success=False, error=f"timeout after {_TIMEOUT_SECONDS}s")
        except (smtplib.SMTPException, OSError) as exc:
            return SendResult(success=False, error=f"smtp_error: {exc}")
        return SendResult(success=True)

    def _send_sync(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(
            self._smtp_host,
            self._smtp_port,
            timeout=_TIMEOUT_SECONDS,  # F9: the connect AND read timeout
        ) as smtp:
            if self._use_tls:
                context = ssl.create_default_context()
                try:
                    smtp.starttls(context=context)
                except smtplib.SMTPNotSupportedError:
                    pass  # server does not offer STARTTLS; plain send
            smtp.send_message(msg)


__all__ = ["EmailChannel", "build_message"]
