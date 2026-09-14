"""Pydantic schemas for outbound webhook management API endpoints.

This module defines request/response schemas for the outbound webhook
management API. These webhooks are for sending notifications to external
systems (e.g., Slack, Discord, Telegram) when events occur in the system.

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
    - batch_analysis_started: Batch analysis processing started
    - batch_analysis_completed: Batch analysis completed successfully
    - batch_analysis_failed: Batch analysis failed

Integration Types:
    - generic: Custom webhook with configurable payload
    - slack: Slack incoming webhook
    - discord: Discord webhook
    - telegram: Telegram bot
    - teams: Microsoft Teams webhook
"""

from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# =============================================================================
# Enums
# =============================================================================


class WebhookEventType(StrEnum):
    """Event types that can trigger webhooks."""

    ALERT_FIRED = "alert_fired"
    ALERT_DISMISSED = "alert_dismissed"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    EVENT_CREATED = "event_created"
    EVENT_ENRICHED = "event_enriched"
    ENTITY_DISCOVERED = "entity_discovered"
    ANOMALY_DETECTED = "anomaly_detected"
    SYSTEM_HEALTH_CHANGED = "system_health_changed"
    BATCH_ANALYSIS_STARTED = "batch_analysis_started"
    BATCH_ANALYSIS_COMPLETED = "batch_analysis_completed"
    BATCH_ANALYSIS_FAILED = "batch_analysis_failed"


class WebhookDeliveryStatus(StrEnum):
    """Webhook delivery attempt status."""

    PENDING = auto()
    SUCCESS = auto()
    FAILED = auto()
    RETRYING = auto()


class IntegrationType(StrEnum):
    """Pre-built integration types."""

    GENERIC = "generic"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    TEAMS = "teams"


# =============================================================================
# Webhook Configuration Schemas
# =============================================================================


class WebhookAuthConfig(BaseModel):
    """Authentication configuration for webhook requests.

    Supports multiple authentication types:
    - none: No authentication
    - bearer: Bearer token authentication
    - basic: Basic authentication with username/password
    - header: Custom header authentication

    Attributes:
        type: Authentication type (none, bearer, basic, header).
        token: Bearer token for bearer auth.
        username: Username for basic auth.
        password: Password for basic auth.
        header_name: Custom header name for header auth.
        header_value: Custom header value for header auth.
    """

    type: str = Field("none", description="Auth type: none, bearer, basic, header")
    # For bearer token
    token: str | None = Field(None, description="Bearer token (if type=bearer)")
    # For basic auth
    username: str | None = Field(None, description="Username (if type=basic)")
    password: str | None = Field(None, description="Password (if type=basic)")
    # For custom header
    header_name: str | None = Field(None, description="Custom header name (if type=header)")
    header_value: str | None = Field(None, description="Custom header value (if type=header)")


