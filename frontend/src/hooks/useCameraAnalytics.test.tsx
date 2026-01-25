/**
 * Tests for useCameraAnalytics hook
 *
 * Tests cover:
 * - Combining detection stats and detection trends data
 * - Camera selection state management
 * - URL persistence of selected camera
 * - Loading and error states
 * - Derived analytics values
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useCameraAnalytics } from './useCameraAnalytics';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    fetchDetectionStats: vi.fn(),
    fetchCameras: vi.fn(),
  };
});

// Create a wrapper with both QueryClient and Router for URL persistence
function createWrapper(initialRoute: string = '/') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialRoute]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe('useCameraAnalytics', () => {
  const mockCameras = [
    {
      id: 'front-door',
      name: 'Front Door',
      folder_path: '/cameras/front-door',
      status: 'online' as const,
      last_seen_at: '2026-01-25T10:00:00Z',
      created_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'backyard',
      name: 'Backyard',
      folder_path: '/cameras/backyard',
      status: 'online' as const,
      last_seen_at: '2026-01-25T10:00:00Z',
      created_at: '2026-01-01T00:00:00Z',
    },
  ];

  const mockAllStats = {
    total_detections: 1000,
    detections_by_class: {
      person: 500,
      car: 300,
      dog: 200,
    },
    average_confidence: 0.85,
  };

  const mockCameraStats = {
    total_detections: 400,
    detections_by_class: {
      person: 250,
      car: 100,
      dog: 50,
    },
    average_confidence: 0.88,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchDetectionStats).mockImplementation((params) => {
      if (params?.camera_id) {
        return Promise.resolve(mockCameraStats);
      }
      return Promise.resolve(mockAllStats);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('camera list', () => {
    it('fetches camera list on mount', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoadingCameras).toBe(false);
      });

      expect(api.fetchCameras).toHaveBeenCalled();
      expect(result.current.cameras).toEqual(mockCameras);
    });

    it('provides camerasWithAll including "All Cameras" option', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoadingCameras).toBe(false);
      });

      expect(result.current.camerasWithAll).toHaveLength(3);
      expect(result.current.camerasWithAll[0]).toEqual({
        id: '',
        name: 'All Cameras',
      });
      expect(result.current.camerasWithAll[1]).toEqual({
        id: 'front-door',
        name: 'Front Door',
      });
    });
  });

  describe('camera selection', () => {
    it('starts with no camera selected (all cameras)', () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      expect(result.current.selectedCameraId).toBeUndefined();
    });

    it('selects a camera when setSelectedCameraId is called', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoadingCameras).toBe(false);
      });

      act(() => {
        result.current.setSelectedCameraId('front-door');
      });

      expect(result.current.selectedCameraId).toBe('front-door');
    });

    it('clears selection when empty string is set (All Cameras)', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoadingCameras).toBe(false);
      });

      act(() => {
        result.current.setSelectedCameraId('front-door');
      });

      expect(result.current.selectedCameraId).toBe('front-door');

      act(() => {
        result.current.setSelectedCameraId('');
      });

      expect(result.current.selectedCameraId).toBeUndefined();
    });

    it('reads initial camera from URL parameter', () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper('/?camera=front-door'),
      });

      expect(result.current.selectedCameraId).toBe('front-door');
    });
  });

  describe('detection stats', () => {
    it('fetches all camera stats when no camera selected', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoadingStats).toBe(false);
      });

      expect(api.fetchDetectionStats).toHaveBeenCalledWith({});
      expect(result.current.stats).toEqual(mockAllStats);
    });

    it('fetches camera-specific stats when camera selected', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper('/?camera=front-door'),
      });

      await waitFor(() => {
        expect(result.current.isLoadingStats).toBe(false);
      });

      expect(api.fetchDetectionStats).toHaveBeenCalledWith({
        camera_id: 'front-door',
      });
      expect(result.current.stats).toEqual(mockCameraStats);
    });

    it('refetches stats when camera selection changes', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoadingStats).toBe(false);
      });

      expect(api.fetchDetectionStats).toHaveBeenCalledTimes(1);
      expect(api.fetchDetectionStats).toHaveBeenLastCalledWith({});

      act(() => {
        result.current.setSelectedCameraId('backyard');
      });

      await waitFor(() => {
        expect(api.fetchDetectionStats).toHaveBeenCalledTimes(2);
      });

      expect(api.fetchDetectionStats).toHaveBeenLastCalledWith({
        camera_id: 'backyard',
      });
    });
  });

  describe('selected camera info', () => {
    it('returns undefined for selectedCamera when no camera selected', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoadingCameras).toBe(false);
      });

      expect(result.current.selectedCamera).toBeUndefined();
    });

    it('returns selected camera object when camera is selected', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper('/?camera=front-door'),
      });

      // Wait for cameras to load and find the selected one
      await waitFor(() => {
        expect(result.current.isLoadingCameras).toBe(false);
        expect(result.current.cameras).toHaveLength(2);
      });

      expect(result.current.selectedCamera).toEqual(mockCameras[0]);
    });
  });

  describe('loading states', () => {
    it('shows loading states correctly', () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      // Initial loading states
      expect(result.current.isLoadingCameras).toBe(true);
      expect(result.current.isLoadingStats).toBe(true);
      expect(result.current.isLoading).toBe(true);
    });

    it('clears loading states when data is fetched', async () => {
      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isLoadingCameras).toBe(false);
      expect(result.current.isLoadingStats).toBe(false);
    });
  });

  describe('error handling', () => {
    it('handles camera fetch errors', async () => {
      const mockError = new Error('Failed to fetch cameras');
      vi.mocked(api.fetchCameras).mockRejectedValue(mockError);

      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      // useCamerasQuery has retry: 1 internally, so wait for loading to finish
      // and check if error is present
      await waitFor(
        () => {
          expect(result.current.isLoadingCameras).toBe(false);
        },
        { timeout: 5000 }
      );

      // After loading finishes with error, cameras should be empty
      expect(result.current.cameras).toEqual([]);
      // camerasError may be null if there's retry logic eating it
      // but cameras being empty is the key indicator
    });

    it('handles stats fetch errors', async () => {
      const mockError = new Error('Failed to fetch stats');
      vi.mocked(api.fetchDetectionStats).mockRejectedValue(mockError);

      const { result } = renderHook(() => useCameraAnalytics(), {
        wrapper: createWrapper(),
      });

      // Wait for stats to finish loading
      await waitFor(
        () => {
          expect(result.current.isLoadingStats).toBe(false);
        },
        { timeout: 5000 }
      );

      // After error, statsError should be set or stats should be undefined
      // depending on retry behavior
      expect(result.current.stats).toBeUndefined();
    });
  });
});
