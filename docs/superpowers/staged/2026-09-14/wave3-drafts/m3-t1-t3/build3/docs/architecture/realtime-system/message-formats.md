# Message Formats

Documentation for WebSocket message schemas and JSON formats.

**Source**: `backend/api/schemas/websocket.py`

## Overview

All WebSocket messages follow a consistent envelope format with a `type` field identifying the message kind and a `data` field containing the payload. Messages may include optional metadata fields like `seq` (sequence number) and `timestamp`.

## Base Message Format

```json
{
  "type": "message_type",
  "data": {
    /* payload specific to message type */
  },
  "seq": 42, // Optional: sequence number for ordering
  "timestamp": "...", // Optional: ISO 8601 timestamp
  "requires_ack": true // Optional: client should acknowledge high-priority messages
}
```

## Client-to-Server Messages

### Ping

Heartbeat message from client to server.

```json
{
  "type": "ping"
}
```

**Response**:

```json
{
  "type": "pong"
}
```

**Legacy Support**: Plain string `"ping"` is also accepted.

### Subscribe

Subscribe to specific event patterns.

```json
{
  "type": "subscribe",
  "data": {
    "events": ["alert.*", "camera.status_changed"]
  }
}
```

**Response**:

```json
{
  "action": "subscribed",
  "events": ["alert.*", "camera.status_changed"]
}
```

### Unsubscribe

Unsubscribe from event patterns.

```json
{
  "type": "unsubscribe",
  "data": {
    "events": ["alert.*"]
  }
}
```

**Response**:

```json
{
  "action": "unsubscribed",
  "events": ["alert.*"]
}
```

### Resync

Request message replay after detecting a sequence gap.

```json
{
  "type": "resync",
  "data": {
    "channel": "events",
    "last_sequence": 42
  }
}
```

**Response**:

```json
{
  "type": "resync_ack",
  "channel": "events",
  "last_sequence": 42
}
```

Followed by replayed messages with `"replay": true`.

### Acknowledge

Acknowledge receipt of a high-priority message.

```json
{
  "type": "ack",
  "data": {
    "seq": 42
  }
}
```

## Server-to-Client Messages

### Connected

Sent immediately after WebSocket connection is established.

```json
{
  "type": "connected",
  "message": "Connected to events channel",
  "connection_id": "ws-events-abc12345"
}
```

### Pong

Response to client ping.

```json
{
  "type": "pong"
}
```

### Server Ping

Server-initiated heartbeat (includes sequence for gap detection).

```json
{
  "type": "ping",
  "lastSeq": 42
}
```

### Error

Error notification for invalid messages or failed operations.

```json
{
  "type": "error",
  "error": "invalid_json",
  "message": "Message must be valid JSON",
  "details": {
    "raw_data_preview": "{invalid..."
  }
}
```

### Service Status

Broadcaster health and service status.

```json
{
  "type": "service_status",
  "data": {
    "service": "event_broadcaster",
    "status": "healthy",
    "message": "Event broadcasting active",
    "circuit_state": "closed"
  }
}
```

## Event Schemas

### Security Event (`type: "event"`)

Core security event from AI pipeline analysis.

```json
{
  "type": "event",
  "seq": 42,
  "data": {
    "id": 123,
    "camera_id": "front_door",
    "detected_at": "2026-01-09T12:00:00Z",
    "detection_type": "person",
    "risk_score": 85,
    "thumbnail_url": "/api/events/123/thumbnail",
    "video_clip_url": "/api/events/123/video",
    "llm_description": "Person detected at front entrance approaching door",
    "processing_time_ms": 1250
  }
}
```

**Data Fields**:

| Field                | Type   | Description                              |
| -------------------- | ------ | ---------------------------------------- |
| `id`                 | int    | Unique event identifier                  |
| `camera_id`          | string | Normalized camera ID                     |
| `detected_at`        | string | ISO 8601 detection timestamp             |
| `detection_type`     | string | Object class ("person", "vehicle", etc.) |
| `risk_score`         | int    | LLM-determined risk (0-100)              |
| `thumbnail_url`      | string | URL to event thumbnail                   |
| `video_clip_url`     | string | URL to video clip                        |
| `llm_description`    | string | AI-generated description                 |
| `processing_time_ms` | int    | Total pipeline processing time           |

### Camera Status (`type: "camera_status"`)

Camera online/offline status changes.

