import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  selectIsHighUsage,
  selectRateLimitUsagePercent,
  useRateLimitStore,
  type RateLimitInfo,
} from './rate-limit-store';

describe('rate-limit-store', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Reset store state before each test
    useRateLimitStore.getState().clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    // Clean up any pending timers
    useRateLimitStore.getState().clear();
  });

  describe('initial state', () => {
    it('has null current by default', () => {
      const state = useRateLimitStore.getState();
      expect(state.current).toBeNull();
    });

    it('has isLimited as false by default', () => {
      const state = useRateLimitStore.getState();
      expect(state.isLimited).toBe(false);
    });

    it('has secondsUntilReset as 0 by default', () => {
      const state = useRateLimitStore.getState();
      expect(state.secondsUntilReset).toBe(0);
    });
  });

  describe('update', () => {
    it('sets current rate limit info', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 50,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(state.current).toEqual(info);
    });

    it('sets isLimited to true when remaining is 0', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(state.isLimited).toBe(true);
    });

    it('sets isLimited to false when remaining is greater than 0', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 50,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(state.isLimited).toBe(false);
    });

    it('calculates secondsUntilReset from reset timestamp', () => {
      const now = Math.floor(Date.now() / 1000);
      const resetIn = 120; // 2 minutes
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: now + resetIn,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(state.secondsUntilReset).toBe(resetIn);
    });

    it('sets secondsUntilReset to 0 when reset time has passed', () => {
      const now = Math.floor(Date.now() / 1000);
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: now - 10, // 10 seconds ago
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(state.secondsUntilReset).toBe(0);
    });

    it('preserves retryAfter when provided', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: Math.floor(Date.now() / 1000) + 60,
        retryAfter: 30,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(state.current?.retryAfter).toBe(30);
    });
  });

  describe('auto-clear behavior', () => {
    it('auto-clears isLimited when reset time passes', () => {
      const now = Math.floor(Date.now() / 1000);
      const resetIn = 5; // 5 seconds
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: now + resetIn,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      // Initially rate limited
      expect(useRateLimitStore.getState().isLimited).toBe(true);

      // Advance time past reset
      act(() => {
        vi.advanceTimersByTime(resetIn * 1000);
      });

      // Should auto-clear
      const state = useRateLimitStore.getState();
      expect(state.isLimited).toBe(false);
      expect(state.secondsUntilReset).toBe(0);
    });

    it('clears previous timer when updating with new info', () => {
      const now = Math.floor(Date.now() / 1000);

      // First update with 10 second reset
      const info1: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: now + 10,
      };

      act(() => {
        useRateLimitStore.getState().update(info1);
      });

      // Update with new 5 second reset
      const info2: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: now + 5,
      };

      act(() => {
        useRateLimitStore.getState().update(info2);
      });

      // Advance 5 seconds - should clear now (not wait for original 10)
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(useRateLimitStore.getState().isLimited).toBe(false);
    });

    it('does not schedule auto-clear when remaining > 0', () => {
      const now = Math.floor(Date.now() / 1000);
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 50,
        reset: now + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      // Should not be limited
      expect(useRateLimitStore.getState().isLimited).toBe(false);

      // Advance time - no timer should fire
      act(() => {
        vi.advanceTimersByTime(60000);
      });

      // State should be unchanged
      expect(useRateLimitStore.getState().current).toEqual(info);
    });

    it('does not schedule auto-clear when reset time already passed', () => {
      const now = Math.floor(Date.now() / 1000);
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: now - 10, // Already passed
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      // Should be limited but with 0 seconds until reset
      const state = useRateLimitStore.getState();
      expect(state.isLimited).toBe(true);
      expect(state.secondsUntilReset).toBe(0);
    });
  });

  describe('clear', () => {
    it('resets all state to initial values', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      // Verify state is set
      expect(useRateLimitStore.getState().current).not.toBeNull();

      act(() => {
        useRateLimitStore.getState().clear();
      });

      const state = useRateLimitStore.getState();
      expect(state.current).toBeNull();
      expect(state.isLimited).toBe(false);
      expect(state.secondsUntilReset).toBe(0);
    });

    it('cancels pending auto-clear timer', () => {
      const now = Math.floor(Date.now() / 1000);
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: now + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      act(() => {
        useRateLimitStore.getState().clear();
      });

      // Advance time - no timer should fire
      act(() => {
        vi.advanceTimersByTime(60000);
      });

      // State should still be cleared (timer was cancelled)
      const state = useRateLimitStore.getState();
      expect(state.current).toBeNull();
      expect(state.isLimited).toBe(false);
    });
  });

  describe('selectRateLimitUsagePercent', () => {
    it('returns 0 when current is null', () => {
      const state = useRateLimitStore.getState();
      expect(selectRateLimitUsagePercent(state)).toBe(0);
    });

    it('returns 0 when limit is 0', () => {
      const info: RateLimitInfo = {
        limit: 0,
        remaining: 0,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(selectRateLimitUsagePercent(state)).toBe(0);
    });

    it('calculates correct percentage when half used', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 50,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(selectRateLimitUsagePercent(state)).toBe(50);
    });

    it('returns 100 when fully used', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(selectRateLimitUsagePercent(state)).toBe(100);
    });

    it('rounds to nearest integer', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 67,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(selectRateLimitUsagePercent(state)).toBe(33);
    });
  });

  describe('selectIsHighUsage', () => {
    it('returns false when usage is below 80%', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 30,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(selectIsHighUsage(state)).toBe(false);
    });

    it('returns true when usage is exactly 80%', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 20,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(selectIsHighUsage(state)).toBe(true);
    });

    it('returns true when usage is above 80%', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 10,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(selectIsHighUsage(state)).toBe(true);
    });

    it('returns true when fully rate limited (100%)', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: Math.floor(Date.now() / 1000) + 60,
      };

      act(() => {
        useRateLimitStore.getState().update(info);
      });

      const state = useRateLimitStore.getState();
      expect(selectIsHighUsage(state)).toBe(true);
    });
  });

  describe('state transitions', () => {
    it('handles transition from limited to not limited', () => {
      const now = Math.floor(Date.now() / 1000);

      // Start rate limited
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      expect(useRateLimitStore.getState().isLimited).toBe(true);

      // Update with new window where remaining > 0
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 100,
          reset: now + 120,
        });
      });

      expect(useRateLimitStore.getState().isLimited).toBe(false);
    });

    it('handles transition from not limited to limited', () => {
      const now = Math.floor(Date.now() / 1000);

      // Start not rate limited
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 50,
          reset: now + 60,
        });
      });

      expect(useRateLimitStore.getState().isLimited).toBe(false);

      // Update to rate limited
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      expect(useRateLimitStore.getState().isLimited).toBe(true);
    });

    it('handles multiple rapid updates', () => {
      const now = Math.floor(Date.now() / 1000);

      // Rapid updates
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 50,
          reset: now + 60,
        });
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 25,
          reset: now + 60,
        });
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      // Should reflect final state
      const state = useRateLimitStore.getState();
      expect(state.current?.remaining).toBe(0);
      expect(state.isLimited).toBe(true);
    });
  });
});
