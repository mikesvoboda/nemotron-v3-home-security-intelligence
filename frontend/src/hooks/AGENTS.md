# Frontend Hooks Directory

## Purpose

React custom hooks for managing WebSocket connections, real-time event streams, system status monitoring, storage stats, and GPU metrics polling in the home security dashboard.

## Key Files

| File                        | Purpose                                                          | Exported |
| --------------------------- | ---------------------------------------------------------------- | -------- |
| `index.ts`                  | Central export point for hooks and types                         | N/A      |
| `useWebSocket.ts`           | Low-level WebSocket connection manager                           | Yes      |
| `useWebSocketStatus.ts`     | Enhanced WebSocket with channel status tracking                  | Yes      |
| `useConnectionStatus.ts`    | Unified connection status for all WS channels                    | Yes      |
| `useEventStream.ts`         | Security events via `/ws/events` WebSocket                       | Yes      |
| `useSystemStatus.ts`        | System health via `/ws/system` WebSocket                         | Yes      |
| `useGpuHistory.ts`          | GPU metrics polling with history buffer                          | Yes      |
| `useHealthStatus.ts`        | REST-based health status polling                                 | Yes      |
| `usePerformanceMetrics.ts`  | System performance metrics via WebSocket                         | Yes      |
| `useAIMetrics.ts`           | Fetches AI performance metrics from multiple endpoints           | Yes      |
| `useDetectionEnrichment.ts` | Fetches enrichment data for a specific detection                 | Yes      |
| `useModelZooStatus.ts`      | Fetches and polls Model Zoo status with VRAM stats               | Yes      |
| `useSavedSearches.ts`       | Manages saved searches in localStorage                           | Yes      |
| `useStorageStats.ts`        | Storage disk usage polling with cleanup preview                  | No       |
| `useServiceStatus.ts`       | Per-service status tracking                                      | No       |
| `useSidebarContext.ts`      | Context hook for mobile sidebar state                            | No       |
| `webSocketManager.ts`       | Singleton WebSocket connection manager with deduplication        | No       |

### Test Files

| File                              | Coverage                                                 |
| --------------------------------- | -------------------------------------------------------- |
| `useWebSocket.test.ts`            | Connection lifecycle, message handling, reconnects       |
| `useWebSocketStatus.test.ts`      | Channel status tracking, reconnect state                 |
| `useConnectionStatus.test.ts`     | Multi-channel status aggregation                         |
| `useEventStream.test.ts`          | Event buffering, envelope parsing, non-event filtering   |
| `useSystemStatus.test.ts`         | Backend message transformation, type guards              |
| `useGpuHistory.test.ts`           | Polling, history buffer, start/stop controls             |
| `useHealthStatus.test.ts`         | REST polling, error handling, refresh                    |
| `useStorageStats.test.ts`         | Storage polling, cleanup preview                         |
| `useServiceStatus.test.ts`        | Service status parsing                                   |
| `usePerformanceMetrics.test.ts`   | WebSocket performance metrics, alerts, history buffer    |
| `useAIMetrics.test.ts`            | Multi-endpoint fetching, state combination, polling      |
| `useDetectionEnrichment.test.ts`  | Detection enrichment fetching, loading/error states      |
| `useModelZooStatus.test.ts`       | Model Zoo polling, VRAM calculation, refresh             |
| `useSavedSearches.test.ts`        | LocalStorage persistence, CRUD operations, cross-tab sync|
| `useSidebarContext.test.tsx`      | Context provider, mobile menu state                      |
| `webSocketManager.test.ts`        | Connection deduplication, ref counting, subscribers      |

## Hook Details

### `useWebSocket.ts`

Low-level WebSocket connection manager with automatic reconnection logic.

**Features:**

- Automatic reconnection with configurable attempts and intervals (default: 5 attempts, 3s interval)
- Message serialization (JSON) and deserialization with fallback to raw data
- Connection state tracking (`isConnected`)
- Manual connect/disconnect controls
- Lifecycle callbacks: `onOpen`, `onClose`, `onError`, `onMessage`, `onHeartbeat`
- SSR-safe: checks for `window.WebSocket` availability
- Prevents duplicate connections (checks OPEN/CONNECTING states)
- Handles server heartbeat (ping) messages automatically
- Tracks last heartbeat timestamp for connection health monitoring

**Options Interface:**

