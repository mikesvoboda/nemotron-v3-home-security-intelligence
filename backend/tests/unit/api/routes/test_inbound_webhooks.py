"""Unit tests for the inbound webhook route module (NEM-5170, B1.3).

Where the integration suite
(:mod:`backend.tests.integration.test_inbound_webhooks_api`) drives the four
routes through a live app and asserts the responses an integrator sees, this
module tests the pieces of :mod:`backend.api.routes.inbound_webhooks` in
isolation, at the layer the claim is actually made:

- :func:`require_api_key` — the shared guard itself: absent key, unregistered
  key, registered key, and the fail-closed case (no keys configured).
- :func:`_reject_unimplemented` / :func:`_log_rejected_attempt` — the 501 it
  raises and the shape of the record it writes (no secrets).
- the router declarations — every route is guarded and declares 501.
- the request schemas kept for the Phase 4 arming feature.
- :func:`verify_hmac_signature`, unchanged by B1.3, tested here so the module
  is covered at this tier.

Honesty contract (D3, UR-12): the handlers take no action, so nothing here
asserts a state change — asserting one would re-create the fiction B1.3
removes.
"""

from __future__ import annotations

import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status

from backend.api.middleware.auth import require_api_key
from backend.api.routes.inbound_webhooks import (
    NOT_IMPLEMENTED_DETAIL,
    InboundAlertPayload,
    InboundArmPayload,
    InboundDisarmPayload,
    InboundModePayload,
    _reject_unimplemented,
    router,
    verify_hmac_signature,
)
from backend.core.logging import mask_ip

LOGGER_NAME = "backend.api.routes.inbound_webhooks"
ROUTES = (
    "/api/webhooks/inbound/alert",
    "/api/webhooks/inbound/arm",
    "/api/webhooks/inbound/disarm",
    "/api/webhooks/inbound/mode",
)


def _request(host: str | None = "203.0.113.7") -> SimpleNamespace:
    """A stand-in for the ASGI request the handlers touch.

    Only ``client.host`` is read by the module; ``headers`` carries a sentinel
    so a test can prove the secret never reaches the log record.
    """
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(
        client=client,
        headers={"X-API-Key": "SECRET-NEVER-LOGGED", "User-Agent": "ifttt"},
    )


# =============================================================================
# require_api_key — fail-closed, unconditionally
# =============================================================================


class TestRequireApiKey:
    """The guard the four routes depend on (backend/api/middleware/auth.py)."""

    def test_missing_header_is_401(self):
        """No header at all is refused before any key comparison happens."""
        with pytest.raises(HTTPException) as excinfo:
            require_api_key(None)

        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing X-API-Key" in excinfo.value.detail

    def test_empty_header_is_401(self):
        """An empty header is the same refusal — it is not a zero-length key."""
        with pytest.raises(HTTPException) as excinfo:
            require_api_key("")

        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unregistered_key_is_401(self):
        """A well-formed key that is not in settings.api_keys is refused.

        This is D3's credential class: before B1.3 any key of 16+ characters
        was accepted, so the length of this key is the point, not its obscurity.
        """
        settings = SimpleNamespace(api_keys=["some-other-key"], api_key_enabled=True)

        with patch(
            "backend.api.middleware.auth.get_settings", autospec=True, return_value=settings
        ):
            with pytest.raises(HTTPException) as excinfo:
                require_api_key("abcdefghijklmn0p")  # 16 chars, unregistered

        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API key" in excinfo.value.detail

    def test_registered_key_is_returned_unchanged(self):
        """A configured key passes and is handed back to the caller."""
        settings = SimpleNamespace(api_keys=["registered-key-value"], api_key_enabled=True)

        with patch(
            "backend.api.middleware.auth.get_settings", autospec=True, return_value=settings
        ):
            assert require_api_key("registered-key-value") == "registered-key-value"

    def test_no_keys_configured_refuses_everything(self):
        """The shipped default (empty api_keys) is fail-CLOSED.

        ``api_key_enabled`` is False in that same shipped default, and the two
        older guard copies in routes/dlq.py and routes/system.py return early
        when the flag is off. This dependency has no such branch — with no keys
        on record there is nothing a caller can present that matches, so every
        request is refused rather than every request let through.
        """
        shipped_default = SimpleNamespace(api_keys=[], api_key_enabled=False)

        with patch(
            "backend.api.middleware.auth.get_settings", autospec=True, return_value=shipped_default
        ):
            with pytest.raises(HTTPException) as excinfo:
                require_api_key("any-length-key-at-all")

        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_comparison_uses_digest_not_the_plain_key(self):
        """The setting holds the key, the comparison works on SHA-256 digests."""
        key = "digest-compare-key"
        settings = SimpleNamespace(api_keys=[key], api_key_enabled=True)
        digest = hashlib.sha256(key.encode()).hexdigest()

        with patch(
            "backend.api.middleware.auth.get_settings", autospec=True, return_value=settings
        ):
            with patch(
                "backend.api.middleware.auth._validate_key_hash_constant_time", autospec=True
            ) as compare:
                compare.return_value = True
                require_api_key(key)

        compared_hash, valid_hashes = compare.call_args.args
        assert compared_hash == digest
        assert valid_hashes == {digest}


# =============================================================================
# The rejection helper: what it raises, what it writes
# =============================================================================


