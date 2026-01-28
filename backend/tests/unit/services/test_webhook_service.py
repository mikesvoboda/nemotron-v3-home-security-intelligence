"""Comprehensive unit tests for WebhookService.

Tests cover:
- CRUD operations (create, get, list, update, delete webhooks)
- Webhook delivery with HTTP request handling
- Retry logic with exponential backoff
- HMAC-SHA256 payload signing
- Custom payload templates via Jinja2
- Integration-specific formatting (Slack, Discord, Teams)
- Delivery tracking and statistics
- Error handling and edge cases
- Background webhook triggering
- Delivery retry management
- Health summary calculations
"""

from __future__ import annotations

import base64
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from backend.api.schemas.outbound_webhook import (
    WebhookAuthConfig,
    WebhookCreate,
    WebhookEventType,
    WebhookUpdate,
)
from backend.core.time_utils import utc_now
from backend.models.outbound_webhook import (
    IntegrationType,
    OutboundWebhook,
    WebhookDelivery,
    WebhookDeliveryStatus,
)
from backend.services.webhook_service import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    MAX_BACKOFF_SECONDS,
    MAX_RESPONSE_BODY_LENGTH,
    WebhookService,
    get_webhook_service,
    trigger_webhook_background,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def webhook_service():
    """Create a WebhookService instance."""
    return WebhookService()


@pytest.fixture
def mock_http_client():
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_http_response():
    """Create a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = '{"status": "ok"}'
    return response


@pytest.fixture
def webhook_create_data():
    """Create sample WebhookCreate data."""
    return WebhookCreate(
        name="Test Webhook",
        url="https://example.com/webhook",
        event_types=[WebhookEventType.ALERT_FIRED],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        auth=None,
        custom_headers={},
        payload_template=None,
        max_retries=DEFAULT_MAX_RETRIES,
        retry_delay_seconds=DEFAULT_RETRY_DELAY,
    )


@pytest.fixture
async def sample_webhook(mock_db_session, webhook_create_data):
    """Create a sample OutboundWebhook instance."""
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name=webhook_create_data.name,
        url=str(webhook_create_data.url),
        event_types=[et.value for et in webhook_create_data.event_types],
        integration_type=webhook_create_data.integration_type,
        enabled=webhook_create_data.enabled,
        auth_config=None,
        custom_headers={},
        payload_template=None,
        max_retries=webhook_create_data.max_retries,
        retry_delay_seconds=webhook_create_data.retry_delay_seconds,
        signing_secret="a" * 64,  # 32 bytes hex encoded
        total_deliveries=0,
        successful_deliveries=0,
    )
    return webhook


# =============================================================================
# CRUD Operation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_webhook_success(webhook_service, mock_db_session, webhook_create_data):
    """Test successful webhook creation with generated signing secret."""
    # Arrange
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    # Act
    webhook = await webhook_service.create_webhook(mock_db_session, webhook_create_data)

    # Assert
    assert webhook.name == webhook_create_data.name
    assert webhook.url == str(webhook_create_data.url)
    assert webhook.event_types == [WebhookEventType.ALERT_FIRED.value]
    assert webhook.enabled is True
    assert webhook.signing_secret is not None
    assert len(webhook.signing_secret) == 64  # 32 bytes hex encoded
    mock_db_session.add.assert_called_once()
    mock_db_session.flush.assert_called_once()
    mock_db_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_create_webhook_with_auth_bearer(webhook_service, mock_db_session):
    """Test webhook creation with bearer token authentication."""
    # Arrange
    auth = WebhookAuthConfig(type="bearer", token="secret-token-123")  # pragma: allowlist secret
    data = WebhookCreate(
        name="Auth Webhook",
        url="https://api.example.com/webhook",
        event_types=[WebhookEventType.EVENT_CREATED],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        auth=auth,
    )
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    # Act
    webhook = await webhook_service.create_webhook(mock_db_session, data)

    # Assert
    assert webhook.auth_config["type"] == "bearer"
    assert webhook.auth_config["token"] == "secret-token-123"  # pragma: allowlist secret
    mock_db_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_webhook_with_auth_basic(webhook_service, mock_db_session):
    """Test webhook creation with basic authentication."""
    # Arrange
    auth = WebhookAuthConfig(
        type="basic",
        username="user",
        password="pass",  # pragma: allowlist secret
    )
    data = WebhookCreate(
        name="Basic Auth Webhook",
        url="https://api.example.com/webhook",
        event_types=[WebhookEventType.ALERT_FIRED],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        auth=auth,
    )
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    # Act
    webhook = await webhook_service.create_webhook(mock_db_session, data)

    # Assert
    assert webhook.auth_config["type"] == "basic"
    assert webhook.auth_config["username"] == "user"
    assert webhook.auth_config["password"] == "pass"  # pragma: allowlist secret


@pytest.mark.asyncio
async def test_create_webhook_with_custom_headers(webhook_service, mock_db_session):
    """Test webhook creation with custom headers."""
    # Arrange
    custom_headers = {"X-Custom-Header": "value", "X-API-Version": "v1"}
    data = WebhookCreate(
        name="Custom Headers Webhook",
        url="https://api.example.com/webhook",
        event_types=[WebhookEventType.ALERT_FIRED],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        custom_headers=custom_headers,
    )
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    # Act
    webhook = await webhook_service.create_webhook(mock_db_session, data)

    # Assert
    assert webhook.custom_headers == custom_headers


@pytest.mark.asyncio
async def test_get_webhook_found(webhook_service, mock_db_session, sample_webhook):
    """Test retrieving an existing webhook by ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.get_webhook(mock_db_session, sample_webhook.id)

    # Assert
    assert result == sample_webhook
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_webhook_not_found(webhook_service, mock_db_session):
    """Test retrieving a non-existent webhook returns None."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.get_webhook(mock_db_session, str(uuid4()))

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_list_webhooks_all(webhook_service, mock_db_session, sample_webhook):
    """Test listing all webhooks."""
    # Arrange
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_webhook]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.list_webhooks(mock_db_session, enabled_only=False)

    # Assert
    assert len(result) == 1
    assert result[0] == sample_webhook


@pytest.mark.asyncio
async def test_list_webhooks_enabled_only(webhook_service, mock_db_session, sample_webhook):
    """Test listing only enabled webhooks."""
    # Arrange
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_webhook]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.list_webhooks(mock_db_session, enabled_only=True)

    # Assert
    assert len(result) == 1
    assert result[0].enabled is True


@pytest.mark.asyncio
async def test_update_webhook_name(webhook_service, mock_db_session, sample_webhook):
    """Test updating webhook name."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    update_data = WebhookUpdate(name="Updated Name")

    # Act
    result = await webhook_service.update_webhook(mock_db_session, sample_webhook.id, update_data)

    # Assert
    assert result.name == "Updated Name"
    mock_db_session.flush.assert_called_once()
    mock_db_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_webhook_url(webhook_service, mock_db_session, sample_webhook):
    """Test updating webhook URL."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    new_url = "https://new.example.com/hook"
    update_data = WebhookUpdate(url=new_url)

    # Act
    result = await webhook_service.update_webhook(mock_db_session, sample_webhook.id, update_data)

    # Assert
    assert result.url == new_url


@pytest.mark.asyncio
async def test_update_webhook_event_types(webhook_service, mock_db_session, sample_webhook):
    """Test updating webhook event types."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    new_events = [WebhookEventType.ALERT_FIRED, WebhookEventType.EVENT_CREATED]
    update_data = WebhookUpdate(event_types=new_events)

    # Act
    result = await webhook_service.update_webhook(mock_db_session, sample_webhook.id, update_data)

    # Assert
    assert len(result.event_types) == 2
    assert WebhookEventType.ALERT_FIRED.value in result.event_types
    assert WebhookEventType.EVENT_CREATED.value in result.event_types


