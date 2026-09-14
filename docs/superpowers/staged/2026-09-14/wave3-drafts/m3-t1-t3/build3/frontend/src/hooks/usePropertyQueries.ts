/**
 * TanStack Query hooks for Property and Area management.
 *
 * Provides CRUD operations for:
 * - Properties (physical locations within a household)
 * - Areas (logical zones within a property)
 * - Camera linking to areas
 *
 * @see NEM-3135 - Phase 7.2: Create PropertyManagement component
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchProperties,
  createProperty as apiCreateProperty,
  updateProperty as apiUpdateProperty,
  deleteProperty as apiDeleteProperty,
  fetchAreas,
  createArea as apiCreateArea,
  updateArea as apiUpdateArea,
  deleteArea as apiDeleteArea,
  fetchAreaCameras,
  linkCameraToArea as apiLinkCamera,
  unlinkCameraFromArea as apiUnlinkCamera,
  type Property,
  type PropertyCreate,
  type PropertyUpdate,
  type PropertyListResponse,
  type Area,
  type AreaCreate,
  type AreaUpdate,
  type AreaListResponse,
  type AreaCamera,
  type AreaCamerasResponse,
  type CameraLinkResponse,
} from '../services/api';

// =============================================================================
// Re-export Types with Aliases for Component Compatibility
// =============================================================================

/** Property response from API - alias for Property */
export type PropertyResponse = Property;

/** Area response from API - alias for Area */
export type AreaResponse = Area;

/** Camera info in area context - alias for AreaCamera */
export type AreaCameraResponse = AreaCamera;

// Re-export other types directly
export type {
  PropertyCreate,
  PropertyUpdate,
  PropertyListResponse,
  AreaCreate,
  AreaUpdate,
  AreaListResponse,
  AreaCamerasResponse,
  CameraLinkResponse,
};

// =============================================================================
// Query Keys
// =============================================================================

export const propertyQueryKeys = {
  all: ['properties'] as const,
  lists: () => [...propertyQueryKeys.all, 'list'] as const,
  list: (householdId: number) => [...propertyQueryKeys.lists(), householdId] as const,
  details: () => [...propertyQueryKeys.all, 'detail'] as const,
  detail: (propertyId: number) => [...propertyQueryKeys.details(), propertyId] as const,
};

export const areaQueryKeys = {
  all: ['areas'] as const,
  lists: () => [...areaQueryKeys.all, 'list'] as const,
  list: (propertyId: number) => [...areaQueryKeys.lists(), propertyId] as const,
  details: () => [...areaQueryKeys.all, 'detail'] as const,
  detail: (areaId: number) => [...areaQueryKeys.details(), areaId] as const,
  cameras: (areaId: number) => [...areaQueryKeys.detail(areaId), 'cameras'] as const,
};

// =============================================================================
// Query Hooks
// =============================================================================

export interface UsePropertiesQueryOptions {
  householdId: number;
  enabled?: boolean;
}

