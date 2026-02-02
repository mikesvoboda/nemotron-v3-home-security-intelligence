/**
 * CostAnalyticsDashboard - Cost Analytics Dashboard Component
 *
 * Displays comprehensive cost analytics including:
 * - Token costs and GPU costs
 * - Per-event cost breakdown
 * - Daily and monthly budget utilization gauges
 * - Cost trend charts over time
 *
 * Part of NEM-5024 Phase 2: Cost Analytics Dashboard.
 */

import {
  Card,
  Title,
  Text,
  AreaChart,
  DonutChart,
  ProgressBar,
  Metric,
  Flex,
  Grid,
  Col,
  Badge,
  BarList,
} from '@tremor/react';
import {
  AlertCircle,
  DollarSign,
  Cpu,
  Coins,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
} from 'lucide-react';
import { useMemo } from 'react';

import { useCostAnalyticsQuery } from '../../hooks/useCostAnalyticsQuery';

import type { DailyCostEntry, ModelCostBreakdown } from '../../types/costAnalytics';

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format a cost value to display with appropriate precision.
 */
function formatCost(value: number, precision: number = 4): string {
  if (value === 0) return '$0.00';
  if (value < 0.0001) return `$${value.toExponential(2)}`;
  if (value < 0.01) return `$${value.toFixed(precision)}`;
  return `$${value.toFixed(2)}`;
}

/**
 * Format a date string for display.
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Valid Tremor colors */
type TremorColor = 'rose' | 'amber' | 'yellow' | 'emerald' | 'blue' | 'violet';

/**
 * Get color based on budget utilization ratio.
 */
function getUtilizationColor(ratio: number): TremorColor {
  if (ratio >= 1.0) return 'rose';
  if (ratio >= 0.8) return 'amber';
  if (ratio >= 0.5) return 'yellow';
  return 'emerald';
}

/**
 * Get badge color based on utilization status.
 */
function getBadgeColor(exceeded: boolean, warningReached: boolean): 'red' | 'yellow' | 'green' {
  if (exceeded) return 'red';
  if (warningReached) return 'yellow';
  return 'green';
}

// ============================================================================
// Sub-Components
// ============================================================================

interface BudgetGaugeProps {
  title: string;
  period: string;
  usedUsd: number;
  limitUsd: number;
  utilizationRatio: number;
  exceeded: boolean;
  warningReached: boolean;
}

function BudgetGauge({
  title,
  period,
  usedUsd,
  limitUsd,
  utilizationRatio,
  exceeded,
  warningReached,
}: BudgetGaugeProps) {
  const percentUsed = Math.min(utilizationRatio * 100, 100);
  const color = getUtilizationColor(utilizationRatio);

  return (
    <Card data-testid={`budget-gauge-${period}`}>
      <Flex justifyContent="between" alignItems="center">
        <Title>{title}</Title>
        <Badge color={getBadgeColor(exceeded, warningReached)}>
          {exceeded ? 'Exceeded' : warningReached ? 'Warning' : 'On Track'}
        </Badge>
      </Flex>

      <Metric className="mt-2">{formatCost(usedUsd)}</Metric>
      <Text className="text-gray-400">
        of {limitUsd > 0 ? formatCost(limitUsd) : 'unlimited'} budget
      </Text>

      {limitUsd > 0 && (
        <>
          <ProgressBar
            value={percentUsed}
            color={color}
            className="mt-4"
            data-testid={`budget-progress-${period}`}
          />
          <Text className="mt-2 text-gray-400">
            {percentUsed.toFixed(1)}% utilized
            {utilizationRatio > 1 && (
              <span className="ml-2 text-red-400">
                ({((utilizationRatio - 1) * 100).toFixed(1)}% over)
              </span>
            )}
          </Text>
        </>
      )}
    </Card>
  );
}

interface CostMetricCardProps {
  title: string;
  value: number;
  subtitle: string;
  icon: React.ReactNode;
  trend?: number;
  testId: string;
}

function CostMetricCard({ title, value, subtitle, icon, trend, testId }: CostMetricCardProps) {
  return (
    <Card data-testid={testId}>
      <Flex justifyContent="start" className="gap-3">
        <div className="rounded-lg bg-gray-800 p-2">{icon}</div>
        <div>
          <Text className="text-gray-400">{title}</Text>
          <Metric>{formatCost(value)}</Metric>
        </div>
      </Flex>
      <Flex justifyContent="between" className="mt-4">
        <Text className="text-gray-400">{subtitle}</Text>
        {trend !== undefined && (
          <Flex justifyContent="end" className="gap-1">
            {trend >= 0 ? (
              <TrendingUp className="h-4 w-4 text-emerald-500" />
            ) : (
              <TrendingDown className="h-4 w-4 text-rose-500" />
            )}
            <Text className={trend >= 0 ? 'text-emerald-500' : 'text-rose-500'}>
              {Math.abs(trend).toFixed(1)}%
            </Text>
          </Flex>
        )}
      </Flex>
    </Card>
  );
}

