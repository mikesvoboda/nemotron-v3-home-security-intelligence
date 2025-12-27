# Frontend Hooks Directory

## Purpose

React custom hooks for managing WebSocket connections, real-time event streams, and system status monitoring in the home security dashboard.

## Key Files

### `index.ts`

Central export point for all custom hooks and their TypeScript types. Import hooks from this file:

```typescript
import { useWebSocket, useEventStream, useSystemStatus } from '@/hooks';
import type { SecurityEvent, SystemStatus, WebSocketOptions } from '@/hooks';
```

### `useWebSocket.ts`

Low-level WebSocket connection manager with automatic reconnection logic.

**Features:**

- Automatic reconnection with configurable attempts and intervals (default: 5 attempts, 3s interval)
- Message serialization (JSON) and deserialization with fallback to raw data
- Connection state tracking (`isConnected`)
- Manual connect/disconnect controls
- Lifecycle callbacks: `onOpen`, `onClose`, `onError`, `onMessage`
- SSR-safe: checks for `window.WebSocket` availability
- Prevents duplicate connections (checks OPEN/CONNECTING states)

**Options Interface:**

```typescript
interface WebSocketOptions {
  url: string;
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnect?: boolean; // default: true
  reconnectInterval?: number; // default: 3000ms
  reconnectAttempts?: number; // default: 5
}
```

**Return Interface:**

```typescript
interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: unknown;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
}
```

**Usage:**

```typescript
const { isConnected, lastMessage, send, connect, disconnect } = useWebSocket({
  url: 'ws://localhost:8000/ws',
  onMessage: (data) => console.log(data),
  reconnect: true,
});
```

### `useEventStream.ts`

High-level hook for receiving security events via WebSocket (`/ws/events` endpoint).

**Features:**

- Receives backend event messages in envelope format: `{type: "event", data: {...}}`
- Type guard functions (`isSecurityEvent`, `isBackendEventMessage`) for message validation
- Ignores non-event messages (e.g., `service_status`, `ping`)
- Maintains in-memory buffer of last 100 events (newest first, constant `MAX_EVENTS`)
- Provides `latestEvent` computed value via `useMemo`
- `clearEvents()` method to reset buffer
- Auto-constructs WebSocket URL based on `window.location`

**Backend Message Structure (received):**

```typescript
interface BackendEventMessage {
  type: 'event';
  data: {
    id: number;
    event_id?: number;
    batch_id?: string;
    camera_id: string;
    camera_name?: string;
    risk_score: number;
    risk_level: 'low' | 'medium' | 'high' | 'critical';
    summary: string;
    timestamp?: string;
    started_at?: string;
  };
}
```

**SecurityEvent Interface (extracted from data):**

```typescript
interface SecurityEvent {
  id: string | number;
  event_id?: number;
  batch_id?: string;
  camera_id: string;
  camera_name?: string;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  summary: string;
  timestamp?: string;
  started_at?: string;
}
```

**Usage:**

```typescript
const { events, isConnected, latestEvent, clearEvents } = useEventStream();

// Display latest event
if (latestEvent) {
  console.log(`New event: ${latestEvent.summary} (Risk: ${latestEvent.risk_level})`);
}

// Clear event buffer
clearEvents();
```

### `useSystemStatus.ts`

High-level hook for receiving system health updates via WebSocket (`/ws/system` endpoint).

**Features:**

- Receives backend `system_status` messages and transforms to frontend format
- Tracks GPU metrics: utilization, temperature, memory (used/total)
- Tracks active camera count and overall system health
- Type guard function `isBackendSystemStatus()` for message validation
- Auto-constructs WebSocket URL based on `window.location`

**Backend Message Structure (received):**

```typescript
interface BackendSystemStatus {
  type: 'system_status';
  data: {
    gpu: {
      utilization: number | null;
      memory_used: number | null;
      memory_total: number | null;
      temperature: number | null;
      inference_fps: number | null;
    };
    cameras: { active: number; total: number };
    queue: { pending: number; processing: number };
    health: 'healthy' | 'degraded' | 'unhealthy';
  };
  timestamp: string;
}
```

**Frontend SystemStatus Interface (returned):**

```typescript
interface SystemStatus {
  health: 'healthy' | 'degraded' | 'unhealthy';
  gpu_utilization: number | null;
  gpu_temperature: number | null;
  gpu_memory_used: number | null;
  gpu_memory_total: number | null;
  active_cameras: number;
  last_update: string;
}
```

**Usage:**

```typescript
const { status, isConnected } = useSystemStatus();

if (status) {
  console.log(`Health: ${status.health}, GPU: ${status.gpu_utilization}%`);
}
```

## Custom Hooks Patterns

### URL Construction Pattern

All WebSocket hooks construct URLs dynamically for protocol-agnostic connections:

```typescript
const wsProtocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsHost = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
const url = wsProtocol + '//' + wsHost + '/ws/events';
```

### Message Envelope Pattern

Both `useEventStream` and `useSystemStatus` expect messages in envelope format:

```typescript
// Backend sends messages wrapped in an envelope
{
  type: 'event' | 'system_status',  // Message type discriminator
  data: { ... },                     // Actual payload
  timestamp?: string                 // Optional timestamp
}
```

Type guards validate the envelope structure before processing:

```typescript
function isBackendEventMessage(data: unknown): data is BackendEventMessage {
  if (!data || typeof data !== 'object') return false;
  const msg = data as Record<string, unknown>;
  return msg.type === 'event' && isSecurityEvent(msg.data);
}
```

### Reconnection Pattern

The base `useWebSocket` hook handles reconnection with exponential state tracking:

- Reconnect counter resets on successful connection
- Reconnection stops when `disconnect()` is called manually
- Cleanup clears pending reconnection timeouts

## Testing

All hooks have comprehensive test coverage using Vitest and React Testing Library:

| File                      | Coverage                                                  |
| ------------------------- | --------------------------------------------------------- |
| `useWebSocket.test.ts`    | Connection lifecycle, message handling, reconnects        |
| `useEventStream.test.ts`  | Event buffering, envelope parsing, non-event filtering    |
| `useSystemStatus.test.ts` | Backend message transformation, type guards               |

**Test Utilities:**

- Mock WebSocket implementation for testing
- `renderHook` from `@testing-library/react` for hook testing
- `waitFor` for async state updates
- `vi.fn()` for callback mocking
- Helper function `wrapInEnvelope()` for creating test messages

## Dependencies

- React hooks: `useState`, `useEffect`, `useRef`, `useCallback`, `useMemo`
- Testing: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`

## Notes

- All WebSocket URLs are dynamically constructed using `window.location` for protocol (`ws:`/`wss:`) and host
- SSR-safe: checks for `window.WebSocket` availability before connecting
- Events are stored in reverse chronological order (newest first)
- Connection state is tracked per hook instance
- The `useWebSocket` hook auto-connects on mount and disconnects on unmount
- Message parsing falls back to raw data if JSON parsing fails
- Non-event messages (e.g., `service_status`, `ping`) are silently ignored by `useEventStream`
