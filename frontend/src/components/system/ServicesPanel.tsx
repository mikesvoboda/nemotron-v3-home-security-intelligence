import { Card, Title, Text, Badge, Button } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Server,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  ToggleLeft,
  ToggleRight,
  Database,
  Brain,
  Activity,
  Loader2,
  Ban,
} from 'lucide-react';
import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { toast } from 'sonner';

import { useServiceMutations } from '../../hooks/useServiceMutations';
import { useServiceStatus, type ServiceName } from '../../hooks/useServiceStatus';
import {
  fetchHealth,
  type HealthResponse,
  type ServiceStatus,
} from '../../services/api';

/**
 * Services that should NOT allow restart (dangerous operations)
 */
const RESTART_DISABLED_SERVICES = new Set(['postgres']);

/**
 * Service category types
 */
export type ServiceCategory = 'infrastructure' | 'ai' | 'monitoring';

/**
 * Extended service information with category and port
 */
export interface ServiceInfo {
  name: string;
  displayName: string;
  category: ServiceCategory;
  port?: number;
  description: string;
}

/**
 * Service status with extended info
 */
export interface ServiceWithStatus extends ServiceInfo {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown';
  message?: string;
  enabled: boolean;
  isRestarting: boolean;
}

/**
 * Category summary showing health counts
 */
export interface CategorySummary {
  category: ServiceCategory;
  healthy: number;
  unhealthy: number;
  degraded: number;
  total: number;
}

/**
 * Props for ServicesPanel component
 */
