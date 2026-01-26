/**
 * DeviationBadge - Visual severity indicator for anomaly deviations (NEM-3553)
 *
 * Displays a badge indicating the magnitude and severity of a deviation from baseline.
 * Uses color coding and icons to quickly communicate the severity level.
 *
 * Features:
 * - Color-coded background based on deviation magnitude
 * - Optional icon display
 * - Tooltip with detailed deviation information
 * - Supports different sizes for various contexts
 *
 * @module components/zones/DeviationBadge
 * @see NEM-3553 Zone Anomaly Baseline Visualization
 */

import { clsx } from 'clsx';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, AlertOctagon, Info } from 'lucide-react';
import { memo, useMemo } from 'react';

import { AnomalySeverity } from '../../types/zoneAnomaly';

// ============================================================================
// Types
// ============================================================================

export interface DeviationBadgeProps {
  /** The deviation value in standard deviations */
  deviation: number | null;
  /** Severity level of the anomaly */
  severity?: AnomalySeverity;
  /** Expected value from baseline */
  expectedValue?: number | null;
  /** Actual observed value */
  actualValue?: number | null;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show the trend icon */
  showIcon?: boolean;
  /** Whether to show the numeric deviation value */
  showValue?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get the color configuration based on deviation magnitude.
 */
function getDeviationConfig(deviation: number | null, severity?: AnomalySeverity) {
  // If severity is provided, use it for color
  if (severity) {
    switch (severity) {
      case AnomalySeverity.CRITICAL:
        return {
          bgColor: 'bg-red-500/20',
          textColor: 'text-red-400',
          borderColor: 'border-red-500/30',
          label: 'Critical',
        };
      case AnomalySeverity.WARNING:
        return {
          bgColor: 'bg-yellow-500/20',
          textColor: 'text-yellow-400',
          borderColor: 'border-yellow-500/30',
          label: 'Warning',
        };
      case AnomalySeverity.INFO:
      default:
        return {
          bgColor: 'bg-blue-500/20',
          textColor: 'text-blue-400',
          borderColor: 'border-blue-500/30',
          label: 'Info',
        };
    }
  }

  // Otherwise, derive from deviation magnitude
  if (deviation === null) {
    return {
      bgColor: 'bg-gray-500/20',
      textColor: 'text-gray-400',
      borderColor: 'border-gray-500/30',
      label: 'Unknown',
    };
  }

  const absDeviation = Math.abs(deviation);

  if (absDeviation >= 3) {
    return {
      bgColor: 'bg-red-500/20',
      textColor: 'text-red-400',
      borderColor: 'border-red-500/30',
      label: 'Critical',
    };
  }
  if (absDeviation >= 2) {
    return {
      bgColor: 'bg-orange-500/20',
      textColor: 'text-orange-400',
      borderColor: 'border-orange-500/30',
      label: 'High',
    };
  }
  if (absDeviation >= 1.5) {
    return {
      bgColor: 'bg-yellow-500/20',
      textColor: 'text-yellow-400',
      borderColor: 'border-yellow-500/30',
      label: 'Elevated',
    };
  }
  if (absDeviation >= 1) {
    return {
      bgColor: 'bg-blue-500/20',
      textColor: 'text-blue-400',
      borderColor: 'border-blue-500/30',
      label: 'Slight',
    };
  }
  return {
    bgColor: 'bg-green-500/20',
    textColor: 'text-green-400',
    borderColor: 'border-green-500/30',
    label: 'Normal',
  };
}

/**
 * Get the trend icon based on deviation direction and magnitude.
 */
function getTrendIcon(deviation: number | null, severity?: AnomalySeverity) {
  if (deviation === null) {
    return Minus;
  }

  // For severe anomalies, show alert icons
  if (severity === AnomalySeverity.CRITICAL) {
    return AlertOctagon;
  }
  if (severity === AnomalySeverity.WARNING) {
    return AlertTriangle;
  }
  if (severity === AnomalySeverity.INFO) {
    return Info;
  }

  // For magnitude-based, show trend direction
  if (deviation > 0.5) {
    return TrendingUp;
  }
  if (deviation < -0.5) {
    return TrendingDown;
  }
  return Minus;
}

/**
 * Get size-specific classes.
 */
function getSizeClasses(size: 'sm' | 'md' | 'lg') {
  switch (size) {
    case 'sm':
      return {
        badge: 'px-1.5 py-0.5 text-xs',
        icon: 'h-3 w-3',
        gap: 'gap-1',
      };
    case 'lg':
      return {
        badge: 'px-3 py-1.5 text-sm',
        icon: 'h-5 w-5',
        gap: 'gap-2',
      };
    case 'md':
    default:
      return {
        badge: 'px-2 py-1 text-xs',
        icon: 'h-4 w-4',
        gap: 'gap-1.5',
      };
  }
}

// ============================================================================
// Component
// ============================================================================

/**
 * DeviationBadge displays a visual indicator for anomaly deviation severity.
 *
 * The badge color and icon automatically adjust based on the deviation magnitude
 * or the provided severity level.
 *
 * @example
 * ```tsx
 * // Basic usage with deviation value
 * <DeviationBadge deviation={2.5} />
 *
 * // With severity override
 * <DeviationBadge deviation={2.5} severity={AnomalySeverity.CRITICAL} />
 *
 * // With full statistics
 * <DeviationBadge
 *   deviation={2.5}
 *   expectedValue={10}
 *   actualValue={25}
 *   showValue
 *   showIcon
 * />
 * ```
 */
function DeviationBadgeComponent({
  deviation,
  severity,
  expectedValue,
  actualValue,
  size = 'md',
  showIcon = true,
  showValue = true,
  className,
}: DeviationBadgeProps) {
  const config = useMemo(
    () => getDeviationConfig(deviation, severity),
    [deviation, severity]
  );
  const sizeClasses = useMemo(() => getSizeClasses(size), [size]);
  const TrendIcon = useMemo(
    () => getTrendIcon(deviation, severity),
    [deviation, severity]
  );

  // Build tooltip text
  const tooltipText = useMemo(() => {
    const parts: string[] = [];
    if (deviation !== null) {
      parts.push(`Deviation: ${deviation.toFixed(1)} std`);
    }
    if (expectedValue !== null && expectedValue !== undefined) {
      parts.push(`Expected: ${expectedValue.toFixed(1)}`);
    }
    if (actualValue !== null && actualValue !== undefined) {
      parts.push(`Actual: ${actualValue.toFixed(1)}`);
    }
    if (parts.length === 0) {
      parts.push('No deviation data');
    }
    return parts.join(' | ');
  }, [deviation, expectedValue, actualValue]);

  // Format display text
  const displayText = useMemo(() => {
    if (!showValue) {
      return config.label;
    }
    if (deviation === null) {
      return 'N/A';
    }
    const sign = deviation > 0 ? '+' : '';
    return `${sign}${deviation.toFixed(1)} std`;
  }, [deviation, showValue, config.label]);

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full border font-medium',
        config.bgColor,
        config.textColor,
        config.borderColor,
        sizeClasses.badge,
        sizeClasses.gap,
        className
      )}
      title={tooltipText}
      data-testid="deviation-badge"
      data-deviation={deviation}
      data-severity={severity}
    >
      {showIcon && <TrendIcon className={sizeClasses.icon} aria-hidden="true" />}
      <span>{displayText}</span>
    </span>
  );
}

/**
 * Memoized DeviationBadge component for performance.
 */
export const DeviationBadge = memo(DeviationBadgeComponent);

export default DeviationBadge;
