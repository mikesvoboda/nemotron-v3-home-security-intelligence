/**
 * Tests for DetectionTrendsCard component
 *
 * Tests cover:
 * - Rendering with detection trend data
 * - Empty state when no data
 * - Loading state
 * - Error state
 * - Date range display
 * - Total detections display
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import DetectionTrendsCard from './DetectionTrendsCard';
import * as useDetectionTrendsQueryModule from '../../hooks/useDetectionTrendsQuery';

// Mock the hook
vi.mock('../../hooks/useDetectionTrendsQuery', () => ({
  useDetectionTrendsQuery: vi.fn(),
}));

describe('DetectionTrendsCard', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockDataPoints = [
    { date: '2026-01-10', count: 45 },
    { date: '2026-01-11', count: 62 },
    { date: '2026-01-12', count: 38 },
    { date: '2026-01-13', count: 71 },
    { date: '2026-01-14', count: 55 },
    { date: '2026-01-15', count: 48 },
    { date: '2026-01-16', count: 67 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockReturnValue({
        data: {
          data_points: mockDataPoints,
          total_detections: 386,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        dataPoints: mockDataPoints,
        totalDetections: 386,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('renders the card title', () => {
      render(<DetectionTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByText('Detection Trends')).toBeInTheDocument();
    });

    it('displays total detections', () => {
      render(<DetectionTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('detection-trends-total')).toHaveTextContent('386');
    });

    it('displays date range label', () => {
      render(<DetectionTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByText(/Jan 10 - Jan 17/)).toBeInTheDocument();
    });

    it('renders the main card element', () => {
      render(<DetectionTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('detection-trends-card')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockReturnValue({
        data: undefined,
        dataPoints: [],
        totalDetections: 0,
        isLoading: true,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows loading indicator when isLoading is true', () => {
      render(<DetectionTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('detection-trends-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockReturnValue({
        data: undefined,
        dataPoints: [],
        totalDetections: 0,
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to fetch'),
        isError: true,
        refetch: vi.fn(),
      });
    });

    it('shows error message when error occurs', () => {
      render(<DetectionTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('detection-trends-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load detection trends/)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockReturnValue({
        data: {
          data_points: [],
          total_detections: 0,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        dataPoints: [],
        totalDetections: 0,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('shows empty state when no data points', () => {
      render(<DetectionTrendsCard dateRange={mockDateRange} />);

      expect(screen.getByTestId('detection-trends-empty')).toBeInTheDocument();
      expect(screen.getByText(/No detection data available/)).toBeInTheDocument();
    });
  });

  describe('hook parameters', () => {
    beforeEach(() => {
      vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery).mockReturnValue({
        data: {
          data_points: mockDataPoints,
          total_detections: 386,
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        },
        dataPoints: mockDataPoints,
        totalDetections: 386,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
      });
    });

    it('passes correct date range to hook', () => {
      render(<DetectionTrendsCard dateRange={mockDateRange} />);

      expect(useDetectionTrendsQueryModule.useDetectionTrendsQuery).toHaveBeenCalledWith({
        start_date: '2026-01-10',
        end_date: '2026-01-17',
      });
    });
  });
});
