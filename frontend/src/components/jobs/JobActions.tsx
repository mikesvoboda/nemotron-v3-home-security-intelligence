/**
 * JobActions component for job lifecycle management (NEM-2712).
 *
 * Renders action buttons based on job status:
 * - Pending: Cancel, Delete
 * - Running: Cancel, Abort
 * - Completed: Delete
 * - Failed: Retry, Delete
 * - Cancelled: Retry, Delete
 *
 * Includes confirmation dialogs for destructive actions.
 *
 * @example
 * ```tsx
 * <JobActions
 *   job={job}
 *   onSuccess={(action, response) => toast.success(`Job ${action}ed`)}
 *   onDelete={() => navigate('/jobs')}
 *   onRetry={(newJob) => navigate(`/jobs/${newJob.id}`)}
 * />
 * ```
 */
import { Ban, RefreshCw, Trash2, XCircle } from 'lucide-react';
import { memo, useState, useCallback } from 'react';

import ConfirmDialog from './ConfirmDialog';
import { useJobMutations } from '../../hooks/useJobMutations';

import type { JobResponse, JobCancelResponse, JobAbortResponse } from '../../services/api';

export type JobActionType = 'cancel' | 'abort' | 'retry' | 'delete';

export interface JobActionsProps {
  /** The job to show actions for */
  job: JobResponse;
  /** Compact mode shows icon-only buttons */
  compact?: boolean;
  /** Callback when an action succeeds */
  onSuccess?: (action: JobActionType, response: JobCancelResponse | JobAbortResponse | JobResponse) => void;
  /** Callback when an action fails */
  onError?: (action: JobActionType, error: Error) => void;
  /** Callback after successful delete (e.g., navigate away) */
  onDelete?: () => void;
  /** Callback after successful retry (receives new job) */
  onRetry?: (newJob: JobResponse) => void;
}

/**
 * Dialog configuration for each action type
 */
interface DialogConfig {
  title: string;
  description: string;
  confirmLabel: string;
  variant: 'default' | 'warning' | 'danger';
  loadingText: string;
}

const dialogConfigs: Record<'cancel' | 'abort' | 'delete', DialogConfig> = {
  cancel: {
    title: 'Cancel Job',
    description: 'This will gracefully stop the job. The job will complete its current operation before stopping.',
    confirmLabel: 'Cancel Job',
    variant: 'warning',
    loadingText: 'Cancelling...',
  },
  abort: {
    title: 'Force Abort Job',
    description: 'WARNING: This will forcefully terminate the job immediately. This may cause data inconsistency if the job was in the middle of an operation.',
    confirmLabel: 'Force Abort',
    variant: 'danger',
    loadingText: 'Aborting...',
  },
  delete: {
    title: 'Delete Job',
    description: 'This action cannot be undone. The job record will be permanently deleted from the database.',
    confirmLabel: 'Delete Job',
    variant: 'danger',
    loadingText: 'Deleting...',
  },
};

/**
 * Button styling configuration
 */
const buttonStyles = {
  base: 'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50',
  cancel: 'bg-amber-600/20 text-amber-400 hover:bg-amber-600/30 focus:ring-amber-500/50',
  abort: 'bg-red-600/20 text-red-400 hover:bg-red-600/30 focus:ring-red-500/50',
  retry: 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 focus:ring-blue-500/50',
  delete: 'bg-gray-700/50 text-gray-300 hover:bg-gray-700 focus:ring-gray-500/50',
};

/**
 * JobActions - Renders action buttons for a job based on its status
 */
