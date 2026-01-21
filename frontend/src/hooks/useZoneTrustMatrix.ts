/**
 * useZoneTrustMatrix - TanStack Query hooks for zone trust matrix data
 *
 * Provides hooks for fetching and aggregating trust levels between zones and
 * household members/vehicles. Supports the ZoneTrustMatrix component with
 * efficient data fetching and caching.
 *
 * Endpoints used:
 * - GET /api/zones/{zone_id}/household - Get household config for a zone
 * - GET /api/zones/{zone_id}/household/trust/{entity_type}/{entity_id} - Check trust level
 * - PUT /api/zones/{zone_id}/household - Create/update household config
 *
 * @module hooks/useZoneTrustMatrix
 * @see NEM-3192 ZoneTrustMatrix component implementation
 */

import { useQuery, useMutation, useQueryClient, useQueries } from '@tanstack/react-query';
import { useMemo, useCallback } from 'react';

import { useMembersQuery, useVehiclesQuery } from './useHouseholdApi';
import { STATIC_STALE_TIME, DEFAULT_STALE_TIME } from '../services/queryClient';

import type { HouseholdMember, RegisteredVehicle } from './useHouseholdApi';
import type { Zone, ZoneType } from '../types/generated';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Trust level result from zone access check.
 * Matches backend TrustLevelResult enum from zone_household.py
 */
export type TrustLevelResult = 'full' | 'partial' | 'monitor' | 'none';

/**
 * Entity type for trust checks.
 */
export type EntityType = 'member' | 'vehicle';

/**
 * Access schedule configuration for time-based access.
 */
export interface AccessSchedule {
  member_ids: number[];
  cron_expression: string;
  description?: string | null;
}

/**
 * Zone household configuration from the API.
 */
export interface ZoneHouseholdConfig {
  id: number;
  zone_id: string;
  owner_id: number | null;
  allowed_member_ids: number[];
  allowed_vehicle_ids: number[];
  access_schedules: AccessSchedule[];
  created_at: string;
  updated_at: string;
}

/**
 * Trust check response from the API.
 */
export interface TrustCheckResponse {
  zone_id: string;
  entity_id: number;
  entity_type: EntityType;
  trust_level: TrustLevelResult;
  reason: string;
}

/**
 * Cell data for a single zone-member combination in the trust matrix.
 */
export interface TrustMatrixCell {
  zoneId: string;
  zoneName: string;
  entityId: number;
  entityName: string;
  entityType: EntityType;
  trustLevel: TrustLevelResult;
  reason: string;
  accessSchedules: AccessSchedule[];
  isOwner: boolean;
}

/**
 * Aggregated matrix data for the ZoneTrustMatrix component.
 */
export interface TrustMatrixData {
  /** All zones in the matrix (rows) */
  zones: Zone[];
  /** All household members (columns when viewing members) */
  members: HouseholdMember[];
  /** All vehicles (columns when viewing vehicles) */
  vehicles: RegisteredVehicle[];
  /** Map of zone_id -> entity_id -> cell data */
  cells: Map<string, Map<number, TrustMatrixCell>>;
  /** Whether data is still loading */
  isLoading: boolean;
  /** Error if any occurred */
  error: Error | null;
}

/**
 * Request payload for updating zone household configuration.
 */
export interface ZoneHouseholdConfigUpdate {
  owner_id?: number | null;
  allowed_member_ids?: number[];
  allowed_vehicle_ids?: number[];
  access_schedules?: AccessSchedule[];
}

/**
 * Filter options for the trust matrix.
 */
export interface TrustMatrixFilters {
  /** Filter zones by type */
  zoneType?: ZoneType;
  /** Filter by specific member IDs */
  memberIds?: number[];
  /** Filter by specific vehicle IDs */
  vehicleIds?: number[];
  /** Filter by trust level */
  trustLevel?: TrustLevelResult;
}

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for zone trust matrix API.
 */
export const zoneTrustQueryKeys = {
  /** Base key for all zone trust queries */
  all: ['zoneTrust'] as const,
  /** Zone household config */
  config: (zoneId: string) => [...zoneTrustQueryKeys.all, 'config', zoneId] as const,
  /** Trust check for specific entity */
  trust: (zoneId: string, entityType: EntityType, entityId: number) =>
    [...zoneTrustQueryKeys.all, 'trust', zoneId, entityType, entityId] as const,
  /** Matrix data for a set of zones */
  matrix: (zoneIds: string[]) => [...zoneTrustQueryKeys.all, 'matrix', ...zoneIds] as const,
};

// ============================================================================
// API Functions
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

