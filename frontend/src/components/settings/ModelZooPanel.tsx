/**
 * ModelZooPanel - Main admin panel for Model Zoo management
 *
 * Displays comprehensive model zoo information including:
 * - Per-GPU VRAM usage bars
 * - Models grouped by GPU assignment
 * - Disabled models section
 * - Service health indicators
 * - Summary statistics
 *
 * @see NEM-4790 - Frontend Admin Panel
 * @see docs/plans/2025-01-31-model-zoo-management-design.md
 */

import { Card, Text, Title, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import { Loader2, RefreshCw, ChevronDown, ChevronRight, MemoryStick, Server, AlertCircle } from 'lucide-react';
import { memo, useState, useCallback, useMemo } from 'react';

import ModelCard from './ModelCard';
import { useModels, useVRAMSummary, useLoadModel, useUnloadModel } from '../../hooks/useModelZoo';

import type { ModelStatus, GpuVRAMInfo } from '../../services/modelZooApi';

/**
 * Get color for VRAM progress bar based on utilization percentage
 */
function getVRAMColor(percent: number): 'emerald' | 'yellow' | 'orange' | 'red' {
  if (percent >= 90) return 'red';
  if (percent >= 70) return 'orange';
  if (percent >= 50) return 'yellow';
  return 'emerald';
}

/**
 * GPU labels for display
 */
const GPU_LABELS: Record<number, string> = {
  0: 'GPU 0 (Heavy Models)',
  1: 'GPU 1 (Light Models)',
};

/**
 * VRAMBar component displays VRAM usage for a single GPU
 */
interface VRAMBarProps {
  gpu: GpuVRAMInfo;
}

const VRAMBar = memo(function VRAMBar({ gpu }: VRAMBarProps) {
  const color = getVRAMColor(gpu.utilization_percent);
  const label = GPU_LABELS[gpu.gpu_id] ?? `GPU ${gpu.gpu_id}`;

  return (
    <div data-testid={`vram-bar-gpu-${gpu.gpu_id}`} className="rounded-lg bg-gray-800/50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MemoryStick className="h-4 w-4 text-[#76B900]" />
          <Text className="text-sm font-medium text-white">{label}</Text>
        </div>
        <Text className="text-sm text-gray-400">{gpu.service}</Text>
      </div>
      <div className="mb-1">
        <ProgressBar
          value={gpu.utilization_percent}
          color={color}
          className="h-2"
        />
        <div
          data-testid="vram-fill"
          className="hidden"
          style={{ width: `${gpu.utilization_percent.toFixed(1)}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-400">
        <span>
          <span className="text-white">{gpu.used_mb}</span> / {gpu.budget_mb} MB
        </span>
        <span className="text-[#76B900]">{gpu.utilization_percent.toFixed(1)}%</span>
      </div>
    </div>
  );
});

/**
 * GPUSection component displays models grouped by GPU with collapsible header
 */
interface GPUSectionProps {
  gpuId: number;
  models: ModelStatus[];
  serviceStatus: Record<string, string>;
  onLoadModel: (name: string) => void;
  onUnloadModel: (name: string) => void;
  loadingModel: string | null;
  loadingAction: 'load' | 'unload' | null;
}

const GPUSection = memo(function GPUSection({
  gpuId,
  models,
  serviceStatus,
  onLoadModel,
  onUnloadModel,
  loadingModel,
  loadingAction,
}: GPUSectionProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const label = GPU_LABELS[gpuId] ?? `GPU ${gpuId}`;
  const service = models[0]?.service ?? 'unknown';
  const health = serviceStatus[service] ?? 'unknown';
  const isHealthy = health === 'healthy';

  const handleToggle = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  return (
    <div data-testid={`gpu-section-${gpuId}`} className="rounded-lg border border-gray-800 bg-gray-900/50">
      {/* Section Header - Collapsible */}
      <button
        type="button"
        onClick={handleToggle}
        aria-label={label}
        aria-expanded={isExpanded}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-gray-800/50"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400" />
          )}
          <Server className="h-4 w-4 text-[#76B900]" />
          <Text className="font-semibold text-white">{label}</Text>
          <Text className="text-sm text-gray-400">({models.length} models)</Text>
        </div>
        <div className="flex items-center gap-2">
          <div
            data-testid="service-health-indicator"
            className={clsx(
              'h-2 w-2 rounded-full',
              isHealthy ? 'bg-emerald-500 healthy green' : 'bg-red-500 unhealthy red'
            )}
          />
          <Text className="text-xs text-gray-400">{service}</Text>
          {!isHealthy && <Text className="text-xs text-red-400">unhealthy</Text>}
        </div>
      </button>

      {/* Models Grid */}
      {isExpanded && (
        <div className="grid grid-cols-1 gap-4 p-4 pt-0 md:grid-cols-2 lg:grid-cols-3">
          {models.map((model) => (
            <ModelCard
              key={model.name}
              model={model}
              onLoad={onLoadModel}
              onUnload={onUnloadModel}
              isLoading={loadingModel === model.name}
              loadingAction={loadingModel === model.name ? loadingAction ?? undefined : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
});

/**
 * DisabledModelsSection displays disabled models in a separate section
 */
interface DisabledModelsSectionProps {
  models: ModelStatus[];
}

const DisabledModelsSection = memo(function DisabledModelsSection({
  models,
}: DisabledModelsSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleToggle = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  if (models.length === 0) return null;

  return (
    <div data-testid="disabled-models-section" className="rounded-lg border border-gray-800 bg-gray-900/50">
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={isExpanded}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-gray-800/50"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400" />
          )}
          <AlertCircle className="h-4 w-4 text-gray-500" />
          <Text className="font-semibold text-gray-400">Disabled Models</Text>
          <Text className="text-sm text-gray-500">({models.length} disabled)</Text>
        </div>
      </button>

      {isExpanded && (
        <div className="space-y-2 p-4 pt-0">
          {models.map((model) => (
            <div
              key={model.name}
              className="flex items-center justify-between rounded bg-gray-800/50 p-2 text-sm"
            >
              <Text className="text-gray-400">{model.name}</Text>
              <Text className="text-xs text-gray-500">{model.category}</Text>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

/**
 * ModelZooPanel main component
 */
const ModelZooPanel = memo(function ModelZooPanel() {
  const {
    models,
    serviceStatus,
    isLoading: modelsLoading,
    isRefetching: modelsRefetching,
    error: modelsError,
    refetch: modelsRefetch,
  } = useModels();

  const {
    gpus,
    data: vramData,
    isLoading: vramLoading,
    isRefetching: vramRefetching,
    refetch: vramRefetch,
  } = useVRAMSummary();

  const { loadModel, isLoading: loadLoading } = useLoadModel();
  const { unloadModel, isLoading: unloadLoading } = useUnloadModel();

  const [loadingModel, setLoadingModel] = useState<string | null>(null);
  const [loadingAction, setLoadingAction] = useState<'load' | 'unload' | null>(null);

  const isLoading = modelsLoading || vramLoading;
  const isRefetching = modelsRefetching || vramRefetching;
  const isAnyLoading = loadLoading || unloadLoading;

  // Group models by GPU
  const { disabledModels, modelsByGpu } = useMemo(() => {
    const enabled = models.filter((m) => m.enabled);
    const disabled = models.filter((m) => !m.enabled);

    const byGpu: Record<number, ModelStatus[]> = {};
    for (const model of enabled) {
      const gpuId = model.gpu_id;
      if (!byGpu[gpuId]) byGpu[gpuId] = [];
      byGpu[gpuId].push(model);
    }

    return { disabledModels: disabled, modelsByGpu: byGpu };
  }, [models]);

  // Calculate summary stats
  const summaryStats = useMemo(() => {
    const totalModels = models.length;
    const loadedModels = models.filter((m) => m.runtime?.loaded).length;

    return {
      totalModels,
      loadedModels,
      totalVram: vramData?.totals.used_mb ?? 0,
      budgetVram: vramData?.totals.budget_mb ?? 0,
    };
  }, [models, vramData]);

  const handleRefresh = useCallback(() => {
    void modelsRefetch();
    void vramRefetch();
  }, [modelsRefetch, vramRefetch]);

  const handleLoadModelAsync = useCallback(
    async (modelName: string) => {
      setLoadingModel(modelName);
      setLoadingAction('load');
      try {
        await loadModel(modelName);
      } finally {
        setLoadingModel(null);
        setLoadingAction(null);
      }
    },
    [loadModel]
  );

  const handleUnloadModelAsync = useCallback(
    async (modelName: string) => {
      setLoadingModel(modelName);
      setLoadingAction('unload');
      try {
        await unloadModel(modelName);
      } finally {
        setLoadingModel(null);
        setLoadingAction(null);
      }
    },
    [unloadModel]
  );

  // Wrapper functions that return void for passing to child components
  const handleLoadModel = useCallback(
    (modelName: string): void => {
      void handleLoadModelAsync(modelName);
    },
    [handleLoadModelAsync]
  );

  const handleUnloadModel = useCallback(
    (modelName: string): void => {
      void handleUnloadModelAsync(modelName);
    },
    [handleUnloadModelAsync]
  );

  // Loading state
  if (isLoading) {
    return (
      <Card
        data-testid="model-zoo-panel"
        role="region"
        aria-label="Model Zoo Management"
        className="border-gray-800 bg-[#1A1A1A] p-6"
      >
        <div className="flex items-center justify-center py-12">
          <Loader2 data-testid="loading-spinner" className="h-8 w-8 animate-spin text-[#76B900]" />
          <Text className="ml-3 text-gray-400">Loading model zoo...</Text>
        </div>
      </Card>
    );
  }

  // Error state
  if (modelsError) {
    return (
      <Card
        data-testid="model-zoo-panel"
        role="region"
        aria-label="Model Zoo Management"
        className="border-gray-800 bg-[#1A1A1A] p-6"
      >
        <div className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <Text className="mt-3 text-red-400">Error loading models</Text>
          <Text className="mt-1 text-sm text-gray-500">{modelsError.message}</Text>
          <button
            type="button"
            onClick={handleRefresh}
            aria-label="Retry"
            className="mt-4 rounded bg-[#76B900] px-4 py-2 text-sm font-medium text-white hover:bg-[#6aa800]"
          >
            Retry
          </button>
        </div>
      </Card>
    );
  }

  // Empty state
  if (models.length === 0) {
    return (
      <Card
        data-testid="model-zoo-panel"
        role="region"
        aria-label="Model Zoo Management"
        className="border-gray-800 bg-[#1A1A1A] p-6"
      >
        <div className="flex flex-col items-center justify-center py-12">
          <Server className="h-8 w-8 text-gray-500" />
          <Text className="mt-3 text-gray-400">No models available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card
      data-testid="model-zoo-panel"
      role="region"
      aria-label="Model Zoo Management"
      className="border-gray-800 bg-[#1A1A1A] p-6"
    >
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Title className="text-white">Model Zoo Management</Title>
          <Text className="text-gray-400">
            {summaryStats.totalModels} models | {summaryStats.loadedModels} loaded |{' '}
            {summaryStats.totalVram}/{summaryStats.budgetVram} MB VRAM
          </Text>
        </div>
        <div className="flex items-center gap-2">
          {isRefetching && (
            <Loader2
              data-testid="refreshing-indicator"
              className="h-4 w-4 animate-spin text-[#76B900]"
            />
          )}
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isRefetching || isAnyLoading}
            aria-label="Refresh"
            className={clsx(
              'rounded p-2 transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-[#76B900]/50',
              isRefetching || isAnyLoading
                ? 'cursor-not-allowed text-gray-600'
                : 'text-gray-400 hover:bg-gray-800 hover:text-white'
            )}
          >
            <RefreshCw className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* VRAM Section */}
      <section data-testid="vram-section" className="mb-6">
        <Text className="mb-3 text-sm font-medium text-gray-400">VRAM Usage</Text>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {gpus.map((gpu) => (
            <VRAMBar key={gpu.gpu_id} gpu={gpu} />
          ))}
        </div>
      </section>

      {/* GPU Sections */}
      <div className="space-y-4">
        {Object.entries(modelsByGpu)
          .sort(([a], [b]) => Number(a) - Number(b))
          .map(([gpuId, gpuModels]) => (
            <GPUSection
              key={gpuId}
              gpuId={Number(gpuId)}
              models={gpuModels}
              serviceStatus={serviceStatus}
              onLoadModel={handleLoadModel}
              onUnloadModel={handleUnloadModel}
              loadingModel={loadingModel}
              loadingAction={loadingAction}
            />
          ))}

        {/* Disabled Models */}
        <DisabledModelsSection models={disabledModels} />
      </div>
    </Card>
  );
});

export default ModelZooPanel;
