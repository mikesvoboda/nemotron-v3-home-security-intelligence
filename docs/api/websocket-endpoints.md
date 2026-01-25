# WebSocket Endpoints Reference

This document provides comprehensive documentation of all WebSocket endpoints available in the Home Security Intelligence system.

## Overview

The system provides three WebSocket endpoints for real-time communication:

| Endpoint                 | Purpose                                            | Channel |
| ------------------------ | -------------------------------------------------- | ------- |
| `/ws/events`             | Security events, detections, alerts, camera status | events  |
| `/ws/system`             | System health, GPU stats, service status           | system  |
| `/ws/jobs/{job_id}/logs` | Real-time job log streaming                        | jobs    |

## Authentication

Two authentication methods are supported (both optional, can be used together):

### API Key Authentication

When `api_key_enabled=true` in settings:

```bash
# Via query parameter
ws://localhost:8000/ws/events?api_key=YOUR_KEY

# Via Sec-WebSocket-Protocol header
Sec-WebSocket-Protocol: api-key.YOUR_KEY
```

### Token Authentication

When `WEBSOCKET_TOKEN` is configured:

```bash
ws://localhost:8000/ws/events?token=YOUR_TOKEN
```

**Note**: Connections without valid credentials (when auth is enabled) receive close code 1008 (Policy Violation).

---

## Endpoint: `/ws/events`

**Purpose**: Real-time security event streaming including detections, alerts, camera status changes, and scene changes.

### Connection Example

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/events');

