/**
 * Tests for useCameraPathValidationQuery hook (NEM-3578)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';

import { useCameraPathValidationQuery } from './useCameraPathValidationQuery';
import * as api from '../services/api';
import type { CameraPathValidationResponse } from '../services/api';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    fetchCameraPathValidation: vi.fn(),
  };
});

const mockFetchCameraPathValidation = vi.mocked(api.fetchCameraPathValidation);

// Helper to create a test wrapper with QueryClient
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

// Mock response data
const mockValidationResponse: CameraPathValidationResponse = {
  base_path: '/export/foscam',
  total_cameras: 3,
  valid_count: 2,
  invalid_count: 1,
  valid_cameras: [
    {
      id: 'front_door',
      name: 'Front Door',
      folder_path: '/export/foscam/front_door',
      status: 'online',
      resolved_path: null,
      issues: null,
    },
    {
      id: 'backyard',
      name: 'Backyard',
      folder_path: '/export/foscam/backyard',
      status: 'online',
      resolved_path: null,
      issues: null,
    },
  ],
  invalid_cameras: [
    {
      id: 'garage',
      name: 'Garage',
      folder_path: '/export/foscam/garage',
      status: 'offline',
      resolved_path: '/export/foscam/garage',
      issues: ['directory does not exist'],
    },
  ],
};

describe('useCameraPathValidationQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchCameraPathValidation.mockResolvedValue(mockValidationResponse);
  });

  it('fetches validation results successfully', async () => {
    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    // Wait for data
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockFetchCameraPathValidation).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual(mockValidationResponse);
    expect(result.current.totalCameras).toBe(3);
    expect(result.current.validCount).toBe(2);
    expect(result.current.invalidCount).toBe(1);
  });

  it('returns valid and invalid cameras separately', async () => {
    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.validCameras).toHaveLength(2);
    expect(result.current.invalidCameras).toHaveLength(1);
    expect(result.current.invalidCameras[0].issues).toContain('directory does not exist');
  });

  it('returns basePath from response', async () => {
    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.basePath).toBe('/export/foscam');
  });

  it('calculates allValid correctly when some cameras are invalid', async () => {
    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.allValid).toBe(false);
  });

  it('calculates allValid correctly when all cameras are valid', async () => {
    mockFetchCameraPathValidation.mockResolvedValue({
      ...mockValidationResponse,
      invalid_count: 0,
      invalid_cameras: [],
    });

    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.allValid).toBe(true);
  });

  it('does not fetch when disabled', async () => {
    const { result } = renderHook(
      () => useCameraPathValidationQuery({ enabled: false }),
      { wrapper: createWrapper() }
    );

    // Should not be loading when disabled
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(mockFetchCameraPathValidation).not.toHaveBeenCalled();
  });

  it('handles errors gracefully', async () => {
    const error = new Error('Network error');
    mockFetchCameraPathValidation.mockRejectedValue(error);

    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    // Wait for error state with extended timeout (retry takes time)
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 3000 });

    expect(result.current.error).toBeTruthy();
    expect(result.current.validCameras).toEqual([]);
    expect(result.current.invalidCameras).toEqual([]);
  });

  it('provides refetch function', async () => {
    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.refetch).toBeDefined();
    expect(typeof result.current.refetch).toBe('function');

    // Trigger refetch
    await result.current.refetch();
    expect(mockFetchCameraPathValidation).toHaveBeenCalledTimes(2);
  });

  it('returns empty arrays when no data', () => {
    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    // Before data is loaded, arrays should be empty (not undefined)
    expect(result.current.validCameras).toEqual([]);
    expect(result.current.invalidCameras).toEqual([]);
    expect(result.current.totalCameras).toBe(0);
    expect(result.current.validCount).toBe(0);
    expect(result.current.invalidCount).toBe(0);
  });

  it('allValid is false when totalCameras is 0', async () => {
    mockFetchCameraPathValidation.mockResolvedValue({
      base_path: '/export/foscam',
      total_cameras: 0,
      valid_count: 0,
      invalid_count: 0,
      valid_cameras: [],
      invalid_cameras: [],
    });

    const { result } = renderHook(() => useCameraPathValidationQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // allValid should be false when there are no cameras
    expect(result.current.allValid).toBe(false);
  });
});
