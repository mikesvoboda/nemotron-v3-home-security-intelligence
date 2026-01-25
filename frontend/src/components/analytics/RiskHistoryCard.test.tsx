/**
 * Tests for RiskHistoryCard component
 *
 * Tests cover:
 * - Rendering with risk history data
 * - Empty state when no data
 * - Loading state
 * - Error state
 * - Date range display
 * - Risk level totals display
 */
import { render, screen } from '@testing-library/react';
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
    { date: '2026-01-10', critical: 2, high: 5, medium: 12, low: 25 },
    { date: '2026-01-11', critical: 1, high: 3, medium: 8, low: 20 },
    { date: '2026-01-12', critical: 0, high: 4, medium: 10, low: 18 },
    { date: '2026-01-13', critical: 3, high: 7, medium: 15, low: 30 },
    { date: '2026-01-14', critical: 1, high: 2, medium: 6, low: 15 },
    { date: '2026-01-15', critical: 0, high: 1, medium: 4, low: 10 },
    { date: '2026-01-16', critical: 2, high: 6, medium: 11, low: 22 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
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
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByText('Risk History')).toBeInTheDocument();
    });

    it('displays risk level totals', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      // Critical: 2+1+0+3+1+0+2 = 9
      expect(screen.getByTestId('risk-total-critical')).toHaveTextContent('9');
      // High: 5+3+4+7+2+1+6 = 28
      expect(screen.getByTestId('risk-total-high')).toHaveTextContent('28');
      // Medium: 12+8+10+15+6+4+11 = 66
      expect(screen.getByTestId('risk-total-medium')).toHaveTextContent('66');
      // Low: 25+20+18+30+15+10+22 = 140
      expect(screen.getByTestId('risk-total-low')).toHaveTextContent('140');
    });

    it('displays date range label', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });

    it('renders the main card element', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-history-card')).toBeInTheDocument();
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

    it('shows loading indicator when isLoading is true', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-history-loading')).toBeInTheDocument();
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
        data: {
          data_points: [],
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        dataPoints: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows empty state when no data points', () => {
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-history-empty')).toBeInTheDocument();
      expect(screen.getByText(/No risk data available/)).toBeInTheDocument();
    });
  });

  describe('hook parameters', () => {
    beforeEach(() => {
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
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
      render(<RiskHistoryCard dateRange={mockDateRange} />);

      expect(useRiskHistoryQueryModule.useRiskHistoryQuery).toHaveBeenCalledWith({
        start_date: '2026-01-10',
        end_date: '2026-01-17',
      });
    });
  });
});
