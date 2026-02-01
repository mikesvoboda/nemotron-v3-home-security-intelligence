/**
 * BaselineTuningPanel - Per-camera baseline configuration UI
 *
 * Allows users to:
 * - Adjust anomaly detection sensitivity (threshold_stdev: 0.5-5.0)
 * - Set minimum samples required (min_samples: >= 1)
 * - Toggle between global and per-camera settings
 * - Reset baseline data for a camera
 *
 * @see NEM-4921 - Phase 3: Baseline Tuning UI
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Save, RotateCcw, AlertTriangle, X } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import { useBaselineConfigQuery, baselineConfigKeys } from '../../hooks/useBaselineConfig';
import {
  updateBaselineConfig,
  resetCameraBaseline,
  type BaselineConfigUpdate,
} from '../../services/baselineConfigApi';

// ============================================================================
// Types
// ============================================================================

interface BaselineTuningPanelProps {
  /** Camera ID to configure */
  cameraId: string;
}

// ============================================================================
// Validation Helpers (stateless, extracted for clarity)
// ============================================================================

/** Validate threshold is within acceptable range (0.5-5.0) */
function validateThreshold(value: number): string | undefined {
  if (value < 0.5) return 'Must be at least 0.5';
  if (value > 5.0) return 'Must be at most 5.0';
  return undefined;
}

/** Validate minimum samples is at least 1 */
function validateMinSamples(value: number): string | undefined {
  if (value < 1) return 'Must be at least 1';
  return undefined;
}

// ============================================================================
// Component
// ============================================================================

/**
 * BaselineTuningPanel displays and allows editing of per-camera baseline settings.
 *
 * Features:
 * - Sensitivity slider with validation (0.5-5.0)
 * - Minimum samples input with validation (>= 1)
 * - Toggle between global and custom settings
 * - Reset baseline data with confirmation
 * - Unsaved changes indicator
 */
