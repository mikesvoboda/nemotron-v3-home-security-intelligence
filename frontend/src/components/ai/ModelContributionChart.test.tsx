/**
 * Tests for ModelContributionChart component
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ModelContributionChart from './ModelContributionChart';

describe('ModelContributionChart', () => {
  const mockContributionRates = {
    rtdetr: 1.0,
    florence: 0.85,
    clip: 0.6,
    violence: 0.3,
    clothing: 0.5,
    vehicle: 0.4,
    pet: 0.25,
    weather: 0.2,
    image_quality: 0.7,
    zones: 0.65,
    baseline: 0.55,
    cross_camera: 0.15,
  };

  it('renders the chart container', () => {
    render(<ModelContributionChart contributionRates={mockContributionRates} />);
    expect(screen.getByTestId('model-contribution-chart')).toBeInTheDocument();
  });

  it('renders the chart title', () => {
    render(<ModelContributionChart contributionRates={mockContributionRates} />);
    expect(screen.getByText('Model Contribution Rates')).toBeInTheDocument();
  });

  it('renders empty state when no data is provided', () => {
    render(<ModelContributionChart contributionRates={{}} />);
    expect(screen.getByText('No contribution data available')).toBeInTheDocument();
  });

  it('renders empty state when all rates are zero', () => {
    const zeroRates = {
      rtdetr: 0,
      florence: 0,
      clip: 0,
    };
    render(<ModelContributionChart contributionRates={zeroRates} />);
    expect(screen.getByText('No contribution data available')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(
      <ModelContributionChart contributionRates={mockContributionRates} className="custom-class" />
    );
    const container = screen.getByTestId('model-contribution-chart');
    expect(container).toHaveClass('custom-class');
  });
});
