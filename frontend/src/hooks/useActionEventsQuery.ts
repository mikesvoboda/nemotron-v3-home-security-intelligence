/**
 * useActionEventsQuery - TanStack Query hook for X-CLIP action events
 *
 * This hook provides a TanStack Query wrapper around the action events API
 * with support for filtering by camera, action type, and time range.
 *
 * Used in EventDetailModal to display action recognition results for security events.
 *
 * @module hooks/useActionEventsQuery
 * @see backend/api/routes/action_events.py
 * Linear issue: NEM-5024 (Phase 7)
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchActionEvents,
  fetchActionEventsForEvent,
  fetchSuspiciousActions,
  type ActionEvent,
  type ActionEventListResponse,
  type ActionEventsQueryParams,
} from '../services/actionEventsApi';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useActionEventsQuery hook
 */
export interface UseActionEventsQueryOptions {
  /**
   * Filter by camera ID
   */
  cameraId?: string;

  /**
   * Filter by action type (e.g., 'walking normally', 'climbing')
   */
  action?: string;

  /**
   * Filter by suspicious flag
   */
  isSuspicious?: boolean;

  /**
   * Filter by minimum confidence score (0.0 to 1.0)
   */
  minConfidence?: number;

  /**
   * Filter by start time (ISO format)
   */
  startTime?: string;

  /**
   * Filter by end time (ISO format)
   */
  endTime?: string;

  /**
   * Maximum number of results to return
   * @default 50
   */
  limit?: number;

