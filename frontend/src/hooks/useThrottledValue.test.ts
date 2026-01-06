import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useThrottledValue } from './useThrottledValue';

describe('useThrottledValue', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Basic Throttling', () => {
    it('returns initial value immediately with leading=true (default)', () => {
      const { result } = renderHook(() => useThrottledValue(10));
      expect(result.current).toBe(10);
    });

    it('returns initial value immediately with leading=true explicitly', () => {
      const { result } = renderHook(() =>
        useThrottledValue(10, { leading: true })
      );
      expect(result.current).toBe(10);
    });

    it('returns initial value with leading=false', () => {
      const { result } = renderHook(() =>
        useThrottledValue(10, { leading: false })
      );
      expect(result.current).toBe(10);
    });

    it('throttles rapid value updates', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: 1 } }
      );

      expect(result.current).toBe(1);

      // Rapid updates
      rerender({ value: 2 });
      rerender({ value: 3 });
      rerender({ value: 4 });
      rerender({ value: 5 });

      // Value should still be 1 (throttled)
      expect(result.current).toBe(1);

      // Advance time past throttle interval
      act(() => {
        vi.advanceTimersByTime(500);
      });

      // Should now have the latest value (5)
      expect(result.current).toBe(5);
    });

    it('updates after interval even with single value change', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: 1 } }
      );

      expect(result.current).toBe(1);

      rerender({ value: 2 });

      // Value should still be 1 (throttled)
      expect(result.current).toBe(1);

      // Advance time past throttle interval
      act(() => {
        vi.advanceTimersByTime(500);
      });

      // Should now have the new value
      expect(result.current).toBe(2);
    });
  });

  describe('Default Interval', () => {
    it('uses 500ms as default interval', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value),
        { initialProps: { value: 1 } }
      );

      expect(result.current).toBe(1);

      rerender({ value: 2 });
      expect(result.current).toBe(1);

      // Advance 400ms - should still be throttled
      act(() => {
        vi.advanceTimersByTime(400);
      });
      expect(result.current).toBe(1);

      // Advance remaining 100ms
      act(() => {
        vi.advanceTimersByTime(100);
      });
      expect(result.current).toBe(2);
    });
  });

  describe('Custom Interval', () => {
    it('respects custom interval of 100ms', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 100 }),
        { initialProps: { value: 1 } }
      );

      rerender({ value: 2 });
      expect(result.current).toBe(1);

      act(() => {
        vi.advanceTimersByTime(100);
      });
      expect(result.current).toBe(2);
    });

    it('respects custom interval of 1000ms', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 1000 }),
        { initialProps: { value: 1 } }
      );

      rerender({ value: 2 });
      expect(result.current).toBe(1);

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBe(1);

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBe(2);
    });
  });

  describe('Multiple Throttle Cycles', () => {
    it('handles multiple throttle cycles correctly', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: 1 } }
      );

      // First cycle
      rerender({ value: 2 });
      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBe(2);

      // Second cycle
      rerender({ value: 3 });
      expect(result.current).toBe(2);

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBe(3);

      // Third cycle
      rerender({ value: 4 });
      rerender({ value: 5 });
      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBe(5);
    });
  });

  describe('Object Values', () => {
    it('works with object values', () => {
      interface TestObject {
        count: number;
        data: string[];
      }

      const { result, rerender } = renderHook(
        ({ value }: { value: TestObject }) =>
          useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: { count: 1, data: ['a'] } } }
      );

      expect(result.current).toEqual({ count: 1, data: ['a'] });

      rerender({ value: { count: 2, data: ['a', 'b'] } });
      expect(result.current).toEqual({ count: 1, data: ['a'] });

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toEqual({ count: 2, data: ['a', 'b'] });
    });
  });

  describe('Array Values', () => {
    it('works with array values', () => {
      const { result, rerender } = renderHook(
        ({ value }: { value: number[] }) =>
          useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: [1, 2, 3] } }
      );

      expect(result.current).toEqual([1, 2, 3]);

      rerender({ value: [4, 5, 6] });
      expect(result.current).toEqual([1, 2, 3]);

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toEqual([4, 5, 6]);
    });

    it('handles empty array to populated array', () => {
      const { result, rerender } = renderHook(
        ({ value }: { value: number[] }) =>
          useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: [] as number[] } }
      );

      expect(result.current).toEqual([]);

      rerender({ value: [1, 2, 3] });
      expect(result.current).toEqual([]);

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toEqual([1, 2, 3]);
    });
  });

  describe('Null and Undefined Values', () => {
    it('handles null values', () => {
      const { result, rerender } = renderHook(
        ({ value }: { value: number | null }) =>
          useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: null as number | null } }
      );

      expect(result.current).toBeNull();

      rerender({ value: 5 });
      expect(result.current).toBeNull();

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBe(5);
    });

    it('handles undefined values', () => {
      const { result, rerender } = renderHook(
        ({ value }: { value: number | undefined }) =>
          useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: undefined as number | undefined } }
      );

      expect(result.current).toBeUndefined();

      rerender({ value: 10 });
      expect(result.current).toBeUndefined();

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBe(10);
    });

    it('handles transitions from value to null', () => {
      const { result, rerender } = renderHook(
        ({ value }: { value: number | null }) =>
          useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: 5 as number | null } }
      );

      expect(result.current).toBe(5);

      rerender({ value: null });
      expect(result.current).toBe(5);

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBeNull();
    });
  });

  describe('Edge Cases', () => {
    it('handles same value updates without unnecessary re-renders', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: 1 } }
      );

      expect(result.current).toBe(1);

      rerender({ value: 1 });
      expect(result.current).toBe(1);

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(result.current).toBe(1);
    });

    it('handles zero interval gracefully', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 0 }),
        { initialProps: { value: 1 } }
      );

      expect(result.current).toBe(1);

      rerender({ value: 2 });

      // With 0 interval, should update immediately after timeout
      act(() => {
        vi.advanceTimersByTime(0);
      });
      expect(result.current).toBe(2);
    });

    it('handles very large interval', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 60000 }),
        { initialProps: { value: 1 } }
      );

      rerender({ value: 2 });
      expect(result.current).toBe(1);

      act(() => {
        vi.advanceTimersByTime(30000);
      });
      expect(result.current).toBe(1);

      act(() => {
        vi.advanceTimersByTime(30000);
      });
      expect(result.current).toBe(2);
    });
  });

  describe('Cleanup', () => {
    it('cleans up timeout on unmount', () => {
      const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout');

      const { rerender, unmount } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: 1 } }
      );

      rerender({ value: 2 });

      unmount();

      // clearTimeout should have been called during cleanup
      expect(clearTimeoutSpy).toHaveBeenCalled();

      clearTimeoutSpy.mockRestore();
    });

    it('does not update state after unmount', () => {
      const { result, rerender, unmount } = renderHook(
        ({ value }) => useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: 1 } }
      );

      rerender({ value: 2 });
      unmount();

      // Advance timers after unmount - should not cause errors
      act(() => {
        vi.advanceTimersByTime(500);
      });

      // Result should still be the last value before unmount
      expect(result.current).toBe(1);
    });
  });

  describe('Type Safety', () => {
    it('preserves generic type', () => {
      interface CustomType {
        id: number;
        name: string;
      }

      const initialValue: CustomType = { id: 1, name: 'test' };

      const { result } = renderHook(() => useThrottledValue(initialValue));

      // TypeScript should infer the correct type
      const value: CustomType = result.current;
      expect(value.id).toBe(1);
      expect(value.name).toBe('test');
    });
  });

  describe('WebSocket Use Case Simulation', () => {
    it('handles rapid WebSocket-style updates efficiently', () => {
      const { result, rerender } = renderHook(
        ({ value }: { value: { riskScore: number; timestamp: number }[] }) =>
          useThrottledValue(value, { interval: 500 }),
        { initialProps: { value: [] as { riskScore: number; timestamp: number }[] } }
      );

      // Simulate 10 rapid WebSocket messages within 200ms
      for (let i = 1; i <= 10; i++) {
        rerender({ value: [{ riskScore: i * 10, timestamp: Date.now() + i }] });
      }

      // Should still show empty array (initial value)
      expect(result.current).toEqual([]);

      // After throttle interval, should show the latest value
      act(() => {
        vi.advanceTimersByTime(500);
      });

      expect(result.current).toEqual([{ riskScore: 100, timestamp: expect.any(Number) }]);
    });
  });
});
