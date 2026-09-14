/**
 * Hook for tracking circuit breaker states via WebSocket.
 *
 * The backend's SystemBroadcaster (system_broadcaster.py) periodically broadcasts
 * `circuit_breaker_update` messages via EventBroadcaster when circuit breaker
 * states change. This hook connects to `/ws/system` and listens for those messages,
 * tracking the state of each circuit breaker.
 *
 * Circuit breakers protect services from cascading failures by temporarily
 * blocking requests when a service is unhealthy. The states are:
 * - closed: Normal operation, requests flow through
 * - open: Service is unhealthy, requests are blocked
 * - half_open: Testing if service has recovered
 *
 * For overall system health, use `useSystemStatus` which provides aggregated
 * health status. This hook is useful when you need to show detailed per-breaker
 * status or react to specific circuit breaker state changes.
 */
import { useState, useCallback, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';

/**
 * Circuit breaker state enum matching backend CircuitBreakerStateEnum.
 */
export type CircuitBreakerStateType = 'closed' | 'open' | 'half_open';

/**
 * Individual circuit breaker state from WebSocket updates.
 */
export interface CircuitBreakerState {
  /** Circuit breaker name (e.g., 'rtdetr', 'nemotron') */
  name: string;
  /** Current state of the circuit breaker */
  state: CircuitBreakerStateType;
  /** Number of consecutive failures */
  failure_count: number;
  /** Number of consecutive successes (in half_open state) */
  success_count: number;
  /** ISO timestamp of last failure (if any) */
  last_failure_time?: string | null;
  /** ISO timestamp of last success (if any) */
  last_success_time?: string | null;
}

/**
 * Summary counts of circuit breaker states.
 */
export interface CircuitBreakerSummary {
  /** Total number of circuit breakers */
  total: number;
  /** Number of circuit breakers in closed state */
  closed: number;
  /** Number of circuit breakers in open state */
  open: number;
  /** Number of circuit breakers in half_open state */
  half_open: number;
}

/**
 * Return type for useCircuitBreakerStatus hook.
 */
export interface UseCircuitBreakerStatusReturn {
  /** Map of circuit breaker names to their states */
  breakers: Record<string, CircuitBreakerState>;
  /** Summary counts of circuit breaker states */
  summary: CircuitBreakerSummary;
  /** True if any circuit breaker is in open state */
  hasOpenBreaker: boolean;
  /** True if any circuit breaker is in half_open state */
  hasHalfOpenBreaker: boolean;
  /** True if all circuit breakers are in closed state (healthy) */
  allClosed: boolean;
  /** ISO timestamp of last update received */
  lastUpdate: string | null;
  /** Get a specific circuit breaker's state by name */
  getBreaker: (name: string) => CircuitBreakerState | null;
  /** WebSocket connection status */
  isConnected: boolean;
}

/**
 * Backend WebSocket message data structure for circuit breaker updates.
 * Matches the format from backend/services/system_broadcaster.py broadcast_circuit_breaker_states()
 */
interface CircuitBreakerUpdateData {
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
      state: CircuitBreakerStateType;
      failure_count: number;
      success_count: number;
      last_failure_time?: string | null;
    }
  >;
}

/**
 * Backend WebSocket message envelope structure.
 */
interface CircuitBreakerUpdateMessage {
  type: 'circuit_breaker_update';
  data: CircuitBreakerUpdateData;
}

/**
 * Type guard to validate circuit breaker state value.
 */
function isCircuitBreakerState(value: unknown): value is CircuitBreakerStateType {
  return typeof value === 'string' && ['closed', 'open', 'half_open'].includes(value);
}

/**
 * Type guard for circuit breaker update messages from WebSocket.
 */