/**
 * Build headers for API requests.
 */
function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response and extract error message on failure.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorBody = (await response.json()) as { detail?: string };
      if (errorBody.detail) {
        errorMessage = errorBody.detail;
      }
    } catch {
      // Use default error message if JSON parsing fails
    }
    throw new Error(errorMessage);
  }
  // Handle 204 No Content responses
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

/**
 * Fetch zone household configuration.
 */
export async function fetchZoneHouseholdConfig(
  zoneId: string
): Promise<ZoneHouseholdConfig | null> {
  const response = await fetch(`${BASE_URL}/api/zones/${zoneId}/household`, {
    method: 'GET',
    headers: buildHeaders(),
  });

  if (response.status === 404) {
    return null;
  }

  return handleResponse<ZoneHouseholdConfig | null>(response);
}

/**
 * Check entity trust level in a zone.
 */
export async function checkEntityTrust(
  zoneId: string,
  entityType: EntityType,
  entityId: number,
  atTime?: Date
): Promise<TrustCheckResponse> {
  let url = `${BASE_URL}/api/zones/${zoneId}/household/trust/${entityType}/${entityId}`;
  if (atTime) {
    url += `?at_time=${atTime.toISOString()}`;
  }

  const response = await fetch(url, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<TrustCheckResponse>(response);
}

/**
 * Update zone household configuration (upsert).
 */
export async function upsertZoneHouseholdConfig(
  zoneId: string,
  config: ZoneHouseholdConfigUpdate
): Promise<ZoneHouseholdConfig> {
  const response = await fetch(`${BASE_URL}/api/zones/${zoneId}/household`, {
    method: 'PUT',
    headers: buildHeaders(),
    body: JSON.stringify(config),
  });
  return handleResponse<ZoneHouseholdConfig>(response);
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to fetch household configuration for a zone.
 */
export function useZoneHouseholdConfigQuery(zoneId: string | undefined) {
  return useQuery({
    queryKey: zoneTrustQueryKeys.config(zoneId ?? ''),
    queryFn: () => {
      if (!zoneId) {
        throw new Error('Zone ID is required');
      }
      return fetchZoneHouseholdConfig(zoneId);
    },
    enabled: !!zoneId,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });
}

/**
 * Hook to check trust level for an entity in a zone.
 */
export function useTrustCheckQuery(
  zoneId: string | undefined,
  entityType: EntityType | undefined,
  entityId: number | undefined,
  options: { enabled?: boolean; atTime?: Date } = {}
) {
  const { enabled = true, atTime } = options;

  return useQuery({
    queryKey: zoneTrustQueryKeys.trust(zoneId ?? '', entityType ?? 'member', entityId ?? 0),
    queryFn: () => {
      if (!zoneId || !entityType || entityId === undefined) {
        throw new Error('Zone ID, entity type, and entity ID are required');
      }
      return checkEntityTrust(zoneId, entityType, entityId, atTime);
    },
    enabled: enabled && !!zoneId && !!entityType && entityId !== undefined,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });
}

/**
 * Hook to update zone household configuration.
 */
export function useUpdateZoneHouseholdConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ zoneId, config }: { zoneId: string; config: ZoneHouseholdConfigUpdate }) =>
      upsertZoneHouseholdConfig(zoneId, config),
    onSuccess: (_data, { zoneId }) => {
      // Invalidate the zone config cache
      void queryClient.invalidateQueries({
        queryKey: zoneTrustQueryKeys.config(zoneId),
      });
      // Invalidate all trust queries for this zone
      void queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) &&
          query.queryKey[0] === 'zoneTrust' &&
          query.queryKey[1] === 'trust' &&
          query.queryKey[2] === zoneId,
      });
    },
  });
}

/**
 * Hook to compute the trust level from zone config for a member.
 * This is a client-side computation to avoid excessive API calls.
 */
function computeTrustLevelForMember(
  config: ZoneHouseholdConfig | null | undefined,
  memberId: number
): { trustLevel: TrustLevelResult; reason: string; isOwner: boolean } {
  if (!config) {
    return { trustLevel: 'none', reason: 'No household configuration', isOwner: false };
  }

  // Check if member is owner
  if (config.owner_id === memberId) {
    return { trustLevel: 'full', reason: 'Zone owner', isOwner: true };
  }

  // Check if member is in allowed list
  if (config.allowed_member_ids.includes(memberId)) {
    return { trustLevel: 'partial', reason: 'Allowed member', isOwner: false };
  }

  // Check if member is in any access schedule
  const hasSchedule = config.access_schedules.some((schedule) =>
    schedule.member_ids.includes(memberId)
  );
  if (hasSchedule) {
    return { trustLevel: 'monitor', reason: 'Scheduled access', isOwner: false };
  }

  return { trustLevel: 'none', reason: 'No trust configured', isOwner: false };
}

