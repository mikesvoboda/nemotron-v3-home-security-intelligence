import { Card, Title, Text, Button } from '@tremor/react';
import { AlertCircle, Settings as SettingsIcon, Save, RotateCcw, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import CleanupPreviewPanel from './CleanupPreviewPanel';
import DlqMonitor from './DlqMonitor';
import SeverityThresholds from './SeverityThresholds';
import StorageDashboard from './StorageDashboard';
import {
  fetchConfig,
  updateConfig,
  triggerCleanup,
  type SystemConfig,
  type SystemConfigUpdate,
  type CleanupResponse,
} from '../../services/api';

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

  const hasChanges = !!(
    editedConfig &&
    config &&
    (editedConfig.batch_window_seconds !== config.batch_window_seconds ||
      editedConfig.batch_idle_timeout_seconds !== config.batch_idle_timeout_seconds ||
      editedConfig.retention_days !== config.retention_days ||
      editedConfig.detection_confidence_threshold !== config.detection_confidence_threshold)
  );

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
    <>
      <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
        <Title className="mb-4 flex items-center gap-2 text-white">
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
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
            <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
            <Text className="text-red-400">{error}</Text>
          </div>
        )}

        {success && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
            <Save className="h-5 w-5 flex-shrink-0 text-green-500" />
            <Text className="text-green-500">Settings saved successfully!</Text>
          </div>
        )}

        {!loading && editedConfig && (
          <div className="space-y-6">
            {/* Batch Window Duration */}
            <div>
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <Text className="font-medium text-gray-300">Batch Window Duration</Text>
                  <Text className="mt-1 text-xs text-gray-300">
                    Time window for grouping detections into events (seconds)
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">
                  {editedConfig.batch_window_seconds}s
                </Text>
              </div>
              <input
                type="range"
                min="30"
                max="300"
                step="10"
                value={editedConfig.batch_window_seconds}
                onChange={(e) =>
                  setEditedConfig((prev) =>
                    prev ? { ...prev, batch_window_seconds: parseInt(e.target.value) } : prev
                  )
                }
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                aria-label="Batch window duration in seconds"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-300">
                <span>30s</span>
                <span>300s</span>
              </div>
            </div>

            {/* Idle Timeout */}
            <div>
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <Text className="font-medium text-gray-300">Idle Timeout</Text>
                  <Text className="mt-1 text-xs text-gray-300">
                    Time to wait before processing incomplete batch (seconds)
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">
                  {editedConfig.batch_idle_timeout_seconds}s
                </Text>
              </div>
              <input
                type="range"
                min="10"
                max="120"
                step="5"
                value={editedConfig.batch_idle_timeout_seconds}
                onChange={(e) =>
                  setEditedConfig((prev) =>
                    prev
                      ? { ...prev, batch_idle_timeout_seconds: parseInt(e.target.value) }
                      : prev
                  )
                }
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                aria-label="Batch idle timeout in seconds"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-300">
                <span>10s</span>
                <span>120s</span>
              </div>
            </div>

            {/* Retention Period */}
            <div>
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <Text className="font-medium text-gray-300">Retention Period</Text>
                  <Text className="mt-1 text-xs text-gray-300">
                    Number of days to retain events and detections
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">
                  {editedConfig.retention_days} days
                </Text>
              </div>
              <input
                type="range"
                min="1"
                max="90"
                step="1"
                value={editedConfig.retention_days}
                onChange={(e) =>
                  setEditedConfig((prev) =>
                    prev ? { ...prev, retention_days: parseInt(e.target.value) } : prev
                  )
                }
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                aria-label="Retention period in days"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-300">
                <span>1 day</span>
                <span>90 days</span>
              </div>
            </div>

            {/* Confidence Threshold */}
            <div>
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <Text className="font-medium text-gray-300">Confidence Threshold</Text>
                  <Text className="mt-1 text-xs text-gray-300">
                    Minimum confidence for object detection (0.0 - 1.0)
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">
                  {editedConfig.detection_confidence_threshold?.toFixed(2) ?? '0.50'}
                </Text>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={editedConfig.detection_confidence_threshold}
                onChange={(e) =>
                  setEditedConfig((prev) =>
                    prev
                      ? { ...prev, detection_confidence_threshold: parseFloat(e.target.value) }
                      : prev
                  )
                }
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                aria-label="Detection confidence threshold"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-300">
                <span>0.00</span>
                <span>1.00</span>
              </div>
            </div>

            {/* Storage Dashboard */}
            <div className="border-t border-gray-800 pt-4">
              <StorageDashboard />
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 border-t border-gray-800 pt-4">
              <Button
                onClick={() => void handleSave()}
                disabled={!hasChanges || saving}
                className="flex-1 bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Save className="mr-2 h-4 w-4" />
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
              <Button
                onClick={handleReset}
                disabled={!hasChanges || saving}
                variant="secondary"
                className="flex-1 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                Reset
              </Button>
            </div>

            <div className="border-t border-gray-800 pt-4">
              <Button
                onClick={() => void handleClearData()}
                disabled={cleaning}
                variant="secondary"
                className="w-full border-red-500/30 text-red-400 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {cleaning ? 'Running Cleanup...' : 'Clear Old Data'}
              </Button>
              {cleanupResult && (
                <div className="mt-3 rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                  <Text className="mb-2 font-medium text-green-400">Cleanup Complete</Text>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <Text className="text-gray-300">Events deleted:</Text>
                    <Text className="text-white">{cleanupResult.events_deleted}</Text>
                    <Text className="text-gray-300">Detections deleted:</Text>
                    <Text className="text-white">{cleanupResult.detections_deleted}</Text>
                    <Text className="text-gray-300">GPU stats deleted:</Text>
                    <Text className="text-white">{cleanupResult.gpu_stats_deleted}</Text>
                    <Text className="text-gray-300">Logs deleted:</Text>
                    <Text className="text-white">{cleanupResult.logs_deleted}</Text>
                    <Text className="text-gray-300">Thumbnails deleted:</Text>
                    <Text className="text-white">{cleanupResult.thumbnails_deleted}</Text>
                    <Text className="text-gray-300">Retention period:</Text>
                    <Text className="text-white">{cleanupResult.retention_days} days</Text>
                  </div>
                </div>
              )}
            </div>

            {/* Application Info */}
            <div className="border-t border-gray-800 pt-4">
              <div className="mb-2 flex items-center justify-between">
                <Text className="text-sm text-gray-300">Application</Text>
                <Text className="font-medium text-white">{config?.app_name}</Text>
              </div>
              <div className="flex items-center justify-between">
                <Text className="text-sm text-gray-300">Version</Text>
                <Text className="font-medium text-white">{config?.version}</Text>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Cleanup Preview Panel - Preview retention policy impact */}
      <CleanupPreviewPanel className="mt-6" />

      {/* Severity Thresholds - Display risk score thresholds */}
      <SeverityThresholds className="mt-6" />

      {/* DLQ Monitor - Always visible below config card */}
      <DlqMonitor className="mt-6" />
    </>
  );
}
