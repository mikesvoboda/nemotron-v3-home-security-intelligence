/**
 * Query Persistence Configuration for TanStack Query
 *
 * This module configures offline/cold-start persistence for TanStack Query
 * using localStorage. Only static/slow-changing data is persisted to enable
 * instant page loads while avoiding stale real-time data issues.
 *
 * ## Persisted Query Keys
 * - 'cameras' - Camera list (rarely changes)
 * - 'system.config' - System configuration
 * - 'gpus' - GPU device list (hardware rarely changes)
 * - 'alerts.rules' - Alert rules configuration
 *
 * ## Not Persisted (Real-time Data)
 * - Events, detections, health status
 * - GPU stats, metrics, telemetry
 * - Logs, audit logs, job status
 *
 * @module services/queryPersistence
 * @see NEM-3363 - Query persistence implementation
 * @see https://tanstack.com/query/latest/docs/framework/react/plugins/persistQueryClient
 */

import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';

import type { QueryClient } from '@tanstack/react-query';

// ============================================================================
// Constants
// ============================================================================

/**
 * Storage key for the persisted query cache.
 * This key is used in localStorage to store the dehydrated query state.
 */
export const PERSISTENCE_STORAGE_KEY = 'security-dashboard-cache';

/**
 * Maximum age of persisted data in milliseconds (24 hours).
 * Data older than this will be discarded on restore.
 */
export const PERSISTENCE_MAX_AGE = 1000 * 60 * 60 * 24; // 24 hours

/**
 * Query keys that should be persisted.
 *
 * These are static or slow-changing data that benefit from persistence:
 * - Cameras: Hardware configuration rarely changes
 * - System config: Application settings
 * - GPUs: Hardware devices (for GPU settings page)
 * - Alert rules: User-configured rules
 *
 * Note: We check if query key starts with any of these prefixes.
 */
export const PERSISTABLE_QUERY_KEY_PREFIXES = [
  'cameras',
  ['system', 'config'],
  'gpus',
  ['alerts', 'rules'],
] as const;

// ============================================================================
// Types
// ============================================================================

/**
 * Query-like object interface for dehydration filtering.
 * Uses a minimal interface to avoid type conflicts between TanStack Query versions.
 */
export interface DehydrateQueryLike {
  queryKey: readonly unknown[];
  state: {
    status: string;
    data: unknown;
  };
}

// ============================================================================
// Persister Creation
// ============================================================================

/**
 * Creates a sync storage persister for query persistence.
 *
 * Uses localStorage for synchronous read/write operations.
 * Falls back gracefully if localStorage is not available (SSR, private browsing).
 *
 * @returns SyncStoragePersister instance or undefined if storage unavailable
 *
 * @example
 * ```typescript
 * const persister = createQueryPersister();
 * if (persister) {
 *   // Use with PersistQueryClientProvider
 * }
 * ```
 */
export function createQueryPersister() {
  // Check if localStorage is available (may not be in SSR or private browsing)
  if (typeof window === 'undefined' || !window.localStorage) {
    return undefined;
  }

  try {
    // Test if localStorage is accessible (may throw in some browsers)
    const testKey = '__storage_test__';
    window.localStorage.setItem(testKey, testKey);
    window.localStorage.removeItem(testKey);
  } catch {
    // localStorage not available or quota exceeded
    return undefined;
  }

  return createSyncStoragePersister({
    storage: window.localStorage,
    key: PERSISTENCE_STORAGE_KEY,
    // Serialize/deserialize with JSON (default behavior)
    // Add throttle time to avoid excessive writes
    throttleTime: 1000, // 1 second throttle
  });
}

// ============================================================================
// Query Filtering
// ============================================================================

/**
 * Type-safe helper to check if a query key matches a persistable prefix.
 *
 * @param queryKey - The query key array to check
 * @param prefix - The prefix to match (string or array)
 * @returns true if the query key starts with the prefix
 */
function matchesPrefix(queryKey: readonly unknown[], prefix: string | readonly string[]): boolean {
  if (typeof prefix === 'string') {
    return queryKey[0] === prefix;
  }

  // Array prefix - check each element
  for (let i = 0; i < prefix.length; i++) {
    if (queryKey[i] !== prefix[i]) {
      return false;
    }
  }
  return true;
}

/**
 * Determines if a query should be persisted to storage.
 *
 * Only persists queries that:
 * 1. Have a successful state (not error/loading)
 * 2. Match one of the persistable query key prefixes
 * 3. Have data (not undefined)
 *
 * This filter prevents persisting:
 * - Real-time data (events, metrics, health status)
 * - Failed queries (errors should be re-fetched)
 * - Pending queries (incomplete data)
 *
 * @param query - The query object from TanStack Query
 * @returns true if the query should be persisted
 *
 * @example
 * ```typescript
 * // This query WILL be persisted:
 * // queryKey: ['cameras', 'list']
 *
 * // This query will NOT be persisted:
 * // queryKey: ['events', 'list', { camera_id: 'cam-1' }]
 * ```
 */
export function shouldDehydrateQuery(query: DehydrateQueryLike): boolean {
  // Only persist successful queries with data
  if (query.state.status !== 'success' || query.state.data === undefined) {
    return false;
  }

  // Check if query key matches any persistable prefix
  const queryKey = query.queryKey;

  for (const prefix of PERSISTABLE_QUERY_KEY_PREFIXES) {
    if (matchesPrefix(queryKey, prefix)) {
      return true;
    }
  }

  return false;
}

