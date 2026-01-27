/**
 * useBulkDetectionMutations - TanStack Query mutation hooks for bulk detection operations
 *
 * This module provides hooks for bulk create, update, and delete operations on detections.
 * All operations support HTTP 207 Multi-Status for partial success handling.
 *
 * Key features:
 * - Automatic cache invalidation after successful operations
 * - Handles HTTP 207 responses as success (partial success pattern)
 * - Typed error handling with proper error states
 *
 * @module hooks/useBulkDetectionMutations
 */

import { useMutation } from '@tanstack/react-query';

import {
  bulkCreateDetections,
  bulkUpdateDetections,
  bulkDeleteDetections,
} from '../services/api';
import { queryKeys } from '../services/queryClient';

import type {
  BulkOperationResponse,
  DetectionBulkCreateItem,
  DetectionBulkCreateResponse,
  DetectionBulkUpdateItem,
} from '../types/bulk';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for bulk mutation hooks
 */
export interface BulkMutationOptions<TData> {
  /** Callback on successful mutation (includes partial success) */
  onSuccess?: (data: TData) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
  /** Whether to skip cache invalidation (default: false) */
  skipInvalidation?: boolean;
}

/**
 * Return type for bulk create mutations
 */
export interface UseBulkCreateDetectionsReturn {
  /** Execute the bulk create mutation */
  mutate: (detections: DetectionBulkCreateItem[]) => void;
  /** Execute the bulk create mutation and return a promise */
  mutateAsync: (detections: DetectionBulkCreateItem[]) => Promise<DetectionBulkCreateResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation errored */
  isError: boolean;
  /** Error from the mutation */
  error: Error | null;
  /** Data from successful mutation */
  data: DetectionBulkCreateResponse | undefined;
  /** Reset mutation state */
  reset: () => void;
}

/**
 * Return type for bulk update mutations
 */
export interface UseBulkUpdateDetectionsReturn {
  /** Execute the bulk update mutation */
  mutate: (detections: DetectionBulkUpdateItem[]) => void;
  /** Execute the bulk update mutation and return a promise */
  mutateAsync: (detections: DetectionBulkUpdateItem[]) => Promise<BulkOperationResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation errored */
  isError: boolean;
  /** Error from the mutation */
  error: Error | null;
  /** Data from successful mutation */
  data: BulkOperationResponse | undefined;
  /** Reset mutation state */
  reset: () => void;
}

/**
 * Return type for bulk delete mutations
 */
export interface UseBulkDeleteDetectionsReturn {
  /** Execute the bulk delete mutation */
  mutate: (detectionIds: number[]) => void;
  /** Execute the bulk delete mutation and return a promise */
  mutateAsync: (detectionIds: number[]) => Promise<BulkOperationResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation errored */
  isError: boolean;
  /** Error from the mutation */
  error: Error | null;
  /** Data from successful mutation */
  data: BulkOperationResponse | undefined;
  /** Reset mutation state */
  reset: () => void;
}

// ============================================================================
// useBulkCreateDetections
// ============================================================================

/**
 * Hook for bulk creating detections.
 *
 * Creates multiple detections in a single request. Handles HTTP 207 Multi-Status
 * responses for partial success scenarios.
 *
 * @param options - Configuration options for the mutation
 * @returns Mutation functions and state
 *
 * @example
 * ```tsx
 * function DetectionImporter() {
 *   const { mutate, isPending, data } = useBulkCreateDetections({
 *     onSuccess: (response) => {
 *       console.log(`Created ${response.succeeded} of ${response.total} detections`);
 *     },
 *   });
 *
 *   const handleImport = (detections: DetectionBulkCreateItem[]) => {
 *     mutate(detections);
 *   };
 *
 *   return (
 *     <button onClick={() => handleImport(detectionsToImport)} disabled={isPending}>
 *       {isPending ? 'Importing...' : 'Import Detections'}
 *     </button>
 *   );
 * }
 * ```
 */
