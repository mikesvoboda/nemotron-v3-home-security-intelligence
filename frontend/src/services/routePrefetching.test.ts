/**
 * Tests for route-based query prefetching system (NEM-3359)
 */

import { QueryClient } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  prefetchRoute,
  prefetchQuery,
  prefetchRoutes,
  getRelatedRoutes,
  routePrefetchConfigs,
} from './routePrefetching';

// Mock the API functions
vi.mock('./api', () => ({
  fetchCameras: vi.fn().mockResolvedValue([]),
  fetchFullHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
  fetchEvents: vi.fn().mockResolvedValue({ items: [], pagination: { total: 0 } }),
  fetchNotificationPreferences: vi.fn().mockResolvedValue({ enabled: true }),
}));

vi.mock('../hooks/useSettingsApi', () => ({
  fetchSettings: vi.fn().mockResolvedValue({ detection: { confidence_threshold: 0.5 } }),
}));

describe('routePrefetching', () => {
  let queryClient: QueryClient;
  let prefetchQuerySpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    prefetchQuerySpy = vi.spyOn(queryClient, 'prefetchQuery');
  });

  afterEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
  });

  describe('routePrefetchConfigs', () => {
    it('should have configs for dashboard route', () => {
      expect(routePrefetchConfigs['/']).toBeDefined();
      expect(routePrefetchConfigs['/'].length).toBeGreaterThan(0);
    });

    it('should have configs for timeline route', () => {
      expect(routePrefetchConfigs['/timeline']).toBeDefined();
      expect(routePrefetchConfigs['/timeline'].length).toBeGreaterThan(0);
    });

    it('should have configs for alerts route', () => {
      expect(routePrefetchConfigs['/alerts']).toBeDefined();
      expect(routePrefetchConfigs['/alerts'].length).toBeGreaterThan(0);
    });

    it('should have configs for settings route', () => {
      expect(routePrefetchConfigs['/settings']).toBeDefined();
      expect(routePrefetchConfigs['/settings'].length).toBeGreaterThan(0);
    });

    it('should have configs for notifications route', () => {
      expect(routePrefetchConfigs['/notifications']).toBeDefined();
      expect(routePrefetchConfigs['/notifications'].length).toBeGreaterThan(0);
    });

    it('should have configs for operations route', () => {
      expect(routePrefetchConfigs['/operations']).toBeDefined();
      expect(routePrefetchConfigs['/operations'].length).toBeGreaterThan(0);
    });

    it('should have queryKey and queryFn for each config', () => {
      for (const [_route, configs] of Object.entries(routePrefetchConfigs)) {
        for (const config of configs) {
          expect(config.queryKey).toBeDefined();
          expect(Array.isArray(config.queryKey) || typeof config.queryKey === 'object').toBe(true);
          expect(typeof config.queryFn).toBe('function');
        }
      }
    });
  });

  describe('prefetchRoute', () => {
    it('should prefetch all queries for a known route', () => {
      prefetchRoute(queryClient, '/');

      const expectedConfigCount = routePrefetchConfigs['/'].length;
      expect(prefetchQuerySpy).toHaveBeenCalledTimes(expectedConfigCount);
    });

    it('should do nothing for unknown route', () => {
      prefetchRoute(queryClient, '/unknown-route');

      expect(prefetchQuerySpy).not.toHaveBeenCalled();
    });

    it('should pass correct query key and function to prefetchQuery', () => {
      prefetchRoute(queryClient, '/settings');

      expect(prefetchQuerySpy).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: expect.any(Array),
          queryFn: expect.any(Function),
        })
      );
    });

    it('should use configured stale time', () => {
      prefetchRoute(queryClient, '/');

      const firstCall = prefetchQuerySpy.mock.calls[0][0];
      expect(firstCall).toHaveProperty('staleTime');
      expect(typeof firstCall.staleTime).toBe('number');
    });
  });

  describe('prefetchQuery', () => {
    it('should prefetch a single query configuration', () => {
      const config = {
        queryKey: ['test', 'query'] as const,
        queryFn: vi.fn().mockResolvedValue({ data: 'test' }),
        staleTime: 5000,
      };

      prefetchQuery(queryClient, config);

      expect(prefetchQuerySpy).toHaveBeenCalledTimes(1);
      expect(prefetchQuerySpy).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: config.queryKey,
          queryFn: config.queryFn,
          staleTime: config.staleTime,
        })
      );
    });

    it('should use default stale time when not provided', () => {
      const config = {
        queryKey: ['test', 'query'] as const,
        queryFn: vi.fn().mockResolvedValue({ data: 'test' }),
      };

      prefetchQuery(queryClient, config);

      expect(prefetchQuerySpy).toHaveBeenCalledWith(
        expect.objectContaining({
          staleTime: expect.any(Number),
        })
      );
    });
  });

  describe('prefetchRoutes', () => {
    it('should prefetch multiple routes', () => {
      prefetchRoutes(queryClient, ['/', '/timeline']);

      const dashboardCount = routePrefetchConfigs['/'].length;
      const timelineCount = routePrefetchConfigs['/timeline'].length;
      expect(prefetchQuerySpy).toHaveBeenCalledTimes(dashboardCount + timelineCount);
    });

    it('should handle empty routes array', () => {
      prefetchRoutes(queryClient, []);

      expect(prefetchQuerySpy).not.toHaveBeenCalled();
    });

    it('should skip unknown routes silently', () => {
      prefetchRoutes(queryClient, ['/unknown', '/']);

      const dashboardCount = routePrefetchConfigs['/'].length;
      expect(prefetchQuerySpy).toHaveBeenCalledTimes(dashboardCount);
    });
  });

  describe('getRelatedRoutes', () => {
    it('should return related routes for dashboard', () => {
      const related = getRelatedRoutes('/');

      expect(related).toContain('/timeline');
      expect(related).toContain('/alerts');
      expect(related).toContain('/settings');
    });

    it('should return related routes for timeline', () => {
      const related = getRelatedRoutes('/timeline');

      expect(related).toContain('/');
      expect(related).toContain('/alerts');
    });

    it('should return related routes for alerts', () => {
      const related = getRelatedRoutes('/alerts');

      expect(related).toContain('/');
      expect(related).toContain('/timeline');
    });

    it('should return related routes for settings', () => {
      const related = getRelatedRoutes('/settings');

      expect(related).toContain('/notifications');
      expect(related).toContain('/');
    });

    it('should return related routes for operations', () => {
      const related = getRelatedRoutes('/operations');

      expect(related).toContain('/');
      expect(related).toContain('/ai');
    });

    it('should return empty array for unknown route', () => {
      const related = getRelatedRoutes('/unknown');

      expect(related).toEqual([]);
    });
  });
});
