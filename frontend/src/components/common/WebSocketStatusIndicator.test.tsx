import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import WebSocketStatusIndicator from './WebSocketStatusIndicator';

import type { WebSocketEndpointStatus } from './WebSocketStatusIndicator';

describe('WebSocketStatusIndicator', () => {
  const createMockEndpoint = (overrides: Partial<WebSocketEndpointStatus> = {}): WebSocketEndpointStatus => ({
    name: 'Events',
    state: 'connected',
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    hasExhaustedRetries: false,
    lastMessageTime: new Date(),
    ...overrides,
  });

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('renders without crashing', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events' })]}
        />
      );
      expect(screen.getByTestId('websocket-status-indicator')).toBeInTheDocument();
    });

    it('shows connection count when all connected', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
          ]}
        />
      );

      expect(screen.getByText('2/2')).toBeInTheDocument();
    });

    it('shows green status dot when all connected', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
          ]}
        />
      );

      const statusDot = screen.getByTestId('status-dot');
      expect(statusDot).toHaveClass('bg-green-500');
      expect(statusDot).toHaveClass('motion-safe:animate-pulse');
    });
  });

  describe('connection states', () => {
    it('shows yellow indicator when any endpoint is reconnecting', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'reconnecting', reconnectAttempts: 2 }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
          ]}
        />
      );

      const statusDot = screen.getByTestId('status-dot');
      expect(statusDot).toHaveClass('bg-yellow-500');
      expect(statusDot).not.toHaveClass('motion-safe:animate-pulse');
    });

    it('shows reconnect attempt count when reconnecting', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'reconnecting', reconnectAttempts: 3 }),
            createMockEndpoint({ name: 'System', state: 'reconnecting', reconnectAttempts: 2 }),
          ]}
        />
      );

      // Total attempts: 3 + 2 = 5
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('shows orange indicator when any endpoint has failed', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'failed', hasExhaustedRetries: true }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
          ]}
        />
      );

      const statusDot = screen.getByTestId('status-dot');
      expect(statusDot).toHaveClass('bg-orange-500');
    });

    it('shows red indicator when all disconnected', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'disconnected' }),
            createMockEndpoint({ name: 'System', state: 'disconnected' }),
          ]}
        />
      );

      const statusDot = screen.getByTestId('status-dot');
      expect(statusDot).toHaveClass('bg-red-500');
    });

    it('prioritizes failed state over reconnecting', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'failed', hasExhaustedRetries: true }),
            createMockEndpoint({ name: 'System', state: 'reconnecting', reconnectAttempts: 2 }),
          ]}
        />
      );

      const statusDot = screen.getByTestId('status-dot');
      expect(statusDot).toHaveClass('bg-orange-500');
    });
  });

  describe('compact mode', () => {
    it('hides text label in compact mode', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
          ]}
          compact
        />
      );

      expect(screen.queryByText('2/2')).not.toBeInTheDocument();
    });

    it('still shows status dot in compact mode', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', state: 'connected' })]}
          compact
        />
      );

      expect(screen.getByTestId('status-dot')).toBeInTheDocument();
    });
  });

  describe('tooltip', () => {
    it('shows tooltip on hover', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
          ]}
        />
      );

      expect(screen.queryByTestId('websocket-indicator-tooltip')).not.toBeInTheDocument();

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByTestId('websocket-indicator-tooltip')).toBeInTheDocument();
      expect(screen.getByText('WebSocket Connections')).toBeInTheDocument();
    });

    it('shows endpoint details in tooltip', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'disconnected' }),
          ]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByText('Events')).toBeInTheDocument();
      expect(screen.getByText('System')).toBeInTheDocument();
    });

    it('shows reconnect counter in tooltip for reconnecting endpoints', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({
              name: 'Events',
              state: 'reconnecting',
              reconnectAttempts: 3,
              maxReconnectAttempts: 5,
            }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
          ]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByText('3/5')).toBeInTheDocument();
    });

    it('shows connection ratio in tooltip header', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'disconnected' }),
            createMockEndpoint({ name: 'Detections', state: 'connected' }),
          ]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      // Find the ratio display in the tooltip header
      const tooltip = screen.getByTestId('websocket-indicator-tooltip');
      expect(tooltip).toHaveTextContent('2/3');
    });

    it('hides tooltip after mouse leave with delay', async () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', state: 'connected' })]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));
      expect(screen.getByTestId('websocket-indicator-tooltip')).toBeInTheDocument();

      fireEvent.mouseLeave(screen.getByTestId('websocket-status-indicator'));

      // Still visible immediately
      expect(screen.getByTestId('websocket-indicator-tooltip')).toBeInTheDocument();

      // Hidden after delay
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      expect(screen.queryByTestId('websocket-indicator-tooltip')).not.toBeInTheDocument();
    });

    it('cancels hide timeout on re-enter', async () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', state: 'connected' })]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));
      fireEvent.mouseLeave(screen.getByTestId('websocket-status-indicator'));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      expect(screen.getByTestId('websocket-indicator-tooltip')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper ARIA attributes', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
          ]}
        />
      );

      const indicator = screen.getByTestId('websocket-status-indicator');
      expect(indicator).toHaveAttribute('role', 'button');
      expect(indicator).toHaveAttribute('tabIndex', '0');
      expect(indicator).toHaveAttribute('aria-haspopup', 'true');
      expect(indicator).toHaveAttribute(
        'aria-label',
        'WebSocket status: Connected - 2 of 2 connected'
      );
    });

    it('includes click to retry hint when failed', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'failed', hasExhaustedRetries: true }),
          ]}
          onRetry={() => {}}
        />
      );

      const indicator = screen.getByTestId('websocket-status-indicator');
      expect(indicator).toHaveAttribute('aria-label', expect.stringContaining('Click to retry'));
    });
  });

  describe('retry functionality', () => {
    it('calls onRetry when clicked in failed state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'failed', hasExhaustedRetries: true }),
          ]}
          onRetry={onRetry}
        />
      );

      fireEvent.click(screen.getByTestId('websocket-status-indicator'));
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('does not call onRetry when clicked in connected state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', state: 'connected' })]}
          onRetry={onRetry}
        />
      );

      fireEvent.click(screen.getByTestId('websocket-status-indicator'));
      expect(onRetry).not.toHaveBeenCalled();
    });

    it('calls onRetry when Enter key is pressed in failed state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'failed', hasExhaustedRetries: true }),
          ]}
          onRetry={onRetry}
        />
      );

      fireEvent.keyDown(screen.getByTestId('websocket-status-indicator'), { key: 'Enter' });
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('calls onRetry when Space key is pressed in failed state', () => {
      const onRetry = vi.fn();
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'failed', hasExhaustedRetries: true }),
          ]}
          onRetry={onRetry}
        />
      );

      fireEvent.keyDown(screen.getByTestId('websocket-status-indicator'), { key: ' ' });
      expect(onRetry).toHaveBeenCalledTimes(1);
    });
  });

  describe('polling fallback', () => {
    it('shows polling indicator when isPollingFallback is true', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'failed', hasExhaustedRetries: true }),
          ]}
          isPollingFallback
        />
      );

      expect(screen.getByTestId('polling-indicator')).toBeInTheDocument();
      expect(screen.getByText('REST')).toBeInTheDocument();
    });

    it('does not show polling indicator when isPollingFallback is false', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', state: 'connected' })]}
          isPollingFallback={false}
        />
      );

      expect(screen.queryByTestId('polling-indicator')).not.toBeInTheDocument();
    });

    it('shows polling info in tooltip when in fallback mode', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'failed', hasExhaustedRetries: true }),
          ]}
          isPollingFallback
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByTestId('websocket-indicator-tooltip')).toHaveTextContent(/REST API/i);
    });
  });

  describe('time since last message', () => {
    it('shows "Just now" for recent messages in tooltip', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', lastMessageTime: new Date() })]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByText('Just now')).toBeInTheDocument();
    });

    it('shows seconds ago for messages under a minute old', () => {
      const thirtySecondsAgo = new Date(Date.now() - 30000);

      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', lastMessageTime: thirtySecondsAgo })]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByText('30s ago')).toBeInTheDocument();
    });

    it('shows minutes ago for older messages', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);

      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', lastMessageTime: fiveMinutesAgo })]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByText('5m ago')).toBeInTheDocument();
    });

    it('shows "No messages yet" when lastMessageTime is null', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', lastMessageTime: null })]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByText('No messages yet')).toBeInTheDocument();
    });

    it('updates time since message every second', async () => {
      const fourSecondsAgo = new Date(Date.now() - 4000);

      render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', lastMessageTime: fourSecondsAgo })]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByText('Just now')).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });

      expect(screen.getByText('6s ago')).toBeInTheDocument();
    });
  });

  describe('size variants', () => {
    it('uses smaller icons for sm size', () => {
      const { container } = render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', state: 'connected' })]}
          size="sm"
        />
      );

      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('h-3.5', 'w-3.5');
    });

    it('uses larger icons for md size', () => {
      const { container } = render(
        <WebSocketStatusIndicator
          endpoints={[createMockEndpoint({ name: 'Events', state: 'connected' })]}
          size="md"
        />
      );

      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('h-4', 'w-4');
    });
  });

  describe('empty endpoints', () => {
    it('handles empty endpoints array gracefully', () => {
      render(<WebSocketStatusIndicator endpoints={[]} />);

      const statusDot = screen.getByTestId('status-dot');
      expect(statusDot).toHaveClass('bg-red-500');
    });
  });

  describe('three endpoints', () => {
    it('correctly calculates overall state with three endpoints', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
            createMockEndpoint({ name: 'Detections', state: 'connected' }),
          ]}
        />
      );

      const statusDot = screen.getByTestId('status-dot');
      expect(statusDot).toHaveClass('bg-green-500');
      expect(screen.getByText('3/3')).toBeInTheDocument();
    });

    it('shows yellow when one of three is reconnecting', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'reconnecting', reconnectAttempts: 2 }),
            createMockEndpoint({ name: 'Detections', state: 'connected' }),
          ]}
        />
      );

      const statusDot = screen.getByTestId('status-dot');
      expect(statusDot).toHaveClass('bg-yellow-500');
    });

    it('shows all three endpoints in tooltip', () => {
      render(
        <WebSocketStatusIndicator
          endpoints={[
            createMockEndpoint({ name: 'Events', state: 'connected' }),
            createMockEndpoint({ name: 'System', state: 'connected' }),
            createMockEndpoint({ name: 'Detections', state: 'connected' }),
          ]}
        />
      );

      fireEvent.mouseEnter(screen.getByTestId('websocket-status-indicator'));

      expect(screen.getByText('Events')).toBeInTheDocument();
      expect(screen.getByText('System')).toBeInTheDocument();
      expect(screen.getByText('Detections')).toBeInTheDocument();
    });
  });
});
