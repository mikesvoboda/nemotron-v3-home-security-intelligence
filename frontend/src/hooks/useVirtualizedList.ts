/**
 * useVirtualizedList - Custom hook for list virtualization using @tanstack/react-virtual.
 *
 * This hook provides a simplified interface for virtualizing lists with support for:
 * - Fixed and variable height items
 * - Dynamic measurement with measureElement
 * - Overscan for smoother scrolling
 * - Scroll to item functionality
 *
 * @module hooks/useVirtualizedList
 */

import { useVirtualizer, type VirtualizerOptions, type Virtualizer } from '@tanstack/react-virtual';
import { useCallback, useRef, type RefObject } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the virtualized list.
 */
export interface UseVirtualizedListOptions<T> {
  /** Array of items to virtualize */
  items: T[];
  /**
   * Estimated size of each item in pixels.
   * Used as initial size before measurement.
   * @default 100
   */
  estimateSize?: number;
  /**
   * Function to estimate size based on index.
   * Overrides estimateSize if provided.
   */
  estimateSizeFn?: (index: number) => number;
  /**
   * Number of items to render outside the visible area.
   * Higher values reduce flickering during fast scroll.
   * @default 5
   */
  overscan?: number;
  /**
   * Whether to enable dynamic measurement of items.
   * When true, items should call measureElement on their container.
   * @default true
   */
  enableMeasurement?: boolean;
  /**
   * Get a unique key for each item.
   * Helps with stable item identification during updates.
   */
  getItemKey?: (index: number) => string | number;
  /**
   * Whether to scroll horizontally instead of vertically.
   * @default false
   */
  horizontal?: boolean;
  /**
   * Gap between items in pixels.
   * @default 0
   */
  gap?: number;
  /**
   * Optional callback when scroll occurs.
   */
  onScroll?: (scrollOffset: number) => void;
}

/**
 * Return type for useVirtualizedList hook.
 */
