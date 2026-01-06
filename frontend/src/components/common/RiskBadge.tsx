import { clsx } from 'clsx';
import { AlertOctagon, AlertTriangle, CheckCircle } from 'lucide-react';

import { getRiskLabel, type RiskLevel } from '../../utils/risk';

export interface RiskBadgeProps {
  level: RiskLevel;
  score?: number;
  showScore?: boolean;
  size?: 'sm' | 'md' | 'lg';
  animated?: boolean;
  className?: string;
}

/**
 * RiskBadge component displays risk levels with appropriate styling and colors
 */
export default function RiskBadge({
  level,
  score,
  showScore = false,
  size = 'md',
  animated = true,
  className,
}: RiskBadgeProps) {
  // Get the icon component based on risk level
  const Icon = {
    low: CheckCircle,
    medium: AlertTriangle,
    high: AlertTriangle,
    critical: AlertOctagon,
  }[level];

  // Get icon size based on badge size
  const iconSize = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  }[size];

  // Get text size and padding based on badge size
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-2.5 py-1',
    lg: 'text-base px-3 py-1.5',
  }[size];

  // Get color classes based on risk level
  const colorClasses = {
    low: 'bg-risk-low/10 text-risk-low',
    medium: 'bg-risk-medium/10 text-risk-medium',
    high: 'bg-risk-high/10 text-risk-high',
    critical: 'bg-red-500/10 text-red-500',
  }[level];

  // Apply pulse animation only for critical level
  const shouldAnimate = animated && level === 'critical';

  // Build display text
  const label = getRiskLabel(level);
  const displayText = showScore && score !== undefined ? `${label} (${score})` : label;

  // Build aria-label for accessibility
  const ariaLabel =
    showScore && score !== undefined
      ? `Risk level: ${label}, score ${score}`
      : `Risk level: ${label}`;

  return (
    <span
      role="status"
      aria-label={ariaLabel}
      className={clsx(
        'inline-flex items-center gap-1 rounded-full font-medium',
        sizeClasses,
        colorClasses,
        shouldAnimate && 'animate-pulse',
        className
      )}
      data-testid="risk-badge"
    >
      <Icon className={iconSize} />
      {displayText}
    </span>
  );
}
