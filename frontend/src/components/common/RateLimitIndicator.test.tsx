import { render, screen, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import RateLimitIndicator from './RateLimitIndicator';
import { useRateLimitStore } from '../../stores/rate-limit-store';

// Mock sonner toast using vi.hoisted to avoid hoisting issues
const { mockToastWarning } = vi.hoisted(() => ({
  mockToastWarning: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    warning: mockToastWarning,
  },
}));

describe('RateLimitIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Reset store state before each test
    useRateLimitStore.getState().clear();
    mockToastWarning.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    useRateLimitStore.getState().clear();
  });

  describe('rendering', () => {
    it('renders nothing when no rate limit info is available', () => {
      const { container } = render(<RateLimitIndicator />);
      expect(container).toBeEmptyDOMElement();
    });

    it('renders nothing when quota is above 50%', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 60,
          reset: now + 60,
        });
      });

      const { container } = render(<RateLimitIndicator />);
      expect(container).toBeEmptyDOMElement();
    });

    it('renders the indicator when quota is below 50%', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 40,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      expect(screen.getByTestId('rate-limit-indicator')).toBeInTheDocument();
    });

    it('renders with rate limited state when remaining is 0', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      expect(screen.getByText('Rate Limited')).toBeInTheDocument();
    });
  });

  describe('progress bar display', () => {
    it('displays remaining and total quota', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 30,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      expect(screen.getByText('30/100')).toBeInTheDocument();
    });

    it('renders a progress bar with correct percentage', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 40,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      const progressBar = screen.getByTestId('rate-limit-progress');
      expect(progressBar).toHaveStyle({ width: '40%' });
    });

    it('shows yellow styling when quota is between 20% and 50%', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 30,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      const progressContainer = screen.getByTestId('rate-limit-progress-container');
      expect(progressContainer).toHaveClass('bg-yellow-200');
    });

    it('shows red styling when quota is below 20%', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 15,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      const progressContainer = screen.getByTestId('rate-limit-progress-container');
      expect(progressContainer).toHaveClass('bg-red-200');
    });
  });

  describe('rate limited state', () => {
    it('displays rate limited message', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 90,
        });
      });

      render(<RateLimitIndicator />);
      expect(screen.getByText('Rate Limited')).toBeInTheDocument();
    });

    it('displays countdown timer', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 90,
        });
      });

      render(<RateLimitIndicator />);
      expect(screen.getByText(/Retry in 1:30/)).toBeInTheDocument();
    });

    it('displays warning icon', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      expect(screen.getByTestId('rate-limit-icon')).toBeInTheDocument();
    });

    it('uses red styling when rate limited', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      const indicator = screen.getByTestId('rate-limit-indicator');
      expect(indicator).toHaveClass('border-red-300');
      expect(indicator).toHaveClass('bg-red-100');
    });
  });

  describe('accessibility', () => {
    it('has role="status"', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 30,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      const indicator = screen.getByTestId('rate-limit-indicator');
      expect(indicator).toHaveAttribute('role', 'status');
    });

    it('has aria-live="polite"', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 30,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      const indicator = screen.getByTestId('rate-limit-indicator');
      expect(indicator).toHaveAttribute('aria-live', 'polite');
    });

    it('has descriptive aria-label for low quota', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 30,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      const indicator = screen.getByTestId('rate-limit-indicator');
      expect(indicator).toHaveAttribute(
        'aria-label',
        'API quota low: 30 of 100 requests remaining'
      );
    });

    it('has descriptive aria-label when rate limited', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 90,
        });
      });

      render(<RateLimitIndicator />);
      const indicator = screen.getByTestId('rate-limit-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Rate limited. Retry in 1:30');
    });

    it('progress bar has correct ARIA attributes', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 40,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      const progressBar = screen.getByTestId('rate-limit-progress');
      expect(progressBar).toHaveAttribute('role', 'progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '40');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 30,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator className="custom-class" />);
      const indicator = screen.getByTestId('rate-limit-indicator');
      expect(indicator).toHaveClass('custom-class');
    });
  });

  describe('countdown updates', () => {
    it('updates countdown every second', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now + 65,
        });
      });

      render(<RateLimitIndicator />);
      expect(screen.getByText(/Retry in 1:05/)).toBeInTheDocument();

      // Advance time by 5 seconds
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(screen.getByText(/Retry in 1:00/)).toBeInTheDocument();
    });
  });

  describe('toast notifications', () => {
    it('shows warning toast when quota drops below 20%', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 15,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);

      expect(mockToastWarning).toHaveBeenCalledWith(
        'API quota running low',
        expect.objectContaining({
          description: expect.stringContaining('15'),
        })
      );
    });

    it('shows warning toast only once for the same low quota state', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 15,
          reset: now + 60,
        });
      });

      const { rerender } = render(<RateLimitIndicator />);
      rerender(<RateLimitIndicator />);
      rerender(<RateLimitIndicator />);

      // Should only be called once despite multiple rerenders
      expect(mockToastWarning).toHaveBeenCalledTimes(1);
    });

    it('does not show toast when quota is above 20%', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 25,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      expect(mockToastWarning).not.toHaveBeenCalled();
    });

    it('shows new toast when quota drops below 20% after recovering', () => {
      const now = Math.floor(Date.now() / 1000);

      // First drop below 20%
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 15,
          reset: now + 60,
        });
      });

      const { rerender } = render(<RateLimitIndicator />);
      expect(mockToastWarning).toHaveBeenCalledTimes(1);

      // Recover above 20%
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 80,
          reset: now + 120,
        });
      });

      rerender(<RateLimitIndicator />);

      // Drop below 20% again
      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 10,
          reset: now + 180,
        });
      });

      rerender(<RateLimitIndicator />);
      expect(mockToastWarning).toHaveBeenCalledTimes(2);
    });
  });

  describe('edge cases', () => {
    it('handles limit of 0 gracefully', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 0,
          remaining: 0,
          reset: now + 60,
        });
      });

      const { container } = render(<RateLimitIndicator />);
      // Should render rate limited state even with limit 0
      expect(screen.getByText('Rate Limited')).toBeInTheDocument();
      expect(container).not.toBeEmptyDOMElement();
    });

    it('handles boundary at exactly 20%', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 20,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      // At exactly 20%, should show yellow (not red)
      const progressContainer = screen.getByTestId('rate-limit-progress-container');
      expect(progressContainer).toHaveClass('bg-yellow-200');
    });

    it('handles boundary at exactly 50%', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 50,
          reset: now + 60,
        });
      });

      render(<RateLimitIndicator />);
      // At exactly 50%, should show the indicator
      expect(screen.getByTestId('rate-limit-indicator')).toBeInTheDocument();
    });

    it('handles reset time in the past', () => {
      const now = Math.floor(Date.now() / 1000);

      act(() => {
        useRateLimitStore.getState().update({
          limit: 100,
          remaining: 0,
          reset: now - 10,
        });
      });

      render(<RateLimitIndicator />);
      expect(screen.getByText(/Retry in 0:00/)).toBeInTheDocument();
    });
  });
});
