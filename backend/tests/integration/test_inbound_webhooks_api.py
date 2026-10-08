"""Integration tests for inbound webhook API endpoints (NEM-5170, B1.3).

Tests for the /api/webhooks/inbound endpoints which receive webhook
notifications from external systems like IFTTT, Zapier, n8n, and Home
Assistant.

Endpoints tested:
    POST /api/webhooks/inbound/alert  - Create external alert
    POST /api/webhooks/inbound/arm    - Arm zones
    POST /api/webhooks/inbound/disarm - Disarm zones
    POST /api/webhooks/inbound/mode   - Set system mode

Honesty contract (B1.3, D3, UR-12): the four handlers take no action —
the arming feature they fake is ruled for Phase 4 — so a correctly
authenticated call answers 501 Not Implemented with a body naming UR-12,
and a key that is not in ``settings.api_keys`` gets 401. Before B1.3 these
endpoints accepted any key of 16+ characters and answered 200 with
"queued" messages for work nothing queued (00-audit D3); the expectations
below are the ruled contract that replaces that. Request schemas stay
byte-compatible: a validly-authenticated, malformed payload still 422s —
auth (401) runs first, then schema (422), then the 501.

Related Issues:
    - NEM-5170: [Implement] Phase 8: Inbound Webhook API (stays open: the
      handlers remain unimplemented; only their honesty changed)
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

import uuid

import pytest

from backend.tests.integration.conftest import TEST_API_KEY


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def valid_api_key():
    """A key registered in settings.api_keys (integration_env:973 registers
    exactly this one via API_KEYS; the pre-B1.3 fixture key
    'test-api-key-1234567890abcdef' was never registered — it passed only
    because verify_api_key accepted any key of 16+ characters (D3))."""
    return TEST_API_KEY


@pytest.fixture
def unregistered_api_key():
    """A 16-character key absent from settings.api_keys — exactly the
    credential class D3 accepted. B1.3's Done-when names it."""
    return "abcdefghijklmn0p"  # 16 chars, not in API_KEYS


@pytest.fixture
def invalid_api_key():
    """A key too short to be real, and also unregistered. Green on both
    sides of B1.3: rejected for length before, for registry membership
    after — the observable contract (401 'Invalid API key') is unchanged."""
    return "short"


# (path, a payload that passes that endpoint's schema)
ENDPOINT_CASES = [
    ("/api/webhooks/inbound/alert", {"source": "ifttt", "message": "Motion at the front door"}),
    ("/api/webhooks/inbound/arm", {"zone_ids": ["zone_1"], "mode": "full"}),
    ("/api/webhooks/inbound/disarm", {"zone_ids": ["zone_1"], "reason": "Homeowner arriving"}),
    ("/api/webhooks/inbound/mode", {"mode": "home"}),
]
ENDPOINT_IDS = ["alert", "arm", "disarm", "mode"]


@pytest.fixture
def sample_alert_payload():
    """Sample alert payload."""
    return {
        "source": "ifttt",
        "message": "Motion detected at front door",
        "severity": "high",
        "metadata": {
            "trigger_id": unique_id("trigger"),
            "location": "front_door",
        },
    }


@pytest.fixture
def sample_arm_payload():
    """Sample arm zones payload."""
    return {
        "zone_ids": ["zone_1", "zone_2"],
        "mode": "full",
    }


@pytest.fixture
def sample_disarm_payload():
    """Sample disarm zones payload."""
    return {
        "zone_ids": ["zone_1"],
        "reason": "Homeowner arriving",
    }


@pytest.fixture
def sample_mode_payload():
    """Sample system mode payload."""
    return {
        "mode": "home",
    }


