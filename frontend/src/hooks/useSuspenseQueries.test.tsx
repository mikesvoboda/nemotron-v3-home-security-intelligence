/**
 * Tests for useSuspenseQueries hooks (NEM-3360)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { Suspense } from 'react';
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';

import {
  useSuspenseCamerasQuery,
  useSuspenseHealthQuery,
  useSuspenseSettingsQuery,
  useSuspenseNotificationPreferencesQuery,
  useSuspenseEventsInfiniteQuery,
} from './useSuspenseQueries';

import type { ReactNode } from 'react';

// ============================================================================
// Mock Data
// ============================================================================

const mockCameras = [
  {
    id: 'cam-1',
    name: 'Front Door',
    status: 'online',
    folder_path: '/cameras/front',
    last_seen_at: null,
    created_at: '2024-01-01',
  },
  {
    id: 'cam-2',
    name: 'Backyard',
    status: 'online',
    folder_path: '/cameras/back',
    last_seen_at: null,
    created_at: '2024-01-01',
  },
];

const mockHealth = {
  status: 'healthy',
  ready: true,
  message: 'All systems operational',
  postgres: { status: 'healthy', latency_ms: 5 },
  redis: { status: 'healthy', latency_ms: 2 },
  ai_services: [],
  workers: [],
  circuit_breakers: { total: 0, open: 0, half_open: 0 },
};

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

const mockEvents = {
  items: [
    {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 75,
      risk_level: 'high',
      started_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 2,
      camera_id: 'cam-2',
      risk_score: 25,
      risk_level: 'low',
      started_at: '2024-01-01T01:00:00Z',
    },
  ],
  pagination: {
    total: 2,
    has_more: false,
    next_cursor: null,
  },
};

// ============================================================================
// MSW Server Setup
// ============================================================================

const server = setupServer(
  http.get('/api/cameras', () => {
    return HttpResponse.json(mockCameras);
  }),
  http.get('/api/system/health/full', () => {
    return HttpResponse.json(mockHealth);
  }),
  http.get('/api/v1/settings', () => {
    return HttpResponse.json(mockSettings);
  }),
  http.get('/api/notification-preferences/', () => {
    return HttpResponse.json(mockNotificationPreferences);
  }),
  http.get('/api/events', () => {
    return HttpResponse.json(mockEvents);
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterAll(() => server.close());
afterEach(() => {
  server.resetHandlers();
});

// ============================================================================
// Test Utilities
// ============================================================================

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <Suspense fallback={<div>Loading...</div>}>{children}</Suspense>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// useSuspenseCamerasQuery Tests
// ============================================================================

describe('useSuspenseCamerasQuery', () => {
  it('should return cameras data', async () => {
    const { result } = renderHook(() => useSuspenseCamerasQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.cameras.length).toBeGreaterThan(0);
    });

    expect(result.current.cameras[0]).toHaveProperty('name');
    expect(result.current.cameras[0]).toHaveProperty('id');
  });

  it('should provide refetch function', async () => {
    const { result } = renderHook(() => useSuspenseCamerasQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.cameras).toBeDefined();
    });

    expect(typeof result.current.refetch).toBe('function');
  });

  it('should expose isRefetching state', async () => {
    const { result } = renderHook(() => useSuspenseCamerasQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.cameras).toBeDefined();
    });

    expect(typeof result.current.isRefetching).toBe('boolean');
  });
});

// ============================================================================
// useSuspenseHealthQuery Tests
// ============================================================================

describe('useSuspenseHealthQuery', () => {
  it('should return health data', async () => {
    const { result } = renderHook(() => useSuspenseHealthQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.health).toBeDefined();
    });

    expect(result.current.health.status).toBe('healthy');
    expect(result.current.isReady).toBe(true);
    expect(result.current.statusMessage).toBe('All systems operational');
  });

  it('should derive isReady from health data', async () => {
    const { result } = renderHook(() => useSuspenseHealthQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.health).toBeDefined();
    });

    expect(result.current.isReady).toBe(mockHealth.ready);
  });

  it('should derive statusMessage from health data', async () => {
    const { result } = renderHook(() => useSuspenseHealthQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.health).toBeDefined();
    });

    expect(result.current.statusMessage).toBe(mockHealth.message);
  });
});

// ============================================================================
// useSuspenseSettingsQuery Tests
// ============================================================================

describe('useSuspenseSettingsQuery', () => {
  it('should return settings data', async () => {
    const { result } = renderHook(() => useSuspenseSettingsQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.settings).toBeDefined();
    });

    expect(result.current.settings.detection.confidence_threshold).toBe(0.5);
    expect(result.current.settings.features.reid_enabled).toBe(true);
  });

  it('should provide all settings categories', async () => {
    const { result } = renderHook(() => useSuspenseSettingsQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.settings).toBeDefined();
    });

    expect(result.current.settings).toHaveProperty('detection');
    expect(result.current.settings).toHaveProperty('batch');
    expect(result.current.settings).toHaveProperty('severity');
    expect(result.current.settings).toHaveProperty('features');
    expect(result.current.settings).toHaveProperty('rate_limiting');
    expect(result.current.settings).toHaveProperty('queue');
    expect(result.current.settings).toHaveProperty('retention');
  });
});

// ============================================================================
// useSuspenseNotificationPreferencesQuery Tests
// ============================================================================

describe('useSuspenseNotificationPreferencesQuery', () => {
  it('should return notification preferences', async () => {
    const { result } = renderHook(() => useSuspenseNotificationPreferencesQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.preferences).toBeDefined();
    });

    expect(result.current.preferences.enabled).toBe(true);
    expect(result.current.preferences.sound).toBe('default');
  });
});

// ============================================================================
// useSuspenseEventsInfiniteQuery Tests
// ============================================================================

describe('useSuspenseEventsInfiniteQuery', () => {
  it('should return events data', async () => {
    const { result } = renderHook(() => useSuspenseEventsInfiniteQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.events.length).toBeGreaterThan(0);
    });

    expect(result.current.events[0]).toHaveProperty('id');
    expect(result.current.events[0]).toHaveProperty('camera_id');
  });

  it('should provide total count', async () => {
    const { result } = renderHook(() => useSuspenseEventsInfiniteQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.events.length).toBeGreaterThan(0);
    });

    expect(result.current.totalCount).toBeGreaterThanOrEqual(0);
  });

  it('should provide hasNextPage boolean', async () => {
    const { result } = renderHook(() => useSuspenseEventsInfiniteQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.events).toBeDefined();
    });

    expect(typeof result.current.hasNextPage).toBe('boolean');
  });

  it('should accept filter options', async () => {
    const { result } = renderHook(
      () =>
        useSuspenseEventsInfiniteQuery({
          filters: { risk_level: 'high' },
          limit: 10,
        }),
      {
        wrapper: createWrapper(),
      }
    );

    await waitFor(() => {
      expect(result.current.events).toBeDefined();
    });
  });

  it('should provide fetchNextPage function', async () => {
    const { result } = renderHook(() => useSuspenseEventsInfiniteQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.events).toBeDefined();
    });

    expect(typeof result.current.fetchNextPage).toBe('function');
  });

  it('should provide isFetchingNextPage state', async () => {
    const { result } = renderHook(() => useSuspenseEventsInfiniteQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.events).toBeDefined();
    });

    expect(typeof result.current.isFetchingNextPage).toBe('boolean');
  });
});
