# WebSocket Message Contracts

## Overview

This document specifies the exact message formats for all WebSocket communication between frontend and backend. These contracts ensure type safety and enable validation testing across protocol boundaries.

The frontend implements a **typed event emitter pattern** for type-safe WebSocket message handling, with compile-time type checking for event subscriptions and payloads.

## WebSocket Endpoints

The system exposes two dedicated WebSocket channels:

| Endpoint     | Purpose                                    | Update Frequency |
| ------------ | ------------------------------------------ | ---------------- |
| `/ws/events` | Security events, detections, scene changes | Real-time        |
| `/ws/system` | System status, GPU metrics, service health | Every 5 seconds  |

### Connection URLs

```
Events Channel: ws://localhost:8000/ws/events
System Channel: ws://localhost:8000/ws/system
```

### Authentication

Two authentication methods are supported (both optional, can be used together):

1. **API Key Authentication** (when `api_key_enabled=true`):

   - Query parameter: `ws://host/ws/events?api_key=YOUR_KEY`
   - Sec-WebSocket-Protocol header: `api-key.YOUR_KEY`

2. **Token Authentication** (when `WEBSOCKET_TOKEN` is configured):
   - Query parameter: `ws://host/ws/events?token=YOUR_TOKEN`

Connections without valid authentication (when required) will be rejected with code 1008 (Policy Violation).

## Connection Lifecycle

### Handshake

1. Client initiates WebSocket upgrade to `/ws/events` or `/ws/system`
2. Server validates authentication (if enabled)
3. Server accepts connection
4. For `/ws/system`: Server sends initial system status immediately

### Server-Initiated Heartbeat

- Server sends `{"type":"ping"}` every 30 seconds (configurable via `websocket_ping_interval_seconds`)
- Client should respond with `{"type":"pong"}`
- Keeps connections alive through proxies/load balancers

### Client Keepalive

- Client can send `{"type":"ping"}` at any time
- Server responds with `{"type":"pong"}`
- Legacy string `"ping"` also supported for backward compatibility

### Idle Timeout

- Connections without messages for 300 seconds (configurable) are automatically closed
- Send periodic ping messages to keep connections alive

### Graceful Reconnection

The frontend implements exponential backoff with jitter:

- Default: 15 reconnection attempts
- Base interval: 1 second
- Max interval: 30 seconds
- Provides ~8+ minutes of retry window for backend restarts

## Message Envelope Format

All WebSocket messages follow this envelope structure:

```typescript
interface WebSocketMessage<T = unknown> {
  // Message type discriminant - determines payload schema
  type: string;

  // Actual message content (type-specific schema)
  data: T;

  // Optional: Timestamp (ISO 8601) - present on some message types
  timestamp?: string;
}
```

**Note:** Unlike some WebSocket implementations, messages do NOT include `id` fields. Deduplication is handled client-side using event IDs when applicable.

## Typed Event Emitter Pattern

The frontend uses a `TypedWebSocketEmitter` class for type-safe WebSocket message handling. This provides compile-time type checking for event names and their associated payload types.

### Event Map Definition

```typescript
// frontend/src/types/websocket-events.ts

interface WebSocketEventMap {
  /** Security event from the events channel */
  event: SecurityEventData;
  /** Service status update (e.g., AI service health) */
  service_status: ServiceStatusData;
  /** System status broadcast */
  system_status: SystemStatusData;
  /** Server heartbeat ping */
  ping: HeartbeatPayload;
  /** GPU statistics */
  gpu_stats: GpuStatsPayload;
  /** WebSocket error */
  error: WebSocketErrorPayload;
  /** Pong response */
  pong: PongPayload;
}

// All valid event keys
type WebSocketEventKey = keyof WebSocketEventMap;
// 'event' | 'service_status' | 'system_status' | 'ping' | 'gpu_stats' | 'error' | 'pong'
```

### TypedWebSocketEmitter Class

