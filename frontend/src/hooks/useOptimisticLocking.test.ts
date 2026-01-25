/**
 * Tests for useOptimisticLocking hook
 *
 * Tests the generic hook for handling optimistic locking conflicts
 * with retry logic, version refresh, and conflict resolution callbacks.
 *
 * @see NEM-3626
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useOptimisticLocking } from './useOptimisticLocking';
import { AlertsApiError } from '../services/alertsApi';

describe('useOptimisticLocking', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('returns correct initial state', () => {
      const { result } = renderHook(() => useOptimisticLocking());

      expect(result.current.hasConflict).toBe(false);
      expect(result.current.conflictError).toBeNull();
      expect(result.current.isRetrying).toBe(false);
      expect(result.current.retryCount).toBe(0);
    });

    it('clearConflict is a function', () => {
      const { result } = renderHook(() => useOptimisticLocking());
      expect(typeof result.current.clearConflict).toBe('function');
    });

    it('executeWithConflictHandling is a function', () => {
      const { result } = renderHook(() => useOptimisticLocking());
      expect(typeof result.current.executeWithConflictHandling).toBe('function');
    });
  });

  describe('executeWithConflictHandling', () => {
    it('executes operation successfully and returns result', async () => {
      const { result } = renderHook(() => useOptimisticLocking());

      const mockOperation = vi.fn().mockResolvedValue({ id: '123', status: 'acknowledged' });

      let operationResult: unknown;
      await act(async () => {
        operationResult = await result.current.executeWithConflictHandling(mockOperation);
      });

      expect(operationResult).toEqual({ id: '123', status: 'acknowledged' });
      expect(mockOperation).toHaveBeenCalledTimes(1);
      expect(result.current.hasConflict).toBe(false);
    });

    it('sets conflict state when operation throws conflict error', async () => {
      const { result } = renderHook(() => useOptimisticLocking());

      const conflictError = new AlertsApiError(
        'Alert was modified by another request',
        409,
        true
      );
      const mockOperation = vi.fn().mockRejectedValue(conflictError);

      await act(async () => {
        try {
          await result.current.executeWithConflictHandling(mockOperation);
        } catch {
          // Expected to throw
        }
      });

      expect(result.current.hasConflict).toBe(true);
      expect(result.current.conflictError).toBe(conflictError);
    });

    it('re-throws non-conflict errors without setting conflict state', async () => {
      const { result } = renderHook(() => useOptimisticLocking());

      const regularError = new AlertsApiError('Server error', 500, false);
      const mockOperation = vi.fn().mockRejectedValue(regularError);

      await act(async () => {
        await expect(
          result.current.executeWithConflictHandling(mockOperation)
        ).rejects.toThrow(regularError);
      });

      expect(result.current.hasConflict).toBe(false);
      expect(result.current.conflictError).toBeNull();
    });

    it('calls onConflict callback when conflict occurs', async () => {
      const onConflict = vi.fn();
      const { result } = renderHook(() => useOptimisticLocking({ onConflict }));

      const conflictError = new AlertsApiError('Conflict', 409, true);
      const mockOperation = vi.fn().mockRejectedValue(conflictError);

      await act(async () => {
        try {
          await result.current.executeWithConflictHandling(mockOperation);
        } catch {
          // Expected
        }
      });

      expect(onConflict).toHaveBeenCalledWith(conflictError);
    });

    it('does not call onConflict for non-conflict errors', async () => {
      const onConflict = vi.fn();
      const { result } = renderHook(() => useOptimisticLocking({ onConflict }));

      const regularError = new Error('Network error');
      const mockOperation = vi.fn().mockRejectedValue(regularError);

      await act(async () => {
        try {
          await result.current.executeWithConflictHandling(mockOperation);
        } catch {
          // Expected
        }
      });

      expect(onConflict).not.toHaveBeenCalled();
    });
  });

  describe('clearConflict', () => {
    it('resets conflict state', async () => {
      const { result } = renderHook(() => useOptimisticLocking());

      // First, trigger a conflict
      const conflictError = new AlertsApiError('Conflict', 409, true);
      const mockOperation = vi.fn().mockRejectedValue(conflictError);

      await act(async () => {
        try {
          await result.current.executeWithConflictHandling(mockOperation);
        } catch {
          // Expected
        }
      });

      expect(result.current.hasConflict).toBe(true);

      // Now clear the conflict
      act(() => {
        result.current.clearConflict();
      });

      expect(result.current.hasConflict).toBe(false);
      expect(result.current.conflictError).toBeNull();
      expect(result.current.retryCount).toBe(0);
    });
  });

  describe('retry functionality', () => {
    it('retry executes the operation again', async () => {
      const { result } = renderHook(() => useOptimisticLocking());

      // First operation succeeds
      const mockOperation = vi.fn().mockResolvedValue({ status: 'success' });

      await act(async () => {
        await result.current.executeWithConflictHandling(mockOperation);
      });

      expect(mockOperation).toHaveBeenCalledTimes(1);

      // Retry
      await act(async () => {
        await result.current.retry(mockOperation);
      });

      expect(mockOperation).toHaveBeenCalledTimes(2);
    });

    it('increments retry count on each retry', async () => {
      const { result } = renderHook(() => useOptimisticLocking());

      const mockOperation = vi.fn().mockResolvedValue({ status: 'success' });

      expect(result.current.retryCount).toBe(0);

      await act(async () => {
        await result.current.retry(mockOperation);
      });

      expect(result.current.retryCount).toBe(1);

      await act(async () => {
        await result.current.retry(mockOperation);
      });

      expect(result.current.retryCount).toBe(2);
    });

    it('clears conflict state on successful retry', async () => {
      const { result } = renderHook(() => useOptimisticLocking());

      // First, trigger a conflict
      const conflictError = new AlertsApiError('Conflict', 409, true);
      const mockOperation = vi.fn()
        .mockRejectedValueOnce(conflictError)
        .mockResolvedValueOnce({ status: 'success' });

      await act(async () => {
        try {
          await result.current.executeWithConflictHandling(mockOperation);
        } catch {
          // Expected
        }
      });

      expect(result.current.hasConflict).toBe(true);

      // Successful retry
      await act(async () => {
        await result.current.retry(mockOperation);
      });

      expect(result.current.hasConflict).toBe(false);
    });

    it('sets isRetrying during retry operation', async () => {
      const { result } = renderHook(() => useOptimisticLocking());

      let resolveOperation: (value: unknown) => void;
      const mockOperation = vi.fn().mockReturnValue(
        new Promise((resolve) => {
          resolveOperation = resolve;
        })
      );

      // Start retry (don't await)
      let retryPromise: Promise<unknown>;
      act(() => {
        retryPromise = result.current.retry(mockOperation);
      });

      // Should be retrying
      expect(result.current.isRetrying).toBe(true);

      // Resolve the operation
      await act(async () => {
        resolveOperation!({ status: 'success' });
        await retryPromise;
      });

      expect(result.current.isRetrying).toBe(false);
    });

    it('respects maxRetries option', async () => {
      const { result } = renderHook(() => useOptimisticLocking({ maxRetries: 2 }));

      const mockOperation = vi.fn().mockResolvedValue({ status: 'success' });

      // First retry - allowed
      await act(async () => {
        await result.current.retry(mockOperation);
      });
      expect(result.current.retryCount).toBe(1);

      // Second retry - allowed
      await act(async () => {
        await result.current.retry(mockOperation);
      });
      expect(result.current.retryCount).toBe(2);

      // Third retry - should not execute due to max retries
      await act(async () => {
        await result.current.retry(mockOperation);
      });
      // Operation should not have been called a third time
      expect(mockOperation).toHaveBeenCalledTimes(2);
    });
  });

  describe('options', () => {
    it('uses custom maxRetries', () => {
      const { result } = renderHook(() => useOptimisticLocking({ maxRetries: 5 }));
      // The hook is initialized correctly with custom options
      expect(result.current.hasConflict).toBe(false);
    });

    it('calls onConflict callback with error', async () => {
      const onConflict = vi.fn();
      const { result } = renderHook(() => useOptimisticLocking({ onConflict }));

      const conflictError = new AlertsApiError('Conflict', 409, true);
      const mockOperation = vi.fn().mockRejectedValue(conflictError);

      await act(async () => {
        try {
          await result.current.executeWithConflictHandling(mockOperation);
        } catch {
          // Expected
        }
      });

      expect(onConflict).toHaveBeenCalledTimes(1);
      expect(onConflict).toHaveBeenCalledWith(conflictError);
    });

    it('calls onRetryExhausted when max retries exceeded', async () => {
      const onRetryExhausted = vi.fn();
      const { result } = renderHook(() =>
        useOptimisticLocking({ maxRetries: 1, onRetryExhausted })
      );

      const mockOperation = vi.fn().mockResolvedValue({ status: 'success' });

      // First retry - allowed
      await act(async () => {
        await result.current.retry(mockOperation);
      });

      // Second retry - max exceeded
      await act(async () => {
        await result.current.retry(mockOperation);
      });

      expect(onRetryExhausted).toHaveBeenCalledTimes(1);
    });
  });
});
