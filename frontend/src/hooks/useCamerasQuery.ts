/**
 * useCamerasQuery - TanStack Query hooks for camera data management
 *
 * This module provides hooks for fetching and mutating camera data using
 * TanStack Query. It includes:
 * - useCamerasQuery: Fetch all cameras (with placeholderData support - NEM-3409)
 * - useCameraQuery: Fetch a single camera by ID
 * - useCameraMutation: Create, update, and delete cameras
 * - useCamerasWithSelect: Fetch cameras with data transformation (NEM-3410)
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Optimistic updates support
 * - Background refetching
 * - PlaceholderData for better UX during loading states
 * - Select option for efficient data transformation
 *
 * @module hooks/useCamerasQuery
 * @see NEM-3409 - placeholderData pattern implementation
 * @see NEM-3410 - select option for data transformation
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  createPlaceholderCameras,
  selectOnlineCameras,
  selectCameraCountsByStatus,
} from './useQueryPatterns';
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

  /**
   * Number of placeholder cameras to show during loading.
   * Set to 0 to disable placeholder data.
   * @default 6
   * @see NEM-3409 - placeholderData pattern
   */
  placeholderCount?: number;

  /**
   * Custom selector to transform the camera data.
   * When provided, only the selected data is returned and memoized.
   * @see NEM-3410 - select option for data transformation
   * @example
   * ```tsx
   * // Filter to only online cameras
   * const { cameras } = useCamerasQuery({
   *   select: (cameras) => cameras.filter(c => c.status === 'online'),
   * });
   * ```
   */
  select?: (cameras: Camera[]) => Camera[];
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
  /** Whether the data is placeholder data (NEM-3409) */
  isPlaceholderData: boolean;
}

/**
 * Hook to fetch all cameras using TanStack Query.
 *
 * Supports TanStack Query v5 patterns:
 * - placeholderData: Shows skeleton cameras during loading (NEM-3409)
 * - select: Transform data at query level for efficient memoization (NEM-3410)
 *
 * @param options - Configuration options
 * @returns Camera list and query state
 *
 * @example
 * ```tsx
 * // Basic usage with placeholder data
 * const { cameras, isLoading, isPlaceholderData } = useCamerasQuery();
 *
 * return (
 *   <ul>
 *     {cameras.map(cam => (
 *       <li key={cam.id} className={isPlaceholderData ? 'animate-pulse' : ''}>
 *         {cam.name}
 *       </li>
 *     ))}
 *   </ul>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With select to filter only online cameras
 * const { cameras } = useCamerasQuery({
 *   select: (cams) => cams.filter(c => c.status === 'online'),
 * });
 * ```
 */
export function useCamerasQuery(options: UseCamerasQueryOptions = {}): UseCamerasQueryReturn {
  const {
    enabled = true,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
    placeholderCount = 6,
    select,
  } = options;

  // Create stable placeholder data reference
  const placeholderData = useMemo(
    () => (placeholderCount > 0 ? createPlaceholderCameras(placeholderCount) : undefined),
    [placeholderCount]
  );

  const query = useQuery({
    queryKey: queryKeys.cameras.list(),
    queryFn: fetchCameras,
    enabled,
    refetchInterval,
    staleTime,
    // Reduced retry for faster failure feedback
    retry: 1,
    // PlaceholderData pattern (NEM-3409): Show skeleton data during loading
    placeholderData,
    // Select pattern (NEM-3410): Transform data at query level
    select,
  });

  // Provide empty array as default to avoid null checks
  const cameras = useMemo(() => query.data ?? [], [query.data]);

  return {
    cameras,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    isPlaceholderData: query.isPlaceholderData,
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
 * All mutations implement optimistic updates for immediate UI feedback,
 * with automatic rollback on failure. The cache is automatically invalidated
 * on success to ensure the UI stays in sync with the server.
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

    // Optimistic update: add the new camera immediately
    onMutate: async (newCameraData) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.all });

      // Snapshot the previous value for rollback
      const previousCameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());

      // Create a temporary camera with a placeholder ID
      const optimisticCamera: Camera = {
        id: `temp-${Date.now()}`,
        name: newCameraData.name,
        folder_path: newCameraData.folder_path,
        status: newCameraData.status ?? 'online',
        last_seen_at: null,
        created_at: new Date().toISOString(),
      };

      // Optimistically add the camera to the cache
      queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) => [
        ...(old ?? []),
        optimisticCamera,
      ]);

      // Return context with snapshot for rollback
      return { previousCameras, optimisticId: optimisticCamera.id };
    },

    // On error, rollback to the previous value
    onError: (_err, _variables, context) => {
      if (context?.previousCameras) {
        queryClient.setQueryData(queryKeys.cameras.list(), context.previousCameras);
      }
    },

    // Replace the optimistic camera with the real one on success
    onSuccess: (newCamera, _variables, context) => {
      queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) =>
        old?.map((camera) => (camera.id === context?.optimisticId ? newCamera : camera))
      );
    },

    // Always refetch after error or success for data consistency
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CameraUpdate }) => updateCamera(id, data),

    // Optimistic update: immediately update the cache
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.all });

      // Snapshot the previous value for rollback
      const previousCameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());

      // Optimistically update the cache (only apply non-null values)
      queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) =>
        old?.map((camera) => {
          if (camera.id !== id) return camera;
          // Filter out null/undefined values to avoid overwriting with nulls
          const updates: Partial<Camera> = {};
          if (data.name !== null && data.name !== undefined) updates.name = data.name;
          if (data.folder_path !== null && data.folder_path !== undefined)
            updates.folder_path = data.folder_path;
          if (data.status !== null && data.status !== undefined) updates.status = data.status;
          return { ...camera, ...updates };
        })
      );

      // Return context with snapshot for rollback
      return { previousCameras };
    },

    // On error, rollback to the previous value
    onError: (_err, _variables, context) => {
      if (context?.previousCameras) {
        queryClient.setQueryData(queryKeys.cameras.list(), context.previousCameras);
      }
    },

    // Always refetch after error or success for data consistency
    onSettled: (_data, _error, variables) => {
      // Invalidate all camera queries (list and detail)
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      // Also specifically invalidate the detail query for this camera
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.detail(variables.id) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCamera(id),

    // Optimistic update: immediately remove the camera
    onMutate: async (deletedId) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.all });

      // Snapshot the previous value for rollback
      const previousCameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());

      // Optimistically remove the camera from the cache
      queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) =>
        old?.filter((camera) => camera.id !== deletedId)
      );

      // Return context with snapshot for rollback
      return { previousCameras };
    },

    // On error, rollback to the previous value
    onError: (_err, _variables, context) => {
      if (context?.previousCameras) {
        queryClient.setQueryData(queryKeys.cameras.list(), context.previousCameras);
      }
    },

    // Always refetch and clean up after error or success
    onSettled: (_data, _error, deletedId) => {
      // Invalidate all camera queries
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      // Remove the specific camera from cache
      queryClient.removeQueries({ queryKey: queryKeys.cameras.detail(deletedId) });
    },
  });

  return {
    createMutation,
    updateMutation,
    deleteMutation,
  };
}

