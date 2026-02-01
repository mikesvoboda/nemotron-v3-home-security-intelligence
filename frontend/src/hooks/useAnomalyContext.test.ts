/**
 * Tests for useAnomalyContext hook (NEM-4714)
 *
 * Tests the anomaly investigation context hook including:
 * - Initial state (no anomaly ID)
 * - Successful fetch
 * - Error handling
 * - Enabled/disabled state
 * - Acknowledge mutation
 * - Cache updates after acknowledgment
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import { useAnomalyContext } from './useAnomalyContext';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { AnomalyContext } from './useAnomalyContext';

// Save original fetch for restoration
const originalFetch = globalThis.fetch;

// Mock fetch globally
const mockFetch = vi.fn();

beforeAll(() => {
  globalThis.fetch = mockFetch as typeof fetch;
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

describe('useAnomalyContext', () => {
  // Helper to create mock anomaly context data
  const createMockAnomalyContext = (overrides: Partial<AnomalyContext> = {}): AnomalyContext => ({
    id: 'anomaly-123',
    zone_id: 1,
    zone_name: 'Front Yard',
    anomaly_type: 'high_activity',
    severity: 'warning',
    timestamp: '2024-01-15T14:30:00Z',
    expected_value: 5.0,
    actual_value: 15.0,
    explanation: 'Detected unusually high activity compared to baseline',
    detections: [
      {
        id: 'detection-1',
        camera_id: 'cam-123',
        timestamp: '2024-01-15T14:30:00Z',
        object_class: 'person',
        confidence: 0.95,
        risk_score: 65,
        thumbnail_url: '/thumbnails/detection-1.jpg',
      },
      {
        id: 'detection-2',
        camera_id: 'cam-123',
        timestamp: '2024-01-15T14:31:00Z',
        object_class: 'person',
        confidence: 0.88,
        risk_score: 60,
        thumbnail_url: '/thumbnails/detection-2.jpg',
      },
    ],
    acknowledged: false,
    acknowledged_at: null,
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with undefined data when no anomaly ID provided', () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolving

      const { result } = renderHook(() => useAnomalyContext(null), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
      expect(result.current.isLoading).toBe(false);
    });

    it('starts with isLoading true when fetching with valid anomaly ID', () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolving

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
    });

    it('starts with isLoading false when enabled is false', () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolving

      const { result } = renderHook(
        () => useAnomalyContext('anomaly-123', { enabled: false }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('fetching data', () => {
    it('fetches anomaly context for a specific anomaly ID', async () => {
      const mockContext = createMockAnomalyContext();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockContext),
      });

      renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/zones/anomalies/anomaly-123/context')
        );
      });
    });

    it('updates data after successful fetch', async () => {
      const mockContext = createMockAnomalyContext({
        id: 'anomaly-123',
        zone_name: 'Back Yard',
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockContext),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockContext);
      });

      expect(result.current.data?.zone_name).toBe('Back Yard');
    });

    it('sets isLoading false after fetch completes', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('returns associated detections', async () => {
      const mockContext = createMockAnomalyContext({
        detections: [
          {
            id: 'det-1',
            camera_id: 'cam-1',
            timestamp: '2024-01-15T14:30:00Z',
            object_class: 'person',
            confidence: 0.95,
            risk_score: 75,
            thumbnail_url: '/thumb-1.jpg',
          },
        ],
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockContext),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.detections).toHaveLength(1);
      });

      expect(result.current.data?.detections[0].id).toBe('det-1');
    });

    it('sets error on fetch failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Not Found',
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );

      expect(result.current.isError).toBe(true);
    });

    it('includes error message in error object', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );

      expect(result.current.error?.message).toContain('Failed to fetch anomaly context');
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useAnomalyContext('anomaly-123', { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('does not fetch when anomaly ID is null', async () => {
      renderHook(() => useAnomalyContext(null, { enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('does not fetch when anomaly ID is null and enabled is false', async () => {
      renderHook(() => useAnomalyContext(null, { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('fetches when enabled is true and anomaly ID is provided', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      renderHook(() => useAnomalyContext('anomaly-123', { enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/zones/anomalies/anomaly-123/context')
        );
      });
    });
  });

  describe('refetch function', () => {
    it('provides refetch function', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('can manually refetch data', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Clear call count and refetch
      mockFetch.mockClear();
      void result.current.refetch();

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });
    });
  });

  describe('acknowledge mutation', () => {
    it('provides acknowledgeAnomaly function', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockAnomalyContext()),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.acknowledgeAnomaly).toBe('function');
    });

    it('calls acknowledge endpoint when acknowledgeAnomaly is invoked', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext()),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              acknowledged: true,
              acknowledged_at: '2024-01-15T15:00:00Z',
            }),
        });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.acknowledgeAnomaly();

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/zones/anomalies/anomaly-123/acknowledge'),
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          })
        );
      });
    });

    it('sets isAcknowledging to true during mutation', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext()),
        })
        .mockReturnValueOnce(new Promise(() => {})); // Never resolving

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.acknowledgeAnomaly();

      await waitFor(() => {
        expect(result.current.isAcknowledging).toBe(true);
      });
    });

    it('updates cache with acknowledged status after successful acknowledgment', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext({ acknowledged: false })),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              acknowledged: true,
              acknowledged_at: '2024-01-15T15:00:00Z',
            }),
        });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.acknowledged).toBe(false);
      });

      result.current.acknowledgeAnomaly();

      await waitFor(() => {
        expect(result.current.data?.acknowledged).toBe(true);
      });

      expect(result.current.data?.acknowledged_at).toBe('2024-01-15T15:00:00Z');
    });

    it('sets isAcknowledging to false after mutation completes', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext()),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              acknowledged: true,
              acknowledged_at: '2024-01-15T15:00:00Z',
            }),
        });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.acknowledgeAnomaly();

      await waitFor(() => {
        expect(result.current.isAcknowledging).toBe(false);
      });
    });

    it('sets acknowledgeError on mutation failure', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(createMockAnomalyContext()),
        })
        .mockResolvedValueOnce({
          ok: false,
          statusText: 'Server Error',
        });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.acknowledgeAnomaly();

      await waitFor(() => {
        expect(result.current.acknowledgeError).toBeInstanceOf(Error);
      });
    });
  });

  describe('acknowledged anomalies', () => {
    it('returns acknowledged status when anomaly is already acknowledged', async () => {
      const mockContext = createMockAnomalyContext({
        acknowledged: true,
        acknowledged_at: '2024-01-15T15:00:00Z',
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockContext),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.acknowledged).toBe(true);
      });

      expect(result.current.data?.acknowledged_at).toBe('2024-01-15T15:00:00Z');
    });
  });

  describe('anomaly types and severity', () => {
    it('returns high_activity anomaly type', async () => {
      const mockContext = createMockAnomalyContext({
        anomaly_type: 'high_activity',
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockContext),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.anomaly_type).toBe('high_activity');
      });
    });

    it('returns critical severity level', async () => {
      const mockContext = createMockAnomalyContext({
        severity: 'critical',
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockContext),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.severity).toBe('critical');
      });
    });
  });

  describe('value comparison', () => {
    it('returns expected and actual values', async () => {
      const mockContext = createMockAnomalyContext({
        expected_value: 5.0,
        actual_value: 15.0,
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockContext),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.expected_value).toBe(5.0);
      });

      expect(result.current.data?.actual_value).toBe(15.0);
    });

    it('handles null expected value', async () => {
      const mockContext = createMockAnomalyContext({
        expected_value: null,
        actual_value: 10.0,
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockContext),
      });

      const { result } = renderHook(() => useAnomalyContext('anomaly-123'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.expected_value).toBeNull();
      });

      expect(result.current.data?.actual_value).toBe(10.0);
    });
  });
});
