/**
 * Tests for useAdminMutations hook
 *
 * Tests the admin seed and cleanup mutations for the Developer Tools page.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';

import {
  useAdminMutations,
  useSeedCamerasMutation,
  useSeedEventsMutation,
  useSeedPipelineLatencyMutation,
  useClearSeededDataMutation,
} from './useAdminMutations';

import type { ReactNode } from 'react';

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

describe('useAdminMutations', () => {
  describe('useSeedCamerasMutation', () => {
    it('should seed cameras with specified count', async () => {
      server.use(
        http.post('/api/admin/seed/cameras', async ({ request }) => {
          const body = (await request.json()) as { count: number };
          return HttpResponse.json({
            cameras: Array.from({ length: body.count }, (_, i) => ({ id: `cam-${i}` })),
            cleared: 0,
            created: body.count,
          });
        })
      );

      const { result } = renderHook(() => useSeedCamerasMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ count: 5 });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.created).toBe(5);
    });

    it('should clear existing cameras when requested', async () => {
      server.use(
        http.post('/api/admin/seed/cameras', async ({ request }) => {
          const body = (await request.json()) as { count: number; clear_existing: boolean };
          return HttpResponse.json({
            cameras: Array.from({ length: body.count }, (_, i) => ({ id: `cam-${i}` })),
            cleared: body.clear_existing ? 3 : 0,
            created: body.count,
          });
        })
      );

      const { result } = renderHook(() => useSeedCamerasMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ count: 5, clear_existing: true });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.cleared).toBe(3);
    });

    it('should handle errors', async () => {
      server.use(
        http.post('/api/admin/seed/cameras', () => {
          return HttpResponse.json({ detail: 'Admin access not enabled' }, { status: 403 });
        })
      );

      const { result } = renderHook(() => useSeedCamerasMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ count: 5 });

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('Admin access not enabled');
    });
  });

  describe('useSeedEventsMutation', () => {
    it('should seed events with specified count', async () => {
      server.use(
        http.post('/api/admin/seed/events', async ({ request }) => {
          const body = (await request.json()) as { count: number };
          return HttpResponse.json({
            events_cleared: 0,
            events_created: body.count,
            detections_cleared: 0,
            detections_created: body.count * 3,
          });
        })
      );

      const { result } = renderHook(() => useSeedEventsMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ count: 100 });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.events_created).toBe(100);
      expect(result.current.data?.detections_created).toBe(300);
    });

    it('should handle no cameras error', async () => {
      server.use(
        http.post('/api/admin/seed/events', () => {
          return HttpResponse.json(
            { detail: 'No cameras found. Seed cameras first.' },
            { status: 400 }
          );
        })
      );

      const { result } = renderHook(() => useSeedEventsMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ count: 100 });

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('No cameras found');
    });
  });

  describe('useSeedPipelineLatencyMutation', () => {
    it('should seed pipeline latency data', async () => {
      server.use(
        http.post('/api/admin/seed/pipeline-latency', async ({ request }) => {
          const body = (await request.json()) as { num_samples: number; time_span_hours: number };
          return HttpResponse.json({
            message: 'Pipeline latency data seeded successfully',
            samples_per_stage: body.num_samples,
            stages_seeded: [
              'watch_to_detect',
              'detect_to_batch',
              'batch_to_analyze',
              'total_pipeline',
            ],
            time_span_hours: body.time_span_hours,
          });
        })
      );

      const { result } = renderHook(() => useSeedPipelineLatencyMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ num_samples: 100, time_span_hours: 24 });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.samples_per_stage).toBe(100);
      expect(result.current.data?.time_span_hours).toBe(24);
    });

    it('should use default values for time span', async () => {
      server.use(
        http.post('/api/admin/seed/pipeline-latency', async ({ request }) => {
          const body = (await request.json()) as { time_span_hours?: number };
          // API defaults time_span_hours to 24 if not provided
          const timeSpan = body.time_span_hours ?? 24;
          return HttpResponse.json({
            message: 'Pipeline latency data seeded successfully',
            samples_per_stage: 100,
            stages_seeded: [
              'watch_to_detect',
              'detect_to_batch',
              'batch_to_analyze',
              'total_pipeline',
            ],
            time_span_hours: timeSpan,
          });
        })
      );

      const { result } = renderHook(() => useSeedPipelineLatencyMutation(), {
        wrapper: createWrapper(),
      });

      // Call with time_span_hours as days * 24 (7 days = 168 hours)
      result.current.mutate({ time_span_hours: 168 });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.time_span_hours).toBe(168);
    });
  });

  describe('useClearSeededDataMutation', () => {
    it('should clear all seeded data with correct confirmation', async () => {
      server.use(
        http.delete('/api/admin/seed/clear', async ({ request }) => {
          const body = (await request.json()) as { confirm: string };
          if (body.confirm !== 'DELETE_ALL_DATA') {
            return HttpResponse.json({ detail: 'Invalid confirmation string' }, { status: 400 });
          }
          return HttpResponse.json({
            cameras_cleared: 5,
            events_cleared: 100,
            detections_cleared: 300,
          });
        })
      );

      const { result } = renderHook(() => useClearSeededDataMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ confirm: 'DELETE_ALL_DATA' });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.events_cleared).toBe(100);
    });

    it('should reject invalid confirmation string', async () => {
      server.use(
        http.delete('/api/admin/seed/clear', async ({ request }) => {
          const body = (await request.json()) as { confirm: string };
          if (body.confirm !== 'DELETE_ALL_DATA') {
            return HttpResponse.json(
              { detail: 'Invalid confirmation string. Expected: DELETE_ALL_DATA' },
              { status: 400 }
            );
          }
          return HttpResponse.json({
            cameras_cleared: 5,
            events_cleared: 100,
            detections_cleared: 300,
          });
        })
      );

      const { result } = renderHook(() => useClearSeededDataMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ confirm: 'WRONG_STRING' });

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.error?.message).toContain('Invalid confirmation string');
    });
  });

  describe('useAdminMutations (combined)', () => {
    it('should return all mutation hooks', () => {
      const { result } = renderHook(() => useAdminMutations(), {
        wrapper: createWrapper(),
      });

      expect(result.current.seedCameras).toBeDefined();
      expect(result.current.seedEvents).toBeDefined();
      expect(result.current.seedPipelineLatency).toBeDefined();
      expect(result.current.clearSeededData).toBeDefined();
    });
  });
});
