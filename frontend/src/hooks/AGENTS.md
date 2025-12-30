# Frontend Hooks Directory

## Purpose

React custom hooks for managing WebSocket connections, real-time event streams, system status monitoring, and GPU metrics polling in the home security dashboard.

## Key Files

| File                  | Purpose                                         |
| --------------------- | ----------------------------------------------- |
| `index.ts`            | Central export point for all hooks and types    |
| `useWebSocket.ts`     | Low-level WebSocket connection manager          |
| `useEventStream.ts`   | Security events via `/ws/events` WebSocket      |
| `useSystemStatus.ts`  | System health via `/ws/system` WebSocket        |
| `useGpuHistory.ts`    | GPU metrics polling with history buffer         |
| `useHealthStatus.ts`  | REST-based health status polling                |
| `useServiceStatus.ts` | **DEPRECATED** - Per-service status (not wired) |

### Test Files

| File                       | Coverage                                               |
| -------------------------- | ------------------------------------------------------ |
| `useWebSocket.test.ts`     | Connection lifecycle, message handling, reconnects     |
| `useEventStream.test.ts`   | Event buffering, envelope parsing, non-event filtering |
| `useSystemStatus.test.ts`  | Backend message transformation, type guards            |
| `useGpuHistory.test.ts`    | Polling, history buffer, start/stop controls           |
| `useHealthStatus.test.ts`  | REST polling, error handling, refresh                  |
| `useServiceStatus.test.ts` | Service status parsing (deprecated hook)               |

## Hook Details

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

### `useEventStream.ts`

High-level hook for receiving security events via WebSocket (`/ws/events` endpoint).

**Features:**

- Receives backend event messages in envelope format: `{type: "event", data: {...}}`
- Type guard functions (`isSecurityEvent`, `isBackendEventMessage`) for message validation
- Ignores non-event messages (e.g., `service_status`, `ping`)
- Maintains in-memory buffer of last 100 events (newest first, constant `MAX_EVENTS`)
- Provides `latestEvent` computed value via `useMemo`
- `clearEvents()` method to reset buffer
- Uses `buildWebSocketUrl()` from api service for URL construction

**SecurityEvent Interface:**

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

**Return Interface:**

```typescript
interface UseEventStreamReturn {
  events: SecurityEvent[];
  isConnected: boolean;
  latestEvent: SecurityEvent | null;
  clearEvents: () => void;
}
```

### `useSystemStatus.ts`

High-level hook for receiving system health updates via WebSocket (`/ws/system` endpoint).

**Features:**

- Receives backend `system_status` messages and transforms to frontend format
- Tracks GPU metrics: utilization, temperature, memory (used/total)
- Tracks active camera count and overall system health
- Type guard function `isBackendSystemStatus()` for message validation
- Uses `buildWebSocketUrl()` from api service for URL construction

**SystemStatus Interface:**

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

**Return Interface:**

```typescript
interface UseSystemStatusReturn {
  status: SystemStatus | null;
  isConnected: boolean;
}
```

### `useGpuHistory.ts`

Hook for polling GPU stats and maintaining a rolling history buffer for time-series visualization.

**Features:**

- Polls `GET /api/system/gpu` at configurable intervals (default: 5000ms)
- Maintains rolling buffer of historical metrics (default: 60 data points)
- Start/stop polling controls
- Clear history method
- Auto-start option (default: true)

**Options Interface:**

```typescript
interface UseGpuHistoryOptions {
  pollingInterval?: number; // default: 5000ms
  maxDataPoints?: number; // default: 60
  autoStart?: boolean; // default: true
}
```

**GpuMetricDataPoint Interface:**

```typescript
interface GpuMetricDataPoint {
  timestamp: string;
  utilization: number;
  memory_used: number;
  temperature: number;
}
```

**Return Interface:**

```typescript
interface UseGpuHistoryReturn {
  current: GPUStats | null;
  history: GpuMetricDataPoint[];
  isLoading: boolean;
  error: string | null;
  start: () => void;
  stop: () => void;
  clearHistory: () => void;
}
```

### `useHealthStatus.ts`

Hook for REST-based health status polling from `GET /api/system/health`.

**Features:**

- Polls health endpoint at configurable intervals (default: 30000ms)
- Provides overall system status and per-service status
- Manual refresh capability
- Mount-safe state updates (tracks mounted state)
- Preserves previous health data on error

