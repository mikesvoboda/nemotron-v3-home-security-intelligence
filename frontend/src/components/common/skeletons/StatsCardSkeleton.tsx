import { clsx } from 'clsx';

export interface StatsCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * StatsCardSkeleton component - Loading placeholder matching stat card layout
 */
export default function StatsCardSkeleton({ className }: StatsCardSkeletonProps) {
  return (
    <div
      className={clsx(
        'flex items-center gap-4 rounded-lg border border-gray-800 bg-card p-4',
        className
      )}
      data-testid="stats-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Icon */}
      <div
        className="h-10 w-10 animate-pulse rounded-full bg-gray-800"
        data-testid="stats-card-skeleton-icon"
      />

      {/* Text content */}
      <div className="flex flex-1 flex-col gap-2">
        {/* Label */}
        <div
          className="h-3 w-20 animate-pulse rounded bg-gray-800"
          data-testid="stats-card-skeleton-label"
        />
        {/* Value */}
        <div
          className="h-7 w-16 animate-pulse rounded bg-gray-800"
          data-testid="stats-card-skeleton-value"
        />
      </div>
    </div>
  );
}
