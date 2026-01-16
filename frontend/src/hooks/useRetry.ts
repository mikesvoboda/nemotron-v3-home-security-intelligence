/**
 * Retry Hook with Automatic Backoff for 429 Responses
 *
 * Provides automatic retry functionality with exponential backoff when
 * rate limited (429 status). Supports Retry-After header parsing and
 * user-cancellable retry operations.
 *
 * @see NEM-2297
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';
import { create } from 'zustand';

// ============================================================================
// Types
// ============================================================================

/**
 * Configuration for retry behavior.
 */
export interface RetryConfig {
  /** Maximum number of retry attempts (default: 3) */
  maxRetries: number;
  /** Base delay in milliseconds for exponential backoff (default: 1000) */
  baseDelay: number;
  /** Maximum delay in milliseconds (default: 30000) */
  maxDelay: number;
  /** Whether to use Retry-After header when available (default: true) */
  useRetryAfter: boolean;
}

/**
 * Default retry configuration as specified in requirements.
 */
export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 30000,
  useRetryAfter: true,
};

/**
 * State of a pending retry operation.
 */
export interface RetryState {
  /** Unique identifier for the retry operation */
  id: string;
  /** Current retry attempt number (1-based) */
  attempt: number;
  /** Maximum retry attempts */
  maxAttempts: number;
  /** Seconds remaining until next retry */
  secondsRemaining: number;
  /** Whether the retry has been cancelled */
  cancelled: boolean;
  /** The original request URL for display purposes */
  url: string;
  /** Timestamp when retry will execute */
  retryAt: number;
}

/**
 * Pending retry request in the queue.
 */
export interface PendingRetry<T = unknown> {
  /** Unique identifier for the retry operation */
  id: string;
  /** The function to execute on retry */
  execute: () => Promise<T>;
  /** Current attempt number */
  attempt: number;
  /** Maximum retry attempts */
  maxAttempts: number;
  /** Delay in milliseconds until next retry */
  delay: number;
  /** The original request URL for display purposes */
  url: string;
  /** Resolve callback for the promise */
  resolve: (value: T) => void;
  /** Reject callback for the promise */
  reject: (error: Error) => void;
  /** Timer ID for the scheduled retry */
  timerId: ReturnType<typeof setTimeout> | null;
  /** Whether this retry has been cancelled */
  cancelled: boolean;
}

/**
 * Global retry store state.
 */
export interface RetryStoreState {
  /** Active retry operations keyed by ID */
  retries: Map<string, RetryState>;
  /** Add or update a retry operation */
  setRetry: (id: string, state: RetryState) => void;
  /** Remove a retry operation */
  removeRetry: (id: string) => void;
  /** Mark a retry as cancelled */
  cancelRetry: (id: string) => void;
  /** Update seconds remaining for a retry */
  updateCountdown: (id: string, seconds: number) => void;
  /** Clear all retries */
  clearAll: () => void;
}

// ============================================================================
// Global Retry Store (Zustand)
// ============================================================================

/**
 * Global store for tracking retry operations across the application.
 * This enables the RetryIndicator component to display retry status.
 */
export const useRetryStore = create<RetryStoreState>((set) => ({
  retries: new Map(),

  setRetry: (id, state) =>
    set((prev) => {
      const newRetries = new Map(prev.retries);
      newRetries.set(id, state);
      return { retries: newRetries };
    }),

  removeRetry: (id) =>
    set((prev) => {
      const newRetries = new Map(prev.retries);
      newRetries.delete(id);
      return { retries: newRetries };
    }),

  cancelRetry: (id) =>
    set((prev) => {
      const newRetries = new Map(prev.retries);
      const existing = newRetries.get(id);
      if (existing) {
        newRetries.set(id, { ...existing, cancelled: true });
      }
      return { retries: newRetries };
    }),

  updateCountdown: (id, seconds) =>
    set((prev) => {
      const newRetries = new Map(prev.retries);
      const existing = newRetries.get(id);
      if (existing) {
        newRetries.set(id, { ...existing, secondsRemaining: seconds });
      }
      return { retries: newRetries };
    }),

  clearAll: () => set({ retries: new Map() }),
}));

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Generate a unique ID for retry operations.
 */