```typescript
// frontend/src/hooks/typedEventEmitter.ts

class TypedWebSocketEmitter {
  // Subscribe to an event with type-safe handler
  on<K extends WebSocketEventKey>(
    event: K,
    handler: (data: WebSocketEventMap[K]) => void
  ): () => void;

  // Unsubscribe from an event
  off<K extends WebSocketEventKey>(event: K, handler: (data: WebSocketEventMap[K]) => void): void;

  // Emit an event with typed payload
  emit<K extends WebSocketEventKey>(event: K, data: WebSocketEventMap[K]): void;

  // Subscribe to an event that fires only once
  once<K extends WebSocketEventKey>(
    event: K,
    handler: (data: WebSocketEventMap[K]) => void
  ): () => void;

  // Handle raw WebSocket message by extracting type and emitting
  handleMessage(message: unknown): boolean;

  // Utility methods
  has(event: WebSocketEventKey): boolean;
  listenerCount(event: WebSocketEventKey): number;
  removeAllListeners(event: WebSocketEventKey): void;
  clear(): void;
  events(): WebSocketEventKey[];
}
```

### Usage Example

```typescript
import { TypedWebSocketEmitter } from './typedEventEmitter';

const emitter = new TypedWebSocketEmitter();

// Type-safe subscription - TypeScript knows the payload type
const unsubscribe = emitter.on('event', (data) => {
  // data is typed as SecurityEventData
  console.log(data.risk_score); // OK
  console.log(data.invalid); // TypeScript error!
});

// Handle raw WebSocket messages
ws.onmessage = (e) => {
  const message = JSON.parse(e.data);
  emitter.handleMessage(message); // Routes to correct handler
};

// Cleanup
unsubscribe();
```

### Typed Subscription Integration

The `createTypedSubscription` function combines connection management with typed events:

```typescript
import { createTypedSubscription } from './webSocketManager';

const subscription = createTypedSubscription(
  'ws://localhost:8000/ws/events',
  {
    reconnect: true,
    reconnectInterval: 1000,
    maxReconnectAttempts: 15,
    connectionTimeout: 10000,
    autoRespondToHeartbeat: true,
  },
  {
    onOpen: () => console.log('Connected'),
    onClose: () => console.log('Disconnected'),
  }
);

// Type-safe event subscription
subscription.on('event', (data) => {
  console.log(`Risk: ${data.risk_score}, Camera: ${data.camera_id}`);
});

subscription.on('system_status', (data) => {
  console.log(`GPU: ${data.gpu.utilization}%`);
});

// Cleanup
subscription.unsubscribe();
```

## Message Types

### Events Channel (`/ws/events`)

#### `event` - Security Event

**Direction:** Server → Client
**When:** New security event is created (after AI analysis)

```typescript
interface SecurityEventData {
  id: string | number; // Unique event identifier
  event_id?: number; // Legacy alias for id (backward compatibility)
  batch_id?: string; // Detection batch identifier
  camera_id: string; // Normalized camera ID (e.g., "front_door")
  camera_name?: string; // Human-readable camera name
  risk_score: number; // AI-determined risk score (0-100)
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  summary: string; // AI-generated event summary
  timestamp?: string; // Event timestamp (ISO 8601)
  started_at?: string; // When the event started (ISO 8601)
}
// Note: The backend sends a 'reasoning' field with LLM analysis, but the
// frontend SecurityEventData type does not currently include it. If you need
// the reasoning field, access it from the raw message data.

// Message envelope
interface EventMessage {
  type: 'event';
  data: SecurityEventData;
}
```

**Example payload:**

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
    "started_at": "2026-01-09T12:00:00Z"
  }
}
```

> **Backend also sends:** The backend includes additional fields like `reasoning` (LLM analysis)
> in the actual message. See `backend/api/schemas/websocket.py` for the complete backend schema.

#### `scene_change` - Camera View Change

**Direction:** Server → Client
**When:** Camera view change or tampering is detected

> **Note:** This message type is defined in the backend schema but is NOT currently
> included in the frontend `WebSocketEventMap`. If you need to handle scene_change
> messages, you'll need to process them manually from raw WebSocket messages or
> extend the typed event emitter.

```typescript
interface SceneChangeData {
  id: number; // Unique scene change identifier
  camera_id: string; // Normalized camera ID
  detected_at: string; // ISO 8601 timestamp
  change_type: 'view_blocked' | 'angle_changed' | 'view_tampered' | 'unknown';
  similarity_score: number; // SSIM score (0-1, lower = more different)
}

