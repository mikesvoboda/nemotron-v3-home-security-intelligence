/**
 * Tests for OfflineFallback component
 * TDD: Tests for offline status display component
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import OfflineFallback from './OfflineFallback';

describe('OfflineFallback', () => {
  // Store original navigator.onLine
  const originalOnLine = navigator.onLine;

  beforeEach(() => {
    vi.clearAllMocks();
    // Default to offline for tests
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    // Restore original value
    Object.defineProperty(navigator, 'onLine', {
      value: originalOnLine,
      writable: true,
      configurable: true,
    });
  });

  it('renders offline message', () => {
    render(<OfflineFallback />);

    expect(screen.getByText(/offline/i)).toBeInTheDocument();
  });

  it('displays connection lost icon', () => {
    render(<OfflineFallback />);

    const container = screen.getByTestId('offline-fallback');
    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });

  it('shows retry button when onRetry is provided', () => {
    const onRetry = vi.fn();
    render(<OfflineFallback onRetry={onRetry} />);

    expect(screen.getByRole('button', { name: /retry|try again/i })).toBeInTheDocument();
  });

  it('does not show retry button when onRetry is not provided', () => {
    render(<OfflineFallback />);

    expect(screen.queryByRole('button', { name: /retry|try again/i })).not.toBeInTheDocument();
  });

  it('calls onRetry when retry button is clicked', () => {
    const onRetry = vi.fn();
    render(<OfflineFallback onRetry={onRetry} />);

    const retryButton = screen.getByRole('button', { name: /retry|try again/i });
    fireEvent.click(retryButton);

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('displays cached events count when provided', () => {
    render(<OfflineFallback cachedEventsCount={5} />);

    expect(screen.getByText(/5/)).toBeInTheDocument();
    expect(screen.getByText(/cached/i)).toBeInTheDocument();
  });

  it('does not display cached events section when count is 0', () => {
    render(<OfflineFallback cachedEventsCount={0} />);

    // Should not show cached events message
    expect(screen.queryByText(/cached events/i)).not.toBeInTheDocument();
  });

  it('displays helpful offline tips', () => {
    render(<OfflineFallback />);

    // Should show some helpful message about offline mode
    const container = screen.getByTestId('offline-fallback');
    expect(container.textContent).toMatch(/network|connection|internet|wifi/i);
  });

  it('applies compact variant styling', () => {
    render(<OfflineFallback variant="compact" />);

    const container = screen.getByTestId('offline-fallback');
    // Compact should not have padding for full-page layout
    expect(container.className).not.toMatch(/min-h-screen/);
  });

  it('applies full-page variant styling', () => {
    render(<OfflineFallback variant="full-page" />);

    const container = screen.getByTestId('offline-fallback');
    // Full-page should take up screen
    expect(container.className).toMatch(/min-h-screen|h-full|flex/);
  });

  it('shows last online time when provided', () => {
    const lastOnline = new Date('2024-01-15T10:30:00Z');
    render(<OfflineFallback lastOnlineAt={lastOnline} />);

    // Should display some indication of when we were last online
    expect(screen.getByText(/last.*online|since|ago/i)).toBeInTheDocument();
  });

  it('has correct accessibility attributes', () => {
    render(<OfflineFallback />);

    const container = screen.getByTestId('offline-fallback');
    expect(container).toHaveAttribute('role', 'alert');
  });

  it('calls onRetry automatically when coming back online', async () => {
    const onRetry = vi.fn();
    render(<OfflineFallback onRetry={onRetry} autoRetryOnOnline />);

    // Simulate going online
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
    window.dispatchEvent(new Event('online'));

    await waitFor(() => {
      expect(onRetry).toHaveBeenCalled();
    });
  });

  it('does not auto-retry when autoRetryOnOnline is false', async () => {
    const onRetry = vi.fn();
    render(<OfflineFallback onRetry={onRetry} autoRetryOnOnline={false} />);

    // Simulate going online
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
    window.dispatchEvent(new Event('online'));

    // Wait a bit to ensure the callback is not called
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(onRetry).not.toHaveBeenCalled();
  });

  it('applies dark theme styling', () => {
    render(<OfflineFallback />);

    const container = screen.getByTestId('offline-fallback');
    // Should have dark background
    expect(container.className).toMatch(/bg-/);
  });

  it('renders with custom className', () => {
    render(<OfflineFallback className="custom-class" />);

    const container = screen.getByTestId('offline-fallback');
    expect(container).toHaveClass('custom-class');
  });
});
