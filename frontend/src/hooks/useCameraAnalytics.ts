/**
 * useCameraAnalytics - Comprehensive hook for per-camera analytics
 *
 * This hook combines camera list data with detection statistics to provide
 * a complete analytics view. It supports:
 * - Camera selection with URL persistence for deep linking
 * - Automatic stats filtering by selected camera
 * - "All Cameras" aggregate view
 *
 * @module hooks/useCameraAnalytics
 */

import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useCamerasQuery } from './useCamerasQuery';
import { useDetectionStatsQuery } from './useDetectionStatsQuery';

import type { Camera, DetectionStatsResponse } from '../services/api';

/**
 * Camera option for selector dropdown.
 * Includes the "All Cameras" option with empty id.
 */
export interface CameraOption {
  /** Camera ID, empty string for "All Cameras" */
  id: string;
  /** Camera display name */
  name: string;
}

/**
 * Return type for the useCameraAnalytics hook
 */
export interface UseCameraAnalyticsReturn {
  // Camera data
  /** List of all cameras */
  cameras: Camera[];
  /** Cameras with "All Cameras" option prepended */
  camerasWithAll: CameraOption[];
  /** Whether cameras are loading */
  isLoadingCameras: boolean;
  /** Camera fetch error if any */
  camerasError: Error | null;

  // Selection state
  /** Currently selected camera ID, undefined for "All Cameras" */
  selectedCameraId: string | undefined;
  /** Set the selected camera ID (empty string for "All Cameras") */
  setSelectedCameraId: (cameraId: string) => void;
  /** Full camera object for selected camera, undefined for "All Cameras" */
  selectedCamera: Camera | undefined;

  // Detection stats
  /** Detection statistics (filtered by camera if selected) */
  stats: DetectionStatsResponse | undefined;
  /** Total detections count */
  totalDetections: number;
  /** Detections grouped by object class */
  detectionsByClass: Record<string, number>;
  /** Average confidence score */
  averageConfidence: number | null;
  /** Whether stats are loading */
  isLoadingStats: boolean;
  /** Stats fetch error if any */
  statsError: Error | null;

  // Combined states
  /** Whether any data is loading */
  isLoading: boolean;
  /** Function to refetch all data */
  refetch: () => Promise<void>;
}

/** URL parameter name for camera selection */
const CAMERA_PARAM = 'camera';

/**
 * Hook for comprehensive per-camera analytics with URL persistence.
 *
 * Combines camera list with detection statistics, supporting both
 * aggregate "All Cameras" view and per-camera filtered views.
 * The selected camera is persisted to URL for deep linking.
 *
 * @returns Camera analytics data and selection controls
 *
 * @example
 * ```tsx
 * // Basic usage in analytics page
 * function AnalyticsPage() {
 *   const {
 *     camerasWithAll,
 *     selectedCameraId,
 *     setSelectedCameraId,
 *     stats,
 *     isLoading,
 *   } = useCameraAnalytics();
 *
 *   if (isLoading) return <Spinner />;
 *
 *   return (
 *     <div>
 *       <CameraSelector
 *         cameras={camerasWithAll}
 *         selected={selectedCameraId ?? ''}
 *         onChange={setSelectedCameraId}
 *       />
 *       <StatsDisplay stats={stats} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useCameraAnalytics(): UseCameraAnalyticsReturn {
  const [searchParams, setSearchParams] = useSearchParams();

  // Get selected camera from URL
  const selectedCameraId = searchParams.get(CAMERA_PARAM) ?? undefined;

  // Fetch camera list (disable placeholder data for cleaner UX)
  const {
    cameras,
    isLoading: isLoadingCameras,
    error: camerasError,
    refetch: refetchCameras,
  } = useCamerasQuery({ placeholderCount: 0 });

  // Fetch detection stats (filtered by camera if selected)
  const {
    data: stats,
    totalDetections,
    detectionsByClass,
    averageConfidence,
    isLoading: isLoadingStats,
    error: statsError,
    refetch: refetchStats,
  } = useDetectionStatsQuery(
    selectedCameraId ? { camera_id: selectedCameraId } : {}
  );

  // Set selected camera (updates URL)
  const setSelectedCameraId = useCallback(
    (cameraId: string) => {
      setSearchParams(
        (prev) => {
          const newParams = new URLSearchParams(prev);
          if (cameraId) {
            newParams.set(CAMERA_PARAM, cameraId);
          } else {
            newParams.delete(CAMERA_PARAM);
          }
          return newParams;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  // Get full camera object for selected camera
  const selectedCamera = useMemo(() => {
    if (!selectedCameraId) return undefined;
    return cameras.find((cam) => cam.id === selectedCameraId);
  }, [cameras, selectedCameraId]);

  // Build cameras with "All Cameras" option
  const camerasWithAll = useMemo((): CameraOption[] => {
    const allOption: CameraOption = {
      id: '',
      name: 'All Cameras',
    };
    const cameraOptions: CameraOption[] = cameras.map((cam) => ({
      id: cam.id,
      name: cam.name,
    }));
    return [allOption, ...cameraOptions];
  }, [cameras]);

  // Combined loading state
  const isLoading = isLoadingCameras || isLoadingStats;

  // Combined refetch function
  const refetch = useCallback(async () => {
    await Promise.all([refetchCameras(), refetchStats()]);
  }, [refetchCameras, refetchStats]);

  return {
    // Camera data
    cameras,
    camerasWithAll,
    isLoadingCameras,
    camerasError,

    // Selection state
    selectedCameraId,
    setSelectedCameraId,
    selectedCamera,

    // Detection stats
    stats,
    totalDetections,
    detectionsByClass,
    averageConfidence,
    isLoadingStats,
    statsError,

    // Combined states
    isLoading,
    refetch,
  };
}
