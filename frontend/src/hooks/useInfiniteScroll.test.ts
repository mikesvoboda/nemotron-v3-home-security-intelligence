import { renderHook, act, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import { useInfiniteScroll } from './useInfiniteScroll';

// Mock IntersectionObserver
class MockIntersectionObserver {
  callback: IntersectionObserverCallback;
  elements: Element[] = [];
  options: IntersectionObserverInit | undefined;

  static instances: MockIntersectionObserver[] = [];

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.options = options;
    MockIntersectionObserver.instances.push(this);
  }

  observe(element: Element) {
    this.elements.push(element);
  }

  unobserve(element: Element) {
    this.elements = this.elements.filter((el) => el !== element);
  }

  disconnect() {
    this.elements = [];
  }

  // Helper to trigger intersection
  triggerIntersection(isIntersecting: boolean) {
    const entries = this.elements.map((element) => ({
      isIntersecting,
      target: element,
      boundingClientRect: {} as DOMRectReadOnly,
      intersectionRatio: isIntersecting ? 1 : 0,
      intersectionRect: {} as DOMRectReadOnly,
      rootBounds: null,
      time: Date.now(),
    }));
    this.callback(entries, this as unknown as IntersectionObserver);
  }

  static clearInstances() {
    MockIntersectionObserver.instances = [];
  }

  static getLastInstance(): MockIntersectionObserver | undefined {
    return MockIntersectionObserver.instances[MockIntersectionObserver.instances.length - 1];
  }
}

