/**
 * ModelContributionChart - Bar chart showing AI model contribution rates
 *
 * Displays a horizontal bar chart showing which AI models contribute most
 * to event analysis, with contribution percentages.
 */

import { Card, Title, BarChart } from '@tremor/react';
import { clsx } from 'clsx';
import { BarChart3 } from 'lucide-react';

export interface ModelContributionChartProps {
  /** Model contribution rates (0-1 scale) */
  contributionRates: Record<string, number>;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Human-readable labels for model names
 */
const MODEL_LABELS: Record<string, string> = {
  rtdetr: 'RT-DETR',
  florence: 'Florence',
  clip: 'CLIP',
  violence: 'Violence',
  clothing: 'Clothing',
  vehicle: 'Vehicle',
  pet: 'Pet',
  weather: 'Weather',
  image_quality: 'Image Quality',
  zones: 'Zones',
  baseline: 'Baseline',
  cross_camera: 'Cross-Camera',
};

/**
 * Transform contribution rates to chart data
 */
function transformChartData(rates: Record<string, number>) {
  return Object.entries(rates)
    .map(([key, value]) => ({
      model: MODEL_LABELS[key] || key,
      'Contribution Rate': Math.round(value * 100),
    }))
    .sort((a, b) => b['Contribution Rate'] - a['Contribution Rate']);
}

/**
 * ModelContributionChart - Visualization of model contribution rates
 */
export default function ModelContributionChart({
  contributionRates,
  className,
}: ModelContributionChartProps) {
  const chartData = transformChartData(contributionRates);
  const hasData = chartData.length > 0 && chartData.some((d) => d['Contribution Rate'] > 0);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="model-contribution-chart"
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <BarChart3 className="h-5 w-5 text-[#76B900]" />
        Model Contribution Rates
      </Title>

      {hasData ? (
        <BarChart
          className="mt-4 h-72"
          data={chartData}
          index="model"
          categories={['Contribution Rate']}
          colors={['emerald']}
          valueFormatter={(value) => `${value}%`}
          showAnimation
          showLegend={false}
          layout="vertical"
          data-testid="contribution-bar-chart"
        />
      ) : (
        <div className="flex h-72 items-center justify-center">
          <div className="text-center">
            <BarChart3 className="mx-auto mb-2 h-8 w-8 text-gray-600" />
            <p className="text-gray-500">No contribution data available</p>
            <p className="mt-1 text-xs text-gray-600">
              Model contributions will appear here once events are processed
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
