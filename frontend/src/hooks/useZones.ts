/**
 * useZones - TanStack Query hooks for zone CRUD operations
 *
 * This module provides hooks for fetching and mutating zone data using
 * TanStack Query. It includes:
 * - useZonesQuery: Fetch all zones for a camera
 * - useZoneQuery: Fetch a single zone by ID
 * - useZoneMutation: Create, update, and delete zones
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Optimistic updates support
 * - Background refetching
 * - Coordinate updates for redrawing zone boundaries
 *
 * @module hooks/useZones
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
   * Filter by zone enabled status.
   * When undefined, returns all zones.
   */
  enabledFilter?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;

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
  /** Whether more items are available */
  hasMore: boolean;
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
 * @param cameraId - Camera ID to fetch zones for
 * @param options - Configuration options
 * @returns Zone list and query state
 *
 * @example
 * ```tsx
 * const { zones, isLoading, error } = useZonesQuery('camera-1');
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
  const {
    enabled = true,
    enabledFilter,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  const query = useQuery({
    queryKey: queryKeys.cameras.zones(cameraId ?? ''),
    queryFn: () => {
      if (!cameraId) {
        throw new Error('Camera ID is required');
      }
      return fetchZones(cameraId, enabledFilter);
    },
    enabled: enabled && !!cameraId,
    refetchInterval,
    staleTime,
    // Reduced retry for faster failure feedback
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const zones = useMemo(() => query.data?.items ?? [], [query.data]);
  const total = useMemo(() => query.data?.pagination?.total ?? 0, [query.data]);
  const hasMore = useMemo(() => query.data?.pagination?.has_more ?? false, [query.data]);

  return {
    zones,
    total,
    hasMore,
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
 * @param zoneId - Zone ID to fetch, or undefined to disable the query
 * @param options - Configuration options
 * @returns Zone data and query state
 *
 * @example
 * ```tsx
 * const { data: zone, isLoading, error } = useZoneQuery('camera-1', 'zone-1');
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
 * Return type for the useZoneMutation hook
 */
export interface UseZoneMutationReturn {
  /** Mutation for creating a new zone */
  createMutation: ReturnType<typeof useMutation<Zone, Error, { cameraId: string; data: ZoneCreate }>>;
  /** Mutation for updating an existing zone (supports coordinates for redraw) */
  updateMutation: ReturnType<
    typeof useMutation<Zone, Error, { cameraId: string; zoneId: string; data: ZoneUpdate }>
  >;
  /** Mutation for deleting a zone */
  deleteMutation: ReturnType<typeof useMutation<void, Error, { cameraId: string; zoneId: string }>>;
}

/**
 * Hook providing mutations for zone CRUD operations.
 *
 * All mutations implement optimistic updates for immediate UI feedback,
 * with automatic rollback on failure. The cache is automatically invalidated
 * on success to ensure the UI stays in sync with the server.
 *
 * The update mutation supports coordinate updates for redrawing zone boundaries.
 *
 * @returns Object containing create, update, and delete mutations
 *
 * @example
 * ```tsx
 * const { createMutation, updateMutation, deleteMutation } = useZoneMutation();
 *
 * // Create a new zone
 * await createMutation.mutateAsync({
 *   cameraId: 'camera-1',
 *   data: { name: 'New Zone', zone_type: 'entry_point', coordinates: [...] }
 * });
 *
 * // Update a zone (including coordinates for redraw)
 * await updateMutation.mutateAsync({
 *   cameraId: 'camera-1',
 *   zoneId: 'zone-1',
 *   data: { name: 'Updated', coordinates: [...] }  // coordinates for redraw
 * });
 *
 * // Delete a zone
 * await deleteMutation.mutateAsync({ cameraId: 'camera-1', zoneId: 'zone-1' });
 * ```
 */
