/**
 * Hook for subscribing to zone-related WebSocket events (NEM-5073)
 *
 * This hook provides a type-safe way to subscribe to zone events:
 * - zone.crossing: Entity crossed a zone boundary
 * - zone.dwell_started: Entity entered a zone
 * - zone.dwell_alert: Entity dwell time exceeded threshold
 * - zone.approach: Entity approaching a zone
 *
 * @example
 * ```tsx
 * const { isConnected, reconnectCount } = useZoneEventsWebSocket({
 *   onZoneCrossing: (data) => console.log('Zone crossing:', data),
 *   onZoneDwellAlert: (data) => console.log('Dwell alert:', data),
 * });
 * ```
 */

import { useEffect, useRef, useCallback } from 'react';

import {
  createTypedSubscription,
  type TypedSubscription,
  type ConnectionConfig,
} from './webSocketManager';
import { logger } from '../services/logger';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Zone crossing event payload
 */
export interface ZoneCrossingEvent {
  zone_id: string;
  zone_name?: string;
  entity_id: string;
  entity_type?: string;
  camera_id: string;
  timestamp: string;
  direction: string;
  bbox?: { x: number; y: number; width: number; height: number };
}

/**
 * Zone dwell started event payload
 */
export interface ZoneDwellStartedEvent {
  zone_id: string;
  zone_name?: string;
  entity_id: string;
  entity_type?: string;
  camera_id: string;
  timestamp: string;
}

/**
 * Zone dwell alert event payload
 */
export interface ZoneDwellAlertEvent {
  zone_id: string;
  zone_name?: string;
  entity_id: string;
  entity_type?: string;
  camera_id: string;
  timestamp: string;
  dwell_duration_seconds: number;
  threshold_seconds: number;
}

/**
 * Zone approach event payload
 */
