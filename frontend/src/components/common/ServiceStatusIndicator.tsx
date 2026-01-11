/**
 * ServiceStatusIndicator - Displays overall service health with expandable details.
 *
 * Shows a compact status indicator that can be expanded to show individual service status.
 * Uses the useServiceStatus hook to track real-time service health updates.
 *
 * Features:
 * - Compact status indicator showing overall health (online/degraded/offline)
 * - Expandable dropdown showing individual service status
 * - Color-coded indicators for quick health assessment
 * - Accessibility support with screen reader announcements
 */
import { clsx } from 'clsx';
import { AlertTriangle, CheckCircle, Server, XCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import type { ServiceName, ServiceStatus as ServiceStatusType } from '../../hooks/useServiceStatus';

/**
 * Overall service status derived from individual services.
 */
export type OverallStatus = 'online' | 'degraded' | 'offline';

export interface ServiceStatusIndicatorProps {
  /** Map of services to their current status */
  services: Record<ServiceName, ServiceStatusType | null>;
  /** Whether any service is unhealthy */
  hasUnhealthy: boolean;
  /** Whether any service is restarting */
  isAnyRestarting: boolean;
  /** Optional class name for styling */
  className?: string;
}

/**
 * Derive overall status from individual service statuses.
 */
function deriveOverallStatus(
  services: Record<ServiceName, ServiceStatusType | null>,
  hasUnhealthy: boolean,
  isAnyRestarting: boolean
): OverallStatus {
  // Check if all services are null (initial state)
  const allNull = Object.values(services).every((s) => s === null);
  if (allNull) {
    return 'online'; // Assume online until we get data
  }

  // Any unhealthy/failed service means degraded or offline
  if (hasUnhealthy) {
    // Check if ALL known services are unhealthy
    const knownServices = Object.values(services).filter((s) => s !== null);
    const allUnhealthy = knownServices.every(
      (s) =>
        s?.status === 'unhealthy' ||
        s?.status === 'failed' ||
        s?.status === 'restart_failed'
    );
    return allUnhealthy ? 'offline' : 'degraded';
  }

  // Any restarting service means degraded
  if (isAnyRestarting) {
    return 'degraded';
  }

  return 'online';
}

/**
 * Get display configuration for a status value.
 */
function getStatusConfig(status: OverallStatus): {
  label: string;
  dotColor: string;
  textColor: string;
  icon: typeof CheckCircle;
} {
  switch (status) {
    case 'online':
      return {
        label: 'Online',
        dotColor: 'bg-green-500',
        textColor: 'text-green-400',
        icon: CheckCircle,
      };
    case 'degraded':
      return {
        label: 'Degraded',
        dotColor: 'bg-yellow-500',
        textColor: 'text-yellow-400',
        icon: AlertTriangle,
      };
    case 'offline':
      return {
        label: 'Offline',
        dotColor: 'bg-red-500',
        textColor: 'text-red-400',
        icon: XCircle,
      };
  }
}

/**
 * Get display configuration for individual service status.
 */
function getServiceStatusConfig(status: string): {
  dotColor: string;
  textColor: string;
  icon: typeof CheckCircle;
} {
  switch (status) {
    case 'healthy':
      return {
        dotColor: 'bg-green-500',
        textColor: 'text-green-400',
        icon: CheckCircle,
      };
    case 'restarting':
      return {
        dotColor: 'bg-yellow-500',
        textColor: 'text-yellow-400',
        icon: AlertTriangle,
      };
    case 'unhealthy':
    case 'restart_failed':
    case 'failed':
      return {
        dotColor: 'bg-red-500',
        textColor: 'text-red-400',
        icon: XCircle,
      };
    default:
      return {
        dotColor: 'bg-gray-500',
        textColor: 'text-gray-400',
        icon: Server,
      };
  }
}

/**
 * Format service name for display.
 */
function formatServiceName(name: ServiceName): string {
  const nameMap: Record<ServiceName, string> = {
    redis: 'Redis',
    rtdetr: 'RT-DETRv2',
    nemotron: 'Nemotron',
  };
  return nameMap[name];
}

interface ServiceDetailRowProps {
  name: ServiceName;
  status: ServiceStatusType | null;
}

function ServiceDetailRow({ name, status }: ServiceDetailRowProps) {
  const config = status
    ? getServiceStatusConfig(status.status)
    : { dotColor: 'bg-gray-600', textColor: 'text-gray-500', icon: Server };
  const Icon = config.icon;

  return (
    <div
      className="flex items-center justify-between py-1.5"
      data-testid={`service-row-${name}`}
    >
      <span className="text-sm text-gray-300">{formatServiceName(name)}</span>
      <div className="flex items-center gap-2">
        <Icon className={clsx('h-3 w-3', config.textColor)} aria-hidden="true" />
        <div
          className={clsx('h-2 w-2 rounded-full', config.dotColor)}
          data-testid={`service-indicator-${name}`}
          aria-hidden="true"
        />
        <span className={clsx('text-xs font-medium', config.textColor)}>
          {status?.status ?? 'Unknown'}
        </span>
      </div>
    </div>
  );
}

/**
 * ServiceStatusIndicator displays overall service health with expandable details.
 */
export default function ServiceStatusIndicator({
  services,
  hasUnhealthy,
  isAnyRestarting,
  className,
}: ServiceStatusIndicatorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const dropdownTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const overallStatus = deriveOverallStatus(services, hasUnhealthy, isAnyRestarting);
  const config = getStatusConfig(overallStatus);
  const Icon = config.icon;

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (dropdownTimeoutRef.current) {
        clearTimeout(dropdownTimeoutRef.current);
      }
    };
  }, []);

  const handleMouseEnter = () => {
    if (dropdownTimeoutRef.current) {
      clearTimeout(dropdownTimeoutRef.current);
    }
    setIsExpanded(true);
  };

  const handleMouseLeave = () => {
    dropdownTimeoutRef.current = setTimeout(() => {
      setIsExpanded(false);
    }, 150);
  };

  // Get services that have status data
  const serviceEntries = Object.entries(services) as [ServiceName, ServiceStatusType | null][];

  return (
    <div
      ref={containerRef}
      className={clsx('relative flex cursor-pointer items-center gap-2', className)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
      data-testid="service-status-indicator"
      role="button"
      tabIndex={0}
      aria-label={`Service status: ${config.label}`}
      aria-haspopup="true"
      aria-expanded={isExpanded}
    >
      {/* Status Icon */}
      <Icon className={clsx('h-4 w-4', config.textColor)} aria-hidden="true" />

      {/* Status Dot */}
      <div
        className={clsx(
          'h-2 w-2 rounded-full',
          config.dotColor,
          overallStatus === 'online' && 'animate-pulse'
        )}
        data-testid="service-status-dot"
        aria-hidden="true"
      />

      {/* Status Label - hidden on small screens */}
      <span className="hidden text-sm text-text-secondary sm:inline">
        Services: <span className={config.textColor}>{config.label}</span>
      </span>

      {/* Dropdown */}
      {isExpanded && (
        <div
          className="absolute left-0 top-full z-50 mt-2 min-w-[200px] rounded-lg border border-gray-700 bg-gray-900 p-3 shadow-lg"
          role="tooltip"
          data-testid="service-status-dropdown"
        >
          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
            AI Services
          </div>
          <div className="divide-y divide-gray-800">
            {serviceEntries.map(([name, status]) => (
              <ServiceDetailRow key={name} name={name} status={status} />
            ))}
          </div>
          {hasUnhealthy && (
            <div className="mt-2 border-t border-gray-800 pt-2">
              <div className="flex items-center gap-1 text-xs text-red-400">
                <AlertTriangle className="h-3 w-3" />
                Some services are unhealthy
              </div>
            </div>
          )}
          {isAnyRestarting && !hasUnhealthy && (
            <div className="mt-2 border-t border-gray-800 pt-2">
              <div className="flex items-center gap-1 text-xs text-yellow-400">
                <AlertTriangle className="h-3 w-3" />
                Services restarting
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
