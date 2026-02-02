/**
 * useSceneChangesQuery - Hook for fetching scene changes with filtering
 *
 * Provides React Query hooks for fetching scene changes from the API with
 * support for camera filtering, date ranges, and acknowledgement status.
 *
 * @module hooks/useSceneChangesQuery
 * @see NEM-4935 - Scene Change Detection History Page
 */

import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';

import { useCamerasQuery } from './useCamerasQuery';
import { fetchSceneChanges } from '../services/api';

import type { SceneChangeListResponse, SceneChangeResponse } from '../types/generated';

// ============================================================================
// Types
// ============================================================================

/**
 * Scene change type options for filtering.
 */
export type SceneChangeType = 'view_blocked' | 'angle_changed' | 'view_tampered' | 'all';

/**
 * Time range options for filtering.
 */
export type SceneChangeTimeRange = '1h' | '6h' | '24h' | '7d' | '30d' | 'all';

/**
 * Acknowledgement status filter.
 */
export type AcknowledgementFilter = 'all' | 'acknowledged' | 'unacknowledged';

/**
 * Options for the useSceneChangesQuery hook.
 */
export interface UseSceneChangesQueryOptions {
  /** Camera ID to filter by (undefined = all cameras) */
  cameraId?: string;
  /** Filter by change type */
  changeType?: SceneChangeType;
  /** Filter by time range */
  timeRange?: SceneChangeTimeRange;
  /** Filter by acknowledgement status */
  acknowledgementFilter?: AcknowledgementFilter;
  /** Maximum number of results to fetch per camera */
  limit?: number;
  /** Whether the query is enabled */
  enabled?: boolean;
}

/**
 * Extended scene change data with camera name.
 */
export interface SceneChangeWithCamera extends SceneChangeResponse {
  /** Camera ID */
  camera_id: string;
  /** Camera name for display */
  camera_name: string;
}

/**
 * Return type for the useSceneChangesQuery hook.
 */
export interface UseSceneChangesQueryReturn {
  /** List of scene changes with camera info */
  sceneChanges: SceneChangeWithCamera[];
  /** Whether data is loading */
  isLoading: boolean;
  /** Whether data is being refetched */
  isRefetching: boolean;
  /** Error if query failed */
  error: Error | null;
  /** Refetch the data */
  refetch: () => Promise<void>;
  /** Total count of scene changes */
  totalCount: number;
  /** Count of unacknowledged changes */
  unacknowledgedCount: number;
}

// ============================================================================
// Constants
// ============================================================================

/** Convert time range to milliseconds */
const TIME_RANGE_MS: Record<SceneChangeTimeRange, number | null> = {
  '1h': 60 * 60 * 1000,
  '6h': 6 * 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
  all: null,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for fetching scene changes with filtering support.
 *
 * Fetches scene changes from all cameras (or a specific camera) and
 * aggregates them into a single list with camera names resolved.
 *
 * @param options - Query options
 * @returns Scene changes data and query state
 *
 * @example
 * ```tsx
 * const { sceneChanges, isLoading, refetch } = useSceneChangesQuery({
 *   timeRange: '24h',
 *   acknowledgementFilter: 'unacknowledged',
 * });
 * ```
 */
export function useSceneChangesQuery(
  options: UseSceneChangesQueryOptions = {}
): UseSceneChangesQueryReturn {
  const {
    cameraId,
    changeType = 'all',
    timeRange = '24h',
    acknowledgementFilter = 'all',
    limit = 100,
    enabled = true,
  } = options;

  // Get cameras for name resolution and to know which cameras to query
  const { cameras, isLoading: isCamerasLoading } = useCamerasQuery({ enabled });

  // Build camera name lookup map
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const camera of cameras) {
      map.set(camera.id, camera.name);
    }
    return map;
  }, [cameras]);

  // Determine which cameras to query
  const cameraIds = useMemo(() => {
    if (cameraId) {
      return [cameraId];
    }
    return cameras.map((c) => c.id);
  }, [cameraId, cameras]);

  // Calculate cutoff date for time range filtering
  const cutoffDate = useMemo(() => {
    const ms = TIME_RANGE_MS[timeRange];
    if (ms === null) return null;
    return new Date(Date.now() - ms);
  }, [timeRange]);

  // Build query key
  const queryKey = useMemo(
    () => [
      'sceneChanges',
      {
        cameraIds,
        changeType,
        timeRange,
        acknowledgementFilter,
        limit,
      },
    ],
    [cameraIds, changeType, timeRange, acknowledgementFilter, limit]
  );

  // Fetch scene changes from all cameras
  const fetchAllSceneChanges = useCallback(async (): Promise<SceneChangeWithCamera[]> => {
    if (cameraIds.length === 0) {
      return [];
    }

    // Determine acknowledged filter for API
    let acknowledged: boolean | undefined;
    if (acknowledgementFilter === 'acknowledged') {
      acknowledged = true;
    } else if (acknowledgementFilter === 'unacknowledged') {
      acknowledged = false;
    }

    // Fetch from all cameras in parallel
    const results = await Promise.all(
      cameraIds.map(async (camId) => {
        try {
          const response: SceneChangeListResponse = await fetchSceneChanges(camId, {
            acknowledged,
            limit,
          });
          return {
            cameraId: camId,
            changes: response.scene_changes ?? [],
          };
        } catch {
          // If a camera fails, return empty array for that camera
          console.warn(`Failed to fetch scene changes for camera ${camId}`);
          return { cameraId: camId, changes: [] };
        }
      })
    );

    // Aggregate and enrich with camera names
    const allChanges: SceneChangeWithCamera[] = [];
    for (const { cameraId: camId, changes } of results) {
      const cameraName = cameraNameMap.get(camId) ?? camId;
      for (const change of changes) {
        allChanges.push({
          ...change,
          camera_id: camId,
          camera_name: cameraName,
        });
      }
    }

    // Apply client-side filters
    let filtered = allChanges;

    // Filter by time range
    if (cutoffDate) {
      filtered = filtered.filter((sc) => new Date(sc.detected_at) >= cutoffDate);
    }

    // Filter by change type
    if (changeType !== 'all') {
      filtered = filtered.filter((sc) => sc.change_type === changeType);
    }

    // Sort by detected_at descending (most recent first)
    filtered.sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime());

    return filtered;
  }, [cameraIds, cameraNameMap, acknowledgementFilter, limit, cutoffDate, changeType]);

  // Query
  const {
    data: sceneChanges = [],
    isLoading: isQueryLoading,
    isRefetching,
    error,
    refetch,
  } = useQuery({
    queryKey,
    queryFn: fetchAllSceneChanges,
    enabled: enabled && !isCamerasLoading && cameraIds.length > 0,
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // Refetch every minute
  });

  // Calculate counts
  const totalCount = sceneChanges.length;
  const unacknowledgedCount = sceneChanges.filter((sc) => !sc.acknowledged).length;

  // Refetch wrapper
  const handleRefetch = useCallback(async () => {
    await refetch();
  }, [refetch]);

  return {
    sceneChanges,
    isLoading: isCamerasLoading || isQueryLoading,
    isRefetching,
    error: error ?? null,
    refetch: handleRefetch,
    totalCount,
    unacknowledgedCount,
  };
}

export default useSceneChangesQuery;
