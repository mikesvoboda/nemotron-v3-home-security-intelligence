import { Card, Title, Text, Button, Badge, Select, SelectItem } from '@tremor/react';
import {
  AlertCircle,
  Bell,
  BellOff,
  Camera,
  CheckCircle,
  Clock,
  Loader2,
  Mail,
  Monitor,
  Moon,
  Plus,
  Send,
  Settings,
  Smartphone,
  Trash2,
  Volume2,
  VolumeX,
  Webhook,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { useCamerasQuery } from '../../hooks/useCamerasQuery';
import { useIntegratedNotifications } from '../../hooks/useIntegratedNotifications';
import {
  useNotificationPreferences,
  useCameraNotificationSettings,
  useCameraNotificationSettingMutation,
  useQuietHoursPeriods,
  useQuietHoursPeriodMutations,
} from '../../hooks/useNotificationPreferences';
import {
  fetchNotificationConfig,
  testNotification,
  type NotificationConfig,
} from '../../services/api';

export interface NotificationSettingsProps {
  className?: string;
}

/** Available notification sounds */
const NOTIFICATION_SOUNDS = [
  { value: 'none', label: 'None (Silent)' },
  { value: 'default', label: 'Default' },
  { value: 'alert', label: 'Alert' },
  { value: 'chime', label: 'Chime' },
  { value: 'urgent', label: 'Urgent' },
];

/** Available risk levels for filtering */
const RISK_LEVELS = [
  { value: 'critical', label: 'Critical', color: 'red' },
  { value: 'high', label: 'High', color: 'orange' },
  { value: 'medium', label: 'Medium', color: 'yellow' },
  { value: 'low', label: 'Low', color: 'green' },
];

/** Days of the week */
const DAYS_OF_WEEK = [
  { value: 'monday', label: 'Mon' },
  { value: 'tuesday', label: 'Tue' },
  { value: 'wednesday', label: 'Wed' },
  { value: 'thursday', label: 'Thu' },
  { value: 'friday', label: 'Fri' },
  { value: 'saturday', label: 'Sat' },
  { value: 'sunday', label: 'Sun' },
];

/** Risk level score ranges for threshold conflict detection */
const RISK_LEVEL_RANGES = {
  critical: { min: 80, max: 100 },
  high: { min: 60, max: 79 },
  medium: { min: 40, max: 59 },
  low: { min: 0, max: 39 },
} as const;

/**
 * Check if a camera threshold might conflict with global risk filters.
 * A conflict exists when:
 * - Camera threshold is below the minimum score of enabled risk levels
 * - This means some alerts the user expects might not be delivered due to global filter
 *
 * @returns Object with hasConflict flag and explanation message
 */
function detectThresholdConflict(
  cameraThreshold: number,
  globalRiskFilters: string[]
): { hasConflict: boolean; message: string } {
  if (!globalRiskFilters || globalRiskFilters.length === 0) {
    return { hasConflict: false, message: '' };
  }

  // Find the minimum score that would pass global filters
  const enabledRanges = globalRiskFilters
    .filter((f) => f in RISK_LEVEL_RANGES)
    .map((f) => RISK_LEVEL_RANGES[f as keyof typeof RISK_LEVEL_RANGES]);

  if (enabledRanges.length === 0) {
    return { hasConflict: false, message: '' };
  }

  const minEnabledScore = Math.min(...enabledRanges.map((r) => r.min));

  // Conflict: camera threshold is below the minimum enabled level
  // This means the camera threshold setting would allow alerts that global filter blocks
  if (cameraThreshold < minEnabledScore) {
    const blockedLevels = Object.entries(RISK_LEVEL_RANGES)
      .filter(([level, range]) => !globalRiskFilters.includes(level) && range.max >= cameraThreshold)
      .map(([level]) => level);

    if (blockedLevels.length > 0) {
      return {
        hasConflict: true,
        message: `Alerts below ${minEnabledScore}% are blocked by global risk filters (${blockedLevels.join(', ')} levels disabled)`,
      };
    }
  }

  return { hasConflict: false, message: '' };
}

/**
 * NotificationSettings component displays notification configuration status
 * and provides UI for managing notification preferences.
 *
 * Features:
 * - Shows email (SMTP) configuration status
 * - Shows webhook configuration status
 * - Global notification preferences (enabled, sound, risk filters)
 * - Per-camera notification toggles with risk thresholds
 * - Quiet hours scheduler
 * - Test notification buttons for each channel
 */
export default function NotificationSettings({ className }: NotificationSettingsProps) {
  // Channel configuration state (from environment)
  const [config, setConfig] = useState<NotificationConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testingEmail, setTestingEmail] = useState(false);
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [testResult, setTestResult] = useState<{
    channel: string;
    success: boolean;
    message: string;
  } | null>(null);

  // Notification preferences hooks
  const {
    preferences,
    isLoading: preferencesLoading,
    error: preferencesError,
    updateMutation: preferencesUpdateMutation,
  } = useNotificationPreferences();

  const { cameras } = useCamerasQuery();
  const { settings: cameraSettings, isLoading: cameraSettingsLoading } =
    useCameraNotificationSettings();
  const { updateMutation: cameraSettingUpdateMutation } = useCameraNotificationSettingMutation();

  const { periods: quietHoursPeriods, isLoading: quietHoursLoading } = useQuietHoursPeriods();
  const { createMutation: quietHoursCreateMutation, deleteMutation: quietHoursDeleteMutation } =
    useQuietHoursPeriodMutations();

  // New quiet hours form state
  const [showQuietHoursForm, setShowQuietHoursForm] = useState(false);
  const [newQuietHours, setNewQuietHours] = useState({
    label: '',
    start_time: '22:00',
    end_time: '06:00',
    days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'] as string[],
  });

  // Load channel configuration
  useEffect(() => {
    const loadConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchNotificationConfig();
        setConfig(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load notification configuration');
      } finally {
        setLoading(false);
      }
    };

    void loadConfig();
  }, []);

  const handleTestEmail = async () => {
    if (!config?.email_configured) return;

    try {
      setTestingEmail(true);
      setTestResult(null);
      const result = await testNotification('email');
      setTestResult({
        channel: 'email',
        success: result.success,
        message: result.message,
      });

      setTimeout(() => setTestResult(null), 5000);
    } catch (err) {
      setTestResult({
        channel: 'email',
        success: false,
        message: err instanceof Error ? err.message : 'Failed to send test email',
      });
    } finally {
      setTestingEmail(false);
    }
  };

  const handleTestWebhook = async () => {
    if (!config?.webhook_configured) return;

    try {
      setTestingWebhook(true);
      setTestResult(null);
      const result = await testNotification('webhook');
      setTestResult({
        channel: 'webhook',
        success: result.success,
        message: result.message,
      });

      setTimeout(() => setTestResult(null), 5000);
    } catch (err) {
      setTestResult({
        channel: 'webhook',
        success: false,
        message: err instanceof Error ? err.message : 'Failed to send test webhook',
      });
    } finally {
      setTestingWebhook(false);
    }
  };

  // Toggle global notifications
  const handleToggleGlobalNotifications = useCallback(() => {
    if (!preferences) return;
    preferencesUpdateMutation.mutate({ enabled: !preferences.enabled });
  }, [preferences, preferencesUpdateMutation]);

  // Update notification sound
  const handleSoundChange = useCallback(
    (value: string) => {
      preferencesUpdateMutation.mutate({ sound: value });
    },
    [preferencesUpdateMutation]
  );

  // Toggle risk level filter
  const handleToggleRiskFilter = useCallback(
    (level: string) => {
      if (!preferences) return;
      const currentFilters = preferences.risk_filters || [];
      const newFilters = currentFilters.includes(level)
        ? currentFilters.filter((f: string) => f !== level)
        : [...currentFilters, level];
      preferencesUpdateMutation.mutate({ risk_filters: newFilters });
    },
    [preferences, preferencesUpdateMutation]
  );

  // Toggle camera notification setting
  const handleToggleCameraNotification = useCallback(
    (cameraId: string, currentEnabled: boolean) => {
      cameraSettingUpdateMutation.mutate({
        cameraId,
        update: { enabled: !currentEnabled },
      });
    },
    [cameraSettingUpdateMutation]
  );

  // Update camera risk threshold
  const handleCameraThresholdChange = useCallback(
    (cameraId: string, threshold: number) => {
      cameraSettingUpdateMutation.mutate({
        cameraId,
        update: { risk_threshold: threshold },
      });
    },
    [cameraSettingUpdateMutation]
  );

  // Create quiet hours period
  const handleCreateQuietHours = useCallback(() => {
    if (!newQuietHours.label.trim()) return;
    quietHoursCreateMutation.mutate(
      {
        label: newQuietHours.label,
        start_time: `${newQuietHours.start_time}:00`,
        end_time: `${newQuietHours.end_time}:00`,
        days: newQuietHours.days,
      },
      {
        onSuccess: () => {
          setShowQuietHoursForm(false);
          setNewQuietHours({
            label: '',
            start_time: '22:00',
            end_time: '06:00',
            days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
          });
        },
      }
    );
  }, [newQuietHours, quietHoursCreateMutation]);

  // Delete quiet hours period
  const handleDeleteQuietHours = useCallback(
    (periodId: string) => {
      quietHoursDeleteMutation.mutate(periodId);
    },
    [quietHoursDeleteMutation]
  );

  // Toggle day selection for new quiet hours
  const handleToggleDay = useCallback((day: string) => {
    setNewQuietHours((prev) => ({
      ...prev,
      days: prev.days.includes(day) ? prev.days.filter((d) => d !== day) : [...prev.days, day],
    }));
  }, []);

  // Get camera setting for a specific camera
  const getCameraSetting = useCallback(
    (cameraId: string) => {
      return cameraSettings.find((s) => s.camera_id === cameraId);
    },
    [cameraSettings]
  );

  const isAnyLoading = loading || preferencesLoading;

  // Integrated notifications for desktop/push/audio controls
  const {
    desktopPermission,
    desktopSupported,
    desktopHasPermission,
    requestDesktopPermission,
    pushPermission,
    pushSupported,
    pushHasPermission,
    requestPushPermission,
    audioVolume,
    setAudioVolume,
    audioReady,
    resumeAudio,
  } = useIntegratedNotifications();

  // Test desktop notification
  const [testingDesktop, setTestingDesktop] = useState(false);
  const handleTestDesktop = useCallback(async () => {
    if (!desktopHasPermission) {
      await requestDesktopPermission();
      return;
    }

    try {
      setTestingDesktop(true);
      setTestResult(null);

      // Show test notification
      if (typeof Notification !== 'undefined') {
        new Notification('Test Notification', {
          body: 'This is a test desktop notification from the security system.',
          icon: '/icons/icon-192.png',
        });
      }

      setTestResult({
        channel: 'desktop',
        success: true,
        message: 'Test desktop notification sent successfully!',
      });
      setTimeout(() => setTestResult(null), 5000);
    } catch (err) {
      setTestResult({
        channel: 'desktop',
        success: false,
        message: err instanceof Error ? err.message : 'Failed to send test desktop notification',
      });
    } finally {
      setTestingDesktop(false);
    }
  }, [desktopHasPermission, requestDesktopPermission]);

  // Test audio notification
  const [testingAudio, setTestingAudio] = useState(false);
  const handleTestAudio = useCallback(async () => {
    try {
      setTestingAudio(true);
      setTestResult(null);

      if (!audioReady) {
        await resumeAudio();
      }

      // Play a test sound using the Web Audio API
      if (typeof AudioContext !== 'undefined') {
        const audioContext = new AudioContext();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 440; // A4 note
        gainNode.gain.value = audioVolume * 0.5; // Use current volume

        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.3);

        // Clean up after sound plays
        setTimeout(() => {
          void audioContext.close();
        }, 500);
      }

      setTestResult({
        channel: 'audio',
        success: true,
        message: 'Test audio notification played successfully!',
      });
      setTimeout(() => setTestResult(null), 5000);
    } catch (err) {
      setTestResult({
        channel: 'audio',
        success: false,
        message: err instanceof Error ? err.message : 'Failed to play test audio',
      });
    } finally {
      setTestingAudio(false);
    }
  }, [audioReady, resumeAudio, audioVolume]);

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Bell className="h-5 w-5 text-[#76B900]" />
        Notification Settings
      </Title>

      {isAnyLoading && (
        <div className="space-y-4">
          <div className="skeleton h-32 w-full"></div>
          <div className="skeleton h-32 w-full"></div>
        </div>
      )}

      {(error || preferencesError) && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">{error || preferencesError?.message}</Text>
        </div>
      )}

      {testResult && (
        <div
          className={`mb-4 flex items-center gap-2 rounded-lg border p-4 ${
            testResult.success
              ? 'border-green-500/30 bg-green-500/10'
              : 'border-red-500/30 bg-red-500/10'
          }`}
        >
          {testResult.success ? (
            <CheckCircle className="h-5 w-5 flex-shrink-0 text-green-500" />
          ) : (
            <X className="h-5 w-5 flex-shrink-0 text-red-400" />
          )}
          <Text className={testResult.success ? 'text-green-500' : 'text-red-400'}>
            {testResult.message}
          </Text>
        </div>
      )}

      {!isAnyLoading && config && (
        <div className="space-y-6">
          {/* Global Notification Preferences */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center gap-2">
              <Settings className="h-5 w-5 text-[#76B900]" />
              <Text className="font-medium text-gray-300">Global Preferences</Text>
            </div>

            {/* Enable/Disable Toggle */}
            <div className="mb-4 flex items-center justify-between border-b border-gray-800 pb-4">
              <div>
                <Text className="font-medium text-gray-300">Notifications</Text>
                <Text className="mt-1 text-xs text-gray-500">
                  Enable or disable all notifications
                </Text>
              </div>
              <button
                onClick={handleToggleGlobalNotifications}
                disabled={preferencesUpdateMutation.isPending}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900 ${
                  preferences?.enabled ? 'bg-[#76B900]' : 'bg-gray-600'
                }`}
                role="switch"
                aria-checked={preferences?.enabled}
                aria-label="Toggle notifications"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    preferences?.enabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Notification Sound */}
            <div className="mb-4 flex items-center justify-between border-b border-gray-800 pb-4">
              <div className="flex items-center gap-2">
                <Volume2 className="h-4 w-4 text-gray-400" />
                <div>
                  <Text className="font-medium text-gray-300">Notification Sound</Text>
                  <Text className="text-xs text-gray-500">Sound played for notifications</Text>
                </div>
              </div>
              <Select
                value={preferences?.sound || 'default'}
                onValueChange={handleSoundChange}
                className="w-32"
                disabled={preferencesUpdateMutation.isPending}
              >
                {NOTIFICATION_SOUNDS.map((sound) => (
                  <SelectItem key={sound.value} value={sound.value}>
                    {sound.label}
                  </SelectItem>
                ))}
              </Select>
            </div>

            {/* Risk Level Filters */}
            <div>
              <div className="mb-2 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-gray-400" />
                <Text className="font-medium text-gray-300">Risk Level Filters</Text>
              </div>
              <Text className="mb-3 text-xs text-gray-500">
                Select which risk levels trigger notifications
              </Text>
              <div className="flex flex-wrap gap-2">
                {RISK_LEVELS.map((level) => {
                  const isSelected = preferences?.risk_filters?.includes(level.value);
                  return (
                    <button
                      key={level.value}
                      onClick={() => handleToggleRiskFilter(level.value)}
                      disabled={preferencesUpdateMutation.isPending}
                      className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                        isSelected
                          ? `bg-${level.color}-500/20 text-${level.color}-400 border border-${level.color}-500/50`
                          : 'border border-gray-700 bg-gray-800 text-gray-500'
                      }`}
                    >
                      {level.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Desktop & Push Notification Settings */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center gap-2">
              <Monitor className="h-5 w-5 text-cyan-400" />
              <Text className="font-medium text-gray-300">Desktop & Push Notifications</Text>
            </div>

            <Text className="mb-4 text-xs text-gray-500">
              Configure browser notifications for security alerts
            </Text>

            {/* Desktop Notification Permission */}
            <div className="mb-4 flex items-center justify-between border-b border-gray-800 pb-4">
              <div className="flex items-center gap-2">
                <Monitor className="h-4 w-4 text-gray-400" />
                <div>
                  <Text className="font-medium text-gray-300">Desktop Notifications</Text>
                  <Text className="text-xs text-gray-500">
                    {desktopSupported
                      ? desktopHasPermission
                        ? 'Permission granted - notifications enabled'
                        : desktopPermission === 'denied'
                          ? 'Permission denied - enable in browser settings'
                          : 'Permission required for desktop alerts'
                      : 'Not supported in this browser'}
                  </Text>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge
                  color={
                    desktopHasPermission ? 'green' : desktopPermission === 'denied' ? 'red' : 'gray'
                  }
                  size="sm"
                >
                  {desktopHasPermission ? 'Enabled' : desktopPermission === 'denied' ? 'Denied' : 'Not Set'}
                </Badge>
                {desktopSupported && !desktopHasPermission && desktopPermission !== 'denied' && (
                  <Button
                    size="xs"
                    onClick={() => void requestDesktopPermission()}
                    className="bg-cyan-600 text-white hover:bg-cyan-700"
                  >
                    Enable
                  </Button>
                )}
                {desktopHasPermission && (
                  <Button
                    size="xs"
                    onClick={() => void handleTestDesktop()}
                    disabled={testingDesktop}
                    className="bg-gray-700 text-white hover:bg-gray-600"
                  >
                    {testingDesktop ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Test'}
                  </Button>
                )}
              </div>
            </div>

            {/* Push Notification Permission */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Smartphone className="h-4 w-4 text-gray-400" />
                <div>
                  <Text className="font-medium text-gray-300">Push Notifications</Text>
                  <Text className="text-xs text-gray-500">
                    {pushSupported
                      ? pushHasPermission
                        ? 'Permission granted - push enabled'
                        : pushPermission === 'denied'
                          ? 'Permission denied - enable in browser settings'
                          : 'Permission required for push alerts'
                      : 'Not supported in this browser'}
                  </Text>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge
                  color={
                    pushHasPermission ? 'green' : pushPermission === 'denied' ? 'red' : 'gray'
                  }
                  size="sm"
                >
                  {pushHasPermission ? 'Enabled' : pushPermission === 'denied' ? 'Denied' : 'Not Set'}
                </Badge>
                {pushSupported && !pushHasPermission && pushPermission !== 'denied' && (
                  <Button
                    size="xs"
                    onClick={() => void requestPushPermission()}
                    className="bg-cyan-600 text-white hover:bg-cyan-700"
                  >
                    Enable
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* Audio Notification Settings */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center gap-2">
              {preferences?.sound === 'none' ? (
                <VolumeX className="h-5 w-5 text-gray-500" />
              ) : (
                <Volume2 className="h-5 w-5 text-amber-400" />
              )}
              <Text className="font-medium text-gray-300">Audio Notification Settings</Text>
            </div>

            <Text className="mb-4 text-xs text-gray-500">
              Configure audio alerts for security events
            </Text>

            {/* Volume Control */}
            <div className="mb-4 flex items-center justify-between border-b border-gray-800 pb-4">
              <div className="flex items-center gap-2">
                <Volume2 className="h-4 w-4 text-gray-400" />
                <div>
                  <Text className="font-medium text-gray-300">Volume Level</Text>
                  <Text className="text-xs text-gray-500">
                    Adjust audio notification volume
                  </Text>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={audioVolume}
                  onChange={(e) => setAudioVolume(parseFloat(e.target.value))}
                  disabled={preferences?.sound === 'none'}
                  className="h-2 w-24 cursor-pointer appearance-none rounded-lg bg-gray-700 accent-amber-500 disabled:opacity-50"
                />
                <Badge color={preferences?.sound === 'none' ? 'gray' : 'amber'} size="sm">
                  {Math.round(audioVolume * 100)}%
                </Badge>
              </div>
            </div>

            {/* Test Audio */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bell className="h-4 w-4 text-gray-400" />
                <div>
                  <Text className="font-medium text-gray-300">Test Audio</Text>
                  <Text className="text-xs text-gray-500">
                    Play a test sound at current volume
                  </Text>
                </div>
              </div>
              <Button
                size="xs"
                onClick={() => void handleTestAudio()}
                disabled={testingAudio || preferences?.sound === 'none'}
                className="bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {testingAudio ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <>
                    <Volume2 className="mr-1 h-3 w-3" />
                    Play Test
                  </>
                )}
              </Button>
            </div>

            {preferences?.sound === 'none' && (
              <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800/50 p-3">
                <Text className="text-xs text-gray-400">
                  Audio notifications are disabled. Change the sound setting above to enable audio alerts.
                </Text>
              </div>
            )}
          </div>

          {/* Per-Camera Notification Settings */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-2 flex items-center gap-2">
              <Camera className="h-5 w-5 text-blue-400" />
              <Text className="font-medium text-gray-300">Camera Notifications</Text>
            </div>

            {/* Helper text explaining filter precedence */}
            <Text className="mb-4 text-xs text-gray-500">
              Per-camera thresholds work with global risk filters. An alert must pass both the
              global risk level filter AND meet the camera&apos;s minimum threshold to trigger a
              notification.
            </Text>

            {cameraSettingsLoading ? (
              <div className="skeleton h-24 w-full"></div>
            ) : cameras.length === 0 ? (
              <Text className="text-sm text-gray-500">No cameras configured</Text>
            ) : (
              <div className="space-y-3">
                {cameras.map((camera) => {
                  const setting = getCameraSetting(camera.id);
                  const isEnabled = setting?.enabled ?? true;
                  const threshold = setting?.risk_threshold ?? 0;

                  // Detect potential conflicts between camera threshold and global filters
                  const conflict = detectThresholdConflict(
                    threshold,
                    preferences?.risk_filters ?? []
                  );

                  return (
                    <div
                      key={camera.id}
                      className={`rounded-lg border bg-gray-900/50 p-3 ${
                        conflict.hasConflict && isEnabled
                          ? 'border-amber-500/50'
                          : 'border-gray-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleToggleCameraNotification(camera.id, isEnabled)}
                            disabled={cameraSettingUpdateMutation.isPending}
                            className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                              isEnabled
                                ? 'bg-[#76B900]/20 text-[#76B900]'
                                : 'bg-gray-700 text-gray-500'
                            }`}
                            aria-label={`Toggle notifications for ${camera.name}`}
                          >
                            {isEnabled ? (
                              <Bell className="h-4 w-4" />
                            ) : (
                              <BellOff className="h-4 w-4" />
                            )}
                          </button>
                          <div>
                            <Text className="font-medium text-white">{camera.name}</Text>
                            <Text className="text-xs text-gray-500">{camera.id}</Text>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Text className="text-xs text-gray-500">Min Risk:</Text>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            value={threshold}
                            onChange={(e) =>
                              handleCameraThresholdChange(camera.id, parseInt(e.target.value, 10))
                            }
                            disabled={!isEnabled || cameraSettingUpdateMutation.isPending}
                            className="h-2 w-20 cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                          />
                          <Badge color={isEnabled ? 'green' : 'gray'} size="sm">
                            {threshold}%
                          </Badge>
                        </div>
                      </div>

                      {/* Show warning when camera threshold conflicts with global filters */}
                      {conflict.hasConflict && isEnabled && (
                        <div className="mt-2 flex items-start gap-2 rounded bg-amber-500/10 px-2 py-1.5">
                          <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
                          <Text className="text-xs text-amber-400">{conflict.message}</Text>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Quiet Hours */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Moon className="h-5 w-5 text-purple-400" />
                <Text className="font-medium text-gray-300">Quiet Hours</Text>
              </div>
              <Button
                size="xs"
                onClick={() => setShowQuietHoursForm(!showQuietHoursForm)}
                className="bg-purple-600 text-white hover:bg-purple-700"
              >
                <Plus className="mr-1 h-3 w-3" />
                Add Period
              </Button>
            </div>

            <Text className="mb-3 text-xs text-gray-500">
              Notifications are silenced during quiet hours
            </Text>

            {/* New Quiet Hours Form */}
            {showQuietHoursForm && (
              <div className="mb-4 rounded-lg border border-purple-500/30 bg-purple-500/10 p-4">
                <div className="mb-3">
                  <Text className="mb-1 text-sm text-gray-300">Label</Text>
                  <input
                    type="text"
                    value={newQuietHours.label}
                    onChange={(e) =>
                      setNewQuietHours((prev) => ({ ...prev, label: e.target.value }))
                    }
                    placeholder="e.g., Night Time"
                    className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none"
                  />
                </div>

                <div className="mb-3 grid grid-cols-2 gap-3">
                  <div>
                    <Text className="mb-1 text-sm text-gray-300">Start Time</Text>
                    <input
                      type="time"
                      value={newQuietHours.start_time}
                      onChange={(e) =>
                        setNewQuietHours((prev) => ({ ...prev, start_time: e.target.value }))
                      }
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-white focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <Text className="mb-1 text-sm text-gray-300">End Time</Text>
                    <input
                      type="time"
                      value={newQuietHours.end_time}
                      onChange={(e) =>
                        setNewQuietHours((prev) => ({ ...prev, end_time: e.target.value }))
                      }
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-white focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div className="mb-3">
                  <Text className="mb-1 text-sm text-gray-300">Days</Text>
                  <div className="flex flex-wrap gap-1">
                    {DAYS_OF_WEEK.map((day) => (
                      <button
                        key={day.value}
                        onClick={() => handleToggleDay(day.value)}
                        className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                          newQuietHours.days.includes(day.value)
                            ? 'bg-purple-500 text-white'
                            : 'bg-gray-700 text-gray-400'
                        }`}
                      >
                        {day.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button
                    size="xs"
                    onClick={() => setShowQuietHoursForm(false)}
                    className="bg-gray-700 text-white hover:bg-gray-600"
                  >
                    Cancel
                  </Button>
                  <Button
                    size="xs"
                    onClick={handleCreateQuietHours}
                    disabled={!newQuietHours.label.trim() || quietHoursCreateMutation.isPending}
                    className="bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50"
                  >
                    {quietHoursCreateMutation.isPending ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      'Save'
                    )}
                  </Button>
                </div>
              </div>
            )}

            {/* Existing Quiet Hours Periods */}
            {quietHoursLoading ? (
              <div className="skeleton h-16 w-full"></div>
            ) : quietHoursPeriods.length === 0 ? (
              <Text className="text-sm text-gray-500">No quiet hours configured</Text>
            ) : (
              <div className="space-y-2">
                {quietHoursPeriods.map((period) => (
                  <div
                    key={period.id}
                    className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-900/50 p-3"
                  >
                    <div className="flex items-center gap-3">
                      <Clock className="h-4 w-4 text-purple-400" />
                      <div>
                        <Text className="font-medium text-white">{period.label}</Text>
                        <Text className="text-xs text-gray-500">
                          {period.start_time.slice(0, 5)} - {period.end_time.slice(0, 5)}
                          {' | '}
                          {period.days
                            .map(
                              (d: string) => d.slice(0, 3).charAt(0).toUpperCase() + d.slice(1, 3)
                            )
                            .join(', ')}
                        </Text>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteQuietHours(period.id)}
                      disabled={quietHoursDeleteMutation.isPending}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-red-400 transition-colors hover:bg-red-500/20"
                      aria-label={`Delete ${period.label}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Notifications Enabled Status */}
          <div className="flex items-center justify-between border-b border-gray-800 pb-4">
            <div>
              <Text className="font-medium text-gray-300">System Notifications</Text>
              <Text className="mt-1 text-xs text-gray-500">
                Backend notification system status (from environment)
              </Text>
            </div>
            <Badge color={config.notification_enabled ? 'green' : 'gray'} size="lg">
              {config.notification_enabled ? 'Enabled' : 'Disabled'}
            </Badge>
          </div>

          {/* Email (SMTP) Configuration */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-blue-400" />
                <Text className="font-medium text-gray-300">Email (SMTP)</Text>
              </div>
              <Badge color={config.email_configured ? 'green' : 'gray'} size="sm">
                {config.email_configured ? 'Configured' : 'Not Configured'}
              </Badge>
            </div>

            {config.email_configured ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <Text className="text-gray-500">SMTP Host</Text>
                    <Text className="text-white">{config.smtp_host || '-'}</Text>
                  </div>
                  <div>
                    <Text className="text-gray-500">Port</Text>
                    <Text className="text-white">{config.smtp_port || '-'}</Text>
                  </div>
                  <div>
                    <Text className="text-gray-500">From Address</Text>
                    <Text className="text-white">{config.smtp_from_address || '-'}</Text>
                  </div>
                  <div>
                    <Text className="text-gray-500">TLS</Text>
                    <Text className="text-white">
                      {config.smtp_use_tls ? 'Enabled' : 'Disabled'}
                    </Text>
                  </div>
                </div>

                {config.default_email_recipients.length > 0 && (
                  <div>
                    <Text className="mb-2 text-gray-500">Default Recipients</Text>
                    <div className="flex flex-wrap gap-2">
                      {config.default_email_recipients.map((email, index) => (
                        <Badge key={index} color="blue" size="sm">
                          {email}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                <Button
                  onClick={() => void handleTestEmail()}
                  disabled={testingEmail || !config.notification_enabled}
                  className="mt-3 bg-blue-600 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                  size="sm"
                >
                  {testingEmail ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="mr-2 h-4 w-4" />
                      Send Test Email
                    </>
                  )}
                </Button>
              </div>
            ) : (
              <div className="py-4 text-center">
                <Text className="text-gray-500">Email notifications are not configured.</Text>
                <Text className="mt-1 text-xs text-gray-600">
                  Set SMTP_HOST, SMTP_FROM_ADDRESS, and optionally SMTP_USER/SMTP_PASSWORD
                  environment variables to enable email notifications.
                </Text>
              </div>
            )}
          </div>

          {/* Webhook Configuration */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Webhook className="h-5 w-5 text-purple-400" />
                <Text className="font-medium text-gray-300">Webhook</Text>
              </div>
              <Badge color={config.webhook_configured ? 'green' : 'gray'} size="sm">
                {config.webhook_configured ? 'Configured' : 'Not Configured'}
              </Badge>
            </div>

            {config.webhook_configured ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="col-span-2">
                    <Text className="text-gray-500">Webhook URL</Text>
                    <Text className="break-all text-white">
                      {config.default_webhook_url || '-'}
                    </Text>
                  </div>
                  <div>
                    <Text className="text-gray-500">Timeout</Text>
                    <Text className="text-white">{config.webhook_timeout_seconds || 30}s</Text>
                  </div>
                </div>

                <Button
                  onClick={() => void handleTestWebhook()}
                  disabled={testingWebhook || !config.notification_enabled}
                  className="mt-3 bg-purple-600 text-white hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50"
                  size="sm"
                >
                  {testingWebhook ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="mr-2 h-4 w-4" />
                      Send Test Webhook
                    </>
                  )}
                </Button>
              </div>
            ) : (
              <div className="py-4 text-center">
                <Text className="text-gray-500">Webhook notifications are not configured.</Text>
                <Text className="mt-1 text-xs text-gray-600">
                  Set DEFAULT_WEBHOOK_URL environment variable to enable webhook notifications.
                </Text>
              </div>
            )}
          </div>

          {/* Available Channels Summary */}
          <div className="border-t border-gray-800 pt-4">
            <Text className="mb-2 text-sm text-gray-400">Available Notification Channels</Text>
            <div className="flex flex-wrap gap-2">
              {config.available_channels.length > 0 ? (
                config.available_channels.map((channel) => (
                  <Badge key={channel} color="green" size="sm">
                    {channel.toUpperCase()}
                  </Badge>
                ))
              ) : (
                <Text className="text-sm text-gray-500">No notification channels configured</Text>
              )}
            </div>
          </div>

          {/* Configuration Note */}
          <div className="mt-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
            <Text className="text-sm text-yellow-400">
              <strong>Note:</strong> Email and webhook settings are configured via environment
              variables. Changes require restarting the backend service. Notification preferences
              (enabled/disabled, sound, risk filters, camera settings, quiet hours) are stored in
              the database and take effect immediately.
            </Text>
          </div>
        </div>
      )}
    </Card>
  );
}
