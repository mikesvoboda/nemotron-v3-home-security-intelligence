/**
 * useLineZoneAnalytics - TanStack Query hooks for line zone analytics (NEM-4714)
 *
 * This module provides hooks for fetching line zone data and crossing trends:
 * - useLineZoneAnalytics: Fetch line zones for a camera with crossing counts
 * - useCrossingTrends: Fetch crossing trend data for a specific zone
 * - useResetCrossingCounts: Reset crossing counts for a zone
 *
 * @module hooks/useLineZoneAnalytics
 * @see NEM-4714 Zone Analytics Dashboard Phase 1C
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type { CrossingTrendsResponse, LineZoneWithCounts } from '../types/zoneAnalytics';

// ============================================================================
// Constants
// ============================================================================

const API_BASE = '/api/analytics-zones';

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch line zones for a specific camera with crossing counts.
 */
async function fetchLineZones(cameraId: string): Promise<LineZoneWithCounts[]> {
  const response = await fetch(`${API_BASE}/line-zones/camera/${cameraId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch line zones: ${response.statusText}`);
  }
  const data = (await response.json()) as { zones: LineZoneWithCounts[] };
  return data.zones;
}

/**
 * Fetch crossing trends for a specific line zone.
 */
async function fetchCrossingTrends(
  zoneId: number,
  interval: 'hour' | 'day' = 'hour'
): Promise<CrossingTrendsResponse> {
  const response = await fetch(
    `${API_BASE}/line-zones/${zoneId}/crossing-trends?interval=${interval}`
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch crossing trends: ${response.statusText}`);
  }
  return response.json() as Promise<CrossingTrendsResponse>;
}

/**
 * Reset crossing counts for a specific line zone.
 */
async function resetCrossingCounts(zoneId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/line-zones/${zoneId}/reset-counts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  if (!response.ok) {
    throw new Error(`Failed to reset counts: ${response.statusText}`);
  }
}

// ============================================================================
// Query Keys
// ============================================================================

export const lineZoneAnalyticsQueryKeys = {
  all: ['line-zones'] as const,
  forCamera: (cameraId: string) => [...lineZoneAnalyticsQueryKeys.all, 'camera', cameraId] as const,
  trends: (zoneId: number, interval: 'hour' | 'day') =>
    ['crossing-trends', zoneId, interval] as const,
};

// ============================================================================
// Types
// ============================================================================

/**
 * Options for the useLineZoneAnalytics hook.
 */
export interface UseLineZoneAnalyticsOptions {
  /** Camera ID to fetch line zones for */
  cameraId?: string;
  /** Whether the query is enabled */
  enabled?: boolean;
}

/**
 * Return type for the useLineZoneAnalytics hook.
 */
export interface UseLineZoneAnalyticsReturn {
  /** List of line zones with crossing counts */
  lineZones: LineZoneWithCounts[];
  /** Whether the query is loading */
  isLoading: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Refetch function */
  refetch: () => void;
}

/**
 * Options for the useCrossingTrends hook.
 */
export interface UseCrossingTrendsOptions {
  /** Zone ID to fetch trends for */
  zoneId?: number;
  /** Time interval for aggregation */
  interval?: 'hour' | 'day';
  /** Whether the query is enabled */
  enabled?: boolean;
}

// ============================================================================
// Hook Implementations
// ============================================================================

/**
 * Hook to fetch line zones for a camera with crossing counts.
 *
 * @param options - Configuration options
 * @returns Line zones data, loading state, and error
 *
 * @example
 * ```tsx
 * const { lineZones, isLoading } = useLineZoneAnalytics({
 *   cameraId: 'cam-123',
 * });
 * ```
 */
export function useLineZoneAnalytics(
  options: UseLineZoneAnalyticsOptions = {}
): UseLineZoneAnalyticsReturn {
  const { cameraId, enabled = true } = options;

  const query = useQuery({
    queryKey: lineZoneAnalyticsQueryKeys.forCamera(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchLineZones(cameraId);
    },
    enabled: enabled && !!cameraId,
    staleTime: DEFAULT_STALE_TIME,
  });

  return {
    lineZones: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: () => void query.refetch(),
  };
}

/**
 * Hook to fetch crossing trends for a specific line zone.
 *
 * @param options - Configuration options
 * @returns Crossing trends data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useCrossingTrends({
 *   zoneId: 123,
 *   interval: 'hour',
 * });
 * ```
 */
export function useCrossingTrends(options: UseCrossingTrendsOptions = {}) {
  const { zoneId, interval = 'hour', enabled = true } = options;

  return useQuery({
    queryKey: lineZoneAnalyticsQueryKeys.trends(zoneId ?? 0, interval),
    queryFn: () => {
      if (zoneId === undefined) {
        throw new Error('Zone ID is required');
      }
      return fetchCrossingTrends(zoneId, interval);
    },
    enabled: enabled && zoneId !== undefined,
    staleTime: DEFAULT_STALE_TIME,
  });
}

/**
 * Hook to reset crossing counts for a line zone.
 *
 * @returns Mutation function and state
 *
 * @example
 * ```tsx
 * const { mutate: resetCounts, isPending } = useResetCrossingCounts();
 * resetCounts(zoneId);
 * ```
 */
export function useResetCrossingCounts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: resetCrossingCounts,
    onSuccess: (_, zoneId) => {
      // Invalidate line zones to refresh counts
      void queryClient.invalidateQueries({ queryKey: lineZoneAnalyticsQueryKeys.all });
      // Invalidate trends for this specific zone
      void queryClient.invalidateQueries({
        queryKey: ['crossing-trends', zoneId],
      });
    },
  });
}

export default useLineZoneAnalytics;
