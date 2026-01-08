# WebSocket Message Contracts

## Overview

This document specifies the exact message formats for all WebSocket communication between frontend and backend. These contracts ensure type safety and enable validation testing across protocol boundaries.

## WebSocket Endpoint

**URL:** `ws://localhost:8000/ws`

**Authentication:** None (local single-user deployment)

**Upgrade Headers:**

```
GET /ws HTTP/1.1
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: ...
Sec-WebSocket-Version: 13
```

## Connection Lifecycle

### Handshake

1. Client initiates WebSocket upgrade to `/ws`
2. Server accepts connection
3. Server sends initial `connected` message

### Keepalive

- Client sends ping every 30 seconds
- Server responds with pong
- If no pong within 10 seconds, client reconnects

### Graceful Shutdown

- Server sends `shutdown` message before closing
- Client gracefully closes after cleanup
- Automatic reconnection on unexpected close

## Message Format

All WebSocket messages follow this envelope structure:

```typescript
interface WebSocketMessage<T = unknown> {
  // Message type - determines how to parse payload
  type: string;

  // Timestamp when message was created (ISO 8601)
  timestamp: string;

  // Unique message ID for correlation/deduplication
  id: string;

  // Actual message content (type-specific schema)
  data: T;

  // Optional: Error details if type='error'
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
```

## Message Types

### Connection Management

#### `connected`

**Direction:** Server → Client
**When:** Upon successful WebSocket handshake

```typescript
interface ConnectedMessage {
  type: 'connected';
  timestamp: string;
  id: string;
  data: {
    client_id: string; // Unique client identifier
    server_time: string; // Server's current time (ISO 8601)
    protocol_version: string; // e.g., "1.0"
    features: string[]; // Supported features
  };
}
```

#### `ping`

**Direction:** Client → Server
**When:** Every 30 seconds (client-side keepalive)

```typescript
interface PingMessage {
  type: 'ping';
  timestamp: string;
  id: string;
  data: {
    // Empty
  };
}
```

**Server Response:**

```typescript
interface PongMessage {
  type: 'pong';
  timestamp: string;
  id: string; // Echoes ping ID for correlation
  data: {
    // Empty
  };
}
```

#### `shutdown`

**Direction:** Server → Client
**When:** Server is shutting down gracefully

```typescript
interface ShutdownMessage {
  type: 'shutdown';
  timestamp: string;
  id: string;
  data: {
    reason: string; // e.g., "maintenance", "restart"
    grace_period_ms: number; // Milliseconds until hard close
  };
}
```

### Real-time Data Updates

#### `event:new`

**Direction:** Server → Client
**When:** New event is created

```typescript
interface EventNewMessage {
  type: 'event:new';
  timestamp: string;
  id: string;
  data: {
    id: number;
    camera_id: string;
    started_at: string; // ISO 8601
    ended_at: string; // ISO 8601
    risk_score: number; // 0-100
    risk_level: 'low' | 'medium' | 'high' | 'critical';
    summary: string;
    reasoning: string;
    object_types: string[]; // e.g., ["person", "dog"]
  };
}
```

#### `event:updated`

**Direction:** Server → Client
**When:** Event is updated (reviewed, notes added, etc.)

```typescript
interface EventUpdatedMessage {
  type: 'event:updated';
  timestamp: string;
  id: string;
  data: {
    event_id: number;
    changes: {
      reviewed?: boolean;
      notes?: string | null;
      risk_score?: number;
    };
  };
}
```

#### `detection:new`

**Direction:** Server → Client
**When:** New detection is created

```typescript
interface DetectionNewMessage {
  type: 'detection:new';
  timestamp: string;
  id: string;
  data: {
    id: number;
    camera_id: string;
    detected_at: string; // ISO 8601
    object_type: string; // e.g., "person"
    confidence: number; // 0.0-1.0
    bbox: {
      x: number;
      y: number;
      width: number;
      height: number;
    };
    file_path: string;
    media_type: 'image' | 'video';
  };
}
```

