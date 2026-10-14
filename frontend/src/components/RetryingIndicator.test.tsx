/**
 * Tests for RetryingIndicator component (NEM-1970)
 *
 * Tests that the indicator shows only when:
 * - The client is rate limited (isLimited = true)
 * - AND there are queries or mutations in flight
 */

import {
  QueryClient,
  QueryClientProvider,
  useIsFetching,
  useIsMutating,
} from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import RetryingIndicator from './RetryingIndicator';
import { useRateLimitStore } from '../stores/rate-limit-store';

// Mock the rate limit store
vi.mock('../stores/rate-limit-store', () => ({
  useRateLimitStore: vi.fn(),
}));

// Mock TanStack Query hooks
vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query');
  return {
    ...actual,
    useIsFetching: vi.fn(() => 0),
    useIsMutating: vi.fn(() => 0),
  };
});

describe('RetryingIndicator', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    // Default: not rate limited, no requests in flight
    vi.mocked(useRateLimitStore).mockReturnValue({
      current: null,
      isLimited: false,
      secondsUntilReset: 0,
      update: vi.fn(),
      clear: vi.fn(),
      _timerId: null,
    });
    vi.mocked(useIsFetching).mockReturnValue(0);
    vi.mocked(useIsMutating).mockReturnValue(0);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <RetryingIndicator />
      </QueryClientProvider>
    );
  };

  describe('visibility conditions', () => {
    it('does not render when not rate limited and no requests in flight', () => {
      renderComponent();
      expect(screen.queryByTestId('retrying-indicator')).not.toBeInTheDocument();
    });

    it('does not render when rate limited but no requests in flight', () => {
      vi.mocked(useRateLimitStore).mockReturnValue({
        current: { limit: 100, remaining: 0, reset: Date.now() / 1000 + 60 },
        isLimited: true,
        secondsUntilReset: 60,
        update: vi.fn(),
        clear: vi.fn(),
        _timerId: null,
      });

      renderComponent();
      expect(screen.queryByTestId('retrying-indicator')).not.toBeInTheDocument();
    });

    it('does not render when not rate limited but queries are in flight', () => {
      vi.mocked(useIsFetching).mockReturnValue(3);

      renderComponent();
      expect(screen.queryByTestId('retrying-indicator')).not.toBeInTheDocument();
    });

    it('does not render when not rate limited but mutations are in flight', () => {
      vi.mocked(useIsMutating).mockReturnValue(1);

      renderComponent();
      expect(screen.queryByTestId('retrying-indicator')).not.toBeInTheDocument();
    });

    it('renders when rate limited AND queries are in flight', () => {
      vi.mocked(useRateLimitStore).mockReturnValue({
        current: { limit: 100, remaining: 0, reset: Date.now() / 1000 + 60 },
        isLimited: true,
        secondsUntilReset: 60,
        update: vi.fn(),
        clear: vi.fn(),
        _timerId: null,
      });
      vi.mocked(useIsFetching).mockReturnValue(2);

      renderComponent();
      expect(screen.getByTestId('retrying-indicator')).toBeInTheDocument();
    });

    it('renders when rate limited AND mutations are in flight', () => {
      vi.mocked(useRateLimitStore).mockReturnValue({
        current: { limit: 100, remaining: 0, reset: Date.now() / 1000 + 60 },
        isLimited: true,
        secondsUntilReset: 60,
        update: vi.fn(),
        clear: vi.fn(),
        _timerId: null,
      });
      vi.mocked(useIsMutating).mockReturnValue(1);

      renderComponent();
      expect(screen.getByTestId('retrying-indicator')).toBeInTheDocument();
    });

    it('renders when rate limited AND both queries and mutations are in flight', () => {
      vi.mocked(useRateLimitStore).mockReturnValue({
        current: { limit: 100, remaining: 0, reset: Date.now() / 1000 + 60 },
        isLimited: true,
        secondsUntilReset: 60,
        update: vi.fn(),
        clear: vi.fn(),
        _timerId: null,
      });
      vi.mocked(useIsFetching).mockReturnValue(1);
      vi.mocked(useIsMutating).mockReturnValue(1);

      renderComponent();
      expect(screen.getByTestId('retrying-indicator')).toBeInTheDocument();
    });
  });

  describe('content and styling', () => {
    beforeEach(() => {
      vi.mocked(useRateLimitStore).mockReturnValue({
        current: { limit: 100, remaining: 0, reset: Date.now() / 1000 + 60 },
        isLimited: true,
        secondsUntilReset: 60,
        update: vi.fn(),
        clear: vi.fn(),
        _timerId: null,
      });
      vi.mocked(useIsFetching).mockReturnValue(1);
    });

    // Owner ruling 132 fixed this string ("the string is the owner's ruling,
    // not derived prose" — ruling 155 item 1) and ruling 155 requires the
    // EXACT text, ellipsis included: U+2026 … , not three full stops. An
    // exact-string assert is deliberate — toMatch(/rate limited/i) would pass
    // on a re-worded pill and the owner's wording is the thing under test.
    it('displays the ruled text "Rate limited, retrying…" exactly', () => {
      renderComponent();
      expect(screen.getByText('Rate limited, retrying…')).toBeInTheDocument();
    });

    // Ruling 132's other half: "shows no count, limit or time". This fixture is
    // what makes the assertion non-vacuous — the store above is fed
    // limit=100 / remaining=0 / reset=now+60 / secondsUntilReset=60, so a pill
    // that rendered any of them would print digits here.
    it('renders no count, limit or time while limited', () => {
      renderComponent();
      const pill = screen.getByTestId('retrying-indicator');
      expect(pill.textContent).not.toMatch(/\d/);
      expect(pill.textContent).toBe('Rate limited, retrying…');
    });

    it('shows a spinner element', () => {
      renderComponent();
      expect(screen.getByTestId('retrying-spinner')).toBeInTheDocument();
    });

    it('has role="status" for accessibility', () => {
      renderComponent();
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has aria-live="polite" for screen readers', () => {
      renderComponent();
      const indicator = screen.getByTestId('retrying-indicator');
      expect(indicator).toHaveAttribute('aria-live', 'polite');
    });

    it('applies custom className when provided', () => {
      render(
        <QueryClientProvider client={queryClient}>
          <RetryingIndicator className="custom-class" />
        </QueryClientProvider>
      );
      const indicator = screen.getByTestId('retrying-indicator');
      expect(indicator.className).toContain('custom-class');
    });
  });
});
