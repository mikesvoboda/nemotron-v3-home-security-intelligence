/**
 * useHeatmapQuery - TanStack Query hooks for heatmap data
 *
 * This module provides hooks for fetching heatmap data using TanStack Query.
 * - useHeatmapQuery: Fetch current heatmap for a camera
 * - useHeatmapHistoryQuery: Fetch historical heatmap metadata
 * - useMergedHeatmapQuery: Fetch merged heatmap for a time range
 *
 * @module hooks/useHeatmapQuery
 * @see NEM-4927 - Heatmaps Visualization Page
 * @see backend/api/routes/heatmaps.py - Backend API endpoints
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchApi } from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Resolution levels for heatmap data aggregation.
 */
export type HeatmapResolution = 'hourly' | 'daily' | 'weekly';

/**
 * Time range options for filtering heatmap data.
 */
export type HeatmapTimeRange = '1h' | '6h' | '24h' | '7d' | '30d';

/**
 * Response from the heatmap API.
 */
export interface HeatmapResponse {
  camera_id: string;
  resolution: HeatmapResolution;
  time_bucket: string;
  image_base64: string;
  width: number;
  height: number;
  total_detections: number;
  colormap: string;
}

/**
 * Heatmap metadata entry.
 */
export interface HeatmapMetadata {
  id: number;
  camera_id: string;
  time_bucket: string;
  resolution: HeatmapResolution;
  width: number;
  height: number;
  total_detections: number;
  created_at: string;
  updated_at: string;
}

/**
 * Response from the heatmap history API.
 */
