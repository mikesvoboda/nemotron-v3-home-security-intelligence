import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SummaryCardSkeleton } from './SummaryCardSkeleton';

describe('SummaryCardSkeleton', () => {
  describe('rendering', () => {
    it('renders skeleton container with correct test id for hourly', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      expect(skeleton).toBeInTheDocument();
    });

    it('renders skeleton container with correct test id for daily', () => {
      render(<SummaryCardSkeleton type="daily" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-daily');
      expect(skeleton).toBeInTheDocument();
    });

    it('renders "Hourly Summary" title for hourly type', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
    });

    it('renders "Daily Summary" title for daily type', () => {
      render(<SummaryCardSkeleton type="daily" />);
      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders clock icon for hourly type', () => {
      const { container } = render(<SummaryCardSkeleton type="hourly" />);
      const clockIcon = container.querySelector('svg.lucide-clock');
      expect(clockIcon).toBeInTheDocument();
    });

    it('renders calendar icon for daily type', () => {
      const { container } = render(<SummaryCardSkeleton type="daily" />);
      const calendarIcon = container.querySelector('svg.lucide-calendar');
      expect(calendarIcon).toBeInTheDocument();
    });

    it('icon has aria-hidden attribute', () => {
      const { container } = render(<SummaryCardSkeleton type="hourly" />);
      const icon = container.querySelector('svg.lucide-clock');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('skeleton elements', () => {
    it('includes badge skeleton area', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const badge = screen.getByTestId('summary-card-skeleton-badge-hourly');
      expect(badge).toBeInTheDocument();
    });

    it('includes content skeleton area', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const content = screen.getByTestId('summary-card-skeleton-content-hourly');
      expect(content).toBeInTheDocument();
    });

    it('includes footer skeleton area', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const footer = screen.getByTestId('summary-card-skeleton-footer-hourly');
      expect(footer).toBeInTheDocument();
    });

    it('content skeleton has two skeleton lines', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const content = screen.getByTestId('summary-card-skeleton-content-hourly');
      // Two skeleton lines (full width and 3/4 width)
      const skeletonBars = content.querySelectorAll('.bg-gray-800');
      expect(skeletonBars.length).toBe(2);
    });
  });

  describe('status text', () => {
    it('does not show status text by default', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      expect(screen.queryByText('Loading summary data...')).not.toBeInTheDocument();
    });

    it('shows status text when showStatusText is true', () => {
      render(<SummaryCardSkeleton type="hourly" showStatusText />);
      expect(screen.getByText('Loading summary data...')).toBeInTheDocument();
    });

    it('status text has correct test id', () => {
      render(<SummaryCardSkeleton type="daily" showStatusText />);
      const status = screen.getByTestId('summary-card-skeleton-status-daily');
      expect(status).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has role="status" for loading indication', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      expect(skeleton).toHaveAttribute('role', 'status');
    });

    it('has appropriate aria-label for hourly', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      expect(skeleton).toHaveAttribute('aria-label', 'Loading hourly summary');
    });

    it('has appropriate aria-label for daily', () => {
      render(<SummaryCardSkeleton type="daily" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-daily');
      expect(skeleton).toHaveAttribute('aria-label', 'Loading daily summary');
    });
  });

  describe('styling', () => {
    it('applies NVIDIA dark theme background', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      expect(skeleton).toHaveClass('bg-[#1A1A1A]');
    });

    it('applies gray border for loading state', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      // gray-300 RGB value
      expect(skeleton).toHaveStyle({ borderLeftColor: 'rgb(209, 213, 219)' });
    });

    it('applies border-l-4 class', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      expect(skeleton).toHaveClass('border-l-4');
    });

    it('applies custom className when provided', () => {
      render(<SummaryCardSkeleton type="hourly" className="custom-class" />);
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      expect(skeleton).toHaveClass('custom-class');
    });

    it('badge skeleton has overflow-hidden for shimmer containment', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const badge = screen.getByTestId('summary-card-skeleton-badge-hourly');
      expect(badge).toHaveClass('overflow-hidden');
    });
  });

  describe('shimmer animation', () => {
    it('badge skeleton contains shimmer overlay', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const badge = screen.getByTestId('summary-card-skeleton-badge-hourly');
      const shimmer = badge.querySelector('.animate-shimmer');
      expect(shimmer).toBeInTheDocument();
    });

    it('content skeleton lines contain shimmer overlays', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const content = screen.getByTestId('summary-card-skeleton-content-hourly');
      const shimmers = content.querySelectorAll('.animate-shimmer');
      expect(shimmers.length).toBe(2);
    });

    it('footer skeleton contains shimmer overlay', () => {
      render(<SummaryCardSkeleton type="hourly" />);
      const footer = screen.getByTestId('summary-card-skeleton-footer-hourly');
      const shimmer = footer.querySelector('.animate-shimmer');
      expect(shimmer).toBeInTheDocument();
    });
  });
});
