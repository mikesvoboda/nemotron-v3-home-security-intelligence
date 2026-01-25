/**
 * useOptimisticLocking - Generic hook for handling optimistic locking conflicts
 *
 * Provides conflict detection, retry logic, and state management for
 * operations that use optimistic locking (version-based concurrency control).
 *
 * @see NEM-3626
 */

import { useState, useCallback, useRef } from 'react';

import { AlertsApiError, isConflictError } from '../services/alertsApi';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the optimistic locking hook
 */
export interface UseOptimisticLockingOptions {
  /**
   * Maximum number of retry attempts before giving up
   * @default 3
   */
  maxRetries?: number;

  /**
   * Callback when a conflict is detected
   */
  onConflict?: (error: AlertsApiError) => void;

  /**
   * Callback when max retries are exhausted
   */
  onRetryExhausted?: () => void;
}

/**
 * Return type for the useOptimisticLocking hook
 */
export interface UseOptimisticLockingReturn {
  /** Whether there is an active conflict that needs resolution */
  hasConflict: boolean;

  /** The conflict error if one exists */
  conflictError: AlertsApiError | null;

  /** Whether a retry operation is in progress */
  isRetrying: boolean;

  /** Number of retry attempts made */
  retryCount: number;

  /**
   * Execute an operation with conflict handling.
   * Sets hasConflict if a 409 conflict is detected.
   */
  executeWithConflictHandling: <T>(operation: () => Promise<T>) => Promise<T>;

  /**
   * Retry the operation after a conflict.
   * Clears conflict state on success.
   */
  retry: <T>(operation: () => Promise<T>) => Promise<T | undefined>;

  /**
   * Clear the conflict state.
   * Call this when user dismisses the conflict dialog.
   */
  clearConflict: () => void;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for handling optimistic locking conflicts in operations.
 *
 * Use this hook to wrap operations that may fail due to concurrent
 * modifications (HTTP 409 Conflict). The hook provides state for
 * showing conflict dialogs and retry functionality.
 *
 * @param options - Configuration options
 * @returns Hook state and functions
 *
 * @example
 * ```tsx
 * const {
 *   hasConflict,
 *   conflictError,
 *   isRetrying,
 *   executeWithConflictHandling,
 *   retry,
 *   clearConflict,
 * } = useOptimisticLocking({
 *   onConflict: (error) => toast.warning('Alert was modified'),
 * });
 *
 * const handleAcknowledge = async (alertId: string) => {
 *   try {
 *     await executeWithConflictHandling(() => acknowledgeAlert(alertId));
 *     toast.success('Alert acknowledged');
 *   } catch (error) {
 *     if (!hasConflict) {
 *       toast.error('Failed to acknowledge alert');
 *     }
 *     // Conflict is handled by showing ConflictResolutionModal
 *   }
 * };
 * ```
 */
export function useOptimisticLocking(
  options: UseOptimisticLockingOptions = {}
): UseOptimisticLockingReturn {
  const { maxRetries = 3, onConflict, onRetryExhausted } = options;

  // State
  const [hasConflict, setHasConflict] = useState(false);
  const [conflictError, setConflictError] = useState<AlertsApiError | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  // Ref to track if max retries callback was called
  const maxRetriesCallbackCalled = useRef(false);

  /**
   * Execute an operation with conflict handling.
   * If the operation fails with a conflict error (409), sets conflict state.
   * Non-conflict errors are re-thrown.
   */
  const executeWithConflictHandling = useCallback(
    async <T>(operation: () => Promise<T>): Promise<T> => {
      try {
        const result = await operation();
        // Success - clear any previous conflict
        setHasConflict(false);
        setConflictError(null);
        return result;
      } catch (error) {
        if (isConflictError(error)) {
          // Conflict detected - set state and call callback
          setHasConflict(true);
          setConflictError(error);
          onConflict?.(error);
          throw error;
        }
        // Non-conflict error - re-throw without setting conflict state
        throw error;
      }
    },
    [onConflict]
  );

  /**
   * Retry the operation after a conflict.
   * Respects maxRetries limit.
   */
  const retry = useCallback(
    async <T>(operation: () => Promise<T>): Promise<T | undefined> => {
      // Check if we've exceeded max retries
      if (retryCount >= maxRetries) {
        if (!maxRetriesCallbackCalled.current) {
          maxRetriesCallbackCalled.current = true;
          onRetryExhausted?.();
        }
        return undefined;
      }

      setIsRetrying(true);
      setRetryCount((prev) => prev + 1);

      try {
        const result = await operation();
        // Success - clear conflict state
        setHasConflict(false);
        setConflictError(null);
        setIsRetrying(false);
        return result;
      } catch (error) {
        setIsRetrying(false);
        if (isConflictError(error)) {
          // Still a conflict
          setHasConflict(true);
          setConflictError(error);
          onConflict?.(error);
        }
        throw error;
      }
    },
    [retryCount, maxRetries, onConflict, onRetryExhausted]
  );

  /**
   * Clear conflict state.
   * Call when user cancels or dismisses the conflict dialog.
   */
  const clearConflict = useCallback(() => {
    setHasConflict(false);
    setConflictError(null);
    setRetryCount(0);
    maxRetriesCallbackCalled.current = false;
  }, []);

  return {
    hasConflict,
    conflictError,
    isRetrying,
    retryCount,
    executeWithConflictHandling,
    retry,
    clearConflict,
  };
}
