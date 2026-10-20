/**
 * Hook for tracking individual service health status.
 *
 * The backend's `service_status` broadcasts all flow through one validating
 * funnel — `EventBroadcaster.broadcast_service_status` re-serializes every
 * payload against `WebSocketServiceStatusData` (backend/api/schemas/websocket.py),
 * which aliases `name` → `service`, ignores extra fields and validates `status`
 * against the `WebSocketServiceStatus` enum — so what arrives here is always the
 * flat `{ service, status, message }` shape, regardless of the emitting service.
 * Three live emitters feed that funnel (measured for ruling 267):
 *
 * - ServiceHealthMonitor (health_monitor.py): probes `yolo26` only; statuses
 *   healthy/unhealthy/restarting/restart_failed/failed/restart_disabled.
 * - ContainerOrchestrator (container_orchestrator.py): the 19 discovery config
 *   keys (postgres, redis, backend, ...); statuses running/unhealthy/stopped/
 *   disabled survive the funnel (`starting`/`not_found` are rejected by it).
 * - WorkerSupervisor (worker_supervisor.py): `worker:<name>` for the pipeline
 *   workers; statuses running/stopped/crashed/restarting/failed.
 *
 * This hook connects to `/ws/events` and tracks each service's latest status.
 * `rtdetr` and `nemotron` are dropped: no emitter sends those names (R8 renamed
 * the probed AI service to `yolo26` and removed nemotron from the data).
 *
 * For overall system health, use `useSystemStatus` which connects to `/ws/system`
 * and provides an aggregated health field ('healthy', 'degraded', 'unhealthy').
 * This hook is useful when you need to show detailed per-service status or react
 * to specific service failures.
 */
import { useState, useCallback, useMemo, useEffect, useRef } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';

// Container service names come from ContainerDiscoveryService's config keys
// (backend/services/container_discovery.py). Keep in sync with that dict —
// `starting` and `not_found` never reach the client (the broadcaster's status
// enum rejects them), so only the four surviving statuses are listed below.
const CONTAINER_SERVICE_NAMES = [
  'ai-gateway',
  'alertmanager',
  'alloy',
  'backend',
  'blackbox-exporter',
  'cadvisor',
  'dcgm-exporter',
  'frontend',
  'go2rtc',
  'grafana',
  'json-exporter',
  'loki',
  'node-exporter',
  'postgres',
  'prometheus',
  'pyroscope',
  'redis',
  'redis-exporter',
  'tempo',
] as const;

// Worker names are dynamic (worker:detection-{i} etc.), so they are matched by
// prefix rather than enumerated; the template-literal type keeps the static
// names closed while allowing any `worker:<name>`.
const WORKER_SERVICE_PREFIX = 'worker:';

export type ContainerServiceName = (typeof CONTAINER_SERVICE_NAMES)[number];

export type ServiceName = ContainerServiceName | 'yolo26' | `worker:${string}`;

// Must stay in sync with backend WebSocketServiceStatus
// (backend/api/schemas/websocket.py) — that enum is what the broadcaster
// validates every payload's status against before it reaches this hook.
// History: 'restart_disabled' (unhealthy service with restart_cmd=None, e.g.
// AI_RESTART_ENABLED=false) was once missing and the UI silently never saw the
// service go down; the container orchestrator's ServiceInfo statuses outside
// this list die at the broadcaster and never arrive.
export type ServiceStatusType =
  | 'healthy'
  | 'unhealthy'
  | 'running'
  | 'stopped'
  | 'crashed'
  | 'disabled'
  | 'restarting'
  | 'restart_failed'
  | 'restart_disabled'
  | 'failed';

export interface ServiceStatus {
  service: ServiceName;
  status: ServiceStatusType;
  message?: string | null;
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
  services: Partial<Record<ServiceName, ServiceStatus>>;
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
  message?: string | null;
}

interface BackendServiceStatusMessage {
  type: 'service_status';
  data: BackendServiceStatusData;
  timestamp: string;
}

// 'restart_disabled': unhealthy and no automatic restart is coming — strictly
// worse than 'unhealthy', so it counts as unhealthy for derived flags.
const UNHEALTHY_STATUSES: ServiceStatusType[] = [
  'unhealthy',
  'failed',
  'crashed',
  'restart_failed',
  'restart_disabled',
];

function isServiceName(value: unknown): value is ServiceName {
  if (typeof value !== 'string') {
    return false;
  }
  if (value.startsWith(WORKER_SERVICE_PREFIX)) {
    return value.length > WORKER_SERVICE_PREFIX.length;
  }
  return (CONTAINER_SERVICE_NAMES as readonly string[]).includes(value) || value === 'yolo26';
}

function isServiceStatusType(value: unknown): value is ServiceStatusType {
  return (
    typeof value === 'string' &&
    [
      'healthy',
      'unhealthy',
      'running',
      'stopped',
      'crashed',
      'disabled',
      'restarting',
      'restart_failed',
      'restart_disabled',
      'failed',
    ].includes(value)
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

  // The broadcaster's model_dump always includes `message` — as a string or
  // null (pydantic does not omit None fields), never undefined.
  return (
    isServiceName(msgData.service) &&
    isServiceStatusType(msgData.status) &&
    (msgData.message === undefined ||
      msgData.message === null ||
      typeof msgData.message === 'string')
  );
}

// Degraded statuses are those that indicate reduced functionality but not complete failure
const DEGRADED_STATUSES: ServiceStatusType[] = ['restarting'];

/**
 * Subscribe to per-service health status updates from the backend.
 *
 * Returns current status for each monitored service (yolo26, container
 * services, pipeline workers), along with derived flags for checking if any
 * service is unhealthy or restarting.
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
  const [services, setServices] = useState<Partial<Record<ServiceName, ServiceStatus>>>({});

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
        const previousStatus = prev[data.data.service] ?? null;

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
  // SECURITY (ruling 44): browsers open this socket cookie-authenticated; no key
  const wsOptions = buildWebSocketOptions('/ws/events');

  useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
  });

  const hasUnhealthy = useMemo(() => {
    return Object.values(services).some(
      (status) => status !== undefined && UNHEALTHY_STATUSES.includes(status.status)
    );
  }, [services]);

  const hasDegraded = useMemo(() => {
    return Object.values(services).some(
      (status) => status !== undefined && DEGRADED_STATUSES.includes(status.status)
    );
  }, [services]);

  const isAnyRestarting = useMemo(() => {
    return Object.values(services).some(
      (status) => status !== undefined && status.status === 'restarting'
    );
  }, [services]);

  const allHealthy = useMemo(() => {
    // Only reported services participate: null-reporting names are no longer
    // pre-seeded, so "all healthy" means every service that has reported is
    // healthy (the empty map is vacuously all-healthy — matches the old
    // behavior only once a report arrives; useSystemStatus remains the
    // overall-health source for the not-yet-reported case).
    return Object.values(services).every((status) => status?.status === 'healthy');
  }, [services]);

  const getServiceStatus = useCallback(
    (name: ServiceName): ServiceStatus | null => {
      return services[name] ?? null;
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
