import { Callout, Badge, Text, Title } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertTriangle, AlertCircle } from 'lucide-react';
import { useMemo } from 'react';

import { usePerformanceMetrics } from '../../hooks/usePerformanceMetrics';

import type { PerformanceAlert } from '../../hooks/usePerformanceMetrics';

export interface PerformanceAlertsProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format a numeric value for display with appropriate precision.
 * For percentages, shows whole numbers. For other metrics, shows one decimal.
 */
function formatValue(value: number, metric: string): string {
  // Check if it appears to be a percentage-based metric
  const isPercentage =
    metric.toLowerCase().includes('percent') ||
    metric.toLowerCase().includes('usage') ||
    metric.toLowerCase().includes('utilization') ||
    metric.toLowerCase().includes('ratio');

  if (isPercentage || value >= 1) {
    return value.toFixed(0);
  }
  return value.toFixed(1);
}

/**
 * Get the display unit for a metric based on its name.
 */
function getMetricUnit(metric: string): string {
  const lowerMetric = metric.toLowerCase();

  if (lowerMetric.includes('temperature') || lowerMetric.includes('temp')) {
    return '\u00B0C';
  }
  if (lowerMetric.includes('latency') || lowerMetric.includes('_ms')) {
    return 'ms';
  }
  if (lowerMetric.includes('memory') || lowerMetric.includes('_mb')) {
    return 'MB';
  }
  if (lowerMetric.includes('vram') || lowerMetric.includes('_gb')) {
    return 'GB';
  }
  if (
    lowerMetric.includes('percent') ||
    lowerMetric.includes('usage') ||
    lowerMetric.includes('utilization') ||
    lowerMetric.includes('ratio')
  ) {
    return '%';
  }

  return '';
}

/**
 * Format metric name for display (convert snake_case to Title Case).
 */
function formatMetricName(metric: string): string {
  return metric
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * PerformanceAlerts - Connected component that displays active performance alerts.
 *
 * Uses the `usePerformanceMetrics` hook to get real-time alerts from the WebSocket
 * performance stream. Each alert displays:
 * - Severity badge (warning = amber, critical = red)
 * - Metric name in human-readable format
 * - Current value vs threshold with appropriate units
 * - Alert message
 *
 * Alerts are sorted by severity (critical first, then warning).
 *
 * @example
 * ```tsx
 * // Basic usage - fetches alerts from usePerformanceMetrics hook
 * <PerformanceAlerts />
 *
 * // With custom styling
 * <PerformanceAlerts className="mt-4" />
 * ```
 */
export function PerformanceAlerts({ className }: PerformanceAlertsProps) {
  const { alerts } = usePerformanceMetrics();

  // Sort alerts by severity (critical first, then warning)
  const sortedAlerts = useMemo(() => {
    return [...alerts].sort((a, b) => {
      if (a.severity === 'critical' && b.severity === 'warning') return -1;
      if (a.severity === 'warning' && b.severity === 'critical') return 1;
      return 0;
    });
  }, [alerts]);

  // Empty state when no alerts
  if (sortedAlerts.length === 0) {
    return (
      <div
        className={clsx('flex items-center justify-center p-4', className)}
        data-testid="performance-alerts-empty"
      >
        <Text className="text-gray-400">No active alerts</Text>
      </div>
    );
  }

  return (
    <div className={clsx('space-y-3', className)} data-testid="performance-alerts">
      <Title className="text-lg font-semibold text-white">Active Alerts</Title>
      <div className="space-y-2">
        {sortedAlerts.map((alert) => {
          const unit = getMetricUnit(alert.metric);
          const formattedValue = formatValue(alert.value, alert.metric);
          const formattedThreshold = formatValue(alert.threshold, alert.metric);
          const Icon = alert.severity === 'critical' ? AlertCircle : AlertTriangle;

          return (
            <Callout
              key={`${alert.severity}-${alert.metric}`}
              title={alert.message}
              icon={Icon}
              color={alert.severity === 'critical' ? 'red' : 'yellow'}
              data-testid={`alert-${alert.severity}-${alert.metric}`}
            >
              <span className="mt-2 flex flex-wrap items-center gap-2">
                <Badge color={alert.severity === 'critical' ? 'red' : 'yellow'} size="sm">
                  {alert.severity.toUpperCase()}
                </Badge>
                <span className="text-tremor-content dark:text-dark-tremor-content text-sm">
                  <span className="font-medium">{formatMetricName(alert.metric)}:</span>{' '}
                  <span className="text-red-400">
                    {formattedValue}
                    {unit}
                  </span>
                  {' > '}
                  <span className="text-gray-400">
                    {formattedThreshold}
                    {unit}
                  </span>
                </span>
              </span>
            </Callout>
          );
        })}
      </div>
    </div>
  );
}

export default PerformanceAlerts;
export type { PerformanceAlert };
