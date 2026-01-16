import { Card, ProgressBar, Title, Text, AreaChart, TabGroup, TabList, Tab } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, Thermometer, Activity, Zap, TrendingUp, Plug } from 'lucide-react';
import { useState, useMemo } from 'react';

import {
  useGpuStatsQuery,
  useGpuHistoryQuery,
  type UseGpuStatsQueryOptions,
  type UseGpuHistoryQueryOptions,
} from '../../hooks/useGpuStatsQuery';

import type { GPUStatsSample } from '../../types/generated';
import type { TimeRange } from '../../types/performance';

export interface GpuStatsProps {
  /** GPU device name (e.g., 'NVIDIA RTX A5500') */
  gpuName?: string | null;
  /** GPU utilization 0-100% (optional, for initial/override display) */
  utilization?: number | null;
  /** Memory used in MB (optional, for initial/override display) */
  memoryUsed?: number | null;
  /** Memory total in MB (optional, for initial/override display) */
  memoryTotal?: number | null;
  /** Temperature in Celsius (optional, for initial/override display) */
  temperature?: number | null;
  /** Power usage in Watts (optional) */
  powerUsage?: number | null;
  /** Inference FPS (optional, for initial/override display) */
  inferenceFps?: number | null;
  /** Additional CSS classes */
  className?: string;
  /** Options for the GPU stats query hook */
  statsQueryOptions?: UseGpuStatsQueryOptions;
  /** Options for the GPU history query hook */
  historyQueryOptions?: UseGpuHistoryQueryOptions;
  /** Time range for historical data display ('5m' | '15m' | '60m') */
  timeRange?: TimeRange;
  /** External history data - when provided, used instead of internal useGpuHistoryQuery */
  historyData?: GPUStatsSample[];
}

/**
 * Tab index for history chart selection
 */
type HistoryTab = 0 | 1 | 2;

/**
 * Chart data point for GPU history visualization
 */
interface ChartDataPoint {
  time: string;
  value: number;
}

/**
 * Determines temperature color based on value
 */
function getTemperatureColor(temp: number | null): 'gray' | 'green' | 'yellow' | 'red' {
  if (temp === null) return 'gray';
  if (temp < 70) return 'green';
  if (temp < 80) return 'yellow';
  return 'red';
}

/**
 * Determines power usage color based on value (watts)
 * - Green: < 150W (normal operation)
 * - Yellow: 150-250W (moderate load)
 * - Red: > 250W (high load)
 */
function getPowerColor(watts: number | null): 'gray' | 'green' | 'yellow' | 'red' {
  if (watts === null) return 'gray';
  if (watts < 150) return 'green';
  if (watts < 250) return 'yellow';
  return 'red';
}

/**
 * Formats a numeric value with fallback for null
 */
function formatValue(value: number | null, suffix: string = ''): string {
  return value !== null ? `${value.toFixed(0)}${suffix}` : 'N/A';
}

/**
 * Formats memory usage as a percentage and MB display
 */
function formatMemory(
  used: number | null,
  total: number | null
): { text: string; percentage: number | null } {
  if (used === null || total === null) {
    return { text: 'N/A', percentage: null };
  }
  const usedGB = (used / 1024).toFixed(1);
  const totalGB = (total / 1024).toFixed(1);
  const percentage = (used / total) * 100;
  return { text: `${usedGB} / ${totalGB} GB`, percentage };
}

/**
 * Transform GPU history to utilization chart data format
 */
function transformToUtilizationChart(history: GPUStatsSample[]): ChartDataPoint[] {
  return history.map((point) => ({
    time: new Date(point.recorded_at).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    value: point.utilization ?? 0,
  }));
}

/**
 * Transform GPU history to temperature chart data format
 */
function transformToTemperatureChart(history: GPUStatsSample[]): ChartDataPoint[] {
  return history.map((point) => ({
    time: new Date(point.recorded_at).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    value: point.temperature ?? 0,
  }));
}

/**
 * Transform GPU history to memory chart data format (in GB)
 */
function transformToMemoryChart(history: GPUStatsSample[]): ChartDataPoint[] {
  return history.map((point) => ({
    time: new Date(point.recorded_at).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    value: (point.memory_used ?? 0) / 1024, // Convert MB to GB
  }));
}