/**
 * Hook to compute the trust level from zone config for a vehicle.
 */
function computeTrustLevelForVehicle(
  config: ZoneHouseholdConfig | null | undefined,
  vehicleId: number
): { trustLevel: TrustLevelResult; reason: string } {
  if (!config) {
    return { trustLevel: 'none', reason: 'No household configuration' };
  }

  // Check if vehicle is in allowed list
  if (config.allowed_vehicle_ids.includes(vehicleId)) {
    return { trustLevel: 'partial', reason: 'Allowed vehicle' };
  }

  return { trustLevel: 'none', reason: 'No trust configured' };
}

/**
 * Main hook for the ZoneTrustMatrix component.
 *
 * Aggregates data from zones, household members, vehicles, and zone configs
 * to build a complete trust matrix.
 */
export function useZoneTrustMatrix(
  zones: Zone[],
  filters?: TrustMatrixFilters
): TrustMatrixData {
  // Fetch household members and vehicles
  const membersQuery = useMembersQuery();
  const vehiclesQuery = useVehiclesQuery();

  // Filter zones if zone type filter is applied
  const filteredZones = useMemo(() => {
    if (!filters?.zoneType) return zones;
    return zones.filter((z) => z.zone_type === filters.zoneType);
  }, [zones, filters?.zoneType]);

  // Get zone IDs for fetching configs
  const zoneIds = useMemo(() => filteredZones.map((z) => z.id), [filteredZones]);

  // Fetch zone household configs for all zones using useQueries
  const configQueries = useQueries({
    queries: zoneIds.map((zoneId) => ({
      queryKey: zoneTrustQueryKeys.config(zoneId),
      queryFn: () => fetchZoneHouseholdConfig(zoneId),
      staleTime: STATIC_STALE_TIME,
      retry: 1,
    })),
  });

  // Check if any config query is loading
  const isConfigsLoading = configQueries.some((q) => q.isLoading);
  const configsError = configQueries.find((q) => q.error)?.error as Error | null;

  // Build config map: zoneId -> config
  const configMap = useMemo(() => {
    const map = new Map<string, ZoneHouseholdConfig | null>();
    zoneIds.forEach((zoneId, index) => {
      const result = configQueries[index];
      if (result.data !== undefined) {
        map.set(zoneId, result.data);
      }
    });
    return map;
  }, [zoneIds, configQueries]);

  // Filter members if member IDs filter is applied
  const filteredMembers = useMemo(() => {
    const members = membersQuery.data ?? [];
    if (!filters?.memberIds?.length) return members;
    return members.filter((m) => filters.memberIds?.includes(m.id));
  }, [membersQuery.data, filters?.memberIds]);

  // Filter vehicles if vehicle IDs filter is applied
  const filteredVehicles = useMemo(() => {
    const vehicles = vehiclesQuery.data ?? [];
    if (!filters?.vehicleIds?.length) return vehicles;
    return vehicles.filter((v) => filters.vehicleIds?.includes(v.id));
  }, [vehiclesQuery.data, filters?.vehicleIds]);

  // Build the trust matrix cells
  const cells = useMemo(() => {
    const cellsMap = new Map<string, Map<number, TrustMatrixCell>>();

    // Process each zone
    for (const zone of filteredZones) {
      const config = configMap.get(zone.id);
      const entityMap = new Map<number, TrustMatrixCell>();

      // Add member cells
      for (const member of filteredMembers) {
        const { trustLevel, reason, isOwner } = computeTrustLevelForMember(config, member.id);

        // Apply trust level filter if specified
        if (filters?.trustLevel && trustLevel !== filters.trustLevel) {
          continue;
        }

        // Find access schedules for this member
        const accessSchedules = config?.access_schedules.filter((s) =>
          s.member_ids.includes(member.id)
        ) ?? [];

        entityMap.set(member.id, {
          zoneId: zone.id,
          zoneName: zone.name,
          entityId: member.id,
          entityName: member.name,
          entityType: 'member',
          trustLevel,
          reason,
          accessSchedules,
          isOwner,
        });
      }

      // Add vehicle cells (with negative IDs to distinguish from members)
      for (const vehicle of filteredVehicles) {
        const { trustLevel, reason } = computeTrustLevelForVehicle(config, vehicle.id);

        // Apply trust level filter if specified
        if (filters?.trustLevel && trustLevel !== filters.trustLevel) {
          continue;
        }

        // Use negative ID for vehicles to distinguish from members in the map
        const vehicleKey = -vehicle.id;
        entityMap.set(vehicleKey, {
          zoneId: zone.id,
          zoneName: zone.name,
          entityId: vehicle.id,
          entityName: vehicle.description,
          entityType: 'vehicle',
          trustLevel,
          reason,
          accessSchedules: [],
          isOwner: false,
        });
      }

      cellsMap.set(zone.id, entityMap);
    }

    return cellsMap;
  }, [filteredZones, filteredMembers, filteredVehicles, configMap, filters?.trustLevel]);

  // Combine loading and error states
  const isLoading = membersQuery.isLoading || vehiclesQuery.isLoading || isConfigsLoading;
  const error = membersQuery.error ?? vehiclesQuery.error ?? configsError;

  return {
    zones: filteredZones,
    members: filteredMembers,
    vehicles: filteredVehicles,
    cells,
    isLoading,
    error,
  };
}

