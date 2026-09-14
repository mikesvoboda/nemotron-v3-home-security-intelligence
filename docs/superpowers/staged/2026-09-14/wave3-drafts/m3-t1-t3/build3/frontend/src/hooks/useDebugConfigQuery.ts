/**
 * useDebugConfigQuery - TanStack Query hook for fetching application configuration
 *
 * This hook fetches the debug configuration from GET /api/debug/config
 * and provides the config key-value pairs for display in the Config Inspector panel.
 *
 * Features:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Derived configEntries array with sensitive value detection
 *
 * @module hooks/useDebugConfigQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchDebugConfig, type DebugConfigResponse } from '../services/api';
import { queryKeys, STATIC_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * A single configuration entry with metadata
 */
export interface ConfigEntry {
  /** Configuration key */
  key: string;
  /** Configuration value (can be any type) */
  value: unknown;
  /** Whether the value is sensitive (shown as [REDACTED]) */
  isSensitive: boolean;
}

/**
 * Options for configuring the useDebugConfigQuery hook
 */
export interface UseDebugConfigQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME (5 minutes)
   */
  staleTime?: number;
}

/**
 * Return type for the useDebugConfigQuery hook
 */
export interface UseDebugConfigQueryReturn {
  /** Raw config response, undefined if not yet fetched */
  data: DebugConfigResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Config entries as key-value array with metadata */
  configEntries: ConfigEntry[];
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Determines if a config value is sensitive (redacted)
 */
function isSensitiveValue(value: unknown): boolean {
  return value === '[REDACTED]';
}

/**
 * Converts a config object to an array of ConfigEntry
 */
function toConfigEntries(config: DebugConfigResponse | undefined): ConfigEntry[] {
  if (!config) {
    return [];
  }

  return Object.entries(config).map(([key, value]) => ({
    key,
    value,
    isSensitive: isSensitiveValue(value),
  }));
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch application configuration using TanStack Query.
 *
 * This hook fetches from GET /api/debug/config and provides:
 * - Raw config data
 * - Derived configEntries array with sensitive value detection
 * - Automatic caching with static stale time
 *
 * @param options - Configuration options
 * @returns Config data and query state
 *
 * @example
 * ```tsx
 * const { configEntries, isLoading, error } = useDebugConfigQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <table>
 *     {configEntries.map(entry => (
 *       <tr key={entry.key}>
 *         <td>{entry.key}</td>
 *         <td className={entry.isSensitive ? 'text-gray-500 italic' : ''}>
 *           {formatValue(entry.value)}
 *         </td>
 *       </tr>
 *     ))}
 *   </table>
 * );
 * ```
 */
export function useDebugConfigQuery(
  options: UseDebugConfigQueryOptions = {}
): UseDebugConfigQueryReturn {
  const { enabled = true, staleTime = STATIC_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.debug.config,
    queryFn: fetchDebugConfig,
    enabled,
    staleTime,
    // Config rarely changes, so minimal retries
    retry: 1,
  });

  // Derive config entries from data
  const configEntries = useMemo(() => toConfigEntries(query.data), [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    configEntries,
    refetch: query.refetch,
  };
}

export default useDebugConfigQuery;
