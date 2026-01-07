/**
 * TanStack Query (React Query) Configuration
 *
 * This module provides the QueryClient configuration and query key factories
 * for server-state management throughout the application.
 *
 * ## Architecture Decisions
 *
 * 1. **Stale Times**: Different data types have different freshness requirements:
 *    - Real-time data (GPU metrics, health): 5 seconds
 *    - Default (events, detections): 30 seconds
 *    - Static data (config, severity): 5 minutes
 *
 * 2. **Window Focus Refetch**: Disabled to prevent unexpected refetches
 *    when user switches browser tabs. Explicit polling is preferred.
 *
 * 3. **Retry Logic**: 3 retries for queries with exponential backoff.
 *    Mutations do not retry to prevent duplicate side effects.
 *
 * 4. **Query Keys**: Factory pattern for type-safe, hierarchical cache keys
 *    that support granular invalidation.
 *
 * @see https://tanstack.com/query/latest/docs/framework/react/overview
 */

import { QueryClient } from '@tanstack/react-query';

import type { EventsQueryParams } from './api';

// ============================================================================
// Stale Time Constants
// ============================================================================

/**
 * Default stale time for most queries (30 seconds).
 * Used for data that changes moderately (events, detections, etc.).
 */
export const DEFAULT_STALE_TIME = 30 * 1000;

/**
 * Stale time for real-time data (5 seconds).
 * Used for data that changes frequently (GPU metrics, health status, queues).
 */
export const REALTIME_STALE_TIME = 5 * 1000;

/**
 * Stale time for static/configuration data (5 minutes).
 * Used for data that rarely changes (system config, severity definitions).
 */
export const STATIC_STALE_TIME = 5 * 60 * 1000;

// ============================================================================
// Query Key Factories
// ============================================================================

/**
 * Query key factories for type-safe cache key management.
 *
 * Keys follow a hierarchical pattern: [entity, action?, params?]
 *
 * This structure enables:
 * - Granular cache invalidation (e.g., invalidate all cameras)
 * - Type-safe key generation
 * - Consistent key structure across the app
 *
 * @example
 * // Invalidate all camera queries
 * queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
 *
 * // Invalidate specific camera
 * queryClient.invalidateQueries({ queryKey: queryKeys.cameras.detail('cam-1') });
 *
 * // Invalidate all events
 * queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
 */
