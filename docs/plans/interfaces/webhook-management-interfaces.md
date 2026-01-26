# Webhook Management Interface Definitions (NEM-3624)

This document defines the shared interfaces for the Webhook Management feature implementation.
All agents must follow these interface contracts.

## Linear Issue

- **ID:** NEM-3624
- **Title:** Discovery: Missing Webhooks & Integration Endpoints for Third-Party Systems

**Note:** The existing `backend/api/routes/webhooks.py` handles INCOMING webhooks from Alertmanager.
This feature adds OUTBOUND webhook management for sending notifications to external systems.

---

## 1. Backend Schemas (`backend/api/schemas/outbound_webhook.py`)

```python
"""Pydantic schemas for outbound webhook management API endpoints."""

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
    """Authentication configuration for webhook requests."""
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
    """Schema for creating a new webhook."""
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
    event_types: list[WebhookEventType] = Field(..., min_length=1, description="Events to subscribe to")
    integration_type: IntegrationType = Field(IntegrationType.GENERIC, description="Integration type")
    enabled: bool = Field(True, description="Whether webhook is active")
    auth: WebhookAuthConfig | None = Field(None, description="Authentication config")
    custom_headers: dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers")
    payload_template: str | None = Field(None, description="Custom payload template (Jinja2)")

    # Retry configuration
    max_retries: int = Field(4, ge=0, le=10, description="Max retry attempts")
    retry_delay_seconds: int = Field(10, ge=1, le=3600, description="Initial retry delay")

class WebhookUpdate(BaseModel):
    """Schema for updating a webhook."""
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
    """Full webhook configuration response."""
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
    """Response for listing webhooks."""
    webhooks: list[WebhookResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total count")

# =============================================================================
# Webhook Delivery Schemas
# =============================================================================

class WebhookDeliveryResponse(BaseModel):
    """Response for a webhook delivery attempt."""
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
    """Response for listing webhook deliveries."""
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
    """Request to test a webhook with sample data."""
    event_type: WebhookEventType = Field(
        WebhookEventType.ALERT_FIRED,
        description="Event type for test payload"
    )

class WebhookTestResponse(BaseModel):
    """Response from testing a webhook."""
    success: bool = Field(..., description="Whether test succeeded")
    status_code: int | None = Field(None, description="HTTP response code")
    response_time_ms: int | None = Field(None, description="Response time")
    response_body: str | None = Field(None, description="Response body (truncated)")
    error_message: str | None = Field(None, description="Error if failed")

# =============================================================================
# Webhook Health Schema
# =============================================================================

class WebhookHealthSummary(BaseModel):
    """Health summary for all webhooks."""
    total_webhooks: int = Field(0)
    enabled_webhooks: int = Field(0)
    healthy_webhooks: int = Field(0, description="Webhooks with >90% success rate")
    unhealthy_webhooks: int = Field(0, description="Webhooks with <50% success rate")
    total_deliveries_24h: int = Field(0)
    successful_deliveries_24h: int = Field(0)
    failed_deliveries_24h: int = Field(0)
    average_response_time_ms: float | None = Field(None)
```

---

## 2. Backend Model (`backend/models/outbound_webhook.py`)

```python
"""OutboundWebhook and WebhookDelivery models for outbound webhook management."""

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
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now
from .camera import Base


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


class OutboundWebhook(Base):
    """Model for outbound webhook configurations."""

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
        Enum(IntegrationType, name="integration_type", values_callable=lambda x: [e.value for e in x]),
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Stats (denormalized for performance)
    total_deliveries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_deliveries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_delivery_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
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


class WebhookDelivery(Base):
    """Model for tracking webhook delivery attempts."""

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
        Enum(WebhookDeliveryStatus, name="webhook_delivery_status", values_callable=lambda x: [e.value for e in x]),
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    webhook: Mapped["OutboundWebhook"] = relationship("OutboundWebhook", back_populates="deliveries")

    __table_args__ = (
        Index("idx_webhook_deliveries_webhook_id", "webhook_id"),
        Index("idx_webhook_deliveries_status", "status"),
        Index("idx_webhook_deliveries_created_at", "created_at"),
        Index("idx_webhook_deliveries_next_retry", "next_retry_at", postgresql_where="status = 'retrying'"),
    )
```

---

## 3. API Routes (`backend/api/routes/outbound_webhooks.py`)

