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

import type { DeletedEvent, SystemConfig } from '../services/api';

// A minimal config shape — the page only reads retention_days and the
// optional trash_retention_days; other fields are filler.
function createMockConfig(overrides: Partial<SystemConfig> = {}): SystemConfig {
  return {
    app_name: 'Home Security Intelligence',
    batch_idle_timeout_seconds: 30,
    batch_window_seconds: 90,
    debug: false,
    detection_confidence_threshold: 0.5,
    fast_path_confidence_threshold: 0.9,
    fast_path_enabled: false,
    grafana_url: '/grafana',
    log_retention_days: 7,
    retention_days: 30,
    trash_retention_days: 30,
    version: '0.1.0',
    ...overrides,
  };
}

// Mock the API module — fetchConfig feeds useSystemConfigQuery for the
// purge clock (F4.3); every test asserts copy that depends on it, so the
// default mock answers the configured value, not the old hardcoded 30.
vi.mock('../services/api', () => ({
  fetchDeletedEvents: vi.fn(),
  restoreEvent: vi.fn(),
  permanentlyDeleteEvent: vi.fn(),
  fetchConfig: vi.fn(),
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
    version: 1, // Optimistic locking version (NEM-3625)
    ...overrides,
  };
}

describe('TrashPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default config per test: the documented trash default of 30. Tests
    // needing a different clock mock it differently in their body.
    vi.mocked(api.fetchConfig).mockResolvedValue(createMockConfig());
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

  // F4.3 (spec 4n-trash.md): the notice and the card chips must show the
  // configured clock, never a hardcoded 30 — the setting lives under
  // Settings › Data and can be 0 (Trash clock disabled).
  describe('purge clock from config (F4.3)', () => {
    it('shows the configured trash_retention_days in the cleanup notice', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(createMockConfig({ trash_retention_days: 14 }));
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

      expect(screen.getByText(/after 14 days/i)).toBeInTheDocument();
      expect(screen.queryByText(/after 30 days/i)).not.toBeInTheDocument();
    });

    it('with trash_retention_days = 0 the notice states the retention clock, not days', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(createMockConfig({ trash_retention_days: 0 }));
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

      expect(screen.getByText(/deleted when their general retention expires/i)).toBeInTheDocument();
      expect(screen.queryByText(/after 0 days/i)).not.toBeInTheDocument();
    });

    it('shows the purge date chip computed by the mirror rule', async () => {
      // started 2025-06-01, deleted 2025-06-10 (relative to now it is "2 days
      // ago" so the Deleted chip stays live); retention 365 so the Trash clock
      // wins: purge at deleted + 30d = Jul 10, 2025.
      const event = createMockDeletedEvent({
        started_at: '2025-06-01T12:00:00Z',
        deleted_at: '2025-06-10T12:00:00Z',
      });
      vi.mocked(api.fetchConfig).mockResolvedValue(
        createMockConfig({ retention_days: 365, trash_retention_days: 30 })
      );
      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: [event],
        total: 1,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('purge-date-1')).toBeInTheDocument();
      });
      expect(screen.getByTestId('purge-date-1')).toHaveTextContent('Purged: Jul 10, 2025');
    });

    it('with trash_retention_days = 0 the chip falls back to the retention deadline', async () => {
      // started 2025-06-01 + 30d = Jul 1, even though deleted + 30d is Jul 10.
      const event = createMockDeletedEvent({
        started_at: '2025-06-01T12:00:00Z',
        deleted_at: '2025-06-10T12:00:00Z',
      });
      vi.mocked(api.fetchConfig).mockResolvedValue(
        createMockConfig({ retention_days: 30, trash_retention_days: 0 })
      );
      vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
        events: [event],
        total: 1,
      });

      const queryClient = createTestQueryClient();

      render(
        <QueryClientProvider client={queryClient}>
          <TrashPage />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('purge-date-1')).toBeInTheDocument();
      });
      expect(screen.getByTestId('purge-date-1')).toHaveTextContent('Purged: Jul 1, 2025');
    });

    it('omits the chip while config has not loaded rather than printing a false date', async () => {
      vi.mocked(api.fetchConfig).mockImplementation(() => new Promise(() => {})); // never resolves
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
        expect(screen.getByText('front_door')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('purge-date-1')).not.toBeInTheDocument();
    });
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
      deleted_at: undefined, // Type workaround for restored event
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
