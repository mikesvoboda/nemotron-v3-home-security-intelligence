/**
 * QueueSettings - Reusable queue configuration panel
 *
 * Provides UI controls for managing Redis queue settings:
 * - Configure maximum queue size
 * - Configure backpressure threshold percentage
 *
 * Can be used standalone or embedded within other settings panels.
 *
 * @see NEM-3551 - Add Rate Limiting & Queue Settings UI
 */

import { Text, NumberInput } from '@tremor/react';

export interface QueueSettingsProps {
  /** Maximum size of Redis queues */
  maxSize: number;
  /** Queue fill ratio (0-100) at which to start backpressure warnings */
  backpressureThreshold: number;
  /** Callback when max size changes */
  onMaxSizeChange: (value: number) => void;
  /** Callback when backpressure threshold changes */
  onBackpressureThresholdChange: (value: number) => void;
  /** Whether the component is in a loading/disabled state */
  disabled?: boolean;
  /** Optional className for styling */
  className?: string;
}

/**
 * QueueSettings component
 *
 * A reusable panel for configuring Redis queue settings.
 * Includes controls for maximum queue size and backpressure threshold.
 */
export default function QueueSettings({
  maxSize,
  backpressureThreshold,
  onMaxSizeChange,
  onBackpressureThresholdChange,
  disabled = false,
  className,
}: QueueSettingsProps) {
  return (
    <div className={className} data-testid="queue-settings">
      <Text className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-400">
        Queue Settings
      </Text>
      <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {/* Max Queue Size */}
          <div>
            <label htmlFor="max-queue-size" className="mb-1 block text-xs text-gray-500">
              Max Size
            </label>
            <NumberInput
              id="max-queue-size"
              value={maxSize}
              onValueChange={(value) => onMaxSizeChange(value ?? 10000)}
              min={100}
              max={100000}
              step={100}
              disabled={disabled}
              className="bg-[#1A1A1A]"
              data-testid="input-max-queue-size"
              aria-label="Maximum queue size"
            />
            <Text className="mt-1 text-xs text-gray-600">
              Maximum items in Redis queues (100-100,000)
            </Text>
          </div>
          {/* Backpressure Threshold */}
          <div>
            <label htmlFor="backpressure-threshold" className="mb-1 block text-xs text-gray-500">
              Backpressure Threshold (%)
            </label>
            <NumberInput
              id="backpressure-threshold"
              value={backpressureThreshold}
              onValueChange={(value) => onBackpressureThresholdChange(value ?? 80)}
              min={50}
              max={100}
              step={5}
              disabled={disabled}
              className="bg-[#1A1A1A]"
              data-testid="input-backpressure-threshold"
              aria-label="Backpressure threshold percentage"
            />
            <Text className="mt-1 text-xs text-gray-600">
              Queue usage % that triggers backpressure warnings
            </Text>
          </div>
        </div>
      </div>
    </div>
  );
}