export function useBulkCreateDetections(
  options: BulkMutationOptions<DetectionBulkCreateResponse> = {}
): UseBulkCreateDetectionsReturn {
  const { onSuccess, onError, skipInvalidation = false } = options;

  const mutation = useMutation({
    mutationFn: bulkCreateDetections,

    onSuccess: (data) => {
      onSuccess?.(data);
    },

    onError: (error) => {
      onError?.(error);
    },

    onSettled: (_data, _error, _variables, _context, { client }) => {
      if (!skipInvalidation) {
        // Invalidate detection queries to refetch with new data
        void client.invalidateQueries({ queryKey: queryKeys.detections.all });
      }
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}

// ============================================================================
// useBulkUpdateDetections
// ============================================================================

/**
 * Hook for bulk updating detections.
 *
 * Updates multiple detections in a single request. Only provided fields
 * will be updated for each detection.
 *
 * @param options - Configuration options for the mutation
 * @returns Mutation functions and state
 *
 * @example
 * ```tsx
 * function DetectionEditor() {
 *   const { mutate, isPending } = useBulkUpdateDetections({
 *     onSuccess: (response) => {
 *       if (response.failed > 0) {
 *         console.warn(`${response.failed} updates failed`);
 *       }
 *     },
 *   });
 *
 *   const handleCorrectLabels = (updates: DetectionBulkUpdateItem[]) => {
 *     mutate(updates);
 *   };
 *
 *   return (
 *     <button onClick={() => handleCorrectLabels(corrections)} disabled={isPending}>
 *       Apply Corrections
 *     </button>
 *   );
 * }
 * ```
 */
export function useBulkUpdateDetections(
  options: BulkMutationOptions<BulkOperationResponse> = {}
): UseBulkUpdateDetectionsReturn {
  const { onSuccess, onError, skipInvalidation = false } = options;

  const mutation = useMutation({
    mutationFn: bulkUpdateDetections,

    onSuccess: (data) => {
      onSuccess?.(data);
    },

    onError: (error) => {
      onError?.(error);
    },

    onSettled: (_data, _error, _variables, _context, { client }) => {
      if (!skipInvalidation) {
        // Invalidate detection queries to refetch with updated data
        void client.invalidateQueries({ queryKey: queryKeys.detections.all });
      }
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}

// ============================================================================
// useBulkDeleteDetections
// ============================================================================

/**
 * Hook for bulk deleting detections.
 *
 * Permanently deletes multiple detections in a single request.
 * This is a hard delete - detections cannot be recovered.
 *
 * @param options - Configuration options for the mutation
 * @returns Mutation functions and state
 *
 * @example
 * ```tsx
 * function DetectionCleanup() {
 *   const { mutate, isPending, data } = useBulkDeleteDetections({
 *     onSuccess: (response) => {
 *       console.log(`Deleted ${response.succeeded} detections`);
 *     },
 *     onError: (error) => {
 *       console.error('Delete failed:', error);
 *     },
 *   });
 *
 *   const handleDelete = (ids: number[]) => {
 *     if (confirm(`Delete ${ids.length} detections?`)) {
 *       mutate(ids);
 *     }
 *   };
 *
 *   return (
 *     <button onClick={() => handleDelete(selectedIds)} disabled={isPending}>
 *       {isPending ? 'Deleting...' : 'Delete Selected'}
 *     </button>
 *   );
 * }
 * ```
 */
export function useBulkDeleteDetections(
  options: BulkMutationOptions<BulkOperationResponse> = {}
): UseBulkDeleteDetectionsReturn {
  const { onSuccess, onError, skipInvalidation = false } = options;

  const mutation = useMutation({
    mutationFn: bulkDeleteDetections,

    onSuccess: (data) => {
      onSuccess?.(data);
    },

    onError: (error) => {
      onError?.(error);
    },

    onSettled: (_data, _error, _variables, _context, { client }) => {
      if (!skipInvalidation) {
        // Invalidate detection queries to refetch without deleted items
        void client.invalidateQueries({ queryKey: queryKeys.detections.all });
      }
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}
