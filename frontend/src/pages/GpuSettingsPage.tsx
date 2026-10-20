/**
 * GpuSettingsPage - GPU Configuration Management Page (F-176, F-178, F-182).
 *
 * R2a row 36 retired F-177 (Rescan GPUs), F-179 (Assignment table & Save),
 * F-180 (Service-health column), F-181 (Apply), and F-183 (Import & Rollback).
 */

import { AlertCircle, Cpu, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import GpuBatchActions from '../components/settings/GpuBatchActions';
import GpuDeviceCard from '../components/settings/GpuDeviceCard';
import GpuStrategySelector from '../components/settings/GpuStrategySelector';
import GpuVersionHistory from '../components/settings/GpuVersionHistory';
import { useGpus, useGpuConfig, usePreviewStrategy } from '../hooks/useGpuConfig';

import type { GpuAssignment } from '../hooks/useGpuConfig';

const AVAILABLE_STRATEGIES = [
  'manual',
  'vram_based',
  'latency_optimized',
  'isolation_first',
  'balanced',
];

export default function GpuSettingsPage() {
  const { gpus, isLoading: isLoadingGpus, error: gpusError, refetch: refetchGpus } = useGpus();

  const {
    data: config,
    isLoading: isLoadingConfig,
    error: configError,
    refetch: refetchConfig,
  } = useGpuConfig();

  const {
    preview: previewStrategy,
    isLoading: isPreviewLoading,
    error: previewError,
    data: previewData,
  } = usePreviewStrategy();

  const [localStrategy, setLocalStrategy] = useState<string>('');
  const [localAssignments, setLocalAssignments] = useState<GpuAssignment[]>([]);

  useEffect(() => {
    if (config) {
      setLocalStrategy(config.strategy);
      setLocalAssignments(config.assignments);
    }
  }, [config]);

  const isLoading = isLoadingGpus || isLoadingConfig;
  const error = gpusError || configError;

  const gpuAssignmentsMap = useMemo(() => {
    const map = new Map<number, GpuAssignment[]>();
    localAssignments.forEach((assignment) => {
      if (assignment.gpu_index !== null) {
        const existing = map.get(assignment.gpu_index) ?? [];
        existing.push(assignment);
        map.set(assignment.gpu_index, existing);
      }
    });
    return map;
  }, [localAssignments]);

  const handleStrategyChange = useCallback((strategy: string) => {
    setLocalStrategy(strategy);
  }, []);

  const handlePreview = useCallback(
    async (strategy: string) => {
      return previewStrategy(strategy);
    },
    [previewStrategy]
  );

  const handleRefresh = useCallback(() => {
    void refetchGpus();
    void refetchConfig();
  }, [refetchGpus, refetchConfig]);

  const handleAssignAll = useCallback((gpuIndex: number) => {
    setLocalAssignments((prev) => prev.map((a) => ({ ...a, gpu_index: gpuIndex })));
  }, []);

  const handleResetDefaults = useCallback(() => {
    setLocalAssignments((prev) =>
      prev.map((a) => ({
        ...a,
        gpu_index: 0,
        vram_budget_override: null,
        exclusive_gpu: false,
        priority_weight: 50,
        incompatible_with: null,
      }))
    );
  }, []);

  const [isAutoBalancing, setIsAutoBalancing] = useState(false);
  const handleAutoBalance = useCallback(async () => {
    setIsAutoBalancing(true);
    try {
      const result = await previewStrategy('balanced');
      if (result && result.proposed_assignments) {
        setLocalAssignments(result.proposed_assignments);
      }
    } finally {
      setIsAutoBalancing(false);
    }
  }, [previewStrategy]);

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center" data-testid="loading-spinner">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6" data-testid="gpu-settings-page">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Failed to load GPU configuration</span>
          </div>
          <p className="mt-2 text-sm text-red-300">{error.message}</p>
          <button
            onClick={handleRefresh}
            className="mt-3 rounded bg-red-500/20 px-3 py-1 text-sm text-red-300 hover:bg-red-500/30"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (gpus.length === 0) {
    return (
      <div className="min-h-screen bg-[#121212] p-6" data-testid="gpu-settings-page">
        <div className="mx-auto max-w-[1400px]">
          <div className="mb-8">
            <h1 className="text-page-title">GPU Settings</h1>
            <p className="text-body-sm mt-2">Configure GPU assignments for AI services</p>
          </div>

          <EmptyState
            icon={Cpu}
            title="No GPUs Detected"
            description="No GPU devices were detected on this system. Ensure that your GPUs are properly installed and that the NVIDIA drivers are configured correctly."
            variant="warning"
            actions={[
              {
                label: 'Refresh',
                onClick: handleRefresh,
                variant: 'primary',
              },
            ]}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="gpu-settings-page">
      <div className="mx-auto max-w-[1400px]">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-page-title">GPU Settings</h1>
            <p className="text-body-sm mt-2">Configure GPU assignments for AI services</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<RefreshCw className="h-4 w-4" />}
              onClick={handleRefresh}
              disabled={isLoadingGpus || isLoadingConfig}
            >
              Refresh
            </Button>
          </div>
        </div>

        <section className="mb-8">
          <h2 className="mb-4 text-lg font-semibold text-white">Detected GPUs</h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {gpus.map((gpu) => (
              <GpuDeviceCard
                key={gpu.index}
                gpu={gpu}
                assignedServices={gpuAssignmentsMap.get(gpu.index) ?? []}
                isLoading={isLoadingGpus}
              />
            ))}
          </div>
        </section>

        <section className="mb-8 grid gap-4 lg:grid-cols-2">
          <GpuBatchActions
            gpus={gpus}
            assignments={localAssignments}
            disabled={false}
            onAssignAll={handleAssignAll}
            onResetDefaults={handleResetDefaults}
            onAutoBalance={() => void handleAutoBalance()}
            isAutoBalancing={isAutoBalancing}
          />

          <GpuVersionHistory disabled={false} />
        </section>

        <div className="grid gap-8 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <GpuStrategySelector
              selectedStrategy={localStrategy}
              availableStrategies={AVAILABLE_STRATEGIES}
              onStrategyChange={handleStrategyChange}
              onPreview={handlePreview}
              isPreviewLoading={isPreviewLoading}
              previewError={previewError?.message ?? null}
              previewData={previewData ?? null}
              disabled={false}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
