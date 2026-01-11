import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { formatCountdown, useRateLimitCountdown } from './useRateLimitCountdown';
import { useRateLimitStore } from '../stores/rate-limit-store';

describe('useRateLimitCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Reset store state before each test
    useRateLimitStore.getState().clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    useRateLimitStore.getState().clear();
  });

  describe('formatCountdown', () => {
    it('formats 0 seconds as "0:00"', () => {
      expect(formatCountdown(0)).toBe('0:00');
    });

    it('formats negative seconds as "0:00"', () => {
      expect(formatCountdown(-10)).toBe('0:00');
    });

    it('formats single digit seconds with padding', () => {
      expect(formatCountdown(5)).toBe('0:05');
    });

    it('formats double digit seconds', () => {
      expect(formatCountdown(45)).toBe('0:45');
    });

    it('formats 60 seconds as "1:00"', () => {
      expect(formatCountdown(60)).toBe('1:00');
    });

    it('formats 90 seconds as "1:30"', () => {
      expect(formatCountdown(90)).toBe('1:30');
    });

    it('formats 125 seconds as "2:05"', () => {
      expect(formatCountdown(125)).toBe('2:05');
    });

    it('formats large values correctly', () => {
      expect(formatCountdown(3661)).toBe('61:01'); // 1 hour + 1 minute + 1 second
    });
  });

  describe('initial state', () => {
    it('returns isLimited as false when store is empty', () => {
      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.isLimited).toBe(false);
    });

    it('returns secondsRemaining as 0 when not limited', () => {
      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.secondsRemaining).toBe(0);
    });

    it('returns formattedCountdown as "0:00" when not limited', () => {
      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.formattedCountdown).toBe('0:00');
    });

    it('returns null current when store is empty', () => {
      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.current).toBeNull();
    });
  });

  describe('when rate limited', () => {
    it('reflects isLimited from store', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.isLimited).toBe(true);
    });

    it('calculates secondsRemaining from reset timestamp', () => {
      const now = Math.floor(Date.now() / 1000);
      const resetIn = 90;

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + resetIn,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.secondsRemaining).toBe(resetIn);
    });

    it('provides formatted countdown string', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 90,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.formattedCountdown).toBe('1:30');
    });

    it('provides current rate limit info', () => {
      const now = Math.floor(Date.now() / 1000);
      const reset = now + 60;

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset,
          retryAfter: 30,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.current).toEqual({
        limit: 100,
        remaining: 0,
        reset,
        retryAfter: 30,
      });
    });
  });

  describe('countdown updates', () => {
    it('decrements secondsRemaining every second', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 10,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.secondsRemaining).toBe(10);

      // Advance 1 second
      act(() => {
        vi.advanceTimersByTime(1000);
      });

      expect(result.current.secondsRemaining).toBe(9);

      // Advance 2 more seconds
      act(() => {
        vi.advanceTimersByTime(2000);
      });

      expect(result.current.secondsRemaining).toBe(7);
    });

    it('updates formattedCountdown as time passes', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 65,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.formattedCountdown).toBe('1:05');

      // Advance 10 seconds
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(result.current.formattedCountdown).toBe('0:55');
    });

    it('stops at 0 and does not go negative', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 3,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      // Advance past reset time
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(result.current.secondsRemaining).toBe(0);
      expect(result.current.formattedCountdown).toBe('0:00');
    });

    it('clears interval when countdown reaches 0', () => {
      const now = Math.floor(Date.now() / 1000);
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 2,
        });
      });

      renderHook(() => useRateLimitCountdown());

      // Advance past reset time
      act(() => {
        vi.advanceTimersByTime(3000);
      });

      // Interval should have been cleared
      expect(clearIntervalSpy).toHaveBeenCalled();

      clearIntervalSpy.mockRestore();
    });
  });

  describe('store updates', () => {
    it('responds to store updates while mounted', () => {
      const now = Math.floor(Date.now() / 1000);

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.isLimited).toBe(false);

      // Update store while hook is mounted
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 30,
        });
      });

      expect(result.current.isLimited).toBe(true);
      expect(result.current.secondsRemaining).toBe(30);
    });

    it('resets countdown when store is cleared', () => {
      const now = Math.floor(Date.now() / 1000);

      // Start with rate limit
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.isLimited).toBe(true);

      // Clear store
      act(() => {
        useRateLimitStore.getState().clear();
      });

      expect(result.current.isLimited).toBe(false);
      expect(result.current.secondsRemaining).toBe(0);
    });

    it('restarts countdown when new rate limit is applied', () => {
      const now = Math.floor(Date.now() / 1000);

      // Initial rate limit
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 30,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.secondsRemaining).toBe(30);

      // Advance 10 seconds
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(result.current.secondsRemaining).toBe(20);

      // New rate limit with longer reset
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 90, // Will be 80 seconds from now after 10 second advance
        });
      });

      expect(result.current.secondsRemaining).toBe(80);
    });
  });

  describe('cleanup', () => {
    it('clears interval on unmount', () => {
      const now = Math.floor(Date.now() / 1000);
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      const { unmount } = renderHook(() => useRateLimitCountdown());

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();

      clearIntervalSpy.mockRestore();
    });

    it('does not leak timers when store updates rapidly', () => {
      const now = Math.floor(Date.now() / 1000);
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

      const { result } = renderHook(() => useRateLimitCountdown());

      // Rapid updates
      for (let i = 0; i < 10; i++) {
        act(() => {
          useRateLimitStore.getState().update({
            limit: 100,
            remaining: 0,
            reset: now + 60 + i,
          });
        });
      }

      // Should have the latest countdown
      expect(result.current.secondsRemaining).toBeGreaterThan(0);

      // Each update should clear previous interval (except first)
      // clearInterval should be called for each update after the first
      expect(clearIntervalSpy.mock.calls.length).toBeGreaterThanOrEqual(9);

      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    });
  });

  describe('edge cases', () => {
    it('handles reset time in the past', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now - 10, // 10 seconds ago
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.secondsRemaining).toBe(0);
      expect(result.current.formattedCountdown).toBe('0:00');
    });

    it('handles remaining > 0 (not rate limited)', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 50,
          reset: now + 60,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.isLimited).toBe(false);
      expect(result.current.secondsRemaining).toBe(0);
    });

    it('handles very large reset times', () => {
      const now = Math.floor(Date.now() / 1000);
      const oneHour = 3600;

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + oneHour,
        });
      });

      const { result } = renderHook(() => useRateLimitCountdown());

      expect(result.current.secondsRemaining).toBe(oneHour);
      expect(result.current.formattedCountdown).toBe('60:00');
    });
  });
});