```typescript
interface WebSocketOptions {
  url: string;
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  onMaxRetriesExhausted?: () => void;
  onHeartbeat?: () => void; // Called when server heartbeat received
  reconnect?: boolean; // default: true
  reconnectInterval?: number; // default: 1000ms (base for exponential backoff)
  reconnectAttempts?: number; // default: 5
  connectionTimeout?: number; // default: 10000ms
  autoRespondToHeartbeat?: boolean; // default: true - auto-send pong response
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
  hasExhaustedRetries: boolean;
  reconnectCount: number;
  lastHeartbeat: Date | null; // Timestamp of last server heartbeat
}
```

**Server Heartbeat Handling:**

The backend sends periodic heartbeat messages in the format `{"type": "ping"}` to keep connections alive (default: every 30 seconds). The hook:

- Automatically detects these heartbeat messages
- Updates `lastHeartbeat` timestamp for connection health tracking
- Sends `{"type": "pong"}` response by default (controlled by `autoRespondToHeartbeat`)
- Calls the optional `onHeartbeat` callback
- Does NOT update `lastMessage` or call `onMessage` for heartbeats to prevent unnecessary re-renders

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

### `useWebSocketStatus.ts`

Enhanced WebSocket hook that tracks detailed channel status including reconnection state.

**Features:**

- Full WebSocket lifecycle management with reconnection
- Channel-level status tracking (name, state, reconnect attempts)
- Last message timestamp tracking
- SSR-safe (checks for `window.WebSocket` availability)

**Types:**

```typescript
type ConnectionState = 'connected' | 'disconnected' | 'reconnecting';

interface ChannelStatus {
  name: string;
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastMessageTime: Date | null;
}

interface UseWebSocketStatusReturn {
  channelStatus: ChannelStatus;
  lastMessage: unknown;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
}
```

### `useConnectionStatus.ts`

Unified hook that manages both `/ws/events` and `/ws/system` WebSocket channels.

**Features:**

- Single hook for all WebSocket connections
- Aggregated connection summary (overall state, any reconnecting, all connected)
- Stores events in memory buffer (max 100 events)
- Parses backend system status messages

**Return Interface:**

```typescript
interface ConnectionStatusSummary {
  eventsChannel: ChannelStatus;
  systemChannel: ChannelStatus;
  overallState: ConnectionState;
  anyReconnecting: boolean;
  allConnected: boolean;
  totalReconnectAttempts: number;
}

interface UseConnectionStatusReturn {
  summary: ConnectionStatusSummary;
  events: SecurityEvent[];
  systemStatus: BackendSystemStatus | null;
  clearEvents: () => void;
}
```

### `useStorageStats.ts`

Hook for polling storage statistics and previewing cleanup operations.

**Features:**

- Polls `GET /api/system/storage` at configurable intervals (default: 60s)
- Provides disk usage metrics (used, total, free, percent)
- Storage breakdown by category (thumbnails, images, clips)
- Database record counts (events, detections, GPU stats, logs)
- Cleanup preview functionality (dry run mode)

**Options Interface:**

```typescript
interface UseStorageStatsOptions {
  pollInterval?: number; // default: 60000ms
  enablePolling?: boolean; // default: true
}
```

**Return Interface:**

```typescript
interface UseStorageStatsReturn {
  stats: StorageStatsResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise;
  previewCleanup: () => Promise;
  previewLoading: boolean;
  cleanupPreview: CleanupResponse | null;
}
```

### `usePerformanceMetrics.ts`

Hook for real-time system performance metrics via WebSocket (`/ws/system` endpoint).

**Features:**

- Subscribes to `performance_update` messages via the system WebSocket channel
- Maintains circular buffers for historical data at 3 time resolutions (5m, 15m, 60m)
- Tracks GPU metrics, AI model status, inference latencies, database metrics
- Surfaces active performance alerts (warning/critical severity)
- Downsamples updates: 5m buffer gets every update, 15m every 3rd, 60m every 12th

**Types:**

```typescript
type TimeRange = '5m' | '15m' | '60m';

interface PerformanceUpdate {
  timestamp: string;
  gpu: GpuMetrics | null;
  ai_models: Record;
  nemotron: NemotronMetrics | null;
  inference: InferenceMetrics | null;
  databases: Record;
  host: HostMetrics | null;
  containers: ContainerMetrics[];
  alerts: PerformanceAlert[];
}

interface UsePerformanceMetricsReturn {
  current: PerformanceUpdate | null;
  history: PerformanceHistory;
  alerts: PerformanceAlert[];
  isConnected: boolean;
  timeRange: TimeRange;
  setTimeRange: (range: TimeRange) => void;
}
```

