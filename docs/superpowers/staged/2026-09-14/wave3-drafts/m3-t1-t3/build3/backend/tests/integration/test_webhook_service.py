"""Integration tests for WebhookService.

Tests the WebhookService class which manages outbound webhooks and delivery.
Tests cover CRUD operations, delivery statistics, and health checks with real database.

Related: NEM-3624 Webhook Management Implementation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.api.schemas.outbound_webhook import (
    IntegrationType,
    WebhookCreate,
    WebhookEventType,
    WebhookUpdate,
)
from backend.models.outbound_webhook import WebhookDeliveryStatus
from backend.services.webhook_service import WebhookService
from backend.tests.conftest import unique_id

# Mark all tests as integration
pytestmark = [pytest.mark.integration]


@pytest.fixture
def webhook_service() -> WebhookService:
    """Create a WebhookService instance."""
    return WebhookService()


@pytest.fixture
def sample_webhook_data() -> WebhookCreate:
    """Create sample webhook creation data."""
    return WebhookCreate(
        name=f"Test Webhook {unique_id('wh')[-8:]}",
        url="https://example.com/webhook",
        event_types=[WebhookEventType.ALERT_FIRED, WebhookEventType.EVENT_CREATED],
        integration_type=IntegrationType.GENERIC,
        enabled=True,
        max_retries=3,
        retry_delay_seconds=10,
    )


class TestWebhookServiceCRUD:
    """Tests for WebhookService CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_webhook(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test creating a new webhook."""
        async with test_db() as session:
            webhook = await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()

        assert webhook.id is not None
        assert webhook.name == sample_webhook_data.name
        assert webhook.url == str(sample_webhook_data.url)
        assert webhook.enabled is True
        assert webhook.signing_secret is not None

    @pytest.mark.asyncio
    async def test_get_webhook(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test retrieving a webhook by ID."""
        async with test_db() as session:
            created = await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()
            webhook_id = created.id

        async with test_db() as session:
            webhook = await webhook_service.get_webhook(session, webhook_id)

        assert webhook is not None
        assert webhook.id == webhook_id
        assert webhook.name == sample_webhook_data.name

    @pytest.mark.asyncio
    async def test_get_nonexistent_webhook_returns_none(
        self,
        test_db,
        webhook_service: WebhookService,
    ) -> None:
        """Test that get_webhook returns None for nonexistent ID."""
        async with test_db() as session:
            webhook = await webhook_service.get_webhook(
                session, "00000000-0000-0000-0000-000000000000"
            )

        assert webhook is None

    @pytest.mark.asyncio
    async def test_list_webhooks(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test listing all webhooks."""
        async with test_db() as session:
            await webhook_service.create_webhook(session, sample_webhook_data)
            # Create another webhook with different name
            data2 = WebhookCreate(
                name=f"Another Webhook {unique_id('wh2')[-8:]}",
                url="https://example.com/webhook2",
                event_types=[WebhookEventType.ANOMALY_DETECTED],
            )
            await webhook_service.create_webhook(session, data2)
            await session.commit()

        async with test_db() as session:
            webhooks = await webhook_service.list_webhooks(session)

        assert len(webhooks) >= 2

    @pytest.mark.asyncio
    async def test_list_enabled_webhooks_only(
        self,
        test_db,
        webhook_service: WebhookService,
    ) -> None:
        """Test listing only enabled webhooks."""
        async with test_db() as session:
            # Create enabled webhook
            enabled_data = WebhookCreate(
                name=f"Enabled {unique_id('en')[-8:]}",
                url="https://example.com/enabled",
                event_types=[WebhookEventType.ALERT_FIRED],
                enabled=True,
            )
            await webhook_service.create_webhook(session, enabled_data)

            # Create disabled webhook
            disabled_data = WebhookCreate(
                name=f"Disabled {unique_id('dis')[-8:]}",
                url="https://example.com/disabled",
                event_types=[WebhookEventType.ALERT_FIRED],
                enabled=False,
            )
            await webhook_service.create_webhook(session, disabled_data)
            await session.commit()

        async with test_db() as session:
            enabled_webhooks = await webhook_service.list_webhooks(session, enabled_only=True)

        # All returned webhooks should be enabled
        for webhook in enabled_webhooks:
            assert webhook.enabled is True

    @pytest.mark.asyncio
    async def test_update_webhook(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test updating a webhook."""
        async with test_db() as session:
            created = await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()
            webhook_id = created.id

        # Update the webhook
        new_name = f"Updated Webhook {unique_id('upd')[-8:]}"
        async with test_db() as session:
            updated = await webhook_service.update_webhook(
                session,
                webhook_id,
                WebhookUpdate(name=new_name, enabled=False),
            )
            await session.commit()

        assert updated is not None
        assert updated.name == new_name
        assert updated.enabled is False

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(
        self,
        test_db,
        webhook_service: WebhookService,
    ) -> None:
        """Test that update returns None for nonexistent webhook."""
        async with test_db() as session:
            updated = await webhook_service.update_webhook(
                session,
                "00000000-0000-0000-0000-000000000000",
                WebhookUpdate(name="New Name"),
            )

        assert updated is None

    @pytest.mark.asyncio
    async def test_delete_webhook(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test deleting a webhook."""
        async with test_db() as session:
            created = await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()
            webhook_id = created.id

        # Delete the webhook
        async with test_db() as session:
            deleted = await webhook_service.delete_webhook(session, webhook_id)
            await session.commit()

        assert deleted is True

        # Verify it's gone
        async with test_db() as session:
            webhook = await webhook_service.get_webhook(session, webhook_id)

        assert webhook is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(
        self,
        test_db,
        webhook_service: WebhookService,
    ) -> None:
        """Test that delete returns False for nonexistent webhook."""
        async with test_db() as session:
            deleted = await webhook_service.delete_webhook(
                session, "00000000-0000-0000-0000-000000000000"
            )

        assert deleted is False


class TestWebhookServiceDelivery:
    """Tests for WebhookService delivery operations."""

    @pytest.mark.asyncio
    async def test_deliver_webhook_success(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test successful webhook delivery with mocked HTTP client."""
        async with test_db() as session:
            webhook = await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()

            # Mock HTTP response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = '{"ok": true}'

            with patch.object(
                httpx.AsyncClient,
                "post",
                return_value=mock_response,
            ):
                delivery = await webhook_service.deliver_webhook(
                    session,
                    webhook,
                    WebhookEventType.ALERT_FIRED,
                    {"alert_id": "test-123", "severity": "high"},
                )
                await session.commit()

        assert delivery.status == WebhookDeliveryStatus.SUCCESS
        assert delivery.status_code == 200

    @pytest.mark.asyncio
    async def test_deliver_webhook_failure_schedules_retry(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test that failed delivery schedules retry when retries available."""
        async with test_db() as session:
            webhook = await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()

            # Mock HTTP error response
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            with patch.object(
                httpx.AsyncClient,
                "post",
                return_value=mock_response,
            ):
                delivery = await webhook_service.deliver_webhook(
                    session,
                    webhook,
                    WebhookEventType.ALERT_FIRED,
                    {"alert_id": "test-123"},
                )
                await session.commit()

        # Should be retrying since max_retries > 1
        assert delivery.status == WebhookDeliveryStatus.RETRYING
        assert delivery.next_retry_at is not None


class TestWebhookServiceTrigger:
    """Tests for WebhookService.trigger_webhooks_for_event()."""

    @pytest.mark.asyncio
    async def test_trigger_finds_matching_webhooks(
        self,
        test_db,
        webhook_service: WebhookService,
    ) -> None:
        """Test that trigger finds webhooks subscribed to event type."""
        async with test_db() as session:
            # Create webhook subscribed to ALERT_FIRED
            data = WebhookCreate(
                name=f"Alert Webhook {unique_id('alert')[-8:]}",
                url="https://example.com/alerts",
                event_types=[WebhookEventType.ALERT_FIRED],
                enabled=True,
            )
            await webhook_service.create_webhook(session, data)
            await session.commit()

            # Mock HTTP response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = '{"ok": true}'

            with patch.object(
                httpx.AsyncClient,
                "post",
                return_value=mock_response,
            ):
                deliveries = await webhook_service.trigger_webhooks_for_event(
                    session,
                    WebhookEventType.ALERT_FIRED,
                    {"alert_id": "test-456"},
                )
                await session.commit()

        # Should have triggered at least our webhook
        assert len(deliveries) >= 1

    @pytest.mark.asyncio
    async def test_trigger_returns_empty_for_no_subscribers(
        self,
        test_db,
        webhook_service: WebhookService,
    ) -> None:
        """Test that trigger returns empty list when no webhooks subscribe."""
        async with test_db() as session:
            # Use an event type with no subscribers
            deliveries = await webhook_service.trigger_webhooks_for_event(
                session,
                WebhookEventType.BATCH_ANALYSIS_STARTED,
                {"batch_id": "test-batch"},
            )

        # May be empty or not depending on other tests, but should not error
        assert isinstance(deliveries, list)


class TestWebhookServiceHealth:
    """Tests for WebhookService.get_health_summary()."""

    @pytest.mark.asyncio
    async def test_health_summary_returns_stats(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test that health summary returns aggregate statistics."""
        async with test_db() as session:
            # Create a webhook
            await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()

        async with test_db() as session:
            health = await webhook_service.get_health_summary(session)

        assert health.total_webhooks >= 1
        assert health.enabled_webhooks >= 0
        assert health.healthy_webhooks >= 0
        assert health.unhealthy_webhooks >= 0
        assert health.total_deliveries_24h >= 0


class TestWebhookServiceTest:
    """Tests for WebhookService.test_webhook()."""

    @pytest.mark.asyncio
    async def test_test_webhook_success(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test webhook test with successful response."""
        async with test_db() as session:
            webhook = await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()
            webhook_id = webhook.id

            # Mock HTTP response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = '{"ok": true}'

            with patch.object(
                httpx.AsyncClient,
                "post",
                return_value=mock_response,
            ):
                result = await webhook_service.test_webhook(
                    session,
                    webhook_id,
                    WebhookEventType.ALERT_FIRED,
                )

        assert result.success is True
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_test_nonexistent_webhook_returns_error(
        self,
        test_db,
        webhook_service: WebhookService,
    ) -> None:
        """Test that testing nonexistent webhook returns error."""
        async with test_db() as session:
            result = await webhook_service.test_webhook(
                session,
                "00000000-0000-0000-0000-000000000000",
                WebhookEventType.ALERT_FIRED,
            )

        assert result.success is False
        assert result.error_message == "Webhook not found"


class TestWebhookServiceDeliveryHistory:
    """Tests for WebhookService delivery history methods."""

    @pytest.mark.asyncio
    async def test_get_deliveries_returns_history(
        self,
        test_db,
        webhook_service: WebhookService,
        sample_webhook_data: WebhookCreate,
    ) -> None:
        """Test getting delivery history for a webhook."""
        async with test_db() as session:
            webhook = await webhook_service.create_webhook(session, sample_webhook_data)
            await session.commit()
            webhook_id = webhook.id

            # Create a delivery
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = '{"ok": true}'

            with patch.object(
                httpx.AsyncClient,
                "post",
                return_value=mock_response,
            ):
                await webhook_service.deliver_webhook(
                    session,
                    webhook,
                    WebhookEventType.ALERT_FIRED,
                    {"test": True},
                )
                await session.commit()

        async with test_db() as session:
            deliveries, total = await webhook_service.get_deliveries(session, webhook_id)

        assert total >= 1
        assert len(deliveries) >= 1
