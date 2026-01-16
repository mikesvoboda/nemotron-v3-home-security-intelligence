import { clsx } from 'clsx';

export interface ChartSkeletonProps {
  /** Height in pixels (default: 300) */
  height?: number;
  /** Additional CSS classes */
  className?: string;
}

/**
 * ChartSkeleton component - Loading placeholder for chart components
 */
export default function ChartSkeleton({ height = 300, className }: ChartSkeletonProps) {
  return (
    <div
      className={clsx('relative rounded-lg border border-gray-800 bg-[#1F1F1F] p-4', className)}
      style={{ height: `${height}px` }}
      data-testid="chart-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Y-axis labels */}
      <div
        className="absolute left-4 top-4 flex h-[calc(100%-60px)] flex-col justify-between"
        data-testid="chart-skeleton-y-axis"
      >
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-3 w-8 animate-pulse rounded bg-gray-800" />
        ))}
      </div>

      {/* Chart area with fake bars/lines */}
      <div
        className="ml-14 mr-4 flex h-[calc(100%-60px)] items-end justify-around gap-2 pt-4"
        data-testid="chart-skeleton-area"
      >
        {[65, 45, 80, 55, 70, 40, 85, 60, 75, 50].map((h, i) => (
          <div
            key={i}
            className="w-full animate-pulse rounded-t bg-gray-800"
            style={{ height: `${h}%` }}
          />
        ))}
      </div>

      {/* X-axis labels */}
      <div className="ml-14 mr-4 mt-4 flex justify-around" data-testid="chart-skeleton-x-axis">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
          <div key={i} className="h-3 w-6 animate-pulse rounded bg-gray-800" />
        ))}
      </div>
    </div>
  );
}
