import { Card, ProgressBar, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Brain, Cpu, Activity, Zap } from 'lucide-react';

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
 * Default model info for RT-DETRv2
 */
const DEFAULT_RTDETR: ModelInfo = {
  name: 'RT-DETRv2',
  status: 'unloaded',
  memoryUsed: null,
  inferenceFps: null,
  description: 'Real-time object detection model',
};

/**
 * Default model info for Nemotron
 */
const DEFAULT_NEMOTRON: ModelInfo = {
  name: 'Nemotron',
  status: 'unloaded',
  memoryUsed: null,
  inferenceFps: null,
  description: 'Risk analysis and reasoning model',
};

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
    <Card className="bg-[#1E1E1E] border-gray-800">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-[#76B900]" />
          <Title className="text-white">{model.name}</Title>
        </div>
        <Badge color={statusColor} size="sm">
          {statusText}
        </Badge>
      </div>

      <Text className="text-gray-400 text-sm mb-4">{model.description}</Text>

      <div className="space-y-3">
        {/* Memory Usage */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <Text className="text-gray-300 text-sm flex items-center gap-1.5">
              <Zap className="h-4 w-4" />
              Memory Usage
            </Text>
            <Text className="text-white font-medium text-sm">{memory.text}</Text>
          </div>
          {memory.percentage !== null && (
            <ProgressBar
              value={memory.percentage}
              color={statusColor}
              className="mt-1"
            />
          )}
        </div>

        {/* Inference Speed */}
        {model.status === 'loaded' && (
          <div className="pt-2 border-t border-gray-800">
            <div className="flex items-center justify-between">
              <Text className="text-gray-300 text-sm flex items-center gap-1.5">
                <Activity className="h-4 w-4" />
                Inference Speed
              </Text>
              <Text className="text-[#76B900] font-semibold">
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
 *
 * If model info is not provided, displays default placeholder data.
 */
export default function AIModelsSettings({
  rtdetrModel = DEFAULT_RTDETR,
  nemotronModel = DEFAULT_NEMOTRON,
  totalMemory = null,
  className,
}: AIModelsSettingsProps) {
  return (
    <div className={clsx('space-y-6', className)}>
      <div>
        <Title className="text-white mb-2">AI Models</Title>
        <Text className="text-gray-400">
          View the status and performance of AI models used for object detection and risk
          analysis.
        </Text>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ModelCard model={rtdetrModel} totalMemory={totalMemory} icon={Cpu} />
        <ModelCard model={nemotronModel} totalMemory={totalMemory} icon={Brain} />
      </div>

      {totalMemory !== null && (
        <Card className="bg-[#1A1A1A] border-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <Text className="text-gray-400 text-sm">Total GPU Memory</Text>
              <Text className="text-white font-semibold text-lg mt-1">
                {(totalMemory / 1024).toFixed(1)} GB
              </Text>
            </div>
            <Cpu className="h-8 w-8 text-[#76B900]" />
          </div>
        </Card>
      )}
    </div>
  );
}
