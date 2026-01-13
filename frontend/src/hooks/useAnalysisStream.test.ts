/**
 * Tests for useAnalysisStream hook (NEM-2488).
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useAnalysisStream } from './useAnalysisStream';
import * as api from '../services/api';

// Mock the api module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    createAnalysisStream: vi.fn(),
  };
});

// Mock logger to avoid console output in tests
vi.mock('../services/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

describe('useAnalysisStream', () => {
  let mockEventSource: {
    onopen: ((event: Event) => void) | null;
    onmessage: ((event: MessageEvent) => void) | null;
    onerror: ((event: Event) => void) | null;
    close: ReturnType<typeof vi.fn>;
    readyState: number;
  };

  beforeEach(() => {
    // Reset all mocks
    vi.clearAllMocks();

    // Create a mock EventSource instance
    mockEventSource = {
      onopen: null,
      onmessage: null,
      onerror: null,
      close: vi.fn(),
      readyState: 0,
    };

    // Mock createAnalysisStream to return our mock EventSource
    vi.mocked(api.createAnalysisStream).mockReturnValue(
      mockEventSource as unknown as EventSource
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('returns idle status initially', () => {
      const { result } = renderHook(() => useAnalysisStream());

      expect(result.current.status).toBe('idle');
      expect(result.current.accumulatedText).toBe('');
      expect(result.current.result).toBeNull();
      expect(result.current.error).toBeNull();
      expect(result.current.isStreaming).toBe(false);
    });
  });

  describe('startStream', () => {
    it('creates EventSource and sets status to connecting', () => {
      const { result } = renderHook(() => useAnalysisStream());

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      expect(api.createAnalysisStream).toHaveBeenCalledWith({ batchId: 'batch-123' });
      expect(result.current.status).toBe('connecting');
      expect(result.current.isStreaming).toBe(true);
    });

    it('sets status to connected when EventSource opens', async () => {
      const { result } = renderHook(() => useAnalysisStream());

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      // Simulate EventSource open
      act(() => {
        mockEventSource.onopen?.(new Event('open'));
      });

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });
    });

    it('closes existing connection before starting new one', () => {
      const { result } = renderHook(() => useAnalysisStream());

      // Start first stream
      act(() => {
        result.current.startStream({ batchId: 'batch-1' });
      });

      const firstEventSource = mockEventSource;

      // Create new mock for second stream
      const secondMockEventSource = {
        onopen: null,
        onmessage: null,
        onerror: null,
        close: vi.fn(),
        readyState: 0,
      };
      vi.mocked(api.createAnalysisStream).mockReturnValue(
        secondMockEventSource as unknown as EventSource
      );

      // Start second stream
      act(() => {
        result.current.startStream({ batchId: 'batch-2' });
      });

      expect(firstEventSource.close).toHaveBeenCalled();
    });
  });

  describe('progress events', () => {
    it('updates accumulatedText on progress event', async () => {
      const onProgress = vi.fn();
      const { result } = renderHook(() => useAnalysisStream({ onProgress }));

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      // Simulate progress event
      act(() => {
        const progressEvent = new MessageEvent('message', {
          data: JSON.stringify({
            event_type: 'progress',
            batch_id: 'batch-123',
            accumulated_text: 'Analyzing the scene...',
          }),
        });
        mockEventSource.onmessage?.(progressEvent);
      });

      await waitFor(() => {
        expect(result.current.accumulatedText).toBe('Analyzing the scene...');
      });
      expect(onProgress).toHaveBeenCalledWith('Analyzing the scene...');
    });

    it('updates accumulatedText with subsequent progress events', async () => {
      const { result } = renderHook(() => useAnalysisStream());

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      // First progress event
      act(() => {
        const event1 = new MessageEvent('message', {
          data: JSON.stringify({
            event_type: 'progress',
            batch_id: 'batch-123',
            accumulated_text: 'Analyzing...',
          }),
        });
        mockEventSource.onmessage?.(event1);
      });

      // Second progress event (accumulated)
      act(() => {
        const event2 = new MessageEvent('message', {
          data: JSON.stringify({
            event_type: 'progress',
            batch_id: 'batch-123',
            accumulated_text: 'Analyzing... Person detected near entrance.',
          }),
        });
        mockEventSource.onmessage?.(event2);
      });

      await waitFor(() => {
        expect(result.current.accumulatedText).toBe(
          'Analyzing... Person detected near entrance.'
        );
      });
    });
  });

  describe('complete events', () => {
    it('updates result and status on complete event', async () => {
      const onComplete = vi.fn();
      const { result } = renderHook(() => useAnalysisStream({ onComplete }));

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      // Simulate complete event
      act(() => {
        const completeEvent = new MessageEvent('message', {
          data: JSON.stringify({
            event_type: 'complete',
            batch_id: 'batch-123',
            event_id: 456,
            risk_score: 75,
            risk_level: 'high',
            summary: 'Person detected near front entrance',
          }),
        });
        mockEventSource.onmessage?.(completeEvent);
      });

      await waitFor(() => {
        expect(result.current.status).toBe('complete');
        expect(result.current.result).toEqual({
          eventId: 456,
          riskScore: 75,
          riskLevel: 'high',
          summary: 'Person detected near front entrance',
        });
        expect(result.current.isStreaming).toBe(false);
      });

      expect(onComplete).toHaveBeenCalledWith({
        eventId: 456,
        riskScore: 75,
        riskLevel: 'high',
        summary: 'Person detected near front entrance',
      });
      expect(mockEventSource.close).toHaveBeenCalled();
    });
  });

  describe('error events', () => {
    it('updates error and status on error event', async () => {
      const onError = vi.fn();
      const { result } = renderHook(() => useAnalysisStream({ onError }));

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      // Simulate error event from server
      act(() => {
        const errorEvent = new MessageEvent('message', {
          data: JSON.stringify({
            event_type: 'error',
            batch_id: 'batch-123',
            error_code: 'BATCH_NOT_FOUND',
            error_message: 'Batch not found in Redis',
            recoverable: false,
          }),
        });
        mockEventSource.onmessage?.(errorEvent);
      });

      await waitFor(() => {
        expect(result.current.status).toBe('error');
        expect(result.current.error).toEqual({
          code: 'BATCH_NOT_FOUND',
          message: 'Batch not found in Redis',
          recoverable: false,
        });
        expect(result.current.isStreaming).toBe(false);
      });

      expect(onError).toHaveBeenCalledWith({
        code: 'BATCH_NOT_FOUND',
        message: 'Batch not found in Redis',
        recoverable: false,
      });
      expect(mockEventSource.close).toHaveBeenCalled();
    });

    it('handles connection error', async () => {
      const onError = vi.fn();
      const { result } = renderHook(() => useAnalysisStream({ onError }));

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      // Simulate EventSource connection error
      act(() => {
        mockEventSource.onerror?.(new Event('error'));
      });

      await waitFor(() => {
        expect(result.current.status).toBe('error');
        expect(result.current.error).toEqual({
          code: 'CONNECTION_ERROR',
          message: 'Lost connection to analysis stream',
          recoverable: true,
        });
      });

      expect(onError).toHaveBeenCalled();
      expect(mockEventSource.close).toHaveBeenCalled();
    });
  });

  describe('stopStream', () => {
    it('closes EventSource and resets to idle', () => {
      const { result } = renderHook(() => useAnalysisStream());

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      act(() => {
        result.current.stopStream();
      });

      expect(mockEventSource.close).toHaveBeenCalled();
      expect(result.current.status).toBe('idle');
      expect(result.current.isStreaming).toBe(false);
    });
  });

  describe('cleanup on unmount', () => {
    it('closes EventSource on unmount', () => {
      const { result, unmount } = renderHook(() => useAnalysisStream());

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      unmount();

      expect(mockEventSource.close).toHaveBeenCalled();
    });
  });

  describe('invalid JSON handling', () => {
    it('handles malformed JSON in message', () => {
      const { result } = renderHook(() => useAnalysisStream());

      act(() => {
        result.current.startStream({ batchId: 'batch-123' });
      });

      // Simulate malformed JSON message
      act(() => {
        const badEvent = new MessageEvent('message', {
          data: 'not valid json',
        });
        mockEventSource.onmessage?.(badEvent);
      });

      // Should not crash and status should remain connected/connecting
      expect(result.current.status).not.toBe('error');
    });
  });
});
