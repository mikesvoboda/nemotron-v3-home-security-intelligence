import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ChartLoadingState from './ChartLoadingState';

describe('ChartLoadingState', () => {
  it('renders with default props', () => {
    render(<ChartLoadingState />);
    expect(screen.getByTestId('chart-loading-state')).toBeInTheDocument();
  });

  it('applies default height class', () => {
    render(<ChartLoadingState />);
    const container = screen.getByTestId('chart-loading-state');
    expect(container).toHaveClass('h-48');
  });

  it('applies custom height class', () => {
    render(<ChartLoadingState height="h-64" />);
    const container = screen.getByTestId('chart-loading-state');
    expect(container).toHaveClass('h-64');
  });

  it('displays loading message when provided', () => {
    render(<ChartLoadingState message="Loading history..." />);
    expect(screen.getByText('Loading history...')).toBeInTheDocument();
    expect(screen.getByTestId('chart-loading-state-message')).toBeInTheDocument();
  });

  it('does not display message element when no message provided', () => {
    render(<ChartLoadingState />);
    expect(screen.queryByTestId('chart-loading-state-message')).not.toBeInTheDocument();
  });

  it('uses gray color by default', () => {
    const { container } = render(<ChartLoadingState />);
    const spinner = container.querySelector('svg');
    expect(spinner).toHaveClass('text-gray-400');
  });

  it('uses brand color when useBrandColor is true', () => {
    const { container } = render(<ChartLoadingState useBrandColor />);
    const spinner = container.querySelector('svg');
    expect(spinner).toHaveClass('text-[#76B900]');
  });

  it('applies custom className', () => {
    render(<ChartLoadingState className="custom-class" />);
    const container = screen.getByTestId('chart-loading-state');
    expect(container).toHaveClass('custom-class');
  });

  it('uses custom test ID when provided', () => {
    render(<ChartLoadingState data-testid="custom-loading" />);
    expect(screen.getByTestId('custom-loading')).toBeInTheDocument();
  });

  it('has accessible screen reader text', () => {
    render(<ChartLoadingState />);
    expect(screen.getByText('Loading chart data')).toHaveClass('sr-only');
  });

  it('has motion-safe animate-spin class for reduced motion support', () => {
    const { container } = render(<ChartLoadingState />);
    const spinner = container.querySelector('svg');
    expect(spinner).toHaveClass('motion-safe:animate-spin');
  });

  it('renders spinner with aria-hidden for visual users', () => {
    const { container } = render(<ChartLoadingState />);
    const spinner = container.querySelector('svg');
    expect(spinner).toHaveAttribute('aria-hidden', 'true');
  });
});
