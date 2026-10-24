/**
 * Tests for useTrashQuery hooks - Soft-deleted events management
 *
 * Following TDD approach: RED -> GREEN -> REFACTOR
 * Tests are written first, then implementation to make them pass.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useDeletedEventsQuery,
  useRestoreEventMutation,
  usePermanentDeleteMutation,
  useSoftDeleteEventMutation,
  useBulkSoftDeleteMutation,
} from './useTrashQuery';
import * as api from '../services/api';

import type { DeletedEvent, Event, BulkOperationResponse } from '../services/api';
import type { ReactNode } from 'react';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchDeletedEvents: vi.fn(),
  restoreEvent: vi.fn(),
  permanentlyDeleteEvent: vi.fn(),
  softDeleteEvent: vi.fn(),
  bulkSoftDeleteEvents: vi.fn(),
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

// Wrapper component for providing QueryClient
function createWrapper() {
  const queryClient = createTestQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
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
    deleted_at: '2025-01-05T12:00:00Z',
    version: 1, // Optimistic locking version (NEM-3625)
    ...overrides,
  };
}

// Factory for creating mock event (restored)
function createMockEvent(overrides: Partial<Event> = {}): Event {
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
    version: 1, // Optimistic locking version (NEM-3625)
    ...overrides,
  };
}

describe('useDeletedEventsQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches deleted events on mount', async () => {
    const mockEvents = [
      createMockDeletedEvent({ id: 1 }),
      createMockDeletedEvent({ id: 2, camera_id: 'back_door' }),
    ];

    vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
      events: mockEvents,
      total: 2,
    });

    const { result } = renderHook(() => useDeletedEventsQuery(), {
      wrapper: createWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);
    expect(result.current.deletedEvents).toEqual([]);

    // Wait for data to load
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.deletedEvents).toHaveLength(2);
    expect(result.current.deletedEvents[0].id).toBe(1);
    expect(result.current.deletedEvents[1].id).toBe(2);
    expect(result.current.total).toBe(2);
    expect(api.fetchDeletedEvents).toHaveBeenCalledTimes(1);
  });

  it('returns empty array when no deleted events exist', async () => {
    vi.mocked(api.fetchDeletedEvents).mockResolvedValueOnce({
      events: [],
      total: 0,
    });

    const { result } = renderHook(() => useDeletedEventsQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.deletedEvents).toEqual([]);
    expect(result.current.total).toBe(0);
    expect(result.current.isEmpty).toBe(true);
  });

  it('handles fetch error gracefully', async () => {
    const error = new Error('Network error');
    vi.mocked(api.fetchDeletedEvents).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useDeletedEventsQuery(), {
      wrapper: createWrapper(),
    });

    // Wait for error state
    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 3000 }
    );

    expect(result.current.deletedEvents).toEqual([]);
  });

  it('can be disabled with enabled option', () => {
    const { result } = renderHook(() => useDeletedEventsQuery({ enabled: false }), {
      wrapper: createWrapper(),
    });

    // Should not fetch when disabled
    expect(api.fetchDeletedEvents).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });

  it('provides refetch function', async () => {
    vi.mocked(api.fetchDeletedEvents)
      .mockResolvedValueOnce({ events: [], total: 0 })
      .mockResolvedValueOnce({
        events: [createMockDeletedEvent()],
        total: 1,
      });

    const { result } = renderHook(() => useDeletedEventsQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.deletedEvents).toHaveLength(0);

    // Trigger refetch
    await result.current.refetch();

    await waitFor(() => {
      expect(result.current.deletedEvents).toHaveLength(1);
    });

    expect(api.fetchDeletedEvents).toHaveBeenCalledTimes(2);
  });
});

describe('useRestoreEventMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('restores a deleted event successfully', async () => {
    const restoredEvent = createMockEvent({ id: 1 });
    vi.mocked(api.restoreEvent).mockResolvedValueOnce(restoredEvent);

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useRestoreEventMutation(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    // Execute the mutation
    await result.current.mutateAsync(1);

    expect(api.restoreEvent).toHaveBeenCalledWith(1);
    expect(api.restoreEvent).toHaveBeenCalledTimes(1);

    // Should invalidate the deleted events query to refetch
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('handles restore error', async () => {
    const error = new Error('Restore failed');
    vi.mocked(api.restoreEvent).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useRestoreEventMutation(), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync(1)).rejects.toThrow('Restore failed');

    // Wait for error to be set in mutation state
    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it('provides loading state during mutation', async () => {
    let resolveRestore: (value: Event) => void;
    const restorePromise = new Promise<Event>((resolve) => {
      resolveRestore = resolve;
    });
    vi.mocked(api.restoreEvent).mockReturnValueOnce(restorePromise);

    const { result } = renderHook(() => useRestoreEventMutation(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    // Start the mutation
    const mutationPromise = result.current.mutateAsync(1);

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });

    // Resolve the restore
    resolveRestore!(createMockEvent());
    await mutationPromise;

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });
  });
});

describe('usePermanentDeleteMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('permanently deletes an event successfully', async () => {
    vi.mocked(api.permanentlyDeleteEvent).mockResolvedValueOnce(undefined);

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => usePermanentDeleteMutation(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    // Execute the mutation
    await result.current.mutateAsync(1);

    expect(api.permanentlyDeleteEvent).toHaveBeenCalledWith(1);
    expect(api.permanentlyDeleteEvent).toHaveBeenCalledTimes(1);

    // Should invalidate the deleted events query
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('handles permanent delete error', async () => {
    const error = new Error('Delete failed');
    vi.mocked(api.permanentlyDeleteEvent).mockRejectedValueOnce(error);

    const { result } = renderHook(() => usePermanentDeleteMutation(), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync(1)).rejects.toThrow('Delete failed');

    // Wait for error to be set in mutation state
    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it('provides loading state during mutation', async () => {
    let resolveDelete: () => void;
    const deletePromise = new Promise<void>((resolve) => {
      resolveDelete = resolve;
    });
    vi.mocked(api.permanentlyDeleteEvent).mockReturnValueOnce(deletePromise);

    const { result } = renderHook(() => usePermanentDeleteMutation(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    // Start the mutation
    const mutationPromise = result.current.mutateAsync(1);

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });

    // Resolve the delete
    resolveDelete!();
    await mutationPromise;

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });
  });

  it('reset clears mutation state', async () => {
    const error = new Error('Delete failed');
    vi.mocked(api.permanentlyDeleteEvent).mockRejectedValueOnce(error);

    const { result } = renderHook(() => usePermanentDeleteMutation(), {
      wrapper: createWrapper(),
    });

    // Trigger error
    try {
      await result.current.mutateAsync(1);
    } catch {
      // Expected error
    }

    // Wait for error to be set
    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    // Reset should clear the error
    result.current.reset();

    await waitFor(() => {
      expect(result.current.error).toBeNull();
    });
  });
});

// ============================================================================
// F4.3: useSoftDeleteEventMutation - Move an event to Trash (ruling 131)
// ============================================================================

describe('useSoftDeleteEventMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('soft deletes an event successfully', async () => {
    vi.mocked(api.softDeleteEvent).mockResolvedValueOnce(undefined);

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useSoftDeleteEventMutation(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    await result.current.mutateAsync(5);

    expect(api.softDeleteEvent).toHaveBeenCalledWith(5);
    expect(api.softDeleteEvent).toHaveBeenCalledTimes(1);

    // Undo window: the deleted list must refetch (the event now appears in Trash)
    // and the main events list must drop the row.
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('handles soft delete error', async () => {
    const error = new Error('Soft delete failed');
    vi.mocked(api.softDeleteEvent).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useSoftDeleteEventMutation(), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync(5)).rejects.toThrow('Soft delete failed');

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it('reset clears mutation state', async () => {
    vi.mocked(api.softDeleteEvent).mockRejectedValueOnce(new Error('fail'));

    const { result } = renderHook(() => useSoftDeleteEventMutation(), {
      wrapper: createWrapper(),
    });

    try {
      await result.current.mutateAsync(5);
    } catch {
      // Expected error
    }

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    result.current.reset();

    await waitFor(() => {
      expect(result.current.error).toBeNull();
    });
  });
});

// ============================================================================
// F4.3: useBulkSoftDeleteMutation - Bulk Delete on the timeline selection bar
// ============================================================================

describe('useBulkSoftDeleteMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function createMockBulkResponse(
    overrides: Partial<BulkOperationResponse> = {}
  ): BulkOperationResponse {
    return {
      total: 2,
      succeeded: 2,
      failed: 0,
      skipped: 0,
      results: [
        { index: 0, status: 'success', id: 7, error: null },
        { index: 1, status: 'success', id: 8, error: null },
      ],
      ...overrides,
    };
  }

  it('bulk soft deletes events and returns the 207 response', async () => {
    const response = createMockBulkResponse();
    vi.mocked(api.bulkSoftDeleteEvents).mockResolvedValueOnce(response);

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useBulkSoftDeleteMutation(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    const out = await result.current.mutateAsync([7, 8]);

    expect(api.bulkSoftDeleteEvents).toHaveBeenCalledWith([7, 8]);
    expect(out).toEqual(response);
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('handles bulk soft delete error', async () => {
    const error = new Error('Bulk delete failed');
    vi.mocked(api.bulkSoftDeleteEvents).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useBulkSoftDeleteMutation(), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync([7])).rejects.toThrow('Bulk delete failed');

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });
});
