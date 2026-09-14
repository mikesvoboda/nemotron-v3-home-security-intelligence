import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useChartDimensions } from './useChartDimensions';

/**
 * Creates a mock ResizeObserverEntry for testing
 */
function createMockEntry(target: Element, width: number): Partial<ResizeObserverEntry> {
  return {
    contentRect: {
      width,
      height: 0,
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: width,
      bottom: 0,
    } as DOMRectReadOnly,
    target,
  };
}

describe('useChartDimensions', () => {
  let resizeObserverCallbacks: ResizeObserverCallback[] = [];
  let mockDisconnect: ReturnType<typeof vi.fn>;
  let originalResizeObserver: typeof ResizeObserver;
  let originalMatchMedia: typeof window.matchMedia;

  beforeEach(() => {
    resizeObserverCallbacks = [];
    mockDisconnect = vi.fn();

    // Save originals
    originalResizeObserver = globalThis.ResizeObserver;
    originalMatchMedia = window.matchMedia;

    // Mock ResizeObserver with callback support using a class
    globalThis.ResizeObserver = class MockResizeObserver {
      constructor(callback: ResizeObserverCallback) {
        resizeObserverCallbacks.push(callback);
      }
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = mockDisconnect;
    } as unknown as typeof ResizeObserver;

    // Mock window.matchMedia for mobile detection - default to desktop
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    resizeObserverCallbacks = [];
    vi.clearAllMocks();

    // Restore originals
    globalThis.ResizeObserver = originalResizeObserver;
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: originalMatchMedia,
    });
  });

  describe('basic dimensions', () => {
    it('returns responsive dimensions with default options', () => {
      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() => useChartDimensions(mockRef));

      expect(result.current).toEqual({
        width: 0,
        height: 150, // minHeight default
        isMobile: false,
        isCompact: false,
      });
    });

    it('calculates height based on aspect ratio', () => {
      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() =>
        useChartDimensions(mockRef, { aspectRatio: 16 / 9, debounceMs: 0 })
      );

      // Initial width is 0, so height should be minHeight
      expect(result.current.height).toBe(150);

      // Simulate container resize
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 320) as ResizeObserverEntry], mockObserver);
        });
      });

      // Height should be calculated from aspect ratio: 320 / (16/9) = 180
      expect(result.current.width).toBe(320);
      expect(result.current.height).toBe(180);
    });

    it('respects minHeight constraint', () => {
      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() =>
        useChartDimensions(mockRef, { minHeight: 200, aspectRatio: 16 / 9, debounceMs: 0 })
      );

      // Simulate small container
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 100) as ResizeObserverEntry], mockObserver);
        });
      });

      // Height would be 100 / (16/9) = 56.25, but minHeight is 200
      expect(result.current.height).toBe(200);
    });

    it('respects maxHeight constraint', () => {
      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() =>
        useChartDimensions(mockRef, { maxHeight: 300, aspectRatio: 16 / 9, debounceMs: 0 })
      );

      // Simulate large container
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 1000) as ResizeObserverEntry], mockObserver);
        });
      });

      // Height would be 1000 / (16/9) = 562.5, but maxHeight is 300
      expect(result.current.height).toBe(300);
    });

    it('uses fixedHeight when provided', () => {
      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() =>
        useChartDimensions(mockRef, { fixedHeight: 250, aspectRatio: 16 / 9, debounceMs: 0 })
      );

      // Simulate resize
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 500) as ResizeObserverEntry], mockObserver);
        });
      });

      // fixedHeight should override aspect ratio calculation
      expect(result.current.height).toBe(250);
    });
  });

  describe('mobile detection', () => {
    it('detects mobile viewport (< 768px)', () => {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: vi.fn((query: string) => ({
          matches: query.includes('max-width: 768px') || query.includes('max-width: 400px'),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() => useChartDimensions(mockRef));

      expect(result.current.isMobile).toBe(true);
    });

    it('reduces maxHeight on mobile (max 220px)', () => {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: vi.fn((query: string) => ({
          matches: query.includes('max-width: 768px'),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() =>
        useChartDimensions(mockRef, { maxHeight: 400, aspectRatio: 16 / 9, debounceMs: 0 })
      );

      // Simulate resize
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 600) as ResizeObserverEntry], mockObserver);
        });
      });

      // Height would be 600 / (16/9) = 337.5, but mobile max is 220
      expect(result.current.height).toBeLessThanOrEqual(220);
      expect(result.current.isMobile).toBe(true);
    });
  });

  describe('compact detection', () => {
    it('detects compact viewport (< 400px)', () => {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: vi.fn((query: string) => ({
          matches: query.includes('max-width: 400px') || query.includes('max-width: 768px'),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() => useChartDimensions(mockRef));

      expect(result.current.isCompact).toBe(true);
    });

    it('reduces maxHeight further on compact (max 180px)', () => {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: vi.fn((query: string) => ({
          matches: query.includes('max-width: 400px') || query.includes('max-width: 768px'),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() =>
        useChartDimensions(mockRef, { maxHeight: 400, aspectRatio: 16 / 9, debounceMs: 0 })
      );

      // Simulate resize
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 350) as ResizeObserverEntry], mockObserver);
        });
      });

      // Height should be capped at 180px for compact
      expect(result.current.height).toBeLessThanOrEqual(180);
      expect(result.current.isCompact).toBe(true);
    });
  });

  describe('debouncing', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('debounces resize events', () => {
      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() => useChartDimensions(mockRef, { debounceMs: 100 }));

      // Simulate multiple rapid resize events
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 200) as ResizeObserverEntry], mockObserver);
        });
      });

      // Width should not update immediately
      expect(result.current.width).toBe(0);

      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 300) as ResizeObserverEntry], mockObserver);
        });
      });

      expect(result.current.width).toBe(0);

      // Advance timers past debounce delay
      act(() => {
        vi.advanceTimersByTime(100);
      });

      // Now width should be the last value
      expect(result.current.width).toBe(300);
    });
  });

  describe('cleanup', () => {
    it('disconnects ResizeObserver on unmount', () => {
      const mockRef = { current: document.createElement('div') };
      const { unmount } = renderHook(() => useChartDimensions(mockRef));

      unmount();

      expect(mockDisconnect).toHaveBeenCalled();
    });
  });

  describe('null ref handling', () => {
    it('handles null ref gracefully', () => {
      const mockRef = { current: null };
      const { result } = renderHook(() => useChartDimensions(mockRef));

      expect(result.current).toEqual({
        width: 0,
        height: 150,
        isMobile: false,
        isCompact: false,
      });
    });
  });

  describe('responsive behavior', () => {
    it('updates dimensions when container resizes', () => {
      const mockRef = { current: document.createElement('div') };
      const { result } = renderHook(() =>
        useChartDimensions(mockRef, { aspectRatio: 16 / 9, debounceMs: 0 })
      );

      // Initial dimensions
      expect(result.current.width).toBe(0);

      // First resize
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 400) as ResizeObserverEntry], mockObserver);
        });
      });

      expect(result.current.width).toBe(400);

      // Second resize
      act(() => {
        const mockObserver = {} as ResizeObserver;
        resizeObserverCallbacks.forEach((callback) => {
          callback([createMockEntry(mockRef.current, 600) as ResizeObserverEntry], mockObserver);
        });
      });

      expect(result.current.width).toBe(600);
    });
  });
});
