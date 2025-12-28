/**
 * @deprecated This hook is NOT currently wired up on the backend.
 *
 * The backend's ServiceHealthMonitor (health_monitor.py) exists but is not
 * initialized in main.py, so no `service_status` messages are ever broadcast
 * to /ws/system. The SystemBroadcaster only emits `system_status` messages.
 *
 * For system health information, use `useSystemStatus` instead, which correctly
 * handles the `system_status` messages from /ws/system. The system_status
 * payload includes an overall health field ('healthy', 'degraded', 'unhealthy').
 *
 * If per-service status monitoring is needed in the future:
 * 1. Wire ServiceHealthMonitor in backend/main.py
 * 2. Have it broadcast to /ws/system (currently it would broadcast to event channel)
 * 3. Then this hook can be un-deprecated
 *
 * See bead vq8.11 for context on this decision.
 */
import { useState, useCallback, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';

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

// Backend WebSocket message structure
interface BackendServiceStatusMessage {
  type: 'service_status';
  service: ServiceName;
  status: ServiceStatusType;
  message?: string;
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

  return (
    msg.type === 'service_status' &&
    isServiceName(msg.service) &&
    isServiceStatusType(msg.status) &&
    typeof msg.timestamp === 'string' &&
    (msg.message === undefined || typeof msg.message === 'string')
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
 * @deprecated See file-level deprecation notice.
 * Use `useSystemStatus` for system health information instead.
 */
export function useServiceStatus(): UseServiceStatusResult {
  const [services, setServices] =
    useState<Record<ServiceName, ServiceStatus | null>>(createInitialServices);

  const handleMessage = useCallback((data: unknown) => {
    if (isBackendServiceStatusMessage(data)) {
      const serviceStatus: ServiceStatus = {
        service: data.service,
        status: data.status,
        message: data.message,
        timestamp: data.timestamp,
      };

      setServices((prev) => ({
        ...prev,
        [data.service]: serviceStatus,
      }));
    }
  }, []);

  useWebSocket({
    url: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/system`,
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