class WebhookCreate(BaseModel):
    """Schema for creating a new outbound webhook.

    Create a new webhook configuration for sending notifications to external
    systems when specified events occur.

    Attributes:
        name: Human-readable name for the webhook.
        url: Webhook endpoint URL.
        event_types: List of events that trigger this webhook.
        integration_type: Type of integration (generic, slack, discord, etc.).
        enabled: Whether the webhook is active.
        auth: Optional authentication configuration.
        custom_headers: Additional HTTP headers to send.
        payload_template: Optional Jinja2 template for custom payload.
        max_retries: Maximum number of retry attempts on failure.
        retry_delay_seconds: Initial delay between retries.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Slack Alerts",
                "url": "https://hooks.slack.com/services/xxx/yyy/zzz",
                "event_types": ["alert_fired", "alert_dismissed"],
                "integration_type": "slack",
                "enabled": True,
                "auth": {"type": "none"},
                "custom_headers": {},
                "payload_template": None,
            }
        }
    )

    name: str = Field(..., min_length=1, max_length=100, description="Webhook name")
    url: HttpUrl = Field(..., description="Webhook endpoint URL")
    event_types: list[WebhookEventType] = Field(
        ..., min_length=1, description="Events to subscribe to"
    )
    integration_type: IntegrationType = Field(
        IntegrationType.GENERIC, description="Integration type"
    )
    enabled: bool = Field(True, description="Whether webhook is active")
    auth: WebhookAuthConfig | None = Field(None, description="Authentication config")
    custom_headers: dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers")
    payload_template: str | None = Field(None, description="Custom payload template (Jinja2)")

    # Retry configuration
    max_retries: int = Field(4, ge=0, le=10, description="Max retry attempts")
    retry_delay_seconds: int = Field(10, ge=1, le=3600, description="Initial retry delay")


class WebhookUpdate(BaseModel):
    """Schema for updating an existing webhook.

    All fields are optional - only provided fields will be updated.

    Attributes:
        name: New webhook name.
        url: New webhook URL.
        event_types: New list of subscribed events.
        integration_type: New integration type.
        enabled: New enabled status.
        auth: New authentication configuration.
        custom_headers: New custom headers.
        payload_template: New payload template.
        max_retries: New max retry count.
        retry_delay_seconds: New retry delay.
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    url: HttpUrl | None = None
    event_types: list[WebhookEventType] | None = None
    integration_type: IntegrationType | None = None
    enabled: bool | None = None
    auth: WebhookAuthConfig | None = None
    custom_headers: dict[str, str] | None = None
    payload_template: str | None = None
    max_retries: int | None = Field(None, ge=0, le=10)
    retry_delay_seconds: int | None = Field(None, ge=1, le=3600)


class WebhookResponse(BaseModel):
    """Full webhook configuration response.

    Returns complete webhook information including configuration,
    metadata, and delivery statistics.

    Attributes:
        id: Unique webhook identifier.
        name: Webhook name.
        url: Webhook endpoint URL.
        event_types: Subscribed event types.
        integration_type: Integration type.
        enabled: Whether active.
        custom_headers: Custom HTTP headers.
        payload_template: Jinja2 payload template.
        max_retries: Max retry attempts.
        retry_delay_seconds: Initial retry delay.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        total_deliveries: Total delivery attempts.
        successful_deliveries: Successful delivery count.
        last_delivery_at: Last delivery timestamp.
        last_delivery_status: Status of last delivery.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique webhook identifier")
    name: str = Field(..., description="Webhook name")
    url: str = Field(..., description="Webhook endpoint URL")
    event_types: list[WebhookEventType] = Field(..., description="Subscribed events")
    integration_type: IntegrationType = Field(..., description="Integration type")
    enabled: bool = Field(..., description="Whether active")
    custom_headers: dict[str, str] = Field(default_factory=dict)
    payload_template: str | None = Field(None)
    max_retries: int = Field(...)
    retry_delay_seconds: int = Field(...)

    # Metadata
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Stats
    total_deliveries: int = Field(0, description="Total delivery attempts")
    successful_deliveries: int = Field(0, description="Successful deliveries")
    last_delivery_at: datetime | None = Field(None, description="Last delivery timestamp")
    last_delivery_status: WebhookDeliveryStatus | None = Field(None)


class WebhookListResponse(BaseModel):
    """Response for listing webhooks.

    Attributes:
        webhooks: List of webhook configurations.
        total: Total number of webhooks.
    """

    webhooks: list[WebhookResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total count")


# =============================================================================
# Webhook Delivery Schemas
# =============================================================================


class WebhookDeliveryResponse(BaseModel):
    """Response for a webhook delivery attempt.

    Provides details about a single webhook delivery attempt including
    status, timing, and any error information.

    Attributes:
        id: Delivery ID.
        webhook_id: Parent webhook ID.
        event_type: Event that triggered delivery.
        event_id: Related event ID.
        status: Delivery status.
        status_code: HTTP response status code.
        response_time_ms: Response time in milliseconds.
        error_message: Error message if failed.
        attempt_count: Number of attempts.
        next_retry_at: Next retry timestamp.
        created_at: Delivery creation timestamp.
        delivered_at: Successful delivery timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Delivery ID")
    webhook_id: str = Field(..., description="Parent webhook ID")
    event_type: WebhookEventType = Field(..., description="Event that triggered delivery")
    event_id: str | None = Field(None, description="Related event ID")

    status: WebhookDeliveryStatus = Field(..., description="Delivery status")
    status_code: int | None = Field(None, description="HTTP response status code")
    response_time_ms: int | None = Field(None, description="Response time in milliseconds")
    error_message: str | None = Field(None, description="Error message if failed")

    attempt_count: int = Field(1, description="Number of attempts")
    next_retry_at: datetime | None = Field(None, description="Next retry timestamp")

    created_at: datetime = Field(..., description="Delivery creation timestamp")
    delivered_at: datetime | None = Field(None, description="Successful delivery timestamp")


