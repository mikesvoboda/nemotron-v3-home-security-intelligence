import { clsx } from 'clsx';

export interface EntityCardSkeletonProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * EntityCardSkeleton component - Loading placeholder matching EntityCard layout
 */
export default function EntityCardSkeleton({ className }: EntityCardSkeletonProps) {
  return (
    <div
      className={clsx(
        'overflow-hidden rounded-lg border border-gray-800 bg-[#1F1F1F] transition-colors',
        className
      )}
      data-testid="entity-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Thumbnail area */}
      <div className="relative aspect-square w-full animate-pulse bg-gray-800">
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-12 w-12 animate-pulse rounded-full bg-gray-700" />
        </div>
        <div className="absolute left-2 top-2">
          <div className="h-6 w-16 animate-pulse rounded-full bg-gray-700" />
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <div className="mb-3 h-5 w-32 animate-pulse rounded bg-gray-800" />
        <div className="mb-3 flex items-center gap-4">
          <div className="flex items-center gap-1">
            <div className="h-4 w-4 animate-pulse rounded bg-gray-800" />
            <div className="h-4 w-16 animate-pulse rounded bg-gray-800" />
          </div>
          <div className="flex items-center gap-1">
            <div className="h-4 w-4 animate-pulse rounded bg-gray-800" />
            <div className="h-4 w-20 animate-pulse rounded bg-gray-800" />
          </div>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-1">
            <div className="h-3 w-3 animate-pulse rounded bg-gray-800" />
            <div className="h-3 w-24 animate-pulse rounded bg-gray-800" />
          </div>
          <div className="flex items-center gap-1">
            <div className="h-3 w-3 animate-pulse rounded bg-gray-800" />
            <div className="h-3 w-20 animate-pulse rounded bg-gray-800" />
          </div>
        </div>
      </div>
    </div>
  );
}
