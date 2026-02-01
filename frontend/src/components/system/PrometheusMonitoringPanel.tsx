import { Card, Text, Badge, Button } from '@tremor/react';
import { clsx } from 'clsx';
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  HelpCircle,
} from 'lucide-react';
import React from 'react';

import { useMonitoringHealth } from '../../hooks/useMonitoringHealth';

import type { ExporterStatus, TargetSummary } from '../../services/monitoringApi';

/**
 * Props for PrometheusMonitoringPanel component
 */
export interface PrometheusMonitoringPanelProps {
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * Format a timestamp for display
 */
function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    // Format as YYYY-MM-DD HH:MM:SS
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  } catch {
    return timestamp;
  }
}

/**
 * Get badge color for exporter status
 */
function getStatusBadgeColor(status: 'up' | 'down' | 'unknown'): 'green' | 'red' | 'gray' {
  switch (status) {
    case 'up':
      return 'green';
    case 'down':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Status icon component
 */
function StatusIcon({ status }: { status: 'up' | 'down' | 'unknown' }) {
  switch (status) {
    case 'up':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'down':
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <HelpCircle className="h-4 w-4 text-gray-500" />;
  }
}

/**
 * Target summary table component
 */
function TargetSummaryTable({ targets }: { targets: TargetSummary[] }) {
  if (targets.length === 0) {
    return (
      <Text className="text-sm italic text-gray-500">No targets configured</Text>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-gray-700">
          <th className="py-2 text-left font-medium text-gray-400">Job</th>
          <th className="py-2 text-center font-medium text-gray-400">Total</th>
          <th className="py-2 text-center font-medium text-gray-400">Up</th>
          <th className="py-2 text-center font-medium text-gray-400">Down</th>
        </tr>
      </thead>
      <tbody>
        {targets.map((target) => (
          <tr key={target.job} className="border-b border-gray-800">
            <td className="py-2 text-gray-200">{target.job}</td>
            <td className="py-2 text-center text-gray-300">{target.total}</td>
            <td className="py-2 text-center text-green-500">{target.up}</td>
            <td className="py-2 text-center text-red-500">{target.down}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Exporter status list component
 */
function ExporterStatusList({ exporters }: { exporters: ExporterStatus[] }) {
  if (exporters.length === 0) {
    return (
      <Text className="text-sm italic text-gray-500">No exporters configured</Text>
    );
  }

  return (
    <div className="space-y-2">
      {exporters.map((exporter) => (
        <div
          key={exporter.name}
          className={clsx(
            'flex items-center justify-between rounded-lg border p-3',
            exporter.status === 'up' && 'border-gray-700 bg-gray-800/50',
            exporter.status === 'down' && 'border-red-500/30 bg-red-500/10',
            exporter.status === 'unknown' && 'border-gray-600 bg-gray-800/30'
          )}
        >
          <div className="flex items-center gap-3">
            <StatusIcon status={exporter.status} />
            <div>
              <Text className="text-sm font-medium text-gray-200">{exporter.name}</Text>
              <Text className="text-xs text-gray-500">{exporter.endpoint}</Text>
              {exporter.error && (
                <Text className="text-xs text-red-400">{exporter.error}</Text>
              )}
            </div>
          </div>
          <Badge color={getStatusBadgeColor(exporter.status)} size="xs">
            {exporter.status}
          </Badge>
        </div>
      ))}
    </div>
  );
}

/**
 * PrometheusMonitoringPanel - Displays Prometheus monitoring health status
 *
 * Shows:
 * - Health status badge (Healthy/Unhealthy/Unreachable)
 * - Target summary table with job counts
 * - Exporter status list with health badges
 * - Metrics collection stats
 * - Issues list when present
 * - Last updated timestamp
 * - Refresh button
 */
export function PrometheusMonitoringPanel({
  className,
  'data-testid': testId = 'prometheus-monitoring-panel',
}: PrometheusMonitoringPanelProps): React.ReactElement {
  const { data, isLoading, error, isHealthy, refetch } = useMonitoringHealth({
    pollingInterval: 30000,
  });

  // Loading state
  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="monitoring-loading-skeleton"
      >
        <div className="space-y-4">
          <div className="h-8 w-48 animate-pulse rounded bg-gray-800"></div>
          <div className="h-24 animate-pulse rounded bg-gray-800"></div>
          <div className="h-32 animate-pulse rounded bg-gray-800"></div>
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={testId}
      >
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <XCircle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Error loading monitoring data</Text>
            <Text className="text-xs text-gray-400">{error.message}</Text>
          </div>
        </div>
        <Button
          size="xs"
          variant="secondary"
          icon={RefreshCw}
          onClick={refetch}
          className="mt-4"
        >
          Retry
        </Button>
      </Card>
    );
  }

  // No data state (shouldn't normally happen after loading)
  if (!data) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={testId}
      >
        <Text className="text-sm text-gray-400">No monitoring data available</Text>
      </Card>
    );
  }

  // Determine health badge content and color
  let healthBadgeText: string;
  let healthBadgeColor: 'green' | 'red' | 'gray';

  if (!data.prometheus_reachable) {
    healthBadgeText = 'Prometheus Unreachable';
    healthBadgeColor = 'gray';
  } else if (isHealthy) {
    healthBadgeText = 'Prometheus Healthy';
    healthBadgeColor = 'green';
  } else {
    healthBadgeText = 'Prometheus Unhealthy';
    healthBadgeColor = 'red';
  }

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg',
        !isHealthy && 'border-red-500/30',
        className
      )}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Badge color={healthBadgeColor} size="sm">
          {healthBadgeText}
        </Badge>
        <Button
          size="xs"
          variant="secondary"
          icon={RefreshCw}
          onClick={refetch}
          disabled={isLoading}
          aria-label="Refresh monitoring data"
        >
          Refresh
        </Button>
      </div>

      {/* Prometheus URL */}
      <Text className="mb-4 text-xs text-gray-400">
        URL: <span className="text-gray-300">{data.prometheus_url}</span>
      </Text>

      {/* Target Summary */}
      <div className="mb-4">
        <Text className="mb-2 text-sm font-medium text-gray-300">Target Summary</Text>
        <TargetSummaryTable targets={data.targets_summary} />
      </div>

      {/* Exporter Status */}
      <div className="mb-4">
        <Text className="mb-2 text-sm font-medium text-gray-300">Exporter Status</Text>
        <ExporterStatusList exporters={data.exporters} />
      </div>

      {/* Metrics Collection Stats */}
      <div className="mb-4 rounded-lg border border-gray-700 bg-gray-800/50 p-3">
        <Text className="mb-2 text-sm font-medium text-gray-300">Metrics Collection</Text>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <Text className="text-gray-500">Status</Text>
            <Text className={data.metrics_collection.collecting ? 'text-green-400' : 'text-red-400'}>
              {data.metrics_collection.collecting ? 'Collecting' : 'Not Collecting'}
            </Text>
          </div>
          <div>
            <Text className="text-gray-500">Total Series</Text>
            <Text className="text-gray-200">{data.metrics_collection.total_series}</Text>
          </div>
          <div>
            <Text className="text-gray-500">Scrape Interval</Text>
            <Text className="text-gray-200">{data.metrics_collection.scrape_interval_seconds}s</Text>
          </div>
          {data.metrics_collection.last_successful_scrape && (
            <div>
              <Text className="text-gray-500">Last Scrape</Text>
              <Text className="text-gray-200">
                {formatTimestamp(data.metrics_collection.last_successful_scrape)}
              </Text>
            </div>
          )}
        </div>
      </div>

      {/* Issues List */}
      {data.issues.length > 0 && (
        <div className="mb-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3">
          <div className="mb-2 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
            <Text className="text-sm font-medium text-yellow-400">Issues</Text>
          </div>
          <div className="space-y-1">
            {data.issues.map((issue, index) => (
              <Text key={index} className="text-xs text-yellow-300">
                {issue}
              </Text>
            ))}
          </div>
        </div>
      )}

      {/* Last Updated */}
      <Text className="text-xs text-gray-500">
        Last updated: {formatTimestamp(data.timestamp)}
      </Text>
    </Card>
  );
}

export default PrometheusMonitoringPanel;
