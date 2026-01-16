/**
 * useHealthStatus hook MSW test example.
 *
 * This test demonstrates using MSW for hook testing with renderHook.
 * MSW intercepts actual HTTP requests, providing more realistic test coverage
 * than vi.mock().
 *
 * @see src/mocks/handlers.ts - Default API handlers
 * @see src/mocks/server.ts - MSW server configuration
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';
import { describe, it, expect, beforeEach } from 'vitest';

import { useHealthStatus } from './useHealthStatus';
import { server } from '../mocks/server';
import { clearInFlightRequests } from '../services/api';

// ============================================================================
// Test Data
// ============================================================================

const mockHealthyResponse = {
  status: 'healthy',
  services: {
    database: { status: 'healthy', message: 'Database operational' },
    redis: { status: 'healthy', message: 'Redis connected' },
    ai: { status: 'healthy', message: 'AI services operational' },
  },
  timestamp: '2025-12-28T10:30:00',
};

const mockDegradedResponse = {
  status: 'degraded',
  services: {
    database: { status: 'healthy', message: 'Database operational' },
    redis: { status: 'unhealthy', message: 'Redis connection failed' },
    ai: { status: 'healthy', message: 'AI services operational' },
  },
  timestamp: '2025-12-28T10:30:00',
};

const mockUnhealthyResponse = {
  status: 'unhealthy',
  services: {
    database: { status: 'unhealthy', message: 'Database connection failed' },
    redis: { status: 'unhealthy', message: 'Redis connection failed' },
    ai: { status: 'unhealthy', message: 'AI services unavailable' },
  },
  timestamp: '2025-12-28T10:30:00',
};

// ============================================================================
// Tests
// ============================================================================

describe('useHealthStatus (MSW)', () => {
  beforeEach(() => {
    // Clear in-flight request cache to prevent test interference
    clearInFlightRequests();
  });

  describe('initialization', () => {
    it('starts with null health when disabled', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }));
      expect(result.current.health).toBeNull();
    });

    it('starts with isLoading true', () => {
      // Override handler to never respond (simulating infinite loading)
      server.use(
        http.get('/api/system/health', async () => {
          await delay('infinite');
          return HttpResponse.json(mockHealthyResponse);
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));
      expect(result.current.isLoading).toBe(true);
    });
  });

  describe('fetching data', () => {
    it('updates health after fetch', async () => {
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json(mockHealthyResponse);
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.health).toEqual(mockHealthyResponse);
      });
    });

    it('updates overallStatus to healthy', async () => {
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json(mockHealthyResponse);
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('healthy');
      });
    });

    it('updates overallStatus to degraded', async () => {
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json(mockDegradedResponse);
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('degraded');
      });
    });

    it('updates overallStatus to unhealthy', async () => {
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json(mockUnhealthyResponse);
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('unhealthy');
      });
    });

    it('updates services map', async () => {
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json(mockHealthyResponse);
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.services).toEqual(mockHealthyResponse.services);
      });
    });

    it('sets isLoading false after fetch', async () => {
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json(mockHealthyResponse);
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      // Use 400 to avoid retry backoff
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json({ detail: 'Network error' }, { status: 400 });
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.error).toBe('Network error');
      });
    });

    it('sets isLoading false on error', async () => {
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json({ detail: 'Error' }, { status: 400 });
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('refresh', () => {
    it('manually triggers a refresh', async () => {
      let callCount = 0;
      server.use(
        http.get('/api/system/health', () => {
          callCount++;
          return HttpResponse.json(mockHealthyResponse);
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      // Wait for initial fetch
      await waitFor(() => {
        expect(callCount).toBe(1);
      });

      // Manually refresh
      await act(async () => {
        await result.current.refresh();
      });

      expect(callCount).toBe(2);
    });
  });

  describe('return values', () => {
    it('returns all expected properties', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }));

      expect(result.current).toHaveProperty('health');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('overallStatus');
      expect(result.current).toHaveProperty('services');
      expect(result.current).toHaveProperty('refresh');
      expect(typeof result.current.refresh).toBe('function');
    });
  });

  describe('edge cases', () => {
    it('handles invalid status in response', async () => {
      server.use(
        http.get('/api/system/health', () => {
          return HttpResponse.json({
            status: 'invalid_status',
            services: {},
            timestamp: '2025-12-28T10:30:00',
          });
        })
      );

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.overallStatus).toBeNull();
      });
    });
  });
});
