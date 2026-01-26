/**
 * Tests for OfflineIndicator component
 * @see NEM-3675 - PWA Offline Caching
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import OfflineIndicator from './OfflineIndicator';

describe('OfflineIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('visibility', () => {
    it('does not render when online (isOffline=false)', () => {
      render(<OfflineIndicator isOffline={false} />);
      expect(screen.queryByTestId('offline-indicator')).not.toBeInTheDocument();
    });

    it('renders when offline (isOffline=true)', () => {
      render(<OfflineIndicator isOffline={true} />);
      expect(screen.getByTestId('offline-indicator')).toBeInTheDocument();
    });

    it('respects show prop override', () => {
      // Show when online via show prop
      render(<OfflineIndicator isOffline={false} show={true} />);
      expect(screen.getByTestId('offline-indicator')).toBeInTheDocument();
    });

    it('hides when show=false even if offline', () => {
      render(<OfflineIndicator isOffline={true} show={false} />);
      expect(screen.queryByTestId('offline-indicator')).not.toBeInTheDocument();
    });
  });

  describe('banner variant', () => {
    it('displays "Offline Mode" text', () => {
      render(<OfflineIndicator isOffline={true} variant="banner" />);
      expect(screen.getByText('Offline Mode')).toBeInTheDocument();
    });

    it('displays cached events count', () => {
      render(<OfflineIndicator isOffline={true} variant="banner" cachedEventsCount={15} />);
      expect(screen.getByText(/15 events cached/)).toBeInTheDocument();
    });

    it('displays last online time', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      render(<OfflineIndicator isOffline={true} variant="banner" lastOnlineAt={fiveMinutesAgo} />);
      expect(screen.getByText(/5 minutes ago/)).toBeInTheDocument();
    });

    it('shows retry button when onRetry provided', () => {
      const onRetry = vi.fn();
      render(<OfflineIndicator isOffline={true} variant="banner" onRetry={onRetry} />);
      const retryButton = screen.getByRole('button', { name: /retry/i });
      expect(retryButton).toBeInTheDocument();
      fireEvent.click(retryButton);
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('shows dismiss button when dismissible', () => {
      render(<OfflineIndicator isOffline={true} variant="banner" dismissible />);
      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
    });

    it('hides on dismiss', () => {
      const onDismiss = vi.fn();
      render(<OfflineIndicator isOffline={true} variant="banner" dismissible onDismiss={onDismiss} />);
      const dismissButton = screen.getByRole('button', { name: /dismiss/i });
      fireEvent.click(dismissButton);
      expect(onDismiss).toHaveBeenCalledTimes(1);
      expect(screen.queryByTestId('offline-indicator')).not.toBeInTheDocument();
    });
  });

  describe('badge variant', () => {
    it('renders as a badge', () => {
      render(<OfflineIndicator isOffline={true} variant="badge" />);
      expect(screen.getByText('Offline')).toBeInTheDocument();
    });

    it('shows cached count in badge', () => {
      render(<OfflineIndicator isOffline={true} variant="badge" cachedEventsCount={5} />);
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  describe('minimal variant', () => {
    it('renders as minimal icon', () => {
      render(<OfflineIndicator isOffline={true} variant="minimal" />);
      const indicator = screen.getByTestId('offline-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Offline');
    });
  });

  describe('position', () => {
    it.each([
      ['top-left', 'top-4 left-4'],
      ['top-right', 'top-4 right-4'],
      ['bottom-left', 'bottom-4 left-4'],
      ['bottom-right', 'bottom-4 right-4'],
      ['top', 'top-0 left-0 right-0'],
      ['bottom', 'bottom-0 left-0 right-0'],
    ] as const)('applies %s position classes', (position, expectedClasses) => {
      render(<OfflineIndicator isOffline={true} position={position} />);
      const indicator = screen.getByTestId('offline-indicator');
      expectedClasses.split(' ').forEach((cls) => {
        expect(indicator.className).toContain(cls);
      });
    });
  });

  describe('duration formatting', () => {
    it('shows "Just now" for recent offline', () => {
      const justNow = new Date();
      render(<OfflineIndicator isOffline={true} variant="banner" lastOnlineAt={justNow} />);
      expect(screen.getByText(/Just now/)).toBeInTheDocument();
    });

    it('shows minutes for < 1 hour', () => {
      const thirtyMinutesAgo = new Date(Date.now() - 30 * 60 * 1000);
      render(<OfflineIndicator isOffline={true} variant="banner" lastOnlineAt={thirtyMinutesAgo} />);
      expect(screen.getByText(/30 minutes ago/)).toBeInTheDocument();
    });

    it('shows hours for >= 1 hour', () => {
      const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
      render(<OfflineIndicator isOffline={true} variant="banner" lastOnlineAt={twoHoursAgo} />);
      expect(screen.getByText(/2 hours ago/)).toBeInTheDocument();
    });

    it('shows days for >= 24 hours', () => {
      const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
      render(<OfflineIndicator isOffline={true} variant="banner" lastOnlineAt={twoDaysAgo} />);
      expect(screen.getByText(/2 days ago/)).toBeInTheDocument();
    });

    it('shows "Unknown duration" when lastOnlineAt is null', () => {
      render(<OfflineIndicator isOffline={true} variant="banner" lastOnlineAt={null} />);
      expect(screen.getByText(/Unknown duration/)).toBeInTheDocument();
    });

    it('updates duration every minute', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      render(<OfflineIndicator isOffline={true} variant="banner" lastOnlineAt={fiveMinutesAgo} />);
      expect(screen.getByText(/5 minutes ago/)).toBeInTheDocument();

      // Advance time by 1 minute
      act(() => {
        vi.advanceTimersByTime(60000);
      });
      expect(screen.getByText(/6 minutes ago/)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has appropriate role for banner', () => {
      render(<OfflineIndicator isOffline={true} variant="banner" />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('has appropriate role for badge', () => {
      render(<OfflineIndicator isOffline={true} variant="badge" />);
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has aria-live attribute', () => {
      render(<OfflineIndicator isOffline={true} variant="banner" />);
      expect(screen.getByTestId('offline-indicator')).toHaveAttribute('aria-live');
    });
  });

  describe('dismissed state reset', () => {
    it('resets dismissed state when coming back online', () => {
      const { rerender } = render(
        <OfflineIndicator isOffline={true} variant="banner" dismissible />
      );

      // Dismiss the indicator
      const dismissButton = screen.getByRole('button', { name: /dismiss/i });
      fireEvent.click(dismissButton);
      expect(screen.queryByTestId('offline-indicator')).not.toBeInTheDocument();

      // Go online
      rerender(<OfflineIndicator isOffline={false} variant="banner" dismissible />);

      // Go offline again - should show again
      rerender(<OfflineIndicator isOffline={true} variant="banner" dismissible />);
      expect(screen.getByTestId('offline-indicator')).toBeInTheDocument();
    });
  });
});
