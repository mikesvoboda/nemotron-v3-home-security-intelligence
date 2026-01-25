/**
 * Tests for SeverityContext.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  SeverityProvider,
  useSeverity,
  useSeverityOptional,
  DEFAULT_SEVERITY_CONTEXT,
} from './SeverityContext';
import { useSeverityConfig } from '../hooks/useSeverityConfig';
import {
  DEFAULT_SEVERITY_DEFINITIONS,
  DEFAULT_SEVERITY_THRESHOLDS,
} from '../types/severity';

import type { SeverityMetadata } from '../types/severity';

// Mock the useSeverityConfig hook (must be before imports that use it)
vi.mock('../hooks/useSeverityConfig');

// ============================================================================
// Test Utilities
// ============================================================================

// Mock data
const mockSeverityMetadata: SeverityMetadata = {
  definitions: [
    {
      severity: 'low',
      label: 'Low',
      description: 'Minimal risk',
      color: '#22c55e',
      priority: 1,
      min_score: 0,
      max_score: 29,
    },
    {
      severity: 'medium',
      label: 'Medium',
      description: 'Moderate risk',
      color: '#eab308',
      priority: 2,
      min_score: 30,
      max_score: 59,
    },
    {
      severity: 'high',
      label: 'High',
      description: 'Elevated risk',
      color: '#f97316',
      priority: 3,
      min_score: 60,
      max_score: 84,
    },
    {
      severity: 'critical',
      label: 'Critical',
      description: 'Critical risk',
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

// Create wrapper with QueryClientProvider and SeverityProvider
function createWrapper(providerOptions: { enabled?: boolean } = {}) {
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
        <SeverityProvider {...providerOptions}>{children}</SeverityProvider>
      </QueryClientProvider>
    );
  };
}

// Mock getRiskLevel function
function createMockGetRiskLevel(thresholds = mockSeverityMetadata.thresholds) {
  return (score: number) => {
    if (score < 0 || score > 100) {
      throw new Error('Risk score must be between 0 and 100');
    }
    if (score <= thresholds.low_max) return 'low' as const;
    if (score <= thresholds.medium_max) return 'medium' as const;
    if (score <= thresholds.high_max) return 'high' as const;
    return 'critical' as const;
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('SeverityContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set up default mock return value
    vi.mocked(useSeverityConfig).mockReturnValue({
      data: mockSeverityMetadata,
      thresholds: mockSeverityMetadata.thresholds,
      definitions: mockSeverityMetadata.definitions,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      refetch: vi.fn().mockResolvedValue(undefined),
      getRiskLevel: createMockGetRiskLevel(),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('useSeverity', () => {
    it('provides thresholds from hook', () => {
      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      expect(result.current.thresholds).toEqual(mockSeverityMetadata.thresholds);
    });

    it('provides definitions from hook', () => {
      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      expect(result.current.definitions).toEqual(mockSeverityMetadata.definitions);
      expect(result.current.definitions).toHaveLength(4);
    });

    it('provides getRiskLevel function', () => {
      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      expect(result.current.getRiskLevel(25)).toBe('low');
      expect(result.current.getRiskLevel(50)).toBe('medium');
      expect(result.current.getRiskLevel(75)).toBe('high');
      expect(result.current.getRiskLevel(90)).toBe('critical');
    });

    it('provides getDefinition helper', () => {
      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      const lowDef = result.current.getDefinition('low');
      expect(lowDef?.label).toBe('Low');
      expect(lowDef?.color).toBe('#22c55e');

      const criticalDef = result.current.getDefinition('critical');
      expect(criticalDef?.label).toBe('Critical');
      expect(criticalDef?.color).toBe('#ef4444');
    });

    it('provides getColor helper', () => {
      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      expect(result.current.getColor('low')).toBe('#22c55e');
      expect(result.current.getColor('medium')).toBe('#eab308');
      expect(result.current.getColor('high')).toBe('#f97316');
      expect(result.current.getColor('critical')).toBe('#ef4444');
    });

    it('provides loading state', () => {
      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.isRefetching).toBe(false);
    });

    it('provides error state when no errors', () => {
      const { result } = renderHook(() => useSeverity(), {
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
            return useSeverity();
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
        'useSeverity must be used within a SeverityProvider'
      );
    });
  });

  describe('useSeverityOptional', () => {
    it('returns data when within provider', () => {
      const { result } = renderHook(() => useSeverityOptional(), {
        wrapper: createWrapper(),
      });

      expect(result.current).not.toBeNull();
      expect(result.current?.thresholds).toEqual(mockSeverityMetadata.thresholds);
    });

    it('returns null when outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      const { result } = renderHook(() => useSeverityOptional(), {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      });

      expect(result.current).toBeNull();
    });
  });

  describe('loading states', () => {
    it('shows isLoading when hook is loading', () => {
      vi.mocked(useSeverityConfig).mockReturnValue({
        data: undefined,
        thresholds: DEFAULT_SEVERITY_THRESHOLDS,
        definitions: DEFAULT_SEVERITY_DEFINITIONS,
        isLoading: true,
        isRefetching: false,
        error: null,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        getRiskLevel: createMockGetRiskLevel(DEFAULT_SEVERITY_THRESHOLDS),
      });

      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('shows isRefetching when hook is refetching', () => {
      vi.mocked(useSeverityConfig).mockReturnValue({
        data: mockSeverityMetadata,
        thresholds: mockSeverityMetadata.thresholds,
        definitions: mockSeverityMetadata.definitions,
        isLoading: false,
        isRefetching: true,
        error: null,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        getRiskLevel: createMockGetRiskLevel(),
      });

      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isRefetching).toBe(true);
    });
  });

  describe('error states', () => {
    it('returns error from hook', () => {
      const severityError = new Error('Failed to fetch severity config');
      vi.mocked(useSeverityConfig).mockReturnValue({
        data: undefined,
        thresholds: DEFAULT_SEVERITY_THRESHOLDS,
        definitions: DEFAULT_SEVERITY_DEFINITIONS,
        isLoading: false,
        isRefetching: false,
        error: severityError,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        getRiskLevel: createMockGetRiskLevel(DEFAULT_SEVERITY_THRESHOLDS),
      });

      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBe(severityError);
    });
  });

  describe('refetch', () => {
    it('calls refetch on hook', async () => {
      const mockRefetch = vi.fn().mockResolvedValue(undefined);

      vi.mocked(useSeverityConfig).mockReturnValue({
        data: mockSeverityMetadata,
        thresholds: mockSeverityMetadata.thresholds,
        definitions: mockSeverityMetadata.definitions,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        refetch: mockRefetch,
        getRiskLevel: createMockGetRiskLevel(),
      });

      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
      });

      act(() => {
        void result.current.refetch();
      });

      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });
    });
  });

  describe('provider configuration', () => {
    it('passes enabled option to hook', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      function DisabledWrapper({ children }: { children: React.ReactNode }) {
        return (
          <QueryClientProvider client={queryClient}>
            <SeverityProvider enabled={false}>{children}</SeverityProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useSeverity(), {
        wrapper: DisabledWrapper,
      });

      expect(useSeverityConfig).toHaveBeenCalledWith({ enabled: false });
    });
  });

  describe('DEFAULT_SEVERITY_CONTEXT constant', () => {
    it('has expected structure', () => {
      expect(DEFAULT_SEVERITY_CONTEXT).toHaveProperty('thresholds');
      expect(DEFAULT_SEVERITY_CONTEXT).toHaveProperty('definitions');
      expect(DEFAULT_SEVERITY_CONTEXT).toHaveProperty('isLoading', false);
      expect(DEFAULT_SEVERITY_CONTEXT).toHaveProperty('error', null);
    });

    it('provides working getRiskLevel function', () => {
      expect(DEFAULT_SEVERITY_CONTEXT.getRiskLevel(15)).toBe('low');
      expect(DEFAULT_SEVERITY_CONTEXT.getRiskLevel(45)).toBe('medium');
      expect(DEFAULT_SEVERITY_CONTEXT.getRiskLevel(70)).toBe('high');
      expect(DEFAULT_SEVERITY_CONTEXT.getRiskLevel(95)).toBe('critical');
    });

    it('provides working getDefinition function', () => {
      const lowDef = DEFAULT_SEVERITY_CONTEXT.getDefinition('low');
      expect(lowDef?.label).toBe('Low');
    });

    it('provides working getColor function', () => {
      expect(DEFAULT_SEVERITY_CONTEXT.getColor('low')).toBe('#22c55e');
    });

    it('getRiskLevel throws for invalid scores', () => {
      expect(() => DEFAULT_SEVERITY_CONTEXT.getRiskLevel(-1)).toThrow(
        'Risk score must be between 0 and 100'
      );
      expect(() => DEFAULT_SEVERITY_CONTEXT.getRiskLevel(101)).toThrow(
        'Risk score must be between 0 and 100'
      );
    });
  });

  describe('custom thresholds', () => {
    it('uses custom thresholds from hook', () => {
      const customThresholds = { low_max: 20, medium_max: 50, high_max: 80 };
      vi.mocked(useSeverityConfig).mockReturnValue({
        data: { ...mockSeverityMetadata, thresholds: customThresholds },
        thresholds: customThresholds,
        definitions: mockSeverityMetadata.definitions,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        getRiskLevel: createMockGetRiskLevel(customThresholds),
      });

      const { result } = renderHook(() => useSeverity(), {
        wrapper: createWrapper(),
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
});