# =============================================================================
# Honesty contract: every endpoint answers 501, body names UR-12
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("path,payload", ENDPOINT_CASES, ids=ENDPOINT_IDS)
async def test_valid_key_gets_501_naming_ur12(client, valid_api_key, path, payload):
    """Done-when clause: each endpoint with a valid key answers 501 Not
    Implemented with a body naming UR-12 (UR-12 ruling: 501 until the
    arming feature ships)."""
    response = await client.post(path, json=payload, headers={"X-API-Key": valid_api_key})

    assert response.status_code == 501
    detail = response.json()["detail"]
    assert "UR-12" in detail
    assert "not implemented" in detail.lower()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("path,payload", ENDPOINT_CASES, ids=ENDPOINT_IDS)
async def test_501_body_carries_no_fake_success_fields(client, valid_api_key, path, payload):
    """The 501 body carries none of the fake-success fields. Before B1.3
    every response minted status/message/request_id/timestamp describing
    work that never happened (D3); there is no such field to read now.

    The envelope itself is the app-wide RFC-7807 problem body the exception
    handler produces for every HTTPException (type/title/status/instance/
    detail), observed here rather than assumed — note its ``status`` is the
    HTTP code, not the old model's ``status: "received"``.
    """
    response = await client.post(path, json=payload, headers={"X-API-Key": valid_api_key})

    assert response.status_code == 501
    body = response.json()
    assert "UR-12" in body["detail"]
    assert body["status"] == 501
    for fake_field in ("message", "request_id", "timestamp"):
        assert fake_field not in body, f"{fake_field} is the fabricated-success field D3 names"


# =============================================================================
# Key validation: only keys in settings.api_keys authenticate
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("path,payload", ENDPOINT_CASES, ids=ENDPOINT_IDS)
async def test_unregistered_16_char_key_gets_401(client, unregistered_api_key, path, payload):
    """Done-when clause: a 16-character key absent from settings.api_keys
    gets 401 — the exact credential class D3 accepted (>= 16 chars)."""
    response = await client.post(path, json=payload, headers={"X-API-Key": unregistered_api_key})

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_is_checked_before_the_payload(client, unregistered_api_key):
    """Ordering pin (measured, not assumed): an unregistered key with an
    invalid payload gets 401, not 422 — FastAPI resolves security
    dependencies before body validation, so an unauthenticated caller
    cannot probe the schemas."""
    response = await client.post(
        "/api/webhooks/inbound/alert", json={}, headers={"X-API-Key": unregistered_api_key}
    )

    assert response.status_code == 401


# =============================================================================
# CREATE ALERT Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_missing_api_key(client, sample_alert_payload):
    """Test create alert fails without API key.

    The shared `client` bakes a default X-API-Key header (the `client`
    fixture in integration/conftest.py), so "missing" must be sent as an
    explicit empty value to actually exercise the branch
    (ledger R-T7-INBOUND).
    """
    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=sample_alert_payload,
        headers={"X-API-Key": ""},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing X-API-Key header" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_invalid_api_key(client, invalid_api_key, sample_alert_payload):
    """Test create alert fails with an invalid API key."""
    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=sample_alert_payload,
        headers={"X-API-Key": invalid_api_key},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid API key" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_missing_source(client, valid_api_key):
    """Test alert creation fails without source field."""
    payload = {"message": "No source here"}

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_missing_message(client, valid_api_key):
    """Test alert creation fails without message field."""
    payload = {"source": "ifttt"}

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_empty_source(client, valid_api_key):
    """Test alert creation fails with empty source."""
    payload = {"source": "", "message": "Test"}

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_empty_message(client, valid_api_key):
    """Test alert creation fails with empty message."""
    payload = {"source": "ifttt", "message": ""}

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_with_metadata_501(client, valid_api_key, sample_alert_payload):
    """A fully-formed alert payload (metadata included) still answers 501:
    nothing is queued no matter how well-formed the request is. The old
    default-severity/message-echo tests died with the fake-success body —
    there is no echoed message anymore."""
    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=sample_alert_payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 501


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_source_too_long(client, valid_api_key):
    """Test alert creation fails with source longer than 100 chars."""
    payload = {"source": "x" * 101, "message": "Test"}

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_message_too_long(client, valid_api_key):
    """Test alert creation fails with message longer than 1000 chars."""
    payload = {"source": "ifttt", "message": "x" * 1001}

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


