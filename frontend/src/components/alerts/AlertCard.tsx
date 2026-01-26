import { Check, Clock, Eye, Loader2, X } from 'lucide-react';
import { memo } from 'react';

import { getRiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';
import SnoozeBadge from '../common/SnoozeBadge';
import SnoozeButton from '../common/SnoozeButton';

/**
 * Alert action parameters including version_id for optimistic locking
 * @see NEM-3626
 */
export interface AlertActionParams {
  /** Alert UUID */
  alertId: string;
  /**
   * Version ID for optimistic locking.
   * If provided, the backend will verify this matches before applying changes.
   */
  versionId?: number;
}

export interface AlertCardProps {
  id: string;
  eventId: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending' | 'delivered' | 'acknowledged' | 'dismissed';
  timestamp: string;
  camera_name: string;
  risk_score: number;
  summary: string;
  dedup_key: string;
  /**
   * Version ID for optimistic locking.
   * Passed to action callbacks to detect concurrent modifications.
   * @see NEM-3626
   */
  version_id?: number;
  selected?: boolean;
  /**
   * Whether an action is currently in progress (loading state)
   * @see NEM-3626
   */
  isLoading?: boolean;
  /**
   * Callback when acknowledge button is clicked.
   * Now includes version_id for optimistic locking support.
   * @see NEM-3626
   */
  onAcknowledge?: (params: AlertActionParams) => void;
  /**
   * Callback when dismiss button is clicked.
   * Now includes version_id for optimistic locking support.
   * @see NEM-3626
   */
  onDismiss?: (params: AlertActionParams) => void;
  onSnooze?: (alertId: string, seconds: number) => void;
  /**
   * Callback when unsnooze is clicked.
   * @see NEM-3871
   */
  onUnsnooze?: (alertId: string) => void;
  onViewEvent?: (eventId: number) => void;
  onSelectChange?: (alertId: string, selected: boolean) => void;
  /**
   * ISO timestamp until which the alert is snoozed.
   * @see NEM-3871
   */
  snooze_until?: string | null;
}

/**
 * AlertCard component displays an alert with actionable buttons
 * Distinguishes from EventCard by emphasizing alert-specific actions and severity
 */
const AlertCard = memo(function AlertCard({
  id,
  eventId,
  severity,
  status,
  timestamp,
  camera_name,
  risk_score,
  summary,
  version_id,
  selected,
  isLoading = false,
  onAcknowledge,
  onDismiss,
  onSnooze,
  onUnsnooze,
  onViewEvent,
  onSelectChange,
  snooze_until,
}: AlertCardProps) {

  /**
   * Handle acknowledge action with version_id for optimistic locking
   * @see NEM-3626
   */
  const handleAcknowledge = () => {
    if (onAcknowledge) {
      onAcknowledge({ alertId: id, versionId: version_id });
    }
  };

  /**
   * Handle dismiss action with version_id for optimistic locking
   * @see NEM-3626
   */
  const handleDismiss = () => {
    if (onDismiss) {
      onDismiss({ alertId: id, versionId: version_id });
    }
  };

  // Convert ISO timestamp to readable format
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 60) {
        return diffMins <= 1 ? 'Just now' : `${diffMins} minutes ago`;
      }

      if (diffHours < 24) {
        return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
      }

      if (diffDays < 7) {
        return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
      }

      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
        hour: 'numeric',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  // Severity-based styling
  const getSeverityBorderClass = () => {
    switch (severity) {
      case 'critical':
        return 'border-red-600 bg-red-950/20';
      case 'high':
        return 'border-orange-500 bg-orange-950/20';
      case 'medium':
        return 'border-yellow-500 bg-yellow-950/20';
      case 'low':
        return 'border-blue-500 bg-blue-950/20';
      default:
        return 'border-gray-700 bg-[#1F1F1F]';
    }
  };

  const getSeverityAccentClass = () => {
    switch (severity) {
      case 'critical':
        return 'bg-red-600';
      case 'high':
        return 'bg-orange-500';
      case 'medium':
        return 'bg-yellow-500';
      case 'low':
        return 'bg-blue-500';
      default:
        return 'bg-gray-600';
    }
  };

  const handleCheckboxChange = () => {
    if (onSelectChange) {
      onSelectChange(id, !selected);
    }
  };

  /**
   * Handle snooze via SnoozeButton component
   * @see NEM-3871
   */
  const handleSnooze = (seconds: number) => {
    if (onSnooze) {
      onSnooze(id, seconds);
    }
  };

  /**
   * Handle unsnooze via SnoozeButton component
   * @see NEM-3871
   */
  const handleUnsnooze = () => {
    if (onUnsnooze) {
      onUnsnooze(id);
    }
  };

  const riskLevel = getRiskLevel(risk_score);

  return (
    <article
      className={`relative rounded-lg border-2 ${getSeverityBorderClass()} p-4 transition-all hover:shadow-lg`}
    >
      {/* Severity accent bar */}
      <div
        className={`absolute left-0 top-0 h-full w-1 rounded-l-md ${getSeverityAccentClass()}`}
      />

      {/* Checkbox (if selection enabled) */}
      {selected !== undefined && onSelectChange && (
        <div className="absolute left-3 top-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={handleCheckboxChange}
            className="h-4 w-4 rounded border-gray-600 bg-[#1A1A1A] text-[#76B900] focus:ring-2 focus:ring-[#76B900] focus:ring-offset-0"
            aria-label={`Select alert ${id}`}
          />
        </div>
      )}

      <div className={selected !== undefined ? 'ml-6' : ''}>
        {/* Header with status badge */}
        <div className="mb-2 flex items-start justify-between">
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold text-white">{camera_name}</h3>
              {status === 'pending' && (
                <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400">
                  Unacknowledged
                </span>
              )}
              {status === 'acknowledged' && (
                <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-400">
                  Acknowledged
                </span>
              )}
              {/* NEM-3871: Display SnoozeBadge when event is snoozed */}
              <SnoozeBadge snoozeUntil={snooze_until} size="sm" />
            </div>
            <div className="mt-1 flex items-center gap-2 text-sm text-gray-400">
              <Clock className="h-3.5 w-3.5" />
              <span>{formatTimestamp(timestamp)}</span>
            </div>
          </div>
          <RiskBadge level={riskLevel} size="sm" animated={false} />
        </div>

        {/* Alert summary */}
        <p className="mb-4 text-sm text-gray-300">{summary}</p>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {status === 'pending' && onAcknowledge && (
            <button
              onClick={handleAcknowledge}
              disabled={isLoading}
              className="flex items-center gap-1.5 rounded-md bg-green-600/20 px-3 py-1.5 text-sm font-medium text-green-400 transition-colors hover:bg-green-600/30 disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Acknowledge alert"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              Acknowledge
            </button>
          )}

          {onDismiss && (
            <button
              onClick={handleDismiss}
              disabled={isLoading}
              className="flex items-center gap-1.5 rounded-md bg-gray-700/50 px-3 py-1.5 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Dismiss alert"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <X className="h-4 w-4" />
              )}
              Dismiss
            </button>
          )}

          {onViewEvent && (
            <button
              onClick={() => onViewEvent(eventId)}
              className="flex items-center gap-1.5 rounded-md bg-[#76B900]/20 px-3 py-1.5 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/30"
              aria-label="View event"
            >
              <Eye className="h-4 w-4" />
              View Event
            </button>
          )}

          {/* NEM-3871: Use shared SnoozeButton component */}
          {onSnooze && onUnsnooze && (
            <SnoozeButton
              snoozeUntil={snooze_until}
              onSnooze={handleSnooze}
              onUnsnooze={handleUnsnooze}
              isLoading={isLoading}
              size="sm"
            />
          )}
        </div>
      </div>
    </article>
  );
});

export default AlertCard;
