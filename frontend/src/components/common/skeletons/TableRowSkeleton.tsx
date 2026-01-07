import { clsx } from 'clsx';

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
 */
export default function TableRowSkeleton({
  columns = 4,
  rows = 1,
  className,
}: TableRowSkeletonProps) {
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
            const widths = ['w-24', 'w-32', 'w-20', 'w-28', 'w-16', 'w-40'];
            const widthClass = widths[colIndex % widths.length];
            return (
              <div
                key={colIndex}
                className={clsx('h-4 animate-pulse rounded bg-gray-800', widthClass)}
                data-testid={`table-row-skeleton-col-${colIndex}`}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}
