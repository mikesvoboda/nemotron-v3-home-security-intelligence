/**
 * useIsMobile - Hook for detecting mobile viewport
 *
 * Uses MediaQueryList API to detect if viewport is below mobile breakpoint.
 * Updates reactively when viewport size changes.
 *
 * @deprecated Consider using useViewport() for more granular control including
 * isMobile, isTablet, and isDesktop detection.
 */

import { useState, useEffect } from 'react';

// Re-export useViewport for easier migration
export { useViewport, BREAKPOINTS } from './useViewport';
export type { ViewportInfo, Breakpoint } from './useViewport';

/**
 * Custom hook that detects mobile viewport based on max-width breakpoint
 *
 * @param breakpoint - Maximum width in pixels to consider as mobile (default: 768px)
 * @returns boolean indicating if current viewport is mobile
 *
 * @deprecated Consider using useViewport() for more granular control:
 * - useViewport().isMobile - screens < 640px
 * - useViewport().isTablet - screens 640px - 1023px
 * - useViewport().isDesktop - screens >= 1024px
 */
export function useIsMobile(breakpoint: number = 768): boolean {
  // Initialize with false for SSR safety
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    // Check if we're in a browser environment
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    // Create media query
    const mediaQuery = window.matchMedia(`(max-width: ${breakpoint}px)`);

    // Set initial value
    setIsMobile(mediaQuery.matches);

    // Define handler for media query changes
    const handleChange = (e: MediaQueryListEvent) => {
      setIsMobile(e.matches);
    };

    // Add event listener
    mediaQuery.addEventListener('change', handleChange);

    // Cleanup listener on unmount
    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, [breakpoint]);

  return isMobile;
}

export default useIsMobile;
