/**
 * Tests for TrendSparklines component.
 *
 * Tests the sparkline visualization component that displays:
 * - Event count trends
 * - Average risk trends
 * - High-risk count trends
 *
 * Each metric includes:
 * - Mini sparkline chart
 * - Baseline comparison
 * - Deviation indicator (e.g., "40% above baseline")
 *
 * @see NEM-5406/5407/5408/5409 - Feature 5: Trend Comparison Sparklines
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import TrendSparklines from './TrendSparklines';

import type { TrendsData, TrendMetric } from '@/types/trends';

// Helper to create a valid TrendMetric
function createTrendMetric(overrides: Partial<TrendMetric> = {}): TrendMetric {
  return {
    values: [5, 8, 3, 6, 10, 4, 7, 9, 2, 5, 6, 8],
    baseline: 6.0,
    deviationPct: 33.3,
    ...overrides,
  };
}

// Helper to create valid TrendsData
function createTrendsData(overrides: Partial<TrendsData> = {}): TrendsData {
  return {
    eventCount: createTrendMetric(),
    avgRisk: createTrendMetric({
      values: [45, 52, 38, 60, 72, 40, 55, 65, 35, 48, 50, 58],
      baseline: 50.0,
      deviationPct: 16.0,
    }),
    highRiskCount: createTrendMetric({
      values: [1, 2, 0, 1, 3, 1, 2, 2, 0, 1, 1, 2],
      baseline: 1.3,
      deviationPct: 53.8,
    }),
    ...overrides,
  };
}

describe('TrendSparklines', () => {
  describe('Rendering', () => {
    it('renders without crashing', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} />);
      expect(screen.getByTestId('trend-sparklines')).toBeInTheDocument();
    });

    it('renders all three sparkline cards', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} />);

      expect(screen.getByTestId('trend-event-count')).toBeInTheDocument();
      expect(screen.getByTestId('trend-avg-risk')).toBeInTheDocument();
      expect(screen.getByTestId('trend-high-risk')).toBeInTheDocument();
    });

    it('renders labels for each metric', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} />);

      expect(screen.getByText('Event Count')).toBeInTheDocument();
      expect(screen.getByText('Avg Risk')).toBeInTheDocument();
      expect(screen.getByText('High Risk')).toBeInTheDocument();
    });

    it('renders sparkline SVGs for each metric', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} />);

      expect(screen.getByTestId('sparkline-event-count')).toBeInTheDocument();
      expect(screen.getByTestId('sparkline-avg-risk')).toBeInTheDocument();
      expect(screen.getByTestId('sparkline-high-risk')).toBeInTheDocument();
    });
  });

  describe('Deviation Indicators', () => {
    it('displays positive deviation with up arrow', () => {
      const data = createTrendsData({
        eventCount: createTrendMetric({ deviationPct: 40.0 }),
      });
      render(<TrendSparklines data={data} />);

      const indicator = screen.getByTestId('deviation-event-count');
      expect(indicator).toHaveTextContent('40%');
      expect(indicator).toHaveTextContent('above');
    });

    it('displays negative deviation with down arrow', () => {
      const data = createTrendsData({
        eventCount: createTrendMetric({ deviationPct: -20.0 }),
      });
      render(<TrendSparklines data={data} />);

      const indicator = screen.getByTestId('deviation-event-count');
      expect(indicator).toHaveTextContent('20%');
      expect(indicator).toHaveTextContent('below');
    });

    it('displays zero deviation as neutral', () => {
      const data = createTrendsData({
        eventCount: createTrendMetric({ deviationPct: 0 }),
      });
      render(<TrendSparklines data={data} />);

      const indicator = screen.getByTestId('deviation-event-count');
      expect(indicator).toHaveTextContent('0%');
    });

    it('rounds deviation percentages to whole numbers', () => {
      const data = createTrendsData({
        eventCount: createTrendMetric({ deviationPct: 33.7 }),
      });
      render(<TrendSparklines data={data} />);

      const indicator = screen.getByTestId('deviation-event-count');
      expect(indicator).toHaveTextContent('34%');
    });
  });

  describe('Sparkline Visualization', () => {
    it('generates correct SVG path for sparkline', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} />);

      const sparkline = screen.getByTestId('sparkline-event-count');
      const paths = sparkline.querySelectorAll('path');

      // Should have line path
      expect(paths.length).toBeGreaterThanOrEqual(1);
    });

    it('handles empty values array gracefully', () => {
      const data = createTrendsData({
        eventCount: createTrendMetric({ values: [] }),
      });
      render(<TrendSparklines data={data} />);

      // Should render without errors
      expect(screen.getByTestId('trend-event-count')).toBeInTheDocument();
    });

    it('handles single value in array', () => {
      const data = createTrendsData({
        eventCount: createTrendMetric({ values: [5] }),
      });
      render(<TrendSparklines data={data} />);

      // Should render without errors
      expect(screen.getByTestId('trend-event-count')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading skeleton when isLoading is true', () => {
      render(<TrendSparklines data={null} isLoading={true} />);

      expect(screen.getByTestId('trend-sparklines-loading')).toBeInTheDocument();
    });

    it('shows loading indicator for each metric', () => {
      render(<TrendSparklines data={null} isLoading={true} />);

      const skeletons = screen.getAllByTestId(/skeleton/);
      expect(skeletons.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('Error State', () => {
    it('shows error message when error is provided', () => {
      const error = new Error('Failed to fetch trends');
      render(<TrendSparklines data={null} error={error} />);

      expect(screen.getByTestId('trend-sparklines-error')).toBeInTheDocument();
      expect(screen.getByText(/failed to load trend data/i)).toBeInTheDocument();
    });

    it('shows retry button on error', () => {
      const error = new Error('Failed to fetch trends');
      const onRetry = vi.fn();
      render(<TrendSparklines data={null} error={error} onRetry={onRetry} />);

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state when data is null and not loading', () => {
      render(<TrendSparklines data={null} />);

      expect(screen.getByTestId('trend-sparklines-empty')).toBeInTheDocument();
    });

    it('shows helpful message in empty state', () => {
      render(<TrendSparklines data={null} />);

      expect(screen.getByText(/no trend data available/i)).toBeInTheDocument();
    });
  });

  describe('Color Coding', () => {
    it('uses green color for positive metrics (below baseline for risk)', () => {
      const data = createTrendsData({
        avgRisk: createTrendMetric({ deviationPct: -20.0 }),
      });
      render(<TrendSparklines data={data} />);

      const indicator = screen.getByTestId('deviation-avg-risk');
      // Risk below baseline should be green (good)
      expect(indicator).toHaveClass(/text-green/);
    });

    it('uses red color for negative metrics (above baseline for risk)', () => {
      const data = createTrendsData({
        avgRisk: createTrendMetric({ deviationPct: 40.0 }),
      });
      render(<TrendSparklines data={data} />);

      const indicator = screen.getByTestId('deviation-avg-risk');
      // Risk above baseline should be red (bad)
      expect(indicator).toHaveClass(/text-red/);
    });

    it('uses neutral color for zero deviation', () => {
      const data = createTrendsData({
        eventCount: createTrendMetric({ deviationPct: 0 }),
      });
      render(<TrendSparklines data={data} />);

      const indicator = screen.getByTestId('deviation-event-count');
      expect(indicator).toHaveClass(/text-gray/);
    });
  });

  describe('Accessibility', () => {
    it('has aria-label for sparkline container', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} />);

      const container = screen.getByTestId('trend-sparklines');
      expect(container).toHaveAttribute('aria-label', 'Trend comparison sparklines');
    });

    it('sparklines are hidden from screen readers (decorative)', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} />);

      const sparkline = screen.getByTestId('sparkline-event-count');
      expect(sparkline).toHaveAttribute('aria-hidden', 'true');
    });

    it('deviation indicators have screen reader text', () => {
      const data = createTrendsData({
        eventCount: createTrendMetric({ deviationPct: 40.0 }),
      });
      render(<TrendSparklines data={data} />);

      // Should have accessible text describing the deviation
      expect(screen.getByText(/40% above baseline/)).toBeInTheDocument();
    });
  });

  describe('Responsive Design', () => {
    it('renders in a responsive grid layout', () => {
      const data = createTrendsData();
      const { container } = render(<TrendSparklines data={data} />);

      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('Props', () => {
    it('applies custom className', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} className="custom-class" />);

      expect(screen.getByTestId('trend-sparklines')).toHaveClass('custom-class');
    });

    it('renders compact variant when compact prop is true', () => {
      const data = createTrendsData();
      render(<TrendSparklines data={data} compact />);

      // Compact variant should have smaller dimensions
      const container = screen.getByTestId('trend-sparklines');
      expect(container).toHaveClass('gap-2');
    });
  });
});

describe('generateSparklinePath', () => {
  // Import the helper function for isolated testing
  it('returns empty string for empty data', async () => {
    const { generateSparklinePath } = await import('./TrendSparklines');
    const path = generateSparklinePath([], 100, 24);
    expect(path).toBe('');
  });

  it('generates valid SVG path for data', async () => {
    const { generateSparklinePath } = await import('./TrendSparklines');
    const data = [10, 20, 30, 40, 50];
    const path = generateSparklinePath(data, 100, 24);

    // Path should start with M (moveto)
    expect(path).toMatch(/^M /);
    // Path should contain L (lineto) commands
    expect(path).toContain(' L ');
  });

  it('handles single data point', async () => {
    const { generateSparklinePath } = await import('./TrendSparklines');
    const path = generateSparklinePath([50], 100, 24);

    // Should return a valid path even for single point
    expect(path).toMatch(/^M /);
  });

  it('handles zero values', async () => {
    const { generateSparklinePath } = await import('./TrendSparklines');
    const path = generateSparklinePath([0, 0, 0], 100, 24);

    // Should return valid path
    expect(path).toBeTruthy();
  });
});
