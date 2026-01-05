import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import WebSocketStatus from './WebSocketStatus';

import type { ChannelStatus } from '../../hooks/useWebSocketStatus';

describe('WebSocketStatus', () => {
  const createMockChannel = (
    overrides: Partial<ChannelStatus> = {}
  ): ChannelStatus => ({
    name: 'Events',
    state: 'connected',
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    lastMessageTime: new Date(),
    hasExhaustedRetries: false,
    ...overrides,
  });

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders without crashing', () => {
    render(
      <WebSocketStatus
        eventsChannel={createMockChannel({ name: 'Events' })}
        systemChannel={createMockChannel({ name: 'System' })}
      />
    );
    expect(screen.getByTestId('websocket-status')).toBeInTheDocument();
  });

  it('shows green indicator when both channels connected', () => {
    render(
      <WebSocketStatus
        eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
        systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
      />
    );

    const statusDot = screen.getByTestId('overall-status-dot');
    expect(statusDot).toHaveClass('bg-green-500');
    expect(statusDot).toHaveClass('animate-pulse');
  });

  it('shows yellow indicator when either channel is reconnecting', () => {
    render(
      <WebSocketStatus
        eventsChannel={createMockChannel({ name: 'Events', state: 'reconnecting', reconnectAttempts: 2 })}
        systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
      />
    );

    const statusDot = screen.getByTestId('overall-status-dot');
    expect(statusDot).toHaveClass('bg-yellow-500');
    expect(statusDot).not.toHaveClass('animate-pulse');
  });

  it('shows red indicator when channels are disconnected', () => {
    render(
      <WebSocketStatus
        eventsChannel={createMockChannel({ name: 'Events', state: 'disconnected' })}
        systemChannel={createMockChannel({ name: 'System', state: 'disconnected' })}
      />
    );

    const statusDot = screen.getByTestId('overall-status-dot');
    expect(statusDot).toHaveClass('bg-red-500');
  });

  it('shows reconnection label with attempt count when reconnecting', () => {
    render(
      <WebSocketStatus
        eventsChannel={createMockChannel({ name: 'Events', state: 'reconnecting', reconnectAttempts: 3 })}
        systemChannel={createMockChannel({ name: 'System', state: 'reconnecting', reconnectAttempts: 2 })}
      />
    );

    const label = screen.getByTestId('connection-label');
    expect(label).toHaveTextContent('Reconnecting (5)');
  });

  it('does not show label when connected and showDetails is false', () => {
    render(
      <WebSocketStatus
        eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
        systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        showDetails={false}
      />
    );

    expect(screen.queryByTestId('connection-label')).not.toBeInTheDocument();
  });

  it('shows Connected label when showDetails is true', () => {
    render(
      <WebSocketStatus
        eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
        systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        showDetails={true}
      />
    );

    const label = screen.getByTestId('connection-label');
    expect(label).toHaveTextContent('Connected');
    expect(label).toHaveClass('text-green-400');
  });

  it('has proper ARIA attributes', () => {
    render(
      <WebSocketStatus
        eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
        systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
      />
    );

    const status = screen.getByTestId('websocket-status');
    expect(status).toHaveAttribute('role', 'button');
    expect(status).toHaveAttribute('tabIndex', '0');
    expect(status).toHaveAttribute('aria-label', 'WebSocket connection status: Connected');
    expect(status).toHaveAttribute('aria-haspopup', 'true');
  });

  describe('Tooltip', () => {
    it('shows tooltip on hover with channel details', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        />
      );

      // Tooltip should not be visible initially
      expect(screen.queryByTestId('websocket-tooltip')).not.toBeInTheDocument();

      // Hover to show tooltip
      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      // Tooltip should be visible
      const tooltip = screen.getByTestId('websocket-tooltip');
      expect(tooltip).toBeInTheDocument();
      expect(screen.getByText('WebSocket Channels')).toBeInTheDocument();
    });

    it('shows channel status details in tooltip', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'disconnected' })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      // Check channel names
      expect(screen.getByText('Events')).toBeInTheDocument();
      expect(screen.getByText('System')).toBeInTheDocument();

      // Check dot colors
      const eventsDot = screen.getByTestId('channel-dot-events');
      expect(eventsDot).toHaveClass('bg-green-500');

      const systemDot = screen.getByTestId('channel-dot-system');
      expect(systemDot).toHaveClass('bg-red-500');
    });

    it('shows reconnect counter for reconnecting channels', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({
            name: 'Events',
            state: 'reconnecting',
            reconnectAttempts: 3,
            maxReconnectAttempts: 5,
          })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const reconnectCounter = screen.getByTestId('reconnect-counter-events');
      expect(reconnectCounter).toHaveTextContent('Attempt 3/5');
    });

    it('hides tooltip after mouse leave with delay', async () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        />
      );

      // Show tooltip
      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));
      expect(screen.getByTestId('websocket-tooltip')).toBeInTheDocument();

      // Mouse leave
      fireEvent.mouseLeave(screen.getByTestId('websocket-status'));

      // Tooltip should still be visible immediately
      expect(screen.getByTestId('websocket-tooltip')).toBeInTheDocument();

      // Advance past the delay
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      // Tooltip should be hidden
      expect(screen.queryByTestId('websocket-tooltip')).not.toBeInTheDocument();
    });

    it('cancels tooltip hide timeout on re-enter', async () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        />
      );

      // Show tooltip
      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      // Start to leave
      fireEvent.mouseLeave(screen.getByTestId('websocket-status'));

      // Re-enter before timeout
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      // Advance past the original timeout
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      // Tooltip should still be visible
      expect(screen.getByTestId('websocket-tooltip')).toBeInTheDocument();
    });
  });

  describe('Time since last message', () => {
    it('shows "Just now" for recent messages', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', lastMessageTime: new Date() })}
          systemChannel={createMockChannel({ name: 'System', lastMessageTime: new Date() })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const eventsLastMessage = screen.getByTestId('last-message-events');
      expect(eventsLastMessage).toHaveTextContent('Just now');
    });

    it('shows seconds ago for messages under a minute old', () => {
      const thirtySecondsAgo = new Date(Date.now() - 30000);

      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', lastMessageTime: thirtySecondsAgo })}
          systemChannel={createMockChannel({ name: 'System', lastMessageTime: new Date() })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const eventsLastMessage = screen.getByTestId('last-message-events');
      expect(eventsLastMessage).toHaveTextContent('30s ago');
    });

    it('shows minutes ago for older messages', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);

      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', lastMessageTime: fiveMinutesAgo })}
          systemChannel={createMockChannel({ name: 'System', lastMessageTime: new Date() })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const eventsLastMessage = screen.getByTestId('last-message-events');
      expect(eventsLastMessage).toHaveTextContent('5m ago');
    });

    it('shows "No messages yet" when lastMessageTime is null', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', lastMessageTime: null })}
          systemChannel={createMockChannel({ name: 'System', lastMessageTime: new Date() })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const eventsLastMessage = screen.getByTestId('last-message-events');
      expect(eventsLastMessage).toHaveTextContent('No messages yet');
    });

    it('shows hours ago for messages over an hour old', () => {
      const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);

      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', lastMessageTime: twoHoursAgo })}
          systemChannel={createMockChannel({ name: 'System', lastMessageTime: new Date() })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const eventsLastMessage = screen.getByTestId('last-message-events');
      expect(eventsLastMessage).toHaveTextContent('2h ago');
    });

    it('updates time since message every second', async () => {
      const fourSecondsAgo = new Date(Date.now() - 4000);

      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', lastMessageTime: fourSecondsAgo })}
          systemChannel={createMockChannel({ name: 'System', lastMessageTime: new Date() })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const eventsLastMessage = screen.getByTestId('last-message-events');
      expect(eventsLastMessage).toHaveTextContent('Just now');

      // Advance time by 2 seconds to cross the 5-second threshold
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });

      // Should now show seconds
      expect(eventsLastMessage).toHaveTextContent('6s ago');
    });
  });

  describe('Icon states', () => {
    it('shows Wifi icon when connected', () => {
      const { container } = render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        />
      );

      // lucide-react adds svg with specific class
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('shows spinning RefreshCw icon when reconnecting', () => {
      const { container } = render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'reconnecting' })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        />
      );

      const svg = container.querySelector('svg');
      expect(svg).toHaveClass('animate-spin');
    });
  });

  describe('Styling', () => {
    it('has cursor-pointer class', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events' })}
          systemChannel={createMockChannel({ name: 'System' })}
        />
      );

      expect(screen.getByTestId('websocket-status')).toHaveClass('cursor-pointer');
    });

    it('applies correct colors for reconnecting state', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'reconnecting' })}
          systemChannel={createMockChannel({ name: 'System', state: 'reconnecting' })}
          showDetails={true}
        />
      );

      const label = screen.getByTestId('connection-label');
      expect(label).toHaveClass('text-yellow-400');
    });

    it('applies correct colors for disconnected state', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'disconnected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'disconnected' })}
          showDetails={true}
        />
      );

      const label = screen.getByTestId('connection-label');
      expect(label).toHaveClass('text-red-400');
    });
  });

  describe('Failed state', () => {
    it('shows orange indicator when connection has failed', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        />
      );

      const statusDot = screen.getByTestId('overall-status-dot');
      expect(statusDot).toHaveClass('bg-orange-500');
    });

    it('shows Connection Failed label when in failed state', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'failed', hasExhaustedRetries: true })}
        />
      );

      const label = screen.getByTestId('connection-label');
      expect(label).toHaveTextContent('Connection Failed');
      expect(label).toHaveClass('text-orange-400');
    });

    it('shows Retries exhausted message in tooltip for failed channel', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({
            name: 'Events',
            state: 'failed',
            hasExhaustedRetries: true,
            reconnectAttempts: 5,
            maxReconnectAttempts: 5,
          })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const failedIndicator = screen.getByTestId('failed-indicator-events');
      expect(failedIndicator).toHaveTextContent('Retries exhausted');
    });

    it('includes click to retry hint in aria-label when failed', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
          onRetry={() => {}}
        />
      );

      const status = screen.getByTestId('websocket-status');
      expect(status).toHaveAttribute('aria-label', expect.stringContaining('Click to retry'));
    });

    it('calls onRetry when clicked in failed state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'failed', hasExhaustedRetries: true })}
          onRetry={onRetry}
        />
      );

      fireEvent.click(screen.getByTestId('websocket-status'));
      expect(onRetry).toHaveBeenCalled();
    });

    it('does not call onRetry when clicked in connected state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
          onRetry={onRetry}
        />
      );

      fireEvent.click(screen.getByTestId('websocket-status'));
      expect(onRetry).not.toHaveBeenCalled();
    });

    it('calls onRetry when Enter key is pressed in failed state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'failed', hasExhaustedRetries: true })}
          onRetry={onRetry}
        />
      );

      const status = screen.getByTestId('websocket-status');
      fireEvent.keyDown(status, { key: 'Enter' });
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('calls onRetry when Space key is pressed in failed state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'failed', hasExhaustedRetries: true })}
          onRetry={onRetry}
        />
      );

      const status = screen.getByTestId('websocket-status');
      fireEvent.keyDown(status, { key: ' ' });
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('does not call onRetry when Enter key is pressed in connected state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
          onRetry={onRetry}
        />
      );

      const status = screen.getByTestId('websocket-status');
      fireEvent.keyDown(status, { key: 'Enter' });
      expect(onRetry).not.toHaveBeenCalled();
    });

    it('does not call onRetry when other keys are pressed in failed state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'failed', hasExhaustedRetries: true })}
          onRetry={onRetry}
        />
      );

      const status = screen.getByTestId('websocket-status');
      fireEvent.keyDown(status, { key: 'Tab' });
      fireEvent.keyDown(status, { key: 'Escape' });
      expect(onRetry).not.toHaveBeenCalled();
    });
  });

  describe('Polling fallback indicator', () => {
    it('shows polling indicator when isPollingFallback is true', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'failed', hasExhaustedRetries: true })}
          isPollingFallback={true}
        />
      );

      const pollingIndicator = screen.getByTestId('polling-indicator');
      expect(pollingIndicator).toBeInTheDocument();
      expect(pollingIndicator).toHaveTextContent(/polling/i);
    });

    it('does not show polling indicator when isPollingFallback is false', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'connected' })}
          systemChannel={createMockChannel({ name: 'System', state: 'connected' })}
          isPollingFallback={false}
        />
      );

      expect(screen.queryByTestId('polling-indicator')).not.toBeInTheDocument();
    });

    it('shows polling indicator when isPollingFallback is true even without explicit prop', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'failed', hasExhaustedRetries: true })}
          isPollingFallback={true}
        />
      );

      // Should show that we're using REST API polling as fallback
      const pollingIndicator = screen.getByTestId('polling-indicator');
      expect(pollingIndicator).toHaveClass('text-blue-400');
    });

    it('includes polling info in tooltip when in polling fallback mode', () => {
      render(
        <WebSocketStatus
          eventsChannel={createMockChannel({ name: 'Events', state: 'failed', hasExhaustedRetries: true })}
          systemChannel={createMockChannel({ name: 'System', state: 'failed', hasExhaustedRetries: true })}
          isPollingFallback={true}
        />
      );

      // Hover to show tooltip
      fireEvent.mouseEnter(screen.getByTestId('websocket-status'));

      const tooltip = screen.getByTestId('websocket-tooltip');
      expect(tooltip).toHaveTextContent(/REST API/i);
    });
  });
});
