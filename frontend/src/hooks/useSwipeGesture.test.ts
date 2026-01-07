import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { useSwipeGesture } from './useSwipeGesture';

describe('useSwipeGesture', () => {
  it('detects left swipe', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Simulate touch end - swipe left (end x < start x)
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 30, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).toHaveBeenCalledWith('left');
  });

  it('detects right swipe', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 30, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Simulate touch end - swipe right (end x > start x)
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).toHaveBeenCalledWith('right');
  });

  it('detects up swipe', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Simulate touch end - swipe up (end y < start y)
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 100, clientY: 30 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).toHaveBeenCalledWith('up');
  });

  it('detects down swipe', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 30 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Simulate touch end - swipe down (end y > start y)
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).toHaveBeenCalledWith('down');
  });

  it('does not trigger callback if swipe distance is below threshold', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe, threshold: 50 }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Simulate touch end - short swipe (30px < threshold 50px)
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 70, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).not.toHaveBeenCalled();
  });

  it('triggers callback if swipe distance exceeds threshold', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe, threshold: 50 }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Simulate touch end - long swipe (60px > threshold 50px)
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 40, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).toHaveBeenCalledWith('left');
  });

  it('does not trigger callback if swipe takes longer than timeout', () => {
    vi.useFakeTimers();
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe, timeout: 300 }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Advance time beyond timeout
    act(() => {
      vi.advanceTimersByTime(400);
    });

    // Simulate touch end
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 30, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).not.toHaveBeenCalled();

    vi.useRealTimers();
  });

  it('triggers callback if swipe completes within timeout', () => {
    vi.useFakeTimers();
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe, timeout: 300 }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Advance time within timeout
    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Simulate touch end
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 30, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).toHaveBeenCalledWith('left');

    vi.useRealTimers();
  });

  it('prefers horizontal swipe over vertical when both exceed threshold', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Simulate touch end - diagonal swipe with larger horizontal component
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 30, clientY: 80 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).toHaveBeenCalledWith('left');
  });

  it('prefers vertical swipe over horizontal when vertical is larger', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe }));

    const element = document.createElement('div');
    result.current(element);

    // Simulate touch start
    const touchStart = new TouchEvent('touchstart', {
      touches: [{ clientX: 100, clientY: 100 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchStart);
    });

    // Simulate touch end - diagonal swipe with larger vertical component
    const touchEnd = new TouchEvent('touchend', {
      changedTouches: [{ clientX: 80, clientY: 30 } as Touch],
    });
    act(() => {
      element.dispatchEvent(touchEnd);
    });

    expect(onSwipe).toHaveBeenCalledWith('up');
  });

  it('cleans up event listeners on unmount', () => {
    const onSwipe = vi.fn();
    const { result, unmount } = renderHook(() => useSwipeGesture({ onSwipe }));

    const element = document.createElement('div');
    const removeEventListenerSpy = vi.spyOn(element, 'removeEventListener');

    result.current(element);
    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('touchstart', expect.any(Function));
    expect(removeEventListenerSpy).toHaveBeenCalledWith('touchend', expect.any(Function));
  });

  it('does not throw when element is null', () => {
    const onSwipe = vi.fn();
    const { result } = renderHook(() => useSwipeGesture({ onSwipe }));

    expect(() => result.current(null)).not.toThrow();
  });
});
