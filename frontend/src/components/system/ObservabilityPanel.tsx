import { Card, Title, Text, AreaChart, DonutChart, ProgressBar, Metric } from '@tremor/react';
import { clsx } from 'clsx';
import { Activity, Cpu, Thermometer, Zap, ExternalLink, Server, Layers } from 'lucide-react';

/**
 * GPU metrics data point for time series charts
 */
export interface GpuMetricDataPoint {
  timestamp: string;
  utilization: number;
  memory_used: number;
  temperature: number;
}

/**
 * Queue statistics for pipeline monitoring
 */
export interface QueueStats {
  pending: number;
  processing: number;
}

/**
 * System health status
 */
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

export interface ObservabilityPanelProps {
  /** Current GPU utilization (0-100%) */
  gpuUtilization: number | null;
  /** Current GPU memory used (MB) */
  gpuMemoryUsed: number | null;
  /** Total GPU memory (MB) */
  gpuMemoryTotal: number | null;
  /** Current GPU temperature (Celsius) */
  gpuTemperature: number | null;
  /** Historical GPU metrics for charts */
  gpuHistory?: GpuMetricDataPoint[];
  /** Pipeline queue statistics */
  queueStats?: QueueStats;
  /** Overall system health status */
  healthStatus: HealthStatus;
  /** Grafana base URL (default: localhost:3000) */
  grafanaUrl?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get color for health status indicator
 */
function getHealthColor(status: HealthStatus): string {
  switch (status) {
    case 'healthy':
      return '#76B900'; // NVIDIA Green
    case 'degraded':
      return '#FFB800'; // Warning yellow
    case 'unhealthy':
      return '#ef4444'; // Red
    default:
      return '#6b7280'; // Gray
  }
}

/**
 * Get label for health status
 */
function getHealthLabel(status: HealthStatus): string {
  switch (status) {
    case 'healthy':
      return 'Healthy';
    case 'degraded':
      return 'Degraded';
    case 'unhealthy':
      return 'Unhealthy';
    default:
      return 'Unknown';
  }
}

/**
 * Get color for temperature gauge
 */
function getTemperatureColor(temp: number | null): 'green' | 'yellow' | 'red' | 'gray' {
  if (temp === null) return 'gray';
  if (temp < 70) return 'green';
  if (temp < 80) return 'yellow';
  return 'red';
}

/**
 * Format memory value in GB
 */
function formatMemoryGB(value: number | null): string {
  if (value === null) return 'N/A';
  return `${(value / 1024).toFixed(1)} GB`;
}

/**
 * ObservabilityPanel - System monitoring dashboard section
 *
 * Displays real-time system metrics using native Tremor charts:
 * - GPU utilization over time (AreaChart)
 * - Memory usage gauge (ProgressBar + DonutChart)
 * - Temperature gauge (ProgressBar with color coding)
 * - Queue depth statistics
 * - System health status indicator
 * - Link to Grafana for detailed metrics
 *
 * Features NVIDIA dark theme styling with green accents.
 */
export default function ObservabilityPanel({
  gpuUtilization,
  gpuMemoryUsed,
  gpuMemoryTotal,
  gpuTemperature,
  gpuHistory = [],
  queueStats,
  healthStatus,
  grafanaUrl = 'http://localhost:3000',
  className,
}: ObservabilityPanelProps) {
  const memoryPercentage =
    gpuMemoryUsed !== null && gpuMemoryTotal !== null && gpuMemoryTotal > 0
      ? (gpuMemoryUsed / gpuMemoryTotal) * 100
      : null;

  const tempColor = getTemperatureColor(gpuTemperature);
  const healthColor = getHealthColor(healthStatus);
  const healthLabel = getHealthLabel(healthStatus);

  // Format chart data for Tremor
  const chartData = gpuHistory.map((point) => ({
    time: new Date(point.timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    'GPU Utilization': point.utilization,
    'Memory Usage': (point.memory_used / 1024).toFixed(1),
    Temperature: point.temperature,
  }));

  // Memory donut chart data
  const memoryDonutData =
    gpuMemoryUsed !== null && gpuMemoryTotal !== null
      ? [
          { name: 'Used', value: gpuMemoryUsed },
          { name: 'Free', value: Math.max(0, gpuMemoryTotal - gpuMemoryUsed) },
        ]
      : [{ name: 'Unknown', value: 100 }];

  return (
    <div className={clsx('space-y-6', className)}>
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Server className="h-6 w-6 text-[#76B900]" />
          <Title className="text-white text-2xl">System Observability</Title>
        </div>
        {/* Health Status Indicator */}
        <div className="flex items-center gap-2">
          <div
            className="h-3 w-3 rounded-full animate-pulse"
            style={{ backgroundColor: healthColor }}
            aria-label={`System health: ${healthLabel}`}
          />
          <Text className="text-gray-300">{healthLabel}</Text>
        </div>
      </div>

      {/* Main Grid Layout */}
      <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
        {/* GPU Utilization Chart */}
        <Card className="bg-[#1A1A1A] border-gray-800 shadow-lg xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-[#76B900]" />
              <Title className="text-white">GPU Utilization Over Time</Title>
            </div>
            <div className="text-right">
              <Metric className="text-[#76B900]">
                {gpuUtilization !== null ? `${gpuUtilization.toFixed(0)}%` : 'N/A'}
              </Metric>
              <Text className="text-gray-400 text-sm">Current</Text>
            </div>
          </div>
          {chartData.length > 0 ? (
            <AreaChart
              className="h-48 mt-4"
              data={chartData}
              index="time"
              categories={['GPU Utilization']}
              colors={['emerald']}
              valueFormatter={(value) => `${value}%`}
              showLegend={false}
              showGridLines={false}
              curveType="monotone"
            />
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-500">
              <Text>No data available</Text>
            </div>
          )}
        </Card>

        {/* Memory Usage Card */}
        <Card className="bg-[#1A1A1A] border-gray-800 shadow-lg">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="h-5 w-5 text-[#76B900]" />
            <Title className="text-white">GPU Memory</Title>
          </div>

          <div className="flex items-center justify-center mb-4">
            <DonutChart
              className="h-36 w-36"
              data={memoryDonutData}
              category="value"
              index="name"
              colors={['emerald', 'gray']}
              showAnimation={true}
              showLabel={true}
              valueFormatter={(value) => formatMemoryGB(value)}
            />
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <Text className="text-gray-300">Used</Text>
              <Text className="text-white font-medium">{formatMemoryGB(gpuMemoryUsed)}</Text>
            </div>
            <div className="flex justify-between items-center">
              <Text className="text-gray-300">Total</Text>
              <Text className="text-white font-medium">{formatMemoryGB(gpuMemoryTotal)}</Text>
            </div>
            <ProgressBar
              value={memoryPercentage ?? 0}
              color={memoryPercentage !== null ? 'emerald' : 'gray'}
              className="mt-2"
            />
          </div>
        </Card>

        {/* Temperature Gauge Card */}
        <Card className="bg-[#1A1A1A] border-gray-800 shadow-lg">
          <div className="flex items-center gap-2 mb-4">
            <Thermometer className="h-5 w-5 text-[#76B900]" />
            <Title className="text-white">GPU Temperature</Title>
          </div>

          <div className="flex flex-col items-center justify-center py-4">
            <Metric
              className={clsx(
                tempColor === 'green' && 'text-[#76B900]',
                tempColor === 'yellow' && 'text-yellow-500',
                tempColor === 'red' && 'text-red-500',
                tempColor === 'gray' && 'text-gray-400'
              )}
            >
              {gpuTemperature !== null ? `${gpuTemperature.toFixed(0)}` : 'N/A'}
            </Metric>
            <Text className="text-gray-400">{gpuTemperature !== null ? 'Celsius' : ''}</Text>
          </div>

          <ProgressBar
            value={gpuTemperature ?? 0}
            color={tempColor}
            className="mt-4"
          />

          <div className="flex justify-between mt-2 text-xs text-gray-500">
            <span>0</span>
            <span>70</span>
            <span>80</span>
            <span>100</span>
          </div>
        </Card>

        {/* Queue Stats Card */}
        <Card className="bg-[#1A1A1A] border-gray-800 shadow-lg">
          <div className="flex items-center gap-2 mb-4">
            <Layers className="h-5 w-5 text-[#76B900]" />
            <Title className="text-white">Pipeline Queue</Title>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-[#121212] rounded-lg">
              <div>
                <Text className="text-gray-400 text-sm">Pending</Text>
                <Metric className="text-white">{queueStats?.pending ?? 0}</Metric>
              </div>
              <div className="h-12 w-12 rounded-full bg-yellow-500/20 flex items-center justify-center">
                <span className="text-yellow-500 font-bold">{queueStats?.pending ?? 0}</span>
              </div>
            </div>

            <div className="flex justify-between items-center p-3 bg-[#121212] rounded-lg">
              <div>
                <Text className="text-gray-400 text-sm">Processing</Text>
                <Metric className="text-white">{queueStats?.processing ?? 0}</Metric>
              </div>
              <div className="h-12 w-12 rounded-full bg-[#76B900]/20 flex items-center justify-center">
                <span className="text-[#76B900] font-bold">{queueStats?.processing ?? 0}</span>
              </div>
            </div>
          </div>
        </Card>

        {/* Grafana Link Card */}
        <Card className="bg-[#1A1A1A] border-gray-800 shadow-lg">
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="h-5 w-5 text-[#76B900]" />
            <Title className="text-white">Detailed Metrics</Title>
          </div>

          <Text className="text-gray-400 mb-4">
            View comprehensive system metrics, historical data, and custom dashboards in Grafana.
          </Text>

          <a
            href={grafanaUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#76B900] hover:bg-[#8BCB00] text-black font-medium rounded-lg transition-colors"
          >
            <ExternalLink className="h-4 w-4" />
            Open Grafana
          </a>

          <Text className="text-gray-500 text-xs mt-3">Opens in new tab at {grafanaUrl}</Text>
        </Card>
      </div>
    </div>
  );
}