```json
{
  "type": "camera_status",
  "seq": 43,
  "data": {
    "event_type": "camera.offline",
    "camera_id": "front_door",
    "camera_name": "Front Door Camera",
    "status": "offline",
    "timestamp": "2026-01-09T10:30:00Z",
    "previous_status": "online",
    "reason": "No activity detected for 5 minutes",
    "details": null
  }
}
```

**Event Types**:

- `camera.online` - Camera became online
- `camera.offline` - Camera went offline
- `camera.status_changed` - Generic status change

**Status Values**:

- `online` - Camera is streaming
- `offline` - Camera is not responding
- `degraded` - Camera has issues but streaming

### Scene Change (`type: "scene_change"`)

Camera view tampering or angle change detected.

```json
{
  "type": "scene_change",
  "seq": 44,
  "data": {
    "id": 1,
    "camera_id": "front_door",
    "detected_at": "2026-01-03T10:30:00Z",
    "change_type": "view_blocked",
    "similarity_score": 0.23
  }
}
```

**Change Types**:

- `view_blocked` - Camera view obstructed
- `angle_changed` - Camera angle shifted
- `view_tampered` - Intentional tampering detected
- `unknown` - Unclassified change

### Detection New (`type: "detection.new"`)

Individual detection added to a batch.

```json
{
  "type": "detection.new",
  "seq": 45,
  "data": {
    "detection_id": 123,
    "batch_id": "batch_abc123",
    "camera_id": "front_door",
    "label": "person",
    "confidence": 0.95,
    "bbox": {
      "x": 0.25,
      "y": 0.15,
      "width": 0.1,
      "height": 0.25
    },
    "timestamp": "2026-01-13T12:00:00.000Z"
  }
}
```

### Detection Batch (`type: "detection.batch"`)

Batch closed and ready for analysis.

```json
{
  "type": "detection.batch",
  "seq": 46,
  "data": {
    "batch_id": "batch_abc123",
    "camera_id": "front_door",
    "detection_ids": [123, 124, 125],
    "detection_count": 3,
    "started_at": "2026-01-13T12:00:00.000Z",
    "closed_at": "2026-01-13T12:01:30.000Z",
    "close_reason": "timeout"
  }
}
```

**Close Reasons**:

- `timeout` - 90-second time window expired
- `idle` - 30-second idle timeout
- `max_size` - Maximum batch size reached

## Alert Schemas

### Alert Created (`type: "alert_created"`)

New alert triggered from rule evaluation.

```json
{
  "type": "alert_created",
  "seq": 47,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "event_id": 123,
    "rule_id": "550e8400-e29b-41d4-a716-446655440001",
    "severity": "high",
    "status": "pending",
    "dedup_key": "front_door:person:rule1",
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:00:00Z"
  }
}
```

**Severity Levels**:

- `low` - Informational
- `medium` - Attention needed
- `high` - Urgent attention
- `critical` - Immediate action required

**Status Values**:

- `pending` - Not yet delivered
- `delivered` - Sent to channels
- `acknowledged` - User saw it
- `dismissed` - User dismissed

### Alert Acknowledged (`type: "alert_acknowledged"`)

```json
{
  "type": "alert_acknowledged",
  "seq": 48,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "event_id": 123,
    "severity": "high",
    "status": "acknowledged",
    "dedup_key": "front_door:person:rule1",
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:01:00Z"
  }
}
```

### Alert Dismissed (`type: "alert_dismissed"`)

```json
{
  "type": "alert_dismissed",
  "seq": 49,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "event_id": 123,
    "severity": "high",
    "status": "dismissed",
    "dedup_key": "front_door:person:rule1",
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:02:00Z"
  }
}
```

### Alert Updated (`type: "alert_updated"`)

Alert metadata or channels modified.

```json
{
  "type": "alert_updated",
  "seq": 50,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "event_id": 123,
    "severity": "high",
    "status": "pending",
    "dedup_key": "front_door:person:rule1",
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:00:30Z"
  }
}
```

### Alert Deleted (`type: "alert_deleted"`)

Alert permanently removed.

```json
{
  "type": "alert_deleted",
  "seq": 51,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "reason": "Duplicate alert"
  }
}
```

### Alert Resolved (`type: "alert_resolved"`)

Alert resolved/cleared.

```json
{
  "type": "alert_resolved",
  "seq": 52,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "event_id": 123,
    "severity": "high",
    "status": "dismissed",
    "dedup_key": "front_door:person:rule1",
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:02:00Z"
  }
}
```

