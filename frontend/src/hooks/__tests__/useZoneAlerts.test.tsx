/**
 * Tests for useZoneAlerts hook (NEM-3196)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TrustViolationType } from '../../types/zoneAlert';
import { AnomalyType, AnomalySeverity } from '../../types/zoneAnomaly';
import { useZoneAlerts, zoneAlertQueryKeys } from '../useZoneAlerts';

import type { TrustViolationListResponse } from '../../types/zoneAlert';
import type { ZoneAnomalyListResponse } from '../../types/zoneAnomaly';

// Declare global fetch for TypeScript
declare const global: {
  fetch: typeof fetch;
};


// Mock useWebSocketEvents
vi.mock('../useWebSocketEvent', () => ({
  useWebSocketEvents: () => ({ isConnected: true }),
}));

// Mock useToast
const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
};
vi.mock('../useToast', () => ({
  useToast: () => mockToast,
}));

// Store original fetch
const originalFetch = global.fetch;

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// Mock fetch function
const mockFetch = vi.fn();

describe('useZoneAlerts', () => {
  const mockAnomaliesResponse: ZoneAnomalyListResponse = {
    items: [
      {
        id: 'anomaly-1',
        zone_id: 'zone-1',
        camera_id: 'cam-1',
        anomaly_type: AnomalyType.UNUSUAL_TIME,
        severity: AnomalySeverity.CRITICAL,
        title: 'Critical anomaly',
        description: 'Detected at unusual time',
        expected_value: 5,
        actual_value: 50,
        deviation: 9.0,
        detection_id: 1,
        thumbnail_url: null,
        acknowledged: false,
        acknowledged_at: null,
        acknowledged_by: null,
        timestamp: '2024-01-15T03:00:00Z',
        created_at: '2024-01-15T03:00:00Z',
        updated_at: '2024-01-15T03:00:00Z',
      },
      {
        id: 'anomaly-2',
        zone_id: 'zone-2',
        camera_id: 'cam-2',
        anomaly_type: AnomalyType.UNUSUAL_FREQUENCY,
        severity: AnomalySeverity.WARNING,
        title: 'Warning anomaly',
        description: 'High frequency detected',
        expected_value: 10,
        actual_value: 30,
        deviation: 4.0,
        detection_id: 2,
        thumbnail_url: null,
        acknowledged: true,
        acknowledged_at: '2024-01-15T04:00:00Z',
        acknowledged_by: 'user-1',
        timestamp: '2024-01-15T02:00:00Z',
        created_at: '2024-01-15T02:00:00Z',
        updated_at: '2024-01-15T04:00:00Z',
      },
    ],
    pagination: {
      total: 2,
      limit: 50,
      offset: 0,
      has_more: false,
    },
  };

  const mockTrustViolationsResponse: TrustViolationListResponse = {
    items: [
      {
        id: 'violation-1',
        zone_id: 'zone-1',
        camera_id: 'cam-1',
        violation_type: TrustViolationType.UNKNOWN_ENTITY,
        severity: 'critical',
        title: 'Unknown person detected',
        description: 'An unknown person was detected in restricted zone',
        entity_id: 'entity-1',
        entity_type: 'person',
        detection_id: 3,
        thumbnail_url: null,
        acknowledged: false,
        acknowledged_at: null,
        acknowledged_by: null,
        timestamp: '2024-01-15T04:00:00Z',
        created_at: '2024-01-15T04:00:00Z',
        updated_at: '2024-01-15T04:00:00Z',
      },
    ],
    pagination: {
      total: 1,
      limit: 50,
      offset: 0,
      has_more: false,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Setup global fetch mock
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/zones/anomalies')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockAnomaliesResponse),
        });
      }
      if (url.includes('/zones/trust-violations')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTrustViolationsResponse),
        });
      }
      if (url.includes('/acknowledge')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false } }),
      });
    });
  });

  afterEach(() => {
    // Restore original fetch
    global.fetch = originalFetch;
  });

  it('fetches and combines anomalies and trust violations', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have 3 alerts total (2 anomalies + 1 trust violation)
    expect(result.current.alerts).toHaveLength(3);
    expect(result.current.totalCount).toBe(3);
  });

  it('sorts alerts by priority (critical first) then by timestamp', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Critical alerts should come first
    const criticalAlerts = result.current.alerts.filter((a) => a.severity === 'critical');
    const warningAlerts = result.current.alerts.filter((a) => a.severity === 'warning');

    // Both critical alerts should appear before the warning alert
    const firstWarningIndex = result.current.alerts.findIndex((a) => a.severity === 'warning');
    // Find last critical index using reverse search
    const lastCriticalIndex = result.current.alerts.length - 1 -
      [...result.current.alerts].reverse().findIndex((a) => a.severity === 'critical');

    expect(lastCriticalIndex).toBeLessThan(firstWarningIndex);
    expect(criticalAlerts.length).toBe(2);
    expect(warningAlerts.length).toBe(1);
  });

  it('calculates unacknowledged count correctly', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // 2 unacknowledged (anomaly-1 and violation-1)
    expect(result.current.unacknowledgedCount).toBe(2);
  });

  it('respects the zones filter', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/zones/zone-1/anomalies')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            items: [mockAnomaliesResponse.items[0]],
            pagination: { total: 1, limit: 50, offset: 0, has_more: false },
          }),
        });
      }
      if (url.includes('/zones/trust-violations')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTrustViolationsResponse),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false } }),
      });
    });

    const { result } = renderHook(() => useZoneAlerts({ zones: ['zone-1'] }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have called the zone-specific endpoint
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/zones/zone-1/anomalies'));
  });

  it('respects the severities filter', async () => {
    const { result } = renderHook(() => useZoneAlerts({ severities: ['critical'] }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('severity=critical'));
  });

  it('respects the acknowledged filter', async () => {
    const { result } = renderHook(() => useZoneAlerts({ acknowledged: false }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('unacknowledged_only=true'));
  });

  it('respects the limit option', async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          items: Array(50).fill(mockAnomaliesResponse.items[0]).map((item, i) => ({
            ...item,
            id: `anomaly-${i}`,
          })),
          pagination: { total: 50, limit: 100, offset: 0, has_more: false },
        }),
      })
    );

    const { result } = renderHook(() => useZoneAlerts({ limit: 10 }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should be limited to 10 alerts
    expect(result.current.alerts.length).toBeLessThanOrEqual(10);
  });

  it('respects the enabled option', async () => {
    renderHook(() => useZoneAlerts({ enabled: false }), {
      wrapper: createTestWrapper(),
    });

    // Give time for potential fetch
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should not have called fetch when disabled
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('handles acknowledge alert', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.acknowledgeAlert('anomaly-1', 'anomaly');
    });

    // Should have called the acknowledge endpoint
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/anomalies/anomaly-1/acknowledge'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('handles acknowledge trust violation', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.acknowledgeAlert('violation-1', 'trust_violation');
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/trust-violations/violation-1/acknowledge'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('handles acknowledge all', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.acknowledgeAll();
    });

    // Should show success toast
    expect(mockToast.success).toHaveBeenCalledWith('All alerts acknowledged');
  });

  it('handles acknowledge by severity', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.acknowledgeBySeverity('critical');
    });

    expect(mockToast.success).toHaveBeenCalledWith('All critical alerts acknowledged');
  });

  it('handles fetch error gracefully', async () => {
    mockFetch.mockImplementation(() =>
      Promise.reject(new Error('Network error'))
    );

    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.isError).toBe(true);
      },
      { timeout: 2000 }
    );

    expect(result.current.error).toBeDefined();
  });

  it('handles 404 for trust violations endpoint gracefully', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/zones/anomalies')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockAnomaliesResponse),
        });
      }
      if (url.includes('/zones/trust-violations')) {
        return Promise.resolve({
          ok: false,
          status: 404,
          statusText: 'Not Found',
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false } }),
      });
    });

    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should still work with just anomalies
    expect(result.current.alerts.length).toBe(2);
    expect(result.current.isError).toBe(false);
  });

  it('provides refetch function', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const initialCallCount = mockFetch.mock.calls.length;

    await act(async () => {
      await result.current.refetch();
    });

    // Should have called fetch again
    expect(mockFetch.mock.calls.length).toBeGreaterThan(initialCallCount);
  });

  it('provides isConnected status from WebSocket', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isConnected).toBe(true);
  });

  it('provides isAcknowledging status', async () => {
    const { result } = renderHook(() => useZoneAlerts(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // isAcknowledging should be false when not acknowledging
    expect(result.current.isAcknowledging).toBe(false);

    // Start and complete acknowledging
    await act(async () => {
      await result.current.acknowledgeAlert('anomaly-1', 'anomaly');
    });

    // Should be false again after completion
    expect(result.current.isAcknowledging).toBe(false);
  });
});

describe('zoneAlertQueryKeys', () => {
  it('generates correct query keys', () => {
    expect(zoneAlertQueryKeys.all).toEqual(['zone-alerts']);

    const anomaliesKey = zoneAlertQueryKeys.anomalies({ zones: ['z-1'] });
    expect(anomaliesKey).toContain('zone-alerts');
    expect(anomaliesKey).toContain('anomalies');

    const violationsKey = zoneAlertQueryKeys.trustViolations({ severities: ['critical'] });
    expect(violationsKey).toContain('zone-alerts');
    expect(violationsKey).toContain('trust-violations');

    const combinedKey = zoneAlertQueryKeys.combined({ limit: 50 });
    expect(combinedKey).toContain('zone-alerts');
    expect(combinedKey).toContain('combined');
  });
});
