/**
 * useZones - TanStack Query hooks for zone data management
 *
 * This module provides hooks for fetching and mutating zone data using
 * TanStack Query. Zones define regions of interest within camera feeds
 * for detection filtering and alert configuration.
 *
 * Features:
 * - useZonesQuery: Fetch all zones for a camera
 * - useZoneQuery: Fetch a single zone by ID
 * - useZoneMutation: Create, update, and delete zones with optimistic updates
 *
 * @module hooks/useZones
 * @see NEM-2552 Zone CRUD hooks implementation
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchZones,
  fetchZone,
  createZone,
  updateZone,
  deleteZone,
  type Zone,
  type ZoneCreate,
  type ZoneUpdate,
  type ZoneListResponse,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// useZonesQuery - Fetch all zones for a camera
// ============================================================================

/**
 * Options for configuring the useZonesQuery hook
 */
export interface UseZonesQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Filter zones by enabled status.
   * If undefined, returns all zones.
   */
  enabledFilter?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useZonesQuery hook
 */
export interface UseZonesQueryReturn {
  /** List of zones, empty array if not yet fetched */
  zones: Zone[];
  /** Total count of zones */
  total: number;
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
 * Hook to fetch all zones for a camera using TanStack Query.
 *
 * @param cameraId - Camera ID to fetch zones for, or undefined to disable
 * @param options - Configuration options
 * @returns Zone list and query state
 *
 * @example
 * ```tsx
 * const { zones, isLoading, error } = useZonesQuery('cam-123');
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <ul>
 *     {zones.map(zone => <li key={zone.id}>{zone.name}</li>)}
 *   </ul>
 * );
 * ```
 */
export function useZonesQuery(
  cameraId: string | undefined,
  options: UseZonesQueryOptions = {}
): UseZonesQueryReturn {
  const { enabled = true, enabledFilter, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.cameras.zones(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchZones(cameraId, enabledFilter);
    },
    enabled: enabled && !!cameraId,
    staleTime,
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const zones = useMemo(() => query.data?.items ?? [], [query.data]);
  const total = useMemo(() => query.data?.pagination?.total ?? 0, [query.data]);

  return {
    zones,
    total,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useZoneQuery - Fetch single zone by ID
// ============================================================================

/**
 * Options for configuring the useZoneQuery hook
 */
export interface UseZoneQueryOptions {
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
}

/**
 * Return type for the useZoneQuery hook
 */
export interface UseZoneQueryReturn {
  /** Zone data, undefined if not yet fetched */
  data: Zone | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single zone by ID using TanStack Query.
 *
 * @param cameraId - Camera ID the zone belongs to
 * @param zoneId - Zone ID to fetch, or undefined to disable
 * @param options - Configuration options
 * @returns Zone data and query state
 *
 * @example
 * ```tsx
 * const { data: zone, isLoading, error } = useZoneQuery('cam-123', 'zone-456');
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 * if (!zone) return null;
 *
 * return <ZoneDetails zone={zone} />;
 * ```
 */
export function useZoneQuery(
  cameraId: string | undefined,
  zoneId: string | undefined,
  options: UseZoneQueryOptions = {}
): UseZoneQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: [...queryKeys.cameras.zones(cameraId ?? ''), 'detail', zoneId ?? ''],
    queryFn: () => {
      if (!cameraId || !zoneId) {
        throw new Error('Camera ID and Zone ID are required');
      }
      return fetchZone(cameraId, zoneId);
    },
    enabled: enabled && !!cameraId && !!zoneId,
    staleTime,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useZoneMutation - Create, update, delete zones
// ============================================================================

/**
 * Context type for zone mutations (used for optimistic updates)
 */
interface ZoneMutationContext {
  previousData: ZoneListResponse | undefined;
  optimisticId?: string;
}

/**
 * Return type for the useZoneMutation hook
 */
export interface UseZoneMutationReturn {
  /** Mutation for creating a new zone */
  createMutation: ReturnType<
    typeof useMutation<Zone, Error, { cameraId: string; data: ZoneCreate }, ZoneMutationContext>
  >;
  /** Mutation for updating an existing zone */
  updateMutation: ReturnType<
    typeof useMutation<
      Zone,
      Error,
      { cameraId: string; zoneId: string; data: ZoneUpdate },
      ZoneMutationContext
    >
  >;
  /** Mutation for deleting a zone */
  deleteMutation: ReturnType<
    typeof useMutation<void, Error, { cameraId: string; zoneId: string }, ZoneMutationContext>
  >;
}

/**
 * Hook providing mutations for zone CRUD operations.
 *
 * All mutations implement optimistic updates for immediate UI feedback,
 * with automatic rollback on failure. The cache is automatically invalidated
 * on success to ensure the UI stays in sync with the server.
 *
 * @returns Object containing create, update, and delete mutations
 *
 * @example
 * ```tsx
 * const { createMutation, updateMutation, deleteMutation } = useZoneMutation();
 *
 * // Create a new zone
 * await createMutation.mutateAsync({
 *   cameraId: 'cam-123',
 *   data: { name: 'Entry Zone', zone_type: 'entry_point', coordinates: [...] }
 * });
 *
 * // Update a zone
 * await updateMutation.mutateAsync({
 *   cameraId: 'cam-123',
 *   zoneId: 'zone-456',
 *   data: { name: 'Updated Name' }
 * });
 *
 * // Delete a zone
 * await deleteMutation.mutateAsync({ cameraId: 'cam-123', zoneId: 'zone-456' });
 * ```
 */
export function useZoneMutation(): UseZoneMutationReturn {
  const queryClient = useQueryClient();

  const createMutation = useMutation<
    Zone,
    Error,
    { cameraId: string; data: ZoneCreate },
    ZoneMutationContext
  >({
    mutationFn: ({ cameraId, data }) => createZone(cameraId, data),

    // Optimistic update: add the new zone immediately
    onMutate: async ({ cameraId, data }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.zones(cameraId) });

      // Snapshot the previous value for rollback
      const previousData = queryClient.getQueryData<ZoneListResponse>(
        queryKeys.cameras.zones(cameraId)
      );

      // Create a temporary zone with a placeholder ID
      const optimisticZone: Zone = {
        id: `temp-${Date.now()}`,
        camera_id: cameraId,
        name: data.name,
        zone_type: data.zone_type,
        coordinates: data.coordinates,
        shape: data.shape ?? 'polygon',
        color: data.color ?? '#3B82F6',
        enabled: data.enabled ?? true,
        priority: data.priority ?? 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // Optimistically add the zone to the cache
      queryClient.setQueryData<ZoneListResponse>(queryKeys.cameras.zones(cameraId), (old) => ({
        items: [...(old?.items ?? []), optimisticZone],
        pagination: {
          total: (old?.pagination?.total ?? 0) + 1,
          limit: old?.pagination?.limit ?? 50,
          has_more: old?.pagination?.has_more ?? false,
        },
      }));

      // Return context with snapshot for rollback
      return { previousData, optimisticId: optimisticZone.id };
    },

    // On error, rollback to the previous value
    onError: (_err, { cameraId }, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(queryKeys.cameras.zones(cameraId), context.previousData);
      }
    },

    // Replace the optimistic zone with the real one on success
    onSuccess: (newZone, { cameraId }, context) => {
      queryClient.setQueryData<ZoneListResponse>(queryKeys.cameras.zones(cameraId), (old) => ({
        items:
          old?.items?.map((zone) => (zone.id === context?.optimisticId ? newZone : zone)) ?? [],
        pagination: old?.pagination ?? { total: 1, limit: 50, has_more: false },
      }));
    },

    // Always refetch after error or success for data consistency
    onSettled: (_data, _error, { cameraId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.zones(cameraId) });
    },
  });

  const updateMutation = useMutation<
    Zone,
    Error,
    { cameraId: string; zoneId: string; data: ZoneUpdate },
    ZoneMutationContext
  >({
    mutationFn: ({ cameraId, zoneId, data }) => updateZone(cameraId, zoneId, data),

    // Optimistic update: immediately update the cache
    onMutate: async ({ cameraId, zoneId, data }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.zones(cameraId) });

      // Snapshot the previous value for rollback
      const previousData = queryClient.getQueryData<ZoneListResponse>(
        queryKeys.cameras.zones(cameraId)
      );

      // Optimistically update the zone in the cache
      queryClient.setQueryData<ZoneListResponse>(queryKeys.cameras.zones(cameraId), (old) => ({
        items:
          old?.items?.map((zone) => {
            if (zone.id !== zoneId) return zone;
            // Create a typed update object with only non-null values
            const updates: Partial<Zone> = {
              updated_at: new Date().toISOString(),
            };
            if (data.name !== undefined && data.name !== null) updates.name = data.name;
            if (data.zone_type !== undefined && data.zone_type !== null)
              updates.zone_type = data.zone_type;
            if (data.coordinates !== undefined && data.coordinates !== null)
              updates.coordinates = data.coordinates;
            if (data.shape !== undefined && data.shape !== null) updates.shape = data.shape;
            if (data.color !== undefined && data.color !== null) updates.color = data.color;
            if (data.enabled !== undefined && data.enabled !== null)
              updates.enabled = data.enabled;
            if (data.priority !== undefined && data.priority !== null)
              updates.priority = data.priority;
            return { ...zone, ...updates };
          }) ?? [],
        pagination: old?.pagination ?? { total: 0, limit: 50, has_more: false },
      }));

      // Return context with snapshot for rollback
      return { previousData };
    },

    // On error, rollback to the previous value
    onError: (_err, { cameraId }, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(queryKeys.cameras.zones(cameraId), context.previousData);
      }
    },

    // Always refetch after error or success for data consistency
    onSettled: (_data, _error, { cameraId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.zones(cameraId) });
    },
  });

  const deleteMutation = useMutation<
    void,
    Error,
    { cameraId: string; zoneId: string },
    ZoneMutationContext
  >({
    mutationFn: ({ cameraId, zoneId }) => deleteZone(cameraId, zoneId),

    // Optimistic update: immediately remove the zone
    onMutate: async ({ cameraId, zoneId }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.zones(cameraId) });

      // Snapshot the previous value for rollback
      const previousData = queryClient.getQueryData<ZoneListResponse>(
        queryKeys.cameras.zones(cameraId)
      );

      // Optimistically remove the zone from the cache
      queryClient.setQueryData<ZoneListResponse>(queryKeys.cameras.zones(cameraId), (old) => ({
        items: old?.items?.filter((zone) => zone.id !== zoneId) ?? [],
        pagination: {
          total: Math.max((old?.pagination?.total ?? 1) - 1, 0),
          limit: old?.pagination?.limit ?? 50,
          has_more: old?.pagination?.has_more ?? false,
        },
      }));

      // Return context with snapshot for rollback
      return { previousData };
    },

    // On error, rollback to the previous value
    onError: (_err, { cameraId }, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(queryKeys.cameras.zones(cameraId), context.previousData);
      }
    },

    // Always refetch after error or success for data consistency
    onSettled: (_data, _error, { cameraId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.zones(cameraId) });
    },
  });

  return {
    createMutation,
    updateMutation,
    deleteMutation,
  };
}