class TestRejectUnimplemented:
    """``_reject_unimplemented`` is the whole body of every handler."""

    def test_raises_501_naming_the_ruling(self):
        with pytest.raises(HTTPException) as excinfo:
            _reject_unimplemented("arm", _request())

        assert excinfo.value.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert excinfo.value.detail is NOT_IMPLEMENTED_DETAIL
        assert "UR-12" in excinfo.value.detail
        assert "takes no action" in excinfo.value.detail

    def test_logs_the_rejection_with_endpoint_and_masked_client(
        self, caplog: pytest.LogCaptureFixture
    ):
        caplog.set_level("INFO", logger=LOGGER_NAME)

        # The helper writes the record and then raises; the raise is the 501.
        with pytest.raises(HTTPException):
            _reject_unimplemented("disarm", _request("198.51.100.9"))

        records = [r for r in caplog.records if r.name == LOGGER_NAME]
        assert len(records) == 1, "one record per rejected call"
        assert records[0].endpoint == "disarm"
        # mask_ip keeps the first octet for debugging and masks the rest —
        # the same shape auth.py's own rejection records use.
        assert records[0].client_ip == mask_ip("198.51.100.9")
        assert records[0].client_ip == "198.xxx.xxx.xxx"
        assert "198.51.100.9" not in records[0].client_ip

    def test_logs_unknown_when_the_client_is_unavailable(self, caplog: pytest.LogCaptureFixture):
        """A request with no peer info is still recorded, not skipped."""
        caplog.set_level("INFO", logger=LOGGER_NAME)

        with pytest.raises(HTTPException):
            _reject_unimplemented("mode", _request(host=None))

        assert [r.client_ip for r in caplog.records if r.name == LOGGER_NAME] == ["unknown"]

    def test_no_secret_reaches_the_log(self, caplog: pytest.LogCaptureFixture):
        """The record carries no key, header, or payload (module docstring)."""
        caplog.set_level("INFO", logger=LOGGER_NAME)

        with pytest.raises(HTTPException):
            _reject_unimplemented("alert", _request())

        rendered = [repr(r.getMessage()) for r in caplog.records if r.name == LOGGER_NAME]
        # Key NAMES alone would pass a record carrying the secret in a value
        # (self-review NIT-1, proven: headers={"X-API-Key": secret} as `extra`
        # sailed through the keys-only scan). Values are scanned too — the
        # whole record, repr'd, is the surface a secret can ride.
        rendered += [
            repr(v) for r in caplog.records if r.name == LOGGER_NAME for v in r.__dict__.values()
        ]
        assert all("SECRET-NEVER-LOGGED" not in text for text in rendered)
        assert all("User-Agent" not in text for text in rendered)
        assert all("203.0.113.7" not in text for text in rendered), "IP reaches logs masked only"


# =============================================================================
# Router declarations: guarded, and honest about the status
# =============================================================================


class TestRouterDeclarations:
    """Assertions on the route objects, without an app or a request."""

    @pytest.mark.parametrize("path", ROUTES)
    def test_every_route_depends_on_require_api_key(self, path):
        """Each handler is guarded, so the 501 is never an unauthenticated answer.

        ``route.dependencies`` holds only router-level dependencies; a
        ``Depends()`` declared on the handler signature lands on the resolved
        ``route.dependant``, so that is where the guard is asserted.
        """
        route = next(r for r in router.routes if r.path == path)
        guards = {d.call.__name__ for d in route.dependant.dependencies}

        assert "require_api_key" in guards, f"{path} is not guarded; guards={guards}"

    @pytest.mark.parametrize("path", ROUTES)
    def test_every_route_declares_the_failure_it_returns(self, path):
        route = next(r for r in router.routes if r.path == path)
        documented = set(route.responses) | {route.status_code}

        assert {501, 401} <= documented, f"{path} documents {documented}"


# =============================================================================
# Schemas kept byte-compatible for the Phase 4 arming feature (B1.3)
# =============================================================================


class TestKeptSchemas:
    """The payloads survive unchanged: they are the arming feature's contract."""

    def test_alert_defaults(self):
        payload = InboundAlertPayload(source="ifttt", message="motion")

        assert payload.severity == "medium"
        assert payload.metadata == {}

    def test_alert_metadata_is_not_a_shared_default(self):
        first = InboundAlertPayload(source="a", message="m")
        second = InboundAlertPayload(source="b", message="m")

        first.metadata["trigger"] = "x"

        assert second.metadata == {}, "metadata must not be a shared class default"

    def test_arm_and_disarm_are_all_optional(self):
        """``zone_ids=None`` means "all zones" — the arming feature's semantics."""
        assert InboundArmPayload().zone_ids is None
        assert InboundArmPayload().mode is None
        assert InboundDisarmPayload().zone_ids is None
        assert InboundDisarmPayload().reason is None

    def test_mode_stays_an_unvalidated_string(self):
        """The vocabulary check left with the handler that acted on it.

        Validating the mode values belongs to the Phase 4 feature; keeping the
        field a plain ``str`` is what "keep the request schemas" means here.
        """
        assert InboundModePayload(mode="not-a-real-mode").mode == "not-a-real-mode"


# =============================================================================
# verify_hmac_signature — unchanged by B1.3, covered here
# =============================================================================


class TestHmacSignature:
    """The module's other honest check: a signature is verified or it is not."""

    def test_valid_signature_accepted(self):
        body = b'{"source":"ifttt"}'
        secret = "webhook-secret"
        signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        assert verify_hmac_signature(body, signature, secret) is True

    @pytest.mark.parametrize(
        "body,signature",
        [
            (b'{"source":"ifttt"}', "sha256=" + "0" * 64),  # wrong digest
            (b'{"source":"other"}', "sha256=" + "0" * 64),  # tampered body path
            ('{"source":"ifttt"}', "webhook-secret"),  # unsigned
            ('{"source":"ifttt"}', "sha512=" + "0" * 128),  # wrong algorithm prefix
        ],
    )
    def test_non_matching_signature_rejected(self, body, signature):
        assert verify_hmac_signature(body, signature, "webhook-secret") is False
