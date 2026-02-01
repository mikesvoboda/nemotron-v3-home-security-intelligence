/**
 * Tests for DailyPatternChart component
 *
 * This component displays a 7-day (Monday-Sunday) activity pattern bar chart.
 * Tests verify proper rendering, data visualization, peak hour indicators, and edge cases.
 *
 * Tests cover:
 * - Rendering with valid daily pattern data
 * - Displaying 7 bars (Mon-Sun)
 * - Peak hour indicator within each bar
 * - Tooltip interactions showing day, avg, peak_hour, total_samples
 * - Empty data state
 * - Partial week data
 * - Color intensity varying with activity level
 * - Day name formatting and ordering
 * - Accessibility attributes
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';

import DailyPatternChart from './DailyPatternChart';

import type { DailyPattern } from '../../services/api';

describe('DailyPatternChart', () => {
  // Mock data representing a full week
  const mockFullWeekPatterns: Record<string, DailyPattern> = {
    monday: { avg_detections: 45.0, peak_hour: 17, total_samples: 168 },
    tuesday: { avg_detections: 42.0, peak_hour: 18, total_samples: 168 },
    wednesday: { avg_detections: 48.5, peak_hour: 17, total_samples: 168 },
    thursday: { avg_detections: 50.0, peak_hour: 16, total_samples: 168 },
    friday: { avg_detections: 65.0, peak_hour: 18, total_samples: 168 },
    saturday: { avg_detections: 38.0, peak_hour: 12, total_samples: 168 },
    sunday: { avg_detections: 30.0, peak_hour: 11, total_samples: 168 },
  };

  // Mock data with partial week
  const mockPartialWeekPatterns: Record<string, DailyPattern> = {
    monday: { avg_detections: 45.0, peak_hour: 17, total_samples: 24 },
    wednesday: { avg_detections: 48.5, peak_hour: 17, total_samples: 24 },
    friday: { avg_detections: 65.0, peak_hour: 18, total_samples: 24 },
  };

  // Mock data with varying activity levels
  const mockVaryingActivityPatterns: Record<string, DailyPattern> = {
    monday: { avg_detections: 10.0, peak_hour: 17, total_samples: 168 }, // Low
    tuesday: { avg_detections: 50.0, peak_hour: 18, total_samples: 168 }, // Medium
    wednesday: { avg_detections: 100.0, peak_hour: 17, total_samples: 168 }, // High
  };

  describe('rendering with data', () => {
    it('renders the chart title', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      expect(screen.getByText('Weekly Activity Pattern')).toBeInTheDocument();
    });

    it('renders chart container', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      expect(screen.getByTestId('daily-pattern-chart')).toBeInTheDocument();
    });

    it('renders all 7 day bars', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      // Check for all day labels
      expect(screen.getByText('Mon')).toBeInTheDocument();
      expect(screen.getByText('Tue')).toBeInTheDocument();
      expect(screen.getByText('Wed')).toBeInTheDocument();
      expect(screen.getByText('Thu')).toBeInTheDocument();
      expect(screen.getByText('Fri')).toBeInTheDocument();
      expect(screen.getByText('Sat')).toBeInTheDocument();
      expect(screen.getByText('Sun')).toBeInTheDocument();
    });

    it('displays bars in correct order (Monday to Sunday)', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      screen.getByTestId('daily-pattern-chart');
      const dayLabels = screen.getAllByTestId(/^daily-bar-/);

      // Verify day order
      expect(dayLabels[0]).toHaveAttribute('data-day', 'monday');
      expect(dayLabels[1]).toHaveAttribute('data-day', 'tuesday');
      expect(dayLabels[2]).toHaveAttribute('data-day', 'wednesday');
      expect(dayLabels[3]).toHaveAttribute('data-day', 'thursday');
      expect(dayLabels[4]).toHaveAttribute('data-day', 'friday');
      expect(dayLabels[5]).toHaveAttribute('data-day', 'saturday');
      expect(dayLabels[6]).toHaveAttribute('data-day', 'sunday');
    });

    it('displays peak hour indicator on each bar', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      // Check for peak hour indicators
      expect(screen.getByTestId('peak-indicator-monday')).toBeInTheDocument();
      expect(screen.getByTestId('peak-indicator-friday')).toBeInTheDocument();
    });

    it('applies correct color intensity based on activity level', () => {
      render(<DailyPatternChart patterns={mockVaryingActivityPatterns} />);

      const lowActivityBar = screen.getByTestId('daily-bar-monday');
      const mediumActivityBar = screen.getByTestId('daily-bar-tuesday');
      const highActivityBar = screen.getByTestId('daily-bar-wednesday');

      // Verify different color intensities (lighter for lower activity)
      expect(lowActivityBar).toHaveClass(/opacity-[3-5]0/);
      expect(mediumActivityBar).toHaveClass(/opacity-[6-8]0/);
      expect(highActivityBar).toHaveClass(/opacity-100/);
    });
  });

  describe('tooltip interactions', () => {
    it('shows tooltip on bar hover with complete data', async () => {
      const user = userEvent.setup();
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      const mondayBar = screen.getByTestId('daily-bar-monday');
      await user.hover(mondayBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('daily-pattern-tooltip');
        expect(tooltip).toBeInTheDocument();
        expect(tooltip).toHaveTextContent('Monday');
        expect(tooltip).toHaveTextContent('Average: 45.0 detections');
        expect(tooltip).toHaveTextContent('Peak Hour: 5:00 PM');
        expect(tooltip).toHaveTextContent('Total Samples: 168');
      });
    });

    it('shows tooltip with formatted peak hour', async () => {
      const user = userEvent.setup();
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      // Test morning peak hour
      const saturdayBar = screen.getByTestId('daily-bar-saturday');
      await user.hover(saturdayBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('daily-pattern-tooltip');
        expect(tooltip).toHaveTextContent('Peak Hour: 12:00 PM');
      });

      await user.unhover(saturdayBar);

      // Test evening peak hour
      const fridayBar = screen.getByTestId('daily-bar-friday');
      await user.hover(fridayBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('daily-pattern-tooltip');
        expect(tooltip).toHaveTextContent('Peak Hour: 6:00 PM');
      });
    });

    it('hides tooltip on mouse leave', async () => {
      const user = userEvent.setup();
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      const mondayBar = screen.getByTestId('daily-bar-monday');
      await user.hover(mondayBar);

      await waitFor(() => {
        expect(screen.getByTestId('daily-pattern-tooltip')).toBeInTheDocument();
      });

      await user.unhover(mondayBar);

      await waitFor(() => {
        expect(screen.queryByTestId('daily-pattern-tooltip')).not.toBeInTheDocument();
      });
    });

    it('displays relative activity comparison in tooltip', async () => {
      const user = userEvent.setup();
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      // Friday has highest activity (65.0)
      const fridayBar = screen.getByTestId('daily-bar-friday');
      await user.hover(fridayBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('daily-pattern-tooltip');
        expect(tooltip).toHaveTextContent(/Busiest day/i);
      });

      await user.unhover(fridayBar);

      // Sunday has lowest activity (30.0)
      const sundayBar = screen.getByTestId('daily-bar-sunday');
      await user.hover(sundayBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('daily-pattern-tooltip');
        expect(tooltip).toHaveTextContent(/Quietest day/i);
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no patterns provided', () => {
      render(<DailyPatternChart patterns={{}} />);

      expect(screen.getByTestId('daily-pattern-empty')).toBeInTheDocument();
      expect(screen.getByText(/No daily pattern data available/i)).toBeInTheDocument();
    });

    it('shows empty state with helpful message', () => {
      render(<DailyPatternChart patterns={{}} />);

      expect(
        screen.getByText(/Data will appear after at least one week of learning/i)
      ).toBeInTheDocument();
    });
  });

  describe('partial week data', () => {
    it('renders chart with missing days', () => {
      render(<DailyPatternChart patterns={mockPartialWeekPatterns} />);

      // Chart should still render with all days
      expect(screen.getByTestId('daily-pattern-chart')).toBeInTheDocument();

      // Days with data should render
      expect(screen.getByTestId('daily-bar-monday')).toBeInTheDocument();
      expect(screen.getByTestId('daily-bar-wednesday')).toBeInTheDocument();
      expect(screen.getByTestId('daily-bar-friday')).toBeInTheDocument();

      // Days without data should be rendered as empty/placeholder
      expect(screen.getByTestId('daily-bar-tuesday')).toHaveClass('no-data');
      expect(screen.getByTestId('daily-bar-thursday')).toHaveClass('no-data');
    });

    it('shows indicator for incomplete week', () => {
      render(<DailyPatternChart patterns={mockPartialWeekPatterns} />);

      expect(screen.getByText(/Partial week/i)).toBeInTheDocument();
    });

    it('shows tooltip for days without data', async () => {
      const user = userEvent.setup();
      render(<DailyPatternChart patterns={mockPartialWeekPatterns} />);

      const tuesdayBar = screen.getByTestId('daily-bar-tuesday');
      await user.hover(tuesdayBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('daily-pattern-tooltip');
        expect(tooltip).toHaveTextContent(/No data available for this day/i);
      });
    });
  });

  describe('peak hour visualization', () => {
    it('displays peak hour indicator on each bar', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      // Check that peak indicators exist
      expect(screen.getByTestId('peak-indicator-monday')).toBeInTheDocument();
      expect(screen.getByTestId('peak-indicator-tuesday')).toBeInTheDocument();
    });

    it('positions peak indicator correctly within bar', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      // Monday peak is at 17 (5pm) which is 17/24 = 70.8% through the day
      const mondayPeakIndicator = screen.getByTestId('peak-indicator-monday');
      expect(mondayPeakIndicator).toHaveAttribute('data-peak-hour', '17');
    });

    it('shows peak hour in legend', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      expect(screen.getByText(/Peak Hour Marker/i)).toBeInTheDocument();
    });
  });

  describe('color intensity and activity levels', () => {
    it('applies different color intensities based on activity', () => {
      render(<DailyPatternChart patterns={mockVaryingActivityPatterns} />);

      const lowBar = screen.getByTestId('daily-bar-monday');
      const mediumBar = screen.getByTestId('daily-bar-tuesday');
      const highBar = screen.getByTestId('daily-bar-wednesday');

      // Check that bars have different color classes
      expect(lowBar).toHaveClass(/bg-blue-[2-3]00/);
      expect(mediumBar).toHaveClass(/bg-blue-[4-5]00/);
      expect(highBar).toHaveClass(/bg-blue-[6-7]00/);
    });

    it('displays color scale legend', () => {
      render(<DailyPatternChart patterns={mockVaryingActivityPatterns} />);

      // Use getAllByText since "Activity Level" appears in both legend and screen reader text
      const activityLevelElements = screen.getAllByText(/Activity Level/i);
      expect(activityLevelElements.length).toBeGreaterThan(0);
      expect(screen.getByText(/Low/i)).toBeInTheDocument();
      expect(screen.getByText(/High/i)).toBeInTheDocument();
    });
  });

  describe('data quality indicators', () => {
    it('shows badge for low sample counts', () => {
      render(<DailyPatternChart patterns={mockPartialWeekPatterns} />);

      // Days with only 24 samples (1 day worth) should show low confidence
      expect(screen.getByText(/Low confidence/i)).toBeInTheDocument();
    });

    it('includes sample count in tooltip', async () => {
      const user = userEvent.setup();
      render(<DailyPatternChart patterns={mockPartialWeekPatterns} />);

      const mondayBar = screen.getByTestId('daily-bar-monday');
      await user.hover(mondayBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('daily-pattern-tooltip');
        expect(tooltip).toHaveTextContent('Total Samples: 24');
        expect(tooltip).toHaveTextContent(/Based on 1 week/i);
      });
    });
  });

  describe('accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      const chart = screen.getByTestId('daily-pattern-chart');
      expect(chart).toHaveAttribute('aria-label', 'Weekly activity pattern chart');
    });

    it('provides descriptive text for screen readers', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      expect(screen.getByText(/Chart shows activity levels by day of week/i)).toBeInTheDocument();
    });

    it('each bar is keyboard accessible', async () => {
      const user = userEvent.setup();
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      // Tab through bars
      await user.tab();
      const mondayBar = screen.getByTestId('daily-bar-monday');
      expect(mondayBar).toHaveFocus();

      await user.tab();
      const tuesdayBar = screen.getByTestId('daily-bar-tuesday');
      expect(tuesdayBar).toHaveFocus();
    });

    it('shows tooltip on keyboard focus', async () => {
      userEvent.setup();
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      const mondayBar = screen.getByTestId('daily-bar-monday');
      mondayBar.focus();

      await waitFor(() => {
        expect(screen.getByTestId('daily-pattern-tooltip')).toBeInTheDocument();
      });
    });
  });

  describe('weekend vs weekday highlighting', () => {
    it('visually distinguishes weekends from weekdays', () => {
      render(<DailyPatternChart patterns={mockFullWeekPatterns} />);

      // Saturday and Sunday should have different styling
      const saturdayBar = screen.getByTestId('daily-bar-saturday');
      const sundayBar = screen.getByTestId('daily-bar-sunday');
      const mondayBar = screen.getByTestId('daily-bar-monday');

      expect(saturdayBar).toHaveClass(/weekend/);
      expect(sundayBar).toHaveClass(/weekend/);
      expect(mondayBar).not.toHaveClass(/weekend/);
    });
  });
});