export interface ServicesPanelProps {
  /** Polling interval in milliseconds for fallback (default: 30000) */
  pollingInterval?: number;
  /** Callback when a service is restarted */
  onRestart?: (serviceName: string) => void;
  /** Callback when a service is enabled/disabled */
  onToggle?: (serviceName: string, enabled: boolean) => void;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * Static service configuration - defines all known services
 */
const SERVICE_DEFINITIONS: ServiceInfo[] = [
  // Infrastructure services
  {
    name: 'postgres',
    displayName: 'PostgreSQL',
    category: 'infrastructure',
    port: 5432,
    description: 'Primary database for events, detections, and system data',
  },
  {
    name: 'redis',
    displayName: 'Redis',
    category: 'infrastructure',
    port: 6379,
    description: 'Cache and message queue for pipeline coordination',
  },
  // AI services
  {
    name: 'rtdetr',
    displayName: 'RT-DETRv2',
    category: 'ai',
    port: 8001,
    description: 'Real-time object detection model',
  },
  {
    name: 'nemotron',
    displayName: 'Nemotron',
    category: 'ai',
    port: 8002,
    description: 'Risk analysis LLM for security reasoning',
  },
  // Monitoring services
  {
    name: 'file_watcher',
    displayName: 'File Watcher',
    category: 'monitoring',
    description: 'Monitors camera FTP directories for new images',
  },
  {
    name: 'batch_aggregator',
    displayName: 'Batch Aggregator',
    category: 'monitoring',
    description: 'Aggregates detections into analysis batches',
  },
  {
    name: 'cleanup_service',
    displayName: 'Cleanup Service',
    category: 'monitoring',
    description: 'Removes old data based on retention policy',
  },
];

/**
 * Category display configuration
 */
const CATEGORY_CONFIG: Record<ServiceCategory, { label: string; icon: typeof Server }> = {
  infrastructure: { label: 'Infrastructure', icon: Database },
  ai: { label: 'AI Services', icon: Brain },
  monitoring: { label: 'Monitoring', icon: Activity },
};

/**
 * Map status string to normalized status type
 */
function normalizeStatus(
  status: string | undefined
): 'healthy' | 'unhealthy' | 'degraded' | 'unknown' {
  if (!status) return 'unknown';
  const normalized = status.toLowerCase();
  if (normalized === 'healthy') return 'healthy';
  if (normalized === 'unhealthy' || normalized === 'failed' || normalized === 'restart_failed')
    return 'unhealthy';
  if (normalized === 'degraded' || normalized === 'restarting') return 'degraded';
  return 'unknown';
}

/**
 * Get badge color for status
 */
function getStatusColor(
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown'
): 'emerald' | 'red' | 'yellow' | 'gray' {
  switch (status) {
    case 'healthy':
      return 'emerald'; // Changed from 'green' for WCAG 4.5:1 contrast
    case 'unhealthy':
      return 'red';
    case 'degraded':
      return 'yellow';
    default:
      return 'gray';
  }
}

/**
 * Get status icon component
 */
function StatusIcon({ status }: { status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown' }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-4 w-4 text-green-500" data-testid="status-icon-healthy" />;
    case 'unhealthy':
      return <XCircle className="h-4 w-4 text-red-500" data-testid="status-icon-unhealthy" />;
    case 'degraded':
      return (
        <AlertTriangle className="h-4 w-4 text-yellow-500" data-testid="status-icon-degraded" />
      );
    default:
      return <AlertTriangle className="h-4 w-4 text-gray-500" data-testid="status-icon-unknown" />;
  }
}

/**
 * ServiceCard - Individual service status card
 */
interface ServiceCardProps {
  service: ServiceWithStatus;
  onRestart?: () => void;
  onToggle?: (enabled: boolean) => void;
}

function ServiceCard({ service, onRestart, onToggle }: ServiceCardProps) {
  // Check if restart/stop is disabled for this service (e.g., postgres)
  const isRestartDisabled = RESTART_DISABLED_SERVICES.has(service.name);
  const restartButtonDisabled = service.isRestarting || !service.enabled || isRestartDisabled;
  const toggleDisabled = isRestartDisabled && service.enabled;

  return (
    <div
      className={clsx(
        'rounded-lg border p-3 transition-colors',
        service.status === 'healthy' && 'border-gray-700 bg-gray-800/50',
        service.status === 'unhealthy' && 'border-red-500/30 bg-red-500/10',
        service.status === 'degraded' && 'border-yellow-500/30 bg-yellow-500/10',
        service.status === 'unknown' && 'border-gray-600 bg-gray-800/30'
      )}
      data-testid={`service-card-${service.name}`}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Left side: Status and info */}
        <div className="flex items-start gap-2">
          <StatusIcon status={service.status} />
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <Text className="text-sm font-medium text-gray-200">{service.displayName}</Text>
              {service.port && <Text className="text-xs text-gray-500">:{service.port}</Text>}
            </div>
            <Text className="text-xs text-gray-500">{service.description}</Text>
            {service.message && (
              <Text className="mt-1 text-xs text-gray-400">{service.message}</Text>
            )}
          </div>
        </div>

        {/* Right side: Status badge and actions */}
        <div className="flex flex-col items-end gap-2">
          <Badge
            color={getStatusColor(service.status)}
            size="xs"
            data-testid={`service-status-badge-${service.name}`}
          >
            {service.isRestarting
              ? 'Restarting'
              : service.status.charAt(0).toUpperCase() + service.status.slice(1)}
          </Badge>

          {/* Action buttons */}
          <div className="flex items-center gap-1">
            {/* Restart button */}
            <Button
              size="xs"
              variant="secondary"
              icon={service.isRestarting ? Loader2 : isRestartDisabled ? Ban : RefreshCw}
              onClick={onRestart}
              disabled={restartButtonDisabled}
              className={clsx(
                'h-6 px-2 text-xs',
                service.isRestarting && '[&>svg]:animate-spin',
                isRestartDisabled && 'cursor-not-allowed opacity-50'
              )}
              data-testid={`service-restart-btn-${service.name}`}
              title={isRestartDisabled ? 'Restart disabled (dangerous)' : 'Restart service'}
            >
              Restart
            </Button>

            {/* Enable/Disable toggle */}
            <button
              type="button"
              onClick={() => !toggleDisabled && onToggle?.(!service.enabled)}
              disabled={toggleDisabled}
              className={clsx(
                'flex items-center rounded p-1 transition-colors',
                toggleDisabled && 'cursor-not-allowed opacity-50',
                !toggleDisabled && service.enabled && 'text-[#76B900] hover:bg-[#76B900]/10',
                !toggleDisabled && !service.enabled && 'text-gray-500 hover:bg-gray-700'
              )}
              data-testid={`service-toggle-btn-${service.name}`}
              title={
                toggleDisabled
                  ? 'Stopping disabled (dangerous)'
                  : service.enabled
                    ? 'Disable service'
                    : 'Enable service'
              }
              aria-pressed={service.enabled}
            >
              {service.enabled ? (
                <ToggleRight className="h-5 w-5" />
              ) : (
                <ToggleLeft className="h-5 w-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * CategorySummaryBar - Shows health counts per category
 */
interface CategorySummaryBarProps {
  summaries: CategorySummary[];
}

function CategorySummaryBar({ summaries }: CategorySummaryBarProps) {
  return (
    <div className="mb-4 flex flex-wrap gap-2" data-testid="category-summary-bar">
      {summaries.map((summary) => {
        const CategoryIcon = CATEGORY_CONFIG[summary.category].icon;
        const isAllHealthy = summary.healthy === summary.total;

        return (
          <div
            key={summary.category}
            className={clsx(
              'flex items-center gap-2 rounded-lg px-3 py-1.5',
              isAllHealthy ? 'bg-gray-800/50' : 'bg-yellow-500/10'
            )}
            data-testid={`category-summary-${summary.category}`}
          >
            <CategoryIcon className="h-4 w-4 text-gray-400" />
            <Text className="text-sm text-gray-300">{CATEGORY_CONFIG[summary.category].label}</Text>
            <Badge
              color={isAllHealthy ? 'emerald' : summary.unhealthy > 0 ? 'red' : 'yellow'}
              size="xs"
              data-testid={`category-badge-${summary.category}`}
            >
              {summary.healthy}/{summary.total}
            </Badge>
          </div>
        );
      })}
    </div>
  );
}

/**
 * ServicesPanel - Displays services grouped by category with status and controls
 *
 * Shows:
 * - Services grouped by category (Infrastructure, AI, Monitoring)
 * - Individual service cards with status indicators
 * - Restart button for each service
 * - Enable/Disable toggles
 * - Category summary bar showing health counts
 * - WebSocket real-time updates with 30-second polling fallback
 */
export default function ServicesPanel({
  pollingInterval = 30000,
  onRestart,
  onToggle,
  className,
  'data-testid': testId = 'services-panel',
}: ServicesPanelProps) {
  // Service status from WebSocket (for rtdetr, nemotron, redis)
  const { services: wsServices, hasUnhealthy } = useServiceStatus();

  // Service mutations for restart/stop/start/enable operations
  const { restartService, stopService, enableService } = useServiceMutations();

  // Health status from REST API (includes all services)
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [restartingServices, setRestartingServices] = useState<Set<string>>(new Set());
  const [enabledServices, setEnabledServices] = useState<Set<string>>(
    new Set(SERVICE_DEFINITIONS.map((s) => s.name))
  );

  // Track if component is mounted
  const isMountedRef = useRef(true);

  // Fetch health data from REST API
  const fetchHealthData = useCallback(async () => {
    if (!isMountedRef.current) return;

    try {
      const response = await fetchHealth();
      if (isMountedRef.current) {
        setHealthData(response);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      if (isMountedRef.current) {
        console.error('Failed to fetch health data:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch health data');
        setLoading(false);
      }
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    isMountedRef.current = true;
    void fetchHealthData();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchHealthData]);

  // Polling fallback
  useEffect(() => {
    if (pollingInterval <= 0) return;

    const intervalId = setInterval(() => {
      void fetchHealthData();
    }, pollingInterval);

    return () => clearInterval(intervalId);
  }, [pollingInterval, fetchHealthData]);

  // Combine WebSocket and REST data into service list
  const servicesWithStatus: ServiceWithStatus[] = useMemo(() => {
    return SERVICE_DEFINITIONS.map((def) => {
      // Check WebSocket data first (more real-time for rtdetr, nemotron, redis)
      const wsStatus = wsServices[def.name as ServiceName];

      // Then check REST API health data
      const healthStatus: ServiceStatus | undefined = healthData?.services?.[def.name];

      // Determine status (prefer WebSocket for supported services)
      let status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown' = 'unknown';
      let message: string | undefined;

      if (wsStatus) {
        status = normalizeStatus(wsStatus.status);
        message = wsStatus.message;
      } else if (healthStatus) {
        status = normalizeStatus(healthStatus.status);
        message = healthStatus.message ?? undefined;
      }

      // Check if service is currently restarting (from WebSocket or local state)
      const isRestarting = wsStatus?.status === 'restarting' || restartingServices.has(def.name);

      return {
        ...def,
        status: isRestarting ? 'degraded' : status,
        message,
        enabled: enabledServices.has(def.name),
        isRestarting,
      };
    });
  }, [wsServices, healthData, restartingServices, enabledServices]);

  // Calculate category summaries
  const categorySummaries: CategorySummary[] = useMemo(() => {
    const categories: ServiceCategory[] = ['infrastructure', 'ai', 'monitoring'];

    return categories.map((category) => {
      const categoryServices = servicesWithStatus.filter((s) => s.category === category);
      return {
        category,
        healthy: categoryServices.filter((s) => s.status === 'healthy').length,
        unhealthy: categoryServices.filter((s) => s.status === 'unhealthy').length,
        degraded: categoryServices.filter((s) => s.status === 'degraded').length,
        total: categoryServices.length,
      };
    });
  }, [servicesWithStatus]);

  // Group services by category
  const servicesByCategory = useMemo(() => {
    const groups: Record<ServiceCategory, ServiceWithStatus[]> = {
      infrastructure: [],
      ai: [],
      monitoring: [],
    };

    servicesWithStatus.forEach((service) => {
      groups[service.category].push(service);
    });

    return groups;
  }, [servicesWithStatus]);

  // Handle service restart
  const handleRestart = useCallback(
    (serviceName: string) => {
      // Check if restart is disabled for this service
      if (RESTART_DISABLED_SERVICES.has(serviceName)) {
        toast.error(`Restart is disabled for ${serviceName} (dangerous operation)`);
        return;
      }

      // Confirm before restarting
      const confirmed = window.confirm(
        `Are you sure you want to restart ${serviceName}? This will temporarily interrupt the service.`
      );

      if (!confirmed) {
        return;
      }

      setRestartingServices((prev) => new Set(prev).add(serviceName));

      restartService.mutate(serviceName, {
        onSuccess: (response) => {
          toast.success(response.message || `Service '${serviceName}' restart initiated`);
          onRestart?.(serviceName);

          // Wait for restart to complete and then refresh health data
          setTimeout(() => {
            void fetchHealthData();
          }, 3000);
        },
        onError: (err) => {
          console.error(`Failed to restart service ${serviceName}:`, err);
          toast.error(
            `Failed to restart ${serviceName}: ${err instanceof Error ? err.message : 'Unknown error'}`
          );
        },
        onSettled: () => {
          if (isMountedRef.current) {
            setRestartingServices((prev) => {
              const next = new Set(prev);
              next.delete(serviceName);
              return next;
            });
          }
        },
      });
    },
    [onRestart, fetchHealthData, restartService]
  );

  // Handle service enable/disable toggle
  const handleToggle = useCallback(
    (serviceName: string, enabled: boolean) => {
      // Check if this is a dangerous service to toggle
      if (RESTART_DISABLED_SERVICES.has(serviceName) && !enabled) {
        toast.error(`Stopping ${serviceName} is disabled (dangerous operation)`);
        return;
      }

      // Confirm before disabling
      if (!enabled) {
        const confirmed = window.confirm(
          `Are you sure you want to disable ${serviceName}? This will stop the service and prevent auto-restart.`
        );
        if (!confirmed) {
          return;
        }
      }

      // Optimistically update UI
      setEnabledServices((prev) => {
        const next = new Set(prev);
        if (enabled) {
          next.add(serviceName);
        } else {
          next.delete(serviceName);
        }
        return next;
      });

      // Call the appropriate mutation
      if (enabled) {
        enableService.mutate(serviceName, {
          onSuccess: (response) => {
            toast.success(response.message || `Service '${serviceName}' enabled`);
            onToggle?.(serviceName, true);
            void fetchHealthData();
          },
          onError: (err) => {
            console.error(`Failed to enable service ${serviceName}:`, err);
            toast.error(
              `Failed to enable ${serviceName}: ${err instanceof Error ? err.message : 'Unknown error'}`
            );
            // Revert optimistic update
            setEnabledServices((prev) => {
              const next = new Set(prev);
              next.delete(serviceName);
              return next;
            });
          },
        });
      } else {
        stopService.mutate(serviceName, {
          onSuccess: (response) => {
            toast.success(response.message || `Service '${serviceName}' disabled`);
            onToggle?.(serviceName, false);
            void fetchHealthData();
          },
          onError: (err) => {
            console.error(`Failed to disable service ${serviceName}:`, err);
            toast.error(
              `Failed to disable ${serviceName}: ${err instanceof Error ? err.message : 'Unknown error'}`
            );
            // Revert optimistic update
            setEnabledServices((prev) => {
              const next = new Set(prev);
              next.add(serviceName);
              return next;
            });
          },
        });
      }
    },
    [onToggle, enableService, stopService, fetchHealthData]
  );

  // Calculate overall status
  const totalHealthy = servicesWithStatus.filter((s) => s.status === 'healthy').length;
  const totalServices = servicesWithStatus.length;

  // Loading state
  if (loading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="services-panel-loading"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Server className="h-5 w-5 text-[#76B900]" />
          Services
        </Title>
        <div className="space-y-3">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-800"></div>
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error && !healthData) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="services-panel-error"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Server className="h-5 w-5 text-[#76B900]" />
          Services
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <XCircle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load services</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg',
        hasUnhealthy && 'border-red-500/30',
        className
      )}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Server className="h-5 w-5 text-[#76B900]" />
          Services
        </Title>
        <Badge
          color={totalHealthy === totalServices ? 'emerald' : totalHealthy === 0 ? 'red' : 'yellow'}
          size="sm"
          data-testid="services-total-badge"
        >
          {totalHealthy}/{totalServices} Healthy
        </Badge>
      </div>

      {/* Category Summary Bar */}
      <CategorySummaryBar summaries={categorySummaries} />

      {/* Services grouped by category */}
      <div className="space-y-4">
        {(['infrastructure', 'ai', 'monitoring'] as ServiceCategory[]).map((category) => {
          const CategoryIcon = CATEGORY_CONFIG[category].icon;
          const categoryServices = servicesByCategory[category];

          if (categoryServices.length === 0) return null;

          return (
            <div key={category} data-testid={`category-group-${category}`}>
              <div className="mb-2 flex items-center gap-2">
                <CategoryIcon className="h-4 w-4 text-gray-400" />
                <Text className="text-sm font-medium text-gray-300">
                  {CATEGORY_CONFIG[category].label}
                </Text>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                {categoryServices.map((service) => (
                  <ServiceCard
                    key={service.name}
                    service={service}
                    onRestart={() => void handleRestart(service.name)}
                    onToggle={(enabled) => handleToggle(service.name, enabled)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Last updated timestamp */}
      {healthData?.timestamp && (
        <Text className="mt-4 text-xs text-gray-500" data-testid="services-last-updated">
          Last updated: {new Date(healthData.timestamp).toLocaleTimeString()}
        </Text>
      )}
    </Card>
  );
}
