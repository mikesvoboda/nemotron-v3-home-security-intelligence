import { clsx } from 'clsx';

import Skeleton from '../Skeleton';

export interface EventCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * EventCardSkeleton component - Loading placeholder matching EventCard layout
 * Uses shimmer animation for smooth loading experience
 */
export default function EventCardSkeleton({ className }: EventCardSkeletonProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border border-l-4 border-gray-800 border-l-gray-700 bg-[#1F1F1F] p-4 shadow-lg',
        className
      )}
      data-testid="event-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Main Layout: Thumbnail on left, content on right */}
      <div className="flex gap-4">
        {/* Thumbnail Column (64x64) */}
        <div className="flex-shrink-0">
          <Skeleton
            variant="rectangular"
            width={64}
            height={64}
            animation="shimmer"
            className="rounded-md"
          />
        </div>

        {/* Content Column */}
        <div className="min-w-0 flex-1">
          {/* Header */}
          <div
            className="mb-3 flex items-start justify-between"
            data-testid="event-card-skeleton-header"
          >
            <div className="min-w-0 flex-1">
              <Skeleton variant="text" width={140} height={20} animation="shimmer" />
              <div className="mt-2 flex items-center gap-1.5">
                <Skeleton variant="circular" width={14} height={14} animation="shimmer" />
                <Skeleton variant="text" width={100} height={16} animation="shimmer" />
              </div>
            </div>
            <Skeleton
              variant="rectangular"
              width={70}
              height={28}
              animation="shimmer"
              className="rounded-full"
            />
          </div>

          {/* Object Type Badges */}
          <div className="mb-3 flex flex-wrap gap-1.5">
            <Skeleton
              variant="rectangular"
              width={60}
              height={24}
              animation="shimmer"
              className="rounded-full"
            />
            <Skeleton
              variant="rectangular"
              width={50}
              height={24}
              animation="shimmer"
              className="rounded-full"
            />
          </div>

          {/* Risk Score Progress Bar */}
          <div className="mb-3">
            <div className="mb-1.5 flex items-center justify-between">
              <Skeleton variant="text" width={70} height={12} animation="shimmer" />
              <Skeleton variant="text" width={40} height={12} animation="shimmer" />
            </div>
            <Skeleton
              variant="rectangular"
              width="100%"
              height={8}
              animation="shimmer"
              className="rounded-full"
            />
          </div>

          {/* Summary text */}
          <div className="mb-3" data-testid="event-card-skeleton-summary">
            <Skeleton variant="text" lines={2} height={16} animation="shimmer" />
          </div>

          {/* Detections */}
          <div className="rounded-md bg-black/30 p-3" data-testid="event-card-skeleton-detections">
            <div className="mb-2 flex items-center justify-between">
              <Skeleton variant="text" width={80} height={12} animation="shimmer" />
              <Skeleton variant="text" width={100} height={12} animation="shimmer" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Skeleton
                variant="rectangular"
                width={85}
                height={28}
                animation="shimmer"
                className="rounded-full"
              />
              <Skeleton
                variant="rectangular"
                width={75}
                height={28}
                animation="shimmer"
                className="rounded-full"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