# =============================================================================
# ARM ZONES Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_schema_accepts_empty_zone_list_501(client, valid_api_key):
    """The kept schema accepts zone_ids=[] (pre-B1.3 shipped contract: an
    empty list rendered as 'all' in the fake message). Post-B1.3 there is
    no message to render; the pin is that the schema still accepts it and
    the endpoint answers 501, not 422 — the arming feature reuses this
    schema unchanged."""
    payload = {"zone_ids": [], "mode": "full"}

    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 501


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_no_mode_501(client, valid_api_key):
    """Arm without the optional mode field: schema-valid, so 501 (not 422)."""
    payload = {"zone_ids": ["zone_1", "zone_2"]}

    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 501


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_missing_api_key(client, sample_arm_payload):
    """Test zone arming fails without API key.

    Empty-string X-API-Key overrides the client's default header — see
    test_create_alert_missing_api_key for why (ledger R-T7-INBOUND).
    """
    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=sample_arm_payload,
        headers={"X-API-Key": ""},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing X-API-Key header" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_invalid_api_key(client, invalid_api_key, sample_arm_payload):
    """Test zone arming fails with an invalid API key."""
    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=sample_arm_payload,
        headers={"X-API-Key": invalid_api_key},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid API key" in data["detail"]


# =============================================================================
# DISARM ZONES Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_schema_accepts_empty_zone_list_501(client, valid_api_key):
    """Mirror of the arm-side pin: zone_ids=[] is schema-valid and answers
    501 (pre-B1.3: empty list rendered as 'all' in the fake message —
    routes/inbound_webhooks.py, deleted with the fake)."""
    payload = {"zone_ids": [], "reason": "Test"}

    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 501


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_no_reason_501(client, valid_api_key):
    """Disarm without the optional reason field: schema-valid, so 501."""
    payload = {"zone_ids": ["zone_1"]}

    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 501


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_missing_api_key(client, sample_disarm_payload):
    """Test zone disarming fails without API key.

    Empty-string X-API-Key overrides the client's default header — see
    test_create_alert_missing_api_key for why (ledger R-T7-INBOUND).
    """
    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=sample_disarm_payload,
        headers={"X-API-Key": ""},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing X-API-Key header" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_invalid_api_key(client, invalid_api_key, sample_disarm_payload):
    """Test zone disarming fails with an invalid API key."""
    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=sample_disarm_payload,
        headers={"X-API-Key": invalid_api_key},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid API key" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_reason_too_long(client, valid_api_key):
    """Test zone disarming fails with reason longer than 500 chars."""
    payload = {
        "zone_ids": ["zone_1"],
        "reason": "x" * 501,
    }

    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


# =============================================================================
# SYSTEM MODE Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_any_value_answers_501(client, valid_api_key):
    """Mode-value validation lived in the deleted handler (it 422'd values
    outside SystemMode). B1.3 keeps InboundModePayload byte-identical and
    mode is a plain str there, so an out-of-vocabulary mode now answers 501
    like everything else — the handler that 422'd it is gone, and the
    validation belongs to the Phase 4 arming feature (recorded in the PR,
    not silently dropped)."""
    for mode in ("home", "away", "night", "disarmed", "invalid_mode", ""):
        response = await client.post(
            "/api/webhooks/inbound/mode",
            json={"mode": mode},
            headers={"X-API-Key": valid_api_key},
        )
        assert response.status_code == 501, f"mode={mode!r} should 501"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_missing_mode(client, valid_api_key):
    """Test mode change fails without mode field (schema pin)."""
    payload = {}

    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_missing_api_key(client, sample_mode_payload):
    """Test mode change fails without API key.

    The shared client bakes TEST_API_KEY into default headers (the `client`
    fixture in integration/conftest.py), so "missing" must be sent as an
    explicit empty value to actually exercise the branch (R-T7-INBOUND).
    """
    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=sample_mode_payload,
        headers={"X-API-Key": ""},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing X-API-Key header" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_invalid_api_key(client, invalid_api_key, sample_mode_payload):
    """Test mode change fails with an invalid API key."""
    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=sample_mode_payload,
        headers={"X-API-Key": invalid_api_key},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid API key" in data["detail"]


