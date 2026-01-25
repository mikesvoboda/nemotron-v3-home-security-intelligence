/**
 * Optimistic Updates Utilities (NEM-3361)
 *
 * Provides reusable utilities and patterns for implementing optimistic updates
 * with TanStack Query mutations.
 *
 * ## Architecture
 *
 * Optimistic updates follow a three-phase pattern:
 * 1. **onMutate**: Cancel outgoing queries, snapshot current data, apply optimistic update
 * 2. **onError**: Rollback to snapshot on failure
 * 3. **onSettled**: Invalidate queries to ensure consistency with server
 *
 * @see https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates
 * @module services/optimisticUpdates
 */

import type { QueryClient } from '@tanstack/react-query';

// ============================================================================
// Types
// ============================================================================

/**
 * Context returned from onMutate for rollback support
 */
export interface OptimisticContext<T> {
  /** Snapshot of data before optimistic update for rollback */
  previousData: T | undefined;
  /** ID of the optimistically updated/created item */
  optimisticId?: string | number;
}

/**
 * Generic item type with ID
 */
export interface ItemWithId {
  id: string | number;
  [key: string]: unknown;
}

// ============================================================================
// List Operation Helpers
// ============================================================================

/**
 * Optimistically add an item to a list.
 *
 * @param queryClient - TanStack Query client
 * @param queryKey - Query key for the list
 * @param newItem - Item to add
 * @param position - Where to add the item ('start' or 'end')
 * @returns Previous data for rollback
 *
 * @example
 * ```tsx
 * onMutate: async (newItemData) => {
 *   await queryClient.cancelQueries({ queryKey });
 *   const previousData = optimisticAddToList(
 *     queryClient,
 *     queryKey,
 *     { id: `temp-${Date.now()}`, ...newItemData },
 *     'end'
 *   );
 *   return { previousData };
 * }
 * ```
 */
export function optimisticAddToList<T extends ItemWithId>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  newItem: T,
  position: 'start' | 'end' = 'end'
): T[] | undefined {
  const previousData = queryClient.getQueryData<T[]>(queryKey);

  queryClient.setQueryData<T[]>(queryKey, (old) => {
    if (!old) return [newItem];
    return position === 'start' ? [newItem, ...old] : [...old, newItem];
  });

  return previousData;
}

/**
 * Optimistically update an item in a list.
 *
 * @param queryClient - TanStack Query client
 * @param queryKey - Query key for the list
 * @param id - ID of the item to update
 * @param updates - Partial updates to apply
 * @returns Previous data for rollback
 *
 * @example
 * ```tsx
 * onMutate: async ({ id, updates }) => {
 *   await queryClient.cancelQueries({ queryKey });
 *   const previousData = optimisticUpdateInList(
 *     queryClient,
 *     queryKey,
 *     id,
 *     updates
 *   );
 *   return { previousData };
 * }
 * ```
 */
export function optimisticUpdateInList<T extends ItemWithId>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  id: string | number,
  updates: Partial<T>
): T[] | undefined {
  const previousData = queryClient.getQueryData<T[]>(queryKey);

  queryClient.setQueryData<T[]>(queryKey, (old) => {
    if (!old) return old;
    return old.map((item) => (item.id === id ? { ...item, ...updates } : item));
  });

  return previousData;
}

/**
 * Optimistically remove an item from a list.
 *
 * @param queryClient - TanStack Query client
 * @param queryKey - Query key for the list
 * @param id - ID of the item to remove
 * @returns Previous data for rollback
 *
 * @example
 * ```tsx
 * onMutate: async (id) => {
 *   await queryClient.cancelQueries({ queryKey });
 *   const previousData = optimisticRemoveFromList(
 *     queryClient,
 *     queryKey,
 *     id
 *   );
 *   return { previousData };
 * }
 * ```
 */
export function optimisticRemoveFromList<T extends ItemWithId>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  id: string | number
): T[] | undefined {
  const previousData = queryClient.getQueryData<T[]>(queryKey);

  queryClient.setQueryData<T[]>(queryKey, (old) => {
    if (!old) return old;
    return old.filter((item) => item.id !== id);
  });

  return previousData;
}

