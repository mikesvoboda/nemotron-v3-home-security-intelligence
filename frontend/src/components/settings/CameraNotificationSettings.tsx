/**
 * CameraNotificationSettings component displays and manages per-camera notification settings.
 * - Enable/disable notifications per camera
 * - Set risk threshold per camera
 */
import { Card, Title, Text, Badge, NumberInput } from '@tremor/react';
import { AlertCircle, Camera, Loader2, Video } from 'lucide-react';
import { useState, useCallback } from 'react';

import { useCamerasQuery } from '../../hooks/useCamerasQuery';
import {
  useCameraNotificationSettingsQuery,
  useNotificationPreferencesMutation,
} from '../../hooks/useNotificationPreferencesQuery';

import type {
  CameraNotificationSetting,
  CameraNotificationSettingUpdate,
} from '../../types/notificationPreferences';

export interface CameraNotificationSettingsProps {
  className?: string;
}

interface CameraSettingRowProps {
  cameraId: string;
  cameraName: string;
  setting: CameraNotificationSetting | undefined;
  onUpdate: (cameraId: string, update: CameraNotificationSettingUpdate) => Promise<void>;
  isUpdating: boolean;
}

/**
 * Individual row for camera notification settings
 */
function CameraSettingRow({
  cameraId,
  cameraName,
  setting,
  onUpdate,
  isUpdating,
}: CameraSettingRowProps) {
  const [localEnabled, setLocalEnabled] = useState(setting?.enabled ?? true);
  const [localThreshold, setLocalThreshold] = useState(setting?.risk_threshold ?? 0);
  const [thresholdError, setThresholdError] = useState<string | null>(null);

  // Handle enable toggle
  const handleToggle = async () => {
    const newEnabled = !localEnabled;
    setLocalEnabled(newEnabled);
    try {
      await onUpdate(cameraId, { enabled: newEnabled });
    } catch {
      // Revert on error
      setLocalEnabled(!newEnabled);
    }
  };

  // Handle threshold change with validation
  const handleThresholdChange = (value: number) => {
    setLocalThreshold(value);
    if (value < 0 || value > 100) {
      setThresholdError('Threshold must be between 0 and 100');
    } else {
      setThresholdError(null);
    }
  };

  // Handle threshold blur (save on blur)
  const handleThresholdBlur = async () => {
    if (thresholdError) return;
    if (localThreshold === setting?.risk_threshold) return;

    try {
      await onUpdate(cameraId, { risk_threshold: localThreshold });
    } catch {
      // Revert on error
      setLocalThreshold(setting?.risk_threshold ?? 0);
    }
  };

  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-[#121212] p-4">
      <div className="flex items-center gap-3">
        <Video className="h-5 w-5 text-gray-400" />
        <div>
          <Text className="font-medium text-gray-300">{cameraName}</Text>
          <Text className="text-xs text-gray-500">{cameraId}</Text>
        </div>
      </div>

      <div className="flex items-center gap-6">
        {/* Risk Threshold */}
        <div className="flex items-center gap-2">
          <Text className="text-sm text-gray-400">Min Risk:</Text>
          <div className="w-24">
            <NumberInput
              value={localThreshold}
              onValueChange={handleThresholdChange}
              onBlur={() => void handleThresholdBlur()}
              min={0}
              max={100}
              disabled={!localEnabled || isUpdating}
              className="text-sm"
              error={!!thresholdError}
            />
          </div>
          {thresholdError && (
            <Text className="text-xs text-red-400">{thresholdError}</Text>
          )}
        </div>

        {/* Enable Toggle */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => void handleToggle()}
            disabled={isUpdating}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900 ${
              localEnabled ? 'bg-[#76B900]' : 'bg-gray-600'
            } ${isUpdating ? 'cursor-not-allowed opacity-50' : ''}`}
            role="switch"
            aria-checked={localEnabled}
            aria-label={`Enable notifications for ${cameraName}`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                localEnabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
          <Badge color={localEnabled ? 'green' : 'gray'} size="sm">
            {localEnabled ? 'On' : 'Off'}
          </Badge>
        </div>
      </div>
    </div>
  );
}

/**
 * CameraNotificationSettings displays notification settings for all cameras.
 *
 * Features:
 * - Shows all cameras with their notification status
 * - Enable/disable notifications per camera
 * - Set minimum risk threshold to trigger notifications
 * - Real-time updates
 */
export default function CameraNotificationSettings({
  className,
}: CameraNotificationSettingsProps) {
  const { cameras, isLoading: camerasLoading, error: camerasError } = useCamerasQuery();
  const {
    settings,
    isLoading: settingsLoading,
    error: settingsError,
    refetch,
  } = useCameraNotificationSettingsQuery();
  const { updateCameraMutation } = useNotificationPreferencesMutation();

  // Build a map of camera settings by camera_id
  const settingsMap = new Map(settings.map((s) => [s.camera_id, s]));

  // Handle update for a camera setting
  const handleUpdate = useCallback(
    async (cameraId: string, update: CameraNotificationSettingUpdate) => {
      await updateCameraMutation.mutateAsync({ cameraId, data: update });
    },
    [updateCameraMutation]
  );

  const isLoading = camerasLoading || settingsLoading;
  const error = camerasError || settingsError;

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Camera className="h-5 w-5 text-[#76B900]" />
        Per-Camera Notification Settings
      </Title>

      <Text className="mb-4 text-sm text-gray-400">
        Configure notification settings for individual cameras. Set the minimum risk score
        required to trigger notifications.
      </Text>

      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      )}

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">{error.message}</Text>
          <button
            onClick={() => void refetch()}
            className="ml-auto text-sm text-red-400 underline hover:text-red-300"
          >
            Retry
          </button>
        </div>
      )}

      {updateCameraMutation.error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">
            Failed to update: {updateCameraMutation.error.message}
          </Text>
        </div>
      )}

      {!isLoading && cameras.length === 0 && (
        <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-6 text-center">
          <Camera className="mx-auto mb-2 h-8 w-8 text-gray-500" />
          <Text className="text-gray-400">No cameras configured</Text>
          <Text className="mt-1 text-xs text-gray-500">
            Add cameras in the Cameras settings to configure their notifications.
          </Text>
        </div>
      )}

      {!isLoading && cameras.length > 0 && (
        <div className="space-y-3">
          {cameras.map((camera) => (
            <CameraSettingRow
              key={camera.id}
              cameraId={camera.id}
              cameraName={camera.name}
              setting={settingsMap.get(camera.id)}
              onUpdate={handleUpdate}
              isUpdating={updateCameraMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Info note */}
      <div className="mt-4 rounded-lg border border-blue-500/30 bg-blue-500/10 p-3">
        <Text className="text-sm text-blue-400">
          <strong>Tip:</strong> Set the minimum risk score to filter out low-priority events.
          Score range is 0-100, where 0 means all events and 100 means only critical events.
        </Text>
      </div>
    </Card>
  );
}
