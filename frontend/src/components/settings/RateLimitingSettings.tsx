/**
 * RateLimitingSettings - Reusable rate limiting configuration panel
 *
 * Provides UI controls for managing API rate limiting settings:
 * - Enable/disable rate limiting
 * - Configure requests per minute limit
 * - Configure burst allowance size
 *
 * Can be used standalone or embedded within other settings panels.
 *
 * @see NEM-3551 - Add Rate Limiting & Queue Settings UI
 */

import { Switch } from '@headlessui/react';
import { Text, NumberInput } from '@tremor/react';
import { clsx } from 'clsx';

export interface RateLimitingSettingsProps {
  /** Whether rate limiting is enabled */
  enabled: boolean;
  /** Maximum requests per minute per client IP */
  requestsPerMinute: number;
  /** Additional burst allowance for short request spikes */
  burstSize: number;
  /** Callback when enabled state changes */
  onEnabledChange: (enabled: boolean) => void;
  /** Callback when requests per minute changes */
  onRequestsPerMinuteChange: (value: number) => void;
  /** Callback when burst size changes */
  onBurstSizeChange: (value: number) => void;
  /** Whether the component is in a loading/disabled state */
  disabled?: boolean;
  /** Optional className for styling */
  className?: string;
}

/**
 * RateLimitingSettings component
 *
 * A reusable panel for configuring API rate limiting settings.
 * Includes controls for enabling rate limiting, setting request limits,
 * and configuring burst allowance.
 */
export default function RateLimitingSettings({
  enabled,
  requestsPerMinute,
  burstSize,
  onEnabledChange,
  onRequestsPerMinuteChange,
  onBurstSizeChange,
  disabled = false,
  className,
}: RateLimitingSettingsProps) {
  return (
    <div className={className} data-testid="rate-limiting-settings">
      <Text className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-400">
        Rate Limiting
      </Text>
      <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {/* Requests per minute */}
          <div>
            <label htmlFor="requests-per-minute" className="mb-1 block text-xs text-gray-500">
              Requests/min
            </label>
            <NumberInput
              id="requests-per-minute"
              value={requestsPerMinute}
              onValueChange={(value) => onRequestsPerMinuteChange(value ?? 60)}
              min={1}
              max={10000}
              step={1}
              disabled={disabled}
              className="bg-[#1A1A1A]"
              data-testid="input-requests-per-minute"
              aria-label="Requests per minute"
            />
            <Text className="mt-1 text-xs text-gray-600">
              Max requests per minute per client
            </Text>
          </div>
          {/* Burst size */}
          <div>
            <label htmlFor="burst-size" className="mb-1 block text-xs text-gray-500">
              Burst Size
            </label>
            <NumberInput
              id="burst-size"
              value={burstSize}
              onValueChange={(value) => onBurstSizeChange(value ?? 10)}
              min={1}
              max={100}
              step={1}
              disabled={disabled}
              className="bg-[#1A1A1A]"
              data-testid="input-burst-size"
              aria-label="Burst size"
            />
            <Text className="mt-1 text-xs text-gray-600">
              Extra allowance for request spikes
            </Text>
          </div>
          {/* Enabled toggle */}
          <div>
            <label htmlFor="rate-limit-enabled" className="mb-1 block text-xs text-gray-500">
              Enabled
            </label>
            <div className="flex h-[38px] items-center">
              <Switch
                id="rate-limit-enabled"
                checked={enabled}
                onChange={onEnabledChange}
                disabled={disabled}
                aria-label="Rate limiting enabled"
                data-testid="switch-rate-limit-enabled"
                className={clsx(
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
                  enabled ? 'bg-[#76B900]' : 'bg-gray-600',
                  disabled && 'cursor-not-allowed opacity-50'
                )}
              >
                <span
                  className={clsx(
                    'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                    enabled ? 'translate-x-6' : 'translate-x-1'
                  )}
                />
              </Switch>
              <span className="ml-2 text-sm text-gray-400">{enabled ? 'On' : 'Off'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
