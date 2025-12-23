import { useState, useCallback, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';

export interface SecurityEvent {
  id: string;
  camera_id: string;
  camera_name: string;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  summary: string;
  timestamp: string;
}

export interface UseEventStreamReturn {
  events: SecurityEvent[];
  isConnected: boolean;
  latestEvent: SecurityEvent | null;
  clearEvents: () => void;
}

const MAX_EVENTS = 100;

export function useEventStream(): UseEventStreamReturn {
  const [events, setEvents] = useState<SecurityEvent[]>([]);

  const handleMessage = useCallback((data: unknown) => {
    // Validate that the message is a SecurityEvent
    if (
      data &&
      typeof data === 'object' &&
      'id' in data &&
      'camera_id' in data &&
      'camera_name' in data &&
      'risk_score' in data &&
      'risk_level' in data &&
      'summary' in data &&
      'timestamp' in data
    ) {
      const event = data as SecurityEvent;

      setEvents((prevEvents) => {
        // Add new event to the beginning of the array
        const newEvents = [event, ...prevEvents];

        // Keep only the most recent MAX_EVENTS
        return newEvents.slice(0, MAX_EVENTS);
      });
    }
  }, []);

  const { isConnected } = useWebSocket({
    url: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/events`,
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
