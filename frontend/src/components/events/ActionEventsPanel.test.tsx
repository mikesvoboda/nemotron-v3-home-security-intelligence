/**
 * Tests for ActionEventsPanel component
 *
 * Linear issue: NEM-5024 (Phase 7)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';
import { setupServer } from 'msw/node';
import { type ReactNode } from 'react';
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';

import ActionEventsPanel from './ActionEventsPanel';

import type { ActionEventListResponse } from '../../services/actionEventsApi';

// ============================================================================
// Mock Data
// ============================================================================

const mockActionEventsResponse: ActionEventListResponse = {
  items: [
    {
      id: 1,
      camera_id: 'front_door',
      track_id: 42,
      action: 'walking normally',
      confidence: 0.89,
      is_suspicious: false,
      timestamp: '2026-01-26T12:01:00Z',
      frame_count: 8,
      all_scores: { 'walking normally': 0.89, running: 0.05 },
      created_at: '2026-01-26T12:01:00Z',
    },
    {
      id: 2,
      camera_id: 'front_door',
      track_id: null,
      action: 'climbing',
      confidence: 0.92,
      is_suspicious: true,
      timestamp: '2026-01-26T12:02:00Z',
      frame_count: 8,
      all_scores: { climbing: 0.92, running: 0.04 },
      created_at: '2026-01-26T12:02:00Z',
    },
  ],
  pagination: { total: 2, limit: 50, offset: 0, has_more: false },
};

// ============================================================================
// MSW Server Setup
// ============================================================================

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  server.resetHandlers();
});

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Create a wrapper with QueryClientProvider for testing.
 */
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const defaultProps = {
  eventId: 123,
  cameraId: 'front_door',
  startTime: '2026-01-26T12:00:00Z',
  endTime: '2026-01-26T12:05:00Z',
};

// ============================================================================
// Tests
// ============================================================================