const JobActions = memo(function JobActions({
  job,
  compact = false,
  onSuccess,
  onError,
  onDelete,
  onRetry,
}: JobActionsProps) {
  const [activeDialog, setActiveDialog] = useState<'cancel' | 'abort' | 'delete' | null>(null);

  const {
    cancelJob,
    abortJob,
    retryJob,
    deleteJob,
    isCancelling,
    isAborting,
    isRetrying,
    isDeleting,
    isMutating,
  } = useJobMutations();

  // Determine available actions based on status
  const status = job.status;
  const canCancel = status === 'pending' || status === 'running';
  const canAbort = status === 'running';
  const canRetry = status === 'failed';
  const canDelete = status === 'pending' || status === 'completed' || status === 'failed';

  // Handle action execution
  const handleCancel = useCallback(async () => {
    try {
      const response = await cancelJob(job.job_id);
      setActiveDialog(null);
      onSuccess?.('cancel', response);
    } catch (error) {
      onError?.('cancel', error instanceof Error ? error : new Error(String(error)));
    }
  }, [cancelJob, job.job_id, onSuccess, onError]);

  const handleAbort = useCallback(async () => {
    try {
      const response = await abortJob(job.job_id);
      setActiveDialog(null);
      onSuccess?.('abort', response);
    } catch (error) {
      onError?.('abort', error instanceof Error ? error : new Error(String(error)));
    }
  }, [abortJob, job.job_id, onSuccess, onError]);

  const handleRetry = useCallback(async () => {
    try {
      const response = await retryJob(job.job_id);
      onSuccess?.('retry', response);
      onRetry?.(response);
    } catch (error) {
      onError?.('retry', error instanceof Error ? error : new Error(String(error)));
    }
  }, [retryJob, job.job_id, onSuccess, onError, onRetry]);

  const handleDelete = useCallback(async () => {
    try {
      const response = await deleteJob(job.job_id);
      setActiveDialog(null);
      onSuccess?.('delete', response);
      onDelete?.();
    } catch (error) {
      onError?.('delete', error instanceof Error ? error : new Error(String(error)));
    }
  }, [deleteJob, job.job_id, onSuccess, onError, onDelete]);

  // Render button with optional compact mode
  const renderButton = (
    _action: 'cancel' | 'abort' | 'retry' | 'delete',
    icon: React.ReactNode,
    label: string,
    onClick: () => void,
    isLoading: boolean,
    style: string
  ) => (
    <button
      type="button"
      onClick={onClick}
      disabled={isMutating}
      className={`${buttonStyles.base} ${style}`}
      aria-label={label}
    >
      {icon}
      {compact ? (
        <span className="sr-only">{label}</span>
      ) : (
        <span>{isLoading ? `${label}...` : label}</span>
      )}
    </button>
  );

  return (
    <>
      <div className="flex items-center gap-2">
        {/* Cancel Button */}
        {canCancel && renderButton(
          'cancel',
          <XCircle className="h-4 w-4" />,
          'Cancel',
          () => setActiveDialog('cancel'),
          isCancelling,
          buttonStyles.cancel
        )}

        {/* Abort Button */}
        {canAbort && renderButton(
          'abort',
          <Ban className="h-4 w-4" />,
          'Abort',
          () => setActiveDialog('abort'),
          isAborting,
          buttonStyles.abort
        )}

        {/* Retry Button - no confirmation needed */}
        {canRetry && renderButton(
          'retry',
          <RefreshCw className={`h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`} />,
          'Retry',
          () => void handleRetry(),
          isRetrying,
          buttonStyles.retry
        )}

        {/* Delete Button */}
        {canDelete && renderButton(
          'delete',
          <Trash2 className="h-4 w-4" />,
          'Delete',
          () => setActiveDialog('delete'),
          isDeleting,
          buttonStyles.delete
        )}
      </div>

      {/* Cancel Confirmation Dialog */}
      <ConfirmDialog
        isOpen={activeDialog === 'cancel'}
        title={dialogConfigs.cancel.title}
        description={dialogConfigs.cancel.description}
        confirmLabel={dialogConfigs.cancel.confirmLabel}
        variant={dialogConfigs.cancel.variant}
        isLoading={isCancelling}
        loadingText={dialogConfigs.cancel.loadingText}
        onConfirm={() => void handleCancel()}
        onCancel={() => setActiveDialog(null)}
      />

      {/* Abort Confirmation Dialog */}
      <ConfirmDialog
        isOpen={activeDialog === 'abort'}
        title={dialogConfigs.abort.title}
        description={dialogConfigs.abort.description}
        confirmLabel={dialogConfigs.abort.confirmLabel}
        variant={dialogConfigs.abort.variant}
        isLoading={isAborting}
        loadingText={dialogConfigs.abort.loadingText}
        onConfirm={() => void handleAbort()}
        onCancel={() => setActiveDialog(null)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={activeDialog === 'delete'}
        title={dialogConfigs.delete.title}
        description={dialogConfigs.delete.description}
        confirmLabel={dialogConfigs.delete.confirmLabel}
        variant={dialogConfigs.delete.variant}
        isLoading={isDeleting}
        loadingText={dialogConfigs.delete.loadingText}
        onConfirm={() => void handleDelete()}
        onCancel={() => setActiveDialog(null)}
      />
    </>
  );
});

export default JobActions;