```python
"""API Endpoint Contract:

# Webhook CRUD
POST   /api/outbound-webhooks              - Create webhook
GET    /api/outbound-webhooks              - List webhooks
GET    /api/outbound-webhooks/{id}         - Get webhook by ID
PATCH  /api/outbound-webhooks/{id}         - Update webhook
DELETE /api/outbound-webhooks/{id}         - Delete webhook

# Webhook operations
POST   /api/outbound-webhooks/{id}/test    - Test webhook with sample payload
POST   /api/outbound-webhooks/{id}/enable  - Enable webhook
POST   /api/outbound-webhooks/{id}/disable - Disable webhook

# Delivery logs
GET    /api/outbound-webhooks/{id}/deliveries - List deliveries for webhook
GET    /api/outbound-webhooks/deliveries/{delivery_id} - Get delivery details

# Health dashboard
GET    /api/outbound-webhooks/health       - Get webhook health summary

# Retry failed
POST   /api/outbound-webhooks/deliveries/{delivery_id}/retry - Retry failed delivery
"""

# Router prefix: /api/outbound-webhooks
# Tags: ["outbound-webhooks"]
```

---

## 4. Service Interfaces

### WebhookService (`backend/services/webhook_service.py`)

```python
"""WebhookService Interface:

class WebhookService:
    # CRUD operations
    async def create_webhook(self, db: AsyncSession, data: WebhookCreate) -> OutboundWebhook:
        '''Create a new webhook configuration.'''
        ...

    async def get_webhook(self, db: AsyncSession, webhook_id: str) -> OutboundWebhook | None:
        '''Get webhook by ID.'''
        ...

    async def list_webhooks(
        self,
        db: AsyncSession,
        enabled_only: bool = False,
    ) -> list[OutboundWebhook]:
        '''List all webhooks.'''
        ...

    async def update_webhook(
        self,
        db: AsyncSession,
        webhook_id: str,
        data: WebhookUpdate,
    ) -> OutboundWebhook | None:
        '''Update webhook configuration.'''
        ...

    async def delete_webhook(self, db: AsyncSession, webhook_id: str) -> bool:
        '''Delete a webhook.'''
        ...

    # Delivery operations
    async def deliver_webhook(
        self,
        db: AsyncSession,
        webhook: OutboundWebhook,
        event_type: WebhookEventType,
        event_data: dict,
        event_id: str | None = None,
    ) -> WebhookDelivery:
        '''Deliver a webhook notification.

        Creates delivery record and sends HTTP request.
        Handles retries on failure.
        '''
        ...

    async def trigger_webhooks_for_event(
        self,
        db: AsyncSession,
        event_type: WebhookEventType,
        event_data: dict,
        event_id: str | None = None,
    ) -> list[WebhookDelivery]:
        '''Trigger all webhooks subscribed to an event type.'''
        ...

    async def test_webhook(
        self,
        db: AsyncSession,
        webhook_id: str,
        event_type: WebhookEventType,
    ) -> WebhookTestResponse:
        '''Test a webhook with sample data (doesn't create delivery record).'''
        ...

    async def retry_delivery(
        self,
        db: AsyncSession,
        delivery_id: str,
    ) -> WebhookDelivery | None:
        '''Manually retry a failed delivery.'''
        ...

    # Stats
    async def get_health_summary(self, db: AsyncSession) -> WebhookHealthSummary:
        '''Get webhook health summary for dashboard.'''
        ...

    async def get_deliveries(
        self,
        db: AsyncSession,
        webhook_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WebhookDelivery], int]:
        '''Get delivery history for a webhook.'''
        ...

    # Internal helpers
    def _build_payload(
        self,
        webhook: OutboundWebhook,
        event_type: WebhookEventType,
        event_data: dict,
    ) -> dict:
        '''Build webhook payload, applying template if configured.'''
        ...

    def _sign_payload(self, payload: dict, secret: str) -> str:
        '''Generate HMAC-SHA256 signature for payload.'''
        ...

    async def _send_request(
        self,
        webhook: OutboundWebhook,
        payload: dict,
    ) -> tuple[int, str, int]:
        '''Send HTTP request to webhook URL.

        Returns: (status_code, response_body, response_time_ms)
        '''
        ...

    def _calculate_next_retry(self, attempt: int, base_delay: int) -> datetime:
        '''Calculate next retry time with exponential backoff.'''
        ...
```

---

## 5. Frontend Types (`frontend/src/types/webhook.ts`)

