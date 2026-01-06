/**
 * useCamerasQuery - TanStack Query hooks for camera data management
 *
 * This module provides hooks for fetching and mutating camera data using
 * TanStack Query. It includes:
 * - useCamerasQuery: Fetch all cameras
 * - useCameraQuery: Fetch a single camera by ID
 * - useCameraMutation: Create, update, and delete cameras
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Optimistic updates support
 * - Background refetching
 *
 * @module hooks/useCamerasQuery
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchCameras,
  fetchCamera,
  createCamera,
  updateCamera,
  deleteCamera,
  type Camera,
  type CameraCreate,
  type CameraUpdate,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// useCamerasQuery - Fetch all cameras
// ============================================================================

/**
 * Options for configuring the useCamerasQuery hook
 */
export interface UseCamerasQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

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
 * Return type for the useCamerasQuery hook
 */
export interface UseCamerasQueryReturn {
  /** List of cameras, empty array if not yet fetched */
  cameras: Camera[];
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
 * Hook to fetch all cameras using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Camera list and query state
 *
 * @example
 * ```tsx
 * const { cameras, isLoading, error } = useCamerasQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <ul>
 *     {cameras.map(cam => <li key={cam.id}>{cam.name}</li>)}
 *   </ul>
 * );
 * ```
 */
export function useCamerasQuery(
  options: UseCamerasQueryOptions = {}
): UseCamerasQueryReturn {
  const { enabled = true, refetchInterval = false, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.cameras.list(),
    queryFn: fetchCameras,
    enabled,
    refetchInterval,
    staleTime,
    // Reduced retry for faster failure feedback
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const cameras = useMemo(() => query.data ?? [], [query.data]);

  return {
    cameras,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useCameraQuery - Fetch single camera by ID
// ============================================================================

/**
 * Options for configuring the useCameraQuery hook
 */
export interface UseCameraQueryOptions {
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
 * Return type for the useCameraQuery hook
 */
export interface UseCameraQueryReturn {
  /** Camera data, undefined if not yet fetched */
  data: Camera | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single camera by ID using TanStack Query.
 *
 * @param id - Camera ID to fetch, or undefined to disable the query
 * @param options - Configuration options
 * @returns Camera data and query state
 *
 * @example
 * ```tsx
 * const { data: camera, isLoading, error } = useCameraQuery(cameraId);
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 * if (!camera) return null;
 *
 * return <CameraDetails camera={camera} />;
 * ```
 */
export function useCameraQuery(
  id: string | undefined,
  options: UseCameraQueryOptions = {}
): UseCameraQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.cameras.detail(id ?? ''),
    queryFn: () => {
      if (!id) {
        throw new Error('Camera ID is required');
      }
      return fetchCamera(id);
    },
    enabled: enabled && !!id,
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
// useCameraMutation - Create, update, delete cameras
// ============================================================================

/**
 * Return type for the useCameraMutation hook
 */
export interface UseCameraMutationReturn {
  /** Mutation for creating a new camera */
  createMutation: ReturnType<typeof useMutation<Camera, Error, CameraCreate>>;
  /** Mutation for updating an existing camera */
  updateMutation: ReturnType<typeof useMutation<Camera, Error, { id: string; data: CameraUpdate }>>;
  /** Mutation for deleting a camera */
  deleteMutation: ReturnType<typeof useMutation<void, Error, string>>;
}

/**
 * Hook providing mutations for camera CRUD operations.
 *
 * All mutations automatically invalidate the cameras query cache on success,
 * ensuring the UI stays in sync with the server.
 *
 * @returns Object containing create, update, and delete mutations
 *
 * @example
 * ```tsx
 * const { createMutation, updateMutation, deleteMutation } = useCameraMutation();
 *
 * // Create a new camera
 * await createMutation.mutateAsync({ name: 'New Camera', enabled: true });
 *
 * // Update a camera
 * await updateMutation.mutateAsync({ id: 'cam-1', data: { name: 'Updated' } });
 *
 * // Delete a camera
 * await deleteMutation.mutateAsync('cam-1');
 * ```
 */
export function useCameraMutation(): UseCameraMutationReturn {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: CameraCreate) => createCamera(data),
    onSuccess: () => {
      // Invalidate all camera queries to refetch the list
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CameraUpdate }) => updateCamera(id, data),
    onSuccess: (_data, variables) => {
      // Invalidate all camera queries (list and detail)
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      // Also specifically invalidate the detail query for this camera
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.detail(variables.id) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCamera(id),
    onSuccess: (_data, id) => {
      // Invalidate all camera queries
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      // Remove the specific camera from cache
      queryClient.removeQueries({ queryKey: queryKeys.cameras.detail(id) });
    },
  });

  return {
    createMutation,
    updateMutation,
    deleteMutation,
  };
}
