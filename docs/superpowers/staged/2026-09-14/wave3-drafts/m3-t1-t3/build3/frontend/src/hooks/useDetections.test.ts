import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useDetectionsListQuery,
  useDetectionDetailQuery,
  useDetectionSearchQuery,
  useDetectionLabelsQuery,
} from './useDetections';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchDetections: vi.fn(),
  fetchDetection: vi.fn(),
  searchDetections: vi.fn(),
  fetchDetectionLabels: vi.fn(),
}));

describe('useDetectionsListQuery', () => {
  const mockDetections = {
    items: [
      {
        id: 1,
        event_id: 100,
        camera_id: 'cam-1',
        object_type: 'person',
        confidence: 0.95,
        detected_at: '2025-12-28T10:00:00Z',
        file_path: '/path/to/image.jpg',
        bbox_x1: 0,
        bbox_y1: 0,
        bbox_x2: 100,
        bbox_y2: 100,
      },
      {
        id: 2,
        event_id: 100,
        camera_id: 'cam-1',
        object_type: 'car',
        confidence: 0.88,
        detected_at: '2025-12-28T10:01:00Z',
        file_path: '/path/to/image2.jpg',
        bbox_x1: 50,
        bbox_y1: 50,
        bbox_x2: 150,
        bbox_y2: 150,
      },
    ],
    pagination: {
      total: 2,
      limit: 50,
      offset: 0,
      has_more: false,
      next_cursor: null,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchDetections as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetections);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchDetections as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDetectionsListQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty detections array', () => {
      (api.fetchDetections as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDetectionsListQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.detections).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches detections on mount', async () => {
      renderHook(() => useDetectionsListQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchDetections).toHaveBeenCalledTimes(1);
      });
    });

    it('updates detections after successful fetch', async () => {
      const { result } = renderHook(() => useDetectionsListQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.detections).toEqual(mockDetections.items);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useDetectionsListQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch detections';
      (api.fetchDetections as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useDetectionsListQuery(), {
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

  describe('filtering', () => {
    it('passes filter parameters to API', async () => {
      const filters = {
        camera_id: 'cam-1',
        object_type: 'person',
        min_confidence: 0.9,
      };

      renderHook(
        () =>
          useDetectionsListQuery({
            filters,
            limit: 20,
          }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(api.fetchDetections).toHaveBeenCalledWith(
          expect.objectContaining({
            camera_id: 'cam-1',
            object_type: 'person',
            min_confidence: 0.9,
            limit: 20,
          })
        );
      });
    });
  });

  describe('pagination', () => {
    it('returns hasMore from pagination', async () => {
      const paginatedResponse = {
        ...mockDetections,
        pagination: {
          ...mockDetections.pagination,
          has_more: true,
          next_cursor: 'next-cursor-123',
        },
      };
      (api.fetchDetections as ReturnType<typeof vi.fn>).mockResolvedValue(paginatedResponse);

      const { result } = renderHook(() => useDetectionsListQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hasMore).toBe(true);
        expect(result.current.nextCursor).toBe('next-cursor-123');
      });
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useDetectionsListQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchDetections).not.toHaveBeenCalled();
    });
  });
});

describe('useDetectionDetailQuery', () => {
  const mockDetection = {
    id: 1,
    event_id: 100,
    camera_id: 'cam-1',
    object_type: 'person',
    confidence: 0.95,
    detected_at: '2025-12-28T10:00:00Z',
    file_path: '/path/to/image.jpg',
    bbox_x1: 0,
    bbox_y1: 0,
    bbox_x2: 100,
    bbox_y2: 100,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchDetection as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetection);
  });

  it('fetches single detection by ID', async () => {
    renderHook(() => useDetectionDetailQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(api.fetchDetection).toHaveBeenCalledWith(1);
    });
  });

  it('returns detection data', async () => {
    const { result } = renderHook(() => useDetectionDetailQuery(1), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockDetection);
    });
  });

  it('does not fetch when id is undefined', async () => {
    renderHook(() => useDetectionDetailQuery(undefined), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(api.fetchDetection).not.toHaveBeenCalled();
  });
});

describe('useDetectionSearchQuery', () => {
  const mockSearchResults = {
    results: [
      {
        id: 1,
        camera_id: 'cam-1',
        object_type: 'person',
        confidence: 0.95,
        detected_at: '2025-12-28T10:00:00Z',
        file_path: '/path/to/image.jpg',
        thumbnail_path: '/path/to/thumb.jpg',
        relevance_score: 0.98,
        labels: ['suspicious'],
        bbox_x1: 0,
        bbox_y1: 0,
        bbox_x2: 100,
        bbox_y2: 100,
      },
    ],
    total_count: 1,
    limit: 50,
    offset: 0,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.searchDetections as ReturnType<typeof vi.fn>).mockResolvedValue(mockSearchResults);
  });

  it('searches detections with query', async () => {
    renderHook(
      () =>
        useDetectionSearchQuery({
          params: { query: 'suspicious person' },
        }),
      {
        wrapper: createQueryWrapper(),
      }
    );

    await waitFor(() => {
      expect(api.searchDetections).toHaveBeenCalledWith(
        expect.objectContaining({
          query: 'suspicious person',
        })
      );
    });
  });

  it('returns search results', async () => {
    const { result } = renderHook(
      () =>
        useDetectionSearchQuery({
          params: { query: 'suspicious person' },
        }),
      {
        wrapper: createQueryWrapper(),
      }
    );

    await waitFor(() => {
      expect(result.current.results).toEqual(mockSearchResults.results);
      expect(result.current.totalCount).toBe(1);
    });
  });

  it('does not search when query is empty', async () => {
    renderHook(
      () =>
        useDetectionSearchQuery({
          params: { query: '' },
        }),
      {
        wrapper: createQueryWrapper(),
      }
    );

    await new Promise((r) => setTimeout(r, 100));
    expect(api.searchDetections).not.toHaveBeenCalled();
  });

  it('passes additional filters to API', async () => {
    renderHook(
      () =>
        useDetectionSearchQuery({
          params: {
            query: 'person',
            camera_id: 'cam-1',
            labels: ['suspicious'],
            min_confidence: 0.9,
          },
          limit: 20,
          offset: 10,
        }),
      {
        wrapper: createQueryWrapper(),
      }
    );

    await waitFor(() => {
      expect(api.searchDetections).toHaveBeenCalledWith(
        expect.objectContaining({
          query: 'person',
          camera_id: 'cam-1',
          labels: ['suspicious'],
          min_confidence: 0.9,
          limit: 20,
          offset: 10,
        })
      );
    });
  });
});

describe('useDetectionLabelsQuery', () => {
  const mockLabels = {
    labels: [
      { label: 'person', count: 150 },
      { label: 'car', count: 75 },
      { label: 'suspicious', count: 10 },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockResolvedValue(mockLabels);
  });

  it('fetches detection labels', async () => {
    renderHook(() => useDetectionLabelsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(api.fetchDetectionLabels).toHaveBeenCalledTimes(1);
    });
  });

  it('returns labels with counts', async () => {
    const { result } = renderHook(() => useDetectionLabelsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.labels).toEqual(mockLabels.labels);
    });
  });

  it('does not fetch when disabled', async () => {
    renderHook(() => useDetectionLabelsQuery({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(api.fetchDetectionLabels).not.toHaveBeenCalled();
  });
});