  /**
   * Whether to enable the query
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds
   * Set to false to disable automatic refetching
   * @default false (no auto-refresh for action events)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useActionEventsQuery hook
 */
export interface UseActionEventsQueryReturn {
  /** Action event list response from the API */
  data: ActionEventListResponse | undefined;
  /** List of action events, empty array if not yet fetched */
  actionEvents: ActionEvent[];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the data is stale */
  isStale: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Total count of action events matching the filter */
  totalCount: number;
  /** Whether there are more action events to load */
  hasMore: boolean;
}

// ============================================================================
// useActionEventsQuery Hook
// ============================================================================

/**
 * Hook to fetch action events using TanStack Query.
 *
 * Provides filtering by camera, action type, suspicious flag, and time range.
 *
 * @param options - Configuration options
 * @returns Action event list data and query state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { actionEvents, isLoading, error } = useActionEventsQuery();
 *
 * // With filters
 * const { actionEvents } = useActionEventsQuery({
 *   cameraId: 'front_door',
 *   isSuspicious: true,
 *   minConfidence: 0.8,
 * });
 * ```
 */
export function useActionEventsQuery(
  options: UseActionEventsQueryOptions = {}
): UseActionEventsQueryReturn {
  const {
    cameraId,
    action,
    isSuspicious,
    minConfidence,
    startTime,
    endTime,
    limit = 50,
    enabled = true,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  // Build query params from filter options
  const queryParams: ActionEventsQueryParams = useMemo(() => {
    const params: ActionEventsQueryParams = { limit };

    if (cameraId) {
      params.camera_id = cameraId;
    }

    if (action) {
      params.action = action;
    }

    if (isSuspicious !== undefined) {
      params.is_suspicious = isSuspicious;
    }

    if (minConfidence !== undefined) {
      params.min_confidence = minConfidence;
    }

    if (startTime) {
      params.start_time = startTime;
    }

    if (endTime) {
      params.end_time = endTime;
    }

    return params;
  }, [cameraId, action, isSuspicious, minConfidence, startTime, endTime, limit]);

  // Build the filter object for the query key
  const filterKey = useMemo(() => {
    const filters: Record<string, string | boolean | undefined> = {};
    if (cameraId) filters.camera_id = cameraId;
    if (action) filters.action = action;
    if (isSuspicious !== undefined) filters.is_suspicious = isSuspicious;
    if (startTime) filters.start_time = startTime;
    if (endTime) filters.end_time = endTime;
    return Object.keys(filters).length > 0 ? filters : undefined;
  }, [cameraId, action, isSuspicious, startTime, endTime]);

  const query = useQuery({
    queryKey: queryKeys.actionEvents.list(filterKey),
    queryFn: () => fetchActionEvents(queryParams),
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const actionEvents = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const totalCount = query.data?.pagination?.total ?? 0;
  const hasMore = query.data?.pagination?.has_more ?? false;

  return {
    data: query.data,
    actionEvents,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isStale: query.isStale,
    refetch: query.refetch,
    totalCount,
    hasMore,
  };
}

// ============================================================================
// useActionEventsForEventQuery Hook
// ============================================================================

/**
 * Options for configuring the useActionEventsForEventQuery hook
 */
export interface UseActionEventsForEventQueryOptions {
  /**
   * Security event ID
   */
  eventId: number;

  /**
   * Camera ID for the event
   */
  cameraId: string;

  /**
   * Event start time (ISO format)
   */
  startTime: string;

  /**
   * Event end time (ISO format), optional for ongoing events
   */
  endTime?: string | null;

  /**
   * Maximum number of results to return
   * @default 50
   */
  limit?: number;

  /**
   * Whether to enable the query
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Hook to fetch action events for a specific security event.
 *
 * Uses time correlation to find action events that occurred during the event.
 *
 * @param options - Configuration options
 * @returns Action event list data and query state
 *
 * @example
 * ```tsx
 * const { actionEvents, isLoading } = useActionEventsForEventQuery({
 *   eventId: 123,
 *   cameraId: 'front_door',
 *   startTime: event.started_at || event.timestamp,
 *   endTime: event.ended_at,
 * });
 * ```
 */
export function useActionEventsForEventQuery(
  options: UseActionEventsForEventQueryOptions
): UseActionEventsQueryReturn {
  const {
    eventId,
    cameraId,
    startTime,
    endTime,
    limit = 50,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  const query = useQuery({
    queryKey: queryKeys.actionEvents.forEvent(eventId),
    queryFn: () => fetchActionEventsForEvent(eventId, cameraId, startTime, endTime, limit),
    enabled: enabled && !!eventId && !!cameraId && !!startTime,
    staleTime,
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const actionEvents = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const totalCount = query.data?.pagination?.total ?? 0;
  const hasMore = query.data?.pagination?.has_more ?? false;

  return {
    data: query.data,
    actionEvents,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isStale: query.isStale,
    refetch: query.refetch,
    totalCount,
    hasMore,
  };
}

// ============================================================================
// useSuspiciousActionsQuery Hook
// ============================================================================

/**
 * Options for configuring the useSuspiciousActionsQuery hook
 */
export interface UseSuspiciousActionsQueryOptions {
  /**
   * Filter by camera ID
   */
  cameraId?: string;

  /**
   * Filter by minimum confidence score (0.0 to 1.0)
   */
  minConfidence?: number;

  /**
   * Filter by start time (ISO format)
   */
  startTime?: string;

  /**
   * Filter by end time (ISO format)
   */
  endTime?: string;

  /**
   * Maximum number of results to return
   * @default 50
   */
  limit?: number;

  /**
   * Whether to enable the query
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds
   * Set to false to disable automatic refetching
   * @default 30000 (30 seconds for suspicious actions monitoring)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for the useSuspiciousActionsQuery hook
 */
export interface UseSuspiciousActionsQueryReturn extends UseActionEventsQueryReturn {
  /** Count of suspicious actions */
  suspiciousCount: number;
  /** Total count of all action events (including non-suspicious) */
  totalActionCount: number;
}

/**
 * Hook to fetch suspicious action events only.
 *
 * Includes counts of suspicious vs total events for monitoring dashboards.
 *
 * @param options - Configuration options
 * @returns Suspicious actions data with counts and query state
 *
 * @example
 * ```tsx
 * const { actionEvents, suspiciousCount, totalActionCount, isLoading } =
 *   useSuspiciousActionsQuery({
 *     cameraId: 'back_yard',
 *     minConfidence: 0.9,
 *   });
 *
 * console.log(`${suspiciousCount} of ${totalActionCount} actions are suspicious`);
 * ```
 */
export function useSuspiciousActionsQuery(
  options: UseSuspiciousActionsQueryOptions = {}
): UseSuspiciousActionsQueryReturn {
  const {
    cameraId,
    minConfidence,
    startTime,
    endTime,
    limit = 50,
    enabled = true,
    refetchInterval = 30000,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  // Build filter key for query key
  const filterKey = useMemo(() => {
    const filters: Record<string, string | number | undefined> = {};
    if (cameraId) filters.camera_id = cameraId;
    if (minConfidence !== undefined) filters.min_confidence = minConfidence;
    return Object.keys(filters).length > 0 ? filters : undefined;
  }, [cameraId, minConfidence]);

  const query = useQuery({
    queryKey: queryKeys.actionEvents.suspicious(filterKey),
    queryFn: () =>
      fetchSuspiciousActions({
        camera_id: cameraId,
        min_confidence: minConfidence,
        start_time: startTime,
        end_time: endTime,
        limit,
      }),
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  // Type assertion for the response
  const data = query.data;

  // Provide empty array as default to avoid null checks
  const actionEvents = useMemo(() => data?.items ?? [], [data?.items]);
  const totalCount = data?.pagination?.total ?? 0;
  const hasMore = data?.pagination?.has_more ?? false;
  const suspiciousCount = data?.suspicious_count ?? 0;
  const totalActionCount = data?.total_count ?? 0;

  return {
    data,
    actionEvents,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isStale: query.isStale,
    refetch: query.refetch,
    totalCount,
    hasMore,
    suspiciousCount,
    totalActionCount,
  };
}
