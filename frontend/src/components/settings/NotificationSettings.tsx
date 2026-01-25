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
  Moon,
  Plus,
  Send,
  Settings,
  Save,
  Trash2,
  Volume2,
  Webhook,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { useCamerasQuery } from '../../hooks/useCamerasQuery';
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
  updateNotificationConfig,
  type NotificationConfig,
  type NotificationConfigUpdate,
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

  // Channel configuration form state (NEM-3632)
  const [channelConfig, setChannelConfig] = useState<{
    smtp_enabled: boolean;
    smtp_host: string;
    smtp_port: string;
    smtp_from_address: string;
    webhook_enabled: boolean;
    default_webhook_url: string;
  }>({
    smtp_enabled: false,
    smtp_host: '',
    smtp_port: '587',
    smtp_from_address: '',
    webhook_enabled: false,
    default_webhook_url: '',
  });
  const [savingConfig, setSavingConfig] = useState(false);
  const [configSaveResult, setConfigSaveResult] = useState<{
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
        // Initialize channel config form with loaded values
        setChannelConfig({
          smtp_enabled: data.email_configured,
          smtp_host: data.smtp_host || '',
          smtp_port: data.smtp_port?.toString() || '587',
          smtp_from_address: data.smtp_from_address || '',
          webhook_enabled: data.webhook_configured,
          default_webhook_url: data.default_webhook_url || '',
        });
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

  // Save channel configuration (NEM-3632)
  const handleSaveChannelConfig = useCallback(async () => {
    try {
      setSavingConfig(true);
      setConfigSaveResult(null);

      const update: NotificationConfigUpdate = {
        smtp_enabled: channelConfig.smtp_enabled,
        smtp_host: channelConfig.smtp_host || null,
        smtp_port: channelConfig.smtp_port ? parseInt(channelConfig.smtp_port, 10) : null,
        smtp_from_address: channelConfig.smtp_from_address || null,
        webhook_enabled: channelConfig.webhook_enabled,
        default_webhook_url: channelConfig.default_webhook_url || null,
      };

      const result = await updateNotificationConfig(update);
      setConfigSaveResult({
        success: true,
        message: result.message || 'Configuration updated successfully',
      });

      // Refresh config to sync with server state
      const newConfig = await fetchNotificationConfig();
      setConfig(newConfig);

      setTimeout(() => setConfigSaveResult(null), 5000);
    } catch (err) {
      setConfigSaveResult({
        success: false,
        message: err instanceof Error ? err.message : 'Failed to save configuration',
      });
    } finally {
      setSavingConfig(false);
    }
  }, [channelConfig]);

  // Toggle email channel
  const handleToggleEmailChannel = useCallback(() => {
    setChannelConfig((prev) => ({ ...prev, smtp_enabled: !prev.smtp_enabled }));
  }, []);

  // Toggle webhook channel
  const handleToggleWebhookChannel = useCallback(() => {
    setChannelConfig((prev) => ({ ...prev, webhook_enabled: !prev.webhook_enabled }));
  }, []);

  const isAnyLoading = loading || preferencesLoading;

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

          {/* Per-Camera Notification Settings */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center gap-2">
              <Camera className="h-5 w-5 text-blue-400" />
              <Text className="font-medium text-gray-300">Camera Notifications</Text>
            </div>

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

                  return (
                    <div
                      key={camera.id}
                      className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-900/50 p-3"
                    >
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

          {/* Configuration Save Result */}
          {configSaveResult && (
            <div
              className={`flex items-center gap-2 rounded-lg border p-4 ${
                configSaveResult.success
                  ? 'border-green-500/30 bg-green-500/10'
                  : 'border-red-500/30 bg-red-500/10'
              }`}
            >
              {configSaveResult.success ? (
                <CheckCircle className="h-5 w-5 flex-shrink-0 text-green-500" />
              ) : (
                <X className="h-5 w-5 flex-shrink-0 text-red-400" />
              )}
              <Text className={configSaveResult.success ? 'text-green-500' : 'text-red-400'}>
                {configSaveResult.message}
              </Text>
            </div>
          )}

          {/* Email (SMTP) Configuration */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-blue-400" />
                <Text className="font-medium text-gray-300">Email (SMTP)</Text>
              </div>
              <div className="flex items-center gap-3">
                <Badge color={channelConfig.smtp_enabled ? 'green' : 'gray'} size="sm">
                  {channelConfig.smtp_enabled ? 'Enabled' : 'Disabled'}
                </Badge>
                <button
                  onClick={handleToggleEmailChannel}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900 ${
                    channelConfig.smtp_enabled ? 'bg-blue-500' : 'bg-gray-600'
                  }`}
                  role="switch"
                  aria-checked={channelConfig.smtp_enabled}
                  aria-label="Toggle email channel"
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      channelConfig.smtp_enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="smtp-host" className="mb-1 block text-sm text-gray-400">
                    SMTP Host
                  </label>
                  <input
                    id="smtp-host"
                    type="text"
                    value={channelConfig.smtp_host}
                    onChange={(e) =>
                      setChannelConfig((prev) => ({ ...prev, smtp_host: e.target.value }))
                    }
                    placeholder="smtp.example.com"
                    className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label htmlFor="smtp-port" className="mb-1 block text-sm text-gray-400">
                    SMTP Port
                  </label>
                  <input
                    id="smtp-port"
                    type="number"
                    value={channelConfig.smtp_port}
                    onChange={(e) =>
                      setChannelConfig((prev) => ({ ...prev, smtp_port: e.target.value }))
                    }
                    placeholder="587"
                    className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="smtp-from" className="mb-1 block text-sm text-gray-400">
                  From Address
                </label>
                <input
                  id="smtp-from"
                  type="email"
                  value={channelConfig.smtp_from_address}
                  onChange={(e) =>
                    setChannelConfig((prev) => ({ ...prev, smtp_from_address: e.target.value }))
                  }
                  placeholder="alerts@example.com"
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                />
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
                disabled={testingEmail || !config.notification_enabled || !channelConfig.smtp_enabled}
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
          </div>

          {/* Webhook Configuration */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Webhook className="h-5 w-5 text-purple-400" />
                <Text className="font-medium text-gray-300">Webhook</Text>
              </div>
              <div className="flex items-center gap-3">
                <Badge color={channelConfig.webhook_enabled ? 'green' : 'gray'} size="sm">
                  {channelConfig.webhook_enabled ? 'Enabled' : 'Disabled'}
                </Badge>
                <button
                  onClick={handleToggleWebhookChannel}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-gray-900 ${
                    channelConfig.webhook_enabled ? 'bg-purple-500' : 'bg-gray-600'
                  }`}
                  role="switch"
                  aria-checked={channelConfig.webhook_enabled}
                  aria-label="Toggle webhook channel"
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      channelConfig.webhook_enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label htmlFor="webhook-url" className="mb-1 block text-sm text-gray-400">
                  Webhook URL
                </label>
                <input
                  id="webhook-url"
                  type="url"
                  value={channelConfig.default_webhook_url}
                  onChange={(e) =>
                    setChannelConfig((prev) => ({ ...prev, default_webhook_url: e.target.value }))
                  }
                  placeholder="https://hooks.example.com/notify"
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none"
                />
              </div>

              <Button
                onClick={() => void handleTestWebhook()}
                disabled={testingWebhook || !config.notification_enabled || !channelConfig.webhook_enabled}
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
          </div>

          {/* Save Configuration Button */}
          <div className="flex justify-end">
            <Button
              onClick={() => void handleSaveChannelConfig()}
              disabled={savingConfig}
              className="bg-[#76B900] text-white hover:bg-[#5a8c00] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {savingConfig ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Configuration
                </>
              )}
            </Button>
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