export const queryKeys = {
  /**
   * Camera-related query keys
   */
  cameras: {
    /** Base key for all camera queries - use for bulk invalidation */
    all: ['cameras'] as const,
    /** List of all cameras */
    list: () => [...queryKeys.cameras.all, 'list'] as const,
    /** Single camera by ID */
    detail: (id: string) => [...queryKeys.cameras.all, 'detail', id] as const,
    /** Camera zones */
    zones: (cameraId: string) => [...queryKeys.cameras.all, 'zones', cameraId] as const,
    /** Camera activity baseline */
    activityBaseline: (cameraId: string) =>
      [...queryKeys.cameras.all, 'baseline', 'activity', cameraId] as const,
    /** Camera class baseline */
    classBaseline: (cameraId: string) =>
      [...queryKeys.cameras.all, 'baseline', 'classes', cameraId] as const,
  },

  /**
   * Event-related query keys
   */
  events: {
    /** Base key for all event queries */
    all: ['events'] as const,
    /** Filtered event list */
    list: (filters?: EventsQueryParams) =>
      filters
        ? ([...queryKeys.events.all, 'list', filters] as const)
        : ([...queryKeys.events.all, 'list'] as const),
    /** Single event by ID */
    detail: (id: number) => [...queryKeys.events.all, 'detail', id] as const,
    /** Event statistics */
    stats: (params?: { start_date?: string; end_date?: string }) =>
      params
        ? ([...queryKeys.events.all, 'stats', params] as const)
        : ([...queryKeys.events.all, 'stats'] as const),
    /** Event search results */
    search: (query: string, filters?: Record<string, unknown>) =>
      [...queryKeys.events.all, 'search', query, filters] as const,
  },

  /**
   * System-related query keys
   */
  system: {
    /** System health status */
    health: ['system', 'health'] as const,
    /** GPU statistics */
    gpu: ['system', 'gpu'] as const,
    /** GPU history */
    gpuHistory: (limit?: number) =>
      limit ? (['system', 'gpu', 'history', limit] as const) : (['system', 'gpu', 'history'] as const),
    /** System configuration */
    config: ['system', 'config'] as const,
    /** System statistics */
    stats: ['system', 'stats'] as const,
    /** Storage statistics */
    storage: ['system', 'storage'] as const,
    /** Telemetry data */
    telemetry: ['system', 'telemetry'] as const,
    /** Readiness check */
    readiness: ['system', 'readiness'] as const,
    /** Severity metadata */
    severity: ['system', 'severity'] as const,
    /** Circuit breakers */
    circuitBreakers: ['system', 'circuitBreakers'] as const,
  },

  /**
   * AI-related query keys
   */
  ai: {
    /** Combined AI metrics */
    metrics: ['ai', 'metrics'] as const,
    /** Model Zoo status */
    modelZoo: ['ai', 'modelZoo'] as const,
    /** Model Zoo latency history */
    modelLatency: (model: string, since?: number) =>
      (['ai', 'modelLatency', model, since] as const),
    /** AI audit queries */
    audit: {
      /** Audit statistics */
      stats: (params?: { days?: number; camera_id?: string }) =>
        params
          ? (['ai', 'audit', 'stats', params] as const)
          : (['ai', 'audit', 'stats'] as const),
      /** Model leaderboard */
      leaderboard: (params?: { days?: number }) =>
        params
          ? (['ai', 'audit', 'leaderboard', params] as const)
          : (['ai', 'audit', 'leaderboard'] as const),
      /** Recommendations */
      recommendations: (params?: { days?: number }) =>
        params
          ? (['ai', 'audit', 'recommendations', params] as const)
          : (['ai', 'audit', 'recommendations'] as const),
      /** Event audit */
      event: (eventId: number) => (['ai', 'audit', 'event', eventId] as const),
    },
    /** Prompt management */
    prompts: {
      /** All prompts */
      all: ['ai', 'prompts'] as const,
      /** Single model prompt */
      model: (model: string) => (['ai', 'prompts', model] as const),
      /** Prompt history */
      history: (model?: string) =>
        model
          ? (['ai', 'prompts', 'history', model] as const)
          : (['ai', 'prompts', 'history'] as const),
    },
  },

  /**
   * Detection-related query keys
   */
  detections: {
    /** Detections for an event */
    forEvent: (eventId: number) => ['detections', 'event', eventId] as const,
    /** Detection enrichment data */
    enrichment: (detectionId: number) => ['detections', 'enrichment', detectionId] as const,
    /** Detection statistics */
    stats: ['detections', 'stats'] as const,
  },

  /**
   * Alert-related query keys
   */
  alerts: {
    /** Base key for all alert queries */
    all: ['alerts'] as const,
    /** Alert rules list */
    rules: (filters?: { enabled?: boolean; severity?: string }) =>
      filters
        ? ([...queryKeys.alerts.all, 'rules', filters] as const)
        : ([...queryKeys.alerts.all, 'rules'] as const),
    /** Single alert rule */
    rule: (id: string) => [...queryKeys.alerts.all, 'rule', id] as const,
  },

  /**
   * Entity re-identification query keys
   */
  entities: {
    /** Base key for all entity queries */
    all: ['entities'] as const,
    /** Entity list */
    list: (filters?: { entity_type?: string; camera_id?: string; since?: string }) =>
      filters
        ? ([...queryKeys.entities.all, 'list', filters] as const)
        : ([...queryKeys.entities.all, 'list'] as const),
    /** Single entity */
    detail: (id: string) => [...queryKeys.entities.all, 'detail', id] as const,
    /** Entity history */
    history: (id: string) => [...queryKeys.entities.all, 'history', id] as const,
  },

  /**
   * Log-related query keys
   */
  logs: {
    /** Base key for all log queries */
    all: ['logs'] as const,
    /** Log list with filters */
    list: (filters?: Record<string, unknown>) =>
      filters
        ? ([...queryKeys.logs.all, 'list', filters] as const)
        : ([...queryKeys.logs.all, 'list'] as const),
    /** Log statistics */
    stats: ['logs', 'stats'] as const,
  },

  /**
   * Audit log query keys
   */
  auditLogs: {
    /** Base key for all audit log queries */
    all: ['auditLogs'] as const,
    /** Audit log list */
    list: (filters?: Record<string, unknown>) =>
      filters
        ? ([...queryKeys.auditLogs.all, 'list', filters] as const)
        : ([...queryKeys.auditLogs.all, 'list'] as const),
    /** Single audit log */
    detail: (id: number) => [...queryKeys.auditLogs.all, 'detail', id] as const,
    /** Audit log statistics */
    stats: ['auditLogs', 'stats'] as const,
  },

  /**
   * DLQ (Dead Letter Queue) query keys
   */
  dlq: {
    /** DLQ statistics */
    stats: ['dlq', 'stats'] as const,
    /** Jobs in a specific queue */
    jobs: (queueName: string, start?: number, limit?: number) =>
      (['dlq', 'jobs', queueName, { start, limit }] as const),
  },

  /**
   * Notification query keys
   */
  notifications: {
    /** Notification configuration */
    config: ['notifications', 'config'] as const,
  },
} as const;