## Worker Status (`type: "worker_status"`)

Pipeline worker state changes.

```json
{
  "type": "worker_status",
  "seq": 53,
  "data": {
    "event_type": "worker.started",
    "worker_name": "detection_worker",
    "worker_type": "detection",
    "timestamp": "2026-01-13T10:30:00Z",
    "error": null,
    "error_type": null,
    "failure_count": null,
    "items_processed": null,
    "reason": null,
    "previous_state": null,
    "attempt": null,
    "max_attempts": null,
    "metadata": null
  },
  "timestamp": "2026-01-13T10:30:00Z"
}
```

**Worker Types**:

- `detection` - YOLO26 detection worker
- `analysis` - Nemotron analysis worker
- `timeout` - Batch timeout worker
- `metrics` - Metrics collection worker

**Event Types**:

- `worker.started` - Worker initialized
- `worker.stopped` - Worker shutdown
- `worker.error` - Worker encountered error
- `worker.restarted` - Worker recovered

## Infrastructure Alert (`type: "infrastructure_alert"`)

System-level alerts for infrastructure issues.

```json
{
  "type": "infrastructure_alert",
  "seq": 54,
  "data": {
    "alert_type": "gpu_high_temperature",
    "severity": "warning",
    "message": "GPU temperature exceeds threshold: 85C",
    "component": "gpu_0",
    "timestamp": "2026-01-13T10:30:00Z",
    "metadata": {
      "current_temp": 85,
      "threshold": 80
    }
  }
}
```

## Summary Update (`type: "summary_update"`)

Dashboard summary statistics.

```json
{
  "type": "summary_update",
  "seq": 55,
  "data": {
    "hourly": {
      "events_count": 42,
      "alerts_count": 3,
      "detections_count": 156,
      "avg_risk_score": 32.5
    },
    "daily": {
      "events_count": 328,
      "alerts_count": 18,
      "detections_count": 1245,
      "avg_risk_score": 28.7
    }
  }
}
```

## System Status (`type: "system_status"`)

Sent on `/ws/system` channel every 5 seconds.

```json
{
  "type": "system_status",
  "data": {
    "gpu": {
      "utilization": 45.2,
      "memory_used_mb": 4096,
      "memory_total_mb": 24576,
      "temperature": 62
    },
    "services": {
      "yolo26": "healthy",
      "nemotron": "healthy",
      "redis": "healthy",
      "postgres": "healthy"
    },
    "workers": {
      "detection": "running",
      "analysis": "running",
      "timeout": "running"
    },
    "queues": {
      "detection_queue": 5,
      "analysis_queue": 12
    }
  }
}
```

## Message Type Reference

| Type                   | Direction | Description               |
| ---------------------- | --------- | ------------------------- |
| `ping`                 | Both      | Heartbeat                 |
| `pong`                 | Server    | Heartbeat response        |
| `subscribe`            | Client    | Subscribe to patterns     |
| `unsubscribe`          | Client    | Unsubscribe from patterns |
| `resync`               | Client    | Request replay            |
| `resync_ack`           | Server    | Resync acknowledgment     |
| `ack`                  | Client    | Acknowledge message       |
| `connected`            | Server    | Connection established    |
| `error`                | Server    | Error notification        |
| `event`                | Server    | Security event            |
| `camera_status`        | Server    | Camera status change      |
| `scene_change`         | Server    | View tampering            |
| `detection.new`        | Server    | New detection             |
| `detection.batch`      | Server    | Batch closed              |
| `alert_created`        | Server    | Alert triggered           |
| `alert_acknowledged`   | Server    | Alert acknowledged        |
| `alert_dismissed`      | Server    | Alert dismissed           |
| `alert_updated`        | Server    | Alert modified            |
| `alert_deleted`        | Server    | Alert removed             |
| `alert_resolved`       | Server    | Alert resolved            |
| `worker_status`        | Server    | Worker state change       |
| `infrastructure_alert` | Server    | System alert              |
| `summary_update`       | Server    | Dashboard stats           |
| `system_status`        | Server    | System health             |
| `service_status`       | Server    | Broadcaster health        |

## Related Documentation

- [WebSocket Server](websocket-server.md) - Endpoint handling
- [EventBroadcaster](event-broadcaster.md) - Message broadcasting
- [SubscriptionManager](subscription-manager.md) - Event filtering
