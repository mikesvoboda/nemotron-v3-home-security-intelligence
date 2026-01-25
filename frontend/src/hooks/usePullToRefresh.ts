/**
 * usePullToRefresh - Hook for detecting pull-to-refresh gestures on mobile
 *
 * Detects pull-down gestures at the top of a scrollable container to trigger
 * a refresh action. Provides visual feedback state for pull progress.
 *
 * Features:
 * - Only activates when at the top of scroll container
 * - Configurable threshold and resistance
 * - Prevents multiple concurrent refreshes
 * - Provides pull progress for visual feedback
 *
 * @see NEM-2970
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export interface PullToRefreshOptions {
  /**
   * Callback function when refresh is triggered.
   * Should return a Promise that resolves when refresh is complete.
   */
  onRefresh: () => Promise<void>;

  /**
   * Minimum pull distance in pixels to trigger refresh.
   * @default 80
   */
  threshold?: number;

  /**
   * Resistance factor applied to pull distance (0-1).
   * Lower values make pulling feel heavier.
   * @default 0.5
   */
  resistance?: number;

  /**
   * Whether pull-to-refresh is disabled.
   * @default false
   */
  disabled?: boolean;

  /**
   * External control of refreshing state.
   * Useful when refresh state is managed externally (e.g., by React Query).
   */
  isRefreshing?: boolean;
}

export interface PullToRefreshReturn {
  /**
   * Ref callback to attach to the scrollable container element.
   */
  containerRef: (element: HTMLElement | null) => void;

  /**
   * Whether the user is currently pulling down.
   */
  isPulling: boolean;

  /**
   * Whether a refresh is currently in progress.
   */
  isRefreshing: boolean;

  /**
   * Current pull distance in pixels (after resistance applied).
   */
  pullDistance: number;

  /**
   * Pull progress as a ratio (0-1) of pullDistance to threshold.
   */
  pullProgress: number;
}

interface TouchStartState {
  y: number;
  scrollTop: number;
}

/**
 * Custom hook that detects pull-to-refresh gestures on a scrollable container.
 *
 * @param options - Configuration options for pull-to-refresh
 * @returns Object containing ref callback and state for visual feedback
 *
 * @example
 * ```tsx
 * const { containerRef, isPulling, isRefreshing, pullProgress } = usePullToRefresh({
 *   onRefresh: async () => {
 *     await refetchData();
 *   },
 *   threshold: 80,
 * });
 *
 * return (
 *   <div ref={containerRef}>
 *     {isPulling && <PullIndicator progress={pullProgress} />}
 *     {isRefreshing && <Spinner />}
 *     <Content />
 *   </div>
 * );
 * ```
 */
