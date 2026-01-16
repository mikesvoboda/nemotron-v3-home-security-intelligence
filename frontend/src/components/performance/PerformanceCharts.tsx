/**
 * PerformanceCharts - Time-series visualization for system performance metrics
 *
 * Displays four charts:
 * 1. GPU Utilization - AreaChart showing GPU utilization % and VRAM usage over time
 * 2. Temperature - LineChart with warning (75C) and critical (85C) threshold lines
 * 3. Inference Latency - LineChart with RT-DETRv2, Nemotron, and pipeline latencies
 * 4. Resource Usage - AreaChart showing CPU, RAM, and Disk percentages
 *
 * Data source: usePerformanceMetrics hook's history circular buffers
 */

import { Card, Title, Text, AreaChart, LineChart, Grid, Col } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, Thermometer, Timer, HardDrive } from 'lucide-react';
import { useMemo } from 'react';

import {
  usePerformanceMetrics,
  type PerformanceUpdate,
  type TimeRange,
} from '../../hooks/usePerformanceMetrics';

export interface PerformanceChartsProps {
  /** Additional CSS classes */
  className?: string;
  /** Custom time range - if provided, overrides hook's internal timeRange */
  timeRange?: TimeRange;
  /** Custom history data - if provided, uses this instead of hook data */
  historyData?: PerformanceUpdate[];
  /** Hide time range selector (for embedded use) */
  hideTimeRangeSelector?: boolean;
}

/**
 * Time range display labels
 */
const TIME_RANGE_LABELS: Record<TimeRange, string> = {
  '5m': 'Last 5 minutes',
  '15m': 'Last 15 minutes',
  '60m': 'Last hour',
};

/**
 * Temperature thresholds in Celsius
 */
const TEMPERATURE_THRESHOLDS = {
  warning: 75,
  critical: 85,
};

/**
 * Format timestamp for chart x-axis
 */
function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format temperature value for display
 */
function formatTemperature(value: number): string {
  return `${Math.round(value)}\u00B0C`;
}

/**
 * Format percentage value for display
 */
function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

/**
 * Format milliseconds for display
 */
function formatMs(value: number): string {
  if (value < 1) return '< 1ms';
  if (value < 1000) return `${Math.round(value)}ms`;
  return `${(value / 1000).toFixed(1)}s`;
}

/**
 * GPU chart data point
 */
interface GpuChartPoint {
  time: string;
  'GPU Utilization': number;
  'VRAM Usage': number;
}

/**
 * Temperature chart data point
 */
interface TemperatureChartPoint {
  time: string;
  Temperature: number;
  Warning: number;
  Critical: number;
}

/**
 * Latency chart data point
 */
interface LatencyChartPoint {
  time: string;
  'RT-DETRv2': number | null;
  Nemotron: number | null;
  Pipeline: number | null;
}

/**
 * Resource chart data point
 */
interface ResourceChartPoint {
  time: string;
  CPU: number;
  RAM: number;
  Disk: number;
}

/**
 * Transform history data for GPU utilization chart
 */
function transformGpuData(history: PerformanceUpdate[]): GpuChartPoint[] {
  return history.map((snapshot) => {
    const vramPercent =
      snapshot.gpu && snapshot.gpu.vram_total_gb > 0
        ? (snapshot.gpu.vram_used_gb / snapshot.gpu.vram_total_gb) * 100
        : 0;

    return {
      time: formatTime(snapshot.timestamp),
      'GPU Utilization': snapshot.gpu?.utilization ?? 0,
      'VRAM Usage': vramPercent,
    };
  });
}

/**
 * Transform history data for temperature chart with threshold lines
 */
function transformTemperatureData(history: PerformanceUpdate[]): TemperatureChartPoint[] {
  return history.map((snapshot) => ({
    time: formatTime(snapshot.timestamp),
    Temperature: snapshot.gpu?.temperature ?? 0,
    Warning: TEMPERATURE_THRESHOLDS.warning,
    Critical: TEMPERATURE_THRESHOLDS.critical,
  }));
}

/**
 * Transform history data for inference latency chart
 */
function transformLatencyData(history: PerformanceUpdate[]): LatencyChartPoint[] {
  return history.map((snapshot) => ({
    time: formatTime(snapshot.timestamp),
    'RT-DETRv2': snapshot.inference?.rtdetr_latency_ms?.avg ?? null,
    Nemotron: snapshot.inference?.nemotron_latency_ms?.avg ?? null,
    Pipeline: snapshot.inference?.pipeline_latency_ms?.avg ?? null,
  }));
}

