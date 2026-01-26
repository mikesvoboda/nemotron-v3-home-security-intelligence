/**
 * BackupProgress Component
 *
 * Progress indicator for running backup or restore jobs.
 * Shows current step and percentage with auto-updates via polling.
 *
 * @module components/backup/BackupProgress
 * @see NEM-3566
 */

import { clsx } from 'clsx';
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

import type { BackupJobProgress, RestoreJobProgress } from '../../types/backup';

// ============================================================================
// Types
// ============================================================================

export interface BackupProgressProps {
  /** Progress information */
  progress: BackupJobProgress | RestoreJobProgress;
  /** Current status label */
  status: string;
  /** Error message if failed */
  errorMessage?: string | null;
  /** Whether job is complete */
  isComplete?: boolean;
  /** Whether job failed */
  isFailed?: boolean;
  /** Optional CSS class */
  className?: string;
  /** Size variant */
  size?: 'sm' | 'md';
}

// ============================================================================
// Status Badge Component
// ============================================================================

interface StatusBadgeProps {
  status: string;
  isRunning: boolean;
  isComplete: boolean;
  isFailed: boolean;
}

function StatusBadge({ status, isRunning, isComplete, isFailed }: StatusBadgeProps) {
  const getStatusConfig = () => {
    if (isFailed) {
      return {
        label: 'Failed',
        icon: AlertCircle,
        className: 'bg-red-500/20 text-red-400 border-red-500/30',
      };
    }
    if (isComplete) {
      return {
        label: 'Completed',
        icon: CheckCircle,
        className: 'bg-green-500/20 text-green-400 border-green-500/30',
      };
    }
    if (isRunning) {
      return {
        label: status.charAt(0).toUpperCase() + status.slice(1),
        icon: Loader2,
        className: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      };
    }
    return {
      label: 'Pending',
      icon: Loader2,
      className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    };
  };

  const config = getStatusConfig();
  const Icon = config.icon;

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium',
        config.className
      )}
    >
      <Icon className={clsx('h-3.5 w-3.5', isRunning && !isComplete && !isFailed && 'animate-spin')} />
      {config.label}
    </span>
  );
}

// ============================================================================
// Progress Bar Component
// ============================================================================

interface ProgressBarProps {
  percent: number;
  size: 'sm' | 'md';
  isFailed?: boolean;
}

function ProgressBar({ percent, size, isFailed }: ProgressBarProps) {
  return (
    <div
      className={clsx(
        'w-full overflow-hidden rounded-full bg-gray-700',
        size === 'sm' ? 'h-1.5' : 'h-2'
      )}
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={clsx(
          'h-full rounded-full transition-all duration-300',
          isFailed ? 'bg-red-500' : 'bg-[#76B900]'
        )}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * BackupProgress displays the progress of a running backup or restore job.
 *
 * Features:
 * - Visual progress bar with percentage
 * - Status badge showing current state
 * - Current step description
 * - Error message display for failures
 * - Supports both backup and restore progress
 *
 * @example
 * ```tsx
 * <BackupProgress
 *   progress={job.progress}
 *   status={job.status}
 *   isComplete={job.status === 'completed'}
 *   isFailed={job.status === 'failed'}
 *   errorMessage={job.error_message}
 * />
 * ```
 */
export default function BackupProgress({
  progress,
  status,
  errorMessage,
  isComplete = false,
  isFailed = false,
  className,
  size = 'md',
}: BackupProgressProps) {
  const isRunning = status === 'running' || status === 'validating' || status === 'restoring';

  return (
    <div className={clsx('rounded-lg bg-gray-800/50 p-4', className)} data-testid="backup-progress">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <StatusBadge
          status={status}
          isRunning={isRunning}
          isComplete={isComplete}
          isFailed={isFailed}
        />
        <span className={clsx('font-medium', size === 'sm' ? 'text-sm' : 'text-base', 'text-white')}>
          {progress.progress_percent}%
        </span>
      </div>

      {/* Progress Bar */}
      <ProgressBar percent={progress.progress_percent} size={size} isFailed={isFailed} />

      {/* Current Step */}
      {progress.current_step && !isFailed && (
        <p className={clsx('mt-2 text-gray-400', size === 'sm' ? 'text-xs' : 'text-sm')}>
          {progress.current_step}
        </p>
      )}

      {/* Tables Progress */}
      {!isFailed && progress.total_tables > 0 && (
        <p className={clsx('mt-1 text-gray-500', size === 'sm' ? 'text-xs' : 'text-sm')}>
          {progress.completed_tables} of {progress.total_tables} tables
        </p>
      )}

      {/* Error Message */}
      {isFailed && errorMessage && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-red-500/10 p-3">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
          <span className="text-sm text-red-300">{errorMessage}</span>
        </div>
      )}

      {/* Success Message */}
      {isComplete && !isFailed && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-green-500/10 p-3">
          <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-400" />
          <span className="text-sm text-green-300">Operation completed successfully</span>
        </div>
      )}
    </div>
  );
}
