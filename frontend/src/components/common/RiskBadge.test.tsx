import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RiskBadge from './RiskBadge';

describe('RiskBadge', () => {
  describe('risk level rendering', () => {
    it('renders low risk badge with NVIDIA green styling', () => {
      render(<RiskBadge level="low" />);
      const badge = screen.getByText('Low');
      expect(badge).toBeInTheDocument();
      expect(badge.closest('span')).toHaveClass('bg-risk-low/10', 'text-risk-low');
    });

    it('renders medium risk badge with NVIDIA yellow styling', () => {
      render(<RiskBadge level="medium" />);
      const badge = screen.getByText('Medium');
      expect(badge).toBeInTheDocument();
      expect(badge.closest('span')).toHaveClass('bg-risk-medium/10', 'text-risk-medium');
    });

    it('renders high risk badge with NVIDIA red styling', () => {
      render(<RiskBadge level="high" />);
      const badge = screen.getByText('High');
      expect(badge).toBeInTheDocument();
      expect(badge.closest('span')).toHaveClass('bg-risk-high/10', 'text-risk-high');
    });

    it('renders critical risk badge with WCAG AA compliant styling', () => {
      render(<RiskBadge level="critical" />);
      const badge = screen.getByText('Critical');
      expect(badge).toBeInTheDocument();
      expect(badge.closest('span')).toHaveClass('bg-risk-critical/10', 'text-risk-critical');
    });
  });

  describe('score display', () => {
    it('displays score when showScore is true', () => {
      render(<RiskBadge level="high" score={72} showScore={true} />);
      expect(screen.getByText('High (72)')).toBeInTheDocument();
    });

    it('does not display score when showScore is false', () => {
      render(<RiskBadge level="high" score={72} showScore={false} />);
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.queryByText('High (72)')).not.toBeInTheDocument();
    });

    it('does not display score when showScore is undefined', () => {
      render(<RiskBadge level="high" score={72} />);
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.queryByText('High (72)')).not.toBeInTheDocument();
    });

    it('does not display score when score is undefined', () => {
      render(<RiskBadge level="high" showScore={true} />);
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.queryByText(/\(\d+\)/)).not.toBeInTheDocument();
    });
  });

  describe('size variants', () => {
    it('renders small size with text-xs', () => {
      render(<RiskBadge level="low" size="sm" />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).toHaveClass('text-xs', 'px-2', 'py-0.5');
    });

    it('renders medium size with text-sm (default)', () => {
      render(<RiskBadge level="low" />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).toHaveClass('text-sm', 'px-2.5', 'py-1');
    });

    it('renders large size with text-base', () => {
      render(<RiskBadge level="low" size="lg" />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).toHaveClass('text-base', 'px-3', 'py-1.5');
    });
  });

  describe('animation', () => {
    it('applies pulse-critical animation for critical level when animated is true', () => {
      render(<RiskBadge level="critical" animated={true} />);
      const badge = screen.getByText('Critical');
      // Uses animate-pulse-critical (box-shadow based) instead of animate-pulse (opacity based)
      // to maintain WCAG 2.1 AA color contrast during animation
      expect(badge.closest('span')).toHaveClass('animate-pulse-critical');
    });

    it('does not apply pulse animation for critical level when animated is false', () => {
      render(<RiskBadge level="critical" animated={false} />);
      const badge = screen.getByText('Critical');
      expect(badge.closest('span')).not.toHaveClass('animate-pulse-critical');
    });

    it('does not apply pulse animation for non-critical levels', () => {
      render(<RiskBadge level="low" animated={true} />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).not.toHaveClass('animate-pulse-critical');
    });

    it('applies pulse-critical animation by default for critical level', () => {
      render(<RiskBadge level="critical" />);
      const badge = screen.getByText('Critical');
      expect(badge.closest('span')).toHaveClass('animate-pulse-critical');
    });
  });

  describe('icons', () => {
    it('renders CheckCircle icon for low risk', () => {
      const { container } = render(<RiskBadge level="low" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-check-big');
    });

    it('renders AlertTriangle icon for medium risk', () => {
      const { container } = render(<RiskBadge level="medium" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-triangle-alert');
    });

    it('renders AlertTriangle icon for high risk', () => {
      const { container } = render(<RiskBadge level="high" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-triangle-alert');
    });

    it('renders AlertOctagon icon for critical risk', () => {
      const { container } = render(<RiskBadge level="critical" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-octagon-alert');
    });

    it('renders icon with correct size for small badge', () => {
      const { container } = render(<RiskBadge level="low" size="sm" />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveClass('w-3', 'h-3');
    });

    it('renders icon with correct size for medium badge', () => {
      const { container } = render(<RiskBadge level="low" size="md" />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveClass('w-4', 'h-4');
    });

    it('renders icon with correct size for large badge', () => {
      const { container } = render(<RiskBadge level="low" size="lg" />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveClass('w-5', 'h-5');
    });
  });

  describe('accessibility', () => {
    it('includes aria-label for low risk', () => {
      render(<RiskBadge level="low" />);
      const badge = screen.getByLabelText('Risk level: Low');
      expect(badge).toBeInTheDocument();
    });

    it('includes aria-label with score when score is displayed', () => {
      render(<RiskBadge level="high" score={72} showScore={true} />);
      const badge = screen.getByLabelText('Risk level: High, score 72');
      expect(badge).toBeInTheDocument();
    });

    it('includes role="status" attribute', () => {
      render(<RiskBadge level="medium" />);
      const badge = screen.getByRole('status');
      expect(badge).toBeInTheDocument();
    });
  });

  describe('custom className', () => {
    it('applies custom className to badge', () => {
      render(<RiskBadge level="low" className="custom-class" />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).toHaveClass('custom-class');
    });

    it('merges custom className with default classes', () => {
      render(<RiskBadge level="low" className="ml-4" />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).toHaveClass('ml-4', 'inline-flex', 'items-center');
    });
  });

  describe('base styling', () => {
    it('has pill shape with rounded corners', () => {
      render(<RiskBadge level="low" />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).toHaveClass('rounded-full');
    });

    it('has inline-flex layout', () => {
      render(<RiskBadge level="low" />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).toHaveClass('inline-flex', 'items-center', 'gap-1');
    });

    it('has font-medium weight', () => {
      render(<RiskBadge level="low" />);
      const badge = screen.getByText('Low');
      expect(badge.closest('span')).toHaveClass('font-medium');
    });
  });

  describe('snapshots', () => {
    it.each(['low', 'medium', 'high', 'critical'] as const)(
      'renders %s risk level correctly',
      (level) => {
        const { container } = render(<RiskBadge level={level} />);
        expect(container.firstChild).toMatchSnapshot();
      }
    );

    it('renders with score displayed', () => {
      const { container } = render(<RiskBadge level="high" score={85} showScore={true} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it.each(['sm', 'md', 'lg'] as const)('renders %s size variant correctly', (size) => {
      const { container } = render(<RiskBadge level="medium" size={size} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders critical level with animation', () => {
      const { container } = render(<RiskBadge level="critical" animated={true} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders critical level without animation', () => {
      const { container } = render(<RiskBadge level="critical" animated={false} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders with custom className', () => {
      const { container } = render(<RiskBadge level="low" className="custom-margin ml-4" />);
      expect(container.firstChild).toMatchSnapshot();
    });
  });
});
