/**
 * useHierarchy - TanStack Query hooks for organizational hierarchy management
 *
 * This module provides hooks for managing the household organizational hierarchy:
 * - Households (top-level organization units)
 * - Properties (physical locations within a household)
 * - Areas (logical zones within a property)
 * - Camera-Area linking (many-to-many relationship)
 *
 * Implements Phase 7.4 of NEM-3113 (Orphaned Infrastructure Integration).
 *
 * @module hooks/useHierarchy
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  // API functions
  fetchHouseholds,
  fetchHousehold,
  createHousehold,
  updateHousehold,
  deleteHousehold,
  fetchProperties,
  fetchProperty,
  createProperty,
  updateProperty,
  deleteProperty,
  fetchAreas,
  fetchArea,
  createArea,
  updateArea,
  deleteArea,
  fetchAreaCameras,
  linkCameraToArea,
  unlinkCameraFromArea,
  // Types
  type Household,
  type HouseholdCreate,
  type HouseholdUpdate,
  type Property,
  type PropertyCreate,
  type PropertyUpdate,
  type Area,
  type AreaCreate,
  type AreaUpdate,
  type AreaCamerasResponse,
  type CameraLinkResponse,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// Re-export types for convenience
export type {
  Household,
  HouseholdCreate,
  HouseholdUpdate,
  Property,
  PropertyCreate,
  PropertyUpdate,
  Area,
  AreaCreate,
  AreaUpdate,
  AreaCamerasResponse,
  CameraLinkResponse,
};

// ============================================================================
// Household Hooks
// ============================================================================

/**
 * Options for configuring the useHouseholdsQuery hook.
 */
export interface UseHouseholdsQueryOptions {
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
  /** Refetch interval in milliseconds (default: false) */
  refetchInterval?: number | false;
  /** Custom stale time in milliseconds (default: DEFAULT_STALE_TIME) */
  staleTime?: number;
}

/**
 * Return type for the useHouseholdsQuery hook.
 */
export interface UseHouseholdsQueryReturn {
  /** List of households, empty array if not yet fetched */
  households: Household[];
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
 * Hook to fetch all households using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Household list and query state
 *
 * @example
 * ```tsx
 * const { households, isLoading, error } = useHouseholdsQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <ul>
 *     {households.map(h => <li key={h.id}>{h.name}</li>)}
 *   </ul>
 * );
 * ```
 */
export function useHouseholdsQuery(
  options: UseHouseholdsQueryOptions = {}
): UseHouseholdsQueryReturn {
  const { enabled = true, refetchInterval = false, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.hierarchy.households.list(),
    queryFn: fetchHouseholds,
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  const households = useMemo(() => query.data ?? [], [query.data]);

  return {
    households,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Options for configuring the useHouseholdQuery hook.
 */
export interface UseHouseholdQueryOptions {
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
  /** Custom stale time in milliseconds (default: DEFAULT_STALE_TIME) */
  staleTime?: number;
}

/**
 * Return type for the useHouseholdQuery hook.
 */
export interface UseHouseholdQueryReturn {
  /** Household data, undefined if not yet fetched */
  data: Household | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single household by ID.
 *
 * @param id - Household ID, or undefined to disable the query
 * @param options - Configuration options
 * @returns Household data and query state
 */
export function useHouseholdQuery(
  id: number | undefined,
  options: UseHouseholdQueryOptions = {}
): UseHouseholdQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.hierarchy.households.detail(id ?? 0),
    queryFn: () => {
      if (id === undefined) {
        throw new Error('Household ID is required');
      }
      return fetchHousehold(id);
    },
    enabled: enabled && id !== undefined,
    staleTime,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Return type for the useHouseholdMutation hook.
 */
export interface UseHouseholdMutationReturn {
  /** Mutation for creating a new household */
  createMutation: ReturnType<typeof useMutation<Household, Error, HouseholdCreate>>;
  /** Mutation for updating an existing household */
  updateMutation: ReturnType<
    typeof useMutation<Household, Error, { id: number; data: HouseholdUpdate }>
  >;
  /** Mutation for deleting a household */
  deleteMutation: ReturnType<typeof useMutation<void, Error, number>>;
}

/**
 * Hook providing mutations for household CRUD operations.
 *
 * All mutations implement optimistic updates and automatic cache invalidation.
 *
 * @returns Object containing create, update, and delete mutations
 */
export function useHouseholdMutation(): UseHouseholdMutationReturn {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: HouseholdCreate) => createHousehold(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.households.all });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: HouseholdUpdate }) => updateHousehold(id, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.households.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.hierarchy.households.detail(variables.id),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteHousehold(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.households.all });
      queryClient.removeQueries({ queryKey: queryKeys.hierarchy.households.detail(id) });
      // Also invalidate related properties
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.properties.all });
    },
  });

  return {
    createMutation,
    updateMutation,
    deleteMutation,
  };
}

