import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import StatsRow from './StatsRow';

describe('StatsRow', () => {
  const defaultProps = {
    activeCameras: 5,
    eventsToday: 12,
    currentRiskScore: 45,
    systemStatus: 'healthy' as const,
  };

  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<StatsRow {...defaultProps} />);
      expect(screen.getByRole('region', { name: /dashboard statistics/i })).toBeInTheDocument();
    });

    it('renders all four stat cards', () => {
      render(<StatsRow {...defaultProps} />);

      // Check for stat labels
      expect(screen.getByText('Active Cameras')).toBeInTheDocument();
      expect(screen.getByText('Events Today')).toBeInTheDocument();
      expect(screen.getByText('System Status')).toBeInTheDocument();

      // Risk label is dynamic based on score
      expect(screen.getByTestId('risk-label')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<StatsRow {...defaultProps} className="custom-class" />);
      const statsRow = container.querySelector('.custom-class');
      expect(statsRow).toBeInTheDocument();
    });
  });

  describe('Active Cameras Display', () => {
    it('displays correct active cameras count', () => {
      render(<StatsRow {...defaultProps} activeCameras={8} />);
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('8');
    });

    it('displays zero cameras', () => {
      render(<StatsRow {...defaultProps} activeCameras={0} />);
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('0');
    });

    it('displays large camera count', () => {
      render(<StatsRow {...defaultProps} activeCameras={99} />);
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('99');
    });
  });

  describe('Events Today Display', () => {
    it('displays correct events today count', () => {
      render(<StatsRow {...defaultProps} eventsToday={25} />);
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('25');
    });

    it('displays zero events', () => {
      render(<StatsRow {...defaultProps} eventsToday={0} />);
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('0');
    });

    it('displays large event count', () => {
      render(<StatsRow {...defaultProps} eventsToday={150} />);
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('150');
    });
  });

  describe('Risk Level Display', () => {
    it('displays low risk correctly', () => {
      render(<StatsRow {...defaultProps} currentRiskScore={15} />);
      expect(screen.getByTestId('risk-score')).toHaveTextContent('15');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Low');
    });

    it('displays medium risk correctly', () => {
      render(<StatsRow {...defaultProps} currentRiskScore={45} />);
      expect(screen.getByTestId('risk-score')).toHaveTextContent('45');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Medium');
    });

    it('displays high risk correctly', () => {
      render(<StatsRow {...defaultProps} currentRiskScore={65} />);
      expect(screen.getByTestId('risk-score')).toHaveTextContent('65');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('High');
    });

    it('displays critical risk correctly', () => {
      render(<StatsRow {...defaultProps} currentRiskScore={85} />);
      expect(screen.getByTestId('risk-score')).toHaveTextContent('85');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Critical');
    });

    it('displays zero risk score', () => {
      render(<StatsRow {...defaultProps} currentRiskScore={0} />);
      expect(screen.getByTestId('risk-score')).toHaveTextContent('0');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Low');
    });

    it('displays maximum risk score', () => {
      render(<StatsRow {...defaultProps} currentRiskScore={100} />);
      expect(screen.getByTestId('risk-score')).toHaveTextContent('100');
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Critical');
    });

    it('displays risk color styling', () => {
      render(<StatsRow {...defaultProps} currentRiskScore={85} />);
      const riskLabel = screen.getByTestId('risk-label');
      // Check that color style is applied (critical risk = red)
      expect(riskLabel).toHaveAttribute('style');
      expect(riskLabel.getAttribute('style')).toContain('color');
    });
  });

  describe('System Status Display', () => {
    it('displays healthy status', () => {
      render(<StatsRow {...defaultProps} systemStatus="healthy" />);
      expect(screen.getByTestId('system-status-label')).toHaveTextContent('Online');
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveClass('bg-green-500');
      expect(indicator).toHaveClass('animate-pulse');
    });

    it('displays degraded status', () => {
      render(<StatsRow {...defaultProps} systemStatus="degraded" />);
      expect(screen.getByTestId('system-status-label')).toHaveTextContent('Degraded');
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveClass('bg-yellow-500');
      expect(indicator).not.toHaveClass('animate-pulse');
    });

    it('displays unhealthy status', () => {
      render(<StatsRow {...defaultProps} systemStatus="unhealthy" />);
      expect(screen.getByTestId('system-status-label')).toHaveTextContent('Offline');
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveClass('bg-red-500');
      expect(indicator).not.toHaveClass('animate-pulse');
    });

    it('displays unknown status', () => {
      render(<StatsRow {...defaultProps} systemStatus="unknown" />);
      expect(screen.getByTestId('system-status-label')).toHaveTextContent('Unknown');
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveClass('bg-gray-500');
      expect(indicator).not.toHaveClass('animate-pulse');
    });

    it('has correct aria-label for status indicator', () => {
      render(<StatsRow {...defaultProps} systemStatus="healthy" />);
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'System status: Online');
    });
  });

  describe('Layout and Styling', () => {
    it('has responsive grid layout', () => {
      const { container } = render(<StatsRow {...defaultProps} />);
      const grid = container.firstChild;
      expect(grid).toHaveClass('grid');
      expect(grid).toHaveClass('grid-cols-1');
      expect(grid).toHaveClass('sm:grid-cols-2');
      expect(grid).toHaveClass('lg:grid-cols-4');
    });

    it('has correct dark theme styling', () => {
      const { container } = render(<StatsRow {...defaultProps} />);
      const cards = container.querySelectorAll('.bg-\\[\\#1A1A1A\\]');
      expect(cards.length).toBe(4); // All four stat cards
    });

    it('has proper gap spacing', () => {
      const { container } = render(<StatsRow {...defaultProps} />);
      const grid = container.firstChild;
      expect(grid).toHaveClass('gap-4');
    });

    it('cards have borders', () => {
      const { container } = render(<StatsRow {...defaultProps} />);
      const cards = container.querySelectorAll('.border-gray-800');
      expect(cards.length).toBe(4);
    });

    it('cards have shadow', () => {
      const { container } = render(<StatsRow {...defaultProps} />);
      const cards = container.querySelectorAll('.shadow-sm');
      expect(cards.length).toBe(4);
    });
  });

  describe('Icons', () => {
    it('renders all icons', () => {
      const { container } = render(<StatsRow {...defaultProps} />);

      // Check for SVG elements (icons are rendered as SVG)
      const svgs = container.querySelectorAll('svg');
      expect(svgs.length).toBeGreaterThanOrEqual(4);
    });

    it('icons have aria-hidden attribute', () => {
      const { container } = render(<StatsRow {...defaultProps} />);

      // Icons should be hidden from screen readers
      const hiddenIcons = container.querySelectorAll('[aria-hidden="true"]');
      expect(hiddenIcons.length).toBeGreaterThanOrEqual(4);
    });
  });

  describe('Accessibility', () => {
    it('has proper region role', () => {
      render(<StatsRow {...defaultProps} />);
      expect(screen.getByRole('region')).toBeInTheDocument();
    });

    it('has descriptive aria-label for region', () => {
      render(<StatsRow {...defaultProps} />);
      const region = screen.getByRole('region');
      expect(region).toHaveAttribute('aria-label', 'Dashboard statistics');
    });

    it('status indicator has descriptive aria-label', () => {
      render(<StatsRow {...defaultProps} systemStatus="healthy" />);
      const indicator = screen.getByTestId('status-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'System status: Online');
    });
  });

  describe('Edge Cases', () => {
    it('handles very large numbers', () => {
      render(
        <StatsRow
          {...defaultProps}
          activeCameras={9999}
          eventsToday={10000}
          currentRiskScore={100}
        />
      );

      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('9999');
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('10000');
      expect(screen.getByTestId('risk-score')).toHaveTextContent('100');
    });

    it('handles all zero values', () => {
      render(
        <StatsRow
          activeCameras={0}
          eventsToday={0}
          currentRiskScore={0}
          systemStatus="unhealthy"
        />
      );

      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('0');
      expect(screen.getByTestId('events-today-count')).toHaveTextContent('0');
      expect(screen.getByTestId('risk-score')).toHaveTextContent('0');
    });
  });

  describe('Integration', () => {
    it('updates when props change', () => {
      const { rerender } = render(<StatsRow {...defaultProps} activeCameras={5} />);
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('5');

      rerender(<StatsRow {...defaultProps} activeCameras={10} />);
      expect(screen.getByTestId('active-cameras-count')).toHaveTextContent('10');
    });

    it('updates risk level when score changes', () => {
      const { rerender } = render(<StatsRow {...defaultProps} currentRiskScore={15} />);
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Low');

      rerender(<StatsRow {...defaultProps} currentRiskScore={85} />);
      expect(screen.getByTestId('risk-label')).toHaveTextContent('Critical');
    });

    it('updates system status indicator', () => {
      const { rerender } = render(<StatsRow {...defaultProps} systemStatus="healthy" />);
      expect(screen.getByTestId('status-indicator')).toHaveClass('bg-green-500');

      rerender(<StatsRow {...defaultProps} systemStatus="unhealthy" />);
      expect(screen.getByTestId('status-indicator')).toHaveClass('bg-red-500');
    });
  });

  describe('Visual Consistency', () => {
    it('all stat cards have consistent structure', () => {
      const { container } = render(<StatsRow {...defaultProps} />);
      const cards = container.querySelectorAll('.rounded-lg.border.border-gray-800');

      // Should have 4 cards
      expect(cards.length).toBe(4);

      // Each card should have consistent styling
      cards.forEach((card) => {
        expect(card).toHaveClass('bg-[#1A1A1A]');
        expect(card).toHaveClass('p-4');
        expect(card).toHaveClass('shadow-sm');
      });
    });

    it('all icons have consistent container styling', () => {
      const { container } = render(<StatsRow {...defaultProps} />);
      const iconContainers = container.querySelectorAll('.h-12.w-12.rounded-lg');

      // Should have 4 icon containers
      expect(iconContainers.length).toBeGreaterThanOrEqual(4);

      // Each should have size and shape classes
      iconContainers.forEach((iconContainer) => {
        expect(iconContainer).toHaveClass('flex');
        expect(iconContainer).toHaveClass('items-center');
        expect(iconContainer).toHaveClass('justify-center');
      });
    });

    it('all stat values have consistent font styling', () => {
      const { container } = render(<StatsRow {...defaultProps} />);
      const statValues = container.querySelectorAll('[data-testid$="-count"], [data-testid="risk-score"]');

      // Should have camera count, events count, and risk score
      expect(statValues.length).toBeGreaterThanOrEqual(3);

      // Each should have bold, large text
      statValues.forEach((value) => {
        expect(value).toHaveClass('text-2xl');
        expect(value).toHaveClass('font-bold');
        expect(value).toHaveClass('text-white');
      });
    });
  });
});
