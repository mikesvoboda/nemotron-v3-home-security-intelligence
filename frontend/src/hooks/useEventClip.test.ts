import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { useEventClip } from './useEventClip';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    fetchEventClipInfo: vi.fn(),
    generateEventClip: vi.fn(),
    getEventClipUrl: vi.fn((url: string) => `http://localhost${url}`),
  };
});

describe('useEventClip', () => {
  const mockClipAvailable: api.ClipInfoResponse = {
    event_id: 123,
    clip_available: true,
    clip_url: '/api/media/clips/event_123.mp4',
    duration_seconds: 15,
    generated_at: '2024-01-15T10:00:00Z',
    file_size_bytes: 1024000,
  };

  const mockClipUnavailable: api.ClipInfoResponse = {
    event_id: 123,
    clip_available: false,
    clip_url: null,
    duration_seconds: null,
    generated_at: null,
    file_size_bytes: null,
  };

  const mockGenerateSuccess: api.ClipGenerateResponse = {
    event_id: 123,
    status: 'completed',
    clip_url: '/api/media/clips/event_123.mp4',
    generated_at: '2024-01-15T10:00:00Z',
    message: null,
  };

  const mockGenerateFailed: api.ClipGenerateResponse = {
    event_id: 123,
    status: 'failed',
    clip_url: null,
    generated_at: null,
    message: 'Not enough frames to generate clip',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Default to clip unavailable
    vi.mocked(api.fetchEventClipInfo).mockResolvedValue(mockClipUnavailable);
    vi.mocked(api.generateEventClip).mockResolvedValue(mockGenerateSuccess);
  });

  describe('initial state', () => {
    it('returns initial state correctly', () => {
      const { result } = renderHook(() => useEventClip(123));

      expect(result.current.isLoading).toBe(true);
      expect(result.current.clipInfo).toBeNull();
      expect(result.current.isGenerating).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.clipUrl).toBeNull();
    });

    it('does not fetch when autoFetch is false', () => {
      renderHook(() => useEventClip(123, { autoFetch: false }));

      expect(api.fetchEventClipInfo).not.toHaveBeenCalled();
    });

    it('does not fetch when eventId is undefined', () => {
      renderHook(() => useEventClip(undefined));

      expect(api.fetchEventClipInfo).not.toHaveBeenCalled();
    });
  });

  describe('fetching clip info', () => {
    it('fetches clip info on mount when autoFetch is true (default)', async () => {
      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClipInfo).toHaveBeenCalledWith(123);
      expect(result.current.clipInfo).toEqual(mockClipUnavailable);
    });

    it('sets clipUrl when clip is available', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue(mockClipAvailable);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.clipUrl).toBe(
        'http://localhost/api/media/clips/event_123.mp4'
      );
      expect(result.current.isClipAvailable).toBe(true);
    });

    it('handles fetch error', async () => {
      vi.mocked(api.fetchEventClipInfo).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Network error');
      expect(result.current.clipInfo).toBeNull();
    });

    it('refetches when eventId changes', async () => {
      const { result, rerender } = renderHook(
        ({ eventId }) => useEventClip(eventId),
        { initialProps: { eventId: 123 } }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClipInfo).toHaveBeenCalledWith(123);

      rerender({ eventId: 456 });

      await waitFor(() => {
        expect(api.fetchEventClipInfo).toHaveBeenCalledWith(456);
      });
    });
  });

  describe('generating clips', () => {
    it('generates clip successfully', async () => {
      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.generateClip();
      });

      expect(api.generateEventClip).toHaveBeenCalledWith(123, undefined);
      expect(result.current.clipInfo?.clip_available).toBe(true);
      expect(result.current.clipUrl).toBe(
        'http://localhost/api/media/clips/event_123.mp4'
      );
    });

    it('shows generating state during clip generation', async () => {
      let resolveGenerate: (value: api.ClipGenerateResponse) => void;
      const generatePromise = new Promise<api.ClipGenerateResponse>(
        (resolve) => {
          resolveGenerate = resolve;
        }
      );
      vi.mocked(api.generateEventClip).mockReturnValue(generatePromise);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Start generating
      act(() => {
        void result.current.generateClip();
      });

      // Should be in generating state
      expect(result.current.isGenerating).toBe(true);

      // Resolve the promise
      await act(async () => {
        resolveGenerate!(mockGenerateSuccess);
        await Promise.resolve();
      });

      // Should no longer be generating
      await waitFor(() => {
        expect(result.current.isGenerating).toBe(false);
      });
    });

    it('handles generation failure', async () => {
      vi.mocked(api.generateEventClip).mockResolvedValue(mockGenerateFailed);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.generateClip();
      });

      expect(result.current.error).toBe('Not enough frames to generate clip');
      expect(result.current.clipInfo?.clip_available).toBe(false);
    });

    it('handles generation error', async () => {
      vi.mocked(api.generateEventClip).mockRejectedValue(
        new Error('Server error')
      );

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.generateClip();
      });

      expect(result.current.error).toBe('Server error');
    });

    it('supports force regeneration', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue(mockClipAvailable);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.generateClip({ force: true });
      });

      expect(api.generateEventClip).toHaveBeenCalledWith(123, { force: true });
    });
  });

  describe('refetch', () => {
    it('refetches clip info when called', async () => {
      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClipInfo).toHaveBeenCalledTimes(1);

      await act(async () => {
        await result.current.refetch();
      });

      expect(api.fetchEventClipInfo).toHaveBeenCalledTimes(2);
    });
  });

  describe('computed properties', () => {
    it('isClipAvailable returns true when clip is available', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue(mockClipAvailable);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isClipAvailable).toBe(true);
    });

    it('isClipAvailable returns false when clip is not available', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue(mockClipUnavailable);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isClipAvailable).toBe(false);
    });

    it('canGenerateClip returns true when not generating and not available', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue(mockClipUnavailable);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.canGenerateClip).toBe(true);
    });

    it('canGenerateClip returns true when clip is available (for regeneration)', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue(mockClipAvailable);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Can still generate (regenerate) even when clip is available
      expect(result.current.canGenerateClip).toBe(true);
    });

    it('canGenerateClip returns false when generating', async () => {
      let resolveGenerate: (value: api.ClipGenerateResponse) => void;
      const generatePromise = new Promise<api.ClipGenerateResponse>(
        (resolve) => {
          resolveGenerate = resolve;
        }
      );
      vi.mocked(api.generateEventClip).mockReturnValue(generatePromise);

      const { result } = renderHook(() => useEventClip(123));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      act(() => {
        void result.current.generateClip();
      });

      expect(result.current.canGenerateClip).toBe(false);

      // Clean up
      await act(async () => {
        resolveGenerate!(mockGenerateSuccess);
        await Promise.resolve();
      });
    });
  });
});