/**
 * Hook to update trust level for a member in a zone.
 * Handles the logic of adding/removing from owner, allowed list, or schedules.
 */
export function useUpdateMemberTrust() {
  const updateConfig = useUpdateZoneHouseholdConfig();

  const updateMemberTrust = useCallback(
    async (
      zoneId: string,
      memberId: number,
      newTrustLevel: TrustLevelResult,
      currentConfig: ZoneHouseholdConfig | null
    ) => {
      const config: ZoneHouseholdConfigUpdate = {
        owner_id: currentConfig?.owner_id ?? null,
        allowed_member_ids: [...(currentConfig?.allowed_member_ids ?? [])],
        allowed_vehicle_ids: currentConfig?.allowed_vehicle_ids ?? [],
        access_schedules: currentConfig?.access_schedules ?? [],
      };

      // Remove member from all lists first
      if (config.owner_id === memberId) {
        config.owner_id = null;
      }
      config.allowed_member_ids = config.allowed_member_ids?.filter((id) => id !== memberId) ?? [];
      config.access_schedules = config.access_schedules?.map((schedule) => ({
        ...schedule,
        member_ids: schedule.member_ids.filter((id) => id !== memberId),
      })).filter((schedule) => schedule.member_ids.length > 0) ?? [];

      // Add member to appropriate list based on new trust level
      switch (newTrustLevel) {
        case 'full':
          config.owner_id = memberId;
          break;
        case 'partial':
          config.allowed_member_ids = [...(config.allowed_member_ids ?? []), memberId];
          break;
        case 'monitor':
          // Add a default schedule for the member (24/7 access for now)
          config.access_schedules = [
            ...(config.access_schedules ?? []),
            {
              member_ids: [memberId],
              cron_expression: '* * * * *', // All times
              description: 'Monitor access',
            },
          ];
          break;
        case 'none':
          // Already removed from all lists
          break;
      }

      return updateConfig.mutateAsync({ zoneId, config });
    },
    [updateConfig]
  );

  return {
    updateMemberTrust,
    isLoading: updateConfig.isPending,
    error: updateConfig.error,
  };
}

/**
 * Hook to update trust level for a vehicle in a zone.
 */
export function useUpdateVehicleTrust() {
  const updateConfig = useUpdateZoneHouseholdConfig();

  const updateVehicleTrust = useCallback(
    async (
      zoneId: string,
      vehicleId: number,
      newTrustLevel: TrustLevelResult,
      currentConfig: ZoneHouseholdConfig | null
    ) => {
      const config: ZoneHouseholdConfigUpdate = {
        owner_id: currentConfig?.owner_id ?? null,
        allowed_member_ids: currentConfig?.allowed_member_ids ?? [],
        allowed_vehicle_ids: [...(currentConfig?.allowed_vehicle_ids ?? [])],
        access_schedules: currentConfig?.access_schedules ?? [],
      };

      // Remove vehicle from allowed list first
      config.allowed_vehicle_ids = config.allowed_vehicle_ids?.filter((id) => id !== vehicleId) ?? [];

      // Add vehicle to allowed list if trust level is partial
      // Note: Vehicles only support partial or none trust levels
      if (newTrustLevel === 'partial' || newTrustLevel === 'full') {
        config.allowed_vehicle_ids = [...(config.allowed_vehicle_ids ?? []), vehicleId];
      }

      return updateConfig.mutateAsync({ zoneId, config });
    },
    [updateConfig]
  );

  return {
    updateVehicleTrust,
    isLoading: updateConfig.isPending,
    error: updateConfig.error,
  };
}

export default useZoneTrustMatrix;
