/**
 * useDetectionLabelsQuery - React Query hook for fetching detection labels
 *
 * This hook provides query functionality for fetching available detection labels
 * with their counts from GET /api/detections/labels.
 *
 * Features:
 * - Automatic caching with 10-minute stale time (labels rarely change)
 * - Query key factory for cache invalidation
 * - Derived state for label list and total count
 *
 * @module hooks/useDetectionLabelsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchDetectionLabels } from '../services/api';
import { queryKeys } from '../services/queryClient';

import type { DetectionLabelsResponse, DetectionLabelCount } from '../types/generated';

// ============================================================================
// Constants
// ============================================================================

/**
 * Stale time for detection labels (10 minutes).
 *
 * Labels don't change frequently - they only update when new detection types
 * are added or existing detections are deleted. A longer stale time reduces
 * unnecessary API calls while still keeping data reasonably fresh.
 */
const LABELS_STALE_TIME = 10 * 60 * 1000;

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useDetectionLabelsQuery hook
 */
export interface UseDetectionLabelsQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default LABELS_STALE_TIME (10 minutes)
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
 * Return type for the useDetectionLabelsQuery hook
 */
export interface UseDetectionLabelsQueryReturn {
  /** Raw API response data */
  data: DetectionLabelsResponse | undefined;

  /** Array of labels with their counts */
  labels: DetectionLabelCount[];

  /** Total number of detections across all labels */
  totalDetections: number;

  /** Total number of unique labels */
  labelCount: number;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether a background refetch is in progress */
  isRefetching: boolean;

  /** Whether the query is fetching (initial or background) */
  isFetching: boolean;

  /** Error object if the query failed */
  error: Error | null;

  /** Whether the query has errored */
  isError: boolean;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Query key factory for detection labels queries.
 *
 * Uses the centralized queryKeys from queryClient for consistency,
 * but exports these helpers for convenience and documentation.
 *
 * @example
 * // Invalidate detection labels cache
 * queryClient.invalidateQueries({ queryKey: detectionLabelsKeys.all });
 */
export const detectionLabelsKeys = {
  /** Base key for all detection labels queries */
  all: queryKeys.detections.labels,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch available detection labels with counts using TanStack Query.
 *
 * This hook fetches from GET /api/detections/labels and provides:
 * - List of unique labels with their detection counts
 * - Total detection count across all labels
 * - Label count for display in filter badges
 *
 * @param options - Configuration options
 * @returns Detection labels data and query state
 *
 * @example
 * ```tsx
 * const { labels, totalDetections, isLoading } = useDetectionLabelsQuery();
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <Select label="Filter by label">
 *     {labels.map(({ label, count }) => (
 *       <Option key={label} value={label}>
 *         {label} ({count})
 *       </Option>
 *     ))}
 *   </Select>
 * );
 * ```
 *
 * @example
 * // Conditional fetching - only fetch when filter is open
 * const { labels, isLoading } = useDetectionLabelsQuery({
 *   enabled: isFilterPanelOpen,
 * });
 *
 * @example
 * // With polling for live updates
 * const { labels } = useDetectionLabelsQuery({
 *   refetchInterval: 60000, // Refresh every minute
 * });
 */
export function useDetectionLabelsQuery(
  options: UseDetectionLabelsQueryOptions = {}
): UseDetectionLabelsQueryReturn {
  const {
    enabled = true,
    staleTime = LABELS_STALE_TIME,
    refetchInterval = false,
  } = options;

  const query = useQuery({
    queryKey: queryKeys.detections.labels,
    queryFn: fetchDetectionLabels,
    enabled,
    staleTime,
    refetchInterval,
    // Labels data is not critical, so fewer retries are fine
    retry: 2,
  });

  // Derive labels array from data
  const labels = useMemo((): DetectionLabelCount[] => {
    return query.data?.labels ?? [];
  }, [query.data?.labels]);

  // Calculate total detections across all labels
  const totalDetections = useMemo((): number => {
    return labels.reduce((sum, item) => sum + item.count, 0);
  }, [labels]);

  // Get label count for convenience
  const labelCount = labels.length;

  return {
    data: query.data,
    labels,
    totalDetections,
    labelCount,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useDetectionLabelsQuery;
