import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';

import ClassFrequencyChart from './ClassFrequencyChart';

import type { ClassBaselineEntry } from '../../services/api';

describe('ClassFrequencyChart', () => {
  const mockEntries: ClassBaselineEntry[] = [
    { object_class: 'person', hour: 8, frequency: 3.5, sample_count: 45 },
    { object_class: 'person', hour: 17, frequency: 5.0, sample_count: 50 },
    { object_class: 'vehicle', hour: 8, frequency: 2.0, sample_count: 20 },
  ];

  it('renders the component header', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle']}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('Object Class Distribution')).toBeInTheDocument();
  });

  it('shows most common class', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle']}
        mostCommonClass="person"
      />
    );

    // The text "Most common:" is followed by "Person" in a span
    expect(screen.getByText(/Most common:/)).toBeInTheDocument();
    // Person appears multiple times (in header and legend), just check it exists
    const personElements = screen.getAllByText('Person');
    expect(personElements.length).toBeGreaterThan(0);
  });

  it('shows empty state when no entries', () => {
    render(<ClassFrequencyChart entries={[]} uniqueClasses={[]} mostCommonClass={null} />);

    expect(screen.getByText(/No object class data available/)).toBeInTheDocument();
  });

  it('renders class bars', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle']}
        mostCommonClass="person"
      />
    );

    expect(screen.getByTestId('class-bar-person')).toBeInTheDocument();
    expect(screen.getByTestId('class-bar-vehicle')).toBeInTheDocument();
  });

  it('shows frequency and sample count', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle']}
        mostCommonClass="person"
      />
    );

    // Person has total frequency of 8.5 (3.5 + 5.0) and 95 samples
    expect(screen.getByText(/8.5 freq/)).toBeInTheDocument();
    expect(screen.getByText(/95 samples/)).toBeInTheDocument();
  });

  it('renders legend for unique classes', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle']}
        mostCommonClass="person"
      />
    );

    // Legend should show formatted class names
    const legend = screen.getAllByText('Person');
    expect(legend.length).toBeGreaterThan(0);
    expect(screen.getAllByText('Vehicle').length).toBeGreaterThan(0);
  });

  describe('tooltip functionality', () => {
    it('shows tooltip on bar hover', async () => {
      const user = userEvent.setup();
      render(
        <ClassFrequencyChart
          entries={mockEntries}
          uniqueClasses={['person', 'vehicle']}
          mostCommonClass="person"
        />
      );

      // Find the bar container for person class
      const personBar = screen.getByTestId('class-bar-person');
      // Hover over the bar (the hoverable element is the div with overflow-hidden)
      const hoverableElement = personBar.querySelector('.cursor-pointer');
      expect(hoverableElement).toBeInTheDocument();

      await user.hover(hoverableElement!);

      await waitFor(() => {
        const tooltip = screen.getByTestId('class-chart-tooltip');
        expect(tooltip).toBeInTheDocument();
        expect(tooltip).toHaveTextContent('Person');
      });
    });

    it('hides tooltip on mouse leave', async () => {
      const user = userEvent.setup();
      render(
        <ClassFrequencyChart
          entries={mockEntries}
          uniqueClasses={['person', 'vehicle']}
          mostCommonClass="person"
        />
      );

      const personBar = screen.getByTestId('class-bar-person');
      const hoverableElement = personBar.querySelector('.cursor-pointer');

      await user.hover(hoverableElement!);

      await waitFor(() => {
        expect(screen.getByTestId('class-chart-tooltip')).toBeInTheDocument();
      });

      await user.unhover(hoverableElement!);

      await waitFor(() => {
        expect(screen.queryByTestId('class-chart-tooltip')).not.toBeInTheDocument();
      });
    });

    it('displays frequency, samples, and percentage in tooltip', async () => {
      const user = userEvent.setup();
      render(
        <ClassFrequencyChart
          entries={mockEntries}
          uniqueClasses={['person', 'vehicle']}
          mostCommonClass="person"
        />
      );

      const personBar = screen.getByTestId('class-bar-person');
      const hoverableElement = personBar.querySelector('.cursor-pointer');

      await user.hover(hoverableElement!);

      await waitFor(() => {
        const tooltip = screen.getByTestId('class-chart-tooltip');
        expect(tooltip).toHaveTextContent('Frequency:');
        expect(tooltip).toHaveTextContent('8.5'); // Total frequency for person
        expect(tooltip).toHaveTextContent('Samples:');
        expect(tooltip).toHaveTextContent('95'); // Total samples for person
        expect(tooltip).toHaveTextContent('Share:');
        expect(tooltip).toHaveTextContent('100.0%'); // Person has the max, so 100%
      });
    });
  });
});
