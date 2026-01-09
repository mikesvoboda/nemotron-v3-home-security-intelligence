import { LRUCache } from 'lru-cache';
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

// NEM-2020: LRU cache configuration for deduplication
// Prevents unbounded memory growth over long sessions
const MAX_SEEN_IDS = 10000;
const SEEN_IDS_TTL_MS = 1000 * 60 * 60; // 1 hour

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
  // NEM-2020: Use LRU cache instead of Set to prevent unbounded memory growth
  const seenEventIdsRef = useRef<LRUCache<string, true>>(
    new LRUCache<string, true>({
      max: MAX_SEEN_IDS,
      ttl: SEEN_IDS_TTL_MS,
    })
  );

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

      // Mark event as seen (NEM-2020: use .set() for LRU cache)
      seenEventIdsRef.current.set(eventKey, true);

      setEvents((prevEvents) => {
        // Add new event to the beginning of the array
        const newEvents = [event, ...prevEvents];

        // Keep only the most recent MAX_EVENTS
        const trimmedEvents = newEvents.slice(0, MAX_EVENTS);

        // NEM-1998: Bound the seen IDs set to prevent memory leaks
        // When events are evicted from the array, remove their IDs from the set
        // This ensures the set doesn't grow unbounded over time
        if (newEvents.length > MAX_EVENTS) {
          const evictedEvents = newEvents.slice(MAX_EVENTS);
          for (const evictedEvent of evictedEvents) {
            const evictedKey = getEventKey(evictedEvent);
            seenEventIdsRef.current.delete(evictedKey);
          }
        }

        return trimmedEvents;
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
    // Also clear the seen event IDs cache when events are cleared
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
