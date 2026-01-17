/**
 * Tests for useServiceMutations hook
 *
 * Tests the service control mutations for the ServicesPanel component:
 * - restartService - restart a running service
 * - startService - start a stopped service
 * - stopService - stop/disable a running service (maps to backend disable)
 * - enableService - enable a disabled service
 *
 * @module hooks/useServiceMutations.test
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';

import {
  useServiceMutations,
  useRestartServiceMutation,
  useStartServiceMutation,
  useStopServiceMutation,
  useEnableServiceMutation,
} from './useServiceMutations';

import type { ReactNode } from 'react';

// Mock response data
const mockServiceInfo = {
  name: 'rtdetr',
  display_name: 'RT-DETRv2',
  category: 'ai',
  status: 'running',
  enabled: true,
  container_id: 'abc123def456',
  image: 'ghcr.io/test/rtdetr:latest',
  port: 8001,
  failure_count: 0,
  restart_count: 1,
  last_restart_at: '2025-01-01T12:00:00Z',
  uptime_seconds: 3600,
};

// MSW server setup
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  server.resetHandlers();
});

// Test wrapper with QueryClientProvider
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useServiceMutations', () => {
  describe('useRestartServiceMutation', () => {
    it('should restart a service successfully', async () => {
      server.use(
        http.post('/api/system/services/rtdetr/restart', () => {
          return HttpResponse.json({
            success: true,
            message: "Service 'rtdetr' restart initiated",
            service: mockServiceInfo,
          });
        })
      );

      const { result } = renderHook(() => useRestartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('rtdetr');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.success).toBe(true);
      expect(result.current.data?.message).toContain('restart');
    });

    it('should handle restart of disabled service (400 error)', async () => {
      server.use(
        http.post('/api/system/services/disabled-service/restart', () => {
          return HttpResponse.json(
            { detail: "Service 'disabled-service' is disabled. Enable it first." },
            { status: 400 }
          );
        })
      );

      const { result } = renderHook(() => useRestartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('disabled-service');

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('disabled');
    });

    it('should handle service not found (404 error)', async () => {
      server.use(
        http.post('/api/system/services/nonexistent/restart', () => {
          return HttpResponse.json(
            { detail: "Service 'nonexistent' not found" },
            { status: 404 }
          );
        })
      );

      const { result } = renderHook(() => useRestartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('nonexistent');

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('not found');
    });

    // Note: 503 error handling is tested at the backend level.
    // The frontend fetchApi has internal retry logic that would retry 503 errors.
    // This makes the test complex and the backend already covers this scenario.
  });

  describe('useStartServiceMutation', () => {
    it('should start a stopped service successfully', async () => {
      server.use(
        http.post('/api/system/services/rtdetr/start', () => {
          return HttpResponse.json({
            success: true,
            message: "Service 'rtdetr' start initiated",
            service: { ...mockServiceInfo, status: 'running' },
          });
        })
      );

      const { result } = renderHook(() => useStartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('rtdetr');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.success).toBe(true);
      expect(result.current.data?.message).toContain('start');
    });

    it('should handle starting already running service (400 error)', async () => {
      server.use(
        http.post('/api/system/services/running-service/start', () => {
          return HttpResponse.json(
            { detail: "Service 'running-service' is already running" },
            { status: 400 }
          );
        })
      );

      const { result } = renderHook(() => useStartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('running-service');

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('already running');
    });

    it('should handle starting disabled service (400 error)', async () => {
      server.use(
        http.post('/api/system/services/disabled-service/start', () => {
          return HttpResponse.json(
            { detail: "Service 'disabled-service' is disabled. Enable it first." },
            { status: 400 }
          );
        })
      );

      const { result } = renderHook(() => useStartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('disabled-service');

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('disabled');
    });

    it('should handle service not found (404 error)', async () => {
      server.use(
        http.post('/api/system/services/nonexistent/start', () => {
          return HttpResponse.json(
            { detail: "Service 'nonexistent' not found" },
            { status: 404 }
          );
        })
      );

      const { result } = renderHook(() => useStartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('nonexistent');

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('not found');
    });
  });

  describe('useStopServiceMutation', () => {
    it('should stop/disable a service successfully', async () => {
      server.use(
        http.post('/api/system/services/rtdetr/disable', () => {
          return HttpResponse.json({
            success: true,
            message: "Service 'rtdetr' disabled",
            service: { ...mockServiceInfo, enabled: false, status: 'disabled' },
          });
        })
      );

      const { result } = renderHook(() => useStopServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('rtdetr');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.success).toBe(true);
      expect(result.current.data?.service?.enabled).toBe(false);
    });

    it('should handle service not found (404 error)', async () => {
      server.use(
        http.post('/api/system/services/nonexistent/disable', () => {
          return HttpResponse.json(
            { detail: "Service 'nonexistent' not found" },
            { status: 404 }
          );
        })
      );

      const { result } = renderHook(() => useStopServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('nonexistent');

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('not found');
    });
  });

  describe('useEnableServiceMutation', () => {
    it('should enable a disabled service successfully', async () => {
      server.use(
        http.post('/api/system/services/rtdetr/enable', () => {
          return HttpResponse.json({
            success: true,
            message: "Service 'rtdetr' enabled",
            service: { ...mockServiceInfo, enabled: true },
          });
        })
      );

      const { result } = renderHook(() => useEnableServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('rtdetr');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.success).toBe(true);
      expect(result.current.data?.service?.enabled).toBe(true);
    });

    it('should handle service not found (404 error)', async () => {
      server.use(
        http.post('/api/system/services/nonexistent/enable', () => {
          return HttpResponse.json(
            { detail: "Service 'nonexistent' not found" },
            { status: 404 }
          );
        })
      );

      const { result } = renderHook(() => useEnableServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('nonexistent');

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('not found');
    });
  });

  describe('useServiceMutations (combined)', () => {
    it('should return all mutation hooks', () => {
      const { result } = renderHook(() => useServiceMutations(), {
        wrapper: createWrapper(),
      });

      expect(result.current.restartService).toBeDefined();
      expect(result.current.startService).toBeDefined();
      expect(result.current.stopService).toBeDefined();
      expect(result.current.enableService).toBeDefined();
    });

    it('should expose isPending state for each mutation', () => {
      const { result } = renderHook(() => useServiceMutations(), {
        wrapper: createWrapper(),
      });

      expect(result.current.restartService.isPending).toBe(false);
      expect(result.current.startService.isPending).toBe(false);
      expect(result.current.stopService.isPending).toBe(false);
      expect(result.current.enableService.isPending).toBe(false);
    });
  });

  describe('PostgreSQL restart protection', () => {
    it('should allow restart of backend service', async () => {
      server.use(
        http.post('/api/system/services/backend/restart', () => {
          return HttpResponse.json({
            success: true,
            message: "Service 'backend' restart initiated",
            service: { ...mockServiceInfo, name: 'backend', display_name: 'Backend' },
          });
        })
      );

      const { result } = renderHook(() => useRestartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('backend');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });

    it('should allow restart of redis service', async () => {
      server.use(
        http.post('/api/system/services/redis/restart', () => {
          return HttpResponse.json({
            success: true,
            message: "Service 'redis' restart initiated",
            service: { ...mockServiceInfo, name: 'redis', display_name: 'Redis' },
          });
        })
      );

      const { result } = renderHook(() => useRestartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('redis');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });

    it('should allow restart of nemotron service', async () => {
      server.use(
        http.post('/api/system/services/nemotron/restart', () => {
          return HttpResponse.json({
            success: true,
            message: "Service 'nemotron' restart initiated",
            service: { ...mockServiceInfo, name: 'nemotron', display_name: 'Nemotron' },
          });
        })
      );

      const { result } = renderHook(() => useRestartServiceMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('nemotron');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
  });
});
