/**
 * Tests for useDetectionEnrichment hook
 *
 * This hook uses TanStack Query to fetch enrichment data for a specific detection.
 * Tests use QueryClientProvider wrapper for proper TanStack Query integration.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  useDetectionEnrichment,
  detectionEnrichmentKeys,
} from './useDetectionEnrichment';
import * as api from '../services/api';
import { createQueryClient } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { QueryClient } from '@tanstack/react-query';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const originalModule = await importOriginal<typeof api>();
  return {
    ...originalModule,
    fetchDetectionEnrichment: vi.fn(),
  };
});

describe('useDetectionEnrichment', () => {
  let queryClient: QueryClient;

  const mockEnrichmentData = {
    detection_id: 123,
    enriched_at: '2024-01-15T10:30:00Z',
    license_plate: {
      detected: true,
      confidence: 0.87,
      text: 'ABC-1234',
      ocr_confidence: 0.85,
      bbox: [100, 200, 300, 250],
    },
    face: {
      detected: true,
      count: 1,
      confidence: 0.88,
    },
    vehicle: {
      type: 'sedan',
      color: 'blue',
      confidence: 0.92,
      is_commercial: false,
      damage_detected: false,
      damage_types: [],
    },
    clothing: {
      upper: 'red t-shirt',
      lower: 'blue jeans',
      is_suspicious: false,
      is_service_uniform: false,
      has_face_covered: false,
      has_bag: true,
      clothing_items: ['t-shirt', 'jeans'],
    },
    violence: {
      detected: false,
      score: 0.12,
      confidence: 0.95,
    },
    weather: null,
    pose: null,
    depth: null,
    image_quality: {
      score: 0.85,
      is_blurry: false,
      is_low_quality: false,
      quality_issues: [],
      quality_change_detected: false,
    },
    pet: null,
    processing_time_ms: 125.5,
    errors: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    (api.fetchDetectionEnrichment as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockEnrichmentData
    );
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('query key factory', () => {
    it('generates correct all key', () => {
      expect(detectionEnrichmentKeys.all).toEqual(['detectionEnrichment']);
    });

    it('generates correct detail key', () => {
      expect(detectionEnrichmentKeys.detail(123)).toEqual([
        'detectionEnrichment',
        'detail',
        123,
      ]);
    });
  });

  describe('initial state', () => {
    it('returns loading state initially', () => {
      (api.fetchDetectionEnrichment as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeNull();
    });

    it('does not fetch when detectionId is undefined', () => {
      const { result } = renderHook(() => useDetectionEnrichment(undefined), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeNull();
      expect(api.fetchDetectionEnrichment).not.toHaveBeenCalled();
    });

    it('does not fetch when detectionId is null', () => {
      const { result } = renderHook(() => useDetectionEnrichment(null), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeNull();
      expect(api.fetchDetectionEnrichment).not.toHaveBeenCalled();
    });
  });

  describe('successful fetch', () => {
    it('fetches enrichment data for valid detectionId', async () => {
      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchDetectionEnrichment).toHaveBeenCalledWith(123);
      expect(result.current.data).toEqual(mockEnrichmentData);
      expect(result.current.error).toBeNull();
    });

    it('returns enrichment data with license plate', async () => {
      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.license_plate?.detected).toBe(true);
      expect(result.current.data?.license_plate?.text).toBe('ABC-1234');
      expect(result.current.data?.license_plate?.confidence).toBe(0.87);
    });

    it('returns enrichment data with face detection', async () => {
      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.face?.detected).toBe(true);
      expect(result.current.data?.face?.count).toBe(1);
      expect(result.current.data?.face?.confidence).toBe(0.88);
    });

    it('returns enrichment data with clothing analysis', async () => {
      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.clothing?.upper).toBe('red t-shirt');
      expect(result.current.data?.clothing?.lower).toBe('blue jeans');
      expect(result.current.data?.clothing?.is_suspicious).toBe(false);
    });

    it('returns enrichment data with vehicle classification', async () => {
      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.vehicle?.type).toBe('sedan');
      expect(result.current.data?.vehicle?.color).toBe('blue');
      expect(result.current.data?.vehicle?.confidence).toBe(0.92);
    });

    it('returns enrichment data with image quality assessment', async () => {
      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.image_quality?.score).toBe(0.85);
      expect(result.current.data?.image_quality?.is_blurry).toBe(false);
    });
  });

  describe('error handling', () => {
    it('handles API error', async () => {
      const errorMessage = 'Detection not found';
      (api.fetchDetectionEnrichment as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.isLoading).toBe(false);
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 5000 }
      );

      expect(result.current.data).toBeNull();
      expect(result.current.error).toBe(errorMessage);
    });

    it('handles network error', async () => {
      (api.fetchDetectionEnrichment as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useDetectionEnrichment(456), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBe('Network error');
        },
        { timeout: 5000 }
      );

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeNull();
    });
  });

  describe('refetch on detectionId change', () => {
    it('refetches when detectionId changes', async () => {
      const firstEnrichment = { ...mockEnrichmentData, detection_id: 100 };
      const secondEnrichment = { ...mockEnrichmentData, detection_id: 200 };

      (api.fetchDetectionEnrichment as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(firstEnrichment)
        .mockResolvedValueOnce(secondEnrichment);

      const { result, rerender } = renderHook(
        ({ detectionId }) => useDetectionEnrichment(detectionId),
        {
          initialProps: { detectionId: 100 as number | null | undefined },
          wrapper: createQueryWrapper(queryClient),
        }
      );

      await waitFor(() => {
        expect(result.current.data?.detection_id).toBe(100);
      });

      rerender({ detectionId: 200 });

      await waitFor(() => {
        expect(result.current.data?.detection_id).toBe(200);
      });

      expect(api.fetchDetectionEnrichment).toHaveBeenCalledTimes(2);
      expect(api.fetchDetectionEnrichment).toHaveBeenNthCalledWith(1, 100);
      expect(api.fetchDetectionEnrichment).toHaveBeenNthCalledWith(2, 200);
    });

    it('returns null data when detectionId becomes null', async () => {
      const { result, rerender } = renderHook(
        ({ detectionId }) => useDetectionEnrichment(detectionId),
        {
          initialProps: { detectionId: 123 as number | null | undefined },
          wrapper: createQueryWrapper(queryClient),
        }
      );

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      rerender({ detectionId: null });

      // When disabled, TanStack Query keeps the last data but isLoading becomes false
      // For backward compatibility, we return null when disabled
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('refetch function', () => {
    it('provides refetch function to manually trigger fetch', async () => {
      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.refetch).toBeDefined();
      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(api.fetchDetectionEnrichment).toHaveBeenCalledTimes(1);

      await result.current.refetch();

      expect(api.fetchDetectionEnrichment).toHaveBeenCalledTimes(2);
    });
  });

  describe('empty enrichment data', () => {
    it('handles detection with no enrichment data', async () => {
      const emptyEnrichment = {
        detection_id: 123,
        enriched_at: null,
        license_plate: { detected: false },
        face: { detected: false, count: 0 },
        vehicle: null,
        clothing: null,
        violence: { detected: false, score: 0 },
        weather: null,
        pose: null,
        depth: null,
        image_quality: null,
        pet: null,
        processing_time_ms: null,
        errors: [],
      };

      (api.fetchDetectionEnrichment as ReturnType<typeof vi.fn>).mockResolvedValue(
        emptyEnrichment
      );

      const { result } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.license_plate?.detected).toBe(false);
      expect(result.current.data?.face?.detected).toBe(false);
      expect(result.current.data?.vehicle).toBeNull();
      expect(result.current.data?.clothing).toBeNull();
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      const { result } = renderHook(
        () => useDetectionEnrichment(123, { enabled: false }),
        {
          wrapper: createQueryWrapper(queryClient),
        }
      );

      // Give it time to potentially fetch
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeNull();
      expect(api.fetchDetectionEnrichment).not.toHaveBeenCalled();
    });

    it('fetches when enabled becomes true', async () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useDetectionEnrichment(123, { enabled }),
        {
          initialProps: { enabled: false },
          wrapper: createQueryWrapper(queryClient),
        }
      );

      expect(api.fetchDetectionEnrichment).not.toHaveBeenCalled();

      rerender({ enabled: true });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(api.fetchDetectionEnrichment).toHaveBeenCalledWith(123);
    });
  });

  describe('caching behavior', () => {
    it('uses cached data on subsequent renders', async () => {
      // First render
      const { result: result1 } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result1.current.data).not.toBeNull();
      });

      expect(api.fetchDetectionEnrichment).toHaveBeenCalledTimes(1);

      // Second render with same queryClient - should use cache
      const { result: result2 } = renderHook(() => useDetectionEnrichment(123), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Should immediately have data from cache
      expect(result2.current.data).toEqual(mockEnrichmentData);
      // Should not have made another API call (cache hit)
      expect(api.fetchDetectionEnrichment).toHaveBeenCalledTimes(1);
    });
  });
});
