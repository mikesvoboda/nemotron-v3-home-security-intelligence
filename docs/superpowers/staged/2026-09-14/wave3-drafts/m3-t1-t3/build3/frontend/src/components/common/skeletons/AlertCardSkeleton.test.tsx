import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import AlertCardSkeleton from './AlertCardSkeleton';

describe('AlertCardSkeleton', () => {
  it('renders with default test id', () => {
    render(<AlertCardSkeleton />);
    const skeleton = screen.getByTestId('alert-card-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<AlertCardSkeleton className="custom-class" />);
    const skeleton = screen.getByTestId('alert-card-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('has aria-hidden attribute for accessibility', () => {
    render(<AlertCardSkeleton />);
    const skeleton = screen.getByTestId('alert-card-skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });

  it('has role="presentation" for screen readers', () => {
    render(<AlertCardSkeleton />);
    const skeleton = screen.getByTestId('alert-card-skeleton');
    expect(skeleton).toHaveAttribute('role', 'presentation');
  });

  it('matches AlertCard visual structure with border styling', () => {
    render(<AlertCardSkeleton />);
    const skeleton = screen.getByTestId('alert-card-skeleton');
    expect(skeleton).toHaveClass('rounded-lg');
    expect(skeleton).toHaveClass('border-2');
    expect(skeleton).toHaveClass('border-gray-700');
    expect(skeleton).toHaveClass('bg-[#1F1F1F]');
  });

  it('contains severity accent bar', () => {
    render(<AlertCardSkeleton />);
    const skeleton = screen.getByTestId('alert-card-skeleton');
    const accentBar = skeleton.querySelector('.absolute.left-0.top-0');
    expect(accentBar).toBeInTheDocument();
    expect(accentBar).toHaveClass('h-full');
    expect(accentBar).toHaveClass('w-1');
    expect(accentBar).toHaveClass('bg-gray-600');
  });

  it('contains shimmer-animated skeleton elements', () => {
    render(<AlertCardSkeleton />);
    const skeleton = screen.getByTestId('alert-card-skeleton');
    const shimmerElements = skeleton.querySelectorAll('.animate-shimmer');
    expect(shimmerElements.length).toBeGreaterThan(0);
  });
});
