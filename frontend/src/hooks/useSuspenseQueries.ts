/**
 * useSuspenseQueries - Suspense-enabled query hooks (NEM-3360)
 *
 * This module provides useSuspenseQuery versions of critical queries.
 * These hooks integrate with React Suspense for declarative loading states.
 *
 * ## When to use Suspense queries
 *
 * - Critical data required for initial page render
 * - Data that should block rendering until available
 * - When using React 18+ Suspense boundaries
 *
 * ## Architecture
 *
 * Each suspense hook wraps a regular query with useSuspenseQuery.
 * The data is guaranteed to be available when the component renders,
 * eliminating the need for loading state checks.
 *
 * @see https://tanstack.com/query/latest/docs/framework/react/reference/useSuspenseQuery
 * @module hooks/useSuspenseQueries
 */

import { useSuspenseQuery, useSuspenseInfiniteQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { FULL_HEALTH_QUERY_KEY } from './useFullHealthQuery';
import { fetchSettings, type SettingsResponse } from './useSettingsApi';
import {
  fetchCameras,
  fetchFullHealth,
  fetchEvents,
  fetchNotificationPreferences,
  type Camera,
  type FullHealthResponse,
  type EventListResponse,
  type NotificationPreferencesResponse,
  type EventsQueryParams,
} from '../services/api';
import {
  queryKeys,
  DEFAULT_STALE_TIME,
  REALTIME_STALE_TIME,
  STATIC_STALE_TIME,
} from '../services/queryClient';

import type { InfiniteData, QueryKey } from '@tanstack/react-query';

// ============================================================================
// useSuspenseCamerasQuery - Cameras with Suspense
// ============================================================================

/**
 * Options for useSuspenseCamerasQuery
 */
export interface UseSuspenseCamerasQueryOptions {
  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for useSuspenseCamerasQuery
 */
export interface UseSuspenseCamerasQueryReturn {
  /** List of cameras (guaranteed to be available) */
  cameras: Camera[];
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Suspense-enabled hook to fetch all cameras.
 *
 * This hook suspends rendering until camera data is available.
 * Wrap the consuming component in a Suspense boundary.
 *
 * @param options - Configuration options
 * @returns Camera list (guaranteed available)
 *
 * @example
 * ```tsx
 * // Parent component with Suspense boundary
 * <Suspense fallback={<CameraGridSkeleton />}>
 *   <CameraGrid />
 * </Suspense>
 *
 * // Child component using suspense query
 * function CameraGrid() {
 *   const { cameras } = useSuspenseCamerasQuery();
 *   // cameras is guaranteed to be available here
 *   return cameras.map(cam => <CameraCard key={cam.id} camera={cam} />);
 * }
 * ```
 */
export function useSuspenseCamerasQuery(
  options: UseSuspenseCamerasQueryOptions = {}
): UseSuspenseCamerasQueryReturn {
  const { staleTime = DEFAULT_STALE_TIME } = options;

  const query = useSuspenseQuery({
    queryKey: queryKeys.cameras.list(),
    queryFn: fetchCameras,
    staleTime,
  });

  return {
    cameras: query.data,
    isRefetching: query.isRefetching,
    refetch: query.refetch,
  };
}

// ============================================================================
// useSuspenseHealthQuery - System Health with Suspense
// ============================================================================

/**
 * Options for useSuspenseHealthQuery
 */
export interface UseSuspenseHealthQueryOptions {
  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for useSuspenseHealthQuery
 */
export interface UseSuspenseHealthQueryReturn {
  /** Full health status (guaranteed to be available) */
  health: FullHealthResponse;
  /** Whether the system is ready */
  isReady: boolean;
  /** Overall status message */
  statusMessage: string;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Suspense-enabled hook to fetch system health status.
 *
 * This hook suspends rendering until health data is available.
 * Ideal for status indicators that must show accurate data.
 *
 * @param options - Configuration options
 * @returns Health status (guaranteed available)
 *
 * @example
 * ```tsx
 * <Suspense fallback={<StatusSkeleton />}>
 *   <SystemStatus />
 * </Suspense>
 *
 * function SystemStatus() {
 *   const { health, isReady, statusMessage } = useSuspenseHealthQuery();
 *   return <StatusBadge ready={isReady} message={statusMessage} />;
 * }
 * ```
 */
export function useSuspenseHealthQuery(
  options: UseSuspenseHealthQueryOptions = {}
): UseSuspenseHealthQueryReturn {
  const { staleTime = REALTIME_STALE_TIME } = options;

  const query = useSuspenseQuery({
    queryKey: FULL_HEALTH_QUERY_KEY,
    queryFn: fetchFullHealth,
    staleTime,
  });

  return {
    health: query.data,
    isReady: query.data.ready,
    statusMessage: query.data.message,
    isRefetching: query.isRefetching,
    refetch: query.refetch,
  };
}

// ============================================================================
// useSuspenseSettingsQuery - Settings with Suspense
// ============================================================================

/**
 * Options for useSuspenseSettingsQuery
 */
export interface UseSuspenseSettingsQueryOptions {
  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for useSuspenseSettingsQuery
 */
export interface UseSuspenseSettingsQueryReturn {
  /** Current settings (guaranteed to be available) */
  settings: SettingsResponse;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Suspense-enabled hook to fetch system settings.
 *
 * This hook suspends rendering until settings are available.
 * Use for settings pages where data must be present before render.
 *
 * @param options - Configuration options
 * @returns Settings (guaranteed available)
 *
 * @example
 * ```tsx
 * <Suspense fallback={<SettingsFormSkeleton />}>
 *   <SettingsForm />
 * </Suspense>
 *
 * function SettingsForm() {
 *   const { settings } = useSuspenseSettingsQuery();
 *   return (
 *     <form>
 *       <input defaultValue={settings.detection.confidence_threshold} />
 *     </form>
 *   );
 * }
 * ```
 */
export function useSuspenseSettingsQuery(
  options: UseSuspenseSettingsQueryOptions = {}
): UseSuspenseSettingsQueryReturn {
  const { staleTime = STATIC_STALE_TIME } = options;

  const query = useSuspenseQuery({
    queryKey: ['settings', 'current'],
    queryFn: fetchSettings,
    staleTime,
  });

  return {
    settings: query.data,
    isRefetching: query.isRefetching,
    refetch: query.refetch,
  };
}

// ============================================================================
// useSuspenseNotificationPreferencesQuery - Notification Prefs with Suspense
// ============================================================================

/**
 * Options for useSuspenseNotificationPreferencesQuery
 */
export interface UseSuspenseNotificationPreferencesQueryOptions {
  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for useSuspenseNotificationPreferencesQuery
 */
export interface UseSuspenseNotificationPreferencesQueryReturn {
  /** Notification preferences (guaranteed to be available) */
  preferences: NotificationPreferencesResponse;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Suspense-enabled hook to fetch notification preferences.
 *
 * @param options - Configuration options
 * @returns Notification preferences (guaranteed available)
 */
export function useSuspenseNotificationPreferencesQuery(
  options: UseSuspenseNotificationPreferencesQueryOptions = {}
): UseSuspenseNotificationPreferencesQueryReturn {
  const { staleTime = DEFAULT_STALE_TIME } = options;

  const query = useSuspenseQuery({
    queryKey: queryKeys.notifications.preferences.global,
    queryFn: fetchNotificationPreferences,
    staleTime,
  });

  return {
    preferences: query.data,
    isRefetching: query.isRefetching,
    refetch: query.refetch,
  };
}

// ============================================================================
// useSuspenseEventsInfiniteQuery - Events with Suspense
// ============================================================================

/**
 * Options for useSuspenseEventsInfiniteQuery
 */
export interface UseSuspenseEventsInfiniteQueryOptions {
  /**
   * Filter parameters for events
   */
  filters?: {
    camera_id?: string;
    risk_level?: string;
    start_date?: string;
    end_date?: string;
  };

  /**
   * Number of events per page.
   * @default 25
   */
  limit?: number;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for useSuspenseEventsInfiniteQuery
 */
export interface UseSuspenseEventsInfiniteQueryReturn {
  /** All events from all loaded pages (guaranteed to have at least first page) */
  events: EventListResponse['items'];
  /** Total count of events */
  totalCount: number;
  /** Whether there are more pages to load */
  hasNextPage: boolean;
  /** Function to fetch next page */
  fetchNextPage: () => void;
  /** Whether next page is being fetched */
  isFetchingNextPage: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Suspense-enabled hook to fetch events with infinite pagination.
 *
 * This hook suspends until the first page of events is available.
 *
 * @param options - Configuration options
 * @returns Events data (first page guaranteed available)
 */
export function useSuspenseEventsInfiniteQuery(
  options: UseSuspenseEventsInfiniteQueryOptions = {}
): UseSuspenseEventsInfiniteQueryReturn {
  const { filters, limit = 25, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useSuspenseInfiniteQuery<
    EventListResponse,
    Error,
    InfiniteData<EventListResponse, string | null>,
    QueryKey,
    string | null
  >({
    queryKey: ['events', 'infinite', { filters, limit }],
    queryFn: async ({ pageParam }) => {
      const params: EventsQueryParams = {
        ...filters,
        limit,
        cursor: pageParam ?? undefined,
      };
      return fetchEvents(params);
    },
    initialPageParam: null,
    getNextPageParam: (lastPage) => {
      if (lastPage.pagination.has_more && lastPage.pagination.next_cursor) {
        return lastPage.pagination.next_cursor;
      }
      return undefined;
    },
    staleTime,
  });

  const events = useMemo(() => {
    return query.data.pages.flatMap((page) => page.items);
  }, [query.data.pages]);

  const totalCount = useMemo(() => {
    return query.data.pages[0]?.pagination.total ?? 0;
  }, [query.data.pages]);

  return {
    events,
    totalCount,
    hasNextPage: query.hasNextPage,
    fetchNextPage: () => void query.fetchNextPage(),
    isFetchingNextPage: query.isFetchingNextPage,
    isRefetching: query.isRefetching,
    refetch: query.refetch,
  };
}
