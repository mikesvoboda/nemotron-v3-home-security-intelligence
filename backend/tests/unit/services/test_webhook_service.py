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

import asyncio
import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import and_, func, select

import backend.core.url_validation as uv
import backend.services.webhook_service as W
import backend.services.webhook_service as webhook_service_module
from backend.api.schemas.outbound_webhook import (
    IntegrationType as SchemaIntegrationType,
)
from backend.api.schemas.outbound_webhook import (
    WebhookAuthConfig,
    WebhookCreate,
    WebhookEventType,
    WebhookHealthSummary,
    WebhookTestResponse,
    WebhookUpdate,
)
from backend.api.schemas.outbound_webhook import (
    WebhookDeliveryStatus as SchemaWebhookDeliveryStatus,
)
from backend.core.time_utils import utc_now
from backend.core.url_validation import SSRFValidationError
from backend.models.outbound_webhook import (
    IntegrationType,
    OutboundWebhook,
    WebhookDelivery,
    WebhookDeliveryStatus,
)
from backend.services.webhook_service import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_TIMEOUT,
    MAX_BACKOFF_SECONDS,
    MAX_RESPONSE_BODY_LENGTH,
    WebhookService,
    get_webhook_service,
    trigger_webhook_background,
)

# pytestmark reconciled (B4.2 step 2): the four consolidated battery files set
# pytestmark = pytest.mark.unit at module level; the consolidated file adopts
# that value (no-op in effect: conftest auto-marks everything under /unit/).
pytestmark = pytest.mark.unit

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


@pytest.mark.asyncio
async def test_trigger_webhooks_isolates_a_failed_webhook(
    webhook_service, mock_db_session, sample_webhook
):
    """One webhook's failure must not take the other webhooks' deliveries down.

    The fanout wraps each deliver_webhook in its own SAVEPOINT: a webhook
    deleted between the fanout's SELECT and its delivery INSERT trips
    webhook_deliveries_webhook_id_fkey and, without the savepoint, poisons
    the shared session (PendingRollbackError) — rolling back every sibling
    delivery already flushed in the same transaction, including rows whose
    HTTP attempt had completed (CI run 40002172540: the F-250 golden leg's
    terminal FAILED row vanished this way and the history poll saw zero rows
    for 90s). The pin: the failing webhook is skipped with a warning, the
    loop continues, and the surviving webhooks' deliveries are returned.
    """
    # Arrange - two subscribed webhooks; the first one's delivery raises (the
    # FK failure a concurrent webhook deletion produces), the second succeeds.
    first = sample_webhook
    second = MagicMock(spec=OutboundWebhook)
    second.id = str(uuid4())
    second.name = "survivor"
    second.url = "http://127.0.0.1:1/hook"
    second.event_types = ["alert_fired"]
    second.enabled = True
    second.max_retries = 0
    second.retry_delay_seconds = 1

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [first, second]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    with patch.object(webhook_service, "deliver_webhook", new_callable=AsyncMock) as mock_deliver:
        mock_deliver.side_effect = [
            Exception(
                "(sqlalchemy.dialects.postgresql.asyncpg.ForeignKeyViolationError) insert or "
                'update on table "webhook_deliveries" violates foreign key constraint '
                '"webhook_deliveries_webhook_id_fkey"'
            ),
            WebhookDelivery(
                webhook_id=second.id,
                event_type="alert_fired",
                status=WebhookDeliveryStatus.PENDING,
                attempt_count=1,
            ),
        ]

        # Act
        deliveries = await webhook_service.trigger_webhooks_for_event(
            mock_db_session,
            WebhookEventType.ALERT_FIRED,
            {"alert_id": "test-123"},
            event_id="evt-123",
        )

    # Assert - the survivor's delivery came back; the failed webhook's slot
    # did not abort the fanout. Each delivery rode its own savepoint.
    assert len(deliveries) == 1
    assert deliveries[0].webhook_id == second.id
    assert mock_deliver.await_count == 2
    assert mock_db_session.begin_nested.call_count == 2


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

    with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
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

    with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
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

    with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
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

    with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
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

    with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
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

    with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
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

    with patch("backend.services.webhook_service.get_webhook_service", autospec=True) as mock_get:
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

    with patch("backend.services.webhook_service.get_webhook_service", autospec=True) as mock_get:
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


# =============================================================================
# WP4.4 kill battery (frozen triage feed the deleted archive's wp25-feed/wp44-triage/
# webhook_service.md, real-shape diffs in webhook-diffs.txt). Covers the
# health-summary query battery (#3/#14/#15), the format payload shapes
# (#5/#6/#7), the deliveries/list/get_delivery/delete lookup query builders
# (#2 members) — 153 of the feed's 158 extracted diffs; the other 5 are
# delete_webhook log-extra members dossier-classified EQUIVALENT (cluster
# 27). Root cause: mocks returned canned values and tests asserted the
# canned values flowed back — no statement was ever compiled, no payload
# was ever compared shape-for-shape. Zero production change.
# =============================================================================

_FIXED_NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)
_CUTOFF_SQL = "2026-09-21 12:00:00+00:00"  # _FIXED_NOW - 24h, literal-bound


def _sql(stmt: object) -> str:
    """Compile a captured statement with literal binds (crashes loudly on
    a mutated None statement — which is itself the kill)."""
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[union-attr]


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _scalars_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


@pytest.mark.asyncio
async def test_get_health_summary_sql_text_and_or_zero_defaults(
    webhook_service, mock_db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#3 health-queries + #15 or-default: every aggregate statement's SQL
    text is contractual (cutoff comparison, status equality, IS NOT NULL,
    enabled IS true) and zero counts must stay 0, not `or 1`."""
    monkeypatch.setattr(webhook_service_module, "utc_now", lambda: _FIXED_NOW)
    mock_db_session.execute = AsyncMock(
        side_effect=[
            _scalar_result(0),  # total webhooks
            _scalar_result(0),  # enabled webhooks
            _scalar_result(0),  # deliveries 24h
            _scalar_result(0),  # successful 24h
            _scalar_result(0),  # failed 24h
            _scalar_result(0.0),  # avg response time (falsy -> None)
        ]
    )
    with patch.object(webhook_service, "list_webhooks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        summary = await webhook_service.get_health_summary(mock_db_session)

    assert mock_db_session.execute.call_count == 6
    total_sql, enabled_sql, deliv_sql, succ_sql, fail_sql, avg_sql = [
        _sql(c.args[0]) for c in mock_db_session.execute.call_args_list
    ]
    assert total_sql.startswith("SELECT count(*)")
    assert "FROM outbound_webhooks" in total_sql
    assert " WHERE " not in total_sql.upper()
    assert "outbound_webhooks.enabled IS true" in enabled_sql
    for sql_text in (deliv_sql, succ_sql, fail_sql, avg_sql):
        assert sql_text.startswith(("SELECT count(*)", "SELECT avg"))
        assert "FROM webhook_deliveries" in sql_text
        assert f"webhook_deliveries.created_at >= '{_CUTOFF_SQL}'" in sql_text
    assert "status = 'success'" in succ_sql and "!=" not in succ_sql
    assert "status = 'failed'" in fail_sql and "!=" not in fail_sql
    assert "avg(webhook_deliveries.response_time_ms)" in avg_sql
    assert "response_time_ms IS NOT NULL" in avg_sql

    # zero-count path: `scalar() or 0` — `or 1` mutants surface as 1
    assert summary.total_webhooks == 0
    assert summary.enabled_webhooks == 0
    assert summary.total_deliveries_24h == 0
    assert summary.successful_deliveries_24h == 0
    assert summary.failed_deliveries_24h == 0
    # falsy-but-real avg (0.0): `if avg or True` mutants surface as 0.0
    assert summary.average_response_time_ms is None


@pytest.mark.asyncio
async def test_get_health_summary_threshold_boundaries(
    webhook_service, mock_db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#14 health-boundary: >0, >=0.9, <0.5 and the += 1 accumulators are
    pinned at the exact edges (.90 healthy, .50 neither, total==1 counted,
    two healthy counted as 2 not 1)."""
    monkeypatch.setattr(webhook_service_module, "utc_now", lambda: _FIXED_NOW)
    mock_db_session.execute = AsyncMock(
        side_effect=[_scalar_result(v) for v in (10, 8, 5, 4, 1, 250.5)]
    )
    webhooks = [
        MagicMock(total_deliveries=100, successful_deliveries=95),  # .95 healthy
        MagicMock(total_deliveries=100, successful_deliveries=90),  # .90 healthy (>= edge)
        MagicMock(total_deliveries=100, successful_deliveries=50),  # .50 neither (< edge)
        MagicMock(total_deliveries=100, successful_deliveries=45),  # .45 unhealthy
        MagicMock(total_deliveries=100, successful_deliveries=40),  # .40 unhealthy (count==2)
        MagicMock(total_deliveries=1, successful_deliveries=1),  # 1.0 healthy (total>0 edge)
        MagicMock(total_deliveries=0, successful_deliveries=0),  # skipped
    ]
    with patch.object(webhook_service, "list_webhooks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = webhooks
        summary = await webhook_service.get_health_summary(mock_db_session)

    assert summary.healthy_webhooks == 3
    assert summary.unhealthy_webhooks == 2
    assert summary.average_response_time_ms == 250.5
    # #3 member: list_webhooks must receive the session, not None
    assert mock_list.call_args.args[0] is mock_db_session


@pytest.mark.asyncio
async def test_list_webhooks_enabled_filter_and_order(webhook_service, mock_db_session) -> None:
    """#2 list members: enabled_only adds `enabled IS true` (not
    false/NULL/None), the no-filter path adds no WHERE, both order by
    created_at DESC."""
    mock_db_session.execute = AsyncMock(side_effect=[_scalars_result([]), _scalars_result([])])
    await webhook_service.list_webhooks(mock_db_session, enabled_only=True)
    await webhook_service.list_webhooks(mock_db_session, enabled_only=False)

    assert mock_db_session.execute.call_count == 2
    on_sql, off_sql = [_sql(c.args[0]) for c in mock_db_session.execute.call_args_list]
    assert on_sql.startswith("SELECT outbound_webhooks")
    assert "outbound_webhooks.enabled IS true" in on_sql
    assert " WHERE " not in off_sql.upper()
    for sql_text in (on_sql, off_sql):
        assert "ORDER BY outbound_webhooks.created_at DESC" in sql_text


@pytest.mark.asyncio
async def test_get_deliveries_count_and_page_queries(webhook_service, mock_db_session) -> None:
    """#2 get_deliveries members + #15 `or 1`: count and page statements
    keep the webhook_id equality, DESC order, real LIMIT/OFFSET, and a
    zero count stays zero."""
    wid = str(uuid4())
    wid_sql = wid.replace("-", "")  # UUID literal binds render dashless
    mock_db_session.execute = AsyncMock(side_effect=[_scalar_result(0), _scalars_result([])])
    deliveries, total = await webhook_service.get_deliveries(
        mock_db_session, wid, limit=50, offset=0
    )

    assert deliveries == []
    assert total == 0  # kills `scalar() or 1`
    count_sql, page_sql = [_sql(c.args[0]) for c in mock_db_session.execute.call_args_list]
    assert count_sql.startswith("SELECT count(*)")
    for sql_text in (count_sql, page_sql):
        assert "FROM webhook_deliveries" in sql_text
        assert f"webhook_deliveries.webhook_id = '{wid_sql}'" in sql_text
        assert "!=" not in sql_text
        assert "WHERE NULL" not in sql_text
    assert page_sql.startswith("SELECT webhook_deliveries")  # not select(None) -> SELECT NULL
    assert "ORDER BY webhook_deliveries.created_at DESC" in page_sql
    assert "LIMIT 50" in page_sql
    assert "OFFSET 0" in page_sql


@pytest.mark.asyncio
async def test_get_deliveries_defaults_survive_mutation(webhook_service, mock_db_session) -> None:
    """[B4.2] closes the #7339 test-gap survivors: get_deliveries
    ``limit: int = 50`` and ``offset: int = 0``. Every earlier get_deliveries
    test passes both kwargs explicitly, so a mutant flipping either default
    (50 -> 51, 0 -> 1) kept every test green. This call omits them, so the
    compiled page SQL carries the defaults verbatim only if they survive."""
    wid = str(uuid4())
    mock_db_session.execute = AsyncMock(side_effect=[_scalar_result(0), _scalars_result([])])
    deliveries, total = await webhook_service.get_deliveries(mock_db_session, wid)

    assert deliveries == []
    assert total == 0
    _count_sql, page_sql = [_sql(c.args[0]) for c in mock_db_session.execute.call_args_list]
    assert "LIMIT 50" in page_sql  # default limit, not 51
    assert "OFFSET 0" in page_sql  # default offset, not 1


@pytest.mark.asyncio
async def test_get_delivery_lookup_query(webhook_service, mock_db_session) -> None:
    """#2 get_delivery members: id equality survives to SQL."""
    did = str(uuid4())
    did_sql = did.replace("-", "")
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=result)

    assert await webhook_service.get_delivery(mock_db_session, did) is None
    sql_text = _sql(mock_db_session.execute.call_args.args[0])
    assert sql_text.startswith("SELECT webhook_deliveries")
    assert f"webhook_deliveries.id = '{did_sql}'" in sql_text
    assert "!=" not in sql_text
    assert "WHERE NULL" not in sql_text


@pytest.mark.asyncio
async def test_delete_webhook_lookup_uses_passed_id(webhook_service, mock_db_session) -> None:
    """#2 member `get_webhook(db, None)`: the pre-delete lookup must query
    the passed id (an IS NULL lookup deletes nothing / deletes wrongly)."""
    wid = str(uuid4())
    wid_sql = wid.replace("-", "")
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=result)

    assert await webhook_service.delete_webhook(mock_db_session, wid) is False
    sql_text = _sql(mock_db_session.execute.call_args.args[0])
    assert f"outbound_webhooks.id = '{wid_sql}'" in sql_text
    assert "IS NULL" not in sql_text


# ---------------------------------------------------------------------------
# Integration formatter payload-shape battery (#5 discord / #6 teams /
# #7 slack). Old tests were existence checks ("fields" in embeds); every
# mutation of a key, value, cap, or default survived. Exact equality below.
# ---------------------------------------------------------------------------


def test_format_slack_payload_exact_shape(webhook_service) -> None:
    payload = {
        "event_type": "alert_fired",
        "timestamp": "2026-09-22T12:00:00+00:00",
        "data": {"alpha": 1, "beta": "two", "gamma": None, "delta": ["x"]},
    }
    expected_text = "*alert_fired*\n- alpha: 1\n- beta: two\n"
    result = webhook_service._format_slack_payload(payload)
    assert result == {
        "text": expected_text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": expected_text}},
        ],
    }


def test_format_slack_payload_defaults_on_minimal_event(webhook_service) -> None:
    """With neither event_type nor data present the contract is the literal
    'event' fallback in the text and the {} data default (None/dropped
    defaults crash the .items() loop; renamed/case-flipped literals surface
    in the text)."""
    result = webhook_service._format_slack_payload({})
    assert result["text"] == "*event*\n"


def test_format_discord_payload_exact_shape(webhook_service) -> None:
    # 26 string fields: the embed fields list must cap at Discord's 25.
    data = {f"field_{i}": f"v{i}" for i in range(26)}
    payload = {"event_type": "alert_fired", "data": data, "timestamp": "TS-1"}
    expected_fields = [{"name": f"Field {i}", "value": f"v{i}", "inline": True} for i in range(25)]
    result = webhook_service._format_discord_payload(payload)
    assert result == {
        "embeds": [
            {"title": "Alert Fired", "timestamp": "TS-1", "fields": expected_fields},
        ],
    }


def test_format_discord_payload_defaults_on_minimal_event(webhook_service) -> None:
    result = webhook_service._format_discord_payload({})
    embed = result["embeds"][0]
    assert embed["title"] == "Event"
    assert embed["fields"] == []
    assert isinstance(embed["timestamp"], str) and embed["timestamp"]


def test_format_teams_payload_exact_shape(webhook_service) -> None:
    # 11 facts: the card facts list must cap at 10.
    data = {f"fact_{i}": i for i in range(11)}
    payload = {"event_type": "alert_fired", "data": data}
    expected_facts = [{"title": f"Fact {i}", "value": str(i)} for i in range(10)]
    result = webhook_service._format_teams_payload(payload)
    assert result == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "alert_fired",
        "themeColor": "0076D7",
        "title": "Alert Fired",
        "sections": [{"facts": expected_facts}],
    }


def test_format_teams_payload_defaults_on_minimal_event(webhook_service) -> None:
    result = webhook_service._format_teams_payload({})
    assert result == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "event",
        "themeColor": "0076D7",
        "title": "Event",
        "sections": [{"facts": []}],
    }


@pytest.mark.parametrize(
    "integration_type, title_marker",
    [("slack", "blocks"), ("discord", "embeds"), ("teams", "@type")],
)
def test_format_for_integration_routes_on_exact_type(
    webhook_service, integration_type: str, title_marker: str
) -> None:
    """#12 int-routing: the comparison targets 'slack'/'discord'/'teams'
    are contractual — a renamed target silently falls through to generic
    passthrough."""
    webhook = OutboundWebhook(
        id=str(uuid4()),
        name="Route Test",
        url="https://example.com/hook",
        event_types=["alert_fired"],
        integration_type=IntegrationType(integration_type),
        enabled=True,
        signing_secret="b" * 64,
        total_deliveries=0,
        successful_deliveries=0,
    )
    payload = {"event_type": "alert_fired", "data": {"k": "v"}}
    result = webhook_service._format_for_integration(webhook, payload)
    assert title_marker in result


