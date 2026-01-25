/**
 * Tests for useCameraSnapshotStatus hook (NEM-3579)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';

import { useCameraSnapshotStatus } from './useCameraSnapshotStatus';
import * as api from '../services/api';
import type { CameraSnapshotStatus } from '../services/api';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    checkCameraSnapshot: vi.fn(),
    getCameraSnapshotUrl: vi.fn((cameraId: string) =>
      `http://localhost:8000/api/cameras/${cameraId}/snapshot`
    ),
  };
});

const mockCheckCameraSnapshot = vi.mocked(api.checkCameraSnapshot);
const mockGetCameraSnapshotUrl = vi.mocked(api.getCameraSnapshotUrl);

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

describe('useCameraSnapshotStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns available status when snapshot exists', async () => {
    const mockStatus: CameraSnapshotStatus = {
      available: true,
      url: 'http://localhost:8000/api/cameras/front_door/snapshot',
    };
    mockCheckCameraSnapshot.mockResolvedValue(mockStatus);

    const { result } = renderHook(
      () => useCameraSnapshotStatus('front_door'),
      { wrapper: createWrapper() }
    );

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    // Wait for data
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockCheckCameraSnapshot).toHaveBeenCalledWith('front_door');
    expect(result.current.isAvailable).toBe(true);
    expect(result.current.error).toBeUndefined();
    expect(result.current.suggestion).toBeUndefined();
  });

  it('returns unavailable status with error details', async () => {
    const mockStatus: CameraSnapshotStatus = {
      available: false,
      url: 'http://localhost:8000/api/cameras/garage/snapshot',
      error: 'Camera folder or snapshot not found',
      errorCode: 404,
      suggestion: 'Verify the camera folder exists and contains image or video files.',
    };
    mockCheckCameraSnapshot.mockResolvedValue(mockStatus);

    const { result } = renderHook(
      () => useCameraSnapshotStatus('garage'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.isAvailable).toBe(false);
    expect(result.current.error).toBe('Camera folder or snapshot not found');
    expect(result.current.suggestion).toContain('Verify the camera folder');
  });

  it('always provides snapshot URL regardless of availability', async () => {
    const mockStatus: CameraSnapshotStatus = {
      available: false,
      url: 'http://localhost:8000/api/cameras/test/snapshot',
      error: 'Not found',
    };
    mockCheckCameraSnapshot.mockResolvedValue(mockStatus);

    const { result } = renderHook(
      () => useCameraSnapshotStatus('test'),
      { wrapper: createWrapper() }
    );

    // URL should be available immediately (before loading completes)
    expect(result.current.snapshotUrl).toBe('http://localhost:8000/api/cameras/test/snapshot');
    expect(mockGetCameraSnapshotUrl).toHaveBeenCalledWith('test');
  });

  it('does not fetch when cameraId is undefined', () => {
    const { result } = renderHook(
      () => useCameraSnapshotStatus(undefined),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(mockCheckCameraSnapshot).not.toHaveBeenCalled();
    expect(result.current.snapshotUrl).toBe('');
  });

  it('does not fetch when disabled', () => {
    const { result } = renderHook(
      () => useCameraSnapshotStatus('front_door', { enabled: false }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(mockCheckCameraSnapshot).not.toHaveBeenCalled();
  });

  it('provides recheck function', async () => {
    const mockStatus: CameraSnapshotStatus = {
      available: true,
      url: 'http://localhost:8000/api/cameras/front_door/snapshot',
    };
    mockCheckCameraSnapshot.mockResolvedValue(mockStatus);

    const { result } = renderHook(
      () => useCameraSnapshotStatus('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.recheck).toBeDefined();
    expect(typeof result.current.recheck).toBe('function');

    // Trigger recheck
    await result.current.recheck();
    expect(mockCheckCameraSnapshot).toHaveBeenCalledTimes(2);
  });

  it('handles network errors', async () => {
    mockCheckCameraSnapshot.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(
      () => useCameraSnapshotStatus('front_door'),
      { wrapper: createWrapper() }
    );

    // Wait for error state with extended timeout (retry takes time)
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 3000 });

    expect(result.current.isAvailable).toBe(false);
  });

  it('tracks isChecking state during refetch', async () => {
    const mockStatus: CameraSnapshotStatus = {
      available: true,
      url: 'http://localhost:8000/api/cameras/front_door/snapshot',
    };
    mockCheckCameraSnapshot.mockResolvedValue(mockStatus);

    const { result } = renderHook(
      () => useCameraSnapshotStatus('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isChecking).toBe(false);
  });

  it('defaults isAvailable to false when no data', () => {
    mockCheckCameraSnapshot.mockImplementation(() => new Promise(() => {})); // Never resolves

    const { result } = renderHook(
      () => useCameraSnapshotStatus('front_door'),
      { wrapper: createWrapper() }
    );

    expect(result.current.isAvailable).toBe(false);
  });
});
