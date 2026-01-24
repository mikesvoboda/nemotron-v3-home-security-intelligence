/**
 * Tests for useRoutePrefetch hook (NEM-3359)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRoutePrefetch } from './useRoutePrefetch';
import * as routePrefetching from '../services/routePrefetching';

import type { ReactNode } from 'react';

// Mock the routePrefetching module
vi.mock('../services/routePrefetching', () => ({
  prefetchRoute: vi.fn(),
  prefetchRoutes: vi.fn(),
  getRelatedRoutes: vi.fn().mockReturnValue(['/timeline', '/alerts']),
  routePrefetchConfigs: {
    '/': [],
    '/timeline': [],
    '/alerts': [],
  },
}));

describe('useRoutePrefetch', () => {
  let queryClient: QueryClient;

  const createWrapper = (initialEntries: string[] = ['/']) => {
    return function Wrapper({ children }: { children: ReactNode }) {
      return (
        <MemoryRouter initialEntries={initialEntries}>
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        </MemoryRouter>
      );
    };
  };

  beforeEach(() => {
    vi.useFakeTimers();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    queryClient.clear();
  });

  describe('initialization', () => {
    it('should return prefetch functions', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      expect(result.current.prefetch).toBeDefined();
      expect(typeof result.current.prefetch).toBe('function');
    });

    it('should return prefetchQuery function', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      expect(result.current.prefetchQuery).toBeDefined();
      expect(typeof result.current.prefetchQuery).toBe('function');
    });

    it('should return getLinkProps function', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      expect(result.current.getLinkProps).toBeDefined();
      expect(typeof result.current.getLinkProps).toBe('function');
    });

    it('should return isPrefetchEnabled', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPrefetchEnabled).toBe(true);
    });
  });

  describe('prefetch', () => {
    it('should call prefetchRoute when prefetch is called', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.prefetch('/timeline');
      });

      expect(routePrefetching.prefetchRoute).toHaveBeenCalledWith(
        expect.any(Object),
        '/timeline'
      );
    });

    it('should not prefetch the same route twice', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.prefetch('/timeline');
        result.current.prefetch('/timeline');
      });

      expect(routePrefetching.prefetchRoute).toHaveBeenCalledTimes(1);
    });

    it('should prefetch different routes', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.prefetch('/timeline');
        result.current.prefetch('/alerts');
      });

      expect(routePrefetching.prefetchRoute).toHaveBeenCalledTimes(2);
    });
  });

  describe('getLinkProps', () => {
    it('should return onMouseEnter and onFocus handlers', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      const linkProps = result.current.getLinkProps('/timeline');

      expect(linkProps).toHaveProperty('onMouseEnter');
      expect(linkProps).toHaveProperty('onFocus');
      expect(typeof linkProps.onMouseEnter).toBe('function');
      expect(typeof linkProps.onFocus).toBe('function');
    });

    it('should call prefetch on mouseEnter', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      const linkProps = result.current.getLinkProps('/timeline');

      act(() => {
        linkProps.onMouseEnter();
      });

      expect(routePrefetching.prefetchRoute).toHaveBeenCalledWith(
        expect.any(Object),
        '/timeline'
      );
    });

    it('should call prefetch on focus', () => {
      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      const linkProps = result.current.getLinkProps('/timeline');

      act(() => {
        linkProps.onFocus();
      });

      expect(routePrefetching.prefetchRoute).toHaveBeenCalledWith(
        expect.any(Object),
        '/timeline'
      );
    });
  });

  describe('automatic related route prefetching', () => {
    it('should prefetch related routes after delay', () => {
      renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      // Advance past the default delay
      act(() => {
        vi.advanceTimersByTime(1100);
      });

      expect(routePrefetching.prefetchRoutes).toHaveBeenCalledWith(
        expect.any(Object),
        expect.arrayContaining(['/timeline', '/alerts'])
      );
    });

    it('should not prefetch related routes when disabled', () => {
      renderHook(() => useRoutePrefetch({ prefetchRelated: false }), {
        wrapper: createWrapper(),
      });

      act(() => {
        vi.advanceTimersByTime(2000);
      });

      expect(routePrefetching.prefetchRoutes).not.toHaveBeenCalled();
    });

    it('should respect custom delay', () => {
      renderHook(() => useRoutePrefetch({ relatedPrefetchDelay: 500 }), {
        wrapper: createWrapper(),
      });

      // Should not have prefetched yet
      act(() => {
        vi.advanceTimersByTime(400);
      });
      expect(routePrefetching.prefetchRoutes).not.toHaveBeenCalled();

      // Should have prefetched after delay
      act(() => {
        vi.advanceTimersByTime(200);
      });
      expect(routePrefetching.prefetchRoutes).toHaveBeenCalled();
    });

    it('should include custom routes in prefetching', () => {
      renderHook(
        () => useRoutePrefetch({ customRoutes: ['/settings', '/notifications'] }),
        {
          wrapper: createWrapper(),
        }
      );

      act(() => {
        vi.advanceTimersByTime(1100);
      });

      expect(routePrefetching.prefetchRoutes).toHaveBeenCalledWith(
        expect.any(Object),
        expect.arrayContaining(['/settings', '/notifications'])
      );
    });
  });

  describe('prefetchQuery', () => {
    it('should prefetch custom query configuration', () => {
      const prefetchQuerySpy = vi.spyOn(queryClient, 'prefetchQuery');

      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      const mockFn = vi.fn().mockResolvedValue({ data: 'test' });

      act(() => {
        result.current.prefetchQuery({
          queryKey: ['test', 'custom'],
          queryFn: mockFn,
          staleTime: 5000,
        });
      });

      expect(prefetchQuerySpy).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: ['test', 'custom'],
          queryFn: mockFn,
          staleTime: 5000,
        })
      );
    });

    it('should not prefetch same custom query twice', () => {
      const prefetchQuerySpy = vi.spyOn(queryClient, 'prefetchQuery');

      const { result } = renderHook(() => useRoutePrefetch(), {
        wrapper: createWrapper(),
      });

      const mockFn = vi.fn().mockResolvedValue({ data: 'test' });
      const config = {
        queryKey: ['test', 'duplicate'] as const,
        queryFn: mockFn,
      };

      act(() => {
        result.current.prefetchQuery(config);
        result.current.prefetchQuery(config);
      });

      // Should only be called once for the custom query
      const customQueryCalls = prefetchQuerySpy.mock.calls.filter(
        (call) => JSON.stringify(call[0].queryKey) === JSON.stringify(['test', 'duplicate'])
      );
      expect(customQueryCalls.length).toBe(1);
    });
  });
});
