/**
 * useSceneChangeSummaryQuery - TanStack Query hook for scene change summary (NEM-3580)
 *
 * This module provides a hook for fetching scene change summary statistics using TanStack Query.
 * The summary provides aggregated data computed from the scene change list, enabling
 * summary dashboards and trend analysis.
 *
 * Benefits:
 * - Quick overview of scene changes without loading full list
 * - Breakdown by change type for prioritization
 * - Track acknowledgement status across changes
 * - Identify cameras with frequent scene changes
 *
 * @module hooks/useSceneChangeSummaryQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchSceneChangeSummary,
  type SceneChangeSummary,
  type SceneChangeType,
  type SceneChangeTypeBreakdown,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useSceneChangeSummaryQuery hook.
 */
export interface UseSceneChangeSummaryQueryOptions {
  /**
   * Number of days to look back for scene changes.
   * @default 7
   */
  days?: number;

  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useSceneChangeSummaryQuery hook.
 */
export interface UseSceneChangeSummaryQueryReturn {
  /** Full summary data, undefined if not yet fetched */
  data: SceneChangeSummary | undefined;
  /** Total number of scene changes in the period */
  totalChanges: number;
  /** Number of unacknowledged changes (need review) */
  unacknowledgedCount: number;
  /** Number of acknowledged changes */
  acknowledgedCount: number;
  /** Most recent scene change timestamp, null if no changes */
  lastChangeAt: Date | null;
  /** Breakdown of changes by type */
  byType: SceneChangeTypeBreakdown[];
  /** Most common change type, null if no changes */
  mostCommonType: SceneChangeType | null;
  /** Average similarity score (0-1), null if no changes */
  avgSimilarityScore: number | null;
  /** Whether there are any unacknowledged changes */
  hasUnacknowledged: boolean;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress (initial or background) */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query has errored */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Number of days covered by the summary */
  periodDays: number;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to fetch scene change summary statistics using TanStack Query.
 *
 * Returns aggregated statistics for scene changes detected on a camera,
 * including counts, type breakdown, and acknowledgement status.
 *
 * @param cameraId - The camera ID to fetch summary for
 * @param options - Configuration options
 * @returns Scene change summary data and query state
 *
 * @example
 * ```tsx
 * // Basic usage - show summary card
 * const {
 *   totalChanges,
 *   unacknowledgedCount,
 *   lastChangeAt,
 *   isLoading,
 * } = useSceneChangeSummaryQuery('front_door');
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <Card>
 *     <h3>Scene Changes</h3>
 *     <p>{totalChanges} changes in the last 7 days</p>
 *     {unacknowledgedCount > 0 && (
 *       <Badge color="yellow">{unacknowledgedCount} need review</Badge>
 *     )}
 *     {lastChangeAt && (
 *       <p>Last change: {lastChangeAt.toLocaleString()}</p>
 *     )}
 *   </Card>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // Show type breakdown chart
 * const { byType, totalChanges } = useSceneChangeSummaryQuery('front_door', {
 *   days: 30,  // Look back 30 days
 * });
 *
 * return (
 *   <DonutChart
 *     data={byType.map(({ type, count, percentage }) => ({
 *       name: type,
 *       value: count,
 *     }))}
 *   />
 * );
 * ```
 *
 * @example
 * ```tsx
 * // Alert on unacknowledged changes
 * const { hasUnacknowledged, unacknowledgedCount, mostCommonType } =
 *   useSceneChangeSummaryQuery(cameraId, { refetchInterval: 60000 });
 *
 * if (hasUnacknowledged) {
 *   return (
 *     <Alert severity="warning">
 *       {unacknowledgedCount} unreviewed scene changes detected!
 *       Most common issue: {mostCommonType}
 *     </Alert>
 *   );
 * }
 * ```
 */
export function useSceneChangeSummaryQuery(
  cameraId: string,
  options: UseSceneChangeSummaryQueryOptions = {}
): UseSceneChangeSummaryQueryReturn {
  const {
    days = 7,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    refetchInterval = false,
  } = options;

  const query = useQuery<SceneChangeSummary, Error>({
    queryKey: queryKeys.cameras.sceneChangeSummary(cameraId, days),
    queryFn: () => fetchSceneChangeSummary(cameraId, { days }),
    enabled: enabled && !!cameraId,
    staleTime,
    refetchInterval,
    // Reduced retry for faster feedback
    retry: 1,
  });

  // Memoize derived values
  const totalChanges = useMemo(() => query.data?.totalChanges ?? 0, [query.data]);
  const unacknowledgedCount = useMemo(() => query.data?.unacknowledgedCount ?? 0, [query.data]);
  const acknowledgedCount = useMemo(() => query.data?.acknowledgedCount ?? 0, [query.data]);

  const lastChangeAt = useMemo<Date | null>(() => {
    if (query.data?.lastChangeAt) {
      return new Date(query.data.lastChangeAt);
    }
    return null;
  }, [query.data]);

  const byType = useMemo<SceneChangeTypeBreakdown[]>(
    () => query.data?.byType ?? [],
    [query.data]
  );

  const mostCommonType = useMemo<SceneChangeType | null>(
    () => query.data?.mostCommonType ?? null,
    [query.data]
  );

  const avgSimilarityScore = useMemo<number | null>(
    () => query.data?.avgSimilarityScore ?? null,
    [query.data]
  );

  const hasUnacknowledged = useMemo(() => unacknowledgedCount > 0, [unacknowledgedCount]);
  const periodDays = useMemo(() => query.data?.periodDays ?? days, [query.data, days]);

  return {
    data: query.data,
    totalChanges,
    unacknowledgedCount,
    acknowledgedCount,
    lastChangeAt,
    byType,
    mostCommonType,
    avgSimilarityScore,
    hasUnacknowledged,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    periodDays,
  };
}

// Re-export types for convenience
export type { SceneChangeSummary, SceneChangeType, SceneChangeTypeBreakdown };
