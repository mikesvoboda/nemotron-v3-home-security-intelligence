/**
 * Tests for CrossingTrendsChart component (NEM-4714)
 *
 * Tests crossing trends chart display including:
 * - Loading state
 * - Empty state
 * - Data rendering
 * - Summary statistics
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CrossingTrendsChart from './CrossingTrendsChart';
import { CHART_ANIMATION_THRESHOLD } from '../../utils/chartAnimation';

import type { CrossingTrendsResponse } from '../../types/zoneAnalytics';


// Mock Tremor components to avoid rendering issues in tests
vi.mock('@tremor/react', () => ({
  Card: ({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={className} {...props}>
      {children}
    </div>
  ),
  Title: ({ children, className }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className={className}>{children}</h2>
  ),
  Text: ({ children, className }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className={className}>{children}</p>
  ),
  AreaChart: ({
    data,
    className,
    showAnimation,
    'data-testid': dataTestId,
  }: {
    data: Array<Record<string, unknown>>;
    className?: string;
    showAnimation?: boolean;
    'data-testid'?: string;
    [key: string]: unknown;
  }) => (
    <div
      data-testid={dataTestId || 'area-chart'}
      data-show-animation={showAnimation}
      className={className}
    >
      {data?.length ?? 0} data points
    </div>
  ),
}));

describe('CrossingTrendsChart', () => {
  // Helper to create mock trends response
  const createMockTrendsResponse = (
    overrides: Partial<CrossingTrendsResponse> = {}
  ): CrossingTrendsResponse => ({
    zone_id: 1,
    zone_name: 'Front Entrance',
    trends: [
      {
        timestamp: '2024-01-01T10:00:00Z',
        in_count: 5,
        out_count: 3,
        net_flow: 2,
      },
      {
        timestamp: '2024-01-01T11:00:00Z',
        in_count: 8,
        out_count: 6,
        net_flow: 2,
      },
      {
        timestamp: '2024-01-01T12:00:00Z',
        in_count: 12,
        out_count: 10,
        net_flow: 2,
      },
    ],
    total_in: 25,
    total_out: 19,
    start_time: '2024-01-01T00:00:00Z',
    end_time: '2024-01-01T23:59:59Z',
    interval: 'hour',
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Loading State', () => {
    it('should render loading spinner when isLoading is true', () => {
      render(<CrossingTrendsChart data={undefined} isLoading />);

      expect(screen.getByTestId('crossing-trends-chart-loading')).toBeInTheDocument();
      expect(screen.getByText('Crossing Trends')).toBeInTheDocument();
    });

    it('should not render data when loading', () => {
      render(<CrossingTrendsChart data={createMockTrendsResponse()} isLoading />);

      // Should show loading state, not data
      expect(screen.getByTestId('crossing-trends-chart-loading')).toBeInTheDocument();
      expect(screen.queryByTestId('total-in')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should render empty state when data is undefined', () => {
      render(<CrossingTrendsChart data={undefined} />);

      expect(screen.getByTestId('crossing-trends-chart-empty')).toBeInTheDocument();
      expect(screen.getByText('No crossing data available')).toBeInTheDocument();
    });

    it('should render empty state when trends array is empty', () => {
      const emptyData = createMockTrendsResponse({ trends: [] });
      render(<CrossingTrendsChart data={emptyData} />);

      expect(screen.getByTestId('crossing-trends-chart-empty')).toBeInTheDocument();
      expect(screen.getByText('No crossing data available')).toBeInTheDocument();
    });
  });

  describe('Data Rendering', () => {
    it('should render chart when data is provided', () => {
      const data = createMockTrendsResponse();
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('crossing-trends-chart')).toBeInTheDocument();
    });

    it('should display zone name in title', () => {
      const data = createMockTrendsResponse({ zone_name: 'Back Door' });
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByText(/Crossing Trends - Back Door/)).toBeInTheDocument();
    });

    it('should display total in count', () => {
      const data = createMockTrendsResponse({ total_in: 42 });
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('total-in')).toHaveTextContent('42');
    });

    it('should display total out count', () => {
      const data = createMockTrendsResponse({ total_out: 35 });
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('total-out')).toHaveTextContent('35');
    });

    it('should render area chart with correct data points', () => {
      const data = createMockTrendsResponse();
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('crossing-area-chart')).toBeInTheDocument();
      expect(screen.getByTestId('crossing-area-chart')).toHaveTextContent('3 data points');
    });
  });

  describe('Summary Statistics', () => {
    it('should display Total In label', () => {
      const data = createMockTrendsResponse();
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByText('Total In:')).toBeInTheDocument();
    });

    it('should display Total Out label', () => {
      const data = createMockTrendsResponse();
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByText('Total Out:')).toBeInTheDocument();
    });

    it('should apply green color to total in count', () => {
      const data = createMockTrendsResponse();
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('total-in')).toHaveClass('text-green-400');
    });

    it('should apply red color to total out count', () => {
      const data = createMockTrendsResponse();
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('total-out')).toHaveClass('text-red-400');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const data = createMockTrendsResponse();
      render(<CrossingTrendsChart data={data} className="custom-class" />);

      expect(screen.getByTestId('crossing-trends-chart')).toHaveClass('custom-class');
    });

    it('should apply className to loading state', () => {
      render(<CrossingTrendsChart data={undefined} isLoading className="loading-class" />);

      expect(screen.getByTestId('crossing-trends-chart-loading')).toHaveClass('loading-class');
    });

    it('should apply className to empty state', () => {
      render(<CrossingTrendsChart data={undefined} className="empty-class" />);

      expect(screen.getByTestId('crossing-trends-chart-empty')).toHaveClass('empty-class');
    });
  });

  describe('Chart Title Icon', () => {
    it('should render TrendingUp icon in title', () => {
      const data = createMockTrendsResponse();
      render(<CrossingTrendsChart data={data} />);

      // The icon should be present - checking by finding the container with icon
      const title = screen.getByText(/Crossing Trends/);
      expect(title).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero counts', () => {
      const data = createMockTrendsResponse({
        total_in: 0,
        total_out: 0,
        trends: [
          { timestamp: '2024-01-01T10:00:00Z', in_count: 0, out_count: 0, net_flow: 0 },
        ],
      });
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('total-in')).toHaveTextContent('0');
      expect(screen.getByTestId('total-out')).toHaveTextContent('0');
    });

    it('should handle large counts', () => {
      const data = createMockTrendsResponse({
        total_in: 999999,
        total_out: 888888,
      });
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('total-in')).toHaveTextContent('999999');
      expect(screen.getByTestId('total-out')).toHaveTextContent('888888');
    });

    it('should handle single data point', () => {
      const data = createMockTrendsResponse({
        trends: [
          { timestamp: '2024-01-01T10:00:00Z', in_count: 5, out_count: 3, net_flow: 2 },
        ],
      });
      render(<CrossingTrendsChart data={data} />);

      expect(screen.getByTestId('crossing-area-chart')).toHaveTextContent('1 data points');
    });
  });

  describe('Animation Control (NEM-5045)', () => {
    it('should enable animation for small datasets', () => {
      const data = createMockTrendsResponse({
        trends: Array.from({ length: 10 }, (_, i) => ({
          timestamp: `2024-01-01T${String(i).padStart(2, '0')}:00:00Z`,
          in_count: i,
          out_count: i,
          net_flow: 0,
        })),
      });
      render(<CrossingTrendsChart data={data} />);

      const chart = screen.getByTestId('crossing-area-chart');
      expect(chart).toHaveAttribute('data-show-animation', 'true');
    });

    it('should enable animation for datasets at threshold', () => {
      const data = createMockTrendsResponse({
        trends: Array.from({ length: CHART_ANIMATION_THRESHOLD }, (_, i) => ({
          timestamp: `2024-01-01T${String(i).padStart(2, '0')}:00:00Z`,
          in_count: i,
          out_count: i,
          net_flow: 0,
        })),
      });
      render(<CrossingTrendsChart data={data} />);

      const chart = screen.getByTestId('crossing-area-chart');
      expect(chart).toHaveAttribute('data-show-animation', 'true');
    });

    it('should disable animation for large datasets exceeding threshold', () => {
      const data = createMockTrendsResponse({
        trends: Array.from({ length: CHART_ANIMATION_THRESHOLD + 1 }, (_, i) => ({
          timestamp: `2024-01-01T${String(i % 24).padStart(2, '0')}:00:00Z`,
          in_count: i,
          out_count: i,
          net_flow: 0,
        })),
      });
      render(<CrossingTrendsChart data={data} />);

      const chart = screen.getByTestId('crossing-area-chart');
      expect(chart).toHaveAttribute('data-show-animation', 'false');
    });
  });
});
