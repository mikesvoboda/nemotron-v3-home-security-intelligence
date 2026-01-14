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

import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';

import { ApiError, isTimeoutError } from './api';
import { useRateLimitStore, type RateLimitInfo } from '../stores/rate-limit-store';
import { shouldRetry, ErrorCode } from '../utils/error-handling';

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
// Retry Configuration Constants
// ============================================================================

/**
 * Maximum number of retry attempts for transient errors.
 * After 3 retries (4 total attempts), the error will be thrown to the caller.
 */
export const MAX_RETRY_ATTEMPTS = 3;

/**
 * Base delay for retry backoff in milliseconds (1 second).
 * Exponential backoff: 1s, 2s, 4s for attempts 0, 1, 2.
 */
export const RETRY_BASE_DELAY_MS = 1000;

/**
 * Maximum retry delay in milliseconds (30 seconds).
 * Prevents excessive waits for high attempt indices.
 */
export const MAX_RETRY_DELAY_MS = 30 * 1000;

// ============================================================================
// Retry Functions
// ============================================================================

/**
 * Set of error codes that are safe to retry for mutations (timeout-only).
 *
 * Mutations can have side effects, so we only retry when we're confident
 * the operation didn't complete (timeout means the server didn't respond
 * before our deadline, but the operation may or may not have succeeded).
 *
 * For truly idempotent timeout scenarios, we allow retry.
 */
const MUTATION_SAFE_RETRY_CODES = new Set<string>([
  ErrorCode.TIMEOUT,
  ErrorCode.OPERATION_TIMEOUT,
  ErrorCode.AI_SERVICE_TIMEOUT,
]);

/**
 * Calculate the retry delay for a given attempt index and error.
 *
 * Uses exponential backoff (2^attemptIndex * RETRY_BASE_DELAY_MS) unless:
 * - The error includes a valid `retry_after` field in problemDetails, in which
 *   case we use that value (converted from seconds to milliseconds).
 *
 * The delay is capped at MAX_RETRY_DELAY_MS to prevent excessive waits.
 *
 * @param attemptIndex - Zero-based index of the retry attempt (0 = first retry)
 * @param error - The error that caused the failure
 * @returns Delay in milliseconds before the next retry attempt
 *
 * @example
 * ```typescript
 * // Exponential backoff
 * calculateRetryDelay(0, someError); // 1000ms
 * calculateRetryDelay(1, someError); // 2000ms
 * calculateRetryDelay(2, someError); // 4000ms
 *
 * // Respects Retry-After header
 * const rateLimitError = new ApiError(429, 'Rate limited', undefined, {
 *   type: 'about:blank',
 *   title: 'Rate Limited',
 *   status: 429,
 *   retry_after: 60, // 60 seconds
 * });
 * calculateRetryDelay(0, rateLimitError); // 60000ms (60 seconds)
 * ```
 */
export function calculateRetryDelay(attemptIndex: number, error: unknown): number {
  // Check for Retry-After header in problemDetails
  // Use duck typing to avoid issues in test environments where ApiError may be mocked
  if (
    error &&
    typeof error === 'object' &&
    'problemDetails' in error &&
    error.problemDetails &&
    typeof error.problemDetails === 'object' &&
    'retry_after' in error.problemDetails
  ) {
    const retryAfter = (error.problemDetails as { retry_after: unknown }).retry_after;

    // Validate retry_after is a positive number
    if (typeof retryAfter === 'number' && retryAfter > 0) {
      // Convert seconds to milliseconds and cap at MAX_RETRY_DELAY_MS
      return Math.min(retryAfter * 1000, MAX_RETRY_DELAY_MS);
    }
  }

  // Default to exponential backoff: 2^attemptIndex * RETRY_BASE_DELAY_MS
  const exponentialDelay = Math.pow(2, attemptIndex) * RETRY_BASE_DELAY_MS;

  // Cap at MAX_RETRY_DELAY_MS
  return Math.min(exponentialDelay, MAX_RETRY_DELAY_MS);
}