ws.onopen = () => {
  console.log('Connected to events stream');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event received:', data.type, data);
};
```

### Message Types Received

#### `event` - Security Event

Broadcast when a new security event is created after AI analysis.

```json
{
  "type": "event",
  "data": {
    "id": 1,
    "event_id": 1,
    "batch_id": "batch_abc123",
    "camera_id": "front_door",
    "risk_score": 75,
    "risk_level": "high",
    "summary": "Person detected at front door",
    "reasoning": "Unknown individual approaching entrance during nighttime hours",
    "started_at": "2026-01-25T12:00:00Z"
  },
  "sequence": 42,
  "requires_ack": false
}
```

| Field        | Type    | Description                               |
| ------------ | ------- | ----------------------------------------- |
| `id`         | integer | Unique event identifier                   |
| `event_id`   | integer | Legacy alias for backward compatibility   |
| `batch_id`   | string  | Detection batch identifier                |
| `camera_id`  | string  | Normalized camera ID (e.g., "front_door") |
| `risk_score` | integer | AI-determined risk score (0-100)          |
| `risk_level` | string  | "low", "medium", "high", "critical"       |
| `summary`    | string  | AI-generated event summary                |
| `reasoning`  | string  | LLM reasoning for the risk assessment     |
| `started_at` | string  | ISO 8601 timestamp when event started     |

#### `alert_created` - New Alert

```json
{
  "type": "alert_created",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "event_id": 123,
    "rule_id": "550e8400-e29b-41d4-a716-446655440001",
    "severity": "high",
    "status": "pending",
    "dedup_key": "front_door:person:rule1",
    "created_at": "2026-01-25T12:00:00Z"
  }
}
```

#### `alert_updated` - Alert Modified

```json
{
  "type": "alert_updated",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "updated_at": "2026-01-25T12:05:00Z",
    "status": "acknowledged"
  }
}
```

#### `alert_acknowledged` - Alert Seen

```json
{
  "type": "alert_acknowledged",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "acknowledged_at": "2026-01-25T12:05:00Z"
  }
}
```

#### `alert_resolved` - Alert Closed

```json
{
  "type": "alert_resolved",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "resolved_at": "2026-01-25T12:10:00Z"
  }
}
```

#### `alert_dismissed` - Alert Dismissed

```json
{
  "type": "alert_dismissed",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "dismissed_at": "2026-01-25T12:10:00Z"
  }
}
```

#### `alert_deleted` - Alert Removed

```json
{
  "type": "alert_deleted",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "reason": "Duplicate alert"
  }
}
```

#### `camera_status` - Camera Status Change

```json
{
  "type": "camera_status",
  "data": {
    "camera_id": "front_door",
    "camera_name": "Front Door Camera",
    "status": "offline",
    "previous_status": "online",
    "changed_at": "2026-01-25T10:30:00Z",
    "reason": "No activity detected for 5 minutes"
  }
}
```

| Status Values | Description                    |
| ------------- | ------------------------------ |
| `online`      | Camera is active and streaming |
| `offline`     | Camera has no recent activity  |
| `error`       | Camera encountered an error    |
| `unknown`     | Status cannot be determined    |

#### `scene_change` - View Tampering Detected

```json
{
  "type": "scene_change",
  "data": {
    "id": 1,
    "camera_id": "front_door",
    "detected_at": "2026-01-25T10:30:00Z",
    "change_type": "view_blocked",
    "similarity_score": 0.23
  }
}
```

| Change Type     | Description                    |
| --------------- | ------------------------------ |
| `view_blocked`  | Camera view is obstructed      |
| `angle_changed` | Camera angle has shifted       |
| `view_tampered` | Intentional tampering detected |
| `unknown`       | Unclassified change            |

#### `detection.new` - Real-time Detection

```json
{
  "type": "detection.new",
  "data": {
    "detection_id": 123,
    "batch_id": "batch_abc123",
    "camera_id": "front_door",
    "label": "person",
    "confidence": 0.95,
    "timestamp": "2026-01-25T10:30:00Z"
  }
}
```

#### `detection.batch` - Batch Completed

```json
{
  "type": "detection.batch",
  "data": {
    "batch_id": "batch_abc123",
    "camera_id": "front_door",
    "detection_ids": [123, 124, 125],
    "detection_count": 3,
    "started_at": "2026-01-25T10:30:00Z",
    "closed_at": "2026-01-25T10:32:00Z",
    "close_reason": "timeout"
  }
}
```

| Close Reason | Description                     |
| ------------ | ------------------------------- |
| `timeout`    | 90-second batch window expired  |
| `idle`       | 30 seconds since last detection |
| `max_size`   | Maximum batch size reached      |

#### `worker_status` - Pipeline Worker Status

```json
{
  "type": "worker_status",
  "data": {
    "event_type": "worker.started",
    "worker_name": "detection_worker",
    "worker_type": "detection",
    "timestamp": "2026-01-25T10:30:00Z"
  }
}
```

| Event Type                   | Description                 |
| ---------------------------- | --------------------------- |
| `worker.started`             | Worker started processing   |
| `worker.stopped`             | Worker stopped gracefully   |
| `worker.health_check_failed` | Health check failed         |
| `worker.restarting`          | Worker is restarting        |
| `worker.recovered`           | Worker recovered from error |
| `worker.error`               | Worker encountered an error |

#### `infrastructure_alert` - Prometheus Alert

```json
{
  "type": "infrastructure_alert",
  "data": {
    "alertname": "HSIGPUMemoryHigh",
    "status": "firing",
    "severity": "warning",
    "component": "gpu",
    "summary": "GPU memory usage is high",
    "description": "GPU memory usage is above 90%",
    "started_at": "2026-01-25T12:22:56Z",
    "fingerprint": "example-fingerprint"
  }
}
```

#### `summary_update` - Summary Generation

```json
{
  "type": "summary_update",
  "data": {
    "hourly": {
      "id": 1,
      "content": "Over the past hour...",
      "event_count": 1,
      "window_start": "2026-01-25T14:00:00Z",
      "window_end": "2026-01-25T15:00:00Z",
      "generated_at": "2026-01-25T14:55:00Z"
    },
    "daily": null
  }
}
```

### Client Messages Supported

#### `ping` - Heartbeat Request

```json
{ "type": "ping" }
```

Server responds with:

```json
{ "type": "pong" }
```

#### `subscribe` - Event Filtering

```json
{
  "type": "subscribe",
  "data": {
    "events": ["alert.*", "camera.status_changed"]
  }
}
```

**Pattern Syntax**:

- `*` - All events (default)
- `alert.*` - All alert events
- `camera.status_changed` - Exact match

Server responds with:

```json
{
  "action": "subscribed",
  "events": ["alert.*", "camera.status_changed"]
}
```

#### `unsubscribe` - Remove Filters

```json
{
  "type": "unsubscribe",
  "data": {
    "events": ["alert.*"]
  }
}
```

#### `resync` - Sequence Gap Recovery

When the client detects a gap in sequence numbers:

```json
{
  "type": "resync",
  "data": {
    "channel": "events",
    "last_sequence": 42
  }
}
```

Server responds with:

```json
{
  "type": "resync_ack",
  "channel": "events",
  "last_sequence": 42
}
```

---

## Endpoint: `/ws/system`

**Purpose**: System health monitoring including GPU stats, service status, and overall system health.

### Connection Example

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/system');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'system_status') {
    console.log('GPU Utilization:', data.data.gpu.utilization);
  }
};
```

### Message Types Received

#### `system_status` - Full System Status

Broadcast periodically (every 5 seconds):

```json
{
  "type": "system_status",
  "data": {
    "gpu": {
      "utilization": 45.5,
      "memory_used": 8192000000,
      "memory_total": 24576000000,
      "temperature": 65.0,
      "inference_fps": 30.5
    },
    "cameras": {
      "active": 4,
      "total": 6
    },
    "queue": {
      "pending": 2,
      "processing": 1
    },
    "health": "healthy"
  },
  "timestamp": "2026-01-25T10:30:00.000Z"
}
```

| Health Status | Description                         |
| ------------- | ----------------------------------- |
| `healthy`     | All systems operating normally      |
| `degraded`    | Some components experiencing issues |
| `unhealthy`   | Critical components are failing     |

#### `service_status` - Individual Service Status

```json
{
  "type": "service_status",
  "data": {
    "service": "nemotron",
    "status": "healthy",
    "message": "Service recovered"
  },
  "timestamp": "2026-01-25T12:00:00.000Z"
}
```

| Service Status   | Description                |
| ---------------- | -------------------------- |
| `healthy`        | Service operating normally |
| `unhealthy`      | Service is failing         |
| `restarting`     | Service is being restarted |
| `restart_failed` | Restart attempt failed     |
| `failed`         | Service has failed         |