@pytest.mark.asyncio
async def test_update_webhook_enabled_status(webhook_service, mock_db_session, sample_webhook):
    """Test updating webhook enabled status."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    update_data = WebhookUpdate(enabled=False)

    # Act
    result = await webhook_service.update_webhook(mock_db_session, sample_webhook.id, update_data)

    # Assert
    assert result.enabled is False


@pytest.mark.asyncio
async def test_update_webhook_not_found(webhook_service, mock_db_session):
    """Test updating a non-existent webhook returns None."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    update_data = WebhookUpdate(name="New Name")

    # Act
    result = await webhook_service.update_webhook(mock_db_session, str(uuid4()), update_data)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_update_webhook_no_changes(webhook_service, mock_db_session, sample_webhook):
    """Test updating webhook with no changes doesn't flush."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.flush = AsyncMock()

    update_data = WebhookUpdate()  # No fields set

    # Act
    result = await webhook_service.update_webhook(mock_db_session, sample_webhook.id, update_data)

    # Assert
    assert result == sample_webhook
    mock_db_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_delete_webhook_success(webhook_service, mock_db_session, sample_webhook):
    """Test successful webhook deletion."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.delete = AsyncMock()
    mock_db_session.flush = AsyncMock()

    # Act
    result = await webhook_service.delete_webhook(mock_db_session, sample_webhook.id)

    # Assert
    assert result is True
    mock_db_session.delete.assert_called_once_with(sample_webhook)
    mock_db_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_delete_webhook_not_found(webhook_service, mock_db_session):
    """Test deleting a non-existent webhook returns False."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.delete_webhook(mock_db_session, str(uuid4()))

    # Assert
    assert result is False


# =============================================================================
# Delivery Operation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_deliver_webhook_success(webhook_service, mock_db_session, sample_webhook):
    """Test successful webhook delivery."""
    # Arrange
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    event_data = {"alert_id": "test-123", "severity": "high"}

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (200, '{"status": "ok"}', 150)

        # Act
        delivery = await webhook_service.deliver_webhook(
            mock_db_session,
            sample_webhook,
            WebhookEventType.ALERT_FIRED,
            event_data,
            event_id="evt-123",
        )

        # Assert
        assert delivery.status == WebhookDeliveryStatus.SUCCESS
        assert delivery.status_code == 200
        assert delivery.response_time_ms == 150
        assert delivery.delivered_at is not None
        assert sample_webhook.total_deliveries == 1
        assert sample_webhook.successful_deliveries == 1
        assert sample_webhook.last_delivery_status == WebhookDeliveryStatus.SUCCESS.value


@pytest.mark.asyncio
async def test_deliver_webhook_http_error(webhook_service, mock_db_session, sample_webhook):
    """Test webhook delivery with HTTP error status."""
    # Arrange
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    event_data = {"alert_id": "test-123"}

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (500, "Internal Server Error", 100)

        # Act
        delivery = await webhook_service.deliver_webhook(
            mock_db_session,
            sample_webhook,
            WebhookEventType.ALERT_FIRED,
            event_data,
        )

        # Assert
        assert delivery.status == WebhookDeliveryStatus.RETRYING
        assert delivery.status_code == 500
        assert delivery.error_message == "HTTP 500"
        assert delivery.next_retry_at is not None
        assert sample_webhook.total_deliveries == 1
        assert sample_webhook.last_delivery_status == WebhookDeliveryStatus.RETRYING.value


@pytest.mark.asyncio
async def test_deliver_webhook_network_error(webhook_service, mock_db_session, sample_webhook):
    """Test webhook delivery with network error."""
    # Arrange
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    event_data = {"alert_id": "test-123"}

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = httpx.RequestError("Connection refused")

        # Act
        delivery = await webhook_service.deliver_webhook(
            mock_db_session,
            sample_webhook,
            WebhookEventType.ALERT_FIRED,
            event_data,
        )

        # Assert
        assert delivery.status == WebhookDeliveryStatus.RETRYING
        assert "Connection refused" in delivery.error_message
        assert delivery.next_retry_at is not None


@pytest.mark.asyncio
async def test_deliver_webhook_unexpected_error(webhook_service, mock_db_session, sample_webhook):
    """Test webhook delivery with unexpected error."""
    # Arrange
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    event_data = {"alert_id": "test-123"}

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = Exception("Unexpected error")

        # Act
        delivery = await webhook_service.deliver_webhook(
            mock_db_session,
            sample_webhook,
            WebhookEventType.ALERT_FIRED,
            event_data,
        )

        # Assert
        assert delivery.status == WebhookDeliveryStatus.FAILED
        assert "Unexpected error" in delivery.error_message
        assert sample_webhook.last_delivery_status == WebhookDeliveryStatus.FAILED.value


@pytest.mark.asyncio
async def test_deliver_webhook_max_retries_exhausted(webhook_service, mock_db_session):
    """Test delivery failure after max retries exhausted."""
    # Arrange - webhook with max_retries=2 allows 2 attempts total
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        max_retries=2,  # Allows up to 2 attempts
        retry_delay_seconds=10,
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )

    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (500, "Error", 100)

        # Act - First delivery attempt (attempt_count=1)
        delivery = await webhook_service.deliver_webhook(
            mock_db_session,
            webhook,
            WebhookEventType.ALERT_FIRED,
            {},
        )

        # Assert - First attempt should schedule retry since 1 < 2
        assert delivery.status == WebhookDeliveryStatus.RETRYING
        assert delivery.next_retry_at is not None

        # Now simulate reaching max retries
        delivery.attempt_count = 2  # At max_retries now
        await webhook_service._handle_delivery_failure(mock_db_session, webhook, delivery)

        # Assert - Now should be FAILED since 2 < 2 is False
        assert delivery.status == WebhookDeliveryStatus.FAILED


@pytest.mark.asyncio
async def test_trigger_webhooks_for_event(webhook_service, mock_db_session, sample_webhook):
    """Test triggering multiple webhooks for an event."""
    # Arrange
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_webhook]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    event_data = {"alert_id": "test-123"}

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (200, "OK", 100)

        # Act
        deliveries = await webhook_service.trigger_webhooks_for_event(
            mock_db_session,
            WebhookEventType.ALERT_FIRED,
            event_data,
            event_id="evt-123",
        )

        # Assert
        assert len(deliveries) == 1
        assert deliveries[0].status == WebhookDeliveryStatus.SUCCESS


@pytest.mark.asyncio
async def test_trigger_webhooks_no_subscribers(webhook_service, mock_db_session):
    """Test triggering webhooks when no webhooks subscribe to event."""
    # Arrange
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    deliveries = await webhook_service.trigger_webhooks_for_event(
        mock_db_session,
        WebhookEventType.EVENT_CREATED,
        {"event_id": "evt-123"},
    )

    # Assert
    assert len(deliveries) == 0


# =============================================================================
# Test Webhook Tests
# =============================================================================


@pytest.mark.asyncio
async def test_test_webhook_success(webhook_service, mock_db_session, sample_webhook):
    """Test webhook testing with successful response."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (200, '{"status": "ok"}', 120)

        # Act
        result = await webhook_service.test_webhook(
            mock_db_session,
            sample_webhook.id,
            WebhookEventType.ALERT_FIRED,
        )

        # Assert
        assert result.success is True
        assert result.status_code == 200
        assert result.response_time_ms == 120
        assert result.error_message is None


