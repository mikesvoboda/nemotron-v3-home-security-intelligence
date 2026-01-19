/**
 * useChartDimensions - Responsive dimension calculation hook for charts
 *
 * Provides responsive chart dimensions with automatic height calculation
 * based on aspect ratio, mobile/compact viewport detection, and debouncing.
 *
 * Features:
 * - ResizeObserver for container size changes
 * - Height calculation from aspect ratio with min/max constraints
 * - Mobile detection (< 768px) with reduced max height (220px)
 * - Compact detection (< 400px) with further reduced max height (180px)
 * - Debounced updates for smooth resizing
 */

import { useState, useEffect, useCallback, type RefObject } from 'react';

/**
 * Chart dimensions returned by the hook
 */
export interface ChartDimensions {
  /** Container width in pixels */
  width: number;
  /** Calculated height in pixels */
  height: number;
  /** True if viewport is mobile (< 768px) */
  isMobile: boolean;
  /** True if viewport is compact (< 400px) */
  isCompact: boolean;
}

/**
 * Configuration options for useChartDimensions
 */
export interface UseChartDimensionsOptions {
  /** Minimum height in pixels (default: 150) */
  minHeight?: number;
  /** Maximum height in pixels (default: 400) */
  maxHeight?: number;
  /** Aspect ratio width/height for height calculation (default: 16/9) */
  aspectRatio?: number;
  /** Fixed height that overrides aspect ratio calculation */
  fixedHeight?: number;
  /** Debounce delay in milliseconds (default: 100) */
  debounceMs?: number;
}

/** Mobile viewport max height constraint */
const MOBILE_MAX_HEIGHT = 220;

/** Compact viewport max height constraint */
const COMPACT_MAX_HEIGHT = 180;

/** Mobile viewport breakpoint */
const MOBILE_BREAKPOINT = 768;

/** Compact viewport breakpoint */
const COMPACT_BREAKPOINT = 400;

/**
 * Custom hook that provides responsive chart dimensions
 *
 * @param containerRef - Ref to the container element
 * @param options - Configuration options
 * @returns Chart dimensions object
 *
 * @example
 * ```tsx
 * const containerRef = useRef<HTMLDivElement>(null);
 * const { width, height, isMobile, isCompact } = useChartDimensions(containerRef, {
 *   minHeight: 150,
 *   maxHeight: 400,
 *   aspectRatio: 16 / 9,
 * });
 *
 * return (
 *   <div ref={containerRef}>
 *     <Chart width={width} height={height} />
 *   </div>
 * );
 * ```
 */
export function useChartDimensions(
  containerRef: RefObject<HTMLElement | null>,
  options: UseChartDimensionsOptions = {}
): ChartDimensions {
  const {
    minHeight = 150,
    maxHeight = 400,
    aspectRatio = 16 / 9,
    fixedHeight,
    debounceMs = 100,
  } = options;

  // State for container width
  const [width, setWidth] = useState(0);

  // State for viewport detection
  const [isMobile, setIsMobile] = useState(false);
  const [isCompact, setIsCompact] = useState(false);

  // Setup media queries for mobile/compact detection
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    const mobileQuery = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);
    const compactQuery = window.matchMedia(`(max-width: ${COMPACT_BREAKPOINT}px)`);

    // Set initial values
    setIsMobile(mobileQuery.matches);
    setIsCompact(compactQuery.matches);

    // Handlers for media query changes
    const handleMobileChange = (e: MediaQueryListEvent) => {
      setIsMobile(e.matches);
    };

    const handleCompactChange = (e: MediaQueryListEvent) => {
      setIsCompact(e.matches);
    };

    mobileQuery.addEventListener('change', handleMobileChange);
    compactQuery.addEventListener('change', handleCompactChange);

    return () => {
      mobileQuery.removeEventListener('change', handleMobileChange);
      compactQuery.removeEventListener('change', handleCompactChange);
    };
  }, []);

  // Debounced width setter
  const debouncedSetWidth = useCallback(
    (newWidth: number) => {
      if (debounceMs === 0) {
        setWidth(newWidth);
        return;
      }

      const timeoutId = setTimeout(() => {
        setWidth(newWidth);
      }, debounceMs);

      return timeoutId;
    },
    [debounceMs]
  );

  // Setup ResizeObserver for container size changes
  useEffect(() => {
    const element = containerRef.current;

    if (!element) {
      return;
    }

    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;

      const newWidth = entry.contentRect.width;

      // Clear previous timeout if exists
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      if (debounceMs === 0) {
        setWidth(newWidth);
      } else {
        timeoutId = setTimeout(() => {
          setWidth(newWidth);
        }, debounceMs);
      }
    });

    resizeObserver.observe(element);

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      resizeObserver.disconnect();
    };
  }, [containerRef, debounceMs, debouncedSetWidth]);

  // Calculate height based on options and viewport
  const calculateHeight = useCallback((): number => {
    // Use fixed height if provided
    if (fixedHeight !== undefined) {
      return fixedHeight;
    }

    // Calculate height from aspect ratio
    const calculatedHeight = width / aspectRatio;

    // Determine effective max height based on viewport
    let effectiveMaxHeight = maxHeight;
    if (isCompact) {
      effectiveMaxHeight = Math.min(maxHeight, COMPACT_MAX_HEIGHT);
    } else if (isMobile) {
      effectiveMaxHeight = Math.min(maxHeight, MOBILE_MAX_HEIGHT);
    }

    // Apply constraints
    return Math.max(minHeight, Math.min(calculatedHeight, effectiveMaxHeight));
  }, [width, fixedHeight, aspectRatio, maxHeight, minHeight, isMobile, isCompact]);

  return {
    width,
    height: calculateHeight(),
    isMobile,
    isCompact,
  };
}

export default useChartDimensions;