def test_retired_r2a_row42_webhook_event_types_absent() -> None:
    """R2a row 42 (F-246): retired batch and enrichment webhook event types are absent."""
    from backend.models.outbound_webhook import WebhookEventType as ModelWebhookEventType

    schema_values = {e.value for e in WebhookEventType}
    model_values = {e.value for e in ModelWebhookEventType}
    for retired in (
        "event_enriched",
        "batch_analysis_started",
        "batch_analysis_completed",
        "batch_analysis_failed",
    ):
        assert retired not in schema_values
        assert retired not in model_values


# =============================================================================
# Consolidated from test_webhook_service_batch15.py (B4.2 step 2)
# =============================================================================

# (Battery docstring, preserved verbatim — it is evidence.)
# Batch-15 battery: webhook_service TEST-GAP clusters from the WP4.4 dossier
# (the deleted archive's ``wp25-feed/wp44-triage/webhook_service.md``).
#
# Clusters killed here (mutmut-adjacent behaviour pinned per cluster):
# C1 bted-values (87), C5 fmt-discord (30), C6 fmt-teams (29), C7 fmt-slack (18),
# C12 int-routing (6), C13 boundary300 (6), C15 or-default (6), C19 singleton (2),
# C20 bted-fallback (2), C21 timing-formula (2), C22 tw-body (3), C23 hdrs-names (3).
#
# Deliberately NOT touched (owned by other batches): C2/C3 query-build SQL,
# C4 delivery-record construction, C8 stats counters, C9 signature recomputation,
# C10 resp-fields, C11 create-fields, C14 health-boundary, C16 jinja-context,
# C17 db-args, C18 post-args.
#
# EVERY asserted literal below was MEASURED against the pristine shipped source on
# 2026-09-23 by throwaway probes (``/tmp/b15-probe-*.py`` run with
# ``uv run python`` under the repo venv, consolidated dump in
# ``/tmp/b15-probes.json``). No value was guessed and production was NOT bent to
# any mutant: where shipped behaviour differs from the dossier draft, the shipped
# behaviour is what is pinned. Measured corrections / additions to the dossier:
#
# * Dossier D1 claims ``_build_test_event_data`` returns a ``data``-less shape and
#   that ``timestamp`` ordering is meaningful; the shipped shape is
#   ``{**base, **specific}`` where ``base == {"test": True, "timestamp": <iso>}``
#   (probe1/probe6): the full dict is pinned with a patched clock.
# * ``WebhookDeliveryStatus`` is ``auto()`` so its values are the *lowercase*
#   member names (``"success"``, ``"retrying"``, ``"failed"``) — probe4.
# * C13 boundary: 299 -> SUCCESS in all three classifiers; 300 is FAILURE with a
#   *different* failure shape per entry point — ``deliver_webhook`` -> status
#   ``retrying`` + ``next_retry_at`` set + ``delivered_at`` None, ``test_webhook``
#   -> ``success=False, error_message="HTTP 300", response_body="b300"`` (body is
#   still returned on failure), ``retry_delivery`` -> status ``failed`` +
#   ``delivered_at`` None + ``next_retry_at`` None (probe4).
# * C19: the shipped reset pattern is the module-level holder global
#   ``webhook_service._WebhookServiceHolder.instance`` (there is NO
#   ``reset_webhook_service()`` helper); it is saved/restored in ``finally`` so no
#   module state leaks to other tests (probe6).
# * C21: both ``/1000`` and ``*1001`` are killed by pinning the exact int returned
#   from ``_send_request`` with the service module's ``datetime`` patched to a
#   2-tick clock (37 ms -> 37; ``/1000`` would yield 0, ``*1001`` 37037);
#   ``int()`` also truncates sub-millisecond elapsed to 0 (probe7).
# * C23: the shipped base headers are exactly ``{"Content-Type":
#   "application/json", "User-Agent": "NemotronWebhook/1.0"}`` and the
#   ``post()`` kwargs are exactly ``("json", "headers")`` with the url positional;
#   header VALUES (not just the key set) are pinned because the shipped
#   ``_send_request`` merges custom headers over the base — a value tweak
#   survives a keys-only assert (probe3/probe7).
# * Unmeasured-by-us but recorded because it is shipped contract: the three
#   formatters raise ``AttributeError`` when ``data`` is present-but-``None``
#   (``payload.get("data", {})`` only defaults a *missing* key) — probe2.
#
# Provable-EQUIVALENT members found inside the targeted clusters (kill-work in
# this file cannot reach them; ledger candidates): dropping ``| bool`` from the
# formatters' ``isinstance(value, str | int | float | bool)`` (bool is a subclass
# of int, so the union is unchanged — verified on the mutated module) and the
# Discord-only ``payload.get("event_type", "event")`` default case flip (that
# default reaches ``.title()`` only, so ``"EVENT"`` renders identically).

# ---------------------------------------------------------------------------
# Measured constants (probes 6/7). FIXED/FIXED_ISO come from patching the
# service module's utc_now, so every iso timestamp in this file is the same
# measured value.
# ---------------------------------------------------------------------------
WID = "wid-fixed-1"
URL = "https://x.test/hook"
FIXED = datetime(2026, 3, 4, 5, 6, 7, 891011, tzinfo=UTC)
FIXED_ISO = "2026-03-04T05:06:07.891011+00:00"
SECRET = "ab" * 32  # nosemgrep: hardcoded-password
SECRET_A = "a" * 64
# probe7: HMAC over json.dumps(payload, sort_keys=True, separators=(",",":"))
SIG_P1 = (
    "4012d12033f6bfe41db94b44a97ac0b5434779648ccd370c53ff31d117a6aa4f"  # pragma: allowlist secret
)
SIG_P3 = (
    "31f13e5e1b6da4560d8cca7ec6a477f41b1eb3724711410670f3685c699aec72"  # pragma: allowlist secret
)
BASE_HEADERS = {"Content-Type": "application/json", "User-Agent": "NemotronWebhook/1.0"}

# Payloads whose signatures above were measured with SECRET (probe6/probe7).
P1 = {"zz": 1, "aa": {"y": 2, "b": 3}}
P3 = {"b": [1, 2], "a": "x"}

# A wide data mapping mixing scalar and non-scalar values; the non-scalars must
# be dropped by all three formatters (measured, probe2).
WIDE_DATA = {
    "zone_id": "driveway",
    "score": 0.5,
    "count": 3,
    "flag": False,
    "nested": {"x": 1},
    "items": [1, 2],
    "none": None,
}


# ---------------------------------------------------------------------------
# Local fixtures (self-contained; mock_db_session comes from backend/tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def service() -> WebhookService:
    return WebhookService()


@pytest.fixture(autouse=True)
def _no_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """F12 send-time validation resolves the URL's hostname, and this sandbox
    resolves none of the test hosts — stub ``resolve_hostname`` where the send
    path reads it (backend.core.url_validation; the same seam the channel
    adapters' _no_dns fixture uses). A public IP keeps every shipped URL
    policy-valid under the default flag."""
    import backend.core.url_validation as uv

    monkeypatch.setattr(uv, "resolve_hostname", lambda host: ["93.184.216.34"])  # noqa: ARG005


@pytest.fixture
def clock():
    """Patch the service module's utc_now to the measured FIXED instant."""
    with patch.object(W, "utc_now", return_value=FIXED, autospec=True):
        yield FIXED


def webhook(integration: IntegrationType = IntegrationType.GENERIC, **overrides) -> OutboundWebhook:
    """Build an unpersisted OutboundWebhook with the probe's baseline config."""
    kwargs = {
        "id": WID,
        "name": "Batch15",
        "url": URL,
        "event_types": ["alert_fired"],
        "integration_type": integration,
        "enabled": True,
        "auth_config": None,
        "custom_headers": {},
        "payload_template": None,
        "max_retries": 4,
        "retry_delay_seconds": 10,
        "signing_secret": None,
        "total_deliveries": 0,
        "successful_deliveries": 0,
    }
    kwargs.update(overrides)
    return OutboundWebhook(**kwargs)


class _AnyPinnedTransport:
    """Equality matcher for the F12 pinning transport instance.

    ``pinned_httpx_client`` wraps a real ``_PinnedResolver``; the test only
    needs to know the client received ONE — the resolver's behaviour is
    pinned by its own tests (test_url_validation)."""

    def __eq__(self, other: object) -> bool:
        from backend.core.url_validation import _PinnedResolver

        return isinstance(other, _PinnedResolver)

    __hash__ = None  # identity-free equality: hashability is irrelevant here

    def __repr__(self) -> str:  # pragma: no cover - assertion output only
        return "<any pinned transport>"


ANY_TRANSPORT = _AnyPinnedTransport()


class ClientSpy:
    """Stand-in for ``httpx.AsyncClient`` that records the ``post()`` call.

    Instances are callable and return themselves from ``__call__`` so the
    ``async with httpx.AsyncClient(timeout=...) as client`` form works, and no
    real socket is ever opened.
    """

    def __init__(self, status_code: int = 202, text: str = "queued") -> None:
        self.status_code = status_code
        self.text = text
        self.calls: list[tuple[tuple, dict]] = []
        self.constructor_kwargs: list[dict] = []

    def __call__(self, **kwargs) -> ClientSpy:
        self.constructor_kwargs.append(kwargs)
        return self

    async def __aenter__(self) -> ClientSpy:
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    async def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        response = MagicMock()
        response.status_code = self.status_code
        response.text = self.text
        return response


def _session_with(execute: AsyncMock) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = execute
    return session


def _result(scalar=None, rows=None, one_or_none=None) -> MagicMock:
    result = MagicMock()
    result.scalar.return_value = scalar
    scalars = MagicMock()
    scalars.all.return_value = rows if rows is not None else []
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = one_or_none
    return result


def _patched_clock(steps: list[datetime]) -> type:
    """A ``datetime`` look-alike whose ``now()`` walks ``steps`` once."""

    class TickClock:
        _steps = steps
        _tick = 0

        @classmethod
        def now(cls, _tz=None):
            value = cls._steps[min(cls._tick, len(cls._steps) - 1)]
            cls._tick += 1
            return value

    return TickClock


# ===========================================================================
# C1 bted-values (87) — full-shape equality of the sample-event table
# ===========================================================================
def test_build_test_event_data_full_shape_per_event_type(service, clock):
    """Kills every key/value text mutation (XX…XX, UPPER/lower flips, 1.95/1.87)
    in the event-specific test-data table: the whole merged dict is pinned."""
    measured = {
        WebhookEventType.ALERT_FIRED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "alert_id": "test-alert-001",
            "severity": "high",
            "camera_id": "front_door",
            "description": "Test alert triggered",
        },
        WebhookEventType.ALERT_DISMISSED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "alert_id": "test-alert-001",
        },
        WebhookEventType.ALERT_ACKNOWLEDGED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "alert_id": "test-alert-001",
        },
        WebhookEventType.EVENT_CREATED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "event_id": "test-event-001",
            "camera_id": "front_door",
            "event_type": "motion_detected",
        },
        WebhookEventType.ENTITY_DISCOVERED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "entity_id": "test-entity-001",
            "entity_type": "person",
            "label": "Unknown Person",
        },
        WebhookEventType.ANOMALY_DETECTED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "anomaly_id": "test-anomaly-001",
            "zone_id": "driveway",
            "anomaly_type": "unusual_activity",
            "score": 0.87,
        },
        WebhookEventType.SYSTEM_HEALTH_CHANGED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "component": "ai-yolo26",
            "status": "degraded",
            "message": "High latency detected",
        },
    }
    for event_type, expected in measured.items():
        assert service._build_test_event_data(event_type) == expected
        # insertion order is part of the shipped shape: base first, then specific
        assert list(service._build_test_event_data(event_type)) == list(expected)

    # float literals are floats, not strings / rounded ints
    assert service._build_test_event_data(WebhookEventType.ANOMALY_DETECTED)["score"] == 0.87
    assert type(service._build_test_event_data(WebhookEventType.ANOMALY_DETECTED)["score"]) is float


def test_build_test_event_data_timestamp_is_utc_iso_and_advances(service):
    """Timestamp shape without the clock patch: 32-char ``+00:00`` isoformat."""
    data = service._build_test_event_data(WebhookEventType.ALERT_FIRED)
    stamp = data["timestamp"]
    assert isinstance(stamp, str)
    assert stamp.endswith("+00:00")
    assert len(stamp) == 32
    assert datetime.fromisoformat(stamp).tzinfo == UTC
    later = service._build_test_event_data(WebhookEventType.ALERT_FIRED)["timestamp"]
    assert later >= stamp


# ===========================================================================
# C20 bted-fallback (2) — unmapped event types merge {} (no None, no raise)
# ===========================================================================
def test_build_test_event_data_unmapped_event_type_merges_empty_dict(service, clock):
    """Kills ``.get(value, {})`` -> ``.get(value)`` / dropped default: an enum
    member absent from the table must merge an empty dict, never None."""
    unmapped = [
        "unmapped_event",
    ]
    for event_type in unmapped:
        data = service._build_test_event_data(event_type)
        assert data == {"test": True, "timestamp": FIXED_ISO}
        assert data["test"] is True

    # shipped: the lookup keys are the lowercase StrEnum values
    assert service._build_test_event_data(WebhookEventType.ALERT_FIRED) != {
        "test": True,
        "timestamp": FIXED_ISO,
    }


# ===========================================================================
# C7 fmt-slack (18) — full shape, key case, inline flags, text assembly
# ===========================================================================
def test_format_slack_payload_full_shape(service):
    payload = {"event_type": "camera_motion_detected", "data": WIDE_DATA}
    text = (
        "*camera_motion_detected*\n- zone_id: driveway\n- score: 0.5\n- count: 3\n- flag: False\n"
    )
    assert service._format_slack_payload(payload) == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }


def test_format_slack_payload_defaults_and_non_scalar_filter(service):
    assert service._format_slack_payload({}) == {
        "text": "*event*\n",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "*event*\n"}}],
    }
    assert service._format_slack_payload({"event_type": "e"}) == {
        "text": "*e*\n",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "*e*\n"}}],
    }
    # keys are used verbatim (no title-casing) and non-scalars are skipped
    odd = {
        "event_type": "a_B_c",
        "data": {"HTTP_code_x2": "v", "UPPER_CASE": 1, "mix ed": 2, "": 3},
    }
    text = "*a_B_c*\n- HTTP_code_x2: v\n- UPPER_CASE: 1\n- mix ed: 2\n- : 3\n"
    assert service._format_slack_payload(odd) == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }


# ===========================================================================
# C5 fmt-discord (30) — embed shape, inline flag, title-casing, [:25] cap
# ===========================================================================
def test_format_discord_payload_full_shape(service):
    payload = {"event_type": "camera_motion_detected", "timestamp": "TS-STAMP", "data": WIDE_DATA}
    assert service._format_discord_payload(payload) == {
        "embeds": [
            {
                "title": "Camera Motion Detected",
                "timestamp": "TS-STAMP",
                "fields": [
                    {"name": "Zone Id", "value": "driveway", "inline": True},
                    {"name": "Score", "value": "0.5", "inline": True},
                    {"name": "Count", "value": "3", "inline": True},
                    {"name": "Flag", "value": "False", "inline": True},
                ],
            }
        ]
    }


def test_format_discord_payload_timestamp_lookup_and_defaults(service):
    # missing timestamp falls back to the module clock (utc_now is module-global)
    with patch.object(W, "utc_now", return_value=FIXED, autospec=True):
        assert service._format_discord_payload({"event_type": "e", "data": {}}) == {
            "embeds": [{"title": "E", "timestamp": FIXED_ISO, "fields": []}]
        }
        assert service._format_discord_payload({}) == {
            "embeds": [{"title": "Event", "timestamp": FIXED_ISO, "fields": []}]
        }
    # explicit timestamp wins
    assert service._format_discord_payload({"timestamp": "T2", "data": {"alert_id": "a-1"}}) == {
        "embeds": [
            {
                "title": "Event",
                "timestamp": "T2",
                "fields": [{"name": "Alert Id", "value": "a-1", "inline": True}],
            }
        ]
    }


def test_format_discord_fields_cap_at_25(service):
    """Boundary pin: 26 inputs -> 25 fields (kills ``fields[:25]`` -> ``[:26]``)."""
    data = {f"k{i}": i for i in range(26)}
    fields = service._format_discord_payload({"data": data})["embeds"][0]["fields"]
    assert len(fields) == 25
    assert fields[0] == {"name": "K0", "value": "0", "inline": True}
    assert fields[-1] == {"name": "K24", "value": "24", "inline": True}
    assert [f["name"] for f in fields][-3:] == ["K22", "K23", "K24"]
    # 25 inputs is the largest uncapped case; 24 stays 24
    assert (
        len(
            service._format_discord_payload({"data": {f"k{i}": i for i in range(25)}})["embeds"][0][
                "fields"
            ]
        )
        == 25
    )
    assert (
        len(
            service._format_discord_payload({"data": {f"k{i}": i for i in range(24)}})["embeds"][0][
                "fields"
            ]
        )
        == 24
    )
    empty = service._format_discord_payload({"data": {}})["embeds"][0]
    assert empty["title"] == "Event" and empty["fields"] == []


# ===========================================================================
# C6 fmt-teams (29) — MessageCard shape, themeColor, summary, [:10] cap
# ===========================================================================
def test_format_teams_payload_full_shape(service):
    payload = {"event_type": "camera_motion_detected", "timestamp": "TS-STAMP", "data": WIDE_DATA}
    assert service._format_teams_payload(payload) == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "camera_motion_detected",
        "themeColor": "0076D7",
        "title": "Camera Motion Detected",
        "sections": [
            {
                "facts": [
                    {"title": "Zone Id", "value": "driveway"},
                    {"title": "Score", "value": "0.5"},
                    {"title": "Count", "value": "3"},
                    {"title": "Flag", "value": "False"},
                ]
            }
        ],
    }
    # fact dicts carry exactly two keys — no inline flag (unlike Discord)
    assert list(service._format_teams_payload(payload)["sections"][0]["facts"][0]) == [
        "title",
        "value",
    ]
    # top-level key order is part of the shipped shape
    assert list(service._format_teams_payload(payload)) == [
        "@type",
        "@context",
        "summary",
        "themeColor",
        "title",
        "sections",
    ]


