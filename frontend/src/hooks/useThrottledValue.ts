import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Options for useThrottledValue hook
 */
export interface UseThrottledValueOptions {
  /**
   * Throttle interval in milliseconds.
   * Value updates are batched within this interval.
   * Default: 500ms
   */
  interval?: number;

  /**
   * Whether to emit the first value immediately (leading edge).
   * Default: true
   */
  leading?: boolean;
}

/**
 * useThrottledValue - Throttles value updates to reduce re-renders
 *
 * This hook is designed for WebSocket data that arrives frequently.
 * It batches updates within the specified interval, reducing unnecessary
 * re-renders while keeping the UI responsive.
 *
 * @param value - The value to throttle
 * @param options - Throttle options
 * @returns The throttled value
 *
 * @example
 * ```tsx
 * const { events } = useEventStream();
 * const throttledEvents = useThrottledValue(events, { interval: 500 });
 * // throttledEvents updates at most every 500ms
 * ```
 */
export function useThrottledValue<T>(
  value: T,
  options: UseThrottledValueOptions = {}
): T {
  const { interval = 500 } = options;
  // Note: `leading` option is reserved for future use but not currently implemented
  // since leading=true is the default behavior (initial value is returned immediately)

  // State for the throttled value
  const [throttledValue, setThrottledValue] = useState<T>(value);

  // Track the latest value for trailing edge updates
  const latestValueRef = useRef<T>(value);

  // Track whether we're currently in a throttle window
  const isThrottledRef = useRef<boolean>(false);

  // Track the timeout for cleanup
  const timeoutIdRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track if this is the first render
  const isFirstRenderRef = useRef<boolean>(true);

  // Update the latest value ref whenever the input value changes
  latestValueRef.current = value;

  // Memoized function to perform the trailing edge update
  const performTrailingUpdate = useCallback(() => {
    setThrottledValue(latestValueRef.current);
    isThrottledRef.current = false;
    timeoutIdRef.current = null;
  }, []);

  useEffect(() => {
    // On first render with leading=true, just return (value is already set)
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }

    // If we're not currently throttled, start a new throttle window
    if (!isThrottledRef.current) {
      isThrottledRef.current = true;

      // Schedule the trailing edge update
      timeoutIdRef.current = setTimeout(performTrailingUpdate, interval);
    }
    // If we are throttled, the timeout will pick up latestValueRef.current
    // when it fires (no action needed here)
  }, [value, interval, performTrailingUpdate]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutIdRef.current !== null) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }
    };
  }, []);

  return throttledValue;
}
