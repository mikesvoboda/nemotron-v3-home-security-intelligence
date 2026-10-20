/**
 * ServiceStatusAlert component displays a dismissible banner for service status notifications.
 *
 * The backend's `service_status` broadcasts reach this component through the
 * `useServiceStatus` hook. Three emitters feed that channel (see the hook for
 * the full measurement): the ServiceHealthMonitor probes `yolo26`, the
 * container orchestrator broadcasts the discovery config keys (postgres,
 * redis, ...), and the worker supervisor broadcasts `worker:<name>` — all
 * flattened by the broadcaster to `{ service, status, message }`.
 *
 * Features:
 * - Hidden when all services are healthy or unreported
 * - Yellow/Warning banner when any service is "restarting"
 * - Red/Error banner when any service is "unhealthy", "restart_failed", or "failed"
 * - Shows worst status when multiple services are unhealthy
 * - Animates in/out smoothly with Tailwind transitions
 */
import { clsx } from 'clsx';
import { AlertTriangle, RefreshCw, X, XCircle } from 'lucide-react';

import type { ServiceName, ServiceStatusType } from '../../hooks/useServiceStatus';

/**
 * Service name type - identifies which service
 * (shared with the hook: yolo26, the container discovery names, worker:<name>)
 */
export type { ServiceName };

/**
 * Service status values matching backend WebSocket events
 * (shared with the hook's type — the broadcaster's WebSocketServiceStatus enum)
 */
export type ServiceStatusValue = ServiceStatusType;

/**
 * Service status data from WebSocket
 */
export interface ServiceStatus {
  service: ServiceName;
  status: ServiceStatusValue;
  message?: string | null;
  timestamp: string;
}

export interface ServiceStatusAlertProps {
  services: Partial<Record<ServiceName, ServiceStatus>>;
  onDismiss?: () => void;
}

/**
 * Severity levels for determining which status takes priority
 */
const STATUS_SEVERITY: Partial<Record<ServiceStatusValue, number>> = {
  healthy: 0,
  restarting: 1,
  running: 0,
  unhealthy: 2,
  restart_failed: 3,
  // Unhealthy with no restart coming — at least as severe as unhealthy.
  restart_disabled: 3,
  stopped: 2,
  // A crashed worker is down — at least as severe as unhealthy.
  crashed: 3,
  failed: 4,
  disabled: 2,
};

/**
 * Configuration for each status type
 */
interface StatusConfig {
  bgColor: string;
  textColor: string;
  icon: typeof AlertTriangle;
  iconClassName: string;
  title: string;
}

// Total over every status getWorstStatus can return (it excludes healthy and
// running before returning), so indexing needs no assertion.
const STATUS_CONFIG: Record<Exclude<ServiceStatusValue, 'healthy' | 'running'>, StatusConfig> = {
  restarting: {
    bgColor: 'bg-yellow-100',
    textColor: 'text-yellow-800',
    icon: RefreshCw,
    iconClassName: 'h-5 w-5 animate-spin',
    title: 'Service Restarting',
  },
  unhealthy: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    icon: AlertTriangle,
    iconClassName: 'h-5 w-5',
    title: 'Service Unhealthy',
  },
  restart_failed: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    icon: XCircle,
    iconClassName: 'h-5 w-5',
    title: 'Restart Failed',
  },
  restart_disabled: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    icon: XCircle,
    iconClassName: 'h-5 w-5',
    title: 'Service Down (Auto-Restart Disabled)',
  },
  stopped: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    icon: XCircle,
    iconClassName: 'h-5 w-5',
    title: 'Service Stopped',
  },
  crashed: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    icon: XCircle,
    iconClassName: 'h-5 w-5',
    title: 'Service Crashed',
  },
  disabled: {
    bgColor: 'bg-yellow-100',
    textColor: 'text-yellow-800',
    icon: XCircle,
    iconClassName: 'h-5 w-5',
    title: 'Service Disabled',
  },
  failed: {
    bgColor: 'bg-red-200',
    textColor: 'text-red-900',
    icon: XCircle,
    iconClassName: 'h-5 w-5',
    title: 'Service Failed',
  },
};

/**
 * Formats service name for display. Known names get readable labels; the
 * container discovery names and `worker:<name>` fall back to the raw name
 * with dashes as spaces.
 */
function formatServiceName(name: ServiceName): string {
  const nameMap: Partial<Record<ServiceName, string>> = {
    redis: 'Redis',
    yolo26: 'YOLO26',
    'ai-gateway': 'AI Gateway',
    postgres: 'PostgreSQL',
    backend: 'Backend API',
    frontend: 'Frontend',
  };
  return nameMap[name] ?? name.replace(/-/g, ' ');
}

/**
 * Gets the worst status from all services (highest severity)
 */
function getWorstStatus(services: Partial<Record<ServiceName, ServiceStatus>>): {
  status: Exclude<ServiceStatusValue, 'healthy' | 'running'>;
  affectedServices: ServiceStatus[];
} | null {
  const affectedServices: ServiceStatus[] = [];
  let worstStatus: Exclude<ServiceStatusValue, 'healthy' | 'running'> | null = null;
  let worstSeverity = 0;

  for (const serviceStatus of Object.values(services)) {
    if (
      !serviceStatus ||
      serviceStatus.status === 'healthy' ||
      serviceStatus.status === 'running'
    ) {
      continue;
    }

    affectedServices.push(serviceStatus);
    const severity = STATUS_SEVERITY[serviceStatus.status] ?? 0;

    if (severity > worstSeverity) {
      worstSeverity = severity;
      worstStatus = serviceStatus.status;
    }
  }

  if (worstStatus === null || affectedServices.length === 0) {
    return null;
  }

  return { status: worstStatus, affectedServices };
}

/**
 * Builds the display message for affected services
 */
function buildMessage(affectedServices: ServiceStatus[]): string {
  if (affectedServices.length === 1) {
    const service = affectedServices[0];
    const serviceName = formatServiceName(service.service);
    return service.message ? `${serviceName}: ${service.message}` : serviceName;
  }

  // Multiple services affected
  const serviceNames = affectedServices.map((s) => formatServiceName(s.service));
  return `Affected: ${serviceNames.join(', ')}`;
}

/**
 * Display a dismissible alert banner showing service health status.
 *
 * @param services - Map of service names to their current status
 * @param onDismiss - Optional callback when the alert is dismissed
 */
export function ServiceStatusAlert({
  services,
  onDismiss,
}: ServiceStatusAlertProps): React.ReactNode {
  const result = getWorstStatus(services);

  // Return null if no alerts to show
  if (!result) {
    return null;
  }

  const { status, affectedServices } = result;
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;
  const message = buildMessage(affectedServices);

  return (
    <div
      role="alert"
      aria-live="polite"
      className={clsx(
        'mb-4 rounded-lg p-4 transition-all duration-300 ease-in-out',
        config.bgColor,
        config.textColor
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className={config.iconClassName} aria-hidden="true" />
          <span className="font-medium">{config.title}</span>
          <span className="text-sm">{message}</span>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className={clsx(
              'rounded-full p-1 transition-colors duration-200',
              'hover:bg-black/10 focus:outline-none focus:ring-2 focus:ring-offset-2',
              status === 'restarting' ? 'focus:ring-yellow-500' : 'focus:ring-red-500'
            )}
            aria-label="Dismiss alert"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}

export default ServiceStatusAlert;
