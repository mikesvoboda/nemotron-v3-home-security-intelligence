/**
 * useWebSocketEvent - Hook for subscribing to typed WebSocket events
 *
 * This hook provides a type-safe API for subscribing to specific WebSocket event types.
 * It handles connection management, reconnection, and automatic cleanup.
 *
 * @module hooks/useWebSocketEvent
 *
 * @example
 * ```tsx
 * import { WSEventType } from '../types/websocket-events';
 *
 * function AlertListener() {
 *   // Subscribe to alert.created events with type-safe payload
 *   useWebSocketEvent(
 *     WSEventType.ALERT_CREATED,
 *     (payload) => {
 *       // payload is typed as AlertCreatedPayload
 *       console.log('New alert:', payload.alert_id);
 *       showNotification('New alert received');
 *     }
 *   );
 *
 *   return <div>Listening for alerts...</div>;
 * }
 * ```
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  type ConnectionConfig,
  type TypedSubscription,
  createTypedSubscription,
} from './webSocketManager';
import { logger } from '../services/logger';

import type {
  WSEventType,
  WSEventPayloadMap,
  WSEventHandler,
  WebSocketEventKey,
} from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for the useWebSocketEvent hook.
 */
export interface UseWebSocketEventOptions {
  /**
   * Custom WebSocket URL. Defaults to /ws/events
   */
  url?: string;

  /**
   * Whether to enable the WebSocket connection.
   * @default true
   */
  enabled?: boolean;

  /**
   * Connection configuration (reconnect behavior, timeouts, etc.)
   */
  connectionConfig?: Partial<ConnectionConfig>;

  /**
   * Called when the WebSocket connection is established.
   */
  onConnected?: () => void;

  /**
   * Called when the WebSocket connection is closed.
   */
  onDisconnected?: () => void;

  /**
   * Called when max reconnection attempts are exhausted.
   */
  onMaxRetriesExhausted?: () => void;

  /**
   * Dependencies array - handler will be re-registered when these change.
   * Similar to useEffect dependencies.
   */
  deps?: React.DependencyList;
}

/**
 * Return type for the useWebSocketEvent hook.
 */
export interface UseWebSocketEventReturn {
  /** Whether the WebSocket is currently connected */
  isConnected: boolean;

  /** Number of reconnection attempts */
  reconnectCount: number;

  /** Whether max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;

  /** Timestamp of the last heartbeat received */
  lastHeartbeat: Date | null;

