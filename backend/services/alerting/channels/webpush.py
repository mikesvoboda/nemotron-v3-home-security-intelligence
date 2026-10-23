"""Web Push channel adapter (B4.3).

Sends alert deliveries to a browser's Web Push subscription (RFC 8030) with
RFC 8291 AES128GCM payload encryption and RFC 8292 VAPID authentication, via
``pywebpush`` 2.5.0. The payload carried is the **title only** (4n-alerting.md,
privacy: "push carries the title only") — no summary, no camera, no names; the
bytes on the wire are additionally encrypted end to end to the subscription's
p256dh key, so the push service never sees the content either.

The VAPID private key stays out of the database (``.env`` or a secret file,
4n-alerting.md:186): the adapter reads it from settings at send time. HTTP 410
(and 404, the other shape push services use for the same condition) means the
subscription is gone: the SendResult carries the ``subscription_expired`` marker
the worker keys off to disable the channel row, so the recipient's settings
show the channel switched off (4n-alerting.md:236).
"""

from __future__ import annotations

import json
from typing import Any

import aiohttp
from pywebpush import webpush_async

from backend.core.config import get_settings
from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import Channel, DeliveryTask, SendResult

# RFC 8030: the TTL the push service holds the message for if the browser is
# offline — one hour covers a household away-from-home window without pinning
# stale alerts on a device that comes back days later.
_TTL_SECONDS = 3600

_REQUEST_TIMEOUT_SECONDS = 12.0  # worker's CHANNEL_TIMEOUT_SECONDS for webpush


def generate_vapid_keypair() -> tuple[str, str]:
    """Generate a VAPID key pair for setup provisioning (setup_lib writes these).

    Returns ``(private_key, public_key)`` as urlsafe-base64 strings:
    the private key is PKCS8 DER (what ``Vapid.from_string`` loads), the
    public key the raw uncompressed P-256 point (what a browser hands the
    push service as ``applicationServerKey``). The private key goes to
    ``.env`` (600, owner read/write) and never to the database.
    """
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from py_vapid import Vapid

    key = ec.generate_private_key(ec.SECP256R1())
    vapid = Vapid()
    vapid.private_key = key
    priv = base64.urlsafe_b64encode(
        key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    ).rstrip(b"=")
    pub = base64.urlsafe_b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
    ).rstrip(b"=")
    return priv.decode(), pub.decode()


def _subscription_of(task: DeliveryTask) -> dict[str, Any] | None:
    """The subscription dict a pywebpush call needs, or None when absent.

    The channel row's ``push_subscription`` JSONB holds
    ``{"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}`` — the shape
    ``PushSubscriptionJSON`` gives the browser's
    ``serviceWorkerRegistration.pushManager.subscribe()``.
    """
    sub = task.push_subscription
    if not isinstance(sub, dict):
        return None
    endpoint = sub.get("endpoint")
    keys = sub.get("keys")
    if not endpoint or not isinstance(keys, dict):
        return None
    if not keys.get("p256dh") or not keys.get("auth"):
        return None
    return {"endpoint": endpoint, "keys": dict(keys)}


class WebPushChannel(Channel):
    """Deliver alerts to a browser's Web Push subscription."""

    kind = DeliveryChannelKind.WEBPUSH

    REQUEST_TIMEOUT_SECONDS = _REQUEST_TIMEOUT_SECONDS
    TTL_SECONDS = _TTL_SECONDS

    async def send(self, task: DeliveryTask) -> SendResult:  # noqa: PLR0911 — outcome mapping: one exit per error class
        settings = get_settings()
        private_key = settings.vapid_private_key
        if private_key is None:
            return SendResult(success=False, error="webpush_not_configured")
        subscription = _subscription_of(task)
        if subscription is None:
            return SendResult(success=False, error="missing_subscription")

        subject = settings.vapid_subject or "mailto:alerts@nemotron.local"
        # Privacy (4n-alerting.md privacy section): push carries the title
        # only. No summary, camera, link or names travel on this channel.
        title = str(task.payload.get("title") or "Security alert")
        body = json.dumps({"title": title}).encode("utf-8")

        try:
            response = await webpush_async(
                subscription_info=subscription,
                data=body,
                vapid_private_key=(
                    private_key.get_secret_value()
                    if hasattr(private_key, "get_secret_value")
                    else private_key
                ),
                vapid_claims={"sub": subject},
                ttl=WebPushChannel.TTL_SECONDS,
                timeout=WebPushChannel.REQUEST_TIMEOUT_SECONDS,
            )
        except aiohttp.ClientError as exc:
            return SendResult(success=False, error=f"request_error: {exc}")
        except TimeoutError as exc:
            return SendResult(success=False, error=f"timeout: {exc}")
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status", None)
            if status in (410, 404):
                # The subscription is gone (RFC 8030 6.1): the worker disables
                # the channel row on this marker so the recipient's settings
                # show it switched off.
                return SendResult(
                    success=False,
                    error="subscription_expired",
                    meta={"status_code": status, "expired": True},
                )
            if isinstance(status, int):
                return SendResult(
                    success=False,
                    error=f"http_{status}",
                    meta={"status_code": status},
                )
            if isinstance(exc, ValueError):
                # Malformed subscription/keys (bad b64, wrong lengths) —
                # retrying cannot fix it, but it is not an expiry either.
                return SendResult(success=False, error=f"subscription_invalid: {exc}")
            return SendResult(success=False, error=f"push_error: {exc!r}")

        status = getattr(response, "status", None)
        if status is not None and 200 <= status < 300:
            return SendResult(success=True, meta={"status_code": status})
        return SendResult(
            success=False,
            error=f"http_{status}",
            meta={"status_code": status} if isinstance(status, int) else {},
        )


__all__ = ["WebPushChannel", "generate_vapid_keypair"]
