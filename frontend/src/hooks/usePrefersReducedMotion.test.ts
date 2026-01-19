import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { usePrefersReducedMotion } from './usePrefersReducedMotion';

describe('usePrefersReducedMotion', () => {
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

  it('returns false when reduced motion is not preferred', () => {
    matchMediaMock.mockReturnValue({
      matches: false,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });

    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);
  });

  it('returns true when reduced motion is preferred', () => {
    matchMediaMock.mockReturnValue({
      matches: true,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });

    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);
  });

  it('queries the correct media query string', () => {
    matchMediaMock.mockReturnValue({
      matches: false,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });

    renderHook(() => usePrefersReducedMotion());

    expect(matchMediaMock).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)');
  });

  it('updates when preference changes from no-preference to reduce', () => {
    const mediaQuery = {
      matches: false,
      media: '(prefers-reduced-motion: reduce)',
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

    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);

    // Simulate preference change to reduce
    act(() => {
      mediaQuery.matches = true;
      listeners.forEach((listener) => {
        listener({
          matches: true,
          media: '(prefers-reduced-motion: reduce)',
        } as MediaQueryListEvent);
      });
    });

    expect(result.current).toBe(true);
  });

  it('updates when preference changes from reduce to no-preference', () => {
    const mediaQuery = {
      matches: true,
      media: '(prefers-reduced-motion: reduce)',
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

    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);

    // Simulate preference change to no-preference
    act(() => {
      mediaQuery.matches = false;
      listeners.forEach((listener) => {
        listener({
          matches: false,
          media: '(prefers-reduced-motion: reduce)',
        } as MediaQueryListEvent);
      });
    });

    expect(result.current).toBe(false);
  });

  it('cleans up event listener on unmount', () => {
    const removeEventListenerSpy = vi.fn();
    matchMediaMock.mockReturnValue({
      matches: false,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: removeEventListenerSpy,
      dispatchEvent: vi.fn(),
    });

    const { unmount } = renderHook(() => usePrefersReducedMotion());
    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('handles SSR gracefully when window.matchMedia is undefined', () => {
    const originalMatchMedia = window.matchMedia;
    // @ts-expect-error Testing SSR scenario
    delete window.matchMedia;

    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);

    window.matchMedia = originalMatchMedia;
  });

  it('handles multiple preference changes', () => {
    const mediaQuery = {
      matches: false,
      media: '(prefers-reduced-motion: reduce)',
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

    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);

    // First change: enable reduced motion
    act(() => {
      mediaQuery.matches = true;
      listeners.forEach((listener) => {
        listener({
          matches: true,
          media: '(prefers-reduced-motion: reduce)',
        } as MediaQueryListEvent);
      });
    });
    expect(result.current).toBe(true);

    // Second change: disable reduced motion
    act(() => {
      mediaQuery.matches = false;
      listeners.forEach((listener) => {
        listener({
          matches: false,
          media: '(prefers-reduced-motion: reduce)',
        } as MediaQueryListEvent);
      });
    });
    expect(result.current).toBe(false);

    // Third change: enable again
    act(() => {
      mediaQuery.matches = true;
      listeners.forEach((listener) => {
        listener({
          matches: true,
          media: '(prefers-reduced-motion: reduce)',
        } as MediaQueryListEvent);
      });
    });
    expect(result.current).toBe(true);
  });
});