interface SceneChangeMessage {
  type: 'scene_change';
  data: SceneChangeData;
}
```

#### `service_status` - Service Health Update

**Direction:** Server → Client
**When:** AI service status changes (via health monitor)

```typescript
// Backend sends these status values:
type ServiceStatus = 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed';

// Frontend defines ContainerStatus (note: values differ from backend ServiceStatus):
type ContainerStatus = 'running' | 'starting' | 'unhealthy' | 'stopped' | 'error' | 'unknown';

interface ServiceStatusData {
  service: string; // Service name (redis, rtdetr, nemotron)
  status: ServiceStatus | ContainerStatus; // Status from either backend or container orchestrator
  message?: string; // Optional descriptive message
}

interface ServiceStatusMessage {
  type: 'service_status';
  data: ServiceStatusData;
  timestamp: string; // ISO 8601
}
```

### System Channel (`/ws/system`)

#### `system_status` - Full System Status

**Direction:** Server → Client
**When:** Periodic broadcast (every 5 seconds)

```typescript
interface GpuStatusData {
  utilization: number | null; // GPU utilization percentage (0-100)
  memory_used: number | null; // GPU memory used in bytes
  memory_total: number | null; // Total GPU memory in bytes
  temperature: number | null; // GPU temperature in Celsius
  inference_fps: number | null; // Current inference FPS
}

interface CameraStatusData {
  active: number; // Number of active/online cameras
  total: number; // Total configured cameras
}

interface QueueStatusData {
  pending: number; // Items pending processing
  processing: number; // Items currently being processed
}

type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

interface SystemStatusData {
  gpu: GpuStatusData;
  cameras: CameraStatusData;
  queue: QueueStatusData;
  health: HealthStatus;
}

interface SystemStatusMessage {
  type: 'system_status';
  data: SystemStatusData;
  timestamp: string; // ISO 8601
}
```

**Example payload:**

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
  "timestamp": "2026-01-09T10:30:00.000Z"
}
```

#### `performance_update` - Detailed Performance Metrics

**Direction:** Server → Client
**When:** Periodic broadcast with detailed metrics (via PerformanceCollector)

```typescript
interface PerformanceUpdate {
  timestamp: string;
  gpu: GpuMetrics | null;
  ai_models: Record<string, AIModelMetrics>;
  nemotron: NemotronMetrics | null;
  inference: InferenceMetrics | null;
  databases: Record<string, DatabaseMetrics>;
  host: HostMetrics | null;
  containers: ContainerMetrics[];
  alerts: PerformanceAlert[];
}

interface PerformanceUpdateMessage {
  type: 'performance_update';
  data: PerformanceUpdate;
}
```

#### `circuit_breaker_update` - Circuit Breaker States

**Direction:** Server → Client
**When:** Circuit breaker state changes or periodic broadcast

```typescript
interface CircuitBreakerUpdate {
  timestamp: string;
  summary: {
    total: number;
    open: number;
    half_open: number;
    closed: number;
  };
  breakers: Record<
    string,
    {
      state: 'closed' | 'open' | 'half_open';
      failure_count: number;
    }
  >;
}

interface CircuitBreakerMessage {
  type: 'circuit_breaker_update';
  data: CircuitBreakerUpdate;
}
```

### Bidirectional Messages

#### `ping` / `pong` - Heartbeat

**Direction:** Bidirectional

```typescript
interface HeartbeatMessage {
  type: 'ping';
}

interface PongMessage {
  type: 'pong';
}
```

The server sends `ping` every 30 seconds. Clients should respond with `pong`. Clients can also initiate ping/pong for connection health checks.

#### `error` - Error Response

**Direction:** Server → Client
**When:** Message validation or processing fails

