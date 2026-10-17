import { createContext, useContext } from 'react';

import type { SecurityEvent } from './useEventStream';

// Backend message structure from SystemBroadcaster, shared with the provider
// that builds it (and with the REST fallback that imitates it).
export interface BackendSystemStatus {
  type: 'system_status';
  data: {
    gpu: {
      utilization: number | null;
      memory_used: number | null;
      memory_total: number | null;
      temperature: number | null;
      inference_fps: number | null;
    };
    cameras: {
      active: number;
      total: number;
    };
    queue: {
      pending: number;
      processing: number;
    };
    health: 'healthy' | 'degraded' | 'unhealthy';
  };
  timestamp: string;
}

/**
 * The four states the status surfaces render. Owned here since [r204]: the
 * per-channel machines live in `webSocketManager` now, and this is what its
 * observations are folded into. Widening this union is a display-contract
 * change — every renderer switches over it with a `default:` arm, so a new
 * value would silently render as that fallback label.
 */
export type ConnectionState = 'connected' | 'disconnected' | 'reconnecting' | 'failed';

export interface ChannelStatus {
  name: string;
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastMessageTime: Date | null;
  /** True when max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;
  /**
   * True when the channel is down because the server refused the credential
   * (close code 4001/4002, `AUTH_TERMINAL_CLOSE_CODES`) — the manager stops
   * retrying those, and the surfaces say so instead of implying the backend is
   * unreachable. Optional so the existing `ChannelStatus` literals (the status
   * components' tests build dozens) stay valid; readers coalesce.
   */
  authRequired?: boolean;
}

export interface ConnectionStatusSummary {
  eventsChannel: ChannelStatus;
  systemChannel: ChannelStatus;
  overallState: ConnectionState;
  anyReconnecting: boolean;
  allConnected: boolean;
  totalReconnectAttempts: number;
  /** True if any channel has exhausted reconnection attempts */
  hasExhaustedRetries: boolean;
  /** True if all channels have failed (exhausted retries) */
  allFailed: boolean;
  /** True if any channel is down on a refused credential (4001/4002) */
  authRequired?: boolean;
  /** Timestamp when disconnection started (null if connected) */
  disconnectedSince: Date | null;
}

export interface UseConnectionStatusReturn {
  summary: ConnectionStatusSummary;
  events: SecurityEvent[];
  systemStatus: BackendSystemStatus | null;
  clearEvents: () => void;
  /** True if currently falling back to REST API polling */
  isPollingFallback: boolean;
  /** Manually trigger a reconnection attempt */
  retryConnection: () => void;
}

/**
 * The session built once by `ConnectionStatusProvider`. Kept in this module
 * (not the provider's) because this is the module consumers import, and the
 * provider is the thing that fills it.
 */
export const ConnectionStatusContext = createContext<UseConnectionStatusReturn | null>(null);

/**
 * The shell's connection status, read from the one `ConnectionStatusProvider`
 * session.
 *
 * [r204]: this used to BUILD a session per call — Layout.tsx and Header.tsx
 * each mounted their own pair of sockets through `useWebSocketStatus`, which
 * is why the same two channels appeared as four reconnect state machines (and
 * why golden/shell/ws-status.spec.ts's recovery leg had to budget for the
 * slower of two independent schedulers). The call signature and the returned
 * shape are unchanged, which is what let both consumers and their tests stay
 * as they were; what changed is that the numbers now come from the shared
 * `webSocketManager` subscription the provider holds.
 */
export function useConnectionStatus(): UseConnectionStatusReturn {
  const value = useContext(ConnectionStatusContext);
  if (!value) {
    throw new Error('useConnectionStatus must be used within a ConnectionStatusProvider');
  }
  return value;
}
