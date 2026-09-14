/**
 * Tests for useNetworkStatus hook
 * TDD: RED phase - Write tests first
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';

// Direct import to avoid barrel file memory issues
import { useNetworkStatus } from './useNetworkStatus';

describe('useNetworkStatus', () => {
  // Store original navigator.onLine
  const originalOnLine = navigator.onLine;

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset navigator.onLine to true by default
    Object.defineProperty(navigator, 'onLine', {
      value: true,
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    // Restore original value
    Object.defineProperty(navigator, 'onLine', {
      value: originalOnLine,
      writable: true,
      configurable: true,
    });
  });

  it('returns true when browser is online', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(true);
    expect(result.current.isOffline).toBe(false);
  });

  it('returns false when browser is offline', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(false);
    expect(result.current.isOffline).toBe(true);
  });

  it('updates status when online event fires', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(false);

    // Simulate going online
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
      window.dispatchEvent(new Event('online'));
    });

    await waitFor(() => {
      expect(result.current.isOnline).toBe(true);
    });
  });

  it('updates status when offline event fires', async () => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(true);

    // Simulate going offline
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
      window.dispatchEvent(new Event('offline'));
    });

    await waitFor(() => {
      expect(result.current.isOnline).toBe(false);
      expect(result.current.isOffline).toBe(true);
    });
  });

  it('calls onOnline callback when coming back online', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });

    const onOnline = vi.fn();
    const { result } = renderHook(() => useNetworkStatus({ onOnline }));

    expect(result.current.isOnline).toBe(false);

    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
      window.dispatchEvent(new Event('online'));
    });

    await waitFor(() => {
      expect(onOnline).toHaveBeenCalledTimes(1);
    });
  });

  it('calls onOffline callback when going offline', async () => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });

    const onOffline = vi.fn();
    const { result } = renderHook(() => useNetworkStatus({ onOffline }));

    expect(result.current.isOnline).toBe(true);

    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
      window.dispatchEvent(new Event('offline'));
    });

    await waitFor(() => {
      expect(onOffline).toHaveBeenCalledTimes(1);
    });
  });

  it('cleans up event listeners on unmount', () => {
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

    const { unmount } = renderHook(() => useNetworkStatus());

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('online', expect.any(Function));
    expect(removeEventListenerSpy).toHaveBeenCalledWith('offline', expect.any(Function));

    removeEventListenerSpy.mockRestore();
  });

  it('tracks time since last online', () => {
    vi.useFakeTimers();
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });

    const { result } = renderHook(() => useNetworkStatus());

    // Initially online, so lastOnlineAt should be set
    expect(result.current.lastOnlineAt).toBeInstanceOf(Date);

    // Go offline
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
      window.dispatchEvent(new Event('offline'));
    });

    // Advance time by 5 seconds
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // Still offline, lastOnlineAt should remain the same
    expect(result.current.isOffline).toBe(true);

    // Go back online
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
      window.dispatchEvent(new Event('online'));
    });

    // lastOnlineAt should be updated
    expect(result.current.lastOnlineAt).toBeInstanceOf(Date);

    vi.useRealTimers();
  });

  it('provides wasOffline flag after reconnecting', async () => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });

    const { result } = renderHook(() => useNetworkStatus());

    // Initially online, wasOffline should be false
    expect(result.current.wasOffline).toBe(false);

    // Go offline
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
      window.dispatchEvent(new Event('offline'));
    });

    await waitFor(() => {
      expect(result.current.isOffline).toBe(true);
    });

    // Go back online
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
      window.dispatchEvent(new Event('online'));
    });

    await waitFor(() => {
      expect(result.current.isOnline).toBe(true);
      expect(result.current.wasOffline).toBe(true);
    });
  });

  it('resets wasOffline flag when clearWasOffline is called', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });

    const { result } = renderHook(() => useNetworkStatus());

    // Go online to trigger wasOffline
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
      window.dispatchEvent(new Event('online'));
    });

    await waitFor(() => {
      expect(result.current.wasOffline).toBe(true);
    });

    // Clear the flag
    act(() => {
      result.current.clearWasOffline();
    });

    expect(result.current.wasOffline).toBe(false);
  });
});
