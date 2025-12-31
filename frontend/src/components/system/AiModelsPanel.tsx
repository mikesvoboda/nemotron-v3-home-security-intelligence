import { Card, Title, Text, Badge, DonutChart } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, Brain, HardDrive, Server, Layers } from 'lucide-react';

import type { AiModelMetrics, NemotronMetrics } from '../../types/performance';

export interface AiModelsPanelProps {
  /** RT-DETRv2 object detection model metrics (null when unavailable) */
  rtdetr: AiModelMetrics | null;
  /** Nemotron LLM model metrics (null when unavailable) */
  nemotron: NemotronMetrics | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Gets the badge color based on model status
 */
function getStatusColor(status: string): 'green' | 'yellow' | 'red' | 'gray' {
  switch (status) {
    case 'healthy':
      return 'green';
    case 'loading':
    case 'degraded':
      return 'yellow';
    case 'unhealthy':
    case 'error':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * AiModelsPanel - Displays RT-DETRv2 and Nemotron model metrics side by side.
 *
 * Shows two cards with model status, resource usage, and configuration:
 *
 * **RT-DETRv2 (Detection)**:
 * - Status badge (healthy/unhealthy/loading)
 * - VRAM usage with donut chart visualization
 * - Model name and CUDA device
 *
 * **Nemotron (LLM)**:
 * - Status badge
 * - Active inference slots (e.g., "1/2 active")
 * - Context window size in tokens
 *
 * Handles null values gracefully, showing "No data available" placeholder.
 *
 * @example
 * ```tsx
 * <AiModelsPanel
 *   rtdetr={{ status: 'healthy', vram_gb: 0.17, model: 'rtdetr_r50vd', device: 'cuda:0' }}
 *   nemotron={{ status: 'healthy', slots_active: 1, slots_total: 2, context_size: 4096 }}
 * />
 * ```
 */
export default function AiModelsPanel({
  rtdetr,
  nemotron,
  className,
}: AiModelsPanelProps) {
  // Prepare VRAM donut chart data for RT-DETRv2
  // Using 24GB as typical A5500 total VRAM for visualization
  const totalVram = 24;
  const rtdetrVram = rtdetr?.vram_gb ?? 0;
  const vramChartData = [
    { name: 'RT-DETRv2', value: rtdetrVram },
    { name: 'Available', value: totalVram - rtdetrVram },
  ];

  return (
    <div
      className={clsx('grid gap-4 md:grid-cols-2', className)}
      data-testid="ai-models-panel"
    >
      {/* RT-DETRv2 Card */}
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="rtdetr-card"
      >
        <div className="mb-4 flex items-center justify-between">
          <Title className="flex items-center gap-2 text-white">
            <Cpu className="h-5 w-5 text-[#76B900]" />
            RT-DETRv2
          </Title>
          {rtdetr ? (
            <Badge
              color={getStatusColor(rtdetr.status)}
              data-testid="rtdetr-status-badge"
            >
              {rtdetr.status}
            </Badge>
          ) : (
            <Badge color="gray" data-testid="rtdetr-status-badge">
              unknown
            </Badge>
          )}
        </div>

        {rtdetr ? (
          <div className="space-y-4">
            {/* VRAM Usage */}
            <div className="flex items-center gap-4">
              <DonutChart
                className="h-20 w-20"
                data={vramChartData}
                category="value"
                index="name"
                colors={['emerald', 'gray']}
                showAnimation={false}
                showTooltip={false}
                showLabel={false}
              />
              <div>
                <Text className="text-sm text-gray-400">VRAM Usage</Text>
                <Text className="text-lg font-semibold text-white">
                  {rtdetrVram.toFixed(2)} GB
                </Text>
              </div>
            </div>

            {/* Model Info */}
            <div className="space-y-2 border-t border-gray-800 pt-3">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-gray-500" />
                <Text className="text-sm text-gray-400">Model</Text>
                <Text className="ml-auto text-sm text-white">{rtdetr.model}</Text>
              </div>
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-gray-500" />
                <Text className="text-sm text-gray-400">Device</Text>
                <Text className="ml-auto text-sm text-white">{rtdetr.device}</Text>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex h-32 items-center justify-center">
            <Text className="text-gray-500">No data available</Text>
          </div>
        )}
      </Card>

      {/* Nemotron Card */}
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="nemotron-card"
      >
        <div className="mb-4 flex items-center justify-between">
          <Title className="flex items-center gap-2 text-white">
            <Brain className="h-5 w-5 text-[#76B900]" />
            Nemotron
          </Title>
          {nemotron ? (
            <Badge
              color={getStatusColor(nemotron.status)}
              data-testid="nemotron-status-badge"
            >
              {nemotron.status}
            </Badge>
          ) : (
            <Badge color="gray" data-testid="nemotron-status-badge">
              unknown
            </Badge>
          )}
        </div>

        {nemotron ? (
          <div className="space-y-4">
            {/* Slots Info */}
            <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3">
              <div className="flex items-center gap-2">
                <HardDrive className="h-4 w-4 text-gray-400" />
                <Text className="text-sm text-gray-300">Inference Slots</Text>
              </div>
              <Text className="font-semibold text-white">
                {nemotron.slots_active}/{nemotron.slots_total} active
              </Text>
            </div>

            {/* Context Size */}
            <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-gray-400" />
                <Text className="text-sm text-gray-300">Context Size</Text>
              </div>
              <Text className="font-semibold text-white">
                {nemotron.context_size.toLocaleString()} tokens
              </Text>
            </div>

            {/* Slots utilization bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-gray-500">
                <span>Slot Utilization</span>
                <span>
                  {nemotron.slots_total > 0
                    ? Math.round((nemotron.slots_active / nemotron.slots_total) * 100)
                    : 0}%
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-gray-700">
                <div
                  className="h-full rounded-full bg-[#76B900] transition-all duration-300"
                  style={{
                    width: `${nemotron.slots_total > 0 ? (nemotron.slots_active / nemotron.slots_total) * 100 : 0}%`,
                  }}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="flex h-32 items-center justify-center">
            <Text className="text-gray-500">No data available</Text>
          </div>
        )}
      </Card>
    </div>
  );
}
