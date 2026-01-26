import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Box,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Pause,
  Loader2,
  Clock,
  Server,
  Cpu,
  HardDrive,
} from 'lucide-react';
import { useEffect, useState, useCallback, useMemo, useRef } from 'react';

import {
  fetchContainerServices,
  type ContainerServicesResponse,
  type ServiceInfo,
  type ContainerCategorySummary,
} from '../../services/api';

/**
 * Container status type
 */
export type ContainerStatus = 'running' | 'starting' | 'unhealthy' | 'stopped' | 'disabled' | 'not_found';

/**
 * Category type
 */
export type ContainerCategory = 'infrastructure' | 'ai' | 'monitoring';

/**
 * Extended container information with display formatting
 */
export interface ContainerWithStatus extends ServiceInfo {
  displayStatus: ContainerStatus;
  uptimeFormatted: string | null;
}

/**
 * Props for ContainersPanel component
 */
export interface ContainersPanelProps {
  /** Polling interval in milliseconds (default: 30000) */
  pollingInterval?: number;
  /** Category filter (optional) */
  category?: ContainerCategory;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * Normalize backend status string to display status
 */
function normalizeStatus(status: string | undefined): ContainerStatus {
  if (!status) return 'not_found';
  const normalized = status.toLowerCase();
  switch (normalized) {
    case 'running':
      return 'running';
    case 'starting':
      return 'starting';
    case 'unhealthy':
      return 'unhealthy';
    case 'stopped':
      return 'stopped';
    case 'disabled':
      return 'disabled';
    case 'not_found':
      return 'not_found';
    default:
      return 'not_found';
  }
}

/**
 * Get badge color for container status
 */
function getStatusColor(status: ContainerStatus): 'emerald' | 'red' | 'yellow' | 'gray' {
  switch (status) {
    case 'running':
      return 'emerald';
    case 'unhealthy':
      return 'red';
    case 'starting':
      return 'yellow';
    case 'stopped':
    case 'disabled':
    case 'not_found':
    default:
      return 'gray';
  }
}

/**
 * Get status icon component
 */
function StatusIcon({ status }: { status: ContainerStatus }) {
  switch (status) {
    case 'running':
      return <CheckCircle className="h-4 w-4 text-green-500" data-testid="status-icon-running" />;
    case 'unhealthy':
      return <XCircle className="h-4 w-4 text-red-500" data-testid="status-icon-unhealthy" />;
    case 'starting':
      return <Loader2 className="h-4 w-4 animate-spin text-yellow-500" data-testid="status-icon-starting" />;
    case 'stopped':
      return <Pause className="h-4 w-4 text-gray-500" data-testid="status-icon-stopped" />;
    case 'disabled':
      return <AlertTriangle className="h-4 w-4 text-gray-500" data-testid="status-icon-disabled" />;
    case 'not_found':
    default:
      return <AlertTriangle className="h-4 w-4 text-gray-500" data-testid="status-icon-not-found" />;
  }
}

/**
 * Format uptime in seconds to human-readable format
 */
function formatUptime(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined) return null;

  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${seconds}s`;
}

/**
 * Format status for display (capitalize first letter)
 */
function formatStatus(status: ContainerStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ');
}

/**
 * Get category display label
 */
function getCategoryLabel(category: ContainerCategory): string {
  switch (category) {
    case 'infrastructure':
      return 'Infrastructure';
    case 'ai':
      return 'AI Services';
    case 'monitoring':
      return 'Monitoring';
    default:
      return category;
  }
}

/**
 * Get category icon component
 */
function CategoryIcon({ category }: { category: ContainerCategory }) {
  switch (category) {
    case 'infrastructure':
      return <HardDrive className="h-4 w-4 text-blue-400" />;
    case 'ai':
      return <Cpu className="h-4 w-4 text-purple-400" />;
    case 'monitoring':
      return <Server className="h-4 w-4 text-orange-400" />;
    default:
      return <Box className="h-4 w-4 text-gray-400" />;
  }
}

/**
 * ContainerCard - Individual container status card
 */
interface ContainerCardProps {
  container: ContainerWithStatus;
}

function ContainerCard({ container }: ContainerCardProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border p-3 transition-colors',
        container.displayStatus === 'running' && 'border-gray-700 bg-gray-800/50',
        container.displayStatus === 'unhealthy' && 'border-red-500/30 bg-red-500/10',
        container.displayStatus === 'starting' && 'border-yellow-500/30 bg-yellow-500/10',
        (container.displayStatus === 'stopped' ||
          container.displayStatus === 'disabled' ||
          container.displayStatus === 'not_found') &&
          'border-gray-600 bg-gray-800/30'
      )}
      data-testid={`container-card-${container.name}`}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Left side: Status and info */}
        <div className="flex items-start gap-2">
          <StatusIcon status={container.displayStatus} />
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <Text className="text-sm font-medium text-gray-200">{container.display_name}</Text>
              {container.port && <Text className="text-xs text-gray-500">:{container.port}</Text>}
            </div>
            {container.container_id && (
              <Text className="text-xs text-gray-500" data-testid={`container-id-${container.name}`}>
                ID: {container.container_id}
              </Text>
            )}
            {container.image && (
              <Text className="text-xs text-gray-500 truncate max-w-[200px]" title={container.image}>
                {container.image}
              </Text>
            )}
          </div>
        </div>

        {/* Right side: Status badge and metrics */}
        <div className="flex flex-col items-end gap-1">
          <Badge
            color={getStatusColor(container.displayStatus)}
            size="xs"
            data-testid={`container-status-badge-${container.name}`}
          >
            {formatStatus(container.displayStatus)}
          </Badge>

          {/* Uptime */}
          {container.uptimeFormatted && (
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3 text-gray-500" />
              <Text className="text-xs text-gray-400" data-testid={`container-uptime-${container.name}`}>
                {container.uptimeFormatted}
              </Text>
            </div>
          )}

          {/* Restart count */}
          {container.restart_count > 0 && (
            <div className="flex items-center gap-1">
              <RefreshCw className="h-3 w-3 text-gray-500" />
              <Text className="text-xs text-gray-400" data-testid={`container-restarts-${container.name}`}>
                {container.restart_count} restarts
              </Text>
            </div>
          )}

          {/* Failure count warning */}
          {container.failure_count > 0 && (
            <Badge color="red" size="xs" data-testid={`container-failures-${container.name}`}>
              {container.failure_count} failures
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * CategorySummaryBar - Shows health counts per category
 */
interface CategorySummaryBarProps {
  summaries: Record<string, ContainerCategorySummary>;
}

function CategorySummaryBar({ summaries }: CategorySummaryBarProps) {
  const categories: ContainerCategory[] = ['infrastructure', 'ai', 'monitoring'];

  return (
    <div className="mb-4 flex flex-wrap gap-2" data-testid="category-summary-bar">
      {categories.map((category) => {
        const summary = summaries[category];
        if (!summary) return null;

        const isAllHealthy = summary.healthy === summary.total;

        return (
          <div
            key={category}
            className={clsx(
              'flex items-center gap-2 rounded-lg px-3 py-1.5',
              isAllHealthy ? 'bg-gray-800/50' : 'bg-yellow-500/10'
            )}
            data-testid={`category-summary-${category}`}
          >
            <CategoryIcon category={category} />
            <Text className="text-sm text-gray-300">{getCategoryLabel(category)}</Text>
            <Badge
              color={isAllHealthy ? 'emerald' : summary.unhealthy > 0 ? 'red' : 'yellow'}
              size="xs"
              data-testid={`category-badge-${category}`}
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
 * ContainersPanel - Displays container status and metrics
 *
 * Shows:
 * - List of all running containers
 * - Container status indicators (running, stopped, unhealthy, etc.)
 * - Container uptime
 * - Image name and container ID
 * - Port mappings
 * - Health check status
 * - Restart and failure counts
 * - Category summaries
 */
export default function ContainersPanel({
  pollingInterval = 30000,
  category,
  className,
  'data-testid': testId = 'containers-panel',
}: ContainersPanelProps) {
  // State for container data
  const [data, setData] = useState<ContainerServicesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track if component is mounted
  const isMountedRef = useRef(true);

  // Fetch container data
  const fetchData = useCallback(async () => {
    if (!isMountedRef.current) return;

    try {
      const response = await fetchContainerServices(category);
      if (isMountedRef.current) {
        setData(response);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      if (isMountedRef.current) {
        console.error('Failed to fetch container data:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch container data');
        setLoading(false);
      }
    }
  }, [category]);

  // Initial fetch
  useEffect(() => {
    isMountedRef.current = true;
    void fetchData();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchData]);

  // Polling
  useEffect(() => {
    if (pollingInterval <= 0) return;

    const intervalId = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(intervalId);
  }, [pollingInterval, fetchData]);

  // Transform service data to container display format
  const containersWithStatus: ContainerWithStatus[] = useMemo(() => {
    if (!data?.services) return [];

    return data.services.map((service) => ({
      ...service,
      displayStatus: normalizeStatus(service.status),
      uptimeFormatted: formatUptime(service.uptime_seconds),
    }));
  }, [data]);

  // Group containers by category
  const containersByCategory = useMemo(() => {
    const groups: Record<ContainerCategory, ContainerWithStatus[]> = {
      infrastructure: [],
      ai: [],
      monitoring: [],
    };

    containersWithStatus.forEach((container) => {
      const cat = container.category as ContainerCategory;
      if (groups[cat]) {
        groups[cat].push(container);
      }
    });

    return groups;
  }, [containersWithStatus]);

  // Calculate totals
  const totalContainers = containersWithStatus.length;
  const runningContainers = containersWithStatus.filter((c) => c.displayStatus === 'running').length;

  // Loading state
  if (loading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="containers-panel-loading"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Box className="h-5 w-5 text-[#76B900]" />
          Containers
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
  if (error && !data) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="containers-panel-error"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Box className="h-5 w-5 text-[#76B900]" />
          Containers
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <XCircle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load containers</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Box className="h-5 w-5 text-[#76B900]" />
          Containers
        </Title>
        <Badge
          color={runningContainers === totalContainers ? 'emerald' : runningContainers === 0 ? 'red' : 'yellow'}
          size="sm"
          data-testid="containers-total-badge"
        >
          {runningContainers}/{totalContainers} Running
        </Badge>
      </div>

      {/* Category Summary Bar */}
      {data?.by_category && <CategorySummaryBar summaries={data.by_category} />}

      {/* Containers grouped by category */}
      <div className="space-y-4">
        {(['infrastructure', 'ai', 'monitoring'] as ContainerCategory[]).map((cat) => {
          const categoryContainers = containersByCategory[cat];

          if (categoryContainers.length === 0) return null;

          return (
            <div key={cat} data-testid={`category-group-${cat}`}>
              <div className="mb-2 flex items-center gap-2">
                <CategoryIcon category={cat} />
                <Text className="text-sm font-medium text-gray-300">{getCategoryLabel(cat)}</Text>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                {categoryContainers.map((container) => (
                  <ContainerCard key={container.name} container={container} />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Last updated timestamp */}
      {data?.timestamp && (
        <Text className="mt-4 text-xs text-gray-500" data-testid="containers-last-updated">
          Last updated: {new Date(data.timestamp).toLocaleTimeString()}
        </Text>
      )}
    </Card>
  );
}
