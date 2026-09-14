/**
 * useSwipeGesture - Hook for detecting touch swipe gestures
 *
 * Detects left, right, up, and down swipes with configurable threshold and timeout.
 * Returns a ref callback to attach to the target element.
 */

import { useCallback, useRef } from 'react';

export type SwipeDirection = 'left' | 'right' | 'up' | 'down';

export interface SwipeGestureOptions {
  /** Callback function called when a swipe is detected */
  onSwipe: (direction: SwipeDirection) => void;
  /** Minimum distance in pixels to trigger a swipe (default: 50) */
  threshold?: number;
  /** Maximum time in milliseconds for swipe to complete (default: 300) */
  timeout?: number;
}

interface TouchStart {
  x: number;
  y: number;
  timestamp: number;
}

/**
 * Custom hook that detects swipe gestures on a DOM element
 *
 * @param options - Configuration options for swipe detection
 * @returns Ref callback to attach to the target element
 */
export function useSwipeGesture({
  onSwipe,
  threshold = 50,
  timeout = 300,
}: SwipeGestureOptions): (element: HTMLElement | null) => void {
  const touchStartRef = useRef<TouchStart | null>(null);

  const handleTouchStart = useCallback((e: TouchEvent) => {
    const touch = e.touches[0];
    if (touch) {
      touchStartRef.current = {
        x: touch.clientX,
        y: touch.clientY,
        timestamp: Date.now(),
      };
    }
  }, []);

  const handleTouchEnd = useCallback(
    (e: TouchEvent) => {
      const touchStart = touchStartRef.current;
      if (!touchStart) {
        return;
      }

      const touch = e.changedTouches[0];
      if (!touch) {
        return;
      }

      // Check if swipe completed within timeout
      const elapsed = Date.now() - touchStart.timestamp;
      if (elapsed > timeout) {
        touchStartRef.current = null;
        return;
      }

      // Calculate deltas
      const deltaX = touch.clientX - touchStart.x;
      const deltaY = touch.clientY - touchStart.y;

      // Calculate absolute distances
      const absDeltaX = Math.abs(deltaX);
      const absDeltaY = Math.abs(deltaY);

      // Determine swipe direction based on larger delta
      let direction: SwipeDirection | null = null;

      if (absDeltaX >= threshold || absDeltaY >= threshold) {
        if (absDeltaX > absDeltaY) {
          // Horizontal swipe
          direction = deltaX > 0 ? 'right' : 'left';
        } else {
          // Vertical swipe
          direction = deltaY > 0 ? 'down' : 'up';
        }
      }

      // Reset touch start
      touchStartRef.current = null;

      // Call callback if swipe was detected
      if (direction) {
        onSwipe(direction);
      }
    },
    [onSwipe, threshold, timeout]
  );

  // Return ref callback
  const refCallback = useCallback(
    (element: HTMLElement | null) => {
      // Remove previous listeners if any
      const cleanup = () => {
        if (element) {
          element.removeEventListener('touchstart', handleTouchStart);
          element.removeEventListener('touchend', handleTouchEnd);
        }
      };

      cleanup();

      // Add listeners to new element
      if (element) {
        element.addEventListener('touchstart', handleTouchStart, { passive: true });
        element.addEventListener('touchend', handleTouchEnd, { passive: true });
      }
    },
    [handleTouchStart, handleTouchEnd]
  );

  return refCallback;
}

export default useSwipeGesture;
