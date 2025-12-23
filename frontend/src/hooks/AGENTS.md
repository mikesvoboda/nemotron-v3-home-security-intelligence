# Frontend Hooks Directory

## Purpose

React custom hooks for managing WebSocket connections, real-time event streams, and system status monitoring in the home security dashboard.

## Key Files

### `index.ts`

Central export point for all custom hooks and their TypeScript types. Import hooks from this file.

### `useWebSocket.ts`

Low-level WebSocket connection manager with automatic reconnection logic.

**Features:**

- Automatic reconnection with configurable attempts and intervals (default: 5 attempts, 3s interval)
- Message serialization (JSON) and deserialization
- Connection state tracking (`isConnected`)
- Manual connect/disconnect controls
- Lifecycle callbacks: `onOpen`, `onClose`, `onError`, `onMessage`

**Usage:**

```typescript
const { isConnected, lastMessage, send, connect, disconnect } = useWebSocket({
  url: 'ws://localhost:8000/ws',
  onMessage: (data) => console.log(data),
  reconnect: true,
});
```

**Types:**

- `WebSocketOptions`: Configuration interface
- `UseWebSocketReturn`: Hook return interface

### `useEventStream.ts`

High-level hook for receiving security events via WebSocket (`/ws/events` endpoint).

**Features:**

- Receives and validates `SecurityEvent` objects
- Maintains in-memory buffer of last 100 events (newest first)
- Provides `latestEvent` computed value
- `clearEvents()` method to reset buffer

**Usage:**

```typescript
const { events, isConnected, latestEvent, clearEvents } = useEventStream();
```

**Types:**

- `SecurityEvent`: Event object with `id`, `camera_id`, `camera_name`, `risk_score`, `risk_level`, `summary`, `timestamp`
- `UseEventStreamReturn`: Hook return interface

### `useSystemStatus.ts`

High-level hook for receiving system health updates via WebSocket (`/ws/system` endpoint).

**Features:**

- Receives and validates `SystemStatus` objects
- Tracks GPU utilization, active cameras, health status
- Auto-connects to system status WebSocket channel

**Usage:**

```typescript
const { status, isConnected } = useSystemStatus();
// status: { health, gpu_utilization, active_cameras, last_update }
```

**Types:**

- `SystemStatus`: System status object
- `UseSystemStatusReturn`: Hook return interface

## Testing

All hooks have comprehensive test coverage using Vitest and React Testing Library:

- `useWebSocket.test.ts` - Tests connection lifecycle, message handling, reconnection logic, manual controls
- `useEventStream.test.ts` - Tests event buffering, validation, clearing
- `useSystemStatus.test.ts` - Tests status updates and validation

**Test Utilities:**

- Mock WebSocket implementation for testing
- `renderHook` from `@testing-library/react` for hook testing
- `waitFor` for async state updates

## Dependencies

- React hooks: `useState`, `useEffect`, `useRef`, `useCallback`, `useMemo`
- Testing: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`

## Notes

- All WebSocket URLs are dynamically constructed using `window.location` for protocol (`ws:`/`wss:`) and host
- SSR-safe: checks for `window.WebSocket` availability
- Events are stored in reverse chronological order (newest first)
- Connection state is tracked per hook instance
