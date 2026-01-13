import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useFullHealthQuery,
  FULL_HEALTH_QUERY_KEY,
} from './useFullHealthQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { FullHealthResponse } from '../services/api';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchFullHealth: vi.fn(),
  };
});

describe('useFullHealthQuery', () => {
  // Mock response structure for testing - uses test-friendly property names
  // that may differ slightly from generated types
  const mockHealthyResponse = {
    status: 'healthy',
    ready: true,
    message: 'All systems operational',
    postgres: {
      status: 'healthy',
      latency_ms: 5,
      message: 'Connected',
    },
    redis: {
      status: 'healthy',
      latency_ms: 2,
      message: 'Connected',
    },
    ai_services: [
      {
        name: 'rtdetr',
        status: 'healthy',
        latency_ms: 50,
        message: 'Model loaded',
        circuit_breaker_state: 'closed',
      },
      {
        name: 'nemotron',
        status: 'healthy',
        latency_ms: 100,
        message: 'Model loaded',
        circuit_breaker_state: 'closed',
      },
      {
        name: 'florence',
        status: 'healthy',
        latency_ms: 75,
        message: 'Model loaded',
        circuit_breaker_state: 'closed',
      },
    ],
    circuit_breakers: {
      total: 3,
      closed: 3,
      open: 0,
      half_open: 0,
    },
    workers: [
      {
        name: 'detection_worker',
        running: true,
        critical: true,
        message: 'Processing events',
        last_heartbeat: '2025-12-28T10:00:00Z',
      },
      {
        name: 'cleanup_worker',
        running: true,
        critical: false,
        message: 'Idle',
        last_heartbeat: '2025-12-28T09:55:00Z',
      },
    ],
    timestamp: '2025-12-28T10:00:00Z',
    version: '1.0.0',
  };

  const mockDegradedResponse: FullHealthResponse = {
    status: 'degraded',
    ready: true,
    message: 'Some services degraded',
    postgres: {
      status: 'healthy',
      latency_ms: 5,
      message: 'Connected',
    },
    redis: {
      status: 'healthy',
      latency_ms: 2,
      message: 'Connected',
    },
    ai_services: [
      {
        name: 'rtdetr',
        status: 'healthy',
        latency_ms: 50,
        message: 'Model loaded',
        circuit_breaker_state: 'closed',
      },
      {
        name: 'nemotron',
        status: 'degraded',
        latency_ms: 500,
        message: 'High latency',
        circuit_breaker_state: 'half_open',
      },
      {
        name: 'florence',
        status: 'unhealthy',
        latency_ms: 0,
        message: 'Service unavailable',
        circuit_breaker_state: 'open',
      },
    ],
    circuit_breakers: {
      total: 3,
      closed: 1,
      open: 1,
      half_open: 1,
    },
    workers: [
      {
        name: 'detection_worker',
        running: true,
        critical: true,
        message: 'Processing events',
        last_heartbeat: '2025-12-28T10:00:00Z',
      },
      {
        name: 'cleanup_worker',
        running: false,
        critical: false,
        message: 'Stopped',
        last_heartbeat: '2025-12-28T09:00:00Z',
      },
    ],
    timestamp: '2025-12-28T10:00:00Z',
    version: '1.0.0',
  };

  const mockUnhealthyResponse = {
    status: 'unhealthy',
    ready: false,
    message: 'Critical services unavailable',
    postgres: {
      status: 'unhealthy',
      latency_ms: 0,
      message: 'Connection failed',
    },
    redis: {
      status: 'healthy',
      latency_ms: 2,
      message: 'Connected',
    },
    ai_services: [
      {
        name: 'rtdetr',
        status: 'unhealthy',
        latency_ms: 0,
        message: 'Model failed to load',
        circuit_breaker_state: 'open',
      },
      {
        name: 'nemotron',
        status: 'unhealthy',
        latency_ms: 0,
        message: 'Model failed to load',
        circuit_breaker_state: 'open',
      },
    ],
    circuit_breakers: {
      total: 2,
      closed: 0,
      open: 2,
      half_open: 0,
    },
    workers: [
      {
        name: 'detection_worker',
        running: false,
        critical: true,
        message: 'Crashed',
        last_heartbeat: '2025-12-28T08:00:00Z',
      },
    ],
    timestamp: '2025-12-28T10:00:00Z',
    version: '1.0.0',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockHealthyResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.data).toBeUndefined();
    });

    it('starts with null overallStatus', () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.overallStatus).toBeNull();
    });

    it('starts with checking message', () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.statusMessage).toBe('Checking system health...');
    });
  });

  describe('fetching all health endpoints', () => {
    it('fetches full health on mount', async () => {
      renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(api.fetchFullHealth).toHaveBeenCalledTimes(1);
      });
    });

    it('returns complete health data', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockHealthyResponse);
      });
    });
  });

  describe('aggregate status', () => {
    it('returns healthy overall status when all services healthy', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('healthy');
      });
    });

    it('returns degraded overall status when some services degraded', async () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockDegradedResponse);

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('degraded');
      });
    });

    it('returns unhealthy overall status when critical services down', async () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockUnhealthyResponse);

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('unhealthy');
      });
    });
  });

  describe('isReady status', () => {
    it('returns true when system is ready', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isReady).toBe(true);
      });
    });

    it('returns false when system is not ready', async () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockUnhealthyResponse);

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isReady).toBe(false);
      });
    });
  });

  describe('service-level details', () => {
    it('returns postgres health status', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.postgres).toEqual(mockHealthyResponse.postgres);
      });
    });

    it('returns redis health status', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.redis).toEqual(mockHealthyResponse.redis);
      });
    });

    it('returns all AI services', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.aiServices).toEqual(mockHealthyResponse.ai_services);
        expect(result.current.aiServices.length).toBe(3);
      });
    });

    it('returns circuit breaker summary', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.circuitBreakers).toEqual(mockHealthyResponse.circuit_breakers);
      });
    });

    it('returns worker statuses', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.workers).toEqual(mockHealthyResponse.workers);
        expect(result.current.workers.length).toBe(2);
      });
    });
  });

  describe('unhealthy counts', () => {
    it('returns 0 critical unhealthy when all healthy', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.criticalUnhealthyCount).toBe(0);
      });
    });

    it('returns 0 non-critical unhealthy when all healthy', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.nonCriticalUnhealthyCount).toBe(0);
      });
    });

    it('counts critical unhealthy services correctly', async () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockUnhealthyResponse);

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        // postgres unhealthy (1) + rtdetr unhealthy (1) + nemotron unhealthy (1) + detection_worker not running (1) = 4
        expect(result.current.criticalUnhealthyCount).toBe(4);
      });
    });

    it('counts non-critical unhealthy services correctly', async () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockDegradedResponse);

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        // florence unhealthy (1) + cleanup_worker not running (1) = 2
        expect(result.current.nonCriticalUnhealthyCount).toBe(2);
      });
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch health';
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('options', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(
        () => useFullHealthQuery({ enabled: false }),
        { wrapper: createQueryWrapper() }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchFullHealth).not.toHaveBeenCalled();
    });

    it('provides refetch function', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('query key', () => {
    it('exports correct query key', () => {
      expect(FULL_HEALTH_QUERY_KEY).toEqual(['system', 'health', 'full']);
    });
  });

  describe('status message', () => {
    it('returns status message from response', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.statusMessage).toBe('All systems operational');
      });
    });

    it('returns degraded message when degraded', async () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockDegradedResponse);

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.statusMessage).toBe('Some services degraded');
      });
    });
  });

  describe('isRefetching state', () => {
    it('is false during initial load', () => {
      (api.fetchFullHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.isRefetching).toBe(false);
    });
  });

  describe('isStale state', () => {
    it('provides isStale indicator', async () => {
      const { result } = renderHook(
        () => useFullHealthQuery(),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Initially data should not be stale
      expect(typeof result.current.isStale).toBe('boolean');
    });
  });
});