/**
 * Transform history data for resource usage chart
 */
function transformResourceData(history: PerformanceUpdate[]): ResourceChartPoint[] {
  return history.map((snapshot) => {
    const ramPercent =
      snapshot.host && snapshot.host.ram_total_gb > 0
        ? (snapshot.host.ram_used_gb / snapshot.host.ram_total_gb) * 100
        : 0;

    const diskPercent =
      snapshot.host && snapshot.host.disk_total_gb > 0
        ? (snapshot.host.disk_used_gb / snapshot.host.disk_total_gb) * 100
        : 0;

    return {
      time: formatTime(snapshot.timestamp),
      CPU: snapshot.host?.cpu_percent ?? 0,
      RAM: ramPercent,
      Disk: diskPercent,
    };
  });
}

/**
 * Check if history has meaningful GPU data
 */
function hasGpuData(history: PerformanceUpdate[]): boolean {
  return history.some((snapshot) => snapshot.gpu !== null);
}

/**
 * Check if history has meaningful inference data
 */
function hasInferenceData(history: PerformanceUpdate[]): boolean {
  return history.some(
    (snapshot) =>
      snapshot.inference !== null &&
      (snapshot.inference.rtdetr_latency_ms?.avg !== undefined ||
        snapshot.inference.nemotron_latency_ms?.avg !== undefined ||
        snapshot.inference.pipeline_latency_ms?.avg !== undefined)
  );
}

/**
 * Check if history has meaningful host data
 */
function hasHostData(history: PerformanceUpdate[]): boolean {
  return history.some((snapshot) => snapshot.host !== null);
}

/**
 * Empty state placeholder component
 */
function EmptyChart({
  message,
  icon: Icon,
}: {
  message: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex h-48 items-center justify-center" data-testid="empty-chart">
      <div className="text-center">
        <Icon className="mx-auto mb-2 h-8 w-8 text-gray-600" />
        <Text className="text-gray-500">{message}</Text>
        <Text className="mt-1 text-xs text-gray-600">
          Data will appear as metrics are collected
        </Text>
      </div>
    </div>
  );
}

/**
 * PerformanceCharts - Comprehensive performance metrics visualization
 */
