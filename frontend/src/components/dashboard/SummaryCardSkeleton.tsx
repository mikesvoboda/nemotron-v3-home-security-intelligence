/**
 * SummaryCardSkeleton - Loading placeholder for summary cards.
 *
 * Displays an animated skeleton placeholder matching the SummaryCard layout
 * while summary data is being fetched. Uses shimmer animation for visual feedback.
 *
 * @see SummaryCards.tsx - Parent component that uses this skeleton
 * @see NEM-2928
 */

import { Card, Flex, Title } from '@tremor/react';
import { clsx } from 'clsx';
import { Calendar, Clock } from 'lucide-react';

import type { SummaryType } from '@/types/summary';

/**
 * Props for the SummaryCardSkeleton component.
 */
export interface SummaryCardSkeletonProps {
  /** Type of summary: 'hourly' or 'daily' - determines icon and title */
  type: SummaryType;
  /** Whether to show status text below the skeleton content */
  showStatusText?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Shimmer overlay component for skeleton animations.
 * Creates a gradient that moves across the element.
 */
function ShimmerOverlay() {
  return (
    <div
      className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-gray-700/50 to-transparent"
      aria-hidden="true"
    />
  );
}

/**
 * SummaryCardSkeleton provides a loading placeholder that matches the layout
 * of the actual SummaryCard component.
 *
 * Features:
 * - Animated shimmer effect for visual loading feedback
 * - Matches card structure (header with icon/title, badge area, content, footer)
 * - Accessible with role="status" and aria-label
 * - Dark theme styling consistent with NVIDIA design system
 *
 * @example
 * ```tsx
 * // Basic usage
 * <SummaryCardSkeleton type="hourly" />
 *
 * // With status text
 * <SummaryCardSkeleton type="daily" showStatusText />
 *
 * // With custom class
 * <SummaryCardSkeleton type="hourly" className="mb-4" />
 * ```
 */
export function SummaryCardSkeleton({
  type,
  showStatusText = false,
  className,
}: SummaryCardSkeletonProps) {
  const isHourly = type === 'hourly';
  const title = isHourly ? 'Hourly Summary' : 'Daily Summary';
  const Icon = isHourly ? Clock : Calendar;

  return (
    <Card
      className={clsx('mb-4 border-l-4 border-gray-800 bg-[#1A1A1A]', className)}
      style={{ borderLeftColor: '#d1d5db' }} // gray-300 - neutral loading state
      data-testid={`summary-card-skeleton-${type}`}
      role="status"
      aria-label={`Loading ${type} summary`}
    >
      {/* Header */}
      <Flex justifyContent="between" alignItems="center" className="mb-3">
        <Flex justifyContent="start" className="gap-2">
          <Icon className="h-5 w-5 text-gray-500" aria-hidden="true" />
          <Title className="text-white">{title}</Title>
        </Flex>

        {/* Badge skeleton */}
        <div
          className="relative h-6 w-20 overflow-hidden rounded-full bg-gray-800"
          data-testid={`summary-card-skeleton-badge-${type}`}
        >
          <ShimmerOverlay />
        </div>
      </Flex>

      {/* Content skeleton - two lines of text */}
      <div className="space-y-2" data-testid={`summary-card-skeleton-content-${type}`}>
        <div className="relative h-4 w-full overflow-hidden rounded bg-gray-800">
          <ShimmerOverlay />
        </div>
        <div className="relative h-4 w-3/4 overflow-hidden rounded bg-gray-800">
          <ShimmerOverlay />
        </div>
      </div>

      {/* Footer skeleton - timestamp */}
      <div
        className="relative mt-3 h-3 w-32 overflow-hidden rounded bg-gray-800"
        data-testid={`summary-card-skeleton-footer-${type}`}
      >
        <ShimmerOverlay />
      </div>

      {/* Optional status text */}
      {showStatusText && (
        <p className="mt-3 text-sm text-gray-500" data-testid={`summary-card-skeleton-status-${type}`}>
          Loading summary data...
        </p>
      )}
    </Card>
  );
}

export default SummaryCardSkeleton;
