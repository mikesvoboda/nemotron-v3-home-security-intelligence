/**
 * Tests for RiskScoreTrendCard component
 *
 * Tests cover:
 * - Rendering with trend data
 * - Empty state when no data
 * - Loading state
 * - Error state
 * - Date range display
 * - Average score and trend display
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import RiskScoreTrendCard from './RiskScoreTrendCard';
import * as useRiskScoreTrendsModule from '../../hooks/useRiskScoreTrends';

// Mock the hook
vi.mock('../../hooks/useRiskScoreTrends', () => ({
  useRiskScoreTrends: vi.fn(),
}));

describe('RiskScoreTrendCard', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockDataPoints = [
    { date: '2026-01-10', avg_score: 30.0, count: 5 },
    { date: '2026-01-11', avg_score: 35.0, count: 8 },
    { date: '2026-01-12', avg_score: 40.0, count: 10 },
    { date: '2026-01-13', avg_score: 45.0, count: 7 },
    { date: '2026-01-14', avg_score: 42.0, count: 6 },
    { date: '2026-01-15', avg_score: 38.0, count: 4 },
    { date: '2026-01-16', avg_score: 50.0, count: 9 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        data: {
          data_points: mockDataPoints,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        dataPoints: mockDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('renders the card title', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      expect(screen.getByText('Risk Score Trends')).toBeInTheDocument();
    });

    it('displays average score', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      // Weighted average should be displayed
      expect(screen.getByTestId('risk-score-trend-average')).toBeInTheDocument();
    });

    it('displays trend direction', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      // Trend from 30 to 50 = +20
      expect(screen.getByTestId('risk-score-trend-direction')).toBeInTheDocument();
    });

    it('displays date range label', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });

    it('renders the main card element', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-trend-card')).toBeInTheDocument();
    });
  });

  describe('positive trend display', () => {
    beforeEach(() => {
      const increasingDataPoints = [
        { date: '2026-01-10', avg_score: 20.0, count: 5 },
        { date: '2026-01-11', avg_score: 40.0, count: 5 },
      ];

      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        data: {
          data_points: increasingDataPoints,
          start_date: '2026-01-10',
          end_date: '2026-01-11',
        },
        dataPoints: increasingDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows positive trend with plus sign', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      const trendElement = screen.getByTestId('risk-score-trend-direction');
      expect(trendElement).toHaveTextContent('+20');
    });
  });

  describe('negative trend display', () => {
    beforeEach(() => {
      const decreasingDataPoints = [
        { date: '2026-01-10', avg_score: 60.0, count: 5 },
        { date: '2026-01-11', avg_score: 40.0, count: 5 },
      ];

      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        data: {
          data_points: decreasingDataPoints,
          start_date: '2026-01-10',
          end_date: '2026-01-11',
        },
        dataPoints: decreasingDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows negative trend without plus sign', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      const trendElement = screen.getByTestId('risk-score-trend-direction');
      expect(trendElement).toHaveTextContent('-20');
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        data: undefined,
        dataPoints: [],
        isLoading: true,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows loading indicator when isLoading is true', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-trend-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
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
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-trend-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load risk score trends/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      // Data points exist but all have count=0
      const emptyDataPoints = [
        { date: '2026-01-10', avg_score: 0, count: 0 },
        { date: '2026-01-11', avg_score: 0, count: 0 },
      ];

      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        data: {
          data_points: emptyDataPoints,
          start_date: '2026-01-10',
          end_date: '2026-01-11',
        },
        dataPoints: emptyDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows empty state when no events have data', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-trend-empty')).toBeInTheDocument();
      expect(screen.getByText(/No risk score data available/)).toBeInTheDocument();
    });
  });

  describe('hook parameters', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        data: {
          data_points: mockDataPoints,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        dataPoints: mockDataPoints,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('passes correct date range to hook', () => {
      render(<RiskScoreTrendCard dateRange={mockDateRange} />);

      expect(useRiskScoreTrendsModule.useRiskScoreTrends).toHaveBeenCalledWith({
        start_date: '2026-01-10',
        end_date: '2026-01-17',
      });
    });
  });
});
