"""Integration tests for inbound webhook API endpoints (NEM-5170).

Tests for the /api/webhooks/inbound endpoints which receive webhook notifications
from external systems like IFTTT, Zapier, n8n, and Home Assistant.

Endpoints tested:
    POST /api/webhooks/inbound/alert  - Create external alert
    POST /api/webhooks/inbound/arm    - Arm zones
    POST /api/webhooks/inbound/disarm - Disarm zones
    POST /api/webhooks/inbound/mode   - Set system mode

Related Issues:
    - NEM-5170: [Implement] Phase 8: Inbound Webhook API
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

import uuid

import pytest


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def valid_api_key():
    """Valid API key for authentication."""
    return "test-api-key-1234567890abcdef"


@pytest.fixture
def invalid_api_key():
    """Invalid API key (too short)."""
    return "short"


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
# CREATE ALERT Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_success(client, valid_api_key, sample_alert_payload):
    """Test successful alert creation with valid API key."""
    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=sample_alert_payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "Alert from ifttt queued for processing" in data["message"]
    assert "request_id" in data
    assert data["request_id"] is not None
    assert "timestamp" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_missing_api_key(client, sample_alert_payload):
    """Test alert creation fails without API key."""
    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=sample_alert_payload,
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing X-API-Key header" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_invalid_api_key(client, invalid_api_key, sample_alert_payload):
    """Test alert creation fails with invalid API key."""
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
    payload = {
        "message": "Test message",
        "severity": "medium",
    }

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
    payload = {
        "source": "ifttt",
        "severity": "medium",
    }

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
    payload = {
        "source": "",
        "message": "Test message",
    }

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
    payload = {
        "source": "ifttt",
        "message": "",
    }

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_default_severity(client, valid_api_key):
    """Test alert creation uses default severity."""
    payload = {
        "source": "zapier",
        "message": "Test message without severity",
    }

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_with_metadata(client, valid_api_key):
    """Test alert creation with custom metadata."""
    payload = {
        "source": "home_assistant",
        "message": "Test alert",
        "severity": "critical",
        "metadata": {
            "entity_id": "binary_sensor.front_door",
            "state": "on",
            "attributes": {"device_class": "motion"},
        },
    }

    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_alert_source_too_long(client, valid_api_key):
    """Test alert creation fails with source longer than 100 chars."""
    payload = {
        "source": "x" * 101,
        "message": "Test message",
    }

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
    payload = {
        "source": "ifttt",
        "message": "x" * 1001,
    }

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
async def test_arm_zones_success(client, valid_api_key, sample_arm_payload):
    """Test successful zone arming with specific zones."""
    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=sample_arm_payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "Arm command for 2 zones queued" in data["message"]
    assert "request_id" in data
    assert data["request_id"] is not None
    assert "timestamp" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_all_zones(client, valid_api_key):
    """Test arming all zones when zone_ids is None."""
    payload = {
        "mode": "full",
    }

    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "Arm command for all zones queued" in data["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_no_mode(client, valid_api_key):
    """Test zone arming without mode field."""
    payload = {
        "zone_ids": ["zone_1", "zone_2"],
    }

    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_missing_api_key(client, sample_arm_payload):
    """Test zone arming fails without API key."""
    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=sample_arm_payload,
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing X-API-Key header" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_invalid_api_key(client, invalid_api_key, sample_arm_payload):
    """Test zone arming fails with invalid API key."""
    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=sample_arm_payload,
        headers={"X-API-Key": invalid_api_key},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid API key" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_arm_zones_empty_zone_list(client, valid_api_key):
    """Test zone arming with empty zone_ids list."""
    payload = {
        "zone_ids": [],
        "mode": "full",
    }

    response = await client.post(
        "/api/webhooks/inbound/arm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "Arm command for 0 zones queued" in data["message"]


# =============================================================================
# DISARM ZONES Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_success(client, valid_api_key, sample_disarm_payload):
    """Test successful zone disarming with specific zones."""
    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=sample_disarm_payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "Disarm command for 1 zones queued" in data["message"]
    assert "request_id" in data
    assert data["request_id"] is not None
    assert "timestamp" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_all_zones(client, valid_api_key):
    """Test disarming all zones when zone_ids is None."""
    payload = {
        "reason": "Homeowner home",
    }

    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "Disarm command for all zones queued" in data["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_no_reason(client, valid_api_key):
    """Test zone disarming without reason field."""
    payload = {
        "zone_ids": ["zone_1"],
    }

    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_missing_api_key(client, sample_disarm_payload):
    """Test zone disarming fails without API key."""
    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=sample_disarm_payload,
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing X-API-Key header" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_invalid_api_key(client, invalid_api_key, sample_disarm_payload):
    """Test zone disarming fails with invalid API key."""
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disarm_zones_empty_zone_list(client, valid_api_key):
    """Test zone disarming with empty zone_ids list."""
    payload = {
        "zone_ids": [],
        "reason": "Test",
    }

    response = await client.post(
        "/api/webhooks/inbound/disarm",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "Disarm command for 0 zones queued" in data["message"]


# =============================================================================
# SYSTEM MODE Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_home(client, valid_api_key):
    """Test setting system mode to 'home'."""
    payload = {"mode": "home"}

    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "System mode change to 'home' queued" in data["message"]
    assert "request_id" in data
    assert "timestamp" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_away(client, valid_api_key):
    """Test setting system mode to 'away'."""
    payload = {"mode": "away"}

    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "System mode change to 'away' queued" in data["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_night(client, valid_api_key):
    """Test setting system mode to 'night'."""
    payload = {"mode": "night"}

    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "System mode change to 'night' queued" in data["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_disarmed(client, valid_api_key):
    """Test setting system mode to 'disarmed'."""
    payload = {"mode": "disarmed"}

    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "System mode change to 'disarmed' queued" in data["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_invalid(client, valid_api_key):
    """Test setting invalid system mode."""
    payload = {"mode": "invalid_mode"}

    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422
    data = response.json()
    assert "Invalid mode" in data["detail"]
    assert "invalid_mode" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_missing_mode(client, valid_api_key):
    """Test mode change fails without mode field."""
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
    """Test mode change fails without API key."""
    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=sample_mode_payload,
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing X-API-Key header" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_invalid_api_key(client, invalid_api_key, sample_mode_payload):
    """Test mode change fails with invalid API key."""
    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=sample_mode_payload,
        headers={"X-API-Key": invalid_api_key},
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid API key" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_mode_empty_string(client, valid_api_key):
    """Test mode change fails with empty mode string."""
    payload = {"mode": ""}

    response = await client.post(
        "/api/webhooks/inbound/mode",
        json=payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 422
    data = response.json()
    assert "Invalid mode" in data["detail"]


# =============================================================================
# Cross-Endpoint Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_alerts_different_sources(client, valid_api_key):
    """Test creating multiple alerts from different sources."""
    sources = ["ifttt", "zapier", "n8n", "home_assistant"]

    for source in sources:
        payload = {
            "source": source,
            "message": f"Test alert from {source}",
            "severity": "medium",
        }

        response = await client.post(
            "/api/webhooks/inbound/alert",
            json=payload,
            headers={"X-API-Key": valid_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert source in data["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_id_uniqueness(client, valid_api_key, sample_alert_payload):
    """Test that each webhook call generates a unique request ID."""
    response1 = await client.post(
        "/api/webhooks/inbound/alert",
        json=sample_alert_payload,
        headers={"X-API-Key": valid_api_key},
    )

    response2 = await client.post(
        "/api/webhooks/inbound/alert",
        json=sample_alert_payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    assert data1["request_id"] != data2["request_id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_timestamp_format(client, valid_api_key, sample_alert_payload):
    """Test that timestamp is in ISO format."""
    response = await client.post(
        "/api/webhooks/inbound/alert",
        json=sample_alert_payload,
        headers={"X-API-Key": valid_api_key},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify timestamp is ISO format (basic check)
    timestamp = data["timestamp"]
    assert "T" in timestamp
    assert any(c in timestamp for c in ["+", "Z"])  # Timezone info


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

    for endpoint, payload in endpoints:
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 401, f"Endpoint {endpoint} should require auth"
