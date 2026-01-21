/**
 * useServiceStatusWebSocket - WebSocket hook for container service status changes
 *
 * NEM-3169: Consumes service.status_changed WebSocket events broadcast by the backend
 * when container services (rtdetr, nemotron, etc.) change health state.
 *
 * Events handled:
 * - service.status_changed: Container service status changes (healthy, unhealthy, restarting, etc.)
 *
 * @module hooks/useServiceStatusWebSocket
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import { isHeartbeatMessage, isErrorMessage } from '../types/websocket';

import type { ServiceStatusChangedPayload } from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Service status values
 */
export type ServiceStatus =
  | 'healthy'
  | 'unhealthy'
  | 'restarting'
  | 'restart_failed'
  | 'failed';

/**
 * Extended service status with timestamp
 */
export interface ServiceStatusEntry extends ServiceStatusChangedPayload {
  /** ISO timestamp when this status was received */
  updatedAt: string;
}

/**
 * Map of service names to their status
 */
export type ServiceStatusMap = Record<string, ServiceStatusEntry>;

/**
 * Callback type for service status changes
 */
export type ServiceStatusChangeHandler = (status: ServiceStatusChangedPayload) => void;

/**
 * Options for configuring the useServiceStatusWebSocket hook
 */
export interface UseServiceStatusWebSocketOptions {
  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;

  /**
   * Filter to only track status changes for this service
   * If not provided, all services are tracked
   */
  filterService?: string;

  /**
   * Called when a service status changes
   */
  onStatusChange?: ServiceStatusChangeHandler;
}

/**
 * Return type for the useServiceStatusWebSocket hook
 */
export interface UseServiceStatusWebSocketReturn {
  /** Map of all known service statuses */
  services: ServiceStatusMap;

  /** The most recent status change */
  latestChange: ServiceStatusEntry | null;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** Whether any tracked services are unhealthy */
  hasUnhealthyServices: boolean;

  /** Get status for a specific service */
  getServiceStatus: (serviceName: string) => ServiceStatus | undefined;

  /** Check if a service is healthy */
  isServiceHealthy: (serviceName: string) => boolean;

  /** Get list of unhealthy services */
  getUnhealthyServices: () => ServiceStatusEntry[];

  /** Clear all tracked service statuses */
  clearServices: () => void;
}

// ============================================================================
// Type Guard
// ============================================================================

/**
 * Type guard for service.status_changed messages
 */
function isServiceStatusChangedMessage(
  value: unknown
): value is { type: 'service.status_changed'; data: ServiceStatusChangedPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const msg = value as Record<string, unknown>;
  if (msg.type !== 'service.status_changed') {
    return false;
  }

  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const data = msg.data as Record<string, unknown>;
  return typeof data.service === 'string' && typeof data.status === 'string';
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to real-time service status WebSocket events.
 *
 * Tracks container service health changes (rtdetr, nemotron, etc.) and provides
 * utilities for checking service health status.
 *
 * @param options - Configuration options
 * @returns Service status state and utilities
 *
 * @example
 * ```tsx
 * const {
 *   services,
 *   hasUnhealthyServices,
 *   isServiceHealthy,
 *   getUnhealthyServices,
 * } = useServiceStatusWebSocket({
 *   onStatusChange: (change) => {
 *     if (change.status === 'unhealthy') {
 *       showAlert(`Service ${change.service} is unhealthy: ${change.message}`);
 *     }
 *   },
 * });
 *
 * // Check specific service health
 * if (!isServiceHealthy('rtdetr')) {
 *   console.log('RT-DETR service is down!');
 * }
 * ```
 */
export function useServiceStatusWebSocket(
  options: UseServiceStatusWebSocketOptions = {}
): UseServiceStatusWebSocketReturn {
  const { enabled = true, filterService, onStatusChange } = options;

  // State
  const [services, setServices] = useState<ServiceStatusMap>({});
  const [latestChange, setLatestChange] = useState<ServiceStatusEntry | null>(null);

  // Track mounted state
  const isMountedRef = useRef(true);

  // Store callback in ref
  const onStatusChangeRef = useRef(onStatusChange);

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
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

      // Handle service.status_changed messages
      if (isServiceStatusChangedMessage(data)) {
        const statusData = data.data;

        // Filter by service if specified
        if (filterService && statusData.service !== filterService) {
          return;
        }

        logger.debug('Service.status_changed event received', {
          component: 'useServiceStatusWebSocket',
          service: statusData.service,
          status: statusData.status,
          previous_status: statusData.previous_status,
          message: statusData.message,
        });

        const entry: ServiceStatusEntry = {
          ...statusData,
          updatedAt: new Date().toISOString(),
        };

        setServices((prev) => ({
          ...prev,
          [statusData.service]: entry,
        }));
        setLatestChange(entry);

        onStatusChangeRef.current?.(statusData);
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('Service status WebSocket error', {
          component: 'useServiceStatusWebSocket',
          message: data.message,
        });
        return;
      }
    },
    [filterService]
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
  const getServiceStatus = useCallback(
    (serviceName: string): ServiceStatus | undefined => {
      return services[serviceName]?.status as ServiceStatus | undefined;
    },
    [services]
  );

  const isServiceHealthy = useCallback(
    (serviceName: string): boolean => {
      const status = services[serviceName]?.status;
      return status === 'healthy';
    },
    [services]
  );

  const getUnhealthyServices = useCallback((): ServiceStatusEntry[] => {
    return Object.values(services).filter((s) => s.status !== 'healthy');
  }, [services]);

  const clearServices = useCallback(() => {
    if (!isMountedRef.current) return;
    setServices({});
    setLatestChange(null);
  }, []);

  // Compute derived state
  const hasUnhealthyServices = useMemo(() => {
    return Object.values(services).some((s) => s.status !== 'healthy');
  }, [services]);

  return {
    services,
    latestChange,
    isConnected,
    hasUnhealthyServices,
    getServiceStatus,
    isServiceHealthy,
    getUnhealthyServices,
    clearServices,
  };
}

export default useServiceStatusWebSocket;
