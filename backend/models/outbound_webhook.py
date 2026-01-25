"""OutboundWebhook and WebhookDelivery models for outbound webhook management.

This module defines the data models for managing outbound webhooks and tracking
their delivery attempts. Outbound webhooks send notifications to external systems
(e.g., Slack, Discord, Telegram) when events occur in the system.

Note: The existing backend/api/routes/webhooks.py handles INCOMING webhooks
from Alertmanager. This module is for OUTBOUND webhook management.

Webhook Event Types:
    - alert_fired: Alert was triggered
    - alert_dismissed: Alert was dismissed
    - alert_acknowledged: Alert was acknowledged
    - event_created: Security event was created
    - event_enriched: Event was enriched with AI analysis
    - entity_discovered: New entity was discovered
    - anomaly_detected: Anomaly was detected
    - system_health_changed: System health status changed

Delivery Status Flow:
    pending -> success
           -> failed
           -> retrying -> success
                       -> failed (after max retries)

Usage:
    Webhooks are configured by users and triggered by the WebhookService
    when relevant events occur. The service creates WebhookDelivery records
    to track each delivery attempt and handles retries with exponential backoff.
"""

from datetime import datetime
from enum import StrEnum, auto
from uuid import uuid7

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base


class WebhookEventType(StrEnum):
    """Event types that can trigger webhooks.

    These event types correspond to significant system events that users
    may want to receive notifications about in external systems.
    """

    ALERT_FIRED = "alert_fired"
    ALERT_DISMISSED = "alert_dismissed"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    EVENT_CREATED = "event_created"
    EVENT_ENRICHED = "event_enriched"
    ENTITY_DISCOVERED = "entity_discovered"
    ANOMALY_DETECTED = "anomaly_detected"
    SYSTEM_HEALTH_CHANGED = "system_health_changed"


class WebhookDeliveryStatus(StrEnum):
    """Webhook delivery attempt status.

    Tracks the state of each delivery attempt through its lifecycle.
    """

    PENDING = auto()
    SUCCESS = auto()
    FAILED = auto()
    RETRYING = auto()


class IntegrationType(StrEnum):
    """Pre-built integration types.

    Determines payload formatting for specific platforms.
    """

    GENERIC = "generic"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    TEAMS = "teams"


class OutboundWebhook(Base):
    """Model for outbound webhook configurations.

    Stores the configuration for webhooks that send notifications to external
    systems. Each webhook can subscribe to multiple event types and includes
    authentication, retry, and payload template settings.

    Attributes:
        id: Unique identifier (UUID7).
        name: Human-readable name for the webhook.
        url: Target URL for webhook delivery.
        event_types: List of event types that trigger this webhook.
        integration_type: Type of integration for payload formatting.
        enabled: Whether the webhook is active.
        auth_config: Authentication configuration (JSON).
        custom_headers: Additional HTTP headers (JSON).
        payload_template: Jinja2 template for custom payload.
        max_retries: Maximum retry attempts on failure.
        retry_delay_seconds: Initial delay between retries.
        signing_secret: HMAC secret for payload signing.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        total_deliveries: Total delivery attempts (denormalized).
        successful_deliveries: Successful delivery count (denormalized).
        last_delivery_at: Timestamp of last delivery.
        last_delivery_status: Status of last delivery.
        deliveries: Related delivery records.
    """

    __tablename__ = "outbound_webhooks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)

    event_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
    )

    integration_type: Mapped[IntegrationType] = mapped_column(
        Enum(
            IntegrationType,
            name="integration_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=IntegrationType.GENERIC,
    )

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Auth config stored as JSON
    auth_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    custom_headers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    payload_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retry configuration
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # HMAC secret for signing (auto-generated)
    signing_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Stats (denormalized for performance)
    total_deliveries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_deliveries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_delivery_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    deliveries: Mapped[list[WebhookDelivery]] = relationship(
        "WebhookDelivery",
        back_populates="webhook",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_outbound_webhooks_enabled", "enabled"),
        Index("idx_outbound_webhooks_event_types", "event_types", postgresql_using="gin"),
        CheckConstraint("max_retries >= 0 AND max_retries <= 10", name="ck_webhook_max_retries"),
        CheckConstraint("retry_delay_seconds >= 1", name="ck_webhook_retry_delay"),
    )

    @property
    def success_rate(self) -> float | None:
        """Calculate the webhook's success rate.

        Returns:
            Success rate as a percentage (0-100), or None if no deliveries.
        """
        if self.total_deliveries == 0:
            return None
        return (self.successful_deliveries / self.total_deliveries) * 100

    @property
    def is_healthy(self) -> bool:
        """Check if the webhook is healthy (>90% success rate).

        Returns:
            True if success rate is above 90% or no deliveries yet.
        """
        rate = self.success_rate
        return rate is None or rate >= 90.0

    def __repr__(self) -> str:
        return (
            f"<OutboundWebhook(id={self.id!r}, name={self.name!r}, "
            f"enabled={self.enabled}, events={len(self.event_types)})>"
        )


class WebhookDelivery(Base):
    """Model for tracking webhook delivery attempts.

    Records each attempt to deliver a webhook notification, including
    the request payload, response details, and retry information.

    Attributes:
        id: Unique identifier (UUID7).
        webhook_id: Parent webhook ID.
        event_type: Event that triggered this delivery.
        event_id: ID of the related event (if applicable).
        status: Current delivery status.
        status_code: HTTP response status code.
        response_time_ms: Response time in milliseconds.
        response_body: Response body (truncated for storage).
        error_message: Error message if delivery failed.
        request_payload: Request payload sent (for debugging).
        attempt_count: Number of delivery attempts.
        next_retry_at: Scheduled time for next retry.
        created_at: Record creation timestamp.
        delivered_at: Successful delivery timestamp.
        webhook: Parent webhook relationship.
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    webhook_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("outbound_webhooks.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)

    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        Enum(
            WebhookDeliveryStatus,
            name="webhook_delivery_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=WebhookDeliveryStatus.PENDING,
    )

    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)  # Truncated
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Request payload (for debugging)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Retry tracking
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    webhook: Mapped[OutboundWebhook] = relationship("OutboundWebhook", back_populates="deliveries")

    __table_args__ = (
        Index("idx_webhook_deliveries_webhook_id", "webhook_id"),
        Index("idx_webhook_deliveries_status", "status"),
        Index("idx_webhook_deliveries_created_at", "created_at"),
        Index(
            "idx_webhook_deliveries_next_retry",
            "next_retry_at",
            postgresql_where="status = 'retrying'",
        ),
    )

    @property
    def is_terminal(self) -> bool:
        """Check if delivery is in a terminal state.

        Returns:
            True if delivery succeeded or failed without retry pending.
        """
        return self.status in (
            WebhookDeliveryStatus.SUCCESS,
            WebhookDeliveryStatus.FAILED,
        )

    @property
    def can_retry(self) -> bool:
        """Check if delivery can be retried.

        Returns:
            True if delivery is in a retryable state.
        """
        return self.status in (
            WebhookDeliveryStatus.FAILED,
            WebhookDeliveryStatus.RETRYING,
        )

    def __repr__(self) -> str:
        return (
            f"<WebhookDelivery(id={self.id!r}, webhook_id={self.webhook_id!r}, "
            f"status={self.status.value!r}, attempt={self.attempt_count})>"
        )