/**
 * Determine if a query should be retried based on the error type and attempt count.
 *
 * Uses the `shouldRetry` function from error-handling.ts to check if the error
 * is a transient error that may succeed on retry (timeouts, rate limits,
 * service unavailable, etc.).
 *
 * @param failureCount - Number of failed attempts so far (0 = first failure)
 * @param error - The error that caused the failure
 * @returns true if the query should be retried, false otherwise
 *
 * @example
 * ```typescript
 * // In TanStack Query config
 * retry: (failureCount, error) => shouldRetryQuery(failureCount, error),
 * ```
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  // Don't retry if we've exceeded the maximum attempts
  if (failureCount >= MAX_RETRY_ATTEMPTS) {
    return false;
  }

  // Use the shouldRetry function from error-handling.ts
  // This checks for retryable error codes and HTTP status codes
  return shouldRetry(error);
}

/**
 * Determine if a mutation should be retried based on the error type.
 *
 * Mutations are more conservative than queries because they can have side effects.
 * We only retry mutations for timeout errors, where we're confident the operation
 * either didn't complete or is idempotent.
 *
 * @param failureCount - Number of failed attempts so far (0 = first failure)
 * @param error - The error that caused the failure
 * @returns true if the mutation should be retried, false otherwise
 *
 * @example
 * ```typescript
 * // In TanStack Query mutation config
 * retry: (failureCount, error) => shouldRetryMutation(failureCount, error),
 * ```
 */
export function shouldRetryMutation(failureCount: number, error: unknown): boolean {
  // Don't retry if we've exceeded the maximum attempts
  if (failureCount >= MAX_RETRY_ATTEMPTS) {
    return false;
  }

  // TimeoutError is always safe to retry for mutations
  if (isTimeoutError(error)) {
    return true;
  }

  // Check for timeout-related error codes using duck typing
  // This avoids issues in test environments where ApiError may be mocked
  if (
    error &&
    typeof error === 'object' &&
    'problemDetails' in error &&
    error.problemDetails &&
    typeof error.problemDetails === 'object' &&
    'error_code' in error.problemDetails
  ) {
    const errorCode = (error.problemDetails as { error_code: unknown }).error_code;
    if (typeof errorCode === 'string') {
      return MUTATION_SAFE_RETRY_CODES.has(errorCode);
    }
  }

  // For other errors, don't retry mutations (could cause duplicate side effects)
  return false;
}

// ============================================================================
// Rate Limit Store Integration
// ============================================================================

/**
 * Default retry delay in seconds when no Retry-After header is provided.
 * Falls back to 60 seconds as per acceptance criteria.
 */
export const DEFAULT_RATE_LIMIT_RETRY_SECONDS = 60;

/**
 * Update the rate limit store when a 429 error is encountered.
 *
 * This function extracts rate limit information from the error and updates
 * the Zustand store, enabling the RetryingIndicator component to show
 * feedback to users during automatic retry.
 *
 * @param error - The error that caused the failure
 */
