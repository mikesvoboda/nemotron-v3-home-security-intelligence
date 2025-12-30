import { useState, useCallback, useMemo } from 'react';

import { useWebSocketStatus, ConnectionState, ChannelStatus } from './useWebSocketStatus';
import { buildWebSocketUrl } from '../services/api';

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
}

export interface UseConnectionStatusReturn {
  summary: ConnectionStatusSummary;
  events: SecurityEvent[];
  systemStatus: BackendSystemStatus | null;
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

export function useConnectionStatus(): UseConnectionStatusReturn {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [systemStatus, setSystemStatus] = useState<BackendSystemStatus | null>(null);

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

  const eventsWsUrl = buildWebSocketUrl('/ws/events');
  const systemWsUrl = buildWebSocketUrl('/ws/system');

  const { channelStatus: eventsChannel } = useWebSocketStatus({
    url: eventsWsUrl,
    channelName: 'Events',
    onMessage: handleEventMessage,
  });

  const { channelStatus: systemChannel } = useWebSocketStatus({
    url: systemWsUrl,
    channelName: 'System',
    onMessage: handleSystemMessage,
  });

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  const summary = useMemo((): ConnectionStatusSummary => {
    const anyReconnecting =
      eventsChannel.state === 'reconnecting' || systemChannel.state === 'reconnecting';
    const allConnected =
      eventsChannel.state === 'connected' && systemChannel.state === 'connected';

    let overallState: ConnectionState;
    if (allConnected) {
      overallState = 'connected';
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
      totalReconnectAttempts:
        eventsChannel.reconnectAttempts + systemChannel.reconnectAttempts,
    };
  }, [eventsChannel, systemChannel]);

  return {
    summary,
    events,
    systemStatus,
    clearEvents,
  };
}
