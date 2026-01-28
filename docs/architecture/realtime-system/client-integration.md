# Client Integration

Documentation for frontend WebSocket hooks and connection management.

**Sources**:

- `frontend/src/hooks/useWebSocket.ts`
- `frontend/src/hooks/useEventStream.ts`
- `frontend/src/hooks/webSocketManager.ts`
- `frontend/src/components/common/ConnectionStatusBanner.tsx`
- `frontend/src/components/common/WebSocketStatus.tsx`

## Overview

The frontend uses React hooks for WebSocket connections, providing automatic reconnection, sequence tracking, and connection status UI. A singleton WebSocketManager prevents duplicate connections when multiple components subscribe.

## Core Hooks

### useWebSocket

The foundational WebSocket hook providing connection management and message handling.

```typescript
// frontend/src/hooks/useWebSocket.ts
export function useWebSocket<T = unknown>({
  url,
  onMessage,
  onOpen,
  onClose,
  onError,
  enabled = true,
  reconnect = true,
  reconnectInterval = 3000,
  maxReconnectAttempts = 5,
}: UseWebSocketOptions<T>): UseWebSocketResult;
```

**Options**:

| Option                 | Type     | Default  | Description                  |
| ---------------------- | -------- | -------- | ---------------------------- |
| `url`                  | string   | required | WebSocket endpoint URL       |
| `onMessage`            | function | -        | Message handler callback     |
| `onOpen`               | function | -        | Connection open callback     |
| `onClose`              | function | -        | Connection close callback    |
| `onError`              | function | -        | Error callback               |
| `enabled`              | boolean  | `true`   | Enable/disable connection    |
| `reconnect`            | boolean  | `true`   | Auto-reconnect on disconnect |
| `reconnectInterval`    | number   | `3000`   | Base reconnect delay (ms)    |
| `maxReconnectAttempts` | number   | `5`      | Max reconnect attempts       |

**Return Value**:

```typescript
interface UseWebSocketResult {
  isConnected: boolean;
  isReconnecting: boolean;
  reconnectAttempts: number;
  send: (data: string | object) => void;
  disconnect: () => void;
  connect: () => void;
  lastMessage: unknown | null;
  connectionState: ConnectionState;
}
```

**Usage Example**:

```typescript
const { isConnected, send, lastMessage } = useWebSocket({
  url: '/ws/events',
  onMessage: (event) => {
    console.log('Received:', event.data);
  },
  onOpen: () => {
    // Subscribe to specific events after connection
    send({ type: 'subscribe', data: { events: ['alert.*'] } });
  },
});
```

### useEventStream

Specialized hook for the `/ws/events` channel with built-in event deduplication and sequence validation.

```typescript
// frontend/src/hooks/useEventStream.ts
export function useEventStream(): UseEventStreamReturn;
```

**Return Value**:

```typescript
interface UseEventStreamReturn {
  events: SecurityEvent[]; // Array of received events (max 100, newest first)
  isConnected: boolean; // WebSocket connection status
  latestEvent: SecurityEvent | null; // Most recent event
  clearEvents: () => void; // Clear all events and reset state
  sequenceStats: SequenceStatistics; // Sequence validation metrics (NEM-1999)
}
```

**Features**:

| Feature                 | Description                                             |
| ----------------------- | ------------------------------------------------------- |
| **Deduplication**       | LRU cache prevents duplicate events (max 10,000 IDs)    |
| **Sequence Validation** | Detects gaps and requests resync from server (NEM-1999) |
| **Memory Bounded**      | Keeps only last 100 events, evicts old IDs from cache   |
| **Auto-reconnect**      | Built-in via underlying useWebSocket                    |

**Usage Example**:

```typescript
function EventList() {
  const { events, isConnected, latestEvent, clearEvents, sequenceStats } = useEventStream();

  return (
    <div>
      <p>Connected: {isConnected ? 'Yes' : 'No'}</p>
      <p>Events: {events.length}</p>
      <p>Duplicates blocked: {sequenceStats.duplicateCount}</p>
      <button onClick={clearEvents}>Clear</button>
      <ul>
        {events.map(event => (
          <li key={event.event_id ?? event.id}>{event.summary}</li>
        ))}
      </ul>
    </div>
  );
}
```

