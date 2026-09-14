/**
 * Tests for AlertBadge component
 *
 * NEM-3123: Phase 3.2 - Prometheus alert UI components
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import AlertBadge from './AlertBadge';

import type { AlertCounts } from '../../hooks/usePrometheusAlerts';

// ============================================================================
// Test Fixtures
// ============================================================================

const zeroCounts: AlertCounts = {
  critical: 0,
  warning: 0,
  info: 0,
  total: 0,
};

const criticalOnlyCounts: AlertCounts = {
  critical: 2,
  warning: 0,
  info: 0,
  total: 2,
};

const warningOnlyCounts: AlertCounts = {
  critical: 0,
  warning: 5,
  info: 0,
  total: 5,
};

const infoOnlyCounts: AlertCounts = {
  critical: 0,
  warning: 0,
  info: 3,
  total: 3,
};

const mixedCounts: AlertCounts = {
  critical: 2,
  warning: 5,
  info: 1,
  total: 8,
};

// ============================================================================
// Tests
// ============================================================================

describe('AlertBadge', () => {
  describe('rendering', () => {
    it('renders with no alerts', () => {
      render(<AlertBadge counts={zeroCounts} />);

      expect(screen.getByTestId('alert-badge')).toBeInTheDocument();
      expect(screen.getByTestId('alert-badge-empty')).toHaveTextContent('No alerts');
      expect(screen.getByTestId('alert-badge-icon')).toBeInTheDocument();
    });

    it('renders critical alert count', () => {
      render(<AlertBadge counts={criticalOnlyCounts} />);

      expect(screen.getByTestId('alert-badge-critical')).toBeInTheDocument();
      expect(screen.getByTestId('alert-badge-critical')).toHaveTextContent('2');
      expect(screen.queryByTestId('alert-badge-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('alert-badge-info')).not.toBeInTheDocument();
    });

    it('renders warning alert count', () => {
      render(<AlertBadge counts={warningOnlyCounts} />);

      expect(screen.getByTestId('alert-badge-warning')).toBeInTheDocument();
      expect(screen.getByTestId('alert-badge-warning')).toHaveTextContent('5');
      expect(screen.queryByTestId('alert-badge-critical')).not.toBeInTheDocument();
    });

    it('renders info alert count when no critical or warning', () => {
      render(<AlertBadge counts={infoOnlyCounts} />);

      expect(screen.getByTestId('alert-badge-info')).toBeInTheDocument();
      expect(screen.getByTestId('alert-badge-info')).toHaveTextContent('3');
    });

    it('renders multiple severity counts', () => {
      render(<AlertBadge counts={mixedCounts} />);

      expect(screen.getByTestId('alert-badge-critical')).toHaveTextContent('2');
      expect(screen.getByTestId('alert-badge-warning')).toHaveTextContent('5');
      // Info is hidden when critical/warning present
      expect(screen.queryByTestId('alert-badge-info')).not.toBeInTheDocument();
    });

    it('renders counts container when has alerts', () => {
      render(<AlertBadge counts={criticalOnlyCounts} />);

      expect(screen.getByTestId('alert-badge-counts')).toBeInTheDocument();
      expect(screen.queryByTestId('alert-badge-empty')).not.toBeInTheDocument();
    });
  });

  describe('interactivity', () => {
    it('calls onClick when clicked', () => {
      const handleClick = vi.fn();
      render(<AlertBadge counts={zeroCounts} onClick={handleClick} />);

      fireEvent.click(screen.getByTestId('alert-badge'));

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('renders as a button element', () => {
      render(<AlertBadge counts={zeroCounts} />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge.tagName).toBe('BUTTON');
      expect(badge).toHaveAttribute('type', 'button');
    });
  });

  describe('accessibility', () => {
    it('has correct aria-label for no alerts', () => {
      render(<AlertBadge counts={zeroCounts} />);

      expect(screen.getByLabelText('No active alerts')).toBeInTheDocument();
    });

    it('has correct aria-label for single alert', () => {
      const singleCritical: AlertCounts = {
        critical: 1,
        warning: 0,
        info: 0,
        total: 1,
      };
      render(<AlertBadge counts={singleCritical} />);

      expect(screen.getByLabelText('1 active alert: 1 critical')).toBeInTheDocument();
    });

    it('has correct aria-label for multiple alerts', () => {
      render(<AlertBadge counts={mixedCounts} />);

      expect(
        screen.getByLabelText('8 active alerts: 2 critical, 5 warning, 1 info')
      ).toBeInTheDocument();
    });

    it('has aria-expanded attribute', () => {
      render(<AlertBadge counts={zeroCounts} isOpen={false} />);
      expect(screen.getByTestId('alert-badge')).toHaveAttribute('aria-expanded', 'false');
    });

    it('has aria-expanded true when open', () => {
      render(<AlertBadge counts={zeroCounts} isOpen={true} />);
      expect(screen.getByTestId('alert-badge')).toHaveAttribute('aria-expanded', 'true');
    });

    it('has aria-haspopup dialog', () => {
      render(<AlertBadge counts={zeroCounts} />);
      expect(screen.getByTestId('alert-badge')).toHaveAttribute('aria-haspopup', 'dialog');
    });
  });

  describe('animation', () => {
    it('applies pulse animation when animating with critical alerts', () => {
      render(<AlertBadge counts={criticalOnlyCounts} isAnimating={true} />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).toHaveClass('motion-safe:animate-pulse-critical');
    });

    it('applies regular pulse animation when animating without critical alerts', () => {
      render(<AlertBadge counts={warningOnlyCounts} isAnimating={true} />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).toHaveClass('motion-safe:animate-pulse');
    });

    it('does not apply animation when isAnimating is false', () => {
      render(<AlertBadge counts={criticalOnlyCounts} isAnimating={false} />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).not.toHaveClass('motion-safe:animate-pulse-critical');
      expect(badge).not.toHaveClass('motion-safe:animate-pulse');
    });

    it('does not apply animation when no alerts', () => {
      render(<AlertBadge counts={zeroCounts} isAnimating={true} />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).not.toHaveClass('motion-safe:animate-pulse-critical');
      expect(badge).not.toHaveClass('motion-safe:animate-pulse');
    });
  });

  describe('size variants', () => {
    it('renders small size', () => {
      render(<AlertBadge counts={zeroCounts} size="sm" />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).toHaveClass('px-2', 'py-1', 'text-xs');
    });

    it('renders medium size (default)', () => {
      render(<AlertBadge counts={zeroCounts} />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).toHaveClass('px-3', 'py-1.5', 'text-sm');
    });

    it('renders large size', () => {
      render(<AlertBadge counts={zeroCounts} size="lg" />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).toHaveClass('px-4', 'py-2', 'text-base');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<AlertBadge counts={zeroCounts} className="custom-class" />);

      expect(screen.getByTestId('alert-badge')).toHaveClass('custom-class');
    });

    it('has open state styling when isOpen is true', () => {
      render(<AlertBadge counts={zeroCounts} isOpen={true} />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).toHaveClass('bg-nvidia-surface-light');
    });

    it('has NVIDIA dark theme base styling', () => {
      render(<AlertBadge counts={zeroCounts} />);

      const badge = screen.getByTestId('alert-badge');
      expect(badge).toHaveClass('bg-nvidia-surface', 'border-nvidia-border');
    });
  });

  describe('snapshots', () => {
    it.each([
      ['no alerts', zeroCounts],
      ['critical only', criticalOnlyCounts],
      ['warning only', warningOnlyCounts],
      ['info only', infoOnlyCounts],
      ['mixed alerts', mixedCounts],
    ])('renders %s correctly', (_, counts) => {
      const { container } = render(<AlertBadge counts={counts} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders with animation', () => {
      const { container } = render(<AlertBadge counts={criticalOnlyCounts} isAnimating={true} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders in open state', () => {
      const { container } = render(<AlertBadge counts={mixedCounts} isOpen={true} />);
      expect(container.firstChild).toMatchSnapshot();
    });
  });
});