// ============================================================================
// Property Hooks
// ============================================================================

/**
 * Options for configuring the usePropertiesQuery hook.
 */
export interface UsePropertiesQueryOptions {
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
  /** Refetch interval in milliseconds (default: false) */
  refetchInterval?: number | false;
  /** Custom stale time in milliseconds (default: DEFAULT_STALE_TIME) */
  staleTime?: number;
}

/**
 * Return type for the usePropertiesQuery hook.
 */
export interface UsePropertiesQueryReturn {
  /** List of properties, empty array if not yet fetched */
  properties: Property[];
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
 * Hook to fetch all properties for a household.
 *
 * @param householdId - Household ID, or undefined to disable the query
 * @param options - Configuration options
 * @returns Property list and query state
 */
export function usePropertiesQuery(
  householdId: number | undefined,
  options: UsePropertiesQueryOptions = {}
): UsePropertiesQueryReturn {
  const { enabled = true, refetchInterval = false, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.hierarchy.properties.list(householdId ?? 0),
    queryFn: () => {
      if (householdId === undefined) {
        throw new Error('Household ID is required');
      }
      return fetchProperties(householdId);
    },
    enabled: enabled && householdId !== undefined,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  const properties = useMemo(() => query.data ?? [], [query.data]);

  return {
    properties,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Options for configuring the usePropertyQuery hook.
 */
export interface UsePropertyQueryOptions {
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
  /** Custom stale time in milliseconds (default: DEFAULT_STALE_TIME) */
  staleTime?: number;
}

/**
 * Return type for the usePropertyQuery hook.
 */
export interface UsePropertyQueryReturn {
  /** Property data, undefined if not yet fetched */
  data: Property | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single property by ID.
 *
 * @param id - Property ID, or undefined to disable the query
 * @param options - Configuration options
 * @returns Property data and query state
 */
export function usePropertyQuery(
  id: number | undefined,
  options: UsePropertyQueryOptions = {}
): UsePropertyQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.hierarchy.properties.detail(id ?? 0),
    queryFn: () => {
      if (id === undefined) {
        throw new Error('Property ID is required');
      }
      return fetchProperty(id);
    },
    enabled: enabled && id !== undefined,
    staleTime,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Return type for the usePropertyMutation hook.
 */
export interface UsePropertyMutationReturn {
  /** Mutation for creating a new property */
  createMutation: ReturnType<
    typeof useMutation<Property, Error, { householdId: number; data: PropertyCreate }>
  >;
  /** Mutation for updating an existing property */
  updateMutation: ReturnType<
    typeof useMutation<Property, Error, { id: number; data: PropertyUpdate }>
  >;
  /** Mutation for deleting a property */
  deleteMutation: ReturnType<typeof useMutation<void, Error, number>>;
}

/**
 * Hook providing mutations for property CRUD operations.
 *
 * @returns Object containing create, update, and delete mutations
 */
export function usePropertyMutation(): UsePropertyMutationReturn {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: ({ householdId, data }: { householdId: number; data: PropertyCreate }) =>
      createProperty(householdId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.properties.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.hierarchy.properties.list(variables.householdId),
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: PropertyUpdate }) => updateProperty(id, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.properties.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.hierarchy.properties.detail(variables.id),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteProperty(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.properties.all });
      queryClient.removeQueries({ queryKey: queryKeys.hierarchy.properties.detail(id) });
      // Also invalidate related areas
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.areas.all });
    },
  });

  return {
    createMutation,
    updateMutation,
    deleteMutation,
  };
}

// ============================================================================
// Area Hooks
// ============================================================================

/**
 * Options for configuring the useAreasQuery hook.
 */
export interface UseAreasQueryOptions {
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
  /** Refetch interval in milliseconds (default: false) */
  refetchInterval?: number | false;
  /** Custom stale time in milliseconds (default: DEFAULT_STALE_TIME) */
  staleTime?: number;
}

/**
 * Return type for the useAreasQuery hook.
 */