**Note**: This hook does not accept callback options. For custom message handling or routing by message type, use the lower-level `useWebSocket` hook directly.

## WebSocketManager

Singleton manager preventing duplicate connections when multiple components subscribe.

```typescript
// frontend/src/hooks/webSocketManager.ts
class WebSocketManager {
  private connections: Map<string, ManagedConnection>;
  private subscribers: Map<string, Set<Subscriber>>;

  subscribe(url: string, subscriber: Subscriber): () => void;
  send(url: string, data: string | object): void;
  getConnectionState(url: string): ConnectionState;
}
```

### Connection Deduplication

```mermaid
flowchart TD
    A[Component A calls useWebSocket] --> B{Connection exists?}
    B -->|No| C[Create WebSocket]
    B -->|Yes| D[Add subscriber]
    C --> D
    E[Component B calls useWebSocket] --> F{Connection exists?}
    F -->|Yes| G[Add subscriber]
    D --> H[Single WebSocket]
    G --> H
    H --> I[Messages broadcast to all subscribers]
```

### Subscriber Management

```typescript
// When component mounts
const unsubscribe = manager.subscribe('/ws/events', {
  onMessage: handleMessage,
  onStateChange: handleStateChange,
});

// When component unmounts
unsubscribe(); // Removes subscriber, closes connection if last
```

## Reconnection Flow

### Basic Reconnection Sequence

```mermaid
sequenceDiagram
    participant Client
    participant Manager
    participant Server

    Client->>Manager: connect()
    Manager->>Server: WebSocket upgrade
    Server-->>Manager: Connection open
    Manager-->>Client: onOpen callback

    Note over Manager,Server: Connection drops

    Server--xManager: Connection closed
    Manager->>Manager: Start reconnect timer

    loop Up to maxReconnectAttempts
        Manager->>Manager: Wait reconnectInterval * 2^attempt
        Manager->>Server: WebSocket upgrade
        alt Success
            Server-->>Manager: Connection open
            Manager->>Server: resync (last_sequence)
            Server-->>Manager: Replay missed messages
            Manager-->>Client: onOpen + replayed messages
        else Failure
            Server--xManager: Connection failed
            Manager->>Manager: Increment attempt
        end
    end

    alt All attempts exhausted
        Manager-->>Client: connectionState = 'failed'
    end
```

### Detailed Reconnection Flow with Backoff and State Resync

The following diagram shows the complete reconnection flow including disconnect detection mechanisms, exponential backoff calculation, and full state resynchronization.

