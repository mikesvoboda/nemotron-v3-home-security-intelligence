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
  /**
   * Raw response envelope `{ config, timestamp }`, undefined until fetched.
   * [r130f] F-158: the SETTINGS live at `data.config` — read them there, not off
   * `data`. (`configEntries` is already derived from `data.config`.)
   */
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
 *
 * [r130f] F-158: exact-match on purpose, and it only works at all once the
 * entries come from `body.config`. Measured on the live stack: 17 settings answer
 * exactly '[REDACTED]', and one (`database_url`) answers
 * `postgresql+asyncpg://security:[REDACTED]@postgres:5432/security` — the backend
 * masks only the password so the operator can still read host and db
 * (`backend/api/routes/debug.py:350` _get_redacted_config). Treating that partial
 * as "sensitive" would grey out a value the operator is meant to read, so it stays
 * unflagged and the italic treatment stays a true statement about a masked value.
 */
function isSensitiveValue(value: unknown): boolean {
  return value === '[REDACTED]';
}

/**
 * Converts the response's settings map to an array of ConfigEntry.
 *
 * [r130f] F-158: this took `Object.entries` of the whole response body, which is
 * the ENVELOPE `{ config, timestamp }`, so the inspector table listed 2 rows named
 * `config` and `timestamp` instead of the 303 settings, and redaction could never
 * fire because neither envelope value is '[REDACTED]'. Reading `.config` is the
 * whole fix; the timestamp stays out of the table because it is not a setting.
 */
function toConfigEntries(body: DebugConfigResponse | undefined): ConfigEntry[] {
  const config = body?.config;
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
