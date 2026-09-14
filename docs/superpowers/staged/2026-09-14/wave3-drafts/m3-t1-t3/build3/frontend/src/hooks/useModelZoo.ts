/**
 * TanStack Query hooks for Model Zoo management
 *
 * This module provides hooks for fetching and mutating Model Zoo data
 * using TanStack Query. It includes:
 *
 * Queries:
 * - useModels: Fetch model list with runtime state
 * - useVRAMSummary: Fetch per-GPU VRAM breakdown
 *
 * Mutations:
 * - useLoadModel: Load a model into GPU memory
 * - useUnloadModel: Unload a model from GPU memory
 * - useReloadModel: Reload a model (unload + load)
 * - useUnloadAllModels: Unload all models
 *
 * @module hooks/useModelZoo
 * @see docs/plans/2025-01-31-model-zoo-management-design.md - Design document
 * @see NEM-4788 - TDD tests for frontend
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import * as modelZooApi from '../services/modelZooApi';
import { REALTIME_STALE_TIME } from '../services/queryClient';

import type {
  ModelListResponse,
  ModelStatus,
  VRAMSummaryResponse,
  LoadModelResponse,
  UnloadModelResponse,
  UnloadAllResponse,
  ServiceHealthStatus,
  GpuVRAMInfo,
} from '../services/modelZooApi';

// Re-export types for convenience
export type {
  ModelListResponse,
  ModelStatus,
  ModelRuntime,
  VRAMSummaryResponse,
  GpuVRAMInfo,
  VRAMTotals,
  LoadModelResponse,
  UnloadModelResponse,
  UnloadAllResponse,
  ServiceHealthStatus,
} from '../services/modelZooApi';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query keys for Model Zoo queries.
 * Follows the hierarchical pattern for cache invalidation.
 */
export const MODEL_ZOO_QUERY_KEYS = {
  /** Base key for all model zoo queries - use for bulk invalidation */
  all: ['system', 'models'] as const,
  /** Model list with runtime state */
  models: ['system', 'models', 'list'] as const,
  /** VRAM summary per GPU */
  vramSummary: ['system', 'models', 'vram-summary'] as const,
  /** Individual model status */
  model: (name: string) => ['system', 'models', 'detail', name] as const,
} as const;

// ============================================================================
// useModels - Fetch model list with runtime state
// ============================================================================

/**
 * Options for configuring the useModels hook.
 */
export interface UseModelsOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * @default 5000 (5 seconds)
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useModels hook.
 */
