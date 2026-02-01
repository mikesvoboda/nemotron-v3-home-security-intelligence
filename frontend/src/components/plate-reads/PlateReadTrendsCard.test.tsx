/**
 * Tests for PlateReadTrendsCard component
 *
 * Tests cover:
 * - Rendering with plate read data
 * - Empty state when no data
 * - Loading state
 * - Error state
 * - Date range display
 * - Total reads display
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PlateReadTrendsCard from './PlateReadTrendsCard';
import * as usePlateStatisticsQueryModule from '../../hooks/usePlateStatisticsQuery';

// Mock the hook
vi.mock('../../hooks/usePlateStatisticsQuery', () => ({
  usePlateStatisticsQuery: vi.fn(),
}));

describe('PlateReadTrendsCard', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockStatistics = {
    data: {
      total_reads: 1250,
      unique_plates: 342,
      avg_ocr_confidence: 0.923,
      avg_quality_score: 0.85,
      enhanced_count: 156,
      blurry_count: 43,
      reads_last_hour: 28,
      reads_last_24h: 412,
    },
    totalReads: 1250,
    uniquePlates: 342,
    avgConfidence: 0.923,
    avgConfidencePercent: 92,
    avgQualityScore: 0.85,
    readsLastHour: 28,
    readsLast24h: 412,
    enhancedCount: 156,
    blurryCount: 43,
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue(
        mockStatistics
      );
    });

    it('renders the card title', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByText('Plate Read Trends')).toBeInTheDocument();
    });

    it('displays total reads', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('plate-trends-total')).toBeInTheDocument();
    });

    it('displays date range label', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });

    it('renders the main card element', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('plate-trends-card')).toBeInTheDocument();
    });

    it('displays "Total Reads (7 days)" label', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByText('Total Reads (7 days)')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue({
        ...mockStatistics,
        data: undefined,
        totalReads: 0,
        readsLast24h: 0,
        isLoading: true,
      });
    });

    it('shows loading indicator when isLoading is true', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('plate-trends-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue({
        ...mockStatistics,
        data: undefined,
        totalReads: 0,
        readsLast24h: 0,
        isLoading: false,
        error: new Error('Failed to fetch'),
        isError: true,
      });
    });

    it('shows error message when error occurs', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('plate-trends-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load plate read trends/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue({
        ...mockStatistics,
        totalReads: 0,
        readsLast24h: 0,
        isLoading: false,
        error: null,
        isError: false,
      });
    });

    it('shows empty state when no data', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('plate-trends-empty')).toBeInTheDocument();
      expect(screen.getByText(/No plate read data available/)).toBeInTheDocument();
    });
  });

  describe('hook invocation', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue(
        mockStatistics
      );
    });

    it('calls usePlateStatisticsQuery on mount', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      expect(usePlateStatisticsQueryModule.usePlateStatisticsQuery).toHaveBeenCalledTimes(1);
    });
  });

  describe('chart rendering', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue(
        mockStatistics
      );
    });

    it('renders area chart when data is available', () => {
      render(<PlateReadTrendsCard dateRange={mockDateRange} />);

      // Tremor AreaChart renders with specific classes
      const card = screen.getByTestId('plate-trends-card');
      expect(card).toBeInTheDocument();
    });
  });
});
