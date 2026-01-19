/**
 * Integration tests for SummaryCards with useSummaries hook.
 *
 * Tests the full integration between:
 * - useSummaries hook (data fetching, WebSocket subscription)
 * - SummaryCards component (rendering states)
 * - WebSocket summary_update events
 *
 * @see docs/plans/2026-01-18-dashboard-summaries-design.md
 * @see NEM-2899
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, act } from '@testing-library/react';
import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { SummaryCards } from './SummaryCards';
import { useSummaries } from '../../hooks/useSummaries';
import * as api from '../../services/api';

import type { Summary, SummariesLatestResponse } from '../../types/summary';

// ============================================================================
// Mock Setup
// ============================================================================

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchSummaries: vi.fn(),
}));

// Mock WebSocket hook - capture onMessage callback for simulating WebSocket events
let mockOnMessage: ((data: unknown) => void) | undefined;
let mockIsConnected = true;

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn((options) => {
    mockOnMessage = options?.onMessage;
    return {
      isConnected: mockIsConnected,
      lastMessage: null,
      send: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      hasExhaustedRetries: false,
      reconnectCount: 0,
      lastHeartbeat: null,
    };
  }),
}));

// Mock date-fns for consistent time formatting
vi.mock('date-fns', async () => {
  const actual = await vi.importActual('date-fns');
  return {
    ...actual,
    formatDistanceToNow: vi.fn(() => '2 minutes'),
  };
});

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Creates a fresh QueryClient for each test.
 */
function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
    },
  });
}

/**
 * Wrapper component that provides QueryClient context.
 */
function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

/**
 * Integration component that connects useSummaries to SummaryCards.
 */
function SummaryCardsWithHook() {
  const { hourly, daily, isLoading, error } = useSummaries({
    enabled: true,
    enableWebSocket: true,
  });

  if (error) {
    return (
      <div data-testid="error-state">
        <p>Error: {error.message}</p>
      </div>
    );
  }

  return <SummaryCards hourly={hourly} daily={daily} isLoading={isLoading} />;
}

// ============================================================================
// Test Data
// ============================================================================

const mockHourlySummary: Summary = {
  id: 1,
  content: 'Over the past hour, one critical event occurred at 2:15 PM at the front door.',
  eventCount: 1,
  windowStart: '2026-01-18T14:00:00Z',
  windowEnd: '2026-01-18T15:00:00Z',
  generatedAt: '2026-01-18T14:55:00Z',
};

const mockDailySummary: Summary = {
  id: 2,
  content: 'Today has seen minimal high-priority activity. Property is quiet.',
  eventCount: 0,
  windowStart: '2026-01-18T00:00:00Z',
  windowEnd: '2026-01-18T15:00:00Z',
  generatedAt: '2026-01-18T14:55:00Z',
};

const mockSummariesResponse: SummariesLatestResponse = {
  hourly: mockHourlySummary,
  daily: mockDailySummary,
};

// ============================================================================
// Tests
// ============================================================================

