/**
 * Hook for fetching enrichment data for a specific detection.
 *
 * Fetches structured enrichment results from the backend enrichment endpoint,
 * which contains results from the 18+ vision models run during detection processing.
 */

import { useCallback, useEffect, useState } from 'react';

import { fetchDetectionEnrichment, type EnrichmentResponse } from '../services/api';

/**
 * Options for the useDetectionEnrichment hook.
 */
export interface UseDetectionEnrichmentOptions {
  /** Whether to enable data fetching. Defaults to true when detectionId is provided. */
  enabled?: boolean;
}

/**
 * Return type for the useDetectionEnrichment hook.
 */
export interface UseDetectionEnrichmentReturn {
  /** The enrichment data, or null if not loaded or loading */
  data: EnrichmentResponse | null;
  /** Whether the data is currently being fetched */
  isLoading: boolean;
  /** Error message if the fetch failed, null otherwise */
  error: string | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<void>;
}

/**
 * Hook for fetching and managing enrichment data for a detection.
 *
 * @param detectionId - The detection ID to fetch enrichment for, or null/undefined to skip
 * @param options - Optional configuration
 * @returns Hook state with data, loading, error, and refetch function
 *
 * @example
 * ```tsx
 * const { data, isLoading, error, refetch } = useDetectionEnrichment(123);
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <ErrorMessage error={error} />;
 * if (data) return <EnrichmentPanel enrichment_data={data} />;
 * ```
 */
export function useDetectionEnrichment(
  detectionId: number | null | undefined,
  options?: UseDetectionEnrichmentOptions
): UseDetectionEnrichmentReturn {
  const [data, setData] = useState<EnrichmentResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Determine if fetching is enabled
  const enabled = options?.enabled ?? true;
  const shouldFetch = enabled && detectionId !== null && detectionId !== undefined;

  const fetchData = useCallback(async () => {
    if (detectionId === null || detectionId === undefined) {
      setData(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const enrichmentData = await fetchDetectionEnrichment(detectionId);
      setData(enrichmentData);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch enrichment data';
      setError(errorMessage);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [detectionId]);

  // Fetch data when detectionId changes or enabled changes
  useEffect(() => {
    if (shouldFetch) {
      void fetchData();
    } else {
      // Reset state when disabled or no detectionId
      setData(null);
      setIsLoading(false);
      setError(null);
    }
  }, [shouldFetch, fetchData]);

  const refetch = useCallback(async () => {
    if (detectionId !== null && detectionId !== undefined) {
      await fetchData();
    }
  }, [detectionId, fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch,
  };
}

export type { EnrichmentResponse };
