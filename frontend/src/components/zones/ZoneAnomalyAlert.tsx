/**
 * ZoneAnomalyAlert - Individual anomaly alert card component (NEM-3199)
 *
 * Displays a single zone anomaly alert with severity-based styling,
 * acknowledge functionality, and navigation to zone details.
 *
 * Features:
 * - Severity-based colors (INFO=blue, WARNING=yellow, CRITICAL=red)
 * - Severity icon display
 * - Title, description, zone name, and timestamp display
 * - Acknowledge button to dismiss alerts
 * - Click to view zone details
 * - Thumbnail image support
 *
 * @module components/zones/ZoneAnomalyAlert
 * @see NEM-3199 Frontend Anomaly Alert Integration
 */

import { clsx } from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import {
  AlertOctagon,
  AlertTriangle,
  Info,
  Clock,
  Activity,
  Timer,
  HelpCircle,
  Check,
  ExternalLink,
} from 'lucide-react';
import { memo, useCallback } from 'react';
import { Link } from 'react-router-dom';

import {
  AnomalySeverity,
  AnomalyType,
  ANOMALY_SEVERITY_CONFIG,
  ANOMALY_TYPE_CONFIG,
} from '../../types/zoneAnomaly';

import type { ZoneAnomalyAlertProps } from '../../types/zoneAnomaly';

// ============================================================================
// Icon Components
// ============================================================================

/**
 * Get the severity icon component based on severity level.
 */
function SeverityIcon({ severity, className }: { severity: AnomalySeverity; className?: string }) {
  const iconProps = { className: clsx('h-5 w-5', className) };

  switch (severity) {
    case AnomalySeverity.CRITICAL:
      return <AlertOctagon {...iconProps} />;
    case AnomalySeverity.WARNING:
      return <AlertTriangle {...iconProps} />;
    case AnomalySeverity.INFO:
    default:
      return <Info {...iconProps} />;
  }
}

/**
 * Get the anomaly type icon component.
 */
