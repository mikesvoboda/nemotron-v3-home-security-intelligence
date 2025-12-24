import { clsx } from 'clsx';
import { Camera, Clock, Pause, Play } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { getRiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';

// ============================================================================
// Types
// ============================================================================

export interface ActivityEvent {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  summary: string;
  thumbnail_url?: string;
}

export interface ActivityFeedProps {
  events: ActivityEvent[];
  maxItems?: number;
  onEventClick?: (eventId: string) => void;
  autoScroll?: boolean;
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * ActivityFeed component displays a scrolling list of recent security events
 * with thumbnails, timestamps, camera names, risk badges, and AI summaries.
 */
export default function ActivityFeed({
  events,
  maxItems = 10,
  onEventClick,
  autoScroll: initialAutoScroll = true,
  className,
}: ActivityFeedProps) {
  const [autoScroll, setAutoScroll] = useState(initialAutoScroll);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const previousEventsLengthRef = useRef(events.length);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && scrollContainerRef.current && events.length > previousEventsLengthRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
    previousEventsLengthRef.current = events.length;
  }, [events, autoScroll]);

  // Limit events to maxItems
  const displayedEvents = maxItems > 0 ? events.slice(-maxItems) : [];

  // Toggle auto-scroll
  const toggleAutoScroll = () => {
    setAutoScroll((prev) => !prev);
  };

  // Format timestamp to human-readable format
  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);

      // Check if date is valid
      if (isNaN(date.getTime())) {
        return timestamp;
      }

      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);

      // Show relative time for recent events
      if (diffMins < 1) return 'Just now';
      if (diffMins === 1) return '1 min ago';
      if (diffMins < 60) return `${diffMins} mins ago`;

      const diffHours = Math.floor(diffMins / 60);
      if (diffHours === 1) return '1 hour ago';
      if (diffHours < 24) return `${diffHours} hours ago`;

      // Show absolute time for older events
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return timestamp;
    }
  };

  // Handle event click
  const handleEventClick = (eventId: string) => {
    if (onEventClick) {
      onEventClick(eventId);
    }
  };

  return (
    <div className={clsx('flex h-full flex-col rounded-lg bg-gray-900 shadow-lg', className)}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <h3 className="text-lg font-semibold text-white">Live Activity</h3>
        <button
          onClick={toggleAutoScroll}
          aria-label={autoScroll ? 'Pause auto-scroll' : 'Resume auto-scroll'}
          className="flex items-center gap-2 rounded-md bg-gray-800 px-3 py-1.5 text-sm text-gray-300 transition-colors hover:bg-gray-700 hover:text-white"
        >
          {autoScroll ? (
            <>
              <Pause className="h-4 w-4" />
              <span>Pause</span>
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              <span>Resume</span>
            </>
          )}
        </button>
      </div>

      {/* Event List */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-4"
        style={{ scrollBehavior: autoScroll ? 'smooth' : 'auto' }}
      >
        {displayedEvents.length === 0 ? (
          /* Empty State */
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Camera className="mb-4 h-16 w-16 text-gray-700" />
            <h4 className="mb-2 text-lg font-medium text-gray-400">No Activity Yet</h4>
            <p className="text-sm text-gray-600">Security events will appear here as they occur.</p>
          </div>
        ) : (
          /* Event Items */
          <div className="space-y-3">
            {displayedEvents.map((event) => {
              const riskLevel = getRiskLevel(event.risk_score);

              return (
                <div
                  key={event.id}
                  onClick={() => handleEventClick(event.id)}
                  className={clsx(
                    'group relative flex cursor-pointer gap-3 rounded-lg border border-gray-800 bg-gray-800/50 p-3 transition-all duration-200',
                    onEventClick && 'hover:border-[#76B900] hover:bg-gray-800'
                  )}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleEventClick(event.id);
                    }
                  }}
                  aria-label={`Event from ${event.camera_name} at ${formatTimestamp(event.timestamp)}, risk level ${riskLevel}`}
                >
                  {/* Thumbnail */}
                  <div className="flex-shrink-0">
                    {event.thumbnail_url ? (
                      <img
                        src={event.thumbnail_url}
                        alt={`Thumbnail for ${event.camera_name}`}
                        className="h-20 w-20 rounded-md bg-gray-900 object-cover"
                        onError={(e) => {
                          // Fallback to placeholder if image fails to load
                          const target = e.target as HTMLImageElement;
                          target.style.display = 'none';
                          target.nextElementSibling?.classList.remove('hidden');
                        }}
                      />
                    ) : null}
                    <div
                      className={clsx(
                        'flex h-20 w-20 items-center justify-center rounded-md bg-gray-900',
                        event.thumbnail_url && 'hidden'
                      )}
                    >
                      <Camera className="h-8 w-8 text-gray-700" />
                    </div>
                  </div>

                  {/* Event Details */}
                  <div className="min-w-0 flex-1">
                    {/* Top Row: Camera Name + Risk Badge */}
                    <div className="mb-1.5 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-sm">
                        <Camera className="h-3.5 w-3.5 text-gray-500" />
                        <span className="font-medium text-white">{event.camera_name}</span>
                      </div>
                      <RiskBadge level={riskLevel} score={event.risk_score} showScore size="sm" />
                    </div>

                    {/* Summary */}
                    <p className="mb-1.5 line-clamp-2 text-sm text-gray-400">{event.summary}</p>

                    {/* Timestamp */}
                    <div className="flex items-center gap-1.5 text-xs text-gray-600">
                      <Clock className="h-3 w-3" />
                      <time dateTime={event.timestamp}>{formatTimestamp(event.timestamp)}</time>
                    </div>
                  </div>

                  {/* Hover Indicator */}
                  {onEventClick && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 opacity-0 transition-opacity group-hover:opacity-100">
                      <div className="h-2 w-2 rounded-full bg-[#76B900]" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      {displayedEvents.length > 0 && (
        <div className="border-t border-gray-800 px-4 py-2">
          <p className="text-center text-xs text-gray-600">
            Showing {displayedEvents.length} of {events.length} events
          </p>
        </div>
      )}
    </div>
  );
}
