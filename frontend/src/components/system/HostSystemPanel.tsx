import { Card, Title, Text, ProgressBar, AreaChart } from '@tremor/react';
import { clsx } from 'clsx';
import { Monitor, Cpu, MemoryStick, HardDrive } from 'lucide-react';

/**
 * Host system metrics
 */
export interface HostMetrics {
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  disk_used_gb: number;
  disk_total_gb: number;
}

/**
 * History data point
 */
export interface HistoryDataPoint {
  timestamp: string;
  value: number;
}

/**
 * Host history data for charts
 */
export interface HostHistoryData {
  cpu: HistoryDataPoint[];
  ram: HistoryDataPoint[];
}

/**
 * Props for HostSystemPanel component
 */
export interface HostSystemPanelProps {
  /** Host metrics (null if unavailable) */
  host: HostMetrics | null;
  /** Current time range for historical data */
  timeRange: string;
  /** Historical data for charts */
  history: HostHistoryData;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get color based on CPU usage percentage
 */
function getCpuColor(percent: number): 'green' | 'yellow' | 'red' {
  if (percent >= 95) return 'red';
  if (percent >= 80) return 'yellow';
  return 'green';
}

/**
 * Get color based on RAM usage percentage
 */
function getRamColor(percent: number): 'green' | 'yellow' | 'red' {
  if (percent >= 95) return 'red';
  if (percent >= 85) return 'yellow';
  return 'green';
}

/**
 * Get color based on Disk usage percentage
 */
function getDiskColor(percent: number): 'green' | 'yellow' | 'red' {
  if (percent >= 90) return 'red';
  if (percent >= 80) return 'yellow';
  return 'green';
}

/**
 * Transform history data to chart format
 */
function transformToChartData(data: HistoryDataPoint[]): { time: string; value: number }[] {
  return data.map((point) => ({
    time: new Date(point.timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    value: point.value,
  }));
}

/**
 * Format size value with appropriate precision
 */
function formatSize(value: number): string {
  if (Number.isInteger(value)) {
    return `${value}`;
  }
  return value.toFixed(1);
}

/**
 * HostSystemPanel - Displays host system metrics (CPU, RAM, Disk)
 *
 * Shows:
 * - CPU usage percentage with progress bar
 * - RAM used/total with percentage and progress bar
 * - Disk used/total with percentage and progress bar
 * - Historical charts for CPU and RAM over time
 */
export default function HostSystemPanel({
  host,
  timeRange: _timeRange,
  history,
  className,
}: HostSystemPanelProps) {
  const cpuChartData = transformToChartData(history.cpu);
  const ramChartData = transformToChartData(history.ram);

  // Calculate percentages
  const ramPercent = host ? Math.round((host.ram_used_gb / host.ram_total_gb) * 100) : 0;
  const diskPercent = host ? Math.round((host.disk_used_gb / host.disk_total_gb) * 100) : 0;

  return (
    <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)} data-testid="host-system-panel">
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Monitor className="h-5 w-5 text-[#76B900]" />
        Host System
      </Title>

      {host ? (
        <div className="space-y-6">
          {/* Summary Row */}
          <div className="flex items-center justify-center gap-6 rounded-lg bg-gray-800/30 p-3 text-sm">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-blue-400" />
              <span className="text-gray-400">CPU:</span>
              <span className="font-medium text-white">{host.cpu_percent}%</span>
            </div>
            <span className="text-gray-600">|</span>
            <div className="flex items-center gap-2">
              <MemoryStick className="h-4 w-4 text-purple-400" />
              <span className="text-gray-400">RAM:</span>
              <span className="font-medium text-white">{formatSize(host.ram_used_gb)}/{formatSize(host.ram_total_gb)} GB</span>
              <span className="text-gray-500">({ramPercent}%)</span>
            </div>
            <span className="text-gray-600">|</span>
            <div className="flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-orange-400" />
              <span className="text-gray-400">Disk:</span>
              <span className="font-medium text-white">{formatSize(host.disk_used_gb)}/{formatSize(host.disk_total_gb)} GB</span>
              <span className="text-gray-500">({diskPercent}%)</span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {/* CPU Section */}
            <div data-testid="host-cpu-section">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-blue-400" />
                  <Text className="text-sm font-medium text-gray-200">CPU</Text>
                </div>
                <span
                  className={clsx(
                    'text-sm font-medium',
                    getCpuColor(host.cpu_percent) === 'green' && 'text-green-400',
                    getCpuColor(host.cpu_percent) === 'yellow' && 'text-yellow-400',
                    getCpuColor(host.cpu_percent) === 'red' && 'text-red-400'
                  )}
                  data-testid="host-cpu-value"
                >
                  {host.cpu_percent}%
                </span>
              </div>
              <ProgressBar
                value={host.cpu_percent}
                color={getCpuColor(host.cpu_percent)}
                className="h-2"
                data-testid="host-cpu-bar"
              />
              <div className="mt-3" data-testid="host-cpu-chart">
                {cpuChartData.length > 0 ? (
                  <AreaChart
                    className="h-20"
                    data={cpuChartData}
                    index="time"
                    categories={['value']}
                    colors={['blue']}
                    showLegend={false}
                    showGridLines={false}
                    curveType="monotone"
                    valueFormatter={(value) => `${value}%`}
                  />
                ) : (
                  <div className="flex h-20 items-center justify-center">
                    <Text className="text-xs text-gray-500">No history data</Text>
                  </div>
                )}
              </div>
            </div>

            {/* RAM Section */}
            <div data-testid="host-ram-section">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MemoryStick className="h-4 w-4 text-purple-400" />
                  <Text className="text-sm font-medium text-gray-200">RAM</Text>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-200" data-testid="host-ram-value">
                    {formatSize(host.ram_used_gb)}/{formatSize(host.ram_total_gb)} GB
                  </span>
                  <span
                    className={clsx(
                      'text-sm font-medium',
                      getRamColor(ramPercent) === 'green' && 'text-green-400',
                      getRamColor(ramPercent) === 'yellow' && 'text-yellow-400',
                      getRamColor(ramPercent) === 'red' && 'text-red-400'
                    )}
                    data-testid="host-ram-percent"
                  >
                    {ramPercent}%
                  </span>
                </div>
              </div>
              <ProgressBar
                value={ramPercent}
                color={getRamColor(ramPercent)}
                className="h-2"
                data-testid="host-ram-bar"
              />
              <div className="mt-3" data-testid="host-ram-chart">
                {ramChartData.length > 0 ? (
                  <AreaChart
                    className="h-20"
                    data={ramChartData}
                    index="time"
                    categories={['value']}
                    colors={['violet']}
                    showLegend={false}
                    showGridLines={false}
                    curveType="monotone"
                    valueFormatter={(value) => `${value.toFixed(1)} GB`}
                  />
                ) : (
                  <div className="flex h-20 items-center justify-center">
                    <Text className="text-xs text-gray-500">No history data</Text>
                  </div>
                )}
              </div>
            </div>

            {/* Disk Section */}
            <div data-testid="host-disk-section">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <HardDrive className="h-4 w-4 text-orange-400" />
                  <Text className="text-sm font-medium text-gray-200">Disk</Text>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-200" data-testid="host-disk-value">
                    {formatSize(host.disk_used_gb)}/{formatSize(host.disk_total_gb)} GB
                  </span>
                  <span
                    className={clsx(
                      'text-sm font-medium',
                      getDiskColor(diskPercent) === 'green' && 'text-green-400',
                      getDiskColor(diskPercent) === 'yellow' && 'text-yellow-400',
                      getDiskColor(diskPercent) === 'red' && 'text-red-400'
                    )}
                    data-testid="host-disk-percent"
                  >
                    {diskPercent}%
                  </span>
                </div>
              </div>
              <ProgressBar
                value={diskPercent}
                color={getDiskColor(diskPercent)}
                className="h-2"
                data-testid="host-disk-bar"
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="flex h-40 items-center justify-center">
          <Text className="text-sm text-gray-500">No data available</Text>
        </div>
      )}
    </Card>
  );
}
