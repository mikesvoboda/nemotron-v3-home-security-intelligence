/**
 * useFaceEventsQuery - React Query hook for face detection events with infinite scroll
 *
 * This hook provides cursor-based pagination for face detection events using
 * TanStack Query's infinite query capabilities.
 *
 * Features:
 * - Cursor-based pagination for efficient data loading
 * - Automatic request deduplication
 * - Infinite scroll support
 * - Filtering by camera, status (known/unknown), and date range
 * - Auto-refresh at configurable intervals
 *
 * @module hooks/useFaceEventsQuery
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { useMemo } from 'react';

import { useCursorPaginatedQuery } from './useCursorPaginatedQuery';

import type { CursorPaginatedResponse } from './useCursorPaginatedQuery';
import type { FaceDetectionEvent } from '../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

/**
 * Response structure from the face events API.
 * Extends CursorPaginatedResponse to work with useCursorPaginatedQuery.
 */
export interface FaceEventsQueryResponse extends CursorPaginatedResponse {
  /** List of face detection events */
  items: FaceDetectionEvent[];
  /** Pagination information */
  pagination: {
    total: number;
    has_more: boolean;
    next_cursor?: string | null;
  };
}

/**
 * Filter options for the face events query.
 */
export interface FaceEventsQueryFilters {
  /** Filter by camera ID */
  camera_id?: number;
  /** Filter to show only unknown faces */
  unknown_only?: boolean;
  /** Filter known faces only (opposite of unknown_only) */
  known_only?: boolean;
  /** Start date filter (ISO format) */
  start_date?: string;
  /** End date filter (ISO format) */
  end_date?: string;
  /** Minimum quality score */
  min_quality?: number;
}

/**
 * Options for configuring the useFaceEventsQuery hook.
 */
export interface UseFaceEventsQueryOptions {
  /**
   * Filter options for the query
   */
  filters?: FaceEventsQueryFilters;

  /**
   * Number of items per page
   * @default 20
   */
  limit?: number;

  /**
   * Whether to enable the query
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds
   * @default 30000
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default 30000 (30 seconds)
   */
  refetchInterval?: number | false;

  /**
   * Number of retry attempts for failed queries.
   * @default 1
   */
  retry?: number | boolean;

  /**
   * Maximum number of pages to store in memory.
   * @default 10
   */
  maxPages?: number;
}

/**
 * Return type for the useFaceEventsQuery hook.
 */
export interface UseFaceEventsQueryReturn {
  /** Flattened list of all face events from all pages */
  events: FaceDetectionEvent[];
  /** All loaded pages (for debugging/advanced use) */
  pages: FaceEventsQueryResponse[] | undefined;
  /** Total count of events (from first page pagination) */
  totalCount: number;
  /** Whether the initial load is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress */
  isFetching: boolean;
  /** Whether the next page is being fetched */
  isFetchingNextPage: boolean;
  /** Whether there are more pages to load */
  hasNextPage: boolean;
  /** Function to fetch the next page */
  fetchNextPage: () => void;
  /** Error that occurred during fetching */
  error: Error | null;
  /** Whether an error occurred */
  isError: boolean;
  /** Function to refetch all data */
  refetch: () => void;
}

// ============================================================================
// Query Keys
// ============================================================================

export const faceEventsQueryKeys = {
  all: ['face-events'] as const,
  lists: () => [...faceEventsQueryKeys.all, 'list'] as const,
  infinite: (filters?: FaceEventsQueryFilters, limit?: number) =>
    [...faceEventsQueryKeys.all, 'infinite', { filters, limit }] as const,
  detail: (id: number) => [...faceEventsQueryKeys.all, 'detail', id] as const,
  unknown: () => [...faceEventsQueryKeys.all, 'unknown'] as const,
};

// ============================================================================
// API Fetch Function
// ============================================================================

/**
 * Fetch face events from the API.
 * This is a placeholder implementation - replace with actual API call.
 */
async function fetchFaceEvents(params: {
  cursor?: string;
  limit: number;
  filters?: FaceEventsQueryFilters;
}): Promise<FaceEventsQueryResponse> {
  const { cursor, limit, filters } = params;

  // Build query string
  const queryParams = new URLSearchParams();
  queryParams.set('limit', limit.toString());

  if (cursor) {
    queryParams.set('cursor', cursor);
  }

  if (filters?.camera_id !== undefined) {
    queryParams.set('camera_id', filters.camera_id.toString());
  }

  if (filters?.unknown_only !== undefined) {
    queryParams.set('unknown_only', filters.unknown_only.toString());
  }

  if (filters?.start_date) {
    queryParams.set('start_date', filters.start_date);
  }

  if (filters?.end_date) {
    queryParams.set('end_date', filters.end_date);
  }

  if (filters?.min_quality !== undefined) {
    queryParams.set('min_quality', filters.min_quality.toString());
  }

  const response = await fetch(`/api/face-events?${queryParams.toString()}`);

  if (!response.ok) {
    throw new Error(`Failed to fetch face events: ${response.statusText}`);
  }

  // Define the expected API response structure
  interface ApiResponse {
    items?: FaceDetectionEvent[];
    total?: number;
    next_cursor?: string | null;
  }

  const data: ApiResponse = (await response.json()) as ApiResponse;

  // Transform the API response to match our expected format
  return {
    items: data.items ?? [],
    pagination: {
      total: data.total ?? 0,
      has_more: data.next_cursor !== null,
      next_cursor: data.next_cursor ?? null,
    },
  };
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch face events with infinite scroll pagination.
 *
 * Uses cursor-based pagination for efficient loading of large event lists.
 * Provides automatic polling every 30 seconds by default.
 *
 * @param options - Configuration options
 * @returns Face events data and pagination state
 *
 * @example
 * ```tsx
 * const {
 *   events,
 *   isLoading,
 *   hasNextPage,
 *   fetchNextPage,
 *   isFetchingNextPage,
 * } = useFaceEventsQuery({
 *   filters: { unknown_only: true },
 *   limit: 20,
 * });
 *
 * // Use with Load More button
 * {hasNextPage && (
 *   <button onClick={fetchNextPage} disabled={isFetchingNextPage}>
 *     Load More
 *   </button>
 * )}
 * ```
 */
export function useFaceEventsQuery(
  options: UseFaceEventsQueryOptions = {}
): UseFaceEventsQueryReturn {
  const {
    filters,
    limit = 20,
    enabled = true,
    staleTime,
    refetchInterval = 30000,
    retry = 1,
    maxPages = 10,
  } = options;

  const query = useCursorPaginatedQuery<FaceEventsQueryResponse, FaceEventsQueryFilters>({
    queryKey: faceEventsQueryKeys.infinite(filters, limit),
    queryFn: ({ cursor, filters: queryFilters }) =>
      fetchFaceEvents({ cursor, limit, filters: queryFilters }),
    filters,
    enabled,
    staleTime,
    refetchInterval,
    retry,
    maxPages,
  });

  // Flatten all events from all pages
  const events = useMemo(() => {
    if (!query.data?.pages) {
      return [];
    }
    return query.data.pages.flatMap((page) => page.items);
  }, [query.data?.pages]);

  // Get total count from first page
  const totalCount = useMemo(() => {
    if (!query.data?.pages?.[0]) {
      return 0;
    }
    return query.data.pages[0].pagination.total;
  }, [query.data?.pages]);

  return {
    events,
    pages: query.data?.pages,
    totalCount,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage,
    fetchNextPage: query.fetchNextPage,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useFaceEventsQuery;