```mermaid
sequenceDiagram
    participant C as Client
    participant M as WebSocketManager
    participant S as Server
    participant EB as EventBroadcaster

    Note over C,EB: Active Connection State
    C->>M: Receiving events (seq: 40, 41, 42...)
    M->>M: Track lastSequence = 42

    Note over C,EB: Disconnect Detection
    alt Server-initiated close
        S--xM: WebSocket close event
        M->>M: onClose triggered
    else Network failure
        M->>M: Heartbeat timeout (no pong)
        M->>M: Mark connection dead
    else Ping timeout
        S->>M: {"type": "ping", "lastSeq": 45}
        M--xS: No response (network issue)
        M->>M: Socket error detected
    end

    M->>M: Set connectionState = 'disconnected'
    M-->>C: onClose callback
    M->>M: Store disconnectedAt timestamp

    Note over C,EB: Exponential Backoff Loop
    rect rgb(255, 245, 230)
        M->>M: attempt = 0
        loop Until connected OR attempt >= maxReconnectAttempts
            M->>M: Set connectionState = 'reconnecting'
            M-->>C: Update UI (attempt X/Y)

            M->>M: Calculate delay = 3000 * 2^attempt
            Note right of M: attempt 0: 3s<br/>attempt 1: 6s<br/>attempt 2: 12s<br/>attempt 3: 24s<br/>attempt 4: 48s

            M->>M: Wait delay milliseconds

            M->>S: WebSocket upgrade request
            alt Connection succeeds
                S-->>M: Connection accepted
                M->>M: Set connectionState = 'connected'
                M->>M: Reset attempt = 0
            else Connection fails
                S--xM: Connection refused/timeout
                M->>M: attempt++
                M-->>C: Reconnect failed (attempt X/Y)
            end
        end
    end

    alt Connection established
        Note over C,EB: State Resynchronization
        M->>S: {"type": "resync", "data": {"channel": "events", "last_sequence": 42}}
        S->>EB: get_messages_since(42, mark_as_replay=true)
        EB-->>S: [msg 43, msg 44, msg 45] with replay=true

        loop For each missed message
            S-->>M: {"type": "event", "seq": 43, "replay": true, "data": {...}}
            M->>M: Process replayed message
            M->>M: Update lastSequence
        end

        S-->>M: {"type": "resync_ack", "channel": "events", "last_sequence": 42}
        M-->>C: onOpen callback
        M-->>C: Deliver replayed events

        Note over C,EB: Resume Normal Operation
        S-->>M: {"type": "event", "seq": 46, "data": {...}}
        M-->>C: New event (seq: 46)

    else All attempts exhausted
        M->>M: Set connectionState = 'failed'
        M-->>C: Connection failed permanently
        Note right of C: UI shows "Connection Failed"<br/>with manual retry button
    end
```

### Reconnection Flow States

| State          | Description                           | User Indication              |
| -------------- | ------------------------------------- | ---------------------------- |
| `connected`    | Active WebSocket connection           | Green status indicator       |
| `disconnected` | Connection lost, not yet reconnecting | Brief transition state       |
| `reconnecting` | Actively attempting to reconnect      | Yellow banner with attempt # |
| `failed`       | All reconnect attempts exhausted      | Red banner with retry button |

### Backoff Timing

| Attempt | Delay    | Cumulative Time |
| ------- | -------- | --------------- |
| 0       | 3,000ms  | 3s              |
| 1       | 6,000ms  | 9s              |
| 2       | 12,000ms | 21s             |
| 3       | 24,000ms | 45s             |
| 4       | 48,000ms | 93s (~1.5 min)  |

Total maximum reconnection time before failure: ~1.5 minutes

### Exponential Backoff

```typescript
// Reconnection delay increases with each attempt
const delay = reconnectInterval * Math.pow(2, attempt);
// Attempt 0: 3000ms
// Attempt 1: 6000ms
// Attempt 2: 12000ms
// Attempt 3: 24000ms
// Attempt 4: 48000ms
```

## Sequence Validation

### Frontend Gap Detection

```typescript
// frontend/src/hooks/sequenceValidator.ts
export function validateSequence(currentSeq: number, lastSeq: number | null): SequenceValidation {
  if (lastSeq === null) {
    return { valid: true, gap: false };
  }

  const expectedSeq = lastSeq + 1;
  if (currentSeq === expectedSeq) {
    return { valid: true, gap: false };
  }

  if (currentSeq > expectedSeq) {
    return { valid: true, gap: true, missed: currentSeq - expectedSeq };
  }

  // Duplicate or out-of-order
  return { valid: false, gap: false, duplicate: true };
}
```

### Gap Recovery

```typescript
// When gap detected
if (validation.gap) {
  // Request replay of missed messages
  send({
    type: 'resync',
    data: {
      channel: 'events',
      last_sequence: lastSeq,
    },
  });
}
```

## Connection Status Components

### ConnectionStatusBanner

Prominent banner displayed when WebSocket connection is lost.

```typescript
// frontend/src/components/common/ConnectionStatusBanner.tsx
export interface ConnectionStatusBannerProps {
  connectionState: ConnectionState;
  disconnectedSince: Date | null;
  reconnectAttempts?: number;
  maxReconnectAttempts?: number;
  onRetry: () => void;
  staleThresholdMs?: number;
  isPollingFallback?: boolean;
}
```

**States and Styling**:

