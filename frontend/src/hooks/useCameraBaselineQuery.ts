/**
 * useCameraBaselineQuery - TanStack Query hooks for camera baseline data
 *
 * This module provides hooks for fetching camera baseline activity data:
 * - useCameraBaselineQuery: Fetch baseline summary (patterns, deviation)
 * - useCameraActivityBaselineQuery: Fetch activity heatmap data
 * - useCameraClassBaselineQuery: Fetch class frequency data
 *
 * @module hooks/useCameraBaselineQuery
 * @see NEM-3576 - Camera Baseline Activity API Integration
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchCameraBaseline,
  fetchCameraActivityBaseline,
  fetchCameraClassBaseline,
  type BaselineSummaryResponse,
  type ActivityBaselineResponse,
  type ActivityBaselineEntry,
  type ClassBaselineResponse,
  type ClassBaselineEntry,
} from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Query key factory for camera baseline queries.
 *
 * Keys follow a hierarchical pattern: ['cameras', 'baseline', type, cameraId]
 *
 * @example
 * // Invalidate all baseline queries
 * queryClient.invalidateQueries({ queryKey: cameraBaselineQueryKeys.all });
 *
 * // Invalidate all baselines for a specific camera
 * queryClient.invalidateQueries({ queryKey: cameraBaselineQueryKeys.byCamera('cam-1') });
 */
export const cameraBaselineQueryKeys = {
  /** Base key for all baseline queries - use for bulk invalidation */
  all: ['cameras', 'baseline'] as const,

  /** All baselines for a specific camera */
  byCamera: (cameraId: string) => [...cameraBaselineQueryKeys.all, cameraId] as const,

  /** Baseline summary for a camera */
  summary: (cameraId: string) => [...cameraBaselineQueryKeys.all, 'summary', cameraId] as const,

  /** Activity baseline (heatmap) for a camera */
  activity: (cameraId: string) => [...cameraBaselineQueryKeys.all, 'activity', cameraId] as const,

  /** Class frequency baseline for a camera */
  classes: (cameraId: string) => [...cameraBaselineQueryKeys.all, 'classes', cameraId] as const,
};

// ============================================================================
// useCameraBaselineQuery - Fetch baseline summary
// ============================================================================

/**
 * Options for configuring the useCameraBaselineQuery hook
 */
export interface UseCameraBaselineQueryOptions {
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
}

/**
 * Return type for the useCameraBaselineQuery hook
 */
export interface UseCameraBaselineQueryReturn {
  /** Raw baseline summary data, undefined if not yet fetched */
  data: BaselineSummaryResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query is in an error state */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Derived: Whether the camera has baseline data (data_points > 0) */
  hasBaseline: boolean;
  /** Derived: Whether baseline is still being learned (no baseline_established) */
  isLearning: boolean;
}

/**
 * Hook to fetch baseline summary data for a camera using TanStack Query.
 *
 * Provides comprehensive baseline data including:
 * - Hourly activity patterns
 * - Daily activity patterns
 * - Object-specific baselines
 * - Current deviation from baseline
 *
 * @param cameraId - Camera ID to fetch baseline for, or undefined to disable
 * @param options - Configuration options
 * @returns Baseline summary data and query state
 *
 * @example
 * ```tsx
 * const { data, hasBaseline, isLearning, isLoading } = useCameraBaselineQuery(cameraId);
 *
 * if (isLoading) return <Spinner />;
 * if (!hasBaseline) return <EmptyState message="No baseline data yet" />;
 *
 * return (
 *   <BaselineSummary
 *     deviation={data.current_deviation}
 *     patterns={data.hourly_patterns}
 *   />
 * );
 * ```
 */
export function useCameraBaselineQuery(
  cameraId: string | undefined,
  options: UseCameraBaselineQueryOptions = {}
): UseCameraBaselineQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  // Only enable the query if cameraId is provided
  const queryEnabled = enabled && !!cameraId;

  const query = useQuery<BaselineSummaryResponse, Error>({
    queryKey: cameraBaselineQueryKeys.summary(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchCameraBaseline(cameraId);
    },
    enabled: queryEnabled,
    staleTime,
    retry: 1,
  });

  // Derive hasBaseline from data_points
  const hasBaseline = useMemo((): boolean => {
    if (!query.data) return false;
    return query.data.data_points > 0;
  }, [query.data]);

  // Derive isLearning from baseline_established
  const isLearning = useMemo((): boolean => {
    if (!query.data) return true;
    return query.data.baseline_established === null;
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    hasBaseline,
    isLearning,
  };
}

// ============================================================================
// useCameraActivityBaselineQuery - Fetch activity heatmap data
// ============================================================================

/**
 * Options for configuring the useCameraActivityBaselineQuery hook
 */
export interface UseCameraActivityBaselineQueryOptions {
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
}

/**
 * Return type for the useCameraActivityBaselineQuery hook
 */
