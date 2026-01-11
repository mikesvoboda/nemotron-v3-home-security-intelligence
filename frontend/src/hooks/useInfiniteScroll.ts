import { useCallback, useEffect, useRef } from 'react';

/**
 * Options for the useInfiniteScroll hook
 */
export interface UseInfiniteScrollOptions {
  /**
   * Whether there are more items to load
   */
  hasNextPage: boolean;
  /**
   * Whether a fetch is currently in progress
   */
  isFetchingNextPage: boolean;
  /**
   * Function to call when more items should be loaded
   */
  fetchNextPage: () => void;
  /**
   * Margin around the root element for triggering the intersection.
   * Use a positive value (e.g., '200px') to trigger earlier (before element is visible).
   * @default '200px'
   */
  rootMargin?: string;
  /**
   * Whether infinite scroll is enabled
   * @default true
   */
  enabled?: boolean;
}

/**
 * Return type for the useInfiniteScroll hook
 */
export interface UseInfiniteScrollReturn {
  /**
   * Ref to attach to the sentinel element at the bottom of the list.
   * When this element becomes visible, more items are loaded.
   */
  loadMoreRef: React.RefObject<HTMLDivElement>;
}

/**
 * A hook that implements infinite scroll functionality using the Intersection Observer API.
 *
 * The hook returns a ref that should be attached to a sentinel element at the bottom
 * of the scrollable list. When this element becomes visible (or nearly visible based
 * on rootMargin), the fetchNextPage function is called to load more items.
 *
 * @example
 * ```tsx
 * const { loadMoreRef } = useInfiniteScroll({
 *   hasNextPage,
 *   isFetchingNextPage,
 *   fetchNextPage,
 *   rootMargin: '200px',
 * });
 *
 * return (
 *   <div>
 *     {items.map(item => <ItemComponent key={item.id} item={item} />)}
 *     <div ref={loadMoreRef} />
 *     {isFetchingNextPage && <LoadingSpinner />}
 *   </div>
 * );
 * ```
 */
export function useInfiniteScroll({
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  rootMargin = '200px',
  enabled = true,
}: UseInfiniteScrollOptions): UseInfiniteScrollReturn {
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Memoize the callback to avoid recreating the observer unnecessarily
  const handleIntersection = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const [entry] = entries;
      if (entry.isIntersecting && hasNextPage && !isFetchingNextPage && enabled) {
        fetchNextPage();
      }
    },
    [hasNextPage, isFetchingNextPage, fetchNextPage, enabled]
  );

  useEffect(() => {
    const element = loadMoreRef.current;

    // Don't observe if disabled, no element, or nothing more to load
    if (!enabled || !element) {
      return;
    }

    const observer = new IntersectionObserver(handleIntersection, {
      rootMargin,
      threshold: 0,
    });

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [handleIntersection, rootMargin, enabled]);

  return { loadMoreRef: loadMoreRef as React.RefObject<HTMLDivElement> };
}

export default useInfiniteScroll;
