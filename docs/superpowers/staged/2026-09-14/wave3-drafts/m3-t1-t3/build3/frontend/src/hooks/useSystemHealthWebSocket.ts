/**
 * useSystemHealthWebSocket - WebSocket hook for system health state transitions
 *
 * NEM-3169: Consumes system.health_changed WebSocket events broadcast by the backend
 * when the overall system health state transitions between healthy/degraded/unhealthy.
 *
 * Events handled:
 * - system.health_changed: System health state transitions with component breakdown
 *
 * @module hooks/useSystemHealthWebSocket
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import { isHeartbeatMessage, isErrorMessage } from '../types/websocket';

import type { SystemHealthChangedPayload } from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Health status values
 */
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

/**
 * Component health map
 */
export type ComponentHealthMap = Record<string, HealthStatus>;

/**
 * Health change entry with timestamp for history tracking
 */
export interface HealthChangeEntry extends SystemHealthChangedPayload {
  /** ISO timestamp when this change was received */
  timestamp: string;
}

/**
 * Callback type for health change events
 */
export type HealthChangeHandler = (change: SystemHealthChangedPayload) => void;

/**
 * Options for configuring the useSystemHealthWebSocket hook
 */
export interface UseSystemHealthWebSocketOptions {
  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of historical entries to keep
   * @default 20
   */
  maxHistory?: number;

  /**
   * Called when system health changes
   */
  onHealthChange?: HealthChangeHandler;
}

/**
 * Return type for the useSystemHealthWebSocket hook
 */
export interface UseSystemHealthWebSocketReturn {
  /** Current system health (null if not yet received) */
  health: HealthStatus | null;

  /** Previous health state before the last change */
  previousHealth: HealthStatus | null;

  /** Map of component names to their health status */
  components: ComponentHealthMap;

  /** History of health transitions (newest first) */
  history: HealthChangeEntry[];

  /** ISO timestamp of last health change */
  lastUpdate: string | null;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** True if system health is 'healthy' */
  isHealthy: boolean;

  /** True if system health is 'degraded' */
  isDegraded: boolean;

  /** True if system health is 'unhealthy' */
  isUnhealthy: boolean;

  /** Get health status for a specific component */
  getComponentHealth: (componentName: string) => HealthStatus | undefined;

  /** Check if a component is healthy */
  isComponentHealthy: (componentName: string) => boolean;

  /** Get list of unhealthy component names */
  getUnhealthyComponents: () => string[];

  /** Clear the history buffer */
  clearHistory: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_HISTORY = 20;

// ============================================================================
// Type Guard
// ============================================================================

/**
 * Type guard for system.health_changed messages
 */
function isSystemHealthChangedMessage(
  value: unknown
): value is { type: 'system.health_changed'; data: SystemHealthChangedPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const msg = value as Record<string, unknown>;
  if (msg.type !== 'system.health_changed') {
    return false;
  }

  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const data = msg.data as Record<string, unknown>;
  // health field is required
  if (
    typeof data.health !== 'string' ||
    !['healthy', 'degraded', 'unhealthy'].includes(data.health)
  ) {
    return false;
  }

  return true;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to system health change WebSocket events.
 *
 * Tracks system-wide health state transitions and component-level health status.
 *
 * @param options - Configuration options
 * @returns System health state and utilities
 *
 * @example
 * ```tsx
 * const {
 *   health,
 *   isHealthy,
 *   isDegraded,
 *   components,
 *   getUnhealthyComponents,
 * } = useSystemHealthWebSocket({
 *   onHealthChange: (change) => {
 *     if (change.health === 'unhealthy') {
 *       showAlert('System health critical!');
 *     }
 *   },
 * });
 *
 * // Display unhealthy components
 * if (!isHealthy) {
 *   const failing = getUnhealthyComponents();
 *   console.log('Unhealthy components:', failing);
 * }
 * ```
 */
export function useSystemHealthWebSocket(
  options: UseSystemHealthWebSocketOptions = {}
): UseSystemHealthWebSocketReturn {
  const { enabled = true, maxHistory = DEFAULT_MAX_HISTORY, onHealthChange } = options;

  // State
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [previousHealth, setPreviousHealth] = useState<HealthStatus | null>(null);
  const [components, setComponents] = useState<ComponentHealthMap>({});
  const [history, setHistory] = useState<HealthChangeEntry[]>([]);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  // Track mounted state
  const isMountedRef = useRef(true);

  // Store callback in ref
  const onHealthChangeRef = useRef(onHealthChange);

  useEffect(() => {
    onHealthChangeRef.current = onHealthChange;
  });

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (data: unknown) => {
      if (!isMountedRef.current) {
        return;
      }

      // Handle system.health_changed messages
      if (isSystemHealthChangedMessage(data)) {
        const healthData = data.data;
        const timestamp = new Date().toISOString();

        logger.debug('System.health_changed event received', {
          component: 'useSystemHealthWebSocket',
          health: healthData.health,
          previous_health: healthData.previous_health,
          components: Object.keys(healthData.components || {}),
        });

        setHealth(healthData.health);
        setPreviousHealth(healthData.previous_health);
        setComponents(healthData.components || {});
        setLastUpdate(timestamp);

        const entry: HealthChangeEntry = {
          ...healthData,
          timestamp,
        };

        setHistory((prev) => {
          const updated = [entry, ...prev];
          return updated.slice(0, maxHistory);
        });

        onHealthChangeRef.current?.(healthData);
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('System health WebSocket error', {
          component: 'useSystemHealthWebSocket',
          message: data.message,
        });
        return;
      }
    },
    [maxHistory]
  );

  // Build WebSocket options
  const wsOptions = buildWebSocketOptions('/ws/system');

  // Connect to WebSocket
  const { isConnected } = useWebSocket(
    enabled
      ? {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: true,
          reconnectInterval: 1000,
          reconnectAttempts: 15,
          connectionTimeout: 10000,
          autoRespondToHeartbeat: true,
        }
      : {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: false,
        }
  );

  // Helper functions
  const getComponentHealth = useCallback(
    (componentName: string): HealthStatus | undefined => {
      return components[componentName];
    },
    [components]
  );

  const isComponentHealthy = useCallback(
    (componentName: string): boolean => {
      return components[componentName] === 'healthy';
    },
    [components]
  );

  const getUnhealthyComponents = useCallback((): string[] => {
    return Object.entries(components)
      .filter(([, status]) => status !== 'healthy')
      .map(([name]) => name);
  }, [components]);

  const clearHistory = useCallback(() => {
    if (!isMountedRef.current) return;
    setHistory([]);
  }, []);

  // Computed values
  const isHealthy = useMemo(() => health === 'healthy', [health]);
  const isDegraded = useMemo(() => health === 'degraded', [health]);
  const isUnhealthy = useMemo(() => health === 'unhealthy', [health]);

  return {
    health,
    previousHealth,
    components,
    history,
    lastUpdate,
    isConnected,
    isHealthy,
    isDegraded,
    isUnhealthy,
    getComponentHealth,
    isComponentHealthy,
    getUnhealthyComponents,
    clearHistory,
  };
}

export default useSystemHealthWebSocket;
