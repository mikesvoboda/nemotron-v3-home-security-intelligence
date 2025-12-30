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
import { useState, useCallback, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketUrl } from '../services/api';

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

export interface UseServiceStatusResult {
  services: Record<ServiceName, ServiceStatus | null>;
  hasUnhealthy: boolean;
  isAnyRestarting: boolean;
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

/**
 * Subscribe to per-service health status updates from the backend.
 *
 * Returns current status for each monitored service (rtdetr, nemotron),
 * along with derived flags for checking if any service is unhealthy or restarting.
 *
 * @returns UseServiceStatusResult with services map and utility getters
 */
export function useServiceStatus(): UseServiceStatusResult {
  const [services, setServices] =
    useState<Record<ServiceName, ServiceStatus | null>>(createInitialServices);

  const handleMessage = useCallback((data: unknown) => {
    if (isBackendServiceStatusMessage(data)) {
      // Extract from envelope: data.data contains service/status/message
      const serviceStatus: ServiceStatus = {
        service: data.data.service,
        status: data.data.status,
        message: data.data.message,
        timestamp: data.timestamp,
      };

      setServices((prev) => ({
        ...prev,
        [data.data.service]: serviceStatus,
      }));
    }
  }, []);

  const wsUrl = buildWebSocketUrl('/ws/events');

  useWebSocket({
    url: wsUrl,
    onMessage: handleMessage,
  });

  const hasUnhealthy = useMemo(() => {
    return SERVICE_NAMES.some((name) => {
      const status = services[name];
      return status !== null && UNHEALTHY_STATUSES.includes(status.status);
    });
  }, [services]);

  const isAnyRestarting = useMemo(() => {
    return SERVICE_NAMES.some((name) => {
      const status = services[name];
      return status !== null && status.status === 'restarting';
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
    isAnyRestarting,
    getServiceStatus,
  };
}
