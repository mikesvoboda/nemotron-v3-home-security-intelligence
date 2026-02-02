/**
 * Tests for CostAnalyticsDashboard component
 *
 * Part of NEM-5024 Phase 2: Cost Analytics Dashboard.
 *
 * Tests cover:
 * - Rendering with cost analytics data
 * - Loading state
 * - Error state
 * - Empty state
 * - Budget utilization display
 * - Cost trend chart
 * - Model cost breakdown
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CostAnalyticsDashboard from './CostAnalyticsDashboard';
import * as useCostAnalyticsQueryModule from '../../hooks/useCostAnalyticsQuery';

import type { CostAnalyticsResponse } from '../../types/costAnalytics';

// Mock the hook
vi.mock('../../hooks/useCostAnalyticsQuery', () => ({
  useCostAnalyticsQuery: vi.fn(),
}));

describe('CostAnalyticsDashboard', () => {
  const mockCostAnalyticsData: CostAnalyticsResponse = {
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
      {
        model: 'yolo26',
        cost_usd: 0.0189,
        gpu_seconds: 80.3,
        request_count: 150,
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
        date: '2026-01-29',
        total_cost_usd: 0.042,
        token_cost_usd: 0.025,
        gpu_cost_usd: 0.017,
        event_count: 20,
        detection_count: 130,
      },
      {
        date: '2026-01-30',
        total_cost_usd: 0.045,
        token_cost_usd: 0.028,
        gpu_cost_usd: 0.017,
        event_count: 22,
        detection_count: 140,
      },
      {
        date: '2026-01-31',
        total_cost_usd: 0.0523,
        token_cost_usd: 0.0315,
        gpu_cost_usd: 0.0208,
        event_count: 25,
        detection_count: 150,
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

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering with data', () => {
    beforeEach(() => {
      vi.mocked(useCostAnalyticsQueryModule.useCostAnalyticsQuery).mockReturnValue({
        data: mockCostAnalyticsData,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
        todayCost: mockCostAnalyticsData.today,
        dailyBudget: mockCostAnalyticsData.daily_budget,
        monthlyBudget: mockCostAnalyticsData.monthly_budget,
        costHistory: mockCostAnalyticsData.cost_history,
        todayTotalCost: mockCostAnalyticsData.today.total_cost_usd,
        dailyUtilizationRatio: mockCostAnalyticsData.daily_budget.utilization_ratio,
        monthlyUtilizationRatio: mockCostAnalyticsData.monthly_budget.utilization_ratio,
      });
    });

    it('renders the dashboard container', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('cost-analytics-dashboard')).toBeInTheDocument();
    });

    it('renders the page title', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByText('Cost Analytics')).toBeInTheDocument();
    });

    it('renders today\'s total cost metric', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('metric-today-total')).toBeInTheDocument();
      expect(screen.getByText('Today\'s Total')).toBeInTheDocument();
    });

    it('renders token costs metric', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('metric-token-costs')).toBeInTheDocument();
      expect(screen.getByText('Token Costs')).toBeInTheDocument();
      expect(screen.getByText(/20,000 tokens/)).toBeInTheDocument();
    });

    it('renders GPU costs metric', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('metric-gpu-costs')).toBeInTheDocument();
      expect(screen.getByText('GPU Costs')).toBeInTheDocument();
    });

    it('renders cost per event metric', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('metric-cost-per-event')).toBeInTheDocument();
      expect(screen.getByText('Cost per Event')).toBeInTheDocument();
    });

    it('renders daily budget gauge', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('budget-gauge-daily')).toBeInTheDocument();
      expect(screen.getByText('Daily Budget')).toBeInTheDocument();
    });

    it('renders monthly budget gauge', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('budget-gauge-monthly')).toBeInTheDocument();
      expect(screen.getByText('Monthly Budget')).toBeInTheDocument();
    });

    it('renders cost trend chart', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('cost-trend-chart')).toBeInTheDocument();
      expect(screen.getByText('Cost Trends (30 Days)')).toBeInTheDocument();
    });

    it('renders model cost breakdown chart', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('model-breakdown-chart')).toBeInTheDocument();
      expect(screen.getByText('Cost by Model')).toBeInTheDocument();
    });

    it('renders pricing configuration', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('pricing-info')).toBeInTheDocument();
      expect(screen.getByText('Pricing Configuration')).toBeInTheDocument();
      expect(screen.getByText('Input Tokens')).toBeInTheDocument();
      expect(screen.getByText('Output Tokens')).toBeInTheDocument();
      expect(screen.getByText('GPU Time')).toBeInTheDocument();
    });

    it('shows "On Track" badge when under budget', () => {
      render(<CostAnalyticsDashboard />);
      const onTrackBadges = screen.getAllByText('On Track');
      expect(onTrackBadges.length).toBeGreaterThanOrEqual(2); // Daily and monthly
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(useCostAnalyticsQueryModule.useCostAnalyticsQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
        todayCost: undefined,
        dailyBudget: undefined,
        monthlyBudget: undefined,
        costHistory: [],
        todayTotalCost: 0,
        dailyUtilizationRatio: 0,
        monthlyUtilizationRatio: 0,
      });
    });

    it('shows loading skeleton when isLoading is true', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('cost-analytics-loading')).toBeInTheDocument();
    });

    it('does not show main dashboard during loading', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.queryByTestId('cost-analytics-dashboard')).not.toBeInTheDocument();
    });
  });

  describe('error state', () => {
    beforeEach(() => {
      vi.mocked(useCostAnalyticsQueryModule.useCostAnalyticsQuery).mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to fetch cost data'),
        isError: true,
        refetch: vi.fn(),
        todayCost: undefined,
        dailyBudget: undefined,
        monthlyBudget: undefined,
        costHistory: [],
        todayTotalCost: 0,
        dailyUtilizationRatio: 0,
        monthlyUtilizationRatio: 0,
      });
    });

    it('shows error message when error occurs', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('cost-analytics-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to Load Cost Analytics')).toBeInTheDocument();
      expect(screen.getByText('Failed to fetch cost data')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    beforeEach(() => {
      vi.mocked(useCostAnalyticsQueryModule.useCostAnalyticsQuery).mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
        todayCost: undefined,
        dailyBudget: undefined,
        monthlyBudget: undefined,
        costHistory: [],
        todayTotalCost: 0,
        dailyUtilizationRatio: 0,
        monthlyUtilizationRatio: 0,
      });
    });

    it('shows empty state when no data is available', () => {
      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('cost-analytics-empty')).toBeInTheDocument();
      expect(screen.getByText('No Cost Data Available')).toBeInTheDocument();
    });
  });

  describe('budget exceeded warning', () => {
    it('shows warning when daily budget is exceeded', () => {
      vi.mocked(useCostAnalyticsQueryModule.useCostAnalyticsQuery).mockReturnValue({
        data: {
          ...mockCostAnalyticsData,
          daily_budget: {
            ...mockCostAnalyticsData.daily_budget,
            exceeded: true,
            utilization_ratio: 1.2,
          },
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
        todayCost: mockCostAnalyticsData.today,
        dailyBudget: {
          ...mockCostAnalyticsData.daily_budget,
          exceeded: true,
          utilization_ratio: 1.2,
        },
        monthlyBudget: mockCostAnalyticsData.monthly_budget,
        costHistory: mockCostAnalyticsData.cost_history,
        todayTotalCost: mockCostAnalyticsData.today.total_cost_usd,
        dailyUtilizationRatio: 1.2,
        monthlyUtilizationRatio: mockCostAnalyticsData.monthly_budget.utilization_ratio,
      });

      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('budget-exceeded-warning')).toBeInTheDocument();
      expect(screen.getByText('Budget Exceeded')).toBeInTheDocument();
    });

    it('shows warning badge when budget threshold reached', () => {
      vi.mocked(useCostAnalyticsQueryModule.useCostAnalyticsQuery).mockReturnValue({
        data: {
          ...mockCostAnalyticsData,
          daily_budget: {
            ...mockCostAnalyticsData.daily_budget,
            warning_reached: true,
            utilization_ratio: 0.85,
          },
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
        todayCost: mockCostAnalyticsData.today,
        dailyBudget: {
          ...mockCostAnalyticsData.daily_budget,
          warning_reached: true,
          utilization_ratio: 0.85,
        },
        monthlyBudget: mockCostAnalyticsData.monthly_budget,
        costHistory: mockCostAnalyticsData.cost_history,
        todayTotalCost: mockCostAnalyticsData.today.total_cost_usd,
        dailyUtilizationRatio: 0.85,
        monthlyUtilizationRatio: mockCostAnalyticsData.monthly_budget.utilization_ratio,
      });

      render(<CostAnalyticsDashboard />);
      expect(screen.getByText('Warning')).toBeInTheDocument();
    });
  });

  describe('empty model breakdown', () => {
    it('shows empty state for model breakdown when no data', () => {
      vi.mocked(useCostAnalyticsQueryModule.useCostAnalyticsQuery).mockReturnValue({
        data: {
          ...mockCostAnalyticsData,
          cost_by_model: [],
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
        todayCost: mockCostAnalyticsData.today,
        dailyBudget: mockCostAnalyticsData.daily_budget,
        monthlyBudget: mockCostAnalyticsData.monthly_budget,
        costHistory: mockCostAnalyticsData.cost_history,
        todayTotalCost: mockCostAnalyticsData.today.total_cost_usd,
        dailyUtilizationRatio: mockCostAnalyticsData.daily_budget.utilization_ratio,
        monthlyUtilizationRatio: mockCostAnalyticsData.monthly_budget.utilization_ratio,
      });

      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('model-breakdown-empty')).toBeInTheDocument();
      expect(screen.getByText('No model cost data available')).toBeInTheDocument();
    });
  });

  describe('empty cost history', () => {
    it('shows empty state for cost trends when no history', () => {
      vi.mocked(useCostAnalyticsQueryModule.useCostAnalyticsQuery).mockReturnValue({
        data: {
          ...mockCostAnalyticsData,
          cost_history: [],
        },
        isLoading: false,
        isRefetching: false,
        error: null,
        isError: false,
        refetch: vi.fn(),
        todayCost: mockCostAnalyticsData.today,
        dailyBudget: mockCostAnalyticsData.daily_budget,
        monthlyBudget: mockCostAnalyticsData.monthly_budget,
        costHistory: [],
        todayTotalCost: mockCostAnalyticsData.today.total_cost_usd,
        dailyUtilizationRatio: mockCostAnalyticsData.daily_budget.utilization_ratio,
        monthlyUtilizationRatio: mockCostAnalyticsData.monthly_budget.utilization_ratio,
      });

      render(<CostAnalyticsDashboard />);
      expect(screen.getByTestId('cost-trend-empty')).toBeInTheDocument();
      expect(screen.getByText('No cost history available')).toBeInTheDocument();
    });
  });
});