#### `detections:batch`

**Direction:** Server → Client
**When:** Multiple detections in same batch window (90 seconds)

```typescript
interface DetectionsBatchMessage {
  type: 'detections:batch';
  timestamp: string;
  id: string;
  data: {
    camera_id: string;
    batch_id: string;
    detection_count: number;
    detections: Array<{
      id: number;
      object_type: string;
      confidence: number;
    }>;
  };
}
```

#### `gpu:stats`

**Direction:** Server → Client
**When:** GPU metrics are updated (every 10 seconds)

```typescript
interface GPUStatsMessage {
  type: 'gpu:stats';
  timestamp: string;
  id: string;
  data: {
    gpu_name: string;
    gpu_utilization: number; // Percentage 0-100
    memory_used: number; // MB
    memory_total: number; // MB
    memory_percent: number; // Percentage 0-100
    temperature: number; // Celsius
    power_usage: number; // Watts
    inference_fps: number; // Detections per second
  };
}
```

#### `status:ready`

**Direction:** Server → Client
**When:** All services are operational

```typescript
interface StatusReadyMessage {
  type: 'status:ready';
  timestamp: string;
  id: string;
  data: {
    database: 'healthy' | 'degraded' | 'unhealthy';
    redis: 'healthy' | 'degraded' | 'unhealthy';
    gpu: 'healthy' | 'degraded' | 'unavailable';
  };
}
```

#### `status:warning`

**Direction:** Server → Client
**When:** Service degradation detected

```typescript
interface StatusWarningMessage {
  type: 'status:warning';
  timestamp: string;
  id: string;
  data: {
    service: string; // e.g., "gpu", "redis", "database"
    issue: string; // Human-readable description
    severity: 'warning' | 'critical';
  };
}
```

### System Events

#### `system:alert`

**Direction:** Server → Client
**When:** Alert condition triggered

```typescript
interface SystemAlertMessage {
  type: 'system:alert';
  timestamp: string;
  id: string;
  data: {
    alert_id: string;
    rule_id: number;
    severity: 'info' | 'warning' | 'critical';
    title: string;
    description: string;
    condition: string; // Rule that triggered alert
  };
}
```

#### `queue:depth`

**Direction:** Server → Client
**When:** Processing queue depth changes (batch processing)

```typescript
interface QueueDepthMessage {
  type: 'queue:depth';
  timestamp: string;
  id: string;
  data: {
    queue_name: string; // e.g., "detections", "processing"
    depth: number;
    max_depth: number;
    wait_time_ms: number; // Estimated time to process queue
  };
}
```

#### `pipeline:latency`

**Direction:** Server → Client
**When:** Pipeline latency metrics updated

```typescript
interface PipelineLatencyMessage {
  type: 'pipeline:latency';
  timestamp: string;
  id: string;
  data: {
    stage: string; // e.g., "detection", "analysis", "storage"
    latency_ms: number;
    p95_latency_ms: number;
    p99_latency_ms: number;
  };
}
```

### Error Handling

#### `error`

**Direction:** Either direction
**When:** An error occurs during message processing

```typescript
interface ErrorMessage {
  type: 'error';
  timestamp: string;
  id: string;
  data: {
    // Empty - use envelope.error field
  };
  error: {
    code: string; // e.g., "INVALID_MESSAGE", "INTERNAL_ERROR"
    message: string;
    details?: {
      field?: string; // For validation errors
      expected?: string;
      received?: string;
    };
  };
}
```

**Error Codes:**

| Code                  | Meaning                | Recovery          |
| --------------------- | ---------------------- | ----------------- |
| `PROTOCOL_ERROR`      | Invalid message format | Reconnect         |
| `INVALID_MESSAGE`     | Message parsing failed | Check format      |
| `UNAUTHORIZED`        | Auth failed            | N/A (no auth)     |
| `SERVER_ERROR`        | Server error           | Reconnect         |
| `TIMEOUT`             | Request timeout        | Retry             |
| `SUBSCRIPTION_FAILED` | Cannot subscribe       | Check permissions |

