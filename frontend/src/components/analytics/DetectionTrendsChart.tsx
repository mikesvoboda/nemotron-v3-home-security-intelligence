/**
 * DetectionTrendsChart - Display detection trends over time
 *
 * NEM-3659: Visualizes detection trends data that is available from the
 * useDetectionTrendsQuery hook but was not previously displayed in the
 * native analytics view.
 */

import { Card, Title, Text, AreaChart } from '@tremor/react';
import { AlertCircle, Loader2, TrendingUp } from 'lucide-react';
import { useMemo } from 'react';

import { useDetectionTrendsQuery } from '../../hooks/useDetectionTrendsQuery';

interface DetectionTrendsChartProps {
  startDate: string;
  endDate: string;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatNumber(num: number): string {
  return num.toLocaleString();
}

export default function DetectionTrendsChart({ startDate, endDate }: DetectionTrendsChartProps) {
  const { dataPoints, totalDetections, isLoading, error } = useDetectionTrendsQuery({
    start_date: startDate,
    end_date: endDate,
  });

  const chartData = useMemo(() => {
    return dataPoints.map((point) => ({
      date: formatDate(point.date),
      Detections: point.count,
    }));
  }, [dataPoints]);

  const averageDaily = useMemo(() => {
    if (dataPoints.length === 0) return 0;
    return Math.round(totalDetections / dataPoints.length);
  }, [dataPoints, totalDetections]);

  const dateRangeLabel = formatDate(startDate) + ' - ' + formatDate(endDate);

  if (isLoading) {
    return (
      <Card data-testid="detection-trends-loading">
        <Title>Detection Trends</Title>
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card data-testid="detection-trends-error">
        <Title>Detection Trends</Title>
        <div className="flex h-64 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load detection trends</Text>
        </div>
      </Card>
    );
  }

  if (dataPoints.length === 0) {
    return (
      <Card data-testid="detection-trends-empty">
        <Title>Detection Trends</Title>
        <div className="flex h-64 flex-col items-center justify-center text-gray-400">
          <TrendingUp className="mb-2 h-8 w-8" />
          <Text>No detection data available</Text>
          <Text className="mt-1 text-sm">Detection trends will appear as objects are detected</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="detection-trends-chart">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TrendingUp className="h-5 w-5 text-[#76B900]" />
          <Title>Detection Trends</Title>
        </div>
        <Text className="text-gray-400">{dateRangeLabel}</Text>
      </div>
      <div className="mb-4 grid grid-cols-2 gap-4">
        <div className="rounded-lg bg-gray-800/50 p-3">
          <Text className="text-sm text-gray-400">Total Detections</Text>
          <p className="text-2xl font-semibold text-white" data-testid="detection-trends-total">
            {formatNumber(totalDetections)}
          </p>
        </div>
        <div className="rounded-lg bg-gray-800/50 p-3">
          <Text className="text-sm text-gray-400">Daily Average</Text>
          <p className="text-2xl font-semibold text-white" data-testid="detection-trends-average">
            {formatNumber(averageDaily)}
          </p>
        </div>
      </div>
      <AreaChart
        className="h-48"
        data={chartData}
        index="date"
        categories={['Detections']}
        colors={['emerald']}
        showAnimation
        showLegend={false}
        showGridLines={false}
        curveType="monotone"
        valueFormatter={formatNumber}
        data-testid="detection-trends-area-chart"
      />
    </Card>
  );
}
