import { clsx } from 'clsx';

import Skeleton from '../Skeleton';

export interface StatsCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * StatsCardSkeleton component - Loading placeholder matching stat card layout
 * Uses shimmer animation for smooth loading experience
 */
export default function StatsCardSkeleton({ className }: StatsCardSkeletonProps) {
  return (
    <div
      className={clsx(
        'flex items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 shadow-sm',
        className
      )}
      data-testid="stats-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Icon */}
      <Skeleton
        variant="rectangular"
        width={48}
        height={48}
        animation="shimmer"
        className="rounded-lg"
        data-testid="stats-card-skeleton-icon"
      />

      {/* Text content */}
      <div className="flex flex-1 flex-col gap-2">
        {/* Value */}
        <Skeleton
          variant="text"
          width={50}
          height={28}
          animation="shimmer"
          data-testid="stats-card-skeleton-value"
        />
        {/* Label */}
        <Skeleton
          variant="text"
          width={100}
          height={16}
          animation="shimmer"
          data-testid="stats-card-skeleton-label"
        />
      </div>
    </div>
  );
}