```typescript
interface ErrorMessage {
  type: 'error';
  code?: string; // Error code for programmatic handling
  message: string; // Human-readable error message
  details?: Record<string, unknown>;
}
```

**Error Codes:**

| Code                     | Meaning                      | Recovery           |
| ------------------------ | ---------------------------- | ------------------ |
| `invalid_json`           | Message is not valid JSON    | Fix message format |
| `invalid_message_format` | Message doesn't match schema | Check schema       |
| `unknown_message_type`   | Unknown message type         | Update client      |
| `validation_error`       | Payload validation failed    | Check field values |

### Client → Server Messages

#### `subscribe` / `unsubscribe` - Channel Filtering (Future)

```typescript
interface SubscribeMessage {
  type: 'subscribe';
  channels: string[]; // Channel names (max 10)
}

interface UnsubscribeMessage {
  type: 'unsubscribe';
  channels: string[];
}
```

**Note:** Subscription filtering is reserved for future use. Currently, all connected clients receive all messages for their channel.

## Discriminated Union Types

The frontend uses TypeScript discriminated unions for exhaustive message handling:

```typescript
// All messages from /ws/events channel
type EventsChannelMessage = EventMessage | HeartbeatMessage | ErrorMessage;

// All messages from /ws/system channel
type SystemChannelMessage =
  | SystemStatusMessage
  | ServiceStatusMessage
  | HeartbeatMessage
  | ErrorMessage;

// All possible WebSocket messages
type WebSocketMessage =
  | EventMessage
  | SystemStatusMessage
  | ServiceStatusMessage
  | HeartbeatMessage
  | PongMessage
  | ErrorMessage;
```

### Type Guards

```typescript
// frontend/src/types/websocket.ts

function isEventMessage(value: unknown): value is EventMessage;
function isSystemStatusMessage(value: unknown): value is SystemStatusMessage;
function isServiceStatusMessage(value: unknown): value is ServiceStatusMessage;
function isHeartbeatMessage(value: unknown): value is HeartbeatMessage;
function isPongMessage(value: unknown): value is PongMessage;
function isErrorMessage(value: unknown): value is ErrorMessage;
function isWebSocketMessage(value: unknown): value is WebSocketMessage;
```

### Exhaustive Pattern Matching

```typescript
import { assertNever } from '../types/websocket';

function handleMessage(message: WebSocketMessage) {
  switch (message.type) {
    case 'event':
      // message.data is typed as SecurityEventData
      console.log(message.data.risk_score);
      break;
    case 'system_status':
      // message.data is typed as SystemStatusData
      console.log(message.data.gpu.utilization);
      break;
    case 'service_status':
      console.log(message.data.service, message.data.status);
      break;
    case 'ping':
      // Send pong response
      break;
    case 'pong':
      // Heartbeat acknowledged
      break;
    case 'error':
      console.error(message.message);
      break;
    default:
      // TypeScript will error if any case is missed
      assertNever(message);
  }
}
```

## React Hook Usage

### useEventStream

```typescript
import { useEventStream } from './hooks';

function EventList() {
  const { events, isConnected, latestEvent, clearEvents } = useEventStream();

  return (
    <div>
      <p>Status: {isConnected ? 'Connected' : 'Disconnected'}</p>
      {latestEvent && (
        <p>Latest: {latestEvent.summary} (Risk: {latestEvent.risk_score})</p>
      )}
      <ul>
        {events.map((e) => (
          <li key={e.id}>{e.summary}</li>
        ))}
      </ul>
    </div>
  );
}
```

### useSystemStatus

```typescript
import { useSystemStatus } from './hooks';

function SystemStatusPanel() {
  const { status, isConnected } = useSystemStatus();

  if (!status) return <p>Loading...</p>;

  return (
    <div>
      <p>Health: {status.health}</p>
      <p>GPU: {status.gpu_utilization ?? 'N/A'}%</p>
      <p>Active Cameras: {status.active_cameras}</p>
    </div>
  );
}
```

### useWebSocket (Low-level)