export default function BaselineTuningPanel({ cameraId }: BaselineTuningPanelProps) {
  const queryClient = useQueryClient();

  // Local form state
  const [threshold, setThreshold] = useState(2.0);
  const [minSamples, setMinSamples] = useState(10);
  const [overrideGlobal, setOverrideGlobal] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [validationErrors, setValidationErrors] = useState<{
    threshold?: string;
    minSamples?: string;
  }>({});

  // Toast state for feedback
  const [toast, setToast] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  // Query for current config (using shared hook for consistent cache keys)
  const {
    data: config,
    isLoading,
    isError,
    error,
  } = useBaselineConfigQuery(cameraId);

  // Mutation for updating config
  const updateMutation = useMutation({
    mutationFn: (update: BaselineConfigUpdate) => updateBaselineConfig(cameraId, update),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: baselineConfigKeys.config(cameraId) });
      setHasChanges(false);
      setToast({ type: 'success', message: 'Settings saved successfully' });
    },
    onError: (err: Error) => {
      setToast({ type: 'error', message: `Failed to save: ${err.message}` });
    },
  });

  // Mutation for resetting baseline
  const resetMutation = useMutation({
    mutationFn: () => resetCameraBaseline(cameraId),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: baselineConfigKeys.config(cameraId) });
      void queryClient.invalidateQueries({ queryKey: baselineConfigKeys.baseline(cameraId) });
      setShowResetModal(false);
      setToast({
        type: 'success',
        message: `Baseline reset successfully. ${result.activity_baselines_deleted} activity baselines deleted. ${result.class_baselines_deleted} class baselines deleted.`,
      });
    },
    onError: (err: Error) => {
      setShowResetModal(false);
      setToast({ type: 'error', message: `Failed to reset baseline: ${err.message}` });
    },
  });

  // Sync form state with loaded config
  useEffect(() => {
    if (config) {
      setThreshold(config.threshold_stdev);
      setMinSamples(config.min_samples);
      setOverrideGlobal(config.override_global_config);
      setHasChanges(false);
      setValidationErrors({});
    }
  }, [config]);

  // Track changes
  useEffect(() => {
    if (config) {
      const changed =
        threshold !== config.threshold_stdev ||
        minSamples !== config.min_samples ||
        overrideGlobal !== config.override_global_config;
      setHasChanges(changed);
    }
  }, [threshold, minSamples, overrideGlobal, config]);

  // Clear toast after delay
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Handle threshold change with inline validation
  const handleThresholdChange = useCallback((value: number) => {
    setThreshold(value);
    setValidationErrors((prev) => ({ ...prev, threshold: validateThreshold(value) }));
  }, []);

  // Handle min samples change with inline validation
  const handleMinSamplesChange = useCallback((value: number) => {
    setMinSamples(value);
    setValidationErrors((prev) => ({ ...prev, minSamples: validateMinSamples(value) }));
  }, []);

  // Handle toggle override
  const handleToggleOverride = useCallback((enabled: boolean) => {
    setOverrideGlobal(enabled);
    setHasChanges(true);
  }, []);

  // Handle save with validation
  const handleSave = useCallback(() => {
    const thresholdError = validateThreshold(threshold);
    const minSamplesError = validateMinSamples(minSamples);

    if (thresholdError || minSamplesError) {
      setValidationErrors({ threshold: thresholdError, minSamples: minSamplesError });
      return;
    }

    updateMutation.mutate({
      threshold_stdev: threshold,
      min_samples: minSamples,
      override_global_config: overrideGlobal,
    });
  }, [threshold, minSamples, overrideGlobal, updateMutation]);

  // Handle reset
  const handleReset = useCallback(() => {
    resetMutation.mutate();
  }, [resetMutation]);

  // Loading state
  if (isLoading) {
    return (
      <div
        data-testid="baseline-tuning-panel"
        className="flex items-center justify-center p-8"
      >
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        <span className="ml-2 text-gray-400">Loading baseline configuration...</span>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div
        data-testid="baseline-tuning-panel"
        className="rounded-lg border border-red-500/20 bg-red-500/10 p-4"
      >
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle className="h-5 w-5" />
          <span>Error loading baseline config: {error?.message}</span>
        </div>
      </div>
    );
  }

  const isInputsDisabled = !overrideGlobal;

  return (
    <div
      data-testid="baseline-tuning-panel"
      className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Baseline Tuning</h3>
        <div className="flex items-center gap-2">
          {hasChanges && (
            <span className="text-sm text-yellow-400">Unsaved changes</span>
          )}
          <button
            onClick={handleSave}
            disabled={!hasChanges || updateMutation.isPending}
            className="flex items-center gap-2 rounded bg-[#76B900] px-3 py-1.5 text-sm font-medium text-black transition-colors hover:bg-[#8BD000] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Save"
          >
            {updateMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`mb-4 flex items-center justify-between rounded px-3 py-2 text-sm ${
            toast.type === 'success'
              ? 'bg-green-500/10 text-green-400'
              : 'bg-red-500/10 text-red-400'
          }`}
        >
          <span>{toast.message}</span>
          <button onClick={() => setToast(null)} className="ml-2">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Settings mode toggle */}
      <div className="mb-6 rounded-lg border border-gray-700 bg-gray-800/30 p-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-gray-300">
              Settings Mode
            </span>
            <p className="text-xs text-gray-500">
              {overrideGlobal
                ? 'Custom Override - Using per-camera settings'
                : 'Using Global Settings'}
            </p>
          </div>
          <button
            onClick={() => handleToggleOverride(!overrideGlobal)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              overrideGlobal ? 'bg-[#76B900]' : 'bg-gray-600'
            }`}
            role="switch"
            aria-checked={overrideGlobal}
            aria-label="Custom Override"
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                overrideGlobal ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Sensitivity slider */}
      <div className="mb-6 rounded-lg border border-gray-700 bg-gray-800/30 p-4">
        <label
          htmlFor="sensitivity-slider"
          className="mb-2 block text-sm font-medium text-gray-300"
        >
          Sensitivity (Threshold)
        </label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            id="sensitivity-slider"
            data-testid="sensitivity-slider"
            min="0"
            max="10"
            step="0.1"
            value={threshold}
            onChange={(e) => handleThresholdChange(parseFloat(e.target.value))}
            disabled={isInputsDisabled}
            className="nvidia-slider flex-1"
            aria-valuemin={0.5}
            aria-valuemax={5.0}
            aria-valuenow={threshold}
          />
          <input
            type="number"
            value={threshold.toFixed(1)}
            onChange={(e) => handleThresholdChange(parseFloat(e.target.value) || 0.5)}
            disabled={isInputsDisabled}
            className="nvidia-input w-20 text-center"
            aria-label="Threshold numeric input"
            step="0.1"
          />
        </div>
        {validationErrors.threshold && (
          <p className="error mt-1 text-sm text-red-400">{validationErrors.threshold}</p>
        )}
        <p className="mt-1 text-xs text-gray-500">
          Lower values = more sensitive (more false positives), higher = less sensitive
        </p>
      </div>

      {/* Minimum samples input */}
      <div className="mb-6 rounded-lg border border-gray-700 bg-gray-800/30 p-4">
        <label
          htmlFor="min-samples-input"
          className="mb-2 block text-sm font-medium text-gray-300"
        >
          Minimum Samples
        </label>
        <div className="flex items-center gap-3">
          <input
            type="number"
            id="min-samples-input"
            data-testid="min-samples-input"
            value={minSamples}
            onChange={(e) => handleMinSamplesChange(parseInt(e.target.value) || 0)}
            disabled={isInputsDisabled}
            className="nvidia-input w-28 text-center"
            aria-label="Minimum Samples"
          />
          <span className="text-sm text-gray-400">samples</span>
        </div>
        {validationErrors.minSamples && (
          <p className="error mt-1 text-sm text-red-400">{validationErrors.minSamples}</p>
        )}
        <p className="mt-1 text-xs text-gray-500">
          Number of samples required before anomaly detection is reliable
        </p>
      </div>

      {/* Global config reference */}
      {config?.global_config && (
        <div className="mb-6 rounded-lg border border-gray-700 bg-gray-800/20 p-4">
          <h4 className="mb-2 text-sm font-medium text-gray-400">Global Defaults</h4>
          <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
            <div>Threshold: {config.global_config.threshold_stdev} std</div>
            <div>Min Samples: {config.global_config.min_samples}</div>
            <div>Decay Factor: {config.global_config.decay_factor}</div>
            <div>Window: {config.global_config.window_days} days</div>
          </div>
        </div>
      )}

      {/* Reset baseline button */}
      <div className="border-t border-gray-800 pt-4">
        <button
          onClick={() => setShowResetModal(true)}
          disabled={resetMutation.isPending}
          data-testid="reset-baseline-button"
          className="flex items-center gap-2 rounded border border-red-500/50 bg-red-500/10 px-3 py-2 text-sm text-red-400 transition-colors hover:bg-red-500/20"
          aria-label="Reset Baseline"
        >
          <RotateCcw className="h-4 w-4" />
          Reset Baseline
        </button>
        <p className="mt-2 text-xs text-gray-500">
          This will delete all learned baseline data for this camera. The system will need
          to re-learn activity patterns.
        </p>
      </div>

      {/* Reset confirmation modal */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border border-gray-700 bg-[#1F1F1F] p-6 shadow-xl">
            <h3 className="mb-2 text-lg font-semibold text-white">Confirm Reset</h3>
            <p className="mb-4 text-sm text-gray-400">
              Are you sure you want to reset all baseline data for this camera? This action
              cannot be undone. The system will need to re-learn activity patterns from
              new detections.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowResetModal(false)}
                className="rounded px-4 py-2 text-sm text-gray-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleReset}
                disabled={resetMutation.isPending}
                className="flex items-center gap-2 rounded bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-50"
                aria-label="Confirm"
              >
                {resetMutation.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
