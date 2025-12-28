import { Card, ProgressBar, Title, Text, AreaChart } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, Thermometer, Activity, Zap, TrendingUp } from 'lucide-react';
import { useEffect, useState } from 'react';

import { fetchGpuHistory, type GPUStatsHistoryResponse } from '../../services/api';

export interface GpuStatsProps {
  utilization: number | null; // 0-100%
  memoryUsed: number | null; // MB
  memoryTotal: number | null; // MB
  temperature: number | null; // Celsius
  inferenceFps: number | null;
  className?: string;
}

/**
 * Chart data point for GPU utilization history
 */
interface ChartDataPoint {
  time: string;
  'GPU Utilization': number;
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
 * Transform GPU history response to chart data format
 */
function transformHistoryToChartData(history: GPUStatsHistoryResponse | null): ChartDataPoint[] {
  if (!history || !history.samples || history.samples.length === 0) {
    return [];
  }

  return history.samples.map((sample) => ({
    time: new Date(sample.recorded_at).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    'GPU Utilization': sample.utilization ?? 0,
  }));
}

/**
 * GpuStats component displays GPU metrics in a compact dashboard card
 * - Shows utilization, memory usage, temperature, and inference FPS
 * - Displays GPU utilization history chart
 * - Uses NVIDIA branding color (#76B900) for healthy metrics
 * - Temperature color coding: green (<70C), yellow (70-80C), red (>80C)
 * - Handles null values gracefully with "N/A" display
 */
export default function GpuStats({
  utilization,
  memoryUsed,
  memoryTotal,
  temperature,
  inferenceFps,
  className,
}: GpuStatsProps) {
  const [history, setHistory] = useState<GPUStatsHistoryResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const memory = formatMemory(memoryUsed, memoryTotal);
  const tempColor = getTemperatureColor(temperature);
  const chartData = transformHistoryToChartData(history);

  // Fetch GPU history on mount
  useEffect(() => {
    let isMounted = true;

    async function loadHistory() {
      try {
        setHistoryLoading(true);
        setHistoryError(null);
        const data = await fetchGpuHistory(100);
        if (isMounted) {
          setHistory(data);
        }
      } catch (error) {
        if (isMounted) {
          setHistoryError(error instanceof Error ? error.message : 'Failed to load GPU history');
        }
      } finally {
        if (isMounted) {
          setHistoryLoading(false);
        }
      }
    }

    void loadHistory();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Cpu className="h-5 w-5 text-[#76B900]" />
        GPU Statistics
      </Title>

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

        {/* Inference FPS */}
        <div className="border-t border-gray-800 pt-2">
          <div className="flex items-center justify-between">
            <Text className="text-sm text-gray-300">Inference FPS</Text>
            <Text className="text-lg font-semibold text-[#76B900]">
              {formatValue(inferenceFps)}
            </Text>
          </div>
        </div>

        {/* GPU Utilization History Chart */}
        <div className="border-t border-gray-800 pt-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-[#76B900]" />
            <Text className="text-sm font-medium text-gray-300">Utilization History</Text>
          </div>
          {historyLoading ? (
            <div
              className="flex h-32 items-center justify-center text-gray-500"
              data-testid="gpu-history-loading"
            >
              <Text>Loading history...</Text>
            </div>
          ) : historyError ? (
            <div
              className="flex h-32 items-center justify-center text-red-400"
              data-testid="gpu-history-error"
            >
              <Text>{historyError}</Text>
            </div>
          ) : chartData.length > 0 ? (
            <AreaChart
              className="h-32"
              data={chartData}
              index="time"
              categories={['GPU Utilization']}
              colors={['emerald']}
              valueFormatter={(value) => `${value}%`}
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
        </div>
      </div>
    </Card>
  );
}
