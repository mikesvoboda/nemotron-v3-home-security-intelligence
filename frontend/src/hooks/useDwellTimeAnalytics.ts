/**
 * useDwellTimeAnalytics - TanStack Query hooks for dwell time analytics (NEM-4714)
 *
 * This module provides hooks for fetching polygon zone dwell time data:
 * - usePolygonZones: Fetch polygon zones for a camera
 * - useDwellStatistics: Fetch dwell time statistics for a zone
 * - useActiveDwellers: Fetch active dwellers in a zone (with polling)
 *
 * @module hooks/useDwellTimeAnalytics
 * @see NEM-4714 Zone Analytics Dashboard Phase 2B
 */

import { useQuery } from '@tanstack/react-query';

import { DEFAULT_STALE_TIME, REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Constants
// ============================================================================

const API_BASE = '/api/analytics-zones';

/**
 * Polling interval for active dwellers (5 seconds for real-time feel).
 */
const ACTIVE_DWELLERS_POLL_INTERVAL = 5000;

// ============================================================================
// Types
// ============================================================================

/**
 * Dwell time statistics for a polygon zone.
 */
export interface DwellStatistics {
  /** Zone ID */
  zone_id: number;
  /** Total number of dwell records in the time range */
  total_records: number;
  /** Average dwell time in seconds (null if no records) */
  avg_dwell_seconds: number | null;
  /** Maximum dwell time in seconds (null if no records) */
  max_dwell_seconds: number | null;
  /** Minimum dwell time in seconds (null if no records) */
  min_dwell_seconds: number | null;
  /** Number of alerts triggered by dwell time threshold */
  alerts_triggered: number;
  /** Start of the time range (ISO format) */
  start_time: string;
  /** End of the time range (ISO format) */
  end_time: string;
}

/**
 * An active dweller currently in a zone.
 */
export interface ActiveDweller {
  /** Dwell record ID */
  record_id: number;
  /** Track ID of the entity */
  track_id: string;
  /** Camera ID */
  camera_id: string;
  /** Object class (e.g., 'person', 'vehicle') */
  object_class: string;
  /** Entry time (ISO format) */
  entry_time: string;
  /** Current dwell duration in seconds */
  current_dwell_seconds: number;
}

/**
 * Response from the active dwellers endpoint.
 */
export interface ActiveDwellersResponse {
  /** Zone ID */
  zone_id: number;
  /** List of active dwellers */
  dwellers: ActiveDweller[];
  /** Total count of active dwellers */
  total: number;
}

/**
 * A polygon zone with basic info.
 */
export interface PolygonZone {
  /** Zone ID */
  id: number;
  /** Zone name */
  name: string;
  /** Camera ID the zone belongs to */
  camera_id: string;
  /** Zone type */
  zone_type: string;
  /** Whether the zone is active */
  is_active: boolean;
  /** Current count of entities in the zone */
  current_count: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch dwell statistics for a specific polygon zone.
 */
async function fetchDwellStatistics(zoneId: number): Promise<DwellStatistics> {
  const response = await fetch(`${API_BASE}/polygon-zones/${zoneId}/dwell-statistics`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dwell statistics: ${response.statusText}`);
  }
  return response.json() as Promise<DwellStatistics>;
}

/**
 * Fetch active dwellers for a specific polygon zone.
 */
async function fetchActiveDwellers(zoneId: number): Promise<ActiveDwellersResponse> {
  const response = await fetch(`${API_BASE}/polygon-zones/${zoneId}/dwellers`);
  if (!response.ok) {
    throw new Error(`Failed to fetch active dwellers: ${response.statusText}`);
  }
  return response.json() as Promise<ActiveDwellersResponse>;
}

/**
 * Fetch polygon zones for a specific camera.
 */
async function fetchPolygonZones(cameraId: string): Promise<PolygonZone[]> {
  const response = await fetch(`${API_BASE}/polygon-zones/camera/${cameraId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch polygon zones: ${response.statusText}`);
  }
  const data = (await response.json()) as { zones: PolygonZone[] };
  return data.zones;
}

// ============================================================================
// Query Keys
// ============================================================================

export const dwellTimeAnalyticsQueryKeys = {
  all: ['dwell-time'] as const,
  polygonZones: (cameraId: string) => [...dwellTimeAnalyticsQueryKeys.all, 'polygon-zones', cameraId] as const,
  statistics: (zoneId: number) => [...dwellTimeAnalyticsQueryKeys.all, 'statistics', zoneId] as const,
  activeDwellers: (zoneId: number) => [...dwellTimeAnalyticsQueryKeys.all, 'dwellers', zoneId] as const,
};

// ============================================================================
// Options Types
// ============================================================================

/**
 * Options for the usePolygonZones hook.
 */
export interface UsePolygonZonesOptions {
  /** Camera ID to fetch polygon zones for */
  cameraId?: string;
  /** Whether the query is enabled */
  enabled?: boolean;
}

/**
 * Options for the useDwellStatistics hook.
 */
export interface UseDwellStatisticsOptions {
  /** Zone ID to fetch statistics for */
  zoneId?: number;
  /** Whether the query is enabled */
  enabled?: boolean;
}

/**
 * Options for the useActiveDwellers hook.
 */
export interface UseActiveDwellersOptions {
  /** Zone ID to fetch active dwellers for */
  zoneId?: number;
  /** Whether the query is enabled */
  enabled?: boolean;
  /** Whether to enable polling */
  enablePolling?: boolean;
}

// ============================================================================
// Return Types
// ============================================================================

/**
 * Return type for the usePolygonZones hook.
 */
export interface UsePolygonZonesReturn {
  /** List of polygon zones */
  polygonZones: PolygonZone[];
  /** Whether the query is loading */
  isLoading: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Refetch function */
  refetch: () => void;
}

/**
 * Return type for the useDwellStatistics hook.
 */
export interface UseDwellStatisticsReturn {
  /** Dwell statistics data */
  statistics: DwellStatistics | undefined;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Refetch function */
  refetch: () => void;
}

/**
 * Return type for the useActiveDwellers hook.
 */
export interface UseActiveDwellersReturn {
  /** Active dwellers response */
  data: ActiveDwellersResponse | undefined;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Refetch function */
  refetch: () => void;
}

// ============================================================================
// Hook Implementations
// ============================================================================

/**
 * Hook to fetch polygon zones for a camera.
 *
 * @param options - Configuration options
 * @returns Polygon zones data, loading state, and error
 *
 * @example
 * ```tsx
 * const { polygonZones, isLoading } = usePolygonZones({
 *   cameraId: 'cam-123',
 * });
 * ```
 */
export function usePolygonZones(
  options: UsePolygonZonesOptions = {}
): UsePolygonZonesReturn {
  const { cameraId, enabled = true } = options;

  const query = useQuery({
    queryKey: dwellTimeAnalyticsQueryKeys.polygonZones(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchPolygonZones(cameraId);
    },
    enabled: enabled && !!cameraId,
    staleTime: DEFAULT_STALE_TIME,
  });

  return {
    polygonZones: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: () => void query.refetch(),
  };
}

/**
 * Hook to fetch dwell statistics for a polygon zone.
 *
 * @param options - Configuration options
 * @returns Dwell statistics data, loading state, and error
 *
 * @example
 * ```tsx
 * const { statistics, isLoading } = useDwellStatistics({
 *   zoneId: 123,
 * });
 * ```
 */
export function useDwellStatistics(
  options: UseDwellStatisticsOptions = {}
): UseDwellStatisticsReturn {
  const { zoneId, enabled = true } = options;

  const query = useQuery({
    queryKey: dwellTimeAnalyticsQueryKeys.statistics(zoneId ?? 0),
    queryFn: () => {
      if (zoneId === undefined) {
        throw new Error('Zone ID is required');
      }
      return fetchDwellStatistics(zoneId);
    },
    enabled: enabled && zoneId !== undefined,
    staleTime: DEFAULT_STALE_TIME,
  });

  return {
    statistics: query.data,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: () => void query.refetch(),
  };
}

/**
 * Hook to fetch active dwellers for a polygon zone.
 *
 * Supports automatic polling for real-time updates.
 *
 * @param options - Configuration options
 * @returns Active dwellers data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useActiveDwellers({
 *   zoneId: 123,
 *   enablePolling: true,
 * });
 * ```
 */
export function useActiveDwellers(
  options: UseActiveDwellersOptions = {}
): UseActiveDwellersReturn {
  const { zoneId, enabled = true, enablePolling = false } = options;

  const query = useQuery({
    queryKey: dwellTimeAnalyticsQueryKeys.activeDwellers(zoneId ?? 0),
    queryFn: () => {
      if (zoneId === undefined) {
        throw new Error('Zone ID is required');
      }
      return fetchActiveDwellers(zoneId);
    },
    enabled: enabled && zoneId !== undefined,
    staleTime: REALTIME_STALE_TIME,
    refetchInterval: enablePolling ? ACTIVE_DWELLERS_POLL_INTERVAL : false,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: () => void query.refetch(),
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format a duration in seconds to a human-readable string.
 *
 * @param seconds - Duration in seconds (or null)
 * @returns Formatted string like "5m 30s" or "--" for null values
 *
 * @example
 * ```tsx
 * formatDuration(90);   // "1m 30s"
 * formatDuration(45);   // "45s"
 * formatDuration(null); // "--"
 * ```
 */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) return '--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

export default usePolygonZones;
