/**
 * EventStatsPanel component displays aggregated event statistics.
 *
 * Shows total events, events by risk level, and a mini risk distribution chart.
 * Uses server-side statistics for accuracy instead of local calculations.
 */

import { clsx } from 'clsx';

import RiskDistributionMini from '../charts/RiskDistributionMini';
import Skeleton from '../common/Skeleton';

import type { EventStatsResponse } from '../../types/generated';

/**
 * Props for the EventStatsPanel component.
 */
export interface EventStatsPanelProps {
  /** Event statistics data from the API */
  stats?: EventStatsResponse;
  /** Whether the data is loading */
  isLoading: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format a number with commas for display.
 * @param num - Number to format
 * @returns Formatted string (e.g., "1,234")
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Color mapping for risk levels.
 */
const riskColors: Record<string, string> = {
  critical: 'text-red-500',
  high: 'text-orange-500',
  medium: 'text-yellow-500',
  low: 'text-green-500',
};

/**
 * StatCard component for displaying a single statistic.
 */
interface StatCardProps {
  label: string;
  value: number;
  color?: string;
  testId?: string;
}

function StatCard({ label, value, color, testId }: StatCardProps) {
  return (
    <div className="flex flex-col items-center justify-center p-2" data-testid={testId}>
      <span className={clsx('text-2xl font-bold', color || 'text-white')}>
        {formatNumber(value)}
      </span>
      <span className="text-xs text-gray-400">{label}</span>
    </div>
  );
}

/**
 * EventStatsPanel displays aggregated event statistics in a compact panel.
 *
 * Shows:
 * - Total events count
 * - Events by risk level (critical, high, medium, low)
 * - Mini risk distribution chart
 *
 * @param props - Component props
 * @returns JSX element or null if no data and not loading
 *
 * @example
 * ```tsx
 * <EventStatsPanel
 *   stats={eventStats}
 *   isLoading={isLoading}
 *   className="mb-4"
 * />
 * ```
 */
export default function EventStatsPanel({
  stats,
  isLoading,
  className,
}: EventStatsPanelProps) {
  // Show skeleton while loading
  if (isLoading) {
    return <EventStatsPanelSkeleton className={className} />;
  }

  // Don't render if no data or incomplete data
  if (!stats || !stats.events_by_risk_level) {
    return null;
  }

  const { total_events, events_by_risk_level, risk_distribution } = stats;

  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-800 bg-[#1F1F1F] p-4',
        className
      )}
      data-testid="event-stats-panel"
    >
      <div
        className="grid grid-cols-2 gap-4 md:grid-cols-5"
        data-testid="stats-grid"
      >
        {/* Total Events */}
        <StatCard
          label="Total Events"
          value={total_events}
          testId="stat-total"
        />

        {/* Critical */}
        <StatCard
          label="Critical"
          value={events_by_risk_level.critical}
          color={riskColors.critical}
          testId="stat-critical"
        />

        {/* High */}
        <StatCard
          label="High"
          value={events_by_risk_level.high}
          color={riskColors.high}
          testId="stat-high"
        />

        {/* Medium */}
        <StatCard
          label="Medium"
          value={events_by_risk_level.medium}
          color={riskColors.medium}
          testId="stat-medium"
        />

        {/* Low */}
        <StatCard
          label="Low"
          value={events_by_risk_level.low}
          color={riskColors.low}
          testId="stat-low"
        />
      </div>

      {/* Risk Distribution Mini Chart */}
      <RiskDistributionMini
        distribution={risk_distribution}
        className="mt-4"
      />
    </div>
  );
}

/**
 * Skeleton loading state for EventStatsPanel.
 */
export interface EventStatsPanelSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

export function EventStatsPanelSkeleton({ className }: EventStatsPanelSkeletonProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-800 bg-[#1F1F1F] p-4',
        className
      )}
      data-testid="event-stats-panel-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        {/* Render 5 skeleton stat cards */}
        {Array.from({ length: 5 }).map((_, index) => (
          <div
            key={index}
            className="flex flex-col items-center justify-center gap-2 p-2"
            data-testid="stats-card-skeleton"
          >
            <Skeleton
              variant="text"
              width={60}
              height={32}
              animation="shimmer"
            />
            <Skeleton
              variant="text"
              width={80}
              height={16}
              animation="shimmer"
            />
          </div>
        ))}
      </div>

      {/* Skeleton for distribution chart */}
      <div className="mt-4">
        <Skeleton
          variant="rectangular"
          width="100%"
          height={24}
          animation="shimmer"
        />
      </div>
    </div>
  );
}
