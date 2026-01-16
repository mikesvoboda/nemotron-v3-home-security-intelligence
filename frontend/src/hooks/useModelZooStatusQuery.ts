/**
 * useModelZooStatusQuery - TanStack Query hooks for Model Zoo status
 *
 * This module provides hooks for fetching AI Model Zoo status using TanStack Query.
 * It replaces the manual polling implementation in useModelZooStatus with
 * automatic caching, deduplication, and background refetching.
 *
 * Benefits over the original useModelZooStatus:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching with refetchInterval
 * - DevTools integration for debugging
 *
 * @module hooks/useModelZooStatusQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchModelZooStatus,
  type ModelRegistryResponse,
  type ModelStatusResponse,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * VRAM statistics derived from the Model Zoo registry.
 */
export interface VRAMStats {
  /** Total VRAM budget in MB */
  budgetMb: number;
  /** Currently used VRAM in MB */
  usedMb: number;
  /** Available VRAM in MB */
  availableMb: number;
  /** Usage percentage (0-100) */
  usagePercent: number;
}

// ============================================================================
// useModelZooStatusQuery
// ============================================================================

/**
 * Options for configuring the useModelZooStatusQuery hook
 */
export interface UseModelZooStatusQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default 10000 (10 seconds)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useModelZooStatusQuery hook
 */
export interface UseModelZooStatusQueryReturn {
  /** Raw registry response, undefined if not yet fetched */
  data: ModelRegistryResponse | undefined;
  /** List of all models in the registry */
  models: ModelStatusResponse[];
  /** Calculated VRAM statistics */
  vramStats: VRAMStats | null;
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
 * Calculate VRAM stats from the registry response.
 */
function calculateVramStats(registry: ModelRegistryResponse): VRAMStats {
  const budget = registry.vram_budget_mb;
  const used = registry.vram_used_mb;
  const available = registry.vram_available_mb;
  const usagePercent = budget > 0 ? (used / budget) * 100 : 0;

  return {
    budgetMb: budget,
    usedMb: used,
    availableMb: available,
    usagePercent,
  };
}

/**
 * Hook to fetch Model Zoo status using TanStack Query.
 *
 * This hook fetches from GET /api/system/models and provides:
 * - List of all AI models in the Model Zoo
 * - VRAM usage statistics (budget, used, available, percentage)
 * - Automatic caching and request deduplication
 * - Configurable polling via refetchInterval
 *
 * @param options - Configuration options
 * @returns Model Zoo status and query state
 *
 * @example
 * ```tsx
 * const { models, vramStats, isLoading, error } = useModelZooStatusQuery({
 *   refetchInterval: 10000, // Poll every 10 seconds
 * });
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     <h2>VRAM Usage: {vramStats?.usagePercent.toFixed(1)}%</h2>
 *     <ul>
 *       {models.map(model => (
 *         <li key={model.name}>
 *           {model.name}: {model.status}
 *         </li>
 *       ))}
 *     </ul>
 *   </div>
 * );
 * ```
 */
export function useModelZooStatusQuery(
  options: UseModelZooStatusQueryOptions = {}
): UseModelZooStatusQueryReturn {
  const { enabled = true, refetchInterval = 10000, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.ai.modelZoo,
    queryFn: fetchModelZooStatus,
    enabled,
    refetchInterval,
    staleTime,
    retry: 2,
  });

  // Derive models list
  const models = useMemo(() => query.data?.models ?? [], [query.data?.models]);

  // Calculate VRAM stats
  const vramStats = useMemo(
    () => (query.data ? calculateVramStats(query.data) : null),
    [query.data]
  );

  return {
    data: query.data,
    models,
    vramStats,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}
