/**
 * Tests for useSettingsApi hook
 *
 * Tests the settings API hooks for fetching and updating system settings.
 * Part of Phase 2.3 of the Orphaned Infrastructure Integration epic (NEM-3113).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest';

import {
  useSettingsQuery,
  useUpdateSettings,
  useSettingsApi,
  settingsQueryKeys,
  fetchSettings,
  updateSettings,
  type SettingsResponse,
  type SettingsUpdate,
} from './useSettingsApi';

import type { ReactNode } from 'react';

// ============================================================================
// Mock Data
// ============================================================================

const mockSettingsResponse: SettingsResponse = {
  detection: {
    confidence_threshold: 0.5,
    fast_path_threshold: 0.9,
  },
  batch: {
    window_seconds: 90,
    idle_timeout_seconds: 30,
  },
  severity: {
    low_max: 29,
    medium_max: 59,
    high_max: 84,
  },
  features: {
    vision_extraction_enabled: true,
    reid_enabled: true,
    scene_change_enabled: true,
    clip_generation_enabled: true,
    image_quality_enabled: true,
    background_eval_enabled: true,
  },
  rate_limiting: {
    enabled: true,
    requests_per_minute: 60,
    burst_size: 10,
  },
  queue: {
    max_size: 10000,
    backpressure_threshold: 0.8,
  },
  retention: {
    days: 30,
    log_days: 7,
  },
};

const updatedSettingsResponse: SettingsResponse = {
  ...mockSettingsResponse,
  detection: {
    ...mockSettingsResponse.detection,
    confidence_threshold: 0.6,
  },
  features: {
    ...mockSettingsResponse.features,
    reid_enabled: false,
  },
};

// ============================================================================
// MSW Server Setup
// ============================================================================

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  server.resetHandlers();
});

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Create a wrapper with QueryClientProvider for testing hooks.
 */
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

/**
 * Create a wrapper with a custom QueryClient for testing cache invalidation.
 */
function createWrapperWithClient(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ============================================================================
// Query Key Tests
// ============================================================================

describe('settingsQueryKeys', () => {
  it('should have correct base key', () => {
    expect(settingsQueryKeys.all).toEqual(['settings']);
  });

  it('should generate correct current key', () => {
    expect(settingsQueryKeys.current()).toEqual(['settings', 'current']);
  });
});

// ============================================================================
// API Function Tests
// ============================================================================

describe('fetchSettings', () => {
  it('should fetch settings from API', async () => {
    server.use(
      http.get('/api/v1/settings', () => {
        return HttpResponse.json(mockSettingsResponse);
      })
    );

    const result = await fetchSettings();
    expect(result).toEqual(mockSettingsResponse);
  });

  it('should throw error on API failure', async () => {
    server.use(
      http.get('/api/v1/settings', () => {
        return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 });
      })
    );

    await expect(fetchSettings()).rejects.toThrow('Internal server error');
  });

  it('should handle non-JSON error responses', async () => {
    server.use(
      http.get('/api/v1/settings', () => {
        return new HttpResponse('Service Unavailable', { status: 503 });
      })
    );

    await expect(fetchSettings()).rejects.toThrow('HTTP 503');
  });
});

describe('updateSettings', () => {
  it('should update settings via API', async () => {
    const updatePayload: SettingsUpdate = {
      detection: { confidence_threshold: 0.6 },
    };

    server.use(
      http.patch('/api/v1/settings', async ({ request }) => {
        const body = (await request.json()) as SettingsUpdate;
        expect(body).toEqual(updatePayload);
        return HttpResponse.json(updatedSettingsResponse);
      })
    );

    const result = await updateSettings(updatePayload);
    expect(result.detection.confidence_threshold).toBe(0.6);
  });

  it('should throw error on validation failure', async () => {
    server.use(
      http.patch('/api/v1/settings', () => {
        return HttpResponse.json(
          { detail: 'low_max (50) must be less than medium_max (40)' },
          { status: 422 }
        );
      })
    );

    await expect(
      updateSettings({ severity: { low_max: 50, medium_max: 40 } })
    ).rejects.toThrow('low_max (50) must be less than medium_max (40)');
  });
});

// ============================================================================
// useSettings Hook Tests
// ============================================================================