  /** Manually trigger a reconnection */
  reconnect: () => void;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Default connection configuration.
 */
const DEFAULT_CONNECTION_CONFIG: ConnectionConfig = {
  reconnect: true,
  reconnectInterval: 1000,
  maxReconnectAttempts: 15,
  connectionTimeout: 10000,
  autoRespondToHeartbeat: true,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Compute WebSocket URL from options or defaults.
 */
function computeWebSocketUrl(url?: string): string {
  if (url) return url;
  if (typeof window === 'undefined') return 'ws://localhost:8000/ws/events';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/ws/events`;
}

/**
 * Hook for subscribing to a specific WebSocket event type.
 *
 * Provides a type-safe API for handling WebSocket events with automatic
 * connection management, reconnection with exponential backoff, and cleanup.
 *
 * @param eventType - The WSEventType to subscribe to
 * @param handler - Type-safe handler function for the event payload
 * @param options - Configuration options
 * @returns Connection state and control functions
 *
 * @example
 * ```tsx
 * // Subscribe to job completion events
 * useWebSocketEvent(
 *   WSEventType.JOB_COMPLETED,
 *   (payload) => {
 *     toast.success(`Job ${payload.job_id} completed!`);
 *     queryClient.invalidateQueries({ queryKey: ['jobs'] });
 *   },
 *   { enabled: true }
 * );
 *
 * // Subscribe to camera status changes
 * useWebSocketEvent(
 *   WSEventType.CAMERA_ONLINE,
 *   (payload) => {
 *     console.log(`Camera ${payload.camera_name} is now online`);
 *   }
 * );
 * ```
 */
export function useWebSocketEvent<T extends WSEventType>(
  eventType: T,
  handler: WSEventHandler<T>,
  options: UseWebSocketEventOptions = {}
): UseWebSocketEventReturn {
  const {
    url,
    enabled = true,
    connectionConfig,
    onConnected,
    onDisconnected,
    onMaxRetriesExhausted,
    deps = [],
  } = options;

  // State
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [hasExhaustedRetries, setHasExhaustedRetries] = useState(false);
  const [lastHeartbeat, setLastHeartbeat] = useState<Date | null>(null);

  // Refs for callbacks to avoid stale closures
  const handlerRef = useRef(handler);
  const onConnectedRef = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);
  const onMaxRetriesExhaustedRef = useRef(onMaxRetriesExhausted);
  const subscriptionRef = useRef<TypedSubscription | null>(null);

  // Update refs when callbacks change
  useEffect(() => {
    handlerRef.current = handler;
    onConnectedRef.current = onConnected;
    onDisconnectedRef.current = onDisconnected;
    onMaxRetriesExhaustedRef.current = onMaxRetriesExhausted;
  });

  // Compute WebSocket URL
  const wsUrl = useMemo(() => computeWebSocketUrl(url), [url]);

  // Merge connection config with defaults
  const mergedConfig = useMemo(
    () => ({ ...DEFAULT_CONNECTION_CONFIG, ...connectionConfig }),
    [connectionConfig]
  );

  // Stable handler wrapper that uses the ref
  const stableHandler = useCallback((payload: WSEventPayloadMap[T]) => {
    handlerRef.current(payload);
  }, []);

  // Handle reconnect
  const reconnect = useCallback(() => {
    if (subscriptionRef.current) {
      subscriptionRef.current.unsubscribe();
      subscriptionRef.current = null;
    }
    setReconnectCount(0);
    setHasExhaustedRetries(false);
  }, []);

  // Set up WebSocket subscription
  useEffect(() => {
    if (!enabled) {
      setIsConnected(false);
      return;
    }

    logger.debug('Setting up WebSocket event subscription', {
      component: 'useWebSocketEvent',
      eventType,
      url: wsUrl,
    });

    const subscription = createTypedSubscription(wsUrl, mergedConfig, {
      onOpen: () => {
        setIsConnected(true);
        setReconnectCount(0);
        setHasExhaustedRetries(false);
        onConnectedRef.current?.();
      },
      onClose: () => {
        setIsConnected(false);
        onDisconnectedRef.current?.();
      },
      onHeartbeat: () => {
        const state = subscription.getState();
        setLastHeartbeat(state.lastHeartbeat);
      },
      onMaxRetriesExhausted: () => {
        setHasExhaustedRetries(true);
        onMaxRetriesExhaustedRef.current?.();
      },
    });

    // Subscribe to the specific event type
    // Note: We need to map WSEventType to WebSocketEventKey
    // The TypedWebSocketEmitter uses the legacy event keys
    const eventKey = mapWSEventTypeToEventKey(eventType);
    if (eventKey) {
      subscription.on(eventKey as WebSocketEventKey, stableHandler as (data: unknown) => void);
    }

    subscriptionRef.current = subscription;

    // Update reconnect count periodically
    const intervalId = setInterval(() => {
      const state = subscription.getState();
      setReconnectCount(state.reconnectCount);
    }, 1000);

    return () => {
      clearInterval(intervalId);
      subscription.unsubscribe();
      subscriptionRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, wsUrl, mergedConfig, eventType, stableHandler, ...deps]);

  return {
    isConnected,
    reconnectCount,
    hasExhaustedRetries,
    lastHeartbeat,
    reconnect,
  };
}

// ============================================================================
// Multi-Event Subscription
// ============================================================================

/**
 * Handler map for multiple event types.
 */
export type WebSocketEventHandlers = {
  [K in WSEventType]?: WSEventHandler<K>;
};

/**
 * Options for the useWebSocketEvents hook.
 */
export interface UseWebSocketEventsOptions {
  /**
   * Custom WebSocket URL. Defaults to /ws/events
   */
  url?: string;

  /**
   * Whether to enable the WebSocket connection.
   * @default true
   */
  enabled?: boolean;

  /**
   * Connection configuration (reconnect behavior, timeouts, etc.)
   */
  connectionConfig?: Partial<ConnectionConfig>;

  /**
   * Called when the WebSocket connection is established.
   */
  onConnected?: () => void;

  /**
   * Called when the WebSocket connection is closed.
   */
  onDisconnected?: () => void;

  /**
   * Called when max reconnection attempts are exhausted.
   */
  onMaxRetriesExhausted?: () => void;
}

/**
 * Hook for subscribing to multiple WebSocket event types at once.
 *
 * This is more efficient than using multiple useWebSocketEvent hooks
 * as it shares a single WebSocket connection for all subscriptions.
 *
 * @param handlers - Map of event types to handler functions
 * @param options - Configuration options
 * @returns Connection state and control functions
 *
 * @example
 * ```tsx
 * import { WSEventType } from '../types/websocket-events';
 *
 * function SecurityMonitor() {
 *   const { isConnected } = useWebSocketEvents(
 *     {
 *       [WSEventType.ALERT_CREATED]: (payload) => {
 *         toast.warning(`New alert: ${payload.severity}`);
 *       },
 *       [WSEventType.CAMERA_OFFLINE]: (payload) => {
 *         toast.error(`Camera offline: ${payload.camera_name}`);
 *       },
 *       [WSEventType.JOB_COMPLETED]: (payload) => {
 *         toast.success(`Job ${payload.job_id} completed`);
 *       },
 *     },
 *     { enabled: true }
 *   );
 *
 *   return <div>Connected: {isConnected ? 'Yes' : 'No'}</div>;
 * }
 * ```
 */
export function useWebSocketEvents(
  handlers: WebSocketEventHandlers,
  options: UseWebSocketEventsOptions = {}
): UseWebSocketEventReturn {
  const {
    url,
    enabled = true,
    connectionConfig,
    onConnected,
    onDisconnected,
    onMaxRetriesExhausted,
  } = options;

  // State
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [hasExhaustedRetries, setHasExhaustedRetries] = useState(false);
  const [lastHeartbeat, setLastHeartbeat] = useState<Date | null>(null);

  // Refs
  const handlersRef = useRef(handlers);
  const onConnectedRef = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);
  const onMaxRetriesExhaustedRef = useRef(onMaxRetriesExhausted);
  const subscriptionRef = useRef<TypedSubscription | null>(null);

  // Update refs
  useEffect(() => {
    handlersRef.current = handlers;
    onConnectedRef.current = onConnected;
    onDisconnectedRef.current = onDisconnected;
    onMaxRetriesExhaustedRef.current = onMaxRetriesExhausted;
  });

  // Compute URL and config
  const wsUrl = useMemo(() => computeWebSocketUrl(url), [url]);
  const mergedConfig = useMemo(
    () => ({ ...DEFAULT_CONNECTION_CONFIG, ...connectionConfig }),
    [connectionConfig]
  );

  // Handle reconnect
  const reconnect = useCallback(() => {
    if (subscriptionRef.current) {
      subscriptionRef.current.unsubscribe();
      subscriptionRef.current = null;
    }
    setReconnectCount(0);
    setHasExhaustedRetries(false);
  }, []);

  // Set up subscriptions
  useEffect(() => {
    if (!enabled) {
      setIsConnected(false);
      return;
    }

    const subscription = createTypedSubscription(wsUrl, mergedConfig, {
      onOpen: () => {
        setIsConnected(true);
        setReconnectCount(0);
        setHasExhaustedRetries(false);
        onConnectedRef.current?.();
      },
      onClose: () => {
        setIsConnected(false);
        onDisconnectedRef.current?.();
      },
      onHeartbeat: () => {
        const state = subscription.getState();
        setLastHeartbeat(state.lastHeartbeat);
      },
      onMaxRetriesExhausted: () => {
        setHasExhaustedRetries(true);
        onMaxRetriesExhaustedRef.current?.();
      },
    });

    // Subscribe to all provided event types
    const unsubscribeFns: Array<() => void> = [];
    for (const [eventType, eventHandler] of Object.entries(handlersRef.current)) {
      if (typeof eventHandler === 'function') {
        const eventKey = mapWSEventTypeToEventKey(eventType as WSEventType);
        if (eventKey) {
          const unsubscribe = subscription.on(eventKey as WebSocketEventKey, (data: unknown) => {
            // Get the current handler from ref to avoid stale closure
            const currentHandler = handlersRef.current[eventType as WSEventType];
            if (typeof currentHandler === 'function') {
              // Use double cast to bypass type incompatibilities between different payload types
              (currentHandler as (data: unknown) => void)(data);
            }
          });
          unsubscribeFns.push(unsubscribe);
        }
      }
    }

    subscriptionRef.current = subscription;

    // Update reconnect count periodically
    const intervalId = setInterval(() => {
      const state = subscription.getState();
      setReconnectCount(state.reconnectCount);
    }, 1000);

    return () => {
      clearInterval(intervalId);
      unsubscribeFns.forEach((unsub) => unsub());
      subscription.unsubscribe();
      subscriptionRef.current = null;
    };
  }, [enabled, wsUrl, mergedConfig]);

  return {
    isConnected,
    reconnectCount,
    hasExhaustedRetries,
    lastHeartbeat,
    reconnect,
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Map WSEventType enum values to WebSocketEventKey (legacy event keys).
 *
 * The TypedWebSocketEmitter uses legacy event keys like 'event', 'camera_status'.
 * This function maps the new hierarchical event types to the legacy keys
 * where applicable.
 */
function mapWSEventTypeToEventKey(eventType: WSEventType): string | null {
  // Import the WebSocketEventKey type to check valid keys
  const legacyEventKeys = [
    'event',
    'service_status',
    'system_status',
    'camera_status',
    'ping',
    'gpu_stats',
    'error',
    'pong',
  ];

  // For new event types, return the event type as-is (they use the same string)
  // The typed emitter will match based on message.type
  const eventTypeStr = eventType as string;

  // Check if it's a legacy key
  if (legacyEventKeys.includes(eventTypeStr)) {
    return eventTypeStr;
  }

  // For new hierarchical event types, return the string value
  // These will be handled by direct message.type matching
  return eventTypeStr;
}

export default useWebSocketEvent;
