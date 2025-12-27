import { Card, Title, Text, Button } from '@tremor/react';
import { AlertCircle, Settings as SettingsIcon, Save, RotateCcw, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { fetchConfig, updateConfig, triggerCleanup, type SystemConfig, type SystemConfigUpdate, type CleanupResponse } from '../../services/api';

export interface ProcessingSettingsProps {
  className?: string;
}

/**
 * ProcessingSettings component displays and allows editing of event processing configuration
 * - Fetches settings from /api/system/config endpoint
 * - Allows editing batch window, idle timeout, retention period, and confidence threshold
 * - Uses range sliders for intuitive value adjustment
 * - Saves changes via PATCH /api/system/config endpoint
 * - Shows storage usage and provides data cleanup button
 * - Handles loading, error, and success states
 */
export default function ProcessingSettings({ className }: ProcessingSettingsProps) {
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [editedConfig, setEditedConfig] = useState<SystemConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<CleanupResponse | null>(null);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchConfig();
        setConfig(data);
        setEditedConfig(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load configuration');
      } finally {
        setLoading(false);
      }
    };

    void loadConfig();
  }, []);

  const hasChanges = !!(editedConfig && config && (
    editedConfig.batch_window_seconds !== config.batch_window_seconds ||
    editedConfig.batch_idle_timeout_seconds !== config.batch_idle_timeout_seconds ||
    editedConfig.retention_days !== config.retention_days ||
    editedConfig.detection_confidence_threshold !== config.detection_confidence_threshold
  ));

  const handleSave = async () => {
    if (!editedConfig || !hasChanges) return;

    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      const updates: SystemConfigUpdate = {
        batch_window_seconds: editedConfig.batch_window_seconds,
        batch_idle_timeout_seconds: editedConfig.batch_idle_timeout_seconds,
        retention_days: editedConfig.retention_days,
        detection_confidence_threshold: editedConfig.detection_confidence_threshold,
      };

      const updatedConfig = await updateConfig(updates);
      setConfig(updatedConfig);
      setEditedConfig(updatedConfig);
      setSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (config) {
      setEditedConfig(config);
      setError(null);
      setSuccess(false);
    }
  };

  const handleClearData = async () => {
    try {
      setCleaning(true);
      setError(null);
      setCleanupResult(null);

      const result = await triggerCleanup();
      setCleanupResult(result);

      // Clear cleanup result after 10 seconds
      setTimeout(() => setCleanupResult(null), 10000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run cleanup');
    } finally {
      setCleaning(false);
    }
  };

  return (
    <Card
      className={`bg-[#1A1A1A] border-gray-800 shadow-lg ${className || ''}`}
    >
      <Title className="text-white mb-4 flex items-center gap-2">
        <SettingsIcon className="h-5 w-5 text-[#76B900]" />
        Processing Settings
      </Title>

      {loading && (
        <div className="space-y-4">
          <div className="skeleton h-12 w-full"></div>
          <div className="skeleton h-12 w-full"></div>
          <div className="skeleton h-12 w-full"></div>
          <div className="skeleton h-12 w-full"></div>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4 mb-4">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
          <Text className="text-red-500">{error}</Text>
        </div>
      )}

      {success && (
        <div className="flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-4 mb-4">
          <Save className="h-5 w-5 text-green-500 flex-shrink-0" />
          <Text className="text-green-500">Settings saved successfully!</Text>
        </div>
      )}

      {!loading && editedConfig && (
        <div className="space-y-6">
          {/* Batch Window Duration */}
          <div>
            <div className="flex justify-between items-end mb-2">
              <div>
                <Text className="text-gray-300 font-medium">
                  Batch Window Duration
                </Text>
                <Text className="text-gray-500 text-xs mt-1">
                  Time window for grouping detections into events (seconds)
                </Text>
              </div>
              <Text className="text-white font-semibold text-lg">
                {editedConfig.batch_window_seconds}s
              </Text>
            </div>
            <input
              type="range"
              min="30"
              max="300"
              step="10"
              value={editedConfig.batch_window_seconds}
              onChange={(e) => setEditedConfig({
                ...editedConfig,
                batch_window_seconds: parseInt(e.target.value),
              })}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-[#76B900]"
              aria-label="Batch window duration in seconds"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>30s</span>
              <span>300s</span>
            </div>
          </div>

          {/* Idle Timeout */}
          <div>
            <div className="flex justify-between items-end mb-2">
              <div>
                <Text className="text-gray-300 font-medium">
                  Idle Timeout
                </Text>
                <Text className="text-gray-500 text-xs mt-1">
                  Time to wait before processing incomplete batch (seconds)
                </Text>
              </div>
              <Text className="text-white font-semibold text-lg">
                {editedConfig.batch_idle_timeout_seconds}s
              </Text>
            </div>
            <input
              type="range"
              min="10"
              max="120"
              step="5"
              value={editedConfig.batch_idle_timeout_seconds}
              onChange={(e) => setEditedConfig({
                ...editedConfig,
                batch_idle_timeout_seconds: parseInt(e.target.value),
              })}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-[#76B900]"
              aria-label="Batch idle timeout in seconds"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>10s</span>
              <span>120s</span>
            </div>
          </div>

          {/* Retention Period */}
          <div>
            <div className="flex justify-between items-end mb-2">
              <div>
                <Text className="text-gray-300 font-medium">
                  Retention Period
                </Text>
                <Text className="text-gray-500 text-xs mt-1">
                  Number of days to retain events and detections
                </Text>
              </div>
              <Text className="text-white font-semibold text-lg">
                {editedConfig.retention_days} days
              </Text>
            </div>
            <input
              type="range"
              min="1"
              max="90"
              step="1"
              value={editedConfig.retention_days}
              onChange={(e) => setEditedConfig({
                ...editedConfig,
                retention_days: parseInt(e.target.value),
              })}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-[#76B900]"
              aria-label="Retention period in days"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>1 day</span>
              <span>90 days</span>
            </div>
          </div>

          {/* Confidence Threshold */}
          <div>
            <div className="flex justify-between items-end mb-2">
              <div>
                <Text className="text-gray-300 font-medium">
                  Confidence Threshold
                </Text>
                <Text className="text-gray-500 text-xs mt-1">
                  Minimum confidence for object detection (0.0 - 1.0)
                </Text>
              </div>
              <Text className="text-white font-semibold text-lg">
                {editedConfig.detection_confidence_threshold.toFixed(2)}
              </Text>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={editedConfig.detection_confidence_threshold}
              onChange={(e) => setEditedConfig({
                ...editedConfig,
                detection_confidence_threshold: parseFloat(e.target.value),
              })}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-[#76B900]"
              aria-label="Detection confidence threshold"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0.00</span>
              <span>1.00</span>
            </div>
          </div>

          {/* Storage Usage */}
          <div className="pt-4 border-t border-gray-800">
            <div className="flex justify-between items-center mb-3">
              <Text className="text-gray-300 font-medium">Storage</Text>
              <Text className="text-gray-500 text-sm">Coming soon</Text>
            </div>
            <div className="w-full h-3 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-[#76B900] rounded-full transition-all duration-300"
                style={{ width: '0%' }}
                aria-label="Storage usage percentage"
              />
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0 GB used</span>
              <span>0 GB total</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4 border-t border-gray-800">
            <Button
              onClick={() => void handleSave()}
              disabled={!hasChanges || saving}
              className="flex-1 bg-[#76B900] hover:bg-[#5c8f00] text-white disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="h-4 w-4 mr-2" />
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
            <Button
              onClick={handleReset}
              disabled={!hasChanges || saving}
              variant="secondary"
              className="flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RotateCcw className="h-4 w-4 mr-2" />
              Reset
            </Button>
          </div>

          <div className="pt-4 border-t border-gray-800">
            <Button
              onClick={() => void handleClearData()}
              disabled={cleaning}
              variant="secondary"
              className="w-full border-red-500/30 text-red-400 hover:bg-red-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              {cleaning ? 'Running Cleanup...' : 'Clear Old Data'}
            </Button>
            {cleanupResult && (
              <div className="mt-3 rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                <Text className="text-green-400 font-medium mb-2">Cleanup Complete</Text>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <Text className="text-gray-400">Events deleted:</Text>
                  <Text className="text-white">{cleanupResult.events_deleted}</Text>
                  <Text className="text-gray-400">Detections deleted:</Text>
                  <Text className="text-white">{cleanupResult.detections_deleted}</Text>
                  <Text className="text-gray-400">GPU stats deleted:</Text>
                  <Text className="text-white">{cleanupResult.gpu_stats_deleted}</Text>
                  <Text className="text-gray-400">Logs deleted:</Text>
                  <Text className="text-white">{cleanupResult.logs_deleted}</Text>
                  <Text className="text-gray-400">Thumbnails deleted:</Text>
                  <Text className="text-white">{cleanupResult.thumbnails_deleted}</Text>
                  <Text className="text-gray-400">Retention period:</Text>
                  <Text className="text-white">{cleanupResult.retention_days} days</Text>
                </div>
              </div>
            )}
          </div>

          {/* Application Info */}
          <div className="pt-4 border-t border-gray-800">
            <div className="flex justify-between items-center mb-2">
              <Text className="text-gray-400 text-sm">Application</Text>
              <Text className="text-white font-medium">{config?.app_name}</Text>
            </div>
            <div className="flex justify-between items-center">
              <Text className="text-gray-400 text-sm">Version</Text>
              <Text className="text-white font-medium">{config?.version}</Text>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
