import { clsx } from 'clsx';

import Skeleton from '../Skeleton';

export interface AlertCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * AlertCardSkeleton component - Loading placeholder matching AlertCard layout
 * Uses shimmer animation for smooth loading experience
 */
export default function AlertCardSkeleton({ className }: AlertCardSkeletonProps) {
  return (
    <article
      className={clsx('relative rounded-lg border-2 border-gray-700 bg-[#1F1F1F] p-4', className)}
      data-testid="alert-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Severity accent bar */}
      <div className="absolute left-0 top-0 h-full w-1 rounded-l-md bg-gray-600" />

      <div className="ml-2">
        {/* Header with status badge */}
        <div className="mb-2 flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              {/* Camera name */}
              <Skeleton variant="text" width={150} height={22} animation="shimmer" />
              {/* Status badge */}
              <Skeleton
                variant="rectangular"
                width={100}
                height={22}
                animation="shimmer"
                className="rounded-full"
              />
            </div>
            {/* Timestamp */}
            <div className="mt-1 flex items-center gap-2">
              <Skeleton variant="circular" width={14} height={14} animation="shimmer" />
              <Skeleton variant="text" width={100} height={14} animation="shimmer" />
            </div>
          </div>
          {/* Risk badge */}
          <Skeleton
            variant="rectangular"
            width={60}
            height={26}
            animation="shimmer"
            className="rounded-full"
          />
        </div>

        {/* Alert summary */}
        <div className="mb-4">
          <Skeleton variant="text" lines={2} height={16} animation="shimmer" />
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Skeleton
            variant="rectangular"
            width={110}
            height={32}
            animation="shimmer"
            className="rounded-md"
          />
          <Skeleton
            variant="rectangular"
            width={80}
            height={32}
            animation="shimmer"
            className="rounded-md"
          />
          <Skeleton
            variant="rectangular"
            width={100}
            height={32}
            animation="shimmer"
            className="rounded-md"
          />
        </div>
      </div>
    </article>
  );
}