export interface UseVirtualizedListReturn<T> {
  /** Ref to attach to the scrollable container element */
  parentRef: RefObject<HTMLDivElement>;
  /** Array of virtual items to render */
  virtualItems: ReturnType<Virtualizer<HTMLDivElement, Element>['getVirtualItems']>;
  /** Total size of all items (for container sizing) */
  totalSize: number;
  /** Function to scroll to a specific item index */
  scrollToIndex: (index: number, options?: { align?: 'start' | 'center' | 'end' | 'auto' }) => void;
  /** Function to scroll to a specific offset */
  scrollToOffset: (
    offset: number,
    options?: { align?: 'start' | 'center' | 'end' | 'auto' }
  ) => void;
  /** Measure element function - pass to item container ref for dynamic sizing */
  measureElement: (element: Element | null) => void;
  /** Whether any items are currently being measured */
  isScrolling: boolean;
  /** Get the item at a specific index */
  getItem: (index: number) => T | undefined;
  /** The virtualizer instance for advanced usage */
  virtualizer: Virtualizer<HTMLDivElement, Element>;
  /** Style to apply to the inner container that holds items */
  containerStyle: React.CSSProperties;
  /** Get style for positioning a virtual item */
  getItemStyle: (
    virtualItem: ReturnType<Virtualizer<HTMLDivElement, Element>['getVirtualItems']>[0]
  ) => React.CSSProperties;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to create a virtualized list for efficient rendering of large lists.
 *
 * Uses @tanstack/react-virtual under the hood for optimal performance.
 * Supports both fixed and variable height items with optional dynamic measurement.
 *
 * @param options - Configuration options for the virtualized list
 * @returns Virtualization utilities and state
 *
 * @example
 * ```tsx
 * function EventList({ events }: { events: Event[] }) {
 *   const {
 *     parentRef,
 *     virtualItems,
 *     totalSize,
 *     measureElement,
 *     containerStyle,
 *     getItemStyle,
 *   } = useVirtualizedList({
 *     items: events,
 *     estimateSize: 120,
 *     overscan: 5,
 *   });
 *
 *   return (
 *     <div ref={parentRef} className="h-[600px] overflow-auto">
 *       <div style={containerStyle}>
 *         {virtualItems.map((virtualItem) => (
 *           <div
 *             key={virtualItem.key}
 *             ref={measureElement}
 *             data-index={virtualItem.index}
 *             style={getItemStyle(virtualItem)}
 *           >
 *             <EventCard event={events[virtualItem.index]} />
 *           </div>
 *         ))}
 *       </div>
 *     </div>
 *   );
 * }
 * ```
 */
export function useVirtualizedList<T>(
  options: UseVirtualizedListOptions<T>
): UseVirtualizedListReturn<T> {
  const {
    items,
    estimateSize = 100,
    estimateSizeFn,
    overscan = 5,
    enableMeasurement = true,
    getItemKey,
    horizontal = false,
    gap = 0,
    onScroll,
  } = options;

  const parentRef = useRef<HTMLDivElement>(null);

  // Build virtualizer options
  const virtualizerOptions: Partial<VirtualizerOptions<HTMLDivElement, Element>> = {
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: estimateSizeFn ?? (() => estimateSize),
    overscan,
    horizontal,
    gap,
    getItemKey: getItemKey ?? ((index) => index),
  };

  // Add measurement if enabled
  if (enableMeasurement) {
    virtualizerOptions.measureElement = (element) => {
      if (!element) return 0;
      return horizontal
        ? element.getBoundingClientRect().width
        : element.getBoundingClientRect().height;
    };
  }

  const virtualizer = useVirtualizer(
    virtualizerOptions as Parameters<typeof useVirtualizer<HTMLDivElement, Element>>[0]
  );

  // Set up scroll listener if callback provided
  const scrollToIndex = useCallback(
    (index: number, opts?: { align?: 'start' | 'center' | 'end' | 'auto' }) => {
      virtualizer.scrollToIndex(index, opts);
    },
    [virtualizer]
  );

  const scrollToOffset = useCallback(
    (offset: number, opts?: { align?: 'start' | 'center' | 'end' | 'auto' }) => {
      virtualizer.scrollToOffset(offset, opts);
    },
    [virtualizer]
  );

  const getItem = useCallback((index: number): T | undefined => items[index], [items]);

  // Container style for absolute positioning
  const containerStyle: React.CSSProperties = {
    height: horizontal ? '100%' : `${virtualizer.getTotalSize()}px`,
    width: horizontal ? `${virtualizer.getTotalSize()}px` : '100%',
    position: 'relative',
  };

  // Get style for a virtual item
  const getItemStyle = useCallback(
    (
      virtualItem: ReturnType<Virtualizer<HTMLDivElement, Element>['getVirtualItems']>[0]
    ): React.CSSProperties => {
      return {
        position: 'absolute',
        top: horizontal ? 0 : virtualItem.start,
        left: horizontal ? virtualItem.start : 0,
        width: horizontal ? undefined : '100%',
        height: horizontal ? '100%' : undefined,
        ...(horizontal
          ? { minWidth: `${virtualItem.size}px` }
          : { minHeight: `${virtualItem.size}px` }),
      };
    },
    [horizontal]
  );

  // Handle scroll events
  if (onScroll && parentRef.current) {
    const handleScroll = () => {
      const offset = horizontal
        ? (parentRef.current?.scrollLeft ?? 0)
        : (parentRef.current?.scrollTop ?? 0);
      onScroll(offset);
    };
    parentRef.current.addEventListener('scroll', handleScroll, { passive: true });
  }

  return {
    parentRef: parentRef as RefObject<HTMLDivElement>,
    virtualItems: virtualizer.getVirtualItems(),
    totalSize: virtualizer.getTotalSize(),
    scrollToIndex,
    scrollToOffset,
    measureElement: virtualizer.measureElement,
    isScrolling: virtualizer.isScrolling,
    getItem,
    virtualizer,
    containerStyle,
    getItemStyle,
  };
}

export default useVirtualizedList;
