/**
 * EventClusterCard component
 *
 * Displays a cluster of related events from the same camera within a time window.
 * Shows camera name, event count, time range, highest risk level, and thumbnail strip.
 * Can be expanded to view individual events.
 * Supports bulk actions like marking all events as reviewed.
 *
 * @module EventClusterCard
 */

import { format, parseISO } from 'date-fns';
import { CheckSquare, ChevronDown, ChevronUp, Layers } from 'lucide-react';
import { useState, useCallback, useMemo } from 'react';

import { getRiskLevel, type RiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';

import type { EventCluster } from '../../utils/eventClustering';

/** Maximum number of thumbnails to display in the grid */
const MAX_THUMBNAILS_DISPLAY = 6;

export interface EventClusterCardProps {
  /** The cluster to display */
  cluster: EventCluster;
  /** Callback when an individual event is clicked */
  onEventClick?: (eventId: number) => void;
  /** Callback when bulk mark as reviewed is clicked */
  onBulkMarkReviewed?: (eventIds: number[]) => void;
  /** Whether a bulk action is in progress */
  bulkActionLoading?: boolean;
  /** Whether the card has a checkbox overlay (affects top padding) */
  hasCheckboxOverlay?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format a timestamp for display
 */
function formatTime(timestamp: string): string {
  try {
    return format(parseISO(timestamp), 'HH:mm');
  } catch {
    return '--:--';
  }
}

/**
 * Format a timestamp for display with date
 */
function formatDateTime(timestamp: string): string {
  try {
    return format(parseISO(timestamp), 'MMM d, HH:mm');
  } catch {
    return 'Unknown time';
  }
}

/**
 * Get the border color class based on risk level
 */
function getRiskBorderClass(riskLevel: string): string {
  switch (riskLevel) {
    case 'critical':
      return 'border-l-risk-critical';
    case 'high':
      return 'border-l-risk-high';
    case 'medium':
      return 'border-l-risk-medium';
    case 'low':
      return 'border-l-risk-low';
    default:
      return 'border-l-gray-600';
  }
}

/**
 * Risk level counts for cluster statistics
 */
interface RiskLevelCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

/**
 * EventClusterCard displays a cluster of related events
 */
export default function EventClusterCard({
  cluster,
  onEventClick,
  onBulkMarkReviewed,
  bulkActionLoading = false,
  hasCheckboxOverlay = false,
  className = '',
}: EventClusterCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleToggleExpand = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  const handleEventClick = useCallback(
    (eventId: number) => {
      onEventClick?.(eventId);
    },
    [onEventClick]
  );

  const handleBulkMarkReviewed = useCallback(() => {
    if (onBulkMarkReviewed && cluster.events.length > 0) {
      const eventIds = cluster.events.map((e) => e.id);
      onBulkMarkReviewed(eventIds);
    }
  }, [onBulkMarkReviewed, cluster.events]);

  const {
    cameraName,
    eventCount,
    startTime,
    endTime,
    highestRiskScore,
    highestRiskLevel,
    thumbnails,
    events,
  } = cluster;

  const displayCameraName = cameraName || 'Unknown Camera';

  // Calculate risk level breakdown from events
  const riskLevelCounts = useMemo<RiskLevelCounts>(() => {
    const counts: RiskLevelCounts = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const event of events) {
      const level = event.risk_level || getRiskLevel(event.risk_score || 0);
      if (level in counts) {
        counts[level as RiskLevel]++;
      }
    }
    return counts;
  }, [events]);

  // Get unique object types from events (for future use when object_type is available)
  const objectTypes = useMemo(() => {
    const types = new Set<string>();
    for (const event of events) {
      // Check if event has detection data with object types
      // This is a placeholder for when object_type is available on events
      if (event.summary) {
        // Extract common object types from summary text
        const summaryLower = event.summary.toLowerCase();
        if (summaryLower.includes('person')) types.add('person');
        if (summaryLower.includes('vehicle') || summaryLower.includes('car')) types.add('vehicle');
        if (summaryLower.includes('animal') || summaryLower.includes('dog') || summaryLower.includes('cat')) types.add('animal');
        if (summaryLower.includes('package')) types.add('package');
      }
    }
    return Array.from(types);
  }, [events]);

  // Calculate how many unreviewed events are in this cluster
  const unreviewedCount = useMemo(() => {
    return events.filter((e) => !e.reviewed).length;
  }, [events]);

  // Calculate remaining thumbnails count
  const remainingThumbnailCount = thumbnails.length > MAX_THUMBNAILS_DISPLAY
    ? thumbnails.length - MAX_THUMBNAILS_DISPLAY
    : 0;

  return (
    <div
      data-testid="event-cluster-card"
      className={`overflow-hidden rounded-lg border border-gray-800 bg-[#1F1F1F] transition-all hover:border-gray-700 ${getRiskBorderClass(highestRiskLevel)} border-l-4 ${className}`}
    >
      {/* Header Section */}
      <div className={`p-4 ${hasCheckboxOverlay ? 'pt-12' : ''}`}>
        {/* Camera Name and Cluster Icon */}
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#76B900]" />
            <h3 className="font-semibold text-white">{displayCameraName}</h3>
          </div>
          <div className="flex items-center gap-2">
            <RiskBadge level={highestRiskLevel} size="sm" animated={false} />
            <span className="text-lg font-bold text-white">{highestRiskScore}</span>
          </div>
        </div>

        {/* Thumbnail Grid - Shows up to 6 thumbnails with "+N more" indicator */}
        {thumbnails.length > 0 && (
          <div className="mb-3 grid grid-cols-3 gap-1 overflow-hidden rounded-md" data-testid="thumbnail-grid">
            {thumbnails.slice(0, MAX_THUMBNAILS_DISPLAY).map((url, index) => (
              <div key={index} className="relative aspect-square overflow-hidden rounded">
                <img
                  src={url}
                  alt={`Event thumbnail ${index + 1}`}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>
            ))}
            {remainingThumbnailCount > 0 && (
              <div
                className="flex aspect-square items-center justify-center rounded bg-gray-800 text-sm font-medium text-gray-300"
                data-testid="thumbnail-more-indicator"
              >
                +{remainingThumbnailCount} more
              </div>
            )}
          </div>
        )}

        {/* Risk Level Breakdown */}
        <div className="mb-3 flex flex-wrap gap-2" data-testid="risk-breakdown">
          {riskLevelCounts.critical > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400">
              {riskLevelCounts.critical} critical
            </span>
          )}
          {riskLevelCounts.high > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-orange-500/20 px-2 py-0.5 text-xs font-medium text-orange-400">
              {riskLevelCounts.high} high
            </span>
          )}
          {riskLevelCounts.medium > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs font-medium text-yellow-400">
              {riskLevelCounts.medium} medium
            </span>
          )}
          {riskLevelCounts.low > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-400">
              {riskLevelCounts.low} low
            </span>
          )}
        </div>

        {/* Object Types (if detected) */}
        {objectTypes.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-1" data-testid="object-types">
            {objectTypes.map((type) => (
              <span
                key={type}
                className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-300"
              >
                {type}
              </span>
            ))}
          </div>
        )}

        {/* Event Count and Time Range */}
        <div className="mb-3 flex items-center justify-between text-sm">
          <span className="font-medium text-[#76B900]">{eventCount} events</span>
          <span className="text-gray-400">
            {formatTime(startTime)} - {formatTime(endTime)}
          </span>
        </div>

        {/* Action Buttons Row */}
        <div className="flex gap-2">
          {/* Expand/Collapse Button */}
          <button
            onClick={handleToggleExpand}
            className="flex flex-1 items-center justify-center gap-2 rounded-md border border-gray-700 bg-[#1A1A1A] py-2 text-sm text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525]"
            aria-expanded={isExpanded}
            aria-label={isExpanded ? 'Collapse cluster' : 'Expand to view events'}
          >
            {isExpanded ? (
              <>
                <ChevronUp className="h-4 w-4" />
                <span>Hide Events</span>
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4" />
                <span>View Events</span>
              </>
            )}
          </button>

          {/* Bulk Mark as Reviewed Button */}
          {onBulkMarkReviewed && unreviewedCount > 0 && (
            <button
              onClick={handleBulkMarkReviewed}
              disabled={bulkActionLoading}
              className="flex items-center gap-2 rounded-md bg-[#76B900] px-3 py-2 text-sm font-medium text-black transition-colors hover:bg-[#88d200] disabled:cursor-not-allowed disabled:opacity-50"
              aria-label={`Mark all ${unreviewedCount} events as reviewed`}
              data-testid="bulk-mark-reviewed-btn"
            >
              {bulkActionLoading ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-black border-t-transparent" />
              ) : (
                <CheckSquare className="h-4 w-4" />
              )}
              <span>Mark All</span>
            </button>
          )}
        </div>
      </div>

      {/* Expanded Events List */}
      {isExpanded && (
        <div className="border-t border-gray-800 bg-[#1A1A1A]">
          <div className="max-h-80 overflow-y-auto">
            {events.map((event) => (
              <button
                key={event.id}
                onClick={() => handleEventClick(event.id)}
                className="w-full border-b border-gray-800 p-3 text-left transition-colors last:border-b-0 hover:bg-[#252525]"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-white">
                      {event.summary || 'No summary available'}
                    </p>
                    <p className="mt-1 text-xs text-gray-400">{formatDateTime(event.started_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {event.risk_level && (
                      <RiskBadge
                        level={event.risk_level as 'low' | 'medium' | 'high' | 'critical'}
                        size="sm"
                        animated={false}
                      />
                    )}
                    {event.risk_score !== null && (
                      <span className="text-sm font-medium text-gray-300">{event.risk_score}</span>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
