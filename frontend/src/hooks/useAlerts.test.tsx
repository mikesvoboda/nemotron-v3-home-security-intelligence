/**
 * Tests for useAlerts hook
 *
 * Tests the alert instance management mutations for acknowledging and dismissing alerts.
 *
 * @see NEM-3647 Alert Instance Management Endpoints
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest';

import {
  useAcknowledgeAlert,
  useDismissAlert,
  useAlertMutations,
} from './useAlerts';

import type { AlertResponse } from '../services/api';
import type { ReactNode } from 'react';

// Mock alert response helper
const createMockAlertResponse = (
  id: string,
  status: 'pending' | 'delivered' | 'acknowledged' | 'dismissed'
): AlertResponse => ({
  id,
  event_id: 123,
  rule_id: 'rule-uuid-123',
  severity: 'high',
  status,
  dedup_key: 'front_door:person:entry_zone',
  channels: ['pushover'],
  metadata: { camera_name: 'Front Door' },
  created_at: '2025-12-28T12:00:00Z',
  updated_at: '2025-12-28T12:01:00Z',
  delivered_at: '2025-12-28T12:00:30Z',
});

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

describe('useAlerts', () => {
  describe('useAcknowledgeAlert', () => {
    it('should acknowledge an alert successfully', async () => {
      const alertId = 'alert-uuid-123';
      server.use(
        http.post(`/api/alerts/${alertId}/acknowledge`, () => {
          return HttpResponse.json(createMockAlertResponse(alertId, 'acknowledged'));
        })
      );

      const { result } = renderHook(() => useAcknowledgeAlert(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.id).toBe(alertId);
      expect(result.current.data?.status).toBe('acknowledged');
    });

    it('should call onSuccess callback when successful', async () => {
      const alertId = 'alert-uuid-456';
      const onSuccess = vi.fn();

      server.use(
        http.post(`/api/alerts/${alertId}/acknowledge`, () => {
          return HttpResponse.json(createMockAlertResponse(alertId, 'acknowledged'));
        })
      );

      const { result } = renderHook(() => useAcknowledgeAlert({ onSuccess }), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(onSuccess).toHaveBeenCalledWith(
        expect.objectContaining({ id: alertId, status: 'acknowledged' }),
        alertId
      );
    });

    it('should handle 404 not found error', async () => {
      const alertId = 'non-existent-alert';
      const onError = vi.fn();

      server.use(
        http.post(`/api/alerts/${alertId}/acknowledge`, () => {
          return new HttpResponse(null, { status: 404 });
        })
      );

      const { result } = renderHook(() => useAcknowledgeAlert({ onError }), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(onError).toHaveBeenCalled();
    });

    it('should handle 409 conflict error (wrong status)', async () => {
      const alertId = 'already-acknowledged-alert';
      const onError = vi.fn();

      server.use(
        http.post(`/api/alerts/${alertId}/acknowledge`, () => {
          return HttpResponse.json(
            { detail: 'Alert cannot be acknowledged (wrong status)' },
            { status: 409 }
          );
        })
      );

      const { result } = renderHook(() => useAcknowledgeAlert({ onError }), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(onError).toHaveBeenCalled();
    });

    it('should call onSettled callback after completion', async () => {
      const alertId = 'alert-uuid-789';
      const onSettled = vi.fn();

      server.use(
        http.post(`/api/alerts/${alertId}/acknowledge`, () => {
          return HttpResponse.json(createMockAlertResponse(alertId, 'acknowledged'));
        })
      );

      const { result } = renderHook(() => useAcknowledgeAlert({ onSettled }), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(onSettled).toHaveBeenCalled());
      expect(onSettled).toHaveBeenCalledWith(
        expect.objectContaining({ id: alertId }),
        null,
        alertId
      );
    });

    it('should support mutateAsync for promise-based usage', async () => {
      const alertId = 'alert-uuid-async';

      server.use(
        http.post(`/api/alerts/${alertId}/acknowledge`, () => {
          return HttpResponse.json(createMockAlertResponse(alertId, 'acknowledged'));
        })
      );

      const { result } = renderHook(() => useAcknowledgeAlert(), {
        wrapper: createWrapper(),
      });

      const response = await result.current.mutateAsync(alertId);
      expect(response.id).toBe(alertId);
      expect(response.status).toBe('acknowledged');
    });

    it('should be able to reset mutation state', async () => {
      const alertId = 'alert-uuid-reset';

      server.use(
        http.post(`/api/alerts/${alertId}/acknowledge`, () => {
          return HttpResponse.json(createMockAlertResponse(alertId, 'acknowledged'));
        })
      );

      const { result } = renderHook(() => useAcknowledgeAlert(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      result.current.reset();

      // After reset, mutation should be idle (not success/error/pending)
      await waitFor(() => expect(result.current.data).toBeUndefined());
      expect(result.current.isPending).toBe(false);
      expect(result.current.isError).toBe(false);
    });
  });

  describe('useDismissAlert', () => {
    it('should dismiss an alert successfully', async () => {
      const alertId = 'alert-uuid-dismiss';
      server.use(
        http.post(`/api/alerts/${alertId}/dismiss`, () => {
          return HttpResponse.json(createMockAlertResponse(alertId, 'dismissed'));
        })
      );

      const { result } = renderHook(() => useDismissAlert(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.id).toBe(alertId);
      expect(result.current.data?.status).toBe('dismissed');
    });

    it('should call onSuccess callback when successful', async () => {
      const alertId = 'alert-uuid-dismiss-success';
      const onSuccess = vi.fn();

      server.use(
        http.post(`/api/alerts/${alertId}/dismiss`, () => {
          return HttpResponse.json(createMockAlertResponse(alertId, 'dismissed'));
        })
      );

      const { result } = renderHook(() => useDismissAlert({ onSuccess }), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(onSuccess).toHaveBeenCalledWith(
        expect.objectContaining({ id: alertId, status: 'dismissed' }),
        alertId
      );
    });

    it('should handle 404 not found error', async () => {
      const alertId = 'non-existent-dismiss-alert';
      const onError = vi.fn();

      server.use(
        http.post(`/api/alerts/${alertId}/dismiss`, () => {
          return new HttpResponse(null, { status: 404 });
        })
      );

      const { result } = renderHook(() => useDismissAlert({ onError }), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(onError).toHaveBeenCalled();
    });

    it('should handle 409 conflict error (concurrent modification)', async () => {
      const alertId = 'concurrent-dismiss-alert';
      const onError = vi.fn();

      server.use(
        http.post(`/api/alerts/${alertId}/dismiss`, () => {
          return HttpResponse.json(
            { detail: 'Alert was modified concurrently' },
            { status: 409 }
          );
        })
      );

      const { result } = renderHook(() => useDismissAlert({ onError }), {
        wrapper: createWrapper(),
      });

      result.current.mutate(alertId);

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(onError).toHaveBeenCalled();
    });

    it('should support dismissAlert helper function', async () => {
      const alertId = 'alert-uuid-helper';

      server.use(
        http.post(`/api/alerts/${alertId}/dismiss`, () => {
          return HttpResponse.json(createMockAlertResponse(alertId, 'dismissed'));
        })
      );

      const { result } = renderHook(() => useDismissAlert(), {
        wrapper: createWrapper(),
      });

      const response = await result.current.dismissAlert(alertId);
      expect(response.id).toBe(alertId);
      expect(response.status).toBe('dismissed');
    });
  });

  describe('useAlertMutations', () => {
    it('should provide both acknowledge and dismiss mutations', async () => {
      const acknowledgeId = 'alert-combined-ack';
      const dismissId = 'alert-combined-dismiss';

      server.use(
        http.post(`/api/alerts/${acknowledgeId}/acknowledge`, () => {
          return HttpResponse.json(createMockAlertResponse(acknowledgeId, 'acknowledged'));
        }),
        http.post(`/api/alerts/${dismissId}/dismiss`, () => {
          return HttpResponse.json(createMockAlertResponse(dismissId, 'dismissed'));
        })
      );

      const { result } = renderHook(() => useAlertMutations(), {
        wrapper: createWrapper(),
      });

      // Test acknowledge
      result.current.acknowledge.mutate(acknowledgeId);
      await waitFor(() => expect(result.current.acknowledge.isSuccess).toBe(true));
      expect(result.current.acknowledge.data?.status).toBe('acknowledged');

      // Test dismiss
      result.current.dismiss.mutate(dismissId);
      await waitFor(() => expect(result.current.dismiss.isSuccess).toBe(true));
      expect(result.current.dismiss.data?.status).toBe('dismissed');
    });

    it('should have independent pending states', async () => {
      const acknowledgeId = 'alert-pending-ack';
      const dismissId = 'alert-pending-dismiss';

      // Set up delayed responses to test concurrent states
      server.use(
        http.post(`/api/alerts/${acknowledgeId}/acknowledge`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(createMockAlertResponse(acknowledgeId, 'acknowledged'));
        }),
        http.post(`/api/alerts/${dismissId}/dismiss`, () => {
          return HttpResponse.json(createMockAlertResponse(dismissId, 'dismissed'));
        })
      );

      const { result } = renderHook(() => useAlertMutations(), {
        wrapper: createWrapper(),
      });

      // Start acknowledge (will be pending)
      result.current.acknowledge.mutate(acknowledgeId);

      // Immediately dismiss should work independently
      result.current.dismiss.mutate(dismissId);

      // Dismiss should complete before acknowledge
      await waitFor(() => expect(result.current.dismiss.isSuccess).toBe(true));

      // Acknowledge should still be pending or now complete
      await waitFor(() => expect(result.current.acknowledge.isSuccess).toBe(true));
    });
  });
});
