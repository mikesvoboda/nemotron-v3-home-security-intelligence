/**
 * Hook for subscribing to camera status WebSocket events (NEM-2295).
 *
 * This hook provides real-time camera status updates via WebSocket,
 * allowing components to react to camera.online, camera.offline,
 * camera.error, and camera.updated events.
 *
 * @example
 * ```tsx
 * function CameraMonitor() {
 *   const { cameraStatuses, isConnected } = useCameraStatusWebSocket({
 *     onCameraOnline: (event) => console.log('Camera online:', event.camera_name),
 *     onCameraOffline: (event) => console.log('Camera offline:', event.camera_name),
 *   });
 *
 *   return (
 *     <div>
 *       {Object.entries(cameraStatuses).map(([id, status]) => (
 *         <div key={id}>{status.camera_name}: {status.status}</div>
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  type ConnectionConfig,
  type TypedSubscription,
  createTypedSubscription,
} from './webSocketManager';

import type {
  CameraEventType,
  CameraStatusEventPayload,
  CameraStatusValue,
} from '../types/websocket-events';

/**
 * Camera status state for a single camera.
 */
export interface CameraStatusState {
  /** Camera ID */
  camera_id: string;
  /** Human-readable camera name */
  camera_name: string;
  /** Current status */
  status: CameraStatusValue;
  /** Last update timestamp */
  lastUpdated: string;
  /** Previous status (if available) */
  previousStatus?: CameraStatusValue | null;
  /** Reason for the status change (if available) */
  reason?: string | null;
}

/**
 * Options for the useCameraStatusWebSocket hook.
 */
export interface UseCameraStatusWebSocketOptions {
  /** Custom WebSocket URL. Defaults to /ws/events */
  url?: string;
  /** Connection configuration */
  connectionConfig?: Partial<ConnectionConfig>;
  /** Callback when a camera comes online */
  onCameraOnline?: (event: CameraStatusEventPayload) => void;
  /** Callback when a camera goes offline */
  onCameraOffline?: (event: CameraStatusEventPayload) => void;
  /** Callback when a camera encounters an error */
  onCameraError?: (event: CameraStatusEventPayload) => void;
  /** Callback when a camera configuration is updated */
  onCameraUpdated?: (event: CameraStatusEventPayload) => void;
  /** Callback for any camera status change */
  onCameraStatusChange?: (event: CameraStatusEventPayload) => void;
  /** Whether to enable the WebSocket connection. Default: true */
  enabled?: boolean;
}

/**
 * Return type for the useCameraStatusWebSocket hook.
 */
export interface UseCameraStatusWebSocketReturn {
  /** Map of camera ID to current status state */
  cameraStatuses: Record<string, CameraStatusState>;
  /** Whether the WebSocket is currently connected */
  isConnected: boolean;
  /** Number of reconnection attempts */
  reconnectCount: number;
  /** Last camera status event received */
  lastEvent: CameraStatusEventPayload | null;
  /** Manually trigger a reconnection */
  reconnect: () => void;
}

/**
 * Default connection configuration.
 */
const DEFAULT_CONNECTION_CONFIG: ConnectionConfig = {
  reconnect: true,
  reconnectInterval: 1000,
  maxReconnectAttempts: 10,
  connectionTimeout: 5000,
  autoRespondToHeartbeat: true,
};

/**
 * Map event type to the appropriate callback.
 */
function getCallbackForEventType(
  eventType: CameraEventType,
  options: UseCameraStatusWebSocketOptions
): ((event: CameraStatusEventPayload) => void) | undefined {
  switch (eventType) {
    case 'camera.online':
      return options.onCameraOnline;
    case 'camera.offline':
      return options.onCameraOffline;
    case 'camera.error':
      return options.onCameraError;
    case 'camera.updated':
      return options.onCameraUpdated;
    default:
      return undefined;
  }
}

/**
 * Hook for subscribing to camera status WebSocket events.
 *
 * Provides real-time updates when camera status changes (online, offline, error, updated).
 * Automatically manages WebSocket connection lifecycle with reconnection support.
 */
export function useCameraStatusWebSocket(
  options: UseCameraStatusWebSocketOptions = {}
): UseCameraStatusWebSocketReturn {
  const { url, connectionConfig, onCameraStatusChange, enabled = true } = options;

  // State
  const [cameraStatuses, setCameraStatuses] = useState<Record<string, CameraStatusState>>({});
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [lastEvent, setLastEvent] = useState<CameraStatusEventPayload | null>(null);
  const [subscription, setSubscription] = useState<TypedSubscription | null>(null);

  // Compute WebSocket URL
  const wsUrl = useMemo(() => {
    if (url) return url;
    const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
    return `${protocol}//${host}/ws/events`;
  }, [url]);

  // Merge connection config with defaults
  const mergedConfig = useMemo(
    () => ({ ...DEFAULT_CONNECTION_CONFIG, ...connectionConfig }),
    [connectionConfig]
  );

  // Handle camera status event
  const handleCameraStatusEvent = useCallback(
    (event: CameraStatusEventPayload) => {
      setLastEvent(event);

      // Update camera status state
      setCameraStatuses((prev) => ({
        ...prev,
        [event.camera_id]: {
          camera_id: event.camera_id,
          camera_name: event.camera_name,
          status: event.status,
          lastUpdated: event.timestamp,
          previousStatus: event.previous_status,
          reason: event.reason,
        },
      }));

      // Call event-specific callback
      const specificCallback = getCallbackForEventType(event.event_type, options);
      specificCallback?.(event);

      // Call general callback
      onCameraStatusChange?.(event);
    },
    [options, onCameraStatusChange]
  );

  // Handle reconnect
  const reconnect = useCallback(() => {
    if (subscription) {
      subscription.unsubscribe();
    }
    // Force re-creation of subscription
    setSubscription(null);
    setReconnectCount(0);
  }, [subscription]);

  // Set up WebSocket subscription
  useEffect(() => {
    if (!enabled) {
      setIsConnected(false);
      return;
    }

    const typedSubscription = createTypedSubscription(wsUrl, mergedConfig, {
      onOpen: () => {
        setIsConnected(true);
        setReconnectCount(0);
      },
      onClose: () => {
        setIsConnected(false);
      },
      onError: () => {
        setIsConnected(false);
      },
      onMaxRetriesExhausted: () => {
        setIsConnected(false);
      },
    });

    // Subscribe to camera_status events
    typedSubscription.on('camera_status', handleCameraStatusEvent);

    setSubscription(typedSubscription);

    // Update reconnect count from connection state
    const updateReconnectCount = () => {
      const state = typedSubscription.getState();
      setReconnectCount(state.reconnectCount);
    };

    // Check connection state periodically
    const intervalId = setInterval(updateReconnectCount, 1000);

    return () => {
      clearInterval(intervalId);
      typedSubscription.unsubscribe();
    };
  }, [enabled, wsUrl, mergedConfig, handleCameraStatusEvent]);

  return {
    cameraStatuses,
    isConnected,
    reconnectCount,
    lastEvent,
    reconnect,
  };
}

export default useCameraStatusWebSocket;
