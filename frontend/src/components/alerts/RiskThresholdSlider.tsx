/**
 * RiskThresholdSlider - Visual range slider for risk threshold configuration.
 *
 * Features:
 * - Visual range slider (0-100)
 * - Color gradient (green -> yellow -> orange -> red)
 * - Severity zone indicators (Low/Medium/High/Critical)
 * - Numeric input for precise values
 * - Tooltip showing current value
 *
 * @see NEM-3604 Alert Threshold Configuration
 */

import { clsx } from 'clsx';
import { useCallback, useMemo } from 'react';

// =============================================================================
// Types
// =============================================================================

export interface RiskThresholdSliderProps {
  /** Current threshold value (0-100 or null) */
  value: number | null;
  /** Callback when value changes */
  onChange: (value: number | null) => void;
  /** Whether the slider is disabled */
  disabled?: boolean;
  /** Optional className for the container */
  className?: string;
  /** Show the numeric input alongside slider */
  showNumericInput?: boolean;
  /** Test ID prefix for testing */
  testIdPrefix?: string;
}

export interface SeverityZone {
  label: string;
  min: number;
  max: number;
  color: string;
  bgColor: string;
  textColor: string;
}

// =============================================================================
// Constants
// =============================================================================

/**
 * Severity zones based on risk threshold ranges.
 * These align with common security event categorization.
 */
export const SEVERITY_ZONES: readonly SeverityZone[] = [
  {
    label: 'Low',
    min: 0,
    max: 25,
    color: '#22c55e', // green-500
    bgColor: 'bg-green-500/20',
    textColor: 'text-green-400',
  },
  {
    label: 'Medium',
    min: 26,
    max: 50,
    color: '#eab308', // yellow-500
    bgColor: 'bg-yellow-500/20',
    textColor: 'text-yellow-400',
  },
  {
    label: 'High',
    min: 51,
    max: 75,
    color: '#f97316', // orange-500
    bgColor: 'bg-orange-500/20',
    textColor: 'text-orange-400',
  },
  {
    label: 'Critical',
    min: 76,
    max: 100,
    color: '#ef4444', // red-500
    bgColor: 'bg-red-500/20',
    textColor: 'text-red-400',
  },
] as const;

/**
 * Get the severity zone for a given threshold value.
 */
// eslint-disable-next-line react-refresh/only-export-components -- utility function used by tests
export function getSeverityZone(value: number | null): SeverityZone | null {
  if (value === null) return null;
  return SEVERITY_ZONES.find((zone) => value >= zone.min && value <= zone.max) ?? null;
}

/**
 * Get the color for a given threshold value on the gradient.
 */
// eslint-disable-next-line react-refresh/only-export-components -- utility function used by tests
export function getThresholdColor(value: number): string {
  if (value <= 25) return '#22c55e'; // green
  if (value <= 50) return '#eab308'; // yellow
  if (value <= 75) return '#f97316'; // orange
  return '#ef4444'; // red
}

// =============================================================================
// Component
// =============================================================================

/**
 * Visual slider for configuring risk threshold with severity zone indicators.
 */