describe('useInfiniteScroll', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    MockIntersectionObserver.clearInstances();
    // @ts-expect-error - Mocking IntersectionObserver
    global.IntersectionObserver = MockIntersectionObserver;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('returns expected properties', () => {
      const onLoadMore = vi.fn();

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      expect(result.current.sentinelRef).toBeTypeOf('function');
      expect(result.current.isLoadingMore).toBe(false);
      expect(result.current.error).toBe(null);
      expect(result.current.retry).toBeTypeOf('function');
      expect(result.current.clearError).toBeTypeOf('function');
    });

    it('creates IntersectionObserver when sentinel is attached', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      expect(MockIntersectionObserver.instances).toHaveLength(1);
      expect(MockIntersectionObserver.getLastInstance()?.elements).toContain(mockElement);
    });

    it('uses provided threshold and rootMargin', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          threshold: 0.5,
          rootMargin: '200px',
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      const observer = MockIntersectionObserver.getLastInstance();
      expect(observer?.options?.threshold).toBe(0.5);
      expect(observer?.options?.rootMargin).toBe('200px');
    });
  });

  describe('loading behavior', () => {
    it('calls onLoadMore when sentinel intersects', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // Trigger intersection
      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });
    });

    it('sets isLoadingMore to true while loading', async () => {
      let resolveLoad: () => void;
      const loadPromise = new Promise<void>((resolve) => {
        resolveLoad = resolve;
      });
      const onLoadMore = vi.fn().mockReturnValue(loadPromise);
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // Trigger intersection
      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      await waitFor(() => {
        expect(result.current.isLoadingMore).toBe(true);
      });

      // Resolve the load
      await act(async () => {
        resolveLoad!();
        await loadPromise;
      });

      expect(result.current.isLoadingMore).toBe(false);
    });

    it('does not call onLoadMore when hasMore is false', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: false,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // Trigger intersection
      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      expect(onLoadMore).not.toHaveBeenCalled();
    });

    it('does not call onLoadMore when disabled', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          enabled: false,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // Observer should not be created when disabled
      expect(MockIntersectionObserver.instances).toHaveLength(0);
    });

    it('does not call onLoadMore when isLoading is true', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // Trigger intersection
      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      expect(onLoadMore).not.toHaveBeenCalled();
    });

    it('prevents duplicate calls while loading', async () => {
      let resolveLoad: () => void;
      const loadPromise = new Promise<void>((resolve) => {
        resolveLoad = resolve;
      });
      const onLoadMore = vi.fn().mockReturnValue(loadPromise);
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // Trigger intersection multiple times
      act(() => {
        const observer = MockIntersectionObserver.getLastInstance();
        observer?.triggerIntersection(true);
        observer?.triggerIntersection(true);
        observer?.triggerIntersection(true);
      });

      // Should only call once
      expect(onLoadMore).toHaveBeenCalledTimes(1);

      // Resolve the load
      await act(async () => {
        resolveLoad!();
        await loadPromise;
      });
    });

    it('does not call onLoadMore when not intersecting', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // Trigger non-intersection
      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(false);
      });

      expect(onLoadMore).not.toHaveBeenCalled();
    });
  });

  describe('error handling', () => {
    it('sets error state when onLoadMore fails', async () => {
      const error = new Error('Load failed');
      const onLoadMore = vi.fn().mockRejectedValue(error);
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      await waitFor(() => {
        expect(result.current.error).toEqual(error);
      });

      expect(result.current.isLoadingMore).toBe(false);
    });

    it('converts non-Error rejections to Error objects', async () => {
      const onLoadMore = vi.fn().mockRejectedValue('String error');
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe('String error');
      });
    });

    it('calls onError callback when provided', async () => {
      const error = new Error('Load failed');
      const onLoadMore = vi.fn().mockRejectedValue(error);
      const onError = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          onError,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(error);
      });
    });

    it('clears error on retry', async () => {
      const error = new Error('Load failed');
      const onLoadMore = vi.fn().mockRejectedValueOnce(error).mockResolvedValueOnce(undefined);
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      await waitFor(() => {
        expect(result.current.error).not.toBe(null);
      });

      // Retry
      act(() => {
        result.current.retry();
      });

      await waitFor(() => {
        expect(result.current.error).toBe(null);
      });
    });

    it('clearError clears error state', async () => {
      const error = new Error('Load failed');
      const onLoadMore = vi.fn().mockRejectedValue(error);
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      act(() => {
        MockIntersectionObserver.getLastInstance()?.triggerIntersection(true);
      });

      await waitFor(() => {
        expect(result.current.error).not.toBe(null);
      });

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBe(null);
    });
  });

  describe('cleanup', () => {
    it('disconnects observer on unmount', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result, unmount } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      const observer = MockIntersectionObserver.getLastInstance();
      const disconnectSpy = vi.spyOn(observer!, 'disconnect');

      unmount();

      expect(disconnectSpy).toHaveBeenCalled();
    });

    it('disconnects old observer when sentinel changes', () => {
      const onLoadMore = vi.fn();
      const mockElement1 = document.createElement('div');
      const mockElement2 = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement1);
      });

      const firstObserver = MockIntersectionObserver.getLastInstance();
      const disconnectSpy = vi.spyOn(firstObserver!, 'disconnect');

      act(() => {
        result.current.sentinelRef(mockElement2);
      });

      expect(disconnectSpy).toHaveBeenCalled();
    });

    it('disconnects observer when sentinel is set to null', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      const observer = MockIntersectionObserver.getLastInstance();
      const disconnectSpy = vi.spyOn(observer!, 'disconnect');

      act(() => {
        result.current.sentinelRef(null);
      });

      expect(disconnectSpy).toHaveBeenCalled();
    });
  });

  describe('dynamic updates', () => {
    it('re-observes when hasMore changes', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
          }),
        { initialProps: { hasMore: false } }
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // No observer should be created when hasMore is false
      expect(MockIntersectionObserver.instances).toHaveLength(0);

      // Change hasMore to true
      rerender({ hasMore: true });

      // Observer should now be created
      expect(MockIntersectionObserver.instances.length).toBeGreaterThan(0);
    });

    it('re-observes when enabled changes', () => {
      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result, rerender } = renderHook(
        ({ enabled }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore: true,
            enabled,
          }),
        { initialProps: { enabled: false } }
      );

      act(() => {
        result.current.sentinelRef(mockElement);
      });

      // No observer should be created when disabled
      expect(MockIntersectionObserver.instances).toHaveLength(0);

      // Enable
      rerender({ enabled: true });

      // Observer should now be created
      expect(MockIntersectionObserver.instances.length).toBeGreaterThan(0);
    });
  });

  describe('SSR safety', () => {
    it('handles missing IntersectionObserver gracefully', () => {
      // Remove IntersectionObserver
      const globalScope = globalThis as unknown as {
        IntersectionObserver?: typeof IntersectionObserver;
      };
      const originalIO = globalScope.IntersectionObserver;
      delete globalScope.IntersectionObserver;

      const onLoadMore = vi.fn();
      const mockElement = document.createElement('div');

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
        })
      );

      // Should not throw
      act(() => {
        result.current.sentinelRef(mockElement);
      });

      expect(result.current.isLoadingMore).toBe(false);
      expect(result.current.error).toBe(null);

      // Restore
      globalScope.IntersectionObserver = originalIO;
    });
  });
});
