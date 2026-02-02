/**
 * useZoneActivityHeatmap - TanStack Query hook for zone activity heatmap data (NEM-5024)
 *
 * This module provides a hook for fetching zone activity heatmap data from
 * the backend API, showing activity patterns by hour and day of week.
 *
 * Features:
 * - Configurable time range (1h, 6h, 24h, 7d, 30d)
 * - Weekly activity matrix (hour x day)
 * - Today's hourly activity
 *
 * @module hooks/useZoneActivityHeatmap
 * @see NEM-5024 Zone Activity Heatmaps
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';

import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Time range options for the heatmap.
 */
export type HeatmapTimeRange = '1h' | '6h' | '24h' | '7d' | '30d';

/**
 * Heatmap data point representing activity at a specific time slot.
 */
export interface HeatmapDataPoint {
  /** Hour of day (0-23) */
  hour: number;
  /** Day of week (0-6, 0 = Sunday) */
  dayOfWeek: number;
  /** Activity count/intensity */
  value: number;
}

/**
 * Hourly activity data for time-of-day analysis.
 */
export interface HourlyActivity {
  hour: number;
  count: number;
}

/**
 * Response from the zone activity heatmap endpoint.
 */
export interface ZoneActivityHeatmapResponse {
  zone_id: number;
  zone_name: string;
  time_range: HeatmapTimeRange;
  weekly_data: Array<{
    hour: number;
    day_of_week: number;
    value: number;
  }>;
  hourly_data: Array<{
    hour: number;
    count: number;
  }>;
  total_activity: number;
  start_time: string;
  end_time: string;
}

/**
 * Options for the useZoneActivityHeatmap hook.
 */
export interface UseZoneActivityHeatmapOptions {
  /** Zone ID to fetch heatmap data for */
  zoneId: string | number;
  /** Time range for aggregation */
  timeRange?: HeatmapTimeRange;
  /** Whether the query is enabled */
  enabled?: boolean;
  /** How long data is considered fresh (ms) */
  staleTime?: number;
  /** Refetch interval (ms or false to disable) */
  refetchInterval?: number | false;
}

/**
 * Return value from the useZoneActivityHeatmap hook.
 */
export interface UseZoneActivityHeatmapReturn {
  /** Weekly activity data points */
  weeklyData: HeatmapDataPoint[];
  /** Today's hourly activity */
  hourlyData: HourlyActivity[];
  /** Zone name */
  zoneName: string | null;
  /** Total activity count */
  totalActivity: number;
  /** Start of the query time window */
  startTime: string | null;
  /** End of the query time window */
  endTime: string | null;
  /** Whether data is loading */
  isLoading: boolean;
  /** Whether data is being refetched */
  isFetching: boolean;
  /** Error if any */
  error: Error | null;
  /** Whether an error occurred */
  isError: boolean;
  /** Manually refetch data */
  refetch: () => Promise<unknown>;
  /** Invalidate and refetch data */
  refresh: () => Promise<void>;
}

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = '/api';

/**
 * Fetch zone activity heatmap data from the backend.
 */
async function fetchZoneActivityHeatmap(
  zoneId: string | number,
  timeRange: HeatmapTimeRange
): Promise<ZoneActivityHeatmapResponse> {
  const params = new URLSearchParams({
    time_range: timeRange,
  });

  const url = `${API_BASE}/analytics-zones/polygon-zones/${zoneId}/activity-heatmap?${params.toString()}`;

  const response = await fetch(url);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Zone not found');
    }
    throw new Error(`Failed to fetch zone activity heatmap: ${response.statusText}`);
  }

  return response.json() as Promise<ZoneActivityHeatmapResponse>;
}

// ============================================================================
// Query Keys
// ============================================================================

export const zoneActivityHeatmapQueryKeys = {
  all: ['zone-activity-heatmap'] as const,
  byZone: (zoneId: string | number) => [...zoneActivityHeatmapQueryKeys.all, 'zone', zoneId] as const,
  withRange: (zoneId: string | number, timeRange: HeatmapTimeRange) =>
    [...zoneActivityHeatmapQueryKeys.byZone(zoneId), 'range', timeRange] as const,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch zone activity heatmap data.
 *
 * Provides activity patterns aggregated by hour and day of week for
 * visualizing when a zone is most active.
 *
 * @param options - Configuration options
 * @returns Heatmap data, loading states, and refetch functions
 *
 * @example
 * ```tsx
 * const {
 *   weeklyData,
 *   hourlyData,
 *   isLoading,
 *   refetch,
 * } = useZoneActivityHeatmap({
 *   zoneId: 'zone-123',
 *   timeRange: '7d',
 * });
 *
 * // Render heatmap grid
 * weeklyData.forEach(point => {
 *   console.log(`Hour ${point.hour}, Day ${point.dayOfWeek}: ${point.value}`);
 * });
 * ```
 */
export function useZoneActivityHeatmap(
  options: UseZoneActivityHeatmapOptions
): UseZoneActivityHeatmapReturn {
  const {
    zoneId,
    timeRange = '7d',
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    refetchInterval = false,
  } = options;

  const queryClient = useQueryClient();

  // Build query key
  const queryKey = useMemo(
    () => zoneActivityHeatmapQueryKeys.withRange(zoneId, timeRange),
    [zoneId, timeRange]
  );

  // Main query
  const query = useQuery({
    queryKey,
    queryFn: () => fetchZoneActivityHeatmap(zoneId, timeRange),
    enabled: enabled && !!zoneId,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  // Transform weekly data to component format
  const weeklyData = useMemo<HeatmapDataPoint[]>(() => {
    if (!query.data?.weekly_data) return [];
    return query.data.weekly_data.map((dp) => ({
      hour: dp.hour,
      dayOfWeek: dp.day_of_week,
      value: dp.value,
    }));
  }, [query.data]);

  // Transform hourly data
  const hourlyData = useMemo<HourlyActivity[]>(() => {
    if (!query.data?.hourly_data) return [];
    return query.data.hourly_data.map((ha) => ({
      hour: ha.hour,
      count: ha.count,
    }));
  }, [query.data]);

  // Refresh function to invalidate and refetch
  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: zoneActivityHeatmapQueryKeys.byZone(zoneId) });
  }, [queryClient, zoneId]);

  return {
    weeklyData,
    hourlyData,
    zoneName: query.data?.zone_name ?? null,
    totalActivity: query.data?.total_activity ?? 0,
    startTime: query.data?.start_time ?? null,
    endTime: query.data?.end_time ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    refresh,
  };
}

export default useZoneActivityHeatmap;
