/**
 * Hook for tracking individual service health status.
 *
 * The backend's ServiceHealthMonitor (health_monitor.py) monitors RT-DETRv2 and
 * Nemotron services, broadcasting `service_status` messages via EventBroadcaster
 * when their health changes. This hook connects to `/ws/events` and listens for
 * those messages, tracking the status of each monitored service.
 *
 * For overall system health, use `useSystemStatus` which connects to `/ws/system`
 * and provides an aggregated health field ('healthy', 'degraded', 'unhealthy').
 * This hook is useful when you need to show detailed per-service status or react
 * to specific service failures.
 *
 * Note: Redis health is not monitored by ServiceHealthMonitor since the backend
 * handles Redis failures gracefully through other mechanisms.
 */
import { useState, useCallback, useMemo, useEffect, useRef } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';

export type ServiceName = 'redis' | 'rtdetr' | 'nemotron';
export type ServiceStatusType =
  | 'healthy'
  | 'unhealthy'
  | 'restarting'
  | 'restart_failed'
  | 'failed';

export interface ServiceStatus {
  service: ServiceName;
  status: ServiceStatusType;
  message?: string;
  timestamp: string;
}

/**
 * Callback signature for service status changes.
 * Called whenever a service's status changes.
 */
export type ServiceStatusChangeCallback = (
  service: ServiceName,
  newStatus: ServiceStatus,
  previousStatus: ServiceStatus | null
) => void;

/**
 * Options for the useServiceStatus hook.
 */
export interface UseServiceStatusOptions {
  /** Callback fired when any service's status changes */
  onStatusChange?: ServiceStatusChangeCallback;
}

export interface UseServiceStatusResult {
  services: Record<ServiceName, ServiceStatus | null>;
  hasUnhealthy: boolean;
  hasDegraded: boolean;
  isAnyRestarting: boolean;
  allHealthy: boolean;
  getServiceStatus: (name: ServiceName) => ServiceStatus | null;
}

// Backend WebSocket message envelope structure (matches WebSocketServiceStatusMessage schema)
// Format: { "type": "service_status", "data": {...}, "timestamp": "..." }
interface BackendServiceStatusData {
  service: ServiceName;
  status: ServiceStatusType;
  message?: string;
}

interface BackendServiceStatusMessage {
  type: 'service_status';
  data: BackendServiceStatusData;
  timestamp: string;
}

const SERVICE_NAMES: ServiceName[] = ['redis', 'rtdetr', 'nemotron'];

const UNHEALTHY_STATUSES: ServiceStatusType[] = ['unhealthy', 'failed', 'restart_failed'];

function isServiceName(value: unknown): value is ServiceName {
  return typeof value === 'string' && SERVICE_NAMES.includes(value as ServiceName);
}

function isServiceStatusType(value: unknown): value is ServiceStatusType {
  return (
    typeof value === 'string' &&
    ['healthy', 'unhealthy', 'restarting', 'restart_failed', 'failed'].includes(value)
  );
}

function isBackendServiceStatusMessage(data: unknown): data is BackendServiceStatusMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  // Check envelope structure: { type: "service_status", data: {...}, timestamp: "..." }
  if (msg.type !== 'service_status' || typeof msg.timestamp !== 'string') {
    return false;
  }

  // Check nested data object
  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const msgData = msg.data as Record<string, unknown>;

  return (
    isServiceName(msgData.service) &&
    isServiceStatusType(msgData.status) &&
    (msgData.message === undefined || typeof msgData.message === 'string')
  );
}

function createInitialServices(): Record<ServiceName, ServiceStatus | null> {
  return {
    redis: null,
    rtdetr: null,
    nemotron: null,
  };
}

// Degraded statuses are those that indicate reduced functionality but not complete failure
const DEGRADED_STATUSES: ServiceStatusType[] = ['restarting'];

/**
 * Subscribe to per-service health status updates from the backend.
 *
 * Returns current status for each monitored service (rtdetr, nemotron),
 * along with derived flags for checking if any service is unhealthy or restarting.
 *
 * @param options - Optional configuration including status change callback
 * @returns UseServiceStatusResult with services map and utility getters
 *
 * @example
 * ```tsx
 * const { services, hasUnhealthy, allHealthy } = useServiceStatus({
 *   onStatusChange: (service, newStatus, prevStatus) => {
 *     if (newStatus.status === 'unhealthy') {
 *       console.warn(`Service ${service} became unhealthy`);
 *     }
 *   },
 * });
 * ```
 */
export function useServiceStatus(options: UseServiceStatusOptions = {}): UseServiceStatusResult {
  const { onStatusChange } = options;
  const [services, setServices] =
    useState<Record<ServiceName, ServiceStatus | null>>(createInitialServices);

  // Use ref to store callback to avoid dependency in handleMessage
  const onStatusChangeRef = useRef(onStatusChange);
  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
  }, [onStatusChange]);

  // Track pending status change notifications
  const pendingNotificationRef = useRef<{
    service: ServiceName;
    newStatus: ServiceStatus;
    previousStatus: ServiceStatus | null;
  } | null>(null);

  const handleMessage = useCallback((data: unknown) => {
    if (isBackendServiceStatusMessage(data)) {
      // Extract from envelope: data.data contains service/status/message
      const serviceStatus: ServiceStatus = {
        service: data.data.service,
        status: data.data.status,
        message: data.data.message,
        timestamp: data.timestamp,
      };

      setServices((prev) => {
        const previousStatus = prev[data.data.service];

        // Store pending notification for effect to process
        pendingNotificationRef.current = {
          service: data.data.service,
          newStatus: serviceStatus,
          previousStatus,
        };

        return {
          ...prev,
          [data.data.service]: serviceStatus,
        };
      });
    }
  }, []);

  // Effect to fire callback after state update
  useEffect(() => {
    const pending = pendingNotificationRef.current;
    if (pending && onStatusChangeRef.current) {
      onStatusChangeRef.current(pending.service, pending.newStatus, pending.previousStatus);
      pendingNotificationRef.current = null;
    }
  }, [services]);

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  // SECURITY: API key is passed via Sec-WebSocket-Protocol header, not URL query param
  const wsOptions = buildWebSocketOptions('/ws/events');

  useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
  });

  const hasUnhealthy = useMemo(() => {
    return SERVICE_NAMES.some((name) => {
      const status = services[name];
      return status !== null && UNHEALTHY_STATUSES.includes(status.status);
    });
  }, [services]);

  const hasDegraded = useMemo(() => {
    return SERVICE_NAMES.some((name) => {
      const status = services[name];
      return status !== null && DEGRADED_STATUSES.includes(status.status);
    });
  }, [services]);

  const isAnyRestarting = useMemo(() => {
    return SERVICE_NAMES.some((name) => {
      const status = services[name];
      return status !== null && status.status === 'restarting';
    });
  }, [services]);

  const allHealthy = useMemo(() => {
    // All services must have reported status AND be healthy
    return SERVICE_NAMES.every((name) => {
      const status = services[name];
      return status !== null && status.status === 'healthy';
    });
  }, [services]);

  const getServiceStatus = useCallback(
    (name: ServiceName): ServiceStatus | null => {
      return services[name];
    },
    [services]
  );

  return {
    services,
    hasUnhealthy,
    hasDegraded,
    isAnyRestarting,
    allHealthy,
    getServiceStatus,
  };
}