export function usePullToRefresh({
  onRefresh,
  threshold = 80,
  resistance = 0.5,
  disabled = false,
  isRefreshing: externalIsRefreshing,
}: PullToRefreshOptions): PullToRefreshReturn {
  const [isPulling, setIsPulling] = useState(false);
  const [internalIsRefreshing, setInternalIsRefreshing] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);

  // Track touch start position
  const touchStartRef = useRef<TouchStartState | null>(null);
  // Track current element
  const elementRef = useRef<HTMLElement | null>(null);
  // Track if refresh is in progress (ref for sync access in event handlers)
  const refreshingRef = useRef(false);
  // Track current pull distance in ref for sync access in touchend handler
  const pullDistanceRef = useRef(0);

  // Use external isRefreshing if provided, otherwise use internal state
  const isRefreshing = externalIsRefreshing ?? internalIsRefreshing;

  // Store latest callbacks in refs
  const onRefreshRef = useRef(onRefresh);
  useEffect(() => {
    onRefreshRef.current = onRefresh;
  }, [onRefresh]);

  // Calculate pull progress
  const pullProgress = Math.min(pullDistance / threshold, 1);

  const handleTouchStart = useCallback(
    (e: TouchEvent) => {
      if (disabled || refreshingRef.current) {
        return;
      }

      const touch = e.touches[0];
      if (!touch) {
        return;
      }

      const element = elementRef.current;
      const scrollTop = element?.scrollTop ?? 0;

      touchStartRef.current = {
        y: touch.clientY,
        scrollTop,
      };
    },
    [disabled]
  );

  const handleTouchMove = useCallback(
    (e: TouchEvent) => {
      if (disabled || refreshingRef.current) {
        return;
      }

      const touchStart = touchStartRef.current;
      if (!touchStart) {
        return;
      }

      const touch = e.touches[0];
      if (!touch) {
        return;
      }

      const element = elementRef.current;
      const currentScrollTop = element?.scrollTop ?? 0;

      // Only allow pull when at the top of scroll container
      if (currentScrollTop > 0) {
        // Reset state if we scrolled away from top
        if (isPulling) {
          setIsPulling(false);
          setPullDistance(0);
          pullDistanceRef.current = 0;
        }
        return;
      }

      // Calculate raw delta
      const deltaY = touch.clientY - touchStart.y;

      // Only respond to downward pull
      if (deltaY <= 0) {
        if (isPulling) {
          setIsPulling(false);
          setPullDistance(0);
          pullDistanceRef.current = 0;
        }
        return;
      }

      // Apply resistance
      const resistedDistance = deltaY * resistance;

      setIsPulling(true);
      setPullDistance(resistedDistance);
      pullDistanceRef.current = resistedDistance;

      // Prevent default scrolling behavior during pull
      if (resistedDistance > 0) {
        e.preventDefault();
      }
    },
    [disabled, isPulling, resistance]
  );

  const handleTouchEnd = useCallback(async () => {
    if (disabled || refreshingRef.current) {
      touchStartRef.current = null;
      return;
    }

    // Use ref value for sync access (state may be stale in event handler)
    const currentPullDistance = pullDistanceRef.current;
    const shouldRefresh = currentPullDistance >= threshold;

    // Reset touch tracking
    touchStartRef.current = null;

    if (shouldRefresh) {
      // Trigger refresh
      refreshingRef.current = true;
      setInternalIsRefreshing(true);

      try {
        await onRefreshRef.current();
      } finally {
        refreshingRef.current = false;
        setInternalIsRefreshing(false);
      }
    }

    // Reset pull state
    setIsPulling(false);
    setPullDistance(0);
    pullDistanceRef.current = 0;
  }, [disabled, threshold]);

  // Store latest handlers in refs for stable event listeners
  const handleTouchStartRef = useRef(handleTouchStart);
  const handleTouchMoveRef = useRef(handleTouchMove);
  const handleTouchEndRef = useRef(handleTouchEnd);

  useEffect(() => {
    handleTouchStartRef.current = handleTouchStart;
  }, [handleTouchStart]);

  useEffect(() => {
    handleTouchMoveRef.current = handleTouchMove;
  }, [handleTouchMove]);

  useEffect(() => {
    handleTouchEndRef.current = handleTouchEnd;
  }, [handleTouchEnd]);

  // Stable event handlers that delegate to refs
  const stableTouchStart = useCallback((e: TouchEvent) => {
    handleTouchStartRef.current(e);
  }, []);

  const stableTouchMove = useCallback((e: TouchEvent) => {
    handleTouchMoveRef.current(e);
  }, []);

  const stableTouchEnd = useCallback(() => {
    void handleTouchEndRef.current();
  }, []);

  // Ref callback - now with stable handlers
  const containerRef = useCallback(
    (element: HTMLElement | null) => {
      // Remove listeners from previous element
      if (elementRef.current) {
        elementRef.current.removeEventListener('touchstart', stableTouchStart);
        elementRef.current.removeEventListener('touchmove', stableTouchMove as EventListener);
        elementRef.current.removeEventListener('touchend', stableTouchEnd);
      }

      // Store new element
      elementRef.current = element;

      // Add listeners to new element
      if (element && !disabled) {
        element.addEventListener('touchstart', stableTouchStart, { passive: true });
        element.addEventListener('touchmove', stableTouchMove as EventListener, {
          passive: false,
        });
        element.addEventListener('touchend', stableTouchEnd, { passive: true });
      }
    },
    [stableTouchStart, stableTouchMove, stableTouchEnd, disabled]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (elementRef.current) {
        elementRef.current.removeEventListener('touchstart', stableTouchStart);
        elementRef.current.removeEventListener('touchmove', stableTouchMove as EventListener);
        elementRef.current.removeEventListener('touchend', stableTouchEnd);
      }
    };
  }, [stableTouchStart, stableTouchMove, stableTouchEnd]);

  return {
    containerRef,
    isPulling,
    isRefreshing,
    pullDistance,
    pullProgress,
  };
}

export default usePullToRefresh;
