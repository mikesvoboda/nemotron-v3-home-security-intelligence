/**
 * Route-based Query Prefetching System (NEM-3359)
 *
 * Provides prefetching utilities for TanStack Query to preload data
 * before navigation completes, improving perceived performance.
 *
 * ## Architecture
 *
 * 1. **Route Prefetch Configs**: Define which queries to prefetch for each route
 * 2. **Prefetch on Hover/Focus**: Trigger prefetching when links are hovered
 * 3. **Prefetch on Route Load**: Prefetch related routes on page load
 *
 * @see https://tanstack.com/query/latest/docs/framework/react/guides/prefetching
 * @module services/routePrefetching
 */

import { fetchCameras, fetchFullHealth, fetchEvents, fetchNotificationPreferences } from './api';
import {
  queryKeys,
  DEFAULT_STALE_TIME,
  REALTIME_STALE_TIME,
  STATIC_STALE_TIME,
} from './queryClient';
import { fetchSettings } from '../hooks/useSettingsApi';

import type { EventsQueryParams } from './api';
import type { QueryClient } from '@tanstack/react-query';

// ============================================================================
// Route Prefetch Configuration
// ============================================================================

/**
 * Configuration for a single prefetch operation
 */
export interface PrefetchConfig {
  /** Query key to use for caching */
  queryKey: readonly unknown[];
  /** Function to fetch the data */
  queryFn: () => Promise<unknown>;
  /** Stale time in milliseconds (data won't be refetched if newer than this) */
  staleTime?: number;
}

/**
 * Map of routes to their prefetch configurations.
 * Each route can prefetch multiple queries.
 */
export const routePrefetchConfigs: Record<string, PrefetchConfig[]> = {
  '/': [
    // Dashboard prefetches cameras and health for initial render
    {
      queryKey: queryKeys.cameras.list(),
      queryFn: fetchCameras,
      staleTime: DEFAULT_STALE_TIME,
    },
    {
      queryKey: ['system', 'health', 'full'],
      queryFn: fetchFullHealth,
      staleTime: REALTIME_STALE_TIME,
    },
  ],
  '/timeline': [
    // Timeline prefetches recent events
    {
      queryKey: queryKeys.events.list(),
      queryFn: () => fetchEvents({ limit: 25 } as EventsQueryParams),
      staleTime: DEFAULT_STALE_TIME,
    },
  ],
  '/alerts': [
    // Alerts prefetches high-risk events
    {
      queryKey: ['alerts', 'infinite', { riskLevel: 'high', limit: 25 }],
      queryFn: () => fetchEvents({ risk_level: 'high', limit: 25 } as EventsQueryParams),
      staleTime: DEFAULT_STALE_TIME,
    },
    {
      queryKey: ['alerts', 'infinite', { riskLevel: 'critical', limit: 25 }],
      queryFn: () => fetchEvents({ risk_level: 'critical', limit: 25 } as EventsQueryParams),
      staleTime: DEFAULT_STALE_TIME,
    },
  ],
  '/settings': [
    // Settings prefetches settings and notification preferences
    {
      queryKey: ['settings', 'current'],
      queryFn: fetchSettings,
      staleTime: STATIC_STALE_TIME,
    },
    {
      queryKey: queryKeys.notifications.preferences.global,
      queryFn: fetchNotificationPreferences,
      staleTime: DEFAULT_STALE_TIME,
    },
  ],
  '/notifications': [
    // Notification preferences page
    {
      queryKey: queryKeys.notifications.preferences.global,
      queryFn: fetchNotificationPreferences,
      staleTime: DEFAULT_STALE_TIME,
    },
  ],
  '/operations': [
    // Operations page prefetches health status
    {
      queryKey: ['system', 'health', 'full'],
      queryFn: fetchFullHealth,
      staleTime: REALTIME_STALE_TIME,
    },
    {
      queryKey: queryKeys.cameras.list(),
      queryFn: fetchCameras,
      staleTime: DEFAULT_STALE_TIME,
    },
  ],
};

// ============================================================================
// Prefetch Functions
// ============================================================================

/**
 * Prefetch all queries for a specific route.
 *
 * This function queues prefetch requests for all queries associated with a route.
 * Data is fetched in the background without blocking navigation.
 *
 * @param queryClient - TanStack Query client instance
 * @param route - Route path to prefetch data for
 *
 * @example
 * ```tsx
 * const queryClient = useQueryClient();
 *
 * // Prefetch dashboard data on link hover
 * <Link
 *   to="/"
 *   onMouseEnter={() => prefetchRoute(queryClient, '/')}
 * >
 *   Dashboard
 * </Link>
 * ```
 */
export function prefetchRoute(queryClient: QueryClient, route: string): void {
  const configs = routePrefetchConfigs[route];
  if (!configs) {
    return;
  }

  for (const config of configs) {
    void queryClient.prefetchQuery({
      queryKey: config.queryKey,
      queryFn: config.queryFn,
      staleTime: config.staleTime ?? DEFAULT_STALE_TIME,
    });
  }
}

/**
 * Prefetch a single query by key and function.
 *
 * Use this for custom prefetching scenarios not covered by route configs.
 *
 * @param queryClient - TanStack Query client instance
 * @param config - Prefetch configuration
 *
 * @example
 * ```tsx
 * // Prefetch a specific camera's data
 * prefetchQuery(queryClient, {
 *   queryKey: queryKeys.cameras.detail(cameraId),
 *   queryFn: () => fetchCamera(cameraId),
 *   staleTime: DEFAULT_STALE_TIME,
 * });
 * ```
 */
export function prefetchQuery(queryClient: QueryClient, config: PrefetchConfig): void {
  void queryClient.prefetchQuery({
    queryKey: config.queryKey,
    queryFn: config.queryFn,
    staleTime: config.staleTime ?? DEFAULT_STALE_TIME,
  });
}

/**
 * Prefetch multiple routes at once.
 *
 * Useful for prefetching related routes when a page loads.
 *
 * @param queryClient - TanStack Query client instance
 * @param routes - Array of route paths to prefetch
 *
 * @example
 * ```tsx
 * // On dashboard load, prefetch likely next destinations
 * useEffect(() => {
 *   prefetchRoutes(queryClient, ['/timeline', '/alerts']);
 * }, [queryClient]);
 * ```
 */
export function prefetchRoutes(queryClient: QueryClient, routes: string[]): void {
  for (const route of routes) {
    prefetchRoute(queryClient, route);
  }
}

/**
 * Get the list of routes that should be prefetched when on a given route.
 *
 * These are common navigation patterns (e.g., dashboard -> timeline).
 *
 * @param currentRoute - Current route path
 * @returns Array of routes to prefetch
 */
export function getRelatedRoutes(currentRoute: string): string[] {
  const relatedRoutes: Record<string, string[]> = {
    '/': ['/timeline', '/alerts', '/settings'],
    '/timeline': ['/', '/alerts'],
    '/alerts': ['/', '/timeline'],
    '/settings': ['/notifications', '/'],
    '/operations': ['/', '/ai'],
    '/ai': ['/operations'],
    '/entities': ['/timeline'],
    '/analytics': ['/timeline'],
  };

  return relatedRoutes[currentRoute] ?? [];
}

// Type export is handled at interface definition
