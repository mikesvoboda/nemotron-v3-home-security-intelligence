/**
 * Tests for TrashPage component
 *
 * Following TDD approach: RED -> GREEN -> REFACTOR
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import TrashPage from './TrashPage';
import * as api from '../services/api';

import type { DeletedEvent } from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchDeletedEvents: vi.fn(),
  restoreEvent: vi.fn(),
  permanentlyDeleteEvent: vi.fn(),
}));

// Helper to create a test QueryClient
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// Factory for creating mock deleted events
function createMockDeletedEvent(overrides: Partial<DeletedEvent> = {}): DeletedEvent {
  return {
    id: 1,
    camera_id: 'front_door',
    started_at: '2025-01-01T10:00:00Z',
    ended_at: '2025-01-01T10:05:00Z',
    risk_score: 45,
    risk_level: 'medium',
    summary: 'Person detected at front door',
    reasoning: 'A person was observed approaching the front door',
    thumbnail_url: '/api/media/events/1/thumbnail.jpg',
    reviewed: false,
    detection_count: 3,
    deleted_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    ...overrides,
  };
}

describe('TrashPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows loading state initially', () => {
    // Mock a pending promise
    vi.mocked(api.fetchDeletedEvents).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    // LoadingSpinner component shows "Loading..." text
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('shows empty state when trash is empty', async () => {
    vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
      events: [],
      total: 0,
    });

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Trash is empty')).toBeInTheDocument();
    });

    expect(screen.getByText(/deleted events will appear here/i)).toBeInTheDocument();
  });

  it('displays deleted events when available', async () => {
    const mockEvents = [
      createMockDeletedEvent({ id: 1, camera_id: 'front_door' }),
      createMockDeletedEvent({ id: 2, camera_id: 'back_door' }),
    ];

    vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
      events: mockEvents,
      total: 2,
    });

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('front_door')).toBeInTheDocument();
    });

    expect(screen.getByText('back_door')).toBeInTheDocument();
    expect(screen.getByText('2 events in trash')).toBeInTheDocument();
  });

  it('displays page header', async () => {
    vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
      events: [createMockDeletedEvent()],
      total: 1,
    });

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'Trash' })).toBeInTheDocument();
    });

    expect(screen.getByText(/review and manage deleted events/i)).toBeInTheDocument();
  });

  it('displays 30-day auto-deletion notice', async () => {
    vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
      events: [createMockDeletedEvent()],
      total: 1,
    });

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Automatic cleanup')).toBeInTheDocument();
    });

    expect(screen.getByText(/30 days/i)).toBeInTheDocument();
  });

  it('handles error state', async () => {
    // Mock all calls to reject - retry is set to 1 in the hook
    vi.mocked(api.fetchDeletedEvents).mockRejectedValue(new Error('Network error'));

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    // Wait for error state - may take time due to retry
    await waitFor(
      () => {
        expect(screen.getByText(/failed to load deleted events/i)).toBeInTheDocument();
      },
      { timeout: 5000 }
    );

    expect(screen.getByText('Network error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('can retry after error', async () => {
    const user = userEvent.setup();

    // First two calls fail (initial + retry), then succeed
    vi.mocked(api.fetchDeletedEvents)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        events: [createMockDeletedEvent()],
        total: 1,
      });

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    // Wait for error state
    await waitFor(
      () => {
        expect(screen.getByText(/failed to load deleted events/i)).toBeInTheDocument();
      },
      { timeout: 5000 }
    );

    // Click retry
    const retryButton = screen.getByRole('button', { name: /try again/i });
    await user.click(retryButton);

    // Should load events
    await waitFor(
      () => {
        expect(screen.getByText('front_door')).toBeInTheDocument();
      },
      { timeout: 5000 }
    );
  });

  it('restores an event when restore is clicked', async () => {
    const user = userEvent.setup();
    const mockEvent = createMockDeletedEvent();

    vi.mocked(api.fetchDeletedEvents).mockResolvedValue({
      events: [mockEvent],
      total: 1,
    });

    vi.mocked(api.restoreEvent).mockResolvedValueOnce({
      ...mockEvent,
      deleted_at: undefined as unknown as string, // Type workaround for restored event
    } as unknown as api.Event);

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('front_door')).toBeInTheDocument();
    });

    // Click restore
    const restoreButton = screen.getByRole('button', { name: /restore/i });
    await user.click(restoreButton);

    await waitFor(() => {
      expect(api.restoreEvent).toHaveBeenCalledWith(1);
    });
  });

  it('permanently deletes an event when confirmed', async () => {
    const user = userEvent.setup();
    const mockEvent = createMockDeletedEvent();

    vi.mocked(api.fetchDeletedEvents).mockResolvedValue({
      events: [mockEvent],
      total: 1,
    });

    vi.mocked(api.permanentlyDeleteEvent).mockResolvedValueOnce(undefined);

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('front_door')).toBeInTheDocument();
    });

    // Click delete forever button
    const deleteButton = screen.getByRole('button', { name: /delete forever/i });
    await user.click(deleteButton);

    // Confirm in dialog - find the button inside the dialog
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Find the dialog and get the danger button inside it
    const dialog = screen.getByRole('dialog');
    const confirmButton = dialog.querySelector('button.btn-danger');
    expect(confirmButton).not.toBeNull();
    await user.click(confirmButton!);

    await waitFor(() => {
      expect(api.permanentlyDeleteEvent).toHaveBeenCalledWith(1);
    });
  });

  it('displays correct event count text for single event', async () => {
    vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
      events: [createMockDeletedEvent()],
      total: 1,
    });

    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <TrashPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('1 event in trash')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Bulk Selection Tests
  // ============================================================================

  describe('Bulk Selection', () => {
    it('shows checkboxes on each trash item', async () => {
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      expect(screen.getByTestId('select-event-2')).toBeInTheDocument();
    });

    it('toggles selection when checkbox is clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      const checkbox1 = screen.getByTestId('select-event-1');
      expect((checkbox1 as HTMLInputElement).checked).toBe(false);

      await user.click(checkbox1);

      expect((checkbox1 as HTMLInputElement).checked).toBe(true);
    });

    it('shows bulk action bar when items are selected', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      // Bulk action bar should not be visible initially
      expect(screen.queryByTestId('bulk-action-bar')).not.toBeInTheDocument();

      // Select an item
      const checkbox1 = screen.getByTestId('select-event-1');
      await user.click(checkbox1);

      // Bulk action bar should now be visible
      expect(screen.getByTestId('bulk-action-bar')).toBeInTheDocument();
      expect(screen.getByText('1 event selected')).toBeInTheDocument();
    });

    it('shows correct count when multiple items are selected', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      // Select both items
      await user.click(screen.getByTestId('select-event-1'));
      await user.click(screen.getByTestId('select-event-2'));

      expect(screen.getByText('2 events selected')).toBeInTheDocument();
    });

    it('clears selection when Clear button is clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      // Select an item
      await user.click(screen.getByTestId('select-event-1'));
      expect(screen.getByTestId('bulk-action-bar')).toBeInTheDocument();

      // Click clear
      await user.click(screen.getByTestId('clear-selection-button'));

      // Bulk action bar should be hidden
      expect(screen.queryByTestId('bulk-action-bar')).not.toBeInTheDocument();
    });

    it('selects all items when Select All is clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-all-button')).toBeInTheDocument();
      });

      // Click Select All
      await user.click(screen.getByTestId('select-all-button'));

      // Both checkboxes should be checked
      const checkbox1 = screen.getByTestId('select-event-1');
      const checkbox2 = screen.getByTestId('select-event-2');

      expect((checkbox1 as HTMLInputElement).checked).toBe(true);
      expect((checkbox2 as HTMLInputElement).checked).toBe(true);
      expect(screen.getByText('2 events selected')).toBeInTheDocument();
    });

    it('deselects all when Deselect All is clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-all-button')).toBeInTheDocument();
      });

      // Select all first
      await user.click(screen.getByTestId('select-all-button'));

      // Button text should change to "Deselect All"
      expect(screen.getByTestId('select-all-button')).toHaveTextContent('Deselect All');

      // Click Deselect All
      await user.click(screen.getByTestId('select-all-button'));

      // Checkboxes should be unchecked
      const checkbox1 = screen.getByTestId('select-event-1');
      const checkbox2 = screen.getByTestId('select-event-2');

      expect((checkbox1 as HTMLInputElement).checked).toBe(false);
      expect((checkbox2 as HTMLInputElement).checked).toBe(false);
    });
  });

  // ============================================================================
  // Bulk Restore Tests
  // ============================================================================

  describe('Bulk Restore', () => {
    it('restores selected items when Restore Selected is clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValue({
        events: mockEvents,
        total: 2,
      });

      vi.mocked(api.restoreEvent).mockResolvedValue({} as api.Event);

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      // Select both items
      await user.click(screen.getByTestId('select-event-1'));
      await user.click(screen.getByTestId('select-event-2'));

      // Click Restore Selected
      await user.click(screen.getByTestId('restore-selected-button'));

      // Both items should be restored
      await waitFor(() => {
        expect(api.restoreEvent).toHaveBeenCalledWith(1);
        expect(api.restoreEvent).toHaveBeenCalledWith(2);
      });
    });
  });

  // ============================================================================
  // Bulk Delete Tests
  // ============================================================================

  describe('Bulk Delete', () => {
    it('shows confirmation modal when Delete Selected is clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      // Select both items
      await user.click(screen.getByTestId('select-event-1'));
      await user.click(screen.getByTestId('select-event-2'));

      // Click Delete Selected
      await user.click(screen.getByTestId('delete-selected-button'));

      // Confirmation modal should appear
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByText(/Permanently Delete 2 Events\?/i)).toBeInTheDocument();
    });

    it('deletes selected items when confirmed', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValue({
        events: mockEvents,
        total: 2,
      });

      vi.mocked(api.permanentlyDeleteEvent).mockResolvedValue(undefined);

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      // Select both items
      await user.click(screen.getByTestId('select-event-1'));
      await user.click(screen.getByTestId('select-event-2'));

      // Click Delete Selected
      await user.click(screen.getByTestId('delete-selected-button'));

      // Wait for modal
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Confirm deletion
      const dialog = screen.getByRole('dialog');
      const confirmButton = within(dialog).getByRole('button', { name: /delete forever/i });
      await user.click(confirmButton);

      // Both items should be deleted
      await waitFor(() => {
        expect(api.permanentlyDeleteEvent).toHaveBeenCalledWith(1);
        expect(api.permanentlyDeleteEvent).toHaveBeenCalledWith(2);
      });
    });

    it('closes modal when Cancel is clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 1,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('select-event-1')).toBeInTheDocument();
      });

      // Select item
      await user.click(screen.getByTestId('select-event-1'));

      // Click Delete Selected
      await user.click(screen.getByTestId('delete-selected-button'));

      // Wait for modal
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Click Cancel
      const dialog = screen.getByRole('dialog');
      const cancelButton = within(dialog).getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      // Modal should be closed - dialog should be gone
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  // ============================================================================
  // Empty Trash Tests
  // ============================================================================

  describe('Empty Trash', () => {
    it('shows Empty Trash button in header', async () => {
      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: [createMockDeletedEvent()],
        total: 1,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('empty-trash-button')).toBeInTheDocument();
      });
    });

    it('shows confirmation modal when Empty Trash is clicked', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: mockEvents,
        total: 2,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('empty-trash-button')).toBeInTheDocument();
      });

      // Click Empty Trash
      await user.click(screen.getByTestId('empty-trash-button'));

      // Confirmation modal should appear
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByText(/Empty Trash\? \(2 events\)/i)).toBeInTheDocument();
    });

    it('deletes all items when Empty Trash is confirmed', async () => {
      const user = userEvent.setup();
      const mockEvents = [createMockDeletedEvent({ id: 1 }), createMockDeletedEvent({ id: 2 })];

      vi.mocked(api.fetchDeletedEvents).mockResolvedValue({
        events: mockEvents,
        total: 2,
      });

      vi.mocked(api.permanentlyDeleteEvent).mockResolvedValue(undefined);

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('empty-trash-button')).toBeInTheDocument();
      });

      // Click Empty Trash
      await user.click(screen.getByTestId('empty-trash-button'));

      // Wait for modal
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Confirm deletion
      const dialog = screen.getByRole('dialog');
      const confirmButton = within(dialog).getByRole('button', { name: /delete forever/i });
      await user.click(confirmButton);

      // All items should be deleted
      await waitFor(() => {
        expect(api.permanentlyDeleteEvent).toHaveBeenCalledWith(1);
        expect(api.permanentlyDeleteEvent).toHaveBeenCalledWith(2);
      });
    });
  });
});