describe('useSettingsQuery', () => {
  describe('initialization', () => {
    it('should start with isLoading true', () => {
      server.use(
        http.get('/api/v1/settings', async () => {
          // Delay response to test loading state
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockSettingsResponse);
        })
      );

      const { result } = renderHook(() => useSettingsQuery(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.settings).toBeUndefined();
    });
  });

  describe('fetching data', () => {
    it('should fetch settings on mount', async () => {
      server.use(
        http.get('/api/v1/settings', () => {
          return HttpResponse.json(mockSettingsResponse);
        })
      );

      const { result } = renderHook(() => useSettingsQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.settings).toEqual(mockSettingsResponse);
      expect(result.current.isLoading).toBe(false);
    });

    it('should set error on fetch failure', async () => {
      server.use(
        http.get('/api/v1/settings', () => {
          return HttpResponse.json({ detail: 'Failed to load settings' }, { status: 500 });
        })
      );

      const { result } = renderHook(() => useSettingsQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.error?.message).toContain('Failed to load settings');
    });
  });

  describe('enabled option', () => {
    it('should not fetch when enabled is false', async () => {
      const fetchSpy = vi.fn();
      server.use(
        http.get('/api/v1/settings', () => {
          fetchSpy();
          return HttpResponse.json(mockSettingsResponse);
        })
      );

      renderHook(() => useSettingsQuery({ enabled: false }), {
        wrapper: createWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it('should fetch when enabled changes to true', async () => {
      server.use(
        http.get('/api/v1/settings', () => {
          return HttpResponse.json(mockSettingsResponse);
        })
      );

      const { result, rerender } = renderHook(
        ({ enabled }) => useSettingsQuery({ enabled }),
        {
          wrapper: createWrapper(),
          initialProps: { enabled: false },
        }
      );

      expect(result.current.isLoading).toBe(false);
      expect(result.current.settings).toBeUndefined();

      rerender({ enabled: true });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.settings).toEqual(mockSettingsResponse);
    });
  });

  describe('refetch', () => {
    it('should provide refetch function', async () => {
      let callCount = 0;
      server.use(
        http.get('/api/v1/settings', () => {
          callCount++;
          return HttpResponse.json(mockSettingsResponse);
        })
      );

      const { result } = renderHook(() => useSettingsQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(callCount).toBe(1);

      await act(async () => {
        await result.current.refetch();
      });

      expect(callCount).toBe(2);
    });
  });
});

// ============================================================================
// useUpdateSettings Hook Tests
// ============================================================================

describe('useUpdateSettings', () => {
  it('should update settings successfully', async () => {
    server.use(
      http.patch('/api/v1/settings', () => {
        return HttpResponse.json(updatedSettingsResponse);
      })
    );

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        detection: { confidence_threshold: 0.6 },
      });
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data?.detection.confidence_threshold).toBe(0.6);
  });

  it('should set error on update failure', async () => {
    server.use(
      http.patch('/api/v1/settings', () => {
        return HttpResponse.json(
          { detail: 'Invalid threshold value' },
          { status: 422 }
        );
      })
    );

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync({
          detection: { confidence_threshold: 1.5 },
        });
      } catch {
        // Expected to throw
      }
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toContain('Invalid threshold value');
  });

  it('should invalidate settings cache on success', async () => {
    // First, set up the GET endpoint
    server.use(
      http.get('/api/v1/settings', () => {
        return HttpResponse.json(mockSettingsResponse);
      }),
      http.patch('/api/v1/settings', () => {
        return HttpResponse.json(updatedSettingsResponse);
      })
    );

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapperWithClient(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        detection: { confidence_threshold: 0.6 },
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: settingsQueryKeys.all,
    });
  });

  it('should update cache data directly on success', async () => {
    server.use(
      http.patch('/api/v1/settings', () => {
        return HttpResponse.json(updatedSettingsResponse);
      })
    );

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const setQueryDataSpy = vi.spyOn(queryClient, 'setQueryData');

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapperWithClient(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        detection: { confidence_threshold: 0.6 },
      });
    });

    expect(setQueryDataSpy).toHaveBeenCalledWith(
      settingsQueryKeys.current(),
      updatedSettingsResponse
    );
  });

  it('should expose isPending state', async () => {
    server.use(
      http.patch('/api/v1/settings', async () => {
        // Delay response to allow checking isPending
        await new Promise((resolve) => setTimeout(resolve, 200));
        return HttpResponse.json(updatedSettingsResponse);
      })
    );

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    // Start the mutation without awaiting
    act(() => {
      result.current.mutate({ detection: { confidence_threshold: 0.6 } });
    });

    // Wait a tick for the mutation to start
    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });

    // Wait for the mutation to complete
    await waitFor(
      () => {
        expect(result.current.isPending).toBe(false);
      },
      { timeout: 1000 }
    );

    expect(result.current.isSuccess).toBe(true);
  });

  it('should expose reset function', async () => {
    server.use(
      http.patch('/api/v1/settings', () => {
        return HttpResponse.json(updatedSettingsResponse);
      })
    );

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        detection: { confidence_threshold: 0.6 },
      });
    });

    // Wait for mutation to complete
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    act(() => {
      result.current.reset();
    });

    // Wait for the reset to take effect
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
    });

    expect(result.current.data).toBeUndefined();
  });
});

