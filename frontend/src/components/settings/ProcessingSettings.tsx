import { Card, Title, Text } from '@tremor/react';
import { AlertCircle, Settings as SettingsIcon } from 'lucide-react';
import { useEffect, useState } from 'react';

import { fetchConfig, type SystemConfig } from '../../services/api';

export interface ProcessingSettingsProps {
  className?: string;
}

/**
 * ProcessingSettings component displays event processing configuration settings
 * - Fetches settings from /api/system/config endpoint
 * - Currently read-only (no PUT endpoint available yet)
 * - Shows batch window duration, idle timeout, and retention period
 * - Handles loading and error states
 */
export default function ProcessingSettings({ className }: ProcessingSettingsProps) {
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchConfig();
        setConfig(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load configuration');
      } finally {
        setLoading(false);
      }
    };

    void loadConfig();
  }, []);

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
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <Text className="text-red-500">{error}</Text>
        </div>
      )}

      {!loading && !error && config && (
        <div className="space-y-6">
          {/* Info banner about read-only settings */}
          <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-3">
            <Text className="text-blue-400 text-sm">
              Settings are currently read-only. Configuration updates will be available in a future release.
            </Text>
          </div>

          {/* Batch Window Duration */}
          <div>
            <div className="block mb-2">
              <Text className="text-gray-300 font-medium">
                Batch Window Duration
              </Text>
              <Text className="text-gray-500 text-xs mt-1">
                Time window for grouping detections into events (seconds)
              </Text>
            </div>
            <input
              type="number"
              value={config.batch_window_seconds}
              disabled
              className="nvidia-input w-full opacity-60 cursor-not-allowed"
              aria-label="Batch window duration in seconds"
            />
          </div>

          {/* Idle Timeout */}
          <div>
            <div className="block mb-2">
              <Text className="text-gray-300 font-medium">
                Idle Timeout
              </Text>
              <Text className="text-gray-500 text-xs mt-1">
                Time to wait before processing incomplete batch (seconds)
              </Text>
            </div>
            <input
              type="number"
              value={config.batch_idle_timeout_seconds}
              disabled
              className="nvidia-input w-full opacity-60 cursor-not-allowed"
              aria-label="Batch idle timeout in seconds"
            />
          </div>

          {/* Retention Period */}
          <div>
            <div className="block mb-2">
              <Text className="text-gray-300 font-medium">
                Retention Period
              </Text>
              <Text className="text-gray-500 text-xs mt-1">
                Number of days to retain events and detections
              </Text>
            </div>
            <input
              type="number"
              value={config.retention_days}
              disabled
              className="nvidia-input w-full opacity-60 cursor-not-allowed"
              aria-label="Retention period in days"
            />
          </div>

          {/* Application Info */}
          <div className="pt-4 border-t border-gray-800">
            <div className="flex justify-between items-center mb-2">
              <Text className="text-gray-400 text-sm">Application</Text>
              <Text className="text-white font-medium">{config.app_name}</Text>
            </div>
            <div className="flex justify-between items-center">
              <Text className="text-gray-400 text-sm">Version</Text>
              <Text className="text-white font-medium">{config.version}</Text>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
