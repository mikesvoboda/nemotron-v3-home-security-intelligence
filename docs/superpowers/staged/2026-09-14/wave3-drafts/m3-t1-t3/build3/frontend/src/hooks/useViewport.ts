/**
 * useViewport - Hook for detecting viewport size with multiple breakpoint support
 *
 * Uses MediaQueryList API to detect viewport breakpoints.
 * Updates reactively when viewport size changes.
 *
 * Breakpoints (based on Tailwind CSS defaults):
 * - sm: 640px
 * - md: 768px
 * - lg: 1024px
 * - xl: 1280px
 * - 2xl: 1536px
 *
 * Viewport categories:
 * - isMobile: < 640px (phones)
 * - isTablet: 640px - 1023px (tablets in portrait/landscape)
 * - isDesktop: >= 1024px (desktop/laptop)
 */

import { useState, useEffect, useMemo } from 'react';

/**
 * Tailwind CSS breakpoint thresholds in pixels
 */
export const BREAKPOINTS = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const;

/**
 * Breakpoint name type
 */
export type Breakpoint = 'sm' | 'md' | 'lg' | 'xl' | '2xl';

/**
 * Viewport information returned by the hook
 */
export interface ViewportInfo {
  /** Viewport width < 640px (small mobile devices) */
  isMobile: boolean;
  /** Viewport width 640px - 1023px (tablets, small laptops) */
  isTablet: boolean;
  /** Viewport width >= 1024px (desktop/laptop) */
  isDesktop: boolean;
  /** Current viewport width in pixels */
  width: number;
  /** Current active Tailwind breakpoint */
  breakpoint: Breakpoint;
}

/**
 * Determines the current Tailwind breakpoint based on viewport width
 */
function getBreakpoint(width: number): Breakpoint {
  if (width >= BREAKPOINTS['2xl']) return '2xl';
  if (width >= BREAKPOINTS.xl) return 'xl';
  if (width >= BREAKPOINTS.lg) return 'lg';
  if (width >= BREAKPOINTS.md) return 'md';
  return 'sm';
}

/**
 * Custom hook that provides comprehensive viewport information
 *
 * @returns ViewportInfo object with device type booleans, width, and breakpoint
 *
 * @example
 * ```tsx
 * function ResponsiveComponent() {
 *   const { isMobile, isTablet, isDesktop, breakpoint } = useViewport();
 *
 *   if (isMobile) return <MobileLayout />;
 *   if (isTablet) return <TabletLayout />;
 *   return <DesktopLayout />;
 * }
 * ```
 */
export function useViewport(): ViewportInfo {
  // Initialize with safe defaults for SSR
  const [width, setWidth] = useState<number>(() => {
    if (typeof window === 'undefined') return BREAKPOINTS.lg; // Default to desktop for SSR
    return window.innerWidth;
  });

  useEffect(() => {
    // Check if we're in a browser environment
    if (typeof window === 'undefined') {
      return;
    }

    // Set initial width
    setWidth(window.innerWidth);

    // Create resize handler with requestAnimationFrame for performance
    let rafId: number;
    const handleResize = () => {
      // Cancel any pending animation frame
      if (rafId) {
        cancelAnimationFrame(rafId);
      }
      // Throttle updates using requestAnimationFrame
      rafId = requestAnimationFrame(() => {
        setWidth(window.innerWidth);
      });
    };

    // Add event listener
    window.addEventListener('resize', handleResize);

    // Cleanup listener on unmount
    return () => {
      window.removeEventListener('resize', handleResize);
      if (rafId) {
        cancelAnimationFrame(rafId);
      }
    };
  }, []);

  // Memoize the computed viewport info to prevent unnecessary re-renders
  const viewportInfo = useMemo((): ViewportInfo => {
    const isMobile = width < BREAKPOINTS.sm;
    const isTablet = width >= BREAKPOINTS.sm && width < BREAKPOINTS.lg;
    const isDesktop = width >= BREAKPOINTS.lg;
    const breakpoint = getBreakpoint(width);

    return {
      isMobile,
      isTablet,
      isDesktop,
      width,
      breakpoint,
    };
  }, [width]);

  return viewportInfo;
}

export default useViewport;
