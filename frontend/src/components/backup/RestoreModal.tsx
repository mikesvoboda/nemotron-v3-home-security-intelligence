/**
 * RestoreModal Component
 *
 * Modal dialog for restore operations with file upload,
 * warnings, and progress indicators.
 *
 * @module components/backup/RestoreModal
 * @see NEM-3566
 */

import { clsx } from 'clsx';
import {
  AlertTriangle,
  CheckCircle,
  Upload,
  X,
  XCircle,
} from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

import BackupProgress from './BackupProgress';
import {
  isRestoreJobComplete,
  isRestoreJobFailed,
  isRestoreJobInProgress,
  useRestoreJob,
  useStartRestore,
} from '../../hooks/useBackup';
import AnimatedModal from '../common/AnimatedModal';
import Button from '../common/Button';

import type { RestoreJob } from '../../types/backup';

// ============================================================================
// Types
// ============================================================================

export interface RestoreModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Callback when restore is complete */
  onRestoreComplete?: () => void;
}

type ModalState = 'upload' | 'uploading' | 'restoring' | 'complete' | 'error';

// ============================================================================
// File Dropzone Component
// ============================================================================

interface FileDropzoneProps {
  onFileSelect: (file: File) => void | Promise<void>;
  disabled?: boolean;
  error?: string | null;
}