/**
 * Replace optimistic item with real data after mutation success.
 *
 * @param queryClient - TanStack Query client
 * @param queryKey - Query key for the list
 * @param optimisticId - ID of the optimistic item to replace
 * @param realItem - Real item from server response
 */
export function replaceOptimisticItem<T extends ItemWithId>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  optimisticId: string | number,
  realItem: T
): void {
  queryClient.setQueryData<T[]>(queryKey, (old) => {
    if (!old) return [realItem];
    return old.map((item) => (item.id === optimisticId ? realItem : item));
  });
}

// ============================================================================
// Single Item Operation Helpers
// ============================================================================

/**
 * Optimistically update a single cached item.
 *
 * @param queryClient - TanStack Query client
 * @param queryKey - Query key for the item
 * @param updates - Partial updates to apply
 * @returns Previous data for rollback
 */
export function optimisticUpdateSingle<T>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  updates: Partial<T>
): T | undefined {
  const previousData = queryClient.getQueryData<T>(queryKey);

  queryClient.setQueryData<T>(queryKey, (old) => {
    if (!old) return old;
    return { ...old, ...updates };
  });

  return previousData;
}

// ============================================================================
// Rollback Helpers
// ============================================================================

/**
 * Rollback a list query to its previous state.
 *
 * @param queryClient - TanStack Query client
 * @param queryKey - Query key for the list
 * @param previousData - Snapshot of data before optimistic update
 */
export function rollbackList<T>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  previousData: T[] | undefined
): void {
  if (previousData !== undefined) {
    queryClient.setQueryData(queryKey, previousData);
  }
}

/**
 * Rollback a single item query to its previous state.
 *
 * @param queryClient - TanStack Query client
 * @param queryKey - Query key for the item
 * @param previousData - Snapshot of data before optimistic update
 */
export function rollbackSingle<T>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  previousData: T | undefined
): void {
  if (previousData !== undefined) {
    queryClient.setQueryData(queryKey, previousData);
  }
}

// ============================================================================
// Mutation Lifecycle Helpers
// ============================================================================

/**
 * Cancel all outgoing queries for a query key.
 * Call this at the start of onMutate to prevent race conditions.
 *
 * @param queryClient - TanStack Query client
 * @param queryKey - Query key (or partial key for bulk cancellation)
 */
export async function cancelOutgoingQueries(
  queryClient: QueryClient,
  queryKey: readonly unknown[]
): Promise<void> {
  await queryClient.cancelQueries({ queryKey });
}

/**
 * Invalidate queries after mutation settlement.
 * Call this in onSettled to ensure data consistency.
 *
 * @param queryClient - TanStack Query client
 * @param queryKeys - Array of query keys to invalidate
 */
export function invalidateQueries(queryClient: QueryClient, queryKeys: readonly unknown[][]): void {
  for (const queryKey of queryKeys) {
    void queryClient.invalidateQueries({ queryKey });
  }
}

// ============================================================================
// Typed Mutation Config Factories
// ============================================================================

/**
 * Create mutation config for optimistic list additions.
 *
 * @param queryClient - TanStack Query client
 * @param listQueryKey - Query key for the list
 * @param createOptimisticItem - Function to create optimistic item from variables
 * @param additionalInvalidations - Additional query keys to invalidate on settlement
 * @returns Mutation config object
 *
 * @example
 * ```tsx
 * const addMutationConfig = createOptimisticAddConfig<Camera, CameraCreate>(
 *   queryClient,
 *   queryKeys.cameras.list(),
 *   (data) => ({
 *     id: `temp-${Date.now()}`,
 *     name: data.name,
 *     status: 'online',
 *     created_at: new Date().toISOString(),
 *   }),
 *   [queryKeys.cameras.all]
 * );
 * ```
 */
