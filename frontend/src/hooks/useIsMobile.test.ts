import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useIsMobile } from './useIsMobile';

describe('useIsMobile', () => {
  let matchMediaMock: ReturnType<typeof vi.fn>;
  let listeners: Array<(e: MediaQueryListEvent) => void> = [];

  beforeEach(() => {
    listeners = [];
    matchMediaMock = vi.fn((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((event: string, handler: (e: MediaQueryListEvent) => void) => {
        if (event === 'change') {
          listeners.push(handler);
        }
      }),
      removeEventListener: vi.fn((event: string, handler: (e: MediaQueryListEvent) => void) => {
        if (event === 'change') {
          listeners = listeners.filter((l) => l !== handler);
        }
      }),
      dispatchEvent: vi.fn(),
    }));
    window.matchMedia = matchMediaMock as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    listeners = [];
    vi.clearAllMocks();
  });

  it('returns false for desktop viewports by default', () => {
    matchMediaMock.mockReturnValue({
      matches: false,
      media: '(max-width: 768px)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });

  it('returns true for mobile viewports', () => {
    matchMediaMock.mockReturnValue({
      matches: true,
      media: '(max-width: 768px)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it('updates when viewport changes from desktop to mobile', () => {
    const mediaQuery = {
      matches: false,
      media: '(max-width: 768px)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((event: string, handler: (e: MediaQueryListEvent) => void) => {
        if (event === 'change') {
          listeners.push(handler);
        }
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    };

    matchMediaMock.mockReturnValue(mediaQuery);

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    // Simulate viewport change to mobile
    act(() => {
      mediaQuery.matches = true;
      listeners.forEach((listener) => {
        listener({ matches: true, media: '(max-width: 768px)' } as MediaQueryListEvent);
      });
    });

    expect(result.current).toBe(true);
  });

  it('updates when viewport changes from mobile to desktop', () => {
    const mediaQuery = {
      matches: true,
      media: '(max-width: 768px)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((event: string, handler: (e: MediaQueryListEvent) => void) => {
        if (event === 'change') {
          listeners.push(handler);
        }
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    };

    matchMediaMock.mockReturnValue(mediaQuery);

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);

    // Simulate viewport change to desktop
    act(() => {
      mediaQuery.matches = false;
      listeners.forEach((listener) => {
        listener({ matches: false, media: '(max-width: 768px)' } as MediaQueryListEvent);
      });
    });

    expect(result.current).toBe(false);
  });

  it('accepts custom breakpoint', () => {
    matchMediaMock.mockReturnValue({
      matches: false,
      media: '(max-width: 640px)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });

    const { result } = renderHook(() => useIsMobile(640));

    expect(matchMediaMock).toHaveBeenCalledWith('(max-width: 640px)');
    expect(result.current).toBe(false);
  });

  it('cleans up event listener on unmount', () => {
    const removeEventListenerSpy = vi.fn();
    matchMediaMock.mockReturnValue({
      matches: false,
      media: '(max-width: 768px)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: removeEventListenerSpy,
      dispatchEvent: vi.fn(),
    });

    const { unmount } = renderHook(() => useIsMobile());
    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('handles SSR gracefully when window.matchMedia is undefined', () => {
    const originalMatchMedia = window.matchMedia;
    // @ts-expect-error Testing SSR scenario
    delete window.matchMedia;

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    window.matchMedia = originalMatchMedia;
  });
});