| State          | Background | Icon             | Message                      |
| -------------- | ---------- | ---------------- | ---------------------------- |
| `reconnecting` | Yellow     | Spinning refresh | "Reconnecting (Attempt X/Y)" |
| `failed`       | Orange     | Warning triangle | "Connection Failed"          |
| `disconnected` | Red        | WiFi off         | "Disconnected"               |

**Stale Data Warning**:

When disconnected for longer than `staleThresholdMs` (default 60 seconds), displays:

```
Data may be stale: events and system status may be outdated
```

### WebSocketStatus

Compact status indicator with tooltip showing channel details.

```typescript
// frontend/src/components/common/WebSocketStatus.tsx
export interface WebSocketStatusProps {
  eventsChannel: ChannelStatus;
  systemChannel: ChannelStatus;
  showDetails?: boolean;
  onRetry?: () => void;
  isPollingFallback?: boolean;
}
```

**Channel Status**:

```typescript
interface ChannelStatus {
  name: string;
  state: ConnectionState;
  lastMessageTime: Date | null;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  hasExhaustedRetries: boolean;
}
```

**Tooltip Content**:

- Channel name with status indicator
- "Last message: 5s ago" or "No messages yet"
- Reconnect attempt counter when reconnecting
- "Retries exhausted" badge when failed

## Connection States

```typescript
type ConnectionState =
  | 'connected' // Active connection
  | 'disconnected' // No connection
  | 'reconnecting' // Attempting reconnection
  | 'failed'; // Retries exhausted
```

### State Transitions

```mermaid
stateDiagram-v2
    [*] --> disconnected
    disconnected --> connected: Connection established
    connected --> disconnected: Connection lost
    disconnected --> reconnecting: Auto-reconnect enabled
    reconnecting --> connected: Reconnect success
    reconnecting --> failed: Max attempts reached
    failed --> reconnecting: Manual retry
    failed --> connected: Manual connect success
```

## Polling Fallback

When WebSocket connection fails, components can fall back to REST API polling:

```typescript
// In useEventStream
const { connectionState } = useWebSocket({ ... });

// Enable REST polling when WebSocket fails
const enablePolling = connectionState === 'failed';

const { data: events } = useQuery({
  queryKey: ['events'],
  queryFn: fetchEvents,
  enabled: enablePolling,
  refetchInterval: 5000,  // Poll every 5 seconds
});
```

## Usage Patterns

### Dashboard Page

```typescript
function Dashboard() {
  const { events, isConnected, latestEvent, clearEvents } = useEventStream();

  // Handle alerts separately via useAlertWebSocket or REST polling
  const { alerts } = useAlerts();

  return (
    <div>
      <ConnectionStatusBanner
        connectionState={isConnected ? 'connected' : 'disconnected'}
        disconnectedSince={!isConnected ? new Date() : null}
        onRetry={() => window.location.reload()}
      />
      <EventList events={events} />
    </div>
  );
}
```

### Selective Subscription

```typescript
function AlertsPage() {
  const { send, isConnected } = useWebSocket({
    url: '/ws/events',
    onOpen: () => {
      // Only subscribe to alert events
      send({
        type: 'subscribe',
        data: { events: ['alert.*'] }
      });
    },
    onMessage: handleAlertMessage,
  });

  return <AlertList />;
}
```

### System Status Monitor

```typescript
function SystemStatus() {
  const [gpuStats, setGpuStats] = useState<GpuStats | null>(null);
  const [services, setServices] = useState<ServiceStatus[]>([]);

  useWebSocket({
    url: '/ws/system',
    onMessage: (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'system_status') {
        setGpuStats(data.data.gpu);
        setServices(data.data.services);
      }
    },
  });

  return (
    <div>
      <GpuStatsCard stats={gpuStats} />
      <ServiceStatusList services={services} />
    </div>
  );
}
```

## Related Documentation

- [WebSocket Server](websocket-server.md) - Backend endpoints
- [Message Formats](message-formats.md) - Message schemas
- [EventBroadcaster](event-broadcaster.md) - Server-side broadcasting
