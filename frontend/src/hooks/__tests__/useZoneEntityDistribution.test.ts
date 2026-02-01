/**
 * Tests for useZoneEntityDistribution hooks (NEM-4937)
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { createQueryWrapper } from '../../test-utils';
import {
  useZoneEntityDistribution,
  useAllZonesEntityDistribution,
  getEntityTypeColor,
  getEntityTypeLabel,
} from '../useZoneEntityDistribution';

import type { ZoneEntityDistribution, ZoneEntityDistributionResponse } from '../useZoneEntityDistribution';

// ============================================================================
// Test Data
// ============================================================================

const mockZoneDistribution: ZoneEntityDistribution = {
  zone_id: 1,
  zone_name: 'Front Yard',
  total_entities: 64,
  entity_types: [
    { entity_type: 'person', count: 42, percentage: 65.63 },
    { entity_type: 'vehicle', count: 15, percentage: 23.44 },
    { entity_type: 'dog', count: 7, percentage: 10.94 },
  ],
};

const mockAllZonesResponse: ZoneEntityDistributionResponse = {
  zones: [
    mockZoneDistribution,
    {
      zone_id: 2,
      zone_name: 'Back Yard',
      total_entities: 32,
      entity_types: [
        { entity_type: 'person', count: 20, percentage: 62.5 },
        { entity_type: 'cat', count: 12, percentage: 37.5 },
      ],
    },
  ],
  grand_total: 96,
  start_time: '2026-01-31T00:00:00Z',
  end_time: '2026-01-31T23:59:59Z',
};

// ============================================================================
// Mocks
// ============================================================================

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch);
  mockFetch.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ============================================================================
// useZoneEntityDistribution Tests
// ============================================================================

describe('useZoneEntityDistribution', () => {
  it('should fetch entity distribution for a zone', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockZoneDistribution),
    });

    const { result } = renderHook(() => useZoneEntityDistribution({ zoneId: 1 }), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.distribution).toEqual(mockZoneDistribution);
    expect(result.current.error).toBeNull();
    expect(mockFetch).toHaveBeenCalledWith('/api/analytics-zones/polygon-zones/1/entity-distribution');
  });

  it('should not fetch when disabled', () => {
    renderHook(() => useZoneEntityDistribution({ zoneId: 1, enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('should not fetch when zoneId is undefined', () => {
    renderHook(() => useZoneEntityDistribution({ zoneId: undefined }), {
      wrapper: createQueryWrapper(),
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('should handle fetch error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      statusText: 'Not Found',
    });

    const { result } = renderHook(() => useZoneEntityDistribution({ zoneId: 999 }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });

    expect(result.current.error?.message).toContain('Failed to fetch entity distribution');
  });
});

// ============================================================================
// useAllZonesEntityDistribution Tests
// ============================================================================

describe('useAllZonesEntityDistribution', () => {
  it('should fetch entity distribution for all zones', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockAllZonesResponse),
    });

    const { result } = renderHook(() => useAllZonesEntityDistribution(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockAllZonesResponse);
    expect(result.current.error).toBeNull();
    expect(mockFetch).toHaveBeenCalledWith('/api/analytics-zones/entity-distribution');
  });

  it('should filter by camera ID', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockAllZonesResponse),
    });

    const { result } = renderHook(
      () => useAllZonesEntityDistribution({ cameraId: 'front_door' }),
      { wrapper: createQueryWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/analytics-zones/entity-distribution?camera_id=front_door'
    );
  });

  it('should not fetch when disabled', () => {
    renderHook(() => useAllZonesEntityDistribution({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });
});

// ============================================================================
// Utility Function Tests
// ============================================================================

describe('getEntityTypeColor', () => {
  it('should return correct color for known entity types', () => {
    expect(getEntityTypeColor('person')).toBe('#3B82F6');
    expect(getEntityTypeColor('vehicle')).toBe('#10B981');
    expect(getEntityTypeColor('dog')).toBe('#F59E0B');
    expect(getEntityTypeColor('cat')).toBe('#F97316');
  });

  it('should return fallback color for unknown entity types', () => {
    expect(getEntityTypeColor('unknown_entity')).toBe('#6B7280');
  });

  it('should be case-insensitive', () => {
    expect(getEntityTypeColor('PERSON')).toBe('#3B82F6');
    expect(getEntityTypeColor('Person')).toBe('#3B82F6');
  });
});

describe('getEntityTypeLabel', () => {
  it('should return correct label for known entity types', () => {
    expect(getEntityTypeLabel('person')).toBe('Person');
    expect(getEntityTypeLabel('vehicle')).toBe('Vehicle');
    expect(getEntityTypeLabel('dog')).toBe('Dog');
  });

  it('should capitalize unknown entity types', () => {
    expect(getEntityTypeLabel('alien')).toBe('Alien');
    expect(getEntityTypeLabel('robot')).toBe('Robot');
  });

  it('should be case-insensitive', () => {
    expect(getEntityTypeLabel('PERSON')).toBe('Person');
    expect(getEntityTypeLabel('DOG')).toBe('Dog');
  });
});