## Subscription Model

The server broadcasts all messages to all connected clients. Clients can optionally subscribe to specific message types.

### Client Subscription Filter (Optional)

```typescript
interface SubscribeMessage {
  type: 'subscribe';
  timestamp: string;
  id: string;
  data: {
    channels: string[]; // Message types to receive
    // Examples:
    // - "event:*"        (all event messages)
    // - "detection:*"    (all detection messages)
    // - "gpu:stats"      (only GPU stats)
    // - "*"              (all messages, default)
  };
}
```

## Client Implementation Example

```typescript
// Establish connection
const ws = new WebSocket('ws://localhost:8000/ws');

// Handle incoming message
ws.onmessage = (event) => {
  const message: WebSocketMessage = JSON.parse(event.data);

  switch (message.type) {
    case 'connected':
      console.log('Connected:', message.data);
      break;

    case 'event:new':
      handleNewEvent(message as EventNewMessage);
      break;

    case 'detection:new':
      handleNewDetection(message as DetectionNewMessage);
      break;

    case 'gpu:stats':
      handleGPUStats(message as GPUStatsMessage);
      break;

    case 'error':
      handleError(message as ErrorMessage);
      break;
  }
};

// Send keepalive ping
setInterval(() => {
  ws.send(
    JSON.stringify({
      type: 'ping',
      timestamp: new Date().toISOString(),
      id: crypto.randomUUID(),
      data: {},
    })
  );
}, 30000);
```

## Validation Rules

### Message Timestamps

- Must be ISO 8601 format: `YYYY-MM-DDTHH:mm:ss.fffZ`
- Server timestamps may differ slightly from client (clock skew tolerance: 5 seconds)
- UTC timezone only

### Message IDs

- Must be UUID v4 format or similar unique string
- Used for deduplication across network boundaries
- Client should ignore duplicate IDs within 1-minute window

### Numeric Fields

- GPU percentages: 0-100 (inclusive)
- Confidence scores: 0.0-1.0 (inclusive)
- Risk scores: 0-100 (inclusive)
- Any out-of-range values indicate data corruption

### String Fields

- `camera_id`: Alphanumeric + underscores, max 50 chars
- `object_type`: Enum values only (person, dog, cat, etc.)
- Text fields (summary, reasoning): UTF-8, max 2000 chars

## Contract Testing

E2E contract tests validate these schemas:

```typescript
// frontend/tests/contract/api-contract.test.ts
test('event:new message matches schema', async ({ page }) => {
  const eventMessage = await page.waitForEvent('websocket', (msg) => msg.type === 'event:new');

  const data = JSON.parse(eventMessage.data);
  expect(data).toMatchSchema(EventNewMessageSchema);
});
```

## Message Format Validation

A message is valid if:

1. Envelope contains `type`, `timestamp`, `id`, `data`
2. Timestamp is ISO 8601 UTC
3. Type matches one of the defined types
4. Data matches type-specific schema
5. All required fields are present
6. No unknown fields in payload

## Backward Compatibility

- New message types can be added without breaking existing clients
- Clients must ignore unknown message types
- Payload fields can be added but never removed or renamed
- Schema changes bump protocol version in `connected` message

## Performance Considerations

- Messages should be JSON compact (no pretty-printing)
- Batch operations use `detections:batch` instead of individual `detection:new`
- GPU stats throttled to 10-second intervals to avoid client overload
- Client should debounce rapid updates (e.g., GPU stats)

---

**Version:** 1.0
**Last Updated:** 2026-01-08
**Status:** Stable

See also:

- `frontend/src/types/websocket.ts` - TypeScript definitions
- `backend/api/routes/websocket.py` - Server implementation
- `frontend/tests/e2e/specs/websocket.spec.ts` - E2E tests
