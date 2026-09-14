/**
 * AlertBadge - Compact badge showing Prometheus alert counts by severity
 *
 * Displays active infrastructure alert counts with colored indicators.
 * Clicking the badge opens the AlertDrawer for detailed alert view.
 *
 * NEM-3123: Phase 3.2 - Prometheus alert UI components
 *
 * @example
 * ```tsx
 * <AlertBadge
 *   counts={{ critical: 2, warning: 5, info: 0, total: 7 }}
 *   onClick={openDrawer}
 *   isAnimating={hasNewAlerts}
 * />
 * ```
 */

import { clsx } from 'clsx';
import { Bell, AlertTriangle, AlertOctagon, Info } from 'lucide-react';
import { forwardRef } from 'react';

import type { AlertCounts } from '../../hooks/usePrometheusAlerts';

// ============================================================================
// Types
// ============================================================================

export interface AlertBadgeProps {
  /** Alert counts grouped by severity */
  counts: AlertCounts;

  /** Called when the badge is clicked */
  onClick?: () => void;

  /** Whether to show animation for new alerts */
  isAnimating?: boolean;

  /** Whether the alert drawer is currently open */
  isOpen?: boolean;

  /** Additional CSS classes */
  className?: string;

  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
}

// ============================================================================
// Component
// ============================================================================

/**
 * AlertBadge displays a compact summary of active Prometheus alerts.
 *
 * Shows colored count indicators for critical (red) and warning (yellow) alerts.
 * Pulses/animates when new alerts arrive. Clicking opens the AlertDrawer.
 */
const AlertBadge = forwardRef<HTMLButtonElement, AlertBadgeProps>(function AlertBadge(
  { counts, onClick, isAnimating = false, isOpen = false, className, size = 'md' },
  ref
) {
  const { critical, warning, info, total } = counts;
  const hasAlerts = total > 0;
  const hasCritical = critical > 0;

  // Size-based styling
  const sizeClasses = {
    sm: {
      container: 'px-2 py-1 gap-1.5 text-xs',
      icon: 'w-3.5 h-3.5',
      count: 'min-w-[1rem] h-4 text-[10px]',
    },
    md: {
      container: 'px-3 py-1.5 gap-2 text-sm',
      icon: 'w-4 h-4',
      count: 'min-w-[1.25rem] h-5 text-xs',
    },
    lg: {
      container: 'px-4 py-2 gap-2.5 text-base',
      icon: 'w-5 h-5',
      count: 'min-w-[1.5rem] h-6 text-sm',
    },
  }[size];

  // Build aria-label for accessibility
  const alertSummary = [];
  if (critical > 0) alertSummary.push(`${critical} critical`);
  if (warning > 0) alertSummary.push(`${warning} warning`);
  if (info > 0) alertSummary.push(`${info} info`);

  const ariaLabel =
    total === 0
      ? 'No active alerts'
      : `${total} active alert${total !== 1 ? 's' : ''}: ${alertSummary.join(', ')}`;

  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      aria-expanded={isOpen}
      aria-haspopup="dialog"
      data-testid="alert-badge"
      className={clsx(
        // Base styles - NVIDIA dark theme
        'inline-flex items-center rounded-lg font-medium',
        'bg-nvidia-surface border-nvidia-border border',
        'text-nvidia-text-secondary',
        'transition-all duration-200 ease-in-out',
        // Hover and focus states
        'hover:bg-nvidia-surface-light hover:border-nvidia-border-light',
        'focus:ring-nvidia-green/50 focus:ring-offset-nvidia-bg focus:outline-none focus:ring-2 focus:ring-offset-2',
        // Active state when drawer is open
        isOpen && 'bg-nvidia-surface-light border-nvidia-green/50',
        // Animation for new alerts
        isAnimating && hasCritical && 'motion-safe:animate-pulse-critical',
        isAnimating && !hasCritical && hasAlerts && 'motion-safe:animate-pulse',
        // Size classes
        sizeClasses.container,
        className
      )}
    >
      {/* Bell icon */}
      <Bell
        className={clsx(
          sizeClasses.icon,
          hasAlerts ? 'text-nvidia-text-primary' : 'text-nvidia-text-muted'
        )}
        data-testid="alert-badge-icon"
      />

      {/* Alert counts */}
      {hasAlerts ? (
        <div className="flex items-center gap-1.5" data-testid="alert-badge-counts">
          {/* Critical alerts */}
          {critical > 0 && (
            <span
              className={clsx(
                'inline-flex items-center justify-center gap-0.5 rounded-full px-1.5',
                'bg-risk-critical/20 font-semibold text-risk-critical',
                sizeClasses.count
              )}
              data-testid="alert-badge-critical"
            >
              <AlertOctagon className="h-3 w-3" />
              <span>{critical}</span>
            </span>
          )}

          {/* Warning alerts */}
          {warning > 0 && (
            <span
              className={clsx(
                'inline-flex items-center justify-center gap-0.5 rounded-full px-1.5',
                'bg-risk-medium/20 font-semibold text-risk-medium',
                sizeClasses.count
              )}
              data-testid="alert-badge-warning"
            >
              <AlertTriangle className="h-3 w-3" />
              <span>{warning}</span>
            </span>
          )}

          {/* Info alerts - only show if no critical/warning or if explicitly requested */}
          {info > 0 && critical === 0 && warning === 0 && (
            <span
              className={clsx(
                'inline-flex items-center justify-center gap-0.5 rounded-full px-1.5',
                'bg-nvidia-blue/20 text-nvidia-blue font-semibold',
                sizeClasses.count
              )}
              data-testid="alert-badge-info"
            >
              <Info className="h-3 w-3" />
              <span>{info}</span>
            </span>
          )}
        </div>
      ) : (
        <span className="text-nvidia-text-muted" data-testid="alert-badge-empty">
          No alerts
        </span>
      )}
    </button>
  );
});

export default AlertBadge;