class WebhookDeliveryListResponse(BaseModel):
    """Response for listing webhook deliveries.

    Includes pagination information for navigating large delivery histories.

    Attributes:
        deliveries: List of delivery records.
        total: Total number of deliveries.
        limit: Page size.
        offset: Page offset.
        has_more: Whether more pages exist.
    """

    deliveries: list[WebhookDeliveryResponse] = Field(default_factory=list)
    total: int = Field(0)
    # Pagination
    limit: int = Field(50)
    offset: int = Field(0)
    has_more: bool = Field(False)


# =============================================================================
# Test Webhook Schema
# =============================================================================


class WebhookTestRequest(BaseModel):
    """Request to test a webhook with sample data.

    Allows testing a webhook configuration with a simulated event
    to verify connectivity and payload format.

    Attributes:
        event_type: Event type to use for test payload.
    """

    event_type: WebhookEventType = Field(
        WebhookEventType.ALERT_FIRED,
        description="Event type for test payload",
    )


class WebhookTestResponse(BaseModel):
    """Response from testing a webhook.

    Returns the result of a webhook test including response details
    and any errors encountered.

    Attributes:
        success: Whether test succeeded.
        status_code: HTTP response code.
        response_time_ms: Response time.
        response_body: Response body (truncated).
        error_message: Error if failed.
    """

    success: bool = Field(..., description="Whether test succeeded")
    status_code: int | None = Field(None, description="HTTP response code")
    response_time_ms: int | None = Field(None, description="Response time")
    response_body: str | None = Field(None, description="Response body (truncated)")
    error_message: str | None = Field(None, description="Error if failed")


# =============================================================================
# Webhook Health Schema
# =============================================================================


class WebhookHealthSummary(BaseModel):
    """Health summary for all webhooks.

    Provides an overview of webhook health across the system including
    delivery statistics for the last 24 hours.

    Attributes:
        total_webhooks: Total number of configured webhooks.
        enabled_webhooks: Number of enabled webhooks.
        healthy_webhooks: Webhooks with >90% success rate.
        unhealthy_webhooks: Webhooks with <50% success rate.
        total_deliveries_24h: Total deliveries in last 24 hours.
        successful_deliveries_24h: Successful deliveries in last 24 hours.
        failed_deliveries_24h: Failed deliveries in last 24 hours.
        average_response_time_ms: Average response time.
    """

    total_webhooks: int = Field(0)
    enabled_webhooks: int = Field(0)
    healthy_webhooks: int = Field(0, description="Webhooks with >90% success rate")
    unhealthy_webhooks: int = Field(0, description="Webhooks with <50% success rate")
    total_deliveries_24h: int = Field(0)
    successful_deliveries_24h: int = Field(0)
    failed_deliveries_24h: int = Field(0)
    average_response_time_ms: float | None = Field(None)
