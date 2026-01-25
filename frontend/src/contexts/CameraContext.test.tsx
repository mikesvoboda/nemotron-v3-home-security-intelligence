/**
 * Tests for CameraContext.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { CameraProvider, useCameraContext, useCameraContextOptional } from './CameraContext';
import { useCamerasQuery } from '../hooks/useCamerasQuery';

import type { Camera } from '../services/api';

// Mock the useCamerasQuery hook (must be before imports that use it)
vi.mock('../hooks/useCamerasQuery');

// ============================================================================
// Test Utilities
// ============================================================================

// Mock data
const mockCameras: Camera[] = [
  {
    id: 'front_door',
    name: 'Front Door',
    folder_path: '/export/foscam/front_door',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: null,
  },
  {
    id: 'backyard',
    name: 'Backyard',
    folder_path: '/export/foscam/backyard',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: null,
  },
];

// Create wrapper with QueryClientProvider
function createWrapper(providerOptions: { pollingInterval?: number; enabled?: boolean } = {}) {
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
        <CameraProvider {...providerOptions}>{children}</CameraProvider>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('CameraContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set up default mock return value
    vi.mocked(useCamerasQuery).mockReturnValue({
      cameras: mockCameras,
      isLoading: false,
      isRefetching: false,
      isPlaceholderData: false,
      error: null,
      refetch: vi.fn().mockResolvedValue(undefined),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('useCameraContext', () => {
    it('provides camera data', () => {
      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.cameras).toEqual(mockCameras);
      expect(result.current.cameras).toHaveLength(2);
    });

    it('provides camera name map', () => {
      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.cameraNameMap.get('front_door')).toBe('Front Door');
      expect(result.current.cameraNameMap.get('backyard')).toBe('Backyard');
    });

    it('provides getCameraById helper', () => {
      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      const camera = result.current.getCameraById('front_door');
      expect(camera?.name).toBe('Front Door');
      expect(result.current.getCameraById('nonexistent')).toBeUndefined();
    });

    it('provides getCameraName helper with fallback', () => {
      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.getCameraName('front_door')).toBe('Front Door');
      expect(result.current.getCameraName('nonexistent')).toBe('Unknown Camera');
      expect(result.current.getCameraName('nonexistent', 'Custom Fallback')).toBe(
        'Custom Fallback'
      );
    });

    it('provides loading state', () => {
      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.isRefetching).toBe(false);
    });

    it('provides error state when no errors', () => {
      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBeNull();
    });

    it('throws error when used outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      const { result } = renderHook(
        () => {
          try {
            return useCameraContext();
          } catch (e) {
            return e;
          }
        },
        {
          wrapper: ({ children }) => (
            <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
          ),
        }
      );

      expect(result.current).toBeInstanceOf(Error);
      expect((result.current as Error).message).toBe(
        'useCameraContext must be used within a CameraProvider'
      );
    });
  });

  describe('useCameraContextOptional', () => {
    it('returns data when within provider', () => {
      const { result } = renderHook(() => useCameraContextOptional(), {
        wrapper: createWrapper(),
      });

      expect(result.current).not.toBeNull();
      expect(result.current?.cameras).toEqual(mockCameras);
    });

    it('returns null when outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      const { result } = renderHook(() => useCameraContextOptional(), {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      });

      expect(result.current).toBeNull();
    });
  });

  describe('loading states', () => {
    it('shows isLoading when cameras query is loading', () => {
      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: true,
        isRefetching: false,
        isPlaceholderData: false,
        error: null,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('shows isRefetching when query is refetching', () => {
      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: true,
        isPlaceholderData: false,
        error: null,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isRefetching).toBe(true);
    });
  });

  describe('error states', () => {
    it('returns error from cameras query', () => {
      const camerasError = new Error('Failed to fetch cameras');
      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        isPlaceholderData: false,
        error: camerasError,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBe(camerasError);
    });
  });

  describe('refetch', () => {
    it('calls refetch on cameras query', async () => {
      const camerasRefetch = vi.fn().mockResolvedValue(undefined);

      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        isPlaceholderData: false,
        error: null,
        refetch: camerasRefetch,
      });

      const { result } = renderHook(() => useCameraContext(), {
        wrapper: createWrapper(),
      });

      act(() => {
        void result.current.refetch();
      });

      await waitFor(() => {
        expect(camerasRefetch).toHaveBeenCalled();
      });
    });
  });

  describe('provider configuration', () => {
    it('passes custom polling interval to query', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      function CustomWrapper({ children }: { children: React.ReactNode }) {
        return (
          <QueryClientProvider client={queryClient}>
            <CameraProvider pollingInterval={60000}>{children}</CameraProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useCameraContext(), {
        wrapper: CustomWrapper,
      });

      expect(useCamerasQuery).toHaveBeenCalledWith({
        enabled: true,
        refetchInterval: 60000,
        staleTime: 60000,
      });
    });

    it('disables query when enabled is false', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      function DisabledWrapper({ children }: { children: React.ReactNode }) {
        return (
          <QueryClientProvider client={queryClient}>
            <CameraProvider enabled={false}>{children}</CameraProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useCameraContext(), {
        wrapper: DisabledWrapper,
      });

      expect(useCamerasQuery).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
    });
  });
});
