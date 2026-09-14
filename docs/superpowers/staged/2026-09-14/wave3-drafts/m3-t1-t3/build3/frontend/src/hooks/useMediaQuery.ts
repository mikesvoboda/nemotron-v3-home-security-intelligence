/**
 * useMediaQuery - Generic media query hook with convenience wrappers
 *
 * Provides a flexible API for detecting media queries and viewport conditions.
 * Includes convenience hooks for common mobile and touch detection patterns.
 */

import { useState, useEffect, useCallback } from 'react';

/**
 * Custom hook that subscribes to a CSS media query and returns whether it matches.
 *
 * @param query - CSS media query string (e.g., '(max-width: 768px)', '(pointer: coarse)')
 * @returns boolean indicating if the media query currently matches
 *
 * @example
 * ```tsx
 * const isDarkMode = useMediaQuery('(prefers-color-scheme: dark)');
 * const isLandscape = useMediaQuery('(orientation: landscape)');
 * ```
 */
export function useMediaQuery(query: string): boolean {
  // Initialize with false for SSR safety
  const [matches, setMatches] = useState(false);

  const updateMatches = useCallback((e: MediaQueryListEvent | MediaQueryList) => {
    setMatches(e.matches);
  }, []);

  useEffect(() => {
    // Check if we're in a browser environment
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    // Create media query
    const mediaQuery = window.matchMedia(query);

    // Set initial value
    updateMatches(mediaQuery);

    // Define handler for media query changes
    const handleChange = (e: MediaQueryListEvent) => {
      updateMatches(e);
    };

    // Add event listener
    mediaQuery.addEventListener('change', handleChange);

    // Cleanup listener on unmount
    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, [query, updateMatches]);

  return matches;
}

/**
 * Mobile breakpoint in pixels (matches Tailwind's md breakpoint)
 */
export const MOBILE_BREAKPOINT = 768;

/**
 * Custom hook that detects mobile viewport based on max-width breakpoint.
 * Uses 768px as the default breakpoint (Tailwind's md).
 *
 * @param breakpoint - Maximum width in pixels to consider as mobile (default: 768px)
 * @returns boolean indicating if current viewport is mobile
 *
 * @example
 * ```tsx
 * const isMobile = useIsMobile();
 * // Or with custom breakpoint
 * const isSmallMobile = useIsMobile(480);
 * ```
 */
export function useIsMobile(breakpoint: number = MOBILE_BREAKPOINT): boolean {
  return useMediaQuery(`(max-width: ${breakpoint}px)`);
}

/**
 * Custom hook that detects if the device has a coarse pointer (touch input).
 * This is more reliable than viewport width for detecting touch devices
 * as it accounts for tablets in desktop mode.
 *
 * @returns boolean indicating if device uses touch input
 *
 * @example
 * ```tsx
 * const isTouch = useIsTouch();
 * // Use for touch-specific interactions like drag gestures
 * ```
 */
export function useIsTouch(): boolean {
  return useMediaQuery('(pointer: coarse)');
}

/**
 * Custom hook that detects if user prefers reduced motion.
 * Useful for disabling animations for accessibility.
 *
 * @returns boolean indicating if user prefers reduced motion
 */
export function usePrefersReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}

export default useMediaQuery;