export interface UsePropertiesQueryReturn {
  properties: PropertyResponse[];
  total: number;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

/**
 * Query hook for fetching properties for a household.
 */
export function usePropertiesQuery({
  householdId,
  enabled = true,
}: UsePropertiesQueryOptions): UsePropertiesQueryReturn {
  const query = useQuery({
    queryKey: propertyQueryKeys.list(householdId),
    queryFn: () => fetchProperties(householdId),
    enabled: enabled && householdId > 0,
  });

  // fetchProperties returns Property[] directly
  const properties = query.data ?? [];

  return {
    properties,
    total: properties.length,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

export interface UseAreasQueryOptions {
  propertyId: number;
  enabled?: boolean;
}

export interface UseAreasQueryReturn {
  areas: AreaResponse[];
  total: number;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

/**
 * Query hook for fetching areas for a property.
 */
export function useAreasQuery({
  propertyId,
  enabled = true,
}: UseAreasQueryOptions): UseAreasQueryReturn {
  const query = useQuery({
    queryKey: areaQueryKeys.list(propertyId),
    queryFn: () => fetchAreas(propertyId),
    enabled: enabled && propertyId > 0,
  });

  // fetchAreas returns Area[] directly
  const areas = query.data ?? [];

  return {
    areas,
    total: areas.length,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

export interface UseAreaCamerasQueryOptions {
  areaId: number;
  enabled?: boolean;
}

export interface UseAreaCamerasQueryReturn {
  cameras: AreaCameraResponse[];
  count: number;
  areaName: string;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

/**
 * Query hook for fetching cameras linked to an area.
 */
export function useAreaCamerasQuery({
  areaId,
  enabled = true,
}: UseAreaCamerasQueryOptions): UseAreaCamerasQueryReturn {
  const query = useQuery({
    queryKey: areaQueryKeys.cameras(areaId),
    queryFn: () => fetchAreaCameras(areaId),
    enabled: enabled && areaId > 0,
  });

  return {
    cameras: query.data?.cameras ?? [],
    count: query.data?.count ?? 0,
    areaName: query.data?.area_name ?? '',
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// =============================================================================
// Mutation Hooks
// =============================================================================

export interface UsePropertyMutationsReturn {
  createProperty: ReturnType<
    typeof useMutation<PropertyResponse, Error, { householdId: number; data: PropertyCreate }>
  >;
  updateProperty: ReturnType<
    typeof useMutation<PropertyResponse, Error, { propertyId: number; data: PropertyUpdate }>
  >;
  deleteProperty: ReturnType<
    typeof useMutation<void, Error, { propertyId: number; householdId: number }>
  >;
}

/**
 * Mutation hooks for property CRUD operations.
 */
export function usePropertyMutations(): UsePropertyMutationsReturn {
  const queryClient = useQueryClient();

  const createPropertyMutation = useMutation({
    mutationFn: ({ householdId, data }: { householdId: number; data: PropertyCreate }) =>
      apiCreateProperty(householdId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: propertyQueryKeys.list(variables.householdId),
      });
    },
  });

  const updatePropertyMutation = useMutation({
    mutationFn: ({ propertyId, data }: { propertyId: number; data: PropertyUpdate }) =>
      apiUpdateProperty(propertyId, data),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({
        queryKey: propertyQueryKeys.list(data.household_id),
      });
      void queryClient.invalidateQueries({
        queryKey: propertyQueryKeys.detail(data.id),
      });
    },
  });

  const deletePropertyMutation = useMutation({
    mutationFn: ({ propertyId }: { propertyId: number; householdId: number }) =>
      apiDeleteProperty(propertyId),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: propertyQueryKeys.list(variables.householdId),
      });
    },
  });

  return {
    createProperty: createPropertyMutation,
    updateProperty: updatePropertyMutation,
    deleteProperty: deletePropertyMutation,
  };
}

export interface UseAreaMutationsReturn {
  createArea: ReturnType<
    typeof useMutation<AreaResponse, Error, { propertyId: number; data: AreaCreate }>
  >;
  updateArea: ReturnType<
    typeof useMutation<AreaResponse, Error, { areaId: number; data: AreaUpdate }>
  >;
  deleteArea: ReturnType<typeof useMutation<void, Error, { areaId: number; propertyId: number }>>;
  linkCamera: ReturnType<
    typeof useMutation<CameraLinkResponse, Error, { areaId: number; cameraId: string }>
  >;
  unlinkCamera: ReturnType<
    typeof useMutation<CameraLinkResponse, Error, { areaId: number; cameraId: string }>
  >;
}

/**
 * Mutation hooks for area CRUD and camera linking operations.
 */
export function useAreaMutations(): UseAreaMutationsReturn {
  const queryClient = useQueryClient();

  const createAreaMutation = useMutation({
    mutationFn: ({ propertyId, data }: { propertyId: number; data: AreaCreate }) =>
      apiCreateArea(propertyId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: areaQueryKeys.list(variables.propertyId),
      });
    },
  });

  const updateAreaMutation = useMutation({
    mutationFn: ({ areaId, data }: { areaId: number; data: AreaUpdate }) =>
      apiUpdateArea(areaId, data),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({
        queryKey: areaQueryKeys.list(data.property_id),
      });
      void queryClient.invalidateQueries({
        queryKey: areaQueryKeys.detail(data.id),
      });
    },
  });

  const deleteAreaMutation = useMutation({
    mutationFn: ({ areaId }: { areaId: number; propertyId: number }) => apiDeleteArea(areaId),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: areaQueryKeys.list(variables.propertyId),
      });
    },
  });

  const linkCameraMutation = useMutation({
    mutationFn: ({ areaId, cameraId }: { areaId: number; cameraId: string }) =>
      apiLinkCamera(areaId, cameraId),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({
        queryKey: areaQueryKeys.cameras(data.area_id),
      });
    },
  });

  const unlinkCameraMutation = useMutation({
    mutationFn: ({ areaId, cameraId }: { areaId: number; cameraId: string }) =>
      apiUnlinkCamera(areaId, cameraId),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({
        queryKey: areaQueryKeys.cameras(data.area_id),
      });
    },
  });

  return {
    createArea: createAreaMutation,
    updateArea: updateAreaMutation,
    deleteArea: deleteAreaMutation,
    linkCamera: linkCameraMutation,
    unlinkCamera: unlinkCameraMutation,
  };
}
