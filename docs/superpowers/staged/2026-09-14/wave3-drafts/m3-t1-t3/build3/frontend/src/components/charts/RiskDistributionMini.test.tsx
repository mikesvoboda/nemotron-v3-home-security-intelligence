import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import RiskDistributionMini from './RiskDistributionMini';

import type { RiskDistributionItem } from '../../types/generated';

describe('RiskDistributionMini', () => {
  const mockDistribution: RiskDistributionItem[] = [
    { risk_level: 'critical', count: 2 },
    { risk_level: 'high', count: 5 },
    { risk_level: 'medium', count: 12 },
    { risk_level: 'low', count: 25 },
  ];

  describe('rendering', () => {
    it('renders the component', () => {
      render(<RiskDistributionMini distribution={mockDistribution} />);

      expect(screen.getByTestId('risk-distribution-mini')).toBeInTheDocument();
    });

    it('renders bars for each risk level', () => {
      render(<RiskDistributionMini distribution={mockDistribution} />);

      expect(screen.getByTestId('risk-bar-critical')).toBeInTheDocument();
      expect(screen.getByTestId('risk-bar-high')).toBeInTheDocument();
      expect(screen.getByTestId('risk-bar-medium')).toBeInTheDocument();
      expect(screen.getByTestId('risk-bar-low')).toBeInTheDocument();
    });

    it('renders label', () => {
      render(<RiskDistributionMini distribution={mockDistribution} />);

      expect(screen.getByText('Risk Distribution')).toBeInTheDocument();
    });
  });

  describe('bar widths', () => {
    it('calculates bar widths proportionally', () => {
      render(<RiskDistributionMini distribution={mockDistribution} />);

      // Total is 44, so:
      // critical: 2/44 = ~4.5%
      // high: 5/44 = ~11.4%
      // medium: 12/44 = ~27.3%
      // low: 25/44 = ~56.8%
      const criticalBar = screen.getByTestId('risk-bar-critical');
      const lowBar = screen.getByTestId('risk-bar-low');

      // Get computed flex values from style
      const criticalFlex = criticalBar.style.flex;
      const lowFlex = lowBar.style.flex;

      // Both should have flex values set
      expect(criticalFlex).toBeTruthy();
      expect(lowFlex).toBeTruthy();

      // Low should have larger flex value than critical (parse the first number in flex shorthand)
      const criticalValue = parseFloat(criticalFlex.split(' ')[0]);
      const lowValue = parseFloat(lowFlex.split(' ')[0]);
      expect(lowValue).toBeGreaterThan(criticalValue);
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<RiskDistributionMini distribution={mockDistribution} className="custom-class" />);

      const container = screen.getByTestId('risk-distribution-mini');
      expect(container).toHaveClass('custom-class');
    });

    it('uses correct colors for risk levels', () => {
      render(<RiskDistributionMini distribution={mockDistribution} />);

      expect(screen.getByTestId('risk-bar-critical')).toHaveClass('bg-red-500');
      expect(screen.getByTestId('risk-bar-high')).toHaveClass('bg-orange-500');
      expect(screen.getByTestId('risk-bar-medium')).toHaveClass('bg-yellow-500');
      expect(screen.getByTestId('risk-bar-low')).toHaveClass('bg-green-500');
    });
  });

  describe('edge cases', () => {
    it('handles undefined distribution', () => {
      render(<RiskDistributionMini distribution={undefined} />);

      const container = screen.getByTestId('risk-distribution-mini');
      expect(container).toBeInTheDocument();
    });

    it('handles empty distribution', () => {
      render(<RiskDistributionMini distribution={[]} />);

      const container = screen.getByTestId('risk-distribution-mini');
      expect(container).toBeInTheDocument();
    });

    it('handles zero total events', () => {
      const zeroDistribution: RiskDistributionItem[] = [
        { risk_level: 'critical', count: 0 },
        { risk_level: 'high', count: 0 },
        { risk_level: 'medium', count: 0 },
        { risk_level: 'low', count: 0 },
      ];

      render(<RiskDistributionMini distribution={zeroDistribution} />);

      // Should render without crashing
      expect(screen.getByTestId('risk-distribution-mini')).toBeInTheDocument();
    });

    it('handles partial distribution (only some risk levels)', () => {
      const partialDistribution: RiskDistributionItem[] = [
        { risk_level: 'high', count: 10 },
        { risk_level: 'low', count: 20 },
      ];

      render(<RiskDistributionMini distribution={partialDistribution} />);

      expect(screen.getByTestId('risk-bar-high')).toBeInTheDocument();
      expect(screen.getByTestId('risk-bar-low')).toBeInTheDocument();
      // Missing levels should not throw
      expect(screen.queryByTestId('risk-bar-critical')).not.toBeInTheDocument();
      expect(screen.queryByTestId('risk-bar-medium')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has aria-label on container', () => {
      render(<RiskDistributionMini distribution={mockDistribution} />);

      const container = screen.getByTestId('risk-distribution-mini');
      expect(container).toHaveAttribute('aria-label', 'Risk distribution chart');
    });

    it('has aria-label on bars with count information', () => {
      render(<RiskDistributionMini distribution={mockDistribution} />);

      const criticalBar = screen.getByTestId('risk-bar-critical');
      expect(criticalBar).toHaveAttribute('aria-label', 'Critical: 2 events');

      const lowBar = screen.getByTestId('risk-bar-low');
      expect(lowBar).toHaveAttribute('aria-label', 'Low: 25 events');
    });
  });
});
