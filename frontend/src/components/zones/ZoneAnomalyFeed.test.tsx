/**
 * Tests for ZoneAnomalyFeed component (NEM-3199)
 *
 * This module tests the zone anomaly feed list:
 * - Rendering anomaly list
 * - Filter functionality
 * - Empty state
 * - Loading state
 * - Error state
 * - Real-time connection indicator
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import { ZoneAnomalyFeed } from './ZoneAnomalyFeed';
import { AnomalySeverity, AnomalyType } from '../../types/zoneAnomaly';

import type { ZoneAnomaly, ZoneAnomalyListResponse } from '../../types/zoneAnomaly';

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

// Track mock state
let mockIsConnected = true;

// Mock useWebSocketEvents
vi.mock('../../hooks/useWebSocketEvent', () => ({
  useWebSocketEvents: vi.fn(() => ({
    isConnected: mockIsConnected,
    reconnectCount: 0,
    hasExhaustedRetries: false,
    lastHeartbeat: null,
    reconnect: vi.fn(),
  })),
}));

// Mock useToast
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  }),
}));

// Mock useZonesQuery
vi.mock('../../hooks/useZones', () => ({
  useZonesQuery: vi.fn(() => ({
    zones: [
      { id: 'zone-1', name: 'Front Door' },
      { id: 'zone-2', name: 'Back Yard' },
    ],
    total: 2,
    isLoading: false,
    isRefetching: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

// Helper to create a test query client
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// Helper to wrap component with providers
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe('ZoneAnomalyFeed', () => {
  // Helper to create mock anomaly
  const createMockAnomaly = (overrides: Partial<ZoneAnomaly> = {}): ZoneAnomaly => ({
    id: `anomaly-${Math.random().toString(36).slice(2, 9)}`,
    zone_id: 'zone-1',
    camera_id: 'cam-1',
    anomaly_type: AnomalyType.UNUSUAL_TIME,
    severity: AnomalySeverity.WARNING,
    title: 'Test Anomaly',
    description: 'Test description',
    expected_value: 0.1,
    actual_value: 1.0,
    deviation: 3.5,
    detection_id: 12345,
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  });

  // Helper to create mock list response
  const createMockResponse = (anomalies: ZoneAnomaly[]): ZoneAnomalyListResponse => ({
    items: anomalies,
    pagination: {
      total: anomalies.length,
      limit: 50,
      offset: 0,
      has_more: false,
    },
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
    mockIsConnected = true;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the feed header', () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      expect(screen.getByText('Zone Anomalies')).toBeInTheDocument();
    });

    it('renders filter controls', () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      expect(screen.getByLabelText('Filter by severity')).toBeInTheDocument();
      expect(screen.getByLabelText('Filter by zone')).toBeInTheDocument();
      expect(screen.getByLabelText('Filter by acknowledged status')).toBeInTheDocument();
    });

    it('renders anomaly count in subtitle', async () => {
      const anomalies = [createMockAnomaly(), createMockAnomaly()];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse(anomalies)),
      });

      renderWithProviders(<ZoneAnomalyFeed hoursLookback={24} />);

      await waitFor(() => {
        expect(screen.getByText(/2 anomalies in the last 24 hours/)).toBeInTheDocument();
      });
    });

    it('uses singular "anomaly" for count of 1', async () => {
      const anomalies = [createMockAnomaly()];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse(anomalies)),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.getByText(/1 anomaly in the last/)).toBeInTheDocument();
      });
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton initially', () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolving

      renderWithProviders(<ZoneAnomalyFeed />);

      expect(screen.getByTestId('anomaly-feed-loading')).toBeInTheDocument();
    });

    it('hides loading state after data loads', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.queryByTestId('anomaly-feed-loading')).not.toBeInTheDocument();
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no anomalies', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.getByTestId('anomaly-feed-empty')).toBeInTheDocument();
      });

      expect(screen.getByText('No anomalies found')).toBeInTheDocument();
      expect(screen.getByText('Zone activity is within normal patterns.')).toBeInTheDocument();
    });

    it('shows filter hint when no anomalies with active filters', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(
        <ZoneAnomalyFeed initialFilters={{ severity: AnomalySeverity.CRITICAL }} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('anomaly-feed-empty')).toBeInTheDocument();
      });

      expect(screen.getByText('Try adjusting your filters to see more results.')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error state on fetch failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(
        () => {
          expect(screen.getByTestId('anomaly-feed-error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByText('Failed to load anomalies')).toBeInTheDocument();
    });

    it('shows retry button on error', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Server Error',
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(
        () => {
          expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });

    it('retries fetch on retry button click', async () => {
      const user = userEvent.setup();
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: 'Server Error',
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(
        () => {
          expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      // Setup success response for retry
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      // Verify fetch was called again
      expect(mockFetch.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('anomaly list', () => {
    it('renders list of anomalies', async () => {
      const anomalies = [
        createMockAnomaly({ id: 'anomaly-1', title: 'First Anomaly' }),
        createMockAnomaly({ id: 'anomaly-2', title: 'Second Anomaly' }),
      ];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse(anomalies)),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.getByTestId('anomaly-feed-list')).toBeInTheDocument();
      });

      expect(screen.getByText('First Anomaly')).toBeInTheDocument();
      expect(screen.getByText('Second Anomaly')).toBeInTheDocument();
    });

    it('renders anomaly alerts with zone names', async () => {
      const anomalies = [createMockAnomaly({ zone_id: 'zone-1' })];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse(anomalies)),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });
    });
  });

  describe('filtering', () => {
    it('filters by severity', async () => {
      const user = userEvent.setup();
      const anomalies = [
        createMockAnomaly({ severity: AnomalySeverity.WARNING }),
        createMockAnomaly({ severity: AnomalySeverity.CRITICAL }),
      ];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse(anomalies)),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.getByTestId('anomaly-feed-list')).toBeInTheDocument();
      });

      const severitySelect = screen.getByLabelText('Filter by severity');
      await user.selectOptions(severitySelect, 'critical');

      // Should trigger a new fetch with severity filter
      await waitFor(() => {
        const calls = mockFetch.mock.calls;
        const lastCall = calls[calls.length - 1];
        expect(lastCall[0]).toContain('severity=critical');
      });
    });

    it('filters by zone', async () => {
      const user = userEvent.setup();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.queryByTestId('anomaly-feed-loading')).not.toBeInTheDocument();
      });

      const zoneSelect = screen.getByLabelText('Filter by zone');
      await user.selectOptions(zoneSelect, 'zone-1');

      await waitFor(() => {
        const calls = mockFetch.mock.calls;
        const lastCall = calls[calls.length - 1];
        expect(lastCall[0]).toContain('/zones/zone-1/anomalies');
      });
    });

    it('filters by acknowledged status and passes to API', async () => {
      const user = userEvent.setup();
      // Initial fetch returns all anomalies
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.queryByTestId('anomaly-feed-loading')).not.toBeInTheDocument();
      });

      // Filter to unacknowledged only
      const statusSelect = screen.getByLabelText('Filter by acknowledged status');
      await user.selectOptions(statusSelect, 'unacknowledged');

      // Should pass unacknowledged_only to the API
      await waitFor(() => {
        const calls = mockFetch.mock.calls;
        const lastCall = calls[calls.length - 1];
        expect(lastCall[0]).toContain('unacknowledged_only=true');
      });
    });

    it('uses initial filters from props', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(
        <ZoneAnomalyFeed initialFilters={{ severity: AnomalySeverity.CRITICAL }} />
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('severity=critical'));
      });
    });
  });

  describe('connection status', () => {
    it('shows Live indicator when connected', async () => {
      mockIsConnected = true;
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed enableRealtime />);

      await waitFor(() => {
        expect(screen.getByText('Live')).toBeInTheDocument();
      });
    });

    it('shows Offline indicator when disconnected', async () => {
      mockIsConnected = false;
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed enableRealtime />);

      await waitFor(() => {
        expect(screen.getByText('Offline')).toBeInTheDocument();
      });
    });

    it('hides connection indicator when realtime disabled', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed enableRealtime={false} />);

      await waitFor(() => {
        expect(screen.queryByTestId('anomaly-feed-loading')).not.toBeInTheDocument();
      });

      expect(screen.queryByText('Live')).not.toBeInTheDocument();
      expect(screen.queryByText('Offline')).not.toBeInTheDocument();
    });
  });

  describe('click handling', () => {
    it('calls onAnomalyClick when anomaly is clicked', async () => {
      const user = userEvent.setup();
      const onAnomalyClick = vi.fn();
      const anomalies = [createMockAnomaly({ id: 'test-anomaly' })];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse(anomalies)),
      });

      renderWithProviders(<ZoneAnomalyFeed onAnomalyClick={onAnomalyClick} />);

      await waitFor(() => {
        expect(screen.getByTestId('anomaly-feed-list')).toBeInTheDocument();
      });

      const alert = screen.getByTestId('zone-anomaly-alert');
      await user.click(alert);

      expect(onAnomalyClick).toHaveBeenCalledTimes(1);
      expect(onAnomalyClick).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'test-anomaly' })
      );
    });
  });

  describe('acknowledge functionality', () => {
    it('calls acknowledge endpoint when acknowledge button clicked', async () => {
      const user = userEvent.setup();
      const anomalies = [createMockAnomaly({ id: 'test-anomaly', acknowledged: false })];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(createMockResponse(anomalies)),
      });

      renderWithProviders(<ZoneAnomalyFeed />);

      await waitFor(() => {
        expect(screen.getByTestId('anomaly-feed-list')).toBeInTheDocument();
      });

      // Setup acknowledge response
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 'test-anomaly',
            acknowledged: true,
            acknowledged_at: new Date().toISOString(),
            acknowledged_by: null,
          }),
      });

      const acknowledgeButton = screen.getByRole('button', { name: /acknowledge/i });
      await user.click(acknowledgeButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/zones/anomalies/test-anomaly/acknowledge'),
          expect.objectContaining({ method: 'POST' })
        );
      });
    });
  });

  describe('custom styling', () => {
    it('applies custom className', () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed className="custom-feed-class" />);

      const feed = screen.getByTestId('zone-anomaly-feed');
      expect(feed).toHaveClass('custom-feed-class');
    });

    it('applies custom maxHeight', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      const { container } = renderWithProviders(<ZoneAnomalyFeed maxHeight="400px" />);

      await waitFor(() => {
        expect(screen.queryByTestId('anomaly-feed-loading')).not.toBeInTheDocument();
      });

      const scrollContainer = container.querySelector('.overflow-y-auto');
      expect(scrollContainer).toHaveStyle({ maxHeight: '400px' });
    });

    it('handles numeric maxHeight', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      const { container } = renderWithProviders(<ZoneAnomalyFeed maxHeight={500} />);

      await waitFor(() => {
        expect(screen.queryByTestId('anomaly-feed-loading')).not.toBeInTheDocument();
      });

      const scrollContainer = container.querySelector('.overflow-y-auto');
      expect(scrollContainer).toHaveStyle({ maxHeight: '500px' });
    });
  });

  describe('hours lookback', () => {
    it('uses custom hoursLookback in query', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed hoursLookback={12} />);

      await waitFor(() => {
        expect(screen.getByText(/in the last 12 hours/)).toBeInTheDocument();
      });
    });

    it('calculates correct since time based on hoursLookback', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse([])),
      });

      renderWithProviders(<ZoneAnomalyFeed hoursLookback={6} />);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });

      // Check that since parameter is roughly 6 hours ago
      const call = mockFetch.mock.calls[0][0] as string;
      expect(call).toContain('since=');

      const url = new URL(call, 'http://localhost');
      const sinceParam = url.searchParams.get('since');
      if (sinceParam) {
        const sinceDate = new Date(sinceParam);
        const now = new Date();
        const diffHours = (now.getTime() - sinceDate.getTime()) / (1000 * 60 * 60);
        // Allow some tolerance for test execution time
        expect(diffHours).toBeGreaterThanOrEqual(5.9);
        expect(diffHours).toBeLessThanOrEqual(6.1);
      }
    });
  });
});