export interface HeatmapListResponse {
  heatmaps: HeatmapMetadata[];
  total: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch current heatmap for a camera.
 */
async function fetchHeatmapData(
  cameraId: string,
  resolution: HeatmapResolution,
  colormap: string
): Promise<HeatmapResponse> {
  const params = new URLSearchParams({
    resolution,
    colormap,
    output_width: '640',
    output_height: '480',
  });
  return fetchApi<HeatmapResponse>(
    `/api/heatmaps/camera/${cameraId}?${params.toString()}`
  );
}

/**
 * Calculate time range start time based on selected range.
 */
function calculateStartTime(timeRange: HeatmapTimeRange): Date {
  const now = new Date();
  switch (timeRange) {
    case '1h':
      return new Date(now.getTime() - 60 * 60 * 1000);
    case '6h':
      return new Date(now.getTime() - 6 * 60 * 60 * 1000);
    case '24h':
      return new Date(now.getTime() - 24 * 60 * 60 * 1000);
    case '7d':
      return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    case '30d':
      return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    default:
      return new Date(now.getTime() - 24 * 60 * 60 * 1000);
  }
}

/**
 * Fetch heatmap history for a camera.
 */
async function fetchHeatmapHistoryData(
  cameraId: string,
  timeRange: HeatmapTimeRange,
  resolution?: HeatmapResolution
): Promise<HeatmapListResponse> {
  const startTime = calculateStartTime(timeRange);
  const endTime = new Date();

  const params = new URLSearchParams({
    start_time: startTime.toISOString(),
    end_time: endTime.toISOString(),
    limit: '50',
    offset: '0',
  });
  if (resolution) {
    params.set('resolution', resolution);
  }
  return fetchApi<HeatmapListResponse>(
    `/api/heatmaps/camera/${cameraId}/history?${params.toString()}`
  );
}

/**
 * Fetch merged heatmap for a time range.
 */
async function fetchMergedHeatmapData(
  cameraId: string,
  startTime: Date,
  endTime: Date,
  resolution?: HeatmapResolution
): Promise<HeatmapResponse> {
  const params = new URLSearchParams({
    start_time: startTime.toISOString(),
    end_time: endTime.toISOString(),
  });
  if (resolution) {
    params.set('resolution', resolution);
  }
  return fetchApi<HeatmapResponse>(
    `/api/heatmaps/camera/${cameraId}/merged?${params.toString()}`
  );
}

// ============================================================================
// Query Keys
// ============================================================================

export const heatmapQueryKeys = {
  all: ['heatmaps'] as const,
  camera: (cameraId: string) => [...heatmapQueryKeys.all, 'camera', cameraId] as const,
  current: (cameraId: string, resolution: HeatmapResolution, colormap: string) =>
    [...heatmapQueryKeys.camera(cameraId), 'current', resolution, colormap] as const,
  history: (cameraId: string, timeRange: HeatmapTimeRange, resolution?: HeatmapResolution) =>
    [...heatmapQueryKeys.camera(cameraId), 'history', timeRange, resolution] as const,
  merged: (cameraId: string, startTime: string, endTime: string, resolution?: HeatmapResolution) =>
    [...heatmapQueryKeys.camera(cameraId), 'merged', startTime, endTime, resolution] as const,
};

// ============================================================================
// useHeatmapQuery - Fetch current heatmap
// ============================================================================

/**
 * Options for configuring the useHeatmapQuery hook.
 */
export interface UseHeatmapQueryOptions {
  /** Camera ID to fetch heatmap for */
  cameraId?: string;
  /** Resolution level for heatmap aggregation */
  resolution?: HeatmapResolution;
  /** Colormap for visualization */
  colormap?: string;
  /** Whether to enable the query */
  enabled?: boolean;
  /** Refetch interval in milliseconds */
  refetchInterval?: number | false;
}

/**
 * Return type for useHeatmapQuery hook.
 */
export interface UseHeatmapQueryReturn {
  /** Heatmap data, undefined if not yet fetched */
  data: HeatmapResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch current heatmap for a camera.
 *
 * @param options - Configuration options
 * @returns Heatmap data and query state
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useHeatmapQuery({
 *   cameraId: 'front_door',
 *   resolution: 'hourly',
 *   colormap: 'jet',
 * });
 *
 * if (isLoading) return <Spinner />;
 * if (data) {
 *   return <img src={`data:image/png;base64,${data.image_base64}`} />;
 * }
 * ```
 */
export function useHeatmapQuery(options: UseHeatmapQueryOptions = {}): UseHeatmapQueryReturn {
  const {
    cameraId,
    resolution = 'hourly',
    colormap = 'jet',
    enabled = true,
    refetchInterval = false,
  } = options;

  const query = useQuery({
    queryKey: heatmapQueryKeys.current(cameraId ?? '', resolution, colormap),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchHeatmapData(cameraId, resolution, colormap);
    },
    enabled: enabled && !!cameraId,
    staleTime: DEFAULT_STALE_TIME,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useHeatmapHistoryQuery - Fetch historical heatmaps
// ============================================================================

/**
 * Options for configuring the useHeatmapHistoryQuery hook.
 */
export interface UseHeatmapHistoryQueryOptions {
  /** Camera ID to fetch history for */
  cameraId?: string;
  /** Time range to query */
  timeRange?: HeatmapTimeRange;
  /** Resolution level to filter by */
  resolution?: HeatmapResolution;
  /** Whether to enable the query */
  enabled?: boolean;
}

/**
 * Return type for useHeatmapHistoryQuery hook.
 */
export interface UseHeatmapHistoryQueryReturn {
  /** Heatmap history data, undefined if not yet fetched */
  data: HeatmapListResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch historical heatmap metadata for a camera.
 *
 * @param options - Configuration options
 * @returns Heatmap history data and query state
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useHeatmapHistoryQuery({
 *   cameraId: 'front_door',
 *   timeRange: '7d',
 *   resolution: 'daily',
 * });
 *
 * if (data) {
 *   return data.heatmaps.map((h) => <HistoryItem key={h.id} heatmap={h} />);
 * }
 * ```
 */
export function useHeatmapHistoryQuery(
  options: UseHeatmapHistoryQueryOptions = {}
): UseHeatmapHistoryQueryReturn {
  const { cameraId, timeRange = '24h', resolution, enabled = true } = options;

  const query = useQuery({
    queryKey: heatmapQueryKeys.history(cameraId ?? '', timeRange, resolution),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchHeatmapHistoryData(cameraId, timeRange, resolution);
    },
    enabled: enabled && !!cameraId,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useMergedHeatmapQuery - Fetch merged heatmap
// ============================================================================

/**
 * Options for configuring the useMergedHeatmapQuery hook.
 */
export interface UseMergedHeatmapQueryOptions {
  /** Camera ID to fetch merged heatmap for */
  cameraId?: string;
  /** Start time for the merge range */
  startTime?: Date;
  /** End time for the merge range */
  endTime?: Date;
  /** Resolution level to filter by */
  resolution?: HeatmapResolution;
  /** Whether to enable the query */
  enabled?: boolean;
}

/**
 * Return type for useMergedHeatmapQuery hook.
 */
export interface UseMergedHeatmapQueryReturn {
  /** Merged heatmap data, undefined if not yet fetched */
  data: HeatmapResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a merged heatmap for a custom time range.
 *
 * @param options - Configuration options
 * @returns Merged heatmap data and query state
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useMergedHeatmapQuery({
 *   cameraId: 'front_door',
 *   startTime: new Date('2026-01-01'),
 *   endTime: new Date('2026-01-31'),
 *   resolution: 'daily',
 * });
 *
 * if (data) {
 *   return <img src={`data:image/png;base64,${data.image_base64}`} />;
 * }
 * ```
 */
export function useMergedHeatmapQuery(
  options: UseMergedHeatmapQueryOptions = {}
): UseMergedHeatmapQueryReturn {
  const { cameraId, startTime, endTime, resolution, enabled = true } = options;

  // Memoize date strings to prevent unnecessary re-renders
  const startTimeStr = useMemo(() => startTime?.toISOString() ?? '', [startTime]);
  const endTimeStr = useMemo(() => endTime?.toISOString() ?? '', [endTime]);

  const query = useQuery({
    queryKey: heatmapQueryKeys.merged(cameraId ?? '', startTimeStr, endTimeStr, resolution),
    queryFn: () => {
      if (!cameraId || !startTime || !endTime) {
        throw new Error('Camera ID and time range are required');
      }
      return fetchMergedHeatmapData(cameraId, startTime, endTime, resolution);
    },
    enabled: enabled && !!cameraId && !!startTime && !!endTime,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}
