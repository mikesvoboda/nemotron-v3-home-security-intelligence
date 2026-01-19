import { clsx } from 'clsx';

import Skeleton from '../Skeleton';

export interface TableRowSkeletonProps {
  /** Number of columns to render (default: 4) */
  columns?: number;
  /** Number of rows to render (default: 1) */
  rows?: number;
  /** Additional CSS classes */
  className?: string;
}

/**
 * TableRowSkeleton component - Loading placeholder for table rows
 * Uses shimmer animation for smooth loading experience
 */
export default function TableRowSkeleton({
  columns = 4,
  rows = 1,
  className,
}: TableRowSkeletonProps) {
  // Variable widths for visual variety
  const widths = [96, 128, 80, 112, 64, 160];

  return (
    <div
      className={clsx('divide-y divide-gray-800', className)}
      data-testid="table-row-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {Array.from({ length: rows }, (_, rowIndex) => (
        <div
          key={rowIndex}
          className="flex items-center gap-4 px-4 py-3"
          data-testid={`table-row-skeleton-row-${rowIndex}`}
        >
          {Array.from({ length: columns }, (_, colIndex) => {
            const width = widths[colIndex % widths.length];
            return (
              <Skeleton
                key={colIndex}
                variant="text"
                width={width}
                height={16}
                animation="shimmer"
                data-testid={`table-row-skeleton-col-${colIndex}`}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}
