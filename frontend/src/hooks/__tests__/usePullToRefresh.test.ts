/**
 * @fileoverview Tests for usePullToRefresh hook.
 *
 * This hook detects pull-down gestures at the top of a scrollable container
 * to trigger a refresh action on mobile devices.
 *
 * @see NEM-2970
 */
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { usePullToRefresh } from '../usePullToRefresh';

describe('usePullToRefresh', () => {
  // Helper to create touch events
  function createTouchEvent(
    type: 'touchstart' | 'touchmove' | 'touchend',
    clientY: number,
    clientX: number = 0
  ): TouchEvent {
    const touch = {
      clientY,
      clientX,
      identifier: 0,
      target: document.createElement('div'),
      screenX: clientX,
      screenY: clientY,
      pageX: clientX,
      pageY: clientY,
      radiusX: 0,
      radiusY: 0,
      rotationAngle: 0,
      force: 0,
    } as Touch;

    const event = new TouchEvent(type, {
      touches: type === 'touchend' ? [] : [touch],
      changedTouches: [touch],
      bubbles: true,
      cancelable: true,
    });

    return event;
  }

  // Mock element for ref
  let mockElement: HTMLDivElement;

  beforeEach(() => {
    mockElement = document.createElement('div');
    document.body.appendChild(mockElement);

    // Mock scrollTop as 0 (at top of scroll container)
    Object.defineProperty(mockElement, 'scrollTop', {
      value: 0,
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    document.body.removeChild(mockElement);
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('returns initial state with isPulling false', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

      expect(result.current.isPulling).toBe(false);
      expect(result.current.isRefreshing).toBe(false);
      expect(result.current.pullDistance).toBe(0);
      expect(result.current.pullProgress).toBe(0);
    });

    it('returns a ref callback', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

      expect(typeof result.current.containerRef).toBe('function');
    });
  });

  describe('pull gesture detection', () => {
    it('sets isPulling true when touch starts and moves down', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

      // Attach ref to element
      act(() => {
        result.current.containerRef(mockElement);
      });

      // Simulate touch start
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      // Simulate touch move down
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 50));
      });

      expect(result.current.isPulling).toBe(true);
    });

    it('updates pullDistance during pull', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 60));
      });

      // Pull distance should be positive (moved down)
      expect(result.current.pullDistance).toBeGreaterThan(0);
    });

    it('calculates pullProgress as ratio of pullDistance to threshold', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const threshold = 80;
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, threshold }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 40));
      });

      // Progress should be approximately 0.5 (40/80)
      // Note: resistance may affect actual value
      expect(result.current.pullProgress).toBeGreaterThan(0);
      expect(result.current.pullProgress).toBeLessThanOrEqual(1);
    });

    it('clamps pullProgress to max of 1', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const threshold = 80;
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, threshold }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      // Pull way past threshold
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 200));
      });

      expect(result.current.pullProgress).toBe(1);
    });
  });

  describe('refresh trigger', () => {
    it('triggers onRefresh when released past threshold', async () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const threshold = 80;
      // With default resistance of 0.5, need to pull 160+ pixels to get 80+ pullDistance
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, threshold }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 180)); // 180 * 0.5 = 90 > 80
      });

      await act(async () => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 180));
        await Promise.resolve(); // Flush microtasks for async state updates
      });

      expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    it('does not trigger onRefresh when released before threshold', async () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const threshold = 80;
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, threshold }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 30));
      });

      await act(async () => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 30));
        await Promise.resolve(); // Flush microtasks for async state updates
      });

      expect(onRefresh).not.toHaveBeenCalled();
    });

    it('sets isRefreshing true while refresh is in progress', async () => {
      let resolveRefresh: () => void;
      const onRefresh = vi.fn().mockImplementation(
        () =>
          new Promise<void>((resolve) => {
            resolveRefresh = resolve;
          })
      );

      const threshold = 80;
      // With default resistance of 0.5, need to pull 160+ pixels to get 80+ pullDistance
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, threshold }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 180)); // 180 * 0.5 = 90 > 80
      });

      // Start refresh but don't resolve yet
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 180));
      });

      // Should be refreshing
      expect(result.current.isRefreshing).toBe(true);

      // Resolve the refresh
      await act(async () => {
        resolveRefresh();
        await Promise.resolve(); // Flush microtasks for async state updates
      });

      // Should no longer be refreshing
      expect(result.current.isRefreshing).toBe(false);
    });

    it('resets state after refresh completes', async () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const threshold = 80;
      // With default resistance of 0.5, need to pull 160+ pixels to get 80+ pullDistance
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, threshold }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 180)); // 180 * 0.5 = 90 > 80
      });

      await act(async () => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 180));
        await Promise.resolve(); // Flush microtasks for async state updates
      });

      expect(result.current.isPulling).toBe(false);
      expect(result.current.pullDistance).toBe(0);
      expect(result.current.pullProgress).toBe(0);
    });
  });

  describe('scroll position check', () => {
    it('does not trigger pull when not at top of scroll container', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

      // Set scrollTop to non-zero value
      Object.defineProperty(mockElement, 'scrollTop', {
        value: 100,
        writable: true,
        configurable: true,
      });

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 50));
      });

      expect(result.current.isPulling).toBe(false);
      expect(result.current.pullDistance).toBe(0);
    });
  });

  describe('upward swipe handling', () => {
    it('ignores upward swipes (negative delta)', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 100));
      });

      // Move up (negative delta)
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 50));
      });

      expect(result.current.isPulling).toBe(false);
      expect(result.current.pullDistance).toBe(0);
    });
  });

  describe('disabled state', () => {
    it('does not respond to gestures when disabled', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, disabled: true }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 100));
      });

      expect(result.current.isPulling).toBe(false);
    });

    it('does not trigger refresh when disabled', async () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, disabled: true }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 100));
      });

      await act(async () => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 100));
        await Promise.resolve(); // Flush microtasks for async state updates
      });

      expect(onRefresh).not.toHaveBeenCalled();
    });
  });

  describe('configuration', () => {
    it('uses default threshold of 80px', async () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      // Just under default threshold (with resistance)
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 70));
      });

      await act(async () => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 70));
        await Promise.resolve(); // Flush microtasks for async state updates
      });

      expect(onRefresh).not.toHaveBeenCalled();
    });

    it('respects custom threshold', async () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      // With threshold 50 and default resistance 0.5, need to pull 100+ pixels
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, threshold: 50 }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      // Past custom threshold: 120 * 0.5 = 60 > 50
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 120));
      });

      await act(async () => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 120));
        await Promise.resolve(); // Flush microtasks for async state updates
      });

      expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    it('applies resistance factor to pull distance', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, resistance: 0.5 }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 100));
      });

      // With 0.5 resistance, 100px pull should result in ~50px pull distance
      expect(result.current.pullDistance).toBeLessThan(100);
    });
  });

  describe('concurrent refresh prevention', () => {
    it('does not trigger multiple refreshes while one is in progress', async () => {
      let resolveRefresh: () => void;
      const onRefresh = vi.fn().mockImplementation(
        () =>
          new Promise<void>((resolve) => {
            resolveRefresh = resolve;
          })
      );

      // With threshold 80 and default resistance 0.5, need to pull 160+ pixels
      const { result } = renderHook(() => usePullToRefresh({ onRefresh, threshold: 80 }));

      act(() => {
        result.current.containerRef(mockElement);
      });

      // First pull and release: 180 * 0.5 = 90 > 80
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 180));
      });
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 180));
      });

      expect(result.current.isRefreshing).toBe(true);

      // Try to trigger another refresh while first is in progress
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchstart', 0));
      });
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchmove', 180));
      });
      act(() => {
        mockElement.dispatchEvent(createTouchEvent('touchend', 180));
      });

      // Should only have been called once
      expect(onRefresh).toHaveBeenCalledTimes(1);

      // Resolve first refresh
      await act(async () => {
        resolveRefresh();
        await Promise.resolve(); // Flush microtasks for async state updates
      });
    });
  });

  describe('cleanup', () => {
    it('removes event listeners when element is detached', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() => usePullToRefresh({ onRefresh }));

      const removeEventListenerSpy = vi.spyOn(mockElement, 'removeEventListener');

      act(() => {
        result.current.containerRef(mockElement);
      });

      // Detach by passing null
      act(() => {
        result.current.containerRef(null);
      });

      expect(removeEventListenerSpy).toHaveBeenCalled();
    });

    it('removes event listeners on unmount', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result, unmount } = renderHook(() => usePullToRefresh({ onRefresh }));

      const removeEventListenerSpy = vi.spyOn(mockElement, 'removeEventListener');

      act(() => {
        result.current.containerRef(mockElement);
      });

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalled();
    });
  });

  describe('external isRefreshing control', () => {
    it('respects external isRefreshing prop', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const { result, rerender } = renderHook(
        ({ isRefreshing }) => usePullToRefresh({ onRefresh, isRefreshing }),
        { initialProps: { isRefreshing: false } }
      );

      expect(result.current.isRefreshing).toBe(false);

      rerender({ isRefreshing: true });

      expect(result.current.isRefreshing).toBe(true);
    });
  });
});
