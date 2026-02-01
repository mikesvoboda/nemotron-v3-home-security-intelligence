/**
 * Tests for usePresets Hook (NEM-4885)
 *
 * Comprehensive tests for PTZ preset management using TanStack Query.
 * Tests cover fetching presets, navigating to presets, cache invalidation,
 * and conditional query enabling.
 *
 * @see frontend/src/hooks/usePresets.ts
 */

import { QueryClient } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach, vi } from 'vitest';

import { server } from '../../mocks/server';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';
import { usePresets } from '../usePresets';

import type { PTZPresetsResponse, PTZGotoPresetResponse } from '../../types/ptz';

// Base URL for camera API
const BASE_URL = '/api/cameras';
const TEST_CAMERA_ID = 'camera-1';

// ============================================================================
// Mock Data
// ============================================================================

const mockPresetsResponse: PTZPresetsResponse = {
  presets: [
    { token: 'preset_1', name: 'Front Door' },
    { token: 'preset_2', name: 'Backyard' },
    { token: 'preset_3', name: 'Driveway' },
  ],
};

const mockEmptyPresetsResponse: PTZPresetsResponse = {
  presets: [],
};

const mockGotoPresetResponse: PTZGotoPresetResponse = {
  success: true,
  message: 'Moved to preset',
};

const mockErrorResponse = {
  detail: 'Failed to get presets',
};

// ============================================================================
// Tests - Fetching Presets
// ============================================================================

describe('usePresets - fetching presets', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });
  });

  it('fetches presets on mount', async () => {
    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        return HttpResponse.json(mockPresetsResponse);
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.presets).toBeUndefined();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.presets).toEqual(mockPresetsResponse);
    expect(result.current.presets?.presets).toHaveLength(3);
    expect(result.current.isError).toBe(false);
  });

  it('handles empty presets list', async () => {
    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        return HttpResponse.json(mockEmptyPresetsResponse);
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.presets?.presets).toEqual([]);
  });

  it('handles fetch error', async () => {
    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        return HttpResponse.json(mockErrorResponse, { status: 500 });
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.presets).toBeUndefined();
    expect(result.current.error?.message).toContain('Failed to get presets');
  });

  it('caches presets with 30 second stale time', async () => {
    let fetchCount = 0;

    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        fetchCount++;
        return HttpResponse.json(mockPresetsResponse);
      })
    );

    const { result, rerender } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(fetchCount).toBe(1);

    // Rerender should use cached data
    rerender();

    await waitFor(() => {
      expect(result.current.presets).toBeDefined();
    });

    // Should not refetch while still fresh
    expect(fetchCount).toBe(1);
  });

  it('does not fetch when enabled is false', async () => {
    let fetchCalled = false;

    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        fetchCalled = true;
        return HttpResponse.json(mockPresetsResponse);
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID, false), {
      wrapper: createQueryWrapper(queryClient),
    });

    // Wait a bit to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(fetchCalled).toBe(false);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.presets).toBeUndefined();
  });

  it('does not fetch when cameraId is empty', async () => {
    let fetchCalled = false;

    server.use(
      http.get(`${BASE_URL}//onvif/presets`, () => {
        fetchCalled = true;
        return HttpResponse.json(mockPresetsResponse);
      })
    );

    const { result } = renderHook(() => usePresets(''), {
      wrapper: createQueryWrapper(queryClient),
    });

    // Wait a bit to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(fetchCalled).toBe(false);
    expect(result.current.presets).toBeUndefined();
  });

  it('starts fetching when enabled changes to true', async () => {
    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        return HttpResponse.json(mockPresetsResponse);
      })
    );

    const { result, rerender } = renderHook(
      ({ enabled }) => usePresets(TEST_CAMERA_ID, enabled),
      {
        wrapper: createQueryWrapper(queryClient),
        initialProps: { enabled: false },
      }
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.presets).toBeUndefined();

    // Enable the query
    rerender({ enabled: true });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.presets).toEqual(mockPresetsResponse);
  });
});

// ============================================================================
// Tests - Goto Preset
// ============================================================================

