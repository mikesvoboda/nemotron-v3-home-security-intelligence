/**
 * RiskFactorsBreakdown component tests (NEM-3603)
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RiskFactorsBreakdown from './RiskFactorsBreakdown';

import type { RiskFactor } from '../../types/risk-analysis';

describe('RiskFactorsBreakdown', () => {
  const mockFactors: RiskFactor[] = [
    {
      factor_name: 'nighttime_activity',
      contribution: 15.0,
      description: 'Activity detected outside normal hours (11 PM - 6 AM)',
    },
    {
      factor_name: 'unknown_person',
      contribution: 20.0,
      description: 'Person not recognized by face detection',
    },
    {
      factor_name: 'routine_location',
      contribution: -10.0,
      description: 'Activity at commonly used entrance',
    },
    {
      factor_name: 'recognized_face',
      contribution: -25.0,
      description: 'Face matched to known household member',
    },
    {
      factor_name: 'small_contribution',
      contribution: 5.0,
      description: null,
    },
  ];

  describe('rendering', () => {
    it('renders nothing when riskFactors is null', () => {
      const { container } = render(<RiskFactorsBreakdown riskFactors={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when riskFactors is undefined', () => {
      const { container } = render(<RiskFactorsBreakdown riskFactors={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when riskFactors is empty array', () => {
      const { container } = render(<RiskFactorsBreakdown riskFactors={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders the panel with factors', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      expect(screen.getByTestId('risk-factors-breakdown')).toBeInTheDocument();
      expect(screen.getByText('Risk Factors')).toBeInTheDocument();
    });

    it('displays the factor count badge', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('renders all factor items', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      const factorItems = screen.getAllByTestId('risk-factor-item');
      expect(factorItems).toHaveLength(5);
    });
  });

  describe('factor formatting', () => {
    it('formats factor names from snake_case to Title Case', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      expect(screen.getByText('Nighttime Activity')).toBeInTheDocument();
      expect(screen.getByText('Unknown Person')).toBeInTheDocument();
      expect(screen.getByText('Routine Location')).toBeInTheDocument();
      expect(screen.getByText('Recognized Face')).toBeInTheDocument();
    });

    it('displays contribution values with correct formatting', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      // Positive contributions have + sign
      expect(screen.getByText('+15.0')).toBeInTheDocument();
      expect(screen.getByText('+20.0')).toBeInTheDocument();
      expect(screen.getByText('+5.0')).toBeInTheDocument();

      // Negative contributions have - sign (implicit)
      expect(screen.getByText('-10.0')).toBeInTheDocument();
      expect(screen.getByText('-25.0')).toBeInTheDocument();
    });

    it('displays descriptions when provided', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      expect(
        screen.getByText('Activity detected outside normal hours (11 PM - 6 AM)')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Person not recognized by face detection')
      ).toBeInTheDocument();
    });

    it('handles factors without descriptions', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      expect(screen.getByText('Small Contribution')).toBeInTheDocument();
      // Should not crash and factor should still render
      const factorItems = screen.getAllByTestId('risk-factor-item');
      expect(factorItems).toHaveLength(5);
    });
  });

  describe('sorting', () => {
    it('sorts factors by absolute contribution magnitude (largest first)', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      const factorItems = screen.getAllByTestId('risk-factor-item');

      // First should be recognized_face (-25.0, magnitude 25)
      expect(factorItems[0]).toHaveTextContent('Recognized Face');
      // Second should be unknown_person (+20.0, magnitude 20)
      expect(factorItems[1]).toHaveTextContent('Unknown Person');
      // Third should be nighttime_activity (+15.0, magnitude 15)
      expect(factorItems[2]).toHaveTextContent('Nighttime Activity');
      // Fourth should be routine_location (-10.0, magnitude 10)
      expect(factorItems[3]).toHaveTextContent('Routine Location');
      // Fifth should be small_contribution (+5.0, magnitude 5)
      expect(factorItems[4]).toHaveTextContent('Small Contribution');
    });
  });

  describe('summary totals', () => {
    it('displays positive contribution total', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      // Total positive: 15 + 20 + 5 = 40
      expect(screen.getByText('+40.0')).toBeInTheDocument();
    });

    it('displays negative contribution total', () => {
      render(<RiskFactorsBreakdown riskFactors={mockFactors} />);

      // Total negative: -10 + -25 = -35
      expect(screen.getByText('-35.0')).toBeInTheDocument();
    });

    it('hides positive total when no positive factors', () => {
      const negativeOnly: RiskFactor[] = [
        { factor_name: 'test', contribution: -10.0, description: null },
      ];
      render(<RiskFactorsBreakdown riskFactors={negativeOnly} />);

      // Should show negative total in the summary (in the header area)
      // The summary uses TrendingDown icon and text-green-400 class
      const panel = screen.getByTestId('risk-factors-breakdown');
      expect(panel).toHaveTextContent('-10.0');

      // Should NOT have any positive total indicator (TrendingUp in header with text-red-400)
      // The summary for positive uses "+" prefix
      const headerDiv = panel.querySelector('.flex.items-center.justify-between');
      expect(headerDiv).not.toHaveTextContent(/^\+\d/);
    });

    it('hides negative total when no negative factors', () => {
      const positiveOnly: RiskFactor[] = [
        { factor_name: 'test', contribution: 10.0, description: null },
      ];
      render(<RiskFactorsBreakdown riskFactors={positiveOnly} />);

      // Should show positive total in the summary (text-red-400 class)
      // Using getAllByText since the value appears in both summary and item
      const positiveTexts = screen.getAllByText('+10.0');
      expect(positiveTexts.length).toBeGreaterThanOrEqual(1);

      // Should NOT have any negative total indicator (text-green-400 with TrendingDown)
      expect(screen.queryByText(/^-\d/, { selector: '.text-green-400' })).not.toBeInTheDocument();
    });
  });

  describe('color coding', () => {
    it('applies red styling for high positive contributions (>10)', () => {
      const highPositive: RiskFactor[] = [
        { factor_name: 'high_risk', contribution: 15.0, description: null },
      ];
      render(<RiskFactorsBreakdown riskFactors={highPositive} />);

      const factorItem = screen.getByTestId('risk-factor-item');
      expect(factorItem.className).toMatch(/red/);
    });

    it('applies orange styling for low positive contributions (0-10)', () => {
      const lowPositive: RiskFactor[] = [
        { factor_name: 'low_risk', contribution: 5.0, description: null },
      ];
      render(<RiskFactorsBreakdown riskFactors={lowPositive} />);

      const factorItem = screen.getByTestId('risk-factor-item');
      expect(factorItem.className).toMatch(/orange/);
    });

    it('applies green styling for high negative contributions (<-10)', () => {
      const highNegative: RiskFactor[] = [
        { factor_name: 'safe', contribution: -15.0, description: null },
      ];
      render(<RiskFactorsBreakdown riskFactors={highNegative} />);

      const factorItem = screen.getByTestId('risk-factor-item');
      expect(factorItem.className).toMatch(/green/);
    });

    it('applies emerald styling for low negative contributions (-10 to 0)', () => {
      const lowNegative: RiskFactor[] = [
        { factor_name: 'slightly_safe', contribution: -5.0, description: null },
      ];
      render(<RiskFactorsBreakdown riskFactors={lowNegative} />);

      const factorItem = screen.getByTestId('risk-factor-item');
      expect(factorItem.className).toMatch(/emerald/);
    });

    it('applies gray styling for zero contribution', () => {
      const neutral: RiskFactor[] = [
        { factor_name: 'neutral', contribution: 0, description: null },
      ];
      render(<RiskFactorsBreakdown riskFactors={neutral} />);

      const factorItem = screen.getByTestId('risk-factor-item');
      expect(factorItem.className).toMatch(/gray/);
    });
  });

  describe('className prop', () => {
    it('applies custom className', () => {
      render(
        <RiskFactorsBreakdown
          riskFactors={mockFactors}
          className="custom-class"
        />
      );

      const panel = screen.getByTestId('risk-factors-breakdown');
      expect(panel.className).toContain('custom-class');
    });
  });
});
