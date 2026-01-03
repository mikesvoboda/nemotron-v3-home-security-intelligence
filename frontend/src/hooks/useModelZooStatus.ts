import { useState, useEffect, useCallback, useRef } from 'react';

import { fetchModelZooStatus, type ModelRegistryResponse, type ModelStatusResponse } from '../services/api';

/**
 * VRAM statistics derived from the Model Zoo registry.
 */
export interface VRAMStats {
  /** Total VRAM budget in MB */
  budget_mb: number;
  /** Currently used VRAM in MB */
  used_mb: number;
  /** Available VRAM in MB */
  available_mb: number;
  /** Usage percentage (0-100) */
  usage_percent: number;
}

/**
 * Options for the useModelZooStatus hook.
 */
export interface UseModelZooStatusOptions {
  /**
   * Polling interval in milliseconds.
   * Set to 0 to disable polling (default: 10000 = 10 seconds).
   */
  pollingInterval?: number;
}

/**
 * Return type for the useModelZooStatus hook.
 */
export interface UseModelZooStatusReturn {
  /** List of all models in the registry */
  models: ModelStatusResponse[];
  /** Calculated VRAM statistics */
  vramStats: VRAMStats | null;
  /** Loading state */
  isLoading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Manual refresh function */
  refresh: () => Promise<void>;
}

/**
 * useModelZooStatus - Hook for fetching and polling Model Zoo status
 *
 * Polls the /api/system/models endpoint at regular intervals and provides:
 * - List of all AI models in the Model Zoo
 * - VRAM usage statistics (budget, used, available, percentage)
 * - Loading and error states
 * - Manual refresh capability
 *
 * @example
 * ```tsx
 * const { models, vramStats, isLoading, error, refresh } = useModelZooStatus({
 *   pollingInterval: 10000, // Poll every 10 seconds
 * });
 * ```
 */
export function useModelZooStatus(
  options: UseModelZooStatusOptions = {}
): UseModelZooStatusReturn {
  const { pollingInterval = 10000 } = options;

  const [models, setModels] = useState<ModelStatusResponse[]>([]);
  const [vramStats, setVramStats] = useState<VRAMStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /**
   * Calculate VRAM stats from the registry response.
   */
  const calculateVramStats = useCallback((registry: ModelRegistryResponse): VRAMStats => {
    const budget = registry.vram_budget_mb;
    const used = registry.vram_used_mb;
    const available = registry.vram_available_mb;
    const usagePercent = budget > 0 ? (used / budget) * 100 : 0;

    return {
      budget_mb: budget,
      used_mb: used,
      available_mb: available,
      usage_percent: usagePercent,
    };
  }, []);

  /**
   * Fetch model zoo status from the API.
   */
  const fetchStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const registry = await fetchModelZooStatus();
      setModels(registry.models);
      setVramStats(calculateVramStats(registry));
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch Model Zoo status';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [calculateVramStats]);

  /**
   * Manual refresh function.
   */
  const refresh = useCallback(async () => {
    await fetchStatus();
  }, [fetchStatus]);

  // Initial fetch and polling setup
  useEffect(() => {
    // Clear existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Fetch immediately
    void fetchStatus();

    // Set up polling if enabled
    if (pollingInterval > 0) {
      intervalRef.current = setInterval(() => {
        void fetchStatus();
      }, pollingInterval);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [pollingInterval, fetchStatus]);

  return {
    models,
    vramStats,
    isLoading,
    error,
    refresh,
  };
}
