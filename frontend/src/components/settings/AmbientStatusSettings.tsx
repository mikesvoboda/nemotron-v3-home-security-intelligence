/**
 * AmbientStatusSettings component
 *
 * Settings panel for configuring ambient status awareness features:
 * - Ambient background effects
 * - Audio notifications with volume control
 * - Desktop notifications with permission management
 * - Favicon badge
 */

import { Card, Title, Text, Switch, Badge, Button } from '@tremor/react';
import { clsx } from 'clsx';
import { Bell, BellOff, Eye, EyeOff, Monitor, MonitorOff, Volume2, VolumeX } from 'lucide-react';
import { useCallback } from 'react';

import { useDesktopNotifications } from '../../hooks/useDesktopNotifications';
import { useSettings } from '../../hooks/useSettings';

export interface AmbientStatusSettingsProps {
  className?: string;
}

/**
 * Settings section for ambient status awareness features
 */
export default function AmbientStatusSettings({ className }: AmbientStatusSettingsProps) {
  const {
    ambientEnabled,
    setAmbientEnabled,
    audioEnabled,
    setAudioEnabled,
    audioVolume,
    setAudioVolume,
    desktopNotificationsEnabled,
    setDesktopNotificationsEnabled,
    suppressNotificationsWhenFocused,
    setSuppressNotificationsWhenFocused,
    faviconBadgeEnabled,
    setFaviconBadgeEnabled,
    enableAllAmbientStatus,
    disableAllAmbientStatus,
  } = useSettings();

  const { hasPermission, isDenied, isSupported, requestPermission } = useDesktopNotifications();

  const handleRequestPermission = useCallback(async () => {
    await requestPermission();
  }, [requestPermission]);

  const handleVolumeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setAudioVolume(parseFloat(e.target.value));
    },
    [setAudioVolume]
  );

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="ambient-status-settings"
    >
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Title className="text-white">Ambient Status Awareness</Title>
          <Text className="mt-1 text-gray-400">
            Configure visual and audio cues that communicate system status
          </Text>
        </div>
        <div className="flex gap-2">
          <Button
            size="xs"
            variant="secondary"
            onClick={enableAllAmbientStatus}
            className="text-xs"
          >
            Enable All
          </Button>
          <Button
            size="xs"
            variant="secondary"
            onClick={disableAllAmbientStatus}
            className="text-xs"
          >
            Disable All
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {/* Ambient Background Effects */}
        <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {ambientEnabled ? (
                <Eye className="h-5 w-5 text-[#76B900]" />
              ) : (
                <EyeOff className="h-5 w-5 text-gray-500" />
              )}
              <div>
                <Text className="font-medium text-gray-200">Ambient Background</Text>
                <Text className="mt-1 text-xs text-gray-500">
                  Subtle color shifts based on threat level
                </Text>
              </div>
            </div>
            <Switch
              checked={ambientEnabled}
              onChange={setAmbientEnabled}
              className="focus:ring-[#76B900]"
              aria-label="Enable ambient background effects"
            />
          </div>
        </div>

        {/* Audio Notifications */}
        <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {audioEnabled ? (
                <Volume2 className="h-5 w-5 text-[#76B900]" />
              ) : (
                <VolumeX className="h-5 w-5 text-gray-500" />
              )}
              <div>
                <Text className="font-medium text-gray-200">Audio Alerts</Text>
                <Text className="mt-1 text-xs text-gray-500">
                  Sound notifications for security events
                </Text>
              </div>
            </div>
            <Switch
              checked={audioEnabled}
              onChange={setAudioEnabled}
              className="focus:ring-[#76B900]"
              aria-label="Enable audio notifications"
            />
          </div>

          {/* Volume Slider */}
          {audioEnabled && (
            <div className="mt-4 pl-8">
              <div className="flex items-center gap-4">
                <Text className="w-16 text-sm text-gray-400">Volume</Text>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={audioVolume}
                  onChange={handleVolumeChange}
                  className="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                  aria-label="Audio volume"
                />
                <Text className="w-10 text-sm text-gray-400">{Math.round(audioVolume * 100)}%</Text>
              </div>
            </div>
          )}
        </div>

        {/* Desktop Notifications */}
        <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {desktopNotificationsEnabled && hasPermission ? (
                <Bell className="h-5 w-5 text-[#76B900]" />
              ) : (
                <BellOff className="h-5 w-5 text-gray-500" />
              )}
              <div>
                <Text className="font-medium text-gray-200">Desktop Notifications</Text>
                <Text className="mt-1 text-xs text-gray-500">Browser notifications for alerts</Text>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {/* Permission Status Badge */}
              {isSupported && (
                <Badge size="sm" color={hasPermission ? 'green' : isDenied ? 'red' : 'gray'}>
                  {hasPermission ? 'Granted' : isDenied ? 'Blocked' : 'Not Set'}
                </Badge>
              )}
              {!isSupported && (
                <Badge size="sm" color="gray">
                  Not Supported
                </Badge>
              )}
              <Switch
                checked={desktopNotificationsEnabled}
                onChange={setDesktopNotificationsEnabled}
                className="focus:ring-[#76B900]"
                aria-label="Enable desktop notifications"
                disabled={!isSupported}
              />
            </div>
          </div>

          {/* Permission Request Button */}
          {isSupported && !hasPermission && !isDenied && (
            <div className="mt-4 pl-8">
              <Button
                size="xs"
                variant="secondary"
                onClick={() => void handleRequestPermission()}
                className="bg-[#76B900] text-gray-950 hover:bg-[#5a8f00]"
              >
                Request Permission
              </Button>
            </div>
          )}

          {/* Denied Warning */}
          {isDenied && (
            <div className="mt-4 pl-8">
              <Text className="text-xs text-red-400">
                Notifications are blocked. Please enable them in your browser settings.
              </Text>
            </div>
          )}

          {/* Suppress When Focused Option */}
          {desktopNotificationsEnabled && hasPermission && (
            <div className="mt-4 border-t border-gray-800 pl-8 pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <Text className="text-sm text-gray-300">Suppress when focused</Text>
                  <Text className="mt-1 text-xs text-gray-500">
                    Don&apos;t show notifications when the app is in focus
                  </Text>
                </div>
                <Switch
                  checked={suppressNotificationsWhenFocused}
                  onChange={setSuppressNotificationsWhenFocused}
                  className="focus:ring-[#76B900]"
                  aria-label="Suppress notifications when window has focus"
                />
              </div>
            </div>
          )}
        </div>

        {/* Favicon Badge */}
        <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {faviconBadgeEnabled ? (
                <Monitor className="h-5 w-5 text-[#76B900]" />
              ) : (
                <MonitorOff className="h-5 w-5 text-gray-500" />
              )}
              <div>
                <Text className="font-medium text-gray-200">Favicon Badge</Text>
                <Text className="mt-1 text-xs text-gray-500">
                  Show alert count on browser tab icon and title
                </Text>
              </div>
            </div>
            <Switch
              checked={faviconBadgeEnabled}
              onChange={setFaviconBadgeEnabled}
              className="focus:ring-[#76B900]"
              aria-label="Enable favicon badge"
            />
          </div>
        </div>

        {/* Info Note */}
        <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-4">
          <Text className="text-sm text-blue-400">
            <strong>Note:</strong> Ambient features respect your system&apos;s reduced motion
            preferences. Critical animations will be disabled when reduced motion is enabled.
          </Text>
        </div>
      </div>
    </Card>
  );
}