interface CostTrendChartProps {
  data: DailyCostEntry[];
}

function CostTrendChart({ data }: CostTrendChartProps) {
  const chartData = useMemo(() => {
    return data.map((entry) => ({
      date: formatDate(entry.date),
      'Total Cost': entry.total_cost_usd,
      'Token Cost': entry.token_cost_usd,
      'GPU Cost': entry.gpu_cost_usd,
    }));
  }, [data]);

  if (data.length === 0) {
    return (
      <Card data-testid="cost-trend-empty">
        <Title>Cost Trends</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <TrendingUp className="mb-2 h-8 w-8" />
          <Text>No cost history available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="cost-trend-chart">
      <Title>Cost Trends (30 Days)</Title>
      <Text className="text-gray-400">Daily cost breakdown</Text>
      <AreaChart
        className="mt-4 h-72"
        data={chartData}
        index="date"
        categories={['Total Cost', 'Token Cost', 'GPU Cost']}
        colors={['emerald', 'blue', 'amber']}
        showLegend={true}
        showGridLines={false}
        curveType="monotone"
        valueFormatter={(value) => formatCost(value)}
      />
    </Card>
  );
}

interface ModelCostBreakdownChartProps {
  data: ModelCostBreakdown[];
}

function ModelCostBreakdownChart({ data }: ModelCostBreakdownChartProps) {
  const chartData = useMemo(() => {
    return data.map((model) => ({
      name: model.model,
      value: model.cost_usd,
    }));
  }, [data]);

  const barListData = useMemo(() => {
    return data
      .sort((a, b) => b.cost_usd - a.cost_usd)
      .map((model) => ({
        name: model.model,
        value: model.cost_usd,
        icon: () => <Cpu className="h-4 w-4 text-gray-400" />,
      }));
  }, [data]);

  if (data.length === 0) {
    return (
      <Card data-testid="model-breakdown-empty">
        <Title>Cost by Model</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <Cpu className="mb-2 h-8 w-8" />
          <Text>No model cost data available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="model-breakdown-chart">
      <Title>Cost by Model</Title>
      <Text className="text-gray-400">Today&apos;s cost distribution</Text>
      <Grid numItemsMd={2} className="mt-4 gap-4">
        <Col>
          <DonutChart
            data={chartData}
            category="value"
            index="name"
            colors={['emerald', 'blue', 'amber', 'rose', 'violet']}
            valueFormatter={(value) => formatCost(value)}
            className="h-40"
          />
        </Col>
        <Col>
          <BarList data={barListData} valueFormatter={(value: number) => formatCost(value)} />
        </Col>
      </Grid>
    </Card>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * CostAnalyticsDashboard displays comprehensive cost analytics.
 */
export default function CostAnalyticsDashboard() {
  const {
    data,
    isLoading,
    error,
    todayCost,
    dailyBudget,
    monthlyBudget,
    costHistory,
  } = useCostAnalyticsQuery({
    refetchInterval: 60000, // Refresh every minute
  });

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6 p-6" data-testid="cost-analytics-loading">
        {/* Header skeleton */}
        <div className="mb-8">
          <div className="h-8 w-64 animate-pulse rounded-lg bg-gray-800"></div>
          <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
        </div>

        {/* Cards skeleton */}
        <Grid numItemsMd={2} numItemsLg={4} className="gap-6">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <div className="h-24 animate-pulse rounded-lg bg-gray-800"></div>
            </Card>
          ))}
        </Grid>

        {/* Chart skeleton */}
        <Card>
          <div className="h-72 animate-pulse rounded-lg bg-gray-800"></div>
        </Card>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-6" data-testid="cost-analytics-error">
        <Card>
          <div className="flex flex-col items-center justify-center py-12 text-red-400">
            <AlertCircle className="mb-4 h-12 w-12" />
            <Title>Failed to Load Cost Analytics</Title>
            <Text className="mt-2">{error.message}</Text>
          </div>
        </Card>
      </div>
    );
  }

  // No data state
  if (!data) {
    return (
      <div className="p-6" data-testid="cost-analytics-empty">
        <Card>
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <DollarSign className="mb-4 h-12 w-12" />
            <Title>No Cost Data Available</Title>
            <Text className="mt-2">Cost tracking will appear once inference requests are made.</Text>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6" data-testid="cost-analytics-dashboard">
      {/* Header */}
      <div className="flex items-center gap-3">
        <DollarSign className="h-8 w-8 text-[#76B900]" />
        <div>
          <h1 className="text-2xl font-bold text-white">Cost Analytics</h1>
          <Text className="text-gray-400">
            Track AI inference costs, token usage, and budget utilization
          </Text>
        </div>
      </div>

      {/* Budget Exceeded Warning */}
      {(dailyBudget?.exceeded || monthlyBudget?.exceeded) && (
        <Card className="border-red-500 bg-red-500/10" data-testid="budget-exceeded-warning">
          <Flex justifyContent="start" className="gap-3">
            <AlertTriangle className="h-6 w-6 text-red-400" />
            <div>
              <Title className="text-red-400">Budget Exceeded</Title>
              <Text className="text-red-300">
                {dailyBudget?.exceeded && 'Daily budget has been exceeded. '}
                {monthlyBudget?.exceeded && 'Monthly budget has been exceeded.'}
              </Text>
            </div>
          </Flex>
        </Card>
      )}

      {/* Summary Metrics */}
      <Grid numItemsMd={2} numItemsLg={4} className="gap-6">
        <CostMetricCard
          title="Today's Total"
          value={todayCost?.total_cost_usd ?? 0}
          subtitle={`${todayCost?.event_count ?? 0} events analyzed`}
          icon={<DollarSign className="h-5 w-5 text-emerald-500" />}
          testId="metric-today-total"
        />
        <CostMetricCard
          title="Token Costs"
          value={data.token_usage.token_cost_usd}
          subtitle={`${data.token_usage.total_tokens.toLocaleString()} tokens`}
          icon={<Coins className="h-5 w-5 text-blue-500" />}
          testId="metric-token-costs"
        />
        <CostMetricCard
          title="GPU Costs"
          value={todayCost?.gpu_cost_usd ?? 0}
          subtitle={`${todayCost?.detection_count ?? 0} detections`}
          icon={<Cpu className="h-5 w-5 text-amber-500" />}
          testId="metric-gpu-costs"
        />
        <CostMetricCard
          title="Cost per Event"
          value={data.efficiency.cost_per_event_usd}
          subtitle={`${data.efficiency.total_events.toLocaleString()} total events`}
          icon={<TrendingUp className="h-5 w-5 text-violet-500" />}
          testId="metric-cost-per-event"
        />
      </Grid>

      {/* Budget Gauges */}
      <Grid numItemsMd={2} className="gap-6">
        {dailyBudget && (
          <BudgetGauge
            title="Daily Budget"
            period="daily"
            usedUsd={dailyBudget.used_usd}
            limitUsd={dailyBudget.limit_usd}
            utilizationRatio={dailyBudget.utilization_ratio}
            exceeded={dailyBudget.exceeded}
            warningReached={dailyBudget.warning_reached}
          />
        )}
        {monthlyBudget && (
          <BudgetGauge
            title="Monthly Budget"
            period="monthly"
            usedUsd={monthlyBudget.used_usd}
            limitUsd={monthlyBudget.limit_usd}
            utilizationRatio={monthlyBudget.utilization_ratio}
            exceeded={monthlyBudget.exceeded}
            warningReached={monthlyBudget.warning_reached}
          />
        )}
      </Grid>

      {/* Cost Trend Chart */}
      <CostTrendChart data={costHistory} />

      {/* Model Cost Breakdown */}
      <ModelCostBreakdownChart data={data.cost_by_model} />

      {/* Pricing Info */}
      <Card data-testid="pricing-info">
        <Title>Pricing Configuration</Title>
        <Text className="text-gray-400">Cloud-equivalent pricing used for cost estimation</Text>
        <Grid numItemsMd={2} numItemsLg={3} className="mt-4 gap-4">
          <div>
            <Text className="text-gray-400">Input Tokens</Text>
            <Text className="text-lg text-white">
              {formatCost(data.pricing.input_cost_per_1k_tokens)}/1K
            </Text>
          </div>
          <div>
            <Text className="text-gray-400">Output Tokens</Text>
            <Text className="text-lg text-white">
              {formatCost(data.pricing.output_cost_per_1k_tokens)}/1K
            </Text>
          </div>
          <div>
            <Text className="text-gray-400">GPU Time</Text>
            <Text className="text-lg text-white">
              {formatCost(data.pricing.gpu_cost_per_second, 6)}/sec
            </Text>
          </div>
        </Grid>
      </Card>
    </div>
  );
}
