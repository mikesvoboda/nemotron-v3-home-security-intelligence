/**
 * Tests for PlateStatisticsCards component
 *
 * Tests cover:
 * - Rendering with statistics data
 * - Loading state
 * - Error state
 * - All statistic cards display correctly
 * - Comparison badge displays correctly
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PlateStatisticsCards from './PlateStatisticsCards';
import * as usePlateStatisticsQueryModule from '../../hooks/usePlateStatisticsQuery';

// Mock the hook
vi.mock('../../hooks/usePlateStatisticsQuery', () => ({
  usePlateStatisticsQuery: vi.fn(),
}));

describe('PlateStatisticsCards', () => {
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

    it('renders the statistics cards container', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('plate-statistics-cards')).toBeInTheDocument();
    });

    it('displays total plate reads', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('stat-total-reads')).toBeInTheDocument();
      expect(screen.getByText('Total Plate Reads')).toBeInTheDocument();
      expect(screen.getByText('1,250')).toBeInTheDocument();
    });

    it('displays 24h comparison badge for total reads', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByText(/412/)).toBeInTheDocument();
      expect(screen.getByText(/last 24h/)).toBeInTheDocument();
    });

    it('displays unique plates count', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('stat-unique-plates')).toBeInTheDocument();
      expect(screen.getByText('Unique Plates')).toBeInTheDocument();
      expect(screen.getByText('342')).toBeInTheDocument();
    });

    it('displays average OCR confidence as percentage', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('stat-avg-confidence')).toBeInTheDocument();
      expect(screen.getByText('Avg OCR Confidence')).toBeInTheDocument();
      expect(screen.getByText('92%')).toBeInTheDocument();
    });

    it('displays reads last hour', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('stat-reads-last-hour')).toBeInTheDocument();
      expect(screen.getByText('Reads Last Hour')).toBeInTheDocument();
      expect(screen.getByText('28')).toBeInTheDocument();
    });

    it('displays enhanced count', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('stat-enhanced-count')).toBeInTheDocument();
      expect(screen.getByText('Enhanced (Low-Light)')).toBeInTheDocument();
      expect(screen.getByText('156')).toBeInTheDocument();
    });

    it('displays blurry count', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('stat-blurry-count')).toBeInTheDocument();
      expect(screen.getByText('Blurry Reads')).toBeInTheDocument();
      expect(screen.getByText('43')).toBeInTheDocument();
    });

    it('renders all 6 stat cards', () => {
      render(<PlateStatisticsCards />);

      const cards = screen.getAllByTestId(/^stat-/);
      expect(cards).toHaveLength(6);
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue({
        ...mockStatistics,
        data: undefined,
        totalReads: 0,
        uniquePlates: 0,
        avgConfidence: 0,
        avgConfidencePercent: 0,
        readsLastHour: 0,
        readsLast24h: 0,
        enhancedCount: 0,
        blurryCount: 0,
        avgQualityScore: 0,
        isLoading: true,
      });
    });

    it('shows loading indicator when isLoading is true', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('plate-statistics-loading')).toBeInTheDocument();
    });

    it('shows 6 skeleton cards during loading', () => {
      render(<PlateStatisticsCards />);

      const loadingContainer = screen.getByTestId('plate-statistics-loading');
      const cards = loadingContainer.querySelectorAll('.tremor-Card-root');
      expect(cards).toHaveLength(6);
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue({
        ...mockStatistics,
        data: undefined,
        totalReads: 0,
        uniquePlates: 0,
        avgConfidence: 0,
        avgConfidencePercent: 0,
        readsLastHour: 0,
        readsLast24h: 0,
        enhancedCount: 0,
        blurryCount: 0,
        avgQualityScore: 0,
        isLoading: false,
        error: new Error('Failed to fetch'),
        isError: true,
      });
    });

    it('shows error message when error occurs', () => {
      render(<PlateStatisticsCards />);

      expect(screen.getByTestId('plate-statistics-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load plate statistics/)).toBeInTheDocument();
    });
  });

  describe('number formatting', () => {
    it('formats large numbers with commas', () => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue({
        ...mockStatistics,
        totalReads: 12500,
        uniquePlates: 3420,
        enhancedCount: 1560,
      });

      render(<PlateStatisticsCards />);

      expect(screen.getByText('12,500')).toBeInTheDocument();
      expect(screen.getByText('3,420')).toBeInTheDocument();
      expect(screen.getByText('1,560')).toBeInTheDocument();
    });
  });

  describe('hook invocation', () => {
    beforeEach(() => {
      vi.mocked(usePlateStatisticsQueryModule.usePlateStatisticsQuery).mockReturnValue(
        mockStatistics
      );
    });

    it('calls usePlateStatisticsQuery on mount', () => {
      render(<PlateStatisticsCards />);

      expect(usePlateStatisticsQueryModule.usePlateStatisticsQuery).toHaveBeenCalledTimes(1);
    });
  });
});