```typescript
// Event types
export type WebhookEventType =
  | 'alert_fired'
  | 'alert_dismissed'
  | 'alert_acknowledged'
  | 'event_created'
  | 'event_enriched'
  | 'entity_discovered'
  | 'anomaly_detected'
  | 'system_health_changed';

export type WebhookDeliveryStatus = 'pending' | 'success' | 'failed' | 'retrying';
export type IntegrationType = 'generic' | 'slack' | 'discord' | 'telegram' | 'teams';

// Auth config
export interface WebhookAuthConfig {
  type: 'none' | 'bearer' | 'basic' | 'header';
  token?: string;
  username?: string;
  password?: string;
  header_name?: string;
  header_value?: string;
}

// Webhook
export interface Webhook {
  id: string;
  name: string;
  url: string;
  event_types: WebhookEventType[];
  integration_type: IntegrationType;
  enabled: boolean;
  custom_headers: Record<string, string>;
  payload_template: string | null;
  max_retries: number;
  retry_delay_seconds: number;
  created_at: string;
  updated_at: string;
  total_deliveries: number;
  successful_deliveries: number;
  last_delivery_at: string | null;
  last_delivery_status: WebhookDeliveryStatus | null;
}

export interface WebhookCreate {
  name: string;
  url: string;
  event_types: WebhookEventType[];
  integration_type?: IntegrationType;
  enabled?: boolean;
  auth?: WebhookAuthConfig;
  custom_headers?: Record<string, string>;
  payload_template?: string;
  max_retries?: number;
  retry_delay_seconds?: number;
}

export interface WebhookUpdate {
  name?: string;
  url?: string;
  event_types?: WebhookEventType[];
  integration_type?: IntegrationType;
  enabled?: boolean;
  auth?: WebhookAuthConfig;
  custom_headers?: Record<string, string>;
  payload_template?: string;
  max_retries?: number;
  retry_delay_seconds?: number;
}

export interface WebhookListResponse {
  webhooks: Webhook[];
  total: number;
}

// Delivery
export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event_type: WebhookEventType;
  event_id: string | null;
  status: WebhookDeliveryStatus;
  status_code: number | null;
  response_time_ms: number | null;
  error_message: string | null;
  attempt_count: number;
  next_retry_at: string | null;
  created_at: string;
  delivered_at: string | null;
}

export interface WebhookDeliveryListResponse {
  deliveries: WebhookDelivery[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// Test
export interface WebhookTestRequest {
  event_type: WebhookEventType;
}

export interface WebhookTestResponse {
  success: boolean;
  status_code: number | null;
  response_time_ms: number | null;
  response_body: string | null;
  error_message: string | null;
}

// Health
export interface WebhookHealthSummary {
  total_webhooks: number;
  enabled_webhooks: number;
  healthy_webhooks: number;
  unhealthy_webhooks: number;
  total_deliveries_24h: number;
  successful_deliveries_24h: number;
  failed_deliveries_24h: number;
  average_response_time_ms: number | null;
}

// Event type labels for UI
export const WEBHOOK_EVENT_LABELS: Record<WebhookEventType, string> = {
  alert_fired: 'Alert Fired',
  alert_dismissed: 'Alert Dismissed',
  alert_acknowledged: 'Alert Acknowledged',
  event_created: 'Event Created',
  event_enriched: 'Event Enriched',
  entity_discovered: 'Entity Discovered',
  anomaly_detected: 'Anomaly Detected',
  system_health_changed: 'System Health Changed',
};

// Integration type info for UI
export const INTEGRATION_INFO: Record<
  IntegrationType,
  { label: string; icon: string; urlPattern?: string }
> = {
  generic: { label: 'Generic Webhook', icon: 'webhook' },
  slack: { label: 'Slack', icon: 'slack', urlPattern: 'hooks.slack.com' },
  discord: { label: 'Discord', icon: 'discord', urlPattern: 'discord.com/api/webhooks' },
  telegram: { label: 'Telegram', icon: 'telegram' },
  teams: { label: 'Microsoft Teams', icon: 'microsoft' },
};
```

---

## 6. Frontend API (`frontend/src/services/webhookApi.ts`)