export function createOptimisticAddConfig<T extends ItemWithId, TVariables>(
  queryClient: QueryClient,
  listQueryKey: readonly unknown[],
  createOptimisticItem: (variables: TVariables) => T,
  additionalInvalidations: readonly unknown[][] = []
) {
  return {
    onMutate: async (variables: TVariables) => {
      await cancelOutgoingQueries(queryClient, listQueryKey);
      const optimisticItem = createOptimisticItem(variables);
      const previousData = optimisticAddToList(queryClient, listQueryKey, optimisticItem);
      return { previousData, optimisticId: optimisticItem.id };
    },
    onError: (
      _error: Error,
      _variables: TVariables,
      context: OptimisticContext<T[]> | undefined
    ) => {
      if (context?.previousData) {
        rollbackList(queryClient, listQueryKey, context.previousData);
      }
    },
    onSuccess: (data: T, _variables: TVariables, context: OptimisticContext<T[]> | undefined) => {
      if (context?.optimisticId) {
        replaceOptimisticItem(queryClient, listQueryKey, context.optimisticId, data);
      }
    },
    onSettled: () => {
      invalidateQueries(queryClient, [
        listQueryKey as unknown[],
        ...(additionalInvalidations as unknown[][]),
      ]);
    },
  };
}

/**
 * Create mutation config for optimistic list updates.
 *
 * @param queryClient - TanStack Query client
 * @param listQueryKey - Query key for the list
 * @param getIdFromVariables - Function to extract item ID from variables
 * @param getUpdatesFromVariables - Function to extract updates from variables
 * @param additionalInvalidations - Additional query keys to invalidate on settlement
 * @returns Mutation config object
 */
export function createOptimisticUpdateConfig<T extends ItemWithId, TVariables>(
  queryClient: QueryClient,
  listQueryKey: readonly unknown[],
  getIdFromVariables: (variables: TVariables) => string | number,
  getUpdatesFromVariables: (variables: TVariables) => Partial<T>,
  additionalInvalidations: readonly unknown[][] = []
) {
  return {
    onMutate: async (variables: TVariables) => {
      await cancelOutgoingQueries(queryClient, listQueryKey);
      const id = getIdFromVariables(variables);
      const updates = getUpdatesFromVariables(variables);
      const previousData = optimisticUpdateInList<T>(queryClient, listQueryKey, id, updates);
      return { previousData };
    },
    onError: (
      _error: Error,
      _variables: TVariables,
      context: OptimisticContext<T[]> | undefined
    ) => {
      if (context?.previousData) {
        rollbackList(queryClient, listQueryKey, context.previousData);
      }
    },
    onSettled: () => {
      invalidateQueries(queryClient, [
        listQueryKey as unknown[],
        ...(additionalInvalidations as unknown[][]),
      ]);
    },
  };
}

/**
 * Create mutation config for optimistic list deletions.
 *
 * @param queryClient - TanStack Query client
 * @param listQueryKey - Query key for the list
 * @param getIdFromVariables - Function to extract item ID from variables
 * @param getDetailQueryKey - Optional function to get detail query key for removal
 * @param additionalInvalidations - Additional query keys to invalidate on settlement
 * @returns Mutation config object
 */
export function createOptimisticDeleteConfig<T extends ItemWithId, TVariables>(
  queryClient: QueryClient,
  listQueryKey: readonly unknown[],
  getIdFromVariables: (variables: TVariables) => string | number,
  getDetailQueryKey?: (id: string | number) => readonly unknown[],
  additionalInvalidations: readonly unknown[][] = []
) {
  return {
    onMutate: async (variables: TVariables) => {
      await cancelOutgoingQueries(queryClient, listQueryKey);
      const id = getIdFromVariables(variables);
      const previousData = optimisticRemoveFromList<T>(queryClient, listQueryKey, id);
      return { previousData };
    },
    onError: (
      _error: Error,
      _variables: TVariables,
      context: OptimisticContext<T[]> | undefined
    ) => {
      if (context?.previousData) {
        rollbackList(queryClient, listQueryKey, context.previousData);
      }
    },
    onSettled: (_data: unknown, _error: Error | null, variables: TVariables) => {
      const keysToInvalidate = [
        listQueryKey as unknown[],
        ...(additionalInvalidations as unknown[][]),
      ];
      if (getDetailQueryKey) {
        const id = getIdFromVariables(variables);
        queryClient.removeQueries({ queryKey: getDetailQueryKey(id) });
      }
      invalidateQueries(queryClient, keysToInvalidate);
    },
  };
}