@pytest.mark.asyncio
async def test_test_webhook_http_error(webhook_service, mock_db_session, sample_webhook):
    """Test webhook testing with HTTP error."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (404, "Not Found", 50)

        # Act
        result = await webhook_service.test_webhook(
            mock_db_session,
            sample_webhook.id,
            WebhookEventType.ALERT_FIRED,
        )

        # Assert
        assert result.success is False
        assert result.status_code == 404
        assert result.error_message == "HTTP 404"


@pytest.mark.asyncio
async def test_test_webhook_network_error(webhook_service, mock_db_session, sample_webhook):
    """Test webhook testing with network error."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = httpx.RequestError("Connection timeout")

        # Act
        result = await webhook_service.test_webhook(
            mock_db_session,
            sample_webhook.id,
            WebhookEventType.ALERT_FIRED,
        )

        # Assert
        assert result.success is False
        assert "Connection timeout" in result.error_message


@pytest.mark.asyncio
async def test_test_webhook_not_found(webhook_service, mock_db_session):
    """Test webhook testing when webhook doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.test_webhook(
        mock_db_session,
        str(uuid4()),
        WebhookEventType.ALERT_FIRED,
    )

    # Assert
    assert result.success is False
    assert result.error_message == "Webhook not found"


# =============================================================================
# Retry Delivery Tests
# =============================================================================


@pytest.mark.asyncio
async def test_retry_delivery_success(webhook_service, mock_db_session, sample_webhook):
    """Test successful manual retry of failed delivery."""
    # Arrange
    delivery = WebhookDelivery(
        id=str(uuid4()),
        webhook_id=sample_webhook.id,
        event_type=WebhookEventType.ALERT_FIRED.value,
        status=WebhookDeliveryStatus.FAILED,
        request_payload={"test": True},
        attempt_count=1,
    )

    mock_delivery_result = MagicMock()
    mock_delivery_result.scalar_one_or_none.return_value = delivery
    mock_webhook_result = MagicMock()
    mock_webhook_result.scalar_one_or_none.return_value = sample_webhook

    mock_db_session.execute = AsyncMock(side_effect=[mock_delivery_result, mock_webhook_result])
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (200, "OK", 100)

        # Act
        result = await webhook_service.retry_delivery(mock_db_session, delivery.id)

        # Assert
        assert result.status == WebhookDeliveryStatus.SUCCESS
        assert result.attempt_count == 2
        assert sample_webhook.successful_deliveries == 1


@pytest.mark.asyncio
async def test_retry_delivery_still_fails(webhook_service, mock_db_session, sample_webhook):
    """Test manual retry that still fails."""
    # Arrange
    delivery = WebhookDelivery(
        id=str(uuid4()),
        webhook_id=sample_webhook.id,
        event_type=WebhookEventType.ALERT_FIRED.value,
        status=WebhookDeliveryStatus.FAILED,
        request_payload={"test": True},
        attempt_count=1,
    )

    mock_delivery_result = MagicMock()
    mock_delivery_result.scalar_one_or_none.return_value = delivery
    mock_webhook_result = MagicMock()
    mock_webhook_result.scalar_one_or_none.return_value = sample_webhook

    mock_db_session.execute = AsyncMock(side_effect=[mock_delivery_result, mock_webhook_result])
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (500, "Error", 50)

        # Act
        result = await webhook_service.retry_delivery(mock_db_session, delivery.id)

        # Assert
        assert result.status == WebhookDeliveryStatus.FAILED
        assert result.error_message == "HTTP 500"


@pytest.mark.asyncio
async def test_retry_delivery_not_found(webhook_service, mock_db_session):
    """Test retrying delivery that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.retry_delivery(mock_db_session, str(uuid4()))

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_retry_delivery_webhook_deleted(webhook_service, mock_db_session):
    """Test retrying delivery when webhook has been deleted."""
    # Arrange
    delivery = WebhookDelivery(
        id=str(uuid4()),
        webhook_id=str(uuid4()),
        event_type=WebhookEventType.ALERT_FIRED.value,
        status=WebhookDeliveryStatus.FAILED,
        request_payload={},
        attempt_count=1,
    )

    mock_delivery_result = MagicMock()
    mock_delivery_result.scalar_one_or_none.return_value = delivery
    mock_webhook_result = MagicMock()
    mock_webhook_result.scalar_one_or_none.return_value = None

    mock_db_session.execute = AsyncMock(side_effect=[mock_delivery_result, mock_webhook_result])

    # Act
    result = await webhook_service.retry_delivery(mock_db_session, delivery.id)

    # Assert
    assert result is None