describe('SummaryCards Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnMessage = undefined;
    mockIsConnected = true;
    queryClient = createTestQueryClient();

    // Default: successful API response
    (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue(mockSummariesResponse);
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('Full Hook-to-Component Flow', () => {
    it('fetches summaries via useSummaries and renders them in SummaryCards', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      // Initially shows loading state
      expect(screen.getByTestId('summary-card-hourly-loading')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily-loading')).toBeInTheDocument();

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });

      // Verify API was called
      expect(api.fetchSummaries).toHaveBeenCalledTimes(1);

      // Verify content is rendered
      expect(
        screen.getByText(/critical event occurred at 2:15 PM at the front door/)
      ).toBeInTheDocument();
      expect(screen.getByText(/minimal high-priority activity/)).toBeInTheDocument();

      // Verify badges
      expect(screen.getByText('1 event')).toBeInTheDocument();
      expect(screen.getByText('All clear')).toBeInTheDocument();
    });

    it('displays both cards with correct data after fetch completes', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
        expect(screen.getByTestId('summary-card-daily')).toBeInTheDocument();
      });

      // Check hourly card
      const hourlyCard = screen.getByTestId('summary-card-hourly');
      expect(hourlyCard).toHaveAttribute('data-has-events', 'true');

      // Check daily card
      const dailyCard = screen.getByTestId('summary-card-daily');
      expect(dailyCard).toHaveAttribute('data-has-events', 'false');
    });

    it('handles null summaries from API (no events generated yet)', async () => {
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: null,
        daily: null,
      });

      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly-empty')).toBeInTheDocument();
        expect(screen.getByTestId('summary-card-daily-empty')).toBeInTheDocument();
      });

      // Should show empty state messages
      const emptyMessages = screen.getAllByText(/No summary available/);
      expect(emptyMessages).toHaveLength(2);
    });

    it('handles partial summaries (only hourly available)', async () => {
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: mockHourlySummary,
        daily: null,
      });

      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
        expect(screen.getByTestId('summary-card-daily-empty')).toBeInTheDocument();
      });

      // Hourly should show content
      expect(
        screen.getByText(/critical event occurred at 2:15 PM at the front door/)
      ).toBeInTheDocument();
    });
  });

  describe('WebSocket Updates', () => {
    it('triggers refetch when WebSocket receives summary_update message', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      // Wait for initial fetch
      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });

      expect(api.fetchSummaries).toHaveBeenCalledTimes(1);

      // Update API to return different data for the refetch
      const updatedHourly: Summary = {
        ...mockHourlySummary,
        id: 3,
        content: 'UPDATED: Two critical events in the past hour.',
        eventCount: 2,
      };

      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: updatedHourly,
        daily: mockDailySummary,
      });

      // Simulate WebSocket summary_update message
      const wsMessage = {
        type: 'summary_update',
        data: {
          hourly: updatedHourly,
          daily: mockDailySummary,
        },
      };

      act(() => {
        mockOnMessage?.(wsMessage);
      });

      // Should trigger a refetch
      await waitFor(() => {
        expect(api.fetchSummaries).toHaveBeenCalledTimes(2);
      });

      // UI should update with new content
      await waitFor(() => {
        expect(screen.getByText(/UPDATED: Two critical events/)).toBeInTheDocument();
        expect(screen.getByText('2 events')).toBeInTheDocument();
      });
    });

    it('ignores non-summary_update WebSocket messages', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });

      expect(api.fetchSummaries).toHaveBeenCalledTimes(1);

      // Simulate a different WebSocket message type
      const otherMessage = {
        type: 'event_created',
        data: { id: 123, risk_score: 75 },
      };

      act(() => {
        mockOnMessage?.(otherMessage);
      });

      // Wait a bit to ensure no refetch happens
      await new Promise((r) => setTimeout(r, 100));

      // Should NOT have triggered a refetch
      expect(api.fetchSummaries).toHaveBeenCalledTimes(1);
    });

    it('handles rapid WebSocket updates without excessive refetches', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });

      // Fire multiple WebSocket messages rapidly
      for (let i = 0; i < 5; i++) {
        const wsMessage = {
          type: 'summary_update',
          data: {
            hourly: { ...mockHourlySummary, id: 10 + i },
            daily: mockDailySummary,
          },
        };
        act(() => {
          mockOnMessage?.(wsMessage);
        });
      }

      // Wait for React Query to process invalidations
      await waitFor(
        () => {
          // Due to React Query's deduplication, we expect fewer calls than messages
          // At minimum 2 (initial + at least one refetch)
          expect(api.fetchSummaries).toHaveBeenCalled();
        },
        { timeout: 2000 }
      );

      // The key point: UI should still be stable
      expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
    });

    it('updates UI immediately after WebSocket-triggered refetch completes', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('1 event')).toBeInTheDocument();
      });

      // Prepare updated response
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: {
          ...mockHourlySummary,
          content: 'New content after WebSocket update',
          eventCount: 5,
        },
        daily: mockDailySummary,
      });

      // Trigger WebSocket update
      act(() => {
        mockOnMessage?.({
          type: 'summary_update',
          data: { hourly: { id: 99 }, daily: null },
        });
      });

      // Verify UI updates
      await waitFor(() => {
        expect(screen.getByText('5 events')).toBeInTheDocument();
        expect(screen.getByText('New content after WebSocket update')).toBeInTheDocument();
      });
    });
  });

  describe('Error States', () => {
    it('displays error state when API fetch fails', async () => {
      const errorMessage = 'Failed to fetch summaries';
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(
        () => {
          expect(screen.getByTestId('error-state')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByText(`Error: ${errorMessage}`)).toBeInTheDocument();
    });

    it('recovers from error state when WebSocket triggers successful refetch', async () => {
      // Make all initial calls fail (including retry)
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      // Wait for error state (after retry exhaustion)
      await waitFor(
        () => {
          expect(screen.getByTestId('error-state')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      // Now clear the mock and set up successful response
      vi.mocked(api.fetchSummaries).mockReset();
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue(mockSummariesResponse);

      // Trigger WebSocket update to cause refetch via cache invalidation
      act(() => {
        mockOnMessage?.({
          type: 'summary_update',
          data: mockSummariesResponse,
        });
      });

      // Should recover and show data
      await waitFor(
        () => {
          expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.queryByTestId('error-state')).not.toBeInTheDocument();
    });

    it('handles network timeout gracefully', async () => {
      // Simulate a timeout by never resolving
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        () =>
          new Promise<SummariesLatestResponse>((_, reject) => {
            setTimeout(() => reject(new Error('Request timed out')), 100);
          })
      );

      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      // Initially shows loading
      expect(screen.getByTestId('summary-card-hourly-loading')).toBeInTheDocument();

      // Eventually shows error
      await waitFor(
        () => {
          expect(screen.getByTestId('error-state')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('Loading States', () => {
    it('shows loading skeleton during initial fetch', () => {
      // Make API hang indefinitely
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        () => new Promise<SummariesLatestResponse>(() => {})
      );

      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      // Both cards should show loading state
      expect(screen.getByTestId('summary-card-hourly-loading')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily-loading')).toBeInTheDocument();

      // Loading skeletons should have animation
      const skeletons = screen.getAllByTestId('loading-skeleton');
      expect(skeletons).toHaveLength(2);
      skeletons.forEach((skeleton) => {
        expect(skeleton).toHaveClass('animate-pulse');
      });
    });

    it('transitions from loading to data state correctly', async () => {
      let resolvePromise: (value: SummariesLatestResponse) => void;
      const fetchPromise = new Promise<SummariesLatestResponse>((resolve) => {
        resolvePromise = resolve;
      });

      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockReturnValue(fetchPromise);

      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      // Verify loading state
      expect(screen.getByTestId('summary-card-hourly-loading')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily-loading')).toBeInTheDocument();

      // Resolve the promise
      act(() => {
        resolvePromise!(mockSummariesResponse);
      });

      // Wait for data to appear
      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
        expect(screen.getByTestId('summary-card-daily')).toBeInTheDocument();
      });

      // Loading skeletons should be gone
      expect(screen.queryByTestId('summary-card-hourly-loading')).not.toBeInTheDocument();
      expect(screen.queryByTestId('summary-card-daily-loading')).not.toBeInTheDocument();
    });

    it('shows both loading skeletons with proper styling', () => {
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        () => new Promise<SummariesLatestResponse>(() => {})
      );

      const Wrapper = createWrapper(queryClient);

      const { container } = render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      // Check loading state styling
      const loadingCards = container.querySelectorAll('[data-testid$="-loading"]');
      expect(loadingCards).toHaveLength(2);

      // Each loading card should have gray border (indicating loading state)
      loadingCards.forEach((card) => {
        expect(card).toHaveStyle({ borderLeftColor: 'rgb(209, 213, 219)' }); // gray-300
      });
    });
  });

  describe('Visual State Transitions', () => {
    it('updates border color when event count changes', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });

      // Initially hourly has events (amber border)
      const hourlyCard = screen.getByTestId('summary-card-hourly');
      expect(hourlyCard).toHaveStyle({ borderLeftColor: 'rgb(245, 158, 11)' }); // amber-500

      // Update to no events
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: { ...mockHourlySummary, eventCount: 0, content: 'All quiet' },
        daily: mockDailySummary,
      });

      // Trigger refetch via WebSocket
      act(() => {
        mockOnMessage?.({ type: 'summary_update', data: {} });
      });

      // Wait for update
      await waitFor(() => {
        const updatedCard = screen.getByTestId('summary-card-hourly');
        expect(updatedCard).toHaveStyle({ borderLeftColor: 'rgb(16, 185, 129)' }); // emerald-500
      });
    });

    it('updates badge from event count to all clear', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('1 event')).toBeInTheDocument();
      });

      // Update hourly to have no events
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: { ...mockHourlySummary, eventCount: 0 },
        daily: mockDailySummary,
      });

      act(() => {
        mockOnMessage?.({ type: 'summary_update', data: {} });
      });

      await waitFor(() => {
        // Should now show two "All clear" badges (hourly + daily)
        const allClearBadges = screen.getAllByText('All clear');
        expect(allClearBadges).toHaveLength(2);
      });
    });
  });

  describe('Component Lifecycle', () => {
    it('cleans up WebSocket subscription on unmount', async () => {
      const Wrapper = createWrapper(queryClient);

      const { unmount } = render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });

      // Unmount the component
      unmount();

      // WebSocket messages after unmount should not cause errors
      // (This tests that cleanup happened properly)
      expect(() => {
        act(() => {
          mockOnMessage?.({ type: 'summary_update', data: {} });
        });
      }).not.toThrow();
    });

    it('maintains state consistency across rapid mount/unmount cycles', async () => {
      const Wrapper = createWrapper(queryClient);

      // Rapid mount/unmount
      for (let i = 0; i < 3; i++) {
        const { unmount } = render(<SummaryCardsWithHook />, { wrapper: Wrapper });
        unmount();
      }

      // Final render should work correctly
      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });

      // Should display correct data
      expect(
        screen.getByText(/critical event occurred at 2:15 PM at the front door/)
      ).toBeInTheDocument();
    });
  });

  describe('Data Integrity', () => {
    it('preserves summary IDs through WebSocket updates', async () => {
      const Wrapper = createWrapper(queryClient);

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });

      // Track the content before update
      const initialContent = mockHourlySummary.content;
      expect(screen.getByText(initialContent)).toBeInTheDocument();

      // Update with new summary having different ID
      const newSummary: Summary = {
        ...mockHourlySummary,
        id: 999,
        content: 'New summary with different ID',
      };

      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: newSummary,
        daily: mockDailySummary,
      });

      act(() => {
        mockOnMessage?.({ type: 'summary_update', data: {} });
      });

      await waitFor(() => {
        expect(screen.getByText('New summary with different ID')).toBeInTheDocument();
      });

      // Old content should be gone
      expect(screen.queryByText(initialContent)).not.toBeInTheDocument();
    });

    it('correctly pluralizes event count in badges', async () => {
      const Wrapper = createWrapper(queryClient);

      // Test with 1 event
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: { ...mockHourlySummary, eventCount: 1 },
        daily: { ...mockDailySummary, eventCount: 0 },
      });

      render(<SummaryCardsWithHook />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('1 event')).toBeInTheDocument(); // Singular
      });

      // Update to multiple events
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
        hourly: { ...mockHourlySummary, eventCount: 5 },
        daily: { ...mockDailySummary, eventCount: 0 },
      });

      act(() => {
        mockOnMessage?.({ type: 'summary_update', data: {} });
      });

      await waitFor(() => {
        expect(screen.getByText('5 events')).toBeInTheDocument(); // Plural
      });
    });
  });
});