export function generateRetryId(): string {
  return `retry-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Parse Retry-After header value.
 * Supports both delay-seconds and HTTP-date formats.
 *
 * @param retryAfter - The Retry-After header value
 * @returns Delay in milliseconds, or null if parsing fails
 */
export function parseRetryAfter(retryAfter: string | null): number | null {
  if (!retryAfter) {
    return null;
  }

  // Try parsing as seconds first (e.g., "120")
  const seconds = parseInt(retryAfter, 10);
  if (!isNaN(seconds) && seconds >= 0) {
    return seconds * 1000;
  }

  // Try parsing as HTTP-date (e.g., "Wed, 21 Oct 2015 07:28:00 GMT")
  const date = new Date(retryAfter);
  if (!isNaN(date.getTime())) {
    const delayMs = date.getTime() - Date.now();
    return Math.max(0, delayMs);
  }

  return null;
}

/**
 * Calculate delay for a retry attempt using exponential backoff.
 *
 * @param attempt - Current attempt number (1-based)
 * @param config - Retry configuration
 * @param retryAfterMs - Optional Retry-After header value in milliseconds
 * @returns Delay in milliseconds
 */
export function calculateBackoff(
  attempt: number,
  config: RetryConfig,
  retryAfterMs?: number | null
): number {
  // Use Retry-After header if available and configured
  if (config.useRetryAfter && retryAfterMs && retryAfterMs > 0) {
    return Math.min(retryAfterMs, config.maxDelay);
  }

  // Exponential backoff: baseDelay * 2^(attempt-1)
  const exponentialDelay = config.baseDelay * Math.pow(2, attempt - 1);
  return Math.min(exponentialDelay, config.maxDelay);
}

/**
 * Format milliseconds as a user-friendly countdown string.
 *
 * @param ms - Milliseconds remaining
 * @returns Formatted string like "5 seconds" or "1 minute 30 seconds"
 */
export function formatRetryCountdown(ms: number): string {
  const seconds = Math.ceil(ms / 1000);

  if (seconds < 60) {
    return `${seconds} second${seconds !== 1 ? 's' : ''}`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (remainingSeconds === 0) {
    return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
  }

  return `${minutes} minute${minutes !== 1 ? 's' : ''} ${remainingSeconds} second${remainingSeconds !== 1 ? 's' : ''}`;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Return type for the useRetry hook.
 */
export interface UseRetryReturn {
  /** Queue a request for retry after rate limit */
  queueRetry: <T>(
    execute: () => Promise<T>,
    url: string,
    retryAfterMs?: number | null
  ) => Promise<T>;
  /** Cancel a specific retry by ID */
  cancelRetry: (id: string) => void;
  /** Cancel all pending retries */
  cancelAllRetries: () => void;
  /** Current active retries */
  activeRetries: RetryState[];
  /** Whether there are any active retries */
  hasActiveRetries: boolean;
}

/**
 * Hook for managing automatic retries with exponential backoff.
 *
 * @param config - Optional retry configuration
 * @returns Retry management functions and state
 *
 * @example
 * ```tsx
 * import { useRetry } from '@/hooks/useRetry';
 *
 * function MyComponent() {
 *   const { queueRetry, cancelAllRetries, hasActiveRetries } = useRetry();
 *
 *   const fetchData = async () => {
 *     try {
 *       const response = await fetch('/api/data');
 *       if (response.status === 429) {
 *         const retryAfter = response.headers.get('Retry-After');
 *         const retryAfterMs = parseRetryAfter(retryAfter);
 *         return queueRetry(() => fetch('/api/data'), '/api/data', retryAfterMs);
 *       }
 *       return response;
 *     } catch (error) {
 *       // Handle error
 *     }
 *   };
 * }
 * ```
 */
export function useRetry(config: Partial<RetryConfig> = {}): UseRetryReturn {
  // Memoize config to prevent re-creation on every render
  const mergedConfig = useMemo<RetryConfig>(
    () => ({ ...DEFAULT_RETRY_CONFIG, ...config }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Individual config properties are checked
    [config.baseDelay, config.maxDelay, config.maxRetries, config.useRetryAfter]
  );

  // Store pending retries in ref to avoid re-renders
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pendingRetries = useRef<Map<string, PendingRetry<any>>>(new Map());

  // Track countdown intervals
  const countdownIntervals = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  // Get store actions
  const { setRetry, removeRetry, cancelRetry: storeCancelRetry } = useRetryStore();

  // Get active retries from store
  const retries = useRetryStore((state) => state.retries);
  const activeRetries = Array.from(retries.values()).filter((r) => !r.cancelled);

  /**
   * Start a countdown timer for a retry operation.
   */
  const startCountdown = useCallback((id: string, _delayMs: number, retryAt: number) => {
    // Clear existing interval if any
    const existingInterval = countdownIntervals.current.get(id);
    if (existingInterval) {
      clearInterval(existingInterval);
    }

    const updateCountdown = () => {
      const remaining = Math.max(0, retryAt - Date.now());
      const seconds = Math.ceil(remaining / 1000);
      useRetryStore.getState().updateCountdown(id, seconds);

      if (remaining <= 0) {
        const interval = countdownIntervals.current.get(id);
        if (interval) {
          clearInterval(interval);
          countdownIntervals.current.delete(id);
        }
      }
    };

    // Initial update
    updateCountdown();

    // Update every second
    const intervalId = setInterval(updateCountdown, 1000);
    countdownIntervals.current.set(id, intervalId);
  }, []);

  /**
   * Clean up a retry operation (timer, countdown, store).
   */
  const cleanupRetry = useCallback(
    (id: string) => {
      const pending = pendingRetries.current.get(id);
      if (pending?.timerId) {
        clearTimeout(pending.timerId);
      }
      pendingRetries.current.delete(id);

      const interval = countdownIntervals.current.get(id);
      if (interval) {
        clearInterval(interval);
        countdownIntervals.current.delete(id);
      }

      removeRetry(id);
    },
    [removeRetry]
  );

  /**
   * Queue a request for retry with exponential backoff.
   */
  const queueRetry = useCallback(
    <T>(execute: () => Promise<T>, url: string, retryAfterMs?: number | null): Promise<T> => {
      return new Promise((resolve, reject) => {
        const id = generateRetryId();
        const attempt = 1;
        const delay = calculateBackoff(attempt, mergedConfig, retryAfterMs);
        const retryAt = Date.now() + delay;

        // Create retry state for the store
        const retryState: RetryState = {
          id,
          attempt,
          maxAttempts: mergedConfig.maxRetries,
          secondsRemaining: Math.ceil(delay / 1000),
          cancelled: false,
          url,
          retryAt,
        };

        // Update store
        setRetry(id, retryState);

        // Start countdown
        startCountdown(id, delay, retryAt);

        // Create pending retry object
        const pending: PendingRetry<T> = {
          id,
          execute,
          attempt,
          maxAttempts: mergedConfig.maxRetries,
          delay,
          url,
          resolve: resolve as (value: unknown) => void,
          reject,
          timerId: null,
          cancelled: false,
        };

        // Schedule the retry
        const scheduleRetry = (pendingRetry: PendingRetry<T>) => {
          const currentDelay = calculateBackoff(
            pendingRetry.attempt,
            mergedConfig,
            pendingRetry.attempt === 1 ? retryAfterMs : null
          );

          const currentRetryAt = Date.now() + currentDelay;

          // Update store with current attempt info
          setRetry(pendingRetry.id, {
            id: pendingRetry.id,
            attempt: pendingRetry.attempt,
            maxAttempts: pendingRetry.maxAttempts,
            secondsRemaining: Math.ceil(currentDelay / 1000),
            cancelled: false,
            url: pendingRetry.url,
            retryAt: currentRetryAt,
          });

          // Start countdown for this attempt
          startCountdown(pendingRetry.id, currentDelay, currentRetryAt);

          pendingRetry.timerId = setTimeout(async () => {
            // Check if cancelled
            if (pendingRetry.cancelled) {
              cleanupRetry(pendingRetry.id);
              pendingRetry.reject(new Error('Retry cancelled by user'));
              return;
            }

            try {
              const result = await pendingRetry.execute();
              cleanupRetry(pendingRetry.id);
              pendingRetry.resolve(result);
            } catch (error) {
              // Check if we should retry again
              if (pendingRetry.attempt < pendingRetry.maxAttempts) {
                pendingRetry.attempt += 1;
                scheduleRetry(pendingRetry);
              } else {
                // Max retries reached
                cleanupRetry(pendingRetry.id);
                pendingRetry.reject(
                  error instanceof Error ? error : new Error('Max retries exceeded')
                );
              }
            }
          }, currentDelay);
        };

        pendingRetries.current.set(id, pending);
        scheduleRetry(pending);
      });
    },
    [mergedConfig, setRetry, startCountdown, cleanupRetry]
  );

  /**
   * Cancel a specific retry operation.
   */
  const cancelRetry = useCallback(
    (id: string) => {
      const pending = pendingRetries.current.get(id);
      if (pending) {
        pending.cancelled = true;
        if (pending.timerId) {
          clearTimeout(pending.timerId);
        }
        pending.reject(new Error('Retry cancelled by user'));
      }
      storeCancelRetry(id);
      cleanupRetry(id);
    },
    [storeCancelRetry, cleanupRetry]
  );

  /**
   * Cancel all pending retry operations.
   */
  const cancelAllRetries = useCallback(() => {
    for (const [id, pending] of pendingRetries.current) {
      pending.cancelled = true;
      if (pending.timerId) {
        clearTimeout(pending.timerId);
      }
      pending.reject(new Error('Retry cancelled by user'));
      storeCancelRetry(id);
    }

    // Clear all intervals
    for (const [, interval] of countdownIntervals.current) {
      clearInterval(interval);
    }

    pendingRetries.current.clear();
    countdownIntervals.current.clear();
    useRetryStore.getState().clearAll();
  }, [storeCancelRetry]);

  // Cleanup on unmount
  useEffect(() => {
    // Capture refs at effect creation time for cleanup
    const pendingRetriesRef = pendingRetries;
    const countdownIntervalsRef = countdownIntervals;

    return () => {
      // Clear all timers and intervals on unmount
      for (const [, pending] of pendingRetriesRef.current) {
        if (pending.timerId) {
          clearTimeout(pending.timerId);
        }
      }
      for (const [, interval] of countdownIntervalsRef.current) {
        clearInterval(interval);
      }
    };
  }, []);

  return {
    queueRetry,
    cancelRetry,
    cancelAllRetries,
    activeRetries,
    hasActiveRetries: activeRetries.length > 0,
  };
}

// ============================================================================
// Selector Hooks
// ============================================================================

/**
 * Hook to get the current active retries from the global store.
 * Use this in components that only need to display retry status.
 */
export function useActiveRetries(): RetryState[] {
  const retries = useRetryStore((state) => state.retries);
  return Array.from(retries.values()).filter((r) => !r.cancelled);
}

/**
 * Hook to check if there are any active retries.
 */
export function useHasActiveRetries(): boolean {
  const retries = useRetryStore((state) => state.retries);
  return Array.from(retries.values()).some((r) => !r.cancelled);
}
