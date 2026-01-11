/**
 * GlobalNotificationPreferences component displays and manages global notification settings.
 * - Enable/disable all notifications
 * - Select notification sound
 * - Configure risk level filters
 */
import { Card, Title, Text, Badge, Select, SelectItem } from '@tremor/react';
import { AlertCircle, Bell, Loader2, Volume2 } from 'lucide-react';
import { useState, useCallback, useMemo } from 'react';

import {
  useGlobalNotificationPreferencesQuery,
  useNotificationPreferencesMutation,
} from '../../hooks/useNotificationPreferencesQuery';
import {
  NOTIFICATION_SOUNDS,
  RISK_LEVELS,
  type NotificationSound,
  type RiskLevel,
} from '../../types/notificationPreferences';

export interface GlobalNotificationPreferencesProps {
  className?: string;
}

/**
 * GlobalNotificationPreferences displays and manages global notification settings.
 *
 * Features:
 * - Master toggle for all notifications
 * - Sound selection (none, default, alert, chime, urgent)
 * - Risk level filters (which risk levels trigger notifications)
 * - Real-time updates
 */
export default function GlobalNotificationPreferences({
  className,
}: GlobalNotificationPreferencesProps) {
  const { preferences, isLoading, error, refetch } = useGlobalNotificationPreferencesQuery();
  const { updateGlobalMutation } = useNotificationPreferencesMutation();

  // Local state for optimistic updates
  const [localEnabled, setLocalEnabled] = useState<boolean | null>(null);
  const [localSound, setLocalSound] = useState<NotificationSound | null>(null);
  const [localRiskFilters, setLocalRiskFilters] = useState<RiskLevel[] | null>(null);

  // Effective values (local state overrides server state)
  const enabled = localEnabled ?? preferences?.enabled ?? true;
  const sound = localSound ?? (preferences?.sound as NotificationSound) ?? 'default';
  const riskFilters = useMemo<RiskLevel[]>(
    () => localRiskFilters ?? preferences?.risk_filters ?? [],
    [localRiskFilters, preferences?.risk_filters]
  );

  // Handle enable toggle
  const handleToggle = useCallback(async () => {
    const newEnabled = !enabled;
    setLocalEnabled(newEnabled);
    try {
      await updateGlobalMutation.mutateAsync({ enabled: newEnabled });
      setLocalEnabled(null); // Clear local state after successful update
    } catch {
      setLocalEnabled(null); // Revert on error
    }
  }, [enabled, updateGlobalMutation]);

  // Handle sound change
  const handleSoundChange = useCallback(
    async (newSound: string) => {
      const soundValue = newSound as NotificationSound;
      setLocalSound(soundValue);
      try {
        await updateGlobalMutation.mutateAsync({ sound: soundValue });
        setLocalSound(null);
      } catch {
        setLocalSound(null);
      }
    },
    [updateGlobalMutation]
  );

  // Handle risk filter toggle
  const handleRiskFilterToggle = useCallback(
    async (level: RiskLevel) => {
      const newFilters = riskFilters.includes(level)
        ? riskFilters.filter((l) => l !== level)
        : [...riskFilters, level];
      setLocalRiskFilters(newFilters);
      try {
        await updateGlobalMutation.mutateAsync({ risk_filters: newFilters });
        setLocalRiskFilters(null);
      } catch {
        setLocalRiskFilters(null);
      }
    },
    [riskFilters, updateGlobalMutation]
  );

  const isUpdating = updateGlobalMutation.isPending;

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Bell className="h-5 w-5 text-[#76B900]" />
        Notification Preferences
      </Title>

      <Text className="mb-6 text-sm text-gray-400">
        Configure how and when you receive notifications about security events.
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

      {updateGlobalMutation.error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">
            Failed to update: {updateGlobalMutation.error.message}
          </Text>
        </div>
      )}

      {!isLoading && preferences && (
        <div className="space-y-6">
          {/* Master Toggle */}
          <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="flex items-center gap-3">
              <Bell className="h-5 w-5 text-gray-400" />
              <div>
                <Text className="font-medium text-gray-300">Enable Notifications</Text>
                <Text className="text-xs text-gray-500">
                  Master switch for all notification types
                </Text>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => void handleToggle()}
                disabled={isUpdating}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900 ${
                  enabled ? 'bg-[#76B900]' : 'bg-gray-600'
                } ${isUpdating ? 'cursor-not-allowed opacity-50' : ''}`}
                role="switch"
                aria-checked={enabled}
                aria-label="Enable notifications"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    enabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              <Badge color={enabled ? 'green' : 'gray'} size="sm">
                {enabled ? 'On' : 'Off'}
              </Badge>
            </div>
          </div>

          {/* Sound Selection */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-3 flex items-center gap-3">
              <Volume2 className="h-5 w-5 text-gray-400" />
              <div>
                <Text className="font-medium text-gray-300">Notification Sound</Text>
                <Text className="text-xs text-gray-500">
                  Choose the sound for notifications
                </Text>
              </div>
            </div>
            <Select
              value={sound}
              onValueChange={(value) => void handleSoundChange(value)}
              disabled={!enabled || isUpdating}
              className="mt-2"
            >
              {NOTIFICATION_SOUNDS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </Select>
          </div>

          {/* Risk Level Filters */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-3">
              <Text className="font-medium text-gray-300">Risk Level Filters</Text>
              <Text className="text-xs text-gray-500">
                Select which risk levels should trigger notifications
              </Text>
            </div>
            <div className="flex flex-wrap gap-2">
              {RISK_LEVELS.map((level) => {
                const isSelected = riskFilters.includes(level.value);
                return (
                  <button
                    key={level.value}
                    onClick={() => void handleRiskFilterToggle(level.value)}
                    disabled={!enabled || isUpdating}
                    className={`rounded-lg border px-4 py-2 text-sm font-medium transition-all ${
                      isSelected
                        ? `border-${level.color}-500 bg-${level.color}-500/20 text-${level.color}-400`
                        : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600'
                    } ${!enabled || isUpdating ? 'cursor-not-allowed opacity-50' : ''}`}
                  >
                    {level.label}
                  </button>
                );
              })}
            </div>
            {riskFilters.length === 0 && enabled && (
              <Text className="mt-2 text-xs text-yellow-400">
                Warning: No risk levels selected. You will not receive any notifications.
              </Text>
            )}
          </div>
        </div>
      )}

      {/* Info note */}
      <div className="mt-6 rounded-lg border border-blue-500/30 bg-blue-500/10 p-3">
        <Text className="text-sm text-blue-400">
          <strong>Tip:</strong> Use quiet hours below to temporarily silence notifications during
          specific time periods without disabling them entirely.
        </Text>
      </div>
    </Card>
  );
}
