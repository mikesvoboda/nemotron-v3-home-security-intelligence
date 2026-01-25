import { clsx } from 'clsx';
import { Activity, Circle, Pause, Play, Radio, Signal, Wifi, WifiOff } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { useAnnounce } from '../../hooks/useAnnounce';
import { getRiskLevel, type RiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';
import ActivityFeed, { type ActivityEvent } from '../dashboard/ActivityFeed';

// ============================================================================
// Types
// ============================================================================

export interface LiveActivitySectionProps {
  /** Events to display in the live feed */
  events: ActivityEvent[];
  /** Whether the WebSocket connection is active */
  isConnected: boolean;
  /** Callback when an event is clicked */
  onEventClick?: (eventId: string) => void;
  /** Maximum number of items to display */
  maxItems?: number;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Components
// ============================================================================

interface ConnectionStatusProps {
  isConnected: boolean;
}

function ConnectionStatus({ isConnected }: ConnectionStatusProps) {
  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
        isConnected ? 'bg-[#76B900]/10 text-[#76B900]' : 'bg-yellow-500/10 text-yellow-500'
      )}
      role="status"
      aria-live="polite"
    >
      {isConnected ? (
        <>
          <Wifi className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Live</span>
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#76B900] opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[#76B900]" />
          </span>
        </>
      ) : (
        <>
          <WifiOff className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Disconnected</span>
        </>
      )}
    </div>
  );
}

interface LiveActivityStatsProps {
  events: ActivityEvent[];
}

