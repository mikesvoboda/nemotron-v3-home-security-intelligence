/**
 * Tests for RiskHistoryCard component
 *
 * Tests cover:
 * - Rendering with risk history data
 * - Empty state when no data
 * - Loading state with skeleton
 * - Error state
 * - Summary metrics (total events, critical count, high count, avg/day)
 * - Trend indicator (increasing/decreasing high-risk events)
 * - Stacked area chart visualization
 * - Color coding by severity (green/yellow/orange/red)
 */
import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import RiskHistoryCard from './RiskHistoryCard';
import * as useRiskHistoryQueryModule from '../../hooks/useRiskHistoryQuery';

// Mock the hook
vi.mock('../../hooks/useRiskHistoryQuery', () => ({
  useRiskHistoryQuery: vi.fn(),
}));

describe('RiskHistoryCard', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockDataPoints = [
    { date: '2026-01-10', low: 12, medium: 8, high: 3, critical: 1 },
    { date: '2026-01-11', low: 15, medium: 10, high: 5, critical: 0 },
    { date: '2026-01-12', low: 8, medium: 6, high: 2, critical: 2 },
    { date: '2026-01-13', low: 20, medium: 12, high: 8, critical: 1 },
    { date: '2026-01-14', low: 10, medium: 7, high: 4, critical: 0 },
    { date: '2026-01-15', low: 14, medium: 9, high: 6, critical: 3 },
    { date: '2026-01-16', low: 18, medium: 11, high: 7, critical: 2 },
    { date: '2026-01-17', low: 16, medium: 8, high: 9, critical: 1 },
  ];

  const mockResponse = {
    data_points: mockDataPoints,
    start_date: '2026-01-10',
    end_date: '2026-01-17',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: mockResponse,
        dataPoints: mockDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('renders the card title', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByText('Risk History')).toBeInTheDocument();
    });

    it('renders the date range label', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });

    it('renders the stacked area chart container', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-history-chart')).toBeInTheDocument();
    });

    it('renders summary metrics section', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-history-metrics')).toBeInTheDocument();
    });

    it('renders legend with all severity levels', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      const legend = screen.getByTestId('risk-history-legend');
      expect(within(legend).getByText('Low')).toBeInTheDocument();
      expect(within(legend).getByText('Medium')).toBeInTheDocument();
      expect(within(legend).getByText('High')).toBeInTheDocument();
      expect(within(legend).getByText('Critical')).toBeInTheDocument();
    });
  });

  describe('summary metrics', () => {
    beforeEach(() => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: mockResponse,
        dataPoints: mockDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('displays total events count', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      // Calculate total: sum of all low + medium + high + critical
      // (12+8+3+1) + (15+10+5+0) + (8+6+2+2) + (20+12+8+1) + (10+7+4+0) + (14+9+6+3) + (18+11+7+2) + (16+8+9+1)
      // = 24 + 30 + 18 + 41 + 21 + 32 + 38 + 34 = 238
      const metricsSection = screen.getByTestId('risk-history-metrics');
      expect(within(metricsSection).getByText('238')).toBeInTheDocument();
      expect(within(metricsSection).getByText('Total Events')).toBeInTheDocument();
    });

    it('displays critical events count', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      // Critical: 1 + 0 + 2 + 1 + 0 + 3 + 2 + 1 = 10
      const metricsSection = screen.getByTestId('risk-history-metrics');
      expect(within(metricsSection).getByText('10')).toBeInTheDocument();
      expect(within(metricsSection).getByText('Critical')).toBeInTheDocument();
    });

    it('displays high events count', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      // High: 3 + 5 + 2 + 8 + 4 + 6 + 7 + 9 = 44
      const metricsSection = screen.getByTestId('risk-history-metrics');
      expect(within(metricsSection).getByText('44')).toBeInTheDocument();
      expect(within(metricsSection).getByText('High')).toBeInTheDocument();
    });

    it('displays average events per day', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      // Total 238 / 8 days = 29.75, rounded to 29.8
      const metricsSection = screen.getByTestId('risk-history-metrics');
      expect(within(metricsSection).getByText('29.8')).toBeInTheDocument();
      expect(within(metricsSection).getByText('Avg/Day')).toBeInTheDocument();
    });
  });

  describe('trend indicator', () => {
    it('shows increasing trend when high-risk events are increasing', () => {
      // Data with increasing high+critical events in second half
      const increasingDataPoints = [
        { date: '2026-01-10', low: 10, medium: 5, high: 2, critical: 0 },
        { date: '2026-01-11', low: 10, medium: 5, high: 2, critical: 0 },
        { date: '2026-01-12', low: 10, medium: 5, high: 3, critical: 1 },
        { date: '2026-01-13', low: 10, medium: 5, high: 5, critical: 2 },
      ];

      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: {
          data_points: increasingDataPoints,
          start_date: '2026-01-10',
          end_date: '2026-01-13',
        },
        dataPoints: increasingDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });

      render(<RiskHistoryCard dateRange={mockDateRange} />);

      const trendIndicator = screen.getByTestId('risk-trend-indicator');
      expect(trendIndicator).toHaveAttribute('data-trend', 'increasing');
    });

    it('shows decreasing trend when high-risk events are decreasing', () => {
      // Data with decreasing high+critical events in second half
      const decreasingDataPoints = [
        { date: '2026-01-10', low: 10, medium: 5, high: 5, critical: 2 },
        { date: '2026-01-11', low: 10, medium: 5, high: 4, critical: 1 },
        { date: '2026-01-12', low: 10, medium: 5, high: 2, critical: 0 },
        { date: '2026-01-13', low: 10, medium: 5, high: 1, critical: 0 },
      ];

      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: {
          data_points: decreasingDataPoints,
          start_date: '2026-01-10',
          end_date: '2026-01-13',
        },
        dataPoints: decreasingDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });

      render(<RiskHistoryCard dateRange={mockDateRange} />);

      const trendIndicator = screen.getByTestId('risk-trend-indicator');
      expect(trendIndicator).toHaveAttribute('data-trend', 'decreasing');
    });

    it('shows stable trend when high-risk events are flat', () => {
      // Data with stable high+critical events
      const stableDataPoints = [
        { date: '2026-01-10', low: 10, medium: 5, high: 3, critical: 1 },
        { date: '2026-01-11', low: 10, medium: 5, high: 3, critical: 1 },
        { date: '2026-01-12', low: 10, medium: 5, high: 3, critical: 1 },
        { date: '2026-01-13', low: 10, medium: 5, high: 3, critical: 1 },
      ];

      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: { data_points: stableDataPoints, start_date: '2026-01-10', end_date: '2026-01-13' },
        dataPoints: stableDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });

      render(<RiskHistoryCard dateRange={mockDateRange} />);

      const trendIndicator = screen.getByTestId('risk-trend-indicator');
      expect(trendIndicator).toHaveAttribute('data-trend', 'stable');
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: undefined,
        dataPoints: [],
        isLoading: true,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows loading skeleton when isLoading is true', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-history-loading')).toBeInTheDocument();
    });

    it('shows title in loading state', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByText('Risk History')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: undefined,
        dataPoints: [],
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to fetch'),
        isError: true,
        refetch: vi.fn(),
      });
    });

    it('shows error message when error occurs', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-history-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load risk history/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: { data_points: [], start_date: '2026-01-10', end_date: '2026-01-17' },
        dataPoints: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows empty state when no data', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-history-empty')).toBeInTheDocument();
      expect(screen.getByText(/No risk data available/)).toBeInTheDocument();
    });
  });

  describe('hook integration', () => {
    it('passes correct date range params to hook', () => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: mockResponse,
        dataPoints: mockDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });

      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(useRiskHistoryQueryModule.useRiskHistoryQuery).toHaveBeenCalledWith({
        start_date: '2026-01-10',
        end_date: '2026-01-17',
      });
    });
  });

  describe('color coding', () => {
    beforeEach(() => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        data: mockResponse,
        dataPoints: mockDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('renders legend with correct severity colors', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      const legend = screen.getByTestId('risk-history-legend');

      // Check that legend contains color indicators
      expect(within(legend).getByTestId('legend-low')).toBeInTheDocument();
      expect(within(legend).getByTestId('legend-medium')).toBeInTheDocument();
      expect(within(legend).getByTestId('legend-high')).toBeInTheDocument();
      expect(within(legend).getByTestId('legend-critical')).toBeInTheDocument();
    });
  });
});
