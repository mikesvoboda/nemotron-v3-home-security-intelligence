import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRecordingsQuery, RECORDINGS_QUERY_KEY } from './useRecordingsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { RecordingsListResponse, RecordingResponse } from '../services/api';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchRecordings: vi.fn(),
  };
});

describe('useRecordingsQuery', () => {
  // Mock recording data
  const mockRecording1: RecordingResponse = {
    recording_id: 'rec-001',
    timestamp: '2025-01-17T10:00:00Z',
    method: 'GET',
    path: '/api/events',
    status_code: 200,
    duration_ms: 45.5,
    body_truncated: false,
  };

  const mockRecording2: RecordingResponse = {
    recording_id: 'rec-002',
    timestamp: '2025-01-17T10:01:00Z',
    method: 'POST',
    path: '/api/cameras',
    status_code: 201,
    duration_ms: 120.3,
    body_truncated: false,
  };

  const mockRecording3: RecordingResponse = {
    recording_id: 'rec-003',
    timestamp: '2025-01-17T10:02:00Z',
    method: 'DELETE',
    path: '/api/events/123',
    status_code: 404,
    duration_ms: 15.2,
    body_truncated: false,
  };

  const mockEmptyResponse: RecordingsListResponse = {
    recordings: [],
    total: 0,
    timestamp: '2025-01-17T10:00:00Z',
  };

  const mockRecordingsResponse: RecordingsListResponse = {
    recordings: [mockRecording1, mockRecording2, mockRecording3],
    total: 3,
    timestamp: '2025-01-17T10:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchRecordings as ReturnType<typeof vi.fn>).mockResolvedValue(mockRecordingsResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with empty recordings array', () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      expect(result.current.recordings).toEqual([]);
    });
  });

  describe('fetching recordings', () => {
    it('fetches recordings on mount', async () => {
      renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchRecordings).toHaveBeenCalledTimes(1);
      });
    });

    it('returns recordings data after fetch', async () => {
      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockRecordingsResponse);
      });
    });

    it('returns recordings array from data', async () => {
      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(result.current.recordings).toEqual(mockRecordingsResponse.recordings);
        expect(result.current.recordings.length).toBe(3);
      });
    });

    it('returns total count', async () => {
      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(result.current.totalCount).toBe(3);
      });
    });

    it('sets isLoading to false after fetch', async () => {
      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('empty state', () => {
    it('handles empty recordings list', async () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockResolvedValue(mockEmptyResponse);

      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(result.current.recordings).toEqual([]);
        expect(result.current.totalCount).toBe(0);
      });
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch recordings';
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });

    it('sets isError to true on failure', async () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Failed'));

      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('options', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useRecordingsQuery({ enabled: false }), { wrapper: createQueryWrapper() });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchRecordings).not.toHaveBeenCalled();
    });

    it('provides refetch function', async () => {
      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('respects custom limit option', async () => {
      renderHook(() => useRecordingsQuery({ limit: 50 }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchRecordings).toHaveBeenCalledWith(50);
      });
    });
  });

  describe('query key', () => {
    it('exports correct query key', () => {
      expect(RECORDINGS_QUERY_KEY).toEqual(['debug', 'recordings']);
    });
  });

  describe('derived values', () => {
    it('returns isEmpty true when no recordings', async () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockResolvedValue(mockEmptyResponse);

      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(result.current.isEmpty).toBe(true);
      });
    });

    it('returns isEmpty false when recordings exist', async () => {
      const { result } = renderHook(() => useRecordingsQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(result.current.isEmpty).toBe(false);
      });
    });
  });
});
