/**
 * Hook for fetching enrichment data for a specific detection using TanStack Query.
 *
 * Fetches structured enrichment results from the backend enrichment endpoint,
 * which contains results from the 18+ vision models run during detection processing.
 *
 * Uses TanStack Query for:
 * - Automatic caching (5 minutes stale time)
 * - Background refetching
 * - Deduplication of concurrent requests
 * - Optimistic updates and cache invalidation
 *
 * @module hooks/useDetectionEnrichment
 */

import { useQuery } from '@tanstack/react-query';
import { useCallback } from 'react';

import { fetchDetectionEnrichment, type EnrichmentResponse } from '../services/api';
import { queryKeys, STATIC_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for the useDetectionEnrichment hook.
 */
export interface UseDetectionEnrichmentOptions {
  /** Whether to enable data fetching. Defaults to true when detectionId is provided. */
  enabled?: boolean;
}

/**
 * Return type for the useDetectionEnrichment hook.
 * Maintains backward compatibility with the previous useState/useEffect implementation.
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

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Query key factory for detection enrichment queries.
 *
 * Provides type-safe, hierarchical cache keys that enable:
 * - Granular cache invalidation
 * - Consistent key structure
 *
 * @example
 * // Invalidate all enrichment queries
 * queryClient.invalidateQueries({ queryKey: detectionEnrichmentKeys.all });
 *
 * // Invalidate specific detection enrichment
 * queryClient.invalidateQueries({ queryKey: detectionEnrichmentKeys.detail(123) });
 */
export const detectionEnrichmentKeys = {
  /** Base key for all enrichment queries - use for bulk invalidation */
  all: ['detectionEnrichment'] as const,
  /** Single detection enrichment by ID */
  detail: (detectionId: number) => [...detectionEnrichmentKeys.all, 'detail', detectionId] as const,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for fetching and managing enrichment data for a detection.
 *
 * Uses TanStack Query with a 5-minute stale time (STATIC_STALE_TIME) since
 * enrichment data doesn't change once computed.
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
 *
 * @example
 * // Conditional fetching
 * const { data, isLoading } = useDetectionEnrichment(detectionId, {
 *   enabled: isDetailsPanelOpen,
 * });
 */
export function useDetectionEnrichment(
  detectionId: number | null | undefined,
  options?: UseDetectionEnrichmentOptions
): UseDetectionEnrichmentReturn {
  // Determine if fetching is enabled
  const enabled =
    (options?.enabled ?? true) && detectionId !== null && detectionId !== undefined;

  // Safe to cast since enabled guards against null/undefined
  const safeDetectionId = detectionId ?? 0;

  const query = useQuery({
    // Use query keys from queryClient for consistency with the rest of the app
    queryKey: queryKeys.detections.enrichment(safeDetectionId),
    queryFn: () => fetchDetectionEnrichment(safeDetectionId),
    enabled,
    // Enrichment data doesn't change once computed, so use longer cache time
    staleTime: STATIC_STALE_TIME, // 5 minutes
    // Don't retry too aggressively for enrichment data (optional, missing data is fine)
    retry: 1,
  });

  // Wrap refetch to maintain the original async signature
  const refetch = useCallback(async (): Promise<void> => {
    if (detectionId !== null && detectionId !== undefined) {
      await query.refetch();
    }
  }, [detectionId, query]);

  // Transform the query result to maintain backward compatibility
  // The previous implementation returned null for data when not loaded
  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    // Transform Error to string for backward compatibility
    error: query.error ? (query.error.message || 'Failed to fetch enrichment data') : null,
    refetch,
  };
}

export type { EnrichmentResponse };
