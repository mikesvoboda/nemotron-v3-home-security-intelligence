/**
 * Tests for useZoneAnomalies hook (NEM-3199)
 *
 * This module tests the zone anomaly fetching and mutation hooks:
 * - Fetching anomalies for a specific zone
 * - Fetching all anomalies
 * - Filtering by severity, acknowledged status, and time
 * - Acknowledging anomalies with optimistic updates
 * - WebSocket real-time updates
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll, type Mock } from 'vitest';

import { useZoneAnomalies, zoneAnomalyQueryKeys } from './useZoneAnomalies';
import { createQueryClient } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';
import { AnomalySeverity, AnomalyType } from '../types/zoneAnomaly';

import type { ZoneAnomaly, ZoneAnomalyListResponse } from '../types/zoneAnomaly';

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

// Mock useWebSocketEvents
vi.mock('./useWebSocketEvent', () => ({
  useWebSocketEvents: vi.fn(() => ({
    isConnected: true,
    reconnectCount: 0,
    hasExhaustedRetries: false,
    lastHeartbeat: null,
    reconnect: vi.fn(),
  })),
}));

// Mock useToast
vi.mock('./useToast', () => ({
  useToast: () => ({
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  }),
}));

describe('useZoneAnomalies', () => {
  // Helper to create mock anomaly data
  const createMockAnomaly = (overrides: Partial<ZoneAnomaly> = {}): ZoneAnomaly => ({
    id: `anomaly-${Math.random().toString(36).slice(2, 9)}`,
    zone_id: 'zone-123',
    camera_id: 'cam-123',
    anomaly_type: AnomalyType.UNUSUAL_TIME,
    severity: AnomalySeverity.WARNING,
    title: 'Unusual activity detected',
    description: 'Activity detected at an unusual hour',
    expected_value: 0.1,
    actual_value: 1.0,
    deviation: 3.5,
    detection_id: 12345,
    thumbnail_url: '/thumbnails/test.jpg',
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  });

  // Helper to create mock list response
  const createMockListResponse = (
    anomalies: ZoneAnomaly[],
    pagination?: Partial<ZoneAnomalyListResponse['pagination']>
  ): ZoneAnomalyListResponse => ({
    items: anomalies,
    pagination: {
      total: anomalies.length,
      limit: 50,
      offset: 0,
      has_more: false,
      ...pagination,
    },
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when fetching', () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolving

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.anomalies).toEqual([]);
    });

    it('starts with empty anomalies array', () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.anomalies).toEqual([]);
      expect(result.current.totalCount).toBe(0);
    });

    it('returns isConnected status from WebSocket', () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useZoneAnomalies({ zoneId: 'zone-123', enableRealtime: true }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('fetching data', () => {
    it('fetches anomalies for a specific zone', async () => {
      const mockAnomalies = [createMockAnomaly()];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse(mockAnomalies)),
      });

      renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/zones/zone-123/anomalies')
        );
      });
    });

    it('fetches all anomalies when no zoneId provided', async () => {
      const mockAnomalies = [createMockAnomaly()];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse(mockAnomalies)),
      });

      renderHook(() => useZoneAnomalies({}), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/api/zones/anomalies'));
      });
    });

    it('updates anomalies after successful fetch', async () => {
      const mockAnomalies = [
        createMockAnomaly({ id: 'anomaly-1', title: 'First anomaly' }),
        createMockAnomaly({ id: 'anomaly-2', title: 'Second anomaly' }),
      ];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse(mockAnomalies)),
      });

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.anomalies).toEqual(mockAnomalies);
      });

      expect(result.current.totalCount).toBe(2);
    });

    it('sets isLoading false after fetch', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([])),
      });

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
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
  });

  describe('filtering options', () => {
    it('passes severity filter to API', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([])),
      });

      renderHook(
        () =>
          useZoneAnomalies({
            zoneId: 'zone-123',
            severity: AnomalySeverity.CRITICAL,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('severity=critical')
        );
      });
    });

    it('passes multiple severity filters to API', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([])),
      });

      renderHook(
        () =>
          useZoneAnomalies({
            zoneId: 'zone-123',
            severity: [AnomalySeverity.WARNING, AnomalySeverity.CRITICAL],
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        const url = (mockFetch as Mock).mock.calls[0][0] as string;
        expect(url).toContain('severity=warning');
        expect(url).toContain('severity=critical');
      });
    });

    it('passes unacknowledged filter to API', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([])),
      });

      renderHook(
        () =>
          useZoneAnomalies({
            zoneId: 'zone-123',
            unacknowledgedOnly: true,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('unacknowledged_only=true')
        );
      });
    });

    it('passes since time filter to API', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([])),
      });

      const since = '2024-01-01T00:00:00Z';
      renderHook(
        () =>
          useZoneAnomalies({
            zoneId: 'zone-123',
            since,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining(`since=${encodeURIComponent(since)}`));
      });
    });

    it('passes limit and offset to API', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([])),
      });

      renderHook(
        () =>
          useZoneAnomalies({
            zoneId: 'zone-123',
            limit: 20,
            offset: 40,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        const url = (mockFetch as Mock).mock.calls[0][0] as string;
        expect(url).toContain('limit=20');
        expect(url).toContain('offset=40');
      });
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useZoneAnomalies({ zoneId: 'zone-123', enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('acknowledgeAnomaly mutation', () => {
    it('calls acknowledge API endpoint', async () => {
      // Initial fetch
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve(createMockListResponse([createMockAnomaly({ id: 'anomaly-1' })])),
      });

      // Acknowledge call
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 'anomaly-1',
            acknowledged: true,
            acknowledged_at: new Date().toISOString(),
            acknowledged_by: null,
          }),
      });

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Acknowledge
      await act(async () => {
        await result.current.acknowledgeAnomaly('anomaly-1');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/zones/anomalies/anomaly-1/acknowledge'),
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('applies optimistic update on acknowledge', async () => {
      const anomaly = createMockAnomaly({ id: 'anomaly-1', acknowledged: false });

      // Slow acknowledge to observe optimistic update
      let resolveAcknowledge: (value: unknown) => void;
      const acknowledgePromise = new Promise((resolve) => {
        resolveAcknowledge = resolve;
      });

      // Initial fetch
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([anomaly])),
      });

      // Acknowledge call
      mockFetch.mockReturnValueOnce({
        ok: true,
        json: () => acknowledgePromise,
      } as unknown as Promise<Response>);

      const queryClient = createQueryClient();
      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.anomalies).toHaveLength(1);
      });

      // Start acknowledge
      act(() => {
        void result.current.acknowledgeAnomaly('anomaly-1');
      });

      // Check optimistic update
      await waitFor(() => {
        const updatedAnomalies = result.current.anomalies;
        expect(updatedAnomalies[0].acknowledged).toBe(true);
      });

      // Resolve
      act(() => {
        resolveAcknowledge!({
          id: 'anomaly-1',
          acknowledged: true,
          acknowledged_at: new Date().toISOString(),
          acknowledged_by: null,
        });
      });
    });

    it('sets isAcknowledging during mutation', async () => {
      const anomaly = createMockAnomaly({ id: 'anomaly-1' });

      let resolveAcknowledge: (value: unknown) => void;
      const mockAcknowledgePromise = new Promise((resolve) => {
        resolveAcknowledge = resolve;
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([anomaly])),
      });

      mockFetch.mockReturnValueOnce({
        ok: true,
        json: () => mockAcknowledgePromise,
      } as unknown as Promise<Response>);

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Start acknowledge and wait for pending state
      let mutationPromise: Promise<unknown>;
      act(() => {
        mutationPromise = result.current.acknowledgeAnomaly('anomaly-1');
      });

      // Check isAcknowledging - use waitFor since state updates are async
      await waitFor(() => {
        expect(result.current.isAcknowledging).toBe(true);
      });

      // Resolve
      act(() => {
        resolveAcknowledge!({
          id: 'anomaly-1',
          acknowledged: true,
          acknowledged_at: new Date().toISOString(),
          acknowledged_by: null,
        });
      });

      await waitFor(() => {
        expect(result.current.isAcknowledging).toBe(false);
      });

      // Wait for the promise to complete
      await mutationPromise!;
    });
  });

  describe('refetch function', () => {
    it('provides refetch function', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([])),
      });

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockListResponse([])),
      });

      const { result } = renderHook(() => useZoneAnomalies({ zoneId: 'zone-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callCountBefore = mockFetch.mock.calls.length;

      await act(async () => {
        await result.current.refetch();
      });

      expect(mockFetch.mock.calls.length).toBeGreaterThan(callCountBefore);
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(zoneAnomalyQueryKeys.all).toEqual(['zone-anomalies']);
      expect(zoneAnomalyQueryKeys.forZone('zone-123')).toEqual([
        'zone-anomalies',
        'zone',
        'zone-123',
      ]);
      expect(zoneAnomalyQueryKeys.list({ severity: 'warning' })).toEqual([
        'zone-anomalies',
        'list',
        { severity: 'warning' },
      ]);
    });
  });
});
