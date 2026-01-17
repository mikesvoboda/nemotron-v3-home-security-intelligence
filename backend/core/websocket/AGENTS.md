# Core WebSocket - Agent Guide

## Purpose

This directory contains the WebSocket event type registry, payload schemas, and subscription management infrastructure for real-time event broadcasting throughout the application.

## Files Overview

```
backend/core/websocket/
|-- __init__.py              # Package exports
|-- event_types.py           # WebSocket event type enum and helpers
|-- event_schemas.py         # Pydantic schemas for payload validation
|-- subscription_manager.py  # Channel subscription management
```

## `event_types.py` - Event Type Registry

Provides a centralized registry of all WebSocket event types using a StrEnum.

### WebSocketEventType Enum

Event types follow the pattern: `{domain}.{action}`

**Domains:**

| Domain         | Description                             |
| -------------- | --------------------------------------- |
| `alert`        | Alert notifications and state changes   |
| `camera`       | Camera status and configuration changes |
| `job`          | Background job lifecycle events         |
| `system`       | System health and status events         |
| `service`      | Individual service status changes       |
| `gpu`          | GPU statistics updates                  |
| `worker`       | Pipeline worker lifecycle (NEM-2461)    |
| `event`        | Security event lifecycle (AI-analyzed)  |
| `detection`    | Raw AI detection events                 |
| `scene_change` | Camera view monitoring                  |
| `connection`   | WebSocket connection lifecycle          |

**Event Categories:**

- Alert events: `ALERT_CREATED`, `ALERT_UPDATED`, `ALERT_DELETED`, `ALERT_ACKNOWLEDGED`, `ALERT_RESOLVED`, `ALERT_DISMISSED`
- Camera events: `CAMERA_ONLINE`, `CAMERA_OFFLINE`, `CAMERA_STATUS_CHANGED`, `CAMERA_ENABLED`, `CAMERA_DISABLED`, `CAMERA_ERROR`, `CAMERA_CONFIG_UPDATED`
- Job events: `JOB_STARTED`, `JOB_PROGRESS`, `JOB_COMPLETED`, `JOB_FAILED`, `JOB_CANCELLED`, plus legacy underscore format (NEM-2505)
- System events: `SYSTEM_HEALTH_CHANGED`, `SYSTEM_ERROR`, `SYSTEM_STATUS`, `SERVICE_STATUS_CHANGED`, `GPU_STATS_UPDATED`
- Worker events: `WORKER_STARTED`, `WORKER_STOPPED`, `WORKER_HEALTH_CHECK_FAILED`, `WORKER_RESTARTING`, `WORKER_RECOVERED`, `WORKER_ERROR`
- Security events: `EVENT_CREATED`, `EVENT_UPDATED`, `EVENT_DELETED`
- Detection events: `DETECTION_NEW`, `DETECTION_BATCH`
- Scene change events: `SCENE_CHANGE_DETECTED`
- Connection events: `CONNECTION_ESTABLISHED`, `CONNECTION_ERROR`
- Control messages: `PING`, `PONG`, `ERROR`

### WebSocketEvent TypedDict

Standard envelope structure for all WebSocket events:

| Field            | Type               | Description                 |
| ---------------- | ------------------ | --------------------------- | --------------------------------- |
| `type`           | WebSocketEventType | Event type from enum        |
| `payload`        | dict[str, Any]     | Event-specific payload data |
| `timestamp`      | str                | ISO 8601 timestamp          |
| `correlation_id` | str                | None                        | Optional ID for event correlation |
| `sequence`       | int                | None                        | Optional sequence number          |
| `channel`        | str                | None                        | Optional channel identifier       |

### Helper Functions

| Function                      | Purpose                                         |
| ----------------------------- | ----------------------------------------------- |
| `create_event`                | Factory to create WebSocketEvent with timestamp |
| `get_event_channel`           | Get default channel for an event type           |
| `get_event_description`       | Get human-readable description                  |
| `get_required_payload_fields` | Get required fields for an event type           |
| `validate_event_type`         | Convert string to WebSocketEventType            |
| `get_all_event_types`         | Get all registered event types                  |
| `get_event_types_by_channel`  | Get event types for a channel                   |
| `get_all_channels`            | Get all unique channel names                    |

## `event_schemas.py` - Payload Validation Schemas

Pydantic models for validating event payloads before they are emitted via WebSocket.

### Common Enums

| Enum              | Values                                                 |
| ----------------- | ------------------------------------------------------ |
| `AlertSeverity`   | low, medium, high, critical                            |
| `AlertStatus`     | pending, delivered, acknowledged, dismissed            |
| `CameraStatus`    | online, offline, error, unknown                        |
| `JobStatus`       | pending, running, completed, failed, cancelled         |
| `SystemHealth`    | healthy, degraded, unhealthy                           |
| `ServiceStatus`   | healthy, unhealthy, restarting, restart_failed, failed |
| `RiskLevel`       | low, medium, high, critical                            |
| `SceneChangeType` | view_blocked, angle_changed, view_tampered, unknown    |
| `WorkerType`      | detection, analysis, timeout, metrics                  |
| `WorkerStateEnum` | stopped, starting, running, stopping, error            |

