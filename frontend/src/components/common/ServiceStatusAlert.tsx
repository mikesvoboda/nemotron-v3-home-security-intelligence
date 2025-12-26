import { clsx } from 'clsx';
import { AlertTriangle, RefreshCw, X, XCircle } from 'lucide-react';

/**
 * Service name type - identifies which service
 */
export type ServiceName = 'redis' | 'rtdetr' | 'nemotron';

/**
 * Service status values matching backend WebSocket events
 */
export type ServiceStatusValue = 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed';

/**
 * Service status data from WebSocket
 */
export interface ServiceStatus {
  service: ServiceName;
  status: ServiceStatusValue;
  message?: string;
  timestamp: string;
}

export interface ServiceStatusAlertProps {
  services: Record<ServiceName, ServiceStatus | null>;
  onDismiss?: () => void;
}

/**
 * Severity levels for determining which status takes priority
 */
const STATUS_SEVERITY: Record<ServiceStatusValue, number> = {
  healthy: 0,
  restarting: 1,
  unhealthy: 2,
  restart_failed: 3,
  failed: 4,
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

const STATUS_CONFIG: Record<Exclude<ServiceStatusValue, 'healthy'>, StatusConfig> = {
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
  failed: {
    bgColor: 'bg-red-200',
    textColor: 'text-red-900',
    icon: XCircle,
    iconClassName: 'h-5 w-5',
    title: 'Service Failed',
  },
};

/**
 * Formats service name for display
 */
function formatServiceName(name: ServiceName): string {
  const nameMap: Record<ServiceName, string> = {
    redis: 'Redis',
    rtdetr: 'RT-DETRv2',
    nemotron: 'Nemotron',
  };
  return nameMap[name];
}

/**
 * Gets the worst status from all services (highest severity)
 */
function getWorstStatus(
  services: Record<ServiceName, ServiceStatus | null>
): { status: Exclude<ServiceStatusValue, 'healthy'>; affectedServices: ServiceStatus[] } | null {
  const affectedServices: ServiceStatus[] = [];
  let worstStatus: Exclude<ServiceStatusValue, 'healthy'> | null = null;
  let worstSeverity = 0;

  for (const serviceStatus of Object.values(services)) {
    if (!serviceStatus || serviceStatus.status === 'healthy') {
      continue;
    }

    affectedServices.push(serviceStatus);
    const severity = STATUS_SEVERITY[serviceStatus.status];

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
 * ServiceStatusAlert component displays a dismissible banner for service status notifications.
 *
 * - Hidden when all services are healthy or null
 * - Yellow/Warning banner when any service is "restarting"
 * - Red/Error banner when any service is "unhealthy", "restart_failed", or "failed"
 * - Shows worst status when multiple services are unhealthy
 * - Animates in/out smoothly with Tailwind transitions
 */
export function ServiceStatusAlert({ services, onDismiss }: ServiceStatusAlertProps): JSX.Element | null {
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
        'rounded-lg p-4 mb-4 transition-all duration-300 ease-in-out',
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
              status === 'restarting'
                ? 'focus:ring-yellow-500'
                : 'focus:ring-red-500'
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
