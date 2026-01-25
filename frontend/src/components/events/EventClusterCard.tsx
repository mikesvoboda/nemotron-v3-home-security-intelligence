/**
 * EventClusterCard component
 *
 * Displays a cluster of related events from the same camera within a time window.
 * Shows camera name, event count, time range, highest risk level, and thumbnail strip.
 * Can be expanded to view individual events.
 *
 * @module EventClusterCard
 */

import { format, parseISO } from 'date-fns';
import { ChevronDown, ChevronUp, Layers } from 'lucide-react';
import { useState, useCallback } from 'react';

import RiskBadge from '../common/RiskBadge';

import type { EventCluster } from '../../utils/eventClustering';

export interface EventClusterCardProps {
  /** The cluster to display */
  cluster: EventCluster;
  /** Callback when an individual event is clicked */
  onEventClick?: (eventId: number) => void;
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
 * EventClusterCard displays a cluster of related events
 */
export default function EventClusterCard({
  cluster,
  onEventClick,
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

        {/* Thumbnail Strip - Simple inline rendering */}
        {thumbnails.length > 0 && (
          <div className="mb-3 flex gap-1 overflow-hidden rounded-md">
            {thumbnails.slice(0, 5).map((url, index) => (
              <div key={index} className="relative h-16 w-16 flex-shrink-0 overflow-hidden rounded">
                <img
                  src={url}
                  alt={`Event thumbnail ${index + 1}`}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>
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

        {/* Expand/Collapse Button */}
        <button
          onClick={handleToggleExpand}
          className="flex w-full items-center justify-center gap-2 rounded-md border border-gray-700 bg-[#1A1A1A] py-2 text-sm text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525]"
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