/**
 * Type-compatible wrapper for shouldDehydrateQuery that works with any Query type.
 * This is needed because the Query type may differ between package versions
 * (e.g., @tanstack/react-query vs @tanstack/react-query-persist-client).
 *
 * Uses a generic type to accept any query-like object with the required properties.
 */
export function shouldDehydrateQueryCompat<
  T extends { queryKey: readonly unknown[]; state: { status: string; data: unknown } },
>(query: T): boolean {
  return shouldDehydrateQuery({
    queryKey: query.queryKey,
    state: {
      status: query.state.status,
      data: query.state.data,
    },
  });
}

// ============================================================================
// Persistence Setup
// ============================================================================

/**
 * Options for setting up query persistence.
 */
export interface SetupQueryPersistenceOptions {
  /**
   * Maximum age of persisted data in milliseconds.
   * @default PERSISTENCE_MAX_AGE (24 hours)
   */
  maxAge?: number;

  /**
   * Custom filter for determining which queries to persist.
   * @default shouldDehydrateQuery
   */
  dehydrateFilter?: (query: DehydrateQueryLike) => boolean;
}

/**
 * Sets up query persistence for a QueryClient using the imperative API.
 *
 * This function configures the persist-query-client plugin to:
 * 1. Restore persisted queries on app load (instant page loads)
 * 2. Persist selected queries to localStorage on changes
 * 3. Filter out real-time data from persistence
 *
 * Note: For most cases, use PersistQueryClientProvider in App.tsx instead.
 * This function is useful for programmatic setup or testing.
 *
 * @param queryClient - The QueryClient instance to configure
 * @param options - Optional configuration overrides
 * @returns Cleanup function to unsubscribe from persistence, or undefined if persistence unavailable
 *
 * @example
 * ```typescript
 * // In App.tsx or main.tsx
 * import { queryClient } from './services/queryClient';
 * import { setupQueryPersistence } from './services/queryPersistence';
 *
 * // Setup persistence (returns cleanup function)
 * const cleanup = setupQueryPersistence(queryClient);
 *
 * // Later, to clean up (e.g., in useEffect cleanup)
 * cleanup?.();
 * ```
 */
export function setupQueryPersistence(
  queryClient: QueryClient,
  options: SetupQueryPersistenceOptions = {}
): (() => void) | undefined {
  const { maxAge = PERSISTENCE_MAX_AGE, dehydrateFilter = shouldDehydrateQuery } = options;

  // Create persister
  const persister = createQueryPersister();
  if (!persister) {
    // localStorage not available - skip persistence setup
    return undefined;
  }

  // Helper function to handle the dynamic import and setup
  const setupPersistence = async () => {
    try {
      const { persistQueryClient } = await import('@tanstack/react-query-persist-client');
      // persistQueryClient returns [unsubscribe, promise] - we ignore the return value
      // as cleanup is handled separately via clearPersistedCache
      const result = persistQueryClient({
        // Cast through unknown to work around type conflicts between TanStack Query package versions
        // The interface is compatible but TypeScript sees different private class members
        queryClient: queryClient as unknown as Parameters<typeof persistQueryClient>[0]['queryClient'],
        persister,
        maxAge,
        dehydrateOptions: {
          shouldDehydrateQuery: (query: DehydrateQueryLike) => dehydrateFilter(query),
        },
      });
      // Wait for restoration to complete if it returns a promise
      if (result && Array.isArray(result) && result[1] instanceof Promise) {
        await result[1];
      }
    } catch {
      // Ignore import errors - persistence is optional
    }
  };

  // Execute the setup (void expression to satisfy linting rules)
  void setupPersistence();

  // Return a cleanup function that clears the cache
  return () => {
    clearPersistedCache();
  };
}

// ============================================================================
// Storage Utilities
// ============================================================================

/**
 * Clears the persisted query cache from localStorage.
 *
 * Use this when:
 * - User logs out (if auth is added later)
 * - Cache needs to be invalidated due to schema changes
 * - User explicitly clears app data
 *
 * @example
 * ```typescript
 * // Clear cache on logout or data reset
 * clearPersistedCache();
 * ```
 */
export function clearPersistedCache(): void {
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      window.localStorage.removeItem(PERSISTENCE_STORAGE_KEY);
    } catch {
      // Ignore errors (e.g., in private browsing mode)
    }
  }
}

/**
 * Gets the size of the persisted cache in bytes.
 *
 * Useful for debugging and monitoring storage usage.
 *
 * @returns Size in bytes, or 0 if cache doesn't exist or storage unavailable
 *
 * @example
 * ```typescript
 * const sizeBytes = getPersistedCacheSize();
 * console.log(`Cache size: ${(sizeBytes / 1024).toFixed(2)} KB`);
 * ```
 */
export function getPersistedCacheSize(): number {
  if (typeof window === 'undefined' || !window.localStorage) {
    return 0;
  }

  try {
    const cached = window.localStorage.getItem(PERSISTENCE_STORAGE_KEY);
    return cached ? new Blob([cached]).size : 0;
  } catch {
    return 0;
  }
}

/**
 * Checks if there is persisted data available.
 *
 * @returns true if persisted cache exists and is non-empty
 *
 * @example
 * ```typescript
 * if (hasPersistedCache()) {
 *   console.log('Loading from cache...');
 * }
 * ```
 */
export function hasPersistedCache(): boolean {
  if (typeof window === 'undefined' || !window.localStorage) {
    return false;
  }

  try {
    const cached = window.localStorage.getItem(PERSISTENCE_STORAGE_KEY);
    return cached !== null && cached.length > 0;
  } catch {
    return false;
  }
}