```typescript
/**
 * API client functions for outbound webhook management.
 *
 * Endpoints:
 *   POST   /api/outbound-webhooks              - Create webhook
 *   GET    /api/outbound-webhooks              - List webhooks
 *   GET    /api/outbound-webhooks/:id          - Get webhook
 *   PATCH  /api/outbound-webhooks/:id          - Update webhook
 *   DELETE /api/outbound-webhooks/:id          - Delete webhook
 *   POST   /api/outbound-webhooks/:id/test     - Test webhook
 *   POST   /api/outbound-webhooks/:id/enable   - Enable webhook
 *   POST   /api/outbound-webhooks/:id/disable  - Disable webhook
 *   GET    /api/outbound-webhooks/:id/deliveries - List deliveries
 *   GET    /api/outbound-webhooks/health       - Get health summary
 *   POST   /api/outbound-webhooks/deliveries/:id/retry - Retry delivery
 */

import type {
  Webhook,
  WebhookCreate,
  WebhookUpdate,
  WebhookListResponse,
  WebhookDeliveryListResponse,
  WebhookTestRequest,
  WebhookTestResponse,
  WebhookHealthSummary,
} from '../types/webhook';

const API_BASE = '/api/outbound-webhooks';

export async function createWebhook(data: WebhookCreate): Promise<Webhook>;
export async function listWebhooks(): Promise<WebhookListResponse>;
export async function getWebhook(id: string): Promise<Webhook>;
export async function updateWebhook(id: string, data: WebhookUpdate): Promise<Webhook>;
export async function deleteWebhook(id: string): Promise<void>;
export async function testWebhook(
  id: string,
  request: WebhookTestRequest
): Promise<WebhookTestResponse>;
export async function enableWebhook(id: string): Promise<Webhook>;
export async function disableWebhook(id: string): Promise<Webhook>;
export async function getDeliveries(
  webhookId: string,
  params?: { limit?: number; offset?: number }
): Promise<WebhookDeliveryListResponse>;
export async function getHealthSummary(): Promise<WebhookHealthSummary>;
export async function retryDelivery(deliveryId: string): Promise<void>;
```

---

## 7. Frontend Hook (`frontend/src/hooks/useWebhooks.ts`)

```typescript
/**
 * TanStack Query hooks for webhook management.
 *
 * Query Keys:
 *   ['webhooks'] - base key
 *   ['webhooks', 'list'] - webhook list
 *   ['webhooks', 'detail', id] - specific webhook
 *   ['webhooks', 'deliveries', webhookId] - deliveries for webhook
 *   ['webhooks', 'health'] - health summary
 *
 * Hooks:
 *   useWebhookList() - Fetch list of webhooks
 *   useWebhook(id) - Fetch single webhook
 *   useWebhookDeliveries(webhookId, options) - Fetch delivery history
 *   useWebhookHealth() - Fetch health summary
 *   useCreateWebhook() - Mutation to create webhook
 *   useUpdateWebhook() - Mutation to update webhook
 *   useDeleteWebhook() - Mutation to delete webhook
 *   useTestWebhook() - Mutation to test webhook
 *   useToggleWebhook() - Mutation to enable/disable
 *   useRetryDelivery() - Mutation to retry failed delivery
 */

export const WEBHOOK_QUERY_KEYS = {
  all: ['webhooks'] as const,
  list: ['webhooks', 'list'] as const,
  detail: (id: string) => ['webhooks', 'detail', id] as const,
  deliveries: (webhookId: string) => ['webhooks', 'deliveries', webhookId] as const,
  health: ['webhooks', 'health'] as const,
};

// Hook interfaces follow useGpuConfig.ts patterns
```

---

## 8. Agent Assignments

| Agent | Scope                                    | Files                                                                                                                   |
| ----- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **5** | Backend schemas & models                 | `backend/api/schemas/outbound_webhook.py`, `backend/models/outbound_webhook.py`                                         |
| **6** | WebhookService                           | `backend/services/webhook_service.py`                                                                                   |
| **7** | API routes                               | `backend/api/routes/outbound_webhooks.py`                                                                               |
| **8** | Frontend (types, API, hooks, components) | `frontend/src/types/webhook.ts`, `frontend/src/services/webhookApi.ts`, `frontend/src/hooks/useWebhooks.ts`, components |

---

## 9. Integration Points

The WebhookService should be called from existing event handlers:

1. **Alert creation** (`backend/services/alert_service.py`):

   - Call `trigger_webhooks_for_event(event_type=ALERT_FIRED, ...)`

2. **Alert dismissal/acknowledgment** (`backend/api/routes/alerts.py`):

   - Call `trigger_webhooks_for_event(event_type=ALERT_DISMISSED, ...)`

3. **Event creation** (`backend/services/event_service.py`):

   - Call `trigger_webhooks_for_event(event_type=EVENT_CREATED, ...)`

4. **Event enrichment** (`backend/services/enrichment_service.py`):
   - Call `trigger_webhooks_for_event(event_type=EVENT_ENRICHED, ...)`

---

## 10. Testing Requirements

- **Unit tests** for services in `backend/tests/unit/services/`
- **Integration tests** for API in `backend/tests/integration/test_outbound_webhooks_api.py`
- **Frontend tests** in `frontend/src/hooks/useWebhooks.test.ts`