### Payload Schemas by Domain

**Alert Payloads:** `AlertCreatedPayload`, `AlertUpdatedPayload`, `AlertDeletedPayload`, `AlertAcknowledgedPayload`, `AlertResolvedPayload`, `AlertDismissedPayload`

**Camera Payloads:** `CameraOnlinePayload`, `CameraOfflinePayload`, `CameraStatusChangedPayload`, `CameraErrorPayload`, `CameraConfigUpdatedPayload`

**Job Payloads:** `JobStartedPayload`, `JobProgressPayload`, `JobCompletedPayload`, `JobFailedPayload`, `JobCancelledPayload`

**System Payloads:** `SystemHealthChangedPayload`, `SystemErrorPayload`, `SystemStatusPayload`, `ServiceStatusChangedPayload`, `GPUStatsUpdatedPayload`

**Worker Payloads (NEM-2461):** `WorkerStartedPayload`, `WorkerStoppedPayload`, `WorkerHealthCheckFailedPayload`, `WorkerRestartingPayload`, `WorkerRecoveredPayload`, `WorkerErrorPayload`

**Security Payloads:** `EventCreatedPayload`, `EventUpdatedPayload`, `EventDeletedPayload`

**Detection Payloads:** `DetectionNewPayload`, `DetectionBatchPayload`, `BoundingBox`

**Scene Change Payloads:** `SceneChangeDetectedPayload`

**Connection Payloads:** `ConnectionEstablishedPayload`, `ConnectionErrorPayload`, `ErrorPayload`

### Validation Functions

| Function             | Purpose                                    |
| -------------------- | ------------------------------------------ |
| `get_payload_schema` | Get Pydantic schema for an event type      |
| `validate_payload`   | Validate payload against event type schema |

## `subscription_manager.py` - Subscription Management

Manages WebSocket event subscriptions per connection, supporting wildcard patterns for flexible event filtering.

### SubscriptionManager Class

Thread-safe manager using `threading.RLock` for subscription operations.

**Pattern Matching:**

- `*` - Matches all events (default if no subscription sent)
- `alert.*` - All alert events
- `camera.*` - All camera events
- `job.progress` - Exact match for specific event

**Protocol:**

```json
// Client subscribes
{"action": "subscribe", "events": ["alert.*", "camera.status_changed"]}

// Server acknowledges
{"action": "subscribed", "events": ["alert.*", "camera.status_changed"]}

// Client unsubscribes
{"action": "unsubscribe", "events": ["alert.*"]}

// Server acknowledges
{"action": "unsubscribed", "events": ["alert.*"]}
```

### Methods

| Method                                | Purpose                                  |
| ------------------------------------- | ---------------------------------------- |
| `subscribe(conn_id, patterns)`        | Subscribe connection to patterns         |
| `unsubscribe(conn_id, patterns)`      | Unsubscribe from patterns (or all)       |
| `should_send(conn_id, event_type)`    | Check if connection should receive event |
| `get_recipients(event_type)`          | Get all connections for an event         |
| `get_subscriptions(conn_id)`          | Get patterns a connection subscribes to  |
| `has_explicit_subscriptions(conn_id)` | Check if connection has subscriptions    |
| `register_connection(conn_id)`        | Register new connection (receives all)   |
| `remove_connection(conn_id)`          | Clean up connection on disconnect        |
| `get_connection_count()`              | Get number of registered connections     |
| `get_stats()`                         | Get subscription statistics              |

### Default Behavior

- New connections receive ALL events (backwards compatible)
- Only after explicit `subscribe()` call are events filtered
- Empty subscription list after `subscribe()` means no events

### Global Functions

| Function                             | Purpose                       |
| ------------------------------------ | ----------------------------- |
| `get_subscription_manager()`         | Get global singleton instance |
| `reset_subscription_manager_state()` | Reset for testing             |

## Usage Example

```python
from backend.core.websocket.event_types import WebSocketEventType, create_event
from backend.core.websocket.event_schemas import validate_payload, AlertCreatedPayload
from backend.core.websocket.subscription_manager import get_subscription_manager

# Create an event
event = create_event(
    WebSocketEventType.ALERT_CREATED,
    {"id": "uuid", "event_id": 123, "severity": "high", "status": "pending", "dedup_key": "key", "created_at": "...", "updated_at": "..."},
    correlation_id="req-abc123",
)

# Validate payload
payload = AlertCreatedPayload(**event["payload"])

# Check subscriptions
manager = get_subscription_manager()
if manager.should_send(connection_id, event["type"]):
    await websocket.send_text(json.dumps(event))
```

## Related Documentation

- `/backend/api/routes/websocket.py` - WebSocket route handlers
- `/backend/services/event_broadcaster.py` - Event broadcasting service
- `/backend/core/AGENTS.md` - Core infrastructure overview
