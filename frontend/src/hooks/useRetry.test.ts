/**
 * Tests for useRetry hook (NEM-2297)
 *
 * Tests automatic retry with exponential backoff for 429 responses.
 */

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  useRetry,
  useRetryStore,
  useActiveRetries,
  useHasActiveRetries,
  parseRetryAfter,
  calculateBackoff,
  formatRetryCountdown,
  generateRetryId,
  DEFAULT_RETRY_CONFIG,
} from './useRetry';

describe('useRetry', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Reset store state before each test
    useRetryStore.getState().clearAll();
  });

  afterEach(() => {
    vi.useRealTimers();
    useRetryStore.getState().clearAll();
  });

  describe('parseRetryAfter', () => {
    it('returns null for null input', () => {
      expect(parseRetryAfter(null)).toBeNull();
    });

    it('parses seconds format', () => {
      expect(parseRetryAfter('120')).toBe(120000);
    });

    it('parses zero seconds', () => {
      expect(parseRetryAfter('0')).toBe(0);
    });

    it('parses HTTP-date format', () => {
      const futureDate = new Date(Date.now() + 60000);
      const result = parseRetryAfter(futureDate.toUTCString());
      expect(result).toBeGreaterThan(0);
      expect(result).toBeLessThanOrEqual(60000);
    });

    it('returns 0 for past HTTP-date', () => {
      const pastDate = new Date(Date.now() - 60000);
      expect(parseRetryAfter(pastDate.toUTCString())).toBe(0);
    });

    it('returns null for invalid input', () => {
      expect(parseRetryAfter('invalid')).toBeNull();
    });

    it('returns null for empty string', () => {
      // Empty string is falsy, returns null early
      expect(parseRetryAfter('')).toBeNull();
    });

    it('returns 0 for negative seconds (parsed as past date)', () => {
      // Negative values fail the >= 0 check, fall through to date parsing
      // "-5" is parsed as year "-5" which is in the past, so returns 0
      expect(parseRetryAfter('-5')).toBe(0);
    });
  });

  describe('calculateBackoff', () => {
    it('uses Retry-After when available and configured', () => {
      const result = calculateBackoff(1, DEFAULT_RETRY_CONFIG, 5000);
      expect(result).toBe(5000);
    });

    it('caps Retry-After at maxDelay', () => {
      const result = calculateBackoff(1, DEFAULT_RETRY_CONFIG, 60000);
      expect(result).toBe(DEFAULT_RETRY_CONFIG.maxDelay);
    });

    it('uses exponential backoff when no Retry-After', () => {
      // Attempt 1: baseDelay * 2^0 = 1000
      expect(calculateBackoff(1, DEFAULT_RETRY_CONFIG, null)).toBe(1000);
      // Attempt 2: baseDelay * 2^1 = 2000
      expect(calculateBackoff(2, DEFAULT_RETRY_CONFIG, null)).toBe(2000);
      // Attempt 3: baseDelay * 2^2 = 4000
      expect(calculateBackoff(3, DEFAULT_RETRY_CONFIG, null)).toBe(4000);
    });

    it('caps exponential backoff at maxDelay', () => {
      const result = calculateBackoff(10, DEFAULT_RETRY_CONFIG, null);
      expect(result).toBe(DEFAULT_RETRY_CONFIG.maxDelay);
    });

    it('ignores Retry-After when useRetryAfter is false', () => {
      const config = { ...DEFAULT_RETRY_CONFIG, useRetryAfter: false };
      const result = calculateBackoff(1, config, 5000);
      expect(result).toBe(1000); // exponential backoff
    });

    it('ignores zero or negative Retry-After', () => {
      expect(calculateBackoff(1, DEFAULT_RETRY_CONFIG, 0)).toBe(1000);
      expect(calculateBackoff(1, DEFAULT_RETRY_CONFIG, -100)).toBe(1000);
    });
  });

  describe('formatRetryCountdown', () => {
    it('formats seconds correctly', () => {
      expect(formatRetryCountdown(1000)).toBe('1 second');
      expect(formatRetryCountdown(5000)).toBe('5 seconds');
      expect(formatRetryCountdown(59000)).toBe('59 seconds');
    });

    it('handles singular second', () => {
      expect(formatRetryCountdown(1000)).toBe('1 second');
      expect(formatRetryCountdown(1500)).toBe('2 seconds'); // rounds up
    });

    it('formats minutes correctly', () => {
      expect(formatRetryCountdown(60000)).toBe('1 minute');
      expect(formatRetryCountdown(120000)).toBe('2 minutes');
    });

    it('formats minutes and seconds', () => {
      expect(formatRetryCountdown(90000)).toBe('1 minute 30 seconds');
      expect(formatRetryCountdown(125000)).toBe('2 minutes 5 seconds');
    });

    it('handles edge cases', () => {
      expect(formatRetryCountdown(0)).toBe('0 seconds');
      expect(formatRetryCountdown(500)).toBe('1 second');
    });
  });

  describe('generateRetryId', () => {
    it('generates unique IDs', () => {
      const id1 = generateRetryId();
      const id2 = generateRetryId();
      expect(id1).not.toBe(id2);
    });

    it('starts with "retry-" prefix', () => {
      const id = generateRetryId();
      expect(id).toMatch(/^retry-/);
    });
  });

  describe('useRetryStore', () => {
    it('starts with empty retries', () => {
      const { retries } = useRetryStore.getState();
      expect(retries.size).toBe(0);
    });

    it('can set and get a retry', () => {
      const retryState = {
        id: 'test-1',
        attempt: 1,
        maxAttempts: 3,
        secondsRemaining: 10,
        cancelled: false,
        url: '/api/test',
        retryAt: Date.now() + 10000,
      };

      act(() => {
        useRetryStore.getState().setRetry('test-1', retryState);
      });

      const { retries } = useRetryStore.getState();
      expect(retries.get('test-1')).toEqual(retryState);
    });

    it('can remove a retry', () => {
      const retryState = {
        id: 'test-1',
        attempt: 1,
        maxAttempts: 3,
        secondsRemaining: 10,
        cancelled: false,
        url: '/api/test',
        retryAt: Date.now() + 10000,
      };

      act(() => {
        useRetryStore.getState().setRetry('test-1', retryState);
        useRetryStore.getState().removeRetry('test-1');
      });

      const { retries } = useRetryStore.getState();
      expect(retries.get('test-1')).toBeUndefined();
    });

    it('can cancel a retry', () => {
      const retryState = {
        id: 'test-1',
        attempt: 1,
        maxAttempts: 3,
        secondsRemaining: 10,
        cancelled: false,
        url: '/api/test',
        retryAt: Date.now() + 10000,
      };

      act(() => {
        useRetryStore.getState().setRetry('test-1', retryState);
        useRetryStore.getState().cancelRetry('test-1');
      });

      const { retries } = useRetryStore.getState();
      expect(retries.get('test-1')?.cancelled).toBe(true);
    });

    it('can update countdown', () => {
      const retryState = {
        id: 'test-1',
        attempt: 1,
        maxAttempts: 3,
        secondsRemaining: 10,
        cancelled: false,
        url: '/api/test',
        retryAt: Date.now() + 10000,
      };

      act(() => {
        useRetryStore.getState().setRetry('test-1', retryState);
        useRetryStore.getState().updateCountdown('test-1', 5);
      });

      const { retries } = useRetryStore.getState();
      expect(retries.get('test-1')?.secondsRemaining).toBe(5);
    });

    it('can clear all retries', () => {
      act(() => {
        useRetryStore.getState().setRetry('test-1', {
          id: 'test-1',
          attempt: 1,
          maxAttempts: 3,
          secondsRemaining: 10,
          cancelled: false,
          url: '/api/test',
          retryAt: Date.now() + 10000,
        });
        useRetryStore.getState().setRetry('test-2', {
          id: 'test-2',
          attempt: 1,
          maxAttempts: 3,
          secondsRemaining: 10,
          cancelled: false,
          url: '/api/test2',
          retryAt: Date.now() + 10000,
        });
        useRetryStore.getState().clearAll();
      });

      const { retries } = useRetryStore.getState();
      expect(retries.size).toBe(0);
    });
  });

  describe('useRetry hook', () => {
    it('returns initial state with no active retries', () => {
      const { result } = renderHook(() => useRetry());

      expect(result.current.activeRetries).toEqual([]);
      expect(result.current.hasActiveRetries).toBe(false);
    });

    it('provides queueRetry function', () => {
      const { result } = renderHook(() => useRetry());

      expect(typeof result.current.queueRetry).toBe('function');
    });

    it('provides cancelRetry function', () => {
      const { result } = renderHook(() => useRetry());

      expect(typeof result.current.cancelRetry).toBe('function');
    });

    it('provides cancelAllRetries function', () => {
      const { result } = renderHook(() => useRetry());

      expect(typeof result.current.cancelAllRetries).toBe('function');
    });

    it('accepts custom config', () => {
      const customConfig = {
        maxRetries: 5,
        baseDelay: 500,
        maxDelay: 10000,
      };

      const { result } = renderHook(() => useRetry(customConfig));

      expect(result.current.hasActiveRetries).toBe(false);
    });

    it('queues a retry and shows active state', () => {
      const { result } = renderHook(() => useRetry());
      const mockExecute = vi.fn().mockResolvedValue('success');

      act(() => {
        void result.current.queueRetry(mockExecute, '/api/test', 2000);
      });

      // Should have an active retry
      expect(result.current.hasActiveRetries).toBe(true);
      expect(result.current.activeRetries.length).toBe(1);
      expect(result.current.activeRetries[0].url).toBe('/api/test');
    });

    it('executes retry after delay', async () => {
      const { result } = renderHook(() => useRetry());
      const mockExecute = vi.fn().mockResolvedValue('success');

      let promiseResult: unknown;
      let promiseError: Error | undefined;

      act(() => {
        result.current.queueRetry(mockExecute, '/api/test', 2000)
          .then((res) => {
            promiseResult = res;
          })
          .catch((err: Error) => {
            promiseError = err;
          });
      });

      // Advance past the delay and flush promises
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2500);
      });

      // Verify the execute function was called
      expect(mockExecute).toHaveBeenCalledTimes(1);
      expect(promiseResult).toBe('success');
      expect(promiseError).toBeUndefined();
    });

    it('retries on failure up to maxRetries', async () => {
      const { result } = renderHook(() =>
        useRetry({ maxRetries: 3, baseDelay: 100, maxDelay: 1000 })
      );
      const mockExecute = vi.fn().mockRejectedValue(new Error('Failed'));

      let rejectedError: Error | undefined;

      act(() => {
        result.current.queueRetry(mockExecute, '/api/test', 100).catch((err) => {
          rejectedError = err;
        });
      });

      // Advance through all retry attempts (100ms, 200ms, 400ms = 700ms total)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });

      // Should have attempted 3 times (the max)
      expect(mockExecute).toHaveBeenCalledTimes(3);
      expect(rejectedError?.message).toBe('Failed');
    });

    it('cancels a retry and rejects promise', async () => {
      const { result } = renderHook(() => useRetry());
      const mockExecute = vi.fn().mockResolvedValue('success');

      let rejectedError: Error | undefined;

      act(() => {
        result.current.queueRetry(mockExecute, '/api/test', 5000).catch((err) => {
          rejectedError = err;
        });
      });

      // Wait for store state to update
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      // Get retry ID after state has propagated
      const retryId = result.current.activeRetries[0]?.id;
      expect(retryId).toBeDefined();

      // Cancel the retry
      act(() => {
        if (retryId) {
          result.current.cancelRetry(retryId);
        }
      });

      // Allow promise rejection to propagate
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      expect(rejectedError?.message).toBe('Retry cancelled by user');
      expect(mockExecute).not.toHaveBeenCalled();
    });

    it('cancelAllRetries cancels all pending retries', async () => {
      const { result } = renderHook(() => useRetry());
      const mockExecute1 = vi.fn().mockResolvedValue('success1');
      const mockExecute2 = vi.fn().mockResolvedValue('success2');

      const errors: Error[] = [];

      act(() => {
        void result.current.queueRetry(mockExecute1, '/api/test1', 5000).catch((err: unknown) => {
          errors.push(err as Error);
        });
        void result.current.queueRetry(mockExecute2, '/api/test2', 5000).catch((err: unknown) => {
          errors.push(err as Error);
        });
      });

      expect(result.current.activeRetries.length).toBe(2);

      // Cancel all
      act(() => {
        result.current.cancelAllRetries();
      });

      // Allow promise rejections to propagate
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      expect(errors.length).toBe(2);
      expect(errors.every((e) => e.message === 'Retry cancelled by user')).toBe(true);
      expect(mockExecute1).not.toHaveBeenCalled();
      expect(mockExecute2).not.toHaveBeenCalled();
    });

    it('updates countdown every second', async () => {
      const { result } = renderHook(() => useRetry());
      const mockExecute = vi.fn().mockResolvedValue('success');

      act(() => {
        void result.current.queueRetry(mockExecute, '/api/test', 5000);
      });

      const initialSeconds = result.current.activeRetries[0]?.secondsRemaining;
      expect(initialSeconds).toBe(5);

      // Advance 1 second
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });

      expect(result.current.activeRetries[0]?.secondsRemaining).toBe(4);
    });

    it('cleans up on unmount', () => {
      const { result, unmount } = renderHook(() => useRetry());
      const mockExecute = vi.fn().mockResolvedValue('success');

      act(() => {
        void result.current.queueRetry(mockExecute, '/api/test', 5000);
      });

      unmount();

      // Timer should be cleared (no error thrown)
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(mockExecute).not.toHaveBeenCalled();
    });
  });

  describe('useActiveRetries', () => {
    it('returns empty array when no retries', () => {
      const { result } = renderHook(() => useActiveRetries());
      expect(result.current).toEqual([]);
    });

    it('returns active retries from store', () => {
      act(() => {
        useRetryStore.getState().setRetry('test-1', {
          id: 'test-1',
          attempt: 1,
          maxAttempts: 3,
          secondsRemaining: 10,
          cancelled: false,
          url: '/api/test',
          retryAt: Date.now() + 10000,
        });
      });

      const { result } = renderHook(() => useActiveRetries());
      expect(result.current.length).toBe(1);
      expect(result.current[0].id).toBe('test-1');
    });

    it('excludes cancelled retries', () => {
      act(() => {
        useRetryStore.getState().setRetry('test-1', {
          id: 'test-1',
          attempt: 1,
          maxAttempts: 3,
          secondsRemaining: 10,
          cancelled: true,
          url: '/api/test',
          retryAt: Date.now() + 10000,
        });
      });

      const { result } = renderHook(() => useActiveRetries());
      expect(result.current).toEqual([]);
    });
  });

  describe('useHasActiveRetries', () => {
    it('returns false when no retries', () => {
      const { result } = renderHook(() => useHasActiveRetries());
      expect(result.current).toBe(false);
    });

    it('returns true when there are active retries', () => {
      act(() => {
        useRetryStore.getState().setRetry('test-1', {
          id: 'test-1',
          attempt: 1,
          maxAttempts: 3,
          secondsRemaining: 10,
          cancelled: false,
          url: '/api/test',
          retryAt: Date.now() + 10000,
        });
      });

      const { result } = renderHook(() => useHasActiveRetries());
      expect(result.current).toBe(true);
    });

    it('returns false when all retries are cancelled', () => {
      act(() => {
        useRetryStore.getState().setRetry('test-1', {
          id: 'test-1',
          attempt: 1,
          maxAttempts: 3,
          secondsRemaining: 10,
          cancelled: true,
          url: '/api/test',
          retryAt: Date.now() + 10000,
        });
      });

      const { result } = renderHook(() => useHasActiveRetries());
      expect(result.current).toBe(false);
    });
  });
});
