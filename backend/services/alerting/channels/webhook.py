"""Webhook channel adapter (B4.2).

Sends alert deliveries to a per-recipient webhook URL, signed with the F-246
HMAC convention the outbound-webhook service already uses (HMAC-SHA256 over the
sorted-keys compact JSON, `X-Webhook-Signature: sha256=<hex>`), plus an explicit
idempotency header so receivers can dedupe.

F12: the channel's `on_local_network` flag relaxes URL policy to RFC1918 /
unique-local targets, internal domain suffixes and plain HTTP — loopback,
metadata endpoints and link-local stay blocked for every channel. The send
resolves and validates at request time and pins the connection to the validated
address (DNS rebinding between validate and connect cannot win): the client's
transport refuses to send unless the host still resolves to the pinned address
(the shared transport in ``backend.core.url_validation``, used by both webhook
families).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import socket
from urllib.parse import urlparse

import httpx

from backend.core.url_validation import (
    SSRFValidationError,
    pinned_httpx_client,
    validate_and_resolve_for_send,
)
from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import Channel, DeliveryTask, SendResult

_TIMEOUT_SECONDS = 10.0


def sign_payload(payload: dict, secret: str) -> str:
    """HMAC-SHA256 over the sorted-keys compact JSON bytes (F-246 convention).

    Mirrors backend/services/webhook_service.py:_sign_payload exactly so
    receivers verify both webhook families with one code path.
    """
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    secret_bytes = bytes.fromhex(secret)
    return hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()


def _build_client(url: str, pinned_ip: str) -> httpx.AsyncClient:
    """Client that refuses to send if the host stops resolving to the pinned IP."""
    return pinned_httpx_client(url, pinned_ip, timeout=_TIMEOUT_SECONDS)


class WebhookChannel(Channel):
    """Deliver alerts to a recipient-owned webhook endpoint."""

    kind = DeliveryChannelKind.WEBHOOK

    async def send(self, task: DeliveryTask) -> SendResult:
        url = task.target
        try:
            _validated, pinned_ip = validate_and_resolve_for_send(
                url,
                allow_local_network=task.on_local_network,
            )
        except SSRFValidationError as exc:
            return SendResult(success=False, error=f"url_policy: {exc}")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NemotronAlertDelivery/1.0",
            "X-Delivery-Idempotency-Key": task.idempotency_key,
        }
        if task.signing_secret:
            headers["X-Webhook-Signature"] = (
                f"sha256={sign_payload(task.payload, task.signing_secret)}"
            )

        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        literal_ip = _is_literal_ip(hostname)
        client = (
            httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
            if literal_ip
            else _build_client(url, pinned_ip)
        )
        try:
            async with client:
                response = await client.post(url, json=task.payload, headers=headers)
        except httpx.TimeoutException as exc:
            return SendResult(success=False, error=f"timeout: {exc}")
        except httpx.RequestError as exc:
            return SendResult(success=False, error=f"request_error: {exc}")

        if 200 <= response.status_code < 300:
            return SendResult(success=True, meta={"status_code": response.status_code})
        return SendResult(
            success=False,
            error=f"http_{response.status_code}",
            meta={"status_code": response.status_code},
        )


def _is_literal_ip(hostname: str) -> bool:
    try:
        socket.inet_pton(socket.AF_INET, hostname)
        return True
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, hostname)
        return True
    except OSError:
        return False


__all__ = ["WebhookChannel", "sign_payload"]
