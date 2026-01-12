/**
 * useAlertWebSocket - WebSocket hook for real-time alert state changes
 *
 * This hook subscribes to WebSocket alert events and provides callbacks
 * for handling alert state changes (created, updated, acknowledged, resolved).
 *
 * Events handled:
 * - alert_created: New alert triggered from rule evaluation
 * - alert_updated: Alert modified (metadata, channels updated)
 * - alert_acknowledged: Alert marked as seen by user
 * - alert_resolved: Alert resolved/dismissed
 *
 * @module hooks/useAlertWebSocket
 */

import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useCallback, useRef } from 'react';

import { alertsQueryKeys } from './useAlertsQuery';
import { useWebSocket, type WebSocketOptions } from './useWebSocket';
import { logger } from '../services/logger';
import {
  type WebSocketAlertData,
  isAlertMessage,
  isAlertCreatedMessage,
  isAlertUpdatedMessage,
  isAlertAcknowledgedMessage,
  isAlertResolvedMessage,
} from '../types/generated/websocket';

// ============================================================================
// Types
// ============================================================================

/**
 * Alert event handler callback type
 */
export type AlertEventHandler = (alert: WebSocketAlertData) => void;

/**
 * Options for configuring the useAlertWebSocket hook
 */
export interface UseAlertWebSocketOptions {
  /**
   * WebSocket URL to connect to
   * @default process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws/events'
   */
  url?: string;

  /**
   * Whether to automatically invalidate React Query cache on alert events
   * @default true
   */
  autoInvalidateCache?: boolean;

  /**
   * Called when a new alert is created
   */
  onAlertCreated?: AlertEventHandler;

  /**
   * Called when an alert is updated
   */
  onAlertUpdated?: AlertEventHandler;

  /**
   * Called when an alert is acknowledged
   */
  onAlertAcknowledged?: AlertEventHandler;

  /**
   * Called when an alert is resolved
   */
  onAlertResolved?: AlertEventHandler;

  /**
   * Called for any alert event (before specific handlers)
   */
  onAnyAlertEvent?: (eventType: string, alert: WebSocketAlertData) => void;

  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;
}

/**
 * Return type for the useAlertWebSocket hook
 */
export interface UseAlertWebSocketReturn {
  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** The last alert message received */
  lastAlert: WebSocketAlertData | null;

  /** The last alert event type received */
  lastEventType: string | null;

  /** Connect to the WebSocket */
  connect: () => void;

  /** Disconnect from the WebSocket */
  disconnect: () => void;

  /** Whether max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;

  /** Current reconnection attempt count */
  reconnectCount: number;
}

// ============================================================================
// Hook Implementation
// ============================================================================

const DEFAULT_WS_URL = (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/ws/events';

/**
 * Hook to subscribe to real-time alert WebSocket events.
 *
 * Automatically invalidates React Query cache for alerts when events are received,
 * ensuring the UI stays in sync with server state.
 *
 * @param options - Configuration options
 * @returns WebSocket connection state and handlers
 *
 * @example
 * ```tsx
 * const { isConnected, lastAlert } = useAlertWebSocket({
 *   onAlertCreated: (alert) => {
 *     console.log('New alert:', alert.id);
 *     showNotification('New alert received');
 *   },
 *   onAlertAcknowledged: (alert) => {
 *     console.log('Alert acknowledged:', alert.id);
 *   },
 * });
 * ```
 */
export function useAlertWebSocket(
  options: UseAlertWebSocketOptions = {}
): UseAlertWebSocketReturn {
  const {
    url: urlOption = DEFAULT_WS_URL,
    autoInvalidateCache = true,
    onAlertCreated,
    onAlertUpdated,
    onAlertAcknowledged,
    onAlertResolved,
    onAnyAlertEvent,
    enabled = true,
  } = options;
  const url: string = urlOption;

  const queryClient = useQueryClient();

  // Track last alert state
  const lastAlertRef = useRef<WebSocketAlertData | null>(null);
  const lastEventTypeRef = useRef<string | null>(null);

  // Store callbacks in refs to avoid stale closures
  const onAlertCreatedRef = useRef(onAlertCreated);
  const onAlertUpdatedRef = useRef(onAlertUpdated);
  const onAlertAcknowledgedRef = useRef(onAlertAcknowledged);
  const onAlertResolvedRef = useRef(onAlertResolved);
  const onAnyAlertEventRef = useRef(onAnyAlertEvent);

  // Update refs when callbacks change
  useEffect(() => {
    onAlertCreatedRef.current = onAlertCreated;
    onAlertUpdatedRef.current = onAlertUpdated;
    onAlertAcknowledgedRef.current = onAlertAcknowledged;
    onAlertResolvedRef.current = onAlertResolved;
    onAnyAlertEventRef.current = onAnyAlertEvent;
  });

  // Invalidate alerts query cache to trigger refetch
  const invalidateAlertsCache = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: alertsQueryKeys.all });
  }, [queryClient]);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (data: unknown) => {
      // Check if this is an alert message
      if (!isAlertMessage(data)) {
        return;
      }

      const alertMessage = data;
      const alertData = alertMessage.data;
      const eventType = alertMessage.type;

      // Update refs
      lastAlertRef.current = alertData;
      lastEventTypeRef.current = eventType;

      // Log the event
      logger.debug('Alert WebSocket event received', {
        component: 'useAlertWebSocket',
        eventType,
        alertId: alertData.id,
        severity: alertData.severity,
        status: alertData.status,
      });

      // Call the generic handler first
      onAnyAlertEventRef.current?.(eventType, alertData);

      // Call specific handlers based on event type
      if (isAlertCreatedMessage(data)) {
        onAlertCreatedRef.current?.(alertData);
      } else if (isAlertUpdatedMessage(data)) {
        onAlertUpdatedRef.current?.(alertData);
      } else if (isAlertAcknowledgedMessage(data)) {
        onAlertAcknowledgedRef.current?.(alertData);
      } else if (isAlertResolvedMessage(data)) {
        onAlertResolvedRef.current?.(alertData);
      }

      // Invalidate cache to trigger refetch
      if (autoInvalidateCache) {
        invalidateAlertsCache();
      }
    },
    [autoInvalidateCache, invalidateAlertsCache]
  );

  // Configure WebSocket options
  const wsOptions: WebSocketOptions = {
    url,
    onMessage: handleMessage,
    reconnect: true,
    reconnectInterval: 1000,
    reconnectAttempts: 15,
    connectionTimeout: 10000,
    autoRespondToHeartbeat: true,
  };

  // Use the base WebSocket hook
  const {
    isConnected,
    connect,
    disconnect,
    hasExhaustedRetries,
    reconnectCount,
  } = useWebSocket(enabled ? wsOptions : { ...wsOptions, reconnect: false });

  // Manual connect/disconnect if not enabled
  useEffect(() => {
    if (!enabled) {
      disconnect();
    }
  }, [enabled, disconnect]);

  return {
    isConnected,
    lastAlert: lastAlertRef.current,
    lastEventType: lastEventTypeRef.current,
    connect,
    disconnect,
    hasExhaustedRetries,
    reconnectCount,
  };
}

export default useAlertWebSocket;
