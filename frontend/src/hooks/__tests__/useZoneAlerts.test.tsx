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
import { useWebSocketEvents } from '../useWebSocketEvent';

import type { TrustViolationListResponse } from '../../types/zoneAlert';
import type { ZoneAnomalyListResponse } from '../../types/zoneAnomaly';

// Declare global fetch for TypeScript
declare const global: {
  fetch: typeof fetch;
};

// Mock useWebSocketEvents with full control
// Note: We need to define these outside vi.mock to avoid hoisting issues
let mockWebSocketHandlers: Record<string, (data: unknown) => void> = {};
let mockIsConnected = true;
let mockReconnectCount = 0;

vi.mock('../useWebSocketEvent', () => ({
  useWebSocketEvents: vi.fn((handlers: Record<string, (data: unknown) => void>) => {
    // Store handlers for later invocation in tests
    mockWebSocketHandlers = { ...handlers };
    return {
      isConnected: mockIsConnected,
      reconnectCount: mockReconnectCount,
      hasExhaustedRetries: false,
      lastHeartbeat: null,
      reconnect: vi.fn(),
    };
  }),
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

describe('useZoneAlerts - WebSocket Integration', () => {
  // Get reference to mocked function
  const mockUseWebSocketEvents = vi.mocked(useWebSocketEvents);

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock state
    mockWebSocketHandlers = {};
    mockIsConnected = true;
    mockReconnectCount = 0;

    // Setup default fetch mock
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/zones/anomalies')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            items: [],
            pagination: { total: 0, limit: 50, offset: 0, has_more: false },
          }),
        });
      }
      if (url.includes('/zones/trust-violations')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            items: [],
            pagination: { total: 0, limit: 50, offset: 0, has_more: false },
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false } }),
      });
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('subscribes to WebSocket events when enableRealtime is true', async () => {
    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have subscribed to both event types
    expect(mockUseWebSocketEvents).toHaveBeenCalled();
    const handlerArg = mockUseWebSocketEvents.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(handlerArg).toHaveProperty('zone.anomaly');
    expect(handlerArg).toHaveProperty('zone.trust_violation');
  });

  it('does not subscribe to WebSocket events when enableRealtime is false', async () => {
    renderHook(() => useZoneAlerts({ enableRealtime: false }), {
      wrapper: createTestWrapper(),
    });

    // Give time for subscription
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should have been called with empty handlers object
    expect(mockUseWebSocketEvents).toHaveBeenCalled();
    const handlerArg = mockUseWebSocketEvents.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(Object.keys(handlerArg)).toHaveLength(0);
  });

  it('does not subscribe when enabled is false', async () => {
    renderHook(() => useZoneAlerts({ enabled: false, enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    // Give time for subscription
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should have been called with empty handlers object (enabled gates both queries and websocket)
    expect(mockUseWebSocketEvents).toHaveBeenCalled();
    // When enabled is false, the hook passes an empty object to useWebSocketEvents
    // but useWebSocketEvents itself is gated by the enabled option
    const optionsArg = mockUseWebSocketEvents.mock.calls[0]?.[1] as { enabled: boolean };
    expect(optionsArg.enabled).toBe(false);
  });

  it('handles zone.anomaly WebSocket events and invalidates queries', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Verify handlers were registered
    expect(mockWebSocketHandlers['zone.anomaly']).toBeDefined();

    // Simulate receiving a zone.anomaly WebSocket event
    // Must match ZoneAnomalyEventPayload structure
    const anomalyEvent = {
      id: 'anomaly-ws-1',
      zone_id: 'zone-1',
      camera_id: 'cam-1',
      anomaly_type: AnomalyType.UNUSUAL_TIME,
      severity: AnomalySeverity.CRITICAL,
      title: 'New critical anomaly',
      timestamp: '2024-01-15T05:00:00Z',
    };

    // Clear previous calls
    invalidateSpy.mockClear();

    await act(async () => {
      const handler = mockWebSocketHandlers['zone.anomaly'];
      if (handler) {
        handler(anomalyEvent);
      }
      // Allow async operations to complete
      await new Promise(resolve => setTimeout(resolve, 50));
    });

    // Should have invalidated anomaly queries
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('shows toast for critical anomaly events', async () => {
    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Verify handlers were registered
    expect(mockWebSocketHandlers['zone.anomaly']).toBeDefined();

    // Clear previous toast calls
    mockToast.error.mockClear();

    // Simulate critical anomaly event
    // Must match ZoneAnomalyEventPayload structure
    const criticalEvent = {
      id: 'anomaly-ws-critical',
      zone_id: 'zone-1',
      camera_id: 'cam-1',
      anomaly_type: AnomalyType.UNUSUAL_TIME,
      severity: AnomalySeverity.CRITICAL,
      title: 'Critical Alert',
      timestamp: '2024-01-15T05:00:00Z',
    };

    await act(async () => {
      const handler = mockWebSocketHandlers['zone.anomaly'];
      if (handler) {
        handler(criticalEvent);
      }
      // Allow async operations to complete
      await new Promise(resolve => setTimeout(resolve, 50));
    });

    // Should show error toast for critical alerts
    expect(mockToast.error).toHaveBeenCalledWith('Critical Alert: Critical Alert');
  });

  it('does not show toast for non-critical anomaly events', async () => {
    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Simulate warning anomaly event
    // Must match ZoneAnomalyEventPayload structure
    const warningEvent = {
      id: 'anomaly-ws-warning',
      zone_id: 'zone-1',
      camera_id: 'cam-1',
      anomaly_type: AnomalyType.UNUSUAL_FREQUENCY,
      severity: AnomalySeverity.WARNING,
      title: 'Warning Alert',
      timestamp: '2024-01-15T05:00:00Z',
    };

    act(() => {
      const handler = mockWebSocketHandlers['zone.anomaly'];
      if (handler) {
        handler(warningEvent);
      }
    });

    // Give time for potential toast
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should not show toast for warning alerts
    expect(mockToast.error).not.toHaveBeenCalled();
  });

  it('handles zone.trust_violation WebSocket events', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Simulate trust violation event
    const violationEvent = {
      id: 'violation-1',
      zone_id: 'zone-1',
      camera_id: 'cam-1',
      violation_type: TrustViolationType.UNKNOWN_ENTITY,
      severity: 'critical',
      title: 'Unknown Entity',
      description: 'Unknown person detected',
      entity_id: null,
      entity_type: 'person',
      detection_id: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      acknowledged_by: null,
      timestamp: '2024-01-15T05:00:00Z',
      created_at: '2024-01-15T05:00:00Z',
      updated_at: '2024-01-15T05:00:00Z',
    };

    act(() => {
      const handler = mockWebSocketHandlers['zone.trust_violation'];
      if (handler) {
        handler(violationEvent);
      }
    });

    // Should have invalidated trust violation queries
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalled();
    });
  });

  it('shows toast for critical trust violation events', async () => {
    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Simulate critical trust violation
    const criticalViolation = {
      id: 'violation-1',
      zone_id: 'zone-1',
      camera_id: 'cam-1',
      violation_type: TrustViolationType.UNKNOWN_ENTITY,
      severity: 'critical',
      title: 'Unknown Entity Detected',
      description: 'Unknown person in restricted area',
      entity_id: null,
      entity_type: 'person',
      detection_id: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      acknowledged_by: null,
      timestamp: '2024-01-15T05:00:00Z',
      created_at: '2024-01-15T05:00:00Z',
      updated_at: '2024-01-15T05:00:00Z',
    };

    act(() => {
      const handler = mockWebSocketHandlers['zone.trust_violation'];
      if (handler) {
        handler(criticalViolation);
      }
    });

    // Should show error toast for critical violations
    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Security Alert: Unknown Entity Detected');
    });
  });

  it('filters WebSocket anomaly events by zones', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(
      () => useZoneAlerts({ zones: ['zone-1'], enableRealtime: true }),
      {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Simulate event for different zone
    // Must match ZoneAnomalyEventPayload structure
    const otherZoneEvent = {
      id: 'anomaly-ws-other',
      zone_id: 'zone-2',
      camera_id: 'cam-2',
      anomaly_type: AnomalyType.UNUSUAL_TIME,
      severity: AnomalySeverity.CRITICAL,
      title: 'Other zone event',
      timestamp: '2024-01-15T05:00:00Z',
    };

    invalidateSpy.mockClear();

    act(() => {
      const handler = mockWebSocketHandlers['zone.anomaly'];
      if (handler) {
        handler(otherZoneEvent);
      }
    });

    // Give time for potential invalidation
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should NOT invalidate queries for other zones
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it('filters WebSocket trust violation events by zones', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(
      () => useZoneAlerts({ zones: ['zone-1'], enableRealtime: true }),
      {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Simulate violation for different zone
    const otherZoneViolation = {
      id: 'violation-1',
      zone_id: 'zone-2',
      camera_id: 'cam-2',
      violation_type: TrustViolationType.UNKNOWN_ENTITY,
      severity: 'critical',
      title: 'Other zone violation',
      description: null,
      entity_id: null,
      entity_type: null,
      detection_id: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      acknowledged_by: null,
      timestamp: '2024-01-15T05:00:00Z',
      created_at: '2024-01-15T05:00:00Z',
      updated_at: '2024-01-15T05:00:00Z',
    };

    invalidateSpy.mockClear();

    act(() => {
      const handler = mockWebSocketHandlers['zone.trust_violation'];
      if (handler) {
        handler(otherZoneViolation);
      }
    });

    // Give time for potential invalidation
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should NOT invalidate queries for other zones
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it('ignores invalid anomaly event payloads', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    invalidateSpy.mockClear();

    // Simulate invalid event payload
    act(() => {
      const handler = mockWebSocketHandlers['zone.anomaly'];
      if (handler) {
        handler({ invalid: 'payload' });
      }
    });

    // Give time for potential processing
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should not invalidate queries for invalid payloads
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it('ignores invalid trust violation event payloads', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    invalidateSpy.mockClear();

    // Simulate invalid event payload
    act(() => {
      const handler = mockWebSocketHandlers['zone.trust_violation'];
      if (handler) {
        handler({ invalid: 'payload' });
      }
    });

    // Give time for potential processing
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should not invalidate queries for invalid payloads
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it('provides isConnected status from WebSocket', async () => {
    // Set connected state
    mockIsConnected = true;

    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isConnected).toBe(true);
  });

  it('reflects WebSocket disconnected state', async () => {
    // Set disconnected state
    mockIsConnected = false;

    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isConnected).toBe(false);
  });

  it('handles WebSocket reconnection attempts', async () => {
    // Set reconnecting state
    mockIsConnected = false;
    mockReconnectCount = 3;

    const { result } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // isConnected should reflect the WebSocket state
    expect(result.current.isConnected).toBe(false);
  });

  it('passes connection config to useWebSocketEvents', async () => {
    renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(mockUseWebSocketEvents).toHaveBeenCalled();
    });

    // Check the options passed
    const options = mockUseWebSocketEvents.mock.calls[0]?.[1] as { enabled: boolean };
    expect(options).toHaveProperty('enabled', true);
  });

  it('cleans up WebSocket subscription on unmount', async () => {
    const { unmount } = renderHook(() => useZoneAlerts({ enableRealtime: true }), {
      wrapper: createTestWrapper(),
    });

    // Wait for mount
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Unmount the hook
    unmount();

    // The WebSocket manager should handle cleanup internally
    // We just verify the hook doesn't throw or leave hanging subscriptions
    expect(mockUseWebSocketEvents).toHaveBeenCalled();
  });
});
