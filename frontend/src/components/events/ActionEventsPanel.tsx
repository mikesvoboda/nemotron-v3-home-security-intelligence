/**
 * ActionEventsPanel - Displays X-CLIP action recognition results for an event
 *
 * Shows detected actions from the X-CLIP model including action type,
 * confidence scores, timestamps, and suspicious action indicators.
 * Used in EventDetailModal to surface action recognition results.
 *
 * @module components/events/ActionEventsPanel
 * @see backend/api/routes/action_events.py
 * Linear issue: NEM-5024 (Phase 7)
 */

import {
  Activity,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Clock,
  Filter,
  Loader2,
  RefreshCw,
  Video,
  XCircle,
} from 'lucide-react';
import { useState, useMemo } from 'react';

import { useActionEventsForEventQuery } from '../../hooks/useActionEventsQuery';
import { type ActionEvent } from '../../services/actionEventsApi';

// ============================================================================
// Types
// ============================================================================

export interface ActionEventsPanelProps {
  /** Security event ID */
  eventId: number;
  /** Camera ID for the event */
  cameraId: string;
  /** Event start time (ISO format) */
  startTime: string;
  /** Event end time (ISO format), optional for ongoing events */
  endTime?: string | null;
  /** Optional CSS class name */
  className?: string;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Format confidence score as percentage with color coding
 */
function ConfidenceBadge({ score }: { score: number }) {
  const percent = Math.round(score * 100);

  // Color coding based on confidence
  let colorClass: string;
  if (score >= 0.9) {
    colorClass = 'bg-green-900/40 text-green-400 border-green-700';
  } else if (score >= 0.75) {
    colorClass = 'bg-[#76B900]/20 text-[#76B900] border-[#76B900]/50';
  } else if (score >= 0.5) {
    colorClass = 'bg-yellow-900/40 text-yellow-400 border-yellow-700';
  } else {
    colorClass = 'bg-gray-900/40 text-gray-400 border-gray-700';
  }

  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${colorClass}`}
      title={`${percent}% confidence`}
    >
      {percent}%
    </span>
  );
}

/**
 * Badge for suspicious action indicator
 */
function SuspiciousBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border border-red-700 bg-red-900/40 px-2 py-0.5 text-xs font-semibold text-red-400"
      title="Suspicious action detected"
    >
      <AlertTriangle className="h-3 w-3" />
      Suspicious
    </span>
  );
}

/**
 * Format timestamp to relative or absolute time
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    });
  } catch {
    return isoString;
  }
}

/**
 * Get action display name (capitalize first letter)
 */
function formatActionName(action: string): string {
  return action.charAt(0).toUpperCase() + action.slice(1);
}

/**
 * Single action event item display
 */
function ActionEventItem({
  event,
  showAllScores,
  onToggleScores,
}: {
  event: ActionEvent;
  showAllScores: boolean;
  onToggleScores: () => void;
}) {
  const hasAllScores = event.all_scores && Object.keys(event.all_scores).length > 1;

  // Sort all_scores by confidence descending
  const sortedScores = useMemo(() => {
    if (!event.all_scores) return [];
    return Object.entries(event.all_scores)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5); // Show top 5 scores
  }, [event.all_scores]);

  return (
    <div className="border-b border-gray-800 px-4 py-3 last:border-b-0">
      {/* Main action info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 flex-shrink-0 text-[#76B900]" />
          <span className="font-medium text-white">{formatActionName(event.action)}</span>
          <ConfidenceBadge score={event.confidence} />
          {event.is_suspicious && <SuspiciousBadge />}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Clock className="h-3 w-3" />
          <span>{formatTimestamp(event.timestamp)}</span>
        </div>
      </div>

      {/* Frame count info */}
      <div className="mt-1 flex items-center gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <Video className="h-3 w-3" />
          {event.frame_count} frames analyzed
        </span>
        {event.track_id && (
          <span className="text-gray-600">Track #{event.track_id}</span>
        )}
      </div>

      {/* Expandable all_scores section */}
      {hasAllScores && (
        <div className="mt-2">
          <button
            onClick={onToggleScores}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white"
            aria-expanded={showAllScores}
            aria-label={showAllScores ? 'Hide all scores' : 'Show all scores'}
          >
            {showAllScores ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            {showAllScores ? 'Hide' : 'Show'} all scores
          </button>

          {showAllScores && (
            <div className="mt-2 grid grid-cols-2 gap-1 rounded-md bg-black/30 p-2">
              {sortedScores.map(([action, score]) => (
                <div
                  key={action}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="truncate text-gray-400">{formatActionName(action)}</span>
                  <span className="font-mono text-gray-300">{Math.round(score * 100)}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ActionEventsPanel - Main component
 *
 * Displays action recognition results for a security event with filtering
 * by action type and expandable score details.
 */
export default function ActionEventsPanel({
  eventId,
  cameraId,
  startTime,
  endTime,
  className = '',
}: ActionEventsPanelProps) {
  // State for action type filter
  const [actionFilter, setActionFilter] = useState<string>('all');
  // State for showing/hiding all_scores per event
  const [expandedEventIds, setExpandedEventIds] = useState<Set<number>>(new Set());

  // Fetch action events for this event
  const { actionEvents, isLoading, error, refetch, totalCount } = useActionEventsForEventQuery({
    eventId,
    cameraId,
    startTime,
    endTime,
  });

  // Filter events by action type
  const filteredEvents = useMemo(() => {
    if (actionFilter === 'all') return actionEvents;
    if (actionFilter === 'suspicious') return actionEvents.filter((e) => e.is_suspicious);
    return actionEvents.filter((e) => e.action === actionFilter);
  }, [actionEvents, actionFilter]);

  // Get unique action types from events
  const availableActions = useMemo(() => {
    const actions = new Set(actionEvents.map((e) => e.action));
    return Array.from(actions).sort();
  }, [actionEvents]);

  // Count suspicious events
  const suspiciousCount = useMemo(
    () => actionEvents.filter((e) => e.is_suspicious).length,
    [actionEvents]
  );

  // Toggle expanded state for an event
  const toggleExpandedEvent = (eventId: number) => {
    setExpandedEventIds((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) {
        next.delete(eventId);
      } else {
        next.add(eventId);
      }
      return next;
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="action-events-loading"
      >
        <div className="flex items-center gap-3 text-gray-400">
          <Loader2 className="h-5 w-5 animate-spin text-[#76B900]" />
          <span className="text-sm">Loading action events...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className={`rounded-lg border border-red-900/50 bg-red-900/10 p-4 ${className}`}
        data-testid="action-events-error"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-red-400">
            <XCircle className="h-5 w-5" />
            <span className="text-sm">{error.message || 'Failed to load action events'}</span>
          </div>
          <button
            onClick={() => void refetch()}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
            aria-label="Retry"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  // Empty state - no action events found
  if (actionEvents.length === 0) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
        data-testid="action-events-empty"
      >
        <div className="flex items-center gap-2 text-gray-500">
          <Activity className="h-5 w-5" />
          <span className="text-sm">No action recognition events for this detection</span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] ${className}`}
      data-testid="action-events-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-[#76B900]" />
          <h3 className="text-sm font-semibold text-white">Action Recognition</h3>
          {suspiciousCount > 0 && (
            <span className="rounded-full bg-red-900/40 px-2 py-0.5 text-xs font-semibold text-red-400">
              {suspiciousCount} suspicious
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {totalCount} {totalCount === 1 ? 'action' : 'actions'}
          </span>
          <button
            onClick={() => void refetch()}
            className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
            aria-label="Refresh action events"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Filter bar */}
      {availableActions.length > 1 && (
        <div className="flex items-center gap-2 border-b border-gray-800 px-4 py-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="rounded border border-gray-700 bg-black/30 px-2 py-1 text-xs text-white focus:border-[#76B900] focus:outline-none"
            aria-label="Filter by action type"
          >
            <option value="all">All actions ({actionEvents.length})</option>
            {suspiciousCount > 0 && (
              <option value="suspicious">Suspicious only ({suspiciousCount})</option>
            )}
            {availableActions.map((action) => (
              <option key={action} value={action}>
                {formatActionName(action)} ({actionEvents.filter((e) => e.action === action).length}
                )
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Action events list */}
      <div className="max-h-[350px] overflow-y-auto">
        {filteredEvents.length === 0 ? (
          <div className="p-4 text-center text-sm text-gray-500">
            No {actionFilter === 'suspicious' ? 'suspicious ' : ''}actions matching filter
          </div>
        ) : (
          filteredEvents.map((event) => (
            <ActionEventItem
              key={event.id}
              event={event}
              showAllScores={expandedEventIds.has(event.id)}
              onToggleScores={() => toggleExpandedEvent(event.id)}
            />
          ))
        )}
      </div>

      {/* Footer with X-CLIP info */}
      <div className="border-t border-gray-800 bg-black/20 px-4 py-2">
        <p className="text-xs text-gray-500">
          Actions detected by X-CLIP video analysis model
        </p>
      </div>
    </div>
  );
}
