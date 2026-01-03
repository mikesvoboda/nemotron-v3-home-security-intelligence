import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useDetectionEnrichment } from './useDetectionEnrichment';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchDetectionEnrichment: vi.fn(),
}));

describe('useDetectionEnrichment', () => {
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
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('initial state', () => {
    it('returns loading state initially', () => {
      vi.mocked(api.fetchDetectionEnrichment).mockReturnValue(
        new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useDetectionEnrichment(123));

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeNull();
    });

    it('does not fetch when detectionId is undefined', () => {
      const { result } = renderHook(() => useDetectionEnrichment(undefined));

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeNull();
      expect(api.fetchDetectionEnrichment).not.toHaveBeenCalled();
    });

    it('does not fetch when detectionId is null', () => {
      const { result } = renderHook(() => useDetectionEnrichment(null));

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeNull();
      expect(api.fetchDetectionEnrichment).not.toHaveBeenCalled();
    });
  });

  describe('successful fetch', () => {
    it('fetches enrichment data for valid detectionId', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchDetectionEnrichment).toHaveBeenCalledWith(123);
      expect(result.current.data).toEqual(mockEnrichmentData);
      expect(result.current.error).toBeNull();
    });

    it('returns enrichment data with license plate', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123));

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.license_plate?.detected).toBe(true);
      expect(result.current.data?.license_plate?.text).toBe('ABC-1234');
      expect(result.current.data?.license_plate?.confidence).toBe(0.87);
    });

    it('returns enrichment data with face detection', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123));

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.face?.detected).toBe(true);
      expect(result.current.data?.face?.count).toBe(1);
      expect(result.current.data?.face?.confidence).toBe(0.88);
    });

    it('returns enrichment data with clothing analysis', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123));

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.clothing?.upper).toBe('red t-shirt');
      expect(result.current.data?.clothing?.lower).toBe('blue jeans');
      expect(result.current.data?.clothing?.is_suspicious).toBe(false);
    });

    it('returns enrichment data with vehicle classification', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123));

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.data?.vehicle?.type).toBe('sedan');
      expect(result.current.data?.vehicle?.color).toBe('blue');
      expect(result.current.data?.vehicle?.confidence).toBe(0.92);
    });

    it('returns enrichment data with image quality assessment', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123));

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
      vi.mocked(api.fetchDetectionEnrichment).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useDetectionEnrichment(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeNull();
      expect(result.current.error).toBe(errorMessage);
    });

    it('handles network error', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useDetectionEnrichment(456));

      await waitFor(() => {
        expect(result.current.error).toBe('Network error');
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeNull();
    });
  });

  describe('refetch on detectionId change', () => {
    it('refetches when detectionId changes', async () => {
      const firstEnrichment = { ...mockEnrichmentData, detection_id: 100 };
      const secondEnrichment = { ...mockEnrichmentData, detection_id: 200 };

      vi.mocked(api.fetchDetectionEnrichment)
        .mockResolvedValueOnce(firstEnrichment)
        .mockResolvedValueOnce(secondEnrichment);

      const { result, rerender } = renderHook(
        ({ detectionId }) => useDetectionEnrichment(detectionId),
        { initialProps: { detectionId: 100 as number | null | undefined } }
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

    it('clears data when detectionId becomes null', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result, rerender } = renderHook(
        ({ detectionId }) => useDetectionEnrichment(detectionId),
        { initialProps: { detectionId: 123 as number | null | undefined } }
      );

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      rerender({ detectionId: null });

      expect(result.current.data).toBeNull();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  describe('refetch function', () => {
    it('provides refetch function to manually trigger fetch', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123));

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(result.current.refetch).toBeDefined();
      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123));

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

      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(emptyEnrichment);

      const { result } = renderHook(() => useDetectionEnrichment(123));

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
    it('does not fetch when enabled is false', () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result } = renderHook(() => useDetectionEnrichment(123, { enabled: false }));

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeNull();
      expect(api.fetchDetectionEnrichment).not.toHaveBeenCalled();
    });

    it('fetches when enabled becomes true', async () => {
      vi.mocked(api.fetchDetectionEnrichment).mockResolvedValue(mockEnrichmentData);

      const { result, rerender } = renderHook(
        ({ enabled }) => useDetectionEnrichment(123, { enabled }),
        { initialProps: { enabled: false } }
      );

      expect(api.fetchDetectionEnrichment).not.toHaveBeenCalled();

      rerender({ enabled: true });

      await waitFor(() => {
        expect(result.current.data).not.toBeNull();
      });

      expect(api.fetchDetectionEnrichment).toHaveBeenCalledWith(123);
    });
  });
});
