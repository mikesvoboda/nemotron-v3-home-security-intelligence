/**
 * useZoneHouseholdConfig - TanStack Query hooks for zone-household configuration API
 *
 * Provides hooks for managing zone-household linkage including:
 * - Fetching zone household configuration (owner, allowed members, vehicles, schedules)
 * - Creating/updating zone household configuration
 * - Deleting zone household configuration
 * - Checking entity trust levels in zones
 *
 * Zone-Household API Endpoints:
 * - GET /api/zones/{zone_id}/household - Get household config for a zone
 * - PUT /api/zones/{zone_id}/household - Create/update household config
 * - PATCH /api/zones/{zone_id}/household - Partial update household config
 * - DELETE /api/zones/{zone_id}/household - Remove household config
 * - GET /api/zones/{zone_id}/household/trust/{entity_type}/{entity_id} - Check trust level
 *
 * Phase 2.2: Create ZoneOwnershipPanel component (NEM-3191)
 * Part of the Zone Intelligence System epic (NEM-3186).
 *
 * @module hooks/useZoneHouseholdConfig
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { STATIC_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Type Definitions (matching backend schemas)
// ============================================================================

/**
 * Trust level result from zone access check.
 */
export type TrustLevelResult = 'full' | 'partial' | 'monitor' | 'none';

/**
 * Entity type for trust checks.
 */
export type EntityType = 'member' | 'vehicle';

/**
 * Access schedule for time-based zone access.
 */
export interface AccessSchedule {
  /** List of household member IDs this schedule applies to */
  member_ids: number[];
  /** Cron expression defining when access is granted */
  cron_expression: string;
  /** Optional human-readable description */
  description?: string | null;
}

/**
 * Zone household configuration response from the API.
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
 * Request payload for creating zone household configuration.
 */
