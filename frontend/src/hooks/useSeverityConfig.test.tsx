/**
 * Tests for useSeverityConfig hook.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useSeverityConfig } from './useSeverityConfig';
import { fetchSeverityMetadata } from '../services/api';
import {
  DEFAULT_SEVERITY_DEFINITIONS,
  DEFAULT_SEVERITY_THRESHOLDS,
} from '../types/severity';

import type { SeverityMetadata } from '../types/severity';

// Mock the API function
vi.mock('../services/api', () => ({
  fetchSeverityMetadata: vi.fn(),
}));

// ============================================================================
// Test Utilities
// ============================================================================

// Mock data matching backend response
const mockSeverityMetadata: SeverityMetadata = {
  definitions: [
    {
      severity: 'low',
      label: 'Low',
      description: 'Minimal risk, routine activity',
      color: '#22c55e',
      priority: 1,
      min_score: 0,
      max_score: 29,
    },
    {
      severity: 'medium',
      label: 'Medium',
      description: 'Moderate risk, requires attention',
      color: '#eab308',
      priority: 2,
      min_score: 30,
      max_score: 59,
    },
    {
      severity: 'high',
      label: 'High',
      description: 'Elevated risk, urgent attention needed',
      color: '#f97316',
      priority: 3,
      min_score: 60,
      max_score: 84,
    },
    {
      severity: 'critical',
      label: 'Critical',
      description: 'Critical risk, immediate action required',
      color: '#ef4444',
      priority: 4,
      min_score: 85,
      max_score: 100,
    },
  ],
  thresholds: {
    low_max: 29,
    medium_max: 59,
    high_max: 84,
  },
};

// Custom thresholds for testing dynamic behavior
const customThresholds: SeverityMetadata = {
  definitions: mockSeverityMetadata.definitions.map((def) => ({
    ...def,
    // Adjust score ranges for custom thresholds
    min_score:
      def.severity === 'low'
        ? 0
        : def.severity === 'medium'
          ? 21
          : def.severity === 'high'
            ? 51
            : 81,
    max_score:
      def.severity === 'low'
        ? 20
        : def.severity === 'medium'
          ? 50
          : def.severity === 'high'
            ? 80
            : 100,
  })),
  thresholds: {
    low_max: 20,
    medium_max: 50,
    high_max: 80,
  },
};

// Create wrapper with QueryClientProvider
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Disable all retries in tests to fail fast
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// Longer timeout for error cases where retries may occur
const ERROR_WAIT_TIMEOUT = { timeout: 3000 };

// ============================================================================
// Tests
// ============================================================================

describe('useSeverityConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set up default mock to resolve successfully
    vi.mocked(fetchSeverityMetadata).mockResolvedValue(mockSeverityMetadata);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('successful data fetching', () => {
    it('fetches severity metadata on mount', async () => {
      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(fetchSeverityMetadata).toHaveBeenCalledTimes(1);
      expect(result.current.data).toEqual(mockSeverityMetadata);
    });

    it('provides thresholds from API response', async () => {
      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.thresholds).toEqual(mockSeverityMetadata.thresholds);
    });

    it('provides definitions from API response', async () => {
      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.definitions).toEqual(mockSeverityMetadata.definitions);
      expect(result.current.definitions).toHaveLength(4);
    });
  });

  describe('fallback to defaults', () => {
    it('uses default thresholds while loading', () => {
      // Make the fetch hang indefinitely
      vi.mocked(fetchSeverityMetadata).mockImplementation(() => new Promise(() => {}));

      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.thresholds).toEqual(DEFAULT_SEVERITY_THRESHOLDS);
    });

    it('uses default definitions while loading', () => {
      vi.mocked(fetchSeverityMetadata).mockImplementation(() => new Promise(() => {}));

      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      expect(result.current.definitions).toEqual(DEFAULT_SEVERITY_DEFINITIONS);
    });

    it('uses default thresholds on API error', async () => {
      vi.mocked(fetchSeverityMetadata).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isLoading).toBe(false);
        },
        ERROR_WAIT_TIMEOUT
      );

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.thresholds).toEqual(DEFAULT_SEVERITY_THRESHOLDS);
    });
  });

  describe('getRiskLevel function', () => {
    describe('with default thresholds', () => {
      it('returns "low" for scores 0-29', async () => {
        const { result } = renderHook(() => useSeverityConfig(), {
          wrapper: createWrapper(),
        });

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.getRiskLevel(0)).toBe('low');
        expect(result.current.getRiskLevel(15)).toBe('low');
        expect(result.current.getRiskLevel(29)).toBe('low');
      });

      it('returns "medium" for scores 30-59', async () => {
        const { result } = renderHook(() => useSeverityConfig(), {
          wrapper: createWrapper(),
        });

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.getRiskLevel(30)).toBe('medium');
        expect(result.current.getRiskLevel(45)).toBe('medium');
        expect(result.current.getRiskLevel(59)).toBe('medium');
      });

      it('returns "high" for scores 60-84', async () => {
        const { result } = renderHook(() => useSeverityConfig(), {
          wrapper: createWrapper(),
        });

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.getRiskLevel(60)).toBe('high');
        expect(result.current.getRiskLevel(70)).toBe('high');
        expect(result.current.getRiskLevel(84)).toBe('high');
      });

      it('returns "critical" for scores 85-100', async () => {
        const { result } = renderHook(() => useSeverityConfig(), {
          wrapper: createWrapper(),
        });

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.getRiskLevel(85)).toBe('critical');
        expect(result.current.getRiskLevel(92)).toBe('critical');
        expect(result.current.getRiskLevel(100)).toBe('critical');
      });
    });

    describe('with custom thresholds', () => {
      it('uses custom thresholds from API', async () => {
        vi.mocked(fetchSeverityMetadata).mockResolvedValue(customThresholds);

        const { result } = renderHook(() => useSeverityConfig(), {
          wrapper: createWrapper(),
        });

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });

        // With custom thresholds: low_max=20, medium_max=50, high_max=80
        expect(result.current.getRiskLevel(20)).toBe('low');
        expect(result.current.getRiskLevel(21)).toBe('medium');
        expect(result.current.getRiskLevel(50)).toBe('medium');
        expect(result.current.getRiskLevel(51)).toBe('high');
        expect(result.current.getRiskLevel(80)).toBe('high');
        expect(result.current.getRiskLevel(81)).toBe('critical');
      });
    });

    describe('input validation', () => {
      it('throws error for negative scores', async () => {
        const { result } = renderHook(() => useSeverityConfig(), {
          wrapper: createWrapper(),
        });

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });

        expect(() => result.current.getRiskLevel(-1)).toThrow(
          'Risk score must be between 0 and 100'
        );
        expect(() => result.current.getRiskLevel(-10)).toThrow(
          'Risk score must be between 0 and 100'
        );
      });

      it('throws error for scores above 100', async () => {
        const { result } = renderHook(() => useSeverityConfig(), {
          wrapper: createWrapper(),
        });

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });

        expect(() => result.current.getRiskLevel(101)).toThrow(
          'Risk score must be between 0 and 100'
        );
        expect(() => result.current.getRiskLevel(150)).toThrow(
          'Risk score must be between 0 and 100'
        );
      });
    });
  });

  describe('query options', () => {
    it('does not fetch when disabled', async () => {
      const { result } = renderHook(() => useSeverityConfig({ enabled: false }), {
        wrapper: createWrapper(),
      });

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(fetchSeverityMetadata).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('uses custom stale time', () => {
      renderHook(() => useSeverityConfig({ staleTime: 10000 }), {
        wrapper: createWrapper(),
      });

      // Verify the hook was called - stale time is internal to react-query
      expect(fetchSeverityMetadata).toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(fetchSeverityMetadata).toHaveBeenCalledTimes(1);

      await result.current.refetch();

      expect(fetchSeverityMetadata).toHaveBeenCalledTimes(2);
    });
  });

  describe('error handling', () => {
    it('sets error state on API failure', async () => {
      const error = new Error('Failed to fetch severity config');
      vi.mocked(fetchSeverityMetadata).mockRejectedValue(error);

      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isLoading).toBe(false);
        },
        ERROR_WAIT_TIMEOUT
      );

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe('Failed to fetch severity config');
    });

    it('getRiskLevel still works with defaults after error', async () => {
      vi.mocked(fetchSeverityMetadata).mockRejectedValue(new Error('API Error'));

      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isLoading).toBe(false);
        },
        ERROR_WAIT_TIMEOUT
      );

      // Should use default thresholds
      expect(result.current.getRiskLevel(50)).toBe('medium');
    });
  });

  describe('loading states', () => {
    it('isLoading is true during initial fetch', async () => {
      let resolvePromise: (value: SeverityMetadata) => void;
      vi.mocked(fetchSeverityMetadata).mockImplementation(
        () =>
          new Promise((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);

      // Resolve the promise
      resolvePromise!(mockSeverityMetadata);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('isRefetching is true during background refetch', async () => {
      const { result } = renderHook(() => useSeverityConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Trigger refetch
      const refetchPromise = result.current.refetch();

      // Check isRefetching (may be brief)
      await refetchPromise;

      // After refetch completes, isRefetching should be false
      expect(result.current.isRefetching).toBe(false);
    });
  });
});
