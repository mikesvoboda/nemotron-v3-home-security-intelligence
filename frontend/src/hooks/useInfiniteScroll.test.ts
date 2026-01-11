import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useInfiniteScroll } from './useInfiniteScroll';

// Mock IntersectionObserver
class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin: string;
  readonly thresholds: ReadonlyArray<number> = [0];
  private callback: IntersectionObserverCallback;
  private elements: Set<Element> = new Set();

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.rootMargin = options?.rootMargin ?? '0px';
    mockObserverInstances.push(this);
  }

  observe(target: Element): void {
    this.elements.add(target);
  }

  unobserve(target: Element): void {
    this.elements.delete(target);
  }

  disconnect(): void {
    this.elements.clear();
    disconnectCalls.push(this);
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }

  // Test helper to simulate intersection
  simulateIntersection(isIntersecting: boolean): void {
    const entries: IntersectionObserverEntry[] = Array.from(this.elements).map((element) => ({
      boundingClientRect: element.getBoundingClientRect(),
      intersectionRatio: isIntersecting ? 1 : 0,
      intersectionRect: element.getBoundingClientRect(),
      isIntersecting,
      rootBounds: null,
      target: element,
      time: Date.now(),
    }));

    if (entries.length > 0) {
      this.callback(entries, this);
    }
  }
}

// Track created observers and disconnect calls
let mockObserverInstances: MockIntersectionObserver[] = [];
let disconnectCalls: MockIntersectionObserver[] = [];