### Non-Exported Hooks

The following hooks are NOT exported from `index.ts` and are used internally or directly imported:

**`useServiceStatus.ts`** - Per-service status tracking. The backend's `ServiceHealthMonitor` (health_monitor.py) monitors services and broadcasts `service_status` messages. Use `useSystemStatus` for overall system health or `usePerformanceMetrics` for detailed metrics.

**`useStorageStats.ts`** - Storage disk usage polling with cleanup preview. Import directly when needed.

**`useSidebarContext.ts`** - Context hook for mobile sidebar state. Used by Layout component for sidebar toggle state management.

**`webSocketManager.ts`** - Singleton WebSocket connection manager with deduplication. Used internally by WebSocket hooks for connection sharing.

### `useAIMetrics.ts`

Hook for fetching AI performance metrics from multiple API endpoints and combining them into unified state.

**Features:**

- Fetches from `/api/metrics`, `/api/system/telemetry`, `/api/system/health`, `/api/system/pipeline-latency`
- Combines RT-DETR and Nemotron model statuses
- Tracks detection/analysis latency metrics with percentiles
- Monitors queue depths, errors, and throughput
- Configurable polling interval (default: 5000ms)
- Manual refresh capability

**Return Interface:**

```typescript
interface UseAIMetricsResult {
  data: AIPerformanceState;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}
```

### `useDetectionEnrichment.ts`

Hook for fetching enrichment data (vision model results) for a specific detection.

**Features:**

- Fetches structured enrichment results from `/api/detections/{id}/enrichment`
- Contains results from 18+ vision models run during detection processing
- Automatic fetching when detectionId changes
- Manual refetch capability

**Return Interface:**

```typescript
interface UseDetectionEnrichmentReturn {
  data: EnrichmentResponse | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}
```

### `useModelZooStatus.ts`

Hook for fetching and polling Model Zoo status including VRAM statistics.

**Features:**

- Polls `/api/system/models` at configurable intervals (default: 10000ms)
- Provides list of all AI models in the Model Zoo
- Calculates VRAM usage statistics (budget, used, available, percentage)
- Manual refresh capability

**Return Interface:**

```typescript
interface UseModelZooStatusReturn {
  models: ModelStatusResponse[];
  vramStats: VRAMStats | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}
```

### `useSavedSearches.ts`

Hook for managing saved searches with localStorage persistence.

**Features:**

- Persists searches to localStorage (key: `hsi_saved_searches`)
- Limits to 10 most recent searches
- CRUD operations: save, delete, load, clearAll
- Cross-tab sync via storage event listener
- Handles localStorage errors gracefully

**Return Interface:**

```typescript
interface UseSavedSearchesReturn {
  savedSearches: SavedSearch[];
  saveSearch: (name: string, query: string, filters: SearchFilters) => void;
  deleteSearch: (id: string) => void;
  loadSearch: (id: string) => LoadedSearch | null;
  clearAll: () => void;
}
```

### `useSidebarContext.ts`

Context hook for managing mobile sidebar state across the application.

**Features:**

- Provides mobile menu open/close state
- Toggle function for menu visibility
- Must be used within Layout component

**Return Interface:**

```typescript
interface SidebarContextType {
  isMobileMenuOpen: boolean;
  setMobileMenuOpen: (open: boolean) => void;
  toggleMobileMenu: () => void;
}
```

### `webSocketManager.ts`

Singleton class that manages WebSocket connections with deduplication and reference counting.

**Features:**

- Connection deduplication: multiple subscribers to same URL share one connection
- Reference counting: connection closes only when all subscribers disconnect
- Automatic reconnection with exponential backoff and jitter
- Server heartbeat (ping/pong) handling
- Connection timeout handling
- SSR-safe: checks for `window.WebSocket` availability

**Key Functions:**

```typescript
// Subscribe to a WebSocket URL
subscribe(url: string, subscriber: Subscriber, config: ConnectionConfig): () => void

// Send data through WebSocket
send(url: string, data: unknown): boolean

// Get connection state
getConnectionState(url: string): { isConnected, reconnectCount, hasExhaustedRetries, lastHeartbeat }

// Manual reconnect
reconnect(url: string): void

// Get subscriber count
getSubscriberCount(url: string): number

// Clear all connections
clearAll(): void
```

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
