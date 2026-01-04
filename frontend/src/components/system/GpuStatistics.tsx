import { Card, Title, Text, Badge, SparkAreaChart } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Cpu,
  Activity,
  Thermometer,
  HardDrive,
  Plug,
  Zap,
  ExternalLink,
  CheckCircle,
  XCircle,
  AlertTriangle,
} from 'lucide-react';

import type { GpuMetricDataPoint } from '../../hooks/useGpuHistory';

/**
 * AI Model status for mini-cards
 */
export interface AiModelStatus {
  /** Model name */
  name: string;
  /** Model status */
  status: 'healthy' | 'unhealthy' | 'loading' | 'unknown';
  /** Average latency in ms or seconds */
  latency?: string;
  /** Total inference/analysis count */
  count?: number;
  /** Error count */
  errors?: number;
}

/**
 * Props for GpuStatistics component
 */
export interface GpuStatisticsProps {
  /** GPU device name (e.g., 'NVIDIA RTX A5500') */
  gpuName?: string | null;
  /** GPU utilization 0-100% */
  utilization?: number | null;
  /** Temperature in Celsius */
  temperature?: number | null;
  /** Memory used in MB */
  memoryUsed?: number | null;
  /** Memory total in MB */
  memoryTotal?: number | null;
  /** Power usage in Watts */
  powerUsage?: number | null;
  /** Inference FPS */
  inferenceFps?: number | null;
  /** Historical data for sparklines */
  historyData?: GpuMetricDataPoint[];
  /** RT-DETRv2 model status */
  rtdetr?: AiModelStatus | null;
  /** Nemotron model status */
  nemotron?: AiModelStatus | null;
  /** Grafana URL for external link */
  grafanaUrl?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Determines color based on utilization percentage
 */
function getUtilizationColor(value: number | null): 'emerald' | 'amber' | 'red' | 'gray' {
  if (value === null) return 'gray';
  if (value < 70) return 'emerald';
  if (value < 90) return 'amber';
  return 'red';
}

/**
 * Determines color based on temperature
 */
function getTemperatureColor(temp: number | null): 'emerald' | 'amber' | 'red' | 'gray' {
  if (temp === null) return 'gray';
  if (temp < 70) return 'emerald';
  if (temp < 80) return 'amber';
  return 'red';
}

/**
 * Determines color based on memory usage percentage
 */
function getMemoryColor(used: number | null, total: number | null): 'emerald' | 'amber' | 'red' | 'gray' {
  if (used === null || total === null) return 'gray';
  const percentage = (used / total) * 100;
  if (percentage < 70) return 'emerald';
  if (percentage < 90) return 'amber';
  return 'red';
}

/**
 * Determines color based on power usage (watts)
 */
function getPowerColor(watts: number | null): 'emerald' | 'amber' | 'red' | 'gray' {
  if (watts === null) return 'gray';
  if (watts < 150) return 'emerald';
  if (watts < 250) return 'amber';
  return 'red';
}

/**
 * Get status icon based on model status
 */
function ModelStatusIcon({ status }: { status: AiModelStatus['status'] }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'unhealthy':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'loading':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    default:
      return <AlertTriangle className="h-4 w-4 text-gray-500" />;
  }
}

/**
 * Get badge color based on status
 */
function getModelBadgeColor(status: AiModelStatus['status']): 'green' | 'red' | 'yellow' | 'gray' {
  switch (status) {
    case 'healthy':
      return 'green';
    case 'unhealthy':
      return 'red';
    case 'loading':
      return 'yellow';
    default:
      return 'gray';
  }
}

/**
 * Format memory as GB
 */
function formatMemoryGB(mb: number | null): string {
  if (mb === null) return 'N/A';
  const gb = mb / 1024;
  return `${gb.toFixed(1)}GB`;
}

/**
 * Transform history data to sparkline format for a specific metric
 */
