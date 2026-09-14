import { render, screen, fireEvent, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import ConnectionStatusBanner from './ConnectionStatusBanner';
import { AnnouncementProvider } from '../../contexts/AnnouncementContext';

/**
 * Wrapper component that provides the AnnouncementProvider context
 */
function Wrapper({ children }: { children: ReactNode }) {
  return <AnnouncementProvider>{children}</AnnouncementProvider>;
}

/**
 * Helper to render with context
 */
function renderWithContext(ui: React.ReactElement) {
  return render(ui, { wrapper: Wrapper });
}

describe('ConnectionStatusBanner', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Visibility', () => {
    it('does not render when connected', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="connected"
          disconnectedSince={null}
          onRetry={() => {}}
        />
      );

      expect(screen.queryByTestId('connection-status-banner')).not.toBeInTheDocument();
    });

    it('renders when disconnected', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('connection-status-banner')).toBeInTheDocument();
    });

    it('renders when reconnecting', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="reconnecting"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('connection-status-banner')).toBeInTheDocument();
    });

    it('renders when connection failed', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="failed"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('connection-status-banner')).toBeInTheDocument();
    });
  });

  describe('Connection States', () => {
    it('shows disconnected state with red styling', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      const banner = screen.getByTestId('connection-status-banner');
      expect(banner).toHaveClass('bg-red-900/30');
      expect(screen.getByText(/disconnected/i)).toBeInTheDocument();
    });

    it('shows reconnecting state with yellow/amber styling', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="reconnecting"
          disconnectedSince={new Date()}
          reconnectAttempts={2}
          maxReconnectAttempts={5}
          onRetry={() => {}}
        />
      );

      const banner = screen.getByTestId('connection-status-banner');
      expect(banner).toHaveClass('bg-yellow-900/30');
      expect(screen.getByText(/reconnecting/i)).toBeInTheDocument();
    });

    it('shows failed state with orange styling', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="failed"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      const banner = screen.getByTestId('connection-status-banner');
      expect(banner).toHaveClass('bg-orange-900/30');
      expect(screen.getByText(/connection failed/i)).toBeInTheDocument();
    });
  });

  describe('Reconnection counter', () => {
    it('shows reconnection attempt counter when reconnecting', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="reconnecting"
          disconnectedSince={new Date()}
          reconnectAttempts={3}
          maxReconnectAttempts={5}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('reconnect-counter')).toHaveTextContent('Attempt 3/5');
    });

    it('does not show reconnection counter when not reconnecting', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          reconnectAttempts={0}
          maxReconnectAttempts={5}
          onRetry={() => {}}
        />
      );

      expect(screen.queryByTestId('reconnect-counter')).not.toBeInTheDocument();
    });
  });

  describe('Disconnected duration', () => {
    it('shows how long disconnected for recent disconnect', () => {
      const tenSecondsAgo = new Date(Date.now() - 10000);
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={tenSecondsAgo}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('disconnected-duration')).toHaveTextContent('10s');
    });

    it('shows minutes when disconnected for over a minute', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={fiveMinutesAgo}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('disconnected-duration')).toHaveTextContent('5m');
    });

    it('updates duration every second', async () => {
      const tenSecondsAgo = new Date(Date.now() - 10000);
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={tenSecondsAgo}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('disconnected-duration')).toHaveTextContent('10s');

      // Advance time by 5 seconds
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });

      expect(screen.getByTestId('disconnected-duration')).toHaveTextContent('15s');
    });
  });

  describe('Stale data indicator', () => {
    it('shows stale data warning when disconnected for extended period', () => {
      // 2 minutes ago
      const twoMinutesAgo = new Date(Date.now() - 2 * 60 * 1000);
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={twoMinutesAgo}
          onRetry={() => {}}
          staleThresholdMs={60000} // 1 minute threshold
        />
      );

      expect(screen.getByTestId('stale-data-warning')).toBeInTheDocument();
      expect(screen.getByText(/data may be stale/i)).toBeInTheDocument();
    });

    it('does not show stale data warning for brief disconnection', () => {
      // 30 seconds ago
      const thirtySecondsAgo = new Date(Date.now() - 30000);
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={thirtySecondsAgo}
          onRetry={() => {}}
          staleThresholdMs={60000} // 1 minute threshold
        />
      );

      expect(screen.queryByTestId('stale-data-warning')).not.toBeInTheDocument();
    });

    it('shows which data types may be stale', () => {
      const twoMinutesAgo = new Date(Date.now() - 2 * 60 * 1000);
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={twoMinutesAgo}
          onRetry={() => {}}
          staleThresholdMs={60000}
        />
      );

      // Should indicate events and system status may be stale
      const warning = screen.getByTestId('stale-data-warning');
      expect(warning).toHaveTextContent(/events/i);
      expect(warning).toHaveTextContent(/system status/i);
    });
  });

  describe('Retry button', () => {
    it('shows retry button when connection failed', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="failed"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('retry-button')).toBeInTheDocument();
    });

    it('calls onRetry when retry button is clicked', () => {
      const onRetry = vi.fn();
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="failed"
          disconnectedSince={new Date()}
          onRetry={onRetry}
        />
      );

      fireEvent.click(screen.getByTestId('retry-button'));
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('does not show retry button when reconnecting (auto-retry in progress)', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="reconnecting"
          disconnectedSince={new Date()}
          reconnectAttempts={2}
          maxReconnectAttempts={5}
          onRetry={() => {}}
        />
      );

      expect(screen.queryByTestId('retry-button')).not.toBeInTheDocument();
    });
  });

  describe('Dismiss button', () => {
    it('shows dismiss button', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('dismiss-button')).toBeInTheDocument();
    });

    it('hides banner when dismiss button is clicked', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      expect(screen.getByTestId('connection-status-banner')).toBeInTheDocument();

      fireEvent.click(screen.getByTestId('dismiss-button'));

      expect(screen.queryByTestId('connection-status-banner')).not.toBeInTheDocument();
    });

    it('reappears after dismissal when state changes', () => {
      const { rerender } = renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      // Dismiss the banner
      fireEvent.click(screen.getByTestId('dismiss-button'));
      expect(screen.queryByTestId('connection-status-banner')).not.toBeInTheDocument();

      // Connection reconnects (banner still hidden since connected doesn't render)
      rerender(
        <Wrapper>
          <ConnectionStatusBanner
            connectionState="connected"
            disconnectedSince={null}
            onRetry={() => {}}
          />
        </Wrapper>
      );
      expect(screen.queryByTestId('connection-status-banner')).not.toBeInTheDocument();

      // Disconnect again - banner should reappear
      rerender(
        <Wrapper>
          <ConnectionStatusBanner
            connectionState="disconnected"
            disconnectedSince={new Date()}
            onRetry={() => {}}
          />
        </Wrapper>
      );
      expect(screen.getByTestId('connection-status-banner')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA attributes', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      const banner = screen.getByTestId('connection-status-banner');
      expect(banner).toHaveAttribute('role', 'alert');
      expect(banner).toHaveAttribute('aria-live', 'polite');
    });

    it('has accessible dismiss button', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      const dismissButton = screen.getByTestId('dismiss-button');
      expect(dismissButton).toHaveAttribute('aria-label', 'Dismiss notification');
    });

    it('has accessible retry button', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="failed"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      const retryButton = screen.getByTestId('retry-button');
      expect(retryButton).toHaveAttribute('aria-label', 'Retry connection');
    });
  });

  describe('Screen reader announcements', () => {
    it('announces state changes to screen readers via live region', () => {
      const { rerender } = renderWithContext(
        <ConnectionStatusBanner
          connectionState="connected"
          disconnectedSince={null}
          onRetry={() => {}}
        />
      );

      // Transition to disconnected
      rerender(
        <Wrapper>
          <ConnectionStatusBanner
            connectionState="disconnected"
            disconnectedSince={new Date()}
            onRetry={() => {}}
          />
        </Wrapper>
      );

      // The announcement happens via the live region, which is handled by the context
      // We verify the component uses useAnnounce by checking it renders without error
      expect(screen.getByTestId('connection-status-banner')).toBeInTheDocument();
    });

    it('renders with AnnouncementProvider without error', () => {
      // This test verifies the useAnnounce hook integration works
      expect(() =>
        renderWithContext(
          <ConnectionStatusBanner
            connectionState="failed"
            disconnectedSince={new Date()}
            onRetry={() => {}}
          />
        )
      ).not.toThrow();
    });
  });

  describe('Animation', () => {
    it('has pulsing animation when reconnecting', () => {
      const { container } = renderWithContext(
        <ConnectionStatusBanner
          connectionState="reconnecting"
          disconnectedSince={new Date()}
          reconnectAttempts={1}
          maxReconnectAttempts={5}
          onRetry={() => {}}
        />
      );

      // Check for spinner icon with animation
      const spinner = container.querySelector('svg.motion-safe\\:animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Icons', () => {
    it('shows WifiOff icon when disconnected', () => {
      const { container } = renderWithContext(
        <ConnectionStatusBanner
          connectionState="disconnected"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      // lucide-react renders an svg
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('shows RefreshCw icon when reconnecting', () => {
      const { container } = renderWithContext(
        <ConnectionStatusBanner
          connectionState="reconnecting"
          disconnectedSince={new Date()}
          reconnectAttempts={1}
          maxReconnectAttempts={5}
          onRetry={() => {}}
        />
      );

      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('shows AlertTriangle icon when failed', () => {
      const { container } = renderWithContext(
        <ConnectionStatusBanner
          connectionState="failed"
          disconnectedSince={new Date()}
          onRetry={() => {}}
        />
      );

      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('Polling fallback indicator', () => {
    it('shows polling fallback indicator when enabled', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="failed"
          disconnectedSince={new Date()}
          onRetry={() => {}}
          isPollingFallback={true}
        />
      );

      expect(screen.getByTestId('polling-fallback-indicator')).toBeInTheDocument();
      expect(screen.getByText(/rest api/i)).toBeInTheDocument();
    });

    it('does not show polling indicator when not in fallback mode', () => {
      renderWithContext(
        <ConnectionStatusBanner
          connectionState="failed"
          disconnectedSince={new Date()}
          onRetry={() => {}}
          isPollingFallback={false}
        />
      );

      expect(screen.queryByTestId('polling-fallback-indicator')).not.toBeInTheDocument();
    });
  });
});
