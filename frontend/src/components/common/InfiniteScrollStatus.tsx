import { Loader2, CheckCircle2 } from 'lucide-react';

export interface InfiniteScrollStatusProps {
  /**
   * Whether more items are being fetched
   */
  isFetchingNextPage: boolean;
  /**
   * Whether there are more items to load
   */
  hasNextPage: boolean;
  /**
   * Total count of items (optional, for display)
   */
  totalCount?: number;
  /**
   * Number of items currently loaded
   */
  loadedCount?: number;
  /**
   * Custom loading message
   * @default 'Loading more...'
   */
  loadingMessage?: string;
  /**
   * Custom end message
   * @default 'All items loaded'
   */
  endMessage?: string;
  /**
   * Additional CSS classes
   */
  className?: string;
}

/**
 * InfiniteScrollStatus displays loading indicator during fetch
 * and an "end of list" message when all items have been loaded.
 *
 * @example
 * ```tsx
 * <InfiniteScrollStatus
 *   isFetchingNextPage={isFetchingNextPage}
 *   hasNextPage={hasNextPage}
 *   totalCount={totalCount}
 *   loadedCount={events.length}
 * />
 * ```
 */
export default function InfiniteScrollStatus({
  isFetchingNextPage,
  hasNextPage,
  totalCount,
  loadedCount,
  loadingMessage = 'Loading more...',
  endMessage = 'All items loaded',
  className = '',
}: InfiniteScrollStatusProps) {
  // Don't render anything if we have more pages and aren't fetching
  if (hasNextPage && !isFetchingNextPage) {
    return null;
  }

  // Loading state
  if (isFetchingNextPage) {
    return (
      <div
        className={`flex items-center justify-center gap-2 py-6 text-gray-400 ${className}`}
        data-testid="infinite-scroll-loading"
      >
        <Loader2 className="h-5 w-5 animate-spin text-[#76B900]" aria-hidden="true" />
        <span className="text-sm">{loadingMessage}</span>
      </div>
    );
  }

  // End of list state (no more pages and not fetching)
  if (!hasNextPage) {
    return (
      <div
        className={`flex flex-col items-center justify-center gap-2 py-6 ${className}`}
        data-testid="infinite-scroll-end"
      >
        <div className="flex items-center gap-2 text-gray-500">
          <CheckCircle2 className="h-5 w-5 text-[#76B900]/60" aria-hidden="true" />
          <span className="text-sm">{endMessage}</span>
        </div>
        {totalCount !== undefined && loadedCount !== undefined && (
          <span className="text-xs text-gray-600">
            Showing {loadedCount} of {totalCount} items
          </span>
        )}
      </div>
    );
  }

  return null;
}
