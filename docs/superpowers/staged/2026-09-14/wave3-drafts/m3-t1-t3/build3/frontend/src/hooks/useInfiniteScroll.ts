/**
 * useInfiniteScroll Hook
 *
 * A React hook that uses Intersection Observer to implement infinite scrolling.
 * Detects when a sentinel element becomes visible and triggers loading of more content.
 *
 * Features:
 * - Intersection Observer for efficient scroll detection
 * - Loading state management
 * - Error handling with retry capability
 * - hasMore tracking to stop loading when all data is fetched
 * - Configurable threshold and root margin
 *
 * Usage:
 * ```tsx
 * const { sentinelRef, isLoadingMore, error } = useInfiniteScroll({
 *   onLoadMore: fetchNextPage,
 *   hasMore: hasNextPage,
 *   isLoading: isFetchingNextPage,
 * });
 *
 * return (
 *   <div>
 *     {items.map(item => <Item key={item.id} {...item} />)}
 *     <div ref={sentinelRef} />
 *     {isLoadingMore && <Spinner />}
 *   </div>
 * );
 * ```
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseInfiniteScrollOptions {
  /**
   * Callback function to load more data.
   * Called when the sentinel element becomes visible.
   */
  onLoadMore: () => void | Promise<void>;

  /**
   * Whether there is more data to load.
   * When false, the observer will not trigger onLoadMore.
   */
  hasMore: boolean;

  /**
   * Whether data is currently being loaded.
   * Prevents multiple concurrent load requests.
   */
  isLoading?: boolean;

  /**
   * Whether the infinite scroll is enabled.
   * Can be used to disable scrolling temporarily.
   * @default true
   */
  enabled?: boolean;

  /**
   * The threshold for the Intersection Observer.
   * A value between 0 and 1 indicating the percentage of the target's
   * visibility that triggers the callback.
   * @default 0.1
   */
  threshold?: number;

  /**
   * The root margin for the Intersection Observer.
   * Allows you to grow or shrink the root element's bounding box.
   * Useful for loading content before it's visible.
   * @default '100px'
   */
  rootMargin?: string;

  /**
   * Callback when an error occurs during load.
   */
  onError?: (error: Error) => void;
}

export interface UseInfiniteScrollReturn {
  /**
   * Ref to attach to the sentinel element that triggers loading.
   * Place this element at the bottom of your list.
   */
  sentinelRef: (node: HTMLElement | null) => void;

  /**
   * Whether more data is currently being loaded.
   * This is true when onLoadMore has been called and is still pending.
   */
  isLoadingMore: boolean;

  /**
   * Error that occurred during the last load attempt.
   */
  error: Error | null;

  /**
   * Retry the last failed load attempt.
   */
  retry: () => void;

  /**
   * Clear the current error state.
   */
  clearError: () => void;
}

export function useInfiniteScroll(options: UseInfiniteScrollOptions): UseInfiniteScrollReturn {
  const {
    onLoadMore,
    hasMore,
    isLoading = false,
    enabled = true,
    threshold = 0.1,
    rootMargin = '100px',
    onError,
  } = options;

  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Ref to store the observer instance
  const observerRef = useRef<IntersectionObserver | null>(null);
  // Ref to store the sentinel node
  const sentinelNodeRef = useRef<HTMLElement | null>(null);
  // Ref to track if a load is in progress (to prevent duplicate calls)
  const loadingRef = useRef(false);

  // Store the latest callbacks in refs to avoid recreating the observer
  const onLoadMoreRef = useRef(onLoadMore);
  const onErrorRef = useRef(onError);

  // Update refs when callbacks change
  useEffect(() => {
    onLoadMoreRef.current = onLoadMore;
  }, [onLoadMore]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  // Handle loading more data
  const handleLoadMore = useCallback(async () => {
    // Guard conditions
    if (loadingRef.current || isLoading || !hasMore || !enabled) {
      return;
    }

    loadingRef.current = true;
    setIsLoadingMore(true);
    setError(null);

    try {
      await onLoadMoreRef.current();
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      onErrorRef.current?.(error);
    } finally {
      loadingRef.current = false;
      setIsLoadingMore(false);
    }
  }, [hasMore, isLoading, enabled]);

  // Retry function
  const retry = useCallback(() => {
    setError(null);
    void handleLoadMore();
  }, [handleLoadMore]);

  // Clear error function
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Callback ref for the sentinel element
  const sentinelRef = useCallback(
    (node: HTMLElement | null) => {
      // Disconnect existing observer
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }

      // Store the node reference
      sentinelNodeRef.current = node;

      // Don't observe if conditions aren't met
      if (!node || !enabled || !hasMore) {
        return;
      }

      // Check for IntersectionObserver support (SSR safety)
      if (typeof IntersectionObserver === 'undefined') {
        return;
      }

      // Create and start observing
      observerRef.current = new IntersectionObserver(
        (entries) => {
          const [entry] = entries;
          if (entry?.isIntersecting && hasMore && !loadingRef.current && !isLoading) {
            void handleLoadMore();
          }
        },
        {
          threshold,
          rootMargin,
        }
      );

      observerRef.current.observe(node);
    },
    [enabled, hasMore, isLoading, threshold, rootMargin, handleLoadMore]
  );

  // Cleanup observer on unmount
  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
    };
  }, []);

  // Re-observe when hasMore or enabled changes
  useEffect(() => {
    // If we have a sentinel node and conditions change, re-attach the observer
    if (sentinelNodeRef.current) {
      sentinelRef(sentinelNodeRef.current);
    }
  }, [hasMore, enabled, sentinelRef]);

  return {
    sentinelRef,
    isLoadingMore,
    error,
    retry,
    clearError,
  };
}

export default useInfiniteScroll;