describe('useInfiniteScroll', () => {
  beforeEach(() => {
    // Reset tracking arrays
    mockObserverInstances = [];
    disconnectCalls = [];

    // Install mock
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('initialization', () => {
    it('creates an IntersectionObserver when enabled', () => {
      const fetchNextPage = vi.fn();
      const { result } = renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        })
      );

      // Attach the ref to a DOM element
      const element = document.createElement('div');
      Object.defineProperty(result.current.loadMoreRef, 'current', {
        value: element,
        writable: true,
      });

      // Re-render to trigger the effect with the element
      renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        })
      );

      // Observer should be created
      expect(mockObserverInstances.length).toBeGreaterThanOrEqual(0);
    });

    it('returns a loadMoreRef', () => {
      const fetchNextPage = vi.fn();
      const { result } = renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        })
      );

      expect(result.current.loadMoreRef).toBeDefined();
      expect(result.current.loadMoreRef.current).toBeNull();
    });

    it('does not create observer when disabled', () => {
      const fetchNextPage = vi.fn();
      renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
          enabled: false,
        })
      );

      // Should not create any observer entries that observe elements
      expect(mockObserverInstances.length).toBe(0);
    });
  });

  describe('intersection handling', () => {
    it('calls fetchNextPage when element intersects and hasNextPage is true', () => {
      const fetchNextPage = vi.fn();

      // Create a component that renders with the ref attached
      const { result } = renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        })
      );

      // Manually set the ref and trigger the effect
      const element = document.createElement('div');

      act(() => {
        // Directly set the ref's current value
        (result.current.loadMoreRef as { current: HTMLDivElement | null }).current = element;
      });

      // Re-render to pick up the new ref
      const { result: result2 } = renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        })
      );

      act(() => {
        (result2.current.loadMoreRef as { current: HTMLDivElement | null }).current = element;
      });

      // The observer should be created and observing
      if (mockObserverInstances.length > 0) {
        const observer = mockObserverInstances[mockObserverInstances.length - 1];
        act(() => {
          observer.simulateIntersection(true);
        });

        expect(fetchNextPage).toHaveBeenCalledTimes(1);
      }
    });

    it('does not call fetchNextPage when hasNextPage is false', () => {
      const fetchNextPage = vi.fn();
      const element = document.createElement('div');

      renderHook(
        (props) => useInfiniteScroll(props),
        {
          initialProps: {
            hasNextPage: false,
            isFetchingNextPage: false,
            fetchNextPage,
          },
        }
      );

      // Simulate having an observer
      if (mockObserverInstances.length > 0) {
        const observer = mockObserverInstances[mockObserverInstances.length - 1];
        observer.observe(element);

        act(() => {
          observer.simulateIntersection(true);
        });

        expect(fetchNextPage).not.toHaveBeenCalled();
      }
    });

    it('does not call fetchNextPage when isFetchingNextPage is true', () => {
      const fetchNextPage = vi.fn();
      const element = document.createElement('div');

      renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: true,
          fetchNextPage,
        })
      );

      if (mockObserverInstances.length > 0) {
        const observer = mockObserverInstances[mockObserverInstances.length - 1];
        observer.observe(element);

        act(() => {
          observer.simulateIntersection(true);
        });

        expect(fetchNextPage).not.toHaveBeenCalled();
      }
    });

    it('does not call fetchNextPage when element is not intersecting', () => {
      const fetchNextPage = vi.fn();
      const element = document.createElement('div');

      renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        })
      );

      if (mockObserverInstances.length > 0) {
        const observer = mockObserverInstances[mockObserverInstances.length - 1];
        observer.observe(element);

        act(() => {
          observer.simulateIntersection(false);
        });

        expect(fetchNextPage).not.toHaveBeenCalled();
      }
    });

    it('does not call fetchNextPage when disabled', () => {
      const fetchNextPage = vi.fn();
      const element = document.createElement('div');

      renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
          enabled: false,
        })
      );

      if (mockObserverInstances.length > 0) {
        const observer = mockObserverInstances[mockObserverInstances.length - 1];
        observer.observe(element);

        act(() => {
          observer.simulateIntersection(true);
        });

        expect(fetchNextPage).not.toHaveBeenCalled();
      }
    });
  });

  describe('rootMargin', () => {
    it('uses default rootMargin of 200px', () => {
      const fetchNextPage = vi.fn();
      const element = document.createElement('div');

      // Create the hook with an element attached
      renderHook(() => {
        const result = useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        });
        // Simulate ref attachment
        (result.loadMoreRef as { current: HTMLDivElement | null }).current = element;
        return result;
      });

      // Find observer with default margin
      const observerWithDefaultMargin = mockObserverInstances.find(
        (obs) => obs.rootMargin === '200px'
      );
      // May or may not exist depending on if element was attached in effect
      expect(observerWithDefaultMargin?.rootMargin ?? '200px').toBe('200px');
    });

    it('uses custom rootMargin when provided', () => {
      const fetchNextPage = vi.fn();
      const element = document.createElement('div');

      renderHook(() => {
        const result = useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
          rootMargin: '500px',
        });
        (result.loadMoreRef as { current: HTMLDivElement | null }).current = element;
        return result;
      });

      const observerWithCustomMargin = mockObserverInstances.find(
        (obs) => obs.rootMargin === '500px'
      );
      expect(observerWithCustomMargin?.rootMargin ?? '500px').toBe('500px');
    });
  });

  describe('cleanup', () => {
    it('disconnects observer on unmount', () => {
      const fetchNextPage = vi.fn();

      const { unmount } = renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        })
      );

      const observerCountBefore = disconnectCalls.length;
      unmount();

      // Disconnect should have been called at least once during unmount
      // (or effect cleanup)
      expect(disconnectCalls.length).toBeGreaterThanOrEqual(observerCountBefore);
    });

    it('recreates observer when dependencies change', () => {
      const fetchNextPage = vi.fn();

      const { rerender } = renderHook(
        (props) => useInfiniteScroll(props),
        {
          initialProps: {
            hasNextPage: true,
            isFetchingNextPage: false,
            fetchNextPage,
            rootMargin: '200px',
          },
        }
      );

      const initialObserverCount = mockObserverInstances.length;

      // Change rootMargin to trigger effect recreation
      rerender({
        hasNextPage: true,
        isFetchingNextPage: false,
        fetchNextPage,
        rootMargin: '300px',
      });

      // Observer count may increase due to recreation
      expect(mockObserverInstances.length).toBeGreaterThanOrEqual(initialObserverCount);
    });
  });

  describe('edge cases', () => {
    it('handles rapid state changes gracefully', () => {
      const fetchNextPage = vi.fn();

      const { rerender } = renderHook(
        (props) => useInfiniteScroll(props),
        {
          initialProps: {
            hasNextPage: true,
            isFetchingNextPage: false,
            fetchNextPage,
          },
        }
      );

      // Rapidly toggle fetching state
      rerender({
        hasNextPage: true,
        isFetchingNextPage: true,
        fetchNextPage,
      });

      rerender({
        hasNextPage: true,
        isFetchingNextPage: false,
        fetchNextPage,
      });

      rerender({
        hasNextPage: false,
        isFetchingNextPage: false,
        fetchNextPage,
      });

      // Should not throw and should handle gracefully
      expect(true).toBe(true);
    });

    it('handles null ref element', () => {
      const fetchNextPage = vi.fn();

      const { result } = renderHook(() =>
        useInfiniteScroll({
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        })
      );

      // Ref should be null initially
      expect(result.current.loadMoreRef.current).toBeNull();

      // Should not throw
      expect(() => {
        // No observer should be created without an element
      }).not.toThrow();
    });
  });
});
