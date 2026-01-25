/**
 * useCameraDelete - TanStack Query hooks for camera soft delete and restore
 *
 * This module provides hooks for managing camera soft deletion:
 * - useDeletedCamerasQuery: Fetch all soft-deleted cameras (trash view)
 * - useDeleteCameraMutation: Soft delete a camera
 * - useRestoreCameraMutation: Restore a soft-deleted camera
 *
 * The backend implements soft delete by setting a `deleted_at` timestamp.
 * Cameras with `deleted_at` set are excluded from normal list queries
 * but can be viewed in the trash and restored.
 *
 * @module hooks/useCameraDelete
 * @see NEM-3643 - Camera Soft Delete UI
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import {
  fetchDeletedCameras,
  deleteCamera,
  restoreCamera,
  type Camera,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query keys for deleted cameras.
 * Kept separate from main camera keys to allow independent invalidation.
 */
export const deletedCamerasQueryKeys = {
  /** Base key for deleted cameras */
  all: ['cameras', 'deleted'] as const,
  /** List of deleted cameras */
  list: () => [...deletedCamerasQueryKeys.all, 'list'] as const,
};

// ============================================================================
// useDeletedCamerasQuery - Fetch soft-deleted cameras
// ============================================================================

/**
 * Options for configuring the useDeletedCamerasQuery hook
 */