def test_format_teams_summary_is_raw_event_type_and_defaults(service):
    """``summary`` keeps the raw value while ``title`` is title-cased."""
    assert service._format_teams_payload({}) == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "event",
        "themeColor": "0076D7",
        "title": "Event",
        "sections": [{"facts": []}],
    }
    slim = service._format_teams_payload(
        {"event_type": "a_B_c", "data": {"HTTP_code_x2": "v", "": 3}}
    )
    assert slim["summary"] == "a_B_c"
    assert slim["title"] == "A B C"
    assert slim["sections"][0]["facts"] == [
        {"title": "Http Code X2", "value": "v"},
        {"title": "", "value": "3"},
    ]


def test_format_teams_facts_cap_at_10(service):
    """Boundary pin: 11 inputs -> 10 facts (kills ``facts[:10]`` -> ``[:11]``)."""
    facts = service._format_teams_payload({"data": {f"k{i}": i for i in range(11)}})["sections"][0][
        "facts"
    ]
    assert len(facts) == 10
    assert facts[0] == {"title": "K0", "value": "0"}
    assert facts[-1] == {"title": "K9", "value": "9"}
    assert (
        len(
            service._format_teams_payload({"data": {f"k{i}": i for i in range(10)}})["sections"][0][
                "facts"
            ]
        )
        == 10
    )
    assert (
        len(
            service._format_teams_payload({"data": {f"k{i}": i for i in range(9)}})["sections"][0][
                "facts"
            ]
        )
        == 9
    )
    assert service._format_teams_payload({"data": {}})["sections"] == [{"facts": []}]


# ===========================================================================
# C12 int-routing (6) — _format_for_integration comparison targets
# ===========================================================================
def test_format_for_integration_routes_each_type_with_full_shape(service, clock):
    """Kills ``"slack"/"discord"/"teams"`` comparison-target renames: each route
    must produce its formatted shape; anything else is verbatim passthrough."""
    standard = {
        "event_type": "camera_motion",
        "timestamp": "TS",
        "data": {"zone_id": "driveway", "score": 0.5},
    }

    slack = service._format_for_integration(webhook(IntegrationType.SLACK), {**standard})
    text = "*camera_motion*\n- zone_id: driveway\n- score: 0.5\n"
    assert slack == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }

    discord = service._format_for_integration(webhook(IntegrationType.DISCORD), {**standard})
    assert discord == {
        "embeds": [
            {
                "title": "Camera Motion",
                "timestamp": "TS",
                "fields": [
                    {"name": "Zone Id", "value": "driveway", "inline": True},
                    {"name": "Score", "value": "0.5", "inline": True},
                ],
            }
        ]
    }

    teams = service._format_for_integration(webhook(IntegrationType.TEAMS), {**standard})
    assert teams == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "camera_motion",
        "themeColor": "0076D7",
        "title": "Camera Motion",
        "sections": [
            {
                "facts": [
                    {"title": "Zone Id", "value": "driveway"},
                    {"title": "Score", "value": "0.5"},
                ]
            }
        ],
    }

    generic = webhook(IntegrationType.GENERIC)
    assert service._format_for_integration(generic, standard) == standard
    assert service._format_for_integration(generic, standard) is standard
    # TELEGRAM is not a formatting branch -> passthrough
    assert service._format_for_integration(webhook(IntegrationType.TELEGRAM), standard) == standard
    # a bare (non-enum) integration_type string still routes when it matches
    plain = webhook(IntegrationType.GENERIC)
    plain.integration_type = "discord"
    assert service._format_for_integration(plain, {**standard}) == discord
    # ...and does NOT route when case differs (shipped behaviour, not lenient)
    plain.integration_type = "SLACK"
    assert service._format_for_integration(plain, standard) == standard


def test_build_payload_routes_through_integration(service, clock):
    """_build_payload (no template) ends in the integration formatter."""
    event_data = {"alert_id": "a1"}
    assert service._build_payload(webhook(), WebhookEventType.ALERT_FIRED, event_data) == {
        "event_type": "alert_fired",
        "timestamp": FIXED_ISO,
        "webhook_id": WID,
        "data": event_data,
    }
    text = "*alert_fired*\n- a: 1\n"
    assert service._build_payload(
        webhook(IntegrationType.SLACK), WebhookEventType.ALERT_FIRED, {"a": 1}
    ) == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }
    assert service._build_payload(
        webhook(IntegrationType.TEAMS), WebhookEventType.ALERT_FIRED, {"a": 1}
    ) == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "alert_fired",
        "themeColor": "0076D7",
        "title": "Alert Fired",
        "sections": [{"facts": [{"title": "A", "value": "1"}]}],
    }


# ===========================================================================
# C13 boundary300 (6) — 200 <= status < 300 in deliver / test / retry
# ===========================================================================
@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [
        (199, WebhookDeliveryStatus.RETRYING),
        (200, WebhookDeliveryStatus.SUCCESS),
        (204, WebhookDeliveryStatus.SUCCESS),
        (299, WebhookDeliveryStatus.SUCCESS),
        (300, WebhookDeliveryStatus.RETRYING),
        (301, WebhookDeliveryStatus.RETRYING),
        (500, WebhookDeliveryStatus.RETRYING),
    ],
)
async def test_deliver_webhook_status_classification_at_300_boundary(
    service, mock_db_session, status_code, expected_status
):
    """Kills ``< 300`` -> ``<= 300`` / ``< 301``: 299 succeeds, 300 does not."""
    mock_db_session.execute = AsyncMock(return_value=_result())
    hook = webhook(max_retries=4, retry_delay_seconds=10)

    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (status_code, f"body-{status_code}", 42)
        delivery = await service.deliver_webhook(
            mock_db_session,
            hook,
            WebhookEventType.ALERT_FIRED,
            {"alert_id": "a1"},
            event_id="evt-9",
        )

    assert delivery.status is expected_status
    assert delivery.status_code == status_code
    assert delivery.response_body == f"body-{status_code}"
    assert delivery.response_time_ms == 42
    if expected_status is WebhookDeliveryStatus.SUCCESS:
        assert delivery.error_message is None
        assert delivery.delivered_at is not None
        assert hook.last_delivery_status == "success"
    else:
        assert delivery.error_message == f"HTTP {status_code}"
        assert delivery.delivered_at is None
        assert delivery.next_retry_at is not None
        assert hook.last_delivery_status == "retrying"


@pytest.mark.parametrize("status_code", [300, 301, 404])
async def test_deliver_webhook_300_is_failure_with_measured_field_proof(
    service, mock_db_session, status_code
):
    """The delivery-record fields that *prove* 300 is not a success."""
    mock_db_session.execute = AsyncMock(return_value=_result())
    hook = webhook()
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (status_code, "b", 5)
        delivery = await service.deliver_webhook(
            mock_db_session, hook, WebhookEventType.ALERT_FIRED, {}
        )

    assert delivery.status is WebhookDeliveryStatus.RETRYING
    assert delivery.status == "retrying"  # auto()-based StrEnum value is lowercase
    assert delivery.error_message == f"HTTP {status_code}"
    assert delivery.delivered_at is None
    assert hook.total_deliveries == 1
    assert hook.successful_deliveries == 0


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (
            299,
            "b299",
            {
                "success": True,
                "status_code": 299,
                "response_time_ms": 7,
                "response_body": "b299",
                "error_message": None,
            },
        ),
        (
            300,
            "b300",
            {
                "success": False,
                "status_code": 300,
                "response_time_ms": 7,
                "response_body": "b300",
                "error_message": "HTTP 300",
            },
        ),
        (
            301,
            "b301",
            {
                "success": False,
                "status_code": 301,
                "response_time_ms": 7,
                "response_body": "b301",
                "error_message": "HTTP 301",
            },
        ),
    ],
)
async def test_test_webhook_success_boundary_at_300(
    service, mock_db_session, status_code, body, expected
):
    """test_webhook classification: 299 success / 300 failure, full response."""
    hook = webhook()
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (status_code, body, 7)
        result = await service.test_webhook(mock_db_session, hook.id, WebhookEventType.ALERT_FIRED)
    assert result.model_dump() == expected


async def test_retry_delivery_300_is_failed_299_is_success(service, mock_db_session):
    """retry_delivery uses the same window but the FAILED branch (not RETRYING)."""
    hook = webhook()
    delivery = WebhookDelivery(
        webhook_id=hook.id,
        event_type="alert_fired",
        status=WebhookDeliveryStatus.FAILED,
        attempt_count=1,
        request_payload={"a": 1},
    )
    mock_db_session.execute = AsyncMock(
        side_effect=[_result(one_or_none=delivery), _result(one_or_none=hook)]
    )
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (299, "r299", 11)
        retried = await service.retry_delivery(mock_db_session, "delivery-1")

    assert retried.status is WebhookDeliveryStatus.SUCCESS
    assert retried.status_code == 299
    assert retried.response_body == "r299"
    assert retried.response_time_ms == 11
    assert retried.error_message is None
    assert retried.attempt_count == 2
    assert hook.last_delivery_status == "success"

    hook2 = webhook()
    delivery2 = WebhookDelivery(
        webhook_id=hook2.id,
        event_type="alert_fired",
        status=WebhookDeliveryStatus.FAILED,
        attempt_count=1,
        request_payload={"a": 1},
    )
    mock_db_session.execute = AsyncMock(
        side_effect=[_result(one_or_none=delivery2), _result(one_or_none=hook2)]
    )
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (300, "r300", 11)
        failed = await service.retry_delivery(mock_db_session, "delivery-1")

    assert failed.status is WebhookDeliveryStatus.FAILED
    assert failed.status_code == 300
    assert failed.error_message == "HTTP 300"
    assert failed.response_body == "r300"
    assert failed.attempt_count == 2
    assert hook2.total_deliveries == 1
    assert hook2.successful_deliveries == 0
    assert hook2.last_delivery_status == "failed"


# ===========================================================================
# C22 tw-body (3) — test_webhook response_body passthrough / None / cap
# ===========================================================================
@pytest.mark.parametrize(
    ("status_code", "body", "expected_body"),
    [
        (200, "pong", "pong"),
        (200, "", None),
        (404, "", None),
        (404, "nope", "nope"),
    ],
)
async def test_test_webhook_response_body_passthrough(
    service, mock_db_session, status_code, body, expected_body
):
    hook = webhook()
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (status_code, body, 7)
        result = await service.test_webhook(mock_db_session, hook.id, WebhookEventType.ALERT_FIRED)
    assert result.response_body == expected_body
    assert result.model_dump()["response_body"] == expected_body


async def test_test_webhook_response_body_capped_at_2000(service, mock_db_session):
    hook = webhook()
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (200, "x" * 2001, 7)
        result = await service.test_webhook(mock_db_session, hook.id, WebhookEventType.ALERT_FIRED)
    assert len(result.response_body) == 2000
    assert result.response_body == "x" * 2000
    assert result.success is True and result.error_message is None


async def test_test_webhook_full_success_shape(service, mock_db_session):
    hook = webhook()
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (200, "pong", 7)
        result = await service.test_webhook(mock_db_session, hook.id, WebhookEventType.ALERT_FIRED)
    assert result.model_dump() == {
        "success": True,
        "status_code": 200,
        "response_time_ms": 7,
        "response_body": "pong",
        "error_message": None,
    }


# ===========================================================================
# C23 hdrs-names (3) + C21 timing-formula (2) — _send_request wire contract
# ===========================================================================
async def test_send_request_posts_exact_url_json_and_base_headers(service):
    """Header dict is pinned by keys AND values: the shipped base headers are
    exactly Content-Type/User-Agent and post() gets (url, json=, headers=)."""
    spy = ClientSpy(status_code=202, text="queued")
    with (
        patch.object(httpx, "AsyncClient", spy),
        patch.object(uv, "resolve_hostname", lambda host: ["93.184.216.34"]),  # noqa: ARG005
        patch.object(uv.httpx, "AsyncHTTPTransport", lambda *a, **k: object()),  # noqa: ARG005
    ):
        result = await service._send_request(webhook(), P1)

    # The URL is a hostname, so the F12 send path builds the PINNED client:
    # timeout from the module constant plus the pinning transport wrapper.
    assert spy.constructor_kwargs == [{"timeout": DEFAULT_TIMEOUT, "transport": ANY_TRANSPORT}]
    assert spy.calls == [((URL,), {"json": P1, "headers": BASE_HEADERS})]
    assert result == (202, "queued", 0)


async def test_send_request_signed_headers_exact_dict(service):
    """Kills header key renames for the signature pair (values are the measured
    HMAC over the canonical json.dumps form)."""
    spy = ClientSpy(status_code=200, text="OK")
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(webhook(signing_secret=SECRET), P1)

    _, kwargs = spy.calls[0]
    assert kwargs["headers"] == {
        "Content-Type": "application/json",
        "User-Agent": "NemotronWebhook/1.0",
        "X-Webhook-Signature": f"sha256={SIG_P1}",
        "X-Webhook-Signature-256": SIG_P1,
    }
    assert list(kwargs["headers"]) == [
        "Content-Type",
        "User-Agent",
        "X-Webhook-Signature",
        "X-Webhook-Signature-256",
    ]
    # the measured literal equals an in-test recomputation of the shipped
    # canonicalization (sort_keys + tight separators)
    canonical = json.dumps(P1, sort_keys=True, separators=(",", ":")).encode()
    assert hmac.new(bytes.fromhex(SECRET), canonical, hashlib.sha256).hexdigest() == SIG_P1


async def test_send_request_auth_and_custom_header_dicts_are_exact(service):
    bearer = webhook(
        custom_headers={"X-Trace": "t1"},
        auth_config={"type": "bearer", "token": "TK1"},
        signing_secret=SECRET,
    )
    spy = ClientSpy()
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(bearer, P3)
    _, kwargs = spy.calls[0]
    assert kwargs["headers"] == {
        "Content-Type": "application/json",
        "User-Agent": "NemotronWebhook/1.0",
        "X-Trace": "t1",
        "Authorization": "Bearer TK1",
        "X-Webhook-Signature": f"sha256={SIG_P3}",
        "X-Webhook-Signature-256": SIG_P3,
    }
    assert list(kwargs["headers"]) == [
        "Content-Type",
        "User-Agent",
        "X-Trace",
        "Authorization",
        "X-Webhook-Signature",
        "X-Webhook-Signature-256",
    ]

    basic = webhook(auth_config={"type": "basic", "username": "cam", "password": "pw"})
    spy = ClientSpy()
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(basic, P1)
    assert spy.calls[0][1]["headers"] == {
        "Authorization": "Basic Y2FtOnB3",
        **BASE_HEADERS,
    }

    header_auth = webhook(
        auth_config={"type": "header", "header_name": "X-Api-Key", "header_value": "VV"}
    )
    spy = ClientSpy()
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(header_auth, P1)
    assert spy.calls[0][1]["headers"] == {"X-Api-Key": "VV", **BASE_HEADERS}

    # unknown auth type and empty auth_config add nothing
    for auth_config in ({"type": "weird"}, {}):
        spy = ClientSpy()
        with patch.object(httpx, "AsyncClient", spy):
            await service._send_request(webhook(auth_config=auth_config), P1)
        assert spy.calls[0][1]["headers"] == BASE_HEADERS

    # custom headers are merged OVER the base (later update wins)
    override = webhook(
        custom_headers={"Content-Type": "text/plain", "User-Agent": "mine", "X-Extra": "e"}
    )
    spy = ClientSpy()
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(override, P3)
    assert spy.calls[0][1]["headers"] == {
        "Content-Type": "text/plain",
        "User-Agent": "mine",
        "X-Extra": "e",
    }


@pytest.mark.parametrize(
    ("elapsed_ms", "expected_ms"),
    [(0, 0), (1, 1), (37, 37), (2500, 2500), (100000, 100000)],
)
async def test_send_request_response_time_ms_formula_is_times_1000(
    service, elapsed_ms, expected_ms
):
    """Kills ``* 1000`` -> ``/ 1000`` (37 -> 0) and ``* 1001`` (37 -> 37037) with
    a two-tick clock injected into the service module's ``datetime``."""
    steps = [
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=elapsed_ms),
    ]
    spy = ClientSpy(status_code=200, text="pong")
    with (
        patch.object(httpx, "AsyncClient", spy),
        patch.object(W, "datetime", _patched_clock(steps)),
    ):
        status, text, response_time_ms = await service._send_request(webhook(), P1)
    assert (status, text) == (200, "pong")
    assert response_time_ms == expected_ms
    assert type(response_time_ms) is int


async def test_send_request_sub_millisecond_elapsed_truncates_to_zero(service):
    """``int()`` truncation is measurable: 999us -> 0, 1999us -> 1."""
    steps = [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 0, 0, 0, 999, tzinfo=UTC)]
    spy = ClientSpy()
    with (
        patch.object(httpx, "AsyncClient", spy),
        patch.object(W, "datetime", _patched_clock(steps)),
    ):
        assert (await service._send_request(webhook(), P1))[2] == 0
    steps = [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 0, 0, 0, 1999, tzinfo=UTC)]
    spy = ClientSpy()
    with (
        patch.object(httpx, "AsyncClient", spy),
        patch.object(W, "datetime", _patched_clock(steps)),
    ):
        assert (await service._send_request(webhook(), P1))[2] == 1


