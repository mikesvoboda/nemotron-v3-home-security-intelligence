/**
 * usePrefersReducedMotion - Hook for detecting reduced motion preference
 *
 * Uses MediaQueryList API to detect if user prefers reduced motion.
 * Updates reactively when preference changes.
 *
 * @see https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
 */

import { useState, useEffect } from 'react';

/** Media query string for detecting reduced motion preference */
const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

/**
 * Get the initial reduced motion preference value.
 * Safe for SSR - returns false if window is not available.
 */
function getInitialValue(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return false;
  }
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

/**
 * Custom hook that detects user's reduced motion preference
 *
 * @returns boolean indicating if user prefers reduced motion
 *
 * @example
 * ```tsx
 * function AnimatedComponent() {
 *   const prefersReducedMotion = usePrefersReducedMotion();
 *
 *   return (
 *     <div className={prefersReducedMotion ? '' : 'animate-pulse'}>
 *       Content
 *     </div>
 *   );
 * }
 * ```
 */
export function usePrefersReducedMotion(): boolean {
  // Use lazy initialization to get the correct initial value
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(getInitialValue);

  useEffect(() => {
    // Check if we're in a browser environment
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    // Create media query
    const mediaQuery = window.matchMedia(REDUCED_MOTION_QUERY);

    // Define handler for media query changes
    const handleChange = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    // Add event listener for preference changes
    mediaQuery.addEventListener('change', handleChange);

    // Cleanup listener on unmount
    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, []);

  return prefersReducedMotion;
}

export default usePrefersReducedMotion;
