import { render, screen } from '@testing-library/react';
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
});