# ===========================================================================
# C15 or-default (6) — ``scalar() or 0`` fallbacks
# ===========================================================================
async def test_health_summary_zero_and_none_scalars_fall_back_to_zero(service, mock_db_session):
    """Kills ``or 0`` -> ``or 1`` on all five count scalars: None and 0 both
    produce 0, and average_response_time_ms is None for None *and* 0.0."""
    for values in ([None] * 6, [0, 0, 0, 0, 0, 0]):
        mock_db_session.execute = AsyncMock(side_effect=[_result(scalar=v) for v in values])
        with patch.object(service, "list_webhooks", new_callable=AsyncMock) as lister:
            lister.return_value = []
            summary = await service.get_health_summary(mock_db_session)
        assert summary.model_dump() == {
            "total_webhooks": 0,
            "enabled_webhooks": 0,
            "healthy_webhooks": 0,
            "unhealthy_webhooks": 0,
            "total_deliveries_24h": 0,
            "successful_deliveries_24h": 0,
            "failed_deliveries_24h": 0,
            "average_response_time_ms": None,
        }
        assert mock_db_session.execute.call_count == 6
        assert lister.call_args.args[0] is mock_db_session

    mock_db_session.execute = AsyncMock(
        side_effect=[_result(scalar=v) for v in [0, 0, 0, 0, 0, 0.0]]
    )
    with patch.object(service, "list_webhooks", new_callable=AsyncMock) as lister:
        lister.return_value = []
        summary = await service.get_health_summary(mock_db_session)
    assert summary.average_response_time_ms is None


async def test_health_summary_nonzero_scalars_pass_through(service, mock_db_session):
    """Same helper proves the fallback is not ``or 1`` in the other direction:
    real scalars flow through untouched (avg None -> None)."""
    mock_db_session.execute = AsyncMock(
        side_effect=[_result(scalar=v) for v in [7, 5, 20, 15, 3, None]]
    )
    with patch.object(service, "list_webhooks", new_callable=AsyncMock) as lister:
        lister.return_value = []
        summary = await service.get_health_summary(mock_db_session)
    assert summary.model_dump() == {
        "total_webhooks": 7,
        "enabled_webhooks": 5,
        "healthy_webhooks": 0,
        "unhealthy_webhooks": 0,
        "total_deliveries_24h": 20,
        "successful_deliveries_24h": 15,
        "failed_deliveries_24h": 3,
        "average_response_time_ms": None,
    }

    mock_db_session.execute = AsyncMock(
        side_effect=[_result(scalar=v) for v in [7, 5, 20, 15, 3, 12.5]]
    )
    with patch.object(service, "list_webhooks", new_callable=AsyncMock) as lister:
        lister.return_value = []
        summary = await service.get_health_summary(mock_db_session)
    assert summary.average_response_time_ms == 12.5


@pytest.mark.parametrize(("scalar", "expected"), [(None, 0), (0, 0), (5, 5)])
async def test_get_deliveries_total_falls_back_to_zero(service, mock_db_session, scalar, expected):
    """Kills ``count_result.scalar() or 0`` -> ``or 1`` in get_deliveries."""
    mock_db_session.execute = AsyncMock(side_effect=[_result(scalar=scalar), _result(rows=[])])
    deliveries, total = await service.get_deliveries(mock_db_session, "wid-1", limit=50, offset=0)
    assert total == expected
    assert type(total) is int
    assert deliveries == []
    assert mock_db_session.execute.call_count == 2


# ===========================================================================
# C19 singleton (2) — get_webhook_service holder contract
# ===========================================================================
def test_get_webhook_service_singleton_roundtrip():
    """Kills ``is None`` -> ``is not None`` and ``instance = None``: the holder
    global must be populated with a real, stable WebhookService.

    Shipped reset pattern is the module-level holder attribute (there is no
    reset helper); the original value is restored in ``finally`` so no other
    test can observe a mutated singleton.
    """
    original = W._WebhookServiceHolder.instance
    try:
        W._WebhookServiceHolder.instance = None
        first = W.get_webhook_service()
        assert isinstance(first, WebhookService)
        assert first is not None
        assert W.get_webhook_service() is first
        assert W._WebhookServiceHolder.instance is first

        W._WebhookServiceHolder.instance = None
        assert W._WebhookServiceHolder.instance is None
        second = W.get_webhook_service()
        assert isinstance(second, WebhookService)
        assert second is not first
        assert W._WebhookServiceHolder.instance is second
    finally:
        W._WebhookServiceHolder.instance = original
    assert W._WebhookServiceHolder.instance is original


def test_get_webhook_service_reuses_preexisting_holder_instance():
    """The ``is None`` guard must NOT rebuild when an instance already exists."""
    original = W._WebhookServiceHolder.instance
    sentinel = WebhookService()
    try:
        W._WebhookServiceHolder.instance = sentinel
        assert W.get_webhook_service() is sentinel
        assert W.get_webhook_service() is sentinel
    finally:
        W._WebhookServiceHolder.instance = original


# ===========================================================================
# Shipped-contract extras measured while probing these clusters (not dossier
# drafts): formatter None-data crash and the webhook baseline used above.
# ===========================================================================
def test_formatters_crash_on_present_but_none_data(service):
    """.get("data", {}) only defaults a MISSING key — shipped behaviour raises."""
    for formatter in (
        service._format_slack_payload,
        service._format_discord_payload,
        service._format_teams_payload,
    ):
        with pytest.raises(AttributeError):
            formatter({"event_type": "e", "data": None})


def test_webhook_baseline_helper_matches_probe_construction():
    hook = webhook(IntegrationType.DISCORD, signing_secret=SECRET_A, total_deliveries=7)
    assert (hook.id, hook.url, hook.name) == (WID, URL, "Batch15")
    assert hook.integration_type is IntegrationType.DISCORD
    assert hook.total_deliveries == 7
    assert hook.max_retries == 4 and hook.retry_delay_seconds == 10
    assert str(uuid4()) != hook.id


# =============================================================================
# Consolidated from test_webhook_service_batch15b.py (B4.2 step 2)
# =============================================================================

# (Battery docstring, preserved verbatim — it is evidence.)
# Batch-15b mutation-kill battery: CURRENT-generation webhook survivors.
#
# Target: the 23 survivors the whserv re-check measured against the shipped +
# batch-15 suites (``/tmp/redcheck-whserv.log``, rc=0, 19 KILLED / 23 SURVIVED
# of the 42 CURRENT-cache keys — badge-relevant because the mutmut 3.x cache is
# diff-scoped and this generation IS the denominator). Module
# ``backend/services/webhook_service.py``.
#
# Survivor clusters and disposition (per-mutant, triaged against MEASURED
# shipped behavior — /tmp/b15b-harness.py → /tmp/b15b-probes.json):
# - SQL-shape family (keys 12-21, 11 total): shipped suites never compiled the
#   trigger query. Killed here by full-shape compiled SQL-text pins (batch-14
#   vehicle) plus plain-str-input shapes; ``and_(None, ...)`` / ``select(None)``
#   raise TypeError at build (measured), the rest change the emitted text.
# - ternary family 2/4/10: diverge and are killed. Key 2 (``= None``) makes
#   the query bind NULL; key 4 (``hasattr(event_type, None)``) raises
#   TypeError on EVERY input; key 10 (``else str(None)``) emits "None" for
#   plain-str inputs (MEASURED shipped: ``'motion' = ANY``). Killed by the
#   full-shape SQL text pins on enum AND plain-str inputs.
# - ternary family 3/8/9: EQUIVALENT for every input — WebhookEventType is a
#   str-subclass enum so ``str(e) == e.value`` (MEASURED); key 3
#   (``hasattr(None, …)`` → False) and keys 8/9 (absent attribute spellings
#   "XXvalueXX"/"VALUE") all fall to ``str(event_type)``, and for plain-str
#   input shipped already takes that branch. Documented; no test admissible.
# - debug-log family (25/26/28/29/30): message text + EXTRA KEY pinned EXACT.
# - ``__init___1``: stored-client identity pin.
#
# Every expected value MEASURED against shipped production this session;
# production NOT bent to any mutant. No kill tallies claimed here — those come
# only from the 15b lane red-check.
#
# ADDENDUM (superseded by whserv2, measured this session): the ternary
# disposition above was wrong on four counts — feed shapes re-dumped from
# /tmp/extracts/webhook_service.tsv show key 2 is ``and False`` and key 4 is
# ``hasattr(None, "value")`` (both fall to ``str(obj)``, NOT TypeError/None-
# bind), key 3 (``or True``) is NOT equivalent (forced ``.value`` raises
# AttributeError on plain-str input), and keys 2/4/8/9 all DIVERGE on a non-str
# input carrying ``.value`` where ``str(obj) != obj.value``. All four true gaps
# plus key 14 (WHERE-only asserts blind to ``select(None)``'s SELECT head) are
# killed in ``test_webhook_service_batch15c.py``; key 3 was killed by the
# plain-str shape test above.


