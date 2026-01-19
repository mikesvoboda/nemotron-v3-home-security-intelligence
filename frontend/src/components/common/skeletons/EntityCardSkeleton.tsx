import { clsx } from 'clsx';

import Skeleton from '../Skeleton';

export interface EntityCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * EntityCardSkeleton component - Loading placeholder matching EntityCard layout
 * Uses shimmer animation for smooth loading experience
 */
export default function EntityCardSkeleton({ className }: EntityCardSkeletonProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 shadow-lg',
        className
      )}
      data-testid="entity-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Header: Entity type badge and ID */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Entity type badge */}
          <Skeleton
            variant="rectangular"
            width={70}
            height={26}
            animation="shimmer"
            className="rounded-full"
          />
        </div>
        {/* Entity ID */}
        <Skeleton variant="text" width={80} height={14} animation="shimmer" />
      </div>

      {/* Thumbnail area */}
      <div className="mb-3">
        <Skeleton
          variant="rectangular"
          width="100%"
          height={128}
          animation="shimmer"
          className="rounded-md"
        />
      </div>

      {/* Stats: Appearances and Cameras */}
      <div className="mb-3 flex items-center justify-around">
        {/* Appearances */}
        <div className="flex flex-col items-center gap-1">
          <Skeleton variant="text" width={40} height={24} animation="shimmer" />
          <Skeleton variant="text" width={70} height={12} animation="shimmer" />
        </div>

        {/* Divider */}
        <div className="h-8 w-px bg-gray-700" aria-hidden="true" />

        {/* Cameras */}
        <div className="flex flex-col items-center gap-1">
          <Skeleton variant="text" width={30} height={24} animation="shimmer" />
          <Skeleton variant="text" width={50} height={12} animation="shimmer" />
        </div>
      </div>

      {/* Timestamps */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5">
          <Skeleton variant="circular" width={14} height={14} animation="shimmer" />
          <Skeleton variant="text" width={120} height={14} animation="shimmer" />
        </div>
        <div className="flex items-center gap-1.5">
          <Skeleton variant="circular" width={14} height={14} animation="shimmer" />
          <Skeleton variant="text" width={140} height={14} animation="shimmer" />
        </div>
      </div>
    </div>
  );
}