export interface UseDeletedCamerasQueryOptions {
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
 * Return type for the useDeletedCamerasQuery hook
 */
export interface UseDeletedCamerasQueryReturn {
  /** List of soft-deleted cameras, empty array if not yet fetched */
  deletedCameras: Camera[];
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
 * Hook to fetch all soft-deleted cameras (trash view).
 *
 * Returns cameras that have been soft-deleted, ordered by deleted_at
 * descending (most recently deleted first).
 *
 * @param options - Configuration options
 * @returns Deleted cameras list and query state
 *
 * @example
 * ```tsx
 * const { deletedCameras, isLoading } = useDeletedCamerasQuery();
 *
 * return (
 *   <ul>
 *     {deletedCameras.map(camera => (
 *       <li key={camera.id}>{camera.name} (deleted)</li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useDeletedCamerasQuery(
  options: UseDeletedCamerasQueryOptions = {}
): UseDeletedCamerasQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: deletedCamerasQueryKeys.list(),
    queryFn: fetchDeletedCameras,
    enabled,
    staleTime,
    retry: 1,
  });

  return {
    deletedCameras: query.data ?? [],
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useDeleteCameraMutation - Soft delete a camera
// ============================================================================

/**
 * Return type for the useDeleteCameraMutation hook
 */
export interface UseDeleteCameraMutationReturn {
  /** Mutation for soft-deleting a camera */
  deleteMutation: ReturnType<typeof useMutation<void, Error, string>>;
}

/**
 * Hook providing mutation for soft-deleting a camera.
 *
 * The mutation implements optimistic updates for immediate UI feedback,
 * with automatic rollback on failure. Both the camera list and deleted
 * cameras list caches are invalidated on success.
 *
 * @returns Object containing delete mutation
 *
 * @example
 * ```tsx
 * const { deleteMutation } = useDeleteCameraMutation();
 *
 * const handleDelete = async (cameraId: string) => {
 *   await deleteMutation.mutateAsync(cameraId);
 * };
 * ```
 */
export function useDeleteCameraMutation(): UseDeleteCameraMutationReturn {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCamera(id),

    // Optimistic update: immediately remove the camera from the list
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
      // Invalidate camera queries (list)
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      // Remove the specific camera from cache
      queryClient.removeQueries({ queryKey: queryKeys.cameras.detail(deletedId) });
      // Invalidate deleted cameras list so it shows the newly deleted camera
      void queryClient.invalidateQueries({ queryKey: deletedCamerasQueryKeys.all });
    },
  });

  return { deleteMutation };
}

// ============================================================================
// useRestoreCameraMutation - Restore a soft-deleted camera
// ============================================================================

/**
 * Return type for the useRestoreCameraMutation hook
 */
export interface UseRestoreCameraMutationReturn {
  /** Mutation for restoring a soft-deleted camera */
  restoreMutation: ReturnType<typeof useMutation<Camera, Error, string>>;
}

/**
 * Hook providing mutation for restoring a soft-deleted camera.
 *
 * The mutation implements optimistic updates for immediate UI feedback,
 * with automatic rollback on failure. Both the camera list and deleted
 * cameras list caches are invalidated on success.
 *
 * @returns Object containing restore mutation
 *
 * @example
 * ```tsx
 * const { restoreMutation } = useRestoreCameraMutation();
 *
 * const handleRestore = async (cameraId: string) => {
 *   const restoredCamera = await restoreMutation.mutateAsync(cameraId);
 *   console.log('Restored:', restoredCamera.name);
 * };
 * ```
 */
export function useRestoreCameraMutation(): UseRestoreCameraMutationReturn {
  const queryClient = useQueryClient();

  const restoreMutation = useMutation({
    mutationFn: (id: string) => restoreCamera(id),

    // Optimistic update: immediately remove from deleted cameras list
    onMutate: async (restoredId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: deletedCamerasQueryKeys.all });
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.all });

      // Snapshot the previous values for rollback
      const previousDeletedCameras = queryClient.getQueryData<Camera[]>(
        deletedCamerasQueryKeys.list()
      );
      const previousCameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());

      // Find the camera being restored
      const restoredCamera = previousDeletedCameras?.find((cam) => cam.id === restoredId);

      // Optimistically remove from deleted cameras list
      queryClient.setQueryData<Camera[]>(deletedCamerasQueryKeys.list(), (old) =>
        old?.filter((camera) => camera.id !== restoredId)
      );

      // Optimistically add to cameras list (if we have the data)
      if (restoredCamera && previousCameras) {
        queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) =>
          old ? [...old, restoredCamera] : [restoredCamera]
        );
      }

      // Return context with snapshots for rollback
      return { previousDeletedCameras, previousCameras };
    },

    // On error, rollback to the previous values
    onError: (_err, _variables, context) => {
      if (context?.previousDeletedCameras) {
        queryClient.setQueryData(deletedCamerasQueryKeys.list(), context.previousDeletedCameras);
      }
      if (context?.previousCameras) {
        queryClient.setQueryData(queryKeys.cameras.list(), context.previousCameras);
      }
    },

    // Always refetch after error or success for data consistency
    onSettled: () => {
      // Invalidate both camera lists
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      void queryClient.invalidateQueries({ queryKey: deletedCamerasQueryKeys.all });
    },
  });

  return { restoreMutation };
}

// ============================================================================
// Convenience Hook - Combined delete and restore
// ============================================================================

/**
 * Return type for the useCameraDeleteRestore hook
 */
export interface UseCameraDeleteRestoreReturn {
  /** Mutation for soft-deleting a camera */
  deleteMutation: UseDeleteCameraMutationReturn['deleteMutation'];
  /** Mutation for restoring a soft-deleted camera */
  restoreMutation: UseRestoreCameraMutationReturn['restoreMutation'];
}

/**
 * Convenience hook combining delete and restore mutations.
 *
 * Use this when you need both delete and restore functionality in the same component.
 *
 * @returns Object containing both delete and restore mutations
 *
 * @example
 * ```tsx
 * const { deleteMutation, restoreMutation } = useCameraDeleteRestore();
 *
 * // In a camera list item
 * <button onClick={() => deleteMutation.mutate(camera.id)}>Delete</button>
 *
 * // In a deleted camera list item
 * <button onClick={() => restoreMutation.mutate(camera.id)}>Restore</button>
 * ```
 */
export function useCameraDeleteRestore(): UseCameraDeleteRestoreReturn {
  const { deleteMutation } = useDeleteCameraMutation();
  const { restoreMutation } = useRestoreCameraMutation();

  return { deleteMutation, restoreMutation };
}
