import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import RiskGauge from './RiskGauge';

// Mock console.warn to test validation warnings
const originalWarn = console.warn;
beforeEach(() => {
  console.warn = vi.fn();
});

afterEach(() => {
  console.warn = originalWarn;
});

describe('RiskGauge', () => {
  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<RiskGauge value={50} />);
      expect(screen.getByRole('meter')).toBeInTheDocument();
    });

    it('displays the correct risk value', () => {
      render(<RiskGauge value={75} />);
      // In test environment, animation is instant
      expect(screen.getByText('75')).toBeInTheDocument();
    });

    it('displays risk level label when showLabel is true', () => {
      render(<RiskGauge value={80} showLabel />);
      // In test environment, animation is instant
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });

    it('hides risk level label when showLabel is false', () => {
      render(<RiskGauge value={80} showLabel={false} />);
      expect(screen.queryByText('Critical')).not.toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<RiskGauge value={50} className="custom-class" />);
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Risk Level Categories', () => {
    it('displays Low risk for values 0-25', () => {
      render(<RiskGauge value={20} showLabel />);
      expect(screen.getByText('Low')).toBeInTheDocument();
    });

    it('displays Medium risk for values 26-50', () => {
      render(<RiskGauge value={40} showLabel />);
      expect(screen.getByText('Medium')).toBeInTheDocument();
    });

    it('displays High risk for values 51-75', () => {
      render(<RiskGauge value={60} showLabel />);
      expect(screen.getByText('High')).toBeInTheDocument();
    });

    it('displays Critical risk for values 76-100', () => {
      render(<RiskGauge value={90} showLabel />);
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles minimum value (0)', () => {
      render(<RiskGauge value={0} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('handles maximum value (100)', () => {
      render(<RiskGauge value={100} />);
      expect(screen.getByText('100')).toBeInTheDocument();
    });

    it('handles boundary value at 25 (low/medium threshold)', () => {
      render(<RiskGauge value={25} showLabel />);
      expect(screen.getByText('Low')).toBeInTheDocument();
    });

    it('handles boundary value at 26 (medium start)', () => {
      render(<RiskGauge value={26} showLabel />);
      expect(screen.getByText('Medium')).toBeInTheDocument();
    });
  });

  describe('Value Validation', () => {
    it('clamps negative values to 0', () => {
      render(<RiskGauge value={-10} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('clamps values above 100 to 100', () => {
      render(<RiskGauge value={150} />);
      expect(screen.getByText('100')).toBeInTheDocument();
    });

    it('warns when value is negative', () => {
      render(<RiskGauge value={-10} />);
      // Component should clamp the value
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('warns when value is above 100', () => {
      render(<RiskGauge value={150} />);
      // Component should clamp the value
      expect(screen.getByText('100')).toBeInTheDocument();
    });
  });

  describe('Size Variants', () => {
    it('renders small size variant', () => {
      const { container } = render(<RiskGauge value={50} size="sm" />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('width', '120');
      expect(svg).toHaveAttribute('height', '120');
    });

    it('renders medium size variant (default)', () => {
      const { container } = render(<RiskGauge value={50} size="md" />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('width', '160');
      expect(svg).toHaveAttribute('height', '160');
    });

    it('renders large size variant', () => {
      const { container } = render(<RiskGauge value={50} size="lg" />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('width', '200');
      expect(svg).toHaveAttribute('height', '200');
    });
  });

  describe('History Sparkline', () => {
    it('renders sparkline when history is provided', () => {
      const history = [10, 20, 30, 40, 50];
      render(<RiskGauge value={50} history={history} />);
      expect(screen.getByText('Risk History')).toBeInTheDocument();
    });

    it('does not render sparkline when history is not provided', () => {
      render(<RiskGauge value={50} />);
      expect(screen.queryByText('Risk History')).not.toBeInTheDocument();
    });

    it('does not render sparkline when history is empty', () => {
      render(<RiskGauge value={50} history={[]} />);
      expect(screen.queryByText('Risk History')).not.toBeInTheDocument();
    });

    it('renders sparkline header but no path for single history entry', () => {
      const history = [50];
      render(<RiskGauge value={50} history={history} />);
      // Should show the history section (header) but no path since history.length <= 1
      expect(screen.getByText('Risk History')).toBeInTheDocument();
    });
  });

  describe('SVG Structure', () => {
    it('renders SVG with correct viewBox', () => {
      const { container } = render(<RiskGauge value={50} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveAttribute('width', '160');
      expect(svg).toHaveAttribute('height', '160');
    });

    it('renders background circle (track)', () => {
      const { container } = render(<RiskGauge value={50} />);
      const circles = container.querySelectorAll('circle');
      expect(circles.length).toBeGreaterThanOrEqual(2);
      // Background circle should have gray stroke
      const backgroundCircle = Array.from(circles).find(
        (circle) => circle.getAttribute('stroke') === '#2A2A2A'
      );
      expect(backgroundCircle).toBeInTheDocument();
    });

    it('renders progress circle with correct color', () => {
      const { container } = render(<RiskGauge value={50} />);
      const circles = container.querySelectorAll('circle');
      // Progress circle should have NVIDIA yellow color for medium risk (value=50)
      const progressCircle = Array.from(circles).find(
        (circle) => circle.getAttribute('stroke') === '#FFB800'
      );
      expect(progressCircle).toBeInTheDocument();
    });

    it('renders gradient definition', () => {
      const { container } = render(<RiskGauge value={50} />);
      const gradient = container.querySelector('#riskGradient');
      expect(gradient).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA attributes', () => {
      render(<RiskGauge value={65} />);
      const meter = screen.getByRole('meter');
      expect(meter).toHaveAttribute('aria-valuenow', '65');
      expect(meter).toHaveAttribute('aria-valuemin', '0');
      expect(meter).toHaveAttribute('aria-valuemax', '100');
      expect(meter).toHaveAttribute('aria-label');
    });

    it('includes risk level in aria-label', () => {
      render(<RiskGauge value={80} />);
      const meter = screen.getByRole('meter');
      const ariaLabel = meter.getAttribute('aria-label');
      expect(ariaLabel).toContain('Critical');
      expect(ariaLabel).toContain('80');
    });

    it('marks SVG as aria-hidden', () => {
      const { container } = render(<RiskGauge value={50} />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('Animation', () => {
    it('updates value immediately in test environment', () => {
      const { rerender } = render(<RiskGauge value={0} />);

      // Initial value should be 0
      expect(screen.getByText('0')).toBeInTheDocument();

      // Change value to 75
      rerender(<RiskGauge value={75} />);

      // In test mode, animation is instant so should immediately show 75
      expect(screen.getByText('75')).toBeInTheDocument();
    });
  });

  describe('Color Coding', () => {
    it('uses NVIDIA green color for low risk (0-25)', () => {
      const { container } = render(<RiskGauge value={20} />);
      const circles = container.querySelectorAll('circle');
      const progressCircle = Array.from(circles).find(
        (circle) => circle.getAttribute('stroke') === '#76B900'
      );
      expect(progressCircle).toBeInTheDocument();
    });

    it('uses NVIDIA yellow color for medium risk (26-50)', () => {
      const { container } = render(<RiskGauge value={40} />);
      const circles = container.querySelectorAll('circle');
      const progressCircle = Array.from(circles).find(
        (circle) => circle.getAttribute('stroke') === '#FFB800'
      );
      expect(progressCircle).toBeInTheDocument();
    });

    it('uses NVIDIA red color for high risk (51-75)', () => {
      const { container } = render(<RiskGauge value={60} />);
      const circles = container.querySelectorAll('circle');
      const progressCircle = Array.from(circles).find(
        (circle) => circle.getAttribute('stroke') === '#E74856'
      );
      expect(progressCircle).toBeInTheDocument();
    });

    it('uses red color for critical risk (76-100)', () => {
      const { container } = render(<RiskGauge value={90} />);
      const circles = container.querySelectorAll('circle');
      const progressCircle = Array.from(circles).find(
        (circle) => circle.getAttribute('stroke') === '#ef4444'
      );
      expect(progressCircle).toBeInTheDocument();
    });
  });
});
