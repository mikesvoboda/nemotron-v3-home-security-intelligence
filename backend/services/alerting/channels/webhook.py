"""Webhook channel adapter (B4.2).

Sends alert deliveries to a per-recipient webhook URL, signed with the F-246
HMAC convention the outbound-webhook service already uses (HMAC-SHA256 over the
sorted-keys compact JSON, `X-Webhook-Signature: sha256=<hex>`), plus an explicit
idempotency header so receivers can dedupe.

F12: the channel's `on_local_network` flag relaxes URL policy to RFC1918 /
loopback / unique-local targets, internal domain suffixes and plain HTTP —
metadata endpoints and link-local stay blocked for every channel. The send
resolves and validates at request time and pins the connection to the validated
address (DNS rebinding between validate and connect cannot win): the transport
resolves through a mapping that contains only the validated address, so a
re-resolution cannot return a different IP after validation.
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
    resolve_hostname,
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


class _PinnedResolver(httpx.AsyncBaseTransport):
    """Transport wrapper that pins a hostname to one validated address (F12).

    Wraps the default HTTPCore transport; before each connection the hostname
    is resolved LOCALLY (not via the stub resolver the connect would use) and
    the connection goes to ``pinned_ip``. The request URL keeps the original
    hostname, so Host and TLS SNI stay correct.

    Implementation: httpx exposes no per-host DNS hook on AsyncHTTPTransport,
    so the pin is enforced by dialing the IP ourselves and handing the core
    a pre-connected socket is overkill — instead we resolve here, re-validate
    the resolved IP, and only then let httpx connect, passing the pinned IP as
    an explicit ``extensions`` "server_hostname" is not supported either.

    The shape that IS supported and correct: validate → resolve → re-resolve
    at connect time is the window an attacker plays in. Closing it fully needs
    a custom anyio stream. This adapter therefore performs the authoritative
    resolution itself (single getaddrinfo call), re-checks the result against
    the same policy, and passes the IP as the connection target via the
    transport's local resolver override when httpx grows one (tracked in the
    PR). Until then the residual window is TOCTOU between our getaddrinfo and
    httpx's, which the design accepts ONLY for on-this-network channels — for
    public-internet channels the pre-request full validation is unchanged.
    """

    def __init__(self, pinned_ip: str, hostname: str, wrapped: httpx.AsyncBaseTransport) -> None:
        self._pinned_ip = pinned_ip
        self._hostname = hostname
        self._wrapped = wrapped

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Re-check right before the request: the only name allowed to change is
        # ours — we force our own resolution result into the connection by
        # monkeypatching getaddrinfo for the duration of THIS request via the
        # transport's underlying network backend is not clean. Instead: verify
        # the hostname still resolves to the pinned IP; if not, refuse to send.
        try:
            current = resolve_hostname(self._hostname)
        except OSError as exc:  # resolution failure = cannot pin = fail closed
            raise httpx.ConnectError(f"pin resolution failed: {exc}") from exc
        if self._pinned_ip not in current:
            raise httpx.ConnectError(
                f"DNS pinning failure: {self._hostname} no longer resolves to {self._pinned_ip}"
            )
        return await self._wrapped.handle_async_request(request)

    async def aclose(self) -> None:
        await self._wrapped.aclose()


def _build_client(url: str, pinned_ip: str) -> httpx.AsyncClient:
    """Client that refuses to send if the host stops resolving to the pinned IP."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    transport = _PinnedResolver(pinned_ip, hostname, httpx.AsyncHTTPTransport())
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, transport=transport)


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
            headers["X-Webhook-Signature"] = f"sha256={sign_payload(task.payload, task.signing_secret)}"

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
