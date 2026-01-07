import { Card, Title, Text, Button } from '@tremor/react';
import { Settings, Save, RotateCcw, AlertTriangle, CheckCircle } from 'lucide-react';
import { useState, useEffect } from 'react';

import {
  fetchAnomalyConfig,
  updateAnomalyConfig,
  type AnomalyConfig,
  type AnomalyConfigUpdate,
} from '../../services/api';

export interface AnomalyConfigPanelProps {
  /** Optional className for styling */
  className?: string;
  /** Callback when config is updated successfully */
  onConfigUpdate?: (config: AnomalyConfig) => void;
}

/**
 * AnomalyConfigPanel allows viewing and editing anomaly detection configuration.
 * - Threshold (standard deviations): Controls sensitivity
 * - Minimum samples: Controls when anomaly detection becomes active
 */
export default function AnomalyConfigPanel({
  className = '',
  onConfigUpdate,
}: AnomalyConfigPanelProps) {
  const [config, setConfig] = useState<AnomalyConfig | null>(null);
  const [editedConfig, setEditedConfig] = useState<Partial<AnomalyConfigUpdate>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchAnomalyConfig();
        setConfig(data);
        setEditedConfig({
          threshold_stdev: data.threshold_stdev,
          min_samples: data.min_samples,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load anomaly configuration');
      } finally {
        setLoading(false);
      }
    };

    void loadConfig();
  }, []);

  const hasChanges =
    config &&
    (editedConfig.threshold_stdev !== config.threshold_stdev ||
      editedConfig.min_samples !== config.min_samples);

  const handleSave = async () => {
    if (!hasChanges) return;

    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      const updates: AnomalyConfigUpdate = {};
      if (editedConfig.threshold_stdev !== config?.threshold_stdev) {
        updates.threshold_stdev = editedConfig.threshold_stdev;
      }
      if (editedConfig.min_samples !== config?.min_samples) {
        updates.min_samples = editedConfig.min_samples;
      }

      const updatedConfig = await updateAnomalyConfig(updates);
      setConfig(updatedConfig);
      setEditedConfig({
        threshold_stdev: updatedConfig.threshold_stdev,
        min_samples: updatedConfig.min_samples,
      });
      setSuccess(true);
      onConfigUpdate?.(updatedConfig);

      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (config) {
      setEditedConfig({
        threshold_stdev: config.threshold_stdev,
        min_samples: config.min_samples,
      });
      setError(null);
      setSuccess(false);
    }
  };

  const getThresholdLabel = (value: number): string => {
    if (value <= 1.5) return 'Very Sensitive';
    if (value <= 2.0) return 'Sensitive';
    if (value <= 2.5) return 'Balanced';
    if (value <= 3.0) return 'Relaxed';
    return 'Very Relaxed';
  };

  if (loading) {
    return (
      <Card className={`bg-[#1A1A1A] border-gray-800 ${className}`}>
        <div className="flex items-center justify-center h-48">
          <div className="animate-pulse text-gray-400">Loading configuration...</div>
        </div>
      </Card>
    );
  }

  return (
    <Card className={`bg-[#1A1A1A] border-gray-800 ${className}`}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Settings className="h-5 w-5 text-green-500" />
          <div>
            <Title className="text-white">Anomaly Detection Settings</Title>
            <Text className="text-gray-400">Configure anomaly detection sensitivity</Text>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {success && (
            <div className="flex items-center gap-1 text-green-500">
              <CheckCircle className="h-4 w-4" />
              <Text className="text-green-500">Saved</Text>
            </div>
          )}
          <Button
            size="xs"
            variant="secondary"
            onClick={handleReset}
            disabled={!hasChanges || saving}
            icon={RotateCcw}
          >
            Reset
          </Button>
          <Button
            size="xs"
            onClick={() => void handleSave()}
            disabled={!hasChanges || saving}
            loading={saving}
            icon={Save}
          >
            Save Changes
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/20 border border-red-800 rounded-lg flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" />
          <Text className="text-red-400">{error}</Text>
        </div>
      )}

      <div className="space-y-6">
        {/* Threshold Slider */}
        <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-4">
          <div className="flex items-center justify-between mb-3">
            <Text className="nvidia-slider-label">Detection Sensitivity</Text>
            <div className="flex items-center gap-3">
              <Text className="text-xs text-gray-500">
                {getThresholdLabel(editedConfig.threshold_stdev ?? 2.0)}
              </Text>
              <span className="nvidia-slider-value">
                {editedConfig.threshold_stdev?.toFixed(1)} std
              </span>
            </div>
          </div>
          <div className="relative">
            <input
              type="range"
              min="1"
              max="4"
              step="0.1"
              value={editedConfig.threshold_stdev ?? 2.0}
              onChange={(e) =>
                setEditedConfig((prev) => ({
                  ...prev,
                  threshold_stdev: parseFloat(e.target.value),
                }))
              }
              className="nvidia-slider"
              aria-label="Detection threshold in standard deviations"
              aria-valuemin={1}
              aria-valuemax={4}
              aria-valuenow={editedConfig.threshold_stdev ?? 2.0}
            />
            <div className="nvidia-slider-range">
              <span>More sensitive</span>
              <span>Less sensitive</span>
            </div>
          </div>
          <Text className="nvidia-slider-description">
            Lower values trigger anomalies more easily. Recommended: 2.0-2.5
          </Text>
        </div>

        {/* Minimum Samples Slider */}
        <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-4">
          <div className="flex items-center justify-between mb-3">
            <Text className="nvidia-slider-label">Minimum Learning Samples</Text>
            <span className="nvidia-slider-value">
              {editedConfig.min_samples ?? 10} samples
            </span>
          </div>
          <div className="relative">
            <input
              type="range"
              min="5"
              max="50"
              step="1"
              value={editedConfig.min_samples ?? 10}
              onChange={(e) =>
                setEditedConfig((prev) => ({
                  ...prev,
                  min_samples: parseInt(e.target.value, 10),
                }))
              }
              className="nvidia-slider"
              aria-label="Minimum learning samples"
              aria-valuemin={5}
              aria-valuemax={50}
              aria-valuenow={editedConfig.min_samples ?? 10}
            />
            <div className="nvidia-slider-range">
              <span>Faster learning</span>
              <span>More stable baseline</span>
            </div>
          </div>
          <Text className="nvidia-slider-description">
            Minimum samples per time slot before anomaly detection activates
          </Text>
        </div>

        {/* Read-only info */}
        {config && (
          <div className="pt-4 border-t border-gray-800">
            <Text className="text-gray-400 text-sm mb-3">Additional Settings (read-only)</Text>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-800/50 rounded-lg p-3">
                <Text className="text-gray-400 text-xs uppercase">Decay Factor</Text>
                <Text className="text-white font-medium">{config.decay_factor}</Text>
                <Text className="text-xs text-gray-500">EWMA weight for recent data</Text>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-3">
                <Text className="text-gray-400 text-xs uppercase">Window</Text>
                <Text className="text-white font-medium">{config.window_days} days</Text>
                <Text className="text-xs text-gray-500">Rolling baseline period</Text>
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