function isCircuitBreakerUpdateMessage(data: unknown): data is CircuitBreakerUpdateMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  // Check envelope structure: { type: "circuit_breaker_update", data: {...} }
  if (msg.type !== 'circuit_breaker_update') {
    return false;
  }

  // Check nested data object
  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const msgData = msg.data as Record<string, unknown>;

  // Validate required fields
  if (typeof msgData.timestamp !== 'string') {
    return false;
  }

  // Validate summary object
  if (!msgData.summary || typeof msgData.summary !== 'object') {
    return false;
  }

  const summary = msgData.summary as Record<string, unknown>;
  if (
    typeof summary.total !== 'number' ||
    typeof summary.open !== 'number' ||
    typeof summary.half_open !== 'number' ||
    typeof summary.closed !== 'number'
  ) {
    return false;
  }

  // Validate breakers object
  if (!msgData.breakers || typeof msgData.breakers !== 'object') {
    return false;
  }

  // Validate each breaker entry
  const breakers = msgData.breakers as Record<string, unknown>;
  for (const [, value] of Object.entries(breakers)) {
    if (!value || typeof value !== 'object') {
      return false;
    }
    const breaker = value as Record<string, unknown>;
    if (!isCircuitBreakerState(breaker.state)) {
      return false;
    }
    if (typeof breaker.failure_count !== 'number') {
      return false;
    }
    if (typeof breaker.success_count !== 'number') {
      return false;
    }
  }

  return true;
}

/**
 * Initial summary state with all zeros.
 */
const INITIAL_SUMMARY: CircuitBreakerSummary = {
  total: 0,
  closed: 0,
  open: 0,
  half_open: 0,
};

/**
 * Subscribe to circuit breaker status updates from the backend via WebSocket.
 *
 * Returns current state for each circuit breaker, along with derived flags
 * for checking if any breaker is open, half-open, or if all are closed.
 *
 * @returns UseCircuitBreakerStatusReturn with breakers map, summary, and utility getters
 *
 * @example
 * ```tsx
 * function CircuitBreakerDisplay() {
 *   const { breakers, summary, hasOpenBreaker, allClosed } = useCircuitBreakerStatus();
 *
 *   return (
 *     <div>
 *       <Badge color={allClosed ? 'green' : 'red'}>
 *         {summary.closed}/{summary.total} Healthy
 *       </Badge>
 *       {hasOpenBreaker && <Alert>Some services are protected by open circuit breakers</Alert>}
 *       {Object.values(breakers).map(breaker => (
 *         <div key={breaker.name}>
 *           {breaker.name}: {breaker.state} (failures: {breaker.failure_count})
 *         </div>
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useCircuitBreakerStatus(): UseCircuitBreakerStatusReturn {
  const [breakers, setBreakers] = useState<Record<string, CircuitBreakerState>>({});
  const [summary, setSummary] = useState<CircuitBreakerSummary>(INITIAL_SUMMARY);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const handleMessage = useCallback((data: unknown) => {
    if (isCircuitBreakerUpdateMessage(data)) {
      // Extract from envelope: data.data contains the circuit breaker update
      const updateData = data.data;

      // Update summary
      setSummary({
        total: updateData.summary.total,
        closed: updateData.summary.closed,
        open: updateData.summary.open,
        half_open: updateData.summary.half_open,
      });

      // Update individual breaker states
      const newBreakers: Record<string, CircuitBreakerState> = {};
      for (const [name, breakerData] of Object.entries(updateData.breakers)) {
        newBreakers[name] = {
          name,
          state: breakerData.state,
          failure_count: breakerData.failure_count,
          success_count: breakerData.success_count,
          last_failure_time: breakerData.last_failure_time,
        };
      }
      setBreakers(newBreakers);

      // Update timestamp
      setLastUpdate(updateData.timestamp);
    }
  }, []);

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  // SECURITY: API key is passed via Sec-WebSocket-Protocol header, not URL query param
  // Note: Circuit breaker updates are broadcast via /ws/system (SystemBroadcaster)
  const wsOptions = buildWebSocketOptions('/ws/system');

  const { isConnected } = useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
  });

  // Computed values
  const hasOpenBreaker = useMemo(() => {
    return summary.open > 0;
  }, [summary.open]);

  const hasHalfOpenBreaker = useMemo(() => {
    return summary.half_open > 0;
  }, [summary.half_open]);

  const allClosed = useMemo(() => {
    return summary.total > 0 && summary.closed === summary.total;
  }, [summary.total, summary.closed]);

  const getBreaker = useCallback(
    (name: string): CircuitBreakerState | null => {
      return breakers[name] ?? null;
    },
    [breakers]
  );

  return {
    breakers,
    summary,
    hasOpenBreaker,
    hasHalfOpenBreaker,
    allClosed,
    lastUpdate,
    getBreaker,
    isConnected,
  };
}
