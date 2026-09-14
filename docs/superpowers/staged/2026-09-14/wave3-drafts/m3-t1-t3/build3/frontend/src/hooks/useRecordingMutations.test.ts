import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRecordingMutations } from './useRecordingMutations';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { ReplayResponse } from '../services/api';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    replayRecording: vi.fn(),
    deleteRecording: vi.fn(),
    clearAllRecordings: vi.fn(),
  };
});

describe('useRecordingMutations', () => {
  // Mock replay response
  const mockReplayResponse: ReplayResponse = {
    recording_id: 'rec-001',
    original_status_code: 200,
    replay_status_code: 200,
    replay_response: { data: 'test' },
    replay_metadata: {
      original_timestamp: '2025-01-17T10:00:00Z',
      original_path: '/api/events',
      original_method: 'GET',
      replay_duration_ms: 45.5,
      replayed_at: '2025-01-17T11:00:00Z',
    },
    timestamp: '2025-01-17T11:00:00Z',
  };

  const mockDeleteResponse = { message: "Recording 'rec-001' deleted successfully" };

  const mockClearAllResponse = { message: 'Deleted 5 recordings', deleted_count: 5 };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.replayRecording as ReturnType<typeof vi.fn>).mockResolvedValue(mockReplayResponse);
    (api.deleteRecording as ReturnType<typeof vi.fn>).mockResolvedValue(mockDeleteResponse);
    (api.clearAllRecordings as ReturnType<typeof vi.fn>).mockResolvedValue(mockClearAllResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('replayMutation', () => {
    it('provides replay mutation function', () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      expect(typeof result.current.replayMutation.mutate).toBe('function');
    });

    it('calls replayRecording API with correct recording ID', async () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.replayMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(api.replayRecording).toHaveBeenCalledWith('rec-001');
      });
    });

    it('returns replay response data on success', async () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.replayMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(result.current.replayMutation.data).toEqual(mockReplayResponse);
      });
    });

    it('sets isReplaying to true during mutation', async () => {
      let resolvePromise: (value: ReplayResponse) => void;
      (api.replayRecording as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- mock returns Promise
        (): Promise<ReplayResponse> =>
          new Promise<ReplayResponse>((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.replayMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(result.current.isReplaying).toBe(true);
      });

      act(() => {
        resolvePromise(mockReplayResponse);
      });

      await waitFor(() => {
        expect(result.current.isReplaying).toBe(false);
      });
    });

    it('sets error on replay failure', async () => {
      const error = new Error('Replay failed');
      (api.replayRecording as ReturnType<typeof vi.fn>).mockRejectedValue(error);

      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.replayMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(result.current.replayMutation.error).toEqual(error);
      });
    });
  });

  describe('deleteMutation', () => {
    it('provides delete mutation function', () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      expect(typeof result.current.deleteMutation.mutate).toBe('function');
    });

    it('calls deleteRecording API with correct recording ID', async () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.deleteMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(api.deleteRecording).toHaveBeenCalledWith('rec-001');
      });
    });

    it('returns delete response message on success', async () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.deleteMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(result.current.deleteMutation.data).toEqual(mockDeleteResponse);
      });
    });

    it('sets isDeleting to true during mutation', async () => {
      let resolvePromise: (value: { message: string }) => void;
      (api.deleteRecording as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- mock returns Promise
        (): Promise<{ message: string }> =>
          new Promise<{ message: string }>((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.deleteMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(result.current.isDeleting).toBe(true);
      });

      act(() => {
        resolvePromise(mockDeleteResponse);
      });

      await waitFor(() => {
        expect(result.current.isDeleting).toBe(false);
      });
    });
  });

  describe('clearAllMutation', () => {
    it('provides clear all mutation function', () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      expect(typeof result.current.clearAllMutation.mutate).toBe('function');
    });

    it('calls clearAllRecordings API', async () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.clearAllMutation.mutate();
      });

      await waitFor(() => {
        expect(api.clearAllRecordings).toHaveBeenCalled();
      });
    });

    it('returns clear all response on success', async () => {
      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.clearAllMutation.mutate();
      });

      await waitFor(() => {
        expect(result.current.clearAllMutation.data).toEqual(mockClearAllResponse);
      });
    });

    it('sets isClearing to true during mutation', async () => {
      let resolvePromise: (value: { message: string; deleted_count: number }) => void;
      (api.clearAllRecordings as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- mock returns Promise
        (): Promise<{ message: string; deleted_count: number }> =>
          new Promise<{ message: string; deleted_count: number }>((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.clearAllMutation.mutate();
      });

      await waitFor(() => {
        expect(result.current.isClearing).toBe(true);
      });

      act(() => {
        resolvePromise(mockClearAllResponse);
      });

      await waitFor(() => {
        expect(result.current.isClearing).toBe(false);
      });
    });
  });

  describe('combined loading state', () => {
    it('isAnyMutating is true when replaying', async () => {
      let resolvePromise: (value: ReplayResponse) => void;
      (api.replayRecording as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- mock returns Promise
        (): Promise<ReplayResponse> =>
          new Promise<ReplayResponse>((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.replayMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(result.current.isAnyMutating).toBe(true);
      });

      act(() => {
        resolvePromise(mockReplayResponse);
      });

      await waitFor(() => {
        expect(result.current.isAnyMutating).toBe(false);
      });
    });

    it('isAnyMutating is true when deleting', async () => {
      let resolvePromise: (value: { message: string }) => void;
      (api.deleteRecording as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- mock returns Promise
        (): Promise<{ message: string }> =>
          new Promise<{ message: string }>((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.deleteMutation.mutate('rec-001');
      });

      await waitFor(() => {
        expect(result.current.isAnyMutating).toBe(true);
      });

      act(() => {
        resolvePromise(mockDeleteResponse);
      });

      await waitFor(() => {
        expect(result.current.isAnyMutating).toBe(false);
      });
    });

    it('isAnyMutating is true when clearing all', async () => {
      let resolvePromise: (value: { message: string; deleted_count: number }) => void;
      (api.clearAllRecordings as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- mock returns Promise
        (): Promise<{ message: string; deleted_count: number }> =>
          new Promise<{ message: string; deleted_count: number }>((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useRecordingMutations(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        result.current.clearAllMutation.mutate();
      });

      await waitFor(() => {
        expect(result.current.isAnyMutating).toBe(true);
      });

      act(() => {
        resolvePromise(mockClearAllResponse);
      });

      await waitFor(() => {
        expect(result.current.isAnyMutating).toBe(false);
      });
    });
  });
});
