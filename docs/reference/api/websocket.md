# WebSocket API

> Real-time streaming endpoints for events and system status.

**Time to read:** ~5 min
**Prerequisites:** [API Overview](overview.md)

---

## Overview

The WebSocket API provides real-time streaming of security events and system status updates. This enables dashboards to display live data without polling.

## Endpoints

### Event Stream

```
ws://localhost:8000/ws/events
```

Streams security events as they are detected and analyzed.

### System Status Stream

```
ws://localhost:8000/ws/system
```

Streams system status updates including GPU stats, queue depths, and health.

## Authentication

When `API_KEY_ENABLED=true`, provide your API key via:

**Query Parameter:**

```
ws://localhost:8000/ws/events?api_key=YOUR_KEY
```

**Sec-WebSocket-Protocol Header:**

```
Sec-WebSocket-Protocol: api-key.YOUR_KEY
```

## Message Formats

### Event Messages

```json
{
  "type": "event",
  "data": {
    "id": 1,
    "event_id": 1,
    "batch_id": "batch_abc123",
    "camera_id": "uuid-string",
    "risk_score": 75,
    "risk_level": "high",
    "summary": "Person detected at front door",
    "started_at": "2025-01-15T14:30:00Z"
  }
}
```

### System Status Messages

```json
{
  "type": "system_status",
  "data": {
    "gpu": {
      "utilization": 45.5,
      "memory_used": 8192,
      "memory_total": 24576,
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
  "timestamp": "2025-01-15T14:30:00.000Z"
}
```

### Server Heartbeat

Server sends periodic ping messages to keep connections alive:

```json
{ "type": "ping" }
```

## Client Messages

### Ping (Keep-Alive)

Send to keep connection alive and reset idle timeout:

```json
{ "type": "ping" }
```

**Response:**

```json
{ "type": "pong" }
```

**Legacy format also supported:**

```
ping
```

### Subscribe (Future)

```json
{
  "type": "subscribe",
  "data": {
    "channels": ["events", "system"]
  }
}
```

### Unsubscribe (Future)

```json
{
  "type": "unsubscribe",
  "data": {
    "channels": ["system"]
  }
}
```

## Error Messages

```json
{
  "error": "INVALID_JSON",
  "message": "Message must be valid JSON",
  "details": {
    "raw_data_preview": "not valid json..."
  }
}
```

Error codes:

| Code                     | Description                  |
| ------------------------ | ---------------------------- |
| `INVALID_JSON`           | Message is not valid JSON    |
| `INVALID_MESSAGE_FORMAT` | Message doesn't match schema |
| `UNKNOWN_MESSAGE_TYPE`   | Unrecognized message type    |

## Connection Lifecycle

1. **Connect** - Client initiates WebSocket connection
2. **Authenticate** - API key validated (if enabled)
3. **Register** - Connection registered with broadcaster
4. **Stream** - Events/status pushed to client
5. **Keep-Alive** - Client sends periodic pings
6. **Disconnect** - Connection closed and cleaned up

## Configuration

| Variable                          | Default | Description                                           |
| --------------------------------- | ------- | ----------------------------------------------------- |
| `WEBSOCKET_IDLE_TIMEOUT_SECONDS`  | 300     | Close after this many seconds without client messages |
| `WEBSOCKET_PING_INTERVAL_SECONDS` | 30      | Server heartbeat interval                             |
| `WEBSOCKET_MAX_MESSAGE_SIZE`      | 65536   | Maximum message size (64KB)                           |

## Rate Limiting

WebSocket connections are rate-limited:

- Default: 10 connections per minute per IP
- Configure via `RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE`
- Exceeding limit returns close code 1008 (Policy Violation)

## JavaScript Client Example

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/events");

ws.onopen = () => {
  console.log("Connected");
  // Send ping every 30 seconds to keep alive
  setInterval(() => ws.send('{"type":"ping"}'), 30000);
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === "event") {
    console.log("New event:", data.data);
    // Update UI with new event
  } else if (data.type === "pong") {
    console.log("Pong received");
  }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = (event) => {
  console.log("Disconnected:", event.code, event.reason);
  // Implement reconnection logic
};
```

## React Hook Example

```typescript
import { useEffect, useState } from "react";

function useEventStream(apiKey?: string) {
  const [events, setEvents] = useState<Event[]>([]);

  useEffect(() => {
    const url = apiKey
      ? `ws://localhost:8000/ws/events?api_key=${apiKey}`
      : "ws://localhost:8000/ws/events";

    const ws = new WebSocket(url);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "event") {
        setEvents((prev) => [data.data, ...prev]);
      }
    };

    return () => ws.close();
  }, [apiKey]);

  return events;
}
```

---

## Next Steps

- [Events API](events.md) - REST endpoint for historical events
- [System API](system.md) - REST endpoint for system status
- [Troubleshooting](../troubleshooting/connection-issues.md) - Connection problems
- Back to [API Overview](overview.md)
