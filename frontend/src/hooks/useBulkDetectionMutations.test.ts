/**
 * Tests for useBulkDetectionMutations hooks
 *
 * @module hooks/useBulkDetectionMutations.test
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { createElement } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useBulkCreateDetections,
  useBulkUpdateDetections,
  useBulkDeleteDetections,
} from './useBulkDetectionMutations';
import * as api from '../services/api';

import type {
  BulkOperationResponse,
  DetectionBulkCreateItem,
  DetectionBulkCreateResponse,
  DetectionBulkUpdateItem,
} from '../types/bulk';

// Mock the API module
vi.mock('../services/api', () => ({
  bulkCreateDetections: vi.fn(),
  bulkUpdateDetections: vi.fn(),
  bulkDeleteDetections: vi.fn(),
}));

// Helper to create a wrapper with QueryClientProvider
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// Sample test data
const createDetectionItem: DetectionBulkCreateItem = {
  camera_id: 'cam-test-1',
  object_type: 'person',
  confidence: 0.95,
  detected_at: '2024-01-20T10:30:00Z',
  file_path: '/uploads/cam-test-1/frame_001.jpg',
  bbox_x: 100,
  bbox_y: 50,
  bbox_width: 200,
  bbox_height: 400,
};

const createSuccessResponse: DetectionBulkCreateResponse = {
  total: 2,
  succeeded: 2,
  failed: 0,
  skipped: 0,
  results: [
    { index: 0, status: 'success', id: 1 },
    { index: 1, status: 'success', id: 2 },
  ],
};

const updateSuccessResponse: BulkOperationResponse = {
  total: 2,
  succeeded: 2,
  failed: 0,
  skipped: 0,
  results: [
    { index: 0, status: 'success', id: 1 },
    { index: 1, status: 'success', id: 2 },
  ],
};

const partialSuccessResponse: BulkOperationResponse = {
  total: 3,
  succeeded: 2,
  failed: 1,
  skipped: 0,
  results: [
    { index: 0, status: 'success', id: 1 },
    { index: 1, status: 'failed', error: 'Detection not found' },
    { index: 2, status: 'success', id: 3 },
  ],
};

describe('useBulkCreateDetections', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('starts with idle state', () => {
    const { result } = renderHook(() => useBulkCreateDetections(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isPending).toBe(false);
    expect(result.current.isSuccess).toBe(false);
    expect(result.current.isError).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeNull();
  });

  it('creates detections successfully', async () => {
    vi.mocked(api.bulkCreateDetections).mockResolvedValueOnce(createSuccessResponse);

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useBulkCreateDetections({ onSuccess }), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.mutate([createDetectionItem, createDetectionItem]);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.bulkCreateDetections).toHaveBeenCalled();
    expect(vi.mocked(api.bulkCreateDetections).mock.calls[0][0]).toEqual([createDetectionItem, createDetectionItem]);
    expect(result.current.data).toEqual(createSuccessResponse);
    expect(onSuccess).toHaveBeenCalledWith(createSuccessResponse);
  });

  it('handles API errors', async () => {
    const apiError = new Error('Network error');
    vi.mocked(api.bulkCreateDetections).mockRejectedValueOnce(apiError);

    const onError = vi.fn();
    const { result } = renderHook(() => useBulkCreateDetections({ onError }), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.mutate([createDetectionItem]);
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toEqual(apiError);
    expect(onError).toHaveBeenCalledWith(apiError);
  });

  it('supports mutateAsync', async () => {
    vi.mocked(api.bulkCreateDetections).mockResolvedValueOnce(createSuccessResponse);

    const { result } = renderHook(() => useBulkCreateDetections(), {
      wrapper: createWrapper(),
    });

    let response: DetectionBulkCreateResponse | undefined;
    await act(async () => {
      response = await result.current.mutateAsync([createDetectionItem]);
    });

    expect(response).toEqual(createSuccessResponse);
  });

  it('resets state correctly', async () => {
    vi.mocked(api.bulkCreateDetections).mockResolvedValueOnce(createSuccessResponse);

    const { result } = renderHook(() => useBulkCreateDetections(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.mutate([createDetectionItem]);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    act(() => {
      result.current.reset();
    });

    // After reset, mutation should be in idle state
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
    });
    expect(result.current.isError).toBe(false);
    expect(result.current.isPending).toBe(false);
  });
});

describe('useBulkUpdateDetections', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('updates detections successfully', async () => {
    vi.mocked(api.bulkUpdateDetections).mockResolvedValueOnce(updateSuccessResponse);

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useBulkUpdateDetections({ onSuccess }), {
      wrapper: createWrapper(),
    });

    const updates: DetectionBulkUpdateItem[] = [
      { id: 1, object_type: 'vehicle' },
      { id: 2, confidence: 0.99 },
    ];

    act(() => {
      result.current.mutate(updates);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.bulkUpdateDetections).toHaveBeenCalled();
    expect(vi.mocked(api.bulkUpdateDetections).mock.calls[0][0]).toEqual(updates);
    expect(result.current.data).toEqual(updateSuccessResponse);
    expect(onSuccess).toHaveBeenCalledWith(updateSuccessResponse);
  });

  it('handles partial success (HTTP 207)', async () => {
    vi.mocked(api.bulkUpdateDetections).mockResolvedValueOnce(partialSuccessResponse);

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useBulkUpdateDetections({ onSuccess }), {
      wrapper: createWrapper(),
    });

    const updates: DetectionBulkUpdateItem[] = [
      { id: 1, object_type: 'vehicle' },
      { id: 999, object_type: 'person' }, // Non-existent
      { id: 3, confidence: 0.8 },
    ];

    act(() => {
      result.current.mutate(updates);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // HTTP 207 is treated as success
    expect(result.current.data).toEqual(partialSuccessResponse);
    expect(result.current.data?.failed).toBe(1);
    expect(onSuccess).toHaveBeenCalledWith(partialSuccessResponse);
  });

  it('handles API errors', async () => {
    const apiError = new Error('Server error');
    vi.mocked(api.bulkUpdateDetections).mockRejectedValueOnce(apiError);

    const onError = vi.fn();
    const { result } = renderHook(() => useBulkUpdateDetections({ onError }), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.mutate([{ id: 1, object_type: 'vehicle' }]);
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toEqual(apiError);
    expect(onError).toHaveBeenCalledWith(apiError);
  });
});

describe('useBulkDeleteDetections', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('deletes detections successfully', async () => {
    const deleteResponse: BulkOperationResponse = {
      total: 3,
      succeeded: 3,
      failed: 0,
      skipped: 0,
      results: [
        { index: 0, status: 'success', id: 1 },
        { index: 1, status: 'success', id: 2 },
        { index: 2, status: 'success', id: 3 },
      ],
    };
    vi.mocked(api.bulkDeleteDetections).mockResolvedValueOnce(deleteResponse);

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useBulkDeleteDetections({ onSuccess }), {
      wrapper: createWrapper(),
    });

    const idsToDelete = [1, 2, 3];

    act(() => {
      result.current.mutate(idsToDelete);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.bulkDeleteDetections).toHaveBeenCalled();
    expect(vi.mocked(api.bulkDeleteDetections).mock.calls[0][0]).toEqual(idsToDelete);
    expect(result.current.data).toEqual(deleteResponse);
    expect(onSuccess).toHaveBeenCalledWith(deleteResponse);
  });

  it('handles partial delete failure', async () => {
    const partialDeleteResponse: BulkOperationResponse = {
      total: 3,
      succeeded: 2,
      failed: 1,
      skipped: 0,
      results: [
        { index: 0, status: 'success', id: 1 },
        { index: 1, status: 'failed', error: 'Detection 999 not found' },
        { index: 2, status: 'success', id: 3 },
      ],
    };
    vi.mocked(api.bulkDeleteDetections).mockResolvedValueOnce(partialDeleteResponse);

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useBulkDeleteDetections({ onSuccess }), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.mutate([1, 999, 3]);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.failed).toBe(1);
    expect(result.current.data?.results?.[1].error).toBe('Detection 999 not found');
  });

  it('handles API errors', async () => {
    const apiError = new Error('Permission denied');
    vi.mocked(api.bulkDeleteDetections).mockRejectedValueOnce(apiError);

    const onError = vi.fn();
    const { result } = renderHook(() => useBulkDeleteDetections({ onError }), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.mutate([1, 2, 3]);
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toEqual(apiError);
    expect(onError).toHaveBeenCalledWith(apiError);
  });

  it('supports skipInvalidation option', async () => {
    const deleteResponse: BulkOperationResponse = {
      total: 1,
      succeeded: 1,
      failed: 0,
      skipped: 0,
      results: [{ index: 0, status: 'success', id: 1 }],
    };
    vi.mocked(api.bulkDeleteDetections).mockResolvedValueOnce(deleteResponse);

    const { result } = renderHook(
      () => useBulkDeleteDetections({ skipInvalidation: true }),
      { wrapper: createWrapper() }
    );

    act(() => {
      result.current.mutate([1]);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // The mutation should complete without errors
    expect(result.current.data).toEqual(deleteResponse);
  });
});

describe('Hook Integration', () => {
  it('all hooks can be used together', async () => {
    vi.mocked(api.bulkCreateDetections).mockResolvedValueOnce(createSuccessResponse);
    vi.mocked(api.bulkUpdateDetections).mockResolvedValueOnce(updateSuccessResponse);
    vi.mocked(api.bulkDeleteDetections).mockResolvedValueOnce({
      total: 1,
      succeeded: 1,
      failed: 0,
      skipped: 0,
      results: [{ index: 0, status: 'success', id: 1 }],
    });

    const { result } = renderHook(
      () => ({
        create: useBulkCreateDetections(),
        update: useBulkUpdateDetections(),
        delete: useBulkDeleteDetections(),
      }),
      { wrapper: createWrapper() }
    );

    // All hooks should start in idle state
    expect(result.current.create.isPending).toBe(false);
    expect(result.current.update.isPending).toBe(false);
    expect(result.current.delete.isPending).toBe(false);

    // Execute create
    act(() => {
      result.current.create.mutate([createDetectionItem]);
    });

    await waitFor(() => {
      expect(result.current.create.isSuccess).toBe(true);
    });

    // Execute update
    act(() => {
      result.current.update.mutate([{ id: 1, object_type: 'vehicle' }]);
    });

    await waitFor(() => {
      expect(result.current.update.isSuccess).toBe(true);
    });

    // Execute delete
    act(() => {
      result.current.delete.mutate([1]);
    });

    await waitFor(() => {
      expect(result.current.delete.isSuccess).toBe(true);
    });
  });
});
