import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import EntityCardSkeleton from './EntityCardSkeleton';

describe('EntityCardSkeleton', () => {
  it('renders skeleton container with correct test id', () => {
    render(<EntityCardSkeleton />);
    const skeleton = screen.getByTestId('entity-card-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('applies custom className when provided', () => {
    render(<EntityCardSkeleton className="custom-class" />);
    const skeleton = screen.getByTestId('entity-card-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('has NVIDIA dark theme styling', () => {
    render(<EntityCardSkeleton />);
    const skeleton = screen.getByTestId('entity-card-skeleton');
    expect(skeleton).toHaveClass('bg-[#1F1F1F]');
    expect(skeleton).toHaveClass('border-gray-800');
  });

  it('has aria-hidden for accessibility', () => {
    render(<EntityCardSkeleton />);
    const skeleton = screen.getByTestId('entity-card-skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });

  it('uses shimmer animation for loading effect', () => {
    render(<EntityCardSkeleton />);
    const skeleton = screen.getByTestId('entity-card-skeleton');
    const shimmerElements = skeleton.querySelectorAll('.animate-shimmer');
    expect(shimmerElements.length).toBeGreaterThan(0);
  });
});
