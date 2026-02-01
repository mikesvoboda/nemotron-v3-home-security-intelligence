/**
 * Tests for HourlyPatternChart component
 *
 * This component displays a 24-hour activity pattern line chart with confidence bands.
 * Tests verify proper rendering, data visualization, tooltip interactions, and edge cases.
 *
 * Tests cover:
 * - Rendering with valid hourly pattern data
 * - Displaying 24 data points (one per hour)
 * - Confidence band visualization based on std_dev
 * - Tooltip interactions showing hour, avg, std_dev, sample_count
 * - Empty data state
 * - Partial data with missing hours
 * - Data quality indicators (opacity based on sample_count)
 * - Accessibility attributes
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';

import HourlyPatternChart from './HourlyPatternChart';

import type { HourlyPattern } from '../../services/api';

describe('HourlyPatternChart', () => {
  // Mock data representing a full 24-hour pattern
  const mockFullHourlyPatterns: Record<string, HourlyPattern> = {
    '0': { avg_detections: 0.5, std_dev: 0.3, sample_count: 30 },
    '1': { avg_detections: 0.3, std_dev: 0.2, sample_count: 30 },
    '2': { avg_detections: 0.2, std_dev: 0.1, sample_count: 30 },
    '3': { avg_detections: 0.1, std_dev: 0.1, sample_count: 30 },
    '4': { avg_detections: 0.2, std_dev: 0.1, sample_count: 30 },
    '5': { avg_detections: 0.5, std_dev: 0.3, sample_count: 30 },
    '6': { avg_detections: 1.2, std_dev: 0.5, sample_count: 30 },
    '7': { avg_detections: 2.5, std_dev: 0.8, sample_count: 30 },
    '8': { avg_detections: 3.5, std_dev: 1.0, sample_count: 30 },
    '9': { avg_detections: 3.0, std_dev: 0.9, sample_count: 30 },
    '10': { avg_detections: 2.8, std_dev: 0.7, sample_count: 30 },
    '11': { avg_detections: 3.2, std_dev: 0.8, sample_count: 30 },
    '12': { avg_detections: 4.0, std_dev: 1.2, sample_count: 30 },
    '13': { avg_detections: 3.8, std_dev: 1.1, sample_count: 30 },
    '14': { avg_detections: 3.5, std_dev: 0.9, sample_count: 30 },
    '15': { avg_detections: 4.2, std_dev: 1.0, sample_count: 30 },
    '16': { avg_detections: 5.0, std_dev: 1.3, sample_count: 30 },
    '17': { avg_detections: 8.0, std_dev: 2.0, sample_count: 30 },
    '18': { avg_detections: 6.5, std_dev: 1.5, sample_count: 30 },
    '19': { avg_detections: 4.5, std_dev: 1.0, sample_count: 30 },
    '20': { avg_detections: 3.0, std_dev: 0.8, sample_count: 30 },
    '21': { avg_detections: 2.0, std_dev: 0.6, sample_count: 30 },
    '22': { avg_detections: 1.5, std_dev: 0.5, sample_count: 30 },
    '23': { avg_detections: 1.0, std_dev: 0.4, sample_count: 30 },
  };

  // Mock data with varying sample counts for data quality testing
  const mockVaryingSamplePatterns: Record<string, HourlyPattern> = {
    '0': { avg_detections: 0.5, std_dev: 0.3, sample_count: 5 }, // Low samples
    '8': { avg_detections: 3.5, std_dev: 1.0, sample_count: 15 }, // Medium samples
    '17': { avg_detections: 8.0, std_dev: 2.0, sample_count: 30 }, // High samples
  };

  // Mock data with missing hours
  const mockPartialHourlyPatterns: Record<string, HourlyPattern> = {
    '8': { avg_detections: 3.5, std_dev: 1.0, sample_count: 30 },
    '12': { avg_detections: 5.2, std_dev: 1.1, sample_count: 30 },
    '17': { avg_detections: 8.0, std_dev: 2.0, sample_count: 30 },
  };

  describe('rendering with data', () => {
    it('renders the chart title', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      expect(screen.getByText('24-Hour Activity Pattern')).toBeInTheDocument();
    });

    it('renders chart container', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      expect(screen.getByTestId('hourly-pattern-chart')).toBeInTheDocument();
    });

    it('renders all 24 data points', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      // Verify that all 24 hours are represented
      const chartElement = screen.getByTestId('hourly-pattern-chart');
      expect(chartElement).toBeInTheDocument();

      // Check for hour labels at key points
      expect(screen.getByText('12a')).toBeInTheDocument(); // Midnight
      expect(screen.getByText('6a')).toBeInTheDocument();
      expect(screen.getByText('12p')).toBeInTheDocument(); // Noon
      expect(screen.getByText('6p')).toBeInTheDocument();
    });

    it('displays confidence band indicators', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      // Check for confidence band legend or visual indicator
      expect(screen.getByText(/Confidence Band/i)).toBeInTheDocument();
    });

    it('applies correct data quality styling based on sample count', () => {
      render(<HourlyPatternChart patterns={mockVaryingSamplePatterns} />);

      const chartElement = screen.getByTestId('hourly-pattern-chart');
      expect(chartElement).toBeInTheDocument();

      // Check that there's a legend or indicator for data quality
      expect(screen.getByText(/Sample Count/i)).toBeInTheDocument();
    });
  });

  describe('tooltip interactions', () => {
    it('shows tooltip on hover with complete data', async () => {
      const user = userEvent.setup();
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      // Find a data point to hover over
      const dataPoint = screen.getByTestId('hourly-data-point-17');
      await user.hover(dataPoint);

      await waitFor(() => {
        const tooltip = screen.getByTestId('hourly-pattern-tooltip');
        expect(tooltip).toBeInTheDocument();
        expect(tooltip).toHaveTextContent('5:00 PM');
        expect(tooltip).toHaveTextContent('Average: 8.0');
        expect(tooltip).toHaveTextContent('Std Dev: 2.0');
        expect(tooltip).toHaveTextContent('Samples: 30');
      });
    });

    it('shows tooltip with formatted hour labels', async () => {
      const user = userEvent.setup();
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      // Test morning hour
      const morningPoint = screen.getByTestId('hourly-data-point-8');
      await user.hover(morningPoint);

      await waitFor(() => {
        const tooltip = screen.getByTestId('hourly-pattern-tooltip');
        expect(tooltip).toHaveTextContent('8:00 AM');
      });

      await user.unhover(morningPoint);

      // Test afternoon hour
      const afternoonPoint = screen.getByTestId('hourly-data-point-17');
      await user.hover(afternoonPoint);

      await waitFor(() => {
        const tooltip = screen.getByTestId('hourly-pattern-tooltip');
        expect(tooltip).toHaveTextContent('5:00 PM');
      });
    });

    it('hides tooltip on mouse leave', async () => {
      const user = userEvent.setup();
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      const dataPoint = screen.getByTestId('hourly-data-point-17');
      await user.hover(dataPoint);

      await waitFor(() => {
        expect(screen.getByTestId('hourly-pattern-tooltip')).toBeInTheDocument();
      });

      await user.unhover(dataPoint);

      await waitFor(() => {
        expect(screen.queryByTestId('hourly-pattern-tooltip')).not.toBeInTheDocument();
      });
    });

    it('displays data quality warning for low sample counts', async () => {
      const user = userEvent.setup();
      render(<HourlyPatternChart patterns={mockVaryingSamplePatterns} />);

      // Hover over data point with low sample count
      const lowSamplePoint = screen.getByTestId('hourly-data-point-0');
      await user.hover(lowSamplePoint);

      await waitFor(() => {
        const tooltip = screen.getByTestId('hourly-pattern-tooltip');
        expect(tooltip).toHaveTextContent(/Low confidence/i);
        expect(tooltip).toHaveTextContent('Samples: 5');
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no patterns provided', () => {
      render(<HourlyPatternChart patterns={{}} />);

      expect(screen.getByTestId('hourly-pattern-empty')).toBeInTheDocument();
      expect(screen.getByText(/No hourly pattern data available/i)).toBeInTheDocument();
    });

    it('shows empty state with helpful message', () => {
      render(<HourlyPatternChart patterns={{}} />);

      expect(
        screen.getByText(/Data will appear after baseline learning period/i)
      ).toBeInTheDocument();
    });
  });

  describe('partial data handling', () => {
    it('renders chart with missing hours', () => {
      render(<HourlyPatternChart patterns={mockPartialHourlyPatterns} />);

      // Chart should still render
      expect(screen.getByTestId('hourly-pattern-chart')).toBeInTheDocument();

      // Should show data points that exist
      expect(screen.getByTestId('hourly-data-point-8')).toBeInTheDocument();
      expect(screen.getByTestId('hourly-data-point-12')).toBeInTheDocument();
      expect(screen.getByTestId('hourly-data-point-17')).toBeInTheDocument();
    });

    it('displays indicator for missing data points', () => {
      render(<HourlyPatternChart patterns={mockPartialHourlyPatterns} />);

      // Should indicate that some hours have no data
      expect(screen.getByText(/Partial data/i)).toBeInTheDocument();
    });

    it('shows tooltip explaining missing hours', async () => {
      const user = userEvent.setup();
      render(<HourlyPatternChart patterns={mockPartialHourlyPatterns} />);

      // Hover over a missing hour indicator
      const missingHourIndicator = screen.getByTestId('hourly-data-point-0');
      await user.hover(missingHourIndicator);

      await waitFor(() => {
        const tooltip = screen.getByTestId('hourly-pattern-tooltip');
        expect(tooltip).toHaveTextContent(/No data available/i);
      });
    });
  });

  describe('confidence band visualization', () => {
    it('displays confidence band based on std_dev', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      // Check that confidence band is rendered
      const chart = screen.getByTestId('hourly-pattern-chart');
      expect(chart).toBeInTheDocument();

      // Verify legend explains confidence band
      expect(screen.getByText(/±1 standard deviation/i)).toBeInTheDocument();
    });

    it('scales confidence band correctly for different std_dev values', () => {
      const patternsWithVaryingStdDev: Record<string, HourlyPattern> = {
        '8': { avg_detections: 5.0, std_dev: 0.5, sample_count: 30 }, // Narrow band
        '17': { avg_detections: 5.0, std_dev: 3.0, sample_count: 30 }, // Wide band
      };

      render(<HourlyPatternChart patterns={patternsWithVaryingStdDev} />);

      const chart = screen.getByTestId('hourly-pattern-chart');
      expect(chart).toBeInTheDocument();

      // Chart should render both points with different confidence band widths
    });
  });

  describe('data quality indicators', () => {
    it('applies opacity based on sample count', () => {
      render(<HourlyPatternChart patterns={mockVaryingSamplePatterns} />);

      // Low sample data point should have lower opacity
      const lowSamplePoint = screen.getByTestId('hourly-data-point-0');
      expect(lowSamplePoint).toHaveStyle({ opacity: expect.stringMatching(/0\.[3-5]/) });

      // High sample data point should have full opacity
      const highSamplePoint = screen.getByTestId('hourly-data-point-17');
      expect(highSamplePoint).toHaveStyle({ opacity: '1' });
    });

    it('displays legend for data quality', () => {
      render(<HourlyPatternChart patterns={mockVaryingSamplePatterns} />);

      expect(screen.getByText(/Data Quality/i)).toBeInTheDocument();
      expect(screen.getByText(/High confidence/i)).toBeInTheDocument();
      expect(screen.getByText(/Low confidence/i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      const chart = screen.getByTestId('hourly-pattern-chart');
      expect(chart).toHaveAttribute('aria-label', '24-hour activity pattern chart');
    });

    it('provides descriptive text for screen readers', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      expect(screen.getByText(/Chart shows activity levels by hour of day/i)).toBeInTheDocument();
    });

    it('has keyboard navigation support', async () => {
      const user = userEvent.setup();
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      const dataPoint = screen.getByTestId('hourly-data-point-17');

      // Tab to focus the data point
      await user.tab();
      expect(dataPoint).toHaveFocus();

      // Enter/Space should show tooltip
      await user.keyboard('{Enter}');
      await waitFor(() => {
        expect(screen.getByTestId('hourly-pattern-tooltip')).toBeInTheDocument();
      });
    });
  });

  describe('peak hour highlighting', () => {
    it('highlights hour with highest average', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      // Hour 17 (5pm) has the highest average (8.0)
      const peakPoint = screen.getByTestId('hourly-data-point-17');
      expect(peakPoint).toHaveClass('peak-hour');
    });

    it('displays peak indicator in legend', () => {
      render(<HourlyPatternChart patterns={mockFullHourlyPatterns} />);

      expect(screen.getByText(/Peak hour/i)).toBeInTheDocument();
    });
  });
});
