import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import LoadingSpinner from './LoadingSpinner';

describe('LoadingSpinner', () => {
  it('renders loading spinner', () => {
    render(<LoadingSpinner />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('has proper dark theme styling', () => {
    const { container } = render(<LoadingSpinner />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('bg-[#121212]');
  });

  it('displays animated spinner element with motion-safe prefix', () => {
    const { container } = render(<LoadingSpinner />);
    // Uses motion-safe:animate-spin to respect prefers-reduced-motion
    const spinner = container.querySelector('.motion-safe\\:animate-spin');
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveClass('border-t-green-500');
  });
});