export interface ZoneApproachEvent {
  zone_id: string;
  zone_name?: string;
  entity_id: string;
  entity_type?: string;
  camera_id: string;
  timestamp: string;
  direction: string;
  speed: number;
  eta_seconds: number;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for ZoneCrossingEvent
 */
export function isZoneCrossingEvent(data: unknown): data is ZoneCrossingEvent {
  if (!data || typeof data !== 'object') return false;
  const obj = data as Record<string, unknown>;
  return (
    typeof obj.zone_id === 'string' &&
    typeof obj.entity_id === 'string' &&
    typeof obj.camera_id === 'string' &&
    typeof obj.timestamp === 'string' &&
    typeof obj.direction === 'string'
  );
}

/**
 * Type guard for ZoneDwellStartedEvent
 */
export function isZoneDwellStartedEvent(data: unknown): data is ZoneDwellStartedEvent {
  if (!data || typeof data !== 'object') return false;
  const obj = data as Record<string, unknown>;
  return (
    typeof obj.zone_id === 'string' &&
    typeof obj.entity_id === 'string' &&
    typeof obj.camera_id === 'string' &&
    typeof obj.timestamp === 'string'
  );
}

/**
 * Type guard for ZoneDwellAlertEvent
 */
export function isZoneDwellAlertEvent(data: unknown): data is ZoneDwellAlertEvent {
  if (!data || typeof data !== 'object') return false;
  const obj = data as Record<string, unknown>;
  return (
    typeof obj.zone_id === 'string' &&
    typeof obj.entity_id === 'string' &&
    typeof obj.camera_id === 'string' &&
    typeof obj.timestamp === 'string' &&
    typeof obj.dwell_duration_seconds === 'number' &&
    typeof obj.threshold_seconds === 'number' &&
    obj.dwell_duration_seconds >= 0 &&
    obj.threshold_seconds > 0
  );
}

/**
 * Type guard for ZoneApproachEvent
 */
export function isZoneApproachEvent(data: unknown): data is ZoneApproachEvent {
  if (!data || typeof data !== 'object') return false;
  const obj = data as Record<string, unknown>;
  return (
    typeof obj.zone_id === 'string' &&
    typeof obj.entity_id === 'string' &&
    typeof obj.camera_id === 'string' &&
    typeof obj.timestamp === 'string' &&
    typeof obj.direction === 'string' &&
    typeof obj.speed === 'number' &&
    typeof obj.eta_seconds === 'number' &&
    obj.speed >= 0 &&
    obj.eta_seconds >= 0
  );
}

// ============================================================================
// Hook Options
// ============================================================================

/**
 * Options for useZoneEventsWebSocket hook
 */
export interface UseZoneEventsWebSocketOptions {
  /** Callback for zone.crossing events */
  onZoneCrossing?: (data: ZoneCrossingEvent) => void;
  /** Callback for zone.dwell_started events */
  onZoneDwellStarted?: (data: ZoneDwellStartedEvent) => void;
  /** Callback for zone.dwell_alert events */
  onZoneDwellAlert?: (data: ZoneDwellAlertEvent) => void;
  /** Callback for zone.approach events */
  onZoneApproach?: (data: ZoneApproachEvent) => void;
  /** Custom WebSocket URL (defaults to /ws/events) */
  wsUrl?: string;
  /** Whether to auto-connect (defaults to true) */
  autoConnect?: boolean;
}

/**
 * Return value from useZoneEventsWebSocket hook
 */
export interface UseZoneEventsWebSocketResult {
  /** Whether the WebSocket is currently connected */
  isConnected: boolean;
  /** Number of reconnection attempts */
  reconnectCount: number;
  /** Whether all retry attempts have been exhausted */
  hasExhaustedRetries: boolean;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Default WebSocket configuration
 */
const DEFAULT_CONFIG: ConnectionConfig = {
  reconnect: true,
  reconnectInterval: 1000,
  maxReconnectAttempts: 5,
  connectionTimeout: 5000,
  autoRespondToHeartbeat: true,
};

/**
 * Get the WebSocket URL for zone events
 */
function getWebSocketUrl(customUrl?: string): string {
  if (customUrl) return customUrl;

  // Build URL based on current location
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
  return `${protocol}//${host}/ws/events`;
}

/**
 * Hook for subscribing to zone-related WebSocket events
 *
 * Provides type-safe callbacks for zone crossing, dwell, and approach events.
 * Automatically validates incoming event data using type guards.
 */
export function useZoneEventsWebSocket(
  options: UseZoneEventsWebSocketOptions = {}
): UseZoneEventsWebSocketResult {
  const {
    onZoneCrossing,
    onZoneDwellStarted,
    onZoneDwellAlert,
    onZoneApproach,
    wsUrl,
    autoConnect = true,
  } = options;

  // Use refs for callbacks to avoid re-subscribing on callback changes
  const callbacksRef = useRef({
    onZoneCrossing,
    onZoneDwellStarted,
    onZoneDwellAlert,
    onZoneApproach,
  });

  // Update refs when callbacks change
  useEffect(() => {
    callbacksRef.current = {
      onZoneCrossing,
      onZoneDwellStarted,
      onZoneDwellAlert,
      onZoneApproach,
    };
  }, [onZoneCrossing, onZoneDwellStarted, onZoneDwellAlert, onZoneApproach]);

  // Store subscription reference
  const subscriptionRef = useRef<TypedSubscription | null>(null);
  const unsubscribersRef = useRef<Array<() => void>>([]);

  // Connection state
  const stateRef = useRef({
    isConnected: false,
    reconnectCount: 0,
    hasExhaustedRetries: false,
  });

  // Create stable event handlers
  const handleZoneCrossing = useCallback((data: unknown) => {
    // Extract data from WebSocket message format
    const eventData = typeof data === 'object' && data !== null && 'data' in data
      ? (data as { data: unknown }).data
      : data;

    if (isZoneCrossingEvent(eventData)) {
      callbacksRef.current.onZoneCrossing?.(eventData);
    } else {
      logger.warn('Received invalid zone.crossing event data', {
        component: 'useZoneEventsWebSocket',
        data: eventData,
      });
    }
  }, []);

  const handleZoneDwellStarted = useCallback((data: unknown) => {
    const eventData = typeof data === 'object' && data !== null && 'data' in data
      ? (data as { data: unknown }).data
      : data;

    if (isZoneDwellStartedEvent(eventData)) {
      callbacksRef.current.onZoneDwellStarted?.(eventData);
    } else {
      logger.warn('Received invalid zone.dwell_started event data', {
        component: 'useZoneEventsWebSocket',
        data: eventData,
      });
    }
  }, []);

  const handleZoneDwellAlert = useCallback((data: unknown) => {
    const eventData = typeof data === 'object' && data !== null && 'data' in data
      ? (data as { data: unknown }).data
      : data;

    if (isZoneDwellAlertEvent(eventData)) {
      callbacksRef.current.onZoneDwellAlert?.(eventData);
    } else {
      logger.warn('Received invalid zone.dwell_alert event data', {
        component: 'useZoneEventsWebSocket',
        data: eventData,
      });
    }
  }, []);

  const handleZoneApproach = useCallback((data: unknown) => {
    const eventData = typeof data === 'object' && data !== null && 'data' in data
      ? (data as { data: unknown }).data
      : data;

    if (isZoneApproachEvent(eventData)) {
      callbacksRef.current.onZoneApproach?.(eventData);
    } else {
      logger.warn('Received invalid zone.approach event data', {
        component: 'useZoneEventsWebSocket',
        data: eventData,
      });
    }
  }, []);

  // Connect to WebSocket and subscribe to events
  useEffect(() => {
    if (!autoConnect) return;

    const url = getWebSocketUrl(wsUrl);

    logger.debug('Connecting to zone events WebSocket', {
      component: 'useZoneEventsWebSocket',
      url,
    });

    const subscription = createTypedSubscription(url, DEFAULT_CONFIG, {
      onOpen: () => {
        stateRef.current.isConnected = true;
        stateRef.current.reconnectCount = 0;
        logger.info('Zone events WebSocket connected', {
          component: 'useZoneEventsWebSocket',
        });
      },
      onClose: () => {
        stateRef.current.isConnected = false;
        const state = subscription.getState();
        stateRef.current.reconnectCount = state.reconnectCount;
        logger.info('Zone events WebSocket disconnected', {
          component: 'useZoneEventsWebSocket',
          reconnectCount: state.reconnectCount,
        });
      },
      onError: (error) => {
        logger.error('Zone events WebSocket error', {
          component: 'useZoneEventsWebSocket',
          error: error.type,
        });
      },
      onMaxRetriesExhausted: () => {
        stateRef.current.hasExhaustedRetries = true;
        logger.error('Zone events WebSocket max retries exhausted', {
          component: 'useZoneEventsWebSocket',
        });
      },
    });

    subscriptionRef.current = subscription;

    // Subscribe to zone events using the typed subscription interface
    // The 'on' method returns an unsubscribe function
    const unsubscribers: Array<() => void> = [];

    // Subscribe to zone.crossing events
    if (callbacksRef.current.onZoneCrossing) {
      // Use the emitter's handleMessage which routes by message type
      const unsub = subscription.on('zone.crossing' as never, handleZoneCrossing as never);
      unsubscribers.push(unsub);
    }

    // Subscribe to zone.dwell_started events
    if (callbacksRef.current.onZoneDwellStarted) {
      const unsub = subscription.on('zone.dwell_started' as never, handleZoneDwellStarted as never);
      unsubscribers.push(unsub);
    }

    // Subscribe to zone.dwell_alert events
    if (callbacksRef.current.onZoneDwellAlert) {
      const unsub = subscription.on('zone.dwell_alert' as never, handleZoneDwellAlert as never);
      unsubscribers.push(unsub);
    }

    // Subscribe to zone.approach events
    if (callbacksRef.current.onZoneApproach) {
      const unsub = subscription.on('zone.approach' as never, handleZoneApproach as never);
      unsubscribers.push(unsub);
    }

    unsubscribersRef.current = unsubscribers;

    // Cleanup on unmount
    return () => {
      // Unsubscribe from all event handlers
      unsubscribersRef.current.forEach((unsub) => unsub());
      unsubscribersRef.current = [];

      // Unsubscribe from WebSocket
      subscription.unsubscribe();
      subscriptionRef.current = null;

      logger.debug('Zone events WebSocket cleaned up', {
        component: 'useZoneEventsWebSocket',
      });
    };
  }, [
    autoConnect,
    wsUrl,
    handleZoneCrossing,
    handleZoneDwellStarted,
    handleZoneDwellAlert,
    handleZoneApproach,
  ]);

  // Return current connection state
  const getState = useCallback((): UseZoneEventsWebSocketResult => {
    if (subscriptionRef.current) {
      const state = subscriptionRef.current.getState();
      return {
        isConnected: state.isConnected,
        reconnectCount: state.reconnectCount,
        hasExhaustedRetries: state.hasExhaustedRetries,
      };
    }
    return stateRef.current;
  }, []);

  // Return state - will update when component re-renders
  return getState();
}

export default useZoneEventsWebSocket;
