/**
 * InfiniteScrollStatus Component
 *
 * Displays loading and end-of-list indicators for infinite scroll lists.
 * Includes the sentinel element that triggers loading when visible.
 *
 * Usage:
 * ```tsx
 * const { sentinelRef, isLoadingMore, error, retry } = useInfiniteScroll({...});
 *
 * return (
 *   <div>
 *     {items.map(item => <Item key={item.id} {...item} />)}
 *     <InfiniteScrollStatus
 *       sentinelRef={sentinelRef}
 *       isLoading={isLoadingMore}
 *       hasMore={hasNextPage}
 *       error={error}
 *       onRetry={retry}
 *     />
 *   </div>
 * );
 * ```
 */

import { AlertTriangle, Check, Loader2 } from 'lucide-react';

import type { ReactElement } from 'react';


export interface InfiniteScrollStatusProps {
  /**
   * Ref callback from useInfiniteScroll hook.
   * Attach to the sentinel element for intersection detection.
   */
  sentinelRef: (node: HTMLElement | null) => void;

  /**
   * Whether content is currently being loaded.
   */
  isLoading: boolean;

  /**
   * Whether there is more content to load.
   * When false, shows end-of-list message.
   */
  hasMore: boolean;

  /**
   * Error that occurred during loading.
   */
  error?: Error | null;

  /**
   * Callback to retry loading after an error.
   */
  onRetry?: () => void;

  /**
   * Message to display when there's no more content.
   * @default "You've reached the end"
   */
  endMessage?: string;

  /**
   * Message to display while loading.
   * @default "Loading more..."
   */
  loadingMessage?: string;

  /**
   * Additional CSS classes for the container.
   */
  className?: string;

  /**
   * Whether to show the end message when hasMore is false.
   * @default true
   */
  showEndMessage?: boolean;

  /**
   * Total count of items (optional, for display).
   */
  totalCount?: number;

  /**
   * Current count of loaded items (optional, for display).
   */
  loadedCount?: number;
}

export default function InfiniteScrollStatus({
  sentinelRef,
  isLoading,
  hasMore,
  error = null,
  onRetry,
  endMessage = "You've reached the end",
  loadingMessage = 'Loading more...',
  className = '',
  showEndMessage = true,
  totalCount,
  loadedCount,
}: InfiniteScrollStatusProps): ReactElement {
  // Error state
  if (error) {
    return (
      <div
        ref={sentinelRef}
        className={`flex flex-col items-center justify-center py-8 ${className}`}
        data-testid="infinite-scroll-error"
      >
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle className="h-5 w-5" />
          <span className="text-sm font-medium">Failed to load more</span>
        </div>
        <p className="mt-1 text-xs text-gray-500">{error.message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-3 rounded-md border border-gray-700 bg-[#1A1A1A] px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525]"
            data-testid="infinite-scroll-retry"
          >
            Try again
          </button>
        )}
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div
        ref={sentinelRef}
        className={`flex flex-col items-center justify-center py-8 ${className}`}
        data-testid="infinite-scroll-loading"
      >
        <Loader2 className="h-6 w-6 animate-spin text-[#76B900]" />
        <p className="mt-2 text-sm text-gray-400">{loadingMessage}</p>
        {totalCount !== undefined && loadedCount !== undefined && (
          <p className="mt-1 text-xs text-gray-500">
            Loaded {loadedCount} of {totalCount}
          </p>
        )}
      </div>
    );
  }

  // Has more - show sentinel for intersection observer
  if (hasMore) {
    return (
      <div
        ref={sentinelRef}
        className={`flex items-center justify-center py-4 ${className}`}
        data-testid="infinite-scroll-sentinel"
        aria-hidden="true"
      >
        {/* Invisible sentinel element - takes up minimal space */}
        <div className="h-1 w-full" />
      </div>
    );
  }

  // End of list
  if (showEndMessage) {
    return (
      <div
        ref={sentinelRef}
        className={`flex flex-col items-center justify-center py-8 ${className}`}
        data-testid="infinite-scroll-end"
      >
        <div className="flex items-center gap-2 text-gray-500">
          <Check className="h-5 w-5" />
          <span className="text-sm font-medium">{endMessage}</span>
        </div>
        {totalCount !== undefined && (
          <p className="mt-1 text-xs text-gray-600">{totalCount} items total</p>
        )}
      </div>
    );
  }

  // No message to show
  return (
    <div
      ref={sentinelRef}
      className="h-1"
      data-testid="infinite-scroll-hidden"
      aria-hidden="true"
    />
  );
}

export { InfiniteScrollStatus };
