import { Card, ProgressBar, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Brain, Cpu, Activity, Zap, Loader2 } from 'lucide-react';

import { useAIMetrics, type AIModelStatus } from '../../hooks/useAIMetrics';

export interface ModelInfo {
  name: string;
  status: 'loaded' | 'unloaded' | 'error';
  memoryUsed: number | null; // MB
  inferenceFps: number | null;
  description: string;
}

export interface AIModelsSettingsProps {
  rtdetrModel?: ModelInfo;
  nemotronModel?: ModelInfo;
  totalMemory?: number | null; // MB
  className?: string;
}

/**
 * Gets status badge color based on model status
 */
function getStatusColor(status: 'loaded' | 'unloaded' | 'error'): 'green' | 'gray' | 'red' {
  switch (status) {
    case 'loaded':
      return 'green';
    case 'error':
      return 'red';
    case 'unloaded':
    default:
      return 'gray';
  }
}

/**
 * Gets status badge text
 */
function getStatusText(status: 'loaded' | 'unloaded' | 'error'): string {
  switch (status) {
    case 'loaded':
      return 'Loaded';
    case 'error':
      return 'Error';
    case 'unloaded':
    default:
      return 'Unloaded';
  }
}

/**
 * Formats a numeric value with fallback for null
 */
function formatValue(value: number | null, suffix: string = ''): string {
  return value !== null ? `${value.toFixed(0)}${suffix}` : 'N/A';
}

/**
 * Formats memory usage with percentage if total is available
 */
function formatMemory(
  used: number | null,
  total: number | null
): { text: string; percentage: number | null } {
  if (used === null) {
    return { text: 'N/A', percentage: null };
  }

  const usedGB = (used / 1024).toFixed(1);

  if (total !== null && total > 0) {
    const percentage = (used / total) * 100;
    return { text: `${usedGB} GB`, percentage };
  }

  return { text: `${usedGB} GB`, percentage: null };
}

/**
 * Maps backend AI model status to component status
 * Backend returns: 'healthy', 'unhealthy', 'unreachable', 'loading', 'degraded'
 * Component expects: 'loaded', 'unloaded', 'error'
 */
function mapBackendStatus(backendStatus: string | undefined): 'loaded' | 'unloaded' | 'error' {
  if (!backendStatus) {
    return 'unloaded';
  }
  switch (backendStatus.toLowerCase()) {
    case 'healthy':
      return 'loaded';
    case 'unreachable':
    case 'unhealthy':
    case 'error':
      return 'error';
    case 'loading':
    case 'degraded':
    default:
      return 'unloaded';
  }
}

/**
 * Transforms RT-DETRv2 status from useAIMetrics to ModelInfo format
 */
function transformRtdetrStatus(rtdetr: AIModelStatus | null): ModelInfo {
  if (!rtdetr) {
    return {
      name: 'RT-DETRv2',
      status: 'unloaded',
      memoryUsed: null,
      inferenceFps: null,
      description: 'Real-time object detection model',
    };
  }
  return {
    name: 'RT-DETRv2',
    status: mapBackendStatus(rtdetr.status),
    memoryUsed: null, // VRAM not available from health endpoint
    inferenceFps: null, // Not available from current metrics
    description: rtdetr.message
      ? `Real-time object detection model (${rtdetr.message})`
      : 'Real-time object detection model',
  };
}

/**
 * Transforms Nemotron status from useAIMetrics to ModelInfo format
 */
function transformNemotronStatus(nemotron: AIModelStatus | null): ModelInfo {
  if (!nemotron) {
    return {
      name: 'Nemotron',
      status: 'unloaded',
      memoryUsed: null,
      inferenceFps: null,
      description: 'Risk analysis and reasoning model',
    };
  }
  return {
    name: 'Nemotron',
    status: mapBackendStatus(nemotron.status),
    memoryUsed: null, // VRAM not tracked separately for Nemotron
    inferenceFps: null,
    description: nemotron.message
      ? `Risk analysis and reasoning model (${nemotron.message})`
      : 'Risk analysis and reasoning model',
  };
}