# =============================================================================
# Statistics Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_health_summary(webhook_service, mock_db_session):
    """Test getting webhook health summary."""
    # Arrange
    # Mock total webhooks count
    total_result = MagicMock()
    total_result.scalar.return_value = 5

    # Mock enabled webhooks count
    enabled_result = MagicMock()
    enabled_result.scalar.return_value = 4

    # Mock deliveries 24h count
    deliveries_24h_result = MagicMock()
    deliveries_24h_result.scalar.return_value = 100

    # Mock successful 24h count
    successful_24h_result = MagicMock()
    successful_24h_result.scalar.return_value = 90

    # Mock failed 24h count
    failed_24h_result = MagicMock()
    failed_24h_result.scalar.return_value = 10

    # Mock average response time
    avg_response_result = MagicMock()
    avg_response_result.scalar.return_value = 150.5

    # Mock list_webhooks call
    mock_webhooks = [
        MagicMock(total_deliveries=100, successful_deliveries=95),  # 95% - healthy
        MagicMock(total_deliveries=100, successful_deliveries=80),  # 80% - neither
        MagicMock(total_deliveries=100, successful_deliveries=45),  # 45% - unhealthy
        MagicMock(total_deliveries=0, successful_deliveries=0),  # No deliveries
    ]

    mock_db_session.execute = AsyncMock(
        side_effect=[
            total_result,
            enabled_result,
            deliveries_24h_result,
            successful_24h_result,
            failed_24h_result,
            avg_response_result,
        ]
    )

    with patch.object(webhook_service, "list_webhooks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_webhooks

        # Act
        summary = await webhook_service.get_health_summary(mock_db_session)

        # Assert
        assert summary.total_webhooks == 5
        assert summary.enabled_webhooks == 4
        assert summary.healthy_webhooks == 1
        assert summary.unhealthy_webhooks == 1
        assert summary.total_deliveries_24h == 100
        assert summary.successful_deliveries_24h == 90
        assert summary.failed_deliveries_24h == 10
        assert summary.average_response_time_ms == 150.5


@pytest.mark.asyncio
async def test_get_deliveries(webhook_service, mock_db_session, sample_webhook):
    """Test getting delivery history for a webhook."""
    # Arrange
    deliveries = [
        MagicMock(id=str(uuid4()), webhook_id=sample_webhook.id),
        MagicMock(id=str(uuid4()), webhook_id=sample_webhook.id),
    ]

    count_result = MagicMock()
    count_result.scalar.return_value = 2

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = deliveries
    deliveries_result = MagicMock()
    deliveries_result.scalars.return_value = mock_scalars

    mock_db_session.execute = AsyncMock(side_effect=[count_result, deliveries_result])

    # Act
    result_deliveries, total = await webhook_service.get_deliveries(
        mock_db_session, sample_webhook.id, limit=50, offset=0
    )

    # Assert
    assert len(result_deliveries) == 2
    assert total == 2


@pytest.mark.asyncio
async def test_get_delivery(webhook_service, mock_db_session):
    """Test getting a specific delivery by ID."""
    # Arrange
    delivery = MagicMock(id=str(uuid4()))
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = delivery
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await webhook_service.get_delivery(mock_db_session, delivery.id)

    # Assert
    assert result == delivery


# =============================================================================
# Payload Building Tests
# =============================================================================


def test_build_payload_standard(webhook_service, sample_webhook):
    """Test building standard payload without template."""
    # Arrange
    event_data = {"alert_id": "test-123", "severity": "high"}

    # Act
    payload = webhook_service._build_payload(
        sample_webhook, WebhookEventType.ALERT_FIRED, event_data
    )

    # Assert
    assert payload["event_type"] == WebhookEventType.ALERT_FIRED.value
    assert payload["webhook_id"] == sample_webhook.id
    assert payload["data"] == event_data
    assert "timestamp" in payload


def test_build_payload_with_template(webhook_service):
    """Test building payload with custom Jinja2 template."""
    # Arrange
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        payload_template='{"message": "Alert {{ data.alert_id }}", "level": "{{ data.severity }}"}',
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    event_data = {"alert_id": "test-123", "severity": "critical"}

    # Act
    payload = webhook_service._build_payload(webhook, WebhookEventType.ALERT_FIRED, event_data)

    # Assert
    assert payload["message"] == "Alert test-123"
    assert payload["level"] == "critical"


def test_build_payload_with_invalid_template(webhook_service):
    """Test building payload with invalid template falls back to standard."""
    # Arrange
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        payload_template='{"invalid": {{ undefined_var }}}',  # Invalid template
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    event_data = {"alert_id": "test-123"}

    # Act
    payload = webhook_service._build_payload(webhook, WebhookEventType.ALERT_FIRED, event_data)

    # Assert - Should fall back to standard payload
    assert "event_type" in payload
    assert payload["event_type"] == WebhookEventType.ALERT_FIRED.value


def test_format_slack_payload(webhook_service):
    """Test formatting payload for Slack."""
    # Arrange
    payload = {
        "event_type": "alert_fired",
        "data": {"alert_id": "test-123", "severity": "high", "camera": "front_door"},
    }

    # Act
    result = webhook_service._format_slack_payload(payload)

    # Assert
    assert "text" in result
    assert "blocks" in result
    assert "alert_fired" in result["text"]
    assert "alert_id" in result["text"]


def test_format_discord_payload(webhook_service):
    """Test formatting payload for Discord."""
    # Arrange
    payload = {
        "event_type": "event_created",
        "timestamp": "2024-01-01T00:00:00Z",
        "data": {"event_id": "evt-123", "camera": "front_door"},
    }

    # Act
    result = webhook_service._format_discord_payload(payload)

    # Assert
    assert "embeds" in result
    assert len(result["embeds"]) == 1
    assert result["embeds"][0]["title"] == "Event Created"
    assert "fields" in result["embeds"][0]


def test_format_teams_payload(webhook_service):
    """Test formatting payload for Microsoft Teams."""
    # Arrange
    payload = {
        "event_type": "anomaly_detected",
        "data": {"zone": "driveway", "score": 0.87},
    }

    # Act
    result = webhook_service._format_teams_payload(payload)

    # Assert
    assert result["@type"] == "MessageCard"
    assert result["title"] == "Anomaly Detected"
    assert "sections" in result
    assert "facts" in result["sections"][0]


# =============================================================================
# Signing Tests
# =============================================================================


def test_sign_payload(webhook_service):
    """Test HMAC-SHA256 payload signing."""
    # Arrange
    payload = {"event_type": "alert_fired", "data": {"alert_id": "test"}}
    # nosemgrep: hardcoded-password
    secret = "a" * 64  # 32 bytes hex encoded  # pragma: allowlist secret

    # Act
    signature = webhook_service._sign_payload(payload, secret)

    # Assert
    assert len(signature) == 64  # SHA256 hex digest is 64 chars
    assert signature.isalnum()  # Only hex characters

    # Verify signature is deterministic
    signature2 = webhook_service._sign_payload(payload, secret)
    assert signature == signature2


def test_sign_payload_different_secrets_different_signatures(webhook_service):
    """Test that different secrets produce different signatures."""
    # Arrange
    payload = {"test": "data"}
    secret1 = "a" * 64
    secret2 = "b" * 64

    # Act
    sig1 = webhook_service._sign_payload(payload, secret1)
    sig2 = webhook_service._sign_payload(payload, secret2)

    # Assert
    assert sig1 != sig2


# =============================================================================
# HTTP Request Tests
# =============================================================================


@pytest.mark.asyncio
async def test_send_request_basic(webhook_service, sample_webhook):
    """Test sending basic HTTP request."""
    # Arrange
    payload = {"test": "data"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Act
        status, body, response_time = await webhook_service._send_request(sample_webhook, payload)

        # Assert
        assert status == 200
        assert body == "OK"
        assert response_time >= 0  # Response time can be 0 for fast mocked calls
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_request_with_bearer_auth(webhook_service):
    """Test sending request with bearer token authentication."""
    # Arrange
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://api.example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        auth_config={"type": "bearer", "token": "secret-token-123"},
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    payload = {"test": "data"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Act
        await webhook_service._send_request(webhook, payload)

        # Assert
        call_args = mock_client.post.call_args
        headers = call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer secret-token-123"


@pytest.mark.asyncio
async def test_send_request_with_basic_auth(webhook_service):
    """Test sending request with basic authentication."""
    # Arrange
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://api.example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        auth_config={
            "type": "basic",
            "username": "user",
            "password": "pass",  # pragma: allowlist secret
        },
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    payload = {"test": "data"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Act
        await webhook_service._send_request(webhook, payload)

        # Assert
        call_args = mock_client.post.call_args
        headers = call_args.kwargs["headers"]
        expected_credentials = base64.b64encode(b"user:pass").decode()
        assert headers["Authorization"] == f"Basic {expected_credentials}"


@pytest.mark.asyncio
async def test_send_request_with_custom_header_auth(webhook_service):
    """Test sending request with custom header authentication."""
    # Arrange
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://api.example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        auth_config={
            "type": "header",
            "header_name": "X-API-Key",
            "header_value": "my-api-key",
        },
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    payload = {"test": "data"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Act
        await webhook_service._send_request(webhook, payload)

        # Assert
        call_args = mock_client.post.call_args
        headers = call_args.kwargs["headers"]
        assert headers["X-API-Key"] == "my-api-key"


@pytest.mark.asyncio
async def test_send_request_with_custom_headers(webhook_service):
    """Test sending request with custom headers."""
    # Arrange
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://api.example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        custom_headers={"X-Custom": "value", "X-Version": "v1"},
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    payload = {"test": "data"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Act
        await webhook_service._send_request(webhook, payload)

        # Assert
        call_args = mock_client.post.call_args
        headers = call_args.kwargs["headers"]
        assert headers["X-Custom"] == "value"
        assert headers["X-Version"] == "v1"


@pytest.mark.asyncio
async def test_send_request_with_signature(webhook_service, sample_webhook):
    """Test that signature headers are added to request."""
    # Arrange
    payload = {"test": "data"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Act
        await webhook_service._send_request(sample_webhook, payload)

        # Assert
        call_args = mock_client.post.call_args
        headers = call_args.kwargs["headers"]
        assert "X-Webhook-Signature" in headers
        assert "X-Webhook-Signature-256" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")


# =============================================================================
# Retry Calculation Tests
# =============================================================================


def test_calculate_next_retry_first_attempt(webhook_service):
    """Test retry calculation for first attempt."""
    # Arrange
    base_delay = 10

    # Act
    next_retry = webhook_service._calculate_next_retry(1, base_delay)

    # Assert
    expected_delay = timedelta(seconds=base_delay)
    assert next_retry > utc_now()
    assert next_retry <= utc_now() + expected_delay + timedelta(seconds=1)


def test_calculate_next_retry_exponential_backoff(webhook_service):
    """Test exponential backoff calculation."""
    # Arrange
    base_delay = 10

    # Act
    retry1 = webhook_service._calculate_next_retry(1, base_delay)
    retry2 = webhook_service._calculate_next_retry(2, base_delay)
    retry3 = webhook_service._calculate_next_retry(3, base_delay)

    # Assert - Each delay should be roughly double the previous
    # attempt 1: 10s, attempt 2: 20s, attempt 3: 40s
    now = utc_now()
    delay1 = (retry1 - now).total_seconds()
    delay2 = (retry2 - now).total_seconds()
    delay3 = (retry3 - now).total_seconds()

    assert 9 <= delay1 <= 11  # ~10s
    assert 19 <= delay2 <= 21  # ~20s
    assert 39 <= delay3 <= 41  # ~40s


def test_calculate_next_retry_max_backoff(webhook_service):
    """Test that retry delay is capped at maximum."""
    # Arrange
    base_delay = 10

    # Act - High attempt number that would exceed max
    next_retry = webhook_service._calculate_next_retry(20, base_delay)

    # Assert
    max_delay = timedelta(seconds=MAX_BACKOFF_SECONDS)
    assert next_retry <= utc_now() + max_delay + timedelta(seconds=1)


# =============================================================================
# Test Event Data Generation Tests
# =============================================================================


def test_build_test_event_data_alert_fired(webhook_service):
    """Test building test data for alert_fired event."""
    # Act
    data = webhook_service._build_test_event_data(WebhookEventType.ALERT_FIRED)

    # Assert
    assert data["test"] is True
    assert "timestamp" in data
    assert "alert_id" in data
    assert "severity" in data
    assert "camera_id" in data


def test_build_test_event_data_event_created(webhook_service):
    """Test building test data for event_created event."""
    # Act
    data = webhook_service._build_test_event_data(WebhookEventType.EVENT_CREATED)

    # Assert
    assert data["test"] is True
    assert "event_id" in data
    assert "camera_id" in data


def test_build_test_event_data_unknown_event(webhook_service):
    """Test building test data for unknown event type."""
    # Act
    data = webhook_service._build_test_event_data(WebhookEventType.SYSTEM_HEALTH_CHANGED)

    # Assert
    assert data["test"] is True
    assert "timestamp" in data
    assert "component" in data


# =============================================================================
# Singleton and Background Trigger Tests
# =============================================================================


def test_get_webhook_service_singleton():
    """Test that get_webhook_service returns singleton instance."""
    # Act
    service1 = get_webhook_service()
    service2 = get_webhook_service()

    # Assert
    assert service1 is service2


@pytest.mark.asyncio
async def test_trigger_webhook_background_success(mock_db_session):
    """Test background webhook trigger succeeds."""
    # Arrange
    event_data = {"alert_id": "test"}

    with patch("backend.services.webhook_service.get_webhook_service") as mock_get:
        mock_service = MagicMock()
        mock_service.trigger_webhooks_for_event = AsyncMock(return_value=[])
        mock_get.return_value = mock_service

        # Act
        await trigger_webhook_background(
            mock_db_session,
            WebhookEventType.ALERT_FIRED,
            event_data,
            event_id="evt-123",
        )

        # Assert
        mock_service.trigger_webhooks_for_event.assert_called_once_with(
            mock_db_session,
            WebhookEventType.ALERT_FIRED,
            event_data,
            event_id="evt-123",
        )


@pytest.mark.asyncio
async def test_trigger_webhook_background_handles_exception(mock_db_session):
    """Test background webhook trigger handles exceptions gracefully."""
    # Arrange
    event_data = {"alert_id": "test"}

    with patch("backend.services.webhook_service.get_webhook_service") as mock_get:
        mock_service = MagicMock()
        mock_service.trigger_webhooks_for_event = AsyncMock(side_effect=Exception("Database error"))
        mock_get.return_value = mock_service

        # Act - Should not raise exception
        await trigger_webhook_background(
            mock_db_session,
            WebhookEventType.ALERT_FIRED,
            event_data,
        )

        # Assert - Exception was caught and logged
        mock_service.trigger_webhooks_for_event.assert_called_once()


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_deliver_webhook_response_body_truncation(
    webhook_service, mock_db_session, sample_webhook
):
    """Test that long response bodies are truncated."""
    # Arrange
    long_response = "x" * (MAX_RESPONSE_BODY_LENGTH + 1000)
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    with patch.object(webhook_service, "_send_request", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (200, long_response, 100)

        # Act
        delivery = await webhook_service.deliver_webhook(
            mock_db_session,
            sample_webhook,
            WebhookEventType.ALERT_FIRED,
            {},
        )

        # Assert
        assert len(delivery.response_body) == MAX_RESPONSE_BODY_LENGTH


@pytest.mark.asyncio
async def test_update_webhook_multiple_fields(webhook_service, mock_db_session, sample_webhook):
    """Test updating multiple webhook fields at once."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_webhook
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    update_data = WebhookUpdate(
        name="New Name",
        enabled=False,
        max_retries=10,
    )

    # Act
    result = await webhook_service.update_webhook(mock_db_session, sample_webhook.id, update_data)

    # Assert
    assert result.name == "New Name"
    assert result.enabled is False
    assert result.max_retries == 10


def test_build_payload_with_template_direct_field_access(webhook_service):
    """Test template with direct field access from event_data."""
    # Arrange
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        payload_template='{"alert": "{{ alert_id }}", "sev": "{{ severity }}"}',
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    event_data = {"alert_id": "test-456", "severity": "low"}

    # Act
    payload = webhook_service._build_payload(webhook, WebhookEventType.ALERT_FIRED, event_data)

    # Assert
    assert payload["alert"] == "test-456"
    assert payload["sev"] == "low"


def test_format_for_integration_generic(webhook_service):
    """Test that generic integration returns payload as-is."""
    # Arrange
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Test",
        url="https://example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        signing_secret="a" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    payload = {"custom": "data", "nested": {"value": 123}}

    # Act
    result = webhook_service._format_for_integration(webhook, payload)

    # Assert
    assert result == payload
