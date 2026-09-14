/**
 * useRecordingsQuery - TanStack Query hook for fetching request recordings
 *
 * This hook fetches from GET /api/debug/recordings to provide a list of
 * recorded API requests for debugging and replay purposes.
 *
 * Implements NEM-2721: Request Recording and Replay panel
 *
 * @module hooks/useRecordingsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchRecordings,
  type RecordingsListResponse,
  type RecordingResponse,
} from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

/**
 * Query key for recordings endpoint
 */
export const RECORDINGS_QUERY_KEY = ['debug', 'recordings'] as const;

/**
 * Options for configuring the useRecordingsQuery hook
 */
export interface UseRecordingsQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of recordings to fetch.
   * @default 100
   */
  limit?: number;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false (no auto-refetch)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * Data older than this will be refetched in the background.
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for the useRecordingsQuery hook
 */
export interface UseRecordingsQueryReturn {
  /** Full response from the API, undefined if not yet fetched */
  data: RecordingsListResponse | undefined;

  /** Array of recordings from the response */
  recordings: RecordingResponse[];

  /** Total count of recordings */
  totalCount: number;

  /** Whether the recordings list is empty */
  isEmpty: boolean;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether a background refetch is in progress */
  isRefetching: boolean;

  /** Error object if the query failed */
  error: Error | null;

  /** Whether the query has errored */
  isError: boolean;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch request recordings using TanStack Query.
 *
 * This hook fetches from GET /api/debug/recordings and provides:
 * - List of recorded API requests with metadata
 * - Request method, path, status code, and duration
 * - Timestamp of each recording
 *
 * Note: This endpoint is only available when debug mode is enabled on the backend.
 *
 * @param options - Configuration options
 * @returns Recordings data and query state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const {
 *   recordings,
 *   totalCount,
 *   isLoading,
 *   isEmpty,
 * } = useRecordingsQuery();
 *
 * return (
 *   <div>
 *     {isLoading ? (
 *       <Spinner />
 *     ) : isEmpty ? (
 *       <EmptyState message="No recordings yet" />
 *     ) : (
 *       <RecordingsList recordings={recordings} />
 *     )}
 *   </div>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With custom limit
 * const { recordings } = useRecordingsQuery({ limit: 50 });
 * ```
 */
export function useRecordingsQuery(
  options: UseRecordingsQueryOptions = {}
): UseRecordingsQueryReturn {
  const {
    enabled = true,
    limit = 100,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  const query = useQuery({
    queryKey: [...RECORDINGS_QUERY_KEY, { limit }],
    queryFn: () => fetchRecordings(limit),
    enabled,
    refetchInterval,
    staleTime,
    // Retry once for debug endpoints (may return 404 if debug disabled)
    retry: 1,
  });

  // Derive recordings array
  const recordings = useMemo((): RecordingResponse[] => {
    return query.data?.recordings ?? [];
  }, [query.data?.recordings]);

  // Derive total count
  const totalCount = useMemo((): number => {
    return query.data?.total ?? 0;
  }, [query.data?.total]);

  // Derive isEmpty
  const isEmpty = useMemo((): boolean => {
    return recordings.length === 0;
  }, [recordings.length]);

  return {
    data: query.data,
    recordings,
    totalCount,
    isEmpty,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}