// ============================================================================
// QueryClient Factory
// ============================================================================

/**
 * Creates a new QueryClient instance with optimized defaults.
 *
 * Use this factory when you need a fresh QueryClient (e.g., for testing).
 * For the main application, use the exported `queryClient` singleton.
 *
 * @returns Configured QueryClient instance
 *
 * @example
 * // For testing
 * const testClient = createQueryClient();
 * render(
 *   <QueryClientProvider client={testClient}>
 *     <App />
 *   </QueryClientProvider>
 * );
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        /**
         * Time until data is considered stale.
         * Stale data will be refetched in the background on next use.
         */
        staleTime: DEFAULT_STALE_TIME,

        /**
         * Time to keep inactive queries in cache before garbage collection.
         * Set to 5 minutes to allow quick navigation back without refetching.
         */
        gcTime: 5 * 60 * 1000,

        /**
         * Disable automatic refetch on window focus.
         * This prevents unexpected data refreshes when switching tabs.
         * Components should use explicit polling when real-time updates are needed.
         */
        refetchOnWindowFocus: false,

        /**
         * Enable refetch on reconnect to ensure fresh data after network recovery.
         */
        refetchOnReconnect: true,

        /**
         * Number of retry attempts for failed queries.
         * Uses exponential backoff by default.
         */
        retry: 3,

        /**
         * Retry delay configuration.
         * Uses exponential backoff: attempt^2 * 1000ms, capped at 30 seconds.
         */
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      },
      mutations: {
        /**
         * Do not retry mutations to prevent duplicate side effects.
         * Mutations should be retried explicitly by the user if needed.
         */
        retry: 0,
      },
    },
  });
}

// ============================================================================
// Singleton QueryClient
// ============================================================================

/**
 * Singleton QueryClient instance for the application.
 *
 * This instance is used by the QueryClientProvider in App.tsx.
 * Components access it via useQueryClient() hook.
 *
 * @example
 * // In App.tsx
 * import { QueryClientProvider } from '@tanstack/react-query';
 * import { queryClient } from './services/queryClient';
 *
 * function App() {
 *   return (
 *     <QueryClientProvider client={queryClient}>
 *       <YourApp />
 *     </QueryClientProvider>
 *   );
 * }
 *
 * @example
 * // In a component for cache invalidation
 * import { useQueryClient } from '@tanstack/react-query';
 * import { queryKeys } from './services/queryClient';
 *
 * function MyComponent() {
 *   const queryClient = useQueryClient();
 *
 *   const handleUpdate = () => {
 *     queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
 *   };
 * }
 */
export const queryClient = createQueryClient();
