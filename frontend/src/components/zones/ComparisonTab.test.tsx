/**
 * Tests for ComparisonTab component (NEM-4714)
 *
 * Tests the comparison tab including:
 * - Zone selection
 * - Metric and period selection
 * - Integration with comparison components
 * - Loading and empty states
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import { ComparisonTab } from './ComparisonTab';

import type { Zone } from '../../types/generated';

// Mock the child components to simplify testing
vi.mock('./ZoneComparisonTable', () => {
  const MockTable = ({ zones, metric, isLoading }: { zones: unknown[]; metric: string; isLoading?: boolean }) => (
    <div data-testid="mock-comparison-table">
      {isLoading ? 'Loading...' : `Table: ${(zones).length} zones, metric: ${metric}`}
    </div>
  );
  return {
    ZoneComparisonTable: MockTable,
    default: MockTable,
  };
});

vi.mock('./ZoneComparisonChart', () => {
  const MockChart = ({ zones, metric, isLoading }: { zones: unknown[]; metric: string; isLoading?: boolean }) => (
    <div data-testid="mock-comparison-chart">
      {isLoading ? 'Loading...' : `Chart: ${(zones).length} zones, metric: ${metric}`}
    </div>
  );
  return {
    ZoneComparisonChart: MockChart,
    default: MockChart,
  };
});

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

describe('ComparisonTab', () => {
  // Helper to create mock zone
  const createMockZone = (id: number, name: string): Zone => ({
    id: id.toString(),
    camera_id: 'cam-123',
    name,
    zone_type: 'entry_point',
    coordinates: [],
    shape: 'polygon',
    color: '#3B82F6',
    enabled: true,
    priority: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  });

  // Wrapper with QueryClient
  const createWrapper = () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    return ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the comparison tab', () => {
      const zones = [createMockZone(1, 'Zone A'), createMockZone(2, 'Zone B')];

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      expect(screen.getByTestId('comparison-tab')).toBeInTheDocument();
    });

    it('displays zone selection grid', () => {
      const zones = [createMockZone(1, 'Zone A'), createMockZone(2, 'Zone B')];

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      expect(screen.getByTestId('zone-selection-grid')).toBeInTheDocument();
      expect(screen.getByText('Zone A')).toBeInTheDocument();
      expect(screen.getByText('Zone B')).toBeInTheDocument();
    });

    it('displays metric selector buttons', () => {
      const zones = [createMockZone(1, 'Zone A')];

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      expect(screen.getByTestId('metric-crossings')).toBeInTheDocument();
      expect(screen.getByTestId('metric-dwell_time')).toBeInTheDocument();
      expect(screen.getByTestId('metric-anomalies')).toBeInTheDocument();
      expect(screen.getByTestId('metric-occupancy')).toBeInTheDocument();
    });

    it('displays period selector buttons', () => {
      const zones = [createMockZone(1, 'Zone A')];

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      expect(screen.getByTestId('period-day')).toBeInTheDocument();
      expect(screen.getByTestId('period-week')).toBeInTheDocument();
      expect(screen.getByTestId('period-month')).toBeInTheDocument();
    });
  });

  describe('zone selection', () => {
    it('allows selecting zones', async () => {
      const user = userEvent.setup();
      const zones = [createMockZone(1, 'Zone A'), createMockZone(2, 'Zone B')];

      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            metric: 'crossings',
            zones: [],
            start_time: '2024-01-01T00:00:00Z',
            end_time: '2024-01-01T23:59:59Z',
            comparison_period: 'day',
          }),
      });

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      // Initially, no zones selected - shows prompt
      expect(screen.getByTestId('comparison-no-selection')).toBeInTheDocument();

      // Select Zone A
      const zoneACheckbox = screen.getByLabelText('Select Zone A');
      await user.click(zoneACheckbox);

      // Should now show comparison components
      await waitFor(() => {
        expect(screen.getByTestId('mock-comparison-table')).toBeInTheDocument();
        expect(screen.getByTestId('mock-comparison-chart')).toBeInTheDocument();
      });
    });

    it('allows deselecting zones', async () => {
      const user = userEvent.setup();
      const zones = [createMockZone(1, 'Zone A')];

      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            metric: 'crossings',
            zones: [],
            start_time: '2024-01-01T00:00:00Z',
            end_time: '2024-01-01T23:59:59Z',
            comparison_period: 'day',
          }),
      });

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      // Select Zone A
      const zoneACheckbox = screen.getByLabelText('Select Zone A');
      await user.click(zoneACheckbox);

      // Deselect Zone A
      await user.click(zoneACheckbox);

      // Should show no selection state again
      await waitFor(() => {
        expect(screen.getByTestId('comparison-no-selection')).toBeInTheDocument();
      });
    });

    it('select all button selects all zones', async () => {
      const user = userEvent.setup();
      const zones = [createMockZone(1, 'Zone A'), createMockZone(2, 'Zone B')];

      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            metric: 'crossings',
            zones: [],
            start_time: '2024-01-01T00:00:00Z',
            end_time: '2024-01-01T23:59:59Z',
            comparison_period: 'day',
          }),
      });

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      // Click Select All
      const selectAllBtn = screen.getByTestId('select-all-btn');
      await user.click(selectAllBtn);

      // Should show comparison components
      await waitFor(() => {
        expect(screen.getByTestId('mock-comparison-table')).toBeInTheDocument();
      });
    });

    it('clear button deselects all zones', async () => {
      const user = userEvent.setup();
      const zones = [createMockZone(1, 'Zone A'), createMockZone(2, 'Zone B')];

      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            metric: 'crossings',
            zones: [],
            start_time: '2024-01-01T00:00:00Z',
            end_time: '2024-01-01T23:59:59Z',
            comparison_period: 'day',
          }),
      });

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      // Select all first
      await user.click(screen.getByTestId('select-all-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('mock-comparison-table')).toBeInTheDocument();
      });

      // Click Clear
      await user.click(screen.getByTestId('clear-all-btn'));

      // Should show no selection state
      await waitFor(() => {
        expect(screen.getByTestId('comparison-no-selection')).toBeInTheDocument();
      });
    });
  });

  describe('metric selection', () => {
    it('changes metric when clicking metric button', async () => {
      const user = userEvent.setup();
      const zones = [createMockZone(1, 'Zone A')];

      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            metric: 'dwell_time',
            zones: [],
            start_time: '2024-01-01T00:00:00Z',
            end_time: '2024-01-01T23:59:59Z',
            comparison_period: 'day',
          }),
      });

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      // Select a zone first
      await user.click(screen.getByLabelText('Select Zone A'));

      // Click dwell_time metric
      await user.click(screen.getByTestId('metric-dwell_time'));

      // Wait for the fetch to be called with dwell_time
      await waitFor(() => {
        const callUrl = mockFetch.mock.calls[mockFetch.mock.calls.length - 1][0] as string;
        expect(callUrl).toContain('metric=dwell_time');
      });
    });
  });

  describe('period selection', () => {
    it('changes period when clicking period button', async () => {
      const user = userEvent.setup();
      const zones = [createMockZone(1, 'Zone A')];

      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            metric: 'crossings',
            zones: [],
            start_time: '2024-01-01T00:00:00Z',
            end_time: '2024-01-07T23:59:59Z',
            comparison_period: 'week',
          }),
      });

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      // Select a zone first
      await user.click(screen.getByLabelText('Select Zone A'));

      // Click week period
      await user.click(screen.getByTestId('period-week'));

      // Wait for the fetch to be called with week
      await waitFor(() => {
        const callUrl = mockFetch.mock.calls[mockFetch.mock.calls.length - 1][0] as string;
        expect(callUrl).toContain('period=week');
      });
    });
  });

  describe('loading states', () => {
    it('shows loading state when zones are loading', () => {
      render(<ComparisonTab zones={[]} isLoadingZones={true} />, { wrapper: createWrapper() });

      expect(screen.getByTestId('comparison-tab-loading-zones')).toBeInTheDocument();
    });
  });

  describe('empty states', () => {
    it('shows empty state when no zones available', () => {
      render(<ComparisonTab zones={[]} />, { wrapper: createWrapper() });

      expect(screen.getByTestId('comparison-tab-no-zones')).toBeInTheDocument();
      expect(screen.getByText('No zones available')).toBeInTheDocument();
    });

    it('shows no selection state when no zones selected', () => {
      const zones = [createMockZone(1, 'Zone A')];

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      expect(screen.getByTestId('comparison-no-selection')).toBeInTheDocument();
      // Check text within the no-selection state specifically
      const noSelectionDiv = screen.getByTestId('comparison-no-selection');
      expect(noSelectionDiv).toHaveTextContent('Select Zones to Compare');
      expect(noSelectionDiv).toHaveTextContent('Choose two or more zones');
    });
  });

  describe('error handling', () => {
    it('shows error state on API failure', async () => {
      const user = userEvent.setup();
      const zones = [createMockZone(1, 'Zone A')];

      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      // Select a zone to trigger fetch
      await user.click(screen.getByLabelText('Select Zone A'));

      // Wait for error state
      await waitFor(
        () => {
          expect(screen.getByTestId('comparison-error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('time range info', () => {
    it('displays time range info when data is loaded', async () => {
      const user = userEvent.setup();
      const zones = [createMockZone(1, 'Zone A')];

      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            metric: 'crossings',
            zones: [
              {
                zone_id: 1,
                zone_name: 'Zone A',
                zone_type: 'entry_point',
                camera_id: 'cam-123',
                value: 100,
                trend_percent: 5.5,
              },
            ],
            start_time: '2024-01-01T00:00:00Z',
            end_time: '2024-01-01T23:59:59Z',
            comparison_period: 'day',
          }),
      });

      render(<ComparisonTab zones={zones} />, { wrapper: createWrapper() });

      // Select a zone
      await user.click(screen.getByLabelText('Select Zone A'));

      // Wait for time range info
      await waitFor(() => {
        expect(screen.getByTestId('time-range-info')).toBeInTheDocument();
      });
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      const zones = [createMockZone(1, 'Zone A')];

      render(<ComparisonTab zones={zones} className="custom-class" />, {
        wrapper: createWrapper(),
      });

      expect(screen.getByTestId('comparison-tab')).toHaveClass('custom-class');
    });
  });
});
