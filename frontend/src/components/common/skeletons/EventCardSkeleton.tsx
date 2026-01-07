import { clsx } from 'clsx';

export interface EventCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * EventCardSkeleton component - Loading placeholder matching EventCard layout
 */
export default function EventCardSkeleton({ className }: EventCardSkeletonProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-800 border-l-4 border-l-gray-700 bg-[#1F1F1F] p-4 shadow-lg',
        className
      )}
      data-testid="event-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Header */}
      <div
        className="mb-3 flex items-start justify-between"
        data-testid="event-card-skeleton-header"
      >
        <div className="min-w-0 flex-1">
          <div className="h-5 w-32 animate-pulse rounded bg-gray-800" />
          <div className="mt-2 flex items-center gap-1.5">
            <div className="h-3.5 w-3.5 animate-pulse rounded-full bg-gray-800" />
            <div className="h-4 w-24 animate-pulse rounded bg-gray-800" />
          </div>
        </div>
        <div className="h-7 w-20 animate-pulse rounded-full bg-gray-800" />
      </div>

      {/* Thumbnail */}
      <div
        className="mb-3 aspect-video w-full animate-pulse rounded-md bg-gray-800"
        data-testid="event-card-skeleton-thumbnail"
      />

      {/* Summary text */}
      <div className="mb-3 space-y-2" data-testid="event-card-skeleton-summary">
        <div className="h-4 w-full animate-pulse rounded bg-gray-800" />
        <div className="h-4 w-4/5 animate-pulse rounded bg-gray-800" />
      </div>

      {/* Detections */}
      <div
        className="rounded-md bg-black/30 p-3"
        data-testid="event-card-skeleton-detections"
      >
        <div className="flex flex-wrap gap-2">
          <div className="h-6 w-20 animate-pulse rounded-full bg-gray-800" />
          <div className="h-6 w-24 animate-pulse rounded-full bg-gray-800" />
        </div>
      </div>
    </div>
  );
}
