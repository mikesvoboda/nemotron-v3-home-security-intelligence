/**
 * useZoneEntityDistribution - TanStack Query hooks for zone entity distribution (NEM-4937)
 *
 * This module provides hooks for fetching entity distribution data across zones:
 * - useZoneEntityDistribution: Fetch entity distribution for a single zone
 * - useAllZonesEntityDistribution: Fetch entity distribution across all zones
 *
 * @module hooks/useZoneEntityDistribution
 * @see NEM-4937 Zone Entity Distribution Visualization
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
 * Count of entities by type within a zone.
 */
export interface EntityTypeCount {
  /** Entity type (e.g., person, vehicle, car) */
  entity_type: string;
  /** Number of entities of this type */
  count: number;
  /** Percentage of total entities */
  percentage: number;
}

/**
 * Entity distribution for a single zone.
 */
export interface ZoneEntityDistribution {
  /** Zone ID */
  zone_id: number;
  /** Zone name for display */
  zone_name: string;
  /** Total number of entities in this zone */
  total_entities: number;
  /** Breakdown of entity types in this zone */
  entity_types: EntityTypeCount[];
}

/**
 * Response containing entity distribution across multiple zones.
 */
export interface ZoneEntityDistributionResponse {
  /** Entity distribution per zone */
  zones: ZoneEntityDistribution[];
  /** Total entities across all zones */
  grand_total: number;
  /** Start of the query time window (ISO format) */
  start_time: string;
  /** End of the query time window (ISO format) */
  end_time: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch entity distribution for a specific polygon zone.
 */
async function fetchZoneEntityDistribution(zoneId: number): Promise<ZoneEntityDistribution> {
  const response = await fetch(`${API_BASE}/polygon-zones/${zoneId}/entity-distribution`);
  if (!response.ok) {
    throw new Error(`Failed to fetch entity distribution: ${response.statusText}`);
  }
  return response.json() as Promise<ZoneEntityDistribution>;
}

/**
 * Fetch entity distribution across all polygon zones.
 */
async function fetchAllZonesEntityDistribution(
  cameraId?: string
): Promise<ZoneEntityDistributionResponse> {
  const params = new URLSearchParams();
  if (cameraId) {
    params.append('camera_id', cameraId);
  }
  const queryString = params.toString();
  const url = `${API_BASE}/entity-distribution${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch entity distribution: ${response.statusText}`);
  }
  return response.json() as Promise<ZoneEntityDistributionResponse>;
}

// ============================================================================
// Query Keys
// ============================================================================

export const zoneEntityDistributionQueryKeys = {
  all: ['zone-entity-distribution'] as const,
  zone: (zoneId: number) => [...zoneEntityDistributionQueryKeys.all, 'zone', zoneId] as const,
  allZones: (cameraId?: string) =>
    [...zoneEntityDistributionQueryKeys.all, 'all-zones', cameraId ?? 'all'] as const,
};

// ============================================================================
// Options Types
// ============================================================================

/**
 * Options for the useZoneEntityDistribution hook.
 */
export interface UseZoneEntityDistributionOptions {
  /** Zone ID to fetch entity distribution for */
  zoneId?: number;
  /** Whether the query is enabled */
  enabled?: boolean;
}

/**
 * Options for the useAllZonesEntityDistribution hook.
 */
export interface UseAllZonesEntityDistributionOptions {
  /** Optional camera ID filter */
  cameraId?: string;
  /** Whether the query is enabled */
  enabled?: boolean;
}

// ============================================================================
// Return Types
// ============================================================================

/**
 * Return type for the useZoneEntityDistribution hook.
 */
export interface UseZoneEntityDistributionReturn {
  /** Entity distribution data */
  distribution: ZoneEntityDistribution | undefined;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Refetch function */
  refetch: () => void;
}

/**
 * Return type for the useAllZonesEntityDistribution hook.
 */
export interface UseAllZonesEntityDistributionReturn {
  /** Entity distribution response */
  data: ZoneEntityDistributionResponse | undefined;
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
 * Hook to fetch entity distribution for a single zone.
 *
 * @param options - Configuration options
 * @returns Entity distribution data, loading state, and error
 *
 * @example
 * ```tsx
 * const { distribution, isLoading } = useZoneEntityDistribution({
 *   zoneId: 123,
 * });
 * ```
 */
export function useZoneEntityDistribution(
  options: UseZoneEntityDistributionOptions = {}
): UseZoneEntityDistributionReturn {
  const { zoneId, enabled = true } = options;

  const query = useQuery({
    queryKey: zoneEntityDistributionQueryKeys.zone(zoneId ?? 0),
    queryFn: () => {
      if (zoneId === undefined) {
        throw new Error('Zone ID is required');
      }
      return fetchZoneEntityDistribution(zoneId);
    },
    enabled: enabled && zoneId !== undefined,
    staleTime: DEFAULT_STALE_TIME,
  });

  return {
    distribution: query.data,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: () => void query.refetch(),
  };
}

/**
 * Hook to fetch entity distribution across all zones.
 *
 * @param options - Configuration options
 * @returns Entity distribution data for all zones, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useAllZonesEntityDistribution({
 *   cameraId: 'front_door', // optional
 * });
 * ```
 */
export function useAllZonesEntityDistribution(
  options: UseAllZonesEntityDistributionOptions = {}
): UseAllZonesEntityDistributionReturn {
  const { cameraId, enabled = true } = options;

  const query = useQuery({
    queryKey: zoneEntityDistributionQueryKeys.allZones(cameraId),
    queryFn: () => fetchAllZonesEntityDistribution(cameraId),
    enabled,
    staleTime: DEFAULT_STALE_TIME,
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
 * Get a color for an entity type.
 */
export function getEntityTypeColor(entityType: string): string {
  const colorMap: Record<string, string> = {
    person: '#3B82F6', // blue-500
    vehicle: '#10B981', // emerald-500
    car: '#10B981', // emerald-500
    truck: '#059669', // emerald-600
    motorcycle: '#0891B2', // cyan-600
    bicycle: '#06B6D4', // cyan-500
    dog: '#F59E0B', // amber-500
    cat: '#F97316', // orange-500
    bird: '#8B5CF6', // violet-500
    animal: '#D97706', // amber-600
  };

  return colorMap[entityType.toLowerCase()] ?? '#6B7280'; // gray-500 as fallback
}

/**
 * Get a human-readable label for an entity type.
 */
export function getEntityTypeLabel(entityType: string): string {
  const labelMap: Record<string, string> = {
    person: 'Person',
    vehicle: 'Vehicle',
    car: 'Car',
    truck: 'Truck',
    motorcycle: 'Motorcycle',
    bicycle: 'Bicycle',
    dog: 'Dog',
    cat: 'Cat',
    bird: 'Bird',
    animal: 'Animal',
  };

  return labelMap[entityType.toLowerCase()] ?? entityType.charAt(0).toUpperCase() + entityType.slice(1);
}

export default useZoneEntityDistribution;
