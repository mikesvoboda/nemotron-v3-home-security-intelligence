/**
 * Tests for useNotificationHistoryQuery hook
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useNotificationHistoryQuery } from './useNotificationHistoryQuery';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    fetchNotificationHistory: vi.fn(),
  };
});

const mockFetchNotificationHistory = vi.mocked(api.fetchNotificationHistory);

// Helper to create a wrapper with QueryClient
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
};

describe('useNotificationHistoryQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockEmptyResponse: api.NotificationHistoryResponse = {
    entries: [],
    count: 0,
    limit: 50,
    offset: 0,
  };

  const mockHistoryResponse: api.NotificationHistoryResponse = {
    entries: [
      {
        id: 'entry-1',
        alert_id: 'alert-1',
        channel: 'email',
        recipient: 'user@example.com',
        success: true,
        error: null,
        delivered_at: '2025-01-25T12:00:00Z',
        created_at: '2025-01-25T11:59:59Z',
      },
      {
        id: 'entry-2',
        alert_id: 'alert-2',
        channel: 'webhook',
        recipient: 'https://hooks.example.com/webhook',
        success: false,
        error: 'Connection timeout',
        delivered_at: null,
        created_at: '2025-01-25T11:58:00Z',
      },
    ],
    count: 2,
    limit: 50,
    offset: 0,
  };

  it('should fetch notification history successfully', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockHistoryResponse);

    const { result } = renderHook(() => useNotificationHistoryQuery(), {
      wrapper: createWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    // Wait for data
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.entries).toHaveLength(2);
    expect(result.current.totalCount).toBe(2);
    expect(result.current.error).toBeNull();
    expect(mockFetchNotificationHistory).toHaveBeenCalledWith({
      limit: 50,
      offset: 0,
    });
  });

  it('should handle empty history response', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    const { result } = renderHook(() => useNotificationHistoryQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.entries).toHaveLength(0);
    expect(result.current.totalCount).toBe(0);
    expect(result.current.totalPages).toBe(1);
  });

  it('should pass channel filter to API', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    const { result } = renderHook(
      () =>
        useNotificationHistoryQuery({
          filters: { channel: 'email' },
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchNotificationHistory).toHaveBeenCalledWith({
      limit: 50,
      offset: 0,
      channel: 'email',
    });
  });

  it('should pass success filter to API', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    const { result } = renderHook(
      () =>
        useNotificationHistoryQuery({
          filters: { success: false },
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchNotificationHistory).toHaveBeenCalledWith({
      limit: 50,
      offset: 0,
      success: false,
    });
  });

  it('should pass alertId filter to API', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    const { result } = renderHook(
      () =>
        useNotificationHistoryQuery({
          filters: { alertId: 'alert-123' },
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchNotificationHistory).toHaveBeenCalledWith({
      limit: 50,
      offset: 0,
      alert_id: 'alert-123',
    });
  });

  it('should handle pagination parameters', async () => {
    mockFetchNotificationHistory.mockResolvedValue({
      entries: [],
      count: 100,
      limit: 10,
      offset: 20,
    });

    const { result } = renderHook(
      () =>
        useNotificationHistoryQuery({
          limit: 10,
          page: 2,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchNotificationHistory).toHaveBeenCalledWith({
      limit: 10,
      offset: 20,
    });
    expect(result.current.totalCount).toBe(100);
    expect(result.current.totalPages).toBe(10);
    expect(result.current.page).toBe(2);
    expect(result.current.hasNextPage).toBe(true);
    expect(result.current.hasPreviousPage).toBe(true);
  });

  it('should handle API errors', async () => {
    const error = new Error('Network error');
    mockFetchNotificationHistory.mockRejectedValue(error);

    const { result } = renderHook(() => useNotificationHistoryQuery(), {
      wrapper: createWrapper(),
    });

    // Wait for error state with increased timeout
    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 3000 }
    );

    expect(result.current.entries).toHaveLength(0);
  });

  it('should not fetch when disabled', () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    const { result } = renderHook(
      () =>
        useNotificationHistoryQuery({
          enabled: false,
        }),
      { wrapper: createWrapper() }
    );

    // Should not be loading since query is disabled
    expect(result.current.isLoading).toBe(false);
    expect(mockFetchNotificationHistory).not.toHaveBeenCalled();
  });

  it('should combine multiple filters', async () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    const { result } = renderHook(
      () =>
        useNotificationHistoryQuery({
          filters: {
            alertId: 'alert-456',
            channel: 'webhook',
            success: true,
          },
          limit: 25,
          page: 1,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchNotificationHistory).toHaveBeenCalledWith({
      limit: 25,
      offset: 25,
      alert_id: 'alert-456',
      channel: 'webhook',
      success: true,
    });
  });

  it('should calculate pagination state correctly', async () => {
    mockFetchNotificationHistory.mockResolvedValue({
      entries: [],
      count: 45,
      limit: 10,
      offset: 0,
    });

    const { result } = renderHook(
      () =>
        useNotificationHistoryQuery({
          limit: 10,
          page: 0,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.totalPages).toBe(5); // 45 items / 10 per page = 5 pages
    expect(result.current.hasNextPage).toBe(true);
    expect(result.current.hasPreviousPage).toBe(false);
  });

  it('should expose invalidate function', () => {
    mockFetchNotificationHistory.mockResolvedValue(mockEmptyResponse);

    const { result } = renderHook(() => useNotificationHistoryQuery(), {
      wrapper: createWrapper(),
    });

    // Just verify the invalidate function exists (don't need to wait for data)
    expect(typeof result.current.invalidate).toBe('function');
  });
});
