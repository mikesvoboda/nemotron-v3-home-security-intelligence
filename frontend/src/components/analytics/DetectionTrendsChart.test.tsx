import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import DetectionTrendsChart from './DetectionTrendsChart';
import * as useDetectionTrendsQueryModule from '../../hooks/useDetectionTrendsQuery';

import type { UseDetectionTrendsQueryReturn } from '../../hooks/useDetectionTrendsQuery';

// Mock the hook
vi.mock('../../hooks/useDetectionTrendsQuery', () => ({
  useDetectionTrendsQuery: vi.fn(),
}));

// Mock Tremor components
vi.mock('@tremor/react', () => ({
  Card: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid={props['data-testid'] as string}>{children}</div>
  ),
  Title: ({ children }: React.PropsWithChildren) => <h3>{children}</h3>,
  Text: ({ children, className }: React.PropsWithChildren<{ className?: string }>) => (
    <span className={className}>{children}</span>
  ),
  AreaChart: (props: Record<string, unknown>) => (
    <div data-testid={props['data-testid'] as string}>AreaChart</div>
  ),
}));

describe('DetectionTrendsChart', () => {
  const mockUseDetectionTrendsQuery = vi.mocked(useDetectionTrendsQueryModule.useDetectionTrendsQuery);

  const defaultProps = {
    startDate: '2026-01-10',
    endDate: '2026-01-16',
  };

  const mockSuccessReturn: UseDetectionTrendsQueryReturn = {
    data: {
      data_points: [
        { date: '2026-01-10', count: 45 },
        { date: '2026-01-11', count: 67 },
        { date: '2026-01-12', count: 32 },
        { date: '2026-01-13', count: 89 },
        { date: '2026-01-14', count: 54 },
        { date: '2026-01-15', count: 0 },
        { date: '2026-01-16', count: 78 },
      ],
      total_detections: 365,
      start_date: '2026-01-10',
      end_date: '2026-01-16',
    },
    dataPoints: [
      { date: '2026-01-10', count: 45 },
      { date: '2026-01-11', count: 67 },
      { date: '2026-01-12', count: 32 },
      { date: '2026-01-13', count: 89 },
      { date: '2026-01-14', count: 54 },
      { date: '2026-01-15', count: 0 },
      { date: '2026-01-16', count: 78 },
    ],
    totalDetections: 365,
    isLoading: false,
    isRefetching: false,
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDetectionTrendsQuery.mockReturnValue(mockSuccessReturn);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the chart with data', () => {
      render(<DetectionTrendsChart {...defaultProps} />);
      expect(screen.getByTestId('detection-trends-chart')).toBeInTheDocument();
      expect(screen.getByText('Detection Trends')).toBeInTheDocument();
    });

    it('displays total detections', () => {
      render(<DetectionTrendsChart {...defaultProps} />);
      expect(screen.getByTestId('detection-trends-total')).toHaveTextContent('365');
    });

    it('displays daily average', () => {
      render(<DetectionTrendsChart {...defaultProps} />);
      expect(screen.getByTestId('detection-trends-average')).toHaveTextContent('52');
    });
  });

  describe('loading state', () => {
    it('shows loading spinner when loading', () => {
      mockUseDetectionTrendsQuery.mockReturnValue({
        ...mockSuccessReturn,
        isLoading: true,
        dataPoints: [],
        totalDetections: 0,
        data: undefined,
      });
      render(<DetectionTrendsChart {...defaultProps} />);
      expect(screen.getByTestId('detection-trends-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message when fetch fails', () => {
      mockUseDetectionTrendsQuery.mockReturnValue({
        ...mockSuccessReturn,
        error: new Error('Network error'),
        isError: true,
        dataPoints: [],
        totalDetections: 0,
        data: undefined,
      });
      render(<DetectionTrendsChart {...defaultProps} />);
      expect(screen.getByTestId('detection-trends-error')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty state when no data', () => {
      mockUseDetectionTrendsQuery.mockReturnValue({
        ...mockSuccessReturn,
        dataPoints: [],
        totalDetections: 0,
        data: undefined,
      });
      render(<DetectionTrendsChart {...defaultProps} />);
      expect(screen.getByTestId('detection-trends-empty')).toBeInTheDocument();
    });
  });
});
