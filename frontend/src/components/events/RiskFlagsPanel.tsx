/**
 * RiskFlagsPanel - Display risk flags from analysis (NEM-3601)
 *
 * Shows flags raised during risk analysis such as loitering, nighttime activity,
 * weapon detection, etc. Each flag has a severity level (warning, alert, critical).
 */

import { clsx } from 'clsx';
import { AlertCircle, AlertTriangle, XCircle } from 'lucide-react';

import { FLAG_SEVERITY_CONFIG } from '../../types/risk-analysis';

import type { RiskFlag, FlagSeverity } from '../../types/risk-analysis';
import type { ReactNode } from 'react';

export interface RiskFlagsPanelProps {
  /** List of risk flags from analysis */
  flags: RiskFlag[] | null | undefined;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get icon for flag severity
 */
function getSeverityIcon(severity: FlagSeverity): ReactNode {
  const iconClass = 'h-4 w-4';

  switch (severity) {
    case 'critical':
      return <XCircle className={iconClass} />;
    case 'alert':
      return <AlertCircle className={iconClass} />;
    case 'warning':
    default:
      return <AlertTriangle className={iconClass} />;
  }
}

/**
 * Format flag type for display
 */
function formatFlagType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/-/g, ' ')
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Sort flags by severity (critical first, then alert, then warning)
 */
function sortBySeverity(flags: RiskFlag[]): RiskFlag[] {
  const severityOrder: Record<FlagSeverity, number> = {
    critical: 0,
    alert: 1,
    warning: 2,
  };

  return [...flags].sort((a, b) => {
    const aOrder = severityOrder[a.severity] ?? 3;
    const bOrder = severityOrder[b.severity] ?? 3;
    return aOrder - bOrder;
  });
}

/**
 * Single flag item component
 */
function FlagItem({ flag }: { flag: RiskFlag }) {
  const config = FLAG_SEVERITY_CONFIG[flag.severity] || FLAG_SEVERITY_CONFIG.warning;

  return (
    <div
      data-testid="risk-flag-item"
      className={clsx(
        'flex items-start gap-3 rounded-lg border p-3',
        config.bgColor,
        config.borderColor
      )}
    >
      <div className={clsx('flex-shrink-0 mt-0.5', config.color)}>
        {getSeverityIcon(flag.severity)}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <h5 className={clsx('text-sm font-medium', config.color)}>
            {formatFlagType(flag.type)}
          </h5>
          <span
            className={clsx(
              'inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-medium',
              config.bgColor,
              config.color
            )}
          >
            {config.label}
          </span>
        </div>
        <p className="text-xs text-gray-300">{flag.description}</p>
      </div>
    </div>
  );
}

/**
 * RiskFlagsPanel component
 *
 * Renders a list of risk flags from analysis, sorted by severity.
 * Returns null if no flags are provided.
 */
export default function RiskFlagsPanel({
  flags,
  className,
}: RiskFlagsPanelProps) {
  // Don't render if no flags
  if (!flags || flags.length === 0) {
    return null;
  }

  const sortedFlags = sortBySeverity(flags);
  const hasCritical = flags.some((f) => f.severity === 'critical');

  return (
    <div
      data-testid="risk-flags-panel"
      className={clsx('space-y-3', className)}
    >
      <div className="flex items-center gap-2">
        <h4 className={clsx(
          'text-sm font-semibold uppercase tracking-wide',
          hasCritical ? 'text-red-400' : 'text-gray-400'
        )}>
          Risk Flags
        </h4>
        <span
          className={clsx(
            'inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs font-bold',
            hasCritical
              ? 'bg-red-500 text-white'
              : 'bg-gray-600 text-gray-200'
          )}
        >
          {flags.length}
        </span>
      </div>

      <div className="space-y-2">
        {sortedFlags.map((flag, index) => (
          <FlagItem key={`${flag.type}-${index}`} flag={flag} />
        ))}
      </div>
    </div>
  );
}
