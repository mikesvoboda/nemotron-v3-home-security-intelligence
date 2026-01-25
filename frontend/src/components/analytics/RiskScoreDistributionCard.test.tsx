/**
 * Tests for RiskScoreDistributionCard component
 *
 * Tests cover:
 * - Rendering with distribution data
 * - Empty state when no data
 * - Loading state
 * - Error state
 * - Date range display
 * - Total events display
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import RiskScoreDistributionCard from './RiskScoreDistributionCard';
import * as useRiskScoreDistributionModule from '../../hooks/useRiskScoreDistribution';

// Mock the hook
vi.mock('../../hooks/useRiskScoreDistribution', () => ({
  useRiskScoreDistribution: vi.fn(),
}));

describe('RiskScoreDistributionCard', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockBuckets = [
    { min_score: 0, max_score: 10, count: 5 },
    { min_score: 10, max_score: 20, count: 8 },
    { min_score: 20, max_score: 30, count: 12 },
    { min_score: 30, max_score: 40, count: 6 },
    { min_score: 40, max_score: 50, count: 4 },
    { min_score: 50, max_score: 60, count: 3 },
    { min_score: 60, max_score: 70, count: 2 },
    { min_score: 70, max_score: 80, count: 1 },
    { min_score: 80, max_score: 90, count: 1 },
    { min_score: 90, max_score: 100, count: 0 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreDistributionModule.useRiskScoreDistribution).mockReturnValue({
        data: {
          buckets: mockBuckets,
          total_events: 42,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
          bucket_size: 10,
        },
        buckets: mockBuckets,
        totalEvents: 42,
        bucketSize: 10,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('renders the card title', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByText('Risk Score Distribution')).toBeInTheDocument();
    });

    it('displays total events', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-distribution-total')).toHaveTextContent('42');
    });

    it('displays date range label', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });

    it('renders the main card element', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-distribution-card')).toBeInTheDocument();
    });

    it('displays risk level legend', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Low \(0-29\)/)).toBeInTheDocument();
      expect(screen.getByText(/Medium \(30-59\)/)).toBeInTheDocument();
      expect(screen.getByText(/High \(60-84\)/)).toBeInTheDocument();
      expect(screen.getByText(/Critical \(85\+\)/)).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreDistributionModule.useRiskScoreDistribution).mockReturnValue({
        data: undefined,
        buckets: [],
        totalEvents: 0,
        bucketSize: 10,
        isLoading: true,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows loading indicator when isLoading is true', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-distribution-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreDistributionModule.useRiskScoreDistribution).mockReturnValue({
        data: undefined,
        buckets: [],
        totalEvents: 0,
        bucketSize: 10,
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to fetch'),
        isError: true,
        refetch: vi.fn(),
      });
    });

    it('shows error message when error occurs', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-distribution-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load risk score distribution/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreDistributionModule.useRiskScoreDistribution).mockReturnValue({
        data: {
          buckets: [],
          total_events: 0,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
          bucket_size: 10,
        },
        buckets: [],
        totalEvents: 0,
        bucketSize: 10,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows empty state when no events', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('risk-score-distribution-empty')).toBeInTheDocument();
      expect(screen.getByText(/No risk score data available/)).toBeInTheDocument();
    });
  });

  describe('hook parameters', () => {
    beforeEach(() => {
      vi.mocked(useRiskScoreDistributionModule.useRiskScoreDistribution).mockReturnValue({
        data: {
          buckets: mockBuckets,
          total_events: 42,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
          bucket_size: 10,
        },
        buckets: mockBuckets,
        totalEvents: 42,
        bucketSize: 10,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('passes correct date range to hook', () => {
      render(<RiskScoreDistributionCard dateRange={mockDateRange} />);

      expect(useRiskScoreDistributionModule.useRiskScoreDistribution).toHaveBeenCalledWith({
        start_date: '2026-01-10',
        end_date: '2026-01-17',
      });
    });
  });
});
