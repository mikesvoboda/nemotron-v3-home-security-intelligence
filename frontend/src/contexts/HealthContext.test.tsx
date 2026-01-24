/**
 * Tests for HealthContext.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  HealthProvider,
  useHealthContext,
  useHealthContextOptional,
  DEFAULT_HEALTH,
} from './HealthContext';
import { useHealthStatusQuery } from '../hooks/useHealthStatusQuery';

import type { HealthResponse } from '../services/api';

// Mock the useHealthStatusQuery hook (must be before imports that use it)
vi.mock('../hooks/useHealthStatusQuery');

// ============================================================================
// Test Utilities
// ============================================================================

// Mock data
const mockHealthResponse: HealthResponse = {
  status: 'healthy',
  timestamp: '2024-01-01T00:00:00Z',
  services: {
    database: { status: 'healthy', message: null },
    redis: { status: 'healthy', message: null },
  },
};

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
        <HealthProvider {...providerOptions}>{children}</HealthProvider>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('HealthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set up default mock return value
    vi.mocked(useHealthStatusQuery).mockReturnValue({
      data: mockHealthResponse,
      isLoading: false,
      isRefetching: false,
      isPlaceholderData: false,
      error: null,
      isStale: false,
      overallStatus: 'healthy',
      services: mockHealthResponse.services,
      refetch: vi.fn().mockResolvedValue(undefined),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('useHealthContext', () => {
    it('provides health data', () => {
      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.systemHealth).toEqual(mockHealthResponse);
      expect(result.current.overallStatus).toBe('healthy');
    });

    it('provides services map', () => {
      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.services).toEqual(mockHealthResponse.services);
      expect(result.current.services.database.status).toBe('healthy');
    });

    it('provides isServiceHealthy helper', () => {
      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isServiceHealthy('database')).toBe(true);
      expect(result.current.isServiceHealthy('redis')).toBe(true);
      expect(result.current.isServiceHealthy('nonexistent')).toBe(false);
    });

    it('provides getServiceStatus helper', () => {
      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.getServiceStatus('database')?.status).toBe('healthy');
      expect(result.current.getServiceStatus('nonexistent')).toBeUndefined();
    });

    it('provides loading state', () => {
      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.isRefetching).toBe(false);
    });

    it('provides error state when no errors', () => {
      const { result } = renderHook(() => useHealthContext(), {
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
            return useHealthContext();
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
        'useHealthContext must be used within a HealthProvider'
      );
    });
  });

  describe('useHealthContextOptional', () => {
    it('returns data when within provider', () => {
      const { result } = renderHook(() => useHealthContextOptional(), {
        wrapper: createWrapper(),
      });

      expect(result.current).not.toBeNull();
      expect(result.current?.systemHealth).toEqual(mockHealthResponse);
    });

    it('returns null when outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      const { result } = renderHook(() => useHealthContextOptional(), {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      });

      expect(result.current).toBeNull();
    });
  });

  describe('loading states', () => {
    it('shows isLoading when health query is loading', () => {
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        isPlaceholderData: false,
        error: null,
        isStale: false,
        overallStatus: null,
        services: {},
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('shows isRefetching when query is refetching', () => {
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: mockHealthResponse,
        isLoading: false,
        isRefetching: true,
        isPlaceholderData: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: mockHealthResponse.services,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isRefetching).toBe(true);
    });
  });

  describe('error states', () => {
    it('returns error from health query', () => {
      const healthError = new Error('Failed to fetch health');
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        isPlaceholderData: false,
        error: healthError,
        isStale: false,
        overallStatus: null,
        services: {},
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBe(healthError);
    });
  });

  describe('default values', () => {
    it('provides DEFAULT_HEALTH when health data is not available', () => {
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        isPlaceholderData: false,
        error: null,
        isStale: false,
        overallStatus: null,
        services: {},
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.systemHealth.status).toBe('unknown');
    });

    it('provides "unknown" status when health status is not available', () => {
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        isPlaceholderData: false,
        error: null,
        isStale: false,
        overallStatus: null,
        services: {},
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.overallStatus).toBe('unknown');
    });
  });

  describe('refetch', () => {
    it('calls refetch on health query', async () => {
      const healthRefetch = vi.fn().mockResolvedValue(undefined);

      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: mockHealthResponse,
        isLoading: false,
        isRefetching: false,
        isPlaceholderData: false,
        error: null,
        isStale: false,
        overallStatus: 'healthy',
        services: mockHealthResponse.services,
        refetch: healthRefetch,
      });

      const { result } = renderHook(() => useHealthContext(), {
        wrapper: createWrapper(),
      });

      act(() => {
        void result.current.refetch();
      });

      await waitFor(() => {
        expect(healthRefetch).toHaveBeenCalled();
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
            <HealthProvider pollingInterval={20000}>{children}</HealthProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useHealthContext(), {
        wrapper: CustomWrapper,
      });

      expect(useHealthStatusQuery).toHaveBeenCalledWith({
        enabled: true,
        refetchInterval: 20000,
        staleTime: 20000,
      });
    });

    it('disables query when enabled is false', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      function DisabledWrapper({ children }: { children: React.ReactNode }) {
        return (
          <QueryClientProvider client={queryClient}>
            <HealthProvider enabled={false}>{children}</HealthProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useHealthContext(), {
        wrapper: DisabledWrapper,
      });

      expect(useHealthStatusQuery).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
    });
  });

  describe('DEFAULT_HEALTH constant', () => {
    it('has expected structure', () => {
      expect(DEFAULT_HEALTH).toHaveProperty('status', 'unknown');
      expect(DEFAULT_HEALTH).toHaveProperty('services');
      expect(DEFAULT_HEALTH).toHaveProperty('timestamp');
    });
  });
});
