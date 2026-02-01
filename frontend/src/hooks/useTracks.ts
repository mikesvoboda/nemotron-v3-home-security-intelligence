/**
 * useTracks - TanStack Query hooks for track data management
 *
 * This module provides hooks for fetching track data using TanStack Query.
 * Tracks represent object trajectories detected by cameras over time.
 *
 * Features:
 * - useCameraTracks: Fetch paginated tracks for a camera
 * - useCameraTracksStats: Fetch track statistics for a camera
 * - useActiveTracks: Fetch currently active tracks (with auto-refresh)
 * - useTrack: Fetch a single track by ID
 * - useTrackHistory: Fetch detailed trajectory history for a track
 *
 * @module hooks/useTracks
 * @see NEM-4766 Track Service API implementation
 */

import { useQuery } from '@tanstack/react-query';

import { fetchApi } from '../services/api';
import { DEFAULT_STALE_TIME, REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * A point in a track's trajectory with position and timestamp
 */
export interface TrajectoryPoint {
  /** X coordinate (0-1 normalized or pixel value depending on API) */
  x: number;
  /** Y coordinate (0-1 normalized or pixel value depending on API) */
  y: number;
  /** ISO timestamp when this point was recorded */
  timestamp: string;
}

/**
 * Movement metrics calculated from a track's trajectory
 */
export interface MovementMetrics {
  /** Total distance traveled in pixels or normalized units */
  total_distance: number;
  /** Average speed in units per second */
  avg_speed: number;
  /** Primary direction of movement in degrees (0-360), null if stationary */
  direction: number | null;
  /** Total duration of the track in seconds */
  duration_seconds: number;
}

/**
 * A track representing an object's movement over time
 */
export interface Track {
  /** Unique database ID for this track record */
  id: number;
  /** Track ID assigned by the tracker (may be reused across sessions) */
  track_id: number;
  /** Camera ID where this track was detected */
  camera_id: string;
  /** Object class (e.g., 'person', 'vehicle', 'animal') */
  object_class: string;
  /** ISO timestamp when the track was first detected */
  first_seen: string;
  /** ISO timestamp when the track was last updated */
  last_seen: string;
  /** Computed movement metrics, null if not yet calculated */
  metrics: MovementMetrics | null;
}

/**
 * Extended track data including full trajectory history
 */
export interface TrackHistory extends Track {
  /** Full list of trajectory points for this track */
  trajectory: TrajectoryPoint[];
  /** Movement metrics (always present for history) */
  metrics: MovementMetrics;
}

/**
 * Paginated response for track list queries
 */
export interface TrackListResponse {
  /** List of tracks for the current page */
  tracks: Track[];
  /** Total number of tracks matching the query */
  total: number;
  /** Current page number (1-indexed) */
  page: number;
  /** Number of tracks per page */
  page_size: number;
}

/**
 * Response for active tracks query
 */
export interface ActiveTracksResponse {
  /** List of currently active tracks */
  tracks: Track[];
  /** Number of active tracks */
  count: number;
}

/**
 * Statistics for tracks on a specific camera
 */
export interface CameraTrackStats {
  /** Number of currently active tracks */
  active_count: number;
  /** Total number of tracks detected today */
  total_today: number;
  /** Average track duration in seconds */
  avg_duration_seconds: number;
  /** Track counts grouped by object type */
  by_object_type: Record<string, number>;
}

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Query key factory for track-related queries.
 * Enables granular cache invalidation and type-safe key generation.
 */
export const trackQueryKeys = {
  /** Base key for all track queries */
  all: ['tracks'] as const,
  /** Camera-specific track queries */
  camera: {
    /** Tracks for a specific camera with filters */
    list: (
      cameraId: string,
      options?: { objectClass?: string; page?: number; pageSize?: number }
    ) => [...trackQueryKeys.all, 'camera', cameraId, 'list', options] as const,
    /** Track statistics for a camera */
    stats: (cameraId: string) => [...trackQueryKeys.all, 'camera', cameraId, 'stats'] as const,
    /** Active tracks for a camera */
    active: (cameraId: string) => [...trackQueryKeys.all, 'camera', cameraId, 'active'] as const,
  },
  /** Single track queries */
  detail: (trackId: number) => [...trackQueryKeys.all, 'detail', trackId] as const,
  /** Track history queries */
  history: (trackId: number) => [...trackQueryKeys.all, 'history', trackId] as const,
} as const;

// ============================================================================
// useCameraTracks - Fetch paginated tracks for a camera
// ============================================================================

/**
 * Options for configuring the useCameraTracks hook
 */
export interface UseCameraTracksOptions {
  /** Filter tracks by object class (e.g., 'person', 'vehicle') */
  objectClass?: string;
  /** Page number (1-indexed) */
  page?: number;
  /** Number of tracks per page */
  pageSize?: number;
}

/**
 * Return type for the useCameraTracks hook
 */
export interface UseCameraTracksReturn {
  /** List of tracks for the current page */
  tracks: Track[];
  /** Total number of tracks matching the query */
  total: number;
  /** Current page number */
  page: number;
  /** Number of tracks per page */
  pageSize: number;
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
 * Hook to fetch paginated tracks for a camera using TanStack Query.
 *
 * @param cameraId - Camera ID to fetch tracks for
 * @param options - Pagination and filter options
 * @returns Track list and query state
 *
 * @example
 * ```tsx
 * const { tracks, total, isLoading } = useCameraTracks('cam-123', {
 *   objectClass: 'person',
 *   page: 1,
 *   pageSize: 20,
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     <p>Total tracks: {total}</p>
 *     <TrackList tracks={tracks} />
 *   </div>
 * );
 * ```
 */
export function useCameraTracks(
  cameraId: string,
  options?: UseCameraTracksOptions
): UseCameraTracksReturn {
  const query = useQuery({
    queryKey: trackQueryKeys.camera.list(cameraId, options),
    queryFn: () => {
      const params = new URLSearchParams();
      if (options?.objectClass) params.set('object_class', options.objectClass);
      if (options?.page) params.set('page', String(options.page));
      if (options?.pageSize) params.set('page_size', String(options.pageSize));
      const queryString = params.toString();
      return fetchApi<TrackListResponse>(
        `/api/cameras/${cameraId}/tracks${queryString ? `?${queryString}` : ''}`
      );
    },
    enabled: !!cameraId,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    tracks: query.data?.tracks ?? [],
    total: query.data?.total ?? 0,
    page: query.data?.page ?? 1,
    pageSize: query.data?.page_size ?? 20,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useCameraTracksStats - Fetch track statistics for a camera
// ============================================================================

/**
 * Return type for the useCameraTracksStats hook
 */
export interface UseCameraTracksStatsReturn {
  /** Track statistics data */
  data: CameraTrackStats | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch track statistics for a camera using TanStack Query.
 *
 * @param cameraId - Camera ID to fetch statistics for
 * @returns Track statistics and query state
 *
 * @example
 * ```tsx
 * const { data: stats, isLoading } = useCameraTracksStats('cam-123');
 *
 * if (isLoading) return <Spinner />;
 * if (!stats) return null;
 *
 * return (
 *   <div>
 *     <p>Active: {stats.active_count}</p>
 *     <p>Today: {stats.total_today}</p>
 *     <p>Avg Duration: {stats.avg_duration_seconds}s</p>
 *   </div>
 * );
 * ```
 */
export function useCameraTracksStats(cameraId: string): UseCameraTracksStatsReturn {
  const query = useQuery({
    queryKey: trackQueryKeys.camera.stats(cameraId),
    queryFn: () => fetchApi<CameraTrackStats>(`/api/cameras/${cameraId}/tracks/stats`),
    enabled: !!cameraId,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useActiveTracks - Fetch currently active tracks with auto-refresh
// ============================================================================

/**
 * Options for configuring the useActiveTracks hook
 */
export interface UseActiveTracksOptions {
  /**
   * Refetch interval in milliseconds.
   * @default 5000 (5 seconds)
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useActiveTracks hook
 */
export interface UseActiveTracksReturn {
  /** List of currently active tracks */
  tracks: Track[];
  /** Number of active tracks */
  count: number;
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
 * Hook to fetch currently active tracks for a camera with automatic refresh.
 *
 * By default, this hook refetches every 5 seconds to keep the active tracks
 * list up-to-date. Use the refetchInterval option to customize or disable.
 *
 * @param cameraId - Camera ID to fetch active tracks for
 * @param options - Configuration options
 * @returns Active tracks and query state
 *
 * @example
 * ```tsx
 * const { tracks, count, isLoading } = useActiveTracks('cam-123');
 *
 * return (
 *   <div>
 *     <h3>{count} Active Tracks</h3>
 *     {tracks.map(track => (
 *       <TrackIndicator key={track.id} track={track} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useActiveTracks(
  cameraId: string,
  options?: UseActiveTracksOptions
): UseActiveTracksReturn {
  const { refetchInterval = 5000 } = options ?? {};

  const query = useQuery({
    queryKey: trackQueryKeys.camera.active(cameraId),
    queryFn: () => fetchApi<ActiveTracksResponse>(`/api/cameras/${cameraId}/tracks/active`),
    enabled: !!cameraId,
    staleTime: REALTIME_STALE_TIME,
    refetchInterval,
    retry: 1,
  });

  return {
    tracks: query.data?.tracks ?? [],
    count: query.data?.count ?? 0,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useTrack - Fetch a single track by ID
// ============================================================================

/**
 * Return type for the useTrack hook
 */
export interface UseTrackReturn {
  /** Track data */
  data: Track | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single track by ID using TanStack Query.
 *
 * @param trackId - Track ID to fetch
 * @returns Track data and query state
 *
 * @example
 * ```tsx
 * const { data: track, isLoading, error } = useTrack(123);
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 * if (!track) return null;
 *
 * return <TrackDetails track={track} />;
 * ```
 */
export function useTrack(trackId: number): UseTrackReturn {
  const query = useQuery({
    queryKey: trackQueryKeys.detail(trackId),
    queryFn: () => fetchApi<Track>(`/api/tracks/${trackId}`),
    enabled: !!trackId,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useTrackHistory - Fetch detailed trajectory history for a track
// ============================================================================

/**
 * Return type for the useTrackHistory hook
 */
export interface UseTrackHistoryReturn {
  /** Track history data including full trajectory */
  data: TrackHistory | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch detailed trajectory history for a track using TanStack Query.
 *
 * This hook retrieves the full trajectory with all recorded points,
 * useful for visualizing the complete path of a tracked object.
 *
 * @param trackId - Track ID to fetch history for
 * @returns Track history data and query state
 *
 * @example
 * ```tsx
 * const { data: history, isLoading } = useTrackHistory(123);
 *
 * if (isLoading) return <Spinner />;
 * if (!history) return null;
 *
 * return (
 *   <div>
 *     <p>Distance: {history.metrics.total_distance}</p>
 *     <p>Duration: {history.metrics.duration_seconds}s</p>
 *     <TrajectoryVisualization points={history.trajectory} />
 *   </div>
 * );
 * ```
 */
export function useTrackHistory(trackId: number): UseTrackHistoryReturn {
  const query = useQuery({
    queryKey: trackQueryKeys.history(trackId),
    queryFn: () => fetchApi<TrackHistory>(`/api/tracks/${trackId}/history`),
    enabled: !!trackId,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