def make_svc(rows=()):
    """Carrier: capture the COMPILED trigger SQL, return `rows` from scalars."""
    svc = WebhookService.__new__(WebhookService)
    cap: dict[str, str] = {}

    async def execute(stmt):
        cap["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        res = MagicMock(name="result")
        res.scalars.return_value.all.return_value = list(rows)
        return res

    db = MagicMock(name="db")
    db.execute = AsyncMock(side_effect=execute)
    return svc, db, cap


def patched_logger():
    lg = MagicMock(name="logger")
    orig = W.logger
    W.logger = lg
    return lg, orig


class TestInitStoresClient:
    def test_http_client_stored_identity(self):
        sentinel = object()
        svc = WebhookService.__new__(WebhookService)
        WebhookService.__init__(svc, sentinel)
        assert svc._http_client is sentinel  # kills `= None` (key 1)


class TestTriggerQueryShape:
    async def test_enum_sql_full_shape(self):
        svc, db, cap = make_svc()
        lg, orig = patched_logger()
        try:
            out = await svc.trigger_webhooks_for_event(
                db, WebhookEventType.ALERT_FIRED, {"a": 1}, "evt-1"
            )
        finally:
            W.logger = orig
        where = cap["sql"].split("WHERE")[1]
        assert "outbound_webhooks.enabled IS true" in where
        assert "'alert_fired' = ANY (outbound_webhooks.event_types)" in where
        # MEASURED empty-db return
        assert out == []

    async def test_plain_string_event_type_shape(self):
        # schema-adjacent input the shipped code explicitly supports via the
        # hasattr fallback; MEASURED: emits 'motion' = ANY (not str(None)).
        svc, db, cap = make_svc()
        lg, orig = patched_logger()
        try:
            await svc.trigger_webhooks_for_event(db, "motion", {}, None)  # type: ignore[arg-type]
        finally:
            W.logger = orig
        assert "'motion' = ANY (outbound_webhooks.event_types)" in cap["sql"]


class TestTriggerLoggingShape:
    async def test_empty_path_debug_message_and_extra_exact(self):
        svc, db, _ = make_svc()
        lg, orig = patched_logger()
        try:
            await svc.trigger_webhooks_for_event(db, WebhookEventType.ALERT_FIRED, {}, None)
        finally:
            W.logger = orig
        dbg = lg.debug.call_args
        assert dbg.args[0] == "No webhooks subscribed to event type: alert_fired"
        assert dict(dbg.kwargs["extra"]) == {"event_type": "alert_fired"}

    async def test_nonempty_info_message_extra_and_delivery(self):
        row = MagicMock(name="webhook")
        svc, db, _ = make_svc(rows=[row])
        delivered = MagicMock(name="delivery")
        svc.deliver_webhook = AsyncMock(return_value=delivered)
        lg, orig = patched_logger()
        try:
            out = await svc.trigger_webhooks_for_event(
                db, WebhookEventType.ALERT_FIRED, {"d": 2}, "evt-9"
            )
        finally:
            W.logger = orig
        inf = lg.info.call_args
        assert inf.args[0] == "Triggering 1 webhooks for event type: alert_fired"
        assert dict(inf.kwargs["extra"]) == {"event_type": "alert_fired", "webhook_count": 1}
        args = svc.deliver_webhook.call_args.args
        assert args[1] is row
        assert (
            args[2] is WebhookEventType.ALERT_FIRED
        )  # identity — str-enum == str passes either way
        assert args[3] == {"d": 2}
        assert args[4] == "evt-9"
        assert out == [delivered]


# =============================================================================
# Consolidated from test_webhook_service_batch15c.py (B4.2 step 2)
# =============================================================================

# (Battery docstring, preserved verbatim — it is evidence.)
# Batch-15c mutation-kill battery: whserv2's four true-gap survivors + the
# wh15c discord-default gap.
#
# Measured red-check inputs (this session, no assumptions):
# - ``whserv2`` (42 CURRENT-cache keys vs shipped + batch-15 + batch-15b)
#   landed 37 KILLED / 5 SURVIVED (``/tmp/redcheck-whserv2.log``, rc=0, source
#   clean). Survivors {2,4,8,9,14} triaged against the FEED SHAPES
#   (``/tmp/extracts/webhook_service.tsv`` full minus/plus, dumped this
#   session) — and two of my batch-15b claims were WRONG, corrected here:
#   * key 2 is ``and False`` (not ``= None`` as the 15b note said) and key 4 is
#     ``hasattr(None, "value")`` (not TypeError): BOTH make the ternary always
#     take ``str(event_type)``. For str-subclass enums and plain strings that
#     is invisible (measured equivalence), but a NON-str input carrying a
#     ``.value`` attribute diverges — shipped binds ``custom_duck`` (the
#     ``.value``), the mutants bind ``DUCK`` (``str(obj)``). MEASURED shipped
#     duck-input WHERE clause via /tmp/b15c-duck.py; killed by the duck pin.
#   * keys 8/9 (attribute spellings "XXvalueXX"/"VALUE") are the SAME
#     str-vs-value divergence on the same duck input — same pin kills them;
#     they stay documented EQUIVALENT for enum/plain-str inputs only.
#   * key 3 (``or True``, always ``.value`` branch) is NOT equivalent after
#     all: on plain-str input the forced ``.value`` raises AttributeError
#     (measured). It was already KILLED by the batch-15b plain-str shape test
#     in whserv2 — the 15b docstring's "keys 3/8/9 equivalent" claim is
#     superseded by this row.
#   * key 14 ``select(OutboundWebhook)`` -> ``select(None)`` changes the
#     SELECT head to ``SELECT NULL AS anon_1`` while the WHERE clause stays
#     intact — the 15b test asserted into ``sql.split("WHERE")[1]`` only, so
#     it could never see it. Killed by a SELECT-head prefix pin (full
#     MEASURED 18-column head from /tmp/b15c-probes.json).
# - ``wh15c2`` (77-key batch-15-era feed vs batch-15 battery) landed 76 KILLED
#   / 1 SURVIVED: ``_format_discord_payload__mutmut_9`` swaps the default
#   ``payload.get("event_type", "event")`` -> ``"EVENT"``, which only shows in
#   the embed TITLE (``"event".title() == "Event"``). Killed by pinning the
#   MEASURED shipped titles (absent event_type -> title "Event";
#   "alert_fired" -> "Alert Fired"; fields verified verbatim).
#
# Every expected value MEASURED against shipped production this session;
# production NOT bent to any mutant. No kill tallies claimed here — those
# come only from the whserv3/wh15d lane red-checks.


class DuckEventType:
    """Non-str input carrying .value where str(obj) != obj.value — the only
    input class that separates the ternary mutants from shipped (measured)."""

    value = "custom_duck"

    def __str__(self) -> str:
        return "DUCK"


def make_svc_b15c(rows=()):
    svc = WebhookService.__new__(WebhookService)
    cap: dict[str, str] = {}

    async def execute(stmt):
        cap["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        res = MagicMock(name="result")
        res.scalars.return_value.all.return_value = list(rows)
        return res

    db = MagicMock(name="db")
    db.execute = AsyncMock(side_effect=execute)
    return svc, db, cap


class TestValueAttributeBinding:
    async def test_duck_input_binds_value_not_str(self):
        # MEASURED shipped: "'custom_duck' = ANY (…)" — the .value branch.
        # Mutants 2 (and False), 4 (hasattr(None,"value")), 8/9 (spelling
        # "XXvalueXX"/"VALUE") all fall to str(obj) -> binds "DUCK".
        svc, db, cap = make_svc_b15c()
        lg, orig = patched_logger()
        try:
            await svc.trigger_webhooks_for_event(db, DuckEventType(), {}, None)  # type: ignore[arg-type]
        finally:
            W.logger = orig
        where = cap["sql"].split("WHERE")[1]
        assert "'custom_duck' = ANY (outbound_webhooks.event_types)" in where
        assert "'DUCK'" not in cap["sql"]


class TestSelectHeadShape:
    async def test_select_head_full_columns(self):
        # key 14 select(None) emits "SELECT NULL AS anon_1" — WHERE-only
        # asserts are blind to it; pin the MEASURED shipped head prefix.
        svc, db, cap = make_svc_b15c()
        lg, orig = patched_logger()
        try:
            from backend.api.schemas.outbound_webhook import WebhookEventType

            await svc.trigger_webhooks_for_event(db, WebhookEventType.ALERT_FIRED, {}, None)
        finally:
            W.logger = orig
        assert cap["sql"].startswith(
            "SELECT outbound_webhooks.id, outbound_webhooks.name, "
            "outbound_webhooks.url, outbound_webhooks.event_types, "
            "outbound_webhooks.integration_type, outbound_webhooks.enabled, "
            "outbound_webhooks.on_local_network, "
            "outbound_webhooks.auth_config, outbound_webhooks.custom_headers, "
            "outbound_webhooks.payload_template, outbound_webhooks.max_retries, "
            "outbound_webhooks.retry_delay_seconds, outbound_webhooks.signing_secret, "
            "outbound_webhooks.created_at, outbound_webhooks.updated_at, "
            "outbound_webhooks.total_deliveries, outbound_webhooks.successful_deliveries, "
            "outbound_webhooks.last_delivery_at, outbound_webhooks.last_delivery_status"
        )


class TestDiscordTitleDefault:
    def test_missing_event_type_title_exact(self):
        # wh15c2 survivor: default "event" -> "EVENT" changes title
        # "Event" -> "EVENT". MEASURED shipped title + fields verbatim.
        svc = WebhookService.__new__(WebhookService)
        out = svc._format_discord_payload({"data": {"x": 1}})
        embed = out["embeds"][0]
        assert embed["title"] == "Event"
        assert embed["fields"] == [{"name": "X", "value": "1", "inline": True}]

    def test_provided_event_type_title_exact(self):
        svc = WebhookService.__new__(WebhookService)
        out = svc._format_discord_payload({"data": {"x": 1}, "event_type": "alert_fired"})
        assert out["embeds"][0]["title"] == "Alert Fired"


# =============================================================================
# Consolidated from test_webhook_service_batch38_x.py (B4.2 step 2)
# =============================================================================
# TARGET-MODULE: backend.services.webhook_service

# (Battery docstring, preserved verbatim — it is evidence.)
# Battery X — campaign #22 of the ladder (batch-38): kill-real coverage for
# ``backend/services.webhook_service.py`` (262 survivors at 75.7183% entering).
#
# Harness-compatible by design (batch-30 single-process sweep): every test is a
# module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
# run through ``asyncio.run`` inside. The file is also collected by normal
# pytest in the repo tree, and every seam swap is restored on context exit.
#
# What kills what (each polarity MEASURED against the shipped code before the
# assert was written):
#
# * COMPILED-SQL MIRRORS — the fake session records every executed statement
#   as ``str(stmt.compile(literal_binds))`` and tests assert the whole list
#   against plain-code mirrors built from the real expressions. ``select(X) ->
#   select(None)`` renders ``SELECT NULL AS anon_1``, ``.where(clause) ->
#   .where(None)`` and ``and_(a, None)`` render ``NULL``, ``and_(a, b) ->
#   and_(a)`` drops the conjunct, ``is_(True) -> is_(None)/(False)`` render
#   ``IS NULL``/``IS false``, ``any(v) -> any(None)`` renders ``NULL = ANY``,
#   ``== -> !=`` renders ``!=``, and a call-arg flip ``get_webhook(db, None)``
#   renders ``id = NULL``. ``db.execute(None)`` cannot compile and is recorded
#   as ``<unrenderable AttributeError>``. Every flip becomes a string.
# * NON-ENUM POLARITIES — for a real ``StrEnum`` the
#   ``x.value if hasattr(x, "value") else str(x)`` family is invisible
#   (``str(enum) == enum.value``), so each site ALSO runs with (a) ``_Event``
#   whose ``.value`` differs from its ``str()`` — the and-False,
#   ``hasattr(None, ...)`` and ``"value" -> XX/VALUE`` flips take the
#   str-branch there and diverge — and (b) a plain ``str`` entry with NO
#   ``.value``, which kills the ``or True`` flips (forced ``.value`` ->
#   ``AttributeError``) and the ``str(None)`` else-branch flips; the
#   ``hasattr(x, None)`` / one-arg / trailing-comma flips raise ``TypeError``
#   at every polarity.
# * LOG RECORD LISTS — a fake logger records ``(level, msg, kwargs)`` tuples
#   compared as whole lists: msg->None, ``extra=None``, ``extra`` deletion
#   (kwargs become ``{}``), every extra-key XX/upper flip, and the
#   ``exc_info`` kwarg in the unexpected-error arm.
# * WHOLE-CALL SPIES — ``_send_request`` and ``_handle_delivery_failure`` are
#   swapped on the CLASS and record the whole call tuple, which kills the
#   arg-swap / arg-None / ARG-DELETION families at all three call sites (the
#   trailing-comma form leaves one positional argument -> ``TypeError``, which
#   ``retry_delivery`` PROPAGATES and a test asserts, interim state included).
# * STRICT JINJA SPIES — a fake ``_jinja_env`` asserts the EXACT render
#   context ``{event_type, timestamp, webhook_id, data, **event_data}``; the
#   resulting ``AssertionError`` is outside the module's
#   ``except (TemplateSyntaxError, UndefinedError, JSONDecodeError)`` tuple so
#   kwarg-None and kwarg-deletion mutants propagate instead of falling back.
# * AUTH MATRIX — thirteen ``auth_config`` shapes through a fake module
#   ``httpx`` whose ``AsyncClient`` wraps the real client on a recording
#   transport, asserted as whole header dicts. The absent-key rows are what
#   make the ``.get(key, default)`` family observable: on the key-absent
#   polarity a swapped default becomes the consumed value, and
#   ``get("header_name", None)`` -> ``headers[x] = None`` raises
#   ``TypeError`` inside httpx's ``Headers`` (measured; an empty-string value
#   is accepted). Note ``get(k, )`` (trailing comma = default deleted) is
#   ONE-ARG ``get`` -> ``None``, never a KeyError.
# * REAL-MODEL INSPECTION — ``create_webhook`` returns a real
#   ``OutboundWebhook`` the fake session captured (every construction-kwarg
#   None/deletion flip is an attribute difference; the models' defaults are
#   all ``None``, measured) and ``deliver``/``retry`` assert every post-send
#   mutation, with the webhook entering on non-zero/non-one counters so the
#   ``+= 1 -> = 1 / -= 1 / += 2`` twins diverge.
# * EXACT BOUNDARIES — statuses 200/299/300/404/500 (success-window flips),
#   a 2001-char body for the ``[:2000]`` store cap, 600-char exception
#   messages for the ``[:500] -> [:501]`` twins, a fixed clock
#   (``utc_now`` -> ``2026-12-15T10:30Z``, module ``datetime`` -> a constant
#   ``now()``) so backoff/cutoff/timestamp/response_time are exact, and
#   backoff cases where ``attempt - 1 -> + 1``, ``* 2 -> * 3`` and ``min ->
#   max`` all diverge.
#
# Honesty ledger — dispositions registered EQUIVALENT. The sweep must show
# GREEN on exactly these 12 keys; any other GREEN is a test gap, and a RED
# here is a battery bug. Each was decided BY CONSTRUCTION this session —
# orig-vs-mutant equality on every polarity the module itself can reach:
#
# * ``__init__`` m1 — ``self._http_client = http_client -> None``: the
#   attribute is stored and read nowhere in the module (every send builds its
#   own client), so the store is unreachable. Measured: attribute-only
#   divergence.
# * ``create_webhook`` m2 — ``secrets.token_hex(32) -> token_hex(None)``:
#   measured both produce a 64-char hex string (``token_hex(None)`` defaults
#   to 32 bytes), and the value is only stored and logged, never compared.
# * ``deliver_webhook`` m12/m18 — ``status=WebhookDeliveryStatus.PENDING ->
#   None`` (m18 deletes the kwarg, whose model default is ``None``, measured):
#   every reachable arm overwrites ``delivery.status`` (SUCCESS, RETRYING or
#   FAILED) before the object is observed, and the fake session records the
#   same object either way.
# * ``_format_discord_payload`` m9 — ``.get("event_type", "event") ->
#   "EVENT"``: the default is consumed only when the payload lacks the key,
#   and both spellings pass through ``.replace("_", " ").title()`` which
#   measured identically (``"Event"``); the reachable callers always set the
#   key.
# * ``_sign_payload`` m13 — ``encode("utf-8") -> encode("UTF-8")``: codec
#   names are case-insensitive; digest measured identical.
# * ``_send_request`` m16/m18/m21/m22 — ``.get("type", "none") -> None /
#   (default deleted) / "XXnoneXX" / "NONE"``: the default is consumed only
#   when ``auth_config`` is truthy but carries no ``type`` key (that row IS in
#   the matrix), and the value's ONLY consumer is the
#   ``bearer``/``basic``/``header`` equality chain. ``None``, ``"none"``,
#   ``"XXnoneXX"`` and ``"NONE"`` all match none of the three arms (the
#   trailing-comma m18 is one-arg ``get`` -> ``None``, NOT a KeyError —
#   measured on the shipped tree), so the auth section is skipped
#   identically. Measured equal on the no-type row.
# * ``_send_request`` m68/m70 — ``.get("header_name", "") -> None / (default
#   deleted)``: the default is only ever consumed on the key-absent polarity,
#   and its use is ``if header_name:`` — ``""`` and ``None`` are both falsy,
#   so no header is written either way.
#
# All other 250 survivor keys carry an explicit kill polarity above.
# Run-1 outcome (measured): the sweep showed RED=250/250 scope keys and
# GREEN=12/12 ledger keys, and the RUN preserved exactly 11 of the 12 as
# survivors — ``__init__`` m1 was ADDITIONALLY killed by the pre-existing
# suite (some shipped test reads the attribute the sweep alone never saw).
# The run grew the target 1079 -> 1110 keys; all three adjudicated
# survivor-births (``test_webhook`` m59 success-flip, m60 and
# ``retry_delivery`` m49 truncation twins) are KILLABLE, not equivalent,
# and are closed by this extension's 600-char full-dump arms — run 2's
# sweep result is disclosed in the milestone row.


def _globals_of(obj: Any) -> dict[str, Any]:
    """Module globals of the REAL function (mutant wrappers delegate)."""
    fn = obj
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn.__globals__


_G = _globals_of(WebhookService.create_webhook)
assert _G.get("WebhookService") is WebhookService

# --------------------------------------------------------------------------
# fixed clock
# --------------------------------------------------------------------------

_FIXED = datetime(2026, 12, 15, 10, 30, tzinfo=UTC)
_FIXED_ISO = _FIXED.isoformat()


def _fixed_now() -> datetime:
    return _FIXED


class _FixedDT:
    """Module-global ``datetime`` swap: ``_send_request`` only calls now()."""

    @staticmethod
    def now(_tz: Any = None) -> datetime:
        return _FIXED


class _Env:
    """Swap module globals for one test; restore on exit."""

    def __init__(self, **kw: Any) -> None:
        self._old: dict[str, Any] = {}
        for key, value in kw.items():
            self._old[key] = _G[key]
            _G[key] = value

    def __enter__(self) -> _Env:
        return self

    def __exit__(self, *_exc: Any) -> None:
        for key, value in self._old.items():
            _G[key] = value


# --------------------------------------------------------------------------
# fake logger
# --------------------------------------------------------------------------


class _Logger:
    """Records ``(level, msg, merged)`` — the ``extra`` payload merged with
    any sibling kwargs (``exc_info``). ``extra=None`` / extra-deletion /
    extra-key mutants all change the recorded dict."""

    def __init__(self) -> None:
        self.recs: list[Any] = []

    def _rec(self, level: str, msg: Any, **kw: Any) -> None:
        extra = kw.pop("extra", None)
        merged: dict[str, Any] = dict(extra) if isinstance(extra, dict) else {}
        merged.update(kw)
        self.recs.append((level, msg, merged))

    def debug(self, msg: Any, **kw: Any) -> None:
        self._rec("DEBUG", msg, **kw)

    def info(self, msg: Any, **kw: Any) -> None:
        self._rec("INFO", msg, **kw)

    def warning(self, msg: Any, **kw: Any) -> None:
        self._rec("WARNING", msg, **kw)

    def error(self, msg: Any, **kw: Any) -> None:
        self._rec("ERROR", msg, **kw)


# --------------------------------------------------------------------------
# fake DB session with compiled-SQL recording
# --------------------------------------------------------------------------


def _sql_b38x(stmt: Any) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def _rendered(stmt: Any) -> str:
    try:
        return _sql_b38x(stmt)
    except Exception as e:
        return f"<unrenderable {type(e).__name__}>"


class _Res:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> _Res:
        return self

    def all(self) -> list[Any]:
        return list(self._value)

    def scalar(self) -> Any:
        return self._value


class _Scripted:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self._pos = 0

    def __call__(self) -> Any:
        pos = self._pos
        self._pos += 1
        if pos >= len(self._results):
            raise AssertionError("scripted db results exhausted")
        return _Res(self._results[pos])


class _Nested:
    """SAVEPOINT stand-in: records enter/exit, lets exceptions propagate
    (a real savepoint's ``__aexit__`` returns None and does not swallow)."""

    def __init__(self, db: _DB) -> None:
        self._db = db

    async def __aenter__(self) -> _Nested:
        self._db.nested_enters += 1
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._db.nested_exits += 1


class _DB:
    def __init__(self, results: list[Any]) -> None:
        self.executed: list[str] = []
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushes = 0
        self.refreshed: list[Any] = []
        self.nested_enters = 0
        self.nested_exits = 0
        self._script = _Scripted(results)

    def begin_nested(self) -> _Nested:
        return _Nested(self)

    async def execute(self, statement: Any, *args: Any, **kw: Any) -> Any:
        self.executed.append(_rendered(statement))
        return self._script()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, obj: Any) -> None:
        if obj is None:
            raise ValueError("Refresh of a None instance")
        self.refreshed.append(obj)


# --------------------------------------------------------------------------
# non-enum polarity objects: .value deliberately differs from str()
# --------------------------------------------------------------------------


class _Event:
    """Has ``.value`` but ``str(obj) != obj.value`` (kills the branch flips)."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return "S"


class _RawIT:
    """integration_type without ``.value`` whose str() is not a literal."""

    def __init__(self, v: str) -> None:
        self.v = v

    def __str__(self) -> str:
        return "IT:" + self.v


_WID = "w1"
_URL = "https://x.test/p"
_SIG_SECRET = "ff" * 32  # pragma: allowlist secret
_GET_SQL = _sql_b38x(select(OutboundWebhook).where(OutboundWebhook.id == _WID))


def _trigger_sql(value: Any) -> str:
    return _sql_b38x(
        select(OutboundWebhook).where(
            and_(
                OutboundWebhook.enabled.is_(True),
                OutboundWebhook.event_types.any(value),
            )
        )
    )


def _delivery_select_sql(did: str) -> str:
    return _sql_b38x(select(WebhookDelivery).where(WebhookDelivery.id == did))


def _webhook(**over: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "id": _WID,
        "url": _URL,
        "event_types": ["alert_fired"],
        "integration_type": SchemaIntegrationType.GENERIC,
        "enabled": True,
        # B4.2 ruling 310: _send_request reads this for the F12 destination
        # policy; False keeps every existing URL valid under the default flag.
        "on_local_network": False,
        "auth_config": None,
        "custom_headers": {},
        "payload_template": None,
        "max_retries": 4,
        "retry_delay_seconds": 10,
        "signing_secret": None,
        "total_deliveries": 0,
        "successful_deliveries": 0,
        "last_delivery_at": None,
        "last_delivery_status": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


def _std_payload(event_type: Any, data: Any, wid: str = _WID) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "timestamp": _FIXED_ISO,
        "webhook_id": wid,
        "data": data,
    }


def _hmac_sig(payload: dict[str, Any], secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(bytes.fromhex(secret), body, hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------
# class-level spies
# --------------------------------------------------------------------------


class _SendSpy:
    """Records the whole ``(webhook, payload)`` call tuple."""

    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.calls: list[Any] = []
        self._result = result
        self._error = error
        self._old: Any = None

    async def _send_request(self, webhook: Any, payload: dict[str, Any]) -> tuple[int, str, int]:
        self.calls.append((webhook, payload))
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result

    def __enter__(self) -> _SendSpy:
        self._old = WebhookService._send_request
        WebhookService._send_request = self._send_request  # type: ignore[method-assign]
        return self

    def __exit__(self, *_exc: Any) -> None:
        WebhookService._send_request = self._old


class _FailSpy:
    """Records the whole ``(db, webhook, delivery)`` tuple and reproduces the
    real tail bookkeeping so the stats keys still diverge where they should."""

    def __init__(self) -> None:
        self.calls: list[Any] = []
        self._old: Any = None

    async def _handle(self, db: Any, webhook: Any, delivery: Any) -> None:
        self.calls.append((db, webhook, delivery))
        webhook.total_deliveries += 1
        webhook.last_delivery_at = _FIXED
        webhook.last_delivery_status = "spied"

    def __enter__(self) -> _FailSpy:
        self._old = WebhookService._handle_delivery_failure
        WebhookService._handle_delivery_failure = self._handle  # type: ignore[method-assign]
        return self

    def __exit__(self, *_exc: Any) -> None:
        WebhookService._handle_delivery_failure = self._old


# ==========================================================================
# singleton + background trigger
# ==========================================================================


def test_get_webhook_service_singleton_battery38() -> None:
    holder = _G["_WebhookServiceHolder"]
    old = holder.instance
    holder.instance = None
    try:
        first = _G["get_webhook_service"]()
        assert isinstance(first, WebhookService)
        assert holder.instance is first
        assert holder.instance is not None
        assert _G["get_webhook_service"]() is first
    finally:
        holder.instance = old


def test_trigger_webhook_background_ok() -> None:
    svc = WebhookService()
    calls: list[Any] = []

    async def _trigger(db: Any, event_type: Any, event_data: Any, event_id: Any = None) -> None:
        calls.append((db, event_type, event_data, event_id))

    svc.trigger_webhooks_for_event = _trigger  # type: ignore[method-assign]
    log = _Logger()
    with _Env(get_webhook_service=lambda: svc, logger=log):
        asyncio.run(
            _G["trigger_webhook_background"](
                "DB", WebhookEventType.ALERT_FIRED, {"a": 1}, event_id="e7"
            )
        )
    assert calls == [("DB", WebhookEventType.ALERT_FIRED, {"a": 1}, "e7")]
    assert log.recs == []


def test_trigger_webhook_background_swallows() -> None:
    svc = WebhookService()

    async def _boom(_db: Any, _event_type: Any, _event_data: Any, event_id: Any = None) -> None:
        raise RuntimeError("kaput")

    svc.trigger_webhooks_for_event = _boom  # type: ignore[method-assign]
    log = _Logger()
    with _Env(get_webhook_service=lambda: svc, logger=log):
        asyncio.run(
            _G["trigger_webhook_background"](
                "DB", WebhookEventType.ALERT_FIRED, {"a": 1}, event_id="e7"
            )
        )
    assert log.recs == [
        (
            "WARNING",
            "Background webhook trigger failed for alert_fired: kaput",
            {"event_type": "alert_fired", "event_id": "e7"},
        )
    ]


# ==========================================================================
# CRUD
# ==========================================================================


def test_get_webhook() -> None:
    svc = WebhookService()
    row = SimpleNamespace(id=_WID)
    db = _DB([row])
    with _Env(utc_now=_fixed_now):
        got = asyncio.run(svc.get_webhook(db, _WID))
    assert got is row
    assert db.executed == [_GET_SQL]


_MIXED_EVENTS: list[Any] = [WebhookEventType.ALERT_FIRED, _Event("alert_fired"), "plain_entry"]


def test_create_webhook() -> None:
    svc = WebhookService()
    data = WebhookCreate.model_construct(
        name="Hooks",
        url="https://x.test/hooks",
        event_types=list(_MIXED_EVENTS),
        integration_type=SchemaIntegrationType.SLACK,
        enabled=True,
        auth=None,
        custom_headers=None,
        payload_template="tmpl",
        max_retries=3,
        retry_delay_seconds=20,
    )
    db = _DB([])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        w = asyncio.run(svc.create_webhook(db, data))
    assert isinstance(w, OutboundWebhook)
    assert db.added == [w]
    assert w.name == "Hooks"
    assert w.url == "https://x.test/hooks"
    assert w.event_types == ["alert_fired", "alert_fired", "plain_entry"]
    assert w.integration_type is SchemaIntegrationType.SLACK
    assert w.enabled is True
    assert w.auth_config is None
    assert w.custom_headers == {}
    assert w.payload_template == "tmpl"
    assert w.max_retries == 3
    assert w.retry_delay_seconds == 20
    assert w.signing_secret is not None
    assert len(w.signing_secret) == 64
    assert db.executed == []
    assert db.flushes == 1
    assert db.refreshed == [w]
    assert log.recs == [
        (
            "INFO",
            "Created webhook 'Hooks' (id=None)",
            {
                "webhook_id": None,
                "webhook_name": "Hooks",
                "event_types": ["alert_fired", "alert_fired", "plain_entry"],
            },
        )
    ]


def test_create_webhook_auth_dump_and_custom_headers() -> None:
    svc = WebhookService()
    data = WebhookCreate.model_construct(
        name="Auth",
        url="https://x.test/auth",
        event_types=[WebhookEventType.ALERT_FIRED],
        integration_type=SchemaIntegrationType.GENERIC,
        enabled=False,
        auth=WebhookAuthConfig(type="bearer", token="t"),
        custom_headers={"X-A": "1"},
        payload_template=None,
        max_retries=0,
        retry_delay_seconds=1,
    )
    db = _DB([])
    with _Env(logger=_Logger(), utc_now=_fixed_now):
        w = asyncio.run(svc.create_webhook(db, data))
    assert w.auth_config == {
        "type": "bearer",
        "token": "t",
        "username": None,
        "password": None,
        "header_name": None,
        "header_value": None,
    }
    assert w.custom_headers == {"X-A": "1"}
    assert w.enabled is False
    assert w.max_retries == 0
    assert w.retry_delay_seconds == 1
    data2 = WebhookCreate.model_construct(
        name="Auth2",
        url="https://x.test/auth2",
        event_types=[WebhookEventType.ALERT_FIRED],
        integration_type=SchemaIntegrationType.GENERIC,
        enabled=True,
        auth=None,
        custom_headers={},
        payload_template=None,
        max_retries=4,
        retry_delay_seconds=10,
    )
    db2 = _DB([])
    with _Env(logger=_Logger(), utc_now=_fixed_now):
        w2 = asyncio.run(svc.create_webhook(db2, data2))
    assert w2.auth_config is None
    assert w2.custom_headers == {}


def _full_update() -> WebhookUpdate:
    return WebhookUpdate.model_construct(
        name="New",
        url="https://x.test/new",
        event_types=list(_MIXED_EVENTS),
        integration_type=SchemaIntegrationType.DISCORD,
        enabled=False,
        # F12 field present (False): the update-path effective-flag read
        # consumes it; None would mean "not provided" and fall back to the
        # stored flag — False is the exercised branch here.
        on_local_network=False,
        auth=WebhookAuthConfig(type="basic", username="u", password="p"),
        custom_headers={"H": "1"},
        payload_template="pt",
        max_retries=2,
        retry_delay_seconds=30,
    )


def test_update_webhook_full() -> None:
    svc = WebhookService()
    hook = _webhook()
    db = _DB([hook])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        got = asyncio.run(svc.update_webhook(db, _WID, _full_update()))
    assert got is hook
    assert hook.name == "New"
    assert hook.url == "https://x.test/new"
    assert hook.event_types == ["alert_fired", "alert_fired", "plain_entry"]
    assert hook.integration_type is SchemaIntegrationType.DISCORD
    assert hook.enabled is False
    assert hook.auth_config == {
        "type": "basic",
        "token": None,
        "username": "u",
        "password": "p",
        "header_name": None,
        "header_value": None,
    }
    assert hook.custom_headers == {"H": "1"}
    assert hook.payload_template == "pt"
    assert hook.max_retries == 2
    assert hook.retry_delay_seconds == 30
    assert db.executed == [_GET_SQL]
    assert db.flushes == 1
    assert db.refreshed == [hook]
    assert log.recs == [
        (
            "DEBUG",
            "Updated webhook w1",
            {
                "webhook_id": _WID,
                "updated_fields": [
                    "name",
                    "url",
                    "on_local_network",
                    "event_types",
                    "integration_type",
                    "enabled",
                    "auth_config",
                    "custom_headers",
                    "payload_template",
                    "max_retries",
                    "retry_delay_seconds",
                ],
            },
        )
    ]


def test_update_webhook_partial_enabled() -> None:
    svc = WebhookService()
    hook = _webhook(name="Old", enabled=True)
    db = _DB([hook])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        got = asyncio.run(svc.update_webhook(db, _WID, WebhookUpdate(enabled=False)))
    assert got is hook
    assert hook.enabled is False
    assert hook.name == "Old"
    assert db.executed == [_GET_SQL]
    assert db.flushes == 1
    assert db.refreshed == [hook]
    assert log.recs == [
        (
            "DEBUG",
            "Updated webhook w1",
            {"webhook_id": _WID, "updated_fields": ["enabled"]},
        )
    ]


def test_update_webhook_missing_returns_none() -> None:
    svc = WebhookService()
    db = _DB([None])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        assert asyncio.run(svc.update_webhook(db, _WID, WebhookUpdate(name="X"))) is None
    assert db.flushes == 0
    assert log.recs == []


def test_update_webhook_noop_skips_flush_and_log() -> None:
    svc = WebhookService()
    hook = _webhook(name="Old", enabled=True)
    db = _DB([hook])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        got = asyncio.run(svc.update_webhook(db, _WID, WebhookUpdate()))
    assert got is hook
    assert hook.name == "Old"
    assert hook.enabled is True
    assert db.flushes == 0
    assert db.refreshed == []
    assert log.recs == []


def test_delete_webhook() -> None:
    svc = WebhookService()
    hook = _webhook()
    db = _DB([hook])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        assert asyncio.run(svc.delete_webhook(db, _WID)) is True
    assert db.deleted == [hook]
    assert db.executed == [_GET_SQL]
    assert db.flushes == 1
    assert log.recs == [("INFO", "Deleted webhook w1", {"webhook_id": _WID})]


def test_delete_webhook_missing() -> None:
    svc = WebhookService()
    db = _DB([None])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        assert asyncio.run(svc.delete_webhook(db, "missing")) is False
    assert db.deleted == []
    assert db.flushes == 0
    assert log.recs == []


# ==========================================================================
# deliver_webhook
# ==========================================================================


def test_deliver_success() -> None:
    svc = WebhookService()
    w = _webhook(total_deliveries=2, successful_deliveries=1)
    payload = _std_payload("alert_fired", {"k": 1})
    log = _Logger()
    fake = _SendSpy(result=(200, "body-x", 42))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "evt-9"))
    assert isinstance(d, WebhookDelivery)
    assert db.added == [d]
    assert d.webhook_id == _WID
    assert d.event_type == "alert_fired"
    assert d.event_id == "evt-9"
    assert d.status == SchemaWebhookDeliveryStatus.SUCCESS
    assert d.request_payload == payload
    assert d.attempt_count == 1
    assert d.status_code == 200
    assert d.response_body == "body-x"
    assert d.response_time_ms == 42
    assert d.delivered_at == _FIXED
    assert d.error_message is None
    assert fake.calls == [(w, payload)]
    assert w.total_deliveries == 3
    assert w.successful_deliveries == 2
    assert w.last_delivery_at == _FIXED
    assert w.last_delivery_status == "success"
    assert db.flushes == 2
    assert db.refreshed == [d]
    assert log.recs == [
        (
            "DEBUG",
            "Webhook delivered successfully: w1 -> https://x.test/p",
            {
                "webhook_id": _WID,
                "delivery_id": None,
                "status_code": 200,
                "response_time_ms": 42,
            },
        )
    ]


def test_deliver_string_event_and_upper_bound() -> None:
    # an event_type with no .value takes the str-branch; 299 is the last
    # success status
    svc = WebhookService()
    w = _webhook()
    log = _Logger()
    fake = _SendSpy(result=(299, "b", 1))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, "x", {"k": 1}, "evt-9"))
    assert d.event_type == "x"
    assert d.status == SchemaWebhookDeliveryStatus.SUCCESS
    assert fake.calls == [(w, _std_payload("x", {"k": 1}))]
    assert log.recs[0][2]["status_code"] == 299


def test_deliver_boundary_300_is_failure() -> None:
    svc = WebhookService()
    w = _webhook()
    log = _Logger()
    fake = _SendSpy(result=(300, "b", 1))
    fail = _FailSpy()
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake, fail:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status_code == 300
    assert d.error_message == "HTTP 300"
    assert fake.calls == [(w, _std_payload("alert_fired", {"k": 1}))]
    assert fail.calls == [(db, w, d)]


def test_deliver_response_body_cap() -> None:
    svc = WebhookService()
    w = _webhook()
    log = _Logger()
    fake = _SendSpy(result=(200, "x" * 2001, 1))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.response_body == "x" * 2000
    fake2 = _SendSpy(result=(500, "y" * 2001, 1))
    fail = _FailSpy()
    db2 = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake2, fail:
        d2 = asyncio.run(svc.deliver_webhook(db2, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d2.response_body == "y" * 2000


def test_deliver_http_error_schedules_retry() -> None:
    svc = WebhookService()
    w = _webhook(total_deliveries=2)
    log = _Logger()
    fake = _SendSpy(result=(500, "oops", 7))
    db = _DB([])
    retry_at = _FIXED + timedelta(seconds=10)
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status == SchemaWebhookDeliveryStatus.RETRYING
    assert d.status_code == 500
    assert d.response_body == "oops"
    assert d.response_time_ms == 7
    assert d.error_message == "HTTP 500"
    assert d.next_retry_at == retry_at
    assert d.delivered_at is None
    assert w.total_deliveries == 3
    assert w.successful_deliveries == 0
    assert w.last_delivery_at == _FIXED
    assert w.last_delivery_status == "retrying"
    assert db.flushes == 2
    assert log.recs == [
        (
            "WARNING",
            "Webhook delivery failed, scheduling retry 2/4",
            {
                "webhook_id": _WID,
                "delivery_id": None,
                "next_retry_at": retry_at.isoformat(),
                "error": "HTTP 500",
            },
        )
    ]


def test_deliver_http_error_exhausts_retries() -> None:
    svc = WebhookService()
    w = _webhook(max_retries=1)
    log = _Logger()
    fake = _SendSpy(result=(500, "oops", 7))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status == SchemaWebhookDeliveryStatus.FAILED
    assert d.next_retry_at is None
    assert d.delivered_at is None
    assert w.total_deliveries == 1
    assert w.last_delivery_at == _FIXED
    assert w.last_delivery_status == "failed"
    assert log.recs == [
        (
            "ERROR",
            "Webhook delivery failed after 1 attempts",
            {"webhook_id": _WID, "delivery_id": None, "error": "HTTP 500"},
        )
    ]


def test_deliver_network_error() -> None:
    svc = WebhookService()
    w = _webhook(total_deliveries=2)
    log = _Logger()
    fake = _SendSpy(error=httpx.RequestError("net-boom"))
    db = _DB([])
    retry_at = _FIXED + timedelta(seconds=10)
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status == SchemaWebhookDeliveryStatus.RETRYING
    assert d.error_message == "net-boom"
    assert d.status_code is None
    assert d.response_body is None
    assert d.response_time_ms is None
    assert d.next_retry_at == retry_at
    assert w.total_deliveries == 3
    assert w.last_delivery_status == "retrying"
    assert db.flushes == 2
    assert log.recs == [
        (
            "WARNING",
            "Webhook delivery failed, scheduling retry 2/4",
            {
                "webhook_id": _WID,
                "delivery_id": None,
                "next_retry_at": retry_at.isoformat(),
                "error": "net-boom",
            },
        )
    ]


def test_deliver_network_failure_call_shape() -> None:
    # the RequestError arm's call-site db argument: the spy sees the WHOLE
    # tuple, so db -> None diverges even though the callee ignores db
    svc = WebhookService()
    w = _webhook()
    log = _Logger()
    fake = _SendSpy(error=httpx.RequestError("dns"))
    fail = _FailSpy()
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake, fail:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert fail.calls == [(db, w, d)]
    assert d.error_message == "dns"


def test_deliver_error_message_truncation() -> None:
    # kills the ``[:500] -> [:501]`` twins on both error arms
    svc = WebhookService()
    log = _Logger()
    w1 = _webhook()
    fake = _SendSpy(error=httpx.RequestError("y" * 600))
    db1 = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d1 = asyncio.run(svc.deliver_webhook(db1, w1, _Event("alert_fired"), {"k": 1}, "e"))
    assert d1.error_message == "y" * 500
    w2 = _webhook()
    fake2 = _SendSpy(error=ValueError("z" * 600))
    db2 = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake2:
        d2 = asyncio.run(svc.deliver_webhook(db2, w2, _Event("alert_fired"), {"k": 1}, "e"))
    assert d2.error_message == "z" * 500


def test_deliver_unexpected_error() -> None:
    svc = WebhookService()
    w = _webhook(total_deliveries=2)
    log = _Logger()
    fake = _SendSpy(error=ValueError("kapow"))
    db = _DB([])
    with _Env(logger=log, utc_now=_fixed_now), fake:
        d = asyncio.run(svc.deliver_webhook(db, w, _Event("alert_fired"), {"k": 1}, "e"))
    assert d.status == SchemaWebhookDeliveryStatus.FAILED
    assert d.error_message == "kapow"
    assert d.delivered_at is None
    assert w.total_deliveries == 3
    assert w.last_delivery_at == _FIXED
    assert w.last_delivery_status == "failed"
    assert db.flushes == 2
    assert log.recs == [
        (
            "ERROR",
            "Webhook delivery failed unexpectedly: kapow",
            {"webhook_id": _WID, "delivery_id": None, "exc_info": True},
        )
    ]


# ==========================================================================
# trigger_webhooks_for_event
# ==========================================================================


def test_trigger_webhooks_empty() -> None:
    svc = WebhookService()
    db = _DB([[]])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        out = asyncio.run(svc.trigger_webhooks_for_event(db, _Event("alert_fired"), {"d": 1}, "e1"))
    assert out == []
    assert db.executed == [_trigger_sql("alert_fired")]
    assert log.recs == [
        (
            "DEBUG",
            "No webhooks subscribed to event type: alert_fired",
            {"event_type": "alert_fired"},
        )
    ]


def test_trigger_webhooks_string_event() -> None:
    svc = WebhookService()
    db = _DB([[]])
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        out = asyncio.run(svc.trigger_webhooks_for_event(db, "x", {"d": 1}, "e1"))
    assert out == []
    assert db.executed == [_trigger_sql("x")]
    assert log.recs == [("DEBUG", "No webhooks subscribed to event type: x", {"event_type": "x"})]


def test_trigger_webhooks_delivers_each() -> None:
    svc = WebhookService()
    w1 = _webhook(id="h1")
    w2 = _webhook(id="h2")
    db = _DB([[w1, w2]])
    log = _Logger()
    seen: list[Any] = []

    async def _deliver(
        db_: Any, hook: Any, event_type: Any, event_data: Any, event_id: Any = None
    ) -> str:
        seen.append((db_, hook, event_type, event_data, event_id))
        return "d-" + str(hook.id)

    svc.deliver_webhook = _deliver  # type: ignore[method-assign]
    ev = _Event("alert_fired")
    with _Env(logger=log, utc_now=_fixed_now):
        out = asyncio.run(svc.trigger_webhooks_for_event(db, ev, {"d": 1}, "e1"))
    assert out == ["d-h1", "d-h2"]
    assert seen == [
        (db, w1, ev, {"d": 1}, "e1"),
        (db, w2, ev, {"d": 1}, "e1"),
    ]
    assert db.executed == [_trigger_sql("alert_fired")]
    assert log.recs == [
        (
            "INFO",
            "Triggering 2 webhooks for event type: alert_fired",
            {"event_type": "alert_fired", "webhook_count": 2},
        )
    ]


# ==========================================================================
# test_webhook + _build_test_event_data
# ==========================================================================


_TEST_DATA: dict[str, dict[str, Any]] = {
    "alert_fired": {
        "alert_id": "test-alert-001",
        "severity": "high",
        "camera_id": "front_door",
        "description": "Test alert triggered",
    },
    "alert_dismissed": {"alert_id": "test-alert-001"},
    "alert_acknowledged": {"alert_id": "test-alert-001"},
    "event_created": {
        "event_id": "test-event-001",
        "camera_id": "front_door",
        "event_type": "motion_detected",
    },
    "entity_discovered": {
        "entity_id": "test-entity-001",
        "entity_type": "person",
        "label": "Unknown Person",
    },
    "anomaly_detected": {
        "anomaly_id": "test-anomaly-001",
        "zone_id": "driveway",
        "anomaly_type": "unusual_activity",
        "score": 0.87,
    },
    "system_health_changed": {
        "component": "ai-yolo26",
        "status": "degraded",
        "message": "High latency detected",
    },
}


def _test_data(event_type: Any) -> dict[str, Any]:
    spec = _TEST_DATA.get(str(getattr(event_type, "value", event_type)), {})
    return {"test": True, "timestamp": _FIXED_ISO, **spec}


def test_test_webhook_success_battery38() -> None:
    svc = WebhookService()
    hook = _webhook()
    db = _DB([hook])
    fake = _SendSpy(result=(204, "yay", 5))
    with _Env(utc_now=_fixed_now), fake:
        r = asyncio.run(svc.test_webhook(db, _WID, WebhookEventType.ALERT_FIRED))
    assert isinstance(r, WebhookTestResponse)
    assert r.model_dump() == {
        "success": True,
        "status_code": 204,
        "response_time_ms": 5,
        "response_body": "yay",
        "error_message": None,
    }
    assert fake.calls == [(hook, _std_payload("alert_fired", _test_data("alert_fired")))]


def test_test_webhook_matrix() -> None:
    svc = WebhookService()
    for key in _TEST_DATA:
        hook = _webhook()
        db = _DB([hook])
        fake = _SendSpy(result=(200, "y", 5))
        with _Env(utc_now=_fixed_now), fake:
            asyncio.run(svc.test_webhook(db, _WID, WebhookEventType(key)))
        assert fake.calls[0][1] == _std_payload(key, _test_data(key)), key


def test_build_test_event_data_polarities() -> None:
    # direct private calls with NON-StrEnum event objects: the value-branch
    # must be taken (kills the branch-flip family), and a no-.value object
    # must fall back to str (kills the or-True family)
    svc = WebhookService()
    with _Env(utc_now=_fixed_now):
        via_value = svc._build_test_event_data(_Event("alert_fired"))
        via_str = svc._build_test_event_data("alert_fired")
    assert via_value == _test_data("alert_fired")
    assert via_str == _test_data("alert_fired")


def test_test_webhook_missing() -> None:
    svc = WebhookService()
    db = _DB([None])
    with _Env(utc_now=_fixed_now):
        r = asyncio.run(svc.test_webhook(db, _WID, WebhookEventType.ALERT_FIRED))
    assert r.model_dump() == {
        "success": False,
        "status_code": None,
        "response_time_ms": None,
        "response_body": None,
        "error_message": "Webhook not found",
    }
    # the lookup must carry the REAL id (get_webhook(db, None) renders
    # ``id IS NULL`` -- the compiled mirror catches the call-arg flip)
    assert db.executed == [_GET_SQL]


def test_test_webhook_error_arms() -> None:
    svc = WebhookService()
    hook = _webhook()
    et = WebhookEventType.ALERT_FIRED
    db = _DB([hook])
    fake = _SendSpy(result=(404, "nope", 5))
    with _Env(utc_now=_fixed_now), fake:
        r = asyncio.run(svc.test_webhook(db, _WID, et))
    assert r.model_dump() == {
        "success": False,
        "status_code": 404,
        "response_time_ms": 5,
        "response_body": "nope",
        "error_message": "HTTP 404",
    }
    db2 = _DB([hook])
    fake2 = _SendSpy(error=httpx.RequestError("b" * 600))
    with _Env(utc_now=_fixed_now), fake2:
        r2 = asyncio.run(svc.test_webhook(db2, _WID, et))
    assert r2.model_dump() == {
        "success": False,
        "status_code": None,
        "response_time_ms": None,
        "response_body": None,
        "error_message": "b" * 500,
    }
    db3 = _DB([hook])
    # 600-char message + FULL dump: the generic-except arm's success=False
    # and the [:500] cap are both mutants (births m59/m60 of run 1)
    fake3 = _SendSpy(error=RuntimeError("k" * 600))
    with _Env(utc_now=_fixed_now), fake3:
        r3 = asyncio.run(svc.test_webhook(db3, _WID, et))
    assert r3.model_dump() == {
        "success": False,
        "status_code": None,
        "response_time_ms": None,
        "response_body": None,
        "error_message": "Unexpected error: " + "k" * 482,
    }
    db4 = _DB([hook])
    fake4 = _SendSpy(result=(200, "", 5))
    with _Env(utc_now=_fixed_now), fake4:
        r4 = asyncio.run(svc.test_webhook(db4, _WID, et))
    assert r4.response_body is None
    db5 = _DB([hook])
    fake5 = _SendSpy(result=(200, "x" * 2001, 5))
    with _Env(utc_now=_fixed_now), fake5:
        r5 = asyncio.run(svc.test_webhook(db5, _WID, et))
    assert r5.response_body == "x" * 2000


# ==========================================================================
# retry_delivery
# ==========================================================================


def _retryable(**over: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "webhook_id": _WID,
        "request_payload": {"old": True},
        "attempt_count": 1,
        "status": "stale",
        "error_message": "boom",
        "next_retry_at": "stale",
        "status_code": None,
        "response_body": None,
        "response_time_ms": None,
        "delivered_at": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_retry_delivery_success_battery38() -> None:
    svc = WebhookService()
    delivery = _retryable()
    hook = _webhook(total_deliveries=5, successful_deliveries=2)
    db = _DB([delivery, hook])
    fake = _SendSpy(result=(200, "ok-2", 9))
    with _Env(utc_now=_fixed_now), fake:
        out = asyncio.run(svc.retry_delivery(db, "d1"))
    assert out is delivery
    assert db.executed == [_delivery_select_sql("d1"), _GET_SQL]
    assert delivery.attempt_count == 2
    assert delivery.status == SchemaWebhookDeliveryStatus.SUCCESS
    assert delivery.error_message is None
    assert delivery.next_retry_at is None
    assert delivery.status_code == 200
    assert delivery.response_body == "ok-2"
    assert delivery.response_time_ms == 9
    assert delivery.delivered_at == _FIXED
    assert fake.calls == [(hook, {"old": True})]
    assert hook.total_deliveries == 6
    assert hook.successful_deliveries == 3
    assert hook.last_delivery_at == _FIXED
    assert hook.last_delivery_status == "success"
    assert db.flushes == 1
    assert db.refreshed == [delivery]


def test_retry_delivery_http_error() -> None:
    svc = WebhookService()
    delivery = _retryable()
    hook = _webhook(total_deliveries=5, successful_deliveries=2)
    db = _DB([delivery, hook])
    fake = _SendSpy(result=(503, "later", 9))
    with _Env(utc_now=_fixed_now), fake:
        out = asyncio.run(svc.retry_delivery(db, "d1"))
    assert out is delivery
    assert delivery.status == SchemaWebhookDeliveryStatus.FAILED
    assert delivery.status_code == 503
    assert delivery.response_body == "later"
    assert delivery.response_time_ms == 9
    assert delivery.error_message == "HTTP 503"
    assert delivery.delivered_at is None
    assert hook.total_deliveries == 6
    assert hook.successful_deliveries == 2
    assert hook.last_delivery_status == "failed"


def test_retry_delivery_network_error() -> None:
    svc = WebhookService()
    delivery = _retryable()
    hook = _webhook(total_deliveries=5, successful_deliveries=2)
    db = _DB([delivery, hook])
    # 600-char message: the arm's [:500] cap is a run-1 birth (m49)
    fake = _SendSpy(error=httpx.RequestError("d" * 600))
    with _Env(utc_now=_fixed_now), fake:
        out = asyncio.run(svc.retry_delivery(db, "d1"))
    assert out is delivery
    assert delivery.status == SchemaWebhookDeliveryStatus.FAILED
    assert delivery.error_message == "d" * 500
    assert delivery.delivered_at is None
    assert hook.total_deliveries == 6
    assert hook.successful_deliveries == 2
    assert hook.last_delivery_status == "failed"


def test_retry_delivery_missing_rows() -> None:
    svc = WebhookService()
    db0 = _DB([None])
    with _Env(utc_now=_fixed_now):
        assert asyncio.run(svc.retry_delivery(db0, "d1")) is None
    assert db0.executed == [_delivery_select_sql("d1")]
    db1 = _DB([SimpleNamespace(webhook_id=_WID), None])
    with _Env(utc_now=_fixed_now):
        assert asyncio.run(svc.retry_delivery(db1, "d1")) is None
    assert db1.executed == [_delivery_select_sql("d1"), _GET_SQL]


def test_retry_delivery_falsy_payload() -> None:
    svc = WebhookService()
    delivery = _retryable(request_payload=None)
    hook = _webhook()
    db = _DB([delivery, hook])
    fake = _SendSpy(result=(200, "ok", 1))
    with _Env(utc_now=_fixed_now), fake:
        asyncio.run(svc.retry_delivery(db, "d1"))
    assert fake.calls == [(hook, {})]


def test_retry_delivery_propagates_and_resets() -> None:
    # retry_delivery has NO generic except: an unexpected error propagates
    # after the reset block, so the interim state is observable
    svc = WebhookService()
    delivery = _retryable()
    hook = _webhook()
    db = _DB([delivery, hook])
    fake = _SendSpy(error=RuntimeError("nope"))
    raised = False
    try:
        with _Env(utc_now=_fixed_now), fake:
            asyncio.run(svc.retry_delivery(db, "d1"))
    except RuntimeError as e:
        raised = str(e) == "nope"
    assert raised
    assert delivery.attempt_count == 2
    assert delivery.status == SchemaWebhookDeliveryStatus.PENDING
    assert delivery.error_message is None
    assert delivery.next_retry_at is None
    assert fake.calls == [(hook, {"old": True})]
    assert db.flushes == 0


# ==========================================================================
# _build_payload + templates
# ==========================================================================


def test_build_payload_polarities() -> None:
    svc = WebhookService()
    w = _webhook()
    with _Env(utc_now=_fixed_now):
        via_enum = svc._build_payload(w, WebhookEventType.ALERT_FIRED, {"z": 1})
        via_value = svc._build_payload(w, _Event("alert_fired"), {"z": 1})
        via_str = svc._build_payload(w, "x", {"z": 1})
    assert via_enum == _std_payload("alert_fired", {"z": 1})
    assert via_value == _std_payload("alert_fired", {"z": 1})
    assert via_str == _std_payload("x", {"z": 1})


_TEMPLATE = (
    '{"t": {{ event_type|tojson }}, "b": {{ data|tojson }},'
    ' "c": {{ alert_id|tojson }}, "d": {{ webhook_id|tojson }},'
    ' "e": {{ timestamp|tojson }}}'
)


def test_build_payload_template_renders() -> None:
    svc = WebhookService()
    w = _webhook(payload_template=_TEMPLATE)
    with _Env(utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    assert p == {
        "t": "alert_fired",
        "b": {"alert_id": "A"},
        "c": "A",
        "d": _WID,
        "e": _FIXED_ISO,
    }


class _StrictEnv:
    """Fake ``_jinja_env`` asserting the EXACT render kwargs."""

    def __init__(self, expected: dict[str, Any], crash: bool = False) -> None:
        self._expected = expected
        self._crash = crash

    def from_string(self, _src: str) -> _StrictEnv:
        return self

    def render(self, **kw: Any) -> str:
        if self._crash:
            raise ValueError("renderer exploded off the caught list")
        assert kw == self._expected, f"render context drifted: {sorted(kw)}"
        return '{"ok": 1}'


class _BoomEnv:
    def from_string(self, _src: str) -> Any:
        raise ValueError("from_string exploded off the caught list")


def test_build_payload_template_render_context() -> None:
    svc = WebhookService()
    w = _webhook(payload_template="whatever")
    expected = {
        "event_type": "alert_fired",
        "timestamp": _FIXED_ISO,
        "webhook_id": _WID,
        "data": {"alert_id": "A"},
        "alert_id": "A",
    }
    with _Env(_jinja_env=_StrictEnv(expected), utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    assert p == {"ok": 1}


def test_build_payload_template_uncrashed_paths_propagate() -> None:
    svc = WebhookService()
    w = _webhook(payload_template="whatever")
    raised = False
    try:
        with _Env(_jinja_env=_StrictEnv({}, crash=True), utc_now=_fixed_now):
            svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    except ValueError as e:
        raised = str(e).startswith("renderer exploded")
    assert raised
    # a drifted render context raises AssertionError, also outside the
    # module's except tuple -> propagates rather than falling back
    raised_assert = False
    try:
        with _Env(_jinja_env=_StrictEnv({"bogus": 1}), utc_now=_fixed_now):
            svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    except AssertionError:
        raised_assert = True
    assert raised_assert
    raised2 = False
    try:
        with _Env(_jinja_env=_BoomEnv(), utc_now=_fixed_now):
            svc._build_payload(w, _Event("alert_fired"), {"alert_id": "A"})
    except ValueError as e:
        raised2 = str(e).startswith("from_string exploded")
    assert raised2


def test_build_payload_template_json_failure() -> None:
    svc = WebhookService()
    w = _webhook(payload_template='{"not json"}')
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"k": 1})
    assert p == _std_payload("alert_fired", {"k": 1})
    assert log.recs == [
        (
            "WARNING",
            "Failed to render payload template, using standard payload: "
            "Expecting ':' delimiter: line 1 column 12 (char 11)",
            {"webhook_id": _WID},
        )
    ]


def test_build_payload_template_undefined() -> None:
    svc = WebhookService()
    w = _webhook(payload_template="{{ nope.x }}")
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"k": 1})
    assert p == _std_payload("alert_fired", {"k": 1})
    assert log.recs == [
        (
            "WARNING",
            "Failed to render payload template, using standard payload: 'nope' is undefined",
            {"webhook_id": _WID},
        )
    ]


def test_build_payload_template_syntax_error() -> None:
    svc = WebhookService()
    w = _webhook(payload_template="{{ ")
    log = _Logger()
    with _Env(logger=log, utc_now=_fixed_now):
        p = svc._build_payload(w, _Event("alert_fired"), {"k": 1})
    assert p == _std_payload("alert_fired", {"k": 1})
    assert log.recs == [
        (
            "WARNING",
            "Failed to render payload template, using standard payload: "
            "unexpected 'end of template'",
            {"webhook_id": _WID},
        )
    ]


# ==========================================================================
# _format_for_integration + formatters
# ==========================================================================


def test_format_for_integration_routing() -> None:
    svc = WebhookService()
    payload = _std_payload("alert_fired", {"k": 1})
    # _Event has .value but str() != .value: the value-branch must be taken
    slack = svc._format_for_integration(_webhook(integration_type=_Event("slack")), payload)
    assert slack["text"] == "*alert_fired*\n- k: 1\n"
    discord = svc._format_for_integration(_webhook(integration_type=_Event("discord")), payload)
    assert discord["embeds"][0]["title"] == "Alert Fired"
    teams = svc._format_for_integration(_webhook(integration_type=_Event("teams")), payload)
    assert teams["title"] == "Alert Fired"
    assert teams["summary"] == "alert_fired"
    # a real StrEnum routes by .value
    enum_slack = svc._format_for_integration(
        _webhook(integration_type=SchemaIntegrationType.SLACK), payload
    )
    assert enum_slack["text"] == "*alert_fired*\n- k: 1\n"
    # an integration whose resolved name is not a literal falls through
    assert (
        svc._format_for_integration(_webhook(integration_type=_RawIT("nope")), payload) == payload
    )
    assert (
        svc._format_for_integration(
            _webhook(integration_type=SchemaIntegrationType.TELEGRAM), payload
        )
        == payload
    )


def test_format_slack_payload_battery38() -> None:
    svc = WebhookService()
    out = svc._format_slack_payload(
        {
            "event_type": "e2",
            "data": {
                "s": "str",
                "i": 7,
                "f": 2.5,
                "b": False,
                "d": {"x": 1},
                "li": [1],
                "n": None,
            },
        }
    )
    text = "*e2*\n- s: str\n- i: 7\n- f: 2.5\n- b: False\n"
    assert out == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }


def test_format_discord_payload_battery38() -> None:
    svc = WebhookService()
    data = {f"k{i}": i for i in range(30)}
    d = svc._format_discord_payload({"event_type": "alert_fired", "timestamp": "TS", "data": data})
    assert d == {
        "embeds": [
            {
                "title": "Alert Fired",
                "timestamp": "TS",
                "fields": [
                    {"name": "K" + str(i), "value": str(i), "inline": True} for i in range(25)
                ],
            }
        ]
    }
    with _Env(utc_now=_fixed_now):
        mixed = svc._format_discord_payload(
            {
                "event_type": "e",
                "data": {"s": "v", "i": 1, "f": 2.0, "b": True, "x": {}, "y": []},
            }
        )
    assert mixed["embeds"][0]["fields"] == [
        {"name": "S", "value": "v", "inline": True},
        {"name": "I", "value": "1", "inline": True},
        {"name": "F", "value": "2.0", "inline": True},
        {"name": "B", "value": "True", "inline": True},
    ]
    assert mixed["embeds"][0]["timestamp"] == _FIXED_ISO


def test_format_teams_payload_battery38() -> None:
    svc = WebhookService()
    data = {f"k{i}": i for i in range(30)}
    t = svc._format_teams_payload({"event_type": "alert_fired", "data": data})
    assert t == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "alert_fired",
        "themeColor": "0076D7",
        "title": "Alert Fired",
        "sections": [{"facts": [{"title": "K" + str(i), "value": str(i)} for i in range(10)]}],
    }
    mixed = svc._format_teams_payload(
        {"event_type": "e", "data": {"s": "v", "i": 1, "f": 2.0, "b": True, "x": {}}}
    )
    assert mixed["sections"][0]["facts"] == [
        {"title": "S", "value": "v"},
        {"title": "I", "value": "1"},
        {"title": "F", "value": "2.0"},
        {"title": "B", "value": "True"},
    ]


# ==========================================================================
# _sign_payload
# ==========================================================================


def test_sign_payload_exact() -> None:
    svc = WebhookService()
    payload = {"b": 2, "a": 1}
    want = _hmac_sig(payload, _SIG_SECRET)
    assert svc._sign_payload(payload, _SIG_SECRET) == want
    assert svc._sign_payload({"a": 1, "b": 2}, _SIG_SECRET) == want


# ==========================================================================
# _send_request (real httpx over a recording transport)
# ==========================================================================


class _CaptureTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.seen: list[Any] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(
            (
                request.method,
                str(request.url),
                dict(request.headers),
                request.content.decode(),
            )
        )
        return httpx.Response(200, text="R")


def _fake_httpx(transport: _CaptureTransport) -> ModuleType:
    fake = ModuleType("httpx")

    class Client(httpx.AsyncClient):
        def __init__(self, *args: Any, **kw: Any) -> None:
            kw["transport"] = transport
            super().__init__(*args, **kw)

    fake.AsyncClient = Client
    fake.RequestError = httpx.RequestError
    return fake


def _fake_pinned_client(transport: _CaptureTransport):
    """Stub ``pinned_httpx_client`` for the hostname send path.

    F12 moved the hostname path through the shared pinning transport in
    backend.core.url_validation, whose own ``httpx`` import the ``_Env(httpx=
    …)`` swap cannot reach. These tests pin nothing — headers, auth and
    timing are the measured surface — so the stub connects straight through
    the capture transport. The pinning behaviour has its own tests
    (test_url_validation / test_channel_adapters).
    """

    def _build(url: str, pinned_ip: str, *, timeout: float):
        return httpx.AsyncClient(timeout=timeout, transport=transport)

    return _build


_BASIC_ABSENT = base64.b64encode(b":").decode()

_MATRIX: list[tuple[str, dict[str, Any], dict[str, str]]] = [
    ("none", {"type": "none"}, {}),
    ("bearer-full", {"type": "bearer", "token": "tk"}, {"authorization": "Bearer tk"}),
    (
        "basic-full",
        {"type": "basic", "username": "u1", "password": "p1"},  # pragma: allowlist secret
        {"authorization": "Basic " + base64.b64encode(b"u1:p1").decode()},
    ),
    (
        "header-full",
        {"type": "header", "header_name": "X-Key", "header_value": "hv"},
        {"x-key": "hv"},
    ),
    ("unknown", {"type": "weird"}, {}),
    ("empty", {}, {}),
    ("no-type-key", {"token": "tk"}, {}),
    ("bearer-absent-token", {"type": "bearer"}, {"authorization": "Bearer "}),
    ("basic-absent", {"type": "basic"}, {"authorization": "Basic " + _BASIC_ABSENT}),
    ("header-absent-name", {"type": "header"}, {}),
    ("header-empty-name", {"type": "header", "header_name": "", "header_value": "hv"}, {}),
    ("header-name-only", {"type": "header", "header_name": "X-Key"}, {"x-key": ""}),
    ("header-empty-both", {"type": "header", "header_name": "", "header_value": ""}, {}),
]


def test_send_request_auth_matrix() -> None:
    svc = WebhookService()
    payload = {"b": 2, "a": 1}
    sig = _hmac_sig(payload, _SIG_SECRET)
    for label, auth, auth_hdrs in _MATRIX:
        transport = _CaptureTransport()
        w = _webhook(
            auth_config=auth,
            custom_headers={"X-C": "c1"},
            signing_secret=_SIG_SECRET,
        )
        with _Env(
            httpx=_fake_httpx(transport),
            pinned_httpx_client=_fake_pinned_client(transport),
            utc_now=_fixed_now,
            datetime=_FixedDT,
        ):
            out = asyncio.run(svc._send_request(w, payload))
        assert out == (200, "R", 0), label
        method, url, headers, content = transport.seen[-1]
        assert method == "POST", label
        assert url == _URL, label
        assert json.loads(content) == payload, label
        expected = {
            # httpx defaults (measured on the pinned version)
            "host": "x.test",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate",
            "connection": "keep-alive",
            # set by the module under test
            "content-type": "application/json",
            "user-agent": "NemotronWebhook/1.0",
            "content-length": str(len(content)),
            "x-c": "c1",
            "x-webhook-signature": "sha256=" + sig,
            "x-webhook-signature-256": sig,
        }
        expected.update(auth_hdrs)
        assert headers == expected, label


def test_send_request_bare_request() -> None:
    svc = WebhookService()
    payload = {"x": "y"}
    transport = _CaptureTransport()
    w = _webhook(auth_config=None, custom_headers=None, signing_secret=None)
    with _Env(
        httpx=_fake_httpx(transport),
        pinned_httpx_client=_fake_pinned_client(transport),
        utc_now=_fixed_now,
        datetime=_FixedDT,
    ):
        out = asyncio.run(svc._send_request(w, payload))
    assert out == (200, "R", 0)
    _method, _url, headers, content = transport.seen[-1]
    assert headers == {
        "host": "x.test",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate",
        "connection": "keep-alive",
        "content-type": "application/json",
        "user-agent": "NemotronWebhook/1.0",
        "content-length": str(len(content)),
    }


# ==========================================================================
# _calculate_next_retry
# ==========================================================================


def test_calculate_next_retry_backoff() -> None:
    svc = WebhookService()
    cases = [
        (1, 10, 10),
        (2, 10, 20),
        (3, 10, 40),
        (6, 10, 320),
        (30, 10, 3600),
        (1, 3600, 3600),
        (4, 1, 8),
    ]
    for attempt, base, delay in cases:
        with _Env(utc_now=_fixed_now):
            got = svc._calculate_next_retry(attempt, base)
        assert got == _FIXED + timedelta(seconds=delay), (attempt, base)


# ==========================================================================
# get_health_summary
# ==========================================================================


def _health_mirrors() -> list[str]:
    cutoff = _FIXED - timedelta(hours=24)
    return [
        _sql_b38x(select(func.count()).select_from(OutboundWebhook)),
        _sql_b38x(
            select(func.count())
            .select_from(OutboundWebhook)
            .where(OutboundWebhook.enabled.is_(True))
        ),
        _sql_b38x(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.created_at >= cutoff)
        ),
        _sql_b38x(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.status == SchemaWebhookDeliveryStatus.SUCCESS,
                )
            )
        ),
        _sql_b38x(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.status == SchemaWebhookDeliveryStatus.FAILED,
                )
            )
        ),
        _sql_b38x(
            select(func.avg(WebhookDelivery.response_time_ms)).where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.response_time_ms.is_not(None),
                )
            )
        ),
        _sql_b38x(select(OutboundWebhook).order_by(OutboundWebhook.created_at.desc())),
    ]


def _run_health(rows: list[Any], results: list[Any]) -> tuple[Any, _DB]:
    db = _DB(results)
    svc = WebhookService()
    with _Env(utc_now=_fixed_now):
        h = asyncio.run(svc.get_health_summary(db))
    return h, db


def test_get_health_summary_exact() -> None:
    rows = [
        _webhook(total_deliveries=10, successful_deliveries=9),
        _webhook(total_deliveries=10, successful_deliveries=8),
        _webhook(total_deliveries=10, successful_deliveries=5),
        _webhook(total_deliveries=10, successful_deliveries=4),
        _webhook(total_deliveries=1, successful_deliveries=0),
        _webhook(total_deliveries=0, successful_deliveries=0),
        _webhook(total_deliveries=20, successful_deliveries=20),
    ]
    h, db = _run_health(rows, [7, 3, 11, 8, 2, 42.5, rows])
    assert h == WebhookHealthSummary(
        total_webhooks=7,
        enabled_webhooks=3,
        healthy_webhooks=2,
        unhealthy_webhooks=2,
        total_deliveries_24h=11,
        successful_deliveries_24h=8,
        failed_deliveries_24h=2,
        average_response_time_ms=42.5,
    )
    assert db.executed == _health_mirrors()
    assert db.flushes == 0


def test_get_health_summary_zero_counts_and_none_avg() -> None:
    rows = [_webhook(total_deliveries=10, successful_deliveries=9)]
    h, db = _run_health(rows, [0, 0, 0, 0, 0, None, rows])
    assert h == WebhookHealthSummary(
        total_webhooks=0,
        enabled_webhooks=0,
        healthy_webhooks=1,
        unhealthy_webhooks=0,
        total_deliveries_24h=0,
        successful_deliveries_24h=0,
        failed_deliveries_24h=0,
        average_response_time_ms=None,
    )
    assert db.executed == _health_mirrors()


# ==========================================================================
# B4.2 / ruling 310 — F12 destination policy on outbound webhooks (#7336)
#
# The binding's test list: loopback/link-local/metadata URL → 422; a private
# address passes only with the webhook's on_local_network flag; send-time
# validation is exercised through the pinned-client construction below.
# The 422s are asserted at BOTH schema layers (create/update) and the
# service (the authoritative check), because the API returns 422 only when
# the pydantic layer refuses.
# ==========================================================================


# Loopback, link-local and cloud metadata stay refused for EVERY webhook,
# with or without the flag — these strings are the same ones the binding
# names and the url_validation suite blocks.
_ALWAYS_BLOCKED = [
    "https://127.0.0.1/hook",  # loopback (IPv4)
    "https://[::1]/hook",  # loopback (IPv6)
    "https://169.254.10.10/hook",  # link-local (IPv4)
    "https://[fe80::5]/hook",  # link-local (IPv6)
    "https://169.254.169.254/latest/meta-data/",  # AWS metadata endpoint
    "http://metadata.google.internal/computeMetadata",  # GCP metadata host
]

# RFC1918 / unique-local targets and plain HTTP: refused without the flag,
# accepted once the webhook carries the on-this-network allowance.
_FLAG_GATED = [
    "https://192.168.1.50/hook",
    "https://10.0.0.5/hook",
    "https://[fd00::5]/hook",
    "http://192.168.1.50/hook",  # plain HTTP on the LAN
    "https://nas.lan/hook",  # internal domain suffix
]


def _try_create(url: str, **kw: Any) -> str | None:
    """WebhookCreate's rejection reason, or None when it constructs."""
    try:
        WebhookCreate(name="N", url=url, event_types=["alert_fired"], **kw)
    except ValidationError as exc:
        return str(exc.errors()[0]["msg"])
    return None


def _try_update(url: str, **kw: Any) -> str | None:
    try:
        WebhookUpdate(url=url, **kw)
    except ValidationError as exc:
        return str(exc.errors()[0]["msg"])
    return None


@pytest.mark.parametrize("url", _ALWAYS_BLOCKED)
@pytest.mark.parametrize("flag", [False, True], ids=["no-flag", "flag"])
def test_f12_schema_create_blocks_loopback_metadata_linklocal(url: str, flag: bool) -> None:
    """Create 422s loopback / link-local / metadata with or without the flag."""
    reason = _try_create(url, on_local_network=flag)
    assert reason is not None, f"create accepted {url} (flag={flag})"


@pytest.mark.parametrize("url", _ALWAYS_BLOCKED)
@pytest.mark.parametrize("flag", [False, True], ids=["no-flag", "flag"])
def test_f12_schema_update_blocks_loopback_metadata_linklocal(url: str, flag: bool) -> None:
    """Update 422s the always-blocked set with or without the flag."""
    reason = _try_update(url, on_local_network=flag)
    assert reason is not None, f"update accepted {url} (flag={flag})"


@pytest.mark.parametrize("url", _FLAG_GATED)
def test_f12_schema_create_refuses_private_without_flag(url: str) -> None:
    """A private address / LAN name / plain HTTP 422s at create by default."""
    assert _try_create(url) is not None, f"create accepted {url} without the flag"


@pytest.mark.parametrize("url", _FLAG_GATED)
def test_f12_schema_create_allows_private_with_flag(url: str) -> None:
    """The same set passes create once on_local_network is set."""
    assert _try_create(url, on_local_network=True) is None


@pytest.mark.parametrize("url", _FLAG_GATED)
def test_f12_schema_update_flag_is_effective(url: str) -> None:
    """Update validates under the request's own flag: granting the flag and
    naming the LAN host in the same request passes, refusing it does not."""
    assert _try_update(url, on_local_network=True) is None
    assert _try_update(url, on_local_network=False) is not None


@pytest.mark.asyncio
async def test_f12_service_create_authoritative_check(webhook_service, mock_db_session):
    """The service's own policy check runs with the request's flag in hand —
    a private URL constructs only when on_local_network rides along."""
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    # Flagged private URL: accepted end to end, flag stored.
    data = WebhookCreate(
        name="LAN hook",
        url="https://192.168.1.50/hook",
        event_types=[WebhookEventType.ALERT_FIRED],
        on_local_network=True,
    )
    webhook = await webhook_service.create_webhook(mock_db_session, data)
    assert webhook.on_local_network is True
    assert webhook.url == "https://192.168.1.50/hook"

    # Unflagged private URL: the service refuses even though the schema
    # would have (defense in depth — the schema's model_validator already
    # 422s this; model_construct bypasses validators, the service does not).
    smuggled = WebhookCreate.model_construct(
        name="Smuggled",
        url="https://192.168.1.50/hook",
        event_types=["alert_fired"],
        on_local_network=False,
    )
    with pytest.raises(SSRFValidationError):
        await webhook_service.create_webhook(mock_db_session, smuggled)


@pytest.mark.asyncio
async def test_f12_service_update_effective_flag(webhook_service, mock_db_session):
    """update_webhook validates the new URL under the EFFECTIVE flag — the
    request's flag when it sets one, the stored flag when it does not."""
    hook = webhook(on_local_network=True)  # stored flag is set
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))

    # Same-request grant + LAN URL: allowed.
    data = WebhookUpdate.model_construct(url="https://192.168.1.51/hook", on_local_network=True)
    await webhook_service.update_webhook(mock_db_session, WID, data)
    assert hook.url == "https://192.168.1.51/hook"
    assert hook.on_local_network is True

    # Dropping the flag while the private URL stands is refused.
    data = WebhookUpdate.model_construct(url="https://192.168.1.52/hook", on_local_network=False)
    with pytest.raises(SSRFValidationError):
        await webhook_service.update_webhook(mock_db_session, WID, data)

    # No flag in the request: the stored flag governs (LAN URL stays legal).
    data = WebhookUpdate.model_construct(url="https://192.168.1.53/hook")
    await webhook_service.update_webhook(mock_db_session, WID, data)
    assert hook.url == "https://192.168.1.53/hook"
    assert hook.on_local_network is True