export function updateRateLimitStoreFromError(error: unknown): void {
  // Only handle ApiError instances with 429 status
  // Defensive check: ensure ApiError is defined before instanceof (module init timing)
  if (typeof ApiError !== 'function' || !(error instanceof ApiError) || error.status !== 429) {
    return;
  }

  const problemDetails = error.problemDetails;

  // Extract retry_after, default to 60 seconds if not provided
  let retryAfter = DEFAULT_RATE_LIMIT_RETRY_SECONDS;
  if (
    problemDetails &&
    typeof problemDetails.retry_after === 'number' &&
    problemDetails.retry_after > 0
  ) {
    retryAfter = problemDetails.retry_after;
  }

  // Extract rate limit headers if available
  let limit = 100; // Default limit
  let remaining = 0; // We're rate limited, so remaining is 0
  let reset = Math.floor(Date.now() / 1000) + retryAfter;

  if (problemDetails) {
    if (typeof problemDetails.rate_limit_limit === 'number') {
      limit = problemDetails.rate_limit_limit;
    }
    if (typeof problemDetails.rate_limit_remaining === 'number') {
      remaining = problemDetails.rate_limit_remaining;
    }
    if (typeof problemDetails.rate_limit_reset === 'number') {
      reset = problemDetails.rate_limit_reset;
    }
  }

  // Update the rate limit store
  const rateLimitInfo: RateLimitInfo = {
    limit,
    remaining,
    reset,
    retryAfter,
  };

  useRateLimitStore.getState().update(rateLimitInfo);
}

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
    /** Base key for all detection queries */
    all: ['detections'] as const,
    /** List of detections with filters */
    list: (filters?: Record<string, unknown>) =>
      filters ? (['detections', 'list', filters] as const) : (['detections', 'list'] as const),
    /** Single detection by ID */
    detail: (detectionId: number) => ['detections', 'detail', detectionId] as const,
    /** Detections for an event */
    forEvent: (eventId: number) => ['detections', 'event', eventId] as const,
    /** Detection enrichment data */
    enrichment: (detectionId: number) => ['detections', 'enrichment', detectionId] as const,
    /** Detection statistics */
    stats: ['detections', 'stats'] as const,
    /** Search detections */
    search: (params?: Record<string, unknown>) =>
      params ? (['detections', 'search', params] as const) : (['detections', 'search'] as const),
    /** Detection labels */
    labels: ['detections', 'labels'] as const,
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
    /** V2 API - historical entities */
    v2: {
      /** V2 entity list with source filter */
      list: (filters?: {
        entity_type?: string;
        camera_id?: string;
        since?: string;
        until?: string;
        source?: string;
      }) =>
        filters
          ? ([...queryKeys.entities.all, 'v2', 'list', filters] as const)
          : ([...queryKeys.entities.all, 'v2', 'list'] as const),
      /** V2 entity detail (PostgreSQL) */
      detail: (id: string) => [...queryKeys.entities.all, 'v2', 'detail', id] as const,
      /** Entity detections */
      detections: (id: string, params?: { limit?: number; offset?: number }) =>
        params
          ? ([...queryKeys.entities.all, 'v2', 'detections', id, params] as const)
          : ([...queryKeys.entities.all, 'v2', 'detections', id] as const),
    },
    /** Entity statistics */
    stats: (params?: { since?: string; until?: string }) =>
      params
        ? ([...queryKeys.entities.all, 'stats', params] as const)
        : ([...queryKeys.entities.all, 'stats'] as const),
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
    /** Base key for notification preferences */
    preferences: {
      /** All notification preferences queries */
      all: ['notifications', 'preferences'] as const,
      /** Global notification preferences */
      global: ['notifications', 'preferences', 'global'] as const,
      /** Camera notification settings */
      cameras: {
        /** All camera settings */
        all: ['notifications', 'preferences', 'cameras'] as const,
        /** List of all camera settings */
        list: () =>
          [...queryKeys.notifications.preferences.cameras.all, 'list'] as const,
        /** Single camera setting */
        detail: (cameraId: string) =>
          [
            ...queryKeys.notifications.preferences.cameras.all,
            'detail',
            cameraId,
          ] as const,
      },
      /** Quiet hours periods */
      quietHours: {
        /** All quiet hours queries */
        all: ['notifications', 'preferences', 'quietHours'] as const,
        /** List of quiet hours periods */
        list: () =>
          [...queryKeys.notifications.preferences.quietHours.all, 'list'] as const,
      },
    },
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
  // Create QueryCache with onError callback for rate limit store integration
  const queryCache = new QueryCache({
    onError: (error) => {
      updateRateLimitStoreFromError(error);
    },
  });

  // Create MutationCache with onError callback for rate limit store integration
  const mutationCache = new MutationCache({
    onError: (error) => {
      updateRateLimitStoreFromError(error);
    },
  });

  return new QueryClient({
    queryCache,
    mutationCache,
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
         * Smart retry logic based on error type.
         * Only retries transient errors (timeouts, rate limits, service unavailable).
         * Uses shouldRetryQuery which checks error codes and HTTP status codes.
         */
        retry: (failureCount, error) => shouldRetryQuery(failureCount, error),

        /**
         * Retry delay configuration with Retry-After header support.
         * Uses exponential backoff: 2^attemptIndex * 1000ms (1s, 2s, 4s).
         * Respects Retry-After header from rate limit responses.
         * Capped at 30 seconds.
         */
        retryDelay: (attemptIndex, error) => calculateRetryDelay(attemptIndex, error),
      },
      mutations: {
        /**
         * Conservative retry for mutations to prevent duplicate side effects.
         * Only retries timeout errors (TIMEOUT, OPERATION_TIMEOUT, AI_SERVICE_TIMEOUT).
         * Other errors (including SERVICE_UNAVAILABLE) are not retried to avoid
         * potentially creating duplicate resources or side effects.
         */
        retry: (failureCount, error) => shouldRetryMutation(failureCount, error),

        /**
         * Same retry delay logic as queries when mutations are retried.
         */
        retryDelay: (attemptIndex, error) => calculateRetryDelay(attemptIndex, error),
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
