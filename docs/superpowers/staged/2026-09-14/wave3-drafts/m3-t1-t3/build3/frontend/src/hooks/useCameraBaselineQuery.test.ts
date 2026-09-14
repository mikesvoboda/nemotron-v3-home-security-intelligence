/**
 * Tests for useCameraBaselineQuery hooks
 *
 * TDD: Tests written first to define the expected behavior.
 * @see NEM-3576 - Camera Baseline Activity API Integration
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useCameraBaselineQuery,
  useCameraActivityBaselineQuery,
  useCameraClassBaselineQuery,
  cameraBaselineQueryKeys,
} from './useCameraBaselineQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchCameraBaseline: vi.fn(),
  fetchCameraActivityBaseline: vi.fn(),
  fetchCameraClassBaseline: vi.fn(),
}));

describe('useCameraBaselineQuery', () => {
  const mockBaselineSummary: api.BaselineSummaryResponse = {
    camera_id: 'cam-1',
    camera_name: 'Front Door',
    baseline_established: '2026-01-01T00:00:00Z',
    data_points: 720,
    hourly_patterns: {
      '0': { avg_detections: 0.5, std_dev: 0.3, sample_count: 30 },
      '17': { avg_detections: 5.2, std_dev: 1.1, sample_count: 30 },
    },
    daily_patterns: {
      monday: { avg_detections: 45, peak_hour: 17, total_samples: 24 },
    },
    object_baselines: {
      person: { avg_hourly: 2.3, peak_hour: 17, total_detections: 550 },
    },
    current_deviation: {
      score: 1.8,
      interpretation: 'slightly_above_normal',
      contributing_factors: ['person_count_elevated'],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCameraBaseline as ReturnType<typeof vi.fn>).mockResolvedValue(mockBaselineSummary);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchCameraBaseline as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchCameraBaseline as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });
  });

  describe('fetching data', () => {
    it('fetches baseline data on mount', async () => {
      renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchCameraBaseline).toHaveBeenCalledWith('cam-1');
      });
    });

    it('returns baseline data after successful fetch', async () => {
      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockBaselineSummary);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch baseline';
      (api.fetchCameraBaseline as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useCameraBaselineQuery('cam-1', { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraBaseline).not.toHaveBeenCalled();
    });

    it('does not fetch when cameraId is undefined', async () => {
      renderHook(() => useCameraBaselineQuery(undefined), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraBaseline).not.toHaveBeenCalled();
    });
  });

  describe('derived values', () => {
    it('provides hasBaseline as true when data exists', async () => {
      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hasBaseline).toBe(true);
      });
    });

    it('provides hasBaseline as false when no data points', async () => {
      (api.fetchCameraBaseline as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockBaselineSummary,
        data_points: 0,
      });

      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hasBaseline).toBe(false);
      });
    });

    it('provides isLearning based on baseline_established', async () => {
      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        // Has baseline_established so not in learning mode
        expect(result.current.isLearning).toBe(false);
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useCameraBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

describe('useCameraActivityBaselineQuery', () => {
  const mockActivityBaseline: api.ActivityBaselineResponse = {
    camera_id: 'cam-1',
    entries: [
      { hour: 0, day_of_week: 0, avg_count: 0.5, sample_count: 30, is_peak: false },
      { hour: 17, day_of_week: 4, avg_count: 5.2, sample_count: 30, is_peak: true },
    ],
    total_samples: 720,
    peak_hour: 17,
    peak_day: 4,
    learning_complete: true,
    min_samples_required: 10,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCameraActivityBaseline as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockActivityBaseline
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetching data', () => {
    it('fetches activity baseline data on mount', async () => {
      renderHook(() => useCameraActivityBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam-1');
      });
    });

    it('returns activity baseline data after successful fetch', async () => {
      const { result } = renderHook(() => useCameraActivityBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockActivityBaseline);
      });
    });

    it('provides entries array directly', async () => {
      const { result } = renderHook(() => useCameraActivityBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.entries).toEqual(mockActivityBaseline.entries);
      });
    });

    it('provides learningComplete flag', async () => {
      const { result } = renderHook(() => useCameraActivityBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.learningComplete).toBe(true);
      });
    });

    it('provides minSamplesRequired', async () => {
      const { result } = renderHook(() => useCameraActivityBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.minSamplesRequired).toBe(10);
      });
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useCameraActivityBaselineQuery('cam-1', { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraActivityBaseline).not.toHaveBeenCalled();
    });

    it('does not fetch when cameraId is undefined', async () => {
      renderHook(() => useCameraActivityBaselineQuery(undefined), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraActivityBaseline).not.toHaveBeenCalled();
    });
  });
});

describe('useCameraClassBaselineQuery', () => {
  const mockClassBaseline: api.ClassBaselineResponse = {
    camera_id: 'cam-1',
    entries: [
      { object_class: 'person', hour: 17, frequency: 3.5, sample_count: 45 },
      { object_class: 'vehicle', hour: 8, frequency: 2.1, sample_count: 30 },
    ],
    unique_classes: ['person', 'vehicle', 'animal'],
    total_samples: 150,
    most_common_class: 'person',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCameraClassBaseline as ReturnType<typeof vi.fn>).mockResolvedValue(mockClassBaseline);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetching data', () => {
    it('fetches class baseline data on mount', async () => {
      renderHook(() => useCameraClassBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchCameraClassBaseline).toHaveBeenCalledWith('cam-1');
      });
    });

    it('returns class baseline data after successful fetch', async () => {
      const { result } = renderHook(() => useCameraClassBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockClassBaseline);
      });
    });

    it('provides entries array directly', async () => {
      const { result } = renderHook(() => useCameraClassBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.entries).toEqual(mockClassBaseline.entries);
      });
    });

    it('provides uniqueClasses array', async () => {
      const { result } = renderHook(() => useCameraClassBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.uniqueClasses).toEqual(['person', 'vehicle', 'animal']);
      });
    });

    it('provides mostCommonClass', async () => {
      const { result } = renderHook(() => useCameraClassBaselineQuery('cam-1'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.mostCommonClass).toBe('person');
      });
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useCameraClassBaselineQuery('cam-1', { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraClassBaseline).not.toHaveBeenCalled();
    });

    it('does not fetch when cameraId is undefined', async () => {
      renderHook(() => useCameraClassBaselineQuery(undefined), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraClassBaseline).not.toHaveBeenCalled();
    });
  });
});

describe('cameraBaselineQueryKeys', () => {
  it('generates correct summary key', () => {
    expect(cameraBaselineQueryKeys.summary('cam-1')).toEqual([
      'cameras',
      'baseline',
      'summary',
      'cam-1',
    ]);
  });

  it('generates correct activity key', () => {
    expect(cameraBaselineQueryKeys.activity('cam-1')).toEqual([
      'cameras',
      'baseline',
      'activity',
      'cam-1',
    ]);
  });

  it('generates correct classes key', () => {
    expect(cameraBaselineQueryKeys.classes('cam-1')).toEqual([
      'cameras',
      'baseline',
      'classes',
      'cam-1',
    ]);
  });

  it('generates correct all key for invalidation', () => {
    expect(cameraBaselineQueryKeys.all).toEqual(['cameras', 'baseline']);
  });

  it('generates correct byCamera key for invalidation', () => {
    expect(cameraBaselineQueryKeys.byCamera('cam-1')).toEqual(['cameras', 'baseline', 'cam-1']);
  });
});
