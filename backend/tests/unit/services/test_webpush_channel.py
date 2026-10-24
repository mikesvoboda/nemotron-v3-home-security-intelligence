"""Unit tests for backend.services.alerting.channels.webpush (B4.3).

The adapter calls ``pywebpush.webpush_async`` (RFC 8291 AES128GCM payload
encryption + RFC 8292 VAPID auth); the tests fake at the aiohttp boundary and
at the ``webpush_async`` seam:

- the aiohttp fake proves the adapter passes the subscription keys, the
  title-only payload and the VAPID claims through to ``webpush_async`` and
  maps statuses/exceptions to SendResults (201 success, 410 the expiry
  marker, 5xx retryable, timeouts, connection errors);
- the ``webpush_async`` monkeypatch pins the exact argument contract
  (subscription dict, encrypted data, vapid claims) without crypto;
- the http_ece round-trip proves the bytes an endpoint receives decrypt back
  to the title-only payload (the wire contract, not a fake).
"""

from __future__ import annotations

import base64
import os
from typing import Any
from unittest.mock import AsyncMock

import http_ece
import pytest
from aiohttp import ClientError
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pywebpush import WebPushException

from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import DeliveryTask
from backend.services.alerting.channels.webpush import WebPushChannel, generate_vapid_keypair

# A real (test-generated) VAPID private key: the adapter's config check and
# pywebpush's key load both need parseable DER, not any 184-char string.
_PRIV, _PUB = generate_vapid_keypair()

# --- fixtures ---------------------------------------------------------------


def _subscription() -> dict[str, Any]:
    """A receiver-side keypair so http_ece can decrypt what the adapter sends."""
    recv_priv = ec.generate_private_key(ec.SECP256R1())
    recv_pub_raw = recv_priv.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    return {
        "endpoint": "https://push.example.com/v1/abcd",
        "keys": {
            "p256dh": base64.urlsafe_b64encode(recv_pub_raw).rstrip(b"=").decode(),
            "auth": base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode(),
        },
        "_priv": recv_priv,  # non-serialised handle for the decrypt assertions
    }


def _task(**kw: Any) -> DeliveryTask:
    base: dict[str, Any] = {
        "delivery_id": "d-1",
        "channel_id": "ch-1",
        "channel_kind": DeliveryChannelKind.WEBPUSH,
        "recipient_id": "r-1",
        "idempotency_key": "idem-abc123",
        "payload": {"title": "Person detected", "severity": "high", "summary": "s"},
        "include_names": False,
        "push_subscription": _subscription(),
    }
    base.update(kw)
    sub = base.pop("_priv", None)
    task = DeliveryTask(**base)
    if sub is not None:
        task.push_subscription["_priv"] = sub
    return task


