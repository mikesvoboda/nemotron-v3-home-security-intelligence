/**
 * useZoneComparison - TanStack Query hook for zone comparison data (NEM-4714)
 *
 * This module provides a hook for fetching zone comparison data that allows
 * comparing metrics across multiple zones for side-by-side analysis.
 *
 * Features:
 * - Compare zones by crossings, dwell_time, anomalies, or occupancy metrics
 * - Filter by period (day, week, month)
 * - Select specific zones for comparison
 *
 * @module hooks/useZoneComparison
 * @see NEM-4714 Zone Analytics Dashboard Phase 4B
 */

import { useQuery } from '@tanstack/react-query';

import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Constants
// ============================================================================

const API_BASE = '/api/analytics-zones';

// ============================================================================
// Types
// ============================================================================

/**
 * Metric types available for zone comparison.
 */
export type ComparisonMetric = 'crossings' | 'dwell_time' | 'anomalies' | 'occupancy';

/**
 * Time periods for comparison aggregation.
 */
export type ComparisonPeriod = 'day' | 'week' | 'month';

/**
 * Comparison data for a single zone.
 */
export interface ZoneComparisonData {
  /** Zone ID */
  zone_id: number;
  /** Zone name */
  zone_name: string;
  /** Zone type (entry_point, driveway, etc.) */
  zone_type: string;
  /** Camera ID the zone belongs to */
  camera_id: string;
  /** Metric value for this zone */
  value: number;
  /** Trend percentage change from previous period (null if not available) */
  trend_percent: number | null;
}

/**
 * Response from the zone comparison endpoint.
 */
export interface ZoneComparisonResponse {
  /** The metric being compared */
  metric: ComparisonMetric;
  /** Comparison data for each zone */
  zones: ZoneComparisonData[];
  /** Start of the comparison period (ISO format) */
  start_time: string;
  /** End of the comparison period (ISO format) */
  end_time: string;
  /** The comparison period */
  comparison_period: ComparisonPeriod;
}

/**
 * Options for the useZoneComparison hook.
 */
export interface UseZoneComparisonOptions {
  /** Zone IDs to compare */
  zoneIds: number[];
  /** Metric to compare (default: 'crossings') */
  metric?: ComparisonMetric;
  /** Time period for comparison (default: 'day') */
  period?: ComparisonPeriod;
  /** Whether the query is enabled (default: true) */
  enabled?: boolean;
}

/**
 * Return type for the useZoneComparison hook.
 */
export interface UseZoneComparisonReturn {
  /** Comparison data */
  data: ZoneComparisonResponse | undefined;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Refetch function */
  refetch: () => void;
}

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for zone comparison queries.
 */
export const zoneComparisonQueryKeys = {
  all: ['zone-comparison'] as const,
  comparison: (zoneIds: number[], metric: ComparisonMetric, period: ComparisonPeriod) =>
    [...zoneComparisonQueryKeys.all, zoneIds.sort(), metric, period] as const,
};

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch zone comparison data from the API.
 *
 * @param zoneIds - Array of zone IDs to compare
 * @param metric - Metric to compare
 * @param period - Time period for comparison
 * @returns Promise resolving to zone comparison data
 */
async function fetchZoneComparison(
  zoneIds: number[],
  metric: ComparisonMetric,
  period: ComparisonPeriod
): Promise<ZoneComparisonResponse> {
  const params = new URLSearchParams();
  zoneIds.forEach((id) => params.append('zone_ids', id.toString()));
  params.set('metric', metric);
  params.set('period', period);

  const response = await fetch(`${API_BASE}/comparison?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch comparison data: ${response.statusText}`);
  }
  return response.json() as Promise<ZoneComparisonResponse>;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch zone comparison data.
 *
 * Fetches comparison metrics for multiple zones allowing side-by-side
 * analysis of zone activity.
 *
 * @param options - Configuration options
 * @returns Comparison data, loading state, error, and refetch function
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useZoneComparison({
 *   zoneIds: [1, 2, 3],
 *   metric: 'crossings',
 *   period: 'day',
 * });
 *
 * if (data) {
 *   data.zones.forEach(zone => {
 *     console.log(`${zone.zone_name}: ${zone.value} crossings`);
 *   });
 * }
 * ```
 */
export function useZoneComparison(options: UseZoneComparisonOptions): UseZoneComparisonReturn {
  const { zoneIds, metric = 'crossings', period = 'day', enabled = true } = options;

  const query = useQuery({
    queryKey: zoneComparisonQueryKeys.comparison(zoneIds, metric, period),
    queryFn: () => fetchZoneComparison(zoneIds, metric, period),
    enabled: enabled && zoneIds.length > 0,
    staleTime: DEFAULT_STALE_TIME,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: () => void query.refetch(),
  };
}

export default useZoneComparison;
