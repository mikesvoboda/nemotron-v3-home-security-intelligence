import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import StatsCardSkeleton from './StatsCardSkeleton';

describe('StatsCardSkeleton', () => {
  it('renders skeleton container with correct test id', () => {
    render(<StatsCardSkeleton />);
    const skeleton = screen.getByTestId('stats-card-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('includes icon skeleton area', () => {
    render(<StatsCardSkeleton />);
    const icon = screen.getByTestId('stats-card-skeleton-icon');
    expect(icon).toBeInTheDocument();
    // Icon should be circular
    expect(icon).toHaveClass('rounded-full');
  });

  it('includes label skeleton', () => {
    render(<StatsCardSkeleton />);
    const label = screen.getByTestId('stats-card-skeleton-label');
    expect(label).toBeInTheDocument();
  });

  it('includes value skeleton', () => {
    render(<StatsCardSkeleton />);
    const value = screen.getByTestId('stats-card-skeleton-value');
    expect(value).toBeInTheDocument();
  });

  it('applies custom className when provided', () => {
    render(<StatsCardSkeleton className="custom-class" />);
    const skeleton = screen.getByTestId('stats-card-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('has NVIDIA dark theme styling', () => {
    render(<StatsCardSkeleton />);
    const skeleton = screen.getByTestId('stats-card-skeleton');
    expect(skeleton).toHaveClass('bg-card');
    expect(skeleton).toHaveClass('border-gray-800');
  });

  it('has aria-hidden for accessibility', () => {
    render(<StatsCardSkeleton />);
    const skeleton = screen.getByTestId('stats-card-skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });
});