**Options Interface:**

```typescript
interface UseHealthStatusOptions {
  pollingInterval?: number; // default: 30000ms
  enabled?: boolean; // default: true
}
```

**Return Interface:**

```typescript
interface UseHealthStatusReturn {
  health: HealthResponse | null;
  isLoading: boolean;
  error: string | null;
  overallStatus: 'healthy' | 'degraded' | 'unhealthy' | null;
  services: Record;
  refresh: () => Promise;
}
```

### `useServiceStatus.ts` (DEPRECATED)

**WARNING:** This hook is NOT currently wired up on the backend.

The backend's `ServiceHealthMonitor` (health_monitor.py) exists but is not initialized in `main.py`, so no `service_status` messages are broadcast to `/ws/system`. The `SystemBroadcaster` only emits `system_status` messages.

**Use `useSystemStatus` instead** for system health information - it correctly handles `system_status` messages which include an overall health field.

See bead vq8.11 for context on this decision.

## Service Status Hook

This hook tracks individual service health status (RT-DETRv2, Nemotron) via WebSocket. The backend's `ServiceHealthMonitor` (health_monitor.py) monitors these services and broadcasts `service_status` messages when health changes.

**Use `useSystemStatus`** for overall system health (healthy/degraded/unhealthy).
**Use `useServiceStatus`** for detailed per-service status or when you need to react to specific service failures.

Note: Redis health is not monitored by ServiceHealthMonitor since the backend handles Redis failures gracefully through other mechanisms.

## Custom Hooks Patterns

### URL Construction Pattern

WebSocket hooks use `buildWebSocketUrl()` from `../services/api` for URL construction:

```typescript
import { buildWebSocketUrl } from '../services/api';

// Respects VITE_WS_BASE_URL env var
// Falls back to window.location.host
// Appends api_key query param if VITE_API_KEY is configured
const wsUrl = buildWebSocketUrl('/ws/events');
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

Type guards validate the envelope structure before processing.

### Reconnection Pattern

The base `useWebSocket` hook handles reconnection with counter tracking:

- Reconnect counter resets on successful connection
- Reconnection stops when `disconnect()` is called manually
- Cleanup clears pending reconnection timeouts

## Dependencies

- React hooks: `useState`, `useEffect`, `useRef`, `useCallback`, `useMemo`
- API service: `buildWebSocketUrl`, `fetchGPUStats`, `fetchHealth`
- Testing: `vitest`, `@testing-library/react`

## Usage Examples

### Event Stream

```typescript
const { events, isConnected, latestEvent, clearEvents } = useEventStream();

if (latestEvent) {
  console.log(`New event: ${latestEvent.summary} (Risk: ${latestEvent.risk_level})`);
}
```

### System Status

```typescript
const { status, isConnected } = useSystemStatus();

if (status) {
  console.log(`Health: ${status.health}, GPU: ${status.gpu_utilization}%`);
}
```

### GPU History

```typescript
const { current, history, isLoading, start, stop } = useGpuHistory({
  pollingInterval: 5000,
  maxDataPoints: 60,
});

// Use history array for time-series chart
```

### Health Status

```typescript
const { health, overallStatus, services, refresh } = useHealthStatus({
  pollingInterval: 30000,
});

// Manual refresh
await refresh();
```

## Notes

- All WebSocket URLs are constructed via `buildWebSocketUrl()` which respects `VITE_WS_BASE_URL` and `VITE_API_KEY`
- SSR-safe: checks for `window.WebSocket` availability before connecting
- Events are stored in reverse chronological order (newest first)
- Connection state is tracked per hook instance
- The `useWebSocket` hook auto-connects on mount and disconnects on unmount
- Message parsing falls back to raw data if JSON parsing fails
- Non-event messages (e.g., `service_status`, `ping`) are silently ignored by `useEventStream`

## Entry Points

For AI agents exploring this codebase:

1. **Start with `index.ts`** - Central export point showing all available hooks
2. **WebSocket foundation**: `useWebSocket.ts` is the base layer for real-time data
3. **High-level hooks**: `useEventStream.ts` and `useSystemStatus.ts` build on WebSocket
4. **REST hooks**: `useHealthStatus.ts` and `useGpuHistory.ts` use polling
5. **Tests**: Each hook has corresponding `.test.ts` file with usage patterns