function AnomalyTypeIcon({ type, className }: { type: AnomalyType; className?: string }) {
  const iconProps = { className: clsx('h-4 w-4', className) };

  switch (type) {
    case AnomalyType.UNUSUAL_TIME:
      return <Clock {...iconProps} />;
    case AnomalyType.UNUSUAL_FREQUENCY:
      return <Activity {...iconProps} />;
    case AnomalyType.UNUSUAL_DWELL:
      return <Timer {...iconProps} />;
    case AnomalyType.UNUSUAL_ENTITY:
    default:
      return <HelpCircle {...iconProps} />;
  }
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneAnomalyAlert component displays an individual anomaly alert card.
 *
 * Features severity-based styling with appropriate colors and icons,
 * acknowledge functionality, and links to zone details.
 *
 * @example
 * ```tsx
 * <ZoneAnomalyAlert
 *   anomaly={anomaly}
 *   zoneName="Front Door"
 *   onAcknowledge={handleAcknowledge}
 *   onClick={handleClick}
 * />
 * ```
 */
function ZoneAnomalyAlertComponent({
  anomaly,
  zoneName,
  onAcknowledge,
  onClick,
  isAcknowledging = false,
  expanded = false,
  className,
}: ZoneAnomalyAlertProps) {
  const severityConfig = ANOMALY_SEVERITY_CONFIG[anomaly.severity];
  const typeConfig = ANOMALY_TYPE_CONFIG[anomaly.anomaly_type];

  // Format the timestamp
  const formattedTime = formatDistanceToNow(new Date(anomaly.timestamp), {
    addSuffix: true,
  });

  // Handle acknowledge click
  const handleAcknowledge = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      onAcknowledge?.(anomaly.id);
    },
    [anomaly.id, onAcknowledge]
  );

  // Handle card click
  const handleClick = useCallback(() => {
    onClick?.(anomaly);
  }, [anomaly, onClick]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onClick?.(anomaly);
      }
    },
    [anomaly, onClick]
  );

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- role and tabIndex are conditionally set when interactive
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick ? handleClick : undefined}
      onKeyDown={onClick ? handleKeyDown : undefined}
      className={clsx(
        'rounded-lg border p-4 transition-all',
        severityConfig.bgColor,
        severityConfig.borderColor,
        anomaly.acknowledged && 'opacity-60',
        onClick && 'cursor-pointer hover:bg-opacity-75',
        className
      )}
      data-testid="zone-anomaly-alert"
      data-severity={anomaly.severity}
      data-acknowledged={anomaly.acknowledged}
    >
      {/* Header with severity icon and title */}
      <div className="flex items-start gap-3">
        {/* Severity Icon */}
        <div className={clsx('mt-0.5 shrink-0 rounded-full p-1.5', severityConfig.bgColor)}>
          <SeverityIcon severity={anomaly.severity} className={severityConfig.color} />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {/* Title and timestamp row */}
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h4
                className={clsx(
                  'font-medium leading-tight',
                  anomaly.acknowledged ? 'text-text-secondary' : 'text-text-primary'
                )}
              >
                {anomaly.title}
              </h4>

              {/* Zone name and type badge */}
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                {zoneName && (
                  <Link
                    to={`/zones/${anomaly.zone_id}`}
                    className="text-primary hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {zoneName}
                  </Link>
                )}
                <span
                  className={clsx(
                    'inline-flex items-center gap-1 rounded px-1.5 py-0.5',
                    'bg-gray-700/50 text-gray-400'
                  )}
                >
                  <AnomalyTypeIcon type={anomaly.anomaly_type} />
                  {typeConfig.label}
                </span>
              </div>
            </div>

            {/* Timestamp and acknowledge button */}
            <div className="flex shrink-0 items-center gap-2">
              <span className="text-xs text-text-secondary">{formattedTime}</span>

              {/* Acknowledge button */}
              {!anomaly.acknowledged && onAcknowledge && (
                <button
                  type="button"
                  onClick={handleAcknowledge}
                  disabled={isAcknowledging}
                  className={clsx(
                    'rounded p-1.5 transition-colors',
                    'text-gray-400 hover:bg-gray-700 hover:text-text-primary',
                    'focus:outline-none focus:ring-2 focus:ring-primary',
                    isAcknowledging && 'cursor-not-allowed opacity-50'
                  )}
                  title="Acknowledge anomaly"
                  aria-label="Acknowledge anomaly"
                >
                  <Check className="h-4 w-4" />
                </button>
              )}

              {/* Acknowledged indicator */}
              {anomaly.acknowledged && (
                <span
                  className="rounded bg-green-500/20 px-1.5 py-0.5 text-xs text-green-400"
                  title={`Acknowledged ${anomaly.acknowledged_at ? formatDistanceToNow(new Date(anomaly.acknowledged_at), { addSuffix: true }) : ''}`}
                >
                  Acknowledged
                </span>
              )}
            </div>
          </div>

          {/* Description */}
          {anomaly.description && (
            <p
              className={clsx(
                'mt-2 text-sm',
                anomaly.acknowledged ? 'text-gray-500' : 'text-text-secondary',
                !expanded && 'line-clamp-2'
              )}
            >
              {anomaly.description}
            </p>
          )}

          {/* Statistics row */}
          {(anomaly.expected_value !== null || anomaly.actual_value !== null) && (
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500">
              {anomaly.expected_value !== null && (
                <span>
                  Expected:{' '}
                  <span className="text-text-secondary">{anomaly.expected_value.toFixed(1)}</span>
                </span>
              )}
              {anomaly.actual_value !== null && (
                <span>
                  Actual:{' '}
                  <span className={severityConfig.color}>{anomaly.actual_value.toFixed(1)}</span>
                </span>
              )}
              {anomaly.deviation !== null && (
                <span>
                  Deviation:{' '}
                  <span className={severityConfig.color}>{anomaly.deviation.toFixed(1)} std</span>
                </span>
              )}
            </div>
          )}

          {/* Thumbnail */}
          {anomaly.thumbnail_url && expanded && (
            <div className="mt-3">
              <img
                src={anomaly.thumbnail_url}
                alt={`Thumbnail for anomaly: ${anomaly.title}`}
                className="h-24 w-auto rounded border border-gray-700 object-cover"
                loading="lazy"
              />
            </div>
          )}

          {/* Link to zone details */}
          {expanded && (
            <div className="mt-3">
              <Link
                to={`/zones/${anomaly.zone_id}`}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                View zone details
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Memoized ZoneAnomalyAlert component for performance.
 */
export const ZoneAnomalyAlert = memo(ZoneAnomalyAlertComponent);

export default ZoneAnomalyAlert;
