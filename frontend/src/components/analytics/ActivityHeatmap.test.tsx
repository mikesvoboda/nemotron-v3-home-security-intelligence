import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';

import ActivityHeatmap from './ActivityHeatmap';

import type { ActivityBaselineEntry } from '../../services/api';

describe('ActivityHeatmap', () => {
  const mockEntries: ActivityBaselineEntry[] = [
    { hour: 0, day_of_week: 0, avg_count: 0.5, sample_count: 30, is_peak: false },
    { hour: 17, day_of_week: 4, avg_count: 5.2, sample_count: 30, is_peak: true },
    { hour: 8, day_of_week: 1, avg_count: 2.0, sample_count: 25, is_peak: false },
  ];

  it('renders the component header', () => {
    render(
      <ActivityHeatmap entries={mockEntries} learningComplete={true} minSamplesRequired={10} />
    );

    expect(screen.getByText('Weekly Activity Pattern')).toBeInTheDocument();
  });

  it('shows learning badge when not complete', () => {
    render(
      <ActivityHeatmap entries={mockEntries} learningComplete={false} minSamplesRequired={10} />
    );

    expect(screen.getByText(/Learning/)).toBeInTheDocument();
  });

  it('hides learning badge when complete', () => {
    render(
      <ActivityHeatmap entries={mockEntries} learningComplete={true} minSamplesRequired={10} />
    );

    expect(screen.queryByText(/Learning/)).not.toBeInTheDocument();
  });

  it('shows empty state when no entries', () => {
    render(<ActivityHeatmap entries={[]} learningComplete={false} minSamplesRequired={10} />);

    expect(screen.getByText(/No baseline data available/)).toBeInTheDocument();
  });

  it('renders day labels', () => {
    render(
      <ActivityHeatmap entries={mockEntries} learningComplete={true} minSamplesRequired={10} />
    );

    expect(screen.getByText('Mon')).toBeInTheDocument();
    expect(screen.getByText('Tue')).toBeInTheDocument();
    expect(screen.getByText('Wed')).toBeInTheDocument();
    expect(screen.getByText('Thu')).toBeInTheDocument();
    expect(screen.getByText('Fri')).toBeInTheDocument();
    expect(screen.getByText('Sat')).toBeInTheDocument();
    expect(screen.getByText('Sun')).toBeInTheDocument();
  });

  it('renders heatmap cells', () => {
    render(
      <ActivityHeatmap entries={mockEntries} learningComplete={true} minSamplesRequired={10} />
    );

    // Check for some specific cells
    expect(screen.getByTestId('heatmap-cell-0-0')).toBeInTheDocument();
    expect(screen.getByTestId('heatmap-cell-4-17')).toBeInTheDocument();
  });

  it('renders legend', () => {
    render(
      <ActivityHeatmap entries={mockEntries} learningComplete={true} minSamplesRequired={10} />
    );

    expect(screen.getByText('Low Activity')).toBeInTheDocument();
    expect(screen.getByText('High Activity')).toBeInTheDocument();
    expect(screen.getByText('Peak Hours')).toBeInTheDocument();
  });

  describe('tooltip functionality', () => {
    it('shows tooltip on cell hover', async () => {
      const user = userEvent.setup();
      render(
        <ActivityHeatmap entries={mockEntries} learningComplete={true} minSamplesRequired={10} />
      );

      // Hover over a cell with data (Fri 5pm - index 4, hour 17)
      const cell = screen.getByTestId('heatmap-cell-4-17');
      await user.hover(cell);

      await waitFor(() => {
        const tooltip = screen.getByTestId('heatmap-tooltip');
        expect(tooltip).toBeInTheDocument();
        expect(tooltip).toHaveTextContent('Fri');
        expect(tooltip).toHaveTextContent('5p');
        expect(tooltip).toHaveTextContent('Peak');
      });
    });

    it('hides tooltip on mouse leave', async () => {
      const user = userEvent.setup();
      render(
        <ActivityHeatmap entries={mockEntries} learningComplete={true} minSamplesRequired={10} />
      );

      const cell = screen.getByTestId('heatmap-cell-4-17');
      await user.hover(cell);

      await waitFor(() => {
        expect(screen.getByTestId('heatmap-tooltip')).toBeInTheDocument();
      });

      await user.unhover(cell);

      await waitFor(() => {
        expect(screen.queryByTestId('heatmap-tooltip')).not.toBeInTheDocument();
      });
    });

    it('shows insufficient data message for cells without enough samples', async () => {
      const user = userEvent.setup();
      const entriesWithLowSamples: ActivityBaselineEntry[] = [
        { hour: 8, day_of_week: 1, avg_count: 2.0, sample_count: 5, is_peak: false },
      ];

      render(
        <ActivityHeatmap
          entries={entriesWithLowSamples}
          learningComplete={true}
          minSamplesRequired={10}
        />
      );

      // Hover over a cell with insufficient samples
      const cell = screen.getByTestId('heatmap-cell-1-8');
      await user.hover(cell);

      await waitFor(() => {
        const tooltip = screen.getByTestId('heatmap-tooltip');
        expect(tooltip).toHaveTextContent('Insufficient data');
      });
    });

    it('displays average and sample count in tooltip', async () => {
      const user = userEvent.setup();
      render(
        <ActivityHeatmap entries={mockEntries} learningComplete={true} minSamplesRequired={10} />
      );

      // Hover over Fri 5pm cell (peak cell with data)
      const cell = screen.getByTestId('heatmap-cell-4-17');
      await user.hover(cell);

      await waitFor(() => {
        const tooltip = screen.getByTestId('heatmap-tooltip');
        expect(tooltip).toHaveTextContent('Average:');
        expect(tooltip).toHaveTextContent('5.2');
        expect(tooltip).toHaveTextContent('Samples:');
        expect(tooltip).toHaveTextContent('30');
      });
    });
  });
});
