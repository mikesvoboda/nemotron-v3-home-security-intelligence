import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ConfidenceBadge from './ConfidenceBadge';

describe('ConfidenceBadge', () => {
  describe('basic rendering', () => {
    it('renders badge with percentage text', () => {
      render(<ConfidenceBadge confidence={0.95} />);
      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByText('95%')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<ConfidenceBadge confidence={0.9} className="custom-class" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('custom-class');
    });
  });

  describe('confidence level color coding', () => {
    it('applies red colors for low confidence (< 70%)', () => {
      const { container } = render(<ConfidenceBadge confidence={0.5} />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-red-500/20', 'text-red-400', 'border-red-500/40');
    });

    it('applies yellow colors for medium confidence (70-85%)', () => {
      const { container } = render(<ConfidenceBadge confidence={0.75} />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-yellow-500/20', 'text-yellow-400', 'border-yellow-500/40');
    });

    it('applies green colors for high confidence (>= 85%)', () => {
      const { container } = render(<ConfidenceBadge confidence={0.95} />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-green-500/20', 'text-green-400', 'border-green-500/40');
    });
  });

  describe('size variants', () => {
    it('applies small size classes by default', () => {
      const { container } = render(<ConfidenceBadge confidence={0.9} />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-xs', 'px-2', 'py-0.5');
    });

    it('applies small size classes when size="sm"', () => {
      const { container } = render(<ConfidenceBadge confidence={0.9} size="sm" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-xs', 'px-2', 'py-0.5');
    });

    it('applies medium size classes when size="md"', () => {
      const { container } = render(<ConfidenceBadge confidence={0.9} size="md" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-sm', 'px-2.5', 'py-1');
    });

    it('applies large size classes when size="lg"', () => {
      const { container } = render(<ConfidenceBadge confidence={0.9} size="lg" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-base', 'px-3', 'py-1.5');
    });
  });

  describe('confidence bar', () => {
    it('does not show bar by default', () => {
      const { container } = render(<ConfidenceBadge confidence={0.9} />);
      const bars = container.querySelectorAll('.bg-gray-700');
      expect(bars.length).toBe(0);
    });

    it('shows confidence bar when showBar is true', () => {
      const { container } = render(<ConfidenceBadge confidence={0.9} showBar />);
      const barContainer = container.querySelector('.bg-gray-700');
      expect(barContainer).toBeInTheDocument();
    });

    it('bar has correct width based on confidence', () => {
      const { container } = render(<ConfidenceBadge confidence={0.75} showBar />);
      const bar = container.querySelector('.bg-gray-700 > span');
      expect(bar).toHaveStyle({ width: '75%' });
    });

    it('bar uses red color for low confidence', () => {
      const { container } = render(<ConfidenceBadge confidence={0.5} showBar />);
      const bar = container.querySelector('.bg-gray-700 > span');
      expect(bar).toHaveClass('bg-red-500');
    });

    it('bar uses yellow color for medium confidence', () => {
      const { container } = render(<ConfidenceBadge confidence={0.75} showBar />);
      const bar = container.querySelector('.bg-gray-700 > span');
      expect(bar).toHaveClass('bg-yellow-500');
    });

    it('bar uses green color for high confidence', () => {
      const { container } = render(<ConfidenceBadge confidence={0.95} showBar />);
      const bar = container.querySelector('.bg-gray-700 > span');
      expect(bar).toHaveClass('bg-green-500');
    });
  });

  describe('accessibility', () => {
    it('has role="status"', () => {
      render(<ConfidenceBadge confidence={0.9} />);
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has descriptive aria-label for low confidence', () => {
      render(<ConfidenceBadge confidence={0.5} />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute(
        'aria-label',
        'Detection confidence: 50% (Low Confidence)'
      );
    });

    it('has descriptive aria-label for medium confidence', () => {
      render(<ConfidenceBadge confidence={0.75} />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute(
        'aria-label',
        'Detection confidence: 75% (Medium Confidence)'
      );
    });

    it('has descriptive aria-label for high confidence', () => {
      render(<ConfidenceBadge confidence={0.95} />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute(
        'aria-label',
        'Detection confidence: 95% (High Confidence)'
      );
    });

    it('has title attribute with confidence label', () => {
      render(<ConfidenceBadge confidence={0.95} />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('title', 'High Confidence');
    });

    it('bar container is aria-hidden', () => {
      const { container } = render(<ConfidenceBadge confidence={0.9} showBar />);
      const barContainer = container.querySelector('.bg-gray-700');
      expect(barContainer).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('percentage formatting', () => {
    it('formats 0.95 as 95%', () => {
      render(<ConfidenceBadge confidence={0.95} />);
      expect(screen.getByText('95%')).toBeInTheDocument();
    });

    it('formats 1.0 as 100%', () => {
      render(<ConfidenceBadge confidence={1.0} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('formats 0.5 as 50%', () => {
      render(<ConfidenceBadge confidence={0.5} />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('rounds to nearest integer (0.956 -> 96%)', () => {
      render(<ConfidenceBadge confidence={0.956} />);
      expect(screen.getByText('96%')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles confidence of 0', () => {
      render(<ConfidenceBadge confidence={0} />);
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('handles confidence at boundary 0.7', () => {
      const { container } = render(<ConfidenceBadge confidence={0.7} />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-yellow-400'); // medium
    });

    it('handles confidence at boundary 0.85', () => {
      const { container } = render(<ConfidenceBadge confidence={0.85} />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-green-400'); // high
    });
  });
});
