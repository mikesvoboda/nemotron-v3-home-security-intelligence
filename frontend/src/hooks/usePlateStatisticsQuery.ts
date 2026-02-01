/**
 * usePlateStatisticsQuery - TanStack Query hook for plate statistics data
 *
 * This hook fetches plate read statistics from the LPR API endpoint.
 * It provides aggregated metrics including total reads, unique plates,
 * confidence scores, and recent activity counts.
 *
 * @module hooks/usePlateStatisticsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchPlateStatistics } from '../services/plateReadsApi';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type { PlateStatisticsResponse } from '../types/plateRead';

/**
 * Query key factory for plate statistics queries.
 *
 * Keys follow a hierarchical pattern: ['plate-reads', 'statistics']
 *
 * @example
 * // Invalidate all plate statistics queries
 * queryClient.invalidateQueries({ queryKey: plateStatisticsQueryKeys.all });
 *
 * // Invalidate current statistics
 * queryClient.invalidateQueries({ queryKey: plateStatisticsQueryKeys.current() });
 */
export const plateStatisticsQueryKeys = {
  /** Base key for all plate statistics queries - use for bulk invalidation */
  all: ['plate-reads', 'statistics'] as const,
  /** Current statistics (no params) */
  current: () => [...plateStatisticsQueryKeys.all] as const,
};

/**
 * Options for configuring the usePlateStatisticsQuery hook
 */
export interface UsePlateStatisticsQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * Data older than this will be refetched in the background.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Number of retry attempts on failure.
   * Set to false or 0 to disable retries.
   * @default 1
   */
  retry?: number | boolean;
}

/**
 * Return type for the usePlateStatisticsQuery hook
 */
export interface UsePlateStatisticsQueryReturn {
  /** Raw API response data, undefined if not yet fetched */
  data: PlateStatisticsResponse | undefined;
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
  /** Derived: Total number of plate reads */
  totalReads: number;
  /** Derived: Count of unique plates */
  uniquePlates: number;
  /** Derived: Average OCR confidence as a decimal (0-1) */
  avgConfidence: number;
  /** Derived: Average OCR confidence as a percentage (0-100) */
  avgConfidencePercent: number;
  /** Derived: Number of reads in the last hour */
  readsLastHour: number;
  /** Derived: Number of reads in the last 24 hours */
  readsLast24h: number;
  /** Derived: Number of enhanced (low-light) reads */
  enhancedCount: number;
  /** Derived: Number of blurry reads */
  blurryCount: number;
  /** Derived: Average image quality score (0-1) */
  avgQualityScore: number;
}

/**
 * Hook to fetch plate read statistics using TanStack Query.
 *
 * This hook fetches from GET /api/plate-reads/stats and provides:
 * - Automatic caching and request deduplication
 * - Derived values for easy consumption
 * - Loading, error, and refetching states
 *
 * @param options - Configuration options
 * @returns Plate statistics data and query state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { totalReads, uniquePlates, avgConfidencePercent, isLoading, error } = usePlateStatisticsQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <Stats
 *     total={totalReads}
 *     unique={uniquePlates}
 *     confidence={avgConfidencePercent}
 *   />
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With options
 * const { data, refetch } = usePlateStatisticsQuery({
 *   staleTime: 60000, // 1 minute
 *   retry: 3,
 * });
 * ```
 */
export function usePlateStatisticsQuery(
  options: UsePlateStatisticsQueryOptions = {}
): UsePlateStatisticsQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, retry = 1 } = options;

  const query = useQuery<PlateStatisticsResponse, Error>({
    queryKey: plateStatisticsQueryKeys.current(),
    queryFn: fetchPlateStatistics,
    enabled,
    staleTime,
    retry,
  });

  // Derive total reads from the response
  const totalReads = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.total_reads;
  }, [query.data]);

  // Derive unique plates from the response
  const uniquePlates = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.unique_plates;
  }, [query.data]);

  // Derive average OCR confidence from the response
  const avgConfidence = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.avg_ocr_confidence;
  }, [query.data]);

  // Derive average OCR confidence as percentage
  const avgConfidencePercent = useMemo((): number => {
    if (!query.data) return 0;
    return Math.round(query.data.avg_ocr_confidence * 100);
  }, [query.data]);

  // Derive reads in last hour
  const readsLastHour = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.reads_last_hour;
  }, [query.data]);

  // Derive reads in last 24 hours
  const readsLast24h = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.reads_last_24h;
  }, [query.data]);

  // Derive enhanced count
  const enhancedCount = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.enhanced_count;
  }, [query.data]);

  // Derive blurry count
  const blurryCount = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.blurry_count;
  }, [query.data]);

  // Derive average quality score
  const avgQualityScore = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.avg_quality_score;
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    totalReads,
    uniquePlates,
    avgConfidence,
    avgConfidencePercent,
    readsLastHour,
    readsLast24h,
    enhancedCount,
    blurryCount,
    avgQualityScore,
  };
}
