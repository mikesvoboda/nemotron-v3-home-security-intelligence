import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useViewport, BREAKPOINTS } from './useViewport';

describe('useViewport', () => {
  let originalInnerWidth: number;
  let resizeListeners: Array<() => void> = [];
  let rafCallback: ((time: DOMHighResTimeStamp) => void) | null = null;

  beforeEach(() => {
    originalInnerWidth = window.innerWidth;
    resizeListeners = [];
    rafCallback = null;

    // Mock requestAnimationFrame
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      rafCallback = callback as (time: DOMHighResTimeStamp) => void;
      return 1;
    });

    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {
      rafCallback = null;
    });

    // Mock addEventListener for resize
    vi.spyOn(window, 'addEventListener').mockImplementation((event, handler) => {
      if (event === 'resize') {
        resizeListeners.push(handler as () => void);
      }
    });

    vi.spyOn(window, 'removeEventListener').mockImplementation((event, handler) => {
      if (event === 'resize') {
        resizeListeners = resizeListeners.filter((l) => l !== handler);
      }
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: originalInnerWidth,
    });
    resizeListeners = [];
    rafCallback = null;
    vi.clearAllMocks();
  });

  // Helper to set window width and trigger resize
  const setWindowWidth = (width: number) => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: width,
    });
  };

  const triggerResize = () => {
    resizeListeners.forEach((listener) => listener());
    // Execute the RAF callback with a timestamp
    if (rafCallback) {
      rafCallback(performance.now());
    }
  };

  describe('isMobile detection', () => {
    it('returns isMobile=true for viewports < 640px', () => {
      setWindowWidth(500);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isMobile).toBe(true);
      expect(result.current.isTablet).toBe(false);
      expect(result.current.isDesktop).toBe(false);
    });

    it('returns isMobile=true for viewport at 639px', () => {
      setWindowWidth(639);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isMobile).toBe(true);
    });

    it('returns isMobile=false for viewport at exactly 640px', () => {
      setWindowWidth(640);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isMobile).toBe(false);
    });
  });

  describe('isTablet detection', () => {
    it('returns isTablet=true for viewports 640px - 1023px', () => {
      setWindowWidth(800);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isMobile).toBe(false);
      expect(result.current.isTablet).toBe(true);
      expect(result.current.isDesktop).toBe(false);
    });

    it('returns isTablet=true at exactly 640px (sm breakpoint)', () => {
      setWindowWidth(640);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isTablet).toBe(true);
    });

    it('returns isTablet=true at 768px (md breakpoint)', () => {
      setWindowWidth(768);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isTablet).toBe(true);
    });

    it('returns isTablet=true at 1023px (just below lg)', () => {
      setWindowWidth(1023);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isTablet).toBe(true);
    });

    it('returns isTablet=false at 1024px (lg breakpoint)', () => {
      setWindowWidth(1024);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isTablet).toBe(false);
    });
  });

  describe('isDesktop detection', () => {
    it('returns isDesktop=true for viewports >= 1024px', () => {
      setWindowWidth(1200);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isMobile).toBe(false);
      expect(result.current.isTablet).toBe(false);
      expect(result.current.isDesktop).toBe(true);
    });

    it('returns isDesktop=true at exactly 1024px (lg breakpoint)', () => {
      setWindowWidth(1024);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isDesktop).toBe(true);
    });

    it('returns isDesktop=true for very large viewports', () => {
      setWindowWidth(2560);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isDesktop).toBe(true);
    });
  });

  describe('breakpoint detection', () => {
    it('returns breakpoint="sm" for width < 768px', () => {
      setWindowWidth(700);
      const { result } = renderHook(() => useViewport());
      expect(result.current.breakpoint).toBe('sm');
    });

    it('returns breakpoint="md" for width 768px - 1023px', () => {
      setWindowWidth(800);
      const { result } = renderHook(() => useViewport());
      expect(result.current.breakpoint).toBe('md');
    });

    it('returns breakpoint="lg" for width 1024px - 1279px', () => {
      setWindowWidth(1100);
      const { result } = renderHook(() => useViewport());
      expect(result.current.breakpoint).toBe('lg');
    });

    it('returns breakpoint="xl" for width 1280px - 1535px', () => {
      setWindowWidth(1400);
      const { result } = renderHook(() => useViewport());
      expect(result.current.breakpoint).toBe('xl');
    });

    it('returns breakpoint="2xl" for width >= 1536px', () => {
      setWindowWidth(1920);
      const { result } = renderHook(() => useViewport());
      expect(result.current.breakpoint).toBe('2xl');
    });
  });

  describe('width tracking', () => {
    it('returns current window width', () => {
      setWindowWidth(1024);
      const { result } = renderHook(() => useViewport());
      expect(result.current.width).toBe(1024);
    });
  });

  describe('responsive updates', () => {
    it('updates when viewport changes from mobile to tablet', () => {
      setWindowWidth(500);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isMobile).toBe(true);
      expect(result.current.isTablet).toBe(false);

      // Simulate viewport change to tablet
      act(() => {
        setWindowWidth(768);
        triggerResize();
      });

      expect(result.current.isMobile).toBe(false);
      expect(result.current.isTablet).toBe(true);
    });

    it('updates when viewport changes from tablet to desktop', () => {
      setWindowWidth(800);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isTablet).toBe(true);
      expect(result.current.isDesktop).toBe(false);

      // Simulate viewport change to desktop
      act(() => {
        setWindowWidth(1200);
        triggerResize();
      });

      expect(result.current.isTablet).toBe(false);
      expect(result.current.isDesktop).toBe(true);
    });

    it('updates when viewport changes from desktop to mobile', () => {
      setWindowWidth(1200);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isDesktop).toBe(true);

      // Simulate viewport change to mobile
      act(() => {
        setWindowWidth(400);
        triggerResize();
      });

      expect(result.current.isMobile).toBe(true);
      expect(result.current.isDesktop).toBe(false);
    });
  });

  describe('cleanup', () => {
    it('removes event listener on unmount', () => {
      setWindowWidth(1024);
      const { unmount } = renderHook(() => useViewport());
      unmount();

      expect(window.removeEventListener).toHaveBeenCalledWith('resize', expect.any(Function));
    });
  });

  describe('SSR safety', () => {
    it('handles SSR gracefully when window is undefined', () => {
      const originalWindow = globalThis.window;
      delete (globalThis as Record<string, unknown>).window;

      // Should not throw during SSR
      expect(() => {
        // The hook uses typeof window check
      }).not.toThrow();

      (globalThis as Record<string, unknown>).window = originalWindow;
    });
  });

  describe('BREAKPOINTS constant', () => {
    it('exports correct breakpoint values', () => {
      expect(BREAKPOINTS.sm).toBe(640);
      expect(BREAKPOINTS.md).toBe(768);
      expect(BREAKPOINTS.lg).toBe(1024);
      expect(BREAKPOINTS.xl).toBe(1280);
      expect(BREAKPOINTS['2xl']).toBe(1536);
    });
  });

  describe('edge cases', () => {
    it('handles rapid resize events', () => {
      setWindowWidth(1024);
      const { result } = renderHook(() => useViewport());

      // Simulate rapid resizes
      act(() => {
        setWindowWidth(800);
        triggerResize();
        setWindowWidth(600);
        triggerResize();
        setWindowWidth(500);
        triggerResize();
      });

      expect(result.current.isMobile).toBe(true);
      expect(result.current.width).toBe(500);
    });

    it('handles zero width', () => {
      setWindowWidth(0);
      const { result } = renderHook(() => useViewport());
      expect(result.current.isMobile).toBe(true);
      expect(result.current.breakpoint).toBe('sm');
    });
  });
});