# =============================================================================
# Cross-Endpoint Tests
# =============================================================================


def test_router_declares_no_success_status():
    """Done-when clause, checked structurally: "no inbound-webhook handler
    returns a success status" holds for the route table itself, not just for
    the four payloads probed above — a handler cannot regain a 200 by
    changing its body without also changing a declared status code, and the
    200 it used to document is gone from ``responses``."""
    from fastapi.routing import APIRoute

    from backend.api.routes import inbound_webhooks

    routes = [r for r in inbound_webhooks.router.routes if isinstance(r, APIRoute)]
    assert len(routes) == 4, "the four inbound endpoints"

    for route in routes:
        assert route.methods == {"POST"}, route.path
        assert route.status_code == 501, f"{route.path} declares {route.status_code}"
        documented = set(route.responses) | {route.status_code}
        successes = sorted(c for c in documented if 200 <= c < 300)
        assert not successes, f"{route.path} documents success status(s): {successes}"


def test_no_length_based_key_check_survives_in_the_module():
    """The other half of D3: this module's own accept-any-16-char
    ``verify_api_key`` is gone, replaced by the shared registry-checking
    dependency. Pinning its absence (not just behaviour) keeps a future
    edit from quietly reintroducing a local copy — the module had one of the
    three shipped copies."""
    from backend.api.middleware.auth import require_api_key
    from backend.api.routes import inbound_webhooks

    assert not hasattr(inbound_webhooks, "verify_api_key")
    assert inbound_webhooks.require_api_key is require_api_key
    # The dependency honours no api_key_enabled bypass: fail-closed. Checked
    # on the executable AST (docstring stripped — the docstring *explains*
    # the flag is not honoured, so a source-text scan would find the word
    # there and this pin would be a lie in the other direction).
    import ast
    import inspect

    fn_ast = ast.parse(inspect.getsource(require_api_key)).body[0]
    fn_ast.body = [
        stmt
        for stmt in fn_ast.body
        if not (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )
    ]
    assert "api_key_enabled" not in ast.dump(ast.fix_missing_locations(fn_ast))


def test_dependency_is_fail_closed_with_no_keys_configured():
    """Behavioural half of fail-closed: with settings.api_keys empty (the
    shipped default), the dependency refuses a well-formed key — the
    opposite of the api_key_enabled=False early-return the dlq/system copies
    have. Runs the dependency function directly; no HTTP layer needed."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from fastapi import HTTPException

    from backend.api.middleware.auth import require_api_key

    empty_settings = SimpleNamespace(
        api_keys=[],  # the shipped default: no keys configured
        api_key_enabled=False,  # the flag the dlq/system copies would obey
    )

    with patch(
        "backend.api.middleware.auth.get_settings", autospec=True, return_value=empty_settings
    ):
        try:
            require_api_key(x_api_key="a-perfectly-well-formed-key")
        except HTTPException as exc:
            assert exc.status_code == 401
            assert "Invalid API key" in exc.detail
        else:
            pytest.fail("require_api_key must refuse when no keys are configured (fail-closed)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_endpoints_require_auth(client):
    """Test that all webhook endpoints require authentication."""
    endpoints = [
        ("/api/webhooks/inbound/alert", {"source": "test", "message": "test"}),
        ("/api/webhooks/inbound/arm", {}),
        ("/api/webhooks/inbound/disarm", {}),
        ("/api/webhooks/inbound/mode", {"mode": "home"}),
    ]

    # Explicit empty key: the shared client bakes TEST_API_KEY as a default
    # header, so an omitted header still authenticates (R-T7-INBOUND).
    for endpoint, payload in endpoints:
        response = await client.post(endpoint, json=payload, headers={"X-API-Key": ""})
        assert response.status_code == 401, f"Endpoint {endpoint} should require auth"