@pytest.mark.asyncio
async def test_f12_send_time_policy_refuses_metadata_and_records_failure(
    webhook_service, mock_db_session
):
    """Send time re-validates: a webhook whose URL resolves to a blocked
    address fails the delivery WITHOUT scheduling a retry."""
    hook = webhook(url="http://169.254.169.254/latest/meta-data/")
    delivery = WebhookDelivery(
        id=str(uuid4()),
        webhook_id=hook.id,
        event_type=WebhookEventType.ALERT_FIRED.value,
        status=WebhookDeliveryStatus.FAILED,
        request_payload={"test": True},
        attempt_count=1,
    )
    mock_delivery_result = MagicMock()
    mock_delivery_result.scalar_one_or_none.return_value = delivery
    mock_webhook_result = MagicMock()
    mock_webhook_result.scalar_one_or_none.return_value = hook
    mock_db_session.execute = AsyncMock(side_effect=[mock_delivery_result, mock_webhook_result])
    mock_db_session.flush = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    await webhook_service.retry_delivery(mock_db_session, delivery.id)

    assert delivery.status == WebhookDeliveryStatus.FAILED
    assert "url_policy" in (delivery.error_message or "")
    assert delivery.next_retry_at is None  # no retry scheduled
    assert hook.last_delivery_status == WebhookDeliveryStatus.FAILED.value


