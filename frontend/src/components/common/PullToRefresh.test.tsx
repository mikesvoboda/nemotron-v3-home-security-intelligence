/**
 * @fileoverview Tests for PullToRefresh component.
 *
 * This component provides visual feedback for pull-to-refresh gestures
 * and wraps content with touch event handling for mobile devices.
 *
 * @see NEM-2970
 */
import { render, screen, waitFor } from '@testing-library/react';
import { act } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { PullToRefresh } from './PullToRefresh';

describe('PullToRefresh', () => {
  // Helper to create touch events
  function createTouchEvent(
    type: 'touchstart' | 'touchmove' | 'touchend',
    clientY: number,
    clientX: number = 0
  ): TouchEvent {
    const touch = {
      clientY,
      clientX,
      identifier: 0,
      target: document.createElement('div'),
      screenX: clientX,
      screenY: clientY,
      pageX: clientX,
      pageY: clientY,
      radiusX: 0,
      radiusY: 0,
      rotationAngle: 0,
      force: 0,
    } as Touch;

    const event = new TouchEvent(type, {
      touches: type === 'touchend' ? [] : [touch],
      changedTouches: [touch],
      bubbles: true,
      cancelable: true,
    });

    return event;
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders children content', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh}>
          <div data-testid="child-content">Test Content</div>
        </PullToRefresh>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
      expect(screen.getByText('Test Content')).toBeInTheDocument();
    });

    it('renders pull-to-refresh container', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh}>
          <div>Content</div>
        </PullToRefresh>
      );

      expect(screen.getByTestId('pull-to-refresh-container')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh} className="custom-class">
          <div>Content</div>
        </PullToRefresh>
      );

      expect(screen.getByTestId('pull-to-refresh-container')).toHaveClass('custom-class');
    });
  });

  describe('pull indicator', () => {
    it('hides pull indicator initially', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh}>
          <div>Content</div>
        </PullToRefresh>
      );

      const indicator = screen.queryByTestId('pull-indicator');
      // Indicator should not be visible or have height 0
      expect(indicator?.style.height).toBe('0px');
    });

    it('shows pull indicator during pull gesture', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh}>
          <div>Content</div>
        </PullToRefresh>
      );

      const container = screen.getByTestId('pull-to-refresh-container');

      act(() => {
        container.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        container.dispatchEvent(createTouchEvent('touchmove', 100));
      });

      const indicator = screen.getByTestId('pull-indicator');
      // Indicator should have positive height when pulling
      const heightValue = parseInt(indicator.style.height || '0', 10);
      expect(heightValue).toBeGreaterThan(0);
    });
  });

  describe('refresh spinner', () => {
    it('shows spinner during refresh', async () => {
      let resolveRefresh: () => void;
      const onRefresh = vi.fn().mockImplementation(
        () =>
          new Promise<void>((resolve) => {
            resolveRefresh = resolve;
          })
      );

      render(
        <PullToRefresh onRefresh={onRefresh}>
          <div>Content</div>
        </PullToRefresh>
      );

      const container = screen.getByTestId('pull-to-refresh-container');

      // Trigger refresh
      act(() => {
        container.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        container.dispatchEvent(createTouchEvent('touchmove', 180)); // Past threshold with resistance
      });

      act(() => {
        container.dispatchEvent(createTouchEvent('touchend', 180));
      });

      // Should show spinner while refreshing
      await waitFor(() => {
        expect(screen.getByTestId('refresh-spinner')).toBeInTheDocument();
      });

      // Resolve refresh
      await act(async () => {
        resolveRefresh();
        await Promise.resolve(); // Flush microtasks for async state updates
      });
    });

    it('hides spinner after refresh completes', async () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh}>
          <div>Content</div>
        </PullToRefresh>
      );

      const container = screen.getByTestId('pull-to-refresh-container');

      // Trigger refresh
      act(() => {
        container.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        container.dispatchEvent(createTouchEvent('touchmove', 180));
      });

      await act(async () => {
        container.dispatchEvent(createTouchEvent('touchend', 180));
        await Promise.resolve(); // Flush microtasks for async state updates
      });

      // Wait for refresh to complete and spinner to hide
      await waitFor(() => {
        expect(screen.queryByTestId('refresh-spinner')).not.toBeInTheDocument();
      });
    });
  });

  describe('external isRefreshing', () => {
    it('shows spinner when isRefreshing prop is true', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh} isRefreshing={true}>
          <div>Content</div>
        </PullToRefresh>
      );

      expect(screen.getByTestId('refresh-spinner')).toBeInTheDocument();
    });

    it('hides spinner when isRefreshing prop is false', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh} isRefreshing={false}>
          <div>Content</div>
        </PullToRefresh>
      );

      expect(screen.queryByTestId('refresh-spinner')).not.toBeInTheDocument();
    });
  });

  describe('disabled state', () => {
    it('does not show indicator when disabled', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh} disabled={true}>
          <div>Content</div>
        </PullToRefresh>
      );

      const container = screen.getByTestId('pull-to-refresh-container');

      act(() => {
        container.dispatchEvent(createTouchEvent('touchstart', 0));
      });

      act(() => {
        container.dispatchEvent(createTouchEvent('touchmove', 100));
      });

      const indicator = screen.getByTestId('pull-indicator');
      const heightValue = parseInt(indicator.style.height || '0', 10);
      expect(heightValue).toBe(0);
    });
  });

  describe('accessibility', () => {
    it('has appropriate aria attributes', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh}>
          <div>Content</div>
        </PullToRefresh>
      );

      const container = screen.getByTestId('pull-to-refresh-container');
      expect(container).toHaveAttribute('role', 'region');
      expect(container).toHaveAttribute('aria-label', 'Pull to refresh content');
    });

    it('has live region for refresh status', () => {
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(
        <PullToRefresh onRefresh={onRefresh} isRefreshing={true}>
          <div>Content</div>
        </PullToRefresh>
      );

      // Look for the sr-only live region
      const liveRegion = screen.getByRole('status');
      expect(liveRegion).toBeInTheDocument();
      expect(liveRegion).toHaveTextContent(/refreshing/i);
    });
  });
});
