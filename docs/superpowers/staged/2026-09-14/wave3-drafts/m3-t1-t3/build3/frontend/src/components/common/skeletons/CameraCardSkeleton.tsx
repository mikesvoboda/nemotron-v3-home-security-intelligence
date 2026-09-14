import { clsx } from 'clsx';

import Skeleton from '../Skeleton';

export interface CameraCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * CameraCardSkeleton component - Loading placeholder matching CameraCard layout
 * Uses shimmer animation for smooth loading experience
 */
export default function CameraCardSkeleton({ className }: CameraCardSkeletonProps) {
  return (
    <div
      className={clsx(
        'relative flex w-full flex-col overflow-hidden rounded-lg border border-gray-800 bg-card',
        className
      )}
      data-testid="camera-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Thumbnail area */}
      <div className="relative aspect-video w-full" data-testid="camera-card-skeleton-thumbnail">
        <Skeleton variant="rectangular" width="100%" height="100%" animation="shimmer" />
        {/* Status indicator badge */}
        <div
          className="absolute right-2 top-2 flex items-center gap-1.5 rounded-full bg-black/80 px-2 py-1"
          data-testid="camera-card-skeleton-status"
        >
          <Skeleton variant="circular" width={8} height={8} animation="shimmer" />
          <Skeleton variant="text" width={48} height={12} animation="shimmer" />
        </div>
      </div>

      {/* Camera name footer */}
      <div className="flex items-center justify-between border-t border-gray-800 bg-gray-900/50 px-3 py-2">
        <Skeleton
          variant="text"
          width={96}
          height={16}
          animation="shimmer"
          data-testid="camera-card-skeleton-name"
        />
        <Skeleton variant="text" width={48} height={12} animation="shimmer" />
      </div>
    </div>
  );
}