export default function PerformanceCharts({
  className,
  timeRange: propTimeRange,
  historyData,
  hideTimeRangeSelector = false,
}: PerformanceChartsProps) {
  const { history, timeRange: hookTimeRange, setTimeRange, isConnected } = usePerformanceMetrics();

  // Use prop timeRange if provided, otherwise use hook's timeRange
  const activeTimeRange = propTimeRange ?? hookTimeRange;

  // Use prop historyData if provided, otherwise get from hook's history
  const activeHistory = historyData ?? history[activeTimeRange];

  // Memoize chart data transformations
  const gpuChartData = useMemo(() => transformGpuData(activeHistory), [activeHistory]);
  const temperatureChartData = useMemo(
    () => transformTemperatureData(activeHistory),
    [activeHistory]
  );
  const latencyChartData = useMemo(() => transformLatencyData(activeHistory), [activeHistory]);
  const resourceChartData = useMemo(() => transformResourceData(activeHistory), [activeHistory]);

  // Check data availability
  const showGpuChart = hasGpuData(activeHistory);
  const showInferenceChart = hasInferenceData(activeHistory);
  const showResourceChart = hasHostData(activeHistory);

  return (
    <div className={clsx('space-y-4', className)} data-testid="performance-charts">
      {/* Time Range Selector & Connection Status */}
      {!hideTimeRangeSelector && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {(['5m', '15m', '60m'] as TimeRange[]).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={clsx(
                  'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  activeTimeRange === range
                    ? 'bg-[#76B900] text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
                )}
                data-testid={`time-range-${range}`}
              >
                {TIME_RANGE_LABELS[range]}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <div
              className={clsx('h-2 w-2 rounded-full', isConnected ? 'bg-green-500' : 'bg-red-500')}
              data-testid="connection-indicator"
            />
            <Text className="text-xs text-gray-500">
              {isConnected ? 'Connected' : 'Disconnected'}
            </Text>
          </div>
        </div>
      )}

      {/* Charts Grid */}
      <Grid numItems={1} numItemsMd={2} className="gap-4">
        {/* GPU Utilization Chart */}
        <Col>
          <Card
            className="border-gray-800 bg-[#1A1A1A] shadow-lg"
            data-testid="gpu-utilization-card"
          >
            <Title className="mb-4 flex items-center gap-2 text-white">
              <Cpu className="h-5 w-5 text-[#76B900]" />
              GPU Utilization
            </Title>

            {activeHistory.length > 0 && showGpuChart ? (
              <AreaChart
                className="h-48"
                data={gpuChartData}
                index="time"
                categories={['GPU Utilization', 'VRAM Usage']}
                colors={['emerald', 'blue']}
                valueFormatter={formatPercent}
                showLegend={true}
                showGridLines={true}
                curveType="monotone"
                connectNulls={true}
                yAxisWidth={50}
                data-testid="gpu-area-chart"
              />
            ) : (
              <EmptyChart message="No GPU data available" icon={Cpu} />
            )}

            {activeHistory.length > 0 && showGpuChart && (
              <Text className="mt-2 text-xs text-gray-500">{activeHistory.length} data points</Text>
            )}
          </Card>
        </Col>

        {/* Temperature Chart */}
        <Col>
          <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="temperature-card">
            <Title className="mb-4 flex items-center gap-2 text-white">
              <Thermometer className="h-5 w-5 text-[#76B900]" />
              GPU Temperature
            </Title>

            {activeHistory.length > 0 && showGpuChart ? (
              <LineChart
                className="h-48"
                data={temperatureChartData}
                index="time"
                categories={['Temperature', 'Warning', 'Critical']}
                colors={['amber', 'yellow', 'red']}
                valueFormatter={formatTemperature}
                showLegend={true}
                showGridLines={true}
                curveType="monotone"
                connectNulls={true}
                yAxisWidth={50}
                data-testid="temperature-line-chart"
              />
            ) : (
              <EmptyChart message="No temperature data available" icon={Thermometer} />
            )}

            {activeHistory.length > 0 && showGpuChart && (
              <div className="mt-2 flex items-center justify-between">
                <Text className="text-xs text-gray-500">{activeHistory.length} data points</Text>
                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-yellow-500" />
                    <span className="text-gray-400">
                      Warning: {TEMPERATURE_THRESHOLDS.warning}C
                    </span>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-red-500" />
                    <span className="text-gray-400">
                      Critical: {TEMPERATURE_THRESHOLDS.critical}C
                    </span>
                  </span>
                </div>
              </div>
            )}
          </Card>
        </Col>

        {/* Inference Latency Chart */}
        <Col>
          <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="latency-card">
            <Title className="mb-4 flex items-center gap-2 text-white">
              <Timer className="h-5 w-5 text-[#76B900]" />
              Inference Latency
            </Title>

            {activeHistory.length > 0 && showInferenceChart ? (
              <LineChart
                className="h-48"
                data={latencyChartData}
                index="time"
                categories={['RT-DETRv2', 'Nemotron', 'Pipeline']}
                colors={['cyan', 'violet', 'emerald']}
                valueFormatter={formatMs}
                showLegend={true}
                showGridLines={true}
                curveType="monotone"
                connectNulls={true}
                yAxisWidth={60}
                data-testid="latency-line-chart"
              />
            ) : (
              <EmptyChart message="No inference latency data available" icon={Timer} />
            )}

            {activeHistory.length > 0 && showInferenceChart && (
              <Text className="mt-2 text-xs text-gray-500">{activeHistory.length} data points</Text>
            )}
          </Card>
        </Col>

        {/* Resource Usage Chart */}
        <Col>
          <Card
            className="border-gray-800 bg-[#1A1A1A] shadow-lg"
            data-testid="resource-usage-card"
          >
            <Title className="mb-4 flex items-center gap-2 text-white">
              <HardDrive className="h-5 w-5 text-[#76B900]" />
              System Resources
            </Title>

            {activeHistory.length > 0 && showResourceChart ? (
              <AreaChart
                className="h-48"
                data={resourceChartData}
                index="time"
                categories={['CPU', 'RAM', 'Disk']}
                colors={['blue', 'amber', 'rose']}
                valueFormatter={formatPercent}
                showLegend={true}
                showGridLines={true}
                curveType="monotone"
                connectNulls={true}
                yAxisWidth={50}
                data-testid="resource-area-chart"
              />
            ) : (
              <EmptyChart message="No system resource data available" icon={HardDrive} />
            )}

            {activeHistory.length > 0 && showResourceChart && (
              <Text className="mt-2 text-xs text-gray-500">{activeHistory.length} data points</Text>
            )}
          </Card>
        </Col>
      </Grid>
    </div>
  );
}