/**
 * GpuStats component displays GPU metrics in a compact dashboard card
 * - Shows GPU device name in header
 * - Shows utilization, memory usage, temperature, power usage, and inference FPS
 * - Displays tabbed history charts for utilization, temperature, and memory
 * - Uses NVIDIA branding color (#76B900) for healthy metrics
 * - Temperature color coding: green (<70C), yellow (70-80C), red (>80C)
 * - Power color coding: green (<150W), yellow (150-250W), red (>250W)
 * - Handles null values gracefully with "N/A" display
 * - Uses React Query for automatic data fetching and caching
 */
export default function GpuStats({
  gpuName,
  utilization: propUtilization,
  memoryUsed: propMemoryUsed,
  memoryTotal: propMemoryTotal,
  temperature: propTemperature,
  powerUsage,
  inferenceFps: propInferenceFps,
  className,
  statsQueryOptions,
  historyQueryOptions,
  timeRange,
  historyData,
}: GpuStatsProps) {
  // Determine if we should use the internal hooks or external data
  const useExternalData = historyData !== undefined;

  // Use React Query hooks for current GPU stats
  const {
    data: statsData,
    isLoading: statsLoading,
    error: statsError,
  } = useGpuStatsQuery({
    enabled: !useExternalData,
    ...statsQueryOptions,
  });

  // Use React Query hooks for GPU history
  const {
    history: internalHistory,
    isLoading: historyLoading,
    error: historyError,
  } = useGpuHistoryQuery({
    enabled: !useExternalData,
    ...historyQueryOptions,
  });

  // Use external history data when provided, otherwise use internal hook data
  const history = useExternalData ? historyData : internalHistory;
  const isLoading = useExternalData ? false : statsLoading || historyLoading;
  const error = useExternalData ? null : statsError?.message || historyError?.message || null;

  // Track selected history tab
  const [selectedTab, setSelectedTab] = useState<HistoryTab>(0);

  // Use hook data if available, otherwise fall back to props
  const utilization = statsData?.utilization ?? propUtilization ?? null;
  const memoryUsed = statsData?.memory_used ?? propMemoryUsed ?? null;
  const memoryTotal = statsData?.memory_total ?? propMemoryTotal ?? null;
  const temperature = statsData?.temperature ?? propTemperature ?? null;
  const inferenceFps = statsData?.inference_fps ?? propInferenceFps ?? null;

  const memory = formatMemory(memoryUsed, memoryTotal);
  const tempColor = getTemperatureColor(temperature);
  const powerColor = getPowerColor(powerUsage ?? null);

  // Transform history for different chart views, memoized for performance
  const utilizationChartData = useMemo(() => transformToUtilizationChart(history), [history]);
  const temperatureChartData = useMemo(() => transformToTemperatureChart(history), [history]);
  const memoryChartData = useMemo(() => transformToMemoryChart(history), [history]);

  // Get chart data based on selected tab
  const getChartData = () => {
    switch (selectedTab) {
      case 0:
        return utilizationChartData;
      case 1:
        return temperatureChartData;
      case 2:
        return memoryChartData;
      default:
        return utilizationChartData;
    }
  };

  // Get value formatter based on selected tab
  const getValueFormatter = () => {
    switch (selectedTab) {
      case 0:
        return (value: number) => `${value.toFixed(0)}%`;
      case 1:
        return (value: number) => `${value.toFixed(0)}\u00B0C`;
      case 2:
        return (value: number) => `${value.toFixed(1)} GB`;
      default:
        return (value: number) => `${value}`;
    }
  };

  // Get chart color based on selected tab
  const getChartColor = (): 'emerald' | 'amber' | 'blue' => {
    switch (selectedTab) {
      case 0:
        return 'emerald';
      case 1:
        return 'amber';
      case 2:
        return 'blue';
      default:
        return 'emerald';
    }
  };

  const chartData = getChartData();

  return (
    <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}>
      <div className="mb-4">
        <Title className="flex items-center gap-2 text-white">
          <Cpu className="h-5 w-5 text-[#76B900]" />
          GPU Statistics
        </Title>
        {gpuName && (
          <p className="mt-1 text-sm text-gray-400" data-testid="gpu-device-name">
            {gpuName}
          </p>
        )}
      </div>

      <div className="space-y-4">
        {/* GPU Utilization */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1.5 text-sm text-gray-300">
              <Activity className="h-4 w-4" />
              Utilization
            </Text>
            <Text className="text-sm font-medium text-white">{formatValue(utilization, '%')}</Text>
          </div>
          <ProgressBar
            value={utilization ?? 0}
            color={utilization !== null ? 'green' : 'gray'}
            className="mt-1"
          />
        </div>

        {/* Memory Usage */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1.5 text-sm text-gray-300">
              <Zap className="h-4 w-4" />
              Memory
            </Text>
            <Text className="text-sm font-medium text-white">{memory.text}</Text>
          </div>
          <ProgressBar
            value={memory.percentage ?? 0}
            color={memory.percentage !== null ? 'green' : 'gray'}
            className="mt-1"
          />
        </div>

        {/* Temperature */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1.5 text-sm text-gray-300">
              <Thermometer className="h-4 w-4" />
              Temperature
            </Text>
            <Text
              className={clsx(
                'text-sm font-medium',
                tempColor === 'green' && 'text-[#76B900]',
                tempColor === 'yellow' && 'text-yellow-500',
                tempColor === 'red' && 'text-red-500',
                tempColor === 'gray' && 'text-gray-400'
              )}
            >
              {formatValue(temperature, '\u00B0C')}
            </Text>
          </div>
          <ProgressBar value={temperature ?? 0} color={tempColor} className="mt-1" />
        </div>

        {/* Power Usage */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1.5 text-sm text-gray-300">
              <Plug className="h-4 w-4" />
              Power Usage
            </Text>
            <span
              className={clsx(
                'text-sm font-medium',
                powerColor === 'green' && 'text-[#76B900]',
                powerColor === 'yellow' && 'text-yellow-500',
                powerColor === 'red' && 'text-red-500',
                powerColor === 'gray' && 'text-gray-400'
              )}
              data-testid="gpu-power-usage"
            >
              {formatValue(powerUsage ?? null, 'W')}
            </span>
          </div>
          <ProgressBar
            value={
              powerUsage !== null && powerUsage !== undefined
                ? Math.min((powerUsage / 350) * 100, 100)
                : 0
            }
            color={powerColor}
            className="mt-1"
          />
        </div>

        {/* Inference FPS */}
        <div className="border-t border-gray-800 pt-2">
          <div className="flex items-center justify-between">
            <Text className="text-sm text-gray-300">Inference FPS</Text>
            <Text className="text-lg font-semibold text-[#76B900]">
              {formatValue(inferenceFps)}
            </Text>
          </div>
        </div>

        {/* GPU History Charts with Tabs */}
        <div className="border-t border-gray-800 pt-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-[#76B900]" />
            <Text className="text-sm font-medium text-gray-300">
              Metrics History{timeRange ? ` (${timeRange})` : ''}
            </Text>
          </div>

          {/* Tab Selection */}
          <TabGroup
            index={selectedTab}
            onIndexChange={(index) => setSelectedTab(index as HistoryTab)}
            className="mb-3"
          >
            <TabList variant="solid" className="bg-gray-800/50">
              <Tab className="text-xs" data-testid="tab-utilization">
                Utilization
              </Tab>
              <Tab className="text-xs" data-testid="tab-temperature">
                Temperature
              </Tab>
              <Tab className="text-xs" data-testid="tab-memory">
                Memory
              </Tab>
            </TabList>
          </TabGroup>

          {/* Chart Display */}
          {isLoading && history.length === 0 ? (
            <div
              className="flex h-32 items-center justify-center text-gray-500"
              data-testid="gpu-history-loading"
            >
              <Text>Loading history...</Text>
            </div>
          ) : error ? (
            <div
              className="flex h-32 items-center justify-center text-red-400"
              data-testid="gpu-history-error"
            >
              <Text>{error}</Text>
            </div>
          ) : chartData.length > 0 ? (
            <AreaChart
              className="h-32"
              data={chartData}
              index="time"
              categories={['value']}
              colors={[getChartColor()]}
              valueFormatter={getValueFormatter()}
              showLegend={false}
              showGridLines={false}
              curveType="monotone"
              data-testid="gpu-history-chart"
            />
          ) : (
            <div
              className="flex h-32 items-center justify-center text-gray-500"
              data-testid="gpu-history-empty"
            >
              <Text>No history data available</Text>
            </div>
          )}

          {/* Data point count indicator */}
          {history.length > 0 && (
            <div className="mt-2 text-right">
              <span className="text-xs text-gray-500" data-testid="gpu-history-count">
                {history.length} data point{history.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
