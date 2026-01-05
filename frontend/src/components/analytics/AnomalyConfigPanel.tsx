import { AlertTriangle, Info, Save, Loader2 } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import { updateAnomalyConfig } from '../../services/api';

import type { AnomalyConfig, AnomalyConfigUpdate } from '../../services/api';

interface AnomalyConfigPanelProps {
  /** Current anomaly configuration */
  config: AnomalyConfig;
  /** Callback when config is updated */
  onConfigUpdated?: (config: AnomalyConfig) => void;
}

/**
 * AnomalyConfigPanel displays and allows editing of anomaly detection settings.
 *
 * Shows:
 * - Threshold slider (standard deviations)
 * - Minimum samples input
 * - Read-only display of decay factor and window days
 */
export default function AnomalyConfigPanel({
  config,
  onConfigUpdated,
}: AnomalyConfigPanelProps) {
  const [threshold, setThreshold] = useState(config.threshold_stdev);
  const [minSamples, setMinSamples] = useState(config.min_samples);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Reset local state when config changes externally
  useEffect(() => {
    setThreshold(config.threshold_stdev);
    setMinSamples(config.min_samples);
    setHasChanges(false);
  }, [config.threshold_stdev, config.min_samples]);

  // Check for changes
  useEffect(() => {
    const changed =
      threshold !== config.threshold_stdev || minSamples !== config.min_samples;
    setHasChanges(changed);
  }, [threshold, minSamples, config.threshold_stdev, config.min_samples]);

  const handleSave = useCallback(async () => {
    if (!hasChanges) return;

    setIsSaving(true);
    setError(null);

    try {
      const update: AnomalyConfigUpdate = {};
      if (threshold !== config.threshold_stdev) {
        update.threshold_stdev = threshold;
      }
      if (minSamples !== config.min_samples) {
        update.min_samples = minSamples;
      }

      const updatedConfig = await updateAnomalyConfig(update);
      onConfigUpdated?.(updatedConfig);
      setHasChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update configuration');
    } finally {
      setIsSaving(false);
    }
  }, [hasChanges, threshold, minSamples, config, onConfigUpdated]);

  // Get sensitivity description based on threshold
  const getSensitivityDescription = (stdev: number): { label: string; color: string } => {
    if (stdev <= 1.5) return { label: 'Very High', color: 'text-red-400' };
    if (stdev <= 2.0) return { label: 'High', color: 'text-orange-400' };
    if (stdev <= 2.5) return { label: 'Medium', color: 'text-yellow-400' };
    if (stdev <= 3.0) return { label: 'Low', color: 'text-green-400' };
    return { label: 'Very Low', color: 'text-blue-400' };
  };

  const sensitivity = getSensitivityDescription(threshold);

  return (
    <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Anomaly Detection Settings</h3>
        {hasChanges && (
          <button
            onClick={() => void handleSave()}
            disabled={isSaving}
            className="flex items-center gap-2 rounded bg-[#76B900] px-3 py-1.5 text-sm font-medium text-black transition-colors hover:bg-[#8BD000] disabled:opacity-50"
            data-testid="save-config-button"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save Changes
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="space-y-6">
        {/* Threshold Slider */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label htmlFor="threshold-slider" className="text-sm text-gray-300">
              Detection Threshold
            </label>
            <span className={`text-sm font-medium ${sensitivity.color}`}>
              Sensitivity: {sensitivity.label}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <input
              type="range"
              id="threshold-slider"
              min="1"
              max="4"
              step="0.1"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
              data-testid="threshold-slider"
            />
            <span className="w-16 text-right text-sm text-white">{threshold.toFixed(1)} std</span>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Lower values = more sensitive (more false positives), higher = less sensitive
          </p>
        </div>

        {/* Minimum Samples */}
        <div>
          <label htmlFor="min-samples" className="mb-2 block text-sm text-gray-300">
            Minimum Samples for Detection
          </label>
          <input
            type="number"
            id="min-samples"
            min="1"
            max="100"
            value={minSamples}
            onChange={(e) => setMinSamples(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-24 rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none"
            data-testid="min-samples-input"
          />
          <p className="mt-1 text-xs text-gray-500">
            Number of samples required before anomaly detection is reliable
          </p>
        </div>

        {/* Read-only Settings */}
        <div className="border-t border-gray-800 pt-4">
          <div className="mb-2 flex items-center gap-2 text-sm text-gray-400">
            <Info className="h-4 w-4" />
            <span>System-managed settings</span>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Decay Factor:</span>
              <span className="ml-2 text-gray-300">{config.decay_factor}</span>
            </div>
            <div>
              <span className="text-gray-500">Window:</span>
              <span className="ml-2 text-gray-300">{config.window_days} days</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
