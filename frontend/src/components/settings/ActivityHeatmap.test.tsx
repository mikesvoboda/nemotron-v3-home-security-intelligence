import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ActivityHeatmap from './ActivityHeatmap';

import type { ActivityBaselineEntry } from '../../services/api';

describe('ActivityHeatmap', () => {
  const createMockEntry = (
    hour: number,
    day_of_week: number,
    avg_count: number = 1.0,
    sample_count: number = 10,
    is_peak: boolean = false
  ): ActivityBaselineEntry => ({
    hour,
    day_of_week,
    avg_count,
    sample_count,
    is_peak,
  });

  // Create a full week of mock data (168 entries)
  const createFullWeekData = (): ActivityBaselineEntry[] => {
    const entries: ActivityBaselineEntry[] = [];
    for (let day = 0; day < 7; day++) {
      for (let hour = 0; hour < 24; hour++) {
        entries.push(createMockEntry(hour, day, 1.0 + Math.random() * 4.0, 15, false));
      }
    }
    return entries;
  };

  it('renders component with title', () => {
    render(
      <ActivityHeatmap
        entries={[]}
        peakHour={null}
        peakDay={null}
        learningComplete={false}
      />
    );

    expect(screen.getByText('Activity Heatmap')).toBeInTheDocument();
    expect(screen.getByText('Hourly activity patterns by day of week')).toBeInTheDocument();
  });

  it('shows learning in progress indicator when not complete', () => {
    render(
      <ActivityHeatmap
        entries={[]}
        peakHour={null}
        peakDay={null}
        learningComplete={false}
      />
    );

    expect(screen.getByText('Learning in Progress')).toBeInTheDocument();
  });

  it('shows learning complete indicator when complete', () => {
    render(
      <ActivityHeatmap
        entries={createFullWeekData()}
        peakHour={17}
        peakDay={4}
        learningComplete={true}
      />
    );

    expect(screen.getByText('Learning Complete')).toBeInTheDocument();
  });

  it('displays peak activity time when available', () => {
    render(
      <ActivityHeatmap
        entries={createFullWeekData()}
        peakHour={17}
        peakDay={4}
        learningComplete={true}
      />
    );

    // Fri at 5pm
    expect(screen.getByText(/Peak activity:/)).toBeInTheDocument();
    expect(screen.getByText('Fri at 5pm')).toBeInTheDocument();
  });

  it('displays no data message when peak is null', () => {
    render(
      <ActivityHeatmap
        entries={[]}
        peakHour={null}
        peakDay={null}
        learningComplete={false}
      />
    );

    expect(screen.getByText('No data')).toBeInTheDocument();
  });

  it('renders day labels', () => {
    render(
      <ActivityHeatmap
        entries={createFullWeekData()}
        peakHour={12}
        peakDay={0}
        learningComplete={true}
      />
    );

    expect(screen.getByText('Mon')).toBeInTheDocument();
    expect(screen.getByText('Tue')).toBeInTheDocument();
    expect(screen.getByText('Wed')).toBeInTheDocument();
    expect(screen.getByText('Thu')).toBeInTheDocument();
    expect(screen.getByText('Fri')).toBeInTheDocument();
    expect(screen.getByText('Sat')).toBeInTheDocument();
    expect(screen.getByText('Sun')).toBeInTheDocument();
  });

  it('renders hour labels', () => {
    render(
      <ActivityHeatmap
        entries={createFullWeekData()}
        peakHour={12}
        peakDay={0}
        learningComplete={true}
      />
    );

    expect(screen.getByText('12am')).toBeInTheDocument();
    expect(screen.getByText('12pm')).toBeInTheDocument();
  });

  it('renders legend', () => {
    render(
      <ActivityHeatmap
        entries={createFullWeekData()}
        peakHour={12}
        peakDay={0}
        learningComplete={true}
      />
    );

    expect(screen.getByText('Low')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <ActivityHeatmap
        entries={[]}
        peakHour={null}
        peakDay={null}
        learningComplete={false}
        className="custom-class"
      />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('handles empty entries array gracefully', () => {
    render(
      <ActivityHeatmap
        entries={[]}
        peakHour={null}
        peakDay={null}
        learningComplete={false}
      />
    );

    // Should render without errors
    expect(screen.getByText('Activity Heatmap')).toBeInTheDocument();
  });

  it('handles partial data gracefully', () => {
    const partialData = [
      createMockEntry(12, 0, 5.0, 20, true),
      createMockEntry(17, 4, 3.0, 15, false),
    ];

    render(
      <ActivityHeatmap
        entries={partialData}
        peakHour={12}
        peakDay={0}
        learningComplete={false}
      />
    );

    // Should render without errors
    expect(screen.getByText('Activity Heatmap')).toBeInTheDocument();
  });
});
