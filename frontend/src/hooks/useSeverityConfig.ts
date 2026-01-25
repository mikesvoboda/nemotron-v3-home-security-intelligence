/**
 * useSeverityConfig - TanStack Query hook for severity thresholds
 *
 * This hook fetches severity threshold configuration from the backend API
 * and provides dynamic thresholds for risk level classification.
 *
 * Benefits:
 * - Automatic request deduplication (multiple components share one request)
 * - Built-in caching with 5-minute stale time (thresholds rarely change)
 * - Background refetching on window focus
 * - Fallback to default thresholds if API unavailable
 *
 * @module hooks/useSeverityConfig
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchSeverityMetadata } from '../services/api';
import { queryKeys, STATIC_STALE_TIME } from '../services/queryClient';
import {
  DEFAULT_SEVERITY_DEFINITIONS,
  DEFAULT_SEVERITY_THRESHOLDS,
} from '../types/severity';

import type {
  SeverityDefinition,
  SeverityLevel,
  SeverityMetadata,
  SeverityThresholds,
} from '../types/severity';

/**
 * Options for configuring the useSeverityConfig hook.
 */
export interface UseSeverityConfigOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false (rely on stale time and manual refresh)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * Data older than this will be refetched in the background.
   * @default STATIC_STALE_TIME (5 minutes)
   */
  staleTime?: number;
}

/**
 * Return type for the useSeverityConfig hook.
 */
export interface UseSeverityConfigReturn {
  /** Complete severity metadata from API, undefined if not yet fetched */
  data: SeverityMetadata | undefined;
  /** Current severity thresholds (falls back to defaults if not loaded) */
  thresholds: SeverityThresholds;
  /** Severity definitions (falls back to defaults if not loaded) */
  definitions: SeverityDefinition[];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the data is stale */
  isStale: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /**
   * Convert a risk score to a risk level using the current thresholds.
   * This function respects dynamically configured thresholds from the backend.
   * @param score - Risk score between 0-100
   * @returns The risk level ('low', 'medium', 'high', or 'critical')
   * @throws Error if score is outside 0-100 range
   */
  getRiskLevel: (score: number) => SeverityLevel;
}

/**
 * Hook to fetch severity configuration using TanStack Query.
 *
 * This hook fetches from GET /api/system/severity and provides:
 * - Automatic caching and request deduplication
 * - Derived thresholds with fallback to defaults
 * - A getRiskLevel function that uses dynamic thresholds
 *
 * @param options - Configuration options
 * @returns Severity configuration and query state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { thresholds, getRiskLevel, isLoading } = useSeverityConfig();
 *
 * if (isLoading) return <Spinner />;
 *
 * const level = getRiskLevel(75); // Returns 'high' with default thresholds
 * ```
 *
 * @example
 * ```tsx
 * // Access definitions for UI
 * const { definitions } = useSeverityConfig();
 *
 * return (
 *   <div>
 *     {definitions.map(def => (
 *       <span key={def.severity} style={{ color: def.color }}>
 *         {def.label}: {def.min_score}-{def.max_score}
 *       </span>
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useSeverityConfig(
  options: UseSeverityConfigOptions = {}
): UseSeverityConfigReturn {
  const { enabled = true, refetchInterval = false, staleTime = STATIC_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.system.severity,
    queryFn: fetchSeverityMetadata,
    enabled,
    refetchInterval,
    staleTime,
    // Disable retry for config endpoints to fail fast
    retry: 1,
    // Keep previous data while refetching for smooth UX
    placeholderData: (previousData) => previousData,
  });

  // Derive thresholds with fallback to defaults
  const thresholds = useMemo((): SeverityThresholds => {
    return query.data?.thresholds ?? DEFAULT_SEVERITY_THRESHOLDS;
  }, [query.data?.thresholds]);

  // Derive definitions with fallback to defaults
  const definitions = useMemo((): SeverityDefinition[] => {
    return query.data?.definitions ?? DEFAULT_SEVERITY_DEFINITIONS;
  }, [query.data?.definitions]);

  // Create getRiskLevel function using current thresholds
  const getRiskLevel = useMemo(() => {
    return (score: number): SeverityLevel => {
      if (score < 0 || score > 100) {
        throw new Error('Risk score must be between 0 and 100');
      }

      if (score <= thresholds.low_max) return 'low';
      if (score <= thresholds.medium_max) return 'medium';
      if (score <= thresholds.high_max) return 'high';
      return 'critical';
    };
  }, [thresholds]);

  return {
    data: query.data,
    thresholds,
    definitions,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isStale: query.isStale,
    refetch: query.refetch,
    getRiskLevel,
  };
}

export default useSeverityConfig;
