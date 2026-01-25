import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import {
  useMediaQuery,
  useIsMobile,
  useIsTouch,
  usePrefersReducedMotion,
  MOBILE_BREAKPOINT,
} from './useMediaQuery';

describe('useMediaQuery', () => {
  let matchMediaMock: ReturnType<typeof vi.fn>;
  let listeners: Array<(e: MediaQueryListEvent) => void> = [];

  const createMediaQueryMock = (matches: boolean, query: string) => ({
    matches,
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
  });

  beforeEach(() => {
    listeners = [];
    matchMediaMock = vi.fn((query: string) => createMediaQueryMock(false, query));
    window.matchMedia = matchMediaMock as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    listeners = [];
    vi.clearAllMocks();
  });

  describe('useMediaQuery (generic)', () => {
    it('returns false when query does not match', () => {
      matchMediaMock.mockReturnValue(createMediaQueryMock(false, '(max-width: 768px)'));

      const { result } = renderHook(() => useMediaQuery('(max-width: 768px)'));
      expect(result.current).toBe(false);
    });

    it('returns true when query matches', () => {
      matchMediaMock.mockReturnValue(createMediaQueryMock(true, '(max-width: 768px)'));

      const { result } = renderHook(() => useMediaQuery('(max-width: 768px)'));
      expect(result.current).toBe(true);
    });

    it('updates when media query changes', () => {
      const mediaQuery = createMediaQueryMock(false, '(max-width: 768px)');
      matchMediaMock.mockReturnValue(mediaQuery);

      const { result } = renderHook(() => useMediaQuery('(max-width: 768px)'));
      expect(result.current).toBe(false);

      // Simulate media query change
      act(() => {
        mediaQuery.matches = true;
        listeners.forEach((listener) => {
          listener({ matches: true, media: '(max-width: 768px)' } as MediaQueryListEvent);
        });
      });

      expect(result.current).toBe(true);
    });

    it('passes the correct query string to matchMedia', () => {
      const customQuery = '(prefers-color-scheme: dark)';
      matchMediaMock.mockReturnValue(createMediaQueryMock(false, customQuery));

      renderHook(() => useMediaQuery(customQuery));

      expect(matchMediaMock).toHaveBeenCalledWith(customQuery);
    });

    it('cleans up event listener on unmount', () => {
      const mediaQuery = createMediaQueryMock(false, '(max-width: 768px)');
      matchMediaMock.mockReturnValue(mediaQuery);

      const { unmount } = renderHook(() => useMediaQuery('(max-width: 768px)'));
      unmount();

      expect(mediaQuery.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
    });

    it('handles SSR gracefully when window.matchMedia is undefined', () => {
      const originalMatchMedia = window.matchMedia;
      // @ts-expect-error Testing SSR scenario
      delete window.matchMedia;

      const { result } = renderHook(() => useMediaQuery('(max-width: 768px)'));
      expect(result.current).toBe(false);

      window.matchMedia = originalMatchMedia;
    });

    it('re-subscribes when query changes', () => {
      const mediaQuery768 = createMediaQueryMock(true, '(max-width: 768px)');
      const mediaQuery640 = createMediaQueryMock(false, '(max-width: 640px)');

      matchMediaMock.mockImplementation((query: string) => {
        if (query === '(max-width: 768px)') return mediaQuery768;
        if (query === '(max-width: 640px)') return mediaQuery640;
        return createMediaQueryMock(false, query);
      });

      const { result, rerender } = renderHook(({ query }) => useMediaQuery(query), {
        initialProps: { query: '(max-width: 768px)' },
      });

      expect(result.current).toBe(true);

      rerender({ query: '(max-width: 640px)' });

      expect(result.current).toBe(false);
      expect(mediaQuery768.removeEventListener).toHaveBeenCalled();
    });
  });

  describe('useIsMobile', () => {
    it('returns false for desktop viewports by default', () => {
      matchMediaMock.mockReturnValue(
        createMediaQueryMock(false, `(max-width: ${MOBILE_BREAKPOINT}px)`)
      );

      const { result } = renderHook(() => useIsMobile());
      expect(result.current).toBe(false);
    });

    it('returns true for mobile viewports', () => {
      matchMediaMock.mockReturnValue(
        createMediaQueryMock(true, `(max-width: ${MOBILE_BREAKPOINT}px)`)
      );

      const { result } = renderHook(() => useIsMobile());
      expect(result.current).toBe(true);
    });

    it('uses default breakpoint of 768px', () => {
      matchMediaMock.mockReturnValue(createMediaQueryMock(false, '(max-width: 768px)'));

      renderHook(() => useIsMobile());

      expect(matchMediaMock).toHaveBeenCalledWith('(max-width: 768px)');
    });

    it('accepts custom breakpoint', () => {
      matchMediaMock.mockReturnValue(createMediaQueryMock(false, '(max-width: 640px)'));

      renderHook(() => useIsMobile(640));

      expect(matchMediaMock).toHaveBeenCalledWith('(max-width: 640px)');
    });

    it('updates when viewport changes from desktop to mobile', () => {
      const mediaQuery = createMediaQueryMock(false, '(max-width: 768px)');
      matchMediaMock.mockReturnValue(mediaQuery);

      const { result } = renderHook(() => useIsMobile());
      expect(result.current).toBe(false);

      act(() => {
        mediaQuery.matches = true;
        listeners.forEach((listener) => {
          listener({ matches: true, media: '(max-width: 768px)' } as MediaQueryListEvent);
        });
      });

      expect(result.current).toBe(true);
    });

    it('updates when viewport changes from mobile to desktop', () => {
      const mediaQuery = createMediaQueryMock(true, '(max-width: 768px)');
      matchMediaMock.mockReturnValue(mediaQuery);

      const { result } = renderHook(() => useIsMobile());
      expect(result.current).toBe(true);

      act(() => {
        mediaQuery.matches = false;
        listeners.forEach((listener) => {
          listener({ matches: false, media: '(max-width: 768px)' } as MediaQueryListEvent);
        });
      });

      expect(result.current).toBe(false);
    });
  });

  describe('useIsTouch', () => {
    it('returns false for non-touch devices', () => {
      matchMediaMock.mockReturnValue(createMediaQueryMock(false, '(pointer: coarse)'));

      const { result } = renderHook(() => useIsTouch());
      expect(result.current).toBe(false);
    });

    it('returns true for touch devices', () => {
      matchMediaMock.mockReturnValue(createMediaQueryMock(true, '(pointer: coarse)'));

      const { result } = renderHook(() => useIsTouch());
      expect(result.current).toBe(true);
    });

    it('uses correct pointer query', () => {
      matchMediaMock.mockReturnValue(createMediaQueryMock(false, '(pointer: coarse)'));

      renderHook(() => useIsTouch());

      expect(matchMediaMock).toHaveBeenCalledWith('(pointer: coarse)');
    });
  });

  describe('usePrefersReducedMotion', () => {
    it('returns false when user does not prefer reduced motion', () => {
      matchMediaMock.mockReturnValue(
        createMediaQueryMock(false, '(prefers-reduced-motion: reduce)')
      );

      const { result } = renderHook(() => usePrefersReducedMotion());
      expect(result.current).toBe(false);
    });

    it('returns true when user prefers reduced motion', () => {
      matchMediaMock.mockReturnValue(
        createMediaQueryMock(true, '(prefers-reduced-motion: reduce)')
      );

      const { result } = renderHook(() => usePrefersReducedMotion());
      expect(result.current).toBe(true);
    });

    it('uses correct reduced motion query', () => {
      matchMediaMock.mockReturnValue(
        createMediaQueryMock(false, '(prefers-reduced-motion: reduce)')
      );

      renderHook(() => usePrefersReducedMotion());

      expect(matchMediaMock).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)');
    });
  });

  describe('MOBILE_BREAKPOINT constant', () => {
    it('is 768px (matches Tailwind md breakpoint)', () => {
      expect(MOBILE_BREAKPOINT).toBe(768);
    });
  });
});
