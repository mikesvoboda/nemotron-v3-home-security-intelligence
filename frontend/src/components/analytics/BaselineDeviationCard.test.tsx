/**
 * Tests for BaselineDeviationCard component
 *
 * This component displays the current deviation from baseline with color-coded
 * visual indicators based on deviation interpretation.
 * Tests verify proper rendering, color mapping, deviation display, and edge cases.
 *
 * Tests cover:
 * - Rendering with deviation data
 * - Color coding for each interpretation level:
 *   - far_below_normal -> blue
 *   - below_normal -> light blue
 *   - normal -> green
 *   - slightly_above_normal -> yellow
 *   - above_normal -> orange
 *   - far_above_normal -> red
 * - Score display with correct sign (+/-)
 * - Interpretation text display
 * - Contributing factors as badges
 * - Null deviation (no data) state
 * - Icon selection based on interpretation
 * - Accessibility attributes
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import BaselineDeviationCard from './BaselineDeviationCard';

import type { CurrentDeviation } from '../../services/api';

describe('BaselineDeviationCard', () => {
  // Mock deviations for each interpretation level
  const mockDeviationFarBelowNormal: CurrentDeviation = {
    score: -3.5,
    interpretation: 'far_below_normal',
    contributing_factors: ['person_count_low', 'unusual_quiet_period'],
  };

  const mockDeviationBelowNormal: CurrentDeviation = {
    score: -1.8,
    interpretation: 'below_normal',
    contributing_factors: ['person_count_low'],
  };

  const mockDeviationNormal: CurrentDeviation = {
    score: 0.2,
    interpretation: 'normal',
    contributing_factors: [],
  };

  const mockDeviationSlightlyAboveNormal: CurrentDeviation = {
    score: 1.8,
    interpretation: 'slightly_above_normal',
    contributing_factors: ['person_count_elevated'],
  };

  const mockDeviationAboveNormal: CurrentDeviation = {
    score: 2.5,
    interpretation: 'above_normal',
    contributing_factors: ['person_count_elevated', 'vehicle_count_elevated'],
  };

  const mockDeviationFarAboveNormal: CurrentDeviation = {
    score: 4.2,
    interpretation: 'far_above_normal',
    contributing_factors: [
      'person_count_elevated',
      'vehicle_count_elevated',
      'unusual_time',
    ],
  };

  describe('rendering with data', () => {
    it('renders the card title', () => {
      render(<BaselineDeviationCard deviation={mockDeviationNormal} />);

      expect(screen.getByText('Current Activity Status')).toBeInTheDocument();
    });

    it('renders card container', () => {
      render(<BaselineDeviationCard deviation={mockDeviationNormal} />);

      expect(screen.getByTestId('baseline-deviation-card')).toBeInTheDocument();
    });

    it('displays deviation score', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(screen.getByTestId('deviation-score')).toHaveTextContent('+2.5');
    });

    it('displays interpretation text', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(screen.getByTestId('deviation-interpretation')).toHaveTextContent('Above Normal');
    });
  });

  describe('color coding by interpretation', () => {
    it('applies blue color for far_below_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarBelowNormal} />);

      const card = screen.getByTestId('baseline-deviation-card');
      expect(card).toHaveClass(/bg-blue-/);
      expect(card).toHaveClass(/border-blue-/);
    });

    it('applies light blue color for below_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationBelowNormal} />);

      const card = screen.getByTestId('baseline-deviation-card');
      expect(card).toHaveClass(/bg-blue-100/);
    });

    it('applies green color for normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationNormal} />);

      const card = screen.getByTestId('baseline-deviation-card');
      expect(card).toHaveClass(/bg-green-/);
      expect(card).toHaveClass(/border-green-/);
    });

    it('applies yellow color for slightly_above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationSlightlyAboveNormal} />);

      const card = screen.getByTestId('baseline-deviation-card');
      expect(card).toHaveClass(/bg-yellow-/);
      expect(card).toHaveClass(/border-yellow-/);
    });

    it('applies orange color for above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      const card = screen.getByTestId('baseline-deviation-card');
      expect(card).toHaveClass(/bg-orange-/);
      expect(card).toHaveClass(/border-orange-/);
    });

    it('applies red color for far_above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarAboveNormal} />);

      const card = screen.getByTestId('baseline-deviation-card');
      expect(card).toHaveClass(/bg-red-/);
      expect(card).toHaveClass(/border-red-/);
    });
  });

  describe('score display', () => {
    it('displays positive score with + sign', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(screen.getByTestId('deviation-score')).toHaveTextContent('+2.5');
    });

    it('displays negative score with - sign', () => {
      render(<BaselineDeviationCard deviation={mockDeviationBelowNormal} />);

      expect(screen.getByTestId('deviation-score')).toHaveTextContent('-1.8');
    });

    it('displays score near zero with + sign', () => {
      render(<BaselineDeviationCard deviation={mockDeviationNormal} />);

      expect(screen.getByTestId('deviation-score')).toHaveTextContent('+0.2');
    });

    it('formats score to 1 decimal place', () => {
      const deviation: CurrentDeviation = {
        score: 2.5678,
        interpretation: 'above_normal',
        contributing_factors: [],
      };

      render(<BaselineDeviationCard deviation={deviation} />);

      expect(screen.getByTestId('deviation-score')).toHaveTextContent('+2.6');
    });

    it('displays standard deviation label', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(screen.getByText(/standard deviations/i)).toBeInTheDocument();
    });
  });

  describe('interpretation text', () => {
    it('displays human-readable interpretation for far_below_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarBelowNormal} />);

      expect(screen.getByTestId('deviation-interpretation')).toHaveTextContent(
        'Far Below Normal'
      );
    });

    it('displays human-readable interpretation for below_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationBelowNormal} />);

      expect(screen.getByTestId('deviation-interpretation')).toHaveTextContent('Below Normal');
    });

    it('displays human-readable interpretation for normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationNormal} />);

      expect(screen.getByTestId('deviation-interpretation')).toHaveTextContent('Normal');
    });

    it('displays human-readable interpretation for slightly_above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationSlightlyAboveNormal} />);

      expect(screen.getByTestId('deviation-interpretation')).toHaveTextContent(
        'Slightly Above Normal'
      );
    });

    it('displays human-readable interpretation for above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(screen.getByTestId('deviation-interpretation')).toHaveTextContent('Above Normal');
    });

    it('displays human-readable interpretation for far_above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarAboveNormal} />);

      expect(screen.getByTestId('deviation-interpretation')).toHaveTextContent(
        'Far Above Normal'
      );
    });
  });

  describe('contributing factors', () => {
    it('displays contributing factors as badges', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarAboveNormal} />);

      expect(screen.getByTestId('contributing-factors')).toBeInTheDocument();
      expect(screen.getByText('person_count_elevated')).toBeInTheDocument();
      expect(screen.getByText('vehicle_count_elevated')).toBeInTheDocument();
      expect(screen.getByText('unusual_time')).toBeInTheDocument();
    });

    it('displays multiple factors as separate badges', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      const badges = screen.getAllByTestId(/^factor-badge-/);
      expect(badges).toHaveLength(2);
    });

    it('does not render factors section when empty', () => {
      render(<BaselineDeviationCard deviation={mockDeviationNormal} />);

      expect(screen.queryByTestId('contributing-factors')).not.toBeInTheDocument();
    });

    it('formats factor names as human-readable', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(screen.getByText('Person Count Elevated')).toBeInTheDocument();
      expect(screen.getByText('Vehicle Count Elevated')).toBeInTheDocument();
    });

    it('displays factors section header', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(screen.getByText(/Contributing Factors/i)).toBeInTheDocument();
    });
  });

  describe('null deviation state', () => {
    it('shows no data state when deviation is null', () => {
      render(<BaselineDeviationCard deviation={null} />);

      expect(screen.getByTestId('deviation-no-data')).toBeInTheDocument();
      expect(screen.getByText(/No deviation data available/i)).toBeInTheDocument();
    });

    it('shows helpful message in no data state', () => {
      render(<BaselineDeviationCard deviation={null} />);

      expect(
        screen.getByText(/Baseline data is still being collected/i)
      ).toBeInTheDocument();
    });

    it('does not show score or interpretation in no data state', () => {
      render(<BaselineDeviationCard deviation={null} />);

      expect(screen.queryByTestId('deviation-score')).not.toBeInTheDocument();
      expect(screen.queryByTestId('deviation-interpretation')).not.toBeInTheDocument();
    });

    it('does not show contributing factors in no data state', () => {
      render(<BaselineDeviationCard deviation={null} />);

      expect(screen.queryByTestId('contributing-factors')).not.toBeInTheDocument();
    });
  });

  describe('icons and visual indicators', () => {
    it('displays down arrow icon for far_below_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarBelowNormal} />);

      expect(screen.getByTestId('deviation-icon')).toHaveClass(/arrow-down/);
    });

    it('displays down arrow icon for below_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationBelowNormal} />);

      expect(screen.getByTestId('deviation-icon')).toHaveClass(/arrow-down/);
    });

    it('displays check icon for normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationNormal} />);

      expect(screen.getByTestId('deviation-icon')).toHaveClass(/check/);
    });

    it('displays up arrow icon for slightly_above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationSlightlyAboveNormal} />);

      expect(screen.getByTestId('deviation-icon')).toHaveClass(/arrow-up/);
    });

    it('displays up arrow icon for above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(screen.getByTestId('deviation-icon')).toHaveClass(/arrow-up/);
    });

    it('displays alert icon for far_above_normal', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarAboveNormal} />);

      expect(screen.getByTestId('deviation-icon')).toHaveClass(/alert/);
    });
  });

  describe('additional information', () => {
    it('displays explanation of deviation score', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      expect(
        screen.getByText(/measures how far current activity differs from typical patterns/i)
      ).toBeInTheDocument();
    });

    it('displays timestamp of last update', () => {
      const deviationWithTimestamp: CurrentDeviation & { last_updated?: string } = {
        ...mockDeviationAboveNormal,
        last_updated: '2026-01-31T10:30:00Z',
      };

      render(<BaselineDeviationCard deviation={deviationWithTimestamp} />);

      expect(screen.getByText(/Last updated/i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      const card = screen.getByTestId('baseline-deviation-card');
      expect(card).toHaveAttribute(
        'aria-label',
        'Current activity status: Above Normal, +2.5 standard deviations'
      );
    });

    it('uses semantic color for screen readers', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarAboveNormal} />);

      expect(screen.getByTestId('deviation-interpretation')).toHaveAttribute(
        'aria-live',
        'polite'
      );
    });

    it('factor badges are keyboard accessible', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      const badges = screen.getAllByTestId(/^factor-badge-/);
      badges.forEach((badge) => {
        expect(badge).toHaveAttribute('role', 'listitem');
      });
    });
  });

  describe('responsive layout', () => {
    it('stacks vertically on mobile', () => {
      render(<BaselineDeviationCard deviation={mockDeviationAboveNormal} />);

      const card = screen.getByTestId('baseline-deviation-card');
      expect(card).toHaveClass(/flex-col/);
    });

    it('displays factors in grid on larger screens', () => {
      render(<BaselineDeviationCard deviation={mockDeviationFarAboveNormal} />);

      const factorsContainer = screen.getByTestId('contributing-factors');
      expect(factorsContainer).toHaveClass(/grid/);
    });
  });

  describe('edge cases', () => {
    it('handles extremely large positive deviation', () => {
      const extremeDeviation: CurrentDeviation = {
        score: 10.5,
        interpretation: 'far_above_normal',
        contributing_factors: ['extreme_activity'],
      };

      render(<BaselineDeviationCard deviation={extremeDeviation} />);

      expect(screen.getByTestId('deviation-score')).toHaveTextContent('+10.5');
    });

    it('handles extremely large negative deviation', () => {
      const extremeDeviation: CurrentDeviation = {
        score: -8.2,
        interpretation: 'far_below_normal',
        contributing_factors: ['no_activity'],
      };

      render(<BaselineDeviationCard deviation={extremeDeviation} />);

      expect(screen.getByTestId('deviation-score')).toHaveTextContent('-8.2');
    });

    it('handles score of exactly zero', () => {
      const zeroDeviation: CurrentDeviation = {
        score: 0.0,
        interpretation: 'normal',
        contributing_factors: [],
      };

      render(<BaselineDeviationCard deviation={zeroDeviation} />);

      expect(screen.getByTestId('deviation-score')).toHaveTextContent('0.0');
    });

    it('handles very long factor names', () => {
      const deviationWithLongFactors: CurrentDeviation = {
        score: 2.5,
        interpretation: 'above_normal',
        contributing_factors: [
          'very_long_contributing_factor_name_that_might_overflow',
        ],
      };

      render(<BaselineDeviationCard deviation={deviationWithLongFactors} />);

      const badge = screen.getByTestId('factor-badge-0');
      expect(badge).toHaveClass(/truncate/);
    });
  });
});
