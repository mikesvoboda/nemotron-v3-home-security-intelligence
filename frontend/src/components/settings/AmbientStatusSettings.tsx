/**
 * AmbientStatusSettings component
 *
 * Settings panel for configuring ambient status awareness features:
 * - Ambient background effects
 * - Favicon badge
 */

import { Card, Title, Text, Switch, Button } from '@tremor/react';
import { clsx } from 'clsx';
import { Eye, EyeOff, Monitor, MonitorOff } from 'lucide-react';

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
    faviconBadgeEnabled,
    setFaviconBadgeEnabled,
    enableAllAmbientStatus,
    disableAllAmbientStatus,
  } = useSettings();

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="ambient-status-settings"
    >
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Title className="text-white">Ambient Status Awareness</Title>
          <Text className="mt-1 text-gray-400">
            Configure visual cues that communicate system status
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
