/**
 * useEventLifecycleWebSocket - WebSocket hook for real-time security event lifecycle changes
 *
 * This hook subscribes to WebSocket event lifecycle events and provides callbacks
 * for handling event state changes (created, updated, deleted).
 *
 * Events handled (NEM-2515):
 * - event.created: New security event detected and stored
 * - event.updated: Security event was modified (risk score, status, etc.)
 * - event.deleted: Security event was removed
 *
 * @module hooks/useEventLifecycleWebSocket
 */

import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useCallback, useRef, useState } from 'react';

import { eventsQueryKeys } from './useEventsQuery';
import { recentEventsQueryKeys } from './useRecentEventsQuery';
import { useWebSocket, type WebSocketOptions } from './useWebSocket';
import { logger } from '../services/logger';

import type {
  EventCreatedPayload,
  EventUpdatedPayload,
  EventDeletedPayload,
} from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * WebSocket message structure for event lifecycle events.
 */
interface EventLifecycleMessage<T> {
  type: 'event.created' | 'event.updated' | 'event.deleted';
  data: T;
  timestamp?: string;
}

/**
 * Type guard for event.created messages.
 */
function isEventCreatedMessage(data: unknown): data is EventLifecycleMessage<EventCreatedPayload> {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'event.created' && msg.data !== undefined;
}

/**
 * Type guard for event.updated messages.
 */
function isEventUpdatedMessage(data: unknown): data is EventLifecycleMessage<EventUpdatedPayload> {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'event.updated' && msg.data !== undefined;
}

/**
 * Type guard for event.deleted messages.
 */
function isEventDeletedMessage(data: unknown): data is EventLifecycleMessage<EventDeletedPayload> {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'event.deleted' && msg.data !== undefined;
}

/**
 * Type guard for any event lifecycle message.
 */
function isEventLifecycleMessage(
  data: unknown
): data is EventLifecycleMessage<EventCreatedPayload | EventUpdatedPayload | EventDeletedPayload> {
  return isEventCreatedMessage(data) || isEventUpdatedMessage(data) || isEventDeletedMessage(data);
}

/**
 * Handler callback type for event created events.
 */
export type EventCreatedHandler = (event: EventCreatedPayload) => void;

/**
 * Handler callback type for event updated events.
 */
export type EventUpdatedHandler = (event: EventUpdatedPayload) => void;

/**
 * Handler callback type for event deleted events.
 */
export type EventDeletedHandler = (event: EventDeletedPayload) => void;

/**
 * Options for configuring the useEventLifecycleWebSocket hook.
 */
export interface UseEventLifecycleWebSocketOptions {
  /**
   * WebSocket URL to connect to.
   * @default process.env.VITE_WS_URL || 'ws://localhost:8000/ws/events'
   */
  url?: string;

  /**
   * Whether to automatically invalidate React Query cache on event lifecycle events.
   * @default true
   */
  autoInvalidateCache?: boolean;

  /**
   * Called when a new security event is created.
   */
  onEventCreated?: EventCreatedHandler;

  /**
   * Called when a security event is updated.
   */
  onEventUpdated?: EventUpdatedHandler;

  /**
   * Called when a security event is deleted.
   */
  onEventDeleted?: EventDeletedHandler;

  /**
   * Called for any event lifecycle event (before specific handlers).
   */
  onAnyEventLifecycle?: (
    eventType: 'event.created' | 'event.updated' | 'event.deleted',
    data: EventCreatedPayload | EventUpdatedPayload | EventDeletedPayload
  ) => void;

  /**
   * Whether to enable the WebSocket connection.
   * @default true
   */
  enabled?: boolean;
}

/**
 * Return type for the useEventLifecycleWebSocket hook.
 */
export interface UseEventLifecycleWebSocketReturn {
  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** The last event lifecycle payload received */
  lastEventPayload: EventCreatedPayload | EventUpdatedPayload | EventDeletedPayload | null;

