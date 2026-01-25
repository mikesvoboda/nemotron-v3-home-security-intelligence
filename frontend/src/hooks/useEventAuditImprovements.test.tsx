/**
 * Tests for useEventAuditImprovements hook
 *
 * @see hooks/useEventAuditImprovements.ts
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useEventAuditImprovements } from './useEventAuditImprovements';
import { fetchEventAudit } from '../services/auditApi';
import { CONSISTENCY_THRESHOLD } from '../types/aiAuditImprovements';

import type { ReactNode } from 'react';

// ============================================================================
// Mocks
// ============================================================================

// Mock the API
vi.mock('../services/auditApi', () => ({
  fetchEventAudit: vi.fn(),
}));

const mockFetchEventAudit = vi.mocked(fetchEventAudit);

// ============================================================================
// Test Utilities
// ============================================================================

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function createMockAuditData(overrides = {}) {
  return {
    id: 1,
    event_id: 100,
    audited_at: '2024-01-15T10:00:00Z',
    is_fully_evaluated: true,
    contributions: {
      rtdetr: true,
      florence: true,
      clip: false,
      violence: false,
      clothing: false,
      vehicle: false,
      pet: false,
      weather: false,
      image_quality: false,
      zones: false,
      baseline: false,
      cross_camera: false,
    },
    prompt_length: 5000,
    prompt_token_estimate: 1250,
    enrichment_utilization: 0.85,
    scores: {
      context_usage: 4,
      reasoning_coherence: 4,
      risk_justification: 5,
      consistency: 4,
      overall: 4.25,
    },
    consistency_risk_score: 75,
    consistency_diff: 5,
    self_eval_critique: 'The analysis was comprehensive but could improve context usage.',
    improvements: {
      missing_context: ['Add time-of-day context', 'Include weather conditions'],
      confusing_sections: ['Risk calculation explanation'],
      unused_data: [],
      format_suggestions: ['Use bullet points for recommendations'],
      model_gaps: ['Consider adding motion detection data'],
    },
    ...overrides,
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('useEventAuditImprovements', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createQueryClient();
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('should return loading state initially', () => {
      mockFetchEventAudit.mockReturnValue(new Promise(() => {})); // Never resolves

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.hasAuditData).toBe(false);
      expect(result.current.selfEvaluation).toBeNull();
      expect(result.current.improvements).toBeNull();
      expect(result.current.critique).toBeNull();
    });

    it('should be disabled when eventId is undefined', () => {
      const { result } = renderHook(() => useEventAuditImprovements(undefined), {
        wrapper: createWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.hasAuditData).toBe(false);
      expect(mockFetchEventAudit).not.toHaveBeenCalled();
    });
  });

  describe('with successful data', () => {
    it('should return processed data when fetch succeeds', async () => {
      const mockData = createMockAuditData();
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasAuditData).toBe(true);
      expect(result.current.critique).toBe(mockData.self_eval_critique);
      expect(result.current.isFullyEvaluated).toBe(true);
    });

    it('should process improvements correctly', async () => {
      const mockData = createMockAuditData();
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.improvements).not.toBeNull();
      });

      const improvements = result.current.improvements!;
      expect(improvements.hasImprovements).toBe(true);
      expect(improvements.totalCount).toBe(5); // 2 + 1 + 0 + 1 + 1
      expect(improvements.countByCategory.missing_context).toBe(2);
      expect(improvements.countByCategory.confusing_sections).toBe(1);
      expect(improvements.countByCategory.unused_data).toBe(0);
    });

    it('should process consistency check correctly', async () => {
      const mockData = createMockAuditData({
        consistency_risk_score: 75,
        consistency_diff: 5,
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.consistency).not.toBeNull();
      });

      const consistency = result.current.consistency!;
      expect(consistency.riskScore).toBe(75);
      expect(consistency.diff).toBe(5);
      expect(consistency.passed).toBe(true);
    });

    it('should mark consistency as failed when diff exceeds threshold', async () => {
      const mockData = createMockAuditData({
        consistency_risk_score: 80,
        consistency_diff: CONSISTENCY_THRESHOLD + 5,
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.consistency).not.toBeNull();
      });

      expect(result.current.consistency!.passed).toBe(false);
    });
  });

  describe('convenience methods', () => {
    it('getImprovementsByCategory should return correct items', async () => {
      const mockData = createMockAuditData();
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.hasAuditData).toBe(true);
      });

      const missingContext = result.current.getImprovementsByCategory('missing_context');
      expect(missingContext).toHaveLength(2);
      expect(missingContext).toContain('Add time-of-day context');
      expect(missingContext).toContain('Include weather conditions');

      const unusedData = result.current.getImprovementsByCategory('unused_data');
      expect(unusedData).toHaveLength(0);
    });

    it('hasCategoryImprovements should return correct boolean', async () => {
      const mockData = createMockAuditData();
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.hasAuditData).toBe(true);
      });

      expect(result.current.hasCategoryImprovements('missing_context')).toBe(true);
      expect(result.current.hasCategoryImprovements('unused_data')).toBe(false);
    });

    it('getHighPriorityImprovements should sort by category count', async () => {
      const mockData = createMockAuditData({
        improvements: {
          missing_context: ['Item 1', 'Item 2', 'Item 3'], // 3 items
          confusing_sections: ['Item 1'], // 1 item
          unused_data: [],
          format_suggestions: ['Item 1', 'Item 2'], // 2 items
          model_gaps: [],
        },
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.hasAuditData).toBe(true);
      });

      const prioritized = result.current.getHighPriorityImprovements();

      // First items should be from missing_context (3 items = highest priority)
      expect(prioritized[0].category).toBe('missing_context');
      expect(prioritized[1].category).toBe('missing_context');
      expect(prioritized[2].category).toBe('missing_context');

      // Next should be from format_suggestions (2 items)
      expect(prioritized[3].category).toBe('format_suggestions');
      expect(prioritized[4].category).toBe('format_suggestions');

      // Last should be from confusing_sections (1 item)
      expect(prioritized[5].category).toBe('confusing_sections');
    });
  });

  describe('processed evaluation', () => {
    it('should set evaluationQuality to good for passing evaluation', async () => {
      const mockData = createMockAuditData({
        is_fully_evaluated: true,
        consistency_diff: 5,
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.processed).not.toBeNull();
      });

      expect(result.current.processed!.evaluationQuality).toBe('good');
    });

    it('should set evaluationQuality to needs_improvement for failing evaluation', async () => {
      const mockData = createMockAuditData({
        is_fully_evaluated: true,
        consistency_diff: 15,
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.processed).not.toBeNull();
      });

      expect(result.current.processed!.evaluationQuality).toBe('needs_improvement');
    });

    it('should set evaluationQuality to not_evaluated for incomplete evaluation', async () => {
      const mockData = createMockAuditData({
        is_fully_evaluated: false,
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.processed).not.toBeNull();
      });

      expect(result.current.processed!.evaluationQuality).toBe('not_evaluated');
    });
  });

  describe('edge cases', () => {
    it('should handle null improvements gracefully', async () => {
      const mockData = createMockAuditData({
        improvements: {
          missing_context: [],
          confusing_sections: [],
          unused_data: [],
          format_suggestions: [],
          model_gaps: [],
        },
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.improvements).not.toBeNull();
      });

      expect(result.current.improvements!.hasImprovements).toBe(false);
      expect(result.current.improvements!.totalCount).toBe(0);
    });

    it('should handle null critique', async () => {
      const mockData = createMockAuditData({
        self_eval_critique: null,
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.hasAuditData).toBe(true);
      });

      expect(result.current.critique).toBeNull();
    });

    it('should handle null consistency values', async () => {
      const mockData = createMockAuditData({
        consistency_risk_score: null,
        consistency_diff: null,
      });
      mockFetchEventAudit.mockResolvedValue(mockData);

      const { result } = renderHook(() => useEventAuditImprovements(100), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.consistency).not.toBeNull();
      });

      expect(result.current.consistency!.riskScore).toBeNull();
      expect(result.current.consistency!.diff).toBeNull();
      expect(result.current.consistency!.passed).toBe(true); // null = passed
    });
  });
});
