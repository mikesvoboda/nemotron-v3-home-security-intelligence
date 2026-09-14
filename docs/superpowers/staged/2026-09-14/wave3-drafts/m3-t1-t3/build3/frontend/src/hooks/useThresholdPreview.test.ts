/**
 * Tests for useThresholdPreview hook.
 *
 * @see NEM-3604 Alert Threshold Configuration
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useThresholdPreview } from './useThresholdPreview';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  testAlertRule: vi.fn(),
}));

describe('useThresholdPreview', () => {
  const mockTestResponse: api.RuleTestResponse = {
    rule_id: 'rule-123',
    rule_name: 'Test Rule',
    events_tested: 100,
    events_matched: 25,
    match_rate: 25.0,
    results: [
      {
        event_id: 1,
        camera_id: 'cam-1',
        risk_score: 80,
        object_types: ['person'],
        matches: true,
        matched_conditions: ['risk_threshold'],
        started_at: '2025-01-01T00:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.testAlertRule).mockResolvedValue(mockTestResponse);
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Initial State', () => {
    it('should return initial state when not enabled', () => {
      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: null,
          threshold: 50,
        })
      );

      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.eventsMatched).toBeNull();
      expect(result.current.eventsTested).toBeNull();
      expect(result.current.matchRate).toBeNull();
      expect(result.current.testResponse).toBeNull();
    });

    it('should return initial state when ruleId is null', () => {
      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: null,
          threshold: 50,
          enabled: true,
        })
      );

      expect(result.current.isLoading).toBe(false);
      expect(result.current.eventsMatched).toBeNull();
    });
  });

  describe('API Integration', () => {
    it('should call testAlertRule with correct parameters after debounce', async () => {
      renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
          testLimit: 50,
          debounceMs: 10, // Use very short debounce for tests
        })
      );

      await waitFor(
        () => {
          expect(api.testAlertRule).toHaveBeenCalledWith('rule-123', { limit: 50 });
        },
        { timeout: 1000 }
      );
    });

    it('should update state with API response', async () => {
      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
          debounceMs: 10,
        })
      );

      await waitFor(
        () => {
          expect(result.current.eventsMatched).toBe(25);
          expect(result.current.eventsTested).toBe(100);
          expect(result.current.matchRate).toBe(25.0);
          expect(result.current.testResponse).toEqual(mockTestResponse);
        },
        { timeout: 1000 }
      );
    });
  });

  describe('Refresh Function', () => {
    it('should provide refresh function', () => {
      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
        })
      );

      expect(typeof result.current.refresh).toBe('function');
    });

    it('should trigger fetch on refresh', async () => {
      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
          debounceMs: 100000, // Long debounce
        })
      );

      // Refresh should bypass debounce
      act(() => {
        result.current.refresh();
      });

      await waitFor(
        () => {
          expect(api.testAlertRule).toHaveBeenCalledTimes(1);
        },
        { timeout: 1000 }
      );
    });

    it('should not call API on refresh if not enabled', () => {
      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: null,
          threshold: 70,
        })
      );

      act(() => {
        result.current.refresh();
      });

      expect(api.testAlertRule).not.toHaveBeenCalled();
    });
  });

  describe('Clear Function', () => {
    it('should provide clear function', () => {
      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
        })
      );

      expect(typeof result.current.clear).toBe('function');
    });

    it('should reset state on clear', async () => {
      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
          debounceMs: 10,
        })
      );

      // Wait for data to load
      await waitFor(
        () => {
          expect(result.current.eventsMatched).toBe(25);
        },
        { timeout: 1000 }
      );

      // Clear
      act(() => {
        result.current.clear();
      });

      expect(result.current.eventsMatched).toBeNull();
      expect(result.current.eventsTested).toBeNull();
      expect(result.current.matchRate).toBeNull();
      expect(result.current.error).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors', async () => {
      const errorMessage = 'Network error';
      vi.mocked(api.testAlertRule).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
          debounceMs: 10,
        })
      );

      await waitFor(
        () => {
          expect(result.current.error).toBe(errorMessage);
          expect(result.current.isLoading).toBe(false);
        },
        { timeout: 1000 }
      );
    });

    it('should handle non-Error rejection', async () => {
      vi.mocked(api.testAlertRule).mockRejectedValue('Unknown error');

      const { result } = renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
          debounceMs: 10,
        })
      );

      await waitFor(
        () => {
          expect(result.current.error).toBe('Failed to fetch preview');
        },
        { timeout: 1000 }
      );
    });
  });

  describe('Enabled Flag', () => {
    it('should not fetch when enabled is false', async () => {
      renderHook(() =>
        useThresholdPreview({
          ruleId: 'rule-123',
          threshold: 70,
          enabled: false,
          debounceMs: 10,
        })
      );

      // Wait a bit and verify no call was made
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(api.testAlertRule).not.toHaveBeenCalled();
    });
  });
});
