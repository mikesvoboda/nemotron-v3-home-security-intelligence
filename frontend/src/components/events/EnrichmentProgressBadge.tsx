/**
 * EnrichmentProgressBadge - Displays real-time enrichment progress status
 *
 * Shows the current state of enrichment processing for security events:
 * - Not started: Empty/hidden (no badge)
 * - In progress: Animated spinner with progress percentage
 * - Completed: Success checkmark
 * - Failed: Error icon with message
 *
 * Integrates with useEventEnrichmentWebSocket hook for real-time updates.
 *
 * @module components/events/EnrichmentProgressBadge
 */

import { clsx } from 'clsx';
import { AlertCircle, CheckCircle, Loader2, Sparkles } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

/**
 * Enrichment status values for the badge
 */
export type EnrichmentProgressStatus = 'not_started' | 'in_progress' | 'completed' | 'failed';

/**
 * Props for the EnrichmentProgressBadge component
 */
export interface EnrichmentProgressBadgeProps {
  /** Current status of the enrichment */
  status: EnrichmentProgressStatus;
  /** Progress percentage (0-100) when in progress */
  progress?: number;
  /** Current processing stage name */
  stage?: string;
  /** Error message when status is failed */
  error?: string;
  /** Size variant for the badge */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show the stage/step label */
  showLabel?: boolean;
  /** Whether to show progress percentage */
  showProgress?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Tooltip override (defaults to stage or error) */
  tooltip?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get the appropriate icon based on enrichment status
 */
function getStatusIcon(status: EnrichmentProgressStatus, size: string) {
  const iconClasses = clsx(size, {
    'animate-spin': status === 'in_progress',
  });

  switch (status) {
    case 'not_started':
      return <Sparkles className={iconClasses} />;
    case 'in_progress':
      return <Loader2 className={iconClasses} />;
    case 'completed':
      return <CheckCircle className={iconClasses} />;
    case 'failed':
      return <AlertCircle className={iconClasses} />;
    default:
      return <Sparkles className={iconClasses} />;
  }
}

/**
 * Get color classes based on enrichment status
 */
function getStatusColorClasses(status: EnrichmentProgressStatus): string {
  switch (status) {
    case 'not_started':
      return 'bg-gray-500/20 border-gray-500/40 text-gray-400';
    case 'in_progress':
      return 'bg-blue-500/20 border-blue-500/40 text-blue-400';
    case 'completed':
      return 'bg-green-500/20 border-green-500/40 text-green-400';
    case 'failed':
      return 'bg-red-500/20 border-red-500/40 text-red-400';
    default:
      return 'bg-gray-500/20 border-gray-500/40 text-gray-400';
  }
}

/**
 * Get display label based on enrichment status
 */
function getStatusLabel(
  status: EnrichmentProgressStatus,
  stage?: string,
  progress?: number
): string {
  switch (status) {
    case 'not_started':
      return 'Pending';
    case 'in_progress': {
      if (stage && progress !== undefined) {
        return `${stage} (${progress}%)`;
      }
      if (progress !== undefined) {
        return `${progress}%`;
      }
      if (stage) {
        return stage;
      }
      return 'Enriching...';
    }
    case 'completed':
      return 'Enriched';
    case 'failed':
      return 'Failed';
    default:
      return 'Unknown';
  }
}

/**
 * Get icon size class based on badge size
 */
function getIconSizeClass(size: 'sm' | 'md' | 'lg'): string {
  switch (size) {
    case 'sm':
      return 'h-3 w-3';
    case 'md':
      return 'h-4 w-4';
    case 'lg':
      return 'h-5 w-5';
    default:
      return 'h-4 w-4';
  }
}

/**
 * Get badge size classes
 */
function getBadgeSizeClasses(size: 'sm' | 'md' | 'lg'): string {
  switch (size) {
    case 'sm':
      return 'px-2 py-0.5 text-xs gap-1';
    case 'md':
      return 'px-2.5 py-1 text-sm gap-1.5';
    case 'lg':
      return 'px-3 py-1.5 text-base gap-2';
    default:
      return 'px-2.5 py-1 text-sm gap-1.5';
  }
}

// ============================================================================
// Component
// ============================================================================

/**
 * EnrichmentProgressBadge - Displays enrichment status with visual indicator
 *
 * @example
 * ```tsx
 * // Basic usage
 * <EnrichmentProgressBadge status="in_progress" progress={45} stage="Face Detection" />
 *
 * // Completed state
 * <EnrichmentProgressBadge status="completed" />
 *
 * // Failed state with error
 * <EnrichmentProgressBadge status="failed" error="Model timeout" />
 * ```
 */
export default function EnrichmentProgressBadge({
  status,
  progress,
  stage,
  error,
  size = 'sm',
  showLabel = true,
  showProgress = true,
  className,
  tooltip,
}: EnrichmentProgressBadgeProps) {
  // Don't render for not_started status (clean UI when no enrichment)
  if (status === 'not_started') {
    return null;
  }

  const iconSizeClass = getIconSizeClass(size);
  const colorClasses = getStatusColorClasses(status);
  const sizeClasses = getBadgeSizeClasses(size);
  const label = getStatusLabel(status, stage, showProgress ? progress : undefined);
  const tooltipText = tooltip ?? (status === 'failed' ? error : stage);

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full border font-medium transition-colors',
        colorClasses,
        sizeClasses,
        className
      )}
      title={tooltipText}
      role="status"
      aria-label={`Enrichment status: ${label}`}
      data-testid="enrichment-progress-badge"
      data-status={status}
    >
      {getStatusIcon(status, iconSizeClass)}
      {showLabel && <span>{label}</span>}
    </span>
  );
}

// ============================================================================
// Progress Bar Variant
// ============================================================================

export interface EnrichmentProgressBarProps {
  /** Progress percentage (0-100) */
  progress: number;
  /** Current processing stage name */
  stage?: string;
  /** Total number of steps */
  totalSteps?: number;
  /** Current step number */
  currentStep?: number;
  /** Whether the progress bar should be animated */
  animated?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * EnrichmentProgressBar - Displays a horizontal progress bar for enrichment
 *
 * Use this for detailed progress views (e.g., in event detail modals)
 *
 * @example
 * ```tsx
 * <EnrichmentProgressBar
 *   progress={65}
 *   stage="License Plate OCR"
 *   currentStep={3}
 *   totalSteps={5}
 * />
 * ```
 */
export function EnrichmentProgressBar({
  progress,
  stage,
  totalSteps,
  currentStep,
  animated = true,
  className,
}: EnrichmentProgressBarProps) {
  const clampedProgress = Math.max(0, Math.min(100, progress));

  return (
    <div
      className={clsx('w-full', className)}
      data-testid="enrichment-progress-bar"
      role="progressbar"
      aria-valuenow={clampedProgress}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={stage ? `Enriching: ${stage}` : 'Enrichment in progress'}
    >
      {/* Header with stage and step info */}
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="font-medium text-gray-300">
          {stage ?? 'Processing...'}
        </span>
        <div className="flex items-center gap-2 text-gray-400">
          {totalSteps !== undefined && currentStep !== undefined && (
            <span>
              Step {currentStep} / {totalSteps}
            </span>
          )}
          <span className="font-semibold text-white">{clampedProgress}%</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
        <div
          className={clsx(
            'h-full rounded-full bg-gradient-to-r from-[#76B900] to-[#8ACE00]',
            animated && 'transition-all duration-300 ease-out'
          )}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
    </div>
  );
}