describe('usePresets - gotoPreset', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        return HttpResponse.json(mockPresetsResponse);
      })
    );
  });

  it('calls API with preset token', async () => {
    let capturedToken: string | null = null;

    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets/:token`, ({ params }) => {
        capturedToken = params.token as string;
        return HttpResponse.json(mockGotoPresetResponse);
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.presets).toBeDefined();
    });

    await act(async () => {
      await result.current.gotoPreset.mutateAsync('preset_1');
    });

    expect(capturedToken).toBe('preset_1');

    await waitFor(() => {
      expect(result.current.gotoPreset.isSuccess).toBe(true);
    });
  });

  it('handles goto preset error', async () => {
    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets/:token`, () => {
        return HttpResponse.json({ detail: 'Preset not found' }, { status: 404 });
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.presets).toBeDefined();
    });

    await act(async () => {
      try {
        await result.current.gotoPreset.mutateAsync('invalid_preset');
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    await waitFor(() => {
      expect(result.current.gotoPreset.isError).toBe(true);
    });
    expect(result.current.gotoPreset.error?.message).toContain('Preset not found');
  });

  it('tracks pending state during goto preset', async () => {
    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets/:token`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json(mockGotoPresetResponse);
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.presets).toBeDefined();
    });

    let mutationPromise: Promise<PTZGotoPresetResponse>;
    act(() => {
      mutationPromise = result.current.gotoPreset.mutateAsync('preset_1');
    });

    await waitFor(() => {
      expect(result.current.gotoPreset.isPending).toBe(true);
    });

    await act(async () => {
      await mutationPromise;
    });

    await waitFor(() => {
      expect(result.current.gotoPreset.isPending).toBe(false);
    });
  });

  it('can navigate to multiple presets sequentially', async () => {
    const visitedTokens: string[] = [];

    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets/:token`, ({ params }) => {
        visitedTokens.push(params.token as string);
        return HttpResponse.json(mockGotoPresetResponse);
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.presets).toBeDefined();
    });

    await act(async () => {
      await result.current.gotoPreset.mutateAsync('preset_1');
      await result.current.gotoPreset.mutateAsync('preset_2');
      await result.current.gotoPreset.mutateAsync('preset_3');
    });

    expect(visitedTokens).toEqual(['preset_1', 'preset_2', 'preset_3']);
  });
});

// ============================================================================
// Tests - refetchPresets
// ============================================================================

describe('usePresets - refetchPresets', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });
  });

  it('invalidates cache and refetches presets', async () => {
    let fetchCount = 0;

    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        fetchCount++;
        return HttpResponse.json(mockPresetsResponse);
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    // Wait for initial fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(fetchCount).toBe(1);

    // Trigger refetch
    act(() => {
      result.current.refetchPresets();
    });

    // Wait for refetch to complete
    await waitFor(() => {
      expect(fetchCount).toBe(2);
    });
  });

  it('uses invalidateQueries with correct query key', async () => {
    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        return HttpResponse.json(mockPresetsResponse);
      })
    );

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.presets).toBeDefined();
    });

    act(() => {
      result.current.refetchPresets();
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['ptzPresets', TEST_CAMERA_ID],
    });
  });

  it('updates presets data after refetch', async () => {
    let presetsData = mockPresetsResponse;

    server.use(
      http.get(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/presets`, () => {
        return HttpResponse.json(presetsData);
      })
    );

    const { result } = renderHook(() => usePresets(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.presets?.presets).toHaveLength(3);
    });

    // Update mock data
    presetsData = {
      presets: [
        ...mockPresetsResponse.presets,
        { token: 'preset_4', name: 'Garage' },
      ],
    };

    // Trigger refetch
    act(() => {
      result.current.refetchPresets();
    });

    // Wait for updated data
    await waitFor(() => {
      expect(result.current.presets?.presets).toHaveLength(4);
    });

    expect(result.current.presets?.presets[3]).toEqual({
      token: 'preset_4',
      name: 'Garage',
    });
  });
});

// ============================================================================
// Tests - Multiple Cameras
// ============================================================================

describe('usePresets - multiple cameras', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });
  });

  it('fetches presets for correct camera', async () => {
    const camera1Id = 'camera-1';
    const camera2Id = 'camera-2';

    const camera1Presets: PTZPresetsResponse = {
      presets: [{ token: 'c1_preset_1', name: 'Camera 1 Preset' }],
    };

    const camera2Presets: PTZPresetsResponse = {
      presets: [{ token: 'c2_preset_1', name: 'Camera 2 Preset' }],
    };

    server.use(
      http.get(`${BASE_URL}/${camera1Id}/onvif/presets`, () => {
        return HttpResponse.json(camera1Presets);
      }),
      http.get(`${BASE_URL}/${camera2Id}/onvif/presets`, () => {
        return HttpResponse.json(camera2Presets);
      })
    );

    const { result: result1 } = renderHook(() => usePresets(camera1Id), {
      wrapper: createQueryWrapper(queryClient),
    });

    const { result: result2 } = renderHook(() => usePresets(camera2Id), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result1.current.presets).toBeDefined();
      expect(result2.current.presets).toBeDefined();
    });

    expect(result1.current.presets).toEqual(camera1Presets);
    expect(result2.current.presets).toEqual(camera2Presets);
  });

  it('maintains separate cache for each camera', async () => {
    const camera1Id = 'camera-1';
    const camera2Id = 'camera-2';

    server.use(
      http.get(`${BASE_URL}/${camera1Id}/onvif/presets`, () => {
        return HttpResponse.json({ presets: [{ token: 'c1', name: 'C1' }] });
      }),
      http.get(`${BASE_URL}/${camera2Id}/onvif/presets`, () => {
        return HttpResponse.json({ presets: [{ token: 'c2', name: 'C2' }] });
      })
    );

    const { result: result1 } = renderHook(() => usePresets(camera1Id), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result1.current.presets).toBeDefined();
    });

    // Fetch camera 2 presets
    const { result: result2 } = renderHook(() => usePresets(camera2Id), {
      wrapper: createQueryWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result2.current.presets).toBeDefined();
    });

    // Both should maintain their own data
    expect(result1.current.presets?.presets[0].token).toBe('c1');
    expect(result2.current.presets?.presets[0].token).toBe('c2');
  });
});