export function useZoneMutation(): UseZoneMutationReturn {
  const queryClient = useQueryClient();

  /**
   * Helper to create a default pagination object
   */
  const getDefaultPagination = (itemCount: number) => ({
    has_more: false,
    limit: 50,
    total: itemCount,
  });

  const createMutation = useMutation({
    mutationFn: ({ cameraId, data }: { cameraId: string; data: ZoneCreate }) =>
      createZone(cameraId, data),

    // Optimistic update: add the new zone immediately
    onMutate: async ({ cameraId, data }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.zones(cameraId) });

      // Snapshot the previous value for rollback
      const previousZones = queryClient.getQueryData<ZoneListResponse>(
        queryKeys.cameras.zones(cameraId)
      );

      // Create a temporary zone with a placeholder ID
      const tempId = 'temp-' + String(Date.now());
      const optimisticZone: Zone = {
        id: tempId,
        camera_id: cameraId,
        name: data.name,
        zone_type: data.zone_type,
        coordinates: data.coordinates,
        shape: data.shape,
        color: data.color,
        enabled: data.enabled ?? true,
        priority: data.priority ?? 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const newItems = [...(previousZones?.items ?? []), optimisticZone];

      // Optimistically add the zone to the cache
      queryClient.setQueryData<ZoneListResponse>(queryKeys.cameras.zones(cameraId), {
        items: newItems,
        pagination: previousZones?.pagination ?? getDefaultPagination(newItems.length),
      });

      // Return context with snapshot for rollback
      return { previousZones, optimisticId: optimisticZone.id, cameraId };
    },

    // On error, rollback to the previous value
    onError: (_err, _variables, context) => {
      if (context?.previousZones && context?.cameraId) {
        queryClient.setQueryData(queryKeys.cameras.zones(context.cameraId), context.previousZones);
      }
    },

    // Replace the optimistic zone with the real one on success
    onSuccess: (newZone, _variables, context) => {
      if (context?.cameraId) {
        const currentData = queryClient.getQueryData<ZoneListResponse>(
          queryKeys.cameras.zones(context.cameraId)
        );
        const newItems =
          currentData?.items?.map((zone) =>
            zone.id === context.optimisticId ? newZone : zone
          ) ?? [];
        queryClient.setQueryData<ZoneListResponse>(queryKeys.cameras.zones(context.cameraId), {
          items: newItems,
          pagination: currentData?.pagination ?? getDefaultPagination(newItems.length),
        });
      }
    },

    // Always refetch after error or success for data consistency
    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.zones(variables.cameraId) });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      cameraId,
      zoneId,
      data,
    }: {
      cameraId: string;
      zoneId: string;
      data: ZoneUpdate;
    }) => updateZone(cameraId, zoneId, data),

    // Optimistic update: immediately update the cache
    onMutate: async ({ cameraId, zoneId, data }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.zones(cameraId) });

      // Snapshot the previous value for rollback
      const previousZones = queryClient.getQueryData<ZoneListResponse>(
        queryKeys.cameras.zones(cameraId)
      );

      // Optimistically update the cache
      const newItems =
        previousZones?.items?.map((zone) => {
          if (zone.id !== zoneId) return zone;
          // Apply updates (supports coordinates for redraw)
          const updates: Partial<Zone> = {};
          if (data.name !== null && data.name !== undefined) updates.name = data.name;
          if (data.zone_type !== null && data.zone_type !== undefined)
            updates.zone_type = data.zone_type;
          if (data.coordinates !== null && data.coordinates !== undefined)
            updates.coordinates = data.coordinates;
          if (data.color !== null && data.color !== undefined) updates.color = data.color;
          if (data.enabled !== null && data.enabled !== undefined) updates.enabled = data.enabled;
          if (data.priority !== null && data.priority !== undefined)
            updates.priority = data.priority;
          return { ...zone, ...updates, updated_at: new Date().toISOString() };
        }) ?? [];

      queryClient.setQueryData<ZoneListResponse>(queryKeys.cameras.zones(cameraId), {
        items: newItems,
        pagination: previousZones?.pagination ?? getDefaultPagination(newItems.length),
      });

      // Return context with snapshot for rollback
      return { previousZones, cameraId };
    },

    // On error, rollback to the previous value
    onError: (_err, _variables, context) => {
      if (context?.previousZones && context?.cameraId) {
        queryClient.setQueryData(queryKeys.cameras.zones(context.cameraId), context.previousZones);
      }
    },

    // Always refetch after error or success for data consistency
    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.zones(variables.cameraId) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ cameraId, zoneId }: { cameraId: string; zoneId: string }) =>
      deleteZone(cameraId, zoneId),

    // Optimistic update: immediately remove the zone
    onMutate: async ({ cameraId, zoneId }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.zones(cameraId) });

      // Snapshot the previous value for rollback
      const previousZones = queryClient.getQueryData<ZoneListResponse>(
        queryKeys.cameras.zones(cameraId)
      );

      // Optimistically remove the zone from the cache
      const newItems = previousZones?.items?.filter((zone) => zone.id !== zoneId) ?? [];
      queryClient.setQueryData<ZoneListResponse>(queryKeys.cameras.zones(cameraId), {
        items: newItems,
        pagination: previousZones?.pagination ?? getDefaultPagination(newItems.length),
      });

      // Return context with snapshot for rollback
      return { previousZones, cameraId };
    },

    // On error, rollback to the previous value
    onError: (_err, _variables, context) => {
      if (context?.previousZones && context?.cameraId) {
        queryClient.setQueryData(queryKeys.cameras.zones(context.cameraId), context.previousZones);
      }
    },

    // Always refetch and clean up after error or success
    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.zones(variables.cameraId) });
    },
  });

  return {
    createMutation,
    updateMutation,
    deleteMutation,
  };
}
