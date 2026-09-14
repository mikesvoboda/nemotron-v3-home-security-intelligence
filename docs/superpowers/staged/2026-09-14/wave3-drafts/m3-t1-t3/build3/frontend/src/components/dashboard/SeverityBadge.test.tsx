import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SeverityBadge } from './SeverityBadge';

import type { SeverityLevel } from '@/utils/severityCalculator';

describe('SeverityBadge', () => {
  describe('rendering', () => {
    it('renders with default props', () => {
      render(<SeverityBadge level="clear" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toBeInTheDocument();
    });

    it('renders the label in uppercase', () => {
      render(<SeverityBadge level="medium" />);
      expect(screen.getByText('MODERATE ACTIVITY')).toBeInTheDocument();
    });

    it('renders with count when provided', () => {
      render(<SeverityBadge level="high" count={5} />);
      expect(screen.getByTestId('severity-badge-count')).toHaveTextContent('(5)');
    });

    it('does not render count when not provided', () => {
      render(<SeverityBadge level="low" />);
      expect(screen.queryByTestId('severity-badge-count')).not.toBeInTheDocument();
    });
  });

  describe('severity levels', () => {
    const levels: SeverityLevel[] = ['clear', 'low', 'medium', 'high', 'critical'];

    it.each(levels)('renders %s severity level correctly', (level) => {
      render(<SeverityBadge level={level} />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveAttribute('data-severity', level);
    });

    it('renders "ALL CLEAR" label for clear level', () => {
      render(<SeverityBadge level="clear" />);
      expect(screen.getByText('ALL CLEAR')).toBeInTheDocument();
    });

    it('renders "LOW ACTIVITY" label for low level', () => {
      render(<SeverityBadge level="low" />);
      expect(screen.getByText('LOW ACTIVITY')).toBeInTheDocument();
    });

    it('renders "MODERATE ACTIVITY" label for medium level', () => {
      render(<SeverityBadge level="medium" />);
      expect(screen.getByText('MODERATE ACTIVITY')).toBeInTheDocument();
    });

    it('renders "HIGH ACTIVITY" label for high level', () => {
      render(<SeverityBadge level="high" />);
      expect(screen.getByText('HIGH ACTIVITY')).toBeInTheDocument();
    });

    it('renders "CRITICAL" label for critical level', () => {
      render(<SeverityBadge level="critical" />);
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders CheckCircle icon for clear level', () => {
      const { container } = render(<SeverityBadge level="clear" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-check');
    });

    it('renders CheckCircle icon for low level', () => {
      const { container } = render(<SeverityBadge level="low" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-check');
    });

    it('renders AlertCircle icon for medium level', () => {
      const { container } = render(<SeverityBadge level="medium" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-alert');
    });

    it('renders AlertTriangle icon for high level', () => {
      const { container } = render(<SeverityBadge level="high" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-triangle-alert');
    });

    it('renders XCircle icon for critical level', () => {
      const { container } = render(<SeverityBadge level="critical" />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-x');
    });

    it('icons have aria-hidden attribute', () => {
      const { container } = render(<SeverityBadge level="clear" />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('colors', () => {
    it('applies emerald colors for clear level', () => {
      render(<SeverityBadge level="clear" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-emerald-500/10', 'text-emerald-400');
    });

    it('applies green colors for low level', () => {
      render(<SeverityBadge level="low" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-green-500/10', 'text-green-400');
    });

    it('applies yellow colors for medium level', () => {
      render(<SeverityBadge level="medium" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-yellow-500/10', 'text-yellow-400');
    });

    it('applies orange colors for high level', () => {
      render(<SeverityBadge level="high" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-orange-500/10', 'text-orange-400');
    });

    it('applies red colors for critical level', () => {
      render(<SeverityBadge level="critical" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('bg-red-500/10', 'text-red-400');
    });
  });

  describe('sizes', () => {
    it('renders small size with correct classes', () => {
      const { container } = render(<SeverityBadge level="clear" size="sm" />);
      const badge = screen.getByTestId('severity-badge');
      const svg = container.querySelector('svg');

      expect(badge).toHaveClass('px-2', 'py-0.5', 'text-xs');
      expect(svg).toHaveClass('h-3', 'w-3');
    });

    it('renders medium size by default with correct classes', () => {
      const { container } = render(<SeverityBadge level="clear" />);
      const badge = screen.getByTestId('severity-badge');
      const svg = container.querySelector('svg');

      expect(badge).toHaveClass('px-2.5', 'py-1', 'text-sm');
      expect(svg).toHaveClass('h-4', 'w-4');
    });

    it('renders medium size explicitly with correct classes', () => {
      const { container } = render(<SeverityBadge level="clear" size="md" />);
      const badge = screen.getByTestId('severity-badge');
      const svg = container.querySelector('svg');

      expect(badge).toHaveClass('px-2.5', 'py-1', 'text-sm');
      expect(svg).toHaveClass('h-4', 'w-4');
    });
  });

  describe('pulsing animation', () => {
    it('applies pulse animation when pulsing is true and level is critical', () => {
      render(<SeverityBadge level="critical" pulsing />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('animate-pulse-critical');
    });

    it('does not apply pulse animation when pulsing is false', () => {
      render(<SeverityBadge level="critical" pulsing={false} />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).not.toHaveClass('animate-pulse-critical');
    });

    it('does not apply pulse animation for non-critical levels', () => {
      render(<SeverityBadge level="high" pulsing />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).not.toHaveClass('animate-pulse-critical');
    });

    it('does not apply pulse animation by default', () => {
      render(<SeverityBadge level="critical" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).not.toHaveClass('animate-pulse-critical');
    });
  });

  describe('accessibility', () => {
    it('has role="status" for screen readers', () => {
      render(<SeverityBadge level="clear" />);
      const badge = screen.getByRole('status');
      expect(badge).toBeInTheDocument();
    });

    it('has aria-label for severity without count', () => {
      render(<SeverityBadge level="high" />);
      const badge = screen.getByLabelText('Severity: High activity');
      expect(badge).toBeInTheDocument();
    });

    it('has aria-label for severity with count (singular)', () => {
      render(<SeverityBadge level="critical" count={1} />);
      const badge = screen.getByLabelText('Severity: Critical, 1 event');
      expect(badge).toBeInTheDocument();
    });

    it('has aria-label for severity with count (plural)', () => {
      render(<SeverityBadge level="critical" count={5} />);
      const badge = screen.getByLabelText('Severity: Critical, 5 events');
      expect(badge).toBeInTheDocument();
    });
  });

  describe('base styling', () => {
    it('has pill shape with rounded corners', () => {
      render(<SeverityBadge level="clear" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('rounded-full');
    });

    it('has inline-flex layout', () => {
      render(<SeverityBadge level="clear" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('inline-flex', 'items-center');
    });

    it('has tracking-wide for letter spacing', () => {
      render(<SeverityBadge level="clear" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('tracking-wide');
    });

    it('has font-medium weight', () => {
      render(<SeverityBadge level="clear" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('font-medium');
    });

    it('has border styling', () => {
      render(<SeverityBadge level="clear" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('border');
    });
  });

  describe('custom className', () => {
    it('applies custom className to badge', () => {
      render(<SeverityBadge level="clear" className="custom-class" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('custom-class');
    });

    it('merges custom className with default classes', () => {
      render(<SeverityBadge level="clear" className="ml-4" />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveClass('ml-4', 'inline-flex', 'items-center');
    });
  });

  describe('count display', () => {
    it('displays count of 0 when provided', () => {
      render(<SeverityBadge level="clear" count={0} />);
      expect(screen.getByTestId('severity-badge-count')).toHaveTextContent('(0)');
    });

    it('displays large counts correctly', () => {
      render(<SeverityBadge level="high" count={999} />);
      expect(screen.getByTestId('severity-badge-count')).toHaveTextContent('(999)');
    });

    it('count has font-semibold weight', () => {
      render(<SeverityBadge level="high" count={5} />);
      const count = screen.getByTestId('severity-badge-count');
      expect(count).toHaveClass('font-semibold');
    });
  });

  describe('snapshots', () => {
    it.each(['clear', 'low', 'medium', 'high', 'critical'] as SeverityLevel[])(
      'renders %s severity level correctly',
      (level) => {
        const { container } = render(<SeverityBadge level={level} />);
        expect(container.firstChild).toMatchSnapshot();
      }
    );

    it('renders with count', () => {
      const { container } = render(<SeverityBadge level="high" count={5} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it.each(['sm', 'md'] as const)('renders %s size variant correctly', (size) => {
      const { container } = render(<SeverityBadge level="medium" size={size} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders critical level with pulsing animation', () => {
      const { container } = render(<SeverityBadge level="critical" pulsing />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders with custom className', () => {
      const { container } = render(<SeverityBadge level="low" className="custom-margin ml-4" />);
      expect(container.firstChild).toMatchSnapshot();
    });
  });
});
