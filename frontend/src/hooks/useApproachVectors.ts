/**
 * useApproachVectors - TanStack Query hooks for approach vector analytics (NEM-4936)
 *
 * This module provides hooks for fetching approach vector data:
 * - useZoneApproachVectors: Fetch approach vectors for a single zone
 * - useCameraApproachVectors: Fetch approach vectors for all zones on a camera
 *
 * Approach vectors show entities moving toward zones with ETA and urgency.
 *
 * @module hooks/useApproachVectors
 * @see NEM-4936 Zone: Approach Vector Visualization (ETA to Zone)
 */

import { useQuery } from '@tanstack/react-query';

import { REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Constants
// ============================================================================

const API_BASE = '/api/analytics-zones';

/**
 * Polling interval for approach vectors (2 seconds for real-time tracking).
 */
const APPROACH_VECTORS_POLL_INTERVAL = 2000;

// ============================================================================
// Types
// ============================================================================

/**
 * Urgency levels based on ETA to zone.
 */
export type ApproachUrgency = 'imminent' | 'approaching' | 'distant' | 'not_approaching';

/**
 * Position in normalized coordinates (0-1).
 */
export interface NormalizedPosition {
  /** X coordinate (0-1, left to right) */
  x: number;
  /** Y coordinate (0-1, top to bottom) */
  y: number;
}

/**
 * Approach vector data for a single entity.
 */
export interface ApproachVectorData {
  /** Tracking ID of the approaching entity */
  track_id: number;
  /** Object classification (person, vehicle, etc.) */
  object_class: string;
  /** Whether entity is moving toward the zone */
  is_approaching: boolean;
  /** Direction of movement in degrees (0=up, 90=right, 180=down, 270=left) */
  direction_degrees: number;
  /** Speed of movement in normalized units per second */
  speed_normalized: number;
  /** Current distance to zone boundary (normalized units, 0 = inside) */
  distance_to_zone: number;
  /** Estimated time to reach zone in seconds (null if not approaching) */
  estimated_arrival_seconds: number | null;
  /** Urgency level based on ETA */
  urgency: ApproachUrgency;
  /** Current position in normalized coordinates */
  current_position: NormalizedPosition;
  /** Zone centroid in normalized coordinates */
  zone_centroid: NormalizedPosition;
}

/**
 * Response containing approach vectors for a zone.
 */
export interface ZoneApproachVectorsResponse {
  /** Zone ID */
  zone_id: number;
  /** Zone name */
  zone_name: string;
  /** Approach vectors for all tracked entities */
  approach_vectors: ApproachVectorData[];
  /** Total number of entities approaching */
  total_approaching: number;
  /** Number of entities with imminent arrival (ETA < 3s) */
  imminent_count: number;
  /** Timestamp of the analysis */
  timestamp: string;
}

/**
 * Response containing approach vectors for all zones on a camera.
 */
export interface CameraApproachVectorsResponse {
  /** Camera ID */
  camera_id: string;
  /** Approach vectors per zone */
  zones: ZoneApproachVectorsResponse[];
  /** Total number of zones analyzed */
  total_zones: number;
  /** Total approaching entities across all zones */
  total_approaching_entities: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch approach vectors for a specific polygon zone.
 */
async function fetchZoneApproachVectors(
  zoneId: number
): Promise<ZoneApproachVectorsResponse> {
  const response = await fetch(
    `${API_BASE}/polygon-zones/${zoneId}/approach-vectors`
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch approach vectors: ${response.statusText}`);
  }
  return response.json() as Promise<ZoneApproachVectorsResponse>;
}

/**
 * Fetch approach vectors for all zones on a camera.
 */
async function fetchCameraApproachVectors(
  cameraId: string
): Promise<CameraApproachVectorsResponse> {
  const response = await fetch(
    `${API_BASE}/approach-vectors/camera/${cameraId}`
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch camera approach vectors: ${response.statusText}`);
  }
  return response.json() as Promise<CameraApproachVectorsResponse>;
}

// ============================================================================
// Query Keys
// ============================================================================

export const approachVectorsQueryKeys = {
  all: ['approach-vectors'] as const,
  zone: (zoneId: number) =>
    [...approachVectorsQueryKeys.all, 'zone', zoneId] as const,
  camera: (cameraId: string) =>
    [...approachVectorsQueryKeys.all, 'camera', cameraId] as const,
};

// ============================================================================
// Options Types
// ============================================================================

/**
 * Options for the useZoneApproachVectors hook.
 */
export interface UseZoneApproachVectorsOptions {
  /** Zone ID to fetch approach vectors for */
  zoneId?: number;
  /** Whether the query is enabled */
  enabled?: boolean;
  /** Whether to enable polling for real-time updates */
  enablePolling?: boolean;
}

/**
 * Options for the useCameraApproachVectors hook.
 */
export interface UseCameraApproachVectorsOptions {
  /** Camera ID to fetch approach vectors for */
  cameraId?: string;
  /** Whether the query is enabled */
  enabled?: boolean;
  /** Whether to enable polling for real-time updates */
  enablePolling?: boolean;
}

// ============================================================================
// Return Types
// ============================================================================

/**
 * Return type for the useZoneApproachVectors hook.
 */
export interface UseZoneApproachVectorsReturn {
  /** Approach vectors data */
  data: ZoneApproachVectorsResponse | undefined;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Refetch function */
  refetch: () => void;
}

/**
 * Return type for the useCameraApproachVectors hook.
 */
export interface UseCameraApproachVectorsReturn {
  /** Camera approach vectors data */
  data: CameraApproachVectorsResponse | undefined;
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
 * Hook to fetch approach vectors for a polygon zone.
 *
 * Supports automatic polling for real-time tracking updates.
 *
 * @param options - Configuration options
 * @returns Approach vectors data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useZoneApproachVectors({
 *   zoneId: 123,
 *   enablePolling: true,
 * });
 *
 * // Show approaching entities
 * data?.approach_vectors.filter(v => v.is_approaching).forEach(v => {
 *   console.log(`Track ${v.track_id} ETA: ${v.estimated_arrival_seconds}s`);
 * });
 * ```
 */
export function useZoneApproachVectors(
  options: UseZoneApproachVectorsOptions = {}
): UseZoneApproachVectorsReturn {
  const { zoneId, enabled = true, enablePolling = false } = options;

  const query = useQuery({
    queryKey: approachVectorsQueryKeys.zone(zoneId ?? 0),
    queryFn: () => {
      if (zoneId === undefined) {
        throw new Error('Zone ID is required');
      }
      return fetchZoneApproachVectors(zoneId);
    },
    enabled: enabled && zoneId !== undefined,
    staleTime: REALTIME_STALE_TIME,
    refetchInterval: enablePolling ? APPROACH_VECTORS_POLL_INTERVAL : false,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: () => void query.refetch(),
  };
}

/**
 * Hook to fetch approach vectors for all zones on a camera.
 *
 * Supports automatic polling for real-time tracking updates.
 * This is the recommended hook for camera overlay visualization.
 *
 * @param options - Configuration options
 * @returns Camera approach vectors data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useCameraApproachVectors({
 *   cameraId: 'cam-123',
 *   enablePolling: true,
 * });
 *
 * // Render approach vectors on camera overlay
 * data?.zones.forEach(zone => {
 *   zone.approach_vectors.forEach(v => {
 *     // Draw arrow from v.current_position toward zone
 *   });
 * });
 * ```
 */
export function useCameraApproachVectors(
  options: UseCameraApproachVectorsOptions = {}
): UseCameraApproachVectorsReturn {
  const { cameraId, enabled = true, enablePolling = false } = options;

  const query = useQuery({
    queryKey: approachVectorsQueryKeys.camera(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchCameraApproachVectors(cameraId);
    },
    enabled: enabled && !!cameraId,
    staleTime: REALTIME_STALE_TIME,
    refetchInterval: enablePolling ? APPROACH_VECTORS_POLL_INTERVAL : false,
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
 * Get the color for an urgency level.
 *
 * @param urgency - Urgency level
 * @returns Tailwind color class
 */
export function getUrgencyColor(urgency: ApproachUrgency): string {
  switch (urgency) {
    case 'imminent':
      return '#EF4444'; // red-500
    case 'approaching':
      return '#F59E0B'; // amber-500
    case 'distant':
      return '#22C55E'; // green-500
    case 'not_approaching':
    default:
      return '#6B7280'; // gray-500
  }
}

/**
 * Get a human-readable label for urgency.
 *
 * @param urgency - Urgency level
 * @returns Human-readable string
 */
export function getUrgencyLabel(urgency: ApproachUrgency): string {
  switch (urgency) {
    case 'imminent':
      return 'Imminent';
    case 'approaching':
      return 'Approaching';
    case 'distant':
      return 'Distant';
    case 'not_approaching':
    default:
      return 'Not Approaching';
  }
}

/**
 * Format ETA as a human-readable countdown.
 *
 * @param seconds - ETA in seconds (or null)
 * @returns Formatted string like "3s" or "--"
 */
export function formatETA(seconds: number | null): string {
  if (seconds === null) return '--';
  if (seconds === 0) return 'Now';
  if (seconds < 1) return '<1s';
  return `${Math.round(seconds)}s`;
}

export default useCameraApproachVectors;
