/**
 * Tests for ModelContributionChart component
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ModelContributionChart from './ModelContributionChart';

import type { ModelContribution } from './ModelContributionChart';

const mockContributions: ModelContribution[] = [
  { modelName: 'RT-DETRv2', rate: 1.0, eventCount: 1000 },
  { modelName: 'YOLO-World', rate: 0.85, eventCount: 850 },
  { modelName: 'Florence-2', rate: 0.72, eventCount: 720 },
  { modelName: 'Fashion-CLIP', rate: 0.45, eventCount: 450 },
];

describe('ModelContributionChart', () => {
  it('renders chart title', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    expect(screen.getByText('Model Contribution Breakdown')).toBeInTheDocument();
  });

  it('renders chart subtitle', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    expect(screen.getByText(/percentage of events/i)).toBeInTheDocument();
  });

  it('displays all model names', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    expect(screen.getByText('YOLO-World')).toBeInTheDocument();
    expect(screen.getByText('Florence-2')).toBeInTheDocument();
    expect(screen.getByText('Fashion-CLIP')).toBeInTheDocument();
  });

  it('displays contribution rates as percentages', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  it('displays event counts for each model', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    expect(screen.getByText('1,000 events')).toBeInTheDocument();
    expect(screen.getByText('850 events')).toBeInTheDocument();
    expect(screen.getByText('720 events')).toBeInTheDocument();
    expect(screen.getByText('450 events')).toBeInTheDocument();
  });

  it('renders progress bars with correct widths', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    const progressBars = screen.getAllByRole('progressbar');
    expect(progressBars).toHaveLength(4);

    expect(progressBars[0]).toHaveStyle({ width: '100%' });
    expect(progressBars[1]).toHaveStyle({ width: '85%' });
    expect(progressBars[2]).toHaveStyle({ width: '72%' });
    expect(progressBars[3]).toHaveStyle({ width: '45%' });
  });

  it('renders empty state when no contributions provided', () => {
    render(<ModelContributionChart contributions={[]} />);

    expect(screen.getByText(/no contribution data/i)).toBeInTheDocument();
  });

  it('renders with correct data-testid', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    expect(screen.getByTestId('model-contribution-chart')).toBeInTheDocument();
  });

  it('sorts models by contribution rate descending', () => {
    const unsortedContributions: ModelContribution[] = [
      { modelName: 'Fashion-CLIP', rate: 0.45, eventCount: 450 },
      { modelName: 'RT-DETRv2', rate: 1.0, eventCount: 1000 },
      { modelName: 'Florence-2', rate: 0.72, eventCount: 720 },
      { modelName: 'YOLO-World', rate: 0.85, eventCount: 850 },
    ];

    render(<ModelContributionChart contributions={unsortedContributions} />);

    const modelNames = screen
      .getAllByRole('progressbar')
      .map((el) => el.getAttribute('aria-label'));
    expect(modelNames[0]).toContain('RT-DETRv2');
    expect(modelNames[1]).toContain('YOLO-World');
    expect(modelNames[2]).toContain('Florence-2');
    expect(modelNames[3]).toContain('Fashion-CLIP');
  });

  it('renders accessible progress bars with correct attributes', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    const progressBars = screen.getAllByRole('progressbar');

    expect(progressBars[0]).toHaveAttribute('aria-label', expect.stringContaining('RT-DETRv2'));
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '100');
    expect(progressBars[0]).toHaveAttribute('aria-valuemin', '0');
    expect(progressBars[0]).toHaveAttribute('aria-valuemax', '100');
  });

  it('handles zero contribution rate', () => {
    const zeroContribution: ModelContribution[] = [
      { modelName: 'Unused-Model', rate: 0, eventCount: 0 },
    ];

    render(<ModelContributionChart contributions={zeroContribution} />);

    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.getByText('0 events')).toBeInTheDocument();
  });

  it('formats large event counts with commas', () => {
    const largeCount: ModelContribution[] = [
      { modelName: 'RT-DETRv2', rate: 1.0, eventCount: 12345 },
    ];

    render(<ModelContributionChart contributions={largeCount} />);

    expect(screen.getByText('12,345 events')).toBeInTheDocument();
  });

  it('applies gradient color to progress bars', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    const progressBars = screen.getAllByRole('progressbar');
    progressBars.forEach((bar) => {
      expect(bar).toHaveClass('bg-gradient-to-r');
    });
  });

  it('displays model icons for known models', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    // Check that icons are rendered (they should be visible)
    const container = screen.getByTestId('model-contribution-chart');
    expect(container.querySelectorAll('svg').length).toBeGreaterThan(0);
  });

  it('handles single contribution', () => {
    const singleContribution: ModelContribution[] = [
      { modelName: 'RT-DETRv2', rate: 1.0, eventCount: 100 },
    ];

    render(<ModelContributionChart contributions={singleContribution} />);

    expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('displays contribution rate hover tooltip', () => {
    render(<ModelContributionChart contributions={mockContributions} />);

    const progressBars = screen.getAllByRole('progressbar');
    expect(progressBars[0]).toHaveAttribute('title', expect.stringContaining('100%'));
  });
});