export interface ZoneHouseholdConfigCreate {
  owner_id?: number | null;
  allowed_member_ids?: number[];
  allowed_vehicle_ids?: number[];
  access_schedules?: AccessSchedule[];
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
 * Trust check response from the API.
 */
export interface TrustCheckResponse {
  zone_id: string;
  entity_id: number;
  entity_type: EntityType;
  trust_level: TrustLevelResult;
  reason: string;
}

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for zone household config API.
 */
export const zoneHouseholdQueryKeys = {
  /** Base key for all zone household queries */
  all: ['zone-household'] as const,
  /** Zone household config for a specific zone */
  config: (zoneId: string) => [...zoneHouseholdQueryKeys.all, 'config', zoneId] as const,
  /** Trust check for an entity in a zone */
  trust: (zoneId: string, entityType: EntityType, entityId: number) =>
    [...zoneHouseholdQueryKeys.all, 'trust', zoneId, entityType, entityId] as const,
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

  // Handle 404 or null response gracefully
  if (response.status === 404) {
    return null;
  }

  const result = await handleResponse<ZoneHouseholdConfig | null>(response);
  return result;
}

/**
 * Create or update zone household configuration (PUT - upsert).
 */
export async function upsertZoneHouseholdConfig(
  zoneId: string,
  data: ZoneHouseholdConfigCreate
): Promise<ZoneHouseholdConfig> {
  const response = await fetch(`${BASE_URL}/api/zones/${zoneId}/household`, {
    method: 'PUT',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<ZoneHouseholdConfig>(response);
}

/**
 * Partially update zone household configuration (PATCH).
 */
export async function patchZoneHouseholdConfig(
  zoneId: string,
  data: ZoneHouseholdConfigUpdate
): Promise<ZoneHouseholdConfig> {
  const response = await fetch(`${BASE_URL}/api/zones/${zoneId}/household`, {
    method: 'PATCH',
    headers: buildHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<ZoneHouseholdConfig>(response);
}

/**
 * Delete zone household configuration.
 */
export async function deleteZoneHouseholdConfig(zoneId: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/zones/${zoneId}/household`, {
    method: 'DELETE',
    headers: buildHeaders(),
  });
  return handleResponse<void>(response);
}

/**
 * Check entity trust level in a zone.
 */
export async function checkEntityTrust(
  zoneId: string,
  entityType: EntityType,
  entityId: number,
  atTime?: string
): Promise<TrustCheckResponse> {
  const url = new URL(
    `${BASE_URL}/api/zones/${zoneId}/household/trust/${entityType}/${entityId}`,
    window.location.origin
  );
  if (atTime) {
    url.searchParams.set('at_time', atTime);
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<TrustCheckResponse>(response);
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to fetch zone household configuration.
 *
 * @param zoneId - Zone ID to fetch config for
 * @param options - Optional query options
 * @returns Query result with zone household config
 */
export function useZoneHouseholdConfigQuery(zoneId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: zoneHouseholdQueryKeys.config(zoneId),
    queryFn: () => fetchZoneHouseholdConfig(zoneId),
    staleTime: STATIC_STALE_TIME,
    retry: 1,
    enabled: options?.enabled !== false && Boolean(zoneId),
  });
}

/**
 * Hook to create or update zone household configuration.
 *
 * @returns Mutation for upserting zone household config
 */
export function useUpsertZoneHouseholdConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ zoneId, data }: { zoneId: string; data: ZoneHouseholdConfigCreate }) =>
      upsertZoneHouseholdConfig(zoneId, data),
    onSuccess: (result) => {
      // Update the cache with the new config
      void queryClient.setQueryData(zoneHouseholdQueryKeys.config(result.zone_id), result);
      // Invalidate to ensure freshness
      void queryClient.invalidateQueries({
        queryKey: zoneHouseholdQueryKeys.config(result.zone_id),
      });
    },
  });
}

/**
 * Hook to partially update zone household configuration.
 *
 * @returns Mutation for patching zone household config
 */
export function usePatchZoneHouseholdConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ zoneId, data }: { zoneId: string; data: ZoneHouseholdConfigUpdate }) =>
      patchZoneHouseholdConfig(zoneId, data),
    onSuccess: (result) => {
      void queryClient.setQueryData(zoneHouseholdQueryKeys.config(result.zone_id), result);
      void queryClient.invalidateQueries({
        queryKey: zoneHouseholdQueryKeys.config(result.zone_id),
      });
    },
  });
}

/**
 * Hook to delete zone household configuration.
 *
 * @returns Mutation for deleting zone household config
 */
export function useDeleteZoneHouseholdConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (zoneId: string) => deleteZoneHouseholdConfig(zoneId),
    onSuccess: (_, zoneId) => {
      // Clear the cache
      void queryClient.setQueryData(zoneHouseholdQueryKeys.config(zoneId), null);
      void queryClient.invalidateQueries({
        queryKey: zoneHouseholdQueryKeys.config(zoneId),
      });
    },
  });
}

/**
 * Hook to check entity trust level in a zone.
 *
 * @param zoneId - Zone ID
 * @param entityType - Entity type (member or vehicle)
 * @param entityId - Entity ID
 * @param options - Optional query options including atTime
 * @returns Query result with trust check response
 */
export function useEntityTrustQuery(
  zoneId: string,
  entityType: EntityType,
  entityId: number,
  options?: { enabled?: boolean; atTime?: string }
) {
  return useQuery({
    queryKey: zoneHouseholdQueryKeys.trust(zoneId, entityType, entityId),
    queryFn: () => checkEntityTrust(zoneId, entityType, entityId, options?.atTime),
    staleTime: STATIC_STALE_TIME,
    retry: 1,
    enabled: options?.enabled !== false && Boolean(zoneId) && Boolean(entityId),
  });
}

/**
 * Combined hook for zone household configuration.
 *
 * Provides the config query and all mutation functions for a specific zone.
 *
 * @param zoneId - Zone ID to manage config for
 * @returns Object with config data and mutation functions
 */
export function useZoneHouseholdConfig(zoneId: string) {
  const configQuery = useZoneHouseholdConfigQuery(zoneId);
  const upsertMutation = useUpsertZoneHouseholdConfig();
  const patchMutation = usePatchZoneHouseholdConfig();
  const deleteMutation = useDeleteZoneHouseholdConfig();

  return {
    // Query state
    config: configQuery.data ?? null,
    isLoading: configQuery.isLoading,
    isError: configQuery.isError,
    error: configQuery.error,
    refetch: configQuery.refetch,

    // Mutations
    upsertConfig: upsertMutation,
    patchConfig: patchMutation,
    deleteConfig: deleteMutation,

    // Convenience methods
    setOwner: (ownerId: number | null) =>
      patchMutation.mutateAsync({ zoneId, data: { owner_id: ownerId } }),
    setAllowedMembers: (memberIds: number[]) =>
      patchMutation.mutateAsync({ zoneId, data: { allowed_member_ids: memberIds } }),
    setAllowedVehicles: (vehicleIds: number[]) =>
      patchMutation.mutateAsync({ zoneId, data: { allowed_vehicle_ids: vehicleIds } }),
    setAccessSchedules: (schedules: AccessSchedule[]) =>
      patchMutation.mutateAsync({ zoneId, data: { access_schedules: schedules } }),
    clearConfig: () => deleteMutation.mutateAsync(zoneId),
  };
}

export default useZoneHouseholdConfig;
