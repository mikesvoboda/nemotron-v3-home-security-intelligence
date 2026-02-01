/**
 * Tests for useApproachVectors hook (NEM-4936)
 *
 * @module hooks/__tests__/useApproachVectors.test
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import React from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import {
  useZoneApproachVectors,
  useCameraApproachVectors,
  getUrgencyColor,
  getUrgencyLabel,
  formatETA,
  type ZoneApproachVectorsResponse,
  type CameraApproachVectorsResponse,
} from '../useApproachVectors';

// ============================================================================
// Test Data
// ============================================================================

const mockZoneResponse: ZoneApproachVectorsResponse = {
  zone_id: 1,
  zone_name: 'Front Door',
  approach_vectors: [
    {
      track_id: 42,
      object_class: 'person',
      is_approaching: true,
      direction_degrees: 45.0,
      speed_normalized: 0.05,
      distance_to_zone: 0.15,
      estimated_arrival_seconds: 3.0,
      urgency: 'imminent',
      current_position: { x: 0.35, y: 0.4 },
      zone_centroid: { x: 0.5, y: 0.5 },
    },
    {
      track_id: 43,
      object_class: 'vehicle',
      is_approaching: true,
      direction_degrees: 90.0,
      speed_normalized: 0.02,
      distance_to_zone: 0.25,
      estimated_arrival_seconds: 12.5,
      urgency: 'distant',
      current_position: { x: 0.25, y: 0.5 },
      zone_centroid: { x: 0.5, y: 0.5 },
    },
  ],
  total_approaching: 2,
  imminent_count: 1,
  timestamp: '2026-01-31T12:00:00Z',
};

const mockCameraResponse: CameraApproachVectorsResponse = {
  camera_id: 'front_door',
  zones: [mockZoneResponse],
  total_zones: 1,
  total_approaching_entities: 2,
};

// ============================================================================
// MSW Server Setup
// ============================================================================

const server = setupServer(
  http.get('/api/analytics-zones/polygon-zones/:zoneId/approach-vectors', () => {
    return HttpResponse.json(mockZoneResponse);
  }),
  http.get('/api/analytics-zones/approach-vectors/camera/:cameraId', () => {
    return HttpResponse.json(mockCameraResponse);
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ============================================================================
// Test Utilities
// ============================================================================

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// ============================================================================
// Hook Tests
// ============================================================================

describe('useZoneApproachVectors', () => {
  it('should fetch approach vectors for a zone', async () => {
    const { result } = renderHook(
      () => useZoneApproachVectors({ zoneId: 1 }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toBeDefined();
    expect(result.current.data?.zone_id).toBe(1);
    expect(result.current.data?.approach_vectors).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it('should not fetch when disabled', () => {
    const { result } = renderHook(
      () => useZoneApproachVectors({ zoneId: 1, enabled: false }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('should not fetch when zoneId is undefined', () => {
    const { result } = renderHook(
      () => useZoneApproachVectors({ zoneId: undefined }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('should handle API errors', async () => {
    server.use(
      http.get('/api/analytics-zones/polygon-zones/:zoneId/approach-vectors', () => {
        return new HttpResponse(null, { status: 500 });
      })
    );

    const { result } = renderHook(
      () => useZoneApproachVectors({ zoneId: 1 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).not.toBeNull();
  });
});

describe('useCameraApproachVectors', () => {
  it('should fetch approach vectors for all zones on a camera', async () => {
    const { result } = renderHook(
      () => useCameraApproachVectors({ cameraId: 'front_door' }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toBeDefined();
    expect(result.current.data?.camera_id).toBe('front_door');
    expect(result.current.data?.zones).toHaveLength(1);
    expect(result.current.data?.total_approaching_entities).toBe(2);
    expect(result.current.error).toBeNull();
  });

  it('should not fetch when disabled', () => {
    const { result } = renderHook(
      () => useCameraApproachVectors({ cameraId: 'front_door', enabled: false }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('should not fetch when cameraId is empty', () => {
    const { result } = renderHook(
      () => useCameraApproachVectors({ cameraId: '' }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
  });
});

// ============================================================================
// Utility Function Tests
// ============================================================================

describe('getUrgencyColor', () => {
  it('should return red for imminent urgency', () => {
    expect(getUrgencyColor('imminent')).toBe('#EF4444');
  });

  it('should return amber for approaching urgency', () => {
    expect(getUrgencyColor('approaching')).toBe('#F59E0B');
  });

  it('should return green for distant urgency', () => {
    expect(getUrgencyColor('distant')).toBe('#22C55E');
  });

  it('should return gray for not_approaching', () => {
    expect(getUrgencyColor('not_approaching')).toBe('#6B7280');
  });
});

describe('getUrgencyLabel', () => {
  it('should return readable labels for each urgency', () => {
    expect(getUrgencyLabel('imminent')).toBe('Imminent');
    expect(getUrgencyLabel('approaching')).toBe('Approaching');
    expect(getUrgencyLabel('distant')).toBe('Distant');
    expect(getUrgencyLabel('not_approaching')).toBe('Not Approaching');
  });
});

describe('formatETA', () => {
  it('should format null as --', () => {
    expect(formatETA(null)).toBe('--');
  });

  it('should format 0 as Now', () => {
    expect(formatETA(0)).toBe('Now');
  });

  it('should format small values as <1s', () => {
    expect(formatETA(0.5)).toBe('<1s');
  });

  it('should format seconds correctly', () => {
    expect(formatETA(5)).toBe('5s');
    expect(formatETA(5.4)).toBe('5s');
    expect(formatETA(5.6)).toBe('6s');
  });
});
