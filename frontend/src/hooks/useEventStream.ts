import { useState, useCallback, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';

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

  const handleMessage = useCallback((data: unknown) => {
    // Check if message matches backend envelope structure: {type: "event", data: {...}}
    if (isBackendEventMessage(data)) {
      const event = data.data;

      setEvents((prevEvents) => {
        // Add new event to the beginning of the array
        const newEvents = [event, ...prevEvents];

        // Keep only the most recent MAX_EVENTS
        return newEvents.slice(0, MAX_EVENTS);
      });
    }
    // Ignore non-event messages (e.g., service_status, ping, etc.)
  }, []);

  const wsProtocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';

  const { isConnected } = useWebSocket({
    url: wsProtocol + '//' + wsHost + '/ws/events',
    onMessage: handleMessage,
  });

  const clearEvents = useCallback(() => {
    setEvents([]);
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
