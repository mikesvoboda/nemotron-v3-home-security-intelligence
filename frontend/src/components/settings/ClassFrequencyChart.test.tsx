import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ClassFrequencyChart from './ClassFrequencyChart';

import type { ClassBaselineEntry } from '../../services/api';

describe('ClassFrequencyChart', () => {
  const createMockEntry = (
    object_class: string,
    hour: number,
    frequency: number = 1.0,
    sample_count: number = 10
  ): ClassBaselineEntry => ({
    object_class,
    hour,
    frequency,
    sample_count,
  });

  const mockEntries: ClassBaselineEntry[] = [
    createMockEntry('person', 8, 3.5, 45),
    createMockEntry('person', 17, 5.2, 60),
    createMockEntry('vehicle', 8, 2.1, 30),
    createMockEntry('vehicle', 17, 1.5, 25),
    createMockEntry('animal', 12, 0.8, 15),
  ];

  it('renders component with title', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle', 'animal']}
        totalSamples={175}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('Object Class Distribution')).toBeInTheDocument();
    expect(screen.getByText('Frequency of different object types detected')).toBeInTheDocument();
  });

  it('displays class count badge', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle', 'animal']}
        totalSamples={175}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('3 classes')).toBeInTheDocument();
  });

  it('displays most common class', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle', 'animal']}
        totalSamples={175}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('Most Common')).toBeInTheDocument();
    expect(screen.getByText('Person')).toBeInTheDocument();
  });

  it('displays total samples', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle', 'animal']}
        totalSamples={175}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('Total Samples')).toBeInTheDocument();
    expect(screen.getByText('175')).toBeInTheDocument();
  });

  it('displays class count in stats', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle', 'animal']}
        totalSamples={175}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('Class Count')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('displays N/A when most common class is null', () => {
    render(
      <ClassFrequencyChart
        entries={[]}
        uniqueClasses={[]}
        totalSamples={0}
        mostCommonClass={null}
      />
    );

    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('shows empty state when no data', () => {
    render(
      <ClassFrequencyChart
        entries={[]}
        uniqueClasses={[]}
        totalSamples={0}
        mostCommonClass={null}
      />
    );

    expect(screen.getByText('No class data available yet')).toBeInTheDocument();
  });

  it('displays peak hours section when data exists', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle', 'animal']}
        totalSamples={175}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('Peak Hours by Class')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle', 'animal']}
        totalSamples={175}
        mostCommonClass="person"
        className="custom-class"
      />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('handles single class gracefully', () => {
    const singleClassEntries = [
      createMockEntry('person', 8, 3.5, 45),
      createMockEntry('person', 17, 5.2, 60),
    ];

    render(
      <ClassFrequencyChart
        entries={singleClassEntries}
        uniqueClasses={['person']}
        totalSamples={105}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('1 classes')).toBeInTheDocument();
  });

  it('formats large sample counts with locale string', () => {
    render(
      <ClassFrequencyChart
        entries={mockEntries}
        uniqueClasses={['person', 'vehicle', 'animal']}
        totalSamples={1000000}
        mostCommonClass="person"
      />
    );

    expect(screen.getByText('1,000,000')).toBeInTheDocument();
  });
});
