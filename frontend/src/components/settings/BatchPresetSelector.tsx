/**
 * BatchPresetSelector - Preset selector for batch processing configuration
 *
 * Provides quick selection of predefined batch processing presets:
 * - Real-time: Fastest response with higher overhead
 * - Balanced: Default setting for most use cases
 * - Efficient: Lower overhead with delayed notifications
 *
 * @see NEM-3873 - Batch Config Validation
 */

import { Text } from '@tremor/react';
import { clsx } from 'clsx';
import { Zap, Scale, Gauge } from 'lucide-react';

import { BATCH_PRESETS, detectCurrentPreset, type BatchPreset } from '../../utils/batchSettingsValidation';

export interface BatchPresetSelectorProps {
  /** Callback when a preset is selected */
  onSelect: (preset: BatchPreset) => void;
  /** Current batch window seconds (for highlighting current preset) */
  currentWindowSeconds?: number;
  /** Current idle timeout seconds (for highlighting current preset) */
  currentIdleTimeoutSeconds?: number;
  /** Whether the component is disabled */
  disabled?: boolean;
  /** Optional className for styling */
  className?: string;
}

/**
 * Get icon component for preset
 */
function getPresetIcon(presetId: string) {
  switch (presetId) {
    case 'realtime':
      return Zap;
    case 'balanced':
      return Scale;
    case 'efficient':
      return Gauge;
    default:
      return Scale;
  }
}

/**
 * BatchPresetSelector component
 *
 * A group of buttons for selecting predefined batch processing presets.
 * Highlights the currently active preset if values match.
 */
export default function BatchPresetSelector({
  onSelect,
  currentWindowSeconds,
  currentIdleTimeoutSeconds,
  disabled = false,
  className,
}: BatchPresetSelectorProps) {
  // Detect which preset (if any) matches current values
  const currentPresetId = currentWindowSeconds !== undefined && currentIdleTimeoutSeconds !== undefined
    ? detectCurrentPreset(currentWindowSeconds, currentIdleTimeoutSeconds)
    : null;

  return (
    <div
      data-testid="batch-preset-selector"
      className={clsx('space-y-2', className)}
    >
      <Text className="text-xs font-medium uppercase tracking-wider text-gray-400">
        Quick Presets
      </Text>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {BATCH_PRESETS.map((preset) => {
          const Icon = getPresetIcon(preset.id);
          const isSelected = currentPresetId === preset.id;

          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => onSelect(preset)}
              disabled={disabled}
              aria-pressed={isSelected}
              className={clsx(
                'flex flex-col items-start rounded-lg border p-3 text-left transition-all',
                'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
                isSelected
                  ? 'border-[#76B900] bg-[#76B900]/10'
                  : 'border-gray-700 bg-[#1A1A1A] hover:border-gray-600',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            >
              <div className="flex w-full items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon
                    className={clsx(
                      'h-4 w-4',
                      isSelected ? 'text-[#76B900]' : 'text-gray-400'
                    )}
                  />
                  <Text
                    className={clsx(
                      'font-medium',
                      isSelected ? 'text-[#76B900]' : 'text-white'
                    )}
                  >
                    {preset.name}
                  </Text>
                </div>
                {isSelected && (
                  <span className="text-xs text-[#76B900]">Active</span>
                )}
              </div>

              <Text className="mt-2 line-clamp-2 text-xs text-gray-400">
                {preset.description}
              </Text>

              <Text className="mt-2 text-xs text-gray-500">
                {preset.windowSeconds}s window / {preset.idleTimeoutSeconds}s idle
              </Text>
            </button>
          );
        })}
      </div>
    </div>
  );
}
