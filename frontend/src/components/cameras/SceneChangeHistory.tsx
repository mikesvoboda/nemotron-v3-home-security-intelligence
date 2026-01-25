/**
 * SceneChangeHistory - List of recent scene change events (NEM-3575)
 *
 * Displays a scrollable list of recent scene change detection events.
 * Shows camera name, change type, similarity score, and timestamp.
 *
 * @module components/cameras/SceneChangeHistory
 */

import { clsx } from 'clsx';
import { AlertTriangle, Camera, CheckCircle, Clock, ShieldAlert } from 'lucide-react';
import { memo, useCallback } from 'react';

import type { SceneChangeEventData } from '../../hooks/useSceneChangeEvents';

/**
 * Props for the SceneChangeHistory component
 */
export interface SceneChangeHistoryProps {
  /** List of recent scene change events */
  events: SceneChangeEventData[];
  /** Maximum number of events to display */
  maxItems?: number;
  /** Callback when an event is clicked */
  onEventClick?: (event: SceneChangeEventData) => void;
  /** Callback to dismiss/acknowledge an event */
  onDismiss?: (eventId: number) => void;
  /** Additional CSS classes */
  className?: string;
  /** Whether to show empty state when no events */
  showEmptyState?: boolean;
  /** Custom empty state message */
  emptyMessage?: string;
}

/**
 * Get change type display info
 */
function getChangeTypeInfo(changeType: string): {
  label: string;
  colorClass: string;
  bgClass: string;
  icon: typeof AlertTriangle;
} {
  switch (changeType) {
    case 'view_blocked':
      return {
        label: 'View Blocked',
        colorClass: 'text-red-400',
        bgClass: 'bg-red-500/10',
        icon: ShieldAlert,
      };
    case 'view_tampered':
      return {
        label: 'Tampered',
        colorClass: 'text-red-400',
        bgClass: 'bg-red-500/10',
        icon: ShieldAlert,
      };
    case 'angle_changed':
      return {
        label: 'Angle Changed',
        colorClass: 'text-amber-400',
        bgClass: 'bg-amber-500/10',
        icon: AlertTriangle,
      };
    default:
      return {
        label: 'Unknown',
        colorClass: 'text-gray-400',
        bgClass: 'bg-gray-500/10',
        icon: AlertTriangle,
      };
  }
}

/**
 * Format similarity score as percentage
 */
function formatSimilarity(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Format timestamp for display
 */
function formatTimestamp(timestamp: string | Date): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);

  // For recent events, show relative time
  if (diffMins < 1) {
    return 'just now';
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  // For older events, show date/time
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Single scene change event item
 */
interface SceneChangeItemProps {
  event: SceneChangeEventData;
  onClick?: () => void;
  onDismiss?: () => void;
}

const SceneChangeItem = memo(function SceneChangeItem({
  event,
  onClick,
  onDismiss,
}: SceneChangeItemProps) {
  const typeInfo = getChangeTypeInfo(event.changeType);
  const TypeIcon = typeInfo.icon;

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- role/tabIndex/onKeyDown are conditionally added when onClick is present
    <div
      className={clsx(
        'rounded-lg border border-gray-800 bg-gray-900/50 p-3 transition-colors',
        onClick && 'cursor-pointer hover:border-gray-700 hover:bg-gray-900'
      )}
      onClick={onClick}
      data-testid={`scene-change-item-${event.id}`}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {/* Camera name and timestamp */}
          <div className="flex items-center gap-2 mb-1">
            <Camera className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" aria-hidden="true" />
            <span className="text-sm font-medium text-white truncate">{event.cameraName}</span>
            <span className="text-xs text-gray-500 flex-shrink-0">
              {formatTimestamp(event.detectedAt)}
            </span>
          </div>

          {/* Change type badge and similarity */}
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={clsx(
                'flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium',
                typeInfo.bgClass,
                typeInfo.colorClass
              )}
            >
              <TypeIcon className="h-3 w-3" aria-hidden="true" />
              {typeInfo.label}
            </span>
            <span className="text-xs text-gray-500">
              Similarity: <span className="text-gray-400">{formatSimilarity(event.similarityScore)}</span>
            </span>
          </div>
        </div>

        {/* Dismiss button */}
        {onDismiss && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDismiss();
            }}
            className="flex-shrink-0 rounded-full p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300 transition-colors"
            title="Dismiss"
            aria-label="Dismiss scene change alert"
          >
            <CheckCircle className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
});

/**
 * SceneChangeHistory component
 *
 * Displays a list of recent scene change events with camera info,
 * change type, and similarity scores.
 *
 * @example
 * ```tsx
 * const { recentEvents } = useSceneChangeEvents();
 *
 * <SceneChangeHistory
 *   events={recentEvents}
 *   maxItems={10}
 *   onEventClick={(event) => navigate(`/camera/${event.cameraId}`)}
 * />
 * ```
 */
function SceneChangeHistoryComponent({
  events,
  maxItems = 20,
  onEventClick,
  onDismiss,
  className,
  showEmptyState = true,
  emptyMessage = 'No recent scene changes',
}: SceneChangeHistoryProps) {
  // Limit displayed events
  const displayedEvents = events.slice(0, maxItems);

  // Handle event click
  const handleEventClick = useCallback(
    (event: SceneChangeEventData) => {
      onEventClick?.(event);
    },
    [onEventClick]
  );

  // Handle dismiss
  const handleDismiss = useCallback(
    (eventId: number) => {
      onDismiss?.(eventId);
    },
    [onDismiss]
  );

  // Empty state
  if (displayedEvents.length === 0 && showEmptyState) {
    return (
      <div
        className={clsx(
          'flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gray-900/30 p-8 text-center',
          className
        )}
        data-testid="scene-change-history-empty"
      >
        <div className="rounded-full bg-green-500/10 p-3 mb-3">
          <CheckCircle className="h-6 w-6 text-green-400" aria-hidden="true" />
        </div>
        <p className="text-sm text-gray-400">{emptyMessage}</p>
        <p className="text-xs text-gray-500 mt-1">
          Scene changes will appear here when detected
        </p>
      </div>
    );
  }

  return (
    <div
      className={clsx('space-y-2', className)}
      data-testid="scene-change-history"
      role="list"
      aria-label="Recent scene changes"
    >
      {displayedEvents.map((event) => (
        <SceneChangeItem
          key={event.id}
          event={event}
          onClick={onEventClick ? () => handleEventClick(event) : undefined}
          onDismiss={onDismiss ? () => handleDismiss(event.id) : undefined}
        />
      ))}

      {/* More events indicator */}
      {events.length > maxItems && (
        <div className="text-center py-2">
          <span className="text-xs text-gray-500">
            <Clock className="inline-block h-3 w-3 mr-1" aria-hidden="true" />
            {events.length - maxItems} more scene changes
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * Memoized SceneChangeHistory for performance
 */
export const SceneChangeHistory = memo(SceneChangeHistoryComponent);

export default SceneChangeHistory;
