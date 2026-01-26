import { Card, Title, Text, ProgressBar, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Monitor, Cpu, HardDrive, Clock, Server, MemoryStick } from 'lucide-react';

/**
 * Host system metrics from the performance API
 */
export interface HostSystemMetrics {
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  disk_used_gb: number;
  disk_total_gb: number;
}

/**
 * System stats including uptime
 */
export interface SystemStats {
  uptime_seconds: number;
  total_cameras?: number;
  total_events?: number;
  total_detections?: number;
}

/**
 * Props for HostSystemPanel component
 */
export interface HostSystemPanelProps {
  /** Host system metrics (null if unavailable) */
  metrics: HostSystemMetrics | null;
  /** System stats including uptime (null if unavailable) */
  stats?: SystemStats | null;
  /** OS information (optional) */
  osInfo?: string;
  /** Hostname (optional) */
  hostname?: string;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Error message if data failed to load */
  error?: string | null;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * Get color for usage percentage thresholds
 */
function getUsageColor(
  percent: number,
  thresholds: { warning: number; critical: number } = { warning: 80, critical: 95 }
): 'green' | 'yellow' | 'red' {
  if (percent >= thresholds.critical) return 'red';
  if (percent >= thresholds.warning) return 'yellow';
  return 'green';
}

/**
 * Get badge color based on overall status
 */
function getStatusColor(metrics: HostSystemMetrics): 'emerald' | 'yellow' | 'red' {
  const ramPercent = (metrics.ram_used_gb / metrics.ram_total_gb) * 100;
  const diskPercent = (metrics.disk_used_gb / metrics.disk_total_gb) * 100;

  // Critical if any metric is critical
  if (metrics.cpu_percent >= 95 || ramPercent >= 95 || diskPercent >= 90) {
    return 'red';
  }
  // Warning if any metric is in warning range
  if (metrics.cpu_percent >= 80 || ramPercent >= 85 || diskPercent >= 80) {
    return 'yellow';
  }
  return 'emerald';
}

/**
 * Format uptime in seconds to human-readable format
 */
function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

/**
 * Format bytes to human-readable format (GB)
 */
function formatGB(gb: number): string {
  if (gb >= 1000) {
    return `${(gb / 1000).toFixed(2)} TB`;
  }
  return `${gb.toFixed(1)} GB`;
}

/**
 * HostSystemPanel - Displays host system metrics
 *
 * Shows:
 * - CPU utilization with progress bar
 * - RAM usage (used/total GB, percentage)
 * - Disk usage (used/total GB, percentage)
 * - System uptime
 * - Optional hostname and OS info
 *
 * Color thresholds:
 * - CPU: green <80%, yellow 80-95%, red >95%
 * - RAM: green <85%, yellow 85-95%, red >95%
 * - Disk: green <80%, yellow 80-90%, red >90%
 */
export default function HostSystemPanel({
  metrics,
  stats,
  osInfo,
  hostname,
  isLoading = false,
  error = null,
  className,
  'data-testid': testId = 'host-system-panel',
}: HostSystemPanelProps) {
  // Loading state
  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={`${testId}-loading`}
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Monitor className="h-5 w-5 text-[#76B900]" />
          Host System
        </Title>
        <div className="space-y-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-10 animate-pulse rounded bg-gray-800" />
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={`${testId}-error`}
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Monitor className="h-5 w-5 text-[#76B900]" />
          Host System
        </Title>
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <Text className="text-sm text-red-400">{error}</Text>
        </div>
      </Card>
    );
  }

  // No data state
  if (!metrics) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={testId}
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Monitor className="h-5 w-5 text-[#76B900]" />
          Host System
        </Title>
        <div className="flex h-40 items-center justify-center">
          <Text className="text-sm text-gray-500">No host data available</Text>
        </div>
      </Card>
    );
  }

  const ramPercent = Math.round((metrics.ram_used_gb / metrics.ram_total_gb) * 100);
  const diskPercent = Math.round((metrics.disk_used_gb / metrics.disk_total_gb) * 100);
  const statusColor = getStatusColor(metrics);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Monitor className="h-5 w-5 text-[#76B900]" />
          Host System
        </Title>
        <Badge color={statusColor} size="sm" data-testid="host-status-badge">
          {statusColor === 'emerald' ? 'Healthy' : statusColor === 'yellow' ? 'Warning' : 'Critical'}
        </Badge>
      </div>

      {/* System Info (Hostname & OS) */}
      {(hostname || osInfo) && (
        <div className="mb-4 flex flex-wrap items-center gap-3 text-xs text-gray-400">
          {hostname && (
            <div className="flex items-center gap-1" data-testid="host-hostname">
              <Server className="h-3 w-3" />
              <span>{hostname}</span>
            </div>
          )}
          {osInfo && (
            <div className="flex items-center gap-1" data-testid="host-os-info">
              <Monitor className="h-3 w-3" />
              <span>{osInfo}</span>
            </div>
          )}
        </div>
      )}

      <div className="space-y-4">
        {/* CPU */}
        <div data-testid="cpu-metric">
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <Cpu className="h-4 w-4" />
              CPU Usage
            </Text>
            <span
              className={clsx(
                'text-sm font-medium',
                getUsageColor(metrics.cpu_percent) === 'green' && 'text-green-400',
                getUsageColor(metrics.cpu_percent) === 'yellow' && 'text-yellow-400',
                getUsageColor(metrics.cpu_percent) === 'red' && 'text-red-400'
              )}
              data-testid="cpu-value"
            >
              {metrics.cpu_percent.toFixed(1)}%
            </span>
          </div>
          <ProgressBar
            value={metrics.cpu_percent}
            color={getUsageColor(metrics.cpu_percent)}
            className="h-2"
            data-testid="cpu-progress"
          />
        </div>

        {/* RAM */}
        <div data-testid="ram-metric">
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <MemoryStick className="h-4 w-4" />
              Memory
            </Text>
            <span className="text-sm text-gray-200" data-testid="ram-value">
              {formatGB(metrics.ram_used_gb)} / {formatGB(metrics.ram_total_gb)} ({ramPercent}%)
            </span>
          </div>
          <ProgressBar
            value={ramPercent}
            color={getUsageColor(ramPercent, { warning: 85, critical: 95 })}
            className="h-2"
            data-testid="ram-progress"
          />
        </div>

        {/* Disk */}
        <div data-testid="disk-metric">
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <HardDrive className="h-4 w-4" />
              Disk
            </Text>
            <span className="text-sm text-gray-200" data-testid="disk-value">
              {formatGB(metrics.disk_used_gb)} / {formatGB(metrics.disk_total_gb)} ({diskPercent}%)
            </span>
          </div>
          <ProgressBar
            value={diskPercent}
            color={getUsageColor(diskPercent, { warning: 80, critical: 90 })}
            className="h-2"
            data-testid="disk-progress"
          />
        </div>

        {/* Uptime */}
        {stats?.uptime_seconds !== undefined && (
          <div
            className="flex items-center justify-between border-t border-gray-700 pt-3"
            data-testid="uptime-metric"
          >
            <Text className="flex items-center gap-1 text-sm text-gray-400">
              <Clock className="h-4 w-4" />
              Uptime
            </Text>
            <span className="text-sm font-medium text-[#76B900]" data-testid="uptime-value">
              {formatUptime(stats.uptime_seconds)}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}