export interface UseAreasQueryReturn {
  /** List of areas, empty array if not yet fetched */
  areas: Area[];
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
 * Hook to fetch all areas for a property.
 *
 * @param propertyId - Property ID, or undefined to disable the query
 * @param options - Configuration options
 * @returns Area list and query state
 */
export function useAreasQuery(
  propertyId: number | undefined,
  options: UseAreasQueryOptions = {}
): UseAreasQueryReturn {
  const { enabled = true, refetchInterval = false, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.hierarchy.areas.list(propertyId ?? 0),
    queryFn: () => {
      if (propertyId === undefined) {
        throw new Error('Property ID is required');
      }
      return fetchAreas(propertyId);
    },
    enabled: enabled && propertyId !== undefined,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  const areas = useMemo(() => query.data ?? [], [query.data]);

  return {
    areas,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Options for configuring the useAreaQuery hook.
 */
export interface UseAreaQueryOptions {
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
  /** Custom stale time in milliseconds (default: DEFAULT_STALE_TIME) */
  staleTime?: number;
}

/**
 * Return type for the useAreaQuery hook.
 */
export interface UseAreaQueryReturn {
  /** Area data, undefined if not yet fetched */
  data: Area | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single area by ID.
 *
 * @param id - Area ID, or undefined to disable the query
 * @param options - Configuration options
 * @returns Area data and query state
 */
export function useAreaQuery(
  id: number | undefined,
  options: UseAreaQueryOptions = {}
): UseAreaQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.hierarchy.areas.detail(id ?? 0),
    queryFn: () => {
      if (id === undefined) {
        throw new Error('Area ID is required');
      }
      return fetchArea(id);
    },
    enabled: enabled && id !== undefined,
    staleTime,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Return type for the useAreaMutation hook.
 */
export interface UseAreaMutationReturn {
  /** Mutation for creating a new area */
  createMutation: ReturnType<
    typeof useMutation<Area, Error, { propertyId: number; data: AreaCreate }>
  >;
  /** Mutation for updating an existing area */
  updateMutation: ReturnType<typeof useMutation<Area, Error, { id: number; data: AreaUpdate }>>;
  /** Mutation for deleting an area */
  deleteMutation: ReturnType<typeof useMutation<void, Error, number>>;
}

/**
 * Hook providing mutations for area CRUD operations.
 *
 * @returns Object containing create, update, and delete mutations
 */
export function useAreaMutation(): UseAreaMutationReturn {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: ({ propertyId, data }: { propertyId: number; data: AreaCreate }) =>
      createArea(propertyId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.areas.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.hierarchy.areas.list(variables.propertyId),
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AreaUpdate }) => updateArea(id, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.areas.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.hierarchy.areas.detail(variables.id),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteArea(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.areas.all });
      queryClient.removeQueries({ queryKey: queryKeys.hierarchy.areas.detail(id) });
      // Also invalidate camera links
      queryClient.removeQueries({ queryKey: queryKeys.hierarchy.areas.cameras(id) });
    },
  });

  return {
    createMutation,
    updateMutation,
    deleteMutation,
  };
}

// ============================================================================
// Area Camera Linking Hooks
// ============================================================================

/**
 * Options for configuring the useAreaCamerasQuery hook.
 */
export interface UseAreaCamerasQueryOptions {
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
  /** Refetch interval in milliseconds (default: false) */
  refetchInterval?: number | false;
  /** Custom stale time in milliseconds (default: DEFAULT_STALE_TIME) */
  staleTime?: number;
}

/**
 * Return type for the useAreaCamerasQuery hook.
 */
export interface UseAreaCamerasQueryReturn {
  /** Area cameras response, undefined if not yet fetched */
  data: AreaCamerasResponse | undefined;
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
 * Hook to fetch all cameras linked to an area.
 *
 * @param areaId - Area ID, or undefined to disable the query
 * @param options - Configuration options
 * @returns Area cameras response and query state
 */
export function useAreaCamerasQuery(
  areaId: number | undefined,
  options: UseAreaCamerasQueryOptions = {}
): UseAreaCamerasQueryReturn {
  const { enabled = true, refetchInterval = false, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.hierarchy.areas.cameras(areaId ?? 0),
    queryFn: () => {
      if (areaId === undefined) {
        throw new Error('Area ID is required');
      }
      return fetchAreaCameras(areaId);
    },
    enabled: enabled && areaId !== undefined,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Return type for the useCameraLinkMutation hook.
 */
export interface UseCameraLinkMutationReturn {
  /** Mutation for linking a camera to an area */
  linkMutation: ReturnType<
    typeof useMutation<CameraLinkResponse, Error, { areaId: number; cameraId: string }>
  >;
  /** Mutation for unlinking a camera from an area */
  unlinkMutation: ReturnType<
    typeof useMutation<CameraLinkResponse, Error, { areaId: number; cameraId: string }>
  >;
}

/**
 * Hook providing mutations for camera linking/unlinking operations.
 *
 * @returns Object containing link and unlink mutations
 */
export function useCameraLinkMutation(): UseCameraLinkMutationReturn {
  const queryClient = useQueryClient();

  const linkMutation = useMutation({
    mutationFn: ({ areaId, cameraId }: { areaId: number; cameraId: string }) =>
      linkCameraToArea(areaId, cameraId),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.hierarchy.areas.cameras(variables.areaId),
      });
    },
  });

  const unlinkMutation = useMutation({
    mutationFn: ({ areaId, cameraId }: { areaId: number; cameraId: string }) =>
      unlinkCameraFromArea(areaId, cameraId),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.hierarchy.areas.cameras(variables.areaId),
      });
    },
  });

  return {
    linkMutation,
    unlinkMutation,
  };
}
