/**
 * Hook for subscribing to camera status WebSocket events (NEM-2295).
 *
 * This hook provides real-time camera status updates via WebSocket,
 * allowing components to react to camera.online, camera.offline,
 * camera.error, camera.updated, camera.enabled, camera.disabled,
 * and camera.config_updated events.
 *
 * Enhanced in NEM-3634 to support:
 * - camera.enabled - Camera was enabled
 * - camera.disabled - Camera was disabled
 * - camera.config_updated - Camera configuration was changed
 *
 * @example
 * ```tsx
 * function CameraMonitor() {
 *   const { cameraStatuses, isConnected } = useCameraStatusWebSocket({
 *     onCameraOnline: (event) => console.log('Camera online:', event.camera_name),
 *     onCameraOffline: (event) => console.log('Camera offline:', event.camera_name),
 *     onCameraEnabled: (event) => console.log('Camera enabled:', event.camera_id),
 *     onCameraDisabled: (event) => console.log('Camera disabled:', event.camera_id),
 *     onCameraConfigUpdated: (event) => console.log('Camera config updated:', event.camera_name),
 *     showToasts: true, // Enable toast notifications
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

import { useToast } from './useToast';

import type {
  CameraConfigUpdatedPayload,
  CameraDisabledPayload,
  CameraEnabledPayload,
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
  /** Callback when a camera configuration is updated (legacy status event) */
  onCameraUpdated?: (event: CameraStatusEventPayload) => void;
  /** Callback for any camera status change */
  onCameraStatusChange?: (event: CameraStatusEventPayload) => void;
  /** Callback when a camera is enabled (NEM-3634) */
  onCameraEnabled?: (event: CameraEnabledPayload) => void;
  /** Callback when a camera is disabled (NEM-3634) */
  onCameraDisabled?: (event: CameraDisabledPayload) => void;
  /** Callback when camera configuration is updated (NEM-3634) */
  onCameraConfigUpdated?: (event: CameraConfigUpdatedPayload) => void;
  /** Whether to show toast notifications for camera events. Default: false */
  showToasts?: boolean;
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
 * Also handles camera.enabled, camera.disabled, and camera.config_updated events (NEM-3634).
 * Automatically manages WebSocket connection lifecycle with reconnection support.
 */
export function useCameraStatusWebSocket(
  options: UseCameraStatusWebSocketOptions = {}
): UseCameraStatusWebSocketReturn {
  const {
    url,
    connectionConfig,
    onCameraStatusChange,
    onCameraEnabled,
    onCameraDisabled,
    onCameraConfigUpdated,
    showToasts = false,
    enabled = true,
  } = options;

  // Toast notifications
  const toast = useToast();

  // State
  const [cameraStatuses, setCameraStatuses] = useState<Record<string, CameraStatusState>>({});
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [lastEvent, setLastEvent] = useState<CameraStatusEventPayload | null>(null);
  const [subscription, setSubscription] = useState<TypedSubscription | null>(null);

  // Compute WebSocket URL
  const wsUrl = useMemo(() => {
    if (url) return url;
    const protocol =
      typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
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

      // Show toast notifications
      if (showToasts) {
        switch (event.event_type) {
          case 'camera.online':
            toast.success(`Camera "${event.camera_name}" is now online`);
            break;
          case 'camera.offline':
            toast.warning(`Camera "${event.camera_name}" went offline`);
            break;
          case 'camera.error':
            toast.error(`Camera "${event.camera_name}" encountered an error`, {
              description: event.reason ?? undefined,
            });
            break;
        }
      }
    },
    [options, onCameraStatusChange, showToasts, toast]
  );

  // Handle camera enabled event (NEM-3634)
  const handleCameraEnabledEvent = useCallback(
    (event: CameraEnabledPayload) => {
      // Update camera status to online when enabled
      setCameraStatuses((prev) => {
        const existing = prev[event.camera_id];
        return {
          ...prev,
          [event.camera_id]: {
            camera_id: event.camera_id,
            camera_name: existing?.camera_name ?? event.camera_id,
            status: 'online',
            lastUpdated: event.enabled_at,
            previousStatus: existing?.status ?? null,
          },
        };
      });

      // Call callback
      onCameraEnabled?.(event);

      // Show toast notification
      if (showToasts) {
        toast.success(`Camera enabled`, {
          description: `Camera ${event.camera_id} has been enabled`,
        });
      }
    },
    [onCameraEnabled, showToasts, toast]
  );

  // Handle camera disabled event (NEM-3634)
  const handleCameraDisabledEvent = useCallback(
    (event: CameraDisabledPayload) => {
      // Update camera status to offline when disabled
      setCameraStatuses((prev) => {
        const existing = prev[event.camera_id];
        return {
          ...prev,
          [event.camera_id]: {
            camera_id: event.camera_id,
            camera_name: existing?.camera_name ?? event.camera_id,
            status: 'offline',
            lastUpdated: event.disabled_at,
            previousStatus: existing?.status ?? null,
            reason: event.reason ?? null,
          },
        };
      });

      // Call callback
      onCameraDisabled?.(event);

      // Show toast notification
      if (showToasts) {
        toast.info(`Camera disabled`, {
          description: event.reason ?? `Camera ${event.camera_id} has been disabled`,
        });
      }
    },
    [onCameraDisabled, showToasts, toast]
  );

  // Handle camera config updated event (NEM-3634)
  const handleCameraConfigUpdatedEvent = useCallback(
    (event: CameraConfigUpdatedPayload) => {
      // Update last updated timestamp
      setCameraStatuses((prev) => {
        const existing = prev[event.camera_id];
        if (!existing) return prev;
        return {
          ...prev,
          [event.camera_id]: {
            ...existing,
            camera_name: event.camera_name,
            lastUpdated: event.updated_at,
          },
        };
      });

      // Call callback
      onCameraConfigUpdated?.(event);

      // Show toast notification
      if (showToasts) {
        const fieldsInfo = event.updated_fields?.length
          ? ` (${event.updated_fields.join(', ')})`
          : '';
        toast.info(`Camera configuration updated${fieldsInfo}`, {
          description: `"${event.camera_name}" settings have been updated`,
        });
      }
    },
    [onCameraConfigUpdated, showToasts, toast]
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

    // Subscribe to camera_status events (legacy and hierarchical)
    typedSubscription.on('camera_status', handleCameraStatusEvent);

    // Subscribe to camera config events (NEM-3634)
    typedSubscription.on('camera.enabled', handleCameraEnabledEvent);
    typedSubscription.on('camera.disabled', handleCameraDisabledEvent);
    typedSubscription.on('camera.config_updated', handleCameraConfigUpdatedEvent);

    // Also subscribe to hierarchical camera status events
    typedSubscription.on('camera.online', handleCameraStatusEvent);
    typedSubscription.on('camera.offline', handleCameraStatusEvent);
    typedSubscription.on('camera.error', handleCameraStatusEvent);

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
  }, [
    enabled,
    wsUrl,
    mergedConfig,
    handleCameraStatusEvent,
    handleCameraEnabledEvent,
    handleCameraDisabledEvent,
    handleCameraConfigUpdatedEvent,
  ]);

  return {
    cameraStatuses,
    isConnected,
    reconnectCount,
    lastEvent,
    reconnect,
  };
}

export default useCameraStatusWebSocket;
