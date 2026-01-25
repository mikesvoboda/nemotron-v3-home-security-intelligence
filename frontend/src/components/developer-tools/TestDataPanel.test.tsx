/**
 * Tests for TestDataPanel component
 *
 * Tests the main panel for seeding and cleanup operations.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest';

import TestDataPanel from './TestDataPanel';

import type { ReactNode } from 'react';

// Mock toast hook
const mockSuccess = vi.fn();
const mockError = vi.fn();
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: mockSuccess,
    error: mockError,
    warning: vi.fn(),
    info: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn(),
    promise: vi.fn(),
  }),
}));

// MSW server setup
const server = setupServer(
  // Seed cameras
  http.post('/api/admin/seed/cameras', async ({ request }) => {
    const body = (await request.json()) as { count: number };
    return HttpResponse.json({
      cameras: Array.from({ length: body.count }, (_, i) => ({ id: `cam-${i}` })),
      cleared: 0,
      created: body.count,
    });
  }),
  // Seed events
  http.post('/api/admin/seed/events', async ({ request }) => {
    const body = (await request.json()) as { count: number };
    return HttpResponse.json({
      events_cleared: 0,
      events_created: body.count,
      detections_cleared: 0,
      detections_created: body.count * 3,
    });
  }),
  // Seed pipeline latency
  http.post('/api/admin/seed/pipeline-latency', async ({ request }) => {
    const body = (await request.json()) as { time_span_hours?: number };
    return HttpResponse.json({
      message: 'Pipeline latency data seeded successfully',
      samples_per_stage: 100,
      stages_seeded: ['watch_to_detect', 'detect_to_batch', 'batch_to_analyze', 'total_pipeline'],
      time_span_hours: body.time_span_hours ?? 24,
    });
  }),
  // Clear data
  http.delete('/api/admin/seed/clear', async ({ request }) => {
    const body = (await request.json()) as { confirm: string };
    if (body.confirm !== 'DELETE_ALL_DATA') {
      return HttpResponse.json({ detail: 'Invalid confirmation string' }, { status: 400 });
    }
    return HttpResponse.json({
      cameras_cleared: 5,
      events_cleared: 100,
      detections_cleared: 300,
    });
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  server.resetHandlers();
  mockSuccess.mockClear();
  mockError.mockClear();
});

// Test wrapper with QueryClientProvider
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('TestDataPanel', () => {
  it('should render panel title and warning', () => {
    render(<TestDataPanel />, { wrapper: createWrapper() });

    expect(screen.getByText('Test Data')).toBeInTheDocument();
    expect(screen.getByText(/these operations modify database data/i)).toBeInTheDocument();
  });

  it('should render all seed sections', () => {
    render(<TestDataPanel />, { wrapper: createWrapper() });

    expect(screen.getByText('Cameras')).toBeInTheDocument();
    expect(screen.getByText('Events')).toBeInTheDocument();
    expect(screen.getByText('Pipeline Data')).toBeInTheDocument();
  });

  it('should render all cleanup sections', () => {
    render(<TestDataPanel />, { wrapper: createWrapper() });

    // Text appears multiple times (label + button text)
    expect(screen.getAllByText('Delete All Events').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Full Database Reset').length).toBeGreaterThan(0);
  });

  it('should seed cameras when button is clicked', async () => {
    const user = userEvent.setup();
    render(<TestDataPanel />, { wrapper: createWrapper() });

    const button = screen.getByRole('button', { name: /seed cameras/i });
    await user.click(button);

    await waitFor(() => {
      expect(mockSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Created'),
        expect.anything()
      );
    });
  });

  it('should seed events when button is clicked', async () => {
    const user = userEvent.setup();
    render(<TestDataPanel />, { wrapper: createWrapper() });

    const button = screen.getByRole('button', { name: /seed events/i });
    await user.click(button);

    await waitFor(() => {
      expect(mockSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Created'),
        expect.anything()
      );
    });
  });

  it('should seed pipeline data when button is clicked', async () => {
    const user = userEvent.setup();
    render(<TestDataPanel />, { wrapper: createWrapper() });

    const button = screen.getByRole('button', { name: /seed pipeline data/i });
    await user.click(button);

    await waitFor(() => {
      expect(mockSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Pipeline'),
        expect.anything()
      );
    });
  });

  it('should require confirmation for delete all events', async () => {
    const user = userEvent.setup();
    render(<TestDataPanel />, { wrapper: createWrapper() });

    // Click the delete button
    const deleteButton = screen.getByRole('button', { name: /delete all events/i });
    await user.click(deleteButton);

    // Should show confirmation dialog
    await waitFor(() => {
      expect(screen.getByText(/Type "DELETE" to confirm/)).toBeInTheDocument();
    });
  });

  it('should require confirmation for full database reset', async () => {
    const user = userEvent.setup();
    render(<TestDataPanel />, { wrapper: createWrapper() });

    // Find and click the database reset button
    const resetButtons = screen.getAllByRole('button');
    const resetButton = resetButtons.find((btn) =>
      btn.textContent?.includes('Full Database Reset')
    );
    expect(resetButton).toBeTruthy();
    await user.click(resetButton!);

    // Should show confirmation dialog with RESET DATABASE text
    await waitFor(() => {
      expect(screen.getByText(/Type "RESET DATABASE" to confirm/)).toBeInTheDocument();
    });
  });

  it('should show error toast when operation fails', async () => {
    server.use(
      http.post('/api/admin/seed/cameras', () => {
        return HttpResponse.json({ detail: 'Admin access not enabled' }, { status: 403 });
      })
    );

    const user = userEvent.setup();
    render(<TestDataPanel />, { wrapper: createWrapper() });

    const button = screen.getByRole('button', { name: /seed cameras/i });
    await user.click(button);

    await waitFor(() => {
      expect(mockError).toHaveBeenCalled();
    });
  });
});
