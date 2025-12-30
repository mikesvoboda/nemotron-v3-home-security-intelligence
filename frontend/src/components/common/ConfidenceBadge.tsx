import { clsx } from 'clsx';

import {
  formatConfidencePercent,
  getConfidenceBgColorClass,
  getConfidenceBorderColorClass,
  getConfidenceLabel,
  getConfidenceLevel,
  getConfidenceTextColorClass,
} from '../../utils/confidence';

export interface ConfidenceBadgeProps {
  confidence: number;
  size?: 'sm' | 'md' | 'lg';
  showBar?: boolean;
  className?: string;
}

/**
 * ConfidenceBadge component displays a confidence score with color coding
 * based on confidence level (low: <70%, medium: 70-85%, high: >85%)
 */
export default function ConfidenceBadge({
  confidence,
  size = 'sm',
  showBar = false,
  className,
}: ConfidenceBadgeProps) {
  const level = getConfidenceLevel(confidence);
  const percentText = formatConfidencePercent(confidence);
  const label = getConfidenceLabel(level);

  // Size-based classes
  const sizeClasses = {
    sm: {
      text: 'text-xs px-2 py-0.5',
      bar: 'h-1',
    },
    md: {
      text: 'text-sm px-2.5 py-1',
      bar: 'h-1.5',
    },
    lg: {
      text: 'text-base px-3 py-1.5',
      bar: 'h-2',
    },
  }[size];

  return (
    <span
      role="status"
      aria-label={`Detection confidence: ${percentText} (${label})`}
      title={label}
      className={clsx(
        'inline-flex flex-col items-center gap-0.5 rounded-md border font-medium',
        sizeClasses.text,
        getConfidenceBgColorClass(level),
        getConfidenceBorderColorClass(level),
        getConfidenceTextColorClass(level),
        className
      )}
    >
      <span className="font-semibold">{percentText}</span>
      {showBar && (
        <span
          className={clsx('w-full overflow-hidden rounded-full bg-gray-700', sizeClasses.bar)}
          aria-hidden="true"
        >
          <span
            className={clsx('block h-full rounded-full transition-all duration-300', {
              'bg-red-500': level === 'low',
              'bg-yellow-500': level === 'medium',
              'bg-green-500': level === 'high',
            })}
            style={{ width: percentText }}
          />
        </span>
      )}
    </span>
  );
}
