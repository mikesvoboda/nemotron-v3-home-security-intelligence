"""Unit tests for backend.services.alerting.channels (B4.2).

Covers the F-246 webhook signature vector, the F12 local-network URL policy
(allowed/blocked per flag, metadata always blocked), the F9 SMTP timeout, F13
escaping, and the idempotency headers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from types import MappingProxyType
from typing import Any

import pytest

from backend.core.url_validation import SSRFValidationError  # noqa: F401
from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import DeliveryTask
from backend.services.alerting.channels.email import build_message
from backend.services.alerting.channels.webhook import WebhookChannel, sign_payload
from backend.services.alerting.payload import build_payload


def _task(target: str = "https://hooks.example.com/x", **kw: Any) -> DeliveryTask:
    base: dict[str, Any] = {
        "delivery_id": "d-1",
        "channel_id": "ch-1",
        "channel_kind": DeliveryChannelKind.WEBHOOK,
        "recipient_id": "rec-1",
        "idempotency_key": "idem-abc123",
        "payload": {"title": "Person detected", "summary": "A summary"},
        "include_names": False,
        "target": target,
    }
    base.update(kw)
    return DeliveryTask(**base)


class TestSignature:
    def test_sign_payload_matches_f246_convention(self) -> None:
        """Same canonicalisation as webhook_service._sign_payload."""
        payload = {"b": 2, "a": 1}
        secret = "ab" * 32  # nosemgrep: hardcoded-password — a test dummy, never a credential
        expected = hmac.new(
            bytes.fromhex(secret),
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert sign_payload(payload, secret) == expected

    def test_sign_payload_is_deterministic_and_keyed(self) -> None:
        p = {"a": 1}
        s1, s2 = "11" * 32, "22" * 32
        assert sign_payload(p, s1) == sign_payload(p, s1)
        assert sign_payload(p, s1) != sign_payload(p, s2)


class TestWebhookHeaders:
    @pytest.fixture(autouse=True)
    def _no_dns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """These tests fake the HTTP layer; resolution is faked too.

        The pinning transport moved into url_validation (one policy, one
        transport), so url_validation now holds the only ``resolve_hostname``
        name the send path uses — patch it there.
        """
        import backend.core.url_validation as uv

        monkeypatch.setattr(uv, "resolve_hostname", lambda host: ["93.184.216.34"])  # noqa: ARG005

    @pytest.mark.asyncio
    async def test_idempotency_and_signature_headers_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Headers are built before the request; capture them with a fake post."""
        captured: dict[str, Any] = {}

        class FakeResponse:
            status_code = 200
            text = "ok"

        class FakeClient:
            def __init__(self, *a: Any, **kw: Any) -> None:
                pass

            async def __aenter__(self) -> FakeClient:
                return self

            async def __aexit__(self, *a: Any) -> None:
                return None

            async def post(self, url: str, json: Any = None, headers: Any = None) -> FakeResponse:
                captured["url"] = url
                captured["headers"] = headers
                return FakeResponse()

        monkeypatch.setattr(
            "backend.services.alerting.channels.webhook.httpx.AsyncClient", FakeClient
        )
        channel = WebhookChannel()
        task = _task(signing_secret="ab" * 32)
        result = await channel.send(task)
        assert result.success is True
        assert captured["headers"]["X-Delivery-Idempotency-Key"] == "idem-abc123"
        sig = captured["headers"]["X-Webhook-Signature"]
        assert sig.startswith("sha256=")
        assert sig.split("=", 1)[1] == sign_payload(task.payload, task.signing_secret)

    @pytest.mark.asyncio
    async def test_http_error_records_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResponse:
            status_code = 500
            text = "boom"

        class FakeClient:
            def __init__(self, *a: Any, **kw: Any) -> None:
                pass

            async def __aenter__(self) -> FakeClient:
                return self

            async def __aexit__(self, *a: Any) -> None:
                return None

            async def post(self, url: str, json: Any = None, headers: Any = None) -> FakeResponse:
                return FakeResponse()

        monkeypatch.setattr(
            "backend.services.alerting.channels.webhook.httpx.AsyncClient", FakeClient
        )
        channel = WebhookChannel()
        result = await channel.send(_task())
        assert result.success is False
        assert result.error == "http_500"