```typescript
import { useWebSocket } from './hooks';

function CustomWebSocket() {
  const {
    isConnected,
    lastMessage,
    send,
    hasExhaustedRetries,
    reconnectCount,
    lastHeartbeat,
  } = useWebSocket({
    url: 'ws://localhost:8000/ws/events',
    onMessage: (data) => console.log('Received:', data),
    onHeartbeat: () => console.log('Heartbeat received'),
    reconnect: true,
    reconnectInterval: 1000,
    reconnectAttempts: 15,
    connectionTimeout: 10000,
    autoRespondToHeartbeat: true,
  });

  return (
    <div>
      <p>Connected: {isConnected ? 'Yes' : 'No'}</p>
      <p>Reconnect attempts: {reconnectCount}</p>
      <p>Last heartbeat: {lastHeartbeat?.toISOString()}</p>
    </div>
  );
}
```

## Validation Rules

### Message Timestamps

- Must be ISO 8601 format: `YYYY-MM-DDTHH:mm:ss.fffZ`
- UTC timezone only
- Server timestamps may differ slightly from client (clock skew tolerance: 5 seconds)

### Numeric Fields

- GPU utilization: 0-100 (inclusive, percentage)
- Memory values: bytes (positive integers)
- Confidence scores: 0.0-1.0 (inclusive)
- Risk scores: 0-100 (inclusive, integer)
- Temperature: Celsius (typically 0-100)

### String Fields

- `camera_id`: Alphanumeric + underscores, max 50 chars
- `risk_level`: Must be one of: `low`, `medium`, `high`, `critical`
- `summary`, `reasoning`: UTF-8, max 2000 chars

### Validation Errors

Invalid messages receive an error response:

```json
{
  "type": "error",
  "error": "invalid_message_format",
  "message": "Message does not match expected schema",
  "details": {
    "validation_errors": [{ "loc": ["data", "risk_score"], "msg": "value is not a valid integer" }]
  }
}
```

## Connection Management

### WebSocketManager

The frontend uses a singleton `WebSocketManager` for connection deduplication:

- Multiple components subscribing to the same URL share one connection
- Reference counting ensures connection closes only when all subscribers disconnect
- Automatic reconnection with exponential backoff

### Connection States

```typescript
type ConnectionState = 'connected' | 'disconnected' | 'reconnecting';

interface ChannelStatus {
  name: string;
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastMessageTime: Date | null;
}
```

## Performance Considerations

- Messages are JSON compact (no pretty-printing in production)
- Batch operations use grouped messages instead of individual updates
- GPU/system stats throttled to 5-10 second intervals
- Client should debounce rapid updates using `useThrottledValue`
- Event buffer limited to 100 most recent events to prevent memory issues

## Backward Compatibility

- New message types can be added without breaking existing clients
- Clients MUST ignore unknown message types (use `assertNeverSoft` for logging)
- Payload fields can be added but never removed or renamed
- Legacy string `"ping"` still supported alongside `{"type":"ping"}`
- `event_id` field maintained alongside `id` for backward compatibility

---

**Version:** 2.0
**Last Updated:** 2026-01-09
**Status:** Stable

## Related Files

| File                                      | Purpose                                 |
| ----------------------------------------- | --------------------------------------- |
| `frontend/src/types/websocket.ts`         | Discriminated union types, type guards  |
| `frontend/src/types/websocket-events.ts`  | Event map, typed event utilities        |
| `frontend/src/hooks/typedEventEmitter.ts` | TypedWebSocketEmitter class             |
| `frontend/src/hooks/webSocketManager.ts`  | Connection manager, typed subscriptions |
| `frontend/src/hooks/useWebSocket.ts`      | Low-level WebSocket hook                |
| `frontend/src/hooks/useEventStream.ts`    | Events channel hook                     |
| `frontend/src/hooks/useSystemStatus.ts`   | System channel hook                     |
| `backend/api/routes/websocket.py`         | Server WebSocket endpoints              |
| `backend/api/schemas/websocket.py`        | Pydantic message schemas                |
| `backend/services/event_broadcaster.py`   | Event broadcasting service              |
| `backend/services/system_broadcaster.py`  | System status broadcasting service      |