@pytest.mark.asyncio
async def test_f12_send_time_pins_hostname_to_validated_address(webhook_service):
    """A hostname URL's client carries the pinning transport: the send goes
    through _PinnedResolver, which re-resolves and refuses to dial anything
    but the validated address (F12 — DNS rebinding cannot win)."""
    spy = ClientSpy(status_code=200, text="ok")
    with (
        patch.object(httpx, "AsyncClient", spy),
        patch.object(uv, "resolve_hostname", lambda host: ["93.184.216.34"]),  # noqa: ARG005
        patch.object(uv.httpx, "AsyncHTTPTransport", lambda *a, **k: object()),  # noqa: ARG005
    ):
        await webhook_service._send_request(webhook(), P1)

    # One client, built with the pinning transport wrapper.
    assert len(spy.constructor_kwargs) == 1
    transport = spy.constructor_kwargs[0]["transport"]
    assert isinstance(transport, uv._PinnedResolver)
    assert transport._pinned_ip == "93.184.216.34"
    assert transport._hostname == "x.test"


@pytest.mark.asyncio
async def test_f12_send_time_literal_ip_needs_no_pin(webhook_service):
    """A literal-IP URL dials a plain client — validation already saw the
    address it will connect to, so there is nothing to pin."""
    spy = ClientSpy(status_code=200, text="ok")
    hook = webhook(url="https://93.184.216.34/hook", on_local_network=True)
    with patch.object(httpx, "AsyncClient", spy):
        await webhook_service._send_request(hook, P1)

    assert spy.constructor_kwargs == [{"timeout": DEFAULT_TIMEOUT}]
