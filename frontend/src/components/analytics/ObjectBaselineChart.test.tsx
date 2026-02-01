/**
 * Tests for ObjectBaselineChart component
 *
 * This component displays per-class baseline statistics in a grouped bar chart format.
 * Tests verify proper rendering, data visualization, sorting, and edge cases.
 *
 * Tests cover:
 * - Rendering with object baseline data
 * - Grouped bars for each object class
 * - Metrics display: avg_hourly, peak_hour, total_detections
 * - Tooltip with class name and values
 * - Empty object baselines state
 * - Sorting by selected metric
 * - Color coding by object class
 * - Metric selection and switching
 * - Accessibility attributes
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';

import ObjectBaselineChart from './ObjectBaselineChart';

import type { ObjectBaseline } from '../../services/api';

describe('ObjectBaselineChart', () => {
  // Mock data representing baseline stats for multiple object classes
  const mockObjectBaselines: Record<string, ObjectBaseline> = {
    person: { avg_hourly: 2.3, peak_hour: 17, total_detections: 550 },
    vehicle: { avg_hourly: 1.1, peak_hour: 8, total_detections: 264 },
    animal: { avg_hourly: 0.5, peak_hour: 6, total_detections: 120 },
    bicycle: { avg_hourly: 0.3, peak_hour: 18, total_detections: 72 },
  };

  // Mock data with single object class
  const mockSingleObjectBaseline: Record<string, ObjectBaseline> = {
    person: { avg_hourly: 2.3, peak_hour: 17, total_detections: 550 },
  };

  // Mock data with varying magnitudes for sorting tests
  const mockVaryingMagnitudes: Record<string, ObjectBaseline> = {
    person: { avg_hourly: 10.0, peak_hour: 17, total_detections: 2400 }, // Highest total
    vehicle: { avg_hourly: 0.5, peak_hour: 8, total_detections: 120 }, // Lowest avg
    animal: { avg_hourly: 5.0, peak_hour: 6, total_detections: 1200 }, // Middle values
  };

  describe('rendering with data', () => {
    it('renders the chart title', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      expect(screen.getByText('Detection by Object Type')).toBeInTheDocument();
    });

    it('renders chart container', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      expect(screen.getByTestId('object-baseline-chart')).toBeInTheDocument();
    });

    it('renders grouped bars for each object class', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      // Check for all object class groups
      expect(screen.getByTestId('object-group-person')).toBeInTheDocument();
      expect(screen.getByTestId('object-group-vehicle')).toBeInTheDocument();
      expect(screen.getByTestId('object-group-animal')).toBeInTheDocument();
      expect(screen.getByTestId('object-group-bicycle')).toBeInTheDocument();
    });

    it('displays class names with proper formatting', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Animal')).toBeInTheDocument();
      expect(screen.getByText('Bicycle')).toBeInTheDocument();
    });

    it('renders three metrics for each class', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      // Each object should have bars for avg_hourly, peak_hour, total_detections
      const personGroup = screen.getByTestId('object-group-person');
      const bars = personGroup.querySelectorAll('[data-metric]');
      expect(bars).toHaveLength(3);
    });
  });

  describe('metric display', () => {
    it('displays average hourly metric', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      // Check for average hourly values
      expect(screen.getByTestId('metric-person-avg_hourly')).toBeInTheDocument();
    });

    it('displays peak hour metric', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      // Check for peak hour values
      expect(screen.getByTestId('metric-person-peak_hour')).toBeInTheDocument();
    });

    it('displays total detections metric', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      // Check for total detections values
      expect(screen.getByTestId('metric-person-total_detections')).toBeInTheDocument();
    });

    it('formats metrics with appropriate units', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      // Average hourly should show decimal
      expect(screen.getByText('2.3/hr')).toBeInTheDocument();

      // Peak hour should show time format
      expect(screen.getByText('5:00 PM')).toBeInTheDocument();

      // Total should show integer
      expect(screen.getByText('550')).toBeInTheDocument();
    });
  });

  describe('tooltip interactions', () => {
    it('shows tooltip on bar hover with class and metric data', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const personBar = screen.getByTestId('metric-person-avg_hourly');
      await user.hover(personBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('object-baseline-tooltip');
        expect(tooltip).toBeInTheDocument();
        expect(tooltip).toHaveTextContent('Person');
        expect(tooltip).toHaveTextContent('Average Hourly: 2.3');
      });
    });

    it('shows tooltip for peak hour metric', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const peakBar = screen.getByTestId('metric-person-peak_hour');
      await user.hover(peakBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('object-baseline-tooltip');
        expect(tooltip).toHaveTextContent('Peak Hour: 5:00 PM (17)');
      });
    });

    it('shows tooltip for total detections metric', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const totalBar = screen.getByTestId('metric-person-total_detections');
      await user.hover(totalBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('object-baseline-tooltip');
        expect(tooltip).toHaveTextContent('Total Detections: 550');
      });
    });

    it('hides tooltip on mouse leave', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const personBar = screen.getByTestId('metric-person-avg_hourly');
      await user.hover(personBar);

      await waitFor(() => {
        expect(screen.getByTestId('object-baseline-tooltip')).toBeInTheDocument();
      });

      await user.unhover(personBar);

      await waitFor(() => {
        expect(screen.queryByTestId('object-baseline-tooltip')).not.toBeInTheDocument();
      });
    });

    it('shows relative comparison in tooltip', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      // Person has highest avg_hourly (2.3)
      const personBar = screen.getByTestId('metric-person-avg_hourly');
      await user.hover(personBar);

      await waitFor(() => {
        const tooltip = screen.getByTestId('object-baseline-tooltip');
        expect(tooltip).toHaveTextContent(/Most frequent/i);
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no baselines provided', () => {
      render(<ObjectBaselineChart baselines={{}} />);

      expect(screen.getByTestId('object-baseline-empty')).toBeInTheDocument();
      expect(screen.getByText(/No object baseline data available/i)).toBeInTheDocument();
    });

    it('shows helpful message in empty state', () => {
      render(<ObjectBaselineChart baselines={{}} />);

      expect(
        screen.getByText(/Data will appear after objects are detected/i)
      ).toBeInTheDocument();
    });
  });

  describe('sorting functionality', () => {
    it('displays sort control', () => {
      render(<ObjectBaselineChart baselines={mockVaryingMagnitudes} sortable={true} />);

      expect(screen.getByTestId('sort-selector')).toBeInTheDocument();
    });

    it('sorts by average hourly when selected', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockVaryingMagnitudes} sortable={true} />);

      const sortSelector = screen.getByTestId('sort-selector');
      await user.click(sortSelector);
      await user.click(screen.getByText('Average Hourly'));

      // Check order: person (10.0), animal (5.0), vehicle (0.5)
      const groups = screen.getAllByTestId(/^object-group-/);
      expect(groups[0]).toHaveAttribute('data-class', 'person');
      expect(groups[1]).toHaveAttribute('data-class', 'animal');
      expect(groups[2]).toHaveAttribute('data-class', 'vehicle');
    });

    it('sorts by total detections when selected', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockVaryingMagnitudes} sortable={true} />);

      const sortSelector = screen.getByTestId('sort-selector');
      await user.click(sortSelector);
      await user.click(screen.getByText('Total Detections'));

      // Check order: person (2400), animal (1200), vehicle (120)
      const groups = screen.getAllByTestId(/^object-group-/);
      expect(groups[0]).toHaveAttribute('data-class', 'person');
      expect(groups[1]).toHaveAttribute('data-class', 'animal');
      expect(groups[2]).toHaveAttribute('data-class', 'vehicle');
    });

    it('sorts by peak hour when selected', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockVaryingMagnitudes} sortable={true} />);

      const sortSelector = screen.getByTestId('sort-selector');
      await user.click(sortSelector);
      // Use getAllByText to handle multiple "Peak Hour" occurrences (sort dropdown and legend)
      const peakHourOptions = screen.getAllByText('Peak Hour');
      // Click the first one (the dropdown option)
      await user.click(peakHourOptions[0]);

      // Check order by peak_hour: animal (6), vehicle (8), person (17)
      const groups = screen.getAllByTestId(/^object-group-/);
      expect(groups[0]).toHaveAttribute('data-class', 'animal');
      expect(groups[1]).toHaveAttribute('data-class', 'vehicle');
      expect(groups[2]).toHaveAttribute('data-class', 'person');
    });

    it('maintains alphabetical order when sortable is false', () => {
      render(<ObjectBaselineChart baselines={mockVaryingMagnitudes} sortable={false} />);

      const groups = screen.getAllByTestId(/^object-group-/);
      expect(groups[0]).toHaveAttribute('data-class', 'animal');
      expect(groups[1]).toHaveAttribute('data-class', 'person');
      expect(groups[2]).toHaveAttribute('data-class', 'vehicle');
    });
  });

  describe('color coding by object class', () => {
    it('applies distinct colors to each object class', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const personGroup = screen.getByTestId('object-group-person');
      const vehicleGroup = screen.getByTestId('object-group-vehicle');
      const animalGroup = screen.getByTestId('object-group-animal');

      // Each should have different color classes
      expect(personGroup).toHaveClass(/bg-blue-/);
      expect(vehicleGroup).toHaveClass(/bg-green-/);
      expect(animalGroup).toHaveClass(/bg-orange-/);
    });

    it('displays color legend', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      expect(screen.getByTestId('color-legend')).toBeInTheDocument();
      expect(screen.getByText(/Object Types/i)).toBeInTheDocument();
    });

    it('uses consistent colors across renders', () => {
      const { rerender } = render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const personGroup1 = screen.getByTestId('object-group-person');
      const className1 = personGroup1.className;

      rerender(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const personGroup2 = screen.getByTestId('object-group-person');
      const className2 = personGroup2.className;

      expect(className1).toBe(className2);
    });
  });

  describe('metric selection', () => {
    it('allows selecting primary metric to display', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const metricSelector = screen.getByTestId('metric-selector');
      await user.click(metricSelector);
      // Use getAllByText since "Total" appears in both dropdown and legend
      const totalOptions = screen.getAllByText('Total');
      // Click the first one (the dropdown option)
      await user.click(totalOptions[0]);

      // Chart should emphasize total_detections bars
      const totalBars = screen.getAllByTestId(/metric-.*-total_detections/);
      totalBars.forEach((bar) => {
        expect(bar).toHaveClass(/emphasized/);
      });
    });

    it('displays all metrics but highlights selected', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const metricSelector = screen.getByTestId('metric-selector');
      await user.click(metricSelector);
      // Use getAllByText since "Avg/Hour" appears in both dropdown and legend
      const avgOptions = screen.getAllByText('Avg/Hour');
      // Click the first one (the dropdown option)
      await user.click(avgOptions[0]);

      // All three metrics should still be visible
      expect(screen.getAllByTestId(/metric-.*-avg_hourly/)).toHaveLength(4);
      expect(screen.getAllByTestId(/metric-.*-peak_hour/)).toHaveLength(4);
      expect(screen.getAllByTestId(/metric-.*-total_detections/)).toHaveLength(4);
    });
  });

  describe('single object class', () => {
    it('renders correctly with only one object class', () => {
      render(<ObjectBaselineChart baselines={mockSingleObjectBaseline} />);

      expect(screen.getByTestId('object-baseline-chart')).toBeInTheDocument();
      expect(screen.getByTestId('object-group-person')).toBeInTheDocument();
    });

    it('does not show sort controls for single class', () => {
      render(<ObjectBaselineChart baselines={mockSingleObjectBaseline} sortable={true} />);

      expect(screen.queryByTestId('sort-selector')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const chart = screen.getByTestId('object-baseline-chart');
      expect(chart).toHaveAttribute('aria-label', 'Object baseline statistics chart');
    });

    it('provides descriptive text for screen readers', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      expect(
        screen.getByText(/Chart shows detection statistics by object type/i)
      ).toBeInTheDocument();
    });

    it('bars are keyboard accessible', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const metricSelector = screen.getByTestId('metric-selector');
      // First bar is animal (alphabetically first), not person
      const firstBar = screen.getByTestId('metric-animal-avg_hourly');

      // Tab to metric selector first (it's in the header)
      await user.tab();
      expect(metricSelector).toHaveFocus();

      // Tab again to reach first bar (alphabetically first is animal)
      await user.tab();
      expect(firstBar).toHaveFocus();
    });

    it('shows tooltip on keyboard focus', async () => {
      userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const bar = screen.getByTestId('metric-person-avg_hourly');
      bar.focus();

      await waitFor(() => {
        expect(screen.getByTestId('object-baseline-tooltip')).toBeInTheDocument();
      });
    });

    it('sort selector is keyboard accessible', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} sortable={true} />);

      const sortSelector = screen.getByTestId('sort-selector');
      const metricSelector = screen.getByTestId('metric-selector');

      // Tab to metric selector first (it appears before sort selector in DOM)
      await user.tab();
      expect(metricSelector).toHaveFocus();

      // Tab again to reach sort selector
      await user.tab();
      expect(sortSelector).toHaveFocus();

      // Click to open the dropdown (keyboard navigation verified by focus, interaction tested via click)
      await user.click(sortSelector);
      // The dropdown should now be open, showing all sort options
      await waitFor(() => {
        expect(screen.getByText('Average Hourly')).toBeInTheDocument();
      });
    });
  });

  describe('responsive layout', () => {
    it('stacks bars vertically on mobile', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const chart = screen.getByTestId('object-baseline-chart');
      expect(chart).toHaveClass(/flex-col/);
    });

    it('uses horizontal layout on larger screens', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const chart = screen.getByTestId('object-baseline-chart');
      expect(chart).toHaveClass(/lg:flex-row/);
    });
  });

  describe('legend', () => {
    it('displays legend for metrics', () => {
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      expect(screen.getByTestId('metric-legend')).toBeInTheDocument();
      expect(screen.getByText('Avg/Hour')).toBeInTheDocument();
      expect(screen.getByText('Peak Hour')).toBeInTheDocument();
      expect(screen.getByText('Total')).toBeInTheDocument();
    });

    it('legend items are interactive', async () => {
      const user = userEvent.setup();
      render(<ObjectBaselineChart baselines={mockObjectBaselines} />);

      const avgLegendItem = screen.getByTestId('legend-item-avg_hourly');
      await user.click(avgLegendItem);

      // Clicking legend should highlight corresponding metric
      const avgBars = screen.getAllByTestId(/metric-.*-avg_hourly/);
      avgBars.forEach((bar) => {
        expect(bar).toHaveClass(/highlighted/);
      });
    });
  });

  describe('edge cases', () => {
    it('handles object class with zero detections', () => {
      const baselinesWithZero: Record<string, ObjectBaseline> = {
        person: { avg_hourly: 2.3, peak_hour: 17, total_detections: 550 },
        ghost: { avg_hourly: 0, peak_hour: 0, total_detections: 0 },
      };

      render(<ObjectBaselineChart baselines={baselinesWithZero} />);

      expect(screen.getByTestId('object-group-ghost')).toBeInTheDocument();
      // Verify the ghost class has zero values using aria-label (more specific than text content)
      expect(screen.getByLabelText('Ghost average hourly: 0.0 per hour')).toBeInTheDocument();
      expect(screen.getByLabelText('Ghost total detections: 0')).toBeInTheDocument();
    });

    it('handles very large detection counts', () => {
      const largeBaselines: Record<string, ObjectBaseline> = {
        person: { avg_hourly: 999.9, peak_hour: 17, total_detections: 999999 },
      };

      render(<ObjectBaselineChart baselines={largeBaselines} />);

      expect(screen.getByText('999.9/hr')).toBeInTheDocument();
      expect(screen.getByText('999,999')).toBeInTheDocument(); // Formatted with commas
    });

    it('handles class names with special characters', () => {
      const specialBaselines: Record<string, ObjectBaseline> = {
        'delivery-truck': { avg_hourly: 1.5, peak_hour: 14, total_detections: 360 },
      };

      render(<ObjectBaselineChart baselines={specialBaselines} />);

      expect(screen.getByText('Delivery Truck')).toBeInTheDocument();
    });
  });
});