// ============================================================================
// useSettingsApi Combined Hook Tests
// ============================================================================

describe('useSettingsApi', () => {
  it('should provide both query and mutation', async () => {
    server.use(
      http.get('/api/v1/settings', () => {
        return HttpResponse.json(mockSettingsResponse);
      })
    );

    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createWrapper(),
    });

    // Check query properties
    expect(result.current.isLoading).toBeDefined();
    expect(result.current.settings).toBeUndefined();
    expect(result.current.error).toBeNull();
    expect(result.current.isError).toBe(false);
    expect(result.current.refetch).toBeDefined();

    // Check mutation properties
    expect(result.current.updateMutation).toBeDefined();
    expect(result.current.updateMutation.mutate).toBeDefined();
    expect(result.current.updateMutation.mutateAsync).toBeDefined();
    expect(result.current.updateMutation.isPending).toBe(false);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.settings).toEqual(mockSettingsResponse);
  });

  it('should allow updating settings via combined hook', async () => {
    server.use(
      http.get('/api/v1/settings', () => {
        return HttpResponse.json(mockSettingsResponse);
      }),
      http.patch('/api/v1/settings', () => {
        return HttpResponse.json(updatedSettingsResponse);
      })
    );

    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    await act(async () => {
      await result.current.updateMutation.mutateAsync({
        features: { reid_enabled: false },
      });
    });

    // Wait for mutation to reflect success state
    await waitFor(() => {
      expect(result.current.updateMutation.isSuccess).toBe(true);
    });
  });

  it('should pass options to query', async () => {
    const fetchSpy = vi.fn();
    server.use(
      http.get('/api/v1/settings', () => {
        fetchSpy();
        return HttpResponse.json(mockSettingsResponse);
      })
    );

    renderHook(() => useSettingsApi({ enabled: false }), {
      wrapper: createWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

// ============================================================================
// Partial Update Tests
// ============================================================================

describe('partial updates', () => {
  it('should support updating only detection settings', async () => {
    let receivedBody: SettingsUpdate | null = null;
    server.use(
      http.patch('/api/v1/settings', async ({ request }) => {
        receivedBody = (await request.json()) as SettingsUpdate;
        return HttpResponse.json({
          ...mockSettingsResponse,
          detection: { ...mockSettingsResponse.detection, confidence_threshold: 0.7 },
        });
      })
    );

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        detection: { confidence_threshold: 0.7 },
      });
    });

    // Wait for mutation success
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify request body
    expect(receivedBody).toEqual({ detection: { confidence_threshold: 0.7 } });
    // Verify response
    expect(result.current.data?.detection.confidence_threshold).toBe(0.7);
  });

  it('should support updating only feature toggles', async () => {
    let receivedBody: SettingsUpdate | null = null;
    server.use(
      http.patch('/api/v1/settings', async ({ request }) => {
        receivedBody = (await request.json()) as SettingsUpdate;
        return HttpResponse.json({
          ...mockSettingsResponse,
          features: { ...mockSettingsResponse.features, reid_enabled: false },
        });
      })
    );

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        features: { reid_enabled: false },
      });
    });

    // Wait for mutation success
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify request body
    expect(receivedBody).toEqual({ features: { reid_enabled: false } });
    // Verify response
    expect(result.current.data?.features.reid_enabled).toBe(false);
  });

  it('should support updating multiple categories at once', async () => {
    const multiUpdate: SettingsUpdate = {
      detection: { confidence_threshold: 0.6 },
      features: { reid_enabled: false, scene_change_enabled: false },
      retention: { days: 60 },
    };

    let receivedBody: SettingsUpdate | null = null;
    server.use(
      http.patch('/api/v1/settings', async ({ request }) => {
        receivedBody = (await request.json()) as SettingsUpdate;
        return HttpResponse.json({
          ...mockSettingsResponse,
          detection: { ...mockSettingsResponse.detection, confidence_threshold: 0.6 },
          features: {
            ...mockSettingsResponse.features,
            reid_enabled: false,
            scene_change_enabled: false,
          },
          retention: { ...mockSettingsResponse.retention, days: 60 },
        });
      })
    );

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync(multiUpdate);
    });

    // Wait for mutation success
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify request body
    expect(receivedBody).toEqual(multiUpdate);
    // Verify response
    expect(result.current.data?.detection.confidence_threshold).toBe(0.6);
    expect(result.current.data?.features.reid_enabled).toBe(false);
    expect(result.current.data?.retention.days).toBe(60);
  });
});