function FileDropzone({ onFileSelect, disabled, error }: FileDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragOver(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (disabled) return;

      const file = e.dataTransfer.files[0];
      if (file && file.name.endsWith('.zip')) {
        void onFileSelect(file);
      }
    },
    [disabled, onFileSelect]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        void onFileSelect(file);
      }
    },
    [onFileSelect]
  );

  const handleClick = useCallback(() => {
    if (!disabled) {
      inputRef.current?.click();
    }
  }, [disabled]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        inputRef.current?.click();
      }
    },
    [disabled]
  );

  return (
    <div
      className={clsx(
        'relative cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors',
        isDragOver && !disabled
          ? 'border-[#76B900] bg-[#76B900]/10'
          : 'border-gray-600 hover:border-gray-500',
        disabled && 'cursor-not-allowed opacity-50',
        error && 'border-red-500'
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label="Upload backup file"
      data-testid="file-dropzone"
    >
      <input
        ref={inputRef}
        type="file"
        accept=".zip"
        className="hidden"
        onChange={handleInputChange}
        disabled={disabled}
        data-testid="file-input"
      />
      <Upload className="mx-auto mb-3 h-10 w-10 text-gray-400" />
      <p className="text-sm text-white">
        <span className="font-medium text-[#76B900]">Click to upload</span> or drag and drop
      </p>
      <p className="mt-1 text-xs text-gray-400">Backup ZIP file only</p>
      {error && (
        <p className="mt-2 text-sm text-red-400" data-testid="dropzone-error">
          {error}
        </p>
      )}
    </div>
  );
}

// ============================================================================
// Warning Banner Component
// ============================================================================

function WarningBanner() {
  return (
    <div
      className="flex items-start gap-3 rounded-lg bg-yellow-500/10 p-4"
      data-testid="restore-warning"
    >
      <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-yellow-400" />
      <div>
        <p className="font-medium text-yellow-400">Warning: Data will be overwritten</p>
        <p className="mt-1 text-sm text-yellow-300/80">
          Restoring from a backup will replace all existing data including events, alerts, cameras,
          and configuration. This action cannot be undone. Make sure to create a backup of your
          current data first.
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Upload State Component
// ============================================================================

interface UploadStateProps {
  onFileSelect: (file: File) => void | Promise<void>;
  uploadError: string | null;
}

function UploadState({ onFileSelect, uploadError }: UploadStateProps) {
  return (
    <div className="space-y-4">
      <WarningBanner />
      <FileDropzone onFileSelect={onFileSelect} error={uploadError} />
    </div>
  );
}

// ============================================================================
// Uploading State Component
// ============================================================================

interface UploadingStateProps {
  fileName: string;
}

function UploadingState({ fileName }: UploadingStateProps) {
  return (
    <div className="space-y-4" data-testid="uploading-state">
      <div className="text-center">
        <div className="mb-4 inline-block h-12 w-12 rounded-full border-4 border-gray-700 border-t-[#76B900] motion-safe:animate-spin" />
        <p className="text-white">Uploading backup file...</p>
        <p className="mt-1 text-sm text-gray-400">{fileName}</p>
      </div>
    </div>
  );
}

// ============================================================================
// Restoring State Component
// ============================================================================

interface RestoringStateProps {
  job: RestoreJob;
}

function RestoringState({ job }: RestoringStateProps) {
  return (
    <div className="space-y-4" data-testid="restoring-state">
      <BackupProgress
        progress={job.progress}
        status={job.status}
        isComplete={isRestoreJobComplete(job)}
        isFailed={isRestoreJobFailed(job)}
        errorMessage={job.error_message}
      />
      {job.backup_id && (
        <p className="text-xs text-gray-400">
          Restoring from backup: {job.backup_id.slice(0, 8)}...
          {job.backup_created_at && ` (created ${new Date(job.backup_created_at).toLocaleDateString()})`}
        </p>
      )}
    </div>
  );
}

// ============================================================================
// Complete State Component
// ============================================================================

interface CompleteStateProps {
  job: RestoreJob;
  onClose: () => void;
}

function CompleteState({ job, onClose }: CompleteStateProps) {
  const itemsRestored = job.items_restored ?? {};
  const totalItems = Object.values(itemsRestored).reduce((sum, count) => sum + count, 0);

  return (
    <div className="space-y-4" data-testid="complete-state">
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/20">
          <CheckCircle className="h-8 w-8 text-green-400" />
        </div>
        <h3 className="text-lg font-semibold text-white">Restore Complete</h3>
        <p className="mt-1 text-sm text-gray-400">
          Successfully restored {totalItems} items
        </p>
      </div>

      {/* Items Restored Details */}
      {Object.keys(itemsRestored).length > 0 && (
        <div className="rounded-lg bg-gray-800/50 p-4">
          <p className="mb-2 text-sm font-medium text-gray-300">Items Restored:</p>
          <ul className="space-y-1 text-sm text-gray-400">
            {Object.entries(itemsRestored).map(([table, count]) => (
              <li key={table} className="flex justify-between">
                <span className="capitalize">{table.replace(/_/g, ' ')}</span>
                <span className="text-white">{count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Button variant="primary" fullWidth onClick={onClose}>
        Close
      </Button>
    </div>
  );
}

// ============================================================================
// Error State Component
// ============================================================================

interface ErrorStateProps {
  message: string;
  onRetry: () => void;
  onClose: () => void;
}

function ErrorState({ message, onRetry, onClose }: ErrorStateProps) {
  return (
    <div className="space-y-4" data-testid="error-state">
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-500/20">
          <XCircle className="h-8 w-8 text-red-400" />
        </div>
        <h3 className="text-lg font-semibold text-white">Restore Failed</h3>
        <p className="mt-1 text-sm text-red-300">{message}</p>
      </div>
      <div className="flex gap-3">
        <Button variant="outline" fullWidth onClick={onClose}>
          Cancel
        </Button>
        <Button variant="primary" fullWidth onClick={onRetry}>
          Try Again
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * RestoreModal provides a complete restore flow with file upload,
 * warning, progress, and completion states.
 *
 * Features:
 * - Drag and drop file upload
 * - Warning about data overwrite
 * - Upload progress
 * - Restore progress with polling
 * - Success/error states
 *
 * @example
 * ```tsx
 * <RestoreModal
 *   isOpen={isRestoreModalOpen}
 *   onClose={() => setIsRestoreModalOpen(false)}
 *   onRestoreComplete={handleRestoreComplete}
 * />
 * ```
 */
export default function RestoreModal({
  isOpen,
  onClose,
  onRestoreComplete,
}: RestoreModalProps) {
  const [modalState, setModalState] = useState<ModalState>('upload');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [restoreJobId, setRestoreJobId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');

  const { startRestore } = useStartRestore();
  const { data: restoreJob } = useRestoreJob(restoreJobId ?? '', {
    enabled: !!restoreJobId && modalState === 'restoring',
  });

  // Handle file selection
  const handleFileSelect = useCallback(
    async (file: File) => {
      setSelectedFile(file);
      setUploadError(null);
      setModalState('uploading');

      try {
        const response = await startRestore(file);
        setRestoreJobId(response.job_id);
        setModalState('restoring');
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to start restore';
        setUploadError(message);
        setErrorMessage(message);
        setModalState('error');
      }
    },
    [startRestore]
  );

  // Handle restore job status changes
  const handleJobStatusChange = useCallback(() => {
    if (!restoreJob) return;

    if (isRestoreJobComplete(restoreJob) && !isRestoreJobFailed(restoreJob)) {
      setModalState('complete');
      onRestoreComplete?.();
    } else if (isRestoreJobFailed(restoreJob)) {
      setErrorMessage(restoreJob.error_message ?? 'Restore failed');
      setModalState('error');
    }
  }, [restoreJob, onRestoreComplete]);

  // Check job status on restore job changes - only runs when in 'restoring' state
  if (restoreJob && modalState === 'restoring') {
    if (isRestoreJobComplete(restoreJob) && !isRestoreJobFailed(restoreJob)) {
      handleJobStatusChange();
    } else if (isRestoreJobFailed(restoreJob)) {
      handleJobStatusChange();
    }
  }

  // Reset state when modal closes
  const handleClose = useCallback(() => {
    // Only allow closing if not in the middle of an operation
    if (modalState === 'uploading' || (modalState === 'restoring' && restoreJob && isRestoreJobInProgress(restoreJob))) {
      return;
    }
    setModalState('upload');
    setSelectedFile(null);
    setUploadError(null);
    setRestoreJobId(null);
    setErrorMessage('');
    onClose();
  }, [modalState, restoreJob, onClose]);

  // Handle retry
  const handleRetry = useCallback(() => {
    setModalState('upload');
    setSelectedFile(null);
    setUploadError(null);
    setRestoreJobId(null);
    setErrorMessage('');
  }, []);

  // Determine if close button should be shown
  const showCloseButton = modalState !== 'uploading' &&
    !(modalState === 'restoring' && restoreJob && isRestoreJobInProgress(restoreJob));

  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={handleClose}
      size="md"
      closeOnBackdropClick={showCloseButton}
      closeOnEscape={showCloseButton}
      aria-labelledby="restore-modal-title"
      modalName="restore"
    >
      <div className="p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h2 id="restore-modal-title" className="text-lg font-semibold text-white">
            Restore from Backup
          </h2>
          {showCloseButton && (
            <button
              onClick={handleClose}
              className="rounded-lg p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
              aria-label="Close modal"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Content based on state */}
        {modalState === 'upload' && (
          <UploadState onFileSelect={handleFileSelect} uploadError={uploadError} />
        )}

        {modalState === 'uploading' && selectedFile && (
          <UploadingState fileName={selectedFile.name} />
        )}

        {modalState === 'restoring' && restoreJob && (
          <RestoringState job={restoreJob} />
        )}

        {modalState === 'complete' && restoreJob && (
          <CompleteState job={restoreJob} onClose={handleClose} />
        )}

        {modalState === 'error' && (
          <ErrorState
            message={errorMessage}
            onRetry={handleRetry}
            onClose={handleClose}
          />
        )}

        {/* Footer buttons for upload state */}
        {modalState === 'upload' && (
          <div className="mt-6 flex justify-end">
            <Button variant="ghost" onClick={handleClose}>
              Cancel
            </Button>
          </div>
        )}
      </div>
    </AnimatedModal>
  );
}