// ============================================================================
// Convenience Hooks with Select Pattern (NEM-3410)
// ============================================================================

/**
 * Return type for useOnlineCamerasQuery hook
 */
export interface UseOnlineCamerasQueryReturn extends Omit<UseCamerasQueryReturn, 'cameras'> {
  /** List of online cameras only */
  cameras: Camera[];
  /** Count of online cameras */
  count: number;
}

/**
 * Hook to fetch only online cameras using the select pattern.
 *
 * This hook demonstrates the select option (NEM-3410) for efficient data
 * transformation. The filter is applied at the query level, ensuring
 * the transformed data is properly memoized by React Query.
 *
 * @param options - Configuration options (same as useCamerasQuery, minus select)
 * @returns Online cameras list and query state
 *
 * @example
 * ```tsx
 * const { cameras, count, isLoading } = useOnlineCamerasQuery();
 *
 * return (
 *   <div>
 *     <span>{count} cameras online</span>
 *     <CameraGrid cameras={cameras} />
 *   </div>
 * );
 * ```
 */
export function useOnlineCamerasQuery(
  options: Omit<UseCamerasQueryOptions, 'select'> = {}
): UseOnlineCamerasQueryReturn {
  const result = useCamerasQuery({
    ...options,
    select: selectOnlineCameras,
  });

  return {
    ...result,
    count: result.cameras.length,
  };
}

/**
 * Return type for useCameraCountsQuery hook
 */
export interface UseCameraCountsQueryReturn {
  /** Camera counts by status */
  counts: {
    online: number;
    offline: number;
    error: number;
    total: number;
  };
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Whether the data is placeholder data */
  isPlaceholderData: boolean;
}

/**
 * Hook to fetch camera counts by status using the select pattern.
 *
 * This hook demonstrates the select option (NEM-3410) for transforming
 * data into aggregated statistics. Only the counts are returned, not
 * the full camera objects, reducing component re-renders.
 *
 * @param options - Configuration options
 * @returns Camera counts by status and query state
 *
 * @example
 * ```tsx
 * const { counts, isLoading } = useCameraCountsQuery();
 *
 * return (
 *   <div>
 *     <span>Online: {counts.online}</span>
 *     <span>Offline: {counts.offline}</span>
 *     <span>Error: {counts.error}</span>
 *   </div>
 * );
 * ```
 */
export function useCameraCountsQuery(
  options: Omit<UseCamerasQueryOptions, 'select'> = {}
): UseCameraCountsQueryReturn {
  const {
    enabled = true,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
    placeholderCount = 6,
  } = options;

  // Create stable placeholder data reference
  const placeholderData = useMemo(
    () => (placeholderCount > 0 ? createPlaceholderCameras(placeholderCount) : undefined),
    [placeholderCount]
  );

  const query = useQuery({
    queryKey: queryKeys.cameras.list(),
    queryFn: fetchCameras,
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
    placeholderData,
    // Use select to transform to counts (NEM-3410)
    select: selectCameraCountsByStatus,
  });

  // Provide default counts to avoid null checks
  const defaultCounts = { online: 0, offline: 0, error: 0, total: 0 };
  const counts = query.data ?? defaultCounts;

  return {
    counts,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    isPlaceholderData: query.isPlaceholderData,
  };
}