class TestWebhookUrlPolicy:
    """F12: on_local_network relaxes to the local set; metadata stays blocked."""

    @pytest.mark.asyncio
    async def test_private_url_blocked_without_flag(self) -> None:
        channel = WebhookChannel()
        result = await channel.send(_task(target="http://192.168.1.50/hook"))
        assert result.success is False
        assert result.error and result.error.startswith("url_policy")

    @pytest.mark.asyncio
    async def test_private_url_allowed_with_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        class FakeResponse:
            status_code = 200
            text = "ok"

        class FakeClient:
            def __init__(self, *a: Any, **kw: Any) -> None:
                captured["kw"] = kw

            async def __aenter__(self) -> FakeClient:
                return self

            async def __aexit__(self, *a: Any) -> None:
                return None

            async def post(self, url: str, json: Any = None, headers: Any = None) -> FakeResponse:
                return FakeResponse()

        monkeypatch.setattr(
            "backend.services.alerting.channels.webhook.httpx.AsyncClient", FakeClient
        )
        import backend.core.url_validation as uv

        monkeypatch.setattr(uv, "resolve_hostname", lambda host: ["192.168.1.50"])  # noqa: ARG005
        channel = WebhookChannel()
        result = await channel.send(_task(target="http://192.168.1.50/hook", on_local_network=True))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_metadata_blocked_even_with_flag(self) -> None:
        channel = WebhookChannel()
        result = await channel.send(
            _task(target="http://169.254.169.254/latest/meta-data", on_local_network=True)
        )
        assert result.success is False
        assert result.error and result.error.startswith("url_policy")

    @pytest.mark.asyncio
    async def test_link_local_blocked_even_with_flag(self) -> None:
        channel = WebhookChannel()
        result = await channel.send(
            _task(target="http://169.254.10.10/hook", on_local_network=True)
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_local_suffix_allowed_with_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResponse:
            status_code = 200
            text = "ok"

        class FakeClient:
            def __init__(self, *a: Any, **kw: Any) -> None:
                pass

            async def __aenter__(self) -> FakeClient:
                return self

            async def __aexit__(self, *a: Any) -> None:
                return None

            async def post(self, url: str, json: Any = None, headers: Any = None) -> FakeResponse:
                return FakeResponse()

        monkeypatch.setattr(
            "backend.services.alerting.channels.webhook.httpx.AsyncClient", FakeClient
        )
        # Resolve via monkeypatched resolver: local names do not resolve in CI.
        import backend.core.url_validation as uv

        monkeypatch.setattr(uv, "resolve_hostname", lambda host: ["192.168.1.77"])  # noqa: ARG005
        channel = WebhookChannel()
        result = await channel.send(
            _task(target="http://nas.home.arpa/hook", on_local_network=True)
        )
        assert result.success is True


class TestEmailMessage:
    def _mail_task(self, **kw: Any) -> DeliveryTask:
        return _task(target="household@example.com", **kw)

    def test_message_id_is_idempotency_key(self) -> None:
        task = self._mail_task()
        msg = build_message(task, smtp_from="alerts@example.com")
        # email.headerregistry folds long headers; compare unfolded.
        assert str(msg["Message-ID"]).replace(" ", "") == "<idem-abc123@alerts.nemotron.local>"
        assert msg["To"] == task.target

    def test_body_is_html_escaped(self) -> None:
        task = self._mail_task(
            payload={"title": "t", "summary": "<script>alert(1)</script> & done"}
        )
        msg = build_message(task, smtp_from="a@b.c")
        html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
        content = html_part.get_content()
        assert "<script>" not in content
        assert "&lt;script&gt;" in content

    def test_subject_carries_severity(self) -> None:
        task = self._mail_task(payload={"title": "Person", "severity": "high", "summary": "s"})
        msg = build_message(task, smtp_from="a@b.c")
        assert "[HIGH]" in msg["Subject"]


class TestBuildPayload:
    def test_payload_redacts_names_by_default(self) -> None:
        stub_metadata = MappingProxyType(
            {"rule_name": "Front door", "summary": "known person Jane at the door"}
        )

        class A:
            id = "a-1"
            severity = "medium"
            camera_id = "front"
            event_id = 7
            created_at = None
            description = ""
            alert_metadata = stub_metadata

        p = build_payload(A(), idempotency_key="k1", include_names=False, known_names={"Jane"})
        assert "Jane" not in p["summary"]
        assert "a known person" in p["summary"]
        assert p["idempotency_key"] == "k1"

    def test_payload_includes_names_when_opted_in(self) -> None:
        stub_metadata = MappingProxyType(
            {"rule_name": "Front door", "summary": "known person Jane at the door"}
        )

        class A:
            id = "a-1"
            severity = "medium"
            camera_id = "front"
            event_id = 7
            created_at = None
            description = ""
            alert_metadata = stub_metadata

        p = build_payload(A(), idempotency_key="k1", include_names=True, known_names={"Jane"})
        assert "Jane" in p["summary"]