#### `gpu.stats_updated` - GPU Statistics

```json
{
  "type": "gpu.stats_updated",
  "data": {
    "utilization": 45.5,
    "memory_used": 8192000000,
    "memory_total": 24576000000,
    "temperature": 65.0,
    "inference_fps": 30.5
  }
}
```

---

## Endpoint: `/ws/jobs/{job_id}/logs`

**Purpose**: Stream real-time logs for active background jobs.

### Connection Example

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/jobs/${jobId}/logs`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'log') {
    console.log(`[${data.data.level}] ${data.data.message}`);
  }
};
```

### Message Types Received

#### `log` - Log Entry

```json
{
  "type": "log",
  "data": {
    "timestamp": "2026-01-25T10:32:05Z",
    "level": "INFO",
    "message": "Processing batch 2/3",
    "context": {
      "batch_id": "abc123"
    }
  }
}
```

| Log Level | Description                |
| --------- | -------------------------- |
| `DEBUG`   | Detailed diagnostic info   |
| `INFO`    | General operational info   |
| `WARNING` | Potential issues           |
| `ERROR`   | Errors that need attention |

---

## Connection Lifecycle

### Connection States

1. **Connecting**: WebSocket upgrade request received
2. **Authenticating**: Validating API key or token
3. **Active**: Connected and receiving messages
4. **Idle**: No recent client messages
5. **Timeout**: Idle timeout exceeded (300s default)
6. **Disconnecting**: Graceful cleanup in progress

### Server Heartbeat

The server sends periodic ping messages to keep connections alive:

```json
{
  "type": "ping",
  "lastSeq": 42
}
```

The `lastSeq` field contains the current sequence number for gap detection.

**Client should respond with:**

```json
{ "type": "pong" }
```

### Configuration

| Setting                           | Default | Description                  |
| --------------------------------- | ------- | ---------------------------- |
| `websocket_ping_interval_seconds` | 30      | Heartbeat interval (seconds) |
| `websocket_idle_timeout_seconds`  | 300     | Connection idle timeout      |

### Reconnection

Frontend uses exponential backoff:

- **Attempts**: 15 (default)
- **Base interval**: 1 second
- **Max interval**: 30 seconds
- **Total retry window**: ~8+ minutes

---

## Message Sequencing

All messages include sequence numbers for reliable delivery:

```json
{
  "type": "event",
  "sequence": 42,
  "requires_ack": true,
  "data": { ... }
}
```

| Field          | Description                                    |
| -------------- | ---------------------------------------------- |
| `sequence`     | Monotonically increasing sequence number       |
| `requires_ack` | True if message requires client acknowledgment |

**Note**: Messages with `risk_score >= 80` or `risk_level == 'critical'` require acknowledgment.

---

## Error Handling

### Error Response Format

```json
{
  "type": "error",
  "error": "invalid_json",
  "message": "Message must be valid JSON",
  "details": {
    "raw_data_preview": "..."
  }
}
```

### Error Codes

| Code                     | Meaning                      | Recovery           |
| ------------------------ | ---------------------------- | ------------------ |
| `invalid_json`           | Message is not valid JSON    | Fix message format |
| `invalid_message_format` | Message doesn't match schema | Check schema       |
| `unknown_message_type`   | Unknown message type         | Update client      |
| `validation_error`       | Payload validation failed    | Check field values |

### WebSocket Close Codes

| Code | Name             | When Used                    |
| ---- | ---------------- | ---------------------------- |
| 1000 | Normal Closure   | Idle timeout, graceful close |
| 1008 | Policy Violation | Auth failed, rate limited    |
| 1011 | Internal Error   | Unexpected exception         |

---

## Backend Event Type Registry

The backend defines a comprehensive event type registry in `backend/core/websocket/event_types.py`:

### Event Domains

| Domain      | Description                             |
| ----------- | --------------------------------------- |
| `alert`     | Alert notifications and state changes   |
| `camera`    | Camera status and configuration changes |
| `job`       | Background job lifecycle events         |
| `system`    | System health and status events         |
| `event`     | Security event lifecycle (AI-analyzed)  |
| `detection` | Raw AI detection events                 |
| `worker`    | Pipeline worker lifecycle               |

### Event Channels

| Channel      | Event Types Included        |
| ------------ | --------------------------- |
| `alerts`     | alert.\*, prometheus.alert  |
| `cameras`    | camera.\*                   |
| `jobs`       | job.\*                      |
| `system`     | system._, service._, gpu.\* |
| `events`     | event._, scene_change._     |
| `detections` | detection.\*                |
| `workers`    | worker.\*                   |

---

## Related Documentation

- [WebSocket Message Contracts](../developer/api/websocket-contracts.md) - Detailed message schemas
- [WebSocket Server Architecture](../architecture/realtime-system/websocket-server.md) - Server implementation details
- [WebSocket Message Flow](../architecture/dataflows/websocket-message-flow.md) - Data flow diagrams

---

**Version**: 1.0
**Last Updated**: 2026-01-25
**Status**: Active