export default function RiskThresholdSlider({
  value,
  onChange,
  disabled = false,
  className,
  showNumericInput = true,
  testIdPrefix = 'risk-threshold',
}: RiskThresholdSliderProps) {
  const currentZone = useMemo(() => getSeverityZone(value), [value]);

  // Handle slider change
  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = parseInt(e.target.value, 10);
      onChange(isNaN(newValue) ? null : newValue);
    },
    [onChange]
  );

  // Handle numeric input change
  const handleNumericChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const inputValue = e.target.value;
      if (inputValue === '') {
        onChange(null);
        return;
      }
      const newValue = parseInt(inputValue, 10);
      if (!isNaN(newValue)) {
        // Clamp to valid range
        onChange(Math.min(100, Math.max(0, newValue)));
      }
    },
    [onChange]
  );

  // Calculate the color for the thumb indicator
  const thumbColor = value !== null ? getThresholdColor(value) : '#6b7280';

  return (
    <div className={clsx('space-y-3', className)}>
      {/* Slider with gradient track */}
      <div className="relative">
        {/* Gradient background track */}
        <div
          className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-full"
          style={{
            background:
              'linear-gradient(to right, #22c55e 0%, #22c55e 25%, #eab308 25%, #eab308 50%, #f97316 50%, #f97316 75%, #ef4444 75%, #ef4444 100%)',
            opacity: disabled ? 0.5 : 1,
          }}
          data-testid={`${testIdPrefix}-track`}
        />

        {/* Active portion indicator */}
        {value !== null && (
          <div
            className="pointer-events-none absolute top-1/2 h-2 -translate-y-1/2 rounded-l-full"
            style={{
              left: 0,
              width: `${value}%`,
              background: 'rgba(0, 0, 0, 0.3)',
            }}
          />
        )}

        {/* Range input */}
        <input
          id="risk-threshold-slider"
          type="range"
          min={0}
          max={100}
          value={value ?? 50}
          onChange={handleSliderChange}
          disabled={disabled}
          className={clsx(
            'relative z-10 h-6 w-full cursor-pointer appearance-none bg-transparent',
            '[&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5',
            '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full',
            '[&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white',
            '[&::-webkit-slider-thumb]:shadow-md',
            '[&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:w-5',
            '[&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:rounded-full',
            '[&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white',
            '[&::-moz-range-thumb]:shadow-md',
            disabled && 'cursor-not-allowed opacity-50'
          )}
          style={
            {
              '--thumb-color': thumbColor,
              // Webkit thumb color
              WebkitAppearance: 'none',
            } as React.CSSProperties
          }
          data-testid={`${testIdPrefix}-slider`}
          aria-label="Risk threshold slider"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={value ?? undefined}
          aria-valuetext={value !== null ? `${value} - ${currentZone?.label ?? 'Unknown'}` : 'Not set'}
        />

        {/* Custom thumb styling via CSS variables */}
        <style>{`
          [data-testid="${testIdPrefix}-slider"]::-webkit-slider-thumb {
            background-color: ${thumbColor};
          }
          [data-testid="${testIdPrefix}-slider"]::-moz-range-thumb {
            background-color: ${thumbColor};
          }
        `}</style>
      </div>

      {/* Severity zone labels */}
      <div className="flex justify-between text-xs" data-testid={`${testIdPrefix}-zone-labels`}>
        {SEVERITY_ZONES.map((zone) => (
          <div
            key={zone.label}
            className={clsx(
              'flex flex-col items-center',
              currentZone?.label === zone.label ? zone.textColor : 'text-gray-500'
            )}
          >
            <span className="font-medium">{zone.label}</span>
            <span className="text-gray-600">
              {zone.min}-{zone.max}
            </span>
          </div>
        ))}
      </div>

      {/* Numeric input and current zone indicator */}
      {showNumericInput && (
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <label
              htmlFor={`${testIdPrefix}-numeric-input`}
              className="text-sm text-text-secondary"
            >
              Threshold:
            </label>
            <input
              type="number"
              id={`${testIdPrefix}-numeric-input`}
              value={value ?? ''}
              onChange={handleNumericChange}
              min={0}
              max={100}
              disabled={disabled}
              placeholder="--"
              className={clsx(
                'w-20 rounded-lg border bg-card px-2 py-1 text-center text-sm text-text-primary',
                'focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary',
                disabled ? 'cursor-not-allowed opacity-50' : 'border-gray-700'
              )}
              data-testid={`${testIdPrefix}-numeric-input`}
              aria-label="Risk threshold numeric input"
            />
          </div>

          {/* Current zone badge */}
          {currentZone && (
            <div
              className={clsx(
                'rounded-full px-3 py-1 text-xs font-medium',
                currentZone.bgColor,
                currentZone.textColor
              )}
              data-testid={`${testIdPrefix}-zone-badge`}
            >
              {currentZone.label} Risk
            </div>
          )}
        </div>
      )}
    </div>
  );
}
