import { Card, Title, Text, Badge, DonutChart } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, Brain, HardDrive, Server, Layers } from 'lucide-react';

import type { AiModelMetrics, NemotronMetrics } from '../../types/performance';

/**
 * Union type for all AI model metrics.
 * Detection models have vram_gb, LLM models have slots_active/context_size.
 */
export type AiModelData = AiModelMetrics | NemotronMetrics;

export interface AiModelsPanelProps {
  /**
   * Dictionary of AI model metrics keyed by model name.
   * Supports both detection models (RT-DETRv2) and LLM models (Nemotron).
   * Pass null or undefined for individual models that are unavailable.
   */
  aiModels?: Record<string, AiModelData | null> | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Type guard to check if the model metrics are for a detection model (RT-DETRv2).
 * Detection models have vram_gb, model, and device properties.
 */
function isDetectionModel(model: AiModelData): model is AiModelMetrics {
  return 'vram_gb' in model && 'device' in model;
}

/**
 * Type guard to check if the model metrics are for an LLM model (Nemotron).
 * LLM models have slots_active, slots_total, and context_size properties.
 */
function isLlmModel(model: AiModelData): model is NemotronMetrics {
  return 'slots_active' in model && 'context_size' in model;
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
    case 'unreachable':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Formats a model key into a human-readable display name.
 * e.g., 'rtdetr' -> 'RT-DETRv2', 'nemotron' -> 'Nemotron'
 */
function getDisplayName(key: string): string {
  const knownNames: Record<string, string> = {
    rtdetr: 'RT-DETRv2',
    nemotron: 'Nemotron',
  };
  return knownNames[key.toLowerCase()] || key.charAt(0).toUpperCase() + key.slice(1);
}

interface DetectionModelCardProps {
  modelKey: string;
  metrics: AiModelMetrics | null;
}

/**
 * Card component for displaying detection model metrics (RT-DETRv2).
 */
function DetectionModelCard({ modelKey, metrics }: DetectionModelCardProps) {
  const totalVram = 24; // Typical A5500 total VRAM for visualization
  const vram = metrics?.vram_gb ?? 0;
  const vramChartData = [
    { name: getDisplayName(modelKey), value: vram },
    { name: 'Available', value: totalVram - vram },
  ];

  const displayName = getDisplayName(modelKey);
  const testId = `${modelKey}-card`;
  const statusTestId = `${modelKey}-status-badge`;

  return (
    <Card
      className="border-gray-800 bg-[#1A1A1A] shadow-lg"
      data-testid={testId}
    >
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Cpu className="h-5 w-5 text-[#76B900]" />
          {displayName}
        </Title>
        {metrics ? (
          <Badge
            color={getStatusColor(metrics.status)}
            data-testid={statusTestId}
          >
            {metrics.status}
          </Badge>
        ) : (
          <Badge color="gray" data-testid={statusTestId}>
            unknown
          </Badge>
        )}
      </div>

      {metrics ? (
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
                {vram.toFixed(2)} GB
              </Text>
            </div>
          </div>

          {/* Model Info */}
          <div className="space-y-2 border-t border-gray-800 pt-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-gray-500" />
              <Text className="text-sm text-gray-400">Model</Text>
              <Text className="ml-auto text-sm text-white">{metrics.model}</Text>
            </div>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-gray-500" />
              <Text className="text-sm text-gray-400">Device</Text>
              <Text className="ml-auto text-sm text-white">{metrics.device}</Text>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex h-32 items-center justify-center">
          <Text className="text-gray-500">No data available</Text>
        </div>
      )}
    </Card>
  );
}

interface LlmModelCardProps {
  modelKey: string;
  metrics: NemotronMetrics | null;
}

/**
 * Card component for displaying LLM model metrics (Nemotron).
 */
function LlmModelCard({ modelKey, metrics }: LlmModelCardProps) {
  const displayName = getDisplayName(modelKey);
  const testId = `${modelKey}-card`;
  const statusTestId = `${modelKey}-status-badge`;

  return (
    <Card
      className="border-gray-800 bg-[#1A1A1A] shadow-lg"
      data-testid={testId}
    >
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Brain className="h-5 w-5 text-[#76B900]" />
          {displayName}
        </Title>
        {metrics ? (
          <Badge
            color={getStatusColor(metrics.status)}
            data-testid={statusTestId}
          >
            {metrics.status}
          </Badge>
        ) : (
          <Badge color="gray" data-testid={statusTestId}>
            unknown
          </Badge>
        )}
      </div>

      {metrics ? (
        <div className="space-y-4">
          {/* Slots Info */}
          <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3">
            <div className="flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-gray-400" />
              <Text className="text-sm text-gray-300">Inference Slots</Text>
            </div>
            <Text className="font-semibold text-white">
              {metrics.slots_active}/{metrics.slots_total} active
            </Text>
          </div>

          {/* Context Size */}
          <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-gray-400" />
              <Text className="text-sm text-gray-300">Context Size</Text>
            </div>
            <Text className="font-semibold text-white">
              {metrics.context_size.toLocaleString()} tokens
            </Text>
          </div>

          {/* Slots utilization bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-gray-500">
              <span>Slot Utilization</span>
              <span>
                {metrics.slots_total > 0
                  ? Math.round((metrics.slots_active / metrics.slots_total) * 100)
                  : 0}%
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-gray-700">
              <div
                className="h-full rounded-full bg-[#76B900] transition-all duration-300"
                style={{
                  width: `${metrics.slots_total > 0 ? (metrics.slots_active / metrics.slots_total) * 100 : 0}%`,
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
  );
}

/**
 * AiModelsPanel - Dynamically renders AI model metrics from the ai_models dictionary.
 *
 * Automatically detects model type based on properties present:
 * - **Detection models** (RT-DETRv2): Have `vram_gb`, `model`, `device` properties
 * - **LLM models** (Nemotron): Have `slots_active`, `slots_total`, `context_size` properties
 *
 * Each model type gets a specialized card:
 *
 * **Detection Card**:
 * - Status badge (healthy/unhealthy/loading)
 * - VRAM usage with donut chart visualization
 * - Model name and CUDA device
 *
 * **LLM Card**:
 * - Status badge
 * - Active inference slots (e.g., "1/2 active")
 * - Context window size in tokens
 * - Slot utilization bar
 *
 * Handles null/undefined values gracefully, showing "No data available" placeholder.
 *
 * @example
 * ```tsx
 * <AiModelsPanel
 *   aiModels={{
 *     rtdetr: { status: 'healthy', vram_gb: 0.17, model: 'rtdetr_r50vd', device: 'cuda:0' },
 *     nemotron: { status: 'healthy', slots_active: 1, slots_total: 2, context_size: 4096 },
 *   }}
 * />
 * ```
 */
export default function AiModelsPanel({
  aiModels,
  className,
}: AiModelsPanelProps) {
  // If no models provided OR empty object, show empty state with known models
  // Check both null/undefined AND empty object cases
  const hasModels = aiModels && Object.keys(aiModels).length > 0;
  const models = hasModels ? aiModels : { rtdetr: null, nemotron: null };

  // Sort entries to ensure consistent ordering (rtdetr first, then others alphabetically)
  const sortedEntries = Object.entries(models).sort(([a], [b]) => {
    // Put rtdetr first, nemotron second, then alphabetically
    const order: Record<string, number> = { rtdetr: 0, nemotron: 1 };
    const orderA = order[a.toLowerCase()] ?? 99;
    const orderB = order[b.toLowerCase()] ?? 99;
    if (orderA !== orderB) return orderA - orderB;
    return a.localeCompare(b);
  });

  return (
    <div
      className={clsx('grid gap-4 md:grid-cols-2', className)}
      data-testid="ai-models-panel"
    >
      {sortedEntries.map(([key, modelData]) => {
        // Determine model type and render appropriate card
        if (modelData && isLlmModel(modelData)) {
          return (
            <LlmModelCard
              key={key}
              modelKey={key}
              metrics={modelData}
            />
          );
        }

        // Default to detection model card (for rtdetr or unknown detection models)
        return (
          <DetectionModelCard
            key={key}
            modelKey={key}
            metrics={modelData && isDetectionModel(modelData) ? modelData : null}
          />
        );
      })}
    </div>
  );
}
