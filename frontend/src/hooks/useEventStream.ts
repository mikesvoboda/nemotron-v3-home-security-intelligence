import { useState, useCallback, useMemo, useRef, useEffect } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketUrl } from '../services/api';

export interface SecurityEvent {
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

// Backend WebSocket message envelope structure
interface BackendEventMessage {
  type: 'event';
  data: SecurityEvent;
}

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

    // Check if message matches backend envelope structure: {type: "event", data: {...}}
    if (isBackendEventMessage(data)) {
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
    }
    // Ignore non-event messages (e.g., service_status, ping, etc.)
  }, []);

  // Build WebSocket URL using helper (respects VITE_WS_BASE_URL and adds api_key if configured)
  const wsUrl = buildWebSocketUrl('/ws/events');

  const { isConnected } = useWebSocket({
    url: wsUrl,
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