describe('ActionEventsPanel', () => {
  it('shows loading state initially', () => {
    server.use(
      http.get('/api/action-events', async () => {
        await delay(100);
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    expect(screen.getByTestId('action-events-loading')).toBeInTheDocument();
    expect(screen.getByText(/loading action events/i)).toBeInTheDocument();
  });

  it('shows empty state when no action events found', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
        });
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('action-events-empty')).toBeInTheDocument();
    });

    expect(screen.getByText(/no action recognition events/i)).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json({ detail: 'Network error' }, { status: 500 });
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    await waitFor(
      () => {
        expect(screen.getByTestId('action-events-error')).toBeInTheDocument();
      },
      { timeout: 5000 }
    );
  });

  it('renders action events when data is available', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('action-events-panel')).toBeInTheDocument();
    });

    // Check header
    expect(screen.getByText('Action Recognition')).toBeInTheDocument();
    expect(screen.getByText('2 actions')).toBeInTheDocument();

    // Check action items
    expect(screen.getByText('Walking normally')).toBeInTheDocument();
    expect(screen.getByText('Climbing')).toBeInTheDocument();

    // Check confidence badges
    expect(screen.getByText('89%')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();

    // Check suspicious badge
    expect(screen.getByText('Suspicious')).toBeInTheDocument();
    expect(screen.getByText('1 suspicious')).toBeInTheDocument();

    // Check frame count
    const frameCountElements = screen.getAllByText('8 frames analyzed');
    expect(frameCountElements.length).toBe(2);

    // Check track ID
    expect(screen.getByText('Track #42')).toBeInTheDocument();

    // Check footer
    expect(screen.getByText(/x-clip video analysis/i)).toBeInTheDocument();
  });

  it('allows filtering by action type', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('action-events-panel')).toBeInTheDocument();
    });

    // Find and use the filter dropdown
    const filterSelect = screen.getByLabelText('Filter by action type');
    expect(filterSelect).toBeInTheDocument();

    // Filter by suspicious only
    fireEvent.change(filterSelect, { target: { value: 'suspicious' } });

    // Should only show climbing (suspicious)
    expect(screen.getByText('Climbing')).toBeInTheDocument();
    expect(screen.queryByText('Walking normally')).not.toBeInTheDocument();

    // Filter by specific action
    fireEvent.change(filterSelect, { target: { value: 'walking normally' } });

    // Should only show walking normally
    expect(screen.queryByText('Climbing')).not.toBeInTheDocument();
    expect(screen.getByText('Walking normally')).toBeInTheDocument();
  });

  it('allows expanding all_scores details', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json({
          items: [
            {
              id: 1,
              camera_id: 'front_door',
              track_id: null,
              action: 'walking normally',
              confidence: 0.89,
              is_suspicious: false,
              timestamp: '2026-01-26T12:01:00Z',
              frame_count: 8,
              all_scores: {
                'walking normally': 0.89,
                running: 0.05,
                climbing: 0.02,
                loitering: 0.04,
              },
              created_at: '2026-01-26T12:01:00Z',
            },
          ],
          pagination: { total: 1, limit: 50, offset: 0, has_more: false },
        });
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('action-events-panel')).toBeInTheDocument();
    });

    // Find the expand button
    const expandButton = screen.getByText('Show all scores');
    expect(expandButton).toBeInTheDocument();

    // Click to expand
    fireEvent.click(expandButton);

    // Should now show all scores (sorted by confidence)
    await waitFor(() => {
      expect(screen.getByText('Running')).toBeInTheDocument();
    });
    expect(screen.getByText('Loitering')).toBeInTheDocument();
    expect(screen.getByText('5%')).toBeInTheDocument(); // Running score

    // Button text should change
    expect(screen.getByText('Hide all scores')).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(screen.getByText('Hide all scores'));

    // Detailed scores should be hidden
    await waitFor(() => {
      expect(screen.queryByText('Running')).not.toBeInTheDocument();
    });
  });

  it('allows refreshing action events', async () => {
    let requestCount = 0;

    server.use(
      http.get('/api/action-events', () => {
        requestCount++;
        return HttpResponse.json({
          items: [
            {
              id: 1,
              camera_id: 'front_door',
              track_id: null,
              action: 'walking normally',
              confidence: 0.89,
              is_suspicious: false,
              timestamp: '2026-01-26T12:01:00Z',
              frame_count: 8,
              all_scores: null,
              created_at: '2026-01-26T12:01:00Z',
            },
          ],
          pagination: { total: 1, limit: 50, offset: 0, has_more: false },
        });
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('action-events-panel')).toBeInTheDocument();
    });

    // Initial call
    expect(requestCount).toBe(1);

    // Find and click refresh button
    const refreshButton = screen.getByLabelText('Refresh action events');
    fireEvent.click(refreshButton);

    // Should trigger another fetch
    await waitFor(() => {
      expect(requestCount).toBe(2);
    });
  });

  it('does not show filter when only one action type exists', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json({
          items: [
            {
              id: 1,
              camera_id: 'front_door',
              track_id: null,
              action: 'walking normally',
              confidence: 0.89,
              is_suspicious: false,
              timestamp: '2026-01-26T12:01:00Z',
              frame_count: 8,
              all_scores: null,
              created_at: '2026-01-26T12:01:00Z',
            },
          ],
          pagination: { total: 1, limit: 50, offset: 0, has_more: false },
        });
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('action-events-panel')).toBeInTheDocument();
    });

    // Filter dropdown should not be present with only one action type
    expect(screen.queryByLabelText('Filter by action type')).not.toBeInTheDocument();
  });

  it('handles ongoing events with null end time', async () => {
    let requestUrl: string | undefined;

    server.use(
      http.get('/api/action-events', ({ request }) => {
        requestUrl = request.url;
        return HttpResponse.json({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
        });
      })
    );

    render(
      <ActionEventsPanel {...defaultProps} endTime={null} />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByTestId('action-events-empty')).toBeInTheDocument();
    });

    // Verify request was made with a calculated end time
    expect(requestUrl).toBeDefined();
    const url = new URL(requestUrl!);
    expect(url.searchParams.get('end_time')).toBeTruthy();
  });

  it('displays singular "action" text for 1 event', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json({
          items: [
            {
              id: 1,
              camera_id: 'front_door',
              track_id: null,
              action: 'walking normally',
              confidence: 0.89,
              is_suspicious: false,
              timestamp: '2026-01-26T12:01:00Z',
              frame_count: 8,
              all_scores: null,
              created_at: '2026-01-26T12:01:00Z',
            },
          ],
          pagination: { total: 1, limit: 50, offset: 0, has_more: false },
        });
      })
    );

    render(<ActionEventsPanel {...defaultProps} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('1 action')).toBeInTheDocument();
    });
  });

  it('applies custom className', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
        });
      })
    );

    render(
      <ActionEventsPanel {...defaultProps} className="custom-class" />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByTestId('action-events-empty')).toHaveClass('custom-class');
    });
  });
});