function LiveActivityStats({ events }: LiveActivityStatsProps) {
  // Count events by risk level
  const riskCounts = events.reduce(
    (acc, event) => {
      const level = getRiskLevel(event.risk_score);
      acc[level] = (acc[level] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  if (events.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-4">
      {/* Total count */}
      <div className="flex items-center gap-1.5 text-sm text-gray-400">
        <Activity className="h-4 w-4" aria-hidden="true" />
        <span className="font-medium text-white">{events.length}</span>
        <span className="hidden sm:inline">recent</span>
      </div>

      {/* Risk breakdown (only on larger screens) */}
      <div className="hidden items-center gap-3 md:flex">
        {riskCounts.critical > 0 && (
          <div className="flex items-center gap-1.5">
            <RiskBadge level="critical" size="sm" animated={false} />
            <span className="text-xs font-semibold text-red-400">{riskCounts.critical}</span>
          </div>
        )}
        {riskCounts.high > 0 && (
          <div className="flex items-center gap-1.5">
            <RiskBadge level="high" size="sm" animated={false} />
            <span className="text-xs font-semibold text-orange-400">{riskCounts.high}</span>
          </div>
        )}
        {riskCounts.medium > 0 && (
          <div className="flex items-center gap-1.5">
            <RiskBadge level="medium" size="sm" animated={false} />
            <span className="text-xs font-semibold text-yellow-400">{riskCounts.medium}</span>
          </div>
        )}
        {riskCounts.low > 0 && (
          <div className="flex items-center gap-1.5">
            <RiskBadge level="low" size="sm" animated={false} />
            <span className="text-xs font-semibold text-green-400">{riskCounts.low}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * LiveActivitySection displays real-time security events with enhanced visual hierarchy.
 *
 * Features:
 * - Connection status indicator with animated pulse
 * - Real-time event count with risk breakdown
 * - Pause/resume auto-scroll functionality
 * - Clear distinction from historical events section
 * - Responsive design for all screen sizes
 * - Dark theme compatible styling
 */
/**
 * Get announcement message for new events
 */
function getEventAnnouncementMessage(
  newCount: number,
  highestRiskLevel: RiskLevel | null
): string {
  if (newCount === 1) {
    if (highestRiskLevel === 'critical' || highestRiskLevel === 'high') {
      return `New ${highestRiskLevel} risk security event detected`;
    }
    return 'New security event detected';
  }

  if (highestRiskLevel === 'critical' || highestRiskLevel === 'high') {
    return `${newCount} new security events, including ${highestRiskLevel} risk`;
  }
  return `${newCount} new security events detected`;
}

export default function LiveActivitySection({
  events,
  isConnected,
  onEventClick,
  maxItems = 10,
  className,
}: LiveActivitySectionProps) {
  const [isPaused, setIsPaused] = useState(false);
  const { announce } = useAnnounce();
  const previousEventCountRef = useRef(events.length);
  const previousEventIdsRef = useRef<Set<string>>(new Set(events.map((e) => e.id)));

  const handleTogglePause = useCallback(() => {
    setIsPaused((prev) => !prev);
  }, []);

  // Announce new events to screen readers
  useEffect(() => {
    // Skip if paused
    if (isPaused) {
      return;
    }

    const currentIds = new Set(events.map((e) => e.id));
    const newEvents = events.filter((e) => !previousEventIdsRef.current.has(e.id));

    // Only announce if there are genuinely new events
    if (newEvents.length > 0) {
      // Find the highest risk level among new events
      let highestRiskLevel: RiskLevel | null = null;
      const riskPriority: Record<RiskLevel, number> = {
        critical: 4,
        high: 3,
        medium: 2,
        low: 1,
      };

      for (const event of newEvents) {
        const level = getRiskLevel(event.risk_score);
        if (!highestRiskLevel || riskPriority[level] > riskPriority[highestRiskLevel]) {
          highestRiskLevel = level;
        }
      }

      const message = getEventAnnouncementMessage(newEvents.length, highestRiskLevel);
      const politeness = highestRiskLevel === 'critical' ? 'assertive' : 'polite';
      announce(message, politeness);
    }

    // Update refs
    previousEventCountRef.current = events.length;
    previousEventIdsRef.current = currentIds;
  }, [events, isPaused, announce]);

  return (
    <section
      className={clsx(
        'rounded-xl border border-gray-800 bg-gradient-to-br from-[#1A1A1A] to-[#1F1F1F]',
        'shadow-lg shadow-black/20',
        className
      )}
      aria-labelledby="live-activity-heading"
    >
      {/* Section Header */}
      <div className="flex flex-col gap-3 border-b border-gray-800 p-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Title and Status */}
        <div className="flex items-center gap-3">
          {/* Animated Icon */}
          <div className="relative flex h-10 w-10 items-center justify-center rounded-lg bg-[#76B900]/10">
            <Radio
              className={clsx(
                'h-5 w-5 text-[#76B900]',
                isConnected && !isPaused && 'animate-pulse'
              )}
              aria-hidden="true"
            />
            {isConnected && !isPaused && (
              <span className="absolute -right-0.5 -top-0.5 flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#76B900] opacity-75" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-[#76B900]" />
              </span>
            )}
          </div>

          {/* Title */}
          <div>
            <h2 id="live-activity-heading" className="text-lg font-semibold text-white sm:text-xl">
              Live Activity
            </h2>
            <p className="text-xs text-gray-500 sm:text-sm">Real-time security event stream</p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          {/* Stats */}
          <LiveActivityStats events={events} />

          {/* Connection Status */}
          <ConnectionStatus isConnected={isConnected} />

          {/* Pause/Resume Button */}
          <button
            onClick={handleTogglePause}
            className={clsx(
              'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all',
              'border border-gray-700 bg-[#1A1A1A] hover:border-gray-600 hover:bg-[#252525]',
              'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]'
            )}
            aria-label={isPaused ? 'Resume live updates' : 'Pause live updates'}
            aria-pressed={isPaused}
          >
            {isPaused ? (
              <>
                <Play className="h-4 w-4 text-[#76B900]" aria-hidden="true" />
                <span className="hidden text-gray-300 sm:inline">Resume</span>
              </>
            ) : (
              <>
                <Pause className="h-4 w-4 text-gray-400" aria-hidden="true" />
                <span className="hidden text-gray-300 sm:inline">Pause</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Activity Feed Content */}
      <div className="relative">
        {/* Paused Overlay */}
        {isPaused && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center rounded-b-xl bg-black/40 backdrop-blur-sm"
            aria-hidden="true"
          >
            <div className="flex items-center gap-2 rounded-lg bg-gray-900/90 px-4 py-2 text-sm text-gray-300">
              <Pause className="h-4 w-4" />
              <span>Updates paused</span>
            </div>
          </div>
        )}

        {/* Empty State */}
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-800">
              <Signal className="h-8 w-8 text-gray-600" aria-hidden="true" />
            </div>
            <h3 className="mb-2 text-lg font-medium text-gray-300">No Live Activity</h3>
            <p className="max-w-sm text-sm text-gray-500">
              {isConnected
                ? 'Waiting for security events. New detections will appear here automatically.'
                : 'Connection lost. Attempting to reconnect...'}
            </p>
            {isConnected && (
              <div className="mt-4 flex items-center gap-2 text-xs text-gray-600">
                <Circle className="h-2 w-2 fill-current" aria-hidden="true" />
                <span>Monitoring active cameras</span>
              </div>
            )}
          </div>
        ) : (
          <ActivityFeed
            events={events}
            maxItems={maxItems}
            autoScroll={!isPaused}
            onEventClick={onEventClick}
            className="max-h-[400px] overflow-y-auto rounded-b-xl"
            showHeader={false}
          />
        )}
      </div>

      {/* Section Footer - Visual separator from historical section */}
      {events.length > 0 && (
        <div className="border-t border-gray-800 bg-black/20 px-4 py-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500">
              Showing {Math.min(events.length, maxItems)} of {events.length} recent events
            </p>
            <div className="flex items-center gap-1.5 text-xs text-gray-600">
              <Circle className="h-1.5 w-1.5 fill-current" aria-hidden="true" />
              <span>Auto-refreshing</span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
