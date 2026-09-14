/**
 * useRoutePrefetch - Hook for route-based query prefetching (NEM-3359)
 *
 * Provides a hook interface for prefetching queries based on navigation patterns.
 * Supports hover/focus prefetching for links and automatic prefetching of related routes.
 *
 * @module hooks/useRoutePrefetch
 */

import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

import {
  prefetchRoute,
  prefetchRoutes,
  getRelatedRoutes,
  type PrefetchConfig,
} from '../services/routePrefetching';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring useRoutePrefetch hook
 */
export interface UseRoutePrefetchOptions {
  /**
   * Whether to automatically prefetch related routes on mount.
   * @default true
   */
  prefetchRelated?: boolean;

  /**
   * Delay in milliseconds before prefetching related routes.
   * Prevents prefetching during rapid navigation.
   * @default 1000
   */
  relatedPrefetchDelay?: number;

  /**
   * Custom routes to prefetch regardless of current route.
   */
  customRoutes?: string[];
}

/**
 * Return type for useRoutePrefetch hook
 */
export interface UseRoutePrefetchReturn {
  /**
   * Prefetch queries for a specific route.
   * Call on link hover/focus for instant navigation.
   */
  prefetch: (route: string) => void;

  /**
   * Prefetch a single custom query configuration.
   */
  prefetchQuery: (config: PrefetchConfig) => void;

  /**
   * Get props to spread onto a link element for automatic prefetching.
   * Includes onMouseEnter and onFocus handlers.
   */
  getLinkProps: (route: string) => {
    onMouseEnter: () => void;
    onFocus: () => void;
  };

  /**
   * Whether prefetching is currently enabled.
   * May be disabled during rapid navigation or low network conditions.
   */
  isPrefetchEnabled: boolean;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for prefetching route data to improve navigation performance.
 *
 * Automatically prefetches related routes after page load and provides
 * handlers for prefetching on hover/focus events.
 *
 * @param options - Configuration options
 * @returns Prefetch functions and link props getter
 *
 * @example
 * ```tsx
 * const { prefetch, getLinkProps } = useRoutePrefetch();
 *
 * // Automatic prefetch on hover
 * <NavLink to="/timeline" {...getLinkProps('/timeline')}>
 *   Timeline
 * </NavLink>
 *
 * // Manual prefetch
 * const handleShowMenu = () => {
 *   prefetch('/settings');
 *   prefetch('/notifications');
 * };
 * ```
 */
export function useRoutePrefetch(options: UseRoutePrefetchOptions = {}): UseRoutePrefetchReturn {
  const { prefetchRelated = true, relatedPrefetchDelay = 1000, customRoutes } = options;

  const queryClient = useQueryClient();
  const location = useLocation();
  const prefetchedRef = useRef<Set<string>>(new Set());
  const isPrefetchEnabled = useRef(true);

  // Prefetch a single route
  const prefetch = useCallback(
    (route: string) => {
      if (!isPrefetchEnabled.current) {
        return;
      }

      // Skip if already prefetched this session
      if (prefetchedRef.current.has(route)) {
        return;
      }

      prefetchRoute(queryClient, route);
      prefetchedRef.current.add(route);
    },
    [queryClient]
  );

  // Prefetch a custom query
  const prefetchCustomQuery = useCallback(
    (config: PrefetchConfig) => {
      if (!isPrefetchEnabled.current) {
        return;
      }

      const cacheKey = JSON.stringify(config.queryKey);
      if (prefetchedRef.current.has(cacheKey)) {
        return;
      }

      void queryClient.prefetchQuery({
        queryKey: config.queryKey,
        queryFn: config.queryFn,
        staleTime: config.staleTime,
      });
      prefetchedRef.current.add(cacheKey);
    },
    [queryClient]
  );

  // Get props for link elements
  const getLinkProps = useCallback(
    (route: string) => ({
      onMouseEnter: () => prefetch(route),
      onFocus: () => prefetch(route),
    }),
    [prefetch]
  );

  // Prefetch related routes after page load
  useEffect(() => {
    if (!prefetchRelated) {
      return;
    }

    // Clear prefetched set on route change to allow re-prefetching
    prefetchedRef.current.clear();

    const timeoutId = setTimeout(() => {
      const relatedRoutes = getRelatedRoutes(location.pathname);
      const routesToPrefetch = customRoutes
        ? [...new Set([...relatedRoutes, ...customRoutes])]
        : relatedRoutes;

      prefetchRoutes(queryClient, routesToPrefetch);
      routesToPrefetch.forEach((route) => prefetchedRef.current.add(route));
    }, relatedPrefetchDelay);

    return () => clearTimeout(timeoutId);
  }, [location.pathname, prefetchRelated, relatedPrefetchDelay, customRoutes, queryClient]);

  return {
    prefetch,
    prefetchQuery: prefetchCustomQuery,
    getLinkProps,
    isPrefetchEnabled: isPrefetchEnabled.current,
  };
}

export default useRoutePrefetch;