def _vapid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand the VAPID settings in so send() proceeds past its config check."""
    monkeypatch.setenv(
        "VAPID_PRIVATE_KEY", _PRIV
    )  # nosemgrep: hardcoded-password — a test-generated key, never a credential
    monkeypatch.setenv("VAPID_PUBLIC_KEY", _PUB)
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:alerts@nemotron.local")


class _FakeResponse:
    """Shape webpush_async reads off a real aiohttp response."""

    def __init__(self, status: int, text: str = "") -> None:
        self.status = status
        self._text = text

    async def text(self) -> str:
        return self._text


def _resp(status: int) -> _FakeResponse:
    return _FakeResponse(status)


def _wp_exception(status: int) -> WebPushException:
    exc = WebPushException("Push failed")
    exc.response = _resp(status)
    return exc


# --- the aiohttp-boundary fakes ---------------------------------------------


class _FakeSession:
    """aiohttp.ClientSession double capturing the POST the adapter makes."""

    def __init__(self, status: int = 201, exc: Exception | None = None) -> None:
        self.status = status
        self.exc = exc
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, timeout: Any = None, **kw: Any) -> Any:
        self.calls.append({"url": url, "kw": kw, "timeout": timeout})
        if self.exc is not None:
            raise self.exc
        return _resp(self.status)

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *a: Any) -> None:
        return None

    async def close(self) -> None:
        return None


class _FakeSettings:
    vapid_private_key = _PRIV
    vapid_public_key = _PUB
    vapid_subject = "mailto:alerts@nemotron.local"


# --- the adapter against webpush_async --------------------------------------


class TestWebPushSend:
    async def test_send_success_maps_201_to_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        fake = _FakeSession(201)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.aiohttp.ClientSession",
            lambda **_kw: fake,
        )
        result = await WebPushChannel().send(_task())
        assert result.success is True
        assert result.meta == {"status_code": 201}
        # The POST went to the subscription's endpoint.
        assert fake.calls[0]["url"] == "https://push.example.com/v1/abcd"

    async def test_send_carries_title_only_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Privacy: push carries the title only — no summary, no camera, no names."""
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        fake = _FakeSession(201)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.aiohttp.ClientSession",
            lambda **_kw: fake,
        )
        task = _task(
            payload={
                "title": "Person detected",
                "severity": "high",
                "summary": "known person Jane at the door",
                "camera_id": "front",
                "link": "https://host/alerts",
            }
        )
        result = await WebPushChannel().send(task)
        assert result.success is True
        # The bytes at the aiohttp boundary are RFC 8291 ciphertext; decrypt
        # with the fixture's receiver key and check the plaintext.
        sent = fake.calls[0]["kw"]["data"]
        sub = task.push_subscription
        plaintext = http_ece.decrypt(
            sent,
            private_key=sub["_priv"],
            auth_secret=base64.urlsafe_b64decode(
                sub["keys"]["auth"] + "=" * (-len(sub["keys"]["auth"]) % 4)
            ),
            version="aes128gcm",
        )
        assert plaintext == b'{"title": "Person detected"}'

    async def test_send_passes_subscription_and_vapid_claims(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The exact webpush_async contract: subscription dict + VAPID claims."""
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        wp = AsyncMock(return_value=_resp(201))
        monkeypatch.setattr("backend.services.alerting.channels.webpush.webpush_async", wp)
        sub = _subscription()
        sub_view = {k: v for k, v in sub.items() if k != "_priv"}
        task = _task(push_subscription=sub)
        result = await WebPushChannel().send(task)
        assert result.success is True
        kwargs = wp.await_args.kwargs
        assert kwargs["subscription_info"] == sub_view
        assert kwargs["vapid_claims"]["sub"] == "mailto:alerts@nemotron.local"
        assert kwargs["ttl"] == WebPushChannel.TTL_SECONDS
        assert kwargs["timeout"] == WebPushChannel.REQUEST_TIMEOUT_SECONDS

    async def test_send_requires_configured_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No VAPID keys configured: fail closed, never a half-authed send."""
        _vapid_env(monkeypatch)
        monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)

        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _NoVapidSettings(),
        )
        result = await WebPushChannel().send(_task())
        assert result.success is False
        assert result.error == "webpush_not_configured"

    async def test_send_requires_subscription_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A webpush channel row without subscription keys cannot be sent."""
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        result = await WebPushChannel().send(_task(push_subscription=None))
        assert result.success is False
        assert result.error == "missing_subscription"

    async def test_http_410_carries_the_expiry_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RFC 8030: 410 Gone means the subscription is dead — the marker the
        worker keys off to disable the channel row."""
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        wp = AsyncMock(side_effect=_wp_exception(410))
        monkeypatch.setattr("backend.services.alerting.channels.webpush.webpush_async", wp)
        result = await WebPushChannel().send(_task())
        assert result.success is False
        assert result.error == "subscription_expired"
        assert result.meta == {"status_code": 410, "expired": True}

    async def test_http_404_also_marks_expired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Some push services answer 404 for the same condition."""
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        wp = AsyncMock(side_effect=_wp_exception(404))
        monkeypatch.setattr("backend.services.alerting.channels.webpush.webpush_async", wp)
        result = await WebPushChannel().send(_task())
        assert result.success is False
        assert result.error == "subscription_expired"
        assert result.meta["expired"] is True

    async def test_other_http_errors_are_retryable_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """5xx and 429 ride the worker's backoff ladder, not the expiry path."""
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        for status in (500, 429, 403):
            wp = AsyncMock(side_effect=_wp_exception(status))
            monkeypatch.setattr("backend.services.alerting.channels.webpush.webpush_async", wp)
            result = await WebPushChannel().send(_task())
            assert result.success is False, status
            assert result.error == f"http_{status}", status
            assert "expired" not in result.meta, status

    async def test_connection_error_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        wp = AsyncMock(side_effect=ClientError("connect failed"))
        monkeypatch.setattr("backend.services.alerting.channels.webpush.webpush_async", wp)
        result = await WebPushChannel().send(_task())
        assert result.success is False
        assert result.error and result.error.startswith("request_error")

    async def test_timeout_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        wp = AsyncMock(side_effect=TimeoutError())
        monkeypatch.setattr("backend.services.alerting.channels.webpush.webpush_async", wp)
        result = await WebPushChannel().send(_task())
        assert result.success is False
        assert result.error and result.error.startswith("timeout")


