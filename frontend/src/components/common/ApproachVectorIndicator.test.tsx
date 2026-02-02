/**
 * Tests for ApproachVectorIndicator component (NEM-5024 Phase 6)
 *
 * This component displays approach vector information on detection cards:
 * - Directional arrow showing approach direction
 * - Speed indication
 * - ETA countdown
 * - Zone name being approached
 *
 * @module components/common/ApproachVectorIndicator.test
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ApproachVectorIndicator from './ApproachVectorIndicator';

import type { ApproachVectorIndicatorProps } from './ApproachVectorIndicator';

// ============================================================================
// Test Data
// ============================================================================

const defaultProps: ApproachVectorIndicatorProps = {
  isApproaching: true,
  directionDegrees: 45,
  speedNormalized: 0.05,
  estimatedArrivalSeconds: 5,
  zoneName: 'Front Door',
  urgency: 'approaching',
};

// ============================================================================
// Component Tests
// ============================================================================

describe('ApproachVectorIndicator', () => {
  describe('Rendering', () => {
    it('should render when entity is approaching', () => {
      render(<ApproachVectorIndicator {...defaultProps} />);

      expect(screen.getByTestId('approach-vector-indicator')).toBeInTheDocument();
    });

    it('should not render when entity is not approaching', () => {
      render(<ApproachVectorIndicator {...defaultProps} isApproaching={false} />);

      expect(screen.queryByTestId('approach-vector-indicator')).not.toBeInTheDocument();
    });

    it('should display zone name in text', () => {
      render(<ApproachVectorIndicator {...defaultProps} />);

      expect(screen.getByText(/Front Door/)).toBeInTheDocument();
    });

    it('should display ETA when available', () => {
      render(<ApproachVectorIndicator {...defaultProps} estimatedArrivalSeconds={5} />);

      expect(screen.getByText(/5s/)).toBeInTheDocument();
    });

    it('should display "Now" when ETA is 0', () => {
      render(<ApproachVectorIndicator {...defaultProps} estimatedArrivalSeconds={0} />);

      expect(screen.getByText(/Now/)).toBeInTheDocument();
    });

    it('should display "<1s" when ETA is less than 1 second', () => {
      render(<ApproachVectorIndicator {...defaultProps} estimatedArrivalSeconds={0.5} />);

      expect(screen.getByText(/<1s/)).toBeInTheDocument();
    });

    it('should not display ETA when null', () => {
      render(<ApproachVectorIndicator {...defaultProps} estimatedArrivalSeconds={null} />);

      // Should still render the indicator but without ETA text
      expect(screen.getByTestId('approach-vector-indicator')).toBeInTheDocument();
      expect(screen.queryByText(/ETA:/)).not.toBeInTheDocument();
    });

    it('should render directional arrow', () => {
      render(<ApproachVectorIndicator {...defaultProps} />);

      expect(screen.getByTestId('direction-arrow')).toBeInTheDocument();
    });
  });

  describe('Urgency Colors', () => {
    it('should use red styling for imminent urgency', () => {
      render(<ApproachVectorIndicator {...defaultProps} urgency="imminent" />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveClass('border-red-500');
    });

    it('should use yellow/amber styling for approaching urgency', () => {
      render(<ApproachVectorIndicator {...defaultProps} urgency="approaching" />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveClass('border-amber-500');
    });

    it('should use green styling for distant urgency', () => {
      render(<ApproachVectorIndicator {...defaultProps} urgency="distant" />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveClass('border-green-500');
    });
  });

  describe('Direction Arrow', () => {
    it('should rotate arrow based on direction degrees', () => {
      render(<ApproachVectorIndicator {...defaultProps} directionDegrees={90} />);

      const arrow = screen.getByTestId('direction-arrow');
      // Arrow should be rotated to point in the direction of movement
      expect(arrow).toHaveStyle({ transform: 'rotate(90deg)' });
    });

    it('should handle 0 degrees (up)', () => {
      render(<ApproachVectorIndicator {...defaultProps} directionDegrees={0} />);

      const arrow = screen.getByTestId('direction-arrow');
      expect(arrow).toHaveStyle({ transform: 'rotate(0deg)' });
    });

    it('should handle 180 degrees (down)', () => {
      render(<ApproachVectorIndicator {...defaultProps} directionDegrees={180} />);

      const arrow = screen.getByTestId('direction-arrow');
      expect(arrow).toHaveStyle({ transform: 'rotate(180deg)' });
    });

    it('should handle 270 degrees (left)', () => {
      render(<ApproachVectorIndicator {...defaultProps} directionDegrees={270} />);

      const arrow = screen.getByTestId('direction-arrow');
      expect(arrow).toHaveStyle({ transform: 'rotate(270deg)' });
    });
  });

  describe('Text Display', () => {
    it('should show "Approaching {zoneName} - ETA {time}" format', () => {
      render(
        <ApproachVectorIndicator
          {...defaultProps}
          zoneName="Back Yard"
          estimatedArrivalSeconds={10}
        />
      );

      // Text is split across elements, so check individually
      expect(screen.getByText(/Approaching/)).toBeInTheDocument();
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
      expect(screen.getByText(/ETA: 10s/)).toBeInTheDocument();
    });

    it('should handle long zone names', () => {
      render(
        <ApproachVectorIndicator
          {...defaultProps}
          zoneName="Very Long Zone Name That Should Truncate"
        />
      );

      expect(screen.getByTestId('approach-vector-indicator')).toBeInTheDocument();
    });
  });

  describe('Size Variants', () => {
    it('should render small size correctly', () => {
      render(<ApproachVectorIndicator {...defaultProps} size="sm" />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveClass('text-xs');
    });

    it('should render medium size correctly (default)', () => {
      render(<ApproachVectorIndicator {...defaultProps} />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveClass('text-sm');
    });

    it('should render large size correctly', () => {
      render(<ApproachVectorIndicator {...defaultProps} size="lg" />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveClass('text-base');
    });
  });

  describe('Accessibility', () => {
    it('should have appropriate aria-label', () => {
      render(<ApproachVectorIndicator {...defaultProps} />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Approaching Front Door')
      );
    });

    it('should include ETA in aria-label when available', () => {
      render(<ApproachVectorIndicator {...defaultProps} estimatedArrivalSeconds={5} />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveAttribute('aria-label', expect.stringContaining('5 seconds'));
    });
  });

  describe('Custom className', () => {
    it('should apply custom className', () => {
      render(<ApproachVectorIndicator {...defaultProps} className="custom-class" />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveClass('custom-class');
    });
  });

  describe('Pulse Animation', () => {
    it('should pulse for imminent urgency', () => {
      render(<ApproachVectorIndicator {...defaultProps} urgency="imminent" />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).toHaveClass('animate-pulse');
    });

    it('should not pulse for non-imminent urgencies', () => {
      render(<ApproachVectorIndicator {...defaultProps} urgency="approaching" />);

      const indicator = screen.getByTestId('approach-vector-indicator');
      expect(indicator).not.toHaveClass('animate-pulse');
    });
  });
});
