import { useState, useCallback, useMemo, useRef, useEffect } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import {
  type SecurityEventData,
  isEventMessage,
  isHeartbeatMessage,
  isErrorMessage,
} from '../types/websocket';

/**
 * Re-export SecurityEventData as SecurityEvent for backward compatibility.
 * New code should use SecurityEventData from types/websocket.ts directly.
 */
export type SecurityEvent = SecurityEventData;

export interface UseEventStreamReturn {
  events: SecurityEvent[];
  isConnected: boolean;
  latestEvent: SecurityEvent | null;
  clearEvents: () => void;
}

const MAX_EVENTS = 100;

/**
 * Get a unique identifier for an event for deduplication purposes.
 * Uses event_id if available, falls back to id.
 */
function getEventKey(event: SecurityEvent): string {
  const id = event.event_id ?? event.id;
  return String(id);
}

export function useEventStream(): UseEventStreamReturn {
  const [events, setEvents] = useState<SecurityEvent[]>([]);

  // Track mounted state to prevent state updates after unmount (wa0t.31)
  const isMountedRef = useRef(true);

  // Track seen event IDs to prevent duplicate events (wa0t.34)
  const seenEventIdsRef = useRef<Set<string>>(new Set());

  // Set mounted state on mount and cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const handleMessage = useCallback((data: unknown) => {
    // Check if component is still mounted before updating state (wa0t.31)
    if (!isMountedRef.current) {
      return;
    }

    // Use type guards to validate and narrow the message type
    // First, check for event messages (most common case)
    if (isEventMessage(data)) {
      const event = data.data;
      const eventKey = getEventKey(event);

      // Check for duplicate events (wa0t.34)
      if (seenEventIdsRef.current.has(eventKey)) {
        return;
      }

      // Mark event as seen
      seenEventIdsRef.current.add(eventKey);

      setEvents((prevEvents) => {
        // Add new event to the beginning of the array
        const newEvents = [event, ...prevEvents];

        // Keep only the most recent MAX_EVENTS
        return newEvents.slice(0, MAX_EVENTS);
      });
      return;
    }

    // Handle other valid EventsChannelMessage types with exhaustive checking pattern
    if (isHeartbeatMessage(data)) {
      // Heartbeat messages are handled by useWebSocket internally
      return;
    }

    if (isErrorMessage(data)) {
      // Error messages are logged via the structured logger
      logger.warn('WebSocket error received', {
        component: 'useEventStream',
        errorMessage: data.message,
      });
      return;
    }

    // Unknown message types are silently ignored
    // This is intentional - the backend may send messages we don't care about
  }, []);

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  // SECURITY: API key is passed via Sec-WebSocket-Protocol header, not URL query param
  const wsOptions = buildWebSocketOptions('/ws/events');

  const { isConnected } = useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
  });

  const clearEvents = useCallback(() => {
    // Check if component is still mounted before updating state
    if (!isMountedRef.current) {
      return;
    }
    setEvents([]);
    // Also clear the seen event IDs set when events are cleared
    seenEventIdsRef.current.clear();
  }, []);

  const latestEvent = useMemo(() => {
    return events.length > 0 ? events[0] : null;
  }, [events]);

  return {
    events,
    isConnected,
    latestEvent,
    clearEvents,
  };
}
