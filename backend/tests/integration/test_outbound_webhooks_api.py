"""Integration tests for outbound webhook API endpoints (NEM-3624).

Tests for the /api/outbound-webhooks endpoints which provide CRUD operations
for managing outbound webhooks that send notifications to external systems.

Endpoints tested:
    POST   /api/outbound-webhooks                      - Create webhook
    GET    /api/outbound-webhooks                      - List webhooks
    GET    /api/outbound-webhooks/{id}                 - Get webhook by ID
    PATCH  /api/outbound-webhooks/{id}                 - Update webhook
    DELETE /api/outbound-webhooks/{id}                 - Delete webhook
    POST   /api/outbound-webhooks/{id}/test            - Test webhook
    POST   /api/outbound-webhooks/{id}/enable          - Enable webhook
    POST   /api/outbound-webhooks/{id}/disable         - Disable webhook
    GET    /api/outbound-webhooks/{id}/deliveries      - List deliveries for webhook
    GET    /api/outbound-webhooks/health               - Health summary
    POST   /api/outbound-webhooks/deliveries/{id}/retry - Retry delivery
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import httpx
import pytest


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_webhook_create():
    """Sample webhook creation payload."""
    return {
        "name": unique_id("Test Webhook"),
        "url": "https://example.com/webhook",
        "event_types": ["alert_fired", "event_created"],
        "integration_type": "generic",
        "enabled": True,
        "custom_headers": {},
    }


@pytest.fixture
def sample_slack_webhook():
    """Sample Slack webhook configuration."""
    return {
        "name": unique_id("Slack Alerts"),
        "url": "https://hooks.slack.com/services/T00/B00/xxx",
        "event_types": ["alert_fired"],
        "integration_type": "slack",
        "enabled": True,
    }


# =============================================================================
# CREATE Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_webhook_success(client, sample_webhook_create):
    """Test successful webhook creation with minimal fields."""
    response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_webhook_create["name"]
    assert data["url"] == sample_webhook_create["url"]
    assert data["event_types"] == sample_webhook_create["event_types"]
    assert data["integration_type"] == sample_webhook_create["integration_type"]
    assert data["enabled"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    # UUID validation
    uuid.UUID(data["id"])


@pytest.mark.asyncio
async def test_create_webhook_with_custom_headers(client):
    """Test webhook creation with custom headers."""
    webhook_data = {
        "name": unique_id("Custom Headers Webhook"),
        "url": "https://example.com/webhook",
        "event_types": ["alert_fired"],
        "integration_type": "generic",
        "custom_headers": {
            "X-Custom-Header": "value",
            "X-Another-Header": "another-value",
        },
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 201
    data = response.json()
    assert data["custom_headers"] == webhook_data["custom_headers"]


@pytest.mark.asyncio
async def test_create_webhook_with_payload_template(client):
    """Test webhook creation with custom payload template."""
    webhook_data = {
        "name": unique_id("Template Webhook"),
        "url": "https://example.com/webhook",
        "event_types": ["alert_fired"],
        "integration_type": "generic",
        "payload_template": '{"message": "Alert: {{ event.title }}"}',
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 201
    data = response.json()
    assert data["payload_template"] == webhook_data["payload_template"]


@pytest.mark.asyncio
async def test_create_webhook_missing_name(client):
    """Test webhook creation fails without name."""
    webhook_data = {
        "url": "https://example.com/webhook",
        "event_types": ["alert_fired"],
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_webhook_empty_name(client):
    """Test webhook creation fails with empty name."""
    webhook_data = {
        "name": "",
        "url": "https://example.com/webhook",
        "event_types": ["alert_fired"],
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_webhook_missing_url(client):
    """Test webhook creation fails without URL."""
    webhook_data = {
        "name": unique_id("Test Webhook"),
        "event_types": ["alert_fired"],
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_webhook_invalid_url(client):
    """Test webhook creation fails with invalid URL."""
    webhook_data = {
        "name": unique_id("Test Webhook"),
        "url": "not-a-valid-url",
        "event_types": ["alert_fired"],
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_webhook_empty_event_types(client):
    """Test webhook creation fails with empty event_types list."""
    webhook_data = {
        "name": unique_id("Test Webhook"),
        "url": "https://example.com/webhook",
        "event_types": [],
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_webhook_invalid_event_type(client):
    """Test webhook creation fails with invalid event type."""
    webhook_data = {
        "name": unique_id("Test Webhook"),
        "url": "https://example.com/webhook",
        "event_types": ["invalid_event_type"],
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_webhook_invalid_integration_type(client):
    """Test webhook creation fails with invalid integration type."""
    webhook_data = {
        "name": unique_id("Test Webhook"),
        "url": "https://example.com/webhook",
        "event_types": ["alert_fired"],
        "integration_type": "invalid_type",
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_webhook_all_fields(client):
    """Test webhook creation with all optional fields."""
    webhook_data = {
        "name": unique_id("Complete Webhook"),
        "url": "https://example.com/webhook",
        "event_types": ["alert_fired", "alert_dismissed", "event_created"],
        "integration_type": "slack",
        "enabled": False,
        "custom_headers": {"X-Custom": "value"},
        "payload_template": '{"text": "{{ event.title }}"}',
        "max_retries": 5,
        "retry_delay_seconds": 60,
    }

    response = await client.post("/api/outbound-webhooks", json=webhook_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == webhook_data["name"]
    assert data["url"] == webhook_data["url"]
    assert set(data["event_types"]) == set(webhook_data["event_types"])
    assert data["integration_type"] == webhook_data["integration_type"]
    assert data["enabled"] is False
    assert data["custom_headers"] == webhook_data["custom_headers"]
    assert data["payload_template"] == webhook_data["payload_template"]
    assert data["max_retries"] == webhook_data["max_retries"]
    assert data["retry_delay_seconds"] == webhook_data["retry_delay_seconds"]


# =============================================================================
# READ Tests - List
# =============================================================================


@pytest.mark.asyncio
async def test_list_webhooks_empty(client):
    """Test listing webhooks when none exist."""
    response = await client.get("/api/outbound-webhooks")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["webhooks"], list)
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_list_webhooks_with_data(client, sample_webhook_create):
    """Test listing webhooks with existing data."""
    # Create test webhooks
    webhook1 = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert webhook1.status_code == 201

    webhook2_data = {**sample_webhook_create, "name": unique_id("Webhook 2")}
    webhook2 = await client.post("/api/outbound-webhooks", json=webhook2_data)
    assert webhook2.status_code == 201

    # List webhooks
    response = await client.get("/api/outbound-webhooks")

    assert response.status_code == 200
    data = response.json()
    assert len(data["webhooks"]) >= 2
    assert data["total"] >= 2

    # Verify webhook IDs are in the list
    webhook_ids = [w["id"] for w in data["webhooks"]]
    assert webhook1.json()["id"] in webhook_ids
    assert webhook2.json()["id"] in webhook_ids


@pytest.mark.asyncio
async def test_list_webhooks_enabled_only_filter(client, sample_webhook_create):
    """Test filtering webhooks by enabled status."""
    # Create enabled webhook
    enabled_data = {**sample_webhook_create, "enabled": True}
    enabled_webhook = await client.post("/api/outbound-webhooks", json=enabled_data)
    assert enabled_webhook.status_code == 201

    # Create disabled webhook
    disabled_data = {
        **sample_webhook_create,
        "name": unique_id("Disabled Webhook"),
        "enabled": False,
    }
    disabled_webhook = await client.post("/api/outbound-webhooks", json=disabled_data)
    assert disabled_webhook.status_code == 201

    # List only enabled webhooks
    response = await client.get("/api/outbound-webhooks?enabled_only=true")

    assert response.status_code == 200
    data = response.json()
    # All webhooks in response should be enabled
    for webhook in data["webhooks"]:
        assert webhook["enabled"] is True


# =============================================================================
# READ Tests - Get by ID
# =============================================================================


@pytest.mark.asyncio
async def test_get_webhook_by_id_success(client, sample_webhook_create):
    """Test getting webhook by ID."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    created_webhook = create_response.json()

    # Get webhook by ID
    response = await client.get(f"/api/outbound-webhooks/{created_webhook['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_webhook["id"]
    assert data["name"] == created_webhook["name"]
    assert data["url"] == created_webhook["url"]


@pytest.mark.asyncio
async def test_get_webhook_not_found(client):
    """Test getting non-existent webhook returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/outbound-webhooks/{fake_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_webhook_invalid_uuid(client):
    """Test getting webhook with invalid UUID format."""
    response = await client.get("/api/outbound-webhooks/not-a-uuid")

    assert response.status_code in [400, 422]  # Bad request or validation error


# =============================================================================
# UPDATE Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_webhook_name(client, sample_webhook_create):
    """Test updating webhook name."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Update name
    new_name = unique_id("Updated Webhook")
    update_data = {"name": new_name}
    response = await client.patch(f"/api/outbound-webhooks/{webhook_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new_name
    assert data["id"] == webhook_id


@pytest.mark.asyncio
async def test_update_webhook_url(client, sample_webhook_create):
    """Test updating webhook URL."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Update URL
    new_url = "https://newurl.com/webhook"
    update_data = {"url": new_url}
    response = await client.patch(f"/api/outbound-webhooks/{webhook_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == new_url


@pytest.mark.asyncio
async def test_update_webhook_event_types(client, sample_webhook_create):
    """Test updating webhook event types."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Update event types
    new_event_types = ["event_enriched", "anomaly_detected"]
    update_data = {"event_types": new_event_types}
    response = await client.patch(f"/api/outbound-webhooks/{webhook_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert set(data["event_types"]) == set(new_event_types)


@pytest.mark.asyncio
async def test_update_webhook_custom_headers(client, sample_webhook_create):
    """Test updating webhook custom headers."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Update custom headers
    new_headers = {"X-New-Header": "new-value"}
    update_data = {"custom_headers": new_headers}
    response = await client.patch(f"/api/outbound-webhooks/{webhook_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["custom_headers"] == new_headers


@pytest.mark.asyncio
async def test_update_webhook_multiple_fields(client, sample_webhook_create):
    """Test updating multiple webhook fields at once."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Update multiple fields
    update_data = {
        "name": unique_id("Multi-Update Webhook"),
        "enabled": False,
        "max_retries": 10,
    }
    response = await client.patch(f"/api/outbound-webhooks/{webhook_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["enabled"] is False
    assert data["max_retries"] == 10


@pytest.mark.asyncio
async def test_update_webhook_not_found(client):
    """Test updating non-existent webhook returns 404."""
    fake_id = str(uuid.uuid4())
    update_data = {"name": "Updated Name"}
    response = await client.patch(f"/api/outbound-webhooks/{fake_id}", json=update_data)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_webhook_invalid_url(client, sample_webhook_create):
    """Test updating webhook with invalid URL fails."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Try to update with invalid URL
    update_data = {"url": "not-a-valid-url"}
    response = await client.patch(f"/api/outbound-webhooks/{webhook_id}", json=update_data)

    assert response.status_code == 422


# =============================================================================
# DELETE Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_webhook_success(client, sample_webhook_create):
    """Test deleting webhook."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Delete webhook
    response = await client.delete(f"/api/outbound-webhooks/{webhook_id}")

    assert response.status_code == 204

    # Verify webhook is deleted
    get_response = await client.get(f"/api/outbound-webhooks/{webhook_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_webhook_not_found(client):
    """Test deleting non-existent webhook returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.delete(f"/api/outbound-webhooks/{fake_id}")

    assert response.status_code == 404


# =============================================================================
# ENABLE/DISABLE Tests
# =============================================================================


@pytest.mark.asyncio
async def test_enable_webhook(client, sample_webhook_create):
    """Test enabling disabled webhook."""
    # Create disabled webhook
    webhook_data = {**sample_webhook_create, "enabled": False}
    create_response = await client.post("/api/outbound-webhooks", json=webhook_data)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Enable webhook
    response = await client.post(f"/api/outbound-webhooks/{webhook_id}/enable")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_enable_webhook_not_found(client):
    """Test enabling non-existent webhook returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.post(f"/api/outbound-webhooks/{fake_id}/enable")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_disable_webhook(client, sample_webhook_create):
    """Test disabling enabled webhook."""
    # Create enabled webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Disable webhook
    response = await client.post(f"/api/outbound-webhooks/{webhook_id}/disable")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_disable_webhook_not_found(client):
    """Test disabling non-existent webhook returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.post(f"/api/outbound-webhooks/{fake_id}/disable")

    assert response.status_code == 404


# =============================================================================
# TEST WEBHOOK Tests
# =============================================================================


@pytest.mark.asyncio
async def test_test_webhook_success(client, sample_webhook_create):
    """Test webhook with successful response."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Mock the external webhook endpoint
    mock_response = httpx.Response(200, json={"status": "ok"})

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        # Test webhook
        test_data = {"event_type": "alert_fired"}
        response = await client.post(f"/api/outbound-webhooks/{webhook_id}/test", json=test_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status_code"] == 200
        assert "response_time_ms" in data


@pytest.mark.asyncio
async def test_test_webhook_failure(client, sample_webhook_create):
    """Test webhook with failed response."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Mock the external webhook endpoint to return error
    mock_response = httpx.Response(500, json={"error": "Internal Server Error"})

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        # Test webhook
        test_data = {"event_type": "alert_fired"}
        response = await client.post(f"/api/outbound-webhooks/{webhook_id}/test", json=test_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["status_code"] == 500


@pytest.mark.asyncio
async def test_test_webhook_not_found(client):
    """Test testing non-existent webhook returns 404."""
    fake_id = str(uuid.uuid4())
    test_data = {"event_type": "alert_fired"}
    response = await client.post(f"/api/outbound-webhooks/{fake_id}/test", json=test_data)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_test_webhook_invalid_event_type(client, sample_webhook_create):
    """Test webhook test with invalid event type fails."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # Test with invalid event type
    test_data = {"event_type": "invalid_event"}
    response = await client.post(f"/api/outbound-webhooks/{webhook_id}/test", json=test_data)

    assert response.status_code == 422


# =============================================================================
# DELIVERIES Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_deliveries_empty(client, sample_webhook_create):
    """Test listing deliveries for webhook with no deliveries."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # List deliveries
    response = await client.get(f"/api/outbound-webhooks/{webhook_id}/deliveries")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["deliveries"], list)
    assert data["total"] == 0
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_list_deliveries_not_found(client):
    """Test listing deliveries for non-existent webhook returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/outbound-webhooks/{fake_id}/deliveries")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_deliveries_pagination(client, sample_webhook_create):
    """Test delivery list pagination parameters."""
    # Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook_id = create_response.json()["id"]

    # List with limit and offset
    response = await client.get(f"/api/outbound-webhooks/{webhook_id}/deliveries?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 0


# =============================================================================
# HEALTH Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_webhook_health(client):
    """Test getting webhook health summary."""
    response = await client.get("/api/outbound-webhooks/health")

    assert response.status_code == 200
    data = response.json()
    # Health summary should have basic structure
    assert "total_webhooks" in data
    assert "enabled_webhooks" in data
    assert isinstance(data["total_webhooks"], int)
    assert isinstance(data["enabled_webhooks"], int)


@pytest.mark.asyncio
async def test_get_webhook_health_with_data(client, sample_webhook_create):
    """Test webhook health summary with existing webhooks."""
    # Create enabled webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201

    # Get health
    response = await client.get("/api/outbound-webhooks/health")

    assert response.status_code == 200
    data = response.json()
    assert data["total_webhooks"] >= 1
    assert data["enabled_webhooks"] >= 1


# =============================================================================
# RETRY DELIVERY Tests
# =============================================================================


@pytest.mark.asyncio
async def test_retry_delivery_not_found(client):
    """Test retrying non-existent delivery returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.post(f"/api/outbound-webhooks/deliveries/{fake_id}/retry")

    assert response.status_code == 404


# =============================================================================
# Integration Scenarios
# =============================================================================


@pytest.mark.asyncio
async def test_webhook_lifecycle(client, sample_webhook_create):
    """Test complete webhook lifecycle: create, update, disable, enable, delete."""
    # 1. Create webhook
    create_response = await client.post("/api/outbound-webhooks", json=sample_webhook_create)
    assert create_response.status_code == 201
    webhook = create_response.json()
    webhook_id = webhook["id"]
    assert webhook["enabled"] is True

    # 2. Update webhook
    update_data = {"name": unique_id("Updated Webhook")}
    update_response = await client.patch(f"/api/outbound-webhooks/{webhook_id}", json=update_data)
    assert update_response.status_code == 200
    assert update_response.json()["name"] == update_data["name"]

    # 3. Disable webhook
    disable_response = await client.post(f"/api/outbound-webhooks/{webhook_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False

    # 4. Enable webhook
    enable_response = await client.post(f"/api/outbound-webhooks/{webhook_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["enabled"] is True

    # 5. Delete webhook
    delete_response = await client.delete(f"/api/outbound-webhooks/{webhook_id}")
    assert delete_response.status_code == 204

    # 6. Verify deletion
    get_response = await client.get(f"/api/outbound-webhooks/{webhook_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_list_webhooks_filtering(client, sample_webhook_create):
    """Test listing webhooks with enabled_only filter."""
    # Create enabled webhook
    enabled_data = {**sample_webhook_create, "enabled": True}
    enabled_response = await client.post("/api/outbound-webhooks", json=enabled_data)
    assert enabled_response.status_code == 201
    enabled_id = enabled_response.json()["id"]

    # Create disabled webhook
    disabled_data = {
        **sample_webhook_create,
        "name": unique_id("Disabled Webhook"),
        "enabled": False,
    }
    disabled_response = await client.post("/api/outbound-webhooks", json=disabled_data)
    assert disabled_response.status_code == 201
    disabled_id = disabled_response.json()["id"]

    # List all webhooks
    all_response = await client.get("/api/outbound-webhooks")
    assert all_response.status_code == 200
    all_webhooks = all_response.json()["webhooks"]
    all_ids = [w["id"] for w in all_webhooks]
    assert enabled_id in all_ids
    assert disabled_id in all_ids

    # List only enabled webhooks
    enabled_only_response = await client.get("/api/outbound-webhooks?enabled_only=true")
    assert enabled_only_response.status_code == 200
    enabled_webhooks = enabled_only_response.json()["webhooks"]
    enabled_only_ids = [w["id"] for w in enabled_webhooks]
    assert all(w["enabled"] for w in enabled_webhooks)
    # Disabled webhook should not be in enabled-only list
    assert disabled_id not in enabled_only_ids
