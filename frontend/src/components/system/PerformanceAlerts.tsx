import { Callout } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertTriangle, AlertCircle } from 'lucide-react';

import type { PerformanceAlert } from '../../types/performance';

export interface PerformanceAlertsProps {
  /** Array of performance alerts to display */
  alerts: PerformanceAlert[];
  /** Additional CSS classes */
  className?: string;
}

/**
 * PerformanceAlerts - Displays threshold breach warnings and critical alerts.
 *
 * Shows alert callouts using Tremor's Callout component:
 * - Warning alerts (yellow/amber): Threshold approaching critical
 * - Critical alerts (red): Threshold exceeded, immediate attention needed
 *
 * Only renders when there are alerts to display. Returns null for empty arrays.
 *
 * Alert thresholds are computed server-side and included in the WebSocket
 * performance_update messages.
 *
 * @example
 * ```tsx
 * <PerformanceAlerts
 *   alerts={[
 *     { severity: 'warning', metric: 'gpu_temp', value: 82, threshold: 80, message: 'GPU temp high' },
 *     { severity: 'critical', metric: 'vram', value: 23, threshold: 22.8, message: 'VRAM critical' },
 *   ]}
 * />
 * ```
 */
export default function PerformanceAlerts({ alerts, className }: PerformanceAlertsProps) {
  // Don't render anything if there are no alerts
  if (!alerts || alerts.length === 0) {
    return null;
  }

  return (
    <div className={clsx('space-y-2', className)} data-testid="performance-alerts">
      {alerts.map((alert) => (
        <Callout
          key={`${alert.severity}-${alert.metric}`}
          title={alert.message}
          icon={alert.severity === 'critical' ? AlertCircle : AlertTriangle}
          color={alert.severity === 'critical' ? 'red' : 'yellow'}
          data-testid={`alert-${alert.severity}-${alert.metric}`}
        />
      ))}
    </div>
  );
}
