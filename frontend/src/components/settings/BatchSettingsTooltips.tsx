/**
 * BatchSettingsTooltips - Validation feedback and tooltips for batch settings
 *
 * Provides:
 * - Validation warnings and errors for batch settings
 * - Latency impact preview
 *
 * @see NEM-3873 - Batch Config Validation
 */

import { Text } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertTriangle, AlertCircle, Clock } from 'lucide-react';

import {
  validateBatchSettings,
  calculateLatencyImpact,
} from '../../utils/batchSettingsValidation';

// ============================================================================
// Props
// ============================================================================

export interface BatchSettingsValidationDisplayProps {
  /** Current batch window in seconds */
  windowSeconds: number;
  /** Current idle timeout in seconds */
  idleTimeoutSeconds: number;
  /** Optional className for styling */
  className?: string;
}

export interface BatchSettingsLatencyPreviewProps {
  /** Current batch window in seconds */
  windowSeconds: number;
  /** Current idle timeout in seconds */
  idleTimeoutSeconds: number;
  /** Optional className for styling */
  className?: string;
}

export interface BatchSettingsTooltipsProps {
  /** Current batch window in seconds */
  windowSeconds: number;
  /** Current idle timeout in seconds */
  idleTimeoutSeconds: number;
  /** Optional className for styling */
  className?: string;
}

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Displays validation warnings and errors for batch settings
 */
export function BatchSettingsValidationDisplay({
  windowSeconds,
  idleTimeoutSeconds,
  className,
}: BatchSettingsValidationDisplayProps) {
  const validation = validateBatchSettings(windowSeconds, idleTimeoutSeconds);

  // Don't render if no issues
  if (validation.errors.length === 0 && validation.warnings.length === 0) {
    return null;
  }

  return (
    <div className={clsx('space-y-2', className)}>
      {/* Errors */}
      {validation.errors.length > 0 && (
        <div
          data-testid="batch-validation-errors"
          className="rounded-lg border border-red-500/30 bg-red-500/10 p-3"
        >
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0 text-red-400 mt-0.5" />
            <div className="space-y-1">
              {validation.errors.map((error, index) => (
                <Text key={index} className="text-sm text-red-400">
                  {error}
                </Text>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Warnings */}
      {validation.warnings.length > 0 && (
        <div
          data-testid="batch-validation-warnings"
          className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3"
        >
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-yellow-400 mt-0.5" />
            <div className="space-y-1">
              {validation.warnings.map((warning, index) => (
                <Text key={index} className="text-sm text-yellow-400">
                  {warning}
                </Text>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Displays latency impact preview for current settings
 */
export function BatchSettingsLatencyPreview({
  windowSeconds,
  idleTimeoutSeconds,
  className,
}: BatchSettingsLatencyPreviewProps) {
  const latency = calculateLatencyImpact(windowSeconds, idleTimeoutSeconds);

  return (
    <div
      data-testid="batch-latency-preview"
      className={clsx(
        'rounded-lg border border-gray-700 bg-[#1A1A1A] p-3',
        className
      )}
    >
      <div className="flex items-start gap-2">
        <Clock className="h-4 w-4 flex-shrink-0 text-gray-400 mt-0.5" />
        <div>
          <Text className="text-sm font-medium text-gray-300">
            Estimated Event Latency
          </Text>
          <Text className="mt-1 text-xs text-gray-400">
            {latency.description}
          </Text>
          <div className="mt-2 flex items-center gap-3">
            <div className="text-center">
              <Text className="text-xs text-gray-500">Min</Text>
              <Text className="text-lg font-semibold text-white">
                {latency.minLatencySeconds}s
              </Text>
            </div>
            <div className="text-gray-600">-</div>
            <div className="text-center">
              <Text className="text-xs text-gray-500">Max</Text>
              <Text className="text-lg font-semibold text-white">
                {latency.maxLatencySeconds}s
              </Text>
            </div>
            <div className="ml-auto text-center">
              <Text className="text-xs text-gray-500">Typical</Text>
              <Text className="text-lg font-semibold text-[#76B900]">
                ~{Math.round(latency.typicalLatencySeconds)}s
              </Text>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * BatchSettingsTooltips component
 *
 * Combines validation display and latency preview for batch settings.
 */
export default function BatchSettingsTooltips({
  windowSeconds,
  idleTimeoutSeconds,
  className,
}: BatchSettingsTooltipsProps) {
  return (
    <div
      data-testid="batch-settings-tooltips"
      className={clsx('space-y-3', className)}
    >
      {/* Validation warnings/errors */}
      <BatchSettingsValidationDisplay
        windowSeconds={windowSeconds}
        idleTimeoutSeconds={idleTimeoutSeconds}
      />

      {/* Latency preview */}
      <BatchSettingsLatencyPreview
        windowSeconds={windowSeconds}
        idleTimeoutSeconds={idleTimeoutSeconds}
      />
    </div>
  );
}
