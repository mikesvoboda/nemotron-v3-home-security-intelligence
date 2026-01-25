/**
 * Tests for useEventEnrichmentsQuery hook (NEM-3596)
 *
 * Verifies the hook correctly fetches batch enrichment data
 * for an event using the optimized /api/events/{event_id}/enrichments endpoint.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { createQueryWrapper } from '../test-utils/renderWithProviders';
import { useEventEnrichmentsQuery } from './useEventEnrichmentsQuery';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchEventEnrichments: vi.fn(),
}));

describe('useEventEnrichmentsQuery', () => {
  // Mock response that matches EventEnrichmentsResponse type from generated types
  const mockEnrichmentsResponse = {
    event_id: 123,
    count: 2,
    total: 10,
    limit: 50,
    offset: 0,
    has_more: false,
    enrichments: [
      {
        detection_id: 1,
        enriched_at: '2026-01-03T10:30:00Z',
        face: { detected: false, count: 0 },
        license_plate: { detected: false },
        vehicle: null,
        clothing: { upper: 'jacket', lower: 'jeans' },
      },
      {
        detection_id: 2,
        enriched_at: '2026-01-03T10:31:00Z',
        face: { detected: true, count: 1, age: 35 },
        license_plate: { detected: false },
        vehicle: null,
        clothing: null,
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchEventEnrichments).mockResolvedValue(mockEnrichmentsResponse);
  });

  it('fetches enrichments for a valid event ID', async () => {
    const { result } = renderHook(() => useEventEnrichmentsQuery({ eventId: 123 }), {
      wrapper: createQueryWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have fetched the data
    expect(api.fetchEventEnrichments).toHaveBeenCalledWith(123, undefined);
    expect(result.current.enrichments).toHaveLength(2);
    expect(result.current.data).toEqual(mockEnrichmentsResponse);
  });

  it('returns empty enrichments array when loading', () => {
    const { result } = renderHook(() => useEventEnrichmentsQuery({ eventId: 123 }), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.enrichments).toEqual([]);
    expect(result.current.isLoading).toBe(true);
  });

  it('does not fetch when eventId is NaN', () => {
    const { result } = renderHook(() => useEventEnrichmentsQuery({ eventId: NaN }), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(api.fetchEventEnrichments).not.toHaveBeenCalled();
  });

  it('does not fetch when enabled is false', () => {
    const { result } = renderHook(
      () => useEventEnrichmentsQuery({ eventId: 123, enabled: false }),
      { wrapper: createQueryWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(api.fetchEventEnrichments).not.toHaveBeenCalled();
  });

  it('handles API errors gracefully', async () => {
    vi.mocked(api.fetchEventEnrichments).mockRejectedValue(new Error('API Error'));

    const { result } = renderHook(() => useEventEnrichmentsQuery({ eventId: 123 }), {
      wrapper: createQueryWrapper(),
    });

    // Wait for error state - need to wait longer due to query retries
    await waitFor(
      () => {
        expect(result.current.isError).toBe(true);
      },
      { timeout: 10000 }
    );

    expect(result.current.error?.message).toBe('API Error');
    expect(result.current.enrichments).toEqual([]);
  });

  it('passes pagination params when provided', async () => {
    const { result } = renderHook(
      () => useEventEnrichmentsQuery({ eventId: 123, limit: 10, offset: 5 }),
      { wrapper: createQueryWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.fetchEventEnrichments).toHaveBeenCalledWith(123, { limit: 10, offset: 5 });
  });

  it('provides enrichment lookup by detection ID', async () => {
    const { result } = renderHook(() => useEventEnrichmentsQuery({ eventId: 123 }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Test the getEnrichmentByDetectionId helper
    const enrichment = result.current.getEnrichmentByDetectionId(1);
    expect(enrichment?.detection_id).toBe(1);
    expect(enrichment?.clothing?.upper).toBe('jacket');

    // Returns undefined for non-existent detection
    expect(result.current.getEnrichmentByDetectionId(999)).toBeUndefined();
  });

  it('creates a detection ID to enrichment map', async () => {
    const { result } = renderHook(() => useEventEnrichmentsQuery({ eventId: 123 }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.enrichmentMap.size).toBe(2);
    expect(result.current.enrichmentMap.get(1)?.detection_id).toBe(1);
    expect(result.current.enrichmentMap.get(2)?.detection_id).toBe(2);
  });
});
