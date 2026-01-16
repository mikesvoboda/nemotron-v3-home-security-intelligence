/**
 * Tests for RetryIndicator component (NEM-2297)
 *
 * Tests that the indicator:
 * - Shows when there are active retries
 * - Displays countdown and attempt information
 * - Allows cancellation of retries
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import RetryIndicator, { RetryIndicatorCompact } from './RetryIndicator';
import { type RetryState, useActiveRetries, useRetryStore } from '../hooks/useRetry';

// Mock the useRetry hook
vi.mock('../hooks/useRetry', async () => {
  const actual = await vi.importActual('../hooks/useRetry');
  return {
    ...actual,
    useActiveRetries: vi.fn(() => []),
    useRetryStore: vi.fn(),
  };
});

describe('RetryIndicator', () => {
  const mockCancelRetry = vi.fn();

  beforeEach(() => {
    vi.mocked(useActiveRetries).mockReturnValue([]);
    vi.mocked(useRetryStore).mockImplementation((selector) => {
      if (typeof selector === 'function') {
        return selector({
          retries: new Map(),
          setRetry: vi.fn(),
          removeRetry: vi.fn(),
          cancelRetry: mockCancelRetry,
          updateCountdown: vi.fn(),
          clearAll: vi.fn(),
        });
      }
      return {
        retries: new Map(),
        setRetry: vi.fn(),
        removeRetry: vi.fn(),
        cancelRetry: mockCancelRetry,
        updateCountdown: vi.fn(),
        clearAll: vi.fn(),
      };
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const createRetryState = (overrides: Partial<RetryState> = {}): RetryState => ({
    id: 'test-retry-1',
    attempt: 1,
    maxAttempts: 3,
    secondsRemaining: 10,
    cancelled: false,
    url: '/api/test',
    retryAt: Date.now() + 10000,
    ...overrides,
  });

  describe('visibility', () => {
    it('does not render when there are no active retries', () => {
      vi.mocked(useActiveRetries).mockReturnValue([]);

      render(<RetryIndicator />);

      expect(screen.queryByTestId('retry-indicator')).not.toBeInTheDocument();
    });

    it('renders when there are active retries', () => {
      vi.mocked(useActiveRetries).mockReturnValue([createRetryState()]);

      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-indicator')).toBeInTheDocument();
    });
  });

  describe('content display', () => {
    beforeEach(() => {
      vi.mocked(useActiveRetries).mockReturnValue([
        createRetryState({ secondsRemaining: 10, attempt: 1, maxAttempts: 3 }),
      ]);
    });

    it('displays "Request limit reached" header', () => {
      render(<RetryIndicator />);

      expect(screen.getByText('Request limit reached')).toBeInTheDocument();
    });

    it('displays countdown message', () => {
      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-message')).toBeInTheDocument();
      expect(screen.getByText(/Retrying in/)).toBeInTheDocument();
    });

    it('displays countdown value', () => {
      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-countdown')).toBeInTheDocument();
    });

    it('displays attempt information', () => {
      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-attempt')).toHaveTextContent('Attempt 1 of 3');
    });

    it('shows spinner element', () => {
      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-spinner')).toBeInTheDocument();
    });

    it('has role="status" for accessibility', () => {
      render(<RetryIndicator />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has aria-live="polite" for screen readers', () => {
      render(<RetryIndicator />);

      const indicator = screen.getByTestId('retry-indicator');
      expect(indicator).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('cancel functionality', () => {
    it('shows cancel button for single retry', () => {
      vi.mocked(useActiveRetries).mockReturnValue([createRetryState()]);

      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-cancel-button')).toBeInTheDocument();
    });

    it('calls cancelRetry when cancel button is clicked', () => {
      const retryState = createRetryState({ id: 'test-retry-123' });
      vi.mocked(useActiveRetries).mockReturnValue([retryState]);

      render(<RetryIndicator />);

      fireEvent.click(screen.getByTestId('retry-cancel-button'));

      expect(mockCancelRetry).toHaveBeenCalledWith('test-retry-123');
    });

    it('shows close button (X) for single retry', () => {
      vi.mocked(useActiveRetries).mockReturnValue([createRetryState()]);

      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-cancel-single')).toBeInTheDocument();
    });

    it('calls cancelRetry when X button is clicked', () => {
      const retryState = createRetryState({ id: 'test-retry-456' });
      vi.mocked(useActiveRetries).mockReturnValue([retryState]);

      render(<RetryIndicator />);

      fireEvent.click(screen.getByTestId('retry-cancel-single'));

      expect(mockCancelRetry).toHaveBeenCalledWith('test-retry-456');
    });
  });

  describe('multiple retries', () => {
    it('shows queued count for multiple retries', () => {
      vi.mocked(useActiveRetries).mockReturnValue([
        createRetryState({ id: 'retry-1' }),
        createRetryState({ id: 'retry-2' }),
        createRetryState({ id: 'retry-3' }),
      ]);

      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-multiple')).toHaveTextContent('+2 more requests queued');
    });

    it('shows singular form for 2 retries', () => {
      vi.mocked(useActiveRetries).mockReturnValue([
        createRetryState({ id: 'retry-1' }),
        createRetryState({ id: 'retry-2' }),
      ]);

      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-multiple')).toHaveTextContent('+1 more request queued');
    });

    it('shows "Cancel all retries" button for multiple retries', () => {
      vi.mocked(useActiveRetries).mockReturnValue([
        createRetryState({ id: 'retry-1' }),
        createRetryState({ id: 'retry-2' }),
      ]);

      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-cancel-all')).toBeInTheDocument();
    });

    it('cancels all retries when "Cancel all" is clicked', () => {
      vi.mocked(useActiveRetries).mockReturnValue([
        createRetryState({ id: 'retry-1' }),
        createRetryState({ id: 'retry-2' }),
        createRetryState({ id: 'retry-3' }),
      ]);

      render(<RetryIndicator />);

      fireEvent.click(screen.getByTestId('retry-cancel-all'));

      expect(mockCancelRetry).toHaveBeenCalledWith('retry-1');
      expect(mockCancelRetry).toHaveBeenCalledWith('retry-2');
      expect(mockCancelRetry).toHaveBeenCalledWith('retry-3');
    });

    it('does not show individual cancel button for multiple retries', () => {
      vi.mocked(useActiveRetries).mockReturnValue([
        createRetryState({ id: 'retry-1' }),
        createRetryState({ id: 'retry-2' }),
      ]);

      render(<RetryIndicator />);

      expect(screen.queryByTestId('retry-cancel-button')).not.toBeInTheDocument();
    });
  });

  describe('positioning', () => {
    beforeEach(() => {
      vi.mocked(useActiveRetries).mockReturnValue([createRetryState()]);
    });

    it('defaults to bottom-right position', () => {
      render(<RetryIndicator />);

      const indicator = screen.getByTestId('retry-indicator');
      expect(indicator.className).toContain('bottom-20');
      expect(indicator.className).toContain('right-4');
    });

    it('applies top-left position when specified', () => {
      render(<RetryIndicator position="top-left" />);

      const indicator = screen.getByTestId('retry-indicator');
      expect(indicator.className).toContain('top-4');
      expect(indicator.className).toContain('left-4');
    });

    it('applies top-right position when specified', () => {
      render(<RetryIndicator position="top-right" />);

      const indicator = screen.getByTestId('retry-indicator');
      expect(indicator.className).toContain('top-4');
      expect(indicator.className).toContain('right-4');
    });

    it('applies bottom-left position when specified', () => {
      render(<RetryIndicator position="bottom-left" />);

      const indicator = screen.getByTestId('retry-indicator');
      expect(indicator.className).toContain('bottom-20');
      expect(indicator.className).toContain('left-4');
    });

    it('applies custom className', () => {
      render(<RetryIndicator className="custom-class" />);

      const indicator = screen.getByTestId('retry-indicator');
      expect(indicator.className).toContain('custom-class');
    });
  });

  describe('attempt display', () => {
    it('shows attempt 2 of 3', () => {
      vi.mocked(useActiveRetries).mockReturnValue([
        createRetryState({ attempt: 2, maxAttempts: 3 }),
      ]);

      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-attempt')).toHaveTextContent('Attempt 2 of 3');
    });

    it('shows attempt 3 of 3', () => {
      vi.mocked(useActiveRetries).mockReturnValue([
        createRetryState({ attempt: 3, maxAttempts: 3 }),
      ]);

      render(<RetryIndicator />);

      expect(screen.getByTestId('retry-attempt')).toHaveTextContent('Attempt 3 of 3');
    });
  });
});

describe('RetryIndicatorCompact', () => {
  beforeEach(() => {
    vi.mocked(useActiveRetries).mockReturnValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const createRetryState = (overrides: Partial<RetryState> = {}): RetryState => ({
    id: 'test-retry-1',
    attempt: 1,
    maxAttempts: 3,
    secondsRemaining: 10,
    cancelled: false,
    url: '/api/test',
    retryAt: Date.now() + 10000,
    ...overrides,
  });

  it('does not render when there are no active retries', () => {
    vi.mocked(useActiveRetries).mockReturnValue([]);

    render(<RetryIndicatorCompact />);

    expect(screen.queryByTestId('retry-indicator-compact')).not.toBeInTheDocument();
  });

  it('renders when there are active retries', () => {
    vi.mocked(useActiveRetries).mockReturnValue([createRetryState()]);

    render(<RetryIndicatorCompact />);

    expect(screen.getByTestId('retry-indicator-compact')).toBeInTheDocument();
  });

  it('displays countdown message', () => {
    vi.mocked(useActiveRetries).mockReturnValue([createRetryState({ secondsRemaining: 5 })]);

    render(<RetryIndicatorCompact />);

    expect(screen.getByText(/Retrying in/)).toBeInTheDocument();
  });

  it('has role="status" for accessibility', () => {
    vi.mocked(useActiveRetries).mockReturnValue([createRetryState()]);

    render(<RetryIndicatorCompact />);

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    vi.mocked(useActiveRetries).mockReturnValue([createRetryState()]);

    render(<RetryIndicatorCompact className="custom-compact-class" />);

    const indicator = screen.getByTestId('retry-indicator-compact');
    expect(indicator.className).toContain('custom-compact-class');
  });
});
