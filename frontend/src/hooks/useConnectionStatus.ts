import { useState, useCallback, useMemo, useEffect, useRef } from 'react';

import { useWebSocketStatus, ConnectionState, ChannelStatus } from './useWebSocketStatus';
import { buildWebSocketOptions, fetchHealth, fetchEvents } from '../services/api';

import type { SecurityEvent } from './useEventStream';

// Backend WebSocket message envelope structure
interface BackendEventMessage {
  type: 'event';
  data: SecurityEvent;
}

// Backend message structure from SystemBroadcaster
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

const MAX_EVENTS = 100;

/**
 * Type guard to check if data is a valid SecurityEvent
 */
function isSecurityEvent(data: unknown): data is SecurityEvent {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const obj = data as Record<string, unknown>;
  return (
    ('id' in obj || 'event_id' in obj) &&
    'camera_id' in obj &&
    'risk_score' in obj &&
    'risk_level' in obj &&
    'summary' in obj
  );
}

/**
 * Type guard to check if message is a backend event message envelope
 */
function isBackendEventMessage(data: unknown): data is BackendEventMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'event' && isSecurityEvent(msg.data);
}

function isBackendSystemStatus(data: unknown): data is BackendSystemStatus {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  return (
    msg.type === 'system_status' &&
    typeof msg.data === 'object' &&
    msg.data !== null &&
    typeof msg.timestamp === 'string' &&
    'gpu' in msg.data &&
    'cameras' in msg.data &&
    'health' in msg.data
  );
}

// REST API polling interval when WebSocket fails
// Use shorter interval (5 seconds) during fallback for faster data updates
// and quicker detection of backend recovery
const FALLBACK_POLLING_INTERVAL = 5000;

