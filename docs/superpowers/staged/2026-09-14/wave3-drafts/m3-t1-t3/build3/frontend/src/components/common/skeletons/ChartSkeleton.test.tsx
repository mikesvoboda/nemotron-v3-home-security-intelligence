import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ChartSkeleton from './ChartSkeleton';

describe('ChartSkeleton', () => {
  it('renders skeleton container with correct test id', () => {
    render(<ChartSkeleton />);
    const skeleton = screen.getByTestId('chart-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('includes chart area skeleton', () => {
    render(<ChartSkeleton />);
    const chartArea = screen.getByTestId('chart-skeleton-area');
    expect(chartArea).toBeInTheDocument();
  });

  it('includes axis skeleton elements', () => {
    render(<ChartSkeleton />);
    const xAxis = screen.getByTestId('chart-skeleton-x-axis');
    const yAxis = screen.getByTestId('chart-skeleton-y-axis');
    expect(xAxis).toBeInTheDocument();
    expect(yAxis).toBeInTheDocument();
  });

  it('has customizable height', () => {
    render(<ChartSkeleton height={400} />);
    const skeleton = screen.getByTestId('chart-skeleton');
    expect(skeleton).toHaveStyle({ height: '400px' });
  });

  it('defaults to 300px height', () => {
    render(<ChartSkeleton />);
    const skeleton = screen.getByTestId('chart-skeleton');
    expect(skeleton).toHaveStyle({ height: '300px' });
  });

  it('applies custom className when provided', () => {
    render(<ChartSkeleton className="custom-class" />);
    const skeleton = screen.getByTestId('chart-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('has NVIDIA dark theme styling', () => {
    render(<ChartSkeleton />);
    const skeleton = screen.getByTestId('chart-skeleton');
    expect(skeleton).toHaveClass('bg-[#1F1F1F]');
    expect(skeleton).toHaveClass('border-gray-800');
  });

  it('has aria-hidden for accessibility', () => {
    render(<ChartSkeleton />);
    const skeleton = screen.getByTestId('chart-skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });
});
