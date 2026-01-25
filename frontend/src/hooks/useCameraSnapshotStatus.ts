/**
 * useCameraSnapshotStatus - TanStack Query hook for camera snapshot availability (NEM-3579)
 *
 * This module provides a hook for checking camera snapshot availability using TanStack Query.
 * It provides detailed status information and helpful suggestions when snapshots are unavailable.
 *
 * Benefits:
 * - Check snapshot availability without downloading full images
 * - Get helpful error messages and troubleshooting suggestions
 * - Automatic caching and background refetching
 *
 * @module hooks/useCameraSnapshotStatus
 */

import { useQuery } from '@tanstack/react-query';

import {
  checkCameraSnapshot,
  getCameraSnapshotUrl,
  type CameraSnapshotStatus,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useCameraSnapshotStatus hook.
 */
export interface UseCameraSnapshotStatusOptions {
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

  /**
   * Refetch interval in milliseconds.
   * Useful for monitoring cameras that may come online.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useCameraSnapshotStatus hook.
 */
export interface UseCameraSnapshotStatusReturn {
  /** Snapshot status data, undefined if not yet fetched */
  status: CameraSnapshotStatus | undefined;
  /** Whether the snapshot is available */
  isAvailable: boolean;
  /** The snapshot URL (always available, but may return 404) */
  snapshotUrl: string;
  /** Error message if snapshot is not available */
  error: string | undefined;
  /** Suggestion for resolving the issue */
  suggestion: string | undefined;
  /** Whether the initial check is in progress */
  isLoading: boolean;
  /** Whether any check is in progress (initial or background) */
  isChecking: boolean;
  /** Whether the query has errored (network error, not 404) */
  isError: boolean;
  /** Function to manually trigger a recheck */
  recheck: () => Promise<unknown>;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to check camera snapshot availability using TanStack Query.
 *
 * Uses a HEAD request to efficiently check if a snapshot is available
 * without downloading the full image. Provides helpful error messages
 * and suggestions when snapshots are unavailable.
 *
 * @param cameraId - The camera ID to check, or undefined to disable the query
 * @param options - Configuration options
 * @returns Snapshot status and query state
 *
 * @example
 * ```tsx
 * // Basic usage - check snapshot availability
 * const { isAvailable, snapshotUrl, error, suggestion } = useCameraSnapshotStatus('front_door');
 *
 * if (isAvailable) {
 *   return <img src={snapshotUrl} alt="Camera snapshot" />;
 * }
 *
 * return (
 *   <div className="snapshot-unavailable">
 *     <p>Snapshot unavailable: {error}</p>
 *     <p className="text-muted">{suggestion}</p>
 *   </div>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With polling to detect when camera comes online
 * const { isAvailable, snapshotUrl, recheck } = useCameraSnapshotStatus('front_door', {
 *   refetchInterval: 30000, // Check every 30 seconds
 * });
 *
 * return (
 *   <div>
 *     {isAvailable ? (
 *       <img src={snapshotUrl} alt="Camera" />
 *     ) : (
 *       <div>
 *         <p>Waiting for camera...</p>
 *         <button onClick={() => recheck()}>Check Now</button>
 *       </div>
 *     )}
 *   </div>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // Conditional checking in a camera list
 * function CameraCard({ camera }: { camera: Camera }) {
 *   const { isAvailable, snapshotUrl } = useCameraSnapshotStatus(camera.id, {
 *     // Only check for cameras that are marked as online
 *     enabled: camera.status === 'online',
 *   });
 *
 *   return (
 *     <div className="camera-card">
 *       {isAvailable ? (
 *         <img src={snapshotUrl} alt={camera.name} />
 *       ) : (
 *         <div className="placeholder">No preview available</div>
 *       )}
 *       <h3>{camera.name}</h3>
 *     </div>
 *   );
 * }
 * ```
 */
export function useCameraSnapshotStatus(
  cameraId: string | undefined,
  options: UseCameraSnapshotStatusOptions = {}
): UseCameraSnapshotStatusReturn {
  const {
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    refetchInterval = false,
  } = options;

  // Always compute the URL so it's available even when query is disabled
  const snapshotUrl = cameraId ? getCameraSnapshotUrl(cameraId) : '';

  const query = useQuery<CameraSnapshotStatus, Error>({
    queryKey: queryKeys.cameras.snapshotStatus(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return checkCameraSnapshot(cameraId);
    },
    enabled: enabled && !!cameraId,
    staleTime,
    refetchInterval,
    // Reduced retry - we want fast feedback for snapshot checks
    retry: 1,
  });

  return {
    status: query.data,
    isAvailable: query.data?.available ?? false,
    snapshotUrl,
    error: query.data?.error,
    suggestion: query.data?.suggestion,
    isLoading: query.isLoading,
    isChecking: query.isFetching,
    isError: query.isError,
    recheck: query.refetch,
  };
}

// Re-export types for convenience
export type { CameraSnapshotStatus };