export interface UseCameraActivityBaselineQueryReturn {
  /** Raw activity baseline data, undefined if not yet fetched */
  data: ActivityBaselineResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query is in an error state */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Derived: Activity baseline entries for the heatmap */
  entries: ActivityBaselineEntry[];
  /** Derived: Whether learning is complete */
  learningComplete: boolean;
  /** Derived: Minimum samples required per time slot */
  minSamplesRequired: number;
}

/**
 * Hook to fetch activity baseline data for a camera using TanStack Query.
 *
 * Returns data suitable for rendering in the ActivityHeatmap component:
 * - 168 entries (24 hours x 7 days) representing the full weekly activity
 * - Peak hour and day indicators
 * - Learning progress status
 *
 * @param cameraId - Camera ID to fetch activity baseline for, or undefined to disable
 * @param options - Configuration options
 * @returns Activity baseline data and query state
 *
 * @example
 * ```tsx
 * const { entries, learningComplete, minSamplesRequired } = useCameraActivityBaselineQuery(cameraId);
 *
 * return (
 *   <ActivityHeatmap
 *     entries={entries}
 *     learningComplete={learningComplete}
 *     minSamplesRequired={minSamplesRequired}
 *   />
 * );
 * ```
 */
export function useCameraActivityBaselineQuery(
  cameraId: string | undefined,
  options: UseCameraActivityBaselineQueryOptions = {}
): UseCameraActivityBaselineQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  // Only enable the query if cameraId is provided
  const queryEnabled = enabled && !!cameraId;

  const query = useQuery<ActivityBaselineResponse, Error>({
    queryKey: cameraBaselineQueryKeys.activity(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchCameraActivityBaseline(cameraId);
    },
    enabled: queryEnabled,
    staleTime,
    retry: 1,
  });

  // Derive entries from response
  const entries = useMemo((): ActivityBaselineEntry[] => {
    if (!query.data) return [];
    return query.data.entries;
  }, [query.data]);

  // Derive learningComplete from response
  const learningComplete = useMemo((): boolean => {
    if (!query.data) return false;
    return query.data.learning_complete;
  }, [query.data]);

  // Derive minSamplesRequired from response
  const minSamplesRequired = useMemo((): number => {
    if (!query.data) return 10; // Default from backend
    return query.data.min_samples_required;
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    entries,
    learningComplete,
    minSamplesRequired,
  };
}

// ============================================================================
// useCameraClassBaselineQuery - Fetch class frequency data
// ============================================================================

/**
 * Options for configuring the useCameraClassBaselineQuery hook
 */
export interface UseCameraClassBaselineQueryOptions {
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
}

/**
 * Return type for the useCameraClassBaselineQuery hook
 */
export interface UseCameraClassBaselineQueryReturn {
  /** Raw class baseline data, undefined if not yet fetched */
  data: ClassBaselineResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query is in an error state */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Derived: Class baseline entries */
  entries: ClassBaselineEntry[];
  /** Derived: List of unique object classes detected */
  uniqueClasses: string[];
  /** Derived: Most frequently detected object class */
  mostCommonClass: string | null;
}

/**
 * Hook to fetch class frequency baseline data for a camera using TanStack Query.
 *
 * Returns data about object class detection patterns:
 * - Frequency by class and hour
 * - List of unique object classes
 * - Most common class
 *
 * @param cameraId - Camera ID to fetch class baseline for, or undefined to disable
 * @param options - Configuration options
 * @returns Class baseline data and query state
 *
 * @example
 * ```tsx
 * const { entries, uniqueClasses, mostCommonClass } = useCameraClassBaselineQuery(cameraId);
 *
 * return (
 *   <ClassDistributionChart
 *     entries={entries}
 *     classes={uniqueClasses}
 *     mostCommon={mostCommonClass}
 *   />
 * );
 * ```
 */
export function useCameraClassBaselineQuery(
  cameraId: string | undefined,
  options: UseCameraClassBaselineQueryOptions = {}
): UseCameraClassBaselineQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  // Only enable the query if cameraId is provided
  const queryEnabled = enabled && !!cameraId;

  const query = useQuery<ClassBaselineResponse, Error>({
    queryKey: cameraBaselineQueryKeys.classes(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchCameraClassBaseline(cameraId);
    },
    enabled: queryEnabled,
    staleTime,
    retry: 1,
  });

  // Derive entries from response
  const entries = useMemo((): ClassBaselineEntry[] => {
    if (!query.data) return [];
    return query.data.entries;
  }, [query.data]);

  // Derive uniqueClasses from response
  const uniqueClasses = useMemo((): string[] => {
    if (!query.data) return [];
    return query.data.unique_classes;
  }, [query.data]);

  // Derive mostCommonClass from response
  const mostCommonClass = useMemo((): string | null => {
    if (!query.data) return null;
    return query.data.most_common_class;
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    entries,
    uniqueClasses,
    mostCommonClass,
  };
}
