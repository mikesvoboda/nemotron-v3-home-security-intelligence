/**
 * VirtualizedList - A reusable virtualized list component for efficient rendering.
 *
 * Uses @tanstack/react-virtual for windowing/virtualization to handle large lists
 * efficiently by only rendering visible items plus overscan.
 *
 * @module components/common/VirtualizedList
 */

import { useVirtualizer } from '@tanstack/react-virtual';
import { clsx } from 'clsx';
import { useCallback, useRef, type ReactNode, type CSSProperties, type JSX } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the VirtualizedList component.
 */
export interface VirtualizedListProps<T> {
  /** Array of items to render */
  items: T[];
  /**
   * Render function for each item.
   * Receives item, index, and measurement ref callback.
   */
  renderItem: (item: T, index: number, measureRef: (el: HTMLElement | null) => void) => ReactNode;
  /**
   * Function to get a unique key for each item.
   * Defaults to using index if not provided.
   */
  getItemKey?: (item: T, index: number) => string | number;
  /**
   * Estimated height of each item in pixels.
   * Used for initial layout before measurement.
   * @default 100
   */
  estimateSize?: number;
  /**
   * Number of items to render outside visible area.
   * Higher values reduce flicker during fast scroll.
   * @default 5
   */
  overscan?: number;
  /**
   * Height of the scrollable container.
   * Can be a number (pixels) or CSS string (e.g., '100vh', '500px').
   * @default '100%'
   */
  height?: number | string;
  /**
   * Additional CSS classes for the container.
   */
  className?: string;
  /**
   * Additional CSS classes for the inner scrollable area.
   */
  innerClassName?: string;
  /**
   * Gap between items in pixels.
   * @default 0
   */
  gap?: number;
  /**
   * Callback when scroll position changes.
   */
  onScroll?: (scrollTop: number) => void;
  /**
   * Callback when reaching near the end of the list (for infinite scroll).
   */
  onEndReached?: () => void;
  /**
   * Distance from end to trigger onEndReached.
   * @default 200
   */
  endReachedThreshold?: number;
  /**
   * Whether the list is loading more items.
   * Used to prevent multiple onEndReached calls.
   */
  isLoadingMore?: boolean;
  /**
   * Test ID for the container element.
   */
  testId?: string;
  /**
   * Empty state to show when items array is empty.
   */
  emptyState?: ReactNode;
  /**
   * Loading state to show at the end of the list.
   */
  loadingIndicator?: ReactNode;
  /**
   * Footer content to show at the end of the list (e.g., "End of list" message).
   */
  footer?: ReactNode;
  /**
   * Aria label for the list container.
   */
  ariaLabel?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * VirtualizedList component for efficiently rendering large lists.
 *
 * Uses windowing/virtualization to only render visible items plus overscan,
 * dramatically improving performance for lists with hundreds or thousands of items.
 *
 * @example
 * ```tsx
 * <VirtualizedList
 *   items={events}
 *   renderItem={(event, index, measureRef) => (
 *     <div ref={measureRef} key={event.id}>
 *       <EventCard event={event} />
 *     </div>
 *   )}
 *   getItemKey={(event) => event.id}
 *   estimateSize={120}
 *   height={600}
 *   onEndReached={() => fetchMore()}
 * />
 * ```
 */
export function VirtualizedList<T>({
  items,
  renderItem,
  getItemKey,
  estimateSize = 100,
  overscan = 5,
  height = '100%',
  className,
  innerClassName,
  gap = 0,
  onScroll,
  onEndReached,
  endReachedThreshold = 200,
  isLoadingMore = false,
  testId,
  emptyState,
  loadingIndicator,
  footer,
  ariaLabel,
}: VirtualizedListProps<T>): JSX.Element {
  const parentRef = useRef<HTMLDivElement>(null);
  const endReachedCalledRef = useRef(false);

  // Create virtualizer instance
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize,
    overscan,
    gap,
    getItemKey: getItemKey ? (index) => getItemKey(items[index], index) : (index) => index,
    measureElement: (element) => {
      if (!element) return estimateSize;
      return element.getBoundingClientRect().height;
    },
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();

  // Handle scroll events
  const handleScroll = useCallback(() => {
    if (!parentRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = parentRef.current;

    // Call onScroll callback
    if (onScroll) {
      onScroll(scrollTop);
    }

    // Check for end reached
    if (onEndReached && !isLoadingMore) {
      const distanceFromEnd = scrollHeight - scrollTop - clientHeight;
      if (distanceFromEnd < endReachedThreshold && !endReachedCalledRef.current) {
        endReachedCalledRef.current = true;
        onEndReached();
      } else if (distanceFromEnd >= endReachedThreshold) {
        // Reset the flag when scrolled away from the end
        endReachedCalledRef.current = false;
      }
    }
  }, [onScroll, onEndReached, endReachedThreshold, isLoadingMore]);

  // Container height style
  const containerStyle: CSSProperties = {
    height: typeof height === 'number' ? `${height}px` : height,
  };

  // Empty state
  if (items.length === 0 && emptyState) {
    return (
      <div
        ref={parentRef}
        className={clsx('overflow-auto', className)}
        style={containerStyle}
        data-testid={testId}
        aria-label={ariaLabel}
      >
        {emptyState}
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      className={clsx('overflow-auto', className)}
      style={containerStyle}
      onScroll={handleScroll}
      data-testid={testId}
      aria-label={ariaLabel}
      role="list"
    >
      <div className={clsx('relative w-full', innerClassName)} style={{ height: `${totalSize}px` }}>
        {virtualItems.map((virtualItem) => {
          const item = items[virtualItem.index];
          return (
            <div
              key={virtualItem.key}
              role="listitem"
              data-index={virtualItem.index}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              {renderItem(item, virtualItem.index, virtualizer.measureElement)}
            </div>
          );
        })}
      </div>

      {/* Loading indicator at the end */}
      {isLoadingMore && loadingIndicator && <div className="py-4">{loadingIndicator}</div>}

      {/* Footer (e.g., end of list message) */}
      {!isLoadingMore && footer && items.length > 0 && <div className="py-4">{footer}</div>}
    </div>
  );
}

export default VirtualizedList;
