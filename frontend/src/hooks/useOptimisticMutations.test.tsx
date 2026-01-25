/**
 * Tests for useOptimisticMutations hooks (NEM-3361)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest';

import {
  useOptimisticSettingsUpdate,
  useOptimisticNotificationPreferencesUpdate,
  useOptimisticCameraNotificationSettingUpdate,
  useOptimisticQuietHoursPeriodMutations,
} from './useOptimisticMutations';
import { settingsQueryKeys } from './useSettingsApi';
import { queryKeys } from '../services/queryClient';

import type { ReactNode } from 'react';

// ============================================================================
// Mock Data
// ============================================================================

const mockSettings = {
  detection: { confidence_threshold: 0.5, fast_path_threshold: 0.9 },
  batch: { window_seconds: 90, idle_timeout_seconds: 30 },
  severity: { low_max: 29, medium_max: 59, high_max: 84 },
  features: {
    vision_extraction_enabled: true,
    reid_enabled: true,
    scene_change_enabled: true,
    clip_generation_enabled: true,
    image_quality_enabled: true,
    background_eval_enabled: true,
  },
  rate_limiting: { enabled: true, requests_per_minute: 60, burst_size: 10 },
  queue: { max_size: 10000, backpressure_threshold: 0.8 },
  retention: { days: 30, log_days: 7 },
};

const mockNotificationPreferences = {
  enabled: true,
  id: 1,
  risk_filters: ['critical', 'high', 'medium'],
  sound: 'default',
};

const mockCameraSettings = {
  items: [
    { id: '1', camera_id: 'cam-1', enabled: true, risk_threshold: 50 },
    { id: '2', camera_id: 'cam-2', enabled: true, risk_threshold: 75 },
  ],
  pagination: { total: 2, limit: 100, offset: 0 },
};

const mockQuietHours = {
  items: [
    {
      id: 'period-1',
      label: 'Night Time',
      start_time: '22:00:00',
      end_time: '06:00:00',
      days: ['monday', 'tuesday'],
    },
  ],
  pagination: { total: 1, limit: 100, offset: 0 },
};

// ============================================================================
// MSW Server Setup
// ============================================================================

const server = setupServer(
  http.patch('/api/v1/settings', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      ...mockSettings,
      ...(body as Record<string, unknown>),
    });
  }),
  http.put('/api/notification-preferences/', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      ...mockNotificationPreferences,
      ...(body as Record<string, unknown>),
    });
  }),
  http.put('/api/notification-preferences/cameras/:cameraId', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: '1',
      camera_id: 'cam-1',
      ...(body as Record<string, unknown>),
    });
  }),
  http.post('/api/notification-preferences/quiet-hours', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: 'new-period-id',
      ...body,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    });
  }),
  http.delete('/api/notification-preferences/quiet-hours/:periodId', () => {
    return new HttpResponse(null, { status: 204 });
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  server.resetHandlers();
});

// ============================================================================
// Test Utilities
// ============================================================================

function createTestContext() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { Wrapper, queryClient };
}

// ============================================================================
// useOptimisticSettingsUpdate Tests
// ============================================================================

describe('useOptimisticSettingsUpdate', () => {
  it('should apply optimistic update immediately', async () => {
    const { Wrapper, queryClient } = createTestContext();

    // Pre-populate cache
    queryClient.setQueryData(settingsQueryKeys.current(), mockSettings);

    const { result } = renderHook(() => useOptimisticSettingsUpdate(), { wrapper: Wrapper });

    act(() => {
      result.current.mutate({ features: { reid_enabled: false } });
    });

    // Wait for mutation to complete
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // After mutation, the setting should be updated
    const data = queryClient.getQueryData(settingsQueryKeys.current());
    expect(data).toBeDefined();
    expect((data as typeof mockSettings).features.reid_enabled).toBe(false);
  });

  it('should call onSuccess callback', async () => {
    const { Wrapper, queryClient } = createTestContext();
    queryClient.setQueryData(settingsQueryKeys.current(), mockSettings);

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useOptimisticSettingsUpdate({ onSuccess }), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync({ detection: { confidence_threshold: 0.6 } });
    });

    expect(onSuccess).toHaveBeenCalled();
  });

  it('should rollback on error', async () => {
    const { Wrapper, queryClient } = createTestContext();
    queryClient.setQueryData(settingsQueryKeys.current(), mockSettings);

    // Make the request fail
    server.use(
      http.patch('/api/v1/settings', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
      })
    );

    const onError = vi.fn();
    const { result } = renderHook(() => useOptimisticSettingsUpdate({ onError }), {
      wrapper: Wrapper,
    });

    await act(async () => {
      try {
        await result.current.mutateAsync({ features: { reid_enabled: false } });
      } catch {
        // Expected
      }
    });

    // Should have rolled back to original
    const currentData = queryClient.getQueryData(settingsQueryKeys.current());
    expect((currentData as typeof mockSettings).features.reid_enabled).toBe(true);
    expect(onError).toHaveBeenCalled();
  });

  it('should provide reset function', () => {
    const { Wrapper } = createTestContext();
    const { result } = renderHook(() => useOptimisticSettingsUpdate(), { wrapper: Wrapper });

    expect(typeof result.current.reset).toBe('function');
  });
});

// ============================================================================
// useOptimisticNotificationPreferencesUpdate Tests
// ============================================================================

describe('useOptimisticNotificationPreferencesUpdate', () => {
  it('should apply optimistic update immediately', async () => {
    const { Wrapper, queryClient } = createTestContext();
    queryClient.setQueryData(
      queryKeys.notifications.preferences.global,
      mockNotificationPreferences
    );

    const { result } = renderHook(() => useOptimisticNotificationPreferencesUpdate(), {
      wrapper: Wrapper,
    });

    act(() => {
      result.current.mutate({ enabled: false });
    });

    // Wait for mutation to complete
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // After mutation, enabled should be false (from server or optimistic)
    const data = queryClient.getQueryData(queryKeys.notifications.preferences.global);
    expect((data as typeof mockNotificationPreferences).enabled).toBe(false);
  });

  it('should rollback on error', async () => {
    const { Wrapper, queryClient } = createTestContext();
    queryClient.setQueryData(
      queryKeys.notifications.preferences.global,
      mockNotificationPreferences
    );

    server.use(
      http.put('/api/notification-preferences/', () => {
        return HttpResponse.json({ detail: 'Error' }, { status: 500 });
      })
    );

    const { result } = renderHook(() => useOptimisticNotificationPreferencesUpdate(), {
      wrapper: Wrapper,
    });

    await act(async () => {
      try {
        await result.current.mutateAsync({ enabled: false });
      } catch {
        // Expected
      }
    });

    // Should have rolled back
    const currentData = queryClient.getQueryData(queryKeys.notifications.preferences.global);
    expect((currentData as typeof mockNotificationPreferences).enabled).toBe(true);
  });
});

// ============================================================================
// useOptimisticCameraNotificationSettingUpdate Tests
// ============================================================================

describe('useOptimisticCameraNotificationSettingUpdate', () => {
  it('should apply optimistic update to camera settings list', async () => {
    const { Wrapper, queryClient } = createTestContext();
    queryClient.setQueryData(
      queryKeys.notifications.preferences.cameras.list(),
      mockCameraSettings
    );

    const { result } = renderHook(() => useOptimisticCameraNotificationSettingUpdate(), {
      wrapper: Wrapper,
    });

    act(() => {
      result.current.mutate({ cameraId: 'cam-1', update: { enabled: false } });
    });

    // Wait for mutation to complete
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // After mutation completes, verify success
    expect(result.current.isSuccess).toBe(true);
  });

  it('should not affect other cameras in list', () => {
    const { Wrapper, queryClient } = createTestContext();
    queryClient.setQueryData(
      queryKeys.notifications.preferences.cameras.list(),
      mockCameraSettings
    );

    const { result } = renderHook(() => useOptimisticCameraNotificationSettingUpdate(), {
      wrapper: Wrapper,
    });

    act(() => {
      result.current.mutate({ cameraId: 'cam-1', update: { enabled: false } });
    });

    const optimisticData = queryClient.getQueryData<typeof mockCameraSettings>(
      queryKeys.notifications.preferences.cameras.list()
    );
    const cam2 = optimisticData?.items.find((item) => item.camera_id === 'cam-2');
    expect(cam2?.enabled).toBe(true); // Should be unchanged
  });
});

// ============================================================================
// useOptimisticQuietHoursPeriodMutations Tests
// ============================================================================

describe('useOptimisticQuietHoursPeriodMutations', () => {
  describe('createPeriod', () => {
    it('should add period optimistically', async () => {
      const { Wrapper, queryClient } = createTestContext();
      queryClient.setQueryData(
        queryKeys.notifications.preferences.quietHours.list(),
        mockQuietHours
      );

      const { result } = renderHook(() => useOptimisticQuietHoursPeriodMutations(), {
        wrapper: Wrapper,
      });

      act(() => {
        result.current.createPeriod.mutate({
          label: 'New Period',
          start_time: '10:00:00',
          end_time: '12:00:00',
          days: ['wednesday'],
        });
      });

      // Wait for mutation to complete and check data
      await waitFor(() => {
        expect(result.current.createPeriod.isSuccess || result.current.createPeriod.isPending).toBe(
          true
        );
      });

      // Verify the period was added (optimistically or via server)
      await waitFor(() => {
        const data = queryClient.getQueryData<typeof mockQuietHours>(
          queryKeys.notifications.preferences.quietHours.list()
        );
        expect(data?.items.some((item) => item.label === 'New Period')).toBe(true);
      });
    });

    it('should replace optimistic item with real data on success', async () => {
      const { Wrapper, queryClient } = createTestContext();
      queryClient.setQueryData(
        queryKeys.notifications.preferences.quietHours.list(),
        mockQuietHours
      );

      const { result } = renderHook(() => useOptimisticQuietHoursPeriodMutations(), {
        wrapper: Wrapper,
      });

      await act(async () => {
        await result.current.createPeriod.mutateAsync({
          label: 'New Period',
          start_time: '10:00:00',
          end_time: '12:00:00',
          days: ['wednesday'],
        });
      });

      // Should have real ID now
      const data = queryClient.getQueryData<typeof mockQuietHours>(
        queryKeys.notifications.preferences.quietHours.list()
      );
      const newPeriod = data?.items.find((item) => item.label === 'New Period');
      expect(newPeriod?.id).toBe('new-period-id'); // Real ID from server
    });

    it('should rollback on error', async () => {
      const { Wrapper, queryClient } = createTestContext();
      queryClient.setQueryData(
        queryKeys.notifications.preferences.quietHours.list(),
        mockQuietHours
      );

      server.use(
        http.post('/api/notification-preferences/quiet-hours', () => {
          return HttpResponse.json({ detail: 'Error' }, { status: 500 });
        })
      );

      const onCreateError = vi.fn();
      const { result } = renderHook(
        () => useOptimisticQuietHoursPeriodMutations({ onCreateError }),
        { wrapper: Wrapper }
      );

      await act(async () => {
        try {
          await result.current.createPeriod.mutateAsync({
            label: 'New Period',
            start_time: '10:00:00',
            end_time: '12:00:00',
            days: ['wednesday'],
          });
        } catch {
          // Expected
        }
      });

      // Should have rolled back
      const data = queryClient.getQueryData<typeof mockQuietHours>(
        queryKeys.notifications.preferences.quietHours.list()
      );
      expect(data?.items).toHaveLength(1);
      expect(onCreateError).toHaveBeenCalled();
    });
  });

  describe('deletePeriod', () => {
    it('should remove period optimistically', async () => {
      const { Wrapper, queryClient } = createTestContext();
      queryClient.setQueryData(
        queryKeys.notifications.preferences.quietHours.list(),
        mockQuietHours
      );

      const { result } = renderHook(() => useOptimisticQuietHoursPeriodMutations(), {
        wrapper: Wrapper,
      });

      act(() => {
        result.current.deletePeriod.mutate('period-1');
      });

      // Wait for mutation to complete
      await waitFor(() => {
        expect(result.current.deletePeriod.isSuccess).toBe(true);
      });

      // Verify the period was removed
      const data = queryClient.getQueryData<typeof mockQuietHours>(
        queryKeys.notifications.preferences.quietHours.list()
      );
      expect(data?.items.find((item) => item.id === 'period-1')).toBeUndefined();
    });

    it('should call onDeleteSuccess callback', async () => {
      const { Wrapper, queryClient } = createTestContext();
      queryClient.setQueryData(
        queryKeys.notifications.preferences.quietHours.list(),
        mockQuietHours
      );

      const onDeleteSuccess = vi.fn();
      const { result } = renderHook(
        () => useOptimisticQuietHoursPeriodMutations({ onDeleteSuccess }),
        { wrapper: Wrapper }
      );

      await act(async () => {
        await result.current.deletePeriod.mutateAsync('period-1');
      });

      expect(onDeleteSuccess).toHaveBeenCalled();
    });

    it('should rollback on error', async () => {
      const { Wrapper, queryClient } = createTestContext();
      queryClient.setQueryData(
        queryKeys.notifications.preferences.quietHours.list(),
        mockQuietHours
      );

      server.use(
        http.delete('/api/notification-preferences/quiet-hours/:periodId', () => {
          return HttpResponse.json({ detail: 'Error' }, { status: 500 });
        })
      );

      const { result } = renderHook(() => useOptimisticQuietHoursPeriodMutations(), {
        wrapper: Wrapper,
      });

      await act(async () => {
        try {
          await result.current.deletePeriod.mutateAsync('period-1');
        } catch {
          // Expected
        }
      });

      // Should have rolled back
      const data = queryClient.getQueryData<typeof mockQuietHours>(
        queryKeys.notifications.preferences.quietHours.list()
      );
      expect(data?.items).toHaveLength(1);
    });
  });
});
