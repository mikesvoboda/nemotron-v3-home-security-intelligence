/**
 * Tests for useCostAnalyticsQuery hook
 *
 * Part of NEM-5024 Phase 2: Cost Analytics Dashboard.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import {
  useCostAnalyticsQuery,
  useCostTrendsQuery,
  costAnalyticsQueryKeys,
} from './useCostAnalyticsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { CostAnalyticsResponse, CostTrendResponse } from '../types/costAnalytics';

// Mock the API functions
vi.mock('../services/api', () => ({
  fetchCostAnalytics: vi.fn(),
  fetchCostTrends: vi.fn(),
}));

describe('useCostAnalyticsQuery', () => {
  const mockCostAnalyticsResponse: CostAnalyticsResponse = {
    today: {
      date: '2026-01-31',
      total_cost_usd: 0.0523,
      token_cost_usd: 0.0315,
      gpu_cost_usd: 0.0208,
      event_count: 25,
      detection_count: 150,
    },
    daily_budget: {
      period: 'daily',
      limit_usd: 1.0,
      used_usd: 0.0523,
      remaining_usd: 0.9477,
      utilization_ratio: 0.0523,
      exceeded: false,
      warning_reached: false,
    },
    monthly_budget: {
      period: 'monthly',
      limit_usd: 25.0,
      used_usd: 1.569,
      remaining_usd: 23.431,
      utilization_ratio: 0.06276,
      exceeded: false,
      warning_reached: false,
    },
    token_usage: {
      input_tokens: 15000,
      output_tokens: 5000,
      total_tokens: 20000,
      token_cost_usd: 0.075,
    },
    cost_by_model: [
      {
        model: 'nemotron',
        cost_usd: 0.0234,
        gpu_seconds: 125.5,
        request_count: 42,
      },
    ],
    efficiency: {
      cost_per_detection_usd: 0.00002,
      cost_per_event_usd: 0.0021,
      total_detections: 15000,
      total_events: 250,
    },
    cost_history: [
      {
        date: '2026-01-30',
        total_cost_usd: 0.045,
        token_cost_usd: 0.028,
        gpu_cost_usd: 0.017,
        event_count: 22,
        detection_count: 140,
      },
    ],
    pricing: {
      input_cost_per_1k_tokens: 0.003,
      output_cost_per_1k_tokens: 0.006,
      gpu_cost_per_second: 0.000139,
      detection_cost_per_image: 0.00002,
      enrichment_cost_per_operation: 0.00001,
    },
    last_updated: '2026-01-31T12:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('query keys', () => {
    it('should have correct structure for all keys', () => {
      expect(costAnalyticsQueryKeys.all).toEqual(['analytics', 'costs']);
      expect(costAnalyticsQueryKeys.summary()).toEqual(['analytics', 'costs', 'summary']);
      expect(costAnalyticsQueryKeys.trends.all).toEqual(['analytics', 'costs', 'trends']);
    });

    it('should create unique keys for different date ranges', () => {
      const key1 = costAnalyticsQueryKeys.trends.byDateRange({
        start_date: '2026-01-01',
        end_date: '2026-01-31',
      });
      const key2 = costAnalyticsQueryKeys.trends.byDateRange({
        start_date: '2026-02-01',
        end_date: '2026-02-28',
      });

      expect(key1).not.toEqual(key2);
      expect(key1[0]).toBe('analytics');
      expect(key1[1]).toBe('costs');
      expect(key1[2]).toBe('trends');
    });
  });

  describe('useCostAnalyticsQuery', () => {
    it('should fetch cost analytics data', async () => {
      vi.mocked(api.fetchCostAnalytics).mockResolvedValue(mockCostAnalyticsResponse);

      const { result } = renderHook(() => useCostAnalyticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();

      // Wait for data
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockCostAnalyticsResponse);
      expect(result.current.error).toBeNull();
    });

    it('should provide derived values', async () => {
      vi.mocked(api.fetchCostAnalytics).mockResolvedValue(mockCostAnalyticsResponse);

      const { result } = renderHook(() => useCostAnalyticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Check derived values
      expect(result.current.todayCost).toEqual(mockCostAnalyticsResponse.today);
      expect(result.current.dailyBudget).toEqual(mockCostAnalyticsResponse.daily_budget);
      expect(result.current.monthlyBudget).toEqual(mockCostAnalyticsResponse.monthly_budget);
      expect(result.current.costHistory).toEqual(mockCostAnalyticsResponse.cost_history);
      expect(result.current.todayTotalCost).toBe(0.0523);
      expect(result.current.dailyUtilizationRatio).toBe(0.0523);
      expect(result.current.monthlyUtilizationRatio).toBe(0.06276);
    });

    it('should handle API errors', async () => {
      const error = new Error('API Error');
      vi.mocked(api.fetchCostAnalytics).mockRejectedValue(error);

      const { result } = renderHook(() => useCostAnalyticsQuery({ retry: false }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toEqual(error);
      expect(result.current.data).toBeUndefined();
    });

    it('should respect enabled option', () => {
      const { result } = renderHook(() => useCostAnalyticsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      // Should not fetch when disabled
      expect(api.fetchCostAnalytics).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('should provide default values when data is not loaded', () => {
      vi.mocked(api.fetchCostAnalytics).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useCostAnalyticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.costHistory).toEqual([]);
      expect(result.current.todayTotalCost).toBe(0);
      expect(result.current.dailyUtilizationRatio).toBe(0);
      expect(result.current.monthlyUtilizationRatio).toBe(0);
    });
  });

  describe('useCostTrendsQuery', () => {
    const mockTrendResponse: CostTrendResponse = {
      data_points: [
        { date: '2026-01-30', cost_usd: 0.045 },
        { date: '2026-01-31', cost_usd: 0.052 },
      ],
      total_cost_usd: 0.097,
      start_date: '2026-01-30',
      end_date: '2026-01-31',
    };

    const validParams = {
      start_date: '2026-01-30',
      end_date: '2026-01-31',
    };

    it('should fetch cost trends data', async () => {
      vi.mocked(api.fetchCostTrends).mockResolvedValue(mockTrendResponse);

      const { result } = renderHook(() => useCostTrendsQuery(validParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockTrendResponse);
      expect(result.current.dataPoints).toEqual(mockTrendResponse.data_points);
      expect(result.current.totalCost).toBe(0.097);
    });

    it('should not fetch with invalid params', () => {
      const { result } = renderHook(
        () => useCostTrendsQuery({ start_date: '', end_date: '' }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      expect(api.fetchCostTrends).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('should handle API errors', async () => {
      const error = new Error('Trend API Error');
      vi.mocked(api.fetchCostTrends).mockRejectedValue(error);

      const { result } = renderHook(() => useCostTrendsQuery(validParams, { retry: false }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toEqual(error);
    });

    it('should provide default values when data is not loaded', () => {
      vi.mocked(api.fetchCostTrends).mockImplementation(() => new Promise(() => {}));

      const { result } = renderHook(() => useCostTrendsQuery(validParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.dataPoints).toEqual([]);
      expect(result.current.totalCost).toBe(0);
    });
  });
});
