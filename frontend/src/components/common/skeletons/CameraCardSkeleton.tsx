import { clsx } from 'clsx';

export interface CameraCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * CameraCardSkeleton component - Loading placeholder matching CameraCard layout
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
      <div
        className="relative aspect-video w-full animate-pulse bg-gray-800"
        data-testid="camera-card-skeleton-thumbnail"
      >
        {/* Status indicator badge */}
        <div
          className="absolute right-2 top-2 flex items-center gap-1.5 rounded-full bg-black/80 px-2 py-1"
          data-testid="camera-card-skeleton-status"
        >
          <div className="h-2 w-2 animate-pulse rounded-full bg-gray-700" />
          <div className="h-3 w-12 animate-pulse rounded bg-gray-700" />
        </div>
      </div>

      {/* Camera name footer */}
      <div className="flex items-center justify-between border-t border-gray-800 bg-gray-900/50 px-3 py-2">
        <div
          className="h-4 w-24 animate-pulse rounded bg-gray-800"
          data-testid="camera-card-skeleton-name"
        />
        <div className="h-3 w-12 animate-pulse rounded bg-gray-800" />
      </div>
    </div>
  );
}
