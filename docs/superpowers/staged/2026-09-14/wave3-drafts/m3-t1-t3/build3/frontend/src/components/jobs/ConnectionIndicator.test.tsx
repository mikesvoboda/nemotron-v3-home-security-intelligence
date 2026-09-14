/**
 * Tests for ConnectionIndicator component (TDD RED)
 *
 * Shows WebSocket connection status for job log streaming:
 * - Green dot when connected
 * - Gray dot when reconnecting
 * - Red dot when failed
 *
 * NEM-2711
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import ConnectionIndicator from './ConnectionIndicator';

describe('ConnectionIndicator', () => {
  describe('rendering', () => {
    it('renders without crashing', () => {
      render(<ConnectionIndicator status="connected" />);
      expect(screen.getByTestId('connection-indicator')).toBeInTheDocument();
    });

    it('shows appropriate ARIA attributes for non-interactive state', () => {
      render(<ConnectionIndicator status="connected" />);
      const indicator = screen.getByTestId('connection-indicator');
      expect(indicator).toHaveAttribute('role', 'status');
      expect(indicator).toHaveAttribute('aria-live', 'polite');
    });

    it('shows button role when interactive (failed with onRetry)', () => {
      const onRetry = vi.fn();
      render(<ConnectionIndicator status="failed" onRetry={onRetry} />);
      const indicator = screen.getByTestId('connection-indicator');
      expect(indicator).toHaveAttribute('role', 'button');
      expect(indicator).toHaveAttribute('tabIndex', '0');
    });
  });

  describe('connected state', () => {
    it('shows green dot when connected', () => {
      render(<ConnectionIndicator status="connected" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('bg-green-500');
    });

    it('shows pulse animation when connected', () => {
      render(<ConnectionIndicator status="connected" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('animate-pulse');
    });

    it('shows "Live" label when connected and showLabel is true', () => {
      render(<ConnectionIndicator status="connected" showLabel />);
      expect(screen.getByText('Live')).toBeInTheDocument();
    });

    it('does not show label when showLabel is false', () => {
      render(<ConnectionIndicator status="connected" showLabel={false} />);
      expect(screen.queryByText('Live')).not.toBeInTheDocument();
    });

    it('has accessible label for screen readers', () => {
      render(<ConnectionIndicator status="connected" />);
      expect(screen.getByText(/connected/i, { selector: '.sr-only' })).toBeInTheDocument();
    });
  });

  describe('reconnecting state', () => {
    it('shows gray/yellow dot when reconnecting', () => {
      render(<ConnectionIndicator status="reconnecting" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('bg-yellow-500');
    });

    it('does not show pulse animation when reconnecting', () => {
      render(<ConnectionIndicator status="reconnecting" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).not.toHaveClass('animate-pulse');
    });

    it('shows "Reconnecting" label when reconnecting and showLabel is true', () => {
      render(<ConnectionIndicator status="reconnecting" showLabel />);
      expect(screen.getByText('Reconnecting')).toBeInTheDocument();
    });

    it('shows reconnect count when provided', () => {
      render(<ConnectionIndicator status="reconnecting" reconnectCount={2} showLabel />);
      expect(screen.getByText(/2/)).toBeInTheDocument();
    });

    it('has accessible label for reconnecting state', () => {
      render(<ConnectionIndicator status="reconnecting" />);
      expect(screen.getByText(/reconnecting/i, { selector: '.sr-only' })).toBeInTheDocument();
    });
  });

  describe('disconnected state', () => {
    it('shows gray dot when disconnected', () => {
      render(<ConnectionIndicator status="disconnected" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('bg-gray-500');
    });

    it('does not show pulse animation when disconnected', () => {
      render(<ConnectionIndicator status="disconnected" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).not.toHaveClass('animate-pulse');
    });

    it('shows "Offline" label when disconnected and showLabel is true', () => {
      render(<ConnectionIndicator status="disconnected" showLabel />);
      expect(screen.getByText('Offline')).toBeInTheDocument();
    });

    it('has accessible label for disconnected state', () => {
      render(<ConnectionIndicator status="disconnected" />);
      expect(screen.getByText(/disconnected/i, { selector: '.sr-only' })).toBeInTheDocument();
    });
  });

  describe('failed state', () => {
    it('shows red dot when failed', () => {
      render(<ConnectionIndicator status="failed" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('bg-red-500');
    });

    it('does not show pulse animation when failed', () => {
      render(<ConnectionIndicator status="failed" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).not.toHaveClass('animate-pulse');
    });

    it('shows "Failed" label when failed and showLabel is true', () => {
      render(<ConnectionIndicator status="failed" showLabel />);
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });

    it('has accessible label for failed state', () => {
      render(<ConnectionIndicator status="failed" />);
      expect(screen.getByText(/failed/i, { selector: '.sr-only' })).toBeInTheDocument();
    });

    it('calls onRetry when clicked in failed state', () => {
      const onRetry = vi.fn();
      render(<ConnectionIndicator status="failed" onRetry={onRetry} />);
      fireEvent.click(screen.getByTestId('connection-indicator'));
      expect(onRetry).toHaveBeenCalled();
    });

    it('does not call onRetry when clicked in connected state', () => {
      const onRetry = vi.fn();
      render(<ConnectionIndicator status="connected" onRetry={onRetry} />);
      fireEvent.click(screen.getByTestId('connection-indicator'));
      expect(onRetry).not.toHaveBeenCalled();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<ConnectionIndicator status="connected" className="custom-class" />);
      const indicator = screen.getByTestId('connection-indicator');
      expect(indicator).toHaveClass('custom-class');
    });

    it('has correct size for dot (small by default)', () => {
      render(<ConnectionIndicator status="connected" size="sm" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('h-2', 'w-2');
    });

    it('has correct size for dot (medium)', () => {
      render(<ConnectionIndicator status="connected" size="md" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('h-3', 'w-3');
    });

    it('has correct size for dot (large)', () => {
      render(<ConnectionIndicator status="connected" size="lg" />);
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('h-4', 'w-4');
    });
  });

  describe('tooltip', () => {
    it('shows tooltip on hover', () => {
      render(<ConnectionIndicator status="connected" showTooltip />);
      const indicator = screen.getByTestId('connection-indicator');
      fireEvent.mouseEnter(indicator);
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });

    it('shows connection status in tooltip', () => {
      render(<ConnectionIndicator status="connected" showTooltip />);
      const indicator = screen.getByTestId('connection-indicator');
      fireEvent.mouseEnter(indicator);
      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toHaveTextContent(/log streaming/i);
    });

    it('hides tooltip on mouse leave', () => {
      render(<ConnectionIndicator status="connected" showTooltip />);
      const indicator = screen.getByTestId('connection-indicator');
      fireEvent.mouseEnter(indicator);
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
      fireEvent.mouseLeave(indicator);
      // Tooltip should eventually disappear (may have delay)
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });
});
