/**
 * GpuSettingsPage - GPU Configuration Management Page
 *
 * Provides a comprehensive interface for managing GPU assignments to AI services.
 * Allows users to:
 * - View detected GPU devices and their VRAM utilization
 * - Select assignment strategies (manual, VRAM-based, latency-optimized, etc.)
 * - Manually assign GPUs to specific services
 * - Preview strategy-based assignments before applying
 * - Save and apply configuration changes with service restart
 *
 * @module pages/GpuSettingsPage
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { AlertCircle, Cpu, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import GpuApplyButton from '../components/settings/GpuApplyButton';
import GpuAssignmentTable from '../components/settings/GpuAssignmentTable';
import GpuDeviceCard from '../components/settings/GpuDeviceCard';
import GpuStrategySelector from '../components/settings/GpuStrategySelector';
import {
  useGpus,
  useGpuConfig,
  useGpuStatus,
  useUpdateGpuConfig,
  useApplyGpuConfig,
  useDetectGpus,
  usePreviewStrategy,
} from '../hooks/useGpuConfig';

import type { GpuAssignment, GpuApplyResult } from '../hooks/useGpuConfig';

/**
 * GpuSettingsPage component for managing GPU configuration
 */
export default function GpuSettingsPage() {
  // ============================================================================
  // Data Fetching Hooks
  // ============================================================================

  const { gpus, isLoading: isLoadingGpus, error: gpusError, refetch: refetchGpus } = useGpus();

  const {
    data: config,
    isLoading: isLoadingConfig,
    error: configError,
    refetch: refetchConfig,
  } = useGpuConfig();

  // Enable status polling only when applying configuration
  const [isPollingStatus, setIsPollingStatus] = useState(false);
  const {
    data: statusData,
    isLoading: isLoadingStatus,
    refetch: refetchStatus,
  } = useGpuStatus(isPollingStatus);

  const { updateConfig, isLoading: isUpdating, error: updateError } = useUpdateGpuConfig();
  const { applyConfig, isLoading: isApplying, error: applyError } = useApplyGpuConfig();
  const { detect: detectGpus, isLoading: isDetecting } = useDetectGpus();
  const {
    preview: previewStrategy,
    isLoading: isPreviewLoading,
    error: previewError,
    data: previewData,
  } = usePreviewStrategy();

  // ============================================================================
  // Local State
  // ============================================================================

  const [localStrategy, setLocalStrategy] = useState<string>('');
  const [localAssignments, setLocalAssignments] = useState<GpuAssignment[]>([]);
  const [hasChanges, setHasChanges] = useState(false);
  const [lastApplyResult, setLastApplyResult] = useState<GpuApplyResult | null>(null);

  // Initialize local state from config
  useEffect(() => {
    if (config) {
      setLocalStrategy(config.strategy);
      setLocalAssignments(config.assignments);
      setHasChanges(false);
    }
  }, [config]);

  // Stop polling when all services are healthy
  useEffect(() => {
    if (isPollingStatus && statusData) {
      const allHealthy = statusData.services.every((s) => s.health === 'healthy');
      const noneRestarting = statusData.services.every((s) => !s.restart_status);
      if (allHealthy && noneRestarting) {
        setIsPollingStatus(false);
      }
    }
  }, [isPollingStatus, statusData]);

  // ============================================================================
  // Derived State
  // ============================================================================

  const isLoading = isLoadingGpus || isLoadingConfig;
  const error = gpusError || configError;

  // Create a map of GPU index to assigned services
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

  // ============================================================================
  // Handlers
  // ============================================================================

  const handleStrategyChange = useCallback((strategy: string) => {
    setLocalStrategy(strategy);
    setHasChanges(true);
    // Clear preview when strategy changes
    setLastApplyResult(null);
  }, []);

  const handleAssignmentChange = useCallback((service: string, gpuIndex: number | null) => {
    setLocalAssignments((prev) =>
      prev.map((a) => (a.service === service ? { ...a, gpu_index: gpuIndex } : a))
    );
    setHasChanges(true);
    setLastApplyResult(null);
  }, []);

  const handleVramOverrideChange = useCallback((service: string, vramOverride: number | null) => {
    setLocalAssignments((prev) =>
      prev.map((a) =>
        a.service === service ? { ...a, vram_budget_override: vramOverride } : a
      )
    );
    setHasChanges(true);
    setLastApplyResult(null);
  }, []);

  const handlePreview = useCallback(
    async (strategy: string) => {
      return previewStrategy(strategy);
    },
    [previewStrategy]
  );

  const handleSave = useCallback(async () => {
    await updateConfig({
      strategy: localStrategy,
      assignments: localAssignments,
    });
    setHasChanges(false);
    void refetchConfig();
  }, [localStrategy, localAssignments, updateConfig, refetchConfig]);

  const handleApply = useCallback(async () => {
    // First save the configuration
    await updateConfig({
      strategy: localStrategy,
      assignments: localAssignments,
    });

    // Start polling for status updates
    setIsPollingStatus(true);
    void refetchStatus();

    // Apply the configuration (restart services)
    const result = await applyConfig();
    setLastApplyResult(result);
    setHasChanges(false);

    // Refetch config after apply
    void refetchConfig();

    return result;
  }, [localStrategy, localAssignments, updateConfig, applyConfig, refetchConfig, refetchStatus]);

  const handleRescanGpus = useCallback(async () => {
    await detectGpus();
    void refetchGpus();
  }, [detectGpus, refetchGpus]);

  const handleRefresh = useCallback(() => {
    void refetchGpus();
    void refetchConfig();
    void refetchStatus();
  }, [refetchGpus, refetchConfig, refetchStatus]);

  // ============================================================================
  // Loading State
  // ============================================================================

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center" data-testid="loading-spinner">
        <LoadingSpinner />
      </div>
    );
  }

  // ============================================================================
  // Error State
  // ============================================================================

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

  // ============================================================================
  // Empty State (No GPUs)
  // ============================================================================

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
                label: 'Rescan GPUs',
                onClick: () => void handleRescanGpus(),
                variant: 'primary',
              },
            ]}
          />
        </div>
      </div>
    );
  }

  // ============================================================================
  // Main Render
  // ============================================================================

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="gpu-settings-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
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
            <Button
              variant="outline"
              size="sm"
              leftIcon={<Cpu className="h-4 w-4" />}
              onClick={() => void handleRescanGpus()}
              isLoading={isDetecting}
            >
              Rescan GPUs
            </Button>
          </div>
        </div>

        {/* GPU Device Cards */}
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

        {/* Strategy Selector and Assignment Table */}
        <div className="grid gap-8 lg:grid-cols-5">
          {/* Strategy Selector (narrower) */}
          <div className="lg:col-span-2">
            <GpuStrategySelector
              selectedStrategy={localStrategy}
              availableStrategies={config?.strategies ?? []}
              onStrategyChange={handleStrategyChange}
              onPreview={handlePreview}
              isPreviewLoading={isPreviewLoading}
              previewError={previewError?.message ?? null}
              previewData={previewData ?? null}
              disabled={isUpdating || isApplying}
            />
          </div>

          {/* Assignment Table (wider) */}
          <div className="lg:col-span-3">
            <GpuAssignmentTable
              assignments={localAssignments}
              gpus={gpus}
              serviceStatuses={statusData?.services ?? []}
              strategy={localStrategy}
              onAssignmentChange={handleAssignmentChange}
              onVramOverrideChange={handleVramOverrideChange}
              isLoading={isLoadingConfig || isLoadingStatus}
              hasPendingChanges={hasChanges}
            />
          </div>
        </div>

        {/* Apply Button Section */}
        <div className="mt-8">
          <GpuApplyButton
            hasChanges={hasChanges}
            onSave={handleSave}
            onApply={handleApply}
            isSaving={isUpdating}
            isApplying={isApplying}
            serviceStatuses={statusData?.services ?? []}
            lastApplyResult={lastApplyResult}
            error={updateError?.message ?? applyError?.message ?? null}
            disabled={isUpdating || isApplying}
          />
        </div>
      </div>
    </div>
  );
}