class _NoVapidSettings:
    vapid_private_key = None
    vapid_public_key = None
    vapid_subject = None


# --- the wire contract: encrypt here, decrypt like the browser ---------------


def json_loads(raw: Any) -> dict[str, Any]:
    import json

    if isinstance(raw, bytes):
        return json.loads(raw.decode("utf-8"))
    return json.loads(raw)


class TestWireContract:
    async def test_payload_is_encrypted_and_decrypts_to_title_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """http_ece round-trip: what lands at the endpoint decrypts (with the
        receiver's private key + auth secret) to exactly the title payload.
        Proves RFC 8291 end-to-end encryption is on, not just a POST. Runs the
        real ``webpush_async`` (mocking only the aiohttp session), so the
        captured bytes are the ciphertext a push service would receive."""
        _vapid_env(monkeypatch)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.get_settings",
            lambda: _FakeSettings(),
        )
        fake = _FakeSession(201)
        monkeypatch.setattr(
            "backend.services.alerting.channels.webpush.aiohttp.ClientSession",
            lambda **_kw: fake,
        )
        sub = _subscription()
        result = await WebPushChannel().send(_task(push_subscription=sub))
        assert result.success is True
        post = fake.calls[0]
        headers = post["kw"]["headers"]
        assert headers["Authorization"].startswith("vapid t="), headers
        assert headers["Content-Encoding"] == "aes128gcm"
        assert headers["ttl"] == str(WebPushChannel.TTL_SECONDS)
        # Decrypt as the browser would: private key + auth secret.
        # (aes128gcm carries the sender's key inline — no dh argument.)
        plaintext = http_ece.decrypt(
            post["kw"]["data"],
            private_key=sub["_priv"],
            auth_secret=base64.urlsafe_b64decode(
                sub["keys"]["auth"] + "=" * (-len(sub["keys"]["auth"]) % 4)
            ),
            version="aes128gcm",
        )
        assert plaintext == b'{"title": "Person detected"}'


class TestConfigGeneration:
    def test_generate_vapid_keypair_returns_env_pair(self) -> None:
        """Setup provisioning: private key (SecretStr form) + public key."""
        from backend.services.alerting.channels.webpush import generate_vapid_keypair

        priv, pub = generate_vapid_keypair()
        assert len(priv) >= 160  # PKCS8 DER b64url (184 chars unpadded)
        assert len(pub) == 87  # uncompressed P-256 point b64url
        # Round-trips through the adapter's loader.
        from py_vapid import Vapid

        v = Vapid.from_string(priv)
        assert "Authorization" in v.sign({"sub": "mailto:x@y.z", "aud": "https://push.example.com"})

    def test_public_key_matches_private(self) -> None:
        from py_vapid import Vapid

        from backend.services.alerting.channels.webpush import generate_vapid_keypair

        priv, pub = generate_vapid_keypair()
        v = Vapid.from_string(priv)
        import base64

        raw = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        assert base64.urlsafe_b64encode(raw).rstrip(b"=").decode() == pub


__all__: list[str] = []