/**
 * ModelCard component displays individual model information
 */
function ModelCard({
  model,
  totalMemory,
  icon: Icon,
}: {
  model: ModelInfo;
  totalMemory: number | null;
  icon: React.ComponentType<{ className?: string }>;
}) {
  const memory = formatMemory(model.memoryUsed, totalMemory);
  const statusColor = getStatusColor(model.status);
  const statusText = getStatusText(model.status);

  return (
    <Card className="border-gray-800 bg-[#1E1E1E]">
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-[#76B900]" />
          <Title className="text-white">{model.name}</Title>
        </div>
        <Badge color={statusColor} size="sm">
          {statusText}
        </Badge>
      </div>

      <Text className="mb-4 text-sm text-gray-400">{model.description}</Text>

      <div className="space-y-3">
        {/* Memory Usage */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <Text className="flex items-center gap-1.5 text-sm text-gray-300">
              <Zap className="h-4 w-4" />
              Memory Usage
            </Text>
            <Text className="text-sm font-medium text-white">{memory.text}</Text>
          </div>
          {memory.percentage !== null && (
            <ProgressBar value={memory.percentage} color={statusColor} className="mt-1" />
          )}
        </div>

        {/* Inference Speed */}
        {model.status === 'loaded' && (
          <div className="border-t border-gray-800 pt-2">
            <div className="flex items-center justify-between">
              <Text className="flex items-center gap-1.5 text-sm text-gray-300">
                <Activity className="h-4 w-4" />
                Inference Speed
              </Text>
              <Text className="font-semibold text-[#76B900]">
                {formatValue(model.inferenceFps, ' FPS')}
              </Text>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/**
 * AIModelsSettings component displays AI model information and status
 *
 * Shows detailed information about the RT-DETRv2 detection model and
 * Nemotron risk analysis model including status, memory usage, and
 * performance metrics.
 *
 * Features:
 * - Model status indicators (loaded/unloaded/error)
 * - GPU memory usage per model
 * - Inference speed (FPS) when available
 * - NVIDIA dark theme styling
 * - Real-time updates via HTTP polling
 *
 * Fetches real AI model status from backend via useAIMetrics hook.
 * Falls back to default placeholder data if props are provided (for testing).
 */
export default function AIModelsSettings({
  rtdetrModel,
  nemotronModel,
  totalMemory,
  className,
}: AIModelsSettingsProps) {
  // Fetch real AI model status from backend via HTTP polling
  const { data: aiData, isLoading } = useAIMetrics({ pollingInterval: 5000 });

  // Transform backend status to component format (or use provided props for testing)
  const displayRtdetr = rtdetrModel ?? transformRtdetrStatus(aiData?.rtdetr ?? null);
  const displayNemotron = nemotronModel ?? transformNemotronStatus(aiData?.nemotron ?? null);

  // Use provided totalMemory prop (GPU memory not available from health endpoint)
  const gpuTotalMemory = totalMemory ?? null;

  return (
    <div className={clsx('space-y-6', className)}>
      <div>
        <div className="mb-2 flex items-center gap-2">
          <Title className="text-white">AI Models</Title>
          {isLoading && (
            <Badge color="yellow" size="sm">
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              Loading...
            </Badge>
          )}
        </div>
        <Text className="text-gray-400">
          View the status and performance of AI models used for object detection and risk analysis.
        </Text>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ModelCard model={displayRtdetr} totalMemory={gpuTotalMemory} icon={Cpu} />
        <ModelCard model={displayNemotron} totalMemory={gpuTotalMemory} icon={Brain} />
      </div>

      {gpuTotalMemory !== null && (
        <Card className="border-gray-800 bg-[#1A1A1A]">
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-sm text-gray-400">Total GPU Memory</Text>
              <Text className="mt-1 text-lg font-semibold text-white">
                {(gpuTotalMemory / 1024).toFixed(1)} GB
              </Text>
            </div>
            <Cpu className="h-8 w-8 text-[#76B900]" />
          </div>
        </Card>
      )}
    </div>
  );
}