export interface UseModelsReturn {
  /** Full response data */
  data: ModelListResponse | undefined;
  /** List of models (convenience accessor) */
  models: ModelStatus[];
  /** Service health status map */
  serviceStatus: Record<string, ServiceHealthStatus>;
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
 * Hook to fetch model list with runtime state using TanStack Query.
 *
 * Returns all models from both enrichment services combined with their
 * static configuration and current runtime state.
 *
 * @param options - Configuration options
 * @returns Models and query state
 *
 * @example
 * ```tsx
 * const { models, isLoading, error } = useModels();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * const loadedModels = models.filter(m => m.runtime?.loaded);
 * return <ModelList models={loadedModels} />;
 * ```
 */
export function useModels(options: UseModelsOptions = {}): UseModelsReturn {
  const { enabled = true, staleTime = REALTIME_STALE_TIME, refetchInterval = 5000 } = options;

  const query = useQuery({
    queryKey: MODEL_ZOO_QUERY_KEYS.models,
    queryFn: modelZooApi.listModels,
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    models: query.data?.models ?? [],
    serviceStatus: query.data?.service_status ?? {},
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useVRAMSummary - Fetch VRAM usage per GPU
// ============================================================================

/**
 * Options for configuring the useVRAMSummary hook.
 */
export interface UseVRAMSummaryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * @default 5000 (5 seconds)
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useVRAMSummary hook.
 */
export interface UseVRAMSummaryReturn {
  /** Full response data */
  data: VRAMSummaryResponse | undefined;
  /** Per-GPU VRAM info (convenience accessor) */
  gpus: GpuVRAMInfo[];
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
 * Hook to fetch VRAM summary per GPU using TanStack Query.
 *
 * Returns detailed VRAM breakdown for each GPU including budget,
 * usage, and currently loaded models.
 *
 * @param options - Configuration options
 * @returns VRAM summary and query state
 *
 * @example
 * ```tsx
 * const { gpus, data, isLoading } = useVRAMSummary();
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     {gpus.map(gpu => (
 *       <VRAMBar key={gpu.gpu_id} {...gpu} />
 *     ))}
 *     <p>Total: {data?.totals.used_mb}/{data?.totals.budget_mb} MB</p>
 *   </div>
 * );
 * ```
 */
export function useVRAMSummary(options: UseVRAMSummaryOptions = {}): UseVRAMSummaryReturn {
  const { enabled = true, staleTime = REALTIME_STALE_TIME, refetchInterval = 5000 } = options;

  const query = useQuery({
    queryKey: MODEL_ZOO_QUERY_KEYS.vramSummary,
    queryFn: modelZooApi.getVRAMSummary,
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    gpus: query.data?.gpus ?? [],
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useLoadModel - Load a model into GPU memory
// ============================================================================

/**
 * Return type for the useLoadModel hook.
 */
export interface UseLoadModelReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<LoadModelResponse, Error, string>>;
  /** Convenience method to load a model */
  loadModel: (modelName: string) => Promise<LoadModelResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for loading a model into GPU memory.
 *
 * Automatically invalidates the models and VRAM summary queries on success.
 *
 * @returns Mutation for loading a model
 *
 * @example
 * ```tsx
 * const { loadModel, isLoading, error } = useLoadModel();
 *
 * const handleLoad = async (modelName: string) => {
 *   try {
 *     const result = await loadModel(modelName);
 *     toast.success(`Loaded in ${result.load_time_ms}ms`);
 *   } catch (e) {
 *     toast.error(`Failed to load: ${e.message}`);
 *   }
 * };
 * ```
 */
export function useLoadModel(): UseLoadModelReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: modelZooApi.loadModel,
    onSuccess: () => {
      // Invalidate both queries to reflect new state
      void queryClient.invalidateQueries({
        queryKey: MODEL_ZOO_QUERY_KEYS.all,
      });
    },
  });

  return {
    mutation,
    loadModel: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useUnloadModel - Unload a model from GPU memory
// ============================================================================

/**
 * Return type for the useUnloadModel hook.
 */
export interface UseUnloadModelReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<UnloadModelResponse, Error, string>>;
  /** Convenience method to unload a model */
  unloadModel: (modelName: string) => Promise<UnloadModelResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for unloading a model from GPU memory.
 *
 * Automatically invalidates the models and VRAM summary queries on success.
 *
 * @returns Mutation for unloading a model
 *
 * @example
 * ```tsx
 * const { unloadModel, isLoading } = useUnloadModel();
 *
 * const handleUnload = async (modelName: string) => {
 *   const result = await unloadModel(modelName);
 *   toast.info(`Freed ${result.freed_vram_mb}MB VRAM`);
 * };
 * ```
 */
export function useUnloadModel(): UseUnloadModelReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: modelZooApi.unloadModel,
    onSuccess: () => {
      // Invalidate both queries to reflect new state
      void queryClient.invalidateQueries({
        queryKey: MODEL_ZOO_QUERY_KEYS.all,
      });
    },
  });

  return {
    mutation,
    unloadModel: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useReloadModel - Reload a model (unload + load)
// ============================================================================

/**
 * Return type for the useReloadModel hook.
 */
export interface UseReloadModelReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<LoadModelResponse, Error, string>>;
  /** Convenience method to reload a model */
  reloadModel: (modelName: string) => Promise<LoadModelResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for reloading a model (unload + load).
 *
 * Automatically invalidates the models and VRAM summary queries on success.
 *
 * @returns Mutation for reloading a model
 *
 * @example
 * ```tsx
 * const { reloadModel, isLoading } = useReloadModel();
 *
 * const handleReload = async (modelName: string) => {
 *   const result = await reloadModel(modelName);
 *   toast.success(`Reloaded in ${result.load_time_ms}ms`);
 * };
 * ```
 */
export function useReloadModel(): UseReloadModelReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: modelZooApi.reloadModel,
    onSuccess: () => {
      // Invalidate both queries to reflect new state
      void queryClient.invalidateQueries({
        queryKey: MODEL_ZOO_QUERY_KEYS.all,
      });
    },
  });

  return {
    mutation,
    reloadModel: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useUnloadAllModels - Unload all models
// ============================================================================

/**
 * Return type for the useUnloadAllModels hook.
 */
export interface UseUnloadAllModelsReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<UnloadAllResponse, Error, void>>;
  /** Convenience method to unload all models */
  unloadAll: () => Promise<UnloadAllResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for unloading all models from all GPUs.
 *
 * Automatically invalidates the models and VRAM summary queries on success.
 *
 * @returns Mutation for unloading all models
 *
 * @example
 * ```tsx
 * const { unloadAll, isLoading } = useUnloadAllModels();
 *
 * const handleUnloadAll = async () => {
 *   const result = await unloadAll();
 *   toast.info(`Unloaded ${result.unloaded_count} models`);
 * };
 * ```
 */
export function useUnloadAllModels(): UseUnloadAllModelsReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: modelZooApi.unloadAllModels,
    onSuccess: () => {
      // Invalidate both queries to reflect new state
      void queryClient.invalidateQueries({
        queryKey: MODEL_ZOO_QUERY_KEYS.all,
      });
    },
  });

  return {
    mutation,
    unloadAll: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}