export function useConnectionStatus(): UseConnectionStatusReturn {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [systemStatus, setSystemStatus] = useState<BackendSystemStatus | null>(null);
  const [isPollingFallback, setIsPollingFallback] = useState(false);
  const [disconnectedSince, setDisconnectedSince] = useState<Date | null>(null);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastEventIdRef = useRef<string | number | null>(null);

  const handleEventMessage = useCallback((data: unknown) => {
    if (isBackendEventMessage(data)) {
      const event = data.data;
      setEvents((prevEvents) => {
        const newEvents = [event, ...prevEvents];
        return newEvents.slice(0, MAX_EVENTS);
      });
    }
  }, []);

  const handleSystemMessage = useCallback((data: unknown) => {
    if (isBackendSystemStatus(data)) {
      setSystemStatus(data);
    }
  }, []);

  // Track if we should trigger reconnect after successful health check
  const shouldAutoReconnectRef = useRef(false);

  // REST API polling fallback function
  /* v8 ignore start -- polling fallback is triggered by onMaxRetriesExhausted which requires
   * real WebSocket connection exhaustion. Mock setup cannot reliably trigger this callback. */
  const pollRestApi = useCallback(async () => {
    try {
      // Fetch health status
      const health = await fetchHealth();

      // If health check succeeds during polling fallback, backend is back online
      // Set flag to trigger WebSocket reconnection
      if (health.status === 'healthy' || health.status === 'degraded') {
        shouldAutoReconnectRef.current = true;
      }

      // Get GPU status safely
      const gpuService = health.services?.gpu;
      const gpuIsHealthy = gpuService?.status === 'healthy';

      // Convert health response to BackendSystemStatus format
      // Map the health status to valid values
      const healthValue =
        health.status === 'healthy' || health.status === 'degraded' || health.status === 'unhealthy'
          ? health.status
          : 'unhealthy';

      const healthStatus: BackendSystemStatus = {
        type: 'system_status',
        data: {
          gpu: {
            utilization: gpuIsHealthy ? 50 : null,
            memory_used: null,
            memory_total: null,
            temperature: null,
            inference_fps: null,
          },
          cameras: {
            active: 0,
            total: 0,
          },
          queue: {
            pending: 0,
            processing: 0,
          },
          health: healthValue,
        },
        timestamp: new Date().toISOString(),
      };
      setSystemStatus(healthStatus);

      // Fetch recent events
      const eventsResponse = await fetchEvents({ limit: 20 });
      if (eventsResponse.items && eventsResponse.items.length > 0) {
        // Only add new events we haven't seen
        const newEvents = eventsResponse.items.filter(
          (event) => event.id !== lastEventIdRef.current
        );
        if (newEvents.length > 0) {
          lastEventIdRef.current = eventsResponse.items[0].id;
          setEvents((prevEvents) => {
            // Convert Event to SecurityEvent format
            const securityEvents: SecurityEvent[] = newEvents.map((e) => {
              // Validate risk_level is a valid value
              const validRiskLevels = ['low', 'medium', 'high', 'critical'] as const;
              type RiskLevel = (typeof validRiskLevels)[number];
              const riskLevel: RiskLevel = validRiskLevels.includes(e.risk_level as RiskLevel)
                ? (e.risk_level as RiskLevel)
                : 'low';

              return {
                id: e.id,
                event_id: e.id,
                camera_id: e.camera_id,
                risk_score: e.risk_score ?? 0,
                risk_level: riskLevel,
                summary: e.summary ?? '',
                timestamp: e.started_at,
                started_at: e.started_at,
              };
            });
            const combined = [...securityEvents, ...prevEvents];
            // Deduplicate by id
            const unique = combined.filter(
              (event, index, self) => index === self.findIndex((ev) => ev.id === event.id)
            );
            return unique.slice(0, MAX_EVENTS);
          });
        }
      }
    } catch {
      // Polling failure is expected when server is down - silently ignore
      shouldAutoReconnectRef.current = false;
    }
  }, []);
  /* v8 ignore stop */

  // Reference to retry function (will be set after WebSocket hooks are created)
  const retryConnectionRef = useRef<(() => void) | null>(null);

  // Start/stop polling based on WebSocket state
  /* v8 ignore start -- part of polling fallback system, requires onMaxRetriesExhausted trigger */
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) return; // Already polling

    setIsPollingFallback(true);
    shouldAutoReconnectRef.current = false;

    // Immediate first poll
    void pollRestApi();

    // Set up interval with shorter polling during fallback (5s instead of 30s)
    // This provides faster data updates and quicker backend recovery detection
    pollingIntervalRef.current = setInterval(() => {
      void pollRestApi();

      // If health check succeeded, trigger WebSocket reconnection
      if (shouldAutoReconnectRef.current && retryConnectionRef.current) {
        shouldAutoReconnectRef.current = false;
        retryConnectionRef.current();
      }
    }, FALLBACK_POLLING_INTERVAL);
  }, [pollRestApi]);

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
      setIsPollingFallback(false);
      shouldAutoReconnectRef.current = false;
    }
  }, []);
  /* v8 ignore stop */

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  // SECURITY: API key is passed via Sec-WebSocket-Protocol header, not URL query param
  const eventsWsOptions = buildWebSocketOptions('/ws/events');
  const systemWsOptions = buildWebSocketOptions('/ws/system');

  const { channelStatus: eventsChannel, connect: connectEvents } = useWebSocketStatus({
    url: eventsWsOptions.url,
    protocols: eventsWsOptions.protocols,
    channelName: 'Events',
    onMessage: handleEventMessage,
    onMaxRetriesExhausted: startPolling,
  });

  const { channelStatus: systemChannel, connect: connectSystem } = useWebSocketStatus({
    url: systemWsOptions.url,
    protocols: systemWsOptions.protocols,
    channelName: 'System',
    onMessage: handleSystemMessage,
    onMaxRetriesExhausted: startPolling,
  });

  // Stop polling when WebSocket reconnects
  useEffect(() => {
    if (eventsChannel.state === 'connected' || systemChannel.state === 'connected') {
      stopPolling();
    }
  }, [eventsChannel.state, systemChannel.state, stopPolling]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  // Track when disconnection started
  useEffect(() => {
    const isConnected =
      eventsChannel.state === 'connected' && systemChannel.state === 'connected';

    if (isConnected) {
      // Clear disconnection time when reconnected
      setDisconnectedSince(null);
    } else if (disconnectedSince === null) {
      // Set disconnection time when first disconnected
      setDisconnectedSince(new Date());
    }
    // Note: We intentionally don't include disconnectedSince in deps to avoid resetting
    // the timestamp on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventsChannel.state, systemChannel.state]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    lastEventIdRef.current = null;
  }, []);

  // Manual retry function
  const retryConnection = useCallback(() => {
    stopPolling();
    connectEvents();
    connectSystem();
  }, [stopPolling, connectEvents, connectSystem]);

  // Update ref so auto-reconnect can access this function
  useEffect(() => {
    retryConnectionRef.current = retryConnection;
  }, [retryConnection]);

  const summary = useMemo((): ConnectionStatusSummary => {
    const anyReconnecting =
      eventsChannel.state === 'reconnecting' || systemChannel.state === 'reconnecting';
    const allConnected = eventsChannel.state === 'connected' && systemChannel.state === 'connected';
    const hasExhaustedRetries =
      eventsChannel.hasExhaustedRetries || systemChannel.hasExhaustedRetries;
    const allFailed = eventsChannel.state === 'failed' && systemChannel.state === 'failed';
    const anyFailed = eventsChannel.state === 'failed' || systemChannel.state === 'failed';

    let overallState: ConnectionState;
    if (allConnected) {
      overallState = 'connected';
    } else if (anyFailed) {
      overallState = 'failed';
    } else if (anyReconnecting) {
      overallState = 'reconnecting';
    } else {
      overallState = 'disconnected';
    }

    return {
      eventsChannel,
      systemChannel,
      overallState,
      anyReconnecting,
      allConnected,
      totalReconnectAttempts: eventsChannel.reconnectAttempts + systemChannel.reconnectAttempts,
      hasExhaustedRetries,
      allFailed,
      disconnectedSince,
    };
  }, [eventsChannel, systemChannel, disconnectedSince]);

  return {
    summary,
    events,
    systemStatus,
    clearEvents,
    isPollingFallback,
    retryConnection,
  };
}