function transformToSparklineData(
  history: GpuMetricDataPoint[],
  metric: 'utilization' | 'temperature' | 'memory_used'
): { value: number }[] {
  return history.map((point) => ({
    value: metric === 'memory_used' ? point.memory_used / 1024 : point[metric],
  }));
}

/**
 * Transform history data for power sparkline (derived from utilization as proxy)
 * Since we don't have power history, we estimate based on utilization
 */
function transformToPowerSparklineData(
  history: GpuMetricDataPoint[],
  currentPower: number | null
): { value: number }[] {
  // Estimate power based on utilization (baseline + utilization factor)
  const basePower = 30; // Idle power
  const maxAdditional = currentPower ? currentPower - basePower : 200;

  return history.map((point) => ({
    value: basePower + (point.utilization / 100) * maxAdditional,
  }));
}

/**
 * SparklineRow - A single metric row with label, value, and sparkline
 */
interface SparklineRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  data: { value: number }[];
  color: 'emerald' | 'amber' | 'red' | 'gray';
  testId: string;
}

function SparklineRow({ icon, label, value, data, color, testId }: SparklineRowProps) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg bg-gray-800/30 px-3 py-2"
      data-testid={testId}
    >
      <div className="flex w-28 items-center gap-2 flex-shrink-0">
        {icon}
        <Text className="text-xs text-gray-400">{label}</Text>
      </div>
      <Text className="w-16 text-right text-sm font-semibold text-white flex-shrink-0">
        {value}
      </Text>
      <div className="flex-1 min-w-0">
        {data.length > 0 ? (
          <SparkAreaChart
            data={data}
            categories={['value']}
            index="value"
            colors={[color]}
            className="h-6 w-full"
            curveType="monotone"
          />
        ) : (
          <div className="h-6 flex items-center justify-center">
            <Text className="text-xs text-gray-600">No data</Text>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * AI Model mini-card component
 */
interface ModelMiniCardProps {
  model: AiModelStatus;
  testId: string;
}

function ModelMiniCard({ model, testId }: ModelMiniCardProps) {
  return (
    <div
      className={clsx(
        'flex flex-col rounded-lg border p-3',
        model.status === 'healthy' && 'border-gray-700 bg-gray-800/50',
        model.status === 'unhealthy' && 'border-red-500/30 bg-red-500/10',
        model.status === 'loading' && 'border-yellow-500/30 bg-yellow-500/10',
        model.status === 'unknown' && 'border-gray-700 bg-gray-800/50'
      )}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ModelStatusIcon status={model.status} />
          <Text className="text-sm font-medium text-white">{model.name}</Text>
        </div>
        <Badge color={getModelBadgeColor(model.status)} size="xs">
          {model.status === 'healthy' ? 'Running' : model.status}
        </Badge>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <Text className="text-gray-500">Latency</Text>
          <Text className="font-medium text-gray-300">{model.latency || 'N/A'}</Text>
        </div>
        <div>
          <Text className="text-gray-500">Count</Text>
          <Text className="font-medium text-gray-300">
            {model.count !== undefined ? model.count.toLocaleString() : 'N/A'}
          </Text>
        </div>
        <div>
          <Text className="text-gray-500">Errors</Text>
          <Text className={clsx('font-medium', model.errors && model.errors > 0 ? 'text-red-400' : 'text-gray-300')}>
            {model.errors !== undefined ? model.errors : 'N/A'}
          </Text>
        </div>
      </div>
    </div>
  );
}

/**
 * GpuStatistics - GPU metrics with stacked sparklines and AI model mini-cards
 *
 * Displays GPU metrics in a compact format with:
 * - 4 stacked sparkline rows (Utilization, Temperature, Memory, Power)
 * - Inference FPS prominent at bottom
 * - RT-DETRv2 and Nemotron mini-cards below
 * - Optional Grafana link
 *
 * Designed to replace the tabbed GPU graph with simultaneous visibility
 * of all metrics.
 *
 * @example
 * ```tsx
 * <GpuStatistics
 *   gpuName="NVIDIA RTX A5500"
 *   utilization={38}
 *   temperature={40}
 *   memoryUsed={200}
 *   memoryTotal={24576}
 *   powerUsage={31}
 *   inferenceFps={2.4}
 *   historyData={gpuHistory}
 *   rtdetr={{ name: 'RT-DETRv2', status: 'healthy', latency: '14ms', count: 1847, errors: 0 }}
 *   nemotron={{ name: 'Nemotron', status: 'healthy', latency: '2.1s', count: 64, errors: 0 }}
 * />
 * ```
 */
export default function GpuStatistics({
  gpuName,
  utilization,
  temperature,
  memoryUsed,
  memoryTotal,
  powerUsage,
  inferenceFps,
  historyData = [],
  rtdetr,
  nemotron,
  grafanaUrl,
  className,
}: GpuStatisticsProps) {
  // Prepare sparkline data
  const utilizationData = transformToSparklineData(historyData, 'utilization');
  const temperatureData = transformToSparklineData(historyData, 'temperature');
  const memoryData = transformToSparklineData(historyData, 'memory_used');
  const powerData = transformToPowerSparklineData(historyData, powerUsage ?? null);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="gpu-statistics-panel"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
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
        {grafanaUrl && (
          <a
            href={grafanaUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
            data-testid="grafana-link"
          >
            Open Grafana
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>

      {/* Stacked Sparklines */}
      <div className="mb-4 space-y-2">
        <SparklineRow
          icon={<Activity className="h-4 w-4 text-emerald-400" />}
          label="Utilization"
          value={utilization !== null && utilization !== undefined ? `${utilization}%` : 'N/A'}
          data={utilizationData}
          color={getUtilizationColor(utilization ?? null)}
          testId="gpu-utilization-row"
        />
        <SparklineRow
          icon={<Thermometer className="h-4 w-4 text-amber-400" />}
          label="Temperature"
          value={temperature !== null && temperature !== undefined ? `${temperature}\u00B0C` : 'N/A'}
          data={temperatureData}
          color={getTemperatureColor(temperature ?? null)}
          testId="gpu-temperature-row"
        />
        <SparklineRow
          icon={<HardDrive className="h-4 w-4 text-blue-400" />}
          label="Memory"
          value={
            memoryUsed !== undefined && memoryUsed !== null && memoryTotal !== undefined && memoryTotal !== null
              ? `${formatMemoryGB(memoryUsed)}/${formatMemoryGB(memoryTotal)}`
              : 'N/A'
          }
          data={memoryData}
          color={getMemoryColor(memoryUsed ?? null, memoryTotal ?? null)}
          testId="gpu-memory-row"
        />
        <SparklineRow
          icon={<Plug className="h-4 w-4 text-purple-400" />}
          label="Power"
          value={powerUsage !== null && powerUsage !== undefined ? `${powerUsage}W` : 'N/A'}
          data={powerData}
          color={getPowerColor(powerUsage ?? null)}
          testId="gpu-power-row"
        />
      </div>

      {/* Inference FPS */}
      <div
        className="mb-4 flex items-center justify-between rounded-lg bg-[#76B900]/10 px-4 py-3"
        data-testid="inference-fps-display"
      >
        <div className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-[#76B900]" />
          <Text className="text-sm font-medium text-gray-300">Inference FPS</Text>
        </div>
        <Text className="text-2xl font-bold text-[#76B900]">
          {inferenceFps !== null && inferenceFps !== undefined
            ? inferenceFps.toFixed(1)
            : 'N/A'}
        </Text>
      </div>

      {/* AI Model Mini-Cards */}
      {(rtdetr || nemotron) && (
        <div className="grid grid-cols-1 gap-3 border-t border-gray-800 pt-4 sm:grid-cols-2">
          {rtdetr && <ModelMiniCard model={rtdetr} testId="rtdetr-mini-card" />}
          {nemotron && <ModelMiniCard model={nemotron} testId="nemotron-mini-card" />}
        </div>
      )}
    </Card>
  );
}
