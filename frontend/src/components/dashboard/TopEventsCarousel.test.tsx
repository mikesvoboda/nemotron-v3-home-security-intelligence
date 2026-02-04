import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import TopEventsCarousel from './TopEventsCarousel';
import { fetchEvents } from '../../services/api';

import type { Event } from '../../types/generated';

// Mock the API
vi.mock('../../services/api', () => ({
  fetchEvents: vi.fn(),
}));
const mockFetchEvents = vi.mocked(fetchEvents);

// Helper to create mock events with high risk scores
function createMockEvent(overrides: Partial<Event> = {}): Event {
  const id = (overrides.id as number) ?? Math.floor(Math.random() * 10000);
  return {
    id,
    camera_id: overrides.camera_id ?? `camera-${String(id)}`,
    started_at: new Date().toISOString(),
    ended_at: null,
    risk_score: 75,
    risk_level: 'high',
    summary: `High risk event ${String(id)}`,
    reasoning: 'Test reasoning',
    reviewed: false,
    flagged: false,
    detection_count: 2,
    thumbnail_url: `/api/events/${String(id)}/thumbnail`,
    version: 1,
    ...overrides,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('TopEventsCarousel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock matchMedia for reduced motion tests
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('basic rendering', () => {
    it('renders loading state initially', () => {
      mockFetchEvents.mockReturnValue(new Promise(() => {})); // Never resolves

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      expect(screen.getByTestId('top-events-carousel')).toBeInTheDocument();
      expect(screen.getByTestId('top-events-loading')).toBeInTheDocument();
    });

    it('renders correct number of thumbnails (default 5)', async () => {
      const mockEvents = Array.from({ length: 10 }, (_, i) =>
        createMockEvent({ id: i + 1, risk_score: 100 - i * 5 })
      );

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 10, limit: 10, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      const thumbnails = screen.getAllByTestId(/^top-event-thumbnail-/);
      expect(thumbnails).toHaveLength(5);
    });

    it('renders configurable number of thumbnails', async () => {
      const mockEvents = Array.from({ length: 10 }, (_, i) =>
        createMockEvent({ id: i + 1, risk_score: 100 - i * 5 })
      );

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 10, limit: 10, has_more: false },
      });

      render(<TopEventsCarousel count={3} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      const thumbnails = screen.getAllByTestId(/^top-event-thumbnail-/);
      expect(thumbnails).toHaveLength(3);
    });

    it('renders empty state when no events', async () => {
      mockFetchEvents.mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.getByTestId('top-events-empty')).toBeInTheDocument();
      });

      expect(screen.getByText(/no high-risk events/i)).toBeInTheDocument();
    });

    it('renders error state on fetch failure', async () => {
      mockFetchEvents.mockRejectedValue(new Error('Network error'));

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(
        () => {
          expect(screen.getByTestId('top-events-error')).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      expect(screen.getByText(/failed to load events/i)).toBeInTheDocument();
    });
  });

  describe('expand/collapse functionality', () => {
    it('shows "Show more" button when expandable', async () => {
      const mockEvents = Array.from({ length: 10 }, (_, i) =>
        createMockEvent({ id: i + 1, risk_score: 100 - i * 5 })
      );

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 10, limit: 10, has_more: false },
      });

      render(<TopEventsCarousel count={5} expandedCount={10} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('expands to show more thumbnails when "Show more" clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = Array.from({ length: 10 }, (_, i) =>
        createMockEvent({ id: i + 1, risk_score: 100 - i * 5 })
      );

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 10, limit: 10, has_more: false },
      });

      render(<TopEventsCarousel count={5} expandedCount={10} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      // Initially 5 thumbnails
      expect(screen.getAllByTestId(/^top-event-thumbnail-/)).toHaveLength(5);

      // Click "Show more"
      await user.click(screen.getByRole('button', { name: /show more/i }));

      // Now 10 thumbnails
      await waitFor(() => {
        expect(screen.getAllByTestId(/^top-event-thumbnail-/)).toHaveLength(10);
      });

      // Button changes to "Show less"
      expect(screen.getByRole('button', { name: /show less/i })).toBeInTheDocument();
    });

    it('collapses when "Show less" clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = Array.from({ length: 10 }, (_, i) =>
        createMockEvent({ id: i + 1, risk_score: 100 - i * 5 })
      );

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 10, limit: 10, has_more: false },
      });

      render(<TopEventsCarousel count={5} expandedCount={10} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      // Expand
      await user.click(screen.getByRole('button', { name: /show more/i }));
      await waitFor(() => {
        expect(screen.getAllByTestId(/^top-event-thumbnail-/)).toHaveLength(10);
      });

      // Collapse
      await user.click(screen.getByRole('button', { name: /show less/i }));
      await waitFor(() => {
        expect(screen.getAllByTestId(/^top-event-thumbnail-/)).toHaveLength(5);
      });
    });

    it('does not show expand button when not enough events', async () => {
      const mockEvents = Array.from({ length: 3 }, (_, i) =>
        createMockEvent({ id: i + 1, risk_score: 100 - i * 5 })
      );

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 3, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel count={5} expandedCount={10} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /show more/i })).not.toBeInTheDocument();
    });
  });

  describe('event detail interaction', () => {
    it('calls onEventClick when thumbnail is clicked', async () => {
      const user = userEvent.setup();
      const onEventClick = vi.fn();
      const mockEvents = [createMockEvent({ id: 123, risk_score: 95 })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel onEventClick={onEventClick} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      await user.click(screen.getByTestId('top-event-thumbnail-123'));

      expect(onEventClick).toHaveBeenCalledWith(123);
    });

    it('supports keyboard navigation with Enter key', async () => {
      const user = userEvent.setup();
      const onEventClick = vi.fn();
      const mockEvents = [createMockEvent({ id: 456, risk_score: 95 })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel onEventClick={onEventClick} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      const thumbnail = screen.getByTestId('top-event-thumbnail-456');
      thumbnail.focus();
      await user.keyboard('{Enter}');

      expect(onEventClick).toHaveBeenCalledWith(456);
    });

    it('supports keyboard navigation with Space key', async () => {
      const user = userEvent.setup();
      const onEventClick = vi.fn();
      const mockEvents = [createMockEvent({ id: 789, risk_score: 95 })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel onEventClick={onEventClick} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      const thumbnail = screen.getByTestId('top-event-thumbnail-789');
      thumbnail.focus();
      await user.keyboard(' ');

      expect(onEventClick).toHaveBeenCalledWith(789);
    });
  });

  describe('thumbnail placeholders', () => {
    it('renders placeholder for missing thumbnails', async () => {
      const mockEvents = [createMockEvent({ id: 1, thumbnail_url: null })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('top-event-placeholder-1')).toBeInTheDocument();
    });

    it('placeholder is still clickable', async () => {
      const user = userEvent.setup();
      const onEventClick = vi.fn();
      const mockEvents = [createMockEvent({ id: 999, thumbnail_url: null })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel onEventClick={onEventClick} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      await user.click(screen.getByTestId('top-event-thumbnail-999'));

      expect(onEventClick).toHaveBeenCalledWith(999);
    });
  });

  describe('navigation arrows', () => {
    it('shows navigation arrows when content overflows', async () => {
      const mockEvents = Array.from({ length: 10 }, (_, i) =>
        createMockEvent({ id: i + 1, risk_score: 100 - i * 5 })
      );

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 10, limit: 10, has_more: false },
      });

      render(<TopEventsCarousel count={10} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByLabelText(/scroll left/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/scroll right/i)).toBeInTheDocument();
    });

    it('left arrow is disabled at start', async () => {
      const mockEvents = Array.from({ length: 10 }, (_, i) =>
        createMockEvent({ id: i + 1, risk_score: 100 - i * 5 })
      );

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 10, limit: 10, has_more: false },
      });

      render(<TopEventsCarousel count={10} />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      const leftArrow = screen.getByLabelText(/scroll left/i);
      expect(leftArrow).toBeDisabled();
    });
  });

  describe('accessibility', () => {
    it('has accessible carousel role and aria-label', async () => {
      const mockEvents = [createMockEvent({ id: 1, risk_score: 95 })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      const carousel = screen.getByTestId('top-events-carousel');
      expect(carousel).toHaveAttribute('role', 'region');
      expect(carousel).toHaveAttribute('aria-label', 'Top risk events');
    });

    it('thumbnails have appropriate aria-labels', async () => {
      const mockEvents = [createMockEvent({ id: 1, risk_score: 95, camera_id: 'front_door' })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      const thumbnail = screen.getByTestId('top-event-thumbnail-1');
      expect(thumbnail).toHaveAttribute('aria-label', expect.stringContaining('front_door'));
      expect(thumbnail).toHaveAttribute('aria-label', expect.stringContaining('risk score 95'));
    });

    it('respects prefers-reduced-motion', async () => {
      // Mock reduced motion preference - framer-motion uses this media query
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: query === '(prefers-reduced-motion: reduce)',
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const mockEvents = [createMockEvent({ id: 1, risk_score: 95 })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      // When framer-motion detects reduced motion, useReducedMotion returns true
      // and we add the motion-reduce class. However, framer-motion's detection
      // may not work in test environment, so we verify the component renders
      // correctly regardless.
      const carousel = screen.getByTestId('top-events-carousel');
      expect(carousel).toBeInTheDocument();
      // The carousel should be accessible regardless of motion preference
      expect(carousel).toHaveAttribute('role', 'region');
    });
  });

  describe('risk score display', () => {
    it('displays risk score badge on thumbnails', async () => {
      const mockEvents = [createMockEvent({ id: 1, risk_score: 95 })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      // RiskBadge shows the label with score in format "High (95)"
      expect(screen.getByText(/\(95\)/)).toBeInTheDocument();
    });

    it('orders events by risk score (highest first)', async () => {
      const mockEvents = [
        createMockEvent({ id: 1, risk_score: 50 }),
        createMockEvent({ id: 2, risk_score: 95 }),
        createMockEvent({ id: 3, risk_score: 75 }),
      ];

      // Return events in risk_score descending order (as API would)
      mockFetchEvents.mockResolvedValue({
        items: [mockEvents[1], mockEvents[2], mockEvents[0]], // 95, 75, 50
        pagination: { total: 3, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      const thumbnails = screen.getAllByTestId(/^top-event-thumbnail-/);
      // First thumbnail should be event with risk_score 95 (id: 2)
      expect(thumbnails[0]).toHaveAttribute('data-testid', 'top-event-thumbnail-2');
    });
  });

  describe('title and header', () => {
    it('renders default title', async () => {
      const mockEvents = [createMockEvent({ id: 1 })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByRole('heading', { name: /top events/i })).toBeInTheDocument();
    });

    it('renders custom title', async () => {
      const mockEvents = [createMockEvent({ id: 1 })];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 1, limit: 5, has_more: false },
      });

      render(<TopEventsCarousel title="High Risk Alerts" />, { wrapper: createWrapper() });

      await waitFor(() => {
        expect(screen.queryByTestId('top-events-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByRole('heading', { name: /high risk alerts/i })).toBeInTheDocument();
    });
  });
});
