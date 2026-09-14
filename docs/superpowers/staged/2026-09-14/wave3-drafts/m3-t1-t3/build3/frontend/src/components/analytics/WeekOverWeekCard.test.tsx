/**
 * Tests for WeekOverWeekCard component
 *
 * Tests cover:
 * - Rendering with comparison data
 * - Loading state
 * - Error state
 * - Percentage change calculation and display
 * - Visual indicators (arrows, colors) for increases/decreases
 * - High-risk event color logic (more = bad)
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import WeekOverWeekCard from './WeekOverWeekCard';
import * as useDetectionTrendsQueryModule from '../../hooks/useDetectionTrendsQuery';
import * as useRiskHistoryQueryModule from '../../hooks/useRiskHistoryQuery';
import * as useRiskScoreTrendsModule from '../../hooks/useRiskScoreTrends';

// Mock the hooks
vi.mock('../../hooks/useDetectionTrendsQuery', () => ({
  useDetectionTrendsQuery: vi.fn(),
}));

vi.mock('../../hooks/useRiskHistoryQuery', () => ({
  useRiskHistoryQuery: vi.fn(),
}));

vi.mock('../../hooks/useRiskScoreTrends', () => ({
  useRiskScoreTrends: vi.fn(),
}));

describe('WeekOverWeekCard', () => {
  // Mock data for this week (higher values)
  const mockThisWeekDetectionData = {
    data: {
      data_points: [
        { date: '2026-01-20', count: 100 },
        { date: '2026-01-21', count: 110 },
        { date: '2026-01-22', count: 95 },
        { date: '2026-01-23', count: 105 },
        { date: '2026-01-24', count: 120 },
        { date: '2026-01-25', count: 115 },
        { date: '2026-01-26', count: 105 },
      ],
      total_detections: 750,
      start_date: '2026-01-20',
      end_date: '2026-01-26',
    },
    dataPoints: [],
    totalDetections: 750,
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  // Mock data for last week (lower values)
  const mockLastWeekDetectionData = {
    data: {
      data_points: [
        { date: '2026-01-13', count: 80 },
        { date: '2026-01-14', count: 85 },
        { date: '2026-01-15', count: 75 },
        { date: '2026-01-16', count: 90 },
        { date: '2026-01-17', count: 95 },
        { date: '2026-01-18', count: 80 },
        { date: '2026-01-19', count: 95 },
      ],
      total_detections: 600,
      start_date: '2026-01-13',
      end_date: '2026-01-19',
    },
    dataPoints: [],
    totalDetections: 600,
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  // Mock risk history data (this week - more high-risk events)
  const mockThisWeekRiskData = {
    data: {
      data_points: [
        { date: '2026-01-20', low: 40, medium: 20, high: 10, critical: 5 },
        { date: '2026-01-21', low: 45, medium: 22, high: 12, critical: 6 },
        { date: '2026-01-22', low: 38, medium: 18, high: 8, critical: 4 },
        { date: '2026-01-23', low: 42, medium: 21, high: 11, critical: 5 },
        { date: '2026-01-24', low: 50, medium: 25, high: 15, critical: 8 },
        { date: '2026-01-25', low: 48, medium: 24, high: 14, critical: 7 },
        { date: '2026-01-26', low: 43, medium: 20, high: 10, critical: 5 },
      ],
      start_date: '2026-01-20',
      end_date: '2026-01-26',
    },
    dataPoints: [
      { date: '2026-01-20', low: 40, medium: 20, high: 10, critical: 5 },
      { date: '2026-01-21', low: 45, medium: 22, high: 12, critical: 6 },
      { date: '2026-01-22', low: 38, medium: 18, high: 8, critical: 4 },
      { date: '2026-01-23', low: 42, medium: 21, high: 11, critical: 5 },
      { date: '2026-01-24', low: 50, medium: 25, high: 15, critical: 8 },
      { date: '2026-01-25', low: 48, medium: 24, high: 14, critical: 7 },
      { date: '2026-01-26', low: 43, medium: 20, high: 10, critical: 5 },
    ],
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  // Mock risk history data (last week - fewer high-risk events)
  const mockLastWeekRiskData = {
    data: {
      data_points: [
        { date: '2026-01-13', low: 35, medium: 15, high: 6, critical: 3 },
        { date: '2026-01-14', low: 38, medium: 17, high: 7, critical: 3 },
        { date: '2026-01-15', low: 32, medium: 14, high: 5, critical: 2 },
        { date: '2026-01-16', low: 40, medium: 18, high: 8, critical: 4 },
        { date: '2026-01-17', low: 42, medium: 19, high: 8, critical: 4 },
        { date: '2026-01-18', low: 35, medium: 15, high: 6, critical: 3 },
        { date: '2026-01-19', low: 38, medium: 17, high: 7, critical: 3 },
      ],
      start_date: '2026-01-13',
      end_date: '2026-01-19',
    },
    dataPoints: [
      { date: '2026-01-13', low: 35, medium: 15, high: 6, critical: 3 },
      { date: '2026-01-14', low: 38, medium: 17, high: 7, critical: 3 },
      { date: '2026-01-15', low: 32, medium: 14, high: 5, critical: 2 },
      { date: '2026-01-16', low: 40, medium: 18, high: 8, critical: 4 },
      { date: '2026-01-17', low: 42, medium: 19, high: 8, critical: 4 },
      { date: '2026-01-18', low: 35, medium: 15, high: 6, critical: 3 },
      { date: '2026-01-19', low: 38, medium: 17, high: 7, critical: 3 },
    ],
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  // Mock risk score trends (this week - higher scores)
  const mockThisWeekRiskScoreData = {
    data: {
      data_points: [
        { date: '2026-01-20', avg_score: 55, count: 75 },
        { date: '2026-01-21', avg_score: 58, count: 80 },
        { date: '2026-01-22', avg_score: 52, count: 68 },
        { date: '2026-01-23', avg_score: 56, count: 79 },
        { date: '2026-01-24', avg_score: 62, count: 98 },
        { date: '2026-01-25', avg_score: 59, count: 93 },
        { date: '2026-01-26', avg_score: 54, count: 78 },
      ],
      start_date: '2026-01-20',
      end_date: '2026-01-26',
    },
    dataPoints: [
      { date: '2026-01-20', avg_score: 55, count: 75 },
      { date: '2026-01-21', avg_score: 58, count: 80 },
      { date: '2026-01-22', avg_score: 52, count: 68 },
      { date: '2026-01-23', avg_score: 56, count: 79 },
      { date: '2026-01-24', avg_score: 62, count: 98 },
      { date: '2026-01-25', avg_score: 59, count: 93 },
      { date: '2026-01-26', avg_score: 54, count: 78 },
    ],
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  // Mock risk score trends (last week - lower scores)
  const mockLastWeekRiskScoreData = {
    data: {
      data_points: [
        { date: '2026-01-13', avg_score: 42, count: 59 },
        { date: '2026-01-14', avg_score: 45, count: 65 },
        { date: '2026-01-15', avg_score: 39, count: 53 },
        { date: '2026-01-16', avg_score: 46, count: 70 },
        { date: '2026-01-17', avg_score: 48, count: 73 },
        { date: '2026-01-18', avg_score: 41, count: 59 },
        { date: '2026-01-19', avg_score: 44, count: 65 },
      ],
      start_date: '2026-01-13',
      end_date: '2026-01-19',
    },
    dataPoints: [
      { date: '2026-01-13', avg_score: 42, count: 59 },
      { date: '2026-01-14', avg_score: 45, count: 65 },
      { date: '2026-01-15', avg_score: 39, count: 53 },
      { date: '2026-01-16', avg_score: 46, count: 70 },
      { date: '2026-01-17', avg_score: 48, count: 73 },
      { date: '2026-01-18', avg_score: 41, count: 59 },
      { date: '2026-01-19', avg_score: 44, count: 65 },
    ],
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock Date to ensure consistent date calculations
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-01-26T12:00:00Z'));
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  /**
   * Sets up standard mock returns for hooks with loaded data.
   * Returns this week data for the first call, last week data for the second call.
   */
  function setupMocksWithData() {
    let detectionCallCount = 0;
    vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockImplementation(() => {
      detectionCallCount++;
      return detectionCallCount === 1 ? mockThisWeekDetectionData : mockLastWeekDetectionData;
    });

    let riskHistoryCallCount = 0;
    vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockImplementation(() => {
      riskHistoryCallCount++;
      return riskHistoryCallCount === 1 ? mockThisWeekRiskData : mockLastWeekRiskData;
    });

    let riskScoreCallCount = 0;
    vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockImplementation(() => {
      riskScoreCallCount++;
      return riskScoreCallCount === 1 ? mockThisWeekRiskScoreData : mockLastWeekRiskScoreData;
    });
  }

  describe('rendering with data', () => {
    beforeEach(() => {
      setupMocksWithData();
    });

    it('renders the card title', () => {
      render(<WeekOverWeekCard />);

      expect(screen.getByText('Week over Week')).toBeInTheDocument();
    });

    it('renders the main card element', () => {
      render(<WeekOverWeekCard />);

      expect(screen.getByTestId('week-over-week-card')).toBeInTheDocument();
    });

    it('displays total detections comparison', () => {
      render(<WeekOverWeekCard />);

      // Should show this week and last week values
      expect(screen.getByTestId('detections-this-week')).toHaveTextContent('750');
      expect(screen.getByTestId('detections-last-week')).toHaveTextContent('600');
    });

    it('displays high-risk events comparison', () => {
      render(<WeekOverWeekCard />);

      // High-risk = high + critical
      // This week: (10+12+8+11+15+14+10) + (5+6+4+5+8+7+5) = 80 + 40 = 120
      // Last week: (6+7+5+8+8+6+7) + (3+3+2+4+4+3+3) = 47 + 22 = 69
      expect(screen.getByTestId('high-risk-this-week')).toHaveTextContent('120');
      expect(screen.getByTestId('high-risk-last-week')).toHaveTextContent('69');
    });

    it('displays average risk score comparison', () => {
      render(<WeekOverWeekCard />);

      // Average risk score (weighted by count)
      expect(screen.getByTestId('avg-risk-this-week')).toBeInTheDocument();
      expect(screen.getByTestId('avg-risk-last-week')).toBeInTheDocument();
    });

    it('displays percentage change for detections', () => {
      render(<WeekOverWeekCard />);

      // (750 - 600) / 600 * 100 = 25%
      expect(screen.getByTestId('detections-change')).toHaveTextContent('25.0%');
    });

    it('displays percentage change for high-risk events', () => {
      render(<WeekOverWeekCard />);

      // (120 - 69) / 69 * 100 = 73.9%
      const changeElement = screen.getByTestId('high-risk-change');
      expect(changeElement).toHaveTextContent(/73\.9%/);
    });
  });

  describe('visual indicators', () => {
    beforeEach(() => {
      setupMocksWithData();
    });

    it('shows green indicator for detections increase (more data is good)', () => {
      render(<WeekOverWeekCard />);

      const indicator = screen.getByTestId('detections-indicator');
      expect(indicator).toHaveClass('text-emerald-400');
    });

    it('shows red indicator for high-risk events increase (more high-risk is bad)', () => {
      render(<WeekOverWeekCard />);

      const indicator = screen.getByTestId('high-risk-indicator');
      expect(indicator).toHaveClass('text-red-400');
    });

    it('shows red indicator for risk score increase (higher risk is bad)', () => {
      render(<WeekOverWeekCard />);

      const indicator = screen.getByTestId('avg-risk-indicator');
      expect(indicator).toHaveClass('text-red-400');
    });

    it('shows up arrow for increases', () => {
      render(<WeekOverWeekCard />);

      // All metrics are increasing in our mock data
      const detectionsIndicator = screen.getByTestId('detections-indicator');
      expect(detectionsIndicator.querySelector('svg')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading indicator when any data is loading', () => {
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockReturnValue({
        ...mockThisWeekDetectionData,
        isLoading: true,
      });
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        ...mockThisWeekRiskData,
        isLoading: false,
      });
      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        ...mockThisWeekRiskScoreData,
        isLoading: false,
      });

      render(<WeekOverWeekCard />);

      expect(screen.getByTestId('week-over-week-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message when any query fails', () => {
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockReturnValue({
        ...mockThisWeekDetectionData,
        isLoading: false,
        error: new Error('Failed to fetch'),
        isError: true,
      });
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        ...mockThisWeekRiskData,
        isLoading: false,
      });
      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        ...mockThisWeekRiskScoreData,
        isLoading: false,
      });

      render(<WeekOverWeekCard />);

      expect(screen.getByTestId('week-over-week-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load comparison data/)).toBeInTheDocument();
    });
  });

  describe('empty/zero data handling', () => {
    it('handles zero previous week data gracefully (avoids division by zero)', () => {
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockImplementation(
        (params) => {
          if (params.start_date === '2026-01-20') {
            return mockThisWeekDetectionData;
          }
          return {
            ...mockLastWeekDetectionData,
            totalDetections: 0,
            data: { ...mockLastWeekDetectionData.data, total_detections: 0 },
          };
        }
      );
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockReturnValue({
        ...mockThisWeekRiskData,
        dataPoints: [],
      });
      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockReturnValue({
        ...mockThisWeekRiskScoreData,
        dataPoints: [],
      });

      render(<WeekOverWeekCard />);

      // Should not crash, should show N/A or similar for percentage
      expect(screen.getByTestId('week-over-week-card')).toBeInTheDocument();
    });
  });

  describe('date range calculation', () => {
    it('calls hooks with correct date ranges', () => {
      setupMocksWithData();
      render(<WeekOverWeekCard />);

      // Current date is mocked to 2026-01-26
      // This week: 2026-01-20 to 2026-01-26 (last 7 days)
      // Last week: 2026-01-13 to 2026-01-19 (7-14 days ago)
      expect(useDetectionTrendsQueryModule.useDetectionTrendsQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          start_date: '2026-01-20',
          end_date: '2026-01-26',
        })
      );
      expect(useDetectionTrendsQueryModule.useDetectionTrendsQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          start_date: '2026-01-13',
          end_date: '2026-01-19',
        })
      );
    });
  });

  describe('decrease scenarios', () => {
    it('shows green for high-risk decrease (fewer high-risk is good)', () => {
      // Swap the data so this week has fewer high-risk events
      let riskHistoryCallCount = 0;
      vi.mocked(useRiskHistoryQueryModule.useRiskHistoryQuery).mockImplementation(() => {
        riskHistoryCallCount++;
        // Return last week data first (fewer events), this week data second (more events)
        // This simulates a decrease in high-risk events
        return riskHistoryCallCount === 1 ? mockLastWeekRiskData : mockThisWeekRiskData;
      });

      let detectionCallCount = 0;
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockImplementation(() => {
        detectionCallCount++;
        return detectionCallCount === 1 ? mockLastWeekDetectionData : mockThisWeekDetectionData;
      });

      let riskScoreCallCount = 0;
      vi.mocked(useRiskScoreTrendsModule.useRiskScoreTrends).mockImplementation(() => {
        riskScoreCallCount++;
        return riskScoreCallCount === 1 ? mockLastWeekRiskScoreData : mockThisWeekRiskScoreData;
      });

      render(<WeekOverWeekCard />);

      // High-risk decreased, so indicator should be green
      const indicator = screen.getByTestId('high-risk-indicator');
      expect(indicator).toHaveClass('text-emerald-400');
    });
  });
});