  /** The last event lifecycle type received */
  lastEventType: 'event.created' | 'event.updated' | 'event.deleted' | null;

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

const DEFAULT_WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/ws/events';

/**
 * Hook to subscribe to real-time security event lifecycle WebSocket events.
 *
 * Automatically invalidates React Query cache for events when lifecycle events are received,
 * ensuring the UI stays in sync with server state.
 *
 * @param options - Configuration options
 * @returns WebSocket connection state and handlers
 *
 * @example
 * ```tsx
 * const { isConnected, lastEventType } = useEventLifecycleWebSocket({
 *   onEventCreated: (event) => {
 *     console.log('New event:', event.id);
 *     showNotification(`New ${event.risk_level} risk event detected`);
 *   },
 *   onEventUpdated: (event) => {
 *     console.log('Event updated:', event.id, event.updated_fields);
 *   },
 *   onEventDeleted: (event) => {
 *     console.log('Event deleted:', event.id, event.reason);
 *   },
 * });
 * ```
 */
export function useEventLifecycleWebSocket(
  options: UseEventLifecycleWebSocketOptions = {}
): UseEventLifecycleWebSocketReturn {
  const {
    url: urlOption = DEFAULT_WS_URL,
    autoInvalidateCache = true,
    onEventCreated,
    onEventUpdated,
    onEventDeleted,
    onAnyEventLifecycle,
    enabled = true,
  } = options;
  const url: string = urlOption;

  const queryClient = useQueryClient();

  // Track last event state
  const [lastEventPayload, setLastEventPayload] = useState<
    EventCreatedPayload | EventUpdatedPayload | EventDeletedPayload | null
  >(null);
  const [lastEventType, setLastEventType] = useState<
    'event.created' | 'event.updated' | 'event.deleted' | null
  >(null);

  // Store callbacks in refs to avoid stale closures
  const onEventCreatedRef = useRef(onEventCreated);
  const onEventUpdatedRef = useRef(onEventUpdated);
  const onEventDeletedRef = useRef(onEventDeleted);
  const onAnyEventLifecycleRef = useRef(onAnyEventLifecycle);

  // Update refs when callbacks change
  useEffect(() => {
    onEventCreatedRef.current = onEventCreated;
    onEventUpdatedRef.current = onEventUpdated;
    onEventDeletedRef.current = onEventDeleted;
    onAnyEventLifecycleRef.current = onAnyEventLifecycle;
  });

  // Invalidate events query cache to trigger refetch
  const invalidateEventsCache = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: eventsQueryKeys.all });
    void queryClient.invalidateQueries({ queryKey: recentEventsQueryKeys.all });
  }, [queryClient]);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (data: unknown) => {
      // Check if this is an event lifecycle message
      if (!isEventLifecycleMessage(data)) {
        return;
      }

      const eventMessage = data;
      const eventData = eventMessage.data;
      const eventType = eventMessage.type;

      // Update state
      setLastEventPayload(eventData);
      setLastEventType(eventType);

      // Log the event
      logger.debug('Event lifecycle WebSocket event received', {
        component: 'useEventLifecycleWebSocket',
        eventType,
        eventId: 'id' in eventData ? eventData.id : undefined,
      });

      // Call the generic handler first
      onAnyEventLifecycleRef.current?.(eventType, eventData);

      // Call specific handlers based on event type
      if (isEventCreatedMessage(data)) {
        onEventCreatedRef.current?.(data.data);
      } else if (isEventUpdatedMessage(data)) {
        onEventUpdatedRef.current?.(data.data);
      } else if (isEventDeletedMessage(data)) {
        onEventDeletedRef.current?.(data.data);
      }

      // Invalidate cache to trigger refetch
      if (autoInvalidateCache) {
        invalidateEventsCache();
      }
    },
    [autoInvalidateCache, invalidateEventsCache]
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
  const { isConnected, connect, disconnect, hasExhaustedRetries, reconnectCount } = useWebSocket(
    enabled ? wsOptions : { ...wsOptions, reconnect: false }
  );

  // Manual connect/disconnect if not enabled
  useEffect(() => {
    if (!enabled) {
      disconnect();
    }
  }, [enabled, disconnect]);

  return {
    isConnected,
    lastEventPayload,
    lastEventType,
    connect,
    disconnect,
    hasExhaustedRetries,
    reconnectCount,
  };
}

export default useEventLifecycleWebSocket;
