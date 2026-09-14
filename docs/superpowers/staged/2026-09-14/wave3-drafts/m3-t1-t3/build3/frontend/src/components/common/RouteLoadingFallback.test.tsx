/**
 * Tests for RouteLoadingFallback component
 *
 * TDD RED Phase - These tests define the expected behavior of the loading fallback
 * component that will be shown while lazy-loaded routes are being fetched.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RouteLoadingFallback from './RouteLoadingFallback';

describe('RouteLoadingFallback', () => {
  it('renders without crashing', () => {
    render(<RouteLoadingFallback />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('displays a loading indicator', () => {
    render(<RouteLoadingFallback />);
    // Should have a spinner or loading animation
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has accessible loading text', () => {
    render(<RouteLoadingFallback />);
    // Should have accessible text for screen readers
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('uses appropriate ARIA attributes for loading state', () => {
    render(<RouteLoadingFallback />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-busy', 'true');
  });

  it('applies the correct styling classes', () => {
    render(<RouteLoadingFallback />);
    const container = screen.getByRole('status').parentElement;
    // Should be centered and take up available space
    expect(container).toHaveClass('flex');
  });
});
